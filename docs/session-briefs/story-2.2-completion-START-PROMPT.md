# Session Start Prompt — Complete Story 2.2 (warm handoff)

> Paste the block below as the FIRST message of the next working session. It warmly
> hands over the OVERALL picture, names THIS story's role, boots by reading the
> governing docs + reconciling true state, and then drives the next story — Story
> 2.2's live validation — **to completion**. Completing 2.2 is what unblocks 2.3.

---

```
ZTIE-Issues — Session Start: COMPLETE Story 2.2 (static-lane compliance mapping + signature scans)
You are Kiro, my AWS-native AI developer. Read this fully before acting. Do NOT
change anything until you have (a) READ the governing docs below, (b) re-established
true state (STEP 0), and (c) I have approved the plan.

THE OVERALL PICTURE (where we are)
ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted
artifact BEFORE it reaches the PDE. Work is validation-gated: nothing is ✅ until a
recorded live pass (the covenant). Three accounts: Pipeline-Hub (641628980935) =
brains/durable record; Forensic (360999005254) = self-contained blast zone
(ephemeral only); Pipeline-Sandbox (586917955591) = ZTIE→PDE handoff.
  - Phase 1 ✅ (intake + routing). Phase 2 (parallel inspection) is mid-flight:
    2.0 ✅ (Forensic isolated-VPC infra foundation), 2.1 ✅ (static scanning lane),
    2.2 🟡 (built + merged, NOT yet live-validated), 2.3 ⬜ (detonation, gated).
  - The build sandbox is INTEGRATIONS_ONLY: NO AWS creds → you BUILD + hand off, I
    RUN live in CloudShell and confirm green. GitHub git+gh work; `gh pr create` is
    broken (open PRs via `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`).

THIS STORY'S ROLE (why 2.2 is the thing to finish, not 2.3)
Story 2.2 extends the static lane (2.1) with two enrichments of the SAME evidence
stream: (1) it maps each finding to the NIST 800-53 / ISO 27001 control(s) it
IMPLICATES, and (2) it runs a signature engine for known-bad patterns / secrets /
IoCs — both NON-EXECUTING, both EVIDENCE never a verdict. Its code is built, tested
green offline, and already MERGED to main (PR #48) — but it has NOT had its recorded
live pass, so it sits as the SINGLE open entry in the Validation Debt Register. That
means the advancement gate is CLOSED: 2.3 (a new feature story) may NOT start until
2.2 is validated. So the next story to take TO COMPLETION is 2.2 itself — finishing
its live validation empties the register and unblocks 2.3. This session's job is to
COMPLETE 2.2, not to open 2.3.

STEP 0 — READ THE GOVERNING DOCS, THEN RE-ESTABLISH TRUE STATE (no inference).
Report back before proposing any change:
1. READ the brief `docs/session-briefs/story-2.2-brief.md` (esp. As-built + the DoD)
   and METHODOLOGY.md (the covenant + §4 hard rules: validate-the-final-code-once, a
   🟡 stays 🟡 through rework, no status flip on inference).
2. READ RUNBOOK.md — confirm the Validation Debt Register still lists 2.2 as its one
   open entry, 2.2's row is 🟡, and the G-3 advancement gate is in place. RUNBOOK is
   the source of truth for status.
3. READ the story detail `docs/STORY_DETAIL.md#story-2-2` (what "done" requires) and
   confirm 2.0 ✅ + 2.1 ✅.
4. Reconcile git truth: current branch; open PRs (expect #48 + #47 MERGED — verify);
   `python3 scripts/check_docs.py` (expect PASS); restore tags present
   (`restore/phase-1-green`, `restore/story-2.0-green`, `restore/story-2.1-green`) —
   FLAG that `restore/phase-2-floor-green` is a PHANTOM tag (referenced in
   BOM/RUNBOOK, absent from `git tag -l`); do NOT silently create it.
   One-line verdict: "2.2 = 🟡; register lists 2.2; gate CLOSED; today = validate 2.2."

THIS SESSION'S OBJECTIVE — take Story 2.2 TO COMPLETION
Get my recorded live pass of 2.2, then record it and flip 2.2 ✅ so the register
empties. The live validation is MY action in CloudShell (two tabs: Forensic to
submit + read the findings doc; Hub to read the tracking record); you give me the
exact copy-paste sequence, then RECORD what I return — never simulate an output.
  Deploy prerequisites (Forensic, needs a Docker build box for the container image):
   - Rebuild + `cdk deploy` the static-scan image (it now bundles compliance.py +
     signatures.py); its stack env already sets SUMMARY_CONTRACT_VERSION=1.1.
   - Redeploy the Hub validator so it accepts summary contract v1.1 (its code default
     is 1.1; confirm). On ANY Hub redeploy, pass ALL THREE senders
     (forensicIntakeRoleArn + forensicPreprocessorRoleArn + forensicStaticScanRoleArn)
     or the queue policy drops senders (the 2.1 lesson).
  DoD (I confirm live in Forensic 360999005254 + Hub 641628980935):
   (a) a known-bad IaC/script yields a finding MAPPED to the correct NIST/ISO control
       in the Forensic findings document AND reflected in the Hub summary compliance
       roll-up; (b) a PLANTED known signature (e.g. a secret) is detected as a
       normalized finding (secret redacted); (c) no artifact is executed; (d) the
       lane does not crash on a scanner error.
  ON PASS (and only then): write the dated Validation Result in RUNBOOK 2.2, flip the
   2.2 row 🟡 → ✅ (paired status commit), REMOVE the 2.2 row from the Validation Debt
   Register (it should then be empty), keep PROJECT_PLAN ↔ RUNBOOK aligned; open a PR.
   Any fixes discovered during the live run land as NEW commits (2.2 merged early, so
   reconcile them onto main).
  ON FAIL: 2.2 stays 🟡; fix + re-validate; do NOT advance.

NON-NEGOTIABLE CONSTRAINTS
- GREEN-RUN ACCEPTANCE: nothing flips ✅ on inference — I validate live, you RECORD.
- Do NOT open 2.3 or any new feature story this session — the gate is closed until
  2.2 clears. Completing 2.2 is exactly what the gate permits.
- Never push to main; push to a branch (e.g. `docs/story-2.2-validate` for the status
  flip, or `feature/story-2.2-fixes` if live fixes are needed) and open PRs via
  `gh api`. Merging is my action.
- Two-account reality: submit from a FORENSIC principal (a Hub principal gets 403 —
  the zero-trust gate); read the tracking table from a HUB shell (Forensic gives
  ResourceNotFoundException). Run `aws sts get-caller-identity` before every block.
- Python-first; AWS-native; production-quality; docs first-class (RD-015).

WORKING AGREEMENT
- Start with STEP 0, then WAIT for my go-ahead.
- One story to completion: I confirm green -> you RECORD + flip status (paired
  commit) -> register empties. Then, and only then, the NEXT story is 2.3 (its
  handoff is already written: story-2.3-brief.md / -PROMPT.md / -START-PROMPT.md).
- At session end: if 2.2 passed, confirm 2.3's handoff is still accurate (update its
  "2.2 = 🟡/✅" note) so 2.3 starts warm. Author/refresh the next handoff. Zero cold-start.
- If blocked, surface it and push partial progress + a draft PR; never silently fail.

First action: run STEP 0 (READ the 2.2 brief + METHODOLOGY + RUNBOOK + STORY_DETAIL,
reconcile true state) and report the one-line verdict. Then give me the exact
copy-paste CloudShell validation sequence for my go-ahead.
```

---

> This handoff deliberately points the next session at COMPLETING Story 2.2 (its
> live validation), because the advancement gate is closed until 2.2 clears —
> finishing 2.2 is what unblocks 2.3. When 2.2 passes and the register empties, use
> `story-2.3-START-PROMPT.md` for the following session.
