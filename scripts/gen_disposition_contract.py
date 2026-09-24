#!/usr/bin/env python3
"""Generate the ZTIE REJECT/hold DISPOSITION data contract (Story 4.7, RD-047), v1.

Contract-first: this is the ELEVENTH envelope kind that crosses the SAME
one-directional Forensic -> Hub RD-013 gate as the intake-tracking (1.1R),
classification (1.2), routing (1.3), safe-reject (1.4), static-scan-summary
(2.1/2.2), dynamic-run outcome (2.3), collected-record (2.6), behavioral-telemetry
(2.4), sanitized-telemetry (2.5) and PDE-handoff (4.6) envelopes. It is the bounded,
derived, verdict-free record the Story 4.7 REJECT/hold ENFORCEMENT mechanism emits
AFTER it has destroyed the artifact + its detonation chamber in Forensic (on a
verified Hub-signed `rejected` token) or HELD (destroyed nothing).

Run:  python3 scripts/gen_disposition_contract.py

WHAT THIS ENVELOPE IS (and IS NOT):
  * On a VERIFIED Hub-signed `rejected` decision.token.v1 (RD-048/RD-049, verified
    OFFLINE — never the advisory recommended_verdict, RD-040), Story 4.7's
    Forensic-side `pde_reject` Lambda DESTROYS the raw artifact (all S3 versions +
    delete-markers under intake/<intake_id>/) AND its derived Forensic outputs
    (findings/ runs/ traces/ for the intake) AND terminates any live detonation
    chamber (the ephemeral EC2, if still running — explicit, not TTL). It then
    crosses THIS bounded outcome back to the Hub so the durable record shows the
    enforcement action ran: WHAT was destroyed (by bounded count / state), and that
    the derived report SURVIVES in the Hub. Nothing raw crosses (RD-009/RD-013).
  * It is FAIL-SAFE / FAIL-CLOSED: an `outcome` of `held` records that NOTHING was
    destroyed (INCONCLUSIVE / no valid `rejected` token = the fail-safe default);
    `refused_not_rejected` / `refused_hash_mismatch` record that a token was
    presented but did not authorize a destroy (bad signature / wrong decision /
    stale / untrusted / sha-mismatch), so again NOTHING was destroyed. Only
    `destroyed` means the blast-zone artifact + chamber were torn down.
  * It is NOT a verdict. There is deliberately NO verdict / safe / approved /
    forward / pass_fail / malicious / clean field ANYWHERE. The DECISION was the
    human reject (a Hub-signed token); this envelope only records that the mechanism
    executed and what it tore down. `outcome` describes the MECHANISM RESULT, never
    a safety judgement.

Design invariants (mirror the ten existing crossing contracts, RD-013 / RD-016):
  * allow-list — additionalProperties:false at every level; every field typed and
    enum/length/range-bounded.
  * integrity-keyed — bound to intake_id + sha256 so the disposition outcome can
    only attach to the exact artifact the reject decision was about.
  * DERIVED-ONLY (RD-009) — no raw body; records bounded facts (versions deleted,
    chamber state) + prefixes destroyed, never the payload.
  * ZERO-TRUST (RD-014) — a disposition outcome is EVIDENCE that the mechanism ran,
    never a verdict.
  * OWN VERSION PIN — contract_version enum ['1.0'], pinned SEPARATELY on the Hub
    gate via DISPOSITION_CONTRACT_VERSION (never rides the shared CONTRACT_VERSION).
  * UNIQUE DISCRIMINATOR — the top-level 'disposition' key does not collide with any
    other envelope kind (handoff / collected / sanitized / behavior / run / scan /
    rejection / routing / classification / status).
"""

from __future__ import annotations

# The mechanism-result values. NONE of these is a safety verdict about the
# artifact; they record what the REJECT/destroy MECHANISM did.
#   destroyed              — a VERIFIED Hub-signed `rejected` token + a matching
#                            sha256, so the raw artifact (all versions) + its derived
#                            Forensic outputs were destroyed and any live chamber was
#                            terminated. The only outcome where anything was torn down.
#   held                   — FAIL-SAFE: no `rejected` token was presented at all
#                            (INCONCLUSIVE / pending / absent), so the intake is HELD
#                            at the approval gate and NOTHING was destroyed.
#   refused_not_rejected   — FAIL-CLOSED: a token was presented but it did not
#                            authorize a destroy (bad signature / wrong decision
#                            e.g. `accepted` / stale / untrusted key / malformed), so
#                            NOTHING was destroyed.
#   refused_hash_mismatch  — FAIL-CLOSED: the token's sha256 did not match the
#                            recomputed Forensic artifact sha256 (a token for a
#                            different artifact), so NOTHING was destroyed (SI-7).
DISPOSITION_OUTCOMES = [
    "destroyed",
    "held",
    "refused_not_rejected",
    "refused_hash_mismatch",
]

# The human decision the mechanism observed on the presented token (RD-047 /
# RD-040). Recorded as EVIDENCE of what gated the action; the decision itself is a
# Hub-signed token, human-owned, produced by the Phase-4 human gate (Story 4.4),
# never by 4.7. `pending` = no `rejected` token was presented (the hold path).
OBSERVED_DECISIONS = ["pending", "accepted", "rejected"]

# The state of the detonation chamber (the ephemeral Story-2.3 EC2) for this intake
# at reject time. Recorded as bounded EVIDENCE of the teardown.
#   terminated    — a live chamber was found and this mechanism terminated it
#                   explicitly (not waiting for the 5-min hard TTL).
#   none_running  — no live chamber was found (the common case — the hard TTL
#                   already reaped it), so there was nothing to terminate.
#   not_checked   — the chamber was not inspected (only on a hold / refusal, where
#                   nothing is destroyed so the chamber is deliberately left alone).
CHAMBER_STATES = ["terminated", "none_running", "not_checked"]

# --- The destroyed sub-object: bounded facts about what was torn down --------
# Present only when outcome == 'destroyed'. Bounded counts + the chamber state +
# the prefixes cleared. NEVER the payload; NEVER a per-object listing that could
# echo artifact content — just counts and prefixes (RD-009).
_DESTROYED = {
    "description": (
        "Bounded facts about what the mechanism tore down in Forensic when outcome "
        "is 'destroyed': how many S3 object versions (+ delete-markers) were deleted "
        "under the intake's prefixes, which prefixes were cleared, and the detonation "
        "chamber state. A COUNT + prefix list, never a per-object listing and never "
        "the payload (RD-009). Present only when outcome is 'destroyed'."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["artifact_versions_deleted", "prefixes_cleared", "chamber"],
    "properties": {
        "artifact_versions_deleted": {
            "description": (
                "Total number of S3 object versions AND delete-markers deleted "
                "across all of the intake's Forensic prefixes (the versioned bucket "
                "requires deleting every version + marker \u2014 a plain delete leaves "
                "versions). A bounded count, never content."
            ),
            "type": "integer",
            "minimum": 0,
            "maximum": 1000000,
        },
        "prefixes_cleared": {
            "description": (
                "The Forensic S3 key prefixes that were destroyed for this intake "
                "(e.g. intake/<id>/, findings/<id>/, runs/<id>/, traces/<id>/). "
                "POINTERS into Forensic \u2014 never the payload. Bounded list."
            ),
            "type": "array",
            "maxItems": 16,
            "items": {
                "type": "string",
                "maxLength": 256,
            },
        },
        "chamber": {
            "description": (
                "The detonation chamber (ephemeral Story-2.3 EC2) state for this "
                "intake at reject time: 'terminated' (a live host was found and "
                "explicitly terminated, not waiting for the TTL), or 'none_running' "
                "(no live host \u2014 the common case, the hard TTL already reaped it)."
            ),
            "type": "string",
            "enum": ["terminated", "none_running"],
        },
        "chamber_instance_id": {
            "description": (
                "Optional EC2 instance id of the live chamber that was terminated "
                "(present only when chamber is 'terminated'), for traceability. A "
                "bounded identifier, never content."
            ),
            "type": "string",
            "maxLength": 64,
        },
        "destroyed_at": {
            "description": (
                "Optional RFC3339/ISO-8601 UTC timestamp (Z-suffixed) the destroy "
                "completed in Forensic. Present when outcome is 'destroyed'."
            ),
            "type": "string",
            "format": "date-time",
            "maxLength": 40,
        },
    },
}

# --- The disposition object: the mechanism result + integrity/decision facts -
_DISPOSITION = {
    "description": (
        "The bounded REJECT/hold DISPOSITION OUTCOME: what the Story 4.7 mechanism "
        "did for this intake. It records the mechanism `outcome` (destroyed / held / "
        "refused_not_rejected / refused_hash_mismatch), the human decision it "
        "observed on the presented token (EVIDENCE of what gated the action), whether "
        "the sha256 verified, whether the derived report survives (always true \u2014 "
        "the Hub record is untouched), the chamber state, and \u2014 only when "
        "destroyed \u2014 bounded facts about what was torn down. EVIDENCE only; NO "
        "verdict anywhere. `outcome` is the mechanism result, NOT a safety judgement; "
        "the decision was the human reject (a Hub-signed token)."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "outcome",
        "observed_decision",
        "hash_verified",
        "chamber_state",
        "report_survives",
    ],
    "properties": {
        "outcome": {
            "description": (
                "What the reject/hold mechanism did. 'destroyed' = a verified "
                "Hub-signed `rejected` token + a matching sha256, so the raw artifact "
                "(all versions) + its derived Forensic outputs were destroyed and any "
                "live chamber was terminated (the ONLY outcome where anything was "
                "torn down). 'held' = FAIL-SAFE, no `rejected` token presented "
                "(INCONCLUSIVE / pending), nothing destroyed. "
                "'refused_not_rejected' / 'refused_hash_mismatch' = FAIL-CLOSED, a "
                "token was presented but did not authorize a destroy, nothing "
                "destroyed. NEVER a safety verdict."
            ),
            "type": "string",
            "enum": DISPOSITION_OUTCOMES,
        },
        "observed_decision": {
            "description": (
                "The human decision the mechanism observed on the presented token. "
                "EVIDENCE of what gated the action \u2014 the destroy happens ONLY on "
                "a verified 'rejected' token (RD-040/RD-047: the advisory "
                "recommended_verdict is NEVER the trigger). 'pending' = no `rejected` "
                "token was presented (the hold path). The decision itself is a "
                "Hub-signed token, human-owned, produced by the Phase-4 gate (Story "
                "4.4), never by 4.7."
            ),
            "type": "string",
            "enum": OBSERVED_DECISIONS,
        },
        "hash_verified": {
            "description": (
                "True iff the recomputed Forensic sha256 matched the presented "
                "token's sha256 (SI-7 integrity + artifact binding). A destroy "
                "happens ONLY when this is true (among the other checks); false "
                "records a fail-closed integrity refusal. On a pure hold (no token) "
                "this is false (no artifact binding was checked)."
            ),
            "type": "boolean",
        },
        "chamber_state": {
            "description": (
                "The detonation chamber state observed by the mechanism: 'terminated' "
                "/ 'none_running' when a destroy ran (the chamber was inspected), or "
                "'not_checked' on a hold / refusal (nothing is destroyed, so the "
                "chamber is deliberately left to its hard TTL)."
            ),
            "type": "string",
            "enum": CHAMBER_STATES,
        },
        "report_survives": {
            "description": (
                "Always true. The derived report + the durable tracking record live "
                "in the Hub (RD-012) and are NEVER touched by 4.7 \u2014 only the "
                "Forensic blast-zone artifact + chamber are destroyed. Recorded "
                "explicitly so the audit trail affirms the report survives a reject."
            ),
            "type": "boolean",
        },
        "destroyed": _DESTROYED,
        "artifact_s3_key": {
            "description": (
                "Optional Forensic S3 key of the raw artifact the reject decision was "
                "about (intake/<intake_id>/<filename>), for traceability. A pointer "
                "into Forensic \u2014 never the payload."
            ),
            "type": "string",
            "maxLength": 1024,
        },
        "reason": {
            "description": (
                "Optional short, bounded, non-executable reason for a hold / refusal "
                "(e.g. 'no rejected decision token presented (hold at approval gate)' "
                "or 'wrong_decision: decision \\'accepted\\' != required "
                "\\'rejected\\''). Never raw content, never a verdict."
            ),
            "type": "string",
            "maxLength": 512,
        },
    },
}

SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://ztie.internal/schemas/disposition.contract.v1.json",
    "title": "ZTIE REJECT/hold disposition data contract (v1)",
    "description": (
        "The derived, bounded REJECT/hold DISPOSITION OUTCOME produced by the Story "
        "4.7 enforcement mechanism (RD-047, per RD-048/RD-049), and the ELEVENTH "
        "envelope kind on the Forensic -> Hub RD-013 gate. On a VERIFIED Hub-signed "
        "`rejected` decision token (verified OFFLINE \u2014 never the advisory "
        "recommended_verdict, RD-040), the Forensic-side destroyer tears down the raw "
        "artifact (all S3 versions + delete-markers under intake/<intake_id>/) + its "
        "derived Forensic outputs (findings/ runs/ traces/) AND terminates any live "
        "detonation chamber (explicit, not TTL); it then crosses THIS bounded outcome "
        "back to the Hub. It records the mechanism `outcome` (destroyed / held / "
        "refused_not_rejected / refused_hash_mismatch \u2014 FAIL-SAFE: only "
        "'destroyed' means anything was torn down; 'held' is the INCONCLUSIVE/"
        "no-token default and destroys NOTHING), the human decision observed on the "
        "token, whether the sha256 verified, the chamber state, that the derived "
        "report SURVIVES in the Hub, and \u2014 only when destroyed \u2014 bounded "
        "facts about what was torn down (version count, prefixes, chamber). Nothing "
        "raw crosses (RD-009/RD-013). It is NOT a verdict: there is NO verdict/safe/"
        "approved/forward/pass_fail/malicious/clean field anywhere; `outcome` is the "
        "MECHANISM result, the DECISION was the human reject, and the verdict is "
        "human-gated. Allow-list: additionalProperties false at every level; every "
        "field typed and enum/length/range-bounded. Integrity-keyed by intake_id + "
        "sha256. DERIVED-ONLY. OWN version pin (DISPOSITION_CONTRACT_VERSION) + a "
        "UNIQUE 'disposition' discriminator that does not collide with any other "
        "envelope kind."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "contract_version",
        "intake_id",
        "sha256",
        "disposed_at",
        "disposition",
    ],
    "properties": {
        "contract_version": {
            "description": (
                "REJECT/hold-disposition-contract schema version. Pinned SEPARATELY "
                "on the Hub validator (DISPOSITION_CONTRACT_VERSION) so this envelope "
                "kind versions independently of the other ten kinds (never rides the "
                "shared CONTRACT_VERSION). The Hub rejects unknown-version envelopes "
                "fail-closed."
            ),
            "type": "string",
            "enum": ["1.0"],
        },
        "intake_id": {
            "description": (
                "The intake UUIDv4 this disposition outcome is for. The Hub upserts "
                "the outcome onto the tracking record keyed by this."
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
                "bound to intake_id; the Hub rejects a disposition outcome whose "
                "sha256 does not match the tracked record. On a destroy this is the "
                "same hash the mechanism verified against the token before destroying "
                "(SI-7); on a hold it is the recomputed artifact hash (or the "
                "tracked hash echoed) so the outcome still binds to the record."
            ),
            "type": "string",
            "pattern": "^[0-9a-f]{64}$",
        },
        "disposed_at": {
            "description": (
                "RFC3339/ISO-8601 UTC timestamp (Z-suffixed) the disposition "
                "mechanism produced this outcome in Forensic (the time of the reject "
                "attempt, destroy or hold or refusal)."
            ),
            "type": "string",
            "format": "date-time",
            "maxLength": 40,
        },
        "disposition": {
            **_DISPOSITION,
        },
    },
}


# Repo-root-relative output paths (canonical schema + every bundled lambda
# copy that must stay byte-in-sync). Consumed by scripts/gen_contracts.py.
OUT_PATHS = [
    ("schemas", "disposition.contract.v1.json"),
    ("lambdas", "hub_ingest", "disposition.contract.v1.json"),
    ("lambdas", "pde_reject", "disposition.contract.v1.json"),
]


def main() -> None:
    from contract_writer import resolve_out_paths, write_contract

    write_contract(SCHEMA, resolve_out_paths(OUT_PATHS))


if __name__ == "__main__":
    main()
