# Story A.5 (stakeholder brief) — correct the Floor & Harvest plan drift

> **What this session is.** A **docs-only** remediation-forward (RD-015): fix two
> stale claims in [`docs/governance/FLOOR_AND_HARVEST_PLAN.md`](../../governance/FLOOR_AND_HARVEST_PLAN.md)
> so the plan matches the recorded repo history. It changes **no story's status** and
> touches **no** pipeline/infra/lambda code. It is part of "clean the ground before
> building" — the tier-6 Floor & Harvest pair (A.5 + A.6) that gates Story 2.4.

## Where we are (true state at authoring, 2026-09-08)

- **Phase 2 pipeline is complete once 2.6 lands:** 2.0 ✅, 2.1 ✅, 2.2 ✅, 2.3 ✅,
  2.0E ✅, and **2.6** (parallel fork/join) validated live and closing Phase 2.
- **A.5 = ⬜, tier 6, Track = F&H, Depends-on `A.4`** (A.4 = ✅, the Phase-2 floor
  restore points). A.5 does not depend on 2.6 — but it is authored on-deck *behind*
  2.6 so the ground is cleaned in the run right after Phase 2 closes.
- **The drift (identified in the 2026-09-07 review):** the Floor & Harvest Plan still
  reads as if written on 2026-09-01, but the repo history moved on.

## What A.5 delivers (Definition of Done)

Two corrections to `docs/governance/FLOOR_AND_HARVEST_PLAN.md`, each accurate against
the recorded history:

1. **Exit target.** The plan repeatedly names **Story 2.2** as the exit target
   ("ends in position to build Story 2.2 the new way" — §0 / §2 Exit / §5). But **2.2
   was built + validated ✅ the old (hand-written) way on 2026-09-03**, after the
   2026-09-01 audit that declared this plan — so 2.2 can no longer be "the next story
   built the new way." Correct the exit target to **the next un-built tier-5 pipeline
   story**. NOTE at authoring 2.6 has just closed Phase 2, so state the exit target as
   the dependency graph actually leaves it — read `RUNBOOK.md` / `docs/BUILD_ORDER.md`
   at execution time and name what is genuinely next (do NOT fabricate an ordering).
2. **Full-stop history.** §0's "FULL STOP on new feature work" reads as if enforced
   from 2026-09-01, but **2.2 (2026-09-03) and 2.3 (2026-09-05) both shipped the old
   way after that date** (the Validation Debt Register was/became empty, so
   `check_docs.py` CHECK B did not block them). Rewrite the paragraph to state the
   honest history — the stop was *declared* but 2.2/2.3 proceeded the old way; the
   parameterize-from-archive discipline applies **going forward** from the
   current empty-register state — rather than implying a freeze that did not hold.

**Gate (DoD):** the user confirms the two corrections read accurately against the
recorded history, **and `python3 scripts/check_docs.py` PASSES (exit 0)** on the
edited tree. It flips ✅ per the Close-Out Procedure only on that recorded confirmation.

## Scope guardrails

- **In scope:** the two narrative corrections to the Floor & Harvest Plan; keeping
  RUNBOOK ↔ PROJECT_PLAN ↔ the plan internally consistent; all via PR (RD-015).
- **Out of scope / MUST NOT:** change ANY story's status (2.2 and 2.3 stay ✅ — a
  recorded live pass never auto-reverts, METHODOLOGY §4); re-open/downgrade any
  completed story; touch any pipeline/infra/lambda code; do A.6's tag-push (that is a
  separate owner-action story); retro-edit other historical docs that correctly
  describe the past (only correct THIS plan's stale forward-looking claims).

## What only YOU (the stakeholder) can do

- **Confirm** the two corrections read accurately against the recorded history (this
  is the DoD's human half; the executor cannot self-certify a narrative judgement).
- **Merge** the A.5 PR to `main` (repo-owner action).
- No live AWS is needed — A.5 is docs-only.

## Lessons Learned / Carry-Forward (from Story 2.6, the session that just closed)

- **BASE-BRANCH / STALE-BRANCH trap — it bit 2.6.** The `feature/story-2.6` branch was
  cut from `dbc98a8` (PR #67) **before** the 2.0E work (PRs #68/#70/#71/#72) landed on
  `main`, so its diff vs `main` *deleted* all of 2.0E. Reconciled by merging
  `origin/main` into the branch (only PROJECT_PLAN + RUNBOOK conflicted). **For A.5:
  branch off the LATEST `main` that already includes the 2.6 merge**, not any older
  tag/branch — `git fetch origin && git checkout main && git reset --hard origin/main`
  first, then branch. Confirm HEAD is the 2.6 merge (or a descendant).
- **RD-number collisions are real.** 2.6's orchestration decision was authored as
  RD-027 on the stale branch, which collided with 2.0E's RD-027 (two-tier endpoints) +
  RD-028 (multi-tenancy) already on `main`; it had to be renumbered to **RD-029**
  everywhere. **Before registering a new RD, `grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md`
  on the CURRENT main and take the next free number.** (A.5 is docs-only and registers
  no RD, but keep the habit.)
- **`check_docs.py` CHECK B baseline is `git show HEAD:RUNBOOK.md`.** On a stale branch
  a merged-in ✅ story can read as "new started while register non-empty" — a
  false positive that clears once the reconciliation merge is COMMITTED (so HEAD
  carries the correct baseline). Run `check_docs.py` **after** committing, and always
  run `python3 -m unittest scripts.test_check_docs` too (its fixture FAIL lines are
  the checker exercising itself, not a real failure).
- **Register clears by ROW REMOVAL, gate is baseline-relative.** When 2.6 flips ✅ its
  register row is deleted (the `_(none)_` placeholder returns); the advancement gate
  then disarms and A.5/A.6 (and 2.4) become startable. A.5 itself is a docs-only
  governance-adjacent story — it does NOT enter the register.
- **Don't retro-edit history; correct only forward-looking claims.** A.5's whole point
  is exactly this discipline: the plan's *past* narrative that is wrong-as-forward-
  looking gets rewritten to honest history; genuinely historical references elsewhere
  are left alone.
- **Operator UX (recurs every session):** feed CloudShell/git commands one line at a
  time; for any git work use the token-in-URL HTTPS remote form. A.5 needs no live AWS.
