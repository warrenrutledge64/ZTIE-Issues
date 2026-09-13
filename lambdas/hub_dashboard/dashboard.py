"""ZTIE Story 4.2 (RD-042) — PURE dashboard-payload assembly.

The Phase-4 DATA LAYER. Story 4.1 (RD-041) built the per-intake status read-model
(``status.contract.v1``). Story 4.2 assembles the comprehensive DASHBOARD JSON PAYLOAD
(``dashboard.contract.v1``) the real-time dashboard (4.3 render) consumes, in one of two
shapes discriminated by ``view``:

  * PER-INTAKE DETAIL (``view=intake``): REUSES ``status_model.build_status`` verbatim for
    the core (never re-assembling it), then adds a normalized ``threat`` color band (for
    the dark-theme, graduated severity/threat coloring) + an ``action`` block carrying
    exactly what the human APPROVE/REJECT control needs (the intake identity the
    4.4/4.6/4.7 routing keys on + the ADVISORY 3.5 recommendation + the PENDING human
    decision).
  * FLEET/LIST (``view=fleet``): a bounded, newest-first list of recent-intake rows (the
    caller supplies the raw tracking items read from the ``status-received_at-index`` GSI;
    this module summarizes each into a compact row) + a ``metrics`` roll-up of
    tracking-native counts + STUBBED operational health blocks (AMI build / sensor / cost
    are ``not_wired`` — their real sources are deferred, the SHAPE is fixed here).

This module is deliberately I/O-free and offline-unit-testable (the proven 1.2 -> 4.1
lane pattern: pure logic + a thin boto3 seam). It contains NO boto3, no AWS calls, and NO
model call. Every Phase-3 assessment is already done and lives on the Hub tracking item(s).

Zero-trust invariants baked in here (mirror the contract):
  * READ/TRANSFORM ONLY. NEVER re-normalizes / re-correlates / re-scores / rebuilds
    findings / re-derives the verdict. The per-intake core is 4.1's read-model reused
    verbatim; the ONLY new derivation is the display ``threat_tier`` (from the combined
    score / highest gap severity / contradiction), a color band NEVER a verdict.
  * NO MODEL CALL. Deterministic, reproducible; no Bedrock.
  * ADVISORY, NEVER ACTED UPON (RD-040). The 3.5 recommendation is surfaced as a
    recommendation the human gates; nothing here promotes/routes/enforces. The only
    decision-shaped field is ``decision``, whose single legal value is ``pending``. There
    is deliberately NO bare ``verdict`` / ``safe`` / ``approved`` / ``forward`` /
    ``pass_fail`` / ``malicious`` / ``clean`` key; the only verdict-shaped field is
    ``recommended_verdict`` (advisory).
  * BOUNDED IN, BOUNDED OUT; allow-list; HONEST. The fleet list is capped; a missing field
    becomes an ``unknown``/``absent`` value or an omitted optional block — never a
    fabricated value.
  * DERIVED-ONLY (RD-009). Reasons ONLY over the derived Hub-side fields; references
    nothing raw.
"""

from __future__ import annotations

from typing import Any

import status_model

# --- View discriminator (mirror the contract enum) ---------------------------
VIEW_INTAKE = "intake"
VIEW_FLEET = "fleet"

# --- Threat-tier vocabulary (mirror the contract enum) ------------------------
TIER_UNKNOWN = "unknown"
TIER_LOW = "low"
TIER_MEDIUM = "medium"
TIER_HIGH = "high"
TIER_CRITICAL = "critical"
THREAT_TIERS = (TIER_UNKNOWN, TIER_LOW, TIER_MEDIUM, TIER_HIGH, TIER_CRITICAL)

# --- Fleet-list bounds (stakeholder-confirmed: default 50, hard max 100) ------
DEFAULT_FLEET_LIMIT = 50
MAX_FLEET_LIMIT = 100

# --- Recommended-verdict vocabulary (mirror status/verdict contracts) ---------
RECOMMENDED_VERDICTS = ("PASS", "FAIL", "INCONCLUSIVE")

# --- Health-status vocabulary (mirror the contract enum) ----------------------
HEALTH_NOT_WIRED = "not_wired"

# --- The single legal human-decision value 4.2 can report ---------------------
DECISION_PENDING = "pending"

_MAX_NOTE = 1024

# The shared 0-100 rubric cut lines for the DISPLAY tier. These MIRROR the 3.5 verdict
# bands (RD-040: PASS <=29 / INCONCLUSIVE 30-74 / FAIL >=75) so the color a reviewer sees
# lines up with the advisory recommendation — but this is a DISPLAY band, NOT the verdict
# (4.2 never re-derives the verdict; it only colors already-derived evidence).
_TIER_MEDIUM_MIN = 30
_TIER_HIGH_MIN = 55
_TIER_CRITICAL_MIN = 75

# Gap severities that, on their own, raise the display floor so a reviewer's eye is drawn
# even when scoring is partial/absent. A high/critical gap => at least the HIGH band; this
# is a "look at this" color, never an auto-FAIL (RD-040).
_SEVERITY_TIER_FLOOR = {
    "critical": TIER_HIGH,
    "high": TIER_HIGH,
    "medium": TIER_MEDIUM,
    "low": TIER_LOW,
}

_DASHBOARD_NOTE = (
    "Derived read-only dashboard payload assembled by Story 4.2 from the Hub tracking "
    "record(s). The threat_tier is a DISPLAY color band, not a verdict. The "
    "recommended_verdict is ADVISORY and is NEVER acted upon automatically; the effective "
    "accept/reject decision is a human action at the Phase-4 dashboard gate (the human "
    "decision is pending)."
)


def _tier_rank(tier: str) -> int:
    return THREAT_TIERS.index(tier) if tier in THREAT_TIERS else 0


def _tier_from_score(score: int | None) -> str:
    """Band a 0-100 combined risk score into a display tier. None => unknown. Pure."""
    if score is None:
        return TIER_UNKNOWN
    if score >= _TIER_CRITICAL_MIN:
        return TIER_CRITICAL
    if score >= _TIER_HIGH_MIN:
        return TIER_HIGH
    if score >= _TIER_MEDIUM_MIN:
        return TIER_MEDIUM
    return TIER_LOW


def _combined_score_from_status(status: dict[str, Any]) -> int | None:
    """Pull the combined 3.3 score out of the 4.1 read-model, if it scored. Pure."""
    scores = status.get("scores")
    if not isinstance(scores, dict):
        return None
    combined = scores.get("combined")
    if not isinstance(combined, dict):
        return None
    if combined.get("status") != "scored":
        return None
    val = combined.get("score")
    return val if isinstance(val, int) and not isinstance(val, bool) else None


def build_threat(status: dict[str, Any]) -> dict[str, Any]:
    """Derive the normalized DISPLAY threat block from the 4.1 read-model. The tier is a
    color band computed from the combined score, then raised by a high/critical gap or a
    contradiction so a reviewer's eye is drawn. NEVER a verdict. Pure, HONEST — echoes the
    evidence it banded from; when there is no scoring evidence and no elevating signal the
    tier is ``unknown``."""
    combined_score = _combined_score_from_status(status)
    tier = _tier_from_score(combined_score)

    findings = status.get("findings_summary")
    highest_gap = None
    contradiction = None
    if isinstance(findings, dict):
        highest_gap = findings.get("highest_gap_severity")
        contradiction = findings.get("contradiction_present")

    # Raise the display floor for a severe gap (a "look at this" color, never auto-FAIL).
    if isinstance(highest_gap, str):
        floor = _SEVERITY_TIER_FLOOR.get(highest_gap)
        if floor and _tier_rank(floor) > _tier_rank(tier):
            tier = floor

    # A contradiction (lanes disagree) is worth a human look: at least MEDIUM.
    if contradiction is True and _tier_rank(TIER_MEDIUM) > _tier_rank(tier):
        tier = TIER_MEDIUM

    block: dict[str, Any] = {"tier": tier}
    if combined_score is not None:
        block["combined_score"] = combined_score
    if isinstance(highest_gap, str):
        block["highest_gap_severity"] = highest_gap
    if isinstance(contradiction, bool):
        block["contradiction_present"] = contradiction
    return block


def build_action(status: dict[str, Any]) -> dict[str, Any]:
    """Build the human APPROVE/REJECT control's input from the 4.1 read-model: the intake
    identity the routing (4.4/4.6/4.7) keys on + the ADVISORY recommendation + the PENDING
    decision. NEVER an acted-upon decision. Pure."""
    rec = status.get("recommendation")
    rec = rec if isinstance(rec, dict) else {}
    action: dict[str, Any] = {
        "intake_id": status.get("intake_id"),
        "sha256": status.get("sha256"),
        "recommendation_status": rec.get("status", "not_yet_recommended"),
        "decision": DECISION_PENDING,
        "advisory": True,
    }
    rv = rec.get("recommended_verdict")
    if rv in RECOMMENDED_VERDICTS:
        action["recommended_verdict"] = rv
    return action


def build_intake_view(
    item: dict[str, Any],
    *,
    intake_id: str,
    sha256: str,
    assembled_at: str,
    contract_version: str,
    status_contract_version: str,
) -> dict[str, Any]:
    """Assemble the PER-INTAKE DETAIL dashboard payload (``view=intake``): the 4.1 status
    read-model (reused verbatim) + the derived ``threat`` band + the ``action`` block.
    PURE. NEVER re-assembles the read-model (delegates to ``status_model.build_status``)."""
    status = status_model.build_status(
        item,
        intake_id=intake_id,
        sha256=sha256,
        assembled_at=assembled_at,
        contract_version=status_contract_version,
    )
    return {
        "contract_version": contract_version,
        "view": VIEW_INTAKE,
        "assembled_at": assembled_at,
        "intake": {
            "status": status,
            "threat": build_threat(status),
            "action": build_action(status),
        },
        "dashboard_note": _DASHBOARD_NOTE[:_MAX_NOTE],
    }


def _fleet_row(
    item: dict[str, Any], *, status_contract_version: str
) -> dict[str, Any] | None:
    """Summarize ONE tracking item into a compact fleet row by reusing the 4.1 read-model
    for the per-item core, then projecting the row fields + the display tier. Returns None
    for an item missing its integrity key (skipped honestly, never fabricated). Pure."""
    intake_id = item.get("intake_id")
    sha256 = item.get("sha256")
    if not isinstance(intake_id, str) or not isinstance(sha256, str):
        return None

    status = status_model.build_status(
        item,
        intake_id=intake_id,
        sha256=sha256,
        # A row does not stamp its own assembly time; the payload's top-level
        # assembled_at covers the whole response. Use a fixed valid placeholder that the
        # row never surfaces (the row projects only stable fields below).
        assembled_at="1970-01-01T00:00:00Z",
        contract_version=status_contract_version,
    )
    threat = build_threat(status)
    rec = status.get("recommendation")
    rec = rec if isinstance(rec, dict) else {}

    row: dict[str, Any] = {
        "intake_id": intake_id,
        "sha256": sha256,
        "overall_stage": status.get("overall_stage", "received"),
        "threat_tier": threat["tier"],
        "decision": DECISION_PENDING,
    }
    if isinstance(status.get("status"), str):
        row["status"] = status["status"]
    if isinstance(status.get("received_at"), str):
        row["received_at"] = status["received_at"]
    rv = rec.get("recommended_verdict")
    if rv in RECOMMENDED_VERDICTS:
        row["recommended_verdict"] = rv
    return row


def _health_stub(detail: str) -> dict[str, Any]:
    """A stubbed operational-health block: ``not_wired`` (real source deferred). Pure."""
    return {"status": HEALTH_NOT_WIRED, "detail": detail}


# The overall-stage vocabulary lives on the read-model contract (status_model). Re-declare
# it here (kept in lockstep by the contract) so _metrics can seed a zeroed by_stage map
# without importing a generator into the runtime package.
OVERALL_STAGES = (
    status_model.STAGE_RECEIVED,
    status_model.STAGE_CLASSIFIED,
    status_model.STAGE_COLLECTED,
    status_model.STAGE_CORRELATED,
    status_model.STAGE_SCORED,
    status_model.STAGE_ASSESSED,
    status_model.STAGE_RECOMMENDED,
)


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Roll up tracking-native counts over the returned rows + stub the operational-health
    blocks whose real data sources are deferred. Pure — counts only what is on the rows."""
    by_stage = {stage: 0 for stage in OVERALL_STAGES}
    by_rv = {rv: 0 for rv in RECOMMENDED_VERDICTS}
    by_rv["none"] = 0
    by_tier = {tier: 0 for tier in THREAT_TIERS}

    for row in rows:
        stage = row.get("overall_stage")
        if stage in by_stage:
            by_stage[stage] += 1
        rv = row.get("recommended_verdict")
        if rv in by_rv:
            by_rv[rv] += 1
        else:
            by_rv["none"] += 1
        tier = row.get("threat_tier")
        if tier in by_tier:
            by_tier[tier] += 1

    return {
        "window_count": len(rows),
        "by_stage": by_stage,
        "by_recommended_verdict": by_rv,
        "by_threat_tier": by_tier,
        "ami_build_health": _health_stub(
            "AMI build health source (EC2 Image Builder / SSM) not wired yet; deferred to "
            "a follow-on story."
        ),
        "sensor_status": _health_stub(
            "Sensor status source (detonation-lane telemetry / CloudWatch) not wired yet; "
            "deferred to a follow-on story."
        ),
        "cost": _health_stub(
            "Cost source (Cost Explorer / budgets) not wired yet; deferred to a follow-on "
            "story."
        ),
    }


def build_fleet_view(
    items: list[dict[str, Any]],
    *,
    assembled_at: str,
    contract_version: str,
    status_contract_version: str,
    limit: int = DEFAULT_FLEET_LIMIT,
    more_available: bool = False,
) -> dict[str, Any]:
    """Assemble the FLEET/LIST dashboard payload (``view=fleet``) from raw tracking items
    (the caller reads them newest-first from the GSI, already page-limited). Bounds the
    list to ``limit`` (clamped to ``MAX_FLEET_LIMIT``), summarizes each into a compact row,
    and rolls up tracking-native metrics + stubbed health. PURE. ``more_available`` /
    over-limit input sets ``truncated`` so the render can show a 'showing N of many' hint."""
    capped = max(0, min(int(limit), MAX_FLEET_LIMIT))
    truncated = bool(more_available) or len(items) > capped

    rows: list[dict[str, Any]] = []
    for item in items[:capped]:
        if not isinstance(item, dict):
            continue
        row = _fleet_row(item, status_contract_version=status_contract_version)
        if row is not None:
            rows.append(row)

    return {
        "contract_version": contract_version,
        "view": VIEW_FLEET,
        "assembled_at": assembled_at,
        "fleet": {
            "intakes": rows,
            "returned_count": len(rows),
            "truncated": truncated,
            "metrics": _metrics(rows),
        },
        "dashboard_note": _DASHBOARD_NOTE[:_MAX_NOTE],
    }
