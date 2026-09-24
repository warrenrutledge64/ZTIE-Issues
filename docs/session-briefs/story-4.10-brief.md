# Session Brief — Story 4.10 (Post-ACCEPT Forensic cleanup + a bounded S3 retention floor) — RD-059

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.
>
> **Story 4.10 makes a human ACCEPT leave the Forensic blast zone as clean as a human
> REJECT already does.** Story 4.7 destroys the artifact + chamber on REJECT; Story 4.6
> (ACCEPT-push) COPIES the artifact to the Pipeline-Sandbox landing bucket and deletes
> NOTHING in Forensic. So today every accepted detonation leaves its current
> `intake/<id>/` + derived `findings/<id>/` / `runs/<id>/` / `traces/<id>/` objects in
> the Forensic bucket **forever** (the lifecycle rule expires only *noncurrent* versions)
> — an unbounded per-detonation S3 cost + raw-untrusted-bytes residue in the blast zone,
> contrary to RD-012 ("Forensic holds only ephemeral state"). 4.10 closes that gap.
> Opened as **OD-009** (2026-09-24) and scheduled as this story.

---

## Story 4.10 — Post-ACCEPT Forensic cleanup + a bounded S3 retention floor

| Field | Value |
|-------|-------|
| **Phase** | P4 — Reporting & Handoff (hygiene/cost follow-on; does NOT gate the Phase-4 pipe closure — 4.4 closes Phase 4). |
| **Build tier** | 15 (if a standalone cleanup Lambda) or a **4.6 REWORK** (preferred) — depends on `4.6` (tier 14, ACCEPT-push, ✅). Sequence AFTER `4.7` + `4.4`. Confirm tier at the PLAN gate once the mechanism fork is decided. |
| **Date** | TBD (after 4.7 + 4.4). |
| **Status** | ⬜ Not Started. |
| **Depends on** | **4.6 ✅** (RD-047/RD-048/RD-049 — the ACCEPT-push whose landing confirmation gates the sweep). Not on the Phase-4-closure critical path; a cost/residue hygiene story. |
| **Registered decision** | **RD-059** (post-accept Forensic cleanup + the S3 retention floor). Registered in PROJECT_PLAN (proposed) 2026-09-24. If the mechanism turns out to need a genuinely new sub-decision, verify the next free number first (`grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md \| sort -u \| tail`). |
| **Builds from restore point** | Branch the CODE off current `main` (which will carry 4.6 ✅ + 4.7 ✅ + 4.4 ✅). |
| **Session goal** | Two parts (RD-059): **(1) a RETENTION FLOOR** — add a CURRENT-object S3 lifecycle expiration on the Forensic artifact bucket (`infra/lib/ztie-intake-stack.ts` `IntakeArtifactBucket`) so objects under `intake/`/`findings/`/`runs/`/`traces/` expire after a stakeholder-set window (bounds cost even for INCONCLUSIVE/held intakes; PLAIN lifecycle expiration, NEVER COMPLIANCE Object Lock). **(2) an EAGER POST-ACCEPT SWEEP** — on a verified `accepted` decision, AFTER 4.6 confirms the artifact landed in the Sandbox hash-matched, destroy that intake's Forensic prefixes (all versions + delete-markers, exactly as 4.7 does on reject). KEEP the VPC + subnets + gateway endpoint + SSM channel + IAM roles + launch template + the buckets themselves. Confirm the mechanism fork at the PLAN FIRST GATE. |

---

### ⚠️ ADVANCEMENT GATE (read FIRST at STEP 0)

**4.10 is a NEW feature story (or a 4.6 rework). It may begin ONLY if its Depends-on are
✅ AND the Validation Debt Register is EMPTY.** STEP 0 MUST re-confirm on `main`: **4.6 ✅**
(and, per the recorded sequence, 4.7 + 4.4 done). If the register is non-empty, clear the
open entry first. Trust `main` + `check_docs`.

### What This Story Is (nature + gate role)

**Nature: NEW feature story / 4.6 rework — accept-side blast-zone hygiene.** The single
sentence: **once the accepted artifact is safely in the Sandbox (verified + hash-matched),
its Forensic copy + derived outputs are redundant and must be destroyed — the same
versioned delete 4.7 runs on reject — while the durable/reusable infra (VPC, buckets,
roles, launch template) is KEPT.** It changes NO verdict/decision logic, never re-executes
the artifact, and the derived report survives in the Hub.

### Objective & Value

- **Objective:** accept/reject symmetry in the blast zone — a bounded retention floor on
  the Forensic artifact bucket + an eager post-accept sweep of the accepted intake's
  objects, keeping the reusable infra.
- **Why it matters:** eliminates an unbounded per-detonation S3 cost bleed and minimizes
  how long raw untrusted bytes + derived detail linger in Forensic (RD-012), without
  tearing down the expensive-to-rebuild infra.

### Approach & Constraints — the design forks to confirm at the PLAN FIRST GATE

Recommended options marked **(rec)**:

1. **Sweep mechanism.** **(rec)** FOLD the sweep into the 4.6 `pde_handoff` pusher: after
   the cross-account `PutObject` LANDS and the landing is confirmed (re-read + sha match),
   delete the intake's Forensic prefixes (all versions + markers), and record it in the
   `handoff` outcome. Symmetric with 4.7, one round-trip. This is a **4.6 rework** with its
   own recorded live validation + a widened delete grant. *(Alternative: a separate
   post-accept cleanup Lambda mirroring `pde_reject`, invoked after the push — keeps 4.6
   untouched, more moving parts. Confirm which.)*
2. **When to sweep (safety).** **(rec)** ONLY after the landing is positively confirmed
   (the object exists in Sandbox AND its recomputed sha256 == the pushed bytes) — never
   delete the Forensic original on a mere "push issued." A failed/unconfirmed push must
   leave Forensic intact (fail-safe: keep the only copy).
3. **What the sweep deletes.** **(rec)** The four intake prefixes `intake/<id>/` +
   `findings/<id>/` + `runs/<id>/` + `traces/<id>/`, ALL object versions + delete-markers
   (versioned bucket — reuse the 4.7 `destroy_intake_prefixes` pattern; consider sharing
   the helper). NEVER the bucket, VPC, roles, or launch template.
4. **Retention floor.** **(rec)** Add a current-object lifecycle `expiration` (+ keep the
   existing 90d noncurrent-version expiration) on `IntakeArtifactBucket` for the four
   prefixes, window = a STAKEHOLDER decision (e.g. 7/14/30 days). PLAIN expiration; NEVER
   COMPLIANCE Object Lock. This is the backstop for INCONCLUSIVE/held intakes that never
   get an accept OR reject.
5. **The crossed outcome.** **(rec)** If the sweep is in 4.6, extend the `handoff` outcome
   to record the post-accept cleanup (e.g. `forensic_swept: true` + a versions-deleted
   count) — a bounded, verdict-free fact; do NOT add a verdict field. If a separate Lambda,
   decide whether it reuses the 4.7 `disposition` kind (outcome `destroyed` on an accept
   context) or a small new fact — confirm at the gate (and register only if genuinely new).

Other constraints: production-quality (real deletes; moto only at unit level); AWS-native;
docs first-class (RD-015). NEVER re-execute the artifact. No spoke→Hub read (RD-048) — the
accept decision is the SAME Hub-signed token 4.6 already verifies OFFLINE. Keep the durable
infra.

### Definition of Done / Validation Gate

- **Done means (live, recorded):** (a) the retention floor is live on the Forensic artifact
  bucket (`aws s3api get-bucket-lifecycle-configuration` shows current-object expiration on
  the four prefixes + the existing noncurrent-version rule; NO Object Lock); (b) a fresh
  intake is ACCEPTED, 4.6 pushes + confirms the Sandbox landing, and the intake's four
  Forensic prefixes are then EMPTY (0 versions + 0 delete-markers) — while the VPC, buckets,
  roles, and launch template are untouched; (c) a failed/unconfirmed push leaves Forensic
  intact (fail-safe); (d) the derived report + durable record still exist in the Hub.
- **Validation Result:** `pending`.
- **On pass:** record dated result, flip ✅ (paired commit); **close OD-009** with a dated
  evidence note.
- **On fail:** stays 🟡 (register); fix + re-validate once.

### Management-Artifact Obligations (REQUIRED — RD-015)

- [ ] RD-059 row is in PROJECT_PLAN (done, proposed) — ratify on review.
- [ ] On build: RUNBOOK 4.10 ⬜→🟡 (add the master-table row + a Validation Debt Register
      entry in the SAME commit); repoint `_NEW_WORK_STORY` off 4.10 if it lands there.
- [ ] Author the 4.10 LIVE-RUNBOOK + the next-story handoff before pointing on-deck at them
      (CHECK I).
- [ ] On the live pass, CLOSE OD-009 in the Operational Debt Register (dated evidence note).

### Lessons Learned / Carry-Forward (apply here)

- **Reuse the 4.7 versioned-delete** (`destroy_intake_prefixes` / `_delete_all_versions_
  under_prefix` — deletes `Versions[]` + `DeleteMarkers[]`, batched at the 1000 cap). A
  versioned bucket needs ALL versions + markers gone, not a tombstone (OD-001).
- **Confirm the landing BEFORE deleting the original** — this is the one dangerous ordering:
  never destroy the sole Forensic copy until the Sandbox copy is positively verified.
- **No COMPLIANCE Object Lock** on the Forensic bucket — plain lifecycle expiration only
  (the standing no-WORM rule; a retired Forensic bucket once carried an unwanted 365-day
  COMPLIANCE lock, OD-002).
- **If folding into 4.6, it is a REWORK** (4.6 is ✅) — new story/branch, its own recorded
  live validation, a widened `s3:DeleteObject`/`DeleteObjectVersion`/`ListBucketVersions`
  grant scoped to the four intake prefixes; do NOT retro-edit 4.6's ✅.
- **⛔ post-deploy CODE-ASSET gate** before any live validation ([`story-2.4R-DEPLOY-VERIFY.md`](story-2.4R-DEPLOY-VERIFY.md)):
  grep the LIVE Lambda zip for this story's markers (the sweep + the landing-confirm) + a
  probe-absent guard; never an env-var read, never trust a green `UPDATE_COMPLETE`.
- **Split-brain live validation (RD-055):** the independent validator authors the DoD +
  runbook blind from the PR; the executor authors neither.
- **Offline proof bar:** `~/.pyenv/versions/3.12.13/bin/python3 -m unittest`;
  `~/.pyenv/versions/3.12.13/bin/ruff check`; `env -u NODE_OPTIONS npx tsc --noEmit` (NO new
  error TYPE); `env -u NODE_OPTIONS npx prettier --write`. `gh pr create` is BROKEN — use
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`.

> **Sequencing note:** 4.10 is a cost/hygiene follow-on, sequenced AFTER 4.7 + 4.4 (Phase-4
> closure) per OD-009. It closes OD-009 on its recorded live validation.
