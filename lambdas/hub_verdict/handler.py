"""ZTIE Story 3.5 (RD-040) — Hub-side advisory recommended-verdict Lambda.

The verdict step of Phase 3 (and the FIRST verdict-bearing record). For one intake it
reads the Story 3.3 (RD-038) ``scoring_result`` (three independent 0-100 Nova Pro risk
scores: static / dynamic / combined) AND the Story 3.4 (RD-039) ``remediation_result``
(findings + gaps) ALREADY on the Hub tracking item and produces a bounded, DERIVED,
ADVISORY ``verdict_result`` (``verdict.contract.v1``): a ``recommended_verdict`` in
{PASS, FAIL, INCONCLUSIVE} + a ``recommendation_basis`` + an explicit
``human_decision: pending`` marker. It records the result back onto the SAME item under
its OWN new fields (``verdict_result`` + ``verdict_at``).

RD-040 CONTRACT-FIRST decision: this is PURE Hub-side post-processing — it makes NO
model call. The inputs are already fully structured (three 0-100 scores + categorized
findings/gaps), so the PASS/FAIL/INCONCLUSIVE mapping is deterministic + reproducible +
auditable; a Nova Pro call would only add cost / non-determinism and would undercut "the
model characterizes, the rules/human decide". So — like the 3.4 remediation step and
UNLIKE the 3.2 correlator + the 3.3 scorer — this Lambda has NO Bedrock client and NO
Bedrock grant. Its logic is PURE stdlib (``verdict.py``); all boto3 (DynamoDB only) is in
``awsio.py``.

CRUCIAL (RD-040): the recommended_verdict is ADVISORY and is NEVER acted upon. Nothing in
ZTIE routes / promotes / destroys / moves an artifact based on it. The Phase-4 routing is
driven SOLELY by a HUMAN actively selecting PASS or FAIL on the dashboard. This Lambda
writes ONLY the recommendation + ``human_decision: pending``; it NEVER writes the human's
actual selection (a separate, human-owned Phase-4 field).

Trigger: the Hub tracking DynamoDB table's stream (NEW_AND_OLD_IMAGES), the SAME stream
the 3.1 normalizer + 3.2 correlator + 3.3 scorer + 3.4 remediation step hang off. When a
``scoring_result`` is present, this re-reads the CURRENT item and, IF the evidence has
not already been recommended over for its current content, derives the recommendation and
records it.

Design invariants (RD-009 / RD-012 / RD-013 / RD-014 / RD-040):
  * Hub-SIDE only. The inputs (the scores + findings/gaps) are already Hub-side derived
    data; this NEVER reads the Forensic raw body / findings / trace (RD-009) and NEVER
    crosses the Forensic -> Hub gate (RD-013 is untouched — the verdict result never
    leaves the Hub). No new durable store is added to the Forensic blast zone (RD-012).
  * ADVISORY, never acted upon. The verdict result carries a ``recommended_verdict`` +
    ``human_decision: pending``; the tracking ``status`` is never touched, no other
    Phase-3 field is touched, and the human's selection is never written here.
  * FIRST verdict-bearing record — but ONLY its OWN new fields. It writes
    ``verdict_result`` / ``verdict_at``; it NEVER writes a verdict onto
    ``scoring_result`` / ``remediation_result`` / ``correlation_result`` /
    ``combined_event`` (those stay verdict-free, their no-verdict scans intact).
  * TOLERATES incomplete evidence -> INCONCLUSIVE. A partial scoring_result / a
    contradiction / a coverage gap / a non-assessed remediation never becomes a
    fabricated PASS or FAIL.
  * NO model call (RD-040). Deterministic, reproducible; no retry loop, no Bedrock.
  * ONE recommendation per settled evidence (no re-work, no stream loop). Gated on a
    FINGERPRINT of the evidence the verdict is derived over (the scoring_result score
    blocks + completeness + the remediation status/gaps/contradiction); its own write
    (which changes neither) does not re-trigger it. The write is integrity-bound (record
    exists AND sha256 matches) and NEVER touches status.
  * PURE logic + thin seam. All derivation logic is in ``verdict.py`` (pure); all boto3
    (DynamoDB) is in ``awsio.py``.
"""

from __future__ import annotations

import datetime as _dt
import decimal
import hashlib
import json
import logging
import os
from typing import Any

import verdict

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# --- Configuration (from environment; set by the CDK stack) -----------------

TRACKING_TABLE = os.environ.get("TRACKING_TABLE", "")
# The verdict-result record pins its OWN version (RD-040). Currently "1.0".
VERDICT_CONTRACT_VERSION = os.environ.get("VERDICT_CONTRACT_VERSION", "1.0")


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> Any:
    """Return a comparison-canonical form of ``value`` so a fingerprint computed over a
    freshly-read DynamoDB item (numbers are ``decimal.Decimal``, sets are Python
    ``set``) is stable and JSON-serializable. Mirrors the 3.1/3.2/3.3/3.4 ``_canonical``
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


def _evidence_fingerprint(scoring_result: Any, remediation_result: Any) -> str:
    """A stable content hash of the evidence the verdict is derived over (the 3.3
    scoring_result score blocks + completeness, and the 3.4 remediation status + gaps +
    contradiction signal), used to decide whether the current evidence has already been
    recommended over. Only changes when the evidence 3.5 reasons over changes — so
    re-deriving over the SAME evidence does NOT re-run (no stream loop). Pure.
    Decimal-canonicalized (the 3.1 lesson: a Decimal round-trip must not look
    different)."""
    canonical_scoring = _canonical(scoring_result) if scoring_result is not None else None
    relevant_scoring: dict[str, Any] = {}
    if isinstance(canonical_scoring, dict):
        relevant_scoring = {
            "static": canonical_scoring.get("static"),
            "dynamic": canonical_scoring.get("dynamic"),
            "combined": canonical_scoring.get("combined"),
            "combined_complete": canonical_scoring.get("combined_complete"),
            "rubric_version": canonical_scoring.get("rubric_version"),
        }

    canonical_rem = (
        _canonical(remediation_result) if remediation_result is not None else None
    )
    relevant_rem: dict[str, Any] = {}
    if isinstance(canonical_rem, dict):
        assessment = canonical_rem.get("assessment")
        gaps = assessment.get("gaps") if isinstance(assessment, dict) else None
        counts = assessment.get("counts") if isinstance(assessment, dict) else None
        relevant_rem = {
            "status": canonical_rem.get("status"),
            "combined_complete": canonical_rem.get("combined_complete"),
            "gaps": gaps,
            "contradiction": (
                counts.get("contradiction") if isinstance(counts, dict) else None
            ),
        }

    blob = json.dumps(
        {"scoring": relevant_scoring, "remediation": relevant_rem},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _already_recommended(item: dict[str, Any], fingerprint: str) -> bool:
    """True iff the tracking item already carries a verdict result for THIS evidence
    fingerprint (the re-work / stream-loop guard). Pure."""
    existing = item.get("verdict_result")
    if not isinstance(existing, dict):
        return False
    return existing.get("evidence_fingerprint") == fingerprint


def _rubric_version(scoring_result: Any) -> str | None:
    if isinstance(scoring_result, dict):
        rv = scoring_result.get("rubric_version")
        if isinstance(rv, str):
            return rv
    return None


def _recommend_intake(intake_id: str) -> None:
    """Re-read the current tracking item and, if its scoring result is present and not
    yet recommended over for its current content, derive the advisory verdict and record
    it.

    A missing item, an item without a scoring result, an already-recommended
    fingerprint, or a race on the conditional write is a benign no-op.
    """
    import awsio  # local import so tests can stub the seam before import

    item = awsio.get_item(TRACKING_TABLE, intake_id)
    if not item:
        logger.info("intake_id=%s not present; nothing to recommend", intake_id)
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
    remediation_result = item.get("remediation_result")
    if remediation_result is not None:
        remediation_result = _canonical(remediation_result)

    fingerprint = _evidence_fingerprint(scoring_result, remediation_result)
    if _already_recommended(item, fingerprint):
        logger.info(
            "intake_id=%s already recommended for this evidence fingerprint; no-op (guard)",
            intake_id,
        )
        return

    intake_key = item["intake_id"]
    sha256 = item["sha256"]
    recommended_at = _now_iso()

    payload = verdict.derive(scoring_result, remediation_result)
    result = verdict.build_result(
        intake_id=intake_key,
        sha256=sha256,
        recommended_at=recommended_at,
        contract_version=VERDICT_CONTRACT_VERSION,
        payload=payload,
        rubric_version=_rubric_version(scoring_result),
    )
    # Stamp the fingerprint so the guard recognizes unchanged evidence on the next
    # stream event. Hub-internal bookkeeping (not part of the contract shape validated
    # in tests); written under the same integrity-bound update; ADVISORY, no acted-upon
    # decision.
    result["evidence_fingerprint"] = fingerprint

    try:
        awsio.put_verdict_result(
            TRACKING_TABLE,
            intake_id=intake_key,
            sha256=sha256,
            verdict_result=result,
            recommended_at=recommended_at,
        )
    except Exception as exc:  # classify then re-raise if unexpected
        if _is_conditional_check_failure(exc):
            logger.info(
                "intake_id=%s conditional write failed (race); skipping", intake_id
            )
            return
        raise
    logger.info(
        "intake_id=%s verdict recorded (status=%s, recommended_verdict=%s, human_decision=%s)",
        intake_id,
        result.get("status"),
        result.get("recommended_verdict"),
        result.get("human_decision"),
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
        raise RuntimeError("Hub verdict step is misconfigured")

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
            _recommend_intake(intake_id)
        except Exception:
            logger.exception("failed to recommend intake_id=%s (will retry)", intake_id)
            if seq:
                batch_item_failures.append({"itemIdentifier": seq})

    return {"batchItemFailures": batch_item_failures}
