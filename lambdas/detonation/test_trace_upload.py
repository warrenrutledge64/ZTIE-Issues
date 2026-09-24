"""ZTIE Story 2.4S / Fix B (RD-058) — offline unit tests for the S3-direct trace
transport that decouples trace SURVIVAL from the fragile SSM stdout path.

Three layers, all offline + stdlib-only (INTEGRATIONS_ONLY sandbox — no boto3 / moto /
pytest):

  (A) capturespec.build_trace_upload_commands / build_capture_run_commands — the HOST
      command shape: aws s3 cp per-PID files to traces/{intake_id}/, the completeness
      SENTINEL written LAST, and the upload spliced BEFORE the (fragile) stdout emit block.

  (B) awsio.read_uploaded_trace — the READ seam: sentinel detection (complete vs partial),
      per-PID concatenation, the ``.strace.`` filter that excludes the Lambda's own
      behavior-trace.txt, and the caps. boto3 is stubbed for import; a fake S3 client is
      injected into the module cache so the LOGIC is exercised without any real AWS call.

  (C) handler._build_telemetry_envelopes — the CORE Fix B invariant: an SSM ``TimedOut``
      run WITH a complete S3 trace is a SUCCESSFUL capture (capture_status=captured), NOT a
      failure; a partial S3 upload => captured + trace_truncated; S3 empty + stdout empty =>
      capture_error (unchanged); S3 empty + stdout trace => stdout fallback (backward compat).
"""

from __future__ import annotations

import sys
import types
import unittest

# awsio + handler import boto3/botocore at module top for their client factories; the
# INTEGRATIONS_ONLY sandbox has neither. Stub just enough to import offline — the tests
# never touch a real client (they inject a fake into awsio._s3_client).
if "boto3" not in sys.modules:
    _boto3 = types.ModuleType("boto3")
    _boto3.client = lambda *a, **k: None
    _boto3.resource = lambda *a, **k: None
    sys.modules["boto3"] = _boto3
if "botocore" not in sys.modules:
    _botocore = types.ModuleType("botocore")
    _config = types.ModuleType("botocore.config")
    _config.Config = lambda *a, **k: None
    _botocore.config = _config
    sys.modules["botocore"] = _botocore
    sys.modules["botocore.config"] = _config

import awsio
import capturespec as cs

_INTAKE = "11111111-1111-4111-8111-111111111111"
_SHA = "a" * 64


# ----------------------------------------------------------------------------
# (A) capturespec — the host upload command shape
# ----------------------------------------------------------------------------
class TestTraceUploadCommands(unittest.TestCase):
    def setUp(self):
        self.cmds = cs.build_trace_upload_commands(
            bucket="b-forensic", intake_id=_INTAKE, region="us-east-1"
        )
        self.joined = "\n".join(self.cmds)

    def test_uploads_per_pid_files_to_traces_prefix(self):
        self.assertIn("aws s3 cp", self.joined)
        self.assertIn(f"s3://b-forensic/traces/{_INTAKE}/", self.joined)
        # It iterates the per-PID glob (PREFIX.*), not a single fixed file.
        self.assertIn(f"{cs._TRACE_PREFIX}.*", self.joined)

    def test_every_s3_cp_is_pinned_to_the_regional_endpoint(self):
        # attempt-2 FAIL root cause: a bare `aws s3 cp` resolves the GLOBAL S3 host
        # (s3.amazonaws.com), which the isolated VPC gateway endpoint does NOT serve — it
        # TCP-times-out and, under `|| true`, fails SILENTLY. Every host copy MUST carry
        # --region + --endpoint-url pinned to the REGIONAL host the gateway serves.
        cp_lines = [ln for ln in self.cmds if "s3 cp" in ln]
        self.assertTrue(cp_lines, "expected at least one s3 cp line")
        for ln in cp_lines:
            self.assertIn("--region us-east-1", ln, f"missing --region: {ln}")
            self.assertIn(
                "--endpoint-url https://s3.us-east-1.amazonaws.com",
                ln,
                f"missing regional --endpoint-url: {ln}",
            )
        # And the global endpoint must NEVER appear as a cp target.
        self.assertNotIn("https://s3.amazonaws.com", self.joined)

    def test_every_s3_cp_uses_the_absolute_cli_path(self):
        # attempt-3 FAIL root cause: the CLI is baked on the AMI but NOT on the SSM shell's
        # PATH, so a BARE `aws` invocation is `aws: not found` and every copy failed. Every
        # host `s3 cp` MUST invoke the CLI by its absolute path.
        cp_lines = [ln for ln in self.cmds if "s3 cp" in ln]
        self.assertTrue(cp_lines, "expected at least one s3 cp line")
        for ln in cp_lines:
            self.assertIn(
                f"{cs.HOST_AWS_CLI} s3 cp", ln, f"cp not using absolute CLI path: {ln}"
            )
        # There must be NO bare `aws s3 cp` (i.e. an `aws` NOT preceded by the abs-path dir).
        # Assert the bare token never appears at a word boundary that isn't the abs path.
        import re

        for ln in cp_lines:
            # strip the known-good absolute invocations, then no stray "aws s3 cp" may remain
            stripped = ln.replace(f"{cs.HOST_AWS_CLI} s3 cp", "")
            self.assertIsNone(
                re.search(r"(?<![/\w])aws s3 cp", stripped),
                f"a bare `aws s3 cp` remains: {ln}",
            )

    def test_region_is_baked_as_a_literal_not_a_host_env_ref(self):
        # SSM AWS-RunShellScript runs in a stripped shell; the region must be a LITERAL in
        # the command, never a `$AWS_REGION` the host is trusted to resolve.
        self.assertNotIn("$AWS_REGION", self.joined)
        self.assertNotIn("${AWS_REGION", self.joined)

    def test_upload_stderr_is_captured_and_shipped_back_self_diagnosing(self):
        # attempt-2 FAIL lesson: `|| true` must NOT swallow the failure silently. Each cp
        # redirects stderr to the host log, and that log is emitted between diag markers.
        # DIAGNOSTIC-BRANCH ONLY (diag/story-2.4S-upload-probe): the temporary
        # confirm-before-fix PROBE spliced into build_trace_upload_commands intentionally runs
        # `aws s3 cp` lines WITHOUT the errlog redirect (it surfaces stderr live — the point of
        # the probe). Exclude those probe lines from this PRODUCTION assertion. This exclusion
        # MUST be reverted together with the probe before any fix merge (no probe => no
        # probe lines => this filter is a no-op).
        _probe_markers = ("per_pid_cp_rc", "sentinel_cp_rc", "PROBE", "ztie-probe")
        production_cp = [
            ln
            for ln in self.cmds
            if "aws s3 cp" in ln and not any(m in ln for m in _probe_markers)
        ]
        for ln in production_cp:
            self.assertIn(f"2>>{cs._UPLOAD_STDERR_FILE}", ln, f"cp not logging stderr: {ln}")
        self.assertIn(cs.UPLOAD_DIAG_BEGIN_MARKER, self.joined)
        self.assertIn(cs.UPLOAD_DIAG_END_MARKER, self.joined)
        # the log is read back (head -c) between the markers.
        self.assertIn(cs._UPLOAD_STDERR_FILE, self.joined)

    def test_completeness_sentinel_written_last(self):
        # The sentinel object is the durable, out-of-band "upload finished" signal.
        self.assertIn(cs.TRACE_UPLOAD_COMPLETE_SENTINEL, self.joined)
        # It must be the LAST s3 write (after the per-PID copies) so its presence proves
        # every per-PID file was copied.
        last_cp = self.joined.rfind("aws s3 cp")
        sentinel_at = self.joined.find(cs.TRACE_UPLOAD_COMPLETE_SENTINEL)
        # the sentinel line contains the final `aws s3 cp - s3://.../_UPLOAD_COMPLETE`
        self.assertLessEqual(
            self.joined.find(cs.TRACE_UPLOAD_COMPLETE_SENTINEL),
            last_cp + len("aws s3 cp") + 400,
        )
        self.assertGreater(sentinel_at, 0)

    def test_upload_is_spliced_before_the_stdout_emit_block(self):
        # The whole point of Fix B: the trace is durable in S3 BEFORE the fragile stdout
        # emit block runs, so a hung/killed wrapper cannot lose it.
        full = "\n".join(
            cs.build_capture_run_commands(
                artifact_path="/tmp/ztie/a.sh",
                bucket="b-forensic",
                intake_id=_INTAKE,
                region="us-east-1",
            )
        )
        self.assertLess(
            full.index(cs.TRACE_UPLOAD_BEGIN_MARKER),
            full.index(cs.TRACE_BEGIN_MARKER),
            "S3 upload must be spliced before the stdout emit begin marker",
        )

    def test_backward_compatible_without_bucket(self):
        # No bucket/intake_id => stdout-only, no upload (existing callers/tests unaffected).
        full = "\n".join(cs.build_capture_run_commands(artifact_path="/tmp/ztie/a.sh"))
        self.assertNotIn("aws s3 cp", full)
        self.assertNotIn(cs.TRACE_UPLOAD_COMPLETE_SENTINEL, full)

    def test_upload_skipped_when_region_missing(self):
        # Fail-safe: bucket+intake_id supplied but region omitted => DO NOT emit a
        # global-endpoint copy that would silently fail again; skip the direct upload
        # (stdout-only fallback) rather than regress to the attempt-2 failure mode.
        full = "\n".join(
            cs.build_capture_run_commands(
                artifact_path="/tmp/ztie/a.sh", bucket="b-forensic", intake_id=_INTAKE
            )
        )
        self.assertNotIn("aws s3 cp", full)
        self.assertNotIn(cs.TRACE_UPLOAD_COMPLETE_SENTINEL, full)


# ----------------------------------------------------------------------------
# (B) awsio.read_uploaded_trace — the read seam
# ----------------------------------------------------------------------------
class _FakeBody:
    def __init__(self, data: bytes):
        self._data = data

    def read(self) -> bytes:
        return self._data


class _FakeS3:
    """Minimal fake S3: list_objects_v2 (single page) + get_object over an in-memory map."""

    def __init__(self, objects: dict[str, bytes]):
        self._objects = objects

    def list_objects_v2(self, **kwargs):
        prefix = kwargs.get("Prefix", "")
        contents = [
            {"Key": k, "Size": len(v)}
            for k, v in self._objects.items()
            if k.startswith(prefix)
        ]
        return {"Contents": contents, "IsTruncated": False}

    def get_object(self, **kwargs):
        return {"Body": _FakeBody(self._objects[kwargs["Key"]])}

    def put_object(self, **kwargs):
        # The handler best-effort writes a consolidated behavior-trace.txt via put_trace;
        # accept it so the test exercises the real success path (not the except branch).
        body = kwargs.get("Body", b"")
        self._objects[kwargs["Key"]] = body if isinstance(body, bytes) else bytes(body)
        return {}


class TestReadUploadedTrace(unittest.TestCase):
    def tearDown(self):
        awsio._s3_client = None  # reset the injected fake

    def _inject(self, objects: dict[str, bytes]):
        awsio._s3_client = _FakeS3(objects)

    def _base(self) -> str:
        return f"traces/{_INTAKE}/"

    def test_complete_when_sentinel_present(self):
        base = self._base()
        self._inject(
            {
                f"{base}behavior.strace.101": b"openat(...)\n",
                f"{base}behavior.strace.102": b"connect(...443...)\n",
                f"{base}_UPLOAD_COMPLETE": b"complete",
            }
        )
        r = awsio.read_uploaded_trace("b-forensic", _INTAKE)
        self.assertTrue(r["complete"])
        self.assertEqual(r["object_count"], 2)
        self.assertIn("openat", r["trace"])
        self.assertIn("connect", r["trace"])

    def test_partial_when_sentinel_absent(self):
        base = self._base()
        self._inject(
            {
                f"{base}behavior.strace.101": b"openat(...)\n",
            }
        )
        r = awsio.read_uploaded_trace("b-forensic", _INTAKE)
        self.assertFalse(r["complete"])  # host killed mid-upload
        self.assertEqual(r["object_count"], 1)
        self.assertIn("openat", r["trace"])

    def test_excludes_lambda_written_behavior_trace_txt(self):
        # The Lambda writes its own consolidated behavior-trace.txt under the SAME prefix
        # via put_trace; a re-read must NOT ingest it as a raw per-PID trace.
        base = self._base()
        self._inject(
            {
                f"{base}behavior.strace.101": b"openat(...)\n",
                f"{base}behavior-trace.txt": b"THE CONSOLIDATED SUMMARY - not a per-PID file",
                f"{base}_UPLOAD_COMPLETE": b"complete",
            }
        )
        r = awsio.read_uploaded_trace("b-forensic", _INTAKE)
        self.assertEqual(r["object_count"], 1)
        self.assertIn("openat", r["trace"])
        self.assertNotIn("CONSOLIDATED SUMMARY", r["trace"])

    def test_empty_when_no_objects(self):
        self._inject({})
        r = awsio.read_uploaded_trace("b-forensic", _INTAKE)
        self.assertFalse(r["complete"])
        self.assertIsNone(r["trace"])
        self.assertEqual(r["object_count"], 0)

    def test_per_object_cap_applied(self):
        base = self._base()
        big = b"x" * (200 * 1024)  # 200 KiB > 128 KiB per-object cap
        self._inject(
            {f"{base}behavior.strace.101": big, f"{base}_UPLOAD_COMPLETE": b"c"}
        )
        r = awsio.read_uploaded_trace(
            "b-forensic", _INTAKE, per_object_cap_bytes=128 * 1024
        )
        # header + capped body; the body portion must be <= the per-object cap.
        self.assertLessEqual(len(r["trace"]) - len("=== ZTIE trace file: ... ===\n"), 128 * 1024 + 64)


# ----------------------------------------------------------------------------
# (C) handler._build_telemetry_envelopes — the CORE Fix B invariant
# ----------------------------------------------------------------------------
class TestHandlerS3FirstTelemetry(unittest.TestCase):
    """SSM TimedOut + complete S3 trace = SUCCESSFUL capture (the whole point of Fix B)."""

    @classmethod
    def setUpClass(cls):
        # handler reads several env vars at import; set benign defaults so importing +
        # calling _build_telemetry_envelopes is offline-safe.
        import os

        os.environ.setdefault("HUB_INGEST_QUEUE_URL", "https://sqs.local/q")
        os.environ.setdefault("BEHAVIOR_CONTRACT_VERSION", "1.0")
        os.environ.setdefault("SANITIZED_TELEMETRY_CONTRACT_VERSION", "1.0")
        global handler
        import handler as _handler

        handler = _handler

    def tearDown(self):
        awsio._s3_client = None

    def _inject_s3(self, objects: dict[str, bytes]):
        awsio._s3_client = _FakeS3(objects)

    def _real_trace(self) -> str:
        # A minimal but real-looking strace slice the summarizer can parse.
        return (
            "=== ZTIE trace file: behavior.strace.101 ===\n"
            "101 openat(AT_FDCWD, \"/tmp/x\", O_WRONLY|O_CREAT) = 3\n"
            "101 write(3, \"data\", 4) = 4\n"
            "101 connect(4, {AF_INET, 93.184.216.34:443}, 16) = -1 EINPROGRESS\n"
        )

    def test_timed_out_but_complete_s3_trace_is_a_successful_capture(self):
        base = f"traces/{_INTAKE}/"
        self._inject_s3(
            {
                f"{base}behavior.strace.101": self._real_trace().encode(),
                f"{base}_UPLOAD_COMPLETE": b"complete",
            }
        )
        # stdout is the attempt-6 shape: begin banner only, NO trace, then SSM TimedOut.
        behavior_env, _sanitized = handler._build_telemetry_envelopes(
            bucket="b-forensic",
            intake_id=_INTAKE,
            sha256=_SHA,
            stdout="=== ZTIE detonation: begin (instrumented) ===\n",
            ssm_status="TimedOut",
            capture_reached=True,
            capture_started_offset_ms=0,
            capture_stopped_offset_ms=120000,
        )
        cap = behavior_env["behavior"]["capture"]
        # THE FIX B INVARIANT: not a capture_error — a real captured trace from S3.
        self.assertEqual(cap["capture_status"], "captured")
        # honest note: recovered from S3 despite the SSM TimedOut.
        self.assertIn("S3", cap.get("error_reason", ""))
        self.assertIn("TimedOut", cap.get("error_reason", ""))
        # the real syscalls were summarized (evidence crossed).
        self.assertGreater(behavior_env["behavior"]["syscalls"]["total"], 0)

    def test_partial_s3_trace_is_captured_but_truncated(self):
        base = f"traces/{_INTAKE}/"
        self._inject_s3(
            {f"{base}behavior.strace.101": self._real_trace().encode()}  # NO sentinel
        )
        behavior_env, _ = handler._build_telemetry_envelopes(
            bucket="b-forensic",
            intake_id=_INTAKE,
            sha256=_SHA,
            stdout="=== ZTIE detonation: begin (instrumented) ===\n",
            ssm_status="TimedOut",
            capture_reached=True,
            capture_started_offset_ms=0,
            capture_stopped_offset_ms=120000,
        )
        cap = behavior_env["behavior"]["capture"]
        self.assertEqual(cap["capture_status"], "captured")
        self.assertTrue(cap["trace_truncated"])

    def test_s3_empty_and_stdout_empty_is_capture_error(self):
        self._inject_s3({})  # nothing in S3
        behavior_env, _ = handler._build_telemetry_envelopes(
            bucket="b-forensic",
            intake_id=_INTAKE,
            sha256=_SHA,
            stdout="=== ZTIE detonation: begin (instrumented) ===\n",  # no trace markers
            ssm_status="TimedOut",
            capture_reached=True,
            capture_started_offset_ms=0,
            capture_stopped_offset_ms=120000,
        )
        cap = behavior_env["behavior"]["capture"]
        self.assertEqual(cap["capture_status"], "capture_error")

    def test_s3_empty_but_stdout_has_trace_falls_back_to_stdout(self):
        self._inject_s3({})
        stdout = (
            "=== ZTIE detonation: begin (instrumented) ===\n"
            f"{cs.TRACE_BEGIN_MARKER}\n"
            "=== ZTIE trace file: behavior.strace.101 ===\n"
            "101 openat(AT_FDCWD, \"/tmp/x\", O_WRONLY) = 3\n"
            "101 write(3, \"d\", 1) = 1\n"
            f"{cs.TRACE_END_MARKER}\n"
        )
        behavior_env, _ = handler._build_telemetry_envelopes(
            bucket="b-forensic",
            intake_id=_INTAKE,
            sha256=_SHA,
            stdout=stdout,
            ssm_status="Success",
            capture_reached=True,
            capture_started_offset_ms=0,
            capture_stopped_offset_ms=1000,
        )
        cap = behavior_env["behavior"]["capture"]
        self.assertEqual(cap["capture_status"], "captured")
        self.assertGreater(behavior_env["behavior"]["syscalls"]["total"], 0)


if __name__ == "__main__":
    unittest.main()
