"""ZTIE Story 3.2 — PURE-STDLIB tests for the Hub-side Nova Pro correlator handler.

boto3 (+ botocore) is STUBBED into ``sys.modules`` so ``handler`` and ``awsio``
import offline (moto is not installable in the INTEGRATIONS_ONLY sandbox). The
``awsio`` seam is then monkeypatched with in-memory fakes so the stream handler's
control flow — the model-invocation-and-record path, the exponential-backoff retry,
the call-storm/stream-loop guard (fingerprint), the completeness gate, and the
honest model-error / unparseable recording — is exercised WITHOUT touching Bedrock
or DynamoDB.
"""

from __future__ import annotations

import decimal
import json
import os
import sys
import types
import unittest

# --- Stub boto3 + botocore so handler.py + awsio.py import offline ------------
if "boto3" not in sys.modules:
    _boto3 = types.ModuleType("boto3")
    _boto3.client = lambda *a, **k: None
    _boto3.resource = lambda *a, **k: None
    sys.modules["boto3"] = _boto3
if "botocore.config" not in sys.modules:
    _botocore = types.ModuleType("botocore")
    _config_mod = types.ModuleType("botocore.config")
    _config_mod.Config = lambda *a, **k: None
    _exc_mod = types.ModuleType("botocore.exceptions")

    class _ClientError(Exception):
        def __init__(self, response=None, operation_name="Invoke"):
            super().__init__(str(response))
            self.response = response or {}
            self.operation_name = operation_name

    _exc_mod.ClientError = _ClientError
    _botocore.config = _config_mod
    _botocore.exceptions = _exc_mod
    sys.modules["botocore"] = _botocore
    sys.modules["botocore.config"] = _config_mod
    sys.modules["botocore.exceptions"] = _exc_mod

os.environ.setdefault("TRACKING_TABLE", "ztie-tracking-test")
os.environ.setdefault("CORRELATION_CONTRACT_VERSION", "1.0")
os.environ.setdefault("NOVA_MODEL_ID", "us.amazon.nova-pro-v1:0")

from botocore.exceptions import ClientError

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


def _combined_event(complete=True):
    return {
        "inputs_present": ["static", "dynamic", "sanitized"] if complete else ["static"],
        "complete": complete,
        "sources": {
            "static": {"input": "static", "presence": "present", "highest_severity": "high", "total_findings": 2},
            "dynamic": {"input": "dynamic", "presence": "present" if complete else "absent", "outcome": "completed"} if complete else {"input": "dynamic", "presence": "absent"},
            "sanitized": {"input": "sanitized", "presence": "present" if complete else "absent"},
        },
        "signals": {
            "static_highest_severity": "high",
            "dynamic_outcome": "completed" if complete else None,
            "behavioral_event_count": 1,
            "behavioral_events": [
                {"offset_ms": 5, "category": "process", "syscall": "execve", "summary": "execve(/tmp/x)"}
            ],
        },
    }


def _item_with_combined(complete=True):
    return {
        "intake_id": _INTAKE_ID,
        "sha256": _SHA256,
        "status": "RECEIVED",
        "combined_event": _combined_event(complete),
        "combined_event_contract_version": "1.0",
    }


def _nova_response(text):
    return {
        "output": {"message": {"content": [{"text": text}]}},
        "usage": {"inputTokens": 800, "outputTokens": 200},
    }


_VALID_MODEL_TEXT = json.dumps({
    "summary": "The high-severity finding is exercised by the observed process launch.",
    "findings": [
        {"kind": "correlated", "severity": "high", "title": "Exec observed",
         "static_refs": ["S-1"], "behavioral_refs": ["execve"]}
    ],
})


class _FakeSeam:
    """In-memory stand-in for the awsio seam (Bedrock + DynamoDB)."""

    def __init__(self, item):
        self.item = item
        self.writes = []
        self.raise_conditional = False
        self.nova_calls = 0
        self.nova_impl = lambda **kw: (_nova_response(_VALID_MODEL_TEXT), 1, 850)

    def get_item(self, table, intake_id):
        if self.item is None or self.item.get("intake_id") != intake_id:
            return None
        return dict(self.item)

    def invoke_nova(self, **kw):
        self.nova_calls += 1
        return self.nova_impl(**kw)

    def put_correlation_result(self, table, **kw):
        if self.raise_conditional:
            raise ConditionalCheckFailedException("conditional failed")
        self.writes.append(kw)
        # Reflect the write back as DynamoDB would (this is what the guard reads).
        self.item["correlation_result"] = kw["correlation_result"]
        self.item["correlation_status"] = kw["status"]
        self.item["correlated_at"] = kw["correlated_at"]


class _SeamPatch:
    def __init__(self, fake):
        self.fake = fake
        self._orig = {}

    def __enter__(self):
        for name in ("get_item", "invoke_nova", "put_correlation_result"):
            self._orig[name] = getattr(awsio, name)
            setattr(awsio, name, getattr(self.fake, name))
        return self.fake

    def __exit__(self, *a):
        for name, fn in self._orig.items():
            setattr(awsio, name, fn)


class TestStreamKeyExtraction(unittest.TestCase):
    def test_insert_and_modify(self):
        event = {"Records": [_stream_record(_INTAKE_ID, "INSERT"), _stream_record("11111111-1111-4111-8111-111111111111")]}
        self.assertEqual(handler._intake_ids_from_event(event), [_INTAKE_ID, "11111111-1111-4111-8111-111111111111"])

    def test_remove_ignored(self):
        self.assertEqual(handler._intake_ids_from_event({"Records": [_stream_record(_INTAKE_ID, "REMOVE")]}), [])


class TestCorrelateHappyPath(unittest.TestCase):
    def test_correlates_and_writes(self):
        fake = _FakeSeam(_item_with_combined(complete=True))
        with _SeamPatch(fake):
            out = handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(out["batchItemFailures"], [])
        self.assertEqual(fake.nova_calls, 1)
        self.assertEqual(len(fake.writes), 1)
        result = fake.writes[0]["correlation_result"]
        self.assertEqual(result["status"], "correlated")
        self.assertEqual(result["intake_id"], _INTAKE_ID)
        self.assertEqual(result["sha256"], _SHA256)
        self.assertIn("correlation", result)
        self.assertEqual(result["input_tokens"], 800)
        self.assertIn("combined_event_fingerprint", result)


class TestGuardsAndGating(unittest.TestCase):
    def test_no_combined_event_is_noop(self):
        item = {"intake_id": _INTAKE_ID, "sha256": _SHA256, "status": "RECEIVED"}
        fake = _FakeSeam(item)
        with _SeamPatch(fake):
            out = handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(fake.nova_calls, 0)
        self.assertEqual(len(fake.writes), 0)
        self.assertEqual(out["batchItemFailures"], [])

    def test_incomplete_deferred_by_default(self):
        # CORRELATE_ONLY_WHEN_COMPLETE defaults True -> an incomplete event is deferred.
        fake = _FakeSeam(_item_with_combined(complete=False))
        with _SeamPatch(fake):
            handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(fake.nova_calls, 0)
        self.assertEqual(len(fake.writes), 0)

    def test_no_signals_is_noop(self):
        item = {
            "intake_id": _INTAKE_ID, "sha256": _SHA256,
            "combined_event": {"inputs_present": [], "complete": False, "sources": {}, "signals": {"behavioral_events": []}},
        }
        fake = _FakeSeam(item)
        with _SeamPatch(fake):
            handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(fake.nova_calls, 0)

    def test_missing_item_is_benign(self):
        fake = _FakeSeam(None)
        with _SeamPatch(fake):
            out = handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(out["batchItemFailures"], [])
        self.assertEqual(fake.nova_calls, 0)

    def test_no_call_storm_when_fingerprint_unchanged(self):
        # First stream event correlates; a second event over the SAME (now-updated)
        # item must NOT re-invoke the model (the call-storm / stream-loop guard).
        fake = _FakeSeam(_item_with_combined(complete=True))
        with _SeamPatch(fake):
            handler.handler({"Records": [_stream_record(_INTAKE_ID, seq="1")]})
            handler.handler({"Records": [_stream_record(_INTAKE_ID, seq="2")]})
        self.assertEqual(fake.nova_calls, 1, "must not re-correlate unchanged combined event")
        self.assertEqual(len(fake.writes), 1)

    def test_recorrelates_when_combined_event_changes(self):
        fake = _FakeSeam(_item_with_combined(complete=True))
        with _SeamPatch(fake):
            handler.handler({"Records": [_stream_record(_INTAKE_ID, seq="1")]})
            # The combined event changes (a new behavioral event lands) -> new
            # fingerprint -> correlate again.
            fake.item["combined_event"]["signals"]["behavioral_events"].append(
                {"offset_ms": 99, "category": "network", "syscall": "connect", "summary": "connect(x)"}
            )
            fake.item["combined_event"]["signals"]["behavioral_event_count"] = 2
            handler.handler({"Records": [_stream_record(_INTAKE_ID, seq="2")]})
        self.assertEqual(fake.nova_calls, 2)
        self.assertEqual(len(fake.writes), 2)

    def test_fingerprint_stable_across_decimal_roundtrip(self):
        # A Decimal round-trip of the same content must NOT look like a change (the
        # 3.1 live loop lesson) — else it would re-correlate forever.
        item = _item_with_combined(complete=True)
        fake = _FakeSeam(item)
        with _SeamPatch(fake):
            handler.handler({"Records": [_stream_record(_INTAKE_ID, seq="1")]})
            # Simulate DynamoDB returning numbers as Decimal on the next read.
            fake.item = _dynamodbify(fake.item)
            handler.handler({"Records": [_stream_record(_INTAKE_ID, seq="2")]})
        self.assertEqual(fake.nova_calls, 1, "Decimal round-trip must not trigger a re-correlate")


class TestHonestErrorRecording(unittest.TestCase):
    def test_model_error_recorded_not_fabricated(self):
        fake = _FakeSeam(_item_with_combined(complete=True))

        def _boom(**kw):
            raise RuntimeError("bedrock unavailable")

        fake.nova_impl = _boom
        with _SeamPatch(fake):
            out = handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(out["batchItemFailures"], [])  # recorded, not a retryable failure
        self.assertEqual(len(fake.writes), 1)
        result = fake.writes[0]["correlation_result"]
        self.assertEqual(result["status"], "model_error")
        self.assertNotIn("correlation", result)

    def test_unparseable_recorded(self):
        fake = _FakeSeam(_item_with_combined(complete=True))
        fake.nova_impl = lambda **kw: (_nova_response("this is not json"), 2, 700)
        with _SeamPatch(fake):
            handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        result = fake.writes[0]["correlation_result"]
        self.assertEqual(result["status"], "unparseable")
        self.assertEqual(result["attempts"], 2)
        self.assertNotIn("correlation", result)

    def test_conditional_race_is_benign(self):
        fake = _FakeSeam(_item_with_combined(complete=True))
        fake.raise_conditional = True
        with _SeamPatch(fake):
            out = handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(out["batchItemFailures"], [])


class TestRetryBackoff(unittest.TestCase):
    """Exercise the REAL exponential-backoff loop in awsio.invoke_nova with a fake
    Bedrock client + injected (no-wait) sleep."""

    def _client(self, fail_times, code="ThrottlingException", http_status=429):
        calls = {"n": 0}

        class _Body:
            def read(self_inner):
                return json.dumps(_nova_response(_VALID_MODEL_TEXT)).encode("utf-8")

        class _Client:
            def invoke_model(self_inner, **kw):
                calls["n"] += 1
                if calls["n"] <= fail_times:
                    raise ClientError(
                        response={"Error": {"Code": code}, "ResponseMetadata": {"HTTPStatusCode": http_status}},
                        operation_name="InvokeModel",
                    )
                return {"body": _Body()}

        return _Client(), calls

    def test_retries_then_succeeds(self):
        client, _calls = self._client(fail_times=2)
        slept = []
        awsio._bedrock = client
        try:
            body, attempts, _latency = awsio.invoke_nova(
                model_id="us.amazon.nova-pro-v1:0",
                body={"schemaVersion": "messages-v1"},
                max_attempts=5, base_delay=0.01, sleep=slept.append,
            )
        finally:
            awsio._bedrock = None
        self.assertEqual(attempts, 3, "2 throttles + 1 success = 3 attempts")
        self.assertEqual(len(slept), 2, "backed off twice")
        self.assertIsInstance(body, dict)

    def test_exhausts_budget_and_raises(self):
        client, calls = self._client(fail_times=10)
        awsio._bedrock = client
        try:
            with self.assertRaises(ClientError):
                awsio.invoke_nova(
                    model_id="us.amazon.nova-pro-v1:0", body={},
                    max_attempts=3, base_delay=0.01, sleep=lambda s: None,
                )
        finally:
            awsio._bedrock = None
        self.assertEqual(calls["n"], 3, "made exactly max_attempts calls")

    def test_non_retryable_not_retried(self):
        # A ValidationException (client error, 400) is deterministic — not retried.
        client, calls = self._client(fail_times=10, code="ValidationException", http_status=400)
        awsio._bedrock = client
        try:
            with self.assertRaises(ClientError):
                awsio.invoke_nova(
                    model_id="x", body={}, max_attempts=5, base_delay=0.01, sleep=lambda s: None,
                )
        finally:
            awsio._bedrock = None
        self.assertEqual(calls["n"], 1, "a non-retryable error is not retried")


class TestConfigPin(unittest.TestCase):
    def test_own_version_pin(self):
        self.assertEqual(handler.CORRELATION_CONTRACT_VERSION, "1.0")

    def test_model_id_default(self):
        self.assertTrue(handler.NOVA_MODEL_ID)


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
