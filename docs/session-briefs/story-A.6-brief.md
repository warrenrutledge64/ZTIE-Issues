# Story A.6 (stakeholder brief) — push the outstanding deployed-state restore tags

> **What this session is.** An **owner-action** story (RD-015 / restore-point
> discipline): push the two annotated restore tags that the governance docs already
> reference **as if they exist** but that are **not on `origin`** yet —
> `restore/phase-2-floor-green` (the backed-up Phase-2 floor, from Story A.4) and
> `restore/story-2.3-green` (the validated detonation lane, Story 2.3). It touches **no**
> pipeline/infra/lambda code and changes **no other story's** status. It is the second
> half of the tier-6 Floor & Harvest pair (A.5 + A.6) that **gates Story 2.4**.

## Where we are (true state at authoring, 2026-09-08)

- **A.5 = ✅** (validated 2026-09-08, PR #73): the Floor & Harvest plan drift is
  corrected — the exit target now resolves to **Story 2.4** (the interim "2.4 / 2.6" tie
  collapsed once 2.6 closed ✅). The ground-cleaning docs half is done.
- **A.6 = ⬜, tier 6, Track = F&H, Depends-on `A.4` ✅ + `2.3` ✅.** It is the real
  *foundation* half: until the tags exist, the P2 floor and the 2.3 detonation lane have
  **no returnable restore point** on `origin`, which is a genuine gap before building 2.4.
- **The gap, precisely.** `git ls-remote --tags origin` currently lists only:
  `restore/phase-1-green`, `restore/story-2.0-green`, `restore/story-2.0E-green`,
  `restore/story-2.1-green`. The two A.6 tags are **absent**. The docs (BOM §4, the Floor
  & Harvest Plan, RUNBOOK "Restore tag" column, `docs/STORY_DETAIL.md#story-a-6`) name
  them anyway — the classic "phantom baseline" recurring gap called out in
  [`docs/SETTING_AND_REMOVING_RESTORE_POINTS.md`](../SETTING_AND_REMOVING_RESTORE_POINTS.md) §6.
- **2.4 is structurally blocked on A.6.** Per the RUNBOOK cross-track note (2026-09-07
  decision), `2.4` depends on `2.3` + `A.5` + `A.6`. With A.5 now ✅, **A.6 is the last
  gate before 2.4 can begin.**

## What A.6 delivers (Definition of Done)

Two **annotated** tags pushed to `origin` and verified present:

1. **`restore/phase-2-floor-green`** → tag the merged **Story A.4** status commit — the
   paired commit whose Hub + Forensic manifests are
   `restore-manifests/manifest-20260902T201610Z.json` (Hub, 4 projections) +
   `restore-manifests/manifest-20260902T201931Z.json` (Forensic, 11 projections). This
   pins the backed-up Phase-2 floor (2.0 + 2.1 validated, both accounts verify-clean).
2. **`restore/story-2.3-green`** → tag `origin/main`'s current tip (which is at/after the
   PR #60 merge that flipped 2.3 ✅; later commits are docs-only and do not touch 2.3's
   code or validation result). Verbatim commands already exist in
   [`docs/session-briefs/story-2.3-restore-tag-PROMPT.md`](story-2.3-restore-tag-PROMPT.md).

Both must be **annotated** (`git tag -a … -m …`), pushed, and confirmed with
`git ls-remote --tags origin`.

**Gate (DoD):** the owner pushes both tags; confirmed by `git ls-remote --tags origin`
listing **all six** — `restore/phase-1-green`, `restore/story-2.0-green`,
`restore/story-2.0E-green`, `restore/story-2.1-green`, **`restore/phase-2-floor-green`**,
**`restore/story-2.3-green`**. Then record the dated Validation Result in RUNBOOK +
STORY_DETAIL and flip A.6 ✅. No pushed-and-verified tags → stays ⬜/🟡.

## Scope guardrails

- **In scope:** push the two annotated tags; verify on `origin`; record + flip A.6 ✅ in a
  paired status commit; keep PLAN ↔ RUNBOOK ↔ BOM ↔ STORY_DETAIL internally consistent
  (RD-015).
- **Out of scope / MUST NOT:** change any other story's status; touch any
  pipeline/infra/lambda code; start Story 2.4 or any other work; **re-do A.5's docs work**
  (A.5 is ✅ and merged/landing separately); create a **lightweight** tag (annotated only);
  tag a commit **before** the relevant validation (that would pin pre-validation code).

## What only YOU (the stakeholder / repo owner) can do

- **Push the two annotated tags to `origin`** — this needs real push rights the executor
  does not have in this sandbox (the executor can *prepare* exact copy-paste commands and
  *verify* afterward, but cannot push tags itself here).
- **Confirm** `git ls-remote --tags origin` shows all six tags (the DoD's human half).
- No live AWS is needed for A.6 — it is a pure git-tag action (the manifests it references
  were already captured + verify-clean in A.4).

## Lessons Learned / Carry-Forward (from Story A.5, the session that just closed)

- **A "docs-only" story may already be partly done on `main` — VERIFY before editing.**
  A.5's substantive edit had already been applied by the *same commit that registered the
  story* (`25a66bb`, 2026-09-07). STEP 0's `git log -S` / `git show` on the target file
  revealed this; the *real* residual work was a second-order drift ("2.4 or 2.6" went
  stale when 2.6 closed). **For A.6: before pushing, run `git ls-remote --tags origin`
  yourself** — do not assume the tags are missing just because the docs say so, and do not
  assume they're present just because the docs reference them. Trust the live remote.
- **State drifts between authoring and execution — re-read the graph AT EXECUTION TIME.**
  A.5's prompt (written 2026-09-07) said "the pair 2.4/2.6"; by execution (2026-09-08) 2.6
  had closed, so the honest answer was 2.4 alone. **For A.6:** re-confirm on `origin`/`main`
  which tags actually exist and what the current tip is — a new manifest
  (`restore/story-2.0E-green`, Forensic 16-projection manifest, commit `cb6b5c5`) landed
  after the A.4 floor, so tag `phase-2-floor-green` at the **A.4** commit, not blindly at
  the tip.
- **`check_docs.py` CHECK B baseline is `git show HEAD:RUNBOOK.md`** — run it (and
  `python3 -m unittest scripts.test_check_docs`) only **after** committing the status
  flip. `test_check_docs`'s output includes fixture lines that print `check_docs: FAIL …`
  for stories like 2.5 — those are the checker exercising **itself**, not real failures;
  the suite still reports `OK` / 3 tests.
- **Paired status flip lives in exactly three places, kept aligned (RD-015):** the RUNBOOK
  master-table row (status glyph + Completed date), the FLOOR_AND_HARVEST_PLAN §4 narrative
  table row, and the STORY_DETAIL header + dated Validation Result. For A.6 also update the
  **BOM.md** "Current restore point" header / Restore-point cells and the RUNBOOK
  "Restore tag" column so the CMDB stops referencing phantom tags.
- **`gh pr create` is BROKEN here** — if A.6 needs a PR (for its status-flip commit), open
  it via `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`. Merges are the owner's action.
- **Covenant:** A.6 flips ✅ **only** on the recorded confirmation that both tags are
  pushed + verified on `origin`. No inference. Being blocked on the owner's push is the
  covenant working, not failing — push a draft PR with the prepared commands and surface
  the blocker rather than self-certifying.
