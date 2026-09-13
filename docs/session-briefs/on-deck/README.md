# On deck (the current next-session starter)

> This folder points at the ONE prompt to paste to start the next working session.
> It is kept to a single current pointer so there is never an ambiguous or stale
> starter here. For authoritative status and ordering, read `../../RUNBOOK.md`.

## Next session: VALIDATE Story 3.5 live (advisory recommended_verdict) — RD-040

**Story 3.5 is BUILT + offline-proven and sits 🟡 on the Validation Debt Register**
(`feature/story-3.5`, RD-040). It is the SOLE open register entry, so the advancement gate
is **ARMED** — the ONLY permitted work is validating (or reworking) 3.5 live. No NEW feature
story (incl. 4.1) may begin until 3.5 clears its recorded live pass.

The live validation is the stakeholder's to run:

- **[`../story-3.5-LIVE-RUNBOOK.md`](../story-3.5-LIVE-RUNBOOK.md)** — the step-by-step live
  validation (redeploy `ZtieHubTrackingStack` with the new `hub_verdict` Lambda, submit one
  routable artifact, confirm ONE advisory `verdict_result` with `recommended_verdict` +
  `human_decision: pending` recorded per the RD-040 mapping, never acted upon, the 3.1-3.4
  records still verdict-free, and the full pipeline green end-to-end).

3.5's stakeholder-facing brief is **[`../story-3.5-brief.md`](../story-3.5-brief.md)** and
its build prompt is **[`../story-3.5-PROMPT.md`](../story-3.5-PROMPT.md)**.

### After 3.5 is validated ✅: Story 4.1 (status-retrieval orchestrator) — OPENS Phase 4
Once the stakeholder records 3.5's live pass and the executor flips 3.5 ✅ (clearing the
register + CLOSING Phase 3), the next feature story by tier is **4.1 (status-retrieval
orchestrator)** — build tier 13, the **P3 → P4** transition. Its handoff is authored:

- **[`../story-4.1-PROMPT.md`](../story-4.1-PROMPT.md)** (build prompt)
- **[`../story-4.1-brief.md`](../story-4.1-brief.md)** (stakeholder brief)

### What 3.5 is (built to RD-040 — LOCKED, implemented, not re-opened)
Every Phase-3 record so far (3.1-3.4) is verdict-free BY CONTRACT (a recursive no-verdict
scan enforces it). 3.5's OWN new contract (`verdict.contract.v1`) introduces an ADVISORY
`recommended_verdict` field — but per RD-040 it is **NEVER acted upon**: a human must
ACTIVELY select PASS/FAIL on the dashboard, and only that human selection is enforced
(Phase 4). As built (PURE Hub-side `hub_verdict` Lambda, no model call, no Bedrock grant):
driver = the `combined` score (NOT a re-aggregation of the three lane scores); cut lines
`combined ≤ 29` PASS / `30-74` INCONCLUSIVE / `≥ 75` FAIL; force INCONCLUSIVE on any
`contradiction` finding or any incompleteness; a high-severity gap → INCONCLUSIVE (never
auto-FAIL); it writes ONLY `verdict_result` + `verdict_at` (never touches `status` or the
3.1-3.4 records) and `human_decision` is ALWAYS `pending`. The 3.1-3.4 no-verdict scans are
kept intact; 3.5 carries the advisory field in its own contract only (an INVERTED test
proves 3.5's record DOES carry `recommended_verdict` while it carries no bare effective
verdict key).

### If the stakeholder prefers T.1 instead
**T.1** (multi-tenancy design spike, doc-only — should land before Phase 4) remains a
legitimate reorder once the gate is open — record it in `../../governance/WORK_LOG.md`
before starting (RD-024). While 3.5 is 🟡, though, the gate is armed and 3.5's live
validation comes first.

### G-1 carry-forward (compliance back-map — RD-014)
**G-1 is ✅ CLOSED (2026-09-12).** `docs/COMPLIANCE.md` is finished + ratified (all rows
`Ratified`). New artifacts still enter `Proposed` at authoring time (RD-014). Author a
candidate mapping row for RD-040 / Story 3.5 when the compliance matrix is next revisited.

### Operational Debt: register is EMPTY (2026-09-12)
OD-001 / OD-002 / OD-003 are ALL closed (the RD-032 cost-remediation track is complete).
Design watch-item (not 3.5/4.1 scope): a retired Forensic bucket had an unwanted 365-day
COMPLIANCE Object Lock — do not add COMPLIANCE-mode lock to any bucket.

### Sequencing discipline (read this)
The RUNBOOK carries a binding **Sequencing rule** and METHODOLOGY §5.A.0 adds a
session-open **sequence check**: the story to START is the first OPEN item in the RUNBOOK
"Ready now" schedule, and working a *different* Ready story is a stakeholder-decided
reorder (recorded in WORK_LOG), never an executor self-selection or a quiet edit of the
"Default next action." `check_docs.py` CHECK J surfaces this mechanically as a
**non-blocking advisory**.

### Watch-items (carried from the 3.5 build; apply to the 3.5 validation + the 4.1 session)
- **3.5 built PURE (RD-040), no model call** — the `hub_verdict` Lambda has NO `NOVA_MODEL_ID`
  env + NO `bedrock:InvokeModel` grant, only `dynamodb:*`. The LIVE-RUNBOOK STEP 2 verifies
  this on the live resource (deploy-gap guard: never trust the green `UPDATE_COMPLETE` line —
  inspect the live Lambda env + role after deploy).
- **3.5 is the FIRST + ONLY verdict-bearing record.** No verdict field appears in 3.1-3.4
  (the recursive no-verdict scans enforce that, and must STAY intact); 3.5's OWN record
  carries the advisory `recommended_verdict`. The verdict is HUMAN-GATED + advisory — it
  INFORMS the dashboard accept/reject gate, it does not auto-enforce.
- **RD-040 thresholds are LOCKED** — do NOT re-open or invent them; partial/incomplete
  evidence → INCONCLUSIVE per the RD-040 overrides, never a fabricated PASS/FAIL.
- **`_NEW_WORK_STORY` fixture is now 4.1** (repointed in the 3.5 PR). The 4.1 session repoints
  it off 4.1 to the next still-⬜ feature story (4.2) IN THE SAME PR.
- **RD-040 is already recorded** — 3.5 IMPLEMENTS it. 4.1 authors a new RD only if it surfaces
  a genuine new sub-decision (next free number after RD-040 — VERIFY); **CHECK E is literal** —
  add its plan-table row BEFORE referencing the number in any living doc.
- **Stale-branch trap:** `feature/story-3.5` was cut from `main` BEFORE RD-040's PR #120
  merged and had to reconcile with `git merge origin/main` (conflicts only on the two 3.5
  handoff files, resolved `--theirs`). Cut the NEXT feature branch from the LATEST `main`.
- **CHECK I (broken-link):** if a LIVING doc (this on-deck README) links a not-yet-authored
  file, CHECK I FAILS until that file exists. The 3.5 LIVE-RUNBOOK + the 4.1 brief/prompt are
  authored (this session) so these links resolve. `pytest` is NOT installed offline — run
  `~/.pyenv/versions/3.12.13/bin/python3 -m unittest`.
- **Keep the docs consistent** — `check_docs.py` (CHECK A–J) runs on every status change;
  update the **RUNBOOK master table ONLY** for status and let README / this on-deck pointer /
  BUILD_ORDER POINT to it. Run `check_docs` AFTER committing status edits (CHECK B baseline is
  `git show HEAD:RUNBOOK.md`).

### History note
Earlier on-deck starters (A.2, B.1, 2.6, 2.5, C.3, 3.2, G-2, G-1, 3.4) were superseded as the
plan progressed. This folder holds only a single pointer to the current starter so it cannot
drift into pointing at already-completed or re-sequenced work; for authoritative status and
ordering, read `../../RUNBOOK.md`.
