# Session Brief — Story 3.4 (RD-038 scope)

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.
>
> **Re-scoped by RD-038.** Under the corrected Phase-3 model, **Story 3.3 now produces
> the risk SCORES** (three independent 0-100 Nova Pro scores: static / dynamic /
> combined). **Story 3.4 no longer scores** — it produces the **detailed findings +
> prioritized remediations** over those three scores, and it is the new home of the
> list-shaped synthesis content (candidate-false-positive list + gap list + by-kind
> counts) that migrated out of the old 3.3. Design record:
> [`docs/proposals/phase3-three-score-model.md`](../proposals/phase3-three-score-model.md).

---

## Story 3.4 — Detailed findings + prioritized remediations

| Field | Value |
|-------|-------|
| **Phase** | P3 — Correlation & Synthesis |
| **Build tier** | 11 — **advances tier 10 → 11** (a new dependency layer opens: `3.3` at tier 10 goes ✅). A TIER move WITHIN Phase 3 (no phase transition). STEP 0 must re-confirm the tier-≤10 dependency set (`3.3` + its input `3.2`) is ✅. |
| **Date** | TBD (next session) |
| **Status** | ⬜ Not Started (build tier 11 — but see the ADVANCEMENT GATE below). |
| **Depends on** | **3.3 ✅** (the bounded, verdict-free `scoring_result` — three 0-100 Nova Pro risk scores — plus the 3.2 `correlation_result` it can read for the finding detail). |
| **Builds from restore point** | Branch the CODE off current `main` (which must contain merged + LIVE-VALIDATED 3.3 by the time 3.4 begins). |
| **Session goal** | For one `intake_id`, produce **detailed findings + a prioritized remediation list** from 3.3's three risk scores + the correlation findings, recorded as a bounded, verdict-free result on the Hub tracking item. This is the new home of the migrated candidate-false-positive + gap lists. Still evidence-only — the enforcement VERDICT (PASS/FAIL/INCONCLUSIVE) is Story 3.5. |

---

### ⚠️ ADVANCEMENT GATE (read FIRST at STEP 0)

**3.4 is a NEW FEATURE story. It may begin ONLY if its Depends-on are ALL ✅ AND the
Validation Debt Register is EMPTY.** As of this brief's authoring, **Story 3.3 (reworked
to RD-038) sits 🟡 on the register awaiting its recorded LIVE pass** (see
`story-3.3-LIVE-RUNBOOK.md`). So the gate is expected ARMED until 3.3 is validated live.
STEP 0 MUST re-confirm on `main`: `3.3` ✅ and the register EMPTY (trust `main` +
`check_docs`; if they disagree, `main` wins). **If 3.3 is still 🟡, 3.4 MAY NOT begin —
the only permitted work is validating/reworking 3.3.** `check_docs` CHECK B, machine-enforced.

---

### Background & Context

Phase 3 turns paired static + dynamic evidence into a decision-ready assessment. Story 3.1
(RD-033) normalized the per-lane outputs into ONE `combined_event`; Story 3.2 (RD-035)
correlated it with Amazon Nova Pro into a verdict-free `correlation_result`; **Story 3.3
(RD-038) produced three independent 0-100 Nova Pro risk scores** (static / dynamic /
combined, shared rubric) recorded as a `scoring_result`. **Story 3.4 is the findings +
remediations step:** turn those scores + the correlation findings into a human-readable
detailed findings view and a **prioritized remediation** list the human gate + the Phase-4
report consume. It feeds 3.5 (verdict derivation).

### What This Story Is (nature + gate role)

**Nature: NEW FEATURE story.** It may begin ONLY if 3.3 is ✅ and the register is empty. It
consumes 3.3's `scoring_result` (three scores + rationales) and the 3.2 `correlation_result`
(the categorized findings) and produces the ranked remediations 3.5 + the human gate read.

### Objective & Value

- **Objective:** for one `intake_id`, a bounded, DERIVED, verdict-free result on the Hub
  tracking item containing (a) **detailed findings** — the categorized correlation findings
  + the migrated candidate-false-positive list + gap list (static_uncorroborated /
  dynamic_unexplained / contradiction / coverage) — and (b) a **prioritized remediation
  list** ranked by the three risk scores + finding/gap severities. Contract-first, own
  version pin, Hub-side (mirroring 3.1/3.2/3.3 placement); decide + justify in the new RD.
- **Why it matters:** the scores say *how risky*; 3.4 says *what specifically is wrong and
  what to fix first* — the actionable content the dashboard + per-execution report surface.

### Scope, Dependencies & Position

- **In scope:** the findings + remediation logic (very likely PURE post-processing of the
  already-structured 3.3 scores + 3.2 findings — like 3.3's lane-score assembly was pure
  around the model calls; decide + justify in the RD, and note 3.4 may need NO model call
  at all); the migrated candidate-FP + gap lists (build them HERE from the correlation
  findings — they are no longer in 3.3); a prioritized-remediation ranking; a contract-first
  result schema (bounded, allow-list, own version pin, verdict-free); tests; a new RD +
  candidate control mappings (RD-014).
- **Out of scope / do NOT touch:** the three risk SCORES (that is 3.3, done); the
  enforcement VERDICT (3.5, human-gated); re-scoring / re-correlating / re-normalizing.
- **Depends on:** **3.3 ✅**. **Unblocks:** 3.5 (verdict derivation, closes Phase 3).

### Approach & Constraints

- **Hard constraints:** produce findings + remediations, do not re-score/re-correlate; the
  output is EVIDENCE + a to-do list, **NEVER a verdict** (no verdict/safe/approved/forward/
  pass_fail/malicious/clean field); keep the RD-009/RD-013 boundary intact (reason only over
  the derived Hub-side scores + findings, no raw data, no Forensic durable store); PURE logic
  + thin seams; if it calls Nova Pro (probably NOT needed — the inputs are already
  structured), a REAL call with exponential-backoff retry (RD-003); docs first-class
  (RD-015), PR-reviewed.
- **Prefer PURE (the 3.3/3.1 precedent):** once the evidence is structured (three scores +
  categorized findings), building a findings view + ranking remediations is deterministic —
  almost certainly no model call. Justify the decision in the RD.
- **Roles:** if a LIVE step is needed it is the **stakeholder's**; the executor RECORDS.

### Validation Rationale & Compliance Mapping (REQUIRED — RD-014)

- **Rationale:** a ranked, reproducible remediation list + detailed findings over the three
  risk scores makes the assessment actionable + auditable while keeping the verdict human-gated.
- **Candidate control mappings** *(proposed; ratified on review):*

| Framework | Control ID | Control Name | Rationale | Status |
|-----------|-----------|--------------|-----------|--------|
| NIST 800-53 r5 | RA-5 | Vulnerability Monitoring/Scanning | Prioritized remediations for flagged findings | Proposed |
| NIST 800-53 r5 | RA-7 | Risk Response | Ranked response actions | Proposed |
| NIST 800-53 r5 | SI-4 | System Monitoring | Detailed findings over monitored evidence | Proposed |
| NIST CSF | ID.RA-6 | Risk responses are identified and prioritized | Prioritized remediations | Proposed |
| ISO 27001:2022 | A.8.8 | Management of technical vulnerabilities | Ranked remediations | Proposed |

### Management-Artifact Obligations (REQUIRED — RD-015)

- [ ] Story's brief + runbook entry updated (status, Validation Result, dates).
- [ ] PROJECT_PLAN and RUNBOOK in exact alignment (3.4 identical in both).
- [ ] New RD (findings + remediations design) recorded; candidate mappings recorded.
- [ ] All doc changes PR-reviewed (branch + PR, never straight to main).
- [ ] `check_docs` fixture `_NEW_WORK_STORY` repointed off 3.4 (→ 3.5) IN THE SAME PR.
- [ ] On validation pass: record Validation Result + flip ✅ (paired commit).
- [ ] Author the next-story handoff (3.5 verdict derivation) with real Lessons Learned.

### Definition of Done / Validation Gate

- **Done means:** for one `intake_id` with a `scoring_result`, 3.4 produces a bounded,
  verdict-free result with detailed findings (incl. the migrated candidate-FP + gap lists) +
  a prioritized remediation list validated against its schema and recorded on the tracking
  item; RD-009/RD-013 intact; validated live (if it touches the running pipeline) and recorded.
- **Validation Result:** `pending`.
- **On pass:** record dated result, flip 3.4 ✅ (paired commit), clear the register, keep
  PLAN ↔ RUNBOOK aligned.
- **On fail:** 3.4 stays 🟡 (added to the register in the same commit); fix + re-validate.

### Risks & Watch-Items

- **ADVANCEMENT GATE:** 3.3 must be ✅ (live-validated) first.
- **Evidence, never a verdict** — findings + remediations are actionable evidence; no
  verdict/safe/forward field; the PASS/FAIL/INCONCLUSIVE decision is 3.5.
- **Prefer PURE** — the inputs are already structured (three scores + categorized findings);
  a model call is very likely unnecessary. Justify in the RD.
- **The lists live HERE now** — the candidate-FP + gap lists are NOT in 3.3's output
  anymore; 3.4 builds them from the 3.2 `correlation_result` findings.
- **Deploy-gap** — redeploy `ZtieHubTrackingStack` from the RIGHT branch; verify the LIVE
  resource after.

### Lessons Learned / Carry-Forward (from the 3.3 RD-038 rework, 2026-09-13)

- **The 🟡-rework pattern worked cleanly:** 3.3 was reworked in place on `feature/story-3.3`
  (reset to `main`), the RD-037 artifacts removed (`synthesize.py`/`synthesis.contract`/
  `gen_synthesis_contract`/`test_synthesize`) and the RD-038 ones added
  (`score.py`/`scoring.contract`/`gen_scoring_contract`), all offline-proven. Reuse the same
  "reset the feature branch to main, replace in place" flow if 3.4 ever gets re-scoped.
- **`scoring_result` shape 3.4 consumes** (RD-038, `scoring.contract.v1`): top-level
  `contract_version`/`intake_id`/`sha256`/`scored_at`/`rubric_version`/`combined_complete` +
  three score blocks **`static` / `dynamic` / `combined`**, each with `status`
  (`scored`/`model_error`/`unparseable`/`skipped_no_evidence`) and — only when `scored` — a
  0-100 `score` + `rationale` + model metadata (`model_id`/`attempts`/`latency_ms`/tokens).
  **3.4 must tolerate a PARTIAL result** (a score block may be `model_error` etc.) and rank
  honestly over whichever scores are present.
- **The three scores are COMPARABLE** (shared `rubric_version`), so ranking/thresholding
  across static/dynamic/combined is meaningful — a "70" means the same risk magnitude in any
  of them.
- **The candidate-FP + gap lists migrated to 3.4.** Build them from the 3.2
  `correlation_result` findings (each `kind` ∈ correlated/static_only/dynamic_only/
  contradiction): `static_only` → candidate false positive + `static_uncorroborated` gap;
  `dynamic_only` → `dynamic_unexplained` gap; `contradiction` → `contradiction` gap; plus a
  `coverage` gap when `combined_complete` is false. (The old 3.3 `synthesize.py` — now
  removed — had a reference implementation of this in git history at the PR #104 merge if
  you want to crib the exact mapping.)
- **RD-number + collision hygiene:** RD-038 is 3.3's. `grep -oE "RD-0[0-9][0-9]"
  PROJECT_PLAN.md | sort -u | tail` for the next FREE number (expect RD-039, but VERIFY —
  RD-036 was a real collision: it was taken by G-4 when 3.3 expected it).
- **The C.3 contract-gen + offline bar** (unchanged): new `scripts/gen_<name>_contract.py`
  (SCHEMA + OUT_PATHS + `main()` delegating to `contract_writer`), register in
  `gen_contracts.py`, `chmod +x`, prove `git diff -- schemas lambdas` clean. `ruff` DEFAULT
  rules bit twice in the 3.3 rework: **RUF046** (`int(round(x))` — drop the `int()`, `round()`
  returns int) and **RUF059** (unpacked-but-unused var — prefix `_`). `tsc` shows only the
  missing-`aws-cdk-lib` family; confirm no NEW error TYPE vs the `main` baseline.
- **User notes:** *(open for the stakeholder.)*

> **Sequencing note:** 3.4 (findings + prioritized remediations) is next by tier after 3.3 —
> but ONLY after 3.3 clears its live pass (advancement gate). It consumes 3.3's three scores
> + the migrated lists and feeds 3.5 (verdict derivation, which closes Phase 3).
