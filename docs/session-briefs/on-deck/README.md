# On deck (the current next-session starter)

> This folder points at the ONE prompt to paste to start the next working session.
> It is kept to a single current pointer so there is never an ambiguous or stale
> starter here. For authoritative status and ordering, read `../../RUNBOOK.md`.

## Next session: Story 4.7 — REJECT → destroy artifact + detonation chamber in Forensic / INCONCLUSIVE → hold

**Story 4.6 is ✅ (validated live 2026-09-14).** The reworked ACCEPT-push crossing (RD-047 per
RD-048/RD-049) is proven end-to-end: the Forensic pusher verifies a Hub-signed `accepted`
`decision.token.v1` **OFFLINE** (role has NO `dynamodb`, env has NO `TRACKING_TABLE` — no spoke→Hub
read), pushes the hash-verified artifact to the Pipeline-Sandbox landing bucket (it landed,
sha-matched), fail-closed 5/5, and a bounded verdict-free `handoff` outcome crossed Forensic→Hub. The
register is now **EMPTY** and the advancement gate is **OPEN**.

**Story 4.7 is the first-OPEN Ready-now pipe story (tier 14) — start it.** Paste these:

- **[`../story-4.7-PROMPT.md`](../story-4.7-PROMPT.md)** (executor-facing) +
  **[`../story-4.7-brief.md`](../story-4.7-brief.md)** (stakeholder-facing) — both REFRESHED
  2026-09-14 to the **verify-a-Hub-signed-`rejected`-token-OFFLINE** shape (they previously
  predated RD-048 and described a Hub cross-account read, which RD-048 forbids).

### What 4.7 is
The REJECT/INCONCLUSIVE half of the human gate — the sibling of 4.6. On a **verified Hub-signed
`rejected` `decision.token.v1`** (verified OFFLINE via the vendored `lib/decision_auth`, the SAME
H.2 primitive 4.6 uses, `expected_decision="rejected"`), a Forensic-side Lambda **destroys** the raw
artifact (all S3 versions + delete-markers under `intake/<intake_id>/`) **and** tears down any live
detonation chamber (terminate the ephemeral EC2 if still running — explicit, not TTL), then crosses a
bounded, verdict-free destroy OUTCOME to the Hub (the derived report survives). On INCONCLUSIVE it
**holds** (no `rejected` token is issued, so 4.7 simply does nothing — the fail-safe default). It
destroys ONLY on a verified signed `rejected` — NEVER on the advisory `recommended_verdict` (RD-040)
— and NEVER reads the Hub (RD-048): the destroyer role has NO `dynamodb`, env has NO `TRACKING_TABLE`.
On the recorded live pass 4.7 flips ✅. Then **4.4** (the human accept/reject UI + the Hub sign-side +
one-directional Hub→Forensic delivery, tier 16, dep 4.3 + 4.7) **closes Phase 4**.

### After 4.7 — the rest of Phase 4
**4.4** (tier 16, dep 4.3 + 4.7) closes Phase 4. The tier-15 **4.9** (report-enrichment, RD-046) and
tier-16 **4.8** (dashboard browser auth, RD-044) are enhancements after the tier-14 pipe work. **B.1**
(F&H, tier 6) stays Ready sequenced after per the 2026-09-13 reorder. The `_NEW_WORK_STORY` fixture
is `4.4`.

### Two hard-won lessons from the 4.6 live validation (apply directly to 4.7)
- **Pass the Hub public key to CDK as SINGLE-LINE base64** (`-c hubPublicKeyPemBase64=$(base64 -w0
  pub.pem)`, decoded by `bin/ztie-infra.ts`). A multi-line PEM via `-c hubPublicKeyPem="$(cat)"`
  TRUNCATES to a 27-byte header at the shell/CDK-context boundary, so offline verify fail-closes with
  `bad_signature` on the happy path (cost a redeploy in 4.6 — PR #153). After deploy, dump the live
  `HUB_PUBLIC_KEY_PEM` and confirm it is the full ~178-byte PEM, not 27 bytes.
- **Redeploy `ZtieHubTrackingStack` if 4.7 adds a new RD-013 outcome kind/value** — the live
  `hub_ingest` validator will quarantine the crossed outcome until then (the 4.6 deploy-gap; cost a
  Hub redeploy + re-invoke). Verify the outcome landed on the tracking item afterwards.

> **Restore baseline:** PR #143 closed the restore-tag gap (code half) — the owner still pushes
> `restore/phase-3-green` @ `e2b325d` + `restore/story-4.5-green` @ `537d61c` per
> **[`../restore-tags-phase3-and-4.5-PROMPT.md`](../restore-tags-phase3-and-4.5-PROMPT.md)**; the
> paired state manifests are tracked as **OD-004**.

> **Sequencing-guard caution (learned 2026-09-13 — see [`../../governance/WORK_LOG.md`](../../governance/WORK_LOG.md) + [`../../governance/SEQUENCING_METHOD.md`](../../governance/SEQUENCING_METHOD.md) §4a).** `check_docs` CHECK J compares the on-deck starter against the **first non-✅ bucket-A row by ROW ORDER (not tier)** and names only that ONE row. It does NOT catch an intra-phase / same-track **tier inversion** among Ready siblings. So the by-the-book next pick after 4.5 closes is **strict first-OPEN tier order** (4.6/4.7 at tier 14 before the tier-16 4.4/4.8 and the tier-15 4.9); working any Ready story ahead of a lower-tier Ready sibling — or the tier-16 enhancements ahead of these — is a **priority decision that MUST be recorded in `WORK_LOG.md` BEFORE starting**, never an executor "next" assertion.

### The 4.3 / 4.2 / 4.1 build prompts + briefs + LIVE-RUNBOOKs (for reference)
- **[`../story-4.3-PROMPT.md`](../story-4.3-PROMPT.md)** · **[`../story-4.3-brief.md`](../story-4.3-brief.md)** · **[`../story-4.3-LIVE-RUNBOOK.md`](../story-4.3-LIVE-RUNBOOK.md)**
- **[`../story-4.2-PROMPT.md`](../story-4.2-PROMPT.md)** · **[`../story-4.2-brief.md`](../story-4.2-brief.md)** · **[`../story-4.2-LIVE-RUNBOOK.md`](../story-4.2-LIVE-RUNBOOK.md)**
- **[`../story-4.1-PROMPT.md`](../story-4.1-PROMPT.md)** · **[`../story-4.1-brief.md`](../story-4.1-brief.md)** · **[`../story-4.1-LIVE-RUNBOOK.md`](../story-4.1-LIVE-RUNBOOK.md)**

### Carry-forward lessons from the 4.5 build + LIVE validation (apply to the next story)
- **PURE + READ-only + on-demand (RD-045).** `hub_report` makes NO model call (no Bedrock
  client/grant) and WRITES nothing (READ-only `get_item`; no query/scan — per-intake). Verify the
  LIVE role + env AFTER deploy — never trust the green `UPDATE_COMPLETE`.
- **Reuses the 4.1 read-model.** The Executive core is `status_model.build_status` reused verbatim
  (a VENDORED byte-identical copy of `hub_status/status_model.py` lives in `hub_report/`, with a
  no-drift sha256 test — each Lambda dir bundles as its own asset, so cross-dir import is
  impossible at runtime). If `hub_status/status_model.py` ever changes, re-copy it into
  `hub_report/` or the no-drift test fails.
- **Honest boundary (RD-013).** MITRE/Sigma/file-line render as `not_carried_on_hub` — NOT an
  error, NOT fabricated. The enrichment (widen the crossing) is 4.9 (RD-046), its own story with
  its own live validation of the crossing — do NOT widen RD-013 as a reporting side effect.
- **Advisory + human-gated (RD-040).** The recommendation is surfaced advisory (`decision:
  pending`); no bare `verdict`/`safe`/`approved`/`forward`/`malicious`/`pass_fail`/`clean` key.
- **DynamoDB Number → Decimal (the 4.5 live defect, PR #137).** `boto3.resource(...).get_item`
  deserializes a DynamoDB Number to a Python **`Decimal`**, NOT `int`/`float`. Any handler that
  reads a numeric field off a tracking item and guards it with a strict `isinstance(int)` will
  silently DROP the value (4.5's `rank` guard rejected every remediation → `remediations: 0`).
  COERCE numerics (`int(value)` / `float(value)` in a try, reject bool) like `status_model`'s
  `_coerce_score`/`_coerce_count` — never a strict isinstance check. Offline tests that build
  fixtures with plain `int`/`float` will NOT catch this; add a `Decimal` regression case. 4.6/4.7
  read the item too — apply the same coercion to any numeric they consume.
- **HTML render, not a native PDF.** "PDF for humans" = self-contained HTML → browser print-to-PDF
  (the build sandbox has no package registry, so a native PDF dep isn't installable/offline-
  testable). Every derived value is HTML-escaped (no injection).
- **API-Gateway ↔ direct-invoke contract (carried from 4.3).** If a GET `/report/{intake_id}`
  front is ever added, use a NON-PROXY integration (the Lambda returns a bare object, not a proxy
  envelope) — a `proxy: true` integration 502s. Not in 4.5's scope (direct invoke now).
- Offline tooling: `~/.pyenv/versions/3.12.13/bin/python3 -m unittest` (pytest NOT installed);
  `~/.pyenv/versions/3.12.13/bin/ruff check`; `env -u NODE_OPTIONS npx tsc --noEmit` (confirm NO
  NEW error TYPE); `env -u NODE_OPTIONS npx prettier --write`. `gh pr create` is BROKEN — open PRs
  via `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`.

### G-1 carry-forward (compliance back-map — RD-014)
**G-1 is ✅ CLOSED (2026-09-12).** `docs/COMPLIANCE.md` is finished + ratified. New artifacts still
enter `Proposed` at authoring time (RD-014). Candidate mapping rows for RD-039 … RD-046 are in
`docs/COMPLIANCE.md` (Proposed); ratify on the next compliance review.

### Operational Debt: OD-004 open (non-blocking)
OD-001 / OD-002 / OD-003 are ALL closed. **OD-004 is OPEN (informational; does NOT block feature
work):** the paired restore-point state manifests for `restore/phase-3-green` +
`restore/story-4.5-green` are not captured yet (needs `scripts/ztie-restore` in Hub + Forensic +
Pipeline-Sandbox). Design watch-item: a retired Forensic bucket had an unwanted 365-day COMPLIANCE
Object Lock — do not add COMPLIANCE-mode lock to any bucket.

### Sequencing discipline (read this)
The RUNBOOK carries a binding **Sequencing rule** and METHODOLOGY §5.A.0 adds a session-open
**sequence check**: the story to START is the first OPEN item in the RUNBOOK "Ready now" schedule
(strict tier order), and working a *different* Ready story is a stakeholder-decided reorder
(recorded in WORK_LOG), never an executor self-selection. `check_docs.py` CHECK J surfaces the
on-deck-vs-first-OPEN mismatch as a **non-blocking advisory** — it is reconciled by the recorded
2026-09-13 reorder (Phase-4 pipe work ahead of the F&H track B.1).

### History note
Earlier on-deck starters (A.2, B.1, 2.6, 2.5, C.3, 3.2, G-2, G-1, 3.4, 3.5, 4.1, 4.2, 4.3, 4.5, 4.6)
were superseded as the plan progressed. This folder holds only a single pointer to the current
starter so it cannot drift into pointing at already-completed or re-sequenced work; for
authoritative status and ordering, read `../../RUNBOOK.md`.
