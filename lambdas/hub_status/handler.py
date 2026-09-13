"""ZTIE Story 4.1 (RD-041) — Hub-side status-retrieval orchestrator Lambda.

The Phase-4 opener. For ONE ``intake_id`` it READS the current Hub tracking item and
assembles a bounded, DERIVED per-intake STATUS READ-MODEL (``status.contract.v1``): the
intake identity + the furthest pipeline stage reached + per-stage presence for 3.1-3.5 +
the three 3.3 scores (echoed context) + a bounded 3.4 findings/remediation SUMMARY + the
3.5 ADVISORY ``recommended_verdict`` surfaced alongside the (pending) human ``decision``.
It returns that read-model as its response; the Phase-4 dashboard payload (4.2) + the
per-execution report (4.5) — and, through those, the human gate + routing (4.4/4.6/4.7) —
consume it.

RD-041 CONTRACT-FIRST decision: this is an ON-DEMAND READ/TRANSFORM behind an
orchestrator Lambda, NOT a durable stored record and NOT a stream consumer. It adds NO
durable tracking field, does NOT hang off the tracking-table stream, and makes NO model
call. Its inputs (the Phase-3 derived fields on the Hub item) are already structured, so
assembling the view is deterministic; a Nova Pro call would only add cost /
non-determinism. So — like the 3.4 remediation step + the 3.5 verdict step, and UNLIKE
the 3.2 correlator + the 3.3 scorer — this Lambda has NO Bedrock client and NO Bedrock
grant. Its assembly logic is PURE stdlib (``status_model.py``); the only AWS call (a
single DynamoDB ``get_item``) is in the thin ``awsio.py`` seam.

Invocation: on demand, per intake (direct Lambda invoke). The event carries an
``intake_id`` (accepted at the top level, or nested under ``pathParameters`` /
``queryStringParameters`` so a future API Gateway GET ``/status/{intake_id}`` — deferred
to 4.2 — needs no handler change). It is NOT triggered by the tracking-table stream (this
is a read step, not a derive-and-write step), so there is no fingerprint guard / no
batch-item-failure protocol here.

Design invariants (RD-009 / RD-012 / RD-013 / RD-040 / RD-041):
  * READ/TRANSFORM ONLY. It NEVER writes: no derived field is persisted, the tracking
    ``status`` is never touched, no Phase-3 field is touched. The read-model is a
    response, not a record.
  * NO RE-DERIVATION, NO MODEL CALL. It echoes the already-derived Hub-side fields; it
    does NOT re-normalize / re-correlate / re-score / rebuild findings / re-derive the
    verdict.
  * ADVISORY, NEVER ACTED UPON (RD-040). It surfaces the 3.5 recommendation + an explicit
    ``advisory: true`` flag alongside ``decision: pending``; it NEVER routes / promotes /
    enforces, NEVER presents the recommendation as an effective decision, and NEVER
    reports a made human decision.
  * HUB-SIDE ONLY (RD-009). Its input is already-Hub derived data; it NEVER reads the
    Forensic raw body / findings / trace and never crosses the RD-013 gate. No durable
    store is added anywhere (RD-012 / RD-041).
  * PURE logic + thin seam. All assembly is in ``status_model.py`` (pure); the single
    DynamoDB read is in ``awsio.py``.
"""

from __future__ import annotations

import datetime as _dt
import logging
import os
from typing import Any

import status_model

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# --- Configuration (from environment; set by the CDK stack) -----------------

TRACKING_TABLE = os.environ.get("TRACKING_TABLE", "")
# The status read-model pins its OWN version (RD-041). Currently "1.0".
STATUS_CONTRACT_VERSION = os.environ.get("STATUS_CONTRACT_VERSION", "1.0")

# UUIDv4 shape the tracking key must match (mirror the contract pattern) so a malformed
# or injected key is rejected cheaply before any AWS call.
_UUID4 = (
    "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
import re as _re

_UUID4_RE = _re.compile(_UUID4)


class StatusError(Exception):
    """A bounded, caller-facing error (bad request / not found). Carries an HTTP-ish
    ``code`` so a future API front (4.2) can map it without re-parsing the message."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _extract_intake_id(event: dict[str, Any]) -> str | None:
    """Pull the intake_id from a direct-invoke event OR an API-Gateway-shaped event
    (pathParameters / queryStringParameters), so the same handler serves both a direct
    invoke now and a GET /status/{intake_id} later (deferred to 4.2). Pure."""
    if not isinstance(event, dict):
        return None
    raw = event.get("intake_id")
    if isinstance(raw, str) and raw:
        return raw
    for container_key in ("pathParameters", "queryStringParameters"):
        container = event.get(container_key)
        if isinstance(container, dict):
            val = container.get("intake_id")
            if isinstance(val, str) and val:
                return val
    return None


def get_status(intake_id: str) -> dict[str, Any]:
    """Read the tracking item for ``intake_id`` and assemble the status read-model.

    Raises ``StatusError(404, ...)`` when no record exists, ``StatusError(422, ...)``
    when the record is missing its integrity key (a malformed item that cannot be keyed).
    """
    import awsio  # local import so tests can stub the seam before import

    item = awsio.get_item(TRACKING_TABLE, intake_id)
    if not item:
        raise StatusError(404, f"no tracking record for intake_id={intake_id}")
    key = item.get("intake_id")
    sha256 = item.get("sha256")
    if not isinstance(key, str) or not isinstance(sha256, str):
        raise StatusError(
            422, f"tracking record for intake_id={intake_id} is missing its integrity key"
        )

    status = status_model.build_status(
        item,
        intake_id=key,
        sha256=sha256,
        assembled_at=_now_iso(),
        contract_version=STATUS_CONTRACT_VERSION,
    )
    logger.info(
        "intake_id=%s status assembled (overall_stage=%s, recommendation_status=%s)",
        intake_id,
        status.get("overall_stage"),
        status.get("recommendation", {}).get("status"),
    )
    return status


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """On-demand entry point. Reads ``intake_id`` from the event, assembles the status
    read-model, and returns it. On a bad request / not-found it returns a bounded error
    envelope (never raises to the caller) so a direct invoke or a future API front gets a
    clean, typed response."""
    if not TRACKING_TABLE:
        logger.error("Misconfigured: TRACKING_TABLE not set")
        raise RuntimeError("Hub status orchestrator is misconfigured")

    intake_id = _extract_intake_id(event)
    if not intake_id or not _UUID4_RE.match(intake_id):
        logger.info("bad request: missing or malformed intake_id")
        return {"error": {"code": 400, "message": "missing or malformed intake_id"}}

    try:
        return get_status(intake_id)
    except StatusError as exc:
        logger.info("intake_id=%s status error %s: %s", intake_id, exc.code, exc.message)
        return {"error": {"code": exc.code, "message": exc.message}}
