"""ZTIE Story 2.3 — contract-conformance for the dynamic-run outcome envelope.

TWO layers, so the loop between the schema-first contract and the code is closed
both live AND offline:

  * LIVE (pytest, jsonschema installed): every envelope ``outcome.py`` builds must
    validate against ``dynamic-run.contract.v1.json`` (the exact allow-list the Hub
    validator enforces). Skips in the INTEGRATIONS_ONLY sandbox (PyPI blocked).

  * OFFLINE (always, stdlib only): a MANUAL pure-Python conformance walk that
    asserts the built envelopes satisfy the contract's load-bearing invariants
    (required keys, allow-listed enums, byte bounds, NO verdict field, the
    always-contained facts) even when jsonschema is not installable. This is the
    2.2 lesson — prove conformance offline, not only under a live validator.
"""

from __future__ import annotations

import json
import os
import unittest

import outcome as oc

try:
    from jsonschema import Draft7Validator

    _HAVE_JSONSCHEMA = True
except ImportError:  # offline sandbox
    _HAVE_JSONSCHEMA = False

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "dynamic-run.contract.v1.json")

_VALID_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_VALID_SHA256 = "a" * 64
_LT = "lt-045ddce7fdac386db"

# Fields that must NEVER appear anywhere in a crossed outcome (it is EVIDENCE, not a
# verdict). Checked recursively by the offline walk.
_BANNED_VERDICT_KEYS = frozenset(
    {"verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean"}
)


def _completed_envelope() -> dict:
    run = oc.build_run(
        artifact_class="raw_script",
        outcome=oc.OUTCOME_COMPLETED,
        launch_template_id=_LT,
        launched_from_template=True,
        instance_id="i-0abc",
        launch_template_version="$Latest",
        instance_type="t3.small",
        started_at="2026-09-04T00:00:00Z",
        duration_ms=42000,
        execution=oc.build_execution(
            ssm_status="Success",
            ssm_command_id="cmd-1",
            exit_code=0,
            stdout="=== ZTIE detonation: begin ===\nhello\n=== ZTIE detonation: end rc=0 ===",
            output_s3_bucket="ztie-forensic-artifacts",
            output_s3_key="runs/x/detonation-output.json",
        ),
        teardown=oc.build_teardown(
            hard_ttl_minutes=5,
            teardown_observed=True,
            terminated_at="2026-09-04T00:04:30Z",
            teardown_note="observed shutting-down",
        ),
    )
    return oc.build_run_envelope(
        intake_id=_VALID_INTAKE_ID,
        sha256=_VALID_SHA256,
        detonated_at="2026-09-04T00:04:31Z",
        run=run,
        contract_version="1.0",
    )


def _launch_error_envelope() -> dict:
    run = oc.build_launch_error_run(
        artifact_class="iac_template",
        launch_template_id=_LT,
        hard_ttl_minutes=5,
        error_reason="RunInstances failed: InsufficientInstanceCapacity",
    )
    return oc.build_run_envelope(
        intake_id=_VALID_INTAKE_ID,
        sha256=_VALID_SHA256,
        detonated_at="2026-09-04T00:00:05Z",
        run=run,
        contract_version="1.0",
    )


def _execution_error_envelope() -> dict:
    run = oc.build_run(
        artifact_class="raw_script",
        outcome=oc.OUTCOME_EXECUTION_ERROR,
        launch_template_id=_LT,
        launched_from_template=True,
        instance_id="i-0def",
        execution=oc.build_execution(
            ssm_status="Failed", ssm_command_id="cmd-2", exit_code=1, stderr="boom"
        ),
        teardown=oc.build_teardown(hard_ttl_minutes=5, teardown_observed=False,
                                   teardown_note="teardown not observed; hard TTL is the backstop"),
        error_reason="artifact exited non-zero",
    )
    return oc.build_run_envelope(
        intake_id=_VALID_INTAKE_ID,
        sha256=_VALID_SHA256,
        detonated_at="2026-09-04T00:02:00Z",
        run=run,
        contract_version="1.0",
    )


def _all_sample_envelopes() -> list[dict]:
    return [_completed_envelope(), _launch_error_envelope(), _execution_error_envelope()]


def _no_banned_keys(obj) -> str | None:
    """Recursively assert no verdict-shaped key appears. Returns the offending key
    path or None."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in _BANNED_VERDICT_KEYS:
                return k
            deeper = _no_banned_keys(v)
            if deeper:
                return f"{k}.{deeper}"
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            deeper = _no_banned_keys(v)
            if deeper:
                return f"[{i}].{deeper}"
    return None


class TestOfflineConformanceWalk(unittest.TestCase):
    """Pure-Python manual conformance — runs even without jsonschema."""

    def test_top_level_required_keys(self):
        for env in _all_sample_envelopes():
            for key in ("contract_version", "intake_id", "sha256", "detonated_at", "run"):
                self.assertIn(key, env)
            self.assertEqual(env["contract_version"], "1.0")
            self.assertEqual(env["intake_id"], _VALID_INTAKE_ID)
            self.assertEqual(env["sha256"], _VALID_SHA256)

    def test_run_required_keys_and_enums(self):
        for env in _all_sample_envelopes():
            run = env["run"]
            for key in (
                "lane",
                "artifact_class",
                "outcome",
                "launched_from_template",
                "launch_template_id",
                "containment",
                "execution",
                "teardown",
            ):
                self.assertIn(key, run)
            self.assertEqual(run["lane"], "dynamic_detonation")
            self.assertIn(run["outcome"], oc.OUTCOMES)
            self.assertIn(run["artifact_class"], ("iac_template", "raw_script", "other_unknown"))

    def test_containment_always_contained(self):
        for env in _all_sample_envelopes():
            c = env["run"]["containment"]
            self.assertTrue(c["host_native"])
            self.assertTrue(c["no_docker"])
            self.assertTrue(c["isolated_subnet"])
            self.assertFalse(c["public_ip"])
            self.assertTrue(c["imdsv2_required"])

    def test_execution_bounds(self):
        for env in _all_sample_envelopes():
            e = env["run"]["execution"]
            self.assertEqual(e["mechanism"], "ssm_send_command")
            self.assertIn(e["ssm_status"], oc.SSM_STATUSES)
            if "stdout_tail" in e:
                self.assertLessEqual(len(e["stdout_tail"].encode("utf-8")), oc.MAX_OUTPUT_TAIL)
            if "stderr_tail" in e:
                self.assertLessEqual(len(e["stderr_tail"].encode("utf-8")), oc.MAX_OUTPUT_TAIL)

    def test_teardown_bounds(self):
        for env in _all_sample_envelopes():
            t = env["run"]["teardown"]
            self.assertTrue(1 <= t["hard_ttl_minutes"] <= 60)
            self.assertIn(t["shutdown_behavior"], ("terminate", "stop"))
            self.assertIsInstance(t["teardown_observed"], bool)

    def test_no_verdict_field_anywhere(self):
        for env in _all_sample_envelopes():
            offending = _no_banned_keys(env)
            self.assertIsNone(offending, f"verdict-shaped key present: {offending}")

    def test_schema_itself_has_no_verdict_field(self):
        # The schema must have NO slot for a verdict at all (belt-and-suspenders on
        # top of the built-envelope check).
        with open(_SCHEMA_PATH, encoding="utf-8") as fh:
            schema_text = fh.read().lower()
        # These words may appear in prose descriptions ("never a verdict"), so we
        # check they are not PROPERTY KEYS by loading + walking the schema props.
        schema = json.loads(schema_text)
        self._assert_no_banned_property(schema)

    def _assert_no_banned_property(self, node):
        if isinstance(node, dict):
            props = node.get("properties")
            if isinstance(props, dict):
                for pk in props:
                    self.assertNotIn(
                        pk, _BANNED_VERDICT_KEYS, f"schema defines a verdict property {pk!r}"
                    )
            for v in node.values():
                self._assert_no_banned_property(v)
        elif isinstance(node, list):
            for v in node:
                self._assert_no_banned_property(v)


@unittest.skipUnless(_HAVE_JSONSCHEMA, "jsonschema not available offline")
class TestLiveContractConformance(unittest.TestCase):
    """Live jsonschema validation against the exact contract the Hub enforces."""

    def setUp(self):
        with open(_SCHEMA_PATH, encoding="utf-8") as fh:
            self.validator = Draft7Validator(json.load(fh))

    def _assert_conforms(self, env):
        errors = sorted(self.validator.iter_errors(env), key=str)
        self.assertEqual(errors, [], f"schema errors: {errors}")

    def test_completed_conforms(self):
        self._assert_conforms(_completed_envelope())

    def test_launch_error_conforms(self):
        self._assert_conforms(_launch_error_envelope())

    def test_execution_error_conforms(self):
        self._assert_conforms(_execution_error_envelope())

    def test_rejects_added_unknown_field(self):
        env = _completed_envelope()
        env["run"]["verdict"] = "safe"  # additionalProperties:false must reject
        errors = list(self.validator.iter_errors(env))
        self.assertTrue(errors, "schema must reject an injected verdict field")

    def test_rejects_bad_outcome(self):
        env = _completed_envelope()
        env["run"]["outcome"] = "approved"
        errors = list(self.validator.iter_errors(env))
        self.assertTrue(errors, "schema must reject an out-of-enum outcome")


if __name__ == "__main__":
    unittest.main()
