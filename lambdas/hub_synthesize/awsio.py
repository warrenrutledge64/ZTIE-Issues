"""ZTIE Story 3.3 — thin AWS I/O seam for the Hub-side accuracy + gap_analysis
synthesizer (RD-037).

ALL boto3 lives HERE so the synthesis logic (``synthesize.py``) stays pure and
offline-unit-testable (the proven 1.2 -> 3.2 lane pattern: pure logic + a thin
boto3 seam). Nothing in this module scores accuracy, builds gaps, or makes a
synthesis/verdict decision; it only (a) reads the Hub tracking item and (b) writes
the derived synthesis result back onto the SAME item.

Unlike the 3.2 correlator, the synthesizer makes NO model call — the synthesis is
PURE deterministic post-processing of the 3.2 correlation result (RD-037) — so this
seam touches ONLY the Hub tracking DynamoDB table. There is NO Bedrock client and
NO Bedrock grant.

This runs in the HUB account (Pipeline-Hub, 641628980935). It touches ONLY the Hub
tracking DynamoDB table. It NEVER reads the Forensic S3 body / findings / trace (it
cannot and must not — RD-009); its input is already-derived, already-Hub data (the
3.2 correlation result on the tracking item). There is NO Forensic -> Hub crossing
here (RD-013 is untouched): the synthesis result never leaves the Hub.
"""

from __future__ import annotations

import logging
from typing import Any

import boto3

logger = logging.getLogger()

# Reused across warm invocations.
_ddb_table = None


def table(table_name: str):
    global _ddb_table
    if _ddb_table is None:
        _ddb_table = boto3.resource("dynamodb").Table(table_name)
    return _ddb_table


def get_item(table_name: str, intake_id: str) -> dict[str, Any] | None:
    """Read the Hub tracking item by intake_id. Returns the item dict or None."""
    return table(table_name).get_item(Key={"intake_id": intake_id}).get("Item")


def put_synthesis_result(
    table_name: str,
    *,
    intake_id: str,
    sha256: str,
    synthesis_result: dict[str, Any],
    synthesized_at: str,
    status: str,
) -> None:
    """Write the derived synthesis result back onto the EXISTING tracking record.

    Integrity-bound exactly like every other Hub write path: the update requires the
    record to already exist AND its stored ``sha256`` to equal the artifact the
    synthesis was built over (so a synthesis can only attach to the exact tracked
    artifact). It NEVER creates a record and NEVER touches the tracking ``status`` /
    verdict — the synthesis result is EVIDENCE, not a decision. It sets the derived
    ``synthesis_result`` object, a flattened ``synthesis_status`` for convenient
    dashboard/query use, and ``synthesized_at``.

    A ``ConditionalCheckFailedException`` here means the item vanished or its sha256
    changed between the read and the write (a race); the caller treats that as a
    benign no-op (a later stream event re-derives).
    """
    table(table_name).update_item(
        Key={"intake_id": intake_id},
        UpdateExpression=(
            "SET synthesis_result = :sr, synthesis_status = :ss, "
            "synthesized_at = :sa"
        ),
        ConditionExpression="attribute_exists(intake_id) AND sha256 = :sha",
        ExpressionAttributeValues={
            ":sr": synthesis_result,
            ":ss": status,
            ":sa": synthesized_at,
            ":sha": sha256,
        },
    )
