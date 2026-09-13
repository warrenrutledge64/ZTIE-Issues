"""ZTIE Story 3.4 (RD-039) — PURE unit tests for the findings + remediations logic.

Stdlib-only (unittest), fully offline. Exercises the deterministic assessment core in
``remediate.py``: detailed findings, the migrated candidate-false-positive + gap lists,
the prioritized-remediation ranking, honest partial-scoring tolerance, and the status
logic (assessed / no_scores / skipped_no_evidence). NO boto3, NO model, NO I/O.
"""

from __future__ import annotations

import unittest

import remediate


def _scoring(*, static=None, dynamic=None, combined=None, complete=True, rubric="1.0"):
    def _block(v):
        if v is None:
            return {"status": "skipped_no_evidence"}
        if isinstance(v, str):  # a non-scored status
            return {"status": v}
        return {"status": "scored", "score": v}

    return {
        "contract_version": "1.0",
        "intake_id": "62360e03-dfb1-4655-ac52-2a55345ab6f0",
        "sha256": "a" * 64,
        "scored_at": "2026-09-13T00:00:00Z",
        "rubric_version": rubric,
        "combined_complete": complete,
        "static": _block(static),
        "dynamic": _block(dynamic),
        "combined": _block(combined),
    }


def _correlation(findings, status="correlated"):
    result = {
        "contract_version": "1.0",
        "intake_id": "62360e03-dfb1-4655-ac52-2a55345ab6f0",
        "sha256": "a" * 64,
        "correlated_at": "2026-09-13T00:00:00Z",
        "status": status,
    }
    if status == "correlated":
        result["correlation"] = {
            "summary": "s",
            "finding_count": len(findings),
            "findings": findings,
        }
    return result


def _f(kind, severity, title="t", **extra):
    return {"kind": kind, "severity": severity, "title": title, **extra}


class TestExtractScores(unittest.TestCase):
    def test_none_when_absent(self):
        self.assertIsNone(remediate.extract_scores(None))
        self.assertIsNone(remediate.extract_scores("not a dict"))

    def test_all_three_lanes_present(self):
        scores = remediate.extract_scores(
            _scoring(static=70, dynamic="model_error", combined=55)
        )
        self.assertEqual(scores["static"], {"status": "scored", "score": 70})
        self.assertEqual(scores["dynamic"], {"status": "model_error"})
        self.assertEqual(scores["combined"], {"status": "scored", "score": 55})

    def test_missing_lane_becomes_skipped(self):
        # A malformed scoring_result missing a lane -> synthetic skipped block (honest).
        scores = remediate.extract_scores(
            {"static": {"status": "scored", "score": 40}}
        )
        self.assertEqual(scores["dynamic"], {"status": "skipped_no_evidence"})
        self.assertEqual(scores["combined"], {"status": "skipped_no_evidence"})

    def test_bad_score_is_not_fabricated(self):
        scores = remediate.extract_scores(
            {
                "static": {"status": "scored", "score": "not-a-number"},
                "dynamic": {"status": "scored"},
                "combined": {"status": "scored", "score": True},
            }
        )
        # scored but no numeric score -> the score key is simply absent (never faked).
        self.assertNotIn("score", scores["static"])
        self.assertNotIn("score", scores["dynamic"])
        self.assertNotIn("score", scores["combined"])


class TestHighestScore(unittest.TestCase):
    def test_max_and_kind(self):
        scores = remediate.extract_scores(_scoring(static=70, dynamic=30, combined=55))
        self.assertEqual(remediate.highest_score(scores), (70, "static"))

    def test_combined_wins_a_tie(self):
        scores = remediate.extract_scores(_scoring(static=55, dynamic=30, combined=55))
        self.assertEqual(remediate.highest_score(scores), (55, "combined"))

    def test_none_when_no_lane_scored(self):
        scores = remediate.extract_scores(
            _scoring(static="model_error", dynamic="model_error", combined="unparseable")
        )
        self.assertEqual(remediate.highest_score(scores), (None, None))


class TestExtractFindings(unittest.TestCase):
    def test_pulls_valid_kinds(self):
        findings, status = remediate.extract_findings(
            _correlation([_f("correlated", "high"), _f("static_only", "low")])
        )
        self.assertEqual(status, "correlated")
        self.assertEqual(len(findings), 2)

    def test_drops_bad_kinds(self):
        findings, _ = remediate.extract_findings(
            _correlation([_f("correlated", "high"), _f("bogus_kind", "low")])
        )
        self.assertEqual(len(findings), 1)

    def test_non_correlated_status_yields_no_findings(self):
        findings, status = remediate.extract_findings(
            _correlation([], status="model_error")
        )
        self.assertEqual(findings, [])
        self.assertEqual(status, "model_error")

    def test_absent_correlation_result(self):
        self.assertEqual(remediate.extract_findings(None), ([], None))


class TestMigratedLists(unittest.TestCase):
    def test_candidate_false_positives_from_static_only(self):
        findings, _ = remediate.extract_findings(
            _correlation(
                [_f("static_only", "medium", "flag"), _f("correlated", "high", "conf")]
            )
        )
        cfps, trunc = remediate.build_candidate_false_positives(findings)
        self.assertFalse(trunc)
        self.assertEqual(len(cfps), 1)
        self.assertEqual(cfps[0]["title"], "flag")
        self.assertIn("detail", cfps[0])  # default detail supplied

    def test_gaps_mapping(self):
        findings, _ = remediate.extract_findings(
            _correlation(
                [
                    _f("static_only", "medium", "s"),
                    _f("dynamic_only", "high", "d"),
                    _f("contradiction", "low", "c"),
                    _f("correlated", "high", "agree"),  # NOT a gap
                ]
            )
        )
        gaps, _ = remediate.build_gaps(findings, combined_complete=True)
        types_ = sorted(g["gap_type"] for g in gaps)
        self.assertEqual(
            types_, ["contradiction", "dynamic_unexplained", "static_uncorroborated"]
        )

    def test_coverage_gap_when_incomplete(self):
        gaps, _ = remediate.build_gaps([], combined_complete=False)
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["gap_type"], "coverage")
        self.assertEqual(gaps[0]["severity"], "medium")

    def test_no_coverage_gap_when_complete(self):
        gaps, _ = remediate.build_gaps([], combined_complete=True)
        self.assertEqual(gaps, [])

    def test_lists_are_capped(self):
        many = [_f("static_only", "low", f"s{i}") for i in range(150)]
        cfps, trunc = remediate.build_candidate_false_positives(many)
        self.assertEqual(len(cfps), 100)
        self.assertTrue(trunc)


class TestPrioritizedRemediations(unittest.TestCase):
    def test_ranked_highest_risk_first(self):
        findings, _ = remediate.extract_findings(
            _correlation(
                [
                    _f("static_only", "low", "minor"),
                    _f("dynamic_only", "critical", "severe"),
                ]
            )
        )
        scores = remediate.extract_scores(_scoring(static=20, dynamic=90, combined=60))
        gaps, _ = remediate.build_gaps(findings, combined_complete=True)
        rems, _ = remediate.build_prioritized_remediations(findings, gaps, scores)
        # The critical finding must outrank the low one, and ranks are 1..N contiguous.
        self.assertEqual([r["rank"] for r in rems], list(range(1, len(rems) + 1)))
        self.assertEqual(rems[0]["severity"], "critical")
        self.assertEqual(rems[0]["priority"], "critical")

    def test_a_remediation_is_a_todo_not_a_verdict(self):
        findings, _ = remediate.extract_findings(
            _correlation([_f("static_only", "high", "x")])
        )
        scores = remediate.extract_scores(_scoring(static=80, dynamic=10, combined=60))
        gaps, _ = remediate.build_gaps(findings, combined_complete=True)
        rems, _ = remediate.build_prioritized_remediations(findings, gaps, scores)
        for r in rems:
            action = r["action"].lower()
            # No decision language: it never says reject/forward/approve/pass/fail.
            for banned in ("reject", "forward", "approve", "pass", "fail", "malicious"):
                self.assertNotIn(banned, action, f"remediation action leaked '{banned}'")

    def test_partial_scoring_still_ranks_by_severity(self):
        # No lane scored at all — ranking must fall back to severity, honestly.
        findings, _ = remediate.extract_findings(
            _correlation(
                [_f("dynamic_only", "critical", "sev"), _f("static_only", "low", "min")]
            )
        )
        scores = remediate.extract_scores(
            _scoring(static="model_error", dynamic="model_error", combined="model_error")
        )
        gaps, _ = remediate.build_gaps(findings, combined_complete=True)
        rems, _ = remediate.build_prioritized_remediations(findings, gaps, scores)
        self.assertEqual(rems[0]["severity"], "critical")
        # basis honestly notes no score is available.
        self.assertIn("no risk score", rems[0]["basis"])


class TestAssessStatus(unittest.TestCase):
    def test_no_scores(self):
        payload = remediate.assess(None, _correlation([_f("static_only", "high")]))
        self.assertEqual(payload["status"], "no_scores")
        self.assertNotIn("assessment", payload)

    def test_skipped_no_evidence(self):
        # scoring present but no lane scored AND no findings -> skipped_no_evidence.
        payload = remediate.assess(
            _scoring(static="model_error", dynamic="model_error", combined="model_error"),
            _correlation([]),
        )
        self.assertEqual(payload["status"], "skipped_no_evidence")

    def test_assessed_with_partial_scores_and_findings(self):
        payload = remediate.assess(
            _scoring(static=70, dynamic="model_error", combined=55),
            _correlation([_f("static_only", "high", "x")]),
            combined_complete=True,
        )
        self.assertEqual(payload["status"], "assessed")
        self.assertIn("assessment", payload)
        self.assertEqual(payload["correlation_status"], "correlated")

    def test_assessed_with_scores_but_no_findings(self):
        # At least one lane scored -> assessed even with zero findings.
        payload = remediate.assess(
            _scoring(static=70, dynamic=30, combined=55), _correlation([])
        )
        self.assertEqual(payload["status"], "assessed")
        self.assertEqual(payload["assessment"]["counts"]["remediation_count"], 0)

    def test_assessed_with_findings_but_no_scored_lane(self):
        # No lane scored but there ARE findings -> still assessed (evidence present).
        payload = remediate.assess(
            _scoring(static="model_error", dynamic="model_error", combined="model_error"),
            _correlation([_f("dynamic_only", "high", "x")]),
        )
        self.assertEqual(payload["status"], "assessed")


class TestBuildResult(unittest.TestCase):
    def test_identity_and_no_assessment_when_not_assessed(self):
        payload = remediate.assess(None, None)
        result = remediate.build_result(
            intake_id="62360e03-dfb1-4655-ac52-2a55345ab6f0",
            sha256="a" * 64,
            assessed_at="2026-09-13T00:00:00Z",
            contract_version="1.0",
            payload=payload,
        )
        self.assertEqual(result["status"], "no_scores")
        self.assertNotIn("assessment", result)
        self.assertEqual(result["contract_version"], "1.0")

    def test_carries_traceability_fields(self):
        payload = remediate.assess(
            _scoring(static=70, dynamic=30, combined=55, complete=True),
            _correlation([_f("correlated", "high", "x")]),
            combined_complete=True,
        )
        result = remediate.build_result(
            intake_id="62360e03-dfb1-4655-ac52-2a55345ab6f0",
            sha256="a" * 64,
            assessed_at="2026-09-13T00:00:00Z",
            contract_version="1.0",
            payload=payload,
            rubric_version="1.0",
            combined_complete=True,
        )
        self.assertEqual(result["rubric_version"], "1.0")
        self.assertTrue(result["combined_complete"])
        self.assertEqual(result["correlation_status"], "correlated")


if __name__ == "__main__":
    unittest.main()
