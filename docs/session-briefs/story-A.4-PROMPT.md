You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting. Do NOT change anything until you have (a) READ the
plan + runbook + methodology + the Floor & Harvest Plan + this story's brief
(docs/session-briefs/story-A.4-brief.md), and (b) re-established true state (STEP 0).

# PROJECT IDENTITY
ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted
artifact BEFORE it reaches the PDE. Work is tracked as validation-gated stories:
nothing is done until a recorded live pass (the covenant). Three accounts:
Pipeline-Hub (641628980935), Forensic (360999005254), Pipeline-Sandbox (586917955591).

# THE METHOD (know it before you start)
Foundation-First, Component-Driven Development (METHODOLOGY.md §1a): hardened, reusable
foundations are built and PROVEN before feature work lands on them; build order is
Dependency-Driven Sequencing. Operating loop (docs/governance/OPERATING_MODEL.md): the
AI recommends ONE next story with a one-line reason; the stakeholder decides
go / not-yet / do-Z; work is single-threaded and validated live before anything new
starts. Current recommendation (docs/governance/WORK_LOG.md, recommendation 2):
institute deployed-state restore points (A.4), after the quick A.1 merge + A.3 confirm.

# WHAT A.4 IS
The step that **sets and backs up the Phase-2 floor**. Story 2.0 was validated live
(A.2, 2026-09-02) and the Validation Debt Register is now EMPTY, so the floor is
*validated* but not yet *backed up*. Per the Floor & Harvest Plan (§2 Phase A, §4),
A.4 institutes the **deployed-state restore points**: run `capture` + `verify` for
BOTH accounts, commit the manifests, fill BOM's 11 `pending` rows, and tag
`restore/phase-2-floor-green`. It folds in A.1 (merge the capture-tooling extension)
and A.3 (confirm 2.1 into the floor). A.4 is the LAST step before the harvest
inventory (B.1). It is NOT a new feature story.

# NON-NEGOTIABLE CONSTRAINTS
- NEVER validate/confirm on inference. A.3's confirmation and A.4's `verify`-clean
  results are RECORDED from what the stakeholder actually runs live — never simulated.
- THE LIVE COMMANDS ARE THE STAKEHOLDER'S ACTION. The executor has NO live AWS creds.
  A.4 `capture`/`verify` run in the stakeholder's CloudShells; the executor RECORDS
  the returned results verbatim. Do NOT simulate, assume, or fill in outputs.
- TWO ACCOUNTS, TWO SHELLS. Capture the HUB state (641628980935) from a Hub-authed
  shell and the FORENSIC state (360999005254) from a Forensic-authed shell. Run
  `aws sts get-caller-identity` BEFORE every block — a banner comment does NOT change
  the account, and the operator has repeatedly run blocks in the wrong account. Feed
  commands ONE LINE AT A TIME (never a multi-line paste). /tmp is wiped when CloudShell
  recycles — regenerate any exported file in a new session.
- VERIFY ON A PROJECTION, NOT RAW OBJECTS. `verify` must compare only the
  restore-relevant projection (identity + desired-state fields), or volatile metadata
  (SSM param version, last_modified, CFN stack status, stack_id) will false-positive
  as drift. (Learned in Story 1.R.)
- STORY CLOSURE is DECOUPLED from RESTORE-POINT WORK, but A.4's OWN deliverable IS the
  restore-point work — so A.4 closes only on its own recorded `verify`-clean + BOM +
  tag, per the RUNBOOK Close-Out Procedure.
- DOCS ARE FIRST-CLASS (RD-015): PR-reviewed, never straight to main; keep PROJECT_PLAN
  and RUNBOOK aligned; check_docs.py must stay green.
- AWS-NATIVE ONLY for any automation (no GitHub Actions). Python by default for tooling.

# STEP 0: RE-ESTABLISH TRUE STATE (before any edit)
- git fetch; confirm latest main; list open PRs.
- Confirm status truths (do NOT change on inference):
    2.0 = ✅ (validated live 2026-09-02, A.2; tag restore/story-2.0-green);
    2.1 = ✅ (validated live 2026-09-01); Validation Debt Register = EMPTY;
    A.1 = confirm whether feature/restore-targets-phase2 is NOW merged to main
    (it was unmerged at A.2 close); BOM still has 11 pending rows; no Phase-2
    deployed-state manifest captured yet.
- Run `python3 scripts/check_docs.py` on the clean tree; confirm it exits 0.
- Base your branch off the LATEST main that includes the A.2 flip AND the A.1 merge.
  Do NOT branch off a stale restore tag (the A.2 lesson: restore/story-2.1-green was
  behind main and missing the register/gate). Branch name e.g. docs/story-a4-floor-restore.

# THIS SESSION'S OBJECTIVE
Set the Phase-2 floor and back it up: (A.1) confirm the capture-tooling extension is
merged; (A.3) record the 2.1 confirmation into the floor; (A.4) drive the stakeholder's
live `capture` + `verify` for BOTH accounts, commit the manifests, fill BOM's 11
pending rows, tag restore/phase-2-floor-green, and align RUNBOOK ↔ PROJECT_PLAN.

# DEFINITION OF DONE: PASS/FAIL GATE (Floor & Harvest Plan §2 Phase A)
1. A.1 merged (feature/restore-targets-phase2 on main).
2. A.3 recorded confirmation of 2.1 (no re-run).
3. Deployed-state manifests captured + `verify`-clean for BOTH accounts (Hub + Forensic).
4. BOM's 11 `pending` rows filled (tag + SHA + manifest path each).
5. restore/phase-2-floor-green tagged; RUNBOOK ↔ PROJECT_PLAN aligned; check_docs green.
- Goes done ONLY when the STAKEHOLDER confirms live `verify`-clean on both accounts AND
  it is RECORDED. On any drift/fail: stay on A.4, fix, re-verify. No advancement to B.1.

# SCOPE & GUARDRAILS
- In scope: A.1 confirm-merged, A.3 confirm 2.1, A.4 capture/verify/BOM/tag, doc
  alignment — all via PR.
- Out of scope: harvest inventory (B.1); archive build (Phase C); any new feature story
  (2.2+); any pipeline/infra/lambda code change; the "prove the negatives" 2.0 hardening
  (standing WORK_LOG proposal, a later session).

# ENVIRONMENT
- Repo cloned; push to a branch (e.g. docs/story-a4-floor-restore), never main. Open PRs
  via `gh api repos/warrenrutledge64/ZTIE-Issues/pulls` (NOT `gh pr create`). Merges +
  restore tags are the repo-owner's action.
- Live AWS is the STAKEHOLDER's action in the Hub and Forensic CloudShells (executor has
  no creds). GitHub auth in CloudShell uses the token-in-URL HTTPS form
  (git remote set-url origin https://<TOKEN>@github.com/warrenrutledge64/ZTIE-Issues.git).
- Offline for tooling: doc-consistency runs use stdlib only (python3); ruff clean.

# WORKING AGREEMENT
- One story to completion: STAKEHOLDER runs live capture/verify (both accounts) ->
  executor RECORDS results -> fill BOM + align docs -> paired status commit; push to a
  branch, open a PR; the repo owner tags restore/phase-2-floor-green.
- Validation drives status. With the register empty the advancement gate is disarmed,
  but the covenant still holds: A.4 closes only on its own recorded live `verify`-clean.
- Management artifacts first-class (RD-015): brief + RUNBOOK + PROJECT_PLAN + BOM aligned;
  all via PR.
- At session end, author the NEXT story's brief + prompt (next = B.1 Harvest Inventory,
  per Floor & Harvest Plan §4) with real Lessons Learned. Zero cold-start.
- If blocked, push partial progress + a draft PR; never silently fail.

# LESSONS LEARNED / CARRY-FORWARD (from Story A.2, 2026-09-02)
- Fix-then-validate-once worked: the first cdk deploy failed on an SG rule description
  containing `->` (`>` is outside AWS's allowed SG-rule-description charset
  a-zA-Z0-9. _-:/()#,@[]+=&;{}!$*); fixed `->`→`to` (commit ab748be), redeployed clean,
  then validated the code we kept. Watch SG rule descriptions in any CDK stack.
- Base-branch trap: the restore/story-2.1-green tag was BEHIND main (missing the
  register/gate/plan). Always branch off the latest main that has the governance state
  you're operating on.
- Operator UX (recurs): one line at a time in CloudShell; a multi-line paste of decoded
  UserData executed the printed `shutdown -h +5` in the shell (harmless, not a check).
  Two accounts => two tabs; sts get-caller-identity before every block.
- Register clears by ROW REMOVAL: check_docs ignores an `_(empty)_` placeholder row, so
  the register parses empty and the gate disarms; keep that shape.
- Don't retro-edit history: only current-status surfaces were flipped (RUNBOOK
  table+register, README focus table, BUILD_ORDER graph/recommendation, FLOOR_AND_HARVEST
  §4 A.2 row); briefs/WORK_LOG/RD-023 rationale left as accurate past record.
- Remind the stakeholder to rotate the GitHub PAT pasted in the clear during A.2.
