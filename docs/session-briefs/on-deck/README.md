# On deck (the current next-session starter)

> This folder points at the ONE prompt to paste to start the next working session.
> It is kept to a single current pointer so there is never an ambiguous or stale
> starter here. For authoritative status and ordering, read `../../RUNBOOK.md`.

## Next session: VALIDATE Story 2.4S LIVE — attempt 5 (Fix B direct-upload SILENT failure)

**Story 2.4S (+ its linked 2.4R) are 🟡 — the advancement gate is ARMED.** The confirm-before-fix probe
(2026-09-24) **PROVED Fix B (RD-058) works end-to-end on current `main`** — so there is **NO attempt-5
code fix**; the next step is a CLEAN split-brain re-validation of the current final code, deployed
correctly. On a verified-live deploy (code-asset check first), a hang-past-timeout payload deposited the
per-PID files + the `_UPLOAD_COMPLETE` sentinel to `traces/{intake_id}/`, and the Lambda logged
`using S3-uploaded behavioral trace (objects=2 complete=True ssm_status=Failed)` — the exact RD-058
intent (Failed-SSM-but-complete-S3-trace = successful capture). The attempt-4 SEALED FAIL is now
attributed to a **DEPLOY-GAP** (the live Lambda almost certainly ran pre-#200 code, so the wrapper
crashed on the `set -u` unbound `__ZTIE_RC` before the upload block ran — the empty diag + zero objects
signature), **not** a code defect. Full finding:
**[`../../validation-evidence/2.4S/attempt-4/PROBE-FINDING.md`](../../validation-evidence/2.4S/attempt-4/PROBE-FINDING.md)**
(the attempt-4 sealed FAIL record itself is unchanged at
**[`../../validation-evidence/2.4S/attempt-4/EVIDENCE.md`](../../validation-evidence/2.4S/attempt-4/EVIDENCE.md)**).

**The durable fix is PROCESS, not code (covenant §4).** Because attempt 4 was a deploy-gap, the fix is
the **NON-SKIPPABLE post-deploy live code-asset check** now enforced in
**[`../story-2.4R-DEPLOY-VERIFY.md`](../story-2.4R-DEPLOY-VERIFY.md)** (⛔ gate): before running ANY
2.4S validation, grep the LIVE `capturespec.py` zip for `__ZTIE_RC=0` AND the Fix-B upload markers
(`TRACE-UPLOAD-BEGIN` / `_UPLOAD_COMPLETE` / regional `--endpoint-url`); if any is absent the deploy is
stale — STOP, do not validate, do not seal. This is reinforced by **OD-007** (offline wrapper
smoke-test harness — a stubbed-`aws` `sh -u` execution test would have caught both the crash and the
upload behavior offline) and **OD-008** (SFN false-green — this run's fork branch reported success over
`outcome=execution_error`). The probe was reverted (PR #205 closed unmerged); `main` carries the clean
production `capturespec.py`.

**How to run the live validation — split-brain (RD-052/RD-053, the standing gate):**

- **[`../../GEMINI_VALIDATION_PACKAGE_TEMPLATE.md`](../../GEMINI_VALIDATION_PACKAGE_TEMPLATE.md)** —
  the authoritative path. The code under test is **current `main`** (all five fixes: PRs
  #195/#198/#199/#200 — NO new attempt-5 code, the probe proved the code works); the handoff is that
  PR/commit. Under **RD-055** the **stakeholder** fetches that diff **independently, directly from the
  repository API**, states the requirement in their own words, and the **independent validator brain
  (Gemini)** authors the DoD + numbered live runbook **from scratch, blind** and adjudicates. **The
  ⛔ NON-SKIPPABLE deploy code-asset check ([`../story-2.4R-DEPLOY-VERIFY.md`](../story-2.4R-DEPLOY-VERIFY.md))
  must pass before the run** — a validation over an unverified/stale asset is INVALID (that is what
  attempt 4 was). A `not_run` / empty-with-no-honest-health capture is INCONCLUSIVE, not PASS. **Kiro
  authors no runbook, supplies no diff/fetch command/snippet (RD-055).**
- **Operator hygiene reference (NOT a runbook, NOT the gate):**
  **[`../../governance/cloudshell-hygiene.md`](../../governance/cloudshell-hygiene.md)** — reusable
  CloudShell account/tab discipline, clone-currency, token safety, and deploy-gap discipline. It is
  process guidance only; the validator authors the actual live steps.
- **The probe finding (Fix B proven working; attempt-4 = deploy-gap):**
  **[`../../validation-evidence/2.4S/attempt-4/PROBE-FINDING.md`](../../validation-evidence/2.4S/attempt-4/PROBE-FINDING.md)**,
  alongside the unchanged attempt-4 sealed-FAIL record
  **[`../../validation-evidence/2.4S/attempt-4/EVIDENCE.md`](../../validation-evidence/2.4S/attempt-4/EVIDENCE.md)**.
  The full 2.4R/2.4S attempt history (attempts 1–6 / 1–4) lives in the RUNBOOK Validation Debt Register.
- On a recorded PASS: **2.4S flips 🟡→✅ AND the linked 2.4R entry clears together** (one work item),
  the register empties, and the gate OPENS (the next pipe story, **4.7**, unblocks).

### Sequencing note (the gate is ARMED — this is NOT a new feature story)
The on-deck starter is the **LIVE re-validation of the open 2.4S/2.4R work item**, which is the only
in-progress work permitted while the Validation Debt Register is non-empty (reworking/validating an
already-open entry is how debt clears). It is NOT a new feature story, so the advancement gate is
respected. `check_docs` CHECK J compares the on-deck starter against the first-OPEN bucket-A row by row
order and may surface a NON-blocking advisory; the binding fact is the RUNBOOK register (2.4R + 2.4S
🟡, gate ARMED). No feature story (4.7 included) may begin until 2.4S's recorded live PASS clears the
register.

### After 2.4S's recorded live pass (clears 2.4R too)
2.4S flips ✅, the linked 2.4R entry clears, the register empties, and the gate OPENS. The next pipe
work is then **Story 4.7**
(REJECT → destroy artifact + detonation chamber in Forensic; INCONCLUSIVE → hold) — the tied tier-14
sibling of 4.6 on the Phase-4-closure critical path (**4.4** depends on 4.3 + 4.7), which verifies a
Hub-signed `rejected` `decision.token.v1` OFFLINE the SAME way 4.6 verifies `accepted`. Its refreshed
handoff is at **[`../story-4.7-PROMPT.md`](../story-4.7-PROMPT.md)** + **[`../story-4.7-brief.md`](../story-4.7-brief.md)**. After 4.7, **4.4** (tier 16) closes Phase 4; **4.9** (RD-046, tier 15),
**4.8** (RD-044, tier 16), and **B.1** (F&H, tier 6) follow per the reorder. The `_NEW_WORK_STORY`
fixture is `4.4`.

### Carry-forward from the 2.2G build (apply at live validation + to 4.7)
- **gitleaks command shape:** `gitleaks dir <path> --report-format json --report-path /dev/stdout
  --no-banner --exit-code 1`. `detect` is DEPRECATED in gitleaks v8.19+ → use `dir`. Exit `0`=no
  leaks, `1`=leaks found (JSON on stdout — still a successful scan), `>1`=tool error. Pinned
  `GITLEAKS_VERSION=8.30.1`; the release asset filename drops the leading `v`
  (`gitleaks_8.30.1_linux_x64.tar.gz`) while the git tag keeps it (`v8.30.1`).
- **Contract v1.2 + Hub-first redeploy (deploy-gap class):** the summary contract bumped to v1.2
  (the `gitleaks` tool added to the enum). The Hub ingest gate pins `SUMMARY_CONTRACT_VERSION` and
  QUARANTINES a mismatch fail-closed, so `ZtieHubTrackingStack` MUST be redeployed to accept v1.2
  BEFORE the static lane emits it — verify the LIVE ingest env `SUMMARY_CONTRACT_VERSION=1.2` after
  the redeploy (never trust the green `UPDATE_COMPLETE`). Sibling of the 2.6 collected-kind + 4.6
  handoff-kind deploy-gaps.
- **Secrets redacted:** every gitleaks finding reuses `check_family=signature`, fixed
  `severity=high`, and the raw `Secret`/`Match` is REDACTED (never persisted, RD-009). The
  `REDACTED-OK` grep in the LIVE-RUNBOOK is a hard gate.
- **Supersession (Decision C):** the `ZTIE-SIG-SECRET-*` rules are GONE from `signatures.py`; a
  planted secret now yields a `gitleaks` finding, not a `ZTIE-SIG-SECRET-*` one. DANGEROUS/MALWARE
  (reverse-shell/EICAR/miner/`curl|sh`/`eval`) remain.

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
