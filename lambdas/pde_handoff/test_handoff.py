"""ZTIE Story 4.6 (RD-047) — PURE gate + envelope-assembly tests (offline, stdlib).

These prove the FAIL-CLOSED ACCEPT gate + the verdict-free outcome envelope without
any AWS: they exercise ``handoff.evaluate_gate`` + ``handoff.build_handoff_envelope``
directly. The hardest invariant — nothing leaves Forensic absent a genuine accept +
a verified hash — is tested exhaustively here.
"""

from __future__ import annotations

import unittest

import handoff

_BANNED_VERDICT_KEYS = frozenset(
    {"verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean"}
)


def _no_banned_keys(obj, path="<root>"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in _BANNED_VERDICT_KEYS:
                return f"{path}.{k}"
            deeper = _no_banned_keys(v, f"{path}.{k}")
            if deeper:
                return deeper
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            deeper = _no_banned_keys(v, f"{path}[{i}]")
            if deeper:
                return deeper
    return None


class TestNormalizeDecision(unittest.TestCase):
    def test_known_values_pass_through(self):
        self.assertEqual(handoff.normalize_decision("accepted"), "accepted")
        self.assertEqual(handoff.normalize_decision("rejected"), "rejected")
        self.assertEqual(handoff.normalize_decision("pending"), "pending")

    def test_case_and_whitespace_folded(self):
        self.assertEqual(handoff.normalize_decision("  ACCEPTED "), "accepted")
        self.assertEqual(handoff.normalize_decision("Rejected"), "rejected")

    def test_absent_or_unknown_or_wrong_type_is_pending(self):
        # Fail-closed: anything not a known value collapses to pending (refuse).
        for raw in (None, "", "approve", "yes", "true", 1, True, {}, [], "PASS"):
            self.assertEqual(
                handoff.normalize_decision(raw),
                "pending",
                f"expected pending for {raw!r}",
            )


class TestEvaluateGate(unittest.TestCase):
    def test_accepted_and_verified_pushes(self):
        d = handoff.evaluate_gate(human_decision="accepted", hash_verified=True)
        self.assertTrue(d.push)
        self.assertEqual(d.outcome, handoff.OUTCOME_PUSHED)
        self.assertEqual(d.observed_decision, "accepted")

    def test_accepted_but_hash_mismatch_refuses(self):
        d = handoff.evaluate_gate(human_decision="accepted", hash_verified=False)
        self.assertFalse(d.push)
        self.assertEqual(d.outcome, handoff.OUTCOME_REFUSED_HASH_MISMATCH)
        self.assertEqual(d.observed_decision, "accepted")

    def test_pending_refuses_even_if_hash_ok(self):
        d = handoff.evaluate_gate(human_decision="pending", hash_verified=True)
        self.assertFalse(d.push)
        self.assertEqual(d.outcome, handoff.OUTCOME_REFUSED_NOT_ACCEPTED)
        self.assertEqual(d.observed_decision, "pending")

    def test_rejected_refuses_even_if_hash_ok(self):
        d = handoff.evaluate_gate(human_decision="rejected", hash_verified=True)
        self.assertFalse(d.push)
        self.assertEqual(d.outcome, handoff.OUTCOME_REFUSED_NOT_ACCEPTED)
        self.assertEqual(d.observed_decision, "rejected")

    def test_absent_decision_refuses(self):
        d = handoff.evaluate_gate(human_decision=None, hash_verified=True)
        self.assertFalse(d.push)
        self.assertEqual(d.outcome, handoff.OUTCOME_REFUSED_NOT_ACCEPTED)
        self.assertEqual(d.observed_decision, "pending")

    def test_advisory_verdict_like_value_never_pushes(self):
        # A recommended_verdict-shaped value (e.g. "PASS") is NOT an accept.
        d = handoff.evaluate_gate(human_decision="PASS", hash_verified=True)
        self.assertFalse(d.push)
        self.assertEqual(d.outcome, handoff.OUTCOME_REFUSED_NOT_ACCEPTED)

    def test_not_accepted_takes_precedence_over_hash(self):
        # When not accepted AND hash mismatched, the recorded reason is the
        # not-accepted refusal (the gate never even reaches the hash check).
        d = handoff.evaluate_gate(human_decision="pending", hash_verified=False)
        self.assertEqual(d.outcome, handoff.OUTCOME_REFUSED_NOT_ACCEPTED)


class TestBuildHandoffEnvelope(unittest.TestCase):
    def _base(self, decision, hash_verified, **kw):
        return handoff.build_handoff_envelope(
            intake_id="62360e03-dfb1-4655-ac52-2a55345ab6f0",
            sha256="a" * 64,
            handed_off_at="2026-09-13T00:00:00Z",
            decision=decision,
            hash_verified=hash_verified,
            artifact_s3_key="intake/62360e03-dfb1-4655-ac52-2a55345ab6f0/app.zip",
            size_bytes=1234,
            **kw,
        )

    def test_pushed_envelope_shape(self):
        decision = handoff.evaluate_gate(human_decision="accepted", hash_verified=True)
        env = self._base(
            decision,
            True,
            destination={
                "account_id": "586917955591",
                "bucket": "ztie-sandbox-landing",
                "prefix": "accepted/",
                "key": "accepted/62360e03-dfb1-4655-ac52-2a55345ab6f0/app.zip",
            },
            pushed_at="2026-09-13T00:00:01Z",
        )
        self.assertEqual(env["contract_version"], "1.0")
        self.assertEqual(env["handoff"]["outcome"], "pushed")
        self.assertEqual(env["handoff"]["observed_decision"], "accepted")
        self.assertTrue(env["handoff"]["hash_verified"])
        self.assertIn("destination", env["handoff"])
        self.assertEqual(env["handoff"]["destination"]["account_id"], "586917955591")
        self.assertIn("pushed_at", env["handoff"])

    def test_refused_envelope_carries_no_destination(self):
        decision = handoff.evaluate_gate(human_decision="pending", hash_verified=True)
        env = self._base(
            decision,
            True,
            destination={"account_id": "586917955591", "bucket": "x", "key": "y"},
            pushed_at="2026-09-13T00:00:01Z",
        )
        # Even if a destination is passed, a REFUSAL must not record one (fail-closed).
        self.assertEqual(env["handoff"]["outcome"], "refused_not_accepted")
        self.assertNotIn("destination", env["handoff"])
        self.assertNotIn("pushed_at", env["handoff"])

    def test_hash_mismatch_refusal_records_hash_false(self):
        decision = handoff.evaluate_gate(human_decision="accepted", hash_verified=False)
        env = self._base(decision, False)
        self.assertEqual(env["handoff"]["outcome"], "refused_hash_mismatch")
        self.assertFalse(env["handoff"]["hash_verified"])
        self.assertNotIn("destination", env["handoff"])

    def test_reason_is_bounded(self):
        decision = handoff.evaluate_gate(human_decision="pending", hash_verified=True)
        env = self._base(decision, True)
        self.assertLessEqual(len(env["handoff"]["reason"]), 512)

    def test_no_verdict_key_anywhere(self):
        for hd, hv in (("accepted", True), ("pending", True), ("accepted", False)):
            decision = handoff.evaluate_gate(human_decision=hd, hash_verified=hv)
            env = self._base(
                decision,
                hv,
                destination={"account_id": "586917955591", "bucket": "x", "key": "y"}
                if decision.push
                else None,
                pushed_at="2026-09-13T00:00:01Z" if decision.push else None,
            )
            offending = _no_banned_keys(env)
            self.assertIsNone(offending, f"verdict-shaped key present: {offending}")


if __name__ == "__main__":
    unittest.main()
