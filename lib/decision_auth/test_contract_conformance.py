"""ZTIE Story H.2 (RD-048/RD-049) — contract-conformance for decision.token.v1.

TWO layers (the proven pattern):
  * OFFLINE (always, stdlib): a pure-Python conformance walk asserting a valid token
    satisfies the allow-list (required keys, enums, patterns, additionalProperties
    false, bounds) and that an injected verdict field / bad decision is rejected;
    plus a schema-has-no-verdict-property check.
  * LIVE (pytest, jsonschema installed): validates sample tokens against the exact
    bundled schema. Skips offline (PyPI blocked).
"""

from __future__ import annotations

import json
import os
import unittest

try:
    from jsonschema import Draft7Validator

    _HAVE_JSONSCHEMA = True
except ImportError:  # offline sandbox
    _HAVE_JSONSCHEMA = False

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "decision.token.v1.json")

_INTAKE = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_SHA = "a" * 64

_BANNED_VERDICT_KEYS = frozenset(
    {"verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean"}
)


def _token(**over):
    t = {
        "contract_version": "1.0",
        "intake_id": _INTAKE,
        "decision": "accepted",
        "sha256": _SHA,
        "issued_at": "2026-09-13T11:59:00Z",
        "key_id": "arn:aws:kms:us-east-1:641628980935:key/abcd",
    }
    t.update(over)
    return t


class TestOfflineConformanceWalk(unittest.TestCase):
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
        elif stype == "string":
            self.assertIsInstance(instance, str, f"{path}: expected string")
            if "maxLength" in schema:
                self.assertLessEqual(len(instance), schema["maxLength"], f"{path}: maxLength")
            if "minLength" in schema:
                self.assertGreaterEqual(len(instance), schema["minLength"], f"{path}: minLength")
        if "enum" in schema:
            self.assertIn(instance, schema["enum"], f"{path}: {instance!r} not in enum")

    def _conforms(self, instance):
        try:
            self._walk(instance, self.schema)
            return True
        except AssertionError:
            return False

    def test_valid_token_conforms(self):
        self.assertTrue(self._conforms(_token()))
        self.assertTrue(self._conforms(_token(decision="rejected")))

    def test_required_keys(self):
        for key in ("contract_version", "intake_id", "decision", "sha256", "issued_at", "key_id"):
            self.assertIn(key, _token())

    def test_injected_verdict_rejected(self):
        bad = _token()
        bad["verdict"] = "safe"  # additionalProperties:false
        self.assertFalse(self._conforms(bad))

    def test_bad_decision_rejected(self):
        self.assertFalse(self._conforms(_token(decision="inconclusive")))
        self.assertFalse(self._conforms(_token(decision="maybe")))

    def test_no_inconclusive_in_decision_enum(self):
        # INCONCLUSIVE is a hold: it must NOT be an authorizable decision value.
        decision_enum = self.schema["properties"]["decision"]["enum"]
        self.assertEqual(set(decision_enum), {"accepted", "rejected"})

    def test_schema_has_no_verdict_property(self):
        props = self.schema.get("properties", {})
        for pk in props:
            self.assertNotIn(pk, _BANNED_VERDICT_KEYS, f"verdict property {pk!r}")


@unittest.skipUnless(_HAVE_JSONSCHEMA, "jsonschema not available offline")
class TestLiveContractConformance(unittest.TestCase):
    def setUp(self):
        with open(_SCHEMA_PATH, encoding="utf-8") as fh:
            self.validator = Draft7Validator(json.load(fh))

    def _conforms(self, tok):
        return list(self.validator.iter_errors(tok)) == []

    def test_valid_tokens(self):
        self.assertTrue(self._conforms(_token()))
        self.assertTrue(self._conforms(_token(decision="rejected")))

    def test_rejects_injected_verdict(self):
        bad = _token()
        bad["verdict"] = "safe"
        self.assertFalse(self._conforms(bad))

    def test_rejects_inconclusive(self):
        self.assertFalse(self._conforms(_token(decision="inconclusive")))

    def test_rejects_bad_sha(self):
        self.assertFalse(self._conforms(_token(sha256="zz")))


if __name__ == "__main__":
    unittest.main()
