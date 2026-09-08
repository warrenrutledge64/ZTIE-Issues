# ZTIE — Inventory (Bill of Materials)

> **Living document.** The authoritative inventory of everything this project is
> made of — every deployed resource, dependency, pinned version — and the
> human-readable form of the restore-point state manifest. Updated at **every
> end-of-phase validation**, with each entry tied to the restore point (git tag)
> under which it was captured.
>
> **Rule:** if it is deployed/produced, it is in this inventory. If it is in this
> inventory, it maps to a restore point. This is the defense against
> code-vs-deployed drift.

- **Environment / target:** AWS, three-account topology (see PROJECT_PLAN.md RD-008):
  - **Pipeline-Hub (641628980935)** — brains/control plane: orchestrator, DynamoDB,
    dashboard, reporting/tracking for ZTIE + PDE, human accept/reject gate. Never
    holds the raw payload.
  - **Forensic (360999005254)** — ZTIE self-contained + ultimate blast-radius
    containment: intake/preprocessor, static scanners, VPC/isolated subnets,
    ephemeral EC2 detonation, raw payload.
  - **Pipeline-Sandbox (586917955591)** — ZTIE→PDE handoff landing zone (PDE-owned
    once the artifact lands; out of ZTIE operational scope).
- **Region:** us-east-1
- **Last updated:** 2026-09-08 (Story 2.0E — two-tier detonation endpoints validated
  live 5/5; Forensic deployed-state re-captured + `verify`-clean; `restore/story-2.0E-green`)
- **Current restore point:** `restore/story-2.0E-green` — the validated Story 2.0E
  baseline (two-tier detonation VPC endpoints, RD-027, on the reconciled `main` after
  PR #70). Forensic deployed-state re-captured via `ztie-restore` in the stakeholder's
  CloudShell, `verify`-clean (MATCH, exit 0), 2026-09-08. Manifest:
  `restore-manifests/manifest-20260908T145502Z.json` (Forensic, **16 projections** — now
  includes `ZtieDetonationStack` + the orchestrator Lambda and the three new RD-027 SSM
  params). The **Hub** side is unchanged by 2.0E, so its baseline manifest
  `restore-manifests/manifest-20260902T201610Z.json` (Hub, 4 projections) still applies.
  - _Superseded:_ `restore/phase-2-floor-green` (2026-09-02, Forensic 11 projections) —
    the pre-2.0E Phase-2 floor; kept as historical evidence.

---

## 1. Dependencies & Versions

| Component | Type | Version | Notes |
|-----------|------|---------|-------|
| AWS CDK (aws-cdk-lib) | IaC framework | v2 (see `infra/package.json`) | TypeScript infra for both stacks |
| Node.js | runtime (build) | 18+ | for CDK synth/deploy |
| Python | runtime | 3.12 | all Lambda handlers + the `ztie-restore` tooling |
| Python `jsonschema` | lib | see `lambdas/hub_ingest/requirements.txt` | Hub validator contract enforcement (bundled into the Lambda via Docker) |
| boto3 | lib | AWS-provided in Lambda; CloudShell-provided for `ztie-restore` | AWS SDK; `ztie-restore` imports it lazily so the pure logic is testable without it |
| `ztie-restore` tooling | CLI | 1.0 (manifest `schema_version`) | Story 1.R state-capture + coordinated restore, `scripts/ztie_restore/` |

## 2. Deployed / Produced Artifacts

> Physical resource names are CDK-generated and only known at deploy time. The
> `ztie-restore capture` manifest records the resolved physical ids per capture;
> this table tracks the **logical** inventory and where each lives.

| Artifact | Type | Account / Stack | Logical id | Phase | Restore point |
|----------|------|-----------------|-----------|-------|---------------|
| Intake API `ztie-intake` | API Gateway REST (IAM auth) | Forensic / `ZtieIntakeStack` | `IntakeApi` | P1 | `restore/phase-2-floor-green` @ `33fa6b0`; captured at stack level in the Forensic manifest (`ZtieIntakeStack` template_sha256 `6ed1eaef…`), `restore-manifests/manifest-20260902T201931Z.json` |
| Intake handler | Lambda (Python 3.12) | Forensic / `ZtieIntakeStack` | `IntakeHandler` | P1 | `restore/phase-2-floor-green` @ `33fa6b0`; physical `ZtieIntakeStack-IntakeHandler8F27FC31-EcfFRng3A8PT`, code_sha256 `CJ+VYURMwHFa…`, `restore-manifests/manifest-20260902T201931Z.json` |
| Artifact body store | S3 (KMS, versioned, block-public) | Forensic / `ZtieIntakeStack` | `IntakeArtifactBucket` | P1 | `restore/phase-2-floor-green` @ `33fa6b0`; physical `ztieintakestack-intakeartifactbucket2415ab50-vzfdr2jmnj5a`, `restore-manifests/manifest-20260902T201931Z.json` |
| Durable tracking record | DynamoDB (PK `intake_id`, GSI `status-received_at-index`, PAY_PER_REQUEST, PITR, AWS-managed SSE) | Hub / `ZtieHubTrackingStack` | `TrackingTable` | P1 | `restore/phase-2-floor-green` @ `33fa6b0`; physical `ZtieHubTrackingStack-TrackingTable170A6688-133E30JVEWB1Z`, `restore-manifests/manifest-20260902T201610Z.json` |
| Forensic→Hub ingest queue | SQS (SSE, TLS-only) | Hub / `ZtieHubTrackingStack` | `IngestQueue` | P1 | `restore/phase-2-floor-green` @ `33fa6b0`; covered at stack level (`ZtieHubTrackingStack` template_sha256 `f57af038…`), `restore-manifests/manifest-20260902T201610Z.json` |
| Ingest DLQ | SQS | Hub / `ZtieHubTrackingStack` | `IngestDlq` | P1 | `restore/phase-2-floor-green` @ `33fa6b0`; covered at stack level (`ZtieHubTrackingStack` template_sha256 `f57af038…`), `restore-manifests/manifest-20260902T201610Z.json` |
| Validating ingestion gate | Lambda (Python 3.12, `jsonschema`) | Hub / `ZtieHubTrackingStack` | `IngestValidator` | P1 | `restore/phase-2-floor-green` @ `33fa6b0`; physical `ZtieHubTrackingStack-IngestValidator33BFC8F7-6UKVHm9XTxJw`, code_sha256 `xjH5TbZusVqU…`, `restore-manifests/manifest-20260902T201610Z.json` |
| Contract-failure quarantine | S3 (KMS, versioned, block-public) | Hub / `ZtieHubTrackingStack` | `QuarantineBucket` | P1 | `restore/phase-2-floor-green` @ `33fa6b0`; physical `ztiehubtrackingstack-quarantinebucketfdbda180-tsw5bdhpoqfw`, `restore-manifests/manifest-20260902T201610Z.json` |
| Preprocessor handler | Lambda (Python 3.12) | Forensic / `ZtieIntakeStack` | `PreprocessorHandler` | P1 | `restore/phase-2-floor-green` @ `33fa6b0`; physical `ZtieIntakeStack-PreprocessorHandler02586939-9Sup7PIQmhOC`, code_sha256 `FiUZc8ZFYubj…`, `restore-manifests/manifest-20260902T201931Z.json` |
| Isolated-VPC detonation foundation (VPC/isolated subnets, **S3 gateway endpoint + always-on single-AZ SSM control channel; logs/sqs/bedrock-runtime are ephemeral per-run per RD-027**, IAM, ephemeral-EC2 launch template w/ 5-min hard TTL) | CloudFormation stack (CDK v2) | Forensic / `ZtieForensicInfraStack` | `ZtieForensicInfraStack` | P2 | `restore/story-2.0E-green` @ `cad8b62`; stack-level projection (template_sha256 `a8d60c48…`, param `/ztie/ami/ubuntu-22.04`, Story=2.0 tags), `restore-manifests/manifest-20260908T145502Z.json` |
| Detonation orchestrator (Lambda running the RD-027 ephemeral-endpoint lifecycle + orphan sweep + host-native SSM execution) | CloudFormation stack (CDK v2) + Lambda | Forensic / `ZtieDetonationStack` | `ZtieDetonationStack` (`DetonationOrchestrator`) | P2 | `restore/story-2.0E-green` @ `cad8b62`; stack-level projection (template_sha256 `0338b8c9…`, Story=2.3 tags) + orchestrator Lambda `python3.12` code_sha256, `restore-manifests/manifest-20260908T145502Z.json` |
| Detonation coordination params | SSM parameters — **7 total** (`/ztie/detonation/launch-template-id` = `lt-045ddce7fdac386db`, `…/instance-role-arn`, `…/isolated-subnet-ids`, `…/ami-flavor` = `ubuntu-22.04`, **+ RD-027:** `…/vpc-id`, `…/endpoint-service-names`, `…/endpoint-security-group-id`) | Forensic / published by `ZtieForensicInfraStack` | (SSM) | P2 | `restore/story-2.0E-green` @ `cad8b62`; all **7** String params captured by value, `restore-manifests/manifest-20260908T145502Z.json`. The three RD-027 params (VPC id, ordered ephemeral service names, endpoint SG id) are consumed by the orchestrator to build the ephemeral endpoint tier per run. |
| Static-scan work queue + DLQ | SQS (intra-Forensic; static-scan job enqueue) | Forensic / `ZtieIntakeStack` (2.1 additions) | (stack) | P2 | `restore/phase-2-floor-green` @ `33fa6b0`; covered at stack level (`ZtieIntakeStack` template_sha256 `6ed1eaef…`), `restore-manifests/manifest-20260902T201931Z.json` |
| Static scanning lane (cfn-lint / cfn-guard / checkov / bandit) | Lambda (container image) | Forensic / `ZtieStaticScanStack` | `StaticScanFunction` | P2 | `restore/phase-2-floor-green` @ `33fa6b0`; stack projection (template_sha256 `e2a3f550…`) + physical `ZtieStaticScanStack-StaticScanFunction61438688-jITpXtPa31vp`, code_sha256 `1ece9957…`, `restore-manifests/manifest-20260902T201931Z.json` |

> **Not inventoried (by design):** Forensic's *ephemeral* raw-payload S3 object
> contents and per-run scratch are disposable (rebuilt, not restored). DynamoDB
> items and S3 object contents are data, not configuration, and are outside the
> restore-point baseline.

## 3. Components (reusable units)

| Component | Purpose | Version | Interface / contract | Reused by | Restore point |
|-----------|---------|---------|----------------------|-----------|---------------|
| `ztie-restore` | state-capture + coordinated restore (projection-based) | 1.0 | CLI `capture`/`verify`/`restore`; manifest `schemas/restore-manifest.v1.json` | every phase close | `restore/phase-2-floor-green` @ `33fa6b0`; exercised live in A.4 (both accounts captured + `verify`-clean, exit 0) |
| Forensic→Hub data contract | allow-list schema for the one-directional crossing | v1 | `schemas/intake-tracking.contract.v1.json` (draft-07) | Hub validator Lambda (1.1R) | `restore/phase-2-floor-green` @ `33fa6b0`; validator captured in the Hub manifest, `restore-manifests/manifest-20260902T201610Z.json` |
| Restore manifest schema | shape of a restore-point state manifest | v1 | `schemas/restore-manifest.v1.json` (draft-07) | `ztie-restore` | `restore/phase-2-floor-green` @ `33fa6b0`; both A.4 manifests conform (`schema_version` 1.0) |

## 4. Restore Points

| Tag | Phase | Date | Code (git SHA) | State manifest | Notes |
|-----|-------|------|----------------|----------------|-------|
| `restore/phase-2-floor-green` | P2 floor (2.0 ✅ + 2.1 ✅, backed up) | 2026-09-02 | _(paired A.4 status commit — set by the repo owner when tagging)_ | Hub: `restore-manifests/manifest-20260902T201610Z.json` (4 projections) · Forensic: `restore-manifests/manifest-20260902T201931Z.json` (11 projections) | First deployed-state restore point. Both accounts captured via `ztie-restore` in the stakeholder's CloudShells and `verify`-clean (MATCH, exit 0), 2026-09-02. Manifest capture commits: Hub `de807f3`, Forensic `33fa6b0` on branch `docs/story-a4-floor-capture`. The manifests' pinned `governance_commit` are the capture-time HEADs (Hub `cf903440`, Forensic `de807f3`); the authoritative floor tag is placed on the merged A.4 status commit. |

---

### Maintenance procedure

1. At each **end-of-phase validation that passes**:
   - Capture the live state via `python3 scripts/ztie-restore capture --account <hub|forensic>`
     (one manifest per account, in that account's CloudShell).
   - Update sections 1–3 with any new/changed items (resolved physical ids from
     the manifest can be noted here).
   - Add a row to section 4 with the git tag + SHA + manifest path. The manifest's
     pinned `governance_commit.sha` must equal the tagged commit (RD-015).
2. Commit the inventory update as part of the phase-closing commit.
3. The `restore/phase-N-green` git tag and the section-4 row must always agree.
