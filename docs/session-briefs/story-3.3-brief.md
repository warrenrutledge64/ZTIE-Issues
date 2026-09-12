# Session Brief — Story 3.3

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.

---

## Story 3.3 — accuracy + gap_analysis synthesis

| Field | Value |
|-------|-------|
| **Phase** | P3 — Correlation & Synthesis |
| **Build tier** | 10 — **advances tier 9 → 10** (a new dependency layer opens: `3.2` at tier 9 goes ✅). This is a TIER move WITHIN Phase 3 (no phase transition). STEP 0 must re-confirm the whole tier-≤9 dependency set (`3.2` + its inputs `3.1` + `2.5`) is ✅ before starting. |
| **Date** | TBD (next session) |
| **Status** | ⬜ Not Started (build tier 10 — but see the ADVANCEMENT GATE below) |
| **Depends on** | **3.2 ✅** (the bounded, verdict-free Nova Pro `correlation_result` it synthesizes over). |
| **Builds from restore point** | Branch the CODE off current `main` (which must contain merged + LIVE-VALIDATED 3.2 by the time 3.3 begins). |
| **Session goal** | Run the `accuracy` and `gap_analysis` synthesis over the 3.2 `correlation_result` to (a) score the correlation's accuracy / eliminate false positives and (b) surface static↔dynamic gaps, recording a bounded, verdict-free synthesis result on the Hub tracking item. Still evidence-only — the verdict is Phase 4. |

---

### ⚠️ ADVANCEMENT GATE (read FIRST at STEP 0)

**3.3 is a NEW FEATURE story. It may begin ONLY if its Depends-on are ALL ✅ AND the
Validation Debt Register is EMPTY.** As of this brief's authoring, **Story 3.2 was BUILT
but sits 🟡 on the Validation Debt Register awaiting its recorded LIVE Nova Pro pass**
(see `story-3.2-LIVE-RUNBOOK.md`). So the gate is expected ARMED until 3.2 is validated
live. STEP 0 MUST re-confirm on `main`: `3.2` ✅, and the Validation Debt Register EMPTY
(trust `main` + `check_docs`; if they disagree, `main` wins). **If 3.2 is still 🟡, 3.3
MAY NOT begin — the only permitted work is validating/reworking 3.2.** This is
`check_docs` CHECK B, machine-enforced.

---

### Background & Context

Phase 3 turns paired static + dynamic evidence into decision-ready synthesis. Story 3.1
(RD-033) normalized the per-lane derived outputs into ONE `combined_event`. **Story 3.2
(RD-035) correlated that combined event with Amazon Nova Pro** into a bounded,
verdict-free `correlation_result` (a narrative summary + `findings[]`, each tying a
static observation to a dynamic behavioral indicator, or noting a static-only /
dynamic-only / contradiction observation, with a descriptive severity roll-up). **Story
3.3 is the synthesis step:** the `accuracy` program scores how well the correlation
eliminates false positives (a static flag that dynamic evidence shows was never
exercised is a candidate false positive), and the `gap_analysis` program surfaces where
the two lanes disagree or leave a gap. It feeds 3.4 (unified threat scoring +
remediations).

### What This Story Is (nature + gate role)

**Nature: NEW FEATURE story.** It may begin ONLY if its Depends-on are ALL ✅ **and** the
Validation Debt Register is empty (see the gate above — 3.2 must clear first). It consumes
3.2's `correlation_result` and produces the synthesis 3.4 scores over.

### Objective & Value

- **Objective:** the `accuracy` + `gap_analysis` synthesis over the 3.2
  `correlation_result` for one `intake_id`, recorded as a bounded, DERIVED, verdict-free
  synthesis result on the Hub tracking item (contract-first, its own version pin —
  decide Hub-side vs. a new derivation and justify in the RD, mirroring 3.1/3.2's
  placement reasoning). Decide whether this is a SECOND Nova Pro call (a synthesis prompt
  over the correlation) or PURE post-processing of the 3.2 findings — and justify it.
- **Why it matters:** this is where a static-only false positive is formally reconciled
  against benign dynamic evidence (the false-positive elimination RD-003 promises) and
  where genuine coverage gaps are surfaced for the human gate.

### Scope, Dependencies & Position

- **In scope:** the `accuracy` + `gap_analysis` synthesis logic (PURE + offline-testable);
  if it uses Nova Pro, a bounded synthesis prompt (evidence-in / synthesis-out, NO
  verdict ask) behind the thin `awsio` seam with exponential-backoff retry; a
  contract-first synthesis result schema (bounded, allow-list, own version pin,
  verdict-free); where it lives (likely Hub-side, since the correlation result is on the
  Hub tracking record — confirm); tests; a new RD + candidate control mappings (RD-014).
- **Out of scope / do NOT touch:** any verdict (Phase 4 / human-gated); re-correlating
  (3.2 done); re-normalizing / re-capturing / re-sanitizing (3.1/2.4/2.5 done); the
  unified threat SCORE (that is 3.4).
- **Depends on:** **3.2 ✅**. Plus an **empty Validation Debt Register**.
- **Unblocks:** 3.4 (unified threat scoring + prioritized remediations).
- **Roadmap position:** the false-positive-elimination + gap step of Phase 3.

### Approach & Constraints

- **Expected true-state (STEP 0 re-confirms; trust `main` + `check_docs`):** 3.2 ✅ (only
  after its live pass); Validation Debt Register EMPTY; advancement gate OPEN. Next free
  RD number: re-verify with `grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md | sort -u | tail`
  (RD-035 is 3.2's; expect RD-036, but VERIFY — collisions have happened, and RD-017 is
  a historical gap).
- **Hard constraints:** synthesize, do not re-correlate/re-normalize/re-capture; output
  is EVIDENCE (a synthesis), never a verdict; keep the RD-009/RD-013 boundary intact (no
  raw data, no Forensic durable store); production code (if it calls Nova Pro, a REAL
  call — no mock model, per production-code-at-all-times) with exponential-backoff retry
  (RD-003); PURE logic + thin seams; docs first-class (RD-015), PR-reviewed.
- **Roles:** if a LIVE step is needed it is the **stakeholder's** action; the **executor
  RECORDS** verbatim. Do NOT simulate.

### Validation Rationale & Compliance Mapping (REQUIRED — RD-014)

- **Rationale:** false-positive elimination + gap analysis over a single verdict-free
  correlation record makes the AI synthesis reproducible + auditable and preserves the
  human gate.
- **Candidate control mappings** *(proposed; ratified on review):*

| Framework | Control ID | Control Name | Rationale | Status |
|-----------|-----------|--------------|-----------|--------|
| NIST 800-53 r5 | RA-5 | Vulnerability Monitoring/Scanning | Reconciles findings, eliminates false positives | Proposed |
| NIST 800-53 r5 | SI-4 | System Monitoring | Synthesizes monitored correlation evidence | Proposed |
| NIST CSF | DE.AE-2 | Detected events are analyzed | Synthesis analyzes the correlated events | Proposed |
| ISO 27001:2022 | A.8.16 | Monitoring activities | Analyzes consolidated correlation | Proposed |

### Management-Artifact Obligations (REQUIRED — RD-015)

- [ ] Story's brief + runbook entry updated (status, Validation Result, dates).
- [ ] PROJECT_PLAN and RUNBOOK in exact alignment (3.3 identical in both).
- [ ] New RD (synthesis design) recorded; candidate mappings recorded.
- [ ] All doc changes PR-reviewed (branch + PR, never straight to main).
- [ ] `check_docs` fixture `_NEW_WORK_STORY` repointed off 3.3 (→ 3.4) IN THE SAME PR.
- [ ] Governance kept restorable alongside the code.
- [ ] On validation pass: record Validation Result + flip ✅ (paired commit).
- [ ] Author the next-story handoff (3.4 unified scoring) with real Lessons Learned.

### Definition of Done / Validation Gate

> A pass/fail gate, not a description.

- **Done means:** for one `intake_id` with a `correlation_result`, the accuracy +
  gap_analysis synthesis produces a bounded, verdict-free synthesis result validated
  against its schema and recorded on the tracking item; a static-only false positive is
  demonstrably reconciled against benign dynamic evidence; the RD-009/RD-013 boundary
  intact; validated live (if it touches the running pipeline / makes a real Bedrock call)
  and recorded.
- **Validation Result:** `pending`.
- **On pass (and only then):** record the dated Validation Result, flip 3.3 ✅ (paired
  commit), clear 3.3 from the register, keep PLAN ↔ RUNBOOK aligned.
- **On fail:** 3.3 stays 🟡 (added to the Validation Debt Register in the same commit);
  fix + re-validate.

### Risks & Watch-Items

- **ADVANCEMENT GATE (highest priority):** 3.2 must be ✅ first (live-validated). Do not
  start 3.3 while 3.2 is 🟡 — that is exactly the drift `check_docs` CHECK B blocks.
- **Evidence, never a verdict** — the synthesis result has no verdict/safe/forward field;
  if it calls Nova Pro, the prompt must not ask for a verdict.
- **If it hangs off the tracking-table stream:** reuse the 3.1/3.2 idempotency +
  call-storm guard (a content fingerprint over the input, `Decimal`-canonicalized) so it
  fires once per settled correlation, not on every mutation.
- **Deploy-gap (both modes):** any Lambda change only takes effect after `cdk deploy`;
  redeploy the RIGHT stack from the RIGHT branch and verify the LIVE resource after.

### Lessons Learned / Carry-Forward (from the 3.2 build session, 2026-09-12)

- **The lane/derived pattern held a 7th time (1.2→2.2→2.3→2.4→2.5→3.1→3.2):** contract-first
  + a bounded allow-list schema with its OWN version pin + PURE logic (`correlate.py`) + a
  thin `awsio` seam + evidence-never-verdict + a two-layer conformance test (stdlib walk +
  jsonschema `skipUnless` live layer) + a recursive no-verdict-key scan + a
  schema-has-no-verdict-property check. **Reuse it for 3.3's synthesis-result record.**
- **3.2 was a HUB-SIDE derivation (RD-035), NOT a new RD-013 crossing** — its input (the
  `combined_event`) already sat Hub-side, so it read the item → invoked Nova Pro → wrote
  the `correlation_result` back (integrity-bound, never touches `status`). 3.3's input
  (the `correlation_result`) is likewise already Hub-side; the SAME placement reasoning
  very likely applies. Decide + justify in the RD.
- **The C.3 contract-gen workflow:** add a NEW `scripts/gen_<name>_contract.py` with a
  `SCHEMA` dict + a module-level `OUT_PATHS` list of segment tuples + a `main()` that does
  `from contract_writer import resolve_out_paths, write_contract; write_contract(SCHEMA,
  resolve_out_paths(OUT_PATHS))`, then register the module in `gen_contracts.py`'s
  `CONTRACT_MODULES`. **`chmod +x` the new generator** (the others are executable; ruff's
  EXE001 fires on a shebang'd non-executable file). Prove no-drift with `git diff --
  schemas lambdas` after regenerating (and confirm the two copies are byte-identical).
- **`correlation_result` shape 3.3 consumes** (RD-035, `correlation.contract.v1`): top-level
  `contract_version`/`intake_id`/`sha256`/`correlated_at`/`status`
  (`correlated`/`model_error`/`unparseable`/`skipped_no_signals`) + `model_id`/`attempts`/
  `latency_ms`/`input_tokens`/`output_tokens`/`truncated`/`combined_complete`; and — only
  when `status: correlated` — a `correlation` object (`summary`, `finding_count`,
  `highest_correlation_severity`, `findings[]` where each finding has
  `kind`∈correlated/static_only/dynamic_only/contradiction, `severity`, `title`, optional
  `detail`/`static_refs`/`behavioral_refs`). It is on the tracking item as
  `correlation_result` (+ flattened `correlation_status` + a Hub-internal
  `combined_event_fingerprint`). **3.3 must tolerate `status != correlated`** (synthesize
  honestly over an absent/errored correlation — record it, never fabricate).
- **Nova Pro is a REAL call — design for non-determinism + throttling.** If 3.3 calls the
  model: parse the response DEFENSIVELY into the bounded schema; a malformed/absent
  response is RECORDED via a `status`, never fabricated; the prompt must NOT ask for a
  verdict; use the `awsio.invoke_nova` pattern (real exponential-backoff + full jitter,
  bounded `max_attempts`, returns the attempt count so the retry is inspectable). Nova Pro
  on-demand is reached via the region-prefixed inference profile `us.amazon.nova-pro-v1:0`
  (make it env-configurable); the `bedrock:InvokeModel` grant must be scoped to EXACTLY
  the Nova Pro model/profile ARNs (never `*`), and **Bedrock model access must be enabled
  for the Hub account** or the first live call fails `AccessDeniedException` (STEP 0 of the
  LIVE-RUNBOOK checks this).
- **`check_docs` self-test fixture drift:** `scripts/test_check_docs.py` pins
  `_NEW_WORK_STORY` to a downstream ⬜ story; when 3.2 went 🟡 it was repointed 3.2 → **3.3**.
  **When 3.3 leaves ⬜ (this story starts/finishes), repoint `_NEW_WORK_STORY` to the next
  still-⬜ feature story (3.4) IN THE SAME PR** and re-run `python3 -m unittest
  scripts.test_check_docs` (read the SUITE result line `OK` vs `FAILED (failures=N)` — the
  `check_docs: FAIL …` lines it prints while exercising itself are expected, not failures).
- **`check_docs` timing:** run `python3 scripts/check_docs.py` only AFTER committing any
  status/register edit (CHECK B's baseline is `git show HEAD:RUNBOOK.md`). Set 3.3 🟡 AND
  add it to the Validation Debt Register in the SAME commit (CHECK A requires every 🟡
  feature story to be on the register; CHECK B allows a story that is IN the register).
- **Offline proof bar (INTEGRATIONS_ONLY sandbox):** the repo's default `python3` is 3.9;
  run your tests with `~/.pyenv/versions/3.12.13/bin/python3` (matches the Lambda runtime).
  `ruff` at `~/.pyenv/versions/3.12.13/bin/ruff` (repo has NO ruff config → DEFAULT rules;
  it flags `BLE001` on a blind `except Exception` that does NOT re-raise — the honest
  record-then-continue catch legitimately needs a `# noqa: BLE001`; a blind catch that
  re-raises is fine). `prettier`/`tsc` are the global nvm ones (`env -u NODE_OPTIONS`);
  npm registry is BLOCKED so `node_modules` is absent and `tsc --noEmit` shows ONLY the
  missing-`aws-cdk-lib` family (TS2304/2307/2339/2353/2591) — confirm your new stack code
  adds NO NEW error type. Do NOT prettier-reformat the generated JSON contracts (that
  breaks the no-drift check — leave them as `json.dump(indent=2)` output; the existing
  committed contracts also "fail" the global prettier default, which is not the repo's
  bar). jsonschema/moto/boto3 not installable — prove contracts with the stdlib
  conformance walk + a jsonschema-`skipUnless` layer, and stub boto3 + botocore (`Config`,
  `ClientError`) in `sys.modules` for the handler/seam tests.
- **Retry-loop test trap (found live in 3.2 build):** when unit-testing the backoff loop
  with a fake Bedrock client that raises `ClientError`, set the HTTP status to match the
  error class — a `ValidationException` must carry a 4xx (400), not 429, or the
  retryability heuristic (429/5xx = retryable) will (correctly) retry it and the
  "non-retryable is not retried" assertion fails. That was a test bug, not a code bug.
- **User notes:** *(open for the stakeholder to add anything before the 3.3 session.)*

> **Sequencing note:** 3.3 (accuracy + gap_analysis synthesis) is the next by tier after
> 3.2 — but ONLY after 3.2 clears its live pass (advancement gate). It synthesizes over
> 3.2's one verdict-free correlation result and feeds 3.4 (unified threat scoring).
