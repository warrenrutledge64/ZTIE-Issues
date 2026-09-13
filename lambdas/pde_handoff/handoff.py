"""ZTIE Story 4.6 (RD-047) — PURE gate + outcome-assembly logic for the PDE handoff.

The ACCEPT ENFORCEMENT ACTION, decision core. Everything in this module is PURE
(no boto3, no I/O) so it is fully offline-unit-testable — the proven 1.2 -> 4.5
pattern: pure logic + a thin ``awsio.py`` boto3 seam (in ``awsio.py``) + a thin
orchestrating ``handler.py``.

What lives here:
  * ``evaluate_gate`` — the FAIL-CLOSED decision: given the Hub tracking item's
    recorded human decision and the sha256-verification result, decide whether the
    artifact may be pushed. It NEVER looks at the advisory ``recommended_verdict``
    (RD-040): the trigger is a recorded human ``accepted`` ONLY. Absent a genuine
    accept, or on any hash mismatch, the gate refuses and nothing leaves Forensic.
  * ``build_handoff_envelope`` — assemble the bounded, verdict-free
    ``handoff.contract.v1`` outcome envelope (the 10th RD-013 crossing kind) that
    records WHAT the mechanism did (pushed / refused_not_accepted /
    refused_hash_mismatch) and — only when pushed — a POINTER to where the artifact
    landed in the Pipeline-Sandbox. NO verdict/safe/approved/forward field anywhere.

Design invariants (RD-009 / RD-013 / RD-040 / RD-047):
  * FAIL-CLOSED. ``evaluate_gate`` returns ``push=True`` iff the decision is the
    exact string ``accepted`` AND the sha256 verified. Any other decision
    (``pending`` / ``rejected`` / absent / unknown) or a hash mismatch -> no push.
  * HUMAN ACCEPT, NEVER THE RECOMMENDATION. The gate reads ``human_decision`` only;
    it never reads / trusts ``recommended_verdict``.
  * VERDICT-FREE OUTCOME. The crossed outcome records the MECHANISM result +
    bounded pointer, never a verdict; the human accept was the decision.
"""

from __future__ import annotations

from typing import Any

# The recorded human decision values (RD-047). The tracking item's
# ``human_decision`` field carries one of these; the default (no human has acted)
# is ``pending``. Only ``accepted`` permits a push.
DECISION_PENDING = "pending"
DECISION_ACCEPTED = "accepted"
DECISION_REJECTED = "rejected"
_KNOWN_DECISIONS = frozenset({DECISION_PENDING, DECISION_ACCEPTED, DECISION_REJECTED})

# The mechanism-result values recorded in the crossed outcome. NONE is a verdict.
OUTCOME_PUSHED = "pushed"
OUTCOME_REFUSED_NOT_ACCEPTED = "refused_not_accepted"
OUTCOME_REFUSED_HASH_MISMATCH = "refused_hash_mismatch"

HANDOFF_CONTRACT_VERSION_DEFAULT = "1.0"


class GateDecision:
    """The PURE, fail-closed gate result. ``push`` is the single authority on
    whether the artifact may leave Forensic; ``outcome`` / ``reason`` /
    ``observed_decision`` are recorded verbatim into the crossed handoff outcome."""

    __slots__ = ("observed_decision", "outcome", "push", "reason")

    def __init__(
        self, *, push: bool, outcome: str, reason: str, observed_decision: str
    ) -> None:
        self.push = push
        self.outcome = outcome
        self.reason = reason
        self.observed_decision = observed_decision


def normalize_decision(raw: Any) -> str:
    """Coerce a recorded human decision to a known value, fail-safe.

    Anything that is not the exact string ``accepted`` / ``rejected`` (case-folded,
    stripped) is treated as ``pending`` — the fail-closed default. This means an
    ABSENT field, ``None``, an unexpected type, or an unknown string ALL collapse to
    ``pending`` and therefore refuse. (We deliberately do NOT invent a fourth value:
    the crossed contract's ``observed_decision`` enum is pending/accepted/rejected,
    and 'anything unexpected' is safest reported as pending — no human has validly
    accepted.)"""
    if isinstance(raw, str):
        v = raw.strip().lower()
        if v in _KNOWN_DECISIONS:
            return v
    return DECISION_PENDING


def evaluate_gate(*, human_decision: Any, hash_verified: bool) -> GateDecision:
    """The FAIL-CLOSED ACCEPT gate (RD-040 / RD-047). PURE.

    Push iff the recorded human decision is exactly ``accepted`` AND the sha256
    verified. Evaluation order records the MOST SPECIFIC refusal reason:
      * not accepted           -> refused_not_accepted (never even reached the hash).
      * accepted but mismatch  -> refused_hash_mismatch (SI-7 integrity refusal).
      * accepted + verified    -> pushed.

    NEVER consults ``recommended_verdict`` — the advisory recommendation is not the
    trigger.
    """
    decision = normalize_decision(human_decision)

    if decision != DECISION_ACCEPTED:
        return GateDecision(
            push=False,
            outcome=OUTCOME_REFUSED_NOT_ACCEPTED,
            reason=(
                f"no recorded human accept (human_decision={decision}); "
                f"fail-closed, nothing leaves Forensic"
            ),
            observed_decision=decision,
        )

    if not hash_verified:
        return GateDecision(
            push=False,
            outcome=OUTCOME_REFUSED_HASH_MISMATCH,
            reason=(
                "sha256 mismatch: the Forensic artifact does not match the tracked "
                "record; fail-closed, nothing leaves Forensic"
            ),
            observed_decision=decision,
        )

    return GateDecision(
        push=True,
        outcome=OUTCOME_PUSHED,
        reason="recorded human accept + verified sha256",
        observed_decision=decision,
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

    PURE. Records the mechanism outcome + the observed human decision + whether the
    hash verified, and — only when pushed — the destination pointer + pushed_at.
    There is deliberately NO verdict/safe/approved/forward field; the schema has no
    slot for one.
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
