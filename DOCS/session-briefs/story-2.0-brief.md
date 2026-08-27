# Session Brief — Story 2.0

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.

---

## Story 2.0 — AWS infra foundation (CDK v2: VPC/isolated subnets, IAM, launch template, SSM, Nova Pro access)

| Field | Value |
|-------|-------|
| **Phase** | P2 — Parallel Inspection Paths |
| **Date** | _(set when the session starts)_ |
| **Status** | ⬜ Not Started |
| **Builds from restore point** | `restore/phase-1-green` _(captured at the P1 close; if that hasn't happened yet, build off main after all P1 stories ✅)_ |
| **Session goal** | Deploy the shared CDK v2 TypeScript infrastructure stack in the **Forensic** account that all of Phase 2 depends on: VPC with isolated subnets (VPC endpoints only, no NAT/IGW), IAM roles for the detonation host + scanners, a per-run EC2 launch template (parametric AMI selection), SSM wiring, and Bedrock Nova Pro access grants. This is the foundation that Phase-2 stories 2.1–2.6 and Phase-3 hang off. |

---

### Background & Context

Phase 1 is complete: 1.1 ✅ (intake), 1.1R ✅ (durable record → Hub), 1.R ✅
(restore), 1.2 ✅ (classifier), 1.3 ✅ (router), 1.4 ✅ (safe-reject). The intake
gateway accepts artifacts, classifies them, routes them to the correct lane, and
safely refuses unroutable ones — all recorded on the Hub tracking record. **Phase 2
begins now.** Both Phase-2 lanes (static scanning + dynamic detonation) need shared
infrastructure in the Forensic account: an isolated network, IAM, a launch template,
and SSM. Story 2.0 lays that foundation.

### Objective & Value

- **Objective:** a **CDK v2 TypeScript stack** (`ZtieForensicInfraStack` or similar)
  deployed into the **Forensic account (360999005254)** that stands up:
  - A **VPC** with **isolated subnets** (no internet gateway, no NAT; only VPC
    endpoints for the AWS services the detonation host and scanners need — S3, SQS,
    SSM, CloudWatch Logs, Bedrock, EC2 Messages, SSM Messages).
  - **IAM roles**: (a) an EC2 instance profile for the ephemeral detonation host
    (least-privilege: SSM managed instance, CloudWatch Logs put, S3 put for telemetry
    upload, bounded by the VPC — no internet egress); (b) a role for the scanning
    Lambdas/Step Functions to invoke the launch template and read scan results.
  - A **per-run EC2 launch template** with parametric AMI selection per OS flavor
    (`al2023` / `ubuntu-22.04` / `rhel-9`), the isolated subnet placement, the
    instance profile, and a **5-minute hard TTL** via UserData `shutdown -h +5`.
  - **SSM wiring**: the VPC endpoints + instance profile needed for host-native SSM
    command execution on the ephemeral EC2 (no SSH, no Docker — SSM only).
  - **Bedrock Nova Pro access**: IAM permission for the correlation Lambdas (Phase 3)
    to invoke `bedrock:InvokeModel` on the Nova Pro model. The permission is laid now
    so Phase 3 doesn't need to re-deploy infra.
- **Why it matters:** nothing in Phase 2 can run without this. The detonation chamber
  (2.3) needs the VPC + launch template + SSM. The static scanners (2.1) need the
  IAM roles. The telemetry pipeline (2.4/2.5) needs S3/SQS endpoints. Nova Pro (Phase
  3) needs the Bedrock grant. This is slot #2 in the strict execution order.

### Scope, Dependencies & Position

- **In scope:** the CDK stack (TypeScript); VPC + isolated subnets + VPC endpoints;
  IAM roles (detonation host instance profile, scanner/orchestrator role, Nova Pro
  invoke role); EC2 launch template (parametric AMI via SSM parameters, UserData
  hard-TTL, instance profile, subnet placement); SSM agent wiring (VPC endpoints
  only); Bedrock Nova Pro `InvokeModel` grant; outputs for downstream stories to
  reference. Production-quality CDK, deployable to Forensic.
- **Out of scope / do NOT touch:** the static scanning code (2.1), the detonation
  Lambda/Step Function (2.3), any telemetry capture (2.4), the intake/preprocessor
  stacks (P1 — only reference their outputs if needed), the Hub account (this stack
  goes to Forensic). Don't edit intentional `{{...}}` template placeholders.
- **Depends on:** **1.3 ✅** (per the runbook dependency column; effectively all of
  Phase 1 being complete since 1.3 unblocks Phase 2).
- **Unblocks:** **2.3** (detonation chamber needs the VPC + launch template + SSM),
  **2.1** (static scanning needs IAM), and transitively all of 2.4–2.6 + Phase 3.
- **Roadmap position:** first story of Phase 2; the shared infrastructure foundation
  for the entire inspection pipeline.

### Approach & Constraints

- **Approach:**
  1. Define the VPC (2–3 AZs, isolated subnets only, no public/private with NAT).
  2. Add VPC endpoints (Interface: SSM, SSM Messages, EC2 Messages, CloudWatch Logs,
     Bedrock; Gateway: S3). Security groups scoped to HTTPS (443) inbound from the
     VPC CIDR only.
  3. Define the instance profile (managed policies: `AmazonSSMManagedInstanceCore`;
     inline: bounded CloudWatch Logs + S3 telemetry put).
  4. Define the launch template: parametric AMI (resolve from SSM parameters
     `/ztie/ami/<flavor>`), instance type parameter (default `m5.large`), the
     instance profile, the isolated subnet, UserData that runs `shutdown -h +5`
     (hard 5-minute TTL — the detonation host is ephemeral and self-destructs).
  5. Define the scanner/orchestrator role and the Nova Pro invoke role.
  6. Outputs: VPC ID, subnet IDs, launch template ID/version, role ARNs, endpoint
     IDs — everything downstream stories need.
- **Hard constraints:**
  - **CDK v2 TypeScript** for infrastructure (project standard).
  - **Forensic account (360999005254)** — the blast zone. All Phase-2 execution
    happens here.
  - **Isolated subnets only** — NO internet egress. The detonation host cannot phone
    home; it reaches AWS services exclusively via VPC endpoints.
  - **Host-native SSM on EC2** — no Docker, no containers, no SSH. SSM is the only
    command channel.
  - **5-minute EC2 hard TTL** via UserData `shutdown -h +5`. Non-negotiable.
  - **Parametric AMI selection** per OS flavor (al2023/ubuntu-22.04/rhel-9) via SSM
    parameters — NOT hard-coded AMI IDs.
  - **`ec2:RunInstances` via launch template** (NOT CloudFormation per run).
  - Production code. Validation-gated.

### Validation Rationale & Compliance Mapping (REQUIRED — RD-014)

- **Rationale:** this stack establishes the **network isolation boundary** (the
  detonation host has no internet egress), the **least-privilege IAM posture** for
  Phase-2 compute, the **time-bounded execution** (5-min TTL), and the **controlled
  command channel** (SSM only, no SSH). These are the foundational security controls
  Phase 2 rests on.
- **Candidate control mappings** *(candidate-until-ratified):*

| Framework | Control ID | Control Name | Rationale | Status |
|-----------|-----------|--------------|-----------|--------|
| NIST 800-53 r5 | SC-7 | Boundary Protection | Isolated subnets + VPC endpoints only = no internet egress for detonation; the network boundary is the containment wall | Proposed |
| NIST 800-53 r5 | AC-6 | Least Privilege | IAM roles scoped to exactly the permissions each component needs (instance profile, scanner role, Nova Pro role) | Proposed |
| NIST 800-53 r5 | SC-7(5) | Deny by Default / Allow by Exception | No internet route exists; only allow-listed VPC endpoints provide AWS service access | Proposed |
| NIST 800-53 r5 | SI-14 | Non-Persistence | The 5-minute hard TTL ensures the detonation host is ephemeral and self-destructs; no persistent compute in the blast zone | Proposed |
| NIST 800-53 r5 | AC-17 | Remote Access | SSM is the only command channel (no SSH, no Docker); access is authenticated, encrypted, and logged by AWS | Proposed |
| NIST 800-53 r5 | CM-7 | Least Functionality | Launch template enforces a minimal, locked-down configuration; no unnecessary services/ports | Proposed |
| ISO 27001:2022 | A.8.22 | Segregation of networks | The VPC with isolated subnets is the network segregation control between detonation and the outside world | Proposed |
| ISO 27001:2022 | A.8.2 | Privileged access rights | IAM roles are least-privilege; the instance profile has no admin/power-user policy | Proposed |

- **Audit evidence produced:** the deployed CloudFormation stack + its resource
  inventory + the live validation confirming isolated networking and launch template
  exist.

### Management-Artifact Obligations (REQUIRED — RD-015)

- [ ] Story's **brief + runbook entry** updated (status, validation result, dates).
- [ ] **PROJECT_PLAN and RUNBOOK in exact alignment**.
- [ ] Candidate control mappings recorded (RD-014).
- [ ] All doc changes **PR-reviewed** (branch + PR, never straight to main).
- [ ] Governance kept **restorable** alongside the code.

### Change & Rollback

- **Change type:** normal (adds a new CDK stack to the Forensic account).
- **Restore point this builds from:** `restore/phase-1-green` (or main after P1 ✅).
- **Backout plan:** `cdk destroy ZtieForensicInfraStack` removes the VPC + roles +
  launch template cleanly (no data loss — this is pure infrastructure).

### Definition of Done / Validation Gate

- **Done means:** the user, live in the **Forensic** account, confirms:
  1. The CDK stack deploys successfully (`✅ ZtieForensicInfraStack`).
  2. The VPC exists with **isolated subnets** (no internet gateway, no NAT).
  3. VPC endpoints exist for the required services (SSM, SSM Messages, EC2 Messages,
     CloudWatch Logs, S3, Bedrock).
  4. The **launch template** exists and references a valid AMI via SSM parameter
     resolution.
  5. The **instance profile** exists and has the `AmazonSSMManagedInstanceCore`
     managed policy.
  6. The **5-minute hard TTL** is in the launch template's UserData.
  7. No internet route exists in the route tables (isolated = no 0.0.0.0/0 route).
- **Validated by:** the user, live (Forensic account, `aws` CLI checks).
- **Validation Result:** _pending._
- **On pass (and only then):** record the dated Validation Result + flip 2.0 ✅.
- **On fail:** stays 🟡; next session re-focuses on 2.0.
- **Advancement gate:** blocks 2.3 (detonation needs the VPC + launch template).

### Risks & Watch-Items

- **VPC endpoint costs.** Interface endpoints cost ~$7.50/mo/AZ/endpoint. With 5
  interface endpoints × 2–3 AZs = $75–$112/mo. Acceptable for a security pipeline
  but worth noting. Gateway endpoints (S3) are free.
- **AMI SSM parameters must exist.** The launch template resolves AMI IDs from SSM
  parameters (`/ztie/ami/al2023`, etc.). If these don't exist yet, the launch
  template will fail to create instances. The Image Builder (a separate concern) is
  responsible for populating them. For validation, at least one must be manually set
  (the Ubuntu 22.04 AMI `ami-088e04fb4c75334c4` is already in SSM from a prior
  session).
- **Bedrock Nova Pro model access.** The Bedrock `InvokeModel` grant requires that
  the model is enabled in the account/region. Confirm Bedrock model access is
  provisioned in Forensic (or decide if Nova Pro invocation runs from Hub and the
  derived telemetry crosses to it — align with ARCHITECTURE.md).
- **Do NOT build the detonation logic.** 2.0 is infrastructure only. The Lambda /
  Step Function that actually calls `ec2:RunInstances` with this launch template is
  Story 2.3. 2.0 just makes the resources exist.

### Lessons Learned / Carry-Forward *(from the Phase 1 sessions)*

- **From Phase 1 — what to reuse:**
  - **CDK stack pattern.** `ztie-intake-stack.ts` and `ztie-hub-tracking-stack.ts`
    are good templates: account guard (synth-time warning if wrong account), explicit
    tags, `CfnOutput` for every downstream-consumed value, clear doc comments.
  - **Two-account deploy.** Hub first (if Hub outputs are consumed), then Forensic.
    For 2.0 there is no Hub dependency — it deploys solely to Forensic. But the
    `bin/ztie-infra.ts` app entry needs the new stack registered.
  - **Docker bundling** was needed for the Hub validator Lambda (native rpds-py dep).
    2.0 is pure infra (no Lambda with Python deps) so Docker bundling shouldn't be
    needed here.
  - **`npm install` not `npm ci`** (no lock file in the repo).
  - **CloudShell disk space.** The 974MB home partition fills fast when Docker pulls
    images. `rm -rf ~/.npm ~/.cache node_modules` + `docker system prune -af` frees
    it. 2.0 shouldn't pull Docker images (no Lambda bundling) but watch for it.
- **From Phase 1 — environment truths (unchanged):**
  - Build sandbox is **INTEGRATIONS_ONLY** (no AWS creds, no PyPI/npm installs). You
    build + hand off; the user deploys from CloudShell.
  - **Local proof for CDK:** `npx tsc --noEmit` (TypeScript type check) + `prettier
    --check` (from `infra/` after `unset NODE_OPTIONS`). You CANNOT `cdk synth` or
    `cdk deploy` from the sandbox.
  - **Forensic account (360999005254).** Confirm with `aws sts get-caller-identity`
    before every deploy.
  - Push to `feature/story-2.0`, never main. PR via `gh api`.
- **Must-know / must-avoid for 2.0:**
  - **Isolated subnets** = `SubnetType.PRIVATE_ISOLATED` in CDK (NOT
    `PRIVATE_WITH_EGRESS`). There must be NO NAT gateway and NO internet gateway.
  - **UserData hard TTL:** `shutdown -h +5` in the launch template UserData. This is
    the non-negotiable self-destruct timer.
  - **SSM, not SSH.** No key pair on the launch template. The only command channel is
    SSM (requires the VPC endpoints + instance profile).
  - **Parametric AMI:** resolve from SSM parameters, not hard-coded IDs. CDK has
    `ec2.MachineImage.fromSsmParameter(...)` for this.
  - **The launch template is NOT a CDK Custom Resource that runs EC2.** It is a static
    template resource. The *use* of it (RunInstances) is Story 2.3.
- **User notes:** _(open for the user)_
