# Session Brief — Story 1.2

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.

---

## Story 1.2 — Preprocessor classifier (extension + metadata inspection)

| Field | Value |
|-------|-------|
| **Phase** | P1 — Intake & Routing |
| **Date** | _(set when the session starts)_ |
| **Status** | ⬜ Not Started |
| **Builds from restore point** | none yet (Phase-1 close captures the first tag, after 1.2/1.3/1.4 + validated 1.R) |
| **Session goal** | Build the `preprocessor` classifier: inspect each intake artifact's extension + metadata and classify it (IaC template vs raw script vs other/unknown), producing a classification the routing table (1.3) consumes. |

---

### Background & Context

Phase 1 is Intake & Routing. Story 1.1 (intake gateway) is ✅ and Story 1.1R
(durable record → Hub behind the RD-013 contract gate) is ✅. The artifact now
lands in Forensic S3 and its durable tracking record lives in the Hub. **1.2 is
the next build step**: the `preprocessor` classifies the received artifact so 1.3
can route it and 1.4 can safe-reject the unroutable. (1.R — the restore mechanism
— is built and 🟡 pending the user's live validation; it is the prerequisite for
the *Phase-1 close*, not for building 1.2. 1.2 depends on 1.1, which is ✅.)

### Objective & Value

- **Objective:** a `preprocessor` component that, given an intake record (the
  Forensic S3 object + the derived metadata), determines the artifact class:
  **IaC template** (e.g. CloudFormation YAML/JSON, Terraform), **raw script**
  (e.g. `.py`, `.sh`, `.js`), or **other/unknown**. Classification is by extension
  **and** content/metadata inspection (not extension alone — the claimed type is
  untrusted). Emits a structured classification result keyed by `intake_id`.
- **Why it matters:** classification is the fork point of the whole pipeline —
  everything downstream (static lane, dynamic lane, safe-reject) keys off it.

### Scope, Dependencies & Position

- **In scope:** the classifier logic + its wiring to the intake flow; a structured
  classification result (shape defined first — projection/contract-first). Real
  content/metadata inspection (magic bytes / structural sniffing), not just the
  claimed extension. Production code (no mocks in the execution path).
- **Out of scope:** the routing table itself (1.3), the safe-reject path (1.4),
  any static/dynamic scanning (Phase 2). Do NOT re-open the intake gateway (1.1)
  or the Hub contract gate (1.1R) beyond what classification needs.
- **Depends on:** **1.1 ✅** (intake exists). Does NOT depend on 1.R.
- **Unblocks:** 1.3 (routing) and 1.4 (safe-reject), which both key off the class.
- **Roadmap position:** the classify step of Phase 1; the fork the two Phase-2
  lanes hang off.

### Approach & Constraints

- **Approach:** contract-first — define the classification-result shape (a JSON
  Schema, like 1.1R's contract) BEFORE the code. Classify by extension **and**
  content inspection; where they disagree, treat the claimed type as untrusted and
  prefer the content signal (record both). Keep the classifier a pure, unit-
  testable function over (metadata, content-sniff) with a thin AWS wiring layer.
- **Hard constraints:** **Python 3.12** (project standard). **Production code** —
  real inspection, real error handling, no placeholder classifiers. AWS-native.
  Zero-trust: the classifier never marks an artifact "safe" or forwards it — it
  only labels the class. **Validation-gated**: the user validates live and the
  result is recorded in RUNBOOK.md.

### Validation Rationale & Compliance Mapping (REQUIRED — RD-014)

- **Rationale:** correct classification is an input-validation / integrity control
  — it is how the pipeline decides which controls apply to an artifact.
- **Candidate control mappings** *(candidate-until-ratified; also add ratified rows
  to [`../COMPLIANCE.md`](../COMPLIANCE.md)):*

| Framework | Control ID | Control Name | Rationale | Status |
|-----------|-----------|--------------|-----------|--------|
| NIST 800-53 r5 | SI-10 | Information Input Validation | Classifies/validates the artifact type before processing | Proposed |
| NIST 800-53 r5 | SI-3 | Malicious Code Protection | Content sniffing distrusts the claimed extension | Proposed |
| NIST 800-53 r5 | CM-8 | System Component Inventory | Records the artifact class as tracked metadata | Proposed |
| ISO 27001:2022 | A.8.26 | Application security requirements | Validated input handling | Proposed |

- **Audit evidence produced:** the classification result records + the live
  validation run.

### Management-Artifact Obligations (REQUIRED — RD-015)

- [ ] Story's **brief + runbook entry** updated (status, validation result, dates).
- [ ] **PROJECT_PLAN and RUNBOOK in exact alignment**.
- [ ] Candidate control mappings recorded (RD-014).
- [ ] All doc changes **PR-reviewed** (branch + PR, never straight to main).
- [ ] If 1.2 closes any live state that should be restorable, it is reflected in
      `BOM.md` and captured via `ztie-restore` at the next phase close.

### Change & Rollback

- **Change type:** normal (adds the `preprocessor` classifier + its contract).
- **Restore point this builds from:** none (Phase-1 close is later).
- **Backout plan:** revert the merged PR; the classifier is additive and does not
  mutate the intake path's persisted data.

### Definition of Done / Validation Gate

- **Done means:** the user, live, confirms: a known **IaC template** artifact and
  a known **raw script** artifact are each classified **correctly**, and their
  classification is recorded/queryable keyed by `intake_id`; an artifact whose
  claimed extension disagrees with its content is classified by content (the
  distrust-the-claim behavior is demonstrated).
- **Validated by:** the user, live (Forensic intake → classification).
- **Validation Result:** _pending._
- **On pass (and only then):** record the dated Validation Result + flip 1.2 ✅.
- **On fail:** stays 🟡; next session re-focuses on 1.2.
- **Advancement gate:** blocks 1.3 and 1.4 (both key off the class).

### Risks & Watch-Items

- **Distrust the claimed type** — the intake body is stored as
  `application/octet-stream` with the claimed type kept only as metadata (1.1).
  The classifier must inspect actual content, not trust the extension/claim.
- **Contract-first pays off** — define the classification-result JSON Schema first
  (the 1.1R + 1.R lesson: write the shape, then the code falls out).
- **Zero-trust boundary** — classification is a label, NOT a safety verdict and
  NOT a forward decision. The verdict stays Hub-side/human-gated (Phase 4).
- **Production code** — no mock classifiers; real sniffing + real error handling.

### Lessons Learned / Carry-Forward *(carried from the Story 1.R build session, 2026-08-25)*

- **From 1.R — what to reuse:**
  - **Projection/contract-first works (again).** 1.R defined the manifest
    projection shape first and capture/verify/restore fell out of it cleanly. For
    1.2, define the **classification-result schema first**, then write the
    classifier against it.
  - **Pure-logic split for offline testability.** 1.R put all boto3 behind a thin
    `awsio` layer and kept the real logic (`projection.py`, `confirm.py`) pure, so
    it could be unit-tested with **stdlib `unittest`** in the INTEGRATIONS_ONLY
    sandbox (14 tests, no PyPI). Do the same for 1.2: keep the classifier a pure
    function; put S3/DynamoDB access behind a thin layer; write `unittest` tests
    that run offline AND under `pytest` live.
  - **Local guardrails that DO work offline:** `python3 -m py_compile`,
    `~/.pyenv/versions/3.12.13/bin/ruff`, and `prettier` via `npx --no-install`
    **after `unset NODE_OPTIONS`**. Ruff's default set does **not** enable
    `E402`/`PLC0415`, and it flags `BLE001` (blind-except) — use the correct code
    if you add an intentional `except Exception` (`# noqa: BLE001`), and don't add
    noqa for rules that aren't enabled (ruff reports them as unused `RUF100`).
- **From 1.R — environment truths (unchanged):**
  - Sandbox is **INTEGRATIONS_ONLY**: **PyPI and npm are blocked**. You cannot run
    `pytest`/`moto`/`boto3`/`cdk`/`tsc` here. Build + hand off; the USER validates
    live. Do NOT claim tests/synth/deploy pass from the sandbox.
  - `fs_write` refuses files containing a remote `$schema` URL — write the
    classification-result schema via a `python json.dump` step (as 1.1R and 1.R
    did for their schemas).
- **From 1.R — the true state you inherit:**
  - **1.R is built + on `feature/story-1.R` (PR #15 open), 🟡 pending the user's
    live capture→change→restore validation.** It is the prerequisite for the
    **Phase-1 close**, not for 1.2. If, by the time 1.2 starts, the user has
    confirmed 1.R live, first **close out 1.R** (record the dated Validation Result
    + flip 🟡 → ✅ via a small paired status commit/PR) before building 1.2.
  - `ztie-restore` (`scripts/ztie_restore/` + `scripts/ztie-restore`) is the
    restore tool: `capture` (read-only manifest), `verify` (projection diff),
    `restore` (confirm-gated, re-applies CFN template+params+**tags** + SSM).
    RESTORE.md + BOM.md are filled for the real deployed ZTIE.
  - Deployed P1 resources (from 1.1/1.1R): **Hub** `ZtieHubTrackingStack` (tracking
    DynamoDB, ingest SQS + DLQ, validator Lambda, quarantine S3); **Forensic**
    `ZtieIntakeStack` (intake API, intake Lambda, artifact S3; NO DynamoDB). The
    intake Lambda is where classification most naturally hooks in (or a new
    preprocessor Lambda downstream of it) — decide with the routing (1.3) shape in
    mind so classify→route compose cleanly.
  - `git` truth at handoff: `main` clean, all prior PRs merged EXCEPT **PR #15
    (1.R)** which is open. Re-run STEP 0 at session start to reconfirm.
- **Must-know / must-avoid for the 1.2 session:**
  - Classify by **content**, not the (untrusted) claimed extension; record both.
  - Contract-first + pure-logic + stdlib-`unittest` (offline provable).
  - Classification is a label, never a safety verdict / forward decision.
  - The status flip 🟡 → ✅ rides a **separate paired status commit** after the
    user's confirmed live pass. Do NOT flip on inference.
- **User notes:** _(open for the user)_
