Story G-3 (executor-facing)
You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting. Do NOT change anything until you have (a) READ the
plan + runbook + methodology, (b) re-established true state (STEP 0), and (c)
confirmed there is no dependency blocking G-3.

# PROJECT IDENTITY
ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted
artifact BEFORE it reaches the PDE. Work is tracked as validation-gated stories:
nothing is ✅ until a recorded live pass (the covenant). Three accounts: Pipeline-Hub
(641628980935), Forensic (360999005254), Pipeline-Sandbox (586917955591).

# WHAT G-3 IS
A CROSS-CUTTING GOVERNANCE story. It does NOT build pipeline features. It ENCODES the
"hard pause" so an un-validated story can never silently slip through the cracks —
turning a verbal, in-the-moment pause into a structural, machine-checkable mechanism.
Division of labor agreed with the stakeholder: the EXECUTOR OWNS CALLING hard pauses
(surfacing when we must stop to validate/back up/consolidate); the STAKEHOLDER
retains final say to accept/defer/override. G-3 gives that pause teeth.

# NON-NEGOTIABLE CONSTRAINTS
- DOCS + TOOLING ONLY. No pipeline/infra/runtime code. No deploys.
- NEVER validate on inference. G-3 RECORDS and ENFORCES state; it must NEVER flip a
  story (esp. 2.0) to ✅. The Validation Debt register entry for a story is cleared
  ONLY by that story's real, recorded live validation. Wanting to "resolve" open work
  on paper is the exact drift the covenant forbids (METHODOLOGY §4).
- PYTHON-FIRST for any tooling (project standard). Bash only for trivial glue.
- DOCS ARE FIRST-CLASS (RD-015): PR-reviewed, never straight to main; keep
  PROJECT_PLAN ↔ RUNBOOK in EXACT alignment.
- STORY CLOSURE ≠ RESTORE-POINT WORK. A story is done when ITS OWN validation passes —
  never contingent on downstream restore/capture/archive work. G-3 must state this
  explicitly so no story is ever held hostage to later work.

# THIS SESSION'S OBJECTIVE
Add three enforcement artifacts and wire them to the automated checker:
1. VALIDATION DEBT REGISTER — a section at the TOP of RUNBOOK.md: a table of every
   built-but-not-live-validated story (🟡/⛔), why it is not done, the SINGLE action
   to clear it, and owner. SEED it with the one current entry:
     2.0 — AWS infra foundation → clear by running its 7 DoD checks live (see
     docs/governance/FLOOR_AND_HARVEST_PLAN.md §6).
2. HARD ADVANCEMENT GATE — a clause in the RUNBOOK "Validation & Advancement Gate"
   and METHODOLOGY §4: NO NEW FEATURE STORY may start while the Validation Debt
   register is non-empty. (Reworking/validating an existing 🟡 is allowed — that is
   how debt gets cleared; only NEW feature work is gated.)
3. DECOUPLING STATEMENT — in METHODOLOGY + FLOOR_AND_HARVEST_PLAN: story closure
   depends solely on that story's own validation and is independent of
   restore-point/capture work.
Then wire two checks into scripts/check_docs.py (G-2's checker):
   (a) FAIL if any 🟡 or ⛔ story is absent from the Validation Debt register;
   (b) FAIL if a NEW feature story is marked started/✅ while the register is non-empty.
If G-2's check_docs.py does NOT yet exist, either implement the minimal checker here
(Python 3.12, stdlib, unit-tested) OR specify these two checks precisely as a spec for
G-2 — and record in the brief which path you took.

# STEP 0 — RE-ESTABLISH TRUE STATE (before any edit)
- git pull; confirm you are on main's latest; list open PRs (expect none unless new).
- Confirm current status truths (do NOT change them):
    2.1 = ✅ (validated live 2026-09-01); 2.0 = 🟡 (built, deployed once, NEVER
    live-validated — this is the seed debt item); restore tags restore/phase-1-green
    + restore/story-2.1-green exist; deployed-state restore NOT yet captured
    (BOM has ~11 pending rows; feature/restore-targets-phase2 built, unmerged).
- Confirm whether scripts/check_docs.py exists (G-2). Branch off restore/story-2.1-green
  (or main at that commit). Branch name: docs/story-g3-hard-pause (or feature/story-G-3
  if it includes the checker).

# SCOPE & GUARDRAILS
- In scope: the register (RUNBOOK), the gate clause (RUNBOOK + METHODOLOGY), the
  decoupling statement (METHODOLOGY + FLOOR_AND_HARVEST_PLAN), the two checker rules,
  a candidate registered decision (RD-023: hard-pause/advancement-gate discipline) +
  candidate control mappings (RD-014), PROJECT_PLAN↔RUNBOOK alignment, the G-3 row.
- Out of scope: validating 2.0 (its own action), the archive, any feature code.
- Do NOT flip any story status. Do NOT clear the 2.0 debt entry.

# DEFINITION OF DONE — PASS/FAIL GATE
1. Validation Debt register exists in RUNBOOK.md, seeded with 2.0 (+ its single
   clearing action).
2. Advancement-gate clause (no new feature story while register non-empty) present in
   RUNBOOK gate + METHODOLOGY §4.
3. Story-closure-≠-restore-work decoupling stated in METHODOLOGY + FLOOR_AND_HARVEST_PLAN.
4. check_docs.py FAILS on an injected un-registered 🟡 AND on an injected
   new-feature-started-while-debt-open; PASSES on the clean tree. (Or, if deferred to
   G-2, the two checks are specified precisely + recorded as such.)
5. PROJECT_PLAN ↔ RUNBOOK aligned; RD-023 recorded (candidate); mappings proposed.
- Goes ✅ ONLY when the user confirms (runs the checker / reviews the docs) AND it is
  RECORDED in RUNBOOK.md. On fail: stay on G-3, fix, re-validate.

# ENVIRONMENT
- Repo cloned; push to a branch (docs/story-g3-hard-pause or feature/story-G-3), never
  main. Open PRs via `gh api repos/warrenrutledge64/ZTIE-Issues/pulls` (NOT
  `gh pr create`). Merges are the repo-owner's action.
- Offline: if you add check_docs.py, prove it with stdlib unittest (no PyPI); ruff clean.

# WORKING AGREEMENT
- One story to completion: build → USER validates (runs checker / reviews) → RECORD +
  flip status → paired status commit. Push to a branch; open a PR.
- Management artifacts first-class (RD-015): brief + RUNBOOK + PROJECT_PLAN aligned;
  RD-023 + mappings recorded; all via PR.
- Do NOT advance to any feature story from within G-3. G-3 installs the gate; it does
  not open new feature work.
- At session end, author the next story's brief + prompt with real Lessons Learned.
