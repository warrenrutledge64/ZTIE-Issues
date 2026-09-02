# ZTIE — Zero Trust Inspection Engine

> **What this is.** ZTIE is a four-phase, AWS-native security pipeline that inspects
> every untrusted artifact (IaC templates, scripts, payloads) **before** it is
> allowed to reach the Platform Delivery Engine (PDE). It classifies each artifact,
> runs it down parallel **static** and **dynamic (detonation)** lanes, correlates the
> evidence with Amazon Nova Pro into a single threat verdict, and gates release
> behind a human accept/reject. Nothing reaches production without a recorded PASS.

> **This README is the single pane of glass.** It is the one place to see where we
> are, what is next, how we work, and the map of where everything lives. It does not
> copy the details; it frames them and **links down** to the authoritative source
> docs (which stay the source of truth). Use it as your control panel; trim sections
> you don't reach for over time.

---

## 🔁 How we work (the loop)

- The AI is the senior (and only) developer. It recommends **one** next thing at a
  time, with a one-line reason: *"next up: X, because Y."*
- You decide: **go** / **not yet** / **do Z instead**. You are never handed a menu
  to juggle.
- Single-threaded: we finish that one thing to completion and **validate it live**
  before anything new begins.
- "Parallel" only means the AI is free to choose the order of two independent
  pieces. It never means doing two things at once.

Full version: **[`docs/governance/OPERATING_MODEL.md`](docs/governance/OPERATING_MODEL.md)**.

> **What's next (current recommendation):** validate + harden **story 2.0** (the
> containment wall). Status: **awaiting your decision** (go / not-yet / do-Z). The
> running recommendation log is **[`docs/governance/WORK_LOG.md`](docs/governance/WORK_LOG.md)**.

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
| 2.2 | Compliance mapping (NIST 800-53 / ISO 27001) + signature scans | ⬜ blocked by the advancement gate (2.0 debt open) |
| 2.3 | Detonation chamber (ephemeral EC2 + host-native SSM) | ⬜ blocked on 2.0 |
| 2.4–2.6 | Telemetry capture → sanitization → parallel fork | ⬜ |

> **Actual next move: validate story 2.0.** The advancement gate blocks new feature
> work (2.2) while the Validation Debt Register holds an entry, and 2.0 is that
> entry. Clearing it by validating 2.0 is the one forward move the gate allows.

> Full, authoritative per-story status lives in **[`RUNBOOK.md`](RUNBOOK.md)** (the
> source of truth). Where we stand today: **Phase 1 complete, Phase 2 in progress.**
>
> **Story order is not build order.** The numbers (2.0, 2.1, 2.2, ...) are not the
> sequence we build in; the real order comes from the dependency graph. See
> **[`docs/BUILD_ORDER.md`](docs/BUILD_ORDER.md)**.

---

## 🗺️ Where things live (navigation map)

| I want to… | Go to |
|------------|-------|
| See **project scope, phases, decisions** | [`PROJECT_PLAN.md`](PROJECT_PLAN.md) |
| See **live status / what's next / validation results** | [`RUNBOOK.md`](RUNBOOK.md) |
| Understand **how we work** (the recommend/decide loop) | [`docs/governance/OPERATING_MODEL.md`](docs/governance/OPERATING_MODEL.md) |
| Understand **how we work** (the story/validation discipline) | [`METHODOLOGY.md`](METHODOLOGY.md) |
| See **what is buildable when** (dependency-graph map; story order is NOT build order) | [`docs/BUILD_ORDER.md`](docs/BUILD_ORDER.md) |
| See the **running list of next-up recommendations** | [`docs/governance/WORK_LOG.md`](docs/governance/WORK_LOG.md) |
| See the **system architecture + flow diagram** | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| See **compliance control mappings** (NIST / ISO) | [`docs/COMPLIANCE.md`](docs/COMPLIANCE.md) |
| Read the **application code** (Lambdas) | [`lambdas/`](lambdas/) |
| Read the **infrastructure** (CDK v2 / TypeScript) | [`infra/`](infra/) |
| See the **data contracts** (the boundaries between components) | [`schemas/`](schemas/) |
| See **CLI tools + contract generators** | [`scripts/`](scripts/) |
| Understand **restore/recovery** | [`RESTORE.md`](RESTORE.md) + the `restore/*` tags (below) |
| See **what's deployed where** (inventory) | [`BOM.md`](BOM.md) |
| Pick up the **next story** with full context | [`docs/session-briefs/`](docs/session-briefs/) |

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
one-directional, fail-closed contract gate. (See `docs/ARCHITECTURE.md`.)

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
[`docs/session-briefs/`](docs/session-briefs/) carries the exact, copy-paste
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
| [`docs/governance/OPERATING_MODEL.md`](docs/governance/OPERATING_MODEL.md) | how we work: the recommend/decide loop (AI recommends one thing, you decide) |
| [`docs/BUILD_ORDER.md`](docs/BUILD_ORDER.md) | the dependency-graph map of what is buildable when; story order is NOT build order |
| [`docs/governance/WORK_LOG.md`](docs/governance/WORK_LOG.md) | the running list of the AI's next-up recommendations |
| [`METHODOLOGY.md`](METHODOLOGY.md) | how we work — the validation covenant, story ritual, restore discipline |
| [`RESTORE.md`](RESTORE.md) | state-capture + coordinated-restore procedures |
| [`BOM.md`](BOM.md) | bill of materials — what's deployed where |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | system narrative + flow diagram |
| [`docs/COMPLIANCE.md`](docs/COMPLIANCE.md) | candidate NIST / ISO control mappings |
| [`docs/session-briefs/`](docs/session-briefs/) | per-story briefs + prompts (warm handoffs) |

---

<sub>This dashboard is intentionally comprehensive — it shows all the entry points on
purpose. Once you know which sections you actually use, trim the rest.</sub>
