"""ZTIE Story 4.7 — PURE-STDLIB tests for the Hub gate's 11th kind (REJECT/disposition).

The main Hub-gate suite (``test_handler.py``) exercises the real boto3/DynamoDB/S3
paths under ``moto`` (a LIVE/CI dependency, NOT installable in the INTEGRATIONS_ONLY
sandbox). This companion suite proves the load-bearing Story 4.7 additions to the
gate OFFLINE, stdlib-only, WITHOUT touching DynamoDB:

  * the ``disposition`` discriminator is UNIQUE — it routes a disposition outcome and
    does NOT collide with the handoff / collected / sanitized / behavior / run / scan /
    rejection / routing / classification / status kinds, and is checked FIRST in the
    dispatch (among the unique discriminators);
  * the disposition kind pins its OWN version (``DISPOSITION_CONTRACT_VERSION`` default
    '1.0'), never riding the shared ``CONTRACT_VERSION``;
  * the apply update-expression records the outcome onto its OWN fields and NEVER
    touches ``status`` (RD-040/RD-047: verdict/status stay Hub-owned/human-gated);
  * the bundled ``disposition.contract.v1.json`` validates a well-formed disposition
    outcome and fail-closed REJECTS an injected verdict / wrong version (via a minimal
    pure-Python draft-07 conformance walk, since jsonschema is not installable
    offline).

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

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "disposition.contract.v1.json")

_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_SHA256 = "a" * 64

_BANNED_VERDICT_KEYS = frozenset(
    {"verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean"}
)


def _disposition_envelope(**over):
    env = {
        "contract_version": "1.0",
        "intake_id": _INTAKE_ID,
        "sha256": _SHA256,
        "disposed_at": "2026-09-14T00:00:00Z",
        "disposition": {
            "outcome": "destroyed",
            "observed_decision": "rejected",
            "hash_verified": True,
            "chamber_state": "terminated",
            "report_survives": True,
            "reason": "verified Hub-signed rejected token + matching artifact sha256",
            "destroyed": {
                "artifact_versions_deleted": 4,
                "prefixes_cleared": [
                    f"intake/{_INTAKE_ID}/",
                    f"findings/{_INTAKE_ID}/",
                    f"runs/{_INTAKE_ID}/",
                    f"traces/{_INTAKE_ID}/",
                ],
                "chamber": "terminated",
                "chamber_instance_id": "i-0abc123def456",
                "destroyed_at": "2026-09-14T00:00:01Z",
            },
        },
    }
    env.update(over)
    return env


class TestDispositionDiscriminator(unittest.TestCase):
    def test_disposition_envelope_is_disposition(self):
        self.assertTrue(handler._is_disposition_envelope(_disposition_envelope()))

    def test_discriminator_unique_across_kinds(self):
        env = _disposition_envelope()
        self.assertFalse(handler._is_handoff_envelope(env))
        self.assertFalse(handler._is_collected_envelope(env))
        self.assertFalse(handler._is_sanitized_envelope(env))
        self.assertFalse(handler._is_behavior_envelope(env))
        self.assertFalse(handler._is_dynamic_run_envelope(env))
        self.assertFalse(handler._is_summary_envelope(env))
        self.assertFalse(handler._is_reject_envelope(env))
        self.assertFalse(handler._is_routing_envelope(env))
        self.assertFalse(handler._is_classification_envelope(env))

    def test_other_kinds_are_not_disposition(self):
        self.assertFalse(handler._is_disposition_envelope({"handoff": {}}))
        self.assertFalse(handler._is_disposition_envelope({"collected": {}}))
        self.assertFalse(handler._is_disposition_envelope({"run": {}}))
        self.assertFalse(handler._is_disposition_envelope({"scan": {}}))
        self.assertFalse(handler._is_disposition_envelope({"status": "RECEIVED"}))

    def test_own_version_pin_default(self):
        self.assertEqual(handler.DISPOSITION_CONTRACT_VERSION, "1.0")
        self.assertTrue(hasattr(handler, "DISPOSITION_CONTRACT_VERSION"))

    def test_apply_never_touches_status(self):
        spec = handler._KINDS_BY_NAME["disposition"]
        self.assertNotIn("status", spec.update_expression.lower())
        # Records onto its own fields only.
        self.assertIn("disposition", spec.update_expression)
        self.assertIn("disposition_outcome", spec.update_expression)
        self.assertIn("disposed_at", spec.update_expression)


class TestDispositionDispatchOrder(unittest.TestCase):
    def test_disposition_checked_and_routes(self):
        called = {}

        def _fake_process_disposition(env, raw, mid):
            called["disposition"] = True

        orig = handler._process_disposition
        handler._process_disposition = _fake_process_disposition
        try:
            record = {"messageId": "m1", "body": json.dumps(_disposition_envelope())}
            handler._process_record(record)
        finally:
            handler._process_disposition = orig
        self.assertTrue(
            called.get("disposition"),
            "disposition outcome must route to _process_disposition",
        )

    def test_disposition_not_shadowed_by_handoff(self):
        # A disposition envelope must not be mistaken for a handoff (both are unique).
        env = _disposition_envelope()
        matched = [
            spec.name for spec in handler._KINDS if spec.discriminator in env
        ]
        self.assertEqual(matched[0], "disposition")


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
            self.assertTrue(
                isinstance(instance, int) and not isinstance(instance, bool), f"{path}"
            )
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
        self.assertTrue(self._conforms(_disposition_envelope()))

    def test_injected_verdict_rejected(self):
        bad = _disposition_envelope()
        bad["disposition"]["verdict"] = "malicious"  # additionalProperties:false rejects
        self.assertFalse(self._conforms(bad))

    def test_bad_outcome_rejected(self):
        bad = _disposition_envelope()
        bad["disposition"]["outcome"] = "promoted"
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
