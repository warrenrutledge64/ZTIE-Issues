# Story 4.2 (dashboard JSON payload — the Phase-4 data layer)

You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting. Do NOT change anything until you have (a) READ the plan +
runbook + methodology + this story's brief (`session-briefs/story-4.2-brief.md`), (b)
re-established true state (STEP 0), and (c) confirmed the Validation Debt Register + the
advancement gate.

# PROJECT IDENTITY
ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted artifact
BEFORE it reaches the PDE. Validation-gated: nothing is ✅ until a recorded live pass (the
covenant). Three accounts: Pipeline-Hub (641628980935) = brains/control plane + durable
record + Bedrock; Forensic (360999005254) = self-contained blast zone; Pipeline-Sandbox
(586917955591) = ZTIE→PDE handoff.

# WHERE THIS STORY SITS — BUILD TIER 14, ADVANCING TIER 13 → 14 (WITHIN PHASE 4)
Story 4.2 is **build tier 14**; this session **ADVANCES tier 13 → 14** (its tier-13
dependency `4.1` goes ✅, a new dependency layer opens). This is a tier move **WITHIN
Phase 4** — NOT a phase transition (Phase 4 opened at 4.1). STEP 0 must re-confirm the
ENTIRE tier-≤13 set is ✅ (`4.1` AND its Phase-3 inputs 3.1-3.5).

⚠️ SEQUENCING — 4.2 IS THE NEXT *PIPE* STORY, BUT CONFIRM IT IS THE FIRST OPEN READY ITEM.
The story to START is the **first OPEN item in the RUNBOOK "Ready now" schedule, in tier
order** (METHODOLOGY §5.A.0) — verified live in STEP 0, the RUNBOOK is the source of truth.
As of authoring the Ready-now OPEN items are **4.2 (tier 14)**, **4.5 / 4.6 / 4.7 (tier 14,
also unblocked by 4.1)**, and **B.1 (tier 6, F&H)**. B.1 is LOWER-tier, so by strict tier
order it would be first — BUT the recorded stakeholder reorder (`docs/governance/WORK_LOG.md`,
2026-09-13) sequences the Phase-4 pipe work (starting 4.2) ahead of the F&H track. STEP 0
MUST confirm that reorder still stands; if not, STOP and reconcile. Expect `check_docs`
CHECK J to flag the on-deck-vs-first-OPEN mismatch as a NON-BLOCKING advisory pointing at the
logged reorder — reconcile it, do not ignore it.

# PRIOR-SESSION UPDATE (2026-09-13, after the Story 4.1 session)
Current true state on `main` (STEP 0 RE-VERIFIES — trust `main` + `check_docs`; if they
disagree, `main` wins):
- **Story 4.1 is ✅** (RD-041, status-retrieval orchestrator) — validated live 2026-09-13,
  intake `384d63ef-7577-4787-ba0e-cc5d92305ff9`, Hub 641628980935. It built
  `lambdas/hub_status/`: a PURE, READ-only, ON-DEMAND orchestrator that assembles the
  per-intake **status read-model** (`status.contract.v1`) — NOT a durable record, NOT a
  stream consumer, NO model call, NO write. **4.2 consumes that read-model and SHOULD reuse
  `status_model.build_status` for the per-intake core** rather than re-assembling it.
- **The register is EMPTY, Phase 3 is CLOSED, Phase 4 is under way.** The advancement gate
  is OPEN.
- **3.5's `recommended_verdict` is ADVISORY + human-gated (RD-040)** and 4.1 surfaces it with
  an explicit `advisory: true` + `decision: pending`. 4.2 MUST preserve this: surface the
  recommendation + the pending human decision; NEVER present/persist it as an effective
  decision; NEVER write a verdict onto any record; keep the 3.1-3.4 records verdict-free.
- **Design watch-item (be aware):** do NOT add COMPLIANCE-mode 365-day S3 Object Lock to any
  bucket (the stakeholder does not want WORM on ZTIE forensic data). **ServiceNow is OUT OF
  SCOPE** for the ZTIE workflow + dashboard.

# ⚠️ ADVANCEMENT GATE — CHECK THIS FIRST
NEW FEATURE story. It may begin ONLY if its Depends-on are ALL ✅ AND the Validation Debt
Register is EMPTY. **4.2 depends on 4.1 ✅.** STEP 0 MUST re-confirm on `main`: `4.1` ✅ and
the register EMPTY (trust `main` + `check_docs`). `check_docs` CHECK B, machine-enforced.
Depends-on: **4.1 ✅**. Build tier 14.

# WHAT 4.2 IS — the Phase-4 data layer
Phase 4 turns the accumulated Phase-3 record into human-facing outputs. 4.1 built the
per-intake status read-model. **4.2 builds the comprehensive DASHBOARD JSON PAYLOAD** the
real-time dashboard renders (4.3 is the render). It has two parts:
1. a **per-intake detail view** — assembled from 4.1's read-model (reuse `status_model`), and
2. a **fleet/list view** — recent intakes (prefer the tracking table's `status-received_at`
   GSI, bounded, no full scan) + **pipeline health metrics** (AMI build health, sensor
   status, cost, detonation verdict mix).

# THE JOB
For the dashboard, assemble a bounded, DERIVED JSON payload: the per-intake detail (from 4.1)
+ the fleet/list + health/cost metrics, in the shape the dashboard (4.3) renders. It is a
READ/transform step; it does NOT re-derive any assessment, does NOT make a model call, and
does NOT enforce anything. **Confirm the exact output shape + boundary + the list/metrics
sources with the stakeholder before building.**

# CONTRACT-FIRST DECISION (make + justify; register a new RD only if a genuine sub-decision)
Decide + justify CONTRACT-FIRST, mirroring 4.1 (RD-041): (a) whether 4.2's output is a NEW
durable Hub-side field/contract OR an on-demand READ transform behind an orchestrator/API
(pure logic + thin READ-only seam, no new durable field). **Prefer the 4.1 pattern** (PURE,
READ-only, on-demand, a response/transport contract; reuse `status_model` + the two-layer
conformance test). The exact 4.2 output shape + the fleet/list source + which health metrics
to include + whether to stand up the HTTP API front now (a GET `/status/{intake_id}` +
a list/dashboard endpoint — 4.1's handler already accepts the API-Gateway
pathParameters/queryStringParameters shape) is a STAKEHOLDER decision — confirm + record it.
Only author a NEW RD (next free number after RD-041 — VERIFY with `grep -oE
"RD-0[0-9][0-9]" PROJECT_PLAN.md | sort -u | tail`, expect RD-042) if 4.2 introduces a
genuine new design decision. CHECK E is literal — add any new RD's plan-table row BEFORE
referring to the number in a living doc.

# NON-NEGOTIABLE CONSTRAINTS
- READ/transform only; do not re-normalize/re-correlate/re-score/rebuild findings/re-derive
  the verdict (those are 3.1-3.5) and do not re-assemble what 4.1 already assembles (reuse
  it). No model call.
- THE 3.5 VERDICT STAYS ADVISORY + HUMAN-GATED (RD-040). 4.2 surfaces `recommended_verdict`
  + the pending human decision with an explicit advisory marker (as 4.1's `advisory: true`);
  it NEVER promotes/routes/enforces (that is 4.4/4.6/4.7), and NEVER writes a verdict onto any
  record. Run a `_no_banned_keys` scan (`verdict`/`safe`/`approved`/`forward`/`malicious`/
  `pass_fail`/`clean`) over the payload with `recommended_verdict` deliberately allow-listed.
  Do NOT name any field a bare `verdict` (4.1's `stages` flag is `verdict_recommendation`).
- DASHBOARD DESIGN (learnings): the payload must supply what a DARK-THEME,
  severity/threat-color-graded dashboard needs (a normalized severity/threat tier per item so
  the render can color low/medium/high/critical) + the data for the human APPROVE/REJECT
  control (the advisory recommended_verdict + the pending human decision + the intake identity
  the 4.4/4.6/4.7 action keys on). ServiceNow is OUT OF SCOPE.
- BOUNDED IN + BOUNDED OUT; allow-list; if durable, integrity-keyed by intake_id + sha256.
  RD-009/RD-013 intact (reason only over derived Hub-side data; no raw data, no Forensic
  durable store). If it lists intakes, prefer the `status-received_at-index` GSI (no scan).
- PURE LOGIC + THIN SEAM (the proven 1.2→4.1 pattern); READ-only if it is a read transform.
  AWS-native orchestration only (no GitHub Actions for operations).
- VALIDATION-GATED: 4.2 flips ✅ only on a recorded LIVE pass of the FINAL code.
- DOCS FIRST-CLASS (RD-015): PR-reviewed; PROJECT_PLAN ↔ RUNBOOK aligned.

# OPERATIONAL CONTEXT (state on EVERY command block)
  Build sandbox is INTEGRATIONS_ONLY (NO AWS creds; PyPI + npm BLOCKED — boto3/pytest/moto/
  jsonschema/aws-cdk-lib NOT installable). You BUILD; the USER validates live. Region
  us-east-1; `aws sts get-caller-identity` before EVERY operational block. Tracking table +
  the dashboard Lambda are in the HUB. If 4.2 is PURE (recommended) there is NO Bedrock
  prerequisite. Tests with `~/.pyenv/versions/3.12.13/bin/python3 -m unittest` (pytest NOT
  installed — use `unittest`); `ruff` at `~/.pyenv/versions/3.12.13/bin/ruff` (DEFAULT rules
  — a generator script needs `chmod +x` or EXE001 fires; watch RUF046/RUF059/ISC004, blind
  `except Exception` needs `# noqa: BLE001`). `prettier`/`tsc` need `env -u NODE_OPTIONS`;
  npm BLOCKED so `tsc --noEmit` shows ONLY the missing-`aws-cdk-lib` family — the `main`
  baseline is 109 errors after 4.1 (TS2304=12, TS2307=49, TS2339=36, TS2353=6, TS2591=6);
  adding a stack Lambda adds `__dirname` TS2304 (an EXISTING type — fine; confirm NO NEW
  error TYPE). Do NOT prettier-reformat generated JSON contracts. Keep tests stdlib-only +
  boto3-stubbed.

# HARD-WON LESSONS (do NOT repeat) — from the 4.1 build + LIVE validation (2026-09-13)
- **The PURE + on-demand read-transform pattern validated live (RD-041).** 4.1 =
  `lambdas/hub_status/`: PURE `status_model.py` + thin READ-only `awsio.py` (`get_item` only,
  NO `put_*`) + on-demand `handler.py` (invoked by `intake_id`; also accepts the API-Gateway
  pathParameters/queryStringParameters shape) + `status.contract.v1` response contract +
  two-layer conformance test (stdlib walk + `jsonschema` skipUnless). **Reuse this skeleton;
  reuse `status_model.build_status` for the per-intake core.**
- **4.1's live output shape 4.2 consumes:** `contract_version`/`intake_id`/`sha256`/
  `assembled_at`/`overall_stage`/`stages` (`combined_event`/`correlation`/`scoring`/
  `remediation`/`verdict_recommendation`/opt `classification`)/opt `status`+`received_at`/opt
  `scores` (static/dynamic/combined + `rubric_version`)/opt `findings_summary` (status +
  counts + `highest_gap_severity` + `contradiction_present`)/`recommendation` (`status` +
  `decision: pending` + `advisory: true` + opt `recommended_verdict`/`rubric_version`/
  `summary`) + `read_model_note`. Live: intake `384d63ef-…`, `overall_stage: recommended`,
  scores 55/30/70, `recommended_verdict: INCONCLUSIVE`.
- **`stages` key naming trap:** never name a field a bare `verdict` — it collides with the
  banned-key scan. 4.1 used `verdict_recommendation`. Same discipline for new dashboard fields.
- **READ-only proof (live DoD):** 4.1 re-read the tracking item after invoke to prove NOTHING
  was written (identical key set before/after). If 4.2 is a read transform, do the same;
  `grantReadData` only (READ role = GetItem/Query/BatchGetItem/Scan/DescribeTable/
  ConditionCheckItem/GetRecords/GetShardIterator — NO Update/Put/Delete). Verify the LIVE
  role + env (no `NOVA_MODEL_ID`) after deploy — never trust the green `UPDATE_COMPLETE`.
- **Live invoke shape:** `aws lambda invoke --payload "{\"intake_id\":\"<id>\"}"
  --cli-binary-format raw-in-base64-out`. Two tabs (Forensic submit / Hub deploy+invoke),
  `sts get-caller-identity` before each block; the tracking table + dashboard Lambda are in
  the Hub; use a ROUTABLE artifact (small CloudFormation template) so all Phase-3 stages land;
  pin the intake endpoint with `[?contains(OutputValue,'/intake')].OutputValue | [0]`; feed
  commands ONE LINE AT A TIME; the Hub Lambdas use custom OD-003 LogGroups (tail
  `LoggingConfig.LogGroup`, not `/aws/lambda/<fn>`); reads eventually-consistent.
- **check_docs:** `_NEW_WORK_STORY` fixture is now **4.2** — when 4.2 leaves ⬜, repoint to
  4.3 IN THE SAME PR. CHECK I bites if a living doc links a not-yet-authored file — author the
  next-story handoff + the 4.2 LIVE-RUNBOOK BEFORE pointing the on-deck README at them. Run
  `check_docs` only AFTER committing status/register edits (CHECK B baseline is `git show
  HEAD:RUNBOOK.md`). Set 4.2 🟡 AND add it to the register in the SAME commit. `gh pr create`
  is BROKEN — open PRs via `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`.
- **Stale-branch guard:** cut `feature/story-4.2` from the LATEST `main` (after 4.1's docs
  merge); if you branched early, `git merge origin/main` + commit BEFORE running check_docs.

# STEP 0 — RE-ESTABLISH TRUE STATE
- `git fetch origin`; `git checkout main`; `git reset --hard origin/main`. List open PRs.
- `python3 scripts/check_docs.py` → PASS (a CHECK J advisory for the reorder is expected/OK).
  `python3 -m unittest scripts.test_check_docs` → SUITE OK.
- Confirm: this story = 4.2 = ⬜, build tier 14, Depends-on `4.1`; tier 13 → 14 WITHIN Phase 4;
  EVERY tier-≤13 dep ✅ (`4.1` + 3.1-3.5); register EMPTY + `4.1` ✅ (if not, STOP). CONFIRM
  the exact 4.2 output shape/boundary/list+metrics sources + HTTP-front decision with the
  stakeholder before coding.
- **Sequence check (METHODOLOGY §5.A.0):** confirm the WORK_LOG reorder still sequences 4.2
  ahead of B.1; reconcile the CHECK J advisory, do not ignore it.
- Branch off `main`. Branch name: `feature/story-4.2`.

# DEFINITION OF DONE — a PASS/FAIL GATE
1. For a real run, 4.2 assembles the dashboard JSON payload (per-intake detail from the 4.1
   read-model + a fleet/list view + health/cost metrics) in the shape the render (4.3) uses.
2. READ/transform only — no re-derivation, no model call; the recommended_verdict stays
   advisory (with an explicit advisory marker, never enforced); RD-009/RD-013 intact; the
   3.1-3.4 records stay verdict-free; no bare effective-verdict key in the payload.
3. Validated LIVE and RECORDED (a real run producing the populated dashboard payload).
- Goes ✅ ONLY on a recorded live pass of the FINAL code. No pass → stays 🟡 (+ register).

# WORKING AGREEMENT
- One story to completion: design → build → validate → RECORD + flip status → paired commit;
  push to a branch; open a PR via `gh api …/pulls`. After merge, `git log
  main..feature/story-4.2`.
- Validation drives status; the advancement gate governs advancement.
- MANAGEMENT ARTIFACTS FIRST-CLASS (RD-015): brief + RUNBOOK + PROJECT_PLAN aligned; any new
  RD (+ candidate mappings) recorded; repoint `_NEW_WORK_STORY` off 4.2 (→ 4.3); re-run doc
  checks AFTER committing.
- Author a 4.2 LIVE-RUNBOOK for the stakeholder's real validation.
- At session end, author the next Phase-4 story's brief + prompt with this session's real
  Lessons Learned.
- If blocked, push partial progress + a draft PR; surface the blocker; never silently fail.
