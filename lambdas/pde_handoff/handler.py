"""ZTIE Story 4.6 (RD-047) — Forensic-side PDE-handoff push Lambda.

The ACCEPT ENFORCEMENT ACTION. This Lambda runs in the FORENSIC account
(360999005254) — the blast zone where the raw artifact lives. Invoked on demand by
``intake_id``, it enforces the human-ACCEPT gate and, on a genuine accept + a
verified hash, PUSHES the artifact one-directionally + least-privilege to the
Pipeline-Sandbox landing bucket (586917955591). On landing the artifact is under
PDE control and ZTIE's job ends.

  * ``{"intake_id": "<uuid>"}`` (also accepts an API-Gateway ``pathParameters`` /
    ``queryStringParameters`` shape, so a future 4.4 auto-trigger / API front needs
    no handler change) -> attempt the handoff for that intake.

Flow (FAIL-CLOSED at every step — RD-040 / RD-047):
  1. Read the Hub durable tracking item by intake_id (cross-account GetItem). No
     record -> refuse (404). Missing integrity key -> refuse (422).
  2. Recompute the sha256 of the Forensic artifact (streaming) and compare to the
     Hub record's ``sha256`` (SI-7).
  3. Evaluate the PURE fail-closed gate (``handoff.evaluate_gate``): push iff the
     recorded human ``human_decision == "accepted"`` AND the hash verified. The
     advisory ``recommended_verdict`` is NEVER the trigger (RD-040).
  4. If (and only if) the gate says push, PutObject the artifact cross-account to
     the Sandbox landing bucket under the scoped prefix (SSE-S3).
  5. ALWAYS cross a bounded, verdict-free handoff OUTCOME to the Hub via the RD-013
     ingest queue (pushed / refused_not_accepted / refused_hash_mismatch), so the
     durable record shows the enforcement action ran either way.

Design invariants (RD-009 / RD-013 / RD-040 / RD-047):
  * FAIL-CLOSED. Absent a recorded human accept, or on any hash mismatch, NOTHING
    leaves Forensic — the push is skipped and a refusal outcome is recorded.
  * HUMAN ACCEPT, NEVER THE RECOMMENDATION. The gate reads ``human_decision`` only.
  * HUB STAYS OUT OF THE BLAST ZONE. The artifact goes Forensic -> Sandbox
    DIRECTLY; it is NEVER copied through the Hub. Only the bounded, derived,
    verdict-free outcome crosses to the Hub (allow-list; no raw payload).
  * NEVER RE-EXECUTE. ZTIE does security clearance only; it never re-executes the
    artifact outside Forensic (that is a PDE activity in the Sandbox).
  * LEAST PRIVILEGE. The role grants exactly: cross-account GetItem on the Hub
    table, GetObject on the Forensic artifact bucket, one-prefix PutObject on the
    Sandbox bucket, and SendMessage on the one Hub ingest queue. No Bedrock.
"""

from __future__ import annotations

import datetime as _dt
import logging
import os
import re as _re
from typing import Any

import handoff

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# --- Configuration (from environment; set by the CDK stack) -----------------

# The Hub durable tracking table (read cross-account, GetItem only).
TRACKING_TABLE = os.environ.get("TRACKING_TABLE", "")
# The Forensic artifact bucket the raw body lives in (read in-account).
ARTIFACT_BUCKET = os.environ.get("ARTIFACT_BUCKET", "")
# The Pipeline-Sandbox landing bucket + the one prefix the pusher is scoped to.
SANDBOX_LANDING_BUCKET = os.environ.get("SANDBOX_LANDING_BUCKET", "")
SANDBOX_LANDING_PREFIX = os.environ.get("SANDBOX_LANDING_PREFIX", "accepted/")
SANDBOX_ACCOUNT_ID = os.environ.get("SANDBOX_ACCOUNT_ID", "")
# The one-directional Forensic -> Hub door (the RD-013 ingest queue).
HUB_INGEST_QUEUE_URL = os.environ.get("HUB_INGEST_QUEUE_URL", "")
# The handoff outcome pins its OWN contract version (RD-047). Currently "1.0".
HANDOFF_CONTRACT_VERSION = os.environ.get("HANDOFF_CONTRACT_VERSION", "1.0")

_UUID4_RE = _re.compile(
    "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_SHA256_RE = _re.compile("^[0-9a-f]{64}$")


class HandoffError(Exception):
    """A bounded, caller-facing error (bad request / not found / unprocessable).
    Carries an HTTP-ish ``code`` so a future API front can map it without
    re-parsing the message. Raised BEFORE any push is attempted (fail-closed)."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _get_param(event: dict[str, Any], key: str) -> Any:
    """Pull a param from a direct-invoke event OR an API-Gateway-shaped event
    (pathParameters / queryStringParameters), so the same handler serves both a
    direct invoke now and a 4.4 auto-trigger / API front later. Pure."""
    if not isinstance(event, dict):
        return None
    if key in event and event[key] not in (None, ""):
        return event[key]
    for container_key in ("pathParameters", "queryStringParameters"):
        container = event.get(container_key)
        if isinstance(container, dict):
            val = container.get(key)
            if val not in (None, ""):
                return val
    return None


def _resolve_artifact_key(item: dict[str, Any], intake_id: str) -> str:
    """Resolve the Forensic S3 key of the raw artifact for this intake.

    The intake handler writes raw bodies at ``intake/<intake_id>/<filename>`` and
    the tracking record carries ``filename``. Prefer the recorded origin key when
    present (``origin_s3_key``); else reconstruct from intake_id + filename."""
    origin_key = item.get("origin_s3_key")
    if isinstance(origin_key, str) and origin_key:
        return origin_key
    filename = item.get("filename")
    if not isinstance(filename, str) or not filename:
        raise HandoffError(
            422,
            f"tracking record for intake_id={intake_id} has no artifact key / filename",
        )
    return f"intake/{intake_id}/{filename}"


def _dest_key(intake_id: str, artifact_key: str) -> str:
    """The Sandbox landing key under the scoped prefix. Preserve the artifact's
    basename so the PDE sees a sensible filename; namespace by intake_id so two
    intakes never collide."""
    prefix = SANDBOX_LANDING_PREFIX
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    basename = artifact_key.rsplit("/", 1)[-1] or "artifact"
    return f"{prefix}{intake_id}/{basename}"


def perform_handoff(intake_id: str) -> dict[str, Any]:
    """Read the tracking item, verify the hash, evaluate the fail-closed ACCEPT
    gate, push iff permitted, and ALWAYS cross a bounded outcome to the Hub. Returns
    a bounded response describing what happened. Raises ``HandoffError`` (before any
    push) on a bad/missing/unprocessable record."""
    import awsio  # local import so tests can stub the seam before import

    item = awsio.get_tracking_item(TRACKING_TABLE, intake_id)
    if not item:
        raise HandoffError(404, f"no tracking record for intake_id={intake_id}")

    key_id = item.get("intake_id")
    tracked_sha = item.get("sha256")
    if not isinstance(key_id, str) or not isinstance(tracked_sha, str):
        raise HandoffError(
            422, f"tracking record for intake_id={intake_id} is missing its integrity key"
        )
    tracked_sha = tracked_sha.strip().lower()
    if not _SHA256_RE.match(tracked_sha):
        raise HandoffError(
            422,
            f"tracking record for intake_id={intake_id} has a malformed sha256",
        )

    artifact_key = _resolve_artifact_key(item, intake_id)

    # SI-7: recompute the Forensic artifact's sha256 and compare to the Hub record.
    computed_sha, size_bytes = awsio.compute_artifact_sha256_and_size(
        ARTIFACT_BUCKET, artifact_key
    )
    hash_verified = computed_sha == tracked_sha

    # The FAIL-CLOSED gate: push iff a recorded human accept AND a verified hash.
    # NEVER consults the advisory recommended_verdict (RD-040).
    human_decision = item.get("human_decision")
    decision = handoff.evaluate_gate(
        human_decision=human_decision, hash_verified=hash_verified
    )

    handed_off_at = _now_iso()
    destination: dict[str, Any] | None = None
    pushed_at: str | None = None

    if decision.push:
        dest_key = _dest_key(intake_id, artifact_key)
        version_id = awsio.push_artifact(
            source_bucket=ARTIFACT_BUCKET,
            source_key=artifact_key,
            dest_bucket=SANDBOX_LANDING_BUCKET,
            dest_key=dest_key,
            metadata={"intake-id": intake_id, "sha256": tracked_sha},
        )
        pushed_at = _now_iso()
        prefix = SANDBOX_LANDING_PREFIX
        if prefix and not prefix.endswith("/"):
            prefix += "/"
        destination = {
            "account_id": SANDBOX_ACCOUNT_ID,
            "bucket": SANDBOX_LANDING_BUCKET,
            "prefix": prefix,
            "key": dest_key,
        }
        if isinstance(version_id, str) and version_id and version_id != "null":
            destination["version_id"] = version_id
        logger.info(
            "intake_id=%s ACCEPT enforced: pushed artifact to sandbox bucket=%s key=%s",
            intake_id,
            SANDBOX_LANDING_BUCKET,
            dest_key,
        )
    else:
        logger.info(
            "intake_id=%s handoff REFUSED (fail-closed): outcome=%s reason=%s",
            intake_id,
            decision.outcome,
            decision.reason,
        )

    envelope = handoff.build_handoff_envelope(
        intake_id=intake_id,
        sha256=tracked_sha,
        handed_off_at=handed_off_at,
        decision=decision,
        hash_verified=hash_verified,
        contract_version=HANDOFF_CONTRACT_VERSION,
        artifact_s3_key=artifact_key,
        size_bytes=size_bytes,
        destination=destination,
        pushed_at=pushed_at,
    )

    # ALWAYS record the bounded, verdict-free outcome to the Hub (push or refusal),
    # so the durable record shows the enforcement action ran.
    awsio.send_handoff_envelope(HUB_INGEST_QUEUE_URL, envelope)

    return {
        "intake_id": intake_id,
        "pushed": decision.push,
        "outcome": decision.outcome,
        "hash_verified": hash_verified,
        "observed_decision": decision.observed_decision,
        "handoff": envelope["handoff"],
    }


def _require_config() -> None:
    missing = [
        name
        for name, val in (
            ("TRACKING_TABLE", TRACKING_TABLE),
            ("ARTIFACT_BUCKET", ARTIFACT_BUCKET),
            ("SANDBOX_LANDING_BUCKET", SANDBOX_LANDING_BUCKET),
            ("HUB_INGEST_QUEUE_URL", HUB_INGEST_QUEUE_URL),
        )
        if not val
    ]
    if missing:
        logger.error("Misconfigured: missing env %s", ", ".join(missing))
        raise RuntimeError("PDE handoff pusher is misconfigured")


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """On-demand entry point. Resolves intake_id, performs the fail-closed handoff,
    and returns a bounded response. On a bad request / not-found it returns a bounded
    error envelope (never raises to the caller) so a direct invoke or a future API /
    4.4 auto-trigger gets a clean, typed response. NEVER pushes on a bad request."""
    _require_config()

    event = event if isinstance(event, dict) else {}
    intake_id = _get_param(event, "intake_id")
    if not isinstance(intake_id, str) or not _UUID4_RE.match(intake_id):
        logger.info("bad request: missing or malformed intake_id")
        return {"error": {"code": 400, "message": "missing or malformed intake_id"}}

    try:
        return perform_handoff(intake_id)
    except HandoffError as exc:
        logger.info("handoff error %s: %s", exc.code, exc.message)
        return {"error": {"code": exc.code, "message": exc.message}}
