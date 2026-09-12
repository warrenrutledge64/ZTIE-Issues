Story 3.2

You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting. Do NOT change anything until you have (a) READ the
plan + runbook + methodology + this story's brief (`session-briefs/story-3.2-brief.md`),
(b) re-established true state (STEP 0), and (c) confirmed the Validation Debt Register
state + advancement gate.

# PROJECT IDENTITY
ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted artifact
BEFORE it reaches the PDE. Work is validation-gated: nothing is ✅ until a recorded live
pass (the covenant). Three accounts: Pipeline-Hub (641628980935) = brains/control plane
+ durable record; Forensic (360999005254) = self-contained blast zone (ephemeral only);
Pipeline-Sandbox (586917955591) = ZTIE→PDE handoff. Story 3.2 is the AI-correlation core
of Phase 3: it hands the ONE normalized combined-event record (Story 3.1, RD-033) for an
artifact to Amazon Nova Pro (RD-003), correlates the static misconfigurations with the
dynamic behavioral indicators, and records a bounded, verdict-free correlation result —
with exponential-backoff retry on Bedrock throttling.

# WHERE THIS STORY SITS — BUILD TIER 7, ADVANCING FROM TIER 6 (WITHIN P3)
Story 3.2 is **build tier 7** and this session **ADVANCES from tier 6 to tier 7**: its
tier-6 dependency `3.1` (the combined-event normalize) goes ✅, so a NEW dependency layer
opens. This is a tier move WITHIN Phase 3 (NO phase transition — 3.1 already made the
P2→P3 move). Because this is a tier advance, STEP 0 must re-confirm the ENTIRE new
dependency set is ✅ (`3.1` AND its input `2.5`), not merely glance at the prior story.

# ⚠️ ADVANCEMENT GATE — CHECK THIS FIRST
NEW FEATURE story. It may begin ONLY if its Depends-on are ALL ✅ AND the Validation Debt
Register is EMPTY. **As of this prompt's authoring, Story 3.1 was BUILT but sits 🟡 on the
Validation Debt Register awaiting its recorded LIVE pass (it touches the running Hub
pipeline). So the gate is expected ARMED until 3.1 is validated live** (see
`session-briefs/story-3.1-LIVE-RUNBOOK.md`). STEP 0 MUST re-confirm on `main`: `3.1` ✅,
`2.5` ✅, and the Validation Debt Register EMPTY (trust `main` + `check_docs` over this
prompt; if they disagree, `main` wins). **If 3.1 is still 🟡, 3.2 MAY NOT begin — the only
permitted work is validating/reworking 3.1.** This is `check_docs` CHECK B,
machine-enforced. Depends-on: **3.1 ✅** + **2.5 ✅**. Build tier 7.

# WHERE 3.2 SITS (what already exists that it builds on)
By the time 3.2 begins, the Hub tracking record for one `intake_id` carries the Story 3.1
normalized `combined_event` (RD-033, `combined-event.contract.v1`, own pin
`COMBINED_EVENT_CONTRACT_VERSION`), written Hub-side onto the item by the normalizer
(`lambdas/hub_normalize/`, DynamoDB-stream-triggered). Its shape (what 3.2 reads):
- top level: `contract_version` / `intake_id` / `sha256` / `combined_at` / `combined_event`;
- `combined_event.inputs_present` — subset of `static` / `dynamic` / `sanitized`;
- `combined_event.complete` — all three present (an AGGREGATION fact, NOT a verdict);
- `combined_event.sources.{static,dynamic,sanitized}` — each with `presence` +
  bounded roll-up + a Forensic S3 pointer (by reference, RD-009);
- `combined_event.signals` — `static_highest_severity`, `dynamic_outcome`,
  `behavioral_events[]` (relative `offset_ms`, sanitized summaries), `behavioral_event_count`.
It is EVIDENCE only — there is NO verdict field anywhere, and 3.2 must NOT introduce one.
3.2 should tolerate `complete: false` (correlate what is present, honestly).

# THE JOB
For one `intake_id` with a `combined_event`, invoke Amazon Nova Pro (RD-003, via
`bedrock-runtime`) with a bounded prompt built from the combined event, get back a
correlation of static ↔ dynamic evidence, and record a bounded, DERIVED, verdict-free
correlation RESULT on the tracking item — with exponential-backoff retry on
throttling/5xx. It is a REAL model call (no mock model — production-code-at-all-times).

# CONTRACT-FIRST DECISION (make + justify in the new RD)
The combined event ALREADY lives on the Hub tracking record. So 3.2 is very likely a
**Hub-side correlation** (read the combined event → call Nova Pro → write the correlation
result back onto the same record), NOT a new Forensic→Hub crossing — mirroring 3.1's
placement reasoning (keeps RD-009/RD-013 intact, no Forensic durable store, RD-012).
Decide this CONTRACT-FIRST: define the correlation-result schema (bounded, verdict-free,
allow-list, own version pin), decide WHERE the Bedrock call runs, and justify it in the
RD. Do NOT re-cross or duplicate raw data. If it hangs off the same tracking-table stream
as 3.1, remember 3.1's idempotency loop-guard (write only on change) AND avoid a call
storm — gate the Nova Pro invocation so it fires once per intake when the combined event
is ready (e.g. only when `complete` or a bounded settle), not on every item mutation.

# NON-NEGOTIABLE CONSTRAINTS
- CORRELATE, do not re-aggregate/re-capture/re-sanitize. The input is 3.1's combined
  event; 3.1/2.4/2.5 are done — do not re-litigate them.
- EVIDENCE, NEVER A VERDICT. The correlation result has NO verdict/safe/approved/forward/
  malicious/pass_fail/clean field, and the Nova Pro PROMPT must NOT ask the model for a
  verdict — only for correlation of the evidence. The verdict is Hub-side/human-gated
  (Phase 4). NEVER import/self-assert a verdict from the model response.
- REAL MODEL CALL + EXPONENTIAL-BACKOFF RETRY (RD-003). No mock model. Retry throttling/
  5xx with real exponential backoff; make it inspectable (logged/counted), not a single
  call. Tolerate a malformed/absent/oversized model response — RECORD it honestly (a
  `status`), never fabricate a correlation (same honesty discipline as 3.1's absent inputs).
- BOUNDED PROMPT + BOUNDED RESULT. The prompt is built ONLY from the bounded combined
  event (no raw body / findings text / command log / raw trace — RD-009); the result
  schema is allow-list, every field typed + length/enum/range-bounded, arrays maxItems-capped.
- PURE LOGIC + THIN SEAM (the proven 1.2→…→3.1 pattern). Prompt-building + response-parsing
  are PURE + offline-testable; the Bedrock/DynamoDB I/O is behind a thin `awsio` seam.
- VALIDATION-GATED, NEVER ON INFERENCE: 3.2 flips ✅ only on a recorded LIVE pass of the
  FINAL code (a real Nova Pro invocation — it touches the running pipeline + Bedrock).
- DOCS FIRST-CLASS (RD-015): PR-reviewed, never straight to main; PROJECT_PLAN ↔ RUNBOOK
  in EXACT alignment.

# NEW REGISTERED DECISION
Record the Nova Pro correlation design as a new RD with rationale + candidate NIST/ISO
mappings. RE-VERIFY the next free RD number at STEP 0 with
`grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md | sort -u | tail` and take the next free number
(RD-033 is 3.1's; expect RD-034, but VERIFY — RD-number collisions have happened, and
RD-017 is a historical gap).

# OPERATIONAL CONTEXT (state this on EVERY command block)
  Build sandbox is INTEGRATIONS_ONLY (NO AWS creds; PyPI + npm BLOCKED — boto3/pytest/
  moto/jsonschema/aws-cdk-lib NOT installable). You BUILD; the USER validates live in
  CloudShell (ambient creds, no --profile). Region us-east-1. Confirm the active account
  with `aws sts get-caller-identity` before EVERY operational block. The tracking table +
  the correlation compute (if Hub-side) are in the HUB (641628980935); the artifact-
  touching compute is in FORENSIC (360999005254) — TWO CloudShell tabs if a live step
  touches both. Nova Pro is reached via `bedrock-runtime`. Tooling: `ruff` is NOT on PATH
  — use `~/.pyenv/versions/3.12.13/bin/ruff`; `prettier` and `npx tsc` need
  `env -u NODE_OPTIONS`; npm is BLOCKED so `tsc --noEmit` legitimately shows ONLY the
  missing-`aws-cdk-lib` error family (TS2307/2339/2353/2591/2304) identical across all
  stacks — confirm the new code adds NO NEW error TYPE. NOTE the repo's default `python3`
  is 3.9; run your own tests stdlib-only + boto3-stubbed so they pass offline (existing
  moto-based `test_handler.py` in `hub_ingest`/`intake` FAIL to import offline — that is
  pre-existing, not your regression).

# HARD-WON LESSONS (do NOT repeat)

## The derived pattern (held 6× now: 1.2→2.2→2.3→2.4→2.5→3.1)
Contract-first + a bounded allow-list record with its OWN version pin + PURE logic + a
thin `awsio` seam + evidence-never-verdict + a two-layer conformance test (stdlib
pure-Python walk + a jsonschema `skipUnless` live layer) + a recursive no-verdict-key scan
+ a schema-has-no-verdict-property check. Reuse it for 3.2's correlation-result record.
3.1 was a HUB-SIDE derivation (RD-033), NOT a new RD-013 crossing — its input was already
Hub-side, so it read the item → built the record → wrote it back (integrity-bound, never
touches status). 3.2's combined-event input is likewise already Hub-side; the SAME
placement reasoning very likely applies.

## Nova Pro is a REAL call — design for non-determinism + throttling
The model output is non-deterministic and can be malformed/truncated. Parse it DEFENSIVELY
into the bounded result schema; if it does not conform, RECORD a `status` (e.g.
`model_error` / `unparseable`) — never fabricate a correlation and never let the model
assert a verdict. RD-003 requires exponential-backoff retry on `ThrottlingException`/5xx
— make it real, bounded (max attempts), jittered, and inspectable. The Forensic infra
(2.0) already provisions Bedrock access in-VPC; if 3.2 runs Hub-side it needs its own
`bedrock:InvokeModel` grant scoped to the Nova Pro model ARN.

## check_docs self-test fixture drift
`scripts/test_check_docs.py` pins `_NEW_WORK_STORY` to a downstream ⬜ master-table story.
It is currently pinned to **3.2** (repointed from 3.1 when 3.1 went 🟡). **When 3.2 leaves
⬜ (i.e. THIS story starts/finishes), repoint `_NEW_WORK_STORY` to the next still-⬜
feature story (e.g. 3.3) IN THE SAME PR**, then re-run `python3 -m unittest
scripts.test_check_docs` and confirm the SUITE line is **OK** (the `check_docs: FAIL …`
lines it prints while exercising itself are expected — the SUITE `OK` vs `FAILED
(failures=N)` line is what matters).

## check_docs timing (RD-015)
Run `python3 scripts/check_docs.py` only AFTER committing any status/register edit (CHECK
B's baseline is `git show HEAD:RUNBOOK.md`; running before the commit gives a
FALSE-POSITIVE). Also run `python3 -m unittest scripts.test_check_docs` and read the SUITE
result line, not the fixture-print lines.

## Deploy-gap (if 3.2 touches any Lambda) — TWO failure modes, both silent
Any code change to a Lambda only takes effect after `cdk deploy`. If 3.2 is Hub-side, the
redeploy is `ZtieHubTrackingStack`. TWO ways this bites behind a green deploy:
  1. **Stack not redeployed** — the live Lambda still runs old code.
  2. **Redeployed from the WRONG git checkout** — `cdk deploy` prints `✅ UPDATE_COMPLETE`
     while re-synthesizing STALE code (2.5 live, 2026-09-11: the operator deployed from
     `main`, saw green, and the new env vars were absent).
Also: a `cdk deploy` context `-c` value can be WRONG and still deploy green (2.5: a wrong
role ARN → runtime `UnauthorizedOperation`). GUARD (bake into the 3.2 LIVE-RUNBOOK):
  * BEFORE deploy: `git rev-parse --abbrev-ref HEAD && git log --oneline -1` (expect the
    story branch tip) AND `grep -n <new-marker> <the-stack-or-lambda-source>`.
  * AFTER deploy: inspect the LIVE resource (`aws lambda get-function-configuration ...
    --query Environment.Variables`) and confirm the new env/behavior is present. When a
    call "succeeds" but produces no result, READ THE LAMBDA'S OWN LOGS — never trust a
    green status alone.

## Two accounts, two tabs
`aws sts get-caller-identity` before EVERY block. Tracking table = HUB; a
`ResourceNotFoundException` on it means you queried from Forensic. `/tmp` + shell vars +
pip installs are WIPED on CloudShell recycle — re-set every var AND reinstall `awscurl` in
the SAME block right before use. Placeholders like `<...>` are literal — substitute REAL
values first. Intake API wants a JSON envelope via awscurl (SigV4):
`{"filename":…, "content_type":…, "submitter":…, "content_base64":"<base64>"}`, URL last,
`-d @file.json`; `pip install awscurl` first. `gh pr create` is BROKEN — open PRs via
`gh api repos/warrenrutledge64/ZTIE-Issues/pulls`.

# STEP 0 — RE-ESTABLISH TRUE STATE (before any edit)
# Trust `main` + `check_docs` over anything written here; if they disagree, `main` wins.
- `git fetch origin`; `git checkout main`; `git reset --hard origin/main`. List open PRs.
- `python3 scripts/check_docs.py` → expect PASS. `python3 -m unittest
  scripts.test_check_docs` → expect the SUITE line **OK** (the `check_docs: FAIL …` lines
  are the checker testing ITSELF against the pinned story — not real failures).
- Confirm these EXPECTED TRUTHS (do NOT change until validated):
    - This story = 3.2 = ⬜ (not started), **build tier 7**, Depends-on `3.1` + `2.5`.
    - **Tier transition:** this session advances **tier 6 → 7** (WITHIN P3). Confirm EVERY
      tier-≤6 dependency is ✅ — `3.1` (tier 6) AND its input `2.5` — not just the prior story.
    - **GATE:** the Validation Debt Register MUST be EMPTY and `3.1`/`2.5` MUST be ✅. If
      the register is non-empty for any reason, STOP — the only permitted work is clearing
      that open entry (very likely 3.1's own live pass).
    - Dep ✅: 3.1 ✅ (only after its live pass); 2.5 ✅.
    - Next free RD number: RE-VERIFY (expect RD-034).
- Branch off `main` (current HEAD). Branch name: `feature/story-3.2`.

# THIS SESSION'S OBJECTIVE
For one `intake_id` with a `combined_event`, invoke Nova Pro (real call, exponential-
backoff retry) over a bounded prompt built from the combined event, and record a bounded,
verdict-free correlation RESULT on the tracking item on a contract-first schema, ready for
3.3 (accuracy + gap_analysis synthesis).

# DEFINITION OF DONE (this session) — a PASS/FAIL GATE
1. For one `intake_id`, a REAL Nova Pro invocation over the combined event returns a
   correlation, recorded as a bounded correlation result on the tracking item.
2. Keyed by `intake_id`+`sha256`; exponential-backoff retry exercised/inspectable; a
   malformed/absent model response is RECORDED honestly (never fabricated).
3. EVIDENCE only — no verdict/safe/forward field anywhere; the prompt does not ask for a
   verdict; RD-009/RD-013 boundary intact (no raw data, no Forensic durable store).
4. Validated LIVE (real Bedrock call) and RECORDED.
- Goes ✅ ONLY on a recorded live pass of the FINAL code. No recorded pass → stays 🟡 (and
  3.2 goes on the Validation Debt Register in the same commit). On any fail: stay on 3.2,
  fix, re-validate.

# ENVIRONMENT
- Repo cloned; push to `feature/story-3.2`, never main. Open PRs via
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls` (NOT `gh pr create`). Merges are the
  repo-owner's action. Live AWS is the stakeholder's Hub/Forensic CloudShell action.

# WORKING AGREEMENT
- One story to completion: design → build → validate → RECORD + flip status → paired
  status commit; push to a branch; open a PR. After merge, `git log main..feature/story-3.2`
  to confirm the whole branch landed (base-branch trap).
- Validation drives status; the hard advancement gate governs advancement.
- MANAGEMENT ARTIFACTS ARE FIRST-CLASS (RD-015): brief + RUNBOOK + PROJECT_PLAN aligned;
  the new RD + candidate NIST/ISO mappings recorded; all via PR. **Repoint the
  `check_docs` fixture (`_NEW_WORK_STORY`) off 3.2 in the same PR** (see the lesson above).
  Re-run the G-3 doc checks AFTER committing any status edit.
- Author a 3.2 LIVE-RUNBOOK for the stakeholder's real Nova Pro validation (Hub redeploy
  + deploy-gap guards + submit-or-reuse an intake + verify the correlation result +
  no-verdict grep + retry-inspection).
- At session end, author the NEXT story's brief + prompt (3.3 accuracy + gap_analysis, or
  as the graph leaves it) with THIS session's real Lessons Learned. Zero cold-start.
- If blocked (incl. by the 3.1 gate), push partial progress + a draft PR; surface the
  blocker; never silently fail.
