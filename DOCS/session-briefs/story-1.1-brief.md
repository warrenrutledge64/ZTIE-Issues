# Session Brief — Story 1.1

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.

---

## Story 1.1 — Intake gateway endpoint (payload/artifact entry)

| Field | Value |
|-------|-------|
| **Phase** | P1 — Intake & Routing |
| **Date** | 2026-08-24 |
| **Status** | 🟡 In Progress (built; pending live validation) |
| **Builds from restore point** | none yet (first code story) |
| **Session goal** | Stand up the ZTIE intake gateway that accepts an incoming deployment payload / code artifact and persists it for processing, handing it off to the `preprocessor`. |

---

### Background & Context

ZTIE (Zero Trust Inspection Engine) is a four-phase security-analysis pipeline that
inspects every deployment payload/code artifact before it can reach production
(the PDE). No phase has been built yet — the repo held only the plan, runbook, and
methodology. This is the **first code story**: the front door of the pipeline. Every
downstream phase (classification, static/dynamic inspection, AI correlation,
verdict/handoff) depends on artifacts first being **accepted and durably persisted**
here.

### Objective & Value

- **Objective:** An AWS-native HTTP entry point (`POST /intake`) that accepts an
  incoming artifact plus metadata, persists the artifact body to S3, records a
  queryable intake record in DynamoDB (hub account) with `status=RECEIVED`, and
  returns a stable `intake_id` for tracking.
- **Why it matters:** Nothing can be classified, scanned, detonated, or gated until
  it has entered the pipeline and been persisted. This is the seam the `preprocessor`
  (Story 1.2) reads from. It also establishes the zero-trust posture at the edge:
  only authorized AWS principals can submit, and a submitted artifact starts life as
  `RECEIVED` — never "trusted" and never forwarded anywhere.

### Scope, Dependencies & Position

- **In scope:**
  - CDK v2 (TypeScript) infra stack: REST API Gateway (`POST /intake`, **IAM/SigV4
    auth**), intake Lambda, encrypted+versioned S3 artifact bucket (block-public),
    on-demand encrypted DynamoDB `ztie-intake` table.
  - Python 3.12 intake Lambda: request validation, `intake_id` (UUID) generation,
    SHA-256 of the artifact body, S3 put, DynamoDB put (`status=RECEIVED`), typed
    error responses (400 / 413 / 500 with correlation id).
  - Unit tests (pytest + moto at unit level only).
- **Out of scope (later stories):** artifact **classification** (1.2), **routing**
  to static/dynamic lanes (1.3), **safe-reject** of unknown/incompatible types
  (1.4). 1.1 accepts + stores only; it does not decide what the artifact *is*.
  No PDE path, no verdict, no inspection.
- **Depends on:** — (none; the hard advancement gate is satisfied).
- **Unblocks:** 1.2 (classifier has an artifact + record to inspect).
- **Roadmap position:** first story of Phase 1; the pipeline's entry point.

### Approach & Constraints

- **Approach:** API Gateway (REST, IAM auth) → intake Lambda → S3 (body) +
  DynamoDB (record). Return `201 { intake_id, status, received_at, sha256 }`.
- **Hard constraints (from PROJECT_PLAN.md):**
  - **No mocks in the execution path** — real API GW + Lambda + S3 + DynamoDB;
    moto is unit-test-level only (explicitly agreed).
  - **AWS-native** (API GW / Lambda / S3 / DynamoDB); GitHub is dev-only.
  - **Python-first** app code; infra in CDK v2 TypeScript (project convention).
  - **Multi-account topology** — DynamoDB in hub account **Pipeline-Hub
    (641628980935)** per RD-008.
  - **Zero trust** — artifact persisted as `RECEIVED`; never marked safe, never
    forwarded. IAM auth gates who can submit.

### Change & Rollback

- **Change type:** normal (first infra + code introduction).
- **Restore point this builds from:** none yet.
- **Backout plan:** revert the merged PR (`git revert -m 1 <merge-sha>` via a
  revert branch + PR); `cdk destroy` the intake stack to remove the live resources.

### Definition of Done / Validation Gate

> A pass/fail gate, not a description. The user validates live; the executor records
> the result; only a recorded pass flips the status.

- **Done means:** the user deploys the stack to the hub account, submits a sample
  artifact to `POST /intake` (SigV4-signed), and confirms **all** of:
  1. a `201` response carrying an `intake_id`, `status=RECEIVED`, and a `sha256`;
  2. the artifact body exists in the S3 bucket at the returned key;
  3. a DynamoDB item exists for that `intake_id` with `status=RECEIVED` and a
     `sha256` matching the response.
- **Validated by:** the user, live, on the hub account.
- **Validation Result:** _pending — awaiting the user's live deploy + submit._
- **On pass (and only then):** record the dated Validation Result line and flip the
  1.1 row 🟡 → ✅ in RUNBOOK.md (paired status commit).
- **On fail:** story stays 🟡; next session re-focuses on fixing + re-validating 1.1.
- **Advancement gate:** 1.1 had no dependencies; 1.2 cannot start until 1.1 is ✅.

### Risks & Watch-Items

- **INTEGRATIONS_ONLY** in the build sandbox → no AWS creds here; the executor
  builds + hands off, the user runs `cdk deploy` and validates live.
- **IAM/SigV4 validation** is slightly more involved than an unauthenticated hit —
  the handoff must include the exact SigV4-signed request sequence (awscurl or a
  signed CLI call), zero-guess.
- **Account targeting** — `cdk deploy` must target hub `641628980935`; confirm the
  active profile/account before deploying (state-your-context discipline).
- **Payload size** — API Gateway has a 10 MB request cap; the Lambda enforces a
  size limit and returns 413 rather than failing opaquely. Larger artifacts would
  need a presigned-S3-upload path (future story if needed).
- **RESTORE.md / BOM.md** still carry `{{PROJECT_NAME}}` and generic state-manifest
  sections (Day-0 step 4 not yet done) — out of scope for 1.1, but a watch-item
  before the first phase-close.

### Lessons Learned / Carry-Forward *(authored at the end of this session)*

- Filled in at session close — see the next-session prompt/brief.
