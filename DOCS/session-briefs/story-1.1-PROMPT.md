# Session Prompt — Story 1.1 (executor-facing)

> Generated from `story-1.1-brief.md`. Paste the block below to (re)start the
> Story 1.1 working session.

---

```
You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting.

# PROJECT IDENTITY
ZTIE is a four-phase security-analysis pipeline that inspects every deployment
payload / code artifact BEFORE it can reach production (the Platform Delivery
Engine). Nothing is trusted by default. Story 1.1 builds the pipeline's front
door: the intake gateway that accepts an artifact and persists it for processing.

# NON-NEGOTIABLE CONSTRAINTS
- AWS-native (API Gateway / Lambda / S3 / DynamoDB); GitHub is dev-only.
- Python-first app code; infra in CDK v2 TypeScript (project convention).
- Multi-account: DynamoDB in hub account Pipeline-Hub (641628980935) per RD-008.
- Zero trust: the artifact is persisted as status=RECEIVED; never marked safe,
  never forwarded downstream. IAM/SigV4 auth gates who can submit.
- Production-quality: no mocks/placeholders in the execution path. moto is
  unit-test-level ONLY (explicitly agreed).
- VALIDATION-GATED: nothing is "done" on inference — the USER validates live and
  the result is recorded in RUNBOOK.md.
- RESTORE-POINT DISCIPLINE: build from a known-good point; revert rather than
  forward-patch.

# OPERATIONAL CONTEXT (state this on EVERY command block)
  Build sandbox: INTEGRATIONS_ONLY (NO AWS creds) — the executor BUILDS + hands
  off; the USER runs `cdk deploy` and validates live on hub account 641628980935
  (region of the user's choice). Confirm the active account/profile before deploy.

# HARD-WON LESSONS (do NOT repeat)
- Verify the DEPLOYED/produced artifact (S3 object + DynamoDB item), not just the
  local file or a 201 response.
- Confirm the target account (641628980935) before every operational command.
- IAM/SigV4 endpoints need a signed request to validate — hand the user the EXACT
  copy-paste signed-request sequence (awscurl or signed CLI), zero-guess.
- Give the user the FULL copy-paste command sequence with real values.
- API Gateway has a ~10 MB request cap; enforce a size limit in the Lambda and
  return 413 rather than failing opaquely.

# FIRST — VALIDATION & ADVANCEMENT GATE (do this BEFORE any new work)
# Binding policy: RUNBOOK.md "Validation & Advancement Gate". Validation results
# DRIVE status and DICTATE advancement. The user validates live; you RECORD it.
# 1. CLOSE OUT THE PRIOR STORY: Story 1.1 is 🟡 pending the user's live check.
#      - On PASS (201 + intake_id; S3 object present; DynamoDB item RECEIVED with
#        matching sha256): write the dated Validation Result line + flip the 1.1
#        row 🟡 → ✅ (+ Completed date) in RUNBOOK.md (paired status commit + PR).
#      - On FAIL: keep 1.1 🟡 and RE-FOCUS on fixing + re-validating 1.1. Do NOT
#        advance to 1.2.
# 2. HARD ADVANCEMENT GATE: 1.2 may begin ONLY once 1.1 is ✅.

# WHERE WE ARE
- Current phase/story: P1 / Story 1.1 — Intake gateway endpoint.
- Prior story + validation state: 1.1 built on branch feature/story-1.1, PR open;
  🟡 pending the user's live deploy + submit validation.
- Last restore point: none yet.
- True current state: infra/ CDK stack + lambdas/intake/ handler + unit tests
  exist on feature/story-1.1; NOTHING deployed live yet (INTEGRATIONS_ONLY).
- Governing docs: PROJECT_PLAN.md, RUNBOOK.md, BOM.md, RESTORE.md, and this
  story's brief: session-briefs/story-1.1-brief.md

# THIS SESSION'S OBJECTIVE
Get Story 1.1 to a validated ✅: the user deploys the intake stack to hub
641628980935, submits a sample artifact to POST /intake, confirms accept +
persist, and the executor records the result + flips the runbook.

# SCOPE & GUARDRAILS
- In scope: deploy + live-validate the intake gateway; record result; flip status.
- Out of scope / do NOT touch: classification (1.2), routing (1.3), safe-reject
  (1.4), any PDE/verdict/inspection logic. Do NOT edit the intentional
  {{PROJECT_NAME}} placeholders in METHODOLOGY.md, README Day-0, or the templates.
- Depends on (must already be ✅): none.

# DEFINITION OF DONE (this session) — a PASS/FAIL GATE
The user, live on hub 641628980935, submits a sample artifact and confirms ALL of:
(1) 201 with intake_id + status=RECEIVED + sha256; (2) the S3 object exists at the
returned key; (3) a DynamoDB item exists for that intake_id with status=RECEIVED
and a matching sha256.
- Goes ✅ ONLY when the user confirms this live AND it is RECORDED in RUNBOOK.md.
- If validation FAILS: not done — stay on 1.1, fix, re-validate.

# ENVIRONMENT
- Repo cloned; push to feature/story-1.1 (never main). Open/मanage PRs via
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls` (NOT `gh pr create`).
- Merging is the repo-owner's action unless told "merge it via API."

# WORKING AGREEMENT
- One story to completion: design -> build -> USER validates live -> RECORD +
  flip status -> commit (paired status commit). Push to a branch; open a PR.
- At session end, author the NEXT story's brief + prompt (MANDATORY) with a
  Lessons Learned / Carry-Forward section of THIS session's actual lessons.
- If blocked, push partial progress + a draft PR; never silently fail.
```
