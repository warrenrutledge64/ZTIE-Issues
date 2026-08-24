# ZTIE Security Analysis Pipeline — Project Plan

> The **what and why**. This plan defines scope, phases, decisions, and acceptance
> criteria. The [`RUNBOOK.md`](RUNBOOK.md) tracks execution against it; the two
> must stay in sync. No phase is "done" until its live validation passes (see the
> runbook's Validation & Advancement Gate).

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
that either forwards it to the PDE, nukes it and returns failure telemetry to the
originating sandbox, or holds it at a human approval gate — with both a real-time
dashboard and a per-execution report reflecting that decision.

**Named programs.** Four programs carry the flow: `preprocessor` (Phase 1
intake/routing), `accuracy` and `gap_analysis` (Phase 3 Nova Pro correlation), and
`status retrieval` / `status_retrieval` (Phase 4 handoff/reporting). Refer to these
components by these exact names.

## 1a. Architecture Flow

> See [`DOCS/ARCHITECTURE.md`](DOCS/ARCHITECTURE.md) for the full system narrative
> and named-program reference. The end-to-end flow:

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

> The "If Verified Safe" arrow is the **PASS** path. Full enforcement: **PASS** →
> PDE; **FAIL** → nuke payload + return telemetry to the originating sandbox;
> **INCONCLUSIVE** → hold at the human approval gate.

## 2. Non-Negotiable Constraints

> The rules that hold across every phase. Any deliverable violating one is not
> done, regardless of other progress.

- **Zero Trust posture.** Nothing is trusted by default; every artifact is fully
  inspected before it may proceed. There is no "skip inspection" path.
- **Real execution, no mocks.** The detonation chamber uses **ephemeral EC2
  instances with host-native SSM execution** — not Docker, not containers, not
  application-level simulations. Behavioral telemetry must represent exactly what
  the code would do in a live system. **Terminology:** these instances are
  **ephemeral** — never call them "temporary."
- **Parallel inspection.** Static and dynamic analysis run **concurrently**, not
  sequentially — the preprocessor forks the pipeline into two lanes.
- **AI-correlated verdicts.** Findings are produced by cross-referencing static
  misconfigurations against dynamic behavioral evidence (Nova Pro), not by either
  lane in isolation — this is what eliminates false positives.
- **Gate-based enforcement.** Only verified-safe payloads exit ZTIE to the PDE. The
  verdict (PASS / FAIL / INCONCLUSIVE) drives a routing decision (forward / nuke +
  return telemetry / hold at manual approval gate).
- **Multi-format, tiered reporting.** JSON for the dashboard, PDF for humans, with
  audience-tiered depth (Executive / Security / Developer).
- **Production-quality:** no mocks/placeholders standing in for real services
  unless explicitly agreed. Real API connections, pagination, error handling, and
  test coverage from the start. Integration tests run against real AWS APIs;
  moto/aws-sdk-client-mock is acceptable only for unit-level AWS API simulation.
- **AWS-native automation.** CI/CD and infrastructure automation are AWS-native
  (CodePipeline, CodeBuild, CodeCommit). GitHub is for development only, not
  deployment/operations.
- **Multi-account topology.** The architecture uses **separate AWS accounts** for
  **hub** (Pipeline-Hub, 641628980935 — dashboard + DynamoDB), **sandbox**, and
  **production** environments.
- **ServiceNow out of scope.** ServiceNow integration is strictly out of scope for
  the ZTIE workflow and dashboard.
- **Python by default.** Development is Python-first; Bash only for trivial glue.
- **Validation-gated:** nothing is "done" on inference — the user validates live
  and the result is recorded.
- **Restore-point discipline:** build from a known-good point; revert rather than
  forward-patch.

## 3. Phases & Milestones

> Ordered by dependency + reuse value. Pull genuine shared foundations forward and
> build them once. Each phase has a single, live end-of-phase validation gate. The
> four phases below mirror the ZTIE data flow: Intake → Parallel Inspection → AI
> Correlation → Handoff.

### Phase 1 — Intake and Routing
- **Goal:** Stand up the ZTIE intake gateway and the **preprocessor** — the
  classification/routing layer. It inspects each payload's file extensions and
  metadata and routes IaC templates to the correct linters and raw scripts to their
  distinct auditing paths, so incompatible scans never crash the pipeline.
- **Gate:** Feed representative artifacts (IaC template, raw script, mixed bundle)
  through the intake gateway; confirm each is classified and routed to the correct
  downstream lane, and that an unroutable/unknown artifact is handled safely
  (rejected, not crashed).
- **Stories:** intake gateway endpoint; classifier (extension + metadata
  inspection); routing table to static/dynamic lanes; safe-reject path for unknown
  types. _(mirrored with detail in the runbook)_

### Phase 2 — Parallel Inspection Paths
- **Goal:** Fork the pipeline into two concurrent lanes.
  - **Static Analysis lane** — non-executing inspection with a scanning stack
    (`cfn-lint`, `cfn-guard`, `checkov`, `bandit`), evaluated against mandated
    compliance frameworks (e.g. NIST SP 800-53, ISO 27001), plus signature-based
    scans for known vulnerabilities/malicious patterns. Emits JSON results.
  - **Dynamic Analysis (Detonation) lane** — deploys the payload into a highly
    restricted, ephemeral EC2 instance and runs it via host-native SSM, monitoring
    system calls, network attempts, and file operations. Emits behavioral data.
- **Gate:** A known-bad artifact produces (a) static findings from the scanning
  stack **and** (b) observed runtime behavior from a real detonation, with both
  lanes running in parallel and each emitting its structured output; the ephemeral
  EC2 is confirmed torn down (hard TTL).
- **Stories:** static scanning stack integration; compliance-framework mapping;
  detonation chamber (ephemeral EC2 + SSM host-native exec); behavioral telemetry
  capture (syscalls/network/filesystem); telemetry sanitization pipeline; parallel
  orchestration / fork.

### Phase 3 — AI Correlation and Assessment
- **Goal:** Aggregate the raw telemetry, error logs, and JSON outputs from both
  lanes and pass them to the central analysis engine (**Amazon Nova Pro**). The
  `accuracy` and `gap_analysis` programs synthesize the data — correlating static
  misconfigurations with dynamic behavioral indicators, eliminating false
  positives, and producing a unified threat score, detailed findings, and
  prioritized remediations.
- **Gate:** Given paired static + dynamic outputs for an artifact, Nova Pro returns
  a single unified threat score, correlated findings (static ↔ dynamic evidence),
  and prioritized remediations; a case where static flags a risk but dynamic proves
  benign (or vice-versa) is correctly reconciled (false-positive elimination
  demonstrated).
- **Stories:** telemetry aggregation/normalization; Nova Pro correlation engine
  (with exponential-backoff retry); `accuracy` + `gap_analysis` synthesis; unified
  threat scoring; correlated findings + prioritized remediation output; verdict
  derivation (PASS / FAIL / INCONCLUSIVE).

### Phase 4 — Handoff and Reporting
- **Goal:** The **status retrieval** program orchestrates delivery of the
  correlated data: transform the AI insights into the comprehensive JSON payload
  that populates the dashboard and generate the final PDF report. Enforce the exit
  gate — PASS forwards to the PDE for multi-account deployment; FAIL nukes the
  payload and routes failure telemetry back to the originating sandbox;
  INCONCLUSIVE holds at a human approval gate.
- **Gate:** For a full run, confirm the dashboard JSON and PDF report are produced
  with tiered content (Executive / Security / Developer); a PASS artifact is
  forwarded to the PDE; a FAIL artifact is nuked with telemetry returned; and an
  INCONCLUSIVE artifact holds until a human approves/rejects it from the dashboard.
- **Stories:** status-retrieval orchestrator; dashboard JSON payload; real-time
  dashboard (dark theme, graduated severity/threat color coding); interactive
  approve/reject control gating PDE handoff; per-execution PDF report (tiered);
  PASS→PDE forward; FAIL nuke + telemetry return; INCONCLUSIVE approval-gate hold.

## 4. Dependency Map

**Hard dependencies (X cannot start until Y exists):**
- Phase 2 (parallel inspection) ← Phase 1 (intake/routing) — nothing can be scanned
  or detonated until artifacts are classified and routed to the correct lane.
- Phase 3 (AI correlation) ← Phase 2 — Nova Pro correlation requires **both** the
  static JSON output and the dynamic behavioral telemetry as inputs.
- Phase 4 (handoff/reporting) ← Phase 3 — the dashboard JSON, PDF report, and
  PASS/FAIL/INCONCLUSIVE routing all consume the correlated threat score/findings.
- Detonation chamber ← isolated VPC + parametric AMI + launch template — the
  ephemeral EC2 must run in isolated subnets (VPC endpoints only) with a per-run
  `ec2:RunInstances` launch template and a 5-minute hard TTL.

**Shared foundations pulled forward (multi-phase reuse):**
- **AWS infrastructure (CDK v2 TypeScript stacks).** VPC/isolated subnets, IAM,
  launch template, SSM wiring, and the Nova Pro access path underpin Phases 2–4;
  deploy the infra stack early (before Lambda/Step Function code).
- **Event/telemetry schema (shared package).** A single normalized schema for
  static findings + dynamic behavior is consumed by Phase 3 correlation and Phase 4
  reporting — define once.
- **Telemetry sanitization pipeline** (entropy scrub → noise suppress → ≤25K token
  truncation) — needed before any Nova Pro call; build once, reuse.

## 5. Registered Decisions

> Durable decisions with an ID so they can be referenced and ratified, not
> re-litigated each session.

| ID | Decision | Rationale | Date | Status |
|----|----------|-----------|------|--------|
| RD-001 | Detonation uses host-native SSM execution on real ephemeral EC2 (no Docker/containers/mocks) | Behavioral telemetry must reflect true live-system behavior; containers/mocks distort syscalls/network/fs evidence | 2026-08-24 | ratified |
| RD-002 | Static and dynamic lanes run in parallel, forked by the preprocessor | Speed, and each lane produces independent evidence the correlation engine needs | 2026-08-24 | ratified |
| RD-003 | Amazon Nova Pro is the correlation/assessment engine, with exponential-backoff retry | Cross-references static ↔ dynamic evidence to eliminate false positives and unify scoring | 2026-08-24 | ratified |
| RD-004 | Static stack = cfn-lint, cfn-guard, checkov, bandit; compliance mapped to NIST SP 800-53 / ISO 27001 | Covers IaC config, policy-as-code, and Python SAST against mandated frameworks | 2026-08-24 | ratified |
| RD-005 | Verdict drives routing: PASS→PDE, FAIL→nuke + return telemetry to origin sandbox, INCONCLUSIVE→human approval gate | This is ZTIE's core enforcement mechanism as a transit hub | 2026-08-24 | ratified |
| RD-006 | Dual-output reporting: real-time dashboard (JSON) + per-execution PDF, tiered Executive/Security/Developer | Machine-readable status for ops; human-readable, audience-appropriate depth | 2026-08-24 | ratified |
| RD-007 | Ephemeral EC2 has a 5-minute hard TTL via UserData `shutdown -h +5` | Bounds cost and blast radius of every detonation | 2026-08-24 | ratified |
| RD-008 | Dashboard + DynamoDB deployed into hub account "Pipeline-Hub" (641628980935) | Central hub hosts real-time status and state tables | 2026-08-24 | ratified |

## 6. Universal Acceptance Criteria

Every deliverable, in every phase, must satisfy (kept in sync with the runbook):
1. **No mocks in the execution path** — real AWS services and real detonation; any
   test double is unit-level only and explicitly agreed.
2. **Independently validatable** — the component can be exercised end-to-end and
   its output (routing decision, scan JSON, behavioral telemetry, threat score, or
   verdict) inspected live.
3. **Zero-trust honored** — no artifact reaches the PDE without a recorded PASS
   verdict; FAIL and INCONCLUSIVE are enforced, not advisory.
