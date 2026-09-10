# On deck (the current next-session starter)

> This folder points at the ONE prompt to paste to start the next working session.
> It is kept to a single current pointer so there is never an ambiguous or stale
> starter here.

## Next session: Story 2.5 - Telemetry sanitization pipeline

Paste this file as the first message of the next session:

- **[`../story-2.5-PROMPT.md`](../story-2.5-PROMPT.md)**

Its stakeholder-facing brief is **[`../story-2.5-brief.md`](../story-2.5-brief.md)**.

### Why 2.5 is next
Story 2.4 (behavioral telemetry capture) closed ✅ on 2026-09-10 (validated live,
4/4 DoD, intake_id 16c2af41…). By the RUNBOOK's dependency build-tier order, Story
2.5 (tier 8) is now the next buildable pipeline story: it depends on 2.4's RAW
behavioral telemetry, which now exists. The Validation Debt Register is EMPTY (2.4
cleared on its own recorded live pass), so the advancement gate is open. 2.5 takes the
raw behavioral trace 2.4 captures (which includes SSM-agent + shell/coreutils host
noise) and SANITIZES it: entropy scrub → noise suppress → ≤25K-token truncation, so the
Phase-3 Nova Pro correlation gets a clean, bounded, token-budgeted view.

### Watch-items carried from 2.4's live run (read before building)
- **Deploy-gap (still applies):** 2.5 will touch the detonation lane / telemetry path
  that 2.6's orchestration direct-invokes. Its live validation MUST redeploy
  `ZtieDetonationStack` (and the Hub stack if the contract changes) BEFORE submitting.
- **Host noise is the whole point of 2.5.** 2.4's raw capture faithfully includes the
  SSM-agent + shell/coreutils syscalls (locale files, libc, `openat`/`newfstatat`), not
  just the artifact's own ops — that host noise is exactly what 2.5 must suppress. 2.4's
  top-50 crossed sample was dominated by host noise until the test artifact did an op
  MANY times; 2.5's noise-suppression should make the artifact's real behavior legible
  without needing a pathological test artifact.
- **AMI tooling gap:** the ubuntu-22.04 golden AMI ships `strace` (2.4 confirmed) but
  NOT `curl` (2.4's `curl` probe produced no `execve` / `connect`). If 2.5 (or a test)
  needs a network syscall to exercise, use a binary the AMI actually ships, or add the
  tool to the golden AMI (Image-Builder-owned, outside this repo).
- **Capture-completeness lesson (2.4 commit 71c3387):** trace the artifact DIRECTLY
  under `strace -ff` (per-PID files) + `sync` before reading — the earlier
  `sh -c 'if head|grep…'` wrapper form missed the artifact's own subtree. 2.5 must not
  regress this when it post-processes the trace.

### History note
Earlier on-deck starters (A.2, B.1, 2.6) were superseded as the plan progressed. This
folder holds only a single pointer to the current starter so it cannot drift into
pointing at already-completed or re-sequenced work; for authoritative status and
ordering, read `../../RUNBOOK.md`.
