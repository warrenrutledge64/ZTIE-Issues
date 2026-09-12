#!/usr/bin/env python3
"""Generate the ZTIE dynamic-run OUTCOME data contract (Story 2.3), v1.

Contract-first: this is the SIXTH envelope kind that crosses the SAME
one-directional Forensic -> Hub RD-013 gate as the intake-tracking (1.1R),
classification (1.2), routing (1.3), safe-reject (1.4) and static-scan-summary
(2.1/2.2) envelopes.

Run:  python3 scripts/gen_dynamic_run_contract.py

WHAT THIS ENVELOPE IS (and IS NOT):
  * Story 2.3 is the DYNAMIC lane: a routed artifact is EXECUTED, once, host-native
    via SSM on ONE ephemeral EC2 launched from the Story 2.0 launch template, inside
    the Forensic isolated VPC, and the host self-terminates on a hard TTL
    (`shutdown -h +5`). This envelope is the bounded, derived RUN OUTCOME of that
    detonation: WHAT ran, HOW it was executed, and WHETHER the host was contained and
    torn down. It is EVIDENCE of a controlled execution.
  * It is NOT behavioral telemetry (syscalls / network / filesystem) — that is the
    NEXT story (2.4). This contract deliberately has NO field for captured behavior;
    it records only the control-plane outcome of the run.
  * It is NOT a verdict. There is deliberately NO verdict / safe / approved /
    forward / pass_fail / malicious field anywhere. `execution_status` /
    `outcome` describe whether the ORCHESTRATION completed (the host launched, the
    command ran, the host was contained + torn down), NEVER whether the artifact is
    safe. The verdict is Hub-side / human-gated (Phase 4).

WHAT CROSSES vs WHAT STAYS (RD-009 / RD-012 / RD-013):
  * Any raw command stdout/stderr (which can echo artifact content) STAYS IN
    FORENSIC (S3, runs/ prefix), exactly like the static-findings document. Only a
    POINTER (bucket + key) back to it crosses.
  * ONLY this bounded, derived outcome crosses: the instance id, the launch-template
    id it was launched from, whether launch used the template, the SSM command id +
    invocation status, byte-capped truncated tails of stdout/stderr (bounded — for a
    quick operator glance only; the full log stays in Forensic), the containment
    facts (isolated-subnet launch, no-public-ip, IMDSv2), the TTL facts (the hard
    shutdown minutes + whether teardown was observed), and timing. No unbounded log
    text crosses — the schema caps every string.

Design invariants (mirror the five existing crossing contracts, RD-013):
  * allow-list — additionalProperties:false at every level; every field typed and
    enum/length/range-bounded.
  * integrity-keyed — bound to intake_id + sha256 so the outcome can only attach to
    the exact artifact it was detonated over.
  * DERIVED-ONLY — no raw body / base64 / executable content; the full command log
    stays in Forensic behind a pointer; the tails that DO cross are hard byte-capped.
  * ZERO-TRUST — a run outcome is EVIDENCE, never a verdict. NO verdict / safe /
    forward field; `execution_status` is about the ORCHESTRATION, not the artifact.
  * CONTAINED + EPHEMERAL (RD-001 / RD-007 / RD-008) — records host_native:true,
    no_docker:true, isolated_subnet:true, public_ip:false, imdsv2_required:true,
    the hard-TTL minutes, and whether teardown was observed. The host is
    ephemeral, never "temporary".
"""

from __future__ import annotations

# The lane this outcome belongs to (matches the routing contract's lane enum).
LANE = "dynamic_detonation"

# How the run ended, from the ORCHESTRATION's point of view. NONE of these is a
# safety verdict about the artifact — they describe the controlled run itself.
#   completed        — the host launched, the SSM command ran to completion, and
#                      teardown was observed (or the hard TTL is scheduled to fire).
#   execution_error  — the artifact's command exited non-zero / SSM reported a
#                      failed invocation. This is a RUN fact (the thing ran and
#                      failed), still EVIDENCE — NOT a verdict that it is malware.
#   launch_error     — the ephemeral host could not be launched (RunInstances /
#                      capacity / template error). No execution happened.
#   timed_out        — the SSM command did not report a terminal status within the
#                      orchestrator's polling budget (the hard TTL still tears the
#                      host down regardless).
#   delivery_error   — the artifact could not be delivered to the host for
#                      execution (S3 read on-host / staging failed).
OUTCOMES = [
    "completed",
    "execution_error",
    "launch_error",
    "timed_out",
    "delivery_error",
]

# The terminal SSM command invocation statuses we record verbatim (AWS's own set).
# Recorded as EVIDENCE of how the host-native command ended; not a verdict.
SSM_STATUSES = [
    "Success",
    "Failed",
    "Cancelled",
    "TimedOut",
    "Undelivered",
    "Terminated",
    "Pending",
    "InProgress",
    "Delayed",
    "not_run",
]

# Hard byte cap on the stdout/stderr TAILS that cross. The FULL log stays in
# Forensic (runs/ prefix) behind a pointer; only these bounded tails cross for a
# quick operator glance. Matches the "bounded, derived only" rule.
MAX_OUTPUT_TAIL = 4096

# --- The containment facts sub-object (RD-001 / RD-008) ----------------------
_CONTAINMENT = {
    "description": (
        "The blast-radius containment facts for this run, recorded as EVIDENCE that "
        "the detonation was properly contained (RD-001 / RD-008). Every field is a "
        "fact the orchestrator asserted at launch time, not a verdict."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "host_native",
        "no_docker",
        "isolated_subnet",
        "public_ip",
        "imdsv2_required",
    ],
    "properties": {
        "host_native": {
            "description": (
                "Always true. Execution is host-native via SSM SendCommand on the "
                "ephemeral EC2 (RD-001). The artifact is never run in the Hub."
            ),
            "type": "boolean",
            "const": True,
        },
        "no_docker": {
            "description": (
                "Always true. No Docker / container is used on the detonation host "
                "(RD-001 — a container would distort behavioral telemetry). The "
                "artifact runs directly on the ephemeral host."
            ),
            "type": "boolean",
            "const": True,
        },
        "isolated_subnet": {
            "description": (
                "Always true. The host launched into a PRIVATE_ISOLATED subnet of "
                "the Forensic detonation VPC (no IGW / NAT / 0.0.0.0/0) — it cannot "
                "phone home (RD-008)."
            ),
            "type": "boolean",
            "const": True,
        },
        "public_ip": {
            "description": (
                "Always false. The host is launched with no public IP association "
                "(belt-and-suspenders on top of the isolated subnet)."
            ),
            "type": "boolean",
            "const": False,
        },
        "imdsv2_required": {
            "description": (
                "Always true. The launch template requires IMDSv2 on the host."
            ),
            "type": "boolean",
            "const": True,
        },
    },
}

# --- The TTL / teardown facts sub-object (RD-007) ----------------------------
_TEARDOWN = {
    "description": (
        "The hard-TTL / teardown facts for this run (RD-007). The 5-minute hard TTL "
        "(`shutdown -h +N` baked into the Story 2.0 launch-template UserData) is the "
        "safety backstop: every ephemeral host self-terminates even if the "
        "orchestrator dies. This records the configured TTL and whether teardown was "
        "actually observed."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["hard_ttl_minutes", "shutdown_behavior", "teardown_observed"],
    "properties": {
        "hard_ttl_minutes": {
            "description": (
                "The hard TTL in minutes the launch-template UserData enforces via "
                "`shutdown -h +N` (RD-007; 2.0 default 5). A blast-radius / cost "
                "bound, not a verdict input."
            ),
            "type": "integer",
            "minimum": 1,
            "maximum": 60,
        },
        "shutdown_behavior": {
            "description": (
                "The instance-initiated-shutdown behavior set at RunInstances time. "
                "'terminate' means the scheduled halt tears the host down (the "
                "expected value); recorded so a misconfiguration is visible."
            ),
            "type": "string",
            "enum": ["terminate", "stop"],
        },
        "teardown_observed": {
            "description": (
                "True iff the orchestrator observed the host reach a terminated / "
                "shutting-down state before it finished. False does NOT mean the "
                "host survived — the hard TTL still fires independently; it means "
                "the orchestrator did not wait to witness it. An instance confirmed "
                "STILL RUNNING past its TTL is a SEV finding and is recorded via "
                "`teardown_note`, never silently."
            ),
            "type": "boolean",
        },
        "terminated_at": {
            "description": (
                "Optional RFC3339/ISO-8601 UTC timestamp (Z-suffixed) the host was "
                "observed terminated / shutting down, when teardown_observed is true."
            ),
            "type": "string",
            "format": "date-time",
            "maxLength": 40,
        },
        "teardown_note": {
            "description": (
                "Optional short, bounded, non-executable note about teardown (e.g. "
                "'observed shutting-down at TTL' or a SEV note if the host outlived "
                "its TTL). Never raw content."
            ),
            "type": "string",
            "maxLength": 256,
        },
    },
}

# --- The execution facts sub-object ------------------------------------------
_EXECUTION = {
    "description": (
        "How the artifact was executed host-native via SSM, recorded as EVIDENCE. "
        "The FULL command log stays in Forensic behind output_s3_bucket/key; only "
        "the bounded tails cross. NOT a verdict — ssm_status / exit_code describe "
        "how the run ENDED, not whether the artifact is safe."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["mechanism", "ssm_status"],
    "properties": {
        "mechanism": {
            "description": (
                "How the host-native command was issued. 'ssm_send_command' = the "
                "AWS-managed AWS-RunShellScript document via ssm:SendCommand (the "
                "Story 2.3 delivery choice, RD-026)."
            ),
            "type": "string",
            "enum": ["ssm_send_command"],
        },
        "ssm_command_id": {
            "description": (
                "The SSM command id of the host-native execution, for audit "
                "correlation. Absent when the run never reached execution "
                "(launch_error / delivery_error)."
            ),
            "type": "string",
            "maxLength": 128,
        },
        "ssm_status": {
            "description": (
                "The terminal SSM command invocation status (AWS's own set), or "
                "'not_run' when execution was never reached. EVIDENCE of how the "
                "host-native command ended — never a verdict."
            ),
            "type": "string",
            "enum": SSM_STATUSES,
        },
        "exit_code": {
            "description": (
                "The artifact command's process exit code, when SSM reported one. "
                "A RUN fact (0 = ran clean, non-zero = ran and errored) — NOT a "
                "safety verdict."
            ),
            "type": "integer",
            "minimum": -1,
            "maximum": 255,
        },
        "stdout_tail": {
            "description": (
                f"Byte-capped (<= {MAX_OUTPUT_TAIL}) TAIL of the command stdout for "
                "a quick operator glance. Bounded, derived; the FULL log stays in "
                "Forensic behind output_s3_key. Inert text, never executed."
            ),
            "type": "string",
            "maxLength": MAX_OUTPUT_TAIL,
        },
        "stderr_tail": {
            "description": (
                f"Byte-capped (<= {MAX_OUTPUT_TAIL}) TAIL of the command stderr for "
                "a quick operator glance. Bounded, derived; the FULL log stays in "
                "Forensic behind output_s3_key. Inert text, never executed."
            ),
            "type": "string",
            "maxLength": MAX_OUTPUT_TAIL,
        },
        "output_truncated": {
            "description": (
                "True iff the crossed tails were truncated from a larger full log "
                "(which stays in Forensic)."
            ),
            "type": "boolean",
        },
        "output_s3_bucket": {
            "description": (
                "Forensic S3 bucket holding the full command output log (RD-009 — "
                "the full log stays in Forensic; only the tails + this pointer "
                "cross). Absent when no log was captured."
            ),
            "type": "string",
            "maxLength": 256,
        },
        "output_s3_key": {
            "description": (
                "Forensic S3 key of the full command output log "
                "(runs/<intake_id>/detonation-output.json)."
            ),
            "type": "string",
            "maxLength": 1024,
        },
    },
}

SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://ztie.internal/schemas/dynamic-run.contract.v1.json",
    "title": "ZTIE dynamic-run outcome data contract (v1)",
    "description": (
        "The derived RUN OUTCOME produced by the Story 2.3 DYNAMIC lane (detonation "
        "chamber) for one intake artifact routed to the dynamic_detonation lane, and "
        "the ONLY dynamic-lane shape allowed to cross the Forensic -> Hub boundary "
        "(RD-013) — the sixth envelope kind on the Hub gate. It records WHAT ran, HOW "
        "it was executed host-native via SSM on ONE ephemeral EC2 launched from the "
        "Story 2.0 launch template inside the Forensic isolated VPC, the containment "
        "facts, and the hard-TTL teardown outcome. It is NOT behavioral telemetry "
        "(that is Story 2.4 — this schema has no field for captured behavior) and it "
        "is NOT a verdict (no verdict/safe/approved/forward/pass_fail field; "
        "execution_status/outcome describe the ORCHESTRATION, never the artifact's "
        "safety; the verdict is Hub-side/human-gated, Phase 4). The full command log "
        "stays in Forensic (RD-009) behind a pointer; only bounded, byte-capped tails "
        "cross. Allow-list: additionalProperties false at every level; every field "
        "typed and enum/length/range-bounded. Integrity-keyed by intake_id + sha256. "
        "DERIVED-ONLY. CONTAINED + EPHEMERAL: host_native, no_docker, isolated_subnet, "
        "no public IP, IMDSv2, a hard TTL (RD-001 / RD-007 / RD-008)."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "contract_version",
        "intake_id",
        "sha256",
        "detonated_at",
        "run",
    ],
    "properties": {
        "contract_version": {
            "description": (
                "Dynamic-run-contract schema version. Pinned SEPARATELY on the Hub "
                "validator (DYNAMIC_RUN_CONTRACT_VERSION) so this envelope kind "
                "versions independently of the other kinds (2.2's lesson). The Hub "
                "rejects unknown-version envelopes fail-closed."
            ),
            "type": "string",
            "enum": ["1.0"],
        },
        "intake_id": {
            "description": (
                "The intake UUIDv4 this run outcome is for. The Hub upserts the "
                "outcome onto the tracking record keyed by this."
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
                "Integrity key, bound to intake_id; the Hub rejects an outcome whose "
                "sha256 does not match the tracked record."
            ),
            "type": "string",
            "pattern": "^[0-9a-f]{64}$",
        },
        "detonated_at": {
            "description": (
                "RFC3339/ISO-8601 UTC timestamp (Z-suffixed) the detonation run "
                "completed (the orchestrator finished handling it) in Forensic."
            ),
            "type": "string",
            "format": "date-time",
            "maxLength": 40,
        },
        "run": {
            "description": (
                "The derived run outcome: what host ran it, how it was executed, "
                "how it was contained, and how it was torn down. EVIDENCE only — "
                "never a verdict."
            ),
            "type": "object",
            "additionalProperties": False,
            "required": [
                "lane",
                "artifact_class",
                "outcome",
                "launched_from_template",
                "launch_template_id",
                "containment",
                "execution",
                "teardown",
            ],
            "properties": {
                "lane": {
                    "description": (
                        "The lane this outcome belongs to. Always "
                        "'dynamic_detonation' (matches the routing contract's lane "
                        "enum)."
                    ),
                    "type": "string",
                    "const": LANE,
                },
                "artifact_class": {
                    "description": (
                        "The class label the run was based on (from the Story 1.2 "
                        "classification / 1.3 routing)."
                    ),
                    "type": "string",
                    "enum": ["iac_template", "raw_script", "other_unknown"],
                },
                "outcome": {
                    "description": (
                        "How the RUN ended, from the orchestration's point of view "
                        "(completed / execution_error / launch_error / timed_out / "
                        "delivery_error). NOT a safety verdict about the artifact — "
                        "EVIDENCE of the controlled run."
                    ),
                    "type": "string",
                    "enum": OUTCOMES,
                },
                "instance_id": {
                    "description": (
                        "The ephemeral EC2 instance id that ran the artifact, for "
                        "audit correlation. Absent on launch_error (no host was "
                        "created)."
                    ),
                    "type": "string",
                    "maxLength": 64,
                },
                "launched_from_template": {
                    "description": (
                        "True iff the host was launched from the Story 2.0 launch "
                        "template via ec2:RunInstances (NOT CloudFormation-per-run). "
                        "A required containment fact — recorded even on launch_error "
                        "(false then)."
                    ),
                    "type": "boolean",
                },
                "launch_template_id": {
                    "description": (
                        "The Story 2.0 launch-template id the host was (or would be) "
                        "launched from (e.g. lt-...). Read from the "
                        "/ztie/detonation/launch-template-id SSM parameter, never "
                        "hard-coded."
                    ),
                    "type": "string",
                    "maxLength": 64,
                },
                "launch_template_version": {
                    "description": (
                        "Optional launch-template version used ($Latest / $Default / "
                        "a number)."
                    ),
                    "type": "string",
                    "maxLength": 16,
                },
                "instance_type": {
                    "description": (
                        "Optional instance type the host ran as (e.g. t3.small)."
                    ),
                    "type": "string",
                    "maxLength": 32,
                },
                "started_at": {
                    "description": (
                        "Optional RFC3339/ISO-8601 UTC timestamp (Z-suffixed) the "
                        "detonation run started."
                    ),
                    "type": "string",
                    "format": "date-time",
                    "maxLength": 40,
                },
                "duration_ms": {
                    "description": (
                        "Optional wall-clock duration of the orchestrated run in "
                        "milliseconds."
                    ),
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 86400000,
                },
                "error_reason": {
                    "description": (
                        "Optional short, bounded, non-executable reason when outcome "
                        "is an *_error / timed_out (e.g. 'RunInstances failed: "
                        "InsufficientInstanceCapacity'). Never raw content."
                    ),
                    "type": "string",
                    "maxLength": 512,
                },
                "containment": _CONTAINMENT,
                "execution": _EXECUTION,
                "teardown": _TEARDOWN,
            },
        },
    },
}


# Repo-root-relative output paths (canonical schema + every bundled lambda
# copy that must stay byte-in-sync). Consumed by scripts/gen_contracts.py.
OUT_PATHS = [
    ("schemas", "dynamic-run.contract.v1.json"),
    ("lambdas", "hub_ingest", "dynamic-run.contract.v1.json"),
    ("lambdas", "detonation", "dynamic-run.contract.v1.json"),
]


def main() -> None:
    from contract_writer import resolve_out_paths, write_contract

    write_contract(SCHEMA, resolve_out_paths(OUT_PATHS))


if __name__ == "__main__":
    main()
