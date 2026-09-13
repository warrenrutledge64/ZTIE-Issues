#!/usr/bin/env python3
"""Generate the ZTIE remediation-result data contract (Story 3.4, RD-039), v1.

Contract-first: this is the bounded, DERIVED, verdict-free result the Phase-3
findings + remediations step (Story 3.4) records on the Hub tracking item after the
Story 3.3 (RD-038) three risk scores AND the Story 3.2 (RD-035) correlation findings
have landed. It turns those already-structured inputs into (a) DETAILED FINDINGS for a
human — the categorized correlation findings surfaced, PLUS the migrated
candidate-false-positive list (from `static_only` findings) and the gap list
(`static_uncorroborated` / `dynamic_unexplained` / `contradiction` / `coverage`) that
moved out of the old RD-037 3.3 synthesis — and (b) a PRIORITIZED REMEDIATION list,
ranked highest-risk-first by the three 0-100 risk scores + the finding/gap severities.

Like the combined-event (3.1), correlation (3.2) and scoring (3.3) contracts, and for
the SAME reasons, it is NOT a Forensic -> Hub crossing: its inputs (the 3.3
`scoring_result` + the 3.2 `correlation_result`) ALREADY live on the Hub tracking item.
So 3.4 READS that derived Hub-side data -> deterministically builds the findings view +
ranks the remediations -> writes the remediation result back onto the SAME item. It
makes NO model call (RD-039: PURE post-processing — the inputs are already structured,
so a Nova Pro call would only add cost / non-determinism / verdict-risk for no gain);
so — UNLIKE the 3.2 correlator + the 3.3 scorer — it has NO Bedrock client and NO
Bedrock grant. RD-009 / RD-013 stay intact (it reasons ONLY over the derived Hub-side
scores + findings — never the raw payload / raw trace, which never leave Forensic); no
durable store is added to the Forensic blast zone (RD-012). It is a Hub-INTERNAL derived
field, so it carries NO gate discriminator.

Run:  python3 scripts/gen_remediation_contract.py

WHAT THIS RECORD IS (and IS NOT):
  * It records DETAILED FINDINGS (the correlation findings surfaced + the candidate
    false positives + the gaps) and a PRIORITIZED REMEDIATION list (each remediation an
    actionable, bounded, INERT string ranked highest-risk-first). It is the actionable
    content the dashboard + the per-execution report + the human accept/reject gate
    read.
  * It records its production HONESTLY via `status` (assessed / no_scores /
    skipped_no_evidence). It TOLERATES A PARTIAL scoring result: a score block may be
    `model_error` / `unparseable` / `skipped_no_evidence`, and the ranking is done
    honestly over WHICHEVER scores are present (a missing score is never fabricated).
  * It NEVER contains a verdict. There is deliberately NO verdict / safe / approved /
    forward / pass_fail / malicious / clean field ANYWHERE. A remediation is "fix X,"
    NEVER "reject the artifact"; the findings are EVIDENCE, not a decision. The
    enforcement verdict (PASS / FAIL / INCONCLUSIVE) stays Hub-side / human-gated
    (Story 3.5).

Design invariants (mirror the crossing contracts, RD-013 / RD-014 / RD-016):
  * allow-list — additionalProperties:false at every level; every field typed and
    enum/length/range-bounded; every array maxItems-capped.
  * integrity-keyed — bound to intake_id + sha256.
  * DERIVED-ONLY (RD-009) — reasons over the bounded derived scores + findings; the
    record references nothing raw.
  * ZERO-TRUST (RD-014) — evidence + a to-do list, never a verdict.
  * OWN VERSION PIN — contract_version enum ['1.0'], pinned SEPARATELY via
    REMEDIATION_CONTRACT_VERSION (never rides the shared CONTRACT_VERSION).
"""

from __future__ import annotations

# The overall production status. Records what the step actually did, HONESTLY.
#   assessed             — scores were present; a findings view + prioritized
#                          remediations were produced.
#   no_scores            — no `scoring_result` was on the tracking item yet (3.3 has
#                          not landed), so there was nothing to assess.
#   skipped_no_evidence  — a scoring_result was present but every score block was a
#                          non-scored status (all model_error / unparseable /
#                          skipped_no_evidence) AND there were no correlation findings,
#                          so there was no evidence to rank. (A partial result with at
#                          least one score OR at least one finding is 'assessed'.)
STATUSES = [
    "assessed",
    "no_scores",
    "skipped_no_evidence",
]

# Descriptive severity vocabulary (shared with the 3.2 correlation findings + the old
# 3.3 gap list). Ordered least->most severe elsewhere; enumerated here for the schema.
SEVERITIES = [
    "unknown",
    "none",
    "info",
    "low",
    "medium",
    "high",
    "critical",
]

# The correlation finding kinds carried through from 3.2 (correlation.contract.v1).
FINDING_KINDS = [
    "correlated",
    "static_only",
    "dynamic_only",
    "contradiction",
]

# The gap types (migrated from the old RD-037 3.3 gap list).
GAP_TYPES = [
    "static_uncorroborated",
    "dynamic_unexplained",
    "contradiction",
    "coverage",
]

# Descriptive remediation priority bands (derived from the risk scores + severities).
# EVIDENCE, NOT a verdict: 'critical' priority means "fix this first," never "FAIL".
REMEDIATION_PRIORITIES = [
    "low",
    "medium",
    "high",
    "critical",
]

# The lane a score / remediation basis refers to.
SCORE_KINDS = [
    "static",
    "dynamic",
    "combined",
]

_MAX_SUMMARY = 4000
_MAX_TITLE = 256
_MAX_DETAIL = 1024
_MAX_ACTION = 1024
_MAX_BASIS = 512
_MAX_REF = 256
_MAX_REFS = 20
_MAX_ITEMS = 100
_MAX_COUNT = 1000
_MAX_STATUS_DETAIL = 512
_MAX_CONTRACT_VERSION = 16
_MAX_RUBRIC_VERSION = 16


def _severity_prop(desc: str) -> dict:
    return {
        "description": desc,
        "type": "string",
        "enum": SEVERITIES,
    }


def _refs_prop(desc: str) -> dict:
    return {
        "description": desc,
        "type": "array",
        "maxItems": _MAX_REFS,
        "items": {"type": "string", "maxLength": _MAX_REF},
    }


def _detailed_finding() -> dict:
    """One detailed finding surfaced for a human — a correlation finding (3.2) carried
    through, allow-listed + bounded. EVIDENCE only, never a verdict."""
    return {
        "description": (
            "One detailed finding surfaced for the human gate + the report: a Story 3.2 "
            "correlation finding carried through, bounded + allow-listed. Descriptive "
            "EVIDENCE, never a verdict."
        ),
        "type": "object",
        "additionalProperties": False,
        "required": ["kind", "severity", "title"],
        "properties": {
            "kind": {
                "description": (
                    "How this finding relates the two evidence lanes (correlated / "
                    "static_only / dynamic_only / contradiction), from 3.2. Descriptive, "
                    "never a verdict."
                ),
                "type": "string",
                "enum": FINDING_KINDS,
            },
            "severity": _severity_prop(
                "Descriptive severity roll-up for this finding (how NOTABLE it is), from "
                "3.2. 'unknown' when the model did not rate it. NOT a decision."
            ),
            "title": {
                "description": (
                    "Short, bounded, human-readable title of the finding (from 3.2). "
                    "Inert text, never executed."
                ),
                "type": "string",
                "maxLength": _MAX_TITLE,
            },
            "detail": {
                "description": (
                    "Optional longer, bounded explanation (from 3.2). Inert text; never "
                    "raw content, never a verdict."
                ),
                "type": "string",
                "maxLength": _MAX_DETAIL,
            },
            "static_refs": _refs_prop(
                "Optional bounded short references to the static evidence this finding "
                "draws on (from 3.2). Inert text references, never raw findings."
            ),
            "behavioral_refs": _refs_prop(
                "Optional bounded short references to the dynamic behavioral evidence "
                "this finding draws on (from 3.2). Inert text references, never the raw "
                "trace."
            ),
        },
    }


def _candidate_false_positive() -> dict:
    """One candidate false positive — a static_only finding the observed behavior never
    exercised. Migrated from the old RD-037 3.3 synthesis. EVIDENCE only."""
    return {
        "description": (
            "One CANDIDATE false positive: a static-only finding (a static flag with no "
            "correlated dynamic behavior) surfaced so a reviewer can judge whether the "
            "static scanner over-reported. Migrated from the old 3.3 synthesis. "
            "Descriptive EVIDENCE, never a verdict (it is a CANDIDATE, not a decision "
            "that the finding is benign)."
        ),
        "type": "object",
        "additionalProperties": False,
        "required": ["severity", "title"],
        "properties": {
            "severity": _severity_prop(
                "The static finding's descriptive severity (from 3.2). NOT a decision."
            ),
            "title": {
                "description": (
                    "Short, bounded title of the static-only finding. Inert text."
                ),
                "type": "string",
                "maxLength": _MAX_TITLE,
            },
            "detail": {
                "description": (
                    "Optional bounded explanation of why this is a candidate false "
                    "positive. Inert text; never a verdict."
                ),
                "type": "string",
                "maxLength": _MAX_DETAIL,
            },
            "static_refs": _refs_prop(
                "Optional bounded short references to the static evidence this candidate "
                "draws on. Inert text references, never raw findings."
            ),
        },
    }


def _gap() -> dict:
    """One gap — where the two lanes disagree or leave a hole. Migrated from the old
    RD-037 3.3 synthesis. EVIDENCE only."""
    return {
        "description": (
            "One gap in the two-lane picture: static_uncorroborated (a static flag the "
            "behavior never exercised), dynamic_unexplained (behavior with no static "
            "flag), contradiction (the lanes disagree), or coverage (the assessment ran "
            "over an incomplete combined event). Migrated from the old 3.3 synthesis. "
            "Descriptive EVIDENCE for the human gate, never a verdict."
        ),
        "type": "object",
        "additionalProperties": False,
        "required": ["gap_type", "severity", "title"],
        "properties": {
            "gap_type": {
                "description": (
                    "The kind of gap (static_uncorroborated / dynamic_unexplained / "
                    "contradiction / coverage). Descriptive, never a verdict."
                ),
                "type": "string",
                "enum": GAP_TYPES,
            },
            "severity": _severity_prop(
                "Descriptive severity of the gap. 'unknown' when not rated. NOT a "
                "decision."
            ),
            "title": {
                "description": "Short, bounded title of the gap. Inert text.",
                "type": "string",
                "maxLength": _MAX_TITLE,
            },
            "detail": {
                "description": (
                    "Optional bounded explanation of the gap. Inert text; never a "
                    "verdict."
                ),
                "type": "string",
                "maxLength": _MAX_DETAIL,
            },
            "static_refs": _refs_prop(
                "Optional bounded short static-evidence references for the gap. Inert "
                "text references."
            ),
            "behavioral_refs": _refs_prop(
                "Optional bounded short behavioral-evidence references for the gap. Inert "
                "text references."
            ),
        },
    }


def _remediation() -> dict:
    """One prioritized remediation — an actionable, bounded, INERT to-do. Ranked
    highest-risk-first. EVIDENCE + a to-do, NEVER a verdict."""
    return {
        "description": (
            "One prioritized remediation: an actionable, bounded, INERT to-do derived "
            "from a finding / gap + the risk scores, ranked highest-risk-first. It is "
            "'fix X' (an action to reduce risk), NEVER 'reject/forward/approve the "
            "artifact' (a decision). EVIDENCE + a to-do, never a verdict — the "
            "PASS/FAIL/INCONCLUSIVE decision is Story 3.5 + the human gate."
        ),
        "type": "object",
        "additionalProperties": False,
        "required": ["rank", "priority", "title", "action"],
        "properties": {
            "rank": {
                "description": (
                    "1-based position in the prioritized list (1 = address first). A "
                    "bounded ordinal, never a verdict."
                ),
                "type": "integer",
                "minimum": 1,
                "maximum": _MAX_ITEMS,
            },
            "priority": {
                "description": (
                    "Descriptive priority band (low / medium / high / critical) derived "
                    "from the risk scores + the source severity. 'critical' means "
                    "'address first,' NEVER 'the artifact FAILS'. EVIDENCE, not a "
                    "decision."
                ),
                "type": "string",
                "enum": REMEDIATION_PRIORITIES,
            },
            "title": {
                "description": (
                    "Short, bounded title of what to remediate (derived from the source "
                    "finding / gap). Inert text."
                ),
                "type": "string",
                "maxLength": _MAX_TITLE,
            },
            "action": {
                "description": (
                    "The bounded, INERT, actionable remediation guidance ('investigate "
                    "…', 'confirm …', 'harden …'). Never executable content, never a "
                    "verdict, never a decision to reject/forward the artifact."
                ),
                "type": "string",
                "maxLength": _MAX_ACTION,
            },
            "basis": {
                "description": (
                    "Optional short, bounded, human-readable note on WHY this rank "
                    "(e.g. 'combined risk 80 (critical); static finding severity high'). "
                    "Descriptive EVIDENCE, never a verdict."
                ),
                "type": "string",
                "maxLength": _MAX_BASIS,
            },
            "source_kind": {
                "description": (
                    "What this remediation was derived from: a correlation finding kind "
                    "(correlated / static_only / dynamic_only / contradiction) or a gap "
                    "type (static_uncorroborated / dynamic_unexplained / contradiction / "
                    "coverage). Descriptive traceability, never a verdict."
                ),
                "type": "string",
                "enum": sorted(set(FINDING_KINDS) | set(GAP_TYPES)),
            },
            "severity": _severity_prop(
                "The source finding / gap descriptive severity that fed the ranking. "
                "NOT a decision."
            ),
            "static_refs": _refs_prop(
                "Optional bounded short static-evidence references. Inert text "
                "references."
            ),
            "behavioral_refs": _refs_prop(
                "Optional bounded short behavioral-evidence references. Inert text "
                "references."
            ),
        },
    }


def _score_rollup() -> dict:
    """One echoed score in the assessment roll-up (traceability for the report). The
    NUMBER is 3.3's; 3.4 does NOT re-score — it only echoes + ranks over it."""
    return {
        "description": (
            "One risk score echoed from the 3.3 scoring_result for the report + the "
            "ranking basis. The number is 3.3's (3.4 does NOT re-score). 'score' is "
            "present ONLY when this lane's status is 'scored'. EVIDENCE, never a verdict."
        ),
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
                "enum": [
                    "scored",
                    "model_error",
                    "unparseable",
                    "skipped_no_evidence",
                ],
            },
            "score": {
                "description": (
                    "The 0-100 risk score (higher = riskier) from 3.3, present ONLY when "
                    "status is 'scored'. A descriptive EVIDENCE metric, never a decision."
                ),
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
            },
        },
    }


def _count_prop(desc: str) -> dict:
    return {
        "description": desc,
        "type": "integer",
        "minimum": 0,
        "maximum": _MAX_COUNT,
    }


SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://ztie.internal/schemas/remediation.contract.v1.json",
    "title": "ZTIE remediation-result (detailed findings + prioritized remediations) contract (v1)",
    "description": (
        "The bounded, DERIVED, verdict-free result produced by the Story 3.4 Hub-side "
        "findings + remediations step (RD-039) for one intake artifact. It reads the "
        "Story 3.3 (RD-038) `scoring_result` (three independent 0-100 Nova Pro risk "
        "scores: static / dynamic / combined) AND the Story 3.2 (RD-035) "
        "`correlation_result` (the categorized static<->dynamic findings) ALREADY on the "
        "Hub tracking item and produces (a) DETAILED FINDINGS for a human — the "
        "correlation findings surfaced, PLUS the migrated candidate-false-positive list "
        "(from `static_only` findings) and the gap list (static_uncorroborated / "
        "dynamic_unexplained / contradiction / coverage) that moved out of the old "
        "RD-037 3.3 synthesis — and (b) a PRIORITIZED REMEDIATION list ranked "
        "highest-risk-first by the three risk scores + the finding/gap severities. It is "
        "PURE post-processing (RD-039): the inputs are already structured, so it makes NO "
        "model call (no Bedrock client, no Bedrock grant) — unlike the 3.2 correlator + "
        "the 3.3 scorer. It is NOT a Forensic -> Hub crossing (its inputs already live "
        "Hub-side); it is a Hub-INTERNAL derived field written by the 3.4 Lambda, so it "
        "carries NO gate discriminator. It reasons ONLY over the derived Hub-side scores "
        "+ findings (RD-009): NEVER the raw payload / findings text / command log / raw "
        "trace, which never leave Forensic. It records its production HONESTLY via "
        "`status` (assessed / no_scores / skipped_no_evidence) and TOLERATES A PARTIAL "
        "scoring result — a score block may be non-scored and the ranking is done "
        "honestly over whichever scores are present (a missing score is never "
        "fabricated). It is NOT a verdict: there is NO "
        "verdict/safe/approved/forward/pass_fail/malicious/clean field anywhere; a "
        "remediation is 'fix X' (an action), NEVER 'reject the artifact' (a decision); "
        "the findings are EVIDENCE; the enforcement verdict (PASS/FAIL/INCONCLUSIVE) is "
        "Hub-side/human-gated (Story 3.5). Allow-list: additionalProperties false at "
        "every level; every field typed and enum/length/range-bounded; every array "
        "maxItems-capped. Integrity-keyed by intake_id + sha256. DERIVED-ONLY. OWN "
        "version pin (REMEDIATION_CONTRACT_VERSION)."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "contract_version",
        "intake_id",
        "sha256",
        "assessed_at",
        "status",
    ],
    "properties": {
        "contract_version": {
            "description": (
                "Remediation-contract schema version. Pinned SEPARATELY on the 3.4 "
                "Lambda (REMEDIATION_CONTRACT_VERSION) so this record versions "
                "independently of the shared CONTRACT_VERSION and every crossing kind's "
                "pin."
            ),
            "type": "string",
            "enum": ["1.0"],
        },
        "intake_id": {
            "description": (
                "The intake UUIDv4 this result is for. The 3.4 Lambda writes it back "
                "onto the tracking record keyed by this."
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
                "Integrity key, bound to intake_id; the 3.4 Lambda only writes onto the "
                "tracking record whose sha256 matches the evidence it assessed."
            ),
            "type": "string",
            "pattern": "^[0-9a-f]{64}$",
        },
        "assessed_at": {
            "description": (
                "RFC3339/ISO-8601 UTC timestamp (Z-suffixed) the 3.4 Lambda produced "
                "this result in the Hub. The only wall-clock field."
            ),
            "type": "string",
            "format": "date-time",
            "maxLength": 40,
        },
        "status": {
            "description": (
                "What the step actually did, recorded HONESTLY (assessed / no_scores / "
                "skipped_no_evidence). NOT a verdict — 'no_scores' says 3.3 has not "
                "landed, never that the artifact is safe/unsafe. When status != "
                "'assessed' the 'assessment' object is omitted."
            ),
            "type": "string",
            "enum": STATUSES,
        },
        "status_detail": {
            "description": (
                "Optional short, bounded, non-executable note about the status. Never "
                "raw content, never a verdict."
            ),
            "type": "string",
            "maxLength": _MAX_STATUS_DETAIL,
        },
        "rubric_version": {
            "description": (
                "The shared 0-100 risk-rubric version from the 3.3 scoring_result, "
                "carried through so the ranking is known to be over comparable scores."
            ),
            "type": "string",
            "maxLength": _MAX_RUBRIC_VERSION,
        },
        "combined_complete": {
            "description": (
                "The combined event's aggregation-completeness fact (from 3.1 via 3.3), "
                "carried for traceability + to drive the 'coverage' gap. An "
                "AGGREGATION-completeness fact, NEVER a verdict."
            ),
            "type": "boolean",
        },
        "correlation_status": {
            "description": (
                "The 3.2 correlation status the findings were drawn from (correlated / "
                "model_error / unparseable / skipped_no_signals), for traceability. NOT "
                "a verdict."
            ),
            "type": "string",
            "enum": [
                "correlated",
                "model_error",
                "unparseable",
                "skipped_no_signals",
            ],
        },
        "truncated": {
            "description": (
                "True iff any of the built lists (findings / candidate false positives / "
                "gaps / remediations) was capped at its maxItems (the tail dropped). A "
                "completeness fact, never a verdict."
            ),
            "type": "boolean",
        },
        "assessment": {
            "description": (
                "The findings view + prioritized remediations. Present ONLY when status "
                "is 'assessed'. EVIDENCE + a to-do list, never a verdict."
            ),
            "type": "object",
            "additionalProperties": False,
            "required": ["summary", "scores", "counts", "prioritized_remediations"],
            "properties": {
                "summary": {
                    "description": (
                        "A bounded, DETERMINISTIC narrative of the findings + how the "
                        "remediations were prioritized. Inert text; never a verdict, "
                        "never raw content."
                    ),
                    "type": "string",
                    "maxLength": _MAX_SUMMARY,
                },
                "scores": {
                    "description": (
                        "The three 3.3 risk scores echoed for the report + the ranking "
                        "basis (3.4 does NOT re-score). EVIDENCE, never a verdict."
                    ),
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["static", "dynamic", "combined"],
                    "properties": {
                        "static": _score_rollup(),
                        "dynamic": _score_rollup(),
                        "combined": _score_rollup(),
                        "highest_score": {
                            "description": (
                                "The maximum 0-100 score across the scored lanes (the "
                                "headline risk magnitude for the report). Omitted when no "
                                "lane scored. EVIDENCE, never a verdict."
                            ),
                            "type": "integer",
                            "minimum": 0,
                            "maximum": 100,
                        },
                        "highest_score_kind": {
                            "description": (
                                "Which lane carried the highest score (static / dynamic / "
                                "combined). Omitted when no lane scored. Descriptive, "
                                "never a verdict."
                            ),
                            "type": "string",
                            "enum": SCORE_KINDS,
                        },
                    },
                },
                "counts": {
                    "description": (
                        "Bounded by-kind counts over the correlation findings + the "
                        "derived lists. Descriptive EVIDENCE, never a verdict."
                    ),
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "correlated": _count_prop(
                            "Count of confirmed cross-lane correlation findings."
                        ),
                        "static_only": _count_prop(
                            "Count of static-only findings (candidate false positives)."
                        ),
                        "dynamic_only": _count_prop(
                            "Count of dynamic-only findings."
                        ),
                        "contradiction": _count_prop(
                            "Count of contradiction findings."
                        ),
                        "detailed_finding_count": _count_prop(
                            "Count of detailed findings surfaced."
                        ),
                        "candidate_false_positive_count": _count_prop(
                            "Count of candidate false positives surfaced."
                        ),
                        "gap_count": _count_prop("Count of gaps surfaced."),
                        "remediation_count": _count_prop(
                            "Count of prioritized remediations produced."
                        ),
                    },
                },
                "highest_finding_severity": _severity_prop(
                    "The worst descriptive severity across the detailed findings, rolled "
                    "up for the report. Omitted when there are no findings. EVIDENCE, "
                    "never a decision."
                ),
                "highest_gap_severity": _severity_prop(
                    "The worst descriptive severity across the gaps, rolled up for the "
                    "report. Omitted when there are no gaps. EVIDENCE, never a decision."
                ),
                "detailed_findings": {
                    "description": (
                        "The correlation findings surfaced for the human gate + report. "
                        "Capped at maxItems (recorded via top-level 'truncated'). "
                        "EVIDENCE only."
                    ),
                    "type": "array",
                    "maxItems": _MAX_ITEMS,
                    "items": _detailed_finding(),
                },
                "candidate_false_positives": {
                    "description": (
                        "The candidate-false-positive list (static-only findings). "
                        "Migrated from the old 3.3 synthesis. Capped at maxItems. "
                        "EVIDENCE only."
                    ),
                    "type": "array",
                    "maxItems": _MAX_ITEMS,
                    "items": _candidate_false_positive(),
                },
                "gaps": {
                    "description": (
                        "The gap list (static_uncorroborated / dynamic_unexplained / "
                        "contradiction / coverage). Migrated from the old 3.3 synthesis. "
                        "Capped at maxItems. EVIDENCE only."
                    ),
                    "type": "array",
                    "maxItems": _MAX_ITEMS,
                    "items": _gap(),
                },
                "prioritized_remediations": {
                    "description": (
                        "The prioritized remediation list, ranked highest-risk-first by "
                        "the three risk scores + the finding/gap severities. Capped at "
                        "maxItems. Each is an actionable, bounded, INERT to-do — EVIDENCE "
                        "+ a to-do, never a verdict."
                    ),
                    "type": "array",
                    "maxItems": _MAX_ITEMS,
                    "items": _remediation(),
                },
            },
        },
    },
}


# Repo-root-relative output paths (the canonical schema + the bundled lambda copy that
# must stay byte-in-sync). Consumed by scripts/gen_contracts.py.
OUT_PATHS = [
    ("schemas", "remediation.contract.v1.json"),
    ("lambdas", "hub_remediate", "remediation.contract.v1.json"),
]


def main() -> None:
    from contract_writer import resolve_out_paths, write_contract

    write_contract(SCHEMA, resolve_out_paths(OUT_PATHS))


if __name__ == "__main__":
    main()
