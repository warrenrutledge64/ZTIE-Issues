# Session Brief — Story 3.3 (RD-038 rework)

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.
>
> **This brief supersedes the RD-037 version of 3.3.** 3.3 was first built (RD-037,
> PR #104) as PURE post-processing that produced an `accuracy` + `gap_analysis`
> `synthesis_result` — but it was NEVER live-validated, and a stakeholder
> course-correction (**RD-038**) re-scoped it. See the design record:
> [`docs/proposals/phase3-three-score-model.md`](../proposals/phase3-three-score-model.md).

---

## Story 3.3 — Three Nova Pro risk scores (static / dynamic / combined)

| Field | Value |
|-------|-------|
| **Phase** | P3 — Correlation & Synthesis |
| **Build tier** | 10 (WITHIN Phase 3). Depends-on `3.2` ✅ (+ its inputs `3.1` + `2.5`). |
| **Date** | TBD |
| **Status** | 🟡 Reworked to RD-038 + offline-proven; awaiting recorded live validation. It is the sole open Validation Debt Register entry, so the advancement gate is ARMED (no new downstream feature — 3.4 — may start until 3.3 clears). |
| **Depends on** | **3.2 ✅** (the bounded, verdict-free Nova Pro `correlation_result`) — and the per-lane derived evidence 3.1 aggregated (the static-scan summary + the sanitized behavioral telemetry / run outcome on the Hub tracking item). |
| **Builds from** | The RD-037 `lambdas/hub_synthesize/` code already on `main` (PR #104). Rework it in place on `feature/story-3.3` (or a fresh branch off `main`). |
| **Session goal** | Produce **THREE independent 0-100 risk scores** for one `intake_id` — **static**, **dynamic**, and **combined** — each by a SEPARATE Amazon Nova Pro call over the derived Hub-side evidence, on a SHARED 0-100 rubric, recorded as a bounded, verdict-free scoring result on the Hub tracking item. Each score is EVIDENCE; the verdict stays human-gated (3.5). |

---

### ⚠️ ADVANCEMENT GATE (read FIRST at STEP 0)

3.3 is the sole open Validation Debt Register entry, so the gate is ARMED — no NEW
downstream feature story (3.4) may begin until 3.3 clears its recorded live pass.
**Reworking 3.3 itself is the permitted work** (reworking a 🟡 story is normal — the
covenant working, not a violation). STEP 0 must re-confirm on `main`: 3.3 is 🟡 and on the
register; 3.2 (+ 3.1, 2.5) ✅. Trust `main` + `check_docs` over this brief; if they
disagree, `main` wins.

---

### Background & Context

Phase 3 turns paired static + dynamic evidence into a decision-ready assessment. Story 3.1
(RD-033) normalized the per-lane derived outputs into ONE `combined_event`; Story 3.2
(RD-035) correlated it with Amazon Nova Pro into a verdict-free `correlation_result`.

**The RD-038 correction:** the Phase-3 assessment must be **three independent 0-100 risk
scores** — static and dynamic as **peers** (neither the default point of view), plus a
genuine **combined** assessment — all produced by **Nova Pro**, not one static-centric
metric. The first 3.3 build (RD-037) produced a static-scoped `accuracy_score`
(`confirmed / (confirmed + static_only)`) that did not weigh dynamic evidence as a peer;
RD-038 drops it. (The list-shaped synthesis content — candidate-false-positive list + gap
list + by-kind counts — is NOT thrown away; it MIGRATES to Story 3.4 to feed the
prioritized remediations. 3.3's rework is JUST the three scores.)

### What This Story Is (nature + gate role)

**Nature: a 🟡 REWORK** (not new work). It reworks the already-built `hub_synthesize`
Lambda + its contract to produce the three Nova Pro risk scores instead of the
`accuracy`/`gap_analysis` `synthesis_result`. It clears its Validation Debt Register entry
only on a recorded live pass of the reworked code.

### Objective & Value

- **Objective:** three independent 0-100 risk scores (static / dynamic / combined) for one
  `intake_id`, each produced by a separate Nova Pro call over the derived Hub-side
  evidence, on a shared rubric, recorded as a bounded, DERIVED, verdict-free scoring
  result on the Hub tracking item.
- **Why it matters:** this is the risk read the dashboard + the per-execution report
  (Phase 4) surface and the verdict (3.5) derives from — now with static and dynamic
  weighted as peers and a genuine combined assessment, per the stakeholder's definition.

### Scope, Dependencies & Position

- **In scope:**
  - **Three separate Nova Pro calls** (RD-038): a **static** call (sees ONLY the static
    lane's derived evidence — the static-scan findings + severities on the tracking item),
    a **dynamic** call (sees ONLY the dynamic lane's derived evidence — the sanitized
    behavioral telemetry / run outcome), and a **combined** call (sees BOTH lanes' raw
    derived evidence TOGETHER — NOT the two scores). Each returns a bounded **0-100 risk
    score + short rationale**.
  - A **shared 0-100 rubric** stated in all three prompts so the scores are directly
    comparable (a "40" means the same magnitude of risk from any call); only the evidence
    each call sees differs, never the scale.
  - Reuse the proven 3.2 `awsio.invoke_nova` **exponential-backoff + jitter retry** per
    call (RD-003); parse each response DEFENSIVELY into a bounded 0-100 int; a
    malformed/absent/throttled response is RECORDED via that score's own `status`, never
    fabricated (per-score honest status → **partial results are fine**: one call failing
    does not sink the other two).
  - A contract-first **scoring-result schema** (bounded, allow-list, own version pin,
    verdict-free) recording the three scores + rationales + per-score statuses.
  - The `bedrock:InvokeModel` grant on `hub_synthesize` scoped to EXACTLY the Nova Pro
    model/profile ARNs (never `*`) — this rework RE-INTRODUCES a Bedrock call + grant that
    the RD-037 build deliberately did not have.
  - Tests; update the RD reference (RD-038); the LIVE-RUNBOOK re-issued to the three-score
    definition.
- **Out of scope / do NOT touch:** the enforcement VERDICT (3.5); the detailed findings +
  prioritized remediations + the migrated candidate-FP/gap lists (**that is 3.4** now);
  re-correlating (3.2 done); the ✅ static/dynamic lanes (RD-038 needs NO lane change —
  all scoring is Hub-side over evidence that already crosses).
- **Depends on:** 3.2 ✅ (+ 3.1, 2.5). **Unblocks:** 3.4.

### Approach & Constraints

- **Hard constraints:** three separate scoped Nova Pro calls; shared 0-100 rubric; each
  score is EVIDENCE, **NEVER a verdict** (no verdict/safe/approved/forward/pass_fail/
  malicious/clean field; each prompt asks for a RISK SCORE ONLY, never a decision); "raw
  evidence" = the sanitized/derived Hub-side evidence, NEVER the payload/raw trace
  (RD-008/009); REAL Nova Pro calls with exponential-backoff retry (RD-003), no mock model;
  defensive parse + honest per-score status; PURE score-assembly logic + the thin `awsio`
  seam; keep the RD-009/RD-013 boundary intact; docs first-class (RD-015), PR-reviewed.
- **Reuse:** the 3.2 correlator (`lambdas/hub_correlate/`) is the closest pattern — a
  Hub-side, DynamoDB-stream-triggered Lambda that calls Nova Pro with backoff retry, parses
  defensively, and writes an integrity-bound verdict-free record. 3.3 is the same shape,
  but **three calls** producing **scores** (not one call producing a correlation).
- **Idempotency / call-storm guard:** reuse the fingerprint guard (a `Decimal`-canonicalized
  content hash of the evidence the scores are built over) so the three calls fire once per
  settled evidence, not on every item mutation — critical now that 3.3 makes real (paid)
  model calls again.
- **Roles:** the LIVE step is the **stakeholder's** (Bedrock model access must be enabled
  for the Hub account); the executor RECORDS verbatim. Do NOT simulate.

### Validation Rationale & Compliance Mapping (REQUIRED — RD-014)

- **Rationale:** three independent, comparably-scaled risk scores from Nova Pro (static +
  dynamic as peers + a combined assessment) give a faithful, reproducible risk read while
  keeping the verdict human-gated.
- **Candidate control mappings** *(proposed; ratified on review):*

| Framework | Control ID | Control Name | Rationale | Status |
|-----------|-----------|--------------|-----------|--------|
| NIST 800-53 r5 | RA-3 | Risk Assessment | Three independent risk scores | Proposed |
| NIST 800-53 r5 | RA-5 | Vulnerability Monitoring/Scanning | Static-evidence risk score | Proposed |
| NIST 800-53 r5 | SI-4 | System Monitoring | Dynamic-behavior risk score | Proposed |
| NIST CSF | ID.RA-5 | Threats/vulnerabilities/likelihood → risk | Unified/combined risk score | Proposed |
| ISO 27001:2022 | A.8.16 | Monitoring activities | Scores the monitored evidence | Proposed |

### Management-Artifact Obligations (REQUIRED — RD-015)

- [x] Story's brief + runbook entry updated (this brief; runbook 3.3 row + register → "built, awaiting live").
- [x] PROJECT_PLAN and RUNBOOK in exact alignment (3.3 identical in both).
- [x] RD reference is **RD-038** (registered); candidate mappings recorded.
- [x] All changes PR-reviewed (branch `feature/story-3.3` + PR, never straight to main).
- [x] `check_docs` fixture `_NEW_WORK_STORY` still pinned to 3.4 (unchanged by this rework — confirmed; a downstream ⬜ story).
- [ ] On validation pass: record Validation Result + flip ✅ (paired commit); clear the
      register. _(pending the recorded live Hub pass)_
- [x] Re-issued the 3.3 LIVE-RUNBOOK to the three-score definition.
- [ ] Refresh the 3.4 handoff (it now receives three scores + inherits the migrated
      candidate-FP/gap lists) — _do at session end._

### Definition of Done / Validation Gate

- **Done means:** for one `intake_id`, three bounded **0-100** risk scores (static /
  dynamic / combined) — each from a separate Nova Pro call, on the shared rubric, with a
  rationale + honest per-score status — are recorded verdict-free on the tracking item;
  **no verdict/safe/forward field anywhere**; the combined score reasons over BOTH lanes'
  raw derived evidence (not the two lane scores); RD-009/RD-013 boundary intact; validated
  LIVE (real Nova Pro calls, retry inspectable) and recorded.
- **Validation Result:** `pending`.
- **On pass:** record dated result, flip 3.3 ✅ (paired commit), clear the register.
- **On fail:** 3.3 stays 🟡; fix + re-validate.

### Risks & Watch-Items

- **Evidence, never a verdict** — three prompts ask for a risk score only; no verdict field
  anywhere; the score scale is a risk metric, not a decision.
- **Comparable rubric** — if the three prompts don't share the same 0-100 anchoring, the
  scores aren't comparable; state the rubric identically in all three.
- **Combined ≠ arithmetic** — the combined call must reason over BOTH lanes' raw evidence,
  NOT be a formula over the two lane scores.
- **Cost/latency + retry × 3** — three real Nova Pro calls per artifact; the fingerprint
  call-storm guard matters more now (a stream loop = 3× the paid calls per mutation).
- **Bedrock is BACK** — the RD-037 build had no Bedrock; the rework re-adds the client +
  the scoped `bedrock:InvokeModel` grant. Bedrock model access must be enabled for the Hub
  account (STEP 0 of the LIVE-RUNBOOK), or the first call fails `AccessDeniedException`.
- **Deploy-gap (both modes)** — redeploy `ZtieHubTrackingStack` from the RIGHT branch;
  verify the LIVE Lambda env + the scoped Bedrock policy after.

### Lessons Learned / Carry-Forward (from the RD-037 build + the RD-038 correction)

- **The RD-037 build validated the SHAPE, not the content.** Its Hub-side derivation, the
  contract-first + pure-logic + thin-seam + own-version-pin + evidence-never-verdict
  pattern, the `Decimal`-canonicalized fingerprint guard, and the two-layer conformance
  test all carry straight into the rework. What changes is WHAT it produces (three scores,
  not accuracy/gaps) and that it calls Nova Pro (three times).
- **The 3.2 correlator is the template for the model calls** — `awsio.invoke_nova`
  (exponential-backoff + jitter, bounded attempts, returns attempt count), defensive parse,
  honest status, scoped Bedrock grant. Copy that per call.
- **RD-number + collision hygiene:** RD-038 is registered; do NOT invent a new RD for the
  rework (it IS RD-038).
- **`accuracy_score` is DROPPED, the lists MIGRATE.** Do not re-implement `accuracy_score`.
  Do not build the candidate-FP/gap lists here — they belong to 3.4 now.
- **User notes:** *(open for the stakeholder.)*

> **Sequencing note:** 3.3 (three Nova Pro risk scores) reworked per RD-038; on its live
> pass it clears the register and unblocks 3.4 (detailed findings + prioritized
> remediations, which inherits the migrated candidate-FP/gap lists).
