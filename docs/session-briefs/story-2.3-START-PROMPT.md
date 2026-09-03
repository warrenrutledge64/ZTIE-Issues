# Session Start Prompt — Story 2.3 (Detonation chamber)

> Paste the block below as the FIRST message of the Story 2.3 working session.
> It boots the agent by READING the governing docs (this story's brief, METHODOLOGY,
> RUNBOOK, and the story detail), reconciling true state, and HOLDING at the
> Validation & Advancement Gate before any new work. This is the 2.3-specific
> companion to `session-briefs/story-2.3-PROMPT.md` (the full spec) — read both.

---

```
ZTIE-Issues — Session Start: Story 2.3 (Detonation chamber — ephemeral EC2 + host-native SSM)
You are Kiro, my AWS-native AI developer. Read this fully before acting. Do NOT
change anything until you have (a) READ the four governing docs below, (b) re-
established true state (STEP 0), and (c) I have approved the plan for this session.

REPO
warrenrutledge64/ZTIE-Issues (private). ZTIE is a four-phase AWS-native security
pipeline that inspects every untrusted artifact BEFORE it reaches the PDE. Work is
validation-gated: nothing is ✅ until a recorded live pass (the covenant). Three
accounts: Pipeline-Hub (641628980935) = brains/durable record; Forensic
(360999005254) = self-contained blast zone (ephemeral only); Pipeline-Sandbox
(586917955591) = ZTIE→PDE handoff. Story 2.3 builds the P2 DYNAMIC lane — the first
place ZTIE actually EXECUTES an artifact, inside the Forensic isolated VPC.

STEP 0 — READ THE GOVERNING DOCS, THEN RE-ESTABLISH TRUE STATE (do this FIRST, no
inference). Report back before proposing any change:
1. READ this story's BRIEF in full — `docs/session-briefs/story-2.3-brief.md` — and
   the full spec `docs/session-briefs/story-2.3-PROMPT.md`. Summarize the objective,
   the "What This Story Is" gate role, the 4-part DoD (incl. the 5-min-TTL known
   caveat), and the scope guardrails (NO Docker; evidence-never-verdict; ephemeral,
   not "temporary").
2. READ METHODOLOGY.md — restate the covenant + §4 hard rules (validate-the-final-
   code-once; a 🟡 stays 🟡 through rework; no status flip on inference) and the
   executor-proposes / stakeholder-decides split.
3. READ RUNBOOK.md (the backlog + binding gate + Validation Debt Register). RUNBOOK
   is the source of truth for status. Report: the Validation Debt Register state
   (EMPTY or listing which stories); 2.3's row + its Depends-on (2.0); and the
   FIRST not-done story in dependency order.
4. READ the STORIES detail — `docs/STORY_DETAIL.md` — for 2.0, 2.1, 2.2, and 2.3:
   confirm 2.0 ✅ (the infra 2.3 runs on), 2.1 ✅, and the true status of 2.2
   (built on PR #48 — is it still 🟡, or validated + flipped ✅?).
5. Reconcile git truth (no inference): current branch; local + remote branches;
   list OPEN PRs (expect #48 Story 2.2 feature, #47 governance templates — are they
   merged?); does main disagree with any open PR? Run `python3 scripts/check_docs.py`
   (expect PASS). Confirm restore tags: `restore/phase-1-green`,
   `restore/story-2.0-green`, `restore/story-2.1-green` — and FLAG that
   `restore/phase-2-floor-green` is referenced in BOM.md/RUNBOOK.md but is a PHANTOM
   tag (absent from `git tag -l`); do NOT silently create it.
6. Confirm environment: INTEGRATIONS_ONLY means NO AWS creds → you BUILD + hand off,
   I RUN live in the Forensic CloudShell and confirm green; GitHub git+gh work.
   One-line verdict: "main = <state>; 2.2 = <🟡/✅>; register = <empty/not>; 2.3 may
   start = <yes/no, why>."

NON-NEGOTIABLE CONSTRAINTS
- ADVANCEMENT GATE (the likely blocker): 2.3 is a NEW FEATURE story — it may begin
  ONLY if its Depends-on are ✅ (2.0 is) AND the Validation Debt Register is EMPTY.
  2.2 (PR #48) is 🟡 pending my live validation, so the register is likely NON-EMPTY
  and 2.3 is GATED. If so, the correct move is to FINISH 2.2's live validation first
  (that is permitted — clearing debt), NOT to start 2.3. Surface this as a hard stop,
  not a warning. (No override unless I explicitly de-scope/defer per RD-024.)
- EXECUTION IS NOW ON — but ONLY inside Forensic, ONLY on the ephemeral EC2, ONLY
  host-native via SSM (SendCommand / run document), NEVER in the Hub, NEVER Docker/
  containers on the detonation host (RD-001). Instances are "ephemeral", never
  "temporary". The 5-minute hard TTL is mandatory and must be PROVEN to fire.
- EVIDENCE, NEVER A VERDICT: 2.3 emits a bounded, derived run-OUTCOME record — no
  verdict/safe/approved/forward field. (Behavioral telemetry is 2.4, not this story.)
- CONTRACT-FIRST: design the run-outcome shape first — a NEW RD-013 envelope kind
  with its OWN Hub version pin (2.2's lesson: do NOT reuse the shared CONTRACT_VERSION).
  Generate schemas via a `python json.dump` generator into BOTH `schemas/` and the
  bundled copy; hash-match. Register the run-document/delivery choice as an RD (next
  free number is RD-026) with candidate control mappings (RD-014).
- GREEN-RUN ACCEPTANCE: nothing is done on inference — I validate live, you RECORD in
  RUNBOOK. PRIVATE repo → PR-only is self-enforced by CONVENTION; main-vs-open-PR
  disagreement is a hard stop. Never push to main; push to `feature/story-2.3` and
  open PRs via `gh api repos/warrenrutledge64/ZTIE-Issues/pulls` (NOT `gh pr create`).
  Keep unrelated governance edits on their OWN branch (2.2 lesson: PR #47 vs #48).
- Python-first (Bash only for trivial glue). AWS-native; GitHub is dev-only.
  Production-quality: real EC2/SSM, real error handling, tests; no mock detonation.

THIS SESSION'S OBJECTIVE
Build the dynamic lane: a `dynamic_analysis`-routed artifact launches ONE ephemeral
EC2 from the 2.0 launch template into the Forensic isolated VPC, is delivered + run
host-native via SSM (NO Docker), self-terminates on the 5-min hard TTL, and a bounded
verdict-free run-outcome record crosses to the Hub. DoD (I confirm live in Forensic
360999005254): (1) one ephemeral EC2 from the 2.0 launch template into the isolated
VPC; (2) host-native SSM execution, no Docker; (3) the instance is torn down by the
5-min TTL — if still running past it, that is the finding, do NOT pass; (4) a bounded
verdict-free run-outcome record crosses the RD-013 gate to the Hub.
(NOTE: if the gate is closed by 2.2, TODAY's objective becomes finishing 2.2's live
validation instead — surface and confirm with me first.)

WORKING AGREEMENT
- Start with STEP 0, then WAIT for my go-ahead before changing anything.
- One story to completion: design -> build -> I confirm green -> you RECORD + flip
  status -> paired status commit (+ restore tag). Push to a branch; open a PR.
- MANAGEMENT ARTIFACTS ARE FIRST-CLASS (RD-015): brief + RUNBOOK + PROJECT_PLAN
  aligned; any new RD (RD-026) + candidate mappings recorded; all via PR; governance
  restorable with the code. Updating the docs is part of the work.
- Two-account live reality: artifact-touching compute (incl. the detonation host) is
  in Forensic; the durable record is in the Hub — I use two CloudShell tabs and run
  `aws sts get-caller-identity` before every operational block.
- At session end, author the NEXT story's brief + prompt (2.4 behavioral telemetry
  capture) with what ACTUALLY happened today. Zero cold-start.
- If blocked (incl. the register being non-empty), surface it and push partial
  progress + a draft PR; never silently fail.

First action: run STEP 0 (READ the 2.3 brief + METHODOLOGY + RUNBOOK + STORY_DETAIL,
reconcile true state) and report back with the one-line verdict. Then propose the
ordered plan for my approval.
```

---

> This prompt boots by READING the four governing docs (2.3 brief, METHODOLOGY,
> RUNBOOK, STORY_DETAIL) and reconciling main-vs-open-PR before any work — the
> anti-drift discipline this repo enforces. Its most important job is to catch that
> the advancement gate is likely CLOSED until Story 2.2 is live-validated.
