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
| **Status** | `awaiting-user-decision` (a proposal for you to accept or refine) |

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
