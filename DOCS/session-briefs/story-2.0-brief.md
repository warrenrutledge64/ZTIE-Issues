# Session Brief — Story 2.0

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.

---

## Story 2.0 — AWS infra foundation (Phase-2 shared infrastructure, Forensic)

| Field | Value |
|-------|-------|
| **Phase** | P2 — Parallel Inspection |
| **Date** | 2026-08-31 |
| **Status** | 🟡 In Progress — built; awaiting live validation in Forensic |
| **Builds from restore point** | none yet (the Phase-1 close / `restore/phase-1-green` capture is deferred to a governance session; it does **not** block 2.0, which depends on 1.3 ✅) |
| **Session goal** | Deploy the **shared Phase-2 infrastructure foundation** in the Forensic account that ALL of Phase 2 (and, transitively, the Forensic-side work of Phases 3–4) stands on: an **isolated VPC** (VPC endpoints only, zero internet egress), **IAM roles**, a **per-run EC2 launch template** (parametric AMI, host-native SSM, 5-minute hard TTL), **SSM wiring**, and **Bedrock Nova Pro** access. Build the network + identity + launch template; build NO analysis logic. |

---

### Background & Context

Phase 1 is complete (1.1, 1.1R, 1.R, 1.2, 1.3, 1.4 all ✅). Phase 2 forks the
pipeline into two concurrent lanes — a **static** lane (non-executing scanners) and
a **dynamic** lane (detonation on an **ephemeral** EC2 host, host-native SSM, no
Docker). Both lanes, and everything downstream that touches the raw artifact, run in
the **Forensic account (360999005254)** — ZTIE's self-contained blast zone (RD-008).

Story 2.0 is the **first** Phase-2 story and the **shared foundation**: it creates
the isolated place the dynamic lane runs and the least-privilege identities it runs
as, so 2.3 (detonation chamber) and 2.4 (telemetry) have solid ground. Per the
project's execution order, the CDK infra must land **before** any Lambda/Step
Function code. It builds **no** scanners (2.1), **no** detonation Lambda/Step
Function (2.3), and **no** telemetry capture (2.4).

### Objective & Value

- **Objective:** a new standalone CDK v2 TypeScript stack, `ZtieForensicInfraStack`,
  deployed to Forensic, providing:
  1. an **isolated VPC** — `PRIVATE_ISOLATED` subnets only (no IGW, no NAT, no
     `0.0.0.0/0` route) so the detonation host **cannot phone home**;
  2. **VPC endpoints** — the only path off the VPC: S3 (gateway) + interface
     endpoints for SSM, SSM Messages, EC2 Messages, CloudWatch Logs, SQS, Bedrock;
  3. **IAM roles** — a detonation **instance role** (`AmazonSSMManagedInstanceCore`
     + Nova Pro invoke) and an **orchestrator role** (`ec2:RunInstances` +
     host-native SSM + tightly-scoped `PassRole`);
  4. an **EC2 launch template** — parametric AMI from SSM (`/ztie/ami/<flavor>`), the
     instance role + a no-inbound security group, **no key pair**, IMDSv2 required,
     encrypted root, and **UserData `shutdown -h +5`** (the 5-minute hard TTL);
  5. **SSM wiring** — publishes `/ztie/detonation/*` config params so 2.3 reads
     coordinates instead of hard-coding ids.
- **Why it matters:** this is the **containment wall** for the dynamic lane. The
  account boundary (RD-008), the isolated network (no egress), the SSM-only command
  channel (RD-001), and the hard TTL (RD-007) are what make detonating unknown code
  safe. Everything Phase-2/3/4 does on the Forensic side reuses this once-built
  foundation.

### Scope, Dependencies & Position

- **In scope:** the CDK stack (VPC + isolated subnets + endpoints, IAM roles, launch
  template, SSM wiring, Bedrock grant, `CfnOutput`s); registration in
  `infra/bin/ztie-infra.ts`; offline TS proof (`prettier --check`, `tsc --noEmit`).
- **Out of scope / do NOT touch:** static scanning code (2.1), the detonation
  Lambda/Step Function (2.3), telemetry capture (2.4), the intake/preprocessor
  stacks (P1), the Hub account, the Image-Builder AMI SSM parameters (`/ztie/ami/*`
  are **consumed, not created** here). Don't edit intentional `{{...}}` placeholders.
- **Depends on:** **1.3 ✅** (routing names the `dynamic_detonation` lane this
  foundation serves). Advancement gate satisfied. 2.0 **blocks 2.3**; it does **not**
  block 2.1 (static scanning depends only on 1.3).

### Mapping to ratified decisions

| Construct | Decision |
|-----------|----------|
| `PRIVATE_ISOLATED` subnets, no IGW/NAT, VPC endpoints only | RD-008 (Forensic containment) + RD-009 (Hub never touches payload) |
| Instance profile `AmazonSSMManagedInstanceCore`, no key pair, no SSH | RD-001 (host-native SSM, no Docker/containers) |
| UserData `shutdown -h +5` | RD-007 (5-minute hard TTL) |
| `bedrock:InvokeModel` scoped to `amazon.nova-pro-v1*` | RD-003 (Nova Pro correlation engine) |
| No DynamoDB / no bucket in this stack | RD-012 (no durable store in Forensic) |
| Static launch template; `RunInstances` is Story 2.3, not CFN-per-run | project execution order (CDK infra first) |

---

### As built (branch `feature/story-2.0`)

- **File:** `infra/lib/ztie-forensic-infra-stack.ts` (`ZtieForensicInfraStack`),
  registered in `infra/bin/ztie-infra.ts`. **Standalone** — no cross-account
  dependency; deploys directly to Forensic with Forensic credentials.
- **Isolated VPC:** `10.90.0.0/16`, 2 AZs, `natGateways: 0`, only
  `PRIVATE_ISOLATED` subnets → no IGW, no NAT, no `0.0.0.0/0` route. VPC flow logs
  (ALL). Endpoint SG (in-VPC `:443` ingress) + detonation-host SG (no inbound;
  egress in-VPC `:443` only, `allowAllOutbound:false`).
- **VPC endpoints:** S3 gateway + interface endpoints SSM, SSM Messages, EC2
  Messages, CloudWatch Logs, SQS, Bedrock runtime.
- **IAM:** detonation **instance role** (`AmazonSSMManagedInstanceCore` +
  `bedrock:InvokeModel`/`…WithResponseStream` on `amazon.nova-pro-v1*`);
  **orchestrator role** (`ec2:RunInstances`/tag/terminate/describe region-scoped,
  SSM `SendCommand`/`Get*`/`Describe*`, `iam:PassRole` → only the instance role,
  only to `ec2.amazonaws.com`).
- **Launch template `ztie-detonation`:** `MachineImage.fromSsmParameter(
  '/ztie/ami/<flavor>')` (default `ubuntu-22.04`), t3.small, instance role +
  detonation SG, **no key pair**, `requireImdsv2`, encrypted gp3 root, no public IP,
  **UserData `shutdown -h +5`**.
- **SSM wiring:** `/ztie/detonation/{launch-template-id,instance-role-arn,
  isolated-subnet-ids,ami-flavor}`. **8 `CfnOutput`s** for the validation handoff.
- **Local proof (sandbox INTEGRATIONS_ONLY — no npm/`aws-cdk-lib`, cannot
  `cdk synth`/`deploy`):** `prettier --check` clean; `tsc --noEmit` shows only the
  environmental missing-module error family identical to the two already-live stacks
  — zero genuine defects.

---

### Live deploy + validation (USER, in AWS CloudShell, FORENSIC account)

> **Account check first, every block.** This stack deploys to **Forensic
> (360999005254)** with **ambient** CloudShell credentials (no `--profile`). Run
> commands **one line at a time**. `/tmp` is wiped on session recycle.

**0) Confirm you are in Forensic, then get the code + deps.**
```
aws sts get-caller-identity   # Account must be 360999005254
git clone https://<TOKEN>@github.com/warrenrutledge64/ZTIE-Issues.git
cd ZTIE-Issues/infra
git checkout feature/story-2.0
npm install          # NOT npm ci (no lock file). If the home partition fills:
                     #   rm -rf ~/.npm ~/.cache node_modules && docker system prune -af
```

**1) Confirm the AMI SSM parameter this stack will resolve exists.** (Default flavor
`ubuntu-22.04` — the one known live: `ami-088e04fb4c75334c4`.)
```
aws ssm get-parameter --name /ztie/ami/ubuntu-22.04 --query Parameter.Value --output text
# If you want a different flavor: deploy with -c amiFlavor=al2023 (must exist in SSM).
```

**2) Bootstrap (if this account/region was never bootstrapped) + deploy ONLY this stack.**
```
npx cdk bootstrap aws://360999005254/us-east-1   # one-time per account/region
npx cdk deploy ZtieForensicInfraStack            # review the IAM/VPC changes, approve
```

**3) DoD live checks (the PASS/FAIL gate).** Capture the outputs first:
```
aws cloudformation describe-stacks --stack-name ZtieForensicInfraStack \
  --query "Stacks[0].Outputs" --output table
```
Then confirm each of the seven:
1. **Stack deploys** — `describe-stacks` shows `StackStatus=CREATE_COMPLETE` (or `UPDATE_COMPLETE`).
2. **Isolated subnets (no IGW/NAT)** — for the `VpcId` output:
   ```
   aws ec2 describe-internet-gateways --filters Name=attachment.vpc-id,Values=<VpcId>   # -> empty
   aws ec2 describe-nat-gateways --filter Name=vpc-id,Values=<VpcId>                      # -> empty
   ```
3. **VPC endpoints** exist for SSM, SSM Messages, EC2 Messages, CW Logs, S3, Bedrock:
   ```
   aws ec2 describe-vpc-endpoints --filters Name=vpc-id,Values=<VpcId> \
     --query "VpcEndpoints[].ServiceName" --output text
   ```
4. **Launch template + valid AMI via SSM** — the `AmiParameterName` output is
   `/ztie/ami/ubuntu-22.04`; confirm the template exists and resolves:
   ```
   aws ec2 describe-launch-templates --launch-template-names ztie-detonation
   aws ec2 describe-launch-template-versions --launch-template-name ztie-detonation \
     --versions '$Latest' --query "LaunchTemplateVersions[0].LaunchTemplateData"
   ```
   (The `ImageId` shows as `resolve:ssm:/ztie/ami/ubuntu-22.04` — a valid parametric ref.)
5. **Instance profile has `AmazonSSMManagedInstanceCore`** — from the
   `DetonationInstanceRoleArn` output (role name is the last path segment):
   ```
   aws iam list-attached-role-policies --role-name <role-name> \
     --query "AttachedPolicies[].PolicyName" --output text
   ```
6. **UserData contains `shutdown -h +5`** — decode the launch template UserData:
   ```
   aws ec2 describe-launch-template-versions --launch-template-name ztie-detonation \
     --versions '$Latest' \
     --query "LaunchTemplateVersions[0].LaunchTemplateData.UserData" --output text \
     | base64 -d
   ```
7. **No `0.0.0.0/0` route** — for each route table in the VPC:
   ```
   aws ec2 describe-route-tables --filters Name=vpc-id,Values=<VpcId> \
     --query "RouteTables[].Routes[?DestinationCidrBlock=='0.0.0.0/0']"   # -> [] for all
   ```

**On PASS:** report the outputs + confirmations; the executor records the dated
Validation Result and flips 2.0 → ✅ (paired status commit). **On FAIL:** report what
failed; 2.0 stays 🟡 and the next session re-focuses on fixing it.

---

### Definition of Done (this session) — a PASS/FAIL gate

The user, live in Forensic, confirms: (1) stack deploys; (2) VPC has isolated
subnets (no IGW/NAT); (3) endpoints for SSM/SSM Messages/EC2 Messages/CW Logs/S3/
Bedrock; (4) launch template exists + references a valid AMI via SSM; (5) instance
profile has `AmazonSSMManagedInstanceCore`; (6) UserData contains `shutdown -h +5`;
(7) no `0.0.0.0/0` route. Goes ✅ ONLY when confirmed live AND recorded in RUNBOOK.md.

### Management-artifact obligations (RD-015)

- [x] RUNBOOK 2.0 detail block filled with "As built"; summary row → 🟡.
- [x] PROJECT_PLAN Phase-2 story-set lists the infra foundation (plan ↔ runbook aligned).
- [x] RUNBOOK detail-header drift for 1.3/1.4 reconciled (🟡 → ✅, matching their ✅ summary rows + recorded passes).
- [x] This brief authored.
- [ ] On validation pass: record Validation Result + flip ✅ (paired commit).
- [ ] Next-story handoff (2.1) brief + prompt authored with Lessons Learned.
