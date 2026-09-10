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
        # REGIONAL addressing is REQUIRED for the isolated detonation host. The host
        # has no internet and reaches S3 only through the VPC S3 endpoint, which
        # intercepts the REGIONAL host (``<bucket>.s3.<region>.amazonaws.com``) — NOT
        # the GLOBAL host (``<bucket>.s3.amazonaws.com``). A default client (and even
        # ``region_name`` + ``addressing_style=virtual``) still presigns the GLOBAL
        # host in us-east-1, because us-east-1 is boto3's legacy "global" region —
        # verified live: the on-host curl TCP-timed-out on
        # ``<bucket>.s3.amazonaws.com:443`` even after that config.
        #
        # The reliable fix in us-east-1 is BOTH:
        #   * ``us_east_1_regional_endpoint = "regional"`` so SDK endpoint resolution
        #     yields ``s3.us-east-1.amazonaws.com`` rather than the global host, AND
        #   * an explicit ``endpoint_url`` pinned to the regional host as a
        #     belt-and-suspenders so the PRESIGNED url always carries the regional
        #     host the VPC S3 endpoint serves.
        # SigV4 is ALSO required: us-east-1's legacy default signature version is
        # SigV2 (a presigned URL with `AWSAccessKeyId`/`Signature`/`Expires` query
        # params), which the regional virtual-hosted endpoint REJECTS with a plain
        # HTTP 400 (verified live 2026-09-05 — the fetch reached S3 fine over TLS
        # once the SG egress fix landed, but got a 400 because the URL was SigV2).
        # ``signature_version="s3v4"`` forces SigV4 (`X-Amz-Algorithm=AWS4-HMAC-...`
        # query params), which the regional endpoint accepts.
        region = os.environ.get("AWS_REGION") or os.environ.get(
            "AWS_DEFAULT_REGION", "us-east-1"
        )
        _s3_client = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=f"https://s3.{region}.amazonaws.com",
            config=BotoConfig(
                signature_version="s3v4",
                s3={
                    "addressing_style": "virtual",
                    "us_east_1_regional_endpoint": "regional",
                }
            ),
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


# --- Ephemeral interface VPC endpoints (RD-027, two-tier) --------------------
# ONLY the non-control-channel tier is ephemeral: logs / sqs / bedrock-runtime.
# The SSM control channel (ssm/ssmmessages/ec2messages) is ALWAYS-ON in the
# ZtieForensicInfraStack, because live validation showed a booting host cannot
# reliably reach a same-run-created SSM endpoint (detonation succeeded ~1/3 runs).
# The ephemeral tier is not needed at agent-registration time, so creating it
# per-run is safe and recovers most of the idle saving. Creating/deleting interface
# endpoints adds no IGW/NAT/0.0.0.0/0 route, so containment (RD-008) is unaffected.

# Tag every ephemeral endpoint so teardown + the orphan sweep find exactly the ones
# this lane owns (never touching the always-on control channel or anything else).
_EPHEMERAL_TAG_KEY = "ztie:ephemeral-endpoint"
_EPHEMERAL_TAG_VALUE = "detonation"


def create_interface_endpoints(
    *,
    vpc_id: str,
    subnet_id: str,
    security_group_id: str,
    service_names: list[str],
    intake_id: str,
) -> list[str]:
    """Create one interface VPC endpoint per service name (the ephemeral tier).

    private_dns_enabled=True so the host resolves the normal service host to the
    endpoint ENI. Each endpoint is tagged so teardown + the orphan sweep can find
    it. Returns the created endpoint ids; a partial failure is the caller's problem
    to clean up (it tears down every id returned so far in its finally block).

    RD-027 (live-hardened 2026-09-08): a create that immediately FOLLOWS the deletion
    of a same-service endpoint (i.e. after the start-of-run orphan sweep) can race the
    release of that endpoint's PRIVATE-DNS DOMAIN association. AWS reports this as a
    transient ``InvalidParameter``: ``private-dns-enabled cannot be set because there
    is already a conflicting DNS domain for <svc> in the VPC``. The endpoint RESOURCE
    being gone is NOT a sufficient signal that its DNS-domain association has been
    released, and there is no clean API to observe that release directly — so creation
    must TOLERATE the tail of the release window by retrying the conflicting-DNS-domain
    error with bounded backoff. This is verified-live behavior, not a guess.
    """
    endpoint_ids: list[str] = []
    for service_name in service_names:
        resp = _create_one_interface_endpoint(
            vpc_id=vpc_id,
            subnet_id=subnet_id,
            security_group_id=security_group_id,
            service_name=service_name,
            intake_id=intake_id,
        )
        endpoint_ids.append(resp["VpcEndpoint"]["VpcEndpointId"])
    return endpoint_ids


# A create that follows a same-service delete can transiently collide on the
# private-DNS domain until the deleted endpoint's DNS association is released.
# Retry only THAT specific transient condition, with bounded backoff.
_DNS_DOMAIN_CONFLICT_MARKER = "conflicting DNS domain"
CREATE_ENDPOINT_MAX_ATTEMPTS = int(
    os.environ.get("CREATE_ENDPOINT_MAX_ATTEMPTS", "6")
)
CREATE_ENDPOINT_RETRY_BASE_S = float(
    os.environ.get("CREATE_ENDPOINT_RETRY_BASE_S", "5")
)


def _is_dns_domain_conflict(exc: Exception) -> bool:
    """True iff ``exc`` is the transient 'conflicting DNS domain' create error.

    Matches on the AWS error message marker rather than only the error code, since
    'InvalidParameter' is a broad code and only this specific message is the transient
    DNS-association-release race we want to retry (never retry a genuine mis-config)."""
    return _DNS_DOMAIN_CONFLICT_MARKER in str(exc)


def _create_one_interface_endpoint(
    *,
    vpc_id: str,
    subnet_id: str,
    security_group_id: str,
    service_name: str,
    intake_id: str,
) -> dict[str, Any]:
    """Create a single tagged interface endpoint, retrying ONLY the transient
    conflicting-DNS-domain race (bounded backoff). Any other error propagates."""
    last_exc: Exception | None = None
    for attempt in range(CREATE_ENDPOINT_MAX_ATTEMPTS):
        try:
            return _ec2().create_vpc_endpoint(
                VpcEndpointType="Interface",
                VpcId=vpc_id,
                ServiceName=service_name,
                SubnetIds=[subnet_id],
                SecurityGroupIds=[security_group_id],
                PrivateDnsEnabled=True,
                TagSpecifications=[
                    {
                        "ResourceType": "vpc-endpoint",
                        "Tags": [
                            {"Key": _EPHEMERAL_TAG_KEY, "Value": _EPHEMERAL_TAG_VALUE},
                            {"Key": "Project", "Value": "ZTIE"},
                            {"Key": "IntakeId", "Value": intake_id},
                        ],
                    }
                ],
            )
        except Exception as exc:
            # Narrowed immediately: only the transient DNS-domain conflict is
            # retried; every other error re-raises unchanged.
            if not _is_dns_domain_conflict(exc):
                raise
            # Transient DNS-domain release race: back off and retry.
            last_exc = exc
            if attempt < CREATE_ENDPOINT_MAX_ATTEMPTS - 1:
                time.sleep(CREATE_ENDPOINT_RETRY_BASE_S * (attempt + 1))
    # Exhausted retries on the transient condition; surface the last error.
    raise last_exc if last_exc is not None else RuntimeError(
        "create_vpc_endpoint failed with no captured exception"
    )


def wait_for_endpoints_available(
    endpoint_ids: list[str], timeout_s: int, poll_s: int = 5
) -> bool:
    """Poll until every ephemeral endpoint reaches 'available', or timeout.

    These are the logs/sqs/bedrock-runtime endpoints — NOT the SSM control channel
    (which is always-on), so the host's SSM registration does not depend on them and
    a modest wait is sufficient. Returns True iff all are available within budget.
    """
    if not endpoint_ids:
        return True
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        resp = _ec2().describe_vpc_endpoints(VpcEndpointIds=endpoint_ids)
        states = [ep.get("State") for ep in resp.get("VpcEndpoints", [])]
        if states and all(s == "available" for s in states):
            return True
        if any(s == "failed" for s in states):
            return False
        time.sleep(poll_s)
    return False


def delete_interface_endpoints(endpoint_ids: list[str]) -> None:
    """Delete the ephemeral endpoints (best-effort, never raises fatally).

    Called in the orchestrator's finally block so the endpoints do not linger and
    bill after a run. A failure here is a COST risk, never a safety one (the host is
    torn down by its hard TTL and the SSM channel is always-on), and the start-of-run
    orphan sweep is the backstop — so this deliberately swallows errors.
    """
    if not endpoint_ids:
        return
    try:
        _ec2().delete_vpc_endpoints(VpcEndpointIds=endpoint_ids)
    except Exception:  # noqa: BLE001, S110 - orphan sweep is the backstop; never fatal
        pass


# After the swept endpoints' RESOURCES disappear, the private-DNS DOMAIN association
# they held can take a few more seconds to release. There is no API to observe that
# release directly, so we add a short settle once the resources are gone to give the
# association a head start before the run recreates a same-service endpoint. The
# create path additionally RETRIES the conflicting-DNS-domain error (see
# _create_one_interface_endpoint) as the authoritative backstop.
ENDPOINT_GONE_SETTLE_S = float(os.environ.get("ENDPOINT_GONE_SETTLE_S", "10"))


def wait_for_endpoints_gone(
    endpoint_ids: list[str], timeout_s: int, poll_s: int = 5
) -> bool:
    """Poll until the given endpoints no longer exist (or are 'deleted'), or timeout.

    Used by the orphan sweep so a freshly-deleted same-service endpoint is fully gone
    before a new one is created (avoids a lingering-DNS race). Returns True iff all
    are gone within the budget. Never raises (best-effort hygiene).

    NOTE (live-hardened 2026-09-08): an endpoint's RESOURCE vanishing is necessary but
    NOT sufficient for its private-DNS domain association to be released. Once the
    resources are observed gone we sleep ``ENDPOINT_GONE_SETTLE_S`` to let the DNS
    association release; the create path's conflicting-DNS-domain retry is the real
    backstop for the tail of that window."""
    if not endpoint_ids:
        return True
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            resp = _ec2().describe_vpc_endpoints(VpcEndpointIds=endpoint_ids)
        except Exception:  # noqa: BLE001 - NotFound => gone
            time.sleep(ENDPOINT_GONE_SETTLE_S)
            return True
        endpoints = resp.get("VpcEndpoints", [])
        # An entry still in 'deleting' is NOT gone yet (keep waiting). Only when
        # nothing is left in any state (empty) OR everything is 'deleted' are the
        # resources gone; then settle for the DNS-association release.
        not_gone = [ep for ep in endpoints if ep.get("State") != "deleted"]
        if not not_gone:
            time.sleep(ENDPOINT_GONE_SETTLE_S)
            return True
        time.sleep(poll_s)
    return False


def sweep_orphaned_endpoints(vpc_id: str, drain_timeout_s: int = 120) -> list[str]:
    """Delete any leftover ZTIE ephemeral endpoints from a prior crashed run.

    Backstop for the one failure mode the ephemeral tier introduces: if a previous
    detonation died before its finally-teardown ran, its endpoints would linger and
    bill. Every detonation sweeps first, so idle cost cannot accumulate beyond one
    crashed run's worth. Scoped to this VPC + the ZTIE ephemeral tag, so it can never
    delete the always-on control channel or any non-ZTIE endpoint. After issuing the
    delete, WAITS for the swept endpoints to fully disappear (bounded by
    ``drain_timeout_s``) before returning, so the caller does not create a new
    same-service endpoint while the old one is still 'deleting'. Never raises fatally.
    """
    try:
        resp = _ec2().describe_vpc_endpoints(
            Filters=[
                {"Name": "vpc-id", "Values": [vpc_id]},
                {"Name": f"tag:{_EPHEMERAL_TAG_KEY}", "Values": [_EPHEMERAL_TAG_VALUE]},
            ]
        )
        stale = [
            ep["VpcEndpointId"]
            for ep in resp.get("VpcEndpoints", [])
            if ep.get("State") in ("available", "pendingAcceptance", "pending", "failed")
        ]
        if stale:
            _ec2().delete_vpc_endpoints(VpcEndpointIds=stale)
            wait_for_endpoints_gone(stale, timeout_s=drain_timeout_s)
        return stale
    except Exception:  # noqa: BLE001 - the sweep is best-effort hygiene, never fatal
        return []


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


def put_trace(bucket: str, key: str, trace_text: str) -> None:
    """Write the FULL behavioral trace to Forensic S3 (Story 2.4, traces/ prefix).

    RD-009: the full host trace (strace output) may echo artifact content / paths,
    so it stays in Forensic; only the bounded, derived behavioral SUMMARY crosses to
    the Hub. Written KMS-encrypted as inert text. Same delivery mechanism as the
    2.3 run log (the trace arrives in the SSM command output; the Lambda persists
    it here) — no on-host S3 PUT / presign is introduced.
    """
    _s3().put_object(
        Bucket=bucket,
        Key=key,
        Body=trace_text.encode("utf-8"),
        ContentType="text/plain; charset=utf-8",
        ServerSideEncryption="aws:kms",
    )


def send_run_envelope(queue_url: str, envelope: dict[str, Any]) -> None:
    """Send the derived run-outcome envelope to the Hub ingest queue.

    Sixth envelope kind on the same one-directional Forensic -> Hub door; the Hub
    gate routes by envelope kind and applies the outcome to the tracking record.
    """
    _sqs().send_message(QueueUrl=queue_url, MessageBody=json.dumps(envelope))


def send_behavior_envelope(queue_url: str, envelope: dict[str, Any]) -> None:
    """Send the derived behavioral-telemetry envelope to the Hub ingest queue.

    Eighth envelope kind (Story 2.4) on the SAME one-directional Forensic -> Hub
    door; the Hub gate routes by the unique ``behavior`` discriminator and applies
    the bounded, verdict-free telemetry summary to the tracking record.
    """
    _sqs().send_message(QueueUrl=queue_url, MessageBody=json.dumps(envelope))
