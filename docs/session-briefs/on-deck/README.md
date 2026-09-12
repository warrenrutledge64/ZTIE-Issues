
> This folder points at the ONE prompt to paste to start the next working session.
> It is kept to a single current pointer so there is never an ambiguous or stale
> starter here.

## Next session: Story G-3 (CLOSE) — close the advancement-gate governance story

Paste this file as the first message of the next session:

- **[`../story-G-3-close-PROMPT.md`](../story-G-3-close-PROMPT.md)**

Its stakeholder-facing brief is **[`../story-G-3-close-brief.md`](../story-G-3-close-brief.md)**.

### Why G-3-close is next
G-3 (hard-pause enforcement, RD-023) was built long ago and has been actively
enforcing the advancement gate through every feature story since (it gated 3.1 and
3.2, and was extended with CHECK C when the master table became a true schedule). But
G-3's own status is still 🟡 — the machinery that enforces the covenant was never
itself validation-closed. That is the one genuine status inconsistency on the board
and it is a **near-free, OFFLINE close** (no AWS / CloudShell): verify the four
Definition-of-Done artifacts already exist on `main`, run `check_docs.py` (PASS) +
`test_check_docs` (SUITE `OK`) as the recorded pass, then flip 🟡 → ✅.

### After G-3: the pipeline resumes at Story 3.2
Per the RUNBOOK master table's OPEN queue, the recommended order is **G-3 → C.3
(shared `awsio`/generator seam) → 3.2 (Nova Pro correlation)**. Story 3.2's handoff
is already authored (`../story-3.2-brief.md` + `../story-3.2-PROMPT.md`); C.3 is held
until G-3 is green (stakeholder decision).

### Watch-items for the G-3 close (read before starting)
- **CLOSE, not build.** Do NOT rebuild or re-scope the checker; verify + record only.
- **Governance-story nuance.** G-3 is a `G-` story, EXEMPT from `check_docs` CHECK A/B,
  so it is correctly NOT in the Validation Debt Register even while 🟡; flipping it ✅
  does not clear a register row and does not change `check_docs` output. Do NOT touch
  the `_NEW_WORK_STORY` fixture pin (that tracks the next ⬜ *pipe* story).
- **Timing.** Run `check_docs.py` AFTER committing the status edit (CHECK B reads the
  committed HEAD as its baseline).

### History note
Earlier on-deck starters (A.2, B.1, 2.6, 2.5) were superseded as the plan progressed.
This folder holds only a single pointer to the current starter so it cannot drift into
pointing at already-completed or re-sequenced work; for authoritative status and
ordering, read `../../RUNBOOK.md` (its master table OPEN section is the live queue).
