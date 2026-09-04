# Session Brief — Story 2.3

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.

---

## Story 2.3 — Detonation chamber (ephemeral EC2 + host-native SSM execution)

| Field | Value |
|-------|-------|
| **Phase** | P2 — Parallel Inspection (the DYNAMIC lane) |
| **Date** | TBD (next session) |
| **Status** | ⬜ Not Started |
| **Builds from restore point** | `restore/story-2.0-green` (the Forensic isolated-VPC infra foundation 2.3 runs inside) |
| **Session goal** | Build the DYNAMIC lane: detonate a routed artifact on an **ephemeral EC2** instance in the Forensic isolated VPC, executed **host-native via SSM (NO Docker)**, with a **5-minute hard TTL** (`shutdown -h +5`), and confirm a real instance ran the artifact and was torn down. Non-executing static (2.1/2.2) already covers inspection; this is the first place the artifact actually RUNS. |

---

### Background & Context

ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted
artifact before it reaches the PDE; work is validation-gated (nothing is ✅ until a
recorded live pass — the covenant). Phase 1 is ✅. Phase 2's STATIC lane is built:
2.1 ✅ (four scanners, non-executing) and **2.2 🟡** (compliance mapping + signature
scans — built, pending live validation on PR #48). The infra foundation **2.0 is ✅**
(the Forensic isolated VPC, the detonation launch template, the instance role, the
AMI SSM parameter, the 5-min-TTL UserData). Story 2.3 is the DYNAMIC lane: it takes
the same routed artifact and actually **executes** it, safely, inside that isolated
VPC — the counterpart to the static lane in the P2 fork.

### What This Story Is (nature + gate role)

**Nature: NEW FEATURE story.** It may begin only if its Depends-on are all ✅ **and**
the Validation Debt Register is empty. Its hard dependency (**2.0**) is ✅. **But**
2.2 is 🟡 (built, pending validation) and will sit in the Validation Debt Register
until the stakeholder validates it live — so **the advancement gate is likely CLOSED
when this brief is picked up.** *The category error to prevent:* do NOT start 2.3
feature work while the register is non-empty. **STEP 0 must re-check the register**;
if 2.2 (or anything) is still open, the correct move is to **finish that validation
first** (or, if the stakeholder explicitly de-scopes/defers per RD-024, record that
decision) — not to build 2.3 on top of open debt.

### Objective & Value

- **Objective:** stand up the detonation execution path — given an artifact routed to
  the `dynamic_analysis` lane, launch ONE ephemeral EC2 from the 2.0 launch template
  into the Forensic isolated VPC, deliver + run the artifact **host-native via SSM**
  (`SendCommand`/run document — NO Docker, NO container; RD-001), and let the instance
  self-terminate via the 5-minute hard TTL. Emit a bounded, derived run record
  (evidence, never a verdict) — the *behavioral telemetry* itself is the next story
  (2.4).
- **Why it matters:** static inspection cannot see runtime behavior. The detonation
  chamber is where a disguised/packed/obfuscated artifact reveals what it actually
  DOES — the core of ZTIE's zero-trust posture. It must run the artifact **only**
  inside the blast zone, on a disposable host, that cannot phone home (isolated VPC),
  and that always dies on its own.

### Scope, Dependencies & Position

- **In scope:** the Forensic-side dynamic-lane wiring — consume a `dynamic_analysis`
  work item (the preprocessor/router enqueues it, mirroring how 2.1's static work
  queue is fed); `ec2:RunInstances` **via the 2.0 launch template** (NOT
  CloudFormation-per-run); host-native execution via **SSM** run document; confirm the
  **5-min hard TTL** teardown; a bounded derived run-status record crossing the RD-013
  Hub gate (a new envelope kind — a run *outcome*, NOT telemetry, NOT a verdict);
  tests; any new RD (e.g. the SSM run-document / artifact-delivery choice).
- **Out of scope / do NOT touch:** behavioral telemetry capture (syscalls/network/fs)
  — that is **2.4**; the parallel fork/orchestration of both lanes — **2.6**; the
  telemetry sanitization pipeline — **2.5**; the Hub verdict (a run is EVIDENCE); the
  static lane (2.1/2.2). Do NOT introduce Docker/containers on the detonation host
  (RD-001, terminology: instances are **ephemeral**, never "temporary").
- **Depends on:** **2.0 ✅** (hard gate — the VPC/launch-template/role/AMI/TTL 2.3
  runs on). Also gated by an **empty Validation Debt Register** (see gate role above).
- **Unblocks:** 2.4 (telemetry capture — no telemetry without a real run) and 2.6
  (the fork needs both lanes).
- **Roadmap position:** P2 dynamic lane; the first place ZTIE executes an artifact.

### Approach & Constraints

- **Expected true-state (STEP 0 re-confirms before any edit; trust `main` over this
  brief if they disagree):** 2.0 = ✅ (validated 2026-09-02, tag
  `restore/story-2.0-green`); 2.1 = ✅ (2026-09-01); **2.2 = 🟡 or ✅** depending on
  whether the stakeholder validated PR #48 — CHECK THIS; restore tags present:
  `restore/phase-1-green`, `restore/story-2.0-green`, `restore/story-2.1-green`.
  **PHANTOM-TAG WATCH-ITEM:** `restore/phase-2-floor-green` is referenced in `BOM.md`
  + `RUNBOOK.md` (A.4) as the Phase-2 floor restore point but **does NOT exist** in
  `git tag -l` — before relying on it as a rollback target, either the owner pushes
  the annotated tag on the A.4 status commit OR the docs are reconciled to
  `restore/story-2.1-green`. Confirm the Validation Debt Register state + that the G-3
  gate is in place; run `python3 scripts/check_docs.py` (expect PASS).
- **Approach:** (1) STEP 0; (2) confirm the register is empty (else finish the open
  validation first); (3) design the run record contract FIRST (contract-first — a new
  RD-013 envelope kind for the dynamic-run *outcome*, bounded, verdict-free); (4)
  build the pure logic (run-plan / outcome normalization) + thin seams (an `ec2`/`ssm`
  boto3 seam; the artifact-delivery mechanism) with the 2.1 pattern (a failure is
  recorded, never crashes the lane); (5) wire the Forensic dynamic-lane Lambda/step to
  the launch template; (6) the STAKEHOLDER validates live in Forensic; (7) record +
  flip ✅ (paired commit); PROJECT_PLAN ↔ RUNBOOK aligned; PR.
- **Roles:** the LIVE detonation run + teardown check is the **stakeholder's** action
  in the Forensic account (the executor has NO live creds); the **executor RECORDS**
  the returned output verbatim. Do NOT simulate/assume a live output.
- **Hard constraints:** NON-EXECUTING is OVER — this lane RUNS the artifact, but ONLY
  inside Forensic, ONLY on the ephemeral EC2, ONLY host-native via SSM, NEVER in the
  Hub, NEVER Docker. The 5-min hard TTL is mandatory and must be proven to fire.
  Evidence, never a verdict. Production code (no mock detonation). Docs first-class
  (RD-015), PR-reviewed.

### Validation Rationale & Compliance Mapping (REQUIRED — RD-014)

- **Rationale:** the dynamic lane is ZTIE's runtime-behavior assurance — it exercises
  a suspect artifact in a contained, disposable, network-isolated environment to
  produce runtime evidence that static analysis cannot.
- **Candidate control mappings** *(proposed; ratified on review):*

| Framework | Control ID | Control Name | Rationale | Status |
|-----------|-----------|--------------|-----------|--------|
| NIST 800-53 r5 | SC-44 | Detonation Chambers | 2.3 IS a detonation chamber: it executes suspect content in a contained environment | Proposed |
| NIST 800-53 r5 | SI-3 | Malicious Code Protection | Dynamic execution surfaces malicious runtime behavior a scanner misses | Proposed |
| NIST 800-53 r5 | SC-7 | Boundary Protection | Detonation runs only inside the isolated VPC (no IGW/NAT, no 0.0.0.0/0) — it cannot phone home | Proposed |
| NIST 800-53 r5 | SC-39 | Process Isolation | Each detonation is a fresh, disposable, ephemeral host that self-terminates (5-min TTL) | Proposed |
| NIST CSF | DE.CM-4 / DE.AE | Malicious code detected / anomalies analyzed | Runtime behavior is observed for detection | Proposed |
| ISO 27001:2022 | A.8.7 | Protection against malware | Contained execution to observe malware behavior | Proposed |
| ISO 27001:2022 | A.8.22 | Segregation of networks | The isolated VPC segregates the blast zone | Proposed |

- **Audit evidence produced:** the dated Validation Result in RUNBOOK 2.3; the derived
  run-outcome record on the Hub tracking record; logs showing a real EC2 launch,
  host-native SSM execution, and TTL teardown.

### Management-Artifact Obligations (REQUIRED — RD-015)

- [x] Story's brief + runbook entry updated (status 🟡, Validation Result pending, dates). Master table 2.3 → 🟡; Validation Debt Register now lists 2.3; STORY_DETAIL 2.3 rewritten to the "as built" + DoD form.
- [x] PROJECT_PLAN and RUNBOOK in exact alignment (RD-026 registered in PLAN; per-story status lives in the RUNBOOK single-pane, 2.3 = 🟡 there; the RD narrative + story detail agree).
- [x] Any new/changed registered decisions recorded; candidate control mappings (RD-014) recorded. **RD-026** added (SSM `AWS-RunShellScript` delivery/execution + the new verdict-free run-outcome contract; candidate mappings SC-44/SI-3/SC-7/SC-39, CSF DE.CM-4/DE.AE, ISO A.8.7/A.8.22 — all Proposed).
- [x] All doc changes PR-reviewed (branch `feature/story-2.3` + PR, never straight to main).
- [x] Governance kept restorable alongside the code (all on the one feature branch; restore tag `restore/story-2.3-green` applied on the paired status commit ON validation pass).
- [ ] On validation pass: record Validation Result + flip ✅ (paired commit). **PENDING the stakeholder's live run** (covenant — stays 🟡 until a recorded live pass).
- [x] Author the next-story handoff (2.4 telemetry capture) with real Lessons Learned.
- **Also fixed (RD-015 drift):** the G-3 `scripts/test_check_docs.py` fixtures were stale on `main` (they keyed off the pre-2.2-flip register `_(empty)_` placeholder + a `⬜` story 2.2 that is now ✅), so the governance self-tests were failing on a clean checkout. Repaired the fixture helpers to be state-independent (`_seed_open_debt` inserts after the register separator; `_set_story_status` targets a currently-`⬜` story `2.5`) so the G-3 tests pass again — management tooling held to the same bar as code.

### Change & Rollback

- **Change type:** normal (new dynamic-lane compute + a new contract; runs on 2.0 infra).
- **Restore point this builds from:** `restore/story-2.0-green` (see the phantom-tag
  watch-item above re: `restore/phase-2-floor-green`).
- **Backout plan:** if a check fails, 2.3 stays 🟡; fix + re-validate. If a status flip
  is later found unwarranted, revert the paired status commit + delete the tag. A
  detonation host that fails to terminate is a SEV finding — the TTL is the backstop.

### Definition of Done / Validation Gate

> A pass/fail gate, not a description. The stakeholder validates live; the executor
> records; only a recorded pass flips status.

- **Done means (the stakeholder confirms live in Forensic 360999005254):**
  1. A routed artifact triggers ONE **ephemeral EC2** launched **from the 2.0 launch
     template** (`ec2:RunInstances` via the template — not CloudFormation-per-run)
     into the **isolated VPC**.
  2. The artifact is delivered + executed **host-native via SSM** (run document /
     `SendCommand`) — **NO Docker/container** on the host (RD-001).
  3. The instance is **torn down by the 5-minute hard TTL** (`shutdown -h +5`) —
     confirm the instance is terminated on its own (the KNOWN CAVEAT: 2.0's UserData
     carries `shutdown -h +5`; if the instance is still running past the TTL, that is
     the finding — record it, do NOT pass the check).
  4. A bounded, derived **run-outcome record** crosses the RD-013 gate to the Hub
     (evidence, never a verdict — no verdict/safe/forward field).
- **Validated by:** the stakeholder, live; the executor records verbatim.
- **Validation Result:** `pending`.
- **On pass (and only then):** record the dated Validation Result, flip 2.3 ✅ (paired
  commit), keep PLAN ↔ RUNBOOK aligned; capture a restore point per the runbook.
- **On fail:** 2.3 stays 🟡; re-focus on fixing + re-validating; no advancement.
- **Advancement gate:** 2.3 depends on 2.0 ✅ (satisfied) AND an empty Validation Debt
  Register. It unblocks 2.4 + 2.6.

### Risks & Watch-Items

- **The register may be non-empty when 2.3 is picked up.** 2.2 (PR #48) is 🟡 pending
  live validation. Do NOT start 2.3 feature work while the register holds an open
  entry — finish that validation first (RD-023 gate).
- **Phantom tag `restore/phase-2-floor-green`** — referenced in BOM/RUNBOOK but not in
  `git tag -l`. Resolve (owner pushes it, or reconcile docs to
  `restore/story-2.1-green`) before treating "the Phase-2 floor" as a rollback target.
- **The TTL is the safety backstop — prove it fires.** An instance that outlives its
  TTL is the dangerous failure mode; do not pass check 3 on inference.
- **NO Docker on the detonation host (RD-001).** A container would distort behavioral
  telemetry (2.4) and violates the design. Host-native SSM only. Call the instances
  **ephemeral**, never "temporary."
- **Container-image deploy needs a Docker build box** (the recurring 2.1/2.2 lesson) —
  but that is only for the *static-scan* image; 2.3's compute may be a plain zip
  Lambda / Step Function, so confirm whether a build box is even needed.

### Lessons Learned / Carry-Forward *(from the Story 2.2 build session, 2026-09-03)*

- **Contract-first + pure-logic/thin-seam + evidence-never-verdict is the proven
  lane pattern** (1.2→2.2). 2.2's compliance mapping + signature engine are BOTH pure
  and offline-tested; AWS/real-tool paths sit behind thin seams and are live-only.
  Reuse this exactly for 2.3's run-plan/outcome logic vs. the `ec2`/`ssm` seam.
- **Additive contract version bumps work cleanly.** 2.2 bumped the findings + summary
  contracts to **v1.1** (accept `["1.0","1.1"]`, emit `1.1`). Key gotcha for 2.3's new
  contract: **the Hub gate pins each envelope kind's version SEPARATELY** — 2.2 added
  `SUMMARY_CONTRACT_VERSION` so the summary can be `1.1` while intake/classification/
  routing/reject stay `1.0`. A NEW dynamic-run envelope kind gets its OWN pin; do NOT
  reuse the shared `CONTRACT_VERSION`.
- **Regenerate schemas via the `gen_*` scripts into BOTH `schemas/` and the bundled
  copy, and hash-check** (fs_write refuses a remote `$schema`). One `additionalProperties`
  exception is documented (2.2's control-id→count maps use `additionalProperties:{int}`
  because keys are the framework catalogue) — keep any such exception explicit.
- **The offline proof bar (sandbox is INTEGRATIONS_ONLY — no boto3/pytest/moto/
  jsonschema/cdk):** stdlib `unittest` over fixtures (2.2 = 37 tests) + a **manual
  pure-Python conformance walk** proving the built docs satisfy the contracts when
  jsonschema isn't installable; `ruff` clean; `tsc --noEmit`/`prettier --check` show
  ONLY the environmental missing-`aws-cdk-lib`/`constructs`/`path`/`__dirname`/
  `env-on-Props` family (identical on the live stacks). The USER validates live.
- **Keep governance edits OFF the feature branch.** This session drifted into upgrading
  the prompt+brief templates (to the A.2 standard) and reconciling the A.2 brief; that
  was split onto its own branch (**PR #47**) so the 2.2 feature PR (**PR #48**) stayed
  clean. Do the same if 2.3 spawns unrelated governance work.
- **Two-account live reality (recurs EVERY session):** intake + all artifact-touching
  compute (incl. the detonation host) is in **Forensic 360999005254**; the durable
  tracking record is in the **Hub 641628980935**. Two CloudShell tabs; run
  `aws sts get-caller-identity` before EVERY operational block (the user has repeatedly
  run blocks in the wrong account). `gh pr create` is broken — open PRs via
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`.
- **2.0 facts 2.3 inherits (from the A.2 live validation, verified):** VpcId
  `vpc-0457ce09693cc48e4`; DetonationLaunchTemplateId `lt-045ddce7fdac386db` (`$Latest`
  ImageId `ami-040dc3b259ece28c6` == `/ztie/ami/ubuntu-22.04`, IMDSv2 required,
  t3.small); DetonationInstanceRole has `AmazonSSMManagedInstanceCore`; UserData carries
  `shutdown -h +5`; isolated VPC (no IGW/NAT, no `0.0.0.0/0`). **KNOWN infra gap:** the
  AL2023 AMI build FAILED and the Image Builder → SSM update automation is broken; only
  ubuntu-22.04 is set. If 2.3 needs a non-Ubuntu flavor, that gap must be fixed first.
- **RD-025 (2.2) precedent for a source-of-record decision:** 2.2 recorded its
  compliance-table + signature-ruleset as real, embedded, VERSIONED sources (not
  per-run guesses). 2.3 should likewise register its SSM run-document / artifact-
  delivery choice as an RD with candidate control mappings.
- **User notes:** *(open for the stakeholder to add anything before the 2.3 session.)*

> **Alternative next story (RD-024 — stakeholder decides):** if the stakeholder
> prefers to harden the floor before more pipeline, **B.1** (harvest inventory) is
> also eligible (dep A.4 ✅). 2.3 is the pipeline-forward choice; B.1 is the
> reuse/archive-forward choice. One line, one recommendation: *next up 2.3
> (detonation) — it is the load-bearing dynamic lane the rest of P2/P3 waits on —
> unless you want to pause and harvest first (B.1).*
