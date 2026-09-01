# Session Brief — Story 1.R

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.

---

## Story 1.R — Restore-point mechanism (state-capture + coordinated restore)

| Field | Value |
|-------|-------|
| **Phase** | P1 — Intake & Routing (prerequisite for the Phase-1 close) |
| **Date** | 2026-08-25 (built + validated live) |
| **Status** | ✅ Done (validated live 2026-08-25) |
| **Builds from restore point** | none yet (this story CREATES the mechanism) |
| **Session goal** | Build the Python state-capture + coordinated-restore tooling, fill `RESTORE.md` + `BOM.md`, and validate a live capture→change→restore cycle — the thing that lets `restore/phase-1-green` be captured at the P1 gate. |

---

### Background & Context

Phase 1 cannot close until a **restore-point mechanism** exists and passes a live
capture→change→restore test (that is the P1 gate's extra requirement). Story 1.1 is
✅ and Story 1.1R (durable record → Hub behind the RD-013 contract gate) is
built/🟡 pending live validation. 1.R should be built to capture the **final**
Forensic→Hub topology, so it must land **after 1.1R is validated ✅** (don't snapshot
the pre-remediation shape).

### Objective & Value

- **Objective:** A **Python** tool that (a) captures a **restore-relevant projection**
  of durable state to a timestamped manifest, and (b) performs a **coordinated
  restore** back to a manifest; plus filled-in `RESTORE.md` (procedures) and `BOM.md`
  (the real deployed inventory). Per **RD-015**, the manifest also **pins the
  known-good governance-doc commit** so code + state + governance restore as one unit.
- **Why it matters:** It is the safety net for the whole project — "revert rather
  than forward-patch" only works if there is a known-good point to revert to. It is
  the literal prerequisite for closing Phase 1.

### Scope, Dependencies & Position

- **In scope:**
  - Python state-capture (read-only) capturing a **projection** (identity +
    desired-state fields only) for: the **Hub** durable DynamoDB tracking table, the
    CloudFormation stacks (`ZtieHubTrackingStack`, `ZtieIntakeStack`) incl.
    template SHA + parameters + **stack-level tags**, S3 config, Lambda
    name/runtime/`code_sha256`, and any SSM params. **Never** capture raw resource
    objects (avoids false-positive drift).
  - Python coordinated restore: re-apply captured state (CloudFormation
    `deploy` must re-apply template + parameters + **tags**); any mutating action is
    gated behind a deliberate confirm using **`input()`** that **fails safe to NO**.
  - Fill `RESTORE.md` (capture + restore procedures) and `BOM.md` (real inventory).
  - Pin the known-good **governance-doc commit** in the manifest (RD-015).
- **Out of scope:** the classifier (1.2), routing (1.3), safe-reject (1.4). Restoring
  Forensic's **ephemeral** raw-payload/scratch (it is disposable — rebuilt, not
  restored). The G-2 doc-consistency checker (separate governance story, though 1.R
  coordinates the governance-commit pin with it).
- **Depends on:** **1.1R ✅** (capture the final Forensic→Hub topology). Hard gate:
  do not start until 1.1R is ✅.
- **Unblocks:** the **Phase 1 close** (`restore/phase-1-green` tag + manifest).
- **Roadmap position:** last Phase-1 foundation before the P1 gate.

### Approach & Constraints

- **Approach:** `scripts/` Python CLI: `capture` → timestamped JSON manifest;
  `restore <manifest>` → confirm gate (`input()`, fail-safe NO) → re-apply →
  `verify` compares only the **restore-relevant projection**.
- **Hard constraints:** **Python-first** (the user explicitly moved restore tooling
  off Bash — interactive gate via `input()`, no `/dev/tty` fiddliness). The verify
  must compare a **projection**, not raw objects (SSM version bumps, CFN
  status/last_updated, stack_id-on-recreate, Lambda ordering all legitimately change
  and would otherwise false-positive). CloudFormation restore must re-apply
  **stack-level tags**, not just template+parameters. Read-only capture; mutating
  restore behind a fail-safe-NO confirm. AWS-native.

### Validation Rationale & Compliance Mapping (REQUIRED — RD-014)

- **Rationale:** Restorability + a durable BOM are contingency/recovery and
  configuration-integrity controls.
- **Candidate control mappings** *(candidate-until-ratified; also add ratified rows
  to [`../COMPLIANCE.md`](../COMPLIANCE.md)):*

| Framework | Control ID | Control Name | Rationale | Status |
|-----------|-----------|--------------|-----------|--------|
| NIST 800-53 r5 | CP-9 | System Backup | Captures a restorable projection of durable state | Proposed |
| NIST 800-53 r5 | CP-10 | System Recovery and Reconstitution | Coordinated restore back to a known-good manifest | Proposed |
| NIST 800-53 r5 | CM-2 | Baseline Configuration | The manifest + BOM are the recorded known-good baseline | Proposed |
| NIST 800-53 r5 | CM-8 | System Component Inventory | `BOM.md` is the deployed inventory | Proposed |
| ISO 27001:2022 | A.8.13 | Information backup | Backup/restore of durable state | Proposed |
| ISO 27001:2022 | A.8.9 | Configuration management | Baseline + inventory | Proposed |

- **Audit evidence produced:** the timestamped manifest, `RESTORE.md`, `BOM.md`.

### Management-Artifact Obligations (REQUIRED — RD-015)

- [x] Story's **brief + runbook entry** updated (status → 🟡, date; validation
      result stays *pending* until the user's live pass).
- [x] **PROJECT_PLAN and RUNBOOK in exact alignment** (both carry 1.R as the P1
      restore-mechanism prerequisite; no story-set drift introduced).
- [x] Candidate control mappings recorded (RD-014) — CP-9/CP-10/CM-2/CM-8, ISO
      A.8.13/A.8.9 (in the table above; proposed-until-ratified).
- [x] All doc changes **PR-reviewed** (branch `feature/story-1.R` + PR #15; never
      straight to main).
- [x] The manifest **pins the governance-doc commit** (`governance_commit.sha` +
      branch + `dirty` flag) so governance is restorable alongside code + state —
      the concrete RD-015 mechanism 1.R delivers (`ztie_restore/manifest.py`).

### Change & Rollback

- **Change type:** normal (adds `scripts/` tooling; fills `RESTORE.md` + `BOM.md`).
- **Restore point this builds from:** none (it builds the mechanism).
- **Backout plan:** revert the merged PR; the tooling is read-only except the
  explicitly-confirmed restore path.

### Definition of Done / Validation Gate

- **Done means:** the user, live, confirms: capture the current state to a
  timestamped manifest; make a trivial deliberate change; run the coordinated
  restore back to the manifest; confirm the **restore-relevant projection** matches
  (no false drift) and `BOM.md` reflects reality; the confirm gate demonstrably
  fails safe to NO on empty/negative input.
- **Validated by:** the user, live (Hub account 641628980935, us-east-1).
- **Validation Result:** pass — 2026-08-25, confirmed by the user. capture (4
  projections + governance-commit pin) → no-change verify MATCH → deliberate tag
  change verify DRIFT (exit 3) → coordinated restore (template+params+**tags**) →
  post-restore verify MATCH → confirm gate fails safe to NO on non-affirmative
  input (exit 4) and `ZTIE_ASSUME_NO=1` overrides `--yes`. Full record in
  [`../../RUNBOOK.md`](../../RUNBOOK.md) (story 1.R Validation Result).
- **On pass (and only then):** record the dated Validation Result + flip 1.R ✅.
  Then — since 1.R is the last piece before the P1 gate — the **Phase-1 close**
  proceeds separately (feed representative artifacts through routing once 1.2/1.3/1.4
  exist; only then capture `restore/phase-1-green`).
- **On fail:** stays 🟡; next session re-focuses on 1.R.
- **Advancement gate:** depends on 1.1R ✅; is itself the prerequisite for the P1 close.

### Risks & Watch-Items

- **Projection, not raw objects** — the #1 restore lesson: SSM parameter version
  bumps, SSM `last_modified_utc`, CFN stack status (CREATE vs UPDATE_COMPLETE),
  `last_updated_utc`, and `stack_id` on recreate all change on any successful deploy
  and will false-positive a naive diff. Compare: SSM name/type/value/secure; CFN
  name/template_sha256/parameters/tags; Lambda name/runtime/code_sha256 (sorted);
  DynamoDB table config projection.
- **CFN tags** — `aws cloudformation deploy --tags` must re-apply stack-level tags or
  the restored stack loses them and correctly fails the projected verify.
- **Python interactive gate** — use `input()`; fail safe to NO on empty/negative.
  (The user explicitly moved restore tooling off Bash for exactly this reason.)
- **Capture the FINAL topology** — only build/validate 1.R after 1.1R is ✅, so the
  manifest reflects the Hub-durable/Forensic-ephemeral shape, not the old one.
- **INTEGRATIONS_ONLY sandbox** — build + hand off; the user runs capture/restore live.

### Lessons Learned / Carry-Forward *(carried from the Story 1.1R build session, 2026-08-24)*

- **From 1.1R — what to reuse:**
  - **Contract-first / projection-first thinking works.** 1.1R wrote the JSON Schema
    first and everything fell out of it. For 1.R, define the **manifest projection
    shape first** (exactly which identity + desired-state fields per resource type),
    then write capture/restore/verify against it.
  - **Local guardrails that DO work offline:** `~/.pyenv/versions/3.12.13/bin/ruff`,
    `python3 -m py_compile`, and `prettier` via `npx --no-install` **after
    `unset NODE_OPTIONS`**. Use them; they're the only local proof available.
- **From 1.1R — environment truths (unchanged):**
  - Sandbox is **INTEGRATIONS_ONLY**: **PyPI and npm are blocked**. You cannot run
    `pytest`/`moto`/`cdk`/`tsc` here. Build + hand off; the USER validates live. Do
    NOT claim tests/synth/deploy pass from the sandbox.
  - `fs_write` refuses files containing a remote `$schema` URL — if 1.R emits a
    manifest schema, write it via a `python json.dump` step (as 1.1R did).
- **From 1.1R — the true state you inherit:**
  - 1.1R is **built + on `feature/story-1.1R` (PR open), 🟡 pending live**. The
    durable record only actually moves to the Hub once **both** stacks are deployed
    (Hub first, then Forensic wired with the Hub queue URL/ARN via `-c` context) and
    the four DoD checks pass. **1.R must not start until 1.1R is ✅.**
  - New live resources 1.R must inventory once 1.1R is deployed: **Hub** —
    `ZtieHubTrackingStack` (tracking DynamoDB, ingest SQS queue + DLQ, validator
    Lambda, quarantine S3); **Forensic** — `ZtieIntakeStack` (API GW, intake Lambda,
    artifact S3; **no** DynamoDB any more).
  - `git` truth at handoff: `main` clean, all prior PRs merged; 1.1R is the only open
    PR. Re-run STEP 0 at session start to reconfirm.
- **Must-know / must-avoid for the 1.R session:**
  - Verify against a **projection**; re-apply CFN **tags**; **Python `input()`**
    fail-safe-NO gate. These three are the exact things that bit the earlier Bash
    restore attempt — do not reintroduce them.
  - The status flip 🟡 → ✅ rides a **separate paired status commit** after the
    user's confirmed live pass.
- **User notes:** _(open for the user)_
