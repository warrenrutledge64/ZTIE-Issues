# Session Prompt — Story 4.4 (Interactive accept/reject control (Hub) — human gate UI + signer + auto-delivery) — CLOSES Phase 4 — executor-facing

You are the execution agent for the ZTIE project. Read this fully before acting. Do NOT change
anything until you have (a) READ the plan + runbook + methodology + this story's brief
(`session-briefs/story-4.4-brief.md`) + `docs/architecture/AUTHENTICATED_DECISIONS.md`, (b)
re-established true state (STEP 0), and (c) confirmed the validation-gate state this story
depends on (STEP 0).

# PROJECT IDENTITY
ZTIE is a four-phase, AWS-native security pipeline that fully inspects every untrusted artifact
BEFORE it may reach the PDE. Three accounts: Pipeline-Hub (641628980935) = brains/control plane
+ durable tracking + the human accept/reject gate; Forensic (360999005254) = self-contained
blast zone; Pipeline-Sandbox (586917955591) = the ZTIE→PDE handoff landing zone. Phase 4 is
nearly done: 4.1/4.2/4.3/4.5/4.6 ✅ and **4.7 ✅** (REJECT→destroy). **4.4 is the LAST pipe
story of Phase 4 — it CLOSES the phase.** Validation covenant: nothing is ✅ until a recorded
live pass of the final code.

# ⚠️ REWORK-AWARE (RD-048/RD-049) — the trust model 4.4 MUST use
The Hub is STRICTLY the control plane; **no spoke ever reads into it** (RD-048). 4.4 is the
**SIGN + DELIVER** side of the authenticated-decision primitive (the mirror of 4.6/4.7's verify
side). On a human click, 4.4 records the durable `human_decision` on the Hub tracking item AND
produces a Hub-signed `decision.token.v1` (`aws kms sign` with the H.2 `ZtieDecisionSigningStack`
key — Hub-only `kms:Sign`) AND delivers it ONE-DIRECTIONALLY Hub→Forensic to invoke 4.6
(`accepted`) / 4.7 (`rejected`). INCONCLUSIVE / hold issues NO token (the fail-safe default 4.7
already honors). Reuse the vendored `lib/decision_auth` canonical bytes so the Hub signs exactly
what the spokes verify.

# WHERE THIS STORY SITS (build tier + position)
Story 4.4 is build tier 16 (dep 4.3 tier 15 + 4.7 tier 14). This session ADVANCES a tier
(15→16) — at STEP 0 re-confirm the ENTIRE new dependency set is ✅ AND the Validation Debt
Register is EMPTY (the advancement gate). It CLOSES Phase 4 (all other P4 pipe stories are ✅).

SEQUENCING — 4.4 is the first-OPEN Ready-now pipe story ONCE 4.7 is ✅ (it depends on 4.7). It
CANNOT start while 4.7 is 🟡. Confirm at STEP 0 that 4.7's live pass is recorded + the register
is empty.

# WHAT THIS STORY IS
NEW FEATURE story — the HUMAN ENFORCEMENT GATE (the sign + deliver side). It ENABLES the 4.3
dashboard's DISABLED Approve/Reject surface behind an authenticated Hub action, records the
durable `human_decision`, signs a `decision.token.v1`, and delivers it Hub→Forensic to drive
4.6/4.7. The one sentence that prevents the biggest error: **only a human's explicit
accept/reject — signed by the Hub — drives an action; the advisory `recommended_verdict`
(RD-040) NEVER does, and INCONCLUSIVE issues no token (a hold).**

# NON-NEGOTIABLE CONSTRAINTS
- PLAN FIRST GATE: before writing code, outline the UI action + how it authenticates, recording
  the durable `human_decision`, the Hub-side sign (canonical bytes + the H.2 key), the
  one-directional Hub→Forensic delivery to 4.6/4.7, and the INCONCLUSIVE hold; resolve the FIVE
  design forks in the brief; get explicit approval before generating the implementation.
- ACT ONLY ON A HUMAN DECISION (RD-040): the advisory verdict is never the trigger. INCONCLUSIVE
  = no token = hold.
- THE HUB SIGNS, NEVER LETS A SPOKE READ IT (RD-048): delivery is one-directional Hub→Forensic;
  no Forensic→Hub read is introduced.
- Production-quality; AWS-native; VALIDATION-GATED; RESTORE-POINT discipline; DOCS ARE
  FIRST-CLASS (RD-015): PLAN ↔ RUNBOOK exact.

# OPERATIONAL CONTEXT
Build sandbox is INTEGRATIONS_ONLY (no live AWS creds; PyPI + npm registry BLOCKED). You BUILD;
the STAKEHOLDER validates live in CloudShell (split-brain, RD-055 — the independent validator
authors the DoD + runbook blind from the PR; you author neither). Region us-east-1. This is a
HUB-account story (the UI + signer are in the Hub; delivery reaches Forensic; 4.6/4.7 act
there). Run `aws sts get-caller-identity` before every operational block.

# HARD-WON LESSONS (apply directly — from 4.6 + 4.7)
- **⛔ NON-SKIPPABLE post-deploy CODE-ASSET gate** ([`story-2.4R-DEPLOY-VERIFY.md`](story-2.4R-DEPLOY-VERIFY.md)):
  before concluding ANY live validation, grep the LIVE Lambda zip for THIS story's structural
  markers (the sign path / the delivery path) + a regression guard that any probe marker is
  ABSENT. NEVER an env-var read; NEVER trust a green `UPDATE_COMPLETE`.
- The authenticated-decision primitive is built (H.2) + proven both directions (4.6 accept, 4.7
  reject). Reuse the H.2 key + the canonical `decision.token.v1` bytes: `json.dumps(token,
  sort_keys=True, separators=(",",":"))` over EXACTLY the six token keys; sign with `aws kms
  sign --message-type RAW --signing-algorithm ECDSA_SHA_256`.
- Pass any Hub public key / multi-line value to CDK as SINGLE-LINE base64 (the 4.6 truncation
  defect, PR #153); dump the live value after deploy to confirm it is the full value.
- If 4.4 adds a new RD-013 kind, REDEPLOY `ZtieHubTrackingStack` before the live run (the
  deploy-gap class), then verify the crossed field landed.
- DynamoDB Number → Decimal: coerce any numeric read off the tracking item; never strict
  `isinstance(int)`; add a Decimal regression case.
- Offline proof bar: `~/.pyenv/versions/3.12.13/bin/python3 -m unittest`;
  `~/.pyenv/versions/3.12.13/bin/ruff check`; `env -u NODE_OPTIONS npx tsc --noEmit` (NO new
  error TYPE); `env -u NODE_OPTIONS npx prettier --write`. `gh pr create` is BROKEN — use
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`.

# STEP 0 — RE-ESTABLISH TRUE STATE (before any edit)
- SECRET SCAN the in-scope files; STOP + surface if any secret is found.
- `git fetch origin`; `git checkout main`; `git reset --hard origin/main`. List open PRs.
- `python3 scripts/check_docs.py` → expected PASS. `~/.pyenv/versions/3.12.13/bin/python3 -m
  unittest scripts.test_check_docs` → SUITE OK.
- Confirm EXPECTED TRUTHS on `main`: 4.4 = ⬜ tier 16; **4.3 ✅**, **4.7 ✅**, **4.6 ✅**,
  **H.2 ✅**; the **Validation Debt Register EMPTY** (gate DISARMED — 4.7's live pass recorded).
  If 4.7 is still 🟡, STOP — 4.4 cannot start until 4.7 clears.
- Verify the next free RD (`grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md | sort -u | tail`); register
  a new RD only for a genuinely new sub-decision (e.g. the delivery transport), its plan row
  BEFORE any living-doc reference (CHECK E literal).
- Branch off `main`: `feature/story-4.4`.

# THIS SESSION'S OBJECTIVE
Build the human accept/reject gate: enable the 4.3 dashboard control behind an authenticated Hub
action; on a click record the durable `human_decision` on the Hub item, sign a canonical
`decision.token.v1` with the H.2 key, and deliver it one-directionally Hub→Forensic to invoke
4.6 (accept) / 4.7 (reject); INCONCLUSIVE holds (no token). CLOSES Phase 4.

# SCOPE & GUARDRAILS
- Blast radius: the Hub-side action/signer + delivery wiring + enabling the 4.3 control. Keep
  the 4.3 render otherwise UNCHANGED. Do NOT modify 4.6/4.7's verify side (they already act on a
  signed token).
- Out of scope: re-executing the artifact (NEVER); the advisory verdict as a trigger; browser
  auth beyond what's needed (4.8 owns Cognito); ServiceNow.
- Depends on (must be ✅): 4.3 AND 4.7 (AND 4.6, H.2).

# DEFINITION OF DONE (this session) — a PASS/FAIL GATE
- LIVE, recorded: a human ACCEPT records `human_decision=accepted`, signs + delivers a token,
  4.6 pushes; a human REJECT records `human_decision=rejected`, signs + delivers a `rejected`
  token, 4.7 destroys the artifact + chamber; INCONCLUSIVE holds (no token, no action). The
  advisory verdict triggers nothing. No Forensic→Hub read.
- Goes ✅ ONLY on a recorded live pass of the final code. No recorded pass → stays 🟡.
- **This CLOSES Phase 4** — on the live pass, flip the P4 Progress-Summary row ✅ + capture the
  phase restore point (RESTORE.md + BOM.md).

# WORKING AGREEMENT
- One story to completion. Design → build → STAKEHOLDER validates live → RECORD + flip status →
  paired commit. Branch + PR, never main directly.
- MANAGEMENT ARTIFACTS ARE FIRST-CLASS (RD-015): register a new RD only if genuinely needed
  (verify next free first) + its plan row before any living-doc reference; RUNBOOK 4.4 ⬜→🟡 +
  register entry in the same commit; PLAN ↔ RUNBOOK exact alignment; repoint `_NEW_WORK_STORY`
  off 4.4. Run check_docs AFTER committing the status/register edit.
- At session end author the 4.4 LIVE-RUNBOOK + the next-story handoff (Phase 4 is closed after
  4.4 — next is the F&H B.1 track / 4.9 / 4.8 per the recorded reorder) BEFORE pointing the
  on-deck README at them (CHECK I).
- If blocked, push partial progress + a draft PR; never silently fail.
