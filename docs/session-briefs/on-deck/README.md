# On deck (the current next-session starter)

> This folder points at the ONE prompt to paste to start the next working session.
> It is kept to a single current pointer so there is never an ambiguous or stale
> starter here.

## Next session: Story 2.6 - parallel orchestration (fork the two inspection lanes)

Paste this file as the first message of the next session:

- **[`../story-2.6-PROMPT.md`](../story-2.6-PROMPT.md)**

Its stakeholder-facing brief is **[`../story-2.6-brief.md`](../story-2.6-brief.md)**.

### Why 2.6 is next
Story 2.6 is a NEW FEATURE story (build tier 5, deps 2.1 ✅ + 2.3 ✅). It may begin
because **both** gate conditions now hold: its dependencies are ✅ **and** the
Validation Debt Register is **EMPTY**. The register was emptied on 2026-09-08 when
Story 2.0E was validated live (5/5 DoD) and flipped ✅, so the advancement gate
(RD-023) is disarmed. STEP 0 of the prompt must still RE-CONFIRM this on `main`
(trust `main` + `check_docs.py` over any prose) before touching anything.

2.6 forks the two Phase-2 inspection lanes (static analysis + dynamic detonation) so
they run concurrently and join on both-complete, instead of the current sequential
hand-off. It needs the dynamic RUN (2.3), not its telemetry capture (2.4), so it is
unaffected by the 2.4 gating.

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

### Queued behind 2.6 (authored, do NOT repoint yet)
Story 2.6's brief + prompt are BUILT and awaiting the stakeholder's live 4/4 DoD pass
(see `../story-2.6-LIVE-RUNBOOK.md`); 2.6 stays 🟡 (the one open Validation Debt
Register entry) until that recorded pass. The **next** story after 2.6 closes Phase 2 —
by RUNBOOK build tier — is the Floor & Harvest clean-ground pair **A.5** (correct the
plan drift, docs-only) then **A.6** (push the outstanding restore tags), which together
gate **2.4**. A.5's starter is already written for zero cold-start:
**[`../story-A.5-PROMPT.md`](../story-A.5-PROMPT.md)** (brief:
**[`../story-A.5-brief.md`](../story-A.5-brief.md)**). Do NOT move this on-deck pointer
to A.5 until 2.6's live pass clears the register and disarms the advancement gate.

### History note
Earlier on-deck starters (A.2 "validate 2.0", B.1 "harvest inventory", a premature 2.6
pointer, then the 2.0E validation pointer) were superseded as the plan evolved. This
folder holds only a single pointer to the current starter so it cannot drift into
pointing at already-completed, gated, or re-sequenced work; for authoritative status
and ordering, read `../../RUNBOOK.md`.
