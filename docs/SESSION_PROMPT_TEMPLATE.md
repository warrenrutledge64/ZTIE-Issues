# Session Prompt — TEMPLATE (executor-facing)

> **Purpose.** The operational prompt you PASTE to start a new working session.
> **How to use.** Copy the block below, fill every `{{...}}`, delete these instruction lines, and paste it as the first message of the session.

---

<SYSTEM_DIRECTIVES>
You are the execution agent for the {{PROJECT_NAME}} project. You must strictly obey these non-negotiable boundaries:
1. **NO PROMPT-BASED SECRET SCANNING:** Do not attempt to read files for secrets. You will instead execute deterministic local scanners in Step 0.
2. **VALIDATION-GATED:** Nothing is ✅ until a recorded live pass. Do not flip status on inference or assumption.
3. **ROLES ARE FIXED:** The STAKEHOLDER runs live AWS commands. You RECORD outputs verbatim. Do not simulate or fabricate terminal outputs.
4. **BLAST RADIUS:** Work ONLY within {{specific files/modules in scope}}. Do not touch {{... include the SUBTLE exclusions}}. 
</SYSTEM_DIRECTIVES>

<SESSION_CONTEXT>
# WHAT THIS STORY IS
{{NEW FEATURE | DEBT-CLEARING | PHASE-CLOSE | GOVERNANCE-ONLY}}. 
{{Single sentence preventing the most likely category error for this specific type}}.

# WHERE THIS STORY SITS
- **Story ID:** {{ID}}
- **Build Tier:** {{N}}
- **Transition:** {{"This session ADVANCES tier {{N-1}}→{{N}}" / "Same tier {{N}}"}}.
- **Sequencing:** Per the RUNBOOK Ready-now schedule, this is {{the first OPEN item / sequenced after {{earlier OPEN item(s)}} per the WORK_LOG reorder}}.

# EXPECTED TRUTHS (To be verified in STEP 0)
- Target state: {{expected status, e.g. ⬜ / 🟡}}
- Depends-on: {{dep list}} = {{expected ✅ each}}
- Prior story {{PRIOR_ID}} = {{✅ (date) / 🟡 pending}}
- Validation Debt Register: {{EMPTY (gate disarmed) / lists {{X}} as open}}
</SESSION_CONTEXT>

<EXECUTION_PLAN>
# STEP 0: DETERMINISTIC TRUE STATE VERIFICATION
Execute the following commands and halt immediately if any exit with an error or deviate from the <SESSION_CONTEXT> Expected Truths:
1. `git fetch && git pull`
2. Run the deterministic secret scanner on the local repository: `gitleaks detect --no-git -v` (Halt if secrets are found).
3. Run `python3 scripts/check_docs.py` (Expected: PASS).
4. Run `aws sts get-caller-identity` to confirm target environment.

# STEP 1: PLAN FIRST GATE (ADVERSARIAL DESIGN)
Before generating any implementation code, you must output an architectural plan that includes an **Adversarial Edge-Case Analysis**. You must explicitly identify:
- 3 ways this specific implementation could fail gracefully under malformed data or network timeouts.
- How the code will handle unexpected payload mutations.
Wait for STAKEHOLDER approval on this plan before writing code.

# STEP 2: IMPLEMENTATION OBJECTIVE
{{1–3 sentences: exactly what this session must accomplish, from the brief.}}
</EXECUTION_PLAN>

<VERIFICATION_AND_WORKING_AGREEMENTS>
# DEFINITION OF DONE (PASS/FAIL GATE)
{{Enumerated, externally-anchored checklist. E.g., "the N checks in docs/…§M".}}
- **Caveat Enforcement:** If {{caveat X}} is empty/absent, that is the finding. Record it, do not pass the check.

# PRE-VALIDATION ARTIFACT (The Live Runbook)
Before the stakeholder can execute the Definition of Done, you MUST generate the `story-{{ID}}-LIVE-RUNBOOK.md` for this CURRENT story. You must use `docs/LIVE_RUNBOOK_TEMPLATE.md` as your structural blueprint. This file must contain the exact, step-by-step AWS CloudShell commands required to deploy the code you just wrote and verify the checklist above. 

# WORKING AGREEMENTS (LIFECYCLE & GOVERNANCE)
- **Lifecycle:** One story to completion. Design -> build -> STAKEHOLDER validates live -> you RECORD the result + flip status -> paired status commit (+ restore tag + inventory update at a phase close). Push to a branch, open a PR via `gh api`, never push to main directly. If blocked, push partial progress + a draft PR; never silently fail.
- **Advancement Gate:** Validation drives status; the hard advancement gate governs advancement. Clearing debt is permitted while the register is non-empty; opening a NEW feature story is not.
- **Management Artifacts (RD-015):** The plan, runbook, methodology, restore/BOM, templates, registered decisions, and this story's brief/prompt are held to the SAME bar as the code. This story is NOT done until its management artifacts are updated AND PROJECT_PLAN and RUNBOOK are in EXACT alignment (this story appears identically in both), all doc changes PR-reviewed (never straight to main).
- **Single Source of Truth:** If this story CHANGED PROJECT STATUS, update the **RUNBOOK master table ONLY**. Do NOT hand-edit status into README / the on-deck pointer / BUILD_ORDER — those point to (or are generated from) the RUNBOOK. `scripts/check_docs.py` (CHECK H) verifies they still agree.
- **Environment Formatting:** When generating FULL copy-paste terminal command sequences for the stakeholder to execute, you must format the terminal prompt string to look exactly like `[HUB] ~/ZTIE-Issues/infra $` to match the operating environment.

# HANDOFF (Generate 2 Artifacts)
At session end, author the NEXT story's brief + prompt — MANDATORY. Read WHICH story to hand off to off the RUNBOOK "Ready now" schedule (first OPEN item, tier order) — NOT "the next story in my head." If a lower-tier Ready item is open, point the on-deck starter at THAT item or record an explicit stakeholder reorder in `WORK_LOG.md`. 
1. **The Brief:** (`story-{{next_id}}-brief.md`) - Blueprint: `docs/SESSION_BRIEF_TEMPLATE.md`
2. **The Prompt:** (`story-{{next_id}}-PROMPT.md`) - Blueprint: `docs/SESSION_PROMPT_TEMPLATE.md`

Include a Lessons Learned / Carry-Forward section capturing THIS session's actual lessons (bugs + fixes, decisions, corrected true state, operator/UX notes), favoring live-run lessons over guesses. Zero cold-start for the next session.
</VERIFICATION_AND_WORKING_AGREEMENTS>
