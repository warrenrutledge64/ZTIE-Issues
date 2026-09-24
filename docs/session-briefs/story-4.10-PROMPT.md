# Session Prompt — Story 4.10 (Post-ACCEPT Forensic cleanup + a bounded S3 retention floor) — RD-059 — executor-facing

You are the execution agent for the ZTIE project. Read this fully before acting. Do NOT change
anything until you have (a) READ the plan + runbook + methodology + this story's brief
(`session-briefs/story-4.10-brief.md`) + `docs/architecture/AUTHENTICATED_DECISIONS.md`, (b)
re-established true state (STEP 0), and (c) confirmed the validation-gate state this story
depends on (STEP 0).

# PROJECT IDENTITY
ZTIE is a four-phase, AWS-native security pipeline. Three accounts: Pipeline-Hub
(641628980935) = control plane + durable tracking + the human accept/reject gate; Forensic
(360999005254) = the self-contained blast zone (intake, lanes, the raw artifact, the ephemeral
detonation host); Pipeline-Sandbox (586917955591) = the ZTIE→PDE handoff landing zone. On
ACCEPT, Story 4.6 pushes the hash-verified artifact Forensic→Sandbox; on REJECT, Story 4.7
destroys the artifact + chamber in Forensic. Validation covenant: nothing is ✅ until a
recorded live pass of the final code.

# WHY THIS STORY EXISTS (OD-009)
Story 4.6 COPIES the accepted artifact to the Sandbox and deletes NOTHING in Forensic, and the
Forensic artifact bucket's lifecycle expires only NONCURRENT versions (90d). So the CURRENT
`intake/<id>/` + derived `findings/<id>/` / `runs/<id>/` / `traces/<id>/` objects for every
accepted intake persist INDEFINITELY — an unbounded per-detonation S3 cost + raw-untrusted-bytes
residue in the blast zone (contrary to RD-012). 4.7 already sweeps on reject; 4.10 gives ACCEPT
the same clean-up + adds a retention floor for held/INCONCLUSIVE intakes. The ephemeral EC2
chamber is NOT part of this bleed (it self-terminates on the 5-min hard TTL on every path); the
per-run interface VPC endpoints are already swept. The leak is purely the S3 objects.

# WHERE THIS STORY SITS (build tier + position)
Tier 15 as a standalone cleanup Lambda, OR a 4.6 REWORK (preferred) at 4.6's tier — depends on
4.6 (✅). Sequenced AFTER 4.7 + 4.4 (Phase-4 closure) per OD-009. NOT on the Phase-4-closure
critical path — a cost/hygiene follow-on. Confirm the tier at the PLAN gate once the mechanism
fork is decided.

# WHAT THIS STORY IS
Two parts (RD-059): (1) a RETENTION FLOOR — a CURRENT-object S3 lifecycle expiration on the
Forensic artifact bucket so cost is bounded even for intakes that never reach a decision; and
(2) an EAGER POST-ACCEPT SWEEP — on a verified `accepted` decision, AFTER 4.6 confirms the
artifact landed in the Sandbox hash-matched, destroy that intake's Forensic prefixes (all
versions + delete-markers, exactly as 4.7 does on reject). The one sentence: **once the accepted
artifact is safely in the Sandbox, its Forensic copy + derived outputs are redundant and must be
destroyed — while the durable/reusable infra (VPC, subnets, gateway endpoint, SSM channel, IAM
roles, launch template, the buckets themselves) is KEPT.**

# NON-NEGOTIABLE CONSTRAINTS
- PLAN FIRST GATE: before writing code, outline the sweep mechanism (fold into 4.6 vs a separate
  Lambda), the landing-confirm-before-delete ordering, what the sweep deletes (the four intake
  prefixes, all versions), the retention floor (current-object expiration, window = a
  STAKEHOLDER decision), and the crossed outcome; resolve the FIVE design forks in the brief;
  get explicit approval before generating the implementation.
- CONFIRM THE LANDING BEFORE DELETING THE ORIGINAL: never destroy the sole Forensic copy until
  the Sandbox copy is positively verified (exists + sha match). A failed/unconfirmed push leaves
  Forensic intact (fail-safe — keep the only copy).
- KEEP THE DURABLE INFRA: destroy the intake's OBJECTS only — never the bucket, VPC, subnets,
  gateway endpoint, SSM channel, IAM roles, or launch template.
- NO COMPLIANCE-MODE OBJECT LOCK: the retention floor is PLAIN lifecycle expiration only (the
  standing no-WORM rule for ZTIE forensic data).
- NO SPOKE→HUB READ (RD-048): the accept decision is the SAME Hub-signed token 4.6 already
  verifies OFFLINE; do not introduce a Hub read. NEVER re-execute the artifact.
- If folding into 4.6 (✅), it is a REWORK — new story/branch, its own recorded live validation,
  a widened delete grant; do NOT retro-edit 4.6's ✅.
- Production-quality; AWS-native; VALIDATION-GATED; RESTORE-POINT discipline; DOCS FIRST-CLASS
  (RD-015): PLAN ↔ RUNBOOK exact.

# OPERATIONAL CONTEXT
Build sandbox is INTEGRATIONS_ONLY (no live AWS creds; PyPI + npm BLOCKED). You BUILD; the
STAKEHOLDER validates live (split-brain, RD-055 — the independent validator authors the DoD +
runbook blind from the PR; you author neither). Region us-east-1. This is a Forensic-account
story (the sweep + the bucket lifecycle are in Forensic; the accept decision is the Hub-signed
token). Run `aws sts get-caller-identity` before every operational block.

# HARD-WON LESSONS (apply directly)
- **Reuse the 4.7 versioned-delete** (`destroy_intake_prefixes` / `_delete_all_versions_under_
  prefix` in `lambdas/pde_reject/awsio.py` — deletes `Versions[]` + `DeleteMarkers[]`, batched
  at the 1000 cap). A versioned bucket needs ALL versions + markers gone, not a tombstone
  (OD-001). Consider sharing the helper.
- **The Forensic artifact bucket** is defined in `infra/lib/ztie-intake-stack.ts`
  (`IntakeArtifactBucket`): KMS-managed, versioned, block-public, `enforceSSL`, RETAIN, NO
  Object Lock; lifecycle currently = noncurrent-version expiration 90d + abort-incomplete-MPU
  7d. Add the current-object expiration alongside (do NOT remove the existing rule).
- **⛔ NON-SKIPPABLE post-deploy CODE-ASSET gate** ([`story-2.4R-DEPLOY-VERIFY.md`](story-2.4R-DEPLOY-VERIFY.md)):
  before concluding ANY live validation, grep the LIVE Lambda zip for THIS story's structural
  markers (the sweep + the landing-confirm) + a probe-absent guard. NEVER an env-var read; NEVER
  trust a green `UPDATE_COMPLETE`. Also verify the LIVE bucket lifecycle with
  `aws s3api get-bucket-lifecycle-configuration`.
- Pass any multi-line CDK context value as SINGLE-LINE base64 (the 4.6 PEM-truncation defect).
- DynamoDB Number → Decimal: coerce any numeric read off the tracking item; never strict
  `isinstance(int)`.
- Offline proof bar: `~/.pyenv/versions/3.12.13/bin/python3 -m unittest`;
  `~/.pyenv/versions/3.12.13/bin/ruff check`; `env -u NODE_OPTIONS npx tsc --noEmit` (NO new
  error TYPE); `env -u NODE_OPTIONS npx prettier --write`. `gh pr create` is BROKEN — use
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`.

# STEP 0 — RE-ESTABLISH TRUE STATE (before any edit)
- SECRET SCAN the in-scope files; STOP + surface if any secret is found.
- `git fetch origin`; `git checkout main`; `git reset --hard origin/main`. List open PRs.
- `python3 scripts/check_docs.py` → expected PASS. `~/.pyenv/versions/3.12.13/bin/python3 -m
  unittest scripts.test_check_docs` → SUITE OK.
- Confirm EXPECTED TRUTHS on `main`: **4.6 ✅** (and per the recorded sequence 4.7 + 4.4 done);
  the Validation Debt Register EMPTY (gate DISARMED). If non-empty, clear the open entry first.
- RD-059 is already registered (proposed). If the mechanism needs a genuinely new sub-decision,
  verify the next free RD (`grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md | sort -u | tail`) and add
  its plan-table row BEFORE any living-doc reference (CHECK E literal).
- Branch off `main`: `feature/story-4.10` (or `feature/story-4.6-rework-cleanup` if folding).

# THIS SESSION'S OBJECTIVE
Build the retention floor + the eager post-accept sweep: add a current-object S3 lifecycle
expiration on the Forensic artifact bucket; on a verified accept + a confirmed Sandbox landing,
destroy the accepted intake's four Forensic prefixes (all versions), keeping the durable infra.
Close OD-009 on the live pass.

# SCOPE & GUARDRAILS
- Blast radius: the bucket lifecycle rule + the post-accept sweep (in the 4.6 pusher or a new
  cleanup Lambda) + its delete grant + the crossed-outcome field. Do NOT touch verdict/decision
  logic, the lanes, or the Hub-processing Lambdas beyond a possibly-extended outcome field.
- Out of scope: re-executing the artifact (NEVER); tearing down the VPC/buckets/roles/launch
  template; ServiceNow; changing the accept DECISION path (that is 4.4/4.6).
- Depends on (must be ✅): 4.6 (and per the sequence, 4.7 + 4.4).

# DEFINITION OF DONE (this session) — a PASS/FAIL GATE
- LIVE, recorded: the retention floor is live (get-bucket-lifecycle-configuration shows
  current-object expiration on the four prefixes + the existing noncurrent rule; NO Object
  Lock); a fresh intake is ACCEPTED, 4.6 pushes + confirms the landing, and the intake's four
  Forensic prefixes are then EMPTY (0 versions + 0 markers) while the VPC/buckets/roles/launch
  template are untouched; a failed/unconfirmed push leaves Forensic intact (fail-safe); the
  derived report + durable record survive in the Hub.
- Goes ✅ ONLY on a recorded live pass of the final code. No recorded pass → stays 🟡.
- On the live pass, CLOSE OD-009 with a dated evidence note.

# WORKING AGREEMENT
- One story to completion. Design → build → STAKEHOLDER validates live → RECORD + flip status →
  paired commit. Branch + PR, never main directly.
- MANAGEMENT ARTIFACTS ARE FIRST-CLASS (RD-015): RD-059 row already in PROJECT_PLAN (ratify on
  review); RUNBOOK 4.10 ⬜→🟡 + register entry in the same commit; PLAN ↔ RUNBOOK exact; repoint
  `_NEW_WORK_STORY` off 4.10 if it lands there. Run check_docs AFTER committing the status edit.
- At session end author the 4.10 LIVE-RUNBOOK + the next-story handoff before pointing the
  on-deck README at them (CHECK I). On the live pass, close OD-009.
- If blocked, push partial progress + a draft PR; never silently fail.
