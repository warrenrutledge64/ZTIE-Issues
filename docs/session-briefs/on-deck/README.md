# On deck (the current next-session starter)

> This folder points at the ONE prompt to paste to start the next working session.
> It is kept to a single current pointer so there is never an ambiguous or stale
> starter here. For authoritative status and ordering, read `../../RUNBOOK.md`.

## Next session: VALIDATE Story 3.4 live (RD-039) — then Story 3.5

**Story 3.4 is now BUILT + offline-proven (🟡 on `feature/story-3.4`, RD-039)** and is the
SOLE open Validation-Debt entry, so the advancement gate is **ARMED**. The immediate next
action is to VALIDATE 3.4 LIVE — no new feature story (3.5) may begin until 3.4 clears.

Paste this file as the first message of the next session:

- **[`../story-3.4-LIVE-RUNBOOK.md`](../story-3.4-LIVE-RUNBOOK.md)** — the step-by-step live
  validation for the stakeholder (its DoD #4 doubles as the OD-001/OD-002 post-cleanup
  regression proof). On a recorded live pass, record the Validation Result + flip 3.4 ✅.

3.4's design/change record is **[`../story-3.4-brief.md`](../story-3.4-brief.md)**; its
original agent prompt is **[`../story-3.4-PROMPT.md`](../story-3.4-PROMPT.md)**.

### After 3.4 flips ✅: Story 3.5 (verdict derivation)
Once 3.4 is validated live + closed ✅, the register empties and the next feature story is
**3.5** (derive the PASS/FAIL/INCONCLUSIVE verdict from the three scores + findings + the
human gate — closes Phase 3). Its brief + prompt are authored at
**[`../story-3.5-brief.md`](../story-3.5-brief.md)** / **[`../story-3.5-PROMPT.md`](../story-3.5-PROMPT.md)**.

If the stakeholder prefers **T.1** (multi-tenancy design spike, doc-only — should land
before Phase 4) instead of 3.5 after 3.4 clears, that is a legitimate reorder — record it in
`../../governance/WORK_LOG.md` before starting (RD-024).

### G-1 carry-forward (compliance back-map — RD-014)
**G-1 is ✅ CLOSED (2026-09-12).** The `docs/COMPLIANCE.md` matrix was finished (PR #111)
AND ratified (PR #115): all 59 rows are now `Ratified (warrenrutledge64, 2026-09-12)` — the
accountable party accepted all 8 artifact groups. New artifacts still enter `Proposed` at
authoring time (RD-014). Nothing outstanding here; noted only so the next session knows the
compliance back-map is complete.

### Operational Debt: register is EMPTY (2026-09-12)
OD-001 (Hub stale-stack cleanup, PR #112), OD-002 (Forensic stale-lineage teardown, PR #114),
and OD-003 (CDK bump, #105/#109) are ALL closed — the RD-032 cost-remediation track is
complete. **Post-cleanup regression note:** ~20 stale stacks were deleted across both
accounts; the live ZTIE pipeline stacks were kept + untouched, and **3.4's end-to-end live
validation doubles as the proof the cleanup didn't break the pipeline** (see the 3.4 PROMPT's
DoD #4). Also held: `DeployForensics-ZtieImageBuilder` (not confirmed dead). Design watch-item
(not 3.4 scope): a retired Forensic bucket had an unwanted 365-day COMPLIANCE Object Lock — do
not add COMPLIANCE-mode lock to any bucket.

### Sequencing discipline (read this)
The RUNBOOK carries a binding **Sequencing rule** and METHODOLOGY §5.A.0 adds a
session-open **sequence check**: the story to START is the first OPEN item in the RUNBOOK
"Ready now" schedule, and working a *different* Ready story is a stakeholder-decided
reorder (recorded in WORK_LOG), never an executor self-selection or a quiet edit of the
"Default next action." `check_docs.py` CHECK J now surfaces this mechanically as a
**non-blocking advisory** (it points you to WORK_LOG to confirm a recorded reorder rather
than hard-failing it, because reordering is the stakeholder's call).

### Watch-items (carried from the 3.4 build; apply to the 3.4 live-validation + the 3.5 session)
- **3.4 was built PURE (RD-039), no model call** — the three risk scores are 3.3's
  (`scoring_result`) and the findings are 3.2's (`correlation_result`); 3.4 only surfaces
  the findings + ranks the remediations over them. It has NO Bedrock grant. Confirm this
  holds during the live run (no Nova Pro call from `hub_remediate`).
- **EVIDENCE + a to-do list, never a verdict.** No verdict/safe/forward field anywhere;
  the PASS/FAIL/INCONCLUSIVE verdict is Story 3.5, human-gated.
- **`_NEW_WORK_STORY` fixture repointed 3.4 → 3.5** (done in the 3.4 PR, same PR that set
  3.4 🟡). The 3.5 session repoints it off 3.5 to the next still-⬜ feature story.
- **New RD (next free number, VERIFY):** 3.4 took **RD-039**; the 3.5 session re-greps
  `PROJECT_PLAN.md` for the next free number. **CHECK E is literal** — add the new RD's
  plan-table row BEFORE referencing that number in any living doc, or CHECK E fails on the
  still-undefined token.
- **Keep the docs consistent** — `check_docs.py` (CHECK A–J) runs on every status change;
  update the **RUNBOOK master table ONLY** for status and let README / this on-deck pointer
  / BUILD_ORDER POINT to it. Run `check_docs` AFTER committing status edits (CHECK B
  baseline is `git show HEAD:RUNBOOK.md`).

### History note
Earlier on-deck starters (A.2, B.1, 2.6, 2.5, C.3, 3.2, G-2, G-1) were superseded as the
plan progressed. This folder holds only a single pointer to the current starter so it
cannot drift into pointing at already-completed or re-sequenced work; for authoritative
status and ordering, read `../../RUNBOOK.md`.
