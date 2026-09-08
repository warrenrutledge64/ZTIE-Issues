Story-A.6

You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting. Do NOT change anything until you have (a) READ the
plan + runbook + methodology + this story's brief (`session-briefs/story-A.6-brief.md`)
and the restore-point guide (`docs/SETTING_AND_REMOVING_RESTORE_POINTS.md`), (b)
re-established true state (STEP 0), and (c) confirmed the Validation Debt Register state
+ advancement gate.

# PROJECT IDENTITY
ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted artifact
BEFORE it reaches the PDE. Work is validation-gated: nothing is ✅ until a recorded
confirmation (the covenant). Three accounts: Pipeline-Hub (641628980935) = brains/control
plane + durable record; Forensic (360999005254) = self-contained blast zone (ephemeral
only); Pipeline-Sandbox (586917955591) = ZTIE→PDE handoff. Story A.6 is an OWNER-ACTION
restore-discipline story (RD-015): push two annotated restore tags the docs already name
but that are NOT on `origin`. It closes NO pipeline capability; it makes the Phase-2 floor
+ the 2.3 detonation lane actually backed up before 2.4.

# WHAT THIS STORY IS (nature + gate role)
OWNER-ACTION Floor & Harvest story (Track = F&H, build tier 6, Depends-on `A.4` ✅ +
`2.3` ✅). It changes NO other story's status and touches NO pipeline/infra/lambda code.
With A.5 (✅ 2026-09-08) it is the tier-6 pair that **hard-gates Story 2.4** (RUNBOOK
cross-track note, 2026-09-07 decision: `2.4` depends on `2.3` + `A.5` + `A.6`). A.6 is the
LAST gate before 2.4 can begin. It may proceed now (register empty → advancement gate
OPEN). STEP 0 must RE-CONFIRM this on `main` (trust `main` + `check_docs` over this
prompt) before acting — verify, do not assume.

# THE GAP A.6 CLOSES (read the restore-point guide first)
The governance docs (BOM §4, the Floor & Harvest Plan, RUNBOOK "Restore tag" column,
`docs/STORY_DETAIL.md#story-a-6`) reference two annotated tags AS IF THEY EXIST, but
`git ls-remote --tags origin` does NOT list them — a "phantom baseline" (the recurring gap
in `docs/SETTING_AND_REMOVING_RESTORE_POINTS.md` §6). Push them:
1. **`restore/phase-2-floor-green`** → the merged **Story A.4** status commit — the paired
   commit whose manifests are `restore-manifests/manifest-20260902T201610Z.json` (Hub, 4
   projections) + `restore-manifests/manifest-20260902T201931Z.json` (Forensic, 11
   projections). Pins the backed-up Phase-2 floor. Do NOT blindly tag the tip: a NEWER
   Forensic manifest (`restore/story-2.0E-green`, 16 projections, commit `cb6b5c5`) landed
   after the floor — the floor tag must point at the A.4 commit, not 2.0E's.
2. **`restore/story-2.3-green`** → `origin/main`'s CURRENT tip (at/after the PR #60 merge
   that flipped 2.3 ✅; later commits are docs-only and do not touch 2.3's code or its
   validation result). Verbatim commands already exist in
   `docs/session-briefs/story-2.3-restore-tag-PROMPT.md`.

# NON-NEGOTIABLE CONSTRAINTS
- OWNER ACTION for the PUSH. The executor in this sandbox has NO push rights for tags —
  it PREPARES exact copy-paste `git tag -a … -m …` + `git push origin <tag>` commands and
  VERIFIES afterward via `git ls-remote --tags origin`, but the OWNER runs the push.
- ANNOTATED tags only (`git tag -a`), never lightweight — confirm with
  `git cat-file -t <tag>` prints `tag`. Push to `origin`. Confirm on `origin`.
- Do NOT tag a commit BEFORE the relevant validation (that pins pre-validation code).
- Do NOT re-do A.5's docs work (A.5 is ✅). Do NOT change any other story's status. Do NOT
  touch pipeline/infra/lambda code. Do NOT start 2.4 or anything else.
- KEEP PLAN ↔ RUNBOOK ↔ BOM ↔ STORY_DETAIL internally consistent (RD-015): once the tags
  are live, the docs that referenced them stop being phantom; update BOM's "Current
  restore point" header/cells + the RUNBOOK "Restore tag" column as needed.
- VALIDATION-GATED, NEVER ON INFERENCE: A.6 flips ✅ only on a recorded confirmation that
  BOTH tags are pushed AND `git ls-remote --tags origin` lists all six.

# OPERATIONAL CONTEXT (state this on EVERY command block)
  Build sandbox is INTEGRATIONS_ONLY (NO AWS creds; PyPI + npm BLOCKED). A.6 needs NO live
  AWS — the manifests it references were captured + verify-clean in A.4; A.6 is a pure
  git-tag action. `ruff` lives under `~/.pyenv/versions/3.12.13/bin/ruff` (not on PATH). If
  you ever touch TS/JS, `prettier`/`tsc` need `env -u NODE_OPTIONS` — but A.6 should touch
  none.

# HARD-WON LESSONS (do NOT repeat — from Story A.5, just closed)
- **VERIFY live state; don't trust the prose either way.** A.5's edit was already partly
  on `main` (applied by the very commit that registered the story). For A.6: run
  `git ls-remote --tags origin` yourself — do NOT assume the tags are missing (or present)
  from what the docs say. The remote is the source of truth.
- **State drifts between authoring and execution — re-read at execution time.** A.5's
  prompt said "2.4/2.6"; by execution 2.6 had closed, so the answer was 2.4 alone. For
  A.6: re-confirm which tags exist on `origin` and pin `phase-2-floor-green` at the A.4
  commit (a later 2.0E manifest exists), not blindly at the tip.
- **`check_docs.py` CHECK B baseline is `git show HEAD:RUNBOOK.md`** — run `check_docs.py`
  only AFTER committing the status flip, and always also run
  `python3 -m unittest scripts.test_check_docs` (its fixture FAIL lines are the checker
  testing itself, not real failures; suite reports OK / 3 tests).
- **`gh pr create` is BROKEN here** — open any PR via
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`. Merges are the repo-owner's action.

# STEP 0 — RE-ESTABLISH TRUE STATE (before any action)
# Trust `main` + `check_docs` + `git ls-remote` over anything written here; if they
# disagree, the live remote wins.
- `git fetch origin`; `git checkout main`; `git reset --hard origin/main`. Confirm HEAD is
  the latest `main` (should include A.5's merge, PR #73, if it has landed). List open PRs.
- `git ls-remote --tags origin` → confirm which `restore/*` tags exist. Expect (before
  A.6): `phase-1-green`, `story-2.0-green`, `story-2.0E-green`, `story-2.1-green`; expect
  MISSING: `phase-2-floor-green`, `story-2.3-green`. If either already exists, STOP and
  surface it (do not re-tag / overwrite).
- `python3 scripts/check_docs.py` → expect PASS. `python3 -m unittest
  scripts.test_check_docs` → expect OK (3 tests).
- Confirm: A.6 = ⬜, tier 6, Track F&H, Depends-on `A.4` ✅ + `2.3` ✅; A.5 = ✅. Validation
  Debt Register EMPTY → advancement gate OPEN.
- Identify the exact tag targets: the merged A.4 commit (whose diff added
  `restore-manifests/manifest-20260902T201610Z.json` + `…T201931Z.json`) for
  `phase-2-floor-green`; `origin/main` current tip for `story-2.3-green`.

# THIS SESSION'S OBJECTIVE
Prepare the exact annotated-tag commands, have the OWNER push both tags to `origin`,
verify all six restore tags are present on `origin`, reconcile BOM/RUNBOOK so no doc
references a phantom tag, run `check_docs.py` clean, and get the owner to confirm — then
record the dated Validation Result and flip A.6 ✅.

# DEFINITION OF DONE (this session) — a PASS/FAIL GATE
1. `restore/phase-2-floor-green` (annotated) pushed to `origin`, pointing at the A.4 floor
   commit (the one carrying both manifests) — NOT the 2.0E commit, NOT pre-validation code.
2. `restore/story-2.3-green` (annotated) pushed to `origin`, pointing at/after the PR #60
   2.3-✅ merge.
3. `git ls-remote --tags origin` lists all SIX: `phase-1-green`, `story-2.0-green`,
   `story-2.0E-green`, `story-2.1-green`, `phase-2-floor-green`, `story-2.3-green`.
4. No other story's status changed; no pipeline/infra/lambda code touched; BOM + RUNBOOK
   no longer reference either tag as a phantom.
5. `python3 scripts/check_docs.py` PASSES (exit 0); `test_check_docs` OK.
- Goes ✅ ONLY when the owner confirms both tags are pushed + verified on `origin` AND you
  RECORD it in RUNBOOK.md (dated Validation Result). No recorded confirmation → stays 🟡.

# ENVIRONMENT
- Repo cloned. The status-flip commit goes on a branch (`feature/story-A.6` or
  `docs/story-A.6-close`), never main; open PRs via
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls` (NOT `gh pr create`). The TAG PUSH is
  the owner's direct action to `origin`. Merges are the repo-owner's action. No live AWS.

# WORKING AGREEMENT
- One story to completion: prepare tag commands → owner pushes → you VERIFY on `origin` →
  owner confirms → you RECORD + flip status → paired status commit. Push to a branch; open
  a PR; after merge, `git log main..<branch>` to confirm the whole branch landed
  (base-branch trap).
- MANAGEMENT ARTIFACTS ARE FIRST-CLASS (RD-015): BOM (the CMDB) + RUNBOOK are held to the
  same bar as code; PR-reviewed, never straight to main; PLAN ↔ RUNBOOK ↔ BOM aligned;
  re-run G-3 doc checks after any edit.
- Next by tier after A.6: **Story 2.4** (behavioral telemetry capture) — its brief+prompt
  already exist at `docs/session-briefs/story-2.4-*`. With A.5 ✅ AND A.6 ✅, 2.4 is
  unblocked (deps `2.3` + `A.5` + `A.6` all met). At A.6 session end, refresh 2.4's PROMPT
  with A.6's real Lessons Learned so 2.4 starts warm. Zero cold-start.
- If blocked (owner hasn't pushed yet), push a draft PR carrying the prepared exact tag
  commands + the reconciliation edits; surface the blocker; never silently fail and never
  self-certify the tags as pushed.
