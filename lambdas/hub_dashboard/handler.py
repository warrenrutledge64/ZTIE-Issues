"""ZTIE Story 4.2 (RD-042) — Hub-side dashboard-payload orchestrator Lambda.

The Phase-4 DATA LAYER. On demand it assembles the comprehensive DASHBOARD JSON PAYLOAD
(``dashboard.contract.v1``) the real-time dashboard (4.3 render) consumes, in one of two
shapes discriminated by the request:

  * ``{"view": "intake", "intake_id": "<uuid>"}`` (or a bare ``{"intake_id": "<uuid>"}``)
    -> PER-INTAKE DETAIL: it READS the current Hub tracking item and — by REUSING the
    Story 4.1 status read-model for the core (``status_model.build_status`` via
    ``dashboard.build_intake_view``) — returns the read-model + a normalized ``threat``
    color band + an ``action`` block for the human APPROVE/REJECT control.
  * ``{"view": "fleet"}`` (or an empty event) -> FLEET/LIST: it READS a bounded,
    newest-first page of recent tracking items from the ``status-received_at-index`` GSI
    (NO full scan) and returns a compact row per intake + a ``metrics`` roll-up
    (tracking-native counts + stubbed operational health).

RD-042 CONTRACT-FIRST decision (mirrors RD-041): this is an ON-DEMAND READ/TRANSFORM
behind an orchestrator Lambda, NOT a durable stored record and NOT a stream consumer. It
adds NO durable tracking field, does NOT hang off the tracking-table stream, and makes NO
model call. Its inputs (the Phase-3 derived fields on the Hub item(s)) are already
structured, so assembling the payload is deterministic; the ONLY new derivation is the
display ``threat_tier`` (a color band, never a verdict). So — like the 4.1 status step,
the 3.4 remediation step + the 3.5 verdict step — this Lambda has NO Bedrock client and NO
Bedrock grant. Its assembly logic is PURE stdlib (``dashboard.py`` + the vendored
``status_model.py``); the only AWS calls (a DynamoDB ``get_item`` / a bounded GSI
``query``) are in the thin READ-only ``awsio.py`` seam.

Invocation: on demand (direct Lambda invoke). The event carries ``view`` +
(for the intake view) ``intake_id`` + (for the fleet view) an optional ``limit``. Each is
accepted at the top level, or nested under ``pathParameters`` / ``queryStringParameters``
so a future API Gateway front (GET ``/status/{intake_id}`` + a ``/dashboard`` list
endpoint) needs no handler change (the HTTP front is deferred to a later story). It is NOT
triggered by the tracking-table stream (a read step, not a derive-and-write step).

Design invariants (RD-009 / RD-012 / RD-013 / RD-040 / RD-042):
  * READ/TRANSFORM ONLY. It NEVER writes: no derived field is persisted, the tracking
    ``status`` is never touched, no Phase-3 field is touched. The payload is a response,
    not a record.
  * NO RE-DERIVATION, NO MODEL CALL. It echoes the already-derived Hub-side fields (the
    4.1 read-model reused verbatim); it does NOT re-normalize / re-correlate / re-score /
    rebuild findings / re-derive the verdict. The only new derivation is the display
    ``threat_tier``.
  * ADVISORY, NEVER ACTED UPON (RD-040). It surfaces the 3.5 recommendation + an explicit
    ``advisory: true`` flag alongside ``decision: pending``; it NEVER routes / promotes /
    enforces, NEVER presents the recommendation as an effective decision, and NEVER writes
    a verdict onto any record.
  * HUB-SIDE ONLY (RD-009). Its input is already-Hub derived data; it NEVER reads the
    Forensic raw body / findings / trace and never crosses the RD-013 gate. No durable
    store is added anywhere (RD-012 / RD-042).
  * PURE logic + thin seam. All assembly is in ``dashboard.py`` (pure); the DynamoDB reads
    are in ``awsio.py`` (READ-only).
"""

from __future__ import annotations

import datetime as _dt
import logging
import os
import re as _re
from typing import Any

import dashboard

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# --- Configuration (from environment; set by the CDK stack) -----------------

TRACKING_TABLE = os.environ.get("TRACKING_TABLE", "")
# The dashboard payload pins its OWN version (RD-042). Currently "1.0".
DASHBOARD_CONTRACT_VERSION = os.environ.get("DASHBOARD_CONTRACT_VERSION", "1.0")
# The 4.1 status read-model version the per-intake core is assembled under. Kept in
# lockstep with the hub_status Lambda's STATUS_CONTRACT_VERSION.
STATUS_CONTRACT_VERSION = os.environ.get("STATUS_CONTRACT_VERSION", "1.0")

# UUIDv4 shape the tracking key must match (mirror the contract pattern) so a malformed or
# injected key is rejected cheaply before any AWS call.
_UUID4_RE = _re.compile(
    "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


class DashboardError(Exception):
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


def _resolve_view(event: dict[str, Any]) -> str:
    """Pick the view. Explicit ``view`` wins; otherwise an ``intake_id`` implies the
    per-intake view and its absence implies the fleet view. Pure."""
    view = _get_param(event, "view")
    if isinstance(view, str) and view:
        return view.strip().lower()
    return dashboard.VIEW_INTAKE if _get_param(event, "intake_id") else dashboard.VIEW_FLEET


def _resolve_limit(event: dict[str, Any]) -> int:
    """The fleet-list page size: caller-supplied ``limit`` clamped to [1, MAX], default
    DEFAULT. Pure, tolerant (a bad value falls back to the default)."""
    raw = _get_param(event, "limit")
    if raw is None:
        return dashboard.DEFAULT_FLEET_LIMIT
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return dashboard.DEFAULT_FLEET_LIMIT
    return max(1, min(n, dashboard.MAX_FLEET_LIMIT))


def build_intake(intake_id: str) -> dict[str, Any]:
    """Read the tracking item for ``intake_id`` and assemble the per-intake dashboard
    payload. Raises ``DashboardError(404)`` when no record exists,
    ``DashboardError(422)`` when the record is missing its integrity key."""
    import awsio  # local import so tests can stub the seam before import

    item = awsio.get_item(TRACKING_TABLE, intake_id)
    if not item:
        raise DashboardError(404, f"no tracking record for intake_id={intake_id}")
    key = item.get("intake_id")
    sha256 = item.get("sha256")
    if not isinstance(key, str) or not isinstance(sha256, str):
        raise DashboardError(
            422, f"tracking record for intake_id={intake_id} is missing its integrity key"
        )
    payload = dashboard.build_intake_view(
        item,
        intake_id=key,
        sha256=sha256,
        assembled_at=_now_iso(),
        contract_version=DASHBOARD_CONTRACT_VERSION,
        status_contract_version=STATUS_CONTRACT_VERSION,
    )
    logger.info(
        "intake_id=%s dashboard intake view assembled (overall_stage=%s, threat_tier=%s)",
        intake_id,
        payload["intake"]["status"].get("overall_stage"),
        payload["intake"]["threat"].get("tier"),
    )
    return payload


def build_fleet(limit: int) -> dict[str, Any]:
    """Read a bounded, newest-first page of recent tracking items via the GSI and assemble
    the fleet dashboard payload. READ-only."""
    import awsio  # local import so tests can stub the seam before import

    items, more_available = awsio.recent_items(TRACKING_TABLE, limit=limit)
    payload = dashboard.build_fleet_view(
        items,
        assembled_at=_now_iso(),
        contract_version=DASHBOARD_CONTRACT_VERSION,
        status_contract_version=STATUS_CONTRACT_VERSION,
        limit=limit,
        more_available=more_available,
    )
    logger.info(
        "dashboard fleet view assembled (returned_count=%s, truncated=%s)",
        payload["fleet"]["returned_count"],
        payload["fleet"]["truncated"],
    )
    return payload


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """On-demand entry point. Resolves the view + params from the event, assembles the
    dashboard payload, and returns it. On a bad request / not-found it returns a bounded
    error envelope (never raises to the caller) so a direct invoke or a future API front
    gets a clean, typed response."""
    if not TRACKING_TABLE:
        logger.error("Misconfigured: TRACKING_TABLE not set")
        raise RuntimeError("Hub dashboard orchestrator is misconfigured")

    event = event if isinstance(event, dict) else {}
    view = _resolve_view(event)

    try:
        if view == dashboard.VIEW_INTAKE:
            intake_id = _get_param(event, "intake_id")
            if not isinstance(intake_id, str) or not _UUID4_RE.match(intake_id):
                logger.info("bad request: missing or malformed intake_id")
                return {"error": {"code": 400, "message": "missing or malformed intake_id"}}
            return build_intake(intake_id)
        if view == dashboard.VIEW_FLEET:
            return build_fleet(_resolve_limit(event))
        logger.info("bad request: unknown view %r", view)
        return {"error": {"code": 400, "message": f"unknown view {view!r}"}}
    except DashboardError as exc:
        logger.info("dashboard error %s: %s", exc.code, exc.message)
        return {"error": {"code": exc.code, "message": exc.message}}
