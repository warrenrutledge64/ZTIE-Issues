"""Unit tests for the ZTIE Hub validating ingestion gate (Story 1.1R).

This is the RD-013 contract enforcer. The tests prove the two things the Definition
of Done hinges on:

  1. A contract-VALID envelope lands as a durable record in the Hub tracking table.
  2. A malformed / oversized / injection-crafted / unknown-field / wrong-version /
     verdict-asserting envelope is REJECTED (fail-closed): quarantined to S3 and
     NEVER written to the live tracking table.

moto is used at the UNIT level only (explicitly agreed): the handler's real boto3
paths run against emulated DynamoDB + S3. Live integration validation is performed
by the user against real AWS.
"""

from __future__ import annotations

import copy
import importlib
import json

import boto3
import pytest
from moto import mock_aws

REGION = "us-east-1"
TABLE = "ztie-hub-tracking-test"
QUARANTINE = "ztie-hub-quarantine-test"

VALID_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
VALID_SHA256 = "a" * 64


def _valid_envelope() -> dict:
    return {
        "contract_version": "1.0",
        "intake_id": VALID_INTAKE_ID,
        "sha256": VALID_SHA256,
        "status": "RECEIVED",
        "received_at": "2026-08-24T12:00:00Z",
        "size_bytes": 52,
        "artifact": {
            "filename": "template.yaml",
            "claimed_content_type": "text/yaml",
            "submitter": "ci-pipeline",
        },
        "origin": {
            "account_id": "360999005254",
            "s3_bucket": "ztie-intake-artifacts",
            "s3_key": f"intake/{VALID_INTAKE_ID}/template.yaml",
            "submitted_by_arn": "arn:aws:iam::360999005254:role/forensic-submitter",
        },
    }


@pytest.fixture()
def handler_module(monkeypatch):
    with mock_aws():
        monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)
        monkeypatch.setenv("TRACKING_TABLE", TABLE)
        monkeypatch.setenv("QUARANTINE_BUCKET", QUARANTINE)
        monkeypatch.setenv("CONTRACT_VERSION", "1.0")

        ddb = boto3.resource("dynamodb", region_name=REGION)
        ddb.create_table(
            TableName=TABLE,
            KeySchema=[{"AttributeName": "intake_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "intake_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        s3 = boto3.client("s3", region_name=REGION)
        s3.create_bucket(Bucket=QUARANTINE)

        import handler as handler_mod  # noqa: WPS433 — deliberate fresh import
        importlib.reload(handler_mod)
        handler_mod._ddb_table = None
        handler_mod._s3_client = None
        handler_mod._validator = None
        yield handler_mod


def _sqs_event(*bodies) -> dict:
    return {
        "Records": [
            {"messageId": f"msg-{i}", "body": b if isinstance(b, str) else json.dumps(b)}
            for i, b in enumerate(bodies)
        ]
    }


def _table_items():
    ddb = boto3.resource("dynamodb", region_name=REGION)
    return ddb.Table(TABLE).scan().get("Items", [])


def _quarantine_keys():
    s3 = boto3.client("s3", region_name=REGION)
    return [o["Key"] for o in s3.list_objects_v2(Bucket=QUARANTINE).get("Contents", [])]


# --- The happy path ---------------------------------------------------------


def test_valid_envelope_lands_in_tracking_table(handler_module):
    result = handler_module.handler(_sqs_event(_valid_envelope()))
    assert result == {"batchItemFailures": []}

    items = _table_items()
    assert len(items) == 1
    item = items[0]
    assert item["intake_id"] == VALID_INTAKE_ID
    assert item["sha256"] == VALID_SHA256
    assert item["status"] == "RECEIVED"
    assert item["filename"] == "template.yaml"
    assert item["claimed_content_type"] == "text/yaml"
    assert item["origin_s3_bucket"] == "ztie-intake-artifacts"
    assert "hub_ingested_at" in item
    # Nothing quarantined on the happy path.
    assert _quarantine_keys() == []


def test_redelivery_is_idempotent(handler_module):
    """SQS at-least-once: the same envelope twice yields one record, no failure."""
    handler_module.handler(_sqs_event(_valid_envelope()))
    handler_module.handler(_sqs_event(_valid_envelope()))
    assert len(_table_items()) == 1


# --- Fail-closed rejections (the core RD-013 guarantee) ---------------------


def _assert_rejected(handler_module, bad_body):
    """A bad body must be quarantined, NOT written to the live table, and NOT
    reported as a retryable batch failure (it will never become valid)."""
    result = handler_module.handler(_sqs_event(bad_body))
    assert result == {"batchItemFailures": []}, "contract failure must not retry"
    assert _table_items() == [], "non-conforming record must never be written live"
    assert len(_quarantine_keys()) == 1, "must be quarantined"


def test_reject_not_json(handler_module):
    _assert_rejected(handler_module, "{not json")


def test_reject_not_an_object(handler_module):
    _assert_rejected(handler_module, json.dumps([1, 2, 3]))


def test_reject_missing_required_field(handler_module):
    env = _valid_envelope()
    del env["sha256"]
    _assert_rejected(handler_module, env)


def test_reject_unknown_extra_field(handler_module):
    """additionalProperties:false — an unexpected field is a rejection."""
    env = _valid_envelope()
    env["evil_extra"] = "surprise"
    _assert_rejected(handler_module, env)


def test_reject_bad_intake_id_pattern(handler_module):
    env = _valid_envelope()
    env["intake_id"] = "not-a-uuid"
    _assert_rejected(handler_module, env)


def test_reject_bad_sha256_pattern(handler_module):
    env = _valid_envelope()
    env["sha256"] = "xyz"
    _assert_rejected(handler_module, env)


def test_reject_oversize_size_bytes(handler_module):
    env = _valid_envelope()
    env["size_bytes"] = 999_999_999
    _assert_rejected(handler_module, env)


def test_reject_overlong_filename(handler_module):
    env = _valid_envelope()
    env["artifact"]["filename"] = "a" * 5000
    _assert_rejected(handler_module, env)


def test_reject_wrong_contract_version(handler_module):
    env = _valid_envelope()
    env["contract_version"] = "9.9"
    _assert_rejected(handler_module, env)


def test_reject_imported_verdict_status(handler_module):
    """A crossed record must not be able to assert a verdict via status."""
    for verdict in ("PASS", "FAIL", "INCONCLUSIVE", "APPROVED"):
        env = _valid_envelope()
        env["status"] = verdict
        _assert_rejected(handler_module, env)
        # reset table/quarantine between iterations is not needed; each rejection
        # only quarantines and never writes the table, but re-check the invariant:
        assert _table_items() == []


def test_reject_injection_crafted_payload_field(handler_module):
    """An attacker trying to smuggle a body/base64/script field is rejected by the
    allow-list (no such field exists in the contract)."""
    for bad_key, bad_val in (
        ("content_base64", "ZXZpbA=="),
        ("body", "<script>alert(1)</script>"),
        ("__proto__", {"polluted": True}),
        ("verdict", "PASS"),
    ):
        env = _valid_envelope()
        env[bad_key] = bad_val
        _assert_rejected(handler_module, env)


def test_reject_oversized_envelope_body(handler_module):
    """A hostile oversized raw body is rejected by the pre-parse byte guard,
    before any JSON/schema work — bounding allocation on attacker-controlled input."""
    huge_raw = "x" * (262144 + 10)  # exceeds _MAX_ENVELOPE_BYTES, invalid JSON too
    _assert_rejected(handler_module, huge_raw)


# --- Mixed batch + partial failure behavior ---------------------------------


def test_mixed_batch_valid_and_invalid(handler_module):
    """A batch with one valid + one invalid: valid persists, invalid quarantines,
    neither is a retryable failure."""
    good = _valid_envelope()
    bad = copy.deepcopy(_valid_envelope())
    bad["intake_id"] = "def"  # bad pattern
    result = handler_module.handler(_sqs_event(good, bad))
    assert result == {"batchItemFailures": []}
    assert len(_table_items()) == 1
    assert len(_quarantine_keys()) == 1


def test_unprocessable_write_error_is_retryable(handler_module, monkeypatch):
    """If the durable WRITE itself fails (AWS error), the message IS reported as a
    batch failure so SQS retries/DLQs it — it is not silently dropped."""

    def _boom(*_a, **_k):
        raise RuntimeError("simulated DynamoDB outage")

    # Force the persist path to fail after a valid envelope.
    monkeypatch.setattr(handler_module, "_persist", _boom)
    result = handler_module.handler(_sqs_event(_valid_envelope()))
    assert result == {"batchItemFailures": [{"itemIdentifier": "msg-0"}]}


def test_misconfiguration_raises(monkeypatch):
    """No table/bucket configured -> raise (fail the whole batch), never drop."""
    import handler as handler_mod
    importlib.reload(handler_mod)
    monkeypatch.setattr(handler_mod, "TRACKING_TABLE", "")
    monkeypatch.setattr(handler_mod, "QUARANTINE_BUCKET", "")
    with pytest.raises(RuntimeError):
        handler_mod.handler(_sqs_event(_valid_envelope()))


# --- Story 1.3: the routing-decision envelope (third kind on the same gate) --


def _valid_routing_envelope() -> dict:
    return {
        "contract_version": "1.0",
        "intake_id": VALID_INTAKE_ID,
        "sha256": VALID_SHA256,
        "routed_at": "2026-08-25T12:00:00Z",
        "routing": {
            "artifact_class": "iac_template",
            "lanes": ["static_analysis", "dynamic_detonation"],
            "routable": True,
            "basis": "class_route",
        },
    }


def _seed_tracking_record(sha256: str = VALID_SHA256) -> None:
    """Put an existing RECEIVED tracking record so the integrity-bound routing
    apply (attribute_exists AND sha256 match) can attach to it."""
    ddb = boto3.resource("dynamodb", region_name=REGION)
    ddb.Table(TABLE).put_item(
        Item={
            "intake_id": VALID_INTAKE_ID,
            "sha256": sha256,
            "status": "RECEIVED",
            "received_at": "2026-08-24T12:00:00Z",
        }
    )


def test_routing_decision_attaches_to_existing_record(handler_module):
    """A valid routing decision upserts onto the EXISTING record (integrity-bound),
    setting routing + routing_lanes and NEVER touching status/verdict."""
    _seed_tracking_record()
    result = handler_module.handler(_sqs_event(_valid_routing_envelope()))
    assert result == {"batchItemFailures": []}

    items = _table_items()
    assert len(items) == 1
    item = items[0]
    assert item["routing"]["artifact_class"] == "iac_template"
    assert item["routing"]["lanes"] == ["static_analysis", "dynamic_detonation"]
    assert item["routing_lanes"] == ["static_analysis", "dynamic_detonation"]
    assert item["routed_at"] == "2026-08-25T12:00:00Z"
    # The routing decision must NOT create a verdict or alter status.
    assert item["status"] == "RECEIVED"
    assert "verdict" not in item
    assert _quarantine_keys() == []


def test_routing_decision_never_creates_a_record(handler_module):
    """If the intake record is absent (ordering race), the conditional update
    fails -> the message is reported as a retryable batch failure, and NOTHING is
    written to the live table (never create-on-route)."""
    result = handler_module.handler(_sqs_event(_valid_routing_envelope()))
    assert result == {"batchItemFailures": [{"itemIdentifier": "msg-0"}]}
    assert _table_items() == []
    # An ordering race is retryable, NOT a contract failure -> not quarantined.
    assert _quarantine_keys() == []


def test_routing_sha_mismatch_is_quarantined(handler_module):
    """A routing decision whose sha256 does not match the tracked record is an
    integrity violation -> quarantined, never applied, never retried."""
    _seed_tracking_record(sha256="b" * 64)  # record has a DIFFERENT sha
    result = handler_module.handler(_sqs_event(_valid_routing_envelope()))
    assert result == {"batchItemFailures": []}  # not retryable
    assert len(_quarantine_keys()) == 1
    # The record is untouched (no routing attached).
    item = _table_items()[0]
    assert "routing" not in item


def test_reject_routing_missing_lanes(handler_module):
    env = _valid_routing_envelope()
    del env["routing"]["lanes"]
    _assert_rejected(handler_module, env)


def test_reject_routing_unknown_lane(handler_module):
    env = _valid_routing_envelope()
    env["routing"]["lanes"] = ["forward_to_pde"]  # not in the lane enum
    _assert_rejected(handler_module, env)


def test_reject_routing_smuggled_verdict_field(handler_module):
    """A routing decision is a plan of controls: an attempt to smuggle a verdict /
    forward field is rejected by the allow-list."""
    for bad_key, bad_val in (
        ("verdict", "PASS"),
        ("forward", True),
        ("approved", True),
    ):
        env = _valid_routing_envelope()
        env["routing"][bad_key] = bad_val
        _assert_rejected(handler_module, env)


def test_reject_routing_wrong_contract_version(handler_module):
    env = _valid_routing_envelope()
    env["contract_version"] = "9.9"
    _assert_rejected(handler_module, env)
