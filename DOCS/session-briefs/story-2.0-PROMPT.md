# Session Prompt — Story 2.0 (executor-facing)

> Generated from `story-2.0-brief.md`. Paste the block below to start the Story
> 2.0 working session. It carries the ACTUAL lessons from the Phase 1 build sessions.

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
Story 2.0 deploys the SHARED INFRASTRUCTURE FOUNDATION in the Forensic account
that ALL of Phase 2 depends on: VPC with isolated subnets (VPC endpoints only,
zero internet egress), IAM roles, per-run EC2 launch template (parametric AMI,
5-min hard TTL), SSM wiring, and Bedrock Nova Pro access.

# NON-NEGOTIABLE CONSTRAINTS
- CDK v2 TYPESCRIPT for the stack (project standard for infra).
- FORENSIC ACCOUNT (360999005254) — all Phase-2 execution happens here.
- ISOLATED SUBNETS ONLY — SubnetType.PRIVATE_ISOLATED. NO NAT, NO IGW. The
  detonation host CANNOT phone home. AWS services via VPC endpoints ONLY.
- HOST-NATIVE SSM ON EC2 — no Docker, no containers, no SSH. SSM is the ONLY
  command channel. No key pair on the launch template.
- 5-MINUTE EC2 HARD TTL — UserData `shutdown -h +5`. Non-negotiable. The
  detonation host is ephemeral and self-destructs.
- PARAMETRIC AMI — resolve from SSM parameters (`/ztie/ami/<flavor>`), NOT
  hard-coded AMI IDs. CDK: `ec2.MachineImage.fromSsmParameter(...)`.
- ec2:RunInstances VIA LAUNCH TEMPLATE (NOT CloudFormation per run). The
  launch template is a STATIC resource; the use of it (RunInstances) is 2.3.
- PRODUCTION CODE. VALIDATION-GATED: the USER deploys and confirms live.

# OPERATIONAL CONTEXT (state this on EVERY command block)
  Build sandbox is INTEGRATIONS_ONLY (NO AWS creds; PyPI + npm BLOCKED). You BUILD +
  hand off; the USER runs the deploy in CloudShell (ambient creds, no --profile).
  Confirm the active account before any operational command. Region us-east-1.
  Forensic account: 360999005254.

# HARD-WON LESSONS (do NOT repeat)
- CDK stack pattern: follow ztie-intake-stack.ts / ztie-hub-tracking-stack.ts:
  account guard (synth-time Annotations.of(this).addWarning if wrong account),
  explicit tags ({Project:'ZTIE', Phase:'P2-Infra', ManagedBy:'CDK', Story:'2.0',
  Account:'Forensic'}), CfnOutput for every downstream-consumed value, clear
  doc comments.
- Register the new stack in `infra/bin/ztie-infra.ts`. The Forensic infra stack
  has NO cross-account dependency — it deploys standalone to Forensic.
- Local proof that works offline: `npx tsc --noEmit` (type check), `prettier
  --check` (from infra/ after `unset NODE_OPTIONS`). You CANNOT `cdk synth` or
  `cdk deploy` from the sandbox.
- `npm install` (NOT `npm ci` — no lock file). Watch for the 974MB home partition
  in CloudShell (rm -rf ~/.npm ~/.cache node_modules + docker system prune -af).
- CloudShell: one line at a time. /tmp wiped on session recycle. Confirm account
  with `aws sts get-caller-identity` before every block.
- `gh pr create` is broken — open PRs with
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls -f title=... -F body=@file
  -f head=feature/story-2.0 -f base=main --jq .html_url`.
- Ruff for Python (not relevant here — this is pure CDK/TS). Prettier for TS.
- The Image Builder status: Ubuntu 22.04 AMI built (ami-088e04fb4c75334c4, set in
  SSM). AL2023 FAILED. At least the Ubuntu SSM param should exist for validation.

# FIRST — VALIDATION & ADVANCEMENT GATE (do this BEFORE any new work)
# Binding policy: RUNBOOK.md "Validation & Advancement Gate".
# 1. Phase 1 close: 1.1/1.1R/1.R/1.2/1.3/1.4 are all ✅. If the Phase-1 close
#      (restore/phase-1-green capture) has NOT been done yet, decide whether to do
#      it now or defer (it does NOT block 2.0 per the runbook — 2.0 depends on 1.3,
#      which is ✅). Recommend deferring the P1 restore capture to a governance
#      session rather than blocking infra work on it.
# 2. ADVANCEMENT GATE: 2.0 depends on 1.3 ✅. Confirmed. Proceed.

# WHERE WE ARE (reconfirm via STEP 0 — git pull, list open PRs, no main/PR drift)
- Phase 1 COMPLETE: 1.1 ✅, 1.1R ✅, 1.R ✅, 1.2 ✅, 1.3 ✅, 1.4 ✅.
- Phase 2 starting. 2.0 is the FIRST story.
- Deployed P1 resources: Hub `ZtieHubTrackingStack` (tracking DynamoDB, ingest SQS
  + DLQ, validator Lambda handling 4 envelope kinds, quarantine S3); Forensic
  `ZtieIntakeStack` (intake API + Lambda, artifact S3, preprocessor Lambda that
  classifies + routes + safe-rejects).
- No Phase-2 infrastructure exists yet — this story creates it.
- Governing docs: PROJECT_PLAN.md, RUNBOOK.md (source of truth for status),
  RESTORE.md, BOM.md, DOCS/COMPLIANCE.md, DOCS/ARCHITECTURE.md, and this story's
  brief: session-briefs/story-2.0-brief.md

# THIS SESSION'S OBJECTIVE
Deploy the shared Phase-2 infrastructure foundation in Forensic: a CDK v2 stack
with (1) a VPC with isolated subnets + VPC endpoints (S3, SQS, SSM, SSM Messages,
EC2 Messages, CloudWatch Logs, Bedrock), (2) IAM roles (detonation instance profile
+ scanner/orchestrator role + Nova Pro invoke role), (3) an EC2 launch template
(parametric AMI from SSM, isolated subnet, instance profile, 5-min hard TTL in
UserData), (4) SSM wiring (endpoints + profile). Get the user to validate live that
the stack deploys, the VPC is isolated, and the launch template exists.

# SCOPE & GUARDRAILS
- In scope: CDK stack (TypeScript), VPC + isolated subnets + VPC endpoints, IAM
  roles, launch template, SSM wiring, Bedrock grant, CfnOutputs.
- Out of scope / do NOT touch: static scanning code (2.1), detonation Lambda/Step
  Function (2.3), telemetry capture (2.4), the intake/preprocessor stacks (P1),
  the Hub account. Don't edit intentional {{...}} template placeholders.
- Depends on (must already be ✅): 1.3.

# DEFINITION OF DONE (this session) — a PASS/FAIL GATE
The user, live in the Forensic account, confirms:
  1. CDK stack deploys successfully.
  2. VPC exists with isolated subnets (no IGW, no NAT).
  3. VPC endpoints exist for SSM, SSM Messages, EC2 Messages, CW Logs, S3, Bedrock.
  4. Launch template exists, references a valid AMI via SSM parameter.
  5. Instance profile exists with AmazonSSMManagedInstanceCore.
  6. UserData contains `shutdown -h +5`.
  7. No 0.0.0.0/0 route in the route tables (isolated).
- Goes ✅ ONLY when the user confirms live AND it is RECORDED in RUNBOOK.md.
- If validation FAILS: not done — stay on 2.0, fix, re-validate.

# ENVIRONMENT
- Repo cloned; push to feature/story-2.0 (never main). Open/manage PRs via
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls` (NOT `gh pr create`).
- Merging is the repo-owner's action unless told "merge it via API."

# WORKING AGREEMENT
- MANAGEMENT ARTIFACTS ARE FIRST-CLASS (RD-015): keep PROJECT_PLAN ↔ RUNBOOK in
  EXACT alignment; update the 2.0 brief; PR-review all docs. Not done until docs
  are updated + aligned, not just code.
- One story to completion: design → build → USER validates live → RECORD + flip
  status → commit (paired status commit). Push to a branch; open a PR.
- At session end, author the NEXT story's brief + prompt (MANDATORY) with a Lessons
  Learned / Carry-Forward of THIS session's actual lessons. (Next after 2.0 is
  Story 2.1 static scanning stack — check the runbook ordering.)
- If blocked, push partial progress + a draft PR; never silently fail.
```
