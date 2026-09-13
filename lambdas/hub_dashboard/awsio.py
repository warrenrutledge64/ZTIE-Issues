"""ZTIE Story 4.2 (RD-042) — thin AWS I/O seam for the Hub-side dashboard orchestrator.

ALL boto3 lives HERE so the dashboard-payload assembly (``dashboard.py``) stays pure and
offline-unit-testable (the proven 1.2 -> 4.1 lane pattern: pure logic + a thin boto3
seam). Nothing in this module assembles, transforms, or decides anything; it only READS
Hub tracking data — one item for the per-intake view, or a bounded, newest-first GSI page
for the fleet view.

RD-042 (READ/transform, on-demand): LIKE the 4.1 status step + UNLIKE the Phase-3 steps,
this step makes NO model call (NO ``bedrock-runtime`` client, NO Bedrock grant) and does
NOT WRITE anything (the dashboard payload is an on-demand derived response, not a durable
stored record). So this seam is READ-ONLY: a single ``get_item`` (per-intake view) and a
bounded ``query`` on the ``status-received_at-index`` GSI, newest-first, page-limited (the
fleet view). There is NO ``put_*``/``update_*``/``delete_*`` here by design (RD-042); the
fleet read uses ``Query`` on the GSI (NEVER a full ``Scan``).

This runs in the HUB account (Pipeline-Hub, 641628980935). It NEVER reads the Forensic S3
body / findings / trace (it cannot and must not — RD-009); its input is already-derived,
already-Hub data on the tracking item(s). There is NO Forensic -> Hub crossing here
(RD-013 is untouched): the dashboard payload never leaves the Hub except as this Lambda's
response to a Hub-side caller.
"""

from __future__ import annotations

from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

# The GSI that lists tracking records by status, sorted by received_at (see
# ZtieHubTrackingStack). Querying it newest-first avoids a full-table Scan.
GSI_NAME = "status-received_at-index"

# The lifecycle statuses a tracking record moves through. The fleet view queries each
# partition (the GSI is keyed by `status`) newest-first and merges, so a recent-intakes
# list spans all statuses without a Scan. Kept small + explicit.
KNOWN_STATUSES = ("RECEIVED", "CLASSIFIED", "PROCESSING", "COMPLETE")

# Reused across warm invocations.
_ddb_table = None


def table(table_name: str):
    global _ddb_table
    if _ddb_table is None:
        _ddb_table = boto3.resource("dynamodb").Table(table_name)
    return _ddb_table


def get_item(table_name: str, intake_id: str) -> dict[str, Any] | None:
    """Read one Hub tracking item by intake_id. Returns the item dict or None. READ-only
    (RD-042: no write path exists by design)."""
    return table(table_name).get_item(Key={"intake_id": intake_id}).get("Item")


def recent_items(
    table_name: str,
    *,
    limit: int,
    statuses: tuple[str, ...] = KNOWN_STATUSES,
) -> tuple[list[dict[str, Any]], bool]:
    """Read a bounded, newest-first page of recent tracking items via the GSI (NEVER a
    Scan). Queries each known status partition newest-first (ScanIndexForward=False),
    merges by received_at descending, and returns the top ``limit`` + a ``more_available``
    flag (True iff any partition had more than we took, so the payload can mark the list
    truncated). READ-only (RD-042)."""
    tbl = table(table_name)
    merged: list[dict[str, Any]] = []
    more_available = False
    # Pull up to `limit` from each partition; the merge below keeps only the newest
    # `limit` overall, so this bounds the read without a Scan.
    for status in statuses:
        resp = tbl.query(
            IndexName=GSI_NAME,
            KeyConditionExpression=Key("status").eq(status),
            ScanIndexForward=False,  # newest received_at first
            Limit=limit,
        )
        page = resp.get("Items", []) or []
        merged.extend(page)
        # A LastEvaluatedKey means this partition had more rows than we pulled.
        if resp.get("LastEvaluatedKey"):
            more_available = True

    # Newest-first overall. received_at is an ISO-8601 Z string, so lexical sort == time
    # sort. Missing received_at sorts last (empty string).
    merged.sort(key=lambda it: it.get("received_at") or "", reverse=True)
    if len(merged) > limit:
        more_available = True
    return merged[:limit], more_available
