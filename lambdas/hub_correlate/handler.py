"""ZTIE Story 3.2 — Hub-side Nova Pro correlation engine Lambda (RD-035).

The AI-correlation core of Phase 3 (Correlation & Synthesis). For one intake it
hands the ONE normalized combined-event record (Story 3.1, RD-033) ALREADY on the
Hub tracking item to Amazon Nova Pro (RD-003), correlates the static
misconfigurations with the dynamic behavioral indicators, and records a bounded,
DERIVED, verdict-free correlation RESULT (``correlation.contract.v1``) back onto the
SAME tracking item — with real exponential-backoff retry on Bedrock throttling/5xx.

Trigger: the Hub tracking DynamoDB table's stream (NEW_AND_OLD_IMAGES), the SAME
stream the 3.1 normalizer hangs off. Every time the normalizer writes/updates the
``combined_event`` (or any other item mutation fires), this re-reads the CURRENT
item and, IF the combined event is ready to correlate AND has not already been
correlated for its current content, invokes Nova Pro once and records the result.

Design invariants (RD-009 / RD-012 / RD-013 / RD-014):
  * Hub-SIDE only. The input (the combined event) is already Hub-side derived data;
    this NEVER reads the Forensic raw body / findings / trace (RD-009) and NEVER
    crosses the Forensic -> Hub gate (RD-013 is untouched — the correlation result
    never leaves the Hub). No new durable store is added to the Forensic blast zone
    (RD-012).
  * EVIDENCE, never a verdict. The correlation result has NO verdict/safe/approved/
    forward/pass_fail/malicious/clean field; ``status`` is never touched. The prompt
    never asks the model for a verdict; a verdict-shaped key in the model response is
    dropped by the allow-list parse. The verdict is Hub-side / human-gated (Phase 4).
  * REAL model call + inspectable exponential-backoff retry (RD-003). No mock model.
    A malformed / absent / throttled model response is RECORDED honestly via
    ``status`` (model_error / unparseable), NEVER fabricated.
  * ONE invocation per settled combined event (no call storm, no stream loop). The
    normalizer's own writes fire the stream; to avoid re-correlating on every
    mutation, this gates the Nova Pro call on a FINGERPRINT of the correlatable
    content — it correlates only when the combined event is ready AND its fingerprint
    differs from the fingerprint recorded on the last correlation result. Its own
    write (which does not change the combined event) therefore does not re-trigger a
    call. The write is integrity-bound (record exists AND sha256 matches) and NEVER
    touches status.
  * PURE logic + thin seam. All prompt-building + response-parsing is in
    ``correlate.py`` (pure, offline-testable); all boto3 (Bedrock + DynamoDB) is in
    ``awsio.py``.

No mocks in the execution path: real Bedrock + real DynamoDB via boto3. This Lambda
has NO access to the Forensic account.
"""

from __future__ import annotations

import datetime as _dt
import decimal
import hashlib
import json
import logging
import os
from typing import Any

import correlate

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# --- Configuration (from environment; set by the CDK stack) -----------------

TRACKING_TABLE = os.environ.get("TRACKING_TABLE", "")
# The correlation-result record pins its OWN version so it evolves independently of
# the shared CONTRACT_VERSION and every crossing kind's pin. Currently "1.0".
CORRELATION_CONTRACT_VERSION = os.environ.get("CORRELATION_CONTRACT_VERSION", "1.0")
# The Bedrock model id / inference-profile id for Amazon Nova Pro (RD-003). Nova Pro
# on-demand is reached through a region-prefixed cross-region inference profile
# (e.g. us.amazon.nova-pro-v1:0); overridable via env so the stack pins the exact id
# and a different region/profile can be set without a code change.
NOVA_MODEL_ID = os.environ.get("NOVA_MODEL_ID", "us.amazon.nova-pro-v1:0")
# Bounded retry budget for the exponential-backoff loop (RD-003), overridable.
NOVA_MAX_ATTEMPTS = int(os.environ.get("NOVA_MAX_ATTEMPTS", "5"))
# Only correlate once the combined event is COMPLETE (all three inputs landed) by
# default, so we do not spend a Nova Pro call on every partial re-derive. Set to
# "0" to correlate as soon as there are any correlatable signals.
CORRELATE_ONLY_WHEN_COMPLETE = os.environ.get("CORRELATE_ONLY_WHEN_COMPLETE", "1") != "0"


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> Any:
    """Return a comparison-canonical form of ``value`` so a fingerprint computed over
    a freshly-read DynamoDB item (numbers are ``decimal.Decimal``, sets are Python
    ``set``) is stable and JSON-serializable. Mirrors hub_normalize's ``_canonical``
    (the live 3.1 stream-loop lesson: a Decimal round-trip must not look different
    from the plain value). Pure."""
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


def _combined_event_fingerprint(combined_event: Any) -> str:
    """A stable content hash of the correlatable substance of the combined event
    (its signals + presence facts), used to decide whether the current combined
    event has already been correlated. Ignoring wall-clock noise, this only changes
    when the evidence Nova Pro would correlate changes — so re-deriving the SAME
    combined event does NOT trigger a fresh (costly) model call. Pure."""
    canonical = _canonical(combined_event) if combined_event is not None else None
    relevant = {}
    if isinstance(canonical, dict):
        relevant = {
            "inputs_present": canonical.get("inputs_present"),
            "complete": canonical.get("complete"),
            "signals": canonical.get("signals"),
            "sources": canonical.get("sources"),
        }
    blob = json.dumps(relevant, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _already_correlated(item: dict[str, Any], fingerprint: str) -> bool:
    """True iff the tracking item already carries a correlation result for THIS
    combined-event fingerprint (so we do not re-invoke the model for unchanged
    content — the call-storm / stream-loop guard). Pure."""
    existing = item.get("correlation_result")
    if not isinstance(existing, dict):
        return False
    return existing.get("combined_event_fingerprint") == fingerprint


def _correlate_intake(intake_id: str) -> None:
    """Re-read the current tracking item and, if its combined event is ready and not
    yet correlated for its current content, invoke Nova Pro once and record the
    bounded, verdict-free correlation result.

    Imported lazily-bound via the awsio seam so unit tests can stub it. A missing
    item, an item without a combined event, an already-correlated fingerprint, or a
    race on the conditional write is a benign no-op. A model failure / unparseable
    response is RECORDED honestly (never fabricated).
    """
    import awsio  # local import so tests can stub the seam before import

    item = awsio.get_item(TRACKING_TABLE, intake_id)
    if not item:
        logger.info("intake_id=%s not present; nothing to correlate", intake_id)
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
    fingerprint = _combined_event_fingerprint(combined_event)

    if _already_correlated(item, fingerprint):
        logger.info(
            "intake_id=%s already correlated for this combined-event fingerprint; "
            "no-op (guard)",
            intake_id,
        )
        return

    complete = bool(combined_event.get("complete"))
    # The combined-event contract version lives at the tracking item's top level
    # (written alongside combined_event by 3.1); best-effort carry-through.
    combined_cv = None
    if isinstance(item.get("combined_event_contract_version"), str):
        combined_cv = item["combined_event_contract_version"]

    # Gate: honor CORRELATE_ONLY_WHEN_COMPLETE, but always require SOMETHING to
    # correlate. An empty / no-signals combined event is honestly skipped.
    if not correlate.has_correlatable_signals(combined_event):
        logger.info("intake_id=%s combined event has no correlatable signals; skip",
                    intake_id)
        return
    if CORRELATE_ONLY_WHEN_COMPLETE and not complete:
        logger.info(
            "intake_id=%s combined event not complete yet; deferring correlation "
            "(re-derives when the remaining inputs land)",
            intake_id,
        )
        return

    intake_key = item["intake_id"]
    sha256 = item["sha256"]
    correlated_at = _now_iso()

    # --- Real Nova Pro invocation with exponential-backoff retry (RD-003) -----
    body = correlate.build_invoke_body(combined_event)
    status = correlate.STATUS_CORRELATED
    status_detail = None
    attempts = 0
    latency_ms = None
    input_tokens = output_tokens = None
    correlation = None
    truncated = False

    try:
        response_body, attempts, latency_ms = awsio.invoke_nova(
            model_id=NOVA_MODEL_ID, body=body, max_attempts=NOVA_MAX_ATTEMPTS
        )
        usage = response_body.get("usage") if isinstance(response_body, dict) else None
        if isinstance(usage, dict):
            input_tokens = _as_int(usage.get("inputTokens"))
            output_tokens = _as_int(usage.get("outputTokens"))
        text = correlate.extract_text(response_body)
        correlation, truncated = correlate.parse_correlation(text)
        if correlation is None:
            status = correlate.STATUS_UNPARSEABLE
            status_detail = "model response could not be parsed into the contract"
            logger.warning("intake_id=%s Nova response unparseable", intake_id)
    except Exception as exc:  # noqa: BLE001  record honestly, never fabricate
        status = correlate.STATUS_MODEL_ERROR
        status_detail = f"{exc.__class__.__name__} after {attempts} attempt(s)"
        logger.warning(
            "intake_id=%s Nova invocation failed after %d attempt(s): %s",
            intake_id,
            attempts,
            exc,
        )

    result = correlate.build_result(
        intake_id=intake_key,
        sha256=sha256,
        correlated_at=correlated_at,
        contract_version=CORRELATION_CONTRACT_VERSION,
        status=status,
        model_id=NOVA_MODEL_ID,
        attempts=attempts,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        truncated=truncated,
        combined_complete=complete,
        combined_event_contract_version=combined_cv,
        status_detail=status_detail,
        correlation=correlation,
    )
    # Stamp the fingerprint so the call-storm guard can recognize an unchanged
    # combined event on the next stream event. This is a Hub-internal bookkeeping
    # field on the STORED record (not part of the crossing contract); it is written
    # under the same integrity-bound update and carries no verdict.
    result["combined_event_fingerprint"] = fingerprint

    try:
        awsio.put_correlation_result(
            TRACKING_TABLE,
            intake_id=intake_key,
            sha256=sha256,
            correlation_result=result,
            correlated_at=correlated_at,
            status=status,
        )
    except Exception as exc:  # classify then re-raise if unexpected
        if _is_conditional_check_failure(exc):
            logger.info(
                "intake_id=%s conditional write failed (race); skipping", intake_id
            )
            return
        raise
    logger.info(
        "intake_id=%s correlation recorded (status=%s, attempts=%s, findings=%s)",
        intake_id,
        status,
        attempts,
        (correlation or {}).get("finding_count") if correlation else 0,
    )


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


def _is_conditional_check_failure(exc: Exception) -> bool:
    return exc.__class__.__name__ == "ConditionalCheckFailedException" or (
        hasattr(exc, "response")
        and getattr(exc, "response", {}).get("Error", {}).get("Code")
        == "ConditionalCheckFailedException"
    )


def _intake_ids_from_event(event: dict[str, Any]) -> list[str]:
    """Extract the distinct intake_ids whose tracking item changed from a DynamoDB
    stream event. INSERT / MODIFY records carry the new image's key; REMOVE records
    are ignored (nothing to correlate). Pure enough to unit-test directly."""
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
        raise RuntimeError("Hub Nova Pro correlator is misconfigured")

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
            _correlate_intake(intake_id)
        except Exception:
            logger.exception(
                "failed to correlate intake_id=%s (will retry)", intake_id
            )
            if seq:
                batch_item_failures.append({"itemIdentifier": seq})

    return {"batchItemFailures": batch_item_failures}
