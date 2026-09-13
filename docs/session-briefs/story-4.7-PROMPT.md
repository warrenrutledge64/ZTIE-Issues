# Session Prompt — Story 4.7 (REJECT → destroy artifact + detonation chamber in Forensic / INCONCLUSIVE → hold) — executor-facing

You are the execution agent for the ZTIE project. Read this fully before acting. Do NOT
change anything until you have (a) READ the plan + runbook + methodology + this story's brief
(`session-briefs/story-4.7-brief.md`), (b) re-established true state (STEP 0), and (c)
confirmed the validation-gate state this story depends on (STEP 0).

# PROJECT IDENTITY
ZTIE is a four-phase, AWS-native security pipeline that fully inspects every untrusted
artifact BEFORE it may reach the PDE. Three accounts: Pipeline-Hub (641628980935) =
brains/control plane + durable tracking + the human accept/reject gate; Forensic
(360999005254) = self-contained blast zone (intake, lanes, the raw artifact, ephemeral
detonation host); Pipeline-Sandbox (586917955591) = the ZTIE→PDE handoff landing zone. Phase
4 is under way: 4.1/4.2/4.3/4.5 ✅, and **4.6 (ACCEPT→push) is the sibling you just
completed**. Validation covenant: nothing is ✅ until a recorded live pass of the final code.

# WHERE THIS STORY SITS (build tier + position)
Story 4.7 is build tier 14 (dep 4.1, tier 13) — the tied, independent sibling of 4.6. This
session does NOT advance to a new tier or a new phase. It IS on the Phase-4-closure critical
path: **4.4** (tier 16) depends on **4.3 + 4.7**.

SEQUENCING — 4.7 IS THE FIRST-OPEN READY-NOW STORY ONCE 4.6 ✅; NO CONFIRMATION NEEDED TO
START IT (per the SESSION_PROMPT_TEMPLATE no-confirmation clause), once STEP 0 confirms 4.6
✅ + the register empty. A stakeholder decision is needed ONLY to deviate (a reorder logged
in `WORK_LOG.md`) or for a genuine design fork inside the story (the PLAN FIRST GATE).

# WHAT THIS STORY IS
NEW FEATURE story — the REJECT/INCONCLUSIVE ENFORCEMENT ACTION, the destroy/hold half of the
human gate (4.6 is the push half). On a recorded human REJECT, ZTIE **destroys** the raw
artifact **and** its detonation chamber in Forensic (explicit teardown, not TTL); on
INCONCLUSIVE it **holds** at the approval gate. The one sentence that prevents the biggest
category error: **4.7 destroys ONLY on a recorded human REJECT — NEVER on the advisory
`recommended_verdict`** (RD-040); INCONCLUSIVE is a HOLD (no destroy, no push). Fail-safe:
absent a genuine REJECT, nothing is destroyed. Decoupled from the human UI + auto trigger
(4.4). The derived report always survives in the Hub.

# NON-NEGOTIABLE CONSTRAINTS
- PLAN FIRST GATE: before writing code, outline the destroy/hold mechanism, the accounts +
  trust direction, the REJECT-gate representation, what "destroy the artifact" (all S3
  versions + delete-markers) and "destroy the chamber" (terminate the ephemeral EC2 if
  running) mean, and the crossed outcome; resolve the FIVE design forks in the brief; get
  explicit approval before generating the implementation.
- DESTROY ONLY ON A REAL HUMAN REJECT (RD-040): never the advisory verdict. FAIL-SAFE: no
  reject → no destroy. INCONCLUSIVE → HOLD (no destroy, no push).
- HUB STAYS OUT OF THE BLAST ZONE: the destroy happens IN Forensic; only a bounded, derived,
  verdict-free destroy/hold OUTCOME crosses to the Hub (RD-013). The derived report survives.
- NEVER RE-EXECUTE the artifact. ZTIE does security clearance only.
- VERSIONED-BUCKET DELETE: delete ALL object versions AND delete-markers under
  `intake/<intake_id>/` (a plain delete leaves versions — the OD-001 lesson).
- Production-quality: real deletes/terminates in the execution path; moto only at unit level.
  AWS-native. VALIDATION-GATED, never on inference. RESTORE-POINT discipline (build from
  main; revert not forward-patch). DOCS ARE FIRST-CLASS (RD-015): PLAN ↔ RUNBOOK exact.

# OPERATIONAL CONTEXT
Build sandbox is INTEGRATIONS_ONLY (no live AWS creds; PyPI + npm registry BLOCKED). You
BUILD; the STAKEHOLDER validates live in CloudShell. Region us-east-1. This is a FORENSIC
story (the artifact + chamber are in Forensic 360999005254; it reads the decision from the
Hub cross-account like 4.6, and crosses only a bounded outcome to the Hub). Run `aws sts
get-caller-identity` before every operational block.

# HARD-WON LESSONS (do NOT repeat)
- Verify the DEPLOYED resource after any deploy (role policy, Lambda env) — a green
  UPDATE_COMPLETE can ship stale code / the wrong checkout / wrong account.
- FAIL-SAFE gate is the hardest invariant — destroy ONLY on the exact string `rejected`;
  test it from every angle offline (a fake seam recording whether a destroy happened).
- DynamoDB Number → Decimal: coerce numeric fields read off the Hub item; never strict
  isinstance(int); add a Decimal regression case.
- Versioned-bucket delete needs ALL versions + delete-markers (OD-001).
- Confirm the target ACCOUNT before every operational command (this is Forensic + a Hub read).
- Offline proof bar: `~/.pyenv/versions/3.12.13/bin/python3 -m unittest`;
  `~/.pyenv/versions/3.12.13/bin/ruff check`; `env -u NODE_OPTIONS npx tsc --noEmit` (NO new
  error TYPE); `env -u NODE_OPTIONS npx prettier --write`. `gh pr create` is BROKEN — use
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`.

# STEP 0 — RE-ESTABLISH TRUE STATE (before any edit)
- SECRET SCAN the in-scope files; STOP + surface if any secret is found.
- `git fetch origin`; `git checkout main`; `git reset --hard origin/main`. List open PRs.
- `python3 scripts/check_docs.py` → expected PASS. `~/.pyenv/versions/3.12.13/bin/python3 -m
  unittest scripts.test_check_docs` → SUITE OK.
- Confirm EXPECTED TRUTHS: 4.7 = ⬜ tier 14; **4.6 = ✅** (its live pass cleared the
  register — 4.7 CANNOT begin while 4.6 is 🟡); 4.1 = ✅; the Validation Debt Register EMPTY
  (gate open). If 4.6 is still 🟡, STOP — validate 4.6 first, do not start 4.7.
- VERIFY the next free RD: `grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md | sort -u | tail`
  (expect RD-048). Register RD-048 + add its plan-table row BEFORE any living-doc reference.
- Branch off `main`: `feature/story-4.7`.

# THIS SESSION'S OBJECTIVE
Build the REJECT/INCONCLUSIVE enforcement action: a Forensic-side Lambda, invoked by
`intake_id`, that (1) reads the recorded human decision from the Hub tracking record, (2) on
`rejected` DESTROYS the raw artifact (all S3 versions + delete-markers under
`intake/<intake_id>/`) AND terminates any live detonation chamber for the intake (explicit,
not TTL), (3) on the not-decided/INCONCLUSIVE state HOLDS (destroys nothing, pushes nothing),
and (4) records a bounded, verdict-free destroy/hold OUTCOME to the Hub. FAIL-SAFE everywhere;
the derived report always survives.

# SCOPE & GUARDRAILS
- Blast radius: the new destroy/hold Lambda + its least-privilege role + the crossed outcome.
  Do NOT touch intake/lane/Hub-processing Lambdas beyond reading `human_decision` + recording
  the outcome. Reuse the 4.6 patterns (invoke shape, fail-closed gate, contract discipline).
- Out of scope: the human accept/reject UI + auto trigger (4.4); ACCEPT→push (4.6, done);
  re-executing the artifact (NEVER); the advisory verdict as a trigger; ServiceNow.
- Depends on (must be ✅): 4.1 AND 4.6.

# DEFINITION OF DONE (this session) — a PASS/FAIL GATE
- LIVE, recorded: for an intake with a recorded human `rejected`, the Forensic artifact (all
  versions) is destroyed AND any live chamber torn down; a bounded verdict-free destroy
  outcome crosses to the Hub; the derived report still exists in the Hub.
- FAIL-SAFE proven: an intake WITHOUT a recorded reject (pending/accepted) is NOT destroyed;
  INCONCLUSIVE holds (no destroy, no push). Test this hardest.
- Goes ✅ ONLY on a recorded live pass of the final code. No recorded pass → stays 🟡.
- This + 4.3 UNBLOCKS 4.4 (which closes Phase 4).

# WORKING AGREEMENT
- One story to completion. Design → build → STAKEHOLDER validates live → RECORD + flip status
  → paired commit. Branch + PR, never main directly.
- MANAGEMENT ARTIFACTS ARE FIRST-CLASS (RD-015): register RD-048 (verify next free first) +
  its plan row before any living-doc reference; RUNBOOK 4.7 ⬜→🟡 + register entry in the same
  commit; PLAN ↔ RUNBOOK exact alignment; repoint `_NEW_WORK_STORY` off 4.7 if it points at
  4.7. Run check_docs AFTER committing the status/register edit.
- At session end author the 4.7 LIVE-RUNBOOK + the next-story (4.4) handoff with a Lessons
  Learned / Carry-Forward section, BEFORE pointing the on-deck README at them (CHECK I).
- If blocked, push partial progress + a draft PR; never silently fail.
