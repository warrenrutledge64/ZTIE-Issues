# ZTIE Security Analysis Pipeline — Execution Runbook

> **Living progress ledger.** This runbook mirrors [`PROJECT_PLAN.md`](PROJECT_PLAN.md)
> but is execution-oriented: every story is a trackable item with dependencies,
> do-it steps, a validation check, and a completion marker. The plan is the
> *what/why*; this runbook is the *do-it-and-track-it*. **This file is the source
> of truth for story status** — and it carries the binding Validation &
> Advancement Gate below.
>
> **Ordering:** stories are sequenced by **dependency + reuse value** — do what
> unblocks or gets reused by the most downstream work first; pull genuine shared
> foundations forward and build them once. Validation gates are sacred: no phase
> is done without its live validation, and nothing builds on unproven ground.

## Architecture Flow (reference)

> Full narrative + named-program reference in [`DOCS/ARCHITECTURE.md`](DOCS/ARCHITECTURE.md);
> scope/decisions in [`PROJECT_PLAN.md`](PROJECT_PLAN.md). Named programs:
> `preprocessor` (P1), `accuracy` + `gap_analysis` (P3), `status retrieval` (P4).

```
=======================================================================
          ZTIE SECURITY ANALYSIS PIPELINE: ARCHITECTURE FLOW
=======================================================================

                       [Incoming Code/Payload]
                                  |
                                  v
+---------------------------------------------------------------------+
|                     PHASE 1: INTAKE & ROUTING                       |
| Program: `preprocessor` (Classifies extensions, routes accordingly) |
+---------------------------------------------------------------------+
                                  |
               +------------------+------------------+
               | (Concurrent Parallel Execution)     |
               v                                     v
+-----------------------------+       +-------------------------------+
|    PHASE 2: STATIC PATH     |       |    PHASE 2: DYNAMIC PATH      |
| Non-Executing Inspection    |       | Sandboxed Execution/Detonation|
| Tools: cfn-lint, cfn-guard, |       | Env: Ephemeral EC2            |
|        checkov, bandit      |       | Exec: Host-native SSM         |
| Focus: NIST/ISO Compliance, |       | Focus: Syscalls, Network,     |
|        SAST Vulnerabilities |       |        File Operations        |
+-----------------------------+       +-------------------------------+
|  Output: Static JSON Data   |       |  Output: Behavioral Telemetry |
+-----------------------------+       +-------------------------------+
               |                                     |
               +------------------+------------------+
                                  |
                                  v
+---------------------------------------------------------------------+
|               PHASE 3: AI CORRELATION & ASSESSMENT                  |
| Engine: Amazon Nova Pro                                             |
| Programs: `accuracy`, `gap_analysis`                                |
| Action: Cross-references static findings with dynamic behavior to   |
|         eliminate false positives and generate unified threat score.|
+---------------------------------------------------------------------+
                                  |
                                  v
+---------------------------------------------------------------------+
|                  PHASE 4: HANDOFF & REPORTING                       |
| Program: `status retrieval`                                         |
| Action: Transforms insights into final multi-format reporting.      |
+---------------------------------------------------------------------+
                                  |
                 +----------------+----------------+
                 |                                 |
                 v                                 v
        [JSON Dashboard Data]                 [PDF Report]
                 |
                 v
        (If Verified Safe)
                 |
                 v
+---------------------------------------------------------------------+
|               DOWNSTREAM DEPLOYMENT (Invariant Gate)                |
| Target: Platform Delivery Engine (PDE)                              |
+---------------------------------------------------------------------+
```

> **Enforcement (human accept/reject in the Hub):** the raw artifact stays in
> **Forensic** until a human reviews ZTIE's findings in the Hub. **ACCEPT** → ZTIE
> pushes the hash-verified artifact Forensic → Pipeline-Sandbox (the ZTIE→PDE
> handoff; on landing it is under PDE control and ZTIE's job ends). **REJECT** →
> ZTIE destroys the artifact **and** its detonation chamber in Forensic.
> **INCONCLUSIVE** → hold at the human approval gate. ZTIE performs security
> clearance only and never re-executes the artifact outside Forensic.
> Detonation uses **ephemeral** EC2 (host-native SSM, no Docker) — never
> "temporary." Three-account topology: **Pipeline-Hub 641628980935** (brains /
> control plane), **Forensic 360999005254** (ZTIE self-contained + blast
> containment), **Pipeline-Sandbox 586917955591** (ZTIE→PDE handoff). ServiceNow
> is out of scope. (Full detail: DOCS/ARCHITECTURE.md, PROJECT_PLAN.md RD-008–011.)

## Status Legend

`⬜ Not Started` · `🟡 In Progress` · `⛔ Blocked` · `✅ Done (validated)`

## Validation & Advancement Gate (BINDING)

> The **enforced state machine** for every story and phase. Validation results —
> recorded, live, confirmed — **drive** status changes and **dictate** whether work
> advances. Status is never set on inference; advancement is never taken on faith.

**Roles.** The **validator** (usually the user, on the live system) runs the check
and confirms the outcome; the **executor records** the result (outcome + date) in
the story's *Validation Result* field and only then changes the status. The
executor never self-certifies a story done.

**Story state machine.** A story moves only on a recorded validation result:

| From | Event | To |
|------|-------|----|
| ⬜ Not Started | work begins | 🟡 In Progress |
| 🟡 In Progress | validation **passes** (recorded, confirmed) | ✅ Done (validated) |
| 🟡 In Progress | validation **fails / incomplete** | 🟡 stays (or ⛔ if externally blocked) |
| ✅ Done | (never auto-reverts; a regression opens a new remediation story) | — |

- **No result → no ✅.** Absent a recorded, confirmed pass, a story stays 🟡.
- **Fail → no advancement.** If a story fails or is only partly validated, **stay
  on that story** until it passes. The next session's objective becomes *fix +
  re-validate this story* — not the next one. Mark **⛔ Blocked** only when
  something external prevents progress; otherwise it stays 🟡 and in-focus.
- **The covenant is not to be circumvented.** "How do we get around validation?" is
  a **drift signal**, not a plan. Reworking a 🟡 story (including fixing a defect
  found after build) is normal in-progress work — it never justifies bypassing the
  gate or flipping status on inference. Only a recorded live pass of the **final**
  code earns ✅; when a defect is found pre-validation, **fix-then-validate-once**.
  (Full principle: `METHODOLOGY.md` §4, hard rule 3.)

**Hard advancement gate.** A story **cannot begin** until **every** story in its
`Depends on` column is ✅. If a dependency is not ✅, the executor does **not**
start the dependent story's work. (No override.)

**Phase gate.** A phase closes **only** when its end-of-phase gate returns a
recorded, confirmed pass. On phase-close — and not before:
1. capture the restore point (see [`RESTORE.md`](RESTORE.md)),
2. record it in [`BOM.md`](BOM.md),
3. set the phase row in the Progress Summary to ✅.

**Per-session handshake (enforced by the prompt template).** Every session, before
new work:
1. **Close out the prior story:** if it is 🟡 pending validation, obtain the
   result → on pass, record it + flip ✅ (+ Completed date); on fail, keep 🟡 and
   re-focus on it.
2. **Check the advancement gate:** confirm this story's `Depends on` are all ✅; if
   not, stop and surface the blocker.

**Recording a result.** Each story tracks a *Validation Result* — a one-line dated
record (`pass — <what was checked>, <date>, confirmed by <who>` or
`FAIL — <what failed>, <date>`). This line is the auditable driver behind the
status marker; the marker without a recorded result is not a valid ✅.

## Story Close-Out Procedure (how the ledger stays current)

> There is **no hook, CI job, or script** that mutates this file. The ledger is
> kept current by the **executor, by hand, as a mandatory step of closing a story**
> — enforced by the gate above. These are the exact edits and the commit
> convention.

**The paired-commit convention.** Work and status are **separate commits**:
- **Commit A — the work.** Build the story, push to a branch, open a PR. The story
  **stays 🟡** — merging code does not make it done.
- **Commit B — the status flip.** Only after the user confirms a **live pass**, make
  a **small, dedicated commit** that touches the runbook (and, at a phase close,
  the inventory + tag). Status flips ride small, fast-merging PRs so the ledger on
  the main line never lies. If a flip and the main line disagree, the main line
  wins — reconcile by merging the recorded flip.

**On a confirmed pass, edit exactly these three things in this runbook:**
1. **Summary-table row** — change the story's status cell 🟡 → ✅ and fill the
   **Completed** date.
2. **Detail-block header** — change the story's detail heading from
   `🟡 In Progress` to `✅ Done (validated)`.
3. **`Validation Result:` line** — replace the `pending` text with a dated,
   one-line record quoting *what the user actually checked live*
   (`pass — <what was checked>, <date>, confirmed by <who>`).

**On a fail / incomplete:** change nothing to ✅. Keep the row 🟡 (or ⛔ if
externally blocked), and record the failure in the `Validation Result` line
(`FAIL — <what failed>, <date>`). The next session re-focuses on this story.

**If the story closes a phase (and only on a recorded pass):** additionally
1. create the annotated `restore/phase-<N>-green` tag at the validated commit (see
   [`RESTORE.md`](RESTORE.md)),
2. add the restore-point row to [`BOM.md`](BOM.md) (tag + SHA +
   manifest path),
3. flip the **phase row** in the Progress Summary to ✅.

**Then — the warm handoff (mandatory).** Author the NEXT story's brief + prompt
under `session-briefs/`, including a `Lessons Learned / Carry-Forward` section with
THIS session's actual lessons. A close-out without the next handoff is incomplete.

## Progress Summary

| Phase | Scope | Gate | Status |
|-------|-------|------|--------|
| **P1 — Intake & Routing** | Intake gateway + preprocessor classifier/router (+ 1.1R record→Hub, 1.R restore mechanism) | Representative artifacts route to correct lanes; unknown types safe-rejected; **restore mechanism (1.R) passes a live capture→change→restore test so `restore/phase-1-green` can be captured** | ⬜ Not Started |
| **P2 — Parallel Inspection** | Static (cfn-lint/cfn-guard/checkov/bandit) + Dynamic detonation (ephemeral EC2 + SSM), run concurrently | Known-bad artifact yields both static findings + real behavioral telemetry; EC2 torn down | ⬜ Not Started |
| **P3 — AI Correlation** | Nova Pro correlation → unified threat score, findings, remediations, verdict | Paired static+dynamic inputs yield one score + correlated findings; a false positive is reconciled | ⬜ Not Started |
| **P4 — Handoff & Reporting** | Status-retrieval → dashboard JSON + PDF; PASS→PDE / FAIL→nuke / INCONCLUSIVE→approval gate | Full run produces tiered outputs and correct verdict-driven routing incl. human approve/reject | ⬜ Not Started |

---

## Phase P1 — Intake and Routing

_Gate: feed an IaC template, a raw script, and an unknown/unroutable artifact through the intake gateway; confirm each known type is classified and routed to the correct downstream lane, and the unknown type is safe-rejected (not crashed)._

| Story | Title | Depends on | Status | Completed | Restore tag |
|-------|-------|-----------|--------|-----------|-------------|
| 1.1 | Intake gateway endpoint (payload/artifact entry) | — | ✅ | 2026-08-24 | |
| 1.1R | Remediation: move durable tracking record Forensic → Hub behind the data-contract gate (RD-012/013/016) | 1.1 | ✅ | 2026-08-25 | |
| 1.R | Restore-point mechanism: state-capture + coordinated restore; fill RESTORE.md + BOM.md (prerequisite for the P1 close) | 1.1R | ✅ | 2026-08-25 | |
| 1.2 | Preprocessor classifier (extension + metadata inspection) | 1.1 | ✅ | 2026-08-25 | |
| 1.3 | Routing table → static & dynamic lanes | 1.2 | ✅ | 2026-08-27 | |
| 1.4 | Safe-reject path for unknown/incompatible types | 1.2 | 🟡 | | |

**1.1 — Intake gateway endpoint**  ✅ _Done (validated)_
- Steps: stand up the ZTIE intake gateway that accepts an incoming deployment payload / code artifact and hands it to the preprocessor. Built as API Gateway (POST /intake, IAM/SigV4 auth) → Python 3.12 Lambda → encrypted/versioned/block-public S3 (raw body) + on-demand encrypted DynamoDB (intake record, status=RECEIVED). Deployed self-contained in **Forensic 360999005254** per RD-008/009; the untrusted body is stored as `application/octet-stream` (claimed type kept as metadata only).
- **Validation Result:** pass — live on Forensic 360999005254 (2026-08-24), confirmed by the user: signed POST /intake returned 201 with intake_id=62360e03-dfb1-4655-ac52-2a55345ab6f0, status=RECEIVED, sha256=5563154a…ea57; S3 head-object showed ContentType=application/octet-stream + claimed=text/yaml + matching sha; DynamoDB item showed status=RECEIVED + matching sha256; an unsigned POST returned 403 (zero-trust auth gates).
- **Advancement gate:** ✅ — unblocks 1.2 (preprocessor classifier).
- **Known deviation (remediation queued as 1.1R):** 1.1 placed the durable intake DynamoDB table in **Forensic**, which pre-dates RD-012/013. Per the covenant, 1.1 stays ✅ for what it validated (intake accepts + persists; mechanism works); the account placement is remediated forward by story **1.1R**, not by retro-editing 1.1.

**1.1R — Remediation: durable tracking record → Hub, behind the data-contract gate**  ✅ _Done (validated)_
- Steps: move the **authoritative, durable** intake/tracking/verdict record out of Forensic into the **Hub** (DynamoDB) per RD-012. Leave Forensic holding only ephemeral state — the raw artifact (S3) + transient per-run state; no durable store in Forensic. Establish the **RD-013 data-contract boundary**: a Hub-owned validating ingestion gate (Forensic gets NO direct write to Hub data), a strict bounded allow-list schema (derived fields only, typed, length-capped, size/nesting bounded, no payload/executable field), **fail-closed** quarantine of non-conforming records, one-directional least-privilege crossing, integrity-keyed by intake_id + sha256 (upsert, no cross-record writes). The **verdict is decided Hub-side by the human gate — never imported** from crossed data; the dashboard **escapes crossed data on render**.
- **As built (RD-016):** concrete implementation = a Hub-owned **cross-account SQS ingest queue** (Forensic intake role granted **only** `sqs:SendMessage` on that one queue) → a **Hub validator Lambda** that enforces `schemas/intake-tracking.contract.v1.json` (draft-07 allow-list, `additionalProperties:false` everywhere, `contract_version`/`status` enum-pinned, `intake_id`/`sha256` pattern-locked, all strings capped, **no payload field**) → **PASS** upserts (idempotently, by `intake_id`, non-clobbering vs a Hub verdict) into the **Hub tracking DynamoDB**; **FAIL** writes the raw envelope to a **Hub quarantine S3 bucket** (never the live table); unprocessable messages redrive to a **DLQ**. New CDK stack `ZtieHubTrackingStack` (Hub account); the Forensic intake stack **no longer has a durable DynamoDB** and only emits the derived envelope. Two-account deploy: **Hub stack first**, then the Forensic intake stack wired with the Hub queue URL/ARN (see the 1.1R brief for the exact commands).
- **Validation Result:** pass — live across Forensic (360999005254) + Hub (641628980935), 2026-08-25, confirmed by the user. (1) A SigV4-signed `POST /intake` in Forensic returned 201 (intake_id `bea12db4-…-a5693be3b5a2`, sha256 `7db268c3…03b781`); the Hub validator Lambda ran clean and the record landed in the **Hub** tracking table with status=RECEIVED, matching sha256, `hub_ingested_at` + `origin_account_id=360999005254` stamped Hub-side. (2) A hand-crafted malformed envelope (status=PASS verdict-injection, bad sha, extra field) sent directly to the ingest queue was REJECTED fail-closed — no item in the live table, a quarantine object written to the Hub quarantine S3. (3) `ZtieIntakeStack` has NO DynamoDB table and the intake role holds only `s3:PutObject` + `sqs:SendMessage` (no dynamodb on the Hub table). (4) Raw body in Forensic S3 is `application/octet-stream`, KMS-encrypted, sha256 in metadata. Live fixes required during validation (merged to main before the flip): PR #12 (CloudShell bundling temp/ENOSPC + Docker entrypoint) and PR #13 (force Docker bundling for the native `rpds-py` dep — fixed `ImportModuleError`).
- **On pass (and only then):** record the dated Validation Result + flip ✅ per the Close-Out Procedure.
- **Advancement gate:** should land before Phase 2 builds on the tracking record; absorbs the earlier "surface derived metadata Forensic → Hub" follow-up (now this story).

**1.R — Restore-point mechanism (prerequisite for the P1 close)**  ✅ _Done (validated)_
- Steps: build the **Python** state-capture tool (read-only; captures a **restore-relevant projection** — identity + desired-state fields only, never raw resource objects, to avoid false-positive drift) and the **coordinated restore** (re-apply captured state; CloudFormation restore must re-apply template + parameters + stack-level **tags**). Fill `RESTORE.md` (state-capture + coordinated-restore procedures) and `BOM.md` (the real deployed inventory) for ZTIE. Per RD-012, the durable state to capture is the **Hub** (tracking DynamoDB + infra) and **infra projections** (CFN stacks, S3 config, Lambda name/runtime/code_sha256, any SSM params); Forensic's ephemeral raw-payload/scratch is disposable and is rebuilt, not restored. Per **RD-015**, the manifest must also **pin the known-good governance-doc commit** (PROJECT_PLAN, RUNBOOK, METHODOLOGY, RESTORE, BOM, templates, decisions) so a restore returns **code + state + governance as one unit**. Any mutating restore is gated behind a deliberate confirm that reads the terminal and **fails safe to NO** (Python `input()`).
- **As built (branch `feature/story-1.R`):** `scripts/ztie_restore/` Python 3.12 package + `scripts/ztie-restore` CLI with three subcommands — `capture` (read-only → timestamped `restore-manifests/manifest-<UTC>.json`), `verify` (read-only projection diff), `restore` (confirm-gated coordinated re-apply). Projection model (`projection.py`) captures identity + desired-state only: CFN name/template_sha256/parameters/**tags**; DynamoDB name/billing/keys/attrs/GSIs/SSE/PITR; Lambda name/runtime/handler/code_sha256; S3 config (versioning/encryption/public-access-block/bucket-key); SSM name/type/value/secure. Diff is order-insensitive and ignores volatile metadata. Restore re-applies CFN template+params+**tags** (`cloudformation update_stack` with `Tags=`) + SSM values; `input()` gate fails safe to NO (`ZTIE_ASSUME_NO=1` for automatable NO proof; no assume-YES). Manifest pins `governance_commit` (HEAD sha + branch + dirty). Account-guarded via STS. Manifest schema `schemas/restore-manifest.v1.json`. `RESTORE.md` + `BOM.md` filled. Local proof (sandbox is INTEGRATIONS_ONLY — no boto3/pytest): 14 stdlib-`unittest` tests PASS (projection diff incl. dropped-tag-is-drift + ordering-not-drift + uncaptured-secure-not-drift; confirm both branches + abort-makes-no-changes), `py_compile` clean, `ruff` clean, `prettier` clean.
- **Validation Result:** pass — live on the Hub account (641628980935), us-east-1, 2026-08-25, confirmed by the user. (1) `capture --account hub` wrote `restore-manifests/manifest-20260825T160347Z.json` with 4 projections (CFN `ZtieHubTrackingStack` template_sha256 `175b7472…` + `BootstrapVersion` param + 5 stack tags; validator Lambda python3.12/`handler.handler`/code_sha256; quarantine S3 versioning/KMS/all-4-PAB; tracking DynamoDB PK `intake_id` + GSI `status-received_at-index` HASH status/RANGE received_at, PAY_PER_REQUEST, KMS SSE, PITR) and pinned `governance_commit.sha`. (2) `verify` with no change reported MATCH (exit 0) — no false drift despite live CFN status/timestamps/ARNs. (3) A deliberate `update-stack` adding tag `ZtieDrift=deliberate` made `verify` report DRIFT (exit 3), catching the `tags` field diff keyed to the stack identity. (4) `restore --account hub … --template ZtieHubTrackingStack=<live template>` re-applied template+params+**tags**; the automatic post-restore `verify` reported MATCH (exit 0) — the drift tag removed. (5) Fail-safe-NO proven: a non-affirmative reply aborted with no changes (exit 4), and `ZTIE_ASSUME_NO=1` overrode even `--yes` (hard-NO brake wins, exit 4). Live fix during validation (merged before flip): the confirm gate was made self-diagnosing (prints the exact reply read / the active brake) + a deliberate `--yes` path added, which surfaced that the earlier apparent "typed y but aborted" was a multi-line paste landing in `input()` (the gate correctly fail-safe-rejected it), not an env/code bug.
- **On pass (and only then):** record the dated Validation Result + flip ✅ per the Close-Out Procedure.
- **Advancement gate:** **prerequisite for the Phase 1 close** — `restore/phase-1-green` (tag + manifest) cannot be captured until this exists and passes. Recommended to land after 1.1R (capture the final Forensic→Hub topology, not the pre-remediation one).

**1.2 — Preprocessor classifier**  ✅ _Done (validated)_
- Steps: inspect file extensions + metadata **and actual content** to classify each artifact (IaC template vs raw script vs other/unknown). Contract-first; distrust the claimed type; classification is a LABEL only (no verdict, no route).
- **As built (branch `feature/story-1.2`):** contract-first + pure-logic split (the 1.1R / 1.R pattern).
  - **Contract:** `schemas/classification.contract.v1.json` (draft-07, allow-list, `additionalProperties:false` at every level) — the derived classification LABEL and the only classification shape allowed to cross Forensic → Hub. Integrity-keyed by `intake_id` + `sha256`; records BOTH an `extension_signal` and a `content_signal`, whether they `signals_agree`, and the `basis` the final class rests on. Deliberately **no** `verdict`/`safe`/`route` field. Generated via `python scripts/gen_classification_contract.py` (fs_write refuses a remote `$schema` URL) into both `schemas/` and the bundled `lambdas/hub_ingest/` copy so they cannot drift.
  - **Classifier (pure):** `lambdas/preprocessor/classifier.py` — `classify(filename, content_bytes)` computes the extension signal and the content signal **independently**; on disagreement the CONTENT signal wins (distrust-the-claim), recording both. Content inspection = binary magic-bytes (ELF/PE/PNG/PDF/zip/gzip… → `other_unknown`), CloudFormation cues (`AWSTemplateFormatVersion`, `Resources:` + `AWS::<svc>::<type>`, SAM `Transform`), Terraform/HCL block structure, shebang interpreters, and anchored source-structure patterns (python/js/shell). Ambiguous `.json/.yaml/.yml` are recorded but never decisive by extension alone. Bounded to a 64 KiB head slice. No AWS, no I/O — offline-unit-testable.
  - **Wiring (thin):** `lambdas/preprocessor/awsio.py` (boto3 seam: `head_object_metadata`, ranged `get_object_head_bytes`, `send_classification_envelope`) + `lambdas/preprocessor/handler.py` — a Forensic-side Lambda triggered by S3 `ObjectCreated` on the intake bucket (`intake/` prefix). It reads the object's `intake-id`+`sha256` metadata and a bounded head slice (the read stays in Forensic), runs the pure classifier, and emits a DERIVED, label-only envelope to the SAME Hub ingest queue (1.1R). The raw body never leaves Forensic; only the label crosses.
  - **Hub gate extended:** `lambdas/hub_ingest/handler.py` now routes by envelope kind — a classification envelope (carries `classification`) is validated fail-closed against the classification contract, then **integrity-bound** applied to the EXISTING tracking record via a conditional `update_item` (`attribute_exists(intake_id) AND sha256 = <label sha>`): it never creates a record, never touches `status`/verdict. A conditional failure is disambiguated by a single `GetItem` — record absent = ordering race → retry; `sha256` mismatch = integrity violation → quarantine.
  - **Infra:** `infra/lib/ztie-intake-stack.ts` adds the preprocessor Lambda (S3 notification trigger, `grantRead` on the artifact bucket, `sqs:SendMessage` to the Hub queue) + outputs `PreprocessorFunctionName`/`PreprocessorRoleArn`; `infra/lib/ztie-hub-tracking-stack.ts` grants the validator `grantReadWriteData` (the classification path needs `GetItem`) and adds `forensicPreprocessorRoleArn` so the second Forensic sender is on the queue resource policy.
  - **Local proof (sandbox is INTEGRATIONS_ONLY — no boto3/pytest/cdk):** 32 stdlib-`unittest` classifier tests PASS (three classes + the claim/content-mismatch distrust cases + result-shape/no-verdict-field), 4 schema-conformance tests skip offline / run live under pytest, `py_compile` clean, `ruff` clean, `prettier` clean.
- **Validation Result:** pass — live end-to-end across Forensic (360999005254) + Hub (641628980935), us-east-1, 2026-08-25, confirmed by the user. Redeployed `ZtieHubTrackingStack` (Hub — validator's classification path + read grant; Docker-bundled `rpds-py` clean) then `ZtieIntakeStack` (Forensic — preprocessor Lambda + S3 `ObjectCreated` trigger). Three SigV4-signed `POST /intake` submissions from a Forensic principal each returned 201, and the derived classification label landed on the Hub tracking record (queried by `intake_id`): (1) a CloudFormation template uploaded as `stack.yaml` → `artifact_class=iac_template`, `basis=content` (ambiguous `.yaml` ext → `extension_signal=none`, `content_signal=iac_template`), sha `9c10009d…`; (2) `deploy.sh` bash → `artifact_class=raw_script`, `basis=agreement`, `signals_agree=true` (ext + content both raw_script), sha `43e33be3…`; (3) **distrust-the-claim** — the same bash bytes uploaded as `innocent.yaml` → `artifact_class=raw_script`, `basis=content`, `signals_agree=false`, `content_signal=raw_script` — **content beat the claimed `.yaml` extension**. All three queryable by `intake_id` with matching sha256; no verdict/route field crossed (label only).
- **On pass (and only then):** record + flip ✅ per the Close-Out Procedure. _(Done: 2026-08-25.)_
- **Advancement gate:** ✅ — unblocks 1.3 (routing) and 1.4 (safe-reject), which both key off the class.

**1.3 — Routing table to lanes**  🟡 _In Progress (built; awaiting live validation)_
- Steps: route IaC to the correct linters and raw scripts to their distinct auditing paths; wire both the static and dynamic lanes as fork targets.
- **As built (branch `feature/story-1.3`):** contract-first + pure-logic split (the 1.1R / 1.R / 1.2 pattern), a THIRD envelope kind on the same RD-013 Hub gate.
  - **Contract:** `schemas/routing.contract.v1.json` (draft-07, allow-list, `additionalProperties:false` at every level) — the derived routing DECISION and the only routing shape allowed to cross Forensic → Hub. Integrity-keyed by `intake_id` + `sha256`; the `routing` object records the `artifact_class` it routed on, the `lanes` plan (ordered, unique, bounded 1–3, from a closed lane `enum`), a `routable` boolean, and the `basis` (`class_route` | `safe_reject_fallback`). Deliberately **no** `verdict`/`safe`/`approved`/`forward` field — a routing decision is a PLAN OF CONTROLS, never a verdict and never a forward-to-PDE decision. Generated via `python scripts/gen_routing_contract.py` (fs_write refuses a remote `$schema` URL) into both `schemas/` and the bundled `lambdas/hub_ingest/` copy so they cannot drift (byte-identical).
  - **Router (pure):** `lambdas/preprocessor/router.py` — `route(artifact_class)` is a **declarative, data-driven** table (`_ROUTING_TABLE`), not if/else: `iac_template` and `raw_script` each fork into **both** Phase-2 lanes `[static_analysis, dynamic_detonation]` (`basis=class_route`, `routable=true`); `other_unknown` **and any unrecognised/missing class** fall through to `[safe_reject]` (`basis=safe_reject_fallback`, `routable=false`) — handed to Story 1.4's entry, never a scanner, never a crash, never a silent drop. No AWS, no I/O — offline-unit-testable.
  - **Wiring (thin):** `lambdas/preprocessor/awsio.py` adds `send_routing_envelope`; `handler.py` runs the pure router over the class label it just classified and emits a DERIVED, decision-only routing envelope to the SAME Hub ingest queue (a second `SendMessage` alongside the classification envelope). The raw body never leaves Forensic; only the derived decision crosses.
  - **Hub gate extended:** `lambdas/hub_ingest/handler.py` now routes by a THIRD envelope kind — a routing envelope (carries `routing`) is validated fail-closed against the routing contract, then **integrity-bound** applied to the EXISTING tracking record via a conditional `update_item` (`attribute_exists(intake_id) AND sha256 = <decision sha>`) setting `routing` + `routing_lanes` + `routed_at`: it never creates a record, never touches `status`/verdict. A conditional failure is disambiguated (shared `_resolve_conditional_apply_failure` helper) — record absent = ordering race → retry; `sha256` mismatch = integrity violation → quarantine.
  - **Fork targets (addressable):** the lane `enum` (`static_analysis` → Story 2.1 static lane; `dynamic_detonation` → Story 2.3 dynamic lane; `safe_reject` → Story 1.4) is the concrete set Phase 2 hangs off. 1.3 defines *where* each class goes; it does not build the lanes.
  - **Infra:** `infra/lib/ztie-intake-stack.ts` adds `ROUTING_CONTRACT_VERSION=1.0` to the preprocessor Lambda env; the routing envelope reuses the same one Hub-ingest-queue send-only grant (no new permission).
  - **Local proof (sandbox is INTEGRATIONS_ONLY — no boto3/pytest/cdk):** 12 stdlib-`unittest` router tests PASS (both routable classes fork into both lanes; other_unknown/unrecognised/None/empty fail safe to `[safe_reject]` without crashing; no verdict/forward field on any decision; lanes unique + required fields present), 4 routing schema-conformance tests skip offline / run live under pytest, a manual schema-constraint conformance check passed, 8 new hub-gate routing tests added (moto+pytest, live-only: apply-onto-existing, never-create-on-ordering-race, sha-mismatch-quarantine, allow-list rejections incl. smuggled verdict/forward + unknown lane + wrong version). `py_compile` clean, `ruff` clean, `prettier` clean. Full preprocessor suite: 52 tests, 8 skipped (conformance offline).
- **Validation Result:** pass — live end-to-end across Forensic (360999005254) + Hub (641628980935), us-east-1, 2026-08-27, confirmed by the user. Redeployed `ZtieHubTrackingStack` (Hub — routing validator path + bundled `routing.contract.v1.json`) then `ZtieIntakeStack` (Forensic — `ROUTING_CONTRACT_VERSION` + router emit in the preprocessor). Three SigV4-signed `POST /intake` submissions from a Forensic principal each returned 201, and the derived routing decision landed on the Hub tracking record (queried by `intake_id`): (1) `stack.yaml` (CloudFormation) → `artifact_class=iac_template`, `routing_lanes=[static_analysis, dynamic_detonation]`, `routable=true`, `basis=class_route`, sha `74eeb388…`; (2) `deploy.sh` (bash) → `artifact_class=raw_script`, `routing_lanes=[static_analysis, dynamic_detonation]`, `routable=true`, `basis=class_route`, sha `40455a2e…`; (3) `notes.txt` (plain text, no IaC/script structure) → `artifact_class=other_unknown`, `routing_lanes=[safe_reject]`, `routable=false`, `basis=safe_reject_fallback`, sha `dfc21555…`. All three: `status=RECEIVED` (routing never touches verdict); no `verdict`/`forward`/`approved` field crossed (all null). Each classified type routes to the correct downstream lane, queryable by `intake_id`.
- **On pass (and only then):** record + flip ✅ per the Close-Out Procedure. _(Done: 2026-08-27.)_
- **Advancement gate:** ✅ — unblocks all of Phase 2 (nothing to inspect until routing exists); pairs with 1.4 (safe-reject).

**1.4 — Safe-reject path for unknown types**  🟡 _In Progress (built; awaiting live validation)_
- Steps: for unroutable/incompatible artifacts, reject safely so an incompatible scan never crashes the pipeline.
- **As built (branch `feature/story-1.4`):** contract-first + pure-logic split (the proven 1.1R/1.R/1.2/1.3 pattern), a FOURTH envelope kind on the same RD-013 Hub gate.
  - **Contract:** `schemas/reject.contract.v1.json` (draft-07, allow-list, `additionalProperties:false`) — the derived safe-reject OUTCOME and the only rejection shape allowed to cross Forensic → Hub. Integrity-keyed by `intake_id`+`sha256`; the `rejection` object records `pipeline_outcome` (always `SAFE_REJECTED` — distinct from the human verdict), `reason` (`unroutable_class`), and `artifact_class`. No `verdict`/`safe`/`approved`/`forward` field. Generated via `scripts/gen_reject_contract.py` into both `schemas/` and `lambdas/hub_ingest/` (byte-identical).
  - **Rejector (pure):** `lambdas/preprocessor/rejector.py` — `reject(routing_decision)` returns the rejection outcome when `routable=false`; returns `None` for a routable artifact (never safe-rejects a scannable file). Never crashes on any input.
  - **Wiring (Forensic-side):** `handler.py` emits the reject envelope immediately after the routing envelope when the router says `routable=false`. `awsio.send_reject_envelope` sends it to the same Hub ingest queue. The raw body stays in Forensic (left to S3 lifecycle/TTL per RD-012; explicit delete adds no security value).
  - **Hub gate:** fourth envelope kind (`rejection` key) — fail-closed contract validation + integrity-bound conditional `update_item` (sets `pipeline_outcome=SAFE_REJECTED`, `rejection`, `rejected_at`; never creates a record, never touches `status`/human `verdict`). Shared retry-vs-quarantine disambiguation for the label-ordering race.
  - **Infra:** `REJECT_CONTRACT_VERSION=1.0` on the preprocessor Lambda env (same send-only grant).
  - **Local proof:** 10 stdlib-`unittest` rejector tests PASS (unroutable → SAFE_REJECTED, routable → None, no verdict/forward field, never crash); 3 conformance tests skip offline; full suite 65 tests 11 skipped. `py_compile`, `ruff`, `prettier`(infra) all clean. Schemas byte-identical.
- **Validation Result:** _pending — submit an unknown artifact, confirm it is safe-rejected on the Hub record (pipeline_outcome=SAFE_REJECTED, rejection.reason=unroutable_class), not forwarded to any scanner, pipeline does not crash; AND confirm a routable artifact is NOT safe-rejected._
- **On pass (and only then):** record + flip ✅, then Phase-1 close (BOM + restore/phase-1-green).
- **Advancement gate:** required for the P1 gate (resilience criterion) + the P1 close.

---

## Phase P2 — Parallel Inspection Paths

_Gate: a known-bad artifact produces (a) static findings from the scanning stack AND (b) observed runtime behavior from a real detonation, with both lanes running in parallel and each emitting structured output; the ephemeral EC2 is confirmed torn down via hard TTL._

| Story | Title | Depends on | Status | Completed | Restore tag |
|-------|-------|-----------|--------|-----------|-------------|
| 2.0 | AWS infra foundation (CDK v2: VPC/isolated subnets, IAM, launch template, SSM, Nova Pro access) | 1.3 | ⬜ | | |
| 2.1 | Static scanning stack (cfn-lint, cfn-guard, checkov, bandit) | 1.3 | ⬜ | | |
| 2.2 | Compliance-framework mapping (NIST SP 800-53 / ISO 27001) + signature scans | 2.1 | ⬜ | | |
| 2.3 | Detonation chamber — ephemeral EC2 + host-native SSM execution | 2.0 | ⬜ | | |
| 2.4 | Behavioral telemetry capture (syscalls / network / filesystem) | 2.3 | ⬜ | | |
| 2.5 | Telemetry sanitization pipeline (entropy scrub → noise suppress → ≤25K truncation) | 2.4 | ⬜ | | |
| 2.6 | Parallel orchestration / fork of the two lanes | 2.1, 2.3 | ⬜ | | |

**2.0 — AWS infra foundation**  ⬜ _Not Started_
- Steps: deploy the CDK v2 TypeScript infra stack (VPC isolated subnets w/ VPC endpoints only, IAM, per-run launch template, SSM wiring, Nova Pro access) BEFORE any Lambda/Step Function code. Shared foundation for P2–P4.
- **Validation Result:** _pending — confirm the stack deploys and isolated networking + launch template exist live._
- **On pass (and only then):** record + flip ✅.
- **Advancement gate:** blocks 2.3 (detonation needs the isolated VPC + launch template).

**2.1 — Static scanning stack**  ⬜ _Not Started_
- Steps: integrate cfn-lint, cfn-guard, checkov, bandit as non-executing scanners; emit structured JSON results.
- **Validation Result:** _pending — scan a known-bad IaC/script and confirm findings JSON is emitted._
- **On pass (and only then):** record + flip ✅.
- **Advancement gate:** feeds 2.2 and the fork (2.6); its JSON is a Phase 3 input.

**2.2 — Compliance mapping + signature scans**  ⬜ _Not Started_
- Steps: evaluate source against mandated frameworks (NIST SP 800-53 / ISO 27001); run signature-based scans for known vulns/malicious patterns.
- **Validation Result:** _pending — confirm a violation maps to the correct framework control and a known signature is detected._
- **On pass (and only then):** record + flip ✅.

**2.3 — Detonation chamber (ephemeral EC2 + SSM)**  ⬜ _Not Started_
- Steps: deploy payload into a highly restricted ephemeral EC2 via `ec2:RunInstances` launch template; run host-native via SSM (NO Docker); enforce 5-minute hard TTL (`shutdown -h +5`).
- **Validation Result:** _pending — detonate a sample payload; confirm real EC2 runs it and is torn down by TTL._
- **On pass (and only then):** record + flip ✅.
- **Advancement gate:** blocks 2.4 (no telemetry without a real run).

**2.4 — Behavioral telemetry capture**  ⬜ _Not Started_
- Steps: monitor and capture system calls, network attempts, and file operations during detonation; emit behavioral data.
- **Validation Result:** _pending — confirm syscall/network/fs activity of a known-bad payload is captured._
- **On pass (and only then):** record + flip ✅.

**2.5 — Telemetry sanitization pipeline**  ⬜ _Not Started_
- Steps: entropy scrub → noise suppress → ≤25K token truncation, preparing telemetry for Nova Pro.
- **Validation Result:** _pending — confirm raw telemetry is sanitized and truncated within the token budget._
- **On pass (and only then):** record + flip ✅.
- **Advancement gate:** required before any Phase 3 Nova Pro call.

**2.6 — Parallel orchestration / fork**  ⬜ _Not Started_
- Steps: fork the pipeline so static and dynamic lanes run concurrently after routing; join their outputs for handoff to Phase 3.
- **Validation Result:** _pending — confirm both lanes execute in parallel for one artifact and both outputs are collected._
- **On pass (and only then):** record + flip ✅.
- **Advancement gate:** closes Phase 2; feeds Phase 3 aggregation.

---

## Phase P3 — AI Correlation and Assessment

_Gate: given paired static + dynamic outputs, Nova Pro returns a single unified threat score, correlated findings (static ↔ dynamic evidence), and prioritized remediations; a case where static flags a risk but dynamic proves benign (or vice-versa) is correctly reconciled (false-positive elimination demonstrated)._

| Story | Title | Depends on | Status | Completed | Restore tag |
|-------|-------|-----------|--------|-----------|-------------|
| 3.1 | Telemetry aggregation / normalization (shared schema) | 2.6 | ⬜ | | |
| 3.2 | Nova Pro correlation engine (exponential-backoff retry) | 3.1, 2.5 | ⬜ | | |
| 3.3 | accuracy + gap_analysis synthesis | 3.2 | ⬜ | | |
| 3.4 | Unified threat scoring + prioritized remediations | 3.3 | ⬜ | | |
| 3.5 | Verdict derivation (PASS / FAIL / INCONCLUSIVE) | 3.4 | ⬜ | | |

**3.1 — Telemetry aggregation / normalization**  ⬜ _Not Started_
- Steps: aggregate raw telemetry, error logs, and JSON outputs from both lanes into the shared normalized event schema.
- **Validation Result:** _pending — confirm static + dynamic outputs for one artifact normalize into a single combined record._
- **On pass (and only then):** record + flip ✅.

**3.2 — Nova Pro correlation engine**  ⬜ _Not Started_
- Steps: pass the combined record to Amazon Nova Pro; correlate static misconfigurations with dynamic behavioral indicators; exponential-backoff retry on throttling.
- **Validation Result:** _pending — confirm a correlated assessment is returned for a paired input._
- **On pass (and only then):** record + flip ✅.

**3.3 — accuracy + gap_analysis synthesis**  ⬜ _Not Started_
- Steps: run the accuracy and gap_analysis programs to synthesize the data and eliminate false positives.
- **Validation Result:** _pending — confirm a static-only false positive is reconciled against benign dynamic evidence._
- **On pass (and only then):** record + flip ✅.

**3.4 — Unified threat scoring + remediations**  ⬜ _Not Started_
- Steps: produce a single unified threat score, detailed findings, and prioritized remediations.
- **Validation Result:** _pending — confirm one score + ranked findings + remediations are emitted for a run._
- **On pass (and only then):** record + flip ✅.

**3.5 — Verdict derivation**  ⬜ _Not Started_
- Steps: derive the enforcement verdict from the score/findings: PASS / FAIL / INCONCLUSIVE.
- **Validation Result:** _pending — confirm each of the three verdicts can be produced from representative inputs._
- **On pass (and only then):** record + flip ✅.
- **Advancement gate:** closes Phase 3; the verdict drives all Phase 4 routing.

---

## Phase P4 — Handoff and Reporting

_Gate: for a full run, confirm the dashboard JSON and PDF report are produced with tiered content (Executive / Security / Developer); on human ACCEPT, ZTIE pushes the hash-verified artifact from Forensic to Pipeline-Sandbox (586917955591) and no un-accepted artifact ever leaves Forensic; on REJECT, the artifact + detonation chamber are destroyed in Forensic; an INCONCLUSIVE artifact holds until a human accepts/rejects it from the dashboard._

| Story | Title | Depends on | Status | Completed | Restore tag |
|-------|-------|-----------|--------|-----------|-------------|
| 4.1 | Status-retrieval orchestrator | 3.5 | ⬜ | | |
| 4.2 | Dashboard JSON payload | 4.1 | ⬜ | | |
| 4.3 | Real-time dashboard (dark theme, graduated severity/threat color coding) | 4.2 | ⬜ | | |
| 4.4 | Interactive accept/reject control (Hub) gating the Forensic→Pipeline-Sandbox push | 4.3, 4.7 | ⬜ | | |
| 4.5 | Per-execution PDF report (tiered: Executive / Security / Developer) | 4.1 | ⬜ | | |
| 4.6 | ACCEPT → ZTIE pushes hash-verified artifact Forensic → Pipeline-Sandbox (PDE handoff) | 4.1 | ⬜ | | |
| 4.7 | REJECT → destroy artifact + detonation chamber in Forensic; INCONCLUSIVE → hold at approval gate | 4.1 | ⬜ | | |

**4.1 — Status-retrieval orchestrator**  ⬜ _Not Started_
- Steps: orchestrate delivery of the correlated data; transform AI insights into the outputs the dashboard and report consume.
- **Validation Result:** _pending — confirm the orchestrator emits the correlated payload for a completed run._
- **On pass (and only then):** record + flip ✅.

**4.2 — Dashboard JSON payload**  ⬜ _Not Started_
- Steps: build the comprehensive JSON that populates the dashboard (pipeline status, verdicts, findings, cost/sensor/AMI health metrics).
- **Validation Result:** _pending — confirm the JSON schema is populated for a real run._
- **On pass (and only then):** record + flip ✅.

**4.3 — Real-time dashboard**  ⬜ _Not Started_
- Steps: render a real-time dashboard on a dark background with graduated color coding for severity/threat tiers (low/medium/high/critical distinguishable at a glance). Must surface the operator's headline views (PROJECT_PLAN §7): **live activity** ("detonation running / ports being scanned now"), the **port-indexed view** (port ⇄ MITRE, occurrence count, start/end), and **restore-point status/health** as a first-class visible element.
- **Validation Result:** _pending — confirm the dashboard reflects a live run with correct severity coloring._
- **On pass (and only then):** record + flip ✅.

**4.4 — Interactive approve/reject control**  ⬜ _Not Started_
- Steps: from the dashboard, let a human reviewer approve or reject findings; the approval decision gates whether the object may pass downstream to the PDE (human-in-the-loop for INCONCLUSIVE).
- **Validation Result:** _pending — confirm an approve unlocks PDE handoff and a reject blocks it._
- **On pass (and only then):** record + flip ✅.

**4.5 — Per-execution PDF report (tiered)**  ⬜ _Not Started_
- Steps: generate the PDF with three audience tiers — Executive (risk score + one-paragraph verdict), Security (MITRE ATT&CK mappings, behavioral chains, Sigma rules), Developer (exact failure cause, file/line, remediation, static-dynamic correlation).
- **Validation Result:** _pending — confirm a run produces a PDF with all three tiers populated._
- **On pass (and only then):** record + flip ✅.

**4.6 — ACCEPT → push artifact to Pipeline-Sandbox (PDE handoff)**  ⬜ _Not Started_
- Steps: on a human ACCEPT of ZTIE findings in the Hub, ZTIE pushes the hash-verified artifact Forensic → Pipeline-Sandbox (586917955591), one-directional and least-privilege. On landing the artifact is under PDE control and ZTIE's responsibility ends. ZTIE never re-executes the artifact outside Forensic.
- **Validation Result:** _pending — confirm an accepted artifact is pushed to Pipeline-Sandbox and that no un-accepted/unverified artifact ever leaves Forensic._
- **On pass (and only then):** record + flip ✅.

**4.7 — REJECT → destroy artifact + chamber in Forensic / INCONCLUSIVE hold**  ⬜ _Not Started_
- Steps: on a human REJECT, destroy the artifact **and** its detonation chamber (the ephemeral EC2) in Forensic — explicit teardown, not waiting for TTL; nothing is promoted (the derived report survives in the Hub). On INCONCLUSIVE, hold at the manual approval gate for human review.
- **Validation Result:** _pending — confirm REJECT destroys artifact + detonation chamber in Forensic and INCONCLUSIVE holds at the gate._
- **On pass (and only then):** record + flip ✅.
- **Advancement gate:** together with 4.4 and 4.6, closes Phase 4 — the full enforcement decision flow.

---

## Cross-cutting / Governance stories

_Not phase-bound; sequenced by readiness. Tracked here so they aren't forgotten._

| Story | Title | Depends on | Status | Completed | Restore tag |
|-------|-------|-----------|--------|-----------|-------------|
| G-1 | Back-map design artifacts to candidate NIST family + ISO 27001 controls (RD-014) | — | ⬜ | | |
| G-2 | Management-artifact integrity: automated consistency check + reusable-OS/instance separation (RD-015) | — | ⬜ | | |

**G-1 — Compliance back-mapping (RD-014)**  ⬜ _Not Started_
- Steps: populate [`DOCS/COMPLIANCE.md`](DOCS/COMPLIANCE.md) by proposing candidate control mappings for the existing design artifacts — registered decisions RD-001…RD-014, the non-functional constraints, and each story — against **NIST SP 800-53 Rev 5 (catalog of record), NIST CSF, related NIST (RMF)**, and **ISO/IEC 27001:2022 Annex A**. Each row carries a rationale and Status=`Proposed`.
- **Best executed** once the core pipeline design stabilizes (avoid mapping a moving target); new artifacts still propose mappings at authoring time in the meantime.
- **Validation Result:** _pending — an accountable reviewer ratifies (or corrects) the candidate mappings; Status flips `Proposed` → `Ratified` per reviewed artifact. ZTIE claims coverage only for ratified mappings._
- **On pass (and only then):** record the dated Validation Result + flip ✅ per the Close-Out Procedure. (May be validated incrementally per artifact group.)
- **Advancement gate:** none blocks it and it blocks nothing; it is a standing auditability practice, not a pipeline dependency.

**G-2 — Management-artifact integrity (RD-015)**  ⬜ _Not Started_
- Steps: make RD-015 enforceable, not aspirational. (a) Build a **Python consistency checker** (`scripts/check_docs.py`, Python-first; later wired into AWS-native CI) that **fails (non-zero)** if: PROJECT_PLAN and RUNBOOK story-sets diverge (per phase); any referenced `RD-0NN` doesn't exist in the decisions table; stray template placeholders (`{{…}}`) remain outside the known-intentional template files; or a story marked ✅ lacks a dated Validation Result line. (b) **Separate the reusable-OS layer** (METHODOLOGY, templates, the gate, restore discipline — generic, seeds a new project unchanged) from the **project-instance layer** (RD-008…, account IDs, pipeline stories), and document the boundary so reusability is provable, not asserted. (c) Ensure the restore-point manifest **pins the known-good governance-doc commit** (coordinate with story 1.R) so code + state + governance restore as one unit.
- **Validation Result:** _pending — user confirms live: the checker passes on a clean tree, and is proven to FAIL on each injected defect (deliberate plan/runbook divergence, a dangling RD ref, a stray placeholder, a ✅ story with no validation line); and the reusable-OS/instance boundary doc is reviewed as accurate._
- **On pass (and only then):** record the dated Validation Result + flip ✅ per the Close-Out Procedure.
- **Advancement gate:** none blocks it; strongly recommended before Phase 1 close so the plan↔runbook alignment (RD-015) is machine-enforced, not eyeballed. Coordinates with 1.R (governance-doc commit in the manifest).

---

## Universal Acceptance Criteria (apply to EVERY story/phase gate)

In addition to each story's own validation, every deliverable must satisfy:
1. **No mocks in the execution path** — real AWS services and real detonation on ephemeral EC2 (host-native SSM, no Docker); any test double is unit-level only and explicitly agreed.
2. **Independently validatable** — the component can be exercised end-to-end live and its output (routing decision, scan JSON, behavioral telemetry, threat score, or verdict) inspected.
3. **Zero-trust honored** — no artifact reaches the PDE without a recorded PASS verdict; FAIL (nuke + return telemetry) and INCONCLUSIVE (human approval gate) are enforced, not advisory.
4. **Management artifacts are first-class (RD-015)** — a story is **not done** until its management artifacts are updated to the same bar as its code: the story's brief + runbook entry current, **PROJECT_PLAN and RUNBOOK in exact alignment**, any new/changed registered decisions + candidate control mappings recorded, all doc changes PR-reviewed (never straight to main), and the governance kept restorable alongside the code. Reusable, durable, repeatable — held to the technical bar.

---

## Ledger Maintenance

- Update a story's **Status** as work moves; set **✅** only after its validation
  passes live **and** the Validation Result line is recorded (see the Story
  Close-Out Procedure).
- On each **phase-close pass**: capture a restore point, record it in the
  inventory, set the phase row ✅.
- Runbook and [`PROJECT_PLAN.md`](PROJECT_PLAN.md) must stay in sync — the plan
  defines scope, the runbook tracks execution.
- **Per-story brief + prompt:** filled from the templates into `session-briefs/`.
- **Next-session brief AND prompt are authored during the current session** — the
  final task each session, including Lessons Learned / Carry-Forward, so the next
  session starts with zero cold-start.
