"""ZTIE Story 1.1 — Intake gateway Lambda handler.

The front door of the Zero Trust Inspection Engine. Accepts an incoming
deployment payload / code artifact via ``POST /intake`` (API Gateway REST,
IAM/SigV4 auth), persists the artifact body to S3, records a queryable intake
record in DynamoDB with ``status=RECEIVED``, and returns a stable ``intake_id``.

Zero-trust posture: the artifact is only *received and persisted* here. It is
never classified, marked safe, or forwarded downstream. Classification (Story
1.2), routing (1.3), and safe-reject (1.4) are separate downstream stories that
read the record this handler writes.

No mocks in the execution path: this talks to real S3 + DynamoDB via boto3.
``moto`` is used only in the unit tests.
"""

from __future__ import annotations

import base64
import binascii
import datetime as _dt
import hashlib
import json
import logging
import os
import re
import uuid
from typing import Any

import boto3

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# --- Configuration (from environment; set by the CDK stack) -----------------

ARTIFACT_BUCKET = os.environ.get("ARTIFACT_BUCKET", "")
INTAKE_TABLE = os.environ.get("INTAKE_TABLE", "")

# API Gateway REST has a ~10 MB integration payload cap. We enforce a decoded
# artifact size limit below that and reject larger artifacts with 413 rather
# than failing opaquely. Overridable via env for tuning.
MAX_ARTIFACT_BYTES = int(os.environ.get("MAX_ARTIFACT_BYTES", str(6 * 1024 * 1024)))

# Metadata field caps — defensive bounds so a caller cannot bloat the record.
_MAX_FILENAME_LEN = 512
_MAX_CONTENT_TYPE_LEN = 255
_MAX_SUBMITTER_LEN = 255

# Reused across warm invocations.
_s3_client = None
_intake_table = None

# A filename must not enable path traversal or key injection into S3.
_FILENAME_RE = re.compile(r"^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*$")

STATUS_RECEIVED = "RECEIVED"


class IntakeError(Exception):
    """A client-attributable intake failure carrying an HTTP status code."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _s3():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3")
    return _s3_client


def _table():
    global _intake_table
    if _intake_table is None:
        if not INTAKE_TABLE:
            raise RuntimeError("INTAKE_TABLE environment variable is not set")
        _intake_table = boto3.resource("dynamodb").Table(INTAKE_TABLE)
    return _intake_table


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_body(event: dict[str, Any]) -> dict[str, Any]:
    """Extract and JSON-decode the request body from an API Gateway event."""
    raw = event.get("body")
    if raw is None or raw == "":
        raise IntakeError(400, "Request body is required")

    # API Gateway may base64-encode a binary body; our contract is a JSON body,
    # so decode the transport layer first if flagged.
    if event.get("isBase64Encoded"):
        try:
            raw = base64.b64decode(raw).decode("utf-8")
        except (binascii.Error, ValueError) as exc:
            raise IntakeError(400, "Request body is not valid base64/UTF-8") from exc

    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise IntakeError(400, "Request body must be valid JSON") from exc

    if not isinstance(parsed, dict):
        raise IntakeError(400, "Request body must be a JSON object")
    return parsed


def _require_str(
    body: dict[str, Any], field: str, *, required: bool, max_len: int,
    default: str | None = None,
) -> str | None:
    value = body.get(field, default)
    if value is None or value == "":
        if required:
            raise IntakeError(400, f"Field '{field}' is required")
        return default
    if not isinstance(value, str):
        raise IntakeError(400, f"Field '{field}' must be a string")
    if len(value) > max_len:
        raise IntakeError(400, f"Field '{field}' exceeds {max_len} characters")
    return value


def _decode_artifact(body: dict[str, Any]) -> bytes:
    """Decode the base64 ``content_base64`` artifact body and size-check it."""
    encoded = body.get("content_base64")
    if not encoded or not isinstance(encoded, str):
        raise IntakeError(400, "Field 'content_base64' (base64 artifact body) is required")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise IntakeError(400, "Field 'content_base64' is not valid base64") from exc
    if len(data) == 0:
        raise IntakeError(400, "Artifact body is empty")
    if len(data) > MAX_ARTIFACT_BYTES:
        raise IntakeError(
            413,
            f"Artifact exceeds maximum size of {MAX_ARTIFACT_BYTES} bytes",
        )
    return data


def _validate_filename(filename: str) -> str:
    if not _FILENAME_RE.match(filename):
        raise IntakeError(
            400,
            "Field 'filename' may contain only [A-Za-z0-9._-] and '/' separators "
            "(no absolute paths or '..')",
        )
    if ".." in filename.split("/"):
        raise IntakeError(400, "Field 'filename' must not contain '..' segments")
    return filename


def _validate_request(body: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    """Validate the request; return (artifact_bytes, metadata)."""
    filename = _require_str(body, "filename", required=True, max_len=_MAX_FILENAME_LEN)
    _validate_filename(filename)
    content_type = _require_str(
        body, "content_type", required=False, max_len=_MAX_CONTENT_TYPE_LEN,
        default="application/octet-stream",
    )
    submitter = _require_str(
        body, "submitter", required=False, max_len=_MAX_SUBMITTER_LEN,
        default="unknown",
    )
    artifact = _decode_artifact(body)
    metadata = {
        "filename": filename,
        "content_type": content_type,
        "submitter": submitter,
    }
    return artifact, metadata


def _caller_identity(event: dict[str, Any]) -> str | None:
    """Best-effort IAM caller ARN from the API Gateway request context."""
    ctx = event.get("requestContext") or {}
    identity = ctx.get("identity") or {}
    return identity.get("userArn") or identity.get("caller")


def _persist(artifact: bytes, metadata: dict[str, Any], caller: str | None) -> dict[str, Any]:
    """Write the artifact to S3 and the intake record to DynamoDB."""
    intake_id = str(uuid.uuid4())
    received_at = _now_iso()
    sha256 = hashlib.sha256(artifact).hexdigest()
    s3_key = f"intake/{intake_id}/{metadata['filename']}"

    # 1. Persist the artifact body to S3 (durable, size-friendly).
    _s3().put_object(
        Bucket=ARTIFACT_BUCKET,
        Key=s3_key,
        Body=artifact,
        ContentType=metadata["content_type"],
        ServerSideEncryption="aws:kms",
        Metadata={
            "intake-id": intake_id,
            "sha256": sha256,
            "submitter": metadata["submitter"],
        },
    )

    # 2. Persist the queryable intake record to DynamoDB (status=RECEIVED).
    record = {
        "intake_id": intake_id,
        "status": STATUS_RECEIVED,
        "received_at": received_at,
        "filename": metadata["filename"],
        "content_type": metadata["content_type"],
        "submitter": metadata["submitter"],
        "sha256": sha256,
        "size_bytes": len(artifact),
        "s3_bucket": ARTIFACT_BUCKET,
        "s3_key": s3_key,
    }
    if caller:
        record["submitted_by_arn"] = caller
    _table().put_item(Item=record)

    return {
        "intake_id": intake_id,
        "status": STATUS_RECEIVED,
        "received_at": received_at,
        "sha256": sha256,
        "size_bytes": len(artifact),
        "s3_key": s3_key,
    }


def _response(status_code: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(payload),
    }


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Lambda entry point for ``POST /intake``."""
    request_id = getattr(context, "aws_request_id", None) or str(uuid.uuid4())

    if not ARTIFACT_BUCKET or not INTAKE_TABLE:
        logger.error("Misconfigured: ARTIFACT_BUCKET/INTAKE_TABLE not set")
        return _response(
            500,
            {"error": "Intake gateway is misconfigured", "correlation_id": request_id},
        )

    try:
        body = _parse_body(event)
        artifact, metadata = _validate_request(body)
        caller = _caller_identity(event)
        result = _persist(artifact, metadata, caller)
        logger.info(
            "intake accepted intake_id=%s sha256=%s size=%d",
            result["intake_id"], result["sha256"], result["size_bytes"],
        )
        return _response(201, result)
    except IntakeError as exc:
        logger.warning("intake rejected (%d): %s", exc.status_code, exc.message)
        return _response(
            exc.status_code,
            {"error": exc.message, "correlation_id": request_id},
        )
    except Exception:
        logger.exception("intake failed request_id=%s", request_id)
        return _response(
            500,
            {"error": "Internal error processing intake", "correlation_id": request_id},
        )
