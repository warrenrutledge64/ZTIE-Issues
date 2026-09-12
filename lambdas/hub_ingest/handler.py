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
# Story 2.2 bumped ONLY the static-scan summary contract to 1.1 (additive: the
# signature-scan tool + a bounded compliance roll-up). The other four envelope
# kinds (intake-tracking / classification / routing / reject) are unchanged and
# still pinned to CONTRACT_VERSION ("1.0"). The summary therefore has its OWN
# version pin so a summary v1.1 is accepted while the rest stay 1.0.
SUMMARY_CONTRACT_VERSION = os.environ.get("SUMMARY_CONTRACT_VERSION", "1.1")
# Story 2.3: the dynamic-run OUTCOME envelope (the sixth envelope kind) pins its
# version SEPARATELY (2.2's lesson — each envelope kind versions independently, so
# a new kind never rides the shared CONTRACT_VERSION). Currently "1.0".
DYNAMIC_RUN_CONTRACT_VERSION = os.environ.get("DYNAMIC_RUN_CONTRACT_VERSION", "1.0")
# Story 2.6: the COLLECTED-record (join) envelope (the seventh envelope kind) pins
# its version SEPARATELY (the per-kind pin discipline — a new kind never rides the
# shared CONTRACT_VERSION). It is the bounded, verdict-free record the Story 2.6
# Parallel-state join emits, referencing the two per-lane summaries. Currently "1.0".
COLLECTED_CONTRACT_VERSION = os.environ.get("COLLECTED_CONTRACT_VERSION", "1.0")
# Story 2.4: the behavioral-telemetry envelope (the EIGHTH envelope kind) pins its
# version SEPARATELY (the per-kind pin discipline — a new kind never rides the
# shared CONTRACT_VERSION). It is the bounded, verdict-free behavioral summary
# (syscalls/network/filesystem) captured during the dynamic detonation. Currently "1.0".
BEHAVIOR_CONTRACT_VERSION = os.environ.get("BEHAVIOR_CONTRACT_VERSION", "1.0")
# Story 2.5: the sanitized-telemetry envelope (the NINTH envelope kind) pins its OWN
# version so it validates independently of the shared CONTRACT_VERSION and every
# other per-kind pin. It is the bounded, verdict-free sanitized view the Story 2.5
# pipeline produces from the 2.4 raw trace.
SANITIZED_TELEMETRY_CONTRACT_VERSION = os.environ.get(
    "SANITIZED_TELEMETRY_CONTRACT_VERSION", "1.0"
)

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
# Story 2.1 / 2.2: the derived static-scan SUMMARY contract (a fifth envelope kind
# on the SAME gate). Bounded counts + per-tool status + (Story 2.2, v1.1) a bounded
# compliance roll-up + a pointer to the full findings document in Forensic.
# EVIDENCE — never a verdict.
_SUMMARY_SCHEMA_FILENAME = "static-scan-summary.contract.v1.json"
# Story 2.3: the derived dynamic-run OUTCOME contract (a sixth envelope kind on the
# SAME gate). Bounded run facts (instance/launch-template/SSM status + containment +
# TTL teardown) + a pointer to the full command log in Forensic. EVIDENCE — never a
# verdict; the schema has no verdict/safe/forward field.
_DYNAMIC_RUN_SCHEMA_FILENAME = "dynamic-run.contract.v1.json"
# Story 2.6: the derived COLLECTED-record (join) contract (a seventh envelope kind
# on the SAME gate). The bounded roll-up of BOTH inspection lanes for one intake
# (per-lane status + join facts + Forensic pointers). EVIDENCE — never a verdict;
# the schema has no verdict/safe/forward field. Discriminated by a unique
# ``collected`` key; pins its OWN version (COLLECTED_CONTRACT_VERSION).
_COLLECTED_SCHEMA_FILENAME = "collected.contract.v1.json"
# Story 2.4: the derived behavioral-telemetry contract (an eighth envelope kind on
# the SAME gate). Bounded syscall/network/filesystem summaries + capture health +
# relative offsets + a pointer to the full trace in Forensic. EVIDENCE — never a
# verdict; the schema has no verdict/safe/forward field. Discriminated by a unique
# ``behavior`` key; pins its OWN version (BEHAVIOR_CONTRACT_VERSION).
_BEHAVIOR_SCHEMA_FILENAME = "behavior.contract.v1.json"
# Story 2.5: the derived SANITIZED-telemetry contract (a NINTH envelope kind on the
# SAME gate). The bounded, token-budgeted, entropy-scrubbed, noise-suppressed
# sanitized view of the 2.4 raw trace (a pipeline-accounting object + a capped
# sanitized event sequence + a pointer to the full trace in Forensic). EVIDENCE —
# never a verdict; the schema has no verdict/safe/forward field. Discriminated by a
# unique ``sanitized`` key; pins its OWN version (SANITIZED_TELEMETRY_CONTRACT_VERSION).
_SANITIZED_SCHEMA_FILENAME = "sanitized-telemetry.contract.v1.json"

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
_summary_validator: Draft7Validator | None = None
_dynamic_run_validator: Draft7Validator | None = None
_collected_validator: Draft7Validator | None = None
_behavior_validator: Draft7Validator | None = None
_sanitized_validator: Draft7Validator | None = None


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


def _load_summary_validator() -> Draft7Validator:
    global _summary_validator
    if _summary_validator is None:
        _summary_validator = Draft7Validator(_load_schema(_SUMMARY_SCHEMA_FILENAME))
    return _summary_validator


def _load_dynamic_run_validator() -> Draft7Validator:
    global _dynamic_run_validator
    if _dynamic_run_validator is None:
        _dynamic_run_validator = Draft7Validator(
            _load_schema(_DYNAMIC_RUN_SCHEMA_FILENAME)
        )
    return _dynamic_run_validator


def _load_collected_validator() -> Draft7Validator:
    global _collected_validator
    if _collected_validator is None:
        _collected_validator = Draft7Validator(
            _load_schema(_COLLECTED_SCHEMA_FILENAME)
        )
    return _collected_validator


def _load_sanitized_validator() -> Draft7Validator:
    global _sanitized_validator
    if _sanitized_validator is None:
        _sanitized_validator = Draft7Validator(
            _load_schema(_SANITIZED_SCHEMA_FILENAME)
        )
    return _sanitized_validator


def _load_behavior_validator() -> Draft7Validator:
    global _behavior_validator
    if _behavior_validator is None:
        _behavior_validator = Draft7Validator(
            _load_schema(_BEHAVIOR_SCHEMA_FILENAME)
        )
    return _behavior_validator


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


def _is_summary_envelope(envelope: dict[str, Any]) -> bool:
    """Route by envelope KIND. The static-scan summary envelope (Story 2.1) carries
    a ``scan`` object."""
    return "scan" in envelope


def _is_dynamic_run_envelope(envelope: dict[str, Any]) -> bool:
    """Route by envelope KIND. The dynamic-run outcome envelope (Story 2.3) carries
    a ``run`` object (the detonation outcome). No other kind uses this key."""
    return "run" in envelope


def _is_collected_envelope(envelope: dict[str, Any]) -> bool:
    """Route by envelope KIND. The collected-record (join) envelope (Story 2.6)
    carries a ``collected`` object (the both-lane join). No other kind uses this
    key — the discriminator is unique. Checked FIRST in the dispatch chain so it can
    never be shadowed by a generic key."""
    return "collected" in envelope


def _is_behavior_envelope(envelope: dict[str, Any]) -> bool:
    """Route by envelope KIND. The behavioral-telemetry envelope (Story 2.4) carries
    a ``behavior`` object (the captured syscall/network/filesystem summary). No other
    kind uses this key — the discriminator is unique."""
    return "behavior" in envelope


def _is_sanitized_envelope(envelope: dict[str, Any]) -> bool:
    """Route by envelope KIND. The sanitized-telemetry envelope (Story 2.5) carries
    a ``sanitized`` object (the entropy-scrubbed, noise-suppressed, <=25K-token view
    of the 2.4 raw trace). No other kind uses this key — the discriminator is unique."""
    return "sanitized" in envelope


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


# --- Derived-envelope KIND registry (Story C.3, RD-034) ---------------------
#
# The eight DERIVED envelope kinds (classification / routing / reject / static-scan
# summary / dynamic-run / collected / behavior / sanitized) each used to carry an
# IDENTICAL validate + apply + process trio — the same control flow copy-pasted
# eight times, differing ONLY in data: the discriminator key, which validator to
# load, which version-pin constant to enforce, the error-message label, the
# DynamoDB UpdateExpression, and which values it flattens onto the record. That was
# a real copy-drift surface (a fix to one apply/validate path would silently miss
# the other seven). C.3 collapses the DUPLICATED CONTROL FLOW into the three
# generic helpers below (_validate_kind / _apply_kind / _process_kind), driven by
# this data-only registry — WITHOUT changing any behaviour and WITHOUT removing any
# per-kind function name (each _validate_<kind>_contract / _apply_<kind> /
# _process_<kind> remains as a thin named delegate, so the dispatch, the tests, and
# the monkeypatch targets are all preserved exactly).
#
# The intake-tracking envelope is deliberately NOT in this registry: it is
# structurally different (it CREATES the record via _persist with a different,
# non-integrity-bound condition and it is the one path that sets ``status``), so it
# keeps its own _validate_contract / _persist path in _process_record's fallthrough.


class _KindSpec:
    """Data-only description of one derived envelope kind. No behaviour lives here;
    the shared behaviour is in _validate_kind / _apply_kind / _process_kind."""

    def __init__(
        self,
        *,
        name: str,
        discriminator: str,
        payload_key: str,
        validator_loader,
        version_pin,
        error_label: str,
        resolve_label: str,
        update_expression: str,
        values_builder,
    ) -> None:
        # name           : short id for the registry (e.g. "classification").
        # discriminator  : the top-level key whose presence selects this kind.
        # payload_key    : the top-level key holding the derived payload object.
        # validator_loader: the cached _load_*_validator() for this kind.
        # version_pin    : a zero-arg callable returning the accepted contract_version
        #                  (a callable so per-kind env-var pins are read at call time,
        #                  exactly as the inline `!= CONSTANT` checks did).
        # error_label    : prefix used in the schema-validation ContractViolation
        #                  message (e.g. "classification schema validation failed").
        # resolve_label  : the kind label passed to _resolve_conditional_apply_failure
        #                  (e.g. "static-scan summary") — preserved verbatim.
        # update_expression: the DynamoDB SET expression for the integrity-bound apply.
        # values_builder : envelope -> ExpressionAttributeValues (WITHOUT :sha, which
        #                  the shared apply always adds from envelope["sha256"]).
        self.name = name
        self.discriminator = discriminator
        self.payload_key = payload_key
        self.validator_loader = validator_loader
        self.version_pin = version_pin
        self.error_label = error_label
        self.resolve_label = resolve_label
        self.update_expression = update_expression
        self.values_builder = values_builder


# Ordered exactly as the pre-C.3 dispatch chain checked discriminators: the unique
# discriminators (collected / sanitized / behavior) FIRST so they can never be
# shadowed, then dynamic-run / summary / reject / routing / classification. This
# order is the source of truth for _process_record's dispatch loop.
_KINDS: list[_KindSpec] = [
    _KindSpec(
        name="collected",
        discriminator="collected",
        payload_key="collected",
        validator_loader=lambda: _load_collected_validator(),
        version_pin=lambda: COLLECTED_CONTRACT_VERSION,
        error_label="collected schema validation failed",
        resolve_label="collected record",
        update_expression="SET collected = :c, collected_lanes = :l, joined_at = :ja",
        values_builder=lambda e: {
            ":c": e["collected"],
            ":l": e["collected"]["lanes_collected"],
            ":ja": e["joined_at"],
        },
    ),
    _KindSpec(
        name="sanitized",
        discriminator="sanitized",
        payload_key="sanitized",
        validator_loader=lambda: _load_sanitized_validator(),
        version_pin=lambda: SANITIZED_TELEMETRY_CONTRACT_VERSION,
        error_label="sanitized schema validation failed",
        resolve_label="sanitized telemetry",
        update_expression=(
            "SET sanitized = :s, sanitize_status = :ss, "
            "sanitize_truncated = :tr, sanitized_at = :sa"
        ),
        values_builder=lambda e: {
            ":s": e["sanitized"],
            ":ss": e["sanitized"]["pipeline"]["status"],
            ":tr": e["sanitized"]["pipeline"]["truncated"],
            ":sa": e["sanitized_at"],
        },
    ),
    _KindSpec(
        name="behavior",
        discriminator="behavior",
        payload_key="behavior",
        validator_loader=lambda: _load_behavior_validator(),
        version_pin=lambda: BEHAVIOR_CONTRACT_VERSION,
        error_label="behavior schema validation failed",
        resolve_label="behavioral telemetry",
        update_expression=(
            "SET behavior = :b, behavior_capture_status = :cs, captured_at = :ca"
        ),
        values_builder=lambda e: {
            ":b": e["behavior"],
            ":cs": e["behavior"]["capture"]["capture_status"],
            ":ca": e["captured_at"],
        },
    ),
    _KindSpec(
        name="dynamic_run",
        discriminator="run",
        payload_key="run",
        validator_loader=lambda: _load_dynamic_run_validator(),
        version_pin=lambda: DYNAMIC_RUN_CONTRACT_VERSION,
        error_label="dynamic-run schema validation failed",
        resolve_label="dynamic-run outcome",
        update_expression=(
            "SET dynamic_run = :r, dynamic_run_outcome = :o, detonated_at = :da"
        ),
        values_builder=lambda e: {
            ":r": e["run"],
            ":o": e["run"]["outcome"],
            ":da": e["detonated_at"],
        },
    ),
    _KindSpec(
        name="summary",
        discriminator="scan",
        payload_key="scan",
        validator_loader=lambda: _load_summary_validator(),
        version_pin=lambda: SUMMARY_CONTRACT_VERSION,
        error_label="summary schema validation failed",
        resolve_label="static-scan summary",
        update_expression=(
            "SET static_scan = :s, static_scan_highest_severity = :hs, "
            "static_scan_compliance = :sc, static_scanned_at = :sa"
        ),
        values_builder=lambda e: {
            ":s": e["scan"],
            ":hs": e["scan"]["highest_severity"],
            ":sc": e["scan"].get("compliance", {}),
            ":sa": e["scanned_at"],
        },
    ),
    _KindSpec(
        name="reject",
        discriminator="rejection",
        payload_key="rejection",
        validator_loader=lambda: _load_reject_validator(),
        version_pin=lambda: CONTRACT_VERSION,
        error_label="reject schema validation failed",
        resolve_label="rejection",
        update_expression=(
            "SET pipeline_outcome = :po, rejection = :r, rejected_at = :ra"
        ),
        values_builder=lambda e: {
            ":po": e["rejection"]["pipeline_outcome"],
            ":r": e["rejection"],
            ":ra": e["rejected_at"],
        },
    ),
    _KindSpec(
        name="routing",
        discriminator="routing",
        payload_key="routing",
        validator_loader=lambda: _load_routing_validator(),
        version_pin=lambda: CONTRACT_VERSION,
        error_label="routing schema validation failed",
        resolve_label="routing",
        update_expression="SET routing = :r, routing_lanes = :l, routed_at = :ra",
        values_builder=lambda e: {
            ":r": e["routing"],
            ":l": e["routing"]["lanes"],
            ":ra": e["routed_at"],
        },
    ),
    _KindSpec(
        name="classification",
        discriminator="classification",
        payload_key="classification",
        validator_loader=lambda: _load_classification_validator(),
        version_pin=lambda: CONTRACT_VERSION,
        error_label="classification schema validation failed",
        resolve_label="classification",
        update_expression=(
            "SET artifact_class = :ac, classification = :c, classified_at = :ca"
        ),
        values_builder=lambda e: {
            ":ac": e["classification"]["artifact_class"],
            ":c": e["classification"],
            ":ca": e["classified_at"],
        },
    ),
]

_KINDS_BY_NAME: dict[str, _KindSpec] = {spec.name: spec for spec in _KINDS}


def _validate_kind(spec: _KindSpec, envelope: dict[str, Any]) -> None:
    """Shared fail-closed contract validation for one derived kind. Identical to the
    pre-C.3 per-kind _validate_*_contract: run the kind's Draft7Validator, format the
    first five errors, then enforce the kind's version pin."""
    validator = spec.validator_loader()
    errors = sorted(validator.iter_errors(envelope), key=lambda e: list(e.absolute_path))
    if errors:
        detail = "; ".join(
            f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}"
            for e in errors[:5]
        )
        raise ContractViolation(f"{spec.error_label}: {detail}")
    expected = spec.version_pin()
    if envelope.get("contract_version") != expected:
        raise ContractViolation(
            f"unsupported {spec.name.replace('_', '-')} contract_version "
            f"{envelope.get('contract_version')!r} (expected {expected!r})"
        )


def _apply_kind(spec: _KindSpec, envelope: dict[str, Any]) -> None:
    """Shared integrity-bound apply for one derived kind. Attaches the derived payload
    to the EXISTING tracking record; requires the record to exist AND its stored
    ``sha256`` to equal the envelope's; NEVER creates a record and NEVER touches
    ``status`` / verdict. Identical to the pre-C.3 per-kind _apply_* update_item."""
    values = dict(spec.values_builder(envelope))
    values[":sha"] = envelope["sha256"]
    _table().update_item(
        Key={"intake_id": envelope["intake_id"]},
        UpdateExpression=spec.update_expression,
        ConditionExpression="attribute_exists(intake_id) AND sha256 = :sha",
        ExpressionAttributeValues=values,
    )


def _process_kind(
    spec: _KindSpec, envelope: dict[str, Any], raw_body: str | None, message_id: str
) -> None:
    """Shared fail-closed validate + integrity-bound apply for one derived kind.
    Identical control flow to the pre-C.3 per-kind _process_*: quarantine on a
    contract violation; on a conditional-check failure disambiguate ordering-race
    (retry) vs integrity-violation (quarantine) via _resolve_conditional_apply_failure.
    Note: it calls the module-level _validate_<name>_contract / _apply_<name> by their
    thin-delegate names below, so a test that monkeypatches one still intercepts."""
    try:
        _validate_kind(spec, envelope)
    except ContractViolation as violation:
        _quarantine(raw_body, violation.reason, message_id)
        return

    try:
        _apply_kind(spec, envelope)
    except Exception as exc:
        if _is_conditional_check_failure(exc):
            if _resolve_conditional_apply_failure(
                envelope, raw_body, message_id, spec.resolve_label
            ):
                raise  # retryable ordering race
            return  # quarantined (integrity violation)
        raise


# --- Thin per-kind named delegates ------------------------------------------
#
# Each of these preserves a function name that other code / tests reference (and,
# for _process_*, that _process_record dispatches to by name and tests monkeypatch).
# The body is a one-line delegate to the shared helper with the kind's spec, so the
# behaviour is identical while the duplicated bodies are gone.


def _validate_classification_contract(envelope: dict[str, Any]) -> None:
    _validate_kind(_KINDS_BY_NAME["classification"], envelope)


def _apply_classification(envelope: dict[str, Any]) -> None:
    _apply_kind(_KINDS_BY_NAME["classification"], envelope)


def _process_classification(
    envelope: dict[str, Any], raw_body: str | None, message_id: str
) -> None:
    _process_kind(_KINDS_BY_NAME["classification"], envelope, raw_body, message_id)


def _validate_routing_contract(envelope: dict[str, Any]) -> None:
    _validate_kind(_KINDS_BY_NAME["routing"], envelope)


def _apply_routing(envelope: dict[str, Any]) -> None:
    _apply_kind(_KINDS_BY_NAME["routing"], envelope)


def _process_routing(
    envelope: dict[str, Any], raw_body: str | None, message_id: str
) -> None:
    _process_kind(_KINDS_BY_NAME["routing"], envelope, raw_body, message_id)


def _validate_reject_contract(envelope: dict[str, Any]) -> None:
    _validate_kind(_KINDS_BY_NAME["reject"], envelope)


def _apply_reject(envelope: dict[str, Any]) -> None:
    _apply_kind(_KINDS_BY_NAME["reject"], envelope)


def _process_reject(
    envelope: dict[str, Any], raw_body: str | None, message_id: str
) -> None:
    _process_kind(_KINDS_BY_NAME["reject"], envelope, raw_body, message_id)


def _validate_summary_contract(envelope: dict[str, Any]) -> None:
    _validate_kind(_KINDS_BY_NAME["summary"], envelope)


def _apply_summary(envelope: dict[str, Any]) -> None:
    _apply_kind(_KINDS_BY_NAME["summary"], envelope)


def _process_summary(
    envelope: dict[str, Any], raw_body: str | None, message_id: str
) -> None:
    _process_kind(_KINDS_BY_NAME["summary"], envelope, raw_body, message_id)


def _validate_dynamic_run_contract(envelope: dict[str, Any]) -> None:
    _validate_kind(_KINDS_BY_NAME["dynamic_run"], envelope)


def _apply_dynamic_run(envelope: dict[str, Any]) -> None:
    _apply_kind(_KINDS_BY_NAME["dynamic_run"], envelope)


def _process_dynamic_run(
    envelope: dict[str, Any], raw_body: str | None, message_id: str
) -> None:
    _process_kind(_KINDS_BY_NAME["dynamic_run"], envelope, raw_body, message_id)


def _validate_collected_contract(envelope: dict[str, Any]) -> None:
    _validate_kind(_KINDS_BY_NAME["collected"], envelope)


def _apply_collected(envelope: dict[str, Any]) -> None:
    _apply_kind(_KINDS_BY_NAME["collected"], envelope)


def _process_collected(
    envelope: dict[str, Any], raw_body: str | None, message_id: str
) -> None:
    _process_kind(_KINDS_BY_NAME["collected"], envelope, raw_body, message_id)


def _validate_behavior_contract(envelope: dict[str, Any]) -> None:
    _validate_kind(_KINDS_BY_NAME["behavior"], envelope)


def _apply_behavior(envelope: dict[str, Any]) -> None:
    _apply_kind(_KINDS_BY_NAME["behavior"], envelope)


def _process_behavior(
    envelope: dict[str, Any], raw_body: str | None, message_id: str
) -> None:
    _process_kind(_KINDS_BY_NAME["behavior"], envelope, raw_body, message_id)


def _validate_sanitized_contract(envelope: dict[str, Any]) -> None:
    _validate_kind(_KINDS_BY_NAME["sanitized"], envelope)


def _apply_sanitized(envelope: dict[str, Any]) -> None:
    _apply_kind(_KINDS_BY_NAME["sanitized"], envelope)


def _process_sanitized(
    envelope: dict[str, Any], raw_body: str | None, message_id: str
) -> None:
    _process_kind(_KINDS_BY_NAME["sanitized"], envelope, raw_body, message_id)


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

    # Route by envelope kind: collected (join) vs sanitized (telemetry) vs behavior
    # (telemetry) vs dynamic-run vs summary vs reject vs routing vs classification vs
    # intake-tracking. Each carries a distinct discriminator key. The registry
    # ``_KINDS`` is ordered so the unique discriminators (Story 2.6 ``collected`` +
    # Story 2.5 ``sanitized`` + Story 2.4 ``behavior``) are checked FIRST and can
    # never be shadowed by a generic key. The dispatch calls the kind's named
    # ``_process_<name>`` via a module-attribute lookup (NOT a captured reference),
    # so a test that monkeypatches e.g. ``handler._process_collected`` still
    # intercepts — identical to the pre-C.3 explicit if/elif chain.
    for spec in _KINDS:
        if spec.discriminator in envelope:
            process_fn = globals()[f"_process_{spec.name}"]
            process_fn(envelope, raw_body, message_id)
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
