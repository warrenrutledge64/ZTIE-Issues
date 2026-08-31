"""ZTIE Story 2.1 — which static tools run for which artifact class (PURE logic).

A small declarative table (the 1.3 router lesson: data, not if/else) mapping the
classification label to the set of static tools the lane runs. Pure + offline-
testable; no AWS, no subprocess.

  * iac_template -> cfn-lint (lint), cfn-guard (policy-as-code), checkov (IaC
    misconfiguration).
  * raw_script   -> bandit (Python SAST), checkov (config / secret scanning).

other_unknown never reaches the static lane (Phase 1 safe-rejects it), so it maps
to an empty plan; an unrecognised class also maps to empty (fail-safe — the lane
records that nothing ran rather than crashing).
"""

from __future__ import annotations

from normalize import BANDIT, CFN_GUARD, CFN_LINT, CHECKOV

IAC_TEMPLATE = "iac_template"
RAW_SCRIPT = "raw_script"

# tuple (immutable) so the plan cannot be mutated at runtime.
_TOOL_PLAN: dict[str, tuple[str, ...]] = {
    IAC_TEMPLATE: (CFN_LINT, CFN_GUARD, CHECKOV),
    RAW_SCRIPT: (BANDIT, CHECKOV),
}


def tools_for_class(artifact_class: str | None) -> list[str]:
    """Return the ordered list of tools to run for a class. Unknown/None -> []."""
    return list(_TOOL_PLAN.get(artifact_class, ()))  # type: ignore[arg-type]
