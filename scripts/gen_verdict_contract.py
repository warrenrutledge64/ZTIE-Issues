#!/usr/bin/env python3
"""Generate the ZTIE verdict-result data contract (Story 3.5, RD-040), v1.

Contract-first: this is the bounded, DERIVED verdict record the Phase-3 verdict step
(Story 3.5) records on the Hub tracking item after the Story 3.3 (RD-038) three risk
scores AND the Story 3.4 (RD-039) findings + remediations (and the Story 3.2 (RD-035)
correlation) have landed. It is the FIRST Phase-3 record that legitimately carries a
verdict-shaped field.

RD-040 — the enforcement verdict is a DETERMINISTIC, ADVISORY `recommended_verdict`
(PASS / FAIL / INCONCLUSIVE) that is NEVER acted upon:
  * ADVISORY, NEVER ACTED UPON. Nothing in ZTIE routes / promotes / destroys / moves an
    artifact based on `recommended_verdict`. The Phase-4 routing (4.6 ACCEPT / 4.7
    REJECT / INCONCLUSIVE hold) is driven SOLELY by a HUMAN actively selecting PASS or
    FAIL on the dashboard. 3.5 writes ONLY its recommendation + an explicit
    `human_decision: pending` marker; the human's actual selection is a SEPARATE field
    owned by the human, written later at the gate (Phase 4). 3.5 NEVER pre-populates or
    implies it. The advisory field is deliberately named `recommended_verdict` (NOT a
    bare `verdict`) so no downstream stage can mistake it for the effective decision.
  * PURE + DETERMINISTIC (no model call — like 3.4). The inputs are already structured,
    so the mapping is reproducible + auditable; a model DECIDING the verdict would
    undercut "the model characterizes, the rules/human decide". So — UNLIKE the 3.2
    correlator + the 3.3 scorer — the 3.5 Lambda has NO Bedrock client and NO Bedrock
    grant.
  * DRIVEN BY THE `combined` SCORE — NEVER a re-aggregation of the three lane scores.
    The `combined` score is RD-038's own whole-picture assessment; 3.5 keys off it and
    must NOT blend static / dynamic / combined into a new number (that would reintroduce
    the RD-038 arithmetic-over-scores anti-pattern one layer down). On the shared 0-100
    rubric (higher = riskier): combined <= 29 -> PASS; combined 30-74 -> INCONCLUSIVE;
    combined >= 75 -> FAIL. FORCE INCONCLUSIVE regardless of score if a `contradiction`
    finding is present OR the evidence is incomplete (a `coverage` gap /
    combined_complete=false / a partial scoring_result — any lane model_error /
    unparseable / skipped_no_evidence / `combined` itself not `scored` /
    remediation_result.status != assessed). A high-severity gap pushes toward
    INCONCLUSIVE (human look), NEVER an auto-FAIL — FAIL is reserved for a genuinely
    high `combined` score. Static / dynamic appear in the basis as context, never
    re-blended.

Like the combined-event (3.1), correlation (3.2), scoring (3.3) and remediation (3.4)
contracts, and for the SAME reasons, it is NOT a Forensic -> Hub crossing: its inputs
(the 3.3 `scoring_result` + the 3.4 `remediation_result`) ALREADY live on the Hub
tracking item. So 3.5 READS that derived Hub-side data -> deterministically maps it to a
recommended verdict -> writes the verdict result back onto the SAME item. It makes NO
model call (RD-040: PURE); it reasons ONLY over the derived Hub-side scores + findings
(RD-009) — never the raw payload / raw trace, which never leave Forensic; no durable
store is added to the Forensic blast zone (RD-012). It is a Hub-INTERNAL derived field,
so it carries NO gate discriminator.

Run:  python3 scripts/gen_verdict_contract.py

WHAT THIS RECORD IS (and IS NOT):
  * It records an ADVISORY `recommended_verdict` (PASS / FAIL / INCONCLUSIVE) + a
    bounded `recommendation_basis` (which combined score + which override drove it, with
    static / dynamic as context) + an explicit `human_decision` marker that is ALWAYS
    `pending` on this record (3.5 never writes the human's actual selection).
  * It records its production HONESTLY via `status` (recommended / no_scores /
    incomplete). It TOLERATES incomplete evidence: incompleteness maps to a
    `recommended_verdict` of INCONCLUSIVE (never a fabricated PASS / FAIL).
  * The recommendation is NOT an effective decision. There is deliberately NO bare
    `verdict` / `safe` / `approved` / `forward` / `pass_fail` / `malicious` / `clean`
    field, and NO field carrying the human's actual selection. `human_decision` is
    enumerated to the single value `pending` so this record can NEVER assert a made
    decision. The enforcement decision is a HUMAN action at the Phase-4 gate.

Design invariants (mirror the crossing contracts, RD-013 / RD-014 / RD-016):
  * allow-list — additionalProperties:false at every level; every field typed and
    enum/length/range-bounded; every array maxItems-capped.
  * integrity-keyed — bound to intake_id + sha256.
  * DERIVED-ONLY (RD-009) — reasons over the bounded derived scores + findings; the
    record references nothing raw.
  * ADVISORY-ONLY (RD-040) — a recommendation, never an acted-upon decision; the human
    decision stays `pending` here.
  * OWN VERSION PIN — contract_version enum ['1.0'], pinned SEPARATELY via
    VERDICT_CONTRACT_VERSION (never rides the shared CONTRACT_VERSION).
"""

from __future__ import annotations

# The advisory recommended verdict vocabulary (RD-040). These are RECOMMENDATIONS the
# dashboard surfaces + the human triages on; they are NEVER acted upon automatically.
RECOMMENDED_VERDICTS = [
    "PASS",
    "FAIL",
    "INCONCLUSIVE",
]

# The overall production status. Records what the step actually did, HONESTLY.
#   recommended  — a recommended_verdict was derived (PASS / FAIL / INCONCLUSIVE).
#   no_scores    — no `scoring_result` was on the tracking item yet (3.3 has not
#                  landed), so there was nothing to recommend over.
#   incomplete   — a scoring_result was present but the evidence was incomplete (a
#                  partial scoring_result / combined not scored / etc.); the
#                  recommended_verdict is INCONCLUSIVE. (This is still a 'recommended'
#                  record with recommended_verdict=INCONCLUSIVE; 'incomplete' is the
#                  honest status label for WHY.)
STATUSES = [
    "recommended",
    "no_scores",
    "incomplete",
]

# The single legal value of the human-decision marker on THIS record. 3.5 NEVER writes
# the human's actual selection; it only records that the human decision is still
# outstanding. Enumerated to exactly one value so the record can never assert a made
# decision.
HUMAN_DECISION_PENDING = ["pending"]

# The lane a score refers to (context echoed into the basis; combined is the driver).
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

# The reason an override forced INCONCLUSIVE (or the fact that the score alone drove
# it). Descriptive traceability for the basis, never a verdict.
BASIS_DRIVERS = [
    # The combined score alone drove the recommendation (no override fired).
    "combined_score",
    # A contradiction finding forced INCONCLUSIVE.
    "contradiction_present",
    # The evidence was incomplete (coverage gap / combined_complete=false / partial
    # scoring / combined not scored / remediation not assessed) -> forced INCONCLUSIVE.
    "incomplete_evidence",
    # No lane scored at all -> nothing to score over -> INCONCLUSIVE.
    "no_score_available",
]

_MAX_SUMMARY = 4000
_MAX_NOTE = 1024
_MAX_REASON = 256
_MAX_REASONS = 20
_MAX_STATUS_DETAIL = 512
_MAX_CONTRACT_VERSION = 16
_MAX_RUBRIC_VERSION = 16


def _score_echo(desc: str) -> dict:
    """One echoed lane score in the basis (context/traceability). The NUMBER is 3.3's;
    3.5 does NOT re-score and does NOT re-blend. `score` is present ONLY when the lane's
    status is 'scored'."""
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
                    "status is 'scored'. Context echoed into the basis; the `combined` "
                    "lane is the DRIVER, static/dynamic are context (never re-blended). "
                    "A descriptive EVIDENCE metric, never a decision."
                ),
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
            },
        },
    }


SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://ztie.internal/schemas/verdict.contract.v1.json",
    "title": "ZTIE verdict-result (advisory recommended verdict) contract (v1)",
    "description": (
        "The bounded, DERIVED, ADVISORY verdict record produced by the Story 3.5 "
        "Hub-side verdict step (RD-040) for one intake artifact. It reads the Story 3.3 "
        "(RD-038) `scoring_result` (three independent 0-100 Nova Pro risk scores: static "
        "/ dynamic / combined) AND the Story 3.4 (RD-039) `remediation_result` (findings "
        "+ gaps) / the Story 3.2 (RD-035) correlation ALREADY on the Hub tracking item "
        "and DETERMINISTICALLY maps them to a `recommended_verdict` (PASS / FAIL / "
        "INCONCLUSIVE) + a bounded `recommendation_basis` + an explicit `human_decision` "
        "marker that is ALWAYS `pending`. It is PURE (RD-040): the mapping is "
        "deterministic + reproducible + auditable, so it makes NO model call (no Bedrock "
        "client, no Bedrock grant) — unlike the 3.2 correlator + the 3.3 scorer. It is "
        "NOT a Forensic -> Hub crossing (its inputs already live Hub-side); it is a "
        "Hub-INTERNAL derived field written by the 3.5 Lambda, so it carries NO gate "
        "discriminator. It reasons ONLY over the derived Hub-side scores + findings "
        "(RD-009): NEVER the raw payload / findings text / command log / raw trace, "
        "which never leave Forensic. The `recommended_verdict` is DRIVEN BY THE "
        "`combined` score (RD-038's own whole-picture number) and is NEVER a "
        "re-aggregation of the three lane scores: combined <= 29 -> PASS; combined 30-74 "
        "-> INCONCLUSIVE; combined >= 75 -> FAIL; and it is FORCED to INCONCLUSIVE "
        "regardless of score when a `contradiction` finding is present or the evidence "
        "is incomplete (a partial scoring_result / coverage gap / combined_complete=false "
        "/ combined not scored / remediation not assessed). A high-severity gap pushes "
        "toward INCONCLUSIVE, never an auto-FAIL. CRUCIALLY, the recommendation is "
        "ADVISORY and NEVER ACTED UPON: nothing in ZTIE routes / promotes / destroys / "
        "moves an artifact based on it; the enforcement decision is a HUMAN actively "
        "selecting PASS or FAIL at the Phase-4 dashboard gate. This record therefore "
        "carries ONLY the recommendation + `human_decision: pending`; it NEVER carries "
        "the human's actual selection (a separate, human-owned field written later in "
        "Phase 4), and the advisory field is named `recommended_verdict` (NOT a bare "
        "`verdict`) so no downstream stage mistakes it for the effective decision. "
        "Allow-list: additionalProperties false at every level; every field typed and "
        "enum/length/range-bounded; every array maxItems-capped. Integrity-keyed by "
        "intake_id + sha256. DERIVED-ONLY. OWN version pin (VERDICT_CONTRACT_VERSION)."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "contract_version",
        "intake_id",
        "sha256",
        "recommended_at",
        "status",
        "recommended_verdict",
        "human_decision",
    ],
    "properties": {
        "contract_version": {
            "description": (
                "Verdict-contract schema version. Pinned SEPARATELY on the 3.5 Lambda "
                "(VERDICT_CONTRACT_VERSION) so this record versions independently of the "
                "shared CONTRACT_VERSION and every other kind's pin."
            ),
            "type": "string",
            "enum": ["1.0"],
            "maxLength": _MAX_CONTRACT_VERSION,
        },
        "intake_id": {
            "description": (
                "The intake UUIDv4 this result is for. The 3.5 Lambda writes it back "
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
                "Integrity key, bound to intake_id; the 3.5 Lambda only writes onto the "
                "tracking record whose sha256 matches the evidence it recommended over."
            ),
            "type": "string",
            "pattern": "^[0-9a-f]{64}$",
        },
        "recommended_at": {
            "description": (
                "RFC3339/ISO-8601 UTC timestamp (Z-suffixed) the 3.5 Lambda produced "
                "this recommendation in the Hub. The only wall-clock field."
            ),
            "type": "string",
            "format": "date-time",
            "maxLength": 40,
        },
        "status": {
            "description": (
                "What the step actually did, recorded HONESTLY (recommended / no_scores "
                "/ incomplete). NOT a verdict — 'no_scores' says 3.3 has not landed, "
                "never that the artifact is safe/unsafe. 'incomplete' means the evidence "
                "was incomplete so the recommended_verdict is INCONCLUSIVE."
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
        "recommended_verdict": {
            "description": (
                "The ADVISORY recommended verdict (PASS / FAIL / INCONCLUSIVE) the "
                "dashboard surfaces + the human triages on. It is NEVER acted upon "
                "automatically — nothing in ZTIE routes/promotes/destroys/moves an "
                "artifact based on it. A recommendation, NOT the effective decision "
                "(which is a human selection at the Phase-4 gate). Deliberately named "
                "`recommended_verdict` (not `verdict`) so no downstream stage mistakes "
                "it for the effective decision. Present on every record: on no_scores it "
                "is INCONCLUSIVE (nothing to recommend over yet)."
            ),
            "type": "string",
            "enum": RECOMMENDED_VERDICTS,
        },
        "human_decision": {
            "description": (
                "The human accept/reject decision marker on THIS record. ALWAYS "
                "`pending` — 3.5 NEVER writes the human's actual selection; that is a "
                "SEPARATE, human-owned field written later at the Phase-4 dashboard gate. "
                "Enumerated to exactly one value so this record can never assert a made "
                "decision. Preserves the human-gate covenant: the recommendation "
                "INFORMS; the human DECIDES + ACTS."
            ),
            "type": "string",
            "enum": HUMAN_DECISION_PENDING,
        },
        "rubric_version": {
            "description": (
                "The shared 0-100 risk-rubric version from the 3.3 scoring_result, "
                "carried through so the recommendation is known to be over comparable "
                "scores."
            ),
            "type": "string",
            "maxLength": _MAX_RUBRIC_VERSION,
        },
        "recommendation_basis": {
            "description": (
                "The bounded, DETERMINISTIC basis for the recommended_verdict: which "
                "combined score + which override (if any) drove it, with static/dynamic "
                "as context. EVIDENCE + rationale, never a verdict, never raw content. "
                "Present when status is 'recommended' or 'incomplete'."
            ),
            "type": "object",
            "additionalProperties": False,
            "required": ["driver", "summary"],
            "properties": {
                "driver": {
                    "description": (
                        "WHY the recommendation is what it is: 'combined_score' (the "
                        "combined score alone drove it, no override), "
                        "'contradiction_present' (a contradiction finding forced "
                        "INCONCLUSIVE), 'incomplete_evidence' (incomplete evidence forced "
                        "INCONCLUSIVE), or 'no_score_available' (no lane scored). "
                        "Descriptive traceability, never a verdict."
                    ),
                    "type": "string",
                    "enum": BASIS_DRIVERS,
                },
                "combined_score": {
                    "description": (
                        "The 0-100 `combined` risk score that drives the recommendation "
                        "(RD-038's whole-picture number), present ONLY when the combined "
                        "lane is 'scored'. The DRIVER of the mapping. Omitted when "
                        "combined did not score. Descriptive EVIDENCE, never a verdict."
                    ),
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                },
                "combined_status": {
                    "description": (
                        "The `combined` lane's 3.3 score status (scored / model_error / "
                        "unparseable / skipped_no_evidence), carried through honestly. "
                        "A non-'scored' combined status is one of the incompleteness "
                        "signals that forces INCONCLUSIVE. NOT a verdict."
                    ),
                    "type": "string",
                    "enum": SCORE_STATUSES,
                },
                "scores": {
                    "description": (
                        "The three 3.3 lane scores echoed for CONTEXT + traceability "
                        "(the `combined` lane is the driver; static/dynamic are context "
                        "and are NEVER re-blended into a new number). EVIDENCE, never a "
                        "verdict."
                    ),
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["static", "dynamic", "combined"],
                    "properties": {
                        "static": _score_echo(
                            "The static lane's 3.3 score, echoed as CONTEXT only (never "
                            "re-blended). EVIDENCE, never a verdict."
                        ),
                        "dynamic": _score_echo(
                            "The dynamic lane's 3.3 score, echoed as CONTEXT only (never "
                            "re-blended). EVIDENCE, never a verdict."
                        ),
                        "combined": _score_echo(
                            "The combined lane's 3.3 score — the DRIVER of the "
                            "recommendation (RD-038's whole-picture number). EVIDENCE, "
                            "never a verdict."
                        ),
                    },
                },
                "contradiction_present": {
                    "description": (
                        "True iff a `contradiction` finding was present (the lanes "
                        "disagree), which FORCES the recommended_verdict to INCONCLUSIVE "
                        "regardless of the combined score. A descriptive fact, never a "
                        "verdict."
                    ),
                    "type": "boolean",
                },
                "evidence_complete": {
                    "description": (
                        "True iff the evidence was complete enough to recommend a "
                        "score-driven PASS/FAIL (all incompleteness checks passed). When "
                        "false, the recommended_verdict is FORCED to INCONCLUSIVE. An "
                        "AGGREGATION/completeness fact, never a verdict."
                    ),
                    "type": "boolean",
                },
                "highest_gap_severity": {
                    "description": (
                        "The worst gap severity seen (context). A high-severity gap "
                        "pushes toward INCONCLUSIVE (human look), NEVER an auto-FAIL. "
                        "Descriptive EVIDENCE, never a verdict."
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
                "override_reasons": {
                    "description": (
                        "Bounded list of the specific incompleteness/override reasons "
                        "that forced INCONCLUSIVE (e.g. 'combined_not_scored', "
                        "'coverage_gap', 'combined_incomplete', 'remediation_not_"
                        "assessed', 'static_not_scored'). Descriptive traceability, inert "
                        "text, never a verdict."
                    ),
                    "type": "array",
                    "maxItems": _MAX_REASONS,
                    "items": {"type": "string", "maxLength": _MAX_REASON},
                },
                "summary": {
                    "description": (
                        "A bounded, DETERMINISTIC narrative of WHY this recommendation "
                        "(the combined score + any override). Inert text; explicitly "
                        "frames the result as an ADVISORY recommendation the human gates, "
                        "never a verdict, never raw content."
                    ),
                    "type": "string",
                    "maxLength": _MAX_SUMMARY,
                },
                "cut_lines_note": {
                    "description": (
                        "Optional short, bounded, non-executable note echoing the "
                        "RD-040 cut lines used (<=29 PASS / 30-74 INCONCLUSIVE / >=75 "
                        "FAIL). Descriptive, never a verdict."
                    ),
                    "type": "string",
                    "maxLength": _MAX_NOTE,
                },
            },
        },
    },
}


# Repo-root-relative output paths (the canonical schema + the bundled lambda copy that
# must stay byte-in-sync). Consumed by scripts/gen_contracts.py.
OUT_PATHS = [
    ("schemas", "verdict.contract.v1.json"),
    ("lambdas", "hub_verdict", "verdict.contract.v1.json"),
]


def main() -> None:
    from contract_writer import resolve_out_paths, write_contract

    write_contract(SCHEMA, resolve_out_paths(OUT_PATHS))


if __name__ == "__main__":
    main()
