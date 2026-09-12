#!/usr/bin/env python3
"""Generate the ZTIE sanitized-telemetry data contract (Story 2.5), v1.

Contract-first: this is the NINTH envelope kind that crosses the SAME
one-directional Forensic -> Hub RD-013 gate as the intake-tracking (1.1R),
classification (1.2), routing (1.3), safe-reject (1.4), static-scan-summary
(2.1/2.2), dynamic-run outcome (2.3), collected-record (2.6) and behavioral-
telemetry (2.4) envelopes. It is the SANITIZED behavioral view RD-031 describes:
the raw behavioral trace Story 2.4 captured (RD-030), cleaned through a three-stage
pipeline — entropy scrub -> noise suppress -> <=25K-token truncation — into the
bounded, derived view the Phase-3 Nova Pro correlation engine reasons over.

Run:  python3 scripts/gen_sanitized_telemetry_contract.py

WHY A NEW KIND (not a refinement of the 2.4 behavior contract):
  * Story 2.4's ``behavior`` contract explicitly states sanitization is Story 2.5
    and is NOT in that contract: it CAPTURES raw behavior (bounded syscall/network/
    filesystem TALLIES + a Forensic trace pointer). 2.5 SANITIZES: it produces a
    token-budgeted, entropy-scrubbed, noise-suppressed EVENT SEQUENCE plus the
    three-stage pipeline accounting. Different shape, different purpose, different
    audience (Nova Pro correlation). Refining the 2.4 contract would re-litigate a
    validated story; a new kind keeps 2.4 untouched.
  * A NEW kind gets its OWN version pin (SANITIZED_TELEMETRY_CONTRACT_VERSION) and a
    UNIQUE ``sanitized`` discriminator that does not collide with any of the eight
    existing kinds (classification / routing / rejection / scan / run / status /
    collected / behavior).

WHAT THIS ENVELOPE IS (and IS NOT):
  * Story 2.5 SANITIZES the Story 2.4 raw trace for Phase-3 correlation. It consumes
    the raw host trace (the same text 2.4 wrote to Forensic S3, RD-009) and applies,
    IN ORDER:
      1. ENTROPY SCRUB — high-entropy VALUES (keys, base64 blobs, random tokens) that
         carry no behavioral signal and inflate the token budget are REDACTED to a
         bounded ``[REDACTED:...]`` marker, while the behavioral STRUCTURE (which
         syscall, which path shape) is KEPT.
      2. NOISE SUPPRESS — the deterministic host/runtime noise that is NOT the
         artifact's own behavior (SSM-agent boot, dynamic-linker library loads,
         locale-archive opens, shell/coreutils startup) is DROPPED so the artifact's
         salient ops become legible.
      3. <=25K-TOKEN TRUNCATION — the result is bounded to the Phase-3 token budget,
         DETERMINISTICALLY (kept in trace order, dropping the tail), with a recorded
         ``truncated`` flag. Never a silent drop.
  * The FULL raw trace stays in Forensic (RD-009); this envelope REFERENCES it via a
    pointer and NEVER duplicates it. The sanitized event bodies are byte-capped and
    entropy-scrubbed.
  * TIMESTAMPS ARE RELATIVE. Every event time is a MONOTONIC OFFSET in milliseconds
    from detonation start (``offset_ms``), never a wall clock. The only wall-clock
    field is the top-level ``sanitized_at`` (when the orchestrator finished
    sanitizing, for audit correlation), mirroring the other contracts' ``*_at`` stamp.
  * It is NOT a verdict. There is deliberately NO verdict / safe / approved /
    forward / pass_fail / malicious / clean field ANYWHERE. The sanitized events and
    pipeline accounting are EVIDENCE; the verdict is Hub-side / human-gated (Phase 4).

Design invariants (mirror the eight existing crossing contracts, RD-013 / RD-016):
  * allow-list — additionalProperties:false at every level; every field typed and
    enum/length/range-bounded; every array maxItems-capped.
  * integrity-keyed — bound to intake_id + sha256 so the sanitized view can only
    attach to the exact artifact that was detonated.
  * DERIVED-ONLY (RD-009) — no raw body / raw trace / executable content; the full
    trace stays in Forensic behind a pointer; the crossed events are byte-capped and
    entropy-scrubbed.
  * ZERO-TRUST (RD-014) — the sanitized view is EVIDENCE, never a verdict.
  * RELATIVE CLOCK ONLY — event timings are monotonic offsets from detonation start,
    never a wall clock.
  * OWN VERSION PIN — contract_version enum ['1.0'], pinned SEPARATELY on the Hub
    gate via SANITIZED_TELEMETRY_CONTRACT_VERSION (never rides the shared
    CONTRACT_VERSION).
  * UNIQUE DISCRIMINATOR — the top-level 'sanitized' key does not collide with
    run / scan / rejection / routing / classification / status / collected / behavior.
"""

from __future__ import annotations

# The lane this sanitized view belongs to (matches the 2.4 behavior lane — the
# sanitized view is the cleaned form of the behavior captured during the dynamic run).
LANE = "dynamic_detonation"

# The ordered sanitization stages (proving the pipeline order in the crossed record).
# entropy_scrub -> noise_suppress -> truncate. The Hub records exactly what ran.
SANITIZATION_STAGES = ["entropy_scrub", "noise_suppress", "truncate"]

# How sanitization ended, from the pipeline's point of view. NONE is a safety
# verdict about the artifact — they describe sanitization HEALTH.
#   sanitized       — the raw trace was present and the pipeline produced a view.
#   no_trace        — there was no raw trace to sanitize (capture was tool_unavailable
#                     / not_run / capture_error upstream). Recorded explicitly.
#   sanitize_error  — a trace was present but sanitization failed. Recorded, not fatal.
SANITIZE_STATUSES = ["sanitized", "no_trace", "sanitize_error"]

# The behavioral category of a sanitized event (mirrors the strace -e groups 2.4
# traces: %file / %network / %process / %signal). 'other' is the catch-all so an
# unrecognised-but-kept event is never mis-categorised.
EVENT_CATEGORIES = ["file", "network", "process", "signal", "other"]

# Hard caps on the crossed sanitized view. The FULL trace stays in Forensic behind a
# pointer; only this bounded, token-budgeted view crosses.
MAX_EVENTS = 2000               # capped sanitized-event array
MAX_EVENT_LEN = 512             # a single sanitized event line (byte-capped, scrubbed)
MAX_NAME_LEN = 256              # a syscall name
MAX_COUNT = 100000000           # a bounded count ceiling (100M) for any tally
# The Phase-3 token budget. <=25K tokens is the constraint the sanitized view is
# bounded to (deterministic truncation + a recorded truncated flag). The estimate is
# a deterministic heuristic (chars/4), never a live tokenizer call.
DEFAULT_TOKEN_BUDGET = 25000
MAX_TOKEN_BUDGET = 1000000

# --- A single sanitized behavioral event -------------------------------------
_EVENT = {
    "type": "object",
    "additionalProperties": False,
    "required": ["offset_ms", "category", "syscall", "summary"],
    "properties": {
        "offset_ms": {
            "description": (
                "RELATIVE monotonic offset in milliseconds from detonation start at "
                "which this event was observed. A relative clock only (RD-031: no "
                "wall clock for behavioral timings; derived from the trace's -tt "
                "timestamps as a monotonic delta from the first line)."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": 86400000,
        },
        "category": {
            "description": (
                "The behavioral category of this event (file / network / process / "
                "signal / other). Mirrors the strace syscall groups 2.4 traced."
            ),
            "type": "string",
            "enum": EVENT_CATEGORIES,
        },
        "syscall": {
            "description": (
                "The syscall name for this event (e.g. 'openat', 'connect', "
                "'execve'). Structure is KEPT by the entropy scrub; only high-entropy "
                "VALUES inside the summary are redacted."
            ),
            "type": "string",
            "maxLength": MAX_NAME_LEN,
        },
        "summary": {
            "description": (
                "The SANITIZED one-line summary of this event: the syscall's salient "
                "args with high-entropy VALUES (keys / base64 / random blobs) "
                "replaced by a bounded '[REDACTED:...]' marker and the behavioral "
                "structure (path shape, destination, flags) preserved. Byte-capped. "
                "Inert EVIDENCE, never executed / opened / dialed by the Hub."
            ),
            "type": "string",
            "maxLength": MAX_EVENT_LEN,
        },
        "redacted": {
            "description": (
                "True iff the entropy scrub redacted one or more high-entropy values "
                "in this event's summary. A sanitization-accounting fact, not a "
                "verdict."
            ),
            "type": "boolean",
        },
    },
}

# --- The pipeline accounting sub-object --------------------------------------
_PIPELINE = {
    "description": (
        "The three-stage sanitization accounting: which stages ran (in order), how "
        "much was redacted / suppressed, the token budget and the deterministic "
        "truncation outcome. EVIDENCE of what the pipeline DID to the raw trace so "
        "the transformation is auditable and reproducible. NOT a verdict."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["status", "stages", "token_budget", "estimated_tokens", "truncated"],
    "properties": {
        "status": {
            "description": (
                "How sanitization ended (sanitized / no_trace / sanitize_error). "
                "EVIDENCE of sanitization HEALTH — never a verdict about the "
                "artifact. A missing raw trace is RECORDED here, never a silent gap."
            ),
            "type": "string",
            "enum": SANITIZE_STATUSES,
        },
        "stages": {
            "description": (
                "The ordered sanitization stages that ran: entropy_scrub -> "
                "noise_suppress -> truncate. Records the pipeline order so the "
                "transformation is reproducible."
            ),
            "type": "array",
            "maxItems": len(SANITIZATION_STAGES),
            "items": {"type": "string", "enum": SANITIZATION_STAGES},
        },
        "raw_events": {
            "description": (
                "Number of behavioral events parsed from the RAW trace before "
                "sanitization (the pipeline input size). Bounded count."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": MAX_COUNT,
        },
        "entropy_redactions": {
            "description": (
                "Number of high-entropy VALUES the entropy scrub redacted across all "
                "events (keys / base64 / random blobs replaced by a bounded marker). "
                "Bounded count."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": MAX_COUNT,
        },
        "noise_suppressed": {
            "description": (
                "Number of deterministic host/runtime-noise events the noise "
                "suppressor DROPPED (SSM-agent boot, dynamic-linker library loads, "
                "locale-archive opens, shell/coreutils startup) — NOT the artifact's "
                "own behavior. Bounded count."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": MAX_COUNT,
        },
        "kept_events": {
            "description": (
                "Number of events KEPT after noise suppression, before truncation. "
                "Bounded count."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": MAX_COUNT,
        },
        "emitted_events": {
            "description": (
                "Number of sanitized events actually EMITTED in the bounded 'events' "
                "array after truncation (<= kept_events, <= MAX_EVENTS). Bounded "
                "count."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": MAX_COUNT,
        },
        "token_budget": {
            "description": (
                "The Phase-3 token budget the sanitized view is bounded to (default "
                "25000). Truncation keeps events in trace order until this budget is "
                "reached."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": MAX_TOKEN_BUDGET,
        },
        "estimated_tokens": {
            "description": (
                "The DETERMINISTIC estimated token count of the emitted sanitized "
                "view (a chars/4 heuristic, never a live tokenizer call). Bounded to "
                "<= token_budget by the truncation stage."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": MAX_TOKEN_BUDGET,
        },
        "truncated": {
            "description": (
                "True iff the <=25K-token truncation dropped one or more kept events "
                "to fit the budget (the full trace still stays in Forensic behind the "
                "pointer). A completeness fact, not a verdict. Never a silent drop."
            ),
            "type": "boolean",
        },
    },
}

# --- The source pointer sub-object (RD-009: reference, never duplicate) -------
_SOURCE = {
    "description": (
        "A POINTER to the FULL raw behavioral trace in Forensic S3 (RD-009 — the "
        "full trace stays in Forensic; only this bounded, sanitized view crosses). "
        "REFERENCES the trace, never duplicates it. Absent when there was no trace "
        "to sanitize."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["capture_tool"],
    "properties": {
        "capture_tool": {
            "description": (
                "The host-native capture tool whose trace was sanitized (RD-030: "
                "'strace'), or 'none' when there was no trace."
            ),
            "type": "string",
            "enum": ["strace", "none"],
        },
        "trace_s3_bucket": {
            "description": (
                "Forensic S3 bucket holding the FULL raw behavioral trace that was "
                "sanitized. Absent when no trace was captured."
            ),
            "type": "string",
            "maxLength": 256,
        },
        "trace_s3_key": {
            "description": (
                "Forensic S3 key of the full raw behavioral trace "
                "(traces/<intake_id>/behavior-trace.txt)."
            ),
            "type": "string",
            "maxLength": 1024,
        },
        "raw_trace_bytes": {
            "description": (
                "Size in bytes of the raw trace that was sanitized (the pipeline "
                "input size). Bounded count; EVIDENCE of how much was cleaned."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": MAX_COUNT,
        },
    },
}

# --- The sanitized object: source pointer + pipeline accounting + events ------
_SANITIZED = {
    "description": (
        "The derived, sanitized behavioral view: a pointer to the full raw trace in "
        "Forensic (RD-009), the three-stage pipeline accounting (entropy scrub / "
        "noise suppress / truncate), and the bounded, token-budgeted sanitized event "
        "sequence the Phase-3 Nova Pro correlation engine reasons over. It "
        "REFERENCES — never duplicates — the full trace. EVIDENCE only; NO verdict "
        "anywhere. When there was no raw trace to sanitize (status 'no_trace') the "
        "events array is absent but the pipeline accounting still records the gap "
        "explicitly."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["lane", "pipeline"],
    "properties": {
        "lane": {
            "description": (
                "The lane this sanitized view belongs to. Always 'dynamic_detonation' "
                "(the sanitized form of the behavior captured during the dynamic run)."
            ),
            "type": "string",
            "const": LANE,
        },
        "source": _SOURCE,
        "pipeline": _PIPELINE,
        "events": {
            "description": (
                "The bounded, token-budgeted SANITIZED event sequence (in trace "
                "order): high-entropy values redacted, host/runtime noise suppressed, "
                "truncated to the token budget. The full trace stays in Forensic "
                "(RD-009). Inert EVIDENCE for Phase-3 correlation; never executed."
            ),
            "type": "array",
            "maxItems": MAX_EVENTS,
            "items": _EVENT,
        },
    },
}

SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://ztie.internal/schemas/sanitized-telemetry.contract.v1.json",
    "title": "ZTIE sanitized-telemetry data contract (v1)",
    "description": (
        "The derived, bounded SANITIZED BEHAVIORAL TELEMETRY produced by the Story "
        "2.5 sanitization pipeline (RD-031) for one intake artifact detonated "
        "host-native on the ephemeral EC2, and the NINTH envelope kind on the "
        "Forensic -> Hub RD-013 gate. Story 2.4 CAPTURED the raw behavioral trace "
        "(RD-030) and kept the FULL trace in Forensic (RD-009); Story 2.5 SANITIZES "
        "that raw trace through a three-stage pipeline IN ORDER — (1) entropy scrub "
        "(redact high-entropy VALUES: keys / base64 / random blobs, keeping the "
        "behavioral STRUCTURE), (2) noise suppress (drop deterministic host/runtime "
        "noise: SSM-agent boot, dynamic-linker library loads, locale-archive opens, "
        "shell/coreutils startup), (3) <=25K-token truncation (deterministic, in "
        "trace order, with a recorded truncated flag) — into the bounded, derived "
        "view the Phase-3 Nova Pro correlation engine reasons over. The FULL raw "
        "trace stays in Forensic (RD-009); this envelope REFERENCES it via a pointer "
        "and NEVER duplicates it. All event timings are RELATIVE monotonic offsets "
        "(ms) from detonation start, never a wall clock (only the envelope "
        "'sanitized_at' stamp is wall-clock, for audit correlation). It is NOT a "
        "verdict: there is NO verdict/safe/approved/forward/pass_fail/malicious/clean "
        "field anywhere; the sanitized events and pipeline accounting are EVIDENCE "
        "and the verdict is Hub-side/human-gated (Phase 4). Allow-list: "
        "additionalProperties false at every level; every field typed and "
        "enum/length/range-bounded; every array maxItems-capped. Integrity-keyed by "
        "intake_id + sha256. DERIVED-ONLY. OWN version pin "
        "(SANITIZED_TELEMETRY_CONTRACT_VERSION) + a UNIQUE 'sanitized' discriminator "
        "that does not collide with any other envelope kind."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "contract_version",
        "intake_id",
        "sha256",
        "sanitized_at",
        "sanitized",
    ],
    "properties": {
        "contract_version": {
            "description": (
                "Sanitized-telemetry-contract schema version. Pinned SEPARATELY on "
                "the Hub validator (SANITIZED_TELEMETRY_CONTRACT_VERSION) so this "
                "envelope kind versions independently of the other eight kinds "
                "(never rides the shared CONTRACT_VERSION). The Hub rejects "
                "unknown-version envelopes fail-closed."
            ),
            "type": "string",
            "enum": ["1.0"],
        },
        "intake_id": {
            "description": (
                "The intake UUIDv4 this sanitized view is for. The Hub upserts the "
                "sanitized view onto the tracking record keyed by this."
            ),
            "type": "string",
            "pattern": (
                "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-"
                "[0-9a-f]{12}$"
            ),
        },
        "sha256": {
            "description": (
                "Lowercase hex SHA-256 of the raw artifact body that was detonated. "
                "Integrity key, bound to intake_id; the Hub rejects a sanitized view "
                "whose sha256 does not match the tracked record."
            ),
            "type": "string",
            "pattern": "^[0-9a-f]{64}$",
        },
        "sanitized_at": {
            "description": (
                "RFC3339/ISO-8601 UTC timestamp (Z-suffixed) the orchestrator "
                "finished sanitizing this run's trace in Forensic. This is the ONLY "
                "wall-clock field — all EVENT timings are relative monotonic offsets "
                "(see sanitized.events[].offset_ms)."
            ),
            "type": "string",
            "format": "date-time",
            "maxLength": 40,
        },
        "sanitized": {
            **_SANITIZED,
        },
    },
}


# Repo-root-relative output paths (canonical schema + every bundled lambda
# copy that must stay byte-in-sync). Consumed by scripts/gen_contracts.py.
OUT_PATHS = [
    ("schemas", "sanitized-telemetry.contract.v1.json"),
    ("lambdas", "hub_ingest", "sanitized-telemetry.contract.v1.json"),
    ("lambdas", "detonation", "sanitized-telemetry.contract.v1.json"),
]


def main() -> None:
    from contract_writer import resolve_out_paths, write_contract

    write_contract(SCHEMA, resolve_out_paths(OUT_PATHS))


if __name__ == "__main__":
    main()
