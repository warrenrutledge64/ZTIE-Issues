# Session Brief — Story 1.1R

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.

---

## Story 1.1R — Remediation: durable tracking record Forensic → Hub, behind the data-contract gate

| Field | Value |
|-------|-------|
| **Phase** | P1 — Intake & Routing |
| **Date** | 2026-08-24 |
| **Status** | 🟡 In Progress — built + locally verified (compile/lint/format); **pending live two-account validation** |
| **Builds from restore point** | none yet (Phase 1 not yet closed; no `restore/phase-1-green`) |
| **Session goal** | Move the authoritative, durable intake/tracking record out of the Forensic blast zone into the Hub, behind an enforced RD-013 data-contract gate, so Forensic holds only ephemeral state. |

---

### Background & Context

ZTIE inspects untrusted artifacts in the **Forensic** account (the blast zone) and
keeps its brains/control plane in the **Hub** account. Story 1.1 stood up the intake
gateway but placed the **durable intake DynamoDB record in Forensic** — which
pre-dates decisions **RD-012** (no durable store in the blast zone) and **RD-013**
(the Forensic→Hub crossing must be an enforced data contract). Per the covenant, 1.1
stays ✅ for what it validated; 1.1R **remediates forward**: it relocates the durable
record to the Hub and installs the contract gate. This is the last correctness fix
before the Phase-1 restore mechanism (1.R) and the classifier (1.2).

### Objective & Value

- **Objective:** The durable tracking record lives in a **Hub** DynamoDB table,
  written **only** by a **Hub-owned validating ingestion gate**. Forensic keeps only
  ephemeral state (the raw artifact S3 body) and can reach the Hub through exactly
  one least-privilege, one-directional door.
- **Why it matters:** It removes a durable, stateful attack surface from the
  disposable blast zone, guarantees the audit record survives a Forensic
  nuke/rebuild, and closes the single most dangerous path in the system (a pipe out
  of where untrusted code runs into the account that manages everything) behind a
  strict, fail-closed contract.

### Scope, Dependencies & Position

- **In scope:**
  - The data contract: `schemas/intake-tracking.contract.v1.json` (draft-07,
    allow-list, `additionalProperties:false` at every level, typed + length-capped,
    `contract_version`/`status` enum-pinned, `intake_id`/`sha256` pattern-locked, **no
    payload/executable field**) + `schemas/README.md` design note.
  - `ZtieHubTrackingStack` (Hub account 641628980935): durable tracking DynamoDB
    (GSI on status), the **ingest SQS queue** + **DLQ**, the **validator Lambda**,
    and the **quarantine S3 bucket**. The queue resource policy grants **only**
    `sqs:SendMessage` to the Forensic intake role.
  - `lambdas/hub_ingest/handler.py`: the Hub validating gate — validate → PASS
    upsert-by-`intake_id` (idempotent, non-clobbering) → FAIL quarantine
    (fail-closed); partial-batch failures only for genuinely unprocessable messages.
  - Repointed Forensic intake: **removed** the durable DynamoDB; `handler.py` now
    stores the raw body to S3 and emits the **derived contract envelope** to the Hub
    ingest queue.
  - Unit tests for both lambdas (pytest + moto, unit-level only) incl. the
    fail-closed rejection suite.
- **Out of scope:** the classifier (1.2), routing (1.3), safe-reject (1.4), the
  restore tooling (1.R), the dashboard render-escaping *implementation* (the contract
  notes the requirement; the dashboard is Phase 4). PDE/other accounts.
- **Depends on:** 1.1 ✅ (advancement gate satisfied).
- **Unblocks:** cleanly, 1.R (captures the final Forensic→Hub topology) and the
  Phase-2 work that consumes the tracking record.
- **Roadmap position:** Phase 1 remediation; makes the intake seam RD-012/013-correct.

### Approach & Constraints

- **Approach:** Forensic intake Lambda → `sqs:SendMessage` (one-directional,
  least-privilege) → Hub ingest SQS queue → Hub validator Lambda → (PASS) Hub
  tracking DynamoDB upsert / (FAIL) Hub quarantine S3. DLQ for unprocessable
  messages. Verdict is Hub-owned and never imported.
- **Hard constraints (from PROJECT_PLAN.md):** RD-012 (no durable store in
  Forensic), RD-013 (enforced exit data contract, fail-closed, Hub-owned gate,
  least-privilege one-directional, integrity-keyed, verdict-never-imported), RD-016
  (the concrete SQS/validator/quarantine implementation). No mocks in the execution
  path (moto unit-level only). AWS-native; CDK v2 TS infra + Python 3.12. Python-first.

### Validation Rationale & Compliance Mapping (REQUIRED — RD-014)

- **Rationale:** This story hardens the highest-risk trust boundary in ZTIE and
  relocates the durable audit record to a survivable location. It is a
  security-posture story first.
- **Candidate control mappings** *(candidate-until-ratified; also recorded in
  [`../COMPLIANCE.md`](../COMPLIANCE.md)):*

| Framework | Control ID | Control Name | Rationale | Status |
|-----------|-----------|--------------|-----------|--------|
| NIST 800-53 r5 | SI-10 | Information Input Validation | The Hub gate validates all crossing data against an allow-list schema, fail-closed | Proposed |
| NIST 800-53 r5 | SC-7 | Boundary Protection | Controlled, single access point out of the blast zone into the control plane | Proposed |
| NIST 800-53 r5 | AC-6 | Least Privilege | Forensic holds only `sqs:SendMessage` on one queue; no access to Hub data stores | Proposed |
| NIST 800-53 r5 | AU-9 | Protection of Audit Information | Durable record lives in the Hub, out of the disposable blast zone | Proposed |
| ISO 27001:2022 | A.8.26 | Application security requirements | Enforced input contract at the boundary | Proposed |
| ISO 27001:2022 | A.5.15 | Access control | Single least-privilege access point | Proposed |

- **Audit evidence produced:** the contract schema (versioned), the quarantine
  bucket (rejected-crossing evidence), the Hub tracking table (durable record), and
  the CloudFormation stacks/outputs.

### Management-Artifact Obligations (REQUIRED — RD-015)

- [x] Story's **brief + runbook entry** updated (this brief; RUNBOOK 1.1R detail +
      summary row set 🟡, enriched with the as-built RD-016 design).
- [x] **PROJECT_PLAN and RUNBOOK in exact alignment** (1.1R line updated in both;
      RD-016 registered in the plan's decisions table).
- [x] **New registered decision (RD-016)** recorded in the plan; **candidate control
      mappings** added to `COMPLIANCE.md` and this brief (RD-014).
- [x] All doc changes **PR-reviewed** (branch `feature/story-1.1R`, PR — never
      straight to main).
- [ ] Governance kept **restorable** — the restore manifest will pin these
      governance-doc commits once story **1.R** builds the restore mechanism
      (coordinated there; nothing to pin yet in Phase 1).

### Change & Rollback

- **Change type:** normal (adds a Hub stack; modifies the Forensic intake stack +
  handler; adds a new Lambda + contract + tests).
- **Restore point this builds from:** none yet.
- **Backout plan:** revert the merged PR (`git revert -m 1 <merge-sha>` via a revert
  branch + PR). Live: `cdk destroy ZtieHubTrackingStack` (Hub) and re-deploy the
  prior Forensic intake stack (which re-creates its own DynamoDB) — but note the
  intended forward state has **no** durable table in Forensic.

### Definition of Done / Validation Gate

> Pass/fail gate. The user validates live across **both** accounts; the executor
> records the result; only a recorded pass flips the status.

- **Done means:** on real AWS, the user confirms **all** of:
  1. a Forensic intake produces a **contract-valid** record that lands in the **Hub**
     tracking table via the gate (durable record now in the Hub, not Forensic);
  2. a deliberately **malformed / oversized / injection-crafted** record is
     **REJECTED (fail-closed)** and quarantined — never written to the live Hub table;
  3. the Forensic intake stack has **no durable DynamoDB table**, and the Forensic
     principal has **no direct write** permission on the Hub table (least-privilege);
  4. the **raw artifact still persists to Forensic S3** as `application/octet-stream`.
- **Validated by:** the user, live, across Forensic (360999005254) + Hub (641628980935).
- **Validation Result:** _pending — see the four checks above._
- **On pass (and only then):** record the dated Validation Result line and flip the
  1.1R row 🟡 → ✅ in RUNBOOK.md (paired status commit).
- **On fail:** story stays 🟡; the next session re-focuses on fixing + re-validating 1.1R.
- **Advancement gate:** 1.1R depended on 1.1 ✅; it should land before Phase 2 builds
  on the tracking record. It does not itself close Phase 1 (that is 1.R + the P1 gate).

### Two-account deploy + validation runbook (for CloudShell)

> INTEGRATIONS_ONLY build sandbox: the code is built + handed off; **you** deploy and
> validate live. State the account banner before every block. Region us-east-1.

**Prereqs (once):** `cd infra && npm ci`. Both accounts CDK-bootstrapped.

**Step 1 — Hub account (641628980935): deploy the tracking stack + gate FIRST.**
```bash
# BANNER: Hub / Pipeline-Hub 641628980935 / us-east-1  (aws sts get-caller-identity)
cd infra
npx cdk deploy ZtieHubTrackingStack --require-approval never
# Capture outputs:
#   IngestQueueUrl, IngestQueueArn, TrackingTableName, QuarantineBucketName, IngestDlqUrl
```

**Step 2 — Forensic account (360999005254): deploy intake wired to the Hub queue.**
```bash
# BANNER: Forensic 360999005254 / us-east-1
cd infra
npx cdk deploy ZtieIntakeStack --require-approval never \
  -c hubIngestQueueUrl="<IngestQueueUrl from step 1>" \
  -c hubIngestQueueArn="<IngestQueueArn from step 1>"
# Capture output IntakeHandlerRoleArn.
```

**Step 3 (recommended) — tighten the send grant to the exact role.**
```bash
# BANNER: Hub 641628980935
npx cdk deploy ZtieHubTrackingStack --require-approval never \
  -c forensicIntakeRoleArn="<IntakeHandlerRoleArn from step 2>"
```

**Step 4 — validate the four DoD checks.**
```bash
# (1) VALID crossing — BANNER: Forensic. Signed POST /intake (awscurl / SigV4) with a
#     small artifact. Then BANNER: Hub — confirm the item appears in TrackingTable
#     (aws dynamodb get-item --key intake_id=<id>) with status=RECEIVED + matching sha256.
# (2) FAIL-CLOSED — BANNER: Forensic. Send a hand-crafted MALFORMED envelope directly
#     to the ingest queue (aws sqs send-message) — e.g. extra field / bad sha / wrong
#     contract_version / status=PASS. Then BANNER: Hub — confirm NO new TrackingTable
#     item AND a new object under s3://<QuarantineBucketName>/quarantine/...
# (3) NO durable table in Forensic — BANNER: Forensic. Confirm ZtieIntakeStack has no
#     DynamoDB table (aws cloudformation list-stack-resources) and the intake role
#     policy grants only sqs:SendMessage on the one queue (no dynamodb:* on the Hub table).
# (4) Raw body — BANNER: Forensic. aws s3api head-object on the returned key shows
#     ContentType=application/octet-stream.
```

### Risks & Watch-Items

- **`jsonschema` must be bundled** into the validator Lambda (not in the runtime).
  The Hub stack uses CDK asset **bundling** (local `python3 -m pip install -t`, Docker
  fallback). If local bundling is used in CloudShell, ensure `python3`/`pip` are
  present; otherwise Docker must be available. **Watch:** a validator that imports
  `jsonschema` but wasn't bundled will fail at cold start.
- **Cross-account CDK:** the two stacks deploy separately with separate creds; the
  wiring is via `-c` context (queue URL/ARN). Deploy **Hub first**.
- **SQS visibility timeout ≥ Lambda timeout** (60s ≥ 30s) — already set; don't lower.
- **Contract copy sync:** `schemas/…v1.json` and the bundled
  `lambdas/hub_ingest/…v1.json` must stay byte-identical (a G-2 checker will enforce;
  for now, re-copy on edit).
- **Fail-closed proof needs a raw send:** the intake Lambda only ever emits *valid*
  envelopes, so the malformed-record test must inject directly to the SQS queue
  (that is the real attacker model: anything that can reach the door).
- **Free private repo:** branch protection is not GitHub-enforced (PR-only is by
  convention). Merge is the user's call.

### Lessons Learned / Carry-Forward *(authored at the end of the build session, 2026-08-24)*

- **What went well:**
  - Clean STEP-0 base: 1.1 ✅, all prior PRs merged, no main/PR drift. RD-012/013
    were already ratified, so the design was fully specified going in.
  - The contract-first approach paid off: writing the JSON Schema first made the
    validator, the envelope builder, and the rejection tests fall out naturally.
  - Local guardrails available even offline: `py_compile` + `ruff` (via
    `~/.pyenv/versions/3.12.13/bin/ruff`) + `prettier` (`npx --no-install`, after
    `unset NODE_OPTIONS`) all pass.
- **What went wrong / surprised us:**
  - Sandbox is **INTEGRATIONS_ONLY**: **PyPI and npm are blocked**, so `pytest`/`moto`/
    `jsonschema` and `cdk synth`/`tsc` **cannot run here**. Local proof is limited to
    compile/lint/format + a stdlib schema structural check. The USER runs the real
    tests + two-account deploy. Do NOT claim tests/synth pass from the sandbox.
  - `fs_write` refuses to write a JSON file containing a remote `$schema` URL — the
    contract had to be written via a `python json.dump` step (documented; harmless).
- **Current true state:**
  - Code on branch `feature/story-1.1R` (PR opened). **Nothing is deployed live.**
    `main` unchanged. RUNBOOK 1.1R is **🟡** (correctly NOT flipped — no live pass yet).
  - The Forensic intake stack now has **no** durable DynamoDB in code; the durable
    record moves to the Hub only once **both** stacks are deployed live.
- **Must-know / must-avoid for the validation session:**
  - Deploy **Hub first**, then Forensic with the Hub queue URL/ARN via `-c` context.
  - Prove fail-closed by sending a malformed envelope **directly to the SQS queue**
    (the intake Lambda never emits an invalid one).
  - The status flip 🟡 → ✅ rides a **separate small paired-commit** after the user's
    confirmed live pass — merging the PR does not make 1.1R done.
- **User notes:** _(open for the user)_
