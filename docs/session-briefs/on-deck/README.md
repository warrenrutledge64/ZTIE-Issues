# On deck (the current next-session starter)

> This folder points at the ONE prompt to paste to start the next working session.
> It is kept to a single current pointer so there is never an ambiguous or stale
> starter here. For authoritative status and ordering, read `../../RUNBOOK.md`.

## Next session: Story 4.2 — LIVE validation (dashboard JSON payload, RD-042)

**Story 4.2 (dashboard JSON payload, RD-042) is BUILT + offline-proven and 🟡 In Progress**
— `lambdas/hub_dashboard/` (the PURE, READ-only, on-demand dashboard orchestrator wired into
`ZtieHubTrackingStack`) is complete: 54 offline tests OK (8 jsonschema-live skips), ruff
clean, prettier clean, tsc adds no new error type, contract regen no-drift. It is on the
Validation Debt Register awaiting its recorded live pass, so **the advancement gate is armed**
— the ONLY next step is the LIVE validation, not a new feature story.

**The next session is the stakeholder's LIVE validation of 4.2. Paste this runbook:**

- **[`../story-4.2-LIVE-RUNBOOK.md`](../story-4.2-LIVE-RUNBOOK.md)** (the live validation runbook)

Its stakeholder-facing brief is **[`../story-4.2-brief.md`](../story-4.2-brief.md)**; the build
prompt (for reference) is **[`../story-4.2-PROMPT.md`](../story-4.2-PROMPT.md)**.

### What the 4.2 live run proves
Redeploy `ZtieHubTrackingStack` (Hub 641628980935) and INVOKE the `hub_dashboard` orchestrator
TWICE for a real intake: `view=intake` (the 4.1 read-model reused verbatim + a `threat` color
band + an `action` block for the human APPROVE/REJECT control) and `view=fleet` (recent-intake
rows via the `status-received_at-index` GSI + a `metrics` roll-up, with AMI/sensor/cost STUBBED
`not_wired`). Confirm: PURE (no model call, no `NOVA_MODEL_ID`), READ-only (role has only READ
`dynamodb:*`, nothing written to the item), the recommendation surfaced ADVISORY (`decision:
pending` + `advisory: true`), and NO effective-verdict key. On a pass the executor flips 4.2 ✅,
clears the register, and **4.3 unblocks** (dashboard render).

### After 4.2 goes ✅: Story 4.3 (dashboard render)
Once 4.2 is validated + closed, the next build is **Story 4.3 — Real-time dashboard render**
(tier 15) per the Phase-4 pipe ordering; its handoff is authored + staged:
- **[`../story-4.3-PROMPT.md`](../story-4.3-PROMPT.md)** · **[`../story-4.3-brief.md`](../story-4.3-brief.md)**

4.3 RENDERS 4.2's payload (dark theme, graduated severity/threat coloring, the fleet + per-intake
drill-in, the operator headline views, the human accept/reject control SURFACE — the ACTION is
4.4/4.6/4.7). Confirm the render tech + AWS-native hosting + the 4.2 read path (direct invoke vs.
the deferred GET API front) with the stakeholder at STEP 0.

### The 4.1 build prompt + brief (for reference)
- **[`../story-4.1-PROMPT.md`](../story-4.1-PROMPT.md)** · **[`../story-4.1-brief.md`](../story-4.1-brief.md)** · **[`../story-4.1-LIVE-RUNBOOK.md`](../story-4.1-LIVE-RUNBOOK.md)**

### G-1 carry-forward (compliance back-map — RD-014)
**G-1 is ✅ CLOSED (2026-09-12).** `docs/COMPLIANCE.md` is finished + ratified. New artifacts
still enter `Proposed` at authoring time (RD-014). Candidate mapping rows for RD-039 / RD-040 /
RD-041 / RD-042 are in `docs/COMPLIANCE.md` (Proposed); ratify on the next compliance review.

### Operational Debt: register is EMPTY (2026-09-12)
OD-001 / OD-002 / OD-003 are ALL closed (the RD-032 cost-remediation track is complete).
Design watch-item (not 4.2/4.3 scope): a retired Forensic bucket had an unwanted 365-day
COMPLIANCE Object Lock — do not add COMPLIANCE-mode lock to any bucket.

### Sequencing discipline (read this)
The RUNBOOK carries a binding **Sequencing rule** and METHODOLOGY §5.A.0 adds a
session-open **sequence check**: the story to START is the first OPEN item in the RUNBOOK
"Ready now" schedule, and working a *different* Ready story is a stakeholder-decided
reorder (recorded in WORK_LOG), never an executor self-selection or a quiet edit of the
"Default next action." `check_docs.py` CHECK J surfaces this mechanically as a
**non-blocking advisory** — while 4.2 is 🟡 the on-deck pointer stays on the 4.2 live
validation (the advancement gate blocks new feature work anyway); B.1 (tier 6, F&H) remains
the first-OPEN schedule item, sequenced after the Phase-4 pipe work per the reorder.

### Watch-items (carried from the 4.2 build 2026-09-13; apply to the 4.2 live run + the 4.3 session)
- **PURE + READ-only + on-demand (RD-042).** `hub_dashboard` makes NO model call (no Bedrock
  client/grant) and WRITES nothing (READ-only `get_item` + a bounded GSI `Query`; never a
  `Scan`). Verify the LIVE role + env (no `NOVA_MODEL_ID`; only READ `dynamodb:*`) AFTER deploy —
  never trust the green `UPDATE_COMPLETE`.
- **Reuses the 4.1 read-model.** The per-intake core (`intake.status`) is `status_model.build_status`
  reused verbatim (a VENDORED byte-identical copy of `hub_status/status_model.py` lives in
  `hub_dashboard/`, with a no-drift test — because each Lambda dir bundles as its own asset, so
  cross-dir import is impossible at runtime). If `status_model.py` ever changes in `hub_status`,
  re-copy it into `hub_dashboard` (the no-drift test will fail otherwise).
- **Threat tier is a DISPLAY band, never a verdict** — `threat_tier` bands the combined 3.3 score
  (raised by a high/critical 3.4 gap or a contradiction). The recommended_verdict stays ADVISORY
  (RD-040): surfaced + `decision: pending` + `advisory: true`, never enforced; no bare
  `verdict`/`safe`/`approved`/`forward`/`malicious`/`pass_fail`/`clean` key anywhere (recursive
  scan + schema-has-no-verdict-property test; `recommended_verdict` allow-listed).
- **Metrics honestly scoped.** The fleet list is capped (default 50, hard max 100) via the
  `status-received_at-index` GSI (no scan). `metrics` derives the tracking-native counts and STUBS
  AMI/sensor/cost as `not_wired` — their real data sources are a deferred follow-on.
- **`_NEW_WORK_STORY` fixture is now 4.3** (repointed in this 4.2 build PR). The 4.3 session
  repoints it off 4.3 to the next still-⬜ feature story IN THE SAME PR.
- **RD hygiene:** RD-042 is 4.2's. 4.3 authors a new RD only if it surfaces a genuine new
  sub-decision (next free number after RD-042 — VERIFY with `grep -oE "RD-0[0-9][0-9]"
  PROJECT_PLAN.md | sort -u | tail`); **CHECK E is literal** — add the new RD's plan-table row
  BEFORE referencing its number in any living doc.
- **CHECK I (broken-link):** author the next-story handoff + the LIVE-RUNBOOK BEFORE pointing this
  on-deck README at them. `pytest` is NOT installed offline — run
  `~/.pyenv/versions/3.12.13/bin/python3 -m unittest`.
- **Keep the docs consistent** — `check_docs.py` (CHECK A–J) runs on every status change; update
  the **RUNBOOK master table ONLY** for status and let README / this on-deck pointer / BUILD_ORDER
  POINT to it. Run `check_docs` AFTER committing status edits (CHECK B baseline is
  `git show HEAD:RUNBOOK.md`).

### History note
Earlier on-deck starters (A.2, B.1, 2.6, 2.5, C.3, 3.2, G-2, G-1, 3.4, 3.5, 4.1, 4.2) were superseded as
the plan progressed. This folder holds only a single pointer to the current starter so it
cannot drift into pointing at already-completed or re-sequenced work; for authoritative status
and ordering, read `../../RUNBOOK.md`.
