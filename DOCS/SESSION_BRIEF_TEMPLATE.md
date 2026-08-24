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

---

## Story {{STORY_ID}} — {{STORY_TITLE}}

| Field | Value |
|-------|-------|
| **Phase** | {{PHASE}} |
| **Date** | {{DATE}} |
| **Status** | {{Not Started / In Progress / Blocked / Done}} |
| **Builds from restore point** | {{tag or "none yet"}} |
| **Session goal** | {{one sentence: what this session achieves}} |

---

### Background & Context

{{2–4 sentences: what the project is, where it currently stands (which phases are
done), and why this story is being done now. Enough footing for a newcomer.}}

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

- **Approach:** {{concise do-it steps}}
- **Hard constraints:** {{the non-negotiables from the plan that apply here}}

### Validation Rationale & Compliance Mapping (optional)

- **Rationale:** {{what this story does for the project's quality/security posture}}
- **Candidate control mappings** *(if applicable — proposed, pending ratification):*

| Framework | Control ID | Control Name | Rationale | Status |
|-----------|-----------|--------------|-----------|--------|
| {{...}} | {{...}} | {{...}} | {{...}} | Proposed |

- **Audit evidence produced:** {{artifact this story leaves behind}}

### Change & Rollback

- **Change type:** {{standard / normal}}
- **Restore point this builds from:** {{tag}}
- **Backout plan:** {{how to revert — coordinated restore to the last good point}}

### Definition of Done / Validation Gate

> A **pass/fail gate**, not a description. Per the runbook's binding Validation &
> Advancement Gate: the user validates live, the executor records the result, and
> only a recorded pass flips the status. Failure means we stay on this story.

- **Done means:** {{the exact validation criterion}}
- **Validated by:** {{who runs the live check — typically the user}}
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
