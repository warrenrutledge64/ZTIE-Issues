# Story 3.4 (RD-038 scope — detailed findings + prioritized remediations)

You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting. Do NOT change anything until you have (a) READ the plan +
runbook + methodology + this story's brief (`session-briefs/story-3.4-brief.md`) + the
Phase-3 design record (`docs/proposals/phase3-three-score-model.md`), (b) re-established
true state (STEP 0), and (c) confirmed the Validation Debt Register + advancement gate.

# PROJECT IDENTITY
ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted artifact
BEFORE it reaches the PDE. Validation-gated: nothing is ✅ until a recorded live pass (the
covenant). Three accounts: Pipeline-Hub (641628980935) = brains/control plane + durable
record + Bedrock; Forensic (360999005254) = self-contained blast zone; Pipeline-Sandbox
(586917955591) = ZTIE→PDE handoff.

# WHERE THIS STORY SITS — BUILD TIER 11, ADVANCING FROM TIER 10 (WITHIN P3)
Story 3.4 is **build tier 11**; this session **ADVANCES tier 10 → 11** (its tier-10
dependency `3.3` goes ✅, a new dependency layer opens). A tier move WITHIN Phase 3 (no
phase transition). STEP 0 must re-confirm the ENTIRE tier-≤10 set is ✅ (`3.3` AND its
input `3.2`).

# PRIOR-SESSION UPDATE (2026-09-12, after the G-1 governance session)
Since this prompt was first authored, **Story 3.3 was VALIDATED LIVE (RD-038) and is now ✅
on `main`** (three real Nova Pro risk scores; merge #110, RUNBOOK master row ✅ 2026-09-12),
so the Validation Debt Register is EMPTY and **the advancement gate for 3.4 is expected
OPEN.** Also on `main`: the **G-1 compliance back-map** landed the finished
`docs/COMPLIANCE.md` matrix (PR #111) — G-1 sits 🟡 *authored/awaiting-ratification*, but it
is a `gov` story (register-exempt) so it does NOT arm your gate. STEP 0 still RE-VERIFIES all
of this on `main` (trust `main` + `check_docs`; if they disagree, `main` wins).

# ⚠️ ADVANCEMENT GATE — CHECK THIS FIRST
NEW FEATURE story. It may begin ONLY if its Depends-on are ALL ✅ AND the Validation Debt
Register is EMPTY. **Story 3.3 (reworked to RD-038) is now ✅ on `main` (validated live
2026-09-12)**, so the gate is expected OPEN — but STEP 0 MUST re-confirm on `main`: `3.3` ✅
and the register EMPTY (trust `main` + `check_docs`; if they disagree, `main` wins). **If
`main` shows 3.3 back at 🟡 for any reason, 3.4 MAY NOT begin — the only permitted work is
validating/reworking 3.3.** `check_docs` CHECK B, machine-enforced. Depends-on: **3.3 ✅**.
Build tier 11.

# WHAT CHANGED (RD-038) — READ THIS
Under RD-038, **Story 3.3 now produces the risk SCORES** (three independent 0-100 Nova Pro
scores: static / dynamic / combined, shared rubric, in `scoring_result`). **Story 3.4 does
NOT score.** 3.4 produces the **detailed findings + prioritized remediations** over those
scores, and it is the new home of the list-shaped content that migrated out of the old 3.3
(the candidate-false-positive list + the gap list). Do NOT re-implement scoring here.

# THE JOB
For one `intake_id` with a `scoring_result` (three scores) + the 3.2 `correlation_result`
(categorized findings), produce, recorded verdict-free on the Hub tracking item:
- **detailed findings** — the correlation findings surfaced for a human, PLUS the migrated
  **candidate-false-positive list** (from `static_only` findings) and **gap list**
  (`static_uncorroborated` / `dynamic_unexplained` / `contradiction` / `coverage`);
- a **prioritized remediation list** — ranked by the three risk scores + finding/gap
  severities (highest-risk first), each remediation an actionable, bounded, inert string.

# CONTRACT-FIRST DECISION (make + justify in the new RD)
The inputs are ALREADY fully structured (three 0-100 scores + categorized findings on the
Hub item). So 3.4 is very likely **PURE Hub-side post-processing** (read the scores +
findings → build the findings view + rank remediations → write the result back), NOT a
model call and NOT a new Forensic→Hub crossing — mirroring 3.3's/3.1's placement + "prefer
PURE" reasoning (RD-038/RD-037). Decide CONTRACT-FIRST: define the result schema (bounded,
verdict-free, allow-list, own version pin), decide WHERE it runs + whether it calls the
model (default: PURE, no Bedrock), and justify it in the RD. If it hangs off the
tracking-table stream, reuse the 3.1/3.2/3.3 idempotency + call-storm guard (a
`Decimal`-canonicalized fingerprint over the `scoring_result`).

# NON-NEGOTIABLE CONSTRAINTS
- FINDINGS + REMEDIATIONS, do not re-score/re-correlate/re-normalize. The scores are 3.3's;
  3.3/3.2/3.1/2.5/2.4 are done.
- EVIDENCE + a to-do list, NEVER A VERDICT. No verdict/safe/approved/forward/malicious/
  pass_fail/clean field anywhere. A remediation is "fix X," not "reject the artifact." The
  PASS/FAIL/INCONCLUSIVE verdict is Story 3.5, human-gated.
- TOLERATE PARTIAL SCORES. A `scoring_result` block may be `model_error`/`unparseable`/
  `skipped_no_evidence` (RD-038 partial results are legitimate). Rank honestly over whichever
  scores are present; never fabricate a missing score.
- BUILD THE MIGRATED LISTS HERE from the 3.2 `correlation_result` findings (each `kind` ∈
  correlated/static_only/dynamic_only/contradiction): `static_only` → candidate false
  positive + `static_uncorroborated` gap; `dynamic_only` → `dynamic_unexplained` gap;
  `contradiction` → `contradiction` gap; `coverage` gap when `combined_complete` is false.
  (The removed 3.3 `synthesize.py` at the PR #104 merge in git history has the exact mapping.)
- BOUNDED IN + BOUNDED OUT; allow-list; integrity-keyed by intake_id + sha256; arrays
  maxItems-capped. RD-009/RD-013 intact (reason only over derived Hub-side data).
- PURE LOGIC + THIN SEAM (the proven 1.2→…→3.3 pattern). If — unlikely — it calls Nova Pro,
  a REAL call with exponential-backoff retry (RD-003), scoped Bedrock grant (never `*`); but
  prefer PURE.
- VALIDATION-GATED: 3.4 flips ✅ only on a recorded LIVE pass of the FINAL code.
- DOCS FIRST-CLASS (RD-015): PR-reviewed; PROJECT_PLAN ↔ RUNBOOK aligned.

# NEW REGISTERED DECISION
Record the findings + remediations design as a new RD with rationale + candidate NIST/ISO
mappings. RE-VERIFY the next free RD number at STEP 0 with
`grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md | sort -u | tail` (RD-038 is 3.3's; **expect
RD-039, but VERIFY — RD-number collisions HAVE happened: RD-036 was taken by G-4 when 3.3
expected it, so 3.3 used RD-037. RD-017 is a historical gap.** Take the next genuinely-free
number).

# OPERATIONAL CONTEXT (state on EVERY command block)
  Build sandbox is INTEGRATIONS_ONLY (NO AWS creds; PyPI + npm BLOCKED — boto3/pytest/moto/
  jsonschema/aws-cdk-lib NOT installable). You BUILD; the USER validates live. Region
  us-east-1; `aws sts get-caller-identity` before EVERY operational block. Tracking table +
  (if used) Bedrock = HUB. If 3.4 is PURE (recommended) there is NO Bedrock prerequisite.
  Tests with `~/.pyenv/versions/3.12.13/bin/python3`; `ruff` at
  `~/.pyenv/versions/3.12.13/bin/ruff` (DEFAULT rules — watch RUF046 `int(round(x))` → use
  `round(x)`; RUF059 unused unpacked var → prefix `_`; RUF100 no `# noqa` for a non-enabled
  rule; ISC004 wrap implicit string concat in a list in parens; blind `except Exception`
  that does not re-raise needs `# noqa: BLE001`). `prettier`/`tsc` need `env -u NODE_OPTIONS`;
  npm BLOCKED so `tsc --noEmit` shows ONLY the missing-`aws-cdk-lib` family — confirm the
  error-TYPE set matches the `main` baseline (count deltas in an existing type are fine). Do
  NOT prettier-reformat generated JSON contracts. Keep tests stdlib-only + boto3-stubbed.

# HARD-WON LESSONS (do NOT repeat)
- **The derived pattern (held 8× now, +the 3.3 RD-038 rework):** contract-first + a bounded
  allow-list record with its OWN version pin + PURE logic + a thin `awsio` seam +
  evidence-never-verdict + a two-layer conformance test (stdlib walk + jsonschema
  `skipUnless`) + a recursive no-verdict-key scan + a schema-has-no-verdict-property check.
- **3.3's inputs are structured, so 3.4 is almost certainly PURE.** 3.3 needed Nova Pro
  (raw evidence → scores); 3.4's inputs are scores + categorized findings → deterministic
  ranking. A model call would only add cost/non-determinism/verdict-risk. Prefer PURE; if you
  call the model, justify WHY in the RD and reuse the 3.2/3.3 `awsio.invoke_nova` pattern.
- **check_docs fixture:** `scripts/test_check_docs.py` pins `_NEW_WORK_STORY` to a downstream
  ⬜ story — currently **3.4**. **When 3.4 leaves ⬜ (this story starts/finishes), repoint it
  to the next still-⬜ feature story (3.5) IN THE SAME PR**, then re-run
  `python3 -m unittest scripts.test_check_docs` (SUITE line OK).
- **check_docs timing (RD-015):** run `python3 scripts/check_docs.py` only AFTER committing
  status/register edits (CHECK B baseline is `git show HEAD:RUNBOOK.md`). Set 3.4 🟡 AND add
  it to the register in the SAME commit.
- **CHECK E is literal (learned in the G-1 session):** CHECK E flags the literal token
  `RD-0NN` ANYWHERE in a LIVING doc if that number is absent from the PROJECT_PLAN decisions
  table. So do NOT write a not-yet-defined or never-assigned RD number in prose (e.g. naming
  a historical gap number as `RD-0NN`) — describe it without the literal token, or define the
  RD in the plan table first. When you author RD-039, add its plan-table row BEFORE referring
  to `RD-039` in RUNBOOK/STORY_DETAIL/COMPLIANCE, or CHECK E fails.
- **`test_check_docs` reflects the live tree (learned in the G-1 session):** the suite
  validates the REAL repo docs, so it reports `FAILED` while `check_docs` has ANY real
  violation in the working tree. Fix the `check_docs` violation FIRST, then the suite returns
  `OK` — a mid-edit `FAILED` is usually your own uncommitted violation, not a regression in
  the checker.
- **Deploy-gap (both modes):** if 3.4 touches a Lambda, redeploy `ZtieHubTrackingStack` from
  the RIGHT branch; BEFORE deploy grep the stack source for the new marker; AFTER deploy
  inspect the LIVE resource. When a call "succeeds" but produces no result, READ THE LAMBDA'S
  OWN LOGS.
- **Two accounts, two tabs:** `sts get-caller-identity` before every block; the table = HUB.
  `gh pr create` is BROKEN — open PRs via `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`.

# STEP 0 — RE-ESTABLISH TRUE STATE
- `git fetch origin`; `git checkout main`; `git reset --hard origin/main`. List open PRs.
- `python3 scripts/check_docs.py` → PASS. `python3 -m unittest scripts.test_check_docs` →
  SUITE OK.
- Confirm: this story = 3.4 = ⬜, build tier 11, Depends-on `3.3`; tier 10 → 11 (WITHIN P3);
  EVERY tier-≤10 dep ✅ (`3.3` + `3.2`); register EMPTY + `3.3` ✅ (if not, STOP — clear the
  open entry, i.e. 3.3's live pass). Next free RD number RE-VERIFIED (expect RD-039, confirm).
- Branch off `main`. Branch name: `feature/story-3.4`.

# DEFINITION OF DONE — a PASS/FAIL GATE
1. For one `intake_id`, a bounded, verdict-free result with detailed findings (incl. the
   migrated candidate-FP + gap lists) + a prioritized remediation list recorded on the item.
2. Ranked by the three risk scores + severities; tolerates a partial `scoring_result`
   honestly.
3. EVIDENCE + remediations only — no verdict/safe/forward field anywhere; RD-009/RD-013 intact.
4. Validated LIVE and RECORDED.
- Goes ✅ ONLY on a recorded live pass of the FINAL code. No pass → stays 🟡 (+ register).

# WORKING AGREEMENT
- One story to completion: design → build → validate → RECORD + flip status → paired commit;
  push to a branch; open a PR via `gh api …/pulls`. After merge, `git log
  main..feature/story-3.4`.
- Validation drives status; the advancement gate governs advancement.
- MANAGEMENT ARTIFACTS FIRST-CLASS (RD-015): brief + RUNBOOK + PROJECT_PLAN aligned; the new
  RD + candidate mappings recorded; repoint `_NEW_WORK_STORY` off 3.4; re-run doc checks
  AFTER committing.
- Author a 3.4 LIVE-RUNBOOK for the stakeholder's real validation.
- At session end, author the next story's brief + prompt (3.5 verdict derivation) with this
  session's real Lessons Learned.
- If blocked (incl. by the 3.3 gate), push partial progress + a draft PR; surface the
  blocker; never silently fail.
