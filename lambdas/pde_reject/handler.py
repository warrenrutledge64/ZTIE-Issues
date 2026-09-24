"""ZTIE Story 4.7 (RD-047, per RD-048/RD-049) — Forensic REJECT/destroy Lambda.

The REJECT/hold ENFORCEMENT ACTION — the destroy/hold half of the human gate (4.6 is
the ACCEPT/push half). Runs in the FORENSIC account (360999005254) — the blast zone
where the raw artifact lives. On a genuine Hub-signed REJECT + a matching hash, it
DESTROYS the raw artifact (all S3 versions + delete-markers under intake/<id>/) AND its
derived Forensic outputs (findings/ runs/ traces/ for the intake) AND terminates any
live detonation chamber (the ephemeral EC2, if still running — explicit, not the 5-min
hard TTL). On INCONCLUSIVE (no rejected token) it HOLDS (destroys nothing, pushes
nothing). Either way, a bounded, verdict-free disposition OUTCOME crosses to the Hub;
the derived report in the Hub always survives.

**Trust model (RD-048/RD-049):** the trigger is NOT a cross-account read of the Hub's
``human_decision``. The Hub HANDS OUT an authenticated ``decision.token.v1`` (a
KMS-asymmetric-signed decision) and this spoke VERIFIES it OFFLINE against the Hub's
embedded public key — the Hub is never read. The destroy happens ONLY on a Hub-signed
``rejected`` token whose ``sha256`` matches the recomputed artifact bytes (and which is
fresh + signed by a trusted key).

**The one invariant (RD-040):** 4.7 destroys ONLY on a verified Hub-signed
``rejected`` token — NEVER on the advisory ``recommended_verdict``. INCONCLUSIVE is a
HOLD. Absent a genuine signed REJECT, NOTHING is destroyed.

Invocation payload (direct invoke now; a future Story 4.4 delivers this one-directionally
Hub->Forensic; the handler also accepts the API-Gateway pathParameters/queryStringParameters
shape so an API front needs no change):

  {
    "intake_id": "<uuid>",                          # which intake
    "decision_token": { ...decision.token.v1... },  # (optional) the Hub-signed token
    "signature": "<base64 DER ECDSA sig>",          # (optional) detached signature
    "artifact_s3_key": "intake/<id>/<file>"          # (optional) the Forensic S3 key
    # "filename": "<name>"                           # (optional) derive the key from it
  }

  A missing/absent token+signature is NOT an error — it is the INCONCLUSIVE HOLD path
  (fail-safe default). A present-but-invalid token is a fail-closed refusal (also a
  hold). Only a verified `rejected` token authorizes a destroy.

Flow (FAIL-SAFE at every step — RD-040 / RD-048 / RD-049):
  1. Resolve intake_id from the payload. Missing/malformed -> bounded 400 (no destroy).
  2. Resolve the Forensic artifact key + recompute its sha256 (streaming, in-account).
     If the artifact is already gone (a prior reject), a hold outcome is recorded
     against the tracked hash (idempotent — nothing to destroy).
  3. Evaluate the FAIL-SAFE gate (``reject.evaluate_reject_gate``): destroy iff a
     Hub-signed token verifies AND decision == ``rejected`` AND token.sha256 == the
     recomputed sha256 AND fresh AND trusted key_id. No token -> HOLD. No Hub call.
  4. If (and only if) the gate says destroy: delete ALL versions + markers under the
     intake's Forensic prefixes AND terminate any live chamber (explicit).
  5. ALWAYS cross a bounded, verdict-free disposition OUTCOME to the Hub via the RD-013
     ingest queue (destroyed / held / refused_not_rejected / refused_hash_mismatch).

Design invariants (RD-009 / RD-013 / RD-040 / RD-047 / RD-048 / RD-049):
  * FAIL-SAFE. Absent a valid Hub-signed rejected token whose hash matches, NOTHING is
    destroyed. INCONCLUSIVE holds.
  * NO SPOKE->HUB READ (RD-048). The decision is a signed token verified offline; this
    Lambda holds NO Hub read grant (no dynamodb, no TRACKING_TABLE) and never calls the
    Hub.
  * HUB STAYS OUT OF THE BLAST ZONE. The destroy happens IN Forensic; only the bounded,
    verdict-free outcome crosses to the Hub. The derived report always survives.
  * NEVER RE-EXECUTE. Security clearance only.
  * LEAST PRIVILEGE. The role grants exactly: GetObject + DeleteObject +
    ListBucketVersions on the Forensic artifact bucket (scoped to the intake prefixes),
    DescribeInstances + TerminateInstances (scoped by the ZTIE ephemeral tag),
    SendMessage on the one Hub ingest queue. No Bedrock, no DynamoDB.
"""

from __future__ import annotations

import base64
import datetime as _dt
import logging
import os
import re as _re
from typing import Any

import reject
import signature as _sig
import verify

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# --- Configuration (from environment; set by the CDK stack) -----------------

# The Forensic artifact bucket the raw body + derived outputs live in (read/delete
# in-account). The ONLY bucket this Lambda touches.
ARTIFACT_BUCKET = os.environ.get("ARTIFACT_BUCKET", "")
# The one-directional Forensic -> Hub door (the RD-013 ingest queue).
HUB_INGEST_QUEUE_URL = os.environ.get("HUB_INGEST_QUEUE_URL", "")
# The disposition outcome pins its OWN contract version (RD-047). Currently "1.0".
DISPOSITION_CONTRACT_VERSION = os.environ.get("DISPOSITION_CONTRACT_VERSION", "1.0")
# RD-048/RD-049: the Hub's decision-signing PUBLIC key (PEM), embedded at deploy so the
# destroyer verifies OFFLINE (no call into the Hub / Hub KMS). NOT a secret.
HUB_PUBLIC_KEY_PEM = os.environ.get("HUB_PUBLIC_KEY_PEM", "")
# The trusted signing key id(s) — the token's key_id must be one of these (a set,
# comma-separated, to allow a rotation window). Typically the Hub signing key ARN.
TRUSTED_KEY_IDS = os.environ.get("TRUSTED_KEY_IDS", "")
# Bounded freshness window for a signed decision (replay bound), in seconds.
DECISION_MAX_AGE_SECONDS = int(
    os.environ.get("DECISION_MAX_AGE_SECONDS", str(verify.DEFAULT_MAX_AGE_SECONDS))
)

# The Forensic S3 prefixes destroyed for a rejected intake: the raw artifact +
# every derived output (findings / runs / traces). All stay in Forensic (RD-009); a
# REJECT tears them ALL down so nothing lingers in the blast zone. The derived REPORT
# that survives is the Hub tracking record, never these Forensic outputs.
_DERIVED_PREFIXES = ("intake", "findings", "runs", "traces")

_UUID4_RE = _re.compile(
    "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)


class RejectError(Exception):
    """A bounded, caller-facing error (bad request). Carries an HTTP-ish ``code``.
    Raised BEFORE any destroy is attempted (fail-safe)."""

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
        # Bound it to this intake's prefix so a caller can't point the destroyer at an
        # arbitrary object (defense-in-depth; the IAM grant is already intake/* scoped).
        if not explicit.startswith(f"intake/{intake_id}/"):
            raise RejectError(
                400,
                "artifact_s3_key must be under intake/<intake_id>/ for this intake",
            )
        return explicit
    filename = _get_param(event, "filename")
    if isinstance(filename, str) and filename and "/" not in filename:
        return f"intake/{intake_id}/{filename}"
    raise RejectError(
        400,
        "missing artifact_s3_key (or a bare filename) to locate the Forensic artifact",
    )


def _decode_signature(raw: Any) -> bytes | None:
    """Decode the base64 detached signature from the payload, or None if absent.

    An ABSENT signature is NOT an error — it is the INCONCLUSIVE hold path (a hold
    issues no token/signature). A PRESENT-but-malformed signature raises RejectError
    (fail-closed) so a corrupt authorization can never be silently treated as a hold
    that then somehow destroys — but note the gate still destroys nothing on a hold
    OR a refusal, so this is purely to report a bad request clearly."""
    if raw in (None, ""):
        return None
    if not isinstance(raw, str):
        raise RejectError(400, "malformed decision-token signature")
    try:
        return base64.b64decode(raw, validate=True)
    except (ValueError, TypeError) as exc:
        raise RejectError(400, f"malformed base64 signature: {exc}") from exc


def _all_intake_prefixes(intake_id: str) -> list[str]:
    """The Forensic S3 prefixes destroyed for a rejected intake (raw + derived)."""
    return [f"{p}/{intake_id}/" for p in _DERIVED_PREFIXES]


def perform_reject(event: dict[str, Any], intake_id: str) -> dict[str, Any]:
    """Verify the Hub-signed token OFFLINE, destroy iff it authorizes THIS artifact,
    and ALWAYS cross a bounded outcome to the Hub. Raises ``RejectError`` (before any
    destroy) on a bad request. No Hub read (RD-048)."""
    import awsio  # local import so tests can stub the seam before import

    token = _get_param(event, "decision_token")
    # The token, when present, must be an object AND its intake_id must match (defense-
    # in-depth). An ABSENT token is the hold path (not an error).
    if token is not None and not isinstance(token, dict):
        raise RejectError(400, "malformed decision_token")
    if isinstance(token, dict) and token.get("intake_id") != intake_id:
        raise RejectError(400, "decision_token intake_id does not match intake_id")
    sig = _decode_signature(_get_param(event, "signature"))

    artifact_key = _resolve_artifact_key(event, intake_id)

    # Recompute the Forensic artifact's sha256 (in-account read). The token's sha256 is
    # verified against THIS value inside the gate (SI-7 + artifact binding). If the
    # artifact is already gone (a prior reject already destroyed it), there is nothing
    # to destroy — record a hold against the token's/absent hash (idempotent).
    try:
        computed_sha, _size_bytes = awsio.compute_artifact_sha256_and_size(
            ARTIFACT_BUCKET, artifact_key
        )
    except Exception:  # noqa: BLE001 - a missing artifact is not a destroyer failure
        logger.info(
            "intake_id=%s artifact %s not present (already destroyed?); holding",
            intake_id,
            artifact_key,
        )
        return _emit_hold_when_no_artifact(awsio, intake_id, token, artifact_key)

    # The FAIL-SAFE gate: verify the Hub-signed token OFFLINE. Destroy iff it is a
    # genuine `rejected` token bound to these exact bytes, fresh, trusted key. No token
    # -> HOLD (fail-safe default).
    decision = reject.evaluate_reject_gate(
        token=token,
        signature=sig,
        public_key_pem=HUB_PUBLIC_KEY_PEM.encode("utf-8"),
        verify_signature=_sig.verify_ecdsa_p256_sha256,
        artifact_sha256=computed_sha,
        trusted_key_ids=_trusted_key_ids(),
        max_age_seconds=DECISION_MAX_AGE_SECONDS,
    )
    # hash_verified is meaningful only on a destroy (the artifact binding passed as
    # part of the verified gate); on a hold/refusal there was no successful binding, so
    # it is False. It is therefore True iff the gate authorized a destroy.
    hash_verified = decision.destroy

    disposed_at = _now_iso()
    destroyed: dict[str, Any] | None = None
    chamber_state = reject.CHAMBER_NOT_CHECKED

    if decision.destroy:
        # (1) Destroy ALL versions + delete-markers under every intake prefix (raw +
        #     derived). The bucket is versioned (OD-001) — delete every version.
        result = awsio.destroy_intake_prefixes(
            ARTIFACT_BUCKET, _all_intake_prefixes(intake_id)
        )
        # (2) Terminate any LIVE detonation chamber for this intake (explicit, not TTL).
        chamber_instance = awsio.find_running_chamber(intake_id)
        chamber_id: str | None = None
        if chamber_instance:
            awsio.terminate_chamber(chamber_instance)
            chamber_state = reject.CHAMBER_TERMINATED
            chamber_id = chamber_instance
        else:
            chamber_state = reject.CHAMBER_NONE_RUNNING
        destroyed = {
            "artifact_versions_deleted": int(result["versions_deleted"]),
            "prefixes_cleared": result["prefixes_cleared"],
            "chamber": chamber_state,
            "destroyed_at": _now_iso(),
        }
        if chamber_id:
            destroyed["chamber_instance_id"] = chamber_id
        logger.info(
            "intake_id=%s REJECT enforced (verified Hub-signed token): destroyed "
            "%d versions across %s; chamber=%s",
            intake_id,
            destroyed["artifact_versions_deleted"],
            destroyed["prefixes_cleared"],
            chamber_state,
        )
    else:
        logger.info(
            "intake_id=%s reject HELD/REFUSED (fail-safe): outcome=%s reason=%s",
            intake_id,
            decision.outcome,
            decision.reason,
        )

    envelope = reject.build_disposition_envelope(
        intake_id=intake_id,
        sha256=computed_sha,
        disposed_at=disposed_at,
        decision=decision,
        hash_verified=hash_verified,
        chamber_state=chamber_state,
        contract_version=DISPOSITION_CONTRACT_VERSION,
        artifact_s3_key=artifact_key,
        destroyed=destroyed,
    )

    awsio.send_disposition_envelope(HUB_INGEST_QUEUE_URL, envelope)

    return {
        "intake_id": intake_id,
        "destroyed": decision.destroy,
        "outcome": decision.outcome,
        "hash_verified": hash_verified,
        "observed_decision": decision.observed_decision,
        "chamber_state": chamber_state,
        "disposition": envelope["disposition"],
    }


def _emit_hold_when_no_artifact(
    awsio, intake_id: str, token: Any, artifact_key: str
) -> dict[str, Any]:
    """When the artifact is already gone (idempotent re-reject), record a HOLD outcome
    (nothing to destroy) against the token's sha256 (or a zero hash if absent) so the
    crossing still binds to the record. Destroys nothing; crosses a bounded outcome."""
    # Bind to the token's sha256 if a token is present, else a zeroed hash (the Hub
    # integrity check needs 64-hex; a hold with no token still crosses a bounded fact).
    sha = "0" * 64
    if isinstance(token, dict) and isinstance(token.get("sha256"), str):
        candidate = token["sha256"].strip().lower()
        if _re.match("^[0-9a-f]{64}$", candidate):
            sha = candidate
    hold = reject.GateDecision(
        destroy=False,
        outcome=reject.OUTCOME_HELD,
        reason="artifact already absent (nothing to destroy); holding",
        observed_decision=reject._observed_decision(token),
    )
    envelope = reject.build_disposition_envelope(
        intake_id=intake_id,
        sha256=sha,
        disposed_at=_now_iso(),
        decision=hold,
        hash_verified=False,
        chamber_state=reject.CHAMBER_NOT_CHECKED,
        contract_version=DISPOSITION_CONTRACT_VERSION,
        artifact_s3_key=artifact_key,
        destroyed=None,
    )
    awsio.send_disposition_envelope(HUB_INGEST_QUEUE_URL, envelope)
    return {
        "intake_id": intake_id,
        "destroyed": False,
        "outcome": reject.OUTCOME_HELD,
        "hash_verified": False,
        "observed_decision": hold.observed_decision,
        "chamber_state": reject.CHAMBER_NOT_CHECKED,
        "disposition": envelope["disposition"],
    }


def _trusted_key_ids() -> list[str]:
    return [k.strip() for k in TRUSTED_KEY_IDS.split(",") if k.strip()]


def _require_config() -> None:
    missing = [
        name
        for name, val in (
            ("ARTIFACT_BUCKET", ARTIFACT_BUCKET),
            ("HUB_INGEST_QUEUE_URL", HUB_INGEST_QUEUE_URL),
            ("HUB_PUBLIC_KEY_PEM", HUB_PUBLIC_KEY_PEM),
            ("TRUSTED_KEY_IDS", TRUSTED_KEY_IDS),
        )
        if not val
    ]
    if missing:
        logger.error("Misconfigured: missing env %s", ", ".join(missing))
        raise RuntimeError("Forensic reject/destroy Lambda is misconfigured")


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """On-demand entry point. Resolves intake_id + the (optional) signed token,
    performs the fail-safe reject/hold, and returns a bounded response. On a bad
    request it returns a bounded error envelope (never raises to the caller). NEVER
    destroys on a bad request or an unverified token."""
    _require_config()

    event = event if isinstance(event, dict) else {}
    intake_id = _get_param(event, "intake_id")
    if not isinstance(intake_id, str) or not _UUID4_RE.match(intake_id):
        logger.info("bad request: missing or malformed intake_id")
        return {"error": {"code": 400, "message": "missing or malformed intake_id"}}

    try:
        return perform_reject(event, intake_id)
    except RejectError as exc:
        logger.info("reject error %s: %s", exc.code, exc.message)
        return {"error": {"code": exc.code, "message": exc.message}}
