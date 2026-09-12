#!/usr/bin/env python3
"""Generate the ZTIE collected-record (join) data contract (Story 2.6), v1.

Contract-first: this is the SEVENTH envelope kind that crosses the SAME
one-directional Forensic -> Hub RD-013 gate as the intake-tracking (1.1R),
classification (1.2), routing (1.3), safe-reject (1.4), static-scan-summary
(2.1/2.2) and dynamic-run outcome (2.3) envelopes. It is the record RD-029
describes: the JOIN of the two per-lane derived outputs into ONE bounded,
derived, verdict-free COLLECTED record for one intake_id, ready for Phase-3
aggregation.

Run:  python3 scripts/gen_collected_contract.py

WHAT THIS ENVELOPE IS (and IS NOT):
  * Story 2.6 forks a routed artifact into BOTH inspection lanes concurrently
    (static 2.1/2.2 + dynamic 2.3) for one intake_id, then JOINS their two
    derived outputs into this ONE bounded COLLECTED record. It records WHICH
    lanes routing expected, WHETHER each lane completed / errored / was
    not-applicable, and a small bounded roll-up / pointer for each — so a
    one-lane failure is RECORDED, never silently dropped.
  * It COLLECTS references to the two already-crossed per-lane summaries; it does
    NOT re-embed their full detail. The full static findings document and the
    full dynamic command log stay in Forensic (RD-009); only the bounded roll-ups
    (static: highest_severity + optional findings pointer; dynamic: outcome +
    optional run-log pointer) and the join facts cross.
  * It is NOT a verdict. There is deliberately NO verdict / safe / approved /
    forward / pass_fail / malicious field ANYWHERE. lane_status / outcome /
    highest_severity describe EVIDENCE about the two runs; both_complete says
    whether both expected lanes reported, NEVER whether the artifact is safe. The
    verdict is Hub-side / human-gated (Phase 4), downstream of this join.

Design invariants (mirror the six existing crossing contracts, RD-013 / RD-016):
  * allow-list — additionalProperties:false at every level; every field typed and
    enum/length/range-bounded.
  * integrity-keyed — bound to intake_id + sha256 so the collected record can only
    attach to the exact artifact both lanes inspected.
  * DERIVED-ONLY (RD-009) — no raw body / findings text / command log; references
    the per-lane evidence via bounded roll-ups + Forensic S3 pointers, never
    duplicated.
  * ZERO-TRUST (RD-014) — a collected record is EVIDENCE, never a verdict.
  * OWN VERSION PIN — contract_version enum ['1.0'], pinned SEPARATELY on the Hub
    gate via COLLECTED_CONTRACT_VERSION (never rides the shared CONTRACT_VERSION).
  * UNIQUE DISCRIMINATOR — the top-level 'collected' key does not collide with
    run / scan / rejection / routing / classification / status.
"""

from __future__ import annotations

import json
import os

# The two inspection lanes this record joins (matches the routing contract's lane
# enum). The collected record references these; it does not re-run them.
LANE_STATIC = "static_analysis"
LANE_DYNAMIC = "dynamic_detonation"

# Whether a lane reported for this intake, recorded so a failed OR skipped lane is
# captured, not dropped. NONE of these is a safety verdict about the artifact.
#   completed       — the lane ran and its per-lane summary crossed the gate.
#   errored         — the lane ran (or attempted) and reported an error outcome;
#                     the failure is RECORDED here, not lost.
#   not_applicable  — routing did not expect this lane for this artifact (so there
#                     is nothing to collect for it); recorded explicitly.
LANE_STATUSES = ["completed", "errored", "not_applicable"]

# The dynamic-lane run outcome values we roll up by reference (the exact enum the
# dynamic-run contract emits). EVIDENCE of how the controlled run ended, never a
# verdict.
DYNAMIC_OUTCOMES = [
    "completed",
    "execution_error",
    "launch_error",
    "timed_out",
    "delivery_error",
]

# The worst normalized severity the static lane rolled up, by reference (the exact
# enum the static-scan-summary contract emits). A descriptive roll-up, NOT a
# decision.
STATIC_SEVERITIES = ["none", "info", "low", "medium", "high", "critical"]

# --- The static-lane bounded status sub-object (references 2.1/2.2 summary) ---
_STATIC_STATUS = {
    "description": (
        "The bounded STATIC-lane roll-up for this intake, by reference. It records "
        "whether the static lane completed / errored / was not-applicable, and (when "
        "it completed) the worst severity it rolled up plus a POINTER back to the "
        "full findings document in Forensic (RD-009). It does NOT re-embed the "
        "per-finding detail — that stays in Forensic. EVIDENCE, never a verdict."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["lane", "lane_status"],
    "properties": {
        "lane": {
            "description": (
                "The lane this status is for. Always 'static_analysis' (matches the "
                "routing contract's lane enum and the static-scan-summary lane)."
            ),
            "type": "string",
            "const": LANE_STATIC,
        },
        "lane_status": {
            "description": (
                "Whether the static lane completed / errored / was not-applicable "
                "for this intake. A failed OR skipped lane is RECORDED here, never "
                "dropped. NOT a verdict."
            ),
            "type": "string",
            "enum": LANE_STATUSES,
        },
        "highest_severity": {
            "description": (
                "The worst normalized severity the static lane rolled up (by "
                "reference to the crossed static-scan-summary; 'none' when there "
                "were zero findings). Present when the lane completed. A descriptive "
                "roll-up of EVIDENCE \u2014 NOT a decision about the artifact."
            ),
            "type": "string",
            "enum": STATIC_SEVERITIES,
        },
        "total_findings": {
            "description": (
                "Optional total finding count rolled up from the static-scan "
                "summary, by reference. Bounded; the full findings document stays in "
                "Forensic (RD-009)."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": 1000000,
        },
        "summary_contract_version": {
            "description": (
                "Optional version of the static-scan-summary contract this roll-up "
                "was collected from, for traceability."
            ),
            "type": "string",
            "maxLength": 16,
        },
        "findings_s3_bucket": {
            "description": (
                "Optional Forensic S3 bucket holding the full normalized findings "
                "document (RD-009 \u2014 the full document stays in Forensic; only "
                "this pointer crosses). Referenced, not duplicated."
            ),
            "type": "string",
            "maxLength": 256,
        },
        "findings_s3_key": {
            "description": (
                "Optional Forensic S3 key of the full normalized findings document "
                "(findings/<intake_id>/static-findings.json)."
            ),
            "type": "string",
            "maxLength": 1024,
        },
        "error_reason": {
            "description": (
                "Optional short, bounded, non-executable reason when lane_status is "
                "'errored'. Never raw content."
            ),
            "type": "string",
            "maxLength": 512,
        },
    },
}

# --- The dynamic-lane bounded status sub-object (references 2.3 run outcome) --
_DYNAMIC_STATUS = {
    "description": (
        "The bounded DYNAMIC-lane roll-up for this intake, by reference. It records "
        "whether the dynamic lane completed / errored / was not-applicable, and "
        "(when it ran) the controlled-run outcome plus a POINTER back to the full "
        "command log in Forensic (RD-009). It does NOT re-embed the run detail \u2014 "
        "that stays in Forensic. EVIDENCE, never a verdict."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["lane", "lane_status"],
    "properties": {
        "lane": {
            "description": (
                "The lane this status is for. Always 'dynamic_detonation' (matches "
                "the routing contract's lane enum and the dynamic-run outcome lane)."
            ),
            "type": "string",
            "const": LANE_DYNAMIC,
        },
        "lane_status": {
            "description": (
                "Whether the dynamic lane completed / errored / was not-applicable "
                "for this intake. A failed OR skipped lane is RECORDED here, never "
                "dropped. NOT a verdict."
            ),
            "type": "string",
            "enum": LANE_STATUSES,
        },
        "outcome": {
            "description": (
                "The controlled-run outcome rolled up from the crossed dynamic-run "
                "envelope (completed / execution_error / launch_error / timed_out / "
                "delivery_error). Present when the lane ran. Describes how the "
                "ORCHESTRATION ended \u2014 NOT whether the artifact is safe."
            ),
            "type": "string",
            "enum": DYNAMIC_OUTCOMES,
        },
        "run_contract_version": {
            "description": (
                "Optional version of the dynamic-run contract this roll-up was "
                "collected from, for traceability."
            ),
            "type": "string",
            "maxLength": 16,
        },
        "run_log_s3_bucket": {
            "description": (
                "Optional Forensic S3 bucket holding the full command output log "
                "(RD-009 \u2014 the full log stays in Forensic; only this pointer "
                "crosses). Referenced, not duplicated."
            ),
            "type": "string",
            "maxLength": 256,
        },
        "run_log_s3_key": {
            "description": (
                "Optional Forensic S3 key of the full command output log "
                "(runs/<intake_id>/detonation-output.json)."
            ),
            "type": "string",
            "maxLength": 1024,
        },
        "error_reason": {
            "description": (
                "Optional short, bounded, non-executable reason when lane_status is "
                "'errored'. Never raw content."
            ),
            "type": "string",
            "maxLength": 512,
        },
    },
}

# --- The collected object: per-lane statuses + the join facts ----------------
_COLLECTED = {
    "description": (
        "The joined COLLECTED record: the per-lane bounded status roll-ups (static + "
        "dynamic, by reference) and the join facts (which lanes routing expected, "
        "which reported, whether both completed). It references \u2014 never "
        "duplicates \u2014 the per-lane evidence (RD-009). EVIDENCE only; no verdict "
        "anywhere. both_complete says whether both expected lanes reported, NOT "
        "whether the artifact is safe."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "lanes_expected",
        "lanes_collected",
        "both_complete",
        "static",
        "dynamic",
    ],
    "properties": {
        "lanes_expected": {
            "description": (
                "The set of lanes routing (Story 1.3) expected for this artifact. "
                "The join is measured against this \u2014 a lane routing expected but "
                "that never reported is visible as expected-but-not-collected."
            ),
            "type": "array",
            "minItems": 0,
            "maxItems": 2,
            "uniqueItems": True,
            "items": {
                "type": "string",
                "enum": [LANE_STATIC, LANE_DYNAMIC],
            },
        },
        "lanes_collected": {
            "description": (
                "The set of lanes whose per-lane summary was actually collected into "
                "this record (lane_status 'completed' or 'errored'). A lane routing "
                "expected but missing here is a recorded gap, not a silent drop."
            ),
            "type": "array",
            "minItems": 0,
            "maxItems": 2,
            "uniqueItems": True,
            "items": {
                "type": "string",
                "enum": [LANE_STATIC, LANE_DYNAMIC],
            },
        },
        "both_complete": {
            "description": (
                "True iff every lane routing expected reported (lane_status "
                "'completed'). A JOIN-completeness fact for Phase-3 aggregation \u2014 "
                "NOT a safety verdict; a fully-collected record can still describe a "
                "high-severity finding or an execution_error."
            ),
            "type": "boolean",
        },
        "static": _STATIC_STATUS,
        "dynamic": _DYNAMIC_STATUS,
        "join_note": {
            "description": (
                "Optional short, bounded, non-executable operator note about the "
                "join (e.g. 'dynamic lane not applicable for iac_template' or "
                "'static lane errored; recorded'). Never raw content, never a "
                "verdict."
            ),
            "type": "string",
            "maxLength": 512,
        },
    },
}

SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://ztie.internal/schemas/collected.contract.v1.json",
    "title": "ZTIE collected-record (join) data contract (v1)",
    "description": (
        "The derived, bounded COLLECTED record produced by the Story 2.6 JOIN "
        "(RD-029) for one intake artifact forked into BOTH inspection lanes "
        "concurrently (static 2.1/2.2 + dynamic 2.3), and the SEVENTH envelope kind "
        "on the Forensic -> Hub RD-013 gate. It ties the two already-crossed per-lane "
        "derived outputs together for one intake_id, ready for Phase-3 aggregation: "
        "it records WHICH lanes routing expected, WHETHER each lane completed / "
        "errored / was not-applicable (so a one-lane failure is RECORDED, not lost), "
        "and a bounded roll-up + Forensic pointer for each (static: highest_severity "
        "+ findings pointer; dynamic: outcome + run-log pointer). It REFERENCES \u2014 "
        "never duplicates \u2014 the per-lane detail; the full findings document and "
        "the full command log stay in Forensic (RD-009). It is NOT a verdict: there "
        "is NO verdict/safe/approved/forward/pass_fail/malicious field anywhere; "
        "both_complete is a JOIN-completeness fact, lane_status/outcome/"
        "highest_severity are EVIDENCE, and the verdict is Hub-side/human-gated "
        "(Phase 4). Allow-list: additionalProperties false at every level; every "
        "field typed and enum/length/range-bounded. Integrity-keyed by intake_id + "
        "sha256. DERIVED-ONLY. OWN version pin (COLLECTED_CONTRACT_VERSION) + a "
        "UNIQUE 'collected' discriminator that does not collide with any other "
        "envelope kind."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "contract_version",
        "intake_id",
        "sha256",
        "joined_at",
        "collected",
    ],
    "properties": {
        "contract_version": {
            "description": (
                "Collected-record-contract schema version. Pinned SEPARATELY on the "
                "Hub validator (COLLECTED_CONTRACT_VERSION) so this envelope kind "
                "versions independently of the other six kinds (never rides the "
                "shared CONTRACT_VERSION). The Hub rejects unknown-version envelopes "
                "fail-closed."
            ),
            "type": "string",
            "enum": ["1.0"],
        },
        "intake_id": {
            "description": (
                "The intake UUIDv4 this collected record is for. The Hub upserts the "
                "joined record onto the tracking record keyed by this."
            ),
            "type": "string",
            "pattern": (
                "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-"
                "[0-9a-f]{12}$"
            ),
        },
        "sha256": {
            "description": (
                "Lowercase hex SHA-256 of the raw artifact body both lanes "
                "inspected. Integrity key, bound to intake_id; the Hub rejects a "
                "collected record whose sha256 does not match the tracked record."
            ),
            "type": "string",
            "pattern": "^[0-9a-f]{64}$",
        },
        "joined_at": {
            "description": (
                "RFC3339/ISO-8601 UTC timestamp (Z-suffixed) the join produced this "
                "collected record in Forensic."
            ),
            "type": "string",
            "format": "date-time",
            "maxLength": 40,
        },
        "collected": {
            **_COLLECTED,
        },
    },
}


def main() -> None:
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # Canonical schema location + the bundled copies the Hub validator Lambda and
    # the join-emitting (collector) Lambda load from their own asset dirs. All are
    # written from this one source so they can never drift; hash-check after
    # generating. The lambdas/collector dir is created by FEAT-003; os.makedirs
    # creates it here if it does not exist yet.
    out_paths = [
        os.path.join(repo, "schemas", "collected.contract.v1.json"),
        os.path.join(repo, "lambdas", "hub_ingest", "collected.contract.v1.json"),
        os.path.join(repo, "lambdas", "collector", "collected.contract.v1.json"),
    ]
    for out_path in out_paths:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(SCHEMA, fh, indent=2)
            fh.write("\n")
        print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
