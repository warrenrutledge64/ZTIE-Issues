# Session Brief — Story 3.1

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.

---

## Story 3.1 — Telemetry aggregation / normalization (shared schema)

| Field | Value |
|-------|-------|
| **Phase** | P3 — Correlation & Synthesis (the entry story) |
| **Date** | TBD (next session) |
| **Status** | ⬜ Not Started (build tier 6; the next Phase-3 story — but see the ADVANCEMENT GATE below) |
| **Depends on** | **2.6 ✅** (the parallel fork/join that produces both lane outputs to aggregate). Plus, in practice, the SANITIZED dynamic telemetry from **2.5** and the static findings from **2.1/2.2** are the inputs 3.1 normalizes. |
| **Builds from restore point** | Branch the CODE off current `main` (which must contain merged 2.5 by the time 3.1 begins). |
| **Session goal** | Aggregate the per-lane derived outputs for one `intake_id` — the static-scan summary (2.1/2.2), the dynamic-run outcome (2.3), and the SANITIZED behavioral telemetry (2.5) — into ONE shared, normalized combined-event record that the Phase-3 Nova Pro correlation engine (3.2) consumes. |

---

### ⚠️ ADVANCEMENT GATE (read FIRST at STEP 0)

**As of the 2.5 session (2026-09-10), the Validation Debt Register has ONE open entry:
Story 2.5 (🟡, built, awaiting its live pass).** The advancement gate is therefore
**ARMED**: **Story 3.1 is a NEW feature story and MAY NOT BEGIN until 2.5 is cleared by
its own recorded live pass** (see the [2.5 LIVE-RUNBOOK](story-2.5-LIVE-RUNBOOK.md)).
STEP 0 must RE-CONFIRM on `main` that 2.5 is ✅ and the register is EMPTY before touching
anything (trust `main` + `check_docs`). If 2.5 is still 🟡, the ONLY permitted work is
validating/reworking 2.5 — not starting 3.1. This is `check_docs` CHECK B, machine-enforced.

---

### Background & Context

ZTIE is a four-phase AWS-native security pipeline; work is validation-gated (nothing is
✅ until a recorded live pass — the covenant). Phase 2 produced, for one artifact, THREE
bounded derived records on the Hub tracking item (all verdict-free, all crossed via the
RD-013 gate): the **static-scan summary** (`scan`, 2.1/2.2), the **dynamic-run outcome**
(`run`, 2.3), the **behavioral summary** (`behavior`, 2.4) and — new in 2.5 — the
**sanitized telemetry view** (`sanitized`, the ≤25K-token, entropy-scrubbed,
noise-suppressed event sequence). 2.6 forks + joins the two LANES into a `collected`
record. **Story 3.1 is the first Phase-3 story: it NORMALIZES those per-lane derived
outputs into one shared combined-event schema** so Nova Pro (3.2) reasons over a single,
consistent record rather than four differently-shaped ones.

### What This Story Is (nature + gate role)

**Nature: NEW FEATURE story.** It may begin ONLY if its Depends-on are ALL ✅ **and** the
Validation Debt Register is empty (see the gate above — 2.5 must clear first). It is the
Phase-3 entry story; 3.2 (Nova Pro correlation) depends on it.

### Objective & Value

- **Objective:** a shared normalized combined-event record (contract-first) that
  aggregates, for one `intake_id`, the static findings + the dynamic run outcome + the
  sanitized behavioral telemetry into a single consistent shape, keyed by
  `intake_id`+`sha256`, verdict-free. Decide CONTRACT-FIRST **where this record lives and
  whether it is produced Hub-side** (the Hub already holds all four derived records on the
  tracking item — aggregation may be a Hub-side read+normalize+write, NOT a new Forensic
  crossing) **or a new derivation**; do not re-cross raw data.
- **Why it matters:** Nova Pro correlation (3.2) needs ONE normalized record — static
  misconfigurations aligned with dynamic behavioral indicators on a common schema — not
  four bespoke shapes. 3.1 is what makes the evidence correlatable.

### Scope, Dependencies & Position

- **In scope:** the shared normalized-event schema (contract-first); the aggregation/
  normalization logic (PURE + offline-testable, the proven lane pattern); where it lives
  (likely Hub-side, since all inputs already sit on the Hub tracking record — confirm);
  tests; a new RD for the aggregation design + candidate control mappings (RD-014).
- **Out of scope / do NOT touch:** the Nova Pro CALL itself (that is 3.2); any verdict
  (stays Hub-side / human-gated, Phase 4); re-capturing or re-sanitizing telemetry (2.4/
  2.5 done); the static or dynamic lane internals.
- **Depends on:** **2.6 ✅** + (as inputs) 2.1/2.2 + 2.5. Plus an **empty Validation Debt
  Register** (2.5 cleared).
- **Unblocks:** 3.2 (Nova Pro correlation consumes the normalized combined record).
- **Roadmap position:** P3 entry — the aggregation/normalization stage that feeds
  correlation.

### Approach & Constraints

- **Expected true-state (STEP 0 re-confirms; trust `main` + `check_docs`):** 2.5 ✅
  (only after its live pass); Validation Debt Register EMPTY; advancement gate OPEN. Next
  free RD number: re-verify with `grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md | sort -u |
  tail` (RD-031 is 2.5's; expect RD-032, but VERIFY — collisions have happened).
- **Hard constraints:** aggregate/normalize, do not re-capture or re-cross raw data;
  output is EVIDENCE, never a verdict; keep the RD-009/RD-013 boundary intact (full detail
  stays in Forensic; the Hub holds only bounded derived data); production code (no mock
  data); PURE logic + thin seams; docs first-class (RD-015), PR-reviewed.
- **Roles:** if a LIVE step is needed it is the **stakeholder's** action; the **executor
  RECORDS** verbatim. Do NOT simulate.

### Validation Rationale & Compliance Mapping (REQUIRED — RD-014)

- **Rationale:** a single normalized record is what makes cross-lane correlation possible
  and auditable; normalization without a verdict keeps the human gate authoritative.
- **Candidate control mappings** *(proposed; ratified on review):*

| Framework | Control ID | Control Name | Rationale | Status |
|-----------|-----------|--------------|-----------|--------|
| NIST 800-53 r5 | SI-4 | System Monitoring | Aggregates monitored evidence into an analyzable record | Proposed |
| NIST 800-53 r5 | AU-6 | Audit Record Review/Analysis | Normalization prepares records for correlation/review | Proposed |
| NIST CSF | DE.AE-3 | Event data are aggregated and correlated | The combined record is the aggregated event set | Proposed |
| ISO 27001:2022 | A.8.16 | Monitoring activities | Consolidates monitored behavior for analysis | Proposed |

### Management-Artifact Obligations (REQUIRED — RD-015)

- [ ] Story's brief + runbook entry updated (status, Validation Result, dates).
- [ ] PROJECT_PLAN and RUNBOOK in exact alignment (3.1 identical in both).
- [ ] New RD (aggregation/normalization design) recorded; candidate mappings recorded.
- [ ] All doc changes PR-reviewed (branch + PR, never straight to main).
- [ ] Governance kept restorable alongside the code.
- [ ] On validation pass: record Validation Result + flip ✅ (paired commit).
- [ ] Author the next-story handoff (3.2 Nova Pro correlation) with real Lessons Learned.

### Definition of Done / Validation Gate

> A pass/fail gate, not a description.

- **Done means:** for one `intake_id`, the static + dynamic + sanitized-telemetry outputs
  normalize into ONE combined record on the shared schema, verdict-free, keyed by
  `intake_id`+`sha256`, with the RD-009/RD-013 boundary intact; validated (live if it
  touches the running pipeline; offline conformance otherwise) and recorded.
- **Validation Result:** `pending`.
- **On pass (and only then):** record the dated Validation Result, flip 3.1 ✅ (paired
  commit), keep PLAN ↔ RUNBOOK aligned.
- **On fail:** 3.1 stays 🟡 (added to the Validation Debt Register in the same commit);
  fix + re-validate.

### Risks & Watch-Items

- **ADVANCEMENT GATE (highest priority):** 2.5 must be ✅ first. Do not start 3.1 while
  2.5 is 🟡 — that is exactly the drift `check_docs` CHECK B blocks.
- **CONTRACT-FIRST placement decision:** the four inputs already live on the Hub tracking
  record, so 3.1 is likely a Hub-side normalize (read the record → build the combined
  event → write it back), NOT a new Forensic→Hub crossing. Decide + justify in the RD;
  do NOT re-cross raw data or reintroduce a Forensic durable store (RD-012).
- **Evidence, never a verdict** — the combined record has no verdict/safe/forward field.
- **Ordering / partial inputs:** a lane's derived record may not have landed yet when
  aggregation runs (SQS ordering, or a `no_trace`/`errored` lane). Normalize honestly —
  record which inputs are present, never fabricate a missing one.

### Lessons Learned / Carry-Forward (from the 2.5 build session, 2026-09-10)

- **The lane pattern held a 5th time (1.2→2.2→2.3→2.4→2.5):** contract-first + a new
  envelope kind with its OWN version pin + a UNIQUE discriminator + PURE logic + a thin
  `awsio` seam + evidence-never-verdict. Reuse it for 3.1's record. The `sanitized` kind
  is the **9th** RD-013 kind (`sanitized-telemetry.contract.v1`,
  `SANITIZED_TELEMETRY_CONTRACT_VERSION`). If 3.1 crosses/derives a new record, it is a
  candidate 10th kind — grep the existing discriminators (classification/routing/
  rejection/scan/run/status/collected/behavior/sanitized) so the new one does not collide.
- **NEW RECURRING LESSON — the `check_docs` self-test fixture drifts when the pinned
  story advances.** `scripts/test_check_docs.py` pins `_NEW_WORK_STORY` to a downstream ⬜
  master-table story to drive its CHECK A / CHECK B self-tests. When 2.5 went 🟡 this
  session, the fixture's mutations against 2.5 became no-ops and BOTH self-tests FAILED
  (real failures — NOT the harmless `check_docs: FAIL …` fixture-print lines). Fix:
  repointed `_NEW_WORK_STORY` from 2.5 → **3.1**. **When 3.1 leaves ⬜ (i.e. this story
  starts/finishes), repoint `_NEW_WORK_STORY` to the next still-⬜ master-table feature
  story (e.g. 3.2/3.3) IN THE SAME PR, and re-run `python3 -m unittest
  scripts.test_check_docs` to confirm OK / 3 tests.** Distinguish the two: the suite
  reporting `FAILED (failures=N)` is a REAL problem; the `check_docs: FAIL …` lines it
  prints while exercising itself against the pinned story are expected.
- **`check_docs` timing:** run `python3 scripts/check_docs.py` only AFTER committing any
  status/register edit (CHECK B's baseline is `git show HEAD:RUNBOOK.md`). It PASSED for
  2.5 with 2.5 in the register.
- **Deploy-gap (if 3.1 touches a lane Lambda):** any code change to a lane Lambda only
  takes effect after `cdk deploy`; if 3.1 is Hub-side, the redeploy is `ZtieHubTrackingStack`
  (which must ship any new/updated contract bundle or the crossed record fail-closed
  quarantines). Put the redeploy as an explicit pre-run step in the 3.1 LIVE-RUNBOOK.
- **Offline proof bar (INTEGRATIONS_ONLY sandbox):** `ruff` at
  `~/.pyenv/versions/3.12.13/bin/ruff`; `prettier`/`npx tsc` need `env -u NODE_OPTIONS`;
  `tsc --noEmit` legitimately shows ONLY the missing-`aws-cdk-lib` family
  (TS2304/2307/2339/2353/2591) — confirm NO NEW error type. jsonschema/moto/boto3 not
  installable — prove contracts with a stdlib pure-Python conformance walk + a
  jsonschema-`skipUnless` live layer, and stub boto3/jsonschema in `sys.modules` for the
  Hub dispatch tests.
- **User notes:** *(open for the stakeholder to add anything before the 3.1 session.)*

> **Sequencing note:** 3.1 (telemetry aggregation / normalization) is the Phase-3 entry
> story and the next by tier — but ONLY after 2.5 clears its live pass (advancement gate).
> It normalizes the per-lane derived outputs into the one shared record Nova Pro (3.2)
> consumes.
