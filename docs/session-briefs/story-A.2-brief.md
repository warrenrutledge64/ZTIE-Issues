# Session Brief: Story A.2

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.

---

## Story A.2: Validate Story 2.0 live (clear the Validation Debt register)

| Field | Value |
|-------|-------|
| **Phase** | A (Finish & back up the Phase-2 floor) |
| **Date** | 2026-09-02 |
| **Status** | ✅ Done (validated) |
| **Builds from restore point** | `restore/story-2.1-green` |
| **Session goal** | Run the 7 Definition-of-Done checks for Story 2.0 live in the Forensic account (360999005254), record the dated Validation Result in RUNBOOK 2.0, flip 2.0 to ✅ with a paired status commit, REMOVE the 2.0 row from the Validation Debt register (this is how the register clears), and tag `restore/story-2.0-green`. |

---

### Background & Context

ZTIE tracks work as validation-gated stories: nothing is ✅ until a recorded live
pass (the covenant). Phase 1 is ✅; Phase 2 is mid-flight. **Story 2.1 is ✅
(validated live 2026-09-01)**; **Story 2.0 is 🟡 (built and deployed once, but never
live-validated)**. The just-completed governance story **G-3** installed a **hard
advancement gate**: no NEW feature story may start while the Validation Debt register
is non-empty, and the register was seeded with its single current entry, **2.0**. The
gate deliberately still permits reworking or validating an existing 🟡, because that
is precisely how the debt is meant to be cleared. Story A.2 is that clearing action:
it takes 2.0 through its own recorded live validation so the register empties and
feature work (2.2 and beyond) can resume.

**Why A.2 is the next story (the reasoning, recorded per the handoff covenant):** the
G-3 gate blocks 2.2, 2.3, and all new feature work while the register holds any entry.
The register's sole entry is 2.0. The register clears only when a story completes its
own recorded live validation and its row is removed. Therefore the ONLY forward move
that the gate permits is A.2, the register-clearing live validation of 2.0. This is
enumerated as the immediate actionable work in
[`docs/governance/FLOOR_AND_HARVEST_PLAN.md`](../governance/FLOOR_AND_HARVEST_PLAN.md)
§4 (Stories) and §6 (the 7 DoD checks). A.2 is register-CLEARING rework, which the
gate explicitly allows; it is NOT the start of a new feature story.

### What This Story Is (nature + gate role)

**Nature: DEBT-CLEARING / validation story** — NOT a new feature. A.2 takes the single
open Validation Debt entry (Story 2.0) through its own recorded live validation, then
removes its register row so the register empties. The G-3 hard advancement gate
explicitly PERMITS this (reworking/validating an existing 🟡 is how debt is cleared)
even though it blocks all new feature work while the register is non-empty.
**The category error to prevent:** A.2 CLEARS the gate; it does not walk through it —
do NOT open any new feature story (2.2+) in this session; that is a later session,
only once the register is empty.

### Objective & Value

- **Objective:** run the **7 DoD checks for Story 2.0** live in the Forensic account
  (360999005254), exactly as enumerated in `FLOOR_AND_HARVEST_PLAN.md` §6 (do not
  re-derive them). On all seven passing: record the dated Validation Result in the
  RUNBOOK 2.0 detail block, flip the 2.0 row 🟡 → ✅ (paired status commit), **remove
  the 2.0 row from the Validation Debt register** at the top of the RUNBOOK, and tag
  `restore/story-2.0-green`.
- **Why it matters:** 2.0 is the single open debt item and therefore the single thing
  the G-3 gate is holding the whole plan behind. Clearing it converts "built but
  unproven" into "recorded, provable, backed up," empties the register, and lifts the
  block on all downstream feature work. It also exercises the gate end-to-end for the
  first time, confirming the register clears the way G-3 designed it to.

### Scope, Dependencies & Position

- **In scope:** running the 7 DoD checks live (§6), recording the Validation Result
  line (dated) in RUNBOOK 2.0, flipping the 2.0 row to ✅ (paired commit), removing
  the 2.0 row from the Validation Debt register, tagging `restore/story-2.0-green`,
  and keeping PROJECT_PLAN ↔ RUNBOOK aligned.
- **Out of scope:** starting any NEW feature story (2.2+), which the gate forbids until
  the register is empty, and A.2 is what empties it; A.4 deployed-state capture (a
  separately-tracked activity that a story's ✅ is never held hostage to); the harvest
  inventory / archive work (Phases B/C). A.2 touches governance records only, no
  pipeline/infra/lambda code.
- **Depends on:** 2.0 built (it is) and the G-3 gate + register installed (they are).
  Builds from `restore/story-2.1-green`.
- **Unblocks:** an empty Validation Debt register, which re-opens feature work under
  the G-3 gate (A.3 confirm 2.1, A.4 capture, then eventually the next pipeline story
  the new way). _(Note added 2026-09-07 / Story A.5: this line originally said "2.2
  the new way"; 2.2 in fact shipped the old way 2026-09-03. Refined 2026-09-08 when
  A.5 executed: the interim "2.4/2.6" pair resolved to **Story 2.4** once 2.6 closed ✅
  2026-09-08 — see the Floor & Harvest Plan §2 Exit.)_
- **Roadmap position:** Phase A of the Floor & Harvest Plan; the first register-
  clearing action after the gate went live.

### Approach & Constraints

- **Expected true-state (STEP 0 re-confirms before any edit; trust `main` over this
  brief if they disagree):** 2.0 = 🟡 (built, deployed once, NEVER live-validated —
  the ONE open register entry, this session's target); 2.1 = ✅ (validated live
  2026-09-01); restore tags `restore/phase-1-green` + `restore/story-2.1-green` exist;
  deployed-state restore NOT yet captured (BOM ~11 pending rows;
  `feature/restore-targets-phase2` built but unmerged); the Validation Debt Register
  lists 2.0 as its single open entry and the G-3 hard advancement gate is in place;
  `python3 scripts/check_docs.py` exits 0 on the clean tree.
- **Approach:** (1) STEP 0 re-establish true state from `git`/RUNBOOK; (2) the
  stakeholder runs the 7 DoD checks in the Forensic CloudShell per §6 (STEP 0 code +
  account, then checks 1..7); (3) the executor RECORDS the returned results verbatim;
  (4) on all-pass, write the dated Validation Result in RUNBOOK 2.0, flip the row to
  ✅ (paired status commit), remove the 2.0 row from the Validation Debt register, and
  tag `restore/story-2.0-green`; (5) keep PROJECT_PLAN ↔ RUNBOOK aligned; open a PR.
- **Roles:** the **stakeholder** runs the 7 live checks in the Forensic CloudShell
  (the executor has NO live creds); the **executor RECORDS** the returned output
  verbatim. Do NOT simulate, assume, or fill in a live output.
- **Hard constraints:** **NEVER validate on inference.** The live AWS commands are the
  **stakeholder's action** (the executor has NO live creds); the executor only records
  the result the stakeholder returns. Do NOT flip 2.0 to ✅ or remove the register row
  until every one of the 7 checks has a recorded pass. Do NOT start any new feature
  story while the register is non-empty. Docs are first-class (RD-015): PR-reviewed,
  never straight to main.

### Validation Rationale & Compliance Mapping (REQUIRED, RD-014)

- **Rationale:** A.2 is the act of *assessing a built component against its stated
  controls and recording the result*, which is what closes the assurance loop the
  G-3 register opened. It converts unproven infrastructure into evidence-backed,
  restorable state.
- **Candidate control mappings** *(proposed; ratified on review):*

| Framework | Control ID | Control Name | Rationale | Status |
|-----------|-----------|--------------|-----------|--------|
| NIST 800-53 r5 | CA-2 | Control Assessments | A.2 IS the assessment: the 7 DoD checks assess 2.0's controls (network isolation, endpoints, IMDSv2, auto-shutdown, SSM role) against their intent, live | Proposed |
| NIST 800-53 r5 | CA-5 | Plan of Action & Milestones | Clearing the 2.0 register row is the POA&M item being closed with recorded evidence | Proposed |
| NIST 800-53 r5 | SC-7 | Boundary Protection | Checks 2 & 7 confirm the isolated VPC has no IGW/NAT and no `0.0.0.0/0` route | Proposed |
| NIST 800-53 r5 | CM-6 | Configuration Settings | Checks 3-6 confirm endpoints, AMI resolution, IMDSv2, and `shutdown -h +5` are configured as intended | Proposed |
| NIST CSF | ID.RA / PR.IP | Risk assessment / protective process validation | Live validation confirms the deployed control set matches the design | Proposed |
| ISO 27001:2022 | A.5.36 | Compliance with policies and standards | Recording the live pass enforces adherence to the validation covenant | Proposed |

- **Audit evidence produced:** the dated Validation Result line in RUNBOOK 2.0, the
  paired status commit flipping 2.0 ✅, the emptied Validation Debt register, and the
  `restore/story-2.0-green` tag.

### Management-Artifact Obligations (REQUIRED, RD-015)

- [x] Story's **brief + runbook entry** updated (2.0 Validation Result recorded; 2.0
      row flipped ✅ with Completed date and restore tag).
- [x] **Validation Debt register updated**: the 2.0 row REMOVED (the register clears
      by removing a cleared row, not by editing it in place). _(register now empty)_
- [x] **PROJECT_PLAN and RUNBOOK in exact alignment** (2.0's status matches in both).
- [x] Any **new/changed registered decisions** recorded; candidate control mappings
      (RD-014) recorded above. _(no new RD for A.2; the RD-014 mappings above stand.)_
- [x] All doc changes **PR-reviewed** (branch + PR, never straight to main).
      _(PR #39, branch docs/story-a2-validate-2.0.)_
- [x] Governance kept **restorable** alongside the code (`restore/story-2.0-green`
      tagged on the paired status commit).

### Change & Rollback

- **Change type:** standard (governance records + a live validation of already-
  deployed infra; no new infra/runtime change is authored by A.2).
- **Restore point this builds from:** `restore/story-2.1-green`.
- **Backout plan:** if any check fails, 2.0 stays 🟡, the register keeps its 2.0 row,
  and the session re-focuses on fixing 2.0 (or recording the finding). No status flip
  is made until all 7 pass. If a status flip is later found unwarranted, revert the
  paired status commit and delete the `restore/story-2.0-green` tag.

### Definition of Done / Validation Gate

> A pass/fail gate, not a description. The user validates live; the executor records
> the result; only a recorded pass flips status and clears the register.

- **Done means:** all **7 DoD checks in `FLOOR_AND_HARVEST_PLAN.md` §6** pass live in
  Forensic 360999005254:
  1. **Stack deploys:** `ZtieForensicInfraStack` deploys and returns its outputs
     (`VpcId`, `DetonationLaunchTemplateId`, `DetonationInstanceRoleArn`,
     `AmiParameterName`).
  2. **Isolated VPC (no IGW/NAT):** no internet gateway and no NAT gateway attached
     to the VPC.
  3. **VPC endpoints present:** S3 gateway endpoint plus the SSM, SSMMessages,
     EC2Messages, Logs, SQS, and Bedrock interface endpoints.
  4. **Launch template resolves a valid AMI via SSM:** `$Latest` version resolves an
     `ami-...` id (via `/ztie/ami/ubuntu-22.04`).
  5. **Instance role has `AmazonSSMManagedInstanceCore`** attached.
  6. **UserData has `shutdown -h +5`** (auto-terminate).
  7. **No `0.0.0.0/0` route** in any route table of the VPC.
  Then the Validation Result is recorded (dated), 2.0 flips ✅ (paired commit), the
  2.0 row is removed from the Validation Debt register, and `restore/story-2.0-green`
  is tagged.
- **Validated by:** the **stakeholder**, live in the Forensic CloudShell (the executor
  has no live creds). The executor records the returned result verbatim.
- **Validation Result:** `pass — all 7 DoD checks passed live in Forensic
  360999005254, 2026-09-02, confirmed by the stakeholder (VpcId=vpc-0457ce09693cc48e4,
  DetonationLaunchTemplateId=lt-045ddce7fdac386db, launch-template $Latest
  ImageId=ami-040dc3b259ece28c6 == /ztie/ami/ubuntu-22.04, IMDSv2 required, t3.small;
  isolated VPC no IGW/NAT; S3 gateway + SSM/SSMMessages/EC2Messages/Logs/SQS/
  Bedrock interface endpoints present; AmazonSSMManagedInstanceCore attached; UserData
  has shutdown -h +5; no 0.0.0.0/0 route). One pre-validation defect was fixed first
  (an SG-rule description carried a '>' outside AWS's allowed charset, failing the
  first deploy) and the FIXED code was validated. 2.0 flipped ✅, its Validation Debt
  row removed (register now empty), tag restore/story-2.0-green.`
- **On pass (and only then):** record the dated Validation Result in RUNBOOK 2.0, flip
  the row ✅ (paired status commit), remove the 2.0 row from the Validation Debt
  register, tag `restore/story-2.0-green`.
- **On fail:** 2.0 stays 🟡, its register row stays, the session re-focuses on fixing
  2.0 and re-validating; no advancement.
- **Advancement gate:** A.2 is register-clearing rework, which the G-3 gate permits.
  No NEW feature story may start until A.2 empties the register.

### Risks & Watch-Items

- **Do not flip 2.0 on inference.** The row flips ✅ and the register row is removed
  ONLY after every one of the 7 checks has a recorded live pass from the stakeholder.
  Recording an unverified pass is the exact drift the covenant forbids.
- **Executor has no live creds.** The 7 checks are the stakeholder's CloudShell action;
  the executor's job is to record, not to run them. Do not simulate or assume outputs.
- **Known AMI caveat (from §6):** the Ubuntu AMI was set manually earlier and the
  AL2023 build failed; 2.0 defaults to ubuntu-22.04, so check 4 should resolve. If
  `/ztie/ami/ubuntu-22.04` is empty, that is the finding: fix or record it, do not
  treat the check as passed.
- **Register clears by ROW REMOVAL.** The register is emptied by removing the 2.0 row,
  not by editing it to say "done." The G-3 CHECK A logic keys on 🟡/⛔ stories being
  present in the register; once 2.0 is ✅ it must not remain listed as open debt.
- **Do NOT open new feature work in the same session.** A.2 clears the gate; it does
  not walk through it. Starting 2.2 belongs to a later session, the new way.

### Lessons Learned / Carry-Forward *(from the G-3 session that authored this)*

- **The checker was built here, not deferred.** During G-3 the consistency checker was
  **IMPLEMENTED in `scripts/check_docs.py`** (Python 3.12, stdlib only,
  `unittest`-covered, ruff-clean) rather than left as a spec for G-2. It therefore
  **partially fulfills and overlaps G-2's `check_docs.py` remit**; G-2, when picked
  up, extends this same checker (plan/runbook divergence, dangling RD refs, stray
  placeholders, ✅-without-a-validation-line) rather than starting fresh.
- **The three enforcement artifacts now exist and are machine-enforced:** (1) the
  **Validation Debt register** at the RUNBOOK top, seeded with 2.0; (2) the **hard
  advancement-gate** clause (RUNBOOK gate + METHODOLOGY §4: no new feature story while
  the register is non-empty); (3) the **story-closure ≠ restore-point-work**
  decoupling (METHODOLOGY §4 + FLOOR_AND_HARVEST_PLAN §1). **RD-023** was recorded
  (candidate/proposed) in PROJECT_PLAN §5 with candidate RD-014 control mappings.
- **The gate now BLOCKS Story 2.2 and all new feature work** until 2.0 is validated,
  which is exactly why A.2 (register-clearing validation of 2.0) is the next story and
  not a new feature.
- **Current true state at authoring (2026-09-01):** **2.0 🟡** (the one open debt
  item), **2.1 ✅** (validated live 2026-09-01), restore tags `restore/phase-1-green`
  + `restore/story-2.1-green` exist, deployed-state restore NOT yet captured (BOM has
  ~11 `pending` rows; `feature/restore-targets-phase2` built but unmerged). Plan of
  record: `docs/governance/FLOOR_AND_HARVEST_PLAN.md`.
- **Watch-items discovered while building the checker:** (a) **CHECK A exempts G-\***
  governance stories, because the register tracks feature/floor debt, not the tooling story
  that installs the gate; (b) **CHECK B derives its pre-gate baseline** from
  `git show HEAD:RUNBOOK.md` and falls back to the working tree when there is no git
  history; (c) the **RUNBOOK status-table parser** keys off the
  `Story | Title | Depends on | Status` header and detects the status emoji by
  scanning the cell, so the repo-wide em dash convention in `Depends on` cells does
  not break parsing; (d) an empty `scripts/__init__.py` was added so
  `python -m unittest scripts.test_check_docs` runs from the repo root (verified it
  does not change `gen_*_contract.py` output).
- **Must-know / must-avoid for A.2:** A.2 does not touch pipeline/infra/lambda code;
  it records a live validation and clears the register. The 7 checks are the
  stakeholder's action; the executor records. Do not flip 2.0 or remove its register
  row until all 7 pass. Do not start any feature story until the register is empty.
- **User notes:** *(open for the stakeholder to add anything before the A.2 session.)*
