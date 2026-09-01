Story A.2 (executor-facing)
You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting. Do NOT change anything until you have (a) READ the
plan + runbook + methodology + this story's brief, (b) re-established true state
(STEP 0), and (c) confirmed the Validation Debt register still holds 2.0 as its one
open entry.

# PROJECT IDENTITY
ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted
artifact BEFORE it reaches the PDE. Work is tracked as validation-gated stories:
nothing is ✅ until a recorded live pass (the covenant). Three accounts: Pipeline-Hub
(641628980935), Forensic (360999005254), Pipeline-Sandbox (586917955591).

# WHAT A.2 IS
The REGISTER-CLEARING live validation of Story 2.0. Story 2.0 (the Forensic AWS infra
foundation) was built and deployed once but NEVER live-validated, so the just-installed
G-3 hard advancement gate has parked it as the single entry in the Validation Debt
register. That gate blocks ALL new feature work (2.2, 2.3, ...) while the register is
non-empty, but it EXPLICITLY PERMITS reworking/validating an existing 🟡 to clear its
debt. A.2 is exactly that: run 2.0's 7 Definition-of-Done checks live, record the
result, flip 2.0 ✅, and REMOVE the 2.0 row from the register (removing the row is how
the register clears). A.2 is NOT a new feature story.

# NON-NEGOTIABLE CONSTRAINTS
- NEVER validate on inference. 2.0 flips ✅ and its register row is removed ONLY after
  EVERY one of the 7 DoD checks has a recorded live PASS. Recording an unverified pass
  is the exact drift the covenant forbids (METHODOLOGY §4).
- THE LIVE COMMANDS ARE THE STAKEHOLDER'S ACTION. The executor has NO live AWS creds.
  The stakeholder runs the 7 checks in the Forensic CloudShell; the executor RECORDS
  the returned results verbatim. Do NOT simulate, assume, or fill in outputs.
- DO NOT START ANY NEW FEATURE STORY (2.2+) while the register is non-empty. A.2
  clears the gate; it does not walk through it. New feature work is a later session.
- GOVERNANCE RECORDS ONLY. Do NOT touch pipeline/infra/lambda code. A.2 records a live
  validation of already-deployed 2.0 infra and updates governance docs.
- DOCS ARE FIRST-CLASS (RD-015): PR-reviewed, never straight to main; keep
  PROJECT_PLAN ↔ RUNBOOK in EXACT alignment.
- STORY CLOSURE ≠ RESTORE-POINT WORK. 2.0's ✅ is driven solely by 2.0's own 7-check
  validation; it is NOT contingent on the A.4 deployed-state capture (separate work).

# THIS SESSION'S OBJECTIVE
Take Story 2.0 through its 7 DoD checks live in Forensic 360999005254 and clear the
register. The 7 checks are enumerated authoritatively in
docs/governance/FLOOR_AND_HARVEST_PLAN.md §6 (reference §6; do not re-derive them):
1. STACK DEPLOYS: `ZtieForensicInfraStack` deploys and returns its outputs (VpcId,
   DetonationLaunchTemplateId, DetonationInstanceRoleArn, AmiParameterName).
2. ISOLATED VPC: no internet gateway and no NAT gateway attached to the VPC.
3. VPC ENDPOINTS: S3 gateway endpoint + SSM, SSMMessages, EC2Messages, Logs, SQS,
   Bedrock interface endpoints present.
4. LAUNCH TEMPLATE RESOLVES A VALID AMI VIA SSM: `$Latest` resolves an `ami-...` id
   via `/ztie/ami/ubuntu-22.04`. (Known caveat: the Ubuntu AMI was set manually and
   the AL2023 build failed; 2.0 defaults to ubuntu-22.04 so this should resolve. If
   the param is empty, that is the finding: fix or record it, do NOT pass the check.)
5. INSTANCE ROLE has `AmazonSSMManagedInstanceCore` attached.
6. USERDATA has `shutdown -h +5` (auto-terminate).
7. NO `0.0.0.0/0` ROUTE in any route table of the VPC.
On all 7 PASS: record the dated Validation Result in RUNBOOK 2.0, flip the 2.0 row
🟡 → ✅ (paired status commit), REMOVE the 2.0 row from the Validation Debt register,
and tag `restore/story-2.0-green`. On ANY fail: stay on 2.0, fix, re-validate.

# STEP 0: RE-ESTABLISH TRUE STATE (before any edit)
- git fetch; confirm latest; list open PRs (expect none unless new).
- Confirm current status truths (do NOT change them until validated):
    2.0 = 🟡 (built, deployed once, NEVER live-validated, the ONE open register
    entry, the target of this session); 2.1 = ✅ (validated live 2026-09-01); restore
    tags restore/phase-1-green + restore/story-2.1-green exist; deployed-state restore
    NOT yet captured (BOM ~11 pending rows; feature/restore-targets-phase2 built,
    unmerged).
- Confirm the Validation Debt register (top of RUNBOOK.md) still lists 2.0 as its
  single open entry, and that the G-3 hard advancement gate is in place.
- Optionally run `python scripts/check_docs.py` (via the 3.12 interpreter) on the
  clean tree to confirm it exits 0 before you start. Branch off restore/story-2.1-green
  (or main at that commit). Branch name: e.g. docs/story-a2-validate-2.0.

# SCOPE & GUARDRAILS
- In scope: running the 7 DoD checks live (§6, the stakeholder's action), recording
  the dated Validation Result in RUNBOOK 2.0, flipping 2.0 ✅ (paired commit), REMOVING
  the 2.0 row from the Validation Debt register, tagging restore/story-2.0-green,
  PROJECT_PLAN ↔ RUNBOOK alignment.
- Out of scope: any NEW feature story (2.2+); A.4 deployed-state capture; the harvest
  inventory / archive (Phases B/C); any pipeline/infra/lambda code change.
- Do NOT flip 2.0 or remove its register row until ALL 7 checks have a recorded pass.
  Do NOT start feature work until the register is empty.

# DEFINITION OF DONE: PASS/FAIL GATE
1. All 7 DoD checks (§6) recorded PASS live in Forensic 360999005254.
2. Dated Validation Result written in the RUNBOOK 2.0 detail block.
3. 2.0 row flipped 🟡 → ✅ (Completed date + restore tag) in a paired status commit;
   PROJECT_PLAN ↔ RUNBOOK aligned.
4. The 2.0 row REMOVED from the Validation Debt register (the register clears by row
   removal, after which it should be empty).
5. `restore/story-2.0-green` tagged on the paired status commit.
- Goes ✅ ONLY when the STAKEHOLDER confirms a live pass on all 7 checks AND it is
  RECORDED in RUNBOOK.md. On any fail: stay on 2.0, fix, re-validate. No advancement.

# ENVIRONMENT
- Repo cloned; push to a branch (e.g. docs/story-a2-validate-2.0), never main. Open
  PRs via `gh api repos/warrenrutledge64/ZTIE-Issues/pulls` (NOT `gh pr create`).
  Merges are the repo-owner's action.
- Live AWS is the STAKEHOLDER's action in the Forensic CloudShell (executor has no
  creds). Present each §6 command block with the account banner (360999005254) and
  wait for the stakeholder's returned output before recording anything.
- Offline for tooling: any doc-consistency runs use stdlib only (python 3.12); ruff
  clean.

# WORKING AGREEMENT
- One story to completion: STAKEHOLDER validates live (7 checks) -> executor RECORDS
  the result -> flip 2.0 ✅ + REMOVE its register row -> paired status commit + tag
  restore/story-2.0-green. Push to a branch; open a PR.
- Validation drives status; the G-3 hard advancement gate governs advancement.
  Clearing the register is the goal of this session and is exactly what the gate
  permits; opening a new feature story is not.
- Management artifacts first-class (RD-015): brief + RUNBOOK + PROJECT_PLAN aligned;
  the Validation Debt register updated (2.0 row removed); all via PR.
- At session end, author the NEXT story's brief + prompt with real Lessons Learned.
  With the register empty after A.2, the next story is the first one the reopened gate
  permits (per FLOOR_AND_HARVEST_PLAN §4: A.3 confirm 2.1 / A.4 capture, then feature
  work the new way). Zero cold-start for the next session.
- If blocked, push partial progress + a draft PR; never silently fail.
