# Session Brief — Story 2.4

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.

---

## Story 2.4 — Behavioral telemetry capture (syscalls / network / filesystem)

| Field | Value |
|-------|-------|
| **Phase** | P2 — Parallel Inspection (the DYNAMIC lane, deepened) |
| **Date** | TBD (next session) |
| **Status** | 🟡 In Progress (build tier 7; BUILT + offline-proven, awaiting the recorded live detonation-with-capture pass; on the Validation Debt Register). Live steps: [`story-2.4-LIVE-RUNBOOK.md`](story-2.4-LIVE-RUNBOOK.md). |
| **Depends on (all ✅ as of 2026-09-08)** | **2.3 ✅** (the detonation run 2.4 instruments), **A.5 ✅** (plan-drift corrected), **A.6 ✅** (restore tags pushed) |
| **Builds from restore point** | `restore/story-2.3-green` (the detonation lane 2.4 instruments; pushed + verified on origin by A.6, 2026-09-08). Branch the CODE off current `main` (contains merged 2.3 + 2.6 + A.5/A.6), not off the tag. |
| **Session goal** | While a routed artifact is detonating on the ephemeral EC2 (Story 2.3), CAPTURE its runtime behavior — the syscalls, network connection attempts, and filesystem operations it makes — and emit that as bounded, derived EVIDENCE. The observability layer on top of the run 2.3 already performs. |

---

### Background & Context

ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted artifact
before it reaches the PDE; work is validation-gated (nothing is ✅ until a recorded live
pass — the covenant). Phase 1 is ✅. Phase 2's STATIC lane is ✅ (2.1 + 2.2). Phase 2's
DYNAMIC lane RUNS the artifact: **2.3** launches one ephemeral EC2 from the 2.0 launch
template, executes the artifact host-native via SSM (no Docker), self-terminates on the
5-min hard TTL, and crosses a bounded, verdict-free **run OUTCOME**
(`dynamic-run.contract.v1`). **2.6** (✅ 2026-09-08, RD-029) then added the parallel
orchestration — a Step Functions state machine that forks both lanes concurrently and a
collector Lambda that crosses one bounded `collected` record. But 2.3 records only the
*control-plane* outcome (what ran, how it ended, was it contained + torn down) — it
deliberately captures NO behavior. **Story 2.4 adds the behavior**: what did the artifact
actually DO while it ran — the syscalls, the network it reached for, the files it
touched. That is the evidence static analysis can never produce and the raw material
Phase-3 correlation (Nova Pro) scores.

### What This Story Is (nature + gate role)

**Nature: NEW FEATURE story.** It may begin only if its Depends-on are ALL ✅ **and** the
Validation Debt Register is empty. **All are true as of 2026-09-08:** 2.3 ✅ (2026-09-05),
A.5 ✅ + A.6 ✅ (2026-09-08), and the register is EMPTY — the advancement gate is OPEN.
2.4 is the next story by build tier now that 2.6 closed. STEP 0 must still RE-CONFIRM this
on `main` (trust `main` + `check_docs` over this brief) before touching anything.

### Objective & Value

- **Objective:** instrument the detonation so that, during the host-native run, the
  ephemeral host records its own behavior — syscalls (e.g. via `strace`/auditd or an
  eBPF tool baked into the golden AMI), outbound network attempts (which, in the
  isolated VPC with no egress, are themselves signal — a connect attempt that goes
  nowhere is still evidence of INTENT), and filesystem operations (creates / writes /
  deletes / permission changes). Emit this as bounded, derived behavioral telemetry:
  the FULL capture stays in Forensic (RD-009); only a bounded, derived summary crosses
  to the Hub (a NEW envelope kind, its OWN version pin) — EVIDENCE, never a verdict.
- **Why it matters:** a packed/obfuscated artifact reveals itself by what it DOES at
  runtime. The behavioral trace is the highest-signal input to the Phase-3 verdict and
  the Security-tier report (MITRE ATT&CK mappings, behavioral chains, Sigma rules).

### Scope, Dependencies & Position

- **In scope:** capturing syscall / network / filesystem behavior on the ephemeral
  host during the 2.3 run (host-native capture tool driven over SSM — NO Docker,
  RD-001); shipping the full trace to Forensic S3 (RD-009); a NEW bounded, derived
  behavioral-telemetry contract crossing the RD-013 Hub gate (the EIGHTH envelope kind,
  its OWN version pin + OWN discriminator — the per-kind-pin discipline from 2.2/2.3/2.6;
  the seven existing discriminators are classification/routing/rejection/scan/run/status/
  collected); monotonic-clock relative timestamps (offsets from detonation start, never
  a wall clock); pure logic + thin seams; tests; a new RD (RD-030) for the capture-tool
  choice + candidate control mappings; any golden-AMI change needed to ship the tool.
- **Out of scope / do NOT touch:** the telemetry **sanitization** pipeline (entropy
  scrub → noise suppress → ≤25K truncation) — that is **2.5**; the parallel
  fork/orchestration internals — **2.6** (but the lane stacks it orchestrates MUST be
  redeployed for validation — see the deploy-gap watch-item); the Hub verdict; the
  static lane; Docker on the host. 2.4 CAPTURES raw behavior; 2.5 SANITIZES it.
- **Depends on:** **2.3 ✅ + A.5 ✅ + A.6 ✅** (hard gate — no behavior to capture without
  a real run; A.5/A.6 were the clean-the-ground gate). Plus an **empty Validation Debt
  Register**.
- **Unblocks:** 2.5 (sanitization needs raw telemetry).
- **Roadmap position:** P2 dynamic lane, deepened — the observability layer on the run.
  NOTE: 2.4 does NOT by itself close Phase 2 — the P2 phase-gate also needs 2.4 + 2.5;
  2.6 completed only the parallel-fork orchestration.

### Approach & Constraints

- **Expected true-state (STEP 0 re-confirms; trust `main` + `check_docs` over this
  brief):** 2.3 ✅, A.5 ✅, A.6 ✅; Validation Debt Register EMPTY; advancement gate OPEN.
  ALL SIX restore tags now exist on origin (A.6 pushed the last two 2026-09-08):
  `restore/phase-1-green`, `restore/story-2.0-green`, `restore/story-2.0E-green`,
  `restore/story-2.1-green`, `restore/phase-2-floor-green`, `restore/story-2.3-green`.
  There is NO phantom tag and NO "push a tag first" task — that was A.6's job and it is
  done. Next free RD number = **RD-030** (re-verify at STEP 0).
- **Approach:** (1) STEP 0 + confirm the register is empty; (2) design the
  behavioral-telemetry contract FIRST (new RD-013 envelope kind, bounded, verdict-free,
  own version pin + discriminator); (3) pure capture-normalization logic + thin seams
  (extend the 2.3 `awsio` seam for the capture-tool control over SSM + the trace
  upload); (4) instrument the 2.3 run (the run becomes "start capture → run artifact →
  stop capture → collect trace"); (5) redeploy the detonation lane stack, then the
  STAKEHOLDER validates live; (6) record + flip ✅ (paired commit); PROJECT_PLAN ↔
  RUNBOOK aligned; PR.
- **Roles:** the LIVE detonation-with-capture run is the **stakeholder's** action in
  Forensic (the executor has NO live creds); the **executor RECORDS** the returned
  output verbatim. Do NOT simulate/assume a live output.
- **Hard constraints:** host-native capture only, NO Docker on the host (RD-001);
  behavior is EVIDENCE, never a verdict; the full trace stays in Forensic, only a
  bounded summary crosses; relative monotonic timestamps only. Production code (no mock
  telemetry). Docs first-class (RD-015), PR-reviewed.

### Validation Rationale & Compliance Mapping (REQUIRED — RD-014)

- **Rationale:** behavioral telemetry is the runtime-behavior evidence that makes the
  detonation chamber worth running — it is what the correlation engine reasons over.
- **Candidate control mappings** *(proposed; ratified on review):*

| Framework | Control ID | Control Name | Rationale | Status |
|-----------|-----------|--------------|-----------|--------|
| NIST 800-53 r5 | SI-4 | System Monitoring | Capturing syscall/network/fs behavior IS runtime system monitoring | Proposed |
| NIST 800-53 r5 | SI-3 | Malicious Code Protection | Behavioral capture surfaces malicious runtime activity | Proposed |
| NIST 800-53 r5 | AU-2 / AU-12 | Event Logging / Audit Record Generation | The trace is an audit record of what the artifact did | Proposed |
| NIST CSF | DE.CM-1 / DE.AE-2 | Network/system monitored; events analyzed | Runtime behavior observed + made analyzable | Proposed |
| ISO 27001:2022 | A.8.16 | Monitoring activities | Runtime monitoring of the detonating artifact | Proposed |
| ISO 27001:2022 | A.8.15 | Logging | The behavioral trace is a security log | Proposed |

- **Audit evidence produced:** the dated Validation Result in RUNBOOK 2.4; the derived
  behavioral-telemetry summary on the Hub tracking record; the full trace in Forensic
  S3; logs showing capture started/stopped around a real host-native run.

### Management-Artifact Obligations (REQUIRED — RD-015)

- [x] Story's brief + runbook entry updated (status ⬜→🟡, Validation Result pending, 2.4 added to the Validation Debt Register).
- [x] PROJECT_PLAN and RUNBOOK aligned (2.4 = 🟡 In Progress in the RUNBOOK master table; PROJECT_PLAN Phase-2 narrative + RD-030 recorded; STORY_DETAIL 2.4 updated to 🟡 with the as-built detail).
- [x] New RD-030 (capture-tool choice = `strace`, host-native, graceful degradation, AMI dependency) recorded in PROJECT_PLAN §5; candidate control mappings (RD-014) recorded (SI-4 / SI-3 / AU-2 / AU-12; CSF DE.CM-1 / DE.AE-2; ISO A.8.16 / A.8.15, all Proposed).
- [x] LIVE-RUNBOOK authored ([`story-2.4-LIVE-RUNBOOK.md`](story-2.4-LIVE-RUNBOOK.md)) with the deploy-gap pre-run redeploy step (redeploy `ZtieDetonationStack` + the Hub stack BEFORE submitting).
- [ ] All doc changes PR-reviewed (branch + PR, never straight to main). — PR open; awaiting owner merge.
- [ ] Governance kept restorable alongside the code. — restore point captured by the owner on the validated merge commit (post-live-pass).
- [ ] On validation pass: record Validation Result + flip ✅ (paired commit). — pending the live pass.
- [ ] Author the next-story handoff (2.5 sanitization) with real Lessons Learned. — authored on the recorded live pass (real lessons, not pre-run guesses).

### Change & Rollback

- **Change type:** normal (new capture logic + a new contract; instruments the 2.3 run).
- **Restore point this builds from:** `restore/story-2.3-green` (captured on 2.3's pass;
  pushed + verified on origin by A.6, 2026-09-08).
- **Backout plan:** if a check fails, 2.4 stays 🟡 (added to the Validation Debt Register
  in the same commit); fix + re-validate. If a status flip is later found unwarranted,
  revert the paired status commit + delete the tag.

### Definition of Done / Validation Gate

> A pass/fail gate, not a description. The stakeholder validates live; the executor
> records; only a recorded pass flips status.

- **Done means (the stakeholder confirms live in Forensic 360999005254):**
  1. During a real detonation, the ephemeral host CAPTURES the artifact's behavior —
     syscalls, network connection attempts, and filesystem operations — host-native
     (NO Docker/container).
  2. The FULL behavioral trace is written to Forensic S3 (it stays in Forensic, RD-009).
  3. A bounded, derived behavioral-telemetry summary crosses the RD-013 gate to the Hub
     (a new envelope kind, its own version pin) — EVIDENCE, never a verdict.
  4. Timestamps are relative monotonic offsets from detonation start (never a wall clock).
- **Validated by:** the stakeholder, live; the executor records verbatim.
- **Validation Result:** `pending`.
- **On pass (and only then):** record the dated Validation Result, flip 2.4 ✅ (paired
  commit), keep PLAN ↔ RUNBOOK aligned; capture a restore point (owner action).
- **On fail:** 2.4 stays 🟡; re-focus on fixing + re-validating; no advancement.
- **Advancement gate:** 2.4 depends on 2.3 + A.5 + A.6 ✅ AND an empty Validation Debt
  Register. It unblocks 2.5.

### Risks & Watch-Items

- **DEPLOY-GAP (highest-priority, learned live in 2.6).** 2.4 modifies the detonation
  lane handler. 2.6's orchestration invokes that lane. If validation runs against the
  OLD deployed lane code, the run will misbehave (2.6 saw a direct-invoke fall through
  the SQS path → `{"batchItemFailures":[]}`). **The 2.4 LIVE-RUNBOOK must list
  "redeploy `ZtieDetonationStack` (and the orchestration/Hub stacks if the contract
  changed) BEFORE submitting a run" as an explicit pre-run step.** Deploying only the
  new code is insufficient.
- **The artifact-fetch mechanism 2.3 built has HARD-WON constraints — reuse them
  exactly if 2.4's trace upload needs its OWN S3 interaction.** The full 4-part recipe
  (one gateway endpoint + host SG egress to the S3 managed prefix list + regional
  presign + SigV4) is in Lessons Learned. Do not rediscover any of these live.
- **The isolated VPC means network capture is about INTENT, not success.** The host has
  no egress, so any outbound connection attempt fails — but the *attempt* is the signal.
  Capture attempts, not just completed connections.
- **Capture tool must be on the golden AMI.** strace/auditd/eBPF tooling has to be baked
  into the ubuntu-22.04 golden AMI (the host has no internet to install at boot). Confirm
  what the AMI ships before designing capture; the AL2023 AMI build is still broken
  (ubuntu-only).
- **NO Docker on the host (RD-001).** Capture is host-native, driven over SSM.
- **Bounded crossing.** The full trace can be large; only a bounded, derived summary
  crosses (own version pin). Sanitization/truncation to the ≤25K token budget is 2.5,
  NOT here — but 2.4's crossed summary must still be bounded by its own schema.
- **Relative clock only.** Use monotonic offsets from detonation start, never a wall clock.
- **CloudShell `/tmp` and shell variables are wiped on session recycle.** Re-set
  variables in the SAME block right before use (caused stale-value mistakes in 2.3/2.6).
- **RD-number collisions happen.** Take the next free RD from CURRENT `main`
  (`grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md | sort -u | tail`) — RD-030 as of now.

### Lessons Learned / Carry-Forward

**From Story 2.6's LIVE run (2026-09-08) — most relevant to 2.4:**
- **Deploy-gap (see the top watch-item):** a new direct-invoke code path on a lane
  Lambda that an earlier orchestration invokes requires REDEPLOYING that lane stack
  before validating — deploying only the new orchestration/capture code is not enough.
  Root-cause a "lane didn't really run" via `stepfunctions get-execution-history …
  TaskScheduled.parameters` + the lane Lambda's CloudWatch logs + the returned Payload.
- **The join tolerating one-lane failure is the design working, not a bug:** 2.6's
  collector recorded `lane_status=errored` / `both_complete=false` when a lane fell
  through — no hang, no drop, no fabricated verdict. Keep that fail-open-record posture
  if 2.4 touches any lane orchestration.
- **Intake API via awscurl:** JSON envelope `{filename, content_base64, content_type,
  submitter}` (base64 of the artifact), URL BEFORE the flags, `-d @file.json`; a raw body
  gives "Request body must be valid JSON". `pip install awscurl` in CloudShell.

**From the Story 2.3 build + LIVE VALIDATION (2026-09-04/05):**
- **The lane pattern held (1.2→2.2→2.3, and again in 2.6):** contract-first, pure logic +
  thin boto3 seam, evidence-never-verdict, a NEW envelope kind with its OWN Hub version
  pin + discriminator. `lambdas/detonation/{outcome.py,runspec.py}` are PURE (offline
  unit-tested); `awsio.py` is the only boto3; `handler.py` orchestrates. 2.4 extends this
  seam for the capture-tool control + trace upload; keep new capture logic PURE.
- **2.0 already provisioned the dynamic lane's infra** — the orchestrator IAM + the SSM
  coordinate params `/ztie/detonation/{launch-template-id,isolated-subnet-ids}`. 2.4
  reuses the SAME read-from-SSM pattern; never hardcode ids.
- **2.3's compute is a PLAIN ZIP Lambda (no Docker build box).** The no-Docker rule is
  about the detonation *host*; the orchestrator is stdlib + boto3. 2.4's capture
  orchestration is the same. The capture TOOL, however, must be pre-baked on the AMI.
- **Branch off `main`, not a restore tag, for the CODE base.** Restore tags are ancestors
  of main and predate later merged stories.
- **The complete artifact-fetch recipe (proven live, all four required together):** (1)
  do NOT pass `IamInstanceProfile` on `RunInstances` (the launch template bakes it in);
  (2) bound on-host `curl` with `--connect-timeout`/`--max-time`; (3) ONE S3 gateway
  endpoint (no interface endpoint — private-DNS conflict); (4) regional presign
  (`endpoint_url` + `us_east_1_regional_endpoint=regional`) + host SG egress to the S3
  managed prefix list (resolved via a real `ec2:DescribeManagedPrefixLists` /
  `AwsCustomResource`, not a hard-coded id, not `attrPrefixListId` (TS2339), not an
  unverified `PrefixList.fromLookup`) + SigV4 (`signature_version="s3v4"`; us-east-1
  defaults to SigV2 → HTTP 400).
- **Offline proof bar:** stdlib `unittest` + a MANUAL pure-Python conformance walk
  (jsonschema not installable) — two layers. `ruff` at
  `~/.pyenv/versions/3.12.13/bin/ruff`; `tsc --noEmit`/`prettier` need `env -u
  NODE_OPTIONS` and show only the missing-`aws-cdk-lib` family (no new error TYPE).
- **Governance-tooling drift (RD-015):** run `check_docs.py` AFTER committing a status
  change (CHECK B baseline is `git show HEAD:RUNBOOK.md`); run `python3 -m unittest
  scripts.test_check_docs` (its `check_docs: FAIL …` fixture lines are the checker
  testing itself; suite still OK / 3 tests). If 2.4 goes 🟡 it MUST be added to the
  Validation Debt Register in the same commit.
- **Two accounts, two tabs, `aws sts get-caller-identity` before EVERY block.** Intake +
  compute in Forensic; tracking table in the Hub. `gh pr create` is BROKEN — use
  `gh api …/pulls`. PR mergeability can cache stale after a force-push — verify via
  `git ls-remote`/refs API; if stuck, close + reopen a fresh PR from the same branch.
- **User notes:** *(open for the stakeholder to add anything before the 2.4 session.)*

> **Sequencing note (RD-024 — stakeholder decides):** 2.4 (behavioral telemetry) is the
> next story by build tier (tier 7) now that its gate (2.3 + A.5 + A.6) is fully ✅ and
> 2.6 has closed. It turns the run into analyzable evidence; 2.5 (sanitization) depends
> on it. One recommendation: *next up 2.4 — it is what makes the detonation chamber
> worth running.*
