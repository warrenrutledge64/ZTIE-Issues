# Story 3.3 (RD-038 rework — three Nova Pro risk scores)

You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting. Do NOT change anything until you have (a) READ the plan +
runbook + methodology + this story's brief (`session-briefs/story-3.3-brief.md`) + the
design record (`docs/proposals/phase3-three-score-model.md`), (b) re-established true
state (STEP 0), and (c) confirmed the Validation Debt Register state.

# WHAT CHANGED — READ THIS FIRST
Story 3.3 was first built (RD-037, PR #104) as PURE post-processing producing an
`accuracy` + `gap_analysis` `synthesis_result`. It was **never live-validated**. A
stakeholder course-correction (**RD-038**) re-scoped it. **This is a 🟡 REWORK of an
existing story, not new work.** 3.3 now produces **THREE independent 0-100 risk scores**
(static / dynamic / combined), each by a SEPARATE Amazon Nova Pro call, on a SHARED
0-100 rubric. The old `accuracy_score` is DROPPED. The list-shaped synthesis content
(candidate-false-positive list + gap list + by-kind counts) MIGRATES to Story 3.4 — do
NOT build it here.

# PROJECT IDENTITY
ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted artifact
BEFORE it reaches the PDE. Validation-gated: nothing is ✅ until a recorded live pass (the
covenant). Three accounts: Pipeline-Hub (641628980935) = brains/control plane + durable
record + Bedrock/Nova Pro; Forensic (360999005254) = self-contained blast zone (ephemeral
only); Pipeline-Sandbox (586917955591) = ZTIE→PDE handoff.

# THE JOB (RD-038)
For one `intake_id`, produce THREE independent 0-100 risk scores (higher = riskier), each
by a SEPARATE Nova Pro call over the derived Hub-side evidence:
- **Static risk score** — a Nova Pro call that sees ONLY the static lane's derived evidence
  (the static-scan findings + severities on the Hub tracking item).
- **Dynamic risk score** — a Nova Pro call that sees ONLY the dynamic lane's derived
  evidence (the sanitized behavioral telemetry / run outcome on the tracking item). A PEER
  of static, not a check on it.
- **Combined risk score** — a Nova Pro call that sees BOTH lanes' raw derived evidence
  TOGETHER (NOT the two lane scores) and forms its own independent assessment.

Record all three (+ each score's rationale + honest per-score status) as a bounded,
DERIVED, verdict-free scoring result on the SAME Hub tracking item.

# NON-NEGOTIABLE CONSTRAINTS
- **THREE SEPARATE, EVIDENCE-SCOPED Nova Pro calls.** Static call sees only static
  evidence; dynamic call sees only dynamic evidence; combined call sees both together. This
  is deliberate (chosen over one all-in-one call for true independence + fault isolation).
- **SHARED 0-100 RUBRIC.** State the SAME risk rubric (what makes a score low/medium/high/
  critical on 0-100) in all three prompts so the scores are directly comparable; only the
  evidence each call sees differs, never the scale.
- **EVIDENCE, NEVER A VERDICT.** No verdict/safe/approved/forward/pass_fail/malicious/clean
  field anywhere. Each prompt asks for a RISK SCORE (0-100) + short rationale ONLY — never
  whether the artifact is safe/unsafe/should pass/fail/be forwarded. The verdict is Story
  3.5 + the human gate.
- **REAL Nova Pro calls + exponential-backoff retry (RD-003), no mock model.** Reuse the
  3.2 `awsio.invoke_nova` pattern (backoff + full jitter, bounded attempts, returns the
  attempt count so retry is inspectable). Parse each response DEFENSIVELY into a bounded
  0-100 int; a malformed/absent/throttled response is RECORDED via THAT score's own
  `status`, never fabricated. Partial results are fine (one call failing must not sink the
  other two).
- **"RAW EVIDENCE" = the derived/sanitized Hub-side evidence, NEVER the payload/raw trace**
  (RD-008/009 intact). The combined call sees both lanes' derived evidence together — it
  does NOT see the two lane scores.
- **BOUNDED + ALLOW-LIST + OWN VERSION PIN.** The scoring-result schema is allow-list
  (additionalProperties:false everywhere), typed + bounded, verdict-free, integrity-keyed
  by intake_id + sha256, own version pin. Contract-first (regen via a new/renamed
  `scripts/gen_*_contract.py` + hash-matched bundled copy; `git diff -- schemas lambdas`
  clean).
- **PURE score-assembly logic + thin `awsio` seam** (the proven 1.2→…→3.2 pattern). All
  Nova Pro / DynamoDB I/O behind `awsio`; the assembly + parse logic pure + offline-tested.
- **SCOPED BEDROCK GRANT (this rework RE-ADDS Bedrock).** The RD-037 build had NO Bedrock
  client/grant; the rework re-adds `bedrock:InvokeModel` scoped to EXACTLY the Nova Pro
  model/inference-profile ARNs (never `*`) — copy the 3.2 correlator's IAM scoping.
- **CALL-STORM / STREAM-LOOP GUARD.** Reuse the `Decimal`-canonicalized fingerprint guard
  so the three calls fire once per settled evidence, not on every mutation (a loop now = 3×
  paid calls per mutation).
- **VALIDATION-GATED:** 3.3 flips ✅ only on a recorded LIVE pass of the FINAL reworked code
  (real Nova Pro calls; three bounded 0-100 scores land verdict-free).
- **DOCS FIRST-CLASS (RD-015):** PR-reviewed; PROJECT_PLAN ↔ RUNBOOK aligned; RD reference
  is RD-038 (already registered — do NOT invent a new RD).

# THE RD (already registered)
RD-038 is registered in `PROJECT_PLAN.md` (three-score model). Do NOT create a new RD for
the rework — it IS RD-038. Full design detail: `docs/proposals/phase3-three-score-model.md`.

# WHAT ALREADY EXISTS (reuse it)
- `lambdas/hub_synthesize/` (RD-037 build, on `main`): Hub-side, DynamoDB-stream-triggered,
  reads the tracking item, writes an integrity-bound verdict-free record, has the
  `Decimal`-canonicalized fingerprint guard + a two-layer conformance test. REUSE the
  shape; REPLACE what it produces (three scores, not accuracy/gaps) and RE-ADD the Nova Pro
  calls.
- `lambdas/hub_correlate/` (3.2, RD-035): the template for the model calls —
  `awsio.invoke_nova` (backoff+jitter, attempt count), defensive parse, honest status, the
  scoped `InvokeNovaProOnly` Bedrock policy in `ZtieHubTrackingStack`. Copy this per call.
- The evidence to score is already on the tracking item (put there by the lanes + 3.1):
  the static-scan summary, the sanitized behavioral telemetry / dynamic-run outcome, and
  the 3.1 `combined_event`. Read the derived evidence — NEVER anything raw.

# OPERATIONAL CONTEXT (state on EVERY command block)
  Build sandbox is INTEGRATIONS_ONLY (NO AWS creds; PyPI + npm BLOCKED — boto3/pytest/
  moto/jsonschema/aws-cdk-lib NOT installable). You BUILD; the USER validates live in
  CloudShell. Region us-east-1; confirm the account with `aws sts get-caller-identity`
  before EVERY operational block. Tracking table + Bedrock = HUB (641628980935). Bedrock
  model access must be ENABLED for the Hub account or the first call fails AccessDenied.
  Nova Pro via `bedrock-runtime`, inference profile `us.amazon.nova-pro-v1:0`
  (env-configurable). Tools: tests with `~/.pyenv/versions/3.12.13/bin/python3`; `ruff` at
  `~/.pyenv/versions/3.12.13/bin/ruff` (DEFAULT rules; watch RUF100 — no `# noqa` for a
  non-enabled rule; ISC004 — wrap implicit string concat in a list in parens; a blind
  `except Exception` that does NOT re-raise needs `# noqa: BLE001`); `prettier`/`tsc` need
  `env -u NODE_OPTIONS`; npm BLOCKED so `tsc --noEmit` shows ONLY the missing-`aws-cdk-lib`
  family (TS2304/2307/2339/2353/2591) — confirm the error-TYPE set matches the `main`
  baseline (a count delta in an existing type is fine, a NEW type is not). Do NOT
  prettier-reformat generated JSON contracts. Keep tests stdlib-only + boto3/botocore-
  stubbed so they pass offline.

# HARD-WON LESSONS (do NOT repeat)
- **Retry-loop test trap (from 3.2):** a fake `ClientError` for a NON-retryable code (e.g.
  `ValidationException`) must carry a 4xx status, not 429, or the retryability heuristic
  (429/5xx = retryable) retries it and your "not retried" assertion fails.
- **Deploy-gap (both modes):** BEFORE `cdk deploy` confirm the checkout carries the change
  (`git rev-parse --abbrev-ref HEAD && git log --oneline -1` + grep the stack source for
  the new marker, e.g. the Bedrock grant / the score env vars); AFTER deploy inspect the
  LIVE Lambda env + the scoped Bedrock policy. Never trust the green `UPDATE_COMPLETE`
  line. When a call "succeeds" but produces no result, READ THE LAMBDA'S OWN LOGS.
- **Two accounts, two tabs:** `sts get-caller-identity` before every block; the table +
  Bedrock are HUB; a `ResourceNotFoundException` on the table = you queried from Forensic.
- **check_docs timing:** run `python3 scripts/check_docs.py` only AFTER committing status/
  register edits; also run `python3 -m unittest scripts.test_check_docs` (SUITE line OK).
  `_NEW_WORK_STORY` stays pinned to 3.4 (a downstream ⬜) — this rework does not move it;
  confirm.
- **`gh pr create` is BROKEN** — open PRs via `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`.

# STEP 0 — RE-ESTABLISH TRUE STATE
- `git fetch origin`; `git checkout main`; `git reset --hard origin/main`. List open PRs.
- `python3 scripts/check_docs.py` → PASS. `python3 -m unittest scripts.test_check_docs` →
  SUITE OK.
- Confirm: 3.3 = 🟡 on the Validation Debt Register (reason: "being reworked to RD-038");
  RD-038 registered in PROJECT_PLAN; 3.2/3.1/2.5 ✅. Trust `main` + `check_docs`.
- Work on `feature/story-3.3` (reworking the existing story). If the old branch is stale
  vs `main`, reconcile (`git merge origin/main`, resolve, commit) before building.

# DEFINITION OF DONE — a PASS/FAIL GATE
1. For one `intake_id`, three bounded **0-100** risk scores (static / dynamic / combined),
   each from a SEPARATE Nova Pro call, on the SHARED rubric, each with a rationale + honest
   per-score status, recorded verdict-free on the tracking item.
2. The combined score reasons over BOTH lanes' raw derived evidence (not the two scores).
3. Keyed by intake_id + sha256; retry inspectable; a failed call recorded honestly (partial
   result OK, not fabricated).
4. EVIDENCE only — no verdict/safe/forward field anywhere; RD-009/RD-013 intact; scoped
   Bedrock grant (no `*`).
5. Validated LIVE (real Nova Pro calls) and RECORDED.
- Goes ✅ ONLY on a recorded live pass of the FINAL reworked code. No pass → stays 🟡.

# WORKING AGREEMENT
- Rework to completion: design → build → validate → RECORD + flip status (paired commit);
  push to `feature/story-3.3`; open a PR via `gh api …/pulls`. After merge,
  `git log main..feature/story-3.3` to confirm the whole branch landed.
- Validation drives status; the advancement gate governs advancement.
- MANAGEMENT ARTIFACTS FIRST-CLASS (RD-015): this brief + RUNBOOK + PROJECT_PLAN aligned;
  RD-038 reference correct; re-issue the 3.3 LIVE-RUNBOOK to the three-score definition; all
  via PR. Confirm `_NEW_WORK_STORY` still pinned to 3.4.
- At session end, refresh the 3.4 handoff (it now consumes three scores + inherits the
  migrated candidate-FP/gap lists) with THIS session's real Lessons Learned.
- If blocked, push partial progress + a draft PR; surface the blocker; never silently fail.
