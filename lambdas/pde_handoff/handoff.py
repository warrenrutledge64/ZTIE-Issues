"""ZTIE Story 4.6 (RD-047, reworked per RD-048/RD-049) — PURE gate + outcome assembly.

The ACCEPT ENFORCEMENT ACTION, decision core. Everything here is PURE (no boto3, no
I/O) so it is fully offline-unit-testable — the proven pure-logic + thin-``awsio``-seam
pattern.

**REWORK (RD-048/RD-049):** the trust source is no longer a cross-account read of the
Hub tracking item. The Hub is strictly the control plane; it HANDS OUT an authenticated
``decision.token.v1`` (a KMS-asymmetric-signed decision) that this spoke VERIFIES
OFFLINE against the Hub's embedded public key — no call into the Hub. The push happens
ONLY on a genuine Hub-signed ``accepted`` token whose ``sha256`` matches the recomputed
artifact bytes (and which is fresh + signed by a trusted key). This preserves every
RD-047 property (fail-closed ACCEPT gate on a real human decision, hash-verify before
push, one-directional least-privilege push, verdict-free outcome) while removing the
spoke→Hub read that RD-048 forbids.

What lives here:
  * ``evaluate_token_gate`` — the FAIL-CLOSED decision: given the signed decision token
    (+ its signature + the trusted public key/key_ids) and the recomputed artifact
    sha256, decide whether to push. Delegates the cryptographic + structural checks to
    the vendored ``verify.verify_decision`` (shape → signature → decision==accepted →
    sha256 match → freshness → key trust); any failure ⇒ refuse. NEVER trusts an
    unsigned/spoke-asserted decision (RD-048/RD-049).
  * ``build_handoff_envelope`` — assemble the bounded, verdict-free
    ``handoff.contract.v1`` outcome (unchanged from the original 4.6).
"""

from __future__ import annotations

from typing import Any

import verify

# The mechanism-result values recorded in the crossed outcome. NONE is a verdict.
OUTCOME_PUSHED = "pushed"
OUTCOME_REFUSED_NOT_ACCEPTED = "refused_not_accepted"
OUTCOME_REFUSED_HASH_MISMATCH = "refused_hash_mismatch"

HANDOFF_CONTRACT_VERSION_DEFAULT = "1.0"

# The human decision the mechanism observed (recorded in the outcome as EVIDENCE).
DECISION_PENDING = "pending"
DECISION_ACCEPTED = "accepted"
DECISION_REJECTED = "rejected"

# Map the vendored verify gate's refusal ``code`` to the crossed-outcome ``outcome``
# enum. The outcome contract has three values (pushed / refused_not_accepted /
# refused_hash_mismatch); a hash mismatch is its own outcome, everything else that
# blocks a push is "not accepted" (no valid accepted authorization).
_HASH_CODES = frozenset({"sha_mismatch", "bad_artifact_sha"})


class GateDecision:
    """The PURE, fail-closed gate result. ``push`` is the single authority on whether
    the artifact may leave Forensic; ``outcome`` / ``reason`` / ``observed_decision``
    are recorded verbatim into the crossed handoff outcome."""

    __slots__ = ("observed_decision", "outcome", "push", "reason")

    def __init__(
        self, *, push: bool, outcome: str, reason: str, observed_decision: str
    ) -> None:
        self.push = push
        self.outcome = outcome
        self.reason = reason
        self.observed_decision = observed_decision


def _observed_decision(token: Any) -> str:
    """Best-effort read of the decision the token asserted, for the EVIDENCE field on
    the crossed outcome. Never trusted for the push decision (that is the verified
    gate's job); a malformed/absent token reports ``pending``."""
    if isinstance(token, dict):
        d = token.get("decision")
        if d in (DECISION_ACCEPTED, DECISION_REJECTED, DECISION_PENDING):
            return d
    return DECISION_PENDING


def evaluate_token_gate(
    *,
    token: Any,
    signature: bytes,
    public_key_pem: bytes,
    verify_signature,
    artifact_sha256: str,
    trusted_key_ids,
    now=None,
    max_age_seconds: int = verify.DEFAULT_MAX_AGE_SECONDS,
) -> GateDecision:
    """The FAIL-CLOSED ACCEPT gate (RD-048/RD-049). PURE (crypto is the injected
    ``verify_signature`` callable).

    Push iff the vendored ``verify.verify_decision`` accepts a Hub-signed token whose
    ``decision`` is exactly ``accepted`` AND whose ``sha256`` matches the recomputed
    artifact sha256 AND which is fresh AND signed by a trusted key. Any failure ⇒
    refuse. The advisory ``recommended_verdict`` is never involved; an unsigned or
    spoke-asserted decision cannot pass (no signature ⇒ ``bad_signature``)."""
    observed = _observed_decision(token)
    result = verify.verify_decision(
        token=token,
        signature=signature,
        public_key_pem=public_key_pem,
        verify_signature=verify_signature,
        expected_decision=DECISION_ACCEPTED,
        artifact_sha256=artifact_sha256,
        trusted_key_ids=trusted_key_ids,
        now=now,
        max_age_seconds=max_age_seconds,
    )
    if result.ok:
        return GateDecision(
            push=True,
            outcome=OUTCOME_PUSHED,
            reason="verified Hub-signed accepted token + matching artifact sha256",
            observed_decision=observed,
        )

    # Refusal: map the verify code to the crossed-outcome enum. A hash-binding failure
    # is recorded as refused_hash_mismatch; everything else (bad signature, wrong
    # decision, stale, untrusted key, malformed) is "no valid accepted authorization".
    if result.code in _HASH_CODES:
        outcome = OUTCOME_REFUSED_HASH_MISMATCH
    else:
        outcome = OUTCOME_REFUSED_NOT_ACCEPTED
    return GateDecision(
        push=False,
        outcome=outcome,
        reason=f"{result.code}: {result.reason}"[:512],
        observed_decision=observed,
    )


def build_handoff_envelope(
    *,
    intake_id: str,
    sha256: str,
    handed_off_at: str,
    decision: GateDecision,
    hash_verified: bool,
    contract_version: str = HANDOFF_CONTRACT_VERSION_DEFAULT,
    artifact_s3_key: str | None = None,
    size_bytes: int | None = None,
    destination: dict[str, Any] | None = None,
    pushed_at: str | None = None,
) -> dict[str, Any]:
    """Assemble the bounded, verdict-free ``handoff.contract.v1`` outcome envelope.

    PURE. Unchanged from the original 4.6: records the mechanism outcome + the observed
    human decision + whether the hash verified, and — only when pushed — the
    destination pointer + pushed_at. There is deliberately NO verdict/safe/approved/
    forward field; the schema has no slot for one.
    """
    handoff: dict[str, Any] = {
        "outcome": decision.outcome,
        "observed_decision": decision.observed_decision,
        "hash_verified": bool(hash_verified),
        "reason": decision.reason[:512],
    }
    if artifact_s3_key is not None:
        handoff["artifact_s3_key"] = artifact_s3_key
    if size_bytes is not None:
        handoff["size_bytes"] = int(size_bytes)
    if decision.push:
        # Only a genuine push carries a destination pointer + pushed_at.
        if destination is not None:
            handoff["destination"] = destination
        if pushed_at is not None:
            handoff["pushed_at"] = pushed_at

    return {
        "contract_version": contract_version,
        "intake_id": intake_id,
        "sha256": sha256,
        "handed_off_at": handed_off_at,
        "handoff": handoff,
    }
