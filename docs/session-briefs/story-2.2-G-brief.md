# Session Brief — Story 2.2-G (Gitleaks Integration)

> **Purpose.** The stakeholder-facing spec and the change/audit record for the story. Kiro generates this at the end of the prior session. 

---

<STORY_IDENTITY>
## Story 2.2-G — Gitleaks Integration (Static Lane)

| Field | Value |
|-------|-------|
| **Phase** | P2 — Parallel Inspection |
| **Date** | TBD (next session) |
| **Status** | ⬜ Not Started |
| **Builds from restore point** | restore/story-2.2-green |
| **Session goal** | Integrate the `gitleaks` binary into the static scan container to provide deterministic, signature-based secret detection, replacing any need for custom regex scanners, and normalize its output to the existing contract. |
</STORY_IDENTITY>

<STRATEGIC_CONTEXT>
### Background & Context
Story 2.2 required signature-based scans for secret patterns per the detect-secrets/gitleaks families. This story formally embeds the compiled Gitleaks binary into the `ZtieStaticScanStack` container image, aligning with the existing toolplan architecture and avoiding non-deterministic AI-based secret scanning.

### Objective & Value
- **Objective:** Add `gitleaks` to the static lane container alongside `cfn-lint`, `cfn-guard`, `checkov`, and `bandit`. Invoke it via the subprocess wrapper and normalize its output into the shared `static-findings.contract.v1.json` schema.
- **Why it matters:** It satisfies the Story 2.2 mandate using a best-in-class compiled tool rather than fragile custom regex logic, ensuring no secret-scanning relies on non-deterministic evaluation.

### Scope, Dependencies & Position
- **In scope:** `lambdas/static_scan/Dockerfile`, `lambdas/static_scan/scanners.py`, `lambdas/static_scan/normalize.py`, and `lambdas/static_scan/toolplan.py`.
- **Out of scope / do NOT touch:** The dynamic detonation lane, Hub ingest gate, Phase 3 aggregation logic, or the foundational subprocess architecture. Do NOT create a new lane.
- **Depends on:** Story 2.1 ✅, Story 2.2 ✅
- **Unblocks:** Enhanced static telemetry for Phase 3 correlation (Story 3.2).
</STRATEGIC_CONTEXT>

<EXECUTION_CONSTRAINTS>
### Approach & Constraints
- **Deterministic Security:** Do NOT use LLM prompt-based secret scanning. The execution agent MUST rely on the local `gitleaks detect` pre-commit gate for repo safety during development.
- **Roles:** The STAKEHOLDER executes live commands in AWS CloudShell; the EXECUTOR records verbatim. 
- **Adversarial Design:** The Plan First Gate must include an Adversarial Edge-Case Analysis defining failure modes (e.g., malformed Gitleaks JSON output, exit codes > 1) before code generation.
</EXECUTION_CONSTRAINTS>

<COMPLIANCE_AND_ARTIFACTS>
### Validation Rationale & Compliance Mapping (REQUIRED — RD-014)
- **Rationale:** Embedding a compiled secret scanner within the isolated Forensic environment enforces deterministic, reproducible discovery of leaked credentials before dynamic detonation, ensuring malicious artifacts do not expose keys during runtime.
- **Candidate control mappings:**

| Framework | Control ID | Control Name | Rationale | Status |
|-----------|-----------|--------------|-----------|--------|
| NIST 800-53 r5 | SA-11 | Developer Security Testing | Integrates static secret scanning into the CI/CD analysis pipeline. | Proposed |
| NIST 800-53 r5 | SI-4 | System Monitoring | Monitors the contents of submitted artifacts for unauthorized data (secrets). | Proposed |
| ISO 27001:2022 | A.8.28 | Secure coding | Validates that submitted code adheres to secure principles (no hardcoded secrets). | Proposed |
| ISO 27001:2022 | A.8.16 | Monitoring activities | Scans submitted artifacts for anomalies or exposed credentials. | Proposed |
| NIST CSF | PR.DS-1 | Data-at-rest is protected | Ensures sensitive data (keys/secrets) are identified and prevented from unauthorized exposure. | Proposed |

### Management-Artifact Obligations (REQUIRED — RD-015)
- [ ] Story's brief + runbook entry updated (status 🟡, Validation Result pending).
- [ ] PROJECT_PLAN and RUNBOOK in exact alignment.
- [ ] Any new/changed registered decisions recorded.
- [ ] All doc changes PR-reviewed (never straight to main).
- [ ] On validation pass: record Validation Result + flip ✅ (paired commit).
- [ ] Author the next-story handoff with real Lessons Learned.
</COMPLIANCE_AND_ARTIFACTS>

<VALIDATION_GATE>
### Definition of Done / Validation Gate
> A pass/fail gate, not a description. The stakeholder validates live; the executor records.

- **Done means:** 
  1. The Gitleaks binary is successfully downloaded and executable within the static scan container image.
  2. A known-bad artifact containing a planted secret triggers a Gitleaks finding.
  3. The Gitleaks finding is successfully normalized into the `static-findings.contract.v1` shape and reflected in the bounded Hub summary.
  4. **Caveat Enforcement:** If Gitleaks errors out (e.g., exit code > 1 for reasons other than finding a leak), record it as a tool error in the summary; do not crash the lane.
- **Validated by:** the stakeholder, live; the executor recorded verbatim.
- **Validation Result:** `pending`.
</VALIDATION_GATE>

<CARRY_FORWARD>
### Lessons Learned (from the prior session)
- **Bugs & Fixes:** (To be populated by the agent concluding the prior session)
- **Operational Nuances:** (To be populated by the agent concluding the prior session)
</CARRY_FORWARD>
