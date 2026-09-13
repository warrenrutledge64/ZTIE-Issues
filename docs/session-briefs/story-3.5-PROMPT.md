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
VERDICT (PASS / FAIL / INCONCLUSIVE).** This is a boundary shift: 3.5's contract is the ONE
that legitimately introduces the verdict vocabulary. But the verdict stays HUMAN-GATED —
3.5 derives a RECOMMENDATION that INFORMS the human accept/reject gate on the dashboard
(Phase 4); it does NOT auto-enforce. RD-003 + the human-gate covenant: the model/rules may
CHARACTERIZE + RECOMMEND; the human DECIDES.

# HOW 3.5 SITS WITH 3.1–3.4 (no structural conflict — one thing to watch)
3.5 does NOT conflict with 3.3 or 3.4. Verified on the three ways a conflict could arise:
1. **Field ownership (no write collision).** Each Phase-3 Lambda writes its OWN distinct,
   integrity-bound field and never touches another's: 3.1 → `combined_event`/`combined_at`;
   3.2 → `correlation_result`/`correlation_status`/`correlated_at`; 3.3 → `scoring_result`/
   `scored_at`; 3.4 → `remediation_result`/`assessed_at`. 3.5 → its OWN new field (e.g.
   `verdict_result`/`verdict_at`), same pattern. All hang off the same DynamoDB stream but
   are idempotent + fingerprint-guarded, so adding a fifth consumer does not perturb the
   other four.
2. **Scope (consume, don't re-produce).** 3.5 READS the scores + findings and derives a
   verdict; it never overwrites or re-derives anything 3.1/3.2/3.3/3.4 produced (see the
   "do NOT re-score/re-correlate/re-normalize/rebuild findings" + "do NOT re-aggregate the
   scores" constraints below).
3. **The verdict-free invariant (the ONE real interaction — compatible, not conflicting).**
   3.1–3.4 are all enforced verdict-free by contract. 3.5 is the FIRST record that
   legitimately carries a `verdict` — which is fine AS LONG AS 3.5 introduces it in its OWN
   new contract only and does NOT relax/globalize the 3.1–3.4 scans (see the two ⚠️
   constraints below). This is the one spot where 3.5 mechanically touches the same test
   infrastructure the earlier stories rely on — keep them separate.

# THE JOB
For one `intake_id` with a `remediation_result` (3.4) sitting over a `scoring_result` (3.3,
three 0-100 risk scores) + the 3.2 findings/gaps, derive + record on the Hub tracking item:
- a bounded, DERIVED verdict record: `verdict` ∈ {PASS, FAIL, INCONCLUSIVE} + the basis
  (which scores + findings/gaps drove it) + completeness caveats, framed as ZTIE's
  human-gated RECOMMENDATION.
- **Partial/incomplete evidence → INCONCLUSIVE, honestly** (a partial `scoring_result`, a
  `coverage` gap, or `remediation_result.status != assessed` never becomes a fabricated
  PASS/FAIL).

# CONTRACT-FIRST DECISION (make + justify in the new RD)
Decide + justify CONTRACT-FIRST: (a) the verdict-record schema (bounded, allow-list, own
version pin — this is the ONE Phase-3 contract that carries a `verdict`); (b) whether the
derivation is DETERMINISTIC/PURE (a rules/threshold mapping over the three scores + gap
severities) or a Nova Pro call. **STRONGLY PREFER PURE + deterministic** — a verdict must be
reproducible, explainable, and auditable, the inputs are already structured, and a model
DECIDING the verdict would undercut the "model characterizes, rules/human decide" line. If
PURE, no Bedrock grant (like 3.4). If you propose a model call, justify WHY hard in the RD.
**The PASS/FAIL/INCONCLUSIVE thresholds are a STAKEHOLDER decision — confirm + record them
in the RD; do NOT invent enforcement thresholds unilaterally.** If it hangs off the
tracking-table stream, reuse the 3.1→3.4 idempotency guard (a `Decimal`-canonicalized
fingerprint over the inputs the verdict is derived from).

# NON-NEGOTIABLE CONSTRAINTS
- DERIVE the verdict; do not re-score/re-correlate/re-normalize/rebuild findings (those are
  3.3/3.2/3.1/3.4, all done).
- ⚠️ DO NOT RE-AGGREGATE THE THREE SCORES INTO A NEW COMBINED JUDGMENT. 3.5 derives a verdict
  FROM the three 0-100 scores + findings/gaps; it must NOT compute a fresh blended/averaged
  "overall" number out of static + dynamic + combined. That is the RD-038 anti-pattern pushed
  down a layer (RD-038 was explicit: the `combined` score is Nova Pro's OWN whole-picture
  assessment over both lanes' evidence, NOT an arithmetic roll-up of the two lane scores).
  The `combined` score REMAINS the authoritative whole-picture number — 3.5 READS it (and the
  static/dynamic scores + gaps) to map to PASS/FAIL/INCONCLUSIVE via the stakeholder-confirmed
  thresholds; it never recomputes or re-weights the scores into a new score of its own.
- ⚠️ 3.5's VERDICT LIVES IN A NEW, OWN FIELD + CONTRACT — NEVER on an existing record. Write
  the verdict to a NEW tracking-item field (e.g. `verdict_result` / `verdict_at`), following
  the SAME distinct-field, integrity-bound, fingerprint-guarded, additive-stream-consumer
  pattern as 3.1 (`combined_event`/`combined_at`), 3.2 (`correlation_result`/`correlated_at`),
  3.3 (`scoring_result`/`scored_at`), 3.4 (`remediation_result`/`assessed_at`). NEVER write a
  `verdict` (or any banned key) onto `scoring_result` / `remediation_result` /
  `correlation_result` / `combined_event` — those records are contractually verdict-free and a
  3.3/3.4 test WILL start failing if you do. 3.5 is an ADDITIVE fifth stream consumer: it must
  not perturb the other four's fields, tests, or contracts.
- THE VERDICT IS A HUMAN-GATED RECOMMENDATION. Frame the verdict record as ZTIE's recommended
  verdict that INFORMS the human accept/reject gate — never an auto-enforced decision. The
  human ACTION + Phase-4 routing (4.6/4.7) are downstream.
- PARTIAL / ABSENT EVIDENCE → INCONCLUSIVE. Never fabricate a PASS or FAIL over incomplete
  evidence.
- BOUNDED IN + BOUNDED OUT; allow-list; integrity-keyed by intake_id + sha256. RD-009/RD-013
  intact (reason only over derived Hub-side data — the scores + findings; no raw data, no
  Forensic durable store).
- PURE LOGIC + THIN SEAM (the proven 1.2→…→3.4 pattern). If — discouraged — it calls Nova
  Pro, a REAL call with exponential-backoff retry (RD-003) + scoped Bedrock grant (never
  `*`); but PURE + deterministic is strongly preferred.
- ⚠️ FIRST VERDICT-BEARING CONTRACT — DO NOT WEAKEN OR GLOBALIZE THE 3.1–3.4 NO-VERDICT
  SCANS. The existing recursive no-verdict scans + schema-has-no-verdict-property tests (over
  the shared `_BANNED_VERDICT_KEYS = {verdict, safe, approved, forward, malicious, pass_fail,
  clean}`) protect the 3.1–3.4 records, and they must STAY EXACTLY AS THEY ARE. 3.5's OWN new
  contract intentionally carries the `verdict` field — so give 3.5 its OWN test (an INVERTED
  schema check that verifies the verdict IS present + allow-listed, plus a scan that the rest
  of 3.5's record is otherwise banned-key-free). THE TRAP TO AVOID: do NOT refactor the
  banned-keys test into a shared/global helper that starts covering 3.5's record, and do NOT
  make 3.5's record reuse a 3.1–3.4 field — either would make a 3.3/3.4 test fail or give a
  3.4 record a verdict it is contractually forbidden to have. Keep 3.5's verdict-bearing test
  infrastructure SEPARATE from the 3.1–3.4 no-verdict infrastructure.
- VALIDATION-GATED: 3.5 flips ✅ only on a recorded LIVE pass of the FINAL code.
- DOCS FIRST-CLASS (RD-015): PR-reviewed; PROJECT_PLAN ↔ RUNBOOK aligned.

# NEW REGISTERED DECISION
Record the verdict-derivation design (incl. the stakeholder-confirmed PASS/FAIL/INCONCLUSIVE
thresholds) as a new RD with rationale + candidate NIST/ISO mappings. RE-VERIFY the next
free RD number at STEP 0 with `grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md | sort -u | tail`
(RD-039 is 3.4's; **expect RD-040, but VERIFY — RD-036 was a real collision, RD-017 is a
historical gap.** Take the next genuinely-free number). **CHECK E is literal** — add the new
RD's plan-table row BEFORE referring to that number in any living doc.

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
  register in the SAME commit. **CHECK E is literal** — define RD-040's plan-table row BEFORE
  referencing the number anywhere.
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
  (if not, STOP — clear the open entry, i.e. 3.4's live pass). Next free RD number RE-VERIFIED
  (expect RD-040, confirm). CONFIRM the PASS/FAIL/INCONCLUSIVE thresholds with the stakeholder
  before coding the mapping.
- Branch off `main`. Branch name: `feature/story-3.5`.

# DEFINITION OF DONE — a PASS/FAIL GATE
1. For one `intake_id`, a bounded verdict record (PASS/FAIL/INCONCLUSIVE + basis + caveats)
   recorded on the Hub tracking item, framed as ZTIE's human-gated recommendation.
2. Derived from the three risk scores + findings/gaps; PARTIAL/incomplete evidence yields
   INCONCLUSIVE honestly (never a fabricated PASS/FAIL).
3. The verdict INFORMS the human gate — it is NOT auto-enforced; RD-009/RD-013 intact; the
   3.1–3.4 records stay verdict-free (their no-verdict scans intact).
4. Validated LIVE and RECORDED (another end-to-end pipeline pass). Record in the Validation
   Result the derived verdict + its basis for the test intake.
- Goes ✅ ONLY on a recorded live pass of the FINAL code. No pass → stays 🟡 (+ register).
  **On pass, Phase 3 CLOSES** and Phase 4 (4.1 next) unblocks.

# WORKING AGREEMENT
- One story to completion: design → build → validate → RECORD + flip status → paired commit;
  push to a branch; open a PR via `gh api …/pulls`. After merge, `git log
  main..feature/story-3.5`.
- Validation drives status; the advancement gate governs advancement.
- MANAGEMENT ARTIFACTS FIRST-CLASS (RD-015): brief + RUNBOOK + PROJECT_PLAN aligned; the new
  RD (+ the stakeholder-confirmed thresholds) + candidate mappings recorded; repoint
  `_NEW_WORK_STORY` off 3.5 (→ 4.1); re-run doc checks AFTER committing.
- Author a 3.5 LIVE-RUNBOOK for the stakeholder's real validation.
- At session end, author the next story's brief + prompt (4.1 status-retrieval orchestrator)
  with this session's real Lessons Learned.
- If blocked (incl. by the 3.4 gate), push partial progress + a draft PR; surface the
  blocker; never silently fail.
