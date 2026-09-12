"""ZTIE Story 3.3 (RD-038) — PURE-STDLIB tests for the three-score risk logic.
No boto3, no model, no I/O — exercises score.py directly.
"""

from __future__ import annotations

import json
import unittest

import score

_BANNED_VERDICT_KEYS = frozenset(
    {"verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean"}
)


def _combined_event(*, static="present", dynamic="present", complete=True):
    return {
        "inputs_present": [
            n for n, p in (("static", static), ("dynamic", dynamic)) if p == "present"
        ],
        "complete": complete,
        "sources": {
            "static": {"input": "static", "presence": static, "highest_severity": "high",
                       "total_findings": 3},
            "dynamic": {"input": "dynamic", "presence": dynamic, "outcome": "completed"},
            "sanitized": {"input": "sanitized", "presence": dynamic,
                          "capture_status": "sanitized", "truncated": False},
        },
        "signals": {
            "static_highest_severity": "high",
            "dynamic_outcome": "completed",
            "behavioral_event_count": 2,
            "behavioral_events": [
                {"offset_ms": 5, "category": "process", "syscall": "execve",
                 "summary": "execve(/tmp/x)", "redacted": False},
                {"offset_ms": 12, "category": "network", "syscall": "connect",
                 "summary": "connect(1.2.3.4:443)", "redacted": False},
            ],
        },
    }


def _no_banned_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in _BANNED_VERDICT_KEYS:
                return k
            deeper = _no_banned_keys(v)
            if deeper:
                return f"{k}.{deeper}"
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            deeper = _no_banned_keys(v)
            if deeper:
                return f"[{i}].{deeper}"
    return None


class TestEvidenceViews(unittest.TestCase):
    def test_static_view_is_static_only(self):
        ev = score.static_evidence(_combined_event())
        self.assertEqual(ev["presence"], "present")
        self.assertEqual(ev["highest_severity"], "high")
        self.assertEqual(ev["total_findings"], 3)
        # static view must NOT carry dynamic behavior
        self.assertNotIn("behavioral_events", ev)
        self.assertNotIn("outcome", ev)

    def test_dynamic_view_is_dynamic_only(self):
        ev = score.dynamic_evidence(_combined_event())
        self.assertEqual(ev["presence"], "present")
        self.assertEqual(ev["outcome"], "completed")
        self.assertEqual(len(ev["behavioral_events"]), 2)
        # dynamic view must NOT carry static findings
        self.assertNotIn("highest_severity", ev)
        self.assertNotIn("total_findings", ev)

    def test_combined_view_has_both(self):
        ev = score.combined_evidence(_combined_event())
        self.assertIn("static", ev)
        self.assertIn("dynamic", ev)
        self.assertTrue(ev["complete"])
        # combined view carries the two EVIDENCE views, NOT any scores
        self.assertNotIn("static_score", ev)
        self.assertNotIn("score", ev)

    def test_has_evidence_helpers(self):
        self.assertTrue(score.has_static_evidence(_combined_event()))
        self.assertTrue(score.has_dynamic_evidence(_combined_event()))
        self.assertFalse(score.has_static_evidence(_combined_event(static="absent")))
        self.assertFalse(score.has_dynamic_evidence(_combined_event(dynamic="absent")))

    def test_behavioral_events_prompt_capped(self):
        ev_dict = _combined_event()
        ev_dict["signals"]["behavioral_events"] = [
            {"offset_ms": i, "category": "x", "syscall": "s", "summary": "y"}
            for i in range(500)
        ]
        ev = score.dynamic_evidence(ev_dict)
        self.assertLessEqual(len(ev["behavioral_events"]), 200)
        self.assertTrue(ev["behavioral_events_prompt_capped"])


class TestPromptBuilding(unittest.TestCase):
    def test_all_three_prompts_share_the_rubric_and_forbid_verdict(self):
        ce = _combined_event()
        for kind, ev in (
            ("static", score.static_evidence(ce)),
            ("dynamic", score.dynamic_evidence(ce)),
            ("combined", score.combined_evidence(ce)),
        ):
            body = score.build_invoke_body(kind, ev)
            system = body["system"][0]["text"]
            # shared rubric present + comparable scale
            self.assertIn("0-100", system)
            self.assertIn("HIGHER = RISKIER", system)
            # verdict explicitly forbidden
            self.assertIn("MUST NOT render a verdict", system)
            # asks for score + rationale only
            self.assertIn('"score"', system)
            self.assertIn('"rationale"', system)
            # temperature 0 for reproducibility
            self.assertEqual(body["inferenceConfig"]["temperature"], 0.0)

    def test_system_instruction_is_identical_across_kinds(self):
        # The RUBRIC + scale are the SAME in all three (only the user turn differs).
        ce = _combined_event()
        systems = {
            score.build_invoke_body(k, e)["system"][0]["text"]
            for k, e in (
                ("static", score.static_evidence(ce)),
                ("dynamic", score.dynamic_evidence(ce)),
                ("combined", score.combined_evidence(ce)),
            )
        }
        self.assertEqual(len(systems), 1, "system instruction (rubric) must be identical")

    def test_user_message_scopes_differ(self):
        ce = _combined_event()
        s = score.build_user_message("static", score.static_evidence(ce))
        d = score.build_user_message("dynamic", score.dynamic_evidence(ce))
        self.assertIn("STATIC", s)
        self.assertIn("DYNAMIC", d)
        self.assertNotEqual(s, d)


class TestResponseParsing(unittest.TestCase):
    def _resp(self, text):
        return {"output": {"message": {"content": [{"text": text}]}}}

    def test_clean_json(self):
        s, r = score.parse_score(json.dumps({"score": 72, "rationale": "high sev"}))
        self.assertEqual(s, 72)
        self.assertEqual(r, "high sev")

    def test_fenced_json(self):
        s, _ = score.parse_score('```json\n{"score": 40, "rationale": "x"}\n```')
        self.assertEqual(s, 40)

    def test_prose_wrapped_json(self):
        s, _ = score.parse_score('Here is my assessment: {"score": 15, "rationale": "low"} done')
        self.assertEqual(s, 15)

    def test_score_clamped_to_range(self):
        self.assertEqual(score.parse_score(json.dumps({"score": 250}))[0], 100)
        self.assertEqual(score.parse_score(json.dumps({"score": -5}))[0], 0)

    def test_numeric_string_score(self):
        self.assertEqual(score.parse_score(json.dumps({"score": "83"}))[0], 83)

    def test_float_score_rounded(self):
        self.assertEqual(score.parse_score(json.dumps({"score": 66.7}))[0], 67)

    def test_unparseable_returns_none(self):
        self.assertEqual(score.parse_score("not json at all")[0], None)
        self.assertEqual(score.parse_score(json.dumps({"rationale": "no score"}))[0], None)
        self.assertEqual(score.parse_score(None)[0], None)

    def test_verdict_field_in_response_is_ignored(self):
        # A model that sneaks a verdict field: only score+rationale are read.
        s, _r = score.parse_score(json.dumps({"score": 30, "rationale": "ok", "verdict": "safe"}))
        self.assertEqual(s, 30)
        # parse_score returns only (score, rationale) — no way to carry a verdict.

    def test_extract_text_tolerant(self):
        self.assertIsNone(score.extract_text({"garbage": 1}))
        self.assertIsNone(score.extract_text("string"))
        self.assertEqual(score.extract_text(self._resp("hi")), "hi")


class TestResultAssembly(unittest.TestCase):
    def test_scored_block(self):
        b = score.build_score_block(status="scored", score=55, rationale="r",
                                    model_id="m", attempts=1, latency_ms=900,
                                    input_tokens=10, output_tokens=5)
        self.assertEqual(b["status"], "scored")
        self.assertEqual(b["score"], 55)
        self.assertEqual(b["rationale"], "r")
        self.assertEqual(b["attempts"], 1)

    def test_failed_block_has_no_score(self):
        b = score.build_score_block(status="model_error", status_detail="ThrottlingException")
        self.assertEqual(b["status"], "model_error")
        self.assertNotIn("score", b)
        self.assertNotIn("rationale", b)

    def test_skipped_block(self):
        b = score.build_score_block(status="skipped_no_evidence", status_detail="no static")
        self.assertEqual(b["status"], "skipped_no_evidence")
        self.assertNotIn("score", b)

    def test_score_clamped_in_block(self):
        b = score.build_score_block(status="scored", score=999)
        self.assertEqual(b["score"], 100)

    def test_build_result_shape(self):
        blk = score.build_score_block(status="scored", score=50, rationale="r")
        skip = score.build_score_block(status="skipped_no_evidence")
        result = score.build_result(
            intake_id="62360e03-dfb1-4655-ac52-2a55345ab6f0", sha256="a" * 64,
            scored_at="2026-09-13T00:00:00Z", contract_version="1.0",
            static_block=blk, dynamic_block=skip, combined_block=blk,
            combined_complete=True,
        )
        for k in ("contract_version", "intake_id", "sha256", "scored_at",
                  "static", "dynamic", "combined"):
            self.assertIn(k, result)
        self.assertEqual(result["rubric_version"], score.RUBRIC_VERSION)
        self.assertTrue(result["combined_complete"])

    def test_no_verdict_anywhere(self):
        blk = score.build_score_block(status="scored", score=90, rationale="risky")
        result = score.build_result(
            intake_id="62360e03-dfb1-4655-ac52-2a55345ab6f0", sha256="a" * 64,
            scored_at="2026-09-13T00:00:00Z", contract_version="1.0",
            static_block=blk, dynamic_block=blk, combined_block=blk,
        )
        self.assertIsNone(_no_banned_keys(result))


if __name__ == "__main__":
    unittest.main()
