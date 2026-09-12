"""ZTIE Story 3.3 — Hub-side accuracy + gap_analysis synthesizer Lambda (RD-037).

The false-positive-elimination + gap step of Phase 3 (Correlation & Synthesis). For
one intake it reads the ONE verdict-free Nova Pro correlation result (Story 3.2,
RD-035) ALREADY on the Hub tracking item and, in PURE deterministic logic (NOT a
second model call — the semantic reasoning was already done in 3.2), (a) scores how
well the correlation ELIMINATES FALSE POSITIVES (a static_only finding the dynamic
behavior never exercised is a candidate false positive) and (b) surfaces where the
two lanes DISAGREE or leave a GAP, recording a bounded, DERIVED, verdict-free
synthesis RESULT (``synthesis.contract.v1``) back onto the SAME tracking item.

Trigger: the Hub tracking DynamoDB table's stream (NEW_AND_OLD_IMAGES), the SAME
stream the 3.1 normalizer + 3.2 correlator hang off. Every time the correlator
writes/updates the ``correlation_result`` (or any other item mutation fires), this
re-reads the CURRENT item and, IF a correlation is present AND has not already been
synthesized for its current content, synthesizes once and records the result.

Design invariants (RD-009 / RD-012 / RD-013 / RD-014 / RD-037):
  * Hub-SIDE only. The input (the correlation result) is already Hub-side derived
    data; this NEVER reads the Forensic raw body / findings / trace (RD-009) and
    NEVER crosses the Forensic -> Hub gate (RD-013 is untouched — the synthesis
    result never leaves the Hub). No new durable store is added to the Forensic
    blast zone (RD-012).
  * PURE post-processing, NO model call (RD-037). Unlike the 3.2 correlator, there
    is no Bedrock invocation and no Bedrock grant. The synthesis is deterministic +
    fully reproducible over the already-structured 3.2 findings.
  * EVIDENCE, never a verdict. The synthesis result has NO verdict/safe/approved/
    forward/pass_fail/malicious/clean field; the tracking ``status`` is never
    touched. The accuracy_score describes reconciliation, not safety. The verdict is
    Hub-side / human-gated (Phase 4).
  * HONEST. An absent / non-'correlated' upstream is RECORDED via ``status``
    (no_correlation); a correlated result with zero findings is RECORDED
    (skipped_no_findings); neither fabricates a synthesis.
  * ONE synthesis per settled correlation (no call storm, no stream loop). The
    correlator's own writes fire the stream; to avoid re-synthesizing on every
    mutation, this gates the work on a FINGERPRINT of the correlation content — it
    synthesizes only when the correlation result differs from the fingerprint
    recorded on the last synthesis result. Its own write (which does not change the
    correlation result) therefore does not re-trigger work. The write is
    integrity-bound (record exists AND sha256 matches) and NEVER touches status.
  * PURE logic + thin seam. All synthesis logic is in ``synthesize.py`` (pure,
    offline-testable); all boto3 (DynamoDB) is in ``awsio.py``.

No mocks in the execution path: real DynamoDB via boto3. This Lambda has NO access
to the Forensic account and NO Bedrock access.
"""

from __future__ import annotations

import datetime as _dt
import decimal
import hashlib
import json
import logging
import os
from typing import Any

import synthesize

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# --- Configuration (from environment; set by the CDK stack) -----------------

TRACKING_TABLE = os.environ.get("TRACKING_TABLE", "")
# The synthesis-result record pins its OWN version so it evolves independently of
# the shared CONTRACT_VERSION and every crossing kind's pin. Currently "1.0".
SYNTHESIS_CONTRACT_VERSION = os.environ.get("SYNTHESIS_CONTRACT_VERSION", "1.0")


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> Any:
    """Return a comparison-canonical form of ``value`` so a fingerprint computed
    over a freshly-read DynamoDB item (numbers are ``decimal.Decimal``, sets are
    Python ``set``) is stable and JSON-serializable. Mirrors hub_normalize /
    hub_correlate ``_canonical`` (the live 3.1 stream-loop lesson: a Decimal
    round-trip must not look different from the plain value). Pure."""
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


def _correlation_fingerprint(correlation_result: Any) -> str:
    """A stable content hash of the substance of the correlation result the
    synthesis reasons over, used to decide whether the current correlation has
    already been synthesized. Ignoring wall-clock noise, this only changes when the
    evidence the synthesis would reason over changes — so re-writing the SAME
    correlation does NOT trigger fresh work (breaks the stream loop). Pure."""
    canonical = (
        _canonical(correlation_result)
        if correlation_result is not None
        else None
    )
    relevant: dict[str, Any] = {}
    if isinstance(canonical, dict):
        relevant = {
            "status": canonical.get("status"),
            "correlation": canonical.get("correlation"),
        }
    blob = json.dumps(relevant, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _already_synthesized(item: dict[str, Any], fingerprint: str) -> bool:
    """True iff the tracking item already carries a synthesis result for THIS
    correlation fingerprint (so we do not re-synthesize unchanged content — the
    call-storm / stream-loop guard). Pure."""
    existing = item.get("synthesis_result")
    if not isinstance(existing, dict):
        return False
    return existing.get("correlation_fingerprint") == fingerprint


def _synthesize_intake(intake_id: str) -> None:
    """Re-read the current tracking item and, if its correlation result is present
    and not yet synthesized for its current content, synthesize once and record the
    bounded, verdict-free synthesis result.

    Imported lazily-bound via the awsio seam so unit tests can stub it. A missing
    item, an item without a correlation result, an already-synthesized fingerprint,
    or a race on the conditional write is a benign no-op. An absent / non-correlated
    upstream is RECORDED honestly (never fabricated).
    """
    import awsio  # local import so tests can stub the seam before import

    item = awsio.get_item(TRACKING_TABLE, intake_id)
    if not item:
        logger.info("intake_id=%s not present; nothing to synthesize", intake_id)
        return
    if "sha256" not in item or "intake_id" not in item:
        logger.info("intake_id=%s missing key fields; skipping", intake_id)
        return

    correlation_result = item.get("correlation_result")
    if not isinstance(correlation_result, dict):
        logger.info(
            "intake_id=%s has no correlation_result yet; skipping (3.2 not landed)",
            intake_id,
        )
        return

    correlation_result = _canonical(correlation_result)
    fingerprint = _correlation_fingerprint(correlation_result)

    if _already_synthesized(item, fingerprint):
        logger.info(
            "intake_id=%s already synthesized for this correlation fingerprint; "
            "no-op (guard)",
            intake_id,
        )
        return

    intake_key = item["intake_id"]
    sha256 = item["sha256"]
    synthesized_at = _now_iso()

    # Carry-through facts for traceability (best-effort; never a verdict).
    correlation_cv = None
    if isinstance(correlation_result.get("contract_version"), str):
        correlation_cv = correlation_result["contract_version"]
    combined_complete = None
    if isinstance(correlation_result.get("combined_complete"), bool):
        combined_complete = correlation_result["combined_complete"]

    # --- PURE synthesis (no model call, RD-037) -------------------------------
    payload = synthesize.synthesize(
        correlation_result, combined_complete=combined_complete
    )
    status = payload["status"]

    result = synthesize.build_result(
        intake_id=intake_key,
        sha256=sha256,
        synthesized_at=synthesized_at,
        contract_version=SYNTHESIS_CONTRACT_VERSION,
        payload=payload,
        correlation_contract_version=correlation_cv,
        combined_complete=combined_complete,
    )
    # Stamp the fingerprint so the call-storm guard can recognize an unchanged
    # correlation on the next stream event. This is a Hub-internal bookkeeping field
    # on the STORED record (not part of the contract shape validated in tests); it is
    # written under the same integrity-bound update and carries no verdict.
    result["correlation_fingerprint"] = fingerprint

    try:
        awsio.put_synthesis_result(
            TRACKING_TABLE,
            intake_id=intake_key,
            sha256=sha256,
            synthesis_result=result,
            synthesized_at=synthesized_at,
            status=status,
        )
    except Exception as exc:  # classify then re-raise if unexpected
        if _is_conditional_check_failure(exc):
            logger.info(
                "intake_id=%s conditional write failed (race); skipping", intake_id
            )
            return
        raise
    synth = payload.get("synthesis") or {}
    accuracy = synth.get("accuracy") or {}
    gaps = synth.get("gaps") or {}
    logger.info(
        "intake_id=%s synthesis recorded (status=%s, confirmed=%s, "
        "candidate_false_positives=%s, gaps=%s)",
        intake_id,
        status,
        accuracy.get("confirmed_correlation_count"),
        accuracy.get("candidate_false_positive_count"),
        gaps.get("gap_count"),
    )


def _is_conditional_check_failure(exc: Exception) -> bool:
    return exc.__class__.__name__ == "ConditionalCheckFailedException" or (
        hasattr(exc, "response")
        and getattr(exc, "response", {}).get("Error", {}).get("Code")
        == "ConditionalCheckFailedException"
    )


def _intake_ids_from_event(event: dict[str, Any]) -> list[str]:
    """Extract the distinct intake_ids whose tracking item changed from a DynamoDB
    stream event. INSERT / MODIFY records carry the new image's key; REMOVE records
    are ignored (nothing to synthesize). Pure enough to unit-test directly."""
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
    """DynamoDB-Streams-triggered entry point. Returns partial-batch failures for
    retry so a transient error on one item does not reprocess the whole batch."""
    if not TRACKING_TABLE:
        logger.error("Misconfigured: TRACKING_TABLE not set")
        raise RuntimeError("Hub accuracy + gap_analysis synthesizer is misconfigured")

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
            _synthesize_intake(intake_id)
        except Exception:
            logger.exception(
                "failed to synthesize intake_id=%s (will retry)", intake_id
            )
            if seq:
                batch_item_failures.append({"itemIdentifier": seq})

    return {"batchItemFailures": batch_item_failures}
