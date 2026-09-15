# Session Brief — TEMPLATE (stakeholder-facing)

> **Purpose.** The stakeholder-facing spec and the change/audit record for the story. Kiro generates this at the end of the prior session. 

---

<STORY_IDENTITY>
## Story {{ID}} — {{Title}}

| Field | Value |
|-------|-------|
| **Phase** | {{Phase — e.g., P2 — Parallel Inspection}} |
| **Date** | {{Date or TBD (next session)}} |
| **Status** | ⬜ Not Started |
| **Builds from restore point** | {{Restore tag this builds from, e.g., restore/story-2.0-green}} |
| **Session goal** | {{1-2 sentences summarizing the core objective of the story}} |
</STORY_IDENTITY>

<STRATEGIC_CONTEXT>
### Background & Context
{{Where this story fits in the broader phase and why it is being worked now.}}

### Objective & Value
- **Objective:** {{What exactly is being built (contract-first).}}
- **Why it matters:** {{The value it provides to the pipeline.}}

### Scope, Dependencies & Position
- **In scope:** {{Specific files, logic, and AWS services.}}
- **Out of scope / do NOT touch:** {{Explicit negative scope constraints.}}
- **Depends on:** {{List of required prior stories, e.g., 2.1 ✅}}
- **Unblocks:** {{What subsequent stories rely on this.}}
</STRATEGIC_CONTEXT>

<EXECUTION_CONSTRAINTS>
### Approach & Constraints
- **Deterministic Security:** Do NOT use LLM prompt-based secret scanning. The execution agent MUST rely on the local `gitleaks detect` pre-commit gate.
- **Roles:** The STAKEHOLDER executes live commands in AWS CloudShell; the EXECUTOR records verbatim. 
- **Adversarial Design:** The Plan First Gate must include an Adversarial Edge-Case Analysis defining failure modes before code generation.
</EXECUTION_CONSTRAINTS>

<COMPLIANCE_AND_ARTIFACTS>
### Validation Rationale & Compliance Mapping (REQUIRED — RD-014)
- **Rationale:** {{Why this step secures the pipeline.}}
- **Candidate control mappings:**

| Framework | Control ID | Control Name | Rationale | Status |
|-----------|-----------|--------------|-----------|--------|
| NIST 800-53 r5 | {{ID}} | {{Name}} | {{Rationale}} | Proposed |
| ISO 27001:2022 | {{ID}} | {{Name}} | {{Rationale}} | Proposed |
| NIST CSF | {{ID}} | {{Name}} | {{Rationale}} | Proposed |

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
  1. {{Specific check 1}}
  2. {{Specific check 2}}
- **Validated by:** the stakeholder, live; the executor recorded verbatim.
- **Independent validation (RD-052):** the live-validation runbook + its pass/fail DoD are authored INDEPENDENTLY by the Planner brain (Gemini) — not the builder — from the raw diff + the stakeholder's own requirement, via `docs/GEMINI_VALIDATION_PACKAGE_TEMPLATE.md`. The stakeholder runs it and reads the raw output; a human still reviews any security-critical boundary (see METHODOLOGY §4a).
- **Validation Result:** `pending`.
</VALIDATION_GATE>

<CARRY_FORWARD>
### Lessons Learned (from the prior session)
- **Bugs & Fixes:** {{Any live-found defects and how they were resolved.}}
- **Operational Nuances:** {{Terminal or AWS quirks discovered.}}
</CARRY_FORWARD>
