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
| **Status** | ⬜ Not Started |
| **Builds from restore point** | `restore/story-2.3-green` (the detonation lane 2.4 instruments) — captured on 2.3's live pass (2026-09-05). **NOTE: as of this writing the tag has not yet been pushed** — see TASK 0 below; do that FIRST, before starting 2.4. |
| **Session goal** | While a routed artifact is detonating on the ephemeral EC2 (Story 2.3), CAPTURE its runtime behavior — the system calls, network connection attempts, and filesystem operations it makes — and emit that behavioral telemetry as bounded, derived EVIDENCE. This is the observability layer on top of the run 2.3 already performs. |

---

### TASK 0 (do FIRST, owner action) — tag `restore/story-2.3-green`

Story 2.3 was validated live 2026-09-05 (PR #60 merged; all 4 DoD checks passed) and
its Validation Debt Register entry cleared. `RUNBOOK.md`/`PROJECT_PLAN.md` already
reference the tag `restore/story-2.3-green`, but it does not exist yet in
`git tag -l`. Before opening 2.4:
```
git fetch origin
git log --oneline -1 origin/main   # confirm it is the PR #60 merge commit
git tag -a restore/story-2.3-green origin/main \
  -m "Story 2.3 validated live 2026-09-05: dynamic detonation lane (ephemeral EC2 + host-native SSM), 4/4 DoD pass"
git push origin restore/story-2.3-green
```
Point it at the merge commit for PR #60 (the status-flip commit), never an earlier
build/fix commit (PRs #51–#59 predate validation).

---

### Background & Context

ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted
artifact before it reaches the PDE; work is validation-gated (nothing is ✅ until a
recorded live pass — the covenant). Phase 1 is ✅. Phase 2's STATIC lane is ✅ (2.1 +
2.2). Phase 2's DYNAMIC lane now RUNS the artifact: **2.3** launches one ephemeral EC2
from the 2.0 launch template, executes the artifact host-native via SSM (no Docker),
self-terminates on the 5-min hard TTL, and crosses a bounded, verdict-free **run
OUTCOME** (`dynamic-run.contract.v1`). But 2.3 records only the *control-plane* outcome
(what ran, how it ended, was it contained + torn down) — it deliberately captures NO
behavior. **Story 2.4 adds the behavior**: what did the artifact actually DO while it
ran — the syscalls, the network it reached for, the files it touched. That is the
evidence static analysis can never produce and the raw material Phase-3 correlation
(Nova Pro) scores.

### What This Story Is (nature + gate role)

**Nature: NEW FEATURE story.** It may begin only if its Depends-on are all ✅ **and**
the Validation Debt Register is empty. **Both are already true as of this writing:**
**2.3 was validated live 2026-09-05** (PR #60, merged — all 4 DoD checks passed,
verbatim evidence recorded in `docs/STORY_DETAIL.md#story-2-3`) and the Validation
Debt Register is EMPTY. **The advancement gate is OPEN — 2.4 may start.** STEP 0
must still RE-CONFIRM this on `main` (trust `main` + `check_docs` over this brief)
before touching anything — do not assume it; verify `[2.3]` shows ✅ in RUNBOOK.md's
master table and `check_docs.py` PASSes.

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
  behavioral-telemetry contract crossing the RD-013 Hub gate (a seventh envelope kind
  with its OWN version pin — the per-envelope-kind-pin discipline from 2.2/2.3);
  monotonic-clock relative timestamps (offsets from detonation start, never a wall
  clock — see RD note in PROJECT_PLAN); pure logic + thin seams; tests; likely a new
  RD for the capture-tool choice + candidate control mappings.
- **Out of scope / do NOT touch:** the telemetry **sanitization** pipeline (entropy
  scrub → noise suppress → ≤25K truncation) — that is **2.5**; the parallel
  fork/orchestration — **2.6**; the Hub verdict; the static lane; Docker on the host.
  2.4 CAPTURES raw behavior; 2.5 SANITIZES it; keep them separate.
- **Depends on:** **2.3 ✅** (hard gate — no behavior to capture without a real run).
  Plus an **empty Validation Debt Register**.
- **Unblocks:** 2.5 (sanitization needs raw telemetry) and 2.6 (the fork).
- **Roadmap position:** P2 dynamic lane, deepened — the observability layer on the run.

### Approach & Constraints

- **Expected true-state (STEP 0 re-confirms; trust `main` + `check_docs` over this
  brief):** **2.3 = ✅** (validated live 2026-09-05, PR #60 merged); the Validation
  Debt Register is EMPTY; the advancement gate is OPEN. Restore tags to expect:
  `restore/phase-1-green`, `restore/story-2.0-green`, `restore/story-2.1-green`, and
  **`restore/story-2.3-green` — TASK 0 above must be done FIRST if this tag is still
  missing.** PHANTOM TAG still open (separate issue): `restore/phase-2-floor-green`
  is referenced in BOM/RUNBOOK (A.4) but is NOT in `git tag -l` — resolve before
  relying on the Phase-2 floor; do not conflate it with `restore/story-2.3-green`.
- **Approach:** (1) STEP 0 + confirm the register is empty (else get 2.3 validated
  first); (2) design the behavioral-telemetry contract FIRST (a new RD-013 envelope
  kind, bounded, verdict-free, its OWN version pin); (3) pure capture-normalization
  logic + thin seams (extend the 2.3 `awsio` seam for the capture-tool control over
  SSM + the trace upload); (4) instrument the 2.3 run (the capture wraps the same
  host-native execution — likely the run command becomes "start capture → run artifact
  → stop capture → collect trace"); (5) the STAKEHOLDER validates live; (6) record +
  flip ✅ (paired commit); PROJECT_PLAN ↔ RUNBOOK aligned; PR.
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

- [ ] Story's brief + runbook entry updated (status, Validation Result, dates).
- [ ] PROJECT_PLAN and RUNBOOK in exact alignment (2.4 identical in both).
- [ ] Any new/changed registered decisions recorded; candidate control mappings (RD-014) recorded.
- [ ] All doc changes PR-reviewed (branch + PR, never straight to main).
- [ ] Governance kept restorable alongside the code.
- [ ] On validation pass: record Validation Result + flip ✅ (paired commit).
- [ ] Author the next-story handoff (2.5 sanitization, or 2.6 fork per sequencing) with real Lessons Learned.

### Change & Rollback

- **Change type:** normal (new capture logic + a new contract; instruments the 2.3 run).
- **Restore point this builds from:** `restore/story-2.3-green` (captured on 2.3's pass).
- **Backout plan:** if a check fails, 2.4 stays 🟡; fix + re-validate. If a status flip
  is later found unwarranted, revert the paired status commit + delete the tag.

### Definition of Done / Validation Gate

> A pass/fail gate, not a description. The stakeholder validates live; the executor
> records; only a recorded pass flips status.

- **Done means (the stakeholder confirms live in Forensic 360999005254):**
  1. During a real 2.3 detonation, the ephemeral host CAPTURES the artifact's
     behavior — syscalls, network connection attempts, and filesystem operations —
     host-native (NO Docker/container).
  2. The FULL behavioral trace is written to Forensic S3 (it stays in Forensic, RD-009).
  3. A bounded, derived behavioral-telemetry summary crosses the RD-013 gate to the Hub
     (a new envelope kind, its own version pin) — EVIDENCE, never a verdict.
  4. Timestamps are relative monotonic offsets from detonation start (never a wall clock).
- **Validated by:** the stakeholder, live; the executor records verbatim.
- **Validation Result:** `pending`.
- **On pass (and only then):** record the dated Validation Result, flip 2.4 ✅ (paired
  commit), keep PLAN ↔ RUNBOOK aligned; capture a restore point.
- **On fail:** 2.4 stays 🟡; re-focus on fixing + re-validating; no advancement.
- **Advancement gate:** 2.4 depends on 2.3 ✅ AND an empty Validation Debt Register. It
  unblocks 2.5 + 2.6.

### Risks & Watch-Items

- **The register is empty and the gate is open (re-verify, don't assume).** 2.3 was
  validated 2026-09-05; the only remaining item is tagging `restore/story-2.3-green`
  (TASK 0). Do STEP 0 anyway before starting — trust `main`, not this brief.
- **The artifact-fetch mechanism 2.3 built has HARD-WON constraints — reuse them
  exactly if 2.4's capture-trace upload needs its OWN S3 interaction.** See Lessons
  Learned below for the full 4-part recipe (gateway endpoint + SG egress to the S3
  prefix list + regional presign + SigV4). Do not rediscover any of these live.
- **The isolated VPC means network capture is about INTENT, not success.** The host has
  no egress, so any outbound connection attempt fails — but the *attempt* is the
  signal. Capture attempts, not just completed connections.
- **Capture tool must be on the golden AMI.** strace/auditd/eBPF tooling has to be baked
  into the ubuntu-22.04 golden AMI (or installed at boot — but the host has no internet,
  so it must be pre-baked). Confirm what the AMI ships before designing the capture. The
  AL2023 AMI build is still broken (ubuntu-only) — see Lessons Learned.
- **NO Docker on the host (RD-001).** Capture is host-native, driven over SSM.
- **Bounded crossing.** The full trace can be large; only a bounded, derived summary
  crosses (the per-envelope-kind version-pin discipline from 2.2/2.3). Sanitization/
  truncation to the ≤25K token budget is 2.5, NOT here — but 2.4's crossed summary must
  still be bounded by its own schema.
- **Relative clock only.** Use monotonic offsets from detonation start, never a
  human/observer wall clock (PROJECT_PLAN note).
- **CloudShell `/tmp` and shell variables are wiped on session recycle.** A fresh shell
  tab has NONE of the previous exports even though the visible prompt looks continuous.
  This caused several stale-value mistakes in 2.3's live validation. Always re-set
  variables in the SAME block right before use.

### Lessons Learned / Carry-Forward *(from the Story 2.3 build + LIVE VALIDATION, 2026-09-04/05)*

**From the build (still true):**
- **The lane pattern held again (1.2 → 2.2 → 2.3):** contract-first, pure
  logic + thin boto3 seam, evidence-never-verdict, a NEW envelope kind with its OWN
  Hub version pin. Reuse it for 2.4's capture-summary vs. the capture-tool seam.
  Concretely for 2.3: `lambdas/detonation/{outcome.py,runspec.py}` are PURE (offline
  unit-tested), `awsio.py` is the only boto3, `handler.py` orchestrates; the Hub gate
  got `DYNAMIC_RUN_CONTRACT_VERSION` (its own pin) + `_is_dynamic_run_envelope`
  (discriminator = a `run` object). 2.4 gets its OWN pin + its OWN discriminator key.
- **2.0 already provisioned almost everything the dynamic lane needs** — the
  `orchestratorRole` (RunInstances + SSM SendCommand + PassRole) and the SSM coordinate
  params `/ztie/detonation/{launch-template-id,isolated-subnet-ids}` (the
  `instance-role-arn` param is published but 2.3's final code does NOT read it — see
  below). 2.4 should reuse the SAME pattern (read coordinates from SSM, never hardcode).
- **2.3's compute is a PLAIN ZIP Lambda (NO Docker build box).** The no-Docker rule is
  about the detonation *host*; the orchestrator itself is stdlib + boto3. 2.4's capture
  orchestration is the same — do NOT spin up a Docker build box. The capture TOOL,
  however, must be pre-baked on the golden AMI (the host has no internet to install it).
- **Branch off `main`, not the restore tag, for the CODE base.** Restore tags are
  ancestors of main and predate later merged stories; building on one and PRing to
  main regresses merged work. Branch 2.4 off `main` at the current HEAD.
- **The `tsc --noEmit` environmental-error family is expected + benign** in the
  INTEGRATIONS_ONLY sandbox: TS2307 (missing modules), TS2591 (`path`), TS2304
  (`__dirname`), TS2339 (`env`/`region`/`partition`/`account` "not on Props/Stack").
  Confirm your new code shows ONLY this family (no NEW error class). `npx` needs
  `env -u NODE_OPTIONS npx --no-install`. **When adding a genuinely new CDK API
  (e.g. a custom resource, a new construct method), CROSS-CHECK it against real
  docs/GitHub issues before a live deploy** — two wrong guesses about a single CDK
  attribute (`attrPrefixListId`, then an uncertain `PrefixList.fromLookup`) were
  caught this way in 2.3; the real, verified fix was an `AwsCustomResource` calling
  a documented EC2 API directly.
- **jsonschema is NOT installable offline** — the contract-conformance test needs TWO
  layers: `@unittest.skipUnless(jsonschema)` live tests AND a MANUAL pure-Python
  conformance walk that runs everywhere. Reuse this two-layer pattern for 2.4.
- **Governance-tooling drift is real (RD-015)** — after any status/register edit,
  re-run `python3 -m unittest scripts.test_check_docs` AND `scripts/check_docs.py`.
  The G-3 fixtures are state-independent (`_NEW_WORK_STORY = "2.5"`) — keep them that way.

**From the LIVE detonation run itself (2026-09-05) — the complete artifact-fetch story:**
The FIRST live run of Story 2.3 surfaced SEVEN real defects, one at a time, each only
discoverable by actually executing the pipeline. All are fixed on `main` (PRs #52-#59,
then #60 recorded the pass). **If 2.4 touches ANY new S3 interaction from the isolated
host (e.g. uploading the behavioral trace, or the capture tool needing its own
artifact), the same class of problem WILL recur unless this exact recipe is reused:**
1. `ec2:RunInstances` must NOT pass `IamInstanceProfile` — the 2.0 launch template
   already bakes it in (CDK's `LaunchTemplate({ role })`); deriving one from the role
   ARN produces an invalid profile ARN and `RunInstances` rejects it outright.
2. The on-host `curl` fetching from S3 MUST have `--connect-timeout`/`--max-time`.
   Without them, an unreachable S3 endpoint hangs the SSM command until the hard TTL's
   `shutdown -h` SIGKILLs it (`Rc: 137`, empty output) — indistinguishable from a slow
   artifact. Bound it and have the failure emit a diagnosable marker.
3. Do NOT add an S3 *interface* endpoint if the VPC already has an S3 *gateway*
   endpoint — AWS warns this combination causes private-DNS conflicts; verified live,
   the isolated host resolved S3 to an unroutable PUBLIC IP. One gateway endpoint is
   sufficient.
4. `boto3` presigns the GLOBAL S3 host (`<bucket>.s3.amazonaws.com`) by DEFAULT in
   us-east-1, even with `addressing_style='virtual'`. An S3 gateway endpoint only
   intercepts the REGIONAL host. Fix: explicit `endpoint_url` + `Config(s3={
   "us_east_1_regional_endpoint": "regional"})`.
5. An S3 gateway endpoint routes to S3's PUBLIC IP ranges via a managed prefix list —
   OUTSIDE the VPC CIDR. The detonation host's security-group egress (2.0) only allows
   the VPC CIDR (for interface endpoints); it must ALSO explicitly allow the AWS-managed
   S3 prefix list. Resolve that prefix-list id via a real `ec2:describeManagedPrefixLists`
   call (`AwsCustomResource`) — NOT a hard-coded id, NOT an unverified CDK L2 helper.
6. us-east-1 defaults `boto3` to SigV2 signing; the regional endpoint REJECTS SigV2
   with a plain HTTP 400. Fix: `config=Config(signature_version="s3v4", ...)`.
7. **The full, minimal, correct recipe (proven live, ALL FOUR required together):**
   one S3 gateway endpoint + host SG egress to its prefix list + regional presign +
   SigV4 signing. Missing any one reproduces a timeout or a 400.
- **CloudShell `/tmp` and shell variables are wiped on session recycle** (a new tab or
  a timeout leaves NO exports from the prior session even though the visible prompt
  looks continuous) — this caused several stale-variable mistakes during 2.3's live
  validation (a `get-command-invocation` queried against an OLD instance/command id).
  Re-set every variable used in a block, in the SAME block, right before use.
- **`awscurl` needs a JSON envelope for this repo's intake API**, not a raw binary
  `--data-binary` POST: `{"filename":...,"content_type":...,"submitter":...,
  "content_base64":"<base64>"}` with `-H 'Content-Type: application/json' -d @file.json`.
- **PR mergeability can go stale/cached on GitHub** after a force-push. If a PR looks
  permanently stuck (`mergeable: null` for minutes), close it and open a fresh PR from
  the same corrected branch rather than waiting indefinitely.
- **Recurring two-account live reality:** intake + all artifact-touching compute is in
  **Forensic 360999005254**; the durable tracking record is in the **Hub 641628980935**.
  TWO CloudShell tabs; run `aws sts get-caller-identity` before EVERY block. `gh pr
  create` is BROKEN — open PRs via `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`.
- **PHANTOM TAG still unresolved:** `restore/phase-2-floor-green` is referenced in
  BOM/RUNBOOK (A.4) but does NOT exist in `git tag -l`. Separate from
  `restore/story-2.3-green` (TASK 0, above) — do not conflate the two.
- **User notes:** *(open for the stakeholder to add anything before the 2.4 session.)*

> **Sequencing note (RD-024 — stakeholder decides):** 2.4 (behavioral telemetry) is the
> pipeline-forward choice and the natural next step after 2.3 (it turns the run into
> analyzable evidence). 2.5 (sanitization) depends on 2.4; 2.6 (the fork) depends on
> both lanes. 2.3's live pass IS recorded and the register IS empty (2026-09-05) — the
> gate is open. One recommendation: *next up 2.4 — it is what makes the detonation
> chamber worth running.*
