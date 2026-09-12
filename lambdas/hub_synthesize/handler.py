"""ZTIE Story 3.3 (RD-038) — Hub-side three-score risk scorer Lambda.

The risk-scoring step of Phase 3. For one intake it reads the ONE normalized
combined-event record (Story 3.1, RD-033) ALREADY on the Hub tracking item and makes
THREE SEPARATE, evidence-scoped Amazon Nova Pro calls (RD-003) to produce THREE
INDEPENDENT 0-100 risk scores — a STATIC score (over ONLY the static lane's derived
evidence), a DYNAMIC score (over ONLY the dynamic lane's derived evidence), and a
COMBINED score (over BOTH lanes' derived evidence together, its own assessment, NOT a
formula over the two). All three share ONE 0-100 rubric so they are comparable
(higher = riskier). It records a bounded, DERIVED, verdict-free scoring RESULT
(``scoring.contract.v1``) back onto the SAME item — with real exponential-backoff
retry per call.

This SUPERSEDES the RD-037 build (which produced an `accuracy`/`gap_analysis`
`synthesis_result` with NO model call). RD-038 re-adds the Nova Pro calls + the scoped
Bedrock grant; the list-shaped synthesis content migrated to Story 3.4.

Trigger: the Hub tracking DynamoDB table's stream (NEW_AND_OLD_IMAGES), the SAME
stream the 3.1 normalizer + 3.2 correlator hang off. When a ``combined_event`` is
present, this re-reads the CURRENT item and, IF the evidence has not already been
scored for its current content, makes the (up to) three calls and records the result.

Design invariants (RD-009 / RD-012 / RD-013 / RD-014 / RD-038):
  * Hub-SIDE only. The input (the combined event) is already Hub-side derived data;
    this NEVER reads the Forensic raw body / findings / trace (RD-009) and NEVER
    crosses the Forensic -> Hub gate (RD-013 is untouched — the scoring result never
    leaves the Hub). No new durable store is added to the Forensic blast zone
    (RD-012).
  * EVIDENCE, never a verdict. The scoring result has NO verdict/safe/approved/
    forward/pass_fail/malicious/clean field; the tracking ``status`` is never touched.
    Each prompt asks for a RISK SCORE only. A risk score is EVIDENCE (higher =
    riskier), never a decision. The verdict is Hub-side / human-gated (Story 3.5).
  * THREE INDEPENDENT, EVIDENCE-SCOPED CALLS + PARTIAL RESULTS. Each score has its own
    honest ``status`` (scored / model_error / unparseable / skipped_no_evidence): a
    failing/absent call does not sink the other two — the record is honest about which
    scores it has.
  * REAL model calls + inspectable exponential-backoff retry (RD-003). No mock model.
    A malformed / absent / throttled response is RECORDED via that score's status,
    NEVER fabricated.
  * ONE scoring per settled evidence (no call storm, no stream loop). Gated on a
    FINGERPRINT of the evidence the scores are built over; its own write (which does
    not change the combined event) does not re-trigger the calls. The write is
    integrity-bound (record exists AND sha256 matches) and NEVER touches status.
  * PURE logic + thin seam. All prompt-building + response-parsing is in ``score.py``
    (pure); all boto3 (Bedrock + DynamoDB) is in ``awsio.py``.

No mocks in the execution path: real Bedrock + real DynamoDB via boto3.
"""

from __future__ import annotations

import datetime as _dt
import decimal
import hashlib
import json
import logging
import os
from typing import Any

import score

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# --- Configuration (from environment; set by the CDK stack) -----------------

TRACKING_TABLE = os.environ.get("TRACKING_TABLE", "")
# The scoring-result record pins its OWN version (RD-038). Currently "1.0".
SCORING_CONTRACT_VERSION = os.environ.get("SCORING_CONTRACT_VERSION", "1.0")
# The Bedrock model id / inference-profile id for Amazon Nova Pro (RD-003).
NOVA_MODEL_ID = os.environ.get("NOVA_MODEL_ID", "us.amazon.nova-pro-v1:0")
# Bounded retry budget for the exponential-backoff loop (RD-003), per call.
NOVA_MAX_ATTEMPTS = int(os.environ.get("NOVA_MAX_ATTEMPTS", "5"))
# Only score once the combined event is COMPLETE (all inputs landed) by default, so
# we do not spend three Nova Pro calls on every partial re-derive. Set to "0" to
# score as soon as there is any evidence (a missing lane scores skipped_no_evidence).
SCORE_ONLY_WHEN_COMPLETE = os.environ.get("SCORE_ONLY_WHEN_COMPLETE", "1") != "0"


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> Any:
    """Return a comparison-canonical form of ``value`` so a fingerprint computed over a
    freshly-read DynamoDB item (numbers are ``decimal.Decimal``, sets are Python
    ``set``) is stable and JSON-serializable. Mirrors the 3.1/3.2 ``_canonical`` (the
    live 3.1 stream-loop lesson: a Decimal round-trip must not look different from the
    plain value). Pure."""
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


def _evidence_fingerprint(combined_event: Any) -> str:
    """A stable content hash of the evidence the three scores are built over (the
    signals + presence facts), used to decide whether the current evidence has already
    been scored. Only changes when the evidence Nova Pro would score changes — so
    re-deriving the SAME combined event does NOT trigger three fresh (costly) model
    calls. Pure. (Same relevant fields as the 3.2 correlator's fingerprint.)"""
    canonical = _canonical(combined_event) if combined_event is not None else None
    relevant: dict[str, Any] = {}
    if isinstance(canonical, dict):
        relevant = {
            "inputs_present": canonical.get("inputs_present"),
            "complete": canonical.get("complete"),
            "signals": canonical.get("signals"),
            "sources": canonical.get("sources"),
        }
    blob = json.dumps(relevant, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _already_scored(item: dict[str, Any], fingerprint: str) -> bool:
    """True iff the tracking item already carries a scoring result for THIS evidence
    fingerprint (the call-storm / stream-loop guard). Pure."""
    existing = item.get("scoring_result")
    if not isinstance(existing, dict):
        return False
    return existing.get("evidence_fingerprint") == fingerprint


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, decimal.Decimal):
        return int(value)
    if isinstance(value, float):
        return int(value)
    return None


def _score_one(kind: str, evidence: dict[str, Any], awsio) -> dict[str, Any]:
    """Make ONE scoped Nova Pro call and return its bounded score block. Fault-isolated:
    a model failure / unparseable response is RECORDED via the block's status, never
    raised out of here (so one score failing does not sink the others). Pure-ish (I/O
    via the injected ``awsio`` seam)."""
    body = score.build_invoke_body(kind, evidence)
    try:
        response_body, attempts, latency_ms = awsio.invoke_nova(
            model_id=NOVA_MODEL_ID, body=body, max_attempts=NOVA_MAX_ATTEMPTS
        )
    except Exception as exc:  # noqa: BLE001  record honestly, never fabricate
        logger.warning("%s score: Nova invocation failed: %s", kind, exc)
        return score.build_score_block(
            status=score.STATUS_MODEL_ERROR,
            status_detail=f"{exc.__class__.__name__}",
            model_id=NOVA_MODEL_ID,
        )
    input_tokens = output_tokens = None
    usage = response_body.get("usage") if isinstance(response_body, dict) else None
    if isinstance(usage, dict):
        input_tokens = _as_int(usage.get("inputTokens"))
        output_tokens = _as_int(usage.get("outputTokens"))
    text = score.extract_text(response_body)
    value, rationale = score.parse_score(text)
    if value is None:
        return score.build_score_block(
            status=score.STATUS_UNPARSEABLE,
            status_detail="model response had no parseable 0-100 score",
            model_id=NOVA_MODEL_ID,
            attempts=attempts,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
    return score.build_score_block(
        status=score.STATUS_SCORED,
        score=value,
        rationale=rationale,
        model_id=NOVA_MODEL_ID,
        attempts=attempts,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def _skipped_block(reason: str) -> dict[str, Any]:
    return score.build_score_block(
        status=score.STATUS_SKIPPED_NO_EVIDENCE, status_detail=reason
    )


def _score_intake(intake_id: str) -> None:
    """Re-read the current tracking item and, if its combined event is ready and not
    yet scored for its current content, make the three scoped Nova Pro calls and record
    the bounded, verdict-free scoring result.

    A missing item, an item without a combined event, an already-scored fingerprint, or
    a race on the conditional write is a benign no-op.
    """
    import awsio  # local import so tests can stub the seam before import

    item = awsio.get_item(TRACKING_TABLE, intake_id)
    if not item:
        logger.info("intake_id=%s not present; nothing to score", intake_id)
        return
    if "sha256" not in item or "intake_id" not in item:
        logger.info("intake_id=%s missing key fields; skipping", intake_id)
        return

    combined_event = item.get("combined_event")
    if not isinstance(combined_event, dict):
        logger.info(
            "intake_id=%s has no combined_event yet; skipping (3.1 not landed)",
            intake_id,
        )
        return

    combined_event = _canonical(combined_event)
    fingerprint = _evidence_fingerprint(combined_event)

    if _already_scored(item, fingerprint):
        logger.info(
            "intake_id=%s already scored for this evidence fingerprint; no-op (guard)",
            intake_id,
        )
        return

    complete = bool(combined_event.get("complete"))
    has_static = score.has_static_evidence(combined_event)
    has_dynamic = score.has_dynamic_evidence(combined_event)

    if not (has_static or has_dynamic):
        logger.info("intake_id=%s no lane evidence to score yet; skip", intake_id)
        return
    if SCORE_ONLY_WHEN_COMPLETE and not complete:
        logger.info(
            "intake_id=%s combined event not complete yet; deferring scoring", intake_id
        )
        return

    intake_key = item["intake_id"]
    sha256 = item["sha256"]
    scored_at = _now_iso()

    # --- Three independent, evidence-scoped Nova Pro calls (RD-038) -----------
    if has_static:
        static_block = _score_one("static", score.static_evidence(combined_event), awsio)
    else:
        static_block = _skipped_block("no static lane evidence present")

    if has_dynamic:
        dynamic_block = _score_one(
            "dynamic", score.dynamic_evidence(combined_event), awsio
        )
    else:
        dynamic_block = _skipped_block("no dynamic lane evidence present")

    # The combined call sees BOTH lanes' derived evidence together. It runs whenever
    # there is ANY lane evidence (its view honestly reflects an absent lane).
    combined_block = _score_one(
        "combined", score.combined_evidence(combined_event), awsio
    )

    result = score.build_result(
        intake_id=intake_key,
        sha256=sha256,
        scored_at=scored_at,
        contract_version=SCORING_CONTRACT_VERSION,
        static_block=static_block,
        dynamic_block=dynamic_block,
        combined_block=combined_block,
        combined_complete=complete,
    )
    # Stamp the fingerprint so the call-storm guard recognizes unchanged evidence on
    # the next stream event. Hub-internal bookkeeping (not part of the contract shape
    # validated in tests); written under the same integrity-bound update; no verdict.
    result["evidence_fingerprint"] = fingerprint

    try:
        awsio.put_scoring_result(
            TRACKING_TABLE,
            intake_id=intake_key,
            sha256=sha256,
            scoring_result=result,
            scored_at=scored_at,
        )
    except Exception as exc:  # classify then re-raise if unexpected
        if _is_conditional_check_failure(exc):
            logger.info(
                "intake_id=%s conditional write failed (race); skipping", intake_id
            )
            return
        raise
    logger.info(
        "intake_id=%s scoring recorded (static=%s/%s, dynamic=%s/%s, combined=%s/%s)",
        intake_id,
        static_block.get("status"),
        static_block.get("score"),
        dynamic_block.get("status"),
        dynamic_block.get("score"),
        combined_block.get("status"),
        combined_block.get("score"),
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
        raise RuntimeError("Hub three-score risk scorer is misconfigured")

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
            _score_intake(intake_id)
        except Exception:
            logger.exception("failed to score intake_id=%s (will retry)", intake_id)
            if seq:
                batch_item_failures.append({"itemIdentifier": seq})

    return {"batchItemFailures": batch_item_failures}
