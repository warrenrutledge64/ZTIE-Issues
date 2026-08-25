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
- **Last updated:** 2026-08-25 (Story 1.R — restore-point mechanism built; awaiting
  live validation before the first `restore/phase-1-green` tag)
- **Current restore point:** none yet (Story 1.R creates the mechanism; the first
  restore point is captured at the Phase-1 close, after 1.2/1.3/1.4 route correctly)

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
| Intake API `ztie-intake` | API Gateway REST (IAM auth) | Forensic / `ZtieIntakeStack` | `IntakeApi` | P1 | pending |
| Intake handler | Lambda (Python 3.12) | Forensic / `ZtieIntakeStack` | `IntakeHandler` | P1 | pending |
| Artifact body store | S3 (KMS, versioned, block-public) | Forensic / `ZtieIntakeStack` | `IntakeArtifactBucket` | P1 | pending |
| Durable tracking record | DynamoDB (PK `intake_id`, GSI `status-received_at-index`, PAY_PER_REQUEST, PITR, AWS-managed SSE) | Hub / `ZtieHubTrackingStack` | `TrackingTable` | P1 | pending |
| Forensic→Hub ingest queue | SQS (SSE, TLS-only) | Hub / `ZtieHubTrackingStack` | `IngestQueue` | P1 | pending |
| Ingest DLQ | SQS | Hub / `ZtieHubTrackingStack` | `IngestDlq` | P1 | pending |
| Validating ingestion gate | Lambda (Python 3.12, `jsonschema`) | Hub / `ZtieHubTrackingStack` | `IngestValidator` | P1 | pending |
| Contract-failure quarantine | S3 (KMS, versioned, block-public) | Hub / `ZtieHubTrackingStack` | `QuarantineBucket` | P1 | pending |

> **Not inventoried (by design):** Forensic's *ephemeral* raw-payload S3 object
> contents and per-run scratch are disposable (rebuilt, not restored). DynamoDB
> items and S3 object contents are data, not configuration, and are outside the
> restore-point baseline.

## 3. Components (reusable units)

| Component | Purpose | Version | Interface / contract | Reused by | Restore point |
|-----------|---------|---------|----------------------|-----------|---------------|
| `ztie-restore` | state-capture + coordinated restore (projection-based) | 1.0 | CLI `capture`/`verify`/`restore`; manifest `schemas/restore-manifest.v1.json` | every phase close | pending |
| Forensic→Hub data contract | allow-list schema for the one-directional crossing | v1 | `schemas/intake-tracking.contract.v1.json` (draft-07) | Hub validator Lambda (1.1R) | pending |
| Restore manifest schema | shape of a restore-point state manifest | v1 | `schemas/restore-manifest.v1.json` (draft-07) | `ztie-restore` | pending |

## 4. Restore Points

| Tag | Phase | Date | Code (git SHA) | State manifest | Notes |
|-----|-------|------|----------------|----------------|-------|
| _(none yet)_ | — | — | — | — | First tag `restore/phase-1-green` is captured at the P1 close (after 1.2/1.3/1.4), using `ztie-restore capture`. |

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
