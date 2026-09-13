# Story 3.5 (verdict derivation — PASS / FAIL / INCONCLUSIVE)

You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting. Do NOT change anything until you have (a) READ the plan +
runbook + methodology + this story's brief (`session-briefs/story-3.5-brief.md`) + the
Phase-3 design record (`docs/proposals/phase3-three-score-model.md`), (b) re-established
true state (STEP 0), and (c) confirmed the Validation Debt Register + advancement gate.

# PROJECT IDENTITY
ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted artifact
BEFORE it reaches the PDE. Validation-gated: nothing is ✅ until a recorded live pass (the
covenant). Three accounts: Pipeline-Hub (641628980935) = brains/control plane + durable
record + Bedrock; Forensic (360999005254) = self-contained blast zone; Pipeline-Sandbox
(586917955591) = ZTIE→PDE handoff.

# WHERE THIS STORY SITS — BUILD TIER 12, ADVANCING FROM TIER 11 (WITHIN P3); CLOSES PHASE 3
Story 3.5 is **build tier 12**; this session **ADVANCES tier 11 → 12** (its tier-11
dependency `3.4` goes ✅, a new dependency layer opens). A tier move WITHIN Phase 3 (no
phase transition) — but **3.5 CLOSES Phase 3** and unblocks all of Phase 4. STEP 0 must
re-confirm the ENTIRE tier-≤11 set is ✅ (`3.4` AND its inputs `3.3` + `3.2`).

# PRIOR-SESSION UPDATE (2026-09-13, after the Story 3.4 session)
Current true state on `main` once 3.4 is merged + validated (STEP 0 RE-VERIFIES — trust
`main` + `check_docs`; if they disagree, `main` wins):
- **Story 3.4 is expected ✅** (RD-039, detailed findings + prioritized remediations; PURE
  Hub-side, no model call). It was built + offline-proven on `feature/story-3.4` and then
  LIVE-validated (see `story-3.4-LIVE-RUNBOOK.md`). **If `main` shows 3.4 still 🟡, 3.5 MAY
  NOT begin — the only permitted work is validating/reworking 3.4** (its live pass).
- **The 3.4 live run doubled as the OD-001/OD-002 post-cleanup regression proof.** If it
  passed, the full pipeline (intake→lanes→3.1→3.2→3.3→3.4) is confirmed green after the
  ~20-stack cleanup. The live ZTIE pipeline stacks were kept + untouched — Forensic:
  `ZtieForensicInfraStack` (+ detonation VPC `vpc-0457ce09693cc48e4`), `ZtieDetonationStack`,
  `ZtieStaticScanStack`, `ZtieOrchestrationStack`, `ZtieIntakeStack`, `CDKToolkit`; Hub:
  `ZtieHubTrackingStack`, `CDKToolkit`, `ztie-asymmetric-cmk`; all `PDE-*`/`pde-*`. **Your
  3.5 live run is another end-to-end pass** — treat an infra-shaped failure (missing
  role/bucket/VPC endpoint/export) as possible cleanup fallout, not automatically a 3.5 bug.
- **Design watch-item (NOT 3.5 scope, be aware):** do not add COMPLIANCE-mode 365-day S3
  Object Lock to any bucket (the stakeholder does not want WORM on ZTIE forensic data).

# ⚠️ ADVANCEMENT GATE — CHECK THIS FIRST
NEW FEATURE story. It may begin ONLY if its Depends-on are ALL ✅ AND the Validation Debt
Register is EMPTY. **3.5 depends on 3.4 ✅.** STEP 0 MUST re-confirm on `main`: `3.4` ✅ and
the register EMPTY (trust `main` + `check_docs`; if they disagree, `main` wins). **If `main`
shows 3.4 back at 🟡, 3.5 MAY NOT begin.** `check_docs` CHECK B, machine-enforced.
Depends-on: **3.4 ✅**. Build tier 12.

# WHAT 3.5 IS — READ THIS (it is the FIRST verdict-bearing story)
Everything in Phase 3 so far is EVIDENCE-ONLY, verdict-free BY CONTRACT (3.1 combined event,
3.2 correlation, 3.3 three scores, 3.4 findings + remediations — each enforced verdict-free
by a recursive no-verdict scan). **Story 3.5 is where the accumulated evidence becomes a
RECOMMENDED VERDICT (PASS / FAIL / INCONCLUSIVE).** This is a boundary shift: 3.5's contract
is the ONE that legitimately introduces the verdict vocabulary. But per **RD-040 (stakeholder
ruling, 2026-09-13)** the recommendation is **ADVISORY and NEVER acted upon** — a HUMAN must
ACTIVELY select PASS or FAIL on the dashboard, and only that human selection is enforced
(Phase-4 routing). 3.5 RECOMMENDS; the human DECIDES + ACTS. RD-003 + the human-gate covenant
intact.

# THE SCOPE IS DECIDED — RD-040 (do NOT re-open it)
The stakeholder has RATIFIED the following (registered as RD-040 in PROJECT_PLAN). Implement
EXACTLY this; do not re-litigate or invent alternatives:
- **Advisory `recommended_verdict`, NEVER acted upon.** Nothing in ZTIE routes/promotes/
  destroys/moves an artifact on it. A human actively selects PASS/FAIL on the dashboard; that
  human selection is the only thing enforced. 3.5 writes ONLY `recommended_verdict` +
  `recommendation_basis` + `human_decision: pending`; it NEVER writes the human's actual
  selection (a separate human-owned field, Phase 4). Name the field `recommended_verdict`
  (NOT a bare `verdict`) so nothing downstream mistakes it for the effective decision.
- **PURE + deterministic, NO model call** (like 3.4): no Bedrock client, no Bedrock grant.
- **Driver = the `combined` score. Do NOT re-aggregate the three lane scores** (the
  `combined` score is RD-038's own whole-picture number; re-blending static/dynamic/combined
  would reintroduce the RD-038 arithmetic-over-scores anti-pattern one layer down). Static +
  dynamic are shown as context in the basis, not blended into a new number.
- **Cut lines (shared 0-100 rubric, higher = riskier):** `combined <= 29` → recommend
  **PASS**; `combined 30-74` → recommend **INCONCLUSIVE**; `combined >= 75` → recommend
  **FAIL**.
- **Force INCONCLUSIVE regardless of score** if ANY of: a `contradiction` finding present,
  OR the evidence is incomplete (a `coverage` gap / `combined_complete=false` / a partial
  `scoring_result` — any lane `model_error`/`unparseable`/`skipped_no_evidence` / `combined`
  not `scored` / `remediation_result.status != assessed`). A high-severity gap →
  INCONCLUSIVE (human look), NEVER an auto-FAIL. FAIL is reserved for a genuinely high
  `combined` score.

# THE JOB
For one `intake_id` with a `remediation_result` (3.4) sitting over a `scoring_result` (3.3,
three 0-100 risk scores) + the 3.2 findings/gaps, derive + record on the Hub tracking item a
bounded, DERIVED record (`verdict.contract.v1`, own pin `VERDICT_CONTRACT_VERSION`) carrying:
- `recommended_verdict` ∈ {PASS, FAIL, INCONCLUSIVE} per the RD-040 mapping above,
- `recommendation_basis` (the `combined` score value + which override, if any, fired),
- `human_decision: pending` (the human's actual selection is written LATER, by Phase 4 — NOT
  by 3.5),
- completeness caveats.
Read the authoritative scores from `scoring_result`; read the gaps / `status` (for the
INCONCLUSIVE overrides) from `remediation_result` (and `combined_complete`).

# CONTRACT-FIRST (schema per RD-040)
Define the `verdict.contract.v1` schema FIRST (bounded, allow-list, own version pin). It is
the ONE Phase-3 contract that carries a verdict-shaped field — and it carries it as
`recommended_verdict` (advisory), plus `human_decision: pending`, NEVER an effective verdict.
Idempotent / stream-loop-guarded: reuse the 3.1→3.4 `Decimal`-canonicalized fingerprint over
the inputs the recommendation is derived from (the score blocks + the findings/gaps).

# NON-NEGOTIABLE CONSTRAINTS
- DERIVE the advisory recommendation; do not re-score/re-correlate/re-normalize/rebuild
  findings (those are 3.3/3.2/3.1/3.4, all done); do NOT re-aggregate the three scores.
- ADVISORY, NEVER ACTED UPON (RD-040). The record triggers NO automated action; a human must
  actively select PASS/FAIL on the dashboard. 3.5 never writes the human's selection.
- PARTIAL / INCOMPLETE EVIDENCE → INCONCLUSIVE (per the RD-040 overrides). Never fabricate a
  PASS or FAIL over incomplete evidence.
- BOUNDED IN + BOUNDED OUT; allow-list; integrity-keyed by intake_id + sha256. RD-009/RD-013
  intact (reason only over derived Hub-side data — the scores + findings; no raw data, no
  Forensic durable store).
- PURE LOGIC + THIN SEAM, NO Bedrock (RD-040). Same skeleton as 3.4 (`lambdas/hub_verdict/`
  or similar): a new gen_<name>_contract.py registered in gen_contracts.py, pure logic +
  DynamoDB-only awsio seam + stream handler.
- ⚠️ FIRST VERDICT-BEARING CONTRACT: the existing recursive no-verdict scans protect the
  3.1–3.4 records (they must STAY verdict-free — do NOT relax them, do NOT write a verdict
  onto `scoring_result`/`remediation_result`). 3.5's OWN new contract carries
  `recommended_verdict`; add 3.5's own tests for that advisory vocabulary (and a test that
  it never emits an effective/acted-upon verdict field).
- VALIDATION-GATED: 3.5 flips ✅ only on a recorded LIVE pass of the FINAL code.
- DOCS FIRST-CLASS (RD-015): PR-reviewed; PROJECT_PLAN ↔ RUNBOOK aligned.

# REGISTERED DECISION — RD-040 IS ALREADY RECORDED
**RD-040 is already in PROJECT_PLAN (recorded 2026-09-13) — you do NOT author a new RD for
the scope/thresholds; you IMPLEMENT RD-040.** (If the build surfaces a genuinely new
sub-decision beyond RD-040's scope, THEN register the next free RD — `grep -oE "RD-0[0-9][0-9]"
PROJECT_PLAN.md | sort -u | tail`, expect RD-041, VERIFY; CHECK E is literal — add its
plan-table row BEFORE referencing the number in any living doc.)

# OPERATIONAL CONTEXT (state on EVERY command block)
  Build sandbox is INTEGRATIONS_ONLY (NO AWS creds; PyPI + npm BLOCKED — boto3/pytest/moto/
  jsonschema/aws-cdk-lib NOT installable). You BUILD; the USER validates live. Region
  us-east-1; `aws sts get-caller-identity` before EVERY operational block. Tracking table +
  (if used) Bedrock = HUB. If 3.5 is PURE (recommended) there is NO Bedrock prerequisite.
  Tests with `~/.pyenv/versions/3.12.13/bin/python3 -m unittest` (pytest is NOT installed —
  use `unittest`, NOT pytest); `ruff` at `~/.pyenv/versions/3.12.13/bin/ruff` (DEFAULT rules
  — watch RUF046 `int(round(x))` → use `round(x)`; RUF059 unused unpacked var → prefix `_`;
  ISC004 implicit string concat; blind `except Exception` that does not re-raise needs
  `# noqa: BLE001`). `prettier`/`tsc` need `env -u NODE_OPTIONS`; npm BLOCKED so
  `tsc --noEmit` shows ONLY the missing-`aws-cdk-lib` family — the `main` baseline is
  106 errors (TS2304=9, TS2307=49, TS2339=36, TS2353=6, TS2591=6); adding a stack Lambda adds
  ONE `__dirname` TS2304 (an existing type — fine; confirm NO NEW error TYPE). Do NOT
  prettier-reformat generated JSON contracts. Keep tests stdlib-only + boto3-stubbed.

# HARD-WON LESSONS (do NOT repeat) — from the 3.4 build (2026-09-13)
- **The PURE-derived pattern held a 9th time.** 3.4 = a NEW `lambdas/hub_remediate/` Lambda:
  contract-first (`scripts/gen_remediation_contract.py` registered in `gen_contracts.py`,
  byte-identical `schemas/` + lambda copies via `contract_writer`), PURE logic
  (`remediate.py`) + a thin DynamoDB-only `awsio` seam (NO Bedrock — inputs already
  structured), a stream handler with a `Decimal`-canonicalized fingerprint guard, and a
  two-layer conformance test (stdlib walk + `jsonschema` `skipUnless`) + recursive
  no-verdict scan + schema-has-no-verdict-property. **Reuse this exact skeleton for 3.5** —
  EXCEPT 3.5's own contract intentionally carries a `verdict` (so its schema-no-verdict test
  is inverted for its OWN record; keep the 3.1–3.4 no-verdict scans intact for THEIR records).
- **3.4's inputs were structured → PURE (no model call).** 3.5's inputs are the three scores
  + the findings/gaps → a deterministic PASS/FAIL/INCONCLUSIVE mapping. **Prefer PURE**; a
  model DECIDING the verdict is exactly what the human gate exists to avoid.
- **`remediation_result` (RD-039) shape 3.5 consumes:** top-level `status`
  (`assessed`/`no_scores`/`skipped_no_evidence`) + `assessment`{`scores`(the three 3.3 scores
  echoed + `highest_score`/`highest_score_kind`), `counts`, `detailed_findings[]`,
  `candidate_false_positives[]`, `gaps[]`, `prioritized_remediations[]`}. Read the
  authoritative scores from `scoring_result` + the `gaps`/`status` for the INCONCLUSIVE
  signals (a `coverage` gap or `status != assessed` → INCONCLUSIVE).
- **Tolerate partial evidence → INCONCLUSIVE.** 3.4 ranked over whichever scores were present
  + marked `no_scores`/`skipped_no_evidence` honestly; 3.5 turns that incompleteness into
  INCONCLUSIVE, never a fabricated PASS/FAIL.
- **check_docs fixture:** `scripts/test_check_docs.py` `_NEW_WORK_STORY` is now **3.5**.
  **When 3.5 leaves ⬜, repoint it to the next still-⬜ feature story (4.1) IN THE SAME PR**,
  then re-run `python3 -m unittest scripts.test_check_docs` (SUITE line OK).
- **check_docs CHECK I (links) bites the handoff:** if a LIVING doc (e.g. the on-deck README)
  links a not-yet-authored file (the 4.1 brief/prompt), CHECK I FAILS until that file exists.
  Author the 4.1 handoff files BEFORE pointing the on-deck README at them (or point at the
  3.5 LIVE-RUNBOOK you create this session). This bit the 3.4 session.
- **check_docs timing (RD-015):** run `check_docs.py` only AFTER committing status/register
  edits (CHECK B baseline is `git show HEAD:RUNBOOK.md`). Set 3.5 🟡 AND add it to the
  register in the SAME commit. **CHECK E is literal** — RD-040 is already defined in
  PROJECT_PLAN, so referencing it is fine; if you register any NEW RD (RD-041+), add its
  plan-table row BEFORE referencing the number anywhere.
- **`test_check_docs` reflects the live tree:** it FAILS while `check_docs` has ANY real
  violation in the working tree. Fix the `check_docs` violation FIRST — a mid-edit FAIL is
  usually your own uncommitted violation.
- **Deploy-gap (both modes):** 3.5 touches `ZtieHubTrackingStack` — redeploy from the RIGHT
  branch; BEFORE deploy grep the stack source for the new marker; AFTER deploy inspect the
  LIVE Lambda env + role. When a call "succeeds" but produces no result, READ THE LAMBDA'S
  OWN LOGS (custom OD-003 log group — tail `LoggingConfig.LogGroup`, not `/aws/lambda/<fn>`).
- **Live-run gotchas (from 3.2/3.3/3.4):** intake endpoint query returns TWO outputs — pin
  one with `[?contains(OutputValue,'/intake')].OutputValue | [0]`; use a ROUTABLE artifact
  (a small CloudFormation template, not `/etc/hostname`) so both lanes run + all Phase-3
  stages land; reads are eventually-consistent (re-read after a moment); `awscurl` SigV4 with
  URL LAST + `-d @file.json`.
- **Two accounts, two tabs:** `sts get-caller-identity` before every block; the table = HUB.
  `gh pr create` is BROKEN — open PRs via `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`.

# STEP 0 — RE-ESTABLISH TRUE STATE
- `git fetch origin`; `git checkout main`; `git reset --hard origin/main`. List open PRs.
- `python3 scripts/check_docs.py` → PASS. `python3 -m unittest scripts.test_check_docs` →
  SUITE OK.
- Confirm: this story = 3.5 = ⬜, build tier 12, Depends-on `3.4`; tier 11 → 12 (WITHIN P3,
  CLOSES Phase 3); EVERY tier-≤11 dep ✅ (`3.4` + `3.3` + `3.2`); register EMPTY + `3.4` ✅
  (if not, STOP — clear the open entry, i.e. 3.4's live pass). **RD-040 is ALREADY recorded
  (scope + thresholds ratified 2026-09-13) — do NOT re-open it; IMPLEMENT it.** Confirm RD-040
  is present in PROJECT_PLAN before coding the mapping.
- Branch off `main`. Branch name: `feature/story-3.5`.

# DEFINITION OF DONE — a PASS/FAIL GATE
1. For one `intake_id`, a bounded record carrying an ADVISORY `recommended_verdict`
   (PASS/FAIL/INCONCLUSIVE per the RD-040 `combined`-driven mapping) + `recommendation_basis`
   + `human_decision: pending`, recorded on the Hub tracking item.
2. Derived per RD-040 (driver = `combined`; ≤29 PASS / 30-74 INCONCLUSIVE / ≥75 FAIL;
   contradiction + any incompleteness → force INCONCLUSIVE; high-severity gap → INCONCLUSIVE
   not auto-FAIL); the three scores are NOT re-aggregated; PARTIAL/incomplete evidence yields
   INCONCLUSIVE honestly (never a fabricated PASS/FAIL).
3. ADVISORY, NEVER acted upon — the record triggers no automated action; a human selects
   PASS/FAIL on the dashboard; 3.5 never writes the human's selection. RD-009/RD-013 intact;
   the 3.1–3.4 records stay verdict-free (their no-verdict scans intact).
4. Validated LIVE and RECORDED (another end-to-end pipeline pass). Record in the Validation
   Result the recommended verdict + its basis for the test intake (ideally show PASS on a
   low-`combined` intake, and an INCONCLUSIVE override on a contradiction/incomplete intake).
- Goes ✅ ONLY on a recorded live pass of the FINAL code. No pass → stays 🟡 (+ register).
  **On pass, Phase 3 CLOSES** and Phase 4 (4.1 next) unblocks.

# WORKING AGREEMENT
- One story to completion: design → build → validate → RECORD + flip status → paired commit;
  push to a branch; open a PR via `gh api …/pulls`. After merge, `git log
  main..feature/story-3.5`.
- Validation drives status; the advancement gate governs advancement.
- MANAGEMENT ARTIFACTS FIRST-CLASS (RD-015): brief + RUNBOOK + PROJECT_PLAN aligned; RD-040
  is already recorded (implement it, do not re-open); repoint `_NEW_WORK_STORY` off 3.5
  (→ 4.1); re-run doc checks AFTER committing.
- Author a 3.5 LIVE-RUNBOOK for the stakeholder's real validation.
- At session end, author the next story's brief + prompt (4.1 status-retrieval orchestrator)
  with this session's real Lessons Learned.
- If blocked (incl. by the 3.4 gate), push partial progress + a draft PR; surface the
  blocker; never silently fail.
