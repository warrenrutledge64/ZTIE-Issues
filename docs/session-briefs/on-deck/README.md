# On deck (the current next-session starter)

> This folder points at the ONE prompt to paste to start the next working session.
> It is kept to a single current pointer so there is never an ambiguous or stale
> starter here. For authoritative status and ordering, read `../../RUNBOOK.md`.

## Next session: Story 4.1 — validate the status-retrieval orchestrator LIVE

**Story 4.1 (status-retrieval orchestrator, RD-041) is BUILT + offline-proven and 🟡 on the
Validation Debt Register — the ONLY permitted next work is its recorded LIVE pass.** It was
started AHEAD of B.1 per the **stakeholder reorder recorded 2026-09-13** in
[`../../governance/WORK_LOG.md`](../../governance/WORK_LOG.md) ("option b": do 4.1 first, then
B.1). The advancement gate is ARMED: no NEW feature story (4.2, B.1, …) may begin until 4.1 is
validated live and its register row clears.

**What to run:** an end-to-end pipeline pass in the Hub (641628980935) that lands the full
Phase-3 record for one intake, then invoke the `hub_status` orchestrator (StatusRetrieval
Lambda) for that `intake_id` and confirm it returns the assembled per-intake status read-model
(`status.contract.v1`): intake identity + `overall_stage: recommended` + per-stage presence +
the three 3.3 scores + the bounded `findings_summary` + the `recommendation` block (the 3.5
`recommended_verdict` echoed ADVISORY + `decision: pending` + `advisory: true`). Full steps:

- **[`../story-4.1-LIVE-RUNBOOK.md`](../story-4.1-LIVE-RUNBOOK.md)** (the live validation runbook)

The build prompt + stakeholder brief that produced 4.1:

- **[`../story-4.1-PROMPT.md`](../story-4.1-PROMPT.md)** (build prompt)
- **[`../story-4.1-brief.md`](../story-4.1-brief.md)** (stakeholder brief)

### As built (RD-041, Option A — on-demand read transform)
4.1 is an ON-DEMAND READ/transform behind a Hub-side orchestrator Lambda (`lambdas/hub_status/`):
it READS the current tracking item and assembles the status read-model as its RESPONSE. It is
NOT a durable stored record and NOT a stream consumer — it adds NO durable tracking field, makes
NO model call (no Bedrock), and WRITES nothing (READ-only `dynamodb:GetItem`). PURE assembly
(`status_model.py`) + thin `awsio.py` seam + `status.contract.v1` (a response/transport contract).
The 3.5 recommendation stays **advisory + human-gated** (RD-040): the view surfaces it, never
enforces it, carries no bare effective-verdict field, and reports `decision: pending`. The
3.1-3.4 records stay verdict-free. Invoked on demand per intake (direct Lambda invoke now; a GET
`/status/{intake_id}` API front is **deferred to 4.2** — the handler already accepts the
API-Gateway `pathParameters`/`queryStringParameters` shape).

### Then next: Story 4.2 — Dashboard JSON payload (after 4.1 ✅), then B.1
On 4.1's live pass, 4.1 flips ✅, the register clears, and **4.2** (dashboard JSON payload, tier
14) unblocks — followed by **B.1** (F&H harvest inventory, tier 6, sequenced after 4.1 per the
reorder). 4.2's handoff will be authored at the end of the 4.1 validation session.

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
