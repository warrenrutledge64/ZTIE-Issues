"""ZTIE Story 3.5 (RD-040) — PURE-STDLIB tests for the verdict-derivation logic.

Exercises the deterministic RD-040 mapping in ``verdict.py`` directly (no boto3, no AWS,
no model). Proves the stakeholder-ratified thresholds + the override rules + the
advisory/human-gate invariants:
  * combined <= 29 -> PASS ; 30-74 -> INCONCLUSIVE ; >= 75 -> FAIL (driven by the
    COMBINED score only — never a re-aggregation of the three lane scores).
  * FORCE INCONCLUSIVE on a contradiction finding OR incomplete evidence (partial
    scoring / coverage gap / combined_complete=false / combined not scored /
    remediation not assessed).
  * a high-severity gap -> INCONCLUSIVE bias (context), NEVER an auto-FAIL.
  * ADVISORY only: human_decision is ALWAYS 'pending'; no effective-verdict key.
"""

from __future__ import annotations

import unittest

import verdict as v

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
    assessment = {
        "gaps": gaps or [],
        "counts": {"contradiction": contradiction},
    }
    return {"status": status, "combined_complete": complete, "assessment": assessment}


def _gap(gap_type, severity, title="g"):
    return {"gap_type": gap_type, "severity": severity, "title": title}


class TestScoreDrivenMapping(unittest.TestCase):
    """The cut lines, driven by the COMBINED score only, complete + no override."""

    def test_low_combined_is_pass(self):
        for combined in (0, 10, 29):
            p = v.derive(_scoring(static=90, dynamic=90, combined=combined), _rem())
            self.assertEqual(p["recommended_verdict"], "PASS", f"combined={combined}")
            self.assertEqual(p["status"], "recommended")
            self.assertEqual(p["basis"]["driver"], "combined_score")

    def test_mid_combined_is_inconclusive(self):
        for combined in (30, 50, 74):
            p = v.derive(_scoring(static=0, dynamic=0, combined=combined), _rem())
            self.assertEqual(
                p["recommended_verdict"], "INCONCLUSIVE", f"combined={combined}"
            )
            self.assertEqual(p["basis"]["driver"], "combined_score")

    def test_high_combined_is_fail(self):
        for combined in (75, 90, 100):
            p = v.derive(_scoring(static=0, dynamic=0, combined=combined), _rem())
            self.assertEqual(p["recommended_verdict"], "FAIL", f"combined={combined}")
            self.assertEqual(p["basis"]["driver"], "combined_score")

    def test_boundary_29_pass_30_inconclusive_74_inconclusive_75_fail(self):
        self.assertEqual(
            v.derive(_scoring(static=0, dynamic=0, combined=29), _rem())[
                "recommended_verdict"
            ],
            "PASS",
        )
        self.assertEqual(
            v.derive(_scoring(static=0, dynamic=0, combined=30), _rem())[
                "recommended_verdict"
            ],
            "INCONCLUSIVE",
        )
        self.assertEqual(
            v.derive(_scoring(static=0, dynamic=0, combined=74), _rem())[
                "recommended_verdict"
            ],
            "INCONCLUSIVE",
        )
        self.assertEqual(
            v.derive(_scoring(static=0, dynamic=0, combined=75), _rem())[
                "recommended_verdict"
            ],
            "FAIL",
        )

    def test_verdict_is_driven_by_combined_not_static_or_dynamic(self):
        # High static + high dynamic but LOW combined -> PASS (combined is the driver;
        # the lane scores are NOT re-blended into the decision).
        p = v.derive(_scoring(static=100, dynamic=100, combined=5), _rem())
        self.assertEqual(p["recommended_verdict"], "PASS")
        # Low static + low dynamic but HIGH combined -> FAIL.
        p = v.derive(_scoring(static=0, dynamic=0, combined=95), _rem())
        self.assertEqual(p["recommended_verdict"], "FAIL")


class TestContradictionForcesInconclusive(unittest.TestCase):
    def test_contradiction_via_counts_forces_inconclusive_even_low_score(self):
        p = v.derive(_scoring(static=5, dynamic=5, combined=5), _rem(contradiction=1))
        self.assertEqual(p["recommended_verdict"], "INCONCLUSIVE")
        self.assertEqual(p["basis"]["driver"], "contradiction_present")
        self.assertTrue(p["basis"]["contradiction_present"])

    def test_contradiction_via_gap_forces_inconclusive_even_high_score(self):
        # A high combined would be FAIL, but a contradiction forces INCONCLUSIVE.
        p = v.derive(
            _scoring(static=90, dynamic=90, combined=90),
            _rem(gaps=[_gap("contradiction", "high")]),
        )
        self.assertEqual(p["recommended_verdict"], "INCONCLUSIVE")
        self.assertEqual(p["basis"]["driver"], "contradiction_present")


class TestIncompleteEvidenceForcesInconclusive(unittest.TestCase):
    def test_partial_scoring_static_not_scored(self):
        p = v.derive(
            _scoring(static="model_error", dynamic=10, combined=10), _rem()
        )
        self.assertEqual(p["recommended_verdict"], "INCONCLUSIVE")
        self.assertEqual(p["status"], "incomplete")
        self.assertEqual(p["basis"]["driver"], "incomplete_evidence")
        self.assertIn("static_not_scored", p["basis"]["override_reasons"])

    def test_combined_not_scored(self):
        p = v.derive(
            _scoring(static=10, dynamic=10, combined="model_error"), _rem()
        )
        self.assertEqual(p["recommended_verdict"], "INCONCLUSIVE")
        self.assertEqual(p["basis"]["driver"], "no_score_available")

    def test_combined_complete_false(self):
        p = v.derive(
            _scoring(static=10, dynamic=10, combined=10, complete=False),
            _rem(complete=False),
        )
        self.assertEqual(p["recommended_verdict"], "INCONCLUSIVE")
        self.assertIn("combined_incomplete", p["basis"]["override_reasons"])

    def test_coverage_gap(self):
        p = v.derive(
            _scoring(static=10, dynamic=10, combined=10),
            _rem(gaps=[_gap("coverage", "medium")]),
        )
        self.assertEqual(p["recommended_verdict"], "INCONCLUSIVE")
        self.assertIn("coverage_gap", p["basis"]["override_reasons"])

    def test_remediation_not_assessed(self):
        p = v.derive(
            _scoring(static=10, dynamic=10, combined=10), _rem(status="no_scores")
        )
        self.assertEqual(p["recommended_verdict"], "INCONCLUSIVE")
        self.assertIn("remediation_not_assessed", p["basis"]["override_reasons"])

    def test_no_scoring_result_is_inconclusive_no_scores(self):
        p = v.derive(None, _rem())
        self.assertEqual(p["recommended_verdict"], "INCONCLUSIVE")
        self.assertEqual(p["status"], "no_scores")


class TestHighSeverityGapIsNeverAutoFail(unittest.TestCase):
    def test_high_gap_low_combined_stays_pass(self):
        # A high-severity gap must NOT flip a low-combined PASS into FAIL. It is context
        # (INCONCLUSIVE-bias at most), never an auto-FAIL. Here evidence is complete +
        # combined is low, so it stays PASS with the gap noted as context.
        p = v.derive(
            _scoring(static=10, dynamic=10, combined=10),
            _rem(gaps=[_gap("dynamic_unexplained", "high")]),
        )
        self.assertEqual(p["recommended_verdict"], "PASS")
        self.assertEqual(p["basis"]["highest_gap_severity"], "high")

    def test_critical_gap_never_becomes_fail(self):
        # A critical gap on a low combined score is still not a FAIL.
        p = v.derive(
            _scoring(static=10, dynamic=10, combined=20),
            _rem(gaps=[_gap("dynamic_unexplained", "critical")]),
        )
        self.assertNotEqual(p["recommended_verdict"], "FAIL")


class TestAdvisoryInvariants(unittest.TestCase):
    def _build(self, payload):
        return v.build_result(
            intake_id="62360e03-dfb1-4655-ac52-2a55345ab6f0",
            sha256="a" * 64,
            recommended_at="2026-09-13T00:00:00Z",
            contract_version="1.0",
            payload=payload,
            rubric_version="1.0",
        )

    def test_human_decision_always_pending(self):
        for payload in (
            v.derive(_scoring(static=0, dynamic=0, combined=5), _rem()),  # PASS
            v.derive(_scoring(static=0, dynamic=0, combined=90), _rem()),  # FAIL
            v.derive(None, _rem()),  # no_scores
            v.derive(_scoring(static="model_error", dynamic=0, combined=0), _rem()),
        ):
            r = self._build(payload)
            self.assertEqual(r["human_decision"], "pending")

    def test_no_effective_verdict_key_anywhere(self):
        # The record carries recommended_verdict (allowed) but NEVER a bare effective
        # 'verdict' / 'approved' / 'forward' / 'malicious' / 'pass_fail' / 'clean' /
        # 'safe' key.
        for payload in (
            v.derive(_scoring(static=0, dynamic=0, combined=90), _rem()),
            v.derive(_scoring(static=0, dynamic=0, combined=5), _rem()),
        ):
            r = self._build(payload)
            self.assertIsNone(_find_banned(r))

    def test_recommended_verdict_present_and_allowlisted(self):
        r = self._build(v.derive(_scoring(static=0, dynamic=0, combined=90), _rem()))
        self.assertIn(r["recommended_verdict"], ("PASS", "FAIL", "INCONCLUSIVE"))

    def test_summary_frames_advisory_and_human_gated(self):
        r = self._build(v.derive(_scoring(static=0, dynamic=0, combined=90), _rem()))
        summary = r["recommendation_basis"]["summary"].lower()
        self.assertIn("advisory", summary)
        self.assertIn("human", summary)

    def test_build_result_never_carries_human_selection_field(self):
        # 3.5 records human_decision=pending only; it must not invent a field that
        # asserts the human's actual accept/reject choice.
        r = self._build(v.derive(_scoring(static=0, dynamic=0, combined=5), _rem()))
        for forbidden in ("human_selection", "human_verdict", "effective_verdict",
                          "decision", "accepted", "rejected"):
            self.assertNotIn(forbidden, r)


def _find_banned(obj, path="<root>"):
    if isinstance(obj, dict):
        for k, val in obj.items():
            if k in _BANNED_EFFECTIVE_KEYS:
                return f"{path}.{k}"
            deeper = _find_banned(val, f"{path}.{k}")
            if deeper:
                return deeper
    elif isinstance(obj, list):
        for i, val in enumerate(obj):
            deeper = _find_banned(val, f"{path}[{i}]")
            if deeper:
                return deeper
    return None


if __name__ == "__main__":
    unittest.main()
