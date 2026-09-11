Story 3.1

You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting. Do NOT change anything until you have (a) READ the
plan + runbook + methodology + this story's brief (`session-briefs/story-3.1-brief.md`),
(b) re-established true state (STEP 0), and (c) confirmed the Validation Debt Register
state + advancement gate.

# PROJECT IDENTITY
ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted artifact
BEFORE it reaches the PDE. Work is validation-gated: nothing is ✅ until a recorded live
pass (the covenant). Three accounts: Pipeline-Hub (641628980935) = brains/control plane
+ durable record; Forensic (360999005254) = self-contained blast zone (ephemeral only);
Pipeline-Sandbox (586917955591) = ZTIE→PDE handoff. Story 3.1 is the FIRST Phase-3 story:
it AGGREGATES + NORMALIZES the per-lane derived outputs for one artifact — the static-scan
summary (2.1/2.2), the dynamic-run outcome (2.3), and the SANITIZED behavioral telemetry
(2.5) — into ONE shared, normalized combined-event record that the Phase-3 Nova Pro
correlation engine (3.2) reasons over.

# ⚠️ ADVANCEMENT GATE — CHECK THIS FIRST
NEW FEATURE story. It may begin ONLY if its Depends-on are ALL ✅ AND the Validation Debt
Register is EMPTY. **As of this prompt (authored 2026-09-10 at the end of the 2.5 build
session), the register has ONE OPEN entry: Story 2.5 (🟡, built, awaiting its live pass).
The gate is ARMED — 3.1 MAY NOT BEGIN until 2.5 is cleared by its own recorded live pass**
(see `session-briefs/story-2.5-LIVE-RUNBOOK.md`). STEP 0 MUST re-confirm on `main` that
2.5 is ✅ and the register is EMPTY before touching anything (trust `main` + `check_docs`
over this prompt; if they disagree, `main` wins). If 2.5 is still 🟡, the ONLY permitted
work is validating/reworking 2.5 — STOP and surface that. This is `check_docs` CHECK B,
machine-enforced. Depends-on: **2.6 ✅** (the fork/join) + (as inputs) 2.1/2.2 + 2.5.
Build tier 6.

# WHERE 3.1 SITS (what already exists that it builds on)
By the time 3.1 begins, the Hub tracking record for one `intake_id` already carries FOUR
bounded, verdict-free derived records, each crossed via the RD-013 gate and applied
integrity-bound (intake_id+sha256):
- **`scan`** — static-scan summary (2.1/2.2 — `SUMMARY_CONTRACT_VERSION`).
- **`run`** — dynamic-run outcome (2.3 — `DYNAMIC_RUN_CONTRACT_VERSION`).
- **`behavior`** — raw behavioral summary (2.4 — `BEHAVIOR_CONTRACT_VERSION`, 8th kind).
- **`sanitized`** — the ≤25K-token, entropy-scrubbed, noise-suppressed sanitized view
  (2.5 — `SANITIZED_TELEMETRY_CONTRACT_VERSION`, 9th kind).
- **`collected`** — the 2.6 both-lane JOIN record (`COLLECTED_CONTRACT_VERSION`, 7th kind).
The Hub validator (`lambdas/hub_ingest/handler.py`) routes by a UNIQUE discriminator per
kind and applies each with a conditional update that NEVER touches status/verdict. The
nine existing discriminators are: classification / routing / rejection / scan / run /
status / collected / behavior / sanitized — do NOT collide with them.

# THE JOB
Produce ONE shared, normalized COMBINED-EVENT record for an `intake_id` that aggregates
the static findings + dynamic run outcome + sanitized behavioral telemetry into a single
consistent shape, verdict-free, keyed by intake_id+sha256, for Nova Pro (3.2) to consume.

# CONTRACT-FIRST DECISION (make + justify in the new RD)
The four inputs ALREADY live on the Hub tracking record. So 3.1 is very likely a
**Hub-side normalize** (read the tracking record → build the combined event → write it
back onto the same record), NOT a new Forensic→Hub crossing — this keeps the RD-009/
RD-013 boundary intact and adds no Forensic durable store (RD-012). Decide this
CONTRACT-FIRST: define the shared normalized-event schema (bounded, verdict-free,
allow-list, own version pin if it is a crossed/derived record), and justify Hub-side
normalize vs. a new kind in the RD. Do NOT re-cross or duplicate raw data.

# NON-NEGOTIABLE CONSTRAINTS
- AGGREGATE/NORMALIZE, do not re-capture or re-cross raw data. Inputs are the already-
  crossed derived records; 2.4/2.5 capture+sanitize are done — do not re-litigate them.
- EVIDENCE, NEVER A VERDICT. The combined record has NO verdict/safe/approved/forward/
  malicious/pass_fail/clean field. The verdict is Hub-side/human-gated (Phase 4).
- NORMALIZE HONESTLY. A lane's derived record may not have landed yet (SQS ordering) or a
  lane may be `no_trace`/`errored` — record WHICH inputs are present, never fabricate a
  missing one.
- RELATIVE CLOCK ONLY for any behavioral timings carried through (the 2.5 events already
  use relative `offset_ms`) — never a wall clock.
- PURE LOGIC + THIN SEAM (the proven 1.2→2.2→2.3→2.4→2.5 pattern). The
  aggregation/normalization is PURE + offline-testable; any I/O (read/write the Hub
  record) is behind a thin boto3 seam.
- VALIDATION-GATED, NEVER ON INFERENCE: 3.1 flips ✅ only on a recorded pass of the FINAL
  code (live if it touches the running pipeline; offline conformance otherwise).
- DOCS FIRST-CLASS (RD-015): PR-reviewed, never straight to main; PROJECT_PLAN ↔ RUNBOOK
  in EXACT alignment.

# NEW REGISTERED DECISION
Record the aggregation/normalization design as a new RD with rationale + candidate
NIST/ISO mappings. RE-VERIFY the next free RD number at STEP 0 with
`grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md | sort -u | tail` and take the next free number
(RD-031 is 2.5's; expect RD-032, but VERIFY — RD-number collisions have happened).

# OPERATIONAL CONTEXT (state this on EVERY command block)
  Build sandbox is INTEGRATIONS_ONLY (NO AWS creds; PyPI + npm BLOCKED — boto3/pytest/
  moto/jsonschema/aws-cdk-lib NOT installable). You BUILD; the USER validates live in
  CloudShell (ambient creds, no --profile). Region us-east-1. Confirm the active account
  with `aws sts get-caller-identity` before EVERY operational block. The tracking table
  is in the HUB (641628980935); the artifact-touching compute is in FORENSIC
  (360999005254) — TWO CloudShell tabs if a live step touches both. Tooling: `ruff` is
  NOT on PATH — use `~/.pyenv/versions/3.12.13/bin/ruff`; `prettier` and `npx tsc` need
  `env -u NODE_OPTIONS`; npm is BLOCKED so `tsc --noEmit` legitimately shows ONLY the
  missing-`aws-cdk-lib` error family (TS2307/2339/2353/2591/2304) identical across all
  stacks — confirm the new code adds NO NEW error TYPE.

# HARD-WON LESSONS (do NOT repeat)

## check_docs self-test fixture drift (NEW, learned live in the 2.5 session)
`scripts/test_check_docs.py` pins `_NEW_WORK_STORY` to a downstream ⬜ master-table story
to drive its CHECK A / CHECK B self-tests. It is currently pinned to **3.1** (repointed
from 2.5 when 2.5 went 🟡). **When 3.1 leaves ⬜ (i.e. THIS story starts/finishes),
repoint `_NEW_WORK_STORY` to the next still-⬜ master-table feature story (e.g. 3.2/3.3)
IN THE SAME PR**, then re-run `python3 -m unittest scripts.test_check_docs` and confirm
**OK / 3 tests**. If you skip this, both self-tests silently stop firing (their mutations
become no-ops) — a REAL `FAILED (failures=2)`, NOT the harmless `check_docs: FAIL …`
fixture-print lines the suite emits while exercising itself. Distinguish the two: the
SUITE result line (`OK` vs `FAILED (failures=N)`) is what matters.

## check_docs timing (RD-015)
Run `python3 scripts/check_docs.py` only AFTER committing any status/register edit (CHECK
B's baseline is `git show HEAD:RUNBOOK.md`; running before the commit gives a
FALSE-POSITIVE). Also run `python3 -m unittest scripts.test_check_docs` and read the SUITE
result line, not the fixture-print lines.

## The lane pattern (held 5× now: 1.2→2.2→2.3→2.4→2.5)
Contract-first + a new envelope kind with its OWN version pin + a UNIQUE discriminator +
PURE logic + a thin `awsio` seam + evidence-never-verdict + a two-layer conformance test
(stdlib pure-Python walk + a jsonschema `skipUnless` live layer) + a recursive
no-verdict-key scan + a schema-has-no-verdict-property check. If 3.1 introduces a crossed/
derived record it is a candidate 10th kind — `grep` the nine existing discriminators first
so it does not collide, and give it its OWN version pin (never ride the shared
CONTRACT_VERSION).

## Deploy-gap (if 3.1 touches any Lambda) — TWO failure modes, both silent
Any code change to a Lambda only takes effect after `cdk deploy`. If 3.1 is Hub-side, the
redeploy is `ZtieHubTrackingStack` — and it MUST ship any new/updated contract bundle
(`cp -r . /asset-output` picks up `schemas`/bundled JSON automatically) or a crossed
record fail-closed QUARANTINES. Put the redeploy as an explicit pre-run step in the 3.1
LIVE-RUNBOOK. TWO ways this bites, both hidden behind a green deploy:
  1. **Stack not redeployed** — the live Lambda still runs old code (the classic gap).
  2. **NEW (2.5 live, 2026-09-11): stack redeployed from the WRONG git checkout.** A
     `cdk deploy` prints `✅ UPDATE_COMPLETE` even when the CloudShell box was never
     switched to the story branch — it just re-synthesizes the STALE stack definition. In
     2.5 the operator skipped STEP 0's `git checkout feature/story-2.5`, deployed from
     `main`, got a green deploy, and the new env vars (`SANITIZED_TELEMETRY_CONTRACT_VERSION`,
     `SANITIZE_TOKEN_BUDGET`) were STILL absent on the live Lambda.
GUARD (bake both into the 3.1 LIVE-RUNBOOK):
  * BEFORE deploy: `git rev-parse --abbrev-ref HEAD && git log --oneline -1` (expect the
    story branch tip) AND `grep -n <new-marker> <the-stack-or-lambda-source>` (prove the
    checkout carries the change; if absent, re-run the checkout).
  * AFTER deploy: inspect the LIVE resource (e.g. `aws lambda get-function-configuration
    ... --query Environment.Variables`) and confirm the NEW env/behavior is actually
    present. NEVER trust the `✅ UPDATE_COMPLETE` line alone — a green deploy of the wrong
    checkout is a silent deploy-gap.

## Two accounts, two tabs
`aws sts get-caller-identity` before EVERY block. Tracking table = HUB; a
`ResourceNotFoundException` on it means you queried from Forensic. `/tmp` + shell vars +
pip installs are WIPED on CloudShell recycle — re-set every var AND reinstall `awscurl` in
the SAME block right before use. Placeholders like `<...>` are literal shell redirections
— substitute REAL values first. Intake API wants a JSON envelope via awscurl (SigV4):
`{"filename":…, "content_type":…, "submitter":…, "content_base64":"<base64>"}`, URL last,
`-d @file.json`; `pip install awscurl` first. `gh pr create` is BROKEN — open PRs via
`gh api repos/warrenrutledge64/ZTIE-Issues/pulls`.

# STEP 0 — RE-ESTABLISH TRUE STATE (before any edit)
# Trust `main` + `check_docs` over anything written here; if they disagree, `main` wins.
- `git fetch origin`; `git checkout main`; `git reset --hard origin/main`. List open PRs.
- `python3 scripts/check_docs.py` → expect PASS. `python3 -m unittest
  scripts.test_check_docs` → expect **OK / 3 tests** (the `check_docs: FAIL …` lines are
  the checker testing ITSELF against the pinned story — not real failures).
- Confirm these EXPECTED TRUTHS (do NOT change until validated):
    - This story = 3.1 = ⬜ (not started), build tier 6, Depends-on `2.6`.
    - **GATE:** `2.5` MUST be ✅ and the Validation Debt Register MUST be EMPTY. If 2.5 is
      still 🟡, STOP — the only permitted work is validating/reworking 2.5.
    - Dep ✅: 2.6 ✅; and (inputs) 2.1/2.2 ✅, 2.5 ✅.
    - Next free RD number: RE-VERIFY (expect RD-032).
- Branch off `main` (current HEAD). Branch name: `feature/story-3.1`.

# THIS SESSION'S OBJECTIVE
Aggregate + normalize the per-lane derived outputs (static-scan summary + dynamic-run
outcome + sanitized behavioral telemetry) for one `intake_id` into ONE shared, normalized,
verdict-free combined-event record on a contract-first schema, ready for Nova Pro (3.2).

# DEFINITION OF DONE (this session) — a PASS/FAIL GATE
1. For one `intake_id`, the static + dynamic + sanitized-telemetry outputs normalize into
   ONE combined record on the shared schema.
2. Keyed by `intake_id`+`sha256`; records WHICH inputs are present (honest about missing/
   errored lanes); relative timings preserved.
3. EVIDENCE only — no verdict/safe/forward field anywhere; RD-009/RD-013 boundary intact
   (no re-crossed raw data, no Forensic durable store).
4. Validated (live if it touches the running pipeline; offline conformance otherwise) and
   RECORDED.
- Goes ✅ ONLY on a recorded pass of the FINAL code. No recorded pass → stays 🟡 (and 3.1
  goes on the Validation Debt Register in the same commit). On any fail: stay on 3.1, fix,
  re-validate.

# ENVIRONMENT
- Repo cloned; push to `feature/story-3.1`, never main. Open PRs via
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls` (NOT `gh pr create`). Merges are the
  repo-owner's action. Live AWS is the stakeholder's Hub/Forensic CloudShell action.

# WORKING AGREEMENT
- One story to completion: design → build → validate → RECORD + flip status → paired
  status commit; push to a branch; open a PR. After merge, `git log main..feature/story-3.1`
  to confirm the whole branch landed (base-branch trap).
- Validation drives status; the hard advancement gate governs advancement.
- MANAGEMENT ARTIFACTS ARE FIRST-CLASS (RD-015): brief + RUNBOOK + PROJECT_PLAN aligned;
  the new RD + candidate NIST/ISO mappings recorded; all via PR. **Repoint the
  `check_docs` fixture (`_NEW_WORK_STORY`) off 3.1 in the same PR** (see the lesson above).
  Re-run the G-3 doc checks AFTER committing any status edit.
- At session end, author the NEXT story's brief + prompt (3.2 Nova Pro correlation, or as
  the graph leaves it) with THIS session's real Lessons Learned. Zero cold-start.
- If blocked (incl. by the 2.5 gate), push partial progress + a draft PR; surface the
  blocker; never silently fail.
