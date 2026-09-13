"""ZTIE Story 4.2 (RD-042) — contract-conformance for the dashboard payload.

TWO layers (the proven 2.2 -> 4.1 lesson):
  * OFFLINE (always, stdlib): a manual pure-Python conformance walk asserting the
    assembled dashboard payloads (both `view=intake` and `view=fleet`) satisfy the
    contract's load-bearing invariants (required keys, allow-listed enums,
    additionalProperties allow-list at every level, byte/range/array bounds) + the
    RD-040/RD-042 verdict-safety checks:
      - a payload MAY carry an ADVISORY `recommended_verdict` (allow-listed to
        PASS/FAIL/INCONCLUSIVE) alongside `decision: pending` + `advisory: true`;
      - a payload does NOT define/carry a bare EFFECTIVE verdict key (`verdict` / `safe` /
        `approved` / `forward` / `malicious` / `pass_fail` / `clean`), and every human
        `decision` is `pending`.
  * LIVE (pytest/jsonschema): every payload validates against
    ``dashboard.contract.v1.json``. Skips offline.

Note: the per-intake `intake.status` block is an OPAQUE object here — it is the Story 4.1
status read-model, validated separately by ``status.contract.v1``. This contract declares
it `type: object` (no re-declared internals), so the walk only checks it is a dict.
"""

from __future__ import annotations

import json
import os
import unittest

import dashboard

try:
    from jsonschema import Draft7Validator

    _HAVE_JSONSCHEMA = True
except ImportError:  # offline sandbox
    _HAVE_JSONSCHEMA = False

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "dashboard.contract.v1.json")

_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_INTAKE_ID_2 = "7f1e2d3c-4b5a-4c6d-8e9f-0a1b2c3d4e5f"
_SHA256 = "a" * 64
_ASSEMBLED_AT = "2026-09-14T00:00:00Z"

_ALLOWED_VERDICT_KEY = "recommended_verdict"
_BANNED_EFFECTIVE_KEYS = frozenset(
    {"verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean"}
)


def _scoring(*, static=70, dynamic=30, combined=55):
    def _block(val):
        if isinstance(val, str):
            return {"status": val}
        return {"status": "scored", "score": val}

    return {
        "static": _block(static),
        "dynamic": _block(dynamic),
        "combined": _block(combined),
        "rubric_version": "1.0",
    }


def _rem(*, contradiction=0, highest_gap="high"):
    return {
        "status": "assessed",
        "assessment": {
            "highest_gap_severity": highest_gap,
            "counts": {
                "detailed_finding_count": 1,
                "candidate_false_positive_count": 1,
                "gap_count": 1,
                "remediation_count": 2,
                "contradiction": contradiction,
            },
        },
    }


def _verdict(rv="INCONCLUSIVE"):
    return {
        "status": "recommended",
        "human_decision": "pending",
        "rubric_version": "1.0",
        "recommended_verdict": rv,
        "recommendation_basis": {"driver": "combined_score", "summary": "advisory only"},
    }


def _item(intake_id=_INTAKE_ID, sha256=_SHA256, **parts):
    it = {"intake_id": intake_id, "sha256": sha256, "status": "RECEIVED"}
    it.update(parts)
    return it


def _intake_view(item):
    return dashboard.build_intake_view(
        item,
        intake_id=item["intake_id"],
        sha256=item["sha256"],
        assembled_at=_ASSEMBLED_AT,
        contract_version="1.0",
        status_contract_version="1.0",
    )


def _fleet_view(items, **kw):
    return dashboard.build_fleet_view(
        items,
        assembled_at=_ASSEMBLED_AT,
        contract_version="1.0",
        status_contract_version="1.0",
        **kw,
    )


def _all_samples():
    return [
        # per-intake: bare received
        _intake_view(_item()),
        # per-intake: scored only
        _intake_view(_item(combined_event={}, correlation_result={}, scoring_result=_scoring())),
        # per-intake: fully recommended PASS
        _intake_view(
            _item(
                combined_event={},
                correlation_result={},
                scoring_result=_scoring(combined=10),
                remediation_result=_rem(highest_gap="none"),
                verdict_result=_verdict("PASS"),
            )
        ),
        # per-intake: recommended FAIL (critical tier)
        _intake_view(
            _item(
                combined_event={},
                correlation_result={},
                scoring_result=_scoring(combined=90),
                remediation_result=_rem(),
                verdict_result=_verdict("FAIL"),
            )
        ),
        # per-intake: INCONCLUSIVE with contradiction
        _intake_view(
            _item(
                combined_event={},
                correlation_result={},
                scoring_result=_scoring(),
                remediation_result=_rem(contradiction=1),
                verdict_result=_verdict("INCONCLUSIVE"),
            )
        ),
        # fleet: empty
        _fleet_view([]),
        # fleet: mixed
        _fleet_view(
            [
                _item(
                    received_at="2026-09-14T01:00:00Z",
                    scoring_result=_scoring(combined=90),
                    verdict_result=_verdict("FAIL"),
                ),
                _item(intake_id=_INTAKE_ID_2, received_at="2026-09-14T00:00:00Z", scoring_result=_scoring(combined=10)),
            ]
        ),
        # fleet: truncated
        _fleet_view([_item()], more_available=True),
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
        for view in _all_samples():
            self._walk(view, self.schema)

    def test_top_level_required_keys(self):
        for view in _all_samples():
            for key in ("contract_version", "view", "assembled_at"):
                self.assertIn(key, view)
            self.assertEqual(view["contract_version"], "1.0")
            self.assertIn(view["view"], ("intake", "fleet"))

    def test_action_advisory_and_pending(self):
        for view in _all_samples():
            if view["view"] != "intake":
                continue
            action = view["intake"]["action"]
            self.assertEqual(action["decision"], "pending")
            self.assertIs(action["advisory"], True)
            if "recommended_verdict" in action:
                self.assertIn(action["recommended_verdict"], ("PASS", "FAIL", "INCONCLUSIVE"))

    def test_fleet_rows_decision_pending(self):
        for view in _all_samples():
            if view["view"] != "fleet":
                continue
            for row in view["fleet"]["intakes"]:
                self.assertEqual(row["decision"], "pending")

    def test_no_effective_verdict_key_in_payload(self):
        for view in _all_samples():
            self.assertIsNone(_no_banned_keys(view))

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

    def test_schema_action_decision_only_pending(self):
        hd = self.schema["properties"]["intake"]["properties"]["action"]["properties"][
            "decision"
        ]
        self.assertEqual(hd["enum"], ["pending"])

    def test_schema_defines_recommended_verdict_enum(self):
        rv = self.schema["properties"]["intake"]["properties"]["action"]["properties"][
            _ALLOWED_VERDICT_KEY
        ]
        self.assertEqual(sorted(rv["enum"]), ["FAIL", "INCONCLUSIVE", "PASS"])

    def test_both_views_present_in_samples(self):
        views = {v["view"] for v in _all_samples()}
        self.assertIn("intake", views)
        self.assertIn("fleet", views)


@unittest.skipUnless(_HAVE_JSONSCHEMA, "jsonschema not available offline")
class TestLiveContractConformance(unittest.TestCase):
    def setUp(self):
        with open(_SCHEMA_PATH, encoding="utf-8") as fh:
            self.validator = Draft7Validator(json.load(fh))

    def _assert_conforms(self, view):
        errors = sorted(self.validator.iter_errors(view), key=str)
        self.assertEqual(errors, [], f"schema errors: {errors}")

    def test_all_samples_conform(self):
        for view in _all_samples():
            self._assert_conforms(view)

    def test_rejects_bad_recommended_verdict(self):
        v = _all_samples()[3]  # FAIL intake
        v["intake"]["action"]["recommended_verdict"] = "MAYBE"
        self.assertTrue(list(self.validator.iter_errors(v)))

    def test_rejects_non_pending_decision(self):
        v = _all_samples()[3]
        v["intake"]["action"]["decision"] = "accepted"
        self.assertTrue(list(self.validator.iter_errors(v)))

    def test_rejects_injected_effective_verdict(self):
        v = _all_samples()[3]
        v["verdict"] = "safe"
        self.assertTrue(list(self.validator.iter_errors(v)))

    def test_rejects_bad_view(self):
        v = _all_samples()[0]
        v["view"] = "safe"
        self.assertTrue(list(self.validator.iter_errors(v)))

    def test_rejects_bad_threat_tier(self):
        v = _all_samples()[3]
        v["intake"]["threat"]["tier"] = "extreme"
        self.assertTrue(list(self.validator.iter_errors(v)))

    def test_rejects_missing_required_top_level(self):
        v = _all_samples()[0]
        del v["view"]
        self.assertTrue(list(self.validator.iter_errors(v)))

    def test_rejects_fleet_row_score_out_of_range(self):
        v = _all_samples()[6]  # fleet mixed
        v["fleet"]["metrics"]["window_count"] = -1
        self.assertTrue(list(self.validator.iter_errors(v)))


if __name__ == "__main__":
    unittest.main()
