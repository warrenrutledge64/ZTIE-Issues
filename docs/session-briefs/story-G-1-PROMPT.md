Story G-1

You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting. Do NOT change anything until you have (a) READ the
plan + runbook + methodology + this story's brief (`session-briefs/story-G-1-brief.md`),
(b) re-established true state (STEP 0), and (c) confirmed the sequence check + the
Validation Debt Register state.

# PROJECT IDENTITY
ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted artifact
BEFORE it reaches the PDE. Work is validation-gated: nothing is ✅ until a recorded pass
of the FINAL artifact (the covenant). Three accounts: Pipeline-Hub (641628980935) =
brains/control plane + durable record; Forensic (360999005254) = self-contained blast
zone (ephemeral only); Pipeline-Sandbox (586917955591) = ZTIE→PDE handoff. Story G-1 is a
GOVERNANCE story: it executes RD-014 (compliance mapping is a standing auditability
practice) by FINISHING the control-traceability matrix in `docs/COMPLIANCE.md` and driving
candidate mappings to ratification.

# WHERE THIS STORY SITS — BUILD TIER 0, GOVERNANCE TRACK (no phase, no advancement gate on it)
G-1 is a `gov`-track story at build tier 0, depends on nothing hard-blocking. Governance
(`G-`) stories are EXEMPT from `check_docs` CHECK A/B/C register+gate logic and are not
build-order-gated. Consequences you MUST hold:
- G-1 is legitimately NOT in the Validation Debt Register even while ⬜/🟡; flipping it ✅
  neither clears a register row nor arms/disarms the gate.
- Do NOT touch the `_NEW_WORK_STORY` fixture pin (it tracks the next ⬜ *pipe* story — a
  governance story does not move it).

# SEQUENCE CHECK (METHODOLOGY §5.A.0 — do this FIRST)
G-1 is the first OPEN item in the RUNBOOK "Ready now" schedule (bucket A) as of this
prompt's authoring (G-3, C.3, G-2 all closed 2026-09-12). It is LOW-URGENCY: the
higher-value default next action is the pipe feature **3.2 (Nova Pro correlation)**, which
is being worked in a SEPARATE session and is OFF-LIMITS here (do not touch 3.2's
brief/prompt or its `_NEW_WORK_STORY` pin). **T.1** (multi-tenancy design spike) is also a
legitimate pre-Phase-4 candidate. If the stakeholder prefers to work a different Ready
story, that is a re-prioritization — surface it, get the explicit go, and RECORD it in
`docs/governance/WORK_LOG.md` before starting. Do NOT self-select or edit the schedule to
match a choice. `check_docs.py` CHECK J will flag an on-deck/schedule mismatch as a
non-blocking advisory (it points you to WORK_LOG, it does not fail the build).

# ⚠️ SCOPE — FINISH + RATIFY, DO NOT REBUILD
`docs/COMPLIANCE.md` already EXISTS (framework scope, candidate-vs-ratified convention,
~28 Proposed + 3 Ratified rows; mappings seeded for RD-001/009/012/013/014/016/021/025).
G-1 COMPLETES the matrix for the artifacts not yet mapped and drives ratification — it does
NOT build the doc from scratch. Full scope in the brief; the short version:
- Back-map the remaining registered decisions, the non-functional constraints, and each
  story to NIST SP 800-53 r5 (catalog of record) + NIST CSF + related NIST (RMF) +
  ISO/IEC 27001:2022 Annex A, in the existing matrix shape (artifact, control(s),
  rationale, Status).
- Label every new mapping `Proposed`; an accountable reviewer flips `Proposed → Ratified`
  (dated + attributed) per artifact group. Use `unmapped` honestly — never fabricate
  coverage, never assert ZTIE "is compliant."

# NON-NEGOTIABLE CONSTRAINTS
- FINISH + RATIFY, NEVER REBUILD `docs/COMPLIANCE.md`.
- CANDIDATE-UNTIL-RATIFIED (RD-014): ZTIE claims coverage ONLY for ratified mappings.
- DOCS FIRST-CLASS (RD-015): PR-reviewed, never straight to main; PROJECT_PLAN ↔ RUNBOOK
  in EXACT alignment; keep the doc-integrity checks GREEN (no dangling `RD-0NN` refs in
  living docs — CHECK E; no broken links — CHECK I; no drifted generated glyphs — CHECK H).
- VALIDATION-GATED, NEVER ON INFERENCE: G-1 flips ✅ only on a recorded pass (the reviewed
  matrix is accurate/ratified per artifact group AND `check_docs.py` PASSES clean + suite
  `OK`). May be validated incrementally per artifact group.
- 3.2 IS OFF-LIMITS (separate session). Do not touch it or `_NEW_WORK_STORY`.

# REGISTERED DECISIONS
No NEW RD is required (G-1 executes RD-014). If one is ever warranted, re-verify the next
free number with `grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md | sort -u | tail` and do NOT
hard-code a not-yet-defined RD id into a living doc (CHECK E will flag it).

# OPERATIONAL CONTEXT (state this on any command block)
Build sandbox is INTEGRATIONS_ONLY (NO AWS creds; PyPI + npm BLOCKED). G-1 needs NONE of
that — it is pure docs work, fully offline. `ruff` is NOT on PATH — use
`~/.pyenv/versions/3.12.13/bin/ruff` for any Python you touch (G-1 likely touches none);
default `python3` is 3.9 and `check_docs.py` + `test_check_docs.py` are stdlib-only and run
under it. No CloudShell, no `aws sts get-caller-identity`.

# STEP 0 — RE-ESTABLISH TRUE STATE (before any edit)
# Trust `main` + `check_docs` over anything written here; if they disagree, `main` wins.
- `git fetch origin`; `git checkout main`; `git reset --hard origin/main`. List open PRs.
- `python3 scripts/check_docs.py` → expect PASS (exit 0), possibly with a CHECK J advisory
  (non-blocking). `python3 -m unittest scripts.test_check_docs` → expect SUITE line `OK`.
- Sequence check (§5.A.0): confirm G-1 is the agreed next OPEN story (or record an approved
  reorder); 3.2 is a separate session and off-limits.
- Confirm EXPECTED TRUTHS: this story = G-1 = ⬜, `gov` track, build tier 0, Depends-on none;
  G-1 EXEMPT from CHECK A/B/C (correctly absent from the register); `docs/COMPLIANCE.md`
  already exists (do not rebuild); the G-2 checker (CHECK A–J) is live on `main`.
- Branch off `main`. Branch name: `feature/story-G-1`.

# DEFINITION OF DONE (this session) — a PASS/FAIL GATE
1. The traceability matrix in `docs/COMPLIANCE.md` covers the remaining design artifacts
   (registered decisions not yet mapped, non-functional constraints, stories) with honest,
   rationale-bearing candidate mappings (NIST 800-53 r5 / CSF / RMF + ISO 27001:2022
   Annex A); `unmapped` used where no real control matches.
2. An accountable reviewer has ratified (or corrected) the candidates per artifact group
   (`Proposed → Ratified`, dated + attributed); ZTIE claims coverage only for ratified rows.
3. `check_docs.py` PASSES clean (exit 0) and `test_check_docs` SUITE reports `OK`; PLAN ↔
   RUNBOOK aligned; no other story's status / the register / `_NEW_WORK_STORY` touched; no
   pipeline/infra/lambda code changed.
- Goes ✅ ONLY on a recorded pass. May be closed incrementally per artifact group. On any
  fail: stays ⬜/🟡, fix, re-run.

# ENVIRONMENT
- Repo cloned; push to `feature/story-G-1`, never main. Open PRs via
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls` (NOT `gh pr create` — it is BROKEN).
  Merges are the repo-owner's action. No live AWS is involved.

# WORKING AGREEMENT
- One story to completion: finish/ratify the matrix → RECORD + flip status → paired status
  commit; push to a branch; open a PR. After merge, `git log main..feature/story-G-1` to
  confirm the whole branch landed (base-branch trap).
- Validation drives status; a governance close is recorded, never inferred.
- MANAGEMENT ARTIFACTS ARE FIRST-CLASS (RD-015): brief + RUNBOOK + STORY_DETAIL + PROJECT_PLAN
  aligned; all via PR. If this story changed project status, update the RUNBOOK master table
  ONLY; confirm README / on-deck / BUILD_ORDER still POINT (don't copy); `check_docs` will
  verify. Run `check_docs` + `test_check_docs` AFTER committing any status edit.
- At session end, author the NEXT story's brief + prompt — the next Ready item per the
  RUNBOOK "Scheduling & readiness" buckets — with THIS session's real Lessons Learned.
  Zero cold-start.
- If a scope item proves infeasible, STOP and surface it; record the decision; do not force it.
