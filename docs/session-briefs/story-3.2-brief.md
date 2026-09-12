# Session Brief — Story 3.2

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.

---

## Story 3.2 — Nova Pro correlation engine (exponential-backoff retry)

| Field | Value |
|-------|-------|
| **Phase** | P3 — Correlation & Synthesis |
| **Build tier** | 7 — **advances tier 6 → 7** (a new dependency layer opens: `3.1` at tier 6 goes ✅). This is a TIER move WITHIN Phase 3 (no phase transition — 3.1 already made the P2 → P3 move). STEP 0 must re-confirm the whole tier-≤6 dependency set (`3.1` + its input `2.5`) is ✅ before starting. |
| **Date** | TBD (next session) |
| **Status** | ⬜ Not Started (build tier 7 — but see the ADVANCEMENT GATE below) |
| **Depends on** | **3.1 ✅** (the shared normalized combined-event record it reasons over) + **2.5 ✅** (the sanitized behavioral telemetry that feeds 3.1's combined event). |
| **Builds from restore point** | Branch the CODE off current `main` (which must contain merged + LIVE-VALIDATED 3.1 by the time 3.2 begins). |
| **Session goal** | Pass the ONE normalized combined-event record (RD-033, `combined-event.contract.v1`) for an `intake_id` to Amazon Nova Pro; correlate the static misconfigurations with the dynamic behavioral indicators; return a bounded, verdict-free correlation result with exponential-backoff retry on Bedrock throttling. |

---

### ⚠️ ADVANCEMENT GATE (read FIRST at STEP 0)

**Story 3.1 was validated live 2026-09-12 (intake `a7f21334-…`) and flipped ✅, which
CLEARED the Validation Debt Register — so the gate is expected OPEN for 3.2.** STEP 0 MUST
still RE-CONFIRM on `main` that 3.1 is ✅, 2.5 is ✅, and the register is EMPTY before
touching anything (trust `main` + `check_docs`; if they disagree, `main` wins). If the
register is non-empty for ANY reason, 3.2 MAY NOT begin — the only permitted work is
clearing that open entry. This is `check_docs` CHECK B, machine-enforced.

> Note (carry into 3.2): 3.1's live run surfaced a **stream-loop** bug — its idempotency
> compare treated DynamoDB's `Decimal` number round-trip as ≠ the freshly-built plain
> `int`, so it re-wrote forever. If 3.2 also hangs off the tracking-table stream with an
> idempotent write, reuse `hub_normalize/handler.py::_canonical()` to canonicalize the
> `Decimal` gap BEFORE comparing, and make the fake seam round-trip through `Decimal` in
> tests (the offline test missed it precisely because it stored plain ints).

---

### Background & Context

ZTIE is a four-phase AWS-native security pipeline; work is validation-gated (nothing is
✅ until a recorded live pass — the covenant). Phase 2 produced, for one artifact, the
per-lane derived records on the Hub tracking item (static-scan summary, dynamic-run
outcome, behavioral summary, sanitized telemetry). **Story 3.1 (RD-033) normalized those
into ONE shared, verdict-free `combined_event`** on the Hub tracking record — a per-input
`sources` block, a normalized `signals` block (worst static severity + dynamic outcome +
the sanitized behavioral events), and `inputs_present`/`complete` completeness facts.
**Story 3.2 is the correlation step: it hands that ONE combined event to Amazon Nova Pro
(RD-003) and gets back a correlation result** — static misconfigurations reconciled
against dynamic behavioral indicators — still verdict-free (the verdict is Phase 4).

### What This Story Is (nature + gate role)

**Nature: NEW FEATURE story.** It may begin ONLY if its Depends-on are ALL ✅ **and** the
Validation Debt Register is empty (see the gate above — 3.1 must clear first). It consumes
3.1's combined event and produces the correlation 3.3 (accuracy + gap_analysis) refines.

### Objective & Value

- **Objective:** a Bedrock Nova Pro (RD-003) correlation call over the `combined_event`
  for one `intake_id`, with **exponential-backoff retry** on throttling/5xx, returning a
  bounded, DERIVED, verdict-free correlation result recorded on the Hub tracking item
  (contract-first, its own version pin — decide Hub-side vs. a new derivation and justify
  in the RD, mirroring 3.1's placement reasoning).
- **Why it matters:** correlation is where a static-only false positive gets reconciled
  against benign dynamic evidence (and vice-versa). It is the AI step RD-003 promises.

### Scope, Dependencies & Position

- **In scope:** the Nova Pro prompt (a `prompts/` Markdown template — bounded, evidence-in
  / correlation-out, NO verdict ask); the Bedrock call behind a thin `awsio` seam with
  exponential-backoff retry (`bedrock-runtime`, us-east-1); a contract-first correlation
  result schema (bounded, allow-list, own version pin, verdict-free); where it lives
  (likely Hub-side, since the combined event is on the Hub tracking record — confirm);
  tests; a new RD + candidate control mappings (RD-014).
- **Out of scope / do NOT touch:** any verdict (Phase 4 / human-gated); re-aggregating or
  re-normalizing (3.1 done); re-capturing/re-sanitizing telemetry (2.4/2.5 done); the
  accuracy + gap_analysis synthesis (that is 3.3).
- **Depends on:** **3.1 ✅** + **2.5 ✅**. Plus an **empty Validation Debt Register**.
- **Unblocks:** 3.3 (accuracy + gap_analysis synthesis over the correlation).
- **Roadmap position:** the AI-correlation core of Phase 3.

### Approach & Constraints

- **Expected true-state (STEP 0 re-confirms; trust `main` + `check_docs`):** 3.1 ✅ (only
  after its live pass); Validation Debt Register EMPTY; advancement gate OPEN. Next free
  RD number: re-verify with `grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md | sort -u | tail`
  (RD-033 is 3.1's; expect RD-034, but VERIFY — collisions have happened, and RD-017 is
  a historical gap).
- **Hard constraints:** correlate, do not re-capture/re-normalize; output is EVIDENCE
  (a correlation), never a verdict; keep the RD-009/RD-013 boundary intact (no raw data,
  no Forensic durable store); production code (a REAL Bedrock call — no mock model, per
  the production-code-at-all-times rule) with exponential-backoff retry (RD-003); PURE
  logic + thin seams; docs first-class (RD-015), PR-reviewed.
- **Bedrock reality:** Nova Pro is invoked via `bedrock-runtime`; the Forensic infra (2.0)
  and Hub both may reach Bedrock. Decide WHERE the call runs (Hub-side over the combined
  event is the natural fit); the model is non-deterministic, so the correlation RESULT
  schema must be bounded + validated + the code must tolerate a malformed/absent model
  response (record it, never fabricate — the same honesty discipline as 3.1's absent
  inputs). NEVER let a model response assert a verdict.
- **Roles:** if a LIVE step is needed it is the **stakeholder's** action; the **executor
  RECORDS** verbatim. Do NOT simulate. A REAL Nova Pro invocation is the live proof.

### Validation Rationale & Compliance Mapping (REQUIRED — RD-014)

- **Rationale:** cross-lane correlation is what eliminates false positives; doing it over
  a single normalized record (3.1) makes the AI reasoning reproducible and auditable, and
  keeping the correlation verdict-free preserves the human gate.
- **Candidate control mappings** *(proposed; ratified on review):*

| Framework | Control ID | Control Name | Rationale | Status |
|-----------|-----------|--------------|-----------|--------|
| NIST 800-53 r5 | SI-4 | System Monitoring | Correlates monitored static + dynamic evidence | Proposed |
| NIST 800-53 r5 | RA-5 | Vulnerability Monitoring/Scanning | Reconciles findings to reduce false positives | Proposed |
| NIST CSF | DE.AE-2 | Detected events are analyzed | Nova Pro analyzes the aggregated event | Proposed |
| ISO 27001:2022 | A.8.16 | Monitoring activities | Analyzes consolidated behavior | Proposed |

### Management-Artifact Obligations (REQUIRED — RD-015)

- [ ] Story's brief + runbook entry updated (status, Validation Result, dates).
- [ ] PROJECT_PLAN and RUNBOOK in exact alignment (3.2 identical in both).
- [ ] New RD (Nova Pro correlation design) recorded; candidate mappings recorded.
- [ ] All doc changes PR-reviewed (branch + PR, never straight to main).
- [ ] `check_docs` fixture `_NEW_WORK_STORY` repointed off 3.2 (→ 3.3) IN THE SAME PR.
- [ ] Governance kept restorable alongside the code.
- [ ] On validation pass: record Validation Result + flip ✅ (paired commit).
- [ ] Author the next-story handoff (3.3 accuracy + gap_analysis) with real Lessons Learned.

### Definition of Done / Validation Gate

> A pass/fail gate, not a description.

- **Done means:** for one `intake_id` with a `combined_event`, a REAL Nova Pro invocation
  returns a bounded, verdict-free correlation result that is validated against its schema
  and recorded on the tracking item; exponential-backoff retry is exercised/inspectable;
  the RD-009/RD-013 boundary intact; validated live (it touches the running pipeline +
  makes a real Bedrock call) and recorded.
- **Validation Result:** `pending`.
- **On pass (and only then):** record the dated Validation Result, flip 3.2 ✅ (paired
  commit), clear 3.2 from the register, keep PLAN ↔ RUNBOOK aligned.
- **On fail:** 3.2 stays 🟡 (added to the Validation Debt Register in the same commit);
  fix + re-validate.

### Risks & Watch-Items

- **ADVANCEMENT GATE (highest priority):** 3.1 must be ✅ first (live-validated). Do not
  start 3.2 while 3.1 is 🟡 — that is exactly the drift `check_docs` CHECK B blocks.
- **Non-deterministic model output:** the correlation result schema must be bounded +
  allow-list; parse the model response defensively and RECORD a malformed/absent response
  honestly (never fabricate a correlation, never let the model assert a verdict).
- **Bedrock throttling:** RD-003 requires exponential-backoff retry — make it real and
  inspectable, not a single call.
- **Evidence, never a verdict** — the correlation result has no verdict/safe/forward field.
- **Deploy-gap (both modes):** any Lambda change only takes effect after `cdk deploy`;
  redeploy the RIGHT stack from the RIGHT branch and verify the LIVE resource after (see
  the 3.1 lessons below).

### Lessons Learned / Carry-Forward (from the 3.1 build session, 2026-09-11)

- **The lane/derived pattern held a 6th time (1.2→2.2→2.3→2.4→2.5→3.1):** contract-first +
  a bounded allow-list schema with its OWN version pin + PURE logic (`combine.py`) + a thin
  `awsio` seam + evidence-never-verdict + a two-layer conformance test (stdlib walk +
  jsonschema `skipUnless` live layer) + a recursive no-verdict-key scan + a
  schema-has-no-verdict-property check. **Reuse it for 3.2's correlation-result record.**
- **3.1 was a HUB-SIDE derivation, NOT a new RD-013 crossing** (RD-033): its inputs already
  sat on the Hub tracking item, so it read the item → built the record → wrote it back,
  triggered by the tracking-table **DynamoDB stream**, with an **idempotent** write (only
  writes when the derived record actually changed, so its own write does not loop the
  stream). 3.2's combined-event input is likewise already Hub-side — the SAME Hub-side
  placement reasoning very likely applies; decide + justify in the RD. If 3.2 also hangs
  off the stream, remember the loop-guard.
- **`combined_event` shape 3.2 consumes** (RD-033, `combined-event.contract.v1`): top-level
  `contract_version`/`intake_id`/`sha256`/`combined_at`/`combined_event`; inside,
  `inputs_present` (subset of static/dynamic/sanitized), `complete` (all three present —
  an AGGREGATION fact, NOT a verdict), `sources.{static,dynamic,sanitized}` (each with
  `presence` + bounded roll-up + Forensic pointer), and `signals` (`static_highest_severity`,
  `dynamic_outcome`, `behavioral_events[]` with RELATIVE `offset_ms`, `behavioral_event_count`).
  It is on the tracking item as `combined_event` (+ flattened `combined_complete`). 3.2
  should tolerate `complete: false` (correlate what is present, honestly).
- **`check_docs` self-test fixture drift:** `scripts/test_check_docs.py` pins
  `_NEW_WORK_STORY` to a downstream ⬜ story; when 3.1 went 🟡 it was repointed 3.1 → **3.2**.
  **When 3.2 leaves ⬜ (this story starts/finishes), repoint `_NEW_WORK_STORY` to the next
  still-⬜ feature story (3.3) IN THE SAME PR** and re-run `python3 -m unittest
  scripts.test_check_docs` (read the SUITE result line `OK` vs `FAILED (failures=N)` — the
  `check_docs: FAIL …` lines it prints while exercising itself are expected, not failures).
- **`check_docs` timing:** run `python3 scripts/check_docs.py` only AFTER committing any
  status/register edit (CHECK B's baseline is `git show HEAD:RUNBOOK.md`). It PASSED for
  3.1 with 3.1 in the register.
- **Offline proof bar (INTEGRATIONS_ONLY sandbox):** `ruff` at
  `~/.pyenv/versions/3.12.13/bin/ruff`; `prettier`/`npx tsc` need `env -u NODE_OPTIONS`;
  `tsc --noEmit` legitimately shows ONLY the missing-`aws-cdk-lib` family (TS2304/2307/
  2339/2353/2591) — confirm NO NEW error type. jsonschema/moto/boto3 not installable — prove
  contracts with a stdlib conformance walk + a jsonschema-`skipUnless` layer, and stub
  boto3 (and boto3's `bedrock-runtime` for 3.2) in `sys.modules` for the handler tests.
  NOTE: the repo's default `python3` is 3.9; existing moto-based `test_handler.py` in
  `hub_ingest`/`intake` FAIL to import offline (boto3 absent) — that is pre-existing, not
  your regression. Keep your own tests stdlib-only + stubbed so they pass offline.
- **Deploy-gap (both silent modes):** (1) stack not redeployed → old code still live; (2)
  redeployed from the WRONG git checkout → green `UPDATE_COMPLETE` ships STALE code. GUARD:
  before deploy, confirm `git rev-parse --abbrev-ref HEAD` + `grep` the new marker in the
  stack/lambda source; after deploy, inspect the LIVE resource
  (`aws lambda get-function-configuration … Environment.Variables`). Also verify deploy-time
  `-c` context values come from the RIGHT stack's outputs (a wrong ARN can deploy green and
  fail at runtime). Bake both into the 3.2 LIVE-RUNBOOK.
- **User notes:** *(open for the stakeholder to add anything before the 3.2 session.)*

> **Sequencing note:** 3.2 (Nova Pro correlation) is the next by tier after 3.1 — but ONLY
> after 3.1 clears its live pass (advancement gate). It reasons over 3.1's one normalized
> combined event and feeds 3.3 (accuracy + gap_analysis synthesis).
