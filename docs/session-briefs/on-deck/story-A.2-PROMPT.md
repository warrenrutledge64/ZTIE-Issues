Story A.2 (executor-facing) - ON DECK for the next session
You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting. Do NOT change anything until you have (a) READ the
plan + runbook + methodology + this story's brief, (b) re-established true state
(STEP 0), and (c) confirmed the Validation Debt register still holds 2.0 as its one
open entry.

> This is the ON-DECK copy of the A.2 starter, refreshed with the true state at the
> end of the prior session. It lives at docs/session-briefs/on-deck/ and mirrors the
> style of docs/session-briefs/story-A.2-PROMPT.md. It supersedes that earlier copy
> where they differ (this one reflects the runbook reshape). Zero cold-start.

# PROJECT IDENTITY
ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted
artifact BEFORE it reaches the PDE. Work is tracked as validation-gated stories:
nothing is done until a recorded live pass (the covenant). Three accounts:
Pipeline-Hub (641628980935), Forensic (360999005254), Pipeline-Sandbox (586917955591).

# THE METHOD (named last session; know it before you start)
The project runs Foundation-First, Component-Driven Development (METHODOLOGY.md
section 1a): hardened, reusable foundations are built and PROVEN before feature work
lands on them. Build order is Dependency-Driven Sequencing (build tiers, not story
numbers). The operating loop (docs/governance/OPERATING_MODEL.md): the AI recommends
ONE next story with a one-line reason; the stakeholder decides go / not-yet / do-Z;
work is single-threaded and validated live before anything new starts. The current
recommendation (docs/governance/WORK_LOG.md, recommendation 1) is exactly this:
validate and harden Story 2.0.

# WHAT A.2 IS
The REGISTER-CLEARING live validation of Story 2.0. Story 2.0 (the Forensic AWS infra
foundation) was built and deployed once but NEVER live-validated, so the G-3 hard
advancement gate has parked it as the single entry in the Validation Debt register.
That gate blocks ALL new feature work (2.2, 2.3, ...) while the register is
non-empty, but it EXPLICITLY PERMITS reworking/validating an existing in-progress
story to clear its debt. A.2 is exactly that: run 2.0's 7 Definition-of-Done checks
live, record the result, flip 2.0 done, and REMOVE the 2.0 row from the register
(removing the row is how the register clears). A.2 is NOT a new feature story.

# NON-NEGOTIABLE CONSTRAINTS
- NEVER validate on inference. 2.0 flips done and its register row is removed ONLY
  after EVERY one of the 7 DoD checks has a recorded live PASS. Recording an
  unverified pass is the exact drift the covenant forbids (METHODOLOGY section 4).
- THE LIVE COMMANDS ARE THE STAKEHOLDER'S ACTION. The executor has NO live AWS creds.
  The stakeholder runs the checks in the FORENSIC CloudShell; the executor RECORDS the
  returned results verbatim. Do NOT simulate, assume, or fill in outputs.
- RUN `aws sts get-caller-identity` BEFORE the check block to confirm the account is
  Forensic 360999005254. ZtieForensicInfraStack is in Forensic; a banner comment does
  NOT change the account, and the operator has repeatedly run blocks in the wrong
  account. Also: /tmp is wiped when CloudShell recycles, so regenerate any exported
  file in a new session.
- DO NOT START ANY NEW FEATURE STORY (2.2+) while the register is non-empty. A.2
  clears the gate; it does not walk through it. New feature work is a later session.
- GOVERNANCE RECORDS ONLY. Do NOT touch pipeline/infra/lambda code. A.2 records a live
  validation of already-deployed 2.0 infra and updates governance docs.
- DOCS ARE FIRST-CLASS (RD-015): PR-reviewed, never straight to main; keep
  PROJECT_PLAN and RUNBOOK aligned (see the alignment note below).
- STORY CLOSURE is DECOUPLED from RESTORE-POINT WORK. 2.0's done is driven solely by
  2.0's own 7-check validation; it is NOT contingent on the A.4 deployed-state capture
  (separate work).

# THIS SESSION'S OBJECTIVE
Take Story 2.0 through its 7 DoD checks live in Forensic 360999005254 and clear the
register. The 7 checks are enumerated authoritatively in
docs/governance/FLOOR_AND_HARVEST_PLAN.md section 6 (reference section 6; do not
re-derive them):
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

Optional HARDENING (proposal, accepted by the stakeholder; not a redesign). Where
practical, also prove the NEGATIVES, not just the presence of controls:
- an instance in the detonation subnet CANNOT reach the internet (isolation holds);
- the instance role CANNOT assume anything but its own (no lateral escape);
- the 5-minute TTL ACTUALLY terminates the instance (the fail-safe truly fires).
Record any hardening proof alongside the 7 checks; it strengthens, it does not gate.

On all 7 PASS: record the dated Validation Result, flip 2.0 done, REMOVE the 2.0 row
from the Validation Debt register, and tag `restore/story-2.0-green`. On ANY fail:
stay on 2.0, fix, re-validate.

# WHERE TO EDIT ON A PASS (the runbook was reshaped last session; edit the RIGHT places)
Last session RUNBOOK.md became a single pane of glass and the full per-story detail
moved into docs/STORY_DETAIL.md. So closing 2.0 now touches FOUR places:
1. RUNBOOK.md master table (under "## Build order (dependency-driven)"): 2.0's Status
   cell in-progress -> done, plus its Completed date and Restore tag.
2. RUNBOOK.md detail index (started-stories index): update the bold 2.0 paragraph's
   status marker.
3. docs/STORY_DETAIL.md, anchor story-2-0: update the 2.0 heading and write the dated
   Validation Result line verbatim (the audit trail lives here now).
4. RUNBOOK.md Validation Debt Register: REMOVE the 2.0 row (this is how the gate
   reopens; leaving the row keeps new feature work blocked).
Then re-run the checker (below) and confirm PASS.

# STEP 0: RE-ESTABLISH TRUE STATE (before any edit)
- git fetch; confirm you are on latest main; list open PRs.
- Confirm current status truths (do NOT change them until validated):
    2.0 = in-progress (built, deployed once, NEVER live-validated, the ONE open
    register entry, the target of this session); 2.1 = done (validated live
    2026-09-01); G-3 = in-progress (its own validation is stakeholder-run and still
    pending, but it is NOT a blocker for A.2); restore tags restore/phase-1-green and
    restore/story-2.1-green exist; deployed-state restore NOT yet captured (BOM has
    ~11 pending rows; feature/restore-targets-phase2 built, unmerged).
- Confirm the Validation Debt register (top of RUNBOOK.md) still lists 2.0 as its
  single open entry, and that the G-3 hard advancement gate is in place.
- Run `/root/.pyenv/versions/3.12.13/bin/python scripts/check_docs.py` on the clean
  tree and confirm it exits 0 before you start. Branch off main (or
  restore/story-2.1-green). Branch name: e.g. docs/story-a2-validate-2.0.

# SCOPE & GUARDRAILS
- In scope: running the 7 DoD checks live (section 6, the stakeholder's action) plus
  optional hardening proof; recording the dated Validation Result in
  docs/STORY_DETAIL.md (story-2-0); flipping 2.0 done in the RUNBOOK master table +
  detail index (paired commit); REMOVING the 2.0 row from the Validation Debt
  register; tagging restore/story-2.0-green; keeping PROJECT_PLAN aligned to RUNBOOK.
- Out of scope: any NEW feature story (2.2+); A.4 deployed-state capture; the harvest
  inventory / archive (Phases B/C); any pipeline/infra/lambda code change; the
  parked portfolio-dashboard concept (PR #37 draft - do NOT start it).
- Do NOT flip 2.0 or remove its register row until ALL 7 checks have a recorded pass.
  Do NOT start feature work until the register is empty.

# DEFINITION OF DONE: PASS/FAIL GATE
1. All 7 DoD checks (section 6) recorded PASS live in Forensic 360999005254 (plus any
   optional hardening proof).
2. Dated Validation Result written verbatim in docs/STORY_DETAIL.md (story-2-0).
3. 2.0 flipped in-progress -> done (Completed date + restore tag) in the RUNBOOK
   master table AND detail index, in a paired status commit; PROJECT_PLAN aligned.
4. The 2.0 row REMOVED from the Validation Debt register (the register then empty).
5. `restore/story-2.0-green` tagged on the paired status commit.
6. `check_docs.py` re-run and PASS after the edits.
- Goes done ONLY when the STAKEHOLDER confirms a live pass on all 7 checks AND it is
  RECORDED. On any fail: stay on 2.0, fix, re-validate. No advancement.

# ALIGNMENT NOTE (decided last session)
RUNBOOK.md is the project's SOURCE OF TRUTH; PROJECT_PLAN.md aligns to it (the
stakeholder is a PMP and keeps the plan as a governing artifact organized by phase,
while the runbook is organized by build order). A follow-up to REWRITE PROJECT_PLAN
to align to the runbook was AGREED but NOT yet done - it is a pending carry-forward,
not part of A.2. Same facts, different views: the plan orders by phase, the runbook
by build order; neither is reordered to match the other, and status lives only in the
runbook.

# ENVIRONMENT
- Repo cloned; push to a branch (e.g. docs/story-a2-validate-2.0), never main. Open
  PRs via `gh api repos/warrenrutledge64/ZTIE-Issues/pulls` (NOT `gh pr create`).
  Merges are the repo-owner's action.
- Live AWS is the STAKEHOLDER's action in the Forensic CloudShell (executor has no
  creds). Present each section-6 command block with the account banner (360999005254),
  tell the operator to run `aws sts get-caller-identity` first and to run ONE line at
  a time, and wait for the returned output before recording anything.
- Offline for tooling: doc-consistency runs use stdlib only via the 3.12 interpreter
  at /root/.pyenv/versions/3.12.13/bin/python; keep ruff clean.

# WORKING AGREEMENT
- One story to completion: STAKEHOLDER validates live (7 checks) -> executor RECORDS
  the result -> flip 2.0 done (master table + detail index + STORY_DETAIL) + REMOVE
  its register row -> paired status commit + tag restore/story-2.0-green. Push to a
  branch; open a PR.
- Validation drives status; the G-3 hard advancement gate governs advancement.
  Clearing the register is the goal of this session and is exactly what the gate
  permits; opening a new feature story is not.
- Management artifacts first-class (RD-015): the Validation Debt register updated (2.0
  row removed); RUNBOOK and PROJECT_PLAN aligned; all via PR.
- At session end, author the NEXT story's brief + prompt with real Lessons Learned.
  With the register empty after A.2, the reopened gate permits the next move (per
  FLOOR_AND_HARVEST_PLAN section 4: A.3 confirm 2.1 / A.4 capture, then feature work
  the new way, e.g. the 2.3 detonation critical path vs 2.2 static line - the AI
  recommends one with a reason and the stakeholder decides). Zero cold-start.
- If blocked, push partial progress + a draft PR; never silently fail.

# CARRY-FORWARD FROM THE PRIOR SESSION (what actually happened)
- The prior session was governance/documentation only (no pipeline code). Merged:
  the build-tier RUNBOOK reorg (PR #34), the naming of the development philosophy
  (PR #35, METHODOLOGY section 1a), and the single-pane-of-glass RUNBOOK reshape with
  the new docs/STORY_DETAIL.md companion (PR #36). Also landed the operating model,
  build-order, and work-log docs. Parked: the portfolio-dashboard concept on the
  Dashboard branch (PR #37, draft, NOT started).
- Corrected true state: RUNBOOK is now the single pane of glass and the source of
  truth; the full per-story detail lives in docs/STORY_DETAIL.md; status lives only
  in the RUNBOOK.
- Reinforced lessons: story-number order is NOT build order (use build tiers /
  dependency order); the covenant + G-3 gate mean the ONLY permitted next move is
  clearing the 2.0 debt by validating it; no new feature story until then.
- Pending carry-forward watch-items (NOT part of A.2): (a) rewrite PROJECT_PLAN to
  align to the runbook (agreed, not done); (b) G-3's own validation still pending
  (stakeholder runs check_docs.py / reviews); (c) portfolio dashboard parked in PR
  #37 as a future SEPARATE project - do not start it; (d) deployed-state restore
  capture (Floor & Harvest A.4) and BOM pending rows remain open but are NOT
  prerequisites for closing 2.0.
