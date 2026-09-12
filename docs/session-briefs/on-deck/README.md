# On deck (the current next-session starter)

> This folder points at the ONE prompt to paste to start the next working session.
> It is kept to a single current pointer so there is never an ambiguous or stale
> starter here.

## Next session: Story C.3 — Shared Python seam + one parameterized generator

Paste this file as the first message of the next session:

- **[`../story-C.3-PROMPT.md`](../story-C.3-PROMPT.md)**

Its stakeholder-facing brief is **[`../story-C.3-brief.md`](../story-C.3-brief.md)**.

### Why C.3 is next
Story G-3 (hard-pause enforcement, RD-023) closed ✅ on 2026-09-12 — the one board
inconsistency (the advancement-gate checker itself un-validated) is retired, and the gate
machinery is now validated on its own `check_docs` + `test_check_docs` pass. Per the
RUNBOOK "Scheduling & readiness" buckets, the highest-value *Ready* item is now **C.3**:
the one backlog item whose cost **rises with every pipe story**. On `main` the `awsio.py`
seam is hand-copied **6×** (preprocessor / static_scan / detonation / collector /
hub_normalize / ztie_restore) and there are **10 bespoke contract generators**
(`scripts/gen_*_contract.py`). 3.1 added the 6th hand-copy. C.3 is a behaviour-preserving
refactor: ONE shared seam/gate module + ONE parameterized generator (byte-identical,
hash-matched output) — zero functional change, proven by identical contract hashes + a
green offline proof bar. Its only dependency (A.4) is ✅ and the Validation Debt Register
is empty.

> **Alternative:** if the stakeholder prefers to keep moving on the pipe track, **3.2
> (Nova Pro correlation)** is the other Ready item (its brief + prompt exist). C.3 is
> recommended first because its cost compounds on every subsequent pipe story.

### Watch-items carried from the G-3-close session (read before building)
- **C.3 is a REFACTOR — behaviour-preserving.** Success = same behaviour + same contract
  bytes + less duplication. Prove no-drift with contract **hashes** (regenerate every
  schema with the one new generator and match the committed hash), keep the two-layer
  conformance tests green, and change no handler behaviour. If one contract byte moves, it
  failed.
- **Bundling is the top runtime risk (deploy-gap sibling).** The shared module must be in
  every Lambda's deploy bundle and importable by `scripts/ztie_restore`; a module that
  passes offline but isn't bundled throws `ModuleNotFoundError` at runtime. Decide the
  shared location against how the CDK stacks actually bundle each Lambda; verify the LIVE
  import if a no-op redeploy is used.
- **Don't conflate the two C.3 scopes.** This C.3 is the Python seam + generator collapse
  (dep A.4 only), NOT the CDK L3 archive chain (B.1→C.1→C.2→C.4→C.5).
- **Do NOT touch `_NEW_WORK_STORY`** — it pins the next ⬜ *pipe* story (3.2); a C.3 (F&H)
  close does not move it. And `check_docs` timing is unchanged: run it only AFTER
  committing a status/register edit; read the `test_check_docs` SUITE line (`OK`), not the
  fixture-print `check_docs: FAIL …` lines (suite is OK / 8 tests — assert on `OK`, not a
  fixed count).

### History note
Earlier on-deck starters (A.2, B.1, 2.6, 2.5) were superseded as the plan progressed. This
folder holds only a single pointer to the current starter so it cannot drift into pointing
at already-completed or re-sequenced work; for authoritative status and ordering, read
`../../RUNBOOK.md`.
