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

# The contract schema is bundled into the Lambda asset next to this file.
_SCHEMA_FILENAME = "intake-tracking.contract.v1.json"

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


class ContractViolation(Exception):
    """The envelope failed the data contract. Fail-closed: quarantine, never persist."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _load_validator() -> Draft7Validator:
    global _validator
    if _validator is None:
        schema_path = os.path.join(os.path.dirname(__file__), _SCHEMA_FILENAME)
        with open(schema_path, encoding="utf-8") as fh:
            schema = json.load(fh)
        _validator = Draft7Validator(schema)
    return _validator


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


def _process_record(record: dict[str, Any]) -> None:
    """Process one SQS record. Contract failures quarantine (no raise); only
    genuinely unprocessable conditions raise (so the message retries/DLQs)."""
    message_id = record.get("messageId") or str(uuid.uuid4())
    raw_body = record.get("body")
    try:
        envelope = _parse_envelope(raw_body)
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
        if exc.__class__.__name__ == "ConditionalCheckFailedException" or (
            hasattr(exc, "response")
            and getattr(exc, "response", {}).get("Error", {}).get("Code")
            == "ConditionalCheckFailedException"
        ):
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
