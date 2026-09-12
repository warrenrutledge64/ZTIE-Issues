"""ZTIE Story 2.6 — offline unit tests for the PURE join logic (collect.py).

Stdlib ``unittest`` only — NO boto3 / moto / jsonschema imports (they are not
installable in the INTEGRATIONS_ONLY sandbox, and the pure join path must not need
them). These tests exercise the load-bearing 2.6 invariants:

  * both lanes complete  -> both present, both_complete True, no verdict key
  * one lane errored     -> that lane recorded 'errored', OTHER lane's roll-up
                            preserved, both_complete False (never a hang/drop)
  * lane not routed       -> 'not_applicable'
  * EVIDENCE never a verdict — a recursive no-verdict-key scan over produced records
"""

from __future__ import annotations

import unittest

import collect

_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_SHA256 = "a" * 64
_CV = "1.0"

# Fields that must NEVER appear anywhere in a crossed collected record (it is
# EVIDENCE, not a verdict). Checked recursively.
_BANNED_VERDICT_KEYS = frozenset(
    {"verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean"}
)


def _static_summary(severity="high", total=3):
    """A representative static-scan-summary branch result (2.1/2.2 shape)."""
    return {
        "contract_version": "1.1",
        "intake_id": _INTAKE_ID,
        "sha256": _SHA256,
        "scanned_at": "2026-09-06T00:00:00Z",
        "scan": {
            "lane": "static_analysis",
            "highest_severity": severity,
            "total_findings": total,
            "findings_s3_bucket": "ztie-forensic-artifacts",
            "findings_s3_key": f"findings/{_INTAKE_ID}/static-findings.json",
        },
    }


def _dynamic_run(outcome="completed"):
    """A representative dynamic-run branch result (2.3 shape)."""
    return {
        "contract_version": "1.0",
        "intake_id": _INTAKE_ID,
        "sha256": _SHA256,
        "detonated_at": "2026-09-06T00:04:31Z",
        "run": {
            "lane": "dynamic_detonation",
            "outcome": outcome,
            "execution": {
                "mechanism": "ssm_send_command",
                "ssm_status": "Success",
                "output_s3_bucket": "ztie-forensic-artifacts",
                "output_s3_key": f"runs/{_INTAKE_ID}/detonation-output.json",
            },
        },
    }


def _errored_branch(reason="boom"):
    """A branch Catch result — a lane that errored (per-branch Catch fired)."""
    return {"error": "States.TaskFailed", "Cause": reason}


def _no_banned_keys(obj, path="") -> str | None:
    """Recursively assert no verdict-shaped key appears. Returns the offending key
    path or None."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in _BANNED_VERDICT_KEYS:
                return f"{path}.{k}" if path else k
            deeper = _no_banned_keys(v, f"{path}.{k}" if path else k)
            if deeper:
                return deeper
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            deeper = _no_banned_keys(v, f"{path}[{i}]")
            if deeper:
                return deeper
    return None


class TestBothLanesComplete(unittest.TestCase):
    def setUp(self):
        self.env = collect.join(
            intake_id=_INTAKE_ID,
            sha256=_SHA256,
            joined_at="2026-09-06T00:05:00Z",
            lanes_expected=["static_analysis", "dynamic_detonation"],
            static_result=_static_summary(),
            dynamic_result=_dynamic_run(),
            contract_version=_CV,
        )

    def test_top_level_shape(self):
        for key in ("contract_version", "intake_id", "sha256", "joined_at", "collected"):
            self.assertIn(key, self.env)
        self.assertEqual(self.env["contract_version"], _CV)
        self.assertEqual(self.env["intake_id"], _INTAKE_ID)
        self.assertEqual(self.env["sha256"], _SHA256)

    def test_both_present_and_complete(self):
        c = self.env["collected"]
        self.assertEqual(c["static"]["lane_status"], "completed")
        self.assertEqual(c["dynamic"]["lane_status"], "completed")
        self.assertEqual(
            sorted(c["lanes_collected"]),
            ["dynamic_detonation", "static_analysis"],
        )
        self.assertTrue(c["both_complete"])

    def test_rollups_by_reference(self):
        c = self.env["collected"]
        self.assertEqual(c["static"]["highest_severity"], "high")
        self.assertEqual(c["static"]["total_findings"], 3)
        self.assertEqual(c["static"]["findings_s3_key"], f"findings/{_INTAKE_ID}/static-findings.json")
        self.assertEqual(c["dynamic"]["outcome"], "completed")
        self.assertEqual(c["dynamic"]["run_log_s3_key"], f"runs/{_INTAKE_ID}/detonation-output.json")

    def test_no_verdict_key_anywhere(self):
        self.assertIsNone(_no_banned_keys(self.env))


class TestOneLaneErrored(unittest.TestCase):
    def test_dynamic_errored_static_preserved(self):
        env = collect.join(
            intake_id=_INTAKE_ID,
            sha256=_SHA256,
            joined_at="2026-09-06T00:05:00Z",
            lanes_expected=["static_analysis", "dynamic_detonation"],
            static_result=_static_summary(severity="medium", total=1),
            dynamic_result=_errored_branch("RunInstances failed: capacity"),
            contract_version=_CV,
        )
        c = env["collected"]
        # The errored lane is RECORDED, not dropped.
        self.assertEqual(c["dynamic"]["lane_status"], "errored")
        self.assertIn("error_reason", c["dynamic"])
        self.assertNotIn("outcome", c["dynamic"])
        # The OTHER lane's roll-up is preserved.
        self.assertEqual(c["static"]["lane_status"], "completed")
        self.assertEqual(c["static"]["highest_severity"], "medium")
        # both_complete is False (a lane did not complete) but the record is valid.
        self.assertFalse(c["both_complete"])
        # Both lanes were still COLLECTED (errored counts as collected, not a gap).
        self.assertEqual(
            sorted(c["lanes_collected"]),
            ["dynamic_detonation", "static_analysis"],
        )
        self.assertIsNone(_no_banned_keys(env))

    def test_static_errored_dynamic_preserved(self):
        env = collect.join(
            intake_id=_INTAKE_ID,
            sha256=_SHA256,
            joined_at="2026-09-06T00:05:00Z",
            lanes_expected=["static_analysis", "dynamic_detonation"],
            static_result=_errored_branch("checkov crashed"),
            dynamic_result=_dynamic_run(outcome="execution_error"),
            contract_version=_CV,
        )
        c = env["collected"]
        self.assertEqual(c["static"]["lane_status"], "errored")
        self.assertIn("error_reason", c["static"])
        self.assertEqual(c["dynamic"]["lane_status"], "completed")
        self.assertEqual(c["dynamic"]["outcome"], "execution_error")
        self.assertFalse(c["both_complete"])
        self.assertIsNone(_no_banned_keys(env))

    def test_absent_branch_recorded_as_errored(self):
        # A branch that reported nothing at all (None) is recorded, never dropped.
        env = collect.join(
            intake_id=_INTAKE_ID,
            sha256=_SHA256,
            joined_at="2026-09-06T00:05:00Z",
            lanes_expected=["static_analysis", "dynamic_detonation"],
            static_result=_static_summary(),
            dynamic_result=None,
            contract_version=_CV,
        )
        c = env["collected"]
        self.assertEqual(c["dynamic"]["lane_status"], "errored")
        self.assertEqual(c["static"]["lane_status"], "completed")
        self.assertFalse(c["both_complete"])


class TestLaneNotApplicable(unittest.TestCase):
    def test_dynamic_not_routed_is_not_applicable(self):
        # routing named only the static lane (e.g. an iac_template).
        env = collect.join(
            intake_id=_INTAKE_ID,
            sha256=_SHA256,
            joined_at="2026-09-06T00:05:00Z",
            lanes_expected=["static_analysis"],
            static_result=_static_summary(severity="none", total=0),
            dynamic_result=None,
            contract_version=_CV,
        )
        c = env["collected"]
        self.assertEqual(c["dynamic"]["lane_status"], "not_applicable")
        self.assertNotIn("outcome", c["dynamic"])
        self.assertNotIn("error_reason", c["dynamic"])
        self.assertEqual(c["static"]["lane_status"], "completed")
        # not_applicable lanes are NOT counted as collected.
        self.assertEqual(c["lanes_collected"], ["static_analysis"])
        # Only the static lane was expected and it completed -> both_complete True.
        self.assertTrue(c["both_complete"])
        self.assertEqual(c["lanes_expected"], ["static_analysis"])
        self.assertIsNone(_no_banned_keys(env))

    def test_static_not_routed_is_not_applicable(self):
        env = collect.join(
            intake_id=_INTAKE_ID,
            sha256=_SHA256,
            joined_at="2026-09-06T00:05:00Z",
            lanes_expected=["dynamic_detonation"],
            static_result=None,
            dynamic_result=_dynamic_run(),
            contract_version=_CV,
        )
        c = env["collected"]
        self.assertEqual(c["static"]["lane_status"], "not_applicable")
        self.assertEqual(c["dynamic"]["lane_status"], "completed")
        self.assertEqual(c["lanes_collected"], ["dynamic_detonation"])
        self.assertTrue(c["both_complete"])


class TestBounds(unittest.TestCase):
    def test_error_reason_clipped(self):
        env = collect.join(
            intake_id=_INTAKE_ID,
            sha256=_SHA256,
            joined_at="2026-09-06T00:05:00Z",
            lanes_expected=["dynamic_detonation"],
            dynamic_result=_errored_branch("x" * 5000),
            contract_version=_CV,
        )
        self.assertLessEqual(len(env["collected"]["dynamic"]["error_reason"]), 512)

    def test_join_note_clipped(self):
        env = collect.join(
            intake_id=_INTAKE_ID,
            sha256=_SHA256,
            joined_at="2026-09-06T00:05:00Z",
            lanes_expected=["static_analysis"],
            static_result=_static_summary(),
            join_note="n" * 5000,
            contract_version=_CV,
        )
        self.assertLessEqual(len(env["collected"]["join_note"]), 512)

    def test_out_of_enum_severity_dropped(self):
        # A branch reporting a garbage severity must not leak it into the record.
        bad = _static_summary()
        bad["scan"]["highest_severity"] = "catastrophic"
        env = collect.join(
            intake_id=_INTAKE_ID,
            sha256=_SHA256,
            joined_at="2026-09-06T00:05:00Z",
            lanes_expected=["static_analysis"],
            static_result=bad,
            contract_version=_CV,
        )
        self.assertNotIn("highest_severity", env["collected"]["static"])


if __name__ == "__main__":
    unittest.main()
