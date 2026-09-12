You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting. Do NOT change anything until you have (a) READ the
plan + runbook + methodology + this story's brief (`session-briefs/story-2.6-brief.md`),
(b) re-established true state (STEP 0), and (c) confirmed the Validation Debt Register
state + advancement gate.

# PROJECT IDENTITY
ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted artifact
BEFORE it reaches the PDE. Work is validation-gated: nothing is ✅ until a recorded live
pass (the covenant). Three accounts: Pipeline-Hub (641628980935) = brains/control plane
+ durable record; Forensic (360999005254) = self-contained blast zone (ephemeral only);
Pipeline-Sandbox (586917955591) = ZTIE→PDE handoff. Story 2.6 adds the PARALLEL
ORCHESTRATION that closes Phase 2: after routing, FORK a routable artifact into BOTH
inspection lanes CONCURRENTLY — the static lane (2.1 scanners + 2.2 compliance/signature
enrichment) and the dynamic lane (2.3 detonation) — then JOIN their two derived outputs
into one collected record ready for Phase-3 aggregation.

# WHAT THIS STORY IS (nature + gate role)
NEW FEATURE story. It may begin ONLY if its Depends-on are all ✅ AND the Validation
Debt Register is empty. **Both are already true as of this prompt:** 2.1 ✅ and 2.3 ✅;
the Validation Debt Register is EMPTY; `check_docs.py` PASSes. The advancement gate is
OPEN — 2.6 may start feature work. STEP 0 must still RE-CONFIRM this on `main` (trust
`main` + `check_docs` over this prompt) before touching anything — verify, do not assume.

2.6 is the correct NEXT story (build tier 5). NOTE: 2.4 is NOT next — by the 2026-09-07
decision, 2.4 is gated behind A.5 + A.6 (the "clean the ground first" stories) and sits
at tier 7. 2.6 does not depend on 2.4 (it needs the dynamic RUN — 2.3 — not its
telemetry capture), so it is unaffected.

# THE GAP 2.6 FILLS (read before designing)
Today `lambdas/preprocessor/handler.py` fires TWO INDEPENDENT enqueues after routing:
a static-scan job (when routing names `static_analysis`) and a detonation job (when it
names `dynamic_detonation`) — both intra-Forensic hand-offs (RD-009). Each lane already
crosses its OWN derived, verdict-free summary to the Hub (the fifth envelope kind =
`scan`; the sixth = `run`). What is MISSING and what 2.6 BUILDS: (1) a concurrent FORK
that runs both lanes in parallel for one `intake_id`, and (2) a JOIN that collects both
lane outputs into ONE bounded, derived record for Phase-3 aggregation. 2.6 orchestrates
+ joins; it does NOT re-implement either lane and does NOT correlate (that is Phase 3).

# NON-NEGOTIABLE CONSTRAINTS
- FORK IS CONCURRENT, NOT SEQUENTIAL. The static and dynamic lanes must run in PARALLEL
  for the same artifact (PROJECT_PLAN §"Parallel inspection"). A one-then-the-other
  design does not satisfy the DoD.
- JOIN ON BOTH-COMPLETE. The collected record is produced only when BOTH lanes have
  finished (success OR recorded error) — a lane erroring must not hang the join forever
  or silently drop the other lane's output. Design the join to tolerate one lane
  failing (record it) without losing the other.
- EVIDENCE, NEVER A VERDICT. The joined record carries NO verdict/safe/approved/forward
  field. The verdict stays Hub-side / human-gated (Phase 4). 2.6 COLLECTS inputs; it
  does not judge them.
- FULL DETAIL STAYS IN FORENSIC (RD-009); only a bounded, derived joined record crosses
  the RD-013 gate — if it is a NEW envelope kind, it gets its OWN Hub version pin (the
  per-kind-pin discipline from 2.2/2.3; do NOT reuse a shared CONTRACT_VERSION, and do
  NOT collide the discriminator key with run/scan/routing/classification/rejection/
  status). PREFER joining the two ALREADY-crossed summaries on the Hub record by
  `intake_id` if that satisfies the DoD without a new crossing — decide and justify.
- CONTAINMENT UNCHANGED. The dynamic lane still runs host-native on the ephemeral EC2
  (NO Docker, RD-001); the isolated-VPC containment is untouched; the join introduces
  NO durable store in Forensic (RD-012) and NO raw-payload crossing.
- CONTRACT-FIRST for any new crossing shape: emit schemas via a `python json.dump`
  generator into BOTH `schemas/` and the bundled copies; hash-match.
- PURE LOGIC + THIN SEAM (the proven 1.2→2.3 pattern). Join/collection logic pure +
  offline-testable; orchestration control + any AWS calls behind thin boto3 seams. A
  seam failure is recorded, never crashes the pipeline.
- VALIDATION-GATED, NEVER ON INFERENCE: 2.6 flips ✅ only on a recorded live pass of the
  FINAL code (METHODOLOGY §4).
- ROLES: the LIVE fork run is the STAKEHOLDER's action in Forensic (executor has NO live
  creds); the executor RECORDS the returned output VERBATIM. Do NOT simulate a run.
- DOCS FIRST-CLASS (RD-015): PR-reviewed, never straight to main; PROJECT_PLAN ↔ RUNBOOK
  in EXACT alignment. Keep unrelated governance edits OFF this feature branch.

# ORCHESTRATION CHOICE (decide + record as a new RD)
The plan says the preprocessor "forks the pipeline into two lanes." Choose the
orchestration mechanism and record it as a new RD with rationale + candidate NIST/ISO
mappings: e.g. an AWS Step Functions state machine (a Parallel state that fans out to
both lanes and joins on both-complete) vs. an event-driven join keyed by `intake_id`.
Constraints to weigh: AWS-native only (no GitHub Actions/external); least-privilege;
the join must be idempotent under SQS at-least-once; both lanes already consume from
Forensic work queues, so the fork likely replaces/augments the preprocessor's two
independent enqueues with a single orchestrated fan-out. Justify the pick against the
"both-complete join, tolerate one-lane failure, no durable Forensic store" constraints.

# OPERATIONAL CONTEXT (state this on EVERY command block)
  Build sandbox is INTEGRATIONS_ONLY (NO AWS creds; PyPI + npm BLOCKED — boto3/pytest/
  moto/jsonschema/aws-cdk-lib NOT installable). You BUILD; the USER validates live in
  CloudShell (ambient creds, no --profile). Region us-east-1. Confirm the active account
  with `aws sts get-caller-identity` before EVERY operational block. The fork
  orchestration + both lanes + all artifact-touching compute are in FORENSIC
  (360999005254); the tracking table (where the joined record is verified) is in the HUB
  (641628980935) — TWO CloudShell tabs. `npx` needs `env -u NODE_OPTIONS npx --no-install`
  (proxy-bootstrap preload breaks npx).

# HARD-WON LESSONS (do NOT repeat)
- **BASE-BRANCH TRAP — it bit this project THIS week.** PR #65 merged with only its first
  commit on the branch; the later commits were stranded and needed a follow-up PR (#66)
  to reconcile `main`. After ANY live-validation fix: `git log main..<branch>` and
  confirm every fix commit merged; if a PR merged early, open a FOLLOW-UP PR. The restore
  tag points at the commit carrying the validated code, never an earlier one.
- **Two-account / wrong-account recurs CONSTANTLY:** `ResourceNotFoundException` on the
  tracking table = you queried it from Forensic (it's in the Hub). Run
  `aws sts get-caller-identity` before EVERY block, in EVERY tab, EVERY time.
- **CloudShell `/tmp` + shell vars are WIPED on session recycle.** Re-set every variable
  used in a block, in the SAME block, right before using it — never assume an export
  from an earlier paste survived.
- **`gh pr create` is BROKEN here** — open PRs via
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`. Merges are the repo-owner's action.
- **The 2.3 artifact-fetch recipe is settled — reuse, don't rediscover** (only relevant
  if 2.6 touches launch/execute or an isolated-host S3 fetch): one S3 GATEWAY endpoint
  (no interface endpoint); host SG egress to the S3 managed prefix list (resolved via a
  real `ec2:DescribeManagedPrefixLists` call, NOT a hard-coded id, NOT `PrefixList.
  fromLookup`, NOT `attrPrefixListId`); a REGIONAL presigned host (`endpoint_url` +
  `us_east_1_regional_endpoint=regional`); SigV4 (`signature_version="s3v4"`) — all four
  together. Do NOT pass `IamInstanceProfile` on `RunInstances` (the launch template
  already carries it). Bound every on-host fetch with `--connect-timeout`/`--max-time`.
- **Governance-tooling can DRIFT (RD-015):** after any status/register/table edit, re-run
  `python3 -m unittest scripts.test_check_docs` AND `scripts/check_docs.py`; fix any
  fixture keyed off a changed story state (keep fixtures state-independent —
  `_NEW_WORK_STORY="2.5"`, seed after the register separator). The master table is
  tier-ordered (METHODOLOGY §1a) with a `Track` column (pipe/gov/F&H) — a story's tier =
  1 + the highest tier of anything it depends on; if you change a dependency, re-tier and
  re-sort and confirm the tier column stays monotonic non-decreasing.
- **Offline proof bar:** stdlib `unittest` over fixtures + a MANUAL pure-Python
  conformance walk (jsonschema not installable) — a recursive no-verdict-key scan + a
  schema-has-no-verdict-property check. `ruff` clean; `tsc --noEmit`/`prettier --check`
  show ONLY the environmental missing-`aws-cdk-lib` family — confirm no NEW defect.
- **NEW (Story 2.0E live validation, 2026-09-08) — VPC-endpoint create can transiently
  fail right after a same-service delete.** Only relevant if 2.6 touches the ephemeral
  endpoint lifecycle (it should NOT need to — 2.6 orchestrates the two lanes, not the
  endpoint tier). DoD #5's orphan sweep DELETED the stale tagged endpoint correctly, but
  recreating a same-service (`logs`) endpoint ~380ms later failed with
  `InvalidParameter: private-dns-enabled cannot be set because there is already a
  conflicting DNS domain for logs.us-east-1.amazonaws.com`. Root cause: an endpoint's
  RESOURCE being gone is NOT sufficient for its private-DNS DOMAIN association to be
  released, and there is no API to observe that release — so the drain alone cannot close
  the race. Fix (already on `main`, commit `0977ce0`): `create_interface_endpoints`
  retries ONLY that transient conflicting-DNS-domain error with bounded backoff
  (`CREATE_ENDPOINT_MAX_ATTEMPTS=6`, `CREATE_ENDPOINT_RETRY_BASE_S=5`); any other error
  propagates. **Consequence for 2.6 timing/budgets:** a detonation whose start-of-run
  sweep hits this race can take ~200s (the retries riding out the ~50s DNS-domain release
  window) instead of the usual ~77s — well within the 840s Lambda / 900s SQS-visibility
  budget, but if 2.6 adds any wall-clock assumption about detonation duration, use the
  ~200s worst case, not the happy-path ~77s.
- **NEW (2.0E) — a fast successful run BEATS live `describe-vpc-endpoints` polling; the
  orchestrator LOG is the evidence.** The whole detonation (create ephemeral tier ->
  launch -> execute -> teardown) runs in ~30-80s, so hand-polling endpoint state during a
  run routinely returns an empty table even on a perfect run. Do NOT treat an empty live
  poll as a failure — read `aws logs tail /aws/lambda/ZtieDetonationStack-DetonationOrchestrator26C208DF-3Xzz4erewJub --since 15m`
  (no `--follow`; it blocks) and the Hub tracking record. The log + the crossed record are
  the authoritative DoD evidence for anything time-boxed inside a run.
- **NEW (2.0E) — `npm ci` FAILS in this repo (no committed `package-lock.json`); use
  `npm install`** in `infra/` before `npx cdk deploy`. (A follow-up to commit a lock file
  is worth doing but is not required for 2.6.)
- **NEW (2.0E) — the BASE-BRANCH TRAP recurred AGAIN (PR #68).** PR #68 auto-merged the
  PRE-PIVOT 2.0E code to `main` before live validation, so `main` briefly held the
  disproven all-ephemeral design while the validated two-tier + fix lived only on the
  feature branch. It was reconciled with follow-up PRs #70 (code) and #71 (restore
  manifest + BOM), and the tag `restore/story-2.0E-green` was placed on the reconciled
  `main` merge commit. Reinforces the standing rule: after ANY live-validation fix,
  `git log main..<branch>`, confirm every fix commit merged, and open a follow-up PR if a
  PR merged early — the restore tag points at the commit carrying the validated code.

# STEP 0 — RE-ESTABLISH TRUE STATE (before any edit)
# Trust `main` + `check_docs` over anything written here; if they disagree, `main` wins.
- `git fetch origin`; `git checkout main`; `git reset --hard origin/main`. Confirm HEAD is
  the PR #66 merge (or a descendant). List open PRs (an unrelated `#37 Dashboard` may be
  open — ignore it).
- `python3 scripts/check_docs.py` → expect PASS. `python3 -m unittest
  scripts.test_check_docs` → expect OK (3 tests).
- Confirm these EXPECTED TRUTHS (do NOT change until validated live):
    - This story = 2.6 = ⬜ (not started), build tier 5, Depends-on `2.1, 2.3`.
    - Depends-on: **2.1 = ✅** and **2.3 = ✅** — RE-VERIFY on `main`
      (`grep -nE "\[2\.1\]|\[2\.3\]" RUNBOOK.md` → both ✅).
    - Validation Debt Register = EMPTY → advancement gate OPEN for 2.6.
    - 2.4 = ⬜ at tier 7, Depends-on `2.3, A.5, A.6` (gated — NOT this session).
    - A.5, A.6, B.1, C.3 = ⬜ at tier 6 (Track=F&H); 2.0/2.1/2.2/2.3 = ✅.
    - Restore tags: run `git tag -l`. KNOWN GAP (tracked as Story A.6, owner action):
      `restore/phase-2-floor-green` and `restore/story-2.3-green` may still be MISSING
      from `git tag -l` even though the docs reference them. That is A.6's job, NOT 2.6's
      — do NOT create them here and do NOT block 2.6 on them (2.6's deps are 2.1 + 2.3,
      both ✅). Just note their state.
- Branch off `main` (current HEAD). Branch name: `feature/story-2.6`.

# THIS SESSION'S OBJECTIVE
Fork a routed artifact into BOTH inspection lanes concurrently after routing; run the
static lane (2.1/2.2) and the dynamic lane (2.3) in parallel for the same `intake_id`;
JOIN their two derived outputs into ONE bounded, derived, verdict-free collected record
ready for Phase-3 aggregation (full detail staying in Forensic, RD-009; only bounded
data crossing the RD-013 gate). Get the stakeholder to validate live that one artifact
ran both lanes in parallel and both outputs were collected.

# DEFINITION OF DONE (this session) — a PASS/FAIL GATE
The stakeholder confirms live in Forensic 360999005254 (+ Hub for the crossed record):
1. One routable artifact FORKS into BOTH lanes CONCURRENTLY after routing (parallel, not
   sequential) for the same `intake_id`.
2. Both lane outputs are COLLECTED / joined into one bounded derived record for that
   `intake_id`, ready for Phase 3.
3. The joined record is EVIDENCE — no verdict/safe/approved/forward field anywhere.
4. Containment/boundaries intact: dynamic lane host-native (no Docker, RD-001); isolated
   VPC unchanged; no durable Forensic store (RD-012); no raw-payload crossing.
- Goes ✅ ONLY when the stakeholder confirms a live pass AND you RECORD it in RUNBOOK.md.
  No recorded pass → stays 🟡. On any fail: stay on 2.6, fix, re-validate.

# ENVIRONMENT
- Repo cloned; push to `feature/story-2.6`, never main. Open PRs via
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls` (NOT `gh pr create`). Merges are the
  repo-owner's action. Live AWS is the stakeholder's Forensic/Hub CloudShell action.

# WORKING AGREEMENT
- One story to completion: design → build → STAKEHOLDER validates live → you RECORD +
  flip status → paired status commit (+ restore tag by the owner). Push to a branch; open
  a PR; after merge, `git log main..feature/story-2.6` to confirm the whole branch landed
  (base-branch trap).
- Validation drives status; the hard advancement gate governs advancement.
- MANAGEMENT ARTIFACTS ARE FIRST-CLASS (RD-015): brief + RUNBOOK + PROJECT_PLAN aligned;
  the new orchestration RD + candidate NIST/ISO mappings recorded; all via PR; governance
  restorable alongside the code. Re-run the G-3 doc checks after any status/table edit;
  2.6 closes Phase 2, so also update the P2 phase-gate record on pass.
- At session end, author the NEXT story's brief + prompt with THIS session's real Lessons
  Learned (next by tier after 2.6 closes: the F&H clean-ground items A.5/A.6, then 2.4;
  or 3.1 once the fork feeds Phase 3 — follow the RUNBOOK tiers). Zero cold-start.
- If blocked, push partial progress + a draft PR; surface the blocker; never silently fail.
