"""ZTIE Story 3.3 — contract-conformance for the synthesis-result record.

TWO layers, so the loop between the schema-first contract and the code is closed
both live AND offline (the proven 2.2 -> 3.2 lesson):

  * LIVE (pytest, jsonschema installed): every result ``synthesize.build_result``
    produces must validate against ``synthesis.contract.v1.json``. Skips in the
    INTEGRATIONS_ONLY sandbox (PyPI blocked).

  * OFFLINE (always, stdlib only): a MANUAL pure-Python conformance walk that
    asserts the built results satisfy the contract's load-bearing invariants
    (required keys, allow-listed enums, additionalProperties allow-list at every
    level, byte/length/array bounds, NO verdict field) even when jsonschema is not
    installable, plus a schema-has-no-verdict-property check.

Note: the STORED record carries one Hub-internal bookkeeping field —
``correlation_fingerprint`` — that the contract does not define (it is a
Hub-internal derived field, not part of the contract). The conformance walk
validates the CONTRACT-DEFINED result object built by ``build_result`` (which does
NOT include the fingerprint — the handler stamps that separately just before the
write), so the walk exercises the exact contract shape.
"""

from __future__ import annotations

import json
import os
import unittest

import synthesize

try:
    from jsonschema import Draft7Validator

    _HAVE_JSONSCHEMA = True
except ImportError:  # offline sandbox
    _HAVE_JSONSCHEMA = False

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "synthesis.contract.v1.json")

_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_SHA256 = "a" * 64
_CV = "1.0"

_BANNED_VERDICT_KEYS = frozenset(
    {"verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean"}
)


def _finding(kind, severity="medium", title="t", **extra):
    f = {"kind": kind, "severity": severity, "title": title}
    f.update(extra)
    return f


def _correlation_result(findings, *, status="correlated", combined_complete=True):
    result = {
        "contract_version": "1.0",
        "intake_id": _INTAKE_ID,
        "sha256": _SHA256,
        "correlated_at": "2026-09-12T00:05:00Z",
        "status": status,
        "combined_complete": combined_complete,
    }
    if status == "correlated":
        result["correlation"] = {
            "summary": "s",
            "finding_count": len(findings),
            "findings": findings,
        }
    return result


def _build(payload, *, combined_complete=True):
    return synthesize.build_result(
        intake_id=_INTAKE_ID,
        sha256=_SHA256,
        synthesized_at="2026-09-12T01:00:00Z",
        contract_version=_CV,
        payload=payload,
        correlation_contract_version="1.0",
        combined_complete=combined_complete,
    )


def _synthesized_result():
    corr = _correlation_result(
        [
            _finding("static_only", severity="high", title="Permissive rule never used",
                     static_refs=["SG-open"], detail="static-only"),
            _finding("correlated", severity="medium", title="Exec matched"),
            _finding("dynamic_only", severity="low", title="Unexpected connect",
                     behavioral_refs=["connect(1.2.3.4)"]),
            _finding("contradiction", severity="critical", title="Flagged but unused"),
        ]
    )
    return _build(synthesize.synthesize(corr, combined_complete=True))


def _no_correlation_result():
    return _build(synthesize.synthesize({"status": "model_error"}))


def _skipped_result():
    return _build(synthesize.synthesize(_correlation_result([])))


def _coverage_result():
    corr = _correlation_result([_finding("correlated", title="a")], combined_complete=False)
    return _build(synthesize.synthesize(corr, combined_complete=False), combined_complete=False)


def _all_samples():
    return [_synthesized_result(), _no_correlation_result(), _skipped_result(), _coverage_result()]


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
            for key in ("contract_version", "intake_id", "sha256", "synthesized_at", "status"):
                self.assertIn(key, result)
            self.assertEqual(result["contract_version"], "1.0")

    def test_status_enum(self):
        statuses = {r["status"] for r in _all_samples()}
        self.assertTrue(statuses <= {"synthesized", "no_correlation", "skipped_no_findings"})
        self.assertIn("synthesized", statuses)
        self.assertIn("no_correlation", statuses)
        self.assertIn("skipped_no_findings", statuses)

    def test_only_synthesized_has_synthesis(self):
        self.assertIn("synthesis", _synthesized_result())
        self.assertNotIn("synthesis", _no_correlation_result())
        self.assertNotIn("synthesis", _skipped_result())

    def test_accuracy_and_gaps_present_when_synthesized(self):
        synth = _synthesized_result()["synthesis"]
        self.assertIn("accuracy", synth)
        self.assertIn("gaps", synth)
        self.assertIn("candidate_false_positives", synth["accuracy"])
        self.assertIn("items", synth["gaps"])

    def test_coverage_gap_recorded_for_incomplete(self):
        gaps = _coverage_result()["synthesis"]["gaps"]
        self.assertIn("coverage", [g["gap_type"] for g in gaps["items"]])

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
    """Live jsonschema validation against the exact contract 3.4 will consume."""

    def setUp(self):
        with open(_SCHEMA_PATH, encoding="utf-8") as fh:
            self.validator = Draft7Validator(json.load(fh))

    def _assert_conforms(self, result):
        errors = sorted(self.validator.iter_errors(result), key=str)
        self.assertEqual(errors, [], f"schema errors: {errors}")

    def test_synthesized_conforms(self):
        self._assert_conforms(_synthesized_result())

    def test_no_correlation_conforms(self):
        self._assert_conforms(_no_correlation_result())

    def test_skipped_conforms(self):
        self._assert_conforms(_skipped_result())

    def test_coverage_conforms(self):
        self._assert_conforms(_coverage_result())

    def test_rejects_injected_verdict(self):
        result = _synthesized_result()
        result["verdict"] = "safe"
        errors = list(self.validator.iter_errors(result))
        self.assertTrue(errors, "schema must reject an injected verdict field")

    def test_rejects_bad_status(self):
        result = _synthesized_result()
        result["status"] = "approved"
        errors = list(self.validator.iter_errors(result))
        self.assertTrue(errors, "schema must reject an out-of-enum status")

    def test_rejects_bad_gap_type(self):
        result = _synthesized_result()
        result["synthesis"]["gaps"]["items"][0]["gap_type"] = "malicious"
        errors = list(self.validator.iter_errors(result))
        self.assertTrue(errors, "schema must reject an out-of-enum gap_type")

    def test_rejects_accuracy_score_out_of_range(self):
        result = _synthesized_result()
        result["synthesis"]["accuracy"]["accuracy_score"] = 101
        errors = list(self.validator.iter_errors(result))
        self.assertTrue(errors, "schema must reject accuracy_score > 100")


if __name__ == "__main__":
    unittest.main()
