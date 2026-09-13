# On deck (the current next-session starter)

> This folder points at the ONE prompt to paste to start the next working session.
> It is kept to a single current pointer so there is never an ambiguous or stale
> starter here. For authoritative status and ordering, read `../../RUNBOOK.md`.

## Next session: Story 4.6 — LIVE validation (built; the advancement gate is ARMED on it)

**Story 4.6 (ACCEPT→push, RD-047) is BUILT + offline-proven on `feature/story-4.6` and is 🟡 —
its recorded LIVE pass is the single next action.** The Validation Debt Register has **1 open entry
(4.6)** and the advancement gate is **ARMED**: no NEW feature story may begin until 4.6 clears by
its own live pass. This is NOT a new feature story — it is the LIVE validation of already-built code.
Paste this to run it:

- **[`../story-4.6-LIVE-RUNBOOK.md`](../story-4.6-LIVE-RUNBOOK.md)** (the stakeholder live-validation runbook)

Its build prompt is **[`../story-4.6-PROMPT.md`](../story-4.6-PROMPT.md)** and its stakeholder-facing
brief is **[`../story-4.6-brief.md`](../story-4.6-brief.md)**.

### What 4.6 is
4.6 is the Phase-4 **ACCEPT enforcement action**: on a RECORDED human ACCEPT
(`human_decision == "accepted"` on the Hub tracking item — NEVER the advisory verdict, RD-040), a
Forensic-side `pde_handoff` Lambda reads the raw artifact from Forensic S3, **verifies its sha256
against the Hub record** (SI-7), and PUSHES it **cross-account to a Pipeline-Sandbox landing bucket
(586917955591)** — one-directional, least-privilege, **fail-closed** (no accept / hash mismatch →
NO push). It stands up the Sandbox landing bucket (`ZtieSandboxLandingStack`, the first ZTIE stack
in the Sandbox account) + the Forensic pusher stack (`ZtiePdeHandoffStack`) + a bounded verdict-free
handoff OUTCOME crossing (the **10th** RD-013 envelope kind, `handoff`). **The artifact goes
Forensic→Sandbox directly, never through the Hub (RD-013); only the outcome crosses; ZTIE never
re-executes the artifact.** RD-047 captures the decision.

> **4.6's LIVE validation is the next action** (per the covenant — a story stays 🟡 until a
> recorded live pass). The register is ARMED, so no NEW feature story starts until 4.6 clears.
> The live run spans **THREE accounts** (Forensic pusher + artifact / Pipeline-Sandbox landing /
> Hub decision + outcome) — confirm creds for the Pipeline-Sandbox account (586917955591), the
> first ZTIE story to use it. On a recorded pass 4.6 flips ✅ and the register empties.

### After 4.6 — the rest of Phase 4
On 4.6 ✅, per the RUNBOOK "Ready now" schedule + the 2026-09-13 reorder (Phase-4 pipe work ahead of
the F&H track): **4.7** (REJECT→destroy, tier 14, the tied sibling) is the next first-OPEN pipe
story, then **4.4** (the human accept/reject control, tier 16, dep 4.3 + 4.7) which **closes Phase
4**. The 4.7 handoff is authored at **[`../story-4.7-brief.md`](../story-4.7-brief.md)** +
**[`../story-4.7-PROMPT.md`](../story-4.7-PROMPT.md)**. The tier-15 **4.9** (report-enrichment,
RD-046) and the tier-16 **4.8** (dashboard browser auth, RD-044) are enhancements after the tier-14
pipe work. **B.1** (F&H, tier 6) stays Ready sequenced after the Phase-4 pipe work. The
`_NEW_WORK_STORY` fixture is `4.4`.

> **Sequencing-guard caution (learned 2026-09-13 — see [`../../governance/WORK_LOG.md`](../../governance/WORK_LOG.md) + [`../../governance/SEQUENCING_METHOD.md`](../../governance/SEQUENCING_METHOD.md) §4a).** `check_docs` CHECK J compares the on-deck starter against the **first non-✅ bucket-A row by ROW ORDER (not tier)** and names only that ONE row. It does NOT catch an intra-phase / same-track **tier inversion** among Ready siblings. So the by-the-book next pick after 4.5 closes is **strict first-OPEN tier order** (4.6/4.7 at tier 14 before the tier-16 4.4/4.8 and the tier-15 4.9); working any Ready story ahead of a lower-tier Ready sibling — or the tier-16 enhancements ahead of these — is a **priority decision that MUST be recorded in `WORK_LOG.md` BEFORE starting**, never an executor "next" assertion.

### The 4.3 / 4.2 / 4.1 build prompts + briefs + LIVE-RUNBOOKs (for reference)
- **[`../story-4.3-PROMPT.md`](../story-4.3-PROMPT.md)** · **[`../story-4.3-brief.md`](../story-4.3-brief.md)** · **[`../story-4.3-LIVE-RUNBOOK.md`](../story-4.3-LIVE-RUNBOOK.md)**
- **[`../story-4.2-PROMPT.md`](../story-4.2-PROMPT.md)** · **[`../story-4.2-brief.md`](../story-4.2-brief.md)** · **[`../story-4.2-LIVE-RUNBOOK.md`](../story-4.2-LIVE-RUNBOOK.md)**
- **[`../story-4.1-PROMPT.md`](../story-4.1-PROMPT.md)** · **[`../story-4.1-brief.md`](../story-4.1-brief.md)** · **[`../story-4.1-LIVE-RUNBOOK.md`](../story-4.1-LIVE-RUNBOOK.md)**

### Carry-forward lessons from the 4.5 build + LIVE validation (apply to the next story)
- **PURE + READ-only + on-demand (RD-045).** `hub_report` makes NO model call (no Bedrock
  client/grant) and WRITES nothing (READ-only `get_item`; no query/scan — per-intake). Verify the
  LIVE role + env AFTER deploy — never trust the green `UPDATE_COMPLETE`.
- **Reuses the 4.1 read-model.** The Executive core is `status_model.build_status` reused verbatim
  (a VENDORED byte-identical copy of `hub_status/status_model.py` lives in `hub_report/`, with a
  no-drift sha256 test — each Lambda dir bundles as its own asset, so cross-dir import is
  impossible at runtime). If `hub_status/status_model.py` ever changes, re-copy it into
  `hub_report/` or the no-drift test fails.
- **Honest boundary (RD-013).** MITRE/Sigma/file-line render as `not_carried_on_hub` — NOT an
  error, NOT fabricated. The enrichment (widen the crossing) is 4.9 (RD-046), its own story with
  its own live validation of the crossing — do NOT widen RD-013 as a reporting side effect.
- **Advisory + human-gated (RD-040).** The recommendation is surfaced advisory (`decision:
  pending`); no bare `verdict`/`safe`/`approved`/`forward`/`malicious`/`pass_fail`/`clean` key.
- **DynamoDB Number → Decimal (the 4.5 live defect, PR #137).** `boto3.resource(...).get_item`
  deserializes a DynamoDB Number to a Python **`Decimal`**, NOT `int`/`float`. Any handler that
  reads a numeric field off a tracking item and guards it with a strict `isinstance(int)` will
  silently DROP the value (4.5's `rank` guard rejected every remediation → `remediations: 0`).
  COERCE numerics (`int(value)` / `float(value)` in a try, reject bool) like `status_model`'s
  `_coerce_score`/`_coerce_count` — never a strict isinstance check. Offline tests that build
  fixtures with plain `int`/`float` will NOT catch this; add a `Decimal` regression case. 4.6/4.7
  read the item too — apply the same coercion to any numeric they consume.
- **HTML render, not a native PDF.** "PDF for humans" = self-contained HTML → browser print-to-PDF
  (the build sandbox has no package registry, so a native PDF dep isn't installable/offline-
  testable). Every derived value is HTML-escaped (no injection).
- **API-Gateway ↔ direct-invoke contract (carried from 4.3).** If a GET `/report/{intake_id}`
  front is ever added, use a NON-PROXY integration (the Lambda returns a bare object, not a proxy
  envelope) — a `proxy: true` integration 502s. Not in 4.5's scope (direct invoke now).
- Offline tooling: `~/.pyenv/versions/3.12.13/bin/python3 -m unittest` (pytest NOT installed);
  `~/.pyenv/versions/3.12.13/bin/ruff check`; `env -u NODE_OPTIONS npx tsc --noEmit` (confirm NO
  NEW error TYPE); `env -u NODE_OPTIONS npx prettier --write`. `gh pr create` is BROKEN — open PRs
  via `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`.

### G-1 carry-forward (compliance back-map — RD-014)
**G-1 is ✅ CLOSED (2026-09-12).** `docs/COMPLIANCE.md` is finished + ratified. New artifacts still
enter `Proposed` at authoring time (RD-014). Candidate mapping rows for RD-039 … RD-046 are in
`docs/COMPLIANCE.md` (Proposed); ratify on the next compliance review.

### Operational Debt: register is EMPTY (2026-09-12)
OD-001 / OD-002 / OD-003 are ALL closed. Design watch-item: a retired Forensic bucket had an
unwanted 365-day COMPLIANCE Object Lock — do not add COMPLIANCE-mode lock to any bucket.

### Sequencing discipline (read this)
The RUNBOOK carries a binding **Sequencing rule** and METHODOLOGY §5.A.0 adds a session-open
**sequence check**: the story to START is the first OPEN item in the RUNBOOK "Ready now" schedule
(strict tier order), and working a *different* Ready story is a stakeholder-decided reorder
(recorded in WORK_LOG), never an executor self-selection. `check_docs.py` CHECK J surfaces the
on-deck-vs-first-OPEN mismatch as a **non-blocking advisory** — it is reconciled by the recorded
2026-09-13 reorder (Phase-4 pipe work ahead of the F&H track B.1).

### History note
Earlier on-deck starters (A.2, B.1, 2.6, 2.5, C.3, 3.2, G-2, G-1, 3.4, 3.5, 4.1, 4.2, 4.3, 4.5)
were superseded as the plan progressed. This folder holds only a single pointer to the current
starter so it cannot drift into pointing at already-completed or re-sequenced work; for
authoritative status and ordering, read `../../RUNBOOK.md`.
