# On deck (the current next-session starter)

> This folder points at the ONE prompt to paste to start the next working session.
> It is kept to a single current pointer so there is never an ambiguous or stale
> starter here. For authoritative status and ordering, read `../../RUNBOOK.md`.

## Next session: Story G-1 — Compliance back-mapping (RD-014)

Paste this file as the first message of the next session:

- **[`../story-G-1-PROMPT.md`](../story-G-1-PROMPT.md)**

Its stakeholder-facing brief is **[`../story-G-1-brief.md`](../story-G-1-brief.md)**.

### Why G-1 is next (and where 3.2 / the pipe track is)
Story **G-2** (management-artifact integrity, RD-015) closed ✅ on 2026-09-12 — the
`check_docs.py` gate now enforces plan↔runbook divergence, dangling RD refs, stray
placeholders, undated ✅ stories, living-doc glyph drift, dangling links, and an advisory
sequence-adherence note (CHECK D–J on top of A/B/C). With **G-3, C.3, and G-2 all closed**,
the highest-value item is the pipe feature **3.2 (Nova Pro correlation)** — but **3.2 is
being worked in a SEPARATE session** and already has its brief/prompt, so it is off-limits
to this governance track. Of the remaining OPEN "Ready now" items, **G-1 is the first**
(the RUNBOOK bucket A, top-down). G-1 is a `gov`, tier-0, **finish-and-ratify** story:
`docs/COMPLIANCE.md` already exists (framework scope + candidate-vs-ratified convention +
seeded mappings), so G-1 COMPLETES the matrix for the remaining artifacts and gets an
accountable reviewer to flip `Proposed → Ratified` — it does NOT build the compliance doc
from scratch. It is low-urgency (best once the Phase-3 design stabilizes); if the
stakeholder prefers to prioritize the pipe track or **T.1** (multi-tenancy design spike,
which should land before Phase 4) instead, that is a legitimate reorder — record it in
`../../governance/WORK_LOG.md` before starting (RD-024).

### Sequencing discipline (read this)
The RUNBOOK carries a binding **Sequencing rule** and METHODOLOGY §5.A.0 adds a
session-open **sequence check**: the story to START is the first OPEN item in the RUNBOOK
"Ready now" schedule, and working a *different* Ready story is a stakeholder-decided
reorder (recorded in WORK_LOG), never an executor self-selection or a quiet edit of the
"Default next action." `check_docs.py` CHECK J now surfaces this mechanically as a
**non-blocking advisory** (it points you to WORK_LOG to confirm a recorded reorder rather
than hard-failing it, because reordering is the stakeholder's call).

### Watch-items for the G-1 session (also in the prompt)
- **Finish + ratify, do NOT rebuild** `docs/COMPLIANCE.md`. Extend the existing matrix;
  candidate mappings are labeled `Proposed` until an accountable reviewer ratifies —
  never assert ZTIE "is compliant" (RD-014).
- **G-1 is a `G-` story** — exempt from CHECK A/B/C, not in the register; flipping it ✅
  changes no register row and does not touch the `_NEW_WORK_STORY` fixture pin.
- **Keep the docs consistent** — `check_docs.py` (now CHECK A–J) runs on every status
  change; update the **RUNBOOK master table ONLY** for status, and let README / this
  on-deck pointer / BUILD_ORDER POINT to it (do not hand-copy status). No new RD is
  required for G-1 (it executes RD-014); if one is ever warranted, take the next free
  number by grepping PROJECT_PLAN (do not hard-code a not-yet-defined RD id — CHECK E
  will flag it).

### History note
Earlier on-deck starters (A.2, B.1, 2.6, 2.5, C.3, 3.2, G-2) were superseded as the plan
progressed. This folder holds only a single pointer to the current starter so it cannot
drift into pointing at already-completed or re-sequenced work; for authoritative status
and ordering, read `../../RUNBOOK.md`.
