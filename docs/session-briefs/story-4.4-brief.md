# Session Brief — Story 4.4 (Interactive accept/reject control (Hub) — the human gate UI + signer + auto-delivery) — CLOSES Phase 4

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.
>
> **Story 4.4 is the HUMAN GATE — the piece that turns a human's accept/reject click into
> the authenticated action 4.6 (ACCEPT→push) and 4.7 (REJECT→destroy) already enforce.** It
> is the LAST pipe story of Phase 4: it depends on **4.3** (the dashboard render + its
> DISABLED approve/reject surface) **and 4.7** (the REJECT/destroy mechanism), and — together
> with the already-✅ 4.6 — it CLOSES Phase 4.
>
> **⚠️ REWORK-AWARE (RD-048/RD-049).** 4.4 is the SIGN side of the authenticated-decision
> primitive. On a human click it records the decision on the Hub tracking item AND produces a
> Hub-signed `decision.token.v1` (`aws kms sign` / the H.2 `ZtieDecisionSigningStack` key) and
> DELIVERS it ONE-DIRECTIONALLY Hub→Forensic to invoke 4.6 (accept) or 4.7 (reject). The Hub
> never lets a spoke read it; it HANDS OUT the signed decision. INCONCLUSIVE / hold issues NO
> token (the fail-safe default 4.7 already honors).

---

## Story 4.4 — Interactive accept/reject control (Hub) — CLOSES Phase 4

| Field | Value |
|-------|-------|
| **Phase** | P4 — Reporting & Handoff (this story CLOSES it) |
| **Build tier** | 16 — depends on `4.3` (tier 15, the dashboard render + the DISABLED approve/reject surface) + `4.7` (tier 14, the REJECT/destroy mechanism). Advancing to a new tier: re-confirm the ENTIRE dependency set is ✅ + the Validation Debt Register is EMPTY at STEP 0 (the advancement gate). |
| **Date** | TBD (next session after 4.7 clears) |
| **Status** | ⬜ Not Started. |
| **Depends on** | **4.3 ✅** (RD-043 — the dashboard render + its disabled Approve/Reject buttons this story wires live) **and 4.7 ✅** (RD-047/RD-048/RD-049 — the REJECT/destroy mechanism; 4.6 ACCEPT-push is already ✅). 4.4 is the human UI + the Hub-side signer + the one-directional Hub→Forensic decision delivery that drives 4.6/4.7. |
| **Registered decision** | Implements **RD-040** (the human is the ONLY effective decision; the advisory `recommended_verdict` is never acted upon) + **RD-047/RD-048/RD-049** (the authenticated-decision mechanism it produces + delivers). Verify the next free RD (`grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md \| sort -u \| tail`) and register one ONLY if a genuinely new sub-decision arises (e.g. the auto-delivery transport). Do NOT invent a "human gate" RD — the mechanism exists (H.2). |
| **Builds from restore point** | Branch the CODE off current `main` (which will carry 4.6 ✅ + 4.7 ✅ + H.2 + the RD-048/RD-049 primitive). |
| **Session goal** | Build the human accept/reject gate: (1) ENABLE the 4.3 dashboard Approve/Reject control (the surface 4.3 shipped DISABLED) behind an authenticated Hub action; (2) on a click, record the human decision on the Hub tracking item (`human_decision` — the durable, human-owned field 4.6/3.5 reserved) AND produce a Hub-signed `decision.token.v1` via the H.2 signing key; (3) DELIVER the signed token one-directionally Hub→Forensic to invoke 4.6 (`accepted`) or 4.7 (`rejected`); INCONCLUSIVE / no-decision issues NO token (hold). Confirm the design forks at the PLAN FIRST GATE. |

---

### ⚠️ ADVANCEMENT GATE (read FIRST at STEP 0)

**4.4 is a NEW FEATURE story AND a tier ADVANCE (15→16). It may begin ONLY if its Depends-on
are ALL ✅ AND the Validation Debt Register is EMPTY.** STEP 0 MUST re-confirm on `main`:
**4.3 ✅**, **4.7 ✅**, **4.6 ✅**, and the register EMPTY (4.7's own live pass must be recorded
first — 4.4 cannot start while 4.7 is 🟡). Trust `main` + `check_docs`.

### What This Story Is (nature + gate role)

**Nature: NEW FEATURE story — the human enforcement gate (the SIGN + deliver side).** 4.4 is
where a human's decision becomes the authenticated action the spokes enforce. The single
sentence that prevents the biggest error: **only a human's explicit accept/reject — signed by
the Hub — drives an action; the advisory `recommended_verdict` (RD-040) NEVER does, and
INCONCLUSIVE issues no token (a hold).** 4.4 produces + delivers the token; 4.6/4.7 verify +
act (already built + ✅/🟡). This is the LAST pipe story of Phase 4.

### Objective & Value

- **Objective:** a Hub-side, authenticated human accept/reject control that records the
  durable `human_decision`, signs a `decision.token.v1`, and delivers it one-directionally
  Hub→Forensic to drive 4.6 (accept→push) / 4.7 (reject→destroy); INCONCLUSIVE holds.
- **Why it matters:** it closes the enforcement loop — the human-in-the-loop that RD-040
  makes the ONLY effective decision. Completes Phase 4.

### Approach & Constraints — the design forks to confirm at the PLAN FIRST GATE

Recommended options marked **(rec)**:

1. **The UI action.** **(rec)** Enable the 4.3 dashboard's DISABLED Approve/Reject buttons
   behind an authenticated Hub action (a new authenticated `POST /decision/{intake_id}` on the
   4.3 API Gateway, or a small Hub-side action Lambda). Keep the 4.3 render UNCHANGED except
   enabling the control. *(Confirm: reuse the 4.3 API + IAM auth, or add Cognito — note 4.8 is
   the browser-auth story; 4.4 may stay IAM/SigV4 + defer browser auth to 4.8.)*
2. **Recording the decision.** **(rec)** Write `human_decision ∈ {accepted, rejected}` (+ who /
   when) to the Hub tracking item — the durable, human-owned field 4.6/3.5 reserved. This is
   the authoritative record; the token is derived from it.
3. **Signing + delivery.** **(rec)** On the click, `aws kms sign` a canonical `decision.token.v1`
   with the H.2 signing key (Hub-only `kms:Sign`) and DELIVER it one-directionally Hub→Forensic
   (invoke 4.6/4.7 with `{intake_id, decision_token, signature, artifact_s3_key}`). *(Confirm
   the transport: a direct cross-account Lambda invoke, an EventBridge event, or an SQS
   message — one-directional, least-privilege, no Forensic→Hub read.)*
4. **INCONCLUSIVE / hold.** **(rec)** No token issued (the fail-safe default 4.7 already
   honors) — the intake simply holds at the gate. Do NOT invent an `inconclusive` token.
5. **The auto-trigger vs manual.** **(rec)** 4.4 owns the automatic Hub→Forensic delivery on
   the human click (the piece 4.6/4.7 deferred). Confirm whether a manual `aws kms sign` recipe
   is retained as a break-glass path.

Other constraints: production-quality; AWS-native; docs first-class (RD-015). The Hub SIGNS,
never lets a spoke read it (RD-048). The advisory verdict is never the trigger (RD-040).

### Definition of Done / Validation Gate

- **Done means (live, recorded):** a human accept on the dashboard records `human_decision =
  accepted`, signs a token, delivers it to 4.6, and the artifact is pushed; a human reject
  records `human_decision = rejected`, signs a `rejected` token, delivers it to 4.7, and the
  artifact + chamber are destroyed; INCONCLUSIVE holds (no token, no action). The advisory
  verdict never triggers either. No Forensic→Hub read anywhere.
- **Validation Result:** `pending`.
- **On pass:** record dated result, flip 4.4 ✅ (paired commit). **This CLOSES Phase 4** — set
  the P4 Progress-Summary row ✅ + capture the phase restore point (RESTORE.md + BOM.md).
- **On fail:** 4.4 stays 🟡 (register); fix + re-validate once.

### Management-Artifact Obligations (REQUIRED — RD-015)

- [ ] Verify the next free RD before registering one; register a new RD ONLY for a genuinely
      new sub-decision (e.g. the delivery transport), its plan-table row BEFORE any living-doc
      reference (CHECK E literal).
- [ ] On build: RUNBOOK 4.4 ⬜→🟡 + Validation Debt Register entry in the SAME commit;
      repoint the `_NEW_WORK_STORY` fixture off 4.4 (to the next still-⬜ story).
- [ ] Author the 4.4 LIVE-RUNBOOK + the next-story handoff (after 4.4, Phase 4 is closed — the
      next work is the F&H **B.1** track / **4.9** enrichment / **4.8** browser-auth per the
      recorded reorder).
- [ ] On the live pass, this CLOSES Phase 4 — flip the P4 Progress-Summary row ✅ + capture the
      phase restore point.

### Lessons Learned / Carry-Forward (from 4.6 + 4.7 — apply here)

- **The authenticated-decision primitive is built (H.2) + proven both directions (4.6 accept,
  4.7 reject).** 4.4 is the SIGN + DELIVER side — reuse the H.2 `ZtieDecisionSigningStack` key
  + the canonical `decision.token.v1` bytes (`json.dumps(token, sort_keys=True,
  separators=(",",":"))` over the six keys). Sign with `aws kms sign --message-type RAW
  --signing-algorithm ECDSA_SHA_256`.
- **Pass any Hub public key to CDK as SINGLE-LINE base64** (the 4.6 truncation defect, PR #153).
- **Redeploy the Hub ingest stack if 4.4 adds any new RD-013 kind** (the deploy-gap class).
- **DynamoDB Number → Decimal:** coerce any numeric read off the tracking item; never strict
  `isinstance(int)`.
- **⛔ post-deploy CODE-ASSET gate** before any live validation ([`story-2.4R-DEPLOY-VERIFY.md`](story-2.4R-DEPLOY-VERIFY.md)):
  grep the LIVE Lambda zip for this story's markers + a probe-absent regression guard; never an
  env-var read, never trust a green `UPDATE_COMPLETE`.
- **Split-brain live validation (RD-055):** the independent validator authors the DoD + runbook
  blind from the PR; the executor authors neither.
- **Offline proof bar:** `~/.pyenv/versions/3.12.13/bin/python3 -m unittest`;
  `~/.pyenv/versions/3.12.13/bin/ruff check`; `env -u NODE_OPTIONS npx tsc --noEmit` (NO new
  error TYPE); `env -u NODE_OPTIONS npx prettier --write`. `gh pr create` is BROKEN — use
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`.

> **Sequencing note:** 4.4 is tier 16 and CANNOT be first until BOTH 4.3 (✅) and 4.7 are ✅ —
> so it starts only after 4.7's recorded live pass. It is the Phase-4-closing story.
