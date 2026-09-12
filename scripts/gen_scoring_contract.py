#!/usr/bin/env python3
"""Generate the ZTIE scoring-result data contract (Story 3.3, RD-038), v1.

Contract-first: this is the bounded, DERIVED, verdict-free scoring result the Phase-3
risk-scoring step (Story 3.3, reworked per RD-038) records on the Hub tracking item
after Amazon Nova Pro (RD-003) produces THREE INDEPENDENT 0-100 risk scores for one
intake artifact:

  * a STATIC risk score  — Nova Pro over ONLY the static lane's derived evidence,
  * a DYNAMIC risk score — Nova Pro over ONLY the dynamic lane's derived evidence,
  * a COMBINED risk score — Nova Pro over BOTH lanes' derived evidence TOGETHER (its
    own independent assessment, NOT a formula over the two lane scores).

All three come from Amazon Nova Pro via THREE SEPARATE, evidence-scoped calls, on a
SHARED 0-100 rubric so the scores are directly comparable (higher = riskier). This
supersedes the RD-037 `synthesis.contract.v1` (`accuracy` + `gap_analysis`); the
`accuracy_score` is DROPPED and the list-shaped synthesis content (candidate false
positives + gaps) migrates to Story 3.4.

Like the combined-event (3.1) and correlation (3.2) contracts, and for the SAME
reasons, it is NOT a Forensic -> Hub crossing: its inputs (the derived per-lane
evidence + the 3.1 combined event) ALREADY live on the Hub tracking item. So 3.3
READS that evidence -> invokes Nova Pro three times -> writes the scoring result back
onto the SAME item. RD-009 / RD-013 stay intact (Nova Pro sees only the derived,
sanitized, bounded evidence — never the raw payload / raw trace, which never leave
Forensic); no durable store is added to the Forensic blast zone (RD-012). It is a
Hub-INTERNAL derived field, so it carries NO gate discriminator.

Run:  python3 scripts/gen_scoring_contract.py

WHAT THIS RECORD IS (and IS NOT):
  * It records THREE risk scores (static / dynamic / combined), each a bounded 0-100
    integer + a bounded model-produced rationale, EVIDENCE the Phase-4 human gate +
    the 3.4 remediations + the 3.5 verdict reason over.
  * It records EACH score's invocation HONESTLY via its OWN `status` (scored /
    model_error / unparseable / skipped_no_evidence) + model metadata (model_id,
    attempts so the retry is inspectable, latency, tokens, truncated). Because the
    three calls are INDEPENDENT, a PARTIAL result is legitimate: one score may be
    `model_error` while the other two are `scored` — recorded honestly, never
    fabricated.
  * It NEVER contains a verdict. There is deliberately NO verdict / safe / approved /
    forward / pass_fail / malicious / clean field ANYWHERE. A risk score is a
    descriptive EVIDENCE metric (higher = riskier), NOT a safety decision: a high
    score is not "FAIL" and a low score is not "PASS". The verdict stays Hub-side /
    human-gated (Story 3.5).

Design invariants (mirror the crossing contracts, RD-013 / RD-014 / RD-016):
  * allow-list — additionalProperties:false at every level; every field typed and
    enum/length/range-bounded.
  * integrity-keyed — bound to intake_id + sha256.
  * DERIVED-ONLY (RD-009) — Nova Pro reasons over the bounded derived evidence; the
    record references nothing raw.
  * ZERO-TRUST (RD-014) — every score is EVIDENCE, never a verdict.
  * OWN VERSION PIN — contract_version enum ['1.0'], pinned SEPARATELY via
    SCORING_CONTRACT_VERSION (never rides the shared CONTRACT_VERSION).
"""

from __future__ import annotations

# Per-score status. Records what THAT score's Nova Pro call actually did, HONESTLY,
# so a failed/absent call is never hidden behind a fabricated number. NONE is a
# safety verdict.
#   scored               — Nova Pro returned a response parsed into a bounded 0-100
#                          risk score.
#   model_error          — the Bedrock call failed after exhausting the retry budget
#                          (throttling / 5xx / timeout); no score was produced.
#   unparseable          — the model returned a response, but no bounded 0-100 score
#                          could be parsed from it; no score was fabricated.
#   skipped_no_evidence  — the lane's evidence needed for this score was absent (e.g.
#                          the static lane had not landed), so no call was made.
SCORE_STATUSES = [
    "scored",
    "model_error",
    "unparseable",
    "skipped_no_evidence",
]

# The three score kinds (documentation only; the schema fixes them as named
# properties static/dynamic/combined so their meaning is explicit + allow-listed).
_MAX_RATIONALE = 4000
_MAX_STATUS_DETAIL = 512
_MAX_MODEL_ID = 256
_MAX_ATTEMPTS = 100
_MAX_TOKENS = 1000000
_MAX_LATENCY_MS = 3600000
_MAX_RUBRIC_VERSION = 16
_MAX_CONTRACT_VERSION = 16


def _score_block(kind: str, evidence_desc: str) -> dict:
    """One risk-score block (static / dynamic / combined). A bounded 0-100 score +
    rationale + honest per-call status + model metadata. EVIDENCE, never a verdict.
    """
    return {
        "description": (
            f"The {kind} risk score: Amazon Nova Pro's 0-100 risk assessment "
            f"({evidence_desc}). HIGHER = RISKIER, on the shared rubric "
            f"(rubric_version). EVIDENCE only, NOT a verdict (a high score is not "
            f"'FAIL'; a low score is not 'PASS'). The invocation is recorded HONESTLY "
            f"via 'status'; 'score' is present ONLY when status is 'scored' (no score "
            f"is fabricated for a failed/absent call)."
        ),
        "type": "object",
        "additionalProperties": False,
        "required": ["status"],
        "properties": {
            "status": {
                "description": (
                    "What this score's Nova Pro call did, HONESTLY (scored / "
                    "model_error / unparseable / skipped_no_evidence). NOT a verdict."
                ),
                "type": "string",
                "enum": SCORE_STATUSES,
            },
            "score": {
                "description": (
                    "The 0-100 risk score (higher = riskier), on the shared rubric. "
                    "Present ONLY when status is 'scored'. A descriptive EVIDENCE "
                    "metric, never a safety decision."
                ),
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
            },
            "rationale": {
                "description": (
                    "The model's bounded, inert prose explanation for the score. "
                    "Never a verdict, never raw content. Present when status is "
                    "'scored'."
                ),
                "type": "string",
                "maxLength": _MAX_RATIONALE,
            },
            "status_detail": {
                "description": (
                    "Optional short, bounded, non-executable note about the status "
                    "(e.g. 'ThrottlingException after 5 attempts', 'no static "
                    "evidence present'). Never raw content, never a verdict."
                ),
                "type": "string",
                "maxLength": _MAX_STATUS_DETAIL,
            },
            "model_id": {
                "description": (
                    "The Bedrock model / inference-profile id invoked for this score "
                    "(RD-003, Nova Pro). Recorded for traceability."
                ),
                "type": "string",
                "maxLength": _MAX_MODEL_ID,
            },
            "attempts": {
                "description": (
                    "Number of Bedrock invocation attempts for this score, including "
                    "the final one (so the exponential-backoff retry is inspectable: "
                    "1 = first try; >1 = retried). Bounded."
                ),
                "type": "integer",
                "minimum": 0,
                "maximum": _MAX_ATTEMPTS,
            },
            "latency_ms": {
                "description": (
                    "Optional wall-clock duration (ms) of the successful Bedrock "
                    "invocation for this score. Bounded."
                ),
                "type": "integer",
                "minimum": 0,
                "maximum": _MAX_LATENCY_MS,
            },
            "input_tokens": {
                "description": (
                    "Optional input token count reported by Bedrock usage metadata "
                    "for this score (cost observability). Bounded."
                ),
                "type": "integer",
                "minimum": 0,
                "maximum": _MAX_TOKENS,
            },
            "output_tokens": {
                "description": (
                    "Optional output token count reported by Bedrock usage metadata "
                    "for this score (cost observability). Bounded."
                ),
                "type": "integer",
                "minimum": 0,
                "maximum": _MAX_TOKENS,
            },
        },
    }


SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://ztie.internal/schemas/scoring.contract.v1.json",
    "title": "ZTIE scoring-result (three independent Nova Pro risk scores) contract (v1)",
    "description": (
        "The bounded, DERIVED, verdict-free scoring result produced by the Story 3.3 "
        "Hub-side risk-scoring step (RD-038) for one intake artifact. Amazon Nova Pro "
        "(RD-003) produces THREE INDEPENDENT 0-100 risk scores via THREE SEPARATE, "
        "evidence-scoped calls: a STATIC score (Nova Pro over ONLY the static lane's "
        "derived evidence), a DYNAMIC score (Nova Pro over ONLY the dynamic lane's "
        "derived evidence, a peer of static), and a COMBINED score (Nova Pro over BOTH "
        "lanes' derived evidence TOGETHER, its own independent assessment — NOT a "
        "formula over the two lane scores). All three are on a SHARED 0-100 rubric "
        "(rubric_version) so they are directly comparable; higher = riskier. It is NOT "
        "a Forensic -> Hub crossing (its inputs already live Hub-side); it is a "
        "Hub-INTERNAL derived field written by the 3.3 scorer Lambda, so it carries NO "
        "gate discriminator. Nova Pro reasons ONLY over the bounded, sanitized, "
        "derived evidence on the Hub (RD-009): NEVER the raw payload / findings text / "
        "command log / raw trace, which never leave Forensic. Each score records its "
        "invocation HONESTLY via its OWN 'status' (scored / model_error / unparseable "
        "/ skipped_no_evidence) + model metadata (model_id, attempts so the retry is "
        "inspectable, latency, tokens) — so a failed/absent call is never hidden "
        "behind a fabricated number, and a PARTIAL result (one score failed, the other "
        "two scored) is legitimate. It is NOT a verdict: there is NO "
        "verdict/safe/approved/forward/pass_fail/malicious/clean field anywhere; a risk "
        "score is a descriptive EVIDENCE metric (higher = riskier), NOT a decision (a "
        "high score is not 'FAIL', a low score is not 'PASS'); the verdict is Hub-side/"
        "human-gated (Story 3.5). Supersedes the RD-037 synthesis.contract.v1 (the "
        "accuracy_score is dropped; the candidate-false-positive + gap lists migrate to "
        "Story 3.4). Allow-list: additionalProperties false at every level; every field "
        "typed and enum/length/range-bounded. Integrity-keyed by intake_id + sha256. "
        "DERIVED-ONLY. OWN version pin (SCORING_CONTRACT_VERSION)."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "contract_version",
        "intake_id",
        "sha256",
        "scored_at",
        "static",
        "dynamic",
        "combined",
    ],
    "properties": {
        "contract_version": {
            "description": (
                "Scoring-contract schema version. Pinned SEPARATELY on the 3.3 scorer "
                "(SCORING_CONTRACT_VERSION) so this record versions independently of "
                "the shared CONTRACT_VERSION and every crossing kind's pin."
            ),
            "type": "string",
            "enum": ["1.0"],
        },
        "intake_id": {
            "description": (
                "The intake UUIDv4 this scoring is for. The scorer writes it back "
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
                "Integrity key, bound to intake_id; the scorer only writes onto the "
                "tracking record whose sha256 matches the evidence it scored."
            ),
            "type": "string",
            "pattern": "^[0-9a-f]{64}$",
        },
        "scored_at": {
            "description": (
                "RFC3339/ISO-8601 UTC timestamp (Z-suffixed) the scorer produced this "
                "result in the Hub. The only wall-clock field."
            ),
            "type": "string",
            "format": "date-time",
            "maxLength": 40,
        },
        "rubric_version": {
            "description": (
                "The shared 0-100 risk-rubric version stated in all three Nova Pro "
                "prompts. Recorded so the three scores are known to be on the SAME "
                "comparable scale (a '40' means the same risk magnitude across the "
                "static / dynamic / combined scores)."
            ),
            "type": "string",
            "maxLength": _MAX_RUBRIC_VERSION,
        },
        "combined_complete": {
            "description": (
                "The combined event's aggregation-completeness fact (from 3.1) at the "
                "time of scoring — whether all lanes' evidence had landed. Carried for "
                "traceability. An AGGREGATION-completeness fact, NEVER a verdict; a "
                "score may be honest over incomplete evidence (the missing lane's "
                "score is 'skipped_no_evidence')."
            ),
            "type": "boolean",
        },
        "static": _score_block(
            "static",
            "the static lane's derived evidence ONLY — the static-scan findings + "
            "severities",
        ),
        "dynamic": _score_block(
            "dynamic",
            "the dynamic lane's derived evidence ONLY — the sanitized behavioral "
            "telemetry + run outcome",
        ),
        "combined": _score_block(
            "combined",
            "BOTH lanes' derived evidence together — its own independent assessment, "
            "not a formula over the static + dynamic scores",
        ),
    },
}


# Repo-root-relative output paths (the canonical schema + the bundled lambda copy
# that must stay byte-in-sync). Consumed by scripts/gen_contracts.py.
OUT_PATHS = [
    ("schemas", "scoring.contract.v1.json"),
    ("lambdas", "hub_synthesize", "scoring.contract.v1.json"),
]


def main() -> None:
    from contract_writer import resolve_out_paths, write_contract

    write_contract(SCHEMA, resolve_out_paths(OUT_PATHS))


if __name__ == "__main__":
    main()
