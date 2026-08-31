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

import normalize
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
    def test_iac_template_runs_three_iac_tools(self):
        self.assertEqual(
            toolplan.tools_for_class("iac_template"),
            ["cfn-lint", "cfn-guard", "checkov"],
        )

    def test_raw_script_runs_bandit_and_checkov(self):
        self.assertEqual(
            toolplan.tools_for_class("raw_script"), ["bandit", "checkov"]
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


class TestNeverRaises(unittest.TestCase):
    """A tool that produced garbage / empty / non-JSON output must not crash."""

    def test_empty_and_none(self):
        for tool in ("cfn-lint", "bandit", "checkov", "cfn-guard"):
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
        doc = normalize.build_findings_document(
            intake_id=_VALID_INTAKE_ID,
            sha256=_VALID_SHA,
            artifact_class="iac_template",
            scanned_at=_NOW,
            tool_runs=[normalize.build_tool_run("cfn-lint", status="ok", finding_count=len(findings))],
            findings=findings,
        )
        errors = list(self._validator("static-findings.contract.v1.json").iter_errors(doc))
        self.assertEqual(errors, [], msg=[e.message for e in errors])


if __name__ == "__main__":
    unittest.main()
