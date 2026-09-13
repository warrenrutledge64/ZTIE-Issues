"""ZTIE Story 4.1 (RD-041) — thin AWS I/O seam for the Hub-side status orchestrator.

ALL boto3 lives HERE so the status read-model assembly (``status_model.py``) stays pure
and offline-unit-testable (the proven 1.2 -> 3.5 lane pattern: pure logic + a thin boto3
seam). Nothing in this module assembles, transforms, or decides anything; it only READS
the Hub tracking item for one intake.

RD-041 (READ/transform, on-demand): UNLIKE the 3.2 correlator + the 3.3 scorer, and LIKE
the 3.4 remediation step + the 3.5 verdict step, this step makes NO model call — there is
NO ``bedrock-runtime`` client and NO Bedrock grant. And UNLIKE every Phase-3 step, it
does NOT WRITE anything: the status read-model is an on-demand derived response, not a
durable stored record, so this seam is READ-ONLY (a single ``get_item``). There is no
``put_*`` here by design (RD-041).

This runs in the HUB account (Pipeline-Hub, 641628980935). It NEVER reads the Forensic
S3 body / findings / trace (it cannot and must not — RD-009); its input is
already-derived, already-Hub data on the tracking item. There is NO Forensic -> Hub
crossing here (RD-013 is untouched): the status view never leaves the Hub except as this
Lambda's response to a Hub-side caller.
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
    """Read the Hub tracking item by intake_id. Returns the item dict or None. The ONLY
    AWS call this step makes (RD-041: READ-only; no write path exists by design)."""
    return table(table_name).get_item(Key={"intake_id": intake_id}).get("Item")
