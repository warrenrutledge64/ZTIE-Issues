"""ZTIE Story 2.6 — contract-conformance for the collected-record (join) envelope.

TWO layers, so the loop between the schema-first contract and the code is closed
both live AND offline:

  * LIVE (pytest, jsonschema installed): every envelope ``collect.py`` builds must
    validate against ``collected.contract.v1.json`` (the exact allow-list the Hub
    validator enforces). Skips in the INTEGRATIONS_ONLY sandbox (PyPI blocked).

  * OFFLINE (always, stdlib only): a MANUAL pure-Python conformance walk that
    asserts the built envelopes satisfy the contract's load-bearing invariants
    (required keys, allow-listed enums, additionalProperties allow-list at every
    level, byte/length bounds, NO verdict field) even when jsonschema is not
    installable. This is the 2.2/2.3 lesson — prove conformance offline, not only
    under a live validator; plus a schema-has-no-verdict-property check.
"""

from __future__ import annotations

import json
import os
import unittest

import collect

try:
    from jsonschema import Draft7Validator

    _HAVE_JSONSCHEMA = True
except ImportError:  # offline sandbox
    _HAVE_JSONSCHEMA = False

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "collected.contract.v1.json")

_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_SHA256 = "a" * 64

_BANNED_VERDICT_KEYS = frozenset(
    {"verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean"}
)


def _both_complete_envelope():
    return collect.join(
        intake_id=_INTAKE_ID,
        sha256=_SHA256,
        joined_at="2026-09-06T00:05:00Z",
        lanes_expected=["static_analysis", "dynamic_detonation"],
        static_result={
            "contract_version": "1.1",
            "scan": {
                "lane": "static_analysis",
                "highest_severity": "high",
                "total_findings": 3,
                "findings_s3_bucket": "ztie-forensic-artifacts",
                "findings_s3_key": f"findings/{_INTAKE_ID}/static-findings.json",
            },
        },
        dynamic_result={
            "contract_version": "1.0",
            "run": {
                "lane": "dynamic_detonation",
                "outcome": "completed",
                "execution": {
                    "output_s3_bucket": "ztie-forensic-artifacts",
                    "output_s3_key": f"runs/{_INTAKE_ID}/detonation-output.json",
                },
            },
        },
        contract_version="1.0",
    )


def _one_errored_envelope():
    return collect.join(
        intake_id=_INTAKE_ID,
        sha256=_SHA256,
        joined_at="2026-09-06T00:05:00Z",
        lanes_expected=["static_analysis", "dynamic_detonation"],
        static_result={"scan": {"lane": "static_analysis", "highest_severity": "none", "total_findings": 0}},
        dynamic_result={"error": "States.TaskFailed", "Cause": "capacity"},
        contract_version="1.0",
        join_note="dynamic lane errored; recorded",
    )


def _not_applicable_envelope():
    return collect.join(
        intake_id=_INTAKE_ID,
        sha256=_SHA256,
        joined_at="2026-09-06T00:05:00Z",
        lanes_expected=["static_analysis"],
        static_result={"scan": {"lane": "static_analysis", "highest_severity": "low"}},
        dynamic_result=None,
        contract_version="1.0",
    )


def _all_sample_envelopes():
    return [_both_complete_envelope(), _one_errored_envelope(), _not_applicable_envelope()]


def _no_banned_keys(obj):
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

    @classmethod
    def setUpClass(cls):
        with open(_SCHEMA_PATH, encoding="utf-8") as fh:
            cls.schema = json.load(fh)

    def _walk(self, instance, schema, path="<root>"):
        """A minimal, pure-Python JSON-Schema draft-07 conformance walk covering the
        subset this contract uses: type, required, properties, additionalProperties
        (bool), enum, const, minItems/maxItems/uniqueItems, minimum/maximum,
        maxLength, and array items. Raises AssertionError on any violation."""
        stype = schema.get("type")
        if stype == "object":
            self.assertIsInstance(instance, dict, f"{path}: expected object")
            for req in schema.get("required", []):
                self.assertIn(req, instance, f"{path}: missing required {req!r}")
            props = schema.get("properties", {})
            if schema.get("additionalProperties") is False:
                for k in instance:
                    self.assertIn(k, props, f"{path}: additionalProperty {k!r} not allowed")
            for k, v in instance.items():
                if k in props:
                    self._walk(v, props[k], f"{path}.{k}")
        elif stype == "array":
            self.assertIsInstance(instance, list, f"{path}: expected array")
            if "minItems" in schema:
                self.assertGreaterEqual(len(instance), schema["minItems"], f"{path}: minItems")
            if "maxItems" in schema:
                self.assertLessEqual(len(instance), schema["maxItems"], f"{path}: maxItems")
            if schema.get("uniqueItems"):
                self.assertEqual(len(instance), len({json.dumps(x, sort_keys=True) for x in instance}), f"{path}: uniqueItems")
            item_schema = schema.get("items")
            if isinstance(item_schema, dict):
                for i, v in enumerate(instance):
                    self._walk(v, item_schema, f"{path}[{i}]")
        elif stype == "string":
            self.assertIsInstance(instance, str, f"{path}: expected string")
            if "maxLength" in schema:
                self.assertLessEqual(len(instance), schema["maxLength"], f"{path}: maxLength")
        elif stype == "integer":
            self.assertTrue(isinstance(instance, int) and not isinstance(instance, bool), f"{path}: expected integer")
            if "minimum" in schema:
                self.assertGreaterEqual(instance, schema["minimum"], f"{path}: minimum")
            if "maximum" in schema:
                self.assertLessEqual(instance, schema["maximum"], f"{path}: maximum")
        elif stype == "boolean":
            self.assertIsInstance(instance, bool, f"{path}: expected boolean")

        if "enum" in schema:
            self.assertIn(instance, schema["enum"], f"{path}: {instance!r} not in enum")
        if "const" in schema:
            self.assertEqual(instance, schema["const"], f"{path}: {instance!r} != const")

    def test_all_samples_conform(self):
        for env in _all_sample_envelopes():
            self._walk(env, self.schema)

    def test_top_level_required_keys(self):
        for env in _all_sample_envelopes():
            for key in ("contract_version", "intake_id", "sha256", "joined_at", "collected"):
                self.assertIn(key, env)
            self.assertEqual(env["contract_version"], "1.0")

    def test_lane_consts(self):
        for env in _all_sample_envelopes():
            c = env["collected"]
            self.assertEqual(c["static"]["lane"], "static_analysis")
            self.assertEqual(c["dynamic"]["lane"], "dynamic_detonation")
            self.assertIn(c["static"]["lane_status"], collect.LANE_STATUSES)
            self.assertIn(c["dynamic"]["lane_status"], collect.LANE_STATUSES)

    def test_both_complete_is_bool(self):
        for env in _all_sample_envelopes():
            self.assertIsInstance(env["collected"]["both_complete"], bool)

    def test_no_verdict_field_anywhere(self):
        for env in _all_sample_envelopes():
            offending = _no_banned_keys(env)
            self.assertIsNone(offending, f"verdict-shaped key present: {offending}")

    def test_schema_itself_has_no_verdict_property(self):
        self._assert_no_banned_property(self.schema)

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

    def test_both_complete_conforms(self):
        self._assert_conforms(_both_complete_envelope())

    def test_one_errored_conforms(self):
        self._assert_conforms(_one_errored_envelope())

    def test_not_applicable_conforms(self):
        self._assert_conforms(_not_applicable_envelope())

    def test_rejects_injected_verdict(self):
        env = _both_complete_envelope()
        env["collected"]["verdict"] = "safe"
        errors = list(self.validator.iter_errors(env))
        self.assertTrue(errors, "schema must reject an injected verdict field")

    def test_rejects_bad_lane_status(self):
        env = _both_complete_envelope()
        env["collected"]["static"]["lane_status"] = "approved"
        errors = list(self.validator.iter_errors(env))
        self.assertTrue(errors, "schema must reject an out-of-enum lane_status")


if __name__ == "__main__":
    unittest.main()
