# Session Brief — Story 4.7 (REJECT → destroy artifact + detonation chamber in Forensic / INCONCLUSIVE → hold)

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.
>
> **Story 4.7 is the REJECT/INCONCLUSIVE half of the human gate — the sibling of 4.6.** On a
> recorded human REJECT, ZTIE **destroys** the raw artifact **and** its detonation chamber
> (the ephemeral EC2, if any) in Forensic — explicit teardown, not waiting for the TTL —
> and nothing is promoted (the derived report survives in the Hub). On INCONCLUSIVE, it
> **holds** at the manual approval gate for human review (no destroy, no push). Together with
> 4.6 (ACCEPT→push) and 4.4 (the human UI), 4.7 completes the enforcement decision flow.

---

## Story 4.7 — REJECT → destroy in Forensic / INCONCLUSIVE → hold

| Field | Value |
|-------|-------|
| **Phase** | P4 — Reporting & Handoff |
| **Build tier** | 14 — depends on `4.1` (tier 13). The tied, independent sibling of `4.6` (also tier 14). This session does NOT advance to a new tier or a new phase. |
| **Date** | TBD (next session) |
| **Status** | ⬜ Not Started. |
| **Depends on** | **4.1 ✅** (RD-041, the per-intake status read-model / the Hub tracking record). Like 4.6, 4.7 is the destroy/hold MECHANISM, decoupled from the human-decision UI (4.4). |
| **Registered decision** | **RD-048** (to be authored this session — the REJECT-destroy / INCONCLUSIVE-hold enforcement decision). VERIFY the next free number with `grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md \| sort -u \| tail` (expect RD-048, the number after RD-047). |
| **Builds from restore point** | Branch the CODE off current `main`. |
| **Session goal** | Build the REJECT/INCONCLUSIVE enforcement action: on a recorded human REJECT, a Forensic-side Lambda **destroys** the raw artifact (delete all object versions under `intake/<intake_id>/`) **and** tears down any live detonation chamber for that intake (terminate the ephemeral EC2 if one is still running — explicit, not TTL), then records a bounded, verdict-free destroy OUTCOME to the Hub (the derived report survives). On INCONCLUSIVE it **holds** (records a hold outcome; destroys nothing, pushes nothing). **Fail-closed / fail-safe: never destroy without a recorded REJECT; never push (that is 4.6).** Confirm the design forks at the PLAN FIRST GATE. |

---

### ⚠️ ADVANCEMENT GATE (read FIRST at STEP 0)

**4.7 is a NEW FEATURE story. It may begin ONLY if its Depends-on are ALL ✅ AND the
Validation Debt Register is EMPTY.** STEP 0 MUST re-confirm on `main`: `4.1` ✅ **AND 4.6 ✅**
(4.6 must have cleared the register by its own recorded live pass — 4.7 cannot begin while
4.6 is 🟡). Trust `main` + `check_docs`.

### ⚠️ SEQUENCING — 4.7 is the first-OPEN Ready-now story once 4.6 closes

After 4.6 ✅, 4.7 is the first-OPEN pipe story in tier order (tier 14). It is on the critical
path to closing Phase 4: **4.4** (tier 16, the human accept/reject UI + the auto trigger)
depends on **4.3 + 4.7**. No confirmation needed to start it once STEP 0 confirms it is
first-OPEN + the gate open (per the SESSION_PROMPT_TEMPLATE no-confirmation clause).

### What This Story Is (nature + gate role)

**Nature: NEW FEATURE story — the REJECT/INCONCLUSIVE enforcement action.** The single
sentence that prevents the most likely category error: **4.7 destroys ONLY on a recorded
human REJECT — NEVER on the advisory `recommended_verdict`** (RD-040), and INCONCLUSIVE is a
HOLD, not a destroy. It is fail-safe: absent a genuine REJECT, nothing is destroyed.

### Objective & Value

- **Objective:** a Forensic-side, fail-safe destroy-on-REJECT (artifact + detonation
  chamber) + hold-on-INCONCLUSIVE, with a bounded, verdict-free outcome crossed to the Hub;
  the derived report always survives in the Hub.
- **Why it matters:** it is the other half of the enforcement door — a rejected artifact is
  provably destroyed in the blast zone (nothing lingers, nothing is promoted), and an
  edge-case INCONCLUSIVE holds for a human. Completes the PASS/FAIL/INCONCLUSIVE flow.

### Approach & Constraints — the design forks to confirm at the PLAN FIRST GATE

Recommended options marked **(rec)**:

1. **Trigger + representation.** **(rec)** Mirror 4.6: an invokable Lambda (`{intake_id}`)
   that reads the recorded `human_decision` and acts ONLY on `rejected` (destroy) or the
   INCONCLUSIVE state (hold); the auto Hub→Forensic decision-event trigger is deferred to
   4.4. Reuse the same `human_decision` field 4.6/4.4 use. *(Confirm: does INCONCLUSIVE come
   from `human_decision` (a fourth enum value?) or from the 3.5 advisory
   `recommended_verdict: INCONCLUSIVE` with `human_decision: pending`? Recommend: a HOLD is
   simply "not accepted and not rejected" — i.e. `human_decision` in {`pending`} — so 4.7's
   hold path = the fail-safe default, and REJECT is the only destructive path.)*
2. **What "destroy the artifact" means.** **(rec)** Delete ALL object versions +
   delete-markers under `intake/<intake_id>/` in the Forensic artifact bucket (the bucket is
   versioned, so a single delete is insufficient — the OD-001 lesson). Confirm the derived
   Forensic outputs (findings/ runs/) are also destroyed or explicitly retained.
3. **What "destroy the detonation chamber" means.** **(rec)** If a Story-2.3 ephemeral EC2
   is still running for this intake, terminate it explicitly (don't wait for the 5-min TTL);
   if none is running (the common case — TTL already reaped it), record that as
   `chamber: none_running`. Confirm how 4.7 finds the instance (a tag by intake_id?).
4. **The destroy confirmation gate.** **(rec)** A destructive action must be fail-safe: a
   deliberate confirm (the recorded REJECT IS the confirm) + a self-diagnosing log; NEVER
   destroy on absent/ambiguous decision. (The Python-input()/`ZTIE_ASSUME_NO` lesson applies
   if any interactive path exists — prefer no interactive path; the recorded REJECT gates it.)
5. **The crossed outcome.** **(rec)** A bounded, verdict-free destroy/hold outcome (a new
   RD-013 envelope kind, or extend the 4.6 `handoff` kind with `outcome: destroyed`/`held` —
   confirm which). Records what was destroyed (by reference/count) + that the report
   survives. NO verdict field.

Other constraints: production-quality (real deletes/terminates; moto only at unit level);
AWS-native; docs first-class (RD-015). **NEVER re-execute the artifact.** The Hub stays out
of the blast zone (the destroy happens in Forensic; only the bounded outcome crosses).

### Definition of Done / Validation Gate

- **Done means (live, recorded):** for an intake with a recorded human `rejected` decision,
  the Forensic artifact (all versions) is destroyed AND any live detonation chamber is torn
  down; a bounded verdict-free destroy outcome crosses to the Hub; the derived report still
  exists in the Hub. AND the fail-safe invariant holds: an intake WITHOUT a recorded reject
  (pending / accepted) is NOT destroyed. AND INCONCLUSIVE holds (no destroy, no push).
- **Validation Result:** `pending`.
- **On pass:** record dated result, flip 4.7 ✅ (paired commit). **This + 4.3 unblocks 4.4**
  (which closes Phase 4).
- **On fail:** 4.7 stays 🟡 (register); fix + re-validate.

### Management-Artifact Obligations (REQUIRED — RD-015)

- [ ] Register **RD-048** (verify next free number first); add its plan-table row BEFORE
      referencing the number in any living doc (CHECK E is literal).
- [ ] On build: RUNBOOK 4.7 ⬜→🟡 + Validation Debt Register entry in the SAME commit;
      repoint the `_NEW_WORK_STORY` fixture off 4.7 if it points at 4.7.
- [ ] Author the 4.7 LIVE-RUNBOOK + the next-story handoff (first-OPEN Ready-now after 4.7 =
      **4.4**, tier 16, which CLOSES Phase 4 on 4.3 + 4.7).

### Lessons Learned / Carry-Forward (from 4.6 — apply here)

- **Fail-closed / fail-safe gate is the hardest invariant — test it hardest.** 4.6 pushed
  ONLY on the exact string `accepted`; 4.7 must destroy ONLY on the exact string `rejected`.
  Anything not that (pending / accepted / absent / unknown) → NO destroy. Prove it from every
  angle (an offline `test_handler` with a fake seam recording whether a destroy happened).
- **DynamoDB Number → Decimal (recurring).** Any numeric field read off the Hub item via
  `boto3.resource(...).get_item` arrives as a `Decimal` — coerce, never a strict
  `isinstance(int)` guard; add a `Decimal` regression case.
- **Versioned-bucket delete needs ALL versions + delete-markers** (OD-001) — a plain
  `delete_object` / `s3 rm` leaves versions behind. Delete `list-object-versions` Versions[]
  AND DeleteMarkers[] under the prefix.
- **This is a Forensic story** (the artifact + chamber are in Forensic). It reads the
  decision from the Hub cross-account (like 4.6) and crosses only a bounded outcome back.
  Three-account discipline: `aws sts get-caller-identity` before every block.
- **Offline tooling:** `~/.pyenv/versions/3.12.13/bin/python3 -m unittest` (pytest NOT
  installed); `~/.pyenv/versions/3.12.13/bin/ruff check`; `env -u NODE_OPTIONS npx tsc
  --noEmit` (confirm NO new error TYPE); `env -u NODE_OPTIONS npx prettier --write`. `gh pr
  create` is BROKEN — open PRs via `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`.
- **check_docs timing:** run it AFTER committing the status/register edit (CHECK B baseline
  is `git show HEAD:RUNBOOK.md`). CHECK E is literal — add RD-048's plan-table row before
  naming it anywhere else. CHECK I — author the next-story handoff + the 4.7 LIVE-RUNBOOK
  before pointing the on-deck README at them.

> **Sequencing note:** 4.7 becomes the first-OPEN Ready-now story once 4.6 ✅. It is on the
> Phase-4-closure critical path (4.4 needs 4.3 + 4.7). Start it without confirmation once
> STEP 0 confirms 4.6 ✅ + the register empty.
