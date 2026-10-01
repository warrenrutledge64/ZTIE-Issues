<!-- FILE: docs/PHASE_GATE_VALIDATION_KICKOFF_SKELETON.md -->
# Kiro Phase-Gate Validation-Kickoff Skeleton (generic, any phase)

> **What this is.** A **reusable, phase-agnostic prompt that Gemini pastes to Kiro** to
> START an **end-of-phase gate** validation. It is the phase-level sibling of the
> per-story [`docs/KIRO_VALIDATION_KICKOFF_SKELETON.md`](KIRO_VALIDATION_KICKOFF_SKELETON.md):
> it drives Kiro to produce a **read-only, judgment-free pinned PHASE target + verbatim
> RUNBOOK context** (the phase's gate statement + its story set + each story's recorded
> Validation Result), then **stop** — and nothing more. Kiro hands that back for the
> stakeholder to carry to the Independent Validator (Gemini), who authors the end-of-phase
> Definition of Done + the live integration runbook **blind**.
>
> **Why a phase gate needs its own handoff (not the story one).** A story validation is
> anchored to a *diff / PR* and proves one slice. A **phase gate** proves the **integration
> of the whole phase** against the phase's **gate statement** — the end-to-end behaviour the
> phase promised — anchored at a **fixed `restore/phase-N-green` tag**, not a diff. There is
> no "which PR" ambiguity (the tag is frozen), so this kickoff is deliberately **simpler and
> TAG-ANCHORED**: it does NOT clone the story kickoff's RD-056 open-PR gate / CURRENT-vs-
> HISTORICAL machinery. A phase gate is always a re-proof of the integrated system **at the
> captured phase tag**.
>
> **Where it sits in the split-brain loop.** This is the **builder-facing** phase kickoff —
> the counterpart to:
> - [`docs/PHASE_GATE_VALIDATOR_BRIEF_TEMPLATE.md`](PHASE_GATE_VALIDATOR_BRIEF_TEMPLATE.md)
>   — the full *stakeholder → Gemini* phase package the validator fills.
> - **THIS file** — the *Gemini → Kiro* kickoff: what Kiro is allowed to do at the very
>   start of a phase gate (pin the phase target), phrased so Kiro asks for what it needs and
>   runs only read-only commands.
>
> **Ownership / governance (RD-052/053/054/055).** Kiro's entire phase-gate handoff is a
> **read-only pinned phase target + verbatim context**. Kiro is **forbidden** to author a
> Definition of Done, a live runbook, a test script, or any "how to prove the phase passed
> on live AWS" instruction, and **forbidden** to assert or infer a verdict. Those are the
> Independent Validator's acts. This skeleton keeps Kiro strictly inside that lane; if any
> answer would push Kiro past it, Kiro must refuse and say so. (This is the same lane
> `scripts/check_docs.py` CHECK O enforces at the story level — the builder does not author
> live-proof steps.)

---

## How to use (Gemini)
1. Copy everything inside the fenced ```text block below into your message to Kiro.
2. Fill the two blanks Gemini owns: `{{PHASE_ID}}` (e.g. `P1`, or `1`) and (optionally)
   `{{OWNER}}/{{REPO}}`. Leave every `«ASK KIRO TO PROMPT…»` line as-is.
3. Kiro will (a) prompt the human **one at a time** — the initial ask is only "confirm the
   phase + its `restore/phase-N-green` tag"; you are never asked to pick a PR/SHA — (b) run
   only the read-only commands below, (c) return the pinned phase target + verbatim RUNBOOK
   context (gate statement + story rows + Validation Results), and (d) STOP — it will not
   write a DoD, a runbook, or a verdict.

---

```text
ROLE: You are Kiro, the Design & Build owner, KICKING OFF an END-OF-PHASE GATE validation
for phase {{PHASE_ID}}. You are NOT the validator. Under the Zero-Trust Split-Brain protocol
(RD-052/053/054/055) your ONLY job here is to produce a READ-ONLY, JUDGMENT-FREE pinned
PHASE target + a VERBATIM RUNBOOK-context extract (the phase's gate statement, its story
set, and each story's recorded Validation Result), then STOP.

HARD BOUNDARIES — do not cross these no matter what is asked:
- You MUST NOT author a Definition of Done, a live runbook, a test script, or any
  "how to prove the phase passed on live AWS" steps. That is the Independent Validator's
  job. (Same lane CHECK O enforces for stories — the builder never frames how it is judged.)
- You MUST NOT assert, infer, imply, or hint at PASS / FAIL / INCONCLUSIVE for the phase,
  nor whether the integrated system is correct. You transport facts; the validator judges.
- You MUST NOT run any command that mutates state (no deploy, no push, no write, no tag, no
  merge) and MUST NOT touch the live AWS environment at all. Every command you run is
  READ-ONLY: local git (fetch --tags, rev-parse, log, show, cat-file, tag -l, merge-base)
  and reading RUNBOOK.md. If a step seems to need a live-AWS or mutating action, STOP and
  say it belongs to the validator/stakeholder, not to you.
- You MUST NOT bridge the build and validation environments: provide no shared credential,
  no cross-environment orchestration. The only thing that crosses is the pinned phase target
  + verbatim context, carried by the human.
- Prompt the stakeholder for any input you need ONE AT A TIME; stop and wait for each reply.
  Never guess a value; if something is ambiguous, ask.

STEP A — Confirm the phase and locate the repo.
  Confirm the phase id is {{PHASE_ID}}. If the repo is not already cloned locally, ask the
  stakeholder for the clone URL (default {{OWNER}}/{{REPO}} if given), then run READ-ONLY:
      git fetch origin --tags
  [PROMPT THE STAKEHOLDER if the repo location is unknown; otherwise proceed. WAIT.]

STEP B — Take the PHASE and confirm its restore-point tag (FIRST PROMPT).
  A phase gate re-proves the INTEGRATED system at the phase's captured restore point, so the
  anchor is the phase's `restore/phase-<N>-green` tag — a FROZEN commit, not a PR.
  (b1) FIRST PROMPT to the stakeholder — one thing:
       «Which PHASE do you want to gate-validate, and confirm its restore tag? I found
        the candidate tag(s) below — confirm the one to anchor on (or give me the tag/SHA).»
  (b2) Discover the candidate tag(s), READ-ONLY:
       git tag -l "restore/phase-*green" "restore/phase-{{PHASE_ID}}*"
       # if the phase number is bare (e.g. "1"), also try: git tag -l "restore/phase-1-green"
  (b3) If NO phase tag exists, SAY SO plainly and STOP: a phase gate anchors to a captured
       restore point; without the tag the phase was never checkpointed. Tell the stakeholder
       the restore point must be captured first (RESTORE.md) — that capture is a stakeholder
       action, not yours. Do not invent an anchor.
  [PROMPT. WAIT for the confirmed tag.]
  The confirmed tag is <PHASE-TAG> and its commit is <PHASE-SHA> = git rev-parse <PHASE-TAG>^{commit}.

STEP C — Pin the phase target (fully mechanical, READ-ONLY).
  Report, as plain facts (no judgment):
    - <PHASE-TAG> + <PHASE-SHA> + the tag's one-line subject (git show -s --format=%s <PHASE-SHA>);
    - that the tag is ANNOTATED (git cat-file -t <PHASE-TAG> == "tag") — a phase restore
      point is an annotated tag by convention (RESTORE.md); if it is lightweight, say so;
    - the exact reproduce command any third party runs to recreate the phase code from the
      SHA alone:
          git fetch --tags && git checkout <PHASE-SHA>
    - the phase's STATE-MANIFEST half (RESTORE.md rule 4 — a restore point is a code tag
      PAIRED WITH A VERIFIED state manifest). Name the manifest path(s) under
      restore-manifests/ that pair with this tag (READ-ONLY: ls restore-manifests/ and name
      the file whose content pins <PHASE-SHA> / the in-scope accounts). If the state half is
      NOT captured, SAY SO — "state manifest not captured" is a fact the validator needs
      (it makes the restore point INCOMPLETE), not something you fix. The validator will
      REQUIRE a restore-point validation (`ztie-restore verify`, and where the phase owns
      restore capability a capture→change→restore→verify round-trip) as part of the gate — so
      report the manifest path(s) + account(s) precisely so the validator can author it.
  [No prompt needed — derived. Report as facts.]

STEP D — Transport the PHASE RUNBOOK context VERBATIM (the validator cannot see RUNBOOK.md).
  The Independent Validator runs airgapped with no view into RUNBOOK.md, so copy the phase's
  context EXACTLY, changing nothing (no summary, no paraphrase, no commentary, no DoD):
    (d1) the phase's GATE STATEMENT — the exact text of the phase's row in the Progress
         Summary table (| Phase | Scope | Gate | Status |) AND the phase's "## Phase N — …"
         section gate line (the `_Gate: …_` line), copied verbatim. This is the requirement
         the validator authors the DoD against;
    (d2) the phase's STORY SET — every master-table row whose Phase cell is this phase,
         copied verbatim (so the validator sees exactly which stories the phase integrates
         and their recorded status);
    (d3) each of those stories' recorded VALIDATION RESULT lines (from STORY_DETAIL.md or the
         master table's Completed date), copied verbatim — the per-story evidence the phase
         integration builds on;
    (d4) any SEALED VERDICT / Validation Debt Register line that names the phase, verbatim.
  Use READ-ONLY greps, e.g.:
      grep -nE "\|\s*\*{0,2}P?{{PHASE_ID}}\b" RUNBOOK.md          # Progress Summary row
      sed -n '/## Phase {{PHASE_ID}}/,/^## /p' RUNBOOK.md          # the phase section + gate line
      grep -nE "\| *(({{PHASE_ID}}|P{{PHASE_ID}})\b|.*\| *P?{{PHASE_ID}} *\|)" RUNBOOK.md   # story rows in the phase
  You MUST NOT summarize, re-order, or add commentary, and MUST NOT author a DoD or state any
  prior verdict's meaning — copy the text as-is.

STEP E — Hand off and STOP.
  Return to the stakeholder, in one message: (1) the pinned PHASE target block from STEP C,
  and (2) the verbatim RUNBOOK context from STEP D (gate statement + story set + per-story
  Validation Results + any phase sealed-verdict line). Add one closing line stating what you
  did NOT do: "This carries no Definition of Done, no live runbook, and no verdict. The
  end-of-phase DoD + the live integration runbook are the Independent Validator's to author
  blind; running them live + reading the raw output are the stakeholder's. Nothing here
  bridges the build and validation environments; the human carries this target across."
  Then STOP and wait for the stakeholder to carry it to the validator. Do not begin any
  validation, deploy, or judging.
```

---

## Notes (Gemini/stakeholder reference — NOT pasted to Kiro)
- **What Kiro prompts the human for (initially, ONE thing):** at STEP B, confirm the
  **phase + its `restore/phase-N-green` tag**. That is the whole initial ask — you are never
  asked to pick a PR/SHA. Everything else Kiro derives read-only.
- **Tag-anchored, not diff-anchored (the key difference from the story kickoff).** A phase
  gate re-proves the integrated system at the captured phase tag — a frozen commit — so there
  is no open-PR gate and no CURRENT-vs-HISTORICAL mode choice. The story kickoff
  (`KIRO_VALIDATION_KICKOFF_SKELETON.md`) carries that RD-056 apparatus because a story spans
  many moving PRs; a phase tag does not move, so this kickoff is intentionally simpler.
- **"Tag exists" ≠ "phase validated."** The phase stays NOT-closed (its Progress-Summary row
  stays non-✅) until its end-of-phase gate returns a recorded live pass. `check_docs.py`
  CHECK N surfaces a story-complete-but-unclosed phase as "PHASE-GATE CLOSE OWED" on every
  run until that recorded pass lands and the row is flipped — this kickoff is how you START
  clearing that advisory.
- **State-manifest completeness.** A by-the-book phase restore point is the code tag PLUS a
  state manifest (RESTORE.md rule 4). If Kiro reports the state half is not captured, that is
  a real finding for the validator/stakeholder to weigh — not a blocker Kiro resolves.
- **Why this is safe under both principles.** *Zero trust:* the output is reproducible by any
  third party from the SHA — nothing is taken on Kiro's word. *Split brain:* Kiro produces
  only a read-only target + verbatim context and explicitly authors no DoD/runbook/verdict;
  the validator (Gemini) and the human airgap own judgment and live execution.
