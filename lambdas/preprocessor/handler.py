"""ZTIE Story 1.2 — preprocessor Lambda handler (Forensic-side wiring).

Runs in the **Forensic** account, downstream of intake (Story 1.1). Triggered by
an S3 ``ObjectCreated`` event on the intake artifact bucket, it:

  1. Reads the object's user metadata (intake-id, sha256, claimed-content-type)
     and a bounded HEAD slice of the raw body — the read stays inside Forensic.
  2. Runs the PURE classifier (``classifier.classify``) over the actual bytes +
     the (untrusted) filename, producing a LABEL and the two independent signals.
  3. Emits a DERIVED, label-only classification envelope
     (``schemas/classification.contract.v1.json``) across the one-directional
     Forensic -> Hub boundary via the Hub-owned ingest SQS queue. The Hub
     validating gate enforces the contract and upserts the label onto the durable
     tracking record keyed by ``intake_id``.

Zero-trust invariants (RD-012 / RD-013):
  * The raw artifact body NEVER leaves Forensic — only the derived label crosses.
  * The envelope carries NO body / base64 / executable content and NO verdict /
    route / safety field — a classification is a LABEL only.
  * The label is integrity-bound to ``intake_id`` + ``sha256`` so the Hub can only
    attach it to the exact artifact it was computed over.

No mocks in the execution path: real S3 + SQS via the thin ``awsio`` layer. moto
is used only in the (live) unit tests.
"""

from __future__ import annotations

import datetime as _dt
import logging
import os
import urllib.parse
from typing import Any

import awsio
from classifier import classify
from rejector import reject
from router import route

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# --- Configuration (from environment; set by the CDK stack) -----------------

# Hub-owned ingest SQS queue (the one-directional Forensic -> Hub door). Reused
# from the 1.1R boundary — the same gate validates classification-update envelopes.
HUB_INGEST_QUEUE_URL = os.environ.get("HUB_INGEST_QUEUE_URL", "")
CONTRACT_VERSION = os.environ.get("CLASSIFICATION_CONTRACT_VERSION", "1.0")
# Story 1.3: the routing-decision envelope version (a third kind on the same gate).
ROUTING_CONTRACT_VERSION = os.environ.get("ROUTING_CONTRACT_VERSION", "1.0")
# Story 1.4: the safe-reject outcome envelope version (a fourth kind).
REJECT_CONTRACT_VERSION = os.environ.get("REJECT_CONTRACT_VERSION", "1.0")
# Story 2.1: the Forensic static-scan work queue. When routing names the
# static_analysis lane, the preprocessor enqueues a static-scan JOB here (an
# INTRA-FORENSIC hand-off, not a Hub crossing). Empty until the static-scan stack
# is deployed and this env var is wired — the emit is skipped (logged) when unset,
# so the classification/routing path still works before 2.1's infra lands.
STATIC_SCAN_QUEUE_URL = os.environ.get("STATIC_SCAN_QUEUE_URL", "")
# The lane id (must match the routing contract's lane enum) that triggers a job.
_STATIC_ANALYSIS_LANE = "static_analysis"
# Story 2.3: the Forensic detonation work queue. When routing names the
# dynamic_detonation lane, the preprocessor enqueues a detonation JOB here (an
# INTRA-FORENSIC hand-off, not a Hub crossing). Empty until the detonation stack
# is deployed and this env var is wired — the emit is skipped (logged) when unset,
# so the classification/routing path still works before 2.3's infra lands.
DETONATION_QUEUE_URL = os.environ.get("DETONATION_QUEUE_URL", "")
# The lane id (must match the routing contract's lane enum) that triggers a
# detonation job.
_DYNAMIC_DETONATION_LANE = "dynamic_detonation"

# Only the head slice of the artifact is inspected; matches the classifier bound.
HEAD_BYTES = int(os.environ.get("CLASSIFY_HEAD_BYTES", str(64 * 1024)))

# The S3 object user-metadata keys stamped by the intake handler (1.1). boto3
# lower-cases metadata keys; the intake handler wrote hyphenated keys.
_MD_INTAKE_ID = "intake-id"
_MD_SHA256 = "sha256"


class PreprocessorError(Exception):
    """A non-retryable classification failure (bad event / missing metadata)."""


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _iter_s3_records(event: dict[str, Any]):
    """Yield (bucket, key) for each S3 ObjectCreated record in the event."""
    for record in event.get("Records", []) or []:
        s3 = record.get("s3") or {}
        bucket = (s3.get("bucket") or {}).get("name")
        raw_key = (s3.get("object") or {}).get("key")
        if not bucket or not raw_key:
            continue
        # S3 event keys are URL-encoded (spaces as '+', etc.).
        key = urllib.parse.unquote_plus(raw_key)
        yield bucket, key


def _filename_from_key(key: str) -> str:
    """intake/<intake_id>/<filename> -> <filename> (fall back to the last seg)."""
    return key.rsplit("/", 1)[-1]


def _build_envelope(
    *, intake_id: str, sha256: str, classification: dict[str, Any]
) -> dict[str, Any]:
    """Build the derived classification envelope (label only, integrity-bound)."""
    return {
        "contract_version": CONTRACT_VERSION,
        "intake_id": intake_id,
        "sha256": sha256,
        "classified_at": _now_iso(),
        "classification": classification,
    }


def _build_routing_envelope(
    *, intake_id: str, sha256: str, routing: dict[str, Any]
) -> dict[str, Any]:
    """Build the derived routing-decision envelope (Story 1.3; plan-of-controls
    only, integrity-bound). Carries no verdict / forward field — routing says
    only which downstream lane(s) apply."""
    return {
        "contract_version": ROUTING_CONTRACT_VERSION,
        "intake_id": intake_id,
        "sha256": sha256,
        "routed_at": _now_iso(),
        "routing": routing,
    }


def _build_reject_envelope(
    *, intake_id: str, sha256: str, rejection: dict[str, Any]
) -> dict[str, Any]:
    """Build the derived safe-reject outcome envelope (Story 1.4; terminal
    processing outcome, integrity-bound). Carries no verdict / forward field —
    a safe-reject says only that the artifact was refused cleanly."""
    return {
        "contract_version": REJECT_CONTRACT_VERSION,
        "intake_id": intake_id,
        "sha256": sha256,
        "rejected_at": _now_iso(),
        "rejection": rejection,
    }


def _process_object(bucket: str, key: str) -> dict[str, Any]:
    """Classify one Forensic S3 artifact and emit the label envelope. Pure work
    (the classifier) is isolated; only the reads/sends touch AWS."""
    head = awsio.head_object_metadata(bucket, key)
    metadata = head["metadata"]

    intake_id = metadata.get(_MD_INTAKE_ID)
    sha256 = metadata.get(_MD_SHA256)
    if not intake_id or not sha256:
        # The intake handler always stamps these; their absence means this object
        # did not come through intake. Do not fabricate an identity — skip loudly.
        raise PreprocessorError(
            f"object s3://{bucket}/{key} missing intake-id/sha256 metadata"
        )

    filename = _filename_from_key(key)
    body_head = awsio.get_object_head_bytes(bucket, key, HEAD_BYTES)

    # PURE classification — no AWS, fully offline-testable.
    classification = classify(filename, body_head)

    envelope = _build_envelope(
        intake_id=intake_id, sha256=sha256, classification=classification
    )
    awsio.send_classification_envelope(HUB_INGEST_QUEUE_URL, envelope)

    logger.info(
        "classified intake_id=%s class=%s basis=%s agree=%s ext=%s content=%s",
        intake_id,
        classification["artifact_class"],
        classification["basis"],
        classification["signals_agree"],
        classification["extension_signal"]["artifact_class"],
        classification["content_signal"]["artifact_class"],
    )

    # PURE routing (Story 1.3) — a plan of which controls apply, derived from the
    # class label. Emitted as a SECOND envelope kind to the SAME Hub gate. The raw
    # body still never leaves Forensic; only the derived decision crosses.
    routing = route(classification["artifact_class"])
    routing_envelope = _build_routing_envelope(
        intake_id=intake_id, sha256=sha256, routing=routing
    )
    awsio.send_routing_envelope(HUB_INGEST_QUEUE_URL, routing_envelope)

    logger.info(
        "routed intake_id=%s class=%s lanes=%s routable=%s basis=%s",
        intake_id,
        routing["artifact_class"],
        routing["lanes"],
        routing["routable"],
        routing["basis"],
    )

    # Story 2.1: if routing names the static_analysis lane, enqueue a static-scan
    # JOB onto the Forensic static-scan work queue. This is the fork target for the
    # non-executing static lane. It is an INTRA-FORENSIC hand-off (the job carries
    # the artifact's Forensic S3 coordinates so the static-scan Lambda can read the
    # raw body, which stays in Forensic) — NOT a Forensic -> Hub crossing.
    if _STATIC_ANALYSIS_LANE in routing["lanes"]:
        if STATIC_SCAN_QUEUE_URL:
            static_job = {
                "kind": "static_scan_job",
                "intake_id": intake_id,
                "sha256": sha256,
                "artifact_class": routing["artifact_class"],
                "bucket": bucket,
                "key": key,
            }
            awsio.send_static_scan_job(STATIC_SCAN_QUEUE_URL, static_job)
            logger.info(
                "enqueued static-scan job intake_id=%s class=%s key=s3://%s/%s",
                intake_id,
                routing["artifact_class"],
                bucket,
                key,
            )
        else:
            # Infra not yet wired (STATIC_SCAN_QUEUE_URL unset). Do not fail the
            # classification/routing path — just record that the static lane was
            # named but no work queue is configured.
            logger.warning(
                "static_analysis lane named but STATIC_SCAN_QUEUE_URL unset; "
                "skipping static-scan enqueue for intake_id=%s",
                intake_id,
            )

    # Story 2.3: if routing names the dynamic_detonation lane, enqueue a detonation
    # JOB onto the Forensic detonation work queue. This is the fork target for the
    # DYNAMIC lane — where the artifact is actually EXECUTED (host-native, on an
    # ephemeral EC2, inside the Forensic isolated VPC). Like the static enqueue it
    # is an INTRA-FORENSIC hand-off (the job carries only the artifact's Forensic S3
    # coordinates so the detonation Lambda can pull the raw body, which stays in
    # Forensic) — NOT a Forensic -> Hub crossing. The detonation lane later crosses
    # a bounded, verdict-free run OUTCOME to the Hub via the RD-013 gate.
    if _DYNAMIC_DETONATION_LANE in routing["lanes"]:
        if DETONATION_QUEUE_URL:
            detonation_job = {
                "kind": "detonation_job",
                "intake_id": intake_id,
                "sha256": sha256,
                "artifact_class": routing["artifact_class"],
                "bucket": bucket,
                "key": key,
            }
            awsio.send_detonation_job(DETONATION_QUEUE_URL, detonation_job)
            logger.info(
                "enqueued detonation job intake_id=%s class=%s key=s3://%s/%s",
                intake_id,
                routing["artifact_class"],
                bucket,
                key,
            )
        else:
            # Infra not yet wired (DETONATION_QUEUE_URL unset). Do not fail the
            # classification/routing path — just record that the dynamic lane was
            # named but no work queue is configured.
            logger.warning(
                "dynamic_detonation lane named but DETONATION_QUEUE_URL unset; "
                "skipping detonation enqueue for intake_id=%s",
                intake_id,
            )

    # Story 1.4: if the artifact is unroutable, emit a safe-reject terminal
    # outcome. This is the pipeline's fail-safe — an artifact that cannot enter
    # any Phase-2 lane is refused cleanly, recorded, and never dropped.
    if not routing["routable"]:
        rejection = reject(routing)
        if rejection is not None:
            reject_envelope = _build_reject_envelope(
                intake_id=intake_id, sha256=sha256, rejection=rejection
            )
            awsio.send_reject_envelope(HUB_INGEST_QUEUE_URL, reject_envelope)
            logger.info(
                "safe-rejected intake_id=%s outcome=%s reason=%s class=%s",
                intake_id,
                rejection["pipeline_outcome"],
                rejection["reason"],
                rejection["artifact_class"],
            )

    return envelope


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """S3-triggered entry point. Classifies each newly created intake object.

    Returns partial-batch failures so a single failing object is retried/DLQ'd
    without reprocessing the ones that already succeeded.
    """
    if not HUB_INGEST_QUEUE_URL:
        logger.error("Misconfigured: HUB_INGEST_QUEUE_URL not set")
        raise RuntimeError("Preprocessor is misconfigured")

    batch_item_failures: list[dict[str, str]] = []
    processed = 0

    for bucket, key in _iter_s3_records(event):
        try:
            _process_object(bucket, key)
            processed += 1
        except PreprocessorError as exc:
            # Non-retryable: a malformed/foreign object. Log and skip (do not fail
            # the batch — retrying will never fix a missing-identity object).
            logger.warning("skipping object: %s", exc)
        except Exception:
            # Genuinely unprocessable (transient AWS error). Report so it retries.
            logger.exception("unprocessable object s3://%s/%s (will retry)", bucket, key)
            batch_item_failures.append({"itemIdentifier": f"{bucket}/{key}"})

    logger.info("preprocessor processed=%d failures=%d", processed, len(batch_item_failures))
    return {"batchItemFailures": batch_item_failures}
