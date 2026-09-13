"""ZTIE Story 4.5 (RD-045) — unit tests for the report orchestrator handler.

boto3 is STUBBED into ``sys.modules`` so ``handler`` and ``awsio`` import offline. The
``awsio`` seam is monkeypatched with an in-memory fake so the handler's control flow —
intake_id resolution (top-level + API-Gateway-shaped), the read-and-assemble path, the
format selection (json / html / both), the not-found / malformed-key error envelopes, the
malformed-request guard, and the READ-only invariant — is exercised WITHOUT touching
DynamoDB. There is NO write path (RD-045: 4.5 is read-only) and NO Bedrock (RD-045: no
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

os.environ.setdefault("TRACKING_TABLE", "ztie-tracking-test")
os.environ.setdefault("REPORT_CONTRACT_VERSION", "1.0")
os.environ.setdefault("STATUS_CONTRACT_VERSION", "1.0")

import awsio  # import after stubs + env above
import handler  # import after stubs + env above

_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_SHA256 = "c" * 64

_BANNED_EFFECTIVE_KEYS = frozenset(
    {"verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean"}
)


def _full_item():
    return {
        "intake_id": _INTAKE_ID,
        "sha256": _SHA256,
        "status": "RECEIVED",
        "received_at": "2026-09-13T16:00:00Z",
        "combined_event": {},
        "correlation_result": {
            "status": "correlated",
            "correlation": {"summary": "c", "highest_correlation_severity": "high",
                            "finding_count": 0, "findings": []},
        },
        "scoring_result": {
            "static": {"status": "scored", "score": 50},
            "dynamic": {"status": "scored", "score": 30},
            "combined": {"status": "scored", "score": 70},
            "rubric_version": "1.0",
        },
        "remediation_result": {
            "status": "assessed",
            "assessment": {
                "summary": "s", "highest_gap_severity": "high",
                "counts": {"detailed_finding_count": 0, "candidate_false_positive_count": 0,
                           "gap_count": 0, "remediation_count": 1, "contradiction": 0},
                "detailed_findings": [], "candidate_false_positives": [], "gaps": [],
                "prioritized_remediations": [
                    {"rank": 1, "priority": "high", "title": "fix", "action": "do it",
                     "basis": "score 70", "source_kind": "correlated", "severity": "high"}
                ],
            },
        },
        "verdict_result": {"status": "recommended", "recommended_verdict": "INCONCLUSIVE",
                           "rubric_version": "1.0",
                           "recommendation_basis": {"summary": "advisory INCONCLUSIVE"}},
    }


class _FakeStore:
    """In-memory stand-in for the awsio READ seam. Records reads; has NO write path."""

    def __init__(self, items):
        self.items = items
        self.reads = 0

    def get_item(self, table_name, intake_id):
        self.reads += 1
        return self.items.get(intake_id)


class HandlerTestBase(unittest.TestCase):
    def setUp(self):
        self._orig_get = awsio.get_item
        self.store = _FakeStore({_INTAKE_ID: _full_item()})
        awsio.get_item = self.store.get_item

    def tearDown(self):
        awsio.get_item = self._orig_get


class TestHappyPath(HandlerTestBase):
    def test_default_format_both(self):
        out = handler.handler({"intake_id": _INTAKE_ID})
        self.assertIn("report", out)
        self.assertIn("html", out)
        self.assertEqual(out["report"]["contract_version"], "1.0")
        self.assertEqual(out["report"]["intake_id"], _INTAKE_ID)
        self.assertTrue(out["html"].startswith("<!doctype html>"))

    def test_format_json_only(self):
        out = handler.handler({"intake_id": _INTAKE_ID, "format": "json"})
        self.assertIn("report", out)
        self.assertNotIn("html", out)

    def test_format_html_only(self):
        out = handler.handler({"intake_id": _INTAKE_ID, "format": "html"})
        self.assertIn("html", out)
        self.assertNotIn("report", out)

    def test_api_gateway_pathparameters_shape(self):
        out = handler.handler({"pathParameters": {"intake_id": _INTAKE_ID}})
        self.assertIn("report", out)
        self.assertEqual(out["report"]["intake_id"], _INTAKE_ID)

    def test_three_tiers_present(self):
        rpt = handler.handler({"intake_id": _INTAKE_ID, "format": "json"})["report"]
        self.assertIn("executive", rpt)
        self.assertIn("security", rpt)
        self.assertIn("developer", rpt)

    def test_no_effective_verdict_key(self):
        out = handler.handler({"intake_id": _INTAKE_ID})

        def walk(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    yield k
                    yield from walk(v)
            elif isinstance(obj, list):
                for v in obj:
                    yield from walk(v)

        keys = set(walk(out["report"]))
        self.assertFalse(keys & _BANNED_EFFECTIVE_KEYS)


class TestErrorPaths(HandlerTestBase):
    def test_missing_intake_id_400(self):
        out = handler.handler({})
        self.assertEqual(out["error"]["code"], 400)

    def test_malformed_intake_id_400(self):
        out = handler.handler({"intake_id": "not-a-uuid"})
        self.assertEqual(out["error"]["code"], 400)

    def test_not_found_404(self):
        out = handler.handler({"intake_id": "00000000-0000-4000-8000-000000000000"})
        self.assertEqual(out["error"]["code"], 404)

    def test_missing_integrity_key_422(self):
        # An item present but missing sha256 -> 422.
        self.store.items["11111111-1111-4111-8111-111111111111"] = {
            "intake_id": "11111111-1111-4111-8111-111111111111"
        }
        out = handler.handler({"intake_id": "11111111-1111-4111-8111-111111111111"})
        self.assertEqual(out["error"]["code"], 422)


class TestReadOnly(HandlerTestBase):
    def test_only_reads_never_writes(self):
        # The fake store has no write method; a write attempt would AttributeError.
        handler.handler({"intake_id": _INTAKE_ID})
        self.assertEqual(self.store.reads, 1)
        self.assertFalse(hasattr(self.store, "put_item"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
