"""Unit tests for the ZTIE Story 1.3 PURE routing table.

Pure-logic tests — no boto3, no AWS, no PyPI — so they run in the INTEGRATIONS_ONLY
build sandbox with plain ``unittest`` and also under ``pytest`` live. They pin the
Definition of Done: each classified type is routed to the CORRECT downstream lane
(IaC + raw-script fork into the static and dynamic lanes; other_unknown / any
unroutable class is handed to the safe-reject entry, Story 1.4, and NEVER crashes),
and a routing decision is a PLAN OF CONTROLS only (no verdict / forward field).

Run offline:  python3 -m unittest lambdas/preprocessor/test_router.py
"""

from __future__ import annotations

import unittest

from router import (
    DYNAMIC_DETONATION,
    IAC_TEMPLATE,
    OTHER_UNKNOWN,
    RAW_SCRIPT,
    SAFE_REJECT,
    STATIC_ANALYSIS,
    route,
)

# Fields a routing decision must NEVER carry — a routing decision is a plan of
# which controls apply, never a safety verdict and never a forward-to-PDE decision.
_FORBIDDEN_FIELDS = ("verdict", "safe", "approved", "forward", "route_to_pde", "status")


class TestRoutableClasses(unittest.TestCase):
    """The two routable classes fork into BOTH Phase-2 lanes."""

    def test_iac_template_routes_to_both_lanes(self):
        decision = route(IAC_TEMPLATE)
        self.assertEqual(decision["artifact_class"], IAC_TEMPLATE)
        self.assertEqual(decision["lanes"], [STATIC_ANALYSIS, DYNAMIC_DETONATION])
        self.assertTrue(decision["routable"])
        self.assertEqual(decision["basis"], "class_route")
        self.assertNotIn(SAFE_REJECT, decision["lanes"])

    def test_iac_template_hits_the_static_iac_linter_lane(self):
        # DoD: an IaC template lands in the static (IaC-linter) lane.
        self.assertIn(STATIC_ANALYSIS, route(IAC_TEMPLATE)["lanes"])

    def test_raw_script_routes_to_both_lanes(self):
        decision = route(RAW_SCRIPT)
        self.assertEqual(decision["artifact_class"], RAW_SCRIPT)
        self.assertEqual(decision["lanes"], [STATIC_ANALYSIS, DYNAMIC_DETONATION])
        self.assertTrue(decision["routable"])
        self.assertEqual(decision["basis"], "class_route")

    def test_raw_script_hits_the_dynamic_detonation_lane(self):
        # DoD: a raw script reaches its dynamic / detonation path.
        self.assertIn(DYNAMIC_DETONATION, route(RAW_SCRIPT)["lanes"])


class TestUnroutableClasses(unittest.TestCase):
    """other_unknown and any unrecognised class fail safe to safe-reject (1.4)."""

    def test_other_unknown_hands_to_safe_reject(self):
        decision = route(OTHER_UNKNOWN)
        self.assertEqual(decision["artifact_class"], OTHER_UNKNOWN)
        self.assertEqual(decision["lanes"], [SAFE_REJECT])
        self.assertFalse(decision["routable"])
        self.assertEqual(decision["basis"], "safe_reject_fallback")

    def test_other_unknown_never_reaches_a_scanner_lane(self):
        lanes = route(OTHER_UNKNOWN)["lanes"]
        self.assertNotIn(STATIC_ANALYSIS, lanes)
        self.assertNotIn(DYNAMIC_DETONATION, lanes)

    def test_unrecognised_class_fails_safe_not_crash(self):
        # A class the router has never seen must NOT raise and must NOT be dropped.
        decision = route("something_totally_unexpected")
        self.assertEqual(decision["lanes"], [SAFE_REJECT])
        self.assertFalse(decision["routable"])
        self.assertEqual(decision["basis"], "safe_reject_fallback")
        # Normalised to the known other_unknown class for the record...
        self.assertEqual(decision["artifact_class"], OTHER_UNKNOWN)
        # ...but the offending value is preserved in the audit note.
        self.assertIn("unrecognised class", decision["notes"])

    def test_none_class_fails_safe_not_crash(self):
        decision = route(None)
        self.assertEqual(decision["lanes"], [SAFE_REJECT])
        self.assertFalse(decision["routable"])
        self.assertEqual(decision["artifact_class"], OTHER_UNKNOWN)
        self.assertIn("missing", decision["notes"])

    def test_empty_string_class_fails_safe(self):
        decision = route("")
        self.assertEqual(decision["lanes"], [SAFE_REJECT])
        self.assertFalse(decision["routable"])


class TestRoutingDecisionShape(unittest.TestCase):
    """A routing decision is a PLAN OF CONTROLS — never a verdict."""

    def test_no_verdict_or_forward_field_on_any_class(self):
        for artifact_class in (IAC_TEMPLATE, RAW_SCRIPT, OTHER_UNKNOWN, "bogus", None):
            decision = route(artifact_class)
            for forbidden in _FORBIDDEN_FIELDS:
                self.assertNotIn(
                    forbidden,
                    decision,
                    f"routing decision for {artifact_class!r} must not carry "
                    f"{forbidden!r} (a routing decision is a plan of controls, "
                    f"never a verdict/forward decision)",
                )

    def test_required_fields_present_on_every_decision(self):
        for artifact_class in (IAC_TEMPLATE, RAW_SCRIPT, OTHER_UNKNOWN, "bogus"):
            decision = route(artifact_class)
            for field in ("artifact_class", "lanes", "routable", "basis"):
                self.assertIn(field, decision)
            self.assertIsInstance(decision["lanes"], list)
            self.assertGreaterEqual(len(decision["lanes"]), 1)

    def test_lanes_are_unique(self):
        for artifact_class in (IAC_TEMPLATE, RAW_SCRIPT, OTHER_UNKNOWN):
            lanes = route(artifact_class)["lanes"]
            self.assertEqual(len(lanes), len(set(lanes)))


if __name__ == "__main__":
    unittest.main()
