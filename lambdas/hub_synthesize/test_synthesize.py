"""ZTIE Story 3.3 — PURE-STDLIB tests for the accuracy + gap_analysis synthesis
logic (RD-037). No boto3, no model, no I/O — exercises synthesize.py directly.

The load-bearing DoD assertion lives here: a static-only false positive is
demonstrably reconciled against benign dynamic evidence (surfaced as a candidate
false positive + a static_uncorroborated gap), and the accuracy score reflects the
reconciliation — all in pure, reproducible logic.
"""

from __future__ import annotations

import unittest

import synthesize

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
        "intake_id": "62360e03-dfb1-4655-ac52-2a55345ab6f0",
        "sha256": "a" * 64,
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


class TestFalsePositiveReconciliation(unittest.TestCase):
    """THE DoD case: a static-only finding is reconciled against benign dynamic
    evidence — surfaced as a candidate false positive AND a static_uncorroborated
    gap, and it lowers the reconciliation score."""

    def test_static_only_is_candidate_false_positive(self):
        corr = _correlation_result(
            [
                _finding(
                    "static_only",
                    severity="high",
                    title="Permissive egress rule never exercised",
                    static_refs=["SG-open-egress"],
                    detail="flagged by static scan",
                ),
                _finding("correlated", severity="medium", title="Exec matched observed process"),
            ]
        )
        payload = synthesize.synthesize(corr, combined_complete=True)
        self.assertEqual(payload["status"], "synthesized")
        acc = payload["synthesis"]["accuracy"]
        self.assertEqual(acc["confirmed_correlation_count"], 1)
        self.assertEqual(acc["candidate_false_positive_count"], 1)
        self.assertEqual(acc["static_only_count"], 1)
        # One reconciled candidate FP surfaced with its severity + refs carried.
        cfp = acc["candidate_false_positives"][0]
        self.assertEqual(cfp["severity"], "high")
        self.assertEqual(cfp["static_refs"], ["SG-open-egress"])
        self.assertIn("Permissive egress", cfp["title"])
        # 1 confirmed / (1 confirmed + 1 static-only) = 50.
        self.assertEqual(acc["accuracy_score"], 50)

    def test_static_only_also_surfaced_as_gap(self):
        corr = _correlation_result([_finding("static_only", severity="high", title="x")])
        gaps = synthesize.synthesize(corr)["synthesis"]["gaps"]
        self.assertEqual(gaps["gap_count"], 1)
        self.assertEqual(gaps["items"][0]["gap_type"], "static_uncorroborated")
        self.assertEqual(gaps["highest_gap_severity"], "high")

    def test_all_confirmed_is_perfect_reconciliation(self):
        corr = _correlation_result(
            [_finding("correlated", title="a"), _finding("correlated", title="b")]
        )
        payload = synthesize.synthesize(corr)
        self.assertEqual(payload["synthesis"]["accuracy"]["accuracy_score"], 100)
        self.assertEqual(payload["synthesis"]["accuracy"]["candidate_false_positive_count"], 0)
        self.assertEqual(payload["synthesis"]["gaps"]["gap_count"], 0)

    def test_all_static_only_is_zero_reconciliation(self):
        corr = _correlation_result(
            [_finding("static_only", title="a"), _finding("static_only", title="b")]
        )
        acc = synthesize.synthesize(corr)["synthesis"]["accuracy"]
        self.assertEqual(acc["accuracy_score"], 0)
        self.assertEqual(acc["candidate_false_positive_count"], 2)


class TestGapAnalysis(unittest.TestCase):
    def test_each_kind_maps_to_a_gap(self):
        corr = _correlation_result(
            [
                _finding("static_only", severity="low", title="s"),
                _finding("dynamic_only", severity="medium", title="d"),
                _finding("contradiction", severity="critical", title="c"),
                _finding("correlated", severity="high", title="ok"),
            ]
        )
        gaps = synthesize.synthesize(corr, combined_complete=True)["synthesis"]["gaps"]
        types = sorted(g["gap_type"] for g in gaps["items"])
        # correlated is NOT a gap.
        self.assertEqual(
            types, ["contradiction", "dynamic_unexplained", "static_uncorroborated"]
        )
        self.assertEqual(gaps["highest_gap_severity"], "critical")

    def test_incomplete_combined_event_adds_coverage_gap(self):
        corr = _correlation_result(
            [_finding("correlated", title="a")], combined_complete=False
        )
        gaps = synthesize.synthesize(corr, combined_complete=False)["synthesis"]["gaps"]
        gap_types = [g["gap_type"] for g in gaps["items"]]
        self.assertIn("coverage", gap_types)

    def test_complete_event_no_coverage_gap(self):
        corr = _correlation_result([_finding("correlated", title="a")])
        gaps = synthesize.synthesize(corr, combined_complete=True)["synthesis"]["gaps"]
        self.assertNotIn("coverage", [g["gap_type"] for g in gaps["items"]])

    def test_dynamic_only_carries_behavioral_refs(self):
        corr = _correlation_result(
            [_finding("dynamic_only", title="d", behavioral_refs=["connect(1.2.3.4)"])]
        )
        gap = synthesize.synthesize(corr)["synthesis"]["gaps"]["items"][0]
        self.assertEqual(gap["behavioral_refs"], ["connect(1.2.3.4)"])


class TestHonestStatuses(unittest.TestCase):
    def test_absent_correlation_is_no_correlation(self):
        payload = synthesize.synthesize({"status": "RECEIVED"})
        self.assertEqual(payload["status"], "no_correlation")
        self.assertNotIn("synthesis", payload)

    def test_model_error_upstream_is_no_correlation(self):
        corr = _correlation_result([], status="model_error")
        payload = synthesize.synthesize(corr)
        self.assertEqual(payload["status"], "no_correlation")
        self.assertEqual(payload["correlation_status"], "model_error")
        self.assertNotIn("synthesis", payload)

    def test_unparseable_upstream_is_no_correlation(self):
        payload = synthesize.synthesize(_correlation_result([], status="unparseable"))
        self.assertEqual(payload["status"], "no_correlation")

    def test_skipped_no_signals_upstream_is_no_correlation(self):
        payload = synthesize.synthesize(
            _correlation_result([], status="skipped_no_signals")
        )
        self.assertEqual(payload["status"], "no_correlation")

    def test_correlated_but_zero_findings_is_skipped(self):
        payload = synthesize.synthesize(_correlation_result([]))
        self.assertEqual(payload["status"], "skipped_no_findings")
        self.assertEqual(payload["source_finding_count"], 0)
        self.assertNotIn("synthesis", payload)

    def test_none_input_is_no_correlation(self):
        self.assertEqual(synthesize.synthesize(None)["status"], "no_correlation")


class TestBoundsAndDefensiveParsing(unittest.TestCase):
    def test_out_of_enum_kind_dropped(self):
        corr = _correlation_result(
            [_finding("malicious", title="bad"), _finding("correlated", title="ok")]
        )
        payload = synthesize.synthesize(corr)
        # only the valid 'correlated' finding is counted.
        self.assertEqual(payload["source_finding_count"], 1)
        self.assertEqual(payload["synthesis"]["accuracy"]["confirmed_correlation_count"], 1)

    def test_out_of_enum_severity_becomes_unknown(self):
        corr = _correlation_result([_finding("static_only", severity="APOCALYPTIC", title="x")])
        cfp = synthesize.synthesize(corr)["synthesis"]["accuracy"]["candidate_false_positives"][0]
        self.assertEqual(cfp["severity"], "unknown")

    def test_candidate_false_positives_capped_and_truncated_flag(self):
        findings = [_finding("static_only", title=f"s{i}") for i in range(120)]
        payload = synthesize.synthesize(_correlation_result(findings))
        acc = payload["synthesis"]["accuracy"]
        self.assertEqual(len(acc["candidate_false_positives"]), 100)
        self.assertTrue(payload.get("truncated"))

    def test_gaps_capped_and_truncated(self):
        findings = [_finding("contradiction", title=f"c{i}") for i in range(120)]
        payload = synthesize.synthesize(_correlation_result(findings))
        self.assertEqual(len(payload["synthesis"]["gaps"]["items"]), 100)
        self.assertTrue(payload.get("truncated"))

    def test_title_and_detail_clipped(self):
        corr = _correlation_result(
            [_finding("static_only", title="T" * 1000, detail="D" * 5000)]
        )
        cfp = synthesize.synthesize(corr)["synthesis"]["accuracy"]["candidate_false_positives"][0]
        self.assertLessEqual(len(cfp["title"]), 256)
        self.assertLessEqual(len(cfp["detail"]), 1024)

    def test_refs_capped(self):
        corr = _correlation_result(
            [_finding("dynamic_only", title="d", behavioral_refs=[f"r{i}" for i in range(50)])]
        )
        gap = synthesize.synthesize(corr)["synthesis"]["gaps"]["items"][0]
        self.assertLessEqual(len(gap["behavioral_refs"]), 20)


class TestBuildResult(unittest.TestCase):
    def _build(self, payload):
        return synthesize.build_result(
            intake_id="62360e03-dfb1-4655-ac52-2a55345ab6f0",
            sha256="a" * 64,
            synthesized_at="2026-09-12T01:00:00Z",
            contract_version="1.0",
            payload=payload,
            correlation_contract_version="1.0",
            combined_complete=True,
        )

    def test_synthesized_result_shape(self):
        payload = synthesize.synthesize(
            _correlation_result([_finding("correlated", title="a")])
        )
        result = self._build(payload)
        for key in ("contract_version", "intake_id", "sha256", "synthesized_at", "status"):
            self.assertIn(key, result)
        self.assertEqual(result["contract_version"], "1.0")
        self.assertEqual(result["status"], "synthesized")
        self.assertIn("synthesis", result)
        self.assertEqual(result["correlation_contract_version"], "1.0")
        self.assertTrue(result["combined_complete"])

    def test_no_correlation_result_has_no_synthesis(self):
        payload = synthesize.synthesize({"status": "model_error"})
        result = self._build(payload)
        self.assertEqual(result["status"], "no_correlation")
        self.assertNotIn("synthesis", result)


class TestNoVerdictAnywhere(unittest.TestCase):
    def _all_payloads(self):
        return [
            synthesize.synthesize(
                _correlation_result(
                    [
                        _finding("static_only", severity="high", title="s"),
                        _finding("correlated", title="c"),
                        _finding("dynamic_only", title="d"),
                        _finding("contradiction", severity="critical", title="x"),
                    ],
                    combined_complete=False,
                ),
                combined_complete=False,
            ),
            synthesize.synthesize(_correlation_result([])),
            synthesize.synthesize({"status": "model_error"}),
        ]

    def test_no_banned_keys(self):
        for payload in self._all_payloads():
            offending = _no_banned_keys(payload)
            self.assertIsNone(offending, f"verdict-shaped key present: {offending}")


if __name__ == "__main__":
    unittest.main()
