"""ZTIE Story 2.6 — collector (join) Lambda handler (Forensic-side wiring).

Runs in the **Forensic** account (360999005254). It is the TERMINAL JOIN task of
the Story 2.6 Step Functions Parallel state (RD-027): the preprocessor starts ONE
Standard state-machine execution that forks a routed artifact into BOTH inspection
lanes CONCURRENTLY (static 2.1/2.2 + dynamic 2.3), each branch with a per-branch
error Catch so a lane failing is RECORDED, not fatal; when BOTH branches finish
(success OR recorded error) the state machine invokes THIS Lambda with the two
branch results. It:

  1. Reads the fork context (intake_id, sha256, the routing-expected lanes) and the
     two branch results from the Step Functions task input.
  2. Runs the PURE join (``collect.join``) — building the bounded, derived,
     verdict-free COLLECTED record: per-lane status (completed / errored /
     not_applicable), bounded roll-ups + Forensic pointers by reference, and the
     join facts (lanes_expected, lanes_collected, both_complete). A one-lane failure
     yields a VALID collected record carrying the other lane's roll-up — never a
     hang, never a drop.
  3. Crosses ONLY that bounded record to the Hub ingest queue via the RD-013 gate
     (the seventh envelope kind) through the thin ``awsio`` seam.

Zero-trust invariants (RD-009 / RD-012 / RD-013 / RD-014):
  * The full findings document + full command log stay in Forensic (RD-009); only
    bounded roll-ups + S3 pointers cross. This handler NEVER reads a raw body.
  * The join introduces NO durable store in Forensic (RD-012) — the SFN execution
    state is the only ephemeral state.
  * The crossed record is EVIDENCE, never a verdict — no verdict/safe/forward field.
    The verdict is Hub-side / human-gated (Phase 4).

No mocks in the execution path: real SQS via the thin awsio seam. moto/jsonschema
are used only in the (live) unit tests, never here — and never in the offline path.
"""

from __future__ import annotations

import datetime as _dt
import logging
import os
from typing import Any

import awsio
import collect

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# --- Configuration (from environment; set by the CDK stack) -----------------

# The one-directional Forensic -> Hub door (same queue as the other envelopes).
HUB_INGEST_QUEUE_URL = os.environ.get("HUB_INGEST_QUEUE_URL", "")
# Story 2.6: the collected-record contract version (its OWN pin — a new envelope
# kind never rides the shared CONTRACT_VERSION).
COLLECTED_CONTRACT_VERSION = os.environ.get("COLLECTED_CONTRACT_VERSION", "1.0")

# The lane ids (must match the routing contract's lane enum).
_STATIC_LANE = collect.LANE_STATIC
_DYNAMIC_LANE = collect.LANE_DYNAMIC


class CollectorError(Exception):
    """A non-retryable join failure (malformed task input / missing identity)."""


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _extract_context(event: dict[str, Any]) -> dict[str, Any]:
    """Pull the fork context (intake_id, sha256, lanes_expected) from the task input.

    The state machine passes a small ``context`` object alongside the branch
    results (the preprocessor seeds it from the routing decision). We accept it
    either nested under ``context`` or flattened at the top level for robustness to
    the exact ASL shape.
    """
    ctx = event.get("context")
    if not isinstance(ctx, dict):
        ctx = event
    intake_id = ctx.get("intake_id")
    sha256 = ctx.get("sha256")
    if not intake_id or not sha256:
        raise CollectorError("join task input missing intake_id/sha256")

    lanes_expected = ctx.get("lanes_expected") or ctx.get("lanes") or []
    if not isinstance(lanes_expected, list):
        lanes_expected = []
    # Keep only the allow-listed lane ids.
    lanes_expected = [
        lane for lane in lanes_expected if lane in (_STATIC_LANE, _DYNAMIC_LANE)
    ]
    return {
        "intake_id": intake_id,
        "sha256": sha256,
        "lanes_expected": lanes_expected,
    }


def _extract_branch_results(event: dict[str, Any]) -> tuple[Any, Any]:
    """Pull the two branch results from the task input.

    The Parallel state yields its branch outputs as a list (``results``/``branches``)
    OR the state machine maps them onto explicit ``static``/``dynamic`` keys. Accept
    both. A branch that errored is passed here as its Catch result (a dict carrying
    an ``error`` marker) — the pure join records it as ``errored``.
    """
    # Explicit keys take precedence (clearest ASL mapping).
    if "static" in event or "dynamic" in event:
        return event.get("static"), event.get("dynamic")

    results = event.get("results")
    if not isinstance(results, list):
        results = event.get("branches")
    if isinstance(results, list):
        static_result = results[0] if len(results) > 0 else None
        dynamic_result = results[1] if len(results) > 1 else None
        return static_result, dynamic_result
    return None, None


def _join_note(context: dict[str, Any], static_result: Any, dynamic_result: Any) -> str | None:
    """Build a short, bounded, non-executable operator note about the join. Pure-ish
    (no I/O). Never a verdict."""
    expected = context["lanes_expected"]
    if not expected:
        return "no lanes routed for this artifact"
    parts: list[str] = []
    if _STATIC_LANE in expected and isinstance(static_result, dict) and static_result.get("error"):
        parts.append("static lane errored; recorded")
    if _DYNAMIC_LANE in expected and isinstance(dynamic_result, dict) and dynamic_result.get("error"):
        parts.append("dynamic lane errored; recorded")
    return "; ".join(parts) if parts else None


def _collect(event: dict[str, Any]) -> dict[str, Any]:
    """Join the two branch results into ONE collected envelope and cross it. Returns
    the crossed envelope. Pure work (the join) is isolated; only the send touches
    AWS."""
    context = _extract_context(event)
    static_result, dynamic_result = _extract_branch_results(event)

    envelope = collect.join(
        intake_id=context["intake_id"],
        sha256=context["sha256"],
        joined_at=_now_iso(),
        lanes_expected=context["lanes_expected"],
        static_result=static_result,
        dynamic_result=dynamic_result,
        contract_version=COLLECTED_CONTRACT_VERSION,
        join_note=_join_note(context, static_result, dynamic_result),
    )

    awsio.send_collected_envelope(HUB_INGEST_QUEUE_URL, envelope)

    collected = envelope["collected"]
    logger.info(
        "joined intake_id=%s expected=%s collected=%s both_complete=%s "
        "static=%s dynamic=%s",
        context["intake_id"],
        collected["lanes_expected"],
        collected["lanes_collected"],
        collected["both_complete"],
        collected["static"]["lane_status"],
        collected["dynamic"]["lane_status"],
    )
    return envelope


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Step Functions task entry point (direct task invoke, terminal join).

    Receives the two branch results + the fork context, joins them into ONE bounded
    collected record, and crosses it to the Hub. Returns the crossed envelope so the
    state-machine execution history records exactly what was joined + crossed. A
    malformed input (non-retryable) raises CollectorError so the state machine's
    error handling records it; a transient send failure propagates so the state
    machine retries the task.
    """
    if not HUB_INGEST_QUEUE_URL:
        logger.error("Misconfigured: HUB_INGEST_QUEUE_URL not set")
        raise RuntimeError("Collector (join) lane is misconfigured")

    if not isinstance(event, dict):
        raise CollectorError("join task input is not an object")

    return _collect(event)
