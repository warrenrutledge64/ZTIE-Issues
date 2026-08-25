# ZTIE Security Analysis Pipeline — Execution Runbook

> **Living progress ledger.** This runbook mirrors [`PROJECT_PLAN.md`](PROJECT_PLAN.md)
> but is execution-oriented: every story is a trackable item with dependencies,
> do-it steps, a validation check, and a completion marker. The plan is the
> *what/why*; this runbook is the *do-it-and-track-it*. **This file is the source
> of truth for story status** — and it carries the binding Validation &
> Advancement Gate below.
>
> **Ordering:** stories are sequenced by **dependency + reuse value** — do what
> unblocks or gets reused by the most downstream work first; pull genuine shared
> foundations forward and build them once. Validation gates are sacred: no phase
> is done without its live validation, and nothing builds on unproven ground.

## Architecture Flow (reference)

> Full narrative + named-program reference in [`DOCS/ARCHITECTURE.md`](DOCS/ARCHITECTURE.md);
> scope/decisions in [`PROJECT_PLAN.md`](PROJECT_PLAN.md). Named programs:
> `preprocessor` (P1), `accuracy` + `gap_analysis` (P3), `status retrieval` (P4).

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

> **Enforcement (human accept/reject in the Hub):** the raw artifact stays in
> **Forensic** until a human reviews ZTIE's findings in the Hub. **ACCEPT** → ZTIE
> pushes the hash-verified artifact Forensic → Pipeline-Sandbox (the ZTIE→PDE
> handoff; on landing it is under PDE control and ZTIE's job ends). **REJECT** →
> ZTIE destroys the artifact **and** its detonation chamber in Forensic.
> **INCONCLUSIVE** → hold at the human approval gate. ZTIE performs security
> clearance only and never re-executes the artifact outside Forensic.
> Detonation uses **ephemeral** EC2 (host-native SSM, no Docker) — never
> "temporary." Three-account topology: **Pipeline-Hub 641628980935** (brains /
> control plane), **Forensic 360999005254** (ZTIE self-contained + blast
> containment), **Pipeline-Sandbox 586917955591** (ZTIE→PDE handoff). ServiceNow
> is out of scope. (Full detail: DOCS/ARCHITECTURE.md, PROJECT_PLAN.md RD-008–011.)

## Status Legend

`⬜ Not Started` · `🟡 In Progress` · `⛔ Blocked` · `✅ Done (validated)`

## Validation & Advancement Gate (BINDING)

> The **enforced state machine** for every story and phase. Validation results —
> recorded, live, confirmed — **drive** status changes and **dictate** whether work
> advances. Status is never set on inference; advancement is never taken on faith.

**Roles.** The **validator** (usually the user, on the live system) runs the check
and confirms the outcome; the **executor records** the result (outcome + date) in
the story's *Validation Result* field and only then changes the status. The
executor never self-certifies a story done.

**Story state machine.** A story moves only on a recorded validation result:

| From | Event | To |
|------|-------|----|
| ⬜ Not Started | work begins | 🟡 In Progress |
| 🟡 In Progress | validation **passes** (recorded, confirmed) | ✅ Done (validated) |
| 🟡 In Progress | validation **fails / incomplete** | 🟡 stays (or ⛔ if externally blocked) |
| ✅ Done | (never auto-reverts; a regression opens a new remediation story) | — |

- **No result → no ✅.** Absent a recorded, confirmed pass, a story stays 🟡.
- **Fail → no advancement.** If a story fails or is only partly validated, **stay
  on that story** until it passes. The next session's objective becomes *fix +
  re-validate this story* — not the next one. Mark **⛔ Blocked** only when
  something external prevents progress; otherwise it stays 🟡 and in-focus.
- **The covenant is not to be circumvented.** "How do we get around validation?" is
  a **drift signal**, not a plan. Reworking a 🟡 story (including fixing a defect
  found after build) is normal in-progress work — it never justifies bypassing the
  gate or flipping status on inference. Only a recorded live pass of the **final**
  code earns ✅; when a defect is found pre-validation, **fix-then-validate-once**.
  (Full principle: `METHODOLOGY.md` §4, hard rule 3.)

**Hard advancement gate.** A story **cannot begin** until **every** story in its
`Depends on` column is ✅. If a dependency is not ✅, the executor does **not**
start the dependent story's work. (No override.)

**Phase gate.** A phase closes **only** when its end-of-phase gate returns a
recorded, confirmed pass. On phase-close — and not before:
1. capture the restore point (see [`RESTORE.md`](RESTORE.md)),
2. record it in [`BOM.md`](BOM.md),
3. set the phase row in the Progress Summary to ✅.

**Per-session handshake (enforced by the prompt template).** Every session, before
new work:
1. **Close out the prior story:** if it is 🟡 pending validation, obtain the
   result → on pass, record it + flip ✅ (+ Completed date); on fail, keep 🟡 and
   re-focus on it.
2. **Check the advancement gate:** confirm this story's `Depends on` are all ✅; if
   not, stop and surface the blocker.

**Recording a result.** Each story tracks a *Validation Result* — a one-line dated
record (`pass — <what was checked>, <date>, confirmed by <who>` or
`FAIL — <what failed>, <date>`). This line is the auditable driver behind the
status marker; the marker without a recorded result is not a valid ✅.

## Story Close-Out Procedure (how the ledger stays current)

> There is **no hook, CI job, or script** that mutates this file. The ledger is
> kept current by the **executor, by hand, as a mandatory step of closing a story**
> — enforced by the gate above. These are the exact edits and the commit
> convention.

**The paired-commit convention.** Work and status are **separate commits**:
- **Commit A — the work.** Build the story, push to a branch, open a PR. The story
  **stays 🟡** — merging code does not make it done.
- **Commit B — the status flip.** Only after the user confirms a **live pass**, make
  a **small, dedicated commit** that touches the runbook (and, at a phase close,
  the inventory + tag). Status flips ride small, fast-merging PRs so the ledger on
  the main line never lies. If a flip and the main line disagree, the main line
  wins — reconcile by merging the recorded flip.

**On a confirmed pass, edit exactly these three things in this runbook:**
1. **Summary-table row** — change the story's status cell 🟡 → ✅ and fill the
   **Completed** date.
2. **Detail-block header** — change the story's detail heading from
   `🟡 In Progress` to `✅ Done (validated)`.
3. **`Validation Result:` line** — replace the `pending` text with a dated,
   one-line record quoting *what the user actually checked live*
   (`pass — <what was checked>, <date>, confirmed by <who>`).

**On a fail / incomplete:** change nothing to ✅. Keep the row 🟡 (or ⛔ if
externally blocked), and record the failure in the `Validation Result` line
(`FAIL — <what failed>, <date>`). The next session re-focuses on this story.

**If the story closes a phase (and only on a recorded pass):** additionally
1. create the annotated `restore/phase-<N>-green` tag at the validated commit (see
   [`RESTORE.md`](RESTORE.md)),
2. add the restore-point row to [`BOM.md`](BOM.md) (tag + SHA +
   manifest path),
3. flip the **phase row** in the Progress Summary to ✅.

**Then — the warm handoff (mandatory).** Author the NEXT story's brief + prompt
under `session-briefs/`, including a `Lessons Learned / Carry-Forward` section with
THIS session's actual lessons. A close-out without the next handoff is incomplete.

## Progress Summary

| Phase | Scope | Gate | Status |
|-------|-------|------|--------|
| **P1 — Intake & Routing** | Intake gateway + preprocessor classifier/router (+ 1.1R record→Hub, 1.R restore mechanism) | Representative artifacts route to correct lanes; unknown types safe-rejected; **restore mechanism (1.R) passes a live capture→change→restore test so `restore/phase-1-green` can be captured** | ⬜ Not Started |
| **P2 — Parallel Inspection** | Static (cfn-lint/cfn-guard/checkov/bandit) + Dynamic detonation (ephemeral EC2 + SSM), run concurrently | Known-bad artifact yields both static findings + real behavioral telemetry; EC2 torn down | ⬜ Not Started |
| **P3 — AI Correlation** | Nova Pro correlation → unified threat score, findings, remediations, verdict | Paired static+dynamic inputs yield one score + correlated findings; a false positive is reconciled | ⬜ Not Started |
| **P4 — Handoff & Reporting** | Status-retrieval → dashboard JSON + PDF; PASS→PDE / FAIL→nuke / INCONCLUSIVE→approval gate | Full run produces tiered outputs and correct verdict-driven routing incl. human approve/reject | ⬜ Not Started |

---

## Phase P1 — Intake and Routing

_Gate: feed an IaC template, a raw script, and an unknown/unroutable artifact through the intake gateway; confirm each known type is classified and routed to the correct downstream lane, and the unknown type is safe-rejected (not crashed)._

| Story | Title | Depends on | Status | Completed | Restore tag |
|-------|-------|-----------|--------|-----------|-------------|
| 1.1 | Intake gateway endpoint (payload/artifact entry) | — | ✅ | 2026-08-24 | |
| 1.1R | Remediation: move durable tracking record Forensic → Hub behind the data-contract gate (RD-012/013/016) | 1.1 | 🟡 | | |
| 1.R | Restore-point mechanism: state-capture + coordinated restore; fill RESTORE.md + BOM.md (prerequisite for the P1 close) | 1.1R | ⬜ | | |
| 1.2 | Preprocessor classifier (extension + metadata inspection) | 1.1 | ⬜ | | |
| 1.3 | Routing table → static & dynamic lanes | 1.2 | ⬜ | | |
| 1.4 | Safe-reject path for unknown/incompatible types | 1.2 | ⬜ | | |

**1.1 — Intake gateway endpoint**  ✅ _Done (validated)_
- Steps: stand up the ZTIE intake gateway that accepts an incoming deployment payload / code artifact and hands it to the preprocessor. Built as API Gateway (POST /intake, IAM/SigV4 auth) → Python 3.12 Lambda → encrypted/versioned/block-public S3 (raw body) + on-demand encrypted DynamoDB (intake record, status=RECEIVED). Deployed self-contained in **Forensic 360999005254** per RD-008/009; the untrusted body is stored as `application/octet-stream` (claimed type kept as metadata only).
- **Validation Result:** pass — live on Forensic 360999005254 (2026-08-24), confirmed by the user: signed POST /intake returned 201 with intake_id=62360e03-dfb1-4655-ac52-2a55345ab6f0, status=RECEIVED, sha256=5563154a…ea57; S3 head-object showed ContentType=application/octet-stream + claimed=text/yaml + matching sha; DynamoDB item showed status=RECEIVED + matching sha256; an unsigned POST returned 403 (zero-trust auth gates).
- **Advancement gate:** ✅ — unblocks 1.2 (preprocessor classifier).
- **Known deviation (remediation queued as 1.1R):** 1.1 placed the durable intake DynamoDB table in **Forensic**, which pre-dates RD-012/013. Per the covenant, 1.1 stays ✅ for what it validated (intake accepts + persists; mechanism works); the account placement is remediated forward by story **1.1R**, not by retro-editing 1.1.

**1.1R — Remediation: durable tracking record → Hub, behind the data-contract gate**  🟡 _In Progress (built; pending live validation)_
- Steps: move the **authoritative, durable** intake/tracking/verdict record out of Forensic into the **Hub** (DynamoDB) per RD-012. Leave Forensic holding only ephemeral state — the raw artifact (S3) + transient per-run state; no durable store in Forensic. Establish the **RD-013 data-contract boundary**: a Hub-owned validating ingestion gate (Forensic gets NO direct write to Hub data), a strict bounded allow-list schema (derived fields only, typed, length-capped, size/nesting bounded, no payload/executable field), **fail-closed** quarantine of non-conforming records, one-directional least-privilege crossing, integrity-keyed by intake_id + sha256 (upsert, no cross-record writes). The **verdict is decided Hub-side by the human gate — never imported** from crossed data; the dashboard **escapes crossed data on render**.
- **As built (RD-016):** concrete implementation = a Hub-owned **cross-account SQS ingest queue** (Forensic intake role granted **only** `sqs:SendMessage` on that one queue) → a **Hub validator Lambda** that enforces `schemas/intake-tracking.contract.v1.json` (draft-07 allow-list, `additionalProperties:false` everywhere, `contract_version`/`status` enum-pinned, `intake_id`/`sha256` pattern-locked, all strings capped, **no payload field**) → **PASS** upserts (idempotently, by `intake_id`, non-clobbering vs a Hub verdict) into the **Hub tracking DynamoDB**; **FAIL** writes the raw envelope to a **Hub quarantine S3 bucket** (never the live table); unprocessable messages redrive to a **DLQ**. New CDK stack `ZtieHubTrackingStack` (Hub account); the Forensic intake stack **no longer has a durable DynamoDB** and only emits the derived envelope. Two-account deploy: **Hub stack first**, then the Forensic intake stack wired with the Hub queue URL/ARN (see the 1.1R brief for the exact commands).
- **Validation Result:** _pending — user confirms live: a Forensic intake writes a contract-valid record to the Hub table via the gate; a deliberately malformed / oversized / injection-crafted record is REJECTED (fail-closed) and quarantined, never written live; Forensic holds no durable table; and Forensic has no direct write permission on the Hub table._
- **On pass (and only then):** record the dated Validation Result + flip ✅ per the Close-Out Procedure.
- **Advancement gate:** should land before Phase 2 builds on the tracking record; absorbs the earlier "surface derived metadata Forensic → Hub" follow-up (now this story).

**1.R — Restore-point mechanism (prerequisite for the P1 close)**  ⬜ _Not Started_
- Steps: build the **Python** state-capture tool (read-only; captures a **restore-relevant projection** — identity + desired-state fields only, never raw resource objects, to avoid false-positive drift) and the **coordinated restore** (re-apply captured state; CloudFormation restore must re-apply template + parameters + stack-level **tags**). Fill `RESTORE.md` (state-capture + coordinated-restore procedures) and `BOM.md` (the real deployed inventory) for ZTIE. Per RD-012, the durable state to capture is the **Hub** (tracking DynamoDB + infra) and **infra projections** (CFN stacks, S3 config, Lambda name/runtime/code_sha256, any SSM params); Forensic's ephemeral raw-payload/scratch is disposable and is rebuilt, not restored. Per **RD-015**, the manifest must also **pin the known-good governance-doc commit** (PROJECT_PLAN, RUNBOOK, METHODOLOGY, RESTORE, BOM, templates, decisions) so a restore returns **code + state + governance as one unit**. Any mutating restore is gated behind a deliberate confirm that reads the terminal and **fails safe to NO** (Python `input()`).
- **Validation Result:** _pending — user confirms live: capture the current state to a timestamped manifest; make a trivial deliberate change; run the coordinated restore back to the manifest; confirm the restore-relevant projection matches (no false drift) and BOM reflects reality._
- **On pass (and only then):** record the dated Validation Result + flip ✅ per the Close-Out Procedure.
- **Advancement gate:** **prerequisite for the Phase 1 close** — `restore/phase-1-green` (tag + manifest) cannot be captured until this exists and passes. Recommended to land after 1.1R (capture the final Forensic→Hub topology, not the pre-remediation one).

**1.2 — Preprocessor classifier**  ⬜ _Not Started_
- Steps: inspect file extensions + metadata to classify each artifact (IaC template vs raw script vs other).
- **Validation Result:** _pending — feed known IaC and known script artifacts and confirm each is classified correctly._
- **On pass (and only then):** record + flip ✅ per the Close-Out Procedure.
- **Advancement gate:** blocks 1.3 and 1.4.

**1.3 — Routing table to lanes**  ⬜ _Not Started_
- Steps: route IaC to the correct linters and raw scripts to their distinct auditing paths; wire both the static and dynamic lanes as fork targets.
- **Validation Result:** _pending — confirm each classified type lands in the correct downstream lane._
- **On pass (and only then):** record + flip ✅.
- **Advancement gate:** blocks all of Phase 2 (nothing to inspect until routing exists).

**1.4 — Safe-reject path for unknown types**  ⬜ _Not Started_
- Steps: for unroutable/incompatible artifacts, reject safely so an incompatible scan never crashes the pipeline.
- **Validation Result:** _pending — submit an unknown/unsupported artifact and confirm it is rejected cleanly (no crash)._
- **On pass (and only then):** record + flip ✅.
- **Advancement gate:** required for the P1 gate (resilience criterion).

---

## Phase P2 — Parallel Inspection Paths

_Gate: a known-bad artifact produces (a) static findings from the scanning stack AND (b) observed runtime behavior from a real detonation, with both lanes running in parallel and each emitting structured output; the ephemeral EC2 is confirmed torn down via hard TTL._

| Story | Title | Depends on | Status | Completed | Restore tag |
|-------|-------|-----------|--------|-----------|-------------|
| 2.0 | AWS infra foundation (CDK v2: VPC/isolated subnets, IAM, launch template, SSM, Nova Pro access) | 1.3 | ⬜ | | |
| 2.1 | Static scanning stack (cfn-lint, cfn-guard, checkov, bandit) | 1.3 | ⬜ | | |
| 2.2 | Compliance-framework mapping (NIST SP 800-53 / ISO 27001) + signature scans | 2.1 | ⬜ | | |
| 2.3 | Detonation chamber — ephemeral EC2 + host-native SSM execution | 2.0 | ⬜ | | |
| 2.4 | Behavioral telemetry capture (syscalls / network / filesystem) | 2.3 | ⬜ | | |
| 2.5 | Telemetry sanitization pipeline (entropy scrub → noise suppress → ≤25K truncation) | 2.4 | ⬜ | | |
| 2.6 | Parallel orchestration / fork of the two lanes | 2.1, 2.3 | ⬜ | | |

**2.0 — AWS infra foundation**  ⬜ _Not Started_
- Steps: deploy the CDK v2 TypeScript infra stack (VPC isolated subnets w/ VPC endpoints only, IAM, per-run launch template, SSM wiring, Nova Pro access) BEFORE any Lambda/Step Function code. Shared foundation for P2–P4.
- **Validation Result:** _pending — confirm the stack deploys and isolated networking + launch template exist live._
- **On pass (and only then):** record + flip ✅.
- **Advancement gate:** blocks 2.3 (detonation needs the isolated VPC + launch template).

**2.1 — Static scanning stack**  ⬜ _Not Started_
- Steps: integrate cfn-lint, cfn-guard, checkov, bandit as non-executing scanners; emit structured JSON results.
- **Validation Result:** _pending — scan a known-bad IaC/script and confirm findings JSON is emitted._
- **On pass (and only then):** record + flip ✅.
- **Advancement gate:** feeds 2.2 and the fork (2.6); its JSON is a Phase 3 input.

**2.2 — Compliance mapping + signature scans**  ⬜ _Not Started_
- Steps: evaluate source against mandated frameworks (NIST SP 800-53 / ISO 27001); run signature-based scans for known vulns/malicious patterns.
- **Validation Result:** _pending — confirm a violation maps to the correct framework control and a known signature is detected._
- **On pass (and only then):** record + flip ✅.

**2.3 — Detonation chamber (ephemeral EC2 + SSM)**  ⬜ _Not Started_
- Steps: deploy payload into a highly restricted ephemeral EC2 via `ec2:RunInstances` launch template; run host-native via SSM (NO Docker); enforce 5-minute hard TTL (`shutdown -h +5`).
- **Validation Result:** _pending — detonate a sample payload; confirm real EC2 runs it and is torn down by TTL._
- **On pass (and only then):** record + flip ✅.
- **Advancement gate:** blocks 2.4 (no telemetry without a real run).

**2.4 — Behavioral telemetry capture**  ⬜ _Not Started_
- Steps: monitor and capture system calls, network attempts, and file operations during detonation; emit behavioral data.
- **Validation Result:** _pending — confirm syscall/network/fs activity of a known-bad payload is captured._
- **On pass (and only then):** record + flip ✅.

**2.5 — Telemetry sanitization pipeline**  ⬜ _Not Started_
- Steps: entropy scrub → noise suppress → ≤25K token truncation, preparing telemetry for Nova Pro.
- **Validation Result:** _pending — confirm raw telemetry is sanitized and truncated within the token budget._
- **On pass (and only then):** record + flip ✅.
- **Advancement gate:** required before any Phase 3 Nova Pro call.

**2.6 — Parallel orchestration / fork**  ⬜ _Not Started_
- Steps: fork the pipeline so static and dynamic lanes run concurrently after routing; join their outputs for handoff to Phase 3.
- **Validation Result:** _pending — confirm both lanes execute in parallel for one artifact and both outputs are collected._
- **On pass (and only then):** record + flip ✅.
- **Advancement gate:** closes Phase 2; feeds Phase 3 aggregation.

---

## Phase P3 — AI Correlation and Assessment

_Gate: given paired static + dynamic outputs, Nova Pro returns a single unified threat score, correlated findings (static ↔ dynamic evidence), and prioritized remediations; a case where static flags a risk but dynamic proves benign (or vice-versa) is correctly reconciled (false-positive elimination demonstrated)._

| Story | Title | Depends on | Status | Completed | Restore tag |
|-------|-------|-----------|--------|-----------|-------------|
| 3.1 | Telemetry aggregation / normalization (shared schema) | 2.6 | ⬜ | | |
| 3.2 | Nova Pro correlation engine (exponential-backoff retry) | 3.1, 2.5 | ⬜ | | |
| 3.3 | accuracy + gap_analysis synthesis | 3.2 | ⬜ | | |
| 3.4 | Unified threat scoring + prioritized remediations | 3.3 | ⬜ | | |
| 3.5 | Verdict derivation (PASS / FAIL / INCONCLUSIVE) | 3.4 | ⬜ | | |

**3.1 — Telemetry aggregation / normalization**  ⬜ _Not Started_
- Steps: aggregate raw telemetry, error logs, and JSON outputs from both lanes into the shared normalized event schema.
- **Validation Result:** _pending — confirm static + dynamic outputs for one artifact normalize into a single combined record._
- **On pass (and only then):** record + flip ✅.

**3.2 — Nova Pro correlation engine**  ⬜ _Not Started_
- Steps: pass the combined record to Amazon Nova Pro; correlate static misconfigurations with dynamic behavioral indicators; exponential-backoff retry on throttling.
- **Validation Result:** _pending — confirm a correlated assessment is returned for a paired input._
- **On pass (and only then):** record + flip ✅.

**3.3 — accuracy + gap_analysis synthesis**  ⬜ _Not Started_
- Steps: run the accuracy and gap_analysis programs to synthesize the data and eliminate false positives.
- **Validation Result:** _pending — confirm a static-only false positive is reconciled against benign dynamic evidence._
- **On pass (and only then):** record + flip ✅.

**3.4 — Unified threat scoring + remediations**  ⬜ _Not Started_
- Steps: produce a single unified threat score, detailed findings, and prioritized remediations.
- **Validation Result:** _pending — confirm one score + ranked findings + remediations are emitted for a run._
- **On pass (and only then):** record + flip ✅.

**3.5 — Verdict derivation**  ⬜ _Not Started_
- Steps: derive the enforcement verdict from the score/findings: PASS / FAIL / INCONCLUSIVE.
- **Validation Result:** _pending — confirm each of the three verdicts can be produced from representative inputs._
- **On pass (and only then):** record + flip ✅.
- **Advancement gate:** closes Phase 3; the verdict drives all Phase 4 routing.

---

## Phase P4 — Handoff and Reporting

_Gate: for a full run, confirm the dashboard JSON and PDF report are produced with tiered content (Executive / Security / Developer); on human ACCEPT, ZTIE pushes the hash-verified artifact from Forensic to Pipeline-Sandbox (586917955591) and no un-accepted artifact ever leaves Forensic; on REJECT, the artifact + detonation chamber are destroyed in Forensic; an INCONCLUSIVE artifact holds until a human accepts/rejects it from the dashboard._

| Story | Title | Depends on | Status | Completed | Restore tag |
|-------|-------|-----------|--------|-----------|-------------|
| 4.1 | Status-retrieval orchestrator | 3.5 | ⬜ | | |
| 4.2 | Dashboard JSON payload | 4.1 | ⬜ | | |
| 4.3 | Real-time dashboard (dark theme, graduated severity/threat color coding) | 4.2 | ⬜ | | |
| 4.4 | Interactive accept/reject control (Hub) gating the Forensic→Pipeline-Sandbox push | 4.3, 4.7 | ⬜ | | |
| 4.5 | Per-execution PDF report (tiered: Executive / Security / Developer) | 4.1 | ⬜ | | |
| 4.6 | ACCEPT → ZTIE pushes hash-verified artifact Forensic → Pipeline-Sandbox (PDE handoff) | 4.1 | ⬜ | | |
| 4.7 | REJECT → destroy artifact + detonation chamber in Forensic; INCONCLUSIVE → hold at approval gate | 4.1 | ⬜ | | |

**4.1 — Status-retrieval orchestrator**  ⬜ _Not Started_
- Steps: orchestrate delivery of the correlated data; transform AI insights into the outputs the dashboard and report consume.
- **Validation Result:** _pending — confirm the orchestrator emits the correlated payload for a completed run._
- **On pass (and only then):** record + flip ✅.

**4.2 — Dashboard JSON payload**  ⬜ _Not Started_
- Steps: build the comprehensive JSON that populates the dashboard (pipeline status, verdicts, findings, cost/sensor/AMI health metrics).
- **Validation Result:** _pending — confirm the JSON schema is populated for a real run._
- **On pass (and only then):** record + flip ✅.

**4.3 — Real-time dashboard**  ⬜ _Not Started_
- Steps: render a real-time dashboard on a dark background with graduated color coding for severity/threat tiers (low/medium/high/critical distinguishable at a glance).
- **Validation Result:** _pending — confirm the dashboard reflects a live run with correct severity coloring._
- **On pass (and only then):** record + flip ✅.

**4.4 — Interactive approve/reject control**  ⬜ _Not Started_
- Steps: from the dashboard, let a human reviewer approve or reject findings; the approval decision gates whether the object may pass downstream to the PDE (human-in-the-loop for INCONCLUSIVE).
- **Validation Result:** _pending — confirm an approve unlocks PDE handoff and a reject blocks it._
- **On pass (and only then):** record + flip ✅.

**4.5 — Per-execution PDF report (tiered)**  ⬜ _Not Started_
- Steps: generate the PDF with three audience tiers — Executive (risk score + one-paragraph verdict), Security (MITRE ATT&CK mappings, behavioral chains, Sigma rules), Developer (exact failure cause, file/line, remediation, static-dynamic correlation).
- **Validation Result:** _pending — confirm a run produces a PDF with all three tiers populated._
- **On pass (and only then):** record + flip ✅.

**4.6 — ACCEPT → push artifact to Pipeline-Sandbox (PDE handoff)**  ⬜ _Not Started_
- Steps: on a human ACCEPT of ZTIE findings in the Hub, ZTIE pushes the hash-verified artifact Forensic → Pipeline-Sandbox (586917955591), one-directional and least-privilege. On landing the artifact is under PDE control and ZTIE's responsibility ends. ZTIE never re-executes the artifact outside Forensic.
- **Validation Result:** _pending — confirm an accepted artifact is pushed to Pipeline-Sandbox and that no un-accepted/unverified artifact ever leaves Forensic._
- **On pass (and only then):** record + flip ✅.

**4.7 — REJECT → destroy artifact + chamber in Forensic / INCONCLUSIVE hold**  ⬜ _Not Started_
- Steps: on a human REJECT, destroy the artifact **and** its detonation chamber (the ephemeral EC2) in Forensic — explicit teardown, not waiting for TTL; nothing is promoted (the derived report survives in the Hub). On INCONCLUSIVE, hold at the manual approval gate for human review.
- **Validation Result:** _pending — confirm REJECT destroys artifact + detonation chamber in Forensic and INCONCLUSIVE holds at the gate._
- **On pass (and only then):** record + flip ✅.
- **Advancement gate:** together with 4.4 and 4.6, closes Phase 4 — the full enforcement decision flow.

---

## Cross-cutting / Governance stories

_Not phase-bound; sequenced by readiness. Tracked here so they aren't forgotten._

| Story | Title | Depends on | Status | Completed | Restore tag |
|-------|-------|-----------|--------|-----------|-------------|
| G-1 | Back-map design artifacts to candidate NIST family + ISO 27001 controls (RD-014) | — | ⬜ | | |
| G-2 | Management-artifact integrity: automated consistency check + reusable-OS/instance separation (RD-015) | — | ⬜ | | |

**G-1 — Compliance back-mapping (RD-014)**  ⬜ _Not Started_
- Steps: populate [`DOCS/COMPLIANCE.md`](DOCS/COMPLIANCE.md) by proposing candidate control mappings for the existing design artifacts — registered decisions RD-001…RD-014, the non-functional constraints, and each story — against **NIST SP 800-53 Rev 5 (catalog of record), NIST CSF, related NIST (RMF)**, and **ISO/IEC 27001:2022 Annex A**. Each row carries a rationale and Status=`Proposed`.
- **Best executed** once the core pipeline design stabilizes (avoid mapping a moving target); new artifacts still propose mappings at authoring time in the meantime.
- **Validation Result:** _pending — an accountable reviewer ratifies (or corrects) the candidate mappings; Status flips `Proposed` → `Ratified` per reviewed artifact. ZTIE claims coverage only for ratified mappings._
- **On pass (and only then):** record the dated Validation Result + flip ✅ per the Close-Out Procedure. (May be validated incrementally per artifact group.)
- **Advancement gate:** none blocks it and it blocks nothing; it is a standing auditability practice, not a pipeline dependency.

**G-2 — Management-artifact integrity (RD-015)**  ⬜ _Not Started_
- Steps: make RD-015 enforceable, not aspirational. (a) Build a **Python consistency checker** (`scripts/check_docs.py`, Python-first; later wired into AWS-native CI) that **fails (non-zero)** if: PROJECT_PLAN and RUNBOOK story-sets diverge (per phase); any referenced `RD-0NN` doesn't exist in the decisions table; stray template placeholders (`{{…}}`) remain outside the known-intentional template files; or a story marked ✅ lacks a dated Validation Result line. (b) **Separate the reusable-OS layer** (METHODOLOGY, templates, the gate, restore discipline — generic, seeds a new project unchanged) from the **project-instance layer** (RD-008…, account IDs, pipeline stories), and document the boundary so reusability is provable, not asserted. (c) Ensure the restore-point manifest **pins the known-good governance-doc commit** (coordinate with story 1.R) so code + state + governance restore as one unit.
- **Validation Result:** _pending — user confirms live: the checker passes on a clean tree, and is proven to FAIL on each injected defect (deliberate plan/runbook divergence, a dangling RD ref, a stray placeholder, a ✅ story with no validation line); and the reusable-OS/instance boundary doc is reviewed as accurate._
- **On pass (and only then):** record the dated Validation Result + flip ✅ per the Close-Out Procedure.
- **Advancement gate:** none blocks it; strongly recommended before Phase 1 close so the plan↔runbook alignment (RD-015) is machine-enforced, not eyeballed. Coordinates with 1.R (governance-doc commit in the manifest).

---

## Universal Acceptance Criteria (apply to EVERY story/phase gate)

In addition to each story's own validation, every deliverable must satisfy:
1. **No mocks in the execution path** — real AWS services and real detonation on ephemeral EC2 (host-native SSM, no Docker); any test double is unit-level only and explicitly agreed.
2. **Independently validatable** — the component can be exercised end-to-end live and its output (routing decision, scan JSON, behavioral telemetry, threat score, or verdict) inspected.
3. **Zero-trust honored** — no artifact reaches the PDE without a recorded PASS verdict; FAIL (nuke + return telemetry) and INCONCLUSIVE (human approval gate) are enforced, not advisory.
4. **Management artifacts are first-class (RD-015)** — a story is **not done** until its management artifacts are updated to the same bar as its code: the story's brief + runbook entry current, **PROJECT_PLAN and RUNBOOK in exact alignment**, any new/changed registered decisions + candidate control mappings recorded, all doc changes PR-reviewed (never straight to main), and the governance kept restorable alongside the code. Reusable, durable, repeatable — held to the technical bar.

---

## Ledger Maintenance

- Update a story's **Status** as work moves; set **✅** only after its validation
  passes live **and** the Validation Result line is recorded (see the Story
  Close-Out Procedure).
- On each **phase-close pass**: capture a restore point, record it in the
  inventory, set the phase row ✅.
- Runbook and [`PROJECT_PLAN.md`](PROJECT_PLAN.md) must stay in sync — the plan
  defines scope, the runbook tracks execution.
- **Per-story brief + prompt:** filled from the templates into `session-briefs/`.
- **Next-session brief AND prompt are authored during the current session** — the
  final task each session, including Lessons Learned / Carry-Forward, so the next
  session starts with zero cold-start.
