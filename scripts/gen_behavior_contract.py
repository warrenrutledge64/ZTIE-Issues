#!/usr/bin/env python3
"""Generate the ZTIE behavioral-telemetry data contract (Story 2.4), v1.

Contract-first: this is the EIGHTH envelope kind that crosses the SAME
one-directional Forensic -> Hub RD-013 gate as the intake-tracking (1.1R),
classification (1.2), routing (1.3), safe-reject (1.4), static-scan-summary
(2.1/2.2), dynamic-run outcome (2.3) and collected-record (2.6) envelopes. It is
the record RD-030 describes: the bounded, derived BEHAVIORAL TELEMETRY captured
while a routed artifact detonated host-native on the ephemeral EC2 (Story 2.3) —
what syscalls it made, what network it reached for, what files it touched.

Run:  python3 scripts/gen_behavior_contract.py

WHAT THIS ENVELOPE IS (and IS NOT):
  * Story 2.4 INSTRUMENTS the Story 2.3 detonation: while the artifact runs
    host-native on the ephemeral EC2 (NO Docker, RD-001), the host captures its
    own runtime behavior with a pre-baked host tool (RD-030: ``strace``). The FULL
    trace stays in Forensic S3 (RD-009); this envelope is the bounded, derived
    SUMMARY of that trace: capture health, bounded counts, and a small bounded
    sample of the most-salient syscall / network / filesystem events, with a
    pointer back to the full trace.
  * It is the OBSERVABILITY layer on top of the run 2.3 already performs. The
    dynamic-run OUTCOME (2.3) records the control-plane result (what ran, how it
    ended, contained + torn down). THIS records what the artifact DID.
  * It CAPTURES RAW behavior; it does NOT SANITIZE. The sanitization pipeline
    (entropy scrub -> noise suppress -> <=25K-token truncation) is Story 2.5 and is
    explicitly OUT of this contract. The crossed summary is bounded by ITS OWN
    schema (byte-capped strings, maxItems-capped arrays), but it is not the 2.5
    sanitized/token-budgeted view.
  * Network capture is about INTENT, not success. In the isolated VPC the host has
    no egress, so every outbound connection ATTEMPT fails — but the attempt is the
    signal. This contract records connection ATTEMPTS (destination + whether it
    connected), never only completed connections.
  * TIMESTAMPS ARE RELATIVE. Every time field is a MONOTONIC OFFSET in milliseconds
    from detonation start (``*_offset_ms``), never a human/observer wall clock. The
    only wall-clock field is the top-level ``captured_at`` (when the orchestrator
    finished handling the run, for audit correlation), mirroring the other
    contracts' ``*_at`` envelope stamp.
  * It is NOT a verdict. There is deliberately NO verdict / safe / approved /
    forward / pass_fail / malicious field ANYWHERE. Counts, samples and capture
    health are EVIDENCE about the run; the verdict is Hub-side / human-gated
    (Phase 4), downstream.

Design invariants (mirror the seven existing crossing contracts, RD-013 / RD-016):
  * allow-list — additionalProperties:false at every level; every field typed and
    enum/length/range-bounded; every array maxItems-capped.
  * integrity-keyed — bound to intake_id + sha256 so the telemetry can only attach
    to the exact artifact that was detonated.
  * DERIVED-ONLY (RD-009) — no raw body / raw trace / executable content; the full
    trace stays in Forensic behind a pointer; the crossed samples are byte-capped.
  * ZERO-TRUST (RD-014) — behavioral telemetry is EVIDENCE, never a verdict.
  * HOST-NATIVE + NO-DOCKER (RD-001) — capture ran on the same ephemeral host as the
    detonation, driven over SSM, never in a container. Asserted as a constant.
  * RELATIVE CLOCK ONLY — behavioral timings are monotonic offsets from detonation
    start, never a wall clock.
  * OWN VERSION PIN — contract_version enum ['1.0'], pinned SEPARATELY on the Hub
    gate via BEHAVIOR_CONTRACT_VERSION (never rides the shared CONTRACT_VERSION).
  * UNIQUE DISCRIMINATOR — the top-level 'behavior' key does not collide with
    run / scan / rejection / routing / classification / status / collected.
"""

from __future__ import annotations

import json
import os

# The lane this telemetry belongs to (matches the routing contract's lane enum and
# the dynamic-run outcome lane — behavior is captured during the dynamic run).
LANE = "dynamic_detonation"

# The host-native capture tool (RD-030). ``strace`` is the chosen tool: it is the
# standard Linux syscall tracer and a single strace run yields syscalls, network
# connection attempts (connect/socket/sendto) AND filesystem operations
# (open/openat/write/unlink/rename/chmod) from one trace. ``none`` records the
# degraded case where no capture tool was available on the host (the AMI did not
# ship it and the isolated host cannot install one at boot) — recorded explicitly,
# never a silent gap.
CAPTURE_TOOLS = ["strace", "none"]

# How the capture step ended, from the ORCHESTRATION's point of view. NONE of these
# is a safety verdict about the artifact — they describe capture HEALTH.
#   captured        — the tool ran and a trace was produced + summarized.
#   tool_unavailable— no capture tool was present on the host (degraded; recorded
#                     explicitly so the gap is visible, never hidden). The run's
#                     behavior was NOT captured this time.
#   capture_error   — the tool was present but capture failed (e.g. the trace could
#                     not be read/parsed). Recorded, not fatal to the lane.
#   not_run         — capture was never reached (the detonation never executed —
#                     launch_error / delivery_error upstream). Nothing to capture.
CAPTURE_STATUSES = ["captured", "tool_unavailable", "capture_error", "not_run"]

# Hard caps on the crossed samples (the FULL trace stays in Forensic behind a
# pointer; only these bounded samples cross for a quick operator glance / a
# Phase-3 seed). Sanitization/token-budgeting to <=25K is Story 2.5, NOT here.
MAX_SAMPLE_ITEMS = 50           # per sample array (syscalls / network / fs)
MAX_NAME_LEN = 256              # a syscall name / a path / a destination string
MAX_COUNT = 100000000          # a bounded count ceiling (100M) for any tally

# --- A single bounded (name, count) tally row --------------------------------
def _named_count(name_desc: str, count_desc: str) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["name", "count"],
        "properties": {
            "name": {
                "description": name_desc,
                "type": "string",
                "maxLength": MAX_NAME_LEN,
            },
            "count": {
                "description": count_desc,
                "type": "integer",
                "minimum": 0,
                "maximum": MAX_COUNT,
            },
        },
    }


# --- The syscall summary sub-object ------------------------------------------
_SYSCALLS = {
    "description": (
        "The bounded SYSCALL summary derived from the host trace. EVIDENCE of what "
        "the artifact asked the kernel to do. Bounded: a total count + a capped "
        "top-N of the most-frequent syscall names by count. The full per-call trace "
        "stays in Forensic (RD-009) behind the pointer. NOT a verdict."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["total"],
    "properties": {
        "total": {
            "description": (
                "Total number of syscalls observed in the trace (bounded count)."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": MAX_COUNT,
        },
        "distinct": {
            "description": (
                "Optional number of DISTINCT syscall names observed."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": MAX_COUNT,
        },
        "top": {
            "description": (
                "Capped top-N of the most-frequent syscall names (name + count), "
                "ordered by count descending. Bounded sample for a quick glance / a "
                "Phase-3 seed; the full trace stays in Forensic."
            ),
            "type": "array",
            "maxItems": MAX_SAMPLE_ITEMS,
            "items": _named_count(
                "A syscall name observed in the trace (e.g. 'openat', 'connect').",
                "How many times this syscall was observed.",
            ),
        },
    },
}

# --- The network summary sub-object ------------------------------------------
_NETWORK = {
    "description": (
        "The bounded NETWORK summary derived from the host trace. In the isolated "
        "VPC the host has NO egress, so outbound connection ATTEMPTS fail — but the "
        "ATTEMPT is the signal (INTENT), so this records attempts, not only "
        "completed connections. EVIDENCE of what the artifact reached for. NOT a "
        "verdict."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["connect_attempts"],
    "properties": {
        "connect_attempts": {
            "description": (
                "Total number of outbound connection ATTEMPTS observed (connect/"
                "sendto/etc.), whether or not they succeeded. In the isolated VPC "
                "these fail — the attempt itself is the signal of INTENT."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": MAX_COUNT,
        },
        "distinct_destinations": {
            "description": (
                "Optional number of DISTINCT destinations the attempts targeted."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": MAX_COUNT,
        },
        "dns_lookups": {
            "description": (
                "Optional number of DNS-lookup-shaped operations observed (name "
                "resolution attempts). Bounded count."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": MAX_COUNT,
        },
        "destinations": {
            "description": (
                "Capped sample of DISTINCT connection destinations the artifact "
                "attempted (host:port or ip:port strings + an attempt count + "
                "whether ANY attempt to it connected — false in the isolated VPC). "
                "Bounded sample; the full trace stays in Forensic. Inert strings, "
                "never resolved or dialed by the Hub."
            ),
            "type": "array",
            "maxItems": MAX_SAMPLE_ITEMS,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["destination", "attempts"],
                "properties": {
                    "destination": {
                        "description": (
                            "The destination the artifact attempted to reach "
                            "(host:port / ip:port), as observed in the trace. Inert; "
                            "recorded as EVIDENCE of intent, never contacted."
                        ),
                        "type": "string",
                        "maxLength": MAX_NAME_LEN,
                    },
                    "attempts": {
                        "description": (
                            "How many outbound attempts targeted this destination."
                        ),
                        "type": "integer",
                        "minimum": 0,
                        "maximum": MAX_COUNT,
                    },
                    "connected": {
                        "description": (
                            "True iff ANY attempt to this destination actually "
                            "connected. In the isolated detonation VPC this is "
                            "expected to be false (no egress) — a true here past "
                            "containment would itself be salient EVIDENCE."
                        ),
                        "type": "boolean",
                    },
                },
            },
        },
    },
}

# --- The filesystem summary sub-object ---------------------------------------
_FILESYSTEM = {
    "description": (
        "The bounded FILESYSTEM summary derived from the host trace. EVIDENCE of "
        "what the artifact touched on disk (creates / writes / deletes / renames / "
        "permission changes). Bounded: operation-class counts + a capped sample of "
        "the most-salient paths (writes/creates/deletes). The full trace stays in "
        "Forensic (RD-009). NOT a verdict."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["total_ops"],
    "properties": {
        "total_ops": {
            "description": (
                "Total number of filesystem operations observed (bounded count)."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": MAX_COUNT,
        },
        "opens": {
            "description": "Optional count of open/openat operations.",
            "type": "integer",
            "minimum": 0,
            "maximum": MAX_COUNT,
        },
        "writes": {
            "description": "Optional count of write-class operations.",
            "type": "integer",
            "minimum": 0,
            "maximum": MAX_COUNT,
        },
        "creates": {
            "description": "Optional count of create-class operations (creat / O_CREAT).",
            "type": "integer",
            "minimum": 0,
            "maximum": MAX_COUNT,
        },
        "deletes": {
            "description": "Optional count of delete/unlink-class operations.",
            "type": "integer",
            "minimum": 0,
            "maximum": MAX_COUNT,
        },
        "renames": {
            "description": "Optional count of rename-class operations.",
            "type": "integer",
            "minimum": 0,
            "maximum": MAX_COUNT,
        },
        "permission_changes": {
            "description": "Optional count of chmod/chown-class operations.",
            "type": "integer",
            "minimum": 0,
            "maximum": MAX_COUNT,
        },
        "paths": {
            "description": (
                "Capped sample of the most-salient filesystem paths the artifact "
                "touched (path + the operation class + a touch count). Bounded "
                "sample; the full trace stays in Forensic. Inert strings, never "
                "opened by the Hub."
            ),
            "type": "array",
            "maxItems": MAX_SAMPLE_ITEMS,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["path", "op"],
                "properties": {
                    "path": {
                        "description": (
                            "A filesystem path the artifact touched, as observed in "
                            "the trace. Inert; recorded as EVIDENCE, never opened."
                        ),
                        "type": "string",
                        "maxLength": MAX_NAME_LEN,
                    },
                    "op": {
                        "description": (
                            "The operation class observed for this path."
                        ),
                        "type": "string",
                        "enum": [
                            "open",
                            "write",
                            "create",
                            "delete",
                            "rename",
                            "permission_change",
                            "other",
                        ],
                    },
                    "count": {
                        "description": (
                            "Optional number of times this path was touched with "
                            "this operation class."
                        ),
                        "type": "integer",
                        "minimum": 0,
                        "maximum": MAX_COUNT,
                    },
                },
            },
        },
    },
}

# --- The capture facts sub-object (host-native, no-Docker; RD-001) -----------
_CAPTURE = {
    "description": (
        "The capture facts for this run: which host-native tool ran, whether it was "
        "available, how the capture ended, and the RELATIVE monotonic offsets (ms "
        "from detonation start) at which capture started/stopped. host_native + "
        "no_docker are asserted constants (RD-001) — capture always ran on the same "
        "ephemeral host as the detonation, over SSM, never in a container."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["capture_tool", "capture_status", "host_native", "no_docker"],
    "properties": {
        "capture_tool": {
            "description": (
                "The host-native capture tool used (RD-030: 'strace'), or 'none' "
                "when no capture tool was available on the host (degraded case, "
                "recorded explicitly)."
            ),
            "type": "string",
            "enum": CAPTURE_TOOLS,
        },
        "capture_status": {
            "description": (
                "How the capture ended (captured / tool_unavailable / capture_error "
                "/ not_run). EVIDENCE of capture HEALTH — never a verdict about the "
                "artifact. A missing capture is RECORDED here, never a silent gap."
            ),
            "type": "string",
            "enum": CAPTURE_STATUSES,
        },
        "host_native": {
            "description": (
                "Always true. Capture ran host-native on the ephemeral EC2, driven "
                "over SSM (RD-001) — never in the Hub."
            ),
            "type": "boolean",
            "const": True,
        },
        "no_docker": {
            "description": (
                "Always true. No Docker / container was used for capture (RD-001 — "
                "a container would distort behavioral telemetry). Capture ran "
                "directly on the ephemeral host."
            ),
            "type": "boolean",
            "const": True,
        },
        "capture_started_offset_ms": {
            "description": (
                "RELATIVE monotonic offset in milliseconds from detonation start at "
                "which capture began. A relative clock only (RD: no wall clock for "
                "behavioral timings)."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": 86400000,
        },
        "capture_stopped_offset_ms": {
            "description": (
                "RELATIVE monotonic offset in milliseconds from detonation start at "
                "which capture ended. A relative clock only."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": 86400000,
        },
        "trace_truncated": {
            "description": (
                "True iff the FULL host trace was larger than what was captured / "
                "summarized (the full trace still stays in Forensic behind the "
                "pointer). A capture-completeness fact, not a verdict."
            ),
            "type": "boolean",
        },
        "trace_s3_bucket": {
            "description": (
                "Forensic S3 bucket holding the FULL behavioral trace (RD-009 — the "
                "full trace stays in Forensic; only the bounded summary + this "
                "pointer cross). Absent when no trace was captured."
            ),
            "type": "string",
            "maxLength": 256,
        },
        "trace_s3_key": {
            "description": (
                "Forensic S3 key of the full behavioral trace "
                "(traces/<intake_id>/behavior-trace.txt)."
            ),
            "type": "string",
            "maxLength": 1024,
        },
        "error_reason": {
            "description": (
                "Optional short, bounded, non-executable reason when capture_status "
                "is 'capture_error' / 'tool_unavailable' (e.g. 'strace not present "
                "on host'). Never raw content."
            ),
            "type": "string",
            "maxLength": 512,
        },
    },
}

# --- The behavior object: capture facts + the three summaries ----------------
_BEHAVIOR = {
    "description": (
        "The derived behavioral telemetry: the capture facts (tool, health, "
        "host-native, relative offsets, Forensic trace pointer) and the three "
        "bounded summaries (syscalls, network, filesystem). It REFERENCES — never "
        "duplicates — the full trace (RD-009). EVIDENCE only; NO verdict anywhere. "
        "When capture_status is 'not_run' / 'tool_unavailable', the three summaries "
        "are absent (there was nothing to summarize) but the capture facts still "
        "record the gap explicitly."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["lane", "capture"],
    "properties": {
        "lane": {
            "description": (
                "The lane this telemetry belongs to. Always 'dynamic_detonation' "
                "(behavior is captured during the dynamic run)."
            ),
            "type": "string",
            "const": LANE,
        },
        "capture": _CAPTURE,
        "syscalls": _SYSCALLS,
        "network": _NETWORK,
        "filesystem": _FILESYSTEM,
    },
}

SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://ztie.internal/schemas/behavior.contract.v1.json",
    "title": "ZTIE behavioral-telemetry data contract (v1)",
    "description": (
        "The derived, bounded BEHAVIORAL TELEMETRY produced by the Story 2.4 "
        "instrumentation of the Story 2.3 DYNAMIC lane (RD-030) for one intake "
        "artifact detonated host-native on the ephemeral EC2, and the EIGHTH "
        "envelope kind on the Forensic -> Hub RD-013 gate. While the artifact ran "
        "host-native (NO Docker, RD-001) the ephemeral host captured its own runtime "
        "behavior with a pre-baked host tool (strace); the FULL trace stays in "
        "Forensic (RD-009) behind a pointer, and only this bounded, derived SUMMARY "
        "crosses: capture health, bounded syscall / network / filesystem counts, and "
        "a capped sample of the most-salient events. Network capture records "
        "outbound connection ATTEMPTS (INTENT) — in the isolated VPC the host has no "
        "egress, so attempts fail but the attempt is the signal. All behavioral "
        "timings are RELATIVE monotonic offsets (ms) from detonation start, never a "
        "wall clock (only the envelope 'captured_at' stamp is wall-clock, for audit "
        "correlation). It CAPTURES raw behavior; SANITIZATION (entropy scrub / noise "
        "suppress / <=25K-token truncation) is Story 2.5 and is NOT in this contract. "
        "It is NOT a verdict: there is NO verdict/safe/approved/forward/pass_fail/"
        "malicious field anywhere; counts/samples/capture-health are EVIDENCE and the "
        "verdict is Hub-side/human-gated (Phase 4). Allow-list: additionalProperties "
        "false at every level; every field typed and enum/length/range-bounded; every "
        "array maxItems-capped. Integrity-keyed by intake_id + sha256. DERIVED-ONLY. "
        "OWN version pin (BEHAVIOR_CONTRACT_VERSION) + a UNIQUE 'behavior' "
        "discriminator that does not collide with any other envelope kind."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "contract_version",
        "intake_id",
        "sha256",
        "captured_at",
        "behavior",
    ],
    "properties": {
        "contract_version": {
            "description": (
                "Behavioral-telemetry-contract schema version. Pinned SEPARATELY on "
                "the Hub validator (BEHAVIOR_CONTRACT_VERSION) so this envelope kind "
                "versions independently of the other seven kinds (never rides the "
                "shared CONTRACT_VERSION). The Hub rejects unknown-version envelopes "
                "fail-closed."
            ),
            "type": "string",
            "enum": ["1.0"],
        },
        "intake_id": {
            "description": (
                "The intake UUIDv4 this telemetry is for. The Hub upserts the "
                "telemetry onto the tracking record keyed by this."
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
                "Integrity key, bound to intake_id; the Hub rejects telemetry whose "
                "sha256 does not match the tracked record."
            ),
            "type": "string",
            "pattern": "^[0-9a-f]{64}$",
        },
        "captured_at": {
            "description": (
                "RFC3339/ISO-8601 UTC timestamp (Z-suffixed) the orchestrator "
                "finished handling this run's capture in Forensic. This is the ONLY "
                "wall-clock field — all BEHAVIORAL timings are relative monotonic "
                "offsets (see behavior.capture.*_offset_ms)."
            ),
            "type": "string",
            "format": "date-time",
            "maxLength": 40,
        },
        "behavior": {
            **_BEHAVIOR,
        },
    },
}


def main() -> None:
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # Canonical schema location + the bundled copies the Hub validator Lambda and
    # the detonation lane Lambda load from their own asset dirs. All are written
    # from this one source so they can never drift; hash-check after generating.
    out_paths = [
        os.path.join(repo, "schemas", "behavior.contract.v1.json"),
        os.path.join(repo, "lambdas", "hub_ingest", "behavior.contract.v1.json"),
        os.path.join(repo, "lambdas", "detonation", "behavior.contract.v1.json"),
    ]
    for out_path in out_paths:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(SCHEMA, fh, indent=2)
            fh.write("\n")
        print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
