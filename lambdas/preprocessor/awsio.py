"""ZTIE Story 1.2 — thin AWS I/O layer for the preprocessor (boto3 lives HERE).

Everything that touches AWS is isolated behind these tiny functions so the real
classifier (``classifier.py``) stays a pure, offline-unit-testable function (the
1.R lesson: pure logic + a thin boto3 seam). Nothing in this module makes a
classification decision; it only reads the Forensic S3 head bytes and sends the
derived, label-only envelope to the Hub ingest queue.
"""

from __future__ import annotations

import json
from typing import Any

import boto3

# Reused across warm invocations.
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
    """Return the S3 object's user metadata + size (for sha256 / claimed type)."""
    resp = _s3().head_object(Bucket=bucket, Key=key)
    return {
        "metadata": resp.get("Metadata", {}) or {},
        "content_length": resp.get("ContentLength", 0),
    }


def get_object_head_bytes(bucket: str, key: str, max_bytes: int) -> bytes:
    """Read only the first ``max_bytes`` of the object via a ranged GET.

    Classification only inspects the head slice; a ranged GET avoids pulling a
    whole multi-megabyte artifact into the Lambda. The raw body never leaves
    Forensic — this read happens inside the Forensic account.
    """
    resp = _s3().get_object(Bucket=bucket, Key=key, Range=f"bytes=0-{max_bytes - 1}")
    return resp["Body"].read()


def send_classification_envelope(queue_url: str, envelope: dict[str, Any]) -> None:
    """Send the derived classification envelope to the Hub ingest queue."""
    _sqs().send_message(QueueUrl=queue_url, MessageBody=json.dumps(envelope))


def send_routing_envelope(queue_url: str, envelope: dict[str, Any]) -> None:
    """Send the derived routing-decision envelope (Story 1.3) to the Hub ingest
    queue. Same one-directional Forensic -> Hub door as the classification and
    intake-tracking envelopes; the Hub gate routes by envelope kind."""
    _sqs().send_message(QueueUrl=queue_url, MessageBody=json.dumps(envelope))
