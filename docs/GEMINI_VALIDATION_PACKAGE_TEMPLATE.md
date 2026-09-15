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
> 5. **A sealed verdict block** — after I paste you the raw output, return a clearly
>    delimited verdict: `VERDICT: PASS | FAIL | INCONCLUSIVE`, the DoD items each
>    marked pass/fail with the literal evidence line, and any human-sign-off still
>    outstanding. This block is what I carry back to Kiro; Kiro records it verbatim.
>
> **Security-boundary hard rules (RD-053 — apply when this story governs a security
> control: secret detection/redaction, the RD-013 crossing, auth/signing, destroy/handoff):**
> - **Positive-exercise:** the DoD MUST require the boundary to be positively tripped
>   live (e.g. a planted, non-allowlisted secret yields `gitleaks count ≥ 1`). If the
>   tool reports `count: 0` / a negative / allowlisted / empty result on the planted
>   payload, the verdict is **INCONCLUSIVE, never PASS** — do not accept "the container
>   didn't crash" as proof the control works. Offline tests support but never substitute.
> - **Redaction:** require me (the human) to read the **raw JSON record** and confirm
>   the sensitive value was excised while the finding persists. Do NOT accept a
>   `REDACTED-OK` summary tag as the evidence.
>
> Ask me for any value you need rather than guessing.

---

## Part C — How the loop runs (roles — the RD-053 4-stage loop)

1. **Handoff (Kiro → you).** Kiro hands you objective pointers only (SHA, PR #, stack
   names) and **exits the validation loop.**
2. **Design (you → Gemini).** **You** pull the diff (Part A) and state the requirement
   in your own words → paste both into Gemini (Part B). **Gemini authors the DoD +
   steps.** (Gemini can't reach the repo/AWS, so you are the courier — never let Kiro
   curate what Gemini sees; if it did, the pass is provisional.)
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
  review is still required (Part B item 4).
- **Avoid the two-AI handshake.** "Builder built it, validator approved it" is not a
  pass — your reading of the raw output is.
