"""ZTIE Story 2.4 — contract-conformance for the behavioral-telemetry envelope.

TWO layers (the proven 2.2/2.3 pattern), so the loop between the schema-first
contract and the code is closed both LIVE and OFFLINE:

  * LIVE (pytest, jsonschema installed): every envelope ``behavior.py`` builds must
    validate against ``behavior.contract.v1.json`` (the exact allow-list the Hub
    validator enforces). Skips in the INTEGRATIONS_ONLY sandbox (PyPI blocked).

  * OFFLINE (always, stdlib only): a MANUAL pure-Python conformance walk asserting
    the built envelopes satisfy the contract's load-bearing invariants (required
    keys, allow-listed enums, byte/array bounds, NO verdict field, the always-true
    host-native/no-Docker facts, RELATIVE-clock offsets) even without jsonschema.
"""

from __future__ import annotations

import json
import os
import unittest

import behavior as bh

try:
    from jsonschema import Draft7Validator

    _HAVE_JSONSCHEMA = True
except ImportError:  # offline sandbox
    _HAVE_JSONSCHEMA = False

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "behavior.contract.v1.json")

_VALID_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_VALID_SHA256 = "a" * 64

_TRACE = """
1  00:00:00.100000 openat(AT_FDCWD, "/etc/passwd", O_RDONLY) = 3</etc/passwd>
1  00:00:00.200000 connect(4, {sa_family=AF_INET, sin_port=htons(443), sin_addr=inet_addr("93.184.216.34")}, 16) = -1 ENETUNREACH
"""

# Fields that must NEVER appear anywhere in crossed telemetry (EVIDENCE, not a
# verdict). Checked recursively by the offline walk.
_BANNED_VERDICT_KEYS = frozenset(
    {"verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean"}
)


def _captured_envelope() -> dict:
    cap = bh.build_capture(
        capture_tool=bh.CAPTURE_TOOL_STRACE,
        capture_status=bh.CAPTURE_STATUS_CAPTURED,
        capture_started_offset_ms=1200,
        capture_stopped_offset_ms=63000,
        trace_truncated=False,
        trace_s3_bucket="ztie-forensic-artifacts",
        trace_s3_key="traces/x/behavior-trace.txt",
    )
    return bh.build_behavior_envelope(
        intake_id=_VALID_INTAKE_ID,
        sha256=_VALID_SHA256,
        captured_at="2026-09-08T00:04:31Z",
        behavior=bh.build_behavior(capture=cap, summaries=bh.summarize_trace(_TRACE)),
        contract_version="1.0",
    )


def _tool_unavailable_envelope() -> dict:
    cap = bh.build_capture(
        capture_tool=bh.CAPTURE_TOOL_NONE,
        capture_status=bh.CAPTURE_STATUS_TOOL_UNAVAILABLE,
        capture_started_offset_ms=1000,
        capture_stopped_offset_ms=40000,
        error_reason="strace not present on host; run was uninstrumented",
    )
    return bh.build_behavior_envelope(
        intake_id=_VALID_INTAKE_ID,
        sha256=_VALID_SHA256,
        captured_at="2026-09-08T00:00:40Z",
        behavior=bh.build_behavior(capture=cap),
        contract_version="1.0",
    )


def _not_run_envelope() -> dict:
    cap = bh.build_capture(
        capture_tool=bh.CAPTURE_TOOL_NONE,
        capture_status=bh.CAPTURE_STATUS_NOT_RUN,
        error_reason="detonation never executed host-native; no capture",
    )
    return bh.build_behavior_envelope(
        intake_id=_VALID_INTAKE_ID,
        sha256=_VALID_SHA256,
        captured_at="2026-09-08T00:00:05Z",
        behavior=bh.build_behavior(capture=cap),
        contract_version="1.0",
    )


def _all_sample_envelopes() -> list[dict]:
    return [_captured_envelope(), _tool_unavailable_envelope(), _not_run_envelope()]


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
            for key in ("contract_version", "intake_id", "sha256", "captured_at", "behavior"):
                self.assertIn(key, env)
            self.assertEqual(env["contract_version"], "1.0")
            self.assertEqual(env["intake_id"], _VALID_INTAKE_ID)
            self.assertEqual(env["sha256"], _VALID_SHA256)

    def test_behavior_required_keys_and_lane(self):
        for env in _all_sample_envelopes():
            beh = env["behavior"]
            self.assertIn("lane", beh)
            self.assertIn("capture", beh)
            self.assertEqual(beh["lane"], "dynamic_detonation")

    def test_capture_facts_constants_and_enums(self):
        for env in _all_sample_envelopes():
            cap = env["behavior"]["capture"]
            self.assertTrue(cap["host_native"])   # RD-001, always host-native
            self.assertTrue(cap["no_docker"])     # RD-001, never a container
            self.assertIn(cap["capture_tool"], bh.CAPTURE_TOOLS)
            self.assertIn(cap["capture_status"], bh.CAPTURE_STATUSES)

    def test_relative_clock_offsets_only(self):
        # Behavioral timings are relative monotonic offsets (ms), never a wall clock.
        for env in _all_sample_envelopes():
            cap = env["behavior"]["capture"]
            for k in ("capture_started_offset_ms", "capture_stopped_offset_ms"):
                if k in cap:
                    self.assertIsInstance(cap[k], int)
                    self.assertGreaterEqual(cap[k], 0)
                    self.assertLessEqual(cap[k], 86400000)

    def test_summaries_present_only_when_captured(self):
        captured = _captured_envelope()["behavior"]
        self.assertIn("syscalls", captured)
        self.assertIn("network", captured)
        self.assertIn("filesystem", captured)
        # A tool-unavailable / not-run record records the gap but has no summaries.
        for env in (_tool_unavailable_envelope(), _not_run_envelope()):
            beh = env["behavior"]
            self.assertNotIn("syscalls", beh)
            self.assertNotIn("network", beh)
            self.assertNotIn("filesystem", beh)

    def test_sample_arrays_bounded(self):
        beh = _captured_envelope()["behavior"]
        self.assertLessEqual(len(beh["syscalls"].get("top", [])), bh.MAX_SAMPLE_ITEMS)
        self.assertLessEqual(len(beh["network"].get("destinations", [])), bh.MAX_SAMPLE_ITEMS)
        self.assertLessEqual(len(beh["filesystem"].get("paths", [])), bh.MAX_SAMPLE_ITEMS)

    def test_name_lengths_bounded(self):
        beh = _captured_envelope()["behavior"]
        for row in beh["syscalls"].get("top", []):
            self.assertLessEqual(len(row["name"]), bh.MAX_NAME_LEN)
        for d in beh["network"].get("destinations", []):
            self.assertLessEqual(len(d["destination"]), bh.MAX_NAME_LEN)
        for p in beh["filesystem"].get("paths", []):
            self.assertLessEqual(len(p["path"]), bh.MAX_NAME_LEN)

    def test_network_records_intent(self):
        net = _captured_envelope()["behavior"]["network"]
        self.assertGreaterEqual(net["connect_attempts"], 1)
        for d in net.get("destinations", []):
            # In the isolated VPC, attempts fail — the attempt is the signal.
            self.assertIn("connected", d)

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

    def test_captured_conforms(self):
        self._assert_conforms(_captured_envelope())

    def test_tool_unavailable_conforms(self):
        self._assert_conforms(_tool_unavailable_envelope())

    def test_not_run_conforms(self):
        self._assert_conforms(_not_run_envelope())

    def test_rejects_added_unknown_field(self):
        env = _captured_envelope()
        env["behavior"]["verdict"] = "safe"  # additionalProperties:false must reject
        self.assertTrue(list(self.validator.iter_errors(env)))

    def test_rejects_bad_capture_status(self):
        env = _captured_envelope()
        env["behavior"]["capture"]["capture_status"] = "approved"
        self.assertTrue(list(self.validator.iter_errors(env)))

    def test_rejects_wall_clock_in_offset(self):
        env = _captured_envelope()
        env["behavior"]["capture"]["capture_started_offset_ms"] = "2026-09-08T00:00:00Z"
        self.assertTrue(list(self.validator.iter_errors(env)))


if __name__ == "__main__":
    unittest.main()
