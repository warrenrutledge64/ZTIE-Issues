# ZTIE Security Analysis Pipeline — Project Plan

> The **what and why**. This plan defines scope, phases, decisions, and acceptance
> criteria. The [`RUNBOOK.md`](RUNBOOK.md) tracks execution against it; the two
> must stay in sync. No phase is "done" until its live validation passes (see the
> runbook's Validation & Advancement Gate).
>
> **Same facts, different views (intentional).** This plan is organized by **phase**
> (the overall reference); the runbook is organized by **build order** (dependency
> tiers, the daily view). The two always agree on the **facts** (same stories,
> statuses, dependencies, decisions) but deliberately **order** them differently;
> neither is reordered to match the other. Story status lives in the runbook as the
> single source of truth. The charter-level *why/for-whom* view — vision, outcomes,
> scope, stakeholders, strategy, risk (no story detail or status) — is
> [`docs/PRODUCT_PLAN.md`](docs/PRODUCT_PLAN.md) (RD-036).

## 1. Project Identity

The **Zero Trust Inspection Engine (ZTIE)** is a four-phase security analysis
pipeline that inspects every deployment payload and code artifact **before** it is
allowed to reach production. Nothing is trusted by default: each artifact is
classified and routed, then subjected to **parallel** static and dynamic
inspection, correlated by an AI assessment engine (Amazon Nova Pro), and gated at a
final enforcement point. Only artifacts verified as safe are cleared to exit the
ZTIE inspection point and continue downstream to the **Platform Delivery Engine
(PDE)** for multi-account deployment.

"Done" looks like: an artifact enters the intake gateway, is routed to the correct
analyzers, is statically scanned **and** detonated on an ephemeral EC2 sandbox in
parallel, has its combined telemetry correlated by Nova Pro into a single threat
score with prioritized findings, and receives a PASS / FAIL / INCONCLUSIVE verdict
that a human reviews in the Hub — on ACCEPT the artifact is pushed to
Pipeline-Sandbox for PDE handoff, on REJECT the artifact and its detonation chamber
are destroyed in Forensic, and on INCONCLUSIVE it holds at a human approval gate —
with both a real-time dashboard and a per-execution report reflecting that decision.

**Named programs.** Four programs carry the flow: `preprocessor` (Phase 1
intake/routing), `accuracy` and `gap_analysis` (Phase 3 Nova Pro correlation), and
`status retrieval` / `status_retrieval` (Phase 4 handoff/reporting). Refer to these
components by these exact names.

## 1a. Architecture Flow

> See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full system narrative
> and named-program reference. The end-to-end flow:

```text
=======================================================================
          ZTIE SECURITY ANALYSIS PIPELINE: ARCHITECTURE FLOW
=======================================================================

                 [Local Developer Workspace / Repo]
                                  |
                                  v
                +---------------------------------+
                |      STEP 0: TRUE-STATE GATE    |
                | Local Gitleaks Detect + Checks  |
                +---------------------------------+
                                  |
                                  v
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
|        + Gitleaks (Compiled)|       | Focus: Syscalls, Network,     |
| Focus: NIST/ISO Compliance, |       |        File Operations        |
|        SAST + Secret Scans  |       |                               |
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
