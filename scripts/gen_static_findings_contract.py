#!/usr/bin/env python3
"""Generate the ZTIE normalized static-findings document schema (Story 2.1), v1.

Contract-first (the 1.1R / 1.R / 1.2 / 1.3 / 1.4 lesson): settle the SHAPE before
the scanner glue. This schema defines ONE normalized findings shape across all four
static tools (cfn-lint, cfn-guard, checkov, bandit) so Phase 3 correlation consumes
a single format regardless of which tool produced a finding.

Run:  python3 scripts/gen_static_findings_contract.py

It is written by ``json.dump`` (not fs_write) because the file carries a remote
``$schema`` URL, which fs_write refuses.

WHERE THIS DOCUMENT LIVES (RD-009 / RD-012): the normalized findings document is a
DERIVED artifact of the static scan. It MAY echo artifact content (rule messages,
matched lines, resource names), so per RD-009 it STAYS IN FORENSIC — written to the
Forensic artifact S3 bucket under a ``findings/`` prefix. It does NOT cross to the
Hub. Only a bounded, derived *summary* crosses the RD-013 gate (see
``gen_static_scan_summary_contract.py``); the summary carries a pointer
(``findings_s3_bucket`` / ``findings_s3_key``) to this document.

This schema is therefore NOT bundled into the Hub validator Lambda — the Hub never
parses this document. It is the on-disk / in-S3 shape the static-scan Lambda writes
and that the Phase-3 correlation lane (later) reads back from Forensic. It is used
here to (a) document the shape, (b) validate the static-scan Lambda's own output in
tests, and (c) be the single source Phase 3 builds against.

Design invariants:
  * ONE shape for four tools. Every tool's native output is normalized into the same
    ``finding`` object: which tool, its native rule id, a normalized severity, a
    location (file + optional line span), a bounded message, and the check family.
  * NON-EXECUTING. This is static evidence only. The document records
    ``non_executing: true`` and has no runtime/behavioral field — that is the
    dynamic lane (RD-001, Story 2.3/2.4), a separate contract (RD-017 draft).
  * EVIDENCE, NEVER A VERDICT (zero-trust). There is deliberately no ``verdict`` /
    ``safe`` / ``approved`` / ``forward`` / ``pass_fail`` field. A static finding is
    evidence for the Phase-4 human gate; it is not itself a decision.
  * BOUNDED. Arrays and strings are length-capped so a hostile artifact cannot
    produce an unbounded findings document. ``additionalProperties: false`` at every
    level — an allow-list, like every ZTIE contract.
  * DERIVED-ONLY. No raw artifact body / base64 / executable content field. Messages
    and matched-line snippets are bounded, inert text for triage.
"""

from __future__ import annotations

# The static tools (RD-004). Every finding names exactly one of these.
#   cfn-lint       — CloudFormation template linter (IaC)
#   cfn-guard      — AWS policy-as-code rule engine (IaC)
#   checkov        — multi-framework IaC + config misconfiguration scanner
#   bandit         — Python source SAST
#   gitleaks       — compiled secret scanner (Story 2.2G): the SOLE source of truth
#                    for secret detection; supersedes the 2.2 embedded SECRET regex.
#   signature-scan — ZTIE signature engine (Story 2.2/2.2G): known-bad patterns /
#                    IoCs (DANGEROUS + MALWARE families; SECRET moved to gitleaks),
#                    NON-EXECUTING regex over the artifact bytes.
TOOLS = ["cfn-lint", "cfn-guard", "checkov", "bandit", "gitleaks", "signature-scan"]

# The classes a static scan runs against (must match the classification /
# routing contracts' artifact_class enum). other_unknown never reaches the static
# lane (it is safe-rejected in Phase 1), but it is listed so the enum is closed.
ARTIFACT_CLASSES = ["iac_template", "raw_script", "other_unknown"]

# Normalized severity ladder — the single scale every tool's native severity is
# mapped onto. Ordered low -> high; the summary's highest_severity is the max of
# these seen across all findings.
SEVERITIES = ["info", "low", "medium", "high", "critical"]

# The kind of check that produced a finding — lets Phase 3 group IaC-config vs
# policy-as-code vs SAST vs signature evidence without re-deriving it from the tool
# name. Story 2.2 adds 'signature' for the signature engine's hits.
CHECK_FAMILIES = ["iac_lint", "policy_as_code", "iac_misconfig", "sast", "signature"]

# Story 2.2 — compliance-framework mapping. Each finding may carry a bounded
# 'compliance' sub-object mapping it to the control(s) it IMPLICATES in NIST SP
# 800-53 Rev 5 and ISO/IEC 27001:2022 Annex A (RD-004 / RD-014 framework scope).
# candidate-vs-ratified: 'basis' is 'ratified' (reviewer-accepted), 'proposed'
# (candidate), or 'unmapped' (no honest mapping — empty control lists). This is
# EVIDENCE ("this finding implicates control X"), NEVER a verdict.
MAPPING_BASES = ["ratified", "proposed", "unmapped"]
_COMPLIANCE = {
    "description": (
        "Story 2.2 — the compliance control(s) this finding IMPLICATES, mapped from "
        "the finding's tool + native rule_id. NIST SP 800-53 Rev 5 (catalog of "
        "record) + ISO/IEC 27001:2022 Annex A. EVIDENCE, NEVER A VERDICT: a mapping "
        "says a finding implicates a control, never that the artifact fails. "
        "candidate-vs-ratified (RD-014): basis distinguishes reviewer-ratified from "
        "proposed candidate mappings; an unmapped finding carries empty control "
        "lists + basis 'unmapped' (ZTIE does not fabricate a control). Bounded: "
        "control-id strings short + capped, control lists capped."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": ["nist_800_53", "iso_27001", "basis", "mapping_version"],
    "properties": {
        "nist_800_53": {
            "description": (
                "NIST SP 800-53 Rev 5 control ids the finding implicates (e.g. "
                "'SC-28', 'AC-3'). May be empty (unmapped)."
            ),
            "type": "array",
            "maxItems": 8,
            "items": {"type": "string", "maxLength": 32},
        },
        "iso_27001": {
            "description": (
                "ISO/IEC 27001:2022 Annex A control ids the finding implicates "
                "(e.g. 'A.8.24'). May be empty (unmapped)."
            ),
            "type": "array",
            "maxItems": 8,
            "items": {"type": "string", "maxLength": 32},
        },
        "basis": {
            "description": (
                "candidate-vs-ratified (RD-014). 'ratified' = an accountable "
                "reviewer accepted this mapping; 'proposed' = candidate, authored "
                "not yet reviewed; 'unmapped' = no honest mapping (empty lists). "
                "ZTIE claims coverage only for ratified mappings."
            ),
            "type": "string",
            "enum": MAPPING_BASES,
        },
        "mapping_version": {
            "description": (
                "Version of the mapping table that produced this mapping, so a "
                "stored finding is traceable to the exact table."
            ),
            "type": "string",
            "maxLength": 32,
        },
        "rationale": {
            "description": (
                "Optional bounded, inert rationale for the mapping (why the finding "
                "implicates the control). Present only when mapped."
            ),
            "type": "string",
            "maxLength": 512,
        },
    },
}

_FINDING = {
    "type": "object",
    "additionalProperties": False,
    "required": ["tool", "rule_id", "severity", "check_family", "message"],
    "properties": {
        "tool": {
            "description": "Which static tool produced this finding.",
            "type": "string",
            "enum": TOOLS,
        },
        "rule_id": {
            "description": (
                "The tool's NATIVE rule / check identifier, verbatim and bounded "
                "(e.g. cfn-lint 'E3012', checkov 'CKV_AWS_20', bandit 'B602', a "
                "cfn-guard rule name). Kept as-is so a finding is traceable back "
                "to the tool's own catalog."
            ),
            "type": "string",
            "maxLength": 256,
        },
        "severity": {
            "description": (
                "The tool's native severity mapped onto ZTIE's normalized ladder. "
                "This is a normalized EVIDENCE severity, NOT a verdict."
            ),
            "type": "string",
            "enum": SEVERITIES,
        },
        "check_family": {
            "description": (
                "The kind of check that produced this finding, so Phase 3 can "
                "group IaC-lint / policy-as-code / IaC-misconfig / SAST evidence."
            ),
            "type": "string",
            "enum": CHECK_FAMILIES,
        },
        "message": {
            "description": (
                "Human-readable description of the finding, bounded. Derived, inert "
                "text for triage — never raw executable content."
            ),
            "type": "string",
            "maxLength": 2048,
        },
        "location": {
            "description": (
                "Where in the artifact the finding is, when the tool reports it. "
                "file is the in-artifact filename; line spans are 1-based."
            ),
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "file": {"type": "string", "maxLength": 1024},
                "start_line": {"type": "integer", "minimum": 0},
                "end_line": {"type": "integer", "minimum": 0},
                "resource": {
                    "description": (
                        "The logical resource / construct the finding is about "
                        "(e.g. a CloudFormation logical id), when applicable."
                    ),
                    "type": "string",
                    "maxLength": 512,
                },
            },
        },
        "guideline": {
            "description": (
                "Optional bounded pointer to the rule's remediation guidance / "
                "docs URL, when the tool provides one. Inert text."
            ),
            "type": "string",
            "maxLength": 1024,
        },
        "compliance": _COMPLIANCE,
    },
}

_TOOL_RUN = {
    "type": "object",
    "additionalProperties": False,
    "required": ["tool", "status"],
    "properties": {
        "tool": {"type": "string", "enum": TOOLS},
        "status": {
            "description": (
                "Whether the tool ran to completion. 'ok' = ran and produced "
                "findings (possibly zero); 'error' = the tool failed (crash, "
                "timeout, unparsable output). An 'error' does NOT crash the lane — "
                "it is recorded here and the other tools still run (production "
                "resilience, DoD: 'does not crash on a scanner error')."
            ),
            "type": "string",
            "enum": ["ok", "error"],
        },
        "finding_count": {"type": "integer", "minimum": 0},
        "error_reason": {
            "description": (
                "Bounded reason when status=error (e.g. 'exit 2', 'timeout', "
                "'unparsable json'). Inert diagnostic text."
            ),
            "type": "string",
            "maxLength": 512,
        },
        "duration_ms": {"type": "integer", "minimum": 0},
    },
}

SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "$id": "https://ztie.internal/schemas/static-findings.contract.v1.json",
    "title": "ZTIE normalized static-findings document (v1.2)",
    "description": (
        "The DERIVED, normalized static-analysis findings document produced by the "
        "Story 2.1 static lane (+ the Story 2.2 signature engine + the Story 2.2G "
        "gitleaks secret scanner) for one intake artifact. ONE shape across all "
        "tools (cfn-lint, cfn-guard, checkov, bandit, gitleaks, signature-scan) so "
        "Phase 3 correlation consumes a single format. v1.1 (Story 2.2) additively "
        "added the 'signature-scan' tool + 'signature' check_family + an OPTIONAL "
        "per-finding 'compliance' sub-object. v1.2 (Story 2.2G) additively adds the "
        "'gitleaks' tool to the enum (the SOLE secret scanner; it supersedes the "
        "2.2 embedded SECRET regex rules — gitleaks findings reuse the 'signature' "
        "check_family). NON-EXECUTING: static evidence only, no runtime field. "
        "EVIDENCE, NEVER A VERDICT: no verdict/safe/approved/forward field; a "
        "compliance mapping says a finding implicates a control, never that the "
        "artifact fails. This document STAYS IN FORENSIC (RD-009 — it may echo "
        "artifact content); it is written to the Forensic artifact S3 bucket under "
        "findings/ and does NOT cross to the Hub. Only a bounded derived summary "
        "crosses the RD-013 gate (static-scan-summary.contract.v1), pointing back "
        "here. Allow-list: additionalProperties false at every level; arrays + "
        "strings bounded so a hostile artifact cannot produce an unbounded document."
    ),
    "type": "object",
    "additionalProperties": False,
    "required": [
        "contract_version",
        "intake_id",
        "sha256",
        "artifact_class",
        "scanned_at",
        "non_executing",
        "tools",
        "findings",
    ],
    "properties": {
        "contract_version": {
            "description": (
                "Findings-document schema version. '1.2' (Story 2.2G) is the "
                "current emitted version; '1.0' (Story 2.1) and '1.1' (Story 2.2) "
                "documents remain valid to read."
            ),
            "type": "string",
            "enum": ["1.0", "1.1", "1.2"],
        },
        "intake_id": {
            "description": "The intake UUIDv4 this findings document is for.",
            "type": "string",
            "pattern": (
                "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-"
                "[0-9a-f]{12}$"
            ),
        },
        "sha256": {
            "description": (
                "Lowercase hex SHA-256 of the raw artifact body the scan ran over. "
                "Integrity key bound to intake_id."
            ),
            "type": "string",
            "pattern": "^[0-9a-f]{64}$",
        },
        "artifact_class": {
            "description": "The class label the scan-tool selection was based on.",
            "type": "string",
            "enum": ARTIFACT_CLASSES,
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
        "non_executing": {
            "description": (
                "Always true. The static lane INSPECTS the artifact; it NEVER "
                "executes it (RD-001 — execution is the dynamic lane, 2.3)."
            ),
            "type": "boolean",
            "const": True,
        },
        "tools": {
            "description": (
                "Per-tool run record: which tools ran, whether each succeeded, and "
                "how many findings it produced. A tool 'error' is recorded here and "
                "does not crash the lane."
            ),
            "type": "array",
            "minItems": 1,
            "maxItems": len(TOOLS),
            "items": _TOOL_RUN,
        },
        "findings": {
            "description": (
                "The normalized findings, one shape across all tools. Bounded so a "
                "hostile artifact cannot produce an unbounded document; when a tool "
                "produces more than the cap, the excess is dropped and the "
                "truncated flag is set (the count in tools[] / the summary remains "
                "the true pre-truncation count)."
            ),
            "type": "array",
            "maxItems": 5000,
            "items": _FINDING,
        },
        "truncated": {
            "description": (
                "True iff the findings array was capped (more findings existed than "
                "the maxItems bound). The per-tool + summary counts remain true."
            ),
            "type": "boolean",
        },
    },
}


# Repo-root-relative output paths (canonical schema + every bundled lambda
# copy that must stay byte-in-sync). Consumed by scripts/gen_contracts.py.
OUT_PATHS = [
    ("schemas", "static-findings.contract.v1.json"),
    ("lambdas", "static_scan", "static-findings.contract.v1.json"),
]


def main() -> None:
    from contract_writer import resolve_out_paths, write_contract

    write_contract(SCHEMA, resolve_out_paths(OUT_PATHS))


if __name__ == "__main__":
    main()
