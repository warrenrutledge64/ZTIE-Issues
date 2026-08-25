# Session Prompt — Story 1.R (executor-facing)

> Generated from `story-1.R-brief.md`. Paste the block below to start the Story
> 1.R working session. It carries the ACTUAL lessons from the 1.1R build session.

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
Story 1.R builds the RESTORE-POINT MECHANISM — the safety net that lets a phase be
closed and reverted to a known-good point.

# NON-NEGOTIABLE CONSTRAINTS
- PYTHON-FIRST tooling. The restore tooling MUST be Python (the user explicitly
  moved it off Bash). Interactive confirm via input(), FAIL-SAFE to NO. No /dev/tty.
- Capture is READ-ONLY. The only mutating action (restore) is behind the confirm gate.
- Verify compares a RESTORE-RELEVANT PROJECTION (identity + desired-state fields),
  NEVER raw resource objects — or volatile metadata will false-positive as drift
  (SSM version bumps, CFN status CREATE vs UPDATE_COMPLETE, last_updated_utc,
  stack_id on recreate, Lambda ordering). Compare: SSM name/type/value/secure;
  CFN name/template_sha256/parameters/TAGS; Lambda name/runtime/code_sha256 (sorted);
  DynamoDB table config projection.
- CloudFormation restore MUST re-apply stack-level TAGS (aws cloudformation deploy
  --tags), not just template+parameters, or the restored stack loses its tags and
  correctly fails the projected verify.
- Per RD-015 the manifest must PIN the known-good governance-doc commit so code +
  state + governance restore as ONE unit.
- AWS-native. VALIDATION-GATED: nothing is "done" on inference — the USER validates
  live and the result is RECORDED in RUNBOOK.md.

# OPERATIONAL CONTEXT (state this on EVERY command block)
  Build sandbox is INTEGRATIONS_ONLY (NO AWS creds; PyPI + npm BLOCKED). You BUILD +
  hand off; the USER runs capture/restore live in CloudShell (ambient creds, no
  --profile) and confirms. Confirm the active account before any operational command.
  Region us-east-1.

# HARD-WON LESSONS (do NOT repeat)
- The earlier Bash restore attempt failed on the interactive /dev/tty confirm,
  CR/whitespace handling, and set -e. Python input() + clean structure avoids all of
  it — that is WHY this is Python. Don't reintroduce a shell gate.
- Verify a PROJECTION, not raw objects (see constraints). Re-apply CFN tags.
- Local proof only: python3 -m py_compile + ~/.pyenv/versions/3.12.13/bin/ruff +
  (prettier via npx --no-install AFTER `unset NODE_OPTIONS`). You CANNOT run pytest/
  cdk/tsc here (PyPI/npm blocked). Do NOT claim live tests/deploy pass from the sandbox.
- If you emit a JSON schema/manifest containing a remote "$schema" URL, fs_write
  refuses it — write it via a `python json.dump` step (as Story 1.1R did).

# FIRST — VALIDATION & ADVANCEMENT GATE (do this BEFORE any new work)
# Binding policy: RUNBOOK.md "Validation & Advancement Gate". Results DRIVE status.
# 1. CLOSE OUT THE PRIOR STORY (1.1R): it was built + on branch feature/story-1.1R
#      (PR open), 🟡 pending the user's live two-account validation. If the user has
#      since confirmed the four DoD checks live, RECORD the dated Validation Result +
#      flip 1.1R 🟡 → ✅ (paired status commit + small PR) BEFORE starting 1.R.
# 2. HARD ADVANCEMENT GATE: 1.R depends on 1.1R. Do NOT start 1.R until 1.1R is ✅
#      (so you capture the FINAL Forensic→Hub topology, not the pre-remediation one).
#      If 1.1R is not yet ✅, STOP and re-focus on getting 1.1R validated.

# WHERE WE ARE (reconfirm via STEP 0 — git pull, list open PRs, no main/PR drift)
- Prior story: 1.1R — durable record → Hub behind the RD-013 contract gate. Built,
  🟡 pending live. Implemented as (RD-016): Forensic intake --sqs:SendMessage--> Hub
  ingest queue --> Hub validator Lambda (enforces schemas/intake-tracking.contract
  .v1.json, fail-closed) --> PASS upsert to Hub tracking DynamoDB / FAIL quarantine
  S3 (+ DLQ). Forensic intake stack now has NO durable DynamoDB.
- Last restore point: none yet (1.R creates the mechanism; the P1 close captures the
  first tag AFTER 1.2/1.3/1.4 route correctly).
- Governing docs: PROJECT_PLAN.md, RUNBOOK.md (source of truth for status),
  RESTORE.md, BOM.md, DOCS/COMPLIANCE.md, and this story's brief:
  session-briefs/story-1.R-brief.md

# THIS SESSION'S OBJECTIVE
Build the Python state-capture + coordinated-restore tooling under scripts/, fill
RESTORE.md + BOM.md for the real deployed ZTIE (Hub durable + infra projections;
Forensic ephemeral is rebuilt not restored), pin the governance-doc commit in the
manifest (RD-015), and get the user to validate a live capture→change→restore cycle.

# SCOPE & GUARDRAILS
- In scope: Python capture (projection) + coordinated restore (re-apply incl. CFN
  tags; input() fail-safe-NO gate); fill RESTORE.md + BOM.md; governance-commit pin.
- Out of scope / do NOT touch: classifier (1.2), routing (1.3), safe-reject (1.4);
  restoring Forensic's ephemeral raw-payload/scratch (disposable). Don't edit the
  intentional {{PROJECT_NAME}} template placeholders.
- Depends on (must already be ✅): 1.1R.

# DEFINITION OF DONE (this session) — a PASS/FAIL GATE
The user, live, confirms ALL of: capture current state → timestamped manifest; make
a trivial deliberate change; coordinated restore back to the manifest; the
restore-relevant PROJECTION matches (no false drift); BOM.md reflects reality; and
the confirm gate fails safe to NO on empty/negative input.
- Goes ✅ ONLY when the user confirms live AND it is RECORDED in RUNBOOK.md.
- If validation FAILS: not done — stay on 1.R, fix, re-validate. Do NOT close Phase 1.

# ENVIRONMENT
- Repo cloned; push to feature/story-1.R (never main). Open/manage PRs via
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls` (NOT `gh pr create`).
- Merging is the repo-owner's action unless told "merge it via API."

# WORKING AGREEMENT
- MANAGEMENT ARTIFACTS ARE FIRST-CLASS (RD-015): keep PROJECT_PLAN ↔ RUNBOOK in
  EXACT alignment; update the 1.R brief; PR-review all docs; the manifest must pin
  the governance-doc commit. Not done until docs are updated + aligned, not just code.
- One story to completion: design → build → USER validates live → RECORD + flip
  status → commit (paired status commit). Push to a branch; open a PR.
- At session end, author the NEXT story's brief + prompt (MANDATORY) with a Lessons
  Learned / Carry-Forward of THIS session's actual lessons. (Next up after 1.R is the
  Phase-1 close prep / Story 1.2 classifier — check the runbook ordering.)
- If blocked, push partial progress + a draft PR; never silently fail.
```
