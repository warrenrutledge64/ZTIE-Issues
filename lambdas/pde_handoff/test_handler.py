"""ZTIE Story 4.6 rework (RD-047/RD-048/RD-049) — handler tests (offline).

boto3 is STUBBED into ``sys.modules`` so ``handler`` + ``awsio`` import offline. The
``awsio`` seam is monkeypatched with an in-memory fake (which has NO Hub-read method —
proving the rework removed the spoke→Hub read), and the ECDSA verifier
(``signature.verify_ecdsa_p256_sha256``) is monkeypatched with a stub so the fail-closed
control flow is exercised without real crypto.

The hardest invariant is proven: NOTHING is pushed absent a valid Hub-signed ``accepted``
decision token bound to the recomputed artifact bytes.
"""

from __future__ import annotations

import base64
import datetime as _dt
import os
import sys
import types
import unittest

# --- Stub boto3 so handler.py + awsio.py import offline -----------------------
if "boto3" not in sys.modules:
    _boto3 = types.ModuleType("boto3")
    _boto3.client = lambda *a, **k: None
    _boto3.resource = lambda *a, **k: None
    sys.modules["boto3"] = _boto3

os.environ.setdefault("ARTIFACT_BUCKET", "ztie-forensic-artifacts")
os.environ.setdefault("SANDBOX_LANDING_BUCKET", "ztie-sandbox-landing")
os.environ.setdefault("SANDBOX_LANDING_PREFIX", "accepted/")
os.environ.setdefault("SANDBOX_ACCOUNT_ID", "586917955591")
os.environ.setdefault(
    "HUB_INGEST_QUEUE_URL",
    "https://sqs.us-east-1.amazonaws.com/641628980935/ztie-ingest",
)
os.environ.setdefault("HANDOFF_CONTRACT_VERSION", "1.0")
os.environ.setdefault(
    "HUB_PUBLIC_KEY_PEM", "-----BEGIN PUBLIC KEY-----\nMFkw\n-----END PUBLIC KEY-----\n"
)
os.environ.setdefault(
    "TRUSTED_KEY_IDS", "arn:aws:kms:us-east-1:641628980935:key/abcd-key-1"
)

import awsio
import handler
import signature as _sig

_INTAKE = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_SHA = "a" * 64  # the recomputed artifact sha the fake seam returns
_KEY = "arn:aws:kms:us-east-1:641628980935:key/abcd-key-1"
_ARTIFACT_KEY = f"intake/{_INTAKE}/app.zip"


def _now_issued():
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _token(**over):
    t = {
        "contract_version": "1.0",
        "intake_id": _INTAKE,
        "decision": "accepted",
        "sha256": _SHA,
        "issued_at": _now_issued(),
        "key_id": _KEY,
    }
    t.update(over)
    return t


def _event(token=None, sig=b"realsig", **over):
    ev = {
        "intake_id": _INTAKE,
        "decision_token": _token() if token is None else token,
        "signature": base64.b64encode(sig).decode(),
        "artifact_s3_key": _ARTIFACT_KEY,
    }
    ev.update(over)
    return ev


class _FakeSeam:
    """In-memory awsio seam. Deliberately has NO get_tracking_item (proves no Hub read)."""

    def __init__(self, *, artifact_sha=_SHA, size=4096, sweep_versions=4):
        self.artifact_sha = artifact_sha
        self.size = size
        self.pushes = []
        self.sent = []
        # Story 4.10 (RD-059): record post-accept sweeps + how many versions the fake
        # "deletes" so tests can assert the sweep fired + is recorded in the outcome.
        self.sweeps = []
        self.sweep_versions = sweep_versions

    def compute_artifact_sha256_and_size(self, bucket, key):
        return self.artifact_sha, self.size

    def push_artifact(self, *, source_bucket, source_key, dest_bucket, dest_key, metadata):
        self.pushes.append({"dest_bucket": dest_bucket, "dest_key": dest_key, "metadata": metadata})
        return "v-1"

    def destroy_intake_prefixes(self, bucket, prefixes):
        # Story 4.10 (RD-059): the post-accept Forensic sweep. Record the call + return
        # the reject-shaped result the handler folds into the crossed outcome.
        self.sweeps.append({"bucket": bucket, "prefixes": list(prefixes)})
        return {
            "versions_deleted": self.sweep_versions,
            "prefixes_cleared": list(prefixes),
        }

    def send_handoff_envelope(self, queue_url, envelope):
        self.sent.append((queue_url, envelope))


class HandlerTestBase(unittest.TestCase):
    def _install(self, seam, *, sig_ok=True):
        self.seam = seam
        self._orig = (
            awsio.compute_artifact_sha256_and_size,
            awsio.push_artifact,
            awsio.destroy_intake_prefixes,
            awsio.send_handoff_envelope,
            _sig.verify_ecdsa_p256_sha256,
        )
        awsio.compute_artifact_sha256_and_size = seam.compute_artifact_sha256_and_size
        awsio.push_artifact = seam.push_artifact
        awsio.destroy_intake_prefixes = seam.destroy_intake_prefixes
        awsio.send_handoff_envelope = seam.send_handoff_envelope
        _sig.verify_ecdsa_p256_sha256 = (lambda m, s, p: sig_ok)

    def tearDown(self):
        (
            awsio.compute_artifact_sha256_and_size,
            awsio.push_artifact,
            awsio.destroy_intake_prefixes,
            awsio.send_handoff_envelope,
            _sig.verify_ecdsa_p256_sha256,
        ) = self._orig

    def test_no_hub_read_method_on_seam(self):
        self._install(_FakeSeam())
        # The rework removed the cross-account Hub read: the seam has no such method.
        self.assertFalse(hasattr(awsio, "get_tracking_item"))


class TestAcceptPathPushes(HandlerTestBase):
    def test_valid_signed_accepted_token_pushes(self):
        self._install(_FakeSeam(), sig_ok=True)
        out = handler.handler(_event())
        self.assertTrue(out["pushed"])
        self.assertEqual(out["outcome"], "pushed")
        self.assertEqual(len(self.seam.pushes), 1)
        self.assertTrue(self.seam.pushes[0]["dest_key"].startswith("accepted/"))
        self.assertEqual(self.seam.pushes[0]["metadata"]["sha256"], _SHA)
        self.assertEqual(self.seam.sent[0][1]["handoff"]["outcome"], "pushed")

    def test_api_gateway_shape(self):
        self._install(_FakeSeam(), sig_ok=True)
        ev = {"pathParameters": {"intake_id": _INTAKE}, "decision_token": _token(),
              "signature": base64.b64encode(b"s").decode(), "artifact_s3_key": _ARTIFACT_KEY}
        self.assertTrue(handler.handler(ev)["pushed"])


class TestFailClosed(HandlerTestBase):
    def test_bad_signature_does_not_push(self):
        self._install(_FakeSeam(), sig_ok=False)
        out = handler.handler(_event())
        self.assertFalse(out["pushed"])
        self.assertEqual(out["outcome"], "refused_not_accepted")
        self.assertEqual(len(self.seam.pushes), 0)
        self.assertEqual(self.seam.sent[0][1]["handoff"]["outcome"], "refused_not_accepted")

    def test_rejected_token_does_not_push(self):
        self._install(_FakeSeam(), sig_ok=True)
        out = handler.handler(_event(token=_token(decision="rejected")))
        self.assertFalse(out["pushed"])
        self.assertEqual(len(self.seam.pushes), 0)

    def test_sha_mismatch_does_not_push(self):
        # Token says sha _SHA but the recomputed artifact differs -> hash mismatch refusal.
        self._install(_FakeSeam(artifact_sha="b" * 64), sig_ok=True)
        out = handler.handler(_event())
        self.assertFalse(out["pushed"])
        self.assertEqual(out["outcome"], "refused_hash_mismatch")
        self.assertEqual(len(self.seam.pushes), 0)

    def test_untrusted_key_does_not_push(self):
        self._install(_FakeSeam(), sig_ok=True)
        out = handler.handler(_event(token=_token(key_id="rogue")))
        self.assertFalse(out["pushed"])
        self.assertEqual(len(self.seam.pushes), 0)

    def test_stale_token_does_not_push(self):
        self._install(_FakeSeam(), sig_ok=True)
        old = "2000-01-01T00:00:00Z"
        out = handler.handler(_event(token=_token(issued_at=old)))
        self.assertFalse(out["pushed"])
        self.assertEqual(len(self.seam.pushes), 0)


class TestOD009PostAcceptSweep(HandlerTestBase):
    """Story 4.10 (RD-059) — the POST-ACCEPT Forensic sweep. On a verified accept that
    PUSHED (the artifact landed in the Sandbox), the pusher destroys the intake's Forensic
    prefixes (accept/reject symmetry, RD-012) and records the bounded sweep in the crossed
    outcome. On any REFUSAL, nothing is swept (nothing left Forensic, so nothing to clean)."""

    def test_push_sweeps_the_four_intake_prefixes(self):
        self._install(_FakeSeam(sweep_versions=6), sig_ok=True)
        out = handler.handler(_event())
        self.assertTrue(out["pushed"])
        # The sweep fired exactly once, over the intake's raw + derived prefixes.
        self.assertEqual(len(self.seam.sweeps), 1)
        self.assertEqual(self.seam.sweeps[0]["bucket"], handler.ARTIFACT_BUCKET)
        self.assertEqual(
            sorted(self.seam.sweeps[0]["prefixes"]),
            sorted(
                [
                    f"intake/{_INTAKE}/",
                    f"findings/{_INTAKE}/",
                    f"runs/{_INTAKE}/",
                    f"traces/{_INTAKE}/",
                ]
            ),
        )

    def test_push_records_forensic_sweep_in_crossed_outcome(self):
        self._install(_FakeSeam(sweep_versions=6), sig_ok=True)
        handler.handler(_event())
        crossed = self.seam.sent[0][1]["handoff"]
        self.assertIn("forensic_sweep", crossed)
        self.assertTrue(crossed["forensic_sweep"]["swept"])
        self.assertEqual(crossed["forensic_sweep"]["versions_deleted"], 6)
        self.assertEqual(len(crossed["forensic_sweep"]["prefixes_cleared"]), 4)

    def test_refusal_does_not_sweep(self):
        # A fail-closed refusal pushed nothing, so there is nothing to clean in Forensic.
        self._install(_FakeSeam(), sig_ok=False)
        out = handler.handler(_event())
        self.assertFalse(out["pushed"])
        self.assertEqual(len(self.seam.sweeps), 0)
        self.assertNotIn("forensic_sweep", self.seam.sent[0][1]["handoff"])

    def test_sweep_disabled_when_env_blank_is_backward_compatible(self):
        # A blank FORENSIC_SWEEP_PREFIX_TEMPLATES disables the sweep — the pusher behaves
        # exactly as the original push-only 4.6 (no sweep, no forensic_sweep block).
        self._install(_FakeSeam(), sig_ok=True)
        orig = handler.SWEEP_PREFIX_TEMPLATES
        handler.SWEEP_PREFIX_TEMPLATES = ""
        try:
            out = handler.handler(_event())
        finally:
            handler.SWEEP_PREFIX_TEMPLATES = orig
        self.assertTrue(out["pushed"])
        self.assertEqual(len(self.seam.sweeps), 0)
        self.assertNotIn("forensic_sweep", self.seam.sent[0][1]["handoff"])

    def test_no_verdict_key_in_swept_outcome(self):
        self._install(_FakeSeam(), sig_ok=True)
        handler.handler(_event())
        crossed = self.seam.sent[0][1]
        banned = ("verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean")
        blob = repr(crossed)
        for k in banned:
            self.assertNotIn(f"'{k}'", blob, f"banned verdict-shaped key {k!r} in outcome")


class TestErrorPaths(HandlerTestBase):
    def test_missing_intake_id_400_no_push(self):
        self._install(_FakeSeam())
        out = handler.handler({"decision_token": _token(), "signature": "x"})
        self.assertEqual(out["error"]["code"], 400)
        self.assertEqual(len(self.seam.pushes), 0)
        self.assertEqual(len(self.seam.sent), 0)

    def test_missing_token_400(self):
        self._install(_FakeSeam())
        out = handler.handler({"intake_id": _INTAKE, "signature": "x", "artifact_s3_key": _ARTIFACT_KEY})
        self.assertEqual(out["error"]["code"], 400)
        self.assertEqual(len(self.seam.pushes), 0)

    def test_token_intake_mismatch_400(self):
        self._install(_FakeSeam())
        tok = _token(intake_id="11111111-1111-4111-8111-111111111111")
        out = handler.handler(_event(token=tok))
        self.assertEqual(out["error"]["code"], 400)

    def test_bad_base64_signature_400(self):
        self._install(_FakeSeam())
        out = handler.handler({"intake_id": _INTAKE, "decision_token": _token(),
                               "signature": "!!!not-base64!!!", "artifact_s3_key": _ARTIFACT_KEY})
        self.assertEqual(out["error"]["code"], 400)

    def test_artifact_key_outside_intake_prefix_400(self):
        self._install(_FakeSeam())
        out = handler.handler(_event(artifact_s3_key="intake/other/evil.zip"))
        self.assertEqual(out["error"]["code"], 400)
        self.assertEqual(len(self.seam.pushes), 0)

    def test_missing_artifact_locator_400(self):
        self._install(_FakeSeam())
        ev = {"intake_id": _INTAKE, "decision_token": _token(),
              "signature": base64.b64encode(b"s").decode()}
        out = handler.handler(ev)
        self.assertEqual(out["error"]["code"], 400)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
