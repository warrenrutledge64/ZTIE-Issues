"""ZTIE Story 3.5 (RD-040) — contract-conformance for the verdict-result record.

TWO layers (the proven 2.2 -> 3.4 lesson):
  * OFFLINE (always, stdlib): a manual pure-Python conformance walk asserting the
    built results satisfy the contract's load-bearing invariants (required keys,
    allow-listed enums, additionalProperties allow-list at every level, byte/range
    bounds) + the INVERTED verdict checks (this is the FIRST verdict-bearing contract):
      - the schema DEFINES `recommended_verdict` (allow-listed to PASS/FAIL/
        INCONCLUSIVE) and the record CARRIES it — the opposite of the 3.1-3.4
        no-verdict-property tests, which stay intact for THEIR records.
      - the schema does NOT define, and the record does NOT carry, a bare EFFECTIVE
        verdict key (`verdict` / `safe` / `approved` / `forward` / `malicious` /
        `pass_fail` / `clean`) or any field asserting the human's actual selection —
        the recommendation is advisory and human_decision is always `pending`.
  * LIVE (pytest/jsonschema): every result validates against
    ``verdict.contract.v1.json``. Skips offline.

The STORED record carries one Hub-internal bookkeeping field (``evidence_fingerprint``)
the contract does not define; the walk validates the CONTRACT-DEFINED result object
built by ``verdict.build_result`` (no fingerprint — the handler stamps that separately),
so it exercises the exact contract shape.
"""

from __future__ import annotations

import json
import os
import unittest

import verdict

try:
    from jsonschema import Draft7Validator

    _HAVE_JSONSCHEMA = True
except ImportError:  # offline sandbox
    _HAVE_JSONSCHEMA = False

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "verdict.contract.v1.json")

_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_SHA256 = "a" * 64

# The advisory field 3.5's OWN contract legitimately carries.
_ALLOWED_VERDICT_KEY = "recommended_verdict"
# The EFFECTIVE / acted-upon verdict keys that must NEVER appear (a bare `verdict` here
# would be mistakable for the enforced decision; the rest are the shared 3.1-3.4 banned
# set). `recommended_verdict` is deliberately NOT in this set.
_BANNED_EFFECTIVE_KEYS = frozenset(
    {"verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean"}
)


def _scoring(*, static=None, dynamic=None, combined=None, complete=True):
    def _block(val):
        if val is None:
            return {"status": "skipped_no_evidence"}
        if isinstance(val, str):
            return {"status": val}
        return {"status": "scored", "score": val}

    return {
        "static": _block(static),
        "dynamic": _block(dynamic),
        "combined": _block(combined),
        "combined_complete": complete,
        "rubric_version": "1.0",
    }


def _rem(*, status="assessed", gaps=None, contradiction=0, complete=True):
    return {
        "status": status,
        "combined_complete": complete,
        "assessment": {"gaps": gaps or [], "counts": {"contradiction": contradiction}},
    }


def _gap(gap_type, severity, title="g"):
    return {"gap_type": gap_type, "severity": severity, "title": title}


def _result(payload):
    return verdict.build_result(
        intake_id=_INTAKE_ID,
        sha256=_SHA256,
        recommended_at="2026-09-13T00:05:00Z",
        contract_version="1.0",
        payload=payload,
        rubric_version="1.0",
    )


def _all_samples():
    return [
        # PASS: low combined, complete, no override.
        _result(verdict.derive(_scoring(static=90, dynamic=90, combined=10), _rem())),
        # FAIL: high combined, complete, no override.
        _result(verdict.derive(_scoring(static=0, dynamic=0, combined=90), _rem())),
        # INCONCLUSIVE by score band.
        _result(verdict.derive(_scoring(static=0, dynamic=0, combined=50), _rem())),
        # INCONCLUSIVE forced by contradiction (score would be FAIL).
        _result(
            verdict.derive(
                _scoring(static=90, dynamic=90, combined=90),
                _rem(gaps=[_gap("contradiction", "high")], contradiction=1),
            )
        ),
        # INCONCLUSIVE forced by incomplete evidence (partial scoring).
        _result(
            verdict.derive(_scoring(static="model_error", dynamic=10, combined=10), _rem())
        ),
        # no_scores (3.3 not landed) -> INCONCLUSIVE.
        _result(verdict.derive(None, _rem())),
        # high-severity gap but low combined -> PASS with gap as context.
        _result(
            verdict.derive(
                _scoring(static=10, dynamic=10, combined=10),
                _rem(gaps=[_gap("dynamic_unexplained", "high")]),
            )
        ),
    ]


def _no_banned_keys(obj):
    if isinstance(obj, dict):
        for k, val in obj.items():
            if k in _BANNED_EFFECTIVE_KEYS:
                return k
            deeper = _no_banned_keys(val)
            if deeper:
                return f"{k}.{deeper}"
    elif isinstance(obj, list):
        for i, val in enumerate(obj):
            deeper = _no_banned_keys(val)
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
            for k, val in instance.items():
                if k in props:
                    self._walk(val, props[k], f"{path}.{k}")
        elif stype == "array":
            self.assertIsInstance(instance, list, f"{path}: expected array")
            if "maxItems" in schema:
                self.assertLessEqual(len(instance), schema["maxItems"], f"{path}: maxItems")
            item_schema = schema.get("items")
            if isinstance(item_schema, dict):
                for i, val in enumerate(instance):
                    self._walk(val, item_schema, f"{path}[{i}]")
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
            for key in ("contract_version", "intake_id", "sha256", "recommended_at",
                        "status", "recommended_verdict", "human_decision"):
                self.assertIn(key, result)
            self.assertEqual(result["contract_version"], "1.0")

    def test_recommended_verdict_present_and_allowlisted(self):
        # INVERTED vs the 3.1-3.4 no-verdict tests: 3.5's record MUST carry the advisory
        # recommended_verdict, allow-listed to exactly PASS/FAIL/INCONCLUSIVE.
        for result in _all_samples():
            self.assertIn(_ALLOWED_VERDICT_KEY, result)
            self.assertIn(result[_ALLOWED_VERDICT_KEY], ("PASS", "FAIL", "INCONCLUSIVE"))

    def test_schema_defines_recommended_verdict_enum(self):
        rv = self.schema["properties"]["recommended_verdict"]
        self.assertEqual(sorted(rv["enum"]), ["FAIL", "INCONCLUSIVE", "PASS"])

    def test_human_decision_always_pending(self):
        for result in _all_samples():
            self.assertEqual(result["human_decision"], "pending")

    def test_schema_human_decision_only_pending(self):
        hd = self.schema["properties"]["human_decision"]
        self.assertEqual(hd["enum"], ["pending"])

    def test_no_effective_verdict_key_in_record(self):
        # The record may carry recommended_verdict but NEVER a bare effective verdict
        # key or the human's actual selection.
        for result in _all_samples():
            self.assertIsNone(_no_banned_keys(result))

    def test_schema_has_no_effective_verdict_property(self):
        self._assert_no_banned_property(self.schema)

    def _assert_no_banned_property(self, node):
        if isinstance(node, dict):
            props = node.get("properties")
            if isinstance(props, dict):
                for pk in props:
                    self.assertNotIn(
                        pk,
                        _BANNED_EFFECTIVE_KEYS,
                        f"schema defines an effective-verdict property {pk!r}",
                    )
            for val in node.values():
                self._assert_no_banned_property(val)
        elif isinstance(node, list):
            for val in node:
                self._assert_no_banned_property(val)

    def test_inconclusive_when_forced(self):
        # The contradiction + partial-scoring samples must be INCONCLUSIVE.
        contradiction_sample = _all_samples()[3]
        partial_sample = _all_samples()[4]
        self.assertEqual(contradiction_sample["recommended_verdict"], "INCONCLUSIVE")
        self.assertEqual(partial_sample["recommended_verdict"], "INCONCLUSIVE")

    def test_pass_and_fail_samples(self):
        self.assertEqual(_all_samples()[0]["recommended_verdict"], "PASS")
        self.assertEqual(_all_samples()[1]["recommended_verdict"], "FAIL")

    def test_basis_present_when_recommended(self):
        pass_sample = _all_samples()[0]
        self.assertIn("recommendation_basis", pass_sample)
        self.assertIn("driver", pass_sample["recommendation_basis"])
        self.assertIn("summary", pass_sample["recommendation_basis"])


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

    def test_rejects_bad_recommended_verdict(self):
        r = _all_samples()[0]
        r["recommended_verdict"] = "MAYBE"
        self.assertTrue(list(self.validator.iter_errors(r)))

    def test_rejects_non_pending_human_decision(self):
        # The contract permits ONLY 'pending' — 3.5 can never assert a made decision.
        r = _all_samples()[0]
        r["human_decision"] = "accepted"
        self.assertTrue(list(self.validator.iter_errors(r)))

    def test_rejects_injected_effective_verdict(self):
        r = _all_samples()[0]
        r["verdict"] = "safe"
        self.assertTrue(list(self.validator.iter_errors(r)))

    def test_rejects_bad_status(self):
        r = _all_samples()[0]
        r["status"] = "malicious"
        self.assertTrue(list(self.validator.iter_errors(r)))

    def test_rejects_missing_required_top_level(self):
        r = _all_samples()[0]
        del r["recommended_verdict"]
        self.assertTrue(list(self.validator.iter_errors(r)))

    def test_rejects_combined_score_out_of_range(self):
        r = _all_samples()[1]  # FAIL sample has a combined_score in the basis
        r["recommendation_basis"]["combined_score"] = 101
        self.assertTrue(list(self.validator.iter_errors(r)))


if __name__ == "__main__":
    unittest.main()
