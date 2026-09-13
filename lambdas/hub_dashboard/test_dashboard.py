"""ZTIE Story 4.2 (RD-042) — PURE-STDLIB tests for the dashboard-payload assembly.

No boto3, no AWS, no model call — ``dashboard.py`` (+ the vendored ``status_model.py``) is
pure. Covers: the per-intake view (reuses the 4.1 read-model verbatim + adds threat +
action), the threat-tier banding rules (score bands, gap-severity floor, contradiction
floor, unknown), the action block (advisory + pending, never an effective decision), the
fleet view (rows + metrics + bounding/truncation), and the RD-040/RD-042 verdict-safety
invariants (no bare effective-verdict key anywhere; decision always pending).
"""

from __future__ import annotations

import hashlib
import os
import unittest

import dashboard
import status_model

_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_INTAKE_ID_2 = "7f1e2d3c-4b5a-4c6d-8e9f-0a1b2c3d4e5f"
_SHA256 = "a" * 64
_ASSEMBLED_AT = "2026-09-14T00:00:00Z"

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


def _find_banned(obj):
    if isinstance(obj, dict):
        for k, val in obj.items():
            if k in _BANNED_EFFECTIVE_KEYS:
                return k
            deeper = _find_banned(val)
            if deeper:
                return f"{k}.{deeper}"
    elif isinstance(obj, list):
        for i, val in enumerate(obj):
            deeper = _find_banned(val)
            if deeper:
                return f"[{i}].{deeper}"
    return None


class TestVendoredStatusModelNoDrift(unittest.TestCase):
    """The hub_dashboard status_model.py is a VENDORED copy of the canonical hub_status
    one (each Lambda dir is bundled as its own asset, so cross-dir import is impossible at
    runtime). It MUST stay byte-identical, exactly like the bundled contract copies."""

    def test_status_model_byte_identical_to_canonical(self):
        here = os.path.dirname(__file__)
        vendored = os.path.join(here, "status_model.py")
        canonical = os.path.join(here, "..", "hub_status", "status_model.py")
        if not os.path.exists(canonical):
            self.skipTest("canonical hub_status/status_model.py not present in this tree")
        with open(vendored, "rb") as fh:
            vh = hashlib.sha256(fh.read()).hexdigest()
        with open(canonical, "rb") as fh:
            ch = hashlib.sha256(fh.read()).hexdigest()
        self.assertEqual(vh, ch, "hub_dashboard/status_model.py drifted from canonical")


class TestIntakeView(unittest.TestCase):
    def test_reuses_status_read_model_verbatim(self):
        item = _item(
            combined_event={},
            correlation_result={},
            scoring_result=_scoring(),
            remediation_result=_rem(),
            verdict_result=_verdict(),
        )
        view = _intake_view(item)
        # The embedded status IS exactly what status_model.build_status produces.
        expected = status_model.build_status(
            item,
            intake_id=item["intake_id"],
            sha256=item["sha256"],
            assembled_at=_ASSEMBLED_AT,
            contract_version="1.0",
        )
        self.assertEqual(view["intake"]["status"], expected)
        self.assertEqual(view["view"], "intake")
        self.assertEqual(view["contract_version"], "1.0")
        self.assertEqual(view["assembled_at"], _ASSEMBLED_AT)

    def test_intake_view_has_threat_and_action(self):
        view = _intake_view(_item(scoring_result=_scoring()))
        self.assertIn("threat", view["intake"])
        self.assertIn("action", view["intake"])


class TestThreatTier(unittest.TestCase):
    def _tier(self, **parts):
        return _intake_view(_item(**parts))["intake"]["threat"]

    def test_unknown_when_no_evidence(self):
        self.assertEqual(self._tier()["tier"], "unknown")

    def test_low_band(self):
        t = self._tier(scoring_result=_scoring(combined=10), remediation_result=_rem(highest_gap="none"))
        self.assertEqual(t["tier"], "low")
        self.assertEqual(t["combined_score"], 10)

    def test_medium_band(self):
        t = self._tier(scoring_result=_scoring(combined=40), remediation_result=_rem(highest_gap="none"))
        self.assertEqual(t["tier"], "medium")

    def test_high_band(self):
        t = self._tier(scoring_result=_scoring(combined=60), remediation_result=_rem(highest_gap="none"))
        self.assertEqual(t["tier"], "high")

    def test_critical_band(self):
        t = self._tier(scoring_result=_scoring(combined=90), remediation_result=_rem(highest_gap="none"))
        self.assertEqual(t["tier"], "critical")

    def test_high_gap_raises_floor_even_when_score_low(self):
        # combined 10 => low by score, but a HIGH gap raises the display floor to high.
        t = self._tier(scoring_result=_scoring(combined=10), remediation_result=_rem(highest_gap="high"))
        self.assertEqual(t["tier"], "high")
        self.assertEqual(t["highest_gap_severity"], "high")

    def test_gap_floor_never_lowers_a_higher_score_band(self):
        # combined 90 => critical; a medium gap must NOT lower it.
        t = self._tier(scoring_result=_scoring(combined=90), remediation_result=_rem(highest_gap="medium"))
        self.assertEqual(t["tier"], "critical")

    def test_contradiction_raises_to_at_least_medium(self):
        # No scores => unknown by score, but a contradiction pushes to at least medium.
        t = self._tier(remediation_result=_rem(highest_gap="none", contradiction=1))
        self.assertEqual(t["tier"], "medium")
        self.assertTrue(t["contradiction_present"])


class TestActionBlock(unittest.TestCase):
    def test_action_advisory_and_pending(self):
        view = _intake_view(_item(scoring_result=_scoring(), verdict_result=_verdict("FAIL")))
        action = view["intake"]["action"]
        self.assertEqual(action["intake_id"], _INTAKE_ID)
        self.assertEqual(action["sha256"], _SHA256)
        self.assertEqual(action["decision"], "pending")
        self.assertIs(action["advisory"], True)
        self.assertEqual(action["recommended_verdict"], "FAIL")
        self.assertEqual(action["recommendation_status"], "recommended")

    def test_action_omits_recommended_verdict_when_not_yet(self):
        view = _intake_view(_item(scoring_result=_scoring()))
        action = view["intake"]["action"]
        self.assertNotIn("recommended_verdict", action)
        self.assertEqual(action["recommendation_status"], "not_yet_recommended")
        self.assertEqual(action["decision"], "pending")


class TestNoEffectiveVerdictKey(unittest.TestCase):
    def test_intake_view_no_banned_keys(self):
        for rv in ("PASS", "FAIL", "INCONCLUSIVE"):
            view = _intake_view(
                _item(scoring_result=_scoring(), remediation_result=_rem(), verdict_result=_verdict(rv))
            )
            self.assertIsNone(_find_banned(view))

    def test_fleet_view_no_banned_keys(self):
        items = [
            _item(scoring_result=_scoring(), verdict_result=_verdict("PASS")),
            _item(intake_id=_INTAKE_ID_2, scoring_result=_scoring(combined=90), verdict_result=_verdict("FAIL")),
        ]
        view = dashboard.build_fleet_view(
            items, assembled_at=_ASSEMBLED_AT, contract_version="1.0", status_contract_version="1.0"
        )
        self.assertIsNone(_find_banned(view))


class TestFleetView(unittest.TestCase):
    def _fleet(self, items, **kw):
        return dashboard.build_fleet_view(
            items,
            assembled_at=_ASSEMBLED_AT,
            contract_version="1.0",
            status_contract_version="1.0",
            **kw,
        )

    def test_empty_fleet(self):
        view = self._fleet([])
        self.assertEqual(view["view"], "fleet")
        self.assertEqual(view["fleet"]["returned_count"], 0)
        self.assertEqual(view["fleet"]["intakes"], [])
        self.assertFalse(view["fleet"]["truncated"])
        self.assertEqual(view["fleet"]["metrics"]["window_count"], 0)

    def test_rows_summarize_each_item(self):
        items = [
            _item(
                received_at="2026-09-14T01:00:00Z",
                combined_event={},
                correlation_result={},
                scoring_result=_scoring(combined=90),
                remediation_result=_rem(),
                verdict_result=_verdict("FAIL"),
            ),
            _item(
                intake_id=_INTAKE_ID_2,
                received_at="2026-09-14T00:00:00Z",
                scoring_result=_scoring(combined=10),
            ),
        ]
        view = self._fleet(items)
        rows = view["fleet"]["intakes"]
        self.assertEqual(len(rows), 2)
        r0 = rows[0]
        self.assertEqual(r0["intake_id"], _INTAKE_ID)
        self.assertEqual(r0["overall_stage"], "recommended")
        self.assertEqual(r0["threat_tier"], "critical")
        self.assertEqual(r0["recommended_verdict"], "FAIL")
        self.assertEqual(r0["decision"], "pending")
        self.assertEqual(r0["received_at"], "2026-09-14T01:00:00Z")
        # Second row: scored only, no verdict => no recommended_verdict, low tier.
        r1 = rows[1]
        self.assertNotIn("recommended_verdict", r1)
        self.assertEqual(r1["threat_tier"], "low")

    def test_row_skips_item_missing_integrity_key(self):
        items = [_item(), {"intake_id": _INTAKE_ID_2}]  # second has no sha256
        view = self._fleet(items)
        self.assertEqual(view["fleet"]["returned_count"], 1)

    def test_metrics_rollup(self):
        items = [
            _item(scoring_result=_scoring(combined=90), verdict_result=_verdict("FAIL")),
            _item(intake_id=_INTAKE_ID_2, scoring_result=_scoring(combined=10)),
        ]
        m = self._fleet(items)["fleet"]["metrics"]
        self.assertEqual(m["window_count"], 2)
        self.assertEqual(m["by_recommended_verdict"]["FAIL"], 1)
        self.assertEqual(m["by_recommended_verdict"]["none"], 1)
        self.assertEqual(m["by_threat_tier"]["critical"], 1)
        self.assertEqual(m["by_threat_tier"]["low"], 1)
        self.assertEqual(m["by_stage"]["recommended"], 1)
        # stubbed health blocks are not_wired
        self.assertEqual(m["ami_build_health"]["status"], "not_wired")
        self.assertEqual(m["sensor_status"]["status"], "not_wired")
        self.assertEqual(m["cost"]["status"], "not_wired")

    def test_limit_bounds_and_truncation(self):
        items = [_item(intake_id=f"{i:08d}-0000-4000-8000-000000000000") for i in range(5)]
        view = self._fleet(items, limit=2)
        self.assertEqual(view["fleet"]["returned_count"], 2)
        self.assertTrue(view["fleet"]["truncated"])

    def test_limit_clamped_to_max(self):
        # A silly high limit is clamped; with few items it just returns them all.
        items = [_item()]
        view = self._fleet(items, limit=10_000)
        self.assertEqual(view["fleet"]["returned_count"], 1)
        self.assertFalse(view["fleet"]["truncated"])

    def test_more_available_flag_sets_truncated(self):
        view = self._fleet([_item()], more_available=True)
        self.assertTrue(view["fleet"]["truncated"])


if __name__ == "__main__":
    unittest.main()
