# Gemini Independent-Validation Package — PHASE GATE {{PHASE_ID}}

> **Purpose (RD-052 — split-brain independent validation, phase level).** The
> self-contained package the **stakeholder** fills in and pastes to the **validator brain
> (Gemini)** so Gemini can independently author the **end-of-phase Definition of Done + a
> live integration runbook** and step the stakeholder through gate-validating a whole phase
> **soup-to-nuts**. It is the phase-level sibling of the per-story
> [`docs/GEMINI_VALIDATION_PACKAGE_TEMPLATE.md`](GEMINI_VALIDATION_PACKAGE_TEMPLATE.md).
>
> **What a phase gate proves (different from a story).** A story validation proves one slice
> against a diff. A **phase gate** proves the **integration of the entire phase** against the
> phase's **gate statement** — the end-to-end behaviour the phase promised — anchored at the
> **frozen `restore/phase-N-green` tag**. The validator does not re-check each story (those
> have their own recorded Validation Results, carried here as context); it authors a DoD for
> the **integrated phase outcome** and a runbook that exercises the phase end-to-end on the
> live system.
>
> **Why it is built this way.** The build agent (Kiro) does **not** author this package's
> judgment inputs. Kiro's entire phase handoff is a **read-only pinned phase target +
> verbatim RUNBOOK context** (produced via
> [`docs/PHASE_GATE_VALIDATION_KICKOFF_SKELETON.md`](PHASE_GATE_VALIDATION_KICKOFF_SKELETON.md)):
> the phase tag + its commit, the gate statement, the phase's story set, and each story's
> recorded Validation Result — copied verbatim, with no DoD, no runbook, no verdict. The
> **stakeholder** writes the gate requirement in their own words and runs the live steps;
> **Gemini authors the DoD + runbook from scratch, blind** (METHODOLOGY §4a/§4b).
>
> **How to use.** Fastest path is **Part 0 — the cold-start KICKOFF BLOCK**: fill its blanks
> and paste the whole fenced block into a *fresh* Gemini chat; it carries the role, the gate
> requirement slot, the phase target pointers (tag + SHA), and the ordered deliverables.
> **Part A** = the read-only commands that reproduce the phase code at the tag + re-read the
> phase's recorded per-story evidence. **Part A2** (add per-phase) = the account-labeled
> operator command set for the live integration-run blocks. **Part E** = the fixed runbook-
> output format. Fill every `{{...}}`; delete these instruction lines.
>
> **This is ALWAYS a validation.** A phase gate uses the same 4-stage loop and the same
> depth rules as any other validation; only the DEGREE varies with what the phase governs
> (a phase whose scope crosses a security boundary demands a positive live exercise + a human
> raw-record read + retained evidence, RD-053/054). The KICKOFF BLOCK is a required, standard
> artifact of every phase gate — never reconstructed ad hoc.
>
> **COMMANDS ARE A FLOOR, NOT A CEILING.** Every command in this package was written by the
> builder or the operator, so Part 0 instructs the validator to **analyze each supplied
> command set for efficacy** (does it actually exercise the phase's integrated behaviour end
> to end, or could a gap hide in what it does not drive?) **and to propose additional / wider
> / negative commands** so the gate rests on sufficient evidence, not a convenient subset.

---

## FLOW MAP — the self-driving baton (do these in order; each step names the NEXT)

> **Audience boundary:** **Part 0 is the ONLY thing the validator (Gemini) sees.** Parts
> A / A2 / E are the operator's reference; the validator does not see them.

```
STEP 0  Paste Part 0 into a FRESH validator chat; fill the <<< gate requirement >>> in your words.
          Validator replies: "run the context commands and paste the output."    ▶ STEP 1
STEP 1  Run Part A (reproduce phase code @ tag + re-read per-story Validation Results).
          Paste the pinned target + verbatim context Kiro gave you.              ▶ STEP 2
STEP 2  Validator returns: an end-of-phase DoD + a numbered live INTEGRATION runbook
          authored blind from the gate statement, INCLUDING a required RESTORE-POINT
          VALIDATION item (verify — and where the phase owns restore capability, a full
          capture→change→restore→verify round-trip) AND a required BOM RECONCILIATION item
          (deployed==inventoried against live AWS). (The validator's runbook is authoritative.) ▶ STEP 3
STEP 3  Run the live integration runbook (Part A2 has the account-labeled commands): exercise
          the phase end-to-end, validate the restore point (ztie-restore verify / round-trip),
          AND reconcile the BOM against live-deployed resources; read the raw outputs. ▶ STEP 4
STEP 4  Paste the live raw output back to the validator → SEALED VERDICT (PASS/FAIL/INCONCLUSIVE). ▶ STEP 5
STEP 5  On PASS: confirm the phase restore point is COMPLETE + VALIDATED (code tag + VERIFIED
          state manifest, RESTORE.md), record the gate result, hand the sealed verdict +
          evidence to KIRO → Kiro flips the Progress-Summary phase row ✅ + records it + closes
          the CHECK N advisory / OD row (CHECK N then also hard-checks the paired restore point
          is recorded in BOM). On INCONCLUSIVE/FAIL: the phase stays open; fix + re-run from STEP 3.
```

---

## Part 0 — The cold-start KICKOFF BLOCK (paste this whole block into a fresh Gemini chat)

> **This is the hand-off.** Fill the blanks — `{{PHASE_ID}}`, the phase target pointers Kiro
> pinned (tag + SHA), and the `<<< GATE REQUIREMENT (your own words) >>>` block — then paste
> everything between the fence into a new Gemini chat. Do NOT let Kiro fill the gate
> requirement; that anchor must be yours.

```text
ROLE: You are the INDEPENDENT VALIDATOR for the END-OF-PHASE GATE of phase {{PHASE_ID}}.
You did NOT build this system. Your job: author a Definition of Done + a numbered, live
INTEGRATION runbook that proves — on the real system — whether the INTEGRATED phase meets
its gate, then (after I paste the raw live output) return a SEALED VERDICT of
PASS / FAIL / INCONCLUSIVE. Try to BREAK the phase, not to confirm it.

WHAT A PHASE GATE IS: not a re-check of each story (those passed their own validations — I
paste their recorded results below as context). You validate the phase's INTEGRATED,
end-to-end behaviour against the gate statement, anchored at the frozen phase restore tag.

<<< GATE REQUIREMENT — in MY own words (the one anchor neither AI wrote):
{{State, plainly, what the WHOLE phase must do end-to-end for it to be "done" — the
observable integrated behaviour, not a list of stories. e.g. "a representative artifact
submitted to intake is classified and routed to the correct lane, and an unknown type is
safe-rejected, all on the live system."}} >>>

PHASE TARGET (pinned by Kiro, read-only — reproducible by anyone from the SHA):
- Phase: {{PHASE_ID}}
- Restore tag: {{PHASE_TAG}}   commit: {{PHASE_SHA}}   (annotated: {{yes/no}})
- Reproduce the phase code:  git fetch --tags && git checkout {{PHASE_SHA}}
- State manifest (RESTORE.md rule 4): {{manifest path, or "state half NOT captured — a finding"}}
- Accounts in scope: {{e.g. Forensic 360999005254 (intake/detonation), Hub 641628980935 (tracking)}}

VERBATIM RUNBOOK CONTEXT (copied by Kiro, unmodified — the per-story evidence the phase integrates):
{{Paste here, exactly as Kiro returned it: the phase's Progress-Summary gate row + the
"## Phase N" gate line; every story row in the phase; each story's recorded Validation
Result line; any sealed-verdict / Validation Debt line naming the phase.}}

YOUR DELIVERABLES (author these BLIND from the gate requirement + the context above):
1. A short adversarial review: where could the INTEGRATED phase fail even though each story
   passed in isolation (seams between stories, ordering, a lane that works alone but not when
   forked, state that one story writes and another misreads)?
2. Your OWN Definition of Done for the phase gate — pass/fail items whose outcome is visible
   in LITERAL command output, exercising the gate statement end-to-end on the live system.
3. A numbered, soup-to-nuts live INTEGRATION runbook (Part E format): each step names the
   ACCOUNT it runs in, the EXACT command, and the literal output that proves pass vs fail.
   For every collection step, judge whether the command actually surfaces the needed evidence
   and STRENGTHEN it (wider / corroborating / negative probes) — the supplied commands are a
   floor, not a ceiling.
4. If the phase's scope crosses a SECURITY BOUNDARY: require a POSITIVE live exercise (a
   negative/empty result is INCONCLUSIVE, never PASS) + a human read of the raw record + a
   note that retained evidence must be committed (RD-053/054). A human remains the final
   reader on any security boundary.
5. RESTORE-POINT VALIDATION (REQUIRED — a phase gate validates the RESTORE POINT, not just
   the behaviour). A phase close captures a coordinated code+state restore point; a restore
   point you have never proven you can RESTORE FROM is faith, not a baseline. Author a DoD
   item + live step that PROVES the phase's restore point actually works, at the right depth:
     (a) ALWAYS: the state half exists AND VERIFIES against live state — run
         `python3 scripts/ztie-restore verify --account <acct> --manifest <manifest>` for
         each in-scope account and confirm the manifest's restore-relevant projection MATCHES
         the deployed reality (no drift). A manifest that was captured but never verifies is
         not a complete restore point (RESTORE.md: "annotated tag PAIRED WITH A VERIFIED state
         manifest"). If the state half is "NOT captured" (see the PHASE TARGET), that is a
         FINDING — the phase cannot pass its gate on the code tag alone.
     (b) GOLD STANDARD (require it when the phase OWNS restore capability, e.g. a phase that
         built/changed the restore mechanism, or on the stakeholder's call): a full
         capture→change→restore→verify ROUND-TRIP (the Story 1.R primitive) — capture, make a
         benign reversible change, `ztie-restore restore` back to the manifest, and confirm
         the projection returns to the pinned known-good. This proves you can actually RETURN
         to the baseline, not merely that the manifest reads consistent today.
   State the exact `ztie-restore` commands + the literal output that proves the restore point
   is sound; a green exit alone is not proof.
6. BOM RECONCILIATION (REQUIRED — the authoritative deployed==inventoried check). The BOM is
   the bill of materials: "if it is deployed/produced, it is in the inventory, tied to the
   phase + its restore point." An offline checker cannot see live AWS, so the GATE owns the
   authoritative check. Author a DoD item + live step that LISTS the phase's actually-deployed
   materials in each in-scope account (e.g. `aws cloudformation list-stack-resources` for each
   of the phase's stacks, or `ztie-restore capture` which enumerates the resolved physical
   ids) and CONFIRMS the BOM §2 inventory matches reality: every deployed VPC / API Gateway /
   Lambda / bucket / table / SSM param of the phase is listed in BOM.md with its real deployed
   identity, and NOTHING deployed is missing from the inventory (no orphan, no omission). A
   deployed resource absent from the BOM — or a BOM entry with no live counterpart — is a
   FINDING. (Offline, `check_docs.py` CHECK N already hard-checks the STRUCTURAL half: every
   CDK stack the phase introduces appears in BOM §2; this live step proves the inventory is
   complete + accurate against real AWS.)
7. After I paste the raw live output: a SEALED VERDICT — PASS / FAIL / INCONCLUSIVE —
   adjudicated against YOUR DoD (including restore-point validation #5 + BOM reconciliation
   #6), with the literal evidence line for each item.

HARD RULES:
- Author everything BLIND. Do not accept any Definition of Done, runbook, or verdict framing
  from the builder (Kiro). If any of this reached you via Kiro rather than me, say so — the
  pass is VOID and must be re-sourced.
- "Each story passed" is NOT a phase pass; the integrated live behaviour against the gate is.
- A phase gate is NOT passed until its RESTORE POINT is validated (deliverable #5) AND its
  BOM is reconciled against live AWS (deliverable #6), not just its behaviour — a closed phase
  is a coordinated, PROVEN-restorable baseline with a complete, accurate bill of materials.
- A green deploy / an exit-0 command is not proof; the literal output against your DoD is.
- First reply: ask me to run the context commands and paste the output. Then author 1–6.
  Judge only after I paste the live raw output.
```

---

## Part A — Reproduce the phase code + re-read the per-story evidence (operator, READ-ONLY)

> These produce the context the KICKOFF BLOCK references. Kiro already pinned the target via
> the phase kickoff skeleton; this is how YOU reproduce/verify it independently.

```
# Reproduce the exact phase code at the tag (any third party can run this):
git fetch --tags
git checkout {{PHASE_SHA}}            # == git rev-parse {{PHASE_TAG}}^{commit}
git show -s --format='%H %s' {{PHASE_SHA}}
git cat-file -t {{PHASE_TAG}}         # expect: tag (annotated)

# Re-read the phase's gate statement + story set + per-story Validation Results, VERBATIM:
sed -n '/## Phase {{PHASE_ID}}/,/^## /p' RUNBOOK.md     # the phase section + _Gate:_ line
grep -nE '\|\s*\*{0,2}P?{{PHASE_ID}}\b' RUNBOOK.md       # the Progress-Summary gate row
# (the per-story rows + Validation Results are in RUNBOOK.md / docs/STORY_DETAIL.md)
```

**▶ NEXT:** paste the pinned target + this verbatim context into the validator (STEP 1 → 2).

---

## Part A2 — Account-labeled operator command set for the LIVE integration run (add per-phase)

> Fill this per phase with the **account-labeled** commands the live integration runbook will
> need — submit a representative live input, drive the end-to-end path, read each raw output.
> Every command names the account it runs in and carries an `aws sts get-caller-identity`
> guard. This is the operator's floor; the validator (STEP 2) authors the authoritative
> runbook and may strengthen these.

```
# {{ACCOUNT A — name + id}}  (e.g. Forensic 360999005254)
aws sts get-caller-identity        # confirm you are in {{ACCOUNT A}} before running the block
{{the representative live submission + end-to-end driver commands for this phase}}

# {{ACCOUNT B — name + id}}  (e.g. Hub 641628980935)
aws sts get-caller-identity        # confirm you are in {{ACCOUNT B}}
{{the read-side commands that surface the integrated result + raw records}}
```

**▶ NEXT:** run the validator's runbook (STEP 3), paste the raw output back (STEP 4).

---

## Part E — Runbook output format (FIXED — every phase runbook comes out identical + downloadable)

> **Goal.** The validator's live integration runbook must have the **same shape** every time
> and be a **droppable file** — one self-contained fenced block the stakeholder saves and
> hands to the executor, never prose to reassemble. (The validator can't write files;
> "downloadable" = one clean fenced block → save-as.)

**What the stakeholder asks the validator for (deliverable #3 in Part 0):** output the
runbook as **ONE fenced code block**, nothing outside it, whose first line is the filename
marker and whose body follows the fixed structure below.

**Fixed structure (headers identical every time):**
```
<!-- FILE: docs/session-briefs/phase-{{PHASE_ID}}-GATE-LIVE-RUNBOOK.md -->
# Phase {{PHASE_ID}} — end-of-phase GATE live runbook (stakeholder)

> One-line purpose: prove the INTEGRATED phase meets its gate on the live system. Only YOU
> can run this (the executor has no AWS creds). The executor records your returned output
> VERBATIM; nothing is recorded on inference.

## Ground rules
- The accounts in scope → one CloudShell tab each (name them + IDs). A banner does NOT change the account.
- Run `aws sts get-caller-identity` BEFORE every block; if it's the wrong account, switch tabs.
- Reproduce the phase code first: git fetch --tags && git checkout {{PHASE_SHA}}.
- Feed commands ONE LINE AT A TIME. /tmp is wiped on recycle. Region us-east-1, ambient creds.

## STEP 1..N — the numbered live INTEGRATION steps
   For EACH step: the ACCOUNT it runs in, the EXACT command, and the LITERAL output that
   proves pass vs fail for the INTEGRATED phase behaviour (command-completeness — no bare
   names). The validator has weighed each collection command's efficacy and strengthened it
   (wider/corroborating/negative) — a floor, not a ceiling.

## Definition of Done (phase gate)
   Each DoD item for the integrated phase outcome with the literal evidence line that
   satisfies it. For a security-boundary phase: positive live exercise + human raw-record
   read + retained evidence (RD-053/054).

## Restore-point validation (REQUIRED — the gate validates the restore point, not just behaviour)
   The literal `ztie-restore verify` output per in-scope account proving the state manifest
   MATCHES live state (no drift) — and, when the phase owns restore capability, the full
   capture→change→restore→verify round-trip output proving you can RETURN to the baseline.
   A phase does not pass its gate on the code tag alone; "state manifest NOT captured" is a
   FINDING, not a pass.

## BOM reconciliation (REQUIRED — deployed == inventoried, against live AWS)
   The literal output listing the phase's actually-deployed materials per in-scope account
   (e.g. `aws cloudformation list-stack-resources` per stack, or the `ztie-restore capture`
   resolved-id enumeration) alongside the confirmation that BOM.md §2 lists every one of them
   with its real deployed identity (and no deployed resource is missing / no BOM entry is an
   orphan). The authoritative "if it is deployed, it is in the inventory" check (CHECK N
   enforces the structural stack-coverage half offline; this proves completeness live).

## Verdict recording
   On PASS: the sealed verdict + evidence the stakeholder hands the executor, who then
   captures/confirms the phase restore point (code tag + state manifest), flips the Progress-
   Summary phase row ✅, records the gate result, and closes the CHECK N advisory / OD row.
   INCONCLUSIVE/FAIL → the phase stays open; fix + re-run.
```

**Download / hand-off mechanics (stakeholder):**
1. Copy the validator's single fenced block.
2. Save it verbatim as `docs/session-briefs/phase-{{PHASE_ID}}-GATE-LIVE-RUNBOOK.md` (the
   `<!-- FILE: ... -->` marker names the path). In CloudShell:
   `cat > docs/session-briefs/phase-{{PHASE_ID}}-GATE-LIVE-RUNBOOK.md` then paste + Ctrl-D.
3. **Upload it to Kiro** (attach the file) **or push it to the repo** on the phase-close docs
   branch. Either way the executor has the exact runbook the validator authored.
> This runbook is the VALIDATOR's operator artifact (authored blind). Per RD-053 it does not
> replace the validator's independent authorship or the retained live evidence; it
> standardizes and makes portable the integration steps you actually run.

---

## Part C/D — The loop + the honest limits (operator reference)

- **The loop.** (1) Kiro pins the read-only phase target + verbatim context (phase kickoff
  skeleton) and STOPS. (2) You paste Part 0 + that context to Gemini. (3) Gemini authors the
  end-of-phase DoD + integration runbook blind. (4) You run it live and read the raw output.
  (5) Gemini seals PASS/FAIL/INCONCLUSIVE. (6) On PASS you capture/confirm the restore point
  and hand the sealed verdict to Kiro, who flips the phase row ✅ and records it.
- **"Each story passed" ≠ "phase passed."** The gate is the integrated live behaviour; seams
  between stories are exactly where a phase fails despite green stories.
- **"Tag exists" ≠ "phase validated."** `check_docs.py` CHECK N keeps the phase surfaced as
  "PHASE-GATE CLOSE OWED" until a recorded live pass flips the row, AND hard-fails a ✅ phase
  whose paired restore point (tag + verified state manifest) is not recorded in BOM.
- **The gate validates the RESTORE POINT itself (deliverable #5), not just behaviour.** A
  restore point you have never proven you can restore from is faith. The gate's DoD always
  includes `ztie-restore verify` (manifest matches live state) and, where the phase owns
  restore capability, the full capture→change→restore→verify round-trip (the Story 1.R
  primitive — proof you can actually RETURN to the baseline). "State half not captured" is a
  finding, never a pass.
- **The gate reconciles the BOM against live AWS (deliverable #6).** The BOM is the bill of
  materials — "if it is deployed/produced, it is in the inventory." Offline, `check_docs.py`
  CHECK N hard-fails a ✅ phase whose CDK stacks are not all in BOM §2 (structural coverage);
  but only the live gate can prove the inventory is COMPLETE + ACCURATE against real AWS, so
  the DoD lists the phase's deployed materials per account and confirms every one is in BOM §2
  (no omission, no orphan). A deployed resource absent from the BOM is a finding.
- **Two LLMs can share a blind spot.** For a phase whose scope crosses a security boundary, a
  human review + retained raw evidence (RD-054) is still required.
- **Trust the artifact, not the word — including the validator's.** A sealed PASS is
  necessary but not sufficient for a security-boundary phase; the ✅ rests on retained raw
  evidence captured at validation time (Forensic is ephemeral).
