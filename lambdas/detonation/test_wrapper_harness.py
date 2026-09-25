"""ZTIE OD-007 — the wrapper-EXECUTION smoke-test suite.

These tests do what the string-assertion tests structurally CANNOT: they EXECUTE the
emitted ``capturespec.build_capture_run_commands`` wrapper end-to-end under ``sh -u`` with
a stubbed ``aws`` on PATH (via :mod:`wrapper_harness`) and assert the upload block actually
FIRES — each per-PID ``s3 cp`` + the ``_UPLOAD_COMPLETE`` sentinel + the stderr reaching the
host diag log — across the case matrix that cost five live cycles to surface one defect
each: instant / hanging-past-timeout / no-shebang / strace-absent / empty-capture, plus the
forced-upload-failure self-diagnosing path.

All stdlib-only + offline (no boto3/moto/pytest). Skipped as a whole only if the host lacks
the real coreutils the emitted wrapper shells out to (GNU ``timeout --kill-after`` + friends);
the golden AMI and this build sandbox both have them.
"""

from __future__ import annotations

import shutil
import subprocess
import unittest

import capturespec as cs
import wrapper_harness as wh


def _host_supports_wrapper() -> bool:
    """The emitted wrapper needs setsid + a GNU timeout with --kill-after (+ coreutils)."""
    if not (shutil.which("setsid") and shutil.which("timeout") and shutil.which("sh")):
        return False
    try:
        out = subprocess.run(
            ["timeout", "--help"], capture_output=True, text=True, timeout=5, check=False
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return "--kill-after" in (out.stdout + out.stderr)


@unittest.skipUnless(
    _host_supports_wrapper(),
    "host lacks setsid / GNU timeout --kill-after (the emitted wrapper's shell tools)",
)
class TestWrapperUploadFires(unittest.TestCase):
    """The core OD-007 invariant: on the instrumented path the upload block FIRES —
    every per-PID trace file is copied to S3 AND the completeness sentinel is written
    LAST — proven by executing the wrapper, not by grepping the command string."""

    def test_instrumented_instant_artifact_uploads_all_per_pid_files_and_sentinel(self):
        # strace present, two per-PID trace files, an instant artifact.
        r = wh.run_wrapper(
            artifact_body="#!/bin/sh\necho INSTANT-OK\n",
            strace_present=True,
            strace_pids=["101", "102"],
        )
        # (1) the wrapper did not crash under set -u and exited cleanly.
        self.assertFalse(r.set_u_crashed, f"set -u crash; stderr={r.stderr!r}")
        self.assertEqual(r.returncode, 0, f"stdout={r.stdout!r} stderr={r.stderr!r}")
        # (2) the upload block actually FIRED an `aws s3 cp` per per-PID file + the sentinel.
        #     (This is the attempt-4 class: the block executed but was inert -> no copies.)
        self.assertGreaterEqual(
            len(r.aws_s3_cp_calls),
            3,
            f"expected >=3 s3 cp calls (2 per-PID + sentinel); got {r.aws_s3_cp_calls!r}",
        )
        # (3) both per-PID objects LANDED in the fake S3 (a fired+successful copy), and
        self.assertEqual(
            sorted(r.per_pid_objects_landed),
            ["behavior.strace.101", "behavior.strace.102"],
            f"landed={r.s3_landed!r}",
        )
        # (4) the completeness sentinel landed LAST (durable "upload finished" signal).
        self.assertTrue(r.sentinel_landed, f"sentinel not landed; landed={r.s3_landed!r}")

    def test_sentinel_is_the_last_s3_write(self):
        # Ordering matters: the sentinel proves every per-PID file was copied, so it must
        # be the FINAL s3 cp. We assert on the recorded invocation ORDER (behavioral).
        r = wh.run_wrapper(
            artifact_body="#!/bin/sh\necho OK\n",
            strace_present=True,
            strace_pids=["777"],
        )
        cp_dests = r.s3_cp_dests  # the s3:// operand of each cp, in call order
        self.assertTrue(cp_dests, f"no s3 cp calls recorded; {r.aws_invocations!r}")
        self.assertIn(
            cs.TRACE_UPLOAD_COMPLETE_SENTINEL,
            cp_dests[-1],
            f"sentinel was not the last s3 cp dest; order={cp_dests!r}",
        )

    def test_no_shebang_artifact_still_runs_instrumented_and_uploads(self):
        # A no-shebang artifact takes the `/bin/sh <artifact>` branch of the wrapper; the
        # upload block must still fire (a shell/host-shape variant that could regress).
        r = wh.run_wrapper(
            artifact_body="echo NO-SHEBANG-OK\n",  # no leading #!
            artifact_name="plain.txt",
            strace_present=True,
            strace_pids=["303"],
        )
        self.assertFalse(r.set_u_crashed, f"stderr={r.stderr!r}")
        self.assertEqual(r.returncode, 0, f"stderr={r.stderr!r}")
        self.assertIn("behavior.strace.303", r.per_pid_objects_landed)
        self.assertTrue(r.sentinel_landed)


@unittest.skipUnless(
    _host_supports_wrapper(),
    "host lacks setsid / GNU timeout --kill-after (the emitted wrapper's shell tools)",
)
class TestWrapperHangingArtifact(unittest.TestCase):
    """Hanging-past-timeout: the artifact blocks (a real malware behavior), the wrapper's
    own ``setsid timeout`` terminates it, and the wrapper SURVIVES to run the upload block
    — the trace still crosses to S3. This is the 2.4S attempt-4/5/6 survival path."""

    def test_hanging_artifact_is_bounded_and_upload_still_fires(self):
        # `read` with no input blocks like a /dev/tcp connect with no egress; the wrapper
        # must kill it at BUDGET and STILL upload the per-PID trace + sentinel.
        r = wh.run_wrapper(
            artifact_body="#!/bin/sh\nread _x\n",  # hangs waiting for stdin that never comes
            strace_present=True,
            strace_pids=["555"],
            ssm_execution_timeout_s=20,  # ceiling; wrapper's own budget is shrunk below it
            timeout_s=60,
        )
        # The wrapper regained control (it was NOT killed by the outer ceiling) and ran the
        # upload block: the trace crossed to S3 despite the artifact hanging.
        self.assertFalse(r.set_u_crashed, f"stderr={r.stderr!r}")
        self.assertIn("behavior.strace.555", r.per_pid_objects_landed)
        self.assertTrue(
            r.sentinel_landed,
            f"upload block did not complete after a bounded hang; landed={r.s3_landed!r}",
        )


@unittest.skipUnless(
    _host_supports_wrapper(),
    "host lacks setsid / GNU timeout --kill-after (the emitted wrapper's shell tools)",
)
class TestWrapperStraceAbsent(unittest.TestCase):
    """strace-absent: the UNINSTRUMENTED branch runs the artifact so the detonation still
    happens, emits the tool-unavailable marker, and (by capturespec's structure) does NOT
    run an upload block — there is no trace to upload. Proven behaviorally."""

    def test_strace_absent_runs_uninstrumented_and_does_not_upload(self):
        r = wh.run_wrapper(
            artifact_body="#!/bin/sh\necho RAN-WITHOUT-CAPTURE\n",
            strace_present=False,
        )
        self.assertFalse(r.set_u_crashed, f"stderr={r.stderr!r}")
        self.assertEqual(r.returncode, 0, f"stderr={r.stderr!r}")
        # tool-unavailable is surfaced (a recorded gap, never silent).
        self.assertIn(cs.TOOL_UNAVAILABLE_MARKER, r.stdout)
        # no upload fired (no trace exists) — the uninstrumented branch has no upload block.
        self.assertEqual(r.aws_s3_cp_calls, [], f"unexpected uploads: {r.aws_s3_cp_calls!r}")
        self.assertFalse(r.sentinel_landed)


@unittest.skipUnless(
    _host_supports_wrapper(),
    "host lacks setsid / GNU timeout --kill-after (the emitted wrapper's shell tools)",
)
class TestWrapperEmptyCapture(unittest.TestCase):
    """empty-capture: strace ran (tool present) but produced NO per-PID file (the 2.4R
    FAIL #2 shape, e.g. a rejected -e expression). The upload block must be a clean no-op
    (no per-PID objects, and — crucially — no CRASH), and the wrapper still exits with the
    artifact's rc. The self-diagnosing no-trace path is exercised too."""

    def test_empty_capture_is_a_clean_noop_upload_not_a_crash(self):
        r = wh.run_wrapper(
            artifact_body="#!/bin/sh\necho OK\n",
            strace_present=True,
            strace_pids=[],  # strace wrote NO per-PID file
            strace_stderr="strace: invalid system call '%desc'\n",
        )
        self.assertFalse(r.set_u_crashed, f"stderr={r.stderr!r}")
        self.assertEqual(r.returncode, 0, f"stderr={r.stderr!r}")
        # No per-PID trace file on the host -> no per-PID object landed in S3.
        self.assertEqual(
            r.per_pid_objects_landed, [], f"unexpected per-PID uploads: {r.s3_landed!r}"
        )
        # The empty-capture upload sub-block ran without erroring the wrapper (attempt-4:
        # an executed-but-inert block). The sentinel line still runs (a `printf | aws s3 cp -`),
        # so the sentinel may land; the invariant under test is NO CRASH + no per-PID objects.


@unittest.skipUnless(
    _host_supports_wrapper(),
    "host lacks setsid / GNU timeout --kill-after (the emitted wrapper's shell tools)",
)
class TestWrapperSelfDiagnosingUpload(unittest.TestCase):
    """The attempt-2 lesson executed: when an ``s3 cp`` FAILS, its stderr must reach the
    host upload diag log (never a silent ``|| true`` swallow). We force the aws stub to
    fail every copy and assert the diag log captured the failure text."""

    def test_failed_upload_is_self_diagnosing_via_the_diag_log(self):
        r = wh.run_wrapper(
            artifact_body="#!/bin/sh\necho OK\n",
            strace_present=True,
            strace_pids=["888"],
            fail_s3_cp=True,
        )
        self.assertFalse(r.set_u_crashed, f"stderr={r.stderr!r}")
        # The wrapper still SURVIVES a failed upload (best-effort || true) and exits cleanly.
        self.assertEqual(r.returncode, 0, f"stderr={r.stderr!r}")
        # But the failure is NOT silent: the stub's stderr reached the host diag log.
        self.assertIn(
            "forced s3 cp failure",
            r.upload_diag_log,
            f"upload stderr was swallowed (attempt-2 regression); diag={r.upload_diag_log!r}",
        )
        # And nothing actually landed in S3 (every copy failed).
        self.assertEqual(r.per_pid_objects_landed, [], f"landed={r.s3_landed!r}")


class TestHarnessSelfChecks(unittest.TestCase):
    """A couple of harness-integrity checks that run even where the wrapper tools are
    absent, so the harness module itself is covered (it is reusable test support)."""

    def test_argv_log_parsing_groups_by_end_sentinel(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            log = os.path.join(d, "argv.log")
            with open(log, "w", encoding="utf-8") as fh:
                fh.write("s3\ncp\n/x\ns3://b/k\n--END--\n")
                fh.write("s3\ncp\n-\ns3://b/_UPLOAD_COMPLETE\n--END--\n")
            got = wh._parse_argv_log(log)
        self.assertEqual(got[0], ["aws", "s3", "cp", "/x", "s3://b/k"])
        self.assertEqual(got[1][-1], "s3://b/_UPLOAD_COMPLETE")

    def test_result_predicates(self):
        res = wh.HarnessResult(
            returncode=0,
            stdout="",
            stderr="",
            aws_invocations=[
                ["aws", "s3", "cp", "/x", "s3://b/traces/i/behavior.strace.1"],
                ["aws", "s3", "cp", "-", "s3://b/traces/i/_UPLOAD_COMPLETE"],
            ],
            s3_landed=["behavior.strace.1", cs.TRACE_UPLOAD_COMPLETE_SENTINEL],
        )
        self.assertEqual(len(res.aws_s3_cp_calls), 2)
        self.assertTrue(res.sentinel_landed)
        self.assertEqual(res.per_pid_objects_landed, ["behavior.strace.1"])
        self.assertFalse(res.set_u_crashed)


if __name__ == "__main__":
    unittest.main()
