"""ZTIE Story 1.4 — safe-reject decision (PURE logic).

Given a routing decision where ``routable=False``, produce the safe-reject
terminal outcome. This is the pipeline's FAIL-SAFE: an artifact that cannot be
routed to any Phase-2 lane is refused cleanly and terminally — never crashed,
never dropped, always recorded.

Design:
  * PURE FUNCTION. No boto3, no I/O. Takes the routing decision dict and returns
    the ``rejection`` object shaped by ``schemas/reject.contract.v1.json`` (minus
    the envelope keys the wiring layer stamps). Offline-unit-testable with stdlib.
  * TERMINAL PROCESSING OUTCOME, NOT A VERDICT. The returned dict has no
    ``verdict`` / ``safe`` / ``approved`` / ``forward`` field. A safe-reject says
    "we could not route this"; the human verdict (PASS/FAIL/INCONCLUSIVE) is a
    separate, Hub-side Phase-4 decision.
  * NEVER CRASH, NEVER DROP. Any input produces a well-formed outcome.
"""

from __future__ import annotations

from typing import Any

# The terminal pipeline outcome for a safe-rejected artifact.
PIPELINE_OUTCOME = "SAFE_REJECTED"

# The only rejection reason (for now). The enum is closed and small.
REASON_UNROUTABLE = "unroutable_class"


def reject(routing_decision: dict[str, Any]) -> dict[str, Any]:
    """Produce the safe-reject outcome from an unroutable routing decision.

    Returns the ``rejection`` object of the reject contract:
    ``pipeline_outcome``, ``reason``, ``artifact_class``, and an optional
    ``notes`` string.

    This is a TERMINAL PROCESSING OUTCOME only — never a verdict, never a
    forward-to-PDE decision.

    Precondition: ``routing_decision["routable"]`` is False. If called on a
    routable decision, returns None (the caller should NOT emit a reject envelope
    for a routable artifact).
    """
    if routing_decision.get("routable"):
        return None  # type: ignore[return-value]

    artifact_class = routing_decision.get("artifact_class", "other_unknown")
    notes = routing_decision.get("notes")

    result: dict[str, Any] = {
        "pipeline_outcome": PIPELINE_OUTCOME,
        "reason": REASON_UNROUTABLE,
        "artifact_class": artifact_class,
    }
    if notes:
        # Carry the router's diagnostic note (bounded, non-executable) into the
        # reject record for audit — e.g. "unrecognised class 'xyz'; failed safe."
        result["notes"] = str(notes)[:256]
    return result
