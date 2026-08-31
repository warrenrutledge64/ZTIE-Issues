#!/usr/bin/env python3
"""Generate the ZTIE static-scan SUMMARY data contract (Story 2.1), v1.

Contract-first: this is the FIFTH envelope kind that crosses the SAME
one-directional Forensic -> Hub RD-013 gate as the intake-tracking (1.1R),
classification (1.2), routing (1.3) and safe-reject (1.4) envelopes.

Run:  python3 scripts/gen_static_scan_summary_contract.py

WHAT CROSSES vs WHAT STAYS (RD-009 / RD-012):
  * The full normalized findings document (static-findings.contract.v1) MAY echo
    artifact content, so it STAYS IN FORENSIC (S3, findings/ prefix).
  * ONLY this bounded, derived SUMMARY crosses to the Hub: per-tool run status,
    finding counts by normalized severity, the total, the highest severity seen,
    the non-executing flag, and a POINTER (bucket + key) back to the full document
    in Forensic. No finding messages, no matched lines, no resource names, no raw
    content cross — the summary schema has no field for them.

Design invariants (mirror the four existing crossing contracts, RD-013):
  * allow-list — additionalProperties:false at every level; every field typed and
    enum/length/range-bounded.
  * integrity-keyed — bound to intake_id + sha256 so the summary can only attach
    to the exact artifact it was computed over.
  * DERIVED-ONLY — no raw body / base64 / executable content; no finding text.
  * ZERO-TRUST — a scan summary is EVIDENCE, never a verdict. There is deliberately
    NO verdict / safe / approved / forward / pass_fail field. Highest severity is a
    descriptive roll-up of evidence, not a decision. The verdict is Hub-side /
    human-gated (Phase 4).
  * NON-EXECUTING — records non_executing:true; the static lane never runs the
    artifact (RD-001).
"""

from __future__ import annotations

import json
import os

TOOLS = ["cfn-lint", "cfn-guard", "checkov", "bandit"]
SEVERITIES = ["info", "low", "medium", "high", "critical"]
ARTIFACT_CLASSES = ["iac_template", "raw_script", "other_unknown"]

# Per-tool run status carried in the summary (bounded — no finding text crosses).
_TOOL_STATUS = {
    "type": "object",
    "additionalProperties": False,
    "required": ["tool", "status", "finding_count"],
    "properties": {
        "tool": {"type": "string", "enum": TOOLS},
        "status": {
            "description": (
                "'ok' = the tool ran to completion (possibly zero findings); "
                "'error' = the tool failed. An error is recorded, not fatal — the "
                "lane does not crash on a scanner error."
            ),
            "type": "string",
            "enum": ["ok", "error"],
        },
        "finding_count": {"type": "integer", "minimum": 0, "maximum": 1000000},
        "error_reason": {"type": "string", "maxLength": 512},
    },
}

# counts_by_severity — a fixed-key object (one non-negative int per severity), so
# it is fully bounded and cannot smuggle arbitrary keys.
_COUNTS_BY_SEVERITY = {
    "type": "object",
    "additionalProperties": False,
    "required": SEVERITIES,
    "properties": {
        sev: {"type": "integer", "minimum": 0, "maximum": 1000000}
        for sev in SEVERITIES
    },
}

SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://ztie.internal/schemas/static-scan-summary.contract.v1.json",
    "title": "ZTIE static-scan summary data contract (v1)",
    "description": (
        "The derived static-scan SUMMARY produced by the Story 2.1 static lane for "
        "one intake artifact, and the ONLY static-lane shape allowed to cross the "
        "Forensic -> Hub boundary (RD-013) — the fifth envelope kind on the Hub "
        "gate. The full normalized findings document stays in Forensic (RD-009); "
        "this summary carries only bounded, derived counts + a pointer back to it. "
        "Allow-list: additionalProperties false at every level; every field typed "
        "and enum/length/range-bounded. Integrity-keyed by intake_id + sha256. "
        "DERIVED-ONLY: no raw body / finding text / resource names. ZERO-TRUST: a "
        "scan summary is EVIDENCE, never a verdict — no verdict/safe/approved/"
        "forward field; highest_severity is a descriptive roll-up, not a decision; "
        "the verdict is Hub-side/human-gated (Phase 4). NON-EXECUTING (RD-001)."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "contract_version",
        "intake_id",
        "sha256",
        "scanned_at",
        "scan",
    ],
    "properties": {
        "contract_version": {
            "description": (
                "Summary-contract schema version. Pinned so the Hub validator "
                "rejects unknown-version envelopes fail-closed."
            ),
            "type": "string",
            "enum": ["1.0"],
        },
        "intake_id": {
            "description": (
                "The intake UUIDv4 this scan summary is for. The Hub upserts the "
                "summary onto the tracking record keyed by this."
            ),
            "type": "string",
            "pattern": (
                "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-"
                "[0-9a-f]{12}$"
            ),
        },
        "sha256": {
            "description": (
                "Lowercase hex SHA-256 of the raw artifact body the scan ran over. "
                "Integrity key, bound to intake_id; the Hub rejects a summary whose "
                "sha256 does not match the tracked record."
            ),
            "type": "string",
            "pattern": "^[0-9a-f]{64}$",
        },
        "scanned_at": {
            "description": (
                "RFC3339/ISO-8601 UTC timestamp (Z-suffixed) the scan completed "
                "in Forensic."
            ),
            "type": "string",
            "format": "date-time",
            "maxLength": 40,
        },
        "scan": {
            "description": (
                "The derived scan summary: what ran, how much it found, the worst "
                "severity, and a pointer to the full findings document in Forensic. "
                "EVIDENCE only — never a verdict."
            ),
            "type": "object",
            "additionalProperties": False,
            "required": [
                "artifact_class",
                "non_executing",
                "tools",
                "counts_by_severity",
                "total_findings",
                "highest_severity",
                "findings_s3_bucket",
                "findings_s3_key",
            ],
            "properties": {
                "artifact_class": {
                    "description": (
                        "The class label the tool selection was based on (from the "
                        "Story 1.2 classification)."
                    ),
                    "type": "string",
                    "enum": ARTIFACT_CLASSES,
                },
                "non_executing": {
                    "description": (
                        "Always true. The static lane inspects; it never executes "
                        "the artifact (RD-001)."
                    ),
                    "type": "boolean",
                    "const": True,
                },
                "tools": {
                    "description": (
                        "Per-tool run status + finding count. tools_run and "
                        "tools_errored are derivable from this (status field)."
                    ),
                    "type": "array",
                    "minItems": 1,
                    "maxItems": len(TOOLS),
                    "items": _TOOL_STATUS,
                },
                "counts_by_severity": _COUNTS_BY_SEVERITY,
                "total_findings": {
                    "description": (
                        "Total findings across all tools (true pre-truncation "
                        "count, even if the stored findings document was capped)."
                    ),
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 1000000,
                },
                "highest_severity": {
                    "description": (
                        "The worst normalized severity across all findings, or "
                        "'none' when there were zero findings. A descriptive "
                        "roll-up of EVIDENCE — NOT a verdict."
                    ),
                    "type": "string",
                    "enum": ["none", *SEVERITIES],
                },
                "findings_s3_bucket": {
                    "description": (
                        "Forensic S3 bucket holding the full normalized findings "
                        "document (RD-009 — the full document stays in Forensic; "
                        "only this pointer crosses)."
                    ),
                    "type": "string",
                    "maxLength": 256,
                },
                "findings_s3_key": {
                    "description": (
                        "Forensic S3 key of the full normalized findings document "
                        "(findings/<intake_id>/static-findings.json)."
                    ),
                    "type": "string",
                    "maxLength": 1024,
                },
                "findings_truncated": {
                    "description": (
                        "True iff the stored findings document was capped; the "
                        "counts here remain the true pre-truncation totals."
                    ),
                    "type": "boolean",
                },
            },
        },
    },
}


def main() -> None:
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # Canonical schema location + the bundled copy the Hub validator Lambda loads
    # from its own asset dir (mirrors the four existing crossing contracts). Both
    # are written from this one source so they can never drift.
    out_paths = [
        os.path.join(repo, "schemas", "static-scan-summary.contract.v1.json"),
        os.path.join(
            repo, "lambdas", "hub_ingest", "static-scan-summary.contract.v1.json"
        ),
    ]
    for out_path in out_paths:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(SCHEMA, fh, indent=2)
            fh.write("\n")
        print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
