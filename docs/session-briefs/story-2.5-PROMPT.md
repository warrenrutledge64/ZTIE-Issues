You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting. Do NOT change anything until you have (a) READ the
plan + runbook + methodology + this story's brief (`session-briefs/story-2.5-brief.md`),
(b) re-established true state (STEP 0), and (c) confirmed the Validation Debt Register
state + advancement gate.

# PROJECT IDENTITY
ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted artifact
BEFORE it reaches the PDE. Work is validation-gated: nothing is ✅ until a recorded live
pass (the covenant). Three accounts: Pipeline-Hub (641628980935) = brains/control plane
+ durable record; Forensic (360999005254) = self-contained blast zone (ephemeral only);
Pipeline-Sandbox (586917955591) = ZTIE→PDE handoff. Story 2.5 is the SANITIZATION stage
on the DYNAMIC lane: it takes the RAW behavioral telemetry Story 2.4 captures and cleans
it (entropy scrub → noise suppress → ≤25K-token truncation) into the bounded view the
Phase-3 Nova Pro correlation engine reasons over.

# WHAT THIS STORY IS (nature + gate role)
NEW FEATURE story. It may begin ONLY if its Depends-on are ALL ✅ AND the Validation
Debt Register is empty. **As of this prompt (2026-09-10):**
- **2.4 ✅** (behavioral telemetry capture — the RAW telemetry 2.5 sanitizes; validated
  live 2026-09-10, 4/4 DoD, intake_id 16c2af41-e898-410d-b723-44b798f4f0d3).
The Validation Debt Register is EMPTY (2.4 cleared on its own recorded live pass); the
advancement gate is OPEN. STEP 0 must RE-CONFIRM this on `main` (trust `main` +
`check_docs` over this prompt; if they disagree, `main` wins). 2.5 is build tier 8 and is
the NEXT story by tier now that 2.4 closed ✅.

# WHERE 2.5 SITS (what already exists that it builds on)
- **2.4 (behavioral capture, ✅ 2026-09-10, RD-030):** `lambdas/detonation/` now runs the
  artifact UNDER host-native `strace` (`strace -ff -tt -y -s 256 -e
  trace=%file,%network,%process,%signal`, traced DIRECTLY — not a `sh -c` wrapper),
  writes the FULL trace to Forensic S3 `traces/<intake_id>/behavior-trace.txt` (RD-009),
  and crosses a bounded, verdict-free `behavior` summary (the 8th RD-013 envelope kind,
  own `BEHAVIOR_CONTRACT_VERSION`, discriminated by a `behavior` object) to the Hub.
  `lambdas/detonation/behavior.py` is the PURE parser (syscalls tally / network-as-INTENT
  / filesystem op-classes + salient paths); `capturespec.py` builds the host-native
  command; `awsio.py` has `put_trace` + `send_behavior_envelope`. The raw trace 2.5
  sanitizes FAITHFULLY includes SSM-agent + shell/coreutils host noise + high-entropy
  blobs — that is the raw material.
- **2.6 (orchestration, ✅):** the preprocessor starts a Step Functions STANDARD state
  machine whose Parallel state forks the static + dynamic lanes and DIRECT-invokes the
  detonation Lambda. **2.5 modifies the detonation/telemetry path 2.6 orchestrates —
  coordinate with both (see the DEPLOY-GAP lesson).**

# NON-NEGOTIABLE CONSTRAINTS
- SANITIZE, DO NOT RE-CAPTURE. 2.5 consumes 2.4's raw telemetry (the Forensic trace and/
  or the 2.4 summary) and cleans it. Capture is 2.4 (done) — do not re-litigate it.
- THREE STAGES IN ORDER: (1) entropy scrub (redact high-entropy VALUES — keys/base64/
  random blobs — while KEEPING the behavioral structure), (2) noise suppress (drop the
  deterministic host/runtime noise — SSM-agent boot, dynamic-linker library loads,
  locale-archive opens, shell/coreutils startup — that is NOT the artifact's behavior),
  (3) ≤25K-token truncation (deterministic, with a recorded `truncated` flag).
- EVIDENCE, NEVER A VERDICT. The sanitized view has NO verdict/safe/approved/forward
  field. The verdict is Hub-side/human-gated (Phase 4).
- FULL RAW TRACE STAYS IN FORENSIC (RD-009); only the bounded, sanitized view crosses.
  Decide CONTRACT-FIRST whether it is a NEW envelope kind (own version pin + own
  discriminator) or a refinement of 2.4's summary — do not collide with the eight
  existing discriminators (classification/routing/rejection/scan/run/status/collected/
  behavior) and do not reuse a shared CONTRACT_VERSION.
- RELATIVE CLOCK ONLY — timestamps stay monotonic offsets from detonation start.
- PURE LOGIC + THIN SEAM (the proven 1.2→2.3→2.4 pattern). The sanitization pipeline is
  PURE + offline-testable; any I/O (read the Forensic trace, cross the sanitized view) is
  behind thin boto3 seams. A seam failure is recorded, never crashes the lane.
- VALIDATION-GATED, NEVER ON INFERENCE: 2.5 flips ✅ only on a recorded live pass of the
  FINAL code (METHODOLOGY §4).
- ROLES: the LIVE run is the STAKEHOLDER's action in Forensic (executor has NO live
  creds); the executor RECORDS the returned output VERBATIM. Do NOT simulate.
- DOCS FIRST-CLASS (RD-015): PR-reviewed, never straight to main; PROJECT_PLAN ↔ RUNBOOK
  in EXACT alignment.

# NEW REGISTERED DECISION
Record the sanitization design as a new RD with rationale + candidate NIST/ISO mappings.
RE-VERIFY the next free RD number at STEP 0 with
`grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md | sort -u | tail` and take the next free
number (RD-030 is 2.4's; expect RD-031, but VERIFY — RD-number collisions have happened).

# OPERATIONAL CONTEXT (state this on EVERY command block)
  Build sandbox is INTEGRATIONS_ONLY (NO AWS creds; PyPI + npm BLOCKED — boto3/pytest/
  moto/jsonschema/aws-cdk-lib NOT installable). You BUILD; the USER validates live in
  CloudShell (ambient creds, no --profile). Region us-east-1. Confirm the active
  account with `aws sts get-caller-identity` before EVERY operational block. The
  detonation host + capture + all artifact-touching compute are in FORENSIC
  (360999005254); the tracking table is in the HUB (641628980935) — TWO CloudShell tabs.
  Tooling: `ruff` is NOT on PATH — use `~/.pyenv/versions/3.12.13/bin/ruff`; `prettier`
  and `npx tsc` need `env -u NODE_OPTIONS`; npm is BLOCKED so `tsc --noEmit` legitimately
  shows ONLY the missing-`aws-cdk-lib` error family (TS2307/2339/2353/2591/2304)
  identical across all stacks — confirm the new code adds NO NEW error TYPE.

# HARD-WON LESSONS (do NOT repeat)

## DEPLOY-GAP — the recurring #1 live lesson (2.6, re-confirmed live in 2.4 2026-09-10)
When a story changes a lane Lambda that an EARLIER story's orchestration invokes, the
LIVE lane can still be running its OLD deployed code. In 2.4 EVERY code change (including
the mid-validation capture fix) only took effect after `cdk deploy ZtieDetonationStack`.
So 2.5's LIVE validation MUST redeploy `ZtieDetonationStack` (and `ZtieHubTrackingStack`
if the contract changes — the Hub must ship the new/updated contract bundle or the
crossed record fail-closed QUARANTINES) BEFORE submitting a run. Put the redeploys as an
explicit pre-run step in the 2.5 LIVE-RUNBOOK.

## Capture-completeness (2.4 commit 71c3387) — do NOT regress it
2.4's first two live runs captured only SSM-agent/shell noise and ZERO artifact ops
because strace traced a `sh -c 'if head -c2 FILE | grep -q "^#!"; then FILE; …'` WRAPPER
(the shebang check ran as forked head/grep children) and its single `-o` file was read
partially-flushed. Fix: trace the artifact DIRECTLY (shebang decided in the OUTER
untraced shell) + `strace -ff` (one file per PID, concatenated on emit) + `sync` before
reading. If 2.5 post-processes the trace or touches `capturespec.py`, preserve this.

## Host noise is the TARGET of 2.5, not an accident
2.4's raw trace faithfully includes SSM-agent boot, dynamic-linker library loads,
locale-archive opens, shell/coreutils startup. 2.4's crossed top-50 sample was dominated
by this noise until a test artifact repeated an op 40×. 2.5's noise-suppression is
exactly about telling that deterministic host noise apart from the artifact's own
behavior — DESIGN IT AGAINST A REAL TRACE (pull a real
`traces/<intake_id>/behavior-trace.txt` from Forensic and look at what is actually there;
2.4's passing run was intake_id 16c2af41-e898-410d-b723-44b798f4f0d3).

## AMI tooling gap (2.4 live)
The ubuntu-22.04 golden AMI ships `strace` (2.4 confirmed) but NOT `curl` (2.4's curl
probe produced no `execve`/`connect`, so `network.connect_attempts=0` — honest, nothing
to capture). If a 2.5 test needs a network syscall, use a binary the AMI ships or add the
tool to the golden AMI (Image-Builder-owned, outside this repo; AL2023 build still
broken → ubuntu-only).

## Build + governance discipline (still true)
- The lane pattern held again (1.2→2.2→2.3→2.4): contract-first + pure logic + thin
  boto3 seam + evidence-never-verdict + (if a new kind) own version pin + own
  discriminator. Keep the sanitization pipeline PURE + offline-testable.
- Branch the CODE off `main` (current HEAD, which contains merged 2.3 + 2.6 + 2.4), NOT
  off a restore tag — restore tags are ancestors and predate later merged stories.
- STALE-BRANCH TRAP: if this branch sits while another story merges,
  `git merge-base main <branch>` + `git diff --stat main..<branch>` — if the diff DELETES
  files of an already-merged story, `git merge origin/main` in, resolve keeping BOTH,
  COMMIT the merge, then re-run checks.
- Offline proof bar: stdlib `unittest` over fixtures + a MANUAL pure-Python conformance
  walk (jsonschema not installable) — two layers incl. a recursive no-verdict-key scan +
  a schema-has-no-verdict-property check. Prove the sanitizer against a REAL captured
  trace fixture (entropy blob scrubbed, host noise dropped, artifact ops preserved,
  ≤25K-token truncation deterministic + flagged).
- Governance-tooling can DRIFT (RD-015): run `scripts/check_docs.py` only AFTER
  committing any status/register change (CHECK B's baseline is `git show HEAD:RUNBOOK.md`
  — running before the commit gives a FALSE-POSITIVE). Also run
  `python3 -m unittest scripts.test_check_docs` (its `check_docs: FAIL …` fixture lines
  are the checker testing ITSELF; the suite still reports OK / 3 tests). If 2.5 goes 🟡,
  it MUST be added to the Validation Debt Register in the same commit or CHECK A fails.
- Two accounts, two tabs, `aws sts get-caller-identity` before EVERY block — the single
  most repeated live mistake in 2.4 (a `ResourceNotFoundException` on the Hub table = you
  queried it from Forensic). `/tmp` + shell vars + pip installs are WIPED on CloudShell
  recycle — re-set every variable AND reinstall `awscurl` in the SAME block right before
  use. Placeholders like `<...>` in a pasted command are literal `<`/`>` shell
  redirections and error with `syntax error near unexpected token` — ALWAYS substitute
  REAL values before running.
- Intake API wants a JSON envelope via awscurl (SigV4), NOT a raw file body:
  `{"filename":…, "content_type":…, "submitter":…, "content_base64":"<base64 of raw
  bytes>"}` with `-H 'Content-Type: application/json' -d @file.json`; put the URL BEFORE
  the flags. `pip install awscurl` first. `gh pr create` is BROKEN — open PRs via
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`.

# STEP 0 — RE-ESTABLISH TRUE STATE (before any edit)
# Trust `main` + `check_docs` over anything written here; if they disagree, `main` wins.
- `git fetch origin`; `git checkout main`; `git reset --hard origin/main`. List open PRs.
- `python3 scripts/check_docs.py` → expect PASS. `python3 -m unittest
  scripts.test_check_docs` → expect OK (3 tests).
- Confirm these EXPECTED TRUTHS (do NOT change until validated live):
    - This story = 2.5 = ⬜ (not started), build tier 8, Depends-on `2.4`.
    - Dep ✅: `grep -nE "\[2\.4\]" RUNBOOK.md` → ✅ (validated 2026-09-10).
    - Validation Debt Register = EMPTY → advancement gate OPEN for 2.5.
    - 2.4 = ✅ (2026-09-10); 2.0/2.1/2.2/2.3/2.6 = ✅.
    - Restore tags: `git ls-remote --tags origin | grep restore/` should list the six
      known tags + (once the owner tags it) `restore/story-2.4-green` on the 2.4 merge.
    - Next free RD number: RE-VERIFY (expect RD-031).
- Branch off `main` (current HEAD). Branch name: `feature/story-2.5`.

# THIS SESSION'S OBJECTIVE
Take the raw behavioral telemetry Story 2.4 captures and sanitize it: entropy scrub →
noise suppress → ≤25K-token truncation, producing a bounded, derived, verdict-free
sanitized view (full raw trace stays in Forensic; only the sanitized view crosses).
Get the stakeholder to validate live that a real detonation's raw trace is sanitized
(host noise + high-entropy blobs removed, artifact behavior preserved, ≤25K tokens).

# SCOPE & GUARDRAILS
- In scope: the entropy-scrub → noise-suppress → ≤25K-token-truncation pipeline (PURE +
  offline-testable); the bounded sanitized view (contract-first; own kind + version pin
  or a refinement of 2.4's — decide + justify); deterministic truncation + a recorded
  truncated flag; relative timestamps preserved; pure logic + thin seams; tests; a new RD
  + candidate control mappings; any golden-AMI change if strictly needed.
- Out of scope / do NOT touch: behavioral CAPTURE (2.4 — done); the Hub verdict; the
  static lane; the fork/orchestration internals (2.6 — but you MUST redeploy the lane
  stacks it orchestrates for validation, deploy-gap); Docker on the host; re-litigating
  the 2.4 behavior contract.
- Depends on (must be ✅): 2.4. Plus an EMPTY Validation Debt Register.

# DEFINITION OF DONE (this session) — a PASS/FAIL GATE
The stakeholder confirms live:
1. A real detonation's RAW behavioral trace is run through the pipeline; the SANITIZED
   output has host/runtime noise suppressed + high-entropy blobs scrubbed, artifact
   behavior preserved.
2. The sanitized view is bounded to ≤25K tokens (deterministic truncation + recorded
   truncated flag).
3. The sanitized view is EVIDENCE (no verdict/safe/forward field); the FULL raw trace
   stays in Forensic (RD-009); relative monotonic timestamps preserved.
4. It crosses / attaches per the RD-013 gate (own version pin if a new kind).
- Goes ✅ ONLY when the stakeholder confirms a live pass AND you RECORD it in RUNBOOK.md.
  No recorded pass → stays 🟡 (and 2.5 goes on the Validation Debt Register in the same
  commit). On any fail: stay on 2.5, fix, re-validate.

# ENVIRONMENT
- Repo cloned; push to `feature/story-2.5`, never main. Open PRs via
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls` (NOT `gh pr create`). Merges are the
  repo-owner's action. Live AWS is the stakeholder's Forensic/Hub CloudShell action.

# WORKING AGREEMENT
- One story to completion: design → build → STAKEHOLDER validates live (redeploy the
  detonation lane stack FIRST per the deploy-gap lesson) → you RECORD + flip status →
  paired status commit; push to a branch; open a PR. After merge,
  `git log main..feature/story-2.5` to confirm the whole branch landed (base-branch trap);
  the restore tag (owner action) points at the merge commit that carries the validated code.
- Validation drives status; the hard advancement gate governs advancement.
- MANAGEMENT ARTIFACTS ARE FIRST-CLASS (RD-015): brief + RUNBOOK + PROJECT_PLAN aligned;
  the new RD + candidate NIST/ISO mappings recorded; all via PR; governance restorable
  alongside the code. Re-run the G-3 doc checks AFTER committing any status edit.
- At session end, author the NEXT story's brief + prompt with THIS session's real Lessons
  Learned (next by tier after 2.5: 3.1 telemetry aggregation, or as the graph leaves it).
  Zero cold-start.
- If blocked, push partial progress + a draft PR; surface the blocker; never silently fail.
