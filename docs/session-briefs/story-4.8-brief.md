# Session Brief — Story 4.8 (dashboard browser authentication — Cognito)

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.
>
> **Story 4.8 is a Phase-4 enhancement off Story 4.3 (the dashboard render).** 4.3 stood
> up the dashboard + an **IAM/SigV4-authed** read API; a plain browser can't SigV4-sign, so
> loading live data in a browser was deliberately deferred. 4.8 adds an **Amazon Cognito**
> hosted-UI login + scoped temporary AWS credentials so the browser becomes a first-class
> caller — while KEEPING the API's IAM auth so the machine/SigV4 path stays untouched.

---

## Story 4.8 — Dashboard browser authentication (Cognito)

| Field | Value |
|-------|-------|
| **Phase** | P4 — Reporting & Handoff |
| **Build tier** | 16 — depends on `4.3` (tier 15); build tier = 1 + 15. It does NOT advance to a new dependency layer beyond 4.3 (its only dep). |
| **Date** | TBD (scoped 2026-09-13; not yet built) |
| **Status** | ⬜ Not Started. |
| **Depends on** | **4.3 ✅** (RD-043, the dashboard render + its IAM-auth read API `GET /dashboard` + `GET /status/{intake_id}`). |
| **Registered decision** | **RD-044** (proposed). |
| **Builds from restore point** | Branch the CODE off current `main` (which must contain merged + LIVE-VALIDATED 4.3). |
| **Session goal** | Give the human-facing dashboard a browser login: an Amazon Cognito **user pool** (hosted UI, OIDC) for authN + a Cognito **identity pool** that vends **scoped temporary AWS credentials** so the SPA **SigV4-signs** the 4.3 read API. **Retain** the API's `AWS_IAM` authorization (do NOT swap to a Cognito authorizer) so the machine/SigV4 + `awscurl` path is untouched. Per-SUBSCRIBER, org-shared (RD-028); no per-user partitioning. **Confirm the password/MFA policy + whether an enterprise IdP federation is in scope with the stakeholder before building.** |

---

### ⚠️ ADVANCEMENT GATE (read FIRST at STEP 0)

**4.8 is a NEW FEATURE story. It may begin ONLY if its Depends-on are ALL ✅ AND the
Validation Debt Register is EMPTY.** STEP 0 MUST re-confirm on `main`: `4.3` ✅ and the
register EMPTY (trust `main` + `check_docs`; if they disagree, `main` wins).

---

### ⚠️ SEQUENCING — 4.8 is an enhancement, NOT the Phase-4 critical path

4.8 depends on 4.3 but is INDEPENDENT of the pipeline-completing Phase-4 stories: **Story 4.4
still CLOSES Phase 4** (on 4.3 + 4.7), and 4.5 (report) / 4.6 (ACCEPT→PDE) / 4.7
(REJECT→destroy) complete the handoff. 4.8 is an **operator-UX enhancement** that can land any
time after 4.3 and is **LOWER priority** than 4.4/4.5/4.6/4.7 unless the stakeholder
reprioritizes. Per METHODOLOGY §5.A.0 the story to START is the first OPEN item in the RUNBOOK
"Ready now" schedule; confirm with the stakeholder and record any reorder in
`docs/governance/WORK_LOG.md`.

### Background & Context

The dashboard is the human-facing surface through which the zero-trust human gate is exercised.
Story 4.3 (RD-043) rendered `dashboard.contract.v1` behind an **IAM/SigV4** API Gateway — the
same zero-trust posture as the intake API — and validated the data path via `awscurl`. Because a
browser can't SigV4-sign without credentials, a plain browser load shows the dark-theme SPA shell
plus a bounded "could not load data (403)" notice (expected, not a bug). 4.8 provides the missing
browser identity.

### What This Story Is (nature + gate role)

**Nature: NEW FEATURE story — an operator-UX enhancement.** It adds the browser auth path on top
of 4.3. It does NOT change what the dashboard renders, does NOT change the payload, and does NOT
touch the human accept/reject ACTION (that is Story 4.4) or the advisory recommendation covenant
(RD-040). It only **authenticates** the human and lets the browser call the existing API.

### Objective & Value

- **Objective:** operators load the dashboard in a browser, log in via the Cognito hosted UI, and
  the fleet + per-intake views load with LIVE data (SigV4-signed calls succeed against the
  retained IAM-auth API).
- **Why it matters:** it makes the human gate usable in a browser without hand-signing requests —
  the last mile of the Phase-4 dashboard for real operators.

### Scope, Dependencies & Position

- **In scope:** a Cognito **user pool** (hosted UI, OIDC) for the human login (operators
  provisioned per SUBSCRIBER, org-shared, RD-028 — NO per-user filtering/IAM); a Cognito
  **identity pool** mapping an authenticated identity to a **least-privilege authenticated IAM
  role** holding EXACTLY `execute-api:Invoke` on EXACTLY the two dashboard GET methods; wiring the
  SPA to redirect to the hosted UI, capture the token, exchange it for temp creds, and SigV4-sign
  its `fetch` calls (replacing the current 403 fallback).
- **RETAIN, do NOT replace:** the 4.3 API keeps its `AWS_IAM` authorization. Do NOT swap it to a
  Cognito user-pool authorizer — that would break the SigV4/machine callers + the `awscurl`
  validation path, and couple the auth model to one client.
- **Out of scope / do NOT touch:** the dashboard render + payload (4.3 — consume as-is); the human
  accept/reject ACTION + routing (4.4/4.6/4.7); the report (4.5); an enterprise SAML/OIDC
  federation into the user pool (a future opt-in). **ServiceNow OUT OF SCOPE.**
- **Depends on:** **4.3 ✅**. **Blocks:** nothing on the Phase-4 critical path (4.4 closes Phase 4
  independently).

### Approach & Constraints

- **AWS-native** (Cognito + API Gateway + IAM); no external IdP required for the core.
- **Least privilege:** the authenticated role is scoped to exactly the two dashboard GET methods —
  nothing else.
- **Boundary intact:** Hub-SIDE only (RD-009) — the browser still consumes only the derived
  payload (never raw artifact/findings/trace); nothing new crosses the RD-013 gate; HTTPS-only;
  no durable store (RD-012). Advisory/human-gate covenant unchanged (RD-040).
- **Stakeholder decisions to confirm at STEP 0:** the password policy + MFA posture +
  account-recovery flow; whether an enterprise IdP federation is in scope now (default: deferred);
  the hosted-UI domain/branding.
- Docs first-class (RD-015), PR-reviewed.

### Validation Rationale & Compliance Mapping (REQUIRED — RD-014)

- **Rationale:** operators need a browser identity to exercise the human gate; a Cognito user pool
  + identity pool gives the browser a SigV4-capable identity while retaining the API's IAM auth
  (machine path untouched, one authorization model).
- **Candidate control mappings** *(proposed; ratified on review):*

| Framework | Control ID | Control Name | Rationale | Status |
|-----------|-----------|--------------|-----------|--------|
| NIST 800-53 r5 | IA-2 | Identification & Authentication (Organizational Users) | Cognito user-pool login of operators | Proposed |
| NIST 800-53 r5 | IA-8 | Identification & Authentication (hosted login) | Hosted-UI OIDC sign-in | Proposed |
| NIST 800-53 r5 | AC-3 | Access Enforcement | Scoped `execute-api:Invoke` gates API access | Proposed |
| NIST 800-53 r5 | AC-6 | Least Privilege | Authenticated role scoped to the two GET methods | Proposed |
| NIST 800-53 r5 | SC-8 | Transmission Confidentiality/Integrity | HTTPS + SigV4 | Proposed |
| NIST CSF | PR.AC-1 | Identities & credentials managed | Cognito-managed identities | Proposed |
| NIST CSF | PR.AC-7 | Users authenticated | Login required to load live data | Proposed |
| ISO 27001:2022 | A.8.5 | Secure authentication | Hosted-UI auth + MFA posture | Proposed |
| ISO 27001:2022 | A.5.15 | Access control | Per-subscriber, least-privilege access | Proposed |

### Management-Artifact Obligations (REQUIRED — RD-015)

- [ ] Story's brief + runbook entry updated (status, Validation Result, dates).
- [ ] PROJECT_PLAN and RUNBOOK in exact alignment (4.8 identical in both).
- [ ] RD-044 plan-table row present BEFORE any living-doc reference (CHECK E is literal). _(Done at scoping, 2026-09-13.)_
- [ ] All doc changes PR-reviewed (branch + PR, never straight to main).
- [ ] On build: repoint the `check_docs` `_NEW_WORK_STORY` fixture as needed IN THE SAME PR.
- [ ] On validation pass: record Validation Result + flip ✅ (paired commit).
- [ ] Author the next-story handoff with real Lessons Learned.

### Definition of Done / Validation Gate

- **Done means:** an operator loads the dashboard in a browser, logs in via the Cognito hosted UI,
  and the fleet + per-intake views load with LIVE data (SigV4-signed calls succeed against the
  retained IAM-auth API); a signed-out / unauthorized browser is denied; the machine/SigV4
  (`awscurl`) path still works unchanged; per-subscriber scope holds (no per-user filtering);
  validated live + recorded.
- **Validation Result:** `pending` (scoping entry — not yet built).
- **On pass:** record dated result, flip 4.8 ✅ (paired commit), keep PLAN ↔ RUNBOOK aligned.
- **On fail:** 4.8 stays 🟡 (added to the register in the same commit); fix + re-validate.

### Risks & Watch-Items

- **ADVANCEMENT GATE:** 4.3 must be ✅ (it is, 2026-09-13) and the register EMPTY.
- **RETAIN IAM auth — do NOT swap to a Cognito authorizer** (would break the SigV4/machine path +
  the `awscurl` validation). Additive only.
- **Least privilege:** scope the authenticated role to exactly the two GET methods.
- **Tenant model (RD-028):** per-subscriber, org-shared; no per-user partitioning.
- **Human gate unchanged (RD-040):** 4.8 authenticates; the accept/reject ACTION is 4.4.
- **Carry-forward from 4.3 (the API-Gateway ↔ direct-invoke contract):** the 4.1/4.2 read Lambdas
  return a BARE payload (not a proxy envelope); the 4.3 API uses a NON-PROXY integration. 4.8 must
  not regress that — it changes only WHO may call the API (auth), not the integration shape.

### Lessons Learned / Carry-Forward (from the 4.3 build + LIVE validation)

- **The deferred-auth gap 4.8 closes:** 4.3's API is IAM/SigV4; a browser can't sign, so live data
  in a browser was deferred and validated via `awscurl`. 4.8 supplies the browser identity.
- **API Gateway ↔ direct-invoke Lambda contract:** the read Lambdas return a bare payload; the 4.3
  API is a NON-PROXY integration (a `proxy: true` integration 502s "Malformed Lambda proxy
  response"). Do not touch the integration shape — 4.8 is auth-only.
- **Two accounts / two tabs; `aws sts get-caller-identity` before every block.** The dashboard +
  API + Cognito live in the **Hub** (641628980935).
- **Offline tooling:** `~/.pyenv/versions/3.12.13/bin/python3 -m unittest` (pytest NOT installed);
  `~/.pyenv/versions/3.12.13/bin/ruff check`; `env -u NODE_OPTIONS npx tsc --noEmit` (confirm NO
  new error TYPE); `env -u NODE_OPTIONS npx prettier --write`. `gh pr create` is BROKEN — open PRs
  via `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`.

> **Sequencing note:** 4.8 follows 4.3 by dependency but is an enhancement, not the Phase-4
> critical path (4.4 closes Phase 4). Confirm priority + the auth policy details with the
> stakeholder at STEP 0.
