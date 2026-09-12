You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting. Do NOT change anything until you have (a) READ the
plan + runbook + methodology + this story's brief (`session-briefs/story-2.4-brief.md`),
(b) re-established true state (STEP 0), and (c) confirmed the Validation Debt Register
state + advancement gate.

# PROJECT IDENTITY
ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted artifact
BEFORE it reaches the PDE. Work is validation-gated: nothing is ✅ until a recorded live
pass (the covenant). Three accounts: Pipeline-Hub (641628980935) = brains/control plane
+ durable record; Forensic (360999005254) = self-contained blast zone (ephemeral only);
Pipeline-Sandbox (586917955591) = ZTIE→PDE handoff. Story 2.4 DEEPENS the P2 DYNAMIC
lane: while a routed artifact detonates on the ephemeral EC2 (Story 2.3), it CAPTURES
the artifact's runtime behavior — syscalls, network connection attempts, filesystem
operations — as bounded, derived EVIDENCE. It is the observability layer on top of the
run 2.3 already performs.

# WHAT THIS STORY IS (nature + gate role)
NEW FEATURE story. It may begin ONLY if its Depends-on are ALL ✅ AND the Validation
Debt Register is empty. **As of this prompt (2026-09-08) all three deps are ✅:**
- **2.3 ✅** (dynamic detonation lane, validated live 2026-09-05, PR #60)
- **A.5 ✅** (Floor & Harvest plan-drift corrected, 2026-09-08)
- **A.6 ✅** (both restore tags pushed + verified on origin, 2026-09-08)
The Validation Debt Register is EMPTY; `check_docs.py` PASSes; the advancement gate is
OPEN — 2.4 may start feature work. STEP 0 must still RE-CONFIRM this on `main` (trust
`main` + `check_docs` over this prompt; if they disagree, `main` wins). 2.4 is build
tier 7 and is the NEXT story by tier now that 2.6 closed ✅.

# WHERE 2.4 SITS (what already exists that it builds on)
- **2.3 (dynamic lane):** `lambdas/detonation/` — a plain-zip Python Lambda that reads
  2.0's SSM coordinates (`/ztie/detonation/{launch-template-id,isolated-subnet-ids}`),
  launches ONE ephemeral EC2 from the 2.0 launch template, executes the artifact
  host-native via SSM `AWS-RunShellScript` (NO Docker), self-terminates on the 5-min
  hard TTL, and crosses a bounded verdict-free RUN OUTCOME (`dynamic-run.contract.v1`,
  own `DYNAMIC_RUN_CONTRACT_VERSION`, `run` discriminator). It captures NO behavior —
  that is exactly the gap 2.4 fills.
- **2.6 (orchestration, ✅ 2026-09-08, RD-029):** the preprocessor now starts a Step
  Functions STANDARD state machine (`infra/lib/ztie-orchestration-stack.ts`) whose
  Parallel state fans the static + dynamic lanes out CONCURRENTLY, then a terminal
  collector Lambda (`lambdas/collector/`) crosses ONE bounded verdict-free `collected`
  record (the 7th RD-013 envelope kind). 2.6 invokes the detonation Lambda via a
  Step Functions DIRECT invoke (a bare job dict), which is why the lane handlers now
  have an `_is_direct_invoke` path in addition to the SQS-batch path. **2.4 modifies
  the detonation lane that 2.6 orchestrates — coordinate with both.**

# NON-NEGOTIABLE CONSTRAINTS
- CAPTURE IS HOST-NATIVE — the behavioral capture runs on the SAME ephemeral EC2 as the
  2.3 detonation, driven over SSM, NEVER in the Hub, and NEVER with Docker/containers on
  the host (RD-001 — a container distorts behavioral telemetry; instances are
  "ephemeral", never "temporary").
- CAPTURE, DO NOT SANITIZE. 2.4 captures RAW behavior (syscalls / network / fs). The
  sanitization pipeline (entropy scrub → noise suppress → ≤25K truncation) is 2.5 —
  OUT of scope here. Keep capture and sanitization separate.
- EVIDENCE, NEVER A VERDICT. 2.4 emits a bounded, derived behavioral-telemetry summary —
  no verdict/safe/approved/forward field anywhere. The verdict is Hub-side/human-gated
  (Phase 4).
- FULL TRACE STAYS IN FORENSIC (RD-009); only a bounded, derived summary crosses the
  RD-013 gate — a NEW (the EIGHTH) envelope kind with its OWN Hub version pin and its
  OWN discriminator key. The seven existing kinds/discriminators are:
  `classification`, `routing`, `rejection`, `scan`, `run`, `status`, and `collected`
  (2.6). Do NOT collide with any of them; do NOT reuse a shared CONTRACT_VERSION.
- RELATIVE CLOCK ONLY — timestamps are monotonic offsets from detonation start, never a
  human/observer wall clock (PROJECT_PLAN note).
- CONTRACT-FIRST. Design the telemetry-summary shape first; emit schemas via a
  `python json.dump` generator into BOTH `schemas/` and the bundled copies; hash-match.
- PURE LOGIC + THIN SEAM (the proven 1.2→2.3→2.6 pattern). Capture-normalization pure +
  offline-testable; the capture-tool control + trace upload behind thin boto3 seams. A
  seam failure is recorded, never crashes the lane.
- VALIDATION-GATED, NEVER ON INFERENCE: 2.4 flips ✅ only on a recorded live pass of the
  FINAL code (METHODOLOGY §4).
- ROLES: the LIVE detonation-with-capture run is the STAKEHOLDER's action in Forensic
  (executor has NO live creds); the executor RECORDS the returned output VERBATIM. Do
  NOT simulate/assume a live output.
- DOCS FIRST-CLASS (RD-015): PR-reviewed, never straight to main; PROJECT_PLAN ↔
  RUNBOOK in EXACT alignment. Keep unrelated governance edits OFF this feature branch.

# NEW REGISTERED DECISION
Record the capture-tool choice as a new RD with rationale + candidate NIST/ISO mappings.
**The next free RD number on `main` is RD-030** (RD-029 is 2.6's orchestration decision;
RD-027/028 are 2.0E's). RE-VERIFY at STEP 0 with
`grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md | sort -u | tail` and take the next free
number — RD-number collisions have happened here (2.6 collided at RD-027 on a stale
branch and had to renumber across ~13 files). Decide the tool (strace vs auditd vs an
eBPF tool) against what the ubuntu-22.04 golden AMI actually ships (see below).

# OPERATIONAL CONTEXT (state this on EVERY command block)
  Build sandbox is INTEGRATIONS_ONLY (NO AWS creds; PyPI + npm BLOCKED — boto3/pytest/
  moto/jsonschema/aws-cdk-lib NOT installable). You BUILD; the USER validates live in
  CloudShell (ambient creds, no --profile). Region us-east-1. Confirm the active
  account with `aws sts get-caller-identity` before EVERY operational block. The
  detonation host + capture + all artifact-touching compute are in FORENSIC
  (360999005254); the tracking table is in the HUB (641628980935) — TWO CloudShell tabs.
  Tooling: `ruff` is NOT on PATH — use `~/.pyenv/versions/3.12.13/bin/ruff`; `prettier`
  and `npx tsc` need `env -u NODE_OPTIONS` (proxy-bootstrap preload breaks bare node
  tools); npm is BLOCKED so `tsc --noEmit` legitimately shows ONLY the missing-
  `aws-cdk-lib` error family (TS2307/2339/2353/2591/2304) identical across all stacks —
  confirm the new code adds NO NEW error TYPE, not that there are zero errors.

# HARD-WON LESSONS (do NOT repeat)

## DEPLOY-GAP — THE most important lesson for 2.4 (from 2.6's live run, 2026-09-08)
When a story changes a lane Lambda that an EARLIER story's orchestration invokes, the
LIVE lane can still be running its OLD deployed code. In 2.6, the static-scan +
detonation lanes were still on their pre-2.6 (SQS-batch-only) code, so a Step Functions
direct-invoke with a bare job dict fell through to the SQS path, looped over zero
Records, and returned `{"batchItemFailures":[]}` — the collector correctly recorded
`lane_status=errored`. **2.4 MODIFIES the detonation lane handler** (to start/stop
capture around the run). Therefore: after building, the LIVE validation MUST redeploy
BOTH the detonation lane stack (`ZtieDetonationStack`) AND — if the collected/orchestration
contract changes — the orchestration + Hub stacks, BEFORE submitting a run. Deploying
only your new code is insufficient if 2.6's orchestration path invokes the changed
handler. Put the required redeploys as an explicit pre-run step in the 2.4 LIVE-RUNBOOK.
Root-cause a "lane didn't really run" symptom via
`aws stepfunctions get-execution-history … TaskScheduled.parameters` (was the job passed?)
+ the lane Lambda's CloudWatch logs (did it actually execute?) + the returned Payload.

## The artifact-fetch recipe (from 2.3's live run) — reuse, do NOT rediscover
If 2.4's trace UPLOAD (or any new S3 interaction from the isolated host) needs its own
presigned URL, ALL FOUR are required together (each was a separate live failure in 2.3):
1. Do NOT pass `IamInstanceProfile` on `ec2:RunInstances` — the 2.0 launch template
   already bakes it in; a derived profile ARN is invalid and `RunInstances` rejects it.
2. Bound every on-host `curl` with `--connect-timeout` + `--max-time` — an unreachable
   S3 otherwise hangs until the 5-min TTL SIGKILLs it (`Rc:137`, empty output), looking
   identical to a slow artifact. Emit a diagnosable marker on failure.
3. ONE S3 GATEWAY endpoint only — do NOT add an S3 interface endpoint alongside it
   (private-DNS conflict; the host resolved S3 to an unroutable public IP, verified live).
4. Presign the REGIONAL host: explicit `endpoint_url=https://s3.{region}.amazonaws.com`
   + `Config(s3={"us_east_1_regional_endpoint":"regional"})` — us-east-1 presigns the
   GLOBAL host by default, which the gateway endpoint does not intercept. AND the host
   SG egress must allow the S3 MANAGED PREFIX LIST (a gateway endpoint routes to S3's
   public IP ranges, outside the VPC CIDR) — resolve the prefix-list id via a real
   `ec2:DescribeManagedPrefixLists` (`AwsCustomResource`), NOT a hard-coded id, NOT
   `PrefixList.fromLookup`, NOT `attrPrefixListId` (does not exist — real TS2339). AND
   sign SigV4 (`Config(signature_version="s3v4")`) — us-east-1 defaults to SigV2, which
   the regional endpoint rejects with a plain HTTP 400.

## Capture-tool + AMI (2.4-specific)
- The capture TOOL (strace / auditd / an eBPF tool) must be PRE-BAKED on the
  ubuntu-22.04 golden AMI — the isolated host has NO internet to install it at boot.
  CONFIRM what the AMI ships before designing capture; if the needed tool is absent, the
  AMI (Image Builder) must add it — the AL2023 AMI build is still broken, so ubuntu-only.
- Network capture in the isolated VPC is about INTENT, not success: the host has no
  egress, so every outbound connection attempt FAILS — but the attempt itself is signal.
  Capture attempts, not just completed connections.

## Build + governance discipline (still true)
- The lane pattern held again (1.2→2.2→2.3→2.6): contract-first + pure logic + thin
  boto3 seam + evidence-never-verdict + a new envelope kind with its OWN version pin +
  its OWN discriminator. `lambdas/detonation/{outcome.py,runspec.py}` are pure/offline-
  tested; `awsio.py` is the only boto3; `handler.py` orchestrates. 2.4 extends this seam
  for the capture-tool control over SSM + the trace upload; keep the new capture-
  normalization logic PURE + offline-testable.
- Branch the CODE off `main` (current HEAD, which contains merged 2.3 + 2.6 + A.5/A.6),
  NOT off a restore tag — restore tags are ancestors and predate later merged stories;
  building on one and PRing to main regresses merged work.
- STALE-BRANCH TRAP: if this branch ever sits while another story merges, `git merge-base
  main <branch>` + `git diff --stat main..<branch>` — if the diff DELETES files of an
  already-merged story, `git merge origin/main` in, resolve keeping BOTH, COMMIT the
  merge, then re-run checks. (2.6's branch hit exactly this vs 2.0E.)
- Offline proof bar: stdlib `unittest` over fixtures + a MANUAL pure-Python conformance
  walk (jsonschema not installable) — two layers (skipUnless-live + always-offline walk
  incl. a recursive no-verdict-key scan + a schema-has-no-verdict-property check).
- Governance-tooling can DRIFT (RD-015): run `scripts/check_docs.py` only AFTER
  committing any status/register change (CHECK B's baseline is `git show HEAD:RUNBOOK.md`
  — running before the commit gives a FALSE-POSITIVE). Also run
  `python3 -m unittest scripts.test_check_docs` (its `check_docs: FAIL …` fixture lines
  for story 2.5 are the checker testing ITSELF; the suite still reports OK / 3 tests).
  If 2.4 goes 🟡, it MUST be added to the Validation Debt Register in the same commit or
  CHECK A fails. The master table is tier-ordered (METHODOLOGY §1a) with a Track column
  (pipe/gov/F&H); tier = 1 + max dependency tier — 2.4 is tier 7.
- Two accounts, two tabs, `aws sts get-caller-identity` before EVERY block — the single
  most repeated live mistake (`ResourceNotFoundException` on the Hub table = you queried
  it from Forensic). `/tmp` + shell vars are WIPED on CloudShell session recycle —
  re-set every variable in the SAME block right before use.
- Intake API wants a JSON envelope via awscurl (SigV4), NOT a raw file body:
  `{"filename":…, "content_type":…, "submitter":…, "content_base64":"<base64 of raw
  bytes>"}` with `-H 'Content-Type: application/json' -d @file.json`; put the URL BEFORE
  the flags. Install awscurl with `pip install awscurl`. `gh pr create` is BROKEN — open
  PRs via `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`. PR mergeability can cache
  stale after a force-push — verify via `git ls-remote`/refs API, and if a PR looks
  permanently stuck, close it and open a fresh one from the same corrected branch.

# STEP 0 — RE-ESTABLISH TRUE STATE (before any edit)
# Trust `main` + `check_docs` over anything written here; if they disagree, `main` wins.
- `git fetch origin`; `git checkout main`; `git reset --hard origin/main`. List open PRs
  (an unrelated `#37 Dashboard` may be open — ignore it).
- `python3 scripts/check_docs.py` → expect PASS. `python3 -m unittest
  scripts.test_check_docs` → expect OK (3 tests).
- Confirm these EXPECTED TRUTHS (do NOT change until validated live):
    - This story = 2.4 = ⬜ (not started), build tier 7, Depends-on `2.3, A.5, A.6`.
    - Deps ALL ✅: `grep -nE "\[2\.3\]|\[A\.5\]|\[A\.6\]" RUNBOOK.md` → all ✅. (A.5/A.6
      completed 2026-09-08; 2.3 2026-09-05.)
    - Validation Debt Register = EMPTY → advancement gate OPEN for 2.4.
    - 2.6 = ✅ (2026-09-08) — the orchestration that invokes the detonation lane 2.4
      changes. 2.0/2.1/2.2 = ✅.
    - Restore tags: `git ls-remote --tags origin | grep restore/` should list ALL SIX:
      `restore/phase-1-green`, `restore/story-2.0-green`, `restore/story-2.0E-green`,
      `restore/story-2.1-green`, `restore/phase-2-floor-green`, `restore/story-2.3-green`.
      (A.6 pushed the last two on 2026-09-08 — there is NO phantom tag anymore and NO
      "TASK 0" to push anything; if any tag is missing, surface it, but it is not 2.4's
      job to create them.)
    - Next free RD number = RD-030 (RE-VERIFY per the NEW REGISTERED DECISION section).
- Branch off `main` (current HEAD). Branch name: `feature/story-2.4`.

# THIS SESSION'S OBJECTIVE
Instrument the detonation: while a routed artifact runs host-native on the ephemeral
EC2 (2.3), CAPTURE its syscalls, network connection attempts, and filesystem operations;
ship the FULL trace to Forensic S3 (RD-009); cross a bounded, derived, verdict-free
behavioral-telemetry summary to the Hub as a NEW envelope kind (its own version pin +
discriminator), with relative monotonic timestamps. Get the stakeholder to validate live
that a real run's behavior was captured, stored in Forensic, and summarized to the Hub.

# SCOPE & GUARDRAILS
- In scope: host-native behavioral capture (syscall/network/fs) on the ephemeral host
  during the 2.3 run, driven over SSM (NO Docker); full trace → Forensic S3 (RD-009); a
  bounded derived behavioral-telemetry contract crossing the RD-013 gate (new envelope
  kind #8, own version pin + discriminator); relative monotonic timestamps; pure logic +
  thin seams; tests; a new RD (RD-030) for the capture-tool choice + candidate control
  mappings; any golden-AMI change needed to ship the capture tool.
- Out of scope / do NOT touch: telemetry SANITIZATION (entropy/noise/≤25K truncation) —
  that is 2.5; the fork/orchestration internals — 2.6 (but you MUST redeploy the lane
  stacks it orchestrates, see the deploy-gap lesson); the Hub verdict; the static lane
  (2.1/2.2); Docker on the detonation host; re-litigating the 2.3 run-outcome contract
  or the 2.6 collected contract.
- Depends on (must be ✅): 2.3, A.5, A.6 (all are). Plus an EMPTY Validation Debt Register.

# DEFINITION OF DONE (this session) — a PASS/FAIL GATE
The stakeholder confirms live in Forensic 360999005254 (+ Hub for the crossed summary):
1. During a real detonation, the ephemeral host CAPTURES the artifact's behavior
   (syscalls + network connection attempts + filesystem ops) host-native — NO Docker.
2. The FULL behavioral trace is written to Forensic S3 (it stays in Forensic, RD-009).
3. A bounded, derived behavioral-telemetry summary crosses the RD-013 gate to the Hub
   (new envelope kind, its own version pin) — evidence, no verdict/safe/forward field.
4. Timestamps are relative monotonic offsets from detonation start (never a wall clock).
- Goes ✅ ONLY when the stakeholder confirms a live pass AND you RECORD it in RUNBOOK.md.
  No recorded pass → stays 🟡 (and 2.4 goes on the Validation Debt Register in the same
  commit). On any fail: stay on 2.4, fix, re-validate.

# ENVIRONMENT
- Repo cloned; push to `feature/story-2.4`, never main. Open PRs via
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls` (NOT `gh pr create`). Merges are the
  repo-owner's action. Live AWS is the stakeholder's Forensic/Hub CloudShell action.

# WORKING AGREEMENT
- One story to completion: design → build → STAKEHOLDER validates live (redeploy the
  detonation lane stack FIRST per the deploy-gap lesson) → you RECORD + flip status →
  paired status commit; push to a branch; open a PR. After merge,
  `git log main..feature/story-2.4` to confirm the whole branch landed (base-branch trap);
  the restore tag (owner action) points at the merge commit that carries the validated code.
- Validation drives status; the hard advancement gate governs advancement.
- MANAGEMENT ARTIFACTS ARE FIRST-CLASS (RD-015): brief + RUNBOOK + PROJECT_PLAN aligned;
  the new RD-030 + candidate NIST/ISO mappings recorded; all via PR; governance
  restorable alongside the code. Re-run the G-3 doc checks AFTER committing any status edit.
- At session end, author the NEXT story's brief + prompt with THIS session's real Lessons
  Learned (next by tier after 2.4: 2.5 sanitization). Zero cold-start.
- If blocked, push partial progress + a draft PR; surface the blocker; never silently fail.
