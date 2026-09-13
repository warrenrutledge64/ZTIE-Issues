"""ZTIE Story 3.4 (RD-039) — Hub-side findings + prioritized-remediations Lambda.

The findings + remediations step of Phase 3. For one intake it reads the Story 3.3
(RD-038) ``scoring_result`` (three independent 0-100 Nova Pro risk scores: static /
dynamic / combined) AND the Story 3.2 (RD-035) ``correlation_result`` (the categorized
static<->dynamic findings) ALREADY on the Hub tracking item and produces a bounded,
DERIVED, verdict-free ``remediation_result`` (``remediation.contract.v1``): DETAILED
FINDINGS (the correlation findings surfaced + the migrated candidate-false-positive
list + the gap list) and a PRIORITIZED REMEDIATION list ranked highest-risk-first by
the three risk scores + the finding/gap severities. It records the result back onto the
SAME item.

RD-039 CONTRACT-FIRST decision: this is PURE Hub-side post-processing — it makes NO
model call. The inputs are already fully structured (three 0-100 scores + categorized
findings), so building the findings view + ranking the remediations is deterministic; a
Nova Pro call would only add cost / non-determinism / verdict-risk for no gain. So —
UNLIKE the 3.2 correlator + the 3.3 scorer — this Lambda has NO Bedrock client and NO
Bedrock grant. Its assessment logic is PURE stdlib (``remediate.py``); all boto3
(DynamoDB only) is in ``awsio.py``.

Trigger: the Hub tracking DynamoDB table's stream (NEW_AND_OLD_IMAGES), the SAME stream
the 3.1 normalizer + 3.2 correlator + 3.3 scorer hang off. When a ``scoring_result`` is
present, this re-reads the CURRENT item and, IF the evidence has not already been
assessed for its current content, builds the result and records it.

Design invariants (RD-009 / RD-012 / RD-013 / RD-014 / RD-039):
  * Hub-SIDE only. The inputs (the scores + findings) are already Hub-side derived
    data; this NEVER reads the Forensic raw body / findings / trace (RD-009) and NEVER
    crosses the Forensic -> Hub gate (RD-013 is untouched — the remediation result
    never leaves the Hub). No new durable store is added to the Forensic blast zone
    (RD-012).
  * EVIDENCE + a to-do, never a verdict. The remediation result has NO verdict/safe/
    approved/forward/pass_fail/malicious/clean field; the tracking ``status`` is never
    touched. A remediation is 'fix X', never 'reject the artifact'. The verdict is
    Hub-side / human-gated (Story 3.5).
  * TOLERATES A PARTIAL scoring result. A score block may be model_error / unparseable
    / skipped_no_evidence; the ranking is done honestly over whichever scores are
    present (a missing score is never fabricated).
  * NO model call (RD-039). Deterministic, reproducible; no retry loop, no Bedrock.
  * ONE assessment per settled evidence (no re-work, no stream loop). Gated on a
    FINGERPRINT of the evidence the result is built over (the scoring_result + the
    correlation findings); its own write (which changes neither) does not re-trigger
    it. The write is integrity-bound (record exists AND sha256 matches) and NEVER
    touches status.
  * PURE logic + thin seam. All assessment logic is in ``remediate.py`` (pure); all
    boto3 (DynamoDB) is in ``awsio.py``.
"""

from __future__ import annotations

import datetime as _dt
import decimal
import hashlib
import json
import logging
import os
from typing import Any

import remediate

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# --- Configuration (from environment; set by the CDK stack) -----------------

TRACKING_TABLE = os.environ.get("TRACKING_TABLE", "")
# The remediation-result record pins its OWN version (RD-039). Currently "1.0".
REMEDIATION_CONTRACT_VERSION = os.environ.get("REMEDIATION_CONTRACT_VERSION", "1.0")


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> Any:
    """Return a comparison-canonical form of ``value`` so a fingerprint computed over a
    freshly-read DynamoDB item (numbers are ``decimal.Decimal``, sets are Python
    ``set``) is stable and JSON-serializable. Mirrors the 3.1/3.2/3.3 ``_canonical``
    (the live 3.1 stream-loop lesson: a Decimal round-trip must not look different from
    the plain value). Pure."""
    if isinstance(value, bool):
        return value
    if isinstance(value, decimal.Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, (set, frozenset)):
        return sorted(_canonical(v) for v in value)
    if isinstance(value, dict):
        return {k: _canonical(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    if isinstance(value, bytes):
        return f"__bytes__:{value!r}"
    return value


def _evidence_fingerprint(
    scoring_result: Any, correlation_result: Any
) -> str:
    """A stable content hash of the evidence the remediation result is built over (the
    3.3 scoring_result + the 3.2 correlation findings), used to decide whether the
    current evidence has already been assessed. Only changes when the evidence 3.4
    reasons over changes — so re-deriving over the SAME scores + findings does NOT
    re-run the assessment (no stream loop). Pure. Decimal-canonicalized (the 3.1
    lesson: a Decimal round-trip must not look different)."""
    canonical_scoring = _canonical(scoring_result) if scoring_result is not None else None
    relevant_scoring: dict[str, Any] = {}
    if isinstance(canonical_scoring, dict):
        # The score blocks + the completeness fact are what the ranking depends on.
        # The evidence_fingerprint the 3.3 handler stamps is bookkeeping, not evidence.
        relevant_scoring = {
            "static": canonical_scoring.get("static"),
            "dynamic": canonical_scoring.get("dynamic"),
            "combined": canonical_scoring.get("combined"),
            "combined_complete": canonical_scoring.get("combined_complete"),
            "rubric_version": canonical_scoring.get("rubric_version"),
        }

    canonical_corr = (
        _canonical(correlation_result) if correlation_result is not None else None
    )
    relevant_corr: dict[str, Any] = {}
    if isinstance(canonical_corr, dict):
        correlation = canonical_corr.get("correlation")
        findings = (
            correlation.get("findings") if isinstance(correlation, dict) else None
        )
        relevant_corr = {
            "status": canonical_corr.get("status"),
            "findings": findings,
        }

    blob = json.dumps(
        {"scoring": relevant_scoring, "correlation": relevant_corr},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _already_assessed(item: dict[str, Any], fingerprint: str) -> bool:
    """True iff the tracking item already carries a remediation result for THIS
    evidence fingerprint (the re-work / stream-loop guard). Pure."""
    existing = item.get("remediation_result")
    if not isinstance(existing, dict):
        return False
    return existing.get("evidence_fingerprint") == fingerprint


def _combined_complete(scoring_result: Any) -> bool | None:
    """The combined-event completeness fact carried on the 3.3 scoring_result (drives
    the 'coverage' gap). Pure."""
    if isinstance(scoring_result, dict):
        cc = scoring_result.get("combined_complete")
        if isinstance(cc, bool):
            return cc
    return None


def _rubric_version(scoring_result: Any) -> str | None:
    if isinstance(scoring_result, dict):
        rv = scoring_result.get("rubric_version")
        if isinstance(rv, str):
            return rv
    return None


def _assess_intake(intake_id: str) -> None:
    """Re-read the current tracking item and, if its scoring result is present and not
    yet assessed for its current content, build the derived remediation result and
    record it.

    A missing item, an item without a scoring result, an already-assessed fingerprint,
    or a race on the conditional write is a benign no-op.
    """
    import awsio  # local import so tests can stub the seam before import

    item = awsio.get_item(TRACKING_TABLE, intake_id)
    if not item:
        logger.info("intake_id=%s not present; nothing to assess", intake_id)
        return
    if "sha256" not in item or "intake_id" not in item:
        logger.info("intake_id=%s missing key fields; skipping", intake_id)
        return

    scoring_result = item.get("scoring_result")
    if not isinstance(scoring_result, dict):
        logger.info(
            "intake_id=%s has no scoring_result yet; skipping (3.3 not landed)",
            intake_id,
        )
        return

    scoring_result = _canonical(scoring_result)
    correlation_result = item.get("correlation_result")
    if correlation_result is not None:
        correlation_result = _canonical(correlation_result)

    fingerprint = _evidence_fingerprint(scoring_result, correlation_result)
    if _already_assessed(item, fingerprint):
        logger.info(
            "intake_id=%s already assessed for this evidence fingerprint; no-op (guard)",
            intake_id,
        )
        return

    intake_key = item["intake_id"]
    sha256 = item["sha256"]
    assessed_at = _now_iso()

    payload = remediate.assess(
        scoring_result,
        correlation_result,
        combined_complete=_combined_complete(scoring_result),
    )
    result = remediate.build_result(
        intake_id=intake_key,
        sha256=sha256,
        assessed_at=assessed_at,
        contract_version=REMEDIATION_CONTRACT_VERSION,
        payload=payload,
        rubric_version=_rubric_version(scoring_result),
        combined_complete=_combined_complete(scoring_result),
    )
    # Stamp the fingerprint so the guard recognizes unchanged evidence on the next
    # stream event. Hub-internal bookkeeping (not part of the contract shape validated
    # in tests); written under the same integrity-bound update; no verdict.
    result["evidence_fingerprint"] = fingerprint

    try:
        awsio.put_remediation_result(
            TRACKING_TABLE,
            intake_id=intake_key,
            sha256=sha256,
            remediation_result=result,
            assessed_at=assessed_at,
        )
    except Exception as exc:  # classify then re-raise if unexpected
        if _is_conditional_check_failure(exc):
            logger.info(
                "intake_id=%s conditional write failed (race); skipping", intake_id
            )
            return
        raise
    assessment = result.get("assessment") or {}
    counts = assessment.get("counts") or {}
    logger.info(
        "intake_id=%s remediation recorded (status=%s, findings=%s, gaps=%s, remediations=%s)",
        intake_id,
        result.get("status"),
        counts.get("detailed_finding_count"),
        counts.get("gap_count"),
        counts.get("remediation_count"),
    )


def _is_conditional_check_failure(exc: Exception) -> bool:
    return exc.__class__.__name__ == "ConditionalCheckFailedException" or (
        hasattr(exc, "response")
        and getattr(exc, "response", {}).get("Error", {}).get("Code")
        == "ConditionalCheckFailedException"
    )


def _intake_ids_from_event(event: dict[str, Any]) -> list[str]:
    """Extract the distinct intake_ids whose tracking item changed from a DynamoDB
    stream event. REMOVE records are ignored. Pure enough to unit-test directly."""
    ids: list[str] = []
    for record in event.get("Records", []) or []:
        if record.get("eventName") == "REMOVE":
            continue
        ddb = record.get("dynamodb", {}) or {}
        keys = ddb.get("Keys", {}) or {}
        raw = keys.get("intake_id", {})
        intake_id = raw.get("S") if isinstance(raw, dict) else raw
        if isinstance(intake_id, str) and intake_id and intake_id not in ids:
            ids.append(intake_id)
    return ids


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """DynamoDB-Streams-triggered entry point. Returns partial-batch failures for retry
    so a transient error on one item does not reprocess the whole batch."""
    if not TRACKING_TABLE:
        logger.error("Misconfigured: TRACKING_TABLE not set")
        raise RuntimeError("Hub findings + remediations step is misconfigured")

    batch_item_failures: list[dict[str, str]] = []
    records = event.get("Records", []) or []

    seen: set[str] = set()
    for record in records:
        if record.get("eventName") == "REMOVE":
            continue
        ddb = record.get("dynamodb", {}) or {}
        keys = ddb.get("Keys", {}) or {}
        raw = keys.get("intake_id", {})
        intake_id = raw.get("S") if isinstance(raw, dict) else raw
        seq = ddb.get("SequenceNumber") or record.get("eventID") or ""
        if not (isinstance(intake_id, str) and intake_id) or intake_id in seen:
            continue
        seen.add(intake_id)
        try:
            _assess_intake(intake_id)
        except Exception:
            logger.exception("failed to assess intake_id=%s (will retry)", intake_id)
            if seq:
                batch_item_failures.append({"itemIdentifier": seq})

    return {"batchItemFailures": batch_item_failures}
