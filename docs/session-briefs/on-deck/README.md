# On deck (the current next-session starter)

> This folder points at the ONE prompt to paste to start the next working session.
> It is kept to a single current pointer so there is never an ambiguous or stale
> starter here. For authoritative status and ordering, read `../../RUNBOOK.md`.

## Next session: Story 4.2 — Dashboard JSON payload (the Phase-4 data layer)

**Story 4.1 (status-retrieval orchestrator, RD-041) is validated live + closed ✅
(2026-09-13)** — intake `384d63ef-7577-4787-ba0e-cc5d92305ff9` in the Hub (641628980935): the
PURE, READ-only `hub_status` orchestrator returned the assembled per-intake status read-model
(`overall_stage: recommended`, scores 55/30/70, the 3.5 `recommended_verdict: INCONCLUSIVE`
surfaced ADVISORY with `decision: pending` + `advisory: true`; wrote nothing to the item; no
effective-verdict key; 404/400 error paths clean). The register is EMPTY and the advancement
gate is OPEN.

**Sequencing:** the next build is **Story 4.2 — Dashboard JSON payload (tier 14)** per the
recorded stakeholder reorder (`../../governance/WORK_LOG.md`, 2026-09-13) that sequences the
Phase-4 pipe work ahead of the F&H track. (B.1, tier 6, is lower-tier and also Ready, but the
reorder puts 4.2 first; `check_docs` CHECK J will flag the on-deck-vs-first-OPEN mismatch as a
NON-BLOCKING advisory pointing at that logged reorder — reconcile it at STEP 0, don't ignore
it.) Paste this file as the first message of the next session:

- **[`../story-4.2-PROMPT.md`](../story-4.2-PROMPT.md)** (build prompt)

Its stakeholder-facing brief is **[`../story-4.2-brief.md`](../story-4.2-brief.md)**.

### What 4.2 is
4.2 builds the comprehensive **dashboard JSON payload** the real-time dashboard renders (4.3 is
the render): (a) a per-intake detail view — assembled from 4.1's read-model (reuse
`status_model.build_status`) — and (b) a fleet/list view — recent intakes (prefer the tracking
table's `status-received_at` GSI, no full scan) + pipeline health metrics (AMI build health,
sensor status, cost, detonation verdict mix). READ/transform only; no model call; the 3.5
recommendation stays advisory + human-gated (surface it + the pending human decision with an
explicit advisory marker; never enforce; no bare effective-verdict field). The dashboard is
dark-theme with graduated severity/threat color-coding + a human approve/reject control
(learnings); ServiceNow is OUT OF SCOPE. **Confirm the exact payload shape + the fleet/list +
metrics sources + whether to stand up the HTTP API front now with the stakeholder at STEP 0.**

### The 4.1 build prompt + brief (for reference)
- **[`../story-4.1-PROMPT.md`](../story-4.1-PROMPT.md)** · **[`../story-4.1-brief.md`](../story-4.1-brief.md)** · **[`../story-4.1-LIVE-RUNBOOK.md`](../story-4.1-LIVE-RUNBOOK.md)**

### G-1 carry-forward (compliance back-map — RD-014)
**G-1 is ✅ CLOSED (2026-09-12).** `docs/COMPLIANCE.md` is finished + ratified. New artifacts
still enter `Proposed` at authoring time (RD-014). Candidate mapping rows for RD-039 / RD-040 /
RD-041 are in `docs/COMPLIANCE.md` (Proposed); ratify on the next compliance review.

### Operational Debt: register is EMPTY (2026-09-12)
OD-001 / OD-002 / OD-003 are ALL closed (the RD-032 cost-remediation track is complete).
Design watch-item (not 4.2 scope): a retired Forensic bucket had an unwanted 365-day
COMPLIANCE Object Lock — do not add COMPLIANCE-mode lock to any bucket.

### Sequencing discipline (read this)
The RUNBOOK carries a binding **Sequencing rule** and METHODOLOGY §5.A.0 adds a
session-open **sequence check**: the story to START is the first OPEN item in the RUNBOOK
"Ready now" schedule, and working a *different* Ready story is a stakeholder-decided
reorder (recorded in WORK_LOG), never an executor self-selection or a quiet edit of the
"Default next action." `check_docs.py` CHECK J surfaces this mechanically as a
**non-blocking advisory**.

### Watch-items (carried from the 4.1 build + LIVE validation 2026-09-13; apply to the 4.2 session)
- **The PURE + on-demand READ-transform pattern validated live (RD-041).** `lambdas/hub_status/`
  = PURE `status_model.py` + a thin READ-only `awsio.py` (`get_item` only, NO `put_*`) +
  on-demand `handler.py` (invoked by `intake_id`; also accepts the API-Gateway
  pathParameters/queryStringParameters shape) + `status.contract.v1` response contract +
  two-layer conformance test. **4.2 should reuse this skeleton AND reuse
  `status_model.build_status` for the per-intake core** — do not re-assemble it.
- **4.1's live read-model shape 4.2 consumes:** `contract_version`/`intake_id`/`sha256`/
  `assembled_at`/`overall_stage`/`stages` (`combined_event`/`correlation`/`scoring`/
  `remediation`/`verdict_recommendation`/opt `classification`)/opt `status`+`received_at`/opt
  `scores` (static/dynamic/combined + `rubric_version`)/opt `findings_summary` (status +
  counts + `highest_gap_severity` + `contradiction_present`)/`recommendation` (`status` +
  `decision: pending` + `advisory: true` + opt `recommended_verdict`/`rubric_version`/
  `summary`) + `read_model_note`. Live sample: `overall_stage: recommended`, scores 55/30/70,
  `recommended_verdict: INCONCLUSIVE`.
- **The recommended_verdict is ADVISORY + human-gated (RD-040).** 4.2 surfaces it + the pending
  human decision with an explicit advisory marker (4.1 uses `advisory: true`); it must NOT
  route/promote/enforce (that is 4.4/4.6/4.7) and must NOT write a verdict onto any record. Run
  a `_no_banned_keys` scan (`verdict`/`safe`/`approved`/`forward`/`malicious`/`pass_fail`/
  `clean`) over the payload with `recommended_verdict` deliberately allow-listed.
- **`stages` key naming trap (bit 4.1):** never name a field a bare `verdict` — it collides
  with the banned-key scan. 4.1 named the 3.5 flag `verdict_recommendation`. Same discipline.
- **READ-only proof (live DoD):** 4.1 re-read the item after invoke to prove NOTHING was
  written (identical DynamoDB key set before/after). If 4.2 is a read transform, do the same;
  `grantReadData` only (READ role = GetItem/Query/BatchGetItem/Scan/DescribeTable/
  ConditionCheckItem/GetRecords/GetShardIterator — NO Update/Put/Delete). Verify the LIVE role
  + env (no `NOVA_MODEL_ID`) AFTER deploy — never trust the green `UPDATE_COMPLETE`.
- **Fleet/list source:** prefer the tracking table's `status-received_at-index` GSI for a
  bounded recent-intakes list (no full scan). Confirm the exact health/cost/sensor/AMI metrics
  + their sources with the stakeholder.
- **`_NEW_WORK_STORY` fixture is now 4.2** (repointed in the 4.1 validation PR). The 4.2
  session repoints it off 4.2 to the next still-⬜ feature story (4.3) IN THE SAME PR.
- **RD hygiene:** RD-041 is 4.1's. 4.2 authors a new RD only if it surfaces a genuine new
  sub-decision (next free number after RD-041 — VERIFY, expect RD-042); **CHECK E is literal**
  — add its plan-table row BEFORE referencing the number in any living doc.
- **CHECK I (broken-link):** author the next-story handoff + the 4.2 LIVE-RUNBOOK BEFORE
  pointing this on-deck README at them. `pytest` is NOT installed offline — run
  `~/.pyenv/versions/3.12.13/bin/python3 -m unittest`.
- **Keep the docs consistent** — `check_docs.py` (CHECK A–J) runs on every status change;
  update the **RUNBOOK master table ONLY** for status and let README / this on-deck pointer /
  BUILD_ORDER POINT to it. Run `check_docs` AFTER committing status edits (CHECK B baseline is
  `git show HEAD:RUNBOOK.md`).

### History note
Earlier on-deck starters (A.2, B.1, 2.6, 2.5, C.3, 3.2, G-2, G-1, 3.4, 3.5, 4.1) were superseded as
the plan progressed. This folder holds only a single pointer to the current starter so it
cannot drift into pointing at already-completed or re-sequenced work; for authoritative status
and ordering, read `../../RUNBOOK.md`.
