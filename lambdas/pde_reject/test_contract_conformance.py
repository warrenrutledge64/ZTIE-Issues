"""ZTIE Story 4.7 (RD-047) — contract-conformance for the disposition outcome envelope.

TWO layers, so the loop between the schema-first contract and the code is closed both
LIVE and OFFLINE (the proven 2.6/4.5/4.6 pattern):

  * LIVE (pytest, jsonschema installed): every envelope
    ``reject.build_disposition_envelope`` builds must validate against
    ``disposition.contract.v1.json`` (the exact allow-list the Hub validator enforces).
    Skips in the INTEGRATIONS_ONLY sandbox (PyPI blocked).

  * OFFLINE (always, stdlib only): a MANUAL pure-Python conformance walk asserting the
    built envelopes satisfy the contract's load-bearing invariants (required keys,
    allow-listed enums, additionalProperties allow-list at every level, byte/length
    bounds, NO verdict field) even without jsonschema; plus a schema-has-no-verdict-
    property check.
"""

from __future__ import annotations

import json
import os
import unittest

import reject

try:
    from jsonschema import Draft7Validator

    _HAVE_JSONSCHEMA = True
except ImportError:  # offline sandbox
    _HAVE_JSONSCHEMA = False

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "disposition.contract.v1.json")

_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_SHA256 = "a" * 64

_BANNED_VERDICT_KEYS = frozenset(
    {"verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean"}
)


def _destroyed_envelope():
    decision = reject.GateDecision(
        destroy=True,
        outcome=reject.OUTCOME_DESTROYED,
        reason="verified Hub-signed rejected token + matching artifact sha256",
        observed_decision="rejected",
    )
    return reject.build_disposition_envelope(
        intake_id=_INTAKE_ID,
        sha256=_SHA256,
        disposed_at="2026-09-14T00:00:00Z",
        decision=decision,
        hash_verified=True,
        chamber_state=reject.CHAMBER_TERMINATED,
        artifact_s3_key=f"intake/{_INTAKE_ID}/app.zip",
        destroyed={
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
    )


def _held_envelope():
    decision = reject.GateDecision(
        destroy=False,
        outcome=reject.OUTCOME_HELD,
        reason="no rejected decision token presented (hold at approval gate)",
        observed_decision="pending",
    )
    return reject.build_disposition_envelope(
        intake_id=_INTAKE_ID,
        sha256=_SHA256,
        disposed_at="2026-09-14T00:00:00Z",
        decision=decision,
        hash_verified=False,
        chamber_state=reject.CHAMBER_NOT_CHECKED,
        artifact_s3_key=f"intake/{_INTAKE_ID}/app.zip",
    )


def _refused_not_rejected_envelope():
    decision = reject.GateDecision(
        destroy=False,
        outcome=reject.OUTCOME_REFUSED_NOT_REJECTED,
        reason="wrong_decision: decision 'accepted' != required 'rejected'",
        observed_decision="accepted",
    )
    return reject.build_disposition_envelope(
        intake_id=_INTAKE_ID,
        sha256=_SHA256,
        disposed_at="2026-09-14T00:00:00Z",
        decision=decision,
        hash_verified=False,
        chamber_state=reject.CHAMBER_NOT_CHECKED,
    )


def _refused_hash_mismatch_envelope():
    decision = reject.GateDecision(
        destroy=False,
        outcome=reject.OUTCOME_REFUSED_HASH_MISMATCH,
        reason="sha_mismatch: token sha256 does not match the artifact",
        observed_decision="rejected",
    )
    return reject.build_disposition_envelope(
        intake_id=_INTAKE_ID,
        sha256=_SHA256,
        disposed_at="2026-09-14T00:00:00Z",
        decision=decision,
        hash_verified=False,
        chamber_state=reject.CHAMBER_NOT_CHECKED,
    )


def _all_sample_envelopes():
    return [
        _destroyed_envelope(),
        _held_envelope(),
        _refused_not_rejected_envelope(),
        _refused_hash_mismatch_envelope(),
    ]


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
                    self.assertIn(
                        k, props, f"{path}: additionalProperty {k!r} not allowed"
                    )
            for k, v in instance.items():
                if k in props:
                    self._walk(v, props[k], f"{path}.{k}")
        elif stype == "array":
            self.assertIsInstance(instance, list, f"{path}: expected array")
            if "maxItems" in schema:
                self.assertLessEqual(
                    len(instance), schema["maxItems"], f"{path}: maxItems"
                )
            item_schema = schema.get("items")
            if isinstance(item_schema, dict):
                for i, v in enumerate(instance):
                    self._walk(v, item_schema, f"{path}[{i}]")
        elif stype == "string":
            self.assertIsInstance(instance, str, f"{path}: expected string")
            if "maxLength" in schema:
                self.assertLessEqual(
                    len(instance), schema["maxLength"], f"{path}: maxLength"
                )
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
            for key in (
                "contract_version",
                "intake_id",
                "sha256",
                "disposed_at",
                "disposition",
            ):
                self.assertIn(key, env)
            self.assertEqual(env["contract_version"], "1.0")

    def test_outcome_enum(self):
        outcomes = {env["disposition"]["outcome"] for env in _all_sample_envelopes()}
        self.assertEqual(
            outcomes,
            {"destroyed", "held", "refused_not_rejected", "refused_hash_mismatch"},
        )

    def test_destroyed_has_destroyed_block_others_do_not(self):
        destroyed = _destroyed_envelope()
        self.assertIn("destroyed", destroyed["disposition"])
        self.assertEqual(
            destroyed["disposition"]["destroyed"]["chamber"], "terminated"
        )
        for env in (
            _held_envelope(),
            _refused_not_rejected_envelope(),
            _refused_hash_mismatch_envelope(),
        ):
            self.assertNotIn("destroyed", env["disposition"])

    def test_report_survives_always_true(self):
        for env in _all_sample_envelopes():
            self.assertIs(env["disposition"]["report_survives"], True)

    def test_hash_verified_is_bool(self):
        for env in _all_sample_envelopes():
            self.assertIsInstance(env["disposition"]["hash_verified"], bool)

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
                        pk,
                        _BANNED_VERDICT_KEYS,
                        f"schema defines a verdict property {pk!r}",
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

    def test_destroyed_conforms(self):
        self._assert_conforms(_destroyed_envelope())

    def test_held_conforms(self):
        self._assert_conforms(_held_envelope())

    def test_refused_not_rejected_conforms(self):
        self._assert_conforms(_refused_not_rejected_envelope())

    def test_refused_hash_mismatch_conforms(self):
        self._assert_conforms(_refused_hash_mismatch_envelope())

    def test_rejects_injected_verdict(self):
        env = _destroyed_envelope()
        env["disposition"]["verdict"] = "malicious"
        errors = list(self.validator.iter_errors(env))
        self.assertTrue(errors, "schema must reject an injected verdict field")

    def test_rejects_bad_outcome(self):
        env = _destroyed_envelope()
        env["disposition"]["outcome"] = "promoted"
        errors = list(self.validator.iter_errors(env))
        self.assertTrue(errors, "schema must reject an out-of-enum outcome")


if __name__ == "__main__":
    unittest.main()
