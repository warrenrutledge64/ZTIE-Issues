"""ZTIE Story 4.6 (RD-047, reworked per RD-048/RD-049) — Forensic PDE-handoff push Lambda.

The ACCEPT ENFORCEMENT ACTION. Runs in the FORENSIC account (360999005254) — the blast
zone where the raw artifact lives. On a genuine Hub-signed ACCEPT + a matching hash, it
PUSHES the artifact one-directionally + least-privilege to the Pipeline-Sandbox landing
bucket (586917955591). On landing the artifact is under PDE control and ZTIE's job ends.

**REWORK (RD-048/RD-049):** the trigger is no longer a cross-account read of the Hub's
``human_decision``. The Hub HANDS OUT an authenticated ``decision.token.v1`` (a
KMS-asymmetric-signed decision) and this spoke VERIFIES it OFFLINE against the Hub's
embedded public key — the Hub is never read. The push happens ONLY on a Hub-signed
``accepted`` token whose ``sha256`` matches the recomputed artifact bytes (and which is
fresh + signed by a trusted key). Every other RD-047 property is unchanged.

Invocation payload (direct invoke now; a future Story 4.4 delivers this one-directionally
Hub→Forensic; the handler also accepts the API-Gateway pathParameters/queryStringParameters
shape so an API front needs no change):

  {
    "intake_id": "<uuid>",                 # which intake
    "decision_token": { ...decision.token.v1... },  # the Hub-signed token (its intake_id must match)
    "signature": "<base64 DER ECDSA sig>", # detached signature over the canonical token bytes
    "artifact_s3_key": "intake/<id>/<file>"  # (optional) the Forensic S3 key; else derived from intake_id + filename
    # "filename": "<name>"                 # (optional) used to derive the key if artifact_s3_key is absent
  }

Flow (FAIL-CLOSED at every step — RD-040 / RD-048 / RD-049):
  1. Resolve intake_id + the signed token + signature from the payload. Missing/malformed
     token or signature -> refuse (400) — nothing read, nothing pushed.
  2. Resolve the Forensic artifact key (from the payload) and recompute its sha256
     (streaming, in-account read).
  3. Verify OFFLINE (``handoff.evaluate_token_gate`` -> vendored ``verify.verify_decision``):
     push iff the signature verifies against the trusted embedded public key AND the
     token decision is exactly ``accepted`` AND ``token.sha256`` == the recomputed
     artifact sha256 AND the token is fresh AND ``key_id`` is trusted. No Hub call.
  4. If (and only if) the gate says push, PutObject the artifact cross-account to the
     Sandbox landing bucket under the scoped prefix (SSE-S3).
  5. ALWAYS cross a bounded, verdict-free handoff OUTCOME to the Hub via the RD-013
     ingest queue (pushed / refused_not_accepted / refused_hash_mismatch).

Design invariants (RD-009 / RD-013 / RD-040 / RD-047 / RD-048 / RD-049):
  * FAIL-CLOSED. Absent a valid Hub-signed accepted token whose hash matches, NOTHING
    leaves Forensic.
  * NO SPOKE→HUB READ (RD-048). The decision is a signed token verified offline; this
    Lambda holds NO Hub read grant and never calls the Hub.
  * HUB STAYS OUT OF THE BLAST ZONE. Artifact goes Forensic → Sandbox DIRECTLY; only the
    bounded, verdict-free outcome crosses to the Hub.
  * NEVER RE-EXECUTE. Security clearance only.
  * LEAST PRIVILEGE. The role grants exactly: GetObject on the Forensic artifact bucket,
    one-prefix PutObject on the Sandbox bucket, SendMessage on the one Hub ingest queue.
    No Bedrock, no DynamoDB.
"""

from __future__ import annotations

import base64
import datetime as _dt
import logging
import os
import re as _re
from typing import Any

import handoff
import signature as _sig
import verify

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# --- Configuration (from environment; set by the CDK stack) -----------------

# The Forensic artifact bucket the raw body lives in (read in-account).
ARTIFACT_BUCKET = os.environ.get("ARTIFACT_BUCKET", "")
# Story 4.10 (RD-059): the intake's Forensic prefixes swept AFTER a verified accept lands
# in the Sandbox (raw + derived). Comma-separated prefix TEMPLATES containing `{intake_id}`;
# each resolves to `intake/<id>/` etc. Mirrors the Story 4.7 REJECT destroy set. A blank/
# unset value DISABLES the sweep (backward-compatible: the pusher behaves exactly as the
# original 4.6 push-only if this env is absent).
SWEEP_PREFIX_TEMPLATES = os.environ.get(
    "FORENSIC_SWEEP_PREFIX_TEMPLATES",
    "intake/{intake_id}/,findings/{intake_id}/,runs/{intake_id}/,traces/{intake_id}/",
)
# The Pipeline-Sandbox landing bucket + the one prefix the pusher is scoped to.
SANDBOX_LANDING_BUCKET = os.environ.get("SANDBOX_LANDING_BUCKET", "")
SANDBOX_LANDING_PREFIX = os.environ.get("SANDBOX_LANDING_PREFIX", "accepted/")
SANDBOX_ACCOUNT_ID = os.environ.get("SANDBOX_ACCOUNT_ID", "")
# The one-directional Forensic -> Hub door (the RD-013 ingest queue).
HUB_INGEST_QUEUE_URL = os.environ.get("HUB_INGEST_QUEUE_URL", "")
# The handoff outcome pins its OWN contract version (RD-047). Currently "1.0".
HANDOFF_CONTRACT_VERSION = os.environ.get("HANDOFF_CONTRACT_VERSION", "1.0")
# RD-048/RD-049: the Hub's decision-signing PUBLIC key (PEM), embedded at deploy so the
# pusher verifies OFFLINE (no call into the Hub / Hub KMS). NOT a secret.
HUB_PUBLIC_KEY_PEM = os.environ.get("HUB_PUBLIC_KEY_PEM", "")
# The trusted signing key id(s) — the token's key_id must be one of these (a set,
# comma-separated, to allow a rotation window). Typically the Hub signing key ARN.
TRUSTED_KEY_IDS = os.environ.get("TRUSTED_KEY_IDS", "")
# Bounded freshness window for a signed decision (replay bound), in seconds.
DECISION_MAX_AGE_SECONDS = int(
    os.environ.get("DECISION_MAX_AGE_SECONDS", str(verify.DEFAULT_MAX_AGE_SECONDS))
)

_UUID4_RE = _re.compile(
    "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


class HandoffError(Exception):
    """A bounded, caller-facing error (bad request / unprocessable). Carries an
    HTTP-ish ``code``. Raised BEFORE any push is attempted (fail-closed)."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _now_iso() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat().replace("+00:00", "Z")


def _get_param(event: dict[str, Any], key: str) -> Any:
    """Pull a param from a direct-invoke event OR an API-Gateway-shaped event
    (pathParameters / queryStringParameters). Pure."""
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


def _resolve_artifact_key(event: dict[str, Any], intake_id: str) -> str:
    """Resolve the Forensic S3 key of the raw artifact from the invoke payload.

    Prefer an explicit ``artifact_s3_key``; else derive ``intake/<intake_id>/<filename>``
    from a ``filename`` param. No Hub read (RD-048)."""
    explicit = _get_param(event, "artifact_s3_key")
    if isinstance(explicit, str) and explicit:
        # Bound it to this intake's prefix so a caller can't point the pusher at an
        # arbitrary object (defense-in-depth; the IAM grant is already intake/* scoped).
        if not explicit.startswith(f"intake/{intake_id}/"):
            raise HandoffError(
                400,
                "artifact_s3_key must be under intake/<intake_id>/ for this intake",
            )
        return explicit
    filename = _get_param(event, "filename")
    if isinstance(filename, str) and filename and "/" not in filename:
        return f"intake/{intake_id}/{filename}"
    raise HandoffError(
        400,
        "missing artifact_s3_key (or a bare filename) to locate the Forensic artifact",
    )


def _dest_key(intake_id: str, artifact_key: str) -> str:
    """The Sandbox landing key under the scoped prefix. Preserve the artifact basename;
    namespace by intake_id so two intakes never collide."""
    prefix = SANDBOX_LANDING_PREFIX
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    basename = artifact_key.rsplit("/", 1)[-1] or "artifact"
    return f"{prefix}{intake_id}/{basename}"


def _sweep_prefixes(intake_id: str) -> list[str]:
    """Story 4.10 (RD-059): resolve the intake's Forensic prefixes to sweep on a verified
    accept, from the ``FORENSIC_SWEEP_PREFIX_TEMPLATES`` env (comma-separated templates
    with ``{intake_id}``). A blank/unset env DISABLES the sweep (returns []), keeping the
    pusher backward-compatible with the original 4.6 push-only behavior. Pure."""
    raw = SWEEP_PREFIX_TEMPLATES or ""
    prefixes: list[str] = []
    for tmpl in raw.split(","):
        t = tmpl.strip()
        if t:
            prefixes.append(t.replace("{intake_id}", intake_id))
    return prefixes


def _decode_signature(raw: Any) -> bytes:
    """Decode the base64 detached signature from the payload. Raises HandoffError(400)
    on a missing/malformed signature (fail-closed before any push)."""
    if not isinstance(raw, str) or not raw:
        raise HandoffError(400, "missing decision-token signature")
    try:
        return base64.b64decode(raw, validate=True)
    except (ValueError, TypeError) as exc:
        raise HandoffError(400, f"malformed base64 signature: {exc}") from exc


def perform_handoff(event: dict[str, Any], intake_id: str) -> dict[str, Any]:
    """Verify the Hub-signed token OFFLINE, push iff it authorizes THIS artifact, and
    ALWAYS cross a bounded outcome to the Hub. Raises ``HandoffError`` (before any push)
    on a bad request. No Hub read (RD-048)."""
    import awsio  # local import so tests can stub the seam before import

    token = _get_param(event, "decision_token")
    if not isinstance(token, dict):
        raise HandoffError(400, "missing or malformed decision_token")
    # The token's intake_id must match the invoke's intake_id (defense-in-depth; the
    # verify gate also checks the token shape).
    if token.get("intake_id") != intake_id:
        raise HandoffError(400, "decision_token intake_id does not match intake_id")
    sig = _decode_signature(_get_param(event, "signature"))

    artifact_key = _resolve_artifact_key(event, intake_id)

    # Recompute the Forensic artifact's sha256 (in-account read). The token's sha256 is
    # verified against THIS value inside the gate (SI-7 + artifact binding).
    computed_sha, size_bytes = awsio.compute_artifact_sha256_and_size(
        ARTIFACT_BUCKET, artifact_key
    )

    # The FAIL-CLOSED gate: verify the Hub-signed token OFFLINE. Push iff it is a
    # genuine `accepted` token bound to these exact bytes, fresh, trusted key.
    decision = handoff.evaluate_token_gate(
        token=token,
        signature=sig,
        public_key_pem=HUB_PUBLIC_KEY_PEM.encode("utf-8"),
        verify_signature=_sig.verify_ecdsa_p256_sha256,
        artifact_sha256=computed_sha,
        trusted_key_ids=_trusted_key_ids(),
        max_age_seconds=DECISION_MAX_AGE_SECONDS,
    )
    hash_verified = decision.outcome != handoff.OUTCOME_REFUSED_HASH_MISMATCH

    handed_off_at = _now_iso()
    destination: dict[str, Any] | None = None
    pushed_at: str | None = None
    forensic_sweep: dict[str, Any] | None = None  # Story 4.10 (RD-059): set on a push.

    if decision.push:
        dest_key = _dest_key(intake_id, artifact_key)
        version_id = awsio.push_artifact(
            source_bucket=ARTIFACT_BUCKET,
            source_key=artifact_key,
            dest_bucket=SANDBOX_LANDING_BUCKET,
            dest_key=dest_key,
            metadata={"intake-id": intake_id, "sha256": computed_sha},
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
            "intake_id=%s ACCEPT enforced (verified Hub-signed token): pushed to %s key=%s",
            intake_id,
            SANDBOX_LANDING_BUCKET,
            dest_key,
        )
        # Story 4.10 (RD-059): the POST-ACCEPT Forensic sweep. Now that the artifact has
        # LANDED in the Sandbox (the cross-account PutObject returned; the object carries
        # the sha256 metadata for the PDE-side hash check), destroy this intake's Forensic
        # prefixes — ALL object versions + delete-markers under intake/ + the derived
        # findings/ runs/ traces/ — so a human ACCEPT leaves the blast zone as clean as a
        # human REJECT does (Story 4.7). Symmetric with reject; RD-012 (Forensic holds only
        # ephemeral state). The DURABLE/REUSABLE infra is untouched — this deletes the
        # intake's OBJECTS only, never the bucket/VPC/roles/launch template. The derived
        # report + durable record survive in the Hub. Recorded in the crossed outcome so the
        # Hub honestly shows the residue was cleaned; a sweep FAILURE raises (fail-closed —
        # never a false 'swept'), after the push already succeeded + is recorded below.
        sweep_prefixes = _sweep_prefixes(intake_id)
        if sweep_prefixes:
            sweep = awsio.destroy_intake_prefixes(ARTIFACT_BUCKET, sweep_prefixes)
            forensic_sweep = {
                "swept": True,
                "versions_deleted": int(sweep.get("versions_deleted", 0)),
                "prefixes_cleared": list(sweep.get("prefixes_cleared", [])),
            }
            logger.info(
                "intake_id=%s POST-ACCEPT Forensic sweep complete: versions_deleted=%s prefixes=%s",
                intake_id,
                forensic_sweep["versions_deleted"],
                forensic_sweep["prefixes_cleared"],
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
        sha256=computed_sha,
        handed_off_at=handed_off_at,
        decision=decision,
        hash_verified=hash_verified,
        contract_version=HANDOFF_CONTRACT_VERSION,
        artifact_s3_key=artifact_key,
        size_bytes=size_bytes,
        destination=destination,
        pushed_at=pushed_at,
        forensic_sweep=forensic_sweep,
    )

    awsio.send_handoff_envelope(HUB_INGEST_QUEUE_URL, envelope)

    return {
        "intake_id": intake_id,
        "pushed": decision.push,
        "outcome": decision.outcome,
        "hash_verified": hash_verified,
        "observed_decision": decision.observed_decision,
        "handoff": envelope["handoff"],
    }


def _trusted_key_ids() -> list[str]:
    return [k.strip() for k in TRUSTED_KEY_IDS.split(",") if k.strip()]


def _require_config() -> None:
    missing = [
        name
        for name, val in (
            ("ARTIFACT_BUCKET", ARTIFACT_BUCKET),
            ("SANDBOX_LANDING_BUCKET", SANDBOX_LANDING_BUCKET),
            ("HUB_INGEST_QUEUE_URL", HUB_INGEST_QUEUE_URL),
            ("HUB_PUBLIC_KEY_PEM", HUB_PUBLIC_KEY_PEM),
            ("TRUSTED_KEY_IDS", TRUSTED_KEY_IDS),
        )
        if not val
    ]
    if missing:
        logger.error("Misconfigured: missing env %s", ", ".join(missing))
        raise RuntimeError("PDE handoff pusher is misconfigured")


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """On-demand entry point. Resolves intake_id + the signed token, performs the
    fail-closed handoff, and returns a bounded response. On a bad request it returns a
    bounded error envelope (never raises to the caller). NEVER pushes on a bad request."""
    _require_config()

    event = event if isinstance(event, dict) else {}
    intake_id = _get_param(event, "intake_id")
    if not isinstance(intake_id, str) or not _UUID4_RE.match(intake_id):
        logger.info("bad request: missing or malformed intake_id")
        return {"error": {"code": 400, "message": "missing or malformed intake_id"}}

    try:
        return perform_handoff(event, intake_id)
    except HandoffError as exc:
        logger.info("handoff error %s: %s", exc.code, exc.message)
        return {"error": {"code": exc.code, "message": exc.message}}
