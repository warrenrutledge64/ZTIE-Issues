#!/usr/bin/env python3
"""Generate the ZTIE classification-result data contract (Story 1.2), v1.

Contract-first: this defines the SHAPE of a preprocessor classification result
BEFORE the classifier code — the 1.1R + 1.R lesson (write the shape, the code
falls out). It is written by ``json.dump`` (not fs_write) because the file carries
a remote ``$schema`` URL, which fs_write refuses.

Run:  python3 scripts/gen_classification_contract.py

Design invariants (mirror the intake-tracking contract, RD-013):
  * allow-list — ``additionalProperties: false`` at every level; every field typed
    and length/enum-bounded.
  * integrity-keyed — bound to ``intake_id`` + ``sha256`` so a classification can
    only be attached to the exact artifact it was computed over.
  * DERIVED-ONLY — no raw artifact body / base64 / executable content field. Only
    the derived label + the signals that produced it cross the boundary.
  * ZERO-TRUST — a classification is a LABEL, never a safety verdict and never a
    forward decision. There is deliberately NO ``verdict`` / ``safe`` / ``route``
    field; the verdict is Hub-side / human-gated (Phase 4). Routing is 1.3.
  * DISTRUST-THE-CLAIM — the result records BOTH the extension signal and the
    content signal, whether they agree, and which signal the final label is based
    on. On disagreement the content signal is authoritative.
"""

from __future__ import annotations

# The three artifact classes the preprocessor may assign. Kept small and closed;
# 1.3 routing and 1.4 safe-reject key off exactly this set.
ARTIFACT_CLASSES = ["iac_template", "raw_script", "other_unknown"]

# The signal a per-signal detector may emit. Same closed set, plus "none" for a
# detector that found nothing to go on (e.g. no extension, or unrecognised bytes).
SIGNAL_CLASSES = [*ARTIFACT_CLASSES, "none"]

SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://ztie.internal/schemas/classification.contract.v1.json",
    "title": "ZTIE preprocessor classification-result data contract (v1)",
    "description": (
        "The derived classification LABEL produced by the Story 1.2 preprocessor "
        "for one intake artifact, and the shape allowed to cross the Forensic -> "
        "Hub boundary as a classification update (RD-013). Allow-list: "
        "additionalProperties false at every level; every field typed and "
        "enum/length-bounded. Integrity-keyed by intake_id + sha256 so a label can "
        "only attach to the exact artifact it was computed over. DERIVED-ONLY: no "
        "raw body / base64 / executable content. ZERO-TRUST: a classification is a "
        "LABEL, never a safety verdict and never a forward decision - there is no "
        "verdict/safe/route field; the verdict is Hub-side/human-gated (Phase 4) "
        "and routing is Story 1.3. DISTRUST-THE-CLAIM: records BOTH the extension "
        "signal and the content signal, whether they agree, and which signal the "
        "final label is based on; on disagreement the content signal wins."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "contract_version",
        "intake_id",
        "sha256",
        "classified_at",
        "classification",
    ],
    "properties": {
        "contract_version": {
            "description": (
                "Classification-contract schema version. Pinned so the Hub "
                "validator rejects unknown-version envelopes fail-closed."
            ),
            "type": "string",
            "enum": ["1.0"],
        },
        "intake_id": {
            "description": (
                "The intake UUIDv4 this classification is for. The Hub upserts the "
                "label onto the tracking record keyed by this."
            ),
            "type": "string",
            "pattern": (
                "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-"
                "[0-9a-f]{12}$"
            ),
        },
        "sha256": {
            "description": (
                "Lowercase hex SHA-256 of the raw artifact body the label was "
                "computed over. Integrity key, bound to intake_id; the Hub must "
                "reject a label whose sha256 does not match the tracked record."
            ),
            "type": "string",
            "pattern": "^[0-9a-f]{64}$",
        },
        "classified_at": {
            "description": (
                "RFC3339/ISO-8601 UTC timestamp (Z-suffixed) when classification "
                "was performed in Forensic."
            ),
            "type": "string",
            "format": "date-time",
            "maxLength": 40,
        },
        "classification": {
            "description": (
                "The derived label and the evidence behind it. A LABEL only - "
                "never a verdict or a forward decision."
            ),
            "type": "object",
            "additionalProperties": False,
            "required": [
                "artifact_class",
                "basis",
                "confidence",
                "signals_agree",
                "extension_signal",
                "content_signal",
            ],
            "properties": {
                "artifact_class": {
                    "description": (
                        "The final assigned class. On a claim/content mismatch this "
                        "equals the content signal (distrust-the-claim)."
                    ),
                    "type": "string",
                    "enum": ARTIFACT_CLASSES,
                },
                "basis": {
                    "description": (
                        "Which signal the final class is based on. 'content' when "
                        "content and extension disagree (or extension is absent); "
                        "'extension' only when content is inconclusive but the "
                        "extension is recognised; 'agreement' when both agree."
                    ),
                    "type": "string",
                    "enum": ["content", "extension", "agreement", "none"],
                },
                "confidence": {
                    "description": (
                        "Coarse confidence in the assigned class. 'high' when a "
                        "strong content structure matched; 'medium' on agreement or "
                        "a single strong signal; 'low' for other_unknown / weak "
                        "evidence."
                    ),
                    "type": "string",
                    "enum": ["high", "medium", "low"],
                },
                "signals_agree": {
                    "description": (
                        "True iff the extension signal and the content signal "
                        "resolved to the same artifact_class. False (with the two "
                        "signals recorded) is the distrust-the-claim evidence."
                    ),
                    "type": "boolean",
                },
                "extension_signal": {
                    "description": (
                        "What the (untrusted) filename extension alone suggested. "
                        "Recorded for audit even when overridden by content."
                    ),
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["artifact_class"],
                    "properties": {
                        "artifact_class": {
                            "type": "string",
                            "enum": SIGNAL_CLASSES,
                        },
                        "extension": {
                            "description": (
                                "The lowercased extension observed (without dot), "
                                "or absent if the filename had none."
                            ),
                            "type": "string",
                            "maxLength": 32,
                        },
                    },
                },
                "content_signal": {
                    "description": (
                        "What structural inspection of the actual bytes suggested. "
                        "Authoritative on disagreement with the extension."
                    ),
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["artifact_class"],
                    "properties": {
                        "artifact_class": {
                            "type": "string",
                            "enum": SIGNAL_CLASSES,
                        },
                        "matched_indicator": {
                            "description": (
                                "Short, non-executable label of the structural cue "
                                "that matched (e.g. 'cfn:AWSTemplateFormatVersion', "
                                "'shebang:sh', 'terraform:resource-block'). Audit "
                                "only; never the raw content."
                            ),
                            "type": "string",
                            "maxLength": 128,
                        },
                    },
                },
                "notes": {
                    "description": (
                        "Optional short, bounded, non-executable diagnostic note "
                        "(e.g. why the class is other_unknown). Never raw content."
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
    ("schemas", "classification.contract.v1.json"),
    ("lambdas", "hub_ingest", "classification.contract.v1.json"),
]


def main() -> None:
    from contract_writer import resolve_out_paths, write_contract

    write_contract(SCHEMA, resolve_out_paths(OUT_PATHS))


if __name__ == "__main__":
    main()
