# Story T.1 (multi-tenant isolation — DESIGN SPIKE, doc-only)

You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting. Do NOT change anything until you have (a) READ the plan +
runbook + methodology + this story's brief (`session-briefs/story-T.1-brief.md`) + the
RD-028 decision row in `PROJECT_PLAN.md` + the T.1 spec in `docs/STORY_DETAIL.md#story-t-1`,
(b) re-established true state (STEP 0), and (c) confirmed the sequencing + gate state.

# PROJECT IDENTITY
ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted artifact
BEFORE it reaches the PDE. Validation-gated: nothing is ✅ until a recorded pass (the
covenant) — for a DESIGN story like T.1 the "pass" is a recorded STAKEHOLDER REVIEW, not a
live green-run. Three accounts: Pipeline-Hub (641628980935) = brains/control plane + durable
record; Forensic (360999005254) = self-contained blast zone; Pipeline-Sandbox (586917955591)
= ZTIE→PDE handoff.

# WHAT T.1 IS — READ THIS (a DESIGN SPIKE, doc-only, NO code, NO live AWS)
T.1 writes ONE architecture doc — `docs/architecture/MULTI_TENANCY.md` — capturing the
ALREADY-SETTLED RD-028 multi-tenancy decisions, and moves RD-028 from Proposed toward
Ratified. **There is NO production code, NO Lambda, NO CDK, NO schema, NO test, and NO live
AWS deploy in this story.** Its validation is a stakeholder REVIEW of the doc + RD-028
ratification — there is no CloudShell / green-run gate. Do NOT build anything; do NOT
re-open or re-litigate RD-028 (document it, with rationale + rejected alternatives).

# WHERE THIS STORY SITS — TIER 5 (tenancy track), FIRST OPEN READY-NOW ITEM
T.1 is **build tier 5** on the `tenancy` track (per the RUNBOOK master table). Its only
dependency (2.3) is ✅. It is NOT on the pipe tier ladder — it is a doc-only spike that has
been schedulable for a while and is deliberately being done NOW (before Phase 4).

⚠️ SEQUENCING — T.1 IS NEXT PER THE RUNBOOK, NOT AN ASSERTION HERE. Story 3.5 closed Phase 3
(2026-09-13). Per the sequencing rule (METHODOLOGY §5.A.0) the story to START is the **first
OPEN item in the RUNBOOK "Ready now" schedule, in tier order** — verified live in STEP 0. That
first OPEN item is **T.1 (tier 5)**, ahead of the next pipe story 4.1 (tier 13). The
stakeholder recorded this ordering on 2026-09-13 in `docs/governance/WORK_LOG.md` (T.1 should
land before Phase 4 — it protects the Phase-4 dashboard/Hub design). STEP 0 re-confirms T.1 is
genuinely the first OPEN Ready-now item; if the RUNBOOK shows an earlier OPEN item, STOP and
surface it.

# GATE STATE
The Validation Debt Register is EMPTY (3.5 cleared it 2026-09-13), so no advancement gate is
armed. T.1's dependency (2.3) is ✅. STEP 0 confirms both. T.1 is a design story, so it does
not itself add validation debt in the usual sense — but it is not ✅ until the stakeholder
review passes (do not self-certify).

# THE JOB
Author `docs/architecture/MULTI_TENANCY.md` capturing (from RD-028 — write up, do NOT
re-decide):
- **BETWEEN subscribers = HARD isolation via a per-subscriber Forensic AWS account** (vended
  via AWS Organizations; Hub stays the shared control plane). Record the alternatives
  considered + rejected as primary (per-tenant VPC in a shared account; per-tenant full-stack
  cell) and WHY.
- **WITHIN a subscriber = SHARED-TRUST** — users share the subscriber's environment + the
  org-shared dashboard; isolation granularity is **per-subscriber, NOT per-user** (no per-user
  accounts / partitioning / IAM). Team-vs-team isolation inside an org is a future opt-in,
  explicitly out of scope now.
- **Residue containment = the ephemeral host + wiped EBS volume**, NOT accounts/endpoints
  (ties to RD-027) — so the design is not over-built.
- **The subscriber-identifier model** + how the **Hub partitions many subscribers' data** on
  the shared control plane (tracking record + dashboard queries scoped by subscriber).
- **The Phase-4 dashboard as a per-subscriber, org-shared view.**
- **The migration path** from today's single shared Forensic account (360999005254) to
  per-subscriber vended accounts (how the current single-tenant deployment maps forward
  without a rebuild).
Then move RD-028 Proposed → Ratified (accountable-party sign-off) + reconcile candidate
control mappings with the EXISTING Ratified RD-028 / Story T.1 row in `docs/COMPLIANCE.md`.

# NON-NEGOTIABLE CONSTRAINTS
- DOC-ONLY. The only new file is `docs/architecture/MULTI_TENANCY.md` (+ the RD-028
  ratification edit + any COMPLIANCE reconciliation + the status/handoff docs). NO code, NO
  Lambda, NO CDK, NO schema, NO test, NO live AWS.
- DOCUMENT, DON'T RE-DECIDE. RD-028 is settled; write it up. A genuine NEW sub-decision needs
  its OWN new RD (next free number after RD-040 — VERIFY with `grep -oE "RD-0[0-9][0-9]"
  PROJECT_PLAN.md | sort -u | tail`; add its plan-table row BEFORE referencing the number —
  CHECK E is literal). Do NOT mutate RD-028's meaning.
- OUT OF SCOPE: any provisioning/deprovisioning automation (T.2), Hub-side data-partitioning
  implementation (T.3), any per-user isolation. This is architecture, not build.
- RATIFICATION IS THE ACCOUNTABLE PARTY'S CALL (RD-014). The executor DRAFTS + proposes; the
  stakeholder (repo owner) ratifies. Do not self-ratify.
- NO LIVE GATE — validated by stakeholder REVIEW. Do NOT fabricate a live pass; record the
  review acceptance.
- DOCS FIRST-CLASS (RD-015): PR-reviewed; PROJECT_PLAN ↔ RUNBOOK aligned; the new doc is a
  durable management artifact.

# OPERATIONAL CONTEXT
  Build sandbox is INTEGRATIONS_ONLY (NO AWS creds; PyPI + npm BLOCKED). For T.1 that does NOT
  matter — there is nothing to deploy or run live. Doc checks run offline:
  `python3 scripts/check_docs.py` (expect PASS) and
  `~/.pyenv/versions/3.12.13/bin/python3 -m unittest scripts.test_check_docs` (expect SUITE
  OK — pytest is NOT installed, use `unittest`). There is no ruff/tsc/contract bar for a
  doc-only story. Do NOT hand-edit status into README / on-deck / BUILD_ORDER — update the
  RUNBOOK master table ONLY (CHECK H verifies the generated blocks agree).

# HARD-WON LESSONS (do NOT repeat) — from the 3.5 build + validation (2026-09-13)
- **Sequencing (the reason THIS story is next):** deps-✅ = eligible, not next. The story to
  start is the first OPEN "Ready now" item in tier order (§5.A.0). After 3.5 closed Phase 3,
  that is T.1 (tier 5), not the higher-tier pipe story 4.1. The prompts were updated to defer
  to the RUNBOOK schedule; heed CHECK J (the non-blocking on-deck-vs-schedule advisory) and
  the WORK_LOG reorder rather than asserting "next."
- **check_docs timing (RD-015):** run `check_docs.py` only AFTER committing the status/register
  edit (CHECK B baseline is `git show HEAD:RUNBOOK.md`). Flip T.1's status in the RUNBOOK
  master table only.
- **CHECK I (broken-link):** the on-deck README currently points at THIS brief + prompt (they
  exist). When you flip T.1 ✅ and repoint the on-deck starter to the next Ready item, author
  that story's handoff FIRST (or point at an existing doc) or CHECK I fails.
- **CHECK E is literal:** RD-028 already exists (ratifying needs no new number). Only if a NEW
  sub-decision arises, add its plan-table row before naming the number anywhere.
- **`docs/COMPLIANCE.md` already has a Ratified RD-028 / Story T.1 row** — reconcile with it
  (cite it, keep it consistent); do NOT add a duplicate row.
- **Stale-branch trap:** cut T.1's branch from the LATEST `main` (after the 3.5-closure +
  T.1-reorder docs land). If you branch early, `git merge origin/main` + commit BEFORE
  running check_docs.
- **Two-tab / CloudShell / awscurl / Nova Pro machinery does NOT apply to T.1** — it is
  doc-only. Ignore the deploy-gap + live-run gotchas from the pipe-story prompts.

# STEP 0 — RE-ESTABLISH TRUE STATE
- `git fetch origin`; `git checkout main`; `git reset --hard origin/main`. List open PRs.
- `python3 scripts/check_docs.py` → PASS. `python3 -m unittest scripts.test_check_docs` →
  SUITE OK.
- Confirm on `main`: this story = T.1 = ⬜, tenancy track, build tier 5, Depends-on `2.3` ✅;
  Validation Debt Register EMPTY (no armed gate); RD-028 present (PROPOSED) in PROJECT_PLAN.
- **Sequence check (METHODOLOGY §5.A.0):** confirm T.1 is the **first OPEN item in the RUNBOOK
  "Ready now" schedule** in tier order (expect T.1 tier 5 first, per the 2026-09-13 WORK_LOG
  reorder). If an earlier OPEN Ready item shows, STOP + surface it.
- `docs/architecture/` does not exist yet — you will create it with `MULTI_TENANCY.md`.
- Branch off `main`. Suggested branch name: `docs/story-T.1-multitenancy`.

# DEFINITION OF DONE — a REVIEW GATE (no live run)
1. `docs/architecture/MULTI_TENANCY.md` exists + PR-reviewed, capturing BOTH boundaries +
   rationale + rejected alternatives + the subscriber-id model + Hub partitioning + the
   Phase-4 per-subscriber dashboard view + the migration path from the single shared Forensic
   account.
2. RD-028 moved Proposed → Ratified (accountable party, dated + attributed); COMPLIANCE row
   reconciled (no duplicate).
3. T.2 + T.3 scoped from the doc (a short forward note is enough).
4. PLAN ↔ RUNBOOK aligned; `check_docs` PASS + `test_check_docs` OK after committing status.
- Goes ✅ ONLY on the recorded STAKEHOLDER REVIEW acceptance (no live gate). No acceptance →
  stays ⬜/🟡; revise + re-review.

# WORKING AGREEMENT
- One story to completion: draft the doc → stakeholder reviews → RECORD acceptance + flip
  status → paired commit; push to a branch; open a PR via
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls` (`gh pr create` is BROKEN).
- Validation (here = review) drives status; do not self-ratify RD-028 or self-certify T.1.
- MANAGEMENT ARTIFACTS FIRST-CLASS (RD-015): the new architecture doc + brief + RUNBOOK +
  PROJECT_PLAN aligned; RD-028 ratified; run doc checks AFTER committing.
- At session end, repoint the on-deck pointer + author the NEXT story's handoff — read the
  next story off the RUNBOOK "Ready now" schedule (first OPEN item; likely B.1 tier 6, then
  the pipe story 4.1) — do NOT assert 4.1 as next.
- If blocked, push partial progress + a draft PR; surface the blocker; never silently fail.
