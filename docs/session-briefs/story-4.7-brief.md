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
>
> **⚠️ REWORK-AWARE (RD-048/RD-049).** This brief was refreshed 2026-09-14 after the 4.6
> rework + the H.2 primitive. 4.7 does **NOT** read the human decision from the Hub. It
> **VERIFIES a Hub-signed `decision.token.v1` OFFLINE** (`decision == "rejected"`) exactly the
> way the reworked 4.6 verifies an `accepted` token — the Hub is strictly the control plane
> (RD-048); the spoke never reads it. 4.7 reuses the SAME `lib/decision_auth` verify primitive
> (built + validated live as **H.2 ✅**) and the SAME embedded Hub public key.

---

## Story 4.7 — REJECT → destroy in Forensic / INCONCLUSIVE → hold

| Field | Value |
|-------|-------|
| **Phase** | P4 — Reporting & Handoff |
| **Build tier** | 14 — depends on `4.1` (tier 13) + **`H.2` (tier 6, the auth-decision primitive)**. The tied, independent sibling of `4.6` (also tier 14). This session does NOT advance to a new tier or a new phase. |
| **Date** | TBD (next session) |
| **Status** | ⬜ Not Started. |
| **Depends on** | **4.1 ✅** (RD-041, the per-intake status read-model / the Hub tracking record — for the crossed-outcome integrity binding) **and H.2 ✅** (RD-048/RD-049, `lib/decision_auth` + the Hub `ZtieDecisionSigningStack`). Like 4.6, 4.7 is the destroy/hold MECHANISM, decoupled from the human-decision UI (4.4). |
| **Registered decision** | **Implements RD-047 (the enforcement-action family) + RD-048/RD-049 (the authenticated-decision boundary + mechanism).** Like other build stories it registers NO new RD unless a genuinely new sub-decision arises (e.g. if the destroy-outcome crossing needs its own decision). Do NOT author a "reject decision" RD — the authenticated-decision mechanism already exists. Verify before assuming: `grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md \| sort -u \| tail`. |
| **Builds from restore point** | Branch the CODE off current `main` (which carries the 4.6 rework + H.2 + PR #153, AND the closed 2.4R/2.4S work + the ⛔ deploy code-asset gate in `story-2.4R-DEPLOY-VERIFY.md`). |
| **Session goal** | Build the REJECT/INCONCLUSIVE enforcement action: given a Hub-signed `rejected` `decision.token.v1` verified OFFLINE, a Forensic-side Lambda **destroys** the raw artifact (delete all object versions under `intake/<intake_id>/`) **and** tears down any live detonation chamber for that intake (terminate the ephemeral EC2 if one is still running — explicit, not TTL), then records a bounded, verdict-free destroy OUTCOME to the Hub (the derived report survives). On INCONCLUSIVE it **holds** (records a hold outcome; destroys nothing, pushes nothing). **Fail-closed / fail-safe: never destroy without a verified `rejected` token; never push (that is 4.6).** Confirm the design forks at the PLAN FIRST GATE. |

---

### ⚠️ ADVANCEMENT GATE (read FIRST at STEP 0)

**4.7 is a NEW FEATURE story. It may begin ONLY if its Depends-on are ALL ✅ AND the
Validation Debt Register is EMPTY.** STEP 0 MUST re-confirm on `main`: `4.1` ✅, **`H.2` ✅**,
and the register EMPTY. The register's LAST clear was the **2.4R + 2.4S** dynamic-lane
evidence-backfill work item (✅ 2026-09-24) — NOT 4.6; that close also rolled **Phase 2 up to
✅**. Trust `main` + `check_docs`.

### ⚠️ SEQUENCING — 4.7 is the first-OPEN Ready-now pipe story

With the 2.4R/2.4S work item ✅ (2026-09-24) and the register empty, 4.7 is the first-OPEN pipe
story in tier order (tier 14). It is on the critical path to closing Phase 4: **4.4** (tier 16,
the human accept/reject UI + the auto trigger + the Hub sign-side) depends on **4.3 + 4.7**. No
confirmation needed to start it once STEP 0 confirms the register empty + the gate open (per
the SESSION_PROMPT_TEMPLATE no-confirmation clause). `check_docs` CHECK J will emit a
NON-blocking advisory (on-deck 4.7 vs first-OPEN-by-row-order B.1) — reconciled by the recorded
2026-09-13 Phase-4-ahead-of-B.1 reorder in `WORK_LOG.md`.

### What This Story Is (nature + gate role)

**Nature: NEW FEATURE story — the REJECT/INCONCLUSIVE enforcement action.** The single
sentence that prevents the most likely category error: **4.7 destroys ONLY on a verified
Hub-signed `rejected` token — NEVER on the advisory `recommended_verdict`** (RD-040), and
INCONCLUSIVE is a HOLD, not a destroy. It is fail-safe: absent a genuine signed REJECT,
nothing is destroyed. And it **never reads the Hub** — the decision arrives as a signed token
verified offline (RD-048/RD-049), the mirror of the reworked 4.6.

### Objective & Value

- **Objective:** a Forensic-side, fail-safe destroy-on-REJECT (artifact + detonation
  chamber) + hold-on-INCONCLUSIVE, gated by a Hub-signed `rejected` token verified OFFLINE,
  with a bounded, verdict-free outcome crossed to the Hub; the derived report always survives
  in the Hub.
- **Why it matters:** it is the other half of the enforcement door — a rejected artifact is
  provably destroyed in the blast zone (nothing lingers, nothing is promoted), and an
  edge-case INCONCLUSIVE holds for a human. Completes the PASS/FAIL/INCONCLUSIVE flow, on the
  same authenticated-decision trust model as 4.6.

### Approach & Constraints — the design forks to confirm at the PLAN FIRST GATE

Recommended options marked **(rec)**:

1. **Trigger + representation.** **(rec)** Mirror the REWORKED 4.6: an invokable Lambda
   (payload `{intake_id, decision_token, signature, artifact_s3_key?}`) that VERIFIES the
   Hub-signed `decision.token.v1` OFFLINE via the vendored `lib/decision_auth`
   (`verify.verify_decision` with `expected_decision="rejected"`) and acts ONLY on a verified
   `rejected` token (destroy). The auto Hub→Forensic decision-event trigger is deferred to
   4.4. Reuse the SAME embedded `HUB_PUBLIC_KEY_PEM` + `TRUSTED_KEY_IDS`. *(Confirm: how does
   INCONCLUSIVE reach 4.7? A HOLD issues NO token at all (per AUTHENTICATED_DECISIONS.md §4
   INCONCLUSIVE = no token) — so 4.7's hold path = "no valid `rejected` token present" = the
   fail-safe default; REJECT is the only destructive path. Recommend NOT inventing an
   `inconclusive` token.)*
2. **What "destroy the artifact" means.** **(rec)** Delete ALL object versions +
   delete-markers under `intake/<intake_id>/` in the Forensic artifact bucket (the bucket is
   versioned, so a single delete is insufficient — the OD-001 lesson). Confirm the derived
   Forensic outputs (findings/ runs/) are also destroyed or explicitly retained.
3. **What "destroy the detonation chamber" means.** **(rec)** If a Story-2.3 ephemeral EC2
   is still running for this intake, terminate it explicitly (don't wait for the 5-min TTL);
   if none is running (the common case — TTL already reaped it), record that as
   `chamber: none_running`. Confirm how 4.7 finds the instance (a tag by intake_id?).
4. **The destroy authorization gate.** **(rec)** A destructive action must be fail-safe: the
   authorization is a VERIFIED Hub-signed `rejected` token (signature valid + `decision ==
   rejected` + `sha256` binds the artifact bytes + fresh + trusted key) — the exact five
   checks 4.6 runs, with `expected_decision="rejected"`. NEVER destroy on an unsigned /
   tampered / wrong-decision / absent token. No interactive path (the signed token IS the
   authorization).
5. **The crossed outcome.** **(rec)** A bounded, verdict-free destroy/hold outcome — decide
   whether to add a new RD-013 envelope kind or extend the 4.6 `handoff` kind with `outcome:
   destroyed`/`held` (confirm which; if it needs its own decision, register it then). Records
   what was destroyed (by reference/count) + that the report survives. NO verdict field.

Other constraints: production-quality (real deletes/terminates; moto only at unit level);
AWS-native; docs first-class (RD-015). **NEVER re-execute the artifact.** The Hub stays out
of the blast zone (the destroy happens in Forensic; only the bounded outcome crosses; **no
spoke→Hub read** — RD-048). The pusher/destroyer role must have **NO `dynamodb`** and **NO
`TRACKING_TABLE`**, mirroring the 4.6 rework.

### Definition of Done / Validation Gate

- **Done means (live, recorded):** for an intake with a Hub-signed `rejected` token verified
  OFFLINE, the Forensic artifact (all versions) is destroyed AND any live detonation chamber
  is torn down; a bounded verdict-free destroy outcome crosses to the Hub; the derived report
  still exists in the Hub. AND the fail-safe invariant holds from every angle: no token /
  bad signature / wrong-decision (`accepted`) / sha-mismatch / stale / untrusted-key → NO
  destroy. AND INCONCLUSIVE (no `rejected` token) holds (no destroy, no push). AND the live
  destroyer role has NO `dynamodb` + env has NO `TRACKING_TABLE` (no Hub read).
- **Validation Result:** `pending`.
- **On pass:** record dated result, flip 4.7 ✅ (paired commit). **This + 4.3 unblocks 4.4**
  (which closes Phase 4).
- **On fail:** 4.7 stays 🟡 (register); fix + re-validate once.

### Management-Artifact Obligations (REQUIRED — RD-015)

- [ ] Do NOT invent a "reject decision" RD — 4.7 implements RD-047 + the existing
      RD-048/RD-049. Only register a new RD if the destroy-outcome crossing is a genuinely new
      decision; if so, add its plan-table row BEFORE referencing the number (CHECK E literal).
- [ ] On build: RUNBOOK 4.7 ⬜→🟡 + Validation Debt Register entry in the SAME commit;
      repoint the `_NEW_WORK_STORY` fixture off 4.7 if it points at 4.7.
- [ ] Author the 4.7 LIVE-RUNBOOK (three-account: Hub signs a `rejected` token / Forensic
      destroyer verifies + destroys / the outcome crosses to the Hub) + the next-story handoff
      (first-OPEN Ready-now after 4.7 = **4.4**, tier 16, which CLOSES Phase 4 on 4.3 + 4.7).

### Lessons Learned / Carry-Forward (from the 4.6 rework + the 2.4R/2.4S saga — apply here)

- **⛔ NON-SKIPPABLE post-deploy CODE-ASSET gate (the #1 lesson from 2.4R/2.4S).** Before
  concluding ANY live validation, PROVE the live Lambda runs the code under test: download the
  deployed zip and `grep` the source for THIS story's structural markers (for 4.7: the
  token-verify path `verify_decision`/`expected_decision="rejected"`/`HUB_PUBLIC_KEY_PEM` + the
  versioned-delete + chamber-terminate path), PLUS a regression guard that any prior
  diagnostic/probe marker is ABSENT. The 2.4S attempt-4 "FAIL" was a DEPLOY-GAP (stale code
  live under a green `UPDATE_COMPLETE`), not a code defect — the code was correct; a validation
  over an unverified/stale asset is INVALID. NEVER an env-var read as proof (env defaults in
  code make env-present == env-absent), NEVER trust the green `UPDATE_COMPLETE`. Reusable
  procedure + rationale: [`story-2.4R-DEPLOY-VERIFY.md`](story-2.4R-DEPLOY-VERIFY.md).
- **OPERATIONAL DEBT to be aware of (do NOT fix mid-story; non-blocking): OD-007** (offline
  wrapper smoke-test harness — the shell/host-shape class that cost 2.4S five live cycles) +
  **OD-008** (SFN false-green — the fork/parallel branch reports `SUCCEEDED` even when a
  launch/host step fails; if 4.7's live run shows a green SFN over a failed/held destroy, that
  is OD-008 — surface it, don't trust the green). Both in the RUNBOOK Operational Debt Register.
- **Verify a signed token OFFLINE; NEVER read the Hub (RD-048/RD-049).** Reuse the vendored
  `lib/decision_auth` (`canonical.py`/`verify.py`/`signature.py`/`decision.token.v1.json`,
  byte-identical + a no-drift sha256 test) exactly as `pde_handoff` does; call
  `verify.verify_decision(..., expected_decision="rejected", ...)`. Docker-bundle the Lambda
  (`cryptography` for the ECDSA verify — not in the Lambda runtime). The role has NO
  `dynamodb`; env carries `HUB_PUBLIC_KEY_PEM` + `TRUSTED_KEY_IDS`, NO `TRACKING_TABLE`.
- **Pass the Hub public key to CDK as SINGLE-LINE base64 (4.6 live defect, PR #153).** A
  multi-line PEM passed via `-c hubPublicKeyPem="$(cat pub.pem)"` TRUNCATES to the 27-byte
  header at the shell/CDK-context boundary, so the embedded key is incomplete and offline
  verify fail-closes with `bad_signature` on the happy path. Use the
  `hubPublicKeyPemBase64` context (`-c hubPublicKeyPemBase64=$(base64 -w0 pub.pem)`) that
  `bin/ztie-infra.ts` now decodes. After deploy, dump the LIVE `HUB_PUBLIC_KEY_PEM` and
  confirm it is the full ~178-byte PEM (header + body + footer), not 27 bytes.
- **Redeploy the Hub ingest stack whenever you add a new RD-013 envelope kind (4.6 deploy-gap).**
  If 4.7 adds a new `destroy`/`held` outcome kind (or a new discriminator), the live
  `hub_ingest` validator will QUARANTINE the crossed outcome until `ZtieHubTrackingStack` is
  redeployed with the new kind. Redeploy the Hub stack as part of the live run, then verify
  the outcome landed on the tracking item. (If 4.7 reuses the existing `handoff` kind
  unchanged, no Hub redeploy is needed — but confirm the live kind supports the new outcome
  enum value first.)
- **Canonical bytes must match.** `aws kms sign --message-type RAW --signing-algorithm
  ECDSA_SHA_256` over the canonical bytes = `json.dumps(token, sort_keys=True,
  separators=(",",":"))` over EXACTLY the six token keys (that is `canonical.canonical_bytes`).
  A `bad_signature` on the happy path means the signed bytes ≠ what the verifier
  canonicalizes, or the embedded PEM ≠ the signing key. Diagnose with `aws kms verify` of the
  same canonical file (isolates signing-half vs verify-half).
- **Fail-closed / fail-safe gate is the hardest invariant — test it hardest.** 4.6 pushed
  ONLY on a verified `accepted`; 4.7 must destroy ONLY on a verified `rejected`. Anything
  else (no token / bad sig / `accepted` / sha-mismatch / stale / untrusted / absent) → NO
  destroy. Prove it from every angle (an offline `test_handler` with a fake seam recording
  whether a destroy happened, + a stub verifier for the fail-closed branches).
- **DynamoDB Number → Decimal (recurring).** Any numeric field read off the Hub item via
  `boto3.resource(...).get_item` arrives as a `Decimal` — coerce (`int()`/`float()` in a try,
  reject bool), never a strict `isinstance(int)` guard; add a `Decimal` regression case.
- **Versioned-bucket delete needs ALL versions + delete-markers** (OD-001) — a plain
  `delete_object` / `s3 rm` leaves versions behind. Delete `list-object-versions` `Versions[]`
  AND `DeleteMarkers[]` under the prefix.
- **This is a Forensic story** (the artifact + chamber are in Forensic). Three accounts, three
  tabs (Hub signs the `rejected` token / Forensic destroys / Hub receives the outcome); `aws
  sts get-caller-identity` before every block; feed commands ONE LINE AT A TIME; `/tmp` +
  shell vars are wiped on a CloudShell recycle.
- **Offline tooling:** `~/.pyenv/versions/3.12.13/bin/python3 -m unittest` (pytest NOT
  installed); `~/.pyenv/versions/3.12.13/bin/ruff check`; `env -u NODE_OPTIONS npx tsc
  --noEmit` (confirm NO new error TYPE — the missing-`aws-cdk-lib` family is baseline); `env -u
  NODE_OPTIONS npx prettier --write`. `gh pr create` is BROKEN — open PRs via `gh api
  repos/warrenrutledge64/ZTIE-Issues/pulls`.
- **check_docs timing:** run it AFTER committing the status/register edit (CHECK B baseline
  is `git show HEAD:RUNBOOK.md`). CHECK E is literal — add any new RD's plan-table row before
  naming it. CHECK I — author the next-story handoff + the 4.7 LIVE-RUNBOOK before pointing
  the on-deck README at them.

> **Sequencing note:** 4.7 is the first-OPEN Ready-now pipe story (the 2.4R/2.4S work item
> closed ✅ 2026-09-24, register empty, gate disarmed). It is on the Phase-4-closure critical
> path (4.4 needs 4.3 + 4.7). Start it without confirmation once STEP 0 confirms the register
> empty + gate open; the CHECK J on-deck-vs-B.1 advisory is non-blocking (reconciled by the
> 2026-09-13 reorder).
