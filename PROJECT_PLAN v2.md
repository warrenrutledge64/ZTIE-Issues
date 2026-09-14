Here is the optimized and compacted **ZTIE Project Plan**.

### How it was compacted:

1. **RD Table Trimming:** The Registered Decisions (Section 5) had become unwieldy (thousands of words). I extracted the *enforcement rules* and *architectural mechanisms* from the walls of text and converted them into concise bullet points. The utility is identical, but it is now scannable.
2. **Constraint Grouping:** The 16 non-negotiable constraints were combined into thematic groups (Topology, Execution, Governance) to reduce redundancy.
3. **Story Flattening:** Phase story lists were flattened into tight, inline lists.
4. **Preservation:** The architectural diagram (with Step 0 and Gitleaks), the universal criteria, and the operator requirements remain fully intact.

---

```markdown
# ZTIE Security Analysis Pipeline — Project Plan

> **Purpose:** Defines scope, phases, decisions, and acceptance criteria. Organized by **phase**. 
> **Companion Docs:** `RUNBOOK.md` tracks daily build execution & status. `docs/PRODUCT_PLAN.md` (RD-036) tracks charter-level vision/stakeholders. Story status lives ONLY in the runbook.

## 1. Project Identity
The **Zero Trust Inspection Engine (ZTIE)** is a four-phase security analysis pipeline that inspects every deployment payload before it reaches production. Artifacts are classified, subjected to **parallel** static and dynamic inspection, correlated by Amazon Nova Pro, and gated. Only artifacts verified as safe are pushed downstream to the **Platform Delivery Engine (PDE)**.
*   **Named programs:** `preprocessor` (Phase 1), `accuracy` & `gap_analysis` (Phase 3), `status retrieval` (Phase 4).

## 1a. Architecture Flow

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

```

## 2. Non-Negotiable Constraints

* **Zero Trust & Execution:** No "skip" paths. Detonation uses real, ephemeral EC2s with host-native SSM execution (no Docker mocks).
* **Three-Account Topology & Boundaries:**
* **Pipeline-Hub:** The brains. Holds durable records and dashboards. Never parses, stores, or executes raw payloads.
* **Forensic:** The blast zone. Receives raw payloads, executes them, and holds temporary state. No direct network exit except via data contracts.
* **Pipeline-Sandbox:** PDE landing zone. ZTIE pushes here upon human approval.


* **One-Way Spoke-to-Hub Flow:** Spokes communicate to the Hub via strict, allow-listed data contracts. Spokes *never* read Hub data directly.
* **Enforcement & Handoff:** Verdicts (PASS/FAIL) require human action. ACCEPT pushes verified hash to Sandbox. REJECT destroys the artifact and EC2.
* **Validation & Governance:** Nothing is "done" without a live validation pass. Code changes breaking local tests must be fixed prior to validation. Restore-point discipline requires building from known-good tags.

## 3. Phases & Milestones

### Phase 1 — Intake and Routing

* **Goal:** Stand up gateway and `preprocessor` to classify and route IaC and scripts to appropriate paths.
* **Gate:** Artifacts properly classified and routed; unroutable files safely rejected.
* **Stories:** 1.1 (Gateway) ✅, 1.1R (Tracking to Hub via SQS) ✅, 1.R (Restore-point mechanics) ✅, 1.2 (Classifier) ✅, 1.3 (Routing Table) ✅, 1.4 (Safe Reject) ✅.

### Phase 2 — Parallel Inspection Paths

* **Goal:** Fork pipeline into Static (linters, Gitleaks, NIST/ISO checks) and Dynamic (ephemeral EC2 SSM detonation) lanes.
* **Gate:** Known-bad artifact produces static findings and dynamic telemetry in parallel; EC2 hard TTL confirmed.
* **Stories:** 2.0 (AWS Infra/SSM/VPC), 2.1 (Static Container), 2.2 (Compliance/Signatures), 2.2-G (Gitleaks), 2.3 (Detonation Chamber), 2.4 (Telemetry Capture), 2.5 (Telemetry Sanitize), 2.6 (Parallel SFN Fork/Join).

### Phase 3 — AI Correlation and Assessment

* **Goal:** Amazon Nova Pro cross-references static/dynamic data to eliminate false positives and yield three independent 0-100 risk scores.
* **Gate:** AI correlates findings, eliminates false positives, and generates prioritized remediations without assigning a final action verdict.
* **Stories:** 3.1 (Hub Normalize), 3.2 (Nova Pro Correlator), 3.3 (Synthesize/Score - *Three-score model*), 3.4 (Remediations), 3.5 (Advisory Verdict).

### Phase 4 — Handoff and Reporting

* **Goal:** Dashboard generation, audience-tiered PDF reports, and the human enforcement gate.
* **Gate:** Dashboard/PDF produced. ACCEPT pushes to Sandbox; REJECT triggers Forensic destruction.
* **Stories:** 4.1 (Status Read-Model), 4.2 (Dashboard Payload), 4.3 (Render SPA), 4.4 (Accept/Reject UI), 4.5 (PDF Report), 4.6 (PDE Push), 4.7 (Destroy), 4.8 (Cognito Auth), 4.9 (Widen Crossing Detail).

### Governance (Cross-Cutting)

* **G-1:** NIST/ISO Control mapping. **G-2:** Artifact integrity tests ✅. **G-3:** Hard-pause debt register ✅. **G-4:** Charter product view (PRODUCT_PLAN).

## 4. Dependency Map

* **Hard Limits:** Phase 2 requires Phase 1. Phase 3 requires Phase 2. Phase 4 requires Phase 3. Detonation requires VPC/Launch Template foundations.
* **Shared Reusables:** CDK infra underpins P2-P4. Telemetry schema shared by P3/P4.

## 5. Registered Decisions (Summarized)

> *Note: Full design records, rationales, and exact control mappings live in `docs/proposals/` and `docs/architecture/`.*

| ID | Core Decision / Mechanism | Date | Status |
| --- | --- | --- | --- |
| **RD-001** | **Host-Native Execution:** Detonation uses real EC2s via SSM `AWS-RunShellScript`. No containers/mocks. | 26-08-24 | Ratified |
| **RD-002** | **Parallel Lanes:** Static and dynamic lanes run concurrently. | 26-08-24 | Ratified |
| **RD-003** | **Nova Pro Correlation:** AI correlates data to drop false positives, using jittered exponential backoff. | 26-08-24 | Ratified |
| **RD-004** | **Static Stack:** Base tools are cfn-lint, cfn-guard, checkov, bandit. | 26-08-24 | Ratified |
| **RD-005** | **Verdict Routing:** Human ACCEPT pushes to PDE. REJECT destroys. INCONCLUSIVE holds. | 26-08-24 | Ratified |
| **RD-008** | **3-Account Topology:** Hub (Brains), Forensic (Blast Zone), Pipeline-Sandbox (PDE Handoff). | 26-08-24 | Ratified |
| **RD-009** | **Hub Isolation:** Hub never parses, stores, or executes raw payloads. Only derived data crosses. | 26-08-24 | Ratified |
| **RD-012** | **No Durable Forensic Stores:** Forensic holds ephemeral data only. Durable records live in Hub DDB. | 26-08-24 | Ratified |
| **RD-013** | **Data Contracts:** Forensic→Hub flow is strictly governed by allow-listed, fail-closed JSON schemas. | 26-08-24 | Ratified |
| **RD-015** | **Management Artifacts:** Governance docs (plans, runbooks) are treated as versioned, restorable code. | 26-08-24 | Ratified |
| **RD-021** | **Static Image Lambda:** Static tools packaged as a container Lambda (exempt from RD-001 no-container rule). | 26-08-31 | Proposed |
| **RD-023** | **Hard Pause Gate:** Validation Debt Register blocks new feature stories while debt is open. | 26-09-01 | Proposed |
| **RD-024** | **Single-Threaded AI:** AI recommends next story based on build order; stakeholder decides. | 26-09-01 | Proposed |
| **RD-025** | **Signatures/Compliance:** Signatures emit evidence, mapped to NIST/ISO via static table. (Amended by RD-050). | 26-09-03 | Proposed |
| **RD-026** | **Dynamic Outcomes:** Bounded `dynamic-run` contract crosses to Hub. No verdict included. | 26-09-04 | Proposed |
| **RD-027** | **Two-Tier Endpoints:** SSM is Always-On (1 AZ). Bedrock/Logs/SQS are ephemeral per run (saves ~$66/mo). | 26-09-07 | Proposed |
| **RD-028** | **Multi-Tenancy:** Hard isolation per subscriber via vended accounts. Users within subscriber share trust. | 26-09-07 | Ratified |
| **RD-029** | **SFN Fork/Join:** Step Functions Parallel state orchestrates lanes, emitting a single `collected` record. | 26-09-07 | Proposed |
| **RD-030** | **Telemetry Capture:** `strace` captures network/fs/syscalls host-native. Full trace stays in Forensic. | 26-09-08 | Proposed |
| **RD-031** | **Telemetry Sanitize:** Pure 3-stage pipeline (entropy scrub, noise suppress, <25K token truncate). | 26-09-10 | Proposed |
| **RD-032** | **Legacy Teardown:** Off-architecture V1 lineages decommissioned based on strict tag matching. | 26-09-10 | Proposed |
| **RD-038** | **Three-Score Assessment:** Nova Pro produces 3 independent risk scores (Static, Dynamic, Combined). | 26-09-13 | Proposed |
| **RD-040** | **Advisory Verdict:** Phase 3 derives `recommended_verdict` deterministically. Never auto-acted upon. | 26-09-13 | Proposed |
| **RD-043** | **Dashboard SPA:** RENDER-ONLY static SPA. Re-derives nothing. Escapes all data to prevent XSS. | 26-09-13 | Proposed |
| **RD-047** | **PDE Push:** ACCEPT triggers Forensic-side push. Hash verifies. Artifact pushed directly to Sandbox. | 26-09-13 | Proposed |
| **RD-048** | **Control Plane Reads:** Spokes NEVER read Hub data. Hub hands out decisions for spokes to verify. | 26-09-13 | Proposed |
| **RD-049** | **KMS Auth Decisions:** Hub produces KMS asymmetric signatures. Spokes verify offline via public key. | 26-09-13 | Ratified |
| **RD-050** | **Gitleaks Integration:** Compiled binary supersedes 2.2 Secret regexes. Dangerous/Malware regexes retained. | 26-09-14 | Ratified |

## 6. Universal Acceptance Criteria

1. **No mocks in the execution path** — Real AWS services and detonation.
2. **Independently validatable** — Components must be executable end-to-end and observable live.
3. **Zero-trust honored** — Artifacts cannot reach PDE without recorded human PASS.

## 7. Operator Requirements (Headline Views)

1. **Behavior/Intent View:** Telemetry mapped to MITRE ATT&CK via Nova Pro capability inventory.
2. **Port-Indexed View:** Scannable ports linked to MITRE with occurrence counts & start/end times.
3. **Inventory & Live Status:** Live pipeline activity, BOM layout, and Restore Point health surfaced on dashboard.

```

```
