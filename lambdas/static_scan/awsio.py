"""ZTIE Story 2.1 — thin AWS I/O layer for the static-scan lane (boto3 lives HERE).

Everything that touches AWS is isolated behind these tiny functions so the
normalization logic (``normalize.py``) and tool plan (``toolplan.py``) stay pure and
offline-unit-testable. Nothing here makes a scan decision; it only:

  * reads the raw artifact body from the Forensic artifact S3 bucket to a local
    path (the read + the file stay inside Forensic — the blast zone),
  * reads the object's user metadata (intake-id / sha256),
  * writes the derived normalized findings document to the Forensic artifact bucket
    under a ``findings/`` prefix (RD-009 — the full document STAYS in Forensic),
  * sends the derived, bounded SUMMARY envelope to the Hub ingest queue (the same
    one-directional RD-013 door the other envelopes use).

No mocks in the execution path: real S3 + SQS. moto is used only in (live) tests.
"""

from __future__ import annotations

import json
from typing import Any

import boto3

_s3_client = None
_sqs_client = None


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


def head_object_metadata(bucket: str, key: str) -> dict[str, Any]:
    """Return the artifact object's user metadata + size (intake-id / sha256)."""
    resp = _s3().head_object(Bucket=bucket, Key=key)
    return {
        "metadata": resp.get("Metadata", {}) or {},
        "content_length": resp.get("ContentLength", 0),
    }


def download_artifact(bucket: str, key: str, dest_path: str) -> None:
    """Download the raw artifact body to a local path for static inspection.

    The file lands in the Forensic Lambda's ephemeral local storage and is scanned
    there; it never leaves Forensic. The scanners read it as data — it is never
    executed (NON-EXECUTING, RD-001).
    """
    _s3().download_file(bucket, key, dest_path)


def put_findings_document(bucket: str, key: str, document: dict[str, Any]) -> None:
    """Write the full normalized findings document to Forensic S3 (findings/).

    RD-009: the full document may echo artifact content, so it stays in Forensic.
    Only the derived summary crosses to the Hub. Written KMS-encrypted as inert
    JSON; it is never executed.
    """
    _s3().put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(document).encode("utf-8"),
        ContentType="application/json",
        ServerSideEncryption="aws:kms",
    )


def send_summary_envelope(queue_url: str, envelope: dict[str, Any]) -> None:
    """Send the derived static-scan SUMMARY envelope to the Hub ingest queue.

    Fifth envelope kind on the same one-directional Forensic -> Hub door; the Hub
    gate routes by envelope kind and applies the summary to the tracking record.
    """
    _sqs().send_message(QueueUrl=queue_url, MessageBody=json.dumps(envelope))
