"""ZTIE Story 4.7 (RD-047/RD-048/RD-049) — PURE reject gate + envelope tests (offline).

These prove the FAIL-SAFE token-verify REJECT gate + the verdict-free outcome envelope
without any AWS and without real crypto: they exercise ``reject.evaluate_reject_gate``
(which delegates to the vendored ``verify.verify_decision`` with
``expected_decision="rejected"``) with an INJECTED signature verifier, plus
``reject.build_disposition_envelope``. The hardest invariant — nothing is destroyed
absent a valid Hub-signed ``rejected`` token bound to these exact bytes, and
INCONCLUSIVE (no token) HOLDS — is tested from every angle.
"""

from __future__ import annotations

import datetime as _dt
import unittest

import reject

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
        "decision": "rejected",
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
    return reject.evaluate_reject_gate(**kw)


class TestGateDestroys(unittest.TestCase):
    def test_valid_signed_rejected_token_destroys(self):
        d = _gate(_token())
        self.assertTrue(d.destroy)
        self.assertEqual(d.outcome, reject.OUTCOME_DESTROYED)
        self.assertEqual(d.observed_decision, "rejected")


class TestGateHoldsOnNoToken(unittest.TestCase):
    """INCONCLUSIVE issues NO token — the fail-safe HOLD path. Distinct from a
    presented-but-refused token."""

    def test_no_token_holds_no_crypto(self):
        # token=None => hold, WITHOUT invoking the verifier (assert by passing a
        # verifier that would explode if called).
        def _boom(msg, sig, pub):
            raise AssertionError("verifier must not be called when no token present")

        d = _gate(None, signature=None, verify_signature=_boom)
        self.assertFalse(d.destroy)
        self.assertEqual(d.outcome, reject.OUTCOME_HELD)
        self.assertEqual(d.observed_decision, "pending")

    def test_token_without_signature_holds(self):
        d = _gate(_token(), signature=None)
        self.assertFalse(d.destroy)
        self.assertEqual(d.outcome, reject.OUTCOME_HELD)

    def test_non_dict_token_holds(self):
        d = _gate("not-a-dict")
        self.assertFalse(d.destroy)
        self.assertEqual(d.outcome, reject.OUTCOME_HELD)


class TestGateFailClosed(unittest.TestCase):
    """A token WAS presented but does not authorize a destroy => refuse (destroy
    nothing). Every angle."""

    def test_bad_signature_refuses(self):
        d = _gate(_token(), verify_signature=_always_false)
        self.assertFalse(d.destroy)
        self.assertEqual(d.outcome, reject.OUTCOME_REFUSED_NOT_REJECTED)

    def test_accepted_token_refuses(self):
        # A signed 'accepted' token does NOT authorize a destroy (that is 4.6's push).
        d = _gate(_token(decision="accepted"))
        self.assertFalse(d.destroy)
        self.assertEqual(d.outcome, reject.OUTCOME_REFUSED_NOT_REJECTED)
        self.assertEqual(d.observed_decision, "accepted")

    def test_sha_mismatch_refuses_as_hash_mismatch(self):
        d = _gate(_token(), artifact_sha256="b" * 64)
        self.assertFalse(d.destroy)
        self.assertEqual(d.outcome, reject.OUTCOME_REFUSED_HASH_MISMATCH)

    def test_stale_token_refuses(self):
        d = _gate(_token(issued_at="2026-09-14T10:00:00Z"), max_age_seconds=3600)
        self.assertFalse(d.destroy)
        self.assertEqual(d.outcome, reject.OUTCOME_REFUSED_NOT_REJECTED)

    def test_future_token_refuses(self):
        d = _gate(_token(issued_at="2026-09-14T14:00:00Z"), max_age_seconds=3600)
        self.assertFalse(d.destroy)
        self.assertEqual(d.outcome, reject.OUTCOME_REFUSED_NOT_REJECTED)

    def test_untrusted_key_refuses(self):
        d = _gate(_token(key_id="rogue"))
        self.assertFalse(d.destroy)
        self.assertEqual(d.outcome, reject.OUTCOME_REFUSED_NOT_REJECTED)

    def test_injected_verdict_key_refuses(self):
        t = _token()
        t["verdict"] = "malicious"  # extra key breaks the exact-keys shape check
        d = _gate(t)
        self.assertFalse(d.destroy)

    def test_wrong_contract_version_refuses(self):
        d = _gate(_token(contract_version="9.9"))
        self.assertFalse(d.destroy)

    def test_advisory_recommended_verdict_never_destroys(self):
        # There is NO code path where the advisory verdict is even consulted — the gate
        # only ever looks at a SIGNED token. Simulate "the caller passes no token but a
        # recommended_verdict of FAIL lives elsewhere": still a hold.
        d = _gate(None, signature=None)
        self.assertFalse(d.destroy)
        self.assertEqual(d.outcome, reject.OUTCOME_HELD)


class TestBuildEnvelope(unittest.TestCase):
    def test_destroyed_envelope_shape(self):
        d = _gate(_token())
        env = reject.build_disposition_envelope(
            intake_id=_INTAKE,
            sha256=_SHA,
            disposed_at="2026-09-14T00:00:00Z",
            decision=d,
            hash_verified=True,
            chamber_state=reject.CHAMBER_TERMINATED,
            artifact_s3_key=f"intake/{_INTAKE}/app.zip",
            destroyed={
                "artifact_versions_deleted": 3,
                "prefixes_cleared": [f"intake/{_INTAKE}/", f"runs/{_INTAKE}/"],
                "chamber": "terminated",
                "chamber_instance_id": "i-0abc",
                "destroyed_at": "2026-09-14T00:00:01Z",
            },
        )
        self.assertEqual(env["disposition"]["outcome"], "destroyed")
        self.assertEqual(env["disposition"]["observed_decision"], "rejected")
        self.assertTrue(env["disposition"]["report_survives"])
        self.assertEqual(env["disposition"]["chamber_state"], "terminated")
        self.assertIn("destroyed", env["disposition"])
        self.assertEqual(env["disposition"]["destroyed"]["artifact_versions_deleted"], 3)

    def test_hold_carries_no_destroyed_block(self):
        d = _gate(None, signature=None)
        env = reject.build_disposition_envelope(
            intake_id=_INTAKE,
            sha256=_SHA,
            disposed_at="2026-09-14T00:00:00Z",
            decision=d,
            hash_verified=False,
            chamber_state=reject.CHAMBER_NOT_CHECKED,
            destroyed={"artifact_versions_deleted": 99, "prefixes_cleared": [], "chamber": "terminated"},
        )
        self.assertEqual(env["disposition"]["outcome"], "held")
        # A hold NEVER carries a destroyed block even if one is passed (decision.destroy
        # is False), so a caller bug can't fabricate a destroy record.
        self.assertNotIn("destroyed", env["disposition"])
        self.assertEqual(env["disposition"]["chamber_state"], "not_checked")
        self.assertTrue(env["disposition"]["report_survives"])

    def test_refusal_carries_no_destroyed_block(self):
        d = _gate(_token(decision="accepted"))
        env = reject.build_disposition_envelope(
            intake_id=_INTAKE,
            sha256=_SHA,
            disposed_at="2026-09-14T00:00:00Z",
            decision=d,
            hash_verified=False,
            chamber_state=reject.CHAMBER_NOT_CHECKED,
        )
        self.assertEqual(env["disposition"]["outcome"], "refused_not_rejected")
        self.assertNotIn("destroyed", env["disposition"])

    def test_report_survives_always_true(self):
        for d in (_gate(_token()), _gate(None, signature=None), _gate(_token(decision="accepted"))):
            env = reject.build_disposition_envelope(
                intake_id=_INTAKE, sha256=_SHA, disposed_at="2026-09-14T00:00:00Z",
                decision=d, hash_verified=d.destroy,
                chamber_state=reject.CHAMBER_NONE_RUNNING if d.destroy else reject.CHAMBER_NOT_CHECKED,
                destroyed={"artifact_versions_deleted": 0, "prefixes_cleared": [], "chamber": "none_running"} if d.destroy else None,
            )
            self.assertIs(env["disposition"]["report_survives"], True)

    def test_no_verdict_key_anywhere(self):
        for tok, sig in ((_token(), b"sig"), (None, None), (_token(decision="accepted"), b"sig")):
            d = _gate(tok, signature=sig)
            env = reject.build_disposition_envelope(
                intake_id=_INTAKE, sha256=_SHA, disposed_at="2026-09-14T00:00:00Z",
                decision=d, hash_verified=d.destroy,
                chamber_state=reject.CHAMBER_NONE_RUNNING if d.destroy else reject.CHAMBER_NOT_CHECKED,
                destroyed={"artifact_versions_deleted": 0, "prefixes_cleared": [], "chamber": "none_running"} if d.destroy else None,
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
