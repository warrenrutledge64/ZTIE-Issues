# Gemini Independent-Validation Package — Story 2.6R (OD-008 SFN false-green fix, RD-060)

> **Scope of this pre-fill (READ FIRST).** Per **RD-055** the executor (Kiro) may supply
> the **PR number and objective lookups ONLY**. This file has therefore pre-filled the
> neutral, non-judgment slots (owner/repo, PR #, pin SHA, accounts, stack/deploy facts,
> submit/verify facts) **plus Kiro's offline-proof attestation**, and has deliberately
> **LEFT BLANK** the two things RD-055 + the validation covenant reserve for you and Gemini:
>
> 1. the **`<<< REQUIREMENT >>>` anchor** — you must write it in your own words (a starter
>    phrasing is provided *outside* the block for reference; do not paste Kiro's wording into
>    the block);
> 2. the **diff / full-source content and the changed-file list `{{FULL_SOURCE_PATHS}}`** —
>    RD-055 forbids Kiro from naming the changed files or fetching the diff; you derive the
>    file list yourself from the PR's `/files` endpoint (the STEP 1.5 loop shows how).
>
> Gemini authors the DoD + runbook + live steps from scratch, blind. Kiro records the
> sealed verdict verbatim only on an explicit PASS.

---

## Objective pointers (Kiro-supplied lookups — safe under RD-055)

| Field | Value |
|-------|-------|
| Subject | **Story 2.6R** — fix OD-008 (SFN false-green): the dynamic fork must not report `SUCCEEDED` over a failed host launch (RD-060) |
| Owner / Repo | `warrenrutledge64` / `ZTIE-Issues` |
| **PR number (the ONLY handoff)** | **`#216`** — its diff *is* the 2.6R change in isolation (cleanest for a blind review) |
| Pin / commit under test | fix commit `7436b82`; live on `main` (tip `e19ffab`) via reconciliation PR `#220` |
| Where to deploy from | `main` (or the `feature/od-008-sfn-launch-failure` branch tip) — the fix is already merged to `main`; there is no separate 2.6R branch to check out |
| Accounts | Forensic **360999005254** (intake + Step Functions orchestration + ephemeral detonation host); Hub **641628980935** (DynamoDB tracking table — the collected record lands here) |
| Region | `us-east-1` |
| Stack under test | `ZtieOrchestrationStack` → the `InspectionOrchestration` STANDARD state machine |

## Deploy-order facts (objective — for the FACTS SHEET / a deploy-gap check; NOT a runbook)
- Standing ZTIE deploy order: `ZtieHubTrackingStack` (Hub) → `ZtieIntakeStack` (Forensic) → `ZtieForensicInfraStack` (Forensic) → `ZtieStaticScanStack` (Forensic) → `ZtieDetonationStack` (Forensic) → **`ZtieOrchestrationStack` (Forensic)**.
- 2.6R changed **only** `ZtieOrchestrationStack` (state-machine definition) + a collector-side regression test. Redeploying that stack ships the fix; the lane Lambdas are unchanged by 2.6R. *(Gemini decides what the runbook actually requires — this is a lookup, not a step.)*
- Intake submission is IAM/SigV4 to the Forensic intake API; the collected record is read from the Hub DynamoDB tracking table. Two CloudShell tabs (Forensic submit / Hub verify), `aws sts get-caller-identity` before each block. *(Exact commands are Gemini's to author.)*

## Kiro offline-proof attestation (final code on `main`, tip `e19ffab`)
- Collector regression suite **OK (16 tests)**, including `TestOD008LaunchFailure` (launch_error/delivery_error markers → dynamic lane recorded `errored`, static preserved, `both_complete` False, no verdict keys; demonstrated teeth — WITHOUT the marker the collector records a false `completed`).
- `env -u NODE_OPTIONS npx tsc --noEmit` — **no new error type** (orchestration stack error profile byte-identical to the missing-`aws-cdk-lib` baseline).
- `prettier --check infra/lib/ztie-orchestration-stack.ts` — **clean**.
- **Not offline-provable:** the SFN execution status flip (FAILED vs the former false SUCCEEDED) is a Step Functions *runtime* behavior — only a live execution can confirm it. **Hence this live gate.**

---

## STARTER requirement phrasing (reference ONLY — reword in your OWN voice; do NOT paste Kiro's words into the block)

> *2.6R fixes OD-008: the Step Functions dynamic fork used to report SUCCEEDED even when the
> ephemeral detonation host failed to launch (or the host-native command was never delivered).
> Prove that when a host-launch failure is forced, the SFN execution now ends FAILED — while
> the collected record still crosses to the Hub with the dynamic lane recorded as `errored`
> and the static lane preserved. Must-not: a legitimate detonation result (`execution_error` /
> `timed_out` — the artifact actually ran) must NOT be turned into a launch failure.*

Rewrite that above into the `<<< REQUIREMENT >>>` slot below in your own words before pasting the block.

---

## Part 0 — KICKOFF BLOCK (fill the two blanks, then paste EVERYTHING between the fences into a fresh Gemini chat)

> Blanks left for you (RD-055): the `<<< REQUIREMENT >>>` line (your words) and
> `{{FULL_SOURCE_PATHS}}` (the changed files — you list them from the PR `/files` output;
> Kiro is barred from naming them).

```
You are the INDEPENDENT VALIDATOR (RD-052/053/054) for the ZTIE project — subject:
Story 2.6R (OD-008 SFN false-green fix, RD-060). The build agent (Kiro) wrote this code;
you did NOT. Author your OWN Definition of Done and a numbered, soup-to-nuts live runbook,
and try to BREAK the change — do not confirm the happy path. I (the stakeholder) run
everything on live AWS and read the raw output; you never touch the live system, only what
I paste you. Kiro is a write-only scribe at the end; it authored none of your rubric.

ZERO-TRUST ON THE COMMANDS THEMSELVES. Every command I give you below (and every command
in the runbook you author) was written by the BUILDER or me — do NOT trust that it collects
ENOUGH. Before you rely on any command set, ANALYZE IT FOR EFFICACY: could a real defect
hide in what it does not capture (an SFN execution read that only checks top-level status
and misses the collected record; a query that reads one field; a grep that misses a lane
state)? Then PROPOSE ADDITIONAL COMMANDS for more robust data collection — wider/independent
captures (full SFN execution history, both branch results, the Hub tracking item), and
negative probes (a NORMAL run that must still read SUCCEEDED; a legitimate execution_error
that must NOT be treated as a launch failure). Treat the supplied commands as a floor, never
a ceiling.

STEP 1 — Tell me to fetch the raw code, then WAIT for me to paste it. The command I run in
AWS CloudShell (gh is not available there) is (the first line LOOKS like it hangs — it is
a SILENT prompt: nothing echoes as I paste the token; I paste it + press Enter):

    read -rsp "Paste GH token, then press Enter (nothing will show): " GH_TOKEN && export GH_TOKEN && echo
    echo "token length: ${#GH_TOKEN}"      # confirms it took — prints only a number, not the token
    curl -sSL -H "Authorization: Bearer $GH_TOKEN" -H "Accept: application/vnd.github.v3.diff" \
      https://api.github.com/repos/warrenrutledge64/ZTIE-Issues/pulls/216
    unset GH_TOKEN

STEP 1.5 — FULL CONTEXT FETCH (mandatory — a diff is NOT enough). A diff hides contextual
leaks and wrapper-execution flaws (the Story 2.4 strace defect lived in the unchanged
surrounding code). First list the files the PR modified, then fetch each FULL file pinned
to the commit SHA (again the first line is a SILENT token prompt — nothing echoes):

    read -rsp "Paste GH token, then press Enter (nothing will show): " GH_TOKEN && export GH_TOKEN && echo
    echo "token length: ${#GH_TOKEN}"
    # list modified files:
    curl -sSL -H "Authorization: Bearer $GH_TOKEN" -H "Accept: application/vnd.github+json" \
      "https://api.github.com/repos/warrenrutledge64/ZTIE-Issues/pulls/216/files" | grep '"filename"'
    SHA=7436b82          # the exact commit under test (pin every fetch to this)
    for f in {{FULL_SOURCE_PATHS}} ; do      # <-- I fill this from the /files output above
      echo "===== $f @ $SHA ====="
      curl -sSL -H "Authorization: Bearer $GH_TOKEN" -H "Accept: application/vnd.github.v3.raw" \
        "https://api.github.com/repos/warrenrutledge64/ZTIE-Issues/contents/$f?ref=$SHA"
      echo
    done
    unset GH_TOKEN

If, reviewing the diff, you find a file whose FULL context you need that I did not list,
NAME it and have me fetch it the same way before you write the DoD. Do not proceed to a
verdict on any file you have only seen as a diff.

(Review the ACTUAL diff AND the full raw files I paste — not my summary. Pin SHA: 7436b82.)

PLAIN REQUIREMENT (my own words — the one anchor neither AI authored):
<<< REQUIREMENT (your own words): what the change must actually DO, what "correct" means,
the must-nots / boundaries it must never cross, and the failure modes it must survive.
Replace this whole line. >>>

FACTS SHEET (objective — lookups, not a rubric):
- Accounts / IDs: Forensic 360999005254 (intake + Step Functions orchestration + ephemeral
  detonation host); Hub 641628980935 (DynamoDB tracking table — the collected record lands
  here). Region us-east-1.
- Stack under test: ZtieOrchestrationStack -> the "InspectionOrchestration" STANDARD state
  machine. 2.6R changed only this stack's state-machine definition + a collector-side test.
- Deploy order (deploy-gap): ZtieHubTrackingStack (Hub) -> ZtieIntakeStack (Forensic) ->
  ZtieForensicInfraStack -> ZtieStaticScanStack -> ZtieDetonationStack ->
  ZtieOrchestrationStack (Forensic). Redeploying ZtieOrchestrationStack ships the fix.
- How to submit a test input + where to read the result: submit an artifact to the Forensic
  intake API (IAM/SigV4); read the collected record + SFN execution status. (You author the
  exact commands; two CloudShell tabs, sts get-caller-identity per block.)
- Code under test: PR #216 (fix commit 7436b82), live on main (tip e19ffab) via PR #220.

DELIVER, IN THIS ORDER:
1. Adversarial review of the diff + full source vs. the requirement — every bypass, a false
   SUCCEEDED that survives, a legitimate detonation result wrongly failed, a dropped collected
   record; flag anything you cannot verify from the diff alone.
2. Your OWN Definition of Done (derived from the requirement, NOT copied from the builder),
   including the adversarial cases: a FORCED launch failure must read the execution FAILED
   AND the collected record must still have crossed (dynamic lane errored, static preserved);
   a NORMAL run must still read SUCCEEDED; a legitimate execution_error/timed_out must NOT be
   treated as a launch failure.
3. Soup-to-nuts runbook — number every step, the exact command, and exactly what LITERAL
   output proves pass vs fail (aws sts get-caller-identity per block; the deploy order + an
   env/definition-pin check; how to FORCE a host-launch failure; submit; read the SFN
   execution status AND the Hub collected record). For EACH data-collection step, first WEIGH
   the supplied command's efficacy and ADD any stronger/corroborating/negative command.
4. What only a HUMAN should sign off.
5. A sealed verdict block after I paste the raw output: VERDICT: PASS | FAIL | INCONCLUSIVE,
   each DoD item marked with its literal evidence line.
6. An evidence manifest — the exact RAW artifacts I must RETAIN (SFN execution history/ARN,
   the Hub tracking item JSON, the forced-failure setup) so the pass is auditable.
7. THE RUNBOOK AS A DOWNLOADABLE FILE (fixed format). Output your STEP-3 runbook as ONE
   self-contained fenced code block, first line
   `<!-- FILE: docs/session-briefs/story-2.6R-LIVE-RUNBOOK.md -->`, body following the
   standard structure (Ground rules / STEP 0 get-the-code / STEP 1..N / Definition of Done /
   Verdict recording).

Ask me for any value you need rather than guessing. Begin with STEP 1.
```

---

## On results
- **Sealed PASS + retained raw evidence** → Kiro appends `docs/validation-evidence/2.6R/attempt-<n>/`, flips 2.6R 🟡→✅ (paired commit), closes linked **OD-008** with a dated note, clears it from the Validation Debt Register, updates WORK_LOG.
- **FAIL / INCONCLUSIVE** → 2.6R stays 🟡; fix-then-validate-once. Kiro never re-judges or upgrades an INCONCLUSIVE.
