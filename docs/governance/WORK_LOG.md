# Work Log - the AI's running list of "next up" recommendations

> A lightweight, dated log of the AI's recommendations under the operating model in
> [`OPERATING_MODEL.md`](OPERATING_MODEL.md). Each entry is a **proposal** the AI
> hands over: one recommended next piece of work, a one-line reason, and a status of
> what the stakeholder decided. **Entries here never change a story's status and
> never clear validation debt**: the source of truth for status stays
> [`../../RUNBOOK.md`](../../RUNBOOK.md). This log only records what was recommended
> and what was decided.
>
> Status values for a log entry: `awaiting-user-decision` · `accepted` ·
> `not-yet` · `superseded`.

---

## 2026-09-16 - Recommendation N+4: 2.4R FAIL #3 — %desc theory falsified; reassess as SSM 24KB truncation; confirm before 4th fix

| Field | Value |
|-------|-------|
| **Recommended next** | STOP guessing at strace flags. Fetch `runs/<intake>/detonation-output.json` to CONFIRM the 24 KB SSM inline-stdout truncation theory; if confirmed, the 4th fix is ARCHITECTURAL — deliver the trace via Forensic S3, not inline SSM stdout. Keep 2.4R 🟡. |
| **One-line reason** | v3 dropped `%desc` and STILL `capture_error` + the self-diagnostic didn't fire ⇒ the failure is in the TRANSPORT (24 KB SSM stdout cap drops the trace), not the strace invocation. |
| **Status** | `awaiting-user-decision` — evidence in [`../validation-evidence/2.4R/attempt-3/`](../validation-evidence/2.4R/attempt-3/EVIDENCE.md); 2.4R stays 🟡 (no ✅; gate ARMED). Code fix HELD pending confirmation. |

### What happened (scribe record — status stays in RUNBOOK)

- **v3 (PR #176, main `8cd0e2b`) re-validated live, 2026-09-16, intake `0ad74eb4-...`:** same `capture_error` / generic reason; self-diagnostic marker did NOT fire.
- **The `%desc` theory (attempt 2) is FALSIFIED** — recorded honestly. Removing `%desc` changed nothing.
- **Reassessed prime suspect:** the trace is shipped inline in SSM `StandardOutputContent` (24,000-char cap; `send_command` sets no `--output-s3-bucket-name`). Verbose pre-trace output pushes the `begin` marker + trace + the self-diagnostic past the cut, so `slice_trace` sees no usable trace. Content/size changes (all three attempts) can't fix a transport that drops by size.
- **Discipline correction:** three fixes have now been shipped against a live-only symptom on strace-flag theories. Halting the guess-and-ship loop: the executor requested `detonation-output.json` (its `stdout` should be ~24000 chars and missing the markers) to CONFIRM before building the architectural (trace-via-S3) fix. This is the covenant working — three adversarial live runs kept a broken capture out of ✅.

---

## 2026-09-16 - Recommendation N+3: 2.4R capture-error re-fix BUILT + offline-proven — re-validate live

| Field | Value |
|-------|-------|
| **Recommended next** | Merge the capture-error re-fix PR, then re-run the split-brain live validation against the new post-fix main tip. Keep 2.4R 🟡. |
| **One-line reason** | Root cause of FAIL #2 confirmed (`%desc` rejected by the AMI strace); the re-fix names the write syscalls explicitly + makes a no-trace capture self-diagnosing, and is offline-proven. |
| **Status** | `awaiting-user-decision` — re-fix built + offline-proven on branch `fix/story-2.4R-capture-error`; 2.4R stays 🟡 (no ✅; gate ARMED). |

### What was built (scribe/build record — status stays in RUNBOOK)

- **Root cause confirmed:** attempt-1's trace (`%file,%network,%process,%signal`) produced a rich trace, so the AMI strace accepts those `%`-classes; attempt-2 added only `%desc` and got zero trace ⇒ `%desc` specifically is rejected by the AMI's strace build (strace exits before writing any `-ff` file ⇒ empty between markers ⇒ `capture_error`).
- **Correction to the FAIL-#2 note:** the strace stderr was NOT lost — the full host output (stdout+stderr) is retained at `runs/<intake>/detonation-output.json`; the `run.log` 404 was a wrong-key fetch. Real gap was that the crossed Hub record didn't surface the reason.
- **Re-fix (capturespec.py + handler.py):** (a) write capture by EXPLICIT syscall name (`write,writev,pwrite64`) appended to the proven-accepted `%`-classes — no `%desc`; (b) strace stderr redirected to a host file + a self-diagnosing no-trace path that surfaces that stderr as the `capture_error` reason on the crossed record.
- **Offline bar green:** `test_capturespec` OK(25) + `test_behavior` OK(15), full detonation suite OK(133/18 skips), ruff clean, contract no-drift, `tsc` unchanged, `check_docs` PASS + `test_check_docs` OK(24); plus a fake-strace behavioral proof of both the write-capture and strace-reject-diagnostic paths.
- **Covenant:** two adversarial live runs have now caught two real regressions before any ✅. 2.4R stays 🟡; re-validation of the re-fixed code is the only path to ✅.

---

## 2026-09-16 - Recommendation N+2: 2.4R re-validation FAILED again (capture_error) — re-fix, do not close

| Field | Value |
|-------|-------|
| **Recommended next** | Re-fix the capture (robust strace groups + a self-diagnosing no-trace path), prove offline, then re-validate live. Keep 2.4R 🟡. |
| **One-line reason** | The PR #175 fixes shipped, but the live re-run of the fixed code produced a TOTAL capture failure (`capture_error`, no trace) — prime suspect the new `%desc` group is rejected by the AMI's strace, and the no-trace path is blind to why. |
| **Status** | `accepted` — evidence retained in [`../validation-evidence/2.4R/attempt-2/`](../validation-evidence/2.4R/attempt-2/EVIDENCE.md); 2.4R stays 🟡 (Kiro did NOT flip ✅; gate ARMED). |

### What happened (scribe record — status stays in RUNBOOK)

- **Live re-run of the FIXED code (PR #175, main `bdc7a68`), 2026-09-16.** Intake `528c0ad1-8285-46fa-8327-48f424d3ca4d`. Result: `capture_status: capture_error`, `error_reason: "no behavioral trace emitted between capture markers"`, S3 `run.log` 404. The ~126 s window shows the artifact ran; strace produced no per-PID files.
- **This is a NEW failure mode introduced by the rework**, not the attempt-1 defect. The attempt-1 fixes (`%desc` write capture, per-PID cap) were correct in intent, but adding `%desc` to the combined `-e trace=` list appears to be rejected by the golden AMI's strace, zeroing the whole capture. The offline bar could not catch it (it only checks the command string).
- **Lesson (folding forward):** a strace-invocation change is a live-only risk; ship it with a fallback + surface the strace stderr so a no-trace run self-diagnoses instead of failing blind. The re-fix does exactly that.
- **Covenant working:** an adversarial live run caught a real regression before any ✅. 2.4R stays 🟡; the re-fix + re-validation is the only path to ✅.

---

## 2026-09-16 - Recommendation N+1: 2.4R rework BUILT + offline-proven — re-validate live next

| Field | Value |
|-------|-------|
| **Recommended next** | Re-run the 2.4R split-brain live validation against the FIXED code (branch/PR `fix/story-2.4R`) using the refreshed validation package; keep 2.4R 🟡 until it earns a recorded live PASS. |
| **One-line reason** | The three FAIL defects are fixed in `capturespec.py` and offline-proven; only a fresh live pass of the fixed code (with retained evidence) can clear the register. |
| **Status** | `awaiting-user-decision` — fixes built + offline-proven; 2.4R **stays 🟡** on the Validation Debt Register (Kiro did NOT flip ✅; gate stays ARMED). |

### What was built (scribe/build record — status stays in RUNBOOK)

- **Fix is entirely in `lambdas/detonation/capturespec.py`** (the `behavior.py` parser was already correct). **(1)** strace now traces `%desc` (fd-based `write`/`writev`/`pwrite64`) so a planted write buffer is captured — the DoD-1 defect. **(2)** the on-host emit caps EACH per-PID trace file independently (128 KiB) + numeric per-PID sort, 512 KiB overall backstop, so a noisy sibling PID can't truncate the artifact's own trace out. **(3)** network is an artifact fix (real `bash` `connect()`, not `dash` `/dev/tcp`) — carried in the refreshed validation package's BLOCK 4; no parser change.
- **Offline bar green:** `test_capturespec` OK(19) + `test_behavior` OK(15) with new regressions, full detonation suite OK(93/18 skips), ruff clean, contract no-drift, `tsc` unchanged, `check_docs` PASS + `test_check_docs` OK(24).
- **Refreshed** `docs/session-briefs/story-2.4R-VALIDATION-PACKAGE.md`: re-points the STEP 1/1.5 fetch to the 2.4R rework PR + POST-FIX main tip (no hardcoded stale SHA), adds the new test files to the full-context fetch, and rewrites BLOCK 4 to write a planted greppable buffer + issue a real `bash` `connect()`; BLOCK 6 now greps for the buffer (must be PRESENT in the raw trace, ABSENT from the Hub record) and a real `connect()`.
- **Covenant:** this is fix-then-validate-once. 2.4R is not ✅ and does not leave the register until the fixed code passes live under the split-brain protocol with its own retained RD-054 evidence.

---

## 2026-09-16 - Recommendation N: 2.4R live validation returned FAIL — fix-forward, do not close

| Field | Value |
|-------|-------|
| **Recommended next** | Record the 2.4R **SEALED VERDICT: FAIL** and its retained evidence; keep 2.4R 🟡; the next forward move is the 2.4R rework (fix-then-validate-once), NOT any new feature story. |
| **One-line reason** | The adversarial 2.4R run exposed real defects (strace missed the planted write buffer; the DoD-3 verdict-field probe hit the concurrent Phase-3 advisory fields), so 2.4R must be fixed and re-validated — the gate stays ARMED. |
| **Status** | `accepted` — evidence retained in [`../validation-evidence/2.4R/`](../validation-evidence/2.4R/EVIDENCE.md); 2.4R stays 🟡 on the Validation Debt Register; Kiro (scribe) did NOT flip ✅. |

### What happened (scribe record — status stays in RUNBOOK)

- **Live run, split-brain (RD-053/054), 2026-09-16.** Intake `2b0af6a6-6552-461f-a18f-f6cca60ba0bc`, code under test commit `566e274`, Forensic `360999005254` / Hub `641628980935`. The independent validator (Gemini) adjudicated **FAIL**.
- **DoD 1 FAIL** — the raw Forensic strace trace completely missed the planted write buffer `ZTIE-EVIL-BUFFER-DATA` (no `write()` syscall captured; strace `-e trace=` omits the write-class syscalls). **DoD 2 PASS** (no leakage, but hollow — never captured). **DoD 3 FAIL** — the evidence-only verdict-field probe hit `recommended_verdict`/`verdict_result`/`verdict_at`, written by the concurrent Phase-3 `hub_verdict` (RD-040) stage. **DoD 4** satisfied by the committed evidence folder.
- **This is the covenant working, not failing.** An adversarial validation caught real capture gaps before any ✅. 2.4R stays 🟡; the fix-forward items (write-class strace capture; the `cat|sort` concatenation/child-follow/512KB-truncation ordering defect; a real-`connect()` network artifact; scoping the DoD-3 probe to the `behavior` attribute) are recorded in RUNBOOK + STORY_DETAIL + the evidence `EVIDENCE.md`. A future PASS needs a fresh live run of the FIXED code with its own retained evidence.

---

## 2026-09-01 - Recommendation 1: validate and harden story 2.0 (the containment wall)

| Field | Value |
|-------|-------|
| **Recommended next** | Validate story **2.0** live, and harden what it proves, before anything detonates on top of it. |
| **One-line reason** | 2.0 is the single built-but-unproven, load-bearing piece, and every dangerous Phase-2 step (2.3 detonation onward) sits directly on it. |
| **Status** | `accepted` — Story 2.0 validated live 2026-09-02 (Story A.2, all 7 DoD checks passed in Forensic); 2.0 flipped ✅ and cleared from the Validation Debt Register. The "prove the negatives too" hardening addition remains a standing proposal for a later session (not blocking). |

### Why this is the recommendation

- **2.0 is the single unproven load-bearing item.** It is built and was deployed
  once, but it has never been validated live, so it is the sole entry in the
  Validation Debt Register at the top of [`../../RUNBOOK.md`](../../RUNBOOK.md).
- **Everything dangerous sits on it.** The detonation line
  (`2.0 → 2.3 → 2.4 → 2.5`, see [`../BUILD_ORDER.md`](../BUILD_ORDER.md)) runs
  untrusted code inside the isolation that 2.0 builds. We should not let anything
  detonate on top of an unproven containment wall.
- **2.1 being done does not cover it.** Story 2.1 is ✅, but 2.0 and 2.1 are
  independent siblings of 1.3, and finishing the static-scanning line proved nothing
  about the containment the detonation line depends on.
- **The gate points here anyway.** The Advancement Gate blocks new feature work
  while the register holds an entry; the only forward move it permits is clearing
  that entry, which means validating 2.0.

This lines up with the earlier warm hand-off in
[`../session-briefs/story-A.2-brief.md`](../session-briefs/story-A.2-brief.md)
(story A.2 is exactly "validate 2.0 live") and with the concrete checks already
written in [`FLOOR_AND_HARVEST_PLAN.md`](FLOOR_AND_HARVEST_PLAN.md) §6.

### What "validate" means here (and the hardening angle)

Story 2.0 already has **7 Definition-of-Done checks** written out in
[`FLOOR_AND_HARVEST_PLAN.md`](FLOOR_AND_HARVEST_PLAN.md) §6. Those checks confirm
that the containment controls are **present**:

- no internet gateway and no NAT gateway on the isolated VPC,
- no `0.0.0.0/0` (open-internet) route in any route table,
- VPC endpoints only (S3 plus the SSM / messaging / Logs / SQS / Bedrock
  interfaces),
- IMDSv2 required on the launch template,
- a 5-minute hard time-to-live (`shutdown -h +5`),
- a least-privilege PassRole for the instance role,
- the stack deploys and returns its outputs.

**The hardening angle (relay these; do not over-engineer):** where practical, a
hardened validation should **also confirm the absence of escape paths**, not just
the presence of controls. In plain terms, prove the negatives too:

- an instance in the detonation subnet **cannot reach the internet** (the isolation
  actually holds, not just that no gateway is configured),
- the instance role **cannot assume anything but its own** (no lateral escape via
  identity),
- the 5-minute TTL **actually terminates the instance** (the fail-safe truly
  fires).

This is an addition to the existing 7 checks, kept modest and practical; it is not
a redesign of story 2.0.

### Important: this is a proposal, not a change

- This entry is a **recommendation awaiting your decision** (go / not yet / do Z
  instead). It does **not** flip 2.0 to ✅ and does **not** remove 2.0 from the
  Validation Debt Register.
- The status only changes later, and only through the existing **Story Close-Out
  Procedure** in [`../../RUNBOOK.md`](../../RUNBOOK.md), after you confirm a live
  pass. Until then 2.0 stays 🟡 and the register keeps its 2.0 entry.
- The live checks are **your** action (you have the live access); the AI records
  what you confirm and never marks anything done on inference.

### Your decision

_Awaiting your call: **go** / **not yet** / **do Z instead**. Once you decide, this
entry's status will be updated and, on "go" and a recorded live pass, story 2.0 is
closed out via the RUNBOOK's Close-Out Procedure._


---

## 2026-09-02 - Recommendation 2: institute deployed-state restore points (A.4), after a quick A.3 confirm

| Field | Value |
|-------|-------|
| **Recommended next** | Confirm Story 2.1 into the floor (**A.3**, a paperwork confirmation — no re-run), then **institute deployed-state restore points (A.4)**: `capture` + `verify` for both accounts, commit the manifests, fill BOM's 11 `pending` rows, and tag `restore/phase-2-floor-green`. |
| **One-line reason** | With 2.0 ✅ and the Validation Debt Register empty, the Phase-2 floor is validated but **not yet backed up**; per the Floor & Harvest Plan (§2 Phase A, §4) the floor is only "set" once deployed-state restore points exist, and A.4 is the last step before the harvest inventory (B.1). |
| **Status** | `accepted` — completed 2026-09-02. A.1's substance (the `targets.py` post-2.1 extension) was re-applied onto latest `main` (PR #40, merged) rather than merging the stale `feature/restore-targets-phase2` branch (which would have reverted governance state — the base-branch trap). A.3 confirmed (2.1 ✅ on `main`, no re-run). A.4 live: both accounts captured + `verify`-clean (Hub `manifest-20260902T201610Z.json`, Forensic `manifest-20260902T201931Z.json`; each `VERIFY: MATCH`, exit 0); BOM's 11 `pending` rows filled + §4 floor row added. `restore/phase-2-floor-green` tagged by the repo owner on the merged A.4 status commit. |

### Why this is the recommendation

- **The register is empty; the gate is disarmed.** Story 2.0 was validated live on
  2026-09-02 (Story A.2). The advancement gate no longer blocks new work, so the
  question is simply "what next," per the Floor & Harvest Plan sequence (§7).
- **The floor is validated but not backed up.** Phase A's gate
  ([`FLOOR_AND_HARVEST_PLAN.md`](FLOOR_AND_HARVEST_PLAN.md) §2) requires deployed-state
  manifests captured + `verify`-clean for **both** accounts and BOM's 11 `pending`
  rows filled, then `restore/phase-2-floor-green`. None of that is done yet
  (`feature/restore-targets-phase2` is built but unmerged — that is **A.1**).
- **Order.** A.1 (merge the capture-tooling extension) unblocks A.4; A.3 is a quick
  confirmation of 2.1 that folds into the floor; A.4 is the substantive live work.
  The natural next session is **A.1 → A.3 → A.4**.

### What only the stakeholder can do

- **A.4** live `capture` / `verify` run in **both** CloudShells (Hub 641628980935 and
  Forensic 360999005254) — the executor has no live creds.
- **A.1** merge of `feature/restore-targets-phase2` — the repo owner's action.

### Note (not a status change)

This entry records a recommendation only. It does not change any story status; the
RUNBOOK remains the source of truth. A.3/A.4 close out only through the Story
Close-Out Procedure after their own recorded confirmations.



---

## 2026-09-02 - Recommendation 3: the harvest inventory (B.1), now that the floor is set and backed up

| Field | Value |
|-------|-------|
| **Recommended next** | Do the **harvest inventory (B.1)**: survey the repo and catalog every repeated/duplicated pattern with a proposed component boundary, its baked-in defaults vs. its parameters, the call-site count it replaces, and a harvest priority — into `docs/governance/HARVEST_INVENTORY.md`. |
| **One-line reason** | With the Phase-2 floor validated **and** backed up (`restore/phase-2-floor-green`), the plan's next step (Floor & Harvest Plan §4/§7) is to inventory *what to parameterize/archive* before building the archive — so the archive is built to an evidence-based spec, not a guess. |
| **Status** | `awaiting-user-decision` (a proposal for you to accept or refine) |

### Why this is the recommendation

- **The floor is done.** A.4 closed 2026-09-02: 2.0 ✅ + 2.1 ✅, deployed-state
  manifests captured + `verify`-clean for both accounts, BOM's rows filled,
  `restore/phase-2-floor-green` tagged. The known-good floor we convert from (and
  the fallback if conversion goes wrong) now exists.
- **Harvest before build.** The plan is explicit (Phase B): inventory the real
  duplication (raw inline `s3.Bucket`/`sqs.Queue`/`lambda.Function`, the duplicated
  `awsio` seam, the 5 bespoke contract generators, the 703-line hub-gate monolith)
  and decide each candidate's parameter surface **before** writing any archive code.
  B.1's output IS the archive's build spec.
- **It is a docs/survey step (no live AWS, no infra change).** B.1 is executor-heavy
  and safe: it reads the repo and produces a reviewed catalog; the archive build
  (Phase C) comes after.

### What only the stakeholder can do

- Nothing live for B.1 itself (it is a repo survey). Your role is to **review and
  accept** the inventory (Phase B gate): confirm each candidate's decided parameter
  surface or explicitly defer it.

### Note (not a status change)

This entry records a recommendation only; the RUNBOOK / Floor & Harvest Plan remain
the source of truth for status. B.1 closes out only through its own recorded
review-and-accept per the plan's Phase B gate.


---

## 2026-09-12 - Recommendation: G-2 next, + a sequence-adherence correction (course-correction)

| Field | Value |
|-------|-------|
| **Recommended next** | Prepare **G-2** (management-artifact integrity — finish/extend the checker + kill doc-drift) as the next governance story, and install a durable **sequence-adherence rule** so a story is never started out of the RUNBOOK schedule order without a stakeholder decision. |
| **One-line reason** | The stakeholder asked to get ready for G-2 and to correct a real process slip: Story 3.2 was started off a schedule recommendation the executor had itself edited, rather than off the stakeholder's decision. |
| **Status** | `accepted` — stakeholder directed both (get ready for G-2; correct the out-of-sequence issue). 3.2 is being worked in a separate session and is left untouched here. |

### What went wrong (the honest record)

- After closing C.3, the executor rewrote the RUNBOOK **"Default next action"** from
  *"C.3 (+ the cheap half of G-2) → back to the pipe track (3.2)"* to *"3.2 is next;
  G-2 low-urgency"*, and then treated 3.2 as next. That was a **re-prioritization of
  the roadmap** — the Planner/stakeholder's call under RD-024 — made unilaterally by
  editing the recommendation and working off the self-made edit.
- **Not a dependency violation:** G-2 (tier 0), B.1 (tier 6) and 3.2 (tier 9) are all
  independent "Ready" stories, so no dependency-precedence rule was broken and
  `check_docs` CHECK C did not (and should not) fire. The failure was purely one of
  **schedule discipline / role separation**, which nothing operationalized at
  session-open. **No 3.2 code was written by that executor** — only a proposal + a
  refreshed 3.2 handoff — so there was nothing to unwind on the code side.

### The correction (durable, this PR)

- **METHODOLOGY §2** — sharpened "the executor does not silently re-plan the roadmap"
  to name the two concrete failure modes: starting an out-of-order Ready story without
  the stakeholder's go, and editing the recommendation to justify it.
- **METHODOLOGY §5.A.0** — new FIRST step of the session-open ritual: confirm you are
  working the first OPEN item in the RUNBOOK schedule; a different Ready story is a
  stakeholder-decided reorder, logged here, before starting.
- **RUNBOOK** — a binding **"Sequencing rule"** note by the schedule buckets.
- **Templates** — `SESSION_PROMPT_TEMPLATE` (STEP 0 sequence check) +
  `SESSION_BRIEF_TEMPLATE` (REQUIRED schedule-position line).
- **G-2 scope** — added a *candidate* mechanical sequence-adherence check (scope a2) so
  the checker work is captured where it belongs (do not build it here).

### What only the stakeholder can do

- Decide the schedule order among independent Ready stories (this note records that
  **G-2 was chosen next**; 3.2 continues in its own session). Reordering is always the
  stakeholder's call — this log + the RUNBOOK schedule are how it is recorded.

### Note (not a status change)

This entry records a recommendation + a process correction only. It changes no story's
status and clears no validation debt; the RUNBOOK remains the source of truth for
status. G-2 remains ⬜ and closes only through its own recorded validation.



## 2026-09-12 - Gate-exempt debt session: G-1 authored, OD-003 confirmed closed, OD-001/002 surfaced

| Field | Value |
|-------|-------|
| **Recommendation** | Handle the three gate-exempt / parked debt items the stakeholder asked to clear in one session: confirm OD-003, surface OD-001/OD-002, and finish Story G-1 (RD-014 compliance back-map). |
| **Status** | `partly done` — G-1 **authoring complete** (PR #111, `feature/story-G-1`), G-1 stays 🟡 pending ratification; OD-003 confirmed **fully closed**; OD-001/OD-002 remain OPEN (live AWS ops, stakeholder-only). |

### What was done this session

- **OD-003 (CDK bump + deprecated-API migration)** — confirmed **fully closed**. PR #105
  shipped the code (CDK `aws-cdk-lib ^2.265.0`, `@types/node ^22`, `pointInTimeRecovery` →
  `pointInTimeRecoverySpecification`, `logRetention` → explicit `logs.LogGroup`); PR #109
  moved OD-003 to CLOSED in the RUNBOOK Operational Debt register after the live deploy was
  verified in BOTH accounts on Node v22 (9 new log groups at 30-day retention; Hub table
  PITR still ENABLED; no code/env/IAM/state-machine drift). Nothing left to do.
- **G-1 (compliance back-map, RD-014)** — **finished the matrix** in `docs/COMPLIANCE.md`
  (did NOT rebuild): a candidate (`Proposed`) mapping now exists for every registered
  decision (RD-001…RD-038), every non-functional constraint (§2), and the built pipeline's
  stories — 59 `Proposed` rows, **0 self-ratified**. `check_docs.py` PASS + `test_check_docs`
  OK. G-1 → 🟡 (*authored, awaiting ratification*); RUNBOOK/STORY_DETAIL aligned. PR #111.

### What only the stakeholder / an accountable reviewer can do

- **Ratify G-1's mappings.** Per RD-014, `Proposed → Ratified` is the accountable
  reviewer's decision, not the executor's — so nothing was self-ratified and ZTIE claims
  coverage for no row yet. A reviewer flips rows to `Ratified` (dated + attributed) per
  artifact group; G-1 closes ✅ incrementally as groups are ratified.
- **OD-001 / OD-002 (cost cleanup, Phase 2 of RD-032).** Both are **live AWS operations**
  that require real `[HUB]` / `[FORENSIC]` CloudShell (the build sandbox has NO AWS creds).
  OD-001 = Hub pipeline run-recency check + `delete-stack` of the confirmed-stale set;
  OD-002 = Forensic import-safety check + teardown of the dead lineage. Ready-to-run
  playbook (exact commands, KEEP/DELETE classification, safety rules — do NOT delete
  `ztie-asymmetric-cmk` or any `PDE-*`/`pde-*` stack) is at
  [`../session-briefs/cost-cleanup-phase2-PROMPT.md`](../session-briefs/cost-cleanup-phase2-PROMPT.md).
  These are optional additional savings; neither blocks feature work.

### Note (not a status change beyond G-1 🟡)

This entry records the debt-session outcome. OD-003's closure was already recorded (PRs
#105/#109); OD-001/OD-002 stay OPEN in the register until their live teardown is done with a
dated evidence note. The next working session's starter is repointed to **Story 3.4**.


---

## 2026-09-13 - Recommendation: after Story 3.5 ✅ (Phase 3 closed), do T.1 next (stakeholder reorder)

| Field | Value |
|-------|-------|
| **Recommended next** | **Story T.1** (multi-tenancy design SPIKE, doc-only) — ahead of the default tier order (4.1, the next pipe story). |
| **One-line reason** | T.1 is the first OPEN item in the RUNBOOK "Ready now" schedule (tier 5) and is explicitly noted as "should land **before Phase 4**" because it protects the Phase-4 dashboard/handoff design that 4.1 opens. |
| **Status** | `accepted` — stakeholder directed 2026-09-13 ("the runbook says t1 is next"). This is the sequencing rule + `check_docs` CHECK J advisory working as intended: the first OPEN Ready-now item is T.1, not 4.1. The 3.5→4.1 handoff artifacts (`story-4.1-brief.md` / `story-4.1-PROMPT.md`) stay authored + staged for when 4.1 comes up; the on-deck starter is repointed to T.1. No story status changes here (Story 3.5 remains ✅; T.1 stays ⬜ until its own work + validation). |

### Why this is the recommendation

- **Sequencing rule.** The story to START is the first OPEN item in the RUNBOOK "Ready now"
  schedule, in tier order. After 3.5 closed Phase 3, the first OPEN Ready-now items are
  **T.1 (tier 5)** then **B.1 (tier 6)**, both ahead of **4.1 (tier 13)**. `check_docs.py`
  CHECK J surfaced exactly this as a non-blocking advisory and pointed here to record the
  decision.
- **T.1 protects the Phase-4 design.** T.1 documents + ratifies the RD-028 multi-tenancy
  decisions (per-subscriber Forensic account = hard boundary; within-org shared-trust +
  org-shared dashboard; per-subscriber isolation granularity) and the migration path from
  today's single shared Forensic account. Landing it before Phase 4 means the 4.x
  dashboard/handoff design (which 4.1 opens) is built against a written tenant model rather
  than retrofitted. It is doc-only (no code), so it is cheap and unblocks T.2.
- **4.1 is not lost.** Its brief + prompt are authored and remain the staged next *pipe*
  build; it simply follows T.1 per this reorder.


---

## 2026-09-13 - Execution: Story T.1 drafted + submitted for stakeholder review (design spike)

| Field | Value |
|-------|-------|
| **Action** | Executed **Story T.1** (multi-tenancy design SPIKE, doc-only) per the accepted 2026-09-13 reorder above. Authored [`../architecture/MULTI_TENANCY.md`](../architecture/MULTI_TENANCY.md) capturing the settled RD-028 decisions (both isolation boundaries + rejected alternatives + subscriber-identifier model + Hub per-subscriber partitioning + Phase-4 per-subscriber org-shared dashboard + the migration path from today's single shared Forensic account as "tenant zero"), and scoping T.2/T.3 forward. Branch `docs/story-T.1-multitenancy`. |
| **RD-028** | Status moved `proposed` -> `ratified` in the plan table, **annotated as pending the accountable party's sign-off on the T.1 PR** (RD-014 — ratification is the stakeholder's call, recorded via PR approval; the executor drafts + proposes). `docs/COMPLIANCE.md` already carries the Ratified RD-028 / Story T.1 row (2026-09-12) — cited, not duplicated. |
| **Status** | `awaiting-user-decision` — T.1 is **🟡 In Progress** (doc drafted, `check_docs` PASS + `test_check_docs` OK), **not** ✅. It is validated by **stakeholder review** (design story, no live gate) and flips ✅ only on the accountable party's recorded review acceptance + RD-028 sign-off. The executor does not self-certify. On acceptance, the next Ready-now item is **B.1** (tier 6), then pipe story **4.1** (tier 13). |


---

## 2026-09-13 - Decision: Story T.1 ACCEPTED (stakeholder review) + RD-028 ratified

| Field | Value |
|-------|-------|
| **Action** | Recorded the stakeholder's review acceptance of **Story T.1** (multi-tenancy design spike, doc-only). The accountable party accepted [`../architecture/MULTI_TENANCY.md`](../architecture/MULTI_TENANCY.md) and **ratified RD-028** (PR #123 merged to `main`, merge `6052a2d`). |
| **Status** | `accepted` — **T.1 → ✅** (validated by stakeholder review 2026-09-13; design story, no live gate). RD-028 Status is `ratified`, attributed to the accountable party 2026-09-13; `docs/COMPLIANCE.md`'s RD-028/T.1 row was already Ratified (cited, not duplicated). T.1 unblocks **T.2** (deferred to commercialization). |
| **Next** | Per the sequencing rule the next first-OPEN Ready-now item is **B.1** (tier 6, Harvest Inventory, docs-only; dep A.4 ✅), ahead of pipe story 4.1 (tier 13). On-deck pointer repointed to B.1. |


---

## 2026-09-13 - Decision: reorder Story 4.1 AHEAD of B.1 (stakeholder reorder)

| Field | Value |
|-------|-------|
| **Recommended/next** | Start **Story 4.1** (status-retrieval orchestrator, opens Phase 4, tier 13) NEXT, ahead of the first-OPEN Ready-now item **B.1** (Harvest Inventory, docs-only, tier 6). |
| **One-line reason** | Stakeholder-directed reorder: the pipeline reaches a human-facing milestone faster by opening Phase 4 now; the B.1→C.5 Floor-&-Harvest archive chain is a platform-maturity investment already flagged "keep but defer" and carries no pipeline dependency that 4.x needs. |
| **Status** | `accepted` — stakeholder directed 2026-09-13 ("option b" to the executor's sequencing question: reorder 4.1 first rather than follow the default schedule to B.1). This is the sequencing rule working as intended: the story to START is normally the first OPEN Ready-now item (B.1), and working a *different* Ready story is a stakeholder-decided reorder recorded HERE (never an executor self-selection). `check_docs` CHECK J is expected to flag the on-deck-starter vs first-OPEN-schedule-item mismatch as a NON-BLOCKING advisory once the on-deck pointer is set to 4.1 — pointing HERE for the recorded decision. |

### Why this is a legitimate reorder (not a dependency skip)

- **Not a dependency violation.** 4.1's only dependency is **3.5 ✅** (Phase 3 closed 2026-09-13; the Validation Debt Register is EMPTY and the advancement gate is OPEN). Starting 4.1 skips no unmet dependency; it only jumps *ahead of a lower-tier Ready sibling* (B.1), which is exactly what a recorded reorder is for.
- **B.1 is not lost.** B.1 (and the C.1→C.5 archive chain it feeds) remains Ready and scheduled; it simply follows 4.1 per this reorder. Its brief + prompt stay authored + staged (`docs/session-briefs/story-B.1-*`).
- **T.1 already protected the Phase-4 design.** The multi-tenancy design spike (T.1, RD-028) closed ✅ 2026-09-13 before Phase 4, so the 4.x dashboard/handoff design is built against a written tenant model.

### Sequencing bookkeeping

- On-deck pointer repointed from B.1 to **4.1**; the `check_docs` CHECK J advisory (if it fires) is reconciled by THIS logged reorder.
- No story status changes here beyond starting 4.1 (which goes 🟡 in its own build commit + is added to the Validation Debt Register until its recorded live pass).


---

## 2026-09-13 - Decision: Story 4.1 VALIDATED LIVE + closed ✅ (RD-041); reorder continues (4.2 ahead of B.1)

| Field | Value |
|-------|-------|
| **Action** | Recorded the LIVE validation of **Story 4.1** (status-retrieval orchestrator, RD-041) and closed it ✅. Build PR #125 merged to `main` (merge `7f1f319`); close-out PR on branch `docs/story-4.1-validate` flips 4.1 🟡→✅ + records the result. |
| **Result (verbatim, recorded)** | Hub 641628980935, intake `384d63ef-7577-4787-ba0e-cc5d92305ff9` (small S3 CloudFormation template routed to both lanes) ran the pipeline end-to-end (all five Phase-3 fields present). The redeployed `hub_status` orchestrator verified PURE + READ-only on the LIVE resource (env `STATUS_CONTRACT_VERSION: 1.0` + `TRACKING_TABLE` + `LOG_LEVEL`, NO `NOVA_MODEL_ID`; role only READ `dynamodb:*`, NO `UpdateItem`/`PutItem`/`DeleteItem`, NO `bedrock:InvokeModel`). Invoking it returned the assembled status read-model: `overall_stage: recommended`, all stages present, scores echoed 55/30/70 (never re-blended), `findings_summary` status `assessed` (1 finding / 1 candidate-FP / 1 gap / 2 remediations, highest gap `high`, no contradiction), `recommendation` = the 3.5 `recommended_verdict: INCONCLUSIVE` ADVISORY with `decision: pending` + `advisory: true`. READ-only proven (identical DynamoDB key set before/after the invoke; nothing written). No effective-verdict key in the view. Error paths clean: non-existent UUID → 404, malformed id → 400. |
| **Status** | `accepted` — **4.1 → ✅** (validated live 2026-09-13). Register EMPTY; advancement gate OPEN. Phase 4 is under way. |
| **Next (reorder continues)** | Per the 2026-09-13 stakeholder reorder (Phase-4 pipe work ahead of the F&H track), the next build is **Story 4.2** (dashboard JSON payload, tier 14), then the other 4.x pipe stories, with **B.1** (tier 6, F&H) sequenced after. On-deck pointer repointed to 4.2; `check_docs` CHECK J will flag the on-deck-vs-first-OPEN (B.1) mismatch as a NON-BLOCKING advisory pointing at the reorder recorded above — reconcile it at the 4.2 STEP 0, do not ignore it. 4.2 handoff (`story-4.2-brief.md` / `story-4.2-PROMPT.md`) authored + staged. |



---

## 2026-09-13 - Decision: Story 4.2 VALIDATED LIVE + closed ✅ (RD-042); reorder continues (4.3 next, B.1 after)

| Field | Value |
|-------|-------|
| **Action** | Recorded the LIVE validation of **Story 4.2** (dashboard JSON payload, the Phase-4 data layer, RD-042) and closed it ✅. Build PR #127 merged to `main` (merge `f1b421c`); close-out PR on branch `docs/story-4.2-validate` flips 4.2 🟡→✅ + records the result. |
| **Result (verbatim, recorded)** | Hub 641628980935, intake `891cb78f-fd35-4045-81d6-030d75d9c83e` (a small S3 CloudFormation template routed to both lanes) ran the pipeline end-to-end (all five Phase-3 fields present). The redeployed `hub_dashboard` orchestrator verified PURE + READ-only on the LIVE resource (env `DASHBOARD_CONTRACT_VERSION: 1.0` + `STATUS_CONTRACT_VERSION: 1.0` + `TRACKING_TABLE` + `LOG_LEVEL`, NO `NOVA_MODEL_ID`; role only READ `dynamodb:*`, NO `UpdateItem`/`PutItem`/`DeleteItem`, NO `bedrock:InvokeModel`). `view=intake` returned `dashboard.contract.v1`: `intake.status` = the 4.1 read-model reused verbatim (`overall_stage: recommended`, scores 50/30/70, `findings_summary` assessed, the 3.5 `recommended_verdict: INCONCLUSIVE` ADVISORY with `decision: pending` + `advisory: true`); `intake.threat.tier: high` (display band from combined 70, never a verdict); `intake.action` = the human APPROVE/REJECT control input (advisory recommendation + pending decision). `view=fleet` (limit 10) returned 10 newest-first GSI-paged rows (`truncated: true`, no scan) with consistent `metrics` (`by_stage` summed to 10; `by_recommended_verdict` 3 INCONCLUSIVE + 7 none; `by_threat_tier` 5 high + 5 unknown; `ami_build_health`/`sensor_status`/`cost` = `not_wired`). READ-only proven (tracking item carried only Phase-1→3 attributes; no `dashboard_*`/`threat_*` field written); no effective-verdict key in either payload. |
| **Status** | `accepted` — **4.2 → ✅** (validated live 2026-09-13). Register EMPTY; advancement gate OPEN. The Phase-4 data layer is done. |
| **Next (reorder continues)** | Per the 2026-09-13 stakeholder reorder (Phase-4 pipe work ahead of the F&H track), the next build is **Story 4.3** (real-time dashboard render, tier 15), then the other 4.x pipe stories, with **B.1** (tier 6, F&H) sequenced after. On-deck pointer repointed to 4.3; `check_docs` CHECK J will flag the on-deck-vs-first-OPEN (B.1) mismatch as a NON-BLOCKING advisory pointing at the reorder recorded here — reconcile it at the 4.3 STEP 0, do not ignore it. 4.3 handoff (`story-4.3-brief.md` / `story-4.3-PROMPT.md`) authored + staged. |



---

## 2026-09-13 - Story 4.3 BUILT + offline-proven → 🟡 (RD-043); reorder continues (4.3 next, B.1 after)

| Field | Value |
|-------|-------|
| **Action** | Built **Story 4.3** (real-time dashboard render, the Phase-4 presentation layer over 4.2's `dashboard.contract.v1`) on branch `feature/story-4.3` and set it **🟡 In Progress** (added to the Validation Debt Register). Registered **RD-043** (proposed) for the dashboard hosting/serving architecture. Build commit `5fe64ad`. |
| **As built** | NEW Hub-side CDK stack `ZtieDashboardStack` (`infra/lib/ztie-dashboard-stack.ts`, wired as Stack 7 in `infra/bin/ztie-infra.ts`, instantiated only with `-c dashboardFunctionArn`): a private S3 + CloudFront (OAC) static dark-theme SPA (`dashboard/`), plus an **IAM-auth API Gateway** front (`GET /dashboard` = fleet, `GET /status/{intake_id}` = per-intake) that PROXIES to the **UNCHANGED Story 4.2 `hub_dashboard` Lambda** (referenced by ARN — the GET front 4.2 deferred; no 4.2 handler change). The SPA (`app.js`) is RENDER-ONLY: GET-only reads of the two 4.2 views, escapes all derived values (`textContent`, never `innerHTML` — no stored XSS, RD-013), advisory banner + per-intake note + `decision: pending`, APPROVE/REJECT buttons a **DISABLED surface** (the ACTION is 4.4/4.7, RD-040), graduated `threat_tier` coloring (dark theme), `not_wired` health → "not available yet", `subscriber_id` on every read (RD-028, default `ztie-tenant-zero`). Offline proof: `dashboard/test_dashboard_render.py` OK(12), the 4.2 `hub_dashboard` suite still OK(54), ruff clean, `tsc` adds NO new error type, prettier clean, `gen_contracts.py` no drift (4.3 authors no new contract — it renders 4.2's). |
| **Docs (RD-015)** | RD-043 row in PROJECT_PLAN (proposed); RUNBOOK master table 4.3 ⬜→🟡 + Validation Debt Register (1 open) + Ready-now/Blocked/Default-next-action updated (4.2 struck closed, 4.3 the in-progress row); STORY_DETAIL 4.3 as-built; COMPLIANCE RD-043 row (Proposed); on-deck README repointed to the 4.3 LIVE validation; `story-4.3-LIVE-RUNBOOK.md` authored. `check_docs` PASS (expected CHECK J advisory) + `test_check_docs` OK(19) after the status commit. |
| **Status** | `awaiting-live-validation` — **4.3 is 🟡**, on the Validation Debt Register; the advancement gate is **ARMED** (no NEW feature story until 4.3 clears by its own recorded live pass). It is validated by the stakeholder deploying `ZtieDashboardStack` + exercising the two GET endpoints (SigV4) + eyeballing the render — see `docs/session-briefs/story-4.3-LIVE-RUNBOOK.md`. The executor does not self-certify. |
| **Next (reorder continues)** | Per the 2026-09-13 stakeholder reorder (Phase-4 pipe work ahead of the F&H track), the immediate next action is the **recorded LIVE validation of 4.3**. On 4.3's pass it flips ✅, the register empties, and the next Phase-4 pipe work (**4.5 / 4.6 / 4.7**, then **4.4** which closes Phase 4 on 4.3 + 4.7) becomes schedulable, with **B.1** (tier 6, F&H) sequenced after. On-deck pointer is on the 4.3 live validation; `check_docs` CHECK J flags the on-deck-vs-first-OPEN (B.1) mismatch as a NON-BLOCKING advisory pointing at THIS reorder — reconcile it, do not ignore it. |



---

## 2026-09-13 - Decision: Story 4.3 VALIDATED LIVE + closed ✅ (RD-043); next = the remaining Phase-4 pipe work

| Field | Value |
|-------|-------|
| **Action** | Recorded the LIVE validation of **Story 4.3** (real-time dashboard render, RD-043) and closed it ✅. Build PR #132 (branch `feature/story-4.3`); close-out on branch `docs/story-4.3-validate` flips 4.3 🟡→✅ + records the result. |
| **Result (verbatim, recorded)** | Hub 641628980935. `ZtieDashboardStack` deployed with `-c dashboardFunctionArn=<4.2 DashboardOrchestrator ARN>` (outputs `DashboardUrl = https://d1zuxj1q2jge2r.cloudfront.net/`, `DashboardApiUrl = https://5lcpg13011.execute-api.us-east-1.amazonaws.com/prod/`, `DashboardSubscriberId = ztie-tenant-zero`); the stack added NO Lambda of its own (only the CDK `BucketDeployment` helper — it references the 4.2 Lambda by ARN). `GET /dashboard?limit=5` returned `view: fleet`, 5 newest-first rows (`returned_count: 5`, `truncated: true`), `metrics.by_stage` summing to 5 (1 scored / 1 assessed / 3 recommended), `by_recommended_verdict` 3 INCONCLUSIVE + 2 none, `by_threat_tier` 5 high, AMI/sensor/cost `not_wired`. `GET /status/891cb78f-…` returned `view: intake`: `intake.status` = the 4.1 read-model reused verbatim (`overall_stage: recommended`, all stages present, scores 50/30/70 echoed as objects, `findings_summary` assessed 1/1/1/2 highest gap `high`), `intake.threat.tier: high` (combined 70), `intake.action` with `recommended_verdict: INCONCLUSIVE` + `decision: pending` + `advisory: true`. No-effective-verdict-key scan OK on both payloads; non-existent intake → clean `{"error":{"code":404}}`; the CloudFront URL rendered the dark-theme SPA (advisory banner, graduated `threat_tier` coloring, disabled Approve/Reject surface). |
| **Live fix (fix-then-validate-once)** | The initial deploy used a `proxy: true` API Gateway integration and returned HTTP 502 "Malformed Lambda proxy response" — the 4.2 `hub_dashboard` Lambda is built for DIRECT invoke and returns a BARE payload, not a `{statusCode, body}` proxy envelope. API Gateway execution logs pinpointed it. Fixed on the branch (commit `8058301`) by switching both GET methods to a NON-PROXY `LambdaIntegration` with a VTL request template + a pass-through integration response mapping the 4.2 error-envelope `code` (400/404/422) to the HTTP status — the 4.2 Lambda stayed UNCHANGED. Redeployed (`get-integration` confirmed `type: AWS`) + re-validated clean. The fix commit is on the validated branch, so it lands on `main` with the close-out (guarding the auto-merge-before-fix trap). |
| **Status** | `accepted` — **4.3 → ✅** (validated live 2026-09-13). Register EMPTY; advancement gate OPEN. Closing 4.3 does NOT close Phase 4 (4.4/4.5/4.6/4.7 remain), so the P4 roll-up glyph stays 🟡. |
| **Next** | Per the 2026-09-13 stakeholder reorder (Phase-4 pipe work ahead of the F&H track), the next feature work is the remaining Phase-4 pipe stories — **4.5** (per-execution report) / **4.6** (ACCEPT→PDE) / **4.7** (REJECT→destroy), then **4.4** (the human accept/reject action, which closes Phase 4 on 4.3 + 4.7). **Confirm which is next with the stakeholder at the next STEP 0** (4.4 cannot be first — it depends on 4.7). **B.1** (tier 6, F&H) stays Ready, sequenced after the Phase-4 pipe work; `check_docs` CHECK J will flag the on-deck-vs-first-OPEN (B.1) mismatch as a NON-BLOCKING advisory pointing at this reorder. On-deck README repointed to "the next Phase-4 pipe story (confirm with stakeholder)"; the next story's brief + prompt are authored at that session's STEP 0 before the README links them (CHECK I). |



---

## 2026-09-13 - Reconciliation (RETROACTIVE): record the intra-Phase-4 reorder 4.1→4.2→4.3 ahead of the tier-14 report/handoff stories (4.5/4.6/4.7)

> **This entry is logged AFTER the fact.** It names a real sequencing gap the stakeholder
> caught and legitimizes the already-completed work with a recorded rationale (option 3:
> retro-log + correct course + tighten the guard). It does not change any story status.

| Field | Value |
|-------|-------|
| **The gap (stated plainly)** | The 2026-09-13 reorder recorded above ("reorder Story 4.1 AHEAD of B.1") only decided **Phase-4 pipe work vs. the Floor-&-Harvest track (B.1)**. It said NOTHING about the ordering **among the 4.x stories**. Yet after 4.2 closed, the executor proceeded **4.2 → 4.3** and carried "the next build is 4.3" in each WORK_LOG "Next" field as if settled. By strict tier order that was an INVERSION: **4.5 / 4.6 / 4.7 are build tier 14** (they depend only on 4.1) while **4.3 is build tier 15** (it depends on 4.2). So once 4.2 was ✅, the first-OPEN *tier-ordered* Ready item was **4.5** (tier 14), not 4.3 (tier 15). We worked the higher-tier 4.3 ahead of its lower-tier Ready siblings **without a recorded intra-Phase-4 reorder** — the executor asserted "next" on its own authority, which the sequencing rule says it must not do. |
| **What was NOT wrong** | **No dependency-precedence violation occurred** (the HARD rule held everywhere): 4.2 depends on 4.1 and 4.3 depends on 4.2, so 4.1→4.2→4.3 is a forced chain — 4.3 could not have been built before 4.2. The miss is purely the missing *recorded priority decision* for putting that dashboard chain ahead of the independent tier-14 siblings (which SEQUENCING_METHOD §4–§5 explicitly allows — "priority orders independents" — but only as a recorded decision, not an executor self-selection). |
| **Why CHECK J did not catch it** | `scripts/check_docs.py` CHECK J (advisory) compares the on-deck starter against the **first non-✅ row of the Ready-now (bucket A) table, read TOP-DOWN by ROW ORDER — not by tier**, and it only ever names that SINGLE first-open row (here **B.1**, the lowest-tier F&H item). So (a) it flagged only the on-deck-vs-B.1 mismatch (which the Phase-4-over-B.1 reorder already covered), and (b) because bucket-A row order is hand-arranged, an intra-phase tier inversion among *sibling Ready pipe stories* is invisible to CHECK J when the rows are arranged to match the executor's intent. The mechanical guard has a real blind spot for intra-phase tier inversions; it is not a substitute for a recorded priority decision. |
| **Decision (retroactive, stakeholder-accepted 2026-09-13)** | RATIFY the intra-Phase-4 ordering that was actually executed: the **Phase-4 dashboard chain 4.1 → 4.2 → 4.3** was worked ahead of the tier-14 report/handoff stories **4.5 / 4.6 / 4.7**. Rationale (critical-path + foundation-hardening, SEQUENCING_METHOD §4): the dashboard render is the human-facing surface through which the zero-trust human gate is exercised and it is the natural continuation of the 4.1→4.2 read-model/payload chain, so standing it up first gives an operator-visible milestone and a concrete render for 4.5/4.6/4.7 + 4.4 to build against. This is a legitimate priority reorder of INDEPENDENT Ready siblings — it broke no dependency precedence — and it is now recorded as the rule requires (belatedly). |
| **Course correction (from here, by the book)** | Phase-4 is NOT closed (4.4/4.5/4.6/4.7 remain). The next pick reverts to STRICT first-OPEN tier order: the lowest-tier OPEN Ready pipe stories are **4.5 / 4.6 / 4.7 (tier 14)**; **4.4** (tier 16) closes Phase 4 and is BLOCKED on 4.7, so it cannot be first. Any further deviation (e.g. doing 4.8 tier-16 enhancement, or a specific one of 4.5/4.6/4.7 out of turn) must be a stakeholder-decided reorder recorded HERE **before** starting — not an executor "next" assertion. B.1 (tier 6, F&H) remains sequenced after the Phase-4 pipe work per the standing reorder. |
| **Guard tightened** | `docs/governance/SEQUENCING_METHOD.md` gains an explicit note that CHECK J compares by bucket-A ROW ORDER and names only the single first-open row, so **intra-phase / same-track tier inversions among Ready siblings are NOT mechanically caught** and require an explicit recorded priority decision (this entry) before working a higher-tier Ready story ahead of a lower-tier Ready sibling. The on-deck README carries the same caution. |
| **Status** | `accepted` — retroactive reconciliation recorded. No story status changed; the Validation Debt Register stays empty. |



---

## 2026-09-13 - Story 4.5 BUILT + offline-proven → 🟡 (RD-045); by-the-book tier-ordered pick

| Field | Value |
|-------|-------|
| **Sequencing (by the book)** | Started **Story 4.5** because it is the **first-OPEN pipe story in strict tier order** in the RUNBOOK "Ready now" schedule (tier 14, dep 4.1 ✅) — confirmed live at STEP 0 (`first OPEN pipe row = 4.5`). This is the sequencing rule followed WITHOUT a stakeholder pick: the runbook decides the next story; the executor read it and worked it (correcting the earlier habit of asking "what next?" when the schedule already answers). The only stakeholder decision brought forward was a genuine design fork — the report OUTPUT FORMAT (Option A). |
| **Action** | Built **Story 4.5** (per-execution tiered report — Executive / Security / Developer) on branch `feature/story-4.5` and set it **🟡 In Progress** (added to the Validation Debt Register). Registered **RD-045** (the 4.5 contract-first decision) and **RD-046** (the 4.9 report-enrichment follow-on). |
| **As built** | NEW PURE, READ-only Hub Lambda `lambdas/hub_report/` (in `ZtieHubTrackingStack`, construct `ReportOrchestrator`, NO stream source, `grantReadData` only, NO Bedrock) invoked on demand by `intake_id`; assembles `report.contract.v1` (own pin `REPORT_CONTRACT_VERSION`) in three tiers + a self-contained inline-CSS HTML render (print-to-PDF). Executive reuses `status_model.build_status` (vendored byte-identical + no-drift test); Security from 3.2 correlation + 3.4 assessment findings/gaps; Developer from 3.4 prioritized_remediations/candidate_false_positives. `handler.py` on-demand (top-level or API-GW shape; format json/html/both; 400/404/422 envelopes). **Option A (stakeholder-confirmed): HTML render, not a native PDF lib** — the build sandbox has no package registry, so a native PDF dep isn't installable/offline-testable; HTML keeps it PURE stdlib + offline-provable. **Honest RD-013 boundary:** MITRE/Sigma/file-line = `not_carried_on_hub` placeholders (raw stays in Forensic); widening the crossing is the separate story **4.9 (RD-046)**. **Advisory (RD-040):** `recommended_verdict` + `decision: pending` + `advisory: true`; no bare effective-verdict key; HTML escapes every derived value. |
| **Docs (RD-015)** | RD-045 + RD-046 rows in PROJECT_PLAN (proposed); RUNBOOK master table 4.5 ⬜→🟡 + new 4.9 row (tier 15, dep 4.5, ⬜) + Validation Debt Register (1 open) + Ready-now/Blocked/Default-next-action updated; STORY_DETAIL 4.5 as-built + new `story-4-9` anchor/spec; COMPLIANCE RD-045 + RD-046 rows (Proposed); on-deck README repointed to the 4.5 LIVE validation; `story-4.5-LIVE-RUNBOOK.md` authored. `check_docs` PASS + `test_check_docs` OK(19) after the status commit. |
| **Offline proof** | `lambdas/hub_report/` tests OK(33, 3 jsonschema-live skips); ruff clean; `tsc` adds NO new error type (main 123 → 125: +1 `__dirname` TS2304 for the new asset dir, +1 TS2353 — both existing missing-`aws-cdk-lib`/`@types/node` family); prettier clean; `gen_contracts.py` no drift; HTML render well-formed + XSS-escaped. |
| **Status** | `awaiting-live-validation` — **4.5 is 🟡**, on the Validation Debt Register; the advancement gate is **ARMED** (no NEW feature story until 4.5 clears by its own recorded live pass). Validated by the stakeholder redeploying `ZtieHubTrackingStack` + invoking `hub_report` for a real intake — see `docs/session-briefs/story-4.5-LIVE-RUNBOOK.md`. The executor does not self-certify. |
| **Next** | On 4.5's recorded live pass it flips ✅, the register empties, and the next Phase-4 pipe work becomes schedulable — **4.6** (ACCEPT→PDE) / **4.7** (REJECT→destroy) at tier 14, then **4.4** (tier 16) which closes Phase 4 on 4.3 + 4.7. **4.9** (report-enrichment, tier 15, RD-046) is Blocked on 4.5; **4.8** (dashboard browser auth, tier 16) is a lower-priority enhancement; **B.1** (F&H, tier 6) sequenced after the Phase-4 pipe work per the reorder. By the SEQUENCING_METHOD §4a guard: the next pick is strict first-OPEN tier order (4.6/4.7 before the tier-15/16 items) unless a reorder is recorded here first. |



---

## 2026-09-13 - Decision: Story 4.5 VALIDATED LIVE + closed ✅ (RD-045); next = 4.6/4.7 (tier order)

| Field | Value |
|-------|-------|
| **Action** | Recorded the LIVE validation of **Story 4.5** (per-execution tiered report — Executive / Security / Developer, RD-045) and closed it ✅. Build PR #136 (branch `feature/story-4.5`); live-fix PR #137 (merge `5d7fa96`); close-out on branch `docs/story-4.5-validate` flips 4.5 🟡→✅ + records the result. |
| **Result (verbatim, recorded)** | Hub 641628980935. `ZtieHubTrackingStack` redeployed (fresh `ReportOrchestrator/Code`); the live `hub_report` verified PURE + READ-only (env `REPORT_CONTRACT_VERSION: 1.0` + `STATUS_CONTRACT_VERSION: 1.0` + `TRACKING_TABLE` + `LOG_LEVEL`, NO `NOVA_MODEL_ID`; role only READ `dynamodb:*`, NO `UpdateItem`/`PutItem`/`DeleteItem`, NO `bedrock:InvokeModel`). Invoked for intake `891cb78f-fd35-4045-81d6-030d75d9c83e` (`format: both`): returned `report.contract.v1` + HTML (8732 chars). Executive `overall_stage: recommended`, `combined_score: 70`, advisory `recommended_verdict: INCONCLUSIVE` + `decision: pending` + `advisory: true` + summary. Security `data_status: available`, 1 finding + 1 gap, `mitre_attack`/`sigma_rules` = `not_carried_on_hub`. Developer `data_status: available`, 2 prioritized remediations (`ranks: [1, 2]`) + 1 candidate FP, `source_location` = `not_carried_on_hub`. No effective-verdict key; READ-only proven (tracking item carried only Phase-1→3 attributes — no `report_*` field written); clean `{"error":{"code":404}}` on a non-existent intake. |
| **Live fix (fix-then-validate-once)** | The first invoke returned `remediations: 0` — `hub_report` reads the item via `boto3.resource`, which deserializes a DynamoDB Number to a `Decimal`, and `_remediation_view`'s strict `isinstance(int)` guard on `rank` rejected every row. Fixed on the branch (PR #137, merge `5d7fa96`) by adding a `_rank()` coercion (accepts `Decimal`/`int`, bounds 1..100) + a regression test; redeployed and re-validated — `remediations: 2`, `ranks: [1, 2]`. Only catchable live (the offline tests used plain-`int` ranks). The fix is on `main` (PR #137 merged) and the close-out branch is cut from `main` after it, so the ✅ points at the validated code. |
| **Status** | `accepted` — **4.5 → ✅** (validated live 2026-09-13). Register EMPTY; advancement gate OPEN. Closing 4.5 does NOT close Phase 4 (4.4/4.6/4.7 remain), so the P4 roll-up glyph stays 🟡. |
| **Next** | Per the 2026-09-13 stakeholder reorder + strict first-OPEN tier order (SEQUENCING_METHOD §4a), the next feature work is the tier-14 pipe stories **4.6** (ACCEPT→PDE) / **4.7** (REJECT→destroy), then **4.4** (tier 16) which closes Phase 4 on 4.3 + 4.7. **4.9** (report-enrichment, tier 15, RD-046) is now Ready on 4.5 ✅ but sequenced after the tier-14 work; **4.8** (dashboard browser auth, tier 16) is a lower-priority enhancement; **B.1** (F&H, tier 6) sequenced after the Phase-4 pipe work. Working a higher-tier Ready story ahead of a lower-tier Ready sibling needs a recorded reorder HERE first. On-deck README repointed to the next Phase-4 pipe story (4.6/4.7). |


---

## 2026-09-13 - Story 4.6 BUILT + offline-proven → 🟡 (RD-047); by-the-book first-OPEN tier-ordered pick

| Field | Value |
|-------|-------|
| **Recommended next** | Build **Story 4.6** (ACCEPT → push hash-verified artifact Forensic → Pipeline-Sandbox, RD-047) — the first-OPEN pipe story in strict tier order (tier 14, dep 4.1 ✅; 4.6 is the first-listed of the tier-14 4.6/4.7 pair). |
| **One-line reason** | With 4.5 ✅ and the register empty, 4.6 was the by-the-book first-OPEN Ready-now pipe story (SEQUENCING_METHOD §4a) — no stakeholder "what next?" needed; the runbook decided it. |
| **Status** | `accepted` — **4.6 → 🟡** (BUILT + offline-proven 2026-09-13 on `feature/story-4.6`). Added to the Validation Debt Register in the same status commit; advancement gate ARMED. Awaits the recorded live pass (`docs/session-briefs/story-4.6-LIVE-RUNBOOK.md`). |
| **As built** | NEW Forensic push Lambda `lambdas/pde_handoff/` (PURE fail-closed gate + envelope in `handoff.py`, thin boto3 seam `awsio.py`, on-demand `handler.py`) + NEW `ZtieSandboxLandingStack` (Pipeline-Sandbox 586917955591 — the FIRST ZTIE stack in this third account: an SSE-S3 landing bucket + a cross-account bucket policy granting EXACTLY the Forensic pusher role `s3:PutObject` on one prefix) + NEW `ZtiePdeHandoffStack` (Forensic: the pusher Lambda + a least-privilege role — cross-account `dynamodb:GetItem` on the Hub table, `s3:GetObject` on the artifact bucket, `s3:PutObject` on the one Sandbox prefix, `sqs:SendMessage` on the Hub ingest queue; NO Bedrock) + the 10th RD-013 crossing kind `handoff` (`handoff.contract.v1`, own pin `HANDOFF_CONTRACT_VERSION`, unique discriminator, applied integrity-bound onto its own fields, never touches `status`/verdict). Both stacks wired in `infra/bin/ztie-infra.ts` (Stacks 8 + 9). RD-047 registered. **Design forks (all stakeholder-approved rec options):** Sandbox-owned landing bucket; pusher in Forensic + grant on the Sandbox bucket policy; ACCEPT = a recorded human `human_decision == "accepted"` on the Hub item (enum `pending`/`accepted`/`rejected`, default `pending`; auto-trigger deferred to 4.4), fail-closed; sha256 verified before push; SSE-S3 (no cross-account CMK). |
| **Offline proof** | `pde_handoff` tests 41 OK (5 jsonschema-live skips); Hub gate `test_handoff_dispatch` 10 OK; `ruff` clean; `tsc` adds NO new error type (only the missing-`aws-cdk-lib`/`@types/node` family for the two new stacks + the bin); `prettier` clean; `gen_contracts.py` no drift (the new `handoff.contract.v1.json` is byte-identical in `schemas/` + `hub_ingest/` + `pde_handoff/`). |
| **Next** | The **4.6 LIVE validation** is the single next action (register ARMED). On the recorded pass 4.6 flips ✅, the register empties, and **4.7** (REJECT→destroy, the tied tier-14 sibling) becomes the first-OPEN pipe story, then **4.4** (tier 16) closes Phase 4 on 4.3 + 4.7. 4.7 handoff authored at `docs/session-briefs/story-4.7-brief.md` + `story-4.7-PROMPT.md`. `_NEW_WORK_STORY` fixture stays `4.4`. |


---

## 2026-09-13 - Story 4.6 live validation surfaced the Hub-read defect → RD-048 + RD-049 + H.1 (redesign, not rewind)

| Field | Value |
|-------|-------|
| **What happened** | During the Story 4.6 (ACCEPT→push, RD-047) LIVE validation, the Forensic pusher's cross-account `dynamodb:GetItem` into the Hub tracking table failed (`AccessDeniedException`) — and, more importantly, the stakeholder ruled that **the Hub must be STRICTLY the control plane: no spoke may read into it**. 4.6 was correctly caught at 🟡 (never flipped ✅), so this is a fix-forward redesign, not a rewind. |
| **Decisions (stakeholder-ratified)** | **RD-048** (PR #142, ratified) — the Hub is strictly the control plane; no spoke reads Hub data; the Hub HANDS OUT authenticated decisions spokes VERIFY; all spoke→Hub flow stays the one-directional RD-013 write-out. **RD-049** (PR #144, ratified) — the mechanism: KMS ASYMMETRIC signature the Hub produces (Hub-only `kms:Sign`), the spoke VERIFIES OFFLINE against the embedded public key (no call into the Hub / Hub-KMS); a canonical `decision.token.v1` binds `intake_id` + `decision` + artifact `sha256` + `issued_at` + `key_id`; verify-then-act is fail-closed. RD-047's cross-account-read clause is superseded in part (noted inline); every other RD-047 property (fail-closed gate, hash-verify, one-directional least-privilege push, verdict-free outcome, never-re-execute) stands. |
| **H.1 (this close-out)** | The authenticated-decision DESIGN SPIKE (doc-only, `security` track, tier 5): `docs/architecture/AUTHENTICATED_DECISIONS.md` (PR #144). VALIDATED by stakeholder review 2026-09-13 → **H.1 ✅**, RD-049 ratified. H.1 is a letter-track id (not `STORY_ID_RE`), so its status never armed the advancement gate. |
| **Restore-tag gap** | Closed the code half (PR #143): prep to push `restore/phase-3-green` @ `e2b325d` + `restore/story-4.5-green` @ `537d61c`; **OD-004** opened for the deferred paired state-manifest capture. The two tags are an OWNER git-push action (prompt at `docs/session-briefs/restore-tags-phase3-and-4.5-PROMPT.md`), not yet on origin. |
| **Status** | **Story 4.6 stays 🟡** (its deployed stacks are the old read-in design — inert/safe: the pusher can't read the Hub so it can't push; they will be redeployed on the rework, not torn down). Register: 4.6 open (armed); OD-004 open (operational, non-arming). |
| **Next** | The authenticated-decision **BUILD story** (implements RD-048/RD-049): author the `decision.token.v1` schema (allow-list, own pin) + generator + conformance test; a PURE verify library (canonicalize → verify sig → the five fail-closed checks) with offline test vectors; a Hub KMS asymmetric signing-key stack (Hub-only `kms:Sign` + `PublicKey` output) + a documented manual `aws kms sign` recipe for validation; embed the public key in the spoke; live-validate the crossing (Hub signs → spoke verifies offline → acts; every fail-closed branch refuses; no spoke→Hub read). THEN rework 4.6 onto it (verify a Hub-signed `accepted` token offline → push; remove the cross-account Hub read grant) → 4.6's single live pass → ✅. 4.7 + 4.4 inherit the primitive. |


---

## 2026-09-13 - Story H.2 BUILT + offline-proven → 🟡 (implements RD-048/RD-049); the auth-decision primitive

| Field | Value |
|-------|-------|
| **Recommended next** | Build **Story H.2** — the authenticated Hub→spoke decision MECHANISM (implements the ratified RD-048/RD-049; the shared primitive the 4.6 rework + 4.7 + 4.4 consume). |
| **One-line reason** | H.1 ✅ settled the design; H.2 is the by-the-book next step — build the primitive ONCE, then rework 4.6 onto it (rather than three ad-hoc implementations). |
| **Status** | `accepted` — **H.2 → 🟡** (BUILT + offline-proven 2026-09-13 on `feature/story-H.2`). H.2 is a letter-track id (not `STORY_ID_RE`), so its 🟡 does NOT arm the advancement gate; no Validation Debt Register entry. Awaits the recorded LIVE sign/verify crossing (`docs/session-briefs/story-H.2-LIVE-RUNBOOK.md`). |
| **As built** | (1) `decision.token.v1` allow-list contract (`schemas/` + `lib/decision_auth/` byte-identical; `scripts/gen_decision_token_contract.py` in `gen_contracts.py`): `decision` enum `accepted`|`rejected` (NO `inconclusive` — a hold issues no token), `sha256` binding, `issued_at` freshness, `key_id`; no verdict field. (2) `lib/decision_auth/` PURE verify library — `canonical.py` (deterministic signed bytes), `verify.py` (fail-closed verify-then-act gate with an INJECTED signature verifier: shape → signature → decision → sha256/SI-7 → freshness → key trust; no `ok=True` without all checks), `signature.py` (the ONLY crypto — `cryptography` ECDSA-P256/SHA-256, isolated + bundled at runtime like `hub_ingest` jsonschema; tests inject a stub + never import it). (3) `infra/lib/ztie-decision-signing-stack.ts` (Hub) — KMS asymmetric ECC_NIST_P256 SIGN_VERIFY key, `RETAIN`, Hub-only `kms:Sign`+`kms:GetPublicKey` (no `kms:Verify` — spokes verify offline), outputs `DecisionSigningKeyArn`(= token `key_id`)+`DecisionSigningKeyId`; wired bin Stack 10; no Lambda. |
| **Offline proof** | `lib/decision_auth/` tests **36 OK** (4 jsonschema-live skips) — every fail-closed branch via a stub verifier (valid / bad-sig / verifier-raises / wrong-decision / sha-mismatch / case-insensitive-sha / stale / future / bad-time / untrusted-key / rotation-set / all shape guards / no-ok-without-all-checks) + canonical determinism + no-`inconclusive`/no-verdict conformance; `ruff` clean (`# noqa: BLE001` on the 3 fail-closed excepts); `tsc` NO new error type (new stack + bin = missing-`aws-cdk-lib` family only); `prettier` clean; `gen_contracts.py` no drift. |
| **Next** | The **H.2 LIVE validation** (single next action): deploy the Hub signing key, export the public key, Hub signs a real `decision.token.v1`, the spoke verifies it OFFLINE + every fail-closed branch refuses, no spoke→Hub call. On the recorded pass H.2 flips ✅ and the **4.6 rework** is unblocked (verify a Hub-signed `accepted` token offline → push; remove the cross-account Hub read grant; then 4.6's single live pass). 4.7 + 4.4 inherit the primitive. **Story 4.6 stays 🟡.** |


---

## 2026-09-14 - Story H.2 VALIDATED LIVE → ✅ (RD-048/RD-049 crossing proven); next = the 4.6 rework

| Field | Value |
|-------|-------|
| **Action** | Recorded the LIVE sign/verify crossing for **Story H.2** (the authenticated Hub→spoke decision mechanism) and closed it ✅. Build PR #146 (branch `feature/story-H.2`); close-out on branch `docs/story-H.2-validate` flips H.2 🟡→✅ + records the result. |
| **Result (verbatim, recorded)** | Hub 641628980935. `ZtieDecisionSigningStack` deployed; live key verified asymmetric **SIGN_VERIFY / ECC_NIST_P256 / ECDSA_SHA_256** (`key/3321e5b7-2ca3-42e3-b99c-9b9d83a45243`). Public key exported via `aws kms get-public-key` (PEM). Hub signed a real `decision.token.v1` for intake `891cb78f-fd35-4045-81d6-030d75d9c83e` (`decision: accepted`, `sha256: cd0429…`) over the canonical bytes (304 B) with `kms:Sign ECDSA_SHA_256` → 72-byte DER signature. The spoke verified it **OFFLINE** against the exported public key via the real `lib/decision_auth` (`cryptography` 49.0.0), **no AWS call**: `VALID -> True ok`. Fail-closed branches all refused: `sha-mismatch -> sha_mismatch`, `wrong-decision -> wrong_decision`, `untrusted-key -> untrusted_key`, `bad-signature -> bad_signature` (one bit flipped — proves real crypto, not a stub), `stale -> stale`. No spoke→Hub read anywhere (RD-048 proven live). |
| **Status** | `accepted` — **H.2 → ✅** (validated live 2026-09-14). H.2 is a letter-track id, so it never armed the advancement gate. **Story 4.6 remains 🟡** (the sole feature-debt entry). |
| **Next** | The **4.6 REWORK** (now unblocked): change `pde_handoff` from reading `human_decision` cross-account to **verifying a Hub-signed `accepted` `decision.token.v1` OFFLINE** (via `lib/decision_auth`, `cryptography` Docker-bundled) — which already includes the sha256 binding — then push; **REMOVE** the cross-account `dynamodb:GetItem` grant; keep the Sandbox landing stack + one-directional least-privilege push + verdict-free outcome crossing unchanged. Then 4.6 gets its single live pass on the reworked code → ✅. 4.7 (verify `rejected` → destroy) + 4.4 (Hub sign-side + one-directional Hub→Forensic delivery) inherit the primitive. Per the stakeholder-set order (2026-09-13): H.2 live ✅ → push restore tags → 4.6 rework. |


---

## 2026-09-14 - Restore tags PUSHED (code half): restore/phase-3-green + restore/story-4.5-green

| Field | Value |
|-------|-------|
| **Action** | The owner pushed the two annotated restore tags prepped in PR #143 (`docs/session-briefs/restore-tags-phase3-and-4.5-PROMPT.md`), pinned to the explicit validated-close commits. Verified on origin (executor + owner). |
| **Result (verbatim)** | `git ls-remote --tags origin` now lists NINE restore tags. `restore/phase-3-green` → annotated (`git cat-file -t` = `tag`), derefs to `e2b325d` (PR #122, Phase 3 CLOSED, RD-040). `restore/story-4.5-green` → annotated, derefs to `537d61c` (PR #138, 4.5 validated incl. the live Decimal fix #137 `5d7fa96`). Both pushed with pre-verify (`git merge-base --is-ancestor <target> origin/main` OK for both; `5d7fa96` ancestor of `537d61c` OK). |
| **Status** | `accepted` — the CODE half of both restore points is locked. The STATE half (paired manifests) remains open as **OD-004** (a live-capture task: `scripts/ztie-restore` in Hub + Forensic + Pipeline-Sandbox, commit under `restore-manifests/`, fill BOM rows, confirm each manifest's `governance_commit.sha` == its tag target). Non-blocking. |
| **Next** | Per the stakeholder order (2026-09-13): H.2 live ✅ → restore tags ✅ → the **4.6 rework** onto the authenticated-decision primitive. |


---

## 2026-09-14 - Story 4.6 REWORKED onto the authenticated-decision primitive (still 🟡; awaits its live pass)

| Field | Value |
|-------|-------|
| **Action** | Reworked Story 4.6 (`feature/story-4.6-rework`) so the Forensic pusher VERIFIES a Hub-signed `decision.token.v1` OFFLINE (RD-048/RD-049, the H.2 primitive) instead of reading the Hub cross-account. Per the stakeholder order: H.2 live ✅ → restore tags ✅ → this rework. |
| **As built** | `lambdas/pde_handoff/handler.py` now takes `{intake_id, decision_token, signature, artifact_s3_key}`, recomputes the artifact sha256, and runs `handoff.evaluate_token_gate` → the VENDORED `lib/decision_auth` `verify.verify_decision` (push iff signature verifies against the embedded Hub public key AND decision==accepted AND token.sha256==recomputed sha AND fresh AND trusted key_id). `awsio.py` DROPPED `get_tracking_item` (only sha/push/send remain). The Lambda VENDORS `lib/decision_auth` (canonical/verify/signature/token schema, byte-identical + a no-drift test) and is DOCKER-BUNDLED (`cryptography` for the ECDSA verify, like hub_ingest's jsonschema). `ZtiePdeHandoffStack` REMOVED the `dynamodb:GetItem` grant + `TRACKING_TABLE` env; ADDED `HUB_PUBLIC_KEY_PEM` + `TRUSTED_KEY_IDS` env + props (from the H.2 `ZtieDecisionSigningStack`); kept `s3:GetObject`(intake/*) + `s3:PutObject`(one prefix) + `sqs:SendMessage`. The Sandbox landing stack + one-directional push + verdict-free `handoff` outcome crossing are UNCHANGED. 4.6 now depends on 4.1 + H.2 (still build tier 14). |
| **Offline proof** | `lambdas/pde_handoff/` tests 42 OK (5 jsonschema-live skips) — the token-verify gate + every fail-closed branch via a stub verifier; `test_handler` asserts the seam has NO `get_tracking_item` (the Hub-read path is gone). `ruff` clean; `tsc` no new error type; `prettier` clean; `gen_contracts.py` no drift. |
| **Status** | `accepted` — **Story 4.6 stays 🟡** (still the sole feature-debt entry; the covenant: no ✅ without a recorded live pass of the FINAL code). Its deployed stacks will be redeployed onto the reworked code during the live pass, not torn down. |
| **Next** | The reworked **4.6 LIVE validation** (`docs/session-briefs/story-4.6-LIVE-RUNBOOK.md`, FRESH — supersedes the old): Hub signs an `accepted` token → the Forensic pusher verifies it OFFLINE + pushes → the artifact lands in Pipeline-Sandbox (hash matches) → every fail-closed branch refuses → only a bounded verdict-free outcome crosses to the Hub; the live pusher role has NO `dynamodb` and NO `TRACKING_TABLE`. On the recorded pass 4.6 flips ✅. Then **4.7** (verify a `rejected` token → destroy) + **4.4** (the human UI + Hub sign-side / one-directional delivery, closes Phase 4) inherit the primitive. |


---

## 2026-09-14 - Story 4.6 VALIDATED LIVE → ✅ (reworked ACCEPT-push; RD-048/RD-049 crossing proven end-to-end); next = 4.7

| Field | Value |
|-------|-------|
| **Action** | Ran the reworked **Story 4.6 LIVE validation** across the three accounts (Hub 641628980935 signs / Forensic 360999005254 pusher + artifact / Pipeline-Sandbox 586917955591 landing), intake `891cb78f-fd35-4045-81d6-030d75d9c83e`. Recorded pass on the FINAL fixed code; 4.6 flipped 🟡 → ✅ and cleared from the Validation Debt Register (register now EMPTY, advancement gate OPEN). |
| **Result** | Pusher role (live) = ONLY `s3:GetObject`/`s3:PutObject`/`s3:PutObjectTagging`/`sqs:SendMessage` — **NO `dynamodb`, NO `bedrock`**; env has `HUB_PUBLIC_KEY_PEM` (full 178 B) + `TRUSTED_KEY_IDS`, **NO `TRACKING_TABLE`/`NOVA_MODEL_ID`** (the rework's whole point — no spoke→Hub read). Hub signed an `accepted` `decision.token.v1` (`kms:Sign` ECDSA_SHA_256 over the 304 B canonical bytes); the pusher verified it OFFLINE and pushed → `pushed: true`, `outcome: pushed`; the object landed in the Sandbox (`accepted/891cb78f-…/probe.yaml`, sha256 == tracked `cd0429…`). FAIL-CLOSED 5/5 (no-token 400; rejected→`wrong_decision`; sha-mismatch→`refused_hash_mismatch`; stale→`stale`; tampered→`bad_signature`) with nothing leaking (exactly 1 object under `accepted/`). The bounded verdict-free `handoff` outcome crossed Forensic→Hub via the RD-013 ingest queue (`handoff_outcome: pushed`, no effective-verdict key). |
| **Live fixes (fix-then-validate-once)** | (1) **PR #153** — the multi-line Hub PEM passed via `-c hubPublicKeyPem="$(cat)"` truncated to a 27-byte header, so offline verify fail-closed with `bad_signature` on the happy path (`aws kms verify` was `SignatureValid: true` + `cryptography` was bundled → isolated the fault to the truncated embedded key). Fix: `bin/ztie-infra.ts` accepts a single-line `hubPublicKeyPemBase64` (decoded via `Buffer.from`); redeploy with `-c hubPublicKeyPemBase64=$(base64 -w0 pub.pem)` put the full 178 B PEM on the Lambda. (2) **`ZtieHubTrackingStack` redeploy (no code change)** — the live `hub_ingest` validator didn't yet know the `handoff` envelope kind (deploy-gap since the 4.6 build), so the first crossed outcome was quarantined; redeploying shipped the kind and a re-invoke crossed cleanly. |
| **Status** | `accepted` — 4.6 ✅ (validated live 2026-09-14). This does NOT close Phase 4 (4.7 + 4.4 remain; P4 roll-up stays 🟡). Reusable lesson: pass any multi-line CDK context (PEMs, certs) as single-line base64; and redeploy the Hub ingest stack whenever a new RD-013 envelope kind is added (the deploy-gap class). |
| **Next** | **Story 4.7** (REJECT → destroy artifact + detonation chamber in Forensic; INCONCLUSIVE → hold) — the tied tier-14 sibling of 4.6 and first-OPEN pipe story, on the Phase-4-closure critical path (4.4 depends on 4.3 + 4.7). 4.7 verifies a Hub-signed `rejected` `decision.token.v1` OFFLINE the SAME way 4.6 verifies `accepted` (the H.2 primitive). The existing `story-4.7-*` handoff predates RD-048 and was REFRESHED this session to the verify-a-signed-token shape. Then **4.4** closes Phase 4. Per the 2026-09-13 reorder the Phase-4 pipe work stays ahead of the F&H **B.1** track. |


---

## 2026-09-14 - REORDER: Story 2.2G (Gitleaks integration) prioritized ahead of 4.7; BUILT + offline-proven → 🟡

| Field | Value |
|-------|-------|
| **Recommended next (by the book)** | The strict first-OPEN tier order after 4.6 ✅ is **Story 4.7** (tier 14, REJECT→destroy). |
| **Stakeholder decision (reorder)** | Work **Story 2.2G** (Gitleaks integration in the static lane, tier 4) THIS session instead — prioritized by the stakeholder over the tier-14 pipe work. This is a stakeholder-decided reorder recorded here per the Sequencing rule (RUNBOOK binding gate + SEQUENCING_METHOD §4a); it is NOT an executor self-selection. 2.2G is an additive static-lane enhancement, NOT on the Phase-4-closure critical path, so pulling it forward does not disturb the 4.7→4.4 closure path. |
| **Action** | Built Story 2.2G on branch `feature/story-2.2G`: embedded the pinned compiled `gitleaks` binary (`GITLEAKS_VERSION=8.30.1`) in the `ZtieStaticScanStack` container, added a NON-EXECUTING subprocess seam (`scanners.run_gitleaks` — `gitleaks dir <path> --report-format json --report-path /dev/stdout --no-banner --exit-code 1`; `detect` is deprecated in v8.19+), normalized its output into `static-findings.contract.v1` (v1.2) with `tool=gitleaks` + `check_family=signature` + fixed `severity=high` + REDACTED secrets, added `gitleaks` to both `toolplan` classes, mapped it to the SECRET controls (IA-5/SC-28 · A.5.17/A.8.24) in `compliance.py`, and — per the stakeholder's Decision-C override — SUPERSEDED the Story-2.2 embedded SECRET regex rules (`ZTIE-SIG-SECRET-*` removed from `signatures.py`; DANGEROUS + MALWARE families retained). Contracts regenerated to v1.2 (the `gitleaks` tool added to the `TOOLS` enum in both generators + all three bundled copies incl. `hub_ingest`); the summary Hub version pin bumped to `SUMMARY_CONTRACT_VERSION=1.2` in `hub_ingest/handler.py`, `ztie-hub-tracking-stack.ts`, and the emitting `ztie-static-scan-stack.ts`. |
| **Also cleared (pre-existing governance defect, gate was disarmed)** | `docs/LIVE_RUNBOOK_TEMPLATE.md` (added in `171a374`) was never in `check_docs.py`'s `TEMPLATE_FILES` exemption, so CHECK F failed on a clean `main` (and `test_check_docs` reported 4 failures). Added it to the exemption → `check_docs` PASS + `test_check_docs` OK restored. Also reconciled PROJECT_PLAN↔RUNBOOK for 2.2G (registered **RD-050**; Phase-2 prose updated; COMPLIANCE RD-050 row Proposed) since 2.2G was in the RUNBOOK master table but absent from the plan's decisions. |
| **Result** | Offline proof bar green: `test_normalize` 42 OK (2 jsonschema-live skips; new `TestNormalizeGitleaks` moves the SECRET assertions to the gitleaks normalizer + a `test_no_secret_rules_remain` proving the SECRET family is gone; DANGEROUS/MALWARE assertions retained); ruff clean; `env -u NODE_OPTIONS npx tsc --noEmit` adds NO new error type; prettier clean; `gen_contracts.py` no drift beyond the two v1.2 static contracts; `check_docs.py` PASS + `test_check_docs` OK. Authored `docs/session-briefs/story-2.2-G-LIVE-RUNBOOK.md` (Hub-ingest redeploy FIRST, then the static lane — the v1.2 deploy-gap). |
| **Status** | `accepted` — 2.2G is **🟡** (built + offline-proven), added to the Validation Debt Register as the sole open entry (advancement gate ARMED). It clears ONLY on its own recorded live pass. |
| **Next** | **VALIDATE 2.2G LIVE** per `docs/session-briefs/story-2.2-G-LIVE-RUNBOOK.md`. On the recorded pass 2.2G flips ✅, the register empties, and the next pipe work is **Story 4.7** (REJECT→destroy), then **4.4** closes Phase 4. `check_docs` CHECK J will advise on-deck (2.2G) vs first-OPEN-by-row-order (4.7) — reconciled by THIS entry. |
