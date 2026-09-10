"""ZTIE Story 2.4 — PURE-STDLIB tests for the Hub gate's 8th kind (behavior telemetry).

The main Hub-gate suite (``test_handler.py``) exercises the real boto3/DynamoDB/S3
paths under ``moto`` (a LIVE/CI dependency, NOT installable in the INTEGRATIONS_ONLY
sandbox). This companion suite proves the load-bearing Story 2.4 additions to the
gate OFFLINE, stdlib-only, WITHOUT touching DynamoDB:

  * the ``behavior`` discriminator is UNIQUE — it routes a behavioral-telemetry
    record and does NOT collide with the collected / run / scan / rejection /
    routing / classification / status kinds, and is checked among the unique
    discriminators FIRST in the dispatch chain;
  * the behavior kind pins its OWN version (``BEHAVIOR_CONTRACT_VERSION`` default
    '1.0'), never riding the shared ``CONTRACT_VERSION``;
  * the bundled ``behavior.contract.v1.json`` validates a well-formed record and
    fail-closed REJECTS an injected verdict / a wall-clock in an offset / a bad
    capture_status (via a minimal pure-Python draft-07 conformance walk, since
    jsonschema is not installable offline);
  * the integrity-bound apply NEVER touches status/verdict (SET expression asserted).

boto3 + jsonschema are STUBBED into ``sys.modules`` so ``handler`` imports offline.
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

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "behavior.contract.v1.json")

_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_SHA256 = "a" * 64

_BANNED_VERDICT_KEYS = frozenset(
    {"verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean"}
)


def _behavior_envelope(**over):
    env = {
        "contract_version": "1.0",
        "intake_id": _INTAKE_ID,
        "sha256": _SHA256,
        "captured_at": "2026-09-08T00:05:00Z",
        "behavior": {
            "lane": "dynamic_detonation",
            "capture": {
                "capture_tool": "strace",
                "capture_status": "captured",
                "host_native": True,
                "no_docker": True,
                "capture_started_offset_ms": 1200,
                "capture_stopped_offset_ms": 63000,
                "trace_truncated": False,
                "trace_s3_bucket": "ztie-forensic-artifacts",
                "trace_s3_key": "traces/x/behavior-trace.txt",
            },
            "syscalls": {"total": 2, "distinct": 2, "top": [{"name": "connect", "count": 1}]},
            "network": {
                "connect_attempts": 1,
                "distinct_destinations": 1,
                "dns_lookups": 0,
                "destinations": [
                    {"destination": "93.184.216.34:443", "attempts": 1, "connected": False}
                ],
            },
            "filesystem": {"total_ops": 1, "opens": 1, "paths": [{"path": "/etc/passwd", "op": "open", "count": 1}]},
        },
    }
    env.update(over)
    return env


class TestBehaviorDiscriminator(unittest.TestCase):
    def test_behavior_envelope_is_behavior(self):
        self.assertTrue(handler._is_behavior_envelope(_behavior_envelope()))

    def test_discriminator_unique_across_kinds(self):
        env = _behavior_envelope()
        self.assertFalse(handler._is_collected_envelope(env))
        self.assertFalse(handler._is_dynamic_run_envelope(env))
        self.assertFalse(handler._is_summary_envelope(env))
        self.assertFalse(handler._is_reject_envelope(env))
        self.assertFalse(handler._is_routing_envelope(env))
        self.assertFalse(handler._is_classification_envelope(env))

    def test_other_kinds_are_not_behavior(self):
        self.assertFalse(handler._is_behavior_envelope({"collected": {}}))
        self.assertFalse(handler._is_behavior_envelope({"run": {}}))
        self.assertFalse(handler._is_behavior_envelope({"scan": {}}))
        self.assertFalse(handler._is_behavior_envelope({"rejection": {}}))
        self.assertFalse(handler._is_behavior_envelope({"routing": {}}))
        self.assertFalse(handler._is_behavior_envelope({"classification": {}}))
        self.assertFalse(handler._is_behavior_envelope({"status": "RECEIVED"}))

    def test_own_version_pin_default(self):
        self.assertEqual(handler.BEHAVIOR_CONTRACT_VERSION, "1.0")
        self.assertTrue(hasattr(handler, "BEHAVIOR_CONTRACT_VERSION"))
        self.assertTrue(hasattr(handler, "COLLECTED_CONTRACT_VERSION"))


class TestBehaviorDispatchOrder(unittest.TestCase):
    def test_behavior_routes_to_process_behavior(self):
        called = {}

        def _fake_process_behavior(env, raw, mid):
            called["behavior"] = True

        orig = handler._process_behavior
        handler._process_behavior = _fake_process_behavior
        try:
            record = {"messageId": "m1", "body": json.dumps(_behavior_envelope())}
            handler._process_record(record)
        finally:
            handler._process_behavior = orig
        self.assertTrue(called.get("behavior"), "behavior record must route to _process_behavior")

    def test_behavior_not_shadowed_by_collected(self):
        # A behavior record has no 'collected' key, so it must NOT be swallowed by
        # the collected check that runs first.
        self.assertFalse(handler._is_collected_envelope(_behavior_envelope()))


class TestBehaviorApplyNeverTouchesVerdict(unittest.TestCase):
    def test_apply_update_expression_is_evidence_only(self):
        # Capture the update_item kwargs WITHOUT a real table, to assert the SET
        # expression only writes evidence fields + is integrity-bound, never status
        # or a verdict.
        captured = {}

        class _FakeTable:
            def update_item(self, **kwargs):
                captured.update(kwargs)

        orig = handler._table
        handler._table = lambda: _FakeTable()
        try:
            handler._apply_behavior(_behavior_envelope())
        finally:
            handler._table = orig

        expr = captured["UpdateExpression"]
        # Only evidence fields are set.
        self.assertIn("behavior = :b", expr)
        self.assertIn("behavior_capture_status = :cs", expr)
        self.assertIn("captured_at = :ca", expr)
        # NEVER the lifecycle status attribute or a verdict. (behavior_capture_status
        # is a flattened EVIDENCE field, not the Hub-owned lifecycle `status`.)
        self.assertNotRegex(expr, r"(?<![_a-zA-Z])status\s*=")
        self.assertNotIn("#s", expr)  # the lifecycle status alias used by _persist
        self.assertNotIn("verdict", expr.lower())
        # And no lifecycle status alias is smuggled via ExpressionAttributeNames.
        self.assertNotIn("ExpressionAttributeNames", captured)
        # Integrity-bound: record must exist AND sha256 must match.
        self.assertIn(
            "attribute_exists(intake_id) AND sha256 = :sha",
            captured["ConditionExpression"],
        )


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
            max_items = schema.get("maxItems")
            if max_items is not None:
                self.assertLessEqual(len(instance), max_items, f"{path}: too many items")
            item_schema = schema.get("items")
            if isinstance(item_schema, dict):
                for i, v in enumerate(instance):
                    self._walk(v, item_schema, f"{path}[{i}]")
        elif stype == "string":
            self.assertIsInstance(instance, str, f"{path}: expected string")
            max_len = schema.get("maxLength")
            if max_len is not None:
                self.assertLessEqual(len(instance), max_len, f"{path}: too long")
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
        self.assertTrue(self._conforms(_behavior_envelope()))

    def test_injected_verdict_rejected(self):
        bad = _behavior_envelope()
        bad["behavior"]["verdict"] = "safe"  # additionalProperties:false rejects
        self.assertFalse(self._conforms(bad))

    def test_bad_capture_status_rejected(self):
        bad = _behavior_envelope()
        bad["behavior"]["capture"]["capture_status"] = "approved"
        self.assertFalse(self._conforms(bad))

    def test_wall_clock_in_offset_rejected(self):
        bad = _behavior_envelope()
        bad["behavior"]["capture"]["capture_started_offset_ms"] = "2026-09-08T00:00:00Z"
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
