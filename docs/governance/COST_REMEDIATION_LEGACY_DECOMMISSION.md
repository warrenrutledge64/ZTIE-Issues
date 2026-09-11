# Cost Remediation — Decommission of Legacy Off-Architecture Lineages

> **Status:** COMPLETE — both accounts confirmed torn down 2026-09-10.
> **Trigger:** unexpected VPC spend flagged in the Hub (641628980935) and Forensic
> (360999005254) accounts.
> **Registered decision:** [RD-031](../../PROJECT_PLAN.md#5-registered-decisions).
> **Nature:** operational / infrastructure cleanup — removal of stale CloudFormation
> stacks from **earlier ZTIE architectures** that predate the current CDK monorepo
> (`infra/`, the six `Ztie*Stack` stacks). No current ZTIE infrastructure and no PDE
> infrastructure was touched.

## 1. Why

Investigation of VPC charges surfaced **two stale, off-architecture ZTIE lineages**
still deployed and billing — neither present in this repository's current CDK app
(`infra/bin/ztie-infra.ts`, which defines exactly `ZtieHubTrackingStack`,
`ZtieIntakeStack`, `ZtieForensicInfraStack`, `ZtieStaticScanStack`,
`ZtieDetonationStack`, `ZtieOrchestrationStack`).

The dominant cost driver in each account was **interface VPC endpoints** (each bills
per-AZ-per-hour 24/7 regardless of use), attached to VPCs created by superseded
detonation-chamber prototypes.

## 2. Diagnosis method (read-only)

All diagnosis used read-only AWS CLI calls (`describe-*`, `list-exports`,
`get-caller-identity`) run from the account's own CloudShell. The reusable auditor
is [`scripts/vpc_cost_audit.py`](../../scripts/vpc_cost_audit.py). The **owning
CloudFormation stack** of each billable VPC was confirmed via its
`aws:cloudformation:stack-name` resource tag before any deletion — identity was
established from tags, never inferred.

## 3. What was found

### Hub account — 641628980935

| VPC | CIDR | Owning stack | Endpoints | Identity (from tags) |
|-----|------|--------------|-----------|----------------------|
| `vpc-0d31e36f0ebd16c2e` | `10.0.0.0/16` | **`ZtieNetwork-dev`** | 8 interface × 2 AZs = 16 ENIs (~$115/mo) | `Name=ztie-detonation-vpc-dev`, `ztie:project=detonation-chamber`, `ztie:environment=dev`, `ztie:managed-by=cdk` |

`ZtieNetwork-dev` was one of a six-stack `-dev` lineage
(`ZtieNetwork-dev`, `ZtieCompute-dev`, `ZtieStorage-dev`, `ZtieWorkflow-dev`,
`ZtieOrchestration-dev`, `ZtieOrchestration-dev`) plus a failed
`ztie-submit-api` stack (`ROLLBACK_COMPLETE`, never successfully deployed).

**Architecture note:** a `detonation-chamber` VPC in the **Hub** is off-architecture
by RD-008 — the Hub is the control plane and is deliberately kept OUT of the blast
zone; detonation belongs in **Forensic**. This `-dev` lineage is a prototype from
before the Forensic topology and the current CDK monorepo were settled.

### Forensic account — 360999005254

| VPC | CIDR | Owning stack | Endpoints | Identity (from tags) |
|-----|------|--------------|-----------|----------------------|
| `vpc-06334ba0f53a93e39` | `10.100.0.0/16` | **`Forensic-Network-Perimeter`** | 9 interface × 1 AZ (~$65/mo) + a long-running `t3.micro` (`Forensic-Linting-Runner`, up since 2026-07-16) | `Name=Forensic-Isolated-VPC` |

The current, in-repo ZTIE detonation VPC in Forensic is the **separate**
`vpc-0457ce09693cc48e4` (`10.90.0.0/16`), owned by `ZtieForensicInfraStack`, with
exactly the 3 always-on SSM control-channel endpoints per RD-027 (~$22/mo — expected
and **retained**). `Forensic-Network-Perimeter` exports nothing (absent from
`list-exports`), so nothing imports from it — it is a self-contained orphan.

## 4. What was KEPT (explicitly not touched)

- **Current ZTIE (both accounts):** the six `Ztie*Stack` stacks and `CDKToolkit`.
- **Forensic real detonation VPC:** `vpc-0457ce09693cc48e4` / `ZtieForensicInfraStack`
  (the 3-SSM-endpoint VPC, ~$22/mo, RD-027 — correct and load-bearing).
- **All PDE infrastructure:** every `PDE-*` / `pde-*` stack in the Hub (the Hub is a
  shared PDE + ZTIE control plane; PDE is out of scope for this cleanup).
- **`StackSet-PDE-CrossAccount-Deployer-*`:** a StackSet instance governed from
  elsewhere — never deleted locally.

## 5. Actions taken

### Hub (executed 2026-09-10)

Deleted in dependency order (consumers first so CloudFormation could release the
network stack's exports), via `aws cloudformation delete-stack`:

1. `ZtieOrchestration-dev` → DELETE_COMPLETE
2. `ZtieWorkflow-dev` → DELETE_COMPLETE
3. `ZtieCompute-dev` → DELETE_COMPLETE
4. `ZtieStorage-dev` → DELETE_COMPLETE
5. `ztie-submit-api` (dead `ROLLBACK_COMPLETE`) → DELETE_COMPLETE
6. `ZtieNetwork-dev` → deletes the `ztie-detonation-vpc-dev` VPC + its 16 endpoint
   ENIs (drains last)

**Estimated saving: ~$115/mo.**

**Confirmed complete 2026-09-10:** `ZtieNetwork-dev` reached `DELETE_COMPLETE` and
`vpc-0d31e36f0ebd16c2e` returns `InvalidVpcID.NotFound` (VPC + all 16 endpoint ENIs
gone). No `DELETE_FAILED` events. **Estimated saving: ~$115/mo.**

### Forensic (executed 2026-09-10)

```
aws cloudformation delete-stack --region us-east-1 --stack-name Forensic-Network-Perimeter
```

**First attempt hit `DELETE_FAILED`** on `EndpointsSecurityGroup`
(`sg-0ee3ec8c0d30e63d1`) and `AnalysisSubnet` (`subnet-02866d00a77c1f3b5`), both
"has a dependent object". Cause (read back from `describe-stack-events` +
`describe-network-interfaces`): **6 interface VPC endpoints were still `available`**,
and their `vpc_endpoint`-type ENIs pinned the subnet and security group. Resolution:

```
aws ec2 delete-vpc-endpoints --region us-east-1 --vpc-endpoint-ids \
  vpce-0cfe06096da38a375 vpce-0149017cdafa12121 vpce-052b98cf9c052ebec \
  vpce-085de0a7a60118f87 vpce-06550124cbf03457c vpce-0ad6299f6b5282b46
# wait ~2-3 min for endpoint ENIs to detach + delete, and for the terminated
# Forensic-Linting-Runner instance ENI to auto-clear, then retry the stack delete
aws cloudformation delete-stack --region us-east-1 --stack-name Forensic-Network-Perimeter
```

**Confirmed complete 2026-09-10:** stack `DELETE_COMPLETE`, zero endpoints remain in
the VPC, and `vpc-06334ba0f53a93e39` returns `InvalidVpcID.NotFound`. The instance
ENI cleared on its own once the instance finished terminating. **Estimated saving:
~$70/mo.**

> **Operational lesson (interface-endpoint VPC teardown):** a CloudFormation
> `delete-stack` on a VPC carrying interface VPC endpoints can fail on the subnet /
> endpoint-SG with a "dependent object" error because the endpoints' ENIs are slow
> to detach. `delete-stack` is async (a re-list may still show resources mid-delete
> — that is `deleting`, not stuck). Fix: delete the interface endpoints directly,
> wait 2-3 min for their ENIs to clear, then re-run `delete-stack` — CloudFormation
> retries only the resources it could not remove and completes. The service names
> the exact blocking resource in `describe-stack-events`, so this is dependency
> safety, not a mystery.

## 6. Verification

- Per-stack: re-poll `describe-stacks ... StackStatus` until `DELETE_COMPLETE`
  (absent stack = done).
- VPC gone: `aws ec2 describe-vpcs --vpc-ids <id>` returns `InvalidVpcID.NotFound`.
- If a network-stack delete reports `DELETE_FAILED`, the cause is read back from
  `describe-stack-events` (CloudFormation names the blocking resource); this is the
  service enforcing dependency safety, not an inference.

## 7. Reversibility

These are superseded prototypes not present in the repo, so the durable source of
truth is the current CDK app. Stack templates can be exported before deletion with
`aws cloudformation get-template --stack-name <S>` for an extra safety copy if a
future forensic need arises.

## Candidate control mappings (RD-014)

- NIST SP 800-53 Rev 5: **CM-8** (System Component Inventory), **CM-2** (Baseline
  Configuration), **SA-9** (External System Services), **CM-7** (Least
  Functionality), **PM-6 / cost-relevant SA-2** (resource stewardship).
- NIST CSF: **ID.AM-1 / ID.AM-2** (asset inventory), **PR.IP-1** (baseline).
- ISO/IEC 27001:2022 Annex A: **A.8.9** (Configuration management), **A.5.9**
  (Inventory of information and other associated assets).

_All mappings **proposed** (candidate-until-ratified per RD-014)._
