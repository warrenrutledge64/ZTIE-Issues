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
# Story 2.6 (RD-029): the AWS Step Functions STANDARD state machine that forks the
# artifact into BOTH inspection lanes CONCURRENTLY (a Parallel state) and joins on
# both-complete via the collector Lambda. When this is set, the preprocessor starts
# ONE execution (the concurrent fan-out) INSTEAD of the two independent enqueues.
# Empty until the orchestration stack is deployed and this env var is wired — the
# preprocessor then falls back to the pre-2.6 independent enqueues (backward-safe),
# so the classification/routing path never breaks.
ORCHESTRATION_STATE_MACHINE_ARN = os.environ.get("ORCHESTRATION_STATE_MACHINE_ARN", "")
# The lanes the concurrent fork drives. The orchestration is started whenever
# routing names AT LEAST ONE of these (the Parallel state records a not-run lane as
# not_applicable in the collected record).
_PARALLEL_LANES = (_STATIC_ANALYSIS_LANE, _DYNAMIC_DETONATION_LANE)

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


def _static_scan_job(
    *, intake_id: str, sha256: str, artifact_class: str, bucket: str, key: str
) -> dict[str, Any]:
    """Build the static-scan JOB payload (S3 coords only; raw body stays in
    Forensic). This is the static branch's input to the fork — the same shape the
    pre-2.6 static-scan work queue consumed (Story 2.1)."""
    return {
        "kind": "static_scan_job",
        "intake_id": intake_id,
        "sha256": sha256,
        "artifact_class": artifact_class,
        "bucket": bucket,
        "key": key,
    }


def _detonation_job(
    *, intake_id: str, sha256: str, artifact_class: str, bucket: str, key: str
) -> dict[str, Any]:
    """Build the detonation JOB payload (S3 coords only; raw body stays in
    Forensic). This is the dynamic branch's input to the fork — the same shape the
    pre-2.6 detonation work queue consumed (Story 2.3)."""
    return {
        "kind": "detonation_job",
        "intake_id": intake_id,
        "sha256": sha256,
        "artifact_class": artifact_class,
        "bucket": bucket,
        "key": key,
    }


def _execution_name(intake_id: str) -> str:
    """A DETERMINISTIC Step Functions execution name derived from intake_id, so SQS
    at-least-once redelivery of the same S3 event cannot start a duplicate fork
    (Step Functions rejects a second StartExecution with the same name). Bounded to
    the 80-char name limit and the allowed character set."""
    # intake_id is a UUIDv4 (hyphenated hex) — already name-safe and well under 80.
    return f"ztie-{intake_id}"[:80]


def _start_orchestration(
    *, intake_id: str, sha256: str, routing: dict[str, Any], bucket: str, key: str
) -> None:
    """Start ONE Step Functions execution (the Story 2.6 CONCURRENT FORK, RD-029).

    Builds the branch inputs (the SAME S3-coord job shapes the lanes already
    consume) + a small fork context (intake_id / sha256 / the routing-expected
    lanes) the collector join step reads, then starts the state machine with a
    deterministic, idempotent execution name. A seam failure is RECORDED, never
    crashes the classification/routing pipeline (the raw body stays in Forensic
    regardless).
    """
    lanes = routing["lanes"]
    orchestration_input = {
        "context": {
            "intake_id": intake_id,
            "sha256": sha256,
            # The lanes routing expects — the collector measures the join against
            # this so a lane routing named but that never reported is visible.
            "lanes_expected": [lane for lane in _PARALLEL_LANES if lane in lanes],
        },
        # The two branch inputs (S3 coords only). The Parallel state hands each to
        # its lane; a lane routing did not name is skipped by the state machine and
        # recorded not_applicable in the collected record.
        "static_job": _static_scan_job(
            intake_id=intake_id,
            sha256=sha256,
            artifact_class=routing["artifact_class"],
            bucket=bucket,
            key=key,
        ),
        "detonation_job": _detonation_job(
            intake_id=intake_id,
            sha256=sha256,
            artifact_class=routing["artifact_class"],
            bucket=bucket,
            key=key,
        ),
    }
    try:
        execution_arn = awsio.start_inspection_orchestration(
            ORCHESTRATION_STATE_MACHINE_ARN,
            _execution_name(intake_id),
            orchestration_input,
        )
        logger.info(
            "started inspection orchestration intake_id=%s lanes=%s execution=%s",
            intake_id,
            orchestration_input["context"]["lanes_expected"],
            execution_arn,
        )
    except Exception as exc:  # a seam failure is recorded, never fatal
        # An already-running/completed execution with the same deterministic name
        # (ExecutionAlreadyExists) is the idempotent no-op we WANT under SQS
        # at-least-once redelivery; any other seam error is logged but must not
        # crash the classification/routing path.
        if exc.__class__.__name__ in (
            "ExecutionAlreadyExists",
            "ExecutionLimitExceeded",
        ) or "ExecutionAlreadyExists" in str(exc):
            logger.info(
                "inspection orchestration already started for intake_id=%s "
                "(idempotent no-op)",
                intake_id,
            )
        else:
            logger.exception(
                "failed to start inspection orchestration for intake_id=%s; "
                "recorded, not fatal",
                intake_id,
            )


def _enqueue_lanes_independently(
    *, intake_id: str, sha256: str, routing: dict[str, Any], bucket: str, key: str
) -> None:
    """Pre-2.6 fallback: fire the two INDEPENDENT intra-Forensic enqueues (Story 2.1
    static + Story 2.3 detonation) when the orchestration state machine is not yet
    wired. Preserves the exact backward-safe unset-queue-url paths so the
    classification/routing path never breaks before the infra lands."""
    if _STATIC_ANALYSIS_LANE in routing["lanes"]:
        if STATIC_SCAN_QUEUE_URL:
            awsio.send_static_scan_job(
                STATIC_SCAN_QUEUE_URL,
                _static_scan_job(
                    intake_id=intake_id,
                    sha256=sha256,
                    artifact_class=routing["artifact_class"],
                    bucket=bucket,
                    key=key,
                ),
            )
            logger.info(
                "enqueued static-scan job intake_id=%s class=%s key=s3://%s/%s",
                intake_id,
                routing["artifact_class"],
                bucket,
                key,
            )
        else:
            logger.warning(
                "static_analysis lane named but STATIC_SCAN_QUEUE_URL unset; "
                "skipping static-scan enqueue for intake_id=%s",
                intake_id,
            )

    if _DYNAMIC_DETONATION_LANE in routing["lanes"]:
        if DETONATION_QUEUE_URL:
            awsio.send_detonation_job(
                DETONATION_QUEUE_URL,
                _detonation_job(
                    intake_id=intake_id,
                    sha256=sha256,
                    artifact_class=routing["artifact_class"],
                    bucket=bucket,
                    key=key,
                ),
            )
            logger.info(
                "enqueued detonation job intake_id=%s class=%s key=s3://%s/%s",
                intake_id,
                routing["artifact_class"],
                bucket,
                key,
            )
        else:
            logger.warning(
                "dynamic_detonation lane named but DETONATION_QUEUE_URL unset; "
                "skipping detonation enqueue for intake_id=%s",
                intake_id,
            )


def _fork_inspection_lanes(
    *, intake_id: str, sha256: str, routing: dict[str, Any], bucket: str, key: str
) -> None:
    """Fork the routed artifact into the two Phase-2 inspection lanes (RD-002).

    Story 2.6 (RD-029): when the orchestration state machine is wired, start ONE
    concurrent fan-out execution (both lanes run in PARALLEL, joined on
    both-complete). Otherwise fall back to the pre-2.6 independent per-lane
    enqueues. The fork only runs when routing named at least one parallel lane.
    """
    named_lanes = [lane for lane in _PARALLEL_LANES if lane in routing["lanes"]]
    if not named_lanes:
        return

    if ORCHESTRATION_STATE_MACHINE_ARN:
        _start_orchestration(
            intake_id=intake_id, sha256=sha256, routing=routing, bucket=bucket, key=key
        )
    else:
        logger.info(
            "ORCHESTRATION_STATE_MACHINE_ARN unset; falling back to independent "
            "per-lane enqueues for intake_id=%s (pre-2.6 path)",
            intake_id,
        )
        _enqueue_lanes_independently(
            intake_id=intake_id, sha256=sha256, routing=routing, bucket=bucket, key=key
        )


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

    # Story 2.6 (RD-029): fork the routed artifact into the two Phase-2 inspection
    # lanes. When the orchestration state machine is wired, start ONE Step Functions
    # execution (a CONCURRENT fan-out that runs both lanes in parallel and joins on
    # both-complete). Otherwise fall back to the pre-2.6 independent per-lane
    # enqueues (backward-safe). Either way the fork targets are the SAME S3-coord
    # jobs; the raw body stays in Forensic (RD-009) — this is an INTRA-FORENSIC
    # hand-off, not a Hub crossing.
    _fork_inspection_lanes(
        intake_id=intake_id, sha256=sha256, routing=routing, bucket=bucket, key=key
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
