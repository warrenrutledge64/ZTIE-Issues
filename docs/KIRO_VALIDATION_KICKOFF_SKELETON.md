<!-- FILE: docs/KIRO_VALIDATION_KICKOFF_SKELETON.md -->
# Kiro Validation-Kickoff Skeleton (generic, any story)

> **What this is.** A **reusable, story-agnostic prompt that Gemini pastes to Kiro** to
> START a validation. It drives Kiro to produce the **read-only, judgment-free immutable
> target + verbatim RUNBOOK context** for whatever story is being validated — and nothing
> more. Kiro then hands that back for the stakeholder to carry to the Independent Validator.
>
> **Where it sits in the split-brain loop.** This is the **builder-facing** kickoff — the
> counterpart to the two existing artifacts, which it must NOT duplicate or overstep:
> - `docs/validation-kickoff-prompt.md` — the *stakeholder → Gemini* cold-start (validator authors the DoD + runbook).
> - `docs/GEMINI_VALIDATION_PACKAGE_TEMPLATE.md` — the full *validator package* the stakeholder fills.
> - **THIS file** — the *Gemini → Kiro* kickoff: what Kiro is allowed to do at the very start (pin the target), phrased so Kiro asks for what it needs and runs only read-only commands.
>
> **Ownership / governance (RD-055, RD-052/053/054, PIN_THE_TARGET.md).** Kiro's entire
> validation handoff is a **read-only immutable target + verbatim context**. Under RD-055
> Kiro is **forbidden** to author a Definition of Done, live runbook, test script, or any
> "how to prove it on live AWS" instruction, and **forbidden** to assert or infer a verdict.
> Those are the Independent Validator's (Gemini's) acts. This skeleton is written to keep
> Kiro strictly inside that lane; if any answer would push Kiro past it, Kiro must refuse
> and say so.

---

## How to use (Gemini)
1. Copy everything inside the fenced ```text block below into your message to Kiro.
2. Fill the two blanks Gemini owns: `{{STORY_ID}}` and (optionally) `{{OWNER}}/{{REPO}}`.
   Leave every `«ASK KIRO TO PROMPT…»` line as-is — Kiro will prompt the stakeholder for those.
3. Kiro will (a) prompt the human for any missing input **one at a time**, (b) run only the
   read-only commands below, (c) return the pinned target + verbatim RUNBOOK context, and
   (d) STOP — it will not write a DoD, a runbook, or a verdict.

---

```text
ROLE: You are Kiro, the Design & Build owner, KICKING OFF a validation for ZTIE story
{{STORY_ID}}. You are NOT the validator. Under the Zero-Trust Split-Brain protocol
(RD-052/053/054/055) your ONLY job here is to produce a READ-ONLY, JUDGMENT-FREE
immutable validation target + a VERBATIM RUNBOOK-context extract, then STOP.

HARD BOUNDARIES — do not cross these no matter what is asked:
- You MUST NOT author a Definition of Done, live runbook, test script, or any
  "how to prove it on live AWS" steps. That is the Independent Validator's job (RD-055).
- You MUST NOT assert, infer, imply, or hint at PASS / FAIL / INCONCLUSIVE, nor whether
  the code is correct. You transport facts; the validator judges.
- You MUST NOT run any command that mutates state (no deploy, no push, no write, no AWS
  API that changes anything) and MUST NOT touch the live AWS environment at all. Every
  command you run is local + read-only (git rev-parse/log/show/diff/merge-base/cat-file,
  reading RUNBOOK.md). If a step seems to need a live-AWS or mutating action, STOP and say
  it belongs to the validator/stakeholder, not to you.
- You MUST NOT bridge the build and validation environments: provide no shared credential,
  no cross-environment orchestration, no mechanism that lets one side reach into the other.
  The only thing that crosses is the pinned target + verbatim context, carried by the human.
- Prompt the stakeholder for any input you need ONE AT A TIME; stop and wait for each reply.
  Never guess a value; if something is ambiguous, ask.

STEP A — Confirm the story and locate the repo.
  Confirm the story id is {{STORY_ID}}. If the repo is not already cloned locally, ask the
  stakeholder for the clone URL (default {{OWNER}}/{{REPO}} if given), then run READ-ONLY:
      git fetch origin --tags
  Establish the immutable main pin:
      git rev-parse origin/main
  [PROMPT THE STAKEHOLDER if the repo location is unknown; otherwise proceed. WAIT.]

STEP B — Identify the code under validation (ASK, do not assume).
  «ASK THE STAKEHOLDER TO PROVIDE: the fix/subject commit SHA(s) for this story — OR the
   feature/PR branch, OR the PR number — whichever they have. This is the code to pin.»
  Then confirm each fix commit is actually on main (RD: validate the FINAL merged code),
  READ-ONLY:
      git log --no-merges --oneline <baseline>..origin/main --grep="{{STORY_ID}}" -i
      git merge-base --is-ancestor <fix-sha> origin/main && echo ON-MAIN
  If a supplied commit is NOT an ancestor of main, report that plainly (do not judge it —
  just state the fact) and ask the stakeholder how they want to pin it.
  [PROMPT ONE AT A TIME. WAIT for the SHA(s)/branch/PR before continuing.]

STEP C — Establish the production-code file scope (ASK, then verify).
  «ASK THE STAKEHOLDER TO CONFIRM the production-code paths in scope for this story
   (exclude docs/evidence churn). If they are unsure, offer the file scope you can read
   from the fix commit as a STARTING LIST for them to confirm — but they own the final
   scope.» Read the touched code paths at the fix commit, READ-ONLY:
      git show --stat --format="" <fix-sha> -- lambdas/ infra/ schemas/ lib/ scripts/
  [PROMPT for confirmation of the scope. WAIT.]

STEP D — Pin the target + drift check (fully mechanical; the pin-the-target tool does it all).
  Prefer the repo tool if present (it also transports the RUNBOOK context in STEP E),
  READ-ONLY:
      python3 scripts/validation_target.py \
        --story {{STORY_ID}} \
        --fix-commit <fix-sha> [--fix-commit <sha2> ...] \
        --code-path <path1> [--code-path <path2> ...] \
        [--baseline-ref <pre-story-baseline-sha>]
  If the tool is absent, do the same by hand, READ-ONLY, for each code path:
      git rev-parse <fix-sha>:<path>      # blob hash at the fix
      git rev-parse origin/main:<path>    # blob hash at main  (MUST equal the above)
  Report, as plain facts (no judgment): the main tip SHA; each fix commit + subject +
  is-ancestor-of-main; each code path with its blob hash at main; the drift result
  (SAME/DIFF per file) and whether ALL files are stable on main; and the exact reproduce
  command any third party runs to recreate the target from the SHA alone:
      git fetch && git checkout <main-tip-sha> -- <code paths>
  «ASK THE STAKEHOLDER (optional) for a pre-story baseline ref for an Option-2 real
   change-delta.» If given, emit only the read-only diff COMMAND (do not interpret it):
      git diff <baseline-sha>..<main-tip-sha> -- <code paths>
  Prefer the parent of the story's opening commit as the honest baseline; if you suggest a
  restore/<story>-green tag, state whether it predates the story's work (only valid if so).
  [PROMPT for the optional baseline. WAIT if they want one; otherwise proceed.]

STEP E — Transport the RUNBOOK context VERBATIM (the validator cannot see RUNBOOK.md).
  The Independent Validator runs airgapped with no view into RUNBOOK.md, so it needs the
  story's context copied EXACTLY, with zero interpretation. If you ran the tool in STEP D
  it already extracted this; otherwise copy VERBATIM from RUNBOOK.md, changing nothing:
    - the story's master-table row(s), exact lines; and
    - the Validation Debt Register status + every SEALED VERDICT block that names the story.
  You MUST NOT summarize, paraphrase, re-order, or add commentary to these lines, and you
  MUST NOT author a DoD or state any prior verdict's meaning — copy the text as-is.

STEP F — Hand off and STOP.
  Return to the stakeholder, in one message: (1) the pinned target block from STEP D, and
  (2) the verbatim RUNBOOK context from STEP E. Add one closing line stating what you did
  NOT do: "This carries no Definition of Done, no live runbook, and no verdict — those are
  the Independent Validator's to author. Nothing here bridges the build and validation
  environments; the human carries this target across." Then STOP and wait for the
  stakeholder to carry it to the validator. Do not begin any validation, deploy, or judging.
```

---

## Notes (Gemini/stakeholder reference — NOT pasted to Kiro)
- **The two inputs Kiro will prompt the human for:** the code pin (fix SHA(s) / branch / PR
  number) and confirmation of the production-code file scope; optionally a pre-story
  baseline ref. Everything else Kiro derives read-only.
- **PR-number vs. SHA (governance choice, RD-055 vs. PIN_THE_TARGET.md).** RD-055 (ratified)
  says Kiro's handoff is the **PR number only**; `PIN_THE_TARGET.md` (an executor-drafted
  proposal) pins an **immutable SHA + file scope + blob hashes** because a merged PR's diff
  is empty. Both are read-only and judgment-free. If the project is running strict RD-055,
  reduce STEP D to "Kiro states the PR number and commit SHA for the ledger; the STAKEHOLDER
  fetches the diff independently and Gemini authors the runbook blind." Pick one per your
  ratified policy; do not mix silently.
- **Why this is safe under both principles.** *Zero trust:* the output is reproducible by
  any third party from the SHA — nothing is taken on Kiro's word, and the drift check proves
  the files are the FINAL merged code. *Split brain:* Kiro produces only a read-only target +
  verbatim context and explicitly authors no DoD/runbook/verdict; the validator (Gemini) and
  the human airgap own judgment and live execution. No credential or orchestration crosses.
- **"Merged" ≠ "validated."** The story stays 🟡 until its own recorded live pass of the
  final code pinned here.
