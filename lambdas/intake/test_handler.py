"""Unit tests for the ZTIE intake Lambda handler.

moto is used at the UNIT level only (explicitly agreed) to simulate the S3 +
DynamoDB API surface. There are no application-level stubs: the handler's real
boto3 code paths run against moto's emulated AWS APIs. Live integration
validation is performed by the user against real AWS (Story 1.1 DoD).
"""

from __future__ import annotations

import base64
import importlib
import json

import boto3
import pytest
from moto import mock_aws

BUCKET = "ztie-intake-artifacts-test"
TABLE = "ztie-intake-test"
REGION = "us-east-1"


@pytest.fixture()
def handler_module(monkeypatch):
    """Provision moto-backed S3 + DynamoDB and (re)import the handler fresh."""
    with mock_aws():
        monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)
        monkeypatch.setenv("ARTIFACT_BUCKET", BUCKET)
        monkeypatch.setenv("INTAKE_TABLE", TABLE)

        s3 = boto3.client("s3", region_name=REGION)
        s3.create_bucket(Bucket=BUCKET)

        ddb = boto3.resource("dynamodb", region_name=REGION)
        ddb.create_table(
            TableName=TABLE,
            KeySchema=[{"AttributeName": "intake_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "intake_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        import handler as handler_mod  # noqa: WPS433 — deliberate fresh import
        importlib.reload(handler_mod)
        # Reset cached clients so they bind to the moto session.
        handler_mod._s3_client = None
        handler_mod._intake_table = None
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


def test_accepts_and_persists_artifact(handler_module):
    content = b"AWSTemplateFormatVersion: '2010-09-09'\nResources: {}\n"
    resp = handler_module.handler(
        _event(_artifact_body(content, content_type="text/yaml", submitter="ci-pipeline"),
               caller_arn="arn:aws:iam::641628980935:role/sandbox-submitter"),
    )

    assert resp["statusCode"] == 201
    payload = json.loads(resp["body"])
    assert payload["status"] == "RECEIVED"
    assert payload["intake_id"]
    assert payload["size_bytes"] == len(content)

    # Verify the produced artifacts, not just the response.
    s3 = boto3.client("s3", region_name=REGION)
    obj = s3.get_object(Bucket=BUCKET, Key=payload["s3_key"])
    assert obj["Body"].read() == content

    ddb = boto3.resource("dynamodb", region_name=REGION)
    item = ddb.Table(TABLE).get_item(Key={"intake_id": payload["intake_id"]})["Item"]
    assert item["status"] == "RECEIVED"
    assert item["sha256"] == payload["sha256"]
    assert item["submitted_by_arn"] == "arn:aws:iam::641628980935:role/sandbox-submitter"


def test_sha256_matches_content(handler_module):
    import hashlib

    content = b"print('hello ZTIE')\n"
    resp = handler_module.handler(_event(_artifact_body(content, filename="payload.py")))
    payload = json.loads(resp["body"])
    assert payload["sha256"] == hashlib.sha256(content).hexdigest()


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


def test_defaults_applied_when_optional_fields_absent(handler_module):
    resp = handler_module.handler(_event(_artifact_body(b"content", filename="f.bin")))
    payload = json.loads(resp["body"])
    ddb = boto3.resource("dynamodb", region_name=REGION)
    item = ddb.Table(TABLE).get_item(Key={"intake_id": payload["intake_id"]})["Item"]
    assert item["content_type"] == "application/octet-stream"
    assert item["submitter"] == "unknown"


def test_misconfiguration_returns_500(monkeypatch):
    """No bucket/table configured -> 500 with a correlation id, not a crash."""
    import handler as handler_mod
    importlib.reload(handler_mod)
    monkeypatch.setattr(handler_mod, "ARTIFACT_BUCKET", "")
    monkeypatch.setattr(handler_mod, "INTAKE_TABLE", "")
    resp = handler_mod.handler(_event(_artifact_body(b"x")))
    assert resp["statusCode"] == 500
    assert "correlation_id" in json.loads(resp["body"])
