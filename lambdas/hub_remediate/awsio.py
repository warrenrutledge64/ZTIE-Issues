"""ZTIE Story 3.4 (RD-039) — thin AWS I/O seam for the Hub-side findings +
prioritized-remediations step.

ALL boto3 lives HERE so the assessment logic (``remediate.py``) stays pure and
offline-unit-testable (the proven 1.2 -> 3.3 lane pattern: pure logic + a thin boto3
seam). Nothing in this module builds findings, ranks remediations, or makes any
scoring/verdict decision; it only (a) reads the Hub tracking item and (b) writes the
derived remediation result back onto the SAME item.

RD-039 (PURE post-processing): UNLIKE the 3.2 correlator + the 3.3 scorer, this step
makes NO model call — there is NO ``bedrock-runtime`` client and NO Bedrock grant. Its
inputs (the 3.3 ``scoring_result`` + the 3.2 ``correlation_result``) are already
structured Hub-side data, so building the findings view + ranking the remediations is
deterministic. This seam therefore touches ONLY the Hub tracking DynamoDB table.

This runs in the HUB account (Pipeline-Hub, 641628980935). It NEVER reads the Forensic
S3 body / findings / trace (it cannot and must not — RD-009); its input is
already-derived, already-Hub data. There is NO Forensic -> Hub crossing here (RD-013 is
untouched): the remediation result never leaves the Hub.
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


def put_remediation_result(
    table_name: str,
    *,
    intake_id: str,
    sha256: str,
    remediation_result: dict[str, Any],
    assessed_at: str,
) -> None:
    """Write the derived remediation result back onto the EXISTING tracking record.

    Integrity-bound exactly like every other Hub write path: the update requires the
    record to already exist AND its stored ``sha256`` to equal the artifact the
    assessment was built over. It NEVER creates a record and NEVER touches the tracking
    ``status`` / verdict — the findings + remediations are EVIDENCE + a to-do list, not
    a decision. It sets the derived ``remediation_result`` object and ``assessed_at``.

    A ``ConditionalCheckFailedException`` here means the item vanished or its sha256
    changed between the read and the write (a race); the caller treats that as a benign
    no-op (a later stream event re-derives).
    """
    table(table_name).update_item(
        Key={"intake_id": intake_id},
        UpdateExpression="SET remediation_result = :rr, assessed_at = :aa",
        ConditionExpression="attribute_exists(intake_id) AND sha256 = :sha",
        ExpressionAttributeValues={
            ":rr": remediation_result,
            ":aa": assessed_at,
            ":sha": sha256,
        },
    )
