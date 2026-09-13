# Session Brief — Story 4.1 (status-retrieval orchestrator)

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.
>
> **Story 4.1 OPENS Phase 4 (Reporting & Handoff).** Phase 3 produced the full
> per-intake assessment on the Hub tracking item (3.1 combined event → 3.2 correlation
> → 3.3 three scores → 3.4 findings/remediations → 3.5 advisory recommended_verdict).
> Phase 4 turns that accumulated Hub-side record into the OUTPUTS a human consumes — the
> dashboard payload (4.2/4.3), the per-execution report (4.5), and the human accept/reject
> gate + routing (4.4/4.6/4.7). **4.1 is the orchestrator/read-model that assembles the
> per-intake status the rest of Phase 4 consumes.**

---

## Story 4.1 — Status-retrieval orchestrator

| Field | Value |
|-------|-------|
| **Phase** | P4 — Reporting & Handoff (this story OPENS it) |
| **Build tier** | 13 — **advances tier 12 → 13** (a new dependency layer opens: `3.5` at tier 12 goes ✅). This is BOTH a tier move AND the **P3 → P4 phase transition**. STEP 0 must re-confirm the ENTIRE tier-≤12 set is ✅ (`3.5` AND its Phase-3 inputs `3.4` + `3.3` + `3.2` + `3.1`) and that the P3 end-of-phase gate is satisfied. |
| **Date** | TBD (next session) |
| **Status** | ⬜ Not Started (build tier 13 — but see the ADVANCEMENT GATE below). |
| **Depends on** | **3.5 ✅** (the advisory `verdict_result` — RD-040) which sits over the whole Phase-3 record (3.1-3.4). 4.1 reads that accumulated Hub-side record and assembles the per-intake status. |
| **Builds from restore point** | Branch the CODE off current `main` (which must contain merged + LIVE-VALIDATED 3.5 by the time 4.1 begins). |
| **Session goal** | For one `intake_id`, orchestrate/assemble the per-intake STATUS read-model — a bounded, DERIVED view over the Hub tracking item (intake metadata + per-stage presence/status + the 3.3 scores + the 3.4 findings/remediations + the 3.5 advisory recommended_verdict + `human_decision`) that the Phase-4 dashboard payload (4.2) and per-execution report (4.5) consume. It is a READ/transform step; it does not re-derive any assessment and does not itself enforce anything. |

---

### ⚠️ ADVANCEMENT GATE (read FIRST at STEP 0)

**4.1 is a NEW FEATURE story. It may begin ONLY if its Depends-on are ALL ✅ AND the
Validation Debt Register is EMPTY.** As of this brief's authoring, **Story 3.5 (RD-040)
sits 🟡 on the register awaiting its recorded LIVE pass** (see
`story-3.5-LIVE-RUNBOOK.md`). So the gate is expected ARMED until 3.5 is validated live.
STEP 0 MUST re-confirm on `main`: `3.5` ✅ and the register EMPTY (trust `main` +
`check_docs`; if they disagree, `main` wins). **If 3.5 is still 🟡, 4.1 MAY NOT begin —
the only permitted work is validating/reworking 3.5.** `check_docs` CHECK B, machine-enforced.

---

### Background & Context

Phase 3 is complete once 3.5 lands: every intake carries, on the Hub tracking item, a
`combined_event` (3.1), a `correlation_result` (3.2), a `scoring_result` (3.3, three 0-100
risk scores), a `remediation_result` (3.4, detailed findings + prioritized remediations),
and an advisory `verdict_result` (3.5, `recommended_verdict` + `human_decision: pending`).
Phase 4 is where those become human-facing outputs + the human gate + routing. **4.1 is the
first Phase-4 story: the orchestrator/read-model.** It consolidates the per-intake status
into one bounded, DERIVED view so 4.2 (dashboard JSON), 4.5 (report), and the gate/routing
stories (4.4/4.6/4.7) all read a single consistent shape rather than each re-reading raw
tracking attributes.

### What This Story Is (nature + gate role)

**Nature: NEW FEATURE story — the Phase-4 opener.** It is a READ/transform/orchestration
step over already-Hub-side derived data. It does NOT re-run any Phase-3 assessment, does
NOT make a model call (the assessments are done), and does NOT enforce anything (the human
gate + routing are 4.4/4.6/4.7). It is the seam between "the pipeline has assessed this
intake" and "a human can see + act on it."

### Objective & Value

- **Objective:** for one `intake_id`, a bounded, DERIVED per-intake STATUS read-model
  assembled from the Hub tracking item — intake identity + per-stage presence/status + the
  scores + the findings/remediations + the advisory recommended_verdict + the (pending)
  human decision — in a shape the dashboard + report consume. Contract-first if it produces
  a durable/crossing artifact; otherwise a bounded transform with its own tests.
- **Why it matters:** it gives Phase 4 ONE consistent, auditable status shape and decouples
  the dashboard/report/gate stories from the raw tracking-item layout.

### Scope, Dependencies & Position

- **In scope:** the orchestration/assembly of the per-intake status read-model; the
  transform from the Hub tracking record → the consolidated status view; tests; a decision
  (contract-first) on whether the output is a new durable field/contract or an on-demand
  read transform; candidate control mappings (RD-014). **Confirm the exact 4.1 output shape
  + boundary with the stakeholder** (it feeds 4.2/4.5).
- **Out of scope / do NOT touch:** re-normalizing / re-correlating / re-scoring / rebuilding
  findings / re-deriving the verdict (those are 3.1-3.5, all done). The dashboard rendering
  (4.3), the JSON payload shape (4.2), the report (4.5), and the human accept/reject ACTION
  + routing (4.4/4.6/4.7) are downstream. **The 3.5 recommended_verdict stays ADVISORY** —
  4.1 surfaces it as a recommendation + the `human_decision: pending`; it never acts on it.
- **Depends on:** **3.5 ✅**. **Unblocks:** 4.2 (dashboard JSON), 4.5 (report), and via those
  the gate/routing (4.4/4.6/4.7). **This story OPENS Phase 4.**

### Approach & Constraints

- **Hard constraints:** READ/transform only over the derived Hub-side record; keep the
  RD-009/RD-013 boundary intact (no raw data, no Forensic durable store; if anything new is
  produced it is Hub-side derived); PURE logic + thin seams (the proven 1.2→3.5 pattern);
  docs first-class (RD-015), PR-reviewed.
- **The verdict stays advisory + human-gated (RD-040).** 4.1 surfaces the recommended_verdict
  as a recommendation alongside `human_decision`; it never promotes/routes/enforces.
- **AWS-native.** Any orchestration is AWS-native (no GitHub Actions for operations).
- **Roles:** if a LIVE step is needed it is the **stakeholder's**; the executor RECORDS.

### Validation Rationale & Compliance Mapping (REQUIRED — RD-014)

- **Rationale:** a single consolidated, auditable per-intake status read-model gives Phase 4
  one consistent shape to render/report/gate on, decoupled from the raw tracking layout.
- **Candidate control mappings** *(proposed; ratified on review):*

| Framework | Control ID | Control Name | Rationale | Status |
|-----------|-----------|--------------|-----------|--------|
| NIST 800-53 r5 | AU-6 | Audit Record Review/Analysis/Reporting | Consolidated per-intake status for review | Proposed |
| NIST 800-53 r5 | SI-4 | System Monitoring | Assembles monitored evidence for reporting | Proposed |
| NIST 800-53 r5 | CA-7 | Continuous Monitoring | Per-intake status feeds ongoing monitoring | Proposed |
| NIST CSF | DE.AE-2 | Analyzed events | Consolidated analysis surfaced to humans | Proposed |
| ISO 27001:2022 | A.8.16 | Monitoring activities | Status read-model over monitored evidence | Proposed |

### Management-Artifact Obligations (REQUIRED — RD-015)

- [ ] Story's brief + runbook entry updated (status, Validation Result, dates).
- [ ] PROJECT_PLAN and RUNBOOK in exact alignment (4.1 identical in both).
- [ ] If a genuinely new sub-decision arises, register the next free RD (after RD-040); CHECK E is literal — add its plan-table row BEFORE referencing the number in any living doc.
- [ ] All doc changes PR-reviewed (branch + PR, never straight to main).
- [ ] `check_docs` fixture `_NEW_WORK_STORY` repointed off 4.1 (→ the next still-⬜ feature story, e.g. 4.2) IN THE SAME PR.
- [ ] On validation pass: record Validation Result + flip ✅ (paired commit).
- [ ] Author the next-story handoff (the next Phase-4 story) with real Lessons Learned.

### Definition of Done / Validation Gate

- **Done means:** for one `intake_id` with the full Phase-3 record, 4.1 assembles the bounded
  per-intake status read-model (identity + per-stage status + scores + findings/remediations
  + advisory recommended_verdict + `human_decision`) validated against its shape and
  available to the downstream Phase-4 consumers; RD-009/RD-013 intact; the recommended_verdict
  stays advisory; validated live (if it touches the running pipeline) and recorded.
- **Validation Result:** `pending`.
- **On pass:** record dated result, flip 4.1 ✅ (paired commit), clear the register, keep
  PLAN ↔ RUNBOOK aligned.
- **On fail:** 4.1 stays 🟡 (added to the register in the same commit); fix + re-validate.

### Risks & Watch-Items

- **ADVANCEMENT GATE:** 3.5 must be ✅ (live-validated) first.
- **P3 → P4 transition** — 4.1 is the first Phase-4 story AND advances tier 12 → 13. Re-confirm
  the whole Phase-3 record is present + the P3 phase gate is satisfied.
- **READ/transform, do not re-derive** — 4.1 consumes 3.1-3.5; it does not re-run any
  assessment or make a model call.
- **The recommended_verdict is advisory (RD-040)** — 4.1 surfaces it + `human_decision`; the
  enforcing accept/reject is a human action in 4.4/4.6/4.7.
- **Deploy-gap** — if it touches `ZtieHubTrackingStack` (or a new stack), redeploy from the
  RIGHT branch; verify the LIVE resource after.

### Lessons Learned / Carry-Forward (from the 3.5 build, 2026-09-13)

- **The PURE-derived pattern held a 10th time.** 3.5 = a NEW `lambdas/hub_verdict/` Lambda:
  contract-first (`scripts/gen_verdict_contract.py` registered in `gen_contracts.py`,
  byte-identical `schemas/` + lambda copies via `contract_writer`), PURE logic (`verdict.py`)
  + a thin DynamoDB-only `awsio` seam (NO Bedrock — the mapping is deterministic), a stream
  handler with a `Decimal`-canonicalized fingerprint guard, and a two-layer conformance test
  (stdlib walk + `jsonschema` `skipUnless`). If 4.1 produces a durable Hub-side field, reuse
  this exact skeleton; if 4.1 is a pure read transform (e.g. behind an API/orchestrator),
  keep the pure-logic + thin-seam split and the same test rigor.
- **3.5 is the FIRST + ONLY verdict-bearing record; 4.1 must keep it that way.** 4.1 surfaces
  the 3.5 `recommended_verdict` + `human_decision: pending`; it must NOT write a verdict onto
  any other record and must NOT relax the 3.1-3.4 no-verdict scans (nor 3.5's own
  advisory-only invariants). If 4.1 emits a consolidated view, that view may ECHO the advisory
  recommended_verdict (clearly labelled advisory + carrying `human_decision`) but must never
  present or persist it as an effective/enforced decision.
- **`verdict_result` (RD-040) shape 4.1 consumes:** top-level `contract_version` / `intake_id`
  / `sha256` / `recommended_at` / `status` (`recommended` / `incomplete` / `no_scores`) /
  `recommended_verdict` (PASS / FAIL / INCONCLUSIVE) / `human_decision` (always `pending`) +
  optional `rubric_version` / `status_detail` / `recommendation_basis` (with `driver`,
  `combined_score`, `scores` echoes, `contradiction_present`, `evidence_complete`,
  `override_reasons`, `summary`). The full per-intake record also carries `combined_event`,
  `correlation_result`, `scoring_result`, `remediation_result`.
- **RD hygiene:** RD-040 is 3.5's. `grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md | sort -u | tail`
  for the next FREE number if 4.1 needs a new RD (expect RD-041, but VERIFY). **CHECK E is
  literal** — add the new RD's plan-table row BEFORE referencing the number in any living doc.
- **The offline bar (unchanged):** `~/.pyenv/versions/3.12.13/bin/python3 -m unittest`
  (pytest is NOT installed — use `unittest`); `~/.pyenv/versions/3.12.13/bin/ruff check`
  (DEFAULT rules — a generator script needs the exec bit `chmod +x` or EXE001 fires; a walrus
  bound to an unused var trips F841; watch RUF046/RUF059/ISC004/BLE001); `env -u NODE_OPTIONS
  npx tsc --noEmit` shows ONLY the missing-`aws-cdk-lib` family — the `main` baseline is
  **106 errors** and adding a stack Lambda adds `__dirname` TS2304 (an EXISTING type — count
  deltas within an existing type are fine; confirm NO NEW error TYPE); `env -u NODE_OPTIONS
  npx prettier --check` the stack, and run `--write` if it flags (purely additive is fine).
  `jsonschema` is NOT installed offline, so the LIVE conformance layer is `skipUnless`-skipped.
- **check_docs fixture:** `scripts/test_check_docs.py` `_NEW_WORK_STORY` is now **4.1**.
  **When 4.1 leaves ⬜, repoint it to the next still-⬜ feature story (4.2) IN THE SAME PR**,
  then re-run `python3 -m unittest scripts.test_check_docs` (SUITE line OK).
- **check_docs CHECK I (links):** if you reference a not-yet-authored doc in a LIVING doc
  (e.g. the on-deck README), CHECK I FAILS until that file exists. Author the next-story
  handoff files BEFORE pointing the on-deck README at them (or point at the 4.1 LIVE-RUNBOOK).
- **check_docs timing (RD-015):** run `check_docs.py` only AFTER committing status/register
  edits (CHECK B baseline is `git show HEAD:RUNBOOK.md`). Set 4.1 🟡 AND add it to the register
  in the SAME commit.
- **Stale-branch trap:** cut `feature/story-4.1` from the LATEST `main` (after 3.5 merges).
  The 3.5 branch was cut before RD-040's PR #120 landed and had to reconcile with `git merge
  origin/main` — avoid that by branching from current `main`.
- **User notes:** *(open for the stakeholder — especially the exact 4.1 output shape/boundary
  and whether 4.1 produces a durable Hub field vs. an on-demand read transform.)*

> **Sequencing note:** 4.1 (status-retrieval orchestrator) is next by tier after 3.5 — but
> ONLY after 3.5 clears its live pass (advancement gate). It OPENS Phase 4 and unblocks
> 4.2/4.5 and, through them, the gate/routing stories (4.4/4.6/4.7).
