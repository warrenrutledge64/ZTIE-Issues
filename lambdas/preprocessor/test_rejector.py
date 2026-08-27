"""Unit tests for the ZTIE Story 1.4 PURE safe-reject decision.

Pure-logic tests — no boto3, no AWS, no PyPI — so they run in the INTEGRATIONS_ONLY
build sandbox with plain ``unittest`` and also under ``pytest`` live. They pin the
Definition of Done: an unroutable artifact is safe-rejected (cleanly, terminally,
never crashed), and a routable artifact is NOT safe-rejected.

Run offline:  python3 -m unittest lambdas/preprocessor/test_rejector.py
"""

from __future__ import annotations

import unittest

from rejector import PIPELINE_OUTCOME, REASON_UNROUTABLE, reject

# Fields a reject outcome must NEVER carry.
_FORBIDDEN_FIELDS = ("verdict", "safe", "approved", "forward", "route_to_pde", "status")


def _unroutable_decision(artifact_class: str = "other_unknown", notes: str | None = None) -> dict:
    d: dict = {
        "artifact_class": artifact_class,
        "lanes": ["safe_reject"],
        "routable": False,
        "basis": "safe_reject_fallback",
    }
    if notes:
        d["notes"] = notes
    return d


def _routable_decision() -> dict:
    return {
        "artifact_class": "iac_template",
        "lanes": ["static_analysis", "dynamic_detonation"],
        "routable": True,
        "basis": "class_route",
    }


class TestUnroutableRejection(unittest.TestCase):
    """An unroutable artifact is safe-rejected cleanly."""

    def test_other_unknown_produces_safe_rejected(self):
        result = reject(_unroutable_decision())
        self.assertEqual(result["pipeline_outcome"], PIPELINE_OUTCOME)
        self.assertEqual(result["reason"], REASON_UNROUTABLE)
        self.assertEqual(result["artifact_class"], "other_unknown")

    def test_notes_carried_from_routing_decision(self):
        result = reject(_unroutable_decision(notes="unrecognised class 'xyz'"))
        self.assertEqual(result["notes"], "unrecognised class 'xyz'")

    def test_no_notes_when_absent_from_decision(self):
        result = reject(_unroutable_decision())
        self.assertNotIn("notes", result)

    def test_notes_bounded_to_256(self):
        long_note = "x" * 500
        result = reject(_unroutable_decision(notes=long_note))
        self.assertLessEqual(len(result["notes"]), 256)

    def test_never_crashes_on_empty_decision(self):
        result = reject({"routable": False})
        self.assertEqual(result["pipeline_outcome"], PIPELINE_OUTCOME)
        self.assertEqual(result["artifact_class"], "other_unknown")


class TestRoutableNotRejected(unittest.TestCase):
    """A routable artifact must NOT be safe-rejected."""

    def test_routable_returns_none(self):
        result = reject(_routable_decision())
        self.assertIsNone(result)

    def test_routable_true_explicit(self):
        self.assertIsNone(reject({"routable": True, "artifact_class": "iac_template"}))


class TestRejectOutcomeShape(unittest.TestCase):
    """The rejection outcome is a terminal processing outcome, never a verdict."""

    def test_no_verdict_or_forward_field(self):
        result = reject(_unroutable_decision())
        for forbidden in _FORBIDDEN_FIELDS:
            self.assertNotIn(
                forbidden,
                result,
                f"reject outcome must not carry {forbidden!r}",
            )

    def test_required_fields_present(self):
        result = reject(_unroutable_decision())
        for field in ("pipeline_outcome", "reason", "artifact_class"):
            self.assertIn(field, result)

    def test_pipeline_outcome_is_safe_rejected(self):
        result = reject(_unroutable_decision())
        self.assertEqual(result["pipeline_outcome"], "SAFE_REJECTED")


if __name__ == "__main__":
    unittest.main()
