"""Unit tests for the ZTIE intake Lambda handler (Story 1.1 + 1.1R).

moto is used at the UNIT level only (explicitly agreed) to simulate the S3 + SQS
API surface. There are no application-level stubs: the handler's real boto3 code
paths run against moto's emulated AWS APIs. Live integration validation is
performed by the user against real AWS (Story 1.1R DoD).

1.1R change: the handler no longer writes a durable DynamoDB record in Forensic.
It stores the raw body in Forensic S3 and emits a DERIVED, contract-shaped
envelope to the Hub-owned ingest SQS queue. These tests assert that new behavior
and that no Forensic durable store is touched.
"""

from __future__ import annotations

import base64
import importlib
import json

import boto3
import pytest
from moto import mock_aws

BUCKET = "ztie-intake-artifacts-test"
REGION = "us-east-1"
QUEUE_NAME = "ztie-hub-ingest-test"
FORENSIC_ACCT = "360999005254"


@pytest.fixture()
def handler_module(monkeypatch):
    """Provision moto-backed S3 + SQS and (re)import the handler fresh."""
    with mock_aws():
        monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)
        monkeypatch.setenv("ARTIFACT_BUCKET", BUCKET)
        monkeypatch.setenv("FORENSIC_ACCOUNT_ID", FORENSIC_ACCT)
        monkeypatch.setenv("CONTRACT_VERSION", "1.0")

        s3 = boto3.client("s3", region_name=REGION)
        s3.create_bucket(Bucket=BUCKET)

        sqs = boto3.client("sqs", region_name=REGION)
        queue_url = sqs.create_queue(QueueName=QUEUE_NAME)["QueueUrl"]
        monkeypatch.setenv("HUB_INGEST_QUEUE_URL", queue_url)

        import handler as handler_mod  # noqa: WPS433 — deliberate fresh import
        importlib.reload(handler_mod)
        # Reset cached clients so they bind to the moto session.
        handler_mod._s3_client = None
        handler_mod._sqs_client = None
        handler_mod._queue_url_for_test = queue_url
        yield handler_mod


def _event(body: dict, is_b64: bool = False, caller_arn: str | None = None) -> dict:
    raw = json.dumps(body)
    if is_b64:
        raw = base64.b64encode(raw.encode()).decode()
    event = {"body": raw, "isBase64Encoded": is_b64}
    if caller_arn:
        event["requestContext"] = {"identity": {"userArn": caller_arn}}
    return event


def _artifact_body(content: bytes, filename: str = "template.yaml", **extra) -> dict:
    body = {"filename": filename, "content_base64": base64.b64encode(content).decode()}
    body.update(extra)
    return body


def _drain_envelope(handler_module) -> dict:
    """Receive exactly the one envelope the handler sent, and return it decoded."""
    sqs = boto3.client("sqs", region_name=REGION)
    msgs = sqs.receive_message(
        QueueUrl=handler_module._queue_url_for_test, MaxNumberOfMessages=10
    ).get("Messages", [])
    assert len(msgs) == 1, f"expected exactly one envelope, got {len(msgs)}"
    return json.loads(msgs[0]["Body"])


def test_accepts_stores_body_and_emits_envelope(handler_module):
    content = b"AWSTemplateFormatVersion: '2010-09-09'\nResources: {}\n"
    resp = handler_module.handler(
        _event(
            _artifact_body(content, content_type="text/yaml", submitter="ci-pipeline"),
            caller_arn="arn:aws:iam::360999005254:role/forensic-submitter",
        ),
    )

    assert resp["statusCode"] == 201
    payload = json.loads(resp["body"])
    assert payload["status"] == "RECEIVED"
    assert payload["intake_id"]
    assert payload["size_bytes"] == len(content)

    # Raw body persisted to Forensic S3.
    s3 = boto3.client("s3", region_name=REGION)
    obj = s3.get_object(Bucket=BUCKET, Key=payload["s3_key"])
    assert obj["Body"].read() == content

    # A single DERIVED envelope emitted to the Hub ingest queue.
    env = _drain_envelope(handler_module)
    assert env["contract_version"] == "1.0"
    assert env["intake_id"] == payload["intake_id"]
    assert env["sha256"] == payload["sha256"]
    assert env["status"] == "RECEIVED"
    assert env["size_bytes"] == len(content)
    assert env["artifact"]["filename"] == "template.yaml"
    assert env["artifact"]["claimed_content_type"] == "text/yaml"
    assert env["artifact"]["submitter"] == "ci-pipeline"
    assert env["origin"]["account_id"] == FORENSIC_ACCT
    assert env["origin"]["s3_bucket"] == BUCKET
    assert env["origin"]["s3_key"] == payload["s3_key"]
    assert env["origin"]["submitted_by_arn"] == (
        "arn:aws:iam::360999005254:role/forensic-submitter"
    )


def test_envelope_carries_no_payload_or_executable_field(handler_module):
    """The derived envelope must NOT carry the artifact body or any base64 blob."""
    content = b"<html><script>alert(1)</script></html>"
    handler_module.handler(
        _event(_artifact_body(content, filename="evil.html", content_type="text/html")),
    )
    env = _drain_envelope(handler_module)
    # No field anywhere in the envelope should contain the raw body / base64.
    flat = json.dumps(env)
    assert "content_base64" not in flat
    assert base64.b64encode(content).decode() not in flat
    assert "<script>" not in flat
    # The claimed type is preserved as inert metadata only.
    assert env["artifact"]["claimed_content_type"] == "text/html"


def test_untrusted_artifact_stored_as_octet_stream(handler_module):
    content = b"<html><script>alert(1)</script></html>"
    resp = handler_module.handler(
        _event(_artifact_body(content, filename="evil.html", content_type="text/html")),
    )
    payload = json.loads(resp["body"])
    s3 = boto3.client("s3", region_name=REGION)
    obj = s3.get_object(Bucket=BUCKET, Key=payload["s3_key"])
    assert obj["ContentType"] == "application/octet-stream"
    assert obj["Metadata"]["claimed-content-type"] == "text/html"


def test_sha256_matches_content(handler_module):
    import hashlib

    content = b"print('hello ZTIE')\n"
    resp = handler_module.handler(_event(_artifact_body(content, filename="payload.py")))
    payload = json.loads(resp["body"])
    assert payload["sha256"] == hashlib.sha256(content).hexdigest()


def test_defaults_applied_when_optional_fields_absent(handler_module):
    handler_module.handler(_event(_artifact_body(b"content", filename="f.bin")))
    env = _drain_envelope(handler_module)
    assert env["artifact"]["claimed_content_type"] == "application/octet-stream"
    # submitter defaults to "unknown" and is carried through.
    assert env["artifact"]["submitter"] == "unknown"


def test_base64_encoded_transport_body(handler_module):
    content = b"resource content"
    resp = handler_module.handler(_event(_artifact_body(content), is_b64=True))
    assert resp["statusCode"] == 201


def test_missing_body_rejected(handler_module):
    resp = handler_module.handler({"body": None})
    assert resp["statusCode"] == 400
    assert "correlation_id" in json.loads(resp["body"])


def test_invalid_json_rejected(handler_module):
    resp = handler_module.handler({"body": "{not json"})
    assert resp["statusCode"] == 400


def test_missing_filename_rejected(handler_module):
    body = {"content_base64": base64.b64encode(b"x").decode()}
    resp = handler_module.handler(_event(body))
    assert resp["statusCode"] == 400


def test_missing_content_rejected(handler_module):
    resp = handler_module.handler(_event({"filename": "a.txt"}))
    assert resp["statusCode"] == 400


def test_empty_artifact_rejected(handler_module):
    resp = handler_module.handler(_event(_artifact_body(b"")))
    assert resp["statusCode"] == 400


def test_invalid_base64_content_rejected(handler_module):
    resp = handler_module.handler(_event({"filename": "a.txt", "content_base64": "!!!notb64"}))
    assert resp["statusCode"] == 400


def test_path_traversal_filename_rejected(handler_module):
    resp = handler_module.handler(_event(_artifact_body(b"x", filename="../../etc/passwd")))
    assert resp["statusCode"] == 400


def test_absolute_path_filename_rejected(handler_module):
    resp = handler_module.handler(_event(_artifact_body(b"x", filename="/etc/passwd")))
    assert resp["statusCode"] == 400


def test_oversize_artifact_rejected(handler_module, monkeypatch):
    monkeypatch.setattr(handler_module, "MAX_ARTIFACT_BYTES", 16)
    resp = handler_module.handler(_event(_artifact_body(b"x" * 32)))
    assert resp["statusCode"] == 413


def test_misconfiguration_returns_500(monkeypatch):
    """No bucket/queue configured -> 500 with a correlation id, not a crash."""
    import handler as handler_mod
    importlib.reload(handler_mod)
    monkeypatch.setattr(handler_mod, "ARTIFACT_BUCKET", "")
    monkeypatch.setattr(handler_mod, "HUB_INGEST_QUEUE_URL", "")
    resp = handler_mod.handler(_event(_artifact_body(b"x")))
    assert resp["statusCode"] == 500
    assert "correlation_id" in json.loads(resp["body"])
