# On deck (the current next-session starter)

> This folder points at the ONE prompt to paste to start the next working session.
> It is kept to a single current pointer so there is never an ambiguous or stale
> starter here.

## Next session: Story A.5 - correct the Floor & Harvest plan drift (docs-only)

Paste this file as the first message of the next session:

- **[`../story-A.5-PROMPT.md`](../story-A.5-PROMPT.md)**

Its stakeholder-facing brief is **[`../story-A.5-brief.md`](../story-A.5-brief.md)**.

### Why A.5 is next
Story **2.6 was validated live 2026-09-08 (4/4 DoD) and is ✅**, which cleared it from
the Validation Debt Register — so the register is **EMPTY** and the advancement gate
(RD-023) is disarmed. By RUNBOOK build tier, the next work is the Floor & Harvest
clean-ground pair: **A.5** (tier 6, docs-only — correct two stale claims in
`docs/governance/FLOOR_AND_HARVEST_PLAN.md`) then **A.6** (push the outstanding restore
tags, owner action). Together A.5 + A.6 gate **2.4** (behavioral telemetry capture).
STEP 0 of the A.5 prompt must RE-CONFIRM this on `main` (trust `main` + `check_docs.py`
over any prose) before touching anything.

### Note on Phase 2
2.6 completed the **parallel-fork orchestration** (both lanes run concurrently + join
into one verdict-free record). Phase 2 is **not fully closed**, though: the P2
phase-gate requires "real behavioral telemetry," which is **Story 2.4** (still ⬜), and
2.5 (telemetry sanitization) is also still ⬜. So the P2 Progress-Summary row stays
⬜ until 2.4/2.5 land — 2.6 did not flip the phase gate.

### Just-closed context (Story 2.0E, validated 2026-09-08)
2.0E's final design is the **two-tier** endpoint model (RD-027): the SSM control
channel (`ssm`/`ssmmessages`/`ec2messages`) is ALWAYS-ON in a single AZ (~$22/mo,
reliable), while `logs`/`sqs`/`bedrock-runtime` are EPHEMERAL per detonation
(~$66/mo recovered). It was validated live 5/5, `main` was reconciled (PR #70) and the
Forensic deployed-state restore point set (tag `restore/story-2.0E-green`, PR #71).
The 2.6 prompt's HARD-WON LESSONS section carries forward the specific traps from that
session (the conflicting-DNS-domain sweep-recreate race + its create-retry fix; log-is-
evidence vs. live endpoint polling; `npm install` vs. `npm ci`).

### Not next
- **2.4** (behavioral telemetry) is a hard dependent of A.5 + A.6 (the "clean the
  ground first" stories), which lifts it to tier 7. 2.6 does not depend on it.
- **Tenancy (T.1/T.2/T.3, RD-028)** is a separate track. T.1 (design spike, doc-only)
  may proceed early to protect the Phase-4 dashboard/Hub design; T.2/T.3 are DEFERRED
  to the commercialization phase (after the core pipeline works). Decisions are
  settled in RD-028 (per-subscriber account = hard boundary; within-org shared-trust +
  org-shared dashboard; per-subscriber granularity; residue bounded by the ephemeral
  host).

### History note
Earlier on-deck starters (A.2 "validate 2.0", B.1 "harvest inventory", a premature 2.6
pointer, then the 2.0E validation pointer) were superseded as the plan evolved. This
folder holds only a single pointer to the current starter so it cannot drift into
pointing at already-completed, gated, or re-sequenced work; for authoritative status
and ordering, read `../../RUNBOOK.md`.
