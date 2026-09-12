"""ZTIE Story 2.6 — thin AWS I/O seam for the collector (join) Lambda.

ALL boto3 lives HERE so the join logic (``collect.py``) stays pure and
offline-unit-testable (the proven 1.2 -> 2.3 lane pattern: pure logic + a thin boto3
seam). Nothing in this module makes a join decision or a verdict; it only sends the
derived, bounded COLLECTED envelope to the one Hub ingest queue.

The collector is invoked as the TERMINAL join task of the Story 2.6 Step Functions
Parallel state (a direct task invoke, not an SQS consumer), receives the two branch
results, joins them into ONE bounded collected record (in ``collect.py``), and
crosses it to the Hub via EXACTLY ``sqs:SendMessage`` on EXACTLY the one Hub ingest
queue (least-privilege, one-directional, RD-013). No other Hub access.
"""

from __future__ import annotations

import json
from typing import Any

import boto3

# Reused across warm invocations.
_sqs_client = None


def _sqs():
    global _sqs_client
    if _sqs_client is None:
        _sqs_client = boto3.client("sqs")
    return _sqs_client


def send_collected_envelope(queue_url: str, envelope: dict[str, Any]) -> None:
    """Send the derived collected-record envelope to the Hub ingest queue.

    Seventh envelope kind on the same one-directional Forensic -> Hub door the other
    envelopes use; the Hub gate routes by envelope kind (the unique ``collected``
    discriminator) and applies the joined record to the tracking record. The full
    per-lane detail stays in Forensic (RD-009); only this bounded, verdict-free
    roll-up crosses.
    """
    _sqs().send_message(QueueUrl=queue_url, MessageBody=json.dumps(envelope))
