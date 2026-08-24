# {{PROJECT_NAME}} — Inventory (Bill of Materials)

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
- **Last updated:** pending first phase
- **Current restore point:** none yet

---

## 1. Dependencies & Versions

| Component | Type | Version | Notes |
|-----------|------|---------|-------|
| {{name}} | {{runtime/lib/model/tool}} | {{pinned version}} | {{purpose}} |

## 2. Deployed / Produced Artifacts

| Artifact | Type | Name / ID | Phase | Restore point |
|----------|------|-----------|-------|---------------|
| {{...}} | {{...}} | {{...}} | {{...}} | {{tag}} |

> Track here the resource classes relevant to this project (e.g. services,
> infrastructure, endpoints, config parameters, keys, pipelines).

## 3. Components (reusable units)

| Component | Purpose | Version | Interface / contract | Reused by | Restore point |
|-----------|---------|---------|----------------------|-----------|---------------|
| {{...}} | {{...}} | {{...}} | {{...}} | {{...}} | {{...}} |

## 4. Restore Points

| Tag | Phase | Date | Code (git SHA) | State manifest | Notes |
|-----|-------|------|----------------|----------------|-------|
| {{restore/phase-N-green}} | {{N}} | {{date}} | {{sha}} | {{path}} | {{...}} |

---

### Maintenance procedure

1. At each **end-of-phase validation that passes**:
   - Capture the live state via the restore-point state-capture step.
   - Update sections 1–3 with any new/changed items.
   - Add a row to section 4 with the git tag + SHA + manifest path.
2. Commit the inventory update as part of the phase-closing commit.
3. The `restore/phase-N-green` git tag and the section-4 row must always agree.
