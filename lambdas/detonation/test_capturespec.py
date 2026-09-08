"""ZTIE Story 2.4 — pure unit tests for the host-native capture command spec.

Offline, stdlib-only (capturespec.py has NO boto3, no AWS). Verifies the fetch +
instrumented-run command list, the strace probe + graceful-degradation branch, the
trace markers, and the trace-slicing that pulls the trace back out of SSM output.
"""

from __future__ import annotations

import unittest

import capturespec as cs


class TestBuildFetchCommands(unittest.TestCase):
    def test_uses_bounded_curl_recipe(self):
        cmds = cs.build_fetch_commands(
            presigned_url="https://s3.us-east-1.amazonaws.com/b/k?sig=x",
            dest_path="/tmp/ztie/a.sh",
        )
        joined = "\n".join(cmds)
        # The proven-live bounded-curl recipe (fails fast instead of hanging to TTL).
        self.assertIn("--connect-timeout 10", joined)
        self.assertIn("--max-time 60", joined)
        self.assertIn("--fail", joined)
        self.assertIn("ZTIE-FETCH-FAILED", joined)

    def test_presigned_url_is_quoted(self):
        # A URL with shell-significant chars must be shell-quoted (no injection).
        cmds = cs.build_fetch_commands(
            presigned_url="https://x/y?a=1&b=2;rm -rf /",
            dest_path="/tmp/ztie/a",
        )
        joined = "\n".join(cmds)
        self.assertIn("'https://x/y?a=1&b=2;rm -rf /'", joined)


class TestBuildCaptureRunCommands(unittest.TestCase):
    def setUp(self):
        self.cmds = cs.build_capture_run_commands(artifact_path="/tmp/ztie/a.sh")
        self.joined = "\n".join(self.cmds)

    def test_probes_for_strace(self):
        self.assertIn("command -v strace", self.joined)

    def test_instrumented_branch_uses_strace_groups(self):
        self.assertIn("strace -f", self.joined)
        # file + network + process syscall groups (network capture = INTENT).
        self.assertIn("%file", self.joined)
        self.assertIn("%network", self.joined)
        self.assertIn("%process", self.joined)

    def test_emits_trace_between_markers(self):
        self.assertIn(cs.TRACE_BEGIN_MARKER, self.joined)
        self.assertIn(cs.TRACE_END_MARKER, self.joined)
        # The emitted trace is capped on-host so the returned output is bounded.
        self.assertIn(f"head -c {cs.ON_HOST_TRACE_CAP_BYTES}", self.joined)

    def test_degrades_gracefully_when_tool_absent(self):
        # The else branch runs the artifact uninstrumented + flags the missing tool.
        self.assertIn(cs.TOOL_UNAVAILABLE_MARKER, self.joined)
        self.assertIn("uninstrumented", self.joined)

    def test_preserves_artifact_exit_code(self):
        # The artifact's own rc must be what SSM sees (2.3 outcome mapping unchanged).
        self.assertIn("exit $__ZTIE_RC", self.joined)

    def test_no_docker(self):
        # Host-native only (RD-001) — never a container.
        self.assertNotIn("docker", self.joined.lower())


class TestArtifactHostPath(unittest.TestCase):
    def test_keeps_basename(self):
        self.assertEqual(cs.artifact_host_path("payload.sh"), "/tmp/ztie/payload.sh")

    def test_strips_dirs(self):
        self.assertEqual(cs.artifact_host_path("a/b/c.sh"), "/tmp/ztie/c.sh")

    def test_empty_falls_back(self):
        self.assertEqual(cs.artifact_host_path(""), "/tmp/ztie/artifact")


class TestSliceTrace(unittest.TestCase):
    def test_slices_between_markers(self):
        out = (
            "noise before\n"
            + cs.TRACE_BEGIN_MARKER
            + "\nLINE1\nLINE2\n"
            + cs.TRACE_END_MARKER
            + "\nnoise after"
        )
        trace, unavailable = cs.slice_trace(out)
        self.assertEqual(trace, "LINE1\nLINE2")
        self.assertFalse(unavailable)

    def test_tool_unavailable_detected(self):
        out = cs.TOOL_UNAVAILABLE_MARKER + "\nran uninstrumented"
        trace, unavailable = cs.slice_trace(out)
        self.assertIsNone(trace)
        self.assertTrue(unavailable)

    def test_missing_end_marker_takes_tail(self):
        out = cs.TRACE_BEGIN_MARKER + "\nPARTIAL TRACE (truncated"
        trace, _unavailable = cs.slice_trace(out)
        self.assertEqual(trace, "PARTIAL TRACE (truncated")

    def test_no_markers_returns_none(self):
        trace, unavailable = cs.slice_trace("just ordinary output")
        self.assertIsNone(trace)
        self.assertFalse(unavailable)

    def test_none_stdout_is_safe(self):
        trace, unavailable = cs.slice_trace(None)
        self.assertIsNone(trace)
        self.assertFalse(unavailable)


if __name__ == "__main__":
    unittest.main()
