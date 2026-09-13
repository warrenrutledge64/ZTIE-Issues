"""ZTIE Story 4.5 (RD-045) — thin AWS I/O seam for the Hub-side report orchestrator.

ALL boto3 lives HERE so the report assembly (``report.py``) stays pure and
offline-unit-testable (the proven 1.2 -> 4.2 lane pattern: pure logic + a thin boto3
seam). Nothing in this module assembles, transforms, or decides anything; it only READS
one Hub tracking item by intake_id.

RD-045 (READ/transform, on-demand): LIKE the 4.1 status + 4.2 dashboard steps + UNLIKE the
Phase-3 steps, this step makes NO model call (NO ``bedrock-runtime`` client, NO Bedrock
grant) and does NOT WRITE anything (the report is an on-demand derived response, not a
durable stored record). So this seam is READ-ONLY: a single ``get_item``. There is NO
``put_*``/``update_*``/``delete_*`` here by design (RD-045), and no ``query``/``scan`` (the
report is per-intake).

This runs in the HUB account (Pipeline-Hub, 641628980935). It NEVER reads the Forensic S3
body / findings / trace (it cannot and must not — RD-009); its input is already-derived,
already-Hub data on the tracking item. There is NO Forensic -> Hub crossing here (RD-013 is
untouched): the report never leaves the Hub except as this Lambda's response to a Hub-side
caller.
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
    """Read one Hub tracking item by intake_id. Returns the item dict or None. READ-only
    (RD-045: no write path exists by design)."""
    return table(table_name).get_item(Key={"intake_id": intake_id}).get("Item")
