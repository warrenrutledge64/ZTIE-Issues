"""ZTIE Story 3.5 (RD-040) — thin AWS I/O seam for the Hub-side verdict step.

ALL boto3 lives HERE so the verdict-derivation logic (``verdict.py``) stays pure and
offline-unit-testable (the proven 1.2 -> 3.4 lane pattern: pure logic + a thin boto3
seam). Nothing in this module derives a verdict, maps scores, or makes any decision; it
only (a) reads the Hub tracking item and (b) writes the derived verdict result back onto
the SAME item.

RD-040 (PURE post-processing): UNLIKE the 3.2 correlator + the 3.3 scorer, and LIKE the
3.4 remediation step, this step makes NO model call — there is NO ``bedrock-runtime``
client and NO Bedrock grant. Its inputs (the 3.3 ``scoring_result`` + the 3.4
``remediation_result``) are already structured Hub-side data, so the PASS/FAIL/
INCONCLUSIVE mapping is deterministic. This seam therefore touches ONLY the Hub tracking
DynamoDB table.

This runs in the HUB account (Pipeline-Hub, 641628980935). It NEVER reads the Forensic
S3 body / findings / trace (it cannot and must not — RD-009); its input is
already-derived, already-Hub data. There is NO Forensic -> Hub crossing here (RD-013 is
untouched): the verdict result never leaves the Hub.

CRITICAL (RD-040): the verdict result is ADVISORY and is written to its OWN new fields
(``verdict_result`` + ``verdict_at``). It NEVER touches the tracking ``status``, NEVER
touches another Phase-3 field (``scoring_result`` / ``remediation_result`` /
``correlation_result`` / ``combined_event`` stay exactly as they are), and NEVER writes
the human's accept/reject selection — the recommended_verdict is a recommendation, and
the human decision is written later at the Phase-4 gate.
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


def put_verdict_result(
    table_name: str,
    *,
    intake_id: str,
    sha256: str,
    verdict_result: dict[str, Any],
    recommended_at: str,
) -> None:
    """Write the derived ADVISORY verdict result back onto the EXISTING tracking record.

    Integrity-bound exactly like every other Hub write path: the update requires the
    record to already exist AND its stored ``sha256`` to equal the artifact the
    recommendation was derived over. It NEVER creates a record and NEVER touches the
    tracking ``status`` / any other Phase-3 field — the recommended_verdict is an
    ADVISORY recommendation, not a decision, so it lives in its OWN fields
    (``verdict_result`` + ``verdict_at``). It never writes the human's selection.

    A ``ConditionalCheckFailedException`` here means the item vanished or its sha256
    changed between the read and the write (a race); the caller treats that as a benign
    no-op (a later stream event re-derives).
    """
    table(table_name).update_item(
        Key={"intake_id": intake_id},
        UpdateExpression="SET verdict_result = :vr, verdict_at = :va",
        ConditionExpression="attribute_exists(intake_id) AND sha256 = :sha",
        ExpressionAttributeValues={
            ":vr": verdict_result,
            ":va": recommended_at,
            ":sha": sha256,
        },
    )
