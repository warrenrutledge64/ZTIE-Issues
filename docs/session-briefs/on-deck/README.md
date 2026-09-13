# On deck (the current next-session starter)

> This folder points at the ONE prompt to paste to start the next working session.
> It is kept to a single current pointer so there is never an ambiguous or stale
> starter here. For authoritative status and ordering, read `../../RUNBOOK.md`.

## Next session: the next Phase-4 pipe story (4.5 / 4.6 / 4.7) — confirm which with the stakeholder

**Story 4.3 (real-time dashboard render, RD-043) is validated live + closed ✅ (2026-09-13)** —
in the Hub (641628980935): `ZtieDashboardStack` deployed (private S3 + CloudFront OAC dark-theme
SPA + an IAM-auth API Gateway fronting the UNCHANGED 4.2 `hub_dashboard` Lambda). `GET /dashboard`
returned the fleet payload and `GET /status/{intake_id}` the per-intake payload (advisory
`recommended_verdict` + `decision: pending`, no effective-verdict key, 404 clean); the CloudFront
URL rendered the dark theme + graduated `threat_tier` coloring + the disabled Approve/Reject
control surface. A live proxy-integration defect (HTTP 502 "Malformed Lambda proxy response") was
fixed by switching to a NON-PROXY API Gateway integration (commit `8058301`, 4.2 Lambda unchanged)
and re-validated. **The register is EMPTY and the advancement gate is OPEN.**

### What's next (sequencing — confirm with the stakeholder at STEP 0)
Per the RUNBOOK "Ready now" schedule + the recorded 2026-09-13 stakeholder reorder
(`../../governance/WORK_LOG.md`, Phase-4 pipe work ahead of the F&H track), the next feature work
is the remaining **Phase-4 pipe stories**:
- **4.5** — per-execution PDF report (tiered: Executive / Security / Developer), dep 4.1, tier 14;
- **4.6** — ACCEPT → ZTIE pushes the hash-verified artifact Forensic → Pipeline-Sandbox (PDE handoff), dep 4.1, tier 14;
- **4.7** — REJECT → destroy artifact + detonation chamber in Forensic; INCONCLUSIVE → hold at the approval gate, dep 4.1, tier 14;
- then **4.4** — the interactive human accept/reject control (the ACTION the 4.3 dashboard surface will call), dep 4.3 + 4.7, tier 16, which **closes Phase 4**.

> **Sequencing-guard caution (learned 2026-09-13 — see [`../../governance/WORK_LOG.md`](../../governance/WORK_LOG.md) reconciliation + [`../../governance/SEQUENCING_METHOD.md`](../../governance/SEQUENCING_METHOD.md) §4a).** `check_docs` CHECK J compares the on-deck starter against the **first non-✅ bucket-A row by ROW ORDER (not by tier)** and names only that ONE row (here `B.1`). It therefore does **NOT** catch an intra-phase / same-track **tier inversion** among Ready siblings — e.g. `4.3` (tier 15) was worked ahead of `4.5/4.6/4.7` (tier 14) and CHECK J stayed silent about it. So the corrected course here is **strict first-OPEN tier order: 4.5 / 4.6 / 4.7 (tier 14) are next** (4.4 is tier 16 and blocked on 4.7). Working any Ready story ahead of a lower-tier Ready sibling — or the tier-16 enhancement `4.8` ahead of these — is a **priority decision that MUST be recorded in `WORK_LOG.md` BEFORE starting**, never an executor "next" assertion and never justified by CHECK J being silent. At STEP 0, after reading the first-OPEN row, also scan the OPEN Ready set for any lower-tier sibling you would be skipping.

**B.1** (F&H harvest inventory, tier 6) stays Ready and is sequenced after the Phase-4 pipe work
per the reorder — so `check_docs` CHECK J will flag the on-deck-vs-first-OPEN (B.1) mismatch as a
NON-BLOCKING advisory pointing at the logged reorder. **STEP 0 of the next session MUST confirm
with the stakeholder which Phase-4 story is next** (the 4.5 report, or the 4.6/4.7 enforcement
actions — 4.4 depends on 4.7 so it cannot be first), then author that story's brief + prompt
BEFORE pointing this on-deck README at them (CHECK I). The `_NEW_WORK_STORY` fixture is `4.4`.

### The 4.3 / 4.2 / 4.1 build prompts + briefs + LIVE-RUNBOOKs (for reference)
- **[`../story-4.3-PROMPT.md`](../story-4.3-PROMPT.md)** · **[`../story-4.3-brief.md`](../story-4.3-brief.md)** · **[`../story-4.3-LIVE-RUNBOOK.md`](../story-4.3-LIVE-RUNBOOK.md)**
- **[`../story-4.2-PROMPT.md`](../story-4.2-PROMPT.md)** · **[`../story-4.2-brief.md`](../story-4.2-brief.md)** · **[`../story-4.2-LIVE-RUNBOOK.md`](../story-4.2-LIVE-RUNBOOK.md)**
- **[`../story-4.1-PROMPT.md`](../story-4.1-PROMPT.md)** · **[`../story-4.1-brief.md`](../story-4.1-brief.md)** · **[`../story-4.1-LIVE-RUNBOOK.md`](../story-4.1-LIVE-RUNBOOK.md)**

### Carry-forward lessons from the 4.3 build + LIVE run (apply to the next Phase-4 story)
- **API Gateway ↔ direct-invoke Lambda contract (the 4.3 live defect).** The Phase-4 read Lambdas
  (4.1 `hub_status`, 4.2 `hub_dashboard`) are built for DIRECT invoke and return a BARE payload
  object (or a bare `{"error":{"code":N}}` envelope), NOT a `{statusCode, body}` proxy envelope. If
  you front one with API Gateway, do NOT use `proxy: true` (it 502s "Malformed Lambda proxy
  response"). Use a NON-PROXY `LambdaIntegration` with a VTL request template + a pass-through
  integration response, and map the error `code` to the HTTP status via `selectionPattern`. The
  offline `tsc` bar cannot catch this — it is an API-Gateway↔Lambda runtime contract, only caught
  live. 4.6 (which does real work / a push) and 4.5 (report generation) should confirm their own
  invoke/response contract live.
- **Redeploy caching.** After changing an API Gateway method integration, the first post-deploy
  request can still hit the OLD integration briefly; confirm with `aws apigateway get-integration
  ... --query type` (expect `AWS` for non-proxy) and re-fire a FRESH request before concluding a
  failure. Read a FRESH API-Gateway execution log (`API-Gateway-Execution-Logs_<apiId>/<stage>`),
  not a stale window.
- **Deploy-gap discipline.** Confirm the box is on the story branch before `cdk deploy`; AFTER
  deploy inspect the LIVE resource (integration type, env, role), never trust the green line.
- **Advisory + human-gated (RD-040).** 4.6/4.7 are the FIRST stages that ACT on a decision — but
  the effective decision is the HUMAN's selection (4.4), never the advisory `recommended_verdict`.
  Nothing routes/pushes/destroys on the recommendation.
- **Two accounts / two tabs.** The 4.6 ACCEPT push crosses Forensic → Pipeline-Sandbox (586917955591);
  4.7 REJECT destroys in Forensic. `aws sts get-caller-identity` before every block.
- Offline tooling: `~/.pyenv/versions/3.12.13/bin/python3 -m unittest` (pytest NOT installed);
  `~/.pyenv/versions/3.12.13/bin/ruff check`; `env -u NODE_OPTIONS npx tsc --noEmit` (confirm NO
  NEW error TYPE); `env -u NODE_OPTIONS npx prettier --write`. `gh pr create` is BROKEN — open PRs
  via `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`.

### G-1 carry-forward (compliance back-map — RD-014)
**G-1 is ✅ CLOSED (2026-09-12).** `docs/COMPLIANCE.md` is finished + ratified. New artifacts still
enter `Proposed` at authoring time (RD-014). Candidate mapping rows for RD-039 … RD-043 are in
`docs/COMPLIANCE.md` (Proposed); ratify on the next compliance review.

### Operational Debt: register is EMPTY (2026-09-12)
OD-001 / OD-002 / OD-003 are ALL closed. Design watch-item: a retired Forensic bucket had an
unwanted 365-day COMPLIANCE Object Lock — do not add COMPLIANCE-mode lock to any bucket.

### Sequencing discipline (read this)
The RUNBOOK carries a binding **Sequencing rule** and METHODOLOGY §5.A.0 adds a session-open
**sequence check**: the story to START is the first OPEN item in the RUNBOOK "Ready now" schedule,
and working a *different* Ready story is a stakeholder-decided reorder (recorded in WORK_LOG),
never an executor self-selection. `check_docs.py` CHECK J surfaces this mechanically as a
**non-blocking advisory** — B.1 (tier 6, F&H) remains the first-OPEN schedule item, sequenced
after the Phase-4 pipe work per the reorder, so the advisory points at the logged reorder.

### History note
Earlier on-deck starters (A.2, B.1, 2.6, 2.5, C.3, 3.2, G-2, G-1, 3.4, 3.5, 4.1, 4.2, 4.3) were
superseded as the plan progressed. This folder holds only a single pointer to the current starter
so it cannot drift into pointing at already-completed or re-sequenced work; for authoritative
status and ordering, read `../../RUNBOOK.md`.
