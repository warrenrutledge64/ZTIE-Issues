You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting. Do NOT change anything until you have (a) READ the
plan + runbook + methodology + this story's brief (`session-briefs/story-2.0E-brief.md`),
(b) re-established true state (STEP 0), and (c) confirmed the Validation Debt Register
state + advancement gate.

# PROJECT IDENTITY
ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted
artifact BEFORE it reaches the PDE. Work is validation-gated: nothing is ✅ until a
recorded live pass (the covenant). Three accounts: Pipeline-Hub (641628980935) =
brains/control plane + durable record; Forensic (360999005254) = self-contained blast
zone (ephemeral only); Pipeline-Sandbox (586917955591) = ZTIE→PDE handoff. Story 2.0E
is a COST-REMEDIATION on the validated Story 2.0 Forensic infra.

# WHAT THIS STORY IS + WHY IT IS NEXT
2.0E is the SOLE OPEN entry in the Validation Debt Register (🟡). Per the hard-pause
gate (RD-023), NO new feature story may start while the register is non-empty — so
2.0E's live validation is THE next action (NOT Story 2.6, whose start is gated until
2.0E clears). Reworking/validating 2.0E is the permitted in-progress work.

THE CODE IS ALREADY BUILT + OFFLINE-VALIDATED on branch `feature/story-2.0E` (latest
commit). This session's job: help the STAKEHOLDER validate the FINAL two-tier design
LIVE, record the result verbatim, and flip status.

# THE DESIGN (FINAL — two-tier, RD-027)  — and the story of how we got here
The detonation VPC's interface endpoints were ~$88/mo idle (6 endpoints x 2 AZs, 24/7)
but only used during a detonation. 2.0E first tried making ALL SIX ephemeral — but a
3-attempt live investigation (2026-09-07) PROVED the SSM control channel cannot be
created per-run reliably: a booting host could not open a TCP connection to a
same-run-created ssm/ssmmessages/ec2messages endpoint (curl 000/connect-timeout) even
though DNS resolved to a private IP, SGs allowed 443 both ways, the endpoint was
`available`, and host+endpoint shared one AZ. Four theories (DNS/SG/subnet/AZ) were
each disproven live; detonation passed only ~1/3. Story 2.3 had proven ALWAYS-ON SSM
endpoints are rock-solid.

FINAL two-tier split (RD-027):
- ALWAYS-ON, SINGLE AZ (in `ZtieForensicInfraStack`): `ssm` + `ssmmessages` +
  `ec2messages` — the host-native SSM control channel. Warm + reliable. ~$22/mo.
- EPHEMERAL per run (orchestrator, `lambdas/detonation/`): `logs` + `sqs` +
  `bedrock-runtime` — NOT needed at agent boot. Created just-in-time, torn down in a
  `finally`, swept if orphaned (sweep drains the delete before recreating). ~$66/mo
  recovered.
The disproven mitigations (DNS-settle, UserData ssm-agent-restart, diagnostics,
context-TTL) were REVERTED. The sweep drain-wait was KEPT.

# NON-NEGOTIABLE CONSTRAINTS
- Do NOT re-open the two-tier decision. The SSM control channel stays ALWAYS-ON; do
  NOT try to make it ephemeral again (proven unreliable, RD-027).
- Containment unchanged: no IGW/NAT/0.0.0.0/0; host-native SSM; no SSH; 5-min hard
  TTL. Region-scoped endpoint IAM only (no IGW/NAT/route creation).
- Do NOT re-introduce an S3 interface endpoint (conflicts with the S3 gateway
  endpoint — verified live in 2.3). S3 stays on the gateway endpoint.
- Residue containment is the ephemeral HOST + wiped volume, NOT the endpoints.
- VALIDATION-GATED: 2.0E flips ✅ only on a recorded live pass of the FINAL code,
  INCLUDING a sweep-triggering run that still reaches outcome=completed.
- ROLES: the LIVE deploy + detonation are the STAKEHOLDER's action in Forensic
  (executor has NO live creds); the executor RECORDS returned output VERBATIM.
- DOCS FIRST-CLASS (RD-015): PR-reviewed; PROJECT_PLAN ↔ RUNBOOK in EXACT alignment.

# OPERATIONAL CONTEXT (state on EVERY command block)
Build sandbox is INTEGRATIONS_ONLY (no AWS creds; PyPI/npm blocked). You BUILD; the
USER validates live in CloudShell (ambient creds). Region us-east-1. Run
`aws sts get-caller-identity` before EVERY operational block. Detonation + all
artifact-touching compute are in FORENSIC (360999005254); the tracking table is in the
HUB (641628980935) — TWO CloudShell tabs. `awscurl` is NOT preinstalled in a fresh
CloudShell: `pip install awscurl`. `cdk deploy` must run from `infra/`.
`ZtieDetonationStack` only instantiates when its `-c` context is supplied.
`aws logs tail --follow` blocks — use `--since 15m` (no follow).

# KNOWN-GOOD LIVE FACTS (from the 2026-09-07 runs)
- Intake: `https://1j01rrd9u4.execute-api.us-east-1.amazonaws.com/prod/intake`
  (IAM/SigV4, submit from a FORENSIC principal).
- Detonation Lambda: `ZtieDetonationStack-DetonationOrchestrator26C208DF-3Xzz4erewJub`
- Hub tracking table: `ZtieHubTrackingStack-TrackingTable170A6688-133E30JVEWB1Z` (HUB tab)
- `vpc-0457ce09693cc48e4`; launch template `lt-045ddce7fdac386db`; endpoint SG
  `sg-00994a01fb3a5eb2c`; subnets `subnet-0290d865c24a57913` (us-east-1a) /
  `subnet-0f520c2e4756b4332` (us-east-1b).
- Intake body contract: JSON `{filename, content_base64, content_type?, submitter?}`
  (base64 must be `-w0`, no wraps).

# STEP 0 — RE-ESTABLISH TRUE STATE (before any edit)
# Trust `main`/`check_docs` over anything written here.
- git fetch/pull; check out `feature/story-2.0E`; list open PRs (expect the 2.0E PR).
- `python3 scripts/check_docs.py` → expect PASS (2.0E is the sole 🟡 register entry).
- Re-run the offline proof to confirm the branch is green BEFORE spending live time:
  `cd lambdas/detonation && python -m unittest test_runspec test_outcome test_ephemeral_endpoints`
  (expect 43 pass); `ruff check`; from `infra/` `prettier --check` + `tsc` baseline.
- Confirm the launch-template UserData is CLEAN (no leftover diagnostic/agent-restart
  lines): the two-tier design does NOT touch UserData beyond the 5-min TTL.

# LIVE VALIDATION RUNBOOK (stakeholder drives; you record) — Forensic tab unless noted
Before each block: `aws sts get-caller-identity` (Forensic 360999005254).
1. Redeploy BOTH stacks from `infra/`:
   `npx cdk deploy ZtieForensicInfraStack` (creates the 3 ALWAYS-ON SSM endpoints,
   single AZ), then `npx cdk deploy ZtieDetonationStack -c artifactBucketName=… -c
   detonationQueueUrl=… -c detonationQueueArn=… -c hubIngestQueueUrl=… -c
   hubIngestQueueArn=… -c detonationInstanceRoleArn=…` (same context values as the
   2026-09-07 runs; they are in cdk.context.json / the brief).
2. DoD #1 (idle): `aws ec2 describe-vpc-endpoints --filters
   Name=vpc-id,Values=vpc-0457ce09693cc48e4 …` → shows S3 Gateway + the 3 always-on
   SSM interface endpoints ONLY; ZERO logs/sqs/bedrock (the ephemeral tier absent
   when idle).
3. `pip install awscurl`; build `/tmp/intake_body.json` (filename hello.sh, a
   `#!/bin/sh` + echo ZTIE-DETONATION-OK script, base64 -w0); submit via awscurl. Note
   the intake_id.
4. DoD #2: during the run, the 3 EPHEMERAL endpoints (logs/sqs/bedrock-runtime) appear
   tagged `ztie:ephemeral-endpoint=detonation` + IntakeId and reach `available`.
5. DoD #3: `aws logs tail … --since 15m` shows the run reach
   `outcome=completed ssm_status=Success` + `ZTIE-DETONATION-OK`. Verify the Hub
   record (HUB tab) has the verdict-free dynamic_run (containment flags true,
   public_ip false, no verdict).
6. DoD #4: after the run, describe-vpc-endpoints returns to the #1 idle state
   (ephemeral tier deleted; always-on SSM trio remains).
7. DoD #5 (orphan sweep): plant a stale tagged endpoint (create a tagged `logs`
   interface endpoint), submit another detonation, confirm the log shows
   `swept 1 orphaned …` deleting it AND the run still reaches `outcome=completed`
   (this exact path — sweep + still-succeed — is what earlier attempts failed).

# DEFINITION OF DONE (5/5 PASS/FAIL)
1. Idle = S3 gateway + 3 always-on SSM only (no ephemeral tier).
2. The 3 ephemeral endpoints appear + reach `available` during a run.
3. The run reaches `ssm_status=Success` / `ZTIE-DETONATION-OK` / `outcome=completed`,
   verdict-free outcome on the Hub record.
4. Ephemeral tier torn down after (back to the #1 idle state).
5. A sweep-triggering run clears a stale tagged endpoint AND still completes; the
   sweep never touches the always-on control channel or any non-ZTIE endpoint.
Flips ✅ ONLY on a recorded live pass; otherwise stays 🟡.

# ON PASS (and only then)
Record the dated Validation Result in STORY_DETAIL 2.0E + the RUNBOOK master table;
flip 2.0E ✅ (paired status commit); CLEAR 2.0E from the Validation Debt Register
(register → empty; note it); keep PLAN ↔ RUNBOOK aligned; re-run `check_docs.py`
(PASS). Because the 2.0 stack changed shape, REFRESH the Forensic deployed-state
restore point / manifest + update BOM. THEN the advancement gate opens and Story 2.6
(the on-deck pipeline story) becomes the next-up.

# ENVIRONMENT
Repo cloned; push to `feature/story-2.0E`, never main. Open PRs via
`gh api repos/warrenrutledge64/ZTIE-Issues/pulls`. Merges + live AWS are the owner's.

# WORKING AGREEMENT
Validate-then-record. If a live check fails, fix on-branch + re-validate ONCE (fix the
code you will actually keep — never validate-the-wrong-thing). Management artifacts are
first-class (RD-015). At session end, if 2.0E is ✅, repoint on-deck to Story 2.6 and
fold this session's real Lessons Learned into 2.6's prompt. If blocked, push partial
progress + surface the blocker; never silently fail.

# CARRY-FORWARD FOR AFTER 2.0E CLOSES (do not act on until 2.0E is ✅)
- Story 2.6 (parallel fork of the two lanes) is the next PIPELINE story once the
  register is empty.
- Multi-tenancy (RD-028) is captured as the 'tenancy' track: T.1 (design spike,
  doc-only, may proceed early — protects Phase-4 dashboard/Hub design) and the
  DEFERRED T.2/T.3 (per-subscriber provisioning + Hub-side per-subscriber isolation,
  commercialization phase). Decisions settled: per-subscriber Forensic ACCOUNT = hard
  boundary; WITHIN a subscriber = shared-trust + org-shared dashboard; per-subscriber
  (not per-user) granularity; residue bounded by the ephemeral host. The Phase-4
  dashboard (Story 4.3) must be built as a per-subscriber, org-shared view from the
  start.
