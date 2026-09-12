"""ZTIE Story 3.1 — thin AWS I/O seam for the Hub-side combined-event normalizer.

ALL boto3 lives HERE so the normalization logic (``combine.py``) stays pure and
offline-unit-testable (the proven 1.2 -> 2.6 lane pattern: pure logic + a thin boto3
seam). Nothing in this module makes a normalization decision or a verdict; it only
reads the Hub tracking item and writes the derived combined event back onto the SAME
item.

This runs in the HUB account (Pipeline-Hub, 641628980935). It touches ONLY the Hub
tracking DynamoDB table — it reads the already-Hub-side derived inputs and writes
the combined event back. It NEVER reads the Forensic S3 body / findings / trace (it
cannot and must not — RD-009); the inputs it reads are already-derived, already-Hub
data. There is NO Forensic -> Hub crossing here (RD-013 is untouched): the combined
event never leaves the Hub.
"""

from __future__ import annotations

from typing import Any

import boto3

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


def put_combined_event(
    table_name: str,
    *,
    intake_id: str,
    sha256: str,
    combined_event: dict[str, Any],
    combined_at: str,
    complete: bool,
) -> None:
    """Write the derived combined event back onto the EXISTING tracking record.

    Integrity-bound exactly like every other Hub apply path: the update requires
    the record to already exist AND its stored ``sha256`` to equal the artifact the
    combined event was built over (so a combined event can only attach to the exact
    tracked artifact). It NEVER creates a record and NEVER touches ``status`` /
    verdict — the combined event is EVIDENCE, not a decision. It sets the derived
    ``combined_event`` object, a flattened ``combined_complete`` for convenient
    dashboard/query use, and ``combined_at``.

    A ``ConditionalCheckFailedException`` here means the item vanished or its sha256
    changed between the read and the write (a race); the caller treats that as a
    benign no-op (a later stream event re-derives).
    """
    table(table_name).update_item(
        Key={"intake_id": intake_id},
        UpdateExpression=(
            "SET combined_event = :ce, combined_complete = :cc, combined_at = :ca"
        ),
        ConditionExpression="attribute_exists(intake_id) AND sha256 = :sha",
        ExpressionAttributeValues={
            ":ce": combined_event,
            ":cc": complete,
            ":ca": combined_at,
            ":sha": sha256,
        },
    )
