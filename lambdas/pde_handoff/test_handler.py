"""ZTIE Story 4.6 (RD-047) — unit tests for the Forensic PDE-handoff pusher handler.

boto3 is STUBBED into ``sys.modules`` so ``handler`` and ``awsio`` import offline. The
``awsio`` seam is monkeypatched with an in-memory fake so the handler's control flow —
intake_id resolution (top-level + API-Gateway-shaped), the read + hash-verify + fail-closed
gate, the CROSS-ACCOUNT push (only on accept + verified hash), the ALWAYS-recorded outcome
crossing, and the bounded error envelopes — is exercised WITHOUT touching AWS.

The hardest invariant is proven here: NOTHING is pushed absent a genuine recorded human
``accepted`` decision AND a verified sha256. Includes a DynamoDB-Number-as-Decimal regression
(the 4.5 live-defect class) proving numeric fields read off the item are coerced, never
strict-isinstance-guarded.
"""

from __future__ import annotations

import os
import sys
import types
import unittest
from decimal import Decimal

# --- Stub boto3 so handler.py + awsio.py import offline -----------------------
if "boto3" not in sys.modules:
    _boto3 = types.ModuleType("boto3")
    _boto3.client = lambda *a, **k: None
    _boto3.resource = lambda *a, **k: None
    sys.modules["boto3"] = _boto3

os.environ.setdefault("TRACKING_TABLE", "ztie-tracking-test")
os.environ.setdefault("ARTIFACT_BUCKET", "ztie-forensic-artifacts")
os.environ.setdefault("SANDBOX_LANDING_BUCKET", "ztie-sandbox-landing")
os.environ.setdefault("SANDBOX_LANDING_PREFIX", "accepted/")
os.environ.setdefault("SANDBOX_ACCOUNT_ID", "586917955591")
os.environ.setdefault(
    "HUB_INGEST_QUEUE_URL",
    "https://sqs.us-east-1.amazonaws.com/641628980935/ztie-ingest",
)
os.environ.setdefault("HANDOFF_CONTRACT_VERSION", "1.0")

import awsio  # import after stubs + env above
import handler  # import after stubs + env above

_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_SHA256 = "a" * 64
_ARTIFACT_KEY = f"intake/{_INTAKE_ID}/app.zip"


def _item(*, decision=None, sha256=_SHA256, extra=None):
    item = {
        "intake_id": _INTAKE_ID,
        "sha256": sha256,
        "status": "RECEIVED",
        "filename": "app.zip",
        # A DynamoDB Number read via boto3.resource arrives as a Decimal — this is
        # exactly the 4.5 live-defect class. Prove the pusher tolerates it.
        "size_bytes": Decimal(4096),
    }
    if decision is not None:
        item["human_decision"] = decision
    if extra:
        item.update(extra)
    return item


class _FakeSeam:
    """In-memory stand-in for the awsio seam. Records every AWS interaction so the
    tests can assert exactly what crossed (and, critically, whether a push happened)."""

    def __init__(self, items, *, artifact_sha=_SHA256, artifact_size=4096):
        self.items = items
        self.artifact_sha = artifact_sha
        self.artifact_size = artifact_size
        self.reads = 0
        self.pushes = []  # each: dict of push kwargs
        self.sent = []  # each: (queue_url, envelope)

    def get_tracking_item(self, table_name, intake_id):
        self.reads += 1
        return self.items.get(intake_id)

    def compute_artifact_sha256_and_size(self, bucket, key):
        return self.artifact_sha, self.artifact_size

    def push_artifact(self, *, source_bucket, source_key, dest_bucket, dest_key, metadata):
        self.pushes.append(
            {
                "source_bucket": source_bucket,
                "source_key": source_key,
                "dest_bucket": dest_bucket,
                "dest_key": dest_key,
                "metadata": metadata,
            }
        )
        return "v-1"

    def send_handoff_envelope(self, queue_url, envelope):
        self.sent.append((queue_url, envelope))


class HandlerTestBase(unittest.TestCase):
    def _install(self, seam):
        self.seam = seam
        self._orig = (
            awsio.get_tracking_item,
            awsio.compute_artifact_sha256_and_size,
            awsio.push_artifact,
            awsio.send_handoff_envelope,
        )
        awsio.get_tracking_item = seam.get_tracking_item
        awsio.compute_artifact_sha256_and_size = seam.compute_artifact_sha256_and_size
        awsio.push_artifact = seam.push_artifact
        awsio.send_handoff_envelope = seam.send_handoff_envelope

    def tearDown(self):
        (
            awsio.get_tracking_item,
            awsio.compute_artifact_sha256_and_size,
            awsio.push_artifact,
            awsio.send_handoff_envelope,
        ) = self._orig


class TestAcceptPathPushes(HandlerTestBase):
    def test_accepted_and_verified_pushes_and_records(self):
        self._install(_FakeSeam({_INTAKE_ID: _item(decision="accepted")}))
        out = handler.handler({"intake_id": _INTAKE_ID})
        # Pushed exactly once, to the Sandbox bucket under the scoped prefix.
        self.assertTrue(out["pushed"])
        self.assertEqual(out["outcome"], "pushed")
        self.assertEqual(len(self.seam.pushes), 1)
        push = self.seam.pushes[0]
        self.assertEqual(push["source_bucket"], "ztie-forensic-artifacts")
        self.assertEqual(push["source_key"], _ARTIFACT_KEY)
        self.assertEqual(push["dest_bucket"], "ztie-sandbox-landing")
        self.assertTrue(push["dest_key"].startswith("accepted/"))
        self.assertIn(_INTAKE_ID, push["dest_key"])
        self.assertEqual(push["metadata"]["sha256"], _SHA256)
        # The outcome was ALSO recorded to the Hub (pushed).
        self.assertEqual(len(self.seam.sent), 1)
        _, env = self.seam.sent[0]
        self.assertEqual(env["handoff"]["outcome"], "pushed")
        self.assertIn("destination", env["handoff"])
        self.assertEqual(env["handoff"]["destination"]["account_id"], "586917955591")

    def test_api_gateway_shape(self):
        self._install(_FakeSeam({_INTAKE_ID: _item(decision="accepted")}))
        out = handler.handler({"pathParameters": {"intake_id": _INTAKE_ID}})
        self.assertTrue(out["pushed"])

    def test_size_bytes_decimal_is_coerced(self):
        # Regression for the 4.5 DynamoDB-Number->Decimal class: size_bytes arrives
        # as Decimal(4096); the recorded outcome must carry a plain int, not blow up.
        self._install(_FakeSeam({_INTAKE_ID: _item(decision="accepted")}))
        _, env = self._run_and_get_envelope()
        self.assertEqual(env["handoff"]["size_bytes"], 4096)
        self.assertIsInstance(env["handoff"]["size_bytes"], int)
        self.assertNotIsInstance(env["handoff"]["size_bytes"], Decimal)

    def _run_and_get_envelope(self):
        handler.handler({"intake_id": _INTAKE_ID})
        return self.seam.sent[0]


class TestFailClosed(HandlerTestBase):
    """The hardest invariant: absent a genuine accept + a verified hash, NOTHING is
    pushed — but the refusal outcome IS recorded to the Hub."""

    def test_pending_does_not_push(self):
        self._install(_FakeSeam({_INTAKE_ID: _item(decision="pending")}))
        out = handler.handler({"intake_id": _INTAKE_ID})
        self.assertFalse(out["pushed"])
        self.assertEqual(out["outcome"], "refused_not_accepted")
        self.assertEqual(len(self.seam.pushes), 0)  # NOTHING left Forensic
        self.assertEqual(len(self.seam.sent), 1)  # refusal recorded
        self.assertEqual(self.seam.sent[0][1]["handoff"]["outcome"], "refused_not_accepted")

    def test_absent_decision_does_not_push(self):
        self._install(_FakeSeam({_INTAKE_ID: _item(decision=None)}))
        out = handler.handler({"intake_id": _INTAKE_ID})
        self.assertFalse(out["pushed"])
        self.assertEqual(len(self.seam.pushes), 0)

    def test_rejected_does_not_push(self):
        self._install(_FakeSeam({_INTAKE_ID: _item(decision="rejected")}))
        out = handler.handler({"intake_id": _INTAKE_ID})
        self.assertFalse(out["pushed"])
        self.assertEqual(out["outcome"], "refused_not_accepted")
        self.assertEqual(len(self.seam.pushes), 0)

    def test_hash_mismatch_does_not_push_even_when_accepted(self):
        # Accepted, but the Forensic artifact's sha256 does NOT match the record.
        self._install(
            _FakeSeam(
                {_INTAKE_ID: _item(decision="accepted")}, artifact_sha="b" * 64
            )
        )
        out = handler.handler({"intake_id": _INTAKE_ID})
        self.assertFalse(out["pushed"])
        self.assertEqual(out["outcome"], "refused_hash_mismatch")
        self.assertFalse(out["hash_verified"])
        self.assertEqual(len(self.seam.pushes), 0)  # NOTHING left Forensic
        self.assertEqual(self.seam.sent[0][1]["handoff"]["outcome"], "refused_hash_mismatch")

    def test_advisory_verdict_value_does_not_trigger_push(self):
        # A recommended_verdict-shaped value in human_decision is NOT an accept.
        self._install(_FakeSeam({_INTAKE_ID: _item(decision="PASS")}))
        out = handler.handler({"intake_id": _INTAKE_ID})
        self.assertFalse(out["pushed"])
        self.assertEqual(len(self.seam.pushes), 0)

    def test_recommended_verdict_on_item_is_ignored(self):
        # Even with an advisory recommended_verdict=PASS on the item, no accept => no push.
        item = _item(decision="pending", extra={"verdict_result": {"recommended_verdict": "PASS"}})
        self._install(_FakeSeam({_INTAKE_ID: item}))
        out = handler.handler({"intake_id": _INTAKE_ID})
        self.assertFalse(out["pushed"])
        self.assertEqual(len(self.seam.pushes), 0)


class TestErrorPaths(HandlerTestBase):
    def test_missing_intake_id_400_no_push(self):
        self._install(_FakeSeam({}))
        out = handler.handler({})
        self.assertEqual(out["error"]["code"], 400)
        self.assertEqual(len(self.seam.pushes), 0)
        self.assertEqual(len(self.seam.sent), 0)

    def test_malformed_intake_id_400(self):
        self._install(_FakeSeam({}))
        out = handler.handler({"intake_id": "not-a-uuid"})
        self.assertEqual(out["error"]["code"], 400)

    def test_not_found_404_no_push(self):
        self._install(_FakeSeam({}))
        out = handler.handler({"intake_id": "00000000-0000-4000-8000-000000000000"})
        self.assertEqual(out["error"]["code"], 404)
        self.assertEqual(len(self.seam.pushes), 0)

    def test_missing_sha_422_no_push(self):
        bad = {"intake_id": "11111111-1111-4111-8111-111111111111", "filename": "x"}
        self._install(_FakeSeam({"11111111-1111-4111-8111-111111111111": bad}))
        out = handler.handler({"intake_id": "11111111-1111-4111-8111-111111111111"})
        self.assertEqual(out["error"]["code"], 422)
        self.assertEqual(len(self.seam.pushes), 0)

    def test_malformed_sha_422_no_push(self):
        bad = _item(decision="accepted", sha256="zz")
        self._install(_FakeSeam({_INTAKE_ID: bad}))
        out = handler.handler({"intake_id": _INTAKE_ID})
        self.assertEqual(out["error"]["code"], 422)
        self.assertEqual(len(self.seam.pushes), 0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
