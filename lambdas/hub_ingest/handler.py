"""ZTIE Story 1.1R — Hub-owned validating ingestion gate (RD-013).

This Lambda is the ONLY door through which data from the Forensic blast zone may
enter the Hub's durable tracking store. It is triggered by the Hub ingest SQS
queue (the one-directional Forensic -> Hub crossing) and, for every message:

  1. Parses the SQS message body as a JSON envelope.
  2. Validates it against the enforced data contract
     (``intake-tracking.contract.v1.json``) — an allow-list schema: typed,
     length-capped, size/nesting-bounded, ``additionalProperties: false`` at every
     level, and with NO field for raw payload / executable content.
  3. **PASS** -> idempotent upsert (by ``intake_id``) into the Hub tracking
     DynamoDB table. The Hub-side ``status`` and lifecycle are authoritative here.
  4. **FAIL (fail-closed)** -> the non-conforming envelope is written to the Hub
     quarantine S3 bucket with the rejection reason and is NEVER written to the
     live tracking table.

Design invariants (RD-012 / RD-013):

- The verdict (PASS / FAIL / INCONCLUSIVE) is a Hub-side, human-gated decision. It
  is NOT part of the contract and is NEVER imported or self-asserted from crossed
  data. This handler only ever records ``status=RECEIVED`` from a valid envelope;
  it never derives or copies a verdict from the message.
- The handler never reads the raw artifact body (it lives in Forensic S3; the Hub
  cannot and must not read it). Only derived metadata is persisted.
- Fail-closed means malformed / oversized / injection-crafted / unknown-field /
  wrong-version records are quarantined, not written live — and are NOT retried
  (they will never become valid). Only genuinely *unprocessable* messages (an AWS
  error on the write path, or a failed quarantine write) are reported back as
  batch item failures so SQS retries and ultimately DLQs them.

No mocks in the execution path: real DynamoDB + S3 via boto3. ``moto`` is used
only in the unit tests.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import os
import uuid
from typing import Any

import boto3
from jsonschema import Draft7Validator

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# --- Configuration (from environment; set by the CDK stack) -----------------

TRACKING_TABLE = os.environ.get("TRACKING_TABLE", "")
QUARANTINE_BUCKET = os.environ.get("QUARANTINE_BUCKET", "")
CONTRACT_VERSION = os.environ.get("CONTRACT_VERSION", "1.0")

# The contract schemas are bundled into the Lambda asset next to this file.
_SCHEMA_FILENAME = "intake-tracking.contract.v1.json"
# Story 1.2: the derived classification LABEL contract (a second envelope kind
# that crosses the SAME one-directional Forensic -> Hub gate).
_CLASSIFICATION_SCHEMA_FILENAME = "classification.contract.v1.json"
# Story 1.3: the derived routing-DECISION contract (a third envelope kind on the
# SAME gate). A plan of which controls apply — never a verdict.
_ROUTING_SCHEMA_FILENAME = "routing.contract.v1.json"
# Story 1.4: the derived safe-reject OUTCOME contract (a fourth envelope kind).
# A terminal processing outcome — never a verdict.
_REJECT_SCHEMA_FILENAME = "reject.contract.v1.json"

# Hard cap on the raw SQS body we will even attempt to parse. The contract itself
# bounds a *valid* record; this is a coarse pre-parse guard so a hostile oversized
# body cannot force a large allocation before validation. SQS max is 256 KiB.
_MAX_ENVELOPE_BYTES = 262144

# The only lifecycle status this gate will persist from a crossed record. The
# human verdict is never in this set and is never imported.
_ALLOWED_STATUS = "RECEIVED"

# Reused across warm invocations.
_ddb_table = None
_s3_client = None
_validator: Draft7Validator | None = None
_classification_validator: Draft7Validator | None = None
_routing_validator: Draft7Validator | None = None
_reject_validator: Draft7Validator | None = None


class ContractViolation(Exception):
    """The envelope failed the data contract. Fail-closed: quarantine, never persist."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _load_schema(filename: str) -> dict[str, Any]:
    schema_path = os.path.join(os.path.dirname(__file__), filename)
    with open(schema_path, encoding="utf-8") as fh:
        return json.load(fh)


def _load_validator() -> Draft7Validator:
    global _validator
    if _validator is None:
        _validator = Draft7Validator(_load_schema(_SCHEMA_FILENAME))
    return _validator


def _load_classification_validator() -> Draft7Validator:
    global _classification_validator
    if _classification_validator is None:
        _classification_validator = Draft7Validator(
            _load_schema(_CLASSIFICATION_SCHEMA_FILENAME)
        )
    return _classification_validator


def _load_routing_validator() -> Draft7Validator:
    global _routing_validator
    if _routing_validator is None:
        _routing_validator = Draft7Validator(_load_schema(_ROUTING_SCHEMA_FILENAME))
    return _routing_validator


def _load_reject_validator() -> Draft7Validator:
    global _reject_validator
    if _reject_validator is None:
        _reject_validator = Draft7Validator(_load_schema(_REJECT_SCHEMA_FILENAME))
    return _reject_validator


def _table():
    global _ddb_table
    if _ddb_table is None:
        if not TRACKING_TABLE:
            raise RuntimeError("TRACKING_TABLE environment variable is not set")
        _ddb_table = boto3.resource("dynamodb").Table(TRACKING_TABLE)
    return _ddb_table


def _s3():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3")
    return _s3_client


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_envelope(raw_body: str | None) -> dict[str, Any]:
    """Decode the SQS body to a JSON object. Raises ContractViolation on failure."""
    if raw_body is None:
        raise ContractViolation("empty message body")
    if len(raw_body.encode("utf-8")) > _MAX_ENVELOPE_BYTES:
        raise ContractViolation(
            f"message body exceeds {_MAX_ENVELOPE_BYTES} bytes"
        )
    try:
        parsed = json.loads(raw_body)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ContractViolation(f"body is not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ContractViolation("body must be a JSON object")
    return parsed


def _validate_contract(envelope: dict[str, Any]) -> None:
    """Enforce the allow-list data contract. Raises ContractViolation on any fail."""
    validator = _load_validator()
    errors = sorted(validator.iter_errors(envelope), key=lambda e: list(e.absolute_path))
    if errors:
        # Report the first few violations; keep the reason bounded.
        detail = "; ".join(
            f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in errors[:5]
        )
        raise ContractViolation(f"schema validation failed: {detail}")

    # Belt-and-suspenders beyond the schema: pin the contract version we accept.
    if envelope.get("contract_version") != CONTRACT_VERSION:
        raise ContractViolation(
            f"unsupported contract_version "
            f"{envelope.get('contract_version')!r} (expected {CONTRACT_VERSION!r})"
        )
    # The gate persists only the allow-listed lifecycle status; the human verdict
    # is never imported. (The schema already restricts status, but assert it here
    # so a future schema loosening cannot silently let a verdict cross.)
    if envelope.get("status") != _ALLOWED_STATUS:
        raise ContractViolation(
            f"status {envelope.get('status')!r} is not importable "
            f"(only {_ALLOWED_STATUS!r} crosses; verdict is Hub-owned)"
        )


def _validate_classification_contract(envelope: dict[str, Any]) -> None:
    """Enforce the Story 1.2 classification-label contract. Fail-closed on any
    violation. Like the intake contract, this is an allow-list: no verdict, no
    route, no body field can be smuggled in — the schema has no slot for them."""
    validator = _load_classification_validator()
    errors = sorted(validator.iter_errors(envelope), key=lambda e: list(e.absolute_path))
    if errors:
        detail = "; ".join(
            f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in errors[:5]
        )
        raise ContractViolation(f"classification schema validation failed: {detail}")
    if envelope.get("contract_version") != CONTRACT_VERSION:
        raise ContractViolation(
            f"unsupported classification contract_version "
            f"{envelope.get('contract_version')!r} (expected {CONTRACT_VERSION!r})"
        )


def _apply_classification(envelope: dict[str, Any]) -> None:
    """Attach the derived classification label to the EXISTING tracking record.

    Integrity-bound: the update requires the record to already exist AND its
    stored ``sha256`` to equal the label's ``sha256`` (a label can only attach to
    the exact artifact it was computed over). A classification NEVER creates a
    record and NEVER touches ``status`` — the human verdict stays Hub-owned. If no
    matching record exists yet (SQS may deliver the label before the intake
    record), the conditional update fails and the message is retried.
    """
    classification = envelope["classification"]
    _table().update_item(
        Key={"intake_id": envelope["intake_id"]},
        UpdateExpression=(
            "SET artifact_class = :ac, classification = :c, classified_at = :ca"
        ),
        ConditionExpression="attribute_exists(intake_id) AND sha256 = :sha",
        ExpressionAttributeValues={
            ":ac": classification["artifact_class"],
            ":c": classification,
            ":ca": envelope["classified_at"],
            ":sha": envelope["sha256"],
        },
    )


def _validate_routing_contract(envelope: dict[str, Any]) -> None:
    """Enforce the Story 1.3 routing-decision contract. Fail-closed on any
    violation. Like the other contracts this is an allow-list: no verdict, no
    forward-to-PDE, no body field can be smuggled in — the schema has no slot for
    them (a routing decision is a plan of controls, never a safety verdict)."""
    validator = _load_routing_validator()
    errors = sorted(validator.iter_errors(envelope), key=lambda e: list(e.absolute_path))
    if errors:
        detail = "; ".join(
            f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in errors[:5]
        )
        raise ContractViolation(f"routing schema validation failed: {detail}")
    if envelope.get("contract_version") != CONTRACT_VERSION:
        raise ContractViolation(
            f"unsupported routing contract_version "
            f"{envelope.get('contract_version')!r} (expected {CONTRACT_VERSION!r})"
        )


def _apply_routing(envelope: dict[str, Any]) -> None:
    """Attach the derived routing decision to the EXISTING tracking record.

    Integrity-bound exactly like the classification apply: the update requires the
    record to already exist AND its stored ``sha256`` to equal the decision's
    ``sha256``. A routing decision NEVER creates a record and NEVER touches
    ``status`` — the human verdict stays Hub-owned. If no matching record exists
    yet (SQS may deliver the routing decision before the intake record), the
    conditional update fails and the message is retried.
    """
    routing = envelope["routing"]
    _table().update_item(
        Key={"intake_id": envelope["intake_id"]},
        UpdateExpression=(
            "SET routing = :r, routing_lanes = :l, routed_at = :ra"
        ),
        ConditionExpression="attribute_exists(intake_id) AND sha256 = :sha",
        ExpressionAttributeValues={
            ":r": routing,
            # A flattened, queryable copy of the lane plan (the authoritative copy
            # is inside :r). Convenient for the dashboard / a lane-scoped query.
            ":l": routing["lanes"],
            ":ra": envelope["routed_at"],
            ":sha": envelope["sha256"],
        },
    )


def _to_tracking_item(envelope: dict[str, Any]) -> dict[str, Any]:
    """Project the validated envelope into the durable tracking record.

    Only known, allow-listed fields are copied. The Hub owns ``status`` and stamps
    its own ``hub_ingested_at``; no verdict is set here.
    """
    artifact = envelope["artifact"]
    origin = envelope.get("origin", {})
    item: dict[str, Any] = {
        "intake_id": envelope["intake_id"],
        "sha256": envelope["sha256"],
        "status": _ALLOWED_STATUS,
        "received_at": envelope["received_at"],
        "size_bytes": envelope["size_bytes"],
        "filename": artifact["filename"],
        "claimed_content_type": artifact["claimed_content_type"],
        "contract_version": envelope["contract_version"],
        "hub_ingested_at": _now_iso(),
    }
    if "submitter" in artifact:
        item["submitter"] = artifact["submitter"]
    for k in ("account_id", "s3_bucket", "s3_key", "submitted_by_arn"):
        if k in origin:
            item[f"origin_{k}"] = origin[k]
    return item


def _persist(envelope: dict[str, Any]) -> None:
    """Idempotent upsert of the tracking record, keyed by intake_id.

    ``put_item`` on the same ``intake_id`` is naturally idempotent for SQS
    at-least-once redelivery. We refuse to overwrite a record that a later
    lifecycle stage may have advanced by only writing when the record is absent or
    still RECEIVED, so a redelivered RECEIVED envelope cannot clobber a verdict the
    Hub has since attached.
    """
    item = _to_tracking_item(envelope)
    _table().put_item(
        Item=item,
        # Idempotent + non-clobbering: create it, or overwrite only if it is still
        # in the RECEIVED lifecycle (i.e. no Hub-side verdict yet).
        ConditionExpression=(
            "attribute_not_exists(intake_id) OR #s = :received"
        ),
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":received": _ALLOWED_STATUS},
    )


def _quarantine(raw_body: str | None, reason: str, message_id: str) -> None:
    """Write a contract-failing record to the Hub quarantine bucket. Fail-closed."""
    if not QUARANTINE_BUCKET:
        raise RuntimeError("QUARANTINE_BUCKET environment variable is not set")
    key = f"quarantine/{_dt.datetime.now(tz=_dt.timezone.utc):%Y/%m/%d}/{message_id}.json"
    body = json.dumps(
        {
            "quarantined_at": _now_iso(),
            "reason": reason,
            "sqs_message_id": message_id,
            # Store the raw body verbatim (as a STRING) for triage. It is never
            # parsed/executed; it is inert audit material.
            "raw_body": raw_body,
        }
    ).encode("utf-8")
    _s3().put_object(
        Bucket=QUARANTINE_BUCKET,
        Key=key,
        Body=body,
        ContentType="application/json",
        ServerSideEncryption="aws:kms",
        Metadata={"quarantine-reason": reason[:1024], "sqs-message-id": message_id},
    )
    logger.warning(
        "quarantined message message_id=%s reason=%s key=%s", message_id, reason, key
    )


def _is_conditional_check_failure(exc: Exception) -> bool:
    return exc.__class__.__name__ == "ConditionalCheckFailedException" or (
        hasattr(exc, "response")
        and getattr(exc, "response", {}).get("Error", {}).get("Code")
        == "ConditionalCheckFailedException"
    )


def _is_classification_envelope(envelope: dict[str, Any]) -> bool:
    """Route by envelope KIND. The classification-update envelope carries a
    ``classification`` object; the intake-tracking envelope carries ``status``."""
    return "classification" in envelope


def _is_routing_envelope(envelope: dict[str, Any]) -> bool:
    """Route by envelope KIND. The routing-update envelope (Story 1.3) carries a
    ``routing`` object; the classification envelope carries ``classification``."""
    return "routing" in envelope


def _is_reject_envelope(envelope: dict[str, Any]) -> bool:
    """Route by envelope KIND. The safe-reject outcome envelope (Story 1.4) carries
    a ``rejection`` object."""
    return "rejection" in envelope


def _resolve_conditional_apply_failure(
    envelope: dict[str, Any], raw_body: str | None, message_id: str, kind: str
) -> bool:
    """Disambiguate a failed integrity-bound conditional update (shared by the
    classification and routing apply paths).

    The condition is ``attribute_exists(intake_id) AND sha256 = <label sha>``:
      * MISSING record  -> an ordering race (the derived update arrived before the
        intake record). Return True so the caller re-raises and SQS redelivers.
      * PRESENT record with a DIFFERENT sha256 -> an integrity violation (an update
        for the wrong artifact). Quarantine, never retry; return False.

    Returns True iff the failure is a retryable ordering race.
    """
    existing = _table().get_item(Key={"intake_id": envelope["intake_id"]}).get("Item")
    if existing is None:
        logger.info(
            "intake_id=%s not yet present for %s; retrying",
            envelope.get("intake_id"),
            kind,
        )
        return True  # retryable — SQS redelivers until the intake record lands
    _quarantine(
        raw_body,
        (
            f"{kind} sha256 {envelope.get('sha256')!r} does not match tracked "
            f"record sha256 {existing.get('sha256')!r} "
            f"(intake_id {envelope.get('intake_id')!r})"
        ),
        message_id,
    )
    return False


def _process_classification(
    envelope: dict[str, Any], raw_body: str | None, message_id: str
) -> None:
    """Fail-closed validate + integrity-bound apply of a classification label."""
    try:
        _validate_classification_contract(envelope)
    except ContractViolation as violation:
        _quarantine(raw_body, violation.reason, message_id)
        return

    try:
        _apply_classification(envelope)
    except Exception as exc:
        if _is_conditional_check_failure(exc):
            if _resolve_conditional_apply_failure(
                envelope, raw_body, message_id, "classification"
            ):
                raise  # retryable ordering race
            return  # quarantined (integrity violation)
        raise


def _process_routing(
    envelope: dict[str, Any], raw_body: str | None, message_id: str
) -> None:
    """Fail-closed validate + integrity-bound apply of a routing decision (1.3)."""
    try:
        _validate_routing_contract(envelope)
    except ContractViolation as violation:
        _quarantine(raw_body, violation.reason, message_id)
        return

    try:
        _apply_routing(envelope)
    except Exception as exc:
        if _is_conditional_check_failure(exc):
            if _resolve_conditional_apply_failure(
                envelope, raw_body, message_id, "routing"
            ):
                raise  # retryable ordering race
            return  # quarantined (integrity violation)
        raise


def _validate_reject_contract(envelope: dict[str, Any]) -> None:
    """Enforce the Story 1.4 safe-reject outcome contract. Fail-closed on any
    violation. Like the other contracts this is an allow-list: no verdict, no
    forward-to-PDE, no body field — a safe-reject is a terminal processing outcome,
    never a verdict."""
    validator = _load_reject_validator()
    errors = sorted(validator.iter_errors(envelope), key=lambda e: list(e.absolute_path))
    if errors:
        detail = "; ".join(
            f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in errors[:5]
        )
        raise ContractViolation(f"reject schema validation failed: {detail}")
    if envelope.get("contract_version") != CONTRACT_VERSION:
        raise ContractViolation(
            f"unsupported reject contract_version "
            f"{envelope.get('contract_version')!r} (expected {CONTRACT_VERSION!r})"
        )


def _apply_reject(envelope: dict[str, Any]) -> None:
    """Attach the terminal safe-reject outcome to the EXISTING tracking record.

    Integrity-bound: the update requires the record to already exist AND its
    stored ``sha256`` to equal the envelope's. A rejection NEVER creates a record
    and NEVER touches the human ``verdict`` (which is Phase 4). It sets
    ``pipeline_outcome=SAFE_REJECTED`` as a terminal processing state.
    """
    rejection = envelope["rejection"]
    _table().update_item(
        Key={"intake_id": envelope["intake_id"]},
        UpdateExpression=(
            "SET pipeline_outcome = :po, rejection = :r, rejected_at = :ra"
        ),
        ConditionExpression="attribute_exists(intake_id) AND sha256 = :sha",
        ExpressionAttributeValues={
            ":po": rejection["pipeline_outcome"],
            ":r": rejection,
            ":ra": envelope["rejected_at"],
            ":sha": envelope["sha256"],
        },
    )


def _process_reject(
    envelope: dict[str, Any], raw_body: str | None, message_id: str
) -> None:
    """Fail-closed validate + integrity-bound apply of a safe-reject outcome (1.4)."""
    try:
        _validate_reject_contract(envelope)
    except ContractViolation as violation:
        _quarantine(raw_body, violation.reason, message_id)
        return

    try:
        _apply_reject(envelope)
    except Exception as exc:
        if _is_conditional_check_failure(exc):
            if _resolve_conditional_apply_failure(
                envelope, raw_body, message_id, "rejection"
            ):
                raise  # retryable ordering race
            return  # quarantined (integrity violation)
        raise


def _process_record(record: dict[str, Any]) -> None:
    """Process one SQS record. Contract failures quarantine (no raise); only
    genuinely unprocessable conditions raise (so the message retries/DLQs)."""
    message_id = record.get("messageId") or str(uuid.uuid4())
    raw_body = record.get("body")
    try:
        envelope = _parse_envelope(raw_body)
    except ContractViolation as violation:
        _quarantine(raw_body, violation.reason, message_id)
        return

    # Route by envelope kind: reject vs routing vs classification vs
    # intake-tracking. Each carries a distinct discriminator key.
    if _is_reject_envelope(envelope):
        _process_reject(envelope, raw_body, message_id)
        return
    if _is_routing_envelope(envelope):
        _process_routing(envelope, raw_body, message_id)
        return
    if _is_classification_envelope(envelope):
        _process_classification(envelope, raw_body, message_id)
        return

    try:
        _validate_contract(envelope)
    except ContractViolation as violation:
        # Fail-closed: quarantine and move on. Do NOT retry — it will never pass.
        # If the quarantine WRITE itself fails, that IS unprocessable -> re-raise.
        _quarantine(raw_body, violation.reason, message_id)
        return

    # Valid envelope -> durable upsert. A conditional-check failure means the
    # record already exists with a Hub-side verdict; that is success (idempotent),
    # not an error.
    try:
        _persist(envelope)
    except Exception as exc:
        if _is_conditional_check_failure(exc):
            logger.info(
                "intake_id=%s already advanced past RECEIVED; skipping (idempotent)",
                envelope.get("intake_id"),
            )
            return
        raise


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """SQS-triggered entry point. Returns partial-batch failures for retry/DLQ."""
    if not TRACKING_TABLE or not QUARANTINE_BUCKET:
        # Misconfiguration must fail the whole batch (retry) rather than silently
        # dropping records — nothing is safe to acknowledge.
        logger.error("Misconfigured: TRACKING_TABLE/QUARANTINE_BUCKET not set")
        raise RuntimeError("Hub ingestion gate is misconfigured")

    records = event.get("Records", []) or []
    batch_item_failures: list[dict[str, str]] = []

    for record in records:
        message_id = record.get("messageId") or ""
        try:
            _process_record(record)
        except Exception:
            # Genuinely unprocessable (AWS error, failed quarantine write). Report
            # it so SQS retries this single message and ultimately DLQs it. The
            # live tracking table is never written from a failed path.
            logger.exception(
                "unprocessable message message_id=%s (will retry/DLQ)", message_id
            )
            if message_id:
                batch_item_failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": batch_item_failures}
