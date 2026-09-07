# On deck (the current next-session starter)

> This folder points at the ONE prompt to paste to start the next working session.
> It is kept to a single current pointer so there is never an ambiguous or stale
> starter here.

## Next session: Story 2.6 - Parallel orchestration / fork of the two lanes

Paste this file as the first message of the next session:

- **[`../story-2.6-PROMPT.md`](../story-2.6-PROMPT.md)**

Its stakeholder-facing brief is **[`../story-2.6-brief.md`](../story-2.6-brief.md)**.

### Why 2.6 is next
By the RUNBOOK's dependency build-tier order, Story 2.6 (tier 5) is the next buildable
pipeline story: its dependencies 2.1 (static lane) and 2.3 (dynamic lane) are both ✅,
and the Validation Debt Register is EMPTY, so the advancement gate is open. 2.6 adds the
parallel orchestration that closes Phase 2 - fork a routed artifact into both inspection
lanes concurrently, then join their two outputs into one collected record for Phase 3.

### Why NOT 2.4
Story 2.4 (behavioral telemetry) is NOT next: by the 2026-09-07 decision it is a hard
dependent of A.5 + A.6 (the "clean the ground first" stories - correct the Floor &
Harvest plan drift, then push the outstanding restore tags), which lifts 2.4 to tier 7.
2.6 does not pass through 2.4 (it needs the dynamic RUN, 2.3, not its telemetry capture),
so 2.6 is the correct next feature story. A.5/A.6 (tier 6, Track=F&H) are the
clean-ground items that gate 2.4 and can be picked up in parallel with / after 2.6.

### History note
Earlier on-deck starters (A.2 "validate 2.0", then B.1 "harvest inventory") were
superseded as the plan evolved. This folder holds only a single pointer to the current
starter so it cannot drift into pointing at already-completed or re-sequenced work; for
authoritative status and ordering, read `../../RUNBOOK.md`.
