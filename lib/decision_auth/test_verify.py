"""ZTIE Story H.2 (RD-048/RD-049) — offline tests for the fail-closed verify gate.

PURE stdlib, fully offline. The raw signature check is INJECTED as a stub verifier so
these tests exercise every fail-closed branch WITHOUT the bundled ``cryptography`` dep
(the real ECDSA verify is proven in the LIVE validation). Test vectors cover: valid,
bad-signature, wrong-decision, sha-mismatch, stale/not-yet, untrusted-key, and every
malformed-shape refusal.
"""

from __future__ import annotations

import datetime as _dt
import unittest

import canonical
import verify

_INTAKE = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_SHA = "a" * 64
_KEY = "arn:aws:kms:us-east-1:641628980935:key/abcd-key-1"
_NOW = _dt.datetime(2026, 9, 13, 12, 0, 0, tzinfo=_dt.timezone.utc)


def _token(**over):
    t = {
        "contract_version": "1.0",
        "intake_id": _INTAKE,
        "decision": "accepted",
        "sha256": _SHA,
        "issued_at": "2026-09-13T11:59:00Z",  # 60s before _NOW
        "key_id": _KEY,
    }
    t.update(over)
    return t


def _always_true(msg, sig, pub):
    return True


def _always_false(msg, sig, pub):
    return False


def _raises(msg, sig, pub):
    raise RuntimeError("boom")


def _verify(token, **over):
    kw = {
        "token": token,
        "signature": b"sig",
        "public_key_pem": b"-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----\n",
        "verify_signature": _always_true,
        "expected_decision": "accepted",
        "artifact_sha256": _SHA,
        "trusted_key_ids": [_KEY],
        "now": _NOW,
    }
    kw.update(over)
    return verify.verify_decision(**kw)


class TestHappyPath(unittest.TestCase):
    def test_all_checks_pass(self):
        r = _verify(_token())
        self.assertTrue(r.ok, r.reason)
        self.assertEqual(r.code, "ok")

    def test_rejected_decision_for_a_destroy(self):
        # A 'rejected' token authorizes a destroy (expected_decision='rejected').
        r = _verify(_token(decision="rejected"), expected_decision="rejected")
        self.assertTrue(r.ok, r.reason)


class TestSignature(unittest.TestCase):
    def test_bad_signature_refuses(self):
        r = _verify(_token(), verify_signature=_always_false)
        self.assertFalse(r.ok)
        self.assertEqual(r.code, "bad_signature")

    def test_verifier_exception_is_failclosed(self):
        r = _verify(_token(), verify_signature=_raises)
        self.assertFalse(r.ok)
        self.assertEqual(r.code, "bad_signature")

    def test_signature_is_over_canonical_bytes(self):
        # The message handed to the verifier must be the canonical bytes.
        seen = {}

        def _capture(msg, sig, pub):
            seen["msg"] = msg
            return True

        tok = _token()
        _verify(tok, verify_signature=_capture)
        self.assertEqual(seen["msg"], canonical.canonical_bytes(tok))


class TestDecision(unittest.TestCase):
    def test_wrong_decision_refuses(self):
        # An 'accepted' token must NOT authorize a destroy.
        r = _verify(_token(decision="accepted"), expected_decision="rejected")
        self.assertFalse(r.ok)
        self.assertEqual(r.code, "wrong_decision")


class TestArtifactBinding(unittest.TestCase):
    def test_sha_mismatch_refuses(self):
        r = _verify(_token(), artifact_sha256="b" * 64)
        self.assertFalse(r.ok)
        self.assertEqual(r.code, "sha_mismatch")

    def test_artifact_sha_case_insensitive_match(self):
        # Token sha is lowercase; a recomputed upper-case hash still matches.
        r = _verify(_token(), artifact_sha256=("A" * 64))
        self.assertTrue(r.ok, r.reason)

    def test_bad_artifact_sha_refuses(self):
        r = _verify(_token(), artifact_sha256="not-a-hash")
        self.assertFalse(r.ok)
        self.assertEqual(r.code, "bad_artifact_sha")


class TestFreshness(unittest.TestCase):
    def test_stale_refuses(self):
        old = "2026-09-13T10:00:00Z"  # 2h before _NOW, > 1h window
        r = _verify(_token(issued_at=old))
        self.assertFalse(r.ok)
        self.assertEqual(r.code, "stale")

    def test_within_window_ok(self):
        r = _verify(_token(issued_at="2026-09-13T11:30:00Z"), max_age_seconds=3600)
        self.assertTrue(r.ok, r.reason)

    def test_future_beyond_skew_refuses(self):
        future = "2026-09-13T14:00:00Z"  # 2h in the future
        r = _verify(_token(issued_at=future))
        self.assertFalse(r.ok)
        self.assertEqual(r.code, "not_yet_valid")

    def test_unparseable_issued_at_refuses(self):
        r = _verify(_token(issued_at="not-a-time"))
        self.assertFalse(r.ok)
        self.assertEqual(r.code, "bad_shape")

    def test_naive_issued_at_refuses(self):
        # No timezone -> refused (we require Z/offset).
        r = _verify(_token(issued_at="2026-09-13T11:59:00"))
        self.assertFalse(r.ok)
        self.assertEqual(r.code, "bad_shape")


class TestKeyTrust(unittest.TestCase):
    def test_untrusted_key_refuses(self):
        r = _verify(_token(key_id="arn:aws:kms:...:key/rogue"))
        self.assertFalse(r.ok)
        self.assertEqual(r.code, "untrusted_key")

    def test_key_rotation_set_ok(self):
        # A spoke may trust a SET of keys during rotation.
        r = _verify(_token(), trusted_key_ids=["old-key", _KEY, "new-key"])
        self.assertTrue(r.ok, r.reason)


class TestShapeGuards(unittest.TestCase):
    def test_not_a_dict(self):
        r = _verify("nope")
        self.assertFalse(r.ok)
        self.assertEqual(r.code, "bad_shape")

    def test_extra_key_refuses(self):
        t = _token()
        t["verdict"] = "safe"  # a smuggled field must break the exact-keys check
        r = _verify(t)
        self.assertFalse(r.ok)
        self.assertEqual(r.code, "bad_shape")

    def test_missing_key_refuses(self):
        t = _token()
        del t["sha256"]
        r = _verify(t)
        self.assertFalse(r.ok)
        self.assertEqual(r.code, "bad_shape")

    def test_bad_version_refuses(self):
        r = _verify(_token(contract_version="2.0"))
        self.assertFalse(r.ok)
        self.assertEqual(r.code, "bad_version")

    def test_bad_intake_id_refuses(self):
        r = _verify(_token(intake_id="not-a-uuid"))
        self.assertFalse(r.ok)
        self.assertEqual(r.code, "bad_shape")

    def test_bad_decision_enum_refuses(self):
        r = _verify(_token(decision="maybe"))
        self.assertFalse(r.ok)
        self.assertEqual(r.code, "bad_shape")

    def test_no_ok_without_all_checks(self):
        # Belt-and-suspenders: the only ok=True path is the fully-valid token.
        self.assertFalse(_verify(_token(), verify_signature=_always_false).ok)
        self.assertFalse(_verify(_token(decision="rejected")).ok)  # wrong for accepted
        self.assertFalse(_verify(_token(), artifact_sha256="b" * 64).ok)
        self.assertFalse(_verify(_token(key_id="rogue")).ok)


class TestCanonical(unittest.TestCase):
    def test_deterministic_and_sorted(self):
        t = _token()
        # Reordering the dict must not change the canonical bytes.
        reordered = {k: t[k] for k in reversed(list(t.keys()))}
        self.assertEqual(canonical.canonical_bytes(t), canonical.canonical_bytes(reordered))

    def test_only_signed_keys_included(self):
        t = _token()
        t["extra"] = "ignored"
        # canonical drops extras (they are not signed).
        self.assertNotIn(b"extra", canonical.canonical_bytes(t))

    def test_no_whitespace(self):
        b = canonical.canonical_bytes(_token())
        self.assertNotIn(b", ", b)
        self.assertNotIn(b": ", b)


if __name__ == "__main__":
    unittest.main()
