"""ZTIE Story 2.5 — contract-conformance for the sanitized-telemetry envelope.

TWO layers (the proven 2.2/2.3/2.4 pattern), so the loop between the schema-first
contract and the code is closed both LIVE and OFFLINE:

  * LIVE (pytest, jsonschema installed): every envelope the detonation lane builds
    from ``sanitize.py`` must validate against ``sanitized-telemetry.contract.v1.json``
    (the exact allow-list the Hub validator enforces). Skips in the INTEGRATIONS_ONLY
    sandbox (PyPI blocked).

  * OFFLINE (always, stdlib only): a MANUAL pure-Python conformance walk asserting the
    built envelopes satisfy the contract's load-bearing invariants (required keys,
    allow-listed enums, byte/array bounds, NO verdict field anywhere, the ordered
    pipeline stages, RELATIVE-clock event offsets, the token budget + truncated flag)
    even without jsonschema.
"""

from __future__ import annotations

import json
import os
import unittest

import sanitize as sz

try:
    from jsonschema import Draft7Validator

    _HAVE_JSONSCHEMA = True
except ImportError:  # offline sandbox
    _HAVE_JSONSCHEMA = False

_SCHEMA_PATH = os.path.join(
    os.path.dirname(__file__), "sanitized-telemetry.contract.v1.json"
)

_VALID_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_VALID_SHA256 = "a" * 64

_TRACE = """
4001  14:03:22.100000 execve("/tmp/ztie/s.sh", ["s.sh"], 0x7ffe /* 20 vars */) = 0
4001  14:03:22.101000 openat(AT_FDCWD, "/etc/ld.so.cache", O_RDONLY) = 3
4001  14:03:22.200000 openat(AT_FDCWD, "/tmp/ztie/loot.txt", O_WRONLY|O_CREAT, 0644) = 5</tmp/ztie/loot.txt>
4001  14:03:22.201000 write(5</tmp/ztie/loot.txt>, "AKIAIOSFODNN7EXAMPLEwJalrXUtnFEMIK7MDENGbPxRfiCY", 47) = 47
4001  14:03:22.250000 connect(6, {sa_family=AF_INET, sin_port=htons(443), sin_addr=inet_addr("93.184.216.34")}, 16) = -1 ENETUNREACH
"""

# Fields that must NEVER appear anywhere in the crossed sanitized view (EVIDENCE,
# not a verdict). Checked recursively by the offline walk.
_BANNED_VERDICT_KEYS = frozenset(
    {"verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean"}
)


def _sanitized_envelope() -> dict:
    result = sz.sanitize_trace(_TRACE, token_budget=25000)
    source = sz.build_source(
        capture_tool=sz.CAPTURE_TOOL_STRACE,
        trace_s3_bucket="ztie-forensic-artifacts",
        trace_s3_key="traces/x/behavior-trace.txt",
        raw_trace_bytes=len(_TRACE.encode("utf-8")),
    )
    return sz.build_sanitized_envelope(
        intake_id=_VALID_INTAKE_ID,
        sha256=_VALID_SHA256,
        sanitized_at="2026-09-10T00:04:31Z",
        sanitized=sz.build_sanitized(
            source=source, pipeline=result["pipeline"], events=result["events"]
        ),
        contract_version="1.0",
    )


def _no_trace_envelope() -> dict:
    result = sz.sanitize_trace(None, token_budget=25000)
    source = sz.build_source(capture_tool=sz.CAPTURE_TOOL_NONE)
    return sz.build_sanitized_envelope(
        intake_id=_VALID_INTAKE_ID,
        sha256=_VALID_SHA256,
        sanitized_at="2026-09-10T00:00:05Z",
        sanitized=sz.build_sanitized(source=source, pipeline=result["pipeline"]),
        contract_version="1.0",
    )


def _truncated_envelope() -> dict:
    result = sz.sanitize_trace(_TRACE, token_budget=10)
    source = sz.build_source(
        capture_tool=sz.CAPTURE_TOOL_STRACE,
        trace_s3_bucket="ztie-forensic-artifacts",
        trace_s3_key="traces/x/behavior-trace.txt",
        raw_trace_bytes=len(_TRACE.encode("utf-8")),
    )
    return sz.build_sanitized_envelope(
        intake_id=_VALID_INTAKE_ID,
        sha256=_VALID_SHA256,
        sanitized_at="2026-09-10T00:04:31Z",
        sanitized=sz.build_sanitized(
            source=source, pipeline=result["pipeline"], events=result["events"]
        ),
        contract_version="1.0",
    )


def _all_sample_envelopes() -> list[dict]:
    return [_sanitized_envelope(), _no_trace_envelope(), _truncated_envelope()]


def _no_banned_keys(obj) -> str | None:
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


class TestOfflineConformanceWalk(unittest.TestCase):
    """Pure-Python manual conformance — runs even without jsonschema."""

    def test_top_level_required_keys(self):
        for env in _all_sample_envelopes():
            for key in ("contract_version", "intake_id", "sha256", "sanitized_at", "sanitized"):
                self.assertIn(key, env)
            self.assertEqual(env["contract_version"], "1.0")
            self.assertEqual(env["intake_id"], _VALID_INTAKE_ID)
            self.assertEqual(env["sha256"], _VALID_SHA256)

    def test_sanitized_required_keys_and_lane(self):
        for env in _all_sample_envelopes():
            s = env["sanitized"]
            self.assertIn("lane", s)
            self.assertIn("pipeline", s)
            self.assertIn("source", s)
            self.assertEqual(s["lane"], "dynamic_detonation")

    def test_pipeline_stage_order_and_enums(self):
        for env in _all_sample_envelopes():
            p = env["sanitized"]["pipeline"]
            self.assertEqual(p["stages"], ["entropy_scrub", "noise_suppress", "truncate"])
            self.assertIn(
                p["status"],
                (sz.STATUS_SANITIZED, sz.STATUS_NO_TRACE, sz.STATUS_ERROR),
            )
            self.assertIsInstance(p["truncated"], bool)
            self.assertLessEqual(p["estimated_tokens"], p["token_budget"])

    def test_source_pointer_references_never_duplicates(self):
        # The source carries a POINTER (bucket/key), never raw trace content.
        s = _sanitized_envelope()["sanitized"]["source"]
        self.assertEqual(s["capture_tool"], "strace")
        self.assertIn("trace_s3_key", s)
        # No field named like a raw payload/body anywhere in source.
        for k in s:
            self.assertNotIn(k, {"body", "content", "raw", "trace", "payload"})

    def test_events_present_only_when_sanitized(self):
        s = _sanitized_envelope()["sanitized"]
        self.assertIn("events", s)
        self.assertTrue(s["events"])
        # A no-trace record records the gap but has no events.
        nt = _no_trace_envelope()["sanitized"]
        self.assertNotIn("events", nt)
        self.assertEqual(nt["pipeline"]["status"], sz.STATUS_NO_TRACE)

    def test_events_bounded(self):
        s = _sanitized_envelope()["sanitized"]
        self.assertLessEqual(len(s["events"]), sz.MAX_EVENTS)
        for e in s["events"]:
            self.assertLessEqual(len(e["summary"]), sz.MAX_EVENT_LEN)
            self.assertLessEqual(len(e["syscall"]), sz.MAX_NAME_LEN)

    def test_relative_clock_offsets_only(self):
        # Event timings are relative monotonic offsets (ms), never a wall clock.
        for e in _sanitized_envelope()["sanitized"]["events"]:
            self.assertIsInstance(e["offset_ms"], int)
            self.assertGreaterEqual(e["offset_ms"], 0)
            self.assertLessEqual(e["offset_ms"], 86400000)

    def test_event_categories_enum(self):
        valid = {"file", "network", "process", "signal", "other"}
        for e in _sanitized_envelope()["sanitized"]["events"]:
            self.assertIn(e["category"], valid)

    def test_truncated_flag_recorded(self):
        p = _truncated_envelope()["sanitized"]["pipeline"]
        self.assertTrue(p["truncated"])
        self.assertLessEqual(p["estimated_tokens"], p["token_budget"])

    def test_no_verdict_field_anywhere(self):
        for env in _all_sample_envelopes():
            offending = _no_banned_keys(env)
            self.assertIsNone(offending, f"verdict-shaped key present: {offending}")

    def test_schema_itself_has_no_verdict_field(self):
        with open(_SCHEMA_PATH, encoding="utf-8") as fh:
            schema = json.load(fh)
        self._assert_no_banned_property(schema)

    def _assert_no_banned_property(self, node):
        if isinstance(node, dict):
            props = node.get("properties")
            if isinstance(props, dict):
                for pk in props:
                    self.assertNotIn(
                        pk, _BANNED_VERDICT_KEYS, f"schema defines a verdict property {pk!r}"
                    )
            for v in node.values():
                self._assert_no_banned_property(v)
        elif isinstance(node, list):
            for v in node:
                self._assert_no_banned_property(v)


@unittest.skipUnless(_HAVE_JSONSCHEMA, "jsonschema not available offline")
class TestLiveContractConformance(unittest.TestCase):
    """Live jsonschema validation against the exact contract the Hub enforces."""

    def setUp(self):
        with open(_SCHEMA_PATH, encoding="utf-8") as fh:
            self.validator = Draft7Validator(json.load(fh))

    def _assert_conforms(self, env):
        errors = sorted(self.validator.iter_errors(env), key=str)
        self.assertEqual(errors, [], f"schema errors: {errors}")

    def test_sanitized_conforms(self):
        self._assert_conforms(_sanitized_envelope())

    def test_no_trace_conforms(self):
        self._assert_conforms(_no_trace_envelope())

    def test_truncated_conforms(self):
        self._assert_conforms(_truncated_envelope())

    def test_rejects_added_unknown_field(self):
        env = _sanitized_envelope()
        env["sanitized"]["verdict"] = "safe"  # additionalProperties:false must reject
        self.assertTrue(list(self.validator.iter_errors(env)))

    def test_rejects_bad_status(self):
        env = _sanitized_envelope()
        env["sanitized"]["pipeline"]["status"] = "approved"
        self.assertTrue(list(self.validator.iter_errors(env)))

    def test_rejects_wall_clock_in_offset(self):
        env = _sanitized_envelope()
        env["sanitized"]["events"][0]["offset_ms"] = "2026-09-10T00:00:00Z"
        self.assertTrue(list(self.validator.iter_errors(env)))

    def test_rejects_bad_event_category(self):
        env = _sanitized_envelope()
        env["sanitized"]["events"][0]["category"] = "malicious"
        self.assertTrue(list(self.validator.iter_errors(env)))


if __name__ == "__main__":
    unittest.main()
