#!/usr/bin/env python3
"""Generate the ZTIE PDE-handoff OUTCOME data contract (Story 4.6, RD-047), v1.

Contract-first: this is the TENTH envelope kind that crosses the SAME
one-directional Forensic -> Hub RD-013 gate as the intake-tracking (1.1R),
classification (1.2), routing (1.3), safe-reject (1.4), static-scan-summary
(2.1/2.2), dynamic-run outcome (2.3), collected-record (2.6), behavioral-telemetry
(2.4) and sanitized-telemetry (2.5) envelopes. It is the bounded, derived,
verdict-free record the Story 4.6 ACCEPT-push MECHANISM emits AFTER it has pushed
(or refused to push) the hash-verified artifact from Forensic to the
Pipeline-Sandbox landing bucket.

Run:  python3 scripts/gen_handoff_contract.py

WHAT THIS ENVELOPE IS (and IS NOT):
  * On a RECORDED HUMAN ACCEPT (never the advisory recommended_verdict, RD-040),
    Story 4.6's Forensic-side `pde_handoff` Lambda hash-verifies the raw artifact
    against the Hub tracking record and pushes it ONE-DIRECTIONALLY +
    LEAST-PRIVILEGE to a Pipeline-Sandbox-owned landing bucket (586917955591). It
    then crosses THIS bounded outcome back to the Hub so the durable record shows
    the enforcement action ran: WHETHER the push happened, and — when it did — a
    POINTER (bucket / key / prefix / account) to where it landed. The pushed
    artifact itself NEVER transits the Hub (RD-009/RD-013); only this pointer +
    bounded facts cross.
  * It is FAIL-CLOSED: an `outcome` of `refused_not_accepted` /
    `refused_hash_mismatch` records that NOTHING left Forensic. Only `pushed`
    means the artifact landed in the Sandbox.
  * It is NOT a verdict. There is deliberately NO verdict / safe / approved /
    forward / pass_fail / malicious / clean field ANYWHERE. The DECISION was the
    human accept (recorded separately as `human_decision` on the tracking item);
    this envelope only records that the mechanism executed and where the bytes
    landed. `outcome` describes the MECHANISM RESULT, never a safety judgement.

Design invariants (mirror the nine existing crossing contracts, RD-013 / RD-016):
  * allow-list — additionalProperties:false at every level; every field typed and
    enum/length/range-bounded.
  * integrity-keyed — bound to intake_id + sha256 so the handoff outcome can only
    attach to the exact artifact that was inspected + verified.
  * DERIVED-ONLY (RD-009) — no raw body; references the landed object via a bounded
    S3 pointer (destination account / bucket / key / prefix), never the payload.
  * ZERO-TRUST (RD-014) — a handoff outcome is EVIDENCE that the mechanism ran,
    never a verdict.
  * OWN VERSION PIN — contract_version enum ['1.0'], pinned SEPARATELY on the Hub
    gate via HANDOFF_CONTRACT_VERSION (never rides the shared CONTRACT_VERSION).
  * UNIQUE DISCRIMINATOR — the top-level 'handoff' key does not collide with any
    other envelope kind (collected / sanitized / behavior / run / scan / rejection
    / routing / classification / status).
"""

from __future__ import annotations

# The mechanism-result values. NONE of these is a safety verdict about the
# artifact; they record what the push MECHANISM did.
#   pushed                 — a recorded human ACCEPT + a verified sha256, so the
#                            artifact was pushed to the Sandbox landing bucket and
#                            it LANDED. This is the only outcome that means bytes
#                            left Forensic.
#   refused_not_accepted   — fail-closed: no recorded human `accepted` decision
#                            (pending / rejected / absent), so nothing was pushed.
#   refused_hash_mismatch  — fail-closed: the recomputed Forensic sha256 did not
#                            match the Hub tracking record's sha256, so nothing was
#                            pushed (SI-7 integrity refusal).
HANDOFF_OUTCOMES = [
    "pushed",
    "refused_not_accepted",
    "refused_hash_mismatch",
]

# The human decision the mechanism observed on the Hub tracking record at push
# time (RD-047 / RD-040). Recorded as EVIDENCE of what gated the action; the
# decision itself is a separate, human-owned field (`human_decision`) on the
# tracking item, written by the Phase-4 human gate (Story 4.4), never by 4.6.
OBSERVED_DECISIONS = ["pending", "accepted", "rejected"]

# --- The destination pointer sub-object (Pipeline-Sandbox landing) -----------
# Present only when outcome == 'pushed'. A POINTER to where the artifact landed in
# the Pipeline-Sandbox account (RD-009 — the artifact stays in the Sandbox under
# PDE control; only this pointer crosses to the Hub). Never the payload.
_DESTINATION = {
    "description": (
        "Pointer to where the accepted, hash-verified artifact LANDED in the "
        "Pipeline-Sandbox account (RD-009 \u2014 the artifact is under PDE control "
        "there; only this pointer crosses to the Hub, never the payload). Present "
        "only when outcome is 'pushed'."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["account_id", "bucket", "key"],
    "properties": {
        "account_id": {
            "description": (
                "The Pipeline-Sandbox AWS account id the artifact was pushed to "
                "(the ZTIE->PDE handoff landing zone; expected 586917955591)."
            ),
            "type": "string",
            "pattern": "^[0-9]{12}$",
        },
        "bucket": {
            "description": (
                "The Pipeline-Sandbox-owned S3 landing bucket the artifact was "
                "pushed to. Sandbox-owned; ZTIE holds only scoped one-prefix "
                "PutObject on it (RD-047)."
            ),
            "type": "string",
            "maxLength": 256,
        },
        "prefix": {
            "description": (
                "The single least-privilege key prefix the Forensic pusher role is "
                "scoped to on the Sandbox landing bucket (the one prefix the "
                "Sandbox bucket policy grants; RD-047 least-privilege)."
            ),
            "type": "string",
            "maxLength": 256,
        },
        "key": {
            "description": (
                "The full S3 key the artifact landed at in the Sandbox bucket "
                "(under the scoped prefix), e.g. "
                "accepted/<intake_id>/<filename>."
            ),
            "type": "string",
            "maxLength": 1024,
        },
        "version_id": {
            "description": (
                "Optional S3 object version id returned by the cross-account "
                "PutObject (present when the landing bucket is versioned), for "
                "traceability of the exact landed object."
            ),
            "type": "string",
            "maxLength": 1024,
        },
    },
}

# --- The handoff object: the mechanism result + the integrity/decision facts --
_HANDOFF = {
    "description": (
        "The bounded PDE-handoff OUTCOME: what the Story 4.6 ACCEPT-push mechanism "
        "did for this intake. It records the mechanism `outcome` (pushed / "
        "refused_not_accepted / refused_hash_mismatch), the human decision it "
        "observed on the tracking record (EVIDENCE of what gated the action), "
        "whether the sha256 verified, and \u2014 only when pushed \u2014 a POINTER to "
        "where the artifact landed in the Pipeline-Sandbox. EVIDENCE only; NO "
        "verdict anywhere. `outcome` is the mechanism result, NOT a safety "
        "judgement; the decision was the human accept."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["outcome", "observed_decision", "hash_verified"],
    "properties": {
        "outcome": {
            "description": (
                "What the push mechanism did. 'pushed' = a recorded human accept + "
                "a verified sha256, so the artifact was pushed and landed in the "
                "Sandbox (the ONLY outcome where bytes left Forensic). "
                "'refused_not_accepted' / 'refused_hash_mismatch' = FAIL-CLOSED, "
                "nothing left Forensic. NEVER a safety verdict."
            ),
            "type": "string",
            "enum": HANDOFF_OUTCOMES,
        },
        "observed_decision": {
            "description": (
                "The human decision the mechanism read off the Hub tracking record "
                "(`human_decision`) at push time. EVIDENCE of what gated the "
                "action \u2014 the push happens ONLY on 'accepted' (RD-040/RD-047: "
                "the advisory recommended_verdict is NEVER the trigger). The "
                "decision itself is a separate, human-owned field written by the "
                "Phase-4 gate (Story 4.4), never by 4.6."
            ),
            "type": "string",
            "enum": OBSERVED_DECISIONS,
        },
        "hash_verified": {
            "description": (
                "True iff the recomputed Forensic sha256 matched the Hub tracking "
                "record's sha256 (SI-7 integrity). A push happens ONLY when this is "
                "true; false records a fail-closed integrity refusal."
            ),
            "type": "boolean",
        },
        "destination": _DESTINATION,
        "pushed_at": {
            "description": (
                "Optional RFC3339/ISO-8601 UTC timestamp (Z-suffixed) the artifact "
                "was pushed to the Sandbox. Present when outcome is 'pushed'."
            ),
            "type": "string",
            "format": "date-time",
            "maxLength": 40,
        },
        "artifact_s3_key": {
            "description": (
                "Optional Forensic S3 key of the raw artifact that was verified + "
                "pushed (intake/<intake_id>/<filename>), for traceability. A "
                "pointer into Forensic \u2014 never the payload."
            ),
            "type": "string",
            "maxLength": 1024,
        },
        "size_bytes": {
            "description": (
                "Optional size in bytes of the verified artifact that was pushed. "
                "Bounded fact, never content."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": 1099511627776,
        },
        "forensic_sweep": {
            "description": (
                "Story 4.10 (RD-059) \u2014 the POST-ACCEPT Forensic sweep accounting. "
                "Present ONLY when outcome is 'pushed' (a verified accept that landed "
                "in the Sandbox), recording that the intake's Forensic prefixes (raw "
                "intake/ + derived findings/ runs/ traces/) were destroyed \u2014 ALL "
                "object versions + delete-markers \u2014 so a human ACCEPT leaves the "
                "blast zone as clean as a human REJECT (Story 4.7). EVIDENCE of "
                "blast-zone hygiene (RD-012), never a verdict. The durable/reusable "
                "infra (bucket/VPC/roles/launch template) is untouched; the report + "
                "durable record survive in the Hub."
            ),
            "type": "object",
            "additionalProperties": False,
            "required": ["swept", "versions_deleted", "prefixes_cleared"],
            "properties": {
                "swept": {
                    "description": (
                        "True iff the post-accept Forensic sweep ran for this intake."
                    ),
                    "type": "boolean",
                },
                "versions_deleted": {
                    "description": (
                        "Count of S3 object versions + delete-markers destroyed across "
                        "the intake's Forensic prefixes. A bounded count, never content."
                    ),
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 1000000,
                },
                "prefixes_cleared": {
                    "description": (
                        "The intake's Forensic prefixes that were swept (e.g. "
                        "intake/<id>/, findings/<id>/, runs/<id>/, traces/<id>/). "
                        "Pointers into Forensic \u2014 never the payload."
                    ),
                    "type": "array",
                    "maxItems": 8,
                    "items": {"type": "string", "maxLength": 256},
                },
            },
        },
        "reason": {
            "description": (
                "Optional short, bounded, non-executable reason for a refusal "
                "(e.g. 'no recorded human accept (human_decision=pending)' or "
                "'sha256 mismatch: artifact does not match tracked record'). Never "
                "raw content, never a verdict."
            ),
            "type": "string",
            "maxLength": 512,
        },
    },
}

SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://ztie.internal/schemas/handoff.contract.v1.json",
    "title": "ZTIE PDE-handoff outcome data contract (v1)",
    "description": (
        "The derived, bounded PDE-handoff OUTCOME produced by the Story 4.6 "
        "ACCEPT-push mechanism (RD-047), and the TENTH envelope kind on the "
        "Forensic -> Hub RD-013 gate. On a RECORDED HUMAN ACCEPT (never the "
        "advisory recommended_verdict, RD-040), the Forensic-side pusher "
        "hash-verifies the raw artifact against the Hub tracking record and pushes "
        "it ONE-DIRECTIONALLY + LEAST-PRIVILEGE to a Pipeline-Sandbox-owned landing "
        "bucket (586917955591); it then crosses THIS bounded outcome back to the "
        "Hub. It records the mechanism `outcome` (pushed / refused_not_accepted / "
        "refused_hash_mismatch \u2014 FAIL-CLOSED: a refusal means nothing left "
        "Forensic), the human decision observed on the tracking record, whether the "
        "sha256 verified, and \u2014 only when pushed \u2014 a POINTER (account / "
        "bucket / prefix / key) to where the artifact landed. The pushed artifact "
        "itself NEVER transits the Hub (RD-009/RD-013); only this pointer + bounded "
        "facts cross. It is NOT a verdict: there is NO verdict/safe/approved/forward/"
        "pass_fail/malicious/clean field anywhere; `outcome` is the MECHANISM "
        "result, the DECISION was the human accept, and the verdict is human-gated. "
        "Allow-list: additionalProperties false at every level; every field typed "
        "and enum/length/range-bounded. Integrity-keyed by intake_id + sha256. "
        "DERIVED-ONLY. OWN version pin (HANDOFF_CONTRACT_VERSION) + a UNIQUE "
        "'handoff' discriminator that does not collide with any other envelope kind."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "contract_version",
        "intake_id",
        "sha256",
        "handed_off_at",
        "handoff",
    ],
    "properties": {
        "contract_version": {
            "description": (
                "PDE-handoff-outcome-contract schema version. Pinned SEPARATELY on "
                "the Hub validator (HANDOFF_CONTRACT_VERSION) so this envelope kind "
                "versions independently of the other nine kinds (never rides the "
                "shared CONTRACT_VERSION). The Hub rejects unknown-version envelopes "
                "fail-closed."
            ),
            "type": "string",
            "enum": ["1.0"],
        },
        "intake_id": {
            "description": (
                "The intake UUIDv4 this handoff outcome is for. The Hub upserts the "
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
                "Lowercase hex SHA-256 of the raw artifact body. Integrity key, "
                "bound to intake_id; the Hub rejects a handoff outcome whose sha256 "
                "does not match the tracked record. This is the same hash the "
                "mechanism verified before pushing (SI-7)."
            ),
            "type": "string",
            "pattern": "^[0-9a-f]{64}$",
        },
        "handed_off_at": {
            "description": (
                "RFC3339/ISO-8601 UTC timestamp (Z-suffixed) the handoff mechanism "
                "produced this outcome in Forensic (the time of the push attempt, "
                "push or refusal)."
            ),
            "type": "string",
            "format": "date-time",
            "maxLength": 40,
        },
        "handoff": {
            **_HANDOFF,
        },
    },
}


# Repo-root-relative output paths (canonical schema + every bundled lambda
# copy that must stay byte-in-sync). Consumed by scripts/gen_contracts.py.
OUT_PATHS = [
    ("schemas", "handoff.contract.v1.json"),
    ("lambdas", "hub_ingest", "handoff.contract.v1.json"),
    ("lambdas", "pde_handoff", "handoff.contract.v1.json"),
]


def main() -> None:
    from contract_writer import resolve_out_paths, write_contract

    write_contract(SCHEMA, resolve_out_paths(OUT_PATHS))


if __name__ == "__main__":
    main()
