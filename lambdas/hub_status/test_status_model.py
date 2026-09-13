"""ZTIE Story 4.1 (RD-041) — PURE-STDLIB tests for the status read-model assembly.

``status_model`` is I/O-free, so these import + exercise it directly (no boto3 stub
needed). They assert the READ/transform invariants: the furthest-stage logic, per-stage
presence, score/finding echoes (never re-derived, never re-blended), the ADVISORY
recommendation surfaced with a pending human decision, and — critically — that the built
view NEVER carries a bare effective-verdict key and the decision is ALWAYS pending.
"""

from __future__ import annotations

import decimal
import unittest

import status_model

_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_SHA256 = "c" * 64
_ASSEMBLED_AT = "2026-09-14T00:00:00Z"

# The EFFECTIVE / acted-upon verdict keys that must NEVER appear anywhere in the view.
# `recommended_verdict` is deliberately NOT here (it is the allow-listed advisory field).
_BANNED_EFFECTIVE_KEYS = frozenset(
    {"verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean"}
)


def _scoring(*, static=70, dynamic=30, combined=55, complete=True, rubric="1.0"):
    def _block(val):
        if isinstance(val, str):
            return {"status": val}
        return {"status": "scored", "score": val}

    return {
        "static": _block(static),
        "dynamic": _block(dynamic),
        "combined": _block(combined),
        "combined_complete": complete,
        "rubric_version": rubric,
    }


def _rem(
    *,
    status="assessed",
    findings=1,
    fps=1,
    gaps=1,
    remediations=2,
    contradiction=0,
    highest_gap="high",
):
    return {
        "status": status,
        "assessment": {
            "highest_gap_severity": highest_gap,
            "counts": {
                "detailed_finding_count": findings,
                "candidate_false_positive_count": fps,
                "gap_count": gaps,
                "remediation_count": remediations,
                "contradiction": contradiction,
            },
        },
    }


def _verdict(*, status="recommended", rv="INCONCLUSIVE", summary="advisory only"):
    v = {
        "contract_version": "1.0",
        "intake_id": _INTAKE_ID,
        "sha256": _SHA256,
        "recommended_at": "2026-09-13T00:00:00Z",
        "status": status,
        "human_decision": "pending",
        "rubric_version": "1.0",
        "recommendation_basis": {"driver": "combined_score", "summary": summary},
    }
    if rv is not None:
        v["recommended_verdict"] = rv
    return v


def _item(**parts):
    item = {"intake_id": _INTAKE_ID, "sha256": _SHA256, "status": "RECEIVED"}
    item.update(parts)
    return item


def _build(item):
    return status_model.build_status(
        item,
        intake_id=_INTAKE_ID,
        sha256=_SHA256,
        assembled_at=_ASSEMBLED_AT,
        contract_version="1.0",
    )


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


class TestOverallStage(unittest.TestCase):
    def test_received_when_bare(self):
        self.assertEqual(_build(_item())["overall_stage"], "received")

    def test_classified(self):
        v = _build(_item(classification="script"))
        self.assertEqual(v["overall_stage"], "classified")
        self.assertEqual(v["stages"]["classification"], "present")

    def test_collected(self):
        self.assertEqual(
            _build(_item(combined_event={"x": 1}))["overall_stage"], "collected"
        )

    def test_correlated(self):
        self.assertEqual(
            _build(_item(combined_event={}, correlation_result={}))["overall_stage"],
            "correlated",
        )

    def test_scored(self):
        self.assertEqual(
            _build(_item(scoring_result=_scoring()))["overall_stage"], "scored"
        )

    def test_assessed(self):
        self.assertEqual(
            _build(_item(scoring_result=_scoring(), remediation_result=_rem()))[
                "overall_stage"
            ],
            "assessed",
        )

    def test_recommended_is_furthest(self):
        v = _build(
            _item(
                scoring_result=_scoring(),
                remediation_result=_rem(),
                verdict_result=_verdict(),
            )
        )
        self.assertEqual(v["overall_stage"], "recommended")


class TestStagePresence(unittest.TestCase):
    def test_all_absent_by_default(self):
        stages = _build(_item())["stages"]
        for k in ("combined_event", "correlation", "scoring", "remediation",
                  "verdict_recommendation"):
            self.assertEqual(stages[k], "absent")
        self.assertNotIn("classification", stages)  # only added when present

    def test_present_maps_correctly(self):
        stages = _build(
            _item(
                combined_event={},
                correlation_result={},
                scoring_result=_scoring(),
                remediation_result=_rem(),
                verdict_result=_verdict(),
            )
        )["stages"]
        for k in ("combined_event", "correlation", "scoring", "remediation",
                  "verdict_recommendation"):
            self.assertEqual(stages[k], "present")


class TestScoreEcho(unittest.TestCase):
    def test_scores_echoed_not_reblended(self):
        v = _build(_item(scoring_result=_scoring(static=70, dynamic=30, combined=55)))
        s = v["scores"]
        self.assertEqual(s["static"], {"status": "scored", "score": 70})
        self.assertEqual(s["dynamic"], {"status": "scored", "score": 30})
        self.assertEqual(s["combined"], {"status": "scored", "score": 55})
        self.assertEqual(s["rubric_version"], "1.0")

    def test_decimal_scores_coerced(self):
        v = _build(_item(scoring_result=_scoring(combined=decimal.Decimal(55))))
        self.assertEqual(v["scores"]["combined"], {"status": "scored", "score": 55})

    def test_non_scored_lane_carried_honestly(self):
        v = _build(_item(scoring_result=_scoring(static="model_error")))
        self.assertEqual(v["scores"]["static"], {"status": "model_error"})

    def test_no_scores_omits_block(self):
        self.assertNotIn("scores", _build(_item()))


class TestFindingsSummary(unittest.TestCase):
    def test_counts_and_severity_summarized(self):
        v = _build(_item(remediation_result=_rem(findings=3, fps=1, gaps=2, remediations=4)))
        fs = v["findings_summary"]
        self.assertEqual(fs["status"], "assessed")
        self.assertEqual(fs["finding_count"], 3)
        self.assertEqual(fs["candidate_false_positive_count"], 1)
        self.assertEqual(fs["gap_count"], 2)
        self.assertEqual(fs["remediation_count"], 4)
        self.assertEqual(fs["highest_gap_severity"], "high")
        self.assertFalse(fs["contradiction_present"])

    def test_contradiction_flag(self):
        v = _build(_item(remediation_result=_rem(contradiction=1)))
        self.assertTrue(v["findings_summary"]["contradiction_present"])

    def test_no_remediation_omits_block(self):
        self.assertNotIn("findings_summary", _build(_item()))

    def test_no_full_findings_text_leaks(self):
        # The summary must carry counts, NOT the full detailed_findings list.
        rem = _rem()
        rem["assessment"]["detailed_findings"] = [{"title": "secret detail"}]
        v = _build(_item(remediation_result=rem))
        self.assertNotIn("detailed_findings", v["findings_summary"])


class TestRecommendation(unittest.TestCase):
    def test_advisory_surfaced_with_pending_decision(self):
        v = _build(_item(verdict_result=_verdict(rv="FAIL", summary="advisory only")))
        rec = v["recommendation"]
        self.assertEqual(rec["status"], "recommended")
        self.assertEqual(rec["recommended_verdict"], "FAIL")
        self.assertEqual(rec["decision"], "pending")
        self.assertIs(rec["advisory"], True)
        self.assertEqual(rec["summary"], "advisory only")
        self.assertEqual(rec["rubric_version"], "1.0")

    def test_not_yet_recommended_when_verdict_absent(self):
        rec = _build(_item(scoring_result=_scoring()))["recommendation"]
        self.assertEqual(rec["status"], "not_yet_recommended")
        self.assertNotIn("recommended_verdict", rec)
        self.assertEqual(rec["decision"], "pending")
        self.assertIs(rec["advisory"], True)

    def test_recommendation_echoed_never_derived(self):
        # 4.1 echoes whatever 3.5 recorded — even INCONCLUSIVE over high scores.
        v = _build(
            _item(
                scoring_result=_scoring(combined=90),
                verdict_result=_verdict(rv="INCONCLUSIVE"),
            )
        )
        self.assertEqual(v["recommendation"]["recommended_verdict"], "INCONCLUSIVE")


class TestZeroTrustInvariants(unittest.TestCase):
    def test_view_never_carries_effective_verdict_key(self):
        v = _build(
            _item(
                scoring_result=_scoring(),
                remediation_result=_rem(),
                verdict_result=_verdict(rv="FAIL"),
            )
        )
        self.assertIsNone(_find_banned(v))

    def test_decision_always_pending(self):
        for verdict_result in (None, _verdict(rv="PASS"), _verdict(rv="FAIL")):
            item = _item()
            if verdict_result is not None:
                item["verdict_result"] = verdict_result
            self.assertEqual(_build(item)["recommendation"]["decision"], "pending")

    def test_identity_and_note_present(self):
        v = _build(_item())
        self.assertEqual(v["intake_id"], _INTAKE_ID)
        self.assertEqual(v["sha256"], _SHA256)
        self.assertEqual(v["assembled_at"], _ASSEMBLED_AT)
        self.assertEqual(v["contract_version"], "1.0")
        self.assertIn("read_model_note", v)
        self.assertEqual(v["status"], "RECEIVED")

    def test_partial_item_never_raises(self):
        # A completely empty item (no sha/status) still assembles without raising.
        v = status_model.build_status(
            {}, intake_id=_INTAKE_ID, sha256=_SHA256,
            assembled_at=_ASSEMBLED_AT, contract_version="1.0",
        )
        self.assertEqual(v["overall_stage"], "received")


if __name__ == "__main__":
    unittest.main()
