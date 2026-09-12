# Cost Remediation — Decommission of Legacy Off-Architecture Lineages

> **Status:** COMPLETE — both accounts confirmed torn down 2026-09-10.
> **Trigger:** unexpected VPC spend flagged in the Hub (641628980935) and Forensic
> (360999005254) accounts.
> **Registered decision:** [RD-032](../../PROJECT_PLAN.md#5-registered-decisions).
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



## 8. Phase 2 — OD-001 Hub stale-stack cleanup (closed 2026-09-12)

Phase 1 (above) stopped the VPC/interface-endpoint bleed. Phase 2 removed the remaining
off-architecture / prototype **Hub** stacks that still carried Lambda/WAF/Cognito/S3 cost
but are absent from the current CDK app. Tracked as **OD-001** in the RUNBOOK Operational
Debt register; run live by the stakeholder in a `[HUB]` (641628980935) CloudShell on
2026-09-12, evidence pasted back and recorded (never on inference).

### Deleted (12 stacks, 13 incl. the nested IAM child) — all verified `GONE`

| Stack | Why stale |
|-------|-----------|
| `ztie-detonation-chamber-production` (+ nested `…-IAMRolesStack-ST8ZNAS04F0D`) | detonation in the Hub violates RD-008 (control plane out of the blast zone) |
| `aws-sam-cli-managed-default` | SAM deploy-artifacts leftover |
| `ztie-hub-frontend-stack`, `ztie-hub-backend-stack`, `ztie-hub-cognito-stack` | old dashboard/website lineage, not in the current CDK repo |
| `ztie-dev-identity`, `ztie-dev-hosting`, `ztie-dev-waf-shield` | old `-dev` lineage (WAF = standing monthly cost) |
| `PipelineStack` | stale self-mutating CDK pipeline (last updated 2026-08-15) |
| `ZTIE-Pipeline-Stack`, `ZTIE-CrossAccount-Pipeline` | stale/failed "Hub→Dev" pipelines (last updated 2026-07-27) |
| `ZTIE-IAM-Deployment-Stack` | IAM role for the two stale pipelines |

### Kept (safety upheld)

`ZtieHubTrackingStack`, `CDKToolkit`, `ztie-asymmetric-cmk` (live KMS attestation key,
referenced by ARN not CFN imports), and **all** `PDE-*` / `pde-*` stacks (incl.
`github-oidc-pde-burn`; the `pde-hub-governance-rules` `ROLLBACK_COMPLETE` is PDE's cruft to
clean, not ZTIE's). `whr-bucket-website-stack` (non-ZTIE/non-PDE) was **excluded** pending
owner confirmation — not deleted.

### Pre-delete safety checks

- **No live consumer:** every one of the 12 was confirmed `NOT IMPORTED` (or exports
  nothing) via `list-exports` + `list-imports` before any delete.
- **Run-recency:** the four pipeline stacks were confirmed months-stale (create/update
  2026-07-26…08-15) with no recent CodePipeline execution state.
- **Identity from tags/inventory**, not inference; delete order = consumers before
  exporters; nested child removed by deleting its parent (not by name).

### Delete-time unblocks (recorded, no hand-deleting of infra)

Three stacks first returned `DELETE_FAILED`, each root-caused via
`describe-stack-events` and cleared the CloudFormation-safe way, then a clean `delete-stack`
retry:

1. `aws-sam-cli-managed-default` — its versioned S3 bucket
   (`…-samclisourcebucket-…`) was non-empty. Emptied ALL object versions + delete-markers
   (`list-object-versions` → `delete-objects`), then retry → `GONE`.
2. `ztie-hub-frontend-stack` — `DashboardBucket` (S3) non-empty (legacy dashboard assets +
   many `submissions/`, `results/`, `reports/` objects). Emptied the same way, retry →
   `GONE`.
3. `ztie-dev-waf-shield` — `GlobalShieldWebACL` is a **CLOUDFRONT-scope** WAFv2 WebACL
   (`ztie-dev-global-shield-acl|…|CLOUDFRONT`). Once `ztie-dev-hosting` was deleted, **0
   CloudFront distributions** referenced the ACL (`list-distributions` filtered on
   `WebACLId`), so the association was already clear; a `delete-stack` retry let
   CloudFormation delete the ACL cleanly → `GONE`.

**Operational lesson (folded into the close-out package):** the WAF blocker was
CLOUDFRONT-scope, so `list-web-acls --scope REGIONAL` (and a name-filtered CLOUDFRONT
query using the wrong name) came back empty — the WebACL's true name + scope came from the
stack's own `AWS::WAFv2::WebACL` `PhysicalResourceId` (`name|id|scope`). For an S3-backed
stack delete, empty ALL VERSIONS + delete-markers (a plain recursive `rm` is insufficient
on a versioned bucket).

_Candidate control mappings unchanged from §Candidate control mappings above (CM-8 / CM-2 /
CM-7 / SA-9; ID.AM-1/2, PR.IP-1; A.8.9, A.5.9) — all **proposed**. OD-002 (Forensic
stale-lineage teardown) remains open._
