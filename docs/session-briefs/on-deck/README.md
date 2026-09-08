# On deck (the current next-session starter)

> This folder points at the ONE prompt to paste to start the next working session.
> It is kept to a single current pointer so there is never an ambiguous or stale
> starter here.

## Next session: Story 2.0E - validate the two-tier detonation endpoints (LIVE)

Paste this file as the first message of the next session:

- **[`../story-2.0E-PROMPT.md`](../story-2.0E-PROMPT.md)**

Its stakeholder-facing brief is **[`../story-2.0E-brief.md`](../story-2.0E-brief.md)**.

### Why 2.0E is next (NOT 2.6)
Story 2.0E is the SOLE OPEN entry in the Validation Debt Register (🟡 - built +
offline-validated, awaiting a live pass). By the hard-pause / advancement gate
(RD-023), **no new feature story may start while the register is non-empty**, so
finishing 2.0E's live validation is the required next action. Reworking/validating an
open register entry is explicitly the permitted in-progress work.

2.0E's final design is the **two-tier** endpoint model (RD-027): the SSM control
channel (`ssm`/`ssmmessages`/`ec2messages`) is ALWAYS-ON in a single AZ (~$22/mo,
reliable), while `logs`/`sqs`/`bedrock-runtime` are EPHEMERAL per detonation
(~$66/mo recovered). This followed a 3-attempt live investigation that proved per-run
creation of the SSM control channel is unreliable (host could not connect to a
same-run-created SSM endpoint; DNS/SG/subnet/AZ all ruled out). The idle bleed is
already stopped; this session confirms the two-tier design live and flips 2.0E ✅.

### What becomes next-up AFTER 2.0E is ✅
Once 2.0E's live pass is recorded and it clears the register, the advancement gate
opens and **Story 2.6** (parallel orchestration / fork of the two inspection lanes,
tier 5, deps 2.1 ✅ + 2.3 ✅) is the next pipeline story. At that point repoint this
on-deck file to `../story-2.6-PROMPT.md`.

### Not next
- **2.6** is gated until 2.0E clears the register (above).
- **2.4** (behavioral telemetry) is a hard dependent of A.5 + A.6 (the "clean the
  ground first" stories), which lifts it to tier 7.
- **Tenancy (T.1/T.2/T.3, RD-028)** is a separate track. T.1 (design spike, doc-only)
  may proceed early to protect the Phase-4 dashboard/Hub design; T.2/T.3 are DEFERRED
  to the commercialization phase (after the core pipeline works). Decisions are
  settled in RD-028 (per-subscriber account = hard boundary; within-org shared-trust +
  org-shared dashboard; per-subscriber granularity; residue bounded by the ephemeral
  host).

### History note
Earlier on-deck starters (A.2 "validate 2.0", B.1 "harvest inventory", then a
premature 2.6 pointer) were superseded as the plan evolved. This folder holds only a
single pointer to the current starter so it cannot drift into pointing at
already-completed, gated, or re-sequenced work; for authoritative status and ordering,
read `../../RUNBOOK.md`.
