You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting. Do NOT change anything until you have (a) READ the
plan + runbook + methodology + this story's brief (`session-briefs/story-2.4-brief.md`),
(b) re-established true state (STEP 0), and (c) confirmed the Validation Debt Register
state + advancement gate.

# THIS SESSION HAS TWO OUTSTANDING ITEMS — DO THEM IN ORDER
1. **TASK 0 (owner action, small, do FIRST):** tag the Story 2.3 restore point. It
   does NOT exist yet even though 2.3 is ✅ on `main`. See "TASK 0" below.
2. **TASK 1 (the story):** build Story 2.4 (behavioral telemetry capture) per this
   prompt + `session-briefs/story-2.4-brief.md`.
Do not skip TASK 0 — a validated story without its restore tag means a future
restore cannot land on the exact commit that passed.

## TASK 0 — Tag `restore/story-2.3-green` (owner action; do this before STEP 0)

Story 2.3 was validated live 2026-09-05 (PR #60, merged, all 4 DoD checks passed —
see `docs/STORY_DETAIL.md#story-2-3` for the verbatim evidence) and its Validation
Debt Register entry was cleared. `RUNBOOK.md` and `PROJECT_PLAN.md` already
reference the tag `restore/story-2.3-green`, but `git tag -l` does NOT show it —
this is the one remaining step to close the story out completely.

```
git fetch origin
git log --oneline -1 origin/main   # confirm this is the merge commit for PR #60
                                    # (docs/story-2.3-validate: "flip 🟡 -> ✅")
git tag -a restore/story-2.3-green <that commit sha or origin/main> \
  -m "Story 2.3 validated live 2026-09-05: dynamic detonation lane (ephemeral EC2 + host-native SSM), 4/4 DoD pass"
git push origin restore/story-2.3-green
git tag -l   # confirm it now lists restore/phase-1-green, restore/story-2.0-green,
             # restore/story-2.1-green, restore/story-2.3-green
```

Do NOT tag any other commit — it must point at the merge commit that carries the
✅ flip + the emptied Validation Debt Register (NOT an earlier commit from the
build-and-fix chain, PRs #51-#59, which is pre-validation code by definition).
This is an OWNER action (real git/AWS rights); if you are the executor without
push rights to tags, surface this as done-by-the-user and move to STEP 0 for 2.4.

# PROJECT IDENTITY
ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted
artifact BEFORE it reaches the PDE. Work is validation-gated: nothing is ✅ until a
recorded live pass (the covenant). Three accounts: Pipeline-Hub (641628980935) =
brains/control plane + durable record; Forensic (360999005254) = self-contained blast
zone (ephemeral only); Pipeline-Sandbox (586917955591) = ZTIE→PDE handoff. Story 2.4
DEEPENS the P2 DYNAMIC lane: while a routed artifact detonates on the ephemeral EC2
(Story 2.3), it CAPTURES the artifact's runtime behavior — syscalls, network attempts,
filesystem operations — as bounded, derived evidence. It is the observability layer on
top of the run that 2.3 already performs.

# WHAT THIS STORY IS  (nature + gate role)
NEW FEATURE story. It may begin ONLY if its Depends-on are all ✅ AND the Validation
Debt Register is empty. **Both are already true as of this prompt:** 2.3 was
validated live 2026-09-05 (PR #60, merged) and flipped ✅ on `main`; the Validation
Debt Register is EMPTY; `check_docs.py` PASSes. The advancement gate is OPEN — 2.4
may start feature work. STEP 0 must still RE-CONFIRM this on `main` (trust `main` +
`check_docs` over this prompt) before touching anything, per the standing discipline
— but do not assume the register is closed by default; verify it.

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
  RD-013 gate — a NEW (seventh) envelope kind with its OWN Hub version pin (the
  per-kind-pin discipline from 2.2/2.3; do NOT reuse the shared CONTRACT_VERSION).
- RELATIVE CLOCK ONLY — timestamps are monotonic offsets from detonation start, never a
  human/observer wall clock (PROJECT_PLAN note).
- CONTRACT-FIRST. Design the telemetry-summary shape first; emit schemas via a
  `python json.dump` generator into BOTH `schemas/` and the bundled copies; hash-match.
- PURE LOGIC + THIN SEAM (the proven 1.2→2.3 pattern). Capture-normalization pure +
  offline-testable; the capture-tool control + trace upload behind thin boto3 seams. A
  seam failure is recorded, never crashes the lane.
- VALIDATION-GATED, NEVER ON INFERENCE: 2.4 flips ✅ only on a recorded live pass of the
  FINAL code (METHODOLOGY §4).
- ROLES: the LIVE detonation-with-capture run is the STAKEHOLDER's action in Forensic
  (executor has NO live creds); the executor RECORDS the returned output VERBATIM. Do
  NOT simulate/assume a live output.
- DOCS FIRST-CLASS (RD-015): PR-reviewed, never straight to main; PROJECT_PLAN ↔
  RUNBOOK in EXACT alignment. Keep unrelated governance edits OFF this feature branch.

# OPERATIONAL CONTEXT (state this on EVERY command block)
  Build sandbox is INTEGRATIONS_ONLY (NO AWS creds; PyPI + npm BLOCKED — boto3/pytest/
  moto/jsonschema/aws-cdk-lib NOT installable). You BUILD; the USER validates live in
  CloudShell (ambient creds, no --profile). Region us-east-1. Confirm the active
  account with `aws sts get-caller-identity` before EVERY operational block. The
  detonation host + capture + all artifact-touching compute are in FORENSIC
  (360999005254); the tracking table is in the HUB (641628980935) — TWO CloudShell tabs.
  npx needs `env -u NODE_OPTIONS npx --no-install` (proxy-bootstrap preload breaks npx).

# HARD-WON LESSONS (do NOT repeat) — from the 2.3 build + LIVE VALIDATION (2026-09-04/05)

## From the build (still true)
- The lane pattern held a fourth time: contract-first + pure-logic/thin-seam +
  evidence-never-verdict + a NEW envelope kind with its OWN Hub version pin. 2.3 added
  `DYNAMIC_RUN_CONTRACT_VERSION` + `_is_dynamic_run_envelope` (discriminator = a `run`
  object). 2.4 gets its OWN pin + its OWN discriminator key (do NOT collide with
  `run`/`scan`/`routing`/`classification`/`rejection`/`status`).
- 2.0 already provisions the dynamic lane's infra: the orchestrator IAM + the SSM
  coordinate params `/ztie/detonation/{launch-template-id,isolated-subnet-ids,
  instance-role-arn,ami-flavor}`. 2.3 reads `launch-template-id` + `isolated-subnet-ids`
  ONLY now (see below — the instance-role-arn read was removed). 2.4 reuses the SAME
  read-from-SSM pattern. 2.3's `awsio.py` seam already launches/executes/observes
  teardown — 2.4 extends it for the capture-tool control + trace upload.
- 2.3's compute is a PLAIN ZIP Lambda — NO Docker build box needed (that was only the
  static-scan tool image). BUT the capture TOOL (strace/auditd/eBPF) must be PRE-BAKED
  on the ubuntu-22.04 golden AMI — the isolated host has no internet to install it.
  Confirm what the AMI ships before designing capture. AL2023 AMI build is still broken
  (ubuntu-only).
- Branch the CODE off `main` (current HEAD, which contains merged 2.3), NOT off a
  restore tag — restore tags are ancestors of main and predate later merged stories;
  building on one and PRing to main regresses merged work. The restore tag is the
  *infra* the lane runs on.
- Offline proof bar: stdlib `unittest` over fixtures + a MANUAL pure-Python conformance
  walk (jsonschema not installable) — TWO layers (skipUnless-live + always-offline
  walk incl. a recursive no-verdict-key scan + a schema-has-no-verdict-property check).
  `ruff` clean (defaults; BLE001 noqa may show RUF100 — remove unused noqa, and for a
  deliberate swallow use `# noqa: BLE001, S110` + a comment). `tsc --noEmit` shows ONLY
  the environmental family (TS2307/TS2591/TS2304/TS2339) — confirm no NEW defect.
- Governance-tooling can DRIFT (RD-015): after any status/register edit, re-run
  `python3 -m unittest scripts.test_check_docs` AND `scripts/check_docs.py`; fix any
  fixture keyed off a changed story state. 2.3 made the fixtures state-independent
  (`_NEW_WORK_STORY="2.5"`, `_seed_open_debt` inserts after the register separator) —
  keep them that way; do NOT re-introduce a hard-coded "story 2.2 is ⬜" assumption.
- Two-account / wrong-account recurs CONSTANTLY: `ResourceNotFoundException` on the
  tracking table = you queried it from Forensic (it's in the Hub). Run
  `aws sts get-caller-identity` before EVERY block, in EVERY tab, EVERY time — this
  was the single most repeated live-session mistake. `gh pr create` is BROKEN — open
  PRs via `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`.
- CloudShell `/tmp` and shell variables are WIPED whenever the session recycles
  (new tab, timeout, etc.) — a fresh shell shows the OLD prompt but has NONE of the
  previous exports. Symptom: `log group does not exist` or a stale
  `get-command-invocation` result from an OLD run because `$INTAKE_ID`/`$INSTANCE_ID`/
  etc. were never re-set in the new shell. ALWAYS re-set every variable used in a
  block, in the SAME block, right before using it — never assume a variable from an
  earlier paste survived.
- `awscurl`'s `-d @file --data-binary` flag pattern differs by version — a raw binary
  POST body via `--data-binary` alone can misparse; the working, verified pattern for
  the intake API specifically is a **JSON envelope** body: `{"filename":...,
  "content_type":..., "submitter":..., "content_base64": "<base64 of the raw bytes>"}`
  posted with `-H 'Content-Type: application/json' -d @file.json` (no `--data-binary`).
  The intake handler base64-decodes `content_base64` server-side.

## From the LIVE detonation run itself (2026-09-05) — the artifact-fetch chain, in full
Story 2.3's first live runs surfaced SEVEN real defects in the launch/fetch path, each
one only discoverable by actually running it (this is exactly why validation is live,
never inferred). All are fixed on `main` (PRs #52-#59). If 2.4 touches artifact
delivery (capture-tool staging, trace upload) or the launch/execute path AT ALL, re-read
this list — do not reintroduce any of these:
1. **Instance profile:** do NOT pass `IamInstanceProfile` on `ec2:RunInstances`. A CDK
   `LaunchTemplate({ role })` already bakes the instance profile INTO the template;
   deriving/passing your own (even from the correct role ARN) produces an INVALID
   profile ARN (a CDK role's auto-created profile has a different name than the role) —
   `RunInstances` rejects it outright (`InvalidParameterValue`).
2. **Unbounded on-host fetch = a silent 5-min hang, not a fast failure:** the host-native
   `curl` pulling the artifact from S3 MUST have `--connect-timeout` + `--max-time`. Without
   them, an unreachable S3 endpoint hangs the SSM command until the hard TTL's
   `shutdown -h` SIGKILLs it (`Rc: 137`, empty stdout, `ssm_status: TimedOut`) —
   indistinguishable from a genuinely slow artifact. Bound it, and have the failure
   emit a diagnosable marker (e.g. `echo "X-FAILED rc=$?"` + a `curl -v` log tail) so
   the NEXT failure is self-diagnosing instead of another silent hang.
3. **S3 gateway + S3 interface endpoint in the SAME VPC conflict:** if the VPC already
   has an S3 GATEWAY endpoint (route-table based), do NOT also add an S3 INTERFACE
   endpoint with private DNS — AWS explicitly warns this combination causes DNS
   resolution conflicts; verified live, the isolated host resolved S3 to a PUBLIC IP
   (unroutable) instead of using either endpoint correctly. One S3 gateway endpoint is
   sufficient and simpler; do not add a second S3 access path without a strong reason.
4. **us-east-1 presigns the GLOBAL S3 host by default:** `boto3.client('s3',
   region_name='us-east-1')` (even with `addressing_style='virtual'`) still presigns
   `<bucket>.s3.amazonaws.com`, NOT `<bucket>.s3.us-east-1.amazonaws.com`. An S3 gateway
   endpoint only intercepts the REGIONAL host. Any S3 URL an isolated host must fetch
   from us-east-1 needs an EXPLICIT `endpoint_url=f"https://s3.{region}.amazonaws.com"`
   AND `config=Config(s3={"us_east_1_regional_endpoint": "regional"})`.
5. **A gateway endpoint routes to PUBLIC S3 IPs — the host's security-group EGRESS must
   allow them, not just the VPC CIDR.** The 2.0 detonation host SG only allowed 443 to
   the VPC's own CIDR block (for the INTERFACE endpoints, whose ENIs are in-VPC). An S3
   GATEWAY endpoint routes to S3's public IP ranges via a managed prefix list — OUTSIDE
   the VPC CIDR — so that SG silently DROPPED the S3 connection even though the gateway
   route existed. Fix: add a distinct egress rule to the AWS-managed S3 prefix list
   specifically. **Resolve the prefix-list id via a REAL `ec2:describeManagedPrefixLists`
   call (an `AwsCustomResource`), NOT `PrefixList.fromLookup` (uncertain availability for
   this repo's CDK version range — an open `aws/aws-cdk` issue proposes it as a NEW
   feature) and NOT `(CfnVPCEndpoint).attrPrefixListId` (does not exist — real
   `TS2339`, caught live). Verify any CDK API against real docs before a live deploy;
   two wrong guesses on this exact spot were caught in this project already.
6. **us-east-1 defaults boto3 to SigV2 signing, which the regional endpoint rejects with
   HTTP 400.** Once the network path is open (items 3-5 fixed), a presigned URL still
   fails with a plain `400 Bad Request` unless the S3 client is built with
   `config=Config(signature_version="s3v4", ...)`. A SigV2 presigned URL has
   `AWSAccessKeyId`/`Signature`/`Expires` query params; a SigV4 one has
   `X-Amz-Algorithm=AWS4-HMAC-SHA256`/`X-Amz-Credential`/`X-Amz-Date`/`X-Amz-Signature`
   — inspect the actual URL string if a 400 recurs, it names the signature version.
7. **The complete, minimal, CORRECT recipe for an isolated host to fetch from S3 via a
   presigned URL in us-east-1** (now proven live, all four required TOGETHER): (a) ONE
   S3 gateway endpoint in the VPC (no interface endpoint); (b) the host SG egress open
   to that gateway endpoint's managed prefix list (resolved via `AwsCustomResource` +
   `describeManagedPrefixLists`, not hard-coded); (c) the S3 client presigns the
   REGIONAL host (`endpoint_url` + `us_east_1_regional_endpoint=regional`); (d) SigV4
   (`signature_version="s3v4"`). Missing ANY one of the four reproduces a timeout or a
   400. If 2.4's capture-trace upload (or any new S3 interaction from the isolated
   host) needs its OWN presigned URL, reuse this exact recipe — do not rediscover it.
- **PR mergeability can go stale/cached on GitHub** after a force-push or a branch
  rebase — `gh api .../pulls/N` may keep reporting an old `head.sha`/`mergeable:null`
  well after the branch ref is genuinely updated (confirmed via
  `gh api .../git/refs/heads/<branch>`). If a PR looks stuck, don't wait indefinitely —
  close it and open a fresh PR from the same (corrected) branch; that forces GitHub to
  recompute cleanly. Always verify against `git ls-remote` / the refs API, not just the
  pulls API, when a PR's state looks wrong.
- **CloudShell CDK deploy note:** `AwsCustomResource` provisions its own small Lambda +
  IAM automatically at synth time (visible as `AWS679f53fac...` in the deploy log,
  plus an `installLatestAwsSdk` warning you can ignore/acknowledge) — this is normal,
  not a sign of a broken deploy.
- **Restore-tag discipline reminder:** a validated story's restore tag does NOT get
  created automatically — it is a separate, explicit owner action AFTER the paired
  status-flip PR merges, and it must point at THAT merge commit (not an earlier
  build/fix commit). Confirm `git tag -l` before assuming a tag exists just because
  RUNBOOK.md references it.

# STEP 0 — RE-ESTABLISH TRUE STATE (before any edit)
# Trust `main` + `check_docs` over anything written here; if they disagree, `main` wins.
- git fetch/pull latest main; confirm HEAD is (or is a descendant of) the merge commit
  for PR #60 (`docs/story-2.3-validate`, title "flip 🟡 -> ✅"). List open PRs (expect
  none open against Story 2.3/2.4 at session start; `#37 Dashboard` may still be open —
  unrelated, ignore it).
- `python3 scripts/check_docs.py` → expect PASS.
- Confirm these EXPECTED TRUTHS (do NOT change them until validated live):
    - This story = 2.4 = ⬜ (not started).
    - Depends-on: **2.3 = ✅** (validated live 2026-09-05, PR #60 merged). RE-VERIFY on
      `main`, do not just trust this line — `grep -n "\[2.3\]" RUNBOOK.md` should show
      `✅` in the Status column with Completed date `2026-09-05`.
    - Validation Debt Register = EMPTY (2.3 was the last open entry; cleared). The
      advancement gate is therefore OPEN for 2.4.
    - 2.0 = ✅ (`restore/story-2.0-green`), 2.1 = ✅, 2.2 = ✅.
    - Restore tags: run `git tag -l`. Expect `restore/phase-1-green`,
      `restore/story-2.0-green`, `restore/story-2.1-green`. **If `restore/story-2.3-green`
      is MISSING, that is TASK 0 above — do it now, before proceeding to 2.4** (this was
      the known state as this prompt was authored: 2.3 validated + merged, tag not yet
      pushed). PHANTOM TAG (separate, still open): `restore/phase-2-floor-green` is
      referenced in BOM.md + RUNBOOK.md (A.4) but does NOT exist in `git tag -l` —
      resolve (owner pushes it OR reconcile docs to `restore/story-2.1-green`) before
      relying on the "Phase-2 floor"; do NOT silently create it.
    - G-3 hard advancement gate in place; `python3 -m unittest scripts.test_check_docs`
      → expect `OK` (3 tests).
- Branch off `main` (current HEAD, containing merged 2.3 + its validation). Branch
  name: `feature/story-2.4`.

# THIS SESSION'S OBJECTIVE
Instrument the detonation: while a routed artifact runs host-native on the ephemeral
EC2 (2.3), CAPTURE its syscalls, network connection attempts, and filesystem
operations; ship the full trace to Forensic S3 (RD-009); cross a bounded, derived,
verdict-free behavioral-telemetry summary to the Hub as a new envelope kind (its own
version pin), with relative monotonic timestamps. Get the stakeholder to validate live
that a real run's behavior was captured, stored in Forensic, and summarized to the Hub.

# SCOPE & GUARDRAILS
- In scope: host-native behavioral capture (syscall/network/fs) on the ephemeral host
  during the 2.3 run, driven over SSM (NO Docker); full trace -> Forensic S3 (RD-009);
  a bounded derived behavioral-telemetry contract crossing the RD-013 gate (new
  envelope kind, its own version pin); relative monotonic timestamps; pure logic + thin
  seams; tests; a new RD for the capture-tool choice + candidate control mappings.
- Out of scope / do NOT touch: telemetry SANITIZATION (entropy/noise/≤25K truncation) —
  that is 2.5; the fork/orchestration — 2.6; the Hub verdict; the static lane
  (2.1/2.2); Docker on the detonation host; re-litigating the 2.3 run outcome contract.
- Depends on (must be ✅): 2.3. Plus an EMPTY Validation Debt Register.

# DEFINITION OF DONE (this session) — a PASS/FAIL GATE
The stakeholder confirms live in Forensic 360999005254:
1. During a real 2.3 detonation, the ephemeral host CAPTURES the artifact's behavior
   (syscalls + network attempts + filesystem ops) host-native — NO Docker on the host.
2. The FULL behavioral trace is written to Forensic S3 (it stays in Forensic, RD-009).
3. A bounded, derived behavioral-telemetry summary crosses the RD-013 gate to the Hub
   (new envelope kind, its own version pin) — evidence, no verdict/safe/forward field.
4. Timestamps are relative monotonic offsets from detonation start (never a wall clock).
- Goes ✅ ONLY when the stakeholder confirms a live pass AND you RECORD it in
  RUNBOOK.md. No recorded pass → stays 🟡. On any fail: stay on 2.4, fix, re-validate.

# ENVIRONMENT
- Repo cloned; push to `feature/story-2.4`, never main. Open PRs via
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls` (NOT `gh pr create`). Merges are
  the repo-owner's action. Live AWS is the stakeholder's Forensic CloudShell action.

# WORKING AGREEMENT
- One story to completion: design → build → STAKEHOLDER validates live → you RECORD +
  flip status → paired status commit (+ restore tag). Push to a branch; open a PR.
- Validation drives status; the hard advancement gate governs advancement. Clearing
  open debt (e.g. finishing 2.3) is permitted while the register is non-empty; opening
  2.4 as new feature work is NOT until the register is empty.
- MANAGEMENT ARTIFACTS ARE FIRST-CLASS (RD-015): brief + RUNBOOK + PROJECT_PLAN aligned;
  any new RD + candidate mappings recorded; all via PR; governance restorable alongside
  the code. Re-run the G-3 doc checks after any status/register edit.
- At session end, author the NEXT story's brief + prompt (2.5 sanitization, or 2.6 fork
  per sequencing) with THIS session's real Lessons Learned. Zero cold-start.
- If blocked (incl. the register being non-empty), push partial progress + a draft PR;
  surface the blocker; never silently fail.
