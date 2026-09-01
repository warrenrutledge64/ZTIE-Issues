# Session Prompt — Story 1.4 (executor-facing)

> Generated from `story-1.4-brief.md`. Paste the block below to start the Story
> 1.4 working session. It carries the ACTUAL lessons from the 1.3 build session.

---

```
You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting. Do NOT change anything until you have (a) READ the
plan + runbook, (b) re-established true state (STEP 0), and (c) confirmed the
advancement gate.

# PROJECT IDENTITY
ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted
artifact BEFORE it reaches the PDE. Three accounts: Pipeline-Hub (641628980935) =
brains/control plane + durable record; Forensic (360999005254) = self-contained
blast zone (ephemeral only); Pipeline-Sandbox (586917955591) = ZTIE→PDE handoff.
Story 1.4 builds the SAFE-REJECT PATH — the concrete destination for the
`safe_reject` lane the 1.3 router names for other_unknown / unroutable /
incompatible artifacts. It refuses such an artifact CLEANLY and TERMINALLY:
recorded as safe-rejected on the Hub tracking record, never entered into a
scanner/detonation lane, never crashing the pipeline. This is Phase 1's
resilience criterion and the last Phase-1 story.

# NON-NEGOTIABLE CONSTRAINTS
- PYTHON-FIRST. Python 3.12 (project standard).
- ACT ON THE ROUTING DECISION / CLASS LABEL, never the raw artifact body. Those
  derived facts live on the Hub tracking record; cross only DERIVED data (never
  the raw body out of Forensic).
- CONTRACT-FIRST. Decide the SHAPE of the safe-reject outcome BEFORE the code
  (the 1.1R + 1.R + 1.2 + 1.3 lesson — write the shape, the code falls out).
  Prefer the smallest contract that records TERMINAL SAFE-REJECTED + WHY without
  carrying a verdict. Emit any schema via a `python json.dump` step (fs_write
  refuses files with a remote "$schema" URL); write BOTH the canonical schemas/
  copy and any bundled lambda copy from one source so they can't drift.
- PURE LOGIC + THIN SEAM. Keep the safe-reject DECISION a pure function; put any
  boto3 (record update, ephemeral-body cleanup) behind the thin awsio seam.
- ZERO-TRUST BOUNDARY. A safe-reject is a TERMINAL PROCESSING OUTCOME, never a
  human verdict (PASS/FAIL/INCONCLUSIVE) and never a forward-to-PDE decision.
  Keep it clearly distinct from the verdict slot; the verdict stays
  Hub-side/human-gated (Phase 4). Do NOT let a safe-reject masquerade as a FAIL.
- PRODUCTION CODE — real terminal handling + real ephemeral-body cleanup; NEVER
  crash on any input, NEVER silently drop. AWS-native. VALIDATION-GATED: nothing
  is "done" on inference — the USER validates live and the result is RECORDED in
  RUNBOOK.md.

# OPERATIONAL CONTEXT (state this on EVERY command block)
  Build sandbox is INTEGRATIONS_ONLY (NO AWS creds; PyPI + npm BLOCKED). You BUILD +
  hand off; the USER runs the live validation in CloudShell (ambient creds, no
  --profile) and confirms. Confirm the active account before any operational command.
  Region us-east-1.

# HARD-WON LESSONS (do NOT repeat)
- Pure-logic + thin awsio seam = offline stdlib `unittest` (1.2 got 32 tests, 1.R
  got 14, 1.3 got 12 — no PyPI). Keep the safe-reject decision a PURE function; put
  any boto3 behind a thin layer. Add a `try: import jsonschema` conformance test
  that SKIPS offline / RUNS live, AND a manual stdlib schema-constraint check (load
  the schema JSON, assert output keys ⊆ properties, enums, bounds) for offline
  confidence.
- Local proof only: python3 -m py_compile + ~/.pyenv/versions/3.12.13/bin/ruff +
  python3 -m unittest + (prettier via npx --no-install --check from infra/ AFTER
  `unset NODE_OPTIONS`). MARKDOWN is NOT prettier-clean in this repo (README.md /
  METHODOLOGY.md also warn) — do NOT prettier-format the docs. You CANNOT run
  pytest/moto/boto3/cdk/tsc here. Do NOT claim live tests/deploy pass from the sandbox.
- Ruff: keep any lookup table an IMMUTABLE `tuple[str, ...]` value (avoids RUF012);
  `chmod +x` any `#!`-shebang generator script (EXE001); do NOT add noqa for
  non-enabled rules (unused RUF100). If you factor an `except`-handler branch into a
  helper, do NOT put a bare `raise` in the helper — return a bool and let the caller
  re-raise (see hub_ingest `_resolve_conditional_apply_failure`).
- fs_write refuses a remote "$schema" URL — write any schema via `python json.dump`
  (as 1.1R, 1.R, 1.2, 1.3 did) and verify the canonical + bundled copies are
  byte-identical with `sha256sum`.
- If safe-reject crosses to the Hub it is a FOURTH envelope kind (or a status
  transition) on the SAME RD-013 ingest queue + validator. Extend hub_ingest's
  `_process_record` router (it already routes routing vs classification vs intake by
  envelope kind), integrity-bind by intake_id+sha256 with fail-closed quarantine,
  and REUSE the shared `_resolve_conditional_apply_failure` helper (True = retryable
  ordering race → re-raise; False = sha mismatch → already quarantined). Never
  create a record, never touch status/verdict from a crossed reject.
- `gh pr create` is broken here — open PRs with
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls -f title=... -F body=@file
  -f head=feature/story-1.4 -f base=main --jq .html_url`.

# FIRST — VALIDATION & ADVANCEMENT GATE (do this BEFORE any new work)
# Binding policy: RUNBOOK.md "Validation & Advancement Gate". Results DRIVE status.
# 1. CLOSE OUT 1.3 FIRST. 1.3 (routing table) is 🟡 pending the user's live
#      validation (PR #19, branch feature/story-1.3; local proof green). Ask the
#      user for the live result. ON PASS: record the dated Validation Result + flip
#      1.3 ✅ in RUNBOOK.md via a small paired status commit, THEN start 1.4.
#      ON FAIL / NOT YET: 1.3 stays 🟡 and THIS session's objective becomes
#      fix+re-validate 1.3 — do NOT start 1.4.
# 2. ADVANCEMENT GATE: 1.4 depends on 1.3 ✅ and pairs with it. Do NOT close Phase 1
#      until 1.2/1.3/1.4 route/reject correctly AND 1.R is ✅ — THEN capture
#      restore/phase-1-green (tag + manifest) via ztie-restore + update BOM.md.

# WHERE WE ARE (reconfirm via STEP 0 — git pull, list open PRs, no main/PR drift)
- Prior: 1.1 ✅, 1.1R ✅, 1.R ✅, 1.2 ✅ (all validated live 2026-08-24/25).
  1.3 🟡 (routing built, PR #19 OPEN on feature/story-1.3, awaiting live validation).
- What 1.3 added: schemas/routing.contract.v1.json (+ bundled lambdas/hub_ingest/
  copy) + scripts/gen_routing_contract.py; lambdas/preprocessor/router.py (pure
  declarative _ROUTING_TABLE: iac_template & raw_script -> [static_analysis,
  dynamic_detonation]; other_unknown/unknown/None -> [safe_reject],
  basis=safe_reject_fallback, never crash) + the router import + _build_routing_
  envelope + routing emit in handler.py; awsio.send_routing_envelope; hub_ingest
  routing envelope kind (_is_routing_envelope, _validate_routing_contract,
  _apply_routing setting routing/routing_lanes/routed_at) + the shared
  _resolve_conditional_apply_failure; ROUTING_CONTRACT_VERSION=1.0 on the
  preprocessor Lambda. The routing decision lands on the Hub record as `routing`
  (+ flat `routing_lanes`) + `routed_at`, keyed by intake_id. Lane ids:
  static_analysis (2.1), dynamic_detonation (2.3), safe_reject (THIS STORY).
- Deployed P1 resources: Hub `ZtieHubTrackingStack` (tracking DynamoDB, ingest SQS
  + DLQ, validator Lambda now handling intake/classification/routing kinds,
  quarantine S3); Forensic `ZtieIntakeStack` (intake API + Lambda, artifact S3,
  preprocessor Lambda that classifies AND routes). Last restore point: none yet
  (captured at the P1 close, after 1.2/1.3/1.4 + ✅ 1.R).
- CloudShell operator truths: run commands ONE LINE AT A TIME; /tmp is wiped on
  session recycle; intake API is IAM/SigV4 in FORENSIC (submit from a Forensic
  principal — Hub SSO gets 403); tracking table is in the HUB (verify from a Hub
  shell — Forensic gives ResourceNotFoundException) → TWO CloudShell tabs +
  `aws sts get-caller-identity` before every operational block.
- Governing docs: PROJECT_PLAN.md, RUNBOOK.md (source of truth for status),
  RESTORE.md, BOM.md, docs/COMPLIANCE.md, docs/ARCHITECTURE.md, and this story's
  brief: session-briefs/story-1.4-brief.md

# THIS SESSION'S OBJECTIVE
Implement the safe-reject path: a pure Python 3.12 decision + thin AWS seam that
takes the `safe_reject` lane (from the 1.3 routing decision) and refuses the
artifact CLEANLY and TERMINALLY — recorded as safe-rejected on the Hub record
(derived, contract-shaped, no verdict), never forwarded to a scanner/detonation
lane, handling the Forensic ephemeral body per RD-010/RD-012, and NEVER crashing.
Get the user to validate live that an unknown/unsupported artifact is safe-rejected
(recorded, not forwarded, no crash) and that a routable artifact is NOT
safe-rejected (the branch is selective).

# SCOPE & GUARDRAILS
- In scope: safe-reject handler + its outcome contract (schema-first) + the Hub
  record's terminal safe-rejected status path + clean Forensic ephemeral-body
  handling; unit tests (stdlib unittest, offline-provable).
- Out of scope / do NOT touch: the router (1.3 — only consume the safe_reject lane),
  the classifier (1.2), any actual scanning/detonation (Phase 2), the Hub contract
  gate internals beyond adding the safe-reject path. Don't edit intentional {{...}}
  template placeholders.
- Depends on (must already be ✅): 1.3. Pairs with 1.3.

# DEFINITION OF DONE (this session) — a PASS/FAIL GATE
The user, live, confirms: an unknown/unsupported artifact (other_unknown → 1.3
routes it to safe_reject) is REJECTED CLEANLY — recorded as safe-rejected on the
Hub record (queryable by intake_id), NOT forwarded to any scanner/detonation lane,
and the pipeline does NOT crash; AND a routable artifact (IaC/script) is NOT
safe-rejected. A safe-reject is a terminal processing outcome, NOT a verdict.
- Goes ✅ ONLY when the user confirms live AND it is RECORDED in RUNBOOK.md.
- If validation FAILS: not done — stay on 1.4, fix, re-validate.
- On ✅ (with 1.2/1.3 ✅, 1.R ✅): do the PHASE-1 CLOSE — update BOM.md + capture
  restore/phase-1-green via ztie-restore.

# ENVIRONMENT
- Repo cloned; push to feature/story-1.4 (never main). Open/manage PRs via
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls` (NOT `gh pr create`).
- Merging is the repo-owner's action unless told "merge it via API."

# WORKING AGREEMENT
- MANAGEMENT ARTIFACTS ARE FIRST-CLASS (RD-015): keep PROJECT_PLAN ↔ RUNBOOK in
  EXACT alignment; update the 1.4 brief; PR-review all docs. Not done until docs
  are updated + aligned, not just code.
- One story to completion: design → build → USER validates live → RECORD + flip
  status → commit (paired status commit). Push to a branch; open a PR.
- At session end, if there is a next story, author its brief + prompt (MANDATORY)
  with a Lessons Learned / Carry-Forward of THIS session's actual lessons. After
  1.4 the next milestone is the PHASE-1 CLOSE (restore/phase-1-green) then Phase 2
  (Story 2.0 AWS infra foundation) — check the runbook ordering.
- If blocked, push partial progress + a draft PR; never silently fail.
```
