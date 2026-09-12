# On deck (the current next-session starter)

> This folder points at the ONE prompt to paste to start the next working session.
> It is kept to a single current pointer so there is never an ambiguous or stale
> starter here.

## Next session: Story G-2 — Management-artifact integrity (RD-015)

Paste this file as the first message of the next session:

- **[`../story-G-2-PROMPT.md`](../story-G-2-PROMPT.md)**

Its stakeholder-facing brief is **[`../story-G-2-brief.md`](../story-G-2-brief.md)**.

### Why G-2 is next (and where 3.2 is)
Story C.3 (shared contract generator + Hub-gate seam, RD-034) closed ✅ on 2026-09-12.
**Story 3.2 (Nova Pro correlation) is being worked in a SEPARATE session** — it is NOT
this starter and must be left untouched by a G-2 session (do not touch 3.2's
brief/prompt or the `_NEW_WORK_STORY` fixture pin). The stakeholder chose **G-2** as the
next governance story to prepare (WORK_LOG 2026-09-12). G-2 is a `gov`, tier-0,
finish-and-extend story: `scripts/check_docs.py` already exists (built by G-3) with CHECK
A/B/C, so G-2 EXTENDS it with the remaining integrity checks + the doc-drift guardrails
(b1/b2/b3) from the 2026-09-12 audit + an optional advisory sequence-adherence check (a2),
converts duplicated status surfaces to pointers, and documents the reusable-OS/instance
boundary. Do NOT rebuild the checker.

### Sequencing discipline (new — read this)
As of 2026-09-12 the RUNBOOK carries a binding **Sequencing rule** and METHODOLOGY §5.A.0
adds a session-open **sequence check**: the story to START is the first OPEN item in the
RUNBOOK "Ready now" schedule, and working a *different* Ready story is a
stakeholder-decided reorder (recorded in WORK_LOG), never an executor self-selection or a
quiet edit of the "Default next action." This was added after a story was started out of
schedule order; G-2's optional (a2) check is the mechanical backstop for it.

### Watch-items for the G-2 session (also in the prompt)
- **Finish + extend, do NOT rebuild** CHECK A/B/C. Keep the checker stdlib-only, offline,
  Python-3.9-compatible; every new check gets a self-test that proves it FIRES (read the
  suite `OK` line, not the in-suite `check_docs: FAIL …` fixture prints).
- **De-dup carefully** — replace README/BUILD_ORDER *duplicated status tables* with
  pointers, not the surrounding narrative; scope the glyph check to LIVING docs only
  (never rewrite a dated frozen brief/PROMPT/LIVE-RUNBOOK/WORK_LOG).
- **G-2 is a `G-` story** — exempt from CHECK A/B/C, not in the register; flipping it ✅
  changes no register row and does not touch `_NEW_WORK_STORY`.
- **Next free RD is RD-035** if the de-dup design warrants one (re-verify with the grep).

### History note
Earlier on-deck starters (A.2, B.1, 2.6, 2.5, C.3, 3.2) were superseded as the plan
progressed. This folder holds only a single pointer to the current starter so it cannot
drift into pointing at already-completed or re-sequenced work; for authoritative status
and ordering, read `../../RUNBOOK.md`.
