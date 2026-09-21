"""ZTIE Story 2.3 — dynamic (detonation) lane Lambda handler (Forensic-side wiring).

Runs in the **Forensic** account (360999005254). Triggered by the Forensic
detonation work queue (the preprocessor/router enqueues a job when the routing
decision names the ``dynamic_detonation`` lane, mirroring how the static lane's work
queue is fed). For each job it orchestrates ONE controlled detonation:

  1. Resolves the Story 2.0 detonation coordinates from SSM (launch-template id +
     isolated subnet ids + instance profile arn) — NO infrastructure ids are
     hard-coded here.
  2. Launches ONE **ephemeral EC2** from the 2.0 launch template via
     ``ec2:RunInstances`` (NOT CloudFormation-per-run) into an isolated subnet, no
     public IP, instance-initiated-shutdown = terminate (so the 5-min hard TTL's
     ``shutdown -h`` tears it down).
  3. Waits for the SSM agent to come Online, then EXECUTES the artifact **host-native
     via SSM** (``AWS-RunShellScript`` — NO Docker, RD-001). This is the first place
     ZTIE actually RUNS the artifact.
  4. Polls the invocation to a terminal status, observes teardown, and (finally)
     best-effort terminates the host (the hard TTL is the guaranteed backstop).
  5. Writes the FULL command log to Forensic S3 under ``runs/`` (RD-009 — it stays
     in Forensic) and crosses ONLY a bounded, derived, verdict-free run-outcome
     envelope (sixth kind) to the Hub ingest queue via the RD-013 gate.

Zero-trust invariants (RD-001 / RD-007 / RD-008 / RD-009 / RD-013):
  * The artifact executes ONLY inside Forensic, ONLY on the ephemeral host, ONLY
    host-native via SSM. Never in the Hub. Never in a container.
  * The host is contained (isolated subnet, no public IP, IMDSv2) and self-destructs
    on the hard TTL. An instance confirmed still running past its TTL is recorded as
    a SEV finding, never hidden.
  * The crossed outcome is EVIDENCE, never a verdict — no verdict/safe/forward field.
    The verdict is Hub-side / human-gated (Phase 4).

No mocks in the execution path: real EC2 + SSM + S3 + SQS via the thin awsio seam.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import os
import time
from typing import Any

import awsio
import behavior as bh
import capturespec
import outcome as oc
import sanitize as sz

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# --- Configuration (from environment; set by the CDK stack) -----------------

HUB_INGEST_QUEUE_URL = os.environ.get("HUB_INGEST_QUEUE_URL", "")
DYNAMIC_RUN_CONTRACT_VERSION = os.environ.get("DYNAMIC_RUN_CONTRACT_VERSION", "1.0")
# Story 2.4: the behavioral-telemetry contract version (its OWN pin — the eighth
# envelope kind never rides the shared CONTRACT_VERSION or the run's pin).
BEHAVIOR_CONTRACT_VERSION = os.environ.get("BEHAVIOR_CONTRACT_VERSION", "1.0")
# Story 2.5: the SANITIZED-telemetry contract version (its OWN pin — the ninth
# envelope kind never rides the shared CONTRACT_VERSION or any other kind's pin).
# The bounded, entropy-scrubbed, noise-suppressed, <=25K-token sanitized view
# crosses to the Hub under this pin; the full raw trace stays in Forensic (RD-009).
SANITIZED_TELEMETRY_CONTRACT_VERSION = os.environ.get(
    "SANITIZED_TELEMETRY_CONTRACT_VERSION", "1.0"
)
# Story 2.5: the Phase-3 token budget the sanitized view is bounded to (<=25K).
# Deterministic truncation keeps events in trace order until this budget is reached.
SANITIZE_TOKEN_BUDGET = int(os.environ.get("SANITIZE_TOKEN_BUDGET", "25000"))
# The Story 2.0 SSM parameters that publish the detonation coordinates (so this
# lane hard-codes no infrastructure ids).
LAUNCH_TEMPLATE_ID_PARAM = os.environ.get(
    "LAUNCH_TEMPLATE_ID_PARAM", "/ztie/detonation/launch-template-id"
)
ISOLATED_SUBNET_IDS_PARAM = os.environ.get(
    "ISOLATED_SUBNET_IDS_PARAM", "/ztie/detonation/isolated-subnet-ids"
)
# RD-027 (two-tier): coordinates for the EPHEMERAL endpoint tier (logs/sqs/
# bedrock-runtime) this lane stands up per run. The SSM control channel is
# ALWAYS-ON in the infra stack and needs no per-run action. Service names + SG id
# are published to SSM so no infrastructure literals are hard-coded here.
VPC_ID_PARAM = os.environ.get("VPC_ID_PARAM", "/ztie/detonation/vpc-id")
ENDPOINT_SERVICE_NAMES_PARAM = os.environ.get(
    "ENDPOINT_SERVICE_NAMES_PARAM", "/ztie/detonation/endpoint-service-names"
)
ENDPOINT_SECURITY_GROUP_ID_PARAM = os.environ.get(
    "ENDPOINT_SECURITY_GROUP_ID_PARAM",
    "/ztie/detonation/endpoint-security-group-id",
)
# Budget for the ephemeral tier to reach 'available' before it is needed. These are
# not the SSM channel, so the host can boot + register in parallel; a modest wait.
ENDPOINT_AVAILABLE_TIMEOUT_S = int(os.environ.get("ENDPOINT_AVAILABLE_TIMEOUT_S", "180"))
# NOTE: the instance PROFILE is NOT resolved or passed by this lane — the 2.0
# launch template already carries it (CDK's LaunchTemplate({ role }) bakes an
# instance profile into the template). RunInstances inherits it from the template.

# The hard TTL (minutes) baked into the 2.0 launch-template UserData (RD-007). This
# lane does not set it; it only RECORDS it in the outcome for evidence.
HARD_TTL_MINUTES = int(os.environ.get("HARD_TTL_MINUTES", "5"))
# Prefix under which the full command log is written in the Forensic bucket.
RUNS_PREFIX = os.environ.get("RUNS_PREFIX", "runs/")
# Story 2.4: prefix under which the FULL behavioral trace is written in the Forensic
# bucket (RD-009 — it stays in Forensic; only the bounded summary crosses).
TRACES_PREFIX = os.environ.get("TRACES_PREFIX", "traces/")

# Orchestration budgets (all comfortably inside the SQS visibility timeout the
# stack sets, and all well under the hard TTL so the host is torn down regardless).
SSM_ONLINE_TIMEOUT_S = int(os.environ.get("SSM_ONLINE_TIMEOUT_S", "120"))
EXEC_TIMEOUT_S = int(os.environ.get("EXEC_TIMEOUT_S", "120"))
EXEC_POLL_TIMEOUT_S = int(os.environ.get("EXEC_POLL_TIMEOUT_S", "150"))
TEARDOWN_OBSERVE_TIMEOUT_S = int(os.environ.get("TEARDOWN_OBSERVE_TIMEOUT_S", "60"))
PRESIGN_EXPIRES_S = int(os.environ.get("PRESIGN_EXPIRES_S", "300"))

# The S3 object user-metadata keys stamped by the intake handler (1.1).
_MD_INTAKE_ID = "intake-id"
_MD_SHA256 = "sha256"
# The lane id (must match the routing contract's lane enum).
_DYNAMIC_LANE = "dynamic_detonation"


class DetonationJobError(Exception):
    """A non-retryable job failure (malformed job / missing artifact identity)."""


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _is_direct_invoke(event: dict[str, Any]) -> bool:
    """A Story 2.6 fork branch invokes this lane DIRECTLY with a single job dict
    (the ``detonation_job`` the preprocessor built — bucket/key/intake_id/sha256/
    artifact_class at the top level), NOT the SQS ``Records`` batch shape. Detect
    that here so the same handler serves both the SQS work queue AND the SFN
    Parallel branch. A direct invoke has no ``Records`` and carries the job's own
    coordinates."""
    if not isinstance(event, dict):
        return False
    if "Records" in event:
        return False
    return bool(event.get("bucket") and event.get("key"))


def _iter_jobs(event: dict[str, Any]):
    """Yield (job, message_id) for each SQS record. The job body carries the
    artifact coordinates the preprocessor enqueued."""
    for record in event.get("Records", []) or []:
        message_id = record.get("messageId") or ""
        body = record.get("body")
        try:
            job = json.loads(body) if body else None
        except (json.JSONDecodeError, TypeError):
            job = None
        yield job, message_id


def _resolve_coordinates() -> dict[str, Any]:
    """Read the 2.0-published detonation coordinates from SSM (no hard-coded ids).

    The launch-template id + an isolated subnet drive the host launch (the instance
    profile, SG, key-pair policy, IMDSv2, root volume and TTL UserData all come from
    the launch template itself). RD-027 adds the coordinates for the EPHEMERAL
    endpoint tier this lane stands up per run (logs/sqs/bedrock-runtime): the VPC id,
    the ordered service names, and the endpoint SG. The SSM control channel is
    always-on and needs no coordinates here.
    """
    launch_template_id = awsio.get_ssm_parameter(LAUNCH_TEMPLATE_ID_PARAM)
    subnet_csv = awsio.get_ssm_parameter(ISOLATED_SUBNET_IDS_PARAM)
    subnet_ids = [s for s in subnet_csv.split(",") if s]
    if not subnet_ids:
        raise DetonationJobError("no isolated subnet ids published in SSM")
    vpc_id = awsio.get_ssm_parameter(VPC_ID_PARAM)
    svc_csv = awsio.get_ssm_parameter(ENDPOINT_SERVICE_NAMES_PARAM)
    endpoint_service_names = [s for s in svc_csv.split(",") if s]
    endpoint_sg_id = awsio.get_ssm_parameter(ENDPOINT_SECURITY_GROUP_ID_PARAM)
    return {
        "launch_template_id": launch_template_id,
        "subnet_id": subnet_ids[0],
        "vpc_id": vpc_id,
        "endpoint_service_names": endpoint_service_names,
        "endpoint_sg_id": endpoint_sg_id,
    }


def _detonate(job: dict[str, Any]) -> dict[str, Any]:
    """Orchestrate ONE detonation end-to-end. Returns the derived run-outcome
    envelope. A launch/exec/teardown failure is RECORDED in the outcome (a bounded
    error), never crashes the lane — the run is always a bounded evidence record."""
    bucket = job.get("bucket")
    key = job.get("key")
    if not bucket or not key:
        raise DetonationJobError("job missing bucket/key")
    intake_id = job.get("intake_id")
    sha256 = job.get("sha256")
    artifact_class = job.get("artifact_class") or "other_unknown"
    if not intake_id or not sha256:
        raise DetonationJobError(f"job for s3://{bucket}/{key} missing intake_id/sha256")

    coords = _resolve_coordinates()
    started_at = _now_iso()
    t0 = time.monotonic()

    # --- RD-027: stand up the EPHEMERAL endpoint tier (logs/sqs/bedrock) ------
    # The SSM control channel is always-on, so the host can boot + register in
    # parallel with this; we still bring these up before launch so they are ready
    # when the run needs them. Sweep any orphans from a prior crashed run first
    # (the backstop that keeps idle cost from accumulating). Torn down in finally.
    swept = awsio.sweep_orphaned_endpoints(coords["vpc_id"])
    if swept:
        logger.info(
            "swept %d orphaned ephemeral endpoint(s) before intake_id=%s: %s",
            len(swept),
            intake_id,
            ",".join(swept),
        )
    endpoint_ids: list[str] = []
    if coords["endpoint_service_names"]:
        try:
            endpoint_ids = awsio.create_interface_endpoints(
                vpc_id=coords["vpc_id"],
                subnet_id=coords["subnet_id"],
                security_group_id=coords["endpoint_sg_id"],
                service_names=coords["endpoint_service_names"],
                intake_id=intake_id,
            )
            awsio.wait_for_endpoints_available(
                endpoint_ids, ENDPOINT_AVAILABLE_TIMEOUT_S
            )
            logger.info(
                "created %d ephemeral endpoint(s) for intake_id=%s: %s",
                len(endpoint_ids),
                intake_id,
                ",".join(endpoint_ids),
            )
        except Exception:
            # Non-fatal: the ephemeral tier is logs/sqs/bedrock, not the control
            # channel. Record nothing special; tear down what we made and proceed
            # to launch (the detonation can still run + report host-native via the
            # always-on SSM channel). A truly needed endpoint failing surfaces in
            # the run outcome.
            logger.exception(
                "ephemeral endpoint setup failed for intake_id=%s (proceeding)",
                intake_id,
            )
            awsio.delete_interface_endpoints(endpoint_ids)
            endpoint_ids = []

    # --- Launch ONE ephemeral host from the 2.0 launch template --------------
    try:
        launched = awsio.run_instance_from_template(
            launch_template_id=coords["launch_template_id"],
            subnet_id=coords["subnet_id"],
            tags={
                "Project": "ZTIE",
                "Lane": _DYNAMIC_LANE,
                "IntakeId": intake_id,
                "Ephemeral": "true",
            },
        )
    except Exception as exc:
        logger.exception("RunInstances failed for intake_id=%s", intake_id)
        # RD-027: no host launched, so tear down the ephemeral endpoints we made.
        awsio.delete_interface_endpoints(endpoint_ids)
        run = oc.build_launch_error_run(
            artifact_class=artifact_class,
            launch_template_id=coords["launch_template_id"],
            hard_ttl_minutes=HARD_TTL_MINUTES,
            error_reason=f"RunInstances failed: {exc}",
        )
        return oc.build_run_envelope(
            intake_id=intake_id,
            sha256=sha256,
            detonated_at=_now_iso(),
            run=run,
            contract_version=DYNAMIC_RUN_CONTRACT_VERSION,
        )

    instance_id = launched["instance_id"]
    logger.info(
        "launched ephemeral detonation host instance_id=%s intake_id=%s from template=%s",
        instance_id,
        intake_id,
        coords["launch_template_id"],
    )

    ssm_status = oc.SSM_STATUS_NOT_RUN
    exit_code: int | None = None
    stdout = ""
    stderr = ""
    command_id: str | None = None
    error_reason: str | None = None
    outcome_label = oc.OUTCOME_TIMED_OUT
    # Story 2.4: relative monotonic offsets (ms from detonation start t0) for the
    # behavioral capture window. None until capture is actually started on the host.
    capture_started_offset_ms: int | None = None
    capture_stopped_offset_ms: int | None = None
    capture_reached = False

    try:
        # --- Wait for the host-native SSM channel to be Online ---------------
        if not awsio.wait_for_ssm_online(instance_id, SSM_ONLINE_TIMEOUT_S):
            error_reason = "SSM agent did not report Online within budget"
            outcome_label = oc.OUTCOME_DELIVERY_ERROR
        else:
            # --- Deliver the artifact + run it UNDER behavioral capture ------
            # Story 2.4 instruments the 2.3 run: the SAME host-native SSM command
            # (NO Docker) fetches the artifact, then runs it under the pre-baked
            # capture tool (strace, RD-030), emitting the trace between markers.
            presigned = awsio.get_artifact_presigned_url(bucket, key, PRESIGN_EXPIRES_S)
            filename = key.rsplit("/", 1)[-1] or "artifact"
            artifact_path = capturespec.artifact_host_path(filename)
            commands = capturespec.build_fetch_commands(
                presigned_url=presigned, dest_path=artifact_path
            ) + capturespec.build_capture_run_commands(
                # Story 2.4S / Fix B (RD-058): pass the Forensic artifact bucket + intake_id
                # so the HOST uploads the strace per-PID files DIRECTLY to
                # traces/{intake_id}/ before the stdout emit block — the trace survives even
                # if the SSM stdout pipe hangs (attempts 1-6) and the wrapper is SIGKILLed.
                artifact_path=artifact_path,
                bucket=bucket,
                intake_id=intake_id,
            )
            # The capture window opens when we hand the run to the host.
            capture_started_offset_ms = int((time.monotonic() - t0) * 1000)
            capture_reached = True
            command_id = awsio.send_command(instance_id, commands, EXEC_TIMEOUT_S)
            logger.info(
                "sent host-native SSM command (with capture) command_id=%s "
                "instance_id=%s intake_id=%s",
                command_id,
                instance_id,
                intake_id,
            )
            result = awsio.poll_command(
                command_id, instance_id, EXEC_POLL_TIMEOUT_S
            )
            # The capture window closes when the host-native command reaches terminal.
            capture_stopped_offset_ms = int((time.monotonic() - t0) * 1000)
            ssm_status = (
                result["status"] if result["status"] in oc.SSM_STATUSES else oc.SSM_STATUS_NOT_RUN
            )
            exit_code = result.get("exit_code")
            stdout = result.get("stdout") or ""
            stderr = result.get("stderr") or ""
            outcome_label = oc.outcome_from_ssm_status(ssm_status)
    except Exception as exc:
        logger.exception("host-native execution failed for intake_id=%s", intake_id)
        error_reason = f"execution failed: {exc}"
        outcome_label = oc.OUTCOME_EXECUTION_ERROR
    finally:
        # Best-effort explicit terminate; the hard TTL is the guaranteed backstop.
        awsio.terminate_instance(instance_id)
        # RD-027: tear down the ephemeral endpoint tier so it bills only for this
        # run. Best-effort (never fatal); the start-of-run orphan sweep is the
        # backstop. Cost concern only — the always-on SSM channel is untouched.
        awsio.delete_interface_endpoints(endpoint_ids)
        if endpoint_ids:
            logger.info(
                "tore down %d ephemeral endpoint(s) for intake_id=%s",
                len(endpoint_ids),
                intake_id,
            )

    # --- Observe teardown (the host reaching shutting-down/terminated) -------
    teardown_view = awsio.observe_teardown(instance_id, TEARDOWN_OBSERVE_TIMEOUT_S)
    teardown_observed = teardown_view["observed"]
    if teardown_observed:
        teardown_note = f"observed {teardown_view['state']}"
        terminated_at: str | None = _now_iso()
    else:
        # Not observing teardown is NOT a failure — the hard TTL fires independently.
        # But if the host is confirmed STILL running, that is the SEV finding.
        last_state = teardown_view["state"]
        terminated_at = None
        if last_state == "running":
            teardown_note = (
                f"SEV: host still 'running' after {TEARDOWN_OBSERVE_TIMEOUT_S}s; "
                f"hard TTL shutdown -h +{HARD_TTL_MINUTES} is the backstop"
            )
        else:
            teardown_note = (
                f"teardown not observed within budget (last state {last_state}); "
                f"hard TTL is the backstop"
            )

    # --- Write the FULL command log to Forensic S3 (stays in Forensic) -------
    output_key = f"{RUNS_PREFIX}{intake_id}/detonation-output.json"
    try:
        awsio.put_output_log(
            bucket,
            output_key,
            {
                "intake_id": intake_id,
                "sha256": sha256,
                "instance_id": instance_id,
                "ssm_command_id": command_id,
                "ssm_status": ssm_status,
                "exit_code": exit_code,
                "stdout": stdout,
                "stderr": stderr,
                "detonated_at": _now_iso(),
            },
        )
        output_s3_bucket: str | None = bucket
        output_s3_key: str | None = output_key
    except Exception:
        logger.exception("failed to write full output log for intake_id=%s", intake_id)
        output_s3_bucket = None
        output_s3_key = None

    duration_ms = int((time.monotonic() - t0) * 1000)

    execution = oc.build_execution(
        ssm_status=ssm_status,
        ssm_command_id=command_id,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        output_s3_bucket=output_s3_bucket,
        output_s3_key=output_s3_key,
    )
    teardown = oc.build_teardown(
        hard_ttl_minutes=HARD_TTL_MINUTES,
        teardown_observed=teardown_observed,
        terminated_at=terminated_at,
        teardown_note=teardown_note,
    )
    run = oc.build_run(
        artifact_class=artifact_class,
        outcome=outcome_label,
        launch_template_id=coords["launch_template_id"],
        launched_from_template=True,
        instance_id=instance_id,
        launch_template_version=launched.get("launch_template_version"),
        instance_type=launched.get("instance_type"),
        started_at=started_at,
        duration_ms=duration_ms,
        error_reason=error_reason,
        execution=execution,
        teardown=teardown,
    )
    logger.info(
        "detonation complete intake_id=%s instance_id=%s outcome=%s ssm_status=%s "
        "teardown_observed=%s duration_ms=%d",
        intake_id,
        instance_id,
        outcome_label,
        ssm_status,
        teardown_observed,
        duration_ms,
    )

    # --- Story 2.4: behavioral telemetry (captured DURING the run above) -----
    # Slice the trace out of the combined SSM output, write the FULL trace to
    # Forensic S3 (RD-009), and cross a bounded, verdict-free behavioral summary to
    # the Hub as its OWN envelope kind (the eighth). A capture failure is RECORDED
    # (capture_status), never fatal to the run — the run outcome above is unaffected.
    behavior_envelope, sanitized_envelope = _build_telemetry_envelopes(
        bucket=bucket,
        intake_id=intake_id,
        sha256=sha256,
        stdout=stdout,
        ssm_status=ssm_status,
        capture_reached=capture_reached,
        capture_started_offset_ms=capture_started_offset_ms,
        capture_stopped_offset_ms=capture_stopped_offset_ms,
    )
    try:
        awsio.send_behavior_envelope(HUB_INGEST_QUEUE_URL, behavior_envelope)
    except Exception:
        # Crossing the behavioral summary is best-effort relative to the run: the
        # run outcome is the primary evidence and already crosses separately. Record
        # and continue (the full trace, if any, is still in Forensic).
        logger.exception(
            "failed to cross behavioral telemetry for intake_id=%s", intake_id
        )

    # --- Story 2.5: sanitized telemetry (the cleaned view for Phase-3) -------
    # The SANITIZED view (entropy-scrubbed, noise-suppressed, <=25K-token) crosses
    # as its OWN envelope kind (the ninth), INDEPENDENTLY of the raw behavior
    # summary and the run outcome. The full raw trace stays in Forensic (RD-009);
    # only this bounded, verdict-free sanitized view crosses. A crossing failure is
    # RECORDED, never fatal to the run.
    try:
        awsio.send_sanitized_envelope(HUB_INGEST_QUEUE_URL, sanitized_envelope)
    except Exception:
        logger.exception(
            "failed to cross sanitized telemetry for intake_id=%s", intake_id
        )

    return oc.build_run_envelope(
        intake_id=intake_id,
        sha256=sha256,
        detonated_at=_now_iso(),
        run=run,
        contract_version=DYNAMIC_RUN_CONTRACT_VERSION,
    )


def _sanitized_gap_envelope(
    *, intake_id: str, sha256: str, capture_tool: str
) -> dict[str, Any]:
    """Assemble the Story 2.5 sanitized-telemetry envelope for a NO-TRACE case
    (capture was never reached, the tool was unavailable, or capture produced no
    trace). The gap is RECORDED in the pipeline accounting (status='no_trace'),
    never faked — there was nothing to sanitize. Pure-shape; the empty pipeline is
    built by ``sanitize_trace(None)``."""
    result = sz.sanitize_trace(None, token_budget=SANITIZE_TOKEN_BUDGET)
    source = sz.build_source(capture_tool=capture_tool)
    sanitized = sz.build_sanitized(source=source, pipeline=result["pipeline"])
    return sz.build_sanitized_envelope(
        intake_id=intake_id,
        sha256=sha256,
        sanitized_at=_now_iso(),
        sanitized=sanitized,
        contract_version=SANITIZED_TELEMETRY_CONTRACT_VERSION,
    )


def _build_telemetry_envelopes(
    *,
    bucket: str,
    intake_id: str,
    sha256: str,
    stdout: str,
    ssm_status: str,
    capture_reached: bool,
    capture_started_offset_ms: int | None,
    capture_stopped_offset_ms: int | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Assemble BOTH telemetry envelopes from the run's captured output:

      * the Story 2.4 behavioral-telemetry summary (the raw, bounded tallies), and
      * the Story 2.5 SANITIZED view (entropy-scrubbed, noise-suppressed,
        <=25K-token) — the cleaned view the Phase-3 correlation engine consumes.

    Both are pure-logic derivations of the SAME raw trace (no re-capture). The full
    raw trace is written to Forensic once (RD-009) and BOTH envelopes reference it;
    only the bounded/sanitized derivations cross. A missing/failed capture is
    recorded via capture_status (2.4) and status='no_trace' (2.5), never faked and
    never fatal. Returns (behavior_envelope, sanitized_envelope)."""
    # Capture was never reached (the run never executed host-native — launch_error /
    # delivery_error / SSM-online failure upstream): nothing to capture or sanitize.
    if not capture_reached:
        capture = bh.build_capture(
            capture_tool=bh.CAPTURE_TOOL_NONE,
            capture_status=bh.CAPTURE_STATUS_NOT_RUN,
            error_reason="detonation never executed host-native; no capture",
        )
        behavior_env = bh.build_behavior_envelope(
            intake_id=intake_id,
            sha256=sha256,
            captured_at=_now_iso(),
            behavior=bh.build_behavior(capture=capture),
            contract_version=BEHAVIOR_CONTRACT_VERSION,
        )
        sanitized_env = _sanitized_gap_envelope(
            intake_id=intake_id, sha256=sha256, capture_tool=sz.CAPTURE_TOOL_NONE
        )
        return behavior_env, sanitized_env

    trace, tool_unavailable = capturespec.slice_trace(stdout)
    # Story 2.4R attempt-4: did the artifact hit the inner ``timeout`` (it hung/blocked,
    # e.g. a ``/dev/tcp`` connect with no egress)? The marker is emitted OUTSIDE the trace
    # markers, so it is in stdout but not in the sliced trace. It is an honest
    # capture-HEALTH fact (a time-bounded run), never a verdict — a hanging artifact is
    # itself EVIDENCE. We surface it in the error_reason (no trace) or the capture note
    # (partial trace) so the crossed record explains a time-bounded run instead of a
    # silent gap, and so the whole wrapper no longer dies to the SSM executionTimeout.
    timed_out = capturespec.artifact_timed_out(stdout)

    # --- Story 2.4S / Fix B (RD-058): S3-FIRST trace source ------------------
    # Attempts 1-6 proved the in-wrapper strace->SSM-stdout transport is structurally
    # fragile: a hanging artifact holds the SSM stdout pipe open, the wrapper never reaches
    # (or its output never returns from) the emit block, the SSM command hits the 120 s
    # executionTimeout and is SIGKILLed (137), and the sliced-from-stdout trace is EMPTY.
    # Fix B has the HOST upload the strace per-PID files DIRECTLY to Forensic S3
    # (traces/{intake_id}/) the moment strace exits, with an _UPLOAD_COMPLETE sentinel
    # written last. So we READ THE TRACE FROM S3 here, out-of-band from the SSM status:
    #   * If a COMPLETE S3 trace exists (sentinel present), it is the authoritative trace
    #     REGARDLESS of the SSM status — a `TimedOut`/`Failed` SSM command whose trace is
    #     complete in S3 is a SUCCESSFUL capture, NOT a failure (the whole point of Fix B;
    #     otherwise we would have durable evidence in S3 and still record a FAIL).
    #   * If S3 has per-PID objects but NO sentinel, the upload was partial (host killed
    #     mid-copy) — use it but mark it truncated.
    #   * If S3 has nothing, fall back to the stdout slice (a host without the Fix-B
    #     upload, or an upload that never ran). Preserves backward behavior.
    ssm_timed_out = ssm_status in ("TimedOut", "Failed")
    trace_from_s3 = False
    s3_trace_partial = False
    if not tool_unavailable:
        try:
            s3_trace = awsio.read_uploaded_trace(bucket, intake_id)
        except Exception:
            logger.exception(
                "reading uploaded S3 trace failed for intake_id=%s (falling back to stdout)",
                intake_id,
            )
            s3_trace = {"complete": False, "trace": None, "object_count": 0}
        if s3_trace["trace"]:
            # Prefer the S3 trace whenever it exists; it is the durable transport. A
            # complete S3 trace overrides a TimedOut/Failed SSM status (Fix B success).
            trace = s3_trace["trace"]
            trace_from_s3 = True
            s3_trace_partial = not s3_trace["complete"]
            logger.info(
                "using S3-uploaded behavioral trace for intake_id=%s "
                "(objects=%d complete=%s ssm_status=%s)",
                intake_id,
                s3_trace["object_count"],
                s3_trace["complete"],
                ssm_status,
            )

    # The host reported the capture tool (strace) was not present — a recorded gap.
    if tool_unavailable:
        capture = bh.build_capture(
            capture_tool=bh.CAPTURE_TOOL_NONE,
            capture_status=bh.CAPTURE_STATUS_TOOL_UNAVAILABLE,
            capture_started_offset_ms=capture_started_offset_ms,
            capture_stopped_offset_ms=capture_stopped_offset_ms,
            error_reason="strace not present on host; run was uninstrumented",
        )
        behavior_env = bh.build_behavior_envelope(
            intake_id=intake_id,
            sha256=sha256,
            captured_at=_now_iso(),
            behavior=bh.build_behavior(capture=capture),
            contract_version=BEHAVIOR_CONTRACT_VERSION,
        )
        sanitized_env = _sanitized_gap_envelope(
            intake_id=intake_id, sha256=sha256, capture_tool=sz.CAPTURE_TOOL_NONE
        )
        return behavior_env, sanitized_env

    # Capture ran but produced no trace text (empty between markers, or markers
    # missing), OR strace ran but wrote no per-PID file and shipped its own stderr as
    # a SELF-DIAGNOSING payload (Story 2.4R FAIL #2 — e.g. a rejected -e expression):
    # record capture_error with no summary rather than a fake one. When the host
    # shipped the strace stderr, surface it as the error_reason so the crossed record
    # explains WHY instead of a silent "no trace".
    diag = capturespec.no_trace_diagnostic(trace)
    if diag is not None or not trace:
        if diag is not None:
            error_reason = f"strace produced no trace files: {diag}"
        elif timed_out:
            # The artifact hung and was time-bounded before strace wrote any per-PID
            # file (e.g. it blocked in connect() before doing traceable work). Honest,
            # non-verdict health fact — the whole wrapper SURVIVED to record this
            # (the Story 2.4R attempt-4 fix), where before it was SIGKILLed with no record.
            error_reason = (
                "artifact hit the inner execution timeout "
                f"({capturespec.ARTIFACT_EXEC_TIMEOUT_S}s) before any trace was captured "
                "(hanging/blocking run, e.g. a network connect with no egress)"
            )
        else:
            error_reason = "no behavioral trace emitted between capture markers"
        capture = bh.build_capture(
            capture_tool=bh.CAPTURE_TOOL_STRACE,
            capture_status=bh.CAPTURE_STATUS_ERROR,
            capture_started_offset_ms=capture_started_offset_ms,
            capture_stopped_offset_ms=capture_stopped_offset_ms,
            error_reason=error_reason,
        )
        behavior_env = bh.build_behavior_envelope(
            intake_id=intake_id,
            sha256=sha256,
            captured_at=_now_iso(),
            behavior=bh.build_behavior(capture=capture),
            contract_version=BEHAVIOR_CONTRACT_VERSION,
        )
        # There is a capture tool but no trace to sanitize — still a no-trace gap
        # for 2.5, recorded with the strace tool so the source pointer is honest.
        result = sz.sanitize_trace(None, token_budget=SANITIZE_TOKEN_BUDGET)
        sanitized_env = sz.build_sanitized_envelope(
            intake_id=intake_id,
            sha256=sha256,
            sanitized_at=_now_iso(),
            sanitized=sz.build_sanitized(
                source=sz.build_source(capture_tool=sz.CAPTURE_TOOL_STRACE),
                pipeline=result["pipeline"],
            ),
            contract_version=SANITIZED_TELEMETRY_CONTRACT_VERSION,
        )
        return behavior_env, sanitized_env

    # Capture succeeded: write the FULL trace to Forensic (RD-009), then derive BOTH
    # the bounded 2.4 summary and the 2.5 sanitized view from that SAME raw trace.
    # If the S3 write fails the derivations still cross (the pointer is just omitted).
    trace_key = f"{TRACES_PREFIX}{intake_id}/behavior-trace.txt"
    trace_bucket: str | None = None
    trace_s3_key: str | None = None
    try:
        awsio.put_trace(bucket, trace_key, trace)
        trace_bucket = bucket
        trace_s3_key = trace_key
    except Exception:
        logger.exception(
            "failed to write full behavioral trace for intake_id=%s", intake_id
        )

    summaries = bh.summarize_trace(trace)
    # The on-host head -c cap (capturespec) may have truncated the emitted trace.
    # A time-bounded artifact (Story 2.4R attempt-4) also yields an incomplete trace —
    # the run was cut short — so we mark trace_truncated and note the timeout, while
    # still crossing whatever real behavior strace DID capture before the cut.
    # Story 2.4S / Fix B: a PARTIAL S3 upload (per-PID objects present but the
    # _UPLOAD_COMPLETE sentinel absent — the host was killed mid-copy) is also an
    # incomplete trace, so it counts toward trace_truncated.
    truncated = (
        len(trace.encode("utf-8")) >= capturespec.ON_HOST_TRACE_CAP_BYTES
        or timed_out
        or s3_trace_partial
    )
    # Honest capture-health note. Story 2.4S: when the trace was recovered from S3 even
    # though the SSM command timed out / failed, SAY SO — this is the Fix B success case
    # (durable evidence survived a hung transport), NOT a failure. A hanging artifact is
    # EVIDENCE, never a verdict.
    if trace_from_s3 and ssm_timed_out:
        timeout_note = (
            "SSM command reported "
            f"{ssm_status}, but a "
            f"{'partial' if s3_trace_partial else 'complete'} behavioral trace was "
            "recovered from the host's direct S3 upload (Story 2.4S/RD-058): the trace "
            "survived the hung stdout transport"
            + (
                "; artifact also hit the inner execution timeout "
                f"({capturespec.ARTIFACT_EXEC_TIMEOUT_S}s, hanging/blocking run)"
                if timed_out
                else ""
            )
        )
    elif timed_out:
        timeout_note = (
            "artifact hit the inner execution timeout "
            f"({capturespec.ARTIFACT_EXEC_TIMEOUT_S}s) and was terminated; trace is partial "
            "(hanging/blocking run, e.g. a network connect with no egress)"
        )
    elif s3_trace_partial:
        timeout_note = (
            "behavioral trace recovered from the host's direct S3 upload was partial "
            "(the _UPLOAD_COMPLETE sentinel was absent — host terminated mid-upload)"
        )
    else:
        timeout_note = None
    capture = bh.build_capture(
        capture_tool=bh.CAPTURE_TOOL_STRACE,
        capture_status=bh.CAPTURE_STATUS_CAPTURED,
        capture_started_offset_ms=capture_started_offset_ms,
        capture_stopped_offset_ms=capture_stopped_offset_ms,
        trace_truncated=truncated,
        trace_s3_bucket=trace_bucket,
        trace_s3_key=trace_s3_key,
        error_reason=timeout_note,
    )
    behavior_env = bh.build_behavior_envelope(
        intake_id=intake_id,
        sha256=sha256,
        captured_at=_now_iso(),
        behavior=bh.build_behavior(capture=capture, summaries=summaries),
        contract_version=BEHAVIOR_CONTRACT_VERSION,
    )

    # --- Story 2.5: sanitize the SAME raw trace (pure pipeline) --------------
    result = sz.sanitize_trace(trace, token_budget=SANITIZE_TOKEN_BUDGET)
    source = sz.build_source(
        capture_tool=sz.CAPTURE_TOOL_STRACE,
        trace_s3_bucket=trace_bucket,
        trace_s3_key=trace_s3_key,
        raw_trace_bytes=len(trace.encode("utf-8")),
    )
    sanitized_env = sz.build_sanitized_envelope(
        intake_id=intake_id,
        sha256=sha256,
        sanitized_at=_now_iso(),
        sanitized=sz.build_sanitized(
            source=source,
            pipeline=result["pipeline"],
            events=result["events"],
        ),
        contract_version=SANITIZED_TELEMETRY_CONTRACT_VERSION,
    )
    return behavior_env, sanitized_env


def _process_job(job: dict[str, Any]) -> dict[str, Any]:
    """Detonate one artifact and cross the outcome. Returns the run-outcome envelope
    (the shape the Story 2.6 collector rolls up). The behavioral-telemetry envelope
    (Story 2.4) AND the sanitized-telemetry envelope (Story 2.5) are crossed
    INDEPENDENTLY inside ``_detonate`` — each attaches to the same tracking record
    but is a separate envelope kind, not part of the collector join, so the 2.6
    direct-invoke contract is unchanged."""
    envelope = _detonate(job)
    awsio.send_run_envelope(HUB_INGEST_QUEUE_URL, envelope)
    return envelope


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """SQS-triggered entry point. Detonates each queued artifact.

    Returns partial-batch failures so a single failing job is retried/DLQ'd without
    reprocessing the ones that already succeeded. A malformed job (non-retryable) is
    logged and skipped; a transient AWS error is reported for retry.
    """
    if not HUB_INGEST_QUEUE_URL:
        logger.error("Misconfigured: HUB_INGEST_QUEUE_URL not set")
        raise RuntimeError("Detonation lane is misconfigured")

    # Story 2.6: a Step Functions Parallel branch invokes this lane DIRECTLY with a
    # single job dict. Run the detonation and RETURN the derived run-outcome
    # envelope so the branch's `outputPath: "$.Payload"` yields the real dynamic-run
    # shape the collector rolls up — NOT the SQS partial-batch object. A malformed
    # job raises DetonationJobError, which propagates so the branch's Catch records
    # the lane as errored (never a silent no-op that reads as completed).
    if _is_direct_invoke(event):
        envelope = _process_job(event)
        logger.info(
            "detonation direct-invoke complete intake_id=%s (SFN fork branch)",
            envelope.get("intake_id"),
        )
        return envelope

    batch_item_failures: list[dict[str, str]] = []
    processed = 0

    for job, message_id in _iter_jobs(event):
        if not isinstance(job, dict):
            logger.warning("skipping unparsable detonation job message_id=%s", message_id)
            continue
        try:
            _process_job(job)
            processed += 1
        except DetonationJobError as exc:
            # Non-retryable: a malformed job / foreign object. Log and skip.
            logger.warning("skipping detonation job: %s", exc)
        except Exception:
            # Transient (AWS error). Report so it retries/DLQs. The host is still
            # torn down by the hard TTL regardless of this control-plane failure.
            logger.exception(
                "unprocessable detonation job message_id=%s (will retry)", message_id
            )
            if message_id:
                batch_item_failures.append({"itemIdentifier": message_id})

    logger.info("detonation processed=%d failures=%d", processed, len(batch_item_failures))
    return {"batchItemFailures": batch_item_failures}
