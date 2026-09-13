"""ZTIE Story 4.1 (RD-041) — PURE-STDLIB tests for the status-orchestrator handler.

boto3 is STUBBED into ``sys.modules`` so ``handler`` and ``awsio`` import offline. The
``awsio`` seam is monkeypatched with an in-memory fake so the handler's control flow —
intake_id extraction (direct + API-shaped), the read-and-assemble path, the not-found /
malformed-key error envelopes, and the malformed-request guard — is exercised WITHOUT
touching DynamoDB. There is NO write path (RD-041: 4.1 is read-only) and NO Bedrock
(RD-041: no model call), so there is no write / backoff / stream class here.
"""

from __future__ import annotations

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
os.environ.setdefault("STATUS_CONTRACT_VERSION", "1.0")

import awsio  # import after stubs + env above
import handler  # import after stubs + env above

_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_SHA256 = "c" * 64

_BANNED_EFFECTIVE_KEYS = frozenset(
    {"verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean"}
)


def _verdict(rv="INCONCLUSIVE"):
    return {
        "contract_version": "1.0",
        "intake_id": _INTAKE_ID,
        "sha256": _SHA256,
        "recommended_at": "2026-09-13T00:00:00Z",
        "status": "recommended",
        "recommended_verdict": rv,
        "human_decision": "pending",
        "recommendation_basis": {"driver": "combined_score", "summary": "advisory only"},
    }


def _full_item():
    return {
        "intake_id": _INTAKE_ID,
        "sha256": _SHA256,
        "status": "RECEIVED",
        "received_at": "2026-09-13T00:00:00Z",
        "combined_event": {"x": 1},
        "correlation_result": {"y": 1},
        "scoring_result": {
            "static": {"status": "scored", "score": 70},
            "dynamic": {"status": "scored", "score": 30},
            "combined": {"status": "scored", "score": 55},
            "rubric_version": "1.0",
        },
        "remediation_result": {
            "status": "assessed",
            "assessment": {
                "highest_gap_severity": "high",
                "counts": {
                    "detailed_finding_count": 1,
                    "gap_count": 1,
                    "remediation_count": 2,
                    "contradiction": 0,
                },
            },
        },
        "verdict_result": _verdict(),
    }


class _FakeSeam:
    """In-memory stand-in for the awsio seam (DynamoDB READ only)."""

    def __init__(self, item):
        self.item = item
        self.reads = 0

    def get_item(self, table_name, intake_id):
        self.reads += 1
        return self.item


class HandlerTestBase(unittest.TestCase):
    def setUp(self):
        self._orig_get = awsio.get_item

    def tearDown(self):
        awsio.get_item = self._orig_get

    def _install(self, seam):
        awsio.get_item = seam.get_item


class TestAssemble(HandlerTestBase):
    def test_direct_invoke_returns_status(self):
        seam = _FakeSeam(_full_item())
        self._install(seam)
        out = handler.handler({"intake_id": _INTAKE_ID})
        self.assertNotIn("error", out)
        self.assertEqual(out["intake_id"], _INTAKE_ID)
        self.assertEqual(out["overall_stage"], "recommended")
        self.assertEqual(out["recommendation"]["recommended_verdict"], "INCONCLUSIVE")
        self.assertEqual(out["recommendation"]["decision"], "pending")
        self.assertIs(out["recommendation"]["advisory"], True)
        self.assertEqual(seam.reads, 1)

    def test_api_gateway_pathparameters_shape(self):
        seam = _FakeSeam(_full_item())
        self._install(seam)
        out = handler.handler({"pathParameters": {"intake_id": _INTAKE_ID}})
        self.assertEqual(out["intake_id"], _INTAKE_ID)

    def test_api_gateway_querystring_shape(self):
        seam = _FakeSeam(_full_item())
        self._install(seam)
        out = handler.handler({"queryStringParameters": {"intake_id": _INTAKE_ID}})
        self.assertEqual(out["intake_id"], _INTAKE_ID)

    def test_view_never_carries_effective_verdict_key(self):
        seam = _FakeSeam(_full_item())
        self._install(seam)
        out = handler.handler({"intake_id": _INTAKE_ID})
        self.assertIsNone(_find_banned(out))

    def test_read_only_never_writes(self):
        # The seam has no put_* at all — assert none was added and the item is untouched.
        seam = _FakeSeam(_full_item())
        self._install(seam)
        before = dict(seam.item)
        handler.handler({"intake_id": _INTAKE_ID})
        self.assertEqual(seam.item, before)
        self.assertFalse(hasattr(awsio, "put_status_result"))


class TestErrors(HandlerTestBase):
    def test_missing_intake_id_is_400(self):
        out = handler.handler({})
        self.assertEqual(out["error"]["code"], 400)

    def test_malformed_intake_id_is_400(self):
        out = handler.handler({"intake_id": "not-a-uuid"})
        self.assertEqual(out["error"]["code"], 400)

    def test_not_found_is_404(self):
        seam = _FakeSeam(None)
        self._install(seam)
        out = handler.handler({"intake_id": _INTAKE_ID})
        self.assertEqual(out["error"]["code"], 404)

    def test_missing_integrity_key_is_422(self):
        seam = _FakeSeam({"intake_id": _INTAKE_ID})  # no sha256
        self._install(seam)
        out = handler.handler({"intake_id": _INTAKE_ID})
        self.assertEqual(out["error"]["code"], 422)


class TestConfig(unittest.TestCase):
    def test_missing_table_raises(self):
        orig = handler.TRACKING_TABLE
        handler.TRACKING_TABLE = ""
        try:
            with self.assertRaises(RuntimeError):
                handler.handler({"intake_id": _INTAKE_ID})
        finally:
            handler.TRACKING_TABLE = orig


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
