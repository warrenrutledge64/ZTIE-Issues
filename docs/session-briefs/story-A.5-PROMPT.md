Story-A.5

You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting. Do NOT change anything until you have (a) READ the
plan + runbook + methodology + this story's brief (`session-briefs/story-A.5-brief.md`)
and the target doc (`docs/governance/FLOOR_AND_HARVEST_PLAN.md`), (b) re-established
true state (STEP 0), and (c) confirmed the Validation Debt Register state + advancement
gate.

# PROJECT IDENTITY
ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted artifact
BEFORE it reaches the PDE. Work is validation-gated: nothing is ✅ until a recorded
confirmation (the covenant). Three accounts: Pipeline-Hub (641628980935) = brains/control
plane + durable record; Forensic (360999005254) = self-contained blast zone (ephemeral
only); Pipeline-Sandbox (586917955591) = ZTIE→PDE handoff. Story A.5 is a DOCS-ONLY
remediation-forward (RD-015): it corrects two stale claims in the Floor & Harvest Plan so
the plan matches the recorded repo history. It closes NO pipeline capability; it cleans
the ground.

# WHAT THIS STORY IS (nature + gate role)
DOCS-ONLY GOVERNANCE story (Track = F&H, build tier 6, Depends-on `A.4` ✅). It changes
NO story's status and touches NO pipeline/infra/lambda code. It may begin only if its
Depends-on are ✅ AND the Validation Debt Register is empty (i.e. after Story 2.6's live
pass clears the register). STEP 0 must RE-CONFIRM this on `main` (trust `main` +
`check_docs` over this prompt) before touching anything — verify, do not assume. If 2.6
is still 🟡 / in the register when you start, STOP and surface it: A.5 is not blocked by
2.6 as a dependency, but the advancement gate is armed while the register is non-empty,
and the correct move is to help clear 2.6 first, not to start A.5 around it.

# THE DRIFT A.5 FIXES (read `docs/governance/FLOOR_AND_HARVEST_PLAN.md` first)
Two stale claims, both identified in the 2026-09-07 review:
1. **Exit target.** The plan repeatedly names **Story 2.2** as the exit target ("ends in
   position to build Story 2.2 the new way" — §0 / §2 Exit / §5). Story 2.2 was BUILT +
   validated ✅ the OLD (hand-written) way on 2026-09-03, AFTER the 2026-09-01 audit that
   declared this plan — so 2.2 can no longer be "the next story built the new way."
   Correct the exit target to the next UN-BUILT tier-5 pipeline story as the dependency
   graph actually leaves it. Read `RUNBOOK.md` + `docs/BUILD_ORDER.md` AT EXECUTION TIME
   and name what is genuinely next (2.6 will have closed Phase 2 by then; do NOT fabricate
   an ordering — state it exactly as the graph leaves it).
2. **Full-stop history.** §0's "FULL STOP on new feature work" reads as if enforced from
   2026-09-01, but 2.2 (2026-09-03) and 2.3 (2026-09-05) BOTH shipped the old way after
   that date (the Validation Debt Register was/became empty, so `check_docs.py` CHECK B
   did not block them). Rewrite the paragraph to the HONEST history — the stop was
   *declared* but 2.2/2.3 proceeded the old way; the parameterize-from-archive discipline
   applies GOING FORWARD from the current empty-register state — rather than implying a
   freeze that did not hold.

# NON-NEGOTIABLE CONSTRAINTS
- DOCS-ONLY. No status changes. 2.2 and 2.3 STAY ✅ — a recorded live pass never
  auto-reverts (METHODOLOGY §4). Do NOT re-open or downgrade any completed story.
- CORRECT ONLY FORWARD-LOOKING CLAIMS; do NOT retro-edit genuinely historical references
  elsewhere that correctly describe the past (that is the exact discipline A.5 embodies).
- DO NOT do A.6's work (pushing `restore/phase-2-floor-green` + `restore/story-2.3-green`
  is a separate owner-action story).
- KEEP PLAN ↔ RUNBOOK ↔ FLOOR_AND_HARVEST_PLAN internally consistent (RD-015). Keep
  unrelated governance edits OFF this branch.
- VALIDATION-GATED, NEVER ON INFERENCE: A.5 flips ✅ only on a recorded stakeholder
  confirmation that the two corrections read accurately AND `check_docs.py` PASSES.

# OPERATIONAL CONTEXT (state this on EVERY command block)
  Build sandbox is INTEGRATIONS_ONLY (NO AWS creds; PyPI + npm BLOCKED). A.5 needs NO
  live AWS — it is a docs edit + a local `check_docs.py` run. `ruff` lives under
  `~/.pyenv/versions/3.12.13/bin/ruff` (plain `ruff` is not on PATH). If you ever touch
  TS/JS, `prettier`/`tsc` need `env -u NODE_OPTIONS` (the proxy-bootstrap preload breaks
  bare node tools) — but A.5 should not touch any.

# HARD-WON LESSONS (do NOT repeat — from Story 2.6, just closed)
- **STALE-BRANCH trap bit 2.6.** Its branch was cut before 2.0E landed on `main`, so its
  diff DELETED all 2.0E work; reconciled by merging `origin/main` in. For A.5: `git fetch
  origin && git checkout main && git reset --hard origin/main` and branch off THAT
  (confirm HEAD includes the 2.6 merge), never an older tag/branch.
- **RD-number collisions are real** (2.6's RD-027 collided with 2.0E's RD-027/RD-028 →
  renumbered to RD-029). A.5 registers no RD, but if that ever changes, grep the CURRENT
  main for the next free RD number first.
- **`check_docs.py` CHECK B baseline is `git show HEAD:RUNBOOK.md`** — run `check_docs.py`
  only AFTER committing any status/reconciliation change, and always also run
  `python3 -m unittest scripts.test_check_docs` (its fixture FAIL lines are the checker
  testing itself, not a real failure).
- **`gh pr create` is BROKEN here** — open PRs via
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`. Merges are the repo-owner's action.

# STEP 0 — RE-ESTABLISH TRUE STATE (before any edit)
# Trust `main` + `check_docs` over anything written here; if they disagree, `main` wins.
- `git fetch origin`; `git checkout main`; `git reset --hard origin/main`. Confirm HEAD
  is the Story 2.6 merge (or a descendant). List open PRs.
- `python3 scripts/check_docs.py` → expect PASS. `python3 -m unittest
  scripts.test_check_docs` → expect OK (3 tests).
- Confirm: A.5 = ⬜, tier 6, Track F&H, Depends-on `A.4` (✅). Validation Debt Register
  EMPTY (2.6 cleared it on its live pass) → advancement gate OPEN. 2.2 ✅ / 2.3 ✅ / 2.6
  ✅. If the register still lists 2.6, STOP and surface it (see gate role above).
- Read `docs/governance/FLOOR_AND_HARVEST_PLAN.md` end-to-end and locate the two stale
  claims (§0 full-stop paragraph; §0/§2 Exit/§5 "Story 2.2" exit-target mentions).
- Branch off `main`. Branch name: `feature/story-A.5` (or `docs/story-A.5-fix-floor-plan`).

# THIS SESSION'S OBJECTIVE
Make the two narrative corrections to `docs/governance/FLOOR_AND_HARVEST_PLAN.md`
(accurate against the recorded history), keep the governance docs internally consistent,
run `check_docs.py` clean, push the branch, open a PR, and get the stakeholder to confirm
the corrections read accurately.

# DEFINITION OF DONE (this session) — a PASS/FAIL GATE
1. Exit-target claim corrected to the next un-built tier-5 pipeline story as the graph
   actually leaves it (read RUNBOOK/BUILD_ORDER at execution time; no fabricated order).
2. Full-stop paragraph rewritten to the honest history (declared 2026-09-01; 2.2/2.3
   shipped the old way after; discipline applies going forward).
3. NO story status changed; NO pipeline/infra/lambda code touched; only this plan's stale
   forward-looking claims edited.
4. `python3 scripts/check_docs.py` PASSES (exit 0); `test_check_docs` OK.
- Goes ✅ ONLY when the stakeholder confirms the corrections read accurately AND you
  RECORD it in RUNBOOK.md (dated Validation Result). No recorded confirmation → stays 🟡.

# ENVIRONMENT
- Repo cloned; push to `feature/story-A.5`, never main. Open PRs via
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls` (NOT `gh pr create`). Merges are the
  repo-owner's action. No live AWS needed.

# WORKING AGREEMENT
- One story to completion: edit → stakeholder confirms → you RECORD + flip status →
  paired status commit. Push to a branch; open a PR; after merge, `git log
  main..feature/story-A.5` to confirm the whole branch landed (base-branch trap).
- MANAGEMENT ARTIFACTS ARE FIRST-CLASS (RD-015): the Floor & Harvest Plan is held to the
  same bar as code; PR-reviewed, never straight to main; PLAN ↔ RUNBOOK ↔ plan aligned;
  re-run G-3 doc checks after any edit.
- Next by tier after A.5: **A.6** (push the outstanding restore tags — owner action),
  which with A.5 gates **2.4** (behavioral telemetry capture). Author A.6's brief+prompt
  at session end with A.5's real Lessons Learned. Zero cold-start.
- If blocked, push partial progress + a draft PR; surface the blocker; never silently fail.
