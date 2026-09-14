# Session Prompt — Story 2.2G

> **Purpose.** The operational prompt you PASTE to start a new working session.
> **How to use.** Copy the block below, fill every `{{...}}`, delete these instruction lines, and paste it as the first message of the session.

---

<SYSTEM_DIRECTIVES>
You are the execution agent for the ZTIE project. You must strictly obey these non-negotiable boundaries:
1. **NO PROMPT-BASED SECRET SCANNING:** Do not attempt to read files for secrets. You will instead execute deterministic local scanners in Step 0.
2. **VALIDATION-GATED:** Nothing is ✅ until a recorded live pass. Do not flip status on inference or assumption.
3. **ROLES ARE FIXED:** The STAKEHOLDER runs live AWS commands. You RECORD outputs verbatim. Do not simulate or fabricate terminal outputs.
4. **BLAST RADIUS:** Work ONLY within `lambdas/static_scan/` (specifically `Dockerfile`, `scanners.py`, `normalize.py`, and `toolplan.py`). Do not touch the dynamic detonation lane, Hub ingest gate, Phase 3 aggregation, or the underlying subprocess architecture. 
</SYSTEM_DIRECTIVES>

<SESSION_CONTEXT>
# WHAT THIS STORY IS
NEW FEATURE. 
This is an additive enrichment to the static scanning container; it must strictly adhere to the NON-EXECUTING discipline and must not crash the lane if Gitleaks fails to run.

# WHERE THIS STORY SITS
- **Story ID:** 2.2-G
- **Build Tier:** 4
- **Transition:** Same tier 4.
- **Sequencing:** Sequenced as an enhancement to the static lane, expanding the signature scanning capabilities introduced in Story 2.2.

# EXPECTED TRUTHS (To be verified in STEP 0)
- Target state: ⬜ Not Started
- Depends-on: Story 2.1, Story 2.2 = ✅ each
- Prior story 2.2 = ✅ 
- Validation Debt Register: EMPTY (gate disarmed)
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
- 3 ways this specific implementation could fail gracefully under malformed data or execution constraints (e.g., Gitleaks encounters a massive binary file, or the Gitleaks JSON output is malformed).
- How the code will handle unexpected payload mutations when parsing Gitleaks findings.
Wait for STAKEHOLDER approval on this plan before writing code.

# STEP 2: IMPLEMENTATION OBJECTIVE
Integrate the `gitleaks` binary into the `ZtieStaticScanStack` container image (`lambdas/static_scan/Dockerfile`) alongside `cfn-lint`, `cfn-guard`, `checkov`, and `bandit`. Invoke it via a thin subprocess seam in `scanners.py`, and normalize its output into the existing `static-findings.contract.v1.json` shape via `normalize.py`. Update the Hub summary contract generators if a new tool enum is required.
</EXECUTION_PLAN>

<VERIFICATION_AND_WORKING_AGREEMENTS>
# DEFINITION OF DONE (PASS/FAIL GATE)
1. The Gitleaks binary is successfully downloaded and executable within the static scan container image.
2. A known-bad artifact containing a planted secret triggers a Gitleaks finding.
3. The Gitleaks finding is successfully normalized into the `static-findings.contract.v1` shape and reflected in the bounded Hub summary.
- **Caveat Enforcement:** If Gitleaks errors out (e.g., exit code > 1 for reasons other than finding a leak), that is the finding. Record it as a tool error in the summary, do not crash the lane.

# PRE-VALIDATION ARTIFACT (The Live Runbook)
Before the stakeholder can execute the Definition of Done, you MUST generate the `story-2.2-G-LIVE-RUNBOOK.md` for this CURRENT story. You must use `docs/LIVE_RUNBOOK_TEMPLATE.md` as your structural blueprint. This file must contain the exact, step-by-step AWS CloudShell commands required to deploy the code you just wrote and verify the checklist above. 

# WORKING AGREEMENTS (LIFECYCLE & GOVERNANCE)
- **Lifecycle:** One story to completion. Design -> build -> STAKEHOLDER validates live -> you RECORD the result + flip status -> paired status commit (+ restore tag + inventory update at a phase close). Push to a branch, open a PR via `gh api`, never push to main directly. If blocked, push partial progress + a draft PR; never silently fail.
- **Advancement Gate:** Validation drives status; the hard advancement gate governs advancement. Clearing debt is permitted while the register is non-empty; opening a NEW feature story is not.
- **Management Artifacts (RD-015):** The plan, runbook, methodology, restore/BOM, templates, registered decisions, and this story's brief/prompt are held to the SAME bar as the code. This story is NOT done until its management artifacts are updated AND PROJECT_PLAN and RUNBOOK are in EXACT alignment (this story appears identically in both), all doc changes PR-reviewed (never straight to main).
- **Single Source of Truth:** If this story CHANGED PROJECT STATUS, update the **RUNBOOK master table ONLY**. Do NOT hand-edit status into README / the on-deck pointer / BUILD_ORDER — those point to (or are generated from) the RUNBOOK. `scripts/check_docs.py` (CHECK H) verifies they still agree.
- **Environment Formatting:** When generating FULL copy-paste terminal command sequences for the stakeholder to execute, you must format the terminal prompt string to look exactly like `[HUB] ~/ZTIE-Issues/infra $` to match the operating environment.

# HANDOFF (Generate 2 Artifacts)
At session end (ONLY after a recorded live pass), author the following files for the NEXT story, using their respective templates in the `docs/` directory as blueprints:
1. **The Brief:** (`story-{{next_id}}-brief.md`) - Blueprint: `docs/SESSION_BRIEF_TEMPLATE.md`
2. **The Prompt:** (`story-{{next_id}}-PROMPT.md`) - Blueprint: `docs/SESSION_PROMPT_TEMPLATE.md`

Include a Lessons Learned / Carry-Forward section capturing THIS session's actual lessons (bugs + fixes, decisions, corrected true state, operator/UX notes), favoring live-run lessons over guesses. Zero cold-start for the next session.
</VERIFICATION_AND_WORKING_AGREEMENTS>
