Story G-3 (CLOSE)

You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting. Do NOT change anything until you have (a) READ the
plan + runbook + methodology + this story's CLOSE brief
(`session-briefs/story-G-3-close-brief.md`), (b) re-established true state (STEP 0),
and (c) confirmed what "closing G-3" means below.

# PROJECT IDENTITY
ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted artifact
BEFORE it reaches the PDE. Work is validation-gated: nothing is ✅ until a recorded pass
of the final code (the covenant). Three accounts: Pipeline-Hub (641628980935) =
brains/control plane + durable record; Forensic (360999005254) = self-contained blast
zone; Pipeline-Sandbox (586917955591) = ZTIE→PDE handoff.

# WHAT THIS SESSION IS
This is a **CLOSE**, not a build. **Story G-3 (Hard-pause enforcement, RD-023)** was
built long ago and has been actively enforcing the advancement gate through every
feature story since (it gated 3.1 and 3.2, and was extended with CHECK C in the
build-order fix). But G-3's own status is still 🟡 — the machinery that enforces the
covenant has never been through the covenant's own close. This session records G-3's
overdue validation and flips it 🟡 → ✅. **Validation is fully OFFLINE — no AWS, no
CloudShell.** Do NOT rebuild, "improve," or re-scope the checker.

# WHERE THIS SITS — BUILD TIER 0, GOVERNANCE TRACK (no phase, no advancement gate on it)
G-3 is a `gov`-track story at build tier 0. Governance (`G-`) stories are EXEMPT from
`check_docs` CHECK A/B (and are not build-order-gated). Consequences you MUST hold:
- G-3 is legitimately NOT in the Validation Debt Register even while 🟡, and flipping
  it ✅ neither clears a register row nor arms/disarms the gate.
- `check_docs` PASSES both before and after this close (its output does not change).
  That is EXPECTED — do not hunt for a register entry to clear.
- Do NOT touch the `_NEW_WORK_STORY` fixture pin (it tracks the next ⬜ *pipe* story,
  currently 3.2 — unrelated to a governance close).

# THE JOB
1. VERIFY (do not build) that G-3's four Definition-of-Done artifacts exist on `main`.
2. RUN the offline validation: the checker PASSES clean + its unittest suite reports
   the SUITE line `OK` (the suite proves CHECK A/B/C each FIRE on injected defects).
3. RECORD a dated Validation Result and flip the G-3 row 🟡 → ✅ (paired commit).
4. Confirm PLAN ↔ RUNBOOK alignment; author the next handoff; open a PR.

# G-3's DEFINITION OF DONE (all expected TRUE on `main` — verify, never fabricate)
1. **Validation Debt Register** exists in `RUNBOOK.md` (machine-parsed table + status
   line).
2. **Advancement-gate clause** ("no new feature story while the register is non-empty")
   in the RUNBOOK gate section + `METHODOLOGY.md` §4.
3. **Story-closure ≠ restore-point-work decoupling** stated in `METHODOLOGY.md`.
4. **`scripts/check_docs.py` enforces the checks:** CHECK A (un-registered 🟡 fails),
   CHECK B (new feature started while debt open fails), clean tree passes; plus CHECK C
   (build-tier monotonic order) added since. All unittest-covered.
The RECORDED PASS is: `python3 scripts/check_docs.py` exit 0 on the clean tree AND
`python3 -m unittest scripts.test_check_docs` SUITE line `OK`. The in-suite
`check_docs: FAIL …` prints are the checker exercising ITSELF against fixtures — NOT
real failures; the SUITE result line (`OK` vs `FAILED (failures=N)`) is what matters.

# NON-NEGOTIABLE CONSTRAINTS
- VERIFY, DON'T BUILD. If all four DoD artifacts are present and the suite is `OK`,
  the ONLY change this session makes is the status flip + the recorded Validation
  Result + the next handoff. No checker changes, no pipeline/infra/lambda code.
- NEVER close on inference. If some DoD artifact is genuinely missing/broken, G-3
  stays 🟡, you FIX that specific gap (that is real G-3 work), then re-validate.
- DO NOT alter any OTHER story's status, the Validation Debt Register, the Operational
  Debt Register, or the `_NEW_WORK_STORY` fixture pin.
- DOCS FIRST-CLASS (RD-015): PR-reviewed, never straight to main; PROJECT_PLAN ↔
  RUNBOOK in EXACT alignment. RD-023 is already registered — no new RD is needed.

# OPERATIONAL CONTEXT (state this on any command block)
Build sandbox is INTEGRATIONS_ONLY (NO AWS creds; PyPI + npm BLOCKED). This close needs
NONE of that — it is pure docs + running the stdlib checker/suite. `ruff` is NOT on PATH
— use `~/.pyenv/versions/3.12.13/bin/ruff` if you touch any Python (you should not need
to). The default `python3` is 3.9; `check_docs.py` + `test_check_docs.py` are stdlib-only
and run under it fine. No CloudShell, no `aws sts get-caller-identity`, no two-tab dance.

# STEP 0 — RE-ESTABLISH TRUE STATE (before any edit)
# Trust `main` + `check_docs` over anything written here; if they disagree, `main` wins.
- `git fetch origin`; `git checkout main`; `git reset --hard origin/main`. List open PRs.
- `python3 scripts/check_docs.py` → expect PASS (exit 0). `python3 -m unittest
  scripts.test_check_docs` → expect SUITE line `OK` (7 tests at time of writing).
- Confirm these EXPECTED TRUTHS:
    - This story = G-3 = 🟡 (in progress), `gov` track, build tier 0, Depends-on none.
    - G-3 is EXEMPT from CHECK A/B — it is correctly absent from the Validation Debt
      Register; the register may be empty or not, either way G-3's close is allowed.
    - The four DoD artifacts (above) are present on `main`.
    - RD-023 is already in PROJECT_PLAN (no new RD).
- Branch off `main`. Branch name: `docs/story-G-3-close`.

# VERIFY THE DoD (paste evidence into the PR / STORY_DETAIL)
- Register present:  `grep -c "Validation Debt Register" RUNBOOK.md`  (>0)
- Gate clause:       `grep -in "advancement gate\|register is non-empty" METHODOLOGY.md`
- Decoupling:        `grep -in "closure is decoupled from restore-point" METHODOLOGY.md`
- Checks present:    `grep -n "check=\"CHECK A\"\|check=\"CHECK B\"\|check=\"CHECK C\"" scripts/check_docs.py`
- Recorded pass:     `python3 scripts/check_docs.py; echo exit=$?`  then
                     `python3 -m unittest scripts.test_check_docs 2>&1 | grep -E "^(OK|FAILED|Ran )"`

# RECORD + FLIP (only after the verify above is clean)
- `RUNBOOK.md` master table: flip the G-3 row `🟡` → `✅`, add the `Completed` date.
- `docs/STORY_DETAIL.md` G-3 section: change the header to `✅ Done (validated <date>)`
  and replace the `Validation Result: pending` line with a dated result that records:
  the four DoD artifacts confirmed present on `main`; `check_docs.py` PASS (exit 0);
  `test_check_docs` SUITE `OK` (N tests) proving CHECK A/B/C fire on injected defects;
  no other story's status changed; no code touched.
- Do NOT touch the Validation Debt Register (G-3 was never in it) or `_NEW_WORK_STORY`.
- COMMIT the status edit, THEN run `python3 scripts/check_docs.py` (CHECK B baseline is
  `git show HEAD:RUNBOOK.md`; running before the commit gives a false positive) and
  `python3 -m unittest scripts.test_check_docs` — confirm PASS + SUITE `OK`.

# DEFINITION OF DONE (this session) — a PASS/FAIL GATE
1. The four G-3 DoD artifacts are confirmed present on `main`.
2. `check_docs.py` PASS (exit 0) + `test_check_docs` SUITE `OK` recorded as G-3's pass.
3. G-3 flipped 🟡 → ✅ with a dated Validation Result; PLAN ↔ RUNBOOK aligned; no other
   story/status/register/fixture touched; no code changed.
- If any DoD artifact is missing/broken: G-3 stays 🟡, fix that gap, re-validate.

# ENVIRONMENT
- Repo cloned; push to `docs/story-G-3-close`, never main. Open PRs via
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls` (NOT `gh pr create` — it is BROKEN).
  Merges are the repo-owner's action. No live AWS is involved in this close.

# WORKING AGREEMENT
- One story to completion: verify → record + flip status → paired status commit; push to
  a branch; open a PR. After merge, `git log main..docs/story-G-3-close` to confirm the
  whole branch landed (base-branch trap).
- Validation drives status; a governance close is recorded, never inferred.
- MANAGEMENT ARTIFACTS ARE FIRST-CLASS (RD-015): brief + RUNBOOK + STORY_DETAIL aligned;
  all via PR. Re-run the doc checks AFTER committing the status edit.
- At session end, author the NEXT story's brief + prompt — the next Ready item per the
  RUNBOOK "Scheduling & readiness" buckets (C.3 shared seam, or 3.2 Nova Pro
  correlation) — with THIS session's real Lessons Learned. Zero cold-start.
- If a DoD gap is found (G-3 not actually closeable), STOP: surface it, keep G-3 🟡,
  push partial progress + a draft PR; never close on inference.
