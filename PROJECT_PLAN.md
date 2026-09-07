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
> single source of truth.

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

> The "If Verified Safe" arrow is the outcome of a **human accept/reject in the
> Hub**. Full enforcement: **ACCEPT** → ZTIE pushes the hash-verified artifact
> Forensic → Pipeline-Sandbox (PDE handoff; ZTIE's job ends on landing); **REJECT**
> → destroy the artifact + detonation chamber in Forensic; **INCONCLUSIVE** → hold
> at the human approval gate. (See §2 topology + RD-008–011.)

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
  sequentially — the preprocessor forks the pipeline into two lanes. The fork/join
  mechanism (a Step Functions Parallel state joining on both-complete, emitting one
  bounded verdict-free collected record) is registered as RD-027.
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
- **Multi-account topology (three roles).** The architecture uses **separate AWS
  accounts**, each with a strict role:
  - **Pipeline-Hub (641628980935) — the brains / control plane.** Pipeline
    orchestrator, DynamoDB, dashboard, and all reporting/tracking for **ZTIE and
    PDE**, including the **human accept/reject gate** over ZTIE findings. The Hub
    **never receives, parses, executes, or stores the raw untrusted payload** — it
    handles only derived/sanitized data (metadata, scan JSON, sanitized telemetry,
    verdicts, metrics). The Hub is deliberately kept **out of the blast zone**.
  - **Forensic (360999005254) — ZTIE, self-contained + ultimate blast-radius
    containment.** Everything that touches the raw untrusted artifact lives and
    STAYS here: intake/`preprocessor`, static scanners, the VPC/isolated subnets,
    and the **ephemeral EC2 detonation host** (host-native SSM). The artifact is
    the **only** place the unknown ever executes, and it does not leave Forensic
    until a human accepts/rejects the findings in the Hub.
  - **Pipeline-Sandbox (586917955591) — the ZTIE→PDE handoff landing zone.** On
    human acceptance of ZTIE findings, ZTIE **pushes** the hash-verified artifact
    here. **The moment it lands, the artifact is under PDE control and ZTIE's
    responsibility ends.** Functional user-acceptance / execution of the (already
    ZTIE-cleared) artifact is a **PDE** activity here; Sandbox isolation is a PDE
    responsibility.
  - **Dev — artifact origin (input-only spoke, RD-019).** A developer/build
    environment from which artifacts are **submitted into** ZTIE intake. The
    crossing is **one-directional: input only.** ZTIE holds **no permissions into
    Dev** and **never writes back**; Dev sees results by **reading** ZTIE's outputs
    (dashboard/report), not by ZTIE pushing into Dev.
- **Hub-and-spoke = security boundary (RD-018).** The topology is a central **Hub**
  (brains) with isolated **spokes** (Forensic, Dev, Pipeline-Sandbox); the **AWS
  account boundary is the security wall.** Spokes talk only to the Hub —
  one-directional, least-privilege, checked at the wall — **no spoke-to-spoke**, and
  the Hub never enters the blast zone. A breach in a spoke stays in that spoke.
- **Forensic containment (RD-020).** Forensic has **no direct path to any account**;
  the **only** exit is **through the contract gate**, for both temporary/short-term
  and long-term/durable data. A bad artifact is dead-ended (rejected + destroyed) in
  Forensic; the only route toward production is a human-approved, hash-verified
  handoff through the gate.
- **Enforcement boundary.** The artifact does not leave Forensic until a human
  reviews ZTIE's findings in the Hub. **ACCEPT →** ZTIE pushes the hash-verified
  artifact Forensic → Pipeline-Sandbox (one-directional, ZTIE-initiated,
  least-privilege) and hands off to PDE. **REJECT →** ZTIE destroys the artifact
  **and** its detonation chamber (the ephemeral EC2) in Forensic; nothing is
  promoted. ZTIE performs **security clearance only** and never re-executes the
  artifact outside Forensic.
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
  (rejected, not crashed). **Phase-close additionally requires** the restore-point
  mechanism to exist and pass a live capture→change→restore test, so that
  `restore/phase-1-green` (tag + state manifest) can actually be captured at the gate.
- **Stories** _(mirrored exactly in the runbook — the two must always align):_
  - **1.1** — intake gateway endpoint _(✅ done)_
  - **1.1R** — remediation: move the durable tracking record Forensic → Hub behind
    the RD-013 data-contract gate (Hub-owned SQS door → validator Lambda → Hub
    tracking DynamoDB; fail-closed quarantine; Forensic keeps only ephemeral
    state). Concrete implementation registered as RD-016. _(✅ done)_
  - **1.R** — restore-point mechanism: build the Python state-capture + coordinated
    restore, fill `RESTORE.md` + `BOM.md`, validate live. **Prerequisite for the
    Phase 1 close** (you cannot capture `restore/phase-1-green` without it).
    _(✅ done)_
  - **1.2** — classifier (extension + metadata inspection) _(✅ done)_
  - **1.3** — routing table to static/dynamic lanes: the class label → a routing
    DECISION (plan of which controls apply); both routable classes fork into both
    Phase-2 lanes, `other_unknown`/unroutable → the safe-reject entry (1.4). A third
    contract-governed crossing on the RD-013 gate (`routing.contract.v1.json`).
    _(✅ done)_
  - **1.4** — safe-reject path for unknown types: the concrete destination for the
    `safe_reject` lane (1.3); marks the artifact SAFE_REJECTED on the Hub record
    (terminal processing outcome, not a verdict), never forwards to a scanner, never
    crashes. A fourth contract-governed crossing on the RD-013 gate
    (`reject.contract.v1.json`). _(✅ done)_

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
- **Stories:** AWS infra foundation (CDK v2: isolated VPC + VPC endpoints, IAM
  roles, ephemeral-EC2 launch template with parametric AMI + 5-min hard TTL, SSM
  wiring, Nova Pro access — the shared foundation deployed first, before any
  Lambda/Step Function code); static scanning stack integration;
  compliance-framework mapping (NIST 800-53 / ISO 27001) + signature scans (RD-025);
  detonation chamber (ephemeral EC2 + SSM host-native
  exec); behavioral telemetry capture (syscalls/network/filesystem); telemetry
  sanitization pipeline; parallel orchestration / fork.

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
  that populates the dashboard (in Pipeline-Hub) and generate the final PDF report.
  Enforce the exit gate, which is a **human accept/reject decision in the Hub** over
  ZTIE's findings. The raw artifact stays in Forensic until that decision:
  **ACCEPT →** ZTIE pushes the hash-verified artifact Forensic → Pipeline-Sandbox
  (586917955591) and hands off to PDE (ZTIE's responsibility ends on landing);
  **REJECT →** ZTIE destroys the artifact **and** its detonation chamber in
  Forensic; **INCONCLUSIVE →** holds at the human approval gate. ZTIE never
  re-executes the artifact outside Forensic.
- **Gate:** For a full run, confirm the dashboard JSON and PDF report are produced
  with tiered content (Executive / Security / Developer); on **accept**, the
  hash-verified artifact is pushed from Forensic to Pipeline-Sandbox (586917955591)
  and no un-accepted artifact ever leaves Forensic; on **reject**, the artifact +
  detonation chamber are destroyed in Forensic; an **inconclusive** artifact holds
  until a human accepts/rejects it from the dashboard.
- **Stories:** status-retrieval orchestrator; dashboard JSON payload; real-time
  dashboard (dark theme, graduated severity/threat color coding); interactive
  accept/reject control that gates the Forensic→Pipeline-Sandbox push; per-execution
  PDF report (tiered); ACCEPT → push hash-verified artifact to Pipeline-Sandbox
  (PDE handoff); REJECT → destroy artifact + detonation chamber in Forensic;
  INCONCLUSIVE → approval-gate hold.

### Cross-cutting / Governance stories
- **Not phase-bound; sequenced by readiness** and tracked in the runbook's
  [Cross-cutting / Governance stories](RUNBOOK.md) table so they aren't forgotten.
  These keep this plan and the runbook referencing the same story set (RD-015):
  - **G-1:** back-map design artifacts to candidate NIST + ISO 27001 controls (RD-014).
  - **G-2:** management-artifact integrity, an automated consistency check (`scripts/check_docs.py`) plus reusable-OS/instance separation (RD-015).
  - **G-3:** hard-pause enforcement, the Validation Debt Register plus an advancement gate (no new feature story while debt is open) plus story-closure/restore-point decoupling, wired into `scripts/check_docs.py` (RD-023). _(🟡 In Progress)_

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
| RD-005 | Verdict/decision drives routing: human ACCEPT→push to Pipeline-Sandbox (PDE handoff), REJECT→destroy artifact + detonation chamber in Forensic, INCONCLUSIVE→human approval gate | This is ZTIE's core enforcement mechanism as a transit hub | 2026-08-24 | ratified |
| RD-006 | Dual-output reporting: real-time dashboard (JSON) + per-execution PDF, tiered Executive/Security/Developer | Machine-readable status for ops; human-readable, audience-appropriate depth | 2026-08-24 | ratified |
| RD-007 | Ephemeral EC2 has a 5-minute hard TTL via UserData `shutdown -h +5` | Bounds cost and blast radius of every detonation | 2026-08-24 | ratified |
| RD-008 | Three-account topology: **Pipeline-Hub (641628980935)** = brains/control plane (orchestrator, DynamoDB, dashboard, reporting/tracking for ZTIE + PDE, human accept/reject gate); **Forensic (360999005254)** = ZTIE self-contained + ultimate blast-radius containment (intake, static, VPC, ephemeral EC2 detonation, raw payload); **Pipeline-Sandbox (586917955591)** = ZTIE→PDE handoff landing zone | Keeps the brains out of the blast zone; the account boundary is the containment wall between the artifact and its manager | 2026-08-24 | ratified |
| RD-009 | The Hub is a **control plane only**: it never receives, parses, executes, or stores the raw untrusted payload; only derived/sanitized data (metadata, scan JSON, sanitized telemetry, verdicts, metrics) crosses Forensic → Hub | Nothing keeps the payload from running on the Hub except this rule + least-privilege IAM + safe parsing; enforce it explicitly | 2026-08-24 | ratified |
| RD-010 | The artifact does not leave Forensic until a human accept/reject in the Hub. On **accept**, ZTIE **pushes** the hash-verified artifact Forensic → Pipeline-Sandbox (one-directional, ZTIE-initiated, least-privilege). On **reject**, ZTIE destroys the artifact + detonation chamber in Forensic (explicit teardown, not waiting for TTL) | Human approval is the only release; reject is terminal for the raw artifact (derived report survives in the Hub) | 2026-08-24 | ratified |
| RD-011 | ZTIE performs **security clearance only** and never re-executes the artifact outside Forensic. Once the accepted artifact lands in Pipeline-Sandbox it is **under PDE control** and ZTIE's responsibility ends; functional user-acceptance / execution of the (already ZTIE-cleared) artifact is a PDE activity, and Sandbox isolation is a PDE responsibility | Re-detonating a ZTIE-cleared artifact adds no security value and a second blast zone; functional acceptance (the human "experiencing" the artifact) is a distinct, PDE-owned concern | 2026-08-24 | ratified |
| RD-012 | **No durable data store in Forensic.** Forensic holds only **ephemeral** state — the raw artifact (S3, destroyed on reject / after handoff) and transient per-run state (Step Functions execution / short-TTL scratch). The **authoritative, durable tracking / intake / verdict record lives in the Hub** (DynamoDB) so it survives blast-zone teardown and serves as the audit trail | A durable store in a disposable blast zone is a liability: it dies (or is at risk) on nuke/rebuild, adds stateful attack surface next to detonation, and creates a second source of truth. Durable things do not belong in an ephemeral account | 2026-08-24 | ratified |
| RD-015 | **Management artifacts are first-class deliverables.** The management artifacts — PROJECT_PLAN, RUNBOOK, METHODOLOGY, RESTORE, BOM, the templates, the registered decisions, and the per-story session briefs/prompts — are held to the **same bar as the technical artifacts**: **reusable, durable, repeatable**. Concretely: (a) versioned + PR-reviewed (never straight to main); (b) covered by the restore-point system — a restore point pins the known-good governance-doc commit so code + state + governance restore as one unit; (c) kept internally consistent by a **repeatable automated check** (plan↔runbook story-sets align; every referenced RD exists; no stray template placeholders); (d) separable into a **reusable OS layer** (methodology, templates, the gate, restore discipline) vs. the **project-instance layer** (ZTIE-specific decisions, account IDs, pipeline stories) so reusability is provable; (e) a story is **not done** until its management artifacts are updated and plan↔runbook aligned, not just its code. | The management artifacts ARE the project's durable memory and the reusable operating system; if they drift, are lost, or are one-offs, the project loses its "why," its repeatability, and its restorability. They deserve the same rigor as code | 2026-08-24 | ratified |
| RD-014 | **Compliance mapping is a standing practice.** ZTIE design artifacts (registered decisions, stories, non-functional constraints) carry candidate control mappings to the **NIST family — SP 800-53 Rev 5 as the control catalog of record, plus NIST CSF and related (e.g. 800-37 RMF) as relevant — and ISO/IEC 27001:2022 Annex A.** Mappings are **proposed at authoring time** and **ratified on review by an accountable party**; they are **candidate-until-ratified**, and ZTIE claims control coverage only for **ratified** mappings. The consolidated traceability matrix lives in [`docs/COMPLIANCE.md`](docs/COMPLIANCE.md); the full back-mapping of existing artifacts is tracked as its own validated story (best executed once the core pipeline stabilizes). | Auditability: a security pipeline that checks artifacts against these frameworks should have its own design traceable to them. Mapping as a first-class, maintained practice avoids decorative/stale compliance; candidate-vs-ratified prevents overclaiming | 2026-08-24 | ratified |
| RD-013 | **Forensic → Hub is an untrusted-data boundary governed by an enforced DATA CONTRACT.** We do not police what goes *into* Forensic (assumed dirty); all rigor is on the exit. Nothing crosses to the Hub unless it satisfies a strict, bounded, allow-list schema enforced by a **Hub-owned validating ingestion gate** (Forensic holds NO direct write to Hub data). Rules: only derived data crosses (no raw payload / no executable content — the schema has no field for it); every field typed + length-capped, total size + nesting bounded; **fail-closed** — non-conforming records are quarantined, never written live; the crossing is **one-directional, least-privilege, integrity-keyed** (bound to intake_id + sha256, upsert-by-key, no cross-record writes); the **verdict is decided Hub-side by the human gate, never imported/self-asserted** from crossed data; the dashboard **escapes crossed data on render** (no stored XSS in the brains). The concrete schema is designed in the remediation story | This is the single most dangerous path: a pipe from where untrusted code runs into the account that manages everything. Everything from Forensic is attacker-influenced; the contract is the wall | 2026-08-24 | ratified |
| RD-016 | **Concrete RD-013 implementation (Story 1.1R): the Forensic → Hub door is a cross-account SQS queue owned by the Hub; the gate is a Hub validator Lambda; contract failures are quarantined to a Hub S3 bucket (+ SQS DLQ for unprocessable messages).** The Forensic intake role is granted **exactly `sqs:SendMessage` on exactly that one queue** (queue resource policy) and nothing else in the Hub. The contract is `schemas/intake-tracking.contract.v1.json` (JSON Schema draft-07, `additionalProperties:false` at every level, `contract_version` + `status` pinned by enum, `intake_id`/`sha256` pattern-locked, all strings length-capped, no payload/executable field). The validator upserts by `intake_id` (idempotent for SQS at-least-once) with a non-clobbering condition so a redelivered `RECEIVED` cannot overwrite a Hub-attached verdict. | SQS is the tightest one-directional least-privilege door (single action, single resource, native DLQ for fail-closed); at-least-once + upsert-by-key makes redelivery safe; keeping the durable table and quarantine Hub-owned means Forensic can influence *content* but never *reach* Hub data stores directly. | 2026-08-24 | ratified |
| RD-021 | **The static-scan lane (Story 2.1) is packaged as a CONTAINER-IMAGE Lambda; this does NOT violate the no-Docker rule (RD-001).** The static lane ships four tools — cfn-lint, checkov and bandit are pip packages, cfn-guard is a Rust binary — so a container-image Lambda (vs. a zip + layers) is the clean, production way to bundle a native binary alongside heavy Python trees. RD-001's no-Docker/no-container constraint is **specifically about the dynamic DETONATION host**, where a container would distort the syscall/network/fs behavioral telemetry; it does **not** apply to packaging the **non-executing** static scanners, which only parse/inspect the artifact and never run it. The lane also fixes two contract shapes (RD-013 gate): the full normalized findings document stays in **Forensic** S3 (RD-009 — it may echo artifact content) and only a bounded, derived summary crosses to the Hub as the fifth envelope kind; cfn-guard is normalized via **SARIF** (stable across versions) rather than its own JSON. | Bundling a native binary + multi-tool Python cleanly exceeds practical zip/layer limits; an image is AWS-native and production-ready. Scoping the no-Docker rule to the detonation host (its actual rationale) avoids over-applying it to inert tooling. Keeping the content-bearing findings document in Forensic and crossing only a bounded, verdict-free summary preserves the RD-009/RD-013 boundary. | 2026-08-31 | proposed |
| RD-023 | **Hard-pause / advancement-gate discipline.** The validation covenant is enforced structurally, not verbally: a **Validation Debt Register** (in [`RUNBOOK.md`](RUNBOOK.md)) lists every built-but-not-live-validated story (`🟡`/`⛔`) and its single clearing action; **no NEW feature story starts while the register is non-empty** (reworking an open `🟡`/`⛔` to clear it is allowed); and **story closure is decoupled from restore-point / capture work** (a story's ✅ depends solely on its own recorded live validation). The **executor owns calling** the pause; the **stakeholder retains final say** to accept, defer, or override. Machine-enforced by [`scripts/check_docs.py`](scripts/check_docs.py). Candidate control mappings (RD-014): NIST 800-53 r5 CA-2, CA-5, CM-3; NIST CSF ID.GV-3 / PR.IP-3; ISO 27001:2022 A.5.36, A.8.32 (all Proposed). | Converts a verbal, in-the-moment pause into a structural, machine-checkable mechanism so un-validated work (e.g. 2.0) cannot silently slip through the cracks; makes the covenant self-policing across sessions. | 2026-09-01 | proposed |
| RD-025 | **Story 2.2 — the static lane emits COMPLIANCE MAPPINGS and SIGNATURE findings as EVIDENCE, from real embedded, versioned sources.** (a) *Compliance mapping:* each normalized static finding is mapped to the NIST SP 800-53 Rev 5 + ISO/IEC 27001:2022 Annex A control(s) it IMPLICATES via a curated correspondence table (`lambdas/static_scan/compliance.py`) keyed by tool + native rule_id (exact / longest-prefix / checkov keyword-topic / signature-family), carrying a `basis` (`ratified`/`proposed`/`unmapped`) + `mapping_version`; unmatched findings are `unmapped` (empty control lists) — ZTIE never fabricates a control. It is candidate-until-ratified (mirrors RD-014) and is DISTINCT from G-1's self-audit matrix (this maps the *scanned artifact's* findings, not ZTIE's own design). (b) *Signature scans:* a pure-Python engine (`lambdas/static_scan/signatures.py`) runs a real, embedded, versioned ruleset (secret patterns modelled on detect-secrets/gitleaks families, dangerous-construct + IoC/malware markers) NON-EXECUTING (regex over the artifact bytes), emitting normalized findings tagged `check_family=signature`, `tool=signature-scan`, rule ids `ZTIE-SIG-<FAMILY>-nnn`; matched secrets are REDACTED, never echoed. Both enrich the SAME findings shape (Forensic) + the SAME derived summary (Hub) — the findings + summary contracts bump to **v1.1** (additive: the signature-scan tool, the signature family, per-finding `compliance`, a bounded summary `compliance` roll-up); the summary has its OWN Hub version pin (1.1) while the other four envelope kinds stay 1.0. NO verdict anywhere — a mapping says a finding *implicates* a control; a signature hit is *evidence*. Candidate control mappings (RD-014): NIST 800-53 r5 RA-5, SI-3, SA-11, CA-2; NIST CSF ID.RA-1 / DE.CM-8; ISO 27001:2022 A.8.8, A.5.36 (all Proposed). | The report tiers + Phase-3 correlation need "which control did this violate" and the known-bad that lint/policy/SAST miss; keeping the mapping a versioned data table (not a per-run guess) with an honest unmapped fallback avoids overclaiming, and redacted signatures + bounded roll-ups preserve the RD-009/RD-013 boundary (rich detail stays in Forensic, only bounded evidence crosses). | 2026-09-03 | proposed |
| RD-024 | **Single-threaded, AI-recommends / stakeholder-decides operating model.** The project runs as a repeatable loop, documented for a non-technical reader in [`docs/governance/OPERATING_MODEL.md`](docs/governance/OPERATING_MODEL.md): the AI acts as the senior (and only) developer and **owns sequencing**: it reads the dependency graph (see [`docs/BUILD_ORDER.md`](docs/BUILD_ORDER.md)) and which items are load-bearing / foundation-hardening, and hands the stakeholder **one** recommended next story at a time with a one-line reason ("next up: X, because Y"); the **stakeholder owns the decision** (go / not yet / do Z instead). Work is strictly **single-threaded**: exactly one story to completion, then live-validate, then record + flip status via the existing Story Close-Out Procedure, then the next recommendation. "Parallel" means only "no dependency between two stories so the AI is free to choose order," never concurrency. Sequencing is justified by **risk / hardening value, not speed**. This makes concrete the "executor proposes, stakeholder decides" split (METHODOLOGY §2) and rides on the hard-pause gate (RD-023) and the covenant (METHODOLOGY §4). Recommendations are logged in [`docs/governance/WORK_LOG.md`](docs/governance/WORK_LOG.md). Candidate control mappings (RD-014): NIST 800-53 r5 PM-2, SA-3, CA-5; NIST CSF ID.GV-1 / ID.RA; ISO 27001:2022 A.5.1, A.5.8 (all Proposed). | Names and makes referenceable the way of working we have agreed, so it can be ratified and test-driven rather than re-litigated each session; keeps sequencing risk-first, single-threaded, and stakeholder-steered, consistent with the covenant and the hard-pause gate. | 2026-09-01 | proposed |
| RD-026 | **Story 2.3 — the dynamic lane DELIVERS + EXECUTES the artifact host-native via SSM `AWS-RunShellScript`, and crosses a bounded, verdict-free RUN OUTCOME as a new envelope kind.** (a) *Delivery + execution:* the detonation orchestrator (a plain-zip Python Lambda, `lambdas/detonation/`) launches ONE ephemeral EC2 from the Story 2.0 launch template via `ec2:RunInstances` (NOT CloudFormation-per-run) into an isolated subnet (no public IP, IMDSv2, instance-initiated-shutdown = terminate), waits for the SSM agent to be Online, then executes the artifact **host-native** with the AWS-managed **`AWS-RunShellScript`** SSM document (`ssm:SendCommand`) — **NO Docker/container on the host** (RD-001). The host pulls its own artifact from Forensic S3 via a short-lived **presigned URL over the S3 VPC gateway endpoint** (the isolated host has no other network path; the artifact + URL never leave Forensic). The 5-min hard TTL (`shutdown -h +N` from 2.0's UserData) is the guaranteed teardown backstop; an explicit terminate is best-effort on top. (b) *Outcome contract:* a NEW RD-013 envelope kind (the sixth), `dynamic-run.contract.v1` (`schemas/` + two bundled copies, hash-matched via `scripts/gen_dynamic_run_contract.py`), discriminated by a `run` object and pinned SEPARATELY on the Hub gate (`DYNAMIC_RUN_CONTRACT_VERSION`, currently 1.0) so it versions independently of the other five kinds. It records WHAT ran (instance id, launch-template id + version, instance type), HOW (`ssm_command_id`, `ssm_status`, `exit_code`, byte-capped stdout/stderr TAILS + a pointer to the FULL log kept in Forensic `runs/`, RD-009), CONTAINMENT (host_native / no_docker / isolated_subnet / no public IP / IMDSv2 — asserted constants), and TTL TEARDOWN (hard-TTL minutes, shutdown behavior, teardown_observed + a SEV note if a host is confirmed still running past its TTL). **NO verdict anywhere** — `outcome` describes the ORCHESTRATION (completed / execution_error / launch_error / timed_out / delivery_error), never the artifact's safety; the verdict stays Hub-side / human-gated (Phase 4). Behavioral telemetry (syscalls/network/fs) is explicitly OUT of this contract — that is Story 2.4. Candidate control mappings (RD-014): NIST 800-53 r5 SC-44 (Detonation Chambers), SI-3, SC-7, SC-39; NIST CSF DE.CM-4 / DE.AE; ISO 27001:2022 A.8.7, A.8.22 (all Proposed). **[Live-validated 2026-09-05, ratifying the mechanism]:** the presigned-URL artifact fetch requires FOUR things together, each confirmed by a live failure until fixed — the S3 gateway endpoint's route (not an S3 interface endpoint, which conflicts with it), the detonation host's security-group EGRESS opened to the AWS-managed S3 prefix list specifically (a gateway endpoint routes to S3's public IP ranges, outside the VPC CIDR), a REGIONAL (not global) presigned host in us-east-1, and SigV4 signing (us-east-1 defaults to SigV2, which the regional endpoint rejects). | Runtime behavior is the evidence static analysis cannot produce; running the artifact only inside the isolated, ephemeral, self-terminating Forensic host (host-native, no container per RD-001) yields honest behavior without a container distorting it or the host phoning home. A versioned SSM document + presigned-URL delivery keeps the mechanism auditable and reuses the S3 VPC endpoint (no new egress). A separate, verdict-free outcome contract with its own version pin keeps the RD-009/RD-013 boundary intact (rich log stays in Forensic; only bounded evidence crosses) and leaves the verdict human-gated. | 2026-09-04 | proposed |
| RD-027 | **Story 2.6 — the two inspection lanes (RD-002) are forked + joined by an AWS Step Functions STANDARD state machine, and the join emits ONE bounded, verdict-free COLLECTED record as a new envelope kind.** (a) *Orchestration:* after the preprocessor routes a routable artifact, orchestration is a **Step Functions STANDARD state machine** whose **`Parallel` state** fans out to the **static lane** (2.1 scanners + 2.2 compliance/signature enrichment) and the **dynamic lane** (2.3 detonation) **concurrently**, joining natively on **both-branches-complete**, with a **per-branch error `Catch`** so one lane failing is RECORDED as that branch's result — not fatal to the other lane. Chosen over an **event-driven DynamoDB-conditional-join keyed by `intake_id`** because: RD-012 **EXPLICITLY names "Step Functions execution"** as the allowed *ephemeral* per-run Forensic state, so SFN adds NO durable Forensic store (execution state is ephemeral per-run and dies with the blast zone); it is **AWS-native only** (no GitHub Actions / external orchestrator); it gives a **native both-complete join + per-branch `Catch`** (directly satisfying "tolerate one-lane failure without losing the other" without hand-rolling a conditional-join state machine over DynamoDB); it is **least-privilege** (the state-machine role gets exactly the two lane-invoke actions + the one join-step invoke, nothing durable); the join is **idempotent under SQS at-least-once** because the collected record upserts Hub-side by `intake_id`+`sha256` (RD-013/016) so a redelivered branch result cannot double-write; and **both lanes already consume Forensic work queues**, so the fork augments/replaces the preprocessor's two independent enqueues with a single orchestrated fan-out rather than adding a new integration surface. (b) *Join record:* a **thin Forensic-side join step** emits ONE **bounded, derived, verdict-free** COLLECTED record as a **NEW (7th) RD-013 envelope kind** (`collected`), with its **OWN discriminator key** and its **OWN version-pin env var** (`COLLECTED_CONTRACT_VERSION`, never riding the shared `CONTRACT_VERSION`), following the RD-013 per-kind gate + RD-016 integrity-keyed upsert pattern exactly. It **references (does NOT duplicate)** the two already-crossed per-lane summaries (the static-scan summary + the dynamic-run outcome) and carries **NO verdict / safe / approved / forward field** — the verdict stays Hub-side / human-gated (Phase 4). Chosen over having **Phase 3 re-join** the two summaries because the DoD requires "one bounded derived record ready for Phase 3," and a single collected envelope is a cleaner, contract-first Phase-3 input than making the correlation engine re-discover and re-join two independent crossings. Candidate control mappings (RD-014): NIST 800-53 r5 SI-4, CA-7, SC-7, AU-6; NIST CSF DE.CM / DE.AE / DE.AE-2; ISO 27001:2022 A.8.16, A.5.36 (all Proposed). | The plan (RD-002) forks the lanes but never fixed HOW; naming Step Functions Standard with a Parallel state makes the fork/join referenceable and rides RD-012's own explicit allowance of ephemeral SFN execution state, so we get AWS-native both-complete join + per-branch fault tolerance with no durable Forensic store and least-privilege IAM. A single bounded, verdict-free collected record (its own contract + version pin + discriminator) keeps the RD-009/RD-013 boundary intact (rich per-lane detail stays where it was crossed; the join only references it) and hands Phase 3 one clean derived input instead of a re-join burden. | 2026-09-07 | proposed |

## 6. Universal Acceptance Criteria

Every deliverable, in every phase, must satisfy (kept in sync with the runbook):
1. **No mocks in the execution path** — real AWS services and real detonation; any
   test double is unit-level only and explicitly agreed.
2. **Independently validatable** — the component can be exercised end-to-end and
   its output (routing decision, scan JSON, behavioral telemetry, threat score, or
   verdict) inspected live.
3. **Zero-trust honored** — no artifact reaches the PDE without a recorded PASS
   verdict; FAIL and INCONCLUSIVE are enforced, not advisory.

## 7. Operator Requirements (headline needs to design toward)

> Captured from the stakeholder as the top-level "what I need to see/have." Every
> Phase 2–4 story should be checked against these. Designed, not yet built.

**The three headline "views" the operator requires:**
1. **"What is this program trying to do?"** — the behavior/intent view: detonation
   telemetry (syscalls, network/call-home, files) mapped to **MITRE ATT&CK**, with
   **Nova Pro** combining the observed behavior with the MITRE catalog into a
   reasoned, scored capability inventory. *(Built: Phase 2 capture → Phase 3
   correlation → Phase 4 display.)*
2. **"Just show me the open ports."** — a fast, scannable **port-indexed view**,
   each port cross-referenced to its MITRE technique(s), with an **occurrence count
   ("times tickled")** and **start/end times** (machine-generated, measured as
   offsets from detonation start — never a human/observer clock). *(Phase 2/4.)*
3. **"What's deployed, where — and when is it active?"** — an **inventory** of which
   components live in which account (the **BOM**, produced/maintained by the restore
   story **1.R**) **plus live operational visibility** ("a detonation is running /
   ports are being scanned now") on the dashboard. *(Inventory = 1.R; live status =
   Phase 4 dashboard.)*

**Restore points on the dashboard.** Restore points are the highest-value safety
asset; beyond building the mechanism (**1.R**), the operator wants **restore-point
status/health surfaced on the dashboard** as a first-class, visible element.
*(Mechanism = 1.R; dashboard visibility = Phase 4 requirement.)*
