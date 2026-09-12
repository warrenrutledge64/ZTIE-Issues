# On deck (the current next-session starter)

> This folder points at the ONE prompt to paste to start the next working session.
> It is kept to a single current pointer so there is never an ambiguous or stale
> starter here. For authoritative status and ordering, read `../../RUNBOOK.md`.

## Next session: Story 3.4 — detailed findings + prioritized remediations (RD-038)

Paste this file as the first message of the next session:

- **[`../story-3.4-PROMPT.md`](../story-3.4-PROMPT.md)**

Its stakeholder-facing brief is **[`../story-3.4-brief.md`](../story-3.4-brief.md)**.

### Why 3.4 is next
As of 2026-09-12, the highest-value **Ready** pipe story is **3.4** (detailed findings +
prioritized remediations over 3.3's three Nova Pro risk scores + the migrated
candidate-FP/gap lists). Its dependency **3.3 is ✅ on `main`** (validated live 2026-09-12,
RD-038, merge #110), so the Validation Debt Register is EMPTY and the advancement gate for
3.4 is expected OPEN. STEP 0 re-verifies this on `main` (trust `main` + `check_docs`).

If the stakeholder prefers **T.1** (multi-tenancy design spike, doc-only — should land
before Phase 4) instead, that is a legitimate reorder — record it in
`../../governance/WORK_LOG.md` before starting (RD-024).

### G-1 carry-forward (compliance back-map — RD-014)
The **G-1 authoring is DONE** (PR #111, branch `feature/story-G-1`, 2026-09-12): the
`docs/COMPLIANCE.md` matrix is finished — a candidate (`Proposed`) mapping now exists for
every registered decision (RD-001…RD-038), every non-functional constraint, and the built
pipeline's stories (59 `Proposed` rows, 0 self-ratified). **G-1 remains 🟡** because the
outstanding half is **ratification**, which is an **accountable reviewer's** action, not the
executor's (RD-014 candidate-until-ratified — ZTIE claims coverage for NO row yet). This is
NOT a working session on its own: the next time a reviewer is available, they flip
`Proposed → Ratified` per artifact group (dated + attributed) and G-1 closes ✅ incrementally.
G-1 is a `gov` story (register-exempt), so its 🟡 does not arm the 3.4 gate.

### Sequencing discipline (read this)
The RUNBOOK carries a binding **Sequencing rule** and METHODOLOGY §5.A.0 adds a
session-open **sequence check**: the story to START is the first OPEN item in the RUNBOOK
"Ready now" schedule, and working a *different* Ready story is a stakeholder-decided
reorder (recorded in WORK_LOG), never an executor self-selection or a quiet edit of the
"Default next action." `check_docs.py` CHECK J now surfaces this mechanically as a
**non-blocking advisory** (it points you to WORK_LOG to confirm a recorded reorder rather
than hard-failing it, because reordering is the stakeholder's call).

### Watch-items for the 3.4 session (also in the prompt)
- **Findings + remediations, do NOT re-score/re-correlate.** The three risk scores are
  3.3's (`scoring_result`); 3.4 ranks over them. Prefer **PURE** Hub-side post-processing
  (its inputs are already structured) — a model call would only add cost/non-determinism.
- **EVIDENCE + a to-do list, never a verdict.** No verdict/safe/forward field anywhere;
  the PASS/FAIL/INCONCLUSIVE verdict is Story 3.5, human-gated.
- **New RD (next free number, VERIFY):** re-grep `PROJECT_PLAN.md` for the next free RD
  number (RD-038 is taken by 3.3; RD-number collisions have happened). **CHECK E is
  literal** — add the new RD's plan-table row BEFORE referencing that number in any living
  doc, or CHECK E fails on the still-undefined token.
- **Repoint the `_NEW_WORK_STORY` fixture** off 3.4 to 3.5 in the same PR when 3.4 leaves
  ⬜, then re-run `python3 -m unittest scripts.test_check_docs` (SUITE line OK).
- **Keep the docs consistent** — `check_docs.py` (CHECK A–J) runs on every status change;
  update the **RUNBOOK master table ONLY** for status and let README / this on-deck pointer
  / BUILD_ORDER POINT to it. Run `check_docs` AFTER committing status edits (CHECK B
  baseline is `git show HEAD:RUNBOOK.md`).

### History note
Earlier on-deck starters (A.2, B.1, 2.6, 2.5, C.3, 3.2, G-2, G-1) were superseded as the
plan progressed. This folder holds only a single pointer to the current starter so it
cannot drift into pointing at already-completed or re-sequenced work; for authoritative
status and ordering, read `../../RUNBOOK.md`.
