# ZTIE Security Analysis Pipeline — Execution Runbook

> **Living progress ledger.** This runbook mirrors [`PROJECT_PLAN.md`](PROJECT_PLAN.md)
> but is execution-oriented: every story is a trackable item with dependencies,
> do-it steps, a validation check, and a completion marker. The plan is the
> *what/why*; this runbook is the *do-it-and-track-it*. **This file is the source
> of truth for story status** — and it carries the binding Validation &
> Advancement Gate below. The charter-level *why/for-whom* view (vision, outcomes,
> scope, stakeholders, risk; no story detail or status) is
> [`docs/PRODUCT_PLAN.md`](docs/PRODUCT_PLAN.md) (RD-036).
>
> **What this runbook tracks.** It is now the complete ledger for ALL work: the
> numbered pipeline stories (1.x/2.x/3.x/4.x), the governance stories (G), and the
> Floor & Harvest transition track (A/B/C, the move to a reusable component
> archive). If a story exists anywhere in the project, its status lives here — the
> numbered pipeline stories, the governance (G) stories, and the Floor & Harvest
> (A/B/C) transition track all live in the **one master table** in the Build order
> section below.
>
> **Ordering:** stories are sequenced by **dependency + reuse value** — do what
> unblocks or gets reused by the most downstream work first; pull genuine shared
> foundations forward and build them once. Validation gates are sacred: no phase
> is done without its live validation, and nothing builds on unproven ground.

## Validation Debt Register (open, built-but-not-live-validated work)

> **Live POA&M of validation debt.** This register lists every story that is built
> but has never had a recorded live validation (status `🟡 In Progress` or
> `⛔ Blocked`). It exists so an un-validated story can never silently slip through
> the cracks. Binding rules:
>
> - **A NEW feature story may not begin while this register is non-empty.** The only
>   in-progress work permitted while debt is open is reworking or validating an
>   already-open `🟡`/`⛔` entry (that is how debt is cleared). See the
>   [Validation & Advancement Gate](#validation--advancement-gate-binding).
> - **An entry is cleared ONLY by that story's own recorded live validation**, never
>   on paper and never on inference. Wanting to "resolve" open work by editing this
>   table is the exact drift the covenant forbids.
> - **Roles.** The **executor owns calling** the hard pause (surfacing when we must
>   stop to validate, back up, or consolidate); the **stakeholder retains final say**
>   to accept, defer, or override.
>
> This table is machine-parseable and enforced by [`scripts/check_docs.py`](scripts/check_docs.py).

| Story | Why not done | Single action to clear | Owner |
|-------|--------------|------------------------|-------|
| 3.2 | **Built, not yet live-validated.** The Hub-side Nova Pro correlation engine (RD-035) — the `hub_correlate` Lambda + the `correlation.contract.v1` result record + the `ZtieHubTrackingStack` wiring — is complete and passes the full offline bar (55 pure/stubbed tests, ruff clean, `tsc` no new error type, contract no-drift), but it makes a REAL Amazon Nova Pro (Bedrock) call, so per the covenant it stays 🟡 until a recorded live pass of the FINAL code. | Deploy the updated `ZtieHubTrackingStack` in the Hub (641628980935), submit/reuse one intake so a `combined_event` lands, then verify the `correlation_result` recorded on the tracking item (status `correlated`, `attempts` present, findings bounded, NO verdict/safe/forward key) per [`docs/session-briefs/story-3.2-LIVE-RUNBOOK.md`](docs/session-briefs/story-3.2-LIVE-RUNBOOK.md). | stakeholder |

> **Register status: 1 open (Story 3.2).** The advancement gate is **ARMED**: no NEW
> feature story (outside the register) may start until 3.2 clears its recorded live
> pass. Reworking / validating 3.2 itself is the permitted work. A story goes into the
> register the moment it is built-but-unvalidated, and comes out only on its own
> recorded live pass.
>
> _Prior entry (cleared 2026-09-12):_ **Story 3.1** (telemetry aggregation / normalization,
> RD-033) was cleared by its own recorded live validation in the Hub 641628980935. Its
> first live run (2026-09-11, intake `d2ae6be3-…`) produced a correct combined event but
> exposed a stream-loop (the idempotency compare rendered DynamoDB's `Decimal` round-trip
> as a quoted string ≠ the freshly-built plain `int`, so it re-wrote forever); FIXED
> (PR #87: `_canonical()` + Decimal-round-trip regression tests) and RE-VALIDATED live
> 2026-09-12 (intake `a7f21334-ba18-4ef5-beeb-87ac487574fe`): 4 writes as the inputs
> landed then `unchanged; no write (idempotent)` — the writes stopped, no loop.
>
> _Prior entry (cleared 2026-09-11):_ **Story 2.5** (telemetry sanitization pipeline,
> RD-031) was cleared by its own recorded live validation in Forensic 360999005254 +
> Hub 641628980935 — 4/4 DoD on the FIXED code (intake_id
> cf37768a-b249-4c41-9c9c-3b6797f08908). A pre-existing latent defect was found live
> and fixed first (fix-then-validate-once): the detonation Lambda's `iam:PassRole`
> grant targeted the wrong role (the Lambda's own execution role instead of the
> `ZtieForensicInfraStack` detonation INSTANCE role), so `ec2:RunInstances` was denied
> `UnauthorizedOperation` and no host ever launched (the SFN branch still "SUCCEEDED"
> via its per-branch Catch — a benign-looking no-op lane). Root cause was a wrong
> `-c detonationInstanceRoleArn` value at deploy time; corrected to the instance-role
> ARN and redeployed. On the fixed run: host `i-055f788c37276f7ab` launched + ran
> host-native + self-terminated on TTL; full 23,869-byte trace stayed in Forensic
> (`traces/cf37768a…/behavior-trace.txt`, RD-009); the crossed `sanitized` record
> showed `raw_events:173` -> `noise_suppressed:84` -> `kept/emitted:89`,
> `entropy_redactions:1` (secret `AKIA…` scrubbed to `[REDACTED:…]`, absent from the
> crossed view), artifact ops preserved (`execve`/`chmod`/`loot.txt`/`exfil.dat`),
> `estimated_tokens:2847 <= 25000`, `truncated:false`; no verdict/safe/forward key
> crossed.
>
> _Prior entry (cleared 2026-09-10):_ **Story 2.4** (behavioral telemetry capture,
> RD-030) was cleared by its own recorded live validation in Forensic 360999005254 +
> Hub 641628980935 — 4/4 DoD on the FIXED code (intake_id
> 16c2af41-e898-410d-b723-44b798f4f0d3). A pre-flip defect was found live and fixed
> first (fix-then-validate-once): strace traced a `sh -c 'if head|grep…'` wrapper and
> missed the artifact's own subtree; corrected to trace the artifact directly with
> `strace -ff` (per-PID files) + `sync`, then re-validated.
>
> _Prior entry (cleared 2026-09-08):_ **Story 2.6** (parallel orchestration / fork,
> RD-029) was cleared by its own recorded live validation in Forensic 360999005254 +
> Hub 641628980935 — all 4/4 DoD passed on the FIXED code. A `raw_script` artifact
> (`intake_id cfae6f8c-aa45-4e63-9383-ecb6f2f82569`) was submitted via intake; the
> preprocessor started ONE Step Functions execution (`ztie-cfae6f8c…`) whose Parallel
> state ran BOTH lanes CONCURRENTLY (execution history: `StaticLaneInvoke` +
> `DynamicLaneInvoke` both entered/started at 18:28:50 and ran with overlapping
> windows, succeeding at 18:29:29 and 18:29:53 — real ~38s/~63s work, not a no-op),
> joined on both-complete, and the terminal collector crossed ONE bounded, verdict-free
> `collected` record to the Hub tracking table: `both_complete: true`, both lanes
> `lane_status: completed` (static `highest_severity: none` + `findings/` pointer;
> dynamic `outcome: completed` + `runs/` pointer), NO verdict/safe/approved/forward
> field (grep clean). **Defect found + fixed during validation (fix-then-validate-once):**
> the first run (`intake_id 3f732083…`) came back with both lanes `errored`
> (`both_complete:false`) because the live static-scan + detonation lanes were still on
> pre-2.6 code (deployed for 2.1/2.3) and took the SQS path — returning
> `{"batchItemFailures": []}` — instead of the new `_is_direct_invoke` path; the join
> CORRECTLY recorded that as `errored` (no hang, no drop, no fabricated verdict). Fix
> was to REDEPLOY both lane stacks so they ship the 2.6 direct-invoke handler; the
> LIVE-RUNBOOK now makes those two redeploys an explicit pre-fork step. 2.6 closes
> Phase 2. See [Story 2.6 in STORY_DETAIL.md](docs/STORY_DETAIL.md#story-2-6).
>
> _Prior entry (cleared 2026-09-08):_ **Story 2.0E** (two-tier detonation endpoints,
> RD-027) was cleared by its own recorded live validation in Forensic 360999005254 —
> all 5/5 DoD passed: idle = S3 gateway + the 3 always-on SSM endpoints only (zero
> ephemeral tier); during a run the 3 ephemeral endpoints (`logs`/`sqs`/`bedrock-runtime`,
> tagged `ztie:ephemeral-endpoint=detonation` + IntakeId) were created and torn down;
> the detonation reached `ssm_status=Success` / `ZTIE-DETONATION-OK` / `outcome=completed`
> with a verdict-free Hub record; and a sweep-triggering run cleared a planted stale
> tagged endpoint AND still completed with its ephemeral tier (after an on-branch fix
> for a conflicting-DNS-domain sweep-recreate race — see
> [Story 2.0E in STORY_DETAIL.md](docs/STORY_DETAIL.md#story-2-0e)). Tag `restore/story-2.0E-green`.
>
> _Prior entry (cleared):_ Story 2.3 (detonation chamber — the first ZTIE story
> that actually EXECUTES an artifact) was cleared by its own recorded live
> validation (2026-09-05, in
> Forensic 360999005254: a `raw_script` artifact was submitted via intake, routed to
> `dynamic_detonation`, launched ONE ephemeral EC2 `i-00b8af8d57fd43571` from launch
> template `lt-045ddce7fdac386db`, executed host-native via SSM `AWS-RunShellScript`
> (`Rc: 0`, stdout `ZTIE-DETONATION-OK` + `uid=0(root)...`, no Docker/container),
> confirmed `terminated` on the 5-minute hard TTL (`teardown_observed: true`), and
> crossed a bounded, verdict-free run-outcome record to the Hub tracking table —
> `lane: dynamic_detonation`, `outcome: completed`, correct containment flags, no
> verdict/safe/forward field anywhere; see [Story 2.3 in STORY_DETAIL.md](docs/STORY_DETAIL.md#story-2-3)).

## Operational Debt Register (open, non-validation follow-through)

> **Live POA&M of OPERATIONAL debt — a SEPARATE ledger from the Validation Debt
> Register above, deliberately kept distinct so neither pollutes the other.** This
> register lists open operational / infrastructure / cost / hygiene follow-through
> that is NOT built-but-unvalidated feature work: cost-cleanup remainders, deferred
> teardowns, orphaned-resource sweeps, config drift to reconcile, and similar. It
> exists so that a new tier, session, or story is **never unaware of the debt that
> is riding** — the debt surfaces automatically at session start.
>
> Binding rules:
> - **Every session's STEP 0 reads this register** (the session-START prompt points
>   here), and [`scripts/check_docs.py`](scripts/check_docs.py) **prints every open
>   entry on every run** so it cannot be missed.
> - Unlike the Validation Debt Register, an open operational-debt entry does **NOT**
>   arm the feature-advancement gate — it does not block new stories. It is a
>   **visibility + accountability** ledger: the executor must SURFACE open entries at
>   session start and the stakeholder decides whether to action, defer, or accept them.
> - An entry is added the moment operational debt is knowingly deferred, and removed
>   only when the follow-through is actually done (with a dated evidence note), never
>   on inference.
> - This register is machine-parsed by `check_docs.py`; keep the table shape
>   `| ID | Debt (what is riding) | Next action | Owner | Opened |`.

| ID | Debt (what is riding) | Next action | Owner | Opened |
|----|-----------------------|-------------|-------|--------|
| OD-001 | **Hub stale-stack cleanup (Phase 2 of RD-032 cost remediation) not yet done.** After the VPC bleed was stopped, these off-architecture / prototype Hub stacks remain and still carry cost (Lambda/WAF/Cognito/S3): `ztie-detonation-chamber-production` (+ nested IAM stack), `aws-sam-cli-managed-default`, `ztie-hub-frontend/backend/cognito-stack`, `ztie-dev-identity/hosting/waf-shield`. FOUR pipeline stacks (`PipelineStack`, `ZTIE-Pipeline-Stack`, `ZTIE-IAM-Deployment-Stack`, `ZTIE-CrossAccount-Pipeline`) are pending a run-recency check. **DO NOT delete `ztie-asymmetric-cmk` (live KMS attestation key) or any `PDE-*`/`pde-*` stack.** | Run the Hub pipeline run-recency check, classify, then `delete-stack` the confirmed-stale set (safety rules in the prompt). Full playbook: [`docs/session-briefs/cost-cleanup-phase2-PROMPT.md`](docs/session-briefs/cost-cleanup-phase2-PROMPT.md). | stakeholder | 2026-09-11 |
| OD-002 | **Forensic stale-lineage teardown (Phase 2 of RD-032) not yet confirmed safe.** The `DeployForensics-ZtieAnalyzer/Collector/Ingestion/Processor`, `ztie-forensic-inspection`, and `Forensic-Unified-Baseline` stacks look superseded but export `pde-*-production` values, so they need the import-safety check **run in a real `[FORENSIC]` shell** (it has landed in the Hub by mistake repeatedly — a Hub run always says "exports nothing" and is meaningless). | In a `[FORENSIC]` (360999005254) CloudShell, run the import-safety check; if nothing imports them, `delete-stack` the dead lineage (consumers before exporters). Playbook: [`docs/session-briefs/cost-cleanup-phase2-PROMPT.md`](docs/session-briefs/cost-cleanup-phase2-PROMPT.md). | stakeholder | 2026-09-11 |
| OD-003 | **CDK/Node build toolchain is aging out.** `cdk deploy` in CloudShell warns the AWS SDK for JS v3 will require **Node >= 22** after early Jan 2027 (CloudShell currently runs Node v20), and CDK reports a newer release available (`2.1141.0` vs the repo's pinned `aws-cdk`/`aws-cdk-lib` `^2.140.0`, `@types/node ^20`). Deploys work today; this is forward-looking hygiene, not a break. Also surfaces the deprecated-API notices (`pointInTimeRecovery` -> `pointInTimeRecoverySpecification`; `logRetention` -> `logGroup`) to modernize at the same time. Surfaced during the Story 3.1 live validation (2026-09-11/12). | Bump `infra/package.json` (`aws-cdk` + `aws-cdk-lib` to a current 2.x, `@types/node` to `^22`), move the CloudShell runbooks to Node 22, migrate the two deprecated CDK APIs, then `cdk diff`/`synth` + one no-op `cdk deploy` per stack to confirm no drift. Track as its own small chore PR. | stakeholder | 2026-09-12 |

> **Register status: 3 open (OD-001, OD-002, OD-003).** OD-001/OD-002 are OPTIONAL
> additional cost savings following the completed VPC remediation (RD-032); OD-003 is
> forward-looking build-toolchain hygiene (Node/CDK version bump + deprecated-API
> migration). NONE of these block feature work (an OD entry does NOT arm the
> advancement gate), but they MUST be surfaced at the start of every session until
> cleared.

## Architecture Flow (reference)

> Full narrative + named-program reference in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md);
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
> is out of scope. (Full detail: docs/ARCHITECTURE.md, PROJECT_PLAN.md RD-008–011.)

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

**Validation-debt gate (no new feature work on open debt).** In addition to the
dependency check above, **NO NEW FEATURE STORY may begin while the
[Validation Debt Register](#validation-debt-register-open-built-but-not-live-validated-work)
is non-empty.** Reworking or validating an existing `🟡`/`⛔` entry is explicitly
**allowed and NOT gated** (that is precisely how debt is cleared); only genuinely
new feature work is blocked. This clause is machine-enforced by
[`scripts/check_docs.py`](scripts/check_docs.py), which fails if any `🟡`/`⛔` story
is missing from the register or if a new feature story is marked started/✅ while the
register is non-empty. (`⛔` is treated the same as `🟡` for the register.)

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

## Build order (dependency-driven)

> **Single pane of glass.** Every story lives in the one master table
> below, in dependency (build) order. This is the daily source of truth for
> status; [`PROJECT_PLAN.md`](PROJECT_PLAN.md) remains the overall scope
> reference. The full per-story record (Steps / As built / dated Validation
> Result / Advancement gate) is archived verbatim in
> [`docs/STORY_DETAIL.md`](docs/STORY_DETAIL.md); the detail index at the
> bottom of this section links each started story straight to it.

| Build tier | Track | Story | Title | Depends on | Status | Phase | Completed | Restore tag |
|-----------|-------|-------|-------|-----------|--------|-------|-----------|-------------|
| 0 | pipe | [1.1](docs/STORY_DETAIL.md#story-1-1) | Intake gateway endpoint (payload/artifact entry) | — | ✅ | P1 | 2026-08-24 |  |
| 0 | F&H | A.1 | Re-apply the capture-tooling Phase-2 target extension onto latest `main` (via the A.4 PR; stale branch intentionally not merged to avoid reverting governance state) | — | ✅ | - |  | (folded into A.4 PR) |
| 1 | pipe | [1.1R](docs/STORY_DETAIL.md#story-1-1r) | Remediation: move durable tracking record Forensic → Hub behind the data-contract gate (RD-012/013/016) | 1.1 | ✅ | P1 | 2026-08-25 |  |
| 1 | pipe | [1.2](docs/STORY_DETAIL.md#story-1-2) | Preprocessor classifier (extension + metadata inspection) | 1.1 | ✅ | P1 | 2026-08-25 |  |
| 2 | pipe | [1.R](docs/STORY_DETAIL.md#story-1-r) | Restore-point mechanism: state-capture + coordinated restore; fill RESTORE.md + BOM.md (prerequisite for the P1 close) | 1.1R | ✅ | P1 | 2026-08-25 |  |
| 2 | pipe | [1.3](docs/STORY_DETAIL.md#story-1-3) | Routing table → static & dynamic lanes | 1.2 | ✅ | P1 | 2026-08-27 |  |
| 2 | pipe | [1.4](docs/STORY_DETAIL.md#story-1-4) | Safe-reject path for unknown/incompatible types | 1.2 | ✅ | P1 | 2026-08-27 |  |
| 3 | pipe | [2.0](docs/STORY_DETAIL.md#story-2-0) | AWS infra foundation (CDK v2: VPC/isolated subnets, IAM, launch template, SSM, Nova Pro access) | 1.3 | ✅ | P2 | 2026-09-02 | `restore/story-2.0-green` |
| 3 | pipe | [2.1](docs/STORY_DETAIL.md#story-2-1) | Static scanning stack (cfn-lint, cfn-guard, checkov, bandit) | 1.3 | ✅ | P2 | 2026-09-01 |  |
| 4 | pipe | [2.2](docs/STORY_DETAIL.md#story-2-2) | Compliance-framework mapping (NIST SP 800-53 / ISO 27001) + signature scans | 2.1 | ✅ | P2 | 2026-09-03 |  |
| 4 | pipe | [2.3](docs/STORY_DETAIL.md#story-2-3) | Detonation chamber — ephemeral EC2 + host-native SSM execution | 2.0 | ✅ | P2 | 2026-09-05 | `restore/story-2.3-green` |
| 4 | F&H | A.2 | Validate Story 2.0 live (7 DoD checks) → record + flip ✅ | 2.0 | ✅ | - |  | `restore/story-2.0-green` |
| 4 | F&H | A.3 | Confirm Story 2.1 ✅ on `main` (no re-run); fold into the floor | 2.1 | ✅ | - |  | (folds into floor) |
| 5 | pipe | [2.0E](docs/STORY_DETAIL.md#story-2-0e) | **Worry 1 (idle cost):** two-tier detonation endpoints — SSM control channel always-on (single AZ, ~$22/mo), logs/sqs/bedrock-runtime ephemeral per-run (~$66/mo recovered) (RD-027) | 2.3 | ✅ | P2 | 2026-09-08 | `restore/story-2.0E-green` |
| 5 | pipe | [2.6](docs/STORY_DETAIL.md#story-2-6) | Parallel orchestration / fork of the two lanes | 2.1, 2.3 | ✅ | P2 | 2026-09-08 |  |
| 5 | F&H | A.4 | Institute deployed-state restore points: capture + verify both accounts, commit manifests, fill BOM's 11 pending rows | A.1, A.2 | ✅ | - |  | `restore/phase-2-floor-green` |
| 6 | pipe | [3.1](docs/STORY_DETAIL.md#story-3-1) | Telemetry aggregation / normalization (shared schema) | 2.6 | ✅ | P3 | 2026-09-12 |  |
| 6 | F&H | [A.5](docs/STORY_DETAIL.md#story-a-5) | Correct the Floor & Harvest plan drift: exit target 2.2 → the next un-built pipeline story as the graph leaves it (Story 2.4, since 2.6 closed ✅ 2026-09-08); rewrite the full-stop history (2.2/2.3 shipped old-way after the audit) | A.4 | ✅ | - | 2026-09-08 | (docs) |
| 6 | F&H | [A.6](docs/STORY_DETAIL.md#story-a-6) | Push the outstanding deployed-state restore tags `restore/phase-2-floor-green` + `restore/story-2.3-green` (owner action) | A.4, 2.3 | ✅ | - | 2026-09-08 | `restore/phase-2-floor-green`, `restore/story-2.3-green` |
| 7 | pipe | [2.4](docs/STORY_DETAIL.md#story-2-4) | Behavioral telemetry capture (syscalls / network / filesystem) | 2.3, A.5, A.6 | ✅ | P2 | 2026-09-10 |  |
| 8 | pipe | [2.5](docs/STORY_DETAIL.md#story-2-5) | Telemetry sanitization pipeline (entropy scrub → noise suppress → ≤25K truncation) | 2.4 | ✅ | P2 | 2026-09-11 |  |
| 0 | gov | [G-3](docs/STORY_DETAIL.md#story-g-3) | Hard-pause enforcement: Validation Debt register + advancement gate (no new feature story while debt open) + story-closure/restore-point decoupling; wire into `check_docs.py` (RD-023) | — | ✅ | - | 2026-09-12 |  |
| 6 | F&H | [C.3](docs/STORY_DETAIL.md#story-c-3) | Shared generator + Hub-gate seam (RD-034): collapse the 10 bespoke contract generators into one shared writer + collapse the 8 duplicated Hub-gate kind trios into one data-driven registry; `awsio` kept per-lane by design (bundling). Behaviour-preserving, byte-identical | A.4 | ✅ | - | 2026-09-12 | `restore/shared-seam-green` |
| 0 | gov | [G-2](docs/STORY_DETAIL.md#story-g-2) | Management-artifact integrity: automated consistency check + reusable-OS/instance separation (RD-015) | — | ⬜ | - |  |  |
| 9 | pipe | [3.2](docs/STORY_DETAIL.md#story-3-2) | Nova Pro correlation engine (exponential-backoff retry) | 3.1, 2.5 | 🟡 | P3 |  |  |
| 10 | pipe | [3.3](docs/STORY_DETAIL.md#story-3-3) | accuracy + gap_analysis synthesis | 3.2 | ⬜ | P3 |  |  |
| 11 | pipe | [3.4](docs/STORY_DETAIL.md#story-3-4) | Unified threat scoring + prioritized remediations | 3.3 | ⬜ | P3 |  |  |
| 12 | pipe | [3.5](docs/STORY_DETAIL.md#story-3-5) | Verdict derivation (PASS / FAIL / INCONCLUSIVE) | 3.4 | ⬜ | P3 |  |  |
| 5 | tenancy | [T.1](docs/STORY_DETAIL.md#story-t-1) | **Worry 2 (tenant isolation) — DESIGN SPIKE (doc-only, may proceed early — protects Phase-4 design):** write `docs/architecture/MULTI_TENANCY.md` capturing the RD-028 decisions (per-subscriber Forensic account = hard boundary; within-org shared-trust + org-shared dashboard; per-subscriber isolation granularity; residue bounded by the ephemeral host) + migration path from today's single shared Forensic account; ratify RD-028. No code. | 2.3 | ⬜ | - |  |  |
| 13 | pipe | [4.1](docs/STORY_DETAIL.md#story-4-1) | Status-retrieval orchestrator | 3.5 | ⬜ | P4 |  |  |
| 14 | pipe | [4.2](docs/STORY_DETAIL.md#story-4-2) | Dashboard JSON payload | 4.1 | ⬜ | P4 |  |  |
| 14 | pipe | [4.5](docs/STORY_DETAIL.md#story-4-5) | Per-execution PDF report (tiered: Executive / Security / Developer) | 4.1 | ⬜ | P4 |  |  |
| 14 | pipe | [4.6](docs/STORY_DETAIL.md#story-4-6) | ACCEPT → ZTIE pushes hash-verified artifact Forensic → Pipeline-Sandbox (PDE handoff) | 4.1 | ⬜ | P4 |  |  |
| 14 | pipe | [4.7](docs/STORY_DETAIL.md#story-4-7) | REJECT → destroy artifact + detonation chamber in Forensic; INCONCLUSIVE → hold at approval gate | 4.1 | ⬜ | P4 |  |  |
| 15 | pipe | [4.3](docs/STORY_DETAIL.md#story-4-3) | Real-time dashboard (dark theme, graduated severity/threat color coding) | 4.2 | ⬜ | P4 |  |  |
| 16 | pipe | [4.4](docs/STORY_DETAIL.md#story-4-4) | Interactive accept/reject control (Hub) gating the Forensic→Pipeline-Sandbox push | 4.3, 4.7 | ⬜ | P4 |  |  |
| 0 | gov | [G-1](docs/STORY_DETAIL.md#story-g-1) | Back-map design artifacts to candidate NIST family + ISO 27001 controls (RD-014) | — | ⬜ | - |  |  |
| 0 | gov | [G-4](docs/STORY_DETAIL.md#story-g-4) | Charter-level product view: author + maintain `docs/PRODUCT_PLAN.md` (PMP/Scrum-PO why/for-whom; no story detail or status) as a third intentional view (RD-036) | — | ✅ | - | 2026-09-12 |  |
| 6 | F&H | B.1 | Harvest inventory: survey the repo, catalog candidates + parameter surfaces + priority in `docs/governance/HARVEST_INVENTORY.md` | A.4 | ⬜ | - |  | (docs) |
| 7 | F&H | C.1 | Stand up the archive repo `infra-building-blocks` (CDK L3 lib; jest Template tests; SemVer 0.x; checkpoint tags) | B.1 | ⬜ | - |  | archive v0.1.0+ |
| 8 | F&H | C.2 | Build the parameterized constructs the inventory selected (SecureBucket, ContractIngestQueue, and the rest) | C.1 | ⬜ | - |  | archive tag per construct |
| 9 | F&H | C.4 | Migrate ONE ZTIE stack onto the archive as proof: constructs, drift-proven `cdk synth`, one "(no changes)" deploy | C.2 | ⬜ | - |  | `restore/migrate-<stack>-green` |
| 10 | F&H | C.5 | Record the practice: RD-022 into PROJECT_PLAN; METHODOLOGY note; update templates + CONVENTIONS; relocate remaining root governance docs | C.4 | ⬜ | - |  | (docs) |
| 6 | tenancy | [T.2](docs/STORY_DETAIL.md#story-t-2) | **Worry 2 — tenant provisioning/deprovisioning [DEFERRED: commercialization phase, after core pipeline]:** automate stand-up + teardown of an isolated per-SUBSCRIBER ZTIE environment per the T.1 model (per-subscriber account-vending), subscriber-tagged + cost-tracked, nuke-on-offboard | T.1 | ⬜ | - |  |  |
| 7 | tenancy | [T.3](docs/STORY_DETAIL.md#story-t-3) | **Worry 2 — Hub-side per-SUBSCRIBER data isolation + noisy-neighbor/quota controls [DEFERRED: commercialization phase, after core pipeline]:** per-subscriber partitioning of the Hub tracking/reporting/dashboard plane; per-subscriber limits so one subscriber's detonations cannot starve another (NO per-user partitioning — within-org is shared-trust, RD-028) | T.2 | ⬜ | - |  |  |

> **How to read this table — it is the TRUE SCHEDULE, top to bottom.** Rows are in
> the actual order we intend to execute them, in three contiguous sections:
> **(1) DONE history** — every ✅ story in the order it was built (build-tier order);
> **(2) the OPEN execution queue** — every not-yet-done story in the order we will
> work it (the next action is the first ⬜/🟡 row); **(3) DEFERRED** — rows explicitly
> parked (title-tagged `[DEFERRED]`), pulled to the bottom. So reading top-to-bottom
> IS the plan: what's built, then what's next, then what's parked.
>
> **Order = our chosen schedule, constrained by dependencies (not by tier number).**
> The one hard rule (from [`METHODOLOGY.md`](METHODOLOGY.md) §1a): **Build tier = 1 +
> the highest tier of anything a story depends on**, and a story ALWAYS appears after
> every story it depends on. Within that constraint we are free to order INDEPENDENT
> stories by priority — e.g. close the tier-0 gate (`G-3`) and do the tier-6 shared
> seam (`C.3`) before the tier-9 pipe story (`3.2`), because none of them depends on
> the others. **Consequence: the `Build tier` column is NOT monotonic down the table**
> — that is intentional. Build tier is retained as per-row dependency metadata (and to
> compute precedence), not as the sort key. The **Track** column (`pipe` / `gov` /
> `F&H` / `tenancy`) only labels the workstream; it does not affect order. The
> **Status** column is the source of truth for state. Phase labels (P1–P4) are on
> pipeline rows; `gov`/`F&H`/`tenancy` rows are not phase-bound and show `-`. This one
> table is the complete single source of truth for every story's status AND sequence.
>
> **Machine-enforced (`scripts/check_docs.py` CHECK C):** the schedule is kept honest
> automatically — **C1** every story appears after all of its `Depends on` entries
> (dependency precedence), and **C2** deferred rows stay at the bottom. The
> dependency-graph picture (with tiers) lives in
> [`docs/BUILD_ORDER.md`](docs/BUILD_ORDER.md).
>
> **Dependency note (cross-track):** F&H tiers are computed from the same graph —
> `A.2` depends on `2.0` (tier 3) → tier 4; `A.3` depends on `2.1` (tier 3) → tier 4;
> `A.4` depends on `A.1`+`A.2` → tier 5; `B.1` and `C.3` depend on `A.4` (tier 5) →
> tier 6; `C.1` on `B.1` → 7; `C.2` on `C.1` → 8; `C.4` on `C.2` → 9; `C.5` on `C.4`
> → 10. `A.2`'s dependency is the **validated** Story 2.0 (`A.2` is itself the act of
> validating it); `A.3`'s is Story 2.1.
>
> **Cross-track hard dependency (2026-09-07 decision):** Story **2.4 now depends on
> `2.3` + `A.5` + `A.6`** — the "clean the ground before building on it" rule is
> encoded structurally, not just advised: 2.4 cannot begin until the F&H plan drift is
> corrected (`A.5` ✅) AND the P2 floor / 2.3 restore tags are actually pushed (`A.6`
> ✅). Because `A.5`/`A.6` are tier 6, this lifts **2.4 from tier 5 to tier 7**, which
> cascades down the detonation→telemetry→Phase-3→Phase-4 chain: `2.5`→8, `3.2`→9,
> `3.3`→10, `3.4`→11, `3.5`→12, `4.1`→13, `4.2`/`4.5`/`4.6`/`4.7`→14, `4.3`→15,
> `4.4`→16. `2.6` (deps `2.1`+`2.3`) stays tier 5 and `3.1` (dep `2.6`) stays tier 6 —
> that branch does not pass through 2.4, so it is unaffected.
> The Floor & Harvest narrative, per-story detail, and the Story 2.0 live-validation
> runbook live in
> [`docs/governance/FLOOR_AND_HARVEST_PLAN.md`](docs/governance/FLOOR_AND_HARVEST_PLAN.md).

### Scheduling & readiness (every open story is scheduled)

> **Purpose.** The master table above already encodes the execution ORDER (its OPEN
> section is the queue, top-first). This section is the READINESS RATIONALE behind
> that order — WHY each open story sits where it does — so the schedule is auditable,
> not just asserted. **Readiness is derived:** a story is *Ready* iff every story in
> its `Depends on` is ✅; otherwise it is *Blocked* on the named unmet dependency; a
> story is *Deferred* only by an explicit recorded decision (with the reason). Note a
> story can be scheduled in the OPEN queue while still *Blocked* — it is placed after
> its dependency (precedence holds) and simply cannot START until that dependency
> closes. Re-derive this whenever a story flips ✅ (a newly-unblocked story moves up).
> The advancement gate still governs *pipe* feature starts (no new pipe feature story
> while the Validation Debt Register is non-empty).

> **Sequencing rule (binding — METHODOLOGY §5.A.0).** The next story to START is the
> **first OPEN item in bucket A, top-down.** A story being "Ready" (dependencies ✅)
> means it *may* be built — NOT that it is scheduled next. Working a *different* Ready
> story is a **re-prioritization of the roadmap, which is the stakeholder's decision**
> (RD-024: executor recommends, stakeholder decides). The executor must NOT self-select
> an out-of-order Ready story, and must NOT edit the "Default next action" / this
> schedule order to match its own choice and then work off that edit. Propose the
> reorder, get the explicit go, and record the approved change here + in
> [`docs/governance/WORK_LOG.md`](governance/WORK_LOG.md) before starting.

**A. Ready now (all dependencies ✅) — schedulable this session, in tier order:**

| Tier | Track | Story | Why it is next / what it unblocks |
|------|-------|-------|-----------------------------------|
| 0 | gov | ~~**G-3**~~ | ✅ **Closed 2026-09-12** — the advancement-gate checker itself (register + gate + decoupling, now extended with CHECK C) is validation-closed on its own `test_check_docs` pass; the gate machinery is no longer itself unvalidated. No longer schedulable. |
| 0 | gov | G-1 | Back-map artifacts to NIST/ISO (RD-014). Best run once the pipeline design has stabilized (Phase 3+), so scheduled but low-urgency. |
| 0 | gov | G-2 | Mgmt-artifact integrity (RD-015). **Substantially satisfied** by `check_docs.py` (CHECK A/B/C); remaining scope is the reusable-OS/instance split — reconcile/close rather than build from scratch. |
| 5 | tenancy | T.1 | Multi-tenancy design SPIKE (doc-only). Should land **before Phase 4** (it protects the Phase-4 dashboard/handoff design); unblocks T.2. |
| 6 | F&H | ~~C.3~~ | ✅ **Closed 2026-09-12 (RD-034)** — collapsed the 10 contract generators into one shared writer + the 8 Hub-gate kind trios into one data-driven registry, byte-identical/behaviour-preserving; `awsio` kept per-lane by design (bundling). No longer schedulable. |
| 6 | F&H | B.1 | Harvest inventory (docs). Unblocks the C.1→C.5 archive chain. |
| 9 | pipe | **3.2** | 🟡 **BUILT — awaiting live validation.** Nova Pro correlation (RD-035): code + contract + stack wiring complete, full offline bar green; on the Validation Debt Register pending a recorded live Bedrock pass. **Gate is ARMED** — the only permitted next action is validating 3.2 live (see its LIVE-RUNBOOK), not starting a new feature. |

**B. Blocked (waiting on an unmet dependency) — scheduled, will unblock automatically:**

| Tier | Track | Story | Blocked on | Unblocks when |
|------|-------|-------|-----------|---------------|
| 7 | F&H | C.1 | B.1 | B.1 ✅ (archive repo stand-up) |
| 8 | F&H | C.2 | C.1 | C.1 ✅ (parameterized constructs) |
| 9 | F&H | C.4 | C.2 | C.2 ✅ (migrate one stack as proof) |
| 10 | F&H | C.5 | C.4 | C.4 ✅ (record the practice) |
| 10 | pipe | 3.3 | 3.2 | 3.2 ✅ |
| 11 | pipe | 3.4 | 3.3 | 3.3 ✅ |
| 12 | pipe | 3.5 | 3.4 | 3.4 ✅ (closes Phase 3) |
| 13 | pipe | 4.1 | 3.5 | 3.5 ✅ |
| 14 | pipe | 4.2 / 4.5 / 4.6 / 4.7 | 4.1 | 4.1 ✅ |
| 15 | pipe | 4.3 | 4.2 | 4.2 ✅ |
| 16 | pipe | 4.4 | 4.3 + 4.7 | both ✅ (closes Phase 4) |

**C. Deferred (explicit recorded decision — will NOT be scheduled until the trigger):**

| Tier | Track | Story | Deferred until | Reason (recorded) |
|------|-------|-------|----------------|-------------------|
| 6 | tenancy | T.2 | Commercialization phase (after the core pipeline is complete) | Per-subscriber environment vending is only needed to sell multi-tenant; the core single-tenant pipeline must land first. Also structurally blocked on T.1. |
| 7 | tenancy | T.3 | Commercialization phase (after the core pipeline is complete) | Hub-side per-subscriber data isolation / quotas — same commercialization trigger; blocked on T.2. |

> **Default next action:** **Story 3.2 (Nova Pro correlation, RD-035) is BUILT and on
> the Validation Debt Register**, so the advancement gate is **ARMED**: the only
> permitted next action is its recorded **live validation** (a real Bedrock/Nova Pro
> run per [`docs/session-briefs/story-3.2-LIVE-RUNBOOK.md`](docs/session-briefs/story-3.2-LIVE-RUNBOOK.md)),
> NOT starting a new feature story. G-1/G-2/B.1 and the C-archive/tenancy tracks remain
> parked (governance stories are gate-exempt but low-urgency; strategy-contingent tracks
> await their trigger). When 3.2 clears its live pass, flip it ✅, clear the register,
> and re-derive the buckets — 3.3 (accuracy + gap_analysis) then moves to Ready.

### Relevance & scope review (2026-09-12)

> **Why this exists.** The `gov` / `F&H` / `tenancy` tracks were authored early; a lot
> has shipped since, so some rows are now mis-**scoped** or mis-**prioritized** against
> what already exists on `main` (they are NOT wrong — the intent stands — but a fresh
> session must not re-build work that is already done). This subsection re-scopes those
> rows against current reality. **Recommendations marked _(pending confirmation)_ are
> the executor's proposal; the keep / defer / drop calls that hinge on business
> strategy — commercialization, platform-maturity — are the stakeholder's.** None of
> these stories is dropped here; this only records scope + priority.

| Story | Current reality on `main` | Re-scoped as | Recommendation |
|-------|---------------------------|--------------|----------------|
| **G-1** — compliance back-map | `docs/COMPLIANCE.md` already EXISTS (framework scope, candidate-vs-ratified convention, 16 seeded mappings); every RD through RD-033 already proposes mappings at authoring time. | **Finish + ratify**, not build from scratch: complete the matrix for the remaining artifacts and get an accountable reviewer to flip `Proposed`→`Ratified`. | **Keep, deferred** — best once the Phase-3 design stabilizes (its own note says so). Low urgency. _(pending confirmation)_ |
| **G-2** — mgmt-artifact integrity | `scripts/check_docs.py` already EXISTS with CHECK A/B/C (register completeness, advancement gate, build-order) + Operational-Debt surfacing, all unittest-covered. | **Remaining scope only:** the four *additional* checks G-2 named (plan↔runbook story-set divergence, dangling `RD-0NN` refs, stray `{{placeholders}}`, a ✅ story missing a dated Validation Result) + the reusable-OS/instance-layer boundary doc. Do NOT rebuild the checker. | **Keep; consider pulling the cheap half forward** with C.3 — the extra checks are high-value guardrails and relatively cheap. _(pending confirmation)_ |
| **C.3** — shared generator + Hub-gate seam | ✅ **Closed 2026-09-12 (RD-034).** Collapsed the 10 contract generators into one shared writer (`scripts/contract_writer.py` + `scripts/gen_contracts.py`) and the 8 Hub-gate kind trios into one data-driven `_KindSpec` registry — byte-identical / behaviour-preserving, proven offline. Per the stakeholder decision the 6 `awsio.py` copies were KEPT per-lane (bundling: a shared module outside each lambda dir would `ModuleNotFoundError`; genuinely-shared surface is ~15 lines). | Done. | — |
| **B.1 → C.1 → C.2 → C.4 → C.5** — harvest into a versioned `infra-building-blocks` archive | Not started; `infra-building-blocks` referenced only in governance docs, not built. | Unchanged scope. This is a **platform-maturity investment** (a reusable construct library), NOT a pipeline requirement. | **Keep but defer — revisit after Phase 3 closes.** Worth it if ZTIE becomes a long-lived platform with many stacks; over-investment if the goal is to finish this one pipeline. **This is the track most worth an explicit keep / defer / drop call.** _(stakeholder decision)_ |
| **T.1** — multi-tenancy design spike (doc-only) | `docs/architecture/MULTI_TENANCY.md` not yet written. | Unchanged scope; cheap (no code). | **Keep — do before Phase 4**, so the 4.x dashboard/handoff design is built against a written tenant model. _(pending confirmation)_ |
| **T.2 / T.3** — per-subscriber provisioning + Hub data isolation | Not started; already in the Deferred bucket. | Unchanged scope. Relevance is **100% contingent on the commercialization decision** — if ZTIE stays single-tenant/internal these may never be needed. | **Keep deferred to commercialization** (as already recorded). Revisit only when/if multi-tenant is committed. **Explicit keep / defer / drop is the stakeholder's call.** _(stakeholder decision)_ |

> **Net:** nothing is dropped; intent stands across all three tracks. The corrections
> are (1) G-1/G-2 are *smaller than their rows imply* (finish/complete, not build), and
> (2) the C-archive chain + T.2/T.3 are strategy-contingent bets that should be an
> explicit stakeholder keep/defer/drop rather than implied commitments. Recommended
> priority now that G-3 and C.3 are closed: **back to the pipe track (3.2)** (the cheap
> half of G-2 can ride a later PR), with the archive chain and tenancy provisioning
> parked until Phase 3 closes / commercialization is decided.

### Phase gates (retained)

The per-phase close gates from the previous phase layout, kept verbatim so no
gate text is lost. Phases still close only when their end-of-phase gate returns
a recorded, confirmed pass.

- **P1:** _Gate: feed an IaC template, a raw script, and an unknown/unroutable artifact through the intake gateway; confirm each known type is classified and routed to the correct downstream lane, and the unknown type is safe-rejected (not crashed)._
- **P2:** _Gate: a known-bad artifact produces (a) static findings from the scanning stack AND (b) observed runtime behavior from a real detonation, with both lanes running in parallel and each emitting structured output; the ephemeral EC2 is confirmed torn down via hard TTL._
- **P3:** _Gate: given paired static + dynamic outputs, Nova Pro returns a single unified threat score, correlated findings (static ↔ dynamic evidence), and prioritized remediations; a case where static flags a risk but dynamic proves benign (or vice-versa) is correctly reconciled (false-positive elimination demonstrated)._
- **P4:** _Gate: for a full run, confirm the dashboard JSON and PDF report are produced with tiered content (Executive / Security / Developer); on human ACCEPT, ZTIE pushes the hash-verified artifact from Forensic to Pipeline-Sandbox (586917955591) and no un-accepted artifact ever leaves Forensic; on REJECT, the artifact + detonation chamber are destroyed in Forensic; an INCONCLUSIVE artifact holds until a human accepts/rejects it from the dashboard._


### Detail index (started stories)

> A quick book-index of the stories that have been started (any status other
> than Not Started), sorted by story ID. Each entry is a short plain-language
> summary of the work; follow the link for the full archived detail in
> [`docs/STORY_DETAIL.md`](docs/STORY_DETAIL.md).

**1.1** (Done) - Stood up the ZTIE intake gateway (API Gateway POST /intake with SigV4 auth to a Python 3.12 Lambda) that stores the raw artifact in encrypted S3 and an intake record in DynamoDB. Validated live on Forensic: a signed request returned 201 and persisted the record, and an unsigned request was rejected 403. A known account-placement deviation was queued forward as 1.1R rather than retro-edited. Full detail: [1.1 in STORY_DETAIL.md](docs/STORY_DETAIL.md#story-1-1).

**1.1R** (Done) - Moved the durable tracking record out of Forensic into the Hub behind the RD-013 data-contract boundary: a Hub-owned cross-account SQS ingest queue and validator Lambda that enforces a strict allow-list schema, upserts passing records into the Hub table, and quarantines anything non-conforming fail-closed. Validated live across both accounts, including a malformed verdict-injection envelope being rejected to quarantine. Full detail: [1.1R in STORY_DETAIL.md](docs/STORY_DETAIL.md#story-1-1r).

**1.R** (Done) - Built the Python restore-point mechanism (a capture / verify / restore CLI) that snapshots a read-only projection of the durable Hub state and infra, re-applies it behind a confirm gate that fails safe to NO, and pins the governance-doc commit so code, state, and governance restore as one unit. Validated live on the Hub: capture wrote a manifest, a deliberate drift was detected, and a restore returned the stack to match. Full detail: [1.R in STORY_DETAIL.md](docs/STORY_DETAIL.md#story-1-r).

**1.2** (Done) - Built the preprocessor classifier that inspects each artifact's extension, metadata, and actual content to label it (IaC template, raw script, or other/unknown), with content winning when it disagrees with the claimed type. It emits only a label, never a verdict or route. Validated live end-to-end, including the distrust-the-claim case where bash bytes uploaded as a .yaml file were still classified as a raw script. Full detail: [1.2 in STORY_DETAIL.md](docs/STORY_DETAIL.md#story-1-2).

**1.3** (Done) - Built the routing table that turns each classification into a lane plan: IaC and raw scripts fork into both the static and dynamic Phase-2 lanes, while unknown or unroutable artifacts fall through to safe-reject. The decision is a plan of controls only, never a verdict or forward-to-PDE decision. Validated live for all three cases with each type routed to the correct lane. Full detail: [1.3 in STORY_DETAIL.md](docs/STORY_DETAIL.md#story-1-3).

**1.4** (Done) - Built the safe-reject path so an unroutable or incompatible artifact is rejected cleanly (marked SAFE_REJECTED) instead of crashing a scanner, while routable artifacts pass through untouched. Validated live: an unknown text file was safely rejected and a routable IaC template was left alone, with the pipeline never crashing. Full detail: [1.4 in STORY_DETAIL.md](docs/STORY_DETAIL.md#story-1-4).

**2.0** (Done) - Built the isolated-VPC containment foundation as a CDK v2 stack: an isolated VPC with no internet path (no IGW or NAT), VPC endpoints as the only egress, least-privilege IAM, and a detonation launch template with a five-minute hard TTL. Validated live in Forensic (Story A.2, 2026-09-02): all seven Definition-of-Done checks passed after fixing a pre-validation defect (an SG rule description carried a `>` outside AWS's allowed charset, which failed the first deploy; corrected and re-deployed clean). Its Validation Debt Register entry was then cleared. Full detail: [2.0 in STORY_DETAIL.md](docs/STORY_DETAIL.md#story-2-0).

**2.1** (Done) - Built the non-executing static scanning stack that runs cfn-lint, cfn-guard, checkov, and bandit as a container-image Lambda, normalizes their output into one finding shape kept in Forensic, and crosses only a bounded summary to the Hub. Validated live end-to-end on known-bad IaC and script artifacts, and proven to keep running when one scanner errors. Full detail: [2.1 in STORY_DETAIL.md](docs/STORY_DETAIL.md#story-2-1).

**2.2** (Done) - Extends the static lane additively (RD-025): each finding is mapped to the NIST 800-53 / ISO 27001 control(s) it implicates (candidate-vs-ratified, unmapped when no honest match — evidence, never a verdict), and a pure-Python signature engine runs a real embedded ruleset for known-bad patterns / secrets / IoCs non-executing (regex over bytes, secrets redacted). Both enrich the same Forensic findings document + the same derived Hub summary (contracts bumped to v1.1); the summary gains a bounded compliance roll-up. Validated live 2026-09-03 on a known-bad IaC template + a script with a planted secret: findings mapped to the correct controls in the Forensic doc + the crossed Hub roll-up, signatures detected (secrets redacted), non-executing, no scanner crash. Full detail: [2.2 in STORY_DETAIL.md](docs/STORY_DETAIL.md#story-2-2).

**2.3** (Done) - Built the dynamic (detonation) lane — the first place ZTIE actually EXECUTES an artifact. A plain-zip Lambda orchestrator launches ONE ephemeral EC2 from the Story 2.0 launch template via `ec2:RunInstances`, delivers the artifact to the isolated host over a presigned S3 URL, executes it host-native via SSM `AWS-RunShellScript` (no Docker/container), and lets the 5-minute hard TTL tear the host down. Only a bounded, derived, verdict-free run-outcome record crosses to the Hub (a new RD-013 envelope kind, its own version pin) — the full command log stays in Forensic. Validated live 2026-09-05: a routed script launched instance `i-00b8af8d57fd43571` from the launch template, ran host-native (`ZTIE-DETONATION-OK`, exit code 0), was confirmed terminated within the TTL, and its outcome (`lane: dynamic_detonation`, `outcome: completed`, correct containment flags, no verdict field) landed in the Hub tracking record. The first live run(s) surfaced and fixed seven real defects in the launch/artifact-fetch path (instance-profile ARN, unbounded fetch, an S3 endpoint conflict, global-vs-regional S3 addressing, security-group egress, and SigV2-vs-SigV4 signing) — see Lessons Learned in `docs/session-briefs/story-2.4-brief.md` for the full chain. Full detail: [2.3 in STORY_DETAIL.md](docs/STORY_DETAIL.md#story-2-3).

**2.0E** (Done) - Cost remediation on the validated Story 2.0 infra: the interface VPC endpoints in the Forensic detonation VPC were billing ~$0.01/hr each per AZ, 24/7 — roughly `$88/mo` sitting idle — even though they are only used during the few minutes of an actual detonation. The **final design is two-tier (RD-027)**, after a 3-attempt live investigation proved the SSM control channel cannot be created reliably per-run: the SSM control channel (`ssm`/`ssmmessages`/`ec2messages`) stays **always-on in a single AZ** (~$22/mo, warm + reliable), while the non-boot-critical tier (`logs`/`sqs`/`bedrock-runtime`) is **ephemeral per run** — the orchestrator sweeps orphans, creates them just-in-time, waits for `available`, runs the detonation, and tears them down in a `finally` (~$66/mo recovered). No containment invariant changes (still no IGW/NAT/`0.0.0.0/0`, host-native SSM, no SSH, 5-minute hard TTL). Validated live in Forensic 360999005254 on 2026-09-08 — all 5/5 DoD passed on the fixed code (a conflicting-DNS-domain race on sweep-then-recreate was found live and fixed with a bounded create-retry, then re-validated). Its Validation Debt Register entry was then cleared. Tag `restore/story-2.0E-green`. Full detail: [2.0E in STORY_DETAIL.md](docs/STORY_DETAIL.md#story-2-0e).

**G-3** (Done, validated 2026-09-12) - Turning the hard pause into a structural, machine-checkable mechanism: the Validation Debt Register, the no-new-feature-work-while-debt-open advancement gate, and the story-closure / restore-point decoupling, wired into `scripts/check_docs.py`. The checker is implemented and unit-tested here; validation-closed offline on the recorded pass — `check_docs.py` PASSES clean (exit 0) and `test_check_docs` reports SUITE `OK`, the suite proving CHECK A/B/C each fire on injected defects. Full detail: [G-3 in STORY_DETAIL.md](docs/STORY_DETAIL.md#story-g-3).

**A.1** (Done) - Re-applied the capture-tooling Phase-2 target extension (the `targets.py` change) onto latest `main` through the A.4 PR. The stale `feature/restore-targets-phase2` branch was intentionally not merged because it predates the docs consolidation, the single-pane RUNBOOK, and the G-3 gate, so merging it would have reverted that governance state; only its substance was carried forward. Full detail: [Floor & Harvest Plan](docs/governance/FLOOR_AND_HARVEST_PLAN.md).

**A.2** (Done) - Validated Story 2.0 live in the Forensic account: all 7 Definition-of-Done checks passed on 2026-09-02, so 2.0 was recorded and flipped ✅ and its Validation Debt Register entry was cleared. Tag `restore/story-2.0-green`. Full detail: [Floor & Harvest Plan](docs/governance/FLOOR_AND_HARVEST_PLAN.md).

**A.3** (Done) - Confirmed Story 2.1 is already ✅ on `main` (validated 2026-09-01) with its dated live Validation Result recorded, so no re-run was performed; it was folded into the Phase-2 floor as a capture target. Full detail: [Floor & Harvest Plan](docs/governance/FLOOR_AND_HARVEST_PLAN.md).

**A.4** (Done) - Instituted deployed-state restore points: captured and verify-clean manifests for both the Hub and Forensic accounts (each VERIFY: MATCH, empty changed/missing/unexpected) and filled BOM's 11 pending rows. Tag `restore/phase-2-floor-green` was placed on the merged A.4 status commit. Full detail: [Floor & Harvest Plan](docs/governance/FLOOR_AND_HARVEST_PLAN.md).

**A.6** (Done) - Pushed the two outstanding annotated restore tags that the docs referenced but that were not on `origin` (the phantom-baseline gap): `restore/phase-2-floor-green` on the merged A.4 status commit `642fc7f` (carries both floor manifests) and `restore/story-2.3-green` on the `origin/main` tip `314d9f5` (at/after the PR #60 2.3-✅ merge). Owner-pushed and independently verified on `origin` 2026-09-08 — `git ls-remote --tags origin` lists all six restore tags, both new tags are annotated (`git cat-file -t` = `tag`) and point at post-validation commits. No pipeline/infra/lambda code touched; no other story's status changed. With A.5 ✅, this closes the tier-6 Floor & Harvest pair and unblocks Story 2.4. Full detail: [A.6 in STORY_DETAIL.md](docs/STORY_DETAIL.md#story-a-6).

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
- **Same facts, different views (do not force-match the ordering).** The plan is
  organized by **phase** (the what/why, the overall reference); this runbook is
  organized by **build order** (dependency tiers, the daily do-it view). The two
  must always agree on the **facts** (the same story set, statuses, dependencies,
  and decisions) but they deliberately **order** those stories differently.
  Neither is reordered to match the other. Story status lives here in the runbook
  as the single source of truth.
- **Per-story brief + prompt:** filled from the templates into `session-briefs/`.
- **Next-session brief AND prompt are authored during the current session** — the
  final task each session, including Lessons Learned / Carry-Forward, so the next
  session starts with zero cold-start.
