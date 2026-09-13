# On deck (the current next-session starter)

> This folder points at the ONE prompt to paste to start the next working session.
> It is kept to a single current pointer so there is never an ambiguous or stale
> starter here. For authoritative status and ordering, read `../../RUNBOOK.md`.

## Next session: Story 4.5 — LIVE validation of the per-execution report

**Story 4.5 (per-execution tiered report, RD-045) is BUILT + offline-proven and 🟡 In
Progress (2026-09-13).** It is in the Validation Debt Register, so the advancement gate is
**ARMED** — the ONLY next action is 4.5's recorded LIVE validation (no new feature story may
begin until 4.5 clears). Paste the LIVE-RUNBOOK to run the stakeholder validation:

- **[`../story-4.5-LIVE-RUNBOOK.md`](../story-4.5-LIVE-RUNBOOK.md)** (redeploy + validate 4.5 live)

Its stakeholder-facing brief/spec is **[`../../STORY_DETAIL.md#story-4-5`](../../STORY_DETAIL.md)**.

### What 4.5 is (as built)
4.5 is the Phase-4 PER-EXECUTION REPORT — the human-readable, audience-tiered counterpart to
the dashboard. A NEW PURE, READ-only Hub Lambda `lambdas/hub_report/` (in `ZtieHubTrackingStack`,
construct `ReportOrchestrator`, NO stream source, `grantReadData` only, NO Bedrock) assembles, on
demand by `intake_id`, `report.contract.v1` in three tiers + a self-contained inline-CSS **HTML**
render (print-to-PDF — **Option A**, chosen over a native PDF lib because the build sandbox has no
package registry): **Executive** (risk score + one-paragraph advisory verdict, reusing the 4.1
read-model), **Security** (correlated findings / behavioral chains + severity roll-ups + gaps,
from 3.2 correlation + 3.4 assessment), **Developer** (prioritized remediations + candidate false
positives + static↔dynamic correlation, from 3.4). **Honest boundary (RD-013):** MITRE ATT&CK
IDs / Sigma rules / exact file-line are `not_carried_on_hub` placeholders (raw stays in Forensic)
— widening the crossing to carry them is the separate tracked story **4.9 (RD-046)**. **Advisory
(RD-040):** the Executive tier surfaces `recommended_verdict` + `decision: pending` + `advisory:
true`; no bare effective-verdict key; the HTML escapes every derived value.

### What the live run must confirm (Definition of Done)
Redeploy `ZtieHubTrackingStack` (ships the new `hub_report` Lambda); invoke it for a real intake
(`format: both`); confirm the three tiers populate (Executive score + advisory verdict; Security
findings/gaps + `not_carried_on_hub` MITRE/Sigma; Developer ranked remediations +
`not_carried_on_hub` file-line), the HTML render is present, PURE + READ-only on the live role/env
(no `NOVA_MODEL_ID`, only READ `dynamodb:*`, nothing written), no effective-verdict key, and a
non-existent intake returns a clean 404. On the recorded pass, 4.5 flips ✅ and the register empties.

### After 4.5 is validated + closed — the next feature story
Per the RUNBOOK "Ready now" schedule (strict first-OPEN tier order) + the recorded 2026-09-13
reorder (Phase-4 pipe work ahead of the F&H track), the next Phase-4 pipe work is **4.6**
(ACCEPT→push to PDE) and **4.7** (REJECT→destroy), both tier 14, then **4.4** (the human
accept/reject ACTION, tier 16) which **closes Phase 4** on 4.3 + 4.7. **B.1** (F&H, tier 6) stays
Ready sequenced after the Phase-4 pipe work. **4.9** (report-enrichment, tier 15, RD-046) is
Blocked on 4.5 and **4.8** (dashboard browser auth, tier 16, RD-044) is a lower-priority
enhancement — both off the closure path. The `_NEW_WORK_STORY` fixture is `4.4`.

> **Sequencing-guard caution (learned 2026-09-13 — see [`../../governance/WORK_LOG.md`](../../governance/WORK_LOG.md) + [`../../governance/SEQUENCING_METHOD.md`](../../governance/SEQUENCING_METHOD.md) §4a).** `check_docs` CHECK J compares the on-deck starter against the **first non-✅ bucket-A row by ROW ORDER (not tier)** and names only that ONE row. It does NOT catch an intra-phase / same-track **tier inversion** among Ready siblings. So the by-the-book next pick after 4.5 closes is **strict first-OPEN tier order** (4.6/4.7 at tier 14 before the tier-16 4.4/4.8 and the tier-15 4.9); working any Ready story ahead of a lower-tier Ready sibling — or the tier-16 enhancements ahead of these — is a **priority decision that MUST be recorded in `WORK_LOG.md` BEFORE starting**, never an executor "next" assertion.

### The 4.3 / 4.2 / 4.1 build prompts + briefs + LIVE-RUNBOOKs (for reference)
- **[`../story-4.3-PROMPT.md`](../story-4.3-PROMPT.md)** · **[`../story-4.3-brief.md`](../story-4.3-brief.md)** · **[`../story-4.3-LIVE-RUNBOOK.md`](../story-4.3-LIVE-RUNBOOK.md)**
- **[`../story-4.2-PROMPT.md`](../story-4.2-PROMPT.md)** · **[`../story-4.2-brief.md`](../story-4.2-brief.md)** · **[`../story-4.2-LIVE-RUNBOOK.md`](../story-4.2-LIVE-RUNBOOK.md)**
- **[`../story-4.1-PROMPT.md`](../story-4.1-PROMPT.md)** · **[`../story-4.1-brief.md`](../story-4.1-brief.md)** · **[`../story-4.1-LIVE-RUNBOOK.md`](../story-4.1-LIVE-RUNBOOK.md)**

### Carry-forward lessons from the 4.5 build (apply to the 4.5 live run + the next story)
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
on-deck-vs-first-OPEN mismatch as a **non-blocking advisory** — while 4.5 is 🟡 the on-deck pointer
stays on the 4.5 live validation (the advancement gate blocks new feature work anyway).

### History note
Earlier on-deck starters (A.2, B.1, 2.6, 2.5, C.3, 3.2, G-2, G-1, 3.4, 3.5, 4.1, 4.2, 4.3, 4.5)
were superseded as the plan progressed. This folder holds only a single pointer to the current
starter so it cannot drift into pointing at already-completed or re-sequenced work; for
authoritative status and ordering, read `../../RUNBOOK.md`.
