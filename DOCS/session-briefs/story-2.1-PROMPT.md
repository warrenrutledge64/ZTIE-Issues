# Session Prompt — Story 2.1 (executor-facing)

> Generated from `story-2.1-brief.md`. Paste the block below to start the Story
> 2.1 working session. It carries the ACTUAL lessons from the 2.0 build session.

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
Story 2.1 builds the STATIC-ANALYSIS LANE — the non-executing scanning stack
(cfn-lint, cfn-guard, checkov, bandit) that runs over an artifact routed to the
`static_analysis` lane by the 1.3 router and emits STRUCTURED JSON findings. It
is the first Phase-2 lane and one of the two evidence streams Nova Pro correlates
in Phase 3. NON-EXECUTING: it reads/parses the artifact, it never runs it.

# NON-NEGOTIABLE CONSTRAINTS
- PYTHON-FIRST. Python 3.12 (project standard). Bash only for trivial glue.
- NON-EXECUTING. The static lane INSPECTS; it must NEVER execute the artifact.
  (Execution is the dynamic lane, 2.3, on the isolated EC2 host.)
- FORENSIC ACCOUNT (360999005254) — it touches the raw artifact, so it runs in
  the blast zone (RD-008). Only DERIVED data crosses to the Hub (RD-009/012).
- CONTRACT-FIRST. Decide the SHAPES first: (a) the NORMALIZED findings JSON (one
  shape across all four tools) and (b) the derived Hub findings-SUMMARY envelope
  (a FIFTH envelope kind on the existing RD-013 Hub gate — integrity-keyed by
  intake_id+sha256, allow-list, bounded, NO verdict field). Emit any schema via a
  `python json.dump` step (fs_write refuses a remote "$schema" URL); write BOTH
  the canonical schemas/ copy and any bundled lambda copy from one source so they
  can't drift. REUSE the Hub-gate envelope-kind routing + integrity-bound
  conditional update_item pattern in lambdas/hub_ingest/handler.py — do NOT invent
  a new crossing mechanism.
- PURE LOGIC + THIN SEAM. Keep normalization pure/offline-testable; put the four
  scanner invocations + boto3 (S3 read, findings write, envelope send) behind the
  thin awsio seam. A scanner error must NOT crash the pipeline.
- ZERO-TRUST BOUNDARY. A static finding is EVIDENCE, never a verdict
  (PASS/FAIL/INCONCLUSIVE) and never a forward-to-PDE decision. Raw findings that
  may echo artifact content STAY in Forensic (S3); only a bounded summary crosses.
- PACKAGING NOTE: cfn-lint/checkov/bandit are pip; cfn-guard is a Rust binary. A
  CONTAINER-IMAGE Lambda is an acceptable PACKAGING choice for the static scanners
  — the no-Docker rule (RD-001) is SPECIFICALLY about the dynamic DETONATION host,
  not static tooling. Confirm the packaging approach (bundled layer vs image vs
  small Forensic compute) against AWS-native + production-code constraints early.
- PRODUCTION CODE. No mock scanners, no fake findings. Real tool invocations,
  real JSON. VALIDATION-GATED: nothing is "done" on inference — the USER validates
  live and the result is RECORDED in RUNBOOK.md.

# OPERATIONAL CONTEXT (state this on EVERY command block)
  Build sandbox is INTEGRATIONS_ONLY (NO AWS creds; PyPI + npm BLOCKED). You BUILD +
  hand off; the USER runs the live validation in CloudShell (ambient creds, no
  --profile). Region us-east-1. Confirm the active account with
  `aws sts get-caller-identity` before every operational block. The intake API +
  scanners are in FORENSIC (360999005254); the tracking table is in the HUB
  (641628980935) — the operator needs TWO CloudShell tabs. Submit from a FORENSIC
  SigV4 principal (a Hub principal gets 403 — zero-trust gate); query the tracking
  table from a HUB shell (querying it in Forensic gives ResourceNotFoundException).

# HARD-WON LESSONS (do NOT repeat) — carried from the 2.0 build session
- Offline Python proof: boto3/pytest/moto are NOT installable offline. Prove the
  PURE normalization logic with stdlib `unittest` over FIXTURE scanner outputs;
  mark AWS-touching + real-scanner tests live-only/skipped (the 1.2/1.3/1.4
  pattern). ruff for lint.
- If you touch TS/CDK (e.g. to add a scanner-packaging resource to a stack):
  `unset NODE_OPTIONS` first or tsc/prettier/npm crash on a broken preload;
  `npm install` gets 403 offline so you CANNOT cdk synth/deploy — proof is
  `prettier --check` clean + `tsc --noEmit` showing ONLY the environmental
  `Cannot find module 'aws-cdk-lib'` family (identical on the live stacks).
- Opening the PR: `gh pr create` is BROKEN. Write the PR body via a bash heredoc
  into a bash-visible path (agent-written /tmp files are NOT visible to gh/bash),
  then: gh api repos/warrenrutledge64/ZTIE-Issues/pulls -f title=... -F body=@file
  -f head=feature/story-2.1 -f base=main --jq .html_url
- Contract-first is the through-line: settle the findings JSON + the Hub summary
  envelope shape before writing scanner glue.

# FIRST — VALIDATION & ADVANCEMENT GATE (do this BEFORE any new work)
# Binding policy: RUNBOOK.md "Validation & Advancement Gate".
# 1. Close out Story 2.0: it was 🟡 (built, awaiting live validation) at the end of
#      its build session (PR #23). If the user validated it, confirm the recorded
#      pass + ✅ flip is on main; if it FAILED, 2.0 is the focus, not 2.1. If still
#      unvalidated, note it — but 2.1 does NOT depend on 2.0, so 2.1 may proceed.
# 2. ADVANCEMENT GATE: 2.1 depends on 1.3 ✅. Confirmed (validated 2026-08-27).
#      Proceed.

# WHERE WE ARE (reconfirm via STEP 0 — git pull, list open PRs, no main/PR drift)
- Phase 1 COMPLETE: 1.1 / 1.1R / 1.R / 1.2 / 1.3 / 1.4 all ✅.
- Phase 2 underway: 2.0 (infra foundation) built + PR #23 — 🟡 or ✅ depending on
  validation (check main). 2.1 is the static lane; 2.3 (detonation) needs 2.0.
- Deployed: Hub `ZtieHubTrackingStack` (tracking DynamoDB, ingest SQS+DLQ,
  validator Lambda handling 4 envelope kinds, quarantine S3); Forensic
  `ZtieIntakeStack` (intake API + Lambda, artifact S3, preprocessor classify+route+
  safe-reject); Forensic `ZtieForensicInfraStack` (2.0 — isolated VPC + endpoints,
  IAM, launch template, SSM). 2.1 adds the static-scan compute + a fifth Hub
  envelope kind.
- Governing docs: PROJECT_PLAN.md, RUNBOOK.md (source of truth for status),
  RESTORE.md, BOM.md, DOCS/COMPLIANCE.md, DOCS/ARCHITECTURE.md, and this story's
  brief: session-briefs/story-2.1-brief.md

# THIS SESSION'S OBJECTIVE
Build the static-analysis lane: run cfn-lint/cfn-guard/checkov/bandit
(non-executing) over an artifact routed to `static_analysis`, normalize to one
structured JSON findings shape (Forensic S3), and cross a derived findings-summary
envelope (fifth kind) to the Hub tracking record via the RD-013 gate. Get the user
to validate live that a known-bad IaC template and a known-bad script each produce
real structured findings and the summary lands on the Hub record — without ever
executing the artifact and without crashing on a scanner error.

# SCOPE & GUARDRAILS
- In scope: scanner invocation + output normalization; findings JSON contract; the
  fifth Hub summary envelope kind (reuse the gate pattern); Forensic-side wiring;
  scanner packaging decision (record it as an RD if architecturally significant).
- Out of scope / do NOT touch: compliance-framework mapping + signature scans (2.2,
  depends on 2.1); dynamic lane (2.3/2.4/2.5); parallel fork (2.6); the Hub verdict;
  the intake/preprocessor stacks + the 2.0 infra stack beyond consuming them.
- Depends on (must be ✅): 1.3. (NOT 2.0.)

# DEFINITION OF DONE (this session) — a PASS/FAIL GATE
The user, live in Forensic, confirms: a known-bad IaC template and a known-bad
script are each statically scanned by the appropriate tools; a structured JSON
findings document is produced (inspectable) with real findings; the derived
scan-complete summary lands on the Hub tracking record (queryable by intake_id); no
artifact is executed; the pipeline does not crash on a scanner error.
- Goes ✅ ONLY when the user confirms live AND it is RECORDED in RUNBOOK.md.
- If validation FAILS: not done — stay on 2.1, fix, re-validate.

# ENVIRONMENT
- Repo cloned; push to feature/story-2.1 (never main). Open/manage PRs via
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls` (NOT `gh pr create`).
- Merging is the repo-owner's action unless told "merge it via API."

# WORKING AGREEMENT
- MANAGEMENT ARTIFACTS ARE FIRST-CLASS (RD-015): keep PROJECT_PLAN ↔ RUNBOOK in
  EXACT alignment; update the 2.1 brief; PR-review all docs. Not done until docs
  are updated + aligned, not just code.
- One story to completion: design → build → USER validates live → RECORD + flip
  status → commit (paired status commit). Push to a branch; open a PR.
- At session end, author the NEXT story's brief + prompt (MANDATORY) with a Lessons
  Learned / Carry-Forward of THIS session's actual lessons. (Next after 2.1 is
  Story 2.2 compliance mapping — check the runbook ordering; 2.3 needs 2.0.)
- If blocked, push partial progress + a draft PR; never silently fail.
```
