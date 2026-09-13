"""ZTIE Story 3.4 (RD-039) — PURE-STDLIB tests for the findings + remediations handler.

boto3 is STUBBED into ``sys.modules`` so ``handler`` and ``awsio`` import offline. The
``awsio`` seam is monkeypatched with an in-memory fake so the stream handler's control
flow — the assess-and-write path, the fingerprint idempotency guard (no re-work / no
stream loop), the not-yet-scored skip, and the conditional-race no-op — is exercised
WITHOUT touching DynamoDB. There is NO Bedrock (RD-039: 3.4 is PURE, no model call), so
— unlike the 3.2/3.3 handler tests — there is no backoff-loop class here.
"""

from __future__ import annotations

import decimal
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

os.environ.setdefault("TRACKING_TABLE", "ztie-tracking-test")
os.environ.setdefault("REMEDIATION_CONTRACT_VERSION", "1.0")

import awsio  # import after stubs + env above
import handler  # import after stubs + env above

_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_SHA256 = "c" * 64


def _stream_record(intake_id, event_name="MODIFY", seq="100"):
    return {
        "eventName": event_name,
        "dynamodb": {"Keys": {"intake_id": {"S": intake_id}}, "SequenceNumber": seq},
    }


def _scoring(*, static=70, dynamic=30, combined=55, complete=True):
    def _block(v):
        if isinstance(v, str):
            return {"status": v}
        # DynamoDB reads numbers as Decimal — exercise the _canonical path.
        return {"status": "scored", "score": decimal.Decimal(v)}

    return {
        "static": _block(static),
        "dynamic": _block(dynamic),
        "combined": _block(combined),
        "combined_complete": complete,
        "rubric_version": "1.0",
    }


def _correlation(findings):
    return {
        "status": "correlated",
        "correlation": {"summary": "s", "findings": findings},
    }


def _f(kind, severity, title="t"):
    return {"kind": kind, "severity": severity, "title": title}


def _item(with_scoring=True, with_correlation=True):
    item = {"intake_id": _INTAKE_ID, "sha256": _SHA256, "status": "RECEIVED"}
    if with_scoring:
        item["scoring_result"] = _scoring()
    if with_correlation:
        item["correlation_result"] = _correlation(
            [_f("static_only", "high", "flag"), _f("dynamic_only", "critical", "weird")]
        )
    return item


class _FakeSeam:
    """In-memory stand-in for the awsio seam (DynamoDB only)."""

    def __init__(self, item):
        self.item = item
        self.writes = []
        self.raise_conditional = False

    def get_item(self, table_name, intake_id):
        return self.item

    def put_remediation_result(self, table_name, *, intake_id, sha256,
                               remediation_result, assessed_at):
        if self.raise_conditional:
            raise handler_conditional_exc()
        # emulate the write landing back on the item (so the guard sees it next time)
        self.item = dict(self.item)
        self.item["remediation_result"] = remediation_result
        self.writes.append(remediation_result)


def handler_conditional_exc():
    class ConditionalCheckFailedException(Exception):
        pass

    return ConditionalCheckFailedException()


class HandlerTestBase(unittest.TestCase):
    def setUp(self):
        self._orig_get = awsio.get_item
        self._orig_put = awsio.put_remediation_result

    def tearDown(self):
        awsio.get_item = self._orig_get
        awsio.put_remediation_result = self._orig_put

    def _install(self, seam):
        awsio.get_item = seam.get_item
        awsio.put_remediation_result = seam.put_remediation_result


class TestAssessAndWrite(HandlerTestBase):
    def test_assessed_and_written(self):
        seam = _FakeSeam(_item())
        self._install(seam)
        out = handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(out, {"batchItemFailures": []})
        self.assertEqual(len(seam.writes), 1)
        w = seam.writes[0]
        self.assertEqual(w["status"], "assessed")
        self.assertEqual(w["intake_id"], _INTAKE_ID)
        self.assertEqual(w["sha256"], _SHA256)
        self.assertIn("assessment", w)
        self.assertIn("evidence_fingerprint", w)  # handler bookkeeping stamp
        # NO verdict field anywhere in the written record.
        self.assertNotIn("verdict", w)

    def test_partial_scoring_written_honestly(self):
        item = _item()
        item["scoring_result"] = _scoring(dynamic="model_error")
        seam = _FakeSeam(item)
        self._install(seam)
        handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        w = seam.writes[0]
        self.assertEqual(w["assessment"]["scores"]["dynamic"]["status"], "model_error")
        self.assertNotIn("score", w["assessment"]["scores"]["dynamic"])


class TestIdempotencyGuard(HandlerTestBase):
    def test_second_stream_event_is_a_noop(self):
        seam = _FakeSeam(_item())
        self._install(seam)
        handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(len(seam.writes), 1)
        # The write landed on the item with the fingerprint; a second event over the
        # SAME evidence must not re-assess (no stream loop / no re-work).
        handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(len(seam.writes), 1, "re-assessed unchanged evidence (loop!)")

    def test_changed_evidence_reassesses(self):
        seam = _FakeSeam(_item())
        self._install(seam)
        handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(len(seam.writes), 1)
        # Change the scores -> a new fingerprint -> re-assess.
        new_item = dict(seam.item)
        new_item["scoring_result"] = _scoring(static=95)
        seam.item = new_item
        handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(len(seam.writes), 2)


class TestSkips(HandlerTestBase):
    def test_no_scoring_result_skips(self):
        seam = _FakeSeam(_item(with_scoring=False))
        self._install(seam)
        handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(seam.writes, [])

    def test_missing_item_skips(self):
        seam = _FakeSeam(None)
        self._install(seam)
        out = handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(out, {"batchItemFailures": []})
        self.assertEqual(seam.writes, [])

    def test_remove_events_ignored(self):
        seam = _FakeSeam(_item())
        self._install(seam)
        handler.handler(
            {"Records": [_stream_record(_INTAKE_ID, event_name="REMOVE")]}
        )
        self.assertEqual(seam.writes, [])

    def test_no_correlation_still_assesses_over_scores(self):
        # Scores present, correlation absent -> still assessed (scores are evidence).
        seam = _FakeSeam(_item(with_correlation=False))
        self._install(seam)
        handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(len(seam.writes), 1)
        self.assertEqual(seam.writes[0]["status"], "assessed")


class TestConditionalRace(HandlerTestBase):
    def test_conditional_failure_is_benign_noop(self):
        seam = _FakeSeam(_item())
        seam.raise_conditional = True
        self._install(seam)
        out = handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        # A ConditionalCheckFailedException is swallowed as a benign race no-op.
        self.assertEqual(out, {"batchItemFailures": []})
        self.assertEqual(seam.writes, [])


class TestFingerprintStability(unittest.TestCase):
    def test_decimal_roundtrip_stable(self):
        # A score read back as Decimal must fingerprint the same as the plain int
        # (the 3.1 stream-loop lesson).
        plain = {
            "static": {"status": "scored", "score": 70},
            "dynamic": {"status": "scored", "score": 30},
            "combined": {"status": "scored", "score": 55},
            "combined_complete": True,
            "rubric_version": "1.0",
        }
        decimalized = {
            "static": {"status": "scored", "score": decimal.Decimal(70)},
            "dynamic": {"status": "scored", "score": decimal.Decimal(30)},
            "combined": {"status": "scored", "score": decimal.Decimal(55)},
            "combined_complete": True,
            "rubric_version": "1.0",
        }
        corr = _correlation([_f("static_only", "high", "x")])
        fp_plain = handler._evidence_fingerprint(
            handler._canonical(plain), handler._canonical(corr)
        )
        fp_dec = handler._evidence_fingerprint(
            handler._canonical(decimalized), handler._canonical(corr)
        )
        self.assertEqual(fp_plain, fp_dec)


if __name__ == "__main__":
    unittest.main()
