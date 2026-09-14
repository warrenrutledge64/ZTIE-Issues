"""ZTIE Story 4.6 rework (RD-047/RD-048/RD-049) — PURE gate + envelope tests (offline).

These prove the FAIL-CLOSED token-verify ACCEPT gate + the verdict-free outcome envelope
without any AWS and without real crypto: they exercise ``handoff.evaluate_token_gate``
(which delegates to the vendored ``verify.verify_decision``) with an INJECTED signature
verifier, plus ``handoff.build_handoff_envelope``. The hardest invariant — nothing pushes
absent a valid Hub-signed ``accepted`` token bound to these exact bytes — is tested from
every angle.
"""

from __future__ import annotations

import datetime as _dt
import unittest

import handoff

_INTAKE = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_SHA = "a" * 64
_KEY = "arn:aws:kms:us-east-1:641628980935:key/abcd-key-1"
_NOW = _dt.datetime(2026, 9, 14, 12, 0, 0, tzinfo=_dt.timezone.utc)

_BANNED_VERDICT_KEYS = frozenset(
    {"verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean"}
)


def _token(**over):
    t = {
        "contract_version": "1.0",
        "intake_id": _INTAKE,
        "decision": "accepted",
        "sha256": _SHA,
        "issued_at": "2026-09-14T11:59:00Z",  # 60s before _NOW
        "key_id": _KEY,
    }
    t.update(over)
    return t


def _always_true(msg, sig, pub):
    return True


def _always_false(msg, sig, pub):
    return False


def _gate(token, **over):
    kw = {
        "token": token,
        "signature": b"sig",
        "public_key_pem": b"-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----\n",
        "verify_signature": _always_true,
        "artifact_sha256": _SHA,
        "trusted_key_ids": [_KEY],
        "now": _NOW,
    }
    kw.update(over)
    return handoff.evaluate_token_gate(**kw)


class TestGatePushes(unittest.TestCase):
    def test_valid_signed_accepted_token_pushes(self):
        d = _gate(_token())
        self.assertTrue(d.push)
        self.assertEqual(d.outcome, handoff.OUTCOME_PUSHED)
        self.assertEqual(d.observed_decision, "accepted")


class TestGateFailClosed(unittest.TestCase):
    def test_bad_signature_refuses(self):
        d = _gate(_token(), verify_signature=_always_false)
        self.assertFalse(d.push)
        self.assertEqual(d.outcome, handoff.OUTCOME_REFUSED_NOT_ACCEPTED)

    def test_rejected_token_refuses(self):
        # A signed 'rejected' token does not authorize a push.
        d = _gate(_token(decision="rejected"))
        self.assertFalse(d.push)
        self.assertEqual(d.outcome, handoff.OUTCOME_REFUSED_NOT_ACCEPTED)
        self.assertEqual(d.observed_decision, "rejected")

    def test_sha_mismatch_refuses_as_hash_mismatch(self):
        d = _gate(_token(), artifact_sha256="b" * 64)
        self.assertFalse(d.push)
        self.assertEqual(d.outcome, handoff.OUTCOME_REFUSED_HASH_MISMATCH)

    def test_stale_token_refuses(self):
        d = _gate(_token(issued_at="2026-09-14T10:00:00Z"), max_age_seconds=3600)
        self.assertFalse(d.push)
        self.assertEqual(d.outcome, handoff.OUTCOME_REFUSED_NOT_ACCEPTED)

    def test_untrusted_key_refuses(self):
        d = _gate(_token(key_id="rogue"))
        self.assertFalse(d.push)
        self.assertEqual(d.outcome, handoff.OUTCOME_REFUSED_NOT_ACCEPTED)

    def test_malformed_token_refuses(self):
        d = _gate("not-a-dict")
        self.assertFalse(d.push)
        self.assertEqual(d.outcome, handoff.OUTCOME_REFUSED_NOT_ACCEPTED)

    def test_injected_verdict_key_refuses(self):
        t = _token()
        t["verdict"] = "safe"  # extra key breaks the exact-keys shape check
        d = _gate(t)
        self.assertFalse(d.push)

    def test_no_ok_without_signature(self):
        # An unsigned/spoke-asserted decision (verifier says false) can never push.
        self.assertFalse(_gate(_token(), verify_signature=_always_false).push)


class TestBuildEnvelope(unittest.TestCase):
    def test_pushed_envelope_shape(self):
        d = _gate(_token())
        env = handoff.build_handoff_envelope(
            intake_id=_INTAKE,
            sha256=_SHA,
            handed_off_at="2026-09-14T00:00:00Z",
            decision=d,
            hash_verified=True,
            artifact_s3_key=f"intake/{_INTAKE}/app.zip",
            size_bytes=1234,
            destination={"account_id": "586917955591", "bucket": "b", "prefix": "accepted/", "key": "accepted/x"},
            pushed_at="2026-09-14T00:00:01Z",
        )
        self.assertEqual(env["handoff"]["outcome"], "pushed")
        self.assertEqual(env["handoff"]["observed_decision"], "accepted")
        self.assertIn("destination", env["handoff"])

    def test_refusal_carries_no_destination(self):
        d = _gate(_token(), verify_signature=_always_false)
        env = handoff.build_handoff_envelope(
            intake_id=_INTAKE,
            sha256=_SHA,
            handed_off_at="2026-09-14T00:00:00Z",
            decision=d,
            hash_verified=True,
            destination={"account_id": "x", "bucket": "b", "key": "y"},
            pushed_at="2026-09-14T00:00:01Z",
        )
        self.assertEqual(env["handoff"]["outcome"], "refused_not_accepted")
        self.assertNotIn("destination", env["handoff"])
        self.assertNotIn("pushed_at", env["handoff"])

    def test_no_verdict_key_anywhere(self):
        for vs in (_always_true, _always_false):
            d = _gate(_token(), verify_signature=vs)
            env = handoff.build_handoff_envelope(
                intake_id=_INTAKE, sha256=_SHA, handed_off_at="2026-09-14T00:00:00Z",
                decision=d, hash_verified=True,
                destination={"account_id": "x", "bucket": "b", "key": "y"} if d.push else None,
                pushed_at="2026-09-14T00:00:01Z" if d.push else None,
            )

            def walk(o):
                if isinstance(o, dict):
                    for k, v in o.items():
                        yield k
                        yield from walk(v)
                elif isinstance(o, list):
                    for v in o:
                        yield from walk(v)

            self.assertFalse(set(walk(env)) & _BANNED_VERDICT_KEYS)


if __name__ == "__main__":
    unittest.main()
