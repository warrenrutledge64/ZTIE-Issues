# Session Prompt — Story 1.3 (executor-facing)

> Generated from `story-1.3-brief.md`. Paste the block below to start the Story
> 1.3 working session. It carries the ACTUAL lessons from the 1.2 build session.

---

```
You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting. Do NOT change anything until you have (a) READ the
plan + runbook, (b) re-established true state (STEP 0), and (c) confirmed the
advancement gate.

# PROJECT IDENTITY
ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted
artifact BEFORE it reaches the PDE. Three accounts: Pipeline-Hub (641628980935) =
brains/control plane + durable record; Forensic (360999005254) = self-contained
blast zone (ephemeral only); Pipeline-Sandbox (586917955591) = ZTIE→PDE handoff.
Story 1.3 builds the ROUTING TABLE — turn the 1.2 classification label
(iac_template / raw_script / other_unknown) into a routing decision: IaC → the
static IaC-linter lane (and dynamic lane per the architecture); raw script → its
audit / dynamic path; other_unknown → the safe-reject entry (1.4). Wire BOTH
Phase-2 lanes as addressable fork targets.

# NON-NEGOTIABLE CONSTRAINTS
- PYTHON-FIRST. Python 3.12 for the router (project standard).
- ROUTE ON THE CLASS LABEL, never the raw artifact body. The label (1.2) lives on
  the Hub tracking record; cross only DERIVED data (never the raw body out of
  Forensic).
- CONTRACT-FIRST. Define the routing-decision JSON Schema BEFORE the code (the
  1.1R + 1.R + 1.2 lesson — write the shape, the code falls out). Emit it via a
  `python json.dump` step (fs_write refuses files with a remote "$schema" URL);
  write BOTH the canonical schemas/ copy and any bundled lambda copy from one
  source so they can't drift.
- DECLARATIVE TABLE. The routing table is data-driven (class → lane[s]), not a pile
  of if/else, so 1.4 and Phase 2 read cleanly off it.
- ZERO-TRUST BOUNDARY. A routing decision is a PLAN OF WHICH CONTROLS TO APPLY,
  never a safety verdict and never a forward-to-PDE decision. No safe/verdict/
  approved field. The verdict stays Hub-side/human-gated (Phase 4).
- PRODUCTION CODE — real routing + real handling of the unroutable (hand to 1.4,
  never crash). AWS-native. VALIDATION-GATED: nothing is "done" on inference — the
  USER validates live and the result is RECORDED in RUNBOOK.md.

# OPERATIONAL CONTEXT (state this on EVERY command block)
  Build sandbox is INTEGRATIONS_ONLY (NO AWS creds; PyPI + npm BLOCKED). You BUILD +
  hand off; the USER runs the live validation in CloudShell (ambient creds, no
  --profile) and confirms. Confirm the active account before any operational command.
  Region us-east-1.

# HARD-WON LESSONS (do NOT repeat)
- Pure-logic + thin awsio seam = offline stdlib `unittest` (1.2 got 32 tests, 1.R
  got 14 — no PyPI). Keep the routing decision a PURE function over the label; put
  any boto3 behind a thin layer. Add a `try: import jsonschema` conformance test
  that SKIPS offline / RUNS live.
- Local proof only: python3 -m py_compile + ~/.pyenv/versions/3.12.13/bin/ruff +
  (prettier via npx --no-install from infra/ AFTER `unset NODE_OPTIONS`). You CANNOT
  run pytest/boto3/cdk/tsc here. Do NOT claim live tests/deploy pass from the sandbox.
- Ruff default set (hit these in 1.2): PIE810 (merge startswith into a tuple),
  I001 (import order), RUF012 (mutable class attr needs typing.ClassVar), EXE001
  (a #! file must be chmod +x). It does NOT enable E402/PLC0415 and DOES flag
  BLE001 — use `# noqa: BLE001` only for an intentional `except Exception`; don't
  add noqa for non-enabled rules (unused RUF100).
- fs_write refuses a remote "$schema" URL — write the routing-decision schema via
  `python json.dump` (as 1.1R, 1.R, 1.2 did).
- If routing crosses to the Hub it is a THIRD envelope kind on the SAME RD-013
  ingest queue + validator. Extend hub_ingest's `_process_record` router (it already
  routes intake vs classification by envelope kind) and integrity-bind by
  intake_id+sha256 with fail-closed quarantine; expect the label-ordering race and
  reuse the conditional-update-then-GetItem retry-vs-quarantine pattern from 1.2.

# FIRST — VALIDATION & ADVANCEMENT GATE (do this BEFORE any new work)
# Binding policy: RUNBOOK.md "Validation & Advancement Gate". Results DRIVE status.
# 1. CLOSE OUT 1.2 FIRST. 1.2 (preprocessor classifier) is 🟡 pending the user's
#      live validation (PR #17, branch feature/story-1.2; local proof green). Ask
#      the user for the live result. ON PASS: record the dated Validation Result +
#      flip 1.2 ✅ in RUNBOOK.md via a small paired status commit, THEN start 1.3.
#      ON FAIL / NOT YET: 1.2 stays 🟡 and THIS session's objective becomes
#      fix+re-validate 1.2 — do NOT start 1.3.
# 2. ADVANCEMENT GATE: 1.3 depends on 1.2. It cannot begin until 1.2 is ✅. It does
#      NOT depend on 1.R. Do NOT close Phase 1 until 1.2/1.3/1.4 route correctly
#      AND 1.R is ✅ (then capture restore/phase-1-green).

# WHERE WE ARE (reconfirm via STEP 0 — git pull, list open PRs, no main/PR drift)
- Prior stories: 1.1 ✅ (intake gateway, Forensic). 1.1R ✅ (durable record → Hub
  behind the RD-013 contract gate). 1.R ✅ (restore mechanism, PR #15/#16). 1.2 🟡
  (classifier built, PR #17 OPEN on feature/story-1.2, awaiting live validation).
- What 1.2 added: `lambdas/preprocessor/` (classifier.py PURE + awsio.py thin seam +
  handler.py S3-ObjectCreated Lambda) emitting a DERIVED label-only envelope to the
  Hub ingest queue; `schemas/classification.contract.v1.json` (+ bundled copy in
  lambdas/hub_ingest/); hub_ingest now routes by envelope kind and applies the label
  with an integrity-bound conditional update_item (never creates a record, never
  touches status/verdict), grantReadWriteData for the GetItem disambiguation. CDK:
  preprocessor Lambda + S3 trigger in ztie-intake-stack.ts (outputs
  PreprocessorFunctionName/PreprocessorRoleArn); forensicPreprocessorRoleArn on the
  Hub stack. The label lands on the Hub tracking record as `artifact_class` +
  `classification` keyed by intake_id.
- Deployed P1 resources: Hub `ZtieHubTrackingStack` (tracking DynamoDB, ingest SQS
  + DLQ, validator Lambda, quarantine S3); Forensic `ZtieIntakeStack` (intake API +
  Lambda, artifact S3, preprocessor Lambda). Last restore point: none yet (captured
  at the P1 close, after 1.2/1.3/1.4 + ✅ 1.R).
- CloudShell operator truths: run commands ONE LINE AT A TIME (a multi-line paste
  into input() was the 1.R "typed y but aborted"); /tmp is wiped on session recycle
  (regenerate exported files); state the account banner + `aws sts get-caller-identity`
  before any operational command.
- Governing docs: PROJECT_PLAN.md, RUNBOOK.md (source of truth for status),
  RESTORE.md, BOM.md, docs/COMPLIANCE.md, and this story's brief:
  session-briefs/story-1.3-brief.md

# THIS SESSION'S OBJECTIVE
Build the routing table: a pure Python 3.12 function over the classification label
that maps each class to its downstream lane(s), a routing-decision contract
(schema-first), and the fork wiring that makes BOTH Phase-2 lanes addressable
targets and hands other_unknown to 1.4's entry. Get the user to validate live that
each classified type routes to the correct lane and the unroutable is handed off
(not crashed).

# SCOPE & GUARDRAILS
- In scope: routing table + routing-decision contract (schema-first) + fork wiring
  to addressable lane targets; hand-off of other_unknown to 1.4's entry; unit tests
  (stdlib unittest, offline-provable).
- Out of scope / do NOT touch: the safe-reject implementation (1.4 — only hand off
  to it), any actual scanning/detonation (Phase 2 — define fork targets, don't build
  lanes), re-opening the classifier (1.2) or the Hub contract gate (1.1R) beyond
  what routing needs. Don't edit intentional {{...}} template placeholders.
- Depends on (must already be ✅): 1.2.

# DEFINITION OF DONE (this session) — a PASS/FAIL GATE
The user, live, confirms: each classified artifact lands in the correct downstream
lane — IaC-template → static IaC-linter lane [+ dynamic lane per architecture],
raw-script → its audit / dynamic path, other_unknown → the safe-reject entry (1.4),
recorded/queryable by intake_id.
- Goes ✅ ONLY when the user confirms live AND it is RECORDED in RUNBOOK.md.
- If validation FAILS: not done — stay on 1.3, fix, re-validate.

# ENVIRONMENT
- Repo cloned; push to feature/story-1.3 (never main). Open/manage PRs via
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls` (NOT `gh pr create`).
- Merging is the repo-owner's action unless told "merge it via API."

# WORKING AGREEMENT
- MANAGEMENT ARTIFACTS ARE FIRST-CLASS (RD-015): keep PROJECT_PLAN ↔ RUNBOOK in
  EXACT alignment; update the 1.3 brief; PR-review all docs. Not done until docs
  are updated + aligned, not just code.
- One story to completion: design → build → USER validates live → RECORD + flip
  status → commit (paired status commit). Push to a branch; open a PR.
- At session end, author the NEXT story's brief + prompt (MANDATORY) with a Lessons
  Learned / Carry-Forward of THIS session's actual lessons. (Next up after 1.3 is
  Story 1.4 safe-reject — check the runbook ordering.)
- If blocked, push partial progress + a draft PR; never silently fail.
```
