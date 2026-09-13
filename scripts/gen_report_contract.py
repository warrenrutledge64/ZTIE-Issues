#!/usr/bin/env python3
"""Generate the ZTIE per-execution report contract (Story 4.5, RD-045), v1.

Contract-first (RD-045): Story 4.5 is the Phase-4 PER-EXECUTION REPORT — the human-
readable, audience-tiered counterpart to the real-time dashboard (4.3). Story 4.1
(RD-041) built the per-intake STATUS READ-MODEL (`status.contract.v1`) and Story 4.2
(RD-042) the dashboard payload; Story 4.5 assembles a bounded, DERIVED per-intake REPORT
PAYLOAD (`report.contract.v1`) in THREE AUDIENCE TIERS and renders it as a self-contained
HTML document (print-to-PDF for "PDF for humans"). It is served on demand by ONE Hub-side
orchestrator Lambda (`hub_report`), by `intake_id`.

The three tiers (from the stakeholder's dual-output reporting requirement):
  * EXECUTIVE — the risk score + a one-paragraph ADVISORY verdict. Built by REUSING the
    4.1 `status_model.build_status` core (scores + the advisory recommendation + the
    findings summary).
  * SECURITY — the correlated findings (behavioral chains), severity roll-ups, and the
    gaps. Built from the 3.2 `correlation_result` + the 3.4 `remediation_result`
    assessment (detailed findings + gaps). NOTE (RD-013 / RD-009): explicit MITRE ATT&CK
    technique IDs and Sigma rules are NOT carried on the Hub side (they would be raw /
    Forensic detail); the report renders the derived findings + behavioral_refs it DOES
    have and marks the MITRE-ID / Sigma-rule detail as `not_carried_on_hub` (an explicit,
    honest placeholder — a widen-the-crossing enrichment is a tracked follow-on story, not
    this one).
  * DEVELOPER — the prioritized remediations (rank / priority / action / basis), the
    candidate false positives, and the static<->dynamic correlation. Built from the 3.4
    `remediation_result` assessment. NOTE (RD-013): exact file/line is NOT carried on the
    Hub side (raw / Forensic detail); rendered as `not_carried_on_hub`.

RD-045 — the report payload is an ON-DEMAND DERIVED TRANSPORT SHAPE, NOT a durable stored
record (mirrors RD-041 / RD-042):
  * ON-DEMAND / DERIVED, NOT PERSISTED. 4.5 is a READ/transform behind an orchestrator
    Lambda: it reads the current Hub tracking item and RETURNS this payload (+ an HTML
    render) as its response. It adds NO durable tracking field, does NOT hang off the
    tracking-table stream, and persists nothing. So THIS is a response/transport contract,
    NOT a stored-record contract.
  * READ/TRANSFORM ONLY, NO RE-DERIVATION, NO MODEL CALL. 4.5 does NOT re-normalize /
    re-correlate / re-score / rebuild findings / re-derive the verdict (3.1-3.5, done) and
    makes NO Bedrock call. It echoes + bounds + re-groups the already-derived Hub-side
    fields into three tiers.
  * THE 3.5 VERDICT STAYS ADVISORY + HUMAN-GATED (RD-040). The Executive tier surfaces the
    3.5 `recommended_verdict` as an ADVISORY recommendation and the human `decision` as
    `pending`; the report NEVER promotes / routes / enforces and NEVER presents the
    recommendation as an effective decision. There is deliberately NO bare `verdict` /
    `safe` / `approved` / `forward` / `pass_fail` / `malicious` / `clean` field anywhere;
    the only verdict-shaped field is `recommended_verdict` (advisory).
  * HUB-SIDE ONLY (RD-009 / RD-013). Its input is already-Hub-derived data on the tracking
    item; it NEVER reads the Forensic raw body / findings text / raw trace and never
    crosses the Forensic -> Hub gate. It carries NO gate discriminator.
  * BOUNDED IN, BOUNDED OUT. Every list is maxItems-capped (mirroring the source
    contracts, hard max 100); every field is typed and enum/length/range-bounded.

Run:  python3 scripts/gen_report_contract.py

Design invariants (mirror the sibling contracts, RD-013 / RD-014 / RD-016):
  * allow-list — additionalProperties:false at every level; every field typed and
    enum/length/range-bounded; every array maxItems-capped.
  * DERIVED-ONLY (RD-009) — echoes the bounded derived Hub-side fields; references nothing
    raw; raw-only detail (MITRE IDs / Sigma / file-line) is an explicit
    `not_carried_on_hub` placeholder, never fabricated.
  * ADVISORY-ONLY (RD-040) — surfaces the recommendation, never an acted-upon decision;
    the human decision stays `pending`.
  * OWN VERSION PIN — contract_version enum ['1.0'], pinned SEPARATELY via
    REPORT_CONTRACT_VERSION.
"""

from __future__ import annotations

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

# The advisory recommended-verdict vocabulary (RD-040). Surfaced as a RECOMMENDATION the
# human triages on; NEVER acted upon.
RECOMMENDED_VERDICTS = ["PASS", "FAIL", "INCONCLUSIVE"]

RECOMMENDATION_STATUSES = [
    "recommended",
    "no_scores",
    "incomplete",
    "not_yet_recommended",
]

# The single legal value of the human-decision marker 4.5 can report.
HUMAN_DECISION_PENDING = ["pending"]

# Allow-listed severity vocabulary (mirror 3.2 / 3.4 / verdict).
SEVERITIES = ["unknown", "none", "info", "low", "medium", "high", "critical"]

# Finding kinds (mirror 3.4 detailed_findings.kind).
FINDING_KINDS = ["correlated", "static_only", "dynamic_only", "contradiction"]

# Gap types (mirror 3.4 gaps.gap_type).
GAP_TYPES = ["static_uncorroborated", "dynamic_unexplained", "contradiction", "coverage"]

# Remediation priority band + source kind (mirror 3.4 prioritized_remediations).
REMEDIATION_PRIORITIES = ["low", "medium", "high", "critical"]
REMEDIATION_SOURCE_KINDS = [
    "contradiction",
    "correlated",
    "coverage",
    "dynamic_only",
    "dynamic_unexplained",
    "static_only",
    "static_uncorroborated",
]

# The status of a tier's data availability. `available` = the source record has landed;
# `pending` = the upstream stage has not produced it yet (honest, not an error);
# `not_carried_on_hub` = the datum is raw/Forensic detail deliberately not crossed
# (RD-013) — surfaced by a future enrichment story, NOT fabricated here.
DATA_STATUSES = ["available", "pending", "not_carried_on_hub"]

_MAX_SUMMARY = 4000
_MAX_NOTE = 1024
_MAX_LABEL = 256
_MAX_DETAIL = 1024
_MAX_BASIS = 512
_MAX_CONTRACT_VERSION = 16
_MAX_RUBRIC_VERSION = 16
_MAX_COUNT = 100000
_MAX_REF = 256
_MAX_REFS = 20
# Every tier list is capped to the source contracts' hard max.
_MAX_LIST = 100

_UUID4_PATTERN = (
    "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


def _count(desc: str) -> dict:
    return {"description": desc, "type": "integer", "minimum": 0, "maximum": _MAX_COUNT}


def _refs(desc: str) -> dict:
    return {
        "description": desc,
        "type": "array",
        "maxItems": _MAX_REFS,
        "items": {"type": "string", "maxLength": _MAX_REF},
    }


# --- SECURITY tier: a correlated finding (behavioral chain) -------------------
_SECURITY_FINDING = {
    "description": (
        "One correlated finding surfaced for the security reviewer — a behavioral chain / "
        "static<->dynamic correlation. Echoed from the 3.4 assessment `detailed_findings` "
        "(itself derived from the 3.2 correlation). EVIDENCE, never a verdict."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["kind", "severity", "title"],
    "properties": {
        "kind": {
            "description": "correlated / static_only / dynamic_only / contradiction.",
            "type": "string",
            "enum": FINDING_KINDS,
        },
        "severity": {
            "description": "The finding's severity (context, never a verdict).",
            "type": "string",
            "enum": SEVERITIES,
        },
        "title": {"description": "Short finding title.", "type": "string", "maxLength": _MAX_LABEL},
        "detail": {
            "description": "Bounded, inert finding detail (the behavioral chain narrative).",
            "type": "string",
            "maxLength": _MAX_DETAIL,
        },
        "static_refs": _refs("Bounded references into the static-lane findings (inert ids)."),
        "behavioral_refs": _refs(
            "Bounded references into the dynamic-lane behavioral indicators (inert ids)."
        ),
    },
}

# --- SECURITY tier: a gap -----------------------------------------------------
_SECURITY_GAP = {
    "description": (
        "One coverage/uncorroborated/contradiction gap surfaced for the security reviewer. "
        "Echoed from the 3.4 assessment `gaps`. EVIDENCE, never a verdict."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["gap_type", "severity", "title"],
    "properties": {
        "gap_type": {
            "description": (
                "static_uncorroborated / dynamic_unexplained / contradiction / coverage."
            ),
            "type": "string",
            "enum": GAP_TYPES,
        },
        "severity": {"description": "The gap's severity.", "type": "string", "enum": SEVERITIES},
        "title": {"description": "Short gap title.", "type": "string", "maxLength": _MAX_LABEL},
        "detail": {
            "description": "Bounded, inert gap detail.",
            "type": "string",
            "maxLength": _MAX_DETAIL,
        },
        "static_refs": _refs("Bounded static-lane references (inert ids)."),
        "behavioral_refs": _refs("Bounded dynamic-lane references (inert ids)."),
    },
}

# --- DEVELOPER tier: a prioritized remediation --------------------------------
_REMEDIATION = {
    "description": (
        "One prioritized remediation for the developer — a ranked 'fix X' to-do, never "
        "'reject the artifact'. Echoed from the 3.4 assessment `prioritized_remediations`. "
        "EVIDENCE + a to-do, never a verdict."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["rank", "priority", "title", "action"],
    "properties": {
        "rank": {
            "description": "1-based rank (1 = highest priority), contiguous.",
            "type": "integer",
            "minimum": 1,
            "maximum": _MAX_LIST,
        },
        "priority": {
            "description": "low / medium / high / critical (banded from the rubric).",
            "type": "string",
            "enum": REMEDIATION_PRIORITIES,
        },
        "title": {"description": "Short remediation title.", "type": "string", "maxLength": _MAX_LABEL},
        "action": {
            "description": "The bounded, inert 'fix X' action text (confirm / review / remediate).",
            "type": "string",
            "maxLength": _MAX_DETAIL,
        },
        "basis": {
            "description": "The bounded rationale for the ranking (risk score / severity cited).",
            "type": "string",
            "maxLength": _MAX_BASIS,
        },
        "source_kind": {
            "description": "Which finding/gap kind motivated this remediation.",
            "type": "string",
            "enum": REMEDIATION_SOURCE_KINDS,
        },
        "severity": {"description": "The source severity.", "type": "string", "enum": SEVERITIES},
        "static_refs": _refs("Bounded static-lane references (inert ids)."),
        "behavioral_refs": _refs("Bounded dynamic-lane references (inert ids)."),
    },
}

# --- DEVELOPER tier: a candidate false positive -------------------------------
_CANDIDATE_FP = {
    "description": (
        "One candidate false positive for the developer to confirm/dismiss (a static "
        "finding not corroborated dynamically). Echoed from the 3.4 assessment "
        "`candidate_false_positives`. EVIDENCE, never a verdict."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["severity", "title"],
    "properties": {
        "severity": {"description": "The candidate FP severity.", "type": "string", "enum": SEVERITIES},
        "title": {"description": "Short title.", "type": "string", "maxLength": _MAX_LABEL},
        "detail": {
            "description": "Bounded, inert detail.",
            "type": "string",
            "maxLength": _MAX_DETAIL,
        },
        "static_refs": _refs("Bounded static-lane references (inert ids)."),
    },
}

# --- An explicit 'raw detail not carried on the Hub' marker (RD-013) ----------
_NOT_CARRIED = {
    "description": (
        "An explicit, honest marker that a piece of report detail (e.g. MITRE ATT&CK "
        "technique IDs, Sigma rules, or exact file/line) is NOT carried on the Hub side — "
        "it is raw / Forensic detail deliberately kept behind the RD-013 gate. It is a "
        "PLACEHOLDER, never fabricated data; a widen-the-crossing enrichment is a tracked "
        "follow-on story. `status` is always `not_carried_on_hub` here."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["status"],
    "properties": {
        "status": {
            "description": "Always `not_carried_on_hub` (an explicit placeholder, not an error).",
            "type": "string",
            "enum": ["not_carried_on_hub"],
        },
        "note": {
            "description": "Optional short, bounded, inert note explaining what is deferred.",
            "type": "string",
            "maxLength": _MAX_LABEL,
        },
    },
}


# --- The three tiers ----------------------------------------------------------

_EXECUTIVE_TIER = {
    "description": (
        "EXECUTIVE tier: the risk score + a one-paragraph ADVISORY verdict, for a "
        "non-technical reader. Built by reusing the 4.1 read-model (RD-041): the combined "
        "risk score, the advisory recommended_verdict + pending human decision, and a "
        "one-paragraph summary. NEVER an effective decision (RD-040)."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["overall_stage", "recommendation"],
    "properties": {
        "overall_stage": {
            "description": "The furthest pipeline stage reached, honestly reported.",
            "type": "string",
            "enum": OVERALL_STAGES,
        },
        "combined_score": {
            "description": (
                "The combined 3.3 risk score (0-100), echoed as the headline risk number. "
                "Present only when scored. EVIDENCE, never a verdict."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": 100,
        },
        "highest_gap_severity": {
            "description": "The worst gap severity, echoed as context.",
            "type": "string",
            "enum": SEVERITIES,
        },
        "contradiction_present": {
            "description": "True iff the lanes disagreed (a contradiction finding present).",
            "type": "boolean",
        },
        "recommendation": {
            "description": (
                "The 3.5 ADVISORY recommendation surfaced ALONGSIDE the human decision "
                "(RD-040): the recommended_verdict (when landed), the recommendation "
                "status, the one-paragraph summary, and decision=`pending` + "
                "advisory=`true`. NEVER acted upon; the advisory field is "
                "`recommended_verdict` (never a bare `verdict`)."
            ),
            "type": "object",
            "additionalProperties": False,
            "required": ["status", "decision", "advisory"],
            "properties": {
                "status": {
                    "description": "recommended / no_scores / incomplete / not_yet_recommended.",
                    "type": "string",
                    "enum": RECOMMENDATION_STATUSES,
                },
                "recommended_verdict": {
                    "description": (
                        "The 3.5 ADVISORY recommended verdict (PASS / FAIL / "
                        "INCONCLUSIVE), when landed. NEVER acted upon."
                    ),
                    "type": "string",
                    "enum": RECOMMENDED_VERDICTS,
                },
                "summary": {
                    "description": (
                        "The one-paragraph ADVISORY verdict narrative carried through from "
                        "3.5. Inert text; never a verdict field."
                    ),
                    "type": "string",
                    "maxLength": _MAX_SUMMARY,
                },
                "rubric_version": {
                    "description": "The shared 0-100 rubric version, carried through.",
                    "type": "string",
                    "maxLength": _MAX_RUBRIC_VERSION,
                },
                "decision": {
                    "description": "The human decision marker. ALWAYS `pending`.",
                    "type": "string",
                    "enum": HUMAN_DECISION_PENDING,
                },
                "advisory": {
                    "description": (
                        "Always true: the recommended_verdict is ADVISORY and must never "
                        "be acted upon automatically."
                    ),
                    "type": "boolean",
                    "enum": [True],
                },
            },
        },
    },
}

_SECURITY_TIER = {
    "description": (
        "SECURITY tier: the correlated findings (behavioral chains), severity roll-ups, "
        "and the gaps, for a security reviewer. Built from the 3.2 correlation + the 3.4 "
        "assessment. `data_status` is `available` when the correlation/remediation records "
        "have landed, else `pending`. MITRE ATT&CK technique IDs and Sigma rules are NOT "
        "carried on the Hub (RD-013) — see `mitre_attack` / `sigma_rules` "
        "(`not_carried_on_hub`)."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["data_status", "findings", "gaps", "mitre_attack", "sigma_rules"],
    "properties": {
        "data_status": {
            "description": "available / pending / not_carried_on_hub.",
            "type": "string",
            "enum": DATA_STATUSES,
        },
        "highest_finding_severity": {
            "description": "The worst finding severity, echoed as context.",
            "type": "string",
            "enum": SEVERITIES,
        },
        "highest_correlation_severity": {
            "description": "The worst correlation severity from 3.2, echoed as context.",
            "type": "string",
            "enum": SEVERITIES,
        },
        "summary": {
            "description": "The bounded correlation/assessment summary narrative (inert).",
            "type": "string",
            "maxLength": _MAX_SUMMARY,
        },
        "finding_count": _count("Number of correlated findings surfaced."),
        "findings": {
            "description": "The bounded list of correlated findings (behavioral chains).",
            "type": "array",
            "maxItems": _MAX_LIST,
            "items": _SECURITY_FINDING,
        },
        "gap_count": _count("Number of gaps surfaced."),
        "gaps": {
            "description": "The bounded list of gaps.",
            "type": "array",
            "maxItems": _MAX_LIST,
            "items": _SECURITY_GAP,
        },
        "mitre_attack": _NOT_CARRIED,
        "sigma_rules": _NOT_CARRIED,
    },
}

_DEVELOPER_TIER = {
    "description": (
        "DEVELOPER tier: the prioritized remediations (rank / priority / action / basis), "
        "the candidate false positives, and the static<->dynamic correlation, for the "
        "developer who must fix the artifact. Built from the 3.4 assessment. `data_status` "
        "is `available` when the remediation record has landed, else `pending`. Exact "
        "file/line is NOT carried on the Hub (RD-013) — see `source_location` "
        "(`not_carried_on_hub`)."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "data_status",
        "prioritized_remediations",
        "candidate_false_positives",
        "source_location",
    ],
    "properties": {
        "data_status": {
            "description": "available / pending / not_carried_on_hub.",
            "type": "string",
            "enum": DATA_STATUSES,
        },
        "summary": {
            "description": "The bounded assessment summary narrative (inert).",
            "type": "string",
            "maxLength": _MAX_SUMMARY,
        },
        "remediation_count": _count("Number of prioritized remediations."),
        "prioritized_remediations": {
            "description": "The bounded, rank-ordered remediation list (highest priority first).",
            "type": "array",
            "maxItems": _MAX_LIST,
            "items": _REMEDIATION,
        },
        "candidate_false_positive_count": _count("Number of candidate false positives."),
        "candidate_false_positives": {
            "description": "The bounded list of candidate false positives to confirm/dismiss.",
            "type": "array",
            "maxItems": _MAX_LIST,
            "items": _CANDIDATE_FP,
        },
        "source_location": _NOT_CARRIED,
    },
}


SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://ztie.internal/schemas/report.contract.v1.json",
    "title": "ZTIE per-execution report contract (v1)",
    "description": (
        "The bounded, DERIVED per-intake PER-EXECUTION REPORT PAYLOAD assembled by the "
        "Story 4.5 Hub-side report orchestrator (`hub_report`, RD-045) — the human-"
        "readable, audience-tiered counterpart to the real-time dashboard (4.3). It is "
        "served on demand by `intake_id` and rendered as a self-contained HTML document "
        "(print-to-PDF). It carries THREE AUDIENCE TIERS: EXECUTIVE (the risk score + a "
        "one-paragraph ADVISORY verdict, built by reusing the 4.1 read-model), SECURITY "
        "(correlated findings / behavioral chains + severity roll-ups + gaps, from the 3.2 "
        "correlation + 3.4 assessment), and DEVELOPER (prioritized remediations + "
        "candidate false positives + static<->dynamic correlation, from the 3.4 "
        "assessment). It is an ON-DEMAND DERIVED TRANSPORT SHAPE, NOT a durable stored "
        "record: 4.5 is a READ/transform behind an orchestrator Lambda, it adds NO durable "
        "tracking field and does NOT hang off the tracking-table stream. It is "
        "READ/transform only — it does NOT re-normalize / re-correlate / re-score / "
        "rebuild findings / re-derive the verdict (3.1-3.5, done) and makes NO model call "
        "(no Bedrock client, no Bedrock grant); it echoes + bounds + re-groups the "
        "already-derived Hub-side fields into three tiers. It is Hub-SIDE only (RD-009): "
        "it reasons ONLY over the derived Hub-side fields, NEVER the raw payload / findings "
        "text / raw trace (which never leave Forensic), and it never crosses the RD-013 "
        "gate. Raw-only detail (MITRE ATT&CK technique IDs, Sigma rules, exact file/line) "
        "is NOT carried on the Hub and is surfaced as an explicit `not_carried_on_hub` "
        "placeholder (a widen-the-crossing enrichment is a tracked follow-on story, NOT "
        "this one) — never fabricated. CRUCIALLY (RD-040), the 3.5 recommendation the "
        "Executive tier surfaces is ADVISORY and NEVER acted upon: the report surfaces the "
        "recommendation ALONGSIDE the human `decision`, whose only value 4.5 can report is "
        "`pending`; the advisory field is named `recommended_verdict` (NOT a bare "
        "`verdict`), and there is deliberately NO bare `verdict` / `safe` / `approved` / "
        "`forward` / `pass_fail` / `malicious` / `clean` field. Allow-list: "
        "additionalProperties false at every level; every field typed and "
        "enum/length/range-bounded; every array maxItems-capped (hard max 100). "
        "DERIVED-ONLY. OWN version pin (REPORT_CONTRACT_VERSION)."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "contract_version",
        "intake_id",
        "sha256",
        "assembled_at",
        "executive",
        "security",
        "developer",
    ],
    "properties": {
        "contract_version": {
            "description": (
                "Report payload schema version. Pinned SEPARATELY on the 4.5 Lambda "
                "(REPORT_CONTRACT_VERSION) so this shape versions independently of every "
                "stored-record contract's pin and of the 4.1/4.2 pins."
            ),
            "type": "string",
            "enum": ["1.0"],
            "maxLength": _MAX_CONTRACT_VERSION,
        },
        "intake_id": {
            "description": "The intake UUIDv4 this report is for.",
            "type": "string",
            "pattern": _UUID4_PATTERN,
        },
        "sha256": {
            "description": (
                "Lowercase hex SHA-256 of the raw artifact body (integrity key bound to "
                "intake_id)."
            ),
            "type": "string",
            "pattern": "^[0-9a-f]{64}$",
        },
        "assembled_at": {
            "description": (
                "RFC3339/ISO-8601 UTC timestamp (Z-suffixed) the 4.5 Lambda ASSEMBLED this "
                "report. A payload assembly time, not a pipeline event time."
            ),
            "type": "string",
            "format": "date-time",
            "maxLength": 40,
        },
        "status": {
            "description": (
                "The tracking record's lifecycle status string (e.g. RECEIVED), echoed. "
                "Bounded, inert; NOT a verdict."
            ),
            "type": "string",
            "maxLength": _MAX_LABEL,
        },
        "received_at": {
            "description": "The intake's received_at timestamp, echoed.",
            "type": "string",
            "maxLength": 40,
        },
        "executive": _EXECUTIVE_TIER,
        "security": _SECURITY_TIER,
        "developer": _DEVELOPER_TIER,
        "report_note": {
            "description": (
                "Optional short, bounded, non-executable note framing this as a DERIVED "
                "read-only report whose recommendation is ADVISORY + human-gated. "
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
    ("schemas", "report.contract.v1.json"),
    ("lambdas", "hub_report", "report.contract.v1.json"),
]


def main() -> None:
    from contract_writer import resolve_out_paths, write_contract

    write_contract(SCHEMA, resolve_out_paths(OUT_PATHS))


if __name__ == "__main__":
    main()
