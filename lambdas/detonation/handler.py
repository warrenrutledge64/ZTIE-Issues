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
import outcome as oc
import runspec

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# --- Configuration (from environment; set by the CDK stack) -----------------

HUB_INGEST_QUEUE_URL = os.environ.get("HUB_INGEST_QUEUE_URL", "")
DYNAMIC_RUN_CONTRACT_VERSION = os.environ.get("DYNAMIC_RUN_CONTRACT_VERSION", "1.0")
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

    try:
        # --- Wait for the host-native SSM channel to be Online ---------------
        if not awsio.wait_for_ssm_online(instance_id, SSM_ONLINE_TIMEOUT_S):
            error_reason = "SSM agent did not report Online within budget"
            outcome_label = oc.OUTCOME_DELIVERY_ERROR
        else:
            # --- Deliver + execute host-native via SSM (NO Docker) -----------
            presigned = awsio.get_artifact_presigned_url(bucket, key, PRESIGN_EXPIRES_S)
            filename = key.rsplit("/", 1)[-1] or "artifact"
            commands = runspec.build_run_commands(
                filename=filename,
                artifact_class=artifact_class,
                presigned_url=presigned,
            )
            command_id = awsio.send_command(instance_id, commands, EXEC_TIMEOUT_S)
            logger.info(
                "sent host-native SSM command command_id=%s instance_id=%s intake_id=%s",
                command_id,
                instance_id,
                intake_id,
            )
            result = awsio.poll_command(
                command_id, instance_id, EXEC_POLL_TIMEOUT_S
            )
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
    return oc.build_run_envelope(
        intake_id=intake_id,
        sha256=sha256,
        detonated_at=_now_iso(),
        run=run,
        contract_version=DYNAMIC_RUN_CONTRACT_VERSION,
    )


def _process_job(job: dict[str, Any]) -> dict[str, Any]:
    """Detonate one artifact and cross the outcome. Returns the outcome envelope."""
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
