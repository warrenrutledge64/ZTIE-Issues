# Story 3.4

You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting. Do NOT change anything until you have (a) READ the
plan + runbook + methodology + this story's brief (`session-briefs/story-3.4-brief.md`),
(b) re-established true state (STEP 0), and (c) confirmed the Validation Debt Register
state + advancement gate.

# PROJECT IDENTITY
ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted artifact
BEFORE it reaches the PDE. Work is validation-gated: nothing is ✅ until a recorded live
pass (the covenant). Three accounts: Pipeline-Hub (641628980935) = brains/control plane
+ durable record; Forensic (360999005254) = self-contained blast zone (ephemeral only);
Pipeline-Sandbox (586917955591) = ZTIE→PDE handoff. Story 3.4 is the unified-scoring step
of Phase 3: it turns the ONE verdict-free `synthesis_result` (Story 3.3, RD-037) for an
artifact into a single unified threat SCORE + detailed findings + prioritized
remediations — still evidence-only; the enforcement VERDICT is Story 3.5.

# WHERE THIS STORY SITS — BUILD TIER 11, ADVANCING FROM TIER 10 (WITHIN P3)
Story 3.4 is **build tier 11** and this session **ADVANCES from tier 10 to tier 11**: its
tier-10 dependency `3.3` (accuracy + gap_analysis synthesis) goes ✅, so a NEW dependency
layer opens. This is a tier move WITHIN Phase 3 (NO phase transition). Because this is a
tier advance, STEP 0 must re-confirm the ENTIRE new dependency set is ✅ (`3.3` AND its
input `3.2`), not merely glance at the prior story.

# ⚠️ ADVANCEMENT GATE — CHECK THIS FIRST
NEW FEATURE story. It may begin ONLY if its Depends-on are ALL ✅ AND the Validation Debt
Register is EMPTY. **As of this prompt's authoring, Story 3.3 was BUILT but sits 🟡 on the
Validation Debt Register awaiting its recorded LIVE pass (a Hub run that reconciles a
static-only false positive). So the gate is expected ARMED until 3.3 is validated live**
(see `session-briefs/story-3.3-LIVE-RUNBOOK.md`). STEP 0 MUST re-confirm on `main`: `3.3`
✅ and the Validation Debt Register EMPTY (trust `main` + `check_docs` over this prompt; if
they disagree, `main` wins). **If 3.3 is still 🟡, 3.4 MAY NOT begin — the only permitted
work is validating/reworking 3.3.** This is `check_docs` CHECK B, machine-enforced.
Depends-on: **3.3 ✅**. Build tier 11.

# WHERE 3.4 SITS (what already exists that it builds on)
By the time 3.4 begins, the Hub tracking record for one `intake_id` carries the Story 3.3
`synthesis_result` (RD-037, `synthesis.contract.v1`, own pin `SYNTHESIS_CONTRACT_VERSION`),
written Hub-side by the synthesizer (`lambdas/hub_synthesize/`, DynamoDB-stream-triggered).
Its shape (what 3.4 reads):
- top level: `contract_version`/`intake_id`/`sha256`/`synthesized_at`/`status`
  (`synthesized`/`no_correlation`/`skipped_no_findings`) + optional `status_detail`/
  `correlation_status`/`correlation_contract_version`/`source_finding_count`/
  `combined_complete`/`truncated`;
- only when `status: synthesized`: a `synthesis` object — `summary`, an `accuracy` block
  (`accuracy_score` 0-100, `confirmed_correlation_count`, `candidate_false_positive_count`,
  `static_only_count`/`dynamic_only_count`/`contradiction_count`,
  `candidate_false_positives[]`), and a `gaps` block (`gap_count`, `highest_gap_severity`,
  `items[]` each `gap_type` ∈ static_uncorroborated/dynamic_unexplained/contradiction/
  coverage + `severity`/`title`/refs).
It is EVIDENCE only — there is NO verdict field anywhere, and 3.4 must NOT introduce one.
3.4 should tolerate `status != synthesized` (score honestly over an absent/errored
synthesis — record it, never fabricate).

# THE JOB
For one `intake_id` with a `synthesis_result`, produce: (a) ONE **unified threat SCORE**
(define the scale explicitly — a bounded EVIDENCE risk score, e.g. 0-100, NOT a verdict),
(b) a detailed **findings** view, and (c) a **prioritized remediation** list (ranked by
severity/impact). Record a bounded, DERIVED, verdict-free scoring RESULT on the tracking
item. Decide CONTRACT-FIRST whether this is PURE post-processing of the 3.3 synthesis
(very likely — see below) or a Nova Pro call — and justify it in the new RD.

# CONTRACT-FIRST DECISION (make + justify in the new RD)
The synthesis result ALREADY lives on the Hub tracking record and is fully structured
(scores, counts, categorized candidate-FPs + gaps with severities). So 3.4 is very likely
**PURE Hub-side post-processing** (read the synthesis result → compute a unified score +
rank remediations → write the scoring result back onto the same record), NOT a model call
and NOT a new Forensic→Hub crossing — mirroring 3.3's placement + "prefer PURE" reasoning
(RD-037: once the evidence is structured, the downstream step is deterministic
aggregation, not a model call; keeps RD-009/RD-013 intact, no Forensic durable store per
RD-012, and needs no Bedrock grant). Decide this CONTRACT-FIRST: define the scoring-result
schema (bounded, verdict-free, allow-list, own version pin), define the SCORE SCALE
explicitly (an evidence risk score, never a verdict), decide WHERE it runs + whether it
calls the model, and justify it in the RD. If it hangs off the tracking-table stream,
reuse the 3.1/3.2/3.3 idempotency + call-storm guard (a content fingerprint over the
`synthesis_result`, `Decimal`-canonicalized) so it fires once per settled synthesis.

# NON-NEGOTIABLE CONSTRAINTS
- SCORE, do not re-synthesize/re-correlate/re-normalize/re-capture/re-sanitize. The input
  is 3.3's synthesis result; 3.3/3.2/3.1/2.5/2.4 are done — do not re-litigate them.
- EVIDENCE, NEVER A VERDICT. The scoring result has NO verdict/safe/approved/forward/
  malicious/pass_fail/clean field, and the unified SCORE is an EVIDENCE risk metric, not a
  decision (a high score is not "FAIL"; a low score is not "PASS"). The PASS/FAIL/
  INCONCLUSIVE verdict is Story 3.5, human-gated.
- REAL MODEL CALL + EXPONENTIAL-BACKOFF RETRY (RD-003) ONLY IF you decide it calls Nova
  Pro (prefer PURE, per RD-037). No mock model. Tolerate a malformed/absent/oversized
  response — RECORD it honestly (a `status`), never fabricate.
- BOUNDED IN + BOUNDED OUT. Reason ONLY over the bounded 3.3 synthesis result (and, if
  needed, the 3.2 correlation it references — no raw data, RD-009); the result schema is
  allow-list, typed + bounded, arrays maxItems-capped.
- PURE LOGIC + THIN SEAM (the proven 1.2→…→3.3 pattern). Scoring logic is PURE +
  offline-testable; any DynamoDB (or, if used, Bedrock) I/O is behind a thin per-lane
  `awsio` seam.
- VALIDATION-GATED, NEVER ON INFERENCE: 3.4 flips ✅ only on a recorded LIVE pass of the
  FINAL code (ONE unified score + ranked findings + prioritized remediations emitted for a
  real run).
- DOCS FIRST-CLASS (RD-015): PR-reviewed, never straight to main; PROJECT_PLAN ↔ RUNBOOK
  in EXACT alignment.

# NEW REGISTERED DECISION
Record the scoring design as a new RD with rationale + candidate NIST/ISO mappings.
RE-VERIFY the next free RD number at STEP 0 with
`grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md | sort -u | tail` (RD-037 is 3.3's; **expect
RD-038, but VERIFY — RD-number collisions HAVE happened: 3.3 expected RD-036 but it was
already taken by G-4, so 3.3 used RD-037. RD-017 is a historical gap.** Take the next
genuinely-free number).

# OPERATIONAL CONTEXT (state this on EVERY command block)
  Build sandbox is INTEGRATIONS_ONLY (NO AWS creds; PyPI + npm BLOCKED — boto3/pytest/
  moto/jsonschema/aws-cdk-lib NOT installable). You BUILD; the USER validates live in
  CloudShell (ambient creds, no --profile). Region us-east-1. Confirm the active account
  with `aws sts get-caller-identity` before EVERY operational block. The tracking table +
  the scoring compute (if Hub-side) are in the HUB (641628980935). If — and only if — you
  decide 3.4 calls Nova Pro, Bedrock model access must be ENABLED for the Hub account (or
  the first call fails AccessDenied); if 3.4 is PURE (recommended), there is NO Bedrock
  prerequisite. Tooling: repo default `python3` is 3.9 — run your tests with
  `~/.pyenv/versions/3.12.13/bin/python3`; `ruff` is at `~/.pyenv/versions/3.12.13/bin/ruff`
  (repo has NO ruff config → DEFAULT rules; watch RUF100 — do NOT add a `# noqa` for a
  non-enabled rule like E402; and ISC004 — wrap implicit string concatenation inside a
  list in parentheses; both bit the 3.3 build; a blind `except Exception` that does NOT
  re-raise needs `# noqa: BLE001`); `prettier`/`tsc` need `env -u NODE_OPTIONS`; npm
  registry is BLOCKED so `tsc --noEmit` shows ONLY the missing-`aws-cdk-lib` family
  (TS2304/2307/2339/2353/2591) — confirm the new stack adds NO new error TYPE (compare the
  error-TYPE set against `main`'s baseline; a count delta in an existing type is fine). Do
  NOT prettier-reformat the generated JSON contracts (breaks no-drift). Keep your own tests
  stdlib-only + boto3-stubbed so they pass offline.

# HARD-WON LESSONS (do NOT repeat)

## The derived pattern (held 8× now: 1.2→2.2→2.3→2.4→2.5→3.1→3.2→3.3)
Contract-first + a bounded allow-list record with its OWN version pin + PURE logic + a
thin `awsio` seam + evidence-never-verdict + a two-layer conformance test (stdlib
pure-Python walk + a jsonschema `skipUnless` live layer) + a recursive no-verdict-key scan
+ a schema-has-no-verdict-property check. Reuse it for 3.4's scoring-result record.

## 3.3 was PURE post-processing (RD-037) — the precedent for 3.4
3.3's input (the 3.2 `correlation_result`) already carried the model's DISCRETE structured
findings, so accuracy + gap_analysis were deterministic aggregations over the finding
`kind` enum — NO second Nova Pro call, NO Bedrock client, NO Bedrock grant (a second call
would only add cost / non-determinism / verdict-injection risk / non-reproducibility).
3.4's input (the `synthesis_result`) is likewise fully structured Hub-side data — the SAME
"prefer PURE" reasoning very likely applies. If you nonetheless decide to call Nova Pro,
justify WHY in the RD and reuse the 3.2 `awsio.invoke_nova` pattern (real exponential-
backoff + full jitter, bounded `max_attempts`, returns the attempt count so the retry is
inspectable; parse DEFENSIVELY; a malformed/absent response is RECORDED via a `status`,
never fabricated; the prompt must NOT ask for a verdict; scope `bedrock:InvokeModel` to
EXACTLY the Nova Pro model/profile ARNs, never `*`).

## C.3 contract-gen workflow (unchanged)
Add a NEW `scripts/gen_<name>_contract.py` (SCHEMA dict + module-level `OUT_PATHS` segment
tuples + a `main()` delegating to `contract_writer.{resolve_out_paths,write_contract}`),
register it in `gen_contracts.py`'s `CONTRACT_MODULES`, and **`chmod +x` it** (the others
are executable; ruff EXE001 fires on a shebang'd non-executable). Prove no-drift with
`git diff -- schemas lambdas` after regenerating; confirm the two copies are byte-identical.

## RD-number collision is real
3.3 expected RD-036 but it was already taken by G-4, so 3.3 used RD-037. ALWAYS
`grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md | sort -u | tail` on CURRENT main and take the
next genuinely-free number (expect RD-038, but CONFIRM).

## check_docs self-test fixture drift
`scripts/test_check_docs.py` pins `_NEW_WORK_STORY` to a downstream ⬜ master-table story.
It is currently pinned to **3.4** (repointed from 3.3 when 3.3 went 🟡). **When 3.4 leaves
⬜ (i.e. THIS story starts/finishes), repoint `_NEW_WORK_STORY` to the next still-⬜
feature story (e.g. 3.5) IN THE SAME PR**, then re-run `python3 -m unittest
scripts.test_check_docs` and confirm the SUITE line is **OK** (the `check_docs: FAIL …`
lines it prints while exercising itself are expected — the SUITE `OK` vs `FAILED
(failures=N)` line is what matters).

## check_docs timing (RD-015)
Run `python3 scripts/check_docs.py` only AFTER committing any status/register edit (CHECK
B's baseline is `git show HEAD:RUNBOOK.md`; running before the commit gives a
FALSE-POSITIVE). Set 3.4 🟡 AND add it to the Validation Debt Register in the SAME commit
(CHECK A requires every 🟡 feature story to be on the register; CHECK B allows a story
that is IN the register). Also run `python3 -m unittest scripts.test_check_docs`.

## Deploy-gap (if 3.4 touches any Lambda) — TWO failure modes, both silent
If 3.4 is Hub-side, the redeploy is `ZtieHubTrackingStack`. (1) Stack not redeployed → old
code still live. (2) Redeployed from the WRONG git checkout → green `UPDATE_COMPLETE`
ships STALE code. GUARD: BEFORE deploy `git rev-parse --abbrev-ref HEAD && git log
--oneline -1` AND `grep` the new marker in the stack source; AFTER deploy inspect the LIVE
resource (`aws lambda get-function-configuration ... --query Environment.Variables`) and
confirm the new env/behavior is present. When a call "succeeds" but produces no result,
READ THE LAMBDA'S OWN LOGS.

## Two accounts, two tabs
`aws sts get-caller-identity` before EVERY block. Tracking table = HUB; a
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
    - This story = 3.4 = ⬜ (not started), **build tier 11**, Depends-on `3.3`.
    - **Tier transition:** this session advances **tier 10 → 11** (WITHIN P3). Confirm
      EVERY tier-≤10 dependency is ✅ — `3.3` (tier 10) AND its input `3.2`.
    - **GATE:** the Validation Debt Register MUST be EMPTY and `3.3` MUST be ✅. If the
      register is non-empty, STOP — the only permitted work is clearing that open entry
      (very likely 3.3's own live pass).
    - Next free RD number: RE-VERIFY (expect RD-038, but confirm — collisions have happened).
- Branch off `main` (current HEAD). Branch name: `feature/story-3.4`.

# THIS SESSION'S OBJECTIVE
For one `intake_id` with a `synthesis_result`, produce ONE unified threat score + detailed
findings + prioritized remediations, recorded as a bounded, verdict-free scoring RESULT on
a contract-first schema, ready for 3.5 (verdict derivation).

# DEFINITION OF DONE (this session) — a PASS/FAIL GATE
1. For one `intake_id`, the scoring produces a bounded, verdict-free result with ONE
   unified threat score + detailed findings + a prioritized remediation list, recorded on
   the tracking item.
2. Keyed by `intake_id`+`sha256`; the score scale is an explicit EVIDENCE risk metric (not
   a verdict); tolerates `status != synthesized` honestly.
3. EVIDENCE only — no verdict/safe/forward field anywhere; RD-009/RD-013 boundary intact.
4. Validated LIVE and RECORDED.
- Goes ✅ ONLY on a recorded live pass of the FINAL code. No recorded pass → stays 🟡 (and
  3.4 goes on the Validation Debt Register in the same commit). On any fail: stay on 3.4,
  fix, re-validate.

# ENVIRONMENT
- Repo cloned; push to `feature/story-3.4`, never main. Open PRs via
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls` (NOT `gh pr create`). Merges are the
  repo-owner's action. Live AWS is the stakeholder's Hub CloudShell action.

# WORKING AGREEMENT
- One story to completion: design → build → validate → RECORD + flip status → paired
  status commit; push to a branch; open a PR. After merge, `git log main..feature/story-3.4`
  to confirm the whole branch landed (base-branch trap).
- Validation drives status; the hard advancement gate governs advancement.
- MANAGEMENT ARTIFACTS ARE FIRST-CLASS (RD-015): brief + RUNBOOK + PROJECT_PLAN aligned;
  the new RD + candidate NIST/ISO mappings recorded; all via PR. **Repoint the
  `check_docs` fixture (`_NEW_WORK_STORY`) off 3.4 in the same PR.** Re-run the doc checks
  AFTER committing any status edit.
- Author a 3.4 LIVE-RUNBOOK for the stakeholder's real validation.
- At session end, author the NEXT story's brief + prompt (3.5 verdict derivation) with
  THIS session's real Lessons Learned. Zero cold-start.
- If blocked (incl. by the 3.3 gate), push partial progress + a draft PR; surface the
  blocker; never silently fail.
