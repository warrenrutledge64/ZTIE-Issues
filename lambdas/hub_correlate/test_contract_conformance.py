"""ZTIE Story 3.2 — contract-conformance for the correlation-result record.

TWO layers, so the loop between the schema-first contract and the code is closed
both live AND offline (the proven 2.2 -> 3.1 lesson):

  * LIVE (pytest, jsonschema installed): every result ``correlate.build_result``
    produces must validate against ``correlation.contract.v1.json``. Skips in the
    INTEGRATIONS_ONLY sandbox (PyPI blocked).

  * OFFLINE (always, stdlib only): a MANUAL pure-Python conformance walk that
    asserts the built results satisfy the contract's load-bearing invariants
    (required keys, allow-listed enums, additionalProperties allow-list at every
    level, byte/length/array bounds, NO verdict field) even when jsonschema is not
    installable, plus a schema-has-no-verdict-property check.

Note: the STORED record carries one Hub-internal bookkeeping field —
``combined_event_fingerprint`` — that the CROSSING contract does not define (it is
not a crossing; it is a Hub-internal derived field). The conformance walk validates
the CONTRACT-DEFINED result object built by ``build_result`` (which does NOT include
the fingerprint — the handler stamps that separately just before the write), so the
walk exercises the exact contract shape.
"""

from __future__ import annotations

import json
import os
import unittest

import correlate

try:
    from jsonschema import Draft7Validator

    _HAVE_JSONSCHEMA = True
except ImportError:  # offline sandbox
    _HAVE_JSONSCHEMA = False

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "correlation.contract.v1.json")

_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_SHA256 = "a" * 64
_CV = "1.0"

_BANNED_VERDICT_KEYS = frozenset(
    {"verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean"}
)


def _correlated_result():
    corr = {
        "summary": "The static open-egress finding is exercised by an outbound connect.",
        "finding_count": 2,
        "highest_correlation_severity": "high",
        "findings": [
            {"kind": "correlated", "severity": "high", "title": "Exfil path exercised",
             "detail": "matches observed connect", "static_refs": ["SG-open-egress"],
             "behavioral_refs": ["connect(1.2.3.4:443)"]},
            {"kind": "static_only", "severity": "low", "title": "Unused permissive rule"},
        ],
    }
    return correlate.build_result(
        intake_id=_INTAKE_ID, sha256=_SHA256, correlated_at="2026-09-12T00:05:00Z",
        contract_version=_CV, status="correlated", model_id="us.amazon.nova-pro-v1:0",
        attempts=1, latency_ms=920, input_tokens=800, output_tokens=210,
        truncated=False, combined_complete=True, combined_event_contract_version="1.0",
        correlation=corr,
    )


def _model_error_result():
    return correlate.build_result(
        intake_id=_INTAKE_ID, sha256=_SHA256, correlated_at="2026-09-12T00:05:00Z",
        contract_version=_CV, status="model_error", model_id="us.amazon.nova-pro-v1:0",
        attempts=5, status_detail="ThrottlingException after 5 attempt(s)",
        combined_complete=True, correlation=None,
    )


def _unparseable_result():
    return correlate.build_result(
        intake_id=_INTAKE_ID, sha256=_SHA256, correlated_at="2026-09-12T00:05:00Z",
        contract_version=_CV, status="unparseable", model_id="us.amazon.nova-pro-v1:0",
        attempts=2, status_detail="model response could not be parsed into the contract",
        combined_complete=False, correlation=None,
    )


def _skipped_result():
    return correlate.build_result(
        intake_id=_INTAKE_ID, sha256=_SHA256, correlated_at="2026-09-12T00:05:00Z",
        contract_version=_CV, status="skipped_no_signals", combined_complete=False,
    )


def _all_samples():
    return [_correlated_result(), _model_error_result(), _unparseable_result(), _skipped_result()]


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
        if "const" in schema:
            self.assertEqual(instance, schema["const"], f"{path}: {instance!r} != const")

    def test_all_samples_conform(self):
        for result in _all_samples():
            self._walk(result, self.schema)

    def test_top_level_required_keys(self):
        for result in _all_samples():
            for key in ("contract_version", "intake_id", "sha256", "correlated_at", "status"):
                self.assertIn(key, result)
            self.assertEqual(result["contract_version"], "1.0")

    def test_status_enum(self):
        statuses = {r["status"] for r in _all_samples()}
        self.assertEqual(
            statuses, {"correlated", "model_error", "unparseable", "skipped_no_signals"}
        )

    def test_only_correlated_has_correlation(self):
        self.assertIn("correlation", _correlated_result())
        self.assertNotIn("correlation", _model_error_result())
        self.assertNotIn("correlation", _unparseable_result())
        self.assertNotIn("correlation", _skipped_result())

    def test_attempts_recorded_for_retry_inspection(self):
        self.assertEqual(_model_error_result()["attempts"], 5)
        self.assertEqual(_correlated_result()["attempts"], 1)

    def test_no_verdict_field_anywhere(self):
        for result in _all_samples():
            offending = _no_banned_keys(result)
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
    """Live jsonschema validation against the exact contract 3.3 will consume."""

    def setUp(self):
        with open(_SCHEMA_PATH, encoding="utf-8") as fh:
            self.validator = Draft7Validator(json.load(fh))

    def _assert_conforms(self, result):
        errors = sorted(self.validator.iter_errors(result), key=str)
        self.assertEqual(errors, [], f"schema errors: {errors}")

    def test_correlated_conforms(self):
        self._assert_conforms(_correlated_result())

    def test_model_error_conforms(self):
        self._assert_conforms(_model_error_result())

    def test_unparseable_conforms(self):
        self._assert_conforms(_unparseable_result())

    def test_skipped_conforms(self):
        self._assert_conforms(_skipped_result())

    def test_rejects_injected_verdict(self):
        result = _correlated_result()
        result["verdict"] = "safe"
        errors = list(self.validator.iter_errors(result))
        self.assertTrue(errors, "schema must reject an injected verdict field")

    def test_rejects_bad_status(self):
        result = _correlated_result()
        result["status"] = "approved"
        errors = list(self.validator.iter_errors(result))
        self.assertTrue(errors, "schema must reject an out-of-enum status")

    def test_rejects_bad_finding_kind(self):
        result = _correlated_result()
        result["correlation"]["findings"][0]["kind"] = "malicious"
        errors = list(self.validator.iter_errors(result))
        self.assertTrue(errors, "schema must reject an out-of-enum finding kind")


if __name__ == "__main__":
    unittest.main()
