# ZTIE — Zero Trust Inspection Engine

> **What this is.** ZTIE is a four-phase, AWS-native security pipeline that inspects
> every untrusted artifact (IaC templates, scripts, payloads) **before** it is
> allowed to reach the Platform Delivery Engine (PDE). It classifies each artifact,
> runs it down parallel **static** and **dynamic (detonation)** lanes, correlates the
> evidence with Amazon Nova Pro into a single threat verdict, and gates release
> behind a human accept/reject. Nothing reaches production without a recorded PASS.

> **This README is the dashboard.** It surfaces *everything* — status, where things
> live, how to deploy/validate, restore points, decisions, branches/tags. Use it as
> your control panel; trim sections you don't reach for over time.

---

## 🚦 Status at a glance

| Phase | What it does | Status |
|-------|--------------|--------|
| **P1 — Intake & Routing** | intake gateway → classify → route to lanes / safe-reject | ✅ **complete** (1.1, 1.1R, 1.R, 1.2, 1.3, 1.4 all validated) |
| **P2 — Parallel Inspection** | static scan lane + dynamic detonation lane, in parallel | 🟡 **in progress** |
| **P3 — AI Correlation** | Nova Pro → unified threat score + verdict | ⬜ not started |
| **P4 — Handoff & Reporting** | dashboard + PDF report; ACCEPT→PDE / REJECT→destroy / INCONCLUSIVE→hold | ⬜ not started |

**Current focus (Phase 2):**

| Story | Title | Status |
|-------|-------|--------|
| 2.0 | AWS infra foundation (isolated VPC, IAM, launch template, SSM, Nova Pro) | 🟡 built, awaiting live validation |
| 2.1 | Static scanning lane (cfn-lint, cfn-guard, checkov, bandit) | ✅ **validated 2026-09-01** |
| 2.2 | Compliance mapping (NIST 800-53 / ISO 27001) + signature scans | ⬜ **next up** |
| 2.3 | Detonation chamber (ephemeral EC2 + host-native SSM) | ⬜ blocked on 2.0 |
| 2.4–2.6 | Telemetry capture → sanitization → parallel fork | ⬜ |

> Full, authoritative per-story status lives in **[`RUNBOOK.md`](RUNBOOK.md)** (the
> source of truth). _Note: the RUNBOOK's top "Progress Summary" phase rollup is
> currently stale (still shows ⬜ for phases whose stories are ✅); the per-story
> tables below it are correct._

---

## 🗺️ Where things live (navigation map)

| I want to… | Go to |
|------------|-------|
| See **project scope, phases, decisions** | [`PROJECT_PLAN.md`](PROJECT_PLAN.md) |
| See **live status / what's next / validation results** | [`RUNBOOK.md`](RUNBOOK.md) |
| Understand **how we work** (the story/validation discipline) | [`METHODOLOGY.md`](METHODOLOGY.md) |
| See the **system architecture + flow diagram** | [`DOCS/ARCHITECTURE.md`](DOCS/ARCHITECTURE.md) |
| See **compliance control mappings** (NIST / ISO) | [`DOCS/COMPLIANCE.md`](DOCS/COMPLIANCE.md) |
| Read the **application code** (Lambdas) | [`lambdas/`](lambdas/) |
| Read the **infrastructure** (CDK v2 / TypeScript) | [`infra/`](infra/) |
| See the **data contracts** (the boundaries between components) | [`schemas/`](schemas/) |
| See **CLI tools + contract generators** | [`scripts/`](scripts/) |
| Understand **restore/recovery** | [`RESTORE.md`](RESTORE.md) + the `restore/*` tags (below) |
| See **what's deployed where** (inventory) | [`BOM.md`](BOM.md) |
| Pick up the **next story** with full context | [`DOCS/session-briefs/`](DOCS/session-briefs/) |

---

## 🏗️ Architecture in one screen

```
[artifact] → P1 Intake & Routing (preprocessor: classify + route)
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
 P2 STATIC lane            P2 DYNAMIC lane
 cfn-lint/cfn-guard/       ephemeral EC2 + host-native
 checkov/bandit            SSM detonation (no Docker)
 (non-executing)          (behavioral telemetry)
        └────────────┬────────────┘
                     ▼
        P3 AI Correlation (Amazon Nova Pro)
        → unified threat score + verdict
                     ▼
        P4 Handoff & Reporting (dashboard + PDF)
        ACCEPT → push to PDE · REJECT → destroy · INCONCLUSIVE → human gate
```

**Three-account topology (the security wall is the AWS account boundary):**

| Account | Role |
|---------|------|
| **Pipeline-Hub** `641628980935` | brains / control plane — durable tracking record, the data-contract gate, dashboard, human accept/reject. Never touches the raw payload. |
| **Forensic** `360999005254` | the blast zone — intake, static scanners, ephemeral detonation EC2, raw artifact. Self-contained; only derived data crosses out. |
| **Pipeline-Sandbox** `586917955591` | the ZTIE→PDE handoff landing zone (Phase 4). |

Only **derived, bounded, verdict-free** data crosses Forensic → Hub, through one
one-directional, fail-closed contract gate. (See `DOCS/ARCHITECTURE.md`.)

---

## 🚀 Deploy & validate

ZTIE deploys as independent CDK stacks. The build sandbox has no AWS creds; deploys
run from AWS CloudShell (or a Docker-capable build box for the container-image lane).

| Stack | Account | Notes |
|-------|---------|-------|
| `ZtieHubTrackingStack` | Hub | data-contract gate + tracking DynamoDB + quarantine; **deploy first** |
| `ZtieIntakeStack` | Forensic | intake API + preprocessor + static-scan work queue; needs the Hub queue URL/ARN |
| `ZtieForensicInfraStack` | Forensic | Phase-2 shared infra (Story 2.0), standalone |
| `ZtieStaticScanStack` | Forensic | **container-image** Lambda (Story 2.1); needs Docker to build → use a build box, not CloudShell |

Typical order: **Hub → Intake → StaticScan**. Each story's brief in
[`DOCS/session-briefs/`](DOCS/session-briefs/) carries the exact, copy-paste
deploy + live-validation steps for that story.

**Recurring gotchas (learned live — save yourself the pain):**
- Two CloudShell tabs: submit from a **Forensic** principal, query the tracking table from a **Hub** principal (`ResourceNotFoundException` = wrong account).
- The Hub queue sender grant is **replace-not-append**: pass **all** `forensic*RoleArn` context values on every Hub deploy.
- The container-image lane needs Docker → a disposable Forensic EC2 build box (terminate when done); CloudShell can't build it.
- CDK "(no changes)" when you expected an update usually means a **stale local clone/branch** — `git reset --hard origin/main` and `rm -rf cdk.out`.

---

## ♻️ Restore points (fall back to a known-good state)

Recovery for **code** is by **git tag**. Each validated milestone is tagged
`restore/<milestone>-green` and pushed to GitHub (durable).

| Tag | Known-good state |
|-----|------------------|
| `restore/phase-1-green` | Phase 1 complete — all of 1.1–1.4 validated live |
| `restore/story-2.1-green` | Story 2.1 (static lane) validated live 2026-09-01, incl. the cfn-guard fixes |

```bash
git fetch --tags
git checkout restore/story-2.1-green      # look at a known-good point
git reset --hard restore/story-2.1-green  # (destructive) revert to it
```

For **deployed AWS state**, see [`RESTORE.md`](RESTORE.md) + the `scripts/ztie_restore/`
capture/verify/restore tooling and the manifests in `restore-manifests/`.

---

## 📌 Registered decisions (the "why", locked so we don't re-litigate)

Full table + rationale in [`PROJECT_PLAN.md`](PROJECT_PLAN.md) §5. Highlights:

| ID | Decision (short) |
|----|------------------|
| RD-001 | Detonation is host-native SSM on real ephemeral EC2 — **no Docker** (dynamic lane only) |
| RD-008 | Three-account topology (Hub / Forensic / Pipeline-Sandbox) |
| RD-009 | Hub is control-plane only — never receives the raw payload |
| RD-010/011 | Artifact leaves Forensic only on human ACCEPT → pushed to Pipeline-Sandbox (PDE handoff) |
| RD-012 | No durable data store in Forensic (the blast zone) |
| RD-013 | Forensic → Hub is an enforced, fail-closed **data contract** boundary |
| RD-016 | Concrete gate: cross-account SQS + Hub validator Lambda + quarantine |
| RD-014 | Compliance mapping (NIST 800-53 / ISO 27001) is a standing practice |
| RD-015 | Management artifacts are first-class deliverables (reusable/durable/repeatable) |
| RD-021 | Static-scan lane is packaged as a **container-image** Lambda (no-Docker rule is detonation-only) |

---

## 🌿 Branches & tags (how to read this repo's history)

- **`main`** — the live, validated code. This is what's deployed.
- **`feature/story-*`, `docs/*`, `fix/*` branches** — per-story / per-change history,
  kept for reference. They are **already merged into `main`**; the live code is on
  `main`, not on these. (Retained intentionally in case we need to look something up.)
- **`restore/*-green` tags** — the known-good restore points (see above).

Convention going forward: one `feature/<story>` branch per story → PR → merge; tag
`restore/<id>-green` on each validated story.

---

## 📚 Governance docs index

| Doc | Purpose |
|-----|---------|
| [`PROJECT_PLAN.md`](PROJECT_PLAN.md) | scope, constraints, phases, story list, registered decisions |
| [`RUNBOOK.md`](RUNBOOK.md) | **source of truth for status** — per-story tracking, validation results, the advancement gate |
| [`METHODOLOGY.md`](METHODOLOGY.md) | how we work — the validation covenant, story ritual, restore discipline |
| [`RESTORE.md`](RESTORE.md) | state-capture + coordinated-restore procedures |
| [`BOM.md`](BOM.md) | bill of materials — what's deployed where |
| [`DOCS/ARCHITECTURE.md`](DOCS/ARCHITECTURE.md) | system narrative + flow diagram |
| [`DOCS/COMPLIANCE.md`](DOCS/COMPLIANCE.md) | candidate NIST / ISO control mappings |
| [`DOCS/session-briefs/`](DOCS/session-briefs/) | per-story briefs + prompts (warm handoffs) |

---

<sub>This dashboard is intentionally comprehensive — it shows all the entry points on
purpose. Once you know which sections you actually use, trim the rest.</sub>
