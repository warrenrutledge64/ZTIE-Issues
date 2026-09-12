#!/usr/bin/env python3
"""Generate the ZTIE correlation-result data contract (Story 3.2, RD-035), v1.

Contract-first: this is the bounded, DERIVED, verdict-free correlation result the
Phase-3 Nova Pro correlation engine (Story 3.2) records on the Hub tracking item
after it hands the ONE normalized combined-event record (Story 3.1, RD-033) to
Amazon Nova Pro (RD-003) and correlates the static misconfigurations with the
dynamic behavioral indicators.

Like the combined-event contract (3.1), and for the SAME reasons, it is deliberately
DIFFERENT from the nine RD-013 crossing envelopes:

  * It is NOT a Forensic -> Hub crossing. Its input (the ``combined_event``)
    ALREADY lives on the Hub tracking record (3.1 wrote it there Hub-side). So 3.2
    is a Hub-SIDE derivation (read the tracking item's combined event -> invoke Nova
    Pro -> write the correlation result back onto the SAME item), NOT a new crossing.
    This keeps the RD-009 / RD-013 boundary intact (no raw data re-crossed, no full
    detail duplicated) and adds NO durable store to the Forensic blast zone
    (RD-012). Because it never travels over SQS through the Hub gate, it carries NO
    unique top-level discriminator and needs no new gate dispatch branch. It is a
    Hub-internal DERIVED field on the tracking item, written by the Story 3.2
    correlator Lambda (DynamoDB-Streams-triggered off the tracking table).
  * It STILL gets its own contract + OWN version pin (CORRELATION_CONTRACT_VERSION)
    and the full evidence-never-verdict discipline, because it is the exact shape
    the accuracy + gap_analysis synthesis (3.3) consumes and must be bounded /
    allow-listed just like every crossing contract.

Run:  python3 scripts/gen_correlation_contract.py

WHAT THIS RECORD IS (and IS NOT):
  * It records a Nova Pro CORRELATION of the combined event: a bounded, model-
    produced narrative summary + a bounded list of correlation findings (each ties a
    static observation to a dynamic behavioral indicator, or notes a static-only /
    dynamic-only observation, with a descriptive severity roll-up). It is EVIDENCE
    the human/Phase-4 gate and the 3.3 synthesis reason over.
  * It records the INVOCATION honestly: a ``status`` (correlated / model_error /
    unparseable / skipped_no_signals), the ``model_id`` used, the number of Bedrock
    ``attempts`` (so the exponential-backoff retry is inspectable), and whether the
    model output was ``truncated`` / had to be bounded. When the model call fails or
    the response cannot be parsed into this schema, the status RECORDS that and NO
    correlation is fabricated (the same honesty discipline as 3.1's absent inputs).
  * It NEVER contains a verdict. There is deliberately NO verdict / safe / approved /
    forward / pass_fail / malicious / clean field ANYWHERE, and the Nova Pro PROMPT
    never asks the model for a verdict — only for a correlation of the evidence. The
    ``severity`` roll-ups describe EVIDENCE (how notable a correlated observation is),
    NOT a decision; the verdict stays Hub-side / human-gated (Phase 4), downstream.

Design invariants (mirror the crossing contracts, RD-013 / RD-014 / RD-016):
  * allow-list — additionalProperties:false at every level; every field typed and
    enum/length/range-bounded; every array maxItems-capped.
  * integrity-keyed — bound to intake_id + sha256 so the correlation can only
    describe the exact artifact all lanes inspected + 3.1 normalized.
  * DERIVED-ONLY (RD-009) — no raw body / findings text / command log / raw trace.
    The correlation reasons over 3.1's bounded combined event; it references nothing
    raw and duplicates nothing from Forensic.
  * ZERO-TRUST (RD-014) — the correlation result is EVIDENCE, never a verdict.
  * OWN VERSION PIN — contract_version enum ['1.0'], pinned SEPARATELY via
    CORRELATION_CONTRACT_VERSION (never rides the shared CONTRACT_VERSION).
"""

from __future__ import annotations

# The invocation status. Records what actually happened HONESTLY so a model failure
# is never hidden behind a fabricated correlation. NONE of these is a safety verdict.
#   correlated         — Nova Pro returned a response that parsed into this schema.
#   model_error        — the Bedrock call failed after exhausting the retry budget
#                        (throttling / 5xx / timeout); no correlation was produced.
#   unparseable        — the model returned a response, but it could not be parsed
#                        into this bounded schema (malformed / off-format output);
#                        no correlation was fabricated.
#   skipped_no_signals — the combined event carried no usable signals to correlate
#                        (e.g. no inputs present yet); nothing was sent to the model.
CORRELATION_STATUSES = [
    "correlated",
    "model_error",
    "unparseable",
    "skipped_no_signals",
]

# Descriptive severity roll-up carried on a correlation finding. EVIDENCE of how
# notable the correlated observation is — NOT a decision. Mirrors the static
# severity vocabulary so 3.3 can align them, plus 'unknown' for a finding the model
# did not rate.
CORRELATION_SEVERITIES = [
    "unknown",
    "none",
    "info",
    "low",
    "medium",
    "high",
    "critical",
]

# How a finding relates the two evidence lanes. Descriptive, never a verdict.
#   correlated     — a static observation is supported/explained by a dynamic one.
#   static_only    — a static observation with no corresponding dynamic behavior.
#   dynamic_only   — a dynamic behavior with no corresponding static observation.
#   contradiction  — static and dynamic evidence disagree (e.g. a flagged
#                    misconfiguration that the behavior shows was never exercised).
CORRELATION_KINDS = [
    "correlated",
    "static_only",
    "dynamic_only",
    "contradiction",
]

# Bounds (kept deliberately tight — the model output is untrusted + non-deterministic).
_MAX_SUMMARY = 4000
_MAX_FINDINGS = 100
_MAX_TITLE = 256
_MAX_DETAIL = 1024
_MAX_REF = 256
_MAX_REFS = 20
_MAX_MODEL_ID = 256
_MAX_STATUS_DETAIL = 512
_MAX_ATTEMPTS = 100
_MAX_TOKENS = 1000000
_MAX_LATENCY_MS = 3600000
_MAX_CONTRACT_VERSION = 16


# --- One correlation finding (a single correlated observation) ----------------

_CORRELATION_FINDING = {
    "description": (
        "One correlated observation Nova Pro produced from the combined event: it "
        "ties (or fails to tie) a static misconfiguration to a dynamic behavioral "
        "indicator. Descriptive EVIDENCE for the Phase-4 human gate and the 3.3 "
        "synthesis — never a verdict. Bounded + allow-listed; the model cannot "
        "smuggle raw content or a decision through it."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["kind", "severity", "title"],
    "properties": {
        "kind": {
            "description": (
                "How this finding relates the two evidence lanes (correlated / "
                "static_only / dynamic_only / contradiction). Descriptive, never a "
                "verdict."
            ),
            "type": "string",
            "enum": CORRELATION_KINDS,
        },
        "severity": {
            "description": (
                "Descriptive severity roll-up for this correlated observation — how "
                "NOTABLE it is, NOT a decision. 'unknown' when the model did not "
                "rate it."
            ),
            "type": "string",
            "enum": CORRELATION_SEVERITIES,
        },
        "title": {
            "description": (
                "Short, bounded, human-readable title of the correlated "
                "observation (model-produced). Inert text, never executed."
            ),
            "type": "string",
            "maxLength": _MAX_TITLE,
        },
        "detail": {
            "description": (
                "Optional longer, bounded explanation of the correlation "
                "(model-produced). Inert text; never raw content, never a verdict."
            ),
            "type": "string",
            "maxLength": _MAX_DETAIL,
        },
        "static_refs": {
            "description": (
                "Optional bounded list of short references to the static evidence "
                "this finding draws on (e.g. a finding id / rule name surfaced in "
                "the combined event). Inert text references, never raw findings."
            ),
            "type": "array",
            "maxItems": _MAX_REFS,
            "items": {"type": "string", "maxLength": _MAX_REF},
        },
        "behavioral_refs": {
            "description": (
                "Optional bounded list of short references to the dynamic "
                "behavioral evidence this finding draws on (e.g. a syscall / event "
                "summary surfaced in the combined event). Inert text references, "
                "never the raw trace."
            ),
            "type": "array",
            "maxItems": _MAX_REFS,
            "items": {"type": "string", "maxLength": _MAX_REF},
        },
    },
}


# --- The correlation object (what the model produced, bounded) ----------------

_CORRELATION = {
    "description": (
        "The Nova Pro correlation of the combined event: a bounded narrative "
        "summary + a bounded list of correlation findings (static ↔ dynamic). "
        "EVIDENCE only — NO verdict anywhere; the model was asked to correlate the "
        "evidence, never to decide. Present when status is 'correlated'; omitted "
        "when the invocation did not produce a parseable correlation (the status "
        "records why)."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "findings"],
    "properties": {
        "summary": {
            "description": (
                "The model's bounded narrative correlation of the static "
                "misconfigurations against the dynamic behavioral indicators. Inert "
                "text; never a verdict, never raw content."
            ),
            "type": "string",
            "maxLength": _MAX_SUMMARY,
        },
        "highest_correlation_severity": {
            "description": (
                "The worst descriptive severity across the findings, rolled up for "
                "convenient downstream (3.3) query. Descriptive EVIDENCE, NOT a "
                "decision. Omitted when there are no findings."
            ),
            "type": "string",
            "enum": CORRELATION_SEVERITIES,
        },
        "finding_count": {
            "description": (
                "Number of correlation findings carried (<= MAX_FINDINGS). A "
                "bounded count."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": _MAX_FINDINGS,
        },
        "findings": {
            "description": (
                "The bounded list of correlation findings (static ↔ dynamic). Capped "
                "at MAX_FINDINGS; a model that returns more is truncated (recorded "
                "via the top-level 'truncated' flag), never overrun. EVIDENCE only."
            ),
            "type": "array",
            "maxItems": _MAX_FINDINGS,
            "items": _CORRELATION_FINDING,
        },
    },
}


SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://ztie.internal/schemas/correlation.contract.v1.json",
    "title": "ZTIE correlation-result (Nova Pro static↔dynamic correlation) contract (v1)",
    "description": (
        "The bounded, DERIVED, verdict-free correlation result produced by the "
        "Story 3.2 Hub-side Nova Pro correlation engine (RD-035) for one intake "
        "artifact — the AI-correlation core of Phase 3 (Correlation & Synthesis). "
        "It hands the ONE normalized combined-event record (Story 3.1, RD-033) for "
        "an intake_id to Amazon Nova Pro (RD-003, via bedrock-runtime, with "
        "exponential-backoff retry on throttling/5xx), correlates the static "
        "misconfigurations with the dynamic behavioral indicators, and records the "
        "result back onto the SAME Hub tracking item. It is NOT a Forensic -> Hub "
        "crossing (its input already lives Hub-side); it is a Hub-INTERNAL derived "
        "field written by the 3.2 correlator Lambda, so it carries NO gate "
        "discriminator. It reasons ONLY over 3.1's bounded combined event and "
        "references nothing raw (RD-009): no raw body, findings text, command log or "
        "raw trace. It records the invocation HONESTLY — a 'status' "
        "(correlated / model_error / unparseable / skipped_no_signals), the model "
        "id, the number of Bedrock attempts (so the retry is inspectable), and "
        "whether output was truncated — so a model failure is never hidden behind a "
        "fabricated correlation. It is NOT a verdict: there is NO "
        "verdict/safe/approved/forward/pass_fail/malicious/clean field anywhere and "
        "the prompt never asks the model for one; 'severity' roll-ups describe "
        "EVIDENCE and the verdict is Hub-side/human-gated (Phase 4). Allow-list: "
        "additionalProperties false at every level; every field typed and "
        "enum/length/range-bounded; every array maxItems-capped. Integrity-keyed by "
        "intake_id + sha256. DERIVED-ONLY. OWN version pin "
        "(CORRELATION_CONTRACT_VERSION)."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "contract_version",
        "intake_id",
        "sha256",
        "correlated_at",
        "status",
    ],
    "properties": {
        "contract_version": {
            "description": (
                "Correlation-contract schema version. Pinned SEPARATELY on the 3.2 "
                "correlator (CORRELATION_CONTRACT_VERSION) so this record versions "
                "independently of the shared CONTRACT_VERSION and every crossing "
                "kind's pin."
            ),
            "type": "string",
            "enum": ["1.0"],
        },
        "intake_id": {
            "description": (
                "The intake UUIDv4 this correlation is for. The correlator writes it "
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
                "inspected. Integrity key, bound to intake_id; the correlator only "
                "writes onto the tracking record whose sha256 matches the combined "
                "event it correlated."
            ),
            "type": "string",
            "pattern": "^[0-9a-f]{64}$",
        },
        "correlated_at": {
            "description": (
                "RFC3339/ISO-8601 UTC timestamp (Z-suffixed) the correlator produced "
                "this result in the Hub. The only wall-clock field (the combined "
                "event's behavioral timings stay relative)."
            ),
            "type": "string",
            "format": "date-time",
            "maxLength": 40,
        },
        "status": {
            "description": (
                "What the invocation actually did, recorded HONESTLY (correlated / "
                "model_error / unparseable / skipped_no_signals). NOT a verdict — a "
                "'model_error' says the call failed, never that the artifact is "
                "safe/unsafe. When status != 'correlated' the 'correlation' object "
                "is omitted (no correlation is fabricated)."
            ),
            "type": "string",
            "enum": CORRELATION_STATUSES,
        },
        "status_detail": {
            "description": (
                "Optional short, bounded, non-executable note about the status "
                "(e.g. 'ThrottlingException after 5 attempts', 'response was not "
                "valid JSON'). Never raw content, never a verdict."
            ),
            "type": "string",
            "maxLength": _MAX_STATUS_DETAIL,
        },
        "model_id": {
            "description": (
                "The Bedrock model id / inference-profile id invoked (RD-003, Nova "
                "Pro). Recorded for traceability + reproducibility."
            ),
            "type": "string",
            "maxLength": _MAX_MODEL_ID,
        },
        "attempts": {
            "description": (
                "Number of Bedrock invocation attempts made, including the final "
                "one (so the exponential-backoff retry is inspectable: 1 = "
                "succeeded first try; >1 = retried). Bounded."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": _MAX_ATTEMPTS,
        },
        "latency_ms": {
            "description": (
                "Optional wall-clock duration (ms) of the successful Bedrock "
                "invocation (last attempt), for cost/perf observability. Bounded."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": _MAX_LATENCY_MS,
        },
        "input_tokens": {
            "description": (
                "Optional input token count reported by Bedrock usage metadata "
                "(for cost observability). Bounded."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": _MAX_TOKENS,
        },
        "output_tokens": {
            "description": (
                "Optional output token count reported by Bedrock usage metadata "
                "(for cost observability). Bounded."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": _MAX_TOKENS,
        },
        "truncated": {
            "description": (
                "True iff the correlator capped the model's findings to MAX_FINDINGS "
                "(dropped the tail) or clipped an oversized field to fit the "
                "bounds. A completeness fact, never a verdict."
            ),
            "type": "boolean",
        },
        "combined_complete": {
            "description": (
                "The combined event's aggregation-completeness fact (from 3.1) at "
                "the time of correlation — whether all three inputs (static / "
                "dynamic / sanitized) had landed. Carried through for traceability. "
                "An AGGREGATION-completeness fact, NEVER a verdict; the correlation "
                "may be honest over an incomplete combined event."
            ),
            "type": "boolean",
        },
        "combined_event_contract_version": {
            "description": (
                "Version of the combined-event contract (3.1) this correlation was "
                "produced from, for traceability."
            ),
            "type": "string",
            "maxLength": _MAX_CONTRACT_VERSION,
        },
        "correlation": {**_CORRELATION},
    },
}


# Repo-root-relative output paths (the canonical schema + the bundled lambda copy
# that must stay byte-in-sync). Consumed by scripts/gen_contracts.py; kept here so
# this contract's data lives in one place.
OUT_PATHS = [
    ("schemas", "correlation.contract.v1.json"),
    ("lambdas", "hub_correlate", "correlation.contract.v1.json"),
]


def main() -> None:
    from contract_writer import resolve_out_paths, write_contract

    write_contract(SCHEMA, resolve_out_paths(OUT_PATHS))


if __name__ == "__main__":
    main()
