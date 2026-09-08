# On deck (the current next-session starter)

> This folder points at the ONE prompt to paste to start the next working session.
> It is kept to a single current pointer so there is never an ambiguous or stale
> starter here.

## Next session: Story 2.4 - Behavioral telemetry capture

Paste this file as the first message of the next session:

- **[`../story-2.4-PROMPT.md`](../story-2.4-PROMPT.md)**

Its stakeholder-facing brief is **[`../story-2.4-brief.md`](../story-2.4-brief.md)**.

### Why 2.4 is next
By the RUNBOOK's dependency build-tier order, Story 2.4 (tier 7) is now the next
buildable pipeline story. Its full dependency gate is satisfied as of 2026-09-08:
2.3 ✅ (the detonation run it instruments), A.5 ✅ (Floor & Harvest plan-drift
corrected), and A.6 ✅ (both outstanding restore tags pushed + verified on origin -
all six restore tags now present). The Validation Debt Register is EMPTY, so the
advancement gate is open. 2.4 instruments the detonation: while a routed artifact runs
host-native on the ephemeral EC2, it captures the artifact's syscalls, network attempts,
and filesystem operations as bounded, derived evidence (full trace stays in Forensic;
only a bounded summary crosses to the Hub as a new envelope kind).

### Watch-item carried from 2.6 (read before validating)
2.6 (parallel orchestration, ✅ 2026-09-08) invokes the detonation lane 2.4 modifies.
The deploy-gap lesson: when a story changes a lane Lambda that an earlier orchestration
invokes, the LIVE lane can still be on its old deployed code - so 2.4's live validation
MUST redeploy the detonation lane stack (and the orchestration/Hub stacks if the
contract changed) BEFORE submitting a run. This is called out in the 2.4 prompt + brief.

### History note
Earlier on-deck starters (A.2, B.1, 2.6) were superseded as the plan progressed. This
folder holds only a single pointer to the current starter so it cannot drift into
pointing at already-completed or re-sequenced work; for authoritative status and
ordering, read `../../RUNBOOK.md`.
