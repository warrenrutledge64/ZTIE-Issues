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

## Master story table (single source of truth for status + sequence)

> **Single pane of glass.** Every story lives in this one table, in dependency
> (build) order — the daily source of truth for **status** AND **sequence**. Read it
> top-to-bottom: **(1)** DONE history (✅, build-tier order), **(2)** the OPEN execution
> queue (the next action is the first ⬜/🟡 row), **(3)** DEFERRED rows (parked, at the
> bottom). The `Build tier` column is per-row dependency metadata (a story always
> appears after everything it depends on) and is deliberately NOT monotonic; the
> `Status` column is the source of truth for state. Full per-story records (Steps / As
> built / dated Validation Result) are in [`docs/STORY_DETAIL.md`](docs/STORY_DETAIL.md);
> the scheduling / readiness / phase-gate detail + how-to-read notes are in the
> [Build order](#build-order-dependency-driven) section below. Machine-enforced by
> [`scripts/check_docs.py`](scripts/check_docs.py) (CHECK A status + CHECK C schedule order).

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
| 4 | pipe | [2.2G](docs/STORY_DETAIL.md#story-2-2g) | Gitleaks integration (static lane): embed the compiled `gitleaks` binary in the static-scan container alongside cfn-lint/cfn-guard/checkov/bandit; subprocess seam + normalize into `static-findings.contract.v1` (v1.2); supersedes the 2.2 embedded regex SECRET rules (gitleaks = sole secret scanner; DANGEROUS/MALWARE signature families retained); deterministic, non-executing, fail-open on tool error | 2.1, 2.2 | ✅ | P2 | 2026-09-15 | `restore/story-2.2-green` |
| 4 | pipe | [2.2R](docs/STORY_DETAIL.md#story-2-2r) `[sec-boundary]` | Remediation of 2.2G (RD-053): supply the live positive-detection + raw-JSON redaction proof 2.2G's `count: 0` run never gave. Submit a genuinely gitleaks-detectable non-allowlisted secret → `gitleaks count ≥ 1` normalized into `static-findings.contract.v1` v1.2, and a human reads the RAW JSON to confirm the value is redacted while the finding persists. No new code unless the live run surfaces a defect. **Evidence (RD-054): [`docs/validation-evidence/2.2R/`](docs/validation-evidence/2.2R/EVIDENCE.md).** | 2.2G | ✅ | P2 | 2026-09-15 | `restore/story-2.2-green` |
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
| 7 | pipe | [2.4R](docs/STORY_DETAIL.md#story-2-4r) `[sec-boundary]` | Remediation of 2.4 (RD-054): backfill the DYNAMIC lane (strace) to the auditable evidence bar. 2.4 was validated 2026-09-10 under the pre-RD-053/054 regime (no retained raw evidence; Forensic is ephemeral so the original trace aged out). Re-validate live via split-brain: detonate a KNOWN-BEHAVIOR artifact, positively exercise the strace capture (real syscall / filesystem / network-attempt counts), and RETAIN the raw evidence (bounded `behavior.contract.v1` summary + a trace slice + the Hub crossing). Six live attempts FAILED (in-wrapper strace→SSM-stdout transport hangs to the 120 s ceiling); cleared via its remediation Story 2.4S (VALIDATED LIVE 2026-09-24 via 2.4S — see attempt-5 evidence) | 2.4 | ✅ | P2 | 2026-09-24 | `restore/story-2.3-green` |
| 8 | pipe | [2.4S](docs/STORY_DETAIL.md#story-2-4s) `[sec-boundary]` | **Fix B / RD-058 — the active remediation of 2.4R (in progress).** Abandon SSM stdout as the trace transport: the ephemeral host uploads the `strace -o` per-PID files DIRECTLY to Forensic S3 (`traces/{intake_id}/`) before exit; the Lambda reads the trace from S3, and treats "SSM `TimedOut` BUT a complete S3 trace exists" as a SUCCESSFUL capture (attempts 1–6 proved the in-wrapper stdout transport hangs to the 120 s ceiling / 137). Changes the RD-013 exit surface + `DetonationInstanceRole` IAM (`s3:PutObject` on `traces/*`), so it carries its OWN live validation of the crossing (not offline-provable; 4.5/4.9 precedent). Clearing 2.4S clears the open 2.4R register entry | 2.4R, RD-057 | ✅ | P2 | 2026-09-24 |  |
| 8 | pipe | [2.5](docs/STORY_DETAIL.md#story-2-5) | Telemetry sanitization pipeline (entropy scrub → noise suppress → ≤25K truncation) | 2.4 | ✅ | P2 | 2026-09-11 |  |
| 0 | gov | [G-3](docs/STORY_DETAIL.md#story-g-3) | Hard-pause enforcement: Validation Debt register + advancement gate (no new feature story while debt open) + story-closure/restore-point decoupling; wire into `check_docs.py` (RD-023) | — | ✅ | - | 2026-09-12 |  |
| 6 | F&H | [C.3](docs/STORY_DETAIL.md#story-c-3) | Shared generator + Hub-gate seam (RD-034): collapse the 10 bespoke contract generators into one shared writer + collapse the 8 duplicated Hub-gate kind trios into one data-driven registry; `awsio` kept per-lane by design (bundling). Behaviour-preserving, byte-identical | A.4 | ✅ | - | 2026-09-12 | `restore/shared-seam-green` |
| 0 | gov | [G-2](docs/STORY_DETAIL.md#story-g-2) | Management-artifact integrity: automated consistency check + reusable-OS/instance separation (RD-015) | — | ✅ | - | 2026-09-12 |  |
| 9 | pipe | [3.2](docs/STORY_DETAIL.md#story-3-2) | Nova Pro correlation engine (exponential-backoff retry) | 3.1, 2.5 | ✅ | P3 | 2026-09-12 |  |
| 10 | pipe | [3.3](docs/STORY_DETAIL.md#story-3-3) | Three Nova Pro risk scores (static / dynamic / combined, 0-100, shared rubric) — RD-038 (reworked) | 3.2 | ✅ | P3 | 2026-09-12 |  |
| 11 | pipe | [3.4](docs/STORY_DETAIL.md#story-3-4) | Detailed findings + prioritized remediations (over the three scores + migrated candidate-FP/gap lists) — RD-039 (scope RD-038) | 3.3 | ✅ | P3 | 2026-09-13 |  |
| 12 | pipe | [3.5](docs/STORY_DETAIL.md#story-3-5) | Verdict derivation — advisory recommended PASS / FAIL / INCONCLUSIVE (never acted upon; human selects on the dashboard) — RD-040 | 3.4 | ✅ | P3 | 2026-09-13 |  |
| 5 | tenancy | [T.1](docs/STORY_DETAIL.md#story-t-1) | **Worry 2 (tenant isolation) — DESIGN SPIKE (doc-only, may proceed early — protects Phase-4 design):** write `docs/architecture/MULTI_TENANCY.md` capturing the RD-028 decisions (per-subscriber Forensic account = hard boundary; within-org shared-trust + org-shared dashboard; per-subscriber isolation granularity; residue bounded by the ephemeral host) + migration path from today's single shared Forensic account; ratify RD-028. No code. | 2.3 | ✅ | - | 2026-09-13 |  |
| 5 | security | [H.1](docs/STORY_DETAIL.md#story-h-1) | **Authenticated Hub→spoke decision — DESIGN SPIKE (doc-only; realizes RD-048, registers RD-049):** write `docs/architecture/AUTHENTICATED_DECISIONS.md` specifying the KMS-asymmetric Hub-sign / spoke-offline-verify mechanism + the `decision.token.v1` shape + the verify-then-act fail-closed gate; the shared primitive 4.6/4.7/4.4 consume. Ratify RD-049 by review. No code. | RD-048 | ✅ | - | 2026-09-13 |  |
| 6 | security | [H.2](docs/STORY_DETAIL.md#story-h-2) | **Authenticated Hub→spoke decision — BUILD (implements RD-048/RD-049):** the `decision.token.v1` contract + a PURE offline verify library (`lib/decision_auth/`: canonicalize → verify KMS-asymmetric signature → the fail-closed decision/sha256/freshness/key-trust checks) + a Hub KMS asymmetric signing-key stack (Hub-only `kms:Sign`, exported public key for offline spoke verify) + a manual `aws kms sign` validation recipe. The shared primitive the 4.6 rework + 4.7 + 4.4 consume. | H.1 | ✅ | - | 2026-09-14 |  |
| 13 | pipe | [4.1](docs/STORY_DETAIL.md#story-4-1) | Status-retrieval orchestrator (RD-041; on-demand read/transform, PURE, no write) | 3.5 | ✅ | P4 | 2026-09-13 |  |
| 14 | pipe | [4.2](docs/STORY_DETAIL.md#story-4-2) | Dashboard JSON payload (RD-042; on-demand read/transform, PURE, no write) | 4.1 | ✅ | P4 | 2026-09-13 |  |
| 14 | pipe | [4.5](docs/STORY_DETAIL.md#story-4-5) | Per-execution report (tiered: Executive / Security / Developer; RD-045, on-demand read/transform, PURE, no write; structured payload + self-contained HTML/print-to-PDF) | 4.1 | ✅ | P4 | 2026-09-13 |  |
| 14 | pipe | [4.6](docs/STORY_DETAIL.md#story-4-6) | ACCEPT → ZTIE pushes hash-verified artifact Forensic → Pipeline-Sandbox (PDE handoff; RD-047, reworked per RD-048/RD-049 to VERIFY a Hub-signed decision token OFFLINE instead of reading the Hub — depends on H.2) | 4.1, H.2 | ✅ | P4 | 2026-09-14 |  |
| 14 | pipe | [4.7](docs/STORY_DETAIL.md#story-4-7) | REJECT → destroy artifact + detonation chamber in Forensic; INCONCLUSIVE → hold at approval gate | 4.1 | ⬜ | P4 |  |  |
| 15 | pipe | [4.3](docs/STORY_DETAIL.md#story-4-3) | Real-time dashboard (dark theme, graduated severity/threat color coding) | 4.2 | ✅ | P4 | 2026-09-13 |  |
| 16 | pipe | [4.4](docs/STORY_DETAIL.md#story-4-4) | Interactive accept/reject control (Hub) gating the Forensic→Pipeline-Sandbox push | 4.3, 4.7 | ⬜ | P4 |  |  |
| 16 | pipe | [4.8](docs/STORY_DETAIL.md#story-4-8) | Dashboard browser auth: Cognito user pool (hosted UI) + identity pool → scoped temp creds SigV4-sign the 4.3 read API; retains IAM auth (RD-044). Enhancement, NOT on the Phase-4-closure path | 4.3 | ⬜ | P4 |  |  |
| 15 | pipe | [4.9](docs/STORY_DETAIL.md#story-4-9) | Report enrichment: WIDEN the RD-013 Forensic→Hub crossing to carry bounded derived MITRE ATT&CK IDs / Sigma rules / file-line so the 4.5 report renders them instead of `not_carried_on_hub` (RD-046). Enhancement, NOT on the Phase-4-closure path | 4.5 | ⬜ | P4 |  |  |
| 0 | gov | [G-1](docs/STORY_DETAIL.md#story-g-1) | Back-map design artifacts to candidate NIST family + ISO 27001 controls (RD-014) | — | ✅ | - | 2026-09-12 |  |
| 0 | gov | [G-4](docs/STORY_DETAIL.md#story-g-4) | Charter-level product view: author + maintain `docs/PRODUCT_PLAN.md` (PMP/Scrum-PO why/for-whom; no story detail or status) as a third intentional view (RD-036) | — | ✅ | - | 2026-09-12 |  |
| 6 | F&H | B.1 | Harvest inventory: survey the repo, catalog candidates + parameter surfaces + priority in `docs/governance/HARVEST_INVENTORY.md` | A.4 | ⬜ | - |  | (docs) |
| 7 | F&H | C.1 | Stand up the archive repo `infra-building-blocks` (CDK L3 lib; jest Template tests; SemVer 0.x; checkpoint tags) | B.1 | ⬜ | - |  | archive v0.1.0+ |
| 8 | F&H | C.2 | Build the parameterized constructs the inventory selected (SecureBucket, ContractIngestQueue, and the rest) | C.1 | ⬜ | - |  | archive tag per construct |
| 9 | F&H | C.4 | Migrate ONE ZTIE stack onto the archive as proof: constructs, drift-proven `cdk synth`, one "(no changes)" deploy | C.2 | ⬜ | - |  | `restore/migrate-<stack>-green` |
| 10 | F&H | C.5 | Record the practice: RD-022 into PROJECT_PLAN; METHODOLOGY note; update templates + CONVENTIONS; relocate remaining root governance docs | C.4 | ⬜ | - |  | (docs) |
| 6 | tenancy | [T.2](docs/STORY_DETAIL.md#story-t-2) | **Worry 2 — tenant provisioning/deprovisioning [DEFERRED: commercialization phase, after core pipeline]:** automate stand-up + teardown of an isolated per-SUBSCRIBER ZTIE environment per the T.1 model (per-subscriber account-vending), subscriber-tagged + cost-tracked, nuke-on-offboard | T.1 | ⬜ | - |  |  |
| 7 | tenancy | [T.3](docs/STORY_DETAIL.md#story-t-3) | **Worry 2 — Hub-side per-SUBSCRIBER data isolation + noisy-neighbor/quota controls [DEFERRED: commercialization phase, after core pipeline]:** per-subscriber partitioning of the Hub tracking/reporting/dashboard plane; per-subscriber limits so one subscriber's detonations cannot starve another (NO per-user partitioning — within-org is shared-trust, RD-028) | T.2 | ⬜ | - |  |  |

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
| _(none open)_ | — | — | — |

> **Register status: EMPTY (0 open). The advancement gate is DISARMED.** Story **2.4S**
> (Fix B / RD-058) was VALIDATED LIVE 2026-09-24 by the independent validator (Gemini, blind,
> RD-055) on the clean final code (`main` `c1e323c`), with the ⛔ non-skippable deploy
> code-asset gate passing first — sealed **PASS**. Raw evidence retained per RD-054 in
> [`docs/validation-evidence/2.4S/attempt-5/`](docs/validation-evidence/2.4S/attempt-5/EVIDENCE.md):
> the Forensic artifact bucket held `traces/beb6f4b5-…/` with the host's per-PID
> `behavior.strace.762`/`.763` + the `_UPLOAD_COMPLETE` sentinel (written last), and the Lambda
> read the trace from S3 and treated the timed-out SSM command with a complete S3 trace as a
> SUCCESSFUL capture (RD-058 intent). **Since 2.4S is the RD-058 remediation of 2.4R, the linked
> 2.4R entry cleared together (one work item)** — the auditable dynamic-lane (strace) evidence
> backfill 2.4R was chartered to provide now exists. Both flipped ✅ in the master table
> (2026-09-24). With the register empty, the next pipe story (**4.7**) is unblocked.
>
> **Story 2.4** (behavioral telemetry, RD-030)
> stays ✅ for what it validated live 2026-09-10, but under **RD-054** that pass rests on
> testimony (no retained raw artifacts; the ephemeral Forensic trace has aged out), so the
> auditable evidence backfill for the DYNAMIC lane was queued forward as **2.4R** (the
> 2.2G/2.2R precedent), which re-arms the gate.
>
> **2.4R live validation attempt 1 — SEALED VERDICT: FAIL (2026-09-16).** 2.4R was run live
> under the RD-053 split-brain protocol (intake `2b0af6a6-6552-461f-a18f-f6cca60ba0bc`, code
> under test commit `566e274`, Forensic `360999005254` / Hub `641628980935`); the independent
> validator (Gemini) returned **FAIL**. **DoD 1 FAIL** — the raw Forensic strace trace
> completely missed the planted write buffer `ZTIE-EVIL-BUFFER-DATA` (no `write()` syscall
> captured at all; strace's `-e trace=` set omits the write-class syscalls), so the positive
> adversarial capture is incomplete. **DoD 2 PASS** — no buffer leaked into the Hub item (but
> hollow: it was never captured to begin with). **DoD 3 FAIL** — the negative verdict-field
> probe hit `recommended_verdict` / `verdict_result` / `verdict_at` on the tracking item
> (written by the concurrent Phase-3 `hub_verdict` RD-040 stage), violating the evidence-only
> requirement of the probe. **DoD 4** satisfied by the retained evidence folder. So **2.4R
> STAYS 🟡, remains OPEN on this register, and the gate stays ARMED** (NOT flipped ✅ — a FAIL
> never earns ✅). The raw run artifacts are retained per RD-054 in
> [`docs/validation-evidence/2.4R/`](docs/validation-evidence/2.4R/EVIDENCE.md) as the
> auditable failure record. Fix-forward (covenant §4, fix-then-validate-once): (1) strace must
> capture write-class syscalls; (2) fix the `cat $(ls … | sort)` alphabetical concatenation /
> child-follow / 512KB-truncation ordering defect; (3) the network artifact must exercise a
> real `connect()` (Ubuntu `/bin/sh` is `dash`, no `/dev/tcp`, so the intent surfaced as a
> file `openat`); (4) scope the DoD-3 verdict-field probe to the `behavior` attribute (or run
> a detonation-only path that does not trigger the Phase-3 verdict stage). A future PASS
> requires a fresh live run of the FIXED code with its own retained evidence.
>
> **2.4R live validation attempt 2 — SEALED VERDICT: FAIL (2026-09-16), NEW failure mode.**
> The attempt-1 fixes shipped in PR #175 (merged to main `bdc7a68`), and the live re-run of
> that FIXED code (intake `528c0ad1-8285-46fa-8327-48f424d3ca4d`, Forensic `360999005254` /
> Hub `641628980935`) produced a TOTAL capture failure: `capture_status: capture_error`,
> `error_reason: "no behavioral trace emitted between capture markers"` — strace produced NO
> per-PID trace files at all (empty between the BEGIN/END markers), and the S3 `run.log` was
> a 404 (never written). The ~126 s capture window (started 65551 ms → stopped 191500 ms)
> shows the artifact DID run; strace erred out without tracing. PRIME SUSPECT (a defect the
> PR #175 rework introduced): the added `%desc` trace group in
> `-e trace=%file,%desc,%network,%process,%signal` is rejected by the golden AMI's strace
> build, so strace exits before writing any `-ff` file — the "offline can't catch it" class
> (offline only asserts the command STRING). COMPOUNDING DEFECT: the `capture_error` path
> discards strace's stderr and wrote no run log, so the run is BLIND to the exact cause. So
> **2.4R STAYS 🟡, remains OPEN, gate ARMED** (NOT ✅ — `capture_error`/no-trace is worse than
> INCONCLUSIVE, never a pass). Evidence retained per RD-054 in
> [`docs/validation-evidence/2.4R/attempt-2/`](docs/validation-evidence/2.4R/attempt-2/EVIDENCE.md).
> Re-fix (fix-then-validate-once): (1) make the strace trace-group set robust so a rejected
> group cannot silently zero the whole capture (explicit widely-supported syscall list, or a
> fallback if a group is rejected); (2) make the no-trace path SELF-DIAGNOSING — surface the
> strace stderr / a diagnostic into the emitted output + ensure the run log is written, so a
> no-trace run is never blind to WHY; (3) re-validate live, confirming the planted write
> buffer appears in the raw trace.
>
> **2.4R live validation attempt 3 — SEALED VERDICT: FAIL (2026-09-16); the %desc theory is
> FALSIFIED.** The v3 fix shipped in PR #176 (merged main `8cd0e2b`) — explicit
> `write`/`writev`/`pwrite64` (NO `%desc`) + a self-diagnosing no-trace path. The live re-run
> (intake `0ad74eb4-7290-4958-8837-58edb7c6e9a7`) produced the SAME `capture_status:
> capture_error` / generic `error_reason: "no behavioral trace emitted between capture
> markers"`, AND the self-diagnostic marker did NOT fire. Two consequences: (a) removing
> `%desc` did not help ⇒ the attempt-2 `%desc` root cause was WRONG/incomplete; (b) the
> self-diagnostic not appearing (nor a strace reason) is the tell. REASSESSED PRIME SUSPECT
> (transport, not strace): the trace is delivered back INLINE via the SSM command's
> `StandardOutputContent`, which AWS truncates at **24,000 characters** (`poll_command` reads
> it; `send_command` sets no `--output-s3-bucket-name`). The capture command emits verbose
> output BEFORE the trace (`curl -v` fetch + banners); once cumulative stdout crosses 24 KB
> everything after — the `begin` marker, the trace, AND the self-diagnostic — is dropped, so
> `slice_trace` sees no usable trace ⇒ generic `capture_error`. This explains why the
> strace-flag changes (attempts 2–3) never helped: they change trace CONTENT/size, not the
> 24 KB transport dropping it. **This is an INFRASTRUCTURE defect (SSM inline-stdout cap),
> not a strace-invocation defect.** So **2.4R STAYS 🟡, OPEN, gate ARMED** (NOT ✅). Evidence:
> [`docs/validation-evidence/2.4R/attempt-3/`](docs/validation-evidence/2.4R/attempt-3/EVIDENCE.md).
> BEFORE the 4th fix: CONFIRM via the retained `runs/<intake>/detonation-output.json` (its
> `stdout` should be ~24000 chars, missing the `begin`/`end` markers). If confirmed, the 4th
> fix is ARCHITECTURAL — deliver the trace to Forensic S3 directly (SSM
> `--output-s3-bucket-name`, or host-writes-to-S3 + Lambda-reads-from-S3) so trace SIZE stops
> being a correctness gate — not another strace-flag tweak.
>
> **2.4R evidence CONFIRMED + the truncation theory FALSIFIED — SEALED FAIL attempt 4
> (2026-09-17).** The confirm-then-fix gate (PR #178, `docs/validation-evidence/2.4R/attempt-3/CONFIRM-BEFORE-FIX.md`)
> was executed: the retained `runs/0ad74eb4-…/detonation-output.json` was fetched from the
> Forensic artifact bucket and adjudicated (Gemini). The raw facts KILLED the truncation
> theory too: **`ssm_status: TimedOut`, `exit_code: 137` (SIGKILL), `len(stdout): 46`,
> `len(stderr): 0`, no BEGIN/END/DIAG markers, zero trace-file headers.** `len(stdout)=46` is
> nowhere near the 24 KB cap — nothing was truncated; there were only 46 bytes to begin with.
> **CONFIRMED ROOT CAUSE:** the known-behavior probe's last op `exec 3<>/dev/tcp/93.184.216.34/443`
> BLOCKS in the egress-less Forensic VPC (no SYN-ACK ever comes); strace, following the
> artifact, blocked with it; after the SSM command's `executionTimeout` (handler
> `EXEC_TIMEOUT_S`, default **120 s**) elapsed, the SSM agent **SIGKILLed the ENTIRE wrapper
> script** (exit 137) — so execution NEVER reached the trace-emit block, the BEGIN/END markers
> + per-PID concat loop never ran, the on-host `-o` trace files died with the host at TTL, and
> the Hub's "no trace between markers" was the CORRECT downstream report of an upstream hang.
> This falsifies ALL prior theories (truncation, `%desc`, shell-branch): nothing was
> truncated, and strace never got to write (empty stderr too). **ARCHITECTURAL FINDING:** the
> capture wrapper was brittle to a hanging/sleeping artifact — a real malware behavior (C2
> connect, daemon, sleep) — and lost the entire trace. **FIX BUILT (2.4R4, this session,
> fix-then-validate-once):** bound the artifact run on-host with `timeout -k GRACE BUDGET`
> (default 75 s + 5 s, well under the 120 s SSM ceiling) around the strace/artifact run so a
> hanging artifact is terminated but the **WRAPPER SURVIVES** to emit whatever strace already
> wrote; a `ZTIE-ARTIFACT-TIMED-OUT` marker + honest capture-health recording (partial trace
> ⇒ `captured` + `trace_truncated` + a timeout note; empty ⇒ `capture_error` with a
> timeout-specific reason) — never a verdict (a hanging artifact is EVIDENCE). Offline-proven
> (capturespec 32 tests incl. a new timeout regression class; full detonation suite 157 OK;
> ruff/tsc-no-new-type/prettier/gen-contracts clean) AND behaviorally proven locally (a
> stand-in that writes a per-PID file then `sleep 600` was killed at the budget, the marker
> fired, and the wrapper emitted the captured file incl. the `connect()` intent — elapsed =
> budget, not 600). **2.4R STAYS 🟡, OPEN, gate ARMED** (NOT ✅ — a FAIL never earns ✅; the fix
> is unvalidated until a fresh live run of the FINAL code). Evidence + as-built + LIVE-RUNBOOK:
> [`docs/validation-evidence/2.4R/attempt-4/`](docs/validation-evidence/2.4R/attempt-4/EVIDENCE.md).
>
> **2.4R live validation attempt 5 — SEALED VERDICT: FAIL (2026-09-20); the 2.4R4 on-host
> `timeout` fix is FALSIFIED as deployed.** The fix was pinned to commit `9cd4102` (immutable
> target, `main` tip `03602939`) and DEPLOYED — the live `ZtieDetonationStack` Lambda env was
> confirmed present before the run (`ARTIFACT_EXEC_TIMEOUT_S=75`, `ARTIFACT_EXEC_KILL_GRACE_S=5`).
> **CORRECTION (2026-09-20, audit-honesty):** the earlier claim here that this "was NOT a
> deploy-gap; the FINAL fixed code ran" is WITHDRAWN as an overclaim — the env-var check does
> NOT prove it. `capturespec.py` reads those vars with in-code defaults
> (`os.environ.get("ARTIFACT_EXEC_TIMEOUT_S", "75")` / `..._KILL_GRACE_S", "5")`), so they read
> `75`/`5` whether or not the deployed CODE PACKAGE actually contained the attempt-4 wrapper —
> env-present and env-absent are behaviorally identical. Only a LIVE CODE-ASSET check (grep the
> deployed `capturespec.py` for `timeout -k`, or compare `CodeSha256`) could have distinguished
> **H1 (attempt-4 fix genuinely ran and is ineffective)** from **H2 (stale code asset ran; the
> fix was never exercised)**, and that check was not performed. The ephemeral Forensic host is
> gone (RD-012), so H1 vs H2 for attempt 5 is now **UNDETERMINED** and cannot be retroactively
> proven. The sealed FAIL stands (the run did not produce a trace); what is corrected is the
> unproven attribution of WHY. (Going forward the deploy gate verifies the code asset, not the
> env — see `docs/session-briefs/story-2.4R-DEPLOY-VERIFY.md` STEP 4.) The known-behavior probe (last op
> `exec 3<>/dev/tcp/93.184.216.34/443 || true`) was submitted and the result was IDENTICAL to
> attempt 4: **`ssm_status: TimedOut`, `exit_code: 137` (SIGKILL), `len(stdout): 46`,
> `len(stderr): 0`, NO BEGIN/END markers, NO `ZTIE-ARTIFACT-TIMED-OUT` marker, and the Forensic
> S3 trace file a 404.** The 75 s GNU `timeout` did NOT return control to the wrapper: execution
> still hung until the 120 s SSM `executionTimeout` (`EXEC_TIMEOUT_S`) SIGKILLed the whole
> wrapper before the emit block ran, so the trace was lost entirely. **Why the fix failed
> (attempt-6 investigation, not a sealed mechanism):** `_instrumented_exec_commands` wraps
> `timeout -k 5 75 strace -ff … /bin/sh <artifact>` — `timeout` signals its DIRECT child
> (`strace`), not the process group, while the blocking `connect()` lives in a re-exec
> GRANDCHILD; killing `strace` need not kill the traced grandchild, which can survive and hold
> the inherited SSM stdout pipe open (the `len(stdout)=46`, no-EOF tell), so the wrapper never
> regains control. Lines of inquiry: (1) process-group / session kill (`setsid` + `kill -- -<pgid>`,
> or `timeout` over a `setsid` session) so the KILL reaches the artifact PID/PGID, not just the
> tracer; (2) `strace -f` tracer that forwards fatal signals to the traced subtree; (3) detach
> the artifact's stdio to on-host files (not the inherited SSM pipe) so a lingering child cannot
> hold the command pipe open; (4) ARCHITECTURAL — deliver the `strace -o` per-PID files to
> Forensic S3 DIRECTLY on strace exit (SSM `--output-s3-bucket-name` or a host `aws s3 cp` trap)
> so trace survival no longer depends on the fragile in-wrapper emit block that has now failed
> five times. **2.4R STAYS 🟡, OPEN, gate ARMED** (NOT ✅ — a FAIL never earns ✅; a PASS requires
> a fresh live run of a NEW attempt-6 fix with its own retained evidence). Evidence retained per
> RD-054 in [`docs/validation-evidence/2.4R/attempt-5/`](docs/validation-evidence/2.4R/attempt-5/EVIDENCE.md).
>
> **2.4R live validation attempt 6 — SEALED VERDICT: FAIL (2026-09-20); RD-057 / Fix A
> (process-group kill via `setsid` + stdio detach) did NOT resolve the SSM stdout pipe-lock
> hang. This FAIL MEETS THE 2.4S (RD-058) TRIGGER.** Run against the immutable target
> `1e44cc4d6504004a5e67973f5acdc7ca5b4e81f3`; the CODE-ASSET deploy gate confirmed the live
> `capturespec.py` contained `setsid timeout --kill-after=` (the fixed code ran — this is NOT
> a stale-deploy artifact, and unlike attempt 5 the code-asset check makes that provable).
> `aws ssm get-command-invocation`: **`Status: TimedOut`, `StatusDetails: ExecutionTimedOut`,
> `ExecutionElapsedTime: PT2M0.003S` (the exact 120 s ceiling), `ResponseCode: 137` (SIGKILL),
> `StandardOutputContent` = the `=== ZTIE detonation: begin (instrumented) ===` banner ONLY,
> no trace, no closing footer.** DIAGNOSTIC DELTA vs attempts 4/5 (which returned `len 46` /
> no markers): the begin banner — emitted immediately BEFORE the `setsid timeout … strace …`
> line — DID print, so the wrapper reached + started the traced run under Fix A and then still
> hung to 120 s/137; the hang is DOWNSTREAM of where Fix A acts. ROOT CAUSE is NOT disambiguated
> by this output (recorded honestly, per the attempt-5 lesson — do not over-attribute a WHY the
> raw output cannot prove): either (1) a detached grandchild/lingering fd still holds the SSM
> stdout pipe open so the agent never gets EOF, OR (2) `setsid` moved the traced child into a
> new session so GNU `timeout` could not deliver the kill to it — both yield `TimedOut`/137.
> DECISION: the SSM stdout transport is structurally fragile for a deliberately-misbehaving
> artifact regardless of which mechanism holds, so the fix is **RD-058 / Story 2.4S (Fix B)** —
> abandon stdout as the payload transport: the host writes `strace -o` per-PID files and uploads
> them to Forensic S3 (`traces/{intake_id}/`) BEFORE the wrapper exits, and the Lambda reads the
> trace from S3, not `StandardOutputContent`, so the evidence SURVIVES the hang. **CRITICAL scope
> addition surfaced by this run:** Fix B does NOT stop the SSM `TimedOut` (if the pipe stays held
> the SSM status is still `TimedOut`/137), so 2.4S's Lambda MUST treat "SSM `TimedOut` BUT a
> complete S3 trace exists" as a SUCCESSFUL capture, else durable evidence still records a FAIL.
> Accordingly **Story 2.4S moves ⬜ DEFERRED → 🟡 (its trigger is met)**; it remains a
> `[sec-boundary]` story that changes the RD-013 exit surface + `DetonationInstanceRole` IAM and
> carries its OWN live validation of the crossing. **2.4R STAYS 🟡, OPEN, gate ARMED** (NOT ✅ —
> Fix A is insufficient; a PASS now comes via the Fix B code + its own recorded live pass).
> Evidence: [`docs/validation-evidence/2.4R/attempt-6/`](docs/validation-evidence/2.4R/attempt-6/EVIDENCE.md).
>
> **2.4S live validation attempt 1 — SEALED VERDICT: INCONCLUSIVE (2026-09-22); BLOCKED by an
> upstream Story 2.0 host-launch failure, NOT a 2.4S defect.** The Fix-B code (PR #192, merge
> `5c5cd76`) went to the independent validator (Gemini, blind, RD-055 — Kiro supplied the PR
> number only). The IAM half PASSED — **DoD 1 (positive)** and **DoD 2 (negative)** both confirmed
> via `iam:simulate*` that `DetonationInstanceRole` is correctly granted `s3:PutObject` on
> `traces/*` (and implicitly denied elsewhere). But **DoD 3 (live deposit)** and **DoD 4 (timeout
> survival)** are **BLOCKED**: the ephemeral detonation host **never launched**, so the Fix-B
> S3-upload / `_UPLOAD_COMPLETE` sentinel / S3-first read / "`TimedOut` but complete S3 trace =
> success" behavior was NEVER exercised. Raw evidence (`/tmp/24s-out.json`): `"outcome":
> "launch_error"`, `"error_reason": "RunInstances failed: … (MissingParameter) … The request must
> contain the parameter ImageId"`, `"ssm_status": "not_run"` (no host ever existed). ROOT CAUSE
> (validator RCA, confirmed against source): `run_instance_from_template` calls `ec2:RunInstances`
> with the launch template + `Version:$Latest` and omits `ImageId`; the currently-deployed
> `$Latest` version of `lt-045ddce7fdac386db` (Forensic `360999005254`) carries no valid AMI. The
> stack resolves the AMI via `MachineImage.fromSsmParameter("/ztie/ami/ubuntu-22.04")` (verified:
> `AMI_SSM_PREFIX="/ztie/ami"`, default flavor `ubuntu-22.04`; the stack CONSUMES, the Image
> Builder PUBLISHES), so the SSM parameter was empty/stale/dummy at the last `cdk deploy` — a
> **deploy-state / drift** condition, NOT a structural 2.0 CDK defect. **2.4S STAYS 🟡, 2.4R STAYS
> 🟡, gate ARMED** — INCONCLUSIVE clears nothing (a blocked run is never a pass). The blocker is
> tracked as **OD-006** (`Blocks: 2.4S validation → 2.4R clearance`). NO code change: the fix is
> operational (republish AMI to `/ztie/ami/ubuntu-22.04` → `cdk deploy ZtieForensicInfraStack` →
> VERIFY the live template version carries a real `ImageId`, never trust the green
> `UPDATE_COMPLETE` → re-run the SAME sealed runbook from STEP 3; no re-review, the code is
> unchanged). Evidence retained per RD-054 in
> [`docs/validation-evidence/2.4S/attempt-1/`](docs/validation-evidence/2.4S/attempt-1/EVIDENCE.md).
>
> **2.4S live validation attempt 2 — SEALED VERDICT: FAIL (2026-09-22); host direct upload
> failed SILENTLY, fell back to SSM stdout. FIRST attempt the host actually launched (OD-006
> resolved), so Fix B was genuinely exercised — and a real 2.4S code defect surfaced.** DoD 1/2
> (IAM) PASS again; **DoD 3 (live deposit) FAIL** — the only object under `traces/{intake_id}/`
> was `behavior-trace.txt`, which is the **Lambda's own** consolidated write (`awsio.put_trace`),
> NOT the host's per-PID `behavior.strace.<pid>` files, and the `_UPLOAD_COMPLETE` sentinel was
> MISSING; **DoD 4 (timeout survival) FAIL** — evidence did not survive out-of-band. The handler's
> S3-first read found no per-PID objects + no sentinel and **fell back to the stdout slice** — the
> exact fragile transport Fix B was built to replace. ROOT CAUSE (localized against source, a real
> 2.4S code defect): the isolated host reaches S3 ONLY via the VPC gateway endpoint, which serves
> the REGIONAL host `s3.us-east-1.amazonaws.com` (the GLOBAL `s3.amazonaws.com` TCP-times-out —
> documented + live-verified in `awsio._s3()`). The Lambda pins its client regional + SigV4 so the
> presigned FETCH works, but `capturespec.build_trace_upload_commands` emits bare `aws s3 cp …
> --only-show-errors || true` with **no `--region` and no `--endpoint-url`**, so the host CLI
> targeted the GLOBAL endpoint, hung/timed out, and the `|| true` **swallowed the failure
> silently**; the wrapper then emitted the trace on stdout → Lambda sliced it → `behavior-trace.txt`.
> **2.4S STAYS 🟡, 2.4R STAYS 🟡, gate ARMED** (a FAIL never earns ✅). Fix-then-validate-once on
> branch `fix/story-2.4S-host-regional-s3`: (1) inject the region DETERMINISTICALLY from the CDK
> deploy context (NOT the host env — SSM `AWS-RunShellScript` runs in a stripped shell where
> `AWS_REGION` is flaky/absent) + add `--region <r> --endpoint-url https://s3.<r>.amazonaws.com` to
> every host `aws s3 cp`, mirroring `awsio._s3()`; (2) keep `|| true` but redirect each copy's stderr
> to a host log that ships back between markers so a future upload failure is SELF-DIAGNOSING, never
> silent (observability covenant). The FIXED code re-validates blind from its own new PR number.
> **OD-006 is RESOLVED** — the host launched this attempt (AMI republish + `ZtieForensicInfraStack`
> redeploy worked); closed in the Operational Debt Register. Evidence retained per RD-054 in
> [`docs/validation-evidence/2.4S/attempt-2/`](docs/validation-evidence/2.4S/attempt-2/EVIDENCE.md).
>
> **2.4S live validation attempt 3 — SEALED VERDICT: FAIL (2026-09-22); regional-endpoint fix
> (PR #195) is LIVE and CORRECT, but the host `aws` CLI is NOT on the SSM PATH so the uploads
> never ran. NET-POSITIVE FAIL — the self-diagnosing log built in PR #195 exposed the exact
> cause on the first failing run (no blind cycle).** DoD 1/2 (IAM) PASS; **DoD 3 (deploy) PASS**
> — the fixed code was live (proven precisely because the new `ZTIE-UPLOAD-DIAG-BEGIN/END`
> diagnostic block fired); **DoD 4 (live deposit) FAIL** — S3 `traces/24s-live-test-3/` again held
> only the Lambda's own `behavior-trace.txt` (stdout fallback), no per-PID files, no sentinel;
> **DoD 5 (timeout survival) FAIL** — the direct-upload path did not execute. ROOT CAUSE (from the
> shipped diagnostic, `runs/24s-live-test-3/detonation-output.json` → `.stdout` between the diag
> markers): `aws: not found` at the host shell (dash/`sh`, lines 15-16 = the per-PID `aws s3 cp`
> loop + the sentinel copy) — **the AWS CLI is not resolvable on the host PATH in the
> non-interactive SSM `AWS-RunShellScript` shell**; every `aws s3 cp` failed instantly and `|| true`
> swallowed it (by design), so the wrapper fell back to stdout. The artifact FETCH worked because
> it uses `curl` on a presigned URL, not the CLI — so this was the first host step to need `aws`,
> and the RD-030 assumption that `aws` is globally available on the host is wrong. **2.4S STAYS 🟡,
> 2.4R STAYS 🟡, gate ARMED** (a FAIL never earns ✅). FIX depends on a fact the output does NOT
> settle — is the CLI INSTALLED-but-off-PATH (→ reference an ABSOLUTE path in `capturespec.py`, a
> small builder change) or NOT INSTALLED on the golden AMI (→ the Image Builder / AMI recipe must
> install it, a Story 2.0-FOUNDATION change)? A live host probe (`command -v aws || ls -la
> /usr/local/bin/aws /usr/bin/aws`) settles it; do NOT hardcode a path that may not exist
> (fix-then-validate-once; avoid repeating the attempt-2 assume-and-fail). Evidence retained per
> RD-054 in [`docs/validation-evidence/2.4S/attempt-3/`](docs/validation-evidence/2.4S/attempt-3/EVIDENCE.md).
>
> **2.4S live validation attempt 4 — SEALED VERDICT: FAIL (2026-09-23); Fix A (`__ZTIE_RC=0`,
> PR #200) is PROVEN, but Fix B (the direct host→S3 trace upload that IS Story 2.4S / RD-058)
> STILL fails SILENTLY and the run falls back to the SSM stdout transport.** Code under test =
> current `main` `99ffdd4` (all five fixes in: PRs #195 regional-endpoint / #198 absolute-CLI /
> #199 root-volume-30GB / #200 set-u init; OD-006 AMI-empty resolved), handed to the independent
> validator (Gemini, blind, RD-055) as the latest merged fix. Intake
> `6994199c-9255-4026-becd-cdf0dbb3c426` (`validation_hang.sh`, 49 B — a hang-past-timeout probe,
> so Fix B's timeout path was genuinely exercised), Forensic `360999005254` / Hub `641628980935`.
> **NET-POSITIVE:** the wrapper SURVIVED the hanging artifact — **`exit_code: 124`** (GNU
> `timeout`) + the **`ZTIE-ARTIFACT-TIMED-OUT`** marker fired (no 120 s SSM SIGKILL/137 this
> time), and strace evidence WAS extracted (a full 11,851-byte `runs/6994199c-…/detonation-output.json`
> via the stdout fallback — so the per-PID `-o` files DID exist for the later emit block). **DoD
> 1/2 (IAM) PASS** (attempt 2); **DoD 3 (deploy) PASS** (the fixed code ran — the wrapper survived
> + the upload markers printed). **DoD 4 (live deposit) FAIL** — S3 has **no `traces/6994199c-…/`
> prefix at all**: NO `behavior.strace.<pid>` per-PID objects and NO `_UPLOAD_COMPLETE` sentinel
> (no `behavior.strace.<pid>` / no sentinel exists anywhere in the bucket for ANY intake — Fix B
> has never deposited). **DoD 5 (timeout survival) FAIL** — `trace_from_s3` was not `True`; the
> Lambda fell back to the stdout slice. **KEY DIAGNOSTIC:** the self-diagnosing
> `ZTIE-UPLOAD-DIAG-BEGIN`/`END` block (PR #195) is **EMPTY** — because every host `aws s3 cp`
> appends `2>>/tmp/ztie/upload.stderr` and the diag ships that log, an empty block means the
> copies wrote NO stderr: they neither ran-and-failed (a fail logs a cause) nor ran-and-succeeded
> (success deposits objects). So this is a NEW, distinct silent-failure mode — the attempt-2
> (global-endpoint) and attempt-3 (`aws` not on PATH) causes are FIXED and NOT the cause (either
> recurring would have written to the errlog). **2.4S STAYS 🟡, 2.4R STAYS 🟡, gate ARMED** (a
> partial/FAIL never earns ✅). ROOT CAUSE **NOT over-attributed** (attempt-5 lesson): candidates
> are (1) the upload `for __t in $(ls /tmp/ztie/behavior.strace.* …)` glob being empty AT UPLOAD
> TIME (a visibility/ordering issue vs. the later emit `ls`), (2) a `setsid timeout --kill-after`
> SIGKILL-group interaction perturbing the upload sub-block, (3) the sentinel copy silently
> no-op'ing / its stderr not reaching the errlog under the SSM shell — the sharpest anomaly is
> that the sentinel `printf | aws s3 cp -` wrote NEITHER an object NOR stderr. CONFIRM-BEFORE-FIX
> (covenant §4, do NOT guess): a live host probe (`pwd`/`id`, `ls -la /tmp/ztie/` + the glob, and
> ONE explicit test `aws s3 cp` with stderr un-suppressed + `echo cp_rc=$?`) settles which
> mechanism holds BEFORE any attempt-5 code change. Evidence retained per RD-054 in
> [`docs/validation-evidence/2.4S/attempt-4/`](docs/validation-evidence/2.4S/attempt-4/EVIDENCE.md)
> (the EMPTY diag block + the adjudicating S3 slice).
>
> **2.4S attempt-4 confirm-before-fix probe — FINDING (2026-09-24): Fix B WORKS; attempt-4 was a
> DEPLOY-GAP, not a code defect. NO attempt-5 code fix; next = a CLEAN split-brain re-validation.**
> The confirm-before-fix probe (temporary in-wrapper diagnostic, PR #205 closed UNMERGED) was run on a
> VERIFIED-LIVE deploy (live code-asset grep confirmed BEFORE the run). On the same hang-past-timeout
> payload (intake `beb6f4b5-bdcc-4466-984c-fdaa3256bcdd`, `exit_code=124`, `ssm_status=Failed`): the
> per-PID files + the `_UPLOAD_COMPLETE` sentinel deposited to `traces/{intake_id}/` (`per_pid_cp_rc=0`,
> `sentinel_cp_rc=0`, `PROBE-GLOB-COUNT: 2`), and the Lambda logged `using S3-uploaded behavioral trace
> (objects=2 complete=True ssm_status=Failed)` — the exact RD-058 intent. All three attempt-4 candidates
> (glob-empty / SIGKILL-teardown / IAM-endpoint) are FALSIFIED. So the direct-upload + S3-first-read +
> "Failed-but-complete-S3-trace = success" path is CORRECT as written; the attempt-4 empty-diag + zero-
> objects signature is most consistent with the live Lambda running STALE pre-#200 code (wrapper crashed
> on the `set -u` unbound `__ZTIE_RC` before the upload block) — the recurring green-deploy-of-stale-code
> class. HONEST LIMIT (attempt-5 over-attribution lesson): the ephemeral attempt-4 host is gone (RD-012),
> so H1-vs-H2 for THAT run cannot be retro-proven; the attempt-4 sealed FAIL stands as the record of that
> run, and this corrects the WHY. **2.4S STAYS 🟡, 2.4R STAYS 🟡, gate ARMED** — the probe was executor-
> run on a probe-contaminated wrapper and is NOT a validation pass (RD-055 requires the independent
> validator on the CLEAN final code). DURABLE FIX = PROCESS: the post-deploy live code-asset check is now
> a ⛔ NON-SKIPPABLE gate in `docs/session-briefs/story-2.4R-DEPLOY-VERIFY.md` (grep the live
> `capturespec.py` for `__ZTIE_RC=0` AND the Fix-B upload markers before validating), reinforced by
> OD-007 (offline wrapper smoke-test harness) + OD-008 (SFN false-green). Next = a CLEAN split-brain
> re-validation of current `main` (final code, deploy-asset gate enforced). Finding:
> [`docs/validation-evidence/2.4S/attempt-4/PROBE-FINDING.md`](docs/validation-evidence/2.4S/attempt-4/PROBE-FINDING.md).
>
> **Prior entry (cleared 2026-09-15):**
> **Story 2.2R** was cleared by its own recorded split-brain live pass (intake
> `669f5ce7-bef4-47bd-aa7f-a4fca1450005`: positive detection `gitleaks count: 1` + raw-JSON
> redaction human-verified, RD-009); 2.2G remains ✅ for the wiring/supersession it validated.
> **Phase 3 is CLOSED** (3.5 validated
> live 2026-09-13); **Story 4.1 (RD-041)**,
> **4.2 (RD-042)**, **4.3 (RD-043)**, **4.5 (per-execution tiered report, RD-045)**, and
> now **Story 4.6 (ACCEPT-push, RD-047, reworked per RD-048/RD-049)** are all validated
> live + closed ✅. **Story 4.6 was validated live 2026-09-14** in the Hub 641628980935 /
> Forensic 360999005254 / Pipeline-Sandbox 586917955591 on the reworked (verify-a-Hub-
> signed-token-offline) code; its register entry was then cleared. The next feature work is
> **4.7** (REJECT→destroy, the tied tier-14 sibling — verifies a Hub-signed `rejected`
> token the same way), then **4.4** which closes Phase 4 on 4.3 + 4.7, with **B.1** (F&H
> harvest inventory) sequenced after the Phase-4 pipe work per the reorder. Keep it this way:
> a story goes into the register the moment it is built-but-unvalidated, and comes out only on
> its own recorded live pass.
>
> _Prior entry (cleared 2026-09-14):_ **Story 4.6** (ACCEPT-push, RD-047, reworked per
> RD-048/RD-049) was cleared by its own recorded live validation across three accounts.
> `ZtiePdeHandoffStack` (Forensic) redeployed on the fixed `main` — verified live: the
> pusher role has ONLY `s3:GetObject` / `s3:PutObject` / `s3:PutObjectTagging` /
> `sqs:SendMessage` (**NO `dynamodb`, NO `bedrock`**) and its env has `HUB_PUBLIC_KEY_PEM` +
> `TRUSTED_KEY_IDS` and **NO `TRACKING_TABLE` / NO `NOVA_MODEL_ID`** — the rework's whole
> point (no spoke→Hub read; the decision is a Hub-signed `decision.token.v1` verified
> OFFLINE, RD-048/RD-049). Hub signed an `accepted` token for intake
> `891cb78f-fd35-4045-81d6-030d75d9c83e` (`aws kms sign` ECDSA_SHA_256 over the canonical
> token bytes); the Forensic pusher verified it offline and PUSHED — `pushed: true`,
> `outcome: pushed`, `observed_decision: accepted`, `hash_verified: true`, destination
> account `586917955591` bucket `ztiesandboxlandingstack-…` key `accepted/891cb78f-…/
> probe.yaml`. The object LANDED and its recomputed sha256 == the tracked
> `cd04299d8e29601f5425054e0470a71f255fb19a7d2fe3734bcb6213f27208f0`. FAIL-CLOSED proven
> 5/5 (no token → `{"error":{"code":400}}`; rejected → `refused_not_accepted`/
> `wrong_decision`; sha-mismatch → `refused_hash_mismatch`; stale → `refused_not_accepted`/
> `stale`; tampered signature → `refused_not_accepted`/`bad_signature`) with nothing
> leaking to the Sandbox (exactly one object under `accepted/`). The bounded, verdict-free
> `handoff` outcome crossed Forensic→Hub via the RD-013 one-directional ingest queue
> (`handoff_outcome: pushed`, `observed_decision: accepted`, `hash_verified: true`,
> `destination` present, `size_bytes: 81`; NO `verdict`/`safe`/`approved`/`forward`/
> `malicious`/`pass_fail`/`clean` key) — no spoke→Hub read anywhere. Two live fixes were
> applied fix-then-validate-once: (1) PR #153 — `bin/ztie-infra.ts` now accepts a single-
> line `hubPublicKeyPemBase64` context value (the multi-line PEM passed via `-c` had
> truncated to a 27-byte header line, so the embedded key was incomplete and offline verify
> fail-closed with `bad_signature`); (2) `ZtieHubTrackingStack` was redeployed so the live
> `hub_ingest` validator knows the `handoff` envelope kind (a deploy-gap — the crossed
> outcome was quarantined until then; no code change). Full detail:
> [4.6 in STORY_DETAIL.md](docs/STORY_DETAIL.md#story-4-6).
>
> _Prior entry (cleared 2026-09-13):_ **Story 4.5** (per-execution tiered report, RD-045) was
> cleared by its own recorded live validation in the Hub 641628980935. `ZtieHubTrackingStack`
> redeployed (ships the new PURE, READ-only `hub_report` orchestrator — verified live: env
> has `REPORT_CONTRACT_VERSION: 1.0` + `STATUS_CONTRACT_VERSION: 1.0` + `TRACKING_TABLE` +
> `LOG_LEVEL` and NO `NOVA_MODEL_ID`; role has only READ `dynamodb:*` and NO
> `UpdateItem`/`PutItem`/`DeleteItem` and NO `bedrock:InvokeModel`). Invoked for intake
> `891cb78f-fd35-4045-81d6-030d75d9c83e` (`format: both`): returned `report.contract.v1` +
> HTML — **Executive** `overall_stage: recommended`, `combined_score: 70`, advisory
> `recommended_verdict: INCONCLUSIVE` + `decision: pending` + `advisory: true` + the
> one-paragraph summary; **Security** `data_status: available`, 1 finding + 1 gap, MITRE +
> Sigma `not_carried_on_hub`; **Developer** `data_status: available`, 2 prioritized
> remediations (`ranks: [1, 2]`) + 1 candidate FP, file-line `not_carried_on_hub`; HTML 8732
> chars. No effective-verdict key; READ-only proven (the tracking item carried only
> Phase-1→3 attributes — no `report_*` field written); clean 404 on a non-existent intake.
> **LIVE FIX (fix-then-validate-once):** the first invoke returned `remediations: 0` because
> `hub_report` read the item via `boto3.resource`, which deserializes a DynamoDB Number to a
> `Decimal`; `_remediation_view`'s strict `isinstance(int)` guard on `rank` rejected every
> row. Fixed on the branch (PR #137, merge `5d7fa96`) by adding a `_rank()` coercion
> (accepts `Decimal`/`int`, bounds 1..100) + a regression test; redeployed and re-validated —
> `remediations: 2`, `ranks: [1, 2]`.
>
> _Prior entry (cleared 2026-09-13):_ **Story 4.3** (real-time dashboard render, RD-043) was
> cleared by its own recorded live validation in the Hub 641628980935. `ZtieDashboardStack`
> deployed (private S3 + CloudFront OAC static dark-theme SPA + an IAM-auth API Gateway
> fronting the UNCHANGED 4.2 `hub_dashboard` Lambda; the stack added NO Lambda of its own —
> only the CDK `BucketDeployment` helper). `GET /dashboard` returned the fleet payload
> (`view: fleet`, 5 rows for `limit=5`, `truncated: true`, `by_stage` summing to 5, 3
> INCONCLUSIVE + 2 none, 5 high, AMI/sensor/cost `not_wired`); `GET /status/891cb78f-…`
> returned the per-intake payload (the 4.1 read-model reused verbatim — `overall_stage:
> recommended`, scores 50/30/70, `findings_summary` assessed — + `threat.tier: high` from
> combined 70 + an `action` block with `recommended_verdict: INCONCLUSIVE`, `decision:
> pending`, `advisory: true`); the no-effective-verdict-key scan returned OK on both
> payloads; a non-existent intake returned a clean `{"error":{"code":404}}`; and the
> CloudFront URL rendered the dark-theme SPA (advisory banner, graduated `threat_tier`
> coloring, disabled Approve/Reject control surface). **LIVE FIX (fix-then-validate-once):**
> the initial deploy used a `proxy: true` API Gateway integration, which 502'd ("Malformed
> Lambda proxy response") because the 4.2 Lambda returns a bare payload, not a proxy
> envelope; fixed on the branch (commit `8058301`) by switching both GET methods to a
> NON-PROXY integration with a request template + pass-through/error-code response mapping
> (the 4.2 Lambda stayed UNCHANGED), redeployed, and re-validated clean.
>
> _Prior entry (cleared 2026-09-13):_ **Story 4.2** (dashboard JSON payload, RD-042) was
> cleared by its own recorded live validation in the Hub 641628980935. Intake
> `891cb78f-fd35-4045-81d6-030d75d9c83e` (a small S3 CloudFormation template routed to both
> lanes) ran the pipeline end-to-end (all five Phase-3 fields landed). The PURE, READ-only
> `hub_dashboard` orchestrator (verified live: env has `DASHBOARD_CONTRACT_VERSION: 1.0` +
> `STATUS_CONTRACT_VERSION: 1.0` + `TRACKING_TABLE` + `LOG_LEVEL` and NO `NOVA_MODEL_ID`;
> role has only READ `dynamodb:*` and NO `UpdateItem`/`PutItem`/`DeleteItem` and NO
> `bedrock:InvokeModel`) assembled `dashboard.contract.v1` in both views: `view=intake`
> reused the 4.1 read-model verbatim + a display `threat.tier: high` (combined 70) + an
> `action` block (advisory `recommended_verdict: INCONCLUSIVE`, `decision: pending`,
> `advisory: true`); `view=fleet` returned 10 GSI-paged newest-first rows (`truncated: true`,
> no scan) with metrics (`by_stage`/`by_recommended_verdict`/`by_threat_tier` all consistent;
> `ami_build_health`/`sensor_status`/`cost` = `not_wired`). READ-only proven (the tracking
> item carried only Phase-1→3 attributes; no `dashboard_*`/`threat_*` field written); no
> effective-verdict key in either payload.
>
> _Prior entry (cleared 2026-09-13):_ **Story 4.1** (status-retrieval orchestrator, RD-041)
> was cleared by its own recorded live validation in the Hub 641628980935. Intake
> `384d63ef-7577-4787-ba0e-cc5d92305ff9` (a small S3 CloudFormation template routed to both
> lanes) ran the pipeline end-to-end (all five Phase-3 fields landed); invoking the PURE,
> READ-only `hub_status` orchestrator (verified live: env has `STATUS_CONTRACT_VERSION: 1.0`
> + `TRACKING_TABLE` + `LOG_LEVEL` and NO `NOVA_MODEL_ID`; role has only READ `dynamodb:*`
> and NO `dynamodb:UpdateItem`/`PutItem`/`DeleteItem` and NO `bedrock:InvokeModel`) returned
> the assembled status read-model (`status.contract.v1`, `contract_version 1.0`): identity +
> `overall_stage: recommended` + all `stages` `present` (incl. `verdict_recommendation`) +
> the three 3.3 scores echoed as context (static 55 / dynamic 30 / combined 70, never
> re-blended) + a bounded `findings_summary` (status `assessed`, 1 finding / 1 candidate-FP /
> 1 gap / 2 remediations, `highest_gap_severity: high`, `contradiction_present: false`) + a
> `recommendation` block surfacing the 3.5 `recommended_verdict: INCONCLUSIVE` (combined 70,
> RD-040 band 30-74) ADVISORY with `decision: pending` + `advisory: true`. READ-only proven:
> the invoke wrote NOTHING to the item (identical key set before/after; no `status_result`
> field). No bare effective-verdict key in the view (only the advisory `recommended_verdict`).
> Error paths clean: a non-existent UUID returned `{"error":{"code":404}}` and a malformed id
> returned `{"error":{"code":400}}`.
>
> _Earlier entry (cleared 2026-09-13):_ **Story 3.5** (advisory `recommended_verdict`,
> RD-040) was cleared by its own recorded live validation in the Hub 641628980935. Intake
> `0c74042e-6976-4fdf-a39c-7599f9733921` (a small S3 CloudFormation template routed to both
> lanes) ran the pipeline end-to-end; the PURE `hub_verdict` Lambda (no model call, verified
> live: env has `VERDICT_CONTRACT_VERSION: 1.0` + `TRACKING_TABLE` + `LOG_LEVEL` and NO
> `NOVA_MODEL_ID`; role has only `dynamodb:*` and NO `bedrock:InvokeModel`) recorded a
> bounded advisory `verdict_result` (`status: recommended`, `contract_version: 1.0`,
> `rubric_version: 1.0`) over the three real 3.3 scores static/dynamic/combined = 55/30/70.
> **`recommended_verdict: INCONCLUSIVE`**, driven by the `combined` score 70 (RD-040 band
> 30-74 → INCONCLUSIVE; `driver: combined_score`; `contradiction_present: false`;
> `evidence_complete: true`) — a genuine score-band INCONCLUSIVE, NOT a re-aggregation
> (static 55 / dynamic 30 echoed as context only). A `highest_gap_severity: high` was noted
> but did NOT force a FAIL (the summary: "a reason for a human look, never an auto-FAIL") —
> the RD-040 rule proven live. **`human_decision: pending`** (3.5 wrote no human selection);
> the summary explicitly frames it "ADVISORY ONLY and is NEVER acted upon automatically; a
> human must actively select PASS or FAIL at the dashboard gate." The item carried all five
> Phase-3 stages (`combined_event` / `correlation_result` / `scoring_result` /
> `remediation_result` / `verdict_result`), so the full intake→lanes→3.1→3.2→3.3→3.4→3.5
> flow ran green (end-to-end pipeline proof). The log proved the guard: several
> `has no scoring_result yet; skipping` while 3.3 landed, then `verdict recorded
> (status=recommended, recommended_verdict=INCONCLUSIVE, human_decision=pending)` followed
> by `already recommended for this evidence fingerprint; no-op (guard)` and NO further
> writes — settled, no stream loop. (Note: two near-simultaneous `verdict recorded` lines
> fired ~0.3s apart from an in-flight stream race before the fingerprint guard engaged;
> both wrote the IDENTICAL result — same fingerprint `563fdd4d…`, same INCONCLUSIVE — so it
> is idempotent-in-effect and self-corrected, not a loop; the guard has held since.)
>
> _Prior entry (cleared 2026-09-13):_ **Story 3.4** (detailed findings + prioritized
> remediations, RD-039) was cleared by its own recorded live validation in the Hub
> 641628980935. Intake `cc058fed-0b0e-4858-8d60-933755f23092` (a small S3 CloudFormation
> template routed to both lanes) ran the pipeline end-to-end; the PURE `hub_remediate`
> Lambda (no model call) recorded a bounded, verdict-free `remediation_result`
> (`status: assessed`, `contract_version: 1.0`, `rubric_version: 1.0`) over the three real
> 3.3 scores (static `scored`/50, dynamic `scored`/30, combined `scored`/55;
> `highest_score: 55` combined) + the 3.2 correlation: 1 detailed finding (the `static_only`
> flag surfaced), 1 candidate false positive (the migrated list), 1 gap
> (`static_uncorroborated`), and 2 prioritized remediations (`rank` 1-2, `priority: high`,
> `basis` citing "highest risk score 55 (combined); source severity high"). No-verdict grep
> over the whole item was clean (`NO verdict-shaped key present`); the remediation `action`
> strings are "confirm/review/remediate," never "reject/forward." The 3.4 log proved the
> guard: several `has no scoring_result yet; skipping` while 3.3 landed, then exactly ONE
> `remediation recorded (status=assessed, findings=1, gaps=1, remediations=2)`, then
> `already assessed for this evidence fingerprint; no-op (guard)` — no stream loop. The
> item carried all Phase-3 stages (`combined_event`/`correlation_result`/`scoring_result`/
> `remediation_result`), so the OD-001/OD-002 ~20-stack cleanup did NOT break the pipeline
> (the regression proof). Live Lambda verified PURE: env has `REMEDIATION_CONTRACT_VERSION`
> + `TRACKING_TABLE` + `LOG_LEVEL` and NO `NOVA_MODEL_ID`; the role has only `dynamodb:*`
> actions and NO `bedrock:InvokeModel`.
>
> _Prior entry (cleared 2026-09-12):_ **Story 3.3** (three Nova Pro risk scores, RD-038)
> was cleared by its own recorded live validation in the Hub 641628980935. Intake
> `217b909b-87b7-4b64-9dbf-201f670c8a8f` (a small S3 CloudFormation template, routed to both
> lanes): the pipeline ran end-to-end and 3.1 built a `complete` combined event
> (`inputs_present=[static,dynamic,sanitized]`). The reworked scorer made THREE REAL Amazon
> Nova Pro calls (`us.amazon.nova-pro-v1:0`) recording a bounded, verdict-free
> `scoring_result` with three independent 0-100 risk scores on the shared rubric
> (`rubric_version:1.0`): **static `scored`/55**, **dynamic `scored`/30**, **combined
> `scored`/55**. The combined score is its OWN cross-lane assessment (not an average — its
> rationale explicitly weighed "high static … dynamic execution error with no behavioral
> events … high but not critical overall risk"). The only no-verdict-grep hit was the word
> "malicious" INSIDE the model's rationale prose — there is NO verdict/safe/approved/forward
> field on the record (a score is EVIDENCE, not a decision; the verdict stays human-gated,
> 3.5). The scorer log proved the call-storm guard: ONE `scoring recorded (static=scored/55,
> dynamic=scored/30, combined=scored/55)` then `already scored for this evidence
> fingerprint; no-op (guard)` on the subsequent stream events (no loop, no repeated paid
> calls). Deploy-gap guards passed (live Lambda env `SCORING_CONTRACT_VERSION`/`NOVA_MODEL_ID`/
> `NOVA_MAX_ATTEMPTS`/`SCORE_ONLY_WHEN_COMPLETE` present; scoped `InvokeNovaProForScoring`
> Bedrock grant, no `*`).
>
> _Prior entry (cleared 2026-09-12):_ **Story 3.2** (Nova Pro correlation engine, RD-035)
> was cleared by its own recorded live validation in the Hub 641628980935. Intake
> `6145dc20-763c-4fc8-ade8-822685c44343` (a small CloudFormation template, routed to both
> lanes): the pipeline ran end-to-end (static `high`, dynamic `execution_error`, sanitized
> `sanitized`), 3.1 built a `complete` combined event, and the correlator made ONE REAL
> Amazon Nova Pro call (`us.amazon.nova-pro-v1:0`, `attempts:1`, `latency_ms:1052`,
> input/output tokens `423`/`106`) recording a bounded, verdict-free `correlation_result`:
> `status:correlated`, one finding `kind:static_only` / `severity:high` ("High severity
> static findings with no dynamic correlation") — the model correctly reasoned that the
> high static finding had NO dynamic correlation because the detonation errored (honest,
> not fabricated). The no-verdict grep over the whole item returned clean. The correlator
> logs showed the gate + guard working exactly: `no correlatable signals; skip` →
> `not complete yet; deferring` → `correlation recorded (status=correlated, attempts=1,
> findings=1)` → `already correlated … no-op (guard)` (ONE model call for the settled
> combined event, no call storm / stream loop). Deploy-gap guards passed (live Lambda env
> pins present; scoped `InvokeNovaProOnly` Bedrock policy, no `*`).
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

> **Dependency wiring (up/down) is shown in-your-face.** Each OD row now carries a
> **`Depends on`** column (UP — what must be true/done before this debt can be actioned)
> and a **`Feeds`** column (DOWN — what consumes this debt's resolution / what is affected
> while it rides). This makes the register read as a set of tracked sub-processes with
> explicit up/down edges, the same way stories carry `Depends on` and decisions carry an
> RD id. (`check_docs.py` parses this table by the column NAMES `ID` / `Debt` / `Next
> action`, so the added `Depends on` + `Feeds` columns are safe.)

| ID | Depends on (UP) | Debt (what is riding) | Feeds (DOWN) | Next action | Owner | Opened |
|----|-----------------|-----------------------|--------------|-------------|-------|--------|
| OD-004 | `restore/phase-3-green` @ `e2b325d` + `restore/story-4.5-green` @ `537d61c` pushed (code half done); `scripts/ztie-restore`; live creds in all three accounts | Restore-point **state manifests** for the two new restore tags are NOT yet captured. Per a stakeholder-approved decision these tags were pushed **code-half only**; a by-the-book restore point pairs the tag with a live state manifest (RESTORE.md rule 4). Until captured, the tags are the CODE half; the STATE half is missing, so a coordinated code+state restore to these points is not yet possible. | A coordinated code+state restore to phase-3 / 4.5; `RESTORE.md` rule-4 completeness; the `BOM.md` §4 restore-tag index | Capture the paired manifests with `scripts/ztie-restore` in the Hub (641628980935) + Forensic (360999005254) + Pipeline-Sandbox (586917955591) accounts, commit them under `restore-manifests/`, add the BOM.md rows, and confirm each manifest's pinned `governance_commit.sha` equals its tag's target SHA. | Stakeholder (live capture) → Executor (record) | 2026-09-13 |
| OD-005 | The split-brain validation loop (RD-052/053/054) being actively RUN by the stakeholder; the packages generated from `docs/GEMINI_VALIDATION_PACKAGE_TEMPLATE.md` | **Validation-tooling UX hardening — a tracked sub-process collecting friction points the stakeholder hits while RUNNING the split-brain validation loop and its packages.** These are usability/clarity problems in the *validation instructions/tooling itself*, NOT defects in the code under test, and NOT to be fixed mid-validation (Kiro records them verbatim as a write-only scribe; they are triaged + fixed together later). The individual observations live in the **VUX sub-lane table** directly below (each with its own up/down edges). | A future dedicated **validation-process UX / hardening story** (fixes the whole VUX set at once) → cleaner `GEMINI_VALIDATION_PACKAGE_TEMPLATE.md` + every generated package + the session prompt template | Keep appending `VUX-NNN` rows to the sub-lane below as they occur (do NOT fix during an active validation); when the collection settles, scope + schedule the fix story, then close OD-005 on that story's validation. | Executor (record verbatim) → Stakeholder (schedule the fix story) | 2026-09-16 |
| OD-007 | The `lambdas/detonation` capture wrapper (`capturespec.build_capture_run_commands` + `build_trace_upload_commands`) + the host/SSM `AWS-RunShellScript` runtime shape; PR #200's first wrapper-EXECUTION test (`test_capturespec.py::test_emitted_wrapper_runs_clean_under_set_u_for_instant_artifact`) as the seed pattern | **Host-environment / wrapper smoke-test HARNESS gap — the offline-can't-catch-it class.** FIVE straight 2.4S/2.4R live defects were all shell/host-shape issues the offline bar CANNOT see because it asserts only the command STRING, never executes the wrapper: attempt-2 global-vs-regional S3 endpoint (the best-effort `or-true` guard swallowed the failure silently), attempt-3 `aws` not on the SSM PATH, the `set -u` `__ZTIE_RC` unbound crash (PR #200), and now attempt-4 the direct-upload block writing NEITHER an S3 object NOR any stderr to the diag log (empty `ZTIE-UPLOAD-DIAG` block, an executed-but-inert upload sub-block). Each cost a full live cycle to surface one defect. PR #200 added the FIRST test that actually EXECUTES the emitted wrapper under `sh -u`; there is no general harness. | The attempt-5 (and future) 2.4S fix confidence; the covenant's "live pass of the FINAL code" burden (a harness catches the shell-shape class BEFORE the live gate); future detonation-lane changes | Author a reusable wrapper-execution harness that runs the EMITTED wrapper under `sh -u` with a **stubbed `aws` on PATH** (fake CLI logging its argv + a configurable exit) and asserts the upload block actually FIRES each per-PID `s3 cp` + the `_UPLOAD_COMPLETE` sentinel copy AND that their stderr reaches `/tmp/ztie/upload.stderr`; plus cases for instant / hanging-past-timeout / no-shebang / strace-absent / empty-capture artifacts. Scope + schedule as a dedicated detonation-hardening story; close OD-007 on that story's validation. | Executor (propose harness) → Stakeholder (schedule the hardening story) | 2026-09-23 |
| OD-008 | The Step Functions orchestration fork/parallel branch that launches the ephemeral detonation host (`ec2:RunInstances` via launch template); the Forensic detonation lane | **SFN false-green observability gap — the fork/parallel branch reports `SUCCEEDED` even when the host-launch path FAILS (e.g. `RunInstances` errors, as in the OD-006 `MissingParameter … ImageId` case).** A green SFN execution over a failed launch let partial/blocked runs look plausible and made prior sign-offs harder to trust — the exact opposite of fail-closed observability. NOTE: this is a candidate that borders on a code/observability DEFECT (not pure hygiene); it is logged here for VISIBILITY + triage, and may be re-scoped by the stakeholder as a small fix story (which would then enter the Validation Debt Register once built, per the covenant) rather than staying operational debt. | Trustworthy live-validation signals (a green fork must mean the host actually launched); every future detonation-lane live run; reduces reliance on manual raw-evidence cross-checks | Triage with the stakeholder: decide whether to (a) make the fork branch surface a launch failure as a FAILED/caught state (a code fix → own validation) or (b) keep as tracked OD until the detonation lane is next touched. Do NOT fix mid-validation. Close OD-008 when the false-green is eliminated (with a dated evidence note) or when re-scoped into a fix story. | Executor (surface) → Stakeholder (decide fix-story vs. defer) | 2026-09-23 |

#### OD-005 sub-lane — VUX findings (validation-tooling UX)

> The running collection under OD-005, broken out so each observation is a visible,
> individually-tracked item with its own UP (what surfaced it) / DOWN (what it feeds).
> These `VUX-NNN` ids are informational (not machine-gated); OD-005 is the parsed row.

| VUX | Depends on (UP) | Finding (what is riding) | Feeds (DOWN) | Status | Opened |
|-----|-----------------|--------------------------|--------------|--------|--------|
| VUX-001 | Story 2.4R kickoff / Part-A token-fetch step; AWS CloudShell. **Provenance:** the line originates in the repo's OWN validation TEMPLATE `docs/GEMINI_VALIDATION_PACKAGE_TEMPLATE.md` (introduced commit `3dc61ff`, "CloudShell-native diff pull") and was inherited by the 2.4R package — it is NOT Gemini's and NOT authored this session; it is a prior governance-artifact line, so fixing the template fixes it for every future package (repeatable/reusable, RD-015). | The first command `read -rs GH_TOKEN && export GH_TOKEN` *appears to hang* — it is `-s` (silent), so there is NO prompt and NO echo; it is silently waiting for the token to be pasted + Enter. It is NOT broken and must NOT be "fixed" by switching to `export GH_TOKEN="…"` (that echoes the token on screen + into shell history = a secret-leak regression; ties to the standing "a PAT echoed into CloudShell output must be rotated" lesson). Fix = CLARITY at the point of use, applied ONCE in the template so all generated packages inherit it: a visible prompt (`read -rsp "Paste GH token, then press Enter (nothing will show): " GH_TOKEN && export GH_TOKEN && echo`), an inline "this looks like it hangs — it's silently waiting; paste + Enter" note, and a non-echoing confirm (`echo "token length: ${#GH_TOKEN}"`); keep `unset GH_TOKEN`. | The token-fetch snippet in `GEMINI_VALIDATION_PACKAGE_TEMPLATE.md` STEP 1 + STEP 1.5 + Part A, and EVERY generated package (2.4R, 2.2R, and future) | **TEMPLATE FIXED 2026-09-16** — all 5 token-fetch snippets in `GEMINI_VALIDATION_PACKAGE_TEMPLATE.md` now use the silent-prompt form `read -rsp "Paste GH token, then press Enter (nothing will show): " GH_TOKEN && export GH_TOKEN && echo` + a `token length` confirm + `unset` + inline "looks like it hangs" note (also replaced the leak-prone `export GH_TOKEN=<pat>` Part-A form). So every FUTURE generated package inherits the fix (reusable, RD-015). Already-generated packages (2.4R live, 2.2R) still carry the old line and are regenerated/patched when next touched — the live 2.4R package stays frozen for its in-flight run (the stakeholder uses the corrected block out-of-band). | 2026-09-16 |

> **Register status: 4 open (OD-004, OD-005, OD-007, OD-008).** OD-006 (opened + CLOSED 2026-09-22) was the
> Forensic detonation host-launch blocker surfaced by the Story 2.4S attempt-1 live validation
> (launch-template `$Latest` had no `ImageId` because `/ztie/ami/ubuntu-22.04` was empty/stale); it
> is now **CLOSED** — the 2.4S attempt-2 run proved the host launched (AMI republish + stack
> redeploy worked). See the CLOSED note below. OD-004 is the deferred state-manifest
> capture for the two restore tags added 2026-09-13 (`restore/phase-3-green` +
> `restore/story-4.5-green`); the tags are pushed code-half only and the manifests follow.
> OD-005 is the validation-tooling UX **sub-process** (opened 2026-09-16 during the Story
> 2.4R split-brain validation) — its individual `VUX-NNN` findings ride in the sub-lane
> table directly above, each with explicit UP/DOWN dependency edges, so the up/down wiring
> is in-your-face rather than buried in prose; it is deliberately parked in the ONE
> centralized register the executor already surfaces at every STEP 0, so there is no
> separate place to look, and the whole set is resolved in a later dedicated story. An open
> operational-debt entry does NOT arm the advancement gate. OD-001, OD-002, OD-003 are all
> closed 2026-09-12 (see the CLOSED notes below); the RD-032 cost-remediation track is
> complete. **OD-007 (opened 2026-09-23)** is the host-environment / wrapper smoke-test
> HARNESS gap — five straight 2.4S/2.4R live defects were all shell/host-shape issues the
> offline bar cannot see (it asserts only the command string, never executes the wrapper);
> a reusable execution harness (stubbed `aws` on PATH, upload block actually fires) would
> surface that whole class offline instead of one live cycle each. **OD-008 (opened
> 2026-09-23)** is the SFN false-green observability gap — the fork/parallel branch reports
> `SUCCEEDED` even when the host-launch path fails; it borders on a code/observability defect
> and may be re-scoped by the stakeholder as a small fix story (which would then enter the
> Validation Debt Register once built). Both were surfaced during the 2.4S attempt-4 live
> validation; neither arms the advancement gate. New operational debt is added here the
> moment it is knowingly deferred, and surfaced at the start of every session.

> **CLOSED — OD-006 (Forensic detonation host-launch / AMI-drift blocker), resolved
> 2026-09-22** (proven by the Story 2.4S attempt-2 live run — evidence pasted back + recorded,
> never on inference). Opened 2026-09-22 when the 2.4S attempt-1 run failed with
> `RunInstances … MissingParameter … ImageId`: the deployed launch template `lt-045ddce7fdac386db`
> (`$Latest`) in Forensic `360999005254` carried no valid AMI because `/ztie/ami/ubuntu-22.04` was
> empty/stale at the last deploy (the stack CONSUMES that SSM value via
> `MachineImage.fromSsmParameter`; the Image Builder PUBLISHES it). **Remedy applied (stakeholder,
> live):** republished a valid golden AMI to `/ztie/ami/ubuntu-22.04` + `cdk deploy
> ZtieForensicInfraStack` to bake it into a new launch-template version. **Proof of closure:** on
> the 2.4S attempt-2 run the ephemeral host **launched and executed** (the run reached the S3-read /
> stdout-fallback stage — no `launch_error`, no `MissingParameter`), so the AMI/launch foundation is
> sound. This was a deploy-state/drift condition, never a 2.0 CDK code defect. (Note: attempt-2
> itself sealed **FAIL** on a SEPARATE, real 2.4S code defect — the host-side S3 upload targeted the
> global endpoint and failed silently; that is tracked in the Validation Debt Register, not here,
> and is fixed on `fix/story-2.4S-host-regional-s3`.)

> **CLOSED — OD-002 (Forensic stale-lineage teardown, Phase 2 of RD-032), resolved
> 2026-09-12** (live teardown run by the stakeholder in a `[FORENSIC]` 360999005254
> CloudShell; evidence pasted back + recorded here — never on inference). **Import-safety
> check first (in the correct account):** every export of the doomed lineage was `NOT
> IMPORTED` *except* internal cross-references among the lineage's own stacks (Collector +
> Processor import from Ingestion) — nothing OUTSIDE the doomed set (no live ZTIE, no live
> PDE) imported anything, so the whole lineage was safe to remove in dependency order.
> **Torn down + verified `GONE` (8 stacks):** `DeployForensics-ZtieCollector`,
> `DeployForensics-ZtieProcessor`, `DeployForensics-ZtieAnalyzer`,
> `ztie-forensic-inspection`, `ZTIE-Forensics-Dashboard-Stack` (Forensic dashboard is
> off-architecture per RD-008), `aws-sam-cli-managed-default`, `Forensic-Unified-Baseline`,
> and `DeployForensics-ZtieIngestion` (deleted LAST — it is the exporter the others
> imported). **Plus** the RD-032 Phase-1 orphan `Forensic-Network-Perimeter` stack + its
> VPC `vpc-06334ba0f53a93e39` (`Forensic-Isolated-VPC`, `10.100.0.0/16`) finally torn down
> (`InvalidVpcID.NotFound`). **Excluded / held:** `DeployForensics-ZtieImageBuilder` (NOT
> confirmed dead — could be an AMI-pipeline dependency; left in place pending confirmation,
> per the executor-recommends/stakeholder-decides model). **Safety upheld:** the live ZTIE
> pipeline stacks (`ZtieForensicInfraStack` + its detonation VPC `vpc-0457ce09693cc48e4`,
> `ZtieDetonationStack`, `ZtieStaticScanStack`, `ZtieOrchestrationStack`, `ZtieIntakeStack`,
> `CDKToolkit`), the PDE `StackSet-PDE-CrossAccount-Deployer-*` instance, and the AWS
> default VPC (`vpc-0e2d555877bc5734a`, `172.31.0.0/16`) were all confirmed present and left
> untouched. **One resource intentionally RETAINED — `forensic-evidence-data-360999005254-us-east-1`:**
> this S3 bucket (owned by `Forensic-Unified-Baseline`) has **S3 Object Lock in COMPLIANCE
> mode, 365-day default retention** (~607 object versions) — COMPLIANCE-mode WORM cannot be
> deleted by anyone (not even root) until each object's retention lapses, so the Baseline
> stack was deleted with `--retain-resources ForensicEvidenceBucket` (drop the stack, orphan
> the locked bucket to age out). **Delete-time unblocks (recorded, no unsafe hand-deletes):**
> several stacks hit `DELETE_FAILED` on non-empty S3 buckets (emptied all versions +
> delete-markers, retried); `DeployForensics-ZtieIngestion` failed on a `Custom::S3BucketNotifications`
> resource whose target bucket was already gone (`NoSuchBucket`) — cleared with
> `delete-stack --retain-resources`; the orphan VPC's final blocker was a lingering
> non-default security group (`sg-0b0d6f1970e1b70b3`, a circular-reference leftover) — its
> rules were revoked and the SG deleted, after which the VPC + stack deleted cleanly. **Watch-item recorded:**
> the stakeholder confirmed a 365-day COMPLIANCE lock is NOT desired for ZTIE forensic data
> going forward — a design check of the CURRENT pipeline's Forensic buckets (that they do not
> silently apply COMPLIANCE-mode Object Lock) is tracked separately; the existing locked
> bucket cannot be shortened (COMPLIANCE forbids it) and will age out. Playbook:
> [`docs/session-briefs/cost-cleanup-phase2-PROMPT.md`](docs/session-briefs/cost-cleanup-phase2-PROMPT.md);
> close-out package: [`docs/session-briefs/close-out-G1-OD001-OD002.md`](docs/session-briefs/close-out-G1-OD001-OD002.md).

> **CLOSED — OD-001 (Hub stale-stack cleanup, Phase 2 of RD-032), resolved 2026-09-12**
> (live teardown run by the stakeholder in a `[HUB]` 641628980935 CloudShell; evidence
> pasted back + recorded here — never on inference). **12 confirmed-stale Hub stacks
> (13 incl. the nested IAM child) deleted, all verified `GONE`:**
> `ztie-detonation-chamber-production` (+ nested
> `ztie-detonation-chamber-production-IAMRolesStack-ST8ZNAS04F0D`),
> `aws-sam-cli-managed-default`, `ztie-hub-frontend-stack`, `ztie-hub-backend-stack`,
> `ztie-hub-cognito-stack`, `ztie-dev-identity`, `ztie-dev-hosting`, `ztie-dev-waf-shield`,
> `PipelineStack`, `ZTIE-Pipeline-Stack`, `ZTIE-CrossAccount-Pipeline`,
> `ZTIE-IAM-Deployment-Stack`. **Safety upheld:** `ztie-asymmetric-cmk` (live KMS
> attestation key) and every `PDE-*`/`pde-*` stack were confirmed present and left
> untouched; `whr-bucket-website-stack` (non-ZTIE/non-PDE) was excluded pending owner
> confirmation. **Pre-delete checks:** all 12 stacks confirmed `NOT IMPORTED` / export
> nothing (no live consumer), and the four pipeline stacks were confirmed months-stale
> (last updated 2026-07-26…08-15, no recent pipeline execution). **Delete-time
> unblocks (recorded):** three stacks first hit `DELETE_FAILED` and were cleared without
> hand-deleting infra — `aws-sam-cli-managed-default` + `ztie-hub-frontend-stack` had
> non-empty (versioned) S3 buckets (emptied all versions + delete-markers, then a clean
> `delete-stack` retry → `GONE`); `ztie-dev-waf-shield` held a CLOUDFRONT-scope WAFv2
> WebACL (`ztie-dev-global-shield-acl`) whose CloudFront association had already cleared
> once `ztie-dev-hosting` was gone (0 distributions referenced it), so a `delete-stack`
> retry succeeded. The nested detonation IAM child was removed by deleting its parent (not
> by name). Playbook: [`docs/session-briefs/cost-cleanup-phase2-PROMPT.md`](docs/session-briefs/cost-cleanup-phase2-PROMPT.md);
> close-out package: [`docs/session-briefs/close-out-G1-OD001-OD002.md`](docs/session-briefs/close-out-G1-OD001-OD002.md).

> **CLOSED — OD-003 (Node>=22 / CDK version bump + deprecated-API migration), resolved
> 2026-09-12 (PR #105 merged; deploy runbook [`docs/session-briefs/OD-003-LIVE-RUNBOOK.md`](docs/session-briefs/OD-003-LIVE-RUNBOOK.md)).**
> Toolchain bumped (`aws-cdk` `^2.1141.0`, `aws-cdk-lib` `^2.265.0`, `@types/node` `^22`)
> and both deprecated CDK APIs migrated (`pointInTimeRecovery` ->
> `pointInTimeRecoverySpecification`; `logRetention` -> explicit `logs.LogGroup`) across
> every Lambda in all five deployed stacks + the Hub tracking table. **Live-verified in
> both accounts on Node v22.23.2 (2026-09-12):** all five stacks (`ZtieHubTrackingStack`
> [Hub], `ZtieIntakeStack`, `ZtieStaticScanStack`, `ZtieDetonationStack`,
> `ZtieOrchestrationStack` [Forensic]) `cdk deploy`'d with **log-groups-only diffs** (each
> retired its old `Custom::LogRetention` and created explicit `AWS::Logs::LogGroup`
> resources; no code/env/IAM/state-machine/image drift). Confirmed live: **9 new log
> groups all at `retentionInDays = 30`**; Hub tracking table PITR still `ENABLED` (table
> not replaced); orchestration state-machine ARN + detonation `iam:PassRole` (instance
> role) unchanged. A smoke intake (`intake_id 8fc58de9-22d3-4a9a-9fa7-824ec4c6cf3d`)
> produced fresh log streams in the new intake + preprocessor log groups, proving logs
> flow through the migrated `logGroup` config. Closes issue #88.

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

**How every validation is framed (BINDING — split-brain, RD-052 + RD-053 + RD-055).**
There is one standing validation mechanism for **every** 🟡→✅ transition; it is not
authored per-story and it does not depend on a story-specific live-runbook document.
The party that BUILT the code (the executor) does **not** author the pass/fail rubric,
the live runbook, curate what the validator sees, or interpret the live results.
**RD-055 (zero-trust validation supply chain, BINDING):** the executor's handoff for a
live validation is the **Pull Request number ONLY** — the executor is **forbidden** from
providing the raw diff, any diff-fetch command, code snippets, or a changed-file list,
and **forbidden** from authoring the live runbook, test scripts, or any live-proof steps.
The Independent Validator (Gemini) authors the runbook + DoD **from scratch, blind** to
the builder's assumptions. If the diff or the requirement ever reached the validator via
the executor, the pass is **VOID** and must be re-sourced by the stakeholder. Instead:

1. The **stakeholder** fetches the **raw diff** **independently, directly from the
   repository API** (their own tool/command — the executor supplies none) and states
   the requirement in their **own plain words** — the two judgment inputs, neither
   authored nor supplied by the builder.
2. An **independent validator brain** (the Planner — e.g. Gemini — which did not
   write the implementation) authors an **adversarial review + its own Definition
   of Done + a numbered, soup-to-nuts live runbook** whose pass/fail is visible in
   the **literal command output**, tasked to try to **break** the change.
3. The **stakeholder runs it on the real system and reads the raw output** — the
   verdict is theirs, not narrated by an AI. **Real AWS is the grader.**
4. The independent validator (Gemini) receives the **raw live output** back from the
   stakeholder and **adjudicates the verdict** (PASS / FAIL / INCONCLUSIVE). Only on
   an explicit **PASS** does the **executor transcribe the sealed verdict + raw
   evidence verbatim** and flip status. The executor is a **write-only scribe here**:
   it never re-judges, upgrades an INCONCLUSIVE, or infers a pass (on a fail/incomplete
   it stays 🟡 — fix-then-validate-once).

The single reusable handoff for this is
[`docs/GEMINI_VALIDATION_PACKAGE_TEMPLATE.md`](docs/GEMINI_VALIDATION_PACKAGE_TEMPLATE.md)
— the stakeholder fills it in and pastes it to the validator. **This is the default
and only path to a ✅**; a story does not need (and should not rely on) its own
`*-LIVE-RUNBOOK.md` — the validator authors the live steps each time from the raw
diff.

**One protocol; only the degree varies.** Every check here is a validation — there
is no "real validation" vs. "lesser check". A light doc confirmation and a live
security-boundary detonation run the *same* split-brain loop through the *same*
package; only the DEGREE (DoD + evidence depth) scales with what the story governs
(a security boundary → positive live exercise + retained evidence, below). The
package's **cold-start kickoff block** (the self-contained prompt pasted into a fresh
validator chat) is a required, standard artifact of every validation — never
reconstructed ad hoc. (METHODOLOGY §4a.)

**Two hard rules (RD-053 — do not waive).**
- **(a) Security-boundary positive-exercise.** For a story governing a security
  control (secret detection/redaction, the RD-013 Forensic→Hub crossing, RD-048/049
  auth/signing, artifact destroy/handoff), the live run **must positively trip the
  boundary**. A negative / allowlisted / empty result — e.g. a scanner reporting
  `count: 0` on a planted payload — is **strictly INCONCLUSIVE, never PASS.** Offline
  tests may support but never substitute for the live positive exercise.
- **(b) Redaction standard.** Redaction is proven **only** by a human reading the
  **raw JSON record** (sensitive value excised, finding metadata persists) — never by
  a summary tag such as `REDACTED-OK`.

**Transport constraint.** Gemini cannot reach the repo or AWS; the raw diff + raw
output travel to it **through the stakeholder** (pulled/pasted by them). The executor
may help the stakeholder OBTAIN the raw diff but must never curate/frame what the
validator sees; if the diff or requirement reached the validator via the executor,
the pass is **provisional** until re-sourced. (Full principle + limits:
`METHODOLOGY.md` §4a–4b, RD-052 + RD-053.)

**Evidence-capture — trust the artifact, not the word (RD-054, do not waive).** A
✅ on a **security-boundary** story rests on **retained raw artifacts, never on any
party's testimony — including the independent validator's.** Independence removes
builder bias; it does not make Gemini an oracle (it only ever sees what is pasted to
it and has no first-hand view of the live system). A security-boundary story may not
flip ✅ unless a durable folder `docs/validation-evidence/<story-id>/` is committed
**with the status flip**, containing: (1) the **raw positive-exercise output** (e.g.
findings JSON with `gitleaks count ≥ 1`), (2) a re-runnable **proof-of-absence** (the
planted secret value returns zero matches in the record), (3) a **named, dated human
attestation** of the raw-record read, and (4) **provenance pins** (`intake_id` +
commit SHA). Capture at validation time — Forensic is ephemeral (RD-012), so a
missing record is a finding, not a pass. This makes the pass **auditable** (not
bulletproof — a sample proves presence, not absence of all defects). Machine-enforced
by [`scripts/check_docs.py`](scripts/check_docs.py). (Full principle: `METHODOLOGY.md`
§4c, RD-054.)

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

**The paired-commit convention.** Work and status are **separate commits**, with the
**split-brain validation (RD-052)** sitting between them:
- **Commit A — the work.** Build the story, push to a branch, open a PR. The story
  **stays 🟡** — merging code does not make it done.
- **Between A and B — independent validation (RD-052, not optional).** The
  stakeholder pulls the raw diff and runs the split-brain loop via
  [`docs/GEMINI_VALIDATION_PACKAGE_TEMPLATE.md`](docs/GEMINI_VALIDATION_PACKAGE_TEMPLATE.md):
  an independent validator brain authors the DoD + live runbook, the stakeholder
  runs it on the real system and reads the raw output. The executor does not author
  or interpret that check. (See the Validation & Advancement Gate above.)
- **Commit B — the status flip.** Only after the stakeholder confirms a **live pass**
  from that raw output, make a **small, dedicated commit** that touches the runbook
  (and, at a phase close, the inventory + tag). Status flips ride small, fast-merging
  PRs so the ledger on the main line never lies. If a flip and the main line
  disagree, the main line wins — reconcile by merging the recorded flip.

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

> **The master story table now lives at the TOP of this runbook** (right after the
> intro) so the single pane of glass is the first thing you see. The scheduling /
> readiness / phase-gate context for it stays in this section below.

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
> [`docs/governance/WORK_LOG.md`](docs/governance/WORK_LOG.md) before starting.

**A. Ready now (all dependencies ✅) — schedulable this session, in tier order:**

| Tier | Track | Story | Why it is next / what it unblocks |
|------|-------|-------|-----------------------------------|
| 0 | gov | ~~**G-3**~~ | ✅ **Closed 2026-09-12** — the advancement-gate checker itself (register + gate + decoupling, now extended with CHECK C) is validation-closed on its own `test_check_docs` pass; the gate machinery is no longer itself unvalidated. No longer schedulable. |
| 0 | gov | ~~G-1~~ | ✅ **Closed 2026-09-12 (RD-014).** The `docs/COMPLIANCE.md` matrix was finished (candidate mapping for every RD-001…RD-038, every non-functional constraint, and the built pipeline's stories — 59 rows) AND **ratified**: the accountable party (repo owner `warrenrutledge64`) reviewed + accepted all 8 artifact groups (all 59 rows → `Ratified`, dated + attributed) on 2026-09-12. ZTIE now claims control-coverage traceability for the ratified mappings (not a "ZTIE is compliant" self-assertion). New artifacts still enter `Proposed` at authoring time (RD-014). No longer schedulable. |
| 0 | gov | ~~G-2~~ | ✅ **Closed 2026-09-12 (RD-015)** — extended `check_docs.py` with the integrity + doc-drift checks (CHECK D–J), converted README/BUILD_ORDER's duplicated status surfaces to pointers + a machine-verified generated region, and documented the reusable-OS/instance boundary. No longer schedulable. |
| 5 | tenancy | ~~T.1~~ | ✅ **Closed 2026-09-13 (RD-028 ratified)** — multi-tenancy design spike validated by stakeholder review: `docs/architecture/MULTI_TENANCY.md` captures both isolation boundaries (per-subscriber Forensic account = hard; within-subscriber shared-trust) + rejected alternatives + subscriber-id model + Hub per-subscriber partitioning + Phase-4 per-subscriber org-shared dashboard + migration path from the single shared Forensic account; RD-028 ratified by the accountable party (PR #123). Unblocks T.2. No longer schedulable. |
| 6 | F&H | ~~C.3~~ | ✅ **Closed 2026-09-12 (RD-034)** — collapsed the 10 contract generators into one shared writer + the 8 Hub-gate kind trios into one data-driven registry, byte-identical/behaviour-preserving; `awsio` kept per-lane by design (bundling). No longer schedulable. |
| 4 | pipe | ~~2.2G~~ | ✅ **Closed 2026-09-15 (RD-050)** — Gitleaks integration in the static lane validated live via the split-brain package (RD-052), intake `1797dcfb-…`: DoD verdict Option (b) wiring/supersession — `SUMMARY_CONTRACT_VERSION=1.2` pinned live on both the Hub ingest validator + the Forensic static-scan function, findings normalized at `contract_version 1.2` with tools `['bandit','checkov','gitleaks','signature-scan']`, the bounded Hub summary attached without quarantine (Hub-first redeploy proven), compiled `gitleaks v8.30.1` embedded and invoked non-executing. `gitleaks count: 0` expected (doc-placeholder allowlist); detection proven offline (`test_normalize.py`). Secret-redaction boundary (RD-009) human-signed-off (`REDACTED-OK`). No longer schedulable. |
| 6 | F&H | B.1 | Harvest inventory (docs). Unblocks the C.1→C.5 archive chain. **Sequenced AFTER 4.1** per the stakeholder reorder recorded 2026-09-13 in `docs/governance/WORK_LOG.md` (4.1 first, then B.1); 4.1 is now ✅, so B.1 is schedulable (gate OPEN, register empty). |
| 9 | pipe | ~~**3.2**~~ | ✅ **Closed 2026-09-12 (RD-035)** — Nova Pro correlation validated live (intake `6145dc20-…`: one real Nova Pro call, bounded verdict-free `correlation_result`, gate+guard proven). No longer schedulable. |
| 10 | pipe | ~~**3.3**~~ | ✅ **Closed 2026-09-12 (RD-038)** — three Nova Pro risk scores validated live (intake `217b909b-…`: three real Nova Pro calls, static/dynamic/combined = 55/30/55 on the shared rubric, verdict-free, call-storm guard proven). No longer schedulable. |
| 11 | pipe | ~~**3.4**~~ | ✅ **Closed 2026-09-13 (RD-039)** — detailed findings + prioritized remediations validated live (intake `cc058fed-…`: PURE Hub-side `remediation_result`, `status: assessed`, over the three real scores static/dynamic/combined = 50/30/55, 1 finding + 1 candidate-FP + 1 gap + 2 ranked remediations, verdict-free, assessed once/guard proven, full pipeline green post-cleanup). No longer schedulable. |
| 12 | pipe | ~~**3.5**~~ | ✅ **Closed 2026-09-13 (RD-040)** — advisory `recommended_verdict` validated live (intake `0c74042e-…`: PURE Hub-side `hub_verdict`, no model call, `status: recommended`, over the three real scores static/dynamic/combined = 55/30/70; **`recommended_verdict: INCONCLUSIVE`** driven by the `combined` score 70 (band 30-74; NOT a re-aggregation — static/dynamic echoed as context), `human_decision: pending`, a high-severity gap noted but NOT auto-FAIL; all five Phase-3 stages present, recommended once/guard proven; the 3.1-3.4 records stay verdict-free). **This CLOSES Phase 3.** No longer schedulable. |
| 13 | pipe | ~~**4.1**~~ | ✅ **Closed 2026-09-13 (RD-041)** — status-retrieval orchestrator validated live (intake `384d63ef-…`: the PURE, READ-only `hub_status` orchestrator returned the assembled per-intake status read-model — `overall_stage: recommended`, all stages present, the three 3.3 scores echoed as context 55/30/70, a bounded `findings_summary`, and the 3.5 `recommended_verdict: INCONCLUSIVE` surfaced ADVISORY with `decision: pending` + `advisory: true`; wrote nothing to the item; no effective-verdict key; 404/400 error paths clean). Opened Phase 4; unblocks 4.2. No longer schedulable. |
| 14 | pipe | ~~**4.2**~~ | ✅ **Closed 2026-09-13 (RD-042)** — dashboard JSON payload validated live (intake `891cb78f-…`: the PURE, READ-only `hub_dashboard` orchestrator returned `dashboard.contract.v1` in both views — `view=intake` = the 4.1 read-model reused verbatim + a display `threat.tier: high` (combined 70) + an `action` block with the advisory `recommended_verdict: INCONCLUSIVE`, `decision: pending`, `advisory: true`; `view=fleet` = 10 GSI-paged newest-first rows, `truncated: true`, no scan, with consistent metrics + AMI/sensor/cost `not_wired`). READ-only proven; no effective-verdict key. Unblocks 4.3. No longer schedulable. |
| 15 | pipe | ~~**4.3**~~ | ✅ **Closed 2026-09-13 (RD-043)** — real-time dashboard render validated live: `ZtieDashboardStack` deployed (private S3 + CloudFront OAC dark-theme SPA + IAM-auth API Gateway fronting the UNCHANGED 4.2 `hub_dashboard` Lambda), `GET /dashboard` + `GET /status/{intake_id}` returned the fleet + per-intake payloads correctly (advisory `recommended_verdict` + `decision: pending`, no effective-verdict key, 404 clean), and the CloudFront URL rendered the dark theme + graduated `threat_tier` coloring + the disabled Approve/Reject surface. A live proxy-integration defect was fixed (non-proxy integration, commit `8058301`) + re-validated. Unblocks 4.4. No longer schedulable. |
| 14 | pipe | ~~**4.5**~~ | ✅ **Closed 2026-09-13 (RD-045)** — per-execution tiered report validated live (intake `891cb78f-…`: the PURE, READ-only `hub_report` orchestrator returned `report.contract.v1` + HTML — Executive `recommended`/combined 70/advisory `INCONCLUSIVE`+`decision: pending`; Security 1 finding+1 gap + MITRE/Sigma `not_carried_on_hub`; Developer 2 remediations `ranks:[1,2]`+1 candidate FP + file-line `not_carried_on_hub`; no effective-verdict key; READ-only proven; clean 404). A live Decimal-vs-int `rank` defect (`remediations: 0`) was fixed (`_rank` coercion, PR #137) + re-validated. Unblocks 4.9. No longer schedulable. |
| 14 | pipe | ~~**4.6**~~ | ✅ **Closed 2026-09-14 (RD-047, reworked per RD-048/RD-049)** — ACCEPT-push validated live across the three accounts (Hub signs a `decision.token.v1`; the Forensic pusher verifies it OFFLINE — role has NO `dynamodb`, env has NO `TRACKING_TABLE` — then pushes the hash-verified artifact to the Sandbox landing bucket 586917955591; it landed sha-matched; fail-closed 5/5; a bounded verdict-free `handoff` outcome crossed Forensic→Hub with no spoke→Hub read). Two live fixes: base64-PEM context (PR #153) + `ZtieHubTrackingStack` redeploy for the `handoff` ingest kind. No longer schedulable. |
| 4 | pipe | ~~2.2R~~ | ✅ **Closed 2026-09-15 (RD-053)** — remediation of 2.2G validated live under the split-brain protocol, independently adjudicated PASS by the validator (intake `669f5ce7-…`): **positive detection `gitleaks count: 1`** on a non-allowlisted planted secret normalized into `static-findings.contract.v1` v1.2, and the secret value **redacted while the finding persisted — human-verified on the RAW JSON** (RD-009). Supplies the live detection + raw-JSON redaction proof 2.2G's `count: 0` run lacked. No longer schedulable. |
| 8 | pipe | ~~2.4S~~ | ✅ **Closed 2026-09-24 (RD-058)** — Fix B validated live via the split-brain protocol (Gemini, blind), intake `beb6f4b5-…`, on the clean final code `main` `c1e323c` with the ⛔ deploy code-asset gate passing first. The Forensic artifact bucket held `traces/beb6f4b5-…/` with the host's per-PID `behavior.strace.762`/`.763` + the `_UPLOAD_COMPLETE` sentinel (written last), and the Lambda read the trace from S3 and treated the timed-out SSM command with a complete S3 trace as a SUCCESSFUL capture (RD-058 intent). Evidence: `docs/validation-evidence/2.4S/attempt-5/`. No longer schedulable. |
| 7 | pipe | ~~2.4R~~ | ✅ **Closed 2026-09-24 (RD-054, via 2.4S)** — the DYNAMIC-lane (strace) auditable evidence backfill. 2.4S is its RD-058 remediation; on 2.4S's recorded live PASS the retained raw evidence 2.4R was chartered to provide now exists (per-PID strace files + sentinel in Forensic S3, human-verified), so the linked entry cleared together. No longer schedulable. |
| 14 | pipe | **4.7** | ⬜ **READY — gate OPEN (register empty 2026-09-24).** REJECT → destroy artifact + detonation chamber in Forensic; INCONCLUSIVE → hold at approval gate. The tied tier-14 sibling of 4.6; on the critical path to Phase-4 closure (**4.4** depends on 4.3 + 4.7). Verifies a Hub-signed `rejected` token OFFLINE the same way 4.6 verifies `accepted` (H.2 primitive). **This is the next pipe story** now that the 2.4R/2.4S work item is closed. |
| 15 | pipe | 4.9 | Report enrichment (RD-046): widen the RD-013 Forensic→Hub crossing to carry bounded derived MITRE ATT&CK IDs / Sigma rules / file-line so the 4.5 report renders them instead of `not_carried_on_hub`. Dep 4.5 ✅ met (2026-09-13), so it is Ready by dependency. An ENHANCEMENT off 4.5, **NOT on the Phase-4-closure critical path**; sequenced after the tier-14 pipe work. |
| 16 | pipe | 4.8 | Dashboard browser auth (RD-044): Cognito user pool (hosted UI) + identity pool → scoped temp creds SigV4-sign the 4.3 read API; retains IAM auth so the machine/SigV4 path is untouched. Dep 4.3 ✅ met (2026-09-13), so it is Ready by dependency. An OPERATOR-UX ENHANCEMENT off 4.3, **NOT on the Phase-4-closure critical path** (4.4 closes Phase 4); LOWER priority than the pipeline-completing 4.4/4.6/4.7 unless the stakeholder reprioritizes. |

**B. Blocked (waiting on an unmet dependency) — scheduled, will unblock automatically:**

| Tier | Track | Story | Blocked on | Unblocks when |
|------|-------|-------|-----------|---------------|
| 7 | F&H | C.1 | B.1 | B.1 ✅ (archive repo stand-up) |
| 8 | F&H | C.2 | C.1 | C.1 ✅ (parameterized constructs) |
| 9 | F&H | C.4 | C.2 | C.2 ✅ (migrate one stack as proof) |
| 10 | F&H | C.5 | C.4 | C.4 ✅ (record the practice) |
| 16 | pipe | 4.4 | 4.3 + 4.7 | both ✅ (closes Phase 4) |

**C. Deferred (explicit recorded decision — will NOT be scheduled until the trigger):**

| Tier | Track | Story | Deferred until | Reason (recorded) |
|------|-------|-------|----------------|-------------------|
| 6 | tenancy | T.2 | Commercialization phase (after the core pipeline is complete) | Per-subscriber environment vending is only needed to sell multi-tenant; the core single-tenant pipeline must land first. Also structurally blocked on T.1. |
| 7 | tenancy | T.3 | Commercialization phase (after the core pipeline is complete) | Hub-side per-subscriber data isolation / quotas — same commercialization trigger; blocked on T.2. |

> **Default next action:** **Story 4.7 (REJECT → destroy artifact + detonation chamber in
> Forensic; INCONCLUSIVE → hold at the approval gate).** The Validation Debt Register is
> EMPTY and the advancement gate is DISARMED as of 2026-09-24: **Story 2.4S** (Fix B / RD-058)
> was VALIDATED LIVE (split-brain, Gemini blind, intake `beb6f4b5-…`, clean code `main`
> `c1e323c` with the ⛔ deploy code-asset gate passing first — retained evidence
> [`docs/validation-evidence/2.4S/attempt-5/`](docs/validation-evidence/2.4S/attempt-5/EVIDENCE.md)),
> and its linked remediation target **2.4R** cleared with it (one work item — the DYNAMIC-lane
> strace evidence backfill now exists). 4.7 is the first-OPEN pipe story by tier (tied tier-14
> sibling of 4.6): it verifies a Hub-signed `rejected` `decision.token.v1` OFFLINE the same way
> 4.6 verifies `accepted`, and it is on the Phase-4-closure critical path (**4.4** depends on
> 4.3 + 4.7). Its refreshed handoff is at
> [`docs/session-briefs/story-4.7-PROMPT.md`](docs/session-briefs/story-4.7-PROMPT.md) +
> [`docs/session-briefs/story-4.7-brief.md`](docs/session-briefs/story-4.7-brief.md). After 4.7,
> **4.4** (tier 16) closes Phase 4; **B.1** (F&H, tier 6), **4.9** (tier 15), **4.8** (tier 16)
> follow per the recorded reorder.
> **G-1, G-2, G-3, C.3, T.1 are closed ✅;** the C-archive/tenancy tracks remain parked
> (strategy-contingent tracks await their trigger). Everything in bucket B unblocks by
> dependency; everything in bucket C waits for the recorded commercialization trigger.

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
| **G-1** — compliance back-map | ✅ **Closed 2026-09-12 (RD-014).** Matrix finished (59 rows: every RD-001…RD-038 + every non-functional constraint + the built pipeline's stories) AND ratified — the accountable party (`warrenrutledge64`) accepted all 8 groups (all 59 rows → `Ratified`, dated + attributed). `check_docs` PASS + `test_check_docs` OK. | Done. | — |
| **G-2** — mgmt-artifact integrity | ✅ **Closed 2026-09-12 (RD-015).** `check_docs.py` extended with CHECK D–J (plan↔runbook divergence, dangling `RD-0NN` refs, stray `{{placeholders}}`, undated ✅, living-doc glyph drift, dangling links, advisory sequence adherence), all unittest-covered; README/BUILD_ORDER status surfaces converted to pointers + a machine-verified generated region; reusable-OS/instance boundary documented in `docs/governance/REUSABLE_OS_VS_INSTANCE.md`; governance-doc pin confirmed (already in the 1.R manifest). | Done. | — |
| **C.3** — shared generator + Hub-gate seam | ✅ **Closed 2026-09-12 (RD-034).** Collapsed the 10 contract generators into one shared writer (`scripts/contract_writer.py` + `scripts/gen_contracts.py`) and the 8 Hub-gate kind trios into one data-driven `_KindSpec` registry — byte-identical / behaviour-preserving, proven offline. Per the stakeholder decision the 6 `awsio.py` copies were KEPT per-lane (bundling: a shared module outside each lambda dir would `ModuleNotFoundError`; genuinely-shared surface is ~15 lines). | Done. | — |
| **B.1 → C.1 → C.2 → C.4 → C.5** — harvest into a versioned `infra-building-blocks` archive | Not started; `infra-building-blocks` referenced only in governance docs, not built. | Unchanged scope. This is a **platform-maturity investment** (a reusable construct library), NOT a pipeline requirement. | **Keep but defer — revisit after Phase 3 closes.** Worth it if ZTIE becomes a long-lived platform with many stacks; over-investment if the goal is to finish this one pipeline. **This is the track most worth an explicit keep / defer / drop call.** _(stakeholder decision)_ |
| **T.1** — multi-tenancy design spike (doc-only) | `docs/architecture/MULTI_TENANCY.md` not yet written. | Unchanged scope; cheap (no code). | **Keep — do before Phase 4**, so the 4.x dashboard/handoff design is built against a written tenant model. _(pending confirmation)_ |
| **T.2 / T.3** — per-subscriber provisioning + Hub data isolation | Not started; already in the Deferred bucket. | Unchanged scope. Relevance is **100% contingent on the commercialization decision** — if ZTIE stays single-tenant/internal these may never be needed. | **Keep deferred to commercialization** (as already recorded). Revisit only when/if multi-tenant is committed. **Explicit keep / defer / drop is the stakeholder's call.** _(stakeholder decision)_ |

> **Net:** nothing is dropped; intent stands across all three tracks. The corrections
> are (1) **G-2 and G-1 are now closed** (2026-09-12) — G-1's matrix was finished AND
> ratified (all 59 rows accepted by the accountable party), so the compliance back-map is
> complete (it was never a build), and (2) the C-archive chain + T.2/T.3 are
> strategy-contingent bets that should be an explicit stakeholder keep/defer/drop rather
> than implied commitments. Recommended priority now that G-3, C.3 and G-2 are closed:
> **the pipe track (3.2)**, with G-1 (low-urgency), the archive chain, and tenancy
> provisioning parked until Phase 3 closes / commercialization is decided.

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

**G-2** (Done, validated 2026-09-12) - Made RD-015 (management artifacts held to the same bar as code) machine-enforceable end-to-end by EXTENDING `scripts/check_docs.py` (CHECK A/B/C left untouched): added CHECK D (PLAN↔RUNBOOK per-phase story-set divergence), E (a referenced `RD-0NN` absent from the decision-defining docs), F (stray `{{placeholders}}` outside the template files), G (an undated ✅ pipe/gov story), H (a living-doc generated status glyph disagreeing with the RUNBOOK roll-up, or an on-deck pointer at an already-✅ story), I (a dangling repo-relative `*.md` link in a living doc), and J (an ADVISORY, non-blocking sequence-adherence note when the on-deck starter is not the first OPEN "Ready now" item). Converted README's / BUILD_ORDER's duplicated status surfaces to pointers plus a small machine-verified `GENERATED: phase-status` region, documented the reusable-OS/instance boundary in `docs/governance/REUSABLE_OS_VS_INSTANCE.md`, and confirmed the governance-doc commit pin (already in the 1.R restore manifest). Validation-closed offline on the recorded pass — `check_docs.py` PASSES clean (exit 0) and `test_check_docs` reports SUITE `OK` (19 tests), the suite proving each new check FIRES on an injected defect. As a `G-` governance story it is exempt from CHECK A/B/C (closing it touches no register row). Full detail: [G-2 in STORY_DETAIL.md](docs/STORY_DETAIL.md#story-g-2).

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
