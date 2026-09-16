# Gemini Independent-Validation Package — Story {{STORY_ID}}

> **Purpose (RD-052 — split-brain independent validation).** The self-contained
> package the **stakeholder** fills in and pastes to the **validator brain (Gemini)**
> so Gemini can independently author the live-validation runbook + its own Definition
> of Done and step the stakeholder through validating a story **soup-to-nuts**.
>
> **Why it is built this way.** The build agent (Kiro) does **not** author this
> package's judgment inputs. The **stakeholder** pulls the raw diff from the repo and
> writes the requirement in their own words, so the validator is not just confirming
> the builder's framing (see METHODOLOGY §4a). Kiro may only supply objective
> *pointers* (PR number, file list, stack names) — never the rubric or the
> interpretation.
>
> **How to use.** The fastest path is **Part 0 — the cold-start KICKOFF BLOCK**: fill its
> blanks and paste the whole fenced block into a *fresh* Gemini chat; it carries the role,
> the requirement slot, the objective pointers, the STEP 1 + STEP 1.5 **fetch commands**,
> and the ordered deliverables — so Gemini can drive from zero. The operator sections are
> the same activity expanded: **Part A** = the fetch commands in detail (token safety, PR
> metadata), **Part A2** (add per-story) = the account-labeled operator command set for the
> live-run blocks, **Part C/D** = the loop + limits, **Part E** = the fixed runbook-output
> format. Fill every `{{...}}`; delete these instruction lines.
>
> **Every package carries a FLOW MAP (self-driving baton).** Immediately below this note,
> a **FLOW MAP** lists the ordered steps (STEP 0 paste Part 0 → STEP 1 fetch/paste → STEP 2
> Gemini DoD+runbook → STEP 3 run live → STEP 4 paste output/sealed verdict → STEP 5 Kiro
> records on PASS), and each part ends with a **▶ NEXT** baton naming the next step. This is
> what lets you resume in the **same chat or a new one** without losing the thread. The
> FLOW MAP also states the **audience boundary**: *Part 0 is the ONLY part pasted to Gemini;
> Parts A/A2/C/D/E are the operator's reference and Gemini never sees them.*
>
> **This is ALWAYS a validation.** Every RD-053 run — from a light doc check to a
> security-boundary detonation — uses this same package and the same 4-stage loop; only
> the **DEGREE** (how deep the DoD + evidence go) varies with what the story governs (see
> METHODOLOGY §4a/§4c). The KICKOFF BLOCK below is a **required, standard artifact of every
> validation** — never reconstructed ad hoc.
>
> **A DIFF IS NEVER ENOUGH (mandatory STEP 1.5).** Every kickoff block MUST include a
> **STEP 1.5 — FULL CONTEXT FETCH**: the exact `curl` commands that pull the FULL raw
> source (`Accept: application/vnd.github.v3.raw`) of every script/parser/CloudFormation
> template the PR modified, **pinned to the commit SHA** (`?ref=<SHA>`). Diffs hide
> contextual leaks and wrapper-execution flaws (the Story 2.4 strace defect lived in the
> unchanged surrounding code); the validator may not sign off on boundary-crossing logic
> or execution telemetry from a diff alone. Fill `{{FULL_SOURCE_PATHS}}` with the modified
> script/parser/template paths.
>
> **COMMAND-COMPLETENESS (every "paste X" ships the command that PRODUCES X).** This
> package must be self-contained and copy-paste runnable with zero hunting. For EVERY
> artifact the block or the validator's DoD asks the operator to paste — the diff, the
> full source, the deploy + env-pin check, the test-input submission, the live result
> record, the raw trace slice, the retained evidence — provide the **exact command that
> generates it**, with real values substituted and **each command labeled with the account
> it runs in** (+ an `aws sts get-caller-identity` guard). Never a bare command name, never
> "run the appropriate query," never "the runbook will tell you." Part 0 carries the STEP 1
> / STEP 1.5 fetch commands and the per-story Part A2 carries the account-labeled operator
> command set; the operator should never reverse-engineer how to obtain a required artifact.
>
> **COMMANDS ARE A FLOOR, NOT A CEILING (zero-trust on the evidence-gathering itself).**
> Command-completeness makes the package *runnable*; this rule makes it *sufficient*. Every
> command in the package was written by the builder or the operator — so the kickoff block
> MUST instruct the validator to **analyze each supplied command set for efficacy** (does it
> actually surface the evidence needed to prove/break the requirement, or could a real
> defect hide in what it does NOT capture — a truncated trace, a `head -N` that clips the
> proof, a grep that misses a syscall/finding family, a query that reads a single field?)
> **and to PROPOSE ADDITIONAL commands for more robust data collection** — wider/independent
> captures, corroborating reads, and negative probes that would expose a fake or partial
> result. The validator treats the supplied commands as a starting floor it is expected to
> strengthen, never a trusted ceiling. This language is REQUIRED in the kickoff block
> (Part 0) and echoed in the operator command set (Part A2) and the runbook-format (Part E),
> because trusting the builder's own collection commands to be sufficient is the same
> "grading your own paper" failure the split-brain exists to close — one layer down, at the
> evidence layer (METHODOLOGY §4a).
>
> **KEEP PART 0 TIGHT — but self-contained through the fetch (anti-drift, balanced with
> command-completeness).** A bloated, everything-in-two-places kickoff block is a real
> drift hazard: the same fact written in the prompt AND an operator section means a later
> edit must be caught in both or they silently disagree — and the copy the validator reads
> (Part 0) diverges from the reference. But leanness must NOT override command-completeness:
> if Part 0 asks the operator to produce data, Part 0 must carry the command that produces
> it, or the operator is left hunting. So draw the line by KIND of content:
> - **IN Part 0 (it needs them to function):** the role, the `<<< REQUIREMENT >>>` anchor,
>   the objective pointers (PR #, merge SHA, accounts), the **STEP 1 + STEP 1.5 fetch
>   commands** (self-contained through the fetch), and the ordered deliverables. Part A2 is
>   the labeled *superset* for the later live-run blocks (deploy/submit/read/evidence) — it
>   restates STEP 1/1.5 by account label as a convenience, which is fine (the SHA/PR live as
>   a single variable, so this is low-drift).
> - **NOT in Part 0 — referenced instead (these are the drift-prone facts):** the full facts
>   sheet beyond the pointers, the builder's-claims list, and the fixed runbook-output
>   structure (**Part E**). The validator gets these through what the stakeholder *pastes
>   and answers* (the diff + full source at STEP 1/1.5, and any value it asks for), not by
>   copying paragraphs into the prompt body.
>
> Rule of thumb: **a command that STEP N runs belongs where STEP N is; a fact that can be
> edited later and drift belongs in exactly one section and is referenced.** Shorter is
> better only up to the point where the operator can still run the block without hunting.

---

## FLOW MAP — the self-driving baton (do these in order; each step names the NEXT)

> **Audience boundary:** **Part 0 is the ONLY thing the validator (Gemini) sees** (you
> paste it into a fresh chat). Parts A / A2 / C / D / E are **the operator's reference** —
> the validator does not see them and does not need to. Wherever you are (same chat or a
> new one), the "▶ NEXT" baton at the end of each part tells you the next step, so nothing
> stalls.

```
STEP 0  Paste Part 0 into a FRESH validator chat; fill the <<< requirement >>> in your words.
          Validator replies: "run the fetch commands and paste the output."   ▶ STEP 1
STEP 1  Run Part A2 BLOCK 1 (diffs) + BLOCK 2 (full source @ SHA). Paste output back.  ▶ STEP 2
STEP 2  Validator returns: adversarial review + its OWN DoD + a numbered live runbook.
          (The validator's runbook is authoritative; Part A2 is your backup reference.)  ▶ STEP 3
STEP 3  Run the live runbook (Part A2 has the same account-labeled commands): deploy →
          submit test input → read the live result → read the raw record.       ▶ STEP 4
STEP 4  Paste the live raw output back to the validator → SEALED VERDICT (PASS/FAIL/INCONCLUSIVE). ▶ STEP 5
STEP 5  On PASS: gather the retained evidence + your named attestation, hand the sealed
          verdict + evidence to KIRO → Kiro records + flips ✅.  On INCONCLUSIVE/FAIL:
          stays 🟡; fix + re-run from STEP 3.
```

---

## Part 0 — The cold-start KICKOFF BLOCK (paste this whole block into a fresh Gemini chat)

> **This is the hand-off.** Fill the blanks — `{{STORY_ID/SUBJECT}}`, the pointers, and the
> `<<< REQUIREMENT (your own words) >>>` block — then paste everything between the fence
> into a new Gemini chat. Do NOT let Kiro fill the requirement; that anchor must be yours.
> The block is **self-contained through the fetch** (it carries the STEP 1 + STEP 1.5 fetch
> commands), then Gemini authors the DoD + runbook and, after you paste the live output,
> returns a sealed verdict.
>
> **Tight, not starved (see the header note "KEEP PART 0 TIGHT").** Keep in the block: role
> + requirement anchor + objective pointers + the fetch commands + ordered deliverables.
> Keep OUT (reference instead): the full facts sheet beyond the pointers, the builder's
> claims, and the runbook-output structure (Part E) — those are the drift-prone facts, and
> duplicating them here is how the block drifts out of sync. But never drop a command STEP 1
> needs just to be shorter: if the block asks you to produce data, the block carries the
> command.

```
You are the INDEPENDENT VALIDATOR (RD-052/053/054) for the ZTIE project — subject:
{{STORY_ID/SUBJECT}}. The build agent (Kiro) wrote this code; you did NOT. Author your OWN
Definition of Done and a numbered, soup-to-nuts live runbook, and try to BREAK the change
— do not confirm the happy path. I (the stakeholder) run everything on live AWS and read
the raw output; you never touch the live system, only what I paste you. Kiro is a
write-only scribe at the end; it authored none of your rubric.

ZERO-TRUST ON THE COMMANDS THEMSELVES. Every command I give you below (and every command
in the runbook you author) was written by the BUILDER or me — do NOT trust that it collects
ENOUGH. Before you rely on any command set, ANALYZE IT FOR EFFICACY: does it actually
surface the evidence needed to prove/break the requirement, or could a real defect hide in
what it does not capture (a truncated trace, a grep that misses a family, a query that reads
one field, a head -N that clips the proof)? Then PROPOSE ADDITIONAL COMMANDS for more robust
data collection — wider/independent captures, corroborating reads, and negative probes that
would expose a fake or partial result. Treat the supplied commands as a floor, never a
ceiling; call out any command whose output could be gamed or is insufficient and give me the
stronger command to run instead or in addition.

STEP 1 — Tell me to fetch the raw code, then WAIT for me to paste it. The command I run in
AWS CloudShell (gh is not available there) is:

    read -rs GH_TOKEN && export GH_TOKEN
    curl -sSL -H "Authorization: Bearer $GH_TOKEN" -H "Accept: application/vnd.github.v3.diff" \
      https://api.github.com/repos/{{OWNER}}/{{REPO}}/pulls/{{PR_NUMBER}}
    unset GH_TOKEN

STEP 1.5 — FULL CONTEXT FETCH (mandatory — a diff is NOT enough). A diff hides
contextual leaks and wrapper-execution flaws (e.g. the Story 2.4 strace defect lived in
the surrounding execution wrapper, not the changed lines). You may NOT sign off on
boundary-crossing logic or execution telemetry from the diff alone. Have me fetch the
FULL raw source of every script / parser / CloudFormation template touched by the PR,
pinned to the exact commit SHA:

    read -rs GH_TOKEN && export GH_TOKEN
    SHA={{MERGE_COMMIT}}          # the exact commit under test (pin every fetch to this)
    for f in {{FULL_SOURCE_PATHS}} ; do      # every modified script/parser/template
      echo "===== $f @ $SHA ====="
      curl -sSL -H "Authorization: Bearer $GH_TOKEN" -H "Accept: application/vnd.github.v3.raw" \
        "https://api.github.com/repos/{{OWNER}}/{{REPO}}/contents/$f?ref=$SHA"
      echo
    done
    unset GH_TOKEN

If, reviewing the diff, you find a file whose FULL context you need that I did not list,
NAME it and have me fetch it the same way before you write the DoD. Do not proceed to a
verdict on any file you have only seen as a diff.

(Review the ACTUAL diff AND the full raw files I paste — not my summary. If the code spans
multiple PRs I will paste each. Merge commit / pin SHA: {{MERGE_COMMIT}}.)

PLAIN REQUIREMENT (my own words — the one anchor neither AI authored):
<<< REQUIREMENT (your own words): what the change must actually DO, what "correct" means,
the must-nots / boundaries it must never cross, and the failure modes it must survive.
Replace this whole line. >>>

FACTS SHEET (objective — I fill these; they are lookups, not a rubric):
- Accounts / IDs: {{ACCOUNTS}}
- Deploy order (deploy-gap): {{DEPLOY_ORDER}}
- How to submit a test input + where to read the result: {{SUBMIT_AND_VERIFY}}
- Code under test: {{PR_LIST}} (merge {{MERGE_COMMIT}}).

DELIVER, IN THIS ORDER:
1. Adversarial review of the diff vs. the requirement — every bypass, leak, crash, or
   forbidden crossing; flag anything you cannot verify from the diff alone.
2. Your OWN Definition of Done (derived from the requirement, NOT copied from the builder),
   including the adversarial cases. IF this subject governs a SECURITY BOUNDARY (secret
   detection/redaction, a data-crossing gate, auth/signing, destroy/handoff, behavioral
   capture): the DoD MUST require (a) a POSITIVE live exercise — the boundary actually
   fires on a planted trigger (e.g. a planted non-allowlisted secret yields count >= 1); a
   negative/allowlisted/empty result (e.g. count: 0 on the planted payload) is INCONCLUSIVE,
   never PASS — "the container didn't crash" is not proof the control works, and offline
   tests support but never substitute; (b) a human reads the RAW record (for redaction, the
   human reads the raw JSON to confirm the sensitive value was excised while the finding
   persists — never a REDACTED-OK summary tag); (c) RETAINED raw evidence in
   docs/validation-evidence/{{STORY_ID}}/ — your sealed PASS is necessary but NOT
   sufficient, the retained artifact is the proof.
3. Soup-to-nuts runbook — number every step, the exact command, and exactly what LITERAL
   output proves pass vs fail (aws sts get-caller-identity per block; the deploy order +
   an env-pin check; submit; read the live result AND, for a boundary, the raw record). For
   EACH data-collection step, first WEIGH the supplied command's efficacy (what could hide
   in what it does not capture) and ADD any stronger/corroborating/negative command needed —
   do not just reuse the commands I hand you.
4. What only a HUMAN should sign off (security boundaries / data-crossing gates) — two LLMs
   agreeing is not sufficient.
5. A sealed verdict block after I paste the raw output: VERDICT: PASS | FAIL | INCONCLUSIVE,
   each DoD item marked with its literal evidence line, any human sign-off outstanding.
6. An evidence manifest — the exact RAW artifacts I must RETAIN so the pass is auditable,
   not testimony.
7. THE RUNBOOK AS A DOWNLOADABLE FILE (fixed format). Output your STEP-3 runbook as ONE
   self-contained fenced code block I can copy straight into a file — no prose around it,
   nothing to reassemble. First line inside the block MUST be the filename comment
   `<!-- FILE: docs/session-briefs/story-{{STORY_ID}}-LIVE-RUNBOOK.md -->`, and the body
   MUST follow this EXACT structure (same headers every time):
     # Story {{STORY_ID}} — LIVE validation runbook (stakeholder, two CloudShells)
     > one-line purpose + "only YOU can run this; executor records verbatim; nothing on inference"
     ## Ground rules  (two accounts→two tabs; `aws sts get-caller-identity` before every block;
       one line at a time; /tmp wiped on recycle; region us-east-1, ambient creds)
     ## STEP 0 — Get the code  (git checkout + reset to the reviewed commit/branch)
     ## STEP 1..N — numbered live steps  (each: the ACCOUNT it runs in, the exact command,
       and the LITERAL output that proves pass vs fail)
     ## Definition of Done  (your DoD, each item with its pass/fail evidence line)
     ## Verdict recording  (what I hand to the executor; INCONCLUSIVE/FAIL → stays open)
   Give it to me AFTER the sealed verdict (or alongside the runbook at STEP 2 if I ask
   early). I save that block verbatim as the named file and upload it to the executor / push
   it to the Hub — so every runbook has the same shape and is a droppable artifact.

Ask me for any value you need rather than guessing. Begin with STEP 1.
```

---

## Part A — Pull the raw code yourself (stakeholder runs this; do NOT let the builder curate it)

> **AWS CloudShell note:** the `gh` CLI is NOT available in CloudShell. Pull the raw
> diff with `curl` against the GitHub REST API, token-authenticated. Export a PAT once
> (never paste the token into the validator or the chat), then run the curl:

```
export GH_TOKEN=<your_personal_access_token>

curl -sSL \
  -H "Authorization: Bearer $GH_TOKEN" \
  -H "Accept: application/vnd.github.v3.diff" \
  https://api.github.com/repos/{{OWNER}}/{{REPO}}/pulls/{{PR_NUMBER}} | tee /tmp/{{STORY_ID}}.diff
```

For the PR metadata (title / state / merge commit / files), use the JSON accept header:

```
curl -sSL -H "Authorization: Bearer $GH_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/{{OWNER}}/{{REPO}}/pulls/{{PR_NUMBER}}
```

Copy the **full** diff output — that raw diff is the code Gemini reviews. (If the code is
already merged, `git show <merge_commit>` in your cloned repo prints the same raw diff
without a token.)

> On a machine where `gh` IS available (not CloudShell), the equivalent is
> `gh pr diff {{PR_NUMBER}} --repo {{OWNER}}/{{REPO}}` — but do not assume it in CloudShell.

**FULL CONTEXT FETCH (mandatory — the diff alone is not enough).** A diff shows only
changed lines; **contextual leaks and wrapper-execution flaws hide in the unchanged
surrounding code** (the Story 2.4 strace defect was exactly this). So also pull the
**FULL raw source** of every **script, parser, or CloudFormation template** modified in
the PR, **pinned to the exact commit SHA**, and paste it to the validator alongside the
diff:

```
export GH_TOKEN=<your_personal_access_token>
SHA=<the exact commit SHA under test>       # pin EVERY fetch to this

# List the files the PR modified (paths), then fetch each FULL file at $SHA:
curl -sSL -H "Authorization: Bearer $GH_TOKEN" -H "Accept: application/vnd.github+json" \
  "https://api.github.com/repos/{{OWNER}}/{{REPO}}/pulls/{{PR_NUMBER}}/files" \
  | grep '"filename"'

# For EACH modified script / parser / template <PATH>:
curl -sSL -H "Authorization: Bearer $GH_TOKEN" -H "Accept: application/vnd.github.v3.raw" \
  "https://api.github.com/repos/{{OWNER}}/{{REPO}}/contents/<PATH>?ref=$SHA"
```

The `application/vnd.github.v3.raw` accept header returns the **entire file** (not a
patch), and `?ref=$SHA` pins it to the reviewed commit so the validator sees exactly the
deployed source. The validator must NOT sign off on boundary-crossing logic or execution
telemetry from a diff hunk alone.

---

## Part C — How the loop runs (roles — the RD-053 4-stage loop)

1. **Handoff (Kiro → you).** Kiro hands you objective pointers only (SHA, PR #, stack
   names) and **exits the validation loop.**
2. **Design (you → Gemini).** **You** paste the Part 0 block (with your requirement in the
   `<<< REQUIREMENT >>>` slot), run its STEP 1 + STEP 1.5 fetch commands, and paste the raw
   diff + full source back into Gemini. **Gemini authors the DoD + steps** (and critiques /
   extends the collection commands). (Gemini can't reach the repo/AWS, so you are the
   courier — never let Kiro curate what Gemini sees; if it did, the pass is provisional.)
3. **Execute & judge (you + Gemini).** You run the steps on the real system and paste
   the **raw output back to Gemini**, which **adjudicates PASS / FAIL / INCONCLUSIVE**
   and returns the sealed verdict block. You **read the raw record yourself** on any
   security boundary — Gemini adjudicates, it does not self-confirm.
4. **Close-out (you → Kiro).** **Only on an explicit PASS**, you carry the sealed
   verdict + raw evidence to **Kiro**, whose role is **purely administrative** — record
   it verbatim, flip status, clear the register, open the next gate. Kiro never
   re-judges or upgrades an INCONCLUSIVE (on a fail/incomplete the story stays 🟡).

---

## Part D — Straight talk (the limits — do not skip)

- **The requirement anchor is yours.** If you paste a requirement the builder wrote,
  its framing sneaks back in. Reword it in your own voice.
- **Real system + your eyes are the grader.** Gemini can't run the live system or see
  its output; it only writes the gate. The genuinely dangerous defects are usually
  live-only.
- **Two LLMs can share a blind spot.** For security-critical boundaries a **human**
  review is still required (Part 0 deliverable #4).
- **Distrust the commands, not just the code.** The commands the builder/operator supply
  are a floor. Gemini must judge whether each command set actually surfaces the evidence —
  or whether a defect could hide in what it does not capture — and add stronger /
  corroborating / negative commands. A pass built on a command that under-collects (a
  truncated trace, a one-field query, a grep that misses a family) is a pass on incomplete
  evidence; run the augmented commands, not just the given ones.
- **Avoid the two-AI handshake.** "Builder built it, validator approved it" is not a
  pass — your reading of the raw output is.
- **Trust the artifact, not the word — including the validator's (RD-054).** A sealed
  PASS from Gemini is necessary but not sufficient. For a security boundary, the ✅
  rests on RETAINED raw artifacts committed to `docs/validation-evidence/<story-id>/`
  (raw positive-exercise output + a re-runnable proof-of-absence + a named human
  attestation + `intake_id`/commit-SHA provenance) — captured at validation time,
  because Forensic is ephemeral. This makes the pass auditable, not bulletproof.


---

## Part E — Runbook output format (FIXED — every runbook comes out identical + downloadable)

> **Goal.** The validator's live runbook must always have the **same shape** and must be
> a **droppable file**: one self-contained block the stakeholder copies into a file and
> uploads to the executor (Kiro) or pushes to the Hub/repo — never prose to reassemble.
> (The validator can't write files; "downloadable" = one clean fenced block → save-as.)

**What the stakeholder asks the validator for (this is deliverable #7 in Part 0):**
output the runbook as **ONE fenced code block**, nothing outside it, whose **first line is
the filename marker** and whose body follows the fixed structure below.

**Fixed structure (headers identical every time):**
```
<!-- FILE: docs/session-briefs/story-{{STORY_ID}}-LIVE-RUNBOOK.md -->
# Story {{STORY_ID}} — LIVE validation runbook (stakeholder, two CloudShells)

> One-line purpose. Only YOU can run this (executor has no AWS creds). The executor
> records your returned output VERBATIM; nothing is recorded on inference.

## Ground rules
- TWO accounts → TWO CloudShell tabs (name them + IDs). A banner does NOT change the account.
- Run `aws sts get-caller-identity` BEFORE every block; if it's the wrong account, switch tabs.
- Feed commands ONE LINE AT A TIME. `/tmp` is wiped on recycle. Region us-east-1, ambient creds.

## STEP 0 — Get the code
   (git fetch + checkout + reset --hard to the reviewed branch/commit)

## STEP 1..N — the numbered live steps
   For EACH step: the ACCOUNT it runs in, the EXACT command, and the LITERAL output that
   proves PASS vs FAIL (command-completeness — no bare names, no "run the query"). For each
   collection step the validator has weighed the supplied command's efficacy and STRENGTHENED
   it — wider/corroborating/negative commands so the evidence can't be truncated, clipped, or
   gamed; the supplied blocks are a floor, not a ceiling.

## Definition of Done
   Each DoD item with the literal evidence line that satisfies it. For a security boundary:
   positive live exercise + human raw-record read + retained evidence (RD-053/054).

## Verdict recording
   What the stakeholder hands the executor on PASS (sealed verdict + evidence);
   INCONCLUSIVE/FAIL → story stays open, fix + re-run.
```

**Download / hand-off mechanics (stakeholder):**
1. Copy the validator's single fenced block.
2. Save it verbatim as `docs/session-briefs/story-{{STORY_ID}}-LIVE-RUNBOOK.md` (the
   `<!-- FILE: ... -->` marker names the path). In CloudShell:
   `cat > docs/session-briefs/story-{{STORY_ID}}-LIVE-RUNBOOK.md` then paste + Ctrl-D.
3. **Upload it to Kiro** (attach the file) **or push it to the Hub/repo** (`git add` +
   commit on the story's docs branch). Either way the executor has the exact runbook.
> This runbook is the validator's operator artifact; per RD-053 it does NOT replace the
> validator's independent authorship or the retained live evidence — it standardizes and
> makes portable the steps you actually run.
