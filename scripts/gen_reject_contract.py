#!/usr/bin/env python3
"""Generate the ZTIE safe-reject outcome data contract (Story 1.4), v1.

Contract-first: this defines the SHAPE of the safe-reject terminal outcome BEFORE
the code — proven in 1.1R + 1.R + 1.2 + 1.3 (write the shape, the code falls out).
Written by ``json.dump`` because the file carries a remote ``$schema`` URL.

Run:  python3 scripts/gen_reject_contract.py

A safe-reject outcome is a TERMINAL PROCESSING OUTCOME for an artifact that the
router (1.3) could not route to any Phase-2 inspection lane. It records the fact
that the artifact was refused cleanly and why. It is the FOURTH envelope kind that
crosses the one-directional Forensic -> Hub gate (RD-013).

Design invariants:
  * allow-list — ``additionalProperties: false`` everywhere; typed + bounded.
  * integrity-keyed — bound to ``intake_id`` + ``sha256``.
  * DERIVED-ONLY — no raw body / base64 / executable content.
  * TERMINAL PROCESSING OUTCOME, NOT A VERDICT — there is deliberately NO
    ``verdict`` / ``safe`` / ``approved`` / ``forward`` field. A safe-reject says
    "we could not route this, so we refused it cleanly." The human verdict
    (PASS/FAIL/INCONCLUSIVE) is a separate, Hub-side/human-gated Phase-4 decision.
  * NEVER CRASH, NEVER DROP — the whole point of 1.4; the contract records the
    outcome so it is observable and auditable.
"""

from __future__ import annotations

import json
import os

# The reason the artifact was safe-rejected. Currently only one reason
# (unroutable class); the enum is intentionally small and closed.
REJECT_REASONS = ["unroutable_class"]

SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://ztie.internal/schemas/reject.contract.v1.json",
    "title": "ZTIE safe-reject outcome data contract (v1)",
    "description": (
        "The derived safe-reject OUTCOME produced by the Story 1.4 reject handler "
        "for one intake artifact, and the shape allowed to cross the Forensic -> "
        "Hub boundary as a terminal-outcome update (RD-013). A safe-reject records "
        "that an artifact was refused cleanly because it could not be routed to any "
        "Phase-2 inspection lane. It is a TERMINAL PROCESSING OUTCOME, NOT a "
        "safety verdict and NOT a forward-to-PDE decision - there is no "
        "verdict/safe/approved/forward field; the human verdict is Hub-side/"
        "human-gated (Phase 4). Allow-list: additionalProperties false at every "
        "level; every field typed and enum/length-bounded. Integrity-keyed by "
        "intake_id + sha256."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "contract_version",
        "intake_id",
        "sha256",
        "rejected_at",
        "rejection",
    ],
    "properties": {
        "contract_version": {
            "description": (
                "Reject-contract schema version. Pinned so the Hub validator "
                "rejects unknown-version envelopes fail-closed."
            ),
            "type": "string",
            "enum": ["1.0"],
        },
        "intake_id": {
            "description": (
                "The intake UUIDv4 this rejection is for. The Hub upserts the "
                "terminal outcome onto the tracking record keyed by this."
            ),
            "type": "string",
            "pattern": (
                "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-"
                "[0-9a-f]{12}$"
            ),
        },
        "sha256": {
            "description": (
                "Lowercase hex SHA-256 of the raw artifact body. Integrity key."
            ),
            "type": "string",
            "pattern": "^[0-9a-f]{64}$",
        },
        "rejected_at": {
            "description": (
                "RFC3339/ISO-8601 UTC timestamp (Z-suffixed) when the safe-reject "
                "decision was made in Forensic."
            ),
            "type": "string",
            "format": "date-time",
            "maxLength": 40,
        },
        "rejection": {
            "description": (
                "The terminal outcome and the reason. A PROCESSING OUTCOME only - "
                "never a verdict or a forward decision."
            ),
            "type": "object",
            "additionalProperties": False,
            "required": [
                "pipeline_outcome",
                "reason",
                "artifact_class",
            ],
            "properties": {
                "pipeline_outcome": {
                    "description": (
                        "The terminal pipeline outcome. Always SAFE_REJECTED for "
                        "this contract. Distinct from the human verdict "
                        "(PASS/FAIL/INCONCLUSIVE) which is Phase 4."
                    ),
                    "type": "string",
                    "enum": ["SAFE_REJECTED"],
                },
                "reason": {
                    "description": (
                        "Why the artifact was safe-rejected. A closed enum."
                    ),
                    "type": "string",
                    "enum": REJECT_REASONS,
                },
                "artifact_class": {
                    "description": (
                        "The class label that triggered the rejection (from "
                        "the 1.2 classifier / 1.3 router)."
                    ),
                    "type": "string",
                    "enum": ["iac_template", "raw_script", "other_unknown"],
                },
                "notes": {
                    "description": (
                        "Optional short, bounded, non-executable diagnostic note. "
                        "Never raw content."
                    ),
                    "type": "string",
                    "maxLength": 256,
                },
            },
        },
    },
}


def main() -> None:
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_paths = [
        os.path.join(repo, "schemas", "reject.contract.v1.json"),
        os.path.join(repo, "lambdas", "hub_ingest", "reject.contract.v1.json"),
    ]
    for out_path in out_paths:
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(SCHEMA, fh, indent=2)
            fh.write("\n")
        print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
