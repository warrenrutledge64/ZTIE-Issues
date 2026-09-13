# Session Prompt — Story 4.3 (real-time dashboard render) — executor-facing

> Ready-to-paste session prompt, reconciled against the canonical
> `docs/SESSION_PROMPT_TEMPLATE.md` (now the corrected template). Its
> stakeholder-facing brief is
> `docs/session-briefs/story-4.3-brief.md`. Paste the block below as the first
> message of the new session.

```
You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project. Read
this fully before acting. Do NOT change anything until you have (a) READ the plan +
runbook + methodology + this story's brief (`session-briefs/story-4.3-brief.md`), (b)
re-established true state (STEP 0), and (c) confirmed the validation-gate state this
story depends on (see STEP 0).

# PROJECT IDENTITY
ZTIE is a four-phase, AWS-native security pipeline that fully inspects every untrusted
artifact BEFORE it may reach the PDE — the zero-trust ingress gate for the software
supply chain. Three accounts: Pipeline-Hub (641628980935) = brains/control plane +
durable tracking record + Bedrock; Forensic (360999005254) = self-contained blast zone
(intake, lanes, ephemeral detonation host); Pipeline-Sandbox (586917955591) = the
ZTIE→PDE handoff landing zone. Phase 4 (Reporting & Handoff) is under way: 4.1 (status
read-model) + 4.2 (dashboard JSON payload) are ✅; 4.3 is the render. Validation
covenant, one line: nothing is ✅ until a recorded live pass of the final code.

# WHERE THIS STORY SITS  (build tier + position — state it explicitly)
Story 4.3 is build tier 15. This session ADVANCES from tier 14 to tier 15 — the
tier-14 work it depends on (4.2, the dashboard JSON payload) has closed ✅, so a NEW
dependency layer opens. This is a tier move WITHIN Phase 4 (NOT a phase transition —
Phase 4 opened at 4.1). A tier advance is exactly when you must re-confirm the ENTIRE
new dependency set is ✅ (4.2 AND its inputs 4.1 + 3.1-3.5) and the Validation Debt
Register is empty — not just glance at 4.2. STEP 0 must catch it if any prior tier is
not closed.

SEQUENCING — DEFER TO THE RUNBOOK, DO NOT ASSERT "NEXT" AS FACT. This prompt names a
build tier + dependencies; it does NOT declare 4.3 is "the next build" on its own
authority. The story to START is whatever is the first OPEN item in the RUNBOOK
"Ready now" schedule, in tier order (METHODOLOGY §5.A.0) — the RUNBOOK is the source of
truth, verified live in STEP 0. Note: 4.3 (tier 15) is NOT the lowest-tier open Ready
item — B.1 (tier 6, F&H, doc-only) and 4.5/4.6/4.7 (tier 14) are all lower-tier and
Ready. So 4.3 is build tier 15, dep 4.2; per the RUNBOOK Ready-now schedule it is
sequenced ahead of those earlier-tier items ONLY by the stakeholder reorder recorded in
`docs/governance/WORK_LOG.md` (2026-09-13: Phase-4 pipe work ahead of the F&H track).
STEP 0 MUST re-confirm that reorder still stands; if it no longer does, STOP and work
the actual first OPEN Ready-now item instead. Expect `check_docs` CHECK J to flag the
on-deck-vs-first-OPEN (B.1) mismatch as a NON-BLOCKING advisory pointing at the logged
reorder — reconcile it, do not ignore it.

# WHAT THIS STORY IS  (name its nature + its role in the gate)
NEW FEATURE story — the Phase-4 RENDER (the presentation layer over 4.2's dashboard
JSON payload). It may begin ONLY if its Depends-on are all ✅ AND the Validation Debt
Register is empty (the advancement gate). The single sentence that prevents the most
likely category error: 4.3 RENDERS already-derived data — it does NOT re-run any
Phase-3 assessment, does NOT make a model call, and does NOT itself enforce anything
(the human accept/reject ACTION + routing is 4.4/4.6/4.7); it surfaces the advisory
`recommended_verdict` + the pending human decision and must present them AS ADVISORY,
never as an effective decision.

# NON-NEGOTIABLE CONSTRAINTS
- PLAN FIRST GATE: before writing any code, outline a step-by-step architectural plan
  (the render tech, hosting, how the dashboard reads 4.2, the component/data-flow, edge
  cases, the tenant-isolation model) and get explicit approval on the plan before
  generating the implementation. (A plan-review gate, not a per-command lock: once the
  plan is approved you build to completion and open a PR per the WORKING AGREEMENT — the
  stakeholder still runs the LIVE commands.)
- RENDER ONLY over 4.2's derived payload: no re-derivation, no model call; do NOT
  re-assemble what 4.1/4.2 already assemble — consume `dashboard.contract.v1`.
- THE 3.5 recommendation stays ADVISORY + human-gated (RD-040): present
  `recommended_verdict` + the pending human decision AS ADVISORY (mirror 4.2's
  `advisory: true` + `decision: pending`); NEVER present it as an effective decision;
  the accept/reject ACTION + routing is 4.4/4.6/4.7, not 4.3. Never render a bare
  effective verdict.
- DASHBOARD DESIGN (learnings): DARK background theme; a graduated color scale for the
  `threat_tier` so low/medium/high/critical are distinguishable at a glance; the human
  APPROVE/REJECT control SURFACE; restore-point status/health as a first-class visible
  element; the operator headline views (PROJECT_PLAN §7: live activity; the port ⇄
  MITRE view; restore-point status/health).
- TENANT-AWARE (RD-028): per-SUBSCRIBER, org-shared; NO per-user filtering within a
  subscriber; design the data/access path per-subscriber now (even while ZTIE runs
  single-tenant) to avoid a costly T.2/T.3 retrofit.
- AWS-NATIVE hosting/serving + CI/CD (no GitHub Actions or external providers for
  operations). ServiceNow is OUT OF SCOPE.
- Production-quality: no mocks/placeholders unless explicitly agreed.
- VALIDATION-GATED, NEVER ON INFERENCE: status flips ONLY after a recorded live pass of
  the FINAL code. Recording an unverified pass is the exact drift the covenant forbids
  (METHODOLOGY §4).
- ROLES ARE FIXED: the LIVE commands are the STAKEHOLDER's action (the executor has no
  live AWS creds); the executor RECORDS the returned output VERBATIM. Do NOT simulate,
  assume, or fill in a live output.
- RESTORE-POINT DISCIPLINE: build from a known-good point (main after 4.2's merges);
  revert (code + state) rather than forward-patch. Story closure ≠ restore-point work
  (4.3's ✅ depends solely on its own recorded live validation).
- DOCS ARE FIRST-CLASS (RD-015): PR-reviewed, never straight to main; keep
  PROJECT_PLAN ↔ RUNBOOK in EXACT alignment.

# OPERATIONAL CONTEXT (state this on EVERY command block, if applicable)
  Build sandbox is INTEGRATIONS_ONLY: the executor has NO live AWS creds (PyPI + npm
  registry BLOCKED — boto3/jsonschema/aws-cdk-lib not installable). You BUILD; the
  STAKEHOLDER validates live in AWS CloudShell. Region us-east-1. The tracking table +
  the 4.2 dashboard Lambda are in the HUB (641628980935); the intake API + lanes are in
  FORENSIC (360999005254). Run `aws sts get-caller-identity` before every operational
  block; a banner comment does NOT change the account.
Never present a command without this banner. Confirm the target account/env before
every operational (esp. destructive) command.

# HARD-WON LESSONS (do NOT repeat)
- Verify the DEPLOYED/produced artifact, not just the local file: after any deploy,
  inspect the LIVE resource (env vars, IAM role, produced output) — a green
  `UPDATE_COMPLETE` can ship stale code or the wrong checkout.
- Confirm the target account before every operational command: the intake API is
  IAM/SigV4 in FORENSIC (a Hub principal gets 403 — the zero-trust gate working); the
  tracking table + Lambdas are in the HUB (a Forensic shell gets ResourceNotFound).
  Two CloudShell tabs; `aws sts get-caller-identity` before each block.
- Feed CloudShell commands ONE LINE AT A TIME (never paste a multi-line block); a
  multi-line `python -c` with embedded newlines in a `b'...'` literal breaks — build
  file content with `chr()` concatenation instead. `/tmp` + shell vars are WIPED on a
  CloudShell recycle — re-set vars in the same block.
- Give the user the FULL copy-paste command sequence (with real values), not bare
  command names.
- 4.2 (dep) live-proven pattern + payload shape 4.3 renders (recorded 2026-09-13,
  intake `891cb78f-…`): 4.2's `hub_dashboard` is invoked on demand (NOT stream-fed):
  `aws lambda invoke --payload "{\"view\":\"intake\",\"intake_id\":\"<id>\"}"` and
  `{"view":"fleet","limit":N}` `--cli-binary-format raw-in-base64-out`. The payload
  (`dashboard.contract.v1`): top-level `contract_version`/`view` (`intake`|`fleet`)/
  `assembled_at`; `view=intake` → `intake.status` (the 4.1 read-model:
  `overall_stage` + `stages` + `scores` static/dynamic/combined + `findings_summary` +
  `recommendation` with `recommended_verdict`/`decision: pending`/`advisory: true`) +
  `intake.threat` (`tier` unknown/low/medium/high/critical + `combined_score`/
  `highest_gap_severity`/`contradiction_present`) + `intake.action` (`intake_id` +
  `sha256` + `recommendation_status` + opt `recommended_verdict` + `decision: pending`
  + `advisory: true`); `view=fleet` → `fleet.intakes` (rows: `intake_id` +
  `overall_stage` + `threat_tier` + `decision` + opt `recommended_verdict`/`status`/
  `received_at`/`sha256`) + `returned_count` + `truncated` + `metrics` (`window_count`
  + `by_stage` + `by_recommended_verdict` + `by_threat_tier` + the STUBBED
  `ami_build_health`/`sensor_status`/`cost` = `not_wired`).
- The `threat_tier` is a DISPLAY band, never a verdict — color the render from it.
- The AMI/sensor/cost health blocks are STUBBED `not_wired` by 4.2 — render them as
  "not available yet", NOT as an error (their real data sources are a deferred
  follow-on story).
- Offline proof-bar tooling: `~/.pyenv/versions/3.12.13/bin/python3 -m unittest`
  (pytest NOT installed); `~/.pyenv/versions/3.12.13/bin/ruff check`; `env -u
  NODE_OPTIONS npx tsc --noEmit` shows ONLY the missing-`aws-cdk-lib` family (confirm
  NO NEW error TYPE; adding a stack Lambda adds only a `__dirname` TS2304 — an existing
  type); `env -u NODE_OPTIONS npx prettier --write`. `gh pr create` is BROKEN — open
  PRs via `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`.

# STEP 0 — RE-ESTABLISH TRUE STATE (before any edit)
# Trust `main` + `check_docs` over anything written here; if they disagree, `main`
# wins — reconcile before building.
- SECRET SCAN: before touching anything, scan the in-scope files for exposed API keys,
  bearer tokens, or secrets. If found, STOP and surface them (move them to a
  gitignored location); never commit a secret.
- `git fetch origin`; `git checkout main`; `git reset --hard origin/main`. List open
  PRs (expect: none of ours open; the unrelated #37 "Dashboard" may linger).
- `python3 scripts/check_docs.py` → expected PASS (a CHECK J advisory for the reorder
  is expected/OK). `~/.pyenv/versions/3.12.13/bin/python3 -m unittest
  scripts.test_check_docs` → SUITE OK.
- Sequence check (METHODOLOGY §5.A.0): confirm the WORK_LOG reorder still sequences the
  Phase-4 pipe work (4.3) ahead of the earlier-tier Ready items (B.1 tier 6;
  4.5/4.6/4.7 tier 14). If it does NOT, STOP and work the actual first OPEN Ready-now
  item; the executor never self-selects an out-of-order Ready story or edits the
  schedule to match. Reconcile the CHECK J advisory, do not ignore it.
- Confirm these EXPECTED TRUTHS (do NOT change them until validated live):
    - This story = 4.3 = ⬜ Not Started, build tier 15 (per the RUNBOOK master table's
      Build-tier column).
    - Tier transition: this session advances tier 14→15; confirm EVERY tier-≤14 story
      this depends on is ✅ so the new layer is open — 4.2 AND its inputs 4.1 + 3.1-3.5.
      A tier advance = re-verify the WHOLE new dependency set, not just 4.2.
    - Depends-on: 4.2 = ✅ (RD-042, dashboard JSON payload, validated live 2026-09-13).
    - Prior story 4.2 = ✅ (2026-09-13).
    - Restore tags present: {{list what `git ls-remote --tags origin` shows; note any
      referenced-but-absent PHANTOM tag}}.
    - Validation Debt Register state: expected EMPTY (gate disarmed / advancement
      permitted) — confirm the advancement gate is in place.
- Branch off `main` (after 4.2's merges). Branch name: `feature/story-4.3`. (If you cut
  it early and `main` moved, `git merge origin/main` + commit BEFORE running check_docs
  — the stale-branch trap.)

# THIS SESSION'S OBJECTIVE
Build the real-time dashboard that RENDERS 4.2's `dashboard.contract.v1` payload: the
fleet/list (colored by `threat_tier`), the per-intake detail drill-in, the operator
headline views (PROJECT_PLAN §7), and the human APPROVE/REJECT control SURFACE (the
advisory recommendation + the pending decision). Dark theme, graduated severity/threat
coloring, tenant-aware (per-subscriber). Confirm the render tech + AWS-native hosting +
the 4.2 read path with the stakeholder (PLAN FIRST GATE) before building.

# SCOPE & GUARDRAILS
- BLAST RADIUS: work ONLY within the new dashboard render/hosting artifacts (and any
  new CDK stack for hosting). Do not refactor or touch the 4.1/4.2 Lambdas, the
  tracking table, or any Phase-3 code; if a change here forces a change elsewhere,
  STOP and state what changed before proceeding.
- DATA & ISOLATION: before any UI work, pin down how the dashboard reads 4.2 (direct
  Lambda invoke vs. standing up the GET API front 4.2 deferred — 4.2's handler already
  accepts the API-Gateway pathParameters/queryStringParameters shape), the data model
  it renders (`dashboard.contract.v1`), and honour the isolation policy: RD-013 (only
  derived, allow-list data — the dashboard payload — ever leaves the Hub; no raw
  payload / executable content) + RD-028 (per-SUBSCRIBER, org-shared; no per-user
  filtering). The render must escape crossed/derived data (no stored XSS in the brains).
- In scope: the dashboard render + AWS-native hosting; consuming 4.2's payload; the
  dark-theme graduated color scheme; the operator headline views; the APPROVE/REJECT
  control SURFACE (the control + the advisory recommendation + the pending decision);
  tenant-aware design built in from the start.
- Out of scope / do NOT touch: the accept/reject ACTION + routing (4.4/4.6/4.7); the
  per-execution report (4.5); re-deriving any assessment; the 4.2 payload shape
  (consume it, do not change it); ServiceNow.
- Depends on (must already be ✅): 4.2 (and through it 4.1 + 3.1-3.5).

# DEFINITION OF DONE (this session) — a PASS/FAIL GATE, not a description
- For a real run, the dashboard RENDERS 4.2's payload: the fleet/list colored by
  `threat_tier`, the per-intake detail drill-in, the operator headline views, and the
  human APPROVE/REJECT control surface (advisory recommendation + pending decision) —
  dark theme, graduated severity/threat coloring.
- Render only — no re-derivation, no model call; the recommended_verdict is presented
  AS ADVISORY (never an effective decision); tenant-aware (per-subscriber); RD-013/
  RD-028 honoured; the render escapes derived data (no stored XSS).
- KNOWN CAVEAT baked in: the AMI/sensor/cost health blocks arrive `not_wired` from 4.2
  — the dashboard must render them as "not available yet"; that is the correct state,
  NOT a failure.
- Validated LIVE and RECORDED: the STAKEHOLDER confirms a live run (a real intake shows
  correctly, with correct severity coloring) AND you RECORD it in the runbook. No
  recorded pass → stays 🟡. If validation FAILS: not done — stay here, fix, re-validate.

# ENVIRONMENT
- The executor works in this sandbox: push to a branch (never main directly), open PRs
  via the `gh api` REST endpoint (not interactive `gh pr` subcommands). The executor
  has NO live AWS creds.
- LIVE AWS is the STAKEHOLDER's action, run in AWS CloudShell — typically TWO tabs: a
  FORENSIC (360999005254) tab to submit an intake and a HUB (641628980935) tab to
  deploy + drive the dashboard/its 4.2 read. Run `aws sts get-caller-identity` before
  every block; a banner comment does NOT change the account.
- Terminal prompt in shell interaction blocks is written as
  `[HUB] ~/ZTIE-Issues/infra $` (or `[FORENSIC] ...`) to make the target account
  unambiguous.
- npm registry is BLOCKED in the build sandbox; if the render stack needs npm deps the
  STAKEHOLDER installs them in CloudShell during the live build. Confirm the hosting/
  build approach at the PLAN FIRST GATE.

# WORKING AGREEMENT
- One story to completion. Design -> build -> STAKEHOLDER validates live -> you RECORD
  the result + flip status -> paired status commit. Push to a branch, open a PR, never
  push to main directly.
- Validation drives status; the hard advancement gate governs advancement (STEP 0 +
  "WHAT THIS STORY IS"). Clearing debt is permitted while the register is non-empty;
  opening a NEW feature story is not.
- MANAGEMENT ARTIFACTS ARE FIRST-CLASS (RD-015): the plan, runbook, methodology,
  restore/BOM, templates, registered decisions, and this story's brief/prompt are held
  to the SAME bar as the code. 4.3 is NOT done until its management artifacts are
  updated AND PROJECT_PLAN and RUNBOOK are in EXACT alignment (4.3 identical in both),
  all doc changes PR-reviewed, and the governance is restorable alongside the code. If
  4.3 introduces a genuine new design decision (e.g. the hosting/serving architecture),
  register the next free RD — VERIFY with `grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md |
  sort -u | tail` (expect RD-043) — and add its plan-table row BEFORE referencing the
  number in any living doc (CHECK E is literal).
- If this story CHANGED PROJECT STATUS, update the RUNBOOK master table ONLY (the single
  source of truth for status). Do NOT hand-edit status into README / the on-deck
  pointer / BUILD_ORDER — those POINT to the RUNBOOK; `scripts/check_docs.py` (CHECK H)
  verifies they still agree. Repoint the `_NEW_WORK_STORY` fixture off 4.3 (→ the next
  still-⬜ feature story) IN THE SAME PR. Run `check_docs` only AFTER committing the
  status/register edit (CHECK B baseline is `git show HEAD:RUNBOOK.md`).
- At session end, author the NEXT story's brief + prompt — MANDATORY — with a Lessons
  Learned / Carry-Forward section of THIS session's actual lessons, favouring live-run
  lessons over guesses. Author the 4.3 LIVE-RUNBOOK for the stakeholder's real
  validation, and the next-story handoff, BEFORE pointing the on-deck README at them
  (CHECK I bites on a link to a not-yet-authored file). Read WHICH story to hand off to
  off the RUNBOOK "Ready now" schedule (first OPEN item, tier order) — not "the next
  story in my head"; if a lower-tier Ready item is still open ahead of the next pipe
  story, point the on-deck starter at THAT item or record an explicit stakeholder
  reorder in `docs/governance/WORK_LOG.md` first. Treat a CHECK J note as a signal to
  reconcile the pointer or log the reorder, not to ignore.
- If blocked, push partial progress + a draft PR; never silently fail.
```
