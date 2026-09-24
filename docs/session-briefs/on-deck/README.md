# On deck (the current next-session starter)

> This folder points at the ONE prompt to paste to start the next working session.
> It is kept to a single current pointer so there is never an ambiguous or stale
> starter here. For authoritative status and ordering, read `../../RUNBOOK.md`.

## Next session: DISPOSITION the Operational Debt Register to 0 open (the gate before Story 4.4)

> **Stakeholder gate (2026-09-24, PR #212):** the Operational Debt Register must read **0 open**
> BEFORE Story **4.4** (the Phase-4 closer) starts. So the immediate next work is NOT 4.4 — it is
> dispositioning the five open OD items (each by fix+live-validate OR a dated stakeholder
> accept/defer), then starting 4.4. See the RUNBOOK **Default next action** for the recommended
> per-item path. This gate is convention-enforced (check_docs does not gate on OD).

**Story 4.7 was VALIDATED LIVE + CLOSED ✅ 2026-09-24** — sealed PASS (Gemini, blind, RD-055) on the
clean final code (branch `feature/story-4.7`, commit `3e73f4b`), attested by Warren Rutledge, with the
RD-054 raw evidence retained in
**[`../../validation-evidence/4.7/attempt-1/EVIDENCE.md`](../../validation-evidence/4.7/attempt-1/EVIDENCE.md)**
(a verified `rejected` token destroyed intake `0c74042e-…` → all four Forensic prefixes `0/0`; a no-token
invoke HELD `08dd5caa-…`; the `disposition` outcome crossed Forensic→Hub `destroyed`/`hash_verified: true`/
`report_survives: true`; destroyer role NO `dynamodb`). A deploy-gap (the new `disposition` RD-013 kind
needed a `ZtieHubTrackingStack` redeploy) was found + closed during the run. The Validation Debt Register
is EMPTY; the advancement gate is DISARMED.

**Open OD items to disposition before 4.4** (recommended path in the RUNBOOK Default-next-action):
**OD-004** (restore-tag state manifests) → live manifest capture + `BOM.md` rows; **OD-009**
(post-ACCEPT cost bleed → Story 4.10/RD-059) → recommend accept/defer (hygiene follow-on, not on the
Phase-4 critical path); **OD-007** (wrapper smoke-test harness) + **OD-008** (SFN false-green, the two
2.4S standing flags) → decide fix-story-vs-defer now; **OD-005** (validation-UX VUX) → recommend
accept/defer (still accreting). Each closes with a dated note; a *fix* route enters the Validation Debt
Register + ARMS the gate until its own live pass, so "0 open before 4.4" means BOTH registers empty.

**Then Story 4.4 — the next pipe story and the Phase-4 CLOSER** (tier 16, deps 4.3 ✅ + 4.7 ✅). The SIGN
side of the authenticated-decision primitive: enable the 4.3 dashboard's DISABLED Approve/Reject surface
behind an authenticated Hub action, record the durable `human_decision` on the Hub tracking item, sign a
`decision.token.v1` (the H.2 KMS key), and deliver it one-directionally Hub→Forensic to drive **4.6**
(accept → push) / **4.7** (reject → destroy); INCONCLUSIVE issues no token (holds). Handoff:
**[`../story-4.4-PROMPT.md`](../story-4.4-PROMPT.md)** + **[`../story-4.4-brief.md`](../story-4.4-brief.md)**.
On 4.4's recorded live pass, **Phase 4 CLOSES** (capture the phase restore point). After 4.4: **4.9**
(tier 15, report enrichment), **4.8** (tier 16, dashboard browser auth), **B.1** (F&H tier 6) per the
recorded reorder.

**4.7 as-built (now ✅, for reference):** Forensic `lambdas/pde_reject/` (`handler.py` + PURE `reject.py`
+ thin `awsio.py` seam + vendored `lib/decision_auth`) + the `disposition.contract.v1` (11th RD-013 kind)
+ the `disposition` kind in `hub_ingest` + `ZtieForensicRejectStack` (Docker-bundled `cryptography`; role
s3 get/delete/list on the four intake prefixes + ec2 describe + tag-scoped terminate + sqs send; NO
`dynamodb`). Its LIVE-RUNBOOK: **[`../story-4.7-LIVE-RUNBOOK.md`](../story-4.7-LIVE-RUNBOOK.md)**.

**Carry-forward (apply to the 4.7 LIVE validation + 4.4 + every future live validation):**
- **⛔ Deploy code-asset gate is NON-SKIPPABLE** ([`../story-2.4R-DEPLOY-VERIFY.md`](../story-2.4R-DEPLOY-VERIFY.md)):
  before ANY live validation, grep the LIVE Lambda zip for the story's structural markers (NOT env vars,
  NOT a green `UPDATE_COMPLETE`) + a regression guard that any prior diagnostic/probe marker is ABSENT. A
  validation over an unverified/stale asset is INVALID. For 4.7 the markers are: `verify_decision` /
  `expected_decision="rejected"` / `HUB_PUBLIC_KEY_PEM` (token-verify), `destroy_intake_prefixes` /
  `DeleteMarkers` / `list_object_versions` (versioned-delete), `find_running_chamber` / `terminate_chamber`
  (chamber). The LIVE-RUNBOOK STEP 1a runs this gate.
- **Pass the Hub public key to CDK as SINGLE-LINE base64** (`-c hubPublicKeyPemBase64=$(base64 -w0 pub.pem)`,
  decoded by `bin/ztie-infra.ts`); a raw multi-line PEM truncates to a 27-byte header (the 4.6 defect, PR #153).
  After deploy, dump the live `HUB_PUBLIC_KEY_PEM` and confirm the FULL ~178-byte value.
- **REDEPLOY `ZtieHubTrackingStack` for the new `disposition` RD-013 kind** BEFORE the live run — the live
  `hub_ingest` validator quarantines an unknown kind until then (the 4.6 `handoff` deploy-gap). The
  LIVE-RUNBOOK STEP 1 sequences the Hub redeploy + a grep of the live ingest zip for `name="disposition"`.
- **FAIL-SAFE is the hardest invariant** — the LIVE-RUNBOOK STEP 5 proves destroy-only-on-verified-rejected
  from every angle (no token/bad sig/`accepted`/sha-mismatch/stale/untrusted → NO destroy; INCONCLUSIVE holds),
  each against a FRESH throwaway intake whose files must remain UNCHANGED after a refusal.
- **OD-004/OD-005/OD-007/OD-008** remain OPEN in the Operational Debt Register (non-blocking): OD-007 (offline
  wrapper smoke-test harness) + OD-008 (SFN false-green — a fork branch reporting `SUCCEEDED` over a failed
  launch/`execution_error`) are the durable-fix candidates for the offline-can't-catch-it class.

**How to run the live validation — split-brain (RD-052/RD-053/RD-055, the standing gate):** the code
under test is handed as a PR/commit ONLY; the **stakeholder** fetches the diff independently and states
the requirement; the **independent validator (Gemini)** authors the DoD + numbered live runbook blind
and adjudicates PASS/FAIL/INCONCLUSIVE; **Kiro authors no runbook and supplies no diff/fetch/snippet
(RD-055)**, and is write-only scribe at close-out. Template:
**[`../../GEMINI_VALIDATION_PACKAGE_TEMPLATE.md`](../../GEMINI_VALIDATION_PACKAGE_TEMPLATE.md)**. Operator
hygiene reference (NOT a runbook): **[`../../governance/cloudshell-hygiene.md`](../../governance/cloudshell-hygiene.md)**.

### Sequencing note (the gate is DISARMED — 4.7 ✅; 4.4 is the first-OPEN pipe story)
Story 4.7 was VALIDATED LIVE + CLOSED **✅** 2026-09-24 (sealed PASS, RD-055; RD-054 evidence retained),
so the Validation Debt Register is EMPTY and the advancement gate is **DISARMED** — new pipe feature work
may begin. With 4.3 (✅) + 4.7 (✅), **4.4** (tier 16) is the first-OPEN pipe story and the Phase-4 CLOSER.
After 4.4: **4.9** (RD-046, tier 15), **4.8** (RD-044, tier 16), and **B.1** (F&H, tier 6) per the recorded
reorder. The `_NEW_WORK_STORY` check-docs fixture was repointed `4.4`→`4.9` (4.4 is now the active
first-OPEN story; 4.9 is still ⬜).

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
OD-001 / OD-002 / OD-003 / OD-006 are closed. **OPEN (all informational; do NOT block feature work):
OD-004** — paired restore-point state manifests for `restore/phase-3-green` + `restore/story-4.5-green`
not captured yet (needs `scripts/ztie-restore` in Hub + Forensic + Pipeline-Sandbox). **OD-005** — the
validation-tooling UX (VUX) collection. **OD-007** — offline wrapper smoke-test harness. **OD-008** — SFN
false-green observability gap. **OD-009 (NEW 2026-09-24)** — post-ACCEPT Forensic cost bleed: on ACCEPT,
4.6 copies the artifact to the Sandbox and deletes NOTHING in Forensic, and the artifact bucket lifecycle
expires only NONCURRENT versions — so current `intake`/`findings`/`runs`/`traces` objects persist per
accepted detonation (unbounded S3 cost + blast-zone residue); scoped for **Story 4.10 (RD-059)** — a
post-accept sweep + a current-object lifecycle floor, keeping the VPC/buckets/roles/launch template.
Design watch-item (standing): a retired Forensic bucket had an unwanted 365-day COMPLIANCE Object Lock —
do NOT add COMPLIANCE-mode lock to any bucket (4.10's floor is plain lifecycle expiration only).
**Standing security action: rotate the leaked GitHub PAT (`ghp_…`) echoed in a `git fetch` this session.**

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
