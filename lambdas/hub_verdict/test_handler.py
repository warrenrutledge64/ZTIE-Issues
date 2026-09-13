"""ZTIE Story 3.5 (RD-040) — PURE-STDLIB tests for the verdict handler.

boto3 is STUBBED into ``sys.modules`` so ``handler`` and ``awsio`` import offline. The
``awsio`` seam is monkeypatched with an in-memory fake so the stream handler's control
flow — the derive-and-write path, the fingerprint idempotency guard (no re-work / no
stream loop), the not-yet-scored skip, and the conditional-race no-op — is exercised
WITHOUT touching DynamoDB. There is NO Bedrock (RD-040: 3.5 is PURE, no model call), so
there is no backoff-loop class here.

Also asserts the RD-040 advisory invariants on the WRITTEN record: it carries
``recommended_verdict`` + ``human_decision: pending`` in its OWN ``verdict_result``
field, it NEVER carries a bare effective ``verdict`` key, and it NEVER touches the
tracking ``status`` or the 3.3/3.4 fields.
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
os.environ.setdefault("VERDICT_CONTRACT_VERSION", "1.0")

import awsio  # import after stubs + env above
import handler  # import after stubs + env above

_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_SHA256 = "c" * 64

_BANNED_EFFECTIVE_KEYS = frozenset(
    {"verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean"}
)


def _stream_record(intake_id, event_name="MODIFY", seq="100"):
    return {
        "eventName": event_name,
        "dynamodb": {"Keys": {"intake_id": {"S": intake_id}}, "SequenceNumber": seq},
    }


def _scoring(*, static=70, dynamic=30, combined=10, complete=True):
    def _block(val):
        if isinstance(val, str):
            return {"status": val}
        # DynamoDB reads numbers as Decimal — exercise the _canonical path.
        return {"status": "scored", "score": decimal.Decimal(val)}

    return {
        "static": _block(static),
        "dynamic": _block(dynamic),
        "combined": _block(combined),
        "combined_complete": complete,
        "rubric_version": "1.0",
    }


def _rem(*, status="assessed", gaps=None, contradiction=0, complete=True):
    return {
        "status": status,
        "combined_complete": complete,
        "assessment": {"gaps": gaps or [], "counts": {"contradiction": contradiction}},
    }


def _item(with_scoring=True, with_remediation=True, **scoring_kw):
    item = {"intake_id": _INTAKE_ID, "sha256": _SHA256, "status": "RECEIVED"}
    if with_scoring:
        item["scoring_result"] = _scoring(**scoring_kw)
    if with_remediation:
        item["remediation_result"] = _rem()
    return item


def _conditional_exc():
    class ConditionalCheckFailedException(Exception):
        pass

    return ConditionalCheckFailedException()


class _FakeSeam:
    """In-memory stand-in for the awsio seam (DynamoDB only)."""

    def __init__(self, item):
        self.item = item
        self.writes = []
        self.raise_conditional = False

    def get_item(self, table_name, intake_id):
        return self.item

    def put_verdict_result(self, table_name, *, intake_id, sha256,
                           verdict_result, recommended_at):
        if self.raise_conditional:
            raise _conditional_exc()
        # emulate the write landing back on the item (so the guard sees it next time),
        # and prove it lands under its OWN field only.
        self.item = dict(self.item)
        self.item["verdict_result"] = verdict_result
        self.item["verdict_at"] = recommended_at
        self.writes.append(verdict_result)


class HandlerTestBase(unittest.TestCase):
    def setUp(self):
        self._orig_get = awsio.get_item
        self._orig_put = awsio.put_verdict_result

    def tearDown(self):
        awsio.get_item = self._orig_get
        awsio.put_verdict_result = self._orig_put

    def _install(self, seam):
        awsio.get_item = seam.get_item
        awsio.put_verdict_result = seam.put_verdict_result


class TestRecommendAndWrite(HandlerTestBase):
    def test_recommended_and_written(self):
        seam = _FakeSeam(_item(combined=10))  # low -> PASS
        self._install(seam)
        out = handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(out, {"batchItemFailures": []})
        self.assertEqual(len(seam.writes), 1)
        w = seam.writes[0]
        self.assertEqual(w["status"], "recommended")
        self.assertEqual(w["recommended_verdict"], "PASS")
        self.assertEqual(w["human_decision"], "pending")
        self.assertEqual(w["intake_id"], _INTAKE_ID)
        self.assertEqual(w["sha256"], _SHA256)
        self.assertIn("evidence_fingerprint", w)  # handler bookkeeping stamp

    def test_written_record_has_no_effective_verdict_key(self):
        seam = _FakeSeam(_item(combined=90))  # high -> FAIL
        self._install(seam)
        handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        w = seam.writes[0]
        self.assertEqual(w["recommended_verdict"], "FAIL")
        self.assertIsNone(_find_banned(w))

    def test_write_lands_only_in_own_field_never_touches_others(self):
        seam = _FakeSeam(_item(combined=10))
        self._install(seam)
        handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        # The 3.3/3.4 fields + tracking status are untouched; a NEW verdict_result field
        # appears; no verdict was written onto scoring_result / remediation_result.
        self.assertEqual(seam.item["status"], "RECEIVED")
        self.assertIn("verdict_result", seam.item)
        self.assertIn("verdict_at", seam.item)
        self.assertNotIn("recommended_verdict", seam.item["scoring_result"])
        self.assertNotIn("verdict", seam.item["scoring_result"])
        self.assertNotIn("verdict", seam.item["remediation_result"])

    def test_contradiction_forces_inconclusive(self):
        item = _item(combined=90)  # would be FAIL by score
        item["remediation_result"] = _rem(
            gaps=[{"gap_type": "contradiction", "severity": "high", "title": "x"}],
            contradiction=1,
        )
        seam = _FakeSeam(item)
        self._install(seam)
        handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(seam.writes[0]["recommended_verdict"], "INCONCLUSIVE")

    def test_partial_scoring_forces_inconclusive(self):
        seam = _FakeSeam(_item(static="model_error", combined=10))
        self._install(seam)
        handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(seam.writes[0]["recommended_verdict"], "INCONCLUSIVE")
        self.assertEqual(seam.writes[0]["status"], "incomplete")


class TestIdempotencyGuard(HandlerTestBase):
    def test_second_stream_event_is_a_noop(self):
        seam = _FakeSeam(_item())
        self._install(seam)
        handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(len(seam.writes), 1)
        # A second event over the SAME evidence must not re-derive (no stream loop).
        handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(len(seam.writes), 1, "re-derived unchanged evidence (loop!)")

    def test_changed_evidence_rerecommends(self):
        seam = _FakeSeam(_item(combined=10))
        self._install(seam)
        handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(len(seam.writes), 1)
        # Change the combined score -> new fingerprint -> re-derive (PASS -> FAIL).
        new_item = dict(seam.item)
        new_item["scoring_result"] = _scoring(combined=90)
        seam.item = new_item
        handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(len(seam.writes), 2)
        self.assertEqual(seam.writes[1]["recommended_verdict"], "FAIL")


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
        handler.handler({"Records": [_stream_record(_INTAKE_ID, event_name="REMOVE")]})
        self.assertEqual(seam.writes, [])

    def test_no_remediation_still_recommends_over_scores(self):
        # Scores present, remediation absent -> still recommends over the combined score
        # (remediation only supplies the incompleteness/contradiction overrides).
        seam = _FakeSeam(_item(with_remediation=False, combined=10))
        self._install(seam)
        handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(len(seam.writes), 1)
        self.assertEqual(seam.writes[0]["recommended_verdict"], "PASS")


class TestConditionalRace(HandlerTestBase):
    def test_conditional_failure_is_benign_noop(self):
        seam = _FakeSeam(_item())
        seam.raise_conditional = True
        self._install(seam)
        out = handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(out, {"batchItemFailures": []})
        self.assertEqual(seam.writes, [])


class TestFingerprintStability(unittest.TestCase):
    def test_decimal_roundtrip_stable(self):
        # A score read back as Decimal must fingerprint the same as the plain int
        # (the 3.1 stream-loop lesson).
        plain = {
            "static": {"status": "scored", "score": 70},
            "dynamic": {"status": "scored", "score": 30},
            "combined": {"status": "scored", "score": 10},
            "combined_complete": True,
            "rubric_version": "1.0",
        }
        decimalized = {
            "static": {"status": "scored", "score": decimal.Decimal(70)},
            "dynamic": {"status": "scored", "score": decimal.Decimal(30)},
            "combined": {"status": "scored", "score": decimal.Decimal(10)},
            "combined_complete": True,
            "rubric_version": "1.0",
        }
        rem = _rem()
        fp_plain = handler._evidence_fingerprint(
            handler._canonical(plain), handler._canonical(rem)
        )
        fp_dec = handler._evidence_fingerprint(
            handler._canonical(decimalized), handler._canonical(rem)
        )
        self.assertEqual(fp_plain, fp_dec)


def _find_banned(obj):
    if isinstance(obj, dict):
        for k, val in obj.items():
            if k in _BANNED_EFFECTIVE_KEYS:
                return k
            deeper = _find_banned(val)
            if deeper:
                return f"{k}.{deeper}"
    elif isinstance(obj, list):
        for i, val in enumerate(obj):
            deeper = _find_banned(val)
            if deeper:
                return f"[{i}].{deeper}"
    return None


if __name__ == "__main__":
    unittest.main()
