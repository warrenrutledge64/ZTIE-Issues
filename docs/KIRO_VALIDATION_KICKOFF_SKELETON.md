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
3. Kiro will (a) prompt the human **one at a time** — the initial ask is only "confirm the
   story ID + file scope, and is it merged?"; you are never asked to pick a PR/SHA — (b) run
   only the read-only commands below (incl. a read-only open-PR gate it blocks on but never
   resolves itself), (c) return the pinned target + verbatim RUNBOOK context, and (d) STOP —
   it will not write a DoD, a runbook, or a verdict, and will not merge/close any PR.

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
- You MUST NOT run any command that mutates state (no deploy, no push, no write, no merge,
  no PR close, no AWS API that changes anything) and MUST NOT touch the live AWS environment
  at all. Every command you run is READ-ONLY: local git (rev-parse/log/show/diff/merge-base/
  cat-file), reading RUNBOOK.md, and READ-ONLY GitHub queries (gh api GET on pulls/files to
  DETECT open PRs — never a merge/close/edit). If a step seems to need a live-AWS, mutating,
  or PR-merge/close action, STOP and say it belongs to the validator/stakeholder, not to you.
- You MUST NOT merge or close a pull request. Detecting and listing open in-scope PRs is
  allowed (read-only fact-reporting); RESOLVING them (merge/close) is the stakeholder's
  action and judgment, not yours.
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

STEP B — Determine the story's file scope + whether it is merged (FIRST PROMPT).
  Do NOT ask "which PR" — a story can span many PRs (code + docs + evidence + scaffolding),
  and only the human knows the story ID reliably. Derive the code from the STORY ID instead.
  (b1) Discover every code commit that names the story, READ-ONLY:
      git log --no-merges --oneline origin/main --grep="{{STORY_ID}}" -i \
        -- lambdas/ infra/ schemas/ lib/ scripts/
  (b2) Read the production-code file scope those commits touch, READ-ONLY, and present it as
       a STARTING LIST for the stakeholder to CONFIRM (they own the final scope; exclude
       docs/evidence churn):
      git show --stat --format="" <each-sha> -- lambdas/ infra/ schemas/ lib/ scripts/
  (b3) FIRST PROMPT to the stakeholder — two things, plainly:
       «CONFIRM the story ID is {{STORY_ID}} and CONFIRM the production-code file scope
        (this list). And tell me: is this story's work ALREADY MERGED to main, or is there
        still an OPEN PR/branch with unmerged work?»
  You are NOT asking them to pick a PR or a SHA — only to confirm the ID + scope and the
  merged/unmerged fact. Everything else you derive yourself.
  [PROMPT ONE AT A TIME. WAIT for the confirmation + merged/unmerged answer.]

STEP B.5 — GATE: no OPEN in-scope PR may remain before validation (detect + BLOCK only).
  A validation target must be a SINGLE source of truth. An open PR whose work belongs to
  this story means "the story's code" is ambiguous / still moving, so validation MUST NOT
  start until it is resolved. Detect every OPEN PR in scope, READ-ONLY:
      # (a) files-intersect test — an OPEN PR whose changed files touch the confirmed scope:
      gh api "repos/{{OWNER}}/{{REPO}}/pulls?state=open&per_page=100" --jq '.[].number' \
        | while read -r n; do \
            gh api "repos/{{OWNER}}/{{REPO}}/pulls/$n/files" --jq '.[].filename' \
              | grep -qE '<confirmed-scope-paths-as-regex>' && echo "IN-SCOPE OPEN PR #$n"; \
          done
      # (b) branch-name test — an OPEN PR whose head branch names the story id:
      gh api "repos/{{OWNER}}/{{REPO}}/pulls?state=open&per_page=100" \
        --jq '.[] | select(.head.ref|test("{{STORY_ID}}";"i")) | "IN-SCOPE OPEN PR #\(.number) (\(.head.ref))"'
  "In scope" = the UNION of (a) files-intersect AND (b) branch-name (most conservative —
  block on EITHER signal). If ANY in-scope OPEN PR is found:
    - LIST them (number + branch + title) as plain facts, and STOP.
    - Tell the stakeholder: "These OPEN in-scope PRs must be MERGED or CLOSED before I can
      pin a target. I cannot merge or close them (that is a state-mutating, judgment act) —
      please resolve them, then tell me to re-scan." Do NOT merge, close, or advise which to
      keep — that is the stakeholder's decision + action.
    - When told to re-scan, run the two commands again; proceed ONLY when the in-scope OPEN
      set is EMPTY.
  If the story was reported UNMERGED in STEP B, the story's own feature PR is expected here —
  it too must be merged (or the run explicitly re-scoped to validate branch code) before you
  pin; state that plainly and let the stakeholder decide. Never proceed with a non-empty
  in-scope OPEN set.
  [DETECT + LIST + BLOCK. WAIT for the stakeholder to resolve, then re-scan.]

STEP C — Identify the LIVE code for the story (drift-derived, not human-picked).
  With the in-scope OPEN set empty, main IS the story's code. For EACH story code commit
  from STEP B, drift-check every confirmed-scope file's blob against main, READ-ONLY:
      git rev-parse <sha>:<path>          # blob at that commit
      git rev-parse origin/main:<path>    # blob at main
  The EFFECTIVE fix commit(s) are those whose in-scope blobs EQUAL main; earlier commits
  whose blobs DIFFER from main were superseded (report them as ancestors, do not pin them).
  This is how you resolve a multi-PR story mechanically — main + the drift check name the
  live code; the human never guesses which PR/SHA is current.
  [No prompt needed — derived. Report the effective fix commit(s) as facts.]

STEP D — Pin the target + drift check (fully mechanical; the pin-the-target tool does it all).
  Prefer the repo tool if present (it also transports the RUNBOOK context in STEP E),
  READ-ONLY (pass the EFFECTIVE fix commit(s) from STEP C + the CONFIRMED scope from STEP B):
      python3 scripts/validation_target.py \
        --story {{STORY_ID}} \
        --fix-commit <effective-fix-sha> [--fix-commit <sha2> ...] \
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
  NOT do: "This carries no Definition of Done, no live runbook, and no verdict, and I merged
  or closed no PRs — those are the Independent Validator's / stakeholder's to own. Nothing
  here bridges the build and validation environments; the human carries this target across."
  Then STOP and wait for the
  stakeholder to carry it to the validator. Do not begin any validation, deploy, or judging.
```

---

## Notes (Gemini/stakeholder reference — NOT pasted to Kiro)
- **What Kiro prompts the human for (initially, ONE thing):** at STEP B, confirm the
  **story ID + the production-code file scope** (Kiro shows a derived starting list) and say
  whether the story is **already merged to main or still has open work**. That is the whole
  initial ask — you are NEVER asked to pick which PR/SHA is "the right one." A later optional
  prompt (STEP D) offers a pre-story baseline for an Option-2 change-delta. Everything else
  Kiro derives read-only.
- **Multi-PR stories are resolved mechanically, not by you.** A story often spans many PRs
  (code + docs + evidence + scaffolding). Kiro discovers every code commit that names the
  story (STEP B), then DRIFT-CHECKS each against main (STEP C): only the commit whose in-scope
  blobs EQUAL main is the live code; superseded attempts are reported as ancestors, never
  pinned. `main` + the drift check name the current code — no human guess.
- **Open-PR gate (STEP B.5).** Validation cannot start while any OPEN PR is in scope
  (scope = the UNION of files-intersect-the-confirmed-scope OR head-branch-names-the-story).
  Kiro DETECTS + LISTS + BLOCKS (read-only `gh api` GET); the STAKEHOLDER merges or closes
  them; Kiro re-scans and proceeds only when the in-scope open set is EMPTY. Kiro never
  merges/closes/advises-which-to-keep (a state-mutating judgment act).
- **Governance status (RD-056, proposed — amends RD-055).** This skeleton operationalizes
  **RD-056** (PROJECT_PLAN, `proposed` pending ratification): a story-ID-driven, `main`-anchored
  drift-pinned target + the open-PR gate, which amends RD-055's ratified "PR number only"
  handoff. RD-055 stays ratified and its independence guarantees are UNCHANGED (the builder
  still authors no DoD/runbook/verdict; the validator works blind; the human carries the
  target). RD-056 only changes WHAT the builder pins (a `main`-anchored, drift-proven target
  derived from the story id) and adds the open-PR gate — strictly more zero-trust and more
  repeatable, at no cost to independence (see `docs/PIN_THE_TARGET.md`). Until RD-056 is
  ratified, if you prefer strict RD-055 instead, reduce STEP C/D to "Kiro states the PR
  number + commit SHA for the ledger; the STAKEHOLDER fetches the diff independently and
  Gemini authors the runbook blind." Pick one per your ratified policy; do not mix silently.
- **Why this is safe under both principles.** *Zero trust:* the output is reproducible by
  any third party from the SHA — nothing is taken on Kiro's word, and the drift check proves
  the files are the FINAL merged code. *Split brain:* Kiro produces only a read-only target +
  verbatim context and explicitly authors no DoD/runbook/verdict; the validator (Gemini) and
  the human airgap own judgment and live execution. No credential or orchestration crosses.
- **"Merged" ≠ "validated."** The story stays 🟡 until its own recorded live pass of the
  final code pinned here.
