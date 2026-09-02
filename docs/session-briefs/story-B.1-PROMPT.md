You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting. Do NOT change anything until you have (a) READ the
plan + runbook + methodology + the Floor & Harvest Plan + this story's brief
(docs/session-briefs/story-B.1-brief.md), and (b) re-established true state (STEP 0).

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
go / not-yet / do-Z; work is single-threaded and validated before anything new starts.
Current recommendation (docs/governance/WORK_LOG.md, recommendation 3): do the harvest
inventory (B.1), now that the Phase-2 floor is set and backed up.

# WHAT B.1 IS
The **Harvest Inventory** — a survey step. The Phase-2 floor is set AND backed up
(Story A.4, 2026-09-02: 2.0 ✅ + 2.1 ✅, deployed-state manifests captured +
`verify`-clean for both accounts, BOM filled, `restore/phase-2-floor-green` tagged).
Per the Floor & Harvest Plan (§2 Phase B, §4/§7), B.1 catalogs every repeated /
duplicated pattern in the repo, each with a proposed component boundary, its baked-in
defaults vs. its parameters, the call-site count it replaces, and a harvest priority,
into `docs/governance/HARVEST_INVENTORY.md`. **This inventory IS the archive's build
spec.** B.1 does NOT build the archive or refactor anything (that is Phase C). It is
NOT a new feature story.

# NON-NEGOTIABLE CONSTRAINTS
- B.1 is a REPO SURVEY: no live AWS, no infra change, no code refactor. It produces a
  reviewed catalog. The archive build and any extraction are Phase C (C.1/C.2/C.3).
- Evidence-based, not speculative. Every candidate lists REAL, observed call-sites
  (count + file references). Parameterization principles (Floor & Harvest Plan §1):
  secure/opinionated defaults are BAKED IN (not props); only real, observed variation
  becomes a prop; add a prop when a SECOND real use needs it. No speculative knobs.
- The Phase B gate is a stakeholder REVIEW-AND-ACCEPT (each candidate's parameter
  surface decided or explicitly deferred). Do NOT self-certify the inventory accepted;
  record the stakeholder's decision.
- DOCS ARE FIRST-CLASS (RD-015): PR-reviewed, never straight to main; keep PROJECT_PLAN
  and RUNBOOK facts aligned; check_docs.py must stay green.
- AWS-NATIVE ONLY for any automation (no GitHub Actions). Python by default for tooling.

# STEP 0: RE-ESTABLISH TRUE STATE (before any edit)
- git fetch; confirm latest main; list open PRs.
- Confirm status truths (do NOT change on inference):
    2.0 = ✅ (A.2, 2026-09-02; restore/story-2.0-green); 2.1 = ✅ (2026-09-01);
    Validation Debt Register = EMPTY; A.1 done (targets.py extension re-applied onto
    main via PR #40 — NOT the stale branch); A.3 confirmed; A.4 = ✅ (floor backed up,
    restore/phase-2-floor-green; BOM has ZERO pending rows; Hub manifest
    restore-manifests/manifest-20260902T201610Z.json + Forensic manifest
    restore-manifests/manifest-20260902T201931Z.json, both verify-clean).
- Run python3 scripts/check_docs.py on the clean tree; confirm it exits 0.
- Base your branch off the LATEST main that includes the A.4 merge (+ the floor tag).
  Do NOT branch off a stale restore tag or an old feature branch (the recurring
  base-branch trap; A.4's A.1 nearly reverted governance state by merging a stale
  branch — see the brief's Lessons Learned). Branch name e.g. docs/story-b1-harvest.

# THIS SESSION'S OBJECTIVE
Produce `docs/governance/HARVEST_INVENTORY.md`: survey the repo (infra/lib/*.ts, the
duplicated awsio seam across lambdas/*, the ~5 bespoke contract generators, the
hub-gate monolith and its per-envelope-kind helpers, raw inline s3.Bucket / sqs.Queue
/ lambda.Function / RestApi / Table instantiations) and catalog each candidate with:
proposed component boundary; baked-in defaults vs. parameters; call-site count +
references; harvest priority. Then hand it to the stakeholder for the Phase B
review-and-accept.

# DEFINITION OF DONE: PASS/FAIL GATE (Floor & Harvest Plan §2 Phase B)
- HARVEST_INVENTORY.md exists and catalogs every candidate with the four fields above.
- Every candidate has a decided parameter surface (or is explicitly deferred).
- Stakeholder has REVIEWED and ACCEPTED the inventory (recorded, not inferred).
- RUNBOOK ↔ PROJECT_PLAN facts aligned; check_docs green; all via PR.
- Goes done ONLY when the stakeholder confirms acceptance AND it is RECORDED.

# SCOPE & GUARDRAILS
- In scope: the survey + catalog + parameter-surface decisions + doc alignment, via PR.
- Out of scope: the archive repo / constructs (C.1/C.2), the shared seam + generator
  (C.3), any stack migration (C.4), any new feature story (2.2+), any infra/lambda code
  change, the "prove the negatives" 2.0 hardening (standing WORK_LOG proposal).

# ENVIRONMENT
- Repo cloned; push to a branch (e.g. docs/story-b1-harvest), never main. Open PRs via
  gh api repos/warrenrutledge64/ZTIE-Issues/pulls (NOT gh pr create).
- No live AWS this session. Offline for tooling: doc-consistency runs use stdlib only
  (python3); ruff clean. Sandbox python is 3.9 (annotations are future-imported, so the
  3.12-style type hints import fine); ruff lives under ~/.pyenv/versions/3.12.13/bin/ruff.

# WORKING AGREEMENT
- One story to completion: build the inventory -> push to a branch, open a PR ->
  stakeholder reviews and accepts (recorded) -> paired status note in the Floor &
  Harvest Plan.
- Management artifacts first-class (RD-015): the inventory + RUNBOOK + PROJECT_PLAN +
  Floor & Harvest Plan aligned; all via PR.
- At session end, author the NEXT story's brief + prompt (next per the plan = Phase C,
  starting C.1 stand-up-the-archive-repo, unless the stakeholder re-orders) with real
  Lessons Learned. Zero cold-start.
- If blocked, push partial progress + a draft PR; never silently fail.

# LESSONS LEARNED / CARRY-FORWARD (from Story A.4, 2026-09-02)
- Do NOT merge a stale branch to "do" a merge story. A.4's A.1 was written as "merge
  feature/restore-targets-phase2," but that branch predated the docs consolidation, the
  single-pane RUNBOOK, the G-3 gate, check_docs.py, and the Floor & Harvest Plan;
  merging it verbatim would have reverted all of it (~48-file diff). Re-apply only the
  substance onto latest main. ALWAYS diff an old branch against current main before
  adopting it.
- Give the operator fully-substituted commands, never <placeholders>: the operator
  pasted `verify --manifest <the path capture printed>` literally and bash errored; the
  verify didn't run. Also have them cd ~/ZTIE-Issues first (a verify run from ~ failed
  file-not-found) and echo the "$?" exit code.
- capture warns "working tree is dirty" when the fresh manifest is untracked in the
  tree — harmless for a floor capture (the tag rides the merged status commit).
- Re-runs can leave stray manifests; keep only the verified pair (one per account) and
  git rm the rest so the restore point is unambiguous.
- GitHub auth in CloudShell: token-in-URL HTTPS remote only (bare PAT-as-password is
  rejected). A PAT was pasted in the clear this session — remind the stakeholder to
  rotate it.
- Two accounts, two tabs, aws sts get-caller-identity before every block (held fine
  this session).
