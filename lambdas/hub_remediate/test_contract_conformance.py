"""ZTIE Story 3.4 (RD-039) — contract-conformance for the remediation-result record.

TWO layers (the proven 2.2 -> 3.3 lesson):
  * OFFLINE (always, stdlib): a manual pure-Python conformance walk asserting the
    built results satisfy the contract's load-bearing invariants (required keys,
    allow-listed enums, additionalProperties allow-list at every level, byte/range
    bounds, NO verdict field) + a schema-has-no-verdict-property check.
  * LIVE (pytest/jsonschema): every result validates against
    ``remediation.contract.v1.json``. Skips offline.

The STORED record carries one Hub-internal bookkeeping field
(``evidence_fingerprint``) the contract does not define; the walk validates the
CONTRACT-DEFINED result object built by ``remediate.build_result`` (no fingerprint —
the handler stamps that separately), so it exercises the exact contract shape.
"""

from __future__ import annotations

import json
import os
import unittest

import remediate

try:
    from jsonschema import Draft7Validator

    _HAVE_JSONSCHEMA = True
except ImportError:  # offline sandbox
    _HAVE_JSONSCHEMA = False

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "remediation.contract.v1.json")

_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_SHA256 = "a" * 64

_BANNED_VERDICT_KEYS = frozenset(
    {"verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean"}
)


def _scoring(*, static=None, dynamic=None, combined=None, complete=True):
    def _block(v):
        if v is None:
            return {"status": "skipped_no_evidence"}
        if isinstance(v, str):
            return {"status": v}
        return {"status": "scored", "score": v}

    return {
        "static": _block(static),
        "dynamic": _block(dynamic),
        "combined": _block(combined),
        "combined_complete": complete,
        "rubric_version": "1.0",
    }


def _correlation(findings, status="correlated"):
    result = {"status": status}
    if status == "correlated":
        result["correlation"] = {"summary": "s", "findings": findings}
    return result


def _f(kind, severity, title="t", **extra):
    return {"kind": kind, "severity": severity, "title": title, **extra}


def _result(payload, *, complete=True):
    return remediate.build_result(
        intake_id=_INTAKE_ID,
        sha256=_SHA256,
        assessed_at="2026-09-13T00:05:00Z",
        contract_version="1.0",
        payload=payload,
        rubric_version="1.0",
        combined_complete=complete,
    )


def _all_samples():
    return [
        # Rich assessed result: findings of every kind, all scored, complete.
        _result(
            remediate.assess(
                _scoring(static=70, dynamic=85, combined=80),
                _correlation(
                    [
                        _f("correlated", "high", "conf", static_refs=["S1"],
                           behavioral_refs=["B1"]),
                        _f("static_only", "medium", "flag"),
                        _f("dynamic_only", "critical", "weird"),
                        _f("contradiction", "low", "disagree"),
                    ]
                ),
                combined_complete=True,
            )
        ),
        # Partial scoring (dynamic errored) + incomplete -> coverage gap.
        _result(
            remediate.assess(
                _scoring(static=40, dynamic="model_error", combined=50, complete=False),
                _correlation([_f("static_only", "high", "x")]),
                combined_complete=False,
            ),
            complete=False,
        ),
        # Scores but zero findings -> assessed, empty remediations.
        _result(
            remediate.assess(
                _scoring(static=20, dynamic=15, combined=18), _correlation([])
            )
        ),
        # no_scores (3.3 not landed).
        _result(remediate.assess(None, _correlation([_f("static_only", "high")]))),
        # skipped_no_evidence (no lane scored, no findings).
        _result(
            remediate.assess(
                _scoring(static="model_error", dynamic="unparseable",
                         combined="model_error"),
                _correlation([]),
            )
        ),
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
            for key in ("contract_version", "intake_id", "sha256", "assessed_at",
                        "status"):
                self.assertIn(key, result)
            self.assertEqual(result["contract_version"], "1.0")

    def test_assessed_carries_assessment(self):
        rich = _all_samples()[0]
        self.assertEqual(rich["status"], "assessed")
        self.assertIn("assessment", rich)
        a = rich["assessment"]
        for key in ("summary", "scores", "counts", "prioritized_remediations"):
            self.assertIn(key, a)

    def test_remediations_ranked_contiguously(self):
        rich = _all_samples()[0]
        rems = rich["assessment"]["prioritized_remediations"]
        self.assertEqual([r["rank"] for r in rems], list(range(1, len(rems) + 1)))

    def test_migrated_lists_present(self):
        rich = _all_samples()[0]
        a = rich["assessment"]
        self.assertIn("candidate_false_positives", a)
        self.assertIn("gaps", a)
        self.assertIn("detailed_findings", a)

    def test_coverage_gap_on_incomplete(self):
        partial = _all_samples()[1]
        gap_types = {g["gap_type"] for g in partial["assessment"]["gaps"]}
        self.assertIn("coverage", gap_types)

    def test_non_assessed_has_no_assessment(self):
        no_scores = _all_samples()[3]
        self.assertEqual(no_scores["status"], "no_scores")
        self.assertNotIn("assessment", no_scores)

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

    def test_rejects_bad_status(self):
        r = _all_samples()[0]
        r["status"] = "malicious"
        self.assertTrue(list(self.validator.iter_errors(r)))

    def test_rejects_bad_remediation_priority(self):
        r = _all_samples()[0]
        r["assessment"]["prioritized_remediations"][0]["priority"] = "reject"
        self.assertTrue(list(self.validator.iter_errors(r)))

    def test_rejects_score_out_of_range(self):
        r = _all_samples()[0]
        r["assessment"]["scores"]["static"]["score"] = 101
        self.assertTrue(list(self.validator.iter_errors(r)))

    def test_rejects_missing_required_top_level(self):
        r = _all_samples()[0]
        del r["assessed_at"]
        self.assertTrue(list(self.validator.iter_errors(r)))


if __name__ == "__main__":
    unittest.main()
