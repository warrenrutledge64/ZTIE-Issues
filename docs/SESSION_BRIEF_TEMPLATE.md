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
| **Builds from** | {{The green tag this builds from — the latest `checkpoint/story-<id>-green` (per-story, code-only) or `restore/phase-<N>-green` (per-phase, code+state), e.g., checkpoint/story-4.7-green}} |
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
- [ ] On validation pass: create + push the per-story `checkpoint/story-{{ID}}-green` tag (annotated, code-half only, NOT in BOM.md — see RESTORE.md §Tagging convention).
- [ ] If this story CLOSES a phase: after the phase gate passes live, create `restore/phase-<N>-green` (annotated tag + verified state manifest + BOM.md index).
- [ ] Author the next-story handoff with real Lessons Learned.
</COMPLIANCE_AND_ARTIFACTS>

<VALIDATION_GATE>
### Definition of Done / Validation Gate
> A pass/fail gate, not a description. The stakeholder validates live; the executor records.

- **Done means:** 
  1. {{Specific check 1}}
  2. {{Specific check 2}}
- **Validated by:** the stakeholder, live; the executor recorded verbatim.
- **Independent validation (RD-052 + RD-053 + RD-055, 4-stage loop):** the DoD + live runbook are authored INDEPENDENTLY by Gemini — not the builder — **from scratch, blind**, from the raw diff **the stakeholder fetches independently from the repository API** + the stakeholder's own requirement, via `docs/GEMINI_VALIDATION_PACKAGE_TEMPLATE.md`. **RD-055 (zero-trust supply chain):** Kiro's validation handoff is the **PR NUMBER ONLY** — Kiro provides no raw diff, no diff-fetch command, no code snippets, and authors no live runbook / test script. The stakeholder runs it on live AWS and pastes the raw output back to Gemini, who adjudicates PASS/FAIL/INCONCLUSIVE; Kiro is a write-only scribe that records an explicit PASS verbatim. **Security-boundary hard rules:** the boundary must be POSITIVELY exercised live (a scanner `count: 0` on a planted payload = INCONCLUSIVE, never PASS); redaction is proven only by a human reading the RAW JSON, not a `REDACTED-OK` tag (see METHODOLOGY §4a–4b + PROJECT_PLAN RD-055).
- **Validation Result:** `pending`.
</VALIDATION_GATE>

<CARRY_FORWARD>
### Lessons Learned (from the prior session)
- **Bugs & Fixes:** {{Any live-found defects and how they were resolved.}}
- **Operational Nuances:** {{Terminal or AWS quirks discovered.}}
</CARRY_FORWARD>
