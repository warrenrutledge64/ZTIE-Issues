#!/usr/bin/env python3
"""Generate the ZTIE combined-event (telemetry aggregation / normalization) data
contract (Story 3.1, RD-033), v1.

Contract-first: this is the shared, NORMALIZED combined-event record the Phase-3
Nova Pro correlation engine (Story 3.2) reasons over. It is the FIRST Phase-3
artifact and it is deliberately DIFFERENT from the nine RD-013 crossing envelopes:

  * It is NOT a Forensic -> Hub crossing. All of its inputs ALREADY live on the Hub
    tracking record (the static-scan summary `scan` / 2.1-2.2, the dynamic-run
    outcome `run` / 2.3, the sanitized behavioral telemetry `sanitized` / 2.5, and
    the 2.6 `collected` join facts) — each already crossed the RD-013 gate and was
    applied integrity-bound by the Hub ingest validator. So 3.1 is a Hub-SIDE
    normalize (read the tracking item -> build the combined event -> write it back
    onto the SAME item), NOT a new crossing. This keeps the RD-009 / RD-013
    boundary intact (no raw data re-crossed, no full detail duplicated) and adds NO
    durable store to the Forensic blast zone (RD-012).
  * Because it never travels over SQS through the Hub gate, it carries NO unique
    top-level discriminator and needs no new gate dispatch branch. It is a
    Hub-internal DERIVED field on the tracking item, written by the Story 3.1
    normalizer Lambda (DynamoDB-Streams-triggered off the tracking table). It STILL
    gets its own contract + OWN version pin (COMBINED_EVENT_CONTRACT_VERSION) and
    the full evidence-never-verdict discipline, because it is the exact shape 3.2
    consumes and must be bounded / allow-listed just like every crossing contract.

Run:  python3 scripts/gen_combined_event_contract.py

WHAT THIS RECORD IS (and IS NOT):
  * It NORMALIZES the per-lane derived outputs for ONE intake_id into ONE consistent
    shape: a per-lane `sources` block that records, for each of the three inputs
    (static / dynamic / sanitized), WHETHER it is present and a bounded roll-up +
    Forensic pointer by reference; a normalized `signals` block (the cross-lane
    facts Nova Pro correlates — worst static severity, dynamic outcome, a bounded
    normalized behavioral event sequence carried through from the sanitized view);
    and `inputs_present` / `complete` completeness facts so a lane that has not
    landed yet (SQS ordering) or errored / produced no trace is RECORDED, never
    fabricated.
  * It REFERENCES — never duplicates — the per-lane detail. The full findings
    document, the full command log and the full raw behavioral trace all stay in
    Forensic (RD-009); only bounded roll-ups + pointers appear here. The behavioral
    events carried through are the ALREADY-sanitized, already-bounded 2.5 events
    (entropy-scrubbed, noise-suppressed, <=25K-token) — 3.1 re-shapes them into the
    combined schema, it does NOT re-capture or re-sanitize (2.4 / 2.5 own that).
  * All behavioral timings are RELATIVE monotonic offsets (ms) carried through from
    the 2.5 events, never a wall clock. Only the envelope `combined_at` stamp is
    wall-clock, for audit correlation.
  * It is NOT a verdict. There is deliberately NO verdict / safe / approved /
    forward / pass_fail / malicious / clean field ANYWHERE. `complete` is an
    aggregation-completeness fact; `highest_severity` / `dynamic_outcome` /
    `capture_status` describe EVIDENCE; the verdict stays Hub-side / human-gated
    (Phase 4), downstream of correlation.

Design invariants (mirror the crossing contracts, RD-013 / RD-014 / RD-016):
  * allow-list — additionalProperties:false at every level; every field typed and
    enum/length/range-bounded; every array maxItems-capped.
  * integrity-keyed — bound to intake_id + sha256 so the combined event can only
    describe the exact artifact all lanes inspected.
  * DERIVED-ONLY (RD-009) — no raw body / findings text / command log / raw trace;
    references the per-lane evidence via bounded roll-ups + Forensic S3 pointers,
    never duplicated.
  * ZERO-TRUST (RD-014) — the combined event is EVIDENCE, never a verdict.
  * OWN VERSION PIN — contract_version enum ['1.0'], pinned SEPARATELY via
    COMBINED_EVENT_CONTRACT_VERSION (never rides the shared CONTRACT_VERSION).
"""

from __future__ import annotations

import json
import os

# The three per-lane derived inputs 3.1 aggregates (already on the Hub tracking
# record). These are the input NAMES, not lanes — the sanitized view is the
# dynamic lane's sanitized behavior, distinct from the raw dynamic-run outcome.
INPUT_STATIC = "static"
INPUT_DYNAMIC = "dynamic"
INPUT_SANITIZED = "sanitized"
INPUTS = [INPUT_STATIC, INPUT_DYNAMIC, INPUT_SANITIZED]

# Whether each input has landed on the tracking record yet. Recorded so a lane
# that has not reported (SQS ordering) or was never expected is captured, not
# fabricated. NONE of these is a safety verdict.
#   present         — the input's derived record is on the tracking item and was
#                     normalized into this combined event.
#   absent          — the input's derived record is NOT (yet) on the tracking item
#                     (it may land later; a later normalize pass re-derives).
INPUT_PRESENCE = ["present", "absent"]

# The worst normalized severity carried through from the static-scan summary, by
# reference (the exact enum the static-scan-summary contract emits). Descriptive
# roll-up, NOT a decision.
STATIC_SEVERITIES = ["none", "info", "low", "medium", "high", "critical"]

# The dynamic-run outcome carried through from the dynamic-run contract, by
# reference. EVIDENCE of how the controlled run ended, never a verdict.
DYNAMIC_OUTCOMES = [
    "completed",
    "execution_error",
    "launch_error",
    "timed_out",
    "delivery_error",
]

# The sanitization pipeline health carried through from the sanitized-telemetry
# contract, by reference. EVIDENCE of capture/sanitization health, never a verdict.
SANITIZE_STATUSES = ["sanitized", "no_trace", "sanitize_error"]

# The behavioral-event categories carried through from the sanitized events (the
# exact enum the sanitized-telemetry contract emits).
EVENT_CATEGORIES = ["file", "network", "process", "signal", "other"]

# Bounds (mirror the source contracts so the normalized copy can never overrun).
_MAX_EVENTS = 2000
_MAX_SUMMARY = 512
_MAX_SYSCALL = 256
_MAX_OFFSET_MS = 86400000
_MAX_FINDINGS = 1000000
_MAX_S3_BUCKET = 256
_MAX_S3_KEY = 1024
_MAX_CONTRACT_VERSION = 16
_MAX_COUNT = 100000000
_MAX_TOKENS = 1000000


# --- Per-input source sub-objects (references, never duplicates) --------------

_STATIC_SOURCE = {
    "description": (
        "The normalized STATIC input for this intake, by reference to the crossed "
        "static-scan summary (2.1/2.2) already on the tracking record. Records "
        "whether the input is present and, when present, the worst severity it "
        "rolled up + a POINTER to the full findings document in Forensic (RD-009). "
        "It does NOT re-embed the per-finding detail. EVIDENCE, never a verdict."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["input", "presence"],
    "properties": {
        "input": {
            "description": "Always 'static' — the static-scan-summary input.",
            "type": "string",
            "const": INPUT_STATIC,
        },
        "presence": {
            "description": (
                "Whether the static-scan summary is present on the tracking record "
                "yet. 'absent' is RECORDED honestly (it may land later); never a "
                "verdict."
            ),
            "type": "string",
            "enum": INPUT_PRESENCE,
        },
        "highest_severity": {
            "description": (
                "The worst normalized severity carried through from the static-scan "
                "summary ('none' when zero findings). Present when the input is "
                "present. Descriptive EVIDENCE, NOT a decision."
            ),
            "type": "string",
            "enum": STATIC_SEVERITIES,
        },
        "total_findings": {
            "description": (
                "Total finding count carried through from the static-scan summary. "
                "Bounded; the full findings document stays in Forensic (RD-009)."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": _MAX_FINDINGS,
        },
        "summary_contract_version": {
            "description": (
                "Version of the static-scan-summary contract this roll-up was "
                "normalized from, for traceability."
            ),
            "type": "string",
            "maxLength": _MAX_CONTRACT_VERSION,
        },
        "findings_s3_bucket": {
            "description": (
                "Forensic S3 bucket holding the full findings document (RD-009 — "
                "referenced, not duplicated)."
            ),
            "type": "string",
            "maxLength": _MAX_S3_BUCKET,
        },
        "findings_s3_key": {
            "description": (
                "Forensic S3 key of the full findings document "
                "(findings/<intake_id>/static-findings.json)."
            ),
            "type": "string",
            "maxLength": _MAX_S3_KEY,
        },
    },
}

_DYNAMIC_SOURCE = {
    "description": (
        "The normalized DYNAMIC input for this intake, by reference to the crossed "
        "dynamic-run outcome (2.3) already on the tracking record. Records whether "
        "the input is present and, when present, the controlled-run outcome + a "
        "POINTER to the full command log in Forensic (RD-009). It does NOT re-embed "
        "the run detail. EVIDENCE, never a verdict."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["input", "presence"],
    "properties": {
        "input": {
            "description": "Always 'dynamic' — the dynamic-run-outcome input.",
            "type": "string",
            "const": INPUT_DYNAMIC,
        },
        "presence": {
            "description": (
                "Whether the dynamic-run outcome is present on the tracking record "
                "yet. 'absent' is RECORDED honestly; never a verdict."
            ),
            "type": "string",
            "enum": INPUT_PRESENCE,
        },
        "outcome": {
            "description": (
                "The controlled-run outcome carried through from the dynamic-run "
                "envelope. Present when the input is present. Describes how the "
                "ORCHESTRATION ended — NOT whether the artifact is safe."
            ),
            "type": "string",
            "enum": DYNAMIC_OUTCOMES,
        },
        "run_contract_version": {
            "description": (
                "Version of the dynamic-run contract this roll-up was normalized "
                "from, for traceability."
            ),
            "type": "string",
            "maxLength": _MAX_CONTRACT_VERSION,
        },
        "run_log_s3_bucket": {
            "description": (
                "Forensic S3 bucket holding the full command output log (RD-009 — "
                "referenced, not duplicated)."
            ),
            "type": "string",
            "maxLength": _MAX_S3_BUCKET,
        },
        "run_log_s3_key": {
            "description": (
                "Forensic S3 key of the full command output log "
                "(runs/<intake_id>/detonation-output.json)."
            ),
            "type": "string",
            "maxLength": _MAX_S3_KEY,
        },
    },
}

_SANITIZED_SOURCE = {
    "description": (
        "The normalized SANITIZED-TELEMETRY input for this intake, by reference to "
        "the crossed sanitized view (2.5) already on the tracking record. Records "
        "whether the input is present, the sanitization pipeline health + token "
        "accounting, and a POINTER to the full raw trace in Forensic (RD-009). The "
        "actual normalized events live under signals.behavioral_events (carried "
        "through from the ALREADY-sanitized 2.5 events; 3.1 re-shapes, it does NOT "
        "re-sanitize). EVIDENCE, never a verdict."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["input", "presence"],
    "properties": {
        "input": {
            "description": "Always 'sanitized' — the sanitized-telemetry input.",
            "type": "string",
            "const": INPUT_SANITIZED,
        },
        "presence": {
            "description": (
                "Whether the sanitized telemetry is present on the tracking record "
                "yet. 'absent' is RECORDED honestly; never a verdict."
            ),
            "type": "string",
            "enum": INPUT_PRESENCE,
        },
        "capture_status": {
            "description": (
                "Sanitization/capture health carried through from the sanitized "
                "view's pipeline.status (sanitized / no_trace / sanitize_error). "
                "EVIDENCE of health — a missing trace is RECORDED, never a verdict."
            ),
            "type": "string",
            "enum": SANITIZE_STATUSES,
        },
        "truncated": {
            "description": (
                "True iff the 2.5 <=25K-token truncation dropped one or more kept "
                "events to fit the budget. A completeness fact carried through, not "
                "a verdict."
            ),
            "type": "boolean",
        },
        "estimated_tokens": {
            "description": (
                "The deterministic estimated token count of the sanitized view, "
                "carried through from 2.5 (chars/4 heuristic, never a live "
                "tokenizer)."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": _MAX_TOKENS,
        },
        "sanitized_contract_version": {
            "description": (
                "Version of the sanitized-telemetry contract this roll-up was "
                "normalized from, for traceability."
            ),
            "type": "string",
            "maxLength": _MAX_CONTRACT_VERSION,
        },
        "trace_s3_bucket": {
            "description": (
                "Forensic S3 bucket holding the full raw behavioral trace (RD-009 — "
                "referenced, not duplicated)."
            ),
            "type": "string",
            "maxLength": _MAX_S3_BUCKET,
        },
        "trace_s3_key": {
            "description": (
                "Forensic S3 key of the full raw behavioral trace "
                "(traces/<intake_id>/behavior-trace.txt)."
            ),
            "type": "string",
            "maxLength": _MAX_S3_KEY,
        },
    },
}


# --- The normalized behavioral event (carried through from 2.5, re-shaped) ----

_BEHAVIORAL_EVENT = {
    "description": (
        "One normalized behavioral event carried through from the ALREADY-sanitized "
        "2.5 events (entropy-scrubbed, noise-suppressed, token-budgeted). 3.1 "
        "re-shapes it into the combined schema; it does NOT re-capture or "
        "re-sanitize. Inert EVIDENCE for Phase-3 correlation; never executed."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["offset_ms", "category", "syscall", "summary"],
    "properties": {
        "offset_ms": {
            "description": (
                "RELATIVE monotonic offset (ms) from detonation start, carried "
                "through from the 2.5 event. A relative clock only — never a wall "
                "clock (RD-031)."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": _MAX_OFFSET_MS,
        },
        "category": {
            "description": (
                "Behavioral category (file / network / process / signal / other), "
                "carried through from the 2.5 event."
            ),
            "type": "string",
            "enum": EVENT_CATEGORIES,
        },
        "syscall": {
            "description": (
                "Syscall name for this event, carried through from the 2.5 event "
                "(structure kept; only high-entropy VALUES were redacted upstream)."
            ),
            "type": "string",
            "maxLength": _MAX_SYSCALL,
        },
        "summary": {
            "description": (
                "The already-SANITIZED one-line summary carried through from the "
                "2.5 event (high-entropy values already replaced by a bounded "
                "'[REDACTED:...]' marker upstream). Inert EVIDENCE, never executed."
            ),
            "type": "string",
            "maxLength": _MAX_SUMMARY,
        },
        "redacted": {
            "description": (
                "True iff the upstream 2.5 entropy scrub redacted one or more "
                "high-entropy values in this event. A sanitization-accounting fact "
                "carried through, not a verdict."
            ),
            "type": "boolean",
        },
    },
}


# --- The normalized cross-lane signals block (what 3.2 correlates over) --------

_SIGNALS = {
    "description": (
        "The NORMALIZED cross-lane signal set the Phase-3 Nova Pro correlation "
        "engine (3.2) reasons over: the static misconfiguration roll-up aligned "
        "with the dynamic behavioral indicators on ONE common shape. Every field "
        "is carried through by reference from an input already on the tracking "
        "record; a signal whose input is absent is simply omitted (never "
        "fabricated). EVIDENCE only — NO verdict anywhere."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["behavioral_events"],
    "properties": {
        "static_highest_severity": {
            "description": (
                "The worst static severity (from the static input), surfaced at the "
                "signals level for correlation. Present iff the static input is "
                "present. Descriptive EVIDENCE, not a decision."
            ),
            "type": "string",
            "enum": STATIC_SEVERITIES,
        },
        "dynamic_outcome": {
            "description": (
                "The controlled-run outcome (from the dynamic input), surfaced at "
                "the signals level for correlation. Present iff the dynamic input "
                "is present. Describes the orchestration, not the artifact's safety."
            ),
            "type": "string",
            "enum": DYNAMIC_OUTCOMES,
        },
        "behavioral_event_count": {
            "description": (
                "Number of normalized behavioral events carried through into "
                "behavioral_events (<= the 2.5 emitted_events, <= MAX_EVENTS). A "
                "bounded count; the full trace stays in Forensic (RD-009)."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": _MAX_COUNT,
        },
        "behavioral_events": {
            "description": (
                "The bounded, token-budgeted, already-sanitized behavioral event "
                "sequence (in trace order), carried through from the 2.5 sanitized "
                "view and re-shaped into the combined schema. Empty when the "
                "sanitized input is absent or recorded no trace. The full trace "
                "stays in Forensic (RD-009). Inert EVIDENCE; never executed."
            ),
            "type": "array",
            "maxItems": _MAX_EVENTS,
            "items": _BEHAVIORAL_EVENT,
        },
    },
}


# --- The combined-event object ------------------------------------------------

_COMBINED = {
    "description": (
        "The NORMALIZED combined event for one intake: the per-input source "
        "roll-ups (static / dynamic / sanitized, by reference), the normalized "
        "cross-lane signals (what 3.2 correlates), and the aggregation-completeness "
        "facts (which inputs are present, whether the aggregation is complete). It "
        "REFERENCES — never duplicates — the per-lane evidence (RD-009). EVIDENCE "
        "only; no verdict anywhere. 'complete' says whether all three inputs have "
        "landed, NOT whether the artifact is safe."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "inputs_present",
        "complete",
        "sources",
        "signals",
    ],
    "properties": {
        "inputs_present": {
            "description": (
                "The set of inputs actually present on the tracking record and "
                "normalized into this combined event (subset of static / dynamic / "
                "sanitized). An input that has not landed yet is simply not listed "
                "here (and its source records presence 'absent') — a recorded gap, "
                "never a silent drop or a fabrication."
            ),
            "type": "array",
            "minItems": 0,
            "maxItems": 3,
            "uniqueItems": True,
            "items": {"type": "string", "enum": INPUTS},
        },
        "complete": {
            "description": (
                "True iff all three inputs (static, dynamic, sanitized) are present "
                "and normalized. An AGGREGATION-completeness fact for Phase-3 "
                "correlation — NOT a safety verdict; a complete combined event can "
                "still describe a high-severity finding or an execution error."
            ),
            "type": "boolean",
        },
        "sources": {
            "description": (
                "The three per-input source roll-ups, by reference. Each records "
                "whether its input is present and, when present, a bounded roll-up "
                "+ Forensic pointer. Present-but-absent inputs are RECORDED, never "
                "fabricated."
            ),
            "type": "object",
            "additionalProperties": False,
            "required": ["static", "dynamic", "sanitized"],
            "properties": {
                "static": _STATIC_SOURCE,
                "dynamic": _DYNAMIC_SOURCE,
                "sanitized": _SANITIZED_SOURCE,
            },
        },
        "signals": {**_SIGNALS},
        "normalize_note": {
            "description": (
                "Optional short, bounded, non-executable note about the "
                "normalization (e.g. 'sanitized input not yet present; re-derives on "
                "next update'). Never raw content, never a verdict."
            ),
            "type": "string",
            "maxLength": _MAX_SUMMARY,
        },
    },
}


SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://ztie.internal/schemas/combined-event.contract.v1.json",
    "title": "ZTIE combined-event (telemetry aggregation / normalization) contract (v1)",
    "description": (
        "The shared, NORMALIZED combined-event record produced by the Story 3.1 "
        "Hub-side aggregation/normalization (RD-033) for one intake artifact, and "
        "the FIRST Phase-3 (Correlation & Synthesis) artifact. It aggregates the "
        "three per-lane derived outputs ALREADY on the Hub tracking record — the "
        "static-scan summary (2.1/2.2), the dynamic-run outcome (2.3) and the "
        "sanitized behavioral telemetry (2.5) — into ONE consistent shape the "
        "Phase-3 Nova Pro correlation engine (3.2) reasons over, rather than three "
        "differently-shaped records. It is NOT a Forensic -> Hub crossing (all "
        "inputs are already Hub-side); it is a Hub-INTERNAL derived field written "
        "back onto the same tracking item by the 3.1 normalizer Lambda, so it "
        "carries NO gate discriminator. It REFERENCES — never duplicates — the "
        "per-lane detail: the full findings document, command log and raw trace all "
        "stay in Forensic (RD-009); only bounded roll-ups + pointers + the "
        "ALREADY-sanitized 2.5 events (re-shaped, not re-sanitized) appear here. It "
        "records WHICH inputs are present so a lane that has not landed yet (SQS "
        "ordering) or errored / produced no trace is captured honestly, never "
        "fabricated. All behavioral timings are RELATIVE monotonic offsets (ms) "
        "carried through from 2.5, never a wall clock (only 'combined_at' is "
        "wall-clock, for audit correlation). It is NOT a verdict: there is NO "
        "verdict/safe/approved/forward/pass_fail/malicious/clean field anywhere; "
        "'complete' is an aggregation-completeness fact and the verdict is "
        "Hub-side/human-gated (Phase 4). Allow-list: additionalProperties false at "
        "every level; every field typed and enum/length/range-bounded; every array "
        "maxItems-capped. Integrity-keyed by intake_id + sha256. DERIVED-ONLY. OWN "
        "version pin (COMBINED_EVENT_CONTRACT_VERSION)."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "contract_version",
        "intake_id",
        "sha256",
        "combined_at",
        "combined_event",
    ],
    "properties": {
        "contract_version": {
            "description": (
                "Combined-event-contract schema version. Pinned SEPARATELY on the "
                "3.1 normalizer (COMBINED_EVENT_CONTRACT_VERSION) so this record "
                "versions independently of the shared CONTRACT_VERSION and every "
                "crossing kind's pin."
            ),
            "type": "string",
            "enum": ["1.0"],
        },
        "intake_id": {
            "description": (
                "The intake UUIDv4 this combined event is for. The normalizer writes "
                "it back onto the tracking record keyed by this."
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
                "Integrity key, bound to intake_id; the normalizer only combines "
                "inputs whose sha256 matches the tracked record."
            ),
            "type": "string",
            "pattern": "^[0-9a-f]{64}$",
        },
        "combined_at": {
            "description": (
                "RFC3339/ISO-8601 UTC timestamp (Z-suffixed) the normalizer produced "
                "this combined event in the Hub. This is the ONLY wall-clock field — "
                "all behavioral timings are relative offsets carried through from "
                "2.5 (signals.behavioral_events[].offset_ms)."
            ),
            "type": "string",
            "format": "date-time",
            "maxLength": 40,
        },
        "combined_event": {**_COMBINED},
    },
}


def main() -> None:
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # Canonical schema location + the bundled copies the Hub validator Lambda (for
    # symmetry with the other bundled contracts) and the 3.1 normalizer Lambda load
    # from their own asset dirs. All written from this one source so they can never
    # drift; hash-check after generating.
    out_paths = [
        os.path.join(repo, "schemas", "combined-event.contract.v1.json"),
        os.path.join(repo, "lambdas", "hub_normalize", "combined-event.contract.v1.json"),
    ]
    for out_path in out_paths:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(SCHEMA, fh, indent=2)
            fh.write("\n")
        print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
