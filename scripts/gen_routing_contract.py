#!/usr/bin/env python3
"""Generate the ZTIE routing-decision data contract (Story 1.3), v1.

Contract-first: this defines the SHAPE of a preprocessor routing decision BEFORE
the router code — the 1.1R + 1.R + 1.2 lesson (write the shape, the code falls
out). It is written by ``json.dump`` (not fs_write) because the file carries a
remote ``$schema`` URL, which fs_write refuses.

Run:  python3 scripts/gen_routing_contract.py

A routing decision turns the derived classification LABEL (Story 1.2) into a PLAN
OF WHICH CONTROLS TO APPLY — the set of downstream Phase-2 lanes an artifact of a
given class should enter (or the safe-reject entry, owned by Story 1.4). It is the
THIRD envelope kind that crosses the SAME one-directional Forensic -> Hub gate as
the intake-tracking (1.1R) and classification (1.2) envelopes.

Design invariants (mirror the intake-tracking + classification contracts, RD-013):
  * allow-list — ``additionalProperties: false`` at every level; every field typed
    and enum/length-bounded; the ``lanes`` array is bounded and enum-constrained.
  * integrity-keyed — bound to ``intake_id`` + ``sha256`` so a routing decision can
    only attach to the exact artifact it was computed over.
  * DERIVED-ONLY — no raw artifact body / base64 / executable content field. Only
    the derived class label + the resulting lane plan cross the boundary.
  * ZERO-TRUST — a routing decision is a PLAN OF CONTROLS, never a safety verdict
    and NEVER a forward-to-PDE decision. There is deliberately NO ``verdict`` /
    ``safe`` / ``approved`` / ``forward`` field; the verdict is Hub-side /
    human-gated (Phase 4). Routing says only "which controls apply."
  * DECLARATIVE — ``lanes`` is a small closed set (the two Phase-2 lanes plus the
    safe-reject entry). ``other_unknown`` / an unroutable class routes to
    ``safe_reject`` (handed to Story 1.4), never into a scanner and never dropped.
"""

from __future__ import annotations

# The class the router routes ON (must match the classification contract's
# artifact_class enum — the label produced by Story 1.2).
ARTIFACT_CLASSES = ["iac_template", "raw_script", "other_unknown"]

# The addressable downstream lane targets. These are the concrete fork targets the
# whole of Phase 2 hangs off (ARCHITECTURE.md):
#   * static_analysis     — the non-executing static lane (cfn-lint, cfn-guard,
#                           checkov, bandit). Story 2.1.
#   * dynamic_detonation  — the dynamic lane: ephemeral EC2 + host-native SSM
#                           detonation. Story 2.3.
#   * safe_reject         — the safe-reject entry for unroutable/incompatible
#                           artifacts. Owned by Story 1.4 (1.3 only hands off).
LANE_IDS = ["static_analysis", "dynamic_detonation", "safe_reject"]

SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://ztie.internal/schemas/routing.contract.v1.json",
    "title": "ZTIE preprocessor routing-decision data contract (v1)",
    "description": (
        "The derived routing DECISION produced by the Story 1.3 router for one "
        "intake artifact, and the shape allowed to cross the Forensic -> Hub "
        "boundary as a routing update (RD-013). A routing decision turns the "
        "class label (Story 1.2) into a PLAN OF WHICH CONTROLS TO APPLY: the set "
        "of downstream Phase-2 lanes the artifact enters, or the safe-reject entry "
        "(Story 1.4) when it is unroutable. Allow-list: additionalProperties false "
        "at every level; every field typed and enum/length-bounded. Integrity-"
        "keyed by intake_id + sha256 so a decision can only attach to the exact "
        "artifact it was computed over. DERIVED-ONLY: no raw body / base64 / "
        "executable content. ZERO-TRUST: a routing decision is a PLAN OF CONTROLS, "
        "never a safety verdict and NEVER a forward-to-PDE decision - there is no "
        "verdict/safe/approved/forward field; the verdict is Hub-side/human-gated "
        "(Phase 4). DECLARATIVE: lanes is a small closed set; other_unknown / an "
        "unroutable class routes to safe_reject (handed to Story 1.4), never into "
        "a scanner and never dropped."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "contract_version",
        "intake_id",
        "sha256",
        "routed_at",
        "routing",
    ],
    "properties": {
        "contract_version": {
            "description": (
                "Routing-contract schema version. Pinned so the Hub validator "
                "rejects unknown-version envelopes fail-closed."
            ),
            "type": "string",
            "enum": ["1.0"],
        },
        "intake_id": {
            "description": (
                "The intake UUIDv4 this routing decision is for. The Hub upserts "
                "the decision onto the tracking record keyed by this."
            ),
            "type": "string",
            "pattern": (
                "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-"
                "[0-9a-f]{12}$"
            ),
        },
        "sha256": {
            "description": (
                "Lowercase hex SHA-256 of the raw artifact body the decision was "
                "computed over. Integrity key, bound to intake_id; the Hub must "
                "reject a decision whose sha256 does not match the tracked record."
            ),
            "type": "string",
            "pattern": "^[0-9a-f]{64}$",
        },
        "routed_at": {
            "description": (
                "RFC3339/ISO-8601 UTC timestamp (Z-suffixed) when the routing "
                "decision was made in Forensic."
            ),
            "type": "string",
            "format": "date-time",
            "maxLength": 40,
        },
        "routing": {
            "description": (
                "The derived routing decision: which lanes apply, and why. A PLAN "
                "OF CONTROLS only - never a verdict or a forward decision."
            ),
            "type": "object",
            "additionalProperties": False,
            "required": [
                "artifact_class",
                "lanes",
                "routable",
                "basis",
            ],
            "properties": {
                "artifact_class": {
                    "description": (
                        "The class label this decision routed on (from the Story "
                        "1.2 classification). The routing table is a pure function "
                        "of this."
                    ),
                    "type": "string",
                    "enum": ARTIFACT_CLASSES,
                },
                "lanes": {
                    "description": (
                        "The ordered, de-duplicated set of downstream lane targets "
                        "this artifact is routed to. For a routable class this is "
                        "one or more Phase-2 lanes (static_analysis and/or "
                        "dynamic_detonation). For an unroutable class it is exactly "
                        "[safe_reject] - handed to Story 1.4, never a scanner."
                    ),
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 3,
                    "uniqueItems": True,
                    "items": {
                        "type": "string",
                        "enum": LANE_IDS,
                    },
                },
                "routable": {
                    "description": (
                        "True iff the class maps to one or more Phase-2 inspection "
                        "lanes. False means the artifact is handed to the "
                        "safe-reject entry (Story 1.4); lanes is then [safe_reject]. "
                        "This is a routing fact, NOT a safety verdict."
                    ),
                    "type": "boolean",
                },
                "basis": {
                    "description": (
                        "How the lane plan was derived. 'class_route' when the "
                        "artifact_class matched a routing-table entry; "
                        "'safe_reject_fallback' when the class was other_unknown or "
                        "an unrecognised class fell through to the safe-reject "
                        "entry (fail-safe hand-off, never a crash)."
                    ),
                    "type": "string",
                    "enum": ["class_route", "safe_reject_fallback"],
                },
                "notes": {
                    "description": (
                        "Optional short, bounded, non-executable diagnostic note "
                        "(e.g. why the artifact was handed to safe-reject). Never "
                        "raw content."
                    ),
                    "type": "string",
                    "maxLength": 256,
                },
            },
        },
    },
}


# Repo-root-relative output paths (canonical schema + every bundled lambda
# copy that must stay byte-in-sync). Consumed by scripts/gen_contracts.py.
OUT_PATHS = [
    ("schemas", "routing.contract.v1.json"),
    ("lambdas", "hub_ingest", "routing.contract.v1.json"),
]


def main() -> None:
    from contract_writer import resolve_out_paths, write_contract

    write_contract(SCHEMA, resolve_out_paths(OUT_PATHS))


if __name__ == "__main__":
    main()
