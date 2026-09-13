# On deck (the current next-session starter)

> This folder points at the ONE prompt to paste to start the next working session.
> It is kept to a single current pointer so there is never an ambiguous or stale
> starter here. For authoritative status and ordering, read `../../RUNBOOK.md`.

## Next session: Story 3.5 — verdict derivation (PASS / FAIL / INCONCLUSIVE)

**Story 3.4 is validated live + closed ✅ (2026-09-13, RD-039)** — intake `cc058fed-…`, a
PURE `remediation_result` (detailed findings + migrated candidate-FP/gap lists + 2 ranked
remediations over the three real scores 50/30/55, verdict-free, assessed once, full pipeline
green post-cleanup). The register is EMPTY, so the advancement gate is **OPEN** and the next
feature story is **3.5 (verdict derivation)** — it CLOSES Phase 3.

Paste this file as the first message of the next session:

- **[`../story-3.5-PROMPT.md`](../story-3.5-PROMPT.md)**

Its stakeholder-facing brief is **[`../story-3.5-brief.md`](../story-3.5-brief.md)**.

### Why 3.5 is next
3.5 derives the enforcement verdict (PASS / FAIL / INCONCLUSIVE) from the three 3.3 risk
scores + the 3.4 findings/gaps, recorded on the Hub item as ZTIE's **human-gated
recommendation** (it INFORMS the dashboard accept/reject gate — it does NOT auto-enforce).
Its dependency **3.4 is ✅ on `main`** (merge #118, validated live 2026-09-13), so the
register is EMPTY and the advancement gate for 3.5 is expected OPEN. STEP 0 re-verifies on
`main`.

If the stakeholder prefers **T.1** (multi-tenancy design spike, doc-only — should land
before Phase 4) instead, that is a legitimate reorder — record it in
`../../governance/WORK_LOG.md` before starting (RD-024).

### 3.5 is the FIRST verdict-bearing story (read this)
Every Phase-3 record so far (3.1-3.4) is verdict-free BY CONTRACT (a recursive no-verdict
scan enforces it). 3.5's OWN new contract legitimately introduces the `verdict` field — but
the verdict stays HUMAN-GATED. Prefer PURE + deterministic (the inputs are structured; a
verdict must be reproducible + auditable); the PASS/FAIL/INCONCLUSIVE **thresholds are a
stakeholder decision** (confirm + record in the new RD); partial/incomplete evidence →
INCONCLUSIVE, never a fabricated PASS/FAIL; keep the 3.1-3.4 no-verdict scans intact for
THEIR records.

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

### Watch-items (carried from the 3.4 build/validation; apply to the 3.5 session)
- **3.4 validated PURE (RD-039), no model call** — confirmed live 2026-09-13: the live
  `hub_remediate` Lambda has NO `NOVA_MODEL_ID` env + NO `bedrock:InvokeModel` grant, only
  `dynamodb:*`. 3.5 should follow the same PURE + deterministic pattern (a verdict must be
  reproducible; the inputs are already structured).
- **3.5 is the FIRST verdict-bearing contract.** No verdict/safe/forward field appears in
  3.1-3.4 (the recursive no-verdict scans enforce that, and must STAY intact for those
  records); 3.5's OWN new contract legitimately carries the `verdict` field. The verdict is
  HUMAN-GATED — it INFORMS the dashboard accept/reject gate, it does not auto-enforce.
- **PASS/FAIL/INCONCLUSIVE thresholds are a STAKEHOLDER decision** — confirm + record them in
  the new RD; partial/incomplete evidence → INCONCLUSIVE, never a fabricated PASS/FAIL.
- **`_NEW_WORK_STORY` fixture is now 3.5** (repointed in the 3.4 PR). The 3.5 session
  repoints it off 3.5 to the next still-⬜ feature story (4.1) IN THE SAME PR.
- **New RD (next free number, VERIFY):** 3.4 took **RD-039**; the 3.5 session re-greps
  `PROJECT_PLAN.md` for the next free number (the one after RD-039). **CHECK E is literal** —
  add the new RD's plan-table row BEFORE referencing that number in any living doc, or
  CHECK E fails on the still-undefined token (do not write the not-yet-defined number here).
- **CHECK I (broken-link) bit the 3.4 session:** if a LIVING doc (this on-deck README) links
  a not-yet-authored file (e.g. the 4.1 brief/prompt), CHECK I FAILS until that file exists.
  Author the 4.1 handoff files BEFORE pointing here at them (or point at the 3.5 LIVE-RUNBOOK
  you create). Also: `pytest` is NOT installed in the offline sandbox — run
  `~/.pyenv/versions/3.12.13/bin/python3 -m unittest`.
- **Keep the docs consistent** — `check_docs.py` (CHECK A–J) runs on every status change;
  update the **RUNBOOK master table ONLY** for status and let README / this on-deck pointer
  / BUILD_ORDER POINT to it. Run `check_docs` AFTER committing status edits (CHECK B
  baseline is `git show HEAD:RUNBOOK.md`).

### History note
Earlier on-deck starters (A.2, B.1, 2.6, 2.5, C.3, 3.2, G-2, G-1) were superseded as the
plan progressed. This folder holds only a single pointer to the current starter so it
cannot drift into pointing at already-completed or re-sequenced work; for authoritative
status and ordering, read `../../RUNBOOK.md`.
