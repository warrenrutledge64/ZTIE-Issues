#!/usr/bin/env python3
"""Generate the ZTIE per-intake status read-model contract (Story 4.1, RD-041), v1.

Contract-first (RD-041): Story 4.1 OPENS Phase 4 (Reporting & Handoff). Phase 3 leaves,
on the Hub tracking item, the full per-intake assessment: a `combined_event` (3.1), a
`correlation_result` (3.2), a `scoring_result` (3.3, three 0-100 risk scores), a
`remediation_result` (3.4, findings + remediations), and an advisory `verdict_result`
(3.5, `recommended_verdict` + `human_decision: pending`). Story 4.1 is the
STATUS-RETRIEVAL ORCHESTRATOR: for one intake it assembles a bounded, DERIVED per-intake
STATUS READ-MODEL that the Phase-4 dashboard payload (4.2) + per-execution report (4.5) —
and, through those, the human gate + routing (4.4 / 4.6 / 4.7) — consume.

RD-041 — the status read-model is an ON-DEMAND DERIVED TRANSPORT SHAPE, NOT a durable
stored record:
  * ON-DEMAND / DERIVED, NOT PERSISTED. 4.1 is a READ/transform behind an orchestrator
    Lambda: it reads the current Hub tracking item and returns this read-model as its
    response. It does NOT add an 11th durable field to the tracking table, does NOT hang
    off the tracking-table stream, and does NOT persist this shape (a materialized status
    view would only duplicate data already on the item and could lag it). So THIS is a
    response/transport contract (the shape 4.2/4.5 code against), NOT a stored-record
    contract like verdict.contract.v1 / scoring.contract.v1 / etc.
  * READ/TRANSFORM ONLY, NO RE-DERIVATION, NO MODEL CALL. 4.1 does NOT re-normalize /
    re-correlate / re-score / rebuild findings / re-derive the verdict (those are
    3.1-3.5, all done) and makes NO Bedrock call. It ECHOES the already-derived Hub-side
    fields into one consolidated, bounded view. So — like the 3.4 remediation step + the
    3.5 verdict step — the 4.1 Lambda has NO Bedrock client and NO Bedrock grant.
  * THE 3.5 VERDICT STAYS ADVISORY + HUMAN-GATED (RD-040). 4.1 surfaces the 3.5
    `recommended_verdict` as an ADVISORY recommendation ALONGSIDE the `human_decision`
    (which is `pending` until a human selects at the Phase-4 gate). It NEVER promotes /
    routes / enforces, NEVER presents or persists the recommendation as an effective /
    enforced decision, and NEVER writes a verdict onto any record. The advisory field
    here is named `recommended_verdict` (NOT a bare `verdict`) exactly as on 3.5's record,
    so no consumer mistakes it for the effective decision; the effective decision is the
    human `decision` field, whose only value 4.1 can ever report is `pending`.
  * HUB-SIDE ONLY (RD-009 / RD-013). Its input is already-Hub-derived data on the
    tracking item; it NEVER reads the Forensic raw body / findings text / raw trace and
    never crosses the Forensic -> Hub gate. It carries NO gate discriminator.

Run:  python3 scripts/gen_status_contract.py

WHAT THIS RECORD IS (and IS NOT):
  * It is a CONSOLIDATED, BOUNDED per-intake status VIEW: intake identity + the furthest
    pipeline stage reached + per-stage presence/status (which of 3.1-3.5 have landed) +
    the three 3.3 scores (echoed as context) + a bounded findings/remediation SUMMARY
    (counts + the 3.4 status, NOT full findings text) + the 3.5 ADVISORY recommendation
    + the (pending) human decision.
  * It is EVIDENCE for a human to look at, never a decision. There is deliberately NO
    bare `verdict` / `safe` / `approved` / `forward` / `pass_fail` / `malicious` /
    `clean` field; the only verdict-shaped field is `recommendation.recommended_verdict`
    (advisory), and the only decision-shaped field is `recommendation.decision`, whose
    single legal value is `pending` (4.1 never reports a made decision).

Design invariants (mirror the stored contracts, RD-013 / RD-014 / RD-016):
  * allow-list — additionalProperties:false at every level; every field typed and
    enum/length/range-bounded; every array maxItems-capped.
  * integrity-keyed — bound to intake_id + sha256 (the artifact the view is over).
  * DERIVED-ONLY (RD-009) — echoes the bounded derived Hub-side fields; references
    nothing raw.
  * ADVISORY-ONLY (RD-040) — surfaces the recommendation, never an acted-upon decision;
    the human decision stays `pending`.
  * OWN VERSION PIN — contract_version enum ['1.0'], pinned SEPARATELY via
    STATUS_CONTRACT_VERSION.
"""

from __future__ import annotations

# The furthest pipeline stage reached for an intake, HONESTLY reported. Ordered
# coarse -> fine; 4.1 reports the furthest stage for which a derived field is present.
#   received    — a tracking record exists (intake landed) but no Phase-3 field yet.
#   classified  — a classification label is present (Story 1.2) but no combined event.
#   collected   — a combined_event (3.1) is present (lane evidence normalized).
#   correlated  — a correlation_result (3.2) is present.
#   scored      — a scoring_result (3.3) is present.
#   assessed    — a remediation_result (3.4) is present.
#   recommended — a verdict_result (3.5) is present (the advisory recommendation exists).
OVERALL_STAGES = [
    "received",
    "classified",
    "collected",
    "correlated",
    "scored",
    "assessed",
    "recommended",
]

# Per-stage presence status in the `stages` block. Kept deliberately small + honest.
#   present — the stage's derived field is on the tracking item.
#   absent  — the stage's derived field is not (yet) on the tracking item.
STAGE_PRESENCE = [
    "present",
    "absent",
]

# The advisory recommended-verdict vocabulary, mirrored from verdict.contract.v1
# (RD-040). Surfaced as a RECOMMENDATION the human triages on; NEVER acted upon.
RECOMMENDED_VERDICTS = [
    "PASS",
    "FAIL",
    "INCONCLUSIVE",
]

# The status of the 3.5 recommendation record itself, carried through honestly.
RECOMMENDATION_STATUSES = [
    "recommended",
    "no_scores",
    "incomplete",
    # 4.1-only: the 3.5 verdict_result is not on the item yet (Phase 3 not complete).
    "not_yet_recommended",
]

# The single legal value of the human-decision marker 4.1 can report. 4.1 NEVER reports
# a made decision — the human's actual accept/reject is a Phase-4 gate action (4.4/4.6/
# 4.7) written to a separate, human-owned field 4.1 does not read/echo. Enumerated to
# exactly one value so this view can never assert a made decision.
HUMAN_DECISION_PENDING = ["pending"]

# The lane a score refers to (echoed context; mirrors scoring.contract.v1 / RD-038).
SCORE_KINDS = [
    "static",
    "dynamic",
    "combined",
]

# The per-lane score statuses carried through from the 3.3 scoring.contract.v1.
SCORE_STATUSES = [
    "scored",
    "model_error",
    "unparseable",
    "skipped_no_evidence",
]

_MAX_SUMMARY = 4000
_MAX_NOTE = 1024
_MAX_LABEL = 256
_MAX_STATUS_DETAIL = 512
_MAX_CONTRACT_VERSION = 16
_MAX_RUBRIC_VERSION = 16
_MAX_COUNT = 100000


def _score_echo(desc: str) -> dict:
    """One echoed lane score (context/traceability). The NUMBER is 3.3's; 4.1 does NOT
    re-score and does NOT re-blend. `score` is present ONLY when status is 'scored'."""
    return {
        "description": desc,
        "type": "object",
        "additionalProperties": False,
        "required": ["status"],
        "properties": {
            "status": {
                "description": (
                    "This lane's 3.3 score status (scored / model_error / unparseable / "
                    "skipped_no_evidence), carried through honestly. NOT a verdict."
                ),
                "type": "string",
                "enum": SCORE_STATUSES,
            },
            "score": {
                "description": (
                    "The 0-100 risk score (higher = riskier) from 3.3, present ONLY when "
                    "status is 'scored'. Echoed context, never re-blended. A descriptive "
                    "EVIDENCE metric, never a decision."
                ),
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
            },
        },
    }


def _count(desc: str) -> dict:
    return {"description": desc, "type": "integer", "minimum": 0, "maximum": _MAX_COUNT}


SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://ztie.internal/schemas/status.contract.v1.json",
    "title": "ZTIE per-intake status read-model contract (v1)",
    "description": (
        "The bounded, DERIVED per-intake STATUS READ-MODEL assembled by the Story 4.1 "
        "Hub-side status-retrieval orchestrator (RD-041) — the Phase-4 opener. For one "
        "intake it READS the current Hub tracking item and consolidates the already-"
        "derived Phase-3 fields (`combined_event` 3.1 / `correlation_result` 3.2 / "
        "`scoring_result` 3.3 / `remediation_result` 3.4 / `verdict_result` 3.5) into ONE "
        "bounded view the Phase-4 dashboard payload (4.2) + per-execution report (4.5) "
        "consume: intake identity + the furthest pipeline stage reached + per-stage "
        "presence/status + the three 3.3 scores (echoed context) + a bounded "
        "findings/remediation SUMMARY (counts + the 3.4 status; NOT full findings text) + "
        "the 3.5 ADVISORY `recommended_verdict` + the (pending) human `decision`. It is "
        "an ON-DEMAND DERIVED TRANSPORT SHAPE, NOT a durable stored record: 4.1 is a "
        "READ/transform behind an orchestrator Lambda, it adds NO durable tracking field "
        "and does NOT hang off the tracking-table stream. It is READ/transform only — it "
        "does NOT re-normalize / re-correlate / re-score / rebuild findings / re-derive "
        "the verdict (those are 3.1-3.5, done) and makes NO model call (no Bedrock client, "
        "no Bedrock grant). It is Hub-SIDE only (RD-009): it reasons ONLY over the derived "
        "Hub-side fields, NEVER the raw payload / findings text / raw trace (which never "
        "leave Forensic), and it never crosses the RD-013 gate; it carries NO gate "
        "discriminator. CRUCIALLY (RD-040), the 3.5 recommendation it surfaces is ADVISORY "
        "and NEVER acted upon: nothing routes / promotes / destroys / moves an artifact on "
        "it; the enforcement decision is a HUMAN actively selecting PASS or FAIL at the "
        "Phase-4 gate (4.4/4.6/4.7). This view therefore surfaces the recommendation "
        "ALONGSIDE the human `decision`, whose only value 4.1 can report is `pending`; the "
        "advisory field is named `recommended_verdict` (NOT a bare `verdict`) so no "
        "consumer mistakes it for the effective decision, and there is deliberately NO "
        "bare `verdict` / `safe` / `approved` / `forward` / `pass_fail` / `malicious` / "
        "`clean` field. Allow-list: additionalProperties false at every level; every field "
        "typed and enum/length/range-bounded; every array maxItems-capped. Integrity-keyed "
        "by intake_id + sha256. DERIVED-ONLY. OWN version pin (STATUS_CONTRACT_VERSION)."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "contract_version",
        "intake_id",
        "sha256",
        "assembled_at",
        "overall_stage",
        "stages",
        "recommendation",
    ],
    "properties": {
        "contract_version": {
            "description": (
                "Status read-model schema version. Pinned SEPARATELY on the 4.1 Lambda "
                "(STATUS_CONTRACT_VERSION) so this shape versions independently of every "
                "stored-record contract's pin."
            ),
            "type": "string",
            "enum": ["1.0"],
            "maxLength": _MAX_CONTRACT_VERSION,
        },
        "intake_id": {
            "description": (
                "The intake UUIDv4 this status view is for (the tracking-record key)."
            ),
            "type": "string",
            "pattern": (
                "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-"
                "[0-9a-f]{12}$"
            ),
        },
        "sha256": {
            "description": (
                "Lowercase hex SHA-256 of the raw artifact body all lanes inspected. "
                "Integrity key, bound to intake_id; the view is over exactly this "
                "artifact's derived record."
            ),
            "type": "string",
            "pattern": "^[0-9a-f]{64}$",
        },
        "assembled_at": {
            "description": (
                "RFC3339/ISO-8601 UTC timestamp (Z-suffixed) the 4.1 Lambda ASSEMBLED "
                "this view in the Hub. The only wall-clock field 4.1 stamps; a read-model "
                "assembly time, not a pipeline event time."
            ),
            "type": "string",
            "format": "date-time",
            "maxLength": 40,
        },
        "overall_stage": {
            "description": (
                "The FURTHEST pipeline stage reached for this intake, reported HONESTLY "
                "from which derived fields are present (received / classified / collected "
                "/ correlated / scored / assessed / recommended). NOT a verdict — it says "
                "how far the pipeline got, never that the artifact is safe/unsafe."
            ),
            "type": "string",
            "enum": OVERALL_STAGES,
        },
        "status": {
            "description": (
                "Optional pass-through of the tracking record's own lifecycle `status` "
                "string (e.g. RECEIVED), echoed for the dashboard. Bounded, inert text; "
                "NOT a verdict."
            ),
            "type": "string",
            "maxLength": _MAX_LABEL,
        },
        "received_at": {
            "description": (
                "Optional pass-through of the intake's `received_at` timestamp (when the "
                "artifact was received), echoed for the dashboard's timeline."
            ),
            "type": "string",
            "maxLength": 40,
        },
        "stages": {
            "description": (
                "Per-stage presence/status for the Phase-3 pipeline (which derived fields "
                "have landed on the tracking item). Presence facts, never verdicts."
            ),
            "type": "object",
            "additionalProperties": False,
            "required": [
                "combined_event",
                "correlation",
                "scoring",
                "remediation",
                "verdict_recommendation",
            ],
            "properties": {
                "classification": {
                    "description": "Story 1.2 classification label presence.",
                    "type": "string",
                    "enum": STAGE_PRESENCE,
                },
                "combined_event": {
                    "description": "Story 3.1 combined_event presence.",
                    "type": "string",
                    "enum": STAGE_PRESENCE,
                },
                "correlation": {
                    "description": "Story 3.2 correlation_result presence.",
                    "type": "string",
                    "enum": STAGE_PRESENCE,
                },
                "scoring": {
                    "description": "Story 3.3 scoring_result presence.",
                    "type": "string",
                    "enum": STAGE_PRESENCE,
                },
                "remediation": {
                    "description": "Story 3.4 remediation_result presence.",
                    "type": "string",
                    "enum": STAGE_PRESENCE,
                },
                "verdict_recommendation": {
                    "description": (
                        "Story 3.5 verdict_result (advisory recommendation) presence. "
                        "Named `verdict_recommendation` (not `verdict`) so this presence "
                        "flag is never mistaken for an effective-verdict field."
                    ),
                    "type": "string",
                    "enum": STAGE_PRESENCE,
                },
            },
        },
        "scores": {
            "description": (
                "The three 3.3 lane scores echoed for CONTEXT + traceability (static / "
                "dynamic / combined; the combined lane is RD-038's whole-picture number). "
                "Present when a scoring_result is on the item. NEVER re-blended into a new "
                "number. EVIDENCE, never a verdict."
            ),
            "type": "object",
            "additionalProperties": False,
            "required": ["static", "dynamic", "combined"],
            "properties": {
                "static": _score_echo(
                    "The static lane's 3.3 score, echoed as context. EVIDENCE, never a "
                    "verdict."
                ),
                "dynamic": _score_echo(
                    "The dynamic lane's 3.3 score, echoed as context. EVIDENCE, never a "
                    "verdict."
                ),
                "combined": _score_echo(
                    "The combined lane's 3.3 score (RD-038's whole-picture number). "
                    "EVIDENCE, never a verdict."
                ),
                "rubric_version": {
                    "description": (
                        "The shared 0-100 risk-rubric version from the 3.3 scoring_result, "
                        "carried through so the scores are known comparable."
                    ),
                    "type": "string",
                    "maxLength": _MAX_RUBRIC_VERSION,
                },
            },
        },
        "findings_summary": {
            "description": (
                "A bounded SUMMARY of the 3.4 remediation_result: its status + the "
                "by-category counts + how many prioritized remediations exist. NOT the "
                "full findings text (the dashboard/report fetch detail as needed). "
                "Present when a remediation_result is on the item. EVIDENCE, never a "
                "verdict."
            ),
            "type": "object",
            "additionalProperties": False,
            "required": ["status"],
            "properties": {
                "status": {
                    "description": (
                        "The 3.4 remediation_result status carried through (e.g. "
                        "assessed / no_scores / skipped_no_evidence). NOT a verdict."
                    ),
                    "type": "string",
                    "maxLength": _MAX_LABEL,
                },
                "finding_count": _count("Number of detailed findings surfaced by 3.4."),
                "candidate_false_positive_count": _count(
                    "Number of candidate false positives 3.4 flagged."
                ),
                "gap_count": _count("Number of gaps 3.4 identified."),
                "remediation_count": _count(
                    "Number of prioritized remediations 3.4 produced."
                ),
                "highest_gap_severity": {
                    "description": (
                        "The worst gap severity 3.4 saw (context). A high-severity gap is "
                        "a reason for a human look, never an auto-FAIL. EVIDENCE, never a "
                        "verdict."
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
                        "True iff a contradiction finding was present (the lanes "
                        "disagree). A descriptive fact carried through, never a verdict."
                    ),
                    "type": "boolean",
                },
            },
        },
        "recommendation": {
            "description": (
                "The 3.5 ADVISORY recommendation surfaced ALONGSIDE the human decision "
                "(RD-040). The `recommended_verdict` is a RECOMMENDATION the human "
                "triages on; it is NEVER acted upon automatically. `decision` is the "
                "human accept/reject marker, whose only value 4.1 can report is "
                "`pending` — the effective decision is a HUMAN action at the Phase-4 "
                "gate (4.4/4.6/4.7). ALWAYS present: when the 3.5 verdict_result has not "
                "landed yet, status is `not_yet_recommended` and no recommended_verdict "
                "is reported."
            ),
            "type": "object",
            "additionalProperties": False,
            "required": ["status", "decision", "advisory"],
            "properties": {
                "status": {
                    "description": (
                        "The 3.5 recommendation record's status carried through "
                        "(recommended / no_scores / incomplete), or `not_yet_recommended` "
                        "when the 3.5 verdict_result is not on the item yet. HONEST "
                        "production status, never a verdict."
                    ),
                    "type": "string",
                    "enum": RECOMMENDATION_STATUSES,
                },
                "recommended_verdict": {
                    "description": (
                        "The 3.5 ADVISORY recommended verdict (PASS / FAIL / "
                        "INCONCLUSIVE), surfaced for the human to triage. It is NEVER "
                        "acted upon automatically. Deliberately named "
                        "`recommended_verdict` (not `verdict`) so no consumer mistakes it "
                        "for the effective decision. Present ONLY when a 3.5 "
                        "verdict_result has landed (status != not_yet_recommended)."
                    ),
                    "type": "string",
                    "enum": RECOMMENDED_VERDICTS,
                },
                "decision": {
                    "description": (
                        "The human accept/reject decision marker. ALWAYS `pending` — 4.1 "
                        "NEVER reports a made decision; the human's actual selection is a "
                        "SEPARATE, human-owned Phase-4 field 4.1 does not echo. "
                        "Enumerated to exactly one value so this view can never assert a "
                        "made decision. Preserves the human-gate covenant: the "
                        "recommendation INFORMS; the human DECIDES + ACTS."
                    ),
                    "type": "string",
                    "enum": HUMAN_DECISION_PENDING,
                },
                "advisory": {
                    "description": (
                        "Always true: an explicit machine-readable flag that the "
                        "recommended_verdict is ADVISORY and must NEVER be acted upon "
                        "automatically. Defense-in-depth so a downstream consumer cannot "
                        "treat this view's recommendation as an effective decision."
                    ),
                    "type": "boolean",
                    "enum": [True],
                },
                "rubric_version": {
                    "description": (
                        "The shared 0-100 risk-rubric version from the 3.5 record, "
                        "carried through."
                    ),
                    "type": "string",
                    "maxLength": _MAX_RUBRIC_VERSION,
                },
                "summary": {
                    "description": (
                        "The 3.5 recommendation summary carried through (a bounded, "
                        "DETERMINISTIC narrative that explicitly frames the result as "
                        "ADVISORY). Inert text; never a verdict, never raw content."
                    ),
                    "type": "string",
                    "maxLength": _MAX_SUMMARY,
                },
                "status_detail": {
                    "description": (
                        "Optional short, bounded, non-executable note about the "
                        "recommendation status. Never a verdict, never raw content."
                    ),
                    "type": "string",
                    "maxLength": _MAX_STATUS_DETAIL,
                },
            },
        },
        "read_model_note": {
            "description": (
                "Optional short, bounded, non-executable note framing this as a DERIVED "
                "read-only status view whose recommendation is ADVISORY + human-gated. "
                "Descriptive, never a verdict."
            ),
            "type": "string",
            "maxLength": _MAX_NOTE,
        },
    },
}


# Repo-root-relative output paths (the canonical schema + the bundled lambda copy that
# must stay byte-in-sync). Consumed by scripts/gen_contracts.py.
OUT_PATHS = [
    ("schemas", "status.contract.v1.json"),
    ("lambdas", "hub_status", "status.contract.v1.json"),
]


def main() -> None:
    from contract_writer import resolve_out_paths, write_contract

    write_contract(SCHEMA, resolve_out_paths(OUT_PATHS))


if __name__ == "__main__":
    main()
