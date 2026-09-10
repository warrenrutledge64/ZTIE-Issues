"""ZTIE Story 2.5 — PURE-STDLIB tests for the Hub gate's 9th kind (sanitized telemetry).

The main Hub-gate suite (``test_handler.py``) exercises the real boto3/DynamoDB/S3
paths under ``moto`` (a LIVE/CI dependency, NOT installable in the INTEGRATIONS_ONLY
sandbox). This companion suite proves the load-bearing Story 2.5 additions to the
gate OFFLINE, stdlib-only, WITHOUT touching DynamoDB:

  * the ``sanitized`` discriminator is UNIQUE — it routes a sanitized-telemetry
    record and does NOT collide with the collected / behavior / run / scan /
    rejection / routing / classification / status kinds, and is checked among the
    unique discriminators FIRST in the dispatch chain (before behavior);
  * the sanitized kind pins its OWN version (``SANITIZED_TELEMETRY_CONTRACT_VERSION``
    default '1.0'), never riding the shared ``CONTRACT_VERSION``;
  * the bundled ``sanitized-telemetry.contract.v1.json`` validates a well-formed
    record and fail-closed REJECTS an injected verdict / a wall-clock in an offset /
    a bad status / a bad event category (via a minimal pure-Python draft-07
    conformance walk, since jsonschema is not installable offline);
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

_SCHEMA_PATH = os.path.join(
    os.path.dirname(__file__), "sanitized-telemetry.contract.v1.json"
)

_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_SHA256 = "a" * 64

_BANNED_VERDICT_KEYS = frozenset(
    {"verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean"}
)


def _sanitized_envelope(**over):
    env = {
        "contract_version": "1.0",
        "intake_id": _INTAKE_ID,
        "sha256": _SHA256,
        "sanitized_at": "2026-09-10T00:05:00Z",
        "sanitized": {
            "lane": "dynamic_detonation",
            "source": {
                "capture_tool": "strace",
                "trace_s3_bucket": "ztie-forensic-artifacts",
                "trace_s3_key": "traces/x/behavior-trace.txt",
                "raw_trace_bytes": 4096,
            },
            "pipeline": {
                "status": "sanitized",
                "stages": ["entropy_scrub", "noise_suppress", "truncate"],
                "raw_events": 20,
                "entropy_redactions": 1,
                "noise_suppressed": 8,
                "kept_events": 12,
                "emitted_events": 12,
                "token_budget": 25000,
                "estimated_tokens": 340,
                "truncated": False,
            },
            "events": [
                {
                    "offset_ms": 0,
                    "category": "process",
                    "syscall": "execve",
                    "summary": 'execve("/tmp/ztie/s.sh", ["s.sh"], ...) = 0',
                },
                {
                    "offset_ms": 100,
                    "category": "file",
                    "syscall": "write",
                    "summary": 'write(5</tmp/ztie/loot.txt>, "[REDACTED:b64]", 47) = 47',
                    "redacted": True,
                },
                {
                    "offset_ms": 150,
                    "category": "network",
                    "syscall": "connect",
                    "summary": 'connect(6, {sa_family=AF_INET, sin_port=htons(443), '
                    'sin_addr=inet_addr("93.184.216.34")}, 16) = -1 ENETUNREACH',
                },
            ],
        },
    }
    env.update(over)
    return env


class TestSanitizedDiscriminator(unittest.TestCase):
    def test_sanitized_envelope_is_sanitized(self):
        self.assertTrue(handler._is_sanitized_envelope(_sanitized_envelope()))

    def test_discriminator_unique_across_kinds(self):
        env = _sanitized_envelope()
        self.assertFalse(handler._is_collected_envelope(env))
        self.assertFalse(handler._is_behavior_envelope(env))
        self.assertFalse(handler._is_dynamic_run_envelope(env))
        self.assertFalse(handler._is_summary_envelope(env))
        self.assertFalse(handler._is_reject_envelope(env))
        self.assertFalse(handler._is_routing_envelope(env))
        self.assertFalse(handler._is_classification_envelope(env))

    def test_other_kinds_are_not_sanitized(self):
        self.assertFalse(handler._is_sanitized_envelope({"collected": {}}))
        self.assertFalse(handler._is_sanitized_envelope({"behavior": {}}))
        self.assertFalse(handler._is_sanitized_envelope({"run": {}}))
        self.assertFalse(handler._is_sanitized_envelope({"scan": {}}))
        self.assertFalse(handler._is_sanitized_envelope({"rejection": {}}))
        self.assertFalse(handler._is_sanitized_envelope({"routing": {}}))
        self.assertFalse(handler._is_sanitized_envelope({"classification": {}}))
        self.assertFalse(handler._is_sanitized_envelope({"status": "RECEIVED"}))

    def test_own_version_pin_default(self):
        self.assertEqual(handler.SANITIZED_TELEMETRY_CONTRACT_VERSION, "1.0")
        self.assertTrue(hasattr(handler, "SANITIZED_TELEMETRY_CONTRACT_VERSION"))
        self.assertTrue(hasattr(handler, "BEHAVIOR_CONTRACT_VERSION"))


class TestSanitizedDispatchOrder(unittest.TestCase):
    def test_sanitized_routes_to_process_sanitized(self):
        called = {}

        def _fake_process_sanitized(env, raw, mid):
            called["sanitized"] = True

        orig = handler._process_sanitized
        handler._process_sanitized = _fake_process_sanitized
        try:
            record = {"messageId": "m1", "body": json.dumps(_sanitized_envelope())}
            handler._process_record(record)
        finally:
            handler._process_sanitized = orig
        self.assertTrue(
            called.get("sanitized"),
            "sanitized record must route to _process_sanitized",
        )

    def test_sanitized_not_shadowed_by_behavior_or_collected(self):
        env = _sanitized_envelope()
        self.assertFalse(handler._is_collected_envelope(env))
        self.assertFalse(handler._is_behavior_envelope(env))


class TestSanitizedApplyNeverTouchesVerdict(unittest.TestCase):
    def test_apply_update_expression_is_evidence_only(self):
        captured = {}

        class _FakeTable:
            def update_item(self, **kwargs):
                captured.update(kwargs)

        orig = handler._table
        handler._table = lambda: _FakeTable()
        try:
            handler._apply_sanitized(_sanitized_envelope())
        finally:
            handler._table = orig

        expr = captured["UpdateExpression"]
        # Only evidence fields are set.
        self.assertIn("sanitized = :s", expr)
        self.assertIn("sanitize_status = :ss", expr)
        self.assertIn("sanitize_truncated = :tr", expr)
        self.assertIn("sanitized_at = :sa", expr)
        # NEVER the lifecycle status attribute or a verdict. (sanitize_status is a
        # flattened EVIDENCE field, not the Hub-owned lifecycle `status`.)
        self.assertNotRegex(expr, r"(?<![_a-zA-Z])status\s*=")
        self.assertNotIn("#s", expr)  # the lifecycle status alias used by _persist
        self.assertNotIn("verdict", expr.lower())
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
        self.assertTrue(self._conforms(_sanitized_envelope()))

    def test_injected_verdict_rejected(self):
        bad = _sanitized_envelope()
        bad["sanitized"]["verdict"] = "safe"  # additionalProperties:false rejects
        self.assertFalse(self._conforms(bad))

    def test_bad_status_rejected(self):
        bad = _sanitized_envelope()
        bad["sanitized"]["pipeline"]["status"] = "approved"
        self.assertFalse(self._conforms(bad))

    def test_wall_clock_in_offset_rejected(self):
        bad = _sanitized_envelope()
        bad["sanitized"]["events"][0]["offset_ms"] = "2026-09-10T00:00:00Z"
        self.assertFalse(self._conforms(bad))

    def test_bad_event_category_rejected(self):
        bad = _sanitized_envelope()
        bad["sanitized"]["events"][0]["category"] = "malicious"
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
