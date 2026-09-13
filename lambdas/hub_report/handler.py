"""ZTIE Story 4.5 (RD-045) — Hub-side per-execution report orchestrator Lambda.

The Phase-4 PER-EXECUTION REPORT. On demand, by ``intake_id``, it READS the current Hub
tracking item and assembles a bounded, DERIVED per-intake REPORT (``report.contract.v1``)
in three audience tiers (Executive / Security / Developer) — reusing the Story 4.1 status
read-model for the executive core — and returns BOTH the structured payload AND a
self-contained HTML render (print-to-PDF for "PDF for humans").

  * ``{"intake_id": "<uuid>"}`` (or ``{"intake_id": "<uuid>", "format": "html"|"json"|"both"}``)
    -> the report for that intake.

RD-045 CONTRACT-FIRST decision (mirrors RD-041 / RD-042): this is an ON-DEMAND
READ/TRANSFORM behind an orchestrator Lambda, NOT a durable stored record and NOT a stream
consumer. It adds NO durable tracking field, does NOT hang off the tracking-table stream,
and makes NO model call. Its inputs (the Phase-3 derived fields on the Hub item) are
already structured, so assembling the report is deterministic; it re-groups + bounds them
into three tiers and renders HTML. So — like the 4.1 status step + the 4.2 dashboard step
— this Lambda has NO Bedrock client and NO Bedrock grant. Its assembly + render logic is
PURE stdlib (``report.py`` + the vendored ``status_model.py``); the only AWS call (a
DynamoDB ``get_item``) is in the thin READ-only ``awsio.py`` seam.

Invocation: on demand (direct Lambda invoke). The event carries ``intake_id`` (+ optional
``format``), at the top level OR nested under ``pathParameters`` / ``queryStringParameters``
so a future API Gateway front (GET ``/report/{intake_id}``) needs no handler change. It is
NOT triggered by the tracking-table stream (a read step, not a derive-and-write step).

Design invariants (RD-009 / RD-012 / RD-013 / RD-040 / RD-045):
  * READ/TRANSFORM ONLY. It NEVER writes: no derived field is persisted, the tracking
    ``status`` is never touched, no Phase-3 field is touched. The report is a response,
    not a record.
  * NO RE-DERIVATION, NO MODEL CALL. It echoes + bounds + re-groups the already-derived
    Hub-side fields; it does NOT re-normalize / re-correlate / re-score / rebuild findings
    / re-derive the verdict.
  * ADVISORY, NEVER ACTED UPON (RD-040). The executive tier surfaces the 3.5
    recommendation + an explicit ``advisory: true`` flag alongside ``decision: pending``;
    it NEVER routes / promotes / enforces, NEVER presents the recommendation as an
    effective decision, and NEVER writes a verdict onto any record.
  * HONEST + BOUNDED. Raw-only detail (MITRE IDs / Sigma / file-line) is an explicit
    ``not_carried_on_hub`` placeholder, never fabricated (RD-013). The HTML render escapes
    every derived value.
  * HUB-SIDE ONLY (RD-009). Its input is already-Hub derived data; it NEVER reads the
    Forensic raw body / findings / trace and never crosses the RD-013 gate. No durable
    store is added anywhere (RD-012 / RD-045).
"""

from __future__ import annotations

import datetime as _dt
import logging
import os
import re as _re
from typing import Any

import report

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# --- Configuration (from environment; set by the CDK stack) -----------------

TRACKING_TABLE = os.environ.get("TRACKING_TABLE", "")
# The report payload pins its OWN version (RD-045). Currently "1.0".
REPORT_CONTRACT_VERSION = os.environ.get("REPORT_CONTRACT_VERSION", "1.0")
# The 4.1 status read-model version the executive core is assembled under. Kept in
# lockstep with the hub_status Lambda's STATUS_CONTRACT_VERSION.
STATUS_CONTRACT_VERSION = os.environ.get("STATUS_CONTRACT_VERSION", "1.0")

_UUID4_RE = _re.compile(
    "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)

_FORMATS = ("json", "html", "both")


class ReportError(Exception):
    """A bounded, caller-facing error (bad request / not found). Carries an HTTP-ish
    ``code`` so a future API front can map it without re-parsing the message."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _get_param(event: dict[str, Any], key: str) -> Any:
    """Pull a param from a direct-invoke event OR an API-Gateway-shaped event
    (pathParameters / queryStringParameters), so the same handler serves both a direct
    invoke now and a GET front later. Pure."""
    if not isinstance(event, dict):
        return None
    if key in event and event[key] not in (None, ""):
        return event[key]
    for container_key in ("pathParameters", "queryStringParameters"):
        container = event.get(container_key)
        if isinstance(container, dict):
            val = container.get(key)
            if val not in (None, ""):
                return val
    return None


def _resolve_format(event: dict[str, Any]) -> str:
    """Pick the output format: ``json`` (payload only), ``html`` (rendered document only),
    or ``both`` (default — payload + html). Tolerant: a bad value falls back to ``both``.
    Pure."""
    raw = _get_param(event, "format")
    if isinstance(raw, str) and raw.strip().lower() in _FORMATS:
        return raw.strip().lower()
    return "both"


def build_report_response(intake_id: str, fmt: str) -> dict[str, Any]:
    """Read the tracking item for ``intake_id`` and assemble the report response. Raises
    ``ReportError(404)`` when no record exists, ``ReportError(422)`` when the record is
    missing its integrity key. READ-only."""
    import awsio  # local import so tests can stub the seam before import

    item = awsio.get_item(TRACKING_TABLE, intake_id)
    if not item:
        raise ReportError(404, f"no tracking record for intake_id={intake_id}")
    key = item.get("intake_id")
    sha256 = item.get("sha256")
    if not isinstance(key, str) or not isinstance(sha256, str):
        raise ReportError(
            422, f"tracking record for intake_id={intake_id} is missing its integrity key"
        )

    payload = report.build_report(
        item,
        intake_id=key,
        sha256=sha256,
        assembled_at=_now_iso(),
        contract_version=REPORT_CONTRACT_VERSION,
        status_contract_version=STATUS_CONTRACT_VERSION,
    )

    response: dict[str, Any] = {}
    if fmt in ("json", "both"):
        response["report"] = payload
    if fmt in ("html", "both"):
        response["html"] = report.render_html(payload)

    logger.info(
        "intake_id=%s report assembled (stage=%s, security=%s, developer=%s, format=%s)",
        intake_id,
        payload["executive"].get("overall_stage"),
        payload["security"].get("data_status"),
        payload["developer"].get("data_status"),
        fmt,
    )
    return response


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """On-demand entry point. Resolves intake_id + format from the event, assembles the
    report, and returns it. On a bad request / not-found it returns a bounded error
    envelope (never raises to the caller) so a direct invoke or a future API front gets a
    clean, typed response."""
    if not TRACKING_TABLE:
        logger.error("Misconfigured: TRACKING_TABLE not set")
        raise RuntimeError("Hub report orchestrator is misconfigured")

    event = event if isinstance(event, dict) else {}
    intake_id = _get_param(event, "intake_id")
    if not isinstance(intake_id, str) or not _UUID4_RE.match(intake_id):
        logger.info("bad request: missing or malformed intake_id")
        return {"error": {"code": 400, "message": "missing or malformed intake_id"}}

    try:
        return build_report_response(intake_id, _resolve_format(event))
    except ReportError as exc:
        logger.info("report error %s: %s", exc.code, exc.message)
        return {"error": {"code": exc.code, "message": exc.message}}
