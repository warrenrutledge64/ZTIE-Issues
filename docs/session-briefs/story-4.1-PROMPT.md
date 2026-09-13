# Story 4.1 (status-retrieval orchestrator — OPENS Phase 4)

You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting. Do NOT change anything until you have (a) READ the plan +
runbook + methodology + this story's brief (`session-briefs/story-4.1-brief.md`), (b)
re-established true state (STEP 0), and (c) confirmed the Validation Debt Register + the
advancement gate.

# PROJECT IDENTITY
ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted artifact
BEFORE it reaches the PDE. Validation-gated: nothing is ✅ until a recorded live pass (the
covenant). Three accounts: Pipeline-Hub (641628980935) = brains/control plane + durable
record + Bedrock; Forensic (360999005254) = self-contained blast zone; Pipeline-Sandbox
(586917955591) = ZTIE→PDE handoff.

# WHERE THIS STORY SITS — BUILD TIER 13, ADVANCING TIER 12 → 13 AND P3 → P4 (OPENS PHASE 4)
Story 4.1 is **build tier 13**; this session **ADVANCES tier 12 → 13** (its tier-12
dependency `3.5` goes ✅, a new dependency layer opens) AND is the **P3 → P4 phase
transition** — 4.1 OPENS Phase 4 (Reporting & Handoff). Name both at handoff (tier 12→13
AND P3→P4). STEP 0 must re-confirm the ENTIRE tier-≤12 set is ✅ (`3.5` AND its Phase-3
inputs `3.4` + `3.3` + `3.2` + `3.1`) and that the P3 end-of-phase gate is satisfied.

⚠️ SEQUENCING — 4.1 IS THE NEXT *PIPE* STORY, BUT NOT NECESSARILY THE NEXT STORY. The
story to START is the **first OPEN item in the RUNBOOK "Ready now" schedule, in tier
order** (METHODOLOGY §5.A.0) — verified live in STEP 0, the RUNBOOK is the source of
truth, NOT this narrative. As of authoring, lower-tier Ready items are OPEN ahead of 4.1
(tier 13) — notably **T.1** (tier 5, multi-tenancy design spike, doc-only, "should land
before Phase 4"), with the stakeholder-recorded reorder in `docs/governance/WORK_LOG.md`
putting **T.1 before 4.1**. So do NOT begin 4.1 until STEP 0 confirms it is genuinely the
first OPEN Ready-now item (i.e. T.1 and any other earlier Ready item are ✅/closed or an
explicit WORK_LOG reorder puts 4.1 first). If the RUNBOOK still lists an earlier OPEN
Ready item, STOP and work that instead (or get the reorder logged) — 4.1 being the
highest-tier just-unblocked pipe story does not make it next.

# PRIOR-SESSION UPDATE (2026-09-13, after the Story 3.5 session)
Current true state on `main` once 3.5 is merged + validated (STEP 0 RE-VERIFIES — trust
`main` + `check_docs`; if they disagree, `main` wins):
- **Story 3.5 is expected ✅** (RD-040, advisory `recommended_verdict`; PURE Hub-side, no
  model call). It was built + offline-proven on `feature/story-3.5` and then LIVE-validated
  (see `story-3.5-LIVE-RUNBOOK.md`). **If `main` shows 3.5 still 🟡, 4.1 MAY NOT begin —
  the only permitted work is validating/reworking 3.5** (its live pass).
- **3.5 is the FIRST + ONLY verdict-bearing record.** Its `verdict_result` carries an ADVISORY
  `recommended_verdict` (PASS / FAIL / INCONCLUSIVE) + `human_decision: pending` and is NEVER
  acted upon (RD-040). The 3.1-3.4 records stay verdict-free. 4.1 must PRESERVE this: surface
  the recommended_verdict as an advisory recommendation + the human_decision; never present or
  persist it as an effective/enforced decision, and never write a verdict onto any other
  record.
- **Design watch-item (NOT 4.1 scope, be aware):** do not add COMPLIANCE-mode 365-day S3
  Object Lock to any bucket (the stakeholder does not want WORM on ZTIE forensic data).

# ⚠️ ADVANCEMENT GATE — CHECK THIS FIRST
NEW FEATURE story. It may begin ONLY if its Depends-on are ALL ✅ AND the Validation Debt
Register is EMPTY. **4.1 depends on 3.5 ✅.** STEP 0 MUST re-confirm on `main`: `3.5` ✅ and
the register EMPTY (trust `main` + `check_docs`; if they disagree, `main` wins). **If `main`
shows 3.5 back at 🟡, 4.1 MAY NOT begin.** `check_docs` CHECK B, machine-enforced.
Depends-on: **3.5 ✅**. Build tier 13.

# WHAT 4.1 IS — READ THIS (the Phase-4 opener)
Phase 3 produced the full per-intake assessment on the Hub tracking item: `combined_event`
(3.1) → `correlation_result` (3.2) → `scoring_result` (3.3, three 0-100 scores) →
`remediation_result` (3.4, findings + remediations) → `verdict_result` (3.5, advisory
`recommended_verdict` + `human_decision: pending`). **Story 4.1 is the status-retrieval
orchestrator: the READ/transform step that assembles the per-intake STATUS read-model** the
rest of Phase 4 consumes (4.2 dashboard JSON, 4.5 report, and via those the human gate +
routing 4.4/4.6/4.7). It does NOT re-derive any assessment, does NOT make a model call, and
does NOT enforce anything.

# THE JOB
For one `intake_id` with the full Phase-3 record on the Hub tracking item, assemble a
bounded, DERIVED per-intake STATUS read-model:
- intake identity + per-stage presence/status (which of 3.1-3.5 have landed),
- the three 3.3 risk scores + the 3.4 findings/remediations,
- the 3.5 advisory `recommended_verdict` + `human_decision` (clearly labelled ADVISORY,
  never presented as enforced),
in the shape the Phase-4 dashboard payload (4.2) + per-execution report (4.5) consume.
**Confirm the exact output shape + boundary with the stakeholder before building.**

# CONTRACT-FIRST DECISION (make + justify; register a new RD only if a genuine sub-decision)
Decide + justify CONTRACT-FIRST: (a) whether 4.1's output is a NEW durable Hub-side field +
contract (own version pin, allow-list, integrity-keyed — reuse the 1.2→3.5 skeleton) OR an
on-demand READ transform behind an orchestrator/API (pure logic + thin seam, no new durable
field); (b) if it hangs off the tracking-table stream, reuse the 3.1→3.5 idempotency guard
(a `Decimal`-canonicalized fingerprint over the inputs). **Prefer the minimal option that
serves 4.2/4.5** — do not add a durable field if a read transform suffices. **The exact 4.1
output shape is a STAKEHOLDER decision — confirm + record it.** RD-040 is 3.5's; only author
a NEW RD (next free number after RD-040 — VERIFY with `grep -oE "RD-0[0-9][0-9]"
PROJECT_PLAN.md | sort -u | tail`) if 4.1 introduces a genuine new design decision. **CHECK E
is literal** — add any new RD's plan-table row BEFORE referring to that number in a living doc.

# NON-NEGOTIABLE CONSTRAINTS
- READ/transform only; do not re-normalize/re-correlate/re-score/rebuild findings/re-derive
  the verdict (those are 3.1-3.5, all done). No model call.
- THE 3.5 VERDICT STAYS ADVISORY + HUMAN-GATED (RD-040). 4.1 surfaces `recommended_verdict`
  as a recommendation + the `human_decision: pending`; it NEVER promotes/routes/enforces, and
  the enforcing accept/reject + routing are downstream (4.4/4.6/4.7).
- KEEP THE 3.1-3.4 RECORDS VERDICT-FREE + 3.5's ADVISORY-ONLY INVARIANTS. Do NOT write a
  verdict onto any other record; do NOT relax the existing no-verdict scans; if 4.1 echoes
  the recommended_verdict into a consolidated view, label it advisory + carry human_decision.
- BOUNDED IN + BOUNDED OUT; allow-list; if durable, integrity-keyed by intake_id + sha256.
  RD-009/RD-013 intact (reason only over derived Hub-side data; no raw data, no Forensic
  durable store).
- PURE LOGIC + THIN SEAM (the proven 1.2→…→3.5 pattern). AWS-native orchestration only (no
  GitHub Actions for operations).
- VALIDATION-GATED: 4.1 flips ✅ only on a recorded LIVE pass of the FINAL code.
- DOCS FIRST-CLASS (RD-015): PR-reviewed; PROJECT_PLAN ↔ RUNBOOK aligned.

# OPERATIONAL CONTEXT (state on EVERY command block)
  Build sandbox is INTEGRATIONS_ONLY (NO AWS creds; PyPI + npm BLOCKED — boto3/pytest/moto/
  jsonschema/aws-cdk-lib NOT installable). You BUILD; the USER validates live. Region
  us-east-1; `aws sts get-caller-identity` before EVERY operational block. Tracking table =
  HUB. If 4.1 is PURE (recommended) there is NO Bedrock prerequisite. Tests with
  `~/.pyenv/versions/3.12.13/bin/python3 -m unittest` (pytest is NOT installed — use
  `unittest`, NOT pytest); `ruff` at `~/.pyenv/versions/3.12.13/bin/ruff` (DEFAULT rules — a
  generator script needs `chmod +x` or EXE001 fires; a walrus bound to an unused var trips
  F841; watch RUF046 `int(round(x))`→`round(x)`, RUF059 unused unpacked var→prefix `_`,
  ISC004, blind `except Exception` needs `# noqa: BLE001`). `prettier`/`tsc` need
  `env -u NODE_OPTIONS`; npm BLOCKED so `tsc --noEmit` shows ONLY the missing-`aws-cdk-lib`
  family — the `main` baseline is 106 errors (TS2304=9, TS2307=49, TS2339=36, TS2353=6,
  TS2591=6); adding a stack Lambda adds `__dirname` TS2304 (an existing type — fine; confirm
  NO NEW error TYPE). Do NOT prettier-reformat generated JSON contracts. Keep tests
  stdlib-only + boto3-stubbed.

# HARD-WON LESSONS (do NOT repeat) — from the 3.5 build (2026-09-13)
- **The PURE-derived pattern held a 10th time.** 3.5 = a NEW `lambdas/hub_verdict/` Lambda:
  contract-first (`scripts/gen_verdict_contract.py` registered in `gen_contracts.py`,
  byte-identical `schemas/` + lambda copies via `contract_writer`), PURE logic (`verdict.py`)
  + a thin DynamoDB-only `awsio` seam (NO Bedrock — the mapping is deterministic), a stream
  handler with a `Decimal`-canonicalized fingerprint guard, and a two-layer conformance test
  (stdlib walk + `jsonschema` `skipUnless`). **Reuse this skeleton if 4.1 produces a durable
  Hub-side field; if 4.1 is a pure read transform, keep the pure-logic + thin-seam split.**
- **Field ownership pattern:** each Phase-3 Lambda writes its OWN distinct integrity-bound
  field (3.1 `combined_event`, 3.2 `correlation_result`, 3.3 `scoring_result`, 3.4
  `remediation_result`, 3.5 `verdict_result`/`verdict_at`). If 4.1 writes anything durable,
  give it its OWN field; never overwrite another stage's.
- **`verdict_result` (RD-040) shape 4.1 consumes:** top-level `contract_version`/`intake_id`/
  `sha256`/`recommended_at`/`status` (`recommended`/`incomplete`/`no_scores`)/
  `recommended_verdict` (PASS/FAIL/INCONCLUSIVE)/`human_decision` (always `pending`) +
  optional `rubric_version`/`status_detail`/`recommendation_basis`{`driver`,`combined_score`,
  `scores` echoes, `contradiction_present`, `evidence_complete`, `override_reasons`,
  `summary`}. Full record also has `combined_event`/`correlation_result`/`scoring_result`/
  `remediation_result`.
- **Advisory, never enforced (RD-040).** 4.1 must surface the recommended_verdict as a
  recommendation + `human_decision`; it must NOT route/act. The human PASS/FAIL selection is
  4.4/4.6/4.7.
- **check_docs fixture:** `scripts/test_check_docs.py` `_NEW_WORK_STORY` is now **4.1**.
  **When 4.1 leaves ⬜, repoint it to the next still-⬜ feature story (4.2) IN THE SAME PR**,
  then re-run `python3 -m unittest scripts.test_check_docs` (SUITE line OK).
- **check_docs CHECK I (links) bites the handoff:** if a LIVING doc (the on-deck README)
  links a not-yet-authored file, CHECK I FAILS until that file exists. Author the next-story
  handoff files BEFORE pointing the on-deck README at them (or point at the 4.1 LIVE-RUNBOOK
  you create this session).
- **check_docs timing (RD-015):** run `check_docs.py` only AFTER committing status/register
  edits (CHECK B baseline is `git show HEAD:RUNBOOK.md`). Set 4.1 🟡 AND add it to the
  register in the SAME commit.
- **`test_check_docs` reflects the live tree:** it FAILS while `check_docs` has ANY real
  violation in the working tree. Fix the `check_docs` violation FIRST.
- **Stale-branch trap (bit the 3.5 session):** `feature/story-3.5` was cut from `main` BEFORE
  RD-040's PR #120 merged, so STEP 0's `git reset --hard origin/main` did not carry RD-040 and
  a `git merge origin/main` reconciliation was needed (conflicts only on the two 3.5 handoff
  files, resolved `--theirs`). **Cut `feature/story-4.1` from the LATEST `main` after 3.5
  merges**, and if you branched early, `git merge origin/main` + commit BEFORE running
  check_docs.
- **Deploy-gap (both modes):** if 4.1 touches `ZtieHubTrackingStack` (or a new stack) —
  redeploy from the RIGHT branch; BEFORE deploy grep the stack source for the new marker;
  AFTER deploy inspect the LIVE resource. Custom OD-003 log groups — tail
  `LoggingConfig.LogGroup`, not `/aws/lambda/<fn>`.
- **Live-run gotchas (from 3.2/3.3/3.4/3.5):** intake endpoint query returns TWO outputs — pin
  one with `[?contains(OutputValue,'/intake')].OutputValue | [0]`; use a ROUTABLE artifact
  (a small CloudFormation template) so all Phase-3 stages land; reads are eventually-consistent;
  `awscurl` SigV4 with URL LAST + `-d @file.json`.
- **Two accounts, two tabs:** `sts get-caller-identity` before every block; the table = HUB.
  `gh pr create` is BROKEN — open PRs via `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`.

# STEP 0 — RE-ESTABLISH TRUE STATE
- `git fetch origin`; `git checkout main`; `git reset --hard origin/main`. List open PRs.
- `python3 scripts/check_docs.py` → PASS. `python3 -m unittest scripts.test_check_docs` →
  SUITE OK.
- Confirm: this story = 4.1 = ⬜, build tier 13, Depends-on `3.5`; tier 12 → 13 AND P3 → P4
  (OPENS Phase 4); EVERY tier-≤12 dep ✅ (`3.5` + `3.4` + `3.3` + `3.2` + `3.1`) + the P3
  phase gate satisfied; register EMPTY + `3.5` ✅ (if not, STOP — clear the open entry, i.e.
  3.5's live pass). CONFIRM the exact 4.1 output shape/boundary with the stakeholder before
  coding.
- **Sequence check (METHODOLOGY §5.A.0) — do this before assuming 4.1 is next.** Read the
  RUNBOOK "Ready now" schedule and confirm 4.1 is the **first OPEN item in tier order**. It
  is NOT if a lower-tier Ready item is still OPEN — notably **T.1** (tier 5, doc-only, should
  land before Phase 4). If an earlier Ready item is still open, STOP and work THAT (or
  confirm a stakeholder reorder is recorded in `docs/governance/WORK_LOG.md` putting 4.1
  first). `check_docs.py` CHECK J flags this mismatch as an advisory — reconcile it, do not
  ignore it. Never self-select 4.1 out of order just because its dependency is ✅.
- Branch off `main`. Branch name: `feature/story-4.1`.

# DEFINITION OF DONE — a PASS/FAIL GATE
1. For one `intake_id` with the full Phase-3 record, 4.1 assembles the bounded per-intake
   status read-model (identity + per-stage status + scores + findings/remediations + the
   advisory recommended_verdict + human_decision) in the shape the Phase-4 consumers use.
2. READ/transform only — no re-derivation, no model call; the recommended_verdict stays
   advisory (never enforced); RD-009/RD-013 intact; the 3.1-3.4 records stay verdict-free and
   3.5's advisory-only invariants intact.
3. Validated LIVE and RECORDED (an end-to-end pipeline pass surfacing the assembled status).
- Goes ✅ ONLY on a recorded live pass of the FINAL code. No pass → stays 🟡 (+ register).

# WORKING AGREEMENT
- One story to completion: design → build → validate → RECORD + flip status → paired commit;
  push to a branch; open a PR via `gh api …/pulls`. After merge, `git log
  main..feature/story-4.1`.
- Validation drives status; the advancement gate governs advancement.
- MANAGEMENT ARTIFACTS FIRST-CLASS (RD-015): brief + RUNBOOK + PROJECT_PLAN aligned; any new
  RD (+ candidate mappings) recorded; repoint `_NEW_WORK_STORY` off 4.1 (→ 4.2); re-run doc
  checks AFTER committing.
- Author a 4.1 LIVE-RUNBOOK for the stakeholder's real validation.
- At session end, author the next Phase-4 story's brief + prompt with this session's real
  Lessons Learned.
- If blocked (incl. by the 3.5 gate), push partial progress + a draft PR; surface the
  blocker; never silently fail.
