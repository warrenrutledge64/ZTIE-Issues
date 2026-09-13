"""ZTIE Story 4.2 (RD-042) — PURE-STDLIB tests for the dashboard-orchestrator handler.

boto3 is STUBBED into ``sys.modules`` so ``handler`` and ``awsio`` import offline. The
``awsio`` seam is monkeypatched with an in-memory fake so the handler's control flow —
view resolution (explicit + inferred), the per-intake read-and-assemble path, the fleet
read-and-assemble path, the not-found / malformed-key error envelopes, the
malformed-request guard, and the READ-only invariant — is exercised WITHOUT touching
DynamoDB. There is NO write path (RD-042: 4.2 is read-only) and NO Bedrock (RD-042: no
model call).
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
# awsio also imports boto3.dynamodb.conditions.Key — stub that path too.
if "boto3.dynamodb" not in sys.modules:
    _ddb = types.ModuleType("boto3.dynamodb")
    _cond = types.ModuleType("boto3.dynamodb.conditions")

    class _Key:
        def __init__(self, name):
            self.name = name

        def eq(self, val):
            return (self.name, "eq", val)

    _cond.Key = _Key
    sys.modules["boto3.dynamodb"] = _ddb
    sys.modules["boto3.dynamodb.conditions"] = _cond

os.environ.setdefault("TRACKING_TABLE", "ztie-tracking-test")
os.environ.setdefault("DASHBOARD_CONTRACT_VERSION", "1.0")
os.environ.setdefault("STATUS_CONTRACT_VERSION", "1.0")

import awsio  # import after stubs + env above
import handler  # import after stubs + env above

_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_INTAKE_ID_2 = "7f1e2d3c-4b5a-4c6d-8e9f-0a1b2c3d4e5f"
_SHA256 = "c" * 64

_BANNED_EFFECTIVE_KEYS = frozenset(
    {"verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean"}
)


def _verdict(rv="INCONCLUSIVE"):
    return {
        "status": "recommended",
        "recommended_verdict": rv,
        "human_decision": "pending",
        "rubric_version": "1.0",
        "recommendation_basis": {"driver": "combined_score", "summary": "advisory only"},
    }


def _full_item(intake_id=_INTAKE_ID):
    return {
        "intake_id": intake_id,
        "sha256": _SHA256,
        "status": "COMPLETE",
        "received_at": "2026-09-13T00:00:00Z",
        "combined_event": {"x": 1},
        "correlation_result": {"y": 1},
        "scoring_result": {
            "static": {"status": "scored", "score": 70},
            "dynamic": {"status": "scored", "score": 30},
            "combined": {"status": "scored", "score": 90},
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
        "verdict_result": _verdict("FAIL"),
    }


class _FakeSeam:
    """In-memory stand-in for the awsio seam (DynamoDB READ only)."""

    def __init__(self, *, item=None, recent=None, more=False):
        self.item = item
        self.recent = recent or []
        self.more = more
        self.reads = 0
        self.queries = 0

    def get_item(self, table_name, intake_id):
        self.reads += 1
        return self.item

    def recent_items(self, table_name, *, limit, statuses=None):
        self.queries += 1
        return self.recent[:limit], self.more or len(self.recent) > limit


class HandlerTestBase(unittest.TestCase):
    def setUp(self):
        self._orig_get = awsio.get_item
        self._orig_recent = awsio.recent_items

    def tearDown(self):
        awsio.get_item = self._orig_get
        awsio.recent_items = self._orig_recent

    def _install(self, seam):
        awsio.get_item = seam.get_item
        awsio.recent_items = seam.recent_items


class TestIntakeView(HandlerTestBase):
    def test_direct_invoke_intake(self):
        seam = _FakeSeam(item=_full_item())
        self._install(seam)
        out = handler.handler({"intake_id": _INTAKE_ID})
        self.assertNotIn("error", out)
        self.assertEqual(out["view"], "intake")
        self.assertEqual(out["intake"]["status"]["intake_id"], _INTAKE_ID)
        self.assertEqual(out["intake"]["status"]["overall_stage"], "recommended")
        self.assertEqual(out["intake"]["threat"]["tier"], "critical")
        self.assertEqual(out["intake"]["action"]["recommended_verdict"], "FAIL")
        self.assertEqual(out["intake"]["action"]["decision"], "pending")
        self.assertIs(out["intake"]["action"]["advisory"], True)
        self.assertEqual(seam.reads, 1)

    def test_explicit_view_intake(self):
        seam = _FakeSeam(item=_full_item())
        self._install(seam)
        out = handler.handler({"view": "intake", "intake_id": _INTAKE_ID})
        self.assertEqual(out["view"], "intake")

    def test_api_gateway_pathparameters_shape(self):
        seam = _FakeSeam(item=_full_item())
        self._install(seam)
        out = handler.handler({"pathParameters": {"intake_id": _INTAKE_ID}})
        self.assertEqual(out["view"], "intake")
        self.assertEqual(out["intake"]["status"]["intake_id"], _INTAKE_ID)

    def test_no_banned_keys(self):
        seam = _FakeSeam(item=_full_item())
        self._install(seam)
        out = handler.handler({"intake_id": _INTAKE_ID})
        self.assertIsNone(_find_banned(out))

    def test_read_only_never_writes(self):
        seam = _FakeSeam(item=_full_item())
        self._install(seam)
        before = dict(seam.item)
        handler.handler({"intake_id": _INTAKE_ID})
        self.assertEqual(seam.item, before)
        self.assertFalse(hasattr(awsio, "put_item"))
        self.assertFalse(hasattr(awsio, "update_item"))


class TestFleetView(HandlerTestBase):
    def test_fleet_default_when_no_intake_id(self):
        seam = _FakeSeam(recent=[_full_item(), _full_item(_INTAKE_ID_2)])
        self._install(seam)
        out = handler.handler({})
        self.assertEqual(out["view"], "fleet")
        self.assertEqual(out["fleet"]["returned_count"], 2)
        self.assertEqual(seam.queries, 1)

    def test_explicit_fleet_view(self):
        seam = _FakeSeam(recent=[_full_item()])
        self._install(seam)
        out = handler.handler({"view": "fleet"})
        self.assertEqual(out["view"], "fleet")
        self.assertEqual(out["fleet"]["returned_count"], 1)

    def test_fleet_limit_passed_and_clamped(self):
        seam = _FakeSeam(recent=[_full_item(f"{i:08d}-0000-4000-8000-000000000000") for i in range(10)])
        self._install(seam)
        out = handler.handler({"view": "fleet", "limit": "3"})
        self.assertEqual(out["fleet"]["returned_count"], 3)
        self.assertTrue(out["fleet"]["truncated"])

    def test_fleet_no_banned_keys(self):
        seam = _FakeSeam(recent=[_full_item()])
        self._install(seam)
        out = handler.handler({"view": "fleet"})
        self.assertIsNone(_find_banned(out))


class TestErrors(HandlerTestBase):
    def test_intake_missing_id_is_400(self):
        self._install(_FakeSeam(item=None))
        out = handler.handler({"view": "intake"})
        self.assertEqual(out["error"]["code"], 400)

    def test_intake_malformed_id_is_400(self):
        self._install(_FakeSeam(item=None))
        out = handler.handler({"intake_id": "not-a-uuid"})
        self.assertEqual(out["error"]["code"], 400)

    def test_intake_not_found_is_404(self):
        self._install(_FakeSeam(item=None))
        out = handler.handler({"intake_id": _INTAKE_ID})
        self.assertEqual(out["error"]["code"], 404)

    def test_intake_missing_integrity_key_is_422(self):
        self._install(_FakeSeam(item={"intake_id": _INTAKE_ID}))
        out = handler.handler({"intake_id": _INTAKE_ID})
        self.assertEqual(out["error"]["code"], 422)

    def test_unknown_view_is_400(self):
        self._install(_FakeSeam())
        out = handler.handler({"view": "bogus"})
        self.assertEqual(out["error"]["code"], 400)


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
