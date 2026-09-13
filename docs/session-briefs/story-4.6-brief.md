# Session Brief — Story 4.6 (ACCEPT → push hash-verified artifact Forensic → Pipeline-Sandbox)

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.
>
> **Story 4.6 is a Phase-4 ENFORCEMENT ACTION — the ACCEPT half of the human gate.** On a
> human ACCEPT of ZTIE's findings, ZTIE PUSHES the hash-verified artifact **Forensic →
> Pipeline-Sandbox (586917955591)** — one-directional, ZTIE-initiated, least-privilege. On
> landing, the artifact is under PDE control and ZTIE's responsibility ends. This is the one
> route by which an inspected artifact leaves the blast zone toward production.

---

## Story 4.6 — ACCEPT → push artifact to Pipeline-Sandbox (PDE handoff)

| Field | Value |
|-------|-------|
| **Phase** | P4 — Reporting & Handoff |
| **Build tier** | 14 — depends on `4.1` (tier 13); build tier = 1 + 13. We remain within tier 14 (a tied, independent sibling of `4.7`). This session does NOT advance to a new tier or a new phase (Phase 4 opened at 4.1). |
| **Date** | TBD (next session) |
| **Status** | ⬜ Not Started. |
| **Depends on** | **4.1 ✅** (RD-041, the per-intake status read-model / the Hub tracking record). The master-table dependency is **4.1, NOT 4.4** — 4.6 is the push MECHANISM, decoupled from the human-decision UI (4.4). |
| **Registered decision** | **RD-047** (to be authored this session — the ACCEPT-push enforcement decision). VERIFY the next free number with `grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md \| sort -u \| tail` (expect RD-047). |
| **Builds from restore point** | Branch the CODE off current `main`. |
| **Session goal** | Build the ACCEPT enforcement action: on a recorded human ACCEPT, a Forensic-side push Lambda reads the raw artifact from Forensic S3, **verifies its sha256 against the Hub tracking record**, and PUSHES it **cross-account to a Pipeline-Sandbox landing bucket (586917955591)** — one-directional, least-privilege, **fail-closed** (no ACCEPT / hash mismatch → NO push). Stand up the Pipeline-Sandbox landing bucket + the cross-account grant. **Confirm the design forks (below) at the PLAN FIRST GATE before building.** |

---

### ⚠️ ADVANCEMENT GATE (read FIRST at STEP 0)

**4.6 is a NEW FEATURE story. It may begin ONLY if its Depends-on are ALL ✅ AND the
Validation Debt Register is EMPTY.** STEP 0 MUST re-confirm on `main`: `4.1` ✅ and the
register EMPTY (trust `main` + `check_docs`; if they disagree, `main` wins). `check_docs`
CHECK B, machine-enforced.

---

### ⚠️ SEQUENCING — 4.6 is the first-OPEN Ready-now story (no confirmation needed to start)

Per METHODOLOGY §5.A.0 + the RUNBOOK "Ready now" schedule, **4.6 is the first-OPEN pipe
story in tier order** (4.5 closed ✅ 2026-09-13; 4.6 and 4.7 are the two tier-14 OPEN
siblings, and the master-table ROW ORDER lists **4.6 first**). Per the SESSION_PROMPT_TEMPLATE
"NO CONFIRMATION NEEDED TO START THE FIRST-OPEN STORY" clause (added 2026-09-13, PR #139),
STEP 0 just re-confirms 4.6 is first-OPEN + the gate is open, then PROCEEDS — no "is this
next?" question. A stakeholder decision is needed ONLY to deviate (a logged reorder) or for a
design fork inside the story (the plan gate). **Note:** 4.7 (REJECT→destroy) is 4.6's tied
sibling and is on the critical path to closing Phase 4 (4.4 depends on 4.3 + 4.7); if the
stakeholder wants 4.7 first for that reason, that is a recorded reorder — otherwise 4.6 (the
first-listed) is next.

### Background & Context

ZTIE is the zero-trust ingress gate: nothing reaches the PDE without full inspection, and the
only route toward production is a **human-approved, hash-verified** handoff. The three-account
topology: **Hub (641628980935)** = brains + the human accept/reject gate; **Forensic
(360999005254)** = the blast zone where the raw artifact + all lanes live; **Pipeline-Sandbox
(586917955591)** = the ZTIE→PDE landing zone. On human ACCEPT, ZTIE pushes the artifact from
Forensic to Pipeline-Sandbox; the moment it lands it is under PDE control and ZTIE's job ends.
ZTIE never re-executes the artifact outside Forensic (functional user-acceptance of the
already-cleared artifact is a PDE activity in the Sandbox).

### What This Story Is (nature + gate role)

**Nature: NEW FEATURE story — the ACCEPT enforcement action.** It builds the push mechanism
+ the enforced ACCEPT gate. The single sentence that prevents the most likely category error:
**4.6 pushes ONLY on a recorded human ACCEPT — NEVER on the advisory `recommended_verdict`**
(RD-040: the recommendation informs; a human decides + acts). It is fail-closed: absent a
genuine ACCEPT, or on any hash mismatch, nothing leaves Forensic.

### Objective & Value

- **Objective:** a Forensic-side, one-directional, least-privilege, hash-verified push of an
  ACCEPTED artifact Forensic → Pipeline-Sandbox, plus the Sandbox landing bucket + the
  cross-account grant; fail-closed so no un-accepted/unverified artifact ever leaves Forensic.
- **Why it matters:** it is the enforcement mechanism of ZTIE as a transit hub — the one
  controlled door from the blast zone toward production, gated by the human decision.

### Scope, Dependencies & Position

- **In scope:** the Forensic→Pipeline-Sandbox push Lambda; the ACCEPT-gate enforcement (reads
  a recorded human decision, refuses unless `accepted`); sha256 verification before push; the
  Pipeline-Sandbox landing S3 bucket + its cross-account bucket policy granting exactly the
  Forensic pusher role scoped `s3:PutObject`; a bounded, verdict-free handoff outcome recorded
  Hub-side (RD-013-respecting).
- **Out of scope / do NOT touch:** the human accept/reject UI + the automatic decision-event
  trigger (**4.4**); **REJECT → destroy** + the INCONCLUSIVE hold (**4.7**); re-executing the
  artifact (NEVER — ZTIE does security clearance only); the advisory verdict as a trigger.
  **ServiceNow is OUT OF SCOPE.**
- **Depends on:** **4.1 ✅**. **Unblocks:** **4.4** (the human accept/reject control that will
  auto-trigger this push and, with 4.7, closes Phase 4).

### Approach & Constraints — the design forks to confirm at the PLAN FIRST GATE

The executor MUST get explicit approval on these at the plan gate before building. Recommended
options are marked **(rec)**:

1. **Landing bucket ownership.** **(rec)** A **Pipeline-Sandbox-owned S3 bucket** (in
   586917955591) that ZTIE's Forensic pusher writes to cross-account — matches "on landing the
   artifact is under PDE control"; the bucket is the PDE's, ZTIE holds only scoped `PutObject`.
   *(Alt, rejected: a Forensic-side staging bucket the Sandbox pulls from — inverts the push
   direction + keeps the artifact under ZTIE after "handoff".)*
2. **Which account runs the push + trust direction.** **(rec)** The push Lambda runs in
   **Forensic** (the artifact is there and must NEVER be copied through the Hub — the Hub stays
   out of the blast zone). The cross-account grant lives on the **Sandbox bucket policy**
   (Sandbox trusts exactly the Forensic pusher role for `s3:PutObject` on one prefix).
3. **How the ACCEPT is represented + how 4.6 is triggered (before 4.4 exists).** **(rec)** 4.6
   is an **invokable push mechanism** — invoked with `{intake_id}` — that reads the recorded
   human decision and **refuses unless it is a genuine `accepted`** (fail-closed). The
   AUTOMATIC Hub→Forensic decision-event wiring (so an ACCEPT auto-triggers the push) is
   **deferred to 4.4** (which owns the decision). For 4.6's live validation, the stakeholder
   records the ACCEPT decision directly, then invokes the pusher. *(Confirm: is the decision a
   field on the Hub tracking item that the Forensic pusher reads cross-account, and what is the
   field name / who is authorized to write it?)*
4. **Hash verification.** **(rec)** The pusher recomputes the sha256 of the Forensic artifact
   and checks it against the Hub tracking record's `sha256` BEFORE pushing (refuse on
   mismatch); it sets object metadata + returns the hash so the landing can be verified.
5. **Fail-closed guarantees (the DoD's hard invariant).** No recorded `accepted` → no push;
   hash mismatch → no push; artifact never routed through the Hub. This is the invariant to
   test hardest.

Other constraints: production-quality (real cross-account S3 push; no mocks in the execution
path); AWS-native; docs first-class (RD-015), PR-reviewed. Because the build sandbox has no
live AWS, the executor unit-tests the PURE gate/hash/decision logic and the STAKEHOLDER
validates the real cross-account push live.

### Validation Rationale & Compliance Mapping (REQUIRED — RD-014)

- **Rationale:** 4.6 is the enforcement door out of the blast zone; a one-directional,
  least-privilege, hash-verified, human-ACCEPT-gated, fail-closed push is the controlled way an
  inspected artifact reaches the PDE without ZTIE ever re-executing it or the Hub touching it.
- **Candidate control mappings** *(proposed; ratified on review):*

| Framework | Control ID | Control Name | Rationale | Status |
|-----------|-----------|--------------|-----------|--------|
| NIST 800-53 r5 | AC-4 | Information Flow Enforcement | Only a human-accepted, hash-verified artifact flows Forensic→Sandbox | Proposed |
| NIST 800-53 r5 | CA-6 | Authorization | The human ACCEPT authorizes the handoff | Proposed |
| NIST 800-53 r5 | AC-6 | Least Privilege | Forensic pusher scoped to one `PutObject` prefix on the Sandbox bucket | Proposed |
| NIST 800-53 r5 | SI-7 | Software/Firmware/Information Integrity | sha256 verified before push | Proposed |
| NIST 800-53 r5 | SC-7 | Boundary Protection | One-directional, ZTIE-initiated crossing out of the blast zone | Proposed |
| NIST CSF | PR.DS-6 | Integrity checking | Hash verification of the handed-off artifact | Proposed |
| ISO 27001:2022 | A.8.16 | Monitoring activities | Bounded handoff outcome recorded | Proposed |
| ISO 27001:2022 | A.5.14 | Information transfer | Controlled cross-account artifact transfer | Proposed |

### Management-Artifact Obligations (REQUIRED — RD-015)

- [ ] Story's brief + runbook entry updated (status, Validation Result, dates).
- [ ] PROJECT_PLAN and RUNBOOK in exact alignment (4.6 identical in both).
- [ ] Register RD-047 (verify next free number first); add its plan-table row BEFORE
      referencing the number in any living doc (CHECK E is literal).
- [ ] All doc changes PR-reviewed (branch + PR, never straight to main).
- [ ] On build: RUNBOOK 4.6 ⬜→🟡 + Validation Debt Register entry in the SAME commit;
      repoint the `check_docs` `_NEW_WORK_STORY` fixture off 4.6 if it points at 4.6.
- [ ] On validation pass: record Validation Result + flip 4.6 ✅ (paired commit).
- [ ] Author the 4.6 LIVE-RUNBOOK + the next-story handoff (first-OPEN Ready-now = 4.7).

### Definition of Done / Validation Gate

- **Done means (live, recorded):** for an intake with a recorded human `accepted` decision,
  the pusher verifies the sha256 and pushes the artifact Forensic → the Pipeline-Sandbox
  landing bucket (586917955591); the object lands + its hash matches. AND the fail-closed
  invariant holds: an intake with NO accept (or a hash mismatch) is REFUSED — nothing leaves
  Forensic. The Hub records a bounded, verdict-free handoff outcome. The artifact never
  transits the Hub.
- **Validation Result:** `pending`.
- **On pass:** record dated result, flip 4.6 ✅ (paired commit), keep PLAN ↔ RUNBOOK aligned.
- **On fail:** 4.6 stays 🟡 (added to the register in the same commit); fix + re-validate.

### Risks & Watch-Items

- **ADVANCEMENT GATE:** 4.1 must be ✅ and the register EMPTY.
- **PUSH ONLY ON A REAL HUMAN ACCEPT (RD-040)** — never the advisory verdict; fail-closed.
- **Hub stays out of the blast zone** — the artifact goes Forensic→Sandbox directly; it must
  NEVER be copied through the Hub. Only a bounded derived outcome crosses to the Hub (RD-013).
- **Least privilege** — the Forensic pusher gets exactly `s3:PutObject` on one Sandbox prefix;
  nothing broader; the grant is on the Sandbox bucket policy.
- **Hash verify before push** — refuse on mismatch (SI-7 / integrity).
- **NEVER re-execute the artifact** outside Forensic — ZTIE does security clearance only.
- **Cross-account KMS** — if the Forensic artifact bucket / Sandbox bucket use KMS, the pusher
  needs decrypt on the source key + the Sandbox bucket must accept the put (encryption + key
  policy). Pin this at the plan gate.

### Lessons Learned / Carry-Forward (from 4.1–4.5)

- **DynamoDB Number → Decimal (4.5 live defect, PR #137).** `boto3.resource(...).get_item`
  deserializes a DynamoDB Number to a Python **`Decimal`**, NOT `int`/`float`. Any numeric read
  off a tracking item guarded by a strict `isinstance(int)` will silently drop the value.
  COERCE (`int()`/`float()` in a try, reject bool) — never a strict isinstance check. Add a
  `Decimal` regression case (offline `int` fixtures won't catch it). 4.6 reads the Hub decision
  + sha256 — any numeric/typed field it consumes needs the same care.
- **API-Gateway ↔ direct-invoke Lambda contract (4.3 live defect).** The Phase-4 Lambdas are
  built for DIRECT invoke and return a BARE object, not a `{statusCode, body}` proxy envelope.
  If 4.6 ever gets an HTTP front, use a NON-PROXY integration (a `proxy: true` integration
  502s). 4.6 as specced is invoked directly — no HTTP front in scope.
- **Deploy-gap discipline.** Confirm the checkout carries the story's code before `cdk deploy`;
  AFTER deploy, inspect the LIVE resource (env, role, bucket policy) — a green `UPDATE_COMPLETE`
  can ship stale code / the wrong checkout. Verify the fixed thing actually took.
- **Two accounts → two (or three) CloudShell tabs.** 4.6 spans Forensic (the pusher + the
  artifact) and Pipeline-Sandbox (the landing bucket) — and the Hub holds the decision + the
  outcome. Run `aws sts get-caller-identity` before EVERY block; a banner comment does not
  change the account. This is the first story that touches the Pipeline-Sandbox account
  (586917955591) — confirm the operator has creds for it.
- **Offline tooling:** `~/.pyenv/versions/3.12.13/bin/python3 -m unittest` (pytest NOT
  installed); `~/.pyenv/versions/3.12.13/bin/ruff check`; `env -u NODE_OPTIONS npx tsc
  --noEmit` (confirm NO new error TYPE — the missing-`aws-cdk-lib`/`@types/node` family is the
  baseline); `env -u NODE_OPTIONS npx prettier --write`. `gh pr create` is BROKEN — open PRs
  via `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`.
- **check_docs timing:** run `python3 scripts/check_docs.py` + `... -m unittest
  scripts.test_check_docs` AFTER committing the status/register edit (CHECK B baseline is
  `git show HEAD:RUNBOOK.md`). CHECK E is literal — add RD-047's plan-table row before naming
  it anywhere else.

> **Sequencing note:** 4.6 is the first-OPEN Ready-now story (tier 14, first-listed of the
> 4.6/4.7 pair) — start it without confirmation once STEP 0 confirms the gate is open. It
> unblocks 4.4 (with 4.7). If the stakeholder wants 4.7 first (critical path to Phase-4
> closure), that is a recorded reorder logged in `docs/governance/WORK_LOG.md` before starting.
