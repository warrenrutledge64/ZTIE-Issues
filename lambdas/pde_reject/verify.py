"""ZTIE Story H.2 (RD-048/RD-049) — the fail-closed verify-then-act gate.

PURE. This module contains the DECISION logic a spoke runs to decide whether a
Hub-signed ``decision.token.v1`` authorizes an action — with the raw signature check
INJECTED as a callable so this module has no crypto dependency and is fully
offline-unit-testable. The real ECDSA verification lives in ``signature.py`` (which
needs the bundled ``cryptography`` lib); tests pass a stub verifier.

The five fail-closed checks (RD-049 §5); the spoke acts ONLY if ALL hold, and the
FIRST failure short-circuits to a refusal (nothing acts):

  1. shape        — token is a dict with exactly the allow-listed keys + right types
                    (a malformed token is refused before any crypto).
  2. signature    — the injected verifier confirms the detached signature over the
                    CANONICAL token bytes (canonical.canonical_bytes) using a trusted
                    public key. This is the one step that needs real crypto.
  3. decision     — token['decision'] == the exact value this action requires
                    (e.g. 'accepted' for a push, 'rejected' for a destroy).
  4. artifact     — token['sha256'] == the recomputed sha256 of the artifact the
                    spoke holds (binds the decision to THESE bytes — SI-7).
  5. freshness    — issued_at is within a bounded window (a replay bound).
  6. key trust    — token['key_id'] is in the spoke's set of trusted key ids.

(Steps are numbered 1..6 above; "five checks" in the design refers to the five
security predicates beyond the basic shape guard.)

Everything is a REFUSAL by default: any exception, any unexpected shape, any failed
check => VerifyResult(ok=False, ...). There is no path that returns ok=True without
all checks passing.
"""

from __future__ import annotations

import datetime as _dt
import re as _re
from collections.abc import Callable, Iterable
from typing import Any

import canonical

_UUID4_RE = _re.compile(
    "^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_SHA256_RE = _re.compile("^[0-9a-f]{64}$")
_DECISIONS = frozenset({"accepted", "rejected"})
_CONTRACT_VERSION = "1.0"

# Default freshness window: a signed decision is valid for a bounded time so a
# captured token cannot be replayed indefinitely. Configurable per call.
DEFAULT_MAX_AGE_SECONDS = 3600

# A verifier is: (message_bytes, signature_bytes, public_key_pem_bytes) -> bool.
# It returns True iff the signature is valid; it MUST NOT raise for an invalid
# signature (it returns False) — but if it does raise, the gate treats that as a
# refusal too (fail-closed).
SignatureVerifier = Callable[[bytes, bytes, bytes], bool]


class VerifyResult:
    """The outcome of the gate. ``ok`` is the single authority on whether the spoke
    may act; ``reason`` / ``code`` explain a refusal (recorded, never acted on)."""

    __slots__ = ("code", "ok", "reason")

    def __init__(self, *, ok: bool, code: str, reason: str) -> None:
        self.ok = ok
        self.code = code
        self.reason = reason

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"VerifyResult(ok={self.ok}, code={self.code!r}, reason={self.reason!r})"


def _refuse(code: str, reason: str) -> VerifyResult:
    return VerifyResult(ok=False, code=code, reason=reason)


def _parse_iso_utc(value: str) -> _dt.datetime | None:
    """Parse an RFC3339/ISO-8601 UTC (Z-suffixed) timestamp to an aware datetime, or
    None if unparseable. Pure."""
    if not isinstance(value, str):
        return None
    try:
        # Accept a trailing Z (Python's fromisoformat handles +00:00; normalize Z).
        normalized = value.replace("Z", "+00:00")
        dt = _dt.datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return None
    return dt.astimezone(_dt.timezone.utc)


def _check_shape(token: Any) -> VerifyResult | None:
    """Fail-closed structural guard: exactly the allow-listed keys + correct types /
    patterns. Returns a refusal VerifyResult on any problem, else None (shape ok)."""
    if not isinstance(token, dict):
        return _refuse("bad_shape", "token is not an object")
    expected = set(canonical.TOKEN_KEYS)
    actual = set(token.keys())
    if actual != expected:
        return _refuse(
            "bad_shape",
            f"token keys {sorted(actual)} != allow-listed {sorted(expected)}",
        )
    if token["contract_version"] != _CONTRACT_VERSION:
        return _refuse(
            "bad_version",
            f"unsupported contract_version {token['contract_version']!r}",
        )
    if not (isinstance(token["intake_id"], str) and _UUID4_RE.match(token["intake_id"])):
        return _refuse("bad_shape", "intake_id is not a UUIDv4")
    if token["decision"] not in _DECISIONS:
        return _refuse("bad_shape", f"decision {token['decision']!r} not allow-listed")
    if not (isinstance(token["sha256"], str) and _SHA256_RE.match(token["sha256"])):
        return _refuse("bad_shape", "sha256 is not 64-hex")
    if not (isinstance(token["issued_at"], str) and 0 < len(token["issued_at"]) <= 40):
        return _refuse("bad_shape", "issued_at is missing/oversized")
    if not (isinstance(token["key_id"], str) and 0 < len(token["key_id"]) <= 256):
        return _refuse("bad_shape", "key_id is missing/oversized")
    return None


def verify_decision(
    *,
    token: Any,
    signature: bytes,
    public_key_pem: bytes,
    verify_signature: SignatureVerifier,
    expected_decision: str,
    artifact_sha256: str,
    trusted_key_ids: Iterable[str],
    now: _dt.datetime | None = None,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
) -> VerifyResult:
    """Run the fail-closed verify-then-act gate. Returns VerifyResult(ok=True) ONLY
    if every check passes; any problem (bad shape, bad signature, wrong decision,
    sha mismatch, stale, untrusted key, or ANY exception) is a refusal. PURE apart
    from the injected ``verify_signature`` callable and the clock (``now``)."""
    # 1. shape (before any crypto).
    shape_refusal = _check_shape(token)
    if shape_refusal is not None:
        return shape_refusal

    # 2. signature over the CANONICAL bytes, via the injected verifier. Any
    #    exception from the verifier is treated as a failed signature (fail-closed).
    try:
        message = canonical.canonical_bytes(token)
    except Exception as exc:  # noqa: BLE001 - fail-closed: a malformed token can't be canonicalized
        return _refuse("bad_shape", f"could not canonicalize token: {exc}")
    try:
        sig_ok = bool(verify_signature(message, signature, public_key_pem))
    except Exception as exc:  # noqa: BLE001 - fail-closed: a raising verifier => not verified
        return _refuse("bad_signature", f"signature verification raised: {exc}")
    if not sig_ok:
        return _refuse("bad_signature", "signature does not verify against the public key")

    # 3. expected decision.
    if token["decision"] != expected_decision:
        return _refuse(
            "wrong_decision",
            f"decision {token['decision']!r} != required {expected_decision!r}",
        )

    # 4. artifact binding (SI-7): the token is about THESE bytes.
    if not (isinstance(artifact_sha256, str) and _SHA256_RE.match(artifact_sha256.strip().lower() if isinstance(artifact_sha256, str) else "")):
        return _refuse("bad_artifact_sha", "artifact_sha256 is not 64-hex")
    if token["sha256"] != artifact_sha256.strip().lower():
        return _refuse(
            "sha_mismatch",
            "token sha256 does not match the recomputed artifact sha256",
        )

    # 5. freshness (replay bound).
    issued = _parse_iso_utc(token["issued_at"])
    if issued is None:
        return _refuse("bad_shape", "issued_at is not a valid UTC timestamp")
    current = now or _dt.datetime.now(tz=_dt.timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=_dt.timezone.utc)
    age = (current - issued).total_seconds()
    if age < -max_age_seconds:
        return _refuse("not_yet_valid", f"issued_at is {-age:.0f}s in the future")
    if age > max_age_seconds:
        return _refuse("stale", f"token age {age:.0f}s exceeds max {max_age_seconds}s")

    # 6. key trust.
    trusted = set(trusted_key_ids)
    if token["key_id"] not in trusted:
        return _refuse("untrusted_key", f"key_id {token['key_id']!r} is not trusted")

    return VerifyResult(ok=True, code="ok", reason="all checks passed")
