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

from normalize import BANDIT, CFN_GUARD, CFN_LINT, CHECKOV, GITLEAKS, SIGNATURE_SCAN

IAC_TEMPLATE = "iac_template"
RAW_SCRIPT = "raw_script"

# tuple (immutable) so the plan cannot be mutated at runtime.
#
# Story 2.2: the SIGNATURE_SCAN engine runs for BOTH routed classes. It is
# language/format-agnostic (regex over the artifact bytes, non-executing) and
# catches known-bad patterns / IoCs (the DANGEROUS + MALWARE families) that the
# config-lint / policy / SAST tools miss — so it complements the class-specific
# tools.
#
# Story 2.2G: GITLEAKS runs for BOTH routed classes as the SOLE secret scanner
# (compiled, deterministic; it SUPERSEDES the 2.2 embedded SECRET regex rules).
# Secrets are language/format-agnostic, so gitleaks runs regardless of class.
_TOOL_PLAN: dict[str, tuple[str, ...]] = {
    IAC_TEMPLATE: (CFN_LINT, CFN_GUARD, CHECKOV, GITLEAKS, SIGNATURE_SCAN),
    RAW_SCRIPT: (BANDIT, CHECKOV, GITLEAKS, SIGNATURE_SCAN),
}


def tools_for_class(artifact_class: str | None) -> list[str]:
    """Return the ordered list of tools to run for a class. Unknown/None -> []."""
    return list(_TOOL_PLAN.get(artifact_class, ()))  # type: ignore[arg-type]
