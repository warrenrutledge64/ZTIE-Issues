"""ZTIE Story 3.3 (RD-038) — contract-conformance for the scoring-result record.

TWO layers (the proven 2.2 -> 3.2 lesson):
  * OFFLINE (always, stdlib): a manual pure-Python conformance walk asserting the
    built results satisfy the contract's load-bearing invariants (required keys,
    allow-listed enums, additionalProperties allow-list at every level, byte/range
    bounds, NO verdict field) + a schema-has-no-verdict-property check.
  * LIVE (pytest, jsonschema): every result validates against
    ``scoring.contract.v1.json``. Skips offline.

The STORED record carries one Hub-internal bookkeeping field
(``evidence_fingerprint``) the contract does not define; the walk validates the
CONTRACT-DEFINED result object built by ``score.build_result`` (no fingerprint — the
handler stamps that separately), so it exercises the exact contract shape.
"""

from __future__ import annotations

import json
import os
import unittest

import score

try:
    from jsonschema import Draft7Validator

    _HAVE_JSONSCHEMA = True
except ImportError:  # offline sandbox
    _HAVE_JSONSCHEMA = False

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "scoring.contract.v1.json")

_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_SHA256 = "a" * 64

_BANNED_VERDICT_KEYS = frozenset(
    {"verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean"}
)


def _scored(v):
    return score.build_score_block(
        status="scored", score=v, rationale="because the evidence shows risk",
        model_id="us.amazon.nova-pro-v1:0", attempts=1, latency_ms=800,
        input_tokens=200, output_tokens=60,
    )


def _err():
    return score.build_score_block(
        status="model_error", status_detail="ThrottlingException",
        model_id="us.amazon.nova-pro-v1:0", attempts=5,
    )


def _unparseable():
    return score.build_score_block(
        status="unparseable", status_detail="no parseable 0-100 score",
        model_id="us.amazon.nova-pro-v1:0", attempts=2, latency_ms=500,
    )


def _skipped():
    return score.build_score_block(status="skipped_no_evidence", status_detail="no static evidence")


def _result(static_b, dynamic_b, combined_b, complete=True):
    return score.build_result(
        intake_id=_INTAKE_ID, sha256=_SHA256, scored_at="2026-09-13T00:05:00Z",
        contract_version="1.0", static_block=static_b, dynamic_block=dynamic_b,
        combined_block=combined_b, combined_complete=complete,
    )


def _all_samples():
    return [
        _result(_scored(20), _scored(85), _scored(70)),          # all scored
        _result(_scored(40), _err(), _scored(50)),               # partial: dynamic errored
        _result(_skipped(), _scored(60), _scored(55), complete=False),  # static absent
        _result(_unparseable(), _unparseable(), _unparseable()), # all unparseable
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
            if "maxItems" in schema:
                self.assertLessEqual(len(instance), schema["maxItems"], f"{path}: maxItems")
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

    def test_all_samples_conform(self):
        for result in _all_samples():
            self._walk(result, self.schema)

    def test_top_level_required_keys(self):
        for result in _all_samples():
            for key in ("contract_version", "intake_id", "sha256", "scored_at",
                        "static", "dynamic", "combined"):
                self.assertIn(key, result)
            self.assertEqual(result["contract_version"], "1.0")

    def test_three_score_blocks_present(self):
        for result in _all_samples():
            for k in ("static", "dynamic", "combined"):
                self.assertIn("status", result[k])

    def test_scored_blocks_have_bounded_score(self):
        r = _all_samples()[0]
        for k in ("static", "dynamic", "combined"):
            self.assertEqual(r[k]["status"], "scored")
            self.assertTrue(0 <= r[k]["score"] <= 100)

    def test_partial_result_is_honest(self):
        r = _all_samples()[1]
        self.assertEqual(r["dynamic"]["status"], "model_error")
        self.assertNotIn("score", r["dynamic"])
        self.assertEqual(r["static"]["status"], "scored")

    def test_no_verdict_field_anywhere(self):
        for result in _all_samples():
            self.assertIsNone(_no_banned_keys(result))

    def test_schema_itself_has_no_verdict_property(self):
        self._assert_no_banned_property(self.schema)

    def _assert_no_banned_property(self, node):
        if isinstance(node, dict):
            props = node.get("properties")
            if isinstance(props, dict):
                for pk in props:
                    self.assertNotIn(pk, _BANNED_VERDICT_KEYS,
                                     f"schema defines a verdict property {pk!r}")
            for v in node.values():
                self._assert_no_banned_property(v)
        elif isinstance(node, list):
            for v in node:
                self._assert_no_banned_property(v)


@unittest.skipUnless(_HAVE_JSONSCHEMA, "jsonschema not available offline")
class TestLiveContractConformance(unittest.TestCase):
    def setUp(self):
        with open(_SCHEMA_PATH, encoding="utf-8") as fh:
            self.validator = Draft7Validator(json.load(fh))

    def _assert_conforms(self, result):
        errors = sorted(self.validator.iter_errors(result), key=str)
        self.assertEqual(errors, [], f"schema errors: {errors}")

    def test_all_samples_conform(self):
        for result in _all_samples():
            self._assert_conforms(result)

    def test_rejects_injected_verdict(self):
        r = _all_samples()[0]
        r["verdict"] = "safe"
        self.assertTrue(list(self.validator.iter_errors(r)))

    def test_rejects_bad_score_status(self):
        r = _all_samples()[0]
        r["static"]["status"] = "approved"
        self.assertTrue(list(self.validator.iter_errors(r)))

    def test_rejects_score_out_of_range(self):
        r = _all_samples()[0]
        r["combined"]["score"] = 101
        self.assertTrue(list(self.validator.iter_errors(r)))

    def test_rejects_missing_score_block(self):
        r = _all_samples()[0]
        del r["combined"]
        self.assertTrue(list(self.validator.iter_errors(r)))


if __name__ == "__main__":
    unittest.main()
