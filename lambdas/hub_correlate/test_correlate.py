"""ZTIE Story 3.2 — PURE unit tests for the Nova Pro correlation logic (correlate.py).

Stdlib only; runs offline in the INTEGRATIONS_ONLY sandbox (no boto3, no jsonschema,
no model). Exercises prompt-building (bounded, evidence-only, no verdict ask) and
defensive response-parsing (allow-listed, bounded, honest on malformed input, never
emits a verdict field)."""

from __future__ import annotations

import json
import unittest

import correlate

_BANNED_VERDICT_KEYS = frozenset(
    {"verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean"}
)


def _combined_event(**overrides):
    ce = {
        "inputs_present": ["static", "dynamic", "sanitized"],
        "complete": True,
        "sources": {
            "static": {
                "input": "static",
                "presence": "present",
                "highest_severity": "high",
                "total_findings": 3,
            },
            "dynamic": {"input": "dynamic", "presence": "present", "outcome": "completed"},
            "sanitized": {"input": "sanitized", "presence": "present"},
        },
        "signals": {
            "static_highest_severity": "high",
            "dynamic_outcome": "completed",
            "behavioral_event_count": 2,
            "behavioral_events": [
                {"offset_ms": 12, "category": "process", "syscall": "execve", "summary": "execve(/tmp/x)"},
                {"offset_ms": 48, "category": "network", "syscall": "connect", "summary": "connect(1.2.3.4:443)"},
            ],
        },
    }
    ce.update(overrides)
    return ce


class TestHasSignals(unittest.TestCase):
    def test_full_has_signals(self):
        self.assertTrue(correlate.has_correlatable_signals(_combined_event()))

    def test_empty_no_signals(self):
        ce = {"inputs_present": [], "complete": False, "sources": {}, "signals": {"behavioral_events": []}}
        self.assertFalse(correlate.has_correlatable_signals(ce))

    def test_static_only_has_signals(self):
        ce = {
            "inputs_present": ["static"],
            "complete": False,
            "sources": {"static": {"presence": "present"}},
            "signals": {"static_highest_severity": "low", "behavioral_events": []},
        }
        self.assertTrue(correlate.has_correlatable_signals(ce))

    def test_non_dict_no_signals(self):
        self.assertFalse(correlate.has_correlatable_signals(None))
        self.assertFalse(correlate.has_correlatable_signals("nope"))


class TestPromptBuilding(unittest.TestCase):
    def test_prompt_payload_is_bounded_and_evidence_only(self):
        payload = correlate.build_prompt_payload(_combined_event())
        self.assertEqual(payload["static"]["highest_severity"], "high")
        self.assertEqual(payload["dynamic"]["outcome"], "completed")
        self.assertEqual(len(payload["behavioral_events"]), 2)
        # No verdict-shaped key anywhere in the payload.
        self.assertIsNone(_find_banned(payload))

    def test_prompt_caps_behavioral_events(self):
        events = [
            {"offset_ms": i, "category": "file", "syscall": "openat", "summary": f"openat({i})"}
            for i in range(500)
        ]
        ce = _combined_event(signals={
            "static_highest_severity": "low",
            "dynamic_outcome": "completed",
            "behavioral_event_count": 500,
            "behavioral_events": events,
        })
        payload = correlate.build_prompt_payload(ce)
        self.assertEqual(len(payload["behavioral_events"]), correlate._PROMPT_MAX_EVENTS)
        self.assertTrue(payload["behavioral_events_prompt_capped"])

    def test_system_instruction_forbids_verdict(self):
        text = correlate.SYSTEM_INSTRUCTION.lower()
        self.assertIn("must not render a verdict", text)
        self.assertIn("correlate", text)
        # It must not instruct the model to decide safe/unsafe.
        self.assertIn("do not decide", text)

    def test_invoke_body_shape(self):
        body = correlate.build_invoke_body(_combined_event())
        self.assertEqual(body["schemaVersion"], "messages-v1")
        self.assertEqual(body["inferenceConfig"]["temperature"], 0.0)
        self.assertEqual(body["messages"][0]["role"], "user")
        self.assertIn("COMBINED_EVENT_EVIDENCE", body["messages"][0]["content"][0]["text"])
        # The embedded evidence is valid JSON.
        text = body["messages"][0]["content"][0]["text"]
        evidence = text.split("COMBINED_EVENT_EVIDENCE:\n", 1)[1]
        json.loads(evidence)


class TestExtractText(unittest.TestCase):
    def test_extracts_nova_text(self):
        body = {"output": {"message": {"content": [{"text": "hello"}, {"text": " world"}]}}}
        self.assertEqual(correlate.extract_text(body), "hello world")

    def test_malformed_returns_none(self):
        self.assertIsNone(correlate.extract_text({}))
        self.assertIsNone(correlate.extract_text({"output": {"message": {}}}))
        self.assertIsNone(correlate.extract_text("not a dict"))
        self.assertIsNone(correlate.extract_text({"output": {"message": {"content": [{"x": 1}]}}}))


class TestParseCorrelation(unittest.TestCase):
    def _valid_model_json(self):
        return json.dumps({
            "summary": "The high-severity finding is exercised by an outbound connect.",
            "findings": [
                {"kind": "correlated", "severity": "high", "title": "Exfil path exercised",
                 "detail": "static open-egress finding matches the observed connect",
                 "static_refs": ["SG-open-egress"], "behavioral_refs": ["connect(1.2.3.4:443)"]},
                {"kind": "static_only", "severity": "low", "title": "Unused permissive rule"},
            ],
        })

    def test_parses_valid(self):
        corr, truncated = correlate.parse_correlation(self._valid_model_json())
        self.assertIsNotNone(corr)
        self.assertFalse(truncated)
        self.assertEqual(corr["finding_count"], 2)
        self.assertEqual(corr["highest_correlation_severity"], "high")
        self.assertEqual(corr["findings"][0]["kind"], "correlated")

    def test_tolerates_prose_and_fence(self):
        fenced = "Here is the result:\n```json\n" + self._valid_model_json() + "\n```\nThanks!"
        corr, _ = correlate.parse_correlation(fenced)
        self.assertIsNotNone(corr)
        self.assertEqual(corr["finding_count"], 2)

    def test_tolerates_prose_braces(self):
        wrapped = "Sure! " + self._valid_model_json() + " Done."
        corr, _ = correlate.parse_correlation(wrapped)
        self.assertIsNotNone(corr)

    def test_unparseable_returns_none(self):
        corr, truncated = correlate.parse_correlation("this is not json at all")
        self.assertIsNone(corr)
        self.assertFalse(truncated)

    def test_none_text_returns_none(self):
        corr, _ = correlate.parse_correlation(None)
        self.assertIsNone(corr)

    def test_missing_summary_is_unparseable(self):
        corr, _ = correlate.parse_correlation(json.dumps({"findings": []}))
        self.assertIsNone(corr)

    def test_drops_bad_findings_never_fabricates(self):
        bad = json.dumps({
            "summary": "ok",
            "findings": [
                {"kind": "bogus", "severity": "high", "title": "x"},   # bad kind -> dropped
                {"kind": "correlated", "severity": "nope", "title": "y"},  # bad severity -> unknown
                {"kind": "correlated", "severity": "low"},  # missing title -> dropped
                {"kind": "dynamic_only", "severity": "medium", "title": "kept"},
            ],
        })
        corr, _ = correlate.parse_correlation(bad)
        titles = [f["title"] for f in corr["findings"]]
        self.assertEqual(titles, ["y", "kept"])
        self.assertEqual(corr["findings"][0]["severity"], "unknown")  # coerced

    def test_caps_findings_and_flags_truncated(self):
        many = {"summary": "many", "findings": [
            {"kind": "correlated", "severity": "low", "title": f"f{i}"} for i in range(150)
        ]}
        corr, truncated = correlate.parse_correlation(json.dumps(many))
        self.assertEqual(corr["finding_count"], correlate._MAX_FINDINGS)
        self.assertTrue(truncated)

    def test_clips_oversized_strings(self):
        big = {"summary": "s" * 10000, "findings": [
            {"kind": "correlated", "severity": "low", "title": "t" * 1000, "detail": "d" * 5000}
        ]}
        corr, _ = correlate.parse_correlation(json.dumps(big))
        self.assertLessEqual(len(corr["summary"]), correlate._MAX_SUMMARY)
        self.assertLessEqual(len(corr["findings"][0]["title"]), correlate._MAX_TITLE)
        self.assertLessEqual(len(corr["findings"][0]["detail"]), correlate._MAX_DETAIL)

    def test_drops_injected_verdict_key(self):
        # A model that tries to smuggle a verdict must not get one into the result.
        sneaky = {
            "summary": "ok",
            "verdict": "safe",
            "findings": [
                {"kind": "correlated", "severity": "low", "title": "t", "approved": True}
            ],
        }
        corr, _ = correlate.parse_correlation(json.dumps(sneaky))
        self.assertIsNone(_find_banned(corr), "no verdict-shaped key may survive parse")


class TestBuildResult(unittest.TestCase):
    _ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
    _SHA = "a" * 64

    def test_correlated_carries_correlation(self):
        corr = {"summary": "x", "findings": [], "finding_count": 0}
        result = correlate.build_result(
            intake_id=self._ID, sha256=self._SHA, correlated_at="2026-09-12T00:00:00Z",
            contract_version="1.0", status="correlated", model_id="us.amazon.nova-pro-v1:0",
            attempts=1, latency_ms=850, combined_complete=True, correlation=corr,
        )
        self.assertEqual(result["status"], "correlated")
        self.assertIn("correlation", result)
        self.assertEqual(result["attempts"], 1)
        self.assertIsNone(_find_banned(result))

    def test_model_error_omits_correlation(self):
        result = correlate.build_result(
            intake_id=self._ID, sha256=self._SHA, correlated_at="2026-09-12T00:00:00Z",
            contract_version="1.0", status="model_error", model_id="us.amazon.nova-pro-v1:0",
            attempts=5, status_detail="ThrottlingException after 5 attempt(s)", correlation=None,
        )
        self.assertEqual(result["status"], "model_error")
        self.assertNotIn("correlation", result)
        self.assertEqual(result["attempts"], 5)

    def test_unparseable_omits_correlation_even_if_passed(self):
        # Guard: build_result only attaches correlation when status == correlated.
        result = correlate.build_result(
            intake_id=self._ID, sha256=self._SHA, correlated_at="2026-09-12T00:00:00Z",
            contract_version="1.0", status="unparseable", correlation={"summary": "x", "findings": []},
        )
        self.assertNotIn("correlation", result)


def _find_banned(obj, path="<root>"):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in _BANNED_VERDICT_KEYS:
                return f"{path}.{k}"
            deeper = _find_banned(v, f"{path}.{k}")
            if deeper:
                return deeper
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            deeper = _find_banned(v, f"{path}[{i}]")
            if deeper:
                return deeper
    return None


if __name__ == "__main__":
    unittest.main()
