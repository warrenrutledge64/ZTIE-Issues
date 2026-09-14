# Session Prompt — Story 4.7 (REJECT → destroy artifact + detonation chamber in Forensic / INCONCLUSIVE → hold) — executor-facing

You are the execution agent for the ZTIE project. Read this fully before acting. Do NOT
change anything until you have (a) READ the plan + runbook + methodology + this story's brief
(`session-briefs/story-4.7-brief.md`) + `docs/architecture/AUTHENTICATED_DECISIONS.md`, (b)
re-established true state (STEP 0), and (c) confirmed the validation-gate state this story
depends on (STEP 0).

# PROJECT IDENTITY
ZTIE is a four-phase, AWS-native security pipeline that fully inspects every untrusted
artifact BEFORE it may reach the PDE. Three accounts: Pipeline-Hub (641628980935) =
brains/control plane + durable tracking + the human accept/reject gate; Forensic
(360999005254) = self-contained blast zone (intake, lanes, the raw artifact, ephemeral
detonation host); Pipeline-Sandbox (586917955591) = the ZTIE→PDE handoff landing zone. Phase
4 is under way: 4.1/4.2/4.3/4.5 ✅, and **4.6 (ACCEPT→push, reworked per RD-048/RD-049) is the
sibling just completed (✅ validated live 2026-09-14)**. Validation covenant: nothing is ✅
until a recorded live pass of the final code.

# ⚠️ REWORK-AWARE (RD-048/RD-049) — the trust model 4.7 MUST use
The Hub is STRICTLY the control plane; **no spoke ever reads into it** (RD-048). The human
decision reaches a spoke as a **Hub-signed `decision.token.v1`** that the spoke **verifies
OFFLINE** against an embedded Hub public key (RD-049; primitive `lib/decision_auth` + the Hub
`ZtieDecisionSigningStack`, built + validated live as **H.2 ✅**). The reworked 4.6 verifies an
`accepted` token this way; **4.7 verifies a `rejected` token the SAME way** (call
`verify.verify_decision(..., expected_decision="rejected", ...)`). 4.7 must NOT read the Hub —
its role has **NO `dynamodb`** and its env has **NO `TRACKING_TABLE`**; it carries
`HUB_PUBLIC_KEY_PEM` + `TRUSTED_KEY_IDS` and verifies offline. (INCONCLUSIVE issues NO token —
so a HOLD is simply "no valid `rejected` token present", the fail-safe default.)

# WHERE THIS STORY SITS (build tier + position)
Story 4.7 is build tier 14 (dep 4.1 tier 13 + H.2 tier 6) — the tied, independent sibling of
4.6. This session does NOT advance to a new tier or a new phase. It IS on the Phase-4-closure
critical path: **4.4** (tier 16) depends on **4.3 + 4.7**.

SEQUENCING — 4.7 IS THE FIRST-OPEN READY-NOW STORY (4.6 ✅ 2026-09-14, register empty); NO
CONFIRMATION NEEDED TO START IT (per the SESSION_PROMPT_TEMPLATE no-confirmation clause), once
STEP 0 confirms the register empty + gate open. A stakeholder decision is needed ONLY to
deviate (a reorder logged in `WORK_LOG.md`) or for a genuine design fork inside the story (the
PLAN FIRST GATE).

# WHAT THIS STORY IS
NEW FEATURE story — the REJECT/INCONCLUSIVE ENFORCEMENT ACTION, the destroy/hold half of the
human gate (4.6 is the push half). On a **verified Hub-signed `rejected` token**, ZTIE
**destroys** the raw artifact **and** its detonation chamber in Forensic (explicit teardown,
not TTL); on INCONCLUSIVE it **holds** at the approval gate. The one sentence that prevents the
biggest category error: **4.7 destroys ONLY on a verified Hub-signed `rejected` token — NEVER
on the advisory `recommended_verdict`** (RD-040); INCONCLUSIVE is a HOLD (no destroy, no push).
Fail-safe: absent a genuine signed REJECT, nothing is destroyed. Decoupled from the human UI +
auto trigger (4.4). The derived report always survives in the Hub.

# NON-NEGOTIABLE CONSTRAINTS
- PLAN FIRST GATE: before writing code, outline the destroy/hold mechanism, the accounts +
  trust direction (Hub signs → Forensic verifies OFFLINE → Forensic destroys → bounded outcome
  crosses to the Hub), the token-verify gate (`expected_decision="rejected"`), what "destroy
  the artifact" (all S3 versions + delete-markers) and "destroy the chamber" (terminate the
  ephemeral EC2 if running) mean, and the crossed outcome; resolve the FIVE design forks in the
  brief; get explicit approval before generating the implementation.
- DESTROY ONLY ON A VERIFIED SIGNED `rejected` TOKEN (RD-040/RD-048/RD-049): never the advisory
  verdict, never an unsigned/spoke-asserted decision. FAIL-SAFE: no valid `rejected` token →
  no destroy. INCONCLUSIVE → HOLD (no destroy, no push).
- NO SPOKE→HUB READ (RD-048): verify OFFLINE via the vendored `lib/decision_auth`; the role has
  NO `dynamodb`, env has NO `TRACKING_TABLE`. Docker-bundle the Lambda (`cryptography` for the
  ECDSA verify), like `pde_handoff`/`hub_ingest`.
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
story (the artifact + chamber are in Forensic 360999005254; the decision is a Hub-signed token
verified OFFLINE — NO Hub read; only a bounded outcome crosses to the Hub). Run `aws sts
get-caller-identity` before every operational block.

# HARD-WON LESSONS (do NOT repeat — from the 4.6 rework + live validation)
- Verify the DEPLOYED resource after any deploy (role policy has NO `dynamodb`; env has
  `HUB_PUBLIC_KEY_PEM` + `TRUSTED_KEY_IDS`, NO `TRACKING_TABLE`) — a green UPDATE_COMPLETE can
  ship stale code / the wrong checkout / wrong account.
- Pass the Hub public key to CDK as SINGLE-LINE base64 (`-c hubPublicKeyPemBase64=$(base64 -w0
  pub.pem)`, decoded by `bin/ztie-infra.ts`). A multi-line PEM via `-c hubPublicKeyPem="$(cat)"`
  TRUNCATES to a 27-byte header, so offline verify fail-closes with `bad_signature` on the
  happy path (this cost a redeploy in 4.6 — PR #153). After deploy, dump the live
  `HUB_PUBLIC_KEY_PEM` and confirm it is the full ~178-byte PEM, not 27 bytes.
- If 4.7 adds a NEW RD-013 outcome kind/value, REDEPLOY `ZtieHubTrackingStack` so the live
  `hub_ingest` validator knows it — otherwise the crossed outcome is quarantined and the Hub
  item field stays null (the 4.6 deploy-gap; cost a Hub redeploy + re-invoke). Verify the
  outcome landed on the tracking item after the redeploy.
- **(from 2.2G, 2026-09-14 — a THIRD form of the same deploy-gap)** BUMPING a crossing
  contract's version (or adding a value to a Hub-validated enum) has the SAME failure mode: the
  Hub gate pins the version and QUARANTINES a mismatch fail-closed, so `ZtieHubTrackingStack`
  must be redeployed to accept the new version BEFORE the emitting lane ships it, and you must
  dump the LIVE ingest env to confirm the new pin took (2.2G bumped the static-scan summary to
  v1.2 for the `gitleaks` tool enum and set `SUMMARY_CONTRACT_VERSION=1.2` on both the Hub gate
  and the emitting lane; the LIVE-RUNBOOK sequences the Hub redeploy first). Same class as the
  collected-kind (2.6) + handoff-kind (4.6) gaps.
- **(from 2.2G) RD-050 is now TAKEN** — re-verify the next free RD number
  (`grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md | sort -u | tail`) before registering any new
  decision. And if 4.7 authors a NEW living template file, add it to `check_docs.py`'s
  `TEMPLATE_FILES` frozenset or CHECK F fails on its `{{placeholders}}` (2.2G had to add
  `docs/LIVE_RUNBOOK_TEMPLATE.md` — a pre-existing gap).
- **(from 2.2G) STEP-0 expected truth:** 4.7 can only START once **2.2G is ✅** (its live pass
  clears the register). If 2.2G is still 🟡 (the register is non-empty), STOP — validate 2.2G
  first (`docs/session-briefs/story-2.2-G-LIVE-RUNBOOK.md`); do not open 4.7 with the gate armed.
- Canonical bytes must match: `aws kms sign --message-type RAW --signing-algorithm
  ECDSA_SHA_256` over `json.dumps(token, sort_keys=True, separators=(",",":"))` of EXACTLY the
  six token keys. A `bad_signature` on the happy path = signed bytes ≠ verifier's canonical, or
  embedded PEM ≠ signing key; diagnose with `aws kms verify` of the same canonical file.
- FAIL-SAFE gate is the hardest invariant — destroy ONLY on a verified `rejected`; test it from
  every angle offline (a fake seam recording whether a destroy happened + a stub verifier for
  no-token / bad-sig / `accepted` / sha-mismatch / stale / untrusted-key).
- DynamoDB Number → Decimal: coerce any numeric field read off the Hub item; never strict
  isinstance(int); add a Decimal regression case.
- Versioned-bucket delete needs ALL versions + delete-markers (OD-001).
- Three accounts, three tabs; confirm the target ACCOUNT before every operational command; feed
  commands ONE LINE AT A TIME; `/tmp` + shell vars wiped on a CloudShell recycle.
- Offline proof bar: `~/.pyenv/versions/3.12.13/bin/python3 -m unittest`;
  `~/.pyenv/versions/3.12.13/bin/ruff check`; `env -u NODE_OPTIONS npx tsc --noEmit` (NO new
  error TYPE); `env -u NODE_OPTIONS npx prettier --write`. `gh pr create` is BROKEN — use
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`.

# STEP 0 — RE-ESTABLISH TRUE STATE (before any edit)
- SECRET SCAN the in-scope files; STOP + surface if any secret is found.
- `git fetch origin`; `git checkout main`; `git reset --hard origin/main`. List open PRs.
- `python3 scripts/check_docs.py` → expected PASS. `~/.pyenv/versions/3.12.13/bin/python3 -m
  unittest scripts.test_check_docs` → SUITE OK.
- Confirm EXPECTED TRUTHS: 4.7 = ⬜ tier 14; **4.6 = ✅** (its live pass 2026-09-14 cleared the
  register); **H.2 = ✅**; 4.1 = ✅; the Validation Debt Register EMPTY (gate open). If the
  register is non-empty, STOP — clear the open entry first, do not start 4.7.
- Do NOT invent a "reject decision" RD — 4.7 implements RD-047 + RD-048/RD-049. Register a new
  RD only if the destroy-outcome crossing is a genuinely new decision; VERIFY the next free
  number first: `grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md | sort -u | tail`, and add its
  plan-table row BEFORE any living-doc reference (CHECK E literal).
- Branch off `main`: `feature/story-4.7`.

# THIS SESSION'S OBJECTIVE
Build the REJECT/INCONCLUSIVE enforcement action: a Forensic-side Lambda, invoked with
`{intake_id, decision_token, signature, artifact_s3_key?}`, that (1) VERIFIES the Hub-signed
`decision.token.v1` OFFLINE via the vendored `lib/decision_auth`
(`verify.verify_decision(expected_decision="rejected")`), (2) on a verified `rejected` DESTROYS
the raw artifact (all S3 versions + delete-markers under `intake/<intake_id>/`) AND terminates
any live detonation chamber for the intake (explicit, not TTL), (3) on no-valid-`rejected`-token
(INCONCLUSIVE / pending) HOLDS (destroys nothing, pushes nothing), and (4) records a bounded,
verdict-free destroy/hold OUTCOME to the Hub. FAIL-SAFE everywhere; the derived report always
survives; NO Hub read.

# SCOPE & GUARDRAILS
- Blast radius: the new destroy/hold Lambda + its least-privilege role + the crossed outcome.
  Do NOT touch intake/lane/Hub-processing Lambdas beyond the (possibly new) ingest kind for the
  destroy/hold outcome. Reuse the 4.6 rework patterns (invoke shape, token-verify gate, vendored
  `lib/decision_auth`, contract discipline, base64-PEM context).
- Out of scope: the human accept/reject UI + auto trigger + the Hub sign-side (4.4); ACCEPT→push
  (4.6, done); re-executing the artifact (NEVER); the advisory verdict as a trigger; ServiceNow.
- Depends on (must be ✅): 4.1 AND H.2.

# DEFINITION OF DONE (this session) — a PASS/FAIL GATE
- LIVE, recorded (three accounts): the Hub signs a `rejected` `decision.token.v1`; the Forensic
  destroyer verifies it OFFLINE and destroys the artifact (all versions) AND any live chamber;
  a bounded verdict-free destroy outcome crosses to the Hub; the derived report still exists.
- FAIL-SAFE proven from every angle: no token / bad signature / `accepted` / sha-mismatch /
  stale / untrusted-key → NO destroy; INCONCLUSIVE (no `rejected` token) holds (no destroy, no
  push). Live destroyer role has NO `dynamodb`; env has NO `TRACKING_TABLE`. Test this hardest.
- Goes ✅ ONLY on a recorded live pass of the final code. No recorded pass → stays 🟡.
- This + 4.3 UNBLOCKS 4.4 (which closes Phase 4).

# WORKING AGREEMENT
- One story to completion. Design → build → STAKEHOLDER validates live → RECORD + flip status
  → paired commit. Branch + PR, never main directly.
- MANAGEMENT ARTIFACTS ARE FIRST-CLASS (RD-015): only register a new RD if genuinely needed
  (verify next free first) + its plan row before any living-doc reference; RUNBOOK 4.7 ⬜→🟡 +
  register entry in the same commit; PLAN ↔ RUNBOOK exact alignment; repoint `_NEW_WORK_STORY`
  off 4.7 if it points at 4.7. Run check_docs AFTER committing the status/register edit.
- At session end author the 4.7 LIVE-RUNBOOK + the next-story (4.4) handoff with a Lessons
  Learned / Carry-Forward section, BEFORE pointing the on-deck README at them (CHECK I).
- If blocked, push partial progress + a draft PR; never silently fail.
