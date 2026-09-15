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
> **How to use.** Fill every `{{...}}`, delete these instruction lines, run Part A,
> then paste Part B (with the pasted diff) to Gemini. Keep Part C/D as-is.

---

## Part A — Pull the raw code yourself (stakeholder runs this; do NOT let the builder curate it)

```
gh pr view {{PR_NUMBER}} --repo {{OWNER}}/{{REPO}} --json title,state,mergeCommit,files
```
```
gh pr diff {{PR_NUMBER}} --repo {{OWNER}}/{{REPO}}
```

Copy the **full** output of `gh pr diff` — that raw diff is the code Gemini reviews.

---

## Part B — Paste to Gemini (with the diff from Part A)

> **Role:** You are the INDEPENDENT validator for {{PROJECT}} Story {{STORY_ID}}. The
> build agent (Kiro) wrote this code; you did not. Step me (the stakeholder) through
> validating it on the real system **soup-to-nuts**, and try to **break** it — do not
> confirm the happy path. Derive your own pass/fail criteria from the plain
> requirement below; do not trust the builder's wording.
>
> **Plain requirement (the anchor — write this in YOUR OWN words; it is the one input
> neither AI authored):**
> {{REQUIREMENT_IN_YOUR_OWN_WORDS — what the story must do, and what "correct" means:
> the observable behavior, the must-nots / boundaries it must never cross, and the
> failure modes it must survive.}}
>
> **Builder's claims to VERIFY, not trust:**
> {{CLAIMS_TO_VERIFY — e.g. "a contract version was bumped and a dependent stack must
> be redeployed first", "X is fail-closed", "Y never crosses the boundary". List the
> load-bearing assertions the builder made so Gemini checks them against the diff.}}
>
> **Facts sheet (objective — accounts, stacks, endpoints, lookups):**
> {{FACTS_SHEET — target account(s) + IDs, region, which stacks deploy where, the
> exact resource/env values to check, how to submit a test input, how to read the
> result. These are lookups + IDs, not a rubric.}}
>
> **The code (raw diff from the stakeholder's Part A — NOT a builder-curated summary):**
> ```
> {{PASTE THE FULL `gh pr diff` OUTPUT HERE}}
> ```
>
> **Deliver, in this order:**
> 1. **Adversarial review** of the diff vs. the requirement — every way it could be
>    bypassed, leak/expose something, crash, or cross something forbidden; flag
>    anything you cannot verify from the diff alone.
> 2. **Your own Definition of Done** (derived from the requirement above, NOT copied
>    from the builder), including the adversarial cases (prove it *fails* when it
>    should, not just that it works).
> 3. **Soup-to-nuts runbook** — number every step I execute, the **exact command**,
>    and **exactly what output proves pass vs. fail**. Make the verdict visible in the
>    **literal command output** so I decide, not you. Cover: which account/tab, the
>    deploy order (verify any "redeploy X first" claim), submitting the test input,
>    confirming the intended behavior on the live system, and the fail-safe/error
>    behavior.
> 4. **What only a human should sign off** — name the parts (security boundaries,
>    data-crossing gates, anything zero-trust) where you + the builder agreeing is not
>    enough.
>
> Ask me for any value you need rather than guessing.

---

## Part C — How the loop runs (roles — keeps it honest)

1. **Stakeholder** pulls the diff (Part A) → pastes into Gemini (Part B).
2. **Gemini** returns its adversarial review + its own DoD + a numbered runbook.
3. **Stakeholder** runs the runbook on the real system and **reads the raw output**
   — the pass/fail is in the literal text, not the AI's narration.
4. **Stakeholder** reports the result to the **executor (Kiro)**, which records it
   verbatim and flips status per METHODOLOGY §4 (or fixes-then-revalidates on a fail).

---

## Part D — Straight talk (the limits — do not skip)

- **The requirement anchor is yours.** If you paste a requirement the builder wrote,
  its framing sneaks back in. Reword it in your own voice.
- **Real system + your eyes are the grader.** Gemini can't run the live system or see
  its output; it only writes the gate. The genuinely dangerous defects are usually
  live-only.
- **Two LLMs can share a blind spot.** For security-critical boundaries a **human**
  review is still required (Part B item 4).
- **Avoid the two-AI handshake.** "Builder built it, validator approved it" is not a
  pass — your reading of the raw output is.
