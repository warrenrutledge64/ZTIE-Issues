"""ZTIE Story 1.3 — routing table (PURE logic).

Given the derived class LABEL produced by the Story 1.2 classifier
(``iac_template`` / ``raw_script`` / ``other_unknown``), decide WHICH downstream
controls apply — i.e. which Phase-2 lane(s) the artifact enters, or the
safe-reject entry (Story 1.4) when it is unroutable.

Design (from the 1.R / 1.1R / 1.2 lessons):

  * PURE FUNCTION. No boto3, no S3, no I/O. It takes a class label string and
    returns a plain dict shaped by ``schemas/routing.contract.v1.json`` (minus the
    envelope keys the wiring layer stamps: intake_id, sha256, routed_at,
    contract_version). This is why it is unit-testable with stdlib ``unittest`` in
    the INTEGRATIONS_ONLY sandbox with no PyPI.
  * DECLARATIVE TABLE. Routing is a small data-driven map (class -> lanes), NOT a
    pile of if/else, so Story 1.4 and all of Phase 2 read cleanly off it. Adding a
    class or re-pointing a lane is a data edit, not a control-flow edit.
  * ZERO-TRUST BOUNDARY. A routing decision is a PLAN OF WHICH CONTROLS TO APPLY.
    It is NEVER a safety verdict and NEVER a forward-to-PDE decision. The returned
    dict has no ``verdict`` / ``safe`` / ``approved`` / ``forward`` field; the
    verdict is Hub-side / human-gated (Phase 4).
  * PRODUCTION CODE — real handling of the unroutable case. ``other_unknown`` and
    ANY unrecognised / malformed class fall through to the safe-reject entry
    (handed to Story 1.4). The router NEVER raises on an unknown class and NEVER
    silently drops an artifact.
"""

from __future__ import annotations

from typing import Any

# --- Lane vocabulary (must match the routing contract's lane enum) -----------
# The addressable downstream fork targets. Phase 2 hangs off exactly these ids.

STATIC_ANALYSIS = "static_analysis"  # non-executing static lane (Story 2.1)
DYNAMIC_DETONATION = "dynamic_detonation"  # ephemeral-EC2 / SSM detonation (2.3)
SAFE_REJECT = "safe_reject"  # safe-reject entry, owned by Story 1.4

# --- Class vocabulary (must match the classification contract's enum) --------

IAC_TEMPLATE = "iac_template"
RAW_SCRIPT = "raw_script"
OTHER_UNKNOWN = "other_unknown"

# --- The routing table: class -> ordered lane plan ---------------------------
# Declarative and closed. Both routable classes fork into BOTH Phase-2 lanes (the
# architecture forks static + dynamic in parallel):
#   * iac_template -> static IaC linters (cfn-lint/cfn-guard/checkov) AND, per the
#     architecture, the dynamic lane.
#   * raw_script   -> the static SAST audit path (bandit) AND the dynamic
#     detonation lane.
# other_unknown is intentionally NOT in this table; it (and any unrecognised
# class) falls through to the safe-reject entry below — never a scanner.
#
# tuple[str, ...] is immutable so the table cannot be mutated at runtime, and
# ruff's RUF012 does not fire on an immutable class-less module constant.
_ROUTING_TABLE: dict[str, tuple[str, ...]] = {
    IAC_TEMPLATE: (STATIC_ANALYSIS, DYNAMIC_DETONATION),
    RAW_SCRIPT: (STATIC_ANALYSIS, DYNAMIC_DETONATION),
}

# Where an unroutable / unknown class goes. A hand-off to Story 1.4, never a crash.
_SAFE_REJECT_PLAN: tuple[str, ...] = (SAFE_REJECT,)


def route(artifact_class: str | None) -> dict[str, Any]:
    """Map a classification label to a routing decision (a plan of controls).

    Returns the ``routing`` object of the routing contract:
    ``artifact_class``, ``lanes`` (ordered, de-duplicated), ``routable``,
    ``basis``, and an optional ``notes`` string.

    This is a PLAN OF CONTROLS only — never a verdict, never a forward-to-PDE
    decision, never a safety claim.

    An unrecognised / missing class is not an error: it fails safe to the
    safe-reject entry (Story 1.4), recording the original class it saw for audit.
    """
    lanes = _ROUTING_TABLE.get(artifact_class)  # type: ignore[arg-type]

    if lanes is not None:
        return {
            # Echo the class the plan was derived from (a known routable class).
            "artifact_class": artifact_class,
            "lanes": list(lanes),
            "routable": True,
            "basis": "class_route",
        }

    # Unroutable: other_unknown OR any unrecognised/missing class. Hand to 1.4.
    # The contract's artifact_class enum only allows the three known classes, so a
    # truly unrecognised input is normalised to other_unknown for the record while
    # the note preserves what was actually seen (bounded, non-executable).
    is_known_unknown = artifact_class == OTHER_UNKNOWN
    decision: dict[str, Any] = {
        "artifact_class": OTHER_UNKNOWN,
        "lanes": list(_SAFE_REJECT_PLAN),
        "routable": False,
        "basis": "safe_reject_fallback",
    }
    if is_known_unknown:
        decision["notes"] = "class other_unknown is unroutable; handed to safe-reject (1.4)"
    else:
        # Preserve the offending value (bounded) so an unexpected class is auditable
        # rather than silently swallowed — but still route safely, never crash.
        seen = "missing" if artifact_class is None else repr(str(artifact_class))[:64]
        decision["notes"] = f"unrecognised class {seen}; failed safe to safe-reject (1.4)"
    return decision
