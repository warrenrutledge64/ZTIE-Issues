"""ZTIE Story 4.7 (RD-047/RD-048/RD-049) — handler tests (offline).

boto3 is STUBBED into ``sys.modules`` so ``handler`` + ``awsio`` import offline. The
``awsio`` seam is monkeypatched with an in-memory fake (which has NO Hub-read method —
proving there is no spoke->Hub read; it records whether a DESTROY / TERMINATE happened),
and the ECDSA verifier (``signature.verify_ecdsa_p256_sha256``) is monkeypatched with a
stub so the fail-safe control flow is exercised without real crypto.

The hardest invariant is proven: NOTHING is destroyed absent a valid Hub-signed
``rejected`` decision token bound to the recomputed artifact bytes, and INCONCLUSIVE
(no token) HOLDS. Tested from every angle.
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
os.environ.setdefault(
    "HUB_INGEST_QUEUE_URL",
    "https://sqs.us-east-1.amazonaws.com/641628980935/ztie-ingest",
)
os.environ.setdefault("DISPOSITION_CONTRACT_VERSION", "1.0")
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
        "decision": "rejected",
        "sha256": _SHA,
        "issued_at": _now_issued(),
        "key_id": _KEY,
    }
    t.update(over)
    return t


def _event(token="__default__", sig=b"realsig", **over):
    ev = {
        "intake_id": _INTAKE,
        "artifact_s3_key": _ARTIFACT_KEY,
    }
    if token == "__default__":
        ev["decision_token"] = _token()
    elif token is not None:
        ev["decision_token"] = token
    if sig is not None:
        ev["signature"] = base64.b64encode(sig).decode()
    ev.update(over)
    return ev


class _FakeSeam:
    """In-memory awsio seam. Deliberately has NO get_tracking_item (proves no Hub read).
    Records whether a destroy / terminate happened so the fail-safe invariant can be
    asserted directly (not merely via the returned outcome)."""

    def __init__(self, *, artifact_sha=_SHA, size=4096, versions_deleted=3,
                 running_chamber=None, missing_artifact=False):
        self.artifact_sha = artifact_sha
        self.size = size
        self.versions_deleted = versions_deleted
        self.running_chamber = running_chamber  # instance id or None
        self.missing_artifact = missing_artifact
        # Recorders — the proof surface.
        self.destroy_calls = []       # list of (bucket, prefixes)
        self.terminate_calls = []     # list of instance ids
        self.sent = []                # list of (queue_url, envelope)

    def compute_artifact_sha256_and_size(self, bucket, key):
        if self.missing_artifact:
            raise RuntimeError("NoSuchKey: artifact already gone")
        return self.artifact_sha, self.size

    def destroy_intake_prefixes(self, bucket, prefixes):
        self.destroy_calls.append((bucket, list(prefixes)))
        return {"versions_deleted": self.versions_deleted, "prefixes_cleared": list(prefixes)}

    def find_running_chamber(self, intake_id):
        return self.running_chamber

    def terminate_chamber(self, instance_id):
        self.terminate_calls.append(instance_id)

    def send_disposition_envelope(self, queue_url, envelope):
        self.sent.append((queue_url, envelope))


class HandlerTestBase(unittest.TestCase):
    def _install(self, seam, *, sig_ok=True):
        self.seam = seam
        self._orig = (
            awsio.compute_artifact_sha256_and_size,
            awsio.destroy_intake_prefixes,
            awsio.find_running_chamber,
            awsio.terminate_chamber,
            awsio.send_disposition_envelope,
            _sig.verify_ecdsa_p256_sha256,
        )
        awsio.compute_artifact_sha256_and_size = seam.compute_artifact_sha256_and_size
        awsio.destroy_intake_prefixes = seam.destroy_intake_prefixes
        awsio.find_running_chamber = seam.find_running_chamber
        awsio.terminate_chamber = seam.terminate_chamber
        awsio.send_disposition_envelope = seam.send_disposition_envelope
        _sig.verify_ecdsa_p256_sha256 = (lambda m, s, p: sig_ok)

    def tearDown(self):
        (
            awsio.compute_artifact_sha256_and_size,
            awsio.destroy_intake_prefixes,
            awsio.find_running_chamber,
            awsio.terminate_chamber,
            awsio.send_disposition_envelope,
            _sig.verify_ecdsa_p256_sha256,
        ) = self._orig

    def assertNoDestroy(self):
        self.assertEqual(self.seam.destroy_calls, [], "artifact must NOT be destroyed")
        self.assertEqual(self.seam.terminate_calls, [], "chamber must NOT be terminated")

    def test_no_hub_read_method_on_seam(self):
        self._install(_FakeSeam())
        # No spoke->Hub read exists on the seam.
        self.assertFalse(hasattr(awsio, "get_tracking_item"))


class TestRejectPathDestroys(HandlerTestBase):
    def test_valid_signed_rejected_token_destroys_all_prefixes(self):
        self._install(_FakeSeam(versions_deleted=7), sig_ok=True)
        out = handler.handler(_event())
        self.assertTrue(out["destroyed"])
        self.assertEqual(out["outcome"], "destroyed")
        # All four intake prefixes are swept (raw + derived).
        self.assertEqual(len(self.seam.destroy_calls), 1)
        _bucket, prefixes = self.seam.destroy_calls[0]
        self.assertEqual(
            set(prefixes),
            {
                f"intake/{_INTAKE}/",
                f"findings/{_INTAKE}/",
                f"runs/{_INTAKE}/",
                f"traces/{_INTAKE}/",
            },
        )
        disp = self.seam.sent[0][1]["disposition"]
        self.assertEqual(disp["outcome"], "destroyed")
        self.assertEqual(disp["destroyed"]["artifact_versions_deleted"], 7)
        self.assertTrue(disp["report_survives"])

    def test_destroy_terminates_live_chamber(self):
        self._install(_FakeSeam(running_chamber="i-0abc123"), sig_ok=True)
        out = handler.handler(_event())
        self.assertTrue(out["destroyed"])
        self.assertEqual(self.seam.terminate_calls, ["i-0abc123"])
        self.assertEqual(out["chamber_state"], "terminated")
        disp = self.seam.sent[0][1]["disposition"]
        self.assertEqual(disp["chamber_state"], "terminated")
        self.assertEqual(disp["destroyed"]["chamber"], "terminated")
        self.assertEqual(disp["destroyed"]["chamber_instance_id"], "i-0abc123")

    def test_destroy_with_no_running_chamber_records_none_running(self):
        self._install(_FakeSeam(running_chamber=None), sig_ok=True)
        out = handler.handler(_event())
        self.assertTrue(out["destroyed"])
        self.assertEqual(self.seam.terminate_calls, [])
        self.assertEqual(out["chamber_state"], "none_running")
        self.assertEqual(self.seam.sent[0][1]["disposition"]["chamber_state"], "none_running")

    def test_api_gateway_shape(self):
        self._install(_FakeSeam(), sig_ok=True)
        ev = {
            "pathParameters": {"intake_id": _INTAKE},
            "decision_token": _token(),
            "signature": base64.b64encode(b"s").decode(),
            "artifact_s3_key": _ARTIFACT_KEY,
        }
        self.assertTrue(handler.handler(ev)["destroyed"])


class TestHoldPath(HandlerTestBase):
    """INCONCLUSIVE / no token => HOLD; NOTHING destroyed, an outcome still crosses."""

    def test_no_token_holds(self):
        self._install(_FakeSeam(), sig_ok=True)
        out = handler.handler(_event(token=None, sig=None))
        self.assertFalse(out["destroyed"])
        self.assertEqual(out["outcome"], "held")
        self.assertNoDestroy()
        self.assertEqual(self.seam.sent[0][1]["disposition"]["outcome"], "held")
        # A hold still crosses a bounded outcome (evidence the mechanism ran + held).
        self.assertEqual(len(self.seam.sent), 1)

    def test_token_without_signature_holds(self):
        self._install(_FakeSeam(), sig_ok=True)
        # token present, signature absent -> hold (fail-safe).
        ev = {"intake_id": _INTAKE, "decision_token": _token(), "artifact_s3_key": _ARTIFACT_KEY}
        out = handler.handler(ev)
        self.assertFalse(out["destroyed"])
        self.assertEqual(out["outcome"], "held")
        self.assertNoDestroy()

    def test_hold_report_survives(self):
        self._install(_FakeSeam(), sig_ok=True)
        handler.handler(_event(token=None, sig=None))
        self.assertTrue(self.seam.sent[0][1]["disposition"]["report_survives"])


class TestFailClosed(HandlerTestBase):
    """A token WAS presented but does not authorize a destroy => refuse; NO destroy."""

    def test_bad_signature_does_not_destroy(self):
        self._install(_FakeSeam(), sig_ok=False)
        out = handler.handler(_event())
        self.assertFalse(out["destroyed"])
        self.assertEqual(out["outcome"], "refused_not_rejected")
        self.assertNoDestroy()
        self.assertEqual(self.seam.sent[0][1]["disposition"]["outcome"], "refused_not_rejected")

    def test_accepted_token_does_not_destroy(self):
        # A signed 'accepted' token (4.6's push authorization) must NOT destroy here.
        self._install(_FakeSeam(), sig_ok=True)
        out = handler.handler(_event(token=_token(decision="accepted")))
        self.assertFalse(out["destroyed"])
        self.assertEqual(out["outcome"], "refused_not_rejected")
        self.assertNoDestroy()

    def test_sha_mismatch_does_not_destroy(self):
        self._install(_FakeSeam(artifact_sha="b" * 64), sig_ok=True)
        out = handler.handler(_event())
        self.assertFalse(out["destroyed"])
        self.assertEqual(out["outcome"], "refused_hash_mismatch")
        self.assertNoDestroy()

    def test_untrusted_key_does_not_destroy(self):
        self._install(_FakeSeam(), sig_ok=True)
        out = handler.handler(_event(token=_token(key_id="rogue")))
        self.assertFalse(out["destroyed"])
        self.assertNoDestroy()

    def test_stale_token_does_not_destroy(self):
        self._install(_FakeSeam(), sig_ok=True)
        out = handler.handler(_event(token=_token(issued_at="2000-01-01T00:00:00Z")))
        self.assertFalse(out["destroyed"])
        self.assertNoDestroy()

    def test_injected_verdict_key_does_not_destroy(self):
        self._install(_FakeSeam(), sig_ok=True)
        tok = _token()
        tok["verdict"] = "malicious"
        out = handler.handler(_event(token=tok))
        self.assertFalse(out["destroyed"])
        self.assertNoDestroy()


class TestIdempotentReReject(HandlerTestBase):
    """A rejected intake whose artifact is already gone: hold (nothing to destroy),
    still crosses a bounded outcome. No error, no false destroy."""

    def test_missing_artifact_holds(self):
        self._install(_FakeSeam(missing_artifact=True), sig_ok=True)
        out = handler.handler(_event())
        self.assertFalse(out["destroyed"])
        self.assertEqual(out["outcome"], "held")
        self.assertNoDestroy()
        disp = self.seam.sent[0][1]["disposition"]
        self.assertEqual(disp["outcome"], "held")
        # The crossed outcome binds to the token's sha256 (still integrity-keyed).
        self.assertEqual(self.seam.sent[0][1]["sha256"], _SHA)


class TestErrorPaths(HandlerTestBase):
    def test_missing_intake_id_400_no_destroy(self):
        self._install(_FakeSeam())
        out = handler.handler({"decision_token": _token(), "signature": "x"})
        self.assertEqual(out["error"]["code"], 400)
        self.assertNoDestroy()
        self.assertEqual(len(self.seam.sent), 0)

    def test_malformed_token_400(self):
        self._install(_FakeSeam())
        out = handler.handler({"intake_id": _INTAKE, "decision_token": "not-a-dict",
                               "signature": "x", "artifact_s3_key": _ARTIFACT_KEY})
        self.assertEqual(out["error"]["code"], 400)
        self.assertNoDestroy()

    def test_token_intake_mismatch_400(self):
        self._install(_FakeSeam())
        tok = _token(intake_id="11111111-1111-4111-8111-111111111111")
        out = handler.handler(_event(token=tok))
        self.assertEqual(out["error"]["code"], 400)
        self.assertNoDestroy()

    def test_bad_base64_signature_400(self):
        self._install(_FakeSeam())
        out = handler.handler({"intake_id": _INTAKE, "decision_token": _token(),
                               "signature": "!!!not-base64!!!", "artifact_s3_key": _ARTIFACT_KEY})
        self.assertEqual(out["error"]["code"], 400)
        self.assertNoDestroy()

    def test_artifact_key_outside_intake_prefix_400(self):
        self._install(_FakeSeam())
        out = handler.handler(_event(artifact_s3_key="intake/other/evil.zip"))
        self.assertEqual(out["error"]["code"], 400)
        self.assertNoDestroy()

    def test_missing_artifact_locator_400(self):
        self._install(_FakeSeam())
        ev = {"intake_id": _INTAKE, "decision_token": _token(),
              "signature": base64.b64encode(b"s").decode()}
        out = handler.handler(ev)
        self.assertEqual(out["error"]["code"], 400)
        self.assertNoDestroy()


class TestDecimalRegression(HandlerTestBase):
    """DynamoDB Numbers arrive as Decimal via boto3.resource. 4.7 does not READ numeric
    Hub fields (it never reads the Hub — RD-048), but the crossed `destroyed` counts
    come from the S3 seam's response, which in a live run flows through
    int()-coercion in the handler. Prove a Decimal-shaped versions count coerces to a
    plain int in the envelope (guards the recurring Decimal trap by construction)."""

    def test_decimal_versions_count_coerces_to_int(self):
        from decimal import Decimal

        # A string-constructed Decimal mirrors exactly what boto3.resource returns for a
        # DynamoDB Number ({"N": "5"}) — the realistic shape of the recurring trap.
        self._install(_FakeSeam(versions_deleted=Decimal("5")), sig_ok=True)  # noqa: FURB157
        out = handler.handler(_event())
        self.assertTrue(out["destroyed"])
        count = self.seam.sent[0][1]["disposition"]["destroyed"]["artifact_versions_deleted"]
        self.assertIsInstance(count, int)
        self.assertNotIsInstance(count, bool)
        self.assertEqual(count, 5)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
