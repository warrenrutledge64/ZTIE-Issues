Story C.3

You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting. Do NOT change anything until you have (a) READ the
plan + runbook + methodology + this story's brief (`session-briefs/story-C.3-brief.md`),
(b) re-established true state (STEP 0), and (c) confirmed the Validation Debt Register
state + that A.4 is ✅.

# PROJECT IDENTITY
ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted artifact
BEFORE it reaches the PDE. Work is validation-gated: nothing is ✅ until a recorded pass
of the FINAL code (the covenant). Three accounts: Pipeline-Hub (641628980935) =
brains/control plane + durable record; Forensic (360999005254) = self-contained blast
zone (ephemeral only); Pipeline-Sandbox (586917955591) = ZTIE→PDE handoff. Story C.3 is a
**Floor & Harvest REFACTOR** — it pays down the single most-compounded piece of
duplication in the codebase without changing any behaviour.

# WHERE THIS STORY SITS — BUILD TIER 6, F&H TRACK (no phase, no tier advance for the pipe line)
C.3 is an `F&H`-track story at build tier 6 (depends on `A.4` ✅, tier 5). It does NOT
advance the pipe line to a new tier and it gates NO phase transition — it rides on the
already-open Floor & Harvest floor. Like `G-` governance stories, F&H stories are NOT
blocked by the advancement gate the way *pipe* features are; but STEP 0 must still confirm
`A.4` is ✅ and the Validation Debt Register is EMPTY on `main` before starting.

# ⚠️ NATURE OF THIS WORK — BEHAVIOUR-PRESERVING REFACTOR
This is NOT a feature. C.3 changes NO runtime behaviour and NO contract SCHEMA bytes. Its
entire success criterion is: same behaviour, same contract output (hash-matched), less
duplication. If the refactor moves ONE contract byte or changes ONE handler's behaviour,
it has FAILED. Prove no-drift; do not "improve" anything while you are in there.

# WHERE C.3 SITS (what exists that it consolidates)
On current `main` two patterns are copy-pasted:
- **`awsio.py` is hand-copied 6×:** `lambdas/preprocessor/awsio.py`,
  `lambdas/static_scan/awsio.py`, `lambdas/detonation/awsio.py`,
  `lambdas/collector/awsio.py`, `lambdas/hub_normalize/awsio.py`, and
  `scripts/ztie_restore/awsio.py`. Each is a thin boto3 seam (S3 / SQS / DynamoDB / EC2 /
  SSM / bedrock-runtime wrappers) + the Hub-gate envelope-kind SEND helpers
  (`send_*_envelope`). 3.1 added the 6th copy — the tax compounds every pipe story.
- **The Hub-gate apply/dispatch pattern** (`lambdas/hub_ingest/`) validates + integrity-
  binds + applies each envelope KIND (`_apply_*`) — a repeated shape, one per kind.
- **10 bespoke contract generators:** `scripts/gen_*_contract.py` (behavior,
  classification, collected, combined_event, dynamic_run, reject, routing,
  sanitized_telemetry, static_findings, static_scan_summary) — all emit a JSON Schema in
  the same shape from per-contract parameters.
C.3 collapses these: ONE importable shared seam/gate module the Lambdas (+ ztie_restore)
import, and ONE parameterized generator whose output is BYTE-IDENTICAL to each bespoke
generator's committed schema.

> **Do NOT conflate the two C.3 scopes.** This C.3 is the **Python** seam + generator
> collapse (dependency: A.4 only). It is DISTINCT from the CDK L3 construct-library chain
> (B.1 → C.1 → C.2 → C.4 → C.5 standing up `infra-building-blocks`). This session is
> Python code-hygiene, not the CDK archive; do not start the archive here.

# THE JOB
1. **Shared `awsio` + Hub-gate module.** Extract the duplicated boto3 seam AND the
   Hub-gate envelope-kind dispatch/apply pattern into ONE importable module. Repoint all 6
   `awsio.py` copies + `scripts/ztie_restore` + the `hub_ingest` dispatch to it. Each
   Lambda's PUBLIC seam surface + behaviour stays unchanged (thin per-Lambda wrappers may
   remain for legibility; the shared logic lives once).
2. **One parameterized generator.** Replace the 10 `scripts/gen_*_contract.py` with ONE
   generator driven by a per-contract parameter table (name, version-pin env var,
   discriminator, field set). It must regenerate every contract schema BYTE-FOR-BYTE
   identical to the committed one (prove by hash).

# CONTRACT-FIRST DECISION (make + justify in the new RD)
Decide WHERE the shared module lives so every Lambda's bundler includes it AND
`scripts/ztie_restore` can import it (a `lib/`-style importable package, or a shared path
the CDK bundling command copies into each Lambda asset — decide against how the stacks
ACTUALLY bundle each Lambda today). Justify the placement + the generator-parameterization
design in the new RD. The shared module must NOT change any contract's schema, any
envelope's on-the-wire shape, or any handler's behaviour.

# NON-NEGOTIABLE CONSTRAINTS
- BEHAVIOUR-PRESERVING, PROVEN. The refactor changes NO runtime behaviour and NO contract
  bytes. Prove it three ways before flipping ✅: (1) regenerate EVERY contract with the new
  single generator and confirm each output hash equals the committed schema's hash (ZERO
  drift); (2) the two-layer contract-conformance tests stay green; (3) each Lambda handler
  + its public `awsio` surface is unchanged.
- NO SCOPE CREEP. Do NOT change a contract schema, add a field, "clean up" a handler, or
  touch verdict/boundary logic while refactoring. The Hub-gate apply must stay integrity-
  bound (record exists AND sha256 matches) and NEVER touch status/verdict — exactly as
  today. EVIDENCE-only crossings stay evidence-only.
- BUNDLING IS REAL (deploy-gap sibling). The shared module MUST be in every Lambda's
  deploy bundle and importable by `scripts/ztie_restore`. A module that passes offline but
  isn't bundled fails at runtime with `ModuleNotFoundError`. If a live no-op redeploy is
  used to prove the bundle, verify the LIVE Lambda imports the shared code.
- PURE LOGIC + THIN SEAM (the proven 1.2→…→3.1 pattern) preserved — you are consolidating
  the seam, not dissolving the pure/seam split.
- VALIDATION-GATED, NEVER ON INFERENCE: C.3 flips ✅ only on a recorded pass of the FINAL
  code (the offline no-drift proof + green proof bar; plus a recorded live no-op redeploy
  if used to prove bundling).
- DOCS FIRST-CLASS (RD-015): PR-reviewed, never straight to main; PROJECT_PLAN ↔ RUNBOOK
  in EXACT alignment.

# NEW REGISTERED DECISION
Record the shared-seam + one-generator design as a new RD with rationale + candidate
NIST/ISO mappings (SA-15 / CM-2 / PR.IP-2 / A.8.32 are the brief's proposed set). RE-VERIFY
the next free RD number at STEP 0 with `grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md | sort -u
| tail` and take the next free number (highest is RD-033; expect RD-034, but VERIFY —
RD-number collisions have happened, and RD-017 is a historical gap).

# OPERATIONAL CONTEXT (state this on EVERY command block)
  Build sandbox is INTEGRATIONS_ONLY (NO AWS creds; PyPI + npm BLOCKED — boto3/pytest/
  moto/jsonschema/aws-cdk-lib NOT installable). You BUILD + prove offline; the USER (if a
  live no-op redeploy is used) validates in CloudShell (ambient creds, no --profile),
  region us-east-1, `aws sts get-caller-identity` before EVERY operational block. The
  Lambdas span the HUB (641628980935: hub_ingest, hub_normalize) and FORENSIC (360999005254:
  preprocessor, static_scan, detonation, collector) — TWO CloudShell tabs if a live step
  touches both. Tooling: `ruff` is NOT on PATH — use `~/.pyenv/versions/3.12.13/bin/ruff`;
  `prettier` and `npx tsc` need `env -u NODE_OPTIONS`; npm is BLOCKED so `tsc --noEmit`
  legitimately shows ONLY the missing-`aws-cdk-lib` error family (TS2307/2339/2353/2591/
  2304) identical across all stacks — confirm the refactor adds NO NEW error TYPE. NOTE the
  repo's default `python3` is 3.9; keep the shared module + tests stdlib-only + boto3-
  stubbed so they pass offline (existing moto-based `test_handler.py` in `hub_ingest`/
  `intake` FAIL to import offline — that is pre-existing, not your regression).

# HARD-WON LESSONS (do NOT repeat)

## Prove no-drift with contract HASHES, not eyeballing
The whole risk is silent drift. Regenerate every contract with the ONE new generator and
compare each output's hash to the committed schema's hash — they MUST match exactly. A
generator that emits semantically-equal-but-byte-different JSON (key order, whitespace,
trailing newline) is a FAIL for this story: match the existing generators' serialization
exactly (same `json.dumps` args, sort, indent, newline). Keep/extend the two-layer
conformance tests (stdlib pure-Python walk + a jsonschema `skipUnless` live layer + the
recursive no-verdict-key scan + the schema-has-no-verdict-property check).

## Bundling / import path (deploy-gap sibling) — the top runtime risk
Each Lambda bundles its own directory today. A shared module that isn't copied into every
Lambda's asset bundle passes offline tests and then throws `ModuleNotFoundError` at
runtime. Decide the shared location against how the CDK stacks ACTUALLY bundle each Lambda
(read the `*-stack.ts` bundling/asset code). If a live no-op redeploy is used to prove it,
AFTER deploy inspect the LIVE Lambda (invoke a benign path / read logs) to confirm it
imports the shared code — never trust a green `UPDATE_COMPLETE` alone (the 2.5/2.6
deploy-gap lessons: green deploy of stale/wrong code, and green SFN branch over an errored
lane — always read the resource's OWN logs).

## Keep the security-relevant seam behaviour identical
The Hub-gate `_apply_*` path is integrity-bound (record exists AND sha256 matches) and
NEVER touches status/verdict; the `send_*_envelope` helpers cross bounded, verdict-free,
allow-list envelopes only. Consolidating them must not relax any of that. Diff the
behaviour, not just the line count.

## F&H stories and the advancement gate
F&H stories are exempt from CHECK B the way `G-` stories are, so C.3 may proceed with the
register empty even though it is not a pipe feature. But STEP 0 still confirms A.4 ✅ + an
empty register on `main`. Trust `main` + `check_docs` over any doc text; if they disagree,
`main` wins.

## Do NOT touch the check_docs fixture pin
`scripts/test_check_docs.py` pins `_NEW_WORK_STORY` to the next ⬜ *pipe* story (currently
**3.2**). A C.3 (F&H) close does NOT move it — leave it alone. (Contrast a pipe story,
which repoints it.) Still run `python3 -m unittest scripts.test_check_docs` after any
status edit and confirm the SUITE line **OK** (the `check_docs: FAIL …` prints are the
checker exercising itself — the SUITE `OK` vs `FAILED (failures=N)` line is what matters;
suite is currently OK / 8 tests — assert on `OK`, not a fixed count).

## check_docs timing (RD-015)
Run `python3 scripts/check_docs.py` only AFTER committing any status/register edit (CHECK
B's baseline is `git show HEAD:RUNBOOK.md`; running before the commit gives a
FALSE-POSITIVE). It should PASS before and after (C.3 is F&H; if C.3 lands 🟡 it goes on
the register in the same commit and CHECK A will then require it there).

## PR mechanics
`gh pr create` is BROKEN — open PRs via `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`.
Push to a branch, never main; merges are the repo-owner's action.

# STEP 0 — RE-ESTABLISH TRUE STATE (before any edit)
# Trust `main` + `check_docs` over anything written here; if they disagree, `main` wins.
- `git fetch origin`; `git checkout main`; `git reset --hard origin/main`. List open PRs.
- `python3 scripts/check_docs.py` → expect PASS (exit 0). `python3 -m unittest
  scripts.test_check_docs` → expect the SUITE line **OK** (the `check_docs: FAIL …` lines
  are the checker testing ITSELF against fixtures — not real failures).
- Confirm these EXPECTED TRUTHS (do NOT change until validated):
    - This story = C.3 = ⬜ (not started), `F&H` track, **build tier 6**, Depends-on `A.4`.
    - G-3 is ✅ (closed 2026-09-12); A.4 is ✅; the Validation Debt Register is EMPTY.
    - The duplication is real on `main`: `find . -name awsio.py -not -path '*/node_modules/*'`
      → 6 copies; `ls scripts/gen_*_contract.py` → 10 generators.
    - Next free RD number: RE-VERIFY (expect RD-034).
- Branch off `main` (current HEAD). Branch name: `feature/story-C.3`.

# THIS SESSION'S OBJECTIVE
Collapse the 6× `awsio`/Hub-gate duplication into ONE importable shared module (all
call-sites repointed, behaviour + public surface unchanged, bundling correct) and the 10
bespoke contract generators into ONE parameterized generator (output byte-identical /
hash-matched to the committed schemas). Zero functional change; green offline proof bar.

# DEFINITION OF DONE (this session) — a PASS/FAIL GATE
1. ONE shared `awsio`+Hub-gate module imported by all 6 former copies (+ `scripts/
   ztie_restore` + the `hub_ingest` dispatch); each Lambda's public seam + behaviour
   unchanged; the shared module is in every Lambda's deploy bundle (bundling verified).
2. ONE parameterized generator replaces the 10 bespoke ones and regenerates BYTE-IDENTICAL
   (hash-matched) contract schemas — zero drift proven.
3. No contract SCHEMA bytes moved; no behaviour changed; the Hub-gate apply stays
   integrity-bound and never touches status/verdict; evidence-only crossings stay so.
4. Offline proof bar green: contract-conformance tests pass; `ruff` clean; `prettier`
   clean; `tsc` adds NO new error type. If a live no-op redeploy is used to prove
   bundling, it is RECORDED.
- Goes ✅ ONLY on a recorded pass of the FINAL code. No recorded pass → stays 🟡 (and C.3
  goes on the Validation Debt Register in the same commit). On any fail: stay on C.3,
  fix, re-validate. Do NOT touch `_NEW_WORK_STORY`.

# ENVIRONMENT
- Repo cloned; push to `feature/story-C.3`, never main. Open PRs via
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls` (NOT `gh pr create`). Merges are the
  repo-owner's action. Any live no-op redeploy is the stakeholder's CloudShell action.

# WORKING AGREEMENT
- One story to completion: design → refactor → prove no-drift → RECORD + flip status →
  paired status commit; push to a branch; open a PR. After merge,
  `git log main..feature/story-C.3` to confirm the whole branch landed (base-branch trap).
- Validation drives status; a refactor is proven (hashes + green tests), never inferred.
- MANAGEMENT ARTIFACTS ARE FIRST-CLASS (RD-015): brief + RUNBOOK + PROJECT_PLAN aligned;
  the new RD + candidate NIST/ISO mappings recorded; all via PR. Do NOT touch
  `_NEW_WORK_STORY` (it pins the next ⬜ *pipe* story, 3.2). Re-run the G-3 doc checks
  AFTER committing any status edit; place `restore/shared-seam-green` on the validated
  commit (owner action).
- If a live no-op redeploy is used to prove bundling, author a short C.3 LIVE-RUNBOOK for
  the stakeholder (which stack(s), the deploy-gap guards, and the LIVE-import verification).
- At session end, author the NEXT story's brief + prompt — the default next Ready item is
  **3.2 (Nova Pro correlation)** on the pipe track (its brief + prompt already exist —
  refresh them with THIS session's real Lessons Learned), unless the stakeholder pulls the
  CDK archive chain (B.1 →) forward. Zero cold-start.
- If blocked, push partial progress + a draft PR; surface the blocker; never silently fail.
