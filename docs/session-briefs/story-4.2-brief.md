# Session Brief — Story 4.2 (dashboard JSON payload)

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.
>
> **Story 4.2 is the second Phase-4 story.** Phase 4 turns the accumulated Hub-side
> Phase-3 record into human-facing outputs. Story 4.1 (RD-041) built the per-intake
> **status read-model** (`status.contract.v1`) — an on-demand, PURE, READ-only transform
> over the tracking item. **4.2 builds the comprehensive DASHBOARD JSON PAYLOAD** the
> real-time dashboard renders (4.3 is the render). It consumes 4.1's read-model + adds the
> fleet/operational view (multiple intakes + AMI/sensor/cost health).

---

## Story 4.2 — Dashboard JSON payload

| Field | Value |
|-------|-------|
| **Phase** | P4 — Reporting & Handoff |
| **Build tier** | 14 — **advances tier 13 → 14** (its tier-13 dependency `4.1` goes ✅, a new dependency layer opens). This is a tier move WITHIN Phase 4 (NOT a phase transition — P4 opened at 4.1). STEP 0 must re-confirm the ENTIRE tier-≤13 set is ✅ (`4.1` AND its Phase-3 inputs 3.1-3.5). |
| **Date** | TBD (next session) |
| **Status** | ⬜ Not Started (build tier 14 — but see the ADVANCEMENT GATE below). |
| **Depends on** | **4.1 ✅** (RD-041, the per-intake status read-model `status.contract.v1`). 4.2 consumes that read-model as the per-intake core of the dashboard payload. |
| **Builds from restore point** | Branch the CODE off current `main` (which must contain merged + LIVE-VALIDATED 4.1). |
| **Session goal** | Build the comprehensive dashboard JSON payload: (a) a per-intake view (assembled from the 4.1 read-model) and (b) a fleet/list view (recent intakes + pipeline health metrics — AMI build health, sensor status, cost, detonation verdict mix). Contract-first if it produces a durable/crossing artifact; else a bounded transform behind an orchestrator/API with its own tests. **Confirm the exact 4.2 output shape + boundary + list-source with the stakeholder before building.** |

---

### ⚠️ ADVANCEMENT GATE (read FIRST at STEP 0)

**4.2 is a NEW FEATURE story. It may begin ONLY if its Depends-on are ALL ✅ AND the
Validation Debt Register is EMPTY.** As of this brief's authoring, **Story 4.1 (RD-041) is
validated live + closed ✅ (2026-09-13)** and the register is EMPTY, so the gate is
expected OPEN. STEP 0 MUST re-confirm on `main`: `4.1` ✅ and the register EMPTY (trust
`main` + `check_docs`; if they disagree, `main` wins). `check_docs` CHECK B, machine-enforced.

---

### ⚠️ SEQUENCING — confirm 4.2 is genuinely the first OPEN Ready-now item

Per METHODOLOGY §5.A.0 the story to START is the **first OPEN item in the RUNBOOK "Ready
now" schedule, in tier order** — verified live in STEP 0. As of authoring the Ready-now
OPEN items are **4.2 (tier 14)**, **4.5 / 4.6 / 4.7 (tier 14, also unblocked by 4.1)**, and
**B.1 (tier 6, F&H, sequenced after 4.1 per the reorder)**. **B.1 is LOWER-tier than 4.2**,
so by strict tier order B.1 would be first — BUT the recorded stakeholder reorder
(`docs/governance/WORK_LOG.md`, 2026-09-13) sequences the Phase-4 pipe work (starting 4.2)
ahead of the F&H track. **STEP 0 MUST confirm the reorder still stands** (4.2 ahead of B.1);
if the RUNBOOK/WORK_LOG no longer reflects that, STOP and reconcile before starting. Expect
`check_docs` CHECK J to flag the on-deck-vs-first-OPEN mismatch as a NON-BLOCKING advisory
pointing at the logged reorder — reconcile it, do not ignore it.

---

### Background & Context

The dashboard is a stakeholder-required, real-time view (learnings): **dark background
theme; graduated severity/threat color-coding (low/medium/high/critical at a glance); an
interactive human APPROVE/REJECT control** that gates whether an analyzed object may pass to
the PDE. 4.2 is the **data layer** for that dashboard — the JSON it renders. The rendering
(4.3), the human accept/reject ACTION + routing (4.4/4.6/4.7), and the per-execution report
(4.5) are separate stories. 4.2 must give the dashboard everything it needs to show pipeline
status, the advisory recommended_verdict (+ the pending human decision), findings, and
health/cost metrics — WITHOUT itself enforcing anything.

### What This Story Is (nature + gate role)

**Nature: NEW FEATURE story — the Phase-4 data layer.** It is a READ/transform/assembly
step over already-Hub-side derived data (the tracking table + 4.1's read-model + operational
metrics). It does NOT re-run any Phase-3 assessment, does NOT make a model call, and does NOT
enforce anything (the human gate + routing are 4.4/4.6/4.7).

### Objective & Value

- **Objective:** a bounded, DERIVED dashboard JSON payload — a per-intake detail view
  (built from the 4.1 read-model) + a fleet/list view (recent intakes via the tracking
  table's `status-received_at` GSI + pipeline health metrics) — in a shape the dashboard
  (4.3) renders. Contract-first if it produces a durable/crossing artifact; otherwise a
  bounded transform behind an orchestrator/API with its own tests.
- **Why it matters:** it is the single, consistent data contract the real-time dashboard
  renders, decoupled from raw tracking layout and from each downstream consumer.

### Scope, Dependencies & Position

- **In scope:** the dashboard JSON assembly (per-intake detail reusing 4.1 + a fleet/list
  view + health/cost metrics); the transform; tests; a contract-first decision on whether
  the output is a durable field/contract or an on-demand read transform (4.1's precedent:
  on-demand read transform behind an orchestrator, no durable field); candidate control
  mappings (RD-014). **Confirm the exact 4.2 output shape + boundary + the list/metrics
  sources with the stakeholder.**
- **Out of scope / do NOT touch:** the dashboard RENDER (4.3), the human accept/reject
  ACTION + routing (4.4/4.6/4.7), the per-execution report (4.5). Re-deriving any Phase-3
  assessment. **The 3.5 recommended_verdict stays ADVISORY** — 4.2 surfaces it + the
  `decision: pending`; it never acts on it and never writes a verdict onto any record.
- **Depends on:** **4.1 ✅**. **Unblocks:** 4.3 (dashboard render). **4.5/4.6/4.7 are
  independently unblocked by 4.1** and sequenced after 4.2.

### Approach & Constraints

- **Hard constraints:** READ/transform only over the derived Hub-side data; keep the
  RD-009/RD-013 boundary intact (no raw data, no Forensic durable store); PURE logic + thin
  seams (the proven 1.2→4.1 pattern); docs first-class (RD-015), PR-reviewed. **Prefer the
  4.1 pattern** (PURE, READ-only, on-demand transform; reuse `status_model` for the
  per-intake core rather than re-assembling it).
- **The verdict stays advisory + human-gated (RD-040).** 4.2 surfaces the
  recommended_verdict + the pending human decision; it never promotes/routes/enforces. It
  MUST carry an explicit advisory marker (as 4.1's `advisory: true` does) so the render
  cannot mistake the recommendation for an effective decision.
- **Dashboard design requirements (learnings):** the payload must supply what a **dark-theme,
  severity/threat color-graded** dashboard needs (e.g. a normalized severity/threat tier per
  item so the render can color low/medium/high/critical) and the data for the **human
  approve/reject control** (the advisory recommended_verdict + the pending human decision +
  the intake identity the 4.4/4.6/4.7 action keys on). **ServiceNow is OUT OF SCOPE.**
- **AWS-native.** Any orchestration/API is AWS-native (no GitHub Actions for operations).
- **Roles:** the LIVE validation step is the **stakeholder's**; the executor RECORDS.

### Validation Rationale & Compliance Mapping (REQUIRED — RD-014)

- **Rationale:** one consolidated, auditable dashboard JSON gives the real-time dashboard a
  single consistent shape to render (per-intake + fleet health), decoupled from raw tracking
  layout, while keeping the recommended_verdict advisory + human-gated.
- **Candidate control mappings** *(proposed; ratified on review):*

| Framework | Control ID | Control Name | Rationale | Status |
|-----------|-----------|--------------|-----------|--------|
| NIST 800-53 r5 | AU-6 | Audit Record Review/Analysis/Reporting | Consolidated dashboard view for human review | Proposed |
| NIST 800-53 r5 | SI-4 | System Monitoring | Fleet + per-intake monitoring surfaced to the dashboard | Proposed |
| NIST 800-53 r5 | CA-7 | Continuous Monitoring | Real-time pipeline/health status | Proposed |
| NIST CSF | DE.AE-2 | Analyzed events | Analyzed events surfaced to humans | Proposed |
| NIST CSF | DE.CM-1 | Networks/systems monitored | Health/cost/sensor metrics surfaced | Proposed |
| ISO 27001:2022 | A.8.16 | Monitoring activities | Dashboard over monitored evidence | Proposed |

### Management-Artifact Obligations (REQUIRED — RD-015)

- [ ] Story's brief + runbook entry updated (status, Validation Result, dates).
- [ ] PROJECT_PLAN and RUNBOOK in exact alignment (4.2 identical in both).
- [ ] If a genuinely new sub-decision arises, register the next free RD (after RD-041 →
      expect RD-042, but VERIFY with `grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md | sort -u |
      tail`); CHECK E is literal — add its plan-table row BEFORE referencing the number.
- [ ] All doc changes PR-reviewed (branch + PR, never straight to main).
- [ ] `check_docs` fixture `_NEW_WORK_STORY` repointed off 4.2 (→ the next still-⬜ feature
      story, e.g. 4.3) IN THE SAME PR.
- [ ] On validation pass: record Validation Result + flip ✅ (paired commit).
- [ ] Author the next-story handoff (the next Phase-4 story) with real Lessons Learned.

### Definition of Done / Validation Gate

- **Done means:** for a real run, 4.2 produces the dashboard JSON payload (per-intake detail
  from the 4.1 read-model + a fleet/list view + health/cost metrics) validated against its
  shape and available to the render (4.3); RD-009/RD-013 intact; the recommended_verdict
  stays advisory (with an explicit advisory marker); validated live and recorded.
- **Validation Result:** `pending`.
- **On pass:** record dated result, flip 4.2 ✅ (paired commit), keep PLAN ↔ RUNBOOK aligned.
- **On fail:** 4.2 stays 🟡 (added to the register in the same commit); fix + re-validate.

### Risks & Watch-Items

- **ADVANCEMENT GATE:** 4.1 must be ✅ (live-validated) first — it is (2026-09-13).
- **READ/transform, do not re-derive** — 4.2 consumes 4.1 + the tracking table; no model call.
- **The recommended_verdict is advisory (RD-040)** — surface it + the pending human decision;
  never enforce. Carry an explicit advisory marker.
- **Fleet/list source** — prefer the tracking table's `status-received_at-index` GSI for a
  bounded recent-intakes list (no full scan). Confirm the exact metrics + their sources with
  the stakeholder (AMI build health / sensor status / cost may need their own data sources).
- **Deploy-gap** — if it touches `ZtieHubTrackingStack` (or a new stack), redeploy from the
  RIGHT branch; verify the LIVE resource after.

### Lessons Learned / Carry-Forward (from the 4.1 build + LIVE validation, 2026-09-13)

- **The PURE + on-demand read-transform pattern validated live (RD-041, Option A).** 4.1 =
  `lambdas/hub_status/`: a PURE `status_model.py` (assembly) + a thin READ-only `awsio.py`
  seam (`get_item` only, NO `put_*`) + `handler.py` (on-demand, invoked by `intake_id`) + a
  `status.contract.v1` response/transport contract + a two-layer conformance test (stdlib
  walk + `jsonschema` skipUnless). **Reuse this exact skeleton for 4.2**, and **reuse
  `status_model.build_status` for the per-intake core** rather than re-assembling it.
- **4.1's live output shape 4.2 consumes** (the per-intake read-model): top-level
  `contract_version` / `intake_id` / `sha256` / `assembled_at` / `overall_stage` (received /
  classified / collected / correlated / scored / assessed / **recommended**) / `stages`
  (`combined_event` / `correlation` / `scoring` / `remediation` / `verdict_recommendation` /
  optional `classification`, each `present`/`absent`) / optional `status` + `received_at` /
  optional `scores` (static/dynamic/combined echoes + `rubric_version`) / optional
  `findings_summary` (status + counts + `highest_gap_severity` + `contradiction_present`) /
  `recommendation` (`status` + `decision: pending` + `advisory: true` + optional
  `recommended_verdict` / `rubric_version` / `summary` / `status_detail`) + `read_model_note`.
  **Live sample:** intake `384d63ef-…`, `overall_stage: recommended`, scores 55/30/70,
  `recommended_verdict: INCONCLUSIVE`, `decision: pending`, `advisory: true`.
- **Keep the advisory marker.** 4.1 proved (live) that surfacing the recommendation with an
  explicit `advisory: true` + `decision: pending` and NO bare effective-verdict key keeps the
  human-gate covenant. 4.2 must do the same — a `_no_banned_keys` scan
  (`verdict`/`safe`/`approved`/`forward`/`malicious`/`pass_fail`/`clean`) over the payload,
  with the advisory `recommended_verdict` deliberately allow-listed.
- **`stages` key naming trap (bit 4.1):** do NOT name a per-stage presence flag `verdict` —
  it collides with the banned bare-`verdict` scan. 4.1 named the 3.5 flag
  `verdict_recommendation`. Follow the same discipline for any new dashboard field.
- **READ-only proof matters.** 4.1's DoD included re-reading the tracking item after the
  invoke to confirm NOTHING was written (identical DynamoDB key set before/after). If 4.2 is
  also a read transform, include the same proof; grant `grantReadData` only (a READ-only role
  is `dynamodb:BatchGetItem/ConditionCheckItem/DescribeTable/GetItem/GetRecords/
  GetShardIterator/Query/Scan` — NO `UpdateItem`/`PutItem`/`DeleteItem`).
- **On-demand invoke shape (live-proven):** `aws lambda invoke --payload
  "{\"intake_id\":\"<id>\"}" --cli-binary-format raw-in-base64-out`. The 4.1 handler also
  accepts the API-Gateway `pathParameters`/`queryStringParameters` shape, so **4.2 is the
  natural place to stand up the GET API front** (`/status/{intake_id}` + a `/dashboard` or
  `/intakes` list endpoint) if the stakeholder wants HTTP now — confirm with them.
- **The offline bar (unchanged):** `~/.pyenv/versions/3.12.13/bin/python3 -m unittest`
  (pytest is NOT installed); `~/.pyenv/versions/3.12.13/bin/ruff check` (a generator script
  needs `chmod +x` or EXE001 fires); `env -u NODE_OPTIONS npx tsc --noEmit` shows ONLY the
  missing-`aws-cdk-lib` family — adding a stack Lambda adds `__dirname` TS2304 (an EXISTING
  type; confirm NO NEW error TYPE); `env -u NODE_OPTIONS npx prettier --write` the stack.
  Regenerate contracts via `scripts/gen_contracts.py` and confirm no-drift; `jsonschema` is
  not installed offline so the LIVE conformance layer is `skipUnless`-skipped.
- **check_docs fixture:** `scripts/test_check_docs.py` `_NEW_WORK_STORY` is now **4.2**.
  When 4.2 leaves ⬜, repoint it to the next still-⬜ feature story (4.3) IN THE SAME PR.
- **check_docs CHECK I (links) + timing (RD-015):** author the next-story handoff files
  (and the 4.2 LIVE-RUNBOOK) BEFORE pointing the on-deck README at them; run `check_docs`
  only AFTER committing status/register edits (CHECK B baseline is `git show HEAD:RUNBOOK.md`).
- **Sequencing:** 4.2 is next per the reorder (Phase-4 pipe work ahead of the F&H B.1);
  re-confirm the WORK_LOG reorder still holds at STEP 0 and reconcile the CHECK J advisory.
- **User notes:** *(open for the stakeholder — especially the exact dashboard JSON shape,
  the fleet/list source + which health/cost/sensor/AMI metrics to include + their data
  sources, and whether to stand up the HTTP API front now vs. defer.)*

> **Sequencing note:** 4.2 (dashboard JSON payload) is next by the recorded reorder (Phase-4
> pipe work ahead of B.1). It consumes 4.1's read-model and unblocks 4.3 (dashboard render).
