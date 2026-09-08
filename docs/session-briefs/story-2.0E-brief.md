# Session Brief — Story 2.0E

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.

---

## Story 2.0E — Cost remediation: ephemeral interface VPC endpoints

| Field | Value |
|-------|-------|
| **Phase** | P2 — Parallel Inspection (Forensic infra cost-remediation) |
| **Date** | 2026-09-07 (built); live validation pending |
| **Status** | 🟡 In Progress (built + offline-validated; pending live validation) |
| **Builds from restore point** | `restore/story-2.3-green` / `restore/phase-2-floor-green` (the validated 2.0 infra + detonation lane this modifies) |
| **Registered decision** | **RD-027** (proposed) |
| **Session goal** | Stop the ~`$88/mo` idle burn from the six always-on interface VPC endpoints in the Forensic detonation VPC by making them **ephemeral** — created per detonation, torn down after — with **no change to any containment invariant** and no functional regression to the Story 2.3 detonation flow. |

---

### Background & Context

ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted
artifact before it reaches the PDE; work is validation-gated (nothing is ✅ until a
recorded live pass — the covenant). Phase 1 is ✅. Phase 2's static lane (2.1/2.2) and
dynamic detonation lane (2.3) are ✅; the Forensic infra foundation (2.0) is ✅.

The stakeholder observed the Forensic account burning budget while idle. Investigation
(see Lessons Learned) traced it to the **six INTERFACE VPC endpoints** the 2.0 stack
creates always-on: they bill ~`$0.01/hr` each, per AZ, 24/7 (12 ENIs at `maxAzs: 2` ≈
`$88/mo`), yet they are only USED for the few minutes of an actual detonation. The
ephemeral EC2 host is NOT the burn (5-min TTL); the S3 gateway endpoint is free; the
VPC/subnets/roles/launch-template are free. The interface endpoints were ~the entire
idle cost. Story 2.0E makes them ephemeral.

### What This Story Is (nature + gate role)

**Nature: follow-forward COST-REMEDIATION on a validated story (RD-027).** Story 2.0
stays ✅ for what it validated; per the covenant we remediate forward, not retro-edit.
2.0E is the **sole open entry in the Validation Debt Register** — so the advancement
gate is armed against NEW unrelated feature stories, but reworking/validating 2.0E
itself is the permitted in-progress work. **STEP 0:** confirm 2.0E is the open
register entry and that `python3 scripts/check_docs.py` PASSes; do NOT start an
unrelated feature story until 2.0E clears.

### Objective & Value

- **Objective:** move the six interface endpoints (SSM, SSM Messages, EC2 Messages,
  CloudWatch Logs, SQS, Bedrock Runtime) from always-on to ephemeral. The durable 2.0
  stack keeps only the FREE scaffolding (isolated VPC + subnets, S3 gateway endpoint,
  endpoint SG, IAM roles, launch template) and publishes the coordinates; the
  detonation orchestrator sweeps orphans → creates the endpoints → waits `available`
  → detonates → deletes them in a `finally`.
- **Why it matters:** ~`$88/mo` of idle cost doing nothing, on the account the
  stakeholder flagged. Making just the interface endpoints ephemeral drives that to
  ~zero while keeping every containment invariant and adding no functional regression.

### Scope, Dependencies & Position

- **In scope:** remove the six always-on `addInterfaceEndpoint` calls from
  `ZtieForensicInfraStack`; publish `/ztie/detonation/{vpc-id,endpoint-service-names,
  endpoint-security-group-id}` + outputs; grant the orchestrator role + the 2.3 Lambda
  role a least-privilege `ec2:CreateVpcEndpoint`/`DeleteVpcEndpoints`/
  `DescribeVpcEndpoints` grant; add the ephemeral-endpoint lifecycle + start-of-run
  orphan sweep to `lambdas/detonation/` (`awsio.py` seam + `handler.py` wiring); tests.
- **Out of scope / do NOT touch:** the containment invariants (no IGW/NAT/`0.0.0.0/0`,
  host-native SSM, no SSH, 5-min hard TTL — all unchanged); the S3 **gateway** endpoint
  (stays always-on, free); **VPC Flow Logs** (deliberately left as-is — a cost/audit
  trade not worth mixing in); the detonation execution logic / outcome contract (2.3,
  unchanged); the static lane. Do NOT drop the Bedrock endpoint (see below).
- **Depends on:** **2.3 ✅** (the orchestrator this extends). Tier 5.
- **Unblocks:** clears the Validation Debt Register so the next feature story (2.6 fork
  / 2.4 telemetry, per the sequencing rule) may proceed.

### Approach & Constraints

- **Bedrock Runtime is KEPT in the ephemeral set (stakeholder decision, RD-027):**
  Phase 3 (Nova Pro correlation, Story 3.2) is intended to invoke Nova Pro from inside
  the isolated VPC. An idle ephemeral endpoint costs `$0`, so keeping Bedrock costs
  nothing and avoids a Phase-3 landmine. **Open lifetime question flagged for 3.2:** if
  correlation runs inside the VPC, the ephemeral-endpoint window must extend to cover
  correlation, not just detonation — the teardown boundary is deliberately explicit so
  3.2 decides consciously.
- **Resilience is bought back, not traded:** the one new failure mode (a crashed run
  leaving endpoints billing) is covered by a **start-of-run orphan sweep** (tag- +
  VPC-scoped, so it can never touch a non-ZTIE endpoint). Worst case reverts to the
  *old* idle cost until the next run mops it up; never a safety regression. No
  scheduled infra added (the sweep rides on the next detonation).
- **Roles:** the LIVE deploy + detonation + endpoint-lifecycle check is the
  **stakeholder's** action in Forensic (the executor has NO live creds); the executor
  RECORDS the returned output verbatim. Do NOT simulate/assume a live output.
- **Hard constraints:** no containment invariant may change; production code (no mock
  endpoints); docs first-class (RD-015), PR-reviewed; the story stays 🟡 until a
  recorded live pass (covenant).

### Validation Rationale & Compliance Mapping (REQUIRED — RD-014)

- **Rationale:** ephemeral endpoints are least-functionality + configuration hygiene —
  the isolated VPC exposes its PrivateLink attack surface + cost only while a
  detonation is actually running, and returns to a minimal (gateway-only) posture when
  idle. Containment (boundary protection, network segregation) is unchanged.
- **Candidate control mappings** *(proposed; ratified on review):*

| Framework | Control ID | Control Name | Rationale | Status |
|-----------|-----------|--------------|-----------|--------|
| NIST 800-53 r5 | SC-7 | Boundary Protection | The isolated VPC's only egress remains VPC endpoints; interface endpoints exist only during a run | Proposed |
| NIST 800-53 r5 | CM-6 | Configuration Settings | Endpoint set is provisioned to a defined, minimal-when-idle configuration | Proposed |
| NIST 800-53 r5 | CM-7 | Least Functionality | The PrivateLink surface is present only while needed (during detonation), removed when idle | Proposed |
| NIST 800-53 r5 | SA-9 | External System Services | Access to AWS services (SSM/Logs/SQS/Bedrock) is scoped to the run window | Proposed |
| NIST CSF | PR.PT-3 / PR.IP-1 | Least functionality / baseline configuration | Minimal-when-idle network posture; defined baseline | Proposed |
| ISO 27001:2022 | A.8.9 | Configuration management | Endpoint lifecycle is a managed, defined configuration | Proposed |
| ISO 27001:2022 | A.8.22 | Segregation of networks | The isolated VPC segregation is preserved unchanged | Proposed |

- **Audit evidence produced:** the dated Validation Result in RUNBOOK/STORY_DETAIL 2.0E;
  `describe-vpc-endpoints` showing gateway-only when idle, six tagged interface
  endpoints during a run, and gateway-only again after; a successful detonation outcome
  on the Hub record identical in shape to 2.3.

### Management-Artifact Obligations (REQUIRED — RD-015)

- [x] Story's brief + runbook entry created (status 🟡, Validation Result pending). Master table 2.0E → 🟡 (tier 5); Validation Debt Register now lists 2.0E; STORY_DETAIL 2.0E written to the "as built" + DoD form; human-readable summary added.
- [x] PROJECT_PLAN and RUNBOOK in exact alignment (RD-027 registered in PLAN; per-story status lives in the RUNBOOK single-pane, 2.0E = 🟡 there; the RD narrative + story detail agree).
- [x] New registered decision recorded: **RD-027** (ephemeral interface endpoints; candidate mappings SC-7/CM-6/CM-7/SA-9, CSF PR.PT-3/PR.IP-1, ISO A.8.9/A.8.22 — all Proposed).
- [x] `scripts/check_docs.py` re-run and PASS; governance self-tests (`scripts/test_check_docs.py`) still pass (3/3).
- [x] BOM updated (forensic infra row notes ephemeral endpoints; SSM-params row notes the three new params + pending-refresh on 2.0E validation).
- [x] All doc changes PR-reviewed (branch `feature/story-2.0E` + PR, never straight to main).
- [ ] On validation pass: record Validation Result + flip ✅ (paired commit); clear 2.0E from the register; refresh the Forensic deployed-state restore point (the 2.0 stack changed shape). **PENDING the stakeholder's live run.**
- [x] Author the next-story handoff (2.0E-PROMPT.md) with real Lessons Learned.

### Change & Rollback

- **Change type:** cost/lifecycle remediation on a validated stack (no containment
  change). Modifies `ZtieForensicInfraStack` + the 2.3 detonation lane.
- **Restore point this builds from:** `restore/story-2.3-green` / `restore/phase-2-floor-green`.
- **Backout plan:** if a check fails, 2.0E stays 🟡; fix + re-validate. If a status flip
  is later found unwarranted, revert the paired status commit. Because the always-on
  free scaffolding is unchanged, reverting the CDK to the always-on endpoints is a clean
  redeploy. An endpoint left billing after a run is the cost failure to watch — the host
  is still torn down by its hard TTL regardless (cost concern, not containment).

### Definition of Done / Validation Gate

> A pass/fail gate, not a description. The stakeholder validates live; the executor
> records; only a recorded pass flips status. (5/5.)

- **Done means (the stakeholder confirms live in Forensic 360999005254):**
  1. **Idle = no interface endpoints:** after deploying both stacks, with no detonation
     running, `describe-vpc-endpoints` for the detonation VPC shows the S3 **gateway**
     endpoint only — **zero** interface endpoints.
  2. **Created + `available` before launch:** during a detonation the six interface
     endpoints appear in the isolated subnet, tagged `ztie:ephemeral-endpoint=detonation`
     + the run's `IntakeId`, and reach `available` before `RunInstances`.
  3. **Detonation still succeeds through them:** ONE ephemeral EC2 launches from the 2.0
     template, the SSM agent comes Online (proves the ephemeral SSM endpoints work),
     runs host-native (`AWS-RunShellScript`), and the bounded verdict-free outcome
     crosses to the Hub — no functional regression vs. 2.3.
  4. **Torn down after:** once the run completes, `describe-vpc-endpoints` returns to
     gateway-endpoint-only (the six interface endpoints are deleted).
  5. **Orphan sweep works:** with a stale ZTIE-tagged endpoint present (simulate, or
     after an interrupted run), the NEXT detonation's start-of-run sweep deletes it and
     never touches a non-ZTIE endpoint.
- **Validated by:** the stakeholder, live; the executor records verbatim.
- **Validation Result:** `pending`.
- **On pass (and only then):** record the dated Validation Result, flip 2.0E ✅ (paired
  commit), clear the register entry, keep PLAN ↔ RUNBOOK aligned, refresh the Forensic
  restore point.
- **On fail:** 2.0E stays 🟡; fix + re-validate; no advancement.
- **Advancement gate:** 2.0E is the sole open register entry; clearing it re-opens NEW
  feature work.

### Risks & Watch-Items

- **Endpoint-availability latency.** Interface-endpoint ENIs must be `available` before
  the host's SSM channel can come Online; the handler waits up to
  `ENDPOINT_AVAILABLE_TIMEOUT_S=180` before launch. If a live run shows endpoints taking
  longer, raise the budget (still inside the 840s Lambda / 900s SQS-visibility window).
- **Teardown-on-crash.** A Lambda hard-timeout could skip the `finally` teardown; the
  start-of-run orphan sweep is the backstop. VERIFY the sweep live (DoD #5) — do not
  pass it on inference.
- **Do NOT re-introduce an S3 interface endpoint.** The S3 gateway endpoint stays; an S3
  interface endpoint with private DNS CONFLICTS with it (verified live during 2.3, PRs
  #54/#56). Only the six non-S3 services are ephemeral interface endpoints.
- **Bedrock endpoint stays** (Phase-3-in-VPC decision). Do not "optimize" it away.
- **Region-scoped IAM only.** The new endpoint-management grant is region-scoped and
  adds NO IGW/NAT/route creation — keep it that way (containment).

### Lessons Learned / Carry-Forward *(from the 2.0E build session, 2026-09-07)*

- **The idle burn was diagnosed to the interface endpoints, not the EC2 host.** The
  "ephemeral" instinct was right but the actual always-on cost was the 6 interface
  endpoints (per-AZ-per-hour, 24/7). The EC2 host self-terminates on its TTL and is
  cheap; the S3 gateway endpoint and the VPC/subnets/roles/launch-template are free.
  When reasoning about VPC cost, separate the FREE scaffolding from the per-hour ENIs.
- **Model A (ephemeral interface endpoints, durable free shell) beat Model B (fully
  ephemeral VPC).** A persistent empty isolated VPC costs `$0` and has no attack surface
  between runs, so recreating the VPC/subnet/gateway per run buys nothing and adds
  latency + IAM surface. Only the per-hour interface endpoints are worth making
  ephemeral.
- **Bedrock: keep it.** The 2.0 stack already grants the detonation instance role
  `bedrock:InvokeModel` and provisions the Bedrock endpoint in-VPC; Phase 3 correlation
  is intended to run in-VPC. Dropping the endpoint would optimize for today's 2.3 and
  break 3.2 silently. Idle ephemeral endpoints cost `$0`, so keeping it is free.
- **Sandbox is INTEGRATIONS_ONLY — no boto3/pytest/moto/cdk.** The new endpoint seam
  tests stub `boto3`/`botocore` and inject a fake into `awsio._ec2_client`; pure tests
  run under stdlib `unittest`. `ruff`/`prettier` live under the pyenv 3.12 toolchain
  (`~/.pyenv/versions/3.12.13/bin/`), not the default python. `tsc --noEmit` shows only
  the known missing-`aws-cdk-lib` baseline; grep the tsc output for the new symbols to
  prove no NEW error was introduced.
- **`check_docs.py` gate reality (recurs):** a `🟡` feature story MUST be in the
  Validation Debt Register (CHECK A) AND, because the register is otherwise empty, being
  in the register is exactly what keeps CHECK B green (an in-register entry is the
  allowed in-progress work). Put 2.0E in the register in the SAME commit you flip it 🟡.
- **Two-account live reality (recurs EVERY session):** deploy + detonate in **Forensic
  360999005254**; the tracking record is in the **Hub 641628980935**. Two CloudShell
  tabs; run `aws sts get-caller-identity` before EVERY operational block. `gh pr create`
  is broken — open PRs via `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`.
- **2.0 live facts this inherits:** VpcId `vpc-0457ce09693cc48e4`; Detonation
  LaunchTemplateId `lt-045ddce7fdac386db`; region us-east-1; ubuntu-22.04 AMI only
  (AL2023 build still broken). The new SSM params are published by the redeployed 2.0
  stack — the stakeholder must `cdk deploy ZtieForensicInfraStack` (Forensic) AND
  redeploy `ZtieDetonationStack` (new env + IAM) before the live detonation test.
- **LIVE FINDING (attempt 1, 2026-09-07) — the SSM-online race, now fixed.** The first
  live run proved the endpoint lifecycle works (created → available → host launched →
  torn down; idle = gateway-only; containment flags correct) but the detonation came
  back `outcome=delivery_error` / `ssm_status=not_run` — the artifact never executed
  because the SSM agent never reported Online. Root cause: a just-created interface
  endpoint's `State: available` PRECEDES its private-hosted-zone DNS propagation, and
  the SSM agent only (re)detects endpoints on (re)start; the host booted into the DNS
  gap and gave up. Fix on-branch: (a) pre-launch DNS-settle delay `ENDPOINT_DNS_SETTLE_S=45`
  after available/before RunInstances (pre-launch → does not eat the host TTL); (b)
  UserData restarts `amazon-ssm-agent` ~30s after boot to re-detect the endpoints; (c)
  `SSM_ONLINE_TIMEOUT_S` 120→150. **Watch on re-run:** DoD #3 now requires
  `ssm_status=Success` / `ZTIE-DETONATION-OK` / `outcome=completed` — the endpoint
  lifecycle passing is necessary but NOT sufficient. Also mind the 5-min host TTL: the
  post-launch budget (150s online + trivial exec) must finish before `shutdown -h +5`;
  the 45s settle is pre-launch so it is safe.
- **Operational recurses confirmed this session:** `awscurl` is NOT preinstalled in a
  fresh CloudShell — `pip install awscurl` (lands in `/usr/local/python3.13/bin`). The
  intake body contract is JSON `{filename, content_base64, content_type?, submitter?}`
  (base64 must be `-w0`, no wraps — `validate=True`). `cdk deploy` must run from
  `infra/` (needs `cdk.json` for `--app`) and `ZtieDetonationStack` only instantiates
  when its `-c` context values are supplied (bucket/queues/roleArn), so a bare
  `cdk deploy ZtieDetonationStack` says "No stacks match". `aws logs tail --follow`
  blocks silently until the Lambda fires; use `--since 10m` (no follow) to pull a
  window. The Hub tracking table (`ZtieHubTrackingStack-TrackingTable170A6688-133E30JVEWB1Z`)
  is in the HUB — read it from a Hub-authed tab, submit intake from a Forensic-authed
  tab.
- **PIVOT to two-tier (2026-09-07), after a 3-attempt live investigation.** Making ALL SIX endpoints ephemeral was DISPROVEN live: a booting host could not open a TCP connection to a same-run-created SSM endpoint (`curl … 000`/connect-timeout) even though DNS resolved to a private IP, SGs allowed it, the endpoint was `available`, and host+endpoint shared one AZ. Four theories (DNS propagation, SG, subnet, AZ) were each tested and rejected with live evidence; the DNS-settle + UserData agent-restart + sweep-drain mitigations treated wrong causes (agent-restart was harmful). Detonation passed only ~1/3. **Final design = two-tier:** SSM control channel always-on (single AZ, ~$22/mo, reliable like Story 2.3); logs/sqs/bedrock-runtime ephemeral (~$66/mo recovered). Key lesson: **the SSM control channel must be warm at boot — do NOT create it per run.** The non-boot-critical endpoints are safe to make ephemeral. Reverted the disproven fixes; kept the sweep drain-wait.
- **Two distinct VPC worries were separated (drove the story set).** Worry 1 = idle cost → Story 2.0E (this story). Worry 2 = tenant isolation → NEW stories **T.1/T.2/T.3** (RD-028). Per-run endpoint ephemerality does NOT isolate tenants sharing a VPC/account; the tenant boundary is the whole environment (recommended: per-tenant Forensic account, given ZTIE's existing multi-account topology). Run-to-run residue is already contained by the ephemeral host + wiped volume, NOT the endpoints (an interface endpoint has no surface a payload can write to).
- **User notes:** *(open for the stakeholder to add anything before the 2.0E re-run.)*
