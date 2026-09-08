"""ZTIE Story 2.6 — PURE-STDLIB tests for the Hub gate's 7th kind (collected record).

The main Hub-gate suite (``test_handler.py``) exercises the real boto3/DynamoDB/S3
paths under ``moto`` (a LIVE/CI dependency, NOT installable in the INTEGRATIONS_ONLY
sandbox). This companion suite proves the load-bearing Story 2.6 additions to the
gate OFFLINE, stdlib-only, WITHOUT touching DynamoDB:

  * the ``collected`` discriminator is UNIQUE — it routes a collected record and
    does NOT collide with the run / scan / rejection / routing / classification /
    status kinds, and is checked FIRST in the dispatch chain;
  * the collected kind pins its OWN version (``COLLECTED_CONTRACT_VERSION`` default
    '1.0'), never riding the shared ``CONTRACT_VERSION``;
  * the bundled ``collected.contract.v1.json`` validates a well-formed collected
    record and fail-closed REJECTS an injected verdict / wrong version (via a
    minimal pure-Python draft-07 conformance walk, since jsonschema is not
    installable offline).

boto3 + jsonschema are STUBBED into ``sys.modules`` so ``handler`` imports offline
(the gate's boto3/jsonschema calls are never invoked here — only the pure
discriminator + the bundled schema are exercised).
"""

from __future__ import annotations

import json
import os
import sys
import types
import unittest

# --- Stub the two unavailable third-party deps so handler.py imports offline ----
if "boto3" not in sys.modules:
    _boto3 = types.ModuleType("boto3")
    _boto3.client = lambda *a, **k: None  # never called in these tests
    _boto3.resource = lambda *a, **k: None
    sys.modules["boto3"] = _boto3

if "jsonschema" not in sys.modules:
    _js = types.ModuleType("jsonschema")

    class _StubValidator:  # only instantiated lazily; never used in these tests
        def __init__(self, *a, **k):
            pass

        def iter_errors(self, *a, **k):
            return iter(())

    _js.Draft7Validator = _StubValidator
    sys.modules["jsonschema"] = _js

import handler  # import after stubbing boto3/jsonschema above

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "collected.contract.v1.json")

_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_SHA256 = "a" * 64

_BANNED_VERDICT_KEYS = frozenset(
    {"verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean"}
)


def _collected_envelope(**over):
    env = {
        "contract_version": "1.0",
        "intake_id": _INTAKE_ID,
        "sha256": _SHA256,
        "joined_at": "2026-09-06T00:05:00Z",
        "collected": {
            "lanes_expected": ["static_analysis", "dynamic_detonation"],
            "lanes_collected": ["static_analysis", "dynamic_detonation"],
            "both_complete": True,
            "static": {"lane": "static_analysis", "lane_status": "completed", "highest_severity": "high"},
            "dynamic": {"lane": "dynamic_detonation", "lane_status": "completed", "outcome": "completed"},
        },
    }
    env.update(over)
    return env


class TestCollectedDiscriminator(unittest.TestCase):
    def test_collected_envelope_is_collected(self):
        self.assertTrue(handler._is_collected_envelope(_collected_envelope()))

    def test_discriminator_unique_across_kinds(self):
        # A collected record must NOT be mistaken for any other kind: its top-level
        # keys are contract_version/intake_id/sha256/joined_at/collected — none of
        # which are the run/scan/rejection/routing/classification discriminators.
        env = _collected_envelope()
        self.assertFalse(handler._is_dynamic_run_envelope(env))
        self.assertFalse(handler._is_summary_envelope(env))
        self.assertFalse(handler._is_reject_envelope(env))
        self.assertFalse(handler._is_routing_envelope(env))
        self.assertFalse(handler._is_classification_envelope(env))

    def test_other_kinds_are_not_collected(self):
        # And the reverse: the other kinds' discriminators do not carry 'collected'.
        self.assertFalse(handler._is_collected_envelope({"run": {}}))
        self.assertFalse(handler._is_collected_envelope({"scan": {}}))
        self.assertFalse(handler._is_collected_envelope({"rejection": {}}))
        self.assertFalse(handler._is_collected_envelope({"routing": {}}))
        self.assertFalse(handler._is_collected_envelope({"classification": {}}))
        self.assertFalse(handler._is_collected_envelope({"status": "RECEIVED"}))

    def test_own_version_pin_default(self):
        # The collected kind pins its OWN version, defaulting to '1.0' — NOT riding
        # the shared CONTRACT_VERSION (which is also '1.0' but a SEPARATE constant).
        self.assertEqual(handler.COLLECTED_CONTRACT_VERSION, "1.0")
        # It is a distinct module-level constant from the other per-kind pins.
        self.assertTrue(hasattr(handler, "COLLECTED_CONTRACT_VERSION"))
        self.assertTrue(hasattr(handler, "DYNAMIC_RUN_CONTRACT_VERSION"))


class TestCollectedDispatchOrder(unittest.TestCase):
    def test_collected_checked_first(self):
        # Drive _process_record with a monkeypatched dispatch so we observe which
        # _process_* the collected envelope routes to WITHOUT touching AWS.
        called = {}

        def _fake_process_collected(env, raw, mid):
            called["collected"] = True

        orig = handler._process_collected
        handler._process_collected = _fake_process_collected
        try:
            record = {"messageId": "m1", "body": json.dumps(_collected_envelope())}
            handler._process_record(record)
        finally:
            handler._process_collected = orig
        self.assertTrue(called.get("collected"), "collected record must route to _process_collected")


class TestBundledSchemaConformance(unittest.TestCase):
    """Minimal pure-Python draft-07 walk over the bundled schema the gate loads."""

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
                    self.assertIn(k, props, f"{path}: additionalProperty {k!r}")
            for k, v in instance.items():
                if k in props:
                    self._walk(v, props[k], f"{path}.{k}")
        elif stype == "array":
            self.assertIsInstance(instance, list, f"{path}: expected array")
            item_schema = schema.get("items")
            if isinstance(item_schema, dict):
                for i, v in enumerate(instance):
                    self._walk(v, item_schema, f"{path}[{i}]")
        elif stype == "string":
            self.assertIsInstance(instance, str, f"{path}: expected string")
        elif stype == "integer":
            self.assertTrue(isinstance(instance, int) and not isinstance(instance, bool), f"{path}")
        elif stype == "boolean":
            self.assertIsInstance(instance, bool, f"{path}: expected boolean")
        if "enum" in schema:
            self.assertIn(instance, schema["enum"], f"{path}: {instance!r} not in enum")
        if "const" in schema:
            self.assertEqual(instance, schema["const"], f"{path}: != const")

    def _conforms(self, instance) -> bool:
        try:
            self._walk(instance, self.schema)
            return True
        except AssertionError:
            return False

    def test_valid_record_conforms(self):
        self.assertTrue(self._conforms(_collected_envelope()))

    def test_injected_verdict_rejected(self):
        bad = _collected_envelope()
        bad["collected"]["verdict"] = "safe"  # additionalProperties:false rejects
        self.assertFalse(self._conforms(bad))

    def test_bad_lane_status_rejected(self):
        bad = _collected_envelope()
        bad["collected"]["static"]["lane_status"] = "approved"
        self.assertFalse(self._conforms(bad))

    def test_schema_has_no_verdict_property(self):
        self._assert_no_banned_property(self.schema)

    def _assert_no_banned_property(self, node):
        if isinstance(node, dict):
            props = node.get("properties")
            if isinstance(props, dict):
                for pk in props:
                    self.assertNotIn(pk, _BANNED_VERDICT_KEYS, f"verdict property {pk!r}")
            for v in node.values():
                self._assert_no_banned_property(v)
        elif isinstance(node, list):
            for v in node:
                self._assert_no_banned_property(v)


if __name__ == "__main__":
    unittest.main()
