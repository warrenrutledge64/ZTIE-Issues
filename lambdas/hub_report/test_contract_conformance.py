"""ZTIE Story 4.5 (RD-045) — contract-conformance for the per-execution report payload.

TWO layers (the proven 2.2 -> 4.2 lesson):
  * OFFLINE (always, stdlib): a manual pure-Python conformance walk asserting the
    assembled report payload satisfies the contract's load-bearing invariants (required
    keys, allow-listed enums, additionalProperties allow-list at every level, byte/range/
    array bounds) + the RD-040/RD-045 verdict-safety checks:
      - the payload MAY carry an ADVISORY `recommended_verdict` (allow-listed to
        PASS/FAIL/INCONCLUSIVE) alongside `decision: pending` + `advisory: true`;
      - the payload does NOT define/carry a bare EFFECTIVE verdict key (`verdict` / `safe`
        / `approved` / `forward` / `malicious` / `pass_fail` / `clean`), and the human
        `decision` is `pending`.
  * LIVE (pytest/jsonschema): the payload validates against ``report.contract.v1.json``.
    Skips offline (jsonschema not installed in the INTEGRATIONS_ONLY sandbox).
"""

from __future__ import annotations

import json
import os
import unittest

import report

try:
    from jsonschema import Draft7Validator

    _HAVE_JSONSCHEMA = True
except ImportError:  # offline sandbox
    _HAVE_JSONSCHEMA = False

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "report.contract.v1.json")

_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_SHA256 = "a" * 64
_ASSEMBLED_AT = "2026-09-14T00:00:00Z"

_ALLOWED_VERDICT_KEY = "recommended_verdict"
_BANNED_EFFECTIVE_KEYS = frozenset(
    {"verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean"}
)


def _full_item():
    return {
        "intake_id": _INTAKE_ID,
        "sha256": _SHA256,
        "status": "RECEIVED",
        "received_at": "2026-09-13T16:00:00Z",
        "combined_event": {},
        "correlation_result": {
            "status": "correlated",
            "correlation": {
                "summary": "corr",
                "highest_correlation_severity": "high",
                "finding_count": 1,
                "findings": [
                    {"kind": "correlated", "severity": "high", "title": "t",
                     "detail": "d", "static_refs": ["S1"], "behavioral_refs": ["b1"]}
                ],
            },
        },
        "scoring_result": {
            "static": {"status": "scored", "score": 50},
            "dynamic": {"status": "scored", "score": 30},
            "combined": {"status": "scored", "score": 70},
            "rubric_version": "1.0",
        },
        "remediation_result": {
            "status": "assessed",
            "assessment": {
                "summary": "s",
                "highest_finding_severity": "high",
                "highest_gap_severity": "high",
                "counts": {"detailed_finding_count": 1, "candidate_false_positive_count": 1,
                           "gap_count": 1, "remediation_count": 1, "contradiction": 0},
                "detailed_findings": [
                    {"kind": "correlated", "severity": "high", "title": "t", "detail": "d",
                     "static_refs": ["S1"], "behavioral_refs": ["b1"]}
                ],
                "candidate_false_positives": [
                    {"severity": "low", "title": "fp", "detail": "d", "static_refs": ["P9"]}
                ],
                "gaps": [
                    {"gap_type": "static_uncorroborated", "severity": "high", "title": "g",
                     "detail": "d", "static_refs": ["S1"], "behavioral_refs": []}
                ],
                "prioritized_remediations": [
                    {"rank": 1, "priority": "high", "title": "fix", "action": "do it",
                     "basis": "score 70", "source_kind": "correlated", "severity": "high",
                     "static_refs": ["S1"], "behavioral_refs": ["b1"]}
                ],
            },
        },
        "verdict_result": {
            "status": "recommended", "recommended_verdict": "INCONCLUSIVE",
            "rubric_version": "1.0",
            "recommendation_basis": {"summary": "advisory INCONCLUSIVE, human gate."},
        },
    }


def _build(item):
    return report.build_report(
        item, intake_id=item["intake_id"], sha256=item["sha256"],
        assembled_at=_ASSEMBLED_AT, contract_version="1.0", status_contract_version="1.0",
    )


_SEVERITIES = {"unknown", "none", "info", "low", "medium", "high", "critical"}


class TestOfflineConformanceWalk(unittest.TestCase):
    """Pure-Python conformance walk (always runs; stdlib only)."""

    def setUp(self):
        self.full = _build(_full_item())
        self.pending = _build({"intake_id": _INTAKE_ID, "sha256": _SHA256, "status": "RECEIVED"})

    def test_required_top_level_keys(self):
        for rpt in (self.full, self.pending):
            for key in ("contract_version", "intake_id", "sha256", "assembled_at",
                        "executive", "security", "developer"):
                self.assertIn(key, rpt)
            self.assertEqual(rpt["contract_version"], "1.0")
            self.assertEqual(rpt["intake_id"], _INTAKE_ID)
            self.assertEqual(rpt["sha256"], _SHA256)

    def test_executive_shape(self):
        ex = self.full["executive"]
        self.assertIn(ex["overall_stage"], {
            "received", "classified", "collected", "correlated", "scored", "assessed",
            "recommended"})
        if "combined_score" in ex:
            self.assertTrue(0 <= ex["combined_score"] <= 100)
        rec = ex["recommendation"]
        self.assertEqual(rec["decision"], "pending")
        self.assertIs(rec["advisory"], True)
        if "recommended_verdict" in rec:
            self.assertIn(rec["recommended_verdict"], {"PASS", "FAIL", "INCONCLUSIVE"})

    def test_security_shape(self):
        sec = self.full["security"]
        self.assertIn(sec["data_status"], {"available", "pending", "not_carried_on_hub"})
        self.assertEqual(sec["mitre_attack"]["status"], "not_carried_on_hub")
        self.assertEqual(sec["sigma_rules"]["status"], "not_carried_on_hub")
        for f in sec["findings"]:
            self.assertIn(f["severity"], _SEVERITIES)
            self.assertLessEqual(len(f["title"]), 256)
            self.assertLessEqual(len(f.get("static_refs", [])), 20)

    def test_developer_shape(self):
        dev = self.full["developer"]
        self.assertIn(dev["data_status"], {"available", "pending", "not_carried_on_hub"})
        self.assertEqual(dev["source_location"]["status"], "not_carried_on_hub")
        ranks = [r["rank"] for r in dev["prioritized_remediations"]]
        for r in dev["prioritized_remediations"]:
            self.assertIn(r["priority"], {"low", "medium", "high", "critical"})
            self.assertTrue(1 <= r["rank"] <= 100)
        self.assertEqual(ranks, sorted(ranks))

    def test_no_effective_verdict_key(self):
        def walk(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    yield k
                    yield from walk(v)
            elif isinstance(obj, list):
                for v in obj:
                    yield from walk(v)

        for rpt in (self.full, self.pending):
            keys = set(walk(rpt))
            self.assertFalse(keys & _BANNED_EFFECTIVE_KEYS)

    def test_bounds_lists_capped(self):
        sec = self.full["security"]
        self.assertLessEqual(len(sec["findings"]), 100)
        self.assertLessEqual(len(sec["gaps"]), 100)
        dev = self.full["developer"]
        self.assertLessEqual(len(dev["prioritized_remediations"]), 100)


@unittest.skipUnless(_HAVE_JSONSCHEMA, "jsonschema not installed (offline sandbox)")
class TestLiveSchemaValidation(unittest.TestCase):
    """LIVE: validate assembled payloads against report.contract.v1.json."""

    def setUp(self):
        with open(_SCHEMA_PATH, encoding="utf-8") as fh:
            self.validator = Draft7Validator(json.load(fh))

    def test_full_payload_validates(self):
        errors = sorted(self.validator.iter_errors(_build(_full_item())),
                        key=lambda e: e.path)
        self.assertEqual(errors, [], f"schema errors: {[e.message for e in errors]}")

    def test_pending_payload_validates(self):
        pending = _build({"intake_id": _INTAKE_ID, "sha256": _SHA256, "status": "RECEIVED"})
        errors = sorted(self.validator.iter_errors(pending), key=lambda e: e.path)
        self.assertEqual(errors, [], f"schema errors: {[e.message for e in errors]}")

    def test_schema_has_no_bare_verdict_property(self):
        with open(_SCHEMA_PATH, encoding="utf-8") as fh:
            raw = fh.read()
        # The advisory key is allow-listed; no bare effective-verdict property is defined.
        self.assertIn(_ALLOWED_VERDICT_KEY, raw)
        for banned in _BANNED_EFFECTIVE_KEYS:
            self.assertNotIn(f'"{banned}"', raw)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
