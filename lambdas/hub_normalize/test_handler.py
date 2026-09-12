"""ZTIE Story 3.1 — PURE-STDLIB tests for the Hub-side normalizer handler.

boto3 is STUBBED into ``sys.modules`` so ``handler`` and ``awsio`` import offline
(moto is not installable in the INTEGRATIONS_ONLY sandbox). The ``awsio`` seam is
then monkeypatched with an in-memory fake so the stream handler's control flow is
exercised WITHOUT touching DynamoDB:

  * DynamoDB-stream key extraction (INSERT / MODIFY normalized, REMOVE ignored);
  * a re-derive WRITES when the combined event changed;
  * a re-derive is a NO-OP when the combined event is unchanged (no stream loop);
  * a conditional-write race is a benign no-op;
  * a missing item is a benign no-op;
  * batch dedupe (multiple MODIFYs on one item -> one re-derive).
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
os.environ.setdefault("COMBINED_EVENT_CONTRACT_VERSION", "1.0")

import awsio  # import after boto3 stub + env above
import handler  # import after boto3 stub + env above

_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_SHA256 = "c" * 64


class ConditionalCheckFailedException(Exception):
    """Stand-in for botocore's ConditionalCheckFailedException. The handler's
    ``_is_conditional_check_failure`` classifies it by CLASS NAME, so this exercises
    the real benign-race path without botocore installed."""


def _stream_record(intake_id, event_name="MODIFY", seq="100"):
    return {
        "eventName": event_name,
        "dynamodb": {
            "Keys": {"intake_id": {"S": intake_id}},
            "SequenceNumber": seq,
        },
    }


def _dynamodbify(value):
    """Simulate how boto3's DynamoDB resource round-trips a stored item: every
    number comes back as ``decimal.Decimal`` (ints AND floats). This is the exact
    type gap that caused the live stream-loop bug (2026-09-11) — a freshly-built
    plain-int event did not compare equal to its Decimal round-trip. The fake write
    path stores through this so the no-loop test exercises the REAL condition."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return decimal.Decimal(value)
    if isinstance(value, float):
        return decimal.Decimal(str(value))
    if isinstance(value, dict):
        return {k: _dynamodbify(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_dynamodbify(v) for v in value]
    return value


class _FakeSeam:
    """In-memory stand-in for the awsio seam."""

    def __init__(self, item):
        self.item = item
        self.writes = []
        self.raise_conditional = False

    def get_item(self, table, intake_id):
        if self.item is None or self.item.get("intake_id") != intake_id:
            return None
        return dict(self.item)

    def put_combined_event(self, table, **kw):
        if self.raise_conditional:
            raise ConditionalCheckFailedException("conditional failed")
        self.writes.append(kw)
        # Reflect the write back onto the item AS DYNAMODB WOULD (numbers become
        # Decimal) so a subsequent re-derive exercises the real type round-trip and
        # the idempotency compare is tested against the actual stored shape.
        self.item["combined_event"] = _dynamodbify(kw["combined_event"])
        self.item["combined_at"] = kw["combined_at"]


class _SeamPatch:
    def __init__(self, fake):
        self.fake = fake
        self._orig = {}

    def __enter__(self):
        for name in ("get_item", "put_combined_event"):
            self._orig[name] = getattr(awsio, name)
            setattr(awsio, name, getattr(self.fake, name))
        return self.fake

    def __exit__(self, *a):
        for name, fn in self._orig.items():
            setattr(awsio, name, fn)


class TestStreamKeyExtraction(unittest.TestCase):
    def test_insert_and_modify_extracted(self):
        event = {
            "Records": [
                _stream_record(_INTAKE_ID, "INSERT"),
                _stream_record("11111111-1111-4111-8111-111111111111", "MODIFY"),
            ]
        }
        ids = handler._intake_ids_from_event(event)
        self.assertEqual(
            ids, [_INTAKE_ID, "11111111-1111-4111-8111-111111111111"]
        )

    def test_remove_ignored(self):
        event = {"Records": [_stream_record(_INTAKE_ID, "REMOVE")]}
        self.assertEqual(handler._intake_ids_from_event(event), [])

    def test_dedupe(self):
        event = {"Records": [_stream_record(_INTAKE_ID), _stream_record(_INTAKE_ID)]}
        self.assertEqual(handler._intake_ids_from_event(event), [_INTAKE_ID])


class TestNormalizeWritesAndIdempotency(unittest.TestCase):
    def test_writes_when_combined_event_new(self):
        item = {
            "intake_id": _INTAKE_ID,
            "sha256": _SHA256,
            "static_scan": {"highest_severity": "high", "total_findings": 2},
        }
        fake = _FakeSeam(item)
        with _SeamPatch(fake):
            out = handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(out["batchItemFailures"], [])
        self.assertEqual(len(fake.writes), 1)
        self.assertEqual(fake.writes[0]["intake_id"], _INTAKE_ID)
        self.assertEqual(fake.writes[0]["sha256"], _SHA256)
        self.assertIn("static", fake.writes[0]["combined_event"]["inputs_present"])

    def test_no_loop_when_unchanged(self):
        item = {
            "intake_id": _INTAKE_ID,
            "sha256": _SHA256,
            "dynamic_run": {"outcome": "completed"},
        }
        fake = _FakeSeam(item)
        with _SeamPatch(fake):
            # First pass writes; second pass over the SAME (now-updated) item must
            # NOT write again (its own write would otherwise loop the stream).
            handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
            handler.handler({"Records": [_stream_record(_INTAKE_ID, seq="200")]})
        self.assertEqual(len(fake.writes), 1, "must not re-write an unchanged combined event")

    def test_conditional_race_is_benign(self):
        item = {"intake_id": _INTAKE_ID, "sha256": _SHA256, "static_scan": {"highest_severity": "low"}}
        fake = _FakeSeam(item)
        fake.raise_conditional = True
        with _SeamPatch(fake):
            out = handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        # No batch failure surfaced (a race is not retryable).
        self.assertEqual(out["batchItemFailures"], [])

    def test_missing_item_is_benign(self):
        fake = _FakeSeam(None)
        with _SeamPatch(fake):
            out = handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(out["batchItemFailures"], [])
        self.assertEqual(len(fake.writes), 0)

    def test_remove_record_not_normalized(self):
        item = {"intake_id": _INTAKE_ID, "sha256": _SHA256, "static_scan": {"highest_severity": "low"}}
        fake = _FakeSeam(item)
        with _SeamPatch(fake):
            out = handler.handler({"Records": [_stream_record(_INTAKE_ID, "REMOVE")]})
        self.assertEqual(len(fake.writes), 0)
        self.assertEqual(out["batchItemFailures"], [])

    def test_unexpected_error_surfaces_batch_failure(self):
        item = {"intake_id": _INTAKE_ID, "sha256": _SHA256, "static_scan": {"highest_severity": "low"}}
        fake = _FakeSeam(item)

        def _boom(*a, **k):
            raise RuntimeError("dynamo down")

        with _SeamPatch(fake):
            awsio.put_combined_event = _boom
            out = handler.handler({"Records": [_stream_record(_INTAKE_ID, seq="777")]})
        self.assertEqual(out["batchItemFailures"], [{"itemIdentifier": "777"}])


class TestIdempotencyAcrossDynamoDBTypes(unittest.TestCase):
    """Regression for the live stream-loop bug (2026-09-11): a freshly-built
    combined_event (plain int/float) MUST compare equal to the same event after a
    DynamoDB round-trip (numbers become decimal.Decimal), or the stream handler
    re-writes forever."""

    def test_equal_ignores_int_vs_decimal(self):
        built = {
            "complete": True,
            "signals": {"behavioral_event_count": 0},
            "sources": {"static": {"total_findings": 3}},
        }
        roundtripped = _dynamodbify(built)  # ints -> Decimal, as DynamoDB returns
        self.assertTrue(
            handler._combined_event_equal(roundtripped, built),
            "int and its Decimal round-trip must compare equal (no-loop guard)",
        )

    def test_equal_ignores_float_vs_decimal(self):
        built = {"signals": {"score_hint": 1.5}}
        roundtripped = _dynamodbify(built)
        self.assertTrue(handler._combined_event_equal(roundtripped, built))

    def test_still_detects_real_change(self):
        a = {"complete": True, "signals": {"behavioral_event_count": 0}}
        b = {"complete": True, "signals": {"behavioral_event_count": 1}}
        self.assertFalse(handler._combined_event_equal(_dynamodbify(a), b))

    def test_bool_not_collapsed_into_number(self):
        # A bool must not canonicalize to a number (True == 1 in Python) and cause a
        # false "equal".
        a = {"complete": True}
        b = {"complete": 1}
        self.assertFalse(handler._combined_event_equal(_dynamodbify(a), b))

    def test_full_roundtrip_does_not_loop(self):
        # End-to-end: a COMPLETE event (carries integer counts) written, then a
        # second stream pass over the Decimal-stored item must NOT re-write.
        item = {
            "intake_id": _INTAKE_ID,
            "sha256": _SHA256,
            "static_scan": {"highest_severity": "high", "total_findings": 3},
            "dynamic_run": {"outcome": "completed"},
            "sanitized": {
                "pipeline": {"status": "sanitized", "truncated": False, "estimated_tokens": 12},
                "events": [
                    {"offset_ms": 5, "category": "file", "syscall": "openat", "summary": "openat(/x)"}
                ],
            },
        }
        fake = _FakeSeam(item)
        with _SeamPatch(fake):
            handler.handler({"Records": [_stream_record(_INTAKE_ID, seq="1")]})
            handler.handler({"Records": [_stream_record(_INTAKE_ID, seq="2")]})
            handler.handler({"Records": [_stream_record(_INTAKE_ID, seq="3")]})
        self.assertEqual(
            len(fake.writes), 1, "must write once then no-op across the Decimal round-trip"
        )


class TestConfigPin(unittest.TestCase):
    def test_own_version_pin(self):
        self.assertEqual(handler.COMBINED_EVENT_CONTRACT_VERSION, "1.0")


if __name__ == "__main__":
    unittest.main()
