You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting. Do NOT change anything until you have (a) READ the
plan + runbook + methodology + this story's brief (`session-briefs/story-2.3-brief.md`),
(b) re-established true state (STEP 0), and (c) confirmed the Validation Debt Register
state + advancement gate.

# PROJECT IDENTITY
ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted
artifact BEFORE it reaches the PDE. Work is validation-gated: nothing is ✅ until a
recorded live pass (the covenant). Three accounts: Pipeline-Hub (641628980935) =
brains/control plane + durable record; Forensic (360999005254) = self-contained blast
zone (ephemeral only); Pipeline-Sandbox (586917955591) = ZTIE→PDE handoff. Story 2.3
builds the P2 DYNAMIC lane — the detonation chamber where a routed artifact is
actually EXECUTED, safely, inside the Forensic isolated VPC. It is the runtime
counterpart to the non-executing static lane (2.1/2.2).

# WHAT THIS STORY IS  (nature + gate role)
NEW FEATURE story. It may begin ONLY if its Depends-on are all ✅ AND the Validation
Debt Register is empty. Its hard dependency 2.0 is ✅. BUT 2.2 (PR #48) is 🟡 (built,
pending live validation) and sits in the register until the stakeholder validates it —
so the advancement gate is LIKELY CLOSED when you pick this up. THE CATEGORY ERROR TO
PREVENT: do NOT start 2.3 feature work while the register is non-empty. STEP 0 must
re-check the register; if 2.2 (or anything) is open, the correct move is to finish
that live validation first (or record a stakeholder de-scope/defer per RD-024), not
to build 2.3 on open debt.

# NON-NEGOTIABLE CONSTRAINTS
- EXECUTION IS NOW ON — but ONLY inside Forensic, ONLY on the ephemeral EC2, ONLY
  host-native via SSM (SendCommand / run document), NEVER in the Hub, and NEVER with
  Docker/containers on the detonation host (RD-001 — a container distorts behavioral
  telemetry; instances are "ephemeral", never "temporary").
- 5-MINUTE HARD TTL IS MANDATORY and must be PROVEN to fire (2.0's UserData carries
  `shutdown -h +5`). An instance that outlives its TTL is the dangerous failure mode.
- EVIDENCE, NEVER A VERDICT. 2.3 emits a bounded, derived RUN-OUTCOME record — no
  verdict/safe/approved/forward field anywhere. The verdict is Hub-side/human-gated
  (Phase 4). (Behavioral telemetry itself is 2.4, NOT this story.)
- CONTRACT-FIRST. Design the run-outcome shape first: a NEW RD-013 envelope kind with
  its OWN Hub version pin (do NOT reuse the shared CONTRACT_VERSION — 2.2's lesson).
  Emit schemas via a `python json.dump` generator into BOTH `schemas/` and the bundled
  copy; hash-match.
- PURE LOGIC + THIN SEAM (the proven 1.2→2.2 pattern). Run-plan / outcome normalization
  pure + offline-testable; `ec2`/`ssm` + artifact-delivery behind thin boto3 seams. A
  seam failure is recorded, never crashes the lane.
- VALIDATION-GATED, NEVER ON INFERENCE: 2.3 flips ✅ only on a recorded live pass of
  the FINAL code (METHODOLOGY §4).
- ROLES: the LIVE detonation run + teardown check is the STAKEHOLDER's action in
  Forensic (executor has NO live creds); the executor RECORDS the returned output
  VERBATIM. Do NOT simulate/assume a live output.
- DOCS FIRST-CLASS (RD-015): PR-reviewed, never straight to main; PROJECT_PLAN ↔
  RUNBOOK in EXACT alignment. Keep unrelated governance edits OFF this feature branch
  (2.2 lesson: they were split to their own PR #47).

# OPERATIONAL CONTEXT (state this on EVERY command block)
  Build sandbox is INTEGRATIONS_ONLY (NO AWS creds; PyPI + npm BLOCKED — boto3/pytest/
  moto/jsonschema/aws-cdk-lib NOT installable). You BUILD; the USER validates live in
  CloudShell (ambient creds, no --profile). Region us-east-1. Confirm the active
  account with `aws sts get-caller-identity` before EVERY operational block. The
  detonation host + all artifact-touching compute are in FORENSIC (360999005254); the
  tracking table is in the HUB (641628980935) — TWO CloudShell tabs.

# HARD-WON LESSONS (do NOT repeat) — carried from the 2.2 build session
- Contract-first + pure-logic/thin-seam + evidence-never-verdict is the lane pattern;
  reuse it for 2.3's run-plan/outcome vs. the ec2/ssm seam.
- The Hub gate pins EACH envelope kind's version SEPARATELY (2.2 added
  SUMMARY_CONTRACT_VERSION). A new dynamic-run envelope kind gets its OWN pin.
- Regenerate schemas via the `gen_*` scripts into BOTH copies + hash-check (fs_write
  refuses a remote `$schema`).
- Offline proof bar: stdlib `unittest` over fixtures + a MANUAL pure-Python conformance
  walk (jsonschema not installable); `ruff` clean; `tsc --noEmit`/`prettier --check`
  show ONLY the environmental missing-`aws-cdk-lib` family (identical on live stacks).
- Two-account / wrong-account recurs: `ResourceNotFoundException` on the tracking table
  = you queried it from Forensic (it's in the Hub). Run `aws sts get-caller-identity`
  before each block. `gh pr create` is BROKEN — open PRs via
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`.
- Container-image deploy needs a Docker build box — but that was the STATIC-SCAN image;
  2.3's compute may be a plain zip Lambda / Step Function, so confirm whether one is
  even needed before spinning up an EC2 build box.

# STEP 0 — RE-ESTABLISH TRUE STATE (before any edit)
# Trust `main` + `check_docs` over anything written here; if they disagree, `main` wins.
- git fetch/pull latest; list open PRs (expect: #48 Story 2.2 feature; #47 governance
  templates — confirm their merge state).
- `python3 scripts/check_docs.py` → expect PASS.
- Confirm these EXPECTED TRUTHS (do NOT change them until validated live):
    - This story = 2.3 = ⬜ (not started).
    - Depends-on: 2.0 = ✅ (validated 2026-09-02, tag `restore/story-2.0-green`).
    - 2.1 = ✅ (2026-09-01). 2.2 = 🟡 OR ✅ — CHECK: if 2.2's PR #48 was validated +
      flipped ✅, the register is empty and 2.3 may start; if still 🟡, the register is
      NON-EMPTY and 2.3 is GATED (finish 2.2 first).
    - Restore tags present: `restore/phase-1-green`, `restore/story-2.0-green`,
      `restore/story-2.1-green`. PHANTOM TAG: `restore/phase-2-floor-green` is
      referenced in BOM.md + RUNBOOK.md (A.4) but does NOT exist in `git tag -l` —
      resolve (owner pushes it OR reconcile docs to `restore/story-2.1-green`) before
      relying on the "Phase-2 floor" as a rollback target. Do NOT silently create it.
    - Validation Debt Register state + G-3 hard advancement gate in place.
- Branch off `restore/story-2.0-green` (the infra 2.3 runs on) or main at that commit.
  Branch name: `feature/story-2.3`.

# THIS SESSION'S OBJECTIVE
Build the dynamic lane: a `dynamic_analysis`-routed artifact launches ONE ephemeral
EC2 from the 2.0 launch template into the Forensic isolated VPC, is delivered + run
host-native via SSM (NO Docker), self-terminates on the 5-min hard TTL, and a bounded
verdict-free run-outcome record crosses to the Hub. Get the stakeholder to validate
live that a real instance ran the artifact and was torn down.

# SCOPE & GUARDRAILS
- In scope: consume a dynamic-analysis work item; `ec2:RunInstances` via the 2.0
  launch template (NOT CloudFormation-per-run); host-native SSM execution; TTL
  teardown; a bounded derived run-outcome contract crossing the RD-013 gate (new
  envelope kind, its own version pin); pure logic + thin seams; tests; a new RD for
  the run-document/artifact-delivery choice + candidate control mappings.
- Out of scope / do NOT touch: behavioral telemetry capture (2.4); the fork /
  orchestration (2.6); telemetry sanitization (2.5); the Hub verdict; the static lane
  (2.1/2.2); Docker on the detonation host.
- Depends on (must be ✅): 2.0. Plus an EMPTY Validation Debt Register.

# DEFINITION OF DONE (this session) — a PASS/FAIL GATE
The stakeholder confirms live in Forensic 360999005254:
1. A routed artifact launches ONE ephemeral EC2 FROM the 2.0 launch template
   (`ec2:RunInstances` via the template) into the isolated VPC.
2. The artifact is delivered + executed host-native via SSM (run document /
   SendCommand) — NO Docker/container on the host (RD-001).
3. The instance is torn down by the 5-min hard TTL (`shutdown -h +5`). KNOWN CAVEAT:
   2.0's UserData carries the TTL; if the instance is still running past it, that is
   the finding — record it, do NOT pass the check.
4. A bounded, derived run-outcome record crosses the RD-013 gate to the Hub (evidence,
   no verdict/safe/forward field).
- Goes ✅ ONLY when the stakeholder confirms a live pass AND you RECORD it in
  RUNBOOK.md. No recorded pass → stays 🟡. On any fail: stay on 2.3, fix, re-validate.

# ENVIRONMENT
- Repo cloned; push to `feature/story-2.3`, never main. Open PRs via
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls` (NOT `gh pr create`). Merges are
  the repo-owner's action. Live AWS is the stakeholder's Forensic CloudShell action.

# WORKING AGREEMENT
- One story to completion: design → build → STAKEHOLDER validates live → you RECORD +
  flip status → paired status commit (+ restore tag). Push to a branch; open a PR.
- Validation drives status; the hard advancement gate governs advancement. Clearing
  open debt (e.g. finishing 2.2) is permitted while the register is non-empty; opening
  2.3 as new feature work is NOT until the register is empty.
- MANAGEMENT ARTIFACTS ARE FIRST-CLASS (RD-015): brief + RUNBOOK + PROJECT_PLAN aligned;
  any new RD + candidate mappings recorded; all via PR; governance restorable alongside
  the code. Keep unrelated governance edits on their own branch (2.2 lesson).
- At session end, author the NEXT story's brief + prompt (2.4 behavioral telemetry
  capture) with THIS session's real Lessons Learned. Zero cold-start.
- If blocked (incl. the register being non-empty), push partial progress + a draft PR;
  surface the blocker; never silently fail.
