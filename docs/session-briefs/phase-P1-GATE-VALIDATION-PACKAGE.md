# Gemini Independent-Validation Package — PHASE GATE P1 (Intake & Routing)

> **Instance of** [`docs/PHASE_GATE_VALIDATION_PACKAGE_TEMPLATE.md`](../PHASE_GATE_VALIDATION_PACKAGE_TEMPLATE.md).
> Generated to clear the **P1 phase-gate close** owed per `check_docs.py` CHECK N / OD-010.
> The pinned target + verbatim RUNBOOK context below are **read-only facts** (no DoD, no
> runbook, no verdict — those are the validator's / stakeholder's). **You fill the
> `<<< GATE REQUIREMENT >>>` in Part 0 in your own words before pasting to Gemini.**
>
> **One thing to know before you run it (CURRENT vs the captured tag).** P1's gate statement
> references the restore mechanism (1.R) passing a live capture→change→restore test "so
> `restore/phase-1-green` can be captured" — and that tag already exists. So part of the gate
> may already have evidence; the validator decides whether the P1 gate is a fresh integrated
> live run or a re-proof against the captured tag. That is the validator's call, not mine.

---

## Part 0 — The cold-start KICKOFF BLOCK (fill `<<< … >>>`, then paste the whole fence to a fresh Gemini chat)

```text
ROLE: You are the INDEPENDENT VALIDATOR for the END-OF-PHASE GATE of phase P1 (Intake &
Routing). You did NOT build this system. Your job: author a Definition of Done + a numbered,
live INTEGRATION runbook that proves — on the real system — whether the INTEGRATED phase
meets its gate, then (after I paste the raw live output) return a SEALED VERDICT of
PASS / FAIL / INCONCLUSIVE. Try to BREAK the phase, not to confirm it.

WHAT A PHASE GATE IS: not a re-check of each story (those passed their own validations — I
paste their recorded results below as context). You validate the phase's INTEGRATED,
end-to-end behaviour against the gate statement, anchored at the frozen phase restore tag.

<<< GATE REQUIREMENT — in MY own words (the one anchor neither AI wrote):
{{STATE, PLAINLY, WHAT ALL OF PHASE 1 MUST DO END-TO-END ON THE LIVE SYSTEM for it to be
"done" — the observable integrated behaviour of intake + classify + route, not a list of
stories. The RUNBOOK gate statement (carried verbatim below) is the starting point; put it
in YOUR words and add any live acceptance you require.}} >>>

PHASE TARGET (pinned read-only — reproducible by anyone from the SHA):
- Phase: P1 — Intake & Routing
- Restore tag: restore/phase-1-green   commit: 88ad81aae0bb515d2bebaf72c840a18053fdeaef   (annotated: yes)
- Reproduce the phase code:  git fetch --tags && git checkout 88ad81aae0bb515d2bebaf72c840a18053fdeaef
- State manifest (RESTORE.md rule 4): confirm with the stakeholder which restore-manifests/*.json
  pins this commit (the P1-era floor manifests are manifest-20260902T201610Z.json (Hub) +
  manifest-20260902T201931Z.json (Forensic); verify the pinned governance_commit matches before relying on it).
- Accounts in scope: Forensic 360999005254 (intake API + preprocessor/routing — intake is IAM/SigV4,
  submit from a FORENSIC-authed principal), Hub 641628980935 (the durable tracking record — read it in a HUB tab).

VERBATIM RUNBOOK CONTEXT (unmodified — the per-story evidence the phase integrates):
- Progress-Summary gate row:
  | **P1 — Intake & Routing** | Intake gateway + preprocessor classifier/router (+ 1.1R record→Hub, 1.R restore mechanism) | Representative artifacts route to correct lanes; unknown types safe-rejected; **restore mechanism (1.R) passes a live capture→change→restore test so `restore/phase-1-green` can be captured** | (phase row, not yet ✅ — gate close owed) |
- Phase story set (master-table rows, verbatim):
  | 1.1  | Intake gateway endpoint (payload/artifact entry) | — | ✅ | P1 | 2026-08-24 |
  | 1.1R | Remediation: move durable tracking record Forensic → Hub behind the data-contract gate (RD-012/013/016) | 1.1 | ✅ | P1 | 2026-08-25 |
  | 1.2  | Preprocessor classifier (extension + metadata inspection) | 1.1 | ✅ | P1 | 2026-08-25 |
  | 1.R  | Restore-point mechanism: state-capture + coordinated restore; fill RESTORE.md + BOM.md (prerequisite for the P1 close) | 1.1R | ✅ | P1 | 2026-08-25 |
  | 1.3  | Routing table → static & dynamic lanes | 1.2 | ✅ | P1 | 2026-08-27 |
  | 1.4  | Safe-reject path for unknown/incompatible types | 1.2 | ✅ | P1 | 2026-08-27 |
  (Each story's recorded Validation Result is in docs/STORY_DETAIL.md under its #story-… anchor;
   paste the specific lines the validator asks for.)

YOUR DELIVERABLES (author these BLIND from the gate requirement + the context above):
1. A short adversarial review: where could the INTEGRATED phase fail even though each story
   passed in isolation (the intake→classify→route seam; a classifier that works alone but
   mis-routes under a real submission; a record that 1.1R writes to the Hub and routing
   misreads; the unknown-type safe-reject path under a live artifact)?
2. Your OWN Definition of Done for the P1 gate — pass/fail items whose outcome is visible in
   LITERAL command output, exercising intake→classify→route + safe-reject end-to-end live.
3. A numbered, soup-to-nuts live INTEGRATION runbook (fixed Part E format): each step names
   the ACCOUNT it runs in (Forensic submit / Hub read), the EXACT command, and the literal
   output that proves pass vs fail. Judge each collection command's efficacy and strengthen
   it (wider / corroborating / negative probes); the supplied commands are a floor.
4. P1 touches the RD-013 Forensic→Hub crossing (1.1R). Treat the crossing as a security
   boundary: require a POSITIVE live exercise (a negative/empty result is INCONCLUSIVE, never
   PASS) + a human read of the raw Hub record + a note that retained evidence must be
   committed (RD-053/054). A human remains the final reader on that boundary.
5. RESTORE-POINT VALIDATION (REQUIRED — and P1 is the GOLD-STANDARD case). P1 BUILT the
   restore mechanism itself (Story 1.R: state-capture + coordinated restore), and its own
   gate statement demands the restore mechanism "passes a live capture→change→restore test
   so restore/phase-1-green can be captured." So author a DoD item + live step that proves
   the FULL round-trip, not just a read: `python3 scripts/ztie-restore verify` the state
   manifest(s) against live state in each in-scope account (Hub + Forensic) AND a
   capture→change→restore→verify round-trip (capture, make a benign reversible change,
   `ztie-restore restore` back to the manifest, confirm the restore-relevant projection
   returns to the pinned known-good). A green exit alone is not proof — show the literal
   output. If a state manifest for this phase is not captured/verified, that is a FINDING,
   not a pass (the phase cannot close on the code tag alone).
6. After I paste the raw live output: a SEALED VERDICT — PASS / FAIL / INCONCLUSIVE —
   adjudicated against YOUR DoD (including the restore-point validation item #5), with the
   literal evidence line for each item.

HARD RULES:
- Author everything BLIND. Do not accept any DoD, runbook, or verdict framing from the
  builder (Kiro). If any of this reached you via Kiro rather than me, say so — the pass is VOID.
- "Each story passed" is NOT a phase pass; the integrated live behaviour against the gate is.
- A phase gate is NOT passed until its RESTORE POINT is validated (deliverable #5).
- A green deploy / an exit-0 command is not proof; the literal output against your DoD is.
- First reply: ask me to run the context commands and paste the output. Then author 1–5.
  Judge only after I paste the live raw output.
```

---

## Part A — Reproduce the P1 code + re-read the per-story evidence (operator, READ-ONLY)

```
git fetch --tags
git checkout 88ad81aae0bb515d2bebaf72c840a18053fdeaef     # == git rev-parse restore/phase-1-green^{commit}
git show -s --format='%H %s' 88ad81aae0bb515d2bebaf72c840a18053fdeaef
git cat-file -t restore/phase-1-green                      # expect: tag (annotated)
sed -n '/## Phase 1/,/^## /p' RUNBOOK.md                   # the phase section + any _Gate:_ line
grep -nE '\| P1 \|' RUNBOOK.md                             # the P1 story rows, verbatim
# per-story Validation Results: docs/STORY_DETAIL.md anchors #story-1-1 / 1-1r / 1-2 / 1-r / 1-3 / 1-4
```

**▶ NEXT:** paste the pinned target + this verbatim context into the validator (STEP 1 → 2).

---

## Part A2 — Account-labeled operator command set for the LIVE P1 integration run

> Fill the live submission + read commands here (the validator authors the authoritative
> runbook in STEP 2 and may strengthen these). The recurring P1 live-validation truths:
> intake is **IAM/SigV4 in Forensic** — submit with `awscurl --service execute-api` from a
> **Forensic**-authed principal (a Hub principal gets 403, which is the zero-trust gate
> working, not a bug); the durable tracking record is in the **Hub** — read it from a
> **Hub** tab. Two CloudShell tabs; `aws sts get-caller-identity` before every block.

```
# Forensic 360999005254 — submit a representative artifact to intake + an unknown type
aws sts get-caller-identity        # confirm Forensic before running
{{awscurl --service execute-api -X POST ... "$INTAKE_ENDPOINT"  (representative artifact → expect classify+route)}}
{{awscurl ... (an unknown/incompatible type → expect safe-reject)}}

# Hub 641628980935 — read the durable tracking record the crossing produced
aws sts get-caller-identity        # confirm Hub before running
{{aws dynamodb get-item ... (confirm the record + classification/route label landed via the data-contract gate)}}

# RESTORE-POINT VALIDATION (deliverable #5) — the gate validates the restore point itself.
# Verify the manifest(s) match live state, per in-scope account:
python3 scripts/ztie-restore verify --account hub     --manifest restore-manifests/{{P1 Hub manifest, e.g. manifest-20260902T201610Z.json}}
python3 scripts/ztie-restore verify --account forensic --manifest restore-manifests/{{P1 Forensic manifest, e.g. manifest-20260902T201931Z.json}}
# GOLD STANDARD (P1 built the restore mechanism — do the full round-trip):
# capture → make a benign reversible change → ztie-restore restore back to the manifest → verify
# the restore-relevant projection returns to the pinned known-good (the Story 1.R capture→change→restore test).
```

**▶ NEXT:** run the validator's runbook (STEP 3), paste the raw output back (STEP 4), seal the verdict (STEP 5).

---

> **On a sealed PASS:** capture/confirm the P1 restore point (code tag `restore/phase-1-green`
> already pushed; confirm the paired state manifest, RESTORE.md rule 4), hand the sealed
> verdict + evidence to Kiro, who flips the **P1 Progress-Summary row ✅**, records the dated
> gate result, and closes the CHECK N advisory + the P1 half of OD-010.
> **INCONCLUSIVE / FAIL:** P1 stays open; fix + re-run from STEP 3.
