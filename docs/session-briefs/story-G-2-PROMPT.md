Story G-2

You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting. Do NOT change anything until you have (a) READ the
plan + runbook + methodology + this story's brief (`session-briefs/story-G-2-brief.md`),
(b) re-established true state (STEP 0), and (c) confirmed the sequence check + the
Validation Debt Register state.

# PROJECT IDENTITY
ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted artifact
BEFORE it reaches the PDE. Work is validation-gated: nothing is ✅ until a recorded pass
of the FINAL code (the covenant). Three accounts: Pipeline-Hub (641628980935) =
brains/control plane + durable record; Forensic (360999005254) = self-contained blast
zone (ephemeral only); Pipeline-Sandbox (586917955591) = ZTIE→PDE handoff. Story G-2 is a
GOVERNANCE story: it makes RD-015 (management artifacts held to the same bar as code)
machine-enforceable end-to-end by EXTENDING the existing `scripts/check_docs.py` and
killing the doc-drift class the 2026-09-12 audit found.

# WHERE THIS STORY SITS — BUILD TIER 0, GOVERNANCE TRACK (no phase, no advancement gate on it)
G-2 is a `gov`-track story at build tier 0, depends on nothing hard-blocking. Governance
(`G-`) stories are EXEMPT from `check_docs` CHECK A/B/C register+gate logic and are not
build-order-gated. Consequences you MUST hold:
- G-2 is legitimately NOT in the Validation Debt Register even while ⬜/🟡; flipping it ✅
  neither clears a register row nor arms/disarms the gate.
- `check_docs` output does not change because of G-2's status; do not hunt for a register
  row to clear.
- Do NOT touch the `_NEW_WORK_STORY` fixture pin (it tracks the next ⬜ *pipe* story — a
  governance story does not move it).

# SEQUENCE CHECK (METHODOLOGY §5.A.0 — do this FIRST)
Confirm G-2 is the story we agreed to work. As of this prompt's authoring the stakeholder
explicitly chose **G-2 as the next governance story** (see the 2026-09-12 WORK_LOG entry);
**Story 3.2 is being worked in a SEPARATE session** and is OFF-LIMITS here — do not touch
3.2's brief/prompt, its `_NEW_WORK_STORY` pin, or start any 3.2 work. If `main` shows a
different agreed next item, STOP and surface it (do not self-select; do not edit the
RUNBOOK schedule to match a choice).

# ⚠️ SCOPE IS RE-BASED — FINISH + EXTEND, DO NOT REBUILD
When G-2 was first written, `scripts/check_docs.py` did not exist. **It exists now** (built
by G-3) and already enforces **CHECK A** (register completeness), **CHECK B** (advancement
gate), and **CHECK C** (schedule order: dependency precedence + deferred-last). G-2 is
**finish + extend, NOT build-from-scratch — DO NOT rebuild the checker or touch CHECK
A/B/C's behaviour.** You ADD new checks + kill doc-drift + document the reusable-OS/instance
boundary. The full scope is in the brief; the short version:

# THE JOB (all EXTEND the existing checker / docs; see the brief for detail)
- (a) **Integrity checks:** fail if PROJECT_PLAN↔RUNBOOK story-sets diverge per phase; a
  referenced `RD-0NN` is absent from the decisions table; stray `{{placeholders}}` remain
  outside the known template files; a ✅ story lacks a dated Validation Result line.
- (a2) **CANDIDATE sequence-adherence check** (added 2026-09-12): evaluate whether the
  checker can mechanically flag when the on-deck starter / the story a session opens is NOT
  the first OPEN item in the RUNBOOK "Ready now" schedule. Make it ADVISORY (a reorder is a
  legitimate stakeholder decision — warn / require an explicit recorded reorder, do NOT
  hard-fail an approved reorder). If a clean mechanical signal isn't feasible, record why
  and leave it as the documented process rule (METHODOLOGY §5.A.0). The process rule already
  landed in the G-2-prep PR; this is only the optional mechanical backstop.
- (b1) **De-duplicate status:** rework README "Status at a glance"/"Current focus" and
  `docs/BUILD_ORDER.md` per-story ✅/⬜ glyphs so they POINT to (or are generated from) the
  RUNBOOK master table instead of being a hand-kept copy (if a fact isn't duplicated it
  can't go stale).
- (b2) **Doc-drift check:** fail when a LIVING doc's embedded story-status glyph disagrees
  with the RUNBOOK master table, AND when the on-deck starter points at a story already ✅.
  SCOPE THE GLYPH CHECK TO LIVING DOCS ONLY (README, BUILD_ORDER, on-deck) — frozen dated
  per-story briefs/PROMPTs/LIVE-RUNBOOKs + WORK_LOG are snapshots and must NOT be "corrected."
- (b3) **Dangling-link check:** fail if any tracked `*.md` links to a repo-relative path
  that does not exist.
- (c) **Reusable-OS / project-instance separation:** document the boundary (the generic OS
  layer — METHODOLOGY, templates, the gate, restore discipline — vs. the ZTIE-instance layer
  — RD-008…, account IDs, pipeline stories) so reusability is provable, not asserted.
- (d) **Governance-doc commit pin:** ensure the restore manifest pins the known-good
  governance-doc commit (coordinate with 1.R) so code + state + governance restore as one unit.
- **Close-out habit:** add one line to `docs/SESSION_PROMPT_TEMPLATE.md` — "if this story
  changed project status, update RUNBOOK ONLY; confirm README / on-deck / BUILD_ORDER still
  POINT (don't copy); `check_docs` will verify."

# NON-NEGOTIABLE CONSTRAINTS
- FINISH + EXTEND, NEVER REBUILD. Keep CHECK A/B/C behaviour intact; add new checks in the
  same module. Keep it **stdlib-only, offline, Python-3.9-compatible** (the suite runs under
  the repo's default `python3`). Every new check gets a self-test in `test_check_docs.py`
  that mutates a copy and asserts the new check FIRES (read the SUITE result line `OK` /
  `FAILED (failures=N)`, NOT the in-suite fixture-print `check_docs: FAIL …` lines — those
  are the checker exercising itself).
- DE-DUP CAREFULLY. When converting README/BUILD_ORDER status to pointers, replace the
  DUPLICATED STATUS TABLE with a link (+ optional generated snippet), not the surrounding
  narrative. Don't lose useful prose.
- LIVING vs FROZEN. The b2 glyph check must target only living docs; never rewrite a dated
  frozen artifact to satisfy a checker.
- VALIDATION-GATED, NEVER ON INFERENCE: G-2 flips ✅ only on a recorded pass — the checker
  PASSES clean AND is demonstrably shown to FAIL on each injected defect (one fixture per new
  check), the reusable-OS/instance boundary doc is reviewed as accurate, and the
  status-duplication surfaces are converted to pointers.
- DOCS FIRST-CLASS (RD-015): PR-reviewed, never straight to main; PROJECT_PLAN ↔ RUNBOOK in
  EXACT alignment.
- 3.2 IS OFF-LIMITS (separate session). Do not touch it or `_NEW_WORK_STORY`.

# REGISTERED DECISIONS
No NEW RD is required (G-2 executes RD-015; the sequence rule is process, already documented).
If the de-dup design warrants a decision, record it — re-verify the next free RD with
`grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md | sort -u | tail` (RD-034 is C.3's; expect RD-035,
but VERIFY — RD-017 is a historical gap and collisions have happened).

# OPERATIONAL CONTEXT (state this on any command block)
Build sandbox is INTEGRATIONS_ONLY (NO AWS creds; PyPI + npm BLOCKED). G-2 needs NONE of
that — it is pure docs + Python stdlib checker/suite work, fully offline. `ruff` is NOT on
PATH — use `~/.pyenv/versions/3.12.13/bin/ruff` for any Python you touch; `prettier`/`npx
tsc` need `env -u NODE_OPTIONS` (only relevant if you touch `.ts`/`.md` prettier scope —
note `scripts/` markdown is NOT prettier-gated and README.md pre-dates prettier). Default
`python3` is 3.9; `check_docs.py` + `test_check_docs.py` are stdlib-only and run under it.
No CloudShell, no `aws sts get-caller-identity`.

# STEP 0 — RE-ESTABLISH TRUE STATE (before any edit)
# Trust `main` + `check_docs` over anything written here; if they disagree, `main` wins.
- `git fetch origin`; `git checkout main`; `git reset --hard origin/main`. List open PRs.
- `python3 scripts/check_docs.py` → expect PASS (exit 0). `python3 -m unittest
  scripts.test_check_docs` → expect SUITE line `OK`.
- Sequence check (§5.A.0): confirm G-2 is the agreed next OPEN story; 3.2 is a separate
  session and off-limits.
- Confirm EXPECTED TRUTHS: this story = G-2 = ⬜, `gov` track, build tier 0, Depends-on none;
  G-2 EXEMPT from CHECK A/B/C (correctly absent from the register); `scripts/check_docs.py`
  already has CHECK A/B/C (do not rebuild); the process sequence-rule already lives in
  METHODOLOGY §5.A.0 + §2 + the RUNBOOK "Sequencing rule" + the templates (landed in the
  G-2-prep PR) — G-2's a2 is only the optional mechanical backstop.
- Branch off `main`. Branch name: `feature/story-G-2`.

# DEFINITION OF DONE (this session) — a PASS/FAIL GATE
1. `check_docs.py` PASSES clean AND is shown to FAIL on each injected defect: plan/runbook
   divergence; a dangling RD ref; a stray placeholder; a ✅ story with no Validation Result
   line; a README/BUILD_ORDER glyph disagreeing with RUNBOOK; an on-deck pointer at a ✅
   story; a dangling `*.md` link. Each new check has a self-test proving it fires; suite `OK`.
2. The status-duplication surfaces (README status regions, BUILD_ORDER glyphs) are converted
   to POINTERS (not hand-kept copies); the (a2) sequence-check is implemented as advisory OR
   its infeasibility is recorded.
3. The reusable-OS / project-instance boundary doc exists and is reviewed as accurate; the
   governance-doc commit pin (d) is confirmed in the restore manifest (coordinate with 1.R).
4. PLAN ↔ RUNBOOK aligned; no other story's status / the register / `_NEW_WORK_STORY` touched;
   no pipeline/infra/lambda code changed.
- Goes ✅ ONLY on a recorded pass of the FINAL checker. On any fail: stays ⬜/🟡, fix, re-run.

# ENVIRONMENT
- Repo cloned; push to `feature/story-G-2`, never main. Open PRs via
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls` (NOT `gh pr create` — it is BROKEN).
  Merges are the repo-owner's action. No live AWS is involved.

# WORKING AGREEMENT
- One story to completion: extend the checker + kill drift → prove each new check FIRES →
  RECORD + flip status → paired status commit; push to a branch; open a PR. After merge,
  `git log main..feature/story-G-2` to confirm the whole branch landed (base-branch trap).
- Validation drives status; a governance close is recorded, never inferred.
- MANAGEMENT ARTIFACTS ARE FIRST-CLASS (RD-015): brief + RUNBOOK + STORY_DETAIL + PROJECT_PLAN
  aligned; all via PR. Run `check_docs` + `test_check_docs` AFTER committing any status edit.
- At session end, author the NEXT story's brief + prompt — the next Ready item per the RUNBOOK
  "Scheduling & readiness" buckets — with THIS session's real Lessons Learned. Zero cold-start.
- If a scope item proves infeasible (e.g. a clean mechanical a2 signal), STOP and surface it;
  record the decision; do not force it.
