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

> **Verdict-driven routing (ZTIE enforcement boundary).** The diagram's "If Verified
> Safe" arrow is the **PASS** path. The full enforcement decision is:
> **PASS** → forward to the PDE; **FAIL** → nuke the payload and route failure
> telemetry back to the originating sandbox; **INCONCLUSIVE** → hold at a human
> approval gate (approve/reject from the dashboard) before any PDE handoff.

## Terminology & topology notes

- Call the dynamic-lane EC2 instances **ephemeral** — never "temporary."
- Detonation is **host-native SSM on EC2**; Docker/containers are strictly forbidden.
- Topology is **multi-account**: separate AWS accounts for **hub** (Pipeline-Hub,
  641628980935 — dashboard + DynamoDB), **sandbox**, and **production**.
- **ServiceNow integration is strictly out of scope** for the ZTIE workflow and
  dashboard.
