# Story 4.3 (real-time dashboard render — the Phase-4 presentation layer)

You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting. Do NOT change anything until you have (a) READ the plan +
runbook + methodology + this story's brief (`session-briefs/story-4.3-brief.md`), (b)
re-established true state (STEP 0), and (c) confirmed the Validation Debt Register + the
advancement gate.

# PROJECT IDENTITY
ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted artifact
BEFORE it reaches the PDE. Validation-gated: nothing is ✅ until a recorded live pass (the
covenant). Three accounts: Pipeline-Hub (641628980935) = brains/control plane + durable
record + Bedrock; Forensic (360999005254) = self-contained blast zone; Pipeline-Sandbox
(586917955591) = ZTIE→PDE handoff.

# WHERE THIS STORY SITS — BUILD TIER 15, ADVANCING TIER 14 → 15 (WITHIN PHASE 4)
Story 4.3 is **build tier 15**; this session **ADVANCES tier 14 → 15** (its tier-14
dependency `4.2` goes ✅, a new dependency layer opens). This is a tier move **WITHIN
Phase 4** — NOT a phase transition. STEP 0 must re-confirm the ENTIRE tier-≤14 set is ✅
(`4.2` AND its inputs 4.1 + 3.1-3.5).

⚠️ SEQUENCING — CONFIRM 4.3 IS THE INTENDED NEXT STORY. The story to START is the **first
OPEN item in the RUNBOOK "Ready now" schedule, in tier order** (METHODOLOGY §5.A.0) — but the
Phase-4 pipe ordering has followed a recorded stakeholder reorder (`docs/governance/WORK_LOG.md`)
that sequences the pipe work ahead of the F&H B.1. 4.5/4.6/4.7 (tier 14) and B.1 (tier 6) are
LOWER-tier than 4.3, so 4.3 is NOT the strict-tier first-OPEN item — CONFIRM with the
stakeholder which Phase-4 story is next (4.3 render vs. the 4.5 report vs. the 4.6/4.7
enforcement actions) and reconcile the `check_docs` CHECK J advisory; if the intended next
story is not 4.3, STOP and start that one instead.

# PRIOR-SESSION UPDATE (after the Story 4.2 session)
Current true state on `main` (STEP 0 RE-VERIFIES — trust `main` + `check_docs`; if they
disagree, `main` wins):
- **Story 4.2 is ✅** (RD-042, dashboard JSON payload) — the PURE, READ-only, ON-DEMAND
  `hub_dashboard` orchestrator that assembles `dashboard.contract.v1` in two shapes
  (`view=intake` = the 4.1 read-model + `threat` tier + `action`; `view=fleet` = recent-intake
  rows via the `status-received_at-index` GSI + `metrics`). NO model call, NO write, NO stream.
  **4.3 RENDERS that payload** — do NOT re-derive anything, do NOT re-assemble what 4.2/4.1
  assemble; consume the payload.
- **The register is EMPTY, Phase 4 is under way.** *(STEP 0 re-verifies.)*
- **The 3.5 `recommended_verdict` is ADVISORY + human-gated (RD-040).** 4.2 surfaces it +
  `decision: pending` + `advisory: true`. 4.3 MUST present it as advisory — the accept/reject
  ACTION + routing is 4.4/4.6/4.7, NOT 4.3. Never present the recommendation as an effective
  decision.
- **Design watch-items:** the AMI/sensor/cost health blocks in 4.2's `metrics` are STUBBED
  `not_wired` (render as "not available yet", not an error). Dashboard = DARK theme + graduated
  severity/threat color grading of `threat_tier`. Tenant-aware (RD-028): per-SUBSCRIBER,
  org-shared, no per-user filtering — build the data/access path per-subscriber now. ServiceNow
  is OUT OF SCOPE.

# ⚠️ ADVANCEMENT GATE — CHECK THIS FIRST
NEW FEATURE story. It may begin ONLY if its Depends-on are ALL ✅ AND the Validation Debt
Register is EMPTY. **4.3 depends on 4.2 ✅.** STEP 0 MUST re-confirm on `main`: `4.2` ✅ and
the register EMPTY. `check_docs` CHECK B, machine-enforced. Build tier 15.

# WHAT 4.3 IS — the Phase-4 render
4.1 built the per-intake status read-model; 4.2 built the comprehensive dashboard JSON
payload; **4.3 RENDERS it** as the real-time dashboard: the fleet/list (colored by
`threat_tier`), the per-intake detail drill-in, the operator headline views (live activity;
the port ⇄ MITRE view; restore-point status/health as a first-class element — PROJECT_PLAN
§7), and the human APPROVE/REJECT control SURFACE (the advisory `recommended_verdict` + the
pending decision; the ACTION itself is 4.4/4.6/4.7).

# THE JOB
Render 4.2's `dashboard.contract.v1` payload as the real-time dashboard: dark theme, graduated
severity/threat coloring, the fleet + per-intake drill-in, the operator headline views, and the
human accept/reject control surface. It is a PRESENTATION layer; it does NOT re-derive any
assessment, does NOT make a model call, and does NOT itself enforce anything. **Confirm the
render tech + AWS-native hosting + how the dashboard reads 4.2 (direct Lambda invoke vs. the GET
API front 4.2 deferred) with the stakeholder before building.**

# CONTRACT-FIRST / DECISION (make + justify; register a new RD only if a genuine sub-decision)
4.3 consumes 4.2's contract; it likely needs NO new data contract. Author a NEW RD only if a
genuine new design decision arises (e.g. the hosting/serving architecture) — next free number
after RD-042 (VERIFY with `grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md | sort -u | tail`, expect
RD-043). CHECK E is literal — add any new RD's plan-table row BEFORE referencing the number in a
living doc. The render tech, AWS-native hosting, and the 4.2 read path are STAKEHOLDER decisions.

# NON-NEGOTIABLE CONSTRAINTS
- RENDER only over 4.2's derived payload; no re-derivation, no model call; do not re-assemble
  what 4.1/4.2 assemble.
- THE 3.5 VERDICT STAYS ADVISORY + HUMAN-GATED (RD-040). Present `recommended_verdict` + the
  pending human decision as ADVISORY; NEVER as an effective decision; the accept/reject ACTION
  + routing is 4.4/4.6/4.7.
- DASHBOARD DESIGN (learnings): DARK background; graduated color scale for `threat_tier`
  (low/medium/high/critical at a glance); the human APPROVE/REJECT control; restore-point
  status/health as a first-class visible element; the operator headline views (PROJECT_PLAN §7).
- TENANT-AWARE (RD-028): per-SUBSCRIBER, org-shared; no per-user filtering; design the
  data/access path per-subscriber now.
- AWS-NATIVE hosting/serving (no GitHub Actions or external providers for operations).
- ServiceNow OUT OF SCOPE.
- VALIDATION-GATED: 4.3 flips ✅ only on a recorded LIVE pass of the FINAL code.
- DOCS FIRST-CLASS (RD-015): PR-reviewed; PROJECT_PLAN ↔ RUNBOOK aligned.

# OPERATIONAL CONTEXT (state on EVERY command block)
  Build sandbox is INTEGRATIONS_ONLY (NO AWS creds; PyPI + npm BLOCKED). You BUILD; the USER
  validates live. Region us-east-1; `aws sts get-caller-identity` before EVERY operational
  block. The tracking table + the 4.2 dashboard Lambda are in the HUB. Tests with
  `~/.pyenv/versions/3.12.13/bin/python3 -m unittest` (pytest NOT installed); `ruff` at
  `~/.pyenv/versions/3.12.13/bin/ruff`; `prettier`/`tsc` need `env -u NODE_OPTIONS`; npm BLOCKED
  so `tsc --noEmit` shows ONLY the missing-`aws-cdk-lib` family (confirm NO NEW error TYPE).
  `gh pr create` is BROKEN — open PRs via `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`.

# HARD-WON LESSONS (do NOT repeat) — from the 4.2 build + LIVE validation
- **The PURE + on-demand read-transform pattern (RD-041/RD-042) is validated.** 4.2 =
  `lambdas/hub_dashboard/`: PURE `dashboard.py` (threat-tier banding + intake view delegating to
  the reused `status_model.build_status` + fleet rows + metrics) + a thin READ-only `awsio.py`
  (`get_item` + a bounded GSI `Query`, no write) + `handler.py` (`view=intake|fleet`, direct +
  API-shaped) + `dashboard.contract.v1` + a two-layer conformance test + a VENDORED byte-identical
  `status_model.py` (with a no-drift test, because each Lambda dir bundles as its own asset).
- **The 4.2 payload shape 4.3 renders** (fill exact live values from the 4.2 live run): top-level
  `contract_version`/`view`/`assembled_at`; `view=intake` → `intake.status` (the 4.1 read-model),
  `intake.threat` (`tier` + `combined_score`/`highest_gap_severity`/`contradiction_present`),
  `intake.action` (`intake_id`+`sha256`+`recommendation_status`+opt `recommended_verdict`+
  `decision: pending`+`advisory: true`); `view=fleet` → `fleet.intakes` (rows) +
  `fleet.returned_count`+`fleet.truncated`+`fleet.metrics` (counts + the stubbed
  `ami_build_health`/`sensor_status`/`cost` = `not_wired`).
- **Threat tier is a DISPLAY band, never a verdict** — color the render from `threat_tier`
  (unknown/low/medium/high/critical). The AMI/sensor/cost health are STUBBED `not_wired` — render
  as "not available yet".
- **check_docs:** `_NEW_WORK_STORY` fixture is now **4.3** — when 4.3 leaves ⬜, repoint to the
  next still-⬜ feature story IN THE SAME PR. CHECK I bites if a living doc links a not-yet-authored
  file — author the next-story handoff + the 4.3 LIVE-RUNBOOK BEFORE pointing the on-deck README at
  them. Run `check_docs` only AFTER committing status/register edits (CHECK B baseline is `git show
  HEAD:RUNBOOK.md`). Set 4.3 🟡 AND add it to the register in the SAME commit.
- **Stale-branch guard:** cut `feature/story-4.3` from the LATEST `main` (after 4.2's docs merge);
  if you branched early, `git merge origin/main` + commit BEFORE running check_docs.

# STEP 0 — RE-ESTABLISH TRUE STATE
- `git fetch origin`; `git checkout main`; `git reset --hard origin/main`. List open PRs.
- `python3 scripts/check_docs.py` → PASS (a CHECK J advisory for the reorder may be expected/OK).
  `python3 -m unittest scripts.test_check_docs` → SUITE OK.
- Confirm: this story = 4.3 = ⬜, build tier 15, Depends-on `4.2`; tier 14 → 15 WITHIN Phase 4;
  EVERY tier-≤14 dep ✅ (`4.2` + 4.1 + 3.1-3.5); register EMPTY + `4.2` ✅ (if not, STOP).
  CONFIRM the render tech + AWS-native hosting + the 4.2 read path + the Phase-4 sequencing with
  the stakeholder before coding.
- Branch off `main`. Branch name: `feature/story-4.3`.

# DEFINITION OF DONE — a PASS/FAIL GATE
1. For a real run, the dashboard renders 4.2's payload — the fleet/list colored by threat tier,
   the per-intake drill-in, the operator headline views, and the APPROVE/REJECT control surface.
2. Render only — no re-derivation, no model call; the recommended_verdict stays advisory (never
   an effective decision); dark theme + graduated severity/threat coloring; tenant-aware design.
3. Validated LIVE and RECORDED (a real intake renders correctly with correct severity coloring).
- Goes ✅ ONLY on a recorded live pass of the FINAL code. No pass → stays 🟡 (+ register).

# WORKING AGREEMENT
- One story to completion: design → build → validate → RECORD + flip status → paired commit;
  push to a branch; open a PR via `gh api …/pulls`. After merge, `git log main..feature/story-4.3`.
- Validation drives status; the advancement gate governs advancement.
- MANAGEMENT ARTIFACTS FIRST-CLASS (RD-015): brief + RUNBOOK + PROJECT_PLAN aligned; any new RD
  (+ candidate mappings) recorded; repoint `_NEW_WORK_STORY` off 4.3; re-run doc checks AFTER
  committing.
- Author a 4.3 LIVE-RUNBOOK for the stakeholder's real validation.
- At session end, author the next Phase-4 story's brief + prompt with this session's real
  Lessons Learned.
- If blocked, push partial progress + a draft PR; surface the blocker; never silently fail.
