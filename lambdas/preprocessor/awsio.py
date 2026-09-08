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
_sfn_client = None


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


def _sfn():
    global _sfn_client
    if _sfn_client is None:
        _sfn_client = boto3.client("stepfunctions")
    return _sfn_client


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



def send_reject_envelope(queue_url: str, envelope: dict[str, Any]) -> None:
    """Send the derived safe-reject outcome envelope (Story 1.4) to the Hub
    ingest queue. Fourth envelope kind on the same one-directional Forensic -> Hub
    door; the Hub gate routes by envelope kind and applies the terminal outcome."""
    _sqs().send_message(QueueUrl=queue_url, MessageBody=json.dumps(envelope))


def send_static_scan_job(queue_url: str, job: dict[str, Any]) -> None:
    """Enqueue a static-scan JOB onto the Forensic static-scan work queue (Story
    2.1) when the routing decision names the static_analysis lane. This is an
    INTRA-FORENSIC hand-off (Forensic preprocessor -> Forensic static-scan lane),
    NOT a Forensic -> Hub crossing: the job carries the artifact's Forensic S3
    coordinates so the static-scan Lambda can read the raw body (which stays in
    Forensic). The static-scan lane later crosses only a derived summary to the Hub.
    """
    _sqs().send_message(QueueUrl=queue_url, MessageBody=json.dumps(job))



def send_detonation_job(queue_url: str, job: dict[str, Any]) -> None:
    """Enqueue a detonation JOB onto the Forensic detonation work queue (Story
    2.3) when the routing decision names the dynamic_detonation lane. This is an
    INTRA-FORENSIC hand-off (Forensic preprocessor -> Forensic detonation lane),
    NOT a Forensic -> Hub crossing: the job carries the artifact's Forensic S3
    coordinates so the detonation Lambda can pull the raw body (which stays in
    Forensic and is executed only on the ephemeral host). The detonation lane later
    crosses only a derived, verdict-free run OUTCOME to the Hub.
    """
    _sqs().send_message(QueueUrl=queue_url, MessageBody=json.dumps(job))


def start_inspection_orchestration(
    state_machine_arn: str, execution_name: str, orchestration_input: dict[str, Any]
) -> str:
    """Start ONE Step Functions execution (Story 2.6 CONCURRENT FORK, RD-029).

    When the routing decision names the parallel inspection lanes, the preprocessor
    starts ONE Standard state-machine execution that fans the artifact out to BOTH
    lanes CONCURRENTLY (static 2.1/2.2 + dynamic 2.3) and joins on both-complete —
    replacing the two disconnected intra-Forensic enqueues. This is still an
    INTRA-FORENSIC hand-off (both the state machine and the lanes it drives live in
    Forensic; the input carries only the artifact's Forensic S3 coordinates) — NOT a
    Forensic -> Hub crossing. Only the collector's bounded, verdict-free COLLECTED
    record later crosses to the Hub via the RD-013 gate.

    ``execution_name`` is DETERMINISTIC (derived from intake_id) so SQS
    at-least-once redelivery of the same S3 event cannot start a duplicate fork:
    Step Functions rejects a second StartExecution with the same name for the same
    state machine (idempotent). The caller treats that specific rejection as a
    benign no-op. Returns the execution ARN.
    """
    resp = _sfn().start_execution(
        stateMachineArn=state_machine_arn,
        name=execution_name,
        input=json.dumps(orchestration_input),
    )
    return resp["executionArn"]
