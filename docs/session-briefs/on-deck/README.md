# On deck (the current next-session starter)

> This folder points at the ONE prompt to paste to start the next working session.
> It is kept to a single current pointer so there is never an ambiguous or stale
> starter here. For authoritative status and ordering, read `../../RUNBOOK.md`.

## Next session: Story 4.1 — status-retrieval orchestrator (OPENS Phase 4)

**Story 3.5 is validated live + closed ✅ (2026-09-13, RD-040)** — intake `0c74042e-…`, a
PURE `hub_verdict` advisory `recommended_verdict: INCONCLUSIVE` driven by the `combined`
score 70 (RD-040 band 30-74; NOT a re-aggregation), `human_decision: pending`, never acted
upon, all five Phase-3 stages present, recommended once/guard proven. **This CLOSED Phase 3.**
The register is EMPTY, so the advancement gate is **OPEN** and the next feature story by tier
is **4.1 (status-retrieval orchestrator)** — build tier 13, the **P3 → P4** transition.

Paste this file as the first message of the next session:

- **[`../story-4.1-PROMPT.md`](../story-4.1-PROMPT.md)**

Its stakeholder-facing brief is **[`../story-4.1-brief.md`](../story-4.1-brief.md)**.

### Why 4.1 is next
Phase 3 produced the full per-intake assessment on the Hub tracking item (3.1 combined event
→ 3.2 correlation → 3.3 three scores → 3.4 findings/remediations → 3.5 advisory
`recommended_verdict`). **4.1 is the orchestrator/read-model** that assembles that accumulated
record into the per-intake status the rest of Phase 4 consumes (4.2 dashboard JSON, 4.5
report, and via those the human gate + routing 4.4/4.6/4.7). Its dependency **3.5 is ✅ on
`main`** (merge #121, validated live 2026-09-13), so the register is EMPTY and the gate is
OPEN. STEP 0 re-verifies on `main`.

If the stakeholder prefers **T.1** (multi-tenancy design spike, doc-only — should land before
Phase 4) first, that is a legitimate reorder — record it in `../../governance/WORK_LOG.md`
before starting (RD-024).

### 4.1 scope (confirm the exact output shape with the stakeholder)
4.1 is a READ/transform/orchestration step over already-Hub-side derived data. It does NOT
re-run any Phase-3 assessment, does NOT make a model call, and does NOT enforce anything. It
assembles a bounded per-intake status read-model (identity + per-stage status + the scores +
the findings/remediations + the advisory `recommended_verdict` + `human_decision`) in a shape
the dashboard + report consume. Contract-first: decide (with the stakeholder) whether the
output is a NEW durable Hub-side field/contract or an on-demand read transform — prefer the
minimal option that serves 4.2/4.5. **The recommended_verdict stays ADVISORY** — 4.1 surfaces
it + `human_decision`; the enforcing accept/reject is a human action in 4.4/4.6/4.7.

### G-1 carry-forward (compliance back-map — RD-014)
**G-1 is ✅ CLOSED (2026-09-12).** `docs/COMPLIANCE.md` is finished + ratified. New artifacts
still enter `Proposed` at authoring time (RD-014). Author candidate mapping rows for RD-039
(Story 3.4) + RD-040 (Story 3.5) when the compliance matrix is next revisited.

### Operational Debt: register is EMPTY (2026-09-12)
OD-001 / OD-002 / OD-003 are ALL closed (the RD-032 cost-remediation track is complete).
Design watch-item (not 4.1 scope): a retired Forensic bucket had an unwanted 365-day
COMPLIANCE Object Lock — do not add COMPLIANCE-mode lock to any bucket.

### Sequencing discipline (read this)
The RUNBOOK carries a binding **Sequencing rule** and METHODOLOGY §5.A.0 adds a
session-open **sequence check**: the story to START is the first OPEN item in the RUNBOOK
"Ready now" schedule, and working a *different* Ready story is a stakeholder-decided
reorder (recorded in WORK_LOG), never an executor self-selection or a quiet edit of the
"Default next action." `check_docs.py` CHECK J surfaces this mechanically as a
**non-blocking advisory**.

### Watch-items (carried from the 3.5 build + live validation; apply to the 4.1 session)
- **3.5 validated PURE (RD-040), no model call** — confirmed live 2026-09-13: the live
  `hub_verdict` Lambda has NO `NOVA_MODEL_ID` env + NO `bedrock:InvokeModel` grant, only
  `dynamodb:*`. 4.1 should follow the same PURE + thin-seam pattern (it is a read/transform).
- **The recommended_verdict is ADVISORY + human-gated (RD-040).** 4.1 surfaces it +
  `human_decision: pending`; it must NOT route/promote/enforce and must NOT write a verdict
  onto any other record. The 3.1-3.4 records stay verdict-free; 3.5's `verdict_result` is the
  only verdict-bearing record — 4.1 keeps it that way (echo it clearly labelled advisory).
- **In-flight stream race (observed live, benign):** 3.5's stream handler fired two identical
  `verdict recorded` writes ~0.3s apart before the fingerprint guard engaged, then held
  (`already recommended … no-op`). Same fingerprint, same result → idempotent-in-effect, not a
  loop. If 4.1 hangs off the tracking-table stream, reuse the same `Decimal`-canonicalized
  fingerprint guard and expect (tolerate) the occasional duplicate-but-identical write under
  concurrent stream delivery.
- **`_NEW_WORK_STORY` fixture is now 4.1** (repointed in the 3.5 PR). The 4.1 session repoints
  it off 4.1 to the next still-⬜ feature story (4.2) IN THE SAME PR.
- **RD-040 is recorded** — 4.1 authors a new RD only if it surfaces a genuine new sub-decision
  (next free number after RD-040 — VERIFY); **CHECK E is literal** — add its plan-table row
  BEFORE referencing the number in any living doc.
- **Stale-branch trap:** cut `feature/story-4.1` from the LATEST `main` (after 3.5's docs
  merge). The 3.5 branch was cut before RD-040's PR #120 landed and needed a `git merge
  origin/main` reconciliation — avoid that by branching from current `main`.
- **CHECK I (broken-link):** if a LIVING doc (this on-deck README) links a not-yet-authored
  file, CHECK I FAILS until that file exists. `pytest` is NOT installed offline — run
  `~/.pyenv/versions/3.12.13/bin/python3 -m unittest`.
- **Keep the docs consistent** — `check_docs.py` (CHECK A–J) runs on every status change;
  update the **RUNBOOK master table ONLY** for status and let README / this on-deck pointer /
  BUILD_ORDER POINT to it. Run `check_docs` AFTER committing status edits (CHECK B baseline is
  `git show HEAD:RUNBOOK.md`).

### History note
Earlier on-deck starters (A.2, B.1, 2.6, 2.5, C.3, 3.2, G-2, G-1, 3.4, 3.5) were superseded as
the plan progressed. This folder holds only a single pointer to the current starter so it
cannot drift into pointing at already-completed or re-sequenced work; for authoritative status
and ordering, read `../../RUNBOOK.md`.
