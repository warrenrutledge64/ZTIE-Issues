"""ZTIE Story 2.1 / 2.2 — static-scan lane Lambda handler (Forensic-side wiring).

Runs in the **Forensic** account. Triggered by the Forensic static-scan work queue
(the preprocessor enqueues a job when the routing decision names the
``static_analysis`` lane). For each job it:

  1. Reads the raw artifact from the Forensic artifact S3 bucket to local ephemeral
     storage, plus the object's ``intake-id`` / ``sha256`` metadata (the read + the
     file stay inside Forensic).
  2. Selects the class-appropriate tools (``toolplan``) and runs them NON-EXECUTING:
     the four static tools via ``scanners`` (subprocess parse only) PLUS the Story
     2.2 ``signatures`` engine (pure regex over the artifact bytes — known-bad
     patterns / secrets / IoCs). A tool/engine error is recorded per-tool and does
     NOT crash the lane.
  3. Normalizes every tool's output into ONE findings shape (``normalize``) and
     (Story 2.2) enriches each finding with the NIST 800-53 / ISO 27001 control(s)
     it implicates (``compliance`` — EVIDENCE, never a verdict). Writes the full
     findings document to Forensic S3 under ``findings/`` (RD-009 — it stays in
     Forensic), validated against its own bundled contract.
  4. Sends the derived, bounded SUMMARY envelope (fifth kind, v1.1) to the Hub
     ingest queue via the RD-013 gate — counts + per-tool status + a bounded
     compliance roll-up + a pointer back to the Forensic document, with NO finding
     text, NO mapping rationale, and NO verdict.

Zero-trust invariants (RD-009 / RD-013 / RD-001):
  * The raw artifact + full findings document NEVER leave Forensic — only the
    bounded summary crosses.
  * The summary carries NO verdict / route / forward / safety field — a scan is
    EVIDENCE. The verdict is Hub-side / human-gated (Phase 4).
  * NON-EXECUTING: the artifact is inspected, never executed.

No mocks in the execution path: real S3 + SQS + real scanners via the thin seams.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import os
import tempfile
import urllib.parse
from typing import Any

import awsio
import compliance
import scanners
import signatures
from normalize import (
    SIGNATURE_SCAN,
    build_findings_document,
    build_summary,
    build_tool_run,
)
from toolplan import tools_for_class

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# --- Configuration (from environment; set by the CDK stack) -----------------

HUB_INGEST_QUEUE_URL = os.environ.get("HUB_INGEST_QUEUE_URL", "")
SUMMARY_CONTRACT_VERSION = os.environ.get("SUMMARY_CONTRACT_VERSION", "1.1")
# Prefix under which the full findings document is written in the Forensic bucket.
FINDINGS_PREFIX = os.environ.get("FINDINGS_PREFIX", "findings/")
# Bundled cfn-guard ruleset (baseline AWS policy-as-code rules) shipped in the asset.
CFN_GUARD_RULES = os.environ.get(
    "CFN_GUARD_RULES", os.path.join(os.path.dirname(__file__), "guard-rules", "baseline.guard")
)
PER_TOOL_TIMEOUT_S = int(os.environ.get("PER_TOOL_TIMEOUT_S", "120"))

# The S3 object user-metadata keys stamped by the intake handler (1.1). boto3
# lower-cases metadata keys.
_MD_INTAKE_ID = "intake-id"
_MD_SHA256 = "sha256"


class StaticScanError(Exception):
    """A non-retryable job failure (bad message / missing artifact metadata)."""


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _run_signature_scan(artifact_path: str) -> scanners.ScanResult:
    """Run the Story 2.2 signature engine over the artifact bytes (NON-EXECUTING —
    pure regex over the file read as data). Reads the file HERE (the pure engine
    stays I/O-free); a read/scan failure is recorded as a per-tool error, never
    fatal. Returns a scanners.ScanResult so the handler treats it like any tool."""
    try:
        with open(artifact_path, "rb") as fh:
            data = fh.read(signatures._MAX_SCAN_BYTES + 1)
        filename = artifact_path.rsplit("/", 1)[-1]
        result = signatures.scan_bytes(data, filename)
        return scanners.ScanResult(
            tool=SIGNATURE_SCAN,
            status=result.status,
            findings=result.findings,
            error_reason=result.error_reason,
            duration_ms=result.duration_ms,
        )
    except Exception as exc:  # noqa: BLE001 - the signature engine must never crash the lane
        return scanners.ScanResult(
            tool=SIGNATURE_SCAN, status="error", error_reason=f"signature scan failed: {exc}"[:512]
        )


def _run_one_tool(tool: str, artifact_path: str) -> scanners.ScanResult:
    """Dispatch to the right scanner. Each scanner never raises (records error)."""
    if tool == scanners.CFN_LINT:
        return scanners.run_cfn_lint(artifact_path, PER_TOOL_TIMEOUT_S)
    if tool == scanners.BANDIT:
        return scanners.run_bandit(artifact_path, PER_TOOL_TIMEOUT_S)
    if tool == scanners.CHECKOV:
        return scanners.run_checkov(artifact_path, PER_TOOL_TIMEOUT_S)
    if tool == scanners.CFN_GUARD:
        return scanners.run_cfn_guard(artifact_path, CFN_GUARD_RULES, PER_TOOL_TIMEOUT_S)
    if tool == SIGNATURE_SCAN:
        return _run_signature_scan(artifact_path)
    # Unknown tool in the plan — record as error, never crash.
    return scanners.ScanResult(tool=tool, status="error", error_reason="unknown tool")


def _scan(artifact_path: str, artifact_class: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Run every class-appropriate tool. Returns (tool_runs, all_findings).

    A per-tool failure is captured in its tool_run (status=error) and the loop
    continues — the lane never crashes on a scanner error (DoD).
    """
    tools = tools_for_class(artifact_class)
    tool_runs: list[dict[str, Any]] = []
    all_findings: list[dict[str, Any]] = []
    for tool in tools:
        try:
            result = _run_one_tool(tool, artifact_path)
        except Exception as exc:  # defence in depth — the seam already guards this
            logger.exception("scanner %s crashed unexpectedly", tool)
            result = scanners.ScanResult(
                tool=tool, status="error", error_reason=f"unexpected: {exc}"[:512]
            )
        tool_runs.append(
            build_tool_run(
                result.tool,
                status=result.status,
                finding_count=len(result.findings),
                error_reason=result.error_reason,
                duration_ms=result.duration_ms,
            )
        )
        all_findings.extend(result.findings)
        logger.info(
            "tool=%s status=%s findings=%d duration_ms=%d",
            result.tool,
            result.status,
            len(result.findings),
            result.duration_ms,
        )
    # Story 2.2 — enrich every finding with its compliance-control mapping (NIST
    # 800-53 / ISO 27001) IN PLACE. EVIDENCE only: a mapping says which control a
    # finding implicates, never a verdict. Unmatched findings get an unmapped tag.
    compliance.enrich_findings(all_findings)
    return tool_runs, all_findings


def _is_direct_invoke(event: dict[str, Any]) -> bool:
    """A Story 2.6 fork branch invokes this lane DIRECTLY with a single job dict
    (the ``static_job`` the preprocessor built — bucket/key/intake_id/sha256/
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


def _process_job(job: dict[str, Any]) -> dict[str, Any]:
    """Scan one artifact end-to-end and cross the summary. Returns the summary."""
    bucket = job.get("bucket")
    raw_key = job.get("key")
    if not bucket or not raw_key:
        raise StaticScanError("job missing bucket/key")
    key = urllib.parse.unquote_plus(raw_key)

    head = awsio.head_object_metadata(bucket, key)
    metadata = head["metadata"]
    # Prefer the identity the job carries (from routing), fall back to S3 metadata.
    intake_id = job.get("intake_id") or metadata.get(_MD_INTAKE_ID)
    sha256 = job.get("sha256") or metadata.get(_MD_SHA256)
    artifact_class = job.get("artifact_class") or ""
    if not intake_id or not sha256:
        raise StaticScanError(f"object s3://{bucket}/{key} missing intake-id/sha256")

    with tempfile.TemporaryDirectory(prefix="ztie-static-") as tmp:
        # Preserve the filename so tools that key off extension behave correctly.
        filename = key.rsplit("/", 1)[-1] or "artifact"
        artifact_path = os.path.join(tmp, filename)
        awsio.download_artifact(bucket, key, artifact_path)

        tool_runs, all_findings = _scan(artifact_path, artifact_class)

    scanned_at = _now_iso()
    findings_key = f"{FINDINGS_PREFIX}{intake_id}/static-findings.json"

    document = build_findings_document(
        intake_id=intake_id,
        sha256=sha256,
        artifact_class=artifact_class,
        scanned_at=scanned_at,
        tool_runs=tool_runs,
        findings=all_findings,
    )
    # The full findings document stays in Forensic (RD-009).
    awsio.put_findings_document(bucket, findings_key, document)

    summary = build_summary(
        intake_id=intake_id,
        sha256=sha256,
        scanned_at=scanned_at,
        artifact_class=artifact_class,
        tool_runs=tool_runs,
        findings=all_findings,
        findings_s3_bucket=bucket,
        findings_s3_key=findings_key,
        contract_version=SUMMARY_CONTRACT_VERSION,
    )
    # Only the bounded summary crosses to the Hub (RD-013 gate).
    awsio.send_summary_envelope(HUB_INGEST_QUEUE_URL, summary)

    rollup = summary["scan"].get("compliance", {})
    logger.info(
        "static-scan complete intake_id=%s class=%s tools=%d findings=%d highest=%s "
        "mapped=%s unmapped=%s findings_key=s3://%s/%s",
        intake_id,
        artifact_class,
        len(tool_runs),
        summary["scan"]["total_findings"],
        summary["scan"]["highest_severity"],
        rollup.get("mapped_findings"),
        rollup.get("unmapped_findings"),
        bucket,
        findings_key,
    )
    return summary


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """SQS-triggered entry point. Scans each queued artifact.

    Returns partial-batch failures so a single failing job is retried/DLQ'd without
    reprocessing the ones that already succeeded. A malformed job (non-retryable) is
    logged and skipped; a transient AWS error is reported for retry.
    """
    if not HUB_INGEST_QUEUE_URL:
        logger.error("Misconfigured: HUB_INGEST_QUEUE_URL not set")
        raise RuntimeError("Static-scan lane is misconfigured")

    # Story 2.6: a Step Functions Parallel branch invokes this lane DIRECTLY with a
    # single job dict. Run the job and RETURN the derived summary envelope so the
    # branch's `outputPath: "$.Payload"` yields the real static-scan-summary shape
    # the collector rolls up — NOT the SQS partial-batch object (which would make a
    # branch that did no work read as a completed lane with an empty roll-up).
    if _is_direct_invoke(event):
        summary = _process_job(event)
        logger.info(
            "static-scan direct-invoke complete intake_id=%s (SFN fork branch)",
            summary.get("intake_id"),
        )
        return summary

    batch_item_failures: list[dict[str, str]] = []
    processed = 0

    for job, message_id in _iter_jobs(event):
        if not isinstance(job, dict):
            logger.warning("skipping unparsable static-scan job message_id=%s", message_id)
            continue
        try:
            _process_job(job)
            processed += 1
        except StaticScanError as exc:
            # Non-retryable: a malformed job / foreign object. Log and skip.
            logger.warning("skipping static-scan job: %s", exc)
        except Exception:
            # Transient (AWS error, scanner infra). Report so it retries/DLQs.
            logger.exception("unprocessable static-scan job message_id=%s (will retry)", message_id)
            if message_id:
                batch_item_failures.append({"itemIdentifier": message_id})

    logger.info("static-scan processed=%d failures=%d", processed, len(batch_item_failures))
    return {"batchItemFailures": batch_item_failures}
