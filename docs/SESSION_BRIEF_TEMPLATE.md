# Session Brief — TEMPLATE

> **Purpose.** A single briefing generated at the start of each story session,
> giving every stakeholder the background and objectives they need. It doubles as
> the change record and audit artifact for that story.
>
> **How it is used.** One brief per story (stored under `session-briefs/`),
> populated from [`RUNBOOK.md`](RUNBOOK.md). Copy this template, fill every
> `{{...}}`, and delete these instruction blockquotes.
>
> **Written during the prior session:** authored at the END of the preceding
> story while context is fresh, so its Lessons Learned section reflects what
> actually just happened.
>
> **The standard (derived from the A.2 brief).** A strong brief situates the story
> inside the validation-gate state machine before describing the work. It (1) names
> **what the story IS** — its *nature* and *role in the gate* (new feature /
> debt-clearing / phase-close / governance-only) with the one sentence that prevents
> the most likely category error; (1a) names **where it sits** — its **build tier**
> and whether the session **advances to a new tier** (a new dependency layer opening),
> so STEP 0 re-confirms the whole new dependency set; (2) records the **expected
> true-state facts** the
> session must re-confirm (STEP 0), so prompt↔`main` drift is caught; (3) states the
> **DoD as an enumerated, externally-anchored checklist** ("the N checks in …§M;
> reference it, do not re-derive"), with any **known caveat baked into the relevant
> check** ("if X is empty, that is the finding — do NOT pass it"); (4) makes **roles**
> unambiguous — who runs the live check vs. who RECORDS it verbatim, never simulate;
> and (5) lists **explicit negative scope**, including the subtle exclusions. A brief
> that omits the story's gate-role, its build tier / tier-transition, or its
> expected-truths is incomplete.

---

## Story {{STORY_ID}} — {{STORY_TITLE}}

| Field | Value |
|-------|-------|
| **Phase** | {{PHASE}} |
| **Build tier** | {{N}} — {{"advances tier N-1 → N (new dependency layer opens)" / "same tier N, tied with {{sibling}}"}} |
| **Date** | {{DATE}} |
| **Status** | {{Not Started / In Progress / Blocked / Done}} |
| **Builds from restore point** | {{tag or "none yet"}} |
| **Session goal** | {{one sentence: what this session achieves}} |

---

### Background & Context

{{2–4 sentences: what the project is, where it currently stands (which phases are
done), and why this story is being done now. Enough footing for a newcomer. State
the covenant in a line: nothing is ✅ until a recorded live pass.}}

### Where This Story Sits (build tier + position)

{{REQUIRED. State the story's BUILD TIER (= 1 + the highest tier of anything it
depends on; METHODOLOGY §1a, owned by the RUNBOOK master table) and whether this
session **moves to a new tier**. If it advances (tier N-1 → N), say which tier-≤N-1
dependencies just closed to open the new layer, and that STEP 0 must re-confirm the
WHOLE new dependency set is ✅ (not just the prior story) before work begins. Note if
the tier advance also coincides with a PHASE change (related but distinct). If it is
a tied sibling within the same tier, say so.}}

{{REQUIRED — SCHEDULE POSITION (METHODOLOGY §5.A.0). State that this story is the
**first OPEN item in the RUNBOOK "Ready now" schedule** (the agreed next story). If
this brief hands off a story that is NOT the scheduled next Ready item, it MUST record
the stakeholder's explicit reorder decision + a WORK_LOG reference — the executor never
self-selects an out-of-order Ready story or edits the schedule to justify it. "Ready"
(deps ✅) means it MAY be built, not that it is scheduled next.}}

### What This Story Is (nature + gate role)

{{One short paragraph naming the story's NATURE, because it changes what is allowed:
  - **NEW FEATURE** — new capability; may begin ONLY if its Depends-on are all ✅ AND
    the Validation Debt Register is empty (the advancement gate).
  - **DEBT-CLEARING / validation** — reworks or live-validates an existing 🟡/⛔ to
    clear its register row; PERMITTED while the register is non-empty; it CLEARS the
    gate, it does not walk through it (do NOT open a new feature story same session).
  - **PHASE-CLOSE** — its pass also closes a phase (capture restore point + BOM + flip
    the phase row).
  - **GOVERNANCE-ONLY** — records/docs only; do NOT touch pipeline/infra/lambda code.
Say which one this is, and the single sentence that prevents its most likely category
error.}}

### Objective & Value

- **Objective:** {{what this story delivers, concretely}}
- **Why it matters:** {{the value — capability gained or risk reduced}}

### Scope, Dependencies & Position

- **In scope:** {{concrete deliverables}}
- **Out of scope:** {{explicitly what this story does NOT do}}
- **Depends on:** {{prior stories/restore points that must be ✅ first}}
- **Unblocks:** {{downstream stories this enables}}
- **Roadmap position:** {{phase/milestone; how it advances the plan}}

### Approach & Constraints

- **Expected true-state (STEP 0 re-confirms before any edit):** {{the facts the
  session must verify against `main` + the consistency check — this story's expected
  status AND build tier, the tier transition (if advancing tier N-1 → N, that EVERY
  tier-≤N-1 dependency is ✅ so the new layer is open), each Depends-on ✅, prior
  story's state, restore tags present (flag any PHANTOM tag referenced-but-absent),
  and the Validation Debt Register state (empty / lists {{X}}). Trust `main` over the
  brief if they disagree.}}
- **Approach:** {{concise do-it steps}}
- **Roles:** {{who runs the live check (typically the stakeholder, on the live
  system) vs. who RECORDS the returned result verbatim (the executor). Never
  simulate/assume a live output. State "N/A" only for offline-only stories.}}
- **Hard constraints:** {{the non-negotiables from the plan that apply here}}

### Validation Rationale & Compliance Mapping (REQUIRED — RD-014)

- **Rationale:** {{what this story does for the project's quality/security posture}}
- **Candidate control mappings** *(RD-014: required for every story; proposed at
  authoring, ratified on review; candidate-until-ratified. Frameworks: NIST SP
  800-53 Rev 5 as catalog of record, NIST CSF, related NIST as relevant, and
  ISO/IEC 27001:2022 Annex A. If a story genuinely maps to no control, state
  "none — <why>" explicitly rather than leaving this blank.)* Also add ratified
  rows to [`../COMPLIANCE.md`](../COMPLIANCE.md).

| Framework | Control ID | Control Name | Rationale | Status |
|-----------|-----------|--------------|-----------|--------|
| NIST 800-53 r5 | {{e.g. SI-10}} | {{control name}} | {{why this story maps}} | Proposed |
| ISO 27001:2022 | {{e.g. A.8.x}} | {{control name}} | {{why}} | Proposed |

- **Audit evidence produced:** {{artifact this story leaves behind}}

### Management-Artifact Obligations (REQUIRED — RD-015)

> Management artifacts are first-class, held to the same bar as the code. This story
> is **not done** until these are satisfied (they are part of the Definition of Done):

- [ ] Story's **brief + runbook entry** updated (status, validation result, dates).
- [ ] **PROJECT_PLAN and RUNBOOK in exact alignment** (this story appears identically in both; phase story-sets match).
- [ ] Any **new/changed registered decisions** recorded in the plan; any **candidate control mappings** recorded (RD-014).
- [ ] All doc changes **PR-reviewed** (branch + PR, never straight to main).
- [ ] Governance kept **restorable** alongside the code (coordinates with the restore-point manifest).

### Change & Rollback

- **Change type:** {{standard / normal}}
- **Restore point this builds from:** {{tag}}
- **Backout plan:** {{how to revert — coordinated restore to the last good point}}

### Definition of Done / Validation Gate

> A **pass/fail gate**, not a description. Per the runbook's binding Validation &
> Advancement Gate: the user validates live, the executor records the result, and
> only a recorded pass flips the status. Failure means we stay on this story.

- **Done means:** {{the exact validation criterion. Prefer an ENUMERATED,
  externally-anchored checklist over prose — e.g. "the N checks in …§M (reference it;
  do not re-derive)". For any check with a KNOWN CAVEAT, bake it in: "if X is
  empty/absent, that is the finding — record it, do NOT pass the check."}}
- **Validated by:** {{who runs the live check — typically the stakeholder, live; the
  executor records the returned result verbatim}}
- **Validation Result:** {{`pass — <checked>, <date>, confirmed` or `FAIL — ...`;
  `pending` until validated}}
- **On pass (and only then):** record the Validation Result, set the runbook row
  ✅; at a phase-close, capture the restore point + inventory update + tag.
- **On fail:** story stays 🟡 (or ⛔ if externally blocked); the next session
  re-focuses on fixing + re-validating THIS story before any advancement.
- **Advancement gate:** this story could not start unless its `Depends on` were
  all ✅; downstream stories cannot start until this is ✅.

### Risks & Watch-Items

- {{known risk / thing to watch / a prior failure mode not to reintroduce}}

### Lessons Learned / Carry-Forward *(authored at the end of the prior session)*

- **What went well:** {{...}}
- **What went wrong / surprised us:** {{...}}
- **Current true state:** {{what is actually live right now; which restore point;
  note any code-vs-deployed drift}}
- **Must-know / must-avoid for this session:** {{explicit warnings}}
- **User notes:** {{open for the user to add anything}}
