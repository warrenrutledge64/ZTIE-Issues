#!/usr/bin/env python3
"""Generate the ZTIE dashboard JSON payload contract (Story 4.2, RD-042), v1.

Contract-first (RD-042): Story 4.2 is the Phase-4 DATA LAYER. Story 4.1 (RD-041) built
the per-intake STATUS READ-MODEL (`status.contract.v1`) — an on-demand, PURE, READ-only
transform over ONE Hub tracking item. Story 4.2 builds the comprehensive DASHBOARD JSON
PAYLOAD the real-time dashboard (4.3 render) consumes. It has two request modes served by
one on-demand orchestrator Lambda:
  * a PER-INTAKE DETAIL view (built by REUSING the 4.1 `status_model.build_status` for the
    core, then adding a normalized `threat_tier` for the render's color grading + an
    `action` block carrying the data the human APPROVE/REJECT control keys on), and
  * a FLEET/LIST view (recent intakes via the tracking table's `status-received_at-index`
    GSI — bounded, newest-first, NO full scan — each as a compact row, plus a `metrics`
    block of tracking-native counts + stubbed operational health blocks).

RD-042 — the dashboard payload is an ON-DEMAND DERIVED TRANSPORT SHAPE, NOT a durable
stored record (mirrors RD-041):
  * ON-DEMAND / DERIVED, NOT PERSISTED. 4.2 is a READ/transform behind an orchestrator
    Lambda: it reads the current Hub tracking item(s) and RETURNS this payload as its
    response. It adds NO durable tracking field, does NOT hang off the tracking-table
    stream, and does NOT persist this shape (a materialized dashboard record would only
    duplicate data already on the items and could lag them). So THIS is a
    response/transport contract (the shape 4.3 codes against), NOT a stored-record
    contract.
  * READ/TRANSFORM ONLY, NO RE-DERIVATION, NO MODEL CALL. 4.2 does NOT re-normalize /
    re-correlate / re-score / rebuild findings / re-derive the verdict (3.1-3.5, done) and
    makes NO Bedrock call. The per-intake core is 4.1's read-model (reused verbatim); the
    only NEW derivation is a normalized `threat_tier` computed from already-derived fields
    (the combined score / highest gap severity / contradiction flag) purely for the
    render's color grading — a display band, NEVER a verdict.
  * THE 3.5 VERDICT STAYS ADVISORY + HUMAN-GATED (RD-040). 4.2 surfaces the 3.5
    `recommended_verdict` as an ADVISORY recommendation and the human `decision` as
    `pending`; it NEVER promotes / routes / enforces, NEVER presents or persists the
    recommendation as an effective decision, and NEVER writes a verdict onto any record.
    The `action` block gives the render exactly what the human control needs (the intake
    identity the 4.4/4.6/4.7 action keys on + the advisory recommendation + the pending
    decision), and nothing 4.2 emits is an acted-upon decision. There is deliberately NO
    bare `verdict` / `safe` / `approved` / `forward` / `pass_fail` / `malicious` / `clean`
    field anywhere; the only verdict-shaped field is `recommended_verdict` (advisory).
  * HUB-SIDE ONLY (RD-009 / RD-013). Its input is already-Hub-derived data on the tracking
    item(s); it NEVER reads the Forensic raw body / findings text / raw trace and never
    crosses the Forensic -> Hub gate. It carries NO gate discriminator.
  * BOUNDED IN, BOUNDED OUT. The fleet list is capped (default 50, hard max 100) and read
    from the GSI newest-first (never a full scan); every field is typed and
    enum/length/range-bounded; every array is maxItems-capped.

Run:  python3 scripts/gen_dashboard_contract.py

WHAT THIS PAYLOAD IS (and IS NOT):
  * It is a CONSOLIDATED, BOUNDED dashboard payload in ONE of two shapes: a per-intake
    detail (view=`intake`) or a fleet/list (view=`fleet`).
  * It is EVIDENCE + operational status for a human to look at, never a decision.

Design invariants (mirror the sibling contracts, RD-013 / RD-014 / RD-016):
  * allow-list — additionalProperties:false at every level; every field typed and
    enum/length/range-bounded; every array maxItems-capped.
  * DERIVED-ONLY (RD-009) — echoes the bounded derived Hub-side fields; references nothing
    raw.
  * ADVISORY-ONLY (RD-040) — surfaces the recommendation, never an acted-upon decision;
    the human decision stays `pending`.
  * OWN VERSION PIN — contract_version enum ['1.0'], pinned SEPARATELY via
    DASHBOARD_CONTRACT_VERSION.
"""

from __future__ import annotations

# Which of the two payload shapes this response is. A single discriminator so the render
# (4.3) can branch without guessing.
VIEWS = [
    "intake",
    "fleet",
]

# The normalized THREAT TIER a dashboard renders as a color band (dark-theme, graduated
# severity/threat color-coding — the stakeholder requirement). A DISPLAY band derived from
# already-derived evidence (the combined score / highest gap severity / contradiction),
# NEVER a verdict. `unknown` when there is not enough evidence yet to band.
THREAT_TIERS = [
    "unknown",
    "low",
    "medium",
    "high",
    "critical",
]

# The furthest pipeline stage reached (mirrors status.contract.v1 / RD-041).
OVERALL_STAGES = [
    "received",
    "classified",
    "collected",
    "correlated",
    "scored",
    "assessed",
    "recommended",
]

# The advisory recommended-verdict vocabulary, mirrored from verdict/status contracts
# (RD-040). Surfaced as a RECOMMENDATION the human triages on; NEVER acted upon.
RECOMMENDED_VERDICTS = [
    "PASS",
    "FAIL",
    "INCONCLUSIVE",
]

# The status of the surfaced recommendation, carried through honestly (mirrors
# status.contract.v1).
RECOMMENDATION_STATUSES = [
    "recommended",
    "no_scores",
    "incomplete",
    "not_yet_recommended",
]

# The single legal value of the human-decision marker 4.2 can report. 4.2 NEVER reports a
# made decision — the human's actual accept/reject is a Phase-4 gate action (4.4/4.6/4.7)
# on a separate, human-owned field 4.2 does not read/echo.
HUMAN_DECISION_PENDING = ["pending"]

# The status of an operational health block. `ok`/`degraded`/`unavailable` are honest
# production states; `not_wired` is 4.2's explicit placeholder for a metric whose real
# data source (Image Builder / SSM / CloudWatch / Cost Explorer) is deferred to a
# follow-on story — the SHAPE is stable so the render never changes when the source lands.
HEALTH_STATUSES = [
    "ok",
    "degraded",
    "unavailable",
    "not_wired",
]

_MAX_SUMMARY = 4000
_MAX_NOTE = 1024
_MAX_LABEL = 256
_MAX_CONTRACT_VERSION = 16
_MAX_RUBRIC_VERSION = 16
_MAX_COUNT = 100000
# Bounded fleet list (default 50, hard max 100 — the stakeholder-confirmed cap).
_MAX_FLEET_ROWS = 100

# The intake_id UUIDv4 pattern, shared by every id field.
_UUID4_PATTERN = (
    "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def _count(desc: str) -> dict:
    return {"description": desc, "type": "integer", "minimum": 0, "maximum": _MAX_COUNT}


def _tier_count(desc: str) -> dict:
    """A by-tier / by-value count map. Fixed, allow-listed keys (no free-form)."""
    return {
        "description": desc,
        "type": "object",
        "additionalProperties": False,
        "properties": {},
    }


# --- Reused sub-schemas -------------------------------------------------------

# The `action` block: exactly what the human APPROVE/REJECT control needs (the intake
# identity the 4.4/4.6/4.7 routing keys on + the advisory recommendation + the PENDING
# human decision). It carries NO acted-upon decision; `decision` is enumerated to exactly
# `pending`, and the advisory field is `recommended_verdict` (never a bare `verdict`).
_ACTION_BLOCK = {
    "description": (
        "The data the dashboard's human APPROVE/REJECT control keys on (RD-040): the "
        "intake identity the 4.4/4.6/4.7 routing action targets + the ADVISORY 3.5 "
        "recommendation + the PENDING human decision. 4.2 NEVER acts on this — it is the "
        "control's input, not an executed decision. `decision` is `pending` (4.2 never "
        "reports a made decision); the advisory field is `recommended_verdict` (never a "
        "bare `verdict`)."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["intake_id", "sha256", "decision", "advisory", "recommendation_status"],
    "properties": {
        "intake_id": {
            "description": (
                "The intake UUIDv4 the human accept/reject action targets (the key the "
                "Phase-4 routing 4.4/4.6/4.7 uses)."
            ),
            "type": "string",
            "pattern": _UUID4_PATTERN,
        },
        "sha256": {
            "description": (
                "Lowercase hex SHA-256 of the raw artifact body (integrity key bound to "
                "intake_id) so the human action targets exactly this artifact."
            ),
            "type": "string",
            "pattern": "^[0-9a-f]{64}$",
        },
        "recommendation_status": {
            "description": (
                "The 3.5 recommendation status carried through (recommended / no_scores / "
                "incomplete / not_yet_recommended). HONEST production status, never a "
                "verdict."
            ),
            "type": "string",
            "enum": RECOMMENDATION_STATUSES,
        },
        "recommended_verdict": {
            "description": (
                "The 3.5 ADVISORY recommended verdict (PASS / FAIL / INCONCLUSIVE), "
                "surfaced for the human to triage. NEVER acted upon automatically. "
                "Present ONLY when a 3.5 recommendation has landed."
            ),
            "type": "string",
            "enum": RECOMMENDED_VERDICTS,
        },
        "decision": {
            "description": (
                "The human accept/reject decision marker. ALWAYS `pending` — 4.2 NEVER "
                "reports a made decision; the human's actual selection is a SEPARATE, "
                "human-owned Phase-4 field 4.2 does not echo. Enumerated to exactly one "
                "value so this payload can never assert a made decision."
            ),
            "type": "string",
            "enum": HUMAN_DECISION_PENDING,
        },
        "advisory": {
            "description": (
                "Always true: an explicit machine-readable flag that the "
                "recommended_verdict is ADVISORY and must NEVER be acted upon "
                "automatically. Defense-in-depth so the render cannot treat the "
                "recommendation as an effective decision."
            ),
            "type": "boolean",
            "enum": [True],
        },
    },
}

# A `threat` block: the normalized display tier + the (echoed) evidence it was banded
# from, so the render can both color the item AND show why. A DISPLAY band, never a
# verdict.
_THREAT_BLOCK = {
    "description": (
        "The normalized THREAT TIER the dashboard renders as a color band (dark-theme, "
        "graduated low/medium/high/critical — the stakeholder requirement), plus the "
        "already-derived evidence it was banded from. A DISPLAY band derived from the "
        "combined 3.3 score / the highest 3.4 gap severity / the contradiction flag — "
        "NEVER a verdict, NEVER acted upon."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["tier"],
    "properties": {
        "tier": {
            "description": (
                "The color band (unknown / low / medium / high / critical). `unknown` "
                "when there is not enough derived evidence yet to band. A display band, "
                "never a verdict."
            ),
            "type": "string",
            "enum": THREAT_TIERS,
        },
        "combined_score": {
            "description": (
                "The combined 3.3 risk score (0-100) the tier was primarily banded from, "
                "echoed as context. Present only when a combined score is available. "
                "EVIDENCE, never a verdict."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": 100,
        },
        "highest_gap_severity": {
            "description": (
                "The worst 3.4 gap severity considered when banding, echoed as context."
            ),
            "type": "string",
            "enum": [
                "unknown",
                "none",
                "info",
                "low",
                "medium",
                "high",
                "critical",
            ],
        },
        "contradiction_present": {
            "description": (
                "True iff a contradiction finding was present (the lanes disagree), which "
                "raises the display tier. A descriptive fact, never a verdict."
            ),
            "type": "boolean",
        },
    },
}

# A compact fleet ROW: one recent intake summarized for the list view. Enough for the
# render to draw a colored row + wire its APPROVE/REJECT control, without the full
# per-intake detail (the render fetches detail on demand via a view=intake call).
_FLEET_ROW = {
    "description": (
        "One recent intake summarized for the fleet/list view: identity + how far it got "
        "+ its color band + the advisory recommendation + the pending human decision. A "
        "compact row; the render fetches full per-intake detail on demand."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["intake_id", "overall_stage", "threat_tier", "decision"],
    "properties": {
        "intake_id": {
            "description": "The intake UUIDv4 (the tracking-record key + row identity).",
            "type": "string",
            "pattern": _UUID4_PATTERN,
        },
        "sha256": {
            "description": (
                "Lowercase hex SHA-256 of the raw artifact (integrity key), when present "
                "on the item."
            ),
            "type": "string",
            "pattern": "^[0-9a-f]{64}$",
        },
        "status": {
            "description": (
                "The tracking record's lifecycle status string (e.g. RECEIVED), echoed "
                "for the row. Bounded, inert; NOT a verdict."
            ),
            "type": "string",
            "maxLength": _MAX_LABEL,
        },
        "received_at": {
            "description": (
                "The intake's received_at timestamp, echoed so the render can sort/label "
                "the timeline."
            ),
            "type": "string",
            "maxLength": 40,
        },
        "overall_stage": {
            "description": (
                "The furthest pipeline stage reached, HONESTLY reported. NOT a verdict."
            ),
            "type": "string",
            "enum": OVERALL_STAGES,
        },
        "threat_tier": {
            "description": (
                "The normalized color band for the row (display, never a verdict)."
            ),
            "type": "string",
            "enum": THREAT_TIERS,
        },
        "recommended_verdict": {
            "description": (
                "The 3.5 ADVISORY recommended verdict (PASS / FAIL / INCONCLUSIVE), when "
                "one has landed. NEVER acted upon."
            ),
            "type": "string",
            "enum": RECOMMENDED_VERDICTS,
        },
        "decision": {
            "description": (
                "The human accept/reject decision marker for the row. ALWAYS `pending`."
            ),
            "type": "string",
            "enum": HUMAN_DECISION_PENDING,
        },
    },
}

# An operational HEALTH block: a status + optional bounded detail. For the metrics whose
# real data source is deferred (AMI build / sensor / cost), 4.2 emits `status: not_wired`
# so the SHAPE is stable for the render and the source can be filled in later with no
# render change.
_HEALTH_BLOCK = {
    "description": (
        "An operational health block: a status + an optional bounded, inert detail note. "
        "For metrics whose real data source is deferred to a follow-on story (AMI build "
        "health / sensor status / cost), status is `not_wired` — an explicit placeholder "
        "so the render's shape is stable and the source can be wired later with no render "
        "change."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["status"],
    "properties": {
        "status": {
            "description": (
                "ok / degraded / unavailable / not_wired. `not_wired` = the real data "
                "source is deferred (an explicit placeholder, not an error)."
            ),
            "type": "string",
            "enum": HEALTH_STATUSES,
        },
        "detail": {
            "description": (
                "Optional short, bounded, inert note about the health status. Never a "
                "verdict, never raw content."
            ),
            "type": "string",
            "maxLength": _MAX_LABEL,
        },
    },
}


SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://ztie.internal/schemas/dashboard.contract.v1.json",
    "title": "ZTIE dashboard JSON payload contract (v1)",
    "description": (
        "The bounded, DERIVED DASHBOARD JSON PAYLOAD assembled by the Story 4.2 Hub-side "
        "dashboard orchestrator (RD-042) — the Phase-4 DATA LAYER the real-time dashboard "
        "(4.3 render) consumes. It comes in ONE of two shapes, discriminated by `view`: a "
        "PER-INTAKE DETAIL (view=`intake`) that REUSES the Story 4.1 status read-model "
        "(`status.contract.v1`) as its core + adds a normalized `threat` color band + an "
        "`action` block for the human APPROVE/REJECT control; or a FLEET/LIST (view="
        "`fleet`) of recent intakes read from the tracking table's `status-received_at-"
        "index` GSI (bounded, newest-first, NO full scan) + a `metrics` block of "
        "tracking-native counts and (stubbed) operational health. It is an ON-DEMAND "
        "DERIVED TRANSPORT SHAPE, NOT a durable stored record: 4.2 is a READ/transform "
        "behind an orchestrator Lambda, it adds NO durable tracking field and does NOT "
        "hang off the tracking-table stream. It is READ/transform only — it does NOT "
        "re-normalize / re-correlate / re-score / rebuild findings / re-derive the verdict "
        "(3.1-3.5, done) and makes NO model call (no Bedrock client, no Bedrock grant); "
        "the ONLY new derivation is the display `threat_tier` (from the combined score / "
        "highest gap severity / contradiction), a color band NEVER a verdict. It is "
        "Hub-SIDE only (RD-009): it reasons ONLY over the derived Hub-side fields, NEVER "
        "the raw payload / findings text / raw trace (which never leave Forensic), and it "
        "never crosses the RD-013 gate. CRUCIALLY (RD-040), the 3.5 recommendation it "
        "surfaces is ADVISORY and NEVER acted upon: nothing routes / promotes / destroys / "
        "moves an artifact on it; the enforcement decision is a HUMAN actively selecting "
        "PASS or FAIL at the Phase-4 gate (4.4/4.6/4.7). Every payload surfaces the "
        "recommendation ALONGSIDE the human `decision`, whose only value 4.2 can report is "
        "`pending`; the advisory field is named `recommended_verdict` (NOT a bare "
        "`verdict`), and there is deliberately NO bare `verdict` / `safe` / `approved` / "
        "`forward` / `pass_fail` / `malicious` / `clean` field. Allow-list: "
        "additionalProperties false at every level; every field typed and "
        "enum/length/range-bounded; every array maxItems-capped (the fleet list default "
        "50, hard max 100). DERIVED-ONLY. OWN version pin (DASHBOARD_CONTRACT_VERSION)."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "contract_version",
        "view",
        "assembled_at",
    ],
    "properties": {
        "contract_version": {
            "description": (
                "Dashboard payload schema version. Pinned SEPARATELY on the 4.2 Lambda "
                "(DASHBOARD_CONTRACT_VERSION) so this shape versions independently of "
                "every stored-record contract's pin and of the 4.1 status read-model pin."
            ),
            "type": "string",
            "enum": ["1.0"],
            "maxLength": _MAX_CONTRACT_VERSION,
        },
        "view": {
            "description": (
                "Which payload shape this is: `intake` (per-intake detail) or `fleet` "
                "(recent-intakes list + metrics). A single discriminator so the render "
                "branches without guessing."
            ),
            "type": "string",
            "enum": VIEWS,
        },
        "assembled_at": {
            "description": (
                "RFC3339/ISO-8601 UTC timestamp (Z-suffixed) the 4.2 Lambda ASSEMBLED "
                "this payload in the Hub. A payload assembly time, not a pipeline event "
                "time."
            ),
            "type": "string",
            "format": "date-time",
            "maxLength": 40,
        },
        "intake": {
            "description": (
                "PER-INTAKE DETAIL (present iff view=`intake`). The 4.1 status read-model "
                "(`status.contract.v1`) as `status` + a normalized `threat` color band + "
                "an `action` block for the human APPROVE/REJECT control."
            ),
            "type": "object",
            "additionalProperties": False,
            "required": ["status", "threat", "action"],
            "properties": {
                "status": {
                    "description": (
                        "The full Story 4.1 per-intake status read-model, reused verbatim "
                        "(status.contract.v1). 4.2 does NOT re-assemble it; it embeds "
                        "4.1's output as-is. `true` here means: validated separately by "
                        "the status contract; this contract does not re-declare its "
                        "internals (see status.contract.v1.json)."
                    ),
                    "type": "object",
                },
                "threat": _THREAT_BLOCK,
                "action": _ACTION_BLOCK,
            },
        },
        "fleet": {
            "description": (
                "FLEET/LIST view (present iff view=`fleet`): a bounded, newest-first list "
                "of recent intakes + roll-up counts + operational health. Read from the "
                "`status-received_at-index` GSI (NO full scan)."
            ),
            "type": "object",
            "additionalProperties": False,
            "required": ["intakes", "returned_count", "metrics"],
            "properties": {
                "intakes": {
                    "description": (
                        "The bounded, newest-first list of recent-intake rows (default "
                        "50, hard max 100)."
                    ),
                    "type": "array",
                    "maxItems": _MAX_FLEET_ROWS,
                    "items": _FLEET_ROW,
                },
                "returned_count": _count(
                    "How many rows this payload actually returned (<= the cap)."
                ),
                "truncated": {
                    "description": (
                        "True iff more recent intakes existed than the cap returned (the "
                        "render can show a 'showing N of many' hint). A bounded-output "
                        "fact."
                    ),
                    "type": "boolean",
                },
                "metrics": {
                    "description": (
                        "Roll-up metrics for the returned window. The pipeline counts are "
                        "DERIVED from the returned rows (tracking-native); the operational "
                        "health blocks (AMI build / sensor / cost) are STUBBED "
                        "`not_wired` — their real data sources are deferred to a follow-on "
                        "story, with the SHAPE fixed here so the render never changes."
                    ),
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "window_count",
                        "by_stage",
                        "by_recommended_verdict",
                        "by_threat_tier",
                        "ami_build_health",
                        "sensor_status",
                        "cost",
                    ],
                    "properties": {
                        "window_count": _count(
                            "Total intakes summarized in this metrics window (== "
                            "returned_count)."
                        ),
                        "by_stage": {
                            "description": (
                                "Count of returned intakes at each `overall_stage`. "
                                "Fixed, allow-listed keys."
                            ),
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                stage: _count(f"Intakes whose furthest stage is {stage}.")
                                for stage in OVERALL_STAGES
                            },
                        },
                        "by_recommended_verdict": {
                            "description": (
                                "Count of returned intakes by the ADVISORY 3.5 "
                                "recommended_verdict (context; NEVER an acted-upon "
                                "tally). `none` = no recommendation landed yet."
                            ),
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                **{
                                    rv: _count(
                                        f"Intakes with advisory recommended_verdict {rv}."
                                    )
                                    for rv in RECOMMENDED_VERDICTS
                                },
                                "none": _count(
                                    "Intakes with no recommendation landed yet."
                                ),
                            },
                        },
                        "by_threat_tier": {
                            "description": (
                                "Count of returned intakes by normalized display "
                                "`threat_tier`. For the dashboard's color roll-up."
                            ),
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                tier: _count(f"Intakes in the {tier} color band.")
                                for tier in THREAT_TIERS
                            },
                        },
                        "ami_build_health": _HEALTH_BLOCK,
                        "sensor_status": _HEALTH_BLOCK,
                        "cost": _HEALTH_BLOCK,
                    },
                },
            },
        },
        "dashboard_note": {
            "description": (
                "Optional short, bounded, non-executable note framing this as a DERIVED "
                "read-only dashboard payload whose recommendation is ADVISORY + "
                "human-gated. Descriptive, never a verdict."
            ),
            "type": "string",
            "maxLength": _MAX_NOTE,
        },
    },
}


# Repo-root-relative output paths (the canonical schema + the bundled lambda copy that
# must stay byte-in-sync). Consumed by scripts/gen_contracts.py.
OUT_PATHS = [
    ("schemas", "dashboard.contract.v1.json"),
    ("lambdas", "hub_dashboard", "dashboard.contract.v1.json"),
]


def main() -> None:
    from contract_writer import resolve_out_paths, write_contract

    write_contract(SCHEMA, resolve_out_paths(OUT_PATHS))


if __name__ == "__main__":
    main()
