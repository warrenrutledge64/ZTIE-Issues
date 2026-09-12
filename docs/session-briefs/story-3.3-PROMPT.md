Story 3.3

You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting. Do NOT change anything until you have (a) READ the
plan + runbook + methodology + this story's brief (`session-briefs/story-3.3-brief.md`),
(b) re-established true state (STEP 0), and (c) confirmed the Validation Debt Register
state + advancement gate.

# PROJECT IDENTITY
ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted artifact
BEFORE it reaches the PDE. Work is validation-gated: nothing is ✅ until a recorded live
pass (the covenant). Three accounts: Pipeline-Hub (641628980935) = brains/control plane
+ durable record; Forensic (360999005254) = self-contained blast zone (ephemeral only);
Pipeline-Sandbox (586917955591) = ZTIE→PDE handoff. Story 3.3 is the synthesis step of
Phase 3: it runs the `accuracy` + `gap_analysis` programs over the ONE verdict-free Nova
Pro correlation result (Story 3.2, RD-035) for an artifact to eliminate false positives
and surface static↔dynamic gaps, recording a bounded, verdict-free synthesis result.

# WHERE THIS STORY SITS — BUILD TIER 10, ADVANCING FROM TIER 9 (WITHIN P3)
Story 3.3 is **build tier 10** and this session **ADVANCES from tier 9 to tier 10**: its
tier-9 dependency `3.2` (Nova Pro correlation) goes ✅, so a NEW dependency layer opens.
This is a tier move WITHIN Phase 3 (NO phase transition). Because this is a tier advance,
STEP 0 must re-confirm the ENTIRE new dependency set is ✅ (`3.2` AND its inputs `3.1` +
`2.5`), not merely glance at the prior story.

# ⚠️ ADVANCEMENT GATE — CHECK THIS FIRST
NEW FEATURE story. It may begin ONLY if its Depends-on are ALL ✅ AND the Validation Debt
Register is EMPTY. **As of this prompt's authoring, Story 3.2 was BUILT but sits 🟡 on the
Validation Debt Register awaiting its recorded LIVE Nova Pro pass (it makes a real
Bedrock call). So the gate is expected ARMED until 3.2 is validated live** (see
`session-briefs/story-3.2-LIVE-RUNBOOK.md`). STEP 0 MUST re-confirm on `main`: `3.2` ✅
and the Validation Debt Register EMPTY (trust `main` + `check_docs` over this prompt; if
they disagree, `main` wins). **If 3.2 is still 🟡, 3.3 MAY NOT begin — the only permitted
work is validating/reworking 3.2.** This is `check_docs` CHECK B, machine-enforced.
Depends-on: **3.2 ✅**. Build tier 10.

# WHERE 3.3 SITS (what already exists that it builds on)
By the time 3.3 begins, the Hub tracking record for one `intake_id` carries the Story 3.2
`correlation_result` (RD-035, `correlation.contract.v1`, own pin
`CORRELATION_CONTRACT_VERSION`), written Hub-side by the correlator (`lambdas/hub_correlate/`,
DynamoDB-stream-triggered). Its shape (what 3.3 reads):
- top level: `contract_version`/`intake_id`/`sha256`/`correlated_at`/`status`
  (`correlated`/`model_error`/`unparseable`/`skipped_no_signals`) + `model_id`/`attempts`/
  `latency_ms`/`input_tokens`/`output_tokens`/`truncated`/`combined_complete`;
- only when `status: correlated`: a `correlation` object — `summary`, `finding_count`,
  `highest_correlation_severity`, `findings[]` (each: `kind`∈correlated/static_only/
  dynamic_only/contradiction, `severity`, `title`, optional `detail`/`static_refs`/
  `behavioral_refs`).
It is EVIDENCE only — there is NO verdict field anywhere, and 3.3 must NOT introduce one.
3.3 should tolerate `status != correlated` (synthesize honestly over an absent/errored
correlation — record it, never fabricate).

# THE JOB
For one `intake_id` with a `correlation_result`, run the `accuracy` + `gap_analysis`
synthesis: (a) `accuracy` scores how well the correlation eliminates false positives (a
static flag that dynamic evidence shows was never exercised is a candidate false
positive), and (b) `gap_analysis` surfaces where the two lanes disagree or leave a gap.
Record a bounded, DERIVED, verdict-free synthesis RESULT on the tracking item. Decide
CONTRACT-FIRST whether this is a SECOND Nova Pro call (a synthesis prompt over the
correlation) or PURE post-processing of the 3.2 findings — and justify it in the new RD.
If it calls Nova Pro, it is a REAL call (no mock model) with exponential-backoff retry.

# CONTRACT-FIRST DECISION (make + justify in the new RD)
The correlation result ALREADY lives on the Hub tracking record. So 3.3 is very likely a
**Hub-side synthesis** (read the correlation result → synthesize → write the synthesis
result back onto the same record), NOT a new Forensic→Hub crossing — mirroring 3.1/3.2's
placement reasoning (keeps RD-009/RD-013 intact, no Forensic durable store, RD-012).
Decide this CONTRACT-FIRST: define the synthesis-result schema (bounded, verdict-free,
allow-list, own version pin), decide WHERE it runs + whether it calls the model, and
justify it in the RD. If it hangs off the tracking-table stream, reuse the 3.1/3.2
idempotency + call-storm guard (a content fingerprint over the correlation, `Decimal`-
canonicalized) so it fires once per settled correlation, not on every item mutation.

# NON-NEGOTIABLE CONSTRAINTS
- SYNTHESIZE, do not re-correlate/re-normalize/re-capture/re-sanitize. The input is 3.2's
  correlation result; 3.2/3.1/2.5/2.4 are done — do not re-litigate them.
- EVIDENCE, NEVER A VERDICT. The synthesis result has NO verdict/safe/approved/forward/
  malicious/pass_fail/clean field, and if it uses Nova Pro the PROMPT must NOT ask the
  model for a verdict — only for synthesis of the evidence. The verdict is Phase 4.
- REAL MODEL CALL + EXPONENTIAL-BACKOFF RETRY (RD-003) IF it calls Nova Pro. No mock
  model. Tolerate a malformed/absent/oversized response — RECORD it honestly (a
  `status`), never fabricate.
- BOUNDED IN + BOUNDED OUT. Reason ONLY over the bounded 3.2 correlation result (no raw
  data — RD-009); the result schema is allow-list, typed + bounded, arrays maxItems-capped.
- PURE LOGIC + THIN SEAM (the proven 1.2→…→3.2 pattern). Synthesis logic is PURE +
  offline-testable; any Bedrock/DynamoDB I/O is behind a thin per-lane `awsio` seam.
- VALIDATION-GATED, NEVER ON INFERENCE: 3.3 flips ✅ only on a recorded LIVE pass of the
  FINAL code (a demonstrated false-positive reconciliation; if it calls Nova Pro, a real
  invocation).
- DOCS FIRST-CLASS (RD-015): PR-reviewed, never straight to main; PROJECT_PLAN ↔ RUNBOOK
  in EXACT alignment.

# NEW REGISTERED DECISION
Record the synthesis design as a new RD with rationale + candidate NIST/ISO mappings.
RE-VERIFY the next free RD number at STEP 0 with
`grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md | sort -u | tail` (RD-035 is 3.2's; expect
RD-036, but VERIFY — RD-number collisions have happened, and RD-017 is a historical gap).

# OPERATIONAL CONTEXT (state this on EVERY command block)
  Build sandbox is INTEGRATIONS_ONLY (NO AWS creds; PyPI + npm BLOCKED — boto3/pytest/
  moto/jsonschema/aws-cdk-lib NOT installable). You BUILD; the USER validates live in
  CloudShell (ambient creds, no --profile). Region us-east-1. Confirm the active account
  with `aws sts get-caller-identity` before EVERY operational block. The tracking table +
  the synthesis compute (if Hub-side) are in the HUB (641628980935); the artifact-
  touching compute is in FORENSIC (360999005254). Nova Pro is reached via
  `bedrock-runtime`; Bedrock model access must be ENABLED for the Hub account (or the
  first call fails AccessDenied). Tooling: repo default `python3` is 3.9 — run your tests
  with `~/.pyenv/versions/3.12.13/bin/python3`; `ruff` is at
  `~/.pyenv/versions/3.12.13/bin/ruff` (repo has NO ruff config → DEFAULT rules; a blind
  `except Exception` that does NOT re-raise needs `# noqa: BLE001`); `prettier`/`tsc` are
  the global nvm ones (`env -u NODE_OPTIONS`); npm is BLOCKED so `tsc --noEmit` shows ONLY
  the missing-`aws-cdk-lib` family (TS2304/2307/2339/2353/2591) — confirm NO NEW error
  TYPE. Do NOT prettier-reformat the generated JSON contracts (breaks no-drift). Keep your
  own tests stdlib-only + boto3/botocore-stubbed so they pass offline.

# HARD-WON LESSONS (do NOT repeat)

## The derived pattern (held 7× now: 1.2→2.2→2.3→2.4→2.5→3.1→3.2)
Contract-first + a bounded allow-list record with its OWN version pin + PURE logic + a
thin `awsio` seam + evidence-never-verdict + a two-layer conformance test (stdlib
pure-Python walk + a jsonschema `skipUnless` live layer) + a recursive no-verdict-key scan
+ a schema-has-no-verdict-property check. Reuse it for 3.3's synthesis-result record. 3.2
was a HUB-SIDE derivation (RD-035), NOT a new RD-013 crossing — its input was already
Hub-side, so it read the item → invoked Nova Pro → wrote the result back (integrity-bound,
never touches status). 3.3's correlation-result input is likewise already Hub-side; the
SAME placement reasoning very likely applies.

## C.3 contract-gen workflow (unchanged)
Add a NEW `scripts/gen_<name>_contract.py` (SCHEMA dict + module-level `OUT_PATHS` segment
tuples + a `main()` delegating to `contract_writer.{resolve_out_paths,write_contract}`),
register it in `gen_contracts.py`'s `CONTRACT_MODULES`, and **`chmod +x` it** (the others
are executable; ruff EXE001 fires on a shebang'd non-executable). Prove no-drift with
`git diff -- schemas lambdas` after regenerating; confirm the two copies are byte-identical.

## Nova Pro is a REAL call (if 3.3 uses it) — design for non-determinism + throttling
Reuse the 3.2 `awsio.invoke_nova` pattern: real exponential-backoff + full jitter, bounded
`max_attempts`, returns the attempt count so the retry is inspectable; parse the response
DEFENSIVELY into the bounded schema; a malformed/absent response is RECORDED via a
`status`, never fabricated; the prompt must NOT ask for a verdict. Nova Pro on-demand is
reached via the region-prefixed inference profile `us.amazon.nova-pro-v1:0` (env-
configurable); scope the `bedrock:InvokeModel` grant to EXACTLY the Nova Pro model/profile
ARNs (never `*`). Retry-loop TEST TRAP: a fake `ClientError` for a NON-retryable code
(e.g. `ValidationException`) must carry a 4xx status, not 429, or the retryability
heuristic (429/5xx = retryable) will retry it and your "not retried" assertion fails.

## check_docs self-test fixture drift
`scripts/test_check_docs.py` pins `_NEW_WORK_STORY` to a downstream ⬜ master-table story.
It is currently pinned to **3.3** (repointed from 3.2 when 3.2 went 🟡). **When 3.3 leaves
⬜ (i.e. THIS story starts/finishes), repoint `_NEW_WORK_STORY` to the next still-⬜
feature story (e.g. 3.4) IN THE SAME PR**, then re-run `python3 -m unittest
scripts.test_check_docs` and confirm the SUITE line is **OK** (the `check_docs: FAIL …`
lines it prints while exercising itself are expected — the SUITE `OK` vs `FAILED
(failures=N)` line is what matters).

## check_docs timing (RD-015)
Run `python3 scripts/check_docs.py` only AFTER committing any status/register edit (CHECK
B's baseline is `git show HEAD:RUNBOOK.md`; running before the commit gives a
FALSE-POSITIVE). Set 3.3 🟡 AND add it to the Validation Debt Register in the SAME commit
(CHECK A requires every 🟡 feature story to be on the register; CHECK B allows a story
that is IN the register). Also run `python3 -m unittest scripts.test_check_docs`.

## Deploy-gap (if 3.3 touches any Lambda) — TWO failure modes, both silent
If 3.3 is Hub-side, the redeploy is `ZtieHubTrackingStack`. (1) Stack not redeployed → old
code still live. (2) Redeployed from the WRONG git checkout → green `UPDATE_COMPLETE`
ships STALE code. GUARD: BEFORE deploy `git rev-parse --abbrev-ref HEAD && git log
--oneline -1` AND `grep` the new marker in the stack source; AFTER deploy inspect the LIVE
resource (`aws lambda get-function-configuration ... --query Environment.Variables`) and
confirm the new env/behavior is present. A `-c` context value can be wrong and still
deploy green. When a call "succeeds" but produces no result, READ THE LAMBDA'S OWN LOGS.

## Two accounts, two tabs
`aws sts get-caller-identity` before EVERY block. Tracking table + Bedrock = HUB; a
`ResourceNotFoundException` on the table means you queried from Forensic. `/tmp` + shell
vars + pip installs are WIPED on CloudShell recycle — re-set every var AND reinstall
`awscurl` in the SAME block right before use. `gh pr create` is BROKEN — open PRs via
`gh api repos/warrenrutledge64/ZTIE-Issues/pulls`.

# STEP 0 — RE-ESTABLISH TRUE STATE (before any edit)
# Trust `main` + `check_docs` over anything written here; if they disagree, `main` wins.
- `git fetch origin`; `git checkout main`; `git reset --hard origin/main`. List open PRs.
- `python3 scripts/check_docs.py` → expect PASS. `python3 -m unittest
  scripts.test_check_docs` → expect the SUITE line **OK**.
- Confirm these EXPECTED TRUTHS (do NOT change until validated):
    - This story = 3.3 = ⬜ (not started), **build tier 10**, Depends-on `3.2`.
    - **Tier transition:** this session advances **tier 9 → 10** (WITHIN P3). Confirm EVERY
      tier-≤9 dependency is ✅ — `3.2` (tier 9) AND its inputs `3.1` + `2.5`.
    - **GATE:** the Validation Debt Register MUST be EMPTY and `3.2` MUST be ✅. If the
      register is non-empty, STOP — the only permitted work is clearing that open entry
      (very likely 3.2's own live pass).
    - Next free RD number: RE-VERIFY (expect RD-036, but confirm).
- Branch off `main` (current HEAD). Branch name: `feature/story-3.3`.

# THIS SESSION'S OBJECTIVE
For one `intake_id` with a `correlation_result`, run the accuracy + gap_analysis synthesis
and record a bounded, verdict-free synthesis RESULT on a contract-first schema, ready for
3.4 (unified threat scoring + prioritized remediations).

# DEFINITION OF DONE (this session) — a PASS/FAIL GATE
1. For one `intake_id`, the synthesis produces a bounded, verdict-free synthesis result
   recorded on the tracking item; a static-only false positive is demonstrably reconciled
   against benign dynamic evidence.
2. Keyed by `intake_id`+`sha256`; if it calls Nova Pro, exponential-backoff retry
   exercised/inspectable + a malformed/absent response RECORDED honestly.
3. EVIDENCE only — no verdict/safe/forward field anywhere; RD-009/RD-013 boundary intact.
4. Validated LIVE and RECORDED.
- Goes ✅ ONLY on a recorded live pass of the FINAL code. No recorded pass → stays 🟡 (and
  3.3 goes on the Validation Debt Register in the same commit). On any fail: stay on 3.3,
  fix, re-validate.

# ENVIRONMENT
- Repo cloned; push to `feature/story-3.3`, never main. Open PRs via
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls` (NOT `gh pr create`). Merges are the
  repo-owner's action. Live AWS is the stakeholder's Hub/Forensic CloudShell action.

# WORKING AGREEMENT
- One story to completion: design → build → validate → RECORD + flip status → paired
  status commit; push to a branch; open a PR. After merge, `git log main..feature/story-3.3`
  to confirm the whole branch landed (base-branch trap).
- Validation drives status; the hard advancement gate governs advancement.
- MANAGEMENT ARTIFACTS ARE FIRST-CLASS (RD-015): brief + RUNBOOK + PROJECT_PLAN aligned;
  the new RD + candidate NIST/ISO mappings recorded; all via PR. **Repoint the
  `check_docs` fixture (`_NEW_WORK_STORY`) off 3.3 in the same PR.** Re-run the doc checks
  AFTER committing any status edit.
- Author a 3.3 LIVE-RUNBOOK for the stakeholder's real validation.
- At session end, author the NEXT story's brief + prompt (3.4 unified threat scoring) with
  THIS session's real Lessons Learned. Zero cold-start.
- If blocked (incl. by the 3.2 gate), push partial progress + a draft PR; surface the
  blocker; never silently fail.
