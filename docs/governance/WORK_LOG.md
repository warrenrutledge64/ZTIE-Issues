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
