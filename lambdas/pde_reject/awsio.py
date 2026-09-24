"""ZTIE Story 4.7 (RD-047, per RD-048/RD-049) — thin AWS I/O seam for the destroyer.

ALL boto3 lives HERE so the gate + envelope logic (``reject.py``) + the verify library
(``verify.py`` / ``canonical.py`` / ``signature.py``) stay pure and offline-unit-
testable (the proven pure-logic + thin-seam pattern; the sibling of 4.6
``pde_handoff/awsio.py``, inverted from ACCEPT-push to REJECT-destroy).

This Lambda runs in the FORENSIC account (360999005254) — the blast zone. **Trust
model (RD-048):** there is NO cross-account read of the Hub. The Hub HANDS the
Forensic destroyer a signed ``decision.token.v1`` (in the invoke payload now; a
one-directional Hub->Forensic delivery later, Story 4.4) and the destroyer VERIFIES it
OFFLINE against the Hub's embedded public key — so this seam does NOT touch DynamoDB
and holds NO Hub read grant. Its operations, each least-privilege:
  1. ``compute_artifact_sha256_and_size`` — stream the raw artifact from the FORENSIC
     artifact bucket (in-account ``s3:GetObject``) and recompute its sha256 for the
     token's SI-7 / artifact-binding check. The raw body stays in Forensic.
  2. ``destroy_intake_prefixes`` — delete ALL S3 object VERSIONS *and* DELETE-MARKERS
     under the intake's Forensic prefixes (``intake/<id>/`` + the derived
     ``findings/<id>/`` ``runs/<id>/`` ``traces/<id>/``). The bucket is VERSIONED, so
     a plain delete leaves versions behind (the OD-001 lesson) — every version + marker
     is deleted. Returns the total count deleted + the prefixes cleared.
  3. ``find_running_chamber`` / ``terminate_chamber`` — find any live ephemeral
     detonation host for the intake (tagged ``IntakeId=<id>`` + ``Ephemeral=true`` by
     the Story-2.3 lane) in a non-terminated state and terminate it explicitly (not
     waiting for the 5-min hard TTL). ``describe`` is scoped by the ZTIE tags.
  4. ``send_disposition_envelope`` — cross the bounded, verdict-free outcome to the Hub
     via EXACTLY ``sqs:SendMessage`` on EXACTLY the one Hub ingest queue (RD-013 door).

There is NO ``bedrock`` client, NO ``dynamodb`` client, and NO read of any Hub store
(RD-048/RD-049). There is NO write to any Hub DATA store (only the SQS send). Nothing
raw ever leaves Forensic; only the bounded outcome crosses.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import boto3

# Reused across warm invocations.
_s3_client = None
_ec2_client = None
_sqs_client = None

# Bounded streaming read size for the sha256 recompute (never buffer the whole body).
_HASH_CHUNK_BYTES = 1024 * 1024

# S3 DeleteObjects hard limit per request (AWS caps a batch at 1000 keys).
_DELETE_BATCH = 1000

# The Story-2.3 detonation lane tags every ephemeral host with these tags (see
# lambdas/detonation/handler.py run_instance_from_template tags). 4.7 finds the
# chamber for an intake by IntakeId + the Ephemeral marker, so it can never terminate
# a non-ZTIE / non-ephemeral instance.
_CHAMBER_EPHEMERAL_TAG_KEY = "Ephemeral"
_CHAMBER_EPHEMERAL_TAG_VALUE = "true"
_CHAMBER_INTAKE_TAG_KEY = "IntakeId"
# Instance states that mean the host is NOT already gone (so a terminate is meaningful).
_CHAMBER_LIVE_STATES = ("pending", "running", "stopping", "stopped")


def _s3():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client("s3")
    return _s3_client


def _ec2():
    global _ec2_client
    if _ec2_client is None:
        _ec2_client = boto3.client("ec2")
    return _ec2_client


def _sqs():
    global _sqs_client
    if _sqs_client is None:
        _sqs_client = boto3.client("sqs")
    return _sqs_client


def compute_artifact_sha256_and_size(bucket: str, key: str) -> tuple[str, int]:
    """Stream the raw artifact from the Forensic artifact bucket and return its
    (lowercase hex sha256, size in bytes). Streaming (never buffers the whole body).
    In-account read; the raw body stays in Forensic. Used to bind the presented
    ``rejected`` token to THESE exact bytes (SI-7) before any destroy."""
    obj = _s3().get_object(Bucket=bucket, Key=key)
    body = obj["Body"]
    hasher = hashlib.sha256()
    size = 0
    try:
        for chunk in body.iter_chunks(chunk_size=_HASH_CHUNK_BYTES):
            if not chunk:
                continue
            hasher.update(chunk)
            size += len(chunk)
    finally:
        body.close()
    return hasher.hexdigest(), size


def _delete_all_versions_under_prefix(bucket: str, prefix: str) -> int:
    """Delete EVERY object version AND delete-marker under ``prefix`` in a VERSIONED
    bucket. Returns the count of versions + markers deleted.

    A plain ``delete_object`` / ``s3 rm --recursive`` on a versioned bucket only adds
    a delete-marker and LEAVES the prior versions (the OD-001 lesson) — so a genuine
    destroy must enumerate ``list_object_versions`` ``Versions[]`` AND
    ``DeleteMarkers[]`` and delete each (Key, VersionId). Paginated; batched at the
    AWS 1000-key cap.
    """
    deleted = 0
    paginator = _s3().get_paginator("list_object_versions")
    batch: list[dict[str, str]] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for entry in (page.get("Versions") or []) + (page.get("DeleteMarkers") or []):
            key = entry.get("Key")
            version_id = entry.get("VersionId")
            if not key or not version_id:
                continue
            batch.append({"Key": key, "VersionId": version_id})
            if len(batch) >= _DELETE_BATCH:
                deleted += _flush_delete_batch(bucket, batch)
                batch = []
    if batch:
        deleted += _flush_delete_batch(bucket, batch)
    return deleted


def _flush_delete_batch(bucket: str, batch: list[dict[str, str]]) -> int:
    """Issue one bounded DeleteObjects call for a batch of (Key, VersionId). Returns
    the number actually deleted (from the response ``Deleted`` list)."""
    if not batch:
        return 0
    resp = _s3().delete_objects(
        Bucket=bucket,
        Delete={"Objects": batch, "Quiet": True},
    )
    errors = resp.get("Errors") or []
    if errors:
        # A destroy that could not fully complete is a real failure — surface it so
        # the caller records a fail-closed error, never a false "destroyed".
        first = errors[0]
        raise RuntimeError(
            f"S3 delete failed for {first.get('Key')!r}: "
            f"{first.get('Code')} {first.get('Message')}"
        )
    # DeleteObjects returns the deleted keys only when not Quiet; with Quiet=True the
    # response omits successfully-deleted entries, so count the batch we submitted
    # (any failure would have raised above).
    return len(batch)


def destroy_intake_prefixes(bucket: str, prefixes: list[str]) -> dict[str, Any]:
    """Destroy every object version + delete-marker under each of the intake's
    Forensic prefixes. Returns ``{"versions_deleted": int, "prefixes_cleared":
    [...]}``. The bucket is versioned, so this deletes ALL versions + markers (not a
    single tombstoning delete). Every prefix swept is recorded as cleared (a prefix
    that held 0 objects is still "cleared" — it was simply empty)."""
    total = 0
    cleared: list[str] = []
    for prefix in prefixes:
        total += _delete_all_versions_under_prefix(bucket, prefix)
        cleared.append(prefix)
    return {"versions_deleted": total, "prefixes_cleared": cleared}


def find_running_chamber(intake_id: str) -> str | None:
    """Find a LIVE ephemeral detonation host (chamber) for ``intake_id``, if any.

    Filters EC2 instances by the Story-2.3 lane's tags (``IntakeId=<id>`` +
    ``Ephemeral=true``) in a non-terminated state. Returns the instance id of a live
    chamber, or None if none is running (the common case — the 5-min hard TTL already
    reaped it). The tag filter guarantees this can never match a non-ZTIE /
    non-ephemeral instance.
    """
    resp = _ec2().describe_instances(
        Filters=[
            {"Name": f"tag:{_CHAMBER_INTAKE_TAG_KEY}", "Values": [intake_id]},
            {
                "Name": f"tag:{_CHAMBER_EPHEMERAL_TAG_KEY}",
                "Values": [_CHAMBER_EPHEMERAL_TAG_VALUE],
            },
            {"Name": "instance-state-name", "Values": list(_CHAMBER_LIVE_STATES)},
        ]
    )
    for reservation in resp.get("Reservations", []) or []:
        for instance in reservation.get("Instances", []) or []:
            instance_id = instance.get("InstanceId")
            if instance_id:
                return instance_id
    return None


def terminate_chamber(instance_id: str) -> None:
    """Terminate the live chamber explicitly (not waiting for the 5-min hard TTL).

    Raises on failure so the caller can record a fail-closed error rather than a false
    "terminated" — a REJECT means the chamber MUST be torn down, so a failed terminate
    is a real problem (the hard TTL is the backstop, but the disposition must be
    honest about what happened).
    """
    _ec2().terminate_instances(InstanceIds=[instance_id])


def send_disposition_envelope(queue_url: str, envelope: dict[str, Any]) -> None:
    """Send the derived disposition-outcome envelope to the Hub ingest queue.

    Eleventh envelope kind on the SAME one-directional Forensic -> Hub RD-013 door the
    other envelopes use; the Hub gate routes by the unique ``disposition``
    discriminator and applies the outcome to the tracking record (integrity-bound,
    never touching status/verdict). Nothing raw crosses (RD-009); only this bounded,
    verdict-free outcome.
    """
    _sqs().send_message(QueueUrl=queue_url, MessageBody=json.dumps(envelope))
