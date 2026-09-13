# On deck (the current next-session starter)

> This folder points at the ONE prompt to paste to start the next working session.
> It is kept to a single current pointer so there is never an ambiguous or stale
> starter here. For authoritative status and ordering, read `../../RUNBOOK.md`.

## Next session: Story 4.3 — LIVE validation of the real-time dashboard render

**Story 4.3 (real-time dashboard render, RD-043) is BUILT + offline-proven and 🟡 In
Progress (2026-09-13).** It is in the Validation Debt Register, so the advancement gate is
**ARMED** — the ONLY next action is 4.3's recorded LIVE validation (no new feature story may
begin until 4.3 clears). Paste the LIVE-RUNBOOK to run the stakeholder validation:

- **[`../story-4.3-LIVE-RUNBOOK.md`](../story-4.3-LIVE-RUNBOOK.md)** (deploy + validate 4.3 live)

Its build prompt is **[`../story-4.3-PROMPT.md`](../story-4.3-PROMPT.md)** and its
stakeholder-facing brief is **[`../story-4.3-brief.md`](../story-4.3-brief.md)**.

### What 4.3 is (as built)
4.3 RENDERS 4.2's `dashboard.contract.v1` payload as the real-time dashboard: a build-step-free
static SPA (vanilla HTML/CSS/JS, **dark theme**, graduated `threat_tier` color-coding
low/medium/high/critical at a glance) served from a private S3 bucket behind CloudFront (OAC),
plus an **IAM-auth API Gateway** front (`GET /dashboard` = fleet, `GET /status/{intake_id}` =
per-intake) that proxies to the **UNCHANGED Story 4.2 `hub_dashboard` Lambda** (referenced by
ARN — the GET front 4.2 deferred; no 4.2 handler change). It renders the fleet/list, the
per-intake detail drill-in (the 4.1 read-model + the `threat` band + risk-score context bars),
the operator headline cards (live activity + restore-point health as a first-class element; a
port ⇄ MITRE placeholder pending its deferred data source — PROJECT_PLAN §7), and the human
APPROVE/REJECT control SURFACE. **Render only** — no re-derivation, no model call, no write; the
`recommended_verdict` stays **advisory + human-gated** (a page-level advisory banner + a
per-intake note; the APPROVE/REJECT buttons are present but **DISABLED** — the ACTION + routing
is 4.4/4.6/4.7). All derived values are escaped (`textContent`, never `innerHTML` — no stored
XSS). `not_wired` health blocks render as "not available yet". Tenant-aware (RD-028):
per-SUBSCRIBER, org-shared, `subscriber_id` on every read, no per-user filtering. AWS-native
hosting; ServiceNow OUT OF SCOPE. New decision registered: **RD-043**.

### What the live run must confirm (Definition of Done)
Deploy `ZtieDashboardStack` in the Hub (641628980935) with `-c dashboardFunctionArn=<the 4.2
`DashboardOrchestratorName` function ARN>`; for a real intake, confirm the dashboard renders the
fleet/list colored by `threat_tier`, the per-intake drill-in, the operator headline views, and
the APPROVE/REJECT control surface (advisory recommendation + pending decision) — dark theme,
correct severity coloring; `not_wired` blocks show "not available yet"; the render is READ-only
(GET) and presents the recommendation as advisory (buttons disabled). Drive the IAM-auth
endpoints via `awscurl` (SigV4). On the recorded pass, 4.3 flips ✅ and the register empties.

### After 4.3 is validated + closed — the next feature story
Per the RUNBOOK "Ready now" schedule + the recorded reorder
(`../../governance/WORK_LOG.md`, 2026-09-13, Phase-4 pipe work ahead of the F&H track), the next
Phase-4 pipe work becomes schedulable — **4.5 (per-execution report) / 4.6 (ACCEPT→PDE) / 4.7
(REJECT→destroy)** (all tier 14, Ready on 4.1), then **4.4** (the human accept/reject ACTION,
tier 16, which closes Phase 4 on 4.3 + 4.7). **B.1** (F&H harvest inventory, tier 6) stays Ready
and is sequenced after the Phase-4 pipe work per the reorder. The `_NEW_WORK_STORY` fixture is
`4.4` (a still-⬜ feature story, used to prove the advancement gate fires).

### The 4.2 / 4.1 build prompts + briefs + LIVE-RUNBOOKs (for reference)
- **[`../story-4.2-PROMPT.md`](../story-4.2-PROMPT.md)** · **[`../story-4.2-brief.md`](../story-4.2-brief.md)** · **[`../story-4.2-LIVE-RUNBOOK.md`](../story-4.2-LIVE-RUNBOOK.md)**
- **[`../story-4.1-PROMPT.md`](../story-4.1-PROMPT.md)** · **[`../story-4.1-brief.md`](../story-4.1-brief.md)** · **[`../story-4.1-LIVE-RUNBOOK.md`](../story-4.1-LIVE-RUNBOOK.md)**

### G-1 carry-forward (compliance back-map — RD-014)
**G-1 is ✅ CLOSED (2026-09-12).** `docs/COMPLIANCE.md` is finished + ratified. New artifacts
still enter `Proposed` at authoring time (RD-014). Candidate mapping rows for RD-039 / RD-040 /
RD-041 / RD-042 / RD-043 are in `docs/COMPLIANCE.md` (Proposed); ratify on the next compliance
review.

### Operational Debt: register is EMPTY (2026-09-12)
OD-001 / OD-002 / OD-003 are ALL closed (the RD-032 cost-remediation track is complete).
Design watch-item (not 4.3 scope): a retired Forensic bucket had an unwanted 365-day
COMPLIANCE Object Lock — do not add COMPLIANCE-mode lock to any bucket.

### Sequencing discipline (read this)
The RUNBOOK carries a binding **Sequencing rule** and METHODOLOGY §5.A.0 adds a
session-open **sequence check**: the story to START is the first OPEN item in the RUNBOOK
"Ready now" schedule, and working a *different* Ready story is a stakeholder-decided
reorder (recorded in WORK_LOG), never an executor self-selection or a quiet edit of the
"Default next action." `check_docs.py` CHECK J surfaces this mechanically as a
**non-blocking advisory** — while 4.3 is 🟡 the on-deck pointer stays on the 4.3 live
validation (the advancement gate blocks new feature work anyway); B.1 (tier 6, F&H) remains
the first-OPEN schedule item, sequenced after the Phase-4 pipe work per the reorder, so the
CHECK J advisory (on-deck 4.3 vs first-OPEN B.1) points HERE / at the logged reorder.

### Watch-items (carried from the 4.3 build 2026-09-13; apply to the 4.3 live run + the next session)
- **RENDER ONLY (RD-043).** 4.3 consumes 4.2's `dashboard.contract.v1`; it re-derives nothing,
  makes no model call, and never writes. The read API PROXIES to the UNCHANGED 4.2 Lambda — do
  NOT modify `hub_dashboard`; if a change there is ever needed, STOP (blast radius).
- **Deploy-gap discipline.** `ZtieDashboardStack` is instantiated ONLY when `-c
  dashboardFunctionArn=<...>` is supplied (build the ARN from the Hub output
  `DashboardOrchestratorName` + `arn:aws:lambda:us-east-1:641628980935:function:<name>`). Confirm
  the box is on `feature/story-4.3` before `cdk deploy`; AFTER deploy verify the LIVE resources
  (the API Gateway endpoints resolve, the CloudFront URL serves the SPA) — never trust the green
  `UPDATE_COMPLETE` alone.
- **Advisory + human-gated (RD-040).** The recommendation is surfaced ADVISORY (banner + note +
  `decision: pending`); the APPROVE/REJECT buttons are a DISABLED surface (the action is 4.4/4.7).
  No bare `verdict`/`safe`/`approved`/`forward`/`malicious`/`pass_fail`/`clean` value is read off
  the payload (the advisory field is `recommended_verdict`).
- **No stored XSS (RD-013).** The client inserts derived values via `textContent`/`createTextNode`
  only — never `innerHTML` of a raw value.
- **Auth.** The API is IAM/SigV4 (same posture as the intake API). A browser Cognito login is a
  DEFERRED follow-on — drive the live validation via `awscurl` (SigV4). It is in the **Hub**
  account (the intake API is in Forensic); `aws sts get-caller-identity` before each block.
- **`_NEW_WORK_STORY` fixture is `4.4`** (a still-⬜ feature story). The NEXT feature-story session
  repoints it off its own story IN THE SAME PR.
- **RD hygiene:** RD-043 is 4.3's; its plan-table row is added. **CHECK E is literal** — never
  write a not-yet-defined RD number in a living doc.
- **CHECK I (broken-link):** author any next-story handoff + LIVE-RUNBOOK BEFORE pointing this
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
