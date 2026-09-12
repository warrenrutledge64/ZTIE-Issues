"""ZTIE Story 3.3 — PURE-STDLIB tests for the Hub-side synthesizer handler.

boto3 is STUBBED into ``sys.modules`` so ``handler`` and ``awsio`` import offline
(moto is not installable in the INTEGRATIONS_ONLY sandbox). The ``awsio`` seam is
then monkeypatched with in-memory fakes so the stream handler's control flow — the
synthesize-and-record path, the call-storm/stream-loop guard (fingerprint), the
honest no_correlation / skipped_no_findings recording, and the conditional-race
no-op — is exercised WITHOUT touching DynamoDB. There is NO model call (RD-037).
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
os.environ.setdefault("SYNTHESIS_CONTRACT_VERSION", "1.0")

import awsio  # import after stubs + env above
import handler  # import after stubs + env above

_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_SHA256 = "c" * 64


class ConditionalCheckFailedException(Exception):
    """Stand-in for botocore's ConditionalCheckFailedException (classified by class
    name by the handler)."""


def _stream_record(intake_id, event_name="MODIFY", seq="100"):
    return {
        "eventName": event_name,
        "dynamodb": {"Keys": {"intake_id": {"S": intake_id}}, "SequenceNumber": seq},
    }


def _finding(kind, severity="medium", title="t", **extra):
    f = {"kind": kind, "severity": severity, "title": title}
    f.update(extra)
    return f


def _correlation_result(findings, *, status="correlated", combined_complete=True):
    result = {
        "contract_version": "1.0",
        "intake_id": _INTAKE_ID,
        "sha256": _SHA256,
        "correlated_at": "2026-09-12T00:05:00Z",
        "status": status,
        "combined_complete": combined_complete,
    }
    if status == "correlated":
        result["correlation"] = {
            "summary": "s",
            "finding_count": len(findings),
            "findings": findings,
        }
    return result


def _item_with_correlation(findings=None, *, status="correlated"):
    if findings is None:
        findings = [
            _finding("static_only", severity="high", title="Permissive rule never used",
                     static_refs=["SG-open"]),
            _finding("correlated", severity="medium", title="Exec matched"),
        ]
    return {
        "intake_id": _INTAKE_ID,
        "sha256": _SHA256,
        "status": "RECEIVED",
        "correlation_result": _correlation_result(findings, status=status),
    }


class _FakeSeam:
    """In-memory stand-in for the awsio seam (DynamoDB only — no Bedrock)."""

    def __init__(self, item):
        self.item = item
        self.writes = []
        self.raise_conditional = False

    def get_item(self, table, intake_id):
        if self.item is None or self.item.get("intake_id") != intake_id:
            return None
        return dict(self.item)

    def put_synthesis_result(self, table, **kw):
        if self.raise_conditional:
            raise ConditionalCheckFailedException("conditional failed")
        self.writes.append(kw)
        self.item["synthesis_result"] = kw["synthesis_result"]
        self.item["synthesis_status"] = kw["status"]
        self.item["synthesized_at"] = kw["synthesized_at"]


class _SeamPatch:
    def __init__(self, fake):
        self.fake = fake
        self._orig = {}

    def __enter__(self):
        for name in ("get_item", "put_synthesis_result"):
            self._orig[name] = getattr(awsio, name)
            setattr(awsio, name, getattr(self.fake, name))
        # Guarantee there is NO bedrock invocation path on this seam (RD-037).
        assert not hasattr(awsio, "invoke_nova"), "synthesizer seam must not call a model"
        return self.fake

    def __exit__(self, *a):
        for name, fn in self._orig.items():
            setattr(awsio, name, fn)


class TestStreamKeyExtraction(unittest.TestCase):
    def test_insert_and_modify(self):
        other = "11111111-1111-4111-8111-111111111111"
        event = {"Records": [_stream_record(_INTAKE_ID, "INSERT"), _stream_record(other)]}
        self.assertEqual(handler._intake_ids_from_event(event), [_INTAKE_ID, other])

    def test_remove_ignored(self):
        self.assertEqual(
            handler._intake_ids_from_event({"Records": [_stream_record(_INTAKE_ID, "REMOVE")]}),
            [],
        )


class TestSynthesizeHappyPath(unittest.TestCase):
    def test_synthesizes_and_writes(self):
        fake = _FakeSeam(_item_with_correlation())
        with _SeamPatch(fake):
            out = handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(out["batchItemFailures"], [])
        self.assertEqual(len(fake.writes), 1)
        result = fake.writes[0]["synthesis_result"]
        self.assertEqual(result["status"], "synthesized")
        self.assertEqual(result["intake_id"], _INTAKE_ID)
        self.assertEqual(result["sha256"], _SHA256)
        self.assertIn("synthesis", result)
        acc = result["synthesis"]["accuracy"]
        self.assertEqual(acc["confirmed_correlation_count"], 1)
        self.assertEqual(acc["candidate_false_positive_count"], 1)
        self.assertIn("correlation_fingerprint", result)
        # written status flattened for query.
        self.assertEqual(fake.writes[0]["status"], "synthesized")


class TestGuards(unittest.TestCase):
    def test_no_correlation_result_is_noop(self):
        item = {"intake_id": _INTAKE_ID, "sha256": _SHA256, "status": "RECEIVED"}
        fake = _FakeSeam(item)
        with _SeamPatch(fake):
            out = handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(len(fake.writes), 0)
        self.assertEqual(out["batchItemFailures"], [])

    def test_missing_item_is_benign(self):
        fake = _FakeSeam(None)
        with _SeamPatch(fake):
            out = handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(out["batchItemFailures"], [])
        self.assertEqual(len(fake.writes), 0)

    def test_no_call_storm_when_fingerprint_unchanged(self):
        # First stream event synthesizes; a second event over the SAME (now-updated)
        # item must NOT re-synthesize (the call-storm / stream-loop guard).
        fake = _FakeSeam(_item_with_correlation())
        with _SeamPatch(fake):
            handler.handler({"Records": [_stream_record(_INTAKE_ID, seq="1")]})
            handler.handler({"Records": [_stream_record(_INTAKE_ID, seq="2")]})
        self.assertEqual(len(fake.writes), 1, "must not re-synthesize unchanged correlation")

    def test_resynthesizes_when_correlation_changes(self):
        fake = _FakeSeam(_item_with_correlation())
        with _SeamPatch(fake):
            handler.handler({"Records": [_stream_record(_INTAKE_ID, seq="1")]})
            # The correlation changes (a new finding lands) -> new fingerprint.
            fake.item["correlation_result"]["correlation"]["findings"].append(
                _finding("dynamic_only", title="new behavior")
            )
            handler.handler({"Records": [_stream_record(_INTAKE_ID, seq="2")]})
        self.assertEqual(len(fake.writes), 2)

    def test_fingerprint_stable_across_decimal_roundtrip(self):
        # A Decimal round-trip of the same content must NOT look like a change (the
        # 3.1 live loop lesson) — else it would re-synthesize forever.
        fake = _FakeSeam(_item_with_correlation())
        with _SeamPatch(fake):
            handler.handler({"Records": [_stream_record(_INTAKE_ID, seq="1")]})
            fake.item = _dynamodbify(fake.item)
            handler.handler({"Records": [_stream_record(_INTAKE_ID, seq="2")]})
        self.assertEqual(len(fake.writes), 1, "Decimal round-trip must not re-synthesize")


class TestHonestRecording(unittest.TestCase):
    def test_no_correlation_recorded(self):
        fake = _FakeSeam(_item_with_correlation([], status="model_error"))
        with _SeamPatch(fake):
            handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        result = fake.writes[0]["synthesis_result"]
        self.assertEqual(result["status"], "no_correlation")
        self.assertNotIn("synthesis", result)

    def test_skipped_no_findings_recorded(self):
        fake = _FakeSeam(_item_with_correlation([], status="correlated"))
        with _SeamPatch(fake):
            handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        result = fake.writes[0]["synthesis_result"]
        self.assertEqual(result["status"], "skipped_no_findings")
        self.assertNotIn("synthesis", result)

    def test_conditional_race_is_benign(self):
        fake = _FakeSeam(_item_with_correlation())
        fake.raise_conditional = True
        with _SeamPatch(fake):
            out = handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(out["batchItemFailures"], [])


class TestConfigPin(unittest.TestCase):
    def test_own_version_pin(self):
        self.assertEqual(handler.SYNTHESIS_CONTRACT_VERSION, "1.0")

    def test_seam_has_no_model_client(self):
        # RD-037: the synthesizer seam is DynamoDB-only; no Bedrock client/function.
        self.assertFalse(hasattr(awsio, "invoke_nova"))
        self.assertFalse(hasattr(awsio, "_bedrock"))


def _dynamodbify(value):
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


if __name__ == "__main__":
    unittest.main()
