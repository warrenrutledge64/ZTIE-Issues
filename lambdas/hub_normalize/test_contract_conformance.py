"""ZTIE Story 3.1 — contract-conformance for the combined-event record.

TWO layers, so the loop between the schema-first contract and the code is closed
both live AND offline (the proven 2.2 -> 2.6 lesson):

  * LIVE (pytest, jsonschema installed): every envelope ``combine.py`` builds must
    validate against ``combined-event.contract.v1.json``. Skips in the
    INTEGRATIONS_ONLY sandbox (PyPI blocked).

  * OFFLINE (always, stdlib only): a MANUAL pure-Python conformance walk that
    asserts the built envelopes satisfy the contract's load-bearing invariants
    (required keys, allow-listed enums, additionalProperties allow-list at every
    level, byte/length/array bounds, NO verdict field) even when jsonschema is not
    installable, plus a schema-has-no-verdict-property check.
"""

from __future__ import annotations

import json
import os
import unittest

import combine

try:
    from jsonschema import Draft7Validator

    _HAVE_JSONSCHEMA = True
except ImportError:  # offline sandbox
    _HAVE_JSONSCHEMA = False

_SCHEMA_PATH = os.path.join(
    os.path.dirname(__file__), "combined-event.contract.v1.json"
)

_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_SHA256 = "a" * 64
_CV = "1.0"

_BANNED_VERDICT_KEYS = frozenset(
    {"verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean"}
)


def _full_item():
    return {
        "intake_id": _INTAKE_ID,
        "sha256": _SHA256,
        "status": "RECEIVED",
        "static_scan": {
            "contract_version": "1.1",
            "highest_severity": "high",
            "total_findings": 3,
            "findings_s3_bucket": "ztie-forensic-artifacts",
            "findings_s3_key": f"findings/{_INTAKE_ID}/static-findings.json",
        },
        "dynamic_run": {
            "contract_version": "1.0",
            "outcome": "completed",
            "execution": {
                "output_s3_bucket": "ztie-forensic-artifacts",
                "output_s3_key": f"runs/{_INTAKE_ID}/detonation-output.json",
            },
        },
        "sanitized": {
            "contract_version": "1.0",
            "lane": "dynamic_detonation",
            "source": {
                "capture_tool": "strace",
                "trace_s3_bucket": "ztie-forensic-artifacts",
                "trace_s3_key": f"traces/{_INTAKE_ID}/behavior-trace.txt",
                "raw_trace_bytes": 40000,
            },
            "pipeline": {
                "status": "sanitized",
                "stages": ["entropy_scrub", "noise_suppress", "truncate"],
                "token_budget": 25000,
                "estimated_tokens": 1200,
                "truncated": False,
            },
            "events": [
                {
                    "offset_ms": 12,
                    "category": "process",
                    "syscall": "execve",
                    "summary": "execve(/tmp/artifact)",
                    "redacted": False,
                },
                {
                    "offset_ms": 48,
                    "category": "network",
                    "syscall": "connect",
                    "summary": "connect(93.184.216.34:443) [REDACTED:token]",
                    "redacted": True,
                },
            ],
        },
    }


def _full_envelope():
    return combine.combine(
        item=_full_item(), combined_at="2026-09-11T00:05:00Z", contract_version=_CV
    )


def _partial_envelope():
    """Only the static input has landed; dynamic + sanitized absent (SQS ordering)."""
    item = {
        "intake_id": _INTAKE_ID,
        "sha256": _SHA256,
        "static_scan": {"highest_severity": "low", "total_findings": 1},
    }
    return combine.combine(
        item=item,
        combined_at="2026-09-11T00:05:00Z",
        contract_version=_CV,
        normalize_note="dynamic + sanitized not yet present; re-derives on next update",
    )


def _empty_envelope():
    """No inputs landed yet — a valid, honest, empty combined event."""
    item = {"intake_id": _INTAKE_ID, "sha256": _SHA256}
    return combine.combine(
        item=item, combined_at="2026-09-11T00:05:00Z", contract_version=_CV
    )


def _all_sample_envelopes():
    return [_full_envelope(), _partial_envelope(), _empty_envelope()]


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
                self.assertEqual(
                    len(instance),
                    len({json.dumps(x, sort_keys=True) for x in instance}),
                    f"{path}: uniqueItems",
                )
            item_schema = schema.get("items")
            if isinstance(item_schema, dict):
                for i, v in enumerate(instance):
                    self._walk(v, item_schema, f"{path}[{i}]")
        elif stype == "string":
            self.assertIsInstance(instance, str, f"{path}: expected string")
            if "maxLength" in schema:
                self.assertLessEqual(len(instance), schema["maxLength"], f"{path}: maxLength")
        elif stype == "integer":
            self.assertTrue(
                isinstance(instance, int) and not isinstance(instance, bool),
                f"{path}: expected integer",
            )
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
            for key in ("contract_version", "intake_id", "sha256", "combined_at", "combined_event"):
                self.assertIn(key, env)
            self.assertEqual(env["contract_version"], "1.0")

    def test_full_is_complete_partial_and_empty_are_not(self):
        self.assertTrue(_full_envelope()["combined_event"]["complete"])
        self.assertFalse(_partial_envelope()["combined_event"]["complete"])
        self.assertFalse(_empty_envelope()["combined_event"]["complete"])

    def test_source_input_consts(self):
        for env in _all_sample_envelopes():
            sources = env["combined_event"]["sources"]
            self.assertEqual(sources["static"]["input"], "static")
            self.assertEqual(sources["dynamic"]["input"], "dynamic")
            self.assertEqual(sources["sanitized"]["input"], "sanitized")

    def test_inputs_present_matches_sources(self):
        for env in _all_sample_envelopes():
            ce = env["combined_event"]
            present = set(ce["inputs_present"])
            for name in ("static", "dynamic", "sanitized"):
                is_present = ce["sources"][name]["presence"] == "present"
                self.assertEqual(name in present, is_present)

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
    """Live jsonschema validation against the exact contract 3.2 will consume."""

    def setUp(self):
        with open(_SCHEMA_PATH, encoding="utf-8") as fh:
            self.validator = Draft7Validator(json.load(fh))

    def _assert_conforms(self, env):
        errors = sorted(self.validator.iter_errors(env), key=str)
        self.assertEqual(errors, [], f"schema errors: {errors}")

    def test_full_conforms(self):
        self._assert_conforms(_full_envelope())

    def test_partial_conforms(self):
        self._assert_conforms(_partial_envelope())

    def test_empty_conforms(self):
        self._assert_conforms(_empty_envelope())

    def test_rejects_injected_verdict(self):
        env = _full_envelope()
        env["combined_event"]["verdict"] = "safe"
        errors = list(self.validator.iter_errors(env))
        self.assertTrue(errors, "schema must reject an injected verdict field")

    def test_rejects_bad_severity(self):
        env = _full_envelope()
        env["combined_event"]["signals"]["static_highest_severity"] = "approved"
        errors = list(self.validator.iter_errors(env))
        self.assertTrue(errors, "schema must reject an out-of-enum severity")


if __name__ == "__main__":
    unittest.main()
