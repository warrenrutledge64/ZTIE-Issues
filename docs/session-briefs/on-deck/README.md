# On deck (the current next-session starter)

> This folder points at the ONE prompt to paste to start the next working session.
> It is kept to a single current pointer so there is never an ambiguous or stale
> starter here.

## Next session: Story 3.2 — Nova Pro correlation engine

Paste this file as the first message of the next session:

- **[`../story-3.2-PROMPT.md`](../story-3.2-PROMPT.md)**

Its stakeholder-facing brief is **[`../story-3.2-brief.md`](../story-3.2-brief.md)**.

### Why 3.2 is next
Story C.3 (shared contract generator + Hub-gate seam, RD-034) closed ✅ on 2026-09-12 —
the behaviour-preserving refactor that collapsed the 10 duplicated contract generators
into one shared writer and the 8 duplicated Hub-gate kind trios into one data-driven
registry (byte-identical, proven offline; `awsio` kept per-lane by design). With G-3 and
C.3 both closed, the highest-value *Ready* item per the RUNBOOK "Scheduling & readiness"
buckets is **3.2** — the next pipe feature (Nova Pro correlation). Its dependencies (3.1
✅ + 2.5 ✅) are met and the Validation Debt Register is empty, so the advancement gate is
OPEN. 3.2 hands the ONE normalized combined-event record (3.1, RD-033) for an artifact to
Amazon Nova Pro (RD-003), correlates static misconfigurations against dynamic behavioral
indicators, and records a bounded, verdict-free correlation result with exponential-
backoff retry.

### Watch-items carried from the C.3 session (read before building — they're in the 3.2 prompt too)
- **Contract-generation workflow CHANGED.** Add 3.2's correlation contract as a NEW
  `scripts/gen_<name>_contract.py` that declares `SCHEMA` + a module-level `OUT_PATHS`
  and delegates `main()` to `contract_writer.write_contract`, then register it in
  `gen_contracts.py`'s `CONTRACT_MODULES`. Prove no-drift with `git diff -- schemas
  lambdas`. Do NOT re-introduce a bespoke writer loop.
- **Hub gate is now a `_KINDS` registry.** A new SQS-crossing kind = one `_KindSpec`
  entry + a thin delegate trio. But a Hub-side 3.2 correlation (like 3.1's combined
  event) is a Hub-INTERNAL derivation, NOT a new crossing — likely no `_KINDS` entry at
  all; confirm placement contract-first.
- **`awsio` stays per-lane by design (RD-034).** Don't try to share it — bundling makes
  a shared module `ModuleNotFoundError` at runtime.
- **Next free RD is RD-035** (RD-034 is C.3) — but re-verify with the grep.
- **Offline proof bar unchanged**; `hub_ingest/test_handler.py` still can't import boto3
  offline (pre-existing, not a regression).

### History note
Earlier on-deck starters (A.2, B.1, 2.6, 2.5, C.3) were superseded as the plan
progressed. This folder holds only a single pointer to the current starter so it cannot
drift into pointing at already-completed or re-sequenced work; for authoritative status
and ordering, read `../../RUNBOOK.md`.
