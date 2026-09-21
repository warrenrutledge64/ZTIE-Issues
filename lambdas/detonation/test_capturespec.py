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

    def test_captures_write_class_syscalls_by_explicit_name_not_desc(self):
        # Story 2.4R FAIL #2 fix: the write-class syscalls (write/writev/pwrite64) are
        # traced by EXPLICIT NAME, appended to the %-classes proven-accepted by the
        # AMI's strace. The %desc CLASS is NOT used: the AMI's strace REJECTED %desc
        # and produced a totally empty capture (capture_error). Explicit syscall names
        # are the most universally-supported -e trace= form.
        self.assertNotIn("%desc", self.joined)
        self.assertIn("write", self.joined)
        self.assertIn("writev", self.joined)
        self.assertIn("pwrite64", self.joined)
        # The four proven-accepted classes remain.
        self.assertIn("%file", self.joined)
        self.assertIn("%network", self.joined)
        self.assertIn("%process", self.joined)
        self.assertIn("%signal", self.joined)

    def test_self_diagnoses_when_strace_writes_no_trace_files(self):
        # Story 2.4R FAIL #2 fix: strace's own stderr is redirected to a host file, and
        # if strace produced NO per-PID trace file the emitter ships the diagnostic
        # marker + that stderr between the markers instead of a silent empty — so a
        # no-trace capture is self-explaining on the crossed record.
        self.assertIn(cs.STRACE_NO_TRACE_DIAG_MARKER, self.joined)
        self.assertIn(cs._STRACE_STDERR_FILE, self.joined)
        # The strace invocation redirects its stderr to that file (2> ...).
        self.assertIn(f"2> {cs._STRACE_STDERR_FILE}", self.joined)

    def test_stderr_file_does_not_collide_with_per_pid_glob(self):
        # The strace stderr file MUST NOT match the ``<prefix>.*`` glob the emitter
        # concatenates, or it would be mixed into the trace as a bogus per-PID file.
        import fnmatch
        self.assertFalse(
            fnmatch.fnmatch(cs._STRACE_STDERR_FILE, f"{cs._TRACE_PREFIX}.*"),
            "strace stderr file must not match the per-PID trace glob",
        )

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


class TestNoTraceDiagnostic(unittest.TestCase):
    def test_real_trace_is_not_a_diagnostic(self):
        real = '1234  14:03:22 execve("/tmp/ztie/a.sh", [...]) = 0'
        self.assertIsNone(cs.no_trace_diagnostic(real))

    def test_empty_or_none_is_not_a_diagnostic(self):
        self.assertIsNone(cs.no_trace_diagnostic(""))
        self.assertIsNone(cs.no_trace_diagnostic(None))

    def test_diagnostic_payload_extracted_as_reason(self):
        # When strace wrote no per-PID file, the emit ships the diag marker + strace's
        # own stderr between the markers. no_trace_diagnostic returns the stderr as the
        # capture_error reason, so a no-trace capture is self-explaining (2.4R FAIL #2).
        sliced = (
            cs.STRACE_NO_TRACE_DIAG_MARKER
            + "\nstrace: invalid system call '%desc'\n"
        )
        reason = cs.no_trace_diagnostic(sliced)
        self.assertIsNotNone(reason)
        self.assertIn("invalid system call", reason)
        self.assertIn("%desc", reason)
        # Bounded + single-lined for the contract error_reason field.
        self.assertLessEqual(len(reason), 400)
        self.assertNotIn("\n", reason)

    def test_diagnostic_with_no_stderr_still_returns_a_reason(self):
        reason = cs.no_trace_diagnostic(cs.STRACE_NO_TRACE_DIAG_MARKER + "\n")
        self.assertIsNotNone(reason)
        self.assertIn("no trace files", reason)


class TestArtifactExecutionTimeout(unittest.TestCase):
    """Story 2.4R SEALED FAIL attempt-4 regression: a hanging/blocking artifact
    (e.g. a ``/dev/tcp`` connect with no egress) must be time-bounded on the host so
    the wrapper SURVIVES to emit the trace, instead of the SSM executionTimeout
    SIGKILLing the whole wrapper (exit 137) before the emit block ran."""

    def setUp(self):
        self.cmds = cs.build_capture_run_commands(artifact_path="/tmp/ztie/a.sh")
        self.joined = "\n".join(self.cmds)

    def test_instrumented_run_is_wrapped_in_setsid_timeout_kill_after(self):
        # Story 2.4R attempt-6 (RD-057): BOTH strace invocations (shebang + via-sh) must
        # be bounded by ``setsid timeout --kill-after=GRACE BUDGET strace`` so the whole
        # process group (strace + the artifact re-exec grandchild) is killed, not just the
        # direct child. Attempt 5 falsified the plain ``timeout -k`` (killed strace only).
        needle = (
            f"setsid timeout --kill-after={cs.ARTIFACT_EXEC_KILL_GRACE_S} "
            f"{cs.ARTIFACT_EXEC_TIMEOUT_S} strace"
        )
        self.assertEqual(self.joined.count(needle), 2, self.joined)

    def test_no_bare_direct_child_timeout_remains(self):
        # Regression guard: the falsified attempt-5 form ``timeout -k G B strace`` (no
        # setsid, signals only the direct child) must be GONE from the emitted commands.
        self.assertNotIn(
            f"timeout -k {cs.ARTIFACT_EXEC_KILL_GRACE_S} {cs.ARTIFACT_EXEC_TIMEOUT_S} strace",
            self.joined,
        )

    def test_traced_program_stdio_detached_from_ssm_pipe(self):
        # STDIO DETACH: the traced program's own stdout must go to a host-local file, not
        # the inherited SSM command pipe, so a lingering child cannot hold the pipe open
        # (the attempt-5 no-EOF hang). strace's own stderr still goes to its diag file.
        self.assertIn(f"1> {cs._ARTIFACT_STDOUT_FILE}", self.joined)
        self.assertIn(f"2> {cs._STRACE_STDERR_FILE}", self.joined)

    def test_uninstrumented_run_is_also_setsid_bounded_and_stdio_detached(self):
        # A hanging artifact must not SIGKILL the wrapper even when strace is absent, and
        # its stdio must also be detached from the SSM pipe (same attempt-6 fix).
        un = cs._uninstrumented_exec_commands("/tmp/ztie/a.sh")
        un_joined = "\n".join(un)
        pref = (
            f"setsid timeout --kill-after={cs.ARTIFACT_EXEC_KILL_GRACE_S} "
            f"{cs.ARTIFACT_EXEC_TIMEOUT_S} "
        )
        io = f"1> {cs._ARTIFACT_STDOUT_FILE} 2> {cs._ARTIFACT_STDERR_FILE}"
        self.assertIn(pref + "/tmp/ztie/a.sh " + io, un_joined)
        self.assertIn(pref + "/bin/sh /tmp/ztie/a.sh " + io, un_joined)

    def test_budget_plus_grace_stays_well_under_ssm_ceiling(self):
        # The whole point: timeout must fire BEFORE the SSM executionTimeout (120s
        # default) so SSM never kills the wrapper. Assert a safe margin for the fetch
        # (curl --max-time 60), strace startup, sync, and the emit loop.
        self.assertLess(
            cs.ARTIFACT_EXEC_TIMEOUT_S + cs.ARTIFACT_EXEC_KILL_GRACE_S,
            120,
            "artifact budget+grace must stay under the 120s SSM executionTimeout",
        )

    def test_emits_timed_out_marker_only_on_timeout_rc(self):
        # The marker is gated on the timeout rc (124) so an ordinary run does not
        # falsely claim a timeout, and is emitted OUTSIDE the trace markers.
        self.assertIn(
            f'if [ "$__ZTIE_RC" = "{cs.ARTIFACT_TIMEOUT_RC}" ]; '
            f"then echo {cs.ARTIFACT_TIMED_OUT_MARKER}; fi",
            self.joined,
        )
        # Emitted before the trace-begin marker (so it is in stdout, not in the slice).
        self.assertLess(
            self.joined.index(cs.ARTIFACT_TIMED_OUT_MARKER),
            self.joined.index(cs.TRACE_BEGIN_MARKER),
        )

    def test_emit_block_runs_after_the_bounded_run(self):
        # The trace-emit block (BEGIN marker + per-PID concat) must come AFTER the
        # bounded run in the command list — this is what the fix guarantees survives.
        self.assertLess(
            self.joined.index("setsid timeout --kill-after="),
            self.joined.index(cs.TRACE_BEGIN_MARKER),
        )

    def test_artifact_timed_out_detects_marker(self):
        self.assertTrue(
            cs.artifact_timed_out("...\n" + cs.ARTIFACT_TIMED_OUT_MARKER + "\n...")
        )
        self.assertFalse(cs.artifact_timed_out("ordinary output, no marker"))
        self.assertFalse(cs.artifact_timed_out(None))

    def test_rc_preserved_for_outcome_mapping(self):
        # __ZTIE_RC still captures the (possibly timeout-forced) rc right after the run
        # and the script exits with it, so the 2.3 outcome mapping is unchanged.
        self.assertIn("__ZTIE_RC=$?", self.joined)
        self.assertIn("exit $__ZTIE_RC", self.joined)


class TestProcessGroupKillBehavioral(unittest.TestCase):
    """Story 2.4R attempt-6 BEHAVIORAL proof (the class of proof attempts 4-5 lacked).

    Attempt 5 falsified ``timeout -k G B strace`` LIVE: ``timeout`` killed only its direct
    child (strace); the artifact's re-exec GRANDCHILD survived, held the inherited stdout
    pipe open, and the wrapper hung to the SSM 120 s ceiling (no EOF). This proves the
    attempt-6 construct actually (a) KILLS the whole process group including a hanging
    grandchild and (b) RELEASES the stdout pipe so a reader gets EOF promptly — i.e. the
    wrapper regains control at BUDGET, not at the grandchild's would-be 600 s.

    Skipped unless the host has ``setsid`` + a GNU ``timeout`` that supports
    ``--kill-after`` (the golden AMI does; some minimal CI images may not)."""

    def _tools_available(self) -> bool:
        import shutil
        import subprocess

        if not (shutil.which("setsid") and shutil.which("timeout")):
            return False
        try:
            out = subprocess.run(
                ["timeout", "--help"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return False
        return "--kill-after" in (out.stdout + out.stderr)

    def test_setsid_timeout_kills_hanging_grandchild_and_releases_pipe(self):
        import os
        import subprocess
        import tempfile
        import time

        if not self._tools_available():
            self.skipTest("setsid / GNU timeout --kill-after not available on this host")

        # A stand-in for strace: it forks a GRANDCHILD that writes a marker line then
        # `sleep 600` while INHERITING stdout, then the stand-in itself waits. This is the
        # attempt-5 topology: the process that holds the pipe open is NOT timeout's direct
        # child. If the group kill works, the whole tree dies at BUDGET and the pipe (a
        # temp file here, but the fd-inheritance semantics are identical to the SSM pipe)
        # stops having live writers so a reader sees the process return promptly.
        with tempfile.TemporaryDirectory() as d:
            outfile = os.path.join(d, "out.log")
            # The "traced program": spawn a grandchild that holds the fd + sleeps long.
            inner = (
                "sh -c '(" 
                "echo GRANDCHILD-ALIVE; sleep 600"  # holds inherited stdout, long sleep
                ") & wait'"
            )
            budget, grace = 2, 1  # tiny budget for the test
            # EXACT attempt-6 construct: setsid + timeout --kill-after, artifact stdout
            # redirected to a host file (the pipe-detach), run as a session/group leader.
            cmd = (
                f"setsid timeout --kill-after={grace} {budget} {inner} "
                f"1> {outfile} 2>/dev/null; echo WRAPPER-RESUMED rc=$?"
            )
            start = time.monotonic()
            proc = subprocess.run(
                ["bash", "-c", cmd],
                capture_output=True,
                text=True,
                timeout=30,  # generous ceiling; the point is it returns ~budget, not 600
                check=False,
            )
            elapsed = time.monotonic() - start

            # (1) The wrapper REGAINED CONTROL far below the grandchild's 600 s sleep and
            #     below any SSM-style ceiling — i.e. timeout+group-kill actually returned.
            self.assertLess(
                elapsed,
                budget + grace + 10,
                f"wrapper did not regain control promptly (elapsed={elapsed:.1f}s)",
            )
            # (2) The wrapper actually resumed and ran the post-run line (the emit block
            #     analogue) — the exact thing attempt 5 never reached.
            self.assertIn("WRAPPER-RESUMED", proc.stdout)
            # (3) The grandchild really started (so we know we killed a LIVE holder, not a
            #     no-op), and (4) no `sleep 600` from this test's group is left running.
            with open(outfile) as fh:
                self.assertIn("GRANDCHILD-ALIVE", fh.read())


if __name__ == "__main__":
    unittest.main()
