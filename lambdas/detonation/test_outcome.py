"""ZTIE Story 2.3 — offline unit tests for the PURE run-outcome builders.

Pure stdlib ``unittest`` — runs in the INTEGRATIONS_ONLY sandbox (no boto3 /
jsonschema / pytest / moto needed). Proves the bounded, verdict-free, contained
shape of everything ``outcome.py`` assembles.
"""

from __future__ import annotations

import unittest

import outcome as oc

_VALID_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_VALID_SHA256 = "a" * 64
_LT = "lt-045ddce7fdac386db"


class TestTailBytes(unittest.TestCase):
    def test_empty_and_none(self):
        self.assertEqual(oc.tail_bytes(None), ("", False))
        self.assertEqual(oc.tail_bytes(""), ("", False))
        self.assertEqual(oc.tail_bytes(b""), ("", False))

    def test_under_cap_not_truncated(self):
        text, trunc = oc.tail_bytes("hello", max_bytes=64)
        self.assertEqual(text, "hello")
        self.assertFalse(trunc)

    def test_over_cap_keeps_tail_and_flags(self):
        big = "x" * 100 + "TAIL"
        text, trunc = oc.tail_bytes(big, max_bytes=8)
        self.assertTrue(trunc)
        self.assertEqual(len(text.encode("utf-8")), 8)
        # The most-recent bytes are preserved (tail, not head).
        self.assertTrue(text.endswith("TAIL"))

    def test_multibyte_safe_decode(self):
        # A cut through a multibyte char must not raise (errors=replace).
        text, trunc = oc.tail_bytes("é" * 50, max_bytes=5)
        self.assertTrue(trunc)
        self.assertIsInstance(text, str)

    def test_bytes_input(self):
        text, trunc = oc.tail_bytes(b"abcdef", max_bytes=3)
        self.assertEqual(text, "def")
        self.assertTrue(trunc)


class TestContainment(unittest.TestCase):
    def test_containment_is_always_contained(self):
        c = oc.build_containment()
        self.assertTrue(c["host_native"])
        self.assertTrue(c["no_docker"])
        self.assertTrue(c["isolated_subnet"])
        self.assertFalse(c["public_ip"])
        self.assertTrue(c["imdsv2_required"])


class TestExecution(unittest.TestCase):
    def test_minimal_execution(self):
        e = oc.build_execution(ssm_status="Success")
        self.assertEqual(e["mechanism"], "ssm_send_command")
        self.assertEqual(e["ssm_status"], "Success")
        # No tails / pointer when not supplied.
        self.assertNotIn("stdout_tail", e)
        self.assertNotIn("output_truncated", e)

    def test_bad_ssm_status_raises(self):
        with self.assertRaises(ValueError):
            oc.build_execution(ssm_status="Bogus")

    def test_exit_code_clamped(self):
        self.assertEqual(oc.build_execution(ssm_status="Failed", exit_code=999)["exit_code"], 255)
        self.assertEqual(oc.build_execution(ssm_status="Failed", exit_code=-5)["exit_code"], -1)

    def test_tails_capped_and_flagged(self):
        big = "z" * (oc.MAX_OUTPUT_TAIL + 500)
        e = oc.build_execution(ssm_status="Success", stdout=big)
        self.assertLessEqual(len(e["stdout_tail"].encode("utf-8")), oc.MAX_OUTPUT_TAIL)
        self.assertTrue(e["output_truncated"])

    def test_pointer_fields(self):
        e = oc.build_execution(
            ssm_status="Success",
            ssm_command_id="cmd-1",
            output_s3_bucket="b",
            output_s3_key="runs/x/detonation-output.json",
        )
        self.assertEqual(e["output_s3_bucket"], "b")
        self.assertEqual(e["output_s3_key"], "runs/x/detonation-output.json")

    def test_no_verdict_field_anywhere(self):
        e = oc.build_execution(ssm_status="Failed", exit_code=1, stdout="bad", stderr="oops")
        for banned in ("verdict", "safe", "approved", "forward", "malicious", "pass_fail"):
            self.assertNotIn(banned, e)


class TestTeardown(unittest.TestCase):
    def test_ttl_clamped(self):
        self.assertEqual(oc.build_teardown(hard_ttl_minutes=0, teardown_observed=False)["hard_ttl_minutes"], 1)
        self.assertEqual(oc.build_teardown(hard_ttl_minutes=999, teardown_observed=False)["hard_ttl_minutes"], 60)

    def test_bad_shutdown_behavior_raises(self):
        with self.assertRaises(ValueError):
            oc.build_teardown(hard_ttl_minutes=5, teardown_observed=True, shutdown_behavior="halt")

    def test_observed_teardown(self):
        t = oc.build_teardown(
            hard_ttl_minutes=5,
            teardown_observed=True,
            terminated_at="2026-09-04T00:00:00Z",
            teardown_note="observed terminated",
        )
        self.assertTrue(t["teardown_observed"])
        self.assertEqual(t["terminated_at"], "2026-09-04T00:00:00Z")


class TestOutcomeFromSsmStatus(unittest.TestCase):
    def test_mappings(self):
        self.assertEqual(oc.outcome_from_ssm_status("Success"), oc.OUTCOME_COMPLETED)
        self.assertEqual(oc.outcome_from_ssm_status("Failed"), oc.OUTCOME_EXECUTION_ERROR)
        self.assertEqual(oc.outcome_from_ssm_status("Terminated"), oc.OUTCOME_EXECUTION_ERROR)
        self.assertEqual(oc.outcome_from_ssm_status("TimedOut"), oc.OUTCOME_TIMED_OUT)
        self.assertEqual(oc.outcome_from_ssm_status("Undelivered"), oc.OUTCOME_DELIVERY_ERROR)
        # non-terminal -> timed_out (we stopped polling before terminal)
        self.assertEqual(oc.outcome_from_ssm_status("InProgress"), oc.OUTCOME_TIMED_OUT)
        self.assertEqual(oc.outcome_from_ssm_status("not_run"), oc.OUTCOME_TIMED_OUT)


class TestBuildRun(unittest.TestCase):
    def _run(self, outcome=oc.OUTCOME_COMPLETED):
        return oc.build_run(
            artifact_class="raw_script",
            outcome=outcome,
            launch_template_id=_LT,
            launched_from_template=True,
            instance_id="i-abc",
            execution=oc.build_execution(ssm_status="Success", exit_code=0),
            teardown=oc.build_teardown(hard_ttl_minutes=5, teardown_observed=True),
        )

    def test_run_shape(self):
        run = self._run()
        self.assertEqual(run["lane"], "dynamic_detonation")
        self.assertEqual(run["outcome"], oc.OUTCOME_COMPLETED)
        self.assertTrue(run["launched_from_template"])
        self.assertEqual(run["launch_template_id"], _LT)
        self.assertIn("containment", run)
        self.assertIn("execution", run)
        self.assertIn("teardown", run)

    def test_bad_outcome_raises(self):
        with self.assertRaises(ValueError):
            self._run(outcome="approved")  # not an allowed outcome

    def test_no_verdict_field_in_run(self):
        run = self._run()
        for banned in ("verdict", "safe", "approved", "forward", "malicious"):
            self.assertNotIn(banned, run)

    def test_duration_clamped(self):
        run = oc.build_run(
            artifact_class="iac_template",
            outcome=oc.OUTCOME_COMPLETED,
            launch_template_id=_LT,
            launched_from_template=True,
            execution=oc.build_execution(ssm_status="Success"),
            teardown=oc.build_teardown(hard_ttl_minutes=5, teardown_observed=False),
            duration_ms=10**12,
        )
        self.assertLessEqual(run["duration_ms"], 86400000)


class TestBuildRunEnvelope(unittest.TestCase):
    def test_envelope_integrity_keyed(self):
        run = oc.build_run(
            artifact_class="raw_script",
            outcome=oc.OUTCOME_COMPLETED,
            launch_template_id=_LT,
            launched_from_template=True,
            execution=oc.build_execution(ssm_status="Success"),
            teardown=oc.build_teardown(hard_ttl_minutes=5, teardown_observed=True),
        )
        env = oc.build_run_envelope(
            intake_id=_VALID_INTAKE_ID,
            sha256=_VALID_SHA256,
            detonated_at="2026-09-04T00:00:00Z",
            run=run,
            contract_version="1.0",
        )
        self.assertEqual(env["intake_id"], _VALID_INTAKE_ID)
        self.assertEqual(env["sha256"], _VALID_SHA256)
        self.assertEqual(env["contract_version"], "1.0")
        self.assertIn("run", env)
        # The discriminator key the Hub gate routes on.
        self.assertTrue("run" in env)


class TestLaunchErrorRun(unittest.TestCase):
    def test_launch_error_is_bounded_evidence(self):
        run = oc.build_launch_error_run(
            artifact_class="raw_script",
            launch_template_id=_LT,
            hard_ttl_minutes=5,
            error_reason="RunInstances failed: InsufficientInstanceCapacity",
        )
        self.assertEqual(run["outcome"], oc.OUTCOME_LAUNCH_ERROR)
        self.assertFalse(run["launched_from_template"])
        self.assertEqual(run["execution"]["ssm_status"], "not_run")
        self.assertFalse(run["teardown"]["teardown_observed"])
        self.assertIn("error_reason", run)
        self.assertNotIn("instance_id", run)


if __name__ == "__main__":
    unittest.main()
