"""ZTIE Story 2.3 — thin AWS I/O seam for the dynamic (detonation) lane.

ALL boto3 lives HERE so the run-outcome logic (``outcome.py``) stays pure and
offline-unit-testable (the proven 1.2 -> 2.2 lane pattern). Nothing in this module
makes a verdict; it only:

  * resolves the Story 2.0 detonation coordinates from SSM parameters
    (``/ztie/detonation/launch-template-id`` + ``/ztie/detonation/isolated-subnet-ids``),
    so the lane hard-codes NO infrastructure ids,
  * launches ONE ephemeral EC2 from the 2.0 launch template via ``ec2:RunInstances``
    (NOT CloudFormation-per-run) into an isolated subnet, with no public IP and
    instance-initiated-shutdown = terminate (so the hard TTL tears it down),
  * waits for the SSM agent to register the instance,
  * executes the artifact host-native via ``ssm:SendCommand`` (AWS-RunShellScript —
    NO Docker, RD-001) and polls the invocation to a terminal status,
  * observes teardown (the instance reaching shutting-down / terminated),
  * writes the FULL command output log to Forensic S3 under ``runs/`` (RD-009 — it
    stays in Forensic; only the bounded tails cross),
  * sends the derived, bounded run-outcome envelope to the Hub ingest queue (the same
    one-directional RD-013 door the other envelopes use).

No mocks in the execution path: real EC2 + SSM + S3 + SQS. moto is used only in the
(live) unit tests, never here.
"""

from __future__ import annotations

import json
import os
import time
from typing import Any

import boto3
from botocore.config import Config as BotoConfig

_ec2_client = None
_ssm_client = None
_ssm_params_client = None
_s3_client = None
_sqs_client = None


def _ec2():
    global _ec2_client
    if _ec2_client is None:
        _ec2_client = boto3.client("ec2")
    return _ec2_client


def _ssm():
    global _ssm_client
    if _ssm_client is None:
        _ssm_client = boto3.client("ssm")
    return _ssm_client


def _ssm_params():
    # Same service as _ssm(); kept as a separate accessor purely for readability at
    # the call sites (parameter reads vs command channel).
    return _ssm()


def _s3():
    global _s3_client
    if _s3_client is None:
        # REGIONAL, virtual-hosted-style addressing is REQUIRED for the isolated
        # detonation host. The host has no internet and reaches S3 only through the
        # VPC S3 endpoint. A default client presigns the GLOBAL endpoint
        # (``<bucket>.s3.amazonaws.com``), whose public IPs the S3 gateway-endpoint
        # route does not carry from the isolated subnet -> the on-host curl TCP-times
        # out (verified live: 'Failed to connect to <bucket>.s3.amazonaws.com:443').
        # Pinning ``region_name`` + ``s3={addressing_style: virtual}`` presigns the
        # REGIONAL host (``<bucket>.s3.<region>.amazonaws.com``), which the VPC S3
        # endpoint intercepts, so the isolated host can fetch its artifact.
        region = os.environ.get("AWS_REGION") or os.environ.get(
            "AWS_DEFAULT_REGION", "us-east-1"
        )
        _s3_client = boto3.client(
            "s3",
            region_name=region,
            config=BotoConfig(s3={"addressing_style": "virtual"}),
        )
    return _s3_client


def _sqs():
    global _sqs_client
    if _sqs_client is None:
        _sqs_client = boto3.client("sqs")
    return _sqs_client


# --- Detonation coordinates (read from the Story 2.0 SSM parameters) ---------


def get_ssm_parameter(name: str) -> str:
    """Read a single SSM StringParameter value (the 2.0-published coordinates)."""
    resp = _ssm_params().get_parameter(Name=name)
    return resp["Parameter"]["Value"]


# --- Ephemeral host lifecycle (ec2:RunInstances via the 2.0 launch template) -


def run_instance_from_template(
    *,
    launch_template_id: str,
    subnet_id: str,
    tags: dict[str, str],
    launch_template_version: str = "$Latest",
) -> dict[str, Any]:
    """Launch ONE ephemeral detonation host from the 2.0 launch template.

    Uses ``ec2:RunInstances`` against the launch template (NOT CloudFormation per
    run). The template already carries the isolated SG, no-key-pair, IMDSv2, the
    encrypted root volume, the 5-min-TTL UserData AND the detonation instance
    profile (CDK's ``LaunchTemplate({ role })`` bakes an instance profile into the
    template). We therefore do NOT pass ``IamInstanceProfile`` here — overriding it
    with a separately-derived ARN is both unnecessary and error-prone (a CDK role's
    auto-created instance profile has a different name than the role). We only pin
    the isolated SUBNET, force no public IP, set instance-initiated-shutdown =
    terminate (so the hard TTL's ``shutdown -h`` tears the host down), and tag it
    for correlation/teardown.

    Returns {'instance_id', 'instance_type', 'launch_template_version'}.
    """
    resp = _ec2().run_instances(
        LaunchTemplate={
            "LaunchTemplateId": launch_template_id,
            "Version": launch_template_version,
        },
        MinCount=1,
        MaxCount=1,
        # Belt-and-suspenders on top of the template + isolated subnet.
        InstanceInitiatedShutdownBehavior="terminate",
        NetworkInterfaces=[
            {
                "DeviceIndex": 0,
                "SubnetId": subnet_id,
                "AssociatePublicIpAddress": False,
            }
        ],
        # NOTE: no IamInstanceProfile — the launch template already carries it.
        TagSpecifications=[
            {
                "ResourceType": "instance",
                "Tags": [{"Key": k, "Value": v} for k, v in tags.items()],
            }
        ],
    )
    instance = resp["Instances"][0]
    return {
        "instance_id": instance["InstanceId"],
        "instance_type": instance.get("InstanceType", ""),
        "launch_template_version": launch_template_version,
    }


def wait_for_ssm_online(instance_id: str, timeout_s: int, poll_s: int = 5) -> bool:
    """Poll until the SSM agent on the instance reports Online, or timeout.

    Returns True iff the instance became SSM-managed within the budget. The host
    has NO SSH; SSM is the only command channel (RD-001), so this must be online
    before we can execute host-native.
    """
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        resp = _ssm().describe_instance_information(
            Filters=[{"Key": "InstanceIds", "Values": [instance_id]}]
        )
        infos = resp.get("InstanceInformationList", [])
        if infos and infos[0].get("PingStatus") == "Online":
            return True
        time.sleep(poll_s)
    return False


def send_command(instance_id: str, commands: list[str], exec_timeout_s: int) -> str:
    """Execute host-native via SSM AWS-RunShellScript (NO Docker, RD-001).

    Returns the SSM command id. The ``commands`` run directly on the ephemeral
    host's shell — this is the host-native execution the whole story exists to do.
    """
    resp = _ssm().send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={
            "commands": commands,
            "executionTimeout": [str(exec_timeout_s)],
        },
    )
    return resp["Command"]["CommandId"]


def poll_command(
    command_id: str, instance_id: str, timeout_s: int, poll_s: int = 5
) -> dict[str, Any]:
    """Poll an SSM command invocation to a terminal status (or timeout).

    Returns {'status', 'exit_code', 'stdout', 'stderr'}. On timeout returns the last
    non-terminal status seen (the caller maps that to a timed_out outcome; the hard
    TTL tears the host down regardless).
    """
    terminal = {"Success", "Failed", "Cancelled", "TimedOut", "Undelivered", "Terminated"}
    deadline = time.monotonic() + timeout_s
    last: dict[str, Any] = {
        "status": "InProgress",
        "exit_code": None,
        "stdout": "",
        "stderr": "",
    }
    while time.monotonic() < deadline:
        try:
            inv = _ssm().get_command_invocation(
                CommandId=command_id, InstanceId=instance_id
            )
        except Exception:  # noqa: BLE001 - invocation may not be registered yet
            time.sleep(poll_s)
            continue
        last = {
            "status": inv.get("Status", "InProgress"),
            "exit_code": inv.get("ResponseCode"),
            "stdout": inv.get("StandardOutputContent", ""),
            "stderr": inv.get("StandardErrorContent", ""),
        }
        if last["status"] in terminal:
            return last
        time.sleep(poll_s)
    return last


def observe_teardown(instance_id: str, timeout_s: int, poll_s: int = 10) -> dict[str, Any]:
    """Observe whether the host reaches shutting-down / terminated within the budget.

    Returns {'observed': bool, 'state': <last state seen>}. False does NOT mean the
    host survived — the hard TTL's ``shutdown -h`` still fires independently; it
    means we did not wait long enough to witness it. An instance confirmed STILL
    running past its TTL is a SEV finding the caller records explicitly.
    """
    down_states = {"shutting-down", "terminated", "stopping", "stopped"}
    deadline = time.monotonic() + timeout_s
    last_state = "unknown"
    while time.monotonic() < deadline:
        resp = _ec2().describe_instances(InstanceIds=[instance_id])
        reservations = resp.get("Reservations", [])
        if reservations and reservations[0].get("Instances"):
            last_state = reservations[0]["Instances"][0]["State"]["Name"]
            if last_state in down_states:
                return {"observed": True, "state": last_state}
        time.sleep(poll_s)
    return {"observed": False, "state": last_state}


def terminate_instance(instance_id: str) -> None:
    """Best-effort explicit terminate (the hard TTL is the real backstop).

    The orchestrator calls this in a finally block so a host does not linger to its
    full TTL when a run finishes early. Never raises fatally — the TTL guarantees
    teardown even if this call fails.
    """
    try:
        _ec2().terminate_instances(InstanceIds=[instance_id])
    except Exception:  # noqa: BLE001, S110 - the hard TTL is the guaranteed backstop
        # Deliberately swallowed: the launch-template UserData `shutdown -h +N`
        # tears the host down regardless, so a failed explicit terminate is not
        # fatal and must not crash the lane. No logger here by design (seam layer).
        pass


# --- Forensic S3 (full log stays here) + Hub crossing ------------------------


def get_artifact_presigned_url(bucket: str, key: str, expires_s: int) -> str:
    """Presign a short-lived GET for the raw artifact so the isolated host can pull
    it over the S3 VPC gateway endpoint (the host has no other network path). The
    artifact + the URL never leave Forensic."""
    return _s3().generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_s,
    )


def put_output_log(bucket: str, key: str, document: dict[str, Any]) -> None:
    """Write the FULL command output log to Forensic S3 (runs/ prefix).

    RD-009: the full log may echo artifact content, so it stays in Forensic; only
    the bounded tails cross to the Hub. Written KMS-encrypted as inert JSON.
    """
    _s3().put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(document).encode("utf-8"),
        ContentType="application/json",
        ServerSideEncryption="aws:kms",
    )


def send_run_envelope(queue_url: str, envelope: dict[str, Any]) -> None:
    """Send the derived run-outcome envelope to the Hub ingest queue.

    Sixth envelope kind on the same one-directional Forensic -> Hub door; the Hub
    gate routes by envelope kind and applies the outcome to the tracking record.
    """
    _sqs().send_message(QueueUrl=queue_url, MessageBody=json.dumps(envelope))
