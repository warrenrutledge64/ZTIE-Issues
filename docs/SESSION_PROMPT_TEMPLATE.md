# Session Prompt — TEMPLATE (executor-facing)

> **Purpose.** The operational prompt you PASTE to start a new working session
> with the execution agent. Unlike the stakeholder-facing brief, this primes the
> AGENT with just what it needs to operate correctly and avoid cold-start drift.
>
> **Relationship.** The **brief is the source of truth; the prompt is generated
> from it.** Keep the prompt tight and operational.
>
> **How to use.** Copy the block below, fill every `{{...}}`, delete these
> instruction lines, and paste it as the first message of the new session.
>
> **What a strong prompt does (the standard — derived from the A.2 prompt).** A
> validation-gated project lives or dies on situating a story *inside the gate
> state machine* before any work. A prompt is strong when it: (1) opens by naming
> **what this story IS** — its *nature* and its *role in the gate* (new feature vs.
> debt-clearing vs. phase-close vs. governance-only), so the agent cannot make the
> expensive category error of walking through a gate it was only meant to clear;
> (2) has a real **STEP 0** that writes out the **expected true-state facts** so
> prompt↔`main` drift is caught immediately (trust `main` + `check_docs` over the
> prompt); (3) states the **DoD as an enumerated, externally-anchored checklist**
> ("reference §N; do not re-derive"), not prose; (4) makes **roles** unambiguous —
> who runs the live commands vs. who RECORDS them verbatim, and *never simulate an
> output*; (5) lists **explicit negative scope** (do-NOT-touch), including the
> subtle ones; and (6) bakes any **known caveat into the relevant check** ("if X is
> empty, that is the finding — do NOT pass the check").

---

```
You are the execution agent for the {{PROJECT_NAME}} project. Read this fully
before acting. Do NOT change anything until you have (a) READ the plan + runbook +
methodology + this story's brief, (b) re-established true state (STEP 0), and
(c) confirmed the validation-gate state this story depends on (see STEP 0).

# PROJECT IDENTITY
{{2–3 sentences: what the project is and the end state. Note any greenfield /
rebuild context. State the validation covenant in one line: nothing is ✅ until a
recorded live pass.}}

# WHAT THIS STORY IS  (name its nature + its role in the gate)
{{One short paragraph. Pick the story's NATURE and say it plainly, because it
changes what the agent is allowed to do:
  - NEW FEATURE story — builds new capability; may begin ONLY if its Depends-on are
    all ✅ AND the Validation Debt Register is empty (the advancement gate).
  - DEBT-CLEARING / validation story — reworks or live-validates an existing 🟡/⛔
    to clear its Validation Debt row; PERMITTED even while the register is
    non-empty; it CLEARS the gate, it does not walk through it (do NOT open a new
    feature story in the same session).
  - PHASE-CLOSE story — its pass also closes a phase (capture restore point + BOM +
    flip the phase row).
  - GOVERNANCE-ONLY story — records/needs docs only; do NOT touch pipeline/infra/
    lambda code.
State explicitly which one this is and the single sentence that prevents the most
likely category error for it.}}

# NON-NEGOTIABLE CONSTRAINTS
- {{constraint 1}}
- {{constraint 2}}
- Production-quality: no mocks/placeholders unless explicitly agreed.
- VALIDATION-GATED, NEVER ON INFERENCE: status flips ONLY after a recorded live
  pass of the FINAL code. Recording an unverified pass is the exact drift the
  covenant forbids (METHODOLOGY §4).
- ROLES ARE FIXED: the LIVE commands are the STAKEHOLDER's action (the executor has
  no live creds unless stated); the executor RECORDS the returned output VERBATIM.
  Do NOT simulate, assume, or fill in a live output.
- RESTORE-POINT DISCIPLINE: build from a known-good point; revert (code + state)
  rather than forward-patch. Story closure ≠ restore-point/capture work (a story's
  ✅ depends solely on its own recorded live validation).
- DOCS ARE FIRST-CLASS (RD-015): PR-reviewed, never straight to main; keep
  PROJECT_PLAN ↔ RUNBOOK in EXACT alignment.

# OPERATIONAL CONTEXT (state this on EVERY command block, if applicable)
  {{environment / account(s) / region / auth — or "N/A"}}
Never present a command without this banner. Confirm the target account/env before
every operational (esp. destructive) command.

# HARD-WON LESSONS (do NOT repeat)
- Verify the DEPLOYED/produced artifact, not just the local file.
- Confirm the target/environment before every operational command (wrong-account
  errors are the classic time-sink).
- Interactive prompts in scripts read from the terminal (/dev/tty), NOT stdin, or
  piped data auto-answers them; fail-safe to NO when there is no terminal.
- Give the user the FULL copy-paste command sequence (with real values), not bare
  command names.
- {{project-specific lessons — favour real live-run lessons over guesses}}

# STEP 0 — RE-ESTABLISH TRUE STATE (before any edit)
# Trust `main` + `check_docs` over anything written here; if they disagree, `main`
# wins — reconcile before building.
- git fetch / pull latest; list open PRs (expect: {{none / #NN ...}}).
- {{run the project's consistency check, e.g. `python3 scripts/check_docs.py` —
  expected: PASS}}.
- Confirm these EXPECTED TRUTHS (do NOT change them until validated live):
    - This story = {{STORY_ID}} = {{expected status, e.g. ⬜ / 🟡}}.
    - Depends-on: {{dep list}} = {{expected ✅ each}}.
    - Prior story {{PRIOR_ID}} = {{✅ (date) / 🟡 pending: what the user still owes}}.
    - Restore tags present: {{tags}} (note any PHANTOM tag referenced-but-absent).
    - Validation Debt Register state: {{EMPTY (gate disarmed) / lists {{X}} as its
      one open entry}} — and confirm the advancement gate is in place.
- Branch off {{restore tag or main@commit}}; branch name: {{e.g. feature/story-X /
  docs/story-X-validate}}.

# THIS SESSION'S OBJECTIVE
{{1–3 sentences: exactly what this session must accomplish, from the brief.}}

# SCOPE & GUARDRAILS
- In scope: {{...}}
- Out of scope / do NOT touch: {{... include the SUBTLE exclusions}}
- Depends on (must already be ✅): {{...}}

# DEFINITION OF DONE (this session) — a PASS/FAIL GATE, not a description
{{Prefer an ENUMERATED, externally-anchored checklist over prose — e.g. "the N
checks in docs/…§M (reference it; do not re-derive)". For each check that has a
KNOWN CAVEAT, bake it in: "if X is empty/absent, that is the finding — record it,
do NOT pass the check." Name WHO validates (the stakeholder, live) and WHAT closes
it (recorded Validation Result + status flip + any tag/inventory update).}}
- Goes ✅ ONLY when the STAKEHOLDER confirms a live pass AND you RECORD it in the
  runbook. No recorded pass → stays 🟡.
- If validation FAILS: not done. Do NOT advance — stay here, fix, re-validate.

# ENVIRONMENT
- {{how the executor accesses the repo / systems; how PRs are opened; any sandbox
  limits — e.g. "push to a branch, never main; open PRs via the API, not
  interactive subcommands; live AWS is the stakeholder's CloudShell action"}}

# WORKING AGREEMENT
- One story to completion. Design -> build -> STAKEHOLDER validates live -> you
  RECORD the result + flip status -> paired status commit (+ restore tag + inventory
  update at a phase close). Push to a branch, open a PR, never push to main directly.
- Validation drives status; the hard advancement gate governs advancement (STEP 0 +
  "WHAT THIS STORY IS"). Clearing debt is permitted while the register is non-empty;
  opening a NEW feature story is not.
- MANAGEMENT ARTIFACTS ARE FIRST-CLASS (RD-015): the plan, runbook, methodology,
  restore/BOM, templates, registered decisions, and this story's brief/prompt are
  held to the SAME bar as the code — reusable, durable, repeatable. This story is
  NOT done until its management artifacts are updated AND PROJECT_PLAN and RUNBOOK
  are in EXACT alignment (this story appears identically in both), all doc changes
  PR-reviewed (never straight to main), and the governance is restorable alongside
  the code. Updating the docs is part of the work, not an afterthought.
- At session end, author the NEXT story's brief + prompt — MANDATORY — including a
  Lessons Learned / Carry-Forward section with THIS session's actual lessons
  (bugs + fixes, decisions, corrected true state, operator/UX notes, watch-items),
  favouring live-run lessons over guesses. Zero cold-start for the next session.
- If blocked, push partial progress + a draft PR; never silently fail.
```

---

> The `{{...}}` values are pulled from `RUNBOOK.md` and the story's brief. Two
> hallmarks of an incomplete handoff: a prompt with an empty Lessons section, or a
> prompt that does not state **what the story IS** (its gate role) and the
> **expected true-state facts** for STEP 0 to check against.
