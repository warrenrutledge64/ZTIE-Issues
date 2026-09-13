"""ZTIE Story 4.6 (RD-047) — thin AWS I/O seam for the Forensic PDE-handoff pusher.

ALL boto3 lives HERE so the gate + envelope logic (``handoff.py``) stays pure and
offline-unit-testable (the proven 1.2 -> 4.5 lane pattern: pure logic + a thin
boto3 seam). Nothing in this module makes the ACCEPT decision or a verdict; it only
does the four bounded, least-privilege AWS operations the mechanism needs.

This Lambda runs in the FORENSIC account (360999005254) — the blast zone. Its four
operations, each least-privilege (RD-047):
  1. ``get_tracking_item`` — read the Hub durable tracking item by intake_id
     (CROSS-ACCOUNT ``dynamodb:GetItem`` on the Hub table; the record carries the
     recorded human ``human_decision`` + the authoritative ``sha256``). READ-only;
     it NEVER writes to the Hub table.
  2. ``compute_artifact_sha256`` + ``get_artifact_size`` — stream the raw artifact
     from the FORENSIC artifact bucket (in-account ``s3:GetObject``) and recompute
     its sha256 for the SI-7 integrity check. The raw body stays in Forensic.
  3. ``push_artifact`` — copy the artifact CROSS-ACCOUNT to the Pipeline-Sandbox
     landing bucket (``s3:PutObject`` scoped to EXACTLY one prefix, granted on the
     Sandbox bucket policy). One-directional, ZTIE-initiated. The artifact goes
     Forensic -> Sandbox DIRECTLY; it is NEVER copied through the Hub.
  4. ``send_handoff_envelope`` — cross the bounded, verdict-free outcome to the Hub
     via EXACTLY ``sqs:SendMessage`` on EXACTLY the one Hub ingest queue (the
     established RD-013 door). No other Hub access.

There is NO ``bedrock`` client and NO Bedrock grant (RD-047: no model call). There
is NO write to any Hub DATA store (only the SQS send + the cross-account S3 put).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import boto3

# Reused across warm invocations.
_ddb_resource = None
_s3_client = None
_sqs_client = None

# Bounded streaming read size for the sha256 recompute (never buffer the whole
# body in memory; the artifact bucket accepts up to ~6 MB bodies but stream anyway).
_HASH_CHUNK_BYTES = 1024 * 1024


def _ddb():
    global _ddb_resource
    if _ddb_resource is None:
        _ddb_resource = boto3.resource("dynamodb")
    return _ddb_resource


def _s3():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3")
    return _s3_client


def _sqs():
    global _sqs_client
    if _sqs_client is None:
        _sqs_client = boto3.client("sqs")
    return _sqs_client


def get_tracking_item(table_name: str, intake_id: str) -> dict[str, Any] | None:
    """Read the Hub durable tracking item by intake_id (CROSS-ACCOUNT GetItem on
    the Hub table). Returns the item dict or None. READ-only — the pusher never
    writes to the Hub table."""
    return (
        _ddb().Table(table_name).get_item(Key={"intake_id": intake_id}).get("Item")
    )


def compute_artifact_sha256_and_size(bucket: str, key: str) -> tuple[str, int]:
    """Stream the raw artifact from the Forensic artifact bucket and return its
    (lowercase hex sha256, size in bytes). Streaming (never buffers the whole body).
    In-account read; the raw body stays in Forensic."""
    obj = _s3().get_object(Bucket=bucket, Key=key)
    body = obj["Body"]
    hasher = hashlib.sha256()
    size = 0
    try:
        for chunk in body.iter_chunks(chunk_size=_HASH_CHUNK_BYTES):
            if not chunk:
                continue
            hasher.update(chunk)
            size += len(chunk)
    finally:
        body.close()
    return hasher.hexdigest(), size


def push_artifact(
    *,
    source_bucket: str,
    source_key: str,
    dest_bucket: str,
    dest_key: str,
    metadata: dict[str, str],
) -> str | None:
    """Push the artifact CROSS-ACCOUNT to the Pipeline-Sandbox landing bucket.

    Reads the object from the Forensic artifact bucket (in-account) and PutObjects
    it into the Sandbox bucket (cross-account, scoped one-prefix PutObject). The
    destination bucket is SSE-S3 (its own default encryption applies; no
    cross-account KMS grant is needed). Sets object metadata so the landing is
    verifiable. Returns the destination VersionId if the landing bucket is versioned
    (else None). One-directional, ZTIE-initiated; the artifact never transits the Hub.
    """
    obj = _s3().get_object(Bucket=source_bucket, Key=source_key)
    body = obj["Body"].read()
    resp = _s3().put_object(
        Bucket=dest_bucket,
        Key=dest_key,
        Body=body,
        Metadata=metadata,
        # Belt-and-suspenders: request SSE-S3 explicitly. The Sandbox landing bucket
        # is SSE-S3 by default; asking for it here means the put still satisfies a
        # bucket policy that requires server-side encryption without any KMS grant.
        ServerSideEncryption="AES256",
    )
    return resp.get("VersionId")


def send_handoff_envelope(queue_url: str, envelope: dict[str, Any]) -> None:
    """Send the derived handoff-outcome envelope to the Hub ingest queue.

    Tenth envelope kind on the SAME one-directional Forensic -> Hub RD-013 door the
    other envelopes use; the Hub gate routes by the unique ``handoff`` discriminator
    and applies the outcome to the tracking record (integrity-bound, never touching
    status/verdict). The pushed artifact stays in the Sandbox (RD-009); only this
    bounded, verdict-free outcome crosses to the Hub.
    """
    _sqs().send_message(QueueUrl=queue_url, MessageBody=json.dumps(envelope))
