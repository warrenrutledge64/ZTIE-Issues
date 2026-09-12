# Session Brief — Story 3.4

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.

---

## Story 3.4 — Unified threat scoring + prioritized remediations

| Field | Value |
|-------|-------|
| **Phase** | P3 — Correlation & Synthesis |
| **Build tier** | 11 — **advances tier 10 → 11** (a new dependency layer opens: `3.3` at tier 10 goes ✅). This is a TIER move WITHIN Phase 3 (no phase transition). STEP 0 must re-confirm the whole tier-≤10 dependency set (`3.3` + its input `3.2`) is ✅ before starting. |
| **Date** | TBD (next session) |
| **Status** | ⬜ Not Started (build tier 11 — but see the ADVANCEMENT GATE below) |
| **Depends on** | **3.3 ✅** (the bounded, verdict-free `synthesis_result` — accuracy + gap_analysis — it scores over). |
| **Builds from restore point** | Branch the CODE off current `main` (which must contain merged + LIVE-VALIDATED 3.3 by the time 3.4 begins). |
| **Session goal** | Produce a single **unified threat SCORE** + detailed findings + **prioritized remediations** from the 3.3 synthesis (accuracy + gaps) for one `intake_id`, recorded as a bounded, verdict-free scoring result on the Hub tracking item. Still evidence-only — the enforcement VERDICT (PASS/FAIL/INCONCLUSIVE) is Story 3.5, downstream. |

---

### ⚠️ ADVANCEMENT GATE (read FIRST at STEP 0)

**3.4 is a NEW FEATURE story. It may begin ONLY if its Depends-on are ALL ✅ AND the
Validation Debt Register is EMPTY.** As of this brief's authoring, **Story 3.3 was BUILT
but sits 🟡 on the Validation Debt Register awaiting its recorded LIVE pass** (see
`story-3.3-LIVE-RUNBOOK.md`). So the gate is expected ARMED until 3.3 is validated live.
STEP 0 MUST re-confirm on `main`: `3.3` ✅, and the Validation Debt Register EMPTY (trust
`main` + `check_docs`; if they disagree, `main` wins). **If 3.3 is still 🟡, 3.4 MAY NOT
begin — the only permitted work is validating/reworking 3.3.** This is `check_docs`
CHECK B, machine-enforced.

---

### Background & Context

Phase 3 turns paired static + dynamic evidence into decision-ready synthesis. Story 3.1
(RD-033) normalized the per-lane outputs into ONE `combined_event`; Story 3.2 (RD-035)
correlated it with Amazon Nova Pro into a verdict-free `correlation_result`; **Story 3.3
(RD-037) synthesized that into a verdict-free `synthesis_result`** — an `accuracy` block
(candidate false positives + a descriptive reconciliation score + counts by correlation
kind) and a `gaps` block (static_uncorroborated / dynamic_unexplained / contradiction /
coverage gaps). **Story 3.4 is the scoring step:** roll the synthesis (and the
correlation severities it draws on) into ONE **unified threat score**, a detailed
findings view, and a **prioritized remediation** list the human gate + the Phase-4 report
consume. It feeds 3.5 (verdict derivation).

### What This Story Is (nature + gate role)

**Nature: NEW FEATURE story.** It may begin ONLY if its Depends-on are ALL ✅ **and** the
Validation Debt Register is empty (see the gate above — 3.3 must clear first). It consumes
3.3's `synthesis_result` (and may read the 3.2 `correlation_result` it references) and
produces the scoring 3.5 derives a verdict from.

### Objective & Value

- **Objective:** a single **unified threat SCORE** + detailed findings + **prioritized
  remediations** for one `intake_id`, recorded as a bounded, DERIVED, verdict-free scoring
  result on the Hub tracking item (contract-first, its own version pin — Hub-side, mirroring
  3.1/3.2/3.3's placement; decide + justify in the new RD).
- **Why it matters:** this is the single, at-a-glance risk read + the ranked "what to fix
  first" that the dashboard and the per-execution report (Phase 4) surface — the last
  synthesis output before the enforcement verdict.

### Scope, Dependencies & Position

- **In scope:** the unified-scoring logic (PURE + offline-testable — like 3.3, this is
  almost certainly PURE post-processing of the already-structured 3.3/3.2 evidence, NOT a
  model call; decide + justify in the RD); a scoring formula that combines the accuracy
  reconciliation + gap severities + correlation severities into ONE bounded score (define
  the scale explicitly — e.g. 0-100 EVIDENCE risk score, NOT a verdict); a detailed
  findings view; a **prioritized remediation** list (ranked by severity/impact); a
  contract-first scoring-result schema (bounded, allow-list, own version pin, verdict-free);
  where it lives (Hub-side — confirm); tests; a new RD + candidate control mappings (RD-014).
- **Out of scope / do NOT touch:** the enforcement VERDICT (PASS/FAIL/INCONCLUSIVE) — that
  is Story 3.5, human-gated; re-synthesizing (3.3 done); re-correlating / re-normalizing /
  re-capturing / re-sanitizing (3.2/3.1/2.4/2.5 done).
- **Depends on:** **3.3 ✅**. Plus an **empty Validation Debt Register**.
- **Unblocks:** 3.5 (verdict derivation — PASS / FAIL / INCONCLUSIVE, closes Phase 3).
- **Roadmap position:** the unified-scoring + remediation step of Phase 3.

### Approach & Constraints

- **Expected true-state (STEP 0 re-confirms; trust `main` + `check_docs`):** 3.3 ✅ (only
  after its live pass); Validation Debt Register EMPTY; advancement gate OPEN. Next free
  RD number: re-verify with `grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md | sort -u | tail`
  (RD-037 is 3.3's; **expect RD-038, but VERIFY — RD-number collisions have happened
  (RD-036 was taken by G-4 when 3.3 expected it), and RD-017 is a historical gap**).
- **Hard constraints:** SCORE, do not re-synthesize/re-correlate/re-normalize; the score
  + remediations are EVIDENCE (a risk read + a to-do list), **NEVER a verdict** (no
  verdict/safe/approved/forward/pass_fail/malicious/clean field; the scale is an evidence
  risk score, not a decision); keep the RD-009/RD-013 boundary intact (no raw data, no
  Forensic durable store); production code (if — unlikely — it calls Nova Pro, a REAL
  call with exponential-backoff retry, RD-003; but prefer PURE like 3.3); PURE logic +
  thin seams; docs first-class (RD-015), PR-reviewed.
- **Roles:** if a LIVE step is needed it is the **stakeholder's** action; the **executor
  RECORDS** verbatim. Do NOT simulate.

### Validation Rationale & Compliance Mapping (REQUIRED — RD-014)

- **Rationale:** one unified, reproducible risk score + a ranked remediation list over the
  verdict-free synthesis makes the assessment decision-ready + auditable while preserving
  the human gate (the score informs, it does not decide).
- **Candidate control mappings** *(proposed; ratified on review):*

| Framework | Control ID | Control Name | Rationale | Status |
|-----------|-----------|--------------|-----------|--------|
| NIST 800-53 r5 | RA-3 | Risk Assessment | Produces a unified risk score from correlated evidence | Proposed |
| NIST 800-53 r5 | RA-5 | Vulnerability Monitoring/Scanning | Prioritized remediations for the flagged findings | Proposed |
| NIST 800-53 r5 | SI-4 | System Monitoring | Scores synthesized monitoring evidence | Proposed |
| NIST CSF | ID.RA-5 | Threats, vulnerabilities, likelihoods used to determine risk | Unified scoring determines risk | Proposed |
| ISO 27001:2022 | A.8.8 | Management of technical vulnerabilities | Ranked remediations | Proposed |

### Management-Artifact Obligations (REQUIRED — RD-015)

- [ ] Story's brief + runbook entry updated (status, Validation Result, dates).
- [ ] PROJECT_PLAN and RUNBOOK in exact alignment (3.4 identical in both).
- [ ] New RD (scoring design) recorded; candidate mappings recorded.
- [ ] All doc changes PR-reviewed (branch + PR, never straight to main).
- [ ] `check_docs` fixture `_NEW_WORK_STORY` repointed off 3.4 (→ 3.5) IN THE SAME PR.
- [ ] Governance kept restorable alongside the code.
- [ ] On validation pass: record Validation Result + flip ✅ (paired commit).
- [ ] Author the next-story handoff (3.5 verdict derivation) with real Lessons Learned.

### Definition of Done / Validation Gate

> A pass/fail gate, not a description.

- **Done means:** for one `intake_id` with a `synthesis_result`, the scoring produces ONE
  bounded, verdict-free unified threat score + detailed findings + a prioritized
  remediation list validated against its schema and recorded on the tracking item; the
  RD-009/RD-013 boundary intact; validated live (if it touches the running pipeline) and
  recorded.
- **Validation Result:** `pending`.
- **On pass (and only then):** record the dated Validation Result, flip 3.4 ✅ (paired
  commit), clear 3.4 from the register, keep PLAN ↔ RUNBOOK aligned.
- **On fail:** 3.4 stays 🟡 (added to the Validation Debt Register in the same commit);
  fix + re-validate.

### Risks & Watch-Items

- **ADVANCEMENT GATE (highest priority):** 3.3 must be ✅ first (live-validated). Do not
  start 3.4 while 3.3 is 🟡 — that is exactly the drift `check_docs` CHECK B blocks.
- **Score is EVIDENCE, never a verdict** — define the scale as a risk/evidence score
  explicitly; no verdict/safe/forward field; the PASS/FAIL/INCONCLUSIVE decision is 3.5.
- **Prefer PURE post-processing (the 3.3 precedent).** 3.3 established that once the
  evidence is structured (correlation findings → synthesis accuracy/gaps), the downstream
  step is deterministic aggregation, not a model call. Score the same way unless there is
  a concrete reason to invoke the model — and if you do, justify it in the RD and make it
  a REAL call with exponential-backoff retry (RD-003).
- **If it hangs off the tracking-table stream:** reuse the 3.1/3.2/3.3 idempotency +
  call-storm guard (a content fingerprint over the input — the `synthesis_result` —
  `Decimal`-canonicalized) so it fires once per settled synthesis, not on every mutation.
- **Deploy-gap (both modes):** any Lambda change only takes effect after `cdk deploy`;
  redeploy the RIGHT stack (`ZtieHubTrackingStack`) from the RIGHT branch and verify the
  LIVE resource after.

### Lessons Learned / Carry-Forward (from the 3.3 build session, 2026-09-12)

- **The lane/derived pattern held an 8th time (1.2→2.2→2.3→2.4→2.5→3.1→3.2→3.3):**
  contract-first + a bounded allow-list schema with its OWN version pin + PURE logic
  (`synthesize.py`) + a thin `awsio` seam + evidence-never-verdict + a two-layer
  conformance test (stdlib walk + jsonschema `skipUnless` live layer) + a recursive
  no-verdict-key scan + a schema-has-no-verdict-property check. **Reuse it for 3.4's
  scoring-result record.**
- **3.3 was PURE Hub-side post-processing (RD-037), NOT a second model call.** Its input
  (the `correlation_result`) already carried the model's DISCRETE structured findings, so
  accuracy + gap_analysis were deterministic aggregations over the finding `kind` enum. A
  second Nova Pro call was rejected (cost / non-determinism / verdict-injection risk / not
  reproducible) and the synthesizer Lambda has **NO Bedrock client + NO Bedrock grant**.
  3.4's input (the `synthesis_result`) is likewise fully structured Hub-side data — the
  SAME "prefer PURE" reasoning very likely applies. Decide + justify in the RD.
- **RD-number collision is REAL — re-verify at STEP 0.** 3.3's brief said "expect RD-036"
  but RD-036 had ALREADY been taken by G-4 (the charter story), so 3.3 used **RD-037**.
  ALWAYS `grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md | sort -u | tail` on CURRENT main and
  take the next genuinely-free number (expect RD-038 for 3.4, but CONFIRM).
- **The C.3 contract-gen workflow:** add a NEW `scripts/gen_<name>_contract.py` with a
  `SCHEMA` dict + a module-level `OUT_PATHS` list of segment tuples + a `main()` that does
  `from contract_writer import resolve_out_paths, write_contract; write_contract(SCHEMA,
  resolve_out_paths(OUT_PATHS))`, register the module in `gen_contracts.py`'s
  `CONTRACT_MODULES`, and **`chmod +x` the new generator** (ruff EXE001 fires on a
  shebang'd non-executable). Prove no-drift with `git diff -- schemas lambdas` after
  regenerating; confirm the two copies are byte-identical.
- **`synthesis_result` shape 3.4 consumes** (RD-037, `synthesis.contract.v1`): top-level
  `contract_version`/`intake_id`/`sha256`/`synthesized_at`/`status`
  (`synthesized`/`no_correlation`/`skipped_no_findings`) + optional `status_detail`/
  `correlation_status`/`correlation_contract_version`/`source_finding_count`/
  `combined_complete`/`truncated`; and — only when `status: synthesized` — a `synthesis`
  object: `summary`, `accuracy` (`accuracy_score` 0-100, `confirmed_correlation_count`,
  `candidate_false_positive_count`, `static_only_count`/`dynamic_only_count`/
  `contradiction_count`, `candidate_false_positives[]`), and `gaps` (`gap_count`,
  `highest_gap_severity`, `items[]` each `gap_type` ∈ static_uncorroborated/
  dynamic_unexplained/contradiction/coverage + `severity`/`title`/refs). It is on the
  tracking item as `synthesis_result` (+ flattened `synthesis_status`). **3.4 must
  tolerate `status != synthesized`** (score honestly over an absent/errored synthesis —
  record it, never fabricate).
- **`check_docs` self-test fixture drift:** `scripts/test_check_docs.py` pins
  `_NEW_WORK_STORY` to a downstream ⬜ story; when 3.3 went 🟡 it was repointed 3.3 → **3.4**.
  **When 3.4 leaves ⬜ (this story starts/finishes), repoint `_NEW_WORK_STORY` to the next
  still-⬜ feature story (3.5) IN THE SAME PR** and re-run `python3 -m unittest
  scripts.test_check_docs` (read the SUITE result line `OK` vs `FAILED (failures=N)` — the
  `check_docs: FAIL …` lines it prints while exercising itself are expected, not failures).
- **`check_docs` timing:** run `python3 scripts/check_docs.py` only AFTER committing any
  status/register edit (CHECK B's baseline is `git show HEAD:RUNBOOK.md`). Set 3.4 🟡 AND
  add it to the Validation Debt Register in the SAME commit.
- **Offline proof bar (INTEGRATIONS_ONLY sandbox):** the repo's default `python3` is 3.9;
  run your tests with `~/.pyenv/versions/3.12.13/bin/python3`. `ruff` at
  `~/.pyenv/versions/3.12.13/bin/ruff` (repo has NO ruff config → DEFAULT rules; watch
  RUF100 = a `# noqa` for a rule that is not enabled — do NOT add `# noqa: E402`; and
  ISC004 = implicit string concatenation inside a list/collection needs wrapping
  parentheses — both bit the 3.3 build). `prettier`/`tsc` are the global nvm ones
  (`env -u NODE_OPTIONS`); npm is BLOCKED so `tsc --noEmit` shows ONLY the missing-
  `aws-cdk-lib` family (TS2304/2307/2339/2353/2591) — confirm your new stack code adds NO
  NEW error TYPE (compare the error-TYPE set against `main`'s baseline; a count delta in
  an existing type is fine). Do NOT prettier-reformat the generated JSON contracts (breaks
  no-drift). Keep your own tests stdlib-only + boto3-stubbed so they pass offline.
- **User notes:** *(open for the stakeholder to add anything before the 3.4 session.)*

> **Sequencing note:** 3.4 (unified threat scoring + prioritized remediations) is the next
> by tier after 3.3 — but ONLY after 3.3 clears its live pass (advancement gate). It scores
> over 3.3's one verdict-free synthesis result and feeds 3.5 (verdict derivation, which
> closes Phase 3).
