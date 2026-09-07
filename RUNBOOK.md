# ZTIE Security Analysis Pipeline — Execution Runbook

> **Living progress ledger.** This runbook mirrors [`PROJECT_PLAN.md`](PROJECT_PLAN.md)
> but is execution-oriented: every story is a trackable item with dependencies,
> do-it steps, a validation check, and a completion marker. The plan is the
> *what/why*; this runbook is the *do-it-and-track-it*. **This file is the source
> of truth for story status** — and it carries the binding Validation &
> Advancement Gate below.
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
| [2.0E](docs/STORY_DETAIL.md#story-2-0e) | Cost-remediation of the validated 2.0 infra: the six always-on interface VPC endpoints are made ephemeral (created per detonation, torn down after) to eliminate ~$88/mo idle burn. **First live run (2026-09-07) proved the endpoint lifecycle end-to-end (created→available→torn down, gateway-only when idle, containment intact) but surfaced an SSM-online race** — the host launched before the just-created endpoints' private DNS had propagated, so the SSM agent never reported Online (`outcome=delivery_error`, `ssm_status=not_run`; the artifact never executed). Fixed (pre-launch DNS-settle delay + UserData ssm-agent restart + longer SSM-online budget); re-validation pending. | Stakeholder re-runs one live detonation in Forensic 360999005254 (after redeploying both stacks on the fixed code) and confirms all 5 DoD checks INCLUDING a host-native run that reaches `ssm_status=Success` / `ZTIE-DETONATION-OK` and `outcome=completed`. | Stakeholder |

> **Register status: 1 OPEN (2.0E).** Story 2.0E is the follow-forward
> cost-remediation on the validated Story 2.0 infra — it moves the six interface
> VPC endpoints from always-on to ephemeral (per-detonation create/teardown) to
> stop the ~$88/mo idle interface-endpoint burn, with no change to any containment
> invariant (no IGW/NAT/0.0.0.0/0; host-native SSM; no SSH; 5-min hard TTL). It is
> built and offline-validated but stays `🟡` until the stakeholder records a live
> detonation pass in Forensic (the covenant). Because 2.0E is itself the open
> register entry, reworking/validating it is the permitted in-progress work; the
> advancement gate blocks only NEW unrelated feature stories until 2.0E clears.
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
| 0 | gov | [G-1](docs/STORY_DETAIL.md#story-g-1) | Back-map design artifacts to candidate NIST family + ISO 27001 controls (RD-014) | — | ⬜ | - |  |  |
| 0 | gov | [G-2](docs/STORY_DETAIL.md#story-g-2) | Management-artifact integrity: automated consistency check + reusable-OS/instance separation (RD-015) | — | ⬜ | - |  |  |
| 0 | gov | [G-3](docs/STORY_DETAIL.md#story-g-3) | Hard-pause enforcement: Validation Debt register + advancement gate (no new feature story while debt open) + story-closure/restore-point decoupling; wire into `check_docs.py` (RD-023) | — | 🟡 | - |  |  |
| 1 | pipe | [1.1R](docs/STORY_DETAIL.md#story-1-1r) | Remediation: move durable tracking record Forensic → Hub behind the data-contract gate (RD-012/013/016) | 1.1 | ✅ | P1 | 2026-08-25 |  |
| 1 | pipe | [1.2](docs/STORY_DETAIL.md#story-1-2) | Preprocessor classifier (extension + metadata inspection) | 1.1 | ✅ | P1 | 2026-08-25 |  |
| 2 | pipe | [1.R](docs/STORY_DETAIL.md#story-1-r) | Restore-point mechanism: state-capture + coordinated restore; fill RESTORE.md + BOM.md (prerequisite for the P1 close) | 1.1R | ✅ | P1 | 2026-08-25 |  |
| 2 | pipe | [1.3](docs/STORY_DETAIL.md#story-1-3) | Routing table → static & dynamic lanes | 1.2 | ✅ | P1 | 2026-08-27 |  |
| 2 | pipe | [1.4](docs/STORY_DETAIL.md#story-1-4) | Safe-reject path for unknown/incompatible types | 1.2 | ✅ | P1 | 2026-08-27 |  |
| 3 | pipe | [2.0](docs/STORY_DETAIL.md#story-2-0) | AWS infra foundation (CDK v2: VPC/isolated subnets, IAM, launch template, SSM, Nova Pro access) | 1.3 | ✅ | P2 | 2026-09-02 | `restore/story-2.0-green` |
| 3 | pipe | [2.1](docs/STORY_DETAIL.md#story-2-1) | Static scanning stack (cfn-lint, cfn-guard, checkov, bandit) | 1.3 | ✅ | P2 | 2026-09-01 |  |
| 4 | pipe | [2.2](docs/STORY_DETAIL.md#story-2-2) | Compliance-framework mapping (NIST SP 800-53 / ISO 27001) + signature scans | 2.1 | ✅ | P2 | 2026-09-03 |  |
| 4 | pipe | [2.3](docs/STORY_DETAIL.md#story-2-3) | Detonation chamber — ephemeral EC2 + host-native SSM execution | 2.0 | ✅ | P2 | 2026-09-05 | `restore/story-2.3-green` |
| 5 | pipe | [2.0E](docs/STORY_DETAIL.md#story-2-0e) | Cost remediation — ephemeral interface VPC endpoints (per-detonation create/teardown) to end ~$88/mo idle burn (RD-027) | 2.3 | 🟡 | P2 |  |  |
| 4 | F&H | A.2 | Validate Story 2.0 live (7 DoD checks) → record + flip ✅ | 2.0 | ✅ | - |  | `restore/story-2.0-green` |
| 4 | F&H | A.3 | Confirm Story 2.1 ✅ on `main` (no re-run); fold into the floor | 2.1 | ✅ | - |  | (folds into floor) |
| 5 | pipe | [2.6](docs/STORY_DETAIL.md#story-2-6) | Parallel orchestration / fork of the two lanes | 2.1, 2.3 | ⬜ | P2 |  |  |
| 5 | F&H | A.4 | Institute deployed-state restore points: capture + verify both accounts, commit manifests, fill BOM's 11 pending rows | A.1, A.2 | ✅ | - |  | `restore/phase-2-floor-green` |
| 6 | pipe | [3.1](docs/STORY_DETAIL.md#story-3-1) | Telemetry aggregation / normalization (shared schema) | 2.6 | ⬜ | P3 |  |  |
| 6 | F&H | [A.5](docs/STORY_DETAIL.md#story-a-5) | Correct the Floor & Harvest plan drift: exit target 2.2 → next tier-5 story (2.4/2.6); rewrite the full-stop history (2.2/2.3 shipped old-way after the audit) | A.4 | ⬜ | - |  | (docs) |
| 6 | F&H | [A.6](docs/STORY_DETAIL.md#story-a-6) | Push the outstanding deployed-state restore tags `restore/phase-2-floor-green` + `restore/story-2.3-green` (owner action) | A.4, 2.3 | ⬜ | - |  | (tags) |
| 6 | F&H | B.1 | Harvest inventory: survey the repo, catalog candidates + parameter surfaces + priority in `docs/governance/HARVEST_INVENTORY.md` | A.4 | ⬜ | - |  | (docs) |
| 6 | F&H | C.3 | Shared Python seam + one generator: extract duplicated `awsio` + hub-gate pattern, collapse the 5 bespoke generators into one | A.4 | ⬜ | - |  | `restore/shared-seam-green` |
| 7 | pipe | [2.4](docs/STORY_DETAIL.md#story-2-4) | Behavioral telemetry capture (syscalls / network / filesystem) | 2.3, A.5, A.6 | ⬜ | P2 |  |  |
| 7 | F&H | C.1 | Stand up the archive repo `infra-building-blocks` (CDK L3 lib; jest Template tests; SemVer 0.x; checkpoint tags) | B.1 | ⬜ | - |  | archive v0.1.0+ |
| 8 | pipe | [2.5](docs/STORY_DETAIL.md#story-2-5) | Telemetry sanitization pipeline (entropy scrub → noise suppress → ≤25K truncation) | 2.4 | ⬜ | P2 |  |  |
| 8 | F&H | C.2 | Build the parameterized constructs the inventory selected (SecureBucket, ContractIngestQueue, and the rest) | C.1 | ⬜ | - |  | archive tag per construct |
| 9 | pipe | [3.2](docs/STORY_DETAIL.md#story-3-2) | Nova Pro correlation engine (exponential-backoff retry) | 3.1, 2.5 | ⬜ | P3 |  |  |
| 9 | F&H | C.4 | Migrate ONE ZTIE stack onto the archive as proof: constructs, drift-proven `cdk synth`, one "(no changes)" deploy | C.2 | ⬜ | - |  | `restore/migrate-<stack>-green` |
| 10 | pipe | [3.3](docs/STORY_DETAIL.md#story-3-3) | accuracy + gap_analysis synthesis | 3.2 | ⬜ | P3 |  |  |
| 10 | F&H | C.5 | Record the practice: RD-022 into PROJECT_PLAN; METHODOLOGY note; update templates + CONVENTIONS; relocate remaining root governance docs | C.4 | ⬜ | - |  | (docs) |
| 11 | pipe | [3.4](docs/STORY_DETAIL.md#story-3-4) | Unified threat scoring + prioritized remediations | 3.3 | ⬜ | P3 |  |  |
| 12 | pipe | [3.5](docs/STORY_DETAIL.md#story-3-5) | Verdict derivation (PASS / FAIL / INCONCLUSIVE) | 3.4 | ⬜ | P3 |  |  |
| 13 | pipe | [4.1](docs/STORY_DETAIL.md#story-4-1) | Status-retrieval orchestrator | 3.5 | ⬜ | P4 |  |  |
| 14 | pipe | [4.2](docs/STORY_DETAIL.md#story-4-2) | Dashboard JSON payload | 4.1 | ⬜ | P4 |  |  |
| 14 | pipe | [4.5](docs/STORY_DETAIL.md#story-4-5) | Per-execution PDF report (tiered: Executive / Security / Developer) | 4.1 | ⬜ | P4 |  |  |
| 14 | pipe | [4.6](docs/STORY_DETAIL.md#story-4-6) | ACCEPT → ZTIE pushes hash-verified artifact Forensic → Pipeline-Sandbox (PDE handoff) | 4.1 | ⬜ | P4 |  |  |
| 14 | pipe | [4.7](docs/STORY_DETAIL.md#story-4-7) | REJECT → destroy artifact + detonation chamber in Forensic; INCONCLUSIVE → hold at approval gate | 4.1 | ⬜ | P4 |  |  |
| 15 | pipe | [4.3](docs/STORY_DETAIL.md#story-4-3) | Real-time dashboard (dark theme, graduated severity/threat color coding) | 4.2 | ⬜ | P4 |  |  |
| 16 | pipe | [4.4](docs/STORY_DETAIL.md#story-4-4) | Interactive accept/reject control (Hub) gating the Forensic→Pipeline-Sandbox push | 4.3, 4.7 | ⬜ | P4 |  |  |

> **How to read this table.** Rows are in Foundation-First **build-tier
> (dependency-topological) order**, exactly as defined in
> [`METHODOLOGY.md`](METHODOLOGY.md) §1a (Dependency-Driven Sequencing): a story's
> **Build tier = 1 + the highest tier of anything it depends on**, so a story
> always appears strictly after every story it depends on, regardless of
> story-number, track, or business priority. **Every** story — numbered pipeline,
> governance (`G`), and Floor & Harvest (`A`/`B`/`C`) — is interleaved into this one
> tier order; the **Track** column (`pipe` / `gov` / `F&H`) only labels which stream a
> row belongs to, it does **not** change the ordering. Stories that share a tier are
> independent and tied, so their order within a tier is not meaningful. The Status
> column here in RUNBOOK is the source of truth. The Phase labels (P1–P4) are
> retained on pipeline rows; `gov` and `F&H` rows are not phase-bound and show `-`.
> The dependency-graph picture lives in [`docs/BUILD_ORDER.md`](docs/BUILD_ORDER.md),
> which uses the same tiers. This one table is the complete single source of truth
> for every story's status.
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

**2.0E** (In Progress) - Cost remediation on the validated Story 2.0 infra: the six interface VPC endpoints (SSM, SSM Messages, EC2 Messages, CloudWatch Logs, SQS, Bedrock Runtime) were billing ~$0.01/hr each per AZ, 24/7 — roughly `$88/mo` sitting idle — even though they are only used during the few minutes of an actual detonation. This story moves them from always-on to **ephemeral**: the detonation orchestrator now sweeps any orphans, creates the six interface endpoints just-in-time before launching the host, waits for them to be `available`, runs the detonation through them, and tears them down in a `finally` after — so idle interface-endpoint cost drops to ~zero. The always-on FREE scaffolding (the isolated VPC, its subnets, the S3 gateway endpoint, the endpoint security group, the IAM roles, and the launch template) is unchanged, and **no containment invariant changes** (still no IGW/NAT/`0.0.0.0/0`, still host-native SSM, still no SSH, still the 5-minute hard TTL). A start-of-run orphan sweep is the resilience backstop so a crashed run cannot leave endpoints billing. Built and offline-validated (39 Python tests pass; ruff/prettier clean; tsc at the known baseline); `🟡` pending the stakeholder's live detonation validation (RD-027). Full detail: [2.0E in STORY_DETAIL.md](docs/STORY_DETAIL.md#story-2-0e).

**G-3** (In Progress) - Turning the hard pause into a structural, machine-checkable mechanism: the Validation Debt Register, the no-new-feature-work-while-debt-open advancement gate, and the story-closure / restore-point decoupling, wired into `scripts/check_docs.py`. The checker is implemented and unit-tested here; it awaits the live confirmation that it passes clean and fails on the injected defects. Full detail: [G-3 in STORY_DETAIL.md](docs/STORY_DETAIL.md#story-g-3).

**A.1** (Done) - Re-applied the capture-tooling Phase-2 target extension (the `targets.py` change) onto latest `main` through the A.4 PR. The stale `feature/restore-targets-phase2` branch was intentionally not merged because it predates the docs consolidation, the single-pane RUNBOOK, and the G-3 gate, so merging it would have reverted that governance state; only its substance was carried forward. Full detail: [Floor & Harvest Plan](docs/governance/FLOOR_AND_HARVEST_PLAN.md).

**A.2** (Done) - Validated Story 2.0 live in the Forensic account: all 7 Definition-of-Done checks passed on 2026-09-02, so 2.0 was recorded and flipped ✅ and its Validation Debt Register entry was cleared. Tag `restore/story-2.0-green`. Full detail: [Floor & Harvest Plan](docs/governance/FLOOR_AND_HARVEST_PLAN.md).

**A.3** (Done) - Confirmed Story 2.1 is already ✅ on `main` (validated 2026-09-01) with its dated live Validation Result recorded, so no re-run was performed; it was folded into the Phase-2 floor as a capture target. Full detail: [Floor & Harvest Plan](docs/governance/FLOOR_AND_HARVEST_PLAN.md).

**A.4** (Done) - Instituted deployed-state restore points: captured and verify-clean manifests for both the Hub and Forensic accounts (each VERIFY: MATCH, empty changed/missing/unexpected) and filled BOM's 11 pending rows. Tag `restore/phase-2-floor-green` was placed on the merged A.4 status commit. Full detail: [Floor & Harvest Plan](docs/governance/FLOOR_AND_HARVEST_PLAN.md).

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
