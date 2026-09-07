"""ZTIE Story 2.6 — END-TO-END branch-output CONTRACT test (review v1, issue 3).

The offline ``test_collect.py`` suite feeds the join hand-built summary/run dicts,
so it CANNOT catch a mismatch between what the lane handlers ACTUALLY return on a
Step Functions direct invoke and what the collector rolls up. That gap is exactly
what let the original invoke-shape defect through: the lane handlers only consumed
the SQS ``Records`` batch shape and returned ``{"batchItemFailures": []}`` when the
fork invoked them with a bare job dict — so the lanes did no work yet the join read
them as ``completed`` and reported ``both_complete: true``.

This suite closes that gap. It drives EACH real lane handler (static + detonation)
with the fork's job payload shape (the ``static_job`` / ``detonation_job`` the
preprocessor builds), then feeds the handler's ACTUAL return into ``collect.join``
and asserts:

  * the direct-invoke return is the lane's real summary/run envelope (NOT a
    batch-failure object), and the collector rolls it up to ``completed`` with the
    real roll-up fields; and
  * the OLD no-op shape (``{"batchItemFailures": []}``) — a lane that ran nothing —
    is now recorded as ``errored`` by the join, never silently ``completed`` and so
    can NEVER drive ``both_complete: true``.

Stdlib-only. The AWS seam (``awsio``) is stubbed into ``sys.modules`` per lane so
the handlers import + run offline (boto3 is not installable in the sandbox); the
real envelope BUILDERS (``normalize.build_summary`` / ``outcome.build_run_envelope``)
run for real so the produced shapes are the genuine contract shapes.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import types
import unittest

import collect

_REPO_LAMBDAS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_STATIC_DIR = os.path.join(_REPO_LAMBDAS, "static_scan")
_DETONATION_DIR = os.path.join(_REPO_LAMBDAS, "detonation")

_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_SHA256 = "a" * 64
_CV = "1.0"

_BANNED_VERDICT_KEYS = frozenset(
    {"verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean"}
)


def _no_banned_keys(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in _BANNED_VERDICT_KEYS:
                return f"{path}.{k}" if path else k
            deeper = _no_banned_keys(v, f"{path}.{k}" if path else k)
            if deeper:
                return deeper
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            deeper = _no_banned_keys(v, f"{path}[{i}]")
            if deeper:
                return deeper
    return None


def _load_lane_handler(lane_dir: str, alias: str, awsio_stub: types.ModuleType):
    """Import a lane's ``handler.py`` in ISOLATION under a unique module ``alias``.

    Both lanes ship a module literally named ``handler`` (and their own ``awsio`` /
    ``normalize`` / ``outcome``), so we cannot just ``import handler`` for both in
    one process. We put the lane dir first on ``sys.path``, inject the lane-specific
    stub for ``awsio`` (so boto3 is never imported), import the handler under a
    unique name, then restore ``sys.path`` and the sibling module names so the next
    lane loads its OWN copies cleanly.
    """
    # Names each lane module imports at top level that we must not let leak between
    # lanes (each has its own copy in its dir).
    lane_local_names = [
        "awsio",
        "normalize",
        "outcome",
        "runspec",
        "scanners",
        "signatures",
        "compliance",
        "toolplan",
    ]
    saved_modules = {n: sys.modules.pop(n, None) for n in lane_local_names}
    saved_path = list(sys.path)
    try:
        sys.path.insert(0, lane_dir)
        sys.modules["awsio"] = awsio_stub
        spec = importlib.util.spec_from_file_location(
            alias, os.path.join(lane_dir, "handler.py")
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[alias] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path[:] = saved_path
        for n, mod in saved_modules.items():
            if mod is not None:
                sys.modules[n] = mod
            else:
                sys.modules.pop(n, None)


def _static_awsio_stub() -> types.ModuleType:
    """A stub static-scan seam: no AWS. Records the crossed summary for assertion."""
    stub = types.ModuleType("awsio")
    stub.sent = []

    def head_object_metadata(bucket, key):
        return {"metadata": {"intake-id": _INTAKE_ID, "sha256": _SHA256}, "content_length": 10}

    def download_artifact(bucket, key, dest_path):
        with open(dest_path, "wb") as fh:
            fh.write(b"# inert fixture artifact\n")

    def put_findings_document(bucket, key, document):
        return None

    def send_summary_envelope(queue_url, envelope):
        stub.sent.append(envelope)

    stub.head_object_metadata = head_object_metadata
    stub.download_artifact = download_artifact
    stub.put_findings_document = put_findings_document
    stub.send_summary_envelope = send_summary_envelope
    return stub


def _detonation_awsio_stub() -> types.ModuleType:
    """A stub detonation seam: no AWS. Simulates a clean host-native SSM run so the
    real ``outcome.build_run_envelope`` produces a genuine ``completed`` run shape."""
    stub = types.ModuleType("awsio")
    stub.sent = []

    def get_ssm_parameter(name):
        if "launch-template" in name:
            return "lt-0abc123"
        return "subnet-0abc123"

    def run_instance_from_template(**kwargs):
        return {
            "instance_id": "i-0abc123",
            "instance_type": "t3.small",
            "launch_template_version": "1",
        }

    def wait_for_ssm_online(instance_id, timeout_s, poll_s=5):
        return True

    def get_artifact_presigned_url(bucket, key, expires_s):
        return "https://example.invalid/presigned"

    def send_command(instance_id, commands, exec_timeout_s):
        return "cmd-0abc123"

    def poll_command(command_id, instance_id, timeout_s, poll_s=5):
        return {"status": "Success", "exit_code": 0, "stdout": "ok", "stderr": ""}

    def observe_teardown(instance_id, timeout_s, poll_s=10):
        return {"observed": True, "state": "terminated"}

    def terminate_instance(instance_id):
        return None

    def put_output_log(bucket, key, document):
        return None

    def send_run_envelope(queue_url, envelope):
        stub.sent.append(envelope)

    stub.get_ssm_parameter = get_ssm_parameter
    stub.run_instance_from_template = run_instance_from_template
    stub.wait_for_ssm_online = wait_for_ssm_online
    stub.get_artifact_presigned_url = get_artifact_presigned_url
    stub.send_command = send_command
    stub.poll_command = poll_command
    stub.observe_teardown = observe_teardown
    stub.terminate_instance = terminate_instance
    stub.put_output_log = put_output_log
    stub.send_run_envelope = send_run_envelope
    return stub


def _static_job():
    return {
        "kind": "static_scan_job",
        "intake_id": _INTAKE_ID,
        "sha256": _SHA256,
        "artifact_class": "raw_script",
        "bucket": "ztie-forensic-artifacts",
        "key": f"artifacts/{_INTAKE_ID}/artifact.py",
    }


def _detonation_job():
    return {
        "kind": "detonation_job",
        "intake_id": _INTAKE_ID,
        "sha256": _SHA256,
        "artifact_class": "raw_script",
        "bucket": "ztie-forensic-artifacts",
        "key": f"artifacts/{_INTAKE_ID}/artifact.py",
    }


class TestStaticBranchContract(unittest.TestCase):
    def setUp(self):
        self.stub = _static_awsio_stub()
        self.handler = _load_lane_handler(_STATIC_DIR, "static_handler", self.stub)
        # Real scanners subprocess out; the CONTRACT under test is the ENVELOPE
        # shape the handler returns, so stub the scan step to canned tool output and
        # let the REAL normalize.build_summary build the crossing shape.
        self.handler.HUB_INGEST_QUEUE_URL = "https://sqs.invalid/hub"
        self.handler._scan = lambda artifact_path, artifact_class: (
            [
                {
                    "tool": "signature_scan",
                    "status": "ok",
                    "finding_count": 1,
                    "duration_ms": 3,
                }
            ],
            [
                {
                    "tool": "signature_scan",
                    "rule_id": "SIG-001",
                    "severity": "high",
                    "title": "known-bad pattern",
                    "location": "L1",
                }
            ],
        )

    def test_direct_invoke_returns_summary_and_join_rolls_up(self):
        result = self.handler.handler(_static_job())
        # It returns the lane's real summary envelope — NOT the SQS batch object.
        self.assertNotIn("batchItemFailures", result)
        self.assertIn("scan", result)
        self.assertEqual(result["scan"]["highest_severity"], "high")
        self.assertEqual(result["scan"]["total_findings"], 1)
        # The crossed summary and the returned summary are the same shape.
        self.assertEqual(len(self.stub.sent), 1)

        env = collect.join(
            intake_id=_INTAKE_ID,
            sha256=_SHA256,
            joined_at="2026-09-07T00:00:00Z",
            lanes_expected=["static_analysis"],
            static_result=result,
            contract_version=_CV,
        )
        c = env["collected"]
        self.assertEqual(c["static"]["lane_status"], "completed")
        self.assertEqual(c["static"]["highest_severity"], "high")
        self.assertTrue(c["both_complete"])
        self.assertIsNone(_no_banned_keys(env))

    def test_old_noop_shape_is_recorded_errored(self):
        # The pre-fix return of the SQS path when invoked with no Records.
        noop = {"batchItemFailures": []}
        env = collect.join(
            intake_id=_INTAKE_ID,
            sha256=_SHA256,
            joined_at="2026-09-07T00:00:00Z",
            lanes_expected=["static_analysis"],
            static_result=noop,
            contract_version=_CV,
        )
        c = env["collected"]
        self.assertEqual(c["static"]["lane_status"], "errored")
        self.assertFalse(c["both_complete"])


class TestDetonationBranchContract(unittest.TestCase):
    def setUp(self):
        self.stub = _detonation_awsio_stub()
        self.handler = _load_lane_handler(_DETONATION_DIR, "detonation_handler", self.stub)
        self.handler.HUB_INGEST_QUEUE_URL = "https://sqs.invalid/hub"

    def test_direct_invoke_returns_run_and_join_rolls_up(self):
        result = self.handler.handler(_detonation_job())
        self.assertNotIn("batchItemFailures", result)
        self.assertIn("run", result)
        self.assertEqual(result["run"]["outcome"], "completed")
        self.assertEqual(len(self.stub.sent), 1)

        env = collect.join(
            intake_id=_INTAKE_ID,
            sha256=_SHA256,
            joined_at="2026-09-07T00:00:00Z",
            lanes_expected=["dynamic_detonation"],
            dynamic_result=result,
            contract_version=_CV,
        )
        c = env["collected"]
        self.assertEqual(c["dynamic"]["lane_status"], "completed")
        self.assertEqual(c["dynamic"]["outcome"], "completed")
        self.assertTrue(c["both_complete"])
        self.assertIsNone(_no_banned_keys(env))

    def test_old_noop_shape_is_recorded_errored(self):
        noop = {"batchItemFailures": []}
        env = collect.join(
            intake_id=_INTAKE_ID,
            sha256=_SHA256,
            joined_at="2026-09-07T00:00:00Z",
            lanes_expected=["dynamic_detonation"],
            dynamic_result=noop,
            contract_version=_CV,
        )
        c = env["collected"]
        self.assertEqual(c["dynamic"]["lane_status"], "errored")
        self.assertFalse(c["both_complete"])


class TestBothLanesEndToEnd(unittest.TestCase):
    """The load-bearing regression: a fork where BOTH lanes ran nothing must NOT
    read as both_complete (the original defect); and BOTH lanes' real returns must
    join to both_complete true."""

    def test_both_noop_never_reads_complete(self):
        env = collect.join(
            intake_id=_INTAKE_ID,
            sha256=_SHA256,
            joined_at="2026-09-07T00:00:00Z",
            lanes_expected=["static_analysis", "dynamic_detonation"],
            static_result={"batchItemFailures": []},
            dynamic_result={"batchItemFailures": []},
            contract_version=_CV,
        )
        c = env["collected"]
        self.assertEqual(c["static"]["lane_status"], "errored")
        self.assertEqual(c["dynamic"]["lane_status"], "errored")
        self.assertFalse(c["both_complete"])


if __name__ == "__main__":
    unittest.main()
