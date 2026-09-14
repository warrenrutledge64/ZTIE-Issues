"""ZTIE Story H.2 (RD-048/RD-049) — canonical serialization of a decision token.

PURE stdlib. The bytes the Hub SIGNS and the spoke VERIFIES must be identical, so
both sides serialize the token the SAME deterministic way. This module is the single
source of that canonical form; it has no crypto and no I/O, so it is fully
offline-unit-testable.

Canonical form (pinned): ``json.dumps(token, sort_keys=True, separators=(",", ":"),
ensure_ascii=False).encode("utf-8")`` — sorted keys, no insignificant whitespace, a
stable UTF-8 encoding. The Hub signer and the spoke verifier MUST both use
``canonical_bytes`` so they hash the exact same bytes.
"""

from __future__ import annotations

import json
from typing import Any

# The keys that are part of the SIGNED token. A canonicalization is computed over
# EXACTLY these keys (extra keys are not signed and must not silently ride along).
TOKEN_KEYS = (
    "contract_version",
    "intake_id",
    "decision",
    "sha256",
    "issued_at",
    "key_id",
)


def canonical_token(token: dict[str, Any]) -> dict[str, Any]:
    """Project a token dict to EXACTLY the signed keys (drop anything else).

    Pure. Raises KeyError if a required key is missing (a malformed token can't be
    canonicalized, so it can't be verified — fail-closed upstream)."""
    return {k: token[k] for k in TOKEN_KEYS}


def canonical_bytes(token: dict[str, Any]) -> bytes:
    """The exact bytes to sign / verify for ``token``. Deterministic. Pure.

    Uses sorted keys + no-whitespace separators so the Hub and the spoke produce
    byte-identical output. Only the signed keys are included (via canonical_token)."""
    projected = canonical_token(token)
    return json.dumps(
        projected,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
