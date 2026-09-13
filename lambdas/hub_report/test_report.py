"""ZTIE Story 4.5 (RD-045) — unit tests for the PURE report assembly + HTML render.

No boto3, no AWS, no model call — ``report.py`` (+ the vendored ``status_model.py``) is
pure logic, so these run offline in the INTEGRATIONS_ONLY sandbox with stdlib unittest.
"""

from __future__ import annotations

import hashlib
import os
import unittest

import report
import status_model

_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_SHA256 = "a" * 64
_ASSEMBLED_AT = "2026-09-14T00:00:00Z"

_BANNED_EFFECTIVE_KEYS = frozenset(
    {"verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean"}
)


def _scoring(*, static=50, dynamic=30, combined=70):
    def _block(v):
        return {"status": "scored", "score": v}

    return {
        "static": _block(static),
        "dynamic": _block(dynamic),
        "combined": _block(combined),
        "rubric_version": "1.0",
    }


def _correlation():
    return {
        "status": "correlated",
        "correlation": {
            "summary": "Static misconfig corroborated by a dynamic call-home.",
            "highest_correlation_severity": "high",
            "finding_count": 1,
            "findings": [
                {
                    "kind": "correlated",
                    "severity": "high",
                    "title": "Public bucket + exfil attempt",
                    "detail": "The world-readable bucket was read then POSTed outbound.",
                    "static_refs": ["S3-001"],
                    "behavioral_refs": ["net-egress-42"],
                }
            ],
        },
    }


def _remediation():
    return {
        "status": "assessed",
        "assessment": {
            "summary": "1 detailed finding, 1 candidate FP, 1 gap, 2 remediations.",
            "highest_finding_severity": "high",
            "highest_gap_severity": "high",
            "counts": {
                "detailed_finding_count": 1,
                "candidate_false_positive_count": 1,
                "gap_count": 1,
                "remediation_count": 2,
                "contradiction": 0,
            },
            "detailed_findings": [
                {
                    "kind": "correlated",
                    "severity": "high",
                    "title": "Public bucket + exfil attempt",
                    "detail": "Correlated static+dynamic.",
                    "static_refs": ["S3-001"],
                    "behavioral_refs": ["net-egress-42"],
                }
            ],
            "candidate_false_positives": [
                {
                    "severity": "low",
                    "title": "Unused open port flagged statically",
                    "detail": "No dynamic activity on it.",
                    "static_refs": ["PORT-9"],
                }
            ],
            "gaps": [
                {
                    "gap_type": "static_uncorroborated",
                    "severity": "high",
                    "title": "Static finding not observed dynamically",
                    "detail": "Needs a human look.",
                    "static_refs": ["S3-001"],
                    "behavioral_refs": [],
                }
            ],
            "prioritized_remediations": [
                {
                    "rank": 1,
                    "priority": "high",
                    "title": "Lock down the public bucket",
                    "action": "Set the bucket to private and review egress.",
                    "basis": "highest risk score 70 (combined); source severity high.",
                    "source_kind": "correlated",
                    "severity": "high",
                    "static_refs": ["S3-001"],
                    "behavioral_refs": ["net-egress-42"],
                },
                {
                    "rank": 2,
                    "priority": "medium",
                    "title": "Review the uncorroborated finding",
                    "action": "Confirm whether the static finding is exploitable.",
                    "basis": "gap static_uncorroborated; severity high.",
                    "source_kind": "static_uncorroborated",
                    "severity": "high",
                    "static_refs": ["S3-001"],
                    "behavioral_refs": [],
                },
            ],
        },
    }


def _verdict(rv="INCONCLUSIVE"):
    return {
        "status": "recommended",
        "recommended_verdict": rv,
        "rubric_version": "1.0",
        "recommendation_basis": {
            "summary": (
                "ADVISORY recommendation INCONCLUSIVE: combined risk score 70/100. "
                "A human must actively select PASS or FAIL at the dashboard gate."
            )
        },
    }


def _item(intake_id=_INTAKE_ID, sha256=_SHA256, **parts):
    it = {"intake_id": intake_id, "sha256": sha256, "status": "RECEIVED",
          "received_at": "2026-09-13T16:00:00Z"}
    it.update(parts)
    return it


def _build(item):
    return report.build_report(
        item,
        intake_id=item["intake_id"],
        sha256=item["sha256"],
        assembled_at=_ASSEMBLED_AT,
        contract_version="1.0",
        status_contract_version="1.0",
    )


def _full_item():
    return _item(
        combined_event={},
        correlation_result=_correlation(),
        scoring_result=_scoring(),
        remediation_result=_remediation(),
        verdict_result=_verdict(),
    )


class TestVendoredStatusModelNoDrift(unittest.TestCase):
    """The hub_report status_model.py is a VENDORED copy of the canonical hub_status one
    (each Lambda dir is bundled as its own asset, so cross-dir import is impossible at
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
        self.assertEqual(vh, ch, "hub_report/status_model.py drifted from canonical")


class TestExecutiveTier(unittest.TestCase):
    def test_reuses_4_1_read_model_core(self):
        item = _full_item()
        rpt = _build(item)
        ex = rpt["executive"]
        # The executive tier's recommendation matches the 4.1 read-model's.
        status_view = status_model.build_status(
            item, intake_id=_INTAKE_ID, sha256=_SHA256,
            assembled_at=_ASSEMBLED_AT, contract_version="1.0",
        )
        self.assertEqual(ex["overall_stage"], status_view["overall_stage"])
        self.assertEqual(ex["combined_score"], 70)
        self.assertEqual(ex["recommendation"]["recommended_verdict"], "INCONCLUSIVE")
        self.assertEqual(ex["recommendation"]["decision"], "pending")
        self.assertIs(ex["recommendation"]["advisory"], True)
        self.assertIn("summary", ex["recommendation"])

    def test_no_scores_no_verdict_is_honest(self):
        rpt = _build(_item())  # bare intake, nothing processed
        ex = rpt["executive"]
        self.assertEqual(ex["overall_stage"], "received")
        self.assertNotIn("combined_score", ex)
        self.assertEqual(ex["recommendation"]["status"], "not_yet_recommended")
        self.assertNotIn("recommended_verdict", ex["recommendation"])


class TestSecurityTier(unittest.TestCase):
    def test_findings_and_gaps_from_assessment(self):
        rpt = _build(_full_item())
        sec = rpt["security"]
        self.assertEqual(sec["data_status"], "available")
        self.assertEqual(sec["finding_count"], 1)
        self.assertEqual(sec["gap_count"], 1)
        self.assertEqual(sec["findings"][0]["kind"], "correlated")
        self.assertEqual(sec["findings"][0]["behavioral_refs"], ["net-egress-42"])
        self.assertEqual(sec["highest_finding_severity"], "high")
        self.assertEqual(sec["highest_correlation_severity"], "high")

    def test_mitre_and_sigma_not_carried(self):
        sec = _build(_full_item())["security"]
        self.assertEqual(sec["mitre_attack"]["status"], "not_carried_on_hub")
        self.assertEqual(sec["sigma_rules"]["status"], "not_carried_on_hub")

    def test_pending_when_no_assessment(self):
        sec = _build(_item(correlation_result=_correlation()))["security"]
        self.assertEqual(sec["data_status"], "pending")
        self.assertEqual(sec["finding_count"], 0)
        self.assertEqual(sec["findings"], [])
        # even pending, the not-carried markers are present (stable shape)
        self.assertEqual(sec["mitre_attack"]["status"], "not_carried_on_hub")


class TestDeveloperTier(unittest.TestCase):
    def test_remediations_ranked(self):
        dev = _build(_full_item())["developer"]
        self.assertEqual(dev["data_status"], "available")
        self.assertEqual(dev["remediation_count"], 2)
        self.assertEqual([r["rank"] for r in dev["prioritized_remediations"]], [1, 2])
        self.assertEqual(dev["prioritized_remediations"][0]["priority"], "high")
        self.assertEqual(dev["candidate_false_positive_count"], 1)

    def test_file_line_not_carried(self):
        dev = _build(_full_item())["developer"]
        self.assertEqual(dev["source_location"]["status"], "not_carried_on_hub")

    def test_pending_when_no_assessment(self):
        dev = _build(_item())["developer"]
        self.assertEqual(dev["data_status"], "pending")
        self.assertEqual(dev["prioritized_remediations"], [])
        self.assertEqual(dev["source_location"]["status"], "not_carried_on_hub")

    def test_rank_as_decimal_is_accepted(self):
        # REGRESSION (found live 2026-09-13): boto3.resource deserializes a DynamoDB Number
        # to Decimal, so `rank` arrives as Decimal(1), not int(1). A strict isinstance(int)
        # guard wrongly dropped every remediation -> remediations: 0. `rank` must be coerced.
        from decimal import Decimal

        rem = _remediation()
        for r in rem["assessment"]["prioritized_remediations"]:
            r["rank"] = Decimal(r["rank"])
        item = _full_item()
        item["remediation_result"] = rem
        dev = _build(item)["developer"]
        self.assertEqual(dev["remediation_count"], 2)
        self.assertEqual([r["rank"] for r in dev["prioritized_remediations"]], [1, 2])
        # the coerced rank is a plain int (JSON-serializable), not a Decimal
        self.assertIsInstance(dev["prioritized_remediations"][0]["rank"], int)


class TestNoEffectiveVerdictKey(unittest.TestCase):
    """RD-040: the report carries only the ADVISORY recommended_verdict, never a bare
    effective-verdict key."""

    def _walk_keys(self, obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                yield k
                yield from self._walk_keys(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from self._walk_keys(v)

    def test_no_banned_key_anywhere(self):
        rpt = _build(_full_item())
        keys = set(self._walk_keys(rpt))
        self.assertIn("recommended_verdict", keys)
        self.assertFalse(keys & _BANNED_EFFECTIVE_KEYS,
                         f"banned effective-verdict key present: {keys & _BANNED_EFFECTIVE_KEYS}")


class TestHtmlRender(unittest.TestCase):
    def test_renders_self_contained_html(self):
        html = report.render_html(_build(_full_item()))
        self.assertTrue(html.startswith("<!doctype html>"))
        self.assertIn("<style>", html)  # inline CSS, self-contained
        self.assertIn("Executive", html)
        self.assertIn("Security", html)
        self.assertIn("Developer", html)
        self.assertIn("advisory only", html)
        self.assertIn("not available on Hub", html)  # the not-carried markers render

    def test_escapes_derived_values_no_injection(self):
        # A hostile derived string must be escaped, never injected as HTML.
        rem = _remediation()
        rem["assessment"]["prioritized_remediations"][0]["title"] = "<script>alert(1)</script>"
        item = _full_item()
        item["remediation_result"] = rem
        html = report.render_html(_build(item))
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)

    def test_pending_tiers_render_without_error(self):
        html = report.render_html(_build(_item()))
        self.assertIn("not yet available", html)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
