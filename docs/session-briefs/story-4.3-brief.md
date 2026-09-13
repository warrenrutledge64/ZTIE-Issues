# Session Brief — Story 4.3 (real-time dashboard render)

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.
>
> **Story 4.3 is the third Phase-4 story — the RENDER.** Story 4.1 (RD-041) built the
> per-intake status read-model; Story 4.2 (RD-042) built the comprehensive DASHBOARD JSON
> PAYLOAD (`dashboard.contract.v1`) — the per-intake detail + the fleet/list + metrics.
> **4.3 renders that payload** as the real-time dashboard (dark theme, graduated
> severity/threat color-coding, and the human APPROVE/REJECT control surface).

---

## Story 4.3 — Real-time dashboard

| Field | Value |
|-------|-------|
| **Phase** | P4 — Reporting & Handoff |
| **Build tier** | 15 — **advances tier 14 → 15** (its tier-14 dependency `4.2` goes ✅, a new dependency layer opens). This is a tier move WITHIN Phase 4 (NOT a phase transition). STEP 0 must re-confirm the ENTIRE tier-≤14 set is ✅ (`4.2` AND its inputs 4.1 + 3.1-3.5). |
| **Date** | TBD (next session) |
| **Status** | ⬜ Not Started (build tier 15 — but see the ADVANCEMENT GATE below). |
| **Depends on** | **4.2 ✅** (RD-042, the dashboard JSON payload `dashboard.contract.v1`). 4.3 renders that payload — the per-intake detail + the fleet/list + metrics. |
| **Builds from restore point** | Branch the CODE off current `main` (which must contain merged + LIVE-VALIDATED 4.2). |
| **Session goal** | Render the real-time dashboard from 4.2's payload: dark theme; graduated severity/threat color-coding (the `threat_tier` low/medium/high/critical) at a glance; the fleet/list view + per-intake detail drill-in; the operator headline views (live activity; the port ⇄ MITRE view; restore-point status/health as a first-class element); and the human APPROVE/REJECT control surface (surfacing the advisory `recommended_verdict` + the pending decision — the ACTION/routing itself is 4.4/4.6/4.7, not 4.3). **Confirm the render tech + hosting + how it invokes 4.2 (direct Lambda invoke vs. a GET API front, deferred by 4.2) with the stakeholder before building.** |

---

### ⚠️ ADVANCEMENT GATE (read FIRST at STEP 0)

**4.3 is a NEW FEATURE story. It may begin ONLY if its Depends-on are ALL ✅ AND the
Validation Debt Register is EMPTY.** STEP 0 MUST re-confirm on `main`: `4.2` ✅ and the
register EMPTY (trust `main` + `check_docs`; if they disagree, `main` wins). `check_docs`
CHECK B, machine-enforced.

---

### ⚠️ SEQUENCING — confirm 4.3 is genuinely the first OPEN Ready-now item

Per METHODOLOGY §5.A.0 the story to START is the **first OPEN item in the RUNBOOK "Ready
now" schedule, in tier order** — verified live in STEP 0. As of authoring, once 4.2 is ✅
the Ready-now OPEN items are **4.3 (tier 15)**, **4.5 / 4.6 / 4.7 (tier 14, unblocked by
4.1)**, and **B.1 (tier 6, F&H)**. B.1 is LOWER-tier and 4.5/4.6/4.7 are lower-tier than
4.3, so by strict tier order 4.3 is NOT first — the Phase-4 pipe ordering follows the
recorded stakeholder reorder (`docs/governance/WORK_LOG.md`). **STEP 0 MUST confirm the
sequencing with the stakeholder** (which Phase-4 story is next — 4.3 render, the 4.5 report,
or the 4.6/4.7 enforcement actions) and reconcile the `check_docs` CHECK J advisory; if the
reorder no longer puts 4.3 next, STOP and reconcile before starting.

---

### Background & Context

The dashboard is a stakeholder-required, real-time view (learnings): **dark background
theme; graduated severity/threat color-coding (low/medium/high/critical at a glance); an
interactive human APPROVE/REJECT control** that gates whether an analyzed object may pass to
the PDE. 4.2 gave the dashboard everything it needs as ONE JSON payload; **4.3 is the render
of that payload.** It must surface the operator headline views (PROJECT_PLAN §7): live
activity, the port ⇄ MITRE view, and restore-point status/health as a first-class element.

### What This Story Is (nature + gate role)

**Nature: NEW FEATURE story — the Phase-4 render.** It is the presentation layer over 4.2's
payload. It does NOT re-derive any assessment, does NOT make a model call, and does NOT
itself enforce anything (the human accept/reject ACTION + routing is 4.4/4.6/4.7). It
surfaces the advisory `recommended_verdict` + the pending human decision; it must present it
as advisory (never as an effective decision).

### Objective & Value

- **Objective:** a real-time dashboard that renders 4.2's `dashboard.contract.v1` payload —
  the fleet/list (colored by `threat_tier`), the per-intake detail drill-in, the operator
  headline views, and the human APPROVE/REJECT control surface — dark theme, graduated
  severity/threat coloring.
- **Why it matters:** it is the human-facing surface of the whole pipeline; the human gate
  (4.4/4.6/4.7) is exercised THROUGH this dashboard.

### Scope, Dependencies & Position

- **In scope:** the dashboard render + hosting; consuming 4.2's payload; the dark-theme
  graduated color scheme; the operator headline views; the APPROVE/REJECT control SURFACE
  (the button + the advisory recommendation + the pending decision); tenant-aware design
  (RD-028: per-SUBSCRIBER, org-shared; no per-user filtering) built in from the start.
- **Out of scope / do NOT touch:** the accept/reject ACTION + routing (4.4/4.6/4.7); the
  per-execution report (4.5); re-deriving any assessment; the 4.2 payload shape (consume it).
  **ServiceNow is OUT OF SCOPE.**
- **Depends on:** **4.2 ✅**. **Unblocks:** 4.4 (the human accept/reject action + INCONCLUSIVE
  hold, which closes Phase 4 with 4.6/4.7).

### Approach & Constraints

- **Hard constraints:** render only over 4.2's derived payload; no re-derivation, no model
  call; the recommended_verdict stays advisory + human-gated (RD-040) — present it as
  advisory, never as an effective decision; AWS-native hosting (no external providers for
  operations); docs first-class (RD-015), PR-reviewed. **The AWS-native hosting choice + the
  render tech + how the dashboard reads 4.2 (direct Lambda invoke now vs. standing up the GET
  API front 4.2 deferred) are STAKEHOLDER decisions — confirm + record.**
- **Dashboard design requirements (learnings):** dark background; a graduated color scale for
  the `threat_tier` so low/medium/high/critical are distinguishable at a glance; the human
  APPROVE/REJECT control; restore-point status/health as a first-class visible element.
- **Tenant-aware (RD-028):** per-SUBSCRIBER, org-shared; design the data/access path
  per-subscriber now even while ZTIE runs single-tenant, to avoid a costly T.2/T.3 retrofit.

### Validation Rationale & Compliance Mapping (REQUIRED — RD-014)

- **Rationale:** the dashboard is the human-facing surface through which the zero-trust human
  gate is exercised; rendering 4.2's consolidated payload gives operators live pipeline
  status + the accept/reject control in one place.
- **Candidate control mappings** *(proposed; ratified on review):*

| Framework | Control ID | Control Name | Rationale | Status |
|-----------|-----------|--------------|-----------|--------|
| NIST 800-53 r5 | AU-6 | Audit Record Review/Analysis/Reporting | Human review surface over analyzed evidence | Proposed |
| NIST 800-53 r5 | CA-6 | Authorization | The human accept/reject gate is exercised here | Proposed |
| NIST 800-53 r5 | SI-4 | System Monitoring | Real-time pipeline/fleet status surfaced | Proposed |
| NIST CSF | DE.AE-2 | Analyzed events | Analyzed events rendered for humans | Proposed |
| ISO 27001:2022 | A.8.16 | Monitoring activities | Real-time monitoring dashboard | Proposed |

### Management-Artifact Obligations (REQUIRED — RD-015)

- [ ] Story's brief + runbook entry updated (status, Validation Result, dates).
- [ ] PROJECT_PLAN and RUNBOOK in exact alignment (4.3 identical in both).
- [ ] If a genuinely new sub-decision arises, register the next free RD (after RD-042 →
      expect RD-043, but VERIFY with `grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md | sort -u |
      tail`); CHECK E is literal — add its plan-table row BEFORE referencing the number.
- [ ] All doc changes PR-reviewed (branch + PR, never straight to main).
- [ ] `check_docs` fixture `_NEW_WORK_STORY` repointed off 4.3 (→ the next still-⬜ feature
      story) IN THE SAME PR.
- [ ] On validation pass: record Validation Result + flip ✅ (paired commit).
- [ ] Author the next-story handoff with real Lessons Learned.

### Definition of Done / Validation Gate

- **Done means:** for a real run, the dashboard renders 4.2's payload — the fleet/list
  colored by threat tier, the per-intake drill-in, the operator headline views, and the
  APPROVE/REJECT control surface (advisory recommendation + pending decision) — dark theme,
  graduated coloring; validated live (a real intake shows correctly, with correct severity
  coloring) and recorded.
- **Validation Result:** `pending`.
- **On pass:** record dated result, flip 4.3 ✅ (paired commit), keep PLAN ↔ RUNBOOK aligned.
- **On fail:** 4.3 stays 🟡 (added to the register in the same commit); fix + re-validate.

### Risks & Watch-Items

- **ADVANCEMENT GATE:** 4.2 must be ✅ (live-validated) first.
- **Render only, do not re-derive** — 4.3 consumes 4.2's payload; no model call.
- **The recommended_verdict is advisory (RD-040)** — present it as advisory + the pending
  human decision; the ACTION is 4.4/4.6/4.7, not 4.3.
- **AWS-native hosting** — confirm the hosting + render tech + the 4.2 read path (direct
  invoke vs. the deferred GET API front) with the stakeholder.
- **Tenant-aware design (RD-028)** — per-subscriber, org-shared; build the data/access path
  per-subscriber now.

### Lessons Learned / Carry-Forward (from the 4.2 build + LIVE validation)

- *(to be filled from the 4.2 live run)* — the exact 4.2 payload shape the render consumes:
  top-level `contract_version` / `view` (`intake`|`fleet`) / `assembled_at`; for `view=intake`
  an `intake` object = `status` (the 4.1 read-model) + `threat` (`tier` +
  `combined_score`/`highest_gap_severity`/`contradiction_present`) + `action` (`intake_id` +
  `sha256` + `recommendation_status` + `recommended_verdict` + `decision: pending` +
  `advisory: true`); for `view=fleet` a `fleet` object = `intakes` (rows: `intake_id` +
  `overall_stage` + `threat_tier` + `decision` + opt `recommended_verdict`/`status`/
  `received_at`/`sha256`) + `returned_count` + `truncated` + `metrics` (`window_count` +
  `by_stage` + `by_recommended_verdict` + `by_threat_tier` + the stubbed `ami_build_health`/
  `sensor_status`/`cost` health blocks).
- **The AMI/sensor/cost health blocks are STUBBED `not_wired` by 4.2** — the render should
  show them as "not available yet" (their real data sources are a deferred follow-on), not as
  an error.
- **How the render invokes 4.2:** direct Lambda invoke `{"view":"intake","intake_id":"<id>"}`
  / `{"view":"fleet","limit":N}` now, or the GET API front (deferred by 4.2 — the handler
  already accepts the API-Gateway `pathParameters`/`queryStringParameters` shape) if the
  stakeholder wants HTTP.
- **User notes:** *(open for the stakeholder — especially the render tech + AWS-native
  hosting + whether to stand up the HTTP API front now, and the exact operator headline-view
  layout.)*

> **Sequencing note:** 4.3 (dashboard render) follows 4.2 by tier. It renders 4.2's payload
> and unblocks 4.4 (the human accept/reject action). Confirm the Phase-4 ordering with the
> stakeholder at STEP 0 (4.3 vs. 4.5/4.6/4.7 vs. B.1).
