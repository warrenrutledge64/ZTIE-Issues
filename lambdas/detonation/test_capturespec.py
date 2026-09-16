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
        # -ff writes one trace file per PID so a forked/exec'd child's trace is never
        # lost to another process's buffering (live-hardened 2026-09-10).
        self.assertIn("strace -ff", self.joined)
        # file + network + process syscall groups (network capture = INTENT).
        self.assertIn("%file", self.joined)
        self.assertIn("%network", self.joined)
        self.assertIn("%process", self.joined)

    def test_emits_trace_between_markers(self):
        self.assertIn(cs.TRACE_BEGIN_MARKER, self.joined)
        self.assertIn(cs.TRACE_END_MARKER, self.joined)
        # The overall on-host cap is a hard backstop on the emitted output.
        self.assertIn(f"head -c {cs.ON_HOST_TRACE_CAP_BYTES}", self.joined)
        # The per-PID files (strace -ff writes PREFIX.<pid>) are iterated + emitted.
        self.assertIn("ls", self.joined)
        self.assertIn(f"{cs._TRACE_PREFIX}.*", self.joined)

    def test_captures_write_class_syscalls_via_desc_group(self):
        # Story 2.4R fix: %desc traces fd-based syscalls (write/writev/pwrite64), so
        # a planted write buffer is observable. %file alone (filename-arg syscalls)
        # never captures write() and the 2.4R live run missed the buffer entirely.
        self.assertIn("%desc", self.joined)
        self.assertIn("%file", self.joined)

    def test_per_pid_cap_so_no_single_pid_truncates_the_artifact(self):
        # Story 2.4R fix: EACH per-PID trace file is capped independently as it is
        # concatenated, so a noisy sibling PID cannot consume the whole budget and
        # truncate the artifact's own PID trace out. A per-PID head -c must be present
        # in addition to the overall backstop cap.
        self.assertIn(f"head -c {cs.ON_HOST_TRACE_PER_PID_CAP_BYTES}", self.joined)
        self.assertLess(
            cs.ON_HOST_TRACE_PER_PID_CAP_BYTES, cs.ON_HOST_TRACE_CAP_BYTES
        )
        # Sorted NUMERICALLY by the PID suffix (lexical sort would misorder 1000/999).
        self.assertIn("sort -t. -k", self.joined)

    def test_syncs_before_reading_trace(self):
        # strace -ff writes per-PID files; sync flushes them all to disk before the
        # caller cats them (the single-file form sliced a partially-flushed file).
        self.assertIn("sync", self.joined)

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
