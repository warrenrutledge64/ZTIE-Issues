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
is a COST-REMEDIATION on the validated Story 2.0 Forensic infra: it moves the six
interface VPC endpoints from always-on to EPHEMERAL (created per detonation, torn down
after) to stop ~$88/mo of idle burn, with NO change to any containment invariant.

# WHAT THIS STORY IS  (nature + gate role)
Follow-forward COST-REMEDIATION on a validated story (RD-027) — NOT a retro-edit (2.0
stays ✅ for what it validated). THE CODE IS ALREADY BUILT + OFFLINE-VALIDATED on
branch `feature/story-2.0E`; this session's job is to help the STAKEHOLDER validate it
LIVE, record the result verbatim, and flip status. 2.0E is the SOLE open entry in the
Validation Debt Register — so reworking/validating it is the permitted in-progress
work, and it blocks only NEW unrelated feature stories until it clears. Do NOT start an
unrelated feature story until 2.0E is ✅.

# THE PROBLEM THIS FIXES (so you can explain it)
The Forensic detonation VPC carried SIX always-on INTERFACE VPC endpoints (SSM,
SSMMessages, EC2Messages, CloudWatchLogs, SQS, BedrockRuntime). Interface endpoints
bill ~$0.01/hr EACH, per AZ, 24/7 — with maxAzs:2 that's 12 ENIs ≈ $88/mo IDLE — yet
they're only USED for the few minutes of a detonation. The EC2 host is NOT the burn
(5-min TTL); the S3 gateway endpoint is free; the VPC/subnets/roles/launch-template
are free. 2.0E makes the six interface endpoints ephemeral. Idle interface-endpoint
cost → ~$0.

# NON-NEGOTIABLE CONSTRAINTS
- NO CONTAINMENT INVARIANT CHANGES. Creating/deleting interface endpoints adds no
  IGW/NAT/0.0.0.0/0 route. Still host-native SSM, still no SSH, still the 5-min hard
  TTL, still isolated subnets. This is a cost/lifecycle change ONLY.
- KEEP ALL SIX ENDPOINTS incl. BEDROCK RUNTIME. Phase 3 (Nova Pro correlation, 3.2) is
  intended to invoke Nova Pro from inside the isolated VPC; an idle ephemeral endpoint
  costs $0, so keeping Bedrock costs nothing and avoids a Phase-3 landmine. Do NOT drop
  it. (Open lifetime question for 3.2: if correlation runs in-VPC, the ephemeral window
  must extend to cover it — the teardown boundary is deliberately explicit.)
- DO NOT RE-INTRODUCE AN S3 INTERFACE ENDPOINT. S3 stays on the GATEWAY endpoint
  (always-on, free); an S3 interface endpoint with private DNS CONFLICTS with the
  gateway endpoint (verified live during 2.3). Only the six non-S3 services are
  ephemeral interface endpoints.
- ORPHAN SWEEP IS THE RESILIENCE BACKSTOP, not a trade. The one new failure mode (a
  crashed run leaving endpoints billing) is covered by a tag- + VPC-scoped start-of-run
  sweep. Worst case reverts to the OLD idle cost until the next run mops up — never a
  safety regression. No scheduled infra added.
- VPC FLOW LOGS LEFT AS-IS (stakeholder decision — a cost/audit trade not worth mixing
  in). Do NOT touch them.
- VALIDATION-GATED, NEVER ON INFERENCE: 2.0E flips ✅ only on a recorded live pass of
  the FINAL code (METHODOLOGY §4). Especially DoD #5 (orphan sweep) — prove it, do not
  infer it.
- ROLES: the LIVE deploy + detonation + endpoint-lifecycle checks are the STAKEHOLDER's
  action in Forensic (executor has NO live creds); the executor RECORDS the returned
  output VERBATIM. Do NOT simulate/assume a live output.
- DOCS FIRST-CLASS (RD-015): PR-reviewed, never straight to main; PROJECT_PLAN ↔
  RUNBOOK in EXACT alignment.

# OPERATIONAL CONTEXT (state this on EVERY command block)
  Build sandbox is INTEGRATIONS_ONLY (NO AWS creds; PyPI + npm BLOCKED — boto3/pytest/
  moto/jsonschema/aws-cdk-lib NOT installable). You BUILD; the USER validates live in
  CloudShell (ambient creds, no --profile). Region us-east-1. Confirm the active
  account with `aws sts get-caller-identity` before EVERY operational block. The
  detonation VPC + all artifact-touching compute are in FORENSIC (360999005254); the
  tracking table is in the HUB (641628980935) — TWO CloudShell tabs.
  Toolchain note: `ruff`/`prettier` live under `~/.pyenv/versions/3.12.13/bin/` (the
  default python lacks ruff). Endpoint-seam tests stub boto3/botocore (sandbox has no
  boto3) and inject a fake into `awsio._ec2_client`.

# WHAT'S ALREADY BUILT (branch `feature/story-2.0E`) — verify, don't rebuild
- `infra/lib/ztie-forensic-infra-stack.ts`: removed the six always-on
  `addInterfaceEndpoint` calls. Kept the FREE scaffolding (isolated VPC + subnets, S3
  GATEWAY endpoint, endpoint SG, IAM roles, launch template). Publishes
  `/ztie/detonation/{vpc-id,endpoint-service-names,endpoint-security-group-id}` (+
  CfnOutputs). orchestratorRole gains `ManageEphemeralInterfaceEndpoints`
  (Create/Delete/DescribeVpcEndpoints + CreateTags, region-scoped — NO IGW/NAT/route).
- `infra/lib/ztie-detonation-stack.ts`: adds the three new SSM param names as env +
  the same endpoint-management grant to the 2.3 Lambda role.
- `lambdas/detonation/awsio.py`: `create_interface_endpoints` (private DNS, tagged
  `ztie:ephemeral-endpoint=detonation` + IntakeId), `wait_for_endpoints_available`
  (polls `available`, bails on `failed`), `delete_interface_endpoints` (never raises),
  `sweep_orphaned_endpoints` (VPC + tag scoped, skips `deleting`, never raises).
- `lambdas/detonation/handler.py`: `_resolve_coordinates` reads vpc/service-names/sg;
  `_detonate` sweeps orphans → creates endpoints → waits available
  (`ENDPOINT_AVAILABLE_TIMEOUT_S=180`) BEFORE launch; deletes endpoints on
  endpoint-setup failure, RunInstances failure, and in the finally after terminate.
- `lambdas/detonation/test_ephemeral_endpoints.py`: 10 offline tests. Offline proof:
  py_compile OK; ruff clean; test_runspec 7 + test_outcome 22 + test_ephemeral_endpoints
  10 = 39 pass; prettier clean; tsc only the known missing-aws-cdk-lib baseline.

# STEP 0 — RE-ESTABLISH TRUE STATE (before any edit)
# Trust `main` + `check_docs` over anything written here; if they disagree, `main` wins.
- git fetch/pull; check out `feature/story-2.0E`; list open PRs (expect the 2.0E PR).
- `python3 scripts/check_docs.py` → expect PASS (2.0E is 🟡 AND in the register).
- Confirm EXPECTED TRUTHS: 2.0E = 🟡 (built, pending live); it is the SOLE register
  entry; Depends-on 2.3 = ✅. Restore tags: `restore/story-2.3-green`,
  `restore/phase-2-floor-green` (owner pushes if still phantom — do NOT silently
  create).
- Re-run the offline proof (39 py tests, ruff, prettier, tsc-baseline) to confirm the
  branch is green before asking the stakeholder to spend live time.

# THIS SESSION'S OBJECTIVE
Get the stakeholder to validate LIVE that (a) idle = gateway-endpoint only (no
interface endpoints billing), (b) a detonation creates the six tagged interface
endpoints and they reach `available` before launch, (c) the detonation still succeeds
host-native through them exactly like 2.3, (d) they're deleted after the run, and (e)
the start-of-run orphan sweep cleans a stale endpoint. Then RECORD the result verbatim
and flip 2.0E ✅.

# LIVE VALIDATION RUNBOOK (stakeholder drives; you record) — ALL in Forensic
Give the stakeholder ONE line at a time (CloudShell paste-safety). Before each block:
`aws sts get-caller-identity` (must be Forensic 360999005254).
1. Redeploy BOTH stacks: `cdk deploy ZtieForensicInfraStack` then re-deploy
   `ZtieDetonationStack` (it needs the new env + IAM). Confirm the three new SSM params
   exist (`aws ssm get-parameter --name /ztie/detonation/vpc-id` etc.).
2. DoD #1 (idle): `aws ec2 describe-vpc-endpoints --filters Name=vpc-id,Values=<VpcId>`
   → gateway (S3) only, ZERO interface endpoints.
3. Submit a `raw_script` artifact via intake → routed to `dynamic_detonation` (as in
   2.3). While it runs, DoD #2: describe-vpc-endpoints shows the six interface
   endpoints tagged `ztie:ephemeral-endpoint=detonation` + the IntakeId, reaching
   `available`. (Tail the detonation Lambda logs for the "created N ephemeral endpoint"
   line + instance id.)
4. DoD #3: the run completes host-native (SSM `Success`, `ZTIE-DETONATION-OK`), host
   terminates on TTL, and the bounded verdict-free outcome lands on the Hub tracking
   record (verify from the HUB tab — TWO tabs).
5. DoD #4: after the run, describe-vpc-endpoints → back to gateway-only.
6. DoD #5 (sweep): create a stale tagged endpoint by hand (or use the interrupted-run
   leftovers), submit another detonation, and confirm the start-of-run sweep deleted
   the stale ZTIE-tagged endpoint (log line "swept N orphaned…") and did NOT touch any
   non-ZTIE endpoint.

# DEFINITION OF DONE (this session) — a PASS/FAIL GATE (5/5)
1. Idle: gateway-endpoint only, zero interface endpoints.
2. Created + `available` (tagged) before RunInstances.
3. Detonation succeeds host-native through the ephemeral endpoints; verdict-free
   outcome on the Hub record (no regression vs 2.3).
4. Interface endpoints deleted after the run (back to gateway-only).
5. Start-of-run orphan sweep deletes a stale ZTIE-tagged endpoint; never touches a
   non-ZTIE endpoint.
- Goes ✅ ONLY when the stakeholder confirms a live pass AND you RECORD it in
  RUNBOOK.md + STORY_DETAIL.md 2.0E. No recorded pass → stays 🟡. On any fail: stay on
  2.0E, fix, re-validate.

# ON PASS (and only then)
- Record the dated Validation Result in STORY_DETAIL 2.0E + the RUNBOOK master table;
  flip 2.0E ✅ (paired status commit); CLEAR 2.0E from the Validation Debt Register
  (register → empty, note it); keep PLAN ↔ RUNBOOK aligned; re-run `check_docs.py`
  (PASS). Because the 2.0 stack changed shape, REFRESH the Forensic deployed-state
  restore point / manifest and update BOM (the pending-refresh notes become actuals).

# ENVIRONMENT
- Repo cloned; push to `feature/story-2.0E`, never main. Open PRs via
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls` (NOT `gh pr create`). Merges are
  the repo-owner's action. Live AWS is the stakeholder's Forensic/Hub CloudShell action.

# WORKING AGREEMENT
- This is a VALIDATE-then-RECORD session: verify the branch is green → STAKEHOLDER
  validates live → you RECORD verbatim + flip status → paired status commit (+ refresh
  restore point). If a live check fails, fix on the branch and re-validate ONCE (fix
  the code you'll actually keep — never validate-the-wrong-thing).
- MANAGEMENT ARTIFACTS ARE FIRST-CLASS (RD-015): brief + RUNBOOK + PROJECT_PLAN aligned;
  RD-027 + candidate mappings recorded; all via PR; governance restorable alongside code.
- At session end, if 2.0E is ✅, recommend the next story (2.6 fork / 2.4 telemetry per
  the sequencing rule) with a one-line reason, and fold this session's real Lessons
  Learned into that story's prompt. Zero cold-start.
- If blocked, push partial progress + a draft PR; surface the blocker; never silently
  fail.
