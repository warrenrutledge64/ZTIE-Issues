# ZTIE Security Analysis Pipeline — Architecture Flow

> Single source of truth for the ZTIE system narrative and flow diagram. Referenced
> by `PROJECT_PLAN.md`, `RUNBOOK.md`, and the session prompt/brief templates.

## System Narrative

ZTIE (Zero Trust Inspection Engine) is a four-phase security analysis pipeline that
inspects deployment payloads and code artifacts before they reach production.

- **Phase 1 — Intake & Routing.** The `preprocessor` program intercepts incoming
  artifacts and acts as an intelligent router. It classifies payloads so that
  Infrastructure-as-Code templates and raw scripts are directed to distinct paths,
  preventing incompatible scans from crashing the pipeline.
- **Phase 2 — Parallel Inspection.** The workflow forks into concurrent static and
  dynamic lanes. The **static** path uses cfn-lint, cfn-guard, checkov, and bandit
  to scan for vulnerabilities and compliance with frameworks such as NIST SP 800-53
  and ISO 27001. Simultaneously, the **dynamic** path detonates the payload on an
  ephemeral EC2 instance (host-native SSM execution; no Docker) to monitor real
  runtime behavior — syscalls, network activity, and file operations.
- **Phase 3 — AI Correlation.** Raw telemetry from both paths is sent to the central
  analysis engine powered by Amazon Nova Pro. The `accuracy` and `gap_analysis`
  programs execute to synthesize the data, cross-referencing static misconfigurations
  with dynamic behavioral indicators to eliminate false positives and generate a
  unified threat score.
- **Phase 4 — Handoff & Reporting.** The `status retrieval` (`status_retrieval`)
  program orchestrates delivery of the correlated insights, generating both a JSON
  payload for the dashboard and a comprehensive PDF report. Only verified-safe
  payloads exit ZTIE downstream to the Platform Delivery Engine (PDE).

## Named programs

| Program | Phase | Role |
|---------|-------|------|
| `preprocessor` | 1 | Classifies extensions/metadata; routes to the correct lane |
| `accuracy` | 3 | Nova Pro synthesis — scoring accuracy / false-positive elimination |
| `gap_analysis` | 3 | Nova Pro synthesis — static↔dynamic gap correlation |
| `status retrieval` (`status_retrieval`) | 4 | Orchestrates handoff + multi-format reporting |

## Architecture Flow Diagram

```
=======================================================================
          ZTIE SECURITY ANALYSIS PIPELINE: ARCHITECTURE FLOW
=======================================================================

                       [Incoming Code/Payload]
                                  |
                                  v
+---------------------------------------------------------------------+
|                     PHASE 1: INTAKE & ROUTING                       |
| Program: `preprocessor` (Classifies extensions, routes accordingly) |
+---------------------------------------------------------------------+
                                  |
               +------------------+------------------+
               | (Concurrent Parallel Execution)     |
               v                                     v
+-----------------------------+       +-------------------------------+
|    PHASE 2: STATIC PATH     |       |    PHASE 2: DYNAMIC PATH      |
| Non-Executing Inspection    |       | Sandboxed Execution/Detonation|
| Tools: cfn-lint, cfn-guard, |       | Env: Ephemeral EC2            |
|        checkov, bandit      |       | Exec: Host-native SSM         |
| Focus: NIST/ISO Compliance, |       | Focus: Syscalls, Network,     |
|        SAST Vulnerabilities |       |        File Operations        |
+-----------------------------+       +-------------------------------+
|  Output: Static JSON Data   |       |  Output: Behavioral Telemetry |
+-----------------------------+       +-------------------------------+
               |                                     |
               +------------------+------------------+
                                  |
                                  v
+---------------------------------------------------------------------+
|               PHASE 3: AI CORRELATION & ASSESSMENT                  |
| Engine: Amazon Nova Pro                                             |
| Programs: `accuracy`, `gap_analysis`                                |
| Action: Cross-references static findings with dynamic behavior to   |
|         eliminate false positives and generate unified threat score.|
+---------------------------------------------------------------------+
                                  |
                                  v
+---------------------------------------------------------------------+
|                  PHASE 4: HANDOFF & REPORTING                       |
| Program: `status retrieval`                                         |
| Action: Transforms insights into final multi-format reporting.      |
+---------------------------------------------------------------------+
                                  |
                 +----------------+----------------+
                 |                                 |
                 v                                 v
        [JSON Dashboard Data]                 [PDF Report]
                 |
                 v
        (If Verified Safe)
                 |
                 v
+---------------------------------------------------------------------+
|               DOWNSTREAM DEPLOYMENT (Invariant Gate)                |
| Target: Platform Delivery Engine (PDE)                              |
+---------------------------------------------------------------------+
```

> **Enforcement boundary (human accept/reject in the Hub).** The diagram's "If
> Verified Safe" arrow is the outcome of a **human decision** taken in Pipeline-Hub
> over ZTIE's reported findings. The raw artifact stays in **Forensic** until then:
> **ACCEPT** → ZTIE pushes the hash-verified artifact Forensic → Pipeline-Sandbox
> (the ZTIE→PDE handoff; on landing it is under PDE control and ZTIE's job ends);
> **REJECT** → ZTIE destroys the artifact **and** its detonation chamber in
> Forensic; **INCONCLUSIVE** → hold at the human approval gate. ZTIE performs
> security clearance only and never re-executes the artifact outside Forensic.

## Account topology (three roles)

The unknown artifact only ever executes in **Forensic** (the blast zone). The
**Hub** (brains) only ever sees derived data. The account boundary is the
containment wall between the artifact and its manager.

```
   ┌──────────────────────────── ZTIE owns ────────────────────────────┐
   [artifact] → FORENSIC (360999005254): intake + static + VPC +        │
                ephemeral EC2 detonation (host-native SSM).             │
                Raw artifact STAYS here.                                │
                        │ derived/sanitized results only                │
                        ▼                                               │
                PIPELINE-HUB (641628980935): orchestrator, DynamoDB,    │
                dashboard, reporting/tracking (ZTIE + PDE).             │
                HUMAN reviews findings → ACCEPT / REJECT.               │
              REJECT ◀───┴───▶ ACCEPT                                   │
       destroy artifact +        ZTIE PUSHES hash-verified artifact     │
       detonation chamber        Forensic ──▶ Pipeline-Sandbox          │
       (in Forensic)                        │                          │
   └─────────────────────────────────────── │ ──────────────────────────┘
                                             ▼
                        PIPELINE-SANDBOX (586917955591)
                        ══ artifact now under PDE control ══
                        (functional user acceptance / execution = PDE)
```

- **Pipeline-Hub (641628980935) — brains / control plane.** Orchestrator, dashboard,
  reporting/tracking for ZTIE **and** PDE, the human accept/reject gate, and the
  **authoritative, durable tracking / intake / verdict record** (DynamoDB) — it
  survives blast-zone teardown and is the audit trail (RD-012). Never receives,
  parses, executes, or stores the raw payload — derived data only. Kept out of the
  blast zone.
- **Forensic (360999005254) — ZTIE self-contained + ultimate blast-radius
  containment.** Intake/`preprocessor`, static scanners, VPC/isolated subnets,
  ephemeral EC2 detonation, the raw payload. The only place the unknown executes.
  Holds **only ephemeral state** — raw artifact (S3) + transient per-run state; **no
  durable data store** (RD-012).

## Forensic → Hub: the data-contract boundary (RD-013)

The write from the blast zone into the brains is the single most dangerous path in
the system — everything Forensic emits is **attacker-influenced data**. We do not
police what goes *into* Forensic (assumed dirty); all rigor is on the exit:

- Nothing crosses unless it satisfies a **strict, bounded, allow-list schema**
  enforced by a **Hub-owned validating ingestion gate**. Forensic has **no direct
  write** to Hub data.
- **Only derived data** crosses — no raw payload, no executable content (the schema
  has no field for it). Every field typed + length-capped; total size + nesting
  bounded.
- **Fail-closed:** non-conforming records are quarantined, never written live.
- **One-directional, least-privilege, integrity-keyed** (bound to intake_id +
  sha256; upsert-by-key; no cross-record writes).
- The **verdict is decided Hub-side by the human gate — never imported** from
  crossed data.
- The dashboard **escapes crossed data on render** (no stored XSS in the brains).
- **Pipeline-Sandbox (586917955591) — ZTIE→PDE handoff landing zone.** Receives the
  hash-verified artifact only on human acceptance; on arrival it is under PDE
  control. Functional user acceptance / execution of the already-cleared artifact,
  and Sandbox isolation, are PDE responsibilities.

## Terminology notes

- Call the dynamic-lane EC2 instances **ephemeral** — never "temporary."
- Detonation is **host-native SSM on EC2**; Docker/containers are strictly forbidden.
- **ServiceNow integration is strictly out of scope** for the ZTIE workflow and
  dashboard.
