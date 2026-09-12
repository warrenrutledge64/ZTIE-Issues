"""ZTIE Story 3.1 — Hub-side combined-event normalizer Lambda (RD-033).

The FIRST Phase-3 (Correlation & Synthesis) component. It NORMALIZES the three
per-lane derived outputs ALREADY on the Hub tracking record — the static-scan
summary (``static_scan``, 2.1/2.2), the dynamic-run outcome (``dynamic_run``, 2.3)
and the sanitized behavioral telemetry (``sanitized``, 2.5) — into ONE shared,
bounded, verdict-free COMBINED-EVENT record (``combined-event.contract.v1``) that
the Phase-3 Nova Pro correlation engine (Story 3.2) reasons over, and writes it back
onto the SAME tracking item.

Trigger: the Hub tracking DynamoDB table's stream (NEW_AND_OLD_IMAGES). Every time
the ingest validator applies one of the per-lane derived inputs (or anything else)
to a tracking item, this fires, re-reads the CURRENT item, and re-derives the
combined event from whatever inputs have landed so far. This is honest about SQS
ordering: a lane that has not landed yet is RECORDED as absent, never fabricated,
and a later stream event re-derives once it lands.

Design invariants (RD-009 / RD-012 / RD-013 / RD-014):
  * Hub-SIDE only. All inputs are already Hub-side derived data; this NEVER reads
    the Forensic raw body / findings / trace (RD-009) and NEVER crosses the
    Forensic -> Hub gate (RD-013 is untouched — the combined event never leaves the
    Hub). No new durable store is added to the Forensic blast zone (RD-012).
  * EVIDENCE, never a verdict. The combined event has NO verdict/safe/approved/
    forward/pass_fail/malicious/clean field; ``status`` is never touched. The
    verdict is Hub-side / human-gated (Phase 4), downstream of this.
  * IDEMPOTENT / no stream loop. Writing the combined event itself produces another
    stream event; to avoid an infinite loop, this only writes when the freshly
    derived combined event DIFFERS from the one already on the item (a re-derive
    that produces the identical record is a no-op). The write is integrity-bound
    (record exists AND sha256 matches) and NEVER touches status.
  * PURE logic + thin seam. All normalization is in ``combine.py`` (pure, offline-
    testable); all boto3 is in ``awsio.py``.

No mocks in the execution path: real DynamoDB via boto3. ``moto`` is used only in
unit tests. This Lambda has NO access to the Forensic account.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import os
from typing import Any

from combine import combine

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# --- Configuration (from environment; set by the CDK stack) -----------------

TRACKING_TABLE = os.environ.get("TRACKING_TABLE", "")
# The combined-event record pins its OWN version so it evolves independently of the
# shared CONTRACT_VERSION and every crossing kind's pin (the per-kind pin
# discipline). Currently "1.0".
COMBINED_EVENT_CONTRACT_VERSION = os.environ.get(
    "COMBINED_EVENT_CONTRACT_VERSION", "1.0"
)

# The derived-input fields on the tracking item this normalizer reads. A change to
# any of these (or the item first appearing) is what should trigger a re-derive.
_INPUT_FIELDS = ("static_scan", "dynamic_run", "sanitized")


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _combined_event_equal(a: Any, b: Any) -> bool:
    """Deep, order-insensitive equality of two combined_event objects (ignoring the
    wall-clock ``combined_at``, which is not part of the derived content). Used to
    make the stream handler idempotent so its own write does not loop."""
    return json.dumps(a, sort_keys=True, default=str) == json.dumps(
        b, sort_keys=True, default=str
    )


def _normalize_intake(intake_id: str) -> None:
    """Re-read the current tracking item and (re)derive the combined event.

    Imported lazily-bound via the awsio seam so unit tests can stub it. Writes only
    when the derived combined event differs from the one already on the item
    (idempotent — no stream loop). A missing item, an item without sha256, or a
    race on the conditional write is a benign no-op.
    """
    import awsio  # local import so tests can stub the seam before import

    item = awsio.get_item(TRACKING_TABLE, intake_id)
    if not item:
        logger.info("intake_id=%s not present; nothing to normalize", intake_id)
        return
    if "sha256" not in item or "intake_id" not in item:
        logger.info("intake_id=%s missing key fields; skipping", intake_id)
        return

    envelope = combine(
        item=item,
        combined_at=_now_iso(),
        contract_version=COMBINED_EVENT_CONTRACT_VERSION,
    )
    new_combined = envelope["combined_event"]

    existing = item.get("combined_event")
    if existing is not None and _combined_event_equal(existing, new_combined):
        logger.info(
            "intake_id=%s combined event unchanged; no write (idempotent)", intake_id
        )
        return

    try:
        awsio.put_combined_event(
            TRACKING_TABLE,
            intake_id=item["intake_id"],
            sha256=item["sha256"],
            combined_event=new_combined,
            combined_at=envelope["combined_at"],
            complete=bool(new_combined.get("complete")),
        )
    except Exception as exc:  # classify then re-raise if unexpected
        if _is_conditional_check_failure(exc):
            # The item vanished or its sha256 changed between read and write. Benign
            # — a later stream event re-derives. Do NOT retry (nothing to fix).
            logger.info(
                "intake_id=%s conditional write failed (race); skipping", intake_id
            )
            return
        raise
    logger.info(
        "intake_id=%s combined event written (inputs_present=%s, complete=%s)",
        intake_id,
        new_combined.get("inputs_present"),
        new_combined.get("complete"),
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
    are ignored (nothing to normalize). Pure enough to unit-test directly."""
    ids: list[str] = []
    for record in event.get("Records", []) or []:
        if record.get("eventName") == "REMOVE":
            continue
        ddb = record.get("dynamodb", {}) or {}
        keys = ddb.get("Keys", {}) or {}
        raw = keys.get("intake_id", {})
        # DynamoDB stream key is in AttributeValue form ({"S": "..."}); tolerate a
        # plain string too (unit tests / deserialized events).
        intake_id = raw.get("S") if isinstance(raw, dict) else raw
        if isinstance(intake_id, str) and intake_id and intake_id not in ids:
            ids.append(intake_id)
    return ids


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """DynamoDB-Streams-triggered entry point. Returns partial-batch failures for
    retry so a transient error on one item does not reprocess the whole batch."""
    if not TRACKING_TABLE:
        logger.error("Misconfigured: TRACKING_TABLE not set")
        raise RuntimeError("Hub combined-event normalizer is misconfigured")

    batch_item_failures: list[dict[str, str]] = []
    records = event.get("Records", []) or []

    # Normalize each distinct changed intake once per batch (dedupe within the
    # batch so multiple MODIFYs on the same item do one re-derive).
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
            _normalize_intake(intake_id)
        except Exception:
            logger.exception(
                "failed to normalize intake_id=%s (will retry)", intake_id
            )
            if seq:
                batch_item_failures.append({"itemIdentifier": seq})

    return {"batchItemFailures": batch_item_failures}
