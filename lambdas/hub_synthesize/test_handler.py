"""ZTIE Story 3.3 (RD-038) — PURE-STDLIB tests for the three-score scorer handler.

boto3 (+ botocore) is STUBBED into ``sys.modules`` so ``handler`` and ``awsio``
import offline. The ``awsio`` seam is monkeypatched with in-memory fakes so the
stream handler's control flow — the three scoped calls, per-score honest status,
PARTIAL results (one call fails), the fingerprint call-storm guard, the completeness
gate, and the conditional-race no-op — is exercised WITHOUT touching Bedrock or
DynamoDB. A separate class exercises the REAL backoff loop in ``awsio.invoke_nova``
with a fake Bedrock client (incl. the non-retryable-4xx trap).
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
os.environ.setdefault("SCORING_CONTRACT_VERSION", "1.0")
os.environ.setdefault("NOVA_MODEL_ID", "us.amazon.nova-pro-v1:0")

import awsio  # import after stubs + env above
import handler  # import after stubs + env above
from botocore.exceptions import ClientError

_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_SHA256 = "c" * 64


class ConditionalCheckFailedException(Exception):
    pass


def _stream_record(intake_id, event_name="MODIFY", seq="100"):
    return {
        "eventName": event_name,
        "dynamodb": {"Keys": {"intake_id": {"S": intake_id}}, "SequenceNumber": seq},
    }


def _combined_event(*, static="present", dynamic="present", complete=True):
    return {
        "inputs_present": [
            n for n, p in (("static", static), ("dynamic", dynamic)) if p == "present"
        ],
        "complete": complete,
        "sources": {
            "static": {"input": "static", "presence": static, "highest_severity": "high",
                       "total_findings": 2},
            "dynamic": {"input": "dynamic", "presence": dynamic, "outcome": "completed"},
            "sanitized": {"input": "sanitized", "presence": dynamic,
                          "capture_status": "sanitized"},
        },
        "signals": {
            "static_highest_severity": "high",
            "dynamic_outcome": "completed",
            "behavioral_event_count": 1,
            "behavioral_events": [
                {"offset_ms": 5, "category": "process", "syscall": "execve",
                 "summary": "execve(/tmp/x)"}
            ],
        },
    }


def _item(**kw):
    return {
        "intake_id": _INTAKE_ID,
        "sha256": _SHA256,
        "status": "RECEIVED",
        "combined_event": _combined_event(**kw),
    }


def _nova_response(score_val, rationale="r"):
    return {
        "output": {"message": {"content": [
            {"text": json.dumps({"score": score_val, "rationale": rationale})}
        ]}},
        "usage": {"inputTokens": 100, "outputTokens": 20},
    }


class _FakeSeam:
    """In-memory stand-in for the awsio seam (Bedrock + DynamoDB)."""

    def __init__(self, item):
        self.item = item
        self.writes = []
        self.raise_conditional = False
        self.nova_calls = 0
        # default: return a score based on the prompt kind embedded in the body
        self.nova_impl = self._default_nova

    def _default_nova(self, *, model_id, body, max_attempts):
        self.nova_calls += 1
        user = body["messages"][0]["content"][0]["text"]
        val = 20 if "STATIC_EVIDENCE" in user else 80 if "DYNAMIC_EVIDENCE" in user else 55
        return _nova_response(val), 1, 700

    def get_item(self, table, intake_id):
        if self.item is None or self.item.get("intake_id") != intake_id:
            return None
        return dict(self.item)

    def invoke_nova(self, **kw):
        return self.nova_impl(**kw)

    def put_scoring_result(self, table, **kw):
        if self.raise_conditional:
            raise ConditionalCheckFailedException("conditional failed")
        self.writes.append(kw)
        self.item["scoring_result"] = kw["scoring_result"]
        self.item["scored_at"] = kw["scored_at"]


class _SeamPatch:
    def __init__(self, fake):
        self.fake = fake
        self._orig = {}

    def __enter__(self):
        for name in ("get_item", "invoke_nova", "put_scoring_result"):
            self._orig[name] = getattr(awsio, name)
            setattr(awsio, name, getattr(self.fake, name))
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
            handler._intake_ids_from_event({"Records": [_stream_record(_INTAKE_ID, "REMOVE")]}), []
        )


class TestThreeScoreHappyPath(unittest.TestCase):
    def test_three_calls_three_scores(self):
        fake = _FakeSeam(_item())
        with _SeamPatch(fake):
            out = handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(out["batchItemFailures"], [])
        self.assertEqual(fake.nova_calls, 3, "one call per score (static/dynamic/combined)")
        self.assertEqual(len(fake.writes), 1)
        result = fake.writes[0]["scoring_result"]
        self.assertEqual(result["static"]["status"], "scored")
        self.assertEqual(result["dynamic"]["status"], "scored")
        self.assertEqual(result["combined"]["status"], "scored")
        self.assertEqual(result["static"]["score"], 20)
        self.assertEqual(result["dynamic"]["score"], 80)
        self.assertEqual(result["combined"]["score"], 55)
        self.assertEqual(result["intake_id"], _INTAKE_ID)
        self.assertIn("evidence_fingerprint", result)
        self.assertEqual(result["rubric_version"], "1.0")


class TestPartialResults(unittest.TestCase):
    def test_one_call_errors_others_still_scored(self):
        fake = _FakeSeam(_item())

        def impl(*, model_id, body, max_attempts):
            fake.nova_calls += 1
            user = body["messages"][0]["content"][0]["text"]
            if "DYNAMIC_EVIDENCE" in user:
                raise RuntimeError("bedrock unavailable")
            val = 20 if "STATIC_EVIDENCE" in user else 55
            return _nova_response(val), 1, 700

        fake.nova_impl = impl
        with _SeamPatch(fake):
            out = handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(out["batchItemFailures"], [])
        result = fake.writes[0]["scoring_result"]
        self.assertEqual(result["static"]["status"], "scored")
        self.assertEqual(result["dynamic"]["status"], "model_error")  # recorded honestly
        self.assertNotIn("score", result["dynamic"])
        self.assertEqual(result["combined"]["status"], "scored")

    def test_unparseable_recorded(self):
        fake = _FakeSeam(_item())
        fake.nova_impl = lambda **kw: (
            {"output": {"message": {"content": [{"text": "no json here"}]}}}, 2, 500
        )
        with _SeamPatch(fake):
            handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        result = fake.writes[0]["scoring_result"]
        self.assertEqual(result["static"]["status"], "unparseable")
        self.assertEqual(result["static"]["attempts"], 2)
        self.assertNotIn("score", result["static"])

    def test_absent_static_lane_scored_skipped(self):
        fake = _FakeSeam(_item(static="absent"))
        with _SeamPatch(fake):
            handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        result = fake.writes[0]["scoring_result"]
        self.assertEqual(result["static"]["status"], "skipped_no_evidence")
        self.assertNotIn("score", result["static"])
        self.assertEqual(result["dynamic"]["status"], "scored")
        # combined still runs (it honestly reflects the absent static lane)
        self.assertEqual(result["combined"]["status"], "scored")
        # 2 calls: dynamic + combined (static skipped, no call)
        self.assertEqual(fake.nova_calls, 2)


class TestGuardsAndGating(unittest.TestCase):
    def test_no_combined_event_is_noop(self):
        fake = _FakeSeam({"intake_id": _INTAKE_ID, "sha256": _SHA256})
        with _SeamPatch(fake):
            out = handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(fake.nova_calls, 0)
        self.assertEqual(len(fake.writes), 0)
        self.assertEqual(out["batchItemFailures"], [])

    def test_incomplete_deferred_by_default(self):
        fake = _FakeSeam(_item(complete=False))
        with _SeamPatch(fake):
            handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(fake.nova_calls, 0)
        self.assertEqual(len(fake.writes), 0)

    def test_missing_item_benign(self):
        fake = _FakeSeam(None)
        with _SeamPatch(fake):
            out = handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(out["batchItemFailures"], [])
        self.assertEqual(fake.nova_calls, 0)

    def test_no_call_storm_when_fingerprint_unchanged(self):
        fake = _FakeSeam(_item())
        with _SeamPatch(fake):
            handler.handler({"Records": [_stream_record(_INTAKE_ID, seq="1")]})
            handler.handler({"Records": [_stream_record(_INTAKE_ID, seq="2")]})
        self.assertEqual(fake.nova_calls, 3, "must not re-score unchanged evidence (3 calls total)")
        self.assertEqual(len(fake.writes), 1)

    def test_rescores_when_evidence_changes(self):
        fake = _FakeSeam(_item())
        with _SeamPatch(fake):
            handler.handler({"Records": [_stream_record(_INTAKE_ID, seq="1")]})
            fake.item["combined_event"]["signals"]["static_highest_severity"] = "critical"
            handler.handler({"Records": [_stream_record(_INTAKE_ID, seq="2")]})
        self.assertEqual(fake.nova_calls, 6, "changed evidence -> re-score (3 + 3)")
        self.assertEqual(len(fake.writes), 2)

    def test_fingerprint_stable_across_decimal_roundtrip(self):
        fake = _FakeSeam(_item())
        with _SeamPatch(fake):
            handler.handler({"Records": [_stream_record(_INTAKE_ID, seq="1")]})
            fake.item = _dynamodbify(fake.item)
            handler.handler({"Records": [_stream_record(_INTAKE_ID, seq="2")]})
        self.assertEqual(fake.nova_calls, 3, "Decimal round-trip must not re-score")

    def test_conditional_race_benign(self):
        fake = _FakeSeam(_item())
        fake.raise_conditional = True
        with _SeamPatch(fake):
            out = handler.handler({"Records": [_stream_record(_INTAKE_ID)]})
        self.assertEqual(out["batchItemFailures"], [])


class TestRetryBackoff(unittest.TestCase):
    """Exercise the REAL exponential-backoff loop in awsio.invoke_nova."""

    def _client(self, fail_times, code="ThrottlingException", http_status=429):
        calls = {"n": 0}

        class _Body:
            def read(self_inner):
                return json.dumps(_nova_response(50)).encode("utf-8")

        class _Client:
            def invoke_model(self_inner, **kw):
                calls["n"] += 1
                if calls["n"] <= fail_times:
                    raise ClientError(
                        response={"Error": {"Code": code},
                                  "ResponseMetadata": {"HTTPStatusCode": http_status}},
                        operation_name="InvokeModel",
                    )
                return {"body": _Body()}

        return _Client(), calls

    def test_retries_then_succeeds(self):
        client, _ = self._client(fail_times=2)
        slept = []
        awsio._bedrock = client
        try:
            body, attempts, _lat = awsio.invoke_nova(
                model_id="m", body={"schemaVersion": "messages-v1"},
                max_attempts=5, base_delay=0.01, sleep=slept.append,
            )
        finally:
            awsio._bedrock = None
        self.assertEqual(attempts, 3)
        self.assertEqual(len(slept), 2)
        self.assertIsInstance(body, dict)

    def test_exhausts_budget_and_raises(self):
        client, calls = self._client(fail_times=10)
        awsio._bedrock = client
        try:
            with self.assertRaises(ClientError):
                awsio.invoke_nova(model_id="m", body={}, max_attempts=3,
                                  base_delay=0.01, sleep=lambda s: None)
        finally:
            awsio._bedrock = None
        self.assertEqual(calls["n"], 3)

    def test_non_retryable_not_retried(self):
        # ValidationException carries a 4xx (400), NOT 429 — must not be retried
        # (the retry-loop test trap from the 3.2 build).
        client, calls = self._client(fail_times=10, code="ValidationException", http_status=400)
        awsio._bedrock = client
        try:
            with self.assertRaises(ClientError):
                awsio.invoke_nova(model_id="m", body={}, max_attempts=5,
                                  base_delay=0.01, sleep=lambda s: None)
        finally:
            awsio._bedrock = None
        self.assertEqual(calls["n"], 1, "a non-retryable error is not retried")


class TestConfigPin(unittest.TestCase):
    def test_scoring_version_pin(self):
        self.assertEqual(handler.SCORING_CONTRACT_VERSION, "1.0")

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
