# Validator Handover — PHASE 3 GATE (AI Correlation)

> **Instance of** [`docs/PHASE_GATE_VALIDATOR_BRIEF_TEMPLATE.md`](../PHASE_GATE_VALIDATOR_BRIEF_TEMPLATE.md).
> Generated to clear the **P3 phase-gate close** owed per `check_docs.py` CHECK N / OD-010.
> The pinned target + verbatim RUNBOOK context below are **read-only facts** (no DoD, no
> runbook, no verdict — those are the validator's / stakeholder's). **You fill the
> `<<< GATE REQUIREMENT >>>` in Part 0 in your own words before pasting to Gemini.**
>
> **State-manifest note.** `restore/phase-3-green`'s **state-manifest half is tracked as
> OD-004** (code tag pushed; state manifest not yet captured). The validator should know the
> state half may be owed — a by-the-book phase restore point pairs the tag with a manifest
> (RESTORE.md rule 4). That capture is a stakeholder action, surfaced here as a fact.

---

## Part 0 — The cold-start KICKOFF BLOCK (fill `<<< … >>>`, then paste the whole fence to a fresh Gemini chat)

```text
ROLE: You are the INDEPENDENT VALIDATOR for the END-OF-PHASE GATE of phase P3 (AI
Correlation). You did NOT build this system. Your job: author a Definition of Done + a
numbered, live INTEGRATION runbook that proves — on the real system — whether the INTEGRATED
phase meets its gate, then (after I paste the raw live output) return a SEALED VERDICT of
PASS / FAIL / INCONCLUSIVE. Try to BREAK the phase, not to confirm it.

WHAT A PHASE GATE IS: not a re-check of each story (those passed their own validations — I
paste their recorded results below as context). You validate the phase's INTEGRATED,
end-to-end behaviour against the gate statement, anchored at the frozen phase restore tag.

<<< GATE REQUIREMENT — in MY own words (the one anchor neither AI wrote):
{{STATE, PLAINLY, WHAT ALL OF PHASE 3 MUST DO END-TO-END ON THE LIVE SYSTEM for it to be
"done" — the observable integrated behaviour: paired static+dynamic inputs yield ONE unified
risk score + correlated findings + prioritized remediations + an advisory verdict, and a
false positive is reconciled. The RUNBOOK gate statement (carried verbatim below) is the
starting point; put it in YOUR words and add any live acceptance you require.}} >>>

PHASE TARGET (pinned read-only — reproducible by anyone from the SHA):
- Phase: P3 — AI Correlation
- Restore tag: restore/phase-3-green   commit: e2b325d727291b479261fbf4aa4e4540faf2f7b9   (annotated: yes)
- Reproduce the phase code:  git fetch --tags && git checkout e2b325d727291b479261fbf4aa4e4540faf2f7b9
- State manifest (RESTORE.md rule 4): NOT yet captured — tracked as OD-004 (a finding, not a blocker you resolve).
- Accounts in scope: Hub 641628980935 (the Phase-3 post-processors are PURE Hub-side Lambdas
  reading/writing the tracking item; they are invoked/observed in the HUB account). The
  upstream static+dynamic evidence originates in Forensic 360999005254 and crosses via the RD-013 gate.

VERBATIM RUNBOOK CONTEXT (unmodified — the per-story evidence the phase integrates):
- Progress-Summary gate row:
  | **P3 — AI Correlation** | Nova Pro correlation → unified threat score, findings, remediations, verdict | Paired static+dynamic inputs yield one score + correlated findings; a false positive is reconciled | (phase row, not yet ✅ — gate close owed) |
- Phase story set (master-table rows, verbatim):
  | 3.1 | Telemetry aggregation / normalization (shared schema) | 2.6 | ✅ | P3 | 2026-09-12 |
  | 3.2 | Nova Pro correlation engine (exponential-backoff retry) | 3.1, 2.5 | ✅ | P3 | 2026-09-12 |
  | 3.3 | Three Nova Pro risk scores (static / dynamic / combined, 0-100, shared rubric) — RD-038 (reworked) | 3.2 | ✅ | P3 | 2026-09-12 |
  | 3.4 | Detailed findings + prioritized remediations (over the three scores + migrated candidate-FP/gap lists) — RD-039 (scope RD-038) | 3.3 | ✅ | P3 | 2026-09-13 |
  | 3.5 | Verdict derivation — advisory recommended PASS / FAIL / INCONCLUSIVE (never acted upon; human selects on the dashboard) — RD-040 | 3.4 | ✅ | P3 | 2026-09-13 |
  (Each story's recorded Validation Result is in docs/STORY_DETAIL.md under its #story-3-… anchor;
   paste the specific lines the validator asks for.)

YOUR DELIVERABLES (author these BLIND from the gate requirement + the context above):
1. A short adversarial review: where could the INTEGRATED phase fail even though each story
   passed in isolation (the 3.1→3.2→3.3→3.4→3.5 chain over a SINGLE intake item; a score 3.3
   writes that 3.4/3.5 misread; the false-positive-reconciliation claim; whether the advisory
   verdict (3.5, RD-040) is correctly NEVER acted upon)?
2. Your OWN Definition of Done for the P3 gate — pass/fail items whose outcome is visible in
   LITERAL command output, exercising paired static+dynamic → one score + correlated findings
   + remediations + advisory verdict + a reconciled false positive, end-to-end live.
3. A numbered, soup-to-nuts live INTEGRATION runbook (fixed Part E format): each step names
   the ACCOUNT it runs in, the EXACT command, and the literal output that proves pass vs
   fail. Judge each collection command's efficacy and strengthen it (wider / corroborating /
   negative probes); the supplied commands are a floor.
4. P3 reads evidence that crossed the RD-013 Forensic→Hub boundary and derives an advisory
   verdict. Confirm the integrated chain carries NO bare effective-verdict (the 3.5 output is
   advisory recommended_verdict only, decision pending, never acted upon). If any part of the
   live exercise touches a security boundary, require a positive live exercise + a human read
   of the raw record + retained evidence (RD-053/054).
5. RESTORE-POINT VALIDATION (REQUIRED). A phase gate validates the restore point, not just
   behaviour. NOTE a known state: `restore/phase-3-green`'s state-manifest half is NOT yet
   captured — it is tracked as OD-004 (the tag was pushed code-half-only). Per RESTORE.md a
   restore point is a code tag PAIRED WITH A VERIFIED state manifest, so an uncaptured state
   half is a FINDING the gate must weigh: author a DoD item that (a) requires the paired state
   manifest be captured + `python3 scripts/ztie-restore verify`'d against live state for the
   in-scope account(s) before the phase can close, and (b) treats "state half not captured"
   as INCONCLUSIVE for the restore-point dimension, never a silent pass. (A capture→change→
   restore round-trip is the gold standard; at minimum the manifest must exist and verify.)
6. BOM RECONCILIATION (REQUIRED — deployed==inventoried against live AWS). NOTE P3 introduces
   NO NEW CDK STACK — its materials are the PURE Hub-side post-processor Lambdas (3.1–3.5)
   that live INSIDE ZtieHubTrackingStack (a P1 stack). So reconcile at the RESOURCE level, not
   the stack level: author a DoD item + live step that lists the Hub Lambdas/resources P3
   added (e.g. `aws cloudformation list-stack-resources --stack-name ZtieHubTrackingStack`,
   filtered to the correlation/scoring/remediation/verdict functions) and confirms each is in
   the BOM §2 inventory with its real deployed identity. A P3 Lambda deployed but absent from
   the BOM is a FINDING. (Offline CHECK N requires no NEW stack for P3 — correctly, since P3
   adds none — so this live resource-level reconciliation is where P3's inventory accuracy is
   proven.)
7. After I paste the raw live output: a SEALED VERDICT — PASS / FAIL / INCONCLUSIVE —
   adjudicated against YOUR DoD (including restore-point validation #5 + BOM reconciliation
   #6), with the literal evidence line for each item.

HARD RULES:
- Author everything BLIND. Do not accept any DoD, runbook, or verdict framing from the
  builder (Kiro). If any of this reached you via Kiro rather than me, say so — the pass is VOID.
- "Each story passed" is NOT a phase pass; the integrated live behaviour against the gate is.
- A phase gate is NOT passed until its RESTORE POINT is validated (#5) AND its BOM is
  reconciled against live AWS (#6); the P3 state-manifest half is OD-004 (not yet captured) —
  that is a finding, not a silent pass.
- A green deploy / an exit-0 command is not proof; the literal output against your DoD is.
- First reply: ask me to run the context commands and paste the output. Then author 1–6.
  Judge only after I paste the live raw output.
```

---

## Part A — Reproduce the P3 code + re-read the per-story evidence (operator, READ-ONLY)

```
git fetch --tags
git checkout e2b325d727291b479261fbf4aa4e4540faf2f7b9     # == git rev-parse restore/phase-3-green^{commit}
git show -s --format='%H %s' e2b325d727291b479261fbf4aa4e4540faf2f7b9
git cat-file -t restore/phase-3-green                      # expect: tag (annotated)
sed -n '/## Phase 3/,/^## /p' RUNBOOK.md                   # the phase section + any _Gate:_ line
grep -nE '\| P3 \|' RUNBOOK.md                             # the P3 story rows, verbatim
# per-story Validation Results: docs/STORY_DETAIL.md anchors #story-3-1 / 3-2 / 3-3 / 3-4 / 3-5
```

**▶ NEXT:** paste the pinned target + this verbatim context into the validator (STEP 1 → 2).

---

## Part A2 — Account-labeled operator command set for the LIVE P3 integration run

> Fill the live driver + read commands here (the validator authors the authoritative runbook
> in STEP 2 and may strengthen these). The recurring P3 truths: the Phase-3 post-processors
> are **PURE Hub-side Lambdas** over one intake's tracking item; the upstream static+dynamic
> evidence crosses from **Forensic** via the RD-013 gate. The Hub Lambdas use custom OD-003
> log groups (read `LoggingConfig.LogGroup`, not `/aws/lambda/<fn>`); reads are
> eventually-consistent. `aws sts get-caller-identity` before every block.

```
# Forensic 360999005254 — submit an artifact that produces BOTH static + dynamic evidence
aws sts get-caller-identity        # confirm Forensic before running
{{awscurl --service execute-api -X POST ... "$INTAKE_ENDPOINT"  (an artifact routed to BOTH lanes)}}

# Hub 641628980935 — observe the integrated P3 chain on that intake's tracking item
aws sts get-caller-identity        # confirm Hub before running
{{aws lambda invoke / aws dynamodb get-item ... (confirm one combined score + correlated findings
   + prioritized remediations + advisory verdict landed; confirm no bare effective-verdict key;
   confirm a false positive is reconciled)}}

# RESTORE-POINT VALIDATION (deliverable #5). The P3 state-manifest half is OD-004 (NOT yet
# captured) — capture it first, then verify, before the phase can close:
# python3 scripts/ztie-restore capture --account hub        # (and forensic, as in scope)
# python3 scripts/ztie-restore verify  --account hub --manifest restore-manifests/<new P3 manifest>
# Until the paired manifest is captured + verifies, the restore-point dimension is INCONCLUSIVE, not a pass.

# BOM RECONCILIATION (deliverable #6) — P3 adds no new stack; reconcile at the resource level:
aws sts get-caller-identity        # Hub
aws cloudformation list-stack-resources --stack-name ZtieHubTrackingStack --query 'StackResourceSummaries[?ResourceType==`AWS::Lambda::Function`].[LogicalResourceId,PhysicalResourceId]' --output table
# Confirm the P3 Hub Lambdas (correlation / scoring / remediation / verdict post-processors) are each listed in BOM.md §2.
```

**▶ NEXT:** run the validator's runbook (STEP 3), paste the raw output back (STEP 4), seal the verdict (STEP 5).

---

> **On a sealed PASS:** confirm the P3 restore point (code tag `restore/phase-3-green` already
> pushed; capture the paired state manifest — this is OD-004), hand the sealed verdict +
> evidence to Kiro, who flips the **P3 Progress-Summary row ✅**, records the dated gate
> result, and closes the CHECK N advisory + the P3 half of OD-010.
> **INCONCLUSIVE / FAIL:** P3 stays open; fix + re-run from STEP 3.
