"""ZTIE Story 4.7 (RD-047, per RD-048/RD-049) — PURE reject gate + outcome assembly.

The REJECT/hold ENFORCEMENT ACTION, decision core. Everything here is PURE (no boto3,
no I/O) so it is fully offline-unit-testable — the proven pure-logic + thin-``awsio``-
seam pattern (the sibling of 4.6 ``handoff.py``, inverted from ACCEPT-push to
REJECT-destroy).

**Trust model (RD-048/RD-049).** The Hub is strictly the control plane; it HANDS OUT
an authenticated ``decision.token.v1`` (a KMS-asymmetric-signed decision) that this
spoke VERIFIES OFFLINE against the Hub's embedded public key — no call into the Hub.
The destroy happens ONLY on a genuine Hub-signed ``rejected`` token whose ``sha256``
matches the recomputed artifact bytes (and which is fresh + signed by a trusted key).

**The one invariant that governs everything (RD-040):** 4.7 destroys ONLY on a
verified Hub-signed ``rejected`` token — NEVER on the advisory ``recommended_verdict``.
INCONCLUSIVE issues NO token, so a HOLD is simply "no valid ``rejected`` token
present" — the fail-safe default. Absent a genuine signed REJECT, NOTHING is destroyed.

What lives here:
  * ``evaluate_reject_gate`` — the FAIL-SAFE decision: given a (possibly absent)
    signed decision token (+ its signature + the trusted public key/key_ids) and the
    recomputed artifact sha256, decide whether to destroy. When NO token is presented
    it returns a HOLD (fail-safe default) WITHOUT any crypto. When a token IS presented
    it delegates the cryptographic + structural checks to the vendored
    ``verify.verify_decision`` with ``expected_decision="rejected"`` (shape ->
    signature -> decision==rejected -> sha256 match -> freshness -> key trust); any
    failure => refuse (hold, destroy nothing). NEVER trusts an unsigned/spoke-asserted
    decision (RD-048/RD-049).
  * ``build_disposition_envelope`` — assemble the bounded, verdict-free
    ``disposition.contract.v1`` outcome (what was destroyed / that it held; the
    derived report always survives).
"""

from __future__ import annotations

from typing import Any

import verify

# The mechanism-result values recorded in the crossed outcome. NONE is a verdict.
OUTCOME_DESTROYED = "destroyed"
OUTCOME_HELD = "held"
OUTCOME_REFUSED_NOT_REJECTED = "refused_not_rejected"
OUTCOME_REFUSED_HASH_MISMATCH = "refused_hash_mismatch"

DISPOSITION_CONTRACT_VERSION_DEFAULT = "1.0"

# The human decision the mechanism observed (recorded in the outcome as EVIDENCE).
DECISION_PENDING = "pending"
DECISION_ACCEPTED = "accepted"
DECISION_REJECTED = "rejected"

# Chamber-state values recorded in the outcome (bounded EVIDENCE of teardown).
CHAMBER_TERMINATED = "terminated"
CHAMBER_NONE_RUNNING = "none_running"
CHAMBER_NOT_CHECKED = "not_checked"

# Map the vendored verify gate's refusal ``code`` to the crossed-outcome ``outcome``
# enum. A hash-binding failure is its own outcome (refused_hash_mismatch); everything
# else that blocks a destroy (bad signature / wrong decision e.g. `accepted` / stale /
# untrusted / malformed) is "no valid rejected authorization".
_HASH_CODES = frozenset({"sha_mismatch", "bad_artifact_sha"})


class GateDecision:
    """The PURE, fail-safe gate result. ``destroy`` is the single authority on whether
    the artifact + chamber may be torn down; ``outcome`` / ``reason`` /
    ``observed_decision`` are recorded verbatim into the crossed disposition outcome.

    A HOLD (no valid ``rejected`` token) has ``destroy=False`` and
    ``outcome=held`` — the fail-safe default, distinct from a token that was
    presented but refused (``refused_*``)."""

    __slots__ = ("destroy", "observed_decision", "outcome", "reason")

    def __init__(
        self, *, destroy: bool, outcome: str, reason: str, observed_decision: str
    ) -> None:
        self.destroy = destroy
        self.outcome = outcome
        self.reason = reason
        self.observed_decision = observed_decision


def _observed_decision(token: Any) -> str:
    """Best-effort read of the decision the token asserted, for the EVIDENCE field on
    the crossed outcome. Never trusted for the destroy decision (that is the verified
    gate's job); a malformed/absent token reports ``pending``."""
    if isinstance(token, dict):
        d = token.get("decision")
        if d in (DECISION_ACCEPTED, DECISION_REJECTED, DECISION_PENDING):
            return d
    return DECISION_PENDING


def evaluate_reject_gate(
    *,
    token: Any,
    signature: bytes | None,
    public_key_pem: bytes,
    verify_signature,
    artifact_sha256: str,
    trusted_key_ids,
    now=None,
    max_age_seconds: int = verify.DEFAULT_MAX_AGE_SECONDS,
) -> GateDecision:
    """The FAIL-SAFE REJECT gate (RD-048/RD-049). PURE (crypto is the injected
    ``verify_signature`` callable).

    Destroy iff the vendored ``verify.verify_decision`` accepts a Hub-signed token
    whose ``decision`` is exactly ``rejected`` AND whose ``sha256`` matches the
    recomputed artifact sha256 AND which is fresh AND signed by a trusted key. Any
    failure => refuse (destroy nothing). The advisory ``recommended_verdict`` is never
    involved; an unsigned or spoke-asserted decision cannot pass (no signature =>
    ``bad_signature``).

    Absent a token (or its signature) entirely, this returns a HOLD (fail-safe
    default) WITHOUT invoking any crypto — INCONCLUSIVE issues no token, so "no token"
    is the correct hold path, distinct from a presented-but-refused token."""
    observed = _observed_decision(token)

    # FAIL-SAFE HOLD: no token (or no signature) presented at all. INCONCLUSIVE /
    # pending issues no `rejected` token, so this is the correct "do nothing / hold"
    # path — never a destroy. No crypto is run (there is nothing to verify).
    if not isinstance(token, dict) or signature is None:
        return GateDecision(
            destroy=False,
            outcome=OUTCOME_HELD,
            reason="no rejected decision token presented (hold at approval gate)",
            observed_decision=observed,
        )

    result = verify.verify_decision(
        token=token,
        signature=signature,
        public_key_pem=public_key_pem,
        verify_signature=verify_signature,
        expected_decision=DECISION_REJECTED,
        artifact_sha256=artifact_sha256,
        trusted_key_ids=trusted_key_ids,
        now=now,
        max_age_seconds=max_age_seconds,
    )
    if result.ok:
        return GateDecision(
            destroy=True,
            outcome=OUTCOME_DESTROYED,
            reason="verified Hub-signed rejected token + matching artifact sha256",
            observed_decision=observed,
        )

    # Refusal: a token WAS presented but did not authorize a destroy. Map the verify
    # code to the crossed-outcome enum. A hash-binding failure is recorded as
    # refused_hash_mismatch; everything else (bad signature, wrong decision, stale,
    # untrusted key, malformed) is "no valid rejected authorization". This is distinct
    # from a HOLD (no token at all) — a refusal means something WAS presented and
    # failed the gate; both destroy NOTHING.
    if result.code in _HASH_CODES:
        outcome = OUTCOME_REFUSED_HASH_MISMATCH
    else:
        outcome = OUTCOME_REFUSED_NOT_REJECTED
    return GateDecision(
        destroy=False,
        outcome=outcome,
        reason=f"{result.code}: {result.reason}"[:512],
        observed_decision=observed,
    )


def build_disposition_envelope(
    *,
    intake_id: str,
    sha256: str,
    disposed_at: str,
    decision: GateDecision,
    hash_verified: bool,
    chamber_state: str,
    contract_version: str = DISPOSITION_CONTRACT_VERSION_DEFAULT,
    artifact_s3_key: str | None = None,
    destroyed: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the bounded, verdict-free ``disposition.contract.v1`` outcome envelope.

    PURE. Records the mechanism outcome + the observed human decision + whether the
    hash verified + the chamber state + that the derived report SURVIVES (always true
    — the Hub record is never touched), and — only when destroyed — the bounded
    ``destroyed`` facts (versions deleted count, prefixes cleared, chamber). There is
    deliberately NO verdict/safe/approved/forward field; the schema has no slot for one.
    """
    disposition: dict[str, Any] = {
        "outcome": decision.outcome,
        "observed_decision": decision.observed_decision,
        "hash_verified": bool(hash_verified),
        # A destroy inspects the chamber; a hold/refusal deliberately leaves it to the
        # hard TTL, so record not_checked there (never a spurious teardown).
        "chamber_state": chamber_state,
        # The derived report + durable tracking record live in the Hub (RD-012) and
        # are NEVER touched by 4.7 — only the Forensic blast-zone artifact + chamber
        # are destroyed. Always true; recorded so the audit trail affirms it.
        "report_survives": True,
        "reason": decision.reason[:512],
    }
    if artifact_s3_key is not None:
        disposition["artifact_s3_key"] = artifact_s3_key
    if decision.destroy and destroyed is not None:
        # Only a genuine destroy carries the bounded teardown facts.
        disposition["destroyed"] = destroyed

    return {
        "contract_version": contract_version,
        "intake_id": intake_id,
        "sha256": sha256,
        "disposed_at": disposed_at,
        "disposition": disposition,
    }
