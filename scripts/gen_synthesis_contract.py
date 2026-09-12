#!/usr/bin/env python3
"""Generate the ZTIE synthesis-result data contract (Story 3.3, RD-037), v1.

Contract-first: this is the bounded, DERIVED, verdict-free SYNTHESIS result the
Phase-3 accuracy + gap_analysis synthesizer (Story 3.3) records on the Hub tracking
item after it reads the ONE verdict-free Nova Pro correlation result (Story 3.2,
RD-035) already on that item and (a) scores how well the correlation ELIMINATES
FALSE POSITIVES (a static flag that the dynamic evidence shows was never exercised
is a candidate false positive) and (b) surfaces where the two lanes DISAGREE or
leave a GAP.

Like the combined-event (3.1) and correlation (3.2) contracts, and for the SAME
reasons, it is deliberately DIFFERENT from the RD-013 crossing envelopes:

  * It is NOT a Forensic -> Hub crossing. Its input (the ``correlation_result``)
    ALREADY lives on the Hub tracking record (3.2 wrote it there Hub-side). So 3.3
    is a Hub-SIDE derivation (read the tracking item's correlation result ->
    synthesize -> write the synthesis result back onto the SAME item), NOT a new
    crossing. This keeps the RD-009 / RD-013 boundary intact (no raw data
    re-crossed, no full detail duplicated) and adds NO durable store to the
    Forensic blast zone (RD-012). Because it never travels over SQS through the Hub
    gate, it carries NO unique top-level discriminator and needs no new gate
    dispatch branch. It is a Hub-internal DERIVED field on the tracking item,
    written by the Story 3.3 synthesizer Lambda (DynamoDB-Streams-triggered off the
    tracking table).
  * It STILL gets its own contract + OWN version pin (SYNTHESIS_CONTRACT_VERSION)
    and the full evidence-never-verdict discipline, because it is the exact shape
    the unified threat scoring (3.4) consumes and must be bounded / allow-listed
    just like every crossing contract.

Run:  python3 scripts/gen_synthesis_contract.py

WHY 3.3 IS PURE POST-PROCESSING, NOT A SECOND NOVA PRO CALL (RD-037):
  * The semantic static<->dynamic reasoning was ALREADY done by Nova Pro in 3.2:
    the correlation result carries DISCRETE, categorized findings, each with a
    ``kind`` in {correlated, static_only, dynamic_only, contradiction} and a
    descriptive severity. accuracy + gap_analysis are DETERMINISTIC aggregations
    over that already-structured evidence — count the candidate false positives
    (static_only findings the behavior never exercised), tally the confirmed
    correlations, and enumerate the contradictions + lane gaps. A second model call
    would add cost, non-determinism, and another verdict-injection surface for NO
    analytical gain, and would make the synthesis non-reproducible. Doing it in
    PURE logic keeps 3.3 fully reproducible + offline-testable and needs NO Bedrock
    grant at all.

WHAT THIS RECORD IS (and IS NOT):
  * It records a SYNTHESIS of the 3.2 correlation: an ``accuracy`` block (candidate
    false positives reconciled against benign dynamic evidence + a descriptive
    accuracy score + counts by correlation kind) and a ``gaps`` block (the
    static-uncorroborated, dynamic-unexplained and contradiction observations that
    the human gate + 3.4 must weigh), plus a bounded narrative ``summary``. It is
    EVIDENCE the Phase-4 human gate and the 3.4 unified scoring reason over.
  * It records the synthesis HONESTLY: a ``status`` (synthesized / no_correlation /
    skipped_no_findings). When the upstream correlation is absent or its status is
    not 'correlated', the status RECORDS that and NO synthesis is fabricated (the
    same honesty discipline as 3.1's absent inputs / 3.2's model_error).
  * It NEVER contains a verdict. There is deliberately NO verdict / safe / approved
    / forward / pass_fail / malicious / clean field ANYWHERE. The ``accuracy_score``
    is a descriptive EVIDENCE metric (how much of the flagged static evidence the
    dynamic behavior reconciled), NOT a safety decision; ``severity`` roll-ups
    describe EVIDENCE, never a decision; the verdict stays Hub-side / human-gated
    (Phase 4), downstream.

Design invariants (mirror the crossing contracts, RD-013 / RD-014 / RD-016):
  * allow-list — additionalProperties:false at every level; every field typed and
    enum/length/range-bounded; every array maxItems-capped.
  * integrity-keyed — bound to intake_id + sha256 so the synthesis can only
    describe the exact artifact all lanes inspected + 3.1 normalized + 3.2
    correlated.
  * DERIVED-ONLY (RD-009) — no raw body / findings text / command log / raw trace.
    The synthesis reasons over 3.2's bounded correlation result; it references
    nothing raw and duplicates nothing from Forensic.
  * ZERO-TRUST (RD-014) — the synthesis result is EVIDENCE, never a verdict.
  * OWN VERSION PIN — contract_version enum ['1.0'], pinned SEPARATELY via
    SYNTHESIS_CONTRACT_VERSION (never rides the shared CONTRACT_VERSION).
"""

from __future__ import annotations

# The synthesis status. Records what actually happened HONESTLY so an absent /
# non-correlated upstream is never hidden behind a fabricated synthesis. NONE of
# these is a safety verdict.
#   synthesized          — the correlation result carried at least one finding and
#                          was synthesized into an accuracy + gaps view.
#   no_correlation       — there was no parseable correlation to synthesize (the
#                          upstream correlation is absent, or its status is
#                          model_error / unparseable / skipped_no_signals). No
#                          synthesis is fabricated; the status records why.
#   skipped_no_findings  — the correlation succeeded (status 'correlated') but
#                          carried ZERO findings, so there is nothing to synthesize
#                          (an honest empty correlation, not a false positive).
SYNTHESIS_STATUSES = [
    "synthesized",
    "no_correlation",
    "skipped_no_findings",
]

# Descriptive severity roll-up carried on a gap. EVIDENCE of how notable the gap is
# — NOT a decision. Mirrors the correlation/static severity vocabulary so 3.4 can
# align them, plus 'unknown' for a gap the upstream did not rate.
GAP_SEVERITIES = [
    "unknown",
    "none",
    "info",
    "low",
    "medium",
    "high",
    "critical",
]

# The kind of gap surfaced by gap_analysis. Descriptive, never a verdict.
#   static_uncorroborated  — a static finding with no supporting dynamic behavior
#                            (a candidate false positive, surfaced for review).
#   dynamic_unexplained    — an observed behavior with no static explanation (a
#                            coverage gap in the static lane).
#   contradiction          — static and dynamic evidence disagree (e.g. a flagged
#                            misconfiguration the behavior shows was never used).
#   coverage               — a structural coverage gap (e.g. the correlation was
#                            produced over an INCOMPLETE combined event, so a lane's
#                            evidence was missing entirely).
GAP_KINDS = [
    "static_uncorroborated",
    "dynamic_unexplained",
    "contradiction",
    "coverage",
]

# Bounds (kept deliberately tight — the input findings are already bounded at 100).
_MAX_SUMMARY = 4000
_MAX_ITEMS = 100
_MAX_TITLE = 256
_MAX_DETAIL = 1024
_MAX_REF = 256
_MAX_REFS = 20
_MAX_STATUS_DETAIL = 512
_MAX_COUNT = 1000
_MAX_CONTRACT_VERSION = 16
# The correlation status enum values 3.3 may carry through for traceability.
_CORRELATION_STATUSES = [
    "correlated",
    "model_error",
    "unparseable",
    "skipped_no_signals",
]


# --- One candidate false positive (accuracy) ----------------------------------

_CANDIDATE_FALSE_POSITIVE = {
    "description": (
        "One candidate false positive surfaced by the accuracy program: a static "
        "finding (a static_only correlation observation) that the dynamic evidence "
        "shows was never exercised, reconciled against benign dynamic behavior. "
        "Descriptive EVIDENCE for the Phase-4 human gate and the 3.4 scoring — a "
        "CANDIDATE for dismissal, never a decision that it IS benign. Bounded + "
        "allow-listed."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["severity", "title"],
    "properties": {
        "severity": {
            "description": (
                "Descriptive severity the correlation assigned the underlying "
                "static observation — how NOTABLE it is, NOT a decision. Carried "
                "through so 3.4 can weigh a dismissed high-severity flag differently "
                "from a low one."
            ),
            "type": "string",
            "enum": GAP_SEVERITIES,
        },
        "title": {
            "description": (
                "Short, bounded title of the reconciled static observation (carried "
                "from the correlation finding). Inert text, never executed."
            ),
            "type": "string",
            "maxLength": _MAX_TITLE,
        },
        "detail": {
            "description": (
                "Optional bounded note on WHY this is a candidate false positive "
                "(e.g. 'static-only finding with no correlated dynamic behavior'). "
                "Inert text; never raw content, never a verdict."
            ),
            "type": "string",
            "maxLength": _MAX_DETAIL,
        },
        "static_refs": {
            "description": (
                "Optional bounded list of short references to the static evidence "
                "this candidate draws on (carried from the correlation finding). "
                "Inert text references, never raw findings."
            ),
            "type": "array",
            "maxItems": _MAX_REFS,
            "items": {"type": "string", "maxLength": _MAX_REF},
        },
    },
}


# --- The accuracy block -------------------------------------------------------

_ACCURACY = {
    "description": (
        "The accuracy program's view: how well the 3.2 correlation eliminates false "
        "positives. It tallies the correlation findings by kind, surfaces the "
        "candidate false positives (static-only findings the dynamic behavior never "
        "exercised), and rolls them into a descriptive accuracy_score. EVIDENCE "
        "only — no verdict; the score describes reconciliation, not safety."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "accuracy_score",
        "confirmed_correlation_count",
        "candidate_false_positive_count",
        "candidate_false_positives",
    ],
    "properties": {
        "accuracy_score": {
            "description": (
                "A descriptive 0-100 EVIDENCE metric of how much of the flagged "
                "evidence the two lanes reconciled — the share of scored findings "
                "that are confirmed correlations rather than uncorroborated single-"
                "lane observations. HIGHER = more of the evidence is corroborated "
                "across both lanes (fewer candidate false positives). It is NOT a "
                "safety score and NOT a verdict — a high score does not mean 'safe' "
                "and a low score does not mean 'unsafe'; it only describes "
                "cross-lane reconciliation for the human gate + 3.4 to weigh."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": 100,
        },
        "confirmed_correlation_count": {
            "description": (
                "Number of correlation findings with kind 'correlated' (a static "
                "observation supported/explained by a dynamic one). A bounded count."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": _MAX_COUNT,
        },
        "candidate_false_positive_count": {
            "description": (
                "Number of candidate false positives surfaced (static_only findings "
                "reconciled against benign dynamic evidence). A bounded count; "
                "equals the length of candidate_false_positives unless that list was "
                "capped (recorded via the top-level 'truncated' flag)."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": _MAX_COUNT,
        },
        "static_only_count": {
            "description": (
                "Number of correlation findings with kind 'static_only'. A bounded "
                "count (>= candidate_false_positive_count before capping)."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": _MAX_COUNT,
        },
        "dynamic_only_count": {
            "description": (
                "Number of correlation findings with kind 'dynamic_only' (dynamic "
                "behavior with no static explanation). A bounded count."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": _MAX_COUNT,
        },
        "contradiction_count": {
            "description": (
                "Number of correlation findings with kind 'contradiction' (static "
                "and dynamic evidence disagree). A bounded count."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": _MAX_COUNT,
        },
        "candidate_false_positives": {
            "description": (
                "The bounded list of candidate false positives (static-only findings "
                "reconciled against benign dynamic evidence). Capped at MAX_ITEMS; a "
                "correlation carrying more is truncated (recorded via the top-level "
                "'truncated' flag), never overrun. EVIDENCE only."
            ),
            "type": "array",
            "maxItems": _MAX_ITEMS,
            "items": _CANDIDATE_FALSE_POSITIVE,
        },
    },
}


# --- One gap (gap_analysis) ---------------------------------------------------

_GAP = {
    "description": (
        "One gap surfaced by the gap_analysis program: where the static and dynamic "
        "lanes disagree (contradiction), where a lane's evidence is unexplained by "
        "the other (static_uncorroborated / dynamic_unexplained), or where the "
        "correlation was produced over incomplete inputs (coverage). Descriptive "
        "EVIDENCE for the Phase-4 human gate and the 3.4 scoring — never a verdict. "
        "Bounded + allow-listed."
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
            "enum": GAP_KINDS,
        },
        "severity": {
            "description": (
                "Descriptive severity roll-up for this gap — how NOTABLE it is, NOT "
                "a decision. 'unknown' when the underlying evidence was not rated."
            ),
            "type": "string",
            "enum": GAP_SEVERITIES,
        },
        "title": {
            "description": (
                "Short, bounded, human-readable title of the gap (carried/derived "
                "from the correlation finding). Inert text, never executed."
            ),
            "type": "string",
            "maxLength": _MAX_TITLE,
        },
        "detail": {
            "description": (
                "Optional longer, bounded explanation of the gap. Inert text; never "
                "raw content, never a verdict."
            ),
            "type": "string",
            "maxLength": _MAX_DETAIL,
        },
        "static_refs": {
            "description": (
                "Optional bounded list of short references to the static evidence "
                "this gap draws on (carried from the correlation finding). Inert "
                "text references, never raw findings."
            ),
            "type": "array",
            "maxItems": _MAX_REFS,
            "items": {"type": "string", "maxLength": _MAX_REF},
        },
        "behavioral_refs": {
            "description": (
                "Optional bounded list of short references to the dynamic behavioral "
                "evidence this gap draws on (carried from the correlation finding). "
                "Inert text references, never the raw trace."
            ),
            "type": "array",
            "maxItems": _MAX_REFS,
            "items": {"type": "string", "maxLength": _MAX_REF},
        },
    },
}


# --- The gaps block -----------------------------------------------------------

_GAPS = {
    "description": (
        "The gap_analysis program's view: where the two lanes disagree or leave a "
        "gap the human gate + 3.4 must weigh. A bounded list of gaps + a rolled-up "
        "worst severity + a count. EVIDENCE only — no verdict."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["gap_count", "items"],
    "properties": {
        "gap_count": {
            "description": (
                "Number of gaps carried (<= MAX_ITEMS). A bounded count."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": _MAX_ITEMS,
        },
        "highest_gap_severity": {
            "description": (
                "The worst descriptive severity across the gaps, rolled up for "
                "convenient downstream (3.4) query. Descriptive EVIDENCE, NOT a "
                "decision. Omitted when there are no gaps."
            ),
            "type": "string",
            "enum": GAP_SEVERITIES,
        },
        "items": {
            "description": (
                "The bounded list of gaps. Capped at MAX_ITEMS; more are truncated "
                "(recorded via the top-level 'truncated' flag), never overrun. "
                "EVIDENCE only."
            ),
            "type": "array",
            "maxItems": _MAX_ITEMS,
            "items": _GAP,
        },
    },
}


# --- The synthesis object (accuracy + gaps + summary) -------------------------

_SYNTHESIS = {
    "description": (
        "The accuracy + gap_analysis synthesis of the 3.2 correlation: a bounded "
        "narrative summary, the accuracy block (candidate false positives + a "
        "descriptive accuracy score), and the gaps block (static<->dynamic "
        "disagreements + coverage gaps). EVIDENCE only — NO verdict anywhere. "
        "Present when status is 'synthesized'; omitted otherwise (the status "
        "records why)."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "accuracy", "gaps"],
    "properties": {
        "summary": {
            "description": (
                "A bounded, deterministic narrative of the synthesis (how many "
                "confirmed correlations vs candidate false positives, and the "
                "notable gaps). Inert text; never a verdict, never raw content."
            ),
            "type": "string",
            "maxLength": _MAX_SUMMARY,
        },
        "accuracy": {**_ACCURACY},
        "gaps": {**_GAPS},
    },
}


SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://ztie.internal/schemas/synthesis.contract.v1.json",
    "title": "ZTIE synthesis-result (accuracy + gap_analysis) contract (v1)",
    "description": (
        "The bounded, DERIVED, verdict-free synthesis result produced by the Story "
        "3.3 Hub-side accuracy + gap_analysis synthesizer (RD-037) for one intake "
        "artifact — the false-positive-elimination + gap step of Phase 3 "
        "(Correlation & Synthesis). It reads the ONE verdict-free Nova Pro "
        "correlation result (Story 3.2, RD-035, 'correlation.contract.v1') already "
        "on the Hub tracking item and, in PURE deterministic logic (NOT a second "
        "model call — the semantic reasoning was already done in 3.2), (a) scores "
        "how well the correlation eliminates false positives (a static_only finding "
        "the dynamic behavior never exercised is a candidate false positive) and "
        "(b) surfaces where the two lanes disagree or leave a gap, recording the "
        "result back onto the SAME Hub tracking item. It is NOT a Forensic -> Hub "
        "crossing (its input already lives Hub-side); it is a Hub-INTERNAL derived "
        "field written by the 3.3 synthesizer Lambda, so it carries NO gate "
        "discriminator. It reasons ONLY over 3.2's bounded correlation result and "
        "references nothing raw (RD-009): no raw body, findings text, command log or "
        "raw trace. It records the synthesis HONESTLY — a 'status' (synthesized / "
        "no_correlation / skipped_no_findings) — so an absent or non-correlated "
        "upstream is never hidden behind a fabricated synthesis. It is NOT a "
        "verdict: there is NO verdict/safe/approved/forward/pass_fail/malicious/"
        "clean field anywhere; the 'accuracy_score' is a descriptive reconciliation "
        "metric (NOT a safety score) and 'severity' roll-ups describe EVIDENCE, and "
        "the verdict is Hub-side/human-gated (Phase 4). Allow-list: "
        "additionalProperties false at every level; every field typed and "
        "enum/length/range-bounded; every array maxItems-capped. Integrity-keyed by "
        "intake_id + sha256. DERIVED-ONLY. OWN version pin "
        "(SYNTHESIS_CONTRACT_VERSION)."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "contract_version",
        "intake_id",
        "sha256",
        "synthesized_at",
        "status",
    ],
    "properties": {
        "contract_version": {
            "description": (
                "Synthesis-contract schema version. Pinned SEPARATELY on the 3.3 "
                "synthesizer (SYNTHESIS_CONTRACT_VERSION) so this record versions "
                "independently of the shared CONTRACT_VERSION and every crossing "
                "kind's pin."
            ),
            "type": "string",
            "enum": ["1.0"],
        },
        "intake_id": {
            "description": (
                "The intake UUIDv4 this synthesis is for. The synthesizer writes it "
                "back onto the tracking record keyed by this."
            ),
            "type": "string",
            "pattern": (
                "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-"
                "[0-9a-f]{12}$"
            ),
        },
        "sha256": {
            "description": (
                "Lowercase hex SHA-256 of the raw artifact body all lanes "
                "inspected. Integrity key, bound to intake_id; the synthesizer only "
                "writes onto the tracking record whose sha256 matches the "
                "correlation it synthesized."
            ),
            "type": "string",
            "pattern": "^[0-9a-f]{64}$",
        },
        "synthesized_at": {
            "description": (
                "RFC3339/ISO-8601 UTC timestamp (Z-suffixed) the synthesizer "
                "produced this result in the Hub. The only wall-clock field."
            ),
            "type": "string",
            "format": "date-time",
            "maxLength": 40,
        },
        "status": {
            "description": (
                "What the synthesis actually did, recorded HONESTLY (synthesized / "
                "no_correlation / skipped_no_findings). NOT a verdict — "
                "'no_correlation' says there was nothing to synthesize, never that "
                "the artifact is safe/unsafe. When status != 'synthesized' the "
                "'synthesis' object is omitted (no synthesis is fabricated)."
            ),
            "type": "string",
            "enum": SYNTHESIS_STATUSES,
        },
        "status_detail": {
            "description": (
                "Optional short, bounded, non-executable note about the status "
                "(e.g. 'upstream correlation status was model_error', 'correlation "
                "carried zero findings'). Never raw content, never a verdict."
            ),
            "type": "string",
            "maxLength": _MAX_STATUS_DETAIL,
        },
        "correlation_status": {
            "description": (
                "The status of the upstream 3.2 correlation this synthesis was "
                "produced from (carried through for traceability). An UPSTREAM fact, "
                "never a verdict."
            ),
            "type": "string",
            "enum": _CORRELATION_STATUSES,
        },
        "correlation_contract_version": {
            "description": (
                "Version of the correlation contract (3.2) this synthesis was "
                "produced from, for traceability."
            ),
            "type": "string",
            "maxLength": _MAX_CONTRACT_VERSION,
        },
        "source_finding_count": {
            "description": (
                "Number of correlation findings the synthesis reasoned over (from "
                "the upstream correlation). A bounded count, for traceability."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": _MAX_COUNT,
        },
        "combined_complete": {
            "description": (
                "The combined event's aggregation-completeness fact (from 3.1, "
                "carried through 3.2) at the time of synthesis — whether all three "
                "inputs had landed. Used by gap_analysis to surface a 'coverage' "
                "gap when the correlation ran over incomplete inputs. An "
                "AGGREGATION-completeness fact, NEVER a verdict."
            ),
            "type": "boolean",
        },
        "truncated": {
            "description": (
                "True iff the synthesizer capped a list (candidate_false_positives "
                "or gaps.items) to MAX_ITEMS (dropped the tail) or clipped an "
                "oversized field to fit the bounds. A completeness fact, never a "
                "verdict."
            ),
            "type": "boolean",
        },
        "synthesis": {**_SYNTHESIS},
    },
}


# Repo-root-relative output paths (the canonical schema + the bundled lambda copy
# that must stay byte-in-sync). Consumed by scripts/gen_contracts.py; kept here so
# this contract's data lives in one place.
OUT_PATHS = [
    ("schemas", "synthesis.contract.v1.json"),
    ("lambdas", "hub_synthesize", "synthesis.contract.v1.json"),
]


def main() -> None:
    from contract_writer import resolve_out_paths, write_contract

    write_contract(SCHEMA, resolve_out_paths(OUT_PATHS))


if __name__ == "__main__":
    main()
