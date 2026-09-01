# Session Brief — Story 1.3

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.

---

## Story 1.3 — Routing table → static & dynamic lanes

| Field | Value |
|-------|-------|
| **Phase** | P1 — Intake & Routing |
| **Date** | 2026-08-25 |
| **Status** | ✅ Done — validated live 2026-08-27 |
| **Builds from restore point** | none yet (Phase-1 close captures the first tag, after 1.2/1.3/1.4 + validated 1.R) |
| **Session goal** | Build the routing table that maps each artifact **class** (from the 1.2 classification label) to its downstream lane(s): IaC templates → the static-analysis lane's IaC linters; raw scripts → their distinct audit path; and wire BOTH the static and dynamic lanes as fork targets so Phase 2 has concrete entry points. |

---

### Background & Context

Phase 1 is Intake & Routing. Story 1.1 (intake gateway) is ✅, 1.1R (durable record
→ Hub behind the RD-013 gate) is ✅, and **1.2 (preprocessor classifier)** produces a
derived **classification label** (`iac_template` / `raw_script` / `other_unknown`)
that is upserted onto the Hub tracking record keyed by `intake_id`. **1.3 is the next
build step:** it turns that label into a **routing decision** — which downstream
lane(s) an artifact goes to. 1.4 (safe-reject) then owns the `other_unknown` /
unroutable path. (1.2 must be ✅ live before 1.3 begins — the advancement gate.)

### Objective & Value

- **Objective:** a **routing table** (declarative, contract-first) that maps an
  artifact class → one or more target lanes, plus the wiring that emits the routing
  decision. IaC templates route to the **static lane** (cfn-lint/cfn-guard/checkov —
  Story 2.1) and, per the architecture, also to the **dynamic lane**; raw scripts
  route to their audit path (bandit-style SAST + the dynamic detonation lane);
  `other_unknown` / unroutable is handed to the **safe-reject** path (1.4). The two
  Phase-2 lanes are wired as concrete **fork targets** so 2.x has somewhere to hang.
- **Why it matters:** routing is the fork point of the pipeline — it is how the class
  becomes "which controls apply." Everything in Phase 2 (both lanes) keys off it.

### Scope, Dependencies & Position

- **In scope:** the routing table + its shape (contract-first, like 1.2's label
  contract); the routing decision as a derived, label-only record (no verdict, no
  forward-to-PDE); wiring the fork so both the static lane and the dynamic lane are
  addressable targets. Production code; pure routing logic + a thin AWS seam;
  offline-provable stdlib `unittest` tests.
- **Out of scope / do NOT touch:** the safe-reject path itself (1.4 — 1.3 only needs
  to *hand off* the unroutable, not implement rejection); any actual scanning /
  detonation (Phase 2 — 1.3 defines the fork targets, it does not build the lanes);
  re-opening the classifier (1.2) or the Hub contract gate (1.1R) beyond what routing
  needs. Don't edit intentional `{{...}}` template placeholders.
- **Depends on:** **1.2 ✅** (the class label must exist to route on). Does NOT depend
  on 1.R.
- **Unblocks:** all of **Phase 2** (both lanes need routing to have a source), and it
  is the companion of **1.4** (which owns the unroutable branch).
- **Roadmap position:** the route step of Phase 1; the fork the two Phase-2 lanes
  hang off.

### Approach & Constraints

- **Approach:** contract-first — define the **routing-decision** shape (JSON Schema,
  like 1.2's `classification.contract.v1.json`) BEFORE the code. Keep routing a
  **pure function** over the classification label → target lane(s); put any AWS
  access behind a thin `awsio`-style seam. The routing table should be **declarative
  and data-driven** (class → lanes), not a pile of `if`s, so 1.4 and Phase 2 read
  cleanly off it. **Zero-trust:** a routing decision is a *plan of which controls to
  apply*, NOT a safety verdict and NOT a forward-to-PDE decision — the verdict stays
  Hub-side / human-gated (Phase 4).
- **Hard constraints:** **Python 3.12** (project standard). **Production code** — real
  routing logic + real handling of the unroutable case (hand to 1.4, never crash).
  AWS-native. **Validation-gated**: the user validates live and the result is recorded
  in `RUNBOOK.md`.

### Validation Rationale & Compliance Mapping (REQUIRED — RD-014)

- **Rationale:** routing is a **flow-control / least-functionality** decision — it is
  how the pipeline applies the *right* controls to the *right* artifact and refuses
  to run an incompatible control (which 1.4 finalizes).
- **Candidate control mappings** *(candidate-until-ratified; also add ratified rows to
  [`../COMPLIANCE.md`](../COMPLIANCE.md)):*

| Framework | Control ID | Control Name | Rationale | Status |
|-----------|-----------|--------------|-----------|--------|
| NIST 800-53 r5 | AC-4 | Information Flow Enforcement | The routing table governs which lane (flow) an artifact may enter based on its class | Proposed |
| NIST 800-53 r5 | CM-7 | Least Functionality | Only the controls appropriate to the class are applied; incompatible lanes are not entered | Proposed |
| NIST 800-53 r5 | SI-3 | Malicious Code Protection | Routing ensures each artifact reaches the scanners/detonation appropriate to it | Proposed |
| ISO 27001:2022 | A.8.26 | Application security requirements | Class-appropriate processing of validated input | Proposed |

- **Audit evidence produced:** the routing-decision records + the live validation run.

### Management-Artifact Obligations (REQUIRED — RD-015)

- [x] Story's **brief + runbook entry** updated (status, dates; validation result
      pending the user's live run). RUNBOOK 1.3 now 🟡 with the full as-built.
- [x] **PROJECT_PLAN and RUNBOOK in exact alignment** (Phase-1 story list markers
      updated: 1.1R/1.R/1.2 ✅, 1.3 🟡; RUNBOOK status table + block match).
- [x] Candidate control mappings recorded (RD-014) — 4 rows added to
      [`../COMPLIANCE.md`](../COMPLIANCE.md) (AC-4, CM-7, SI-3, SI-7, SI-10, ISO
      A.8.26), all `Proposed`.
- [x] All doc changes **PR-reviewed** (branch `feature/story-1.3` + PR, never
      straight to main).
- [ ] If 1.3 closes any live state that should be restorable, it is reflected in
      `BOM.md` and captured via `ztie-restore` at the next phase close. _(No new
      durable resources: routing reuses the existing preprocessor Lambda + Hub gate
      + Hub tracking table; only a Lambda env var + code change. The P1-close
      restore capture will pick up the updated Lambda code_sha256.)_

### Change & Rollback

- **Change type:** normal (adds the routing table + its contract + fork wiring).
- **Restore point this builds from:** none (Phase-1 close is later).
- **Backout plan:** revert the merged PR; routing is additive on top of the
  classification label and does not mutate the classifier or intake path.

### Definition of Done / Validation Gate

- **Done means:** the user, live, confirms that each **classified** artifact lands in
  the **correct downstream lane** — an IaC-template artifact routes to the static
  (IaC-linter) lane [and the dynamic lane per the architecture], a raw-script artifact
  routes to its audit / dynamic path, and an `other_unknown` artifact is handed to the
  safe-reject branch (1.4's entry) rather than into a scanner — recorded/queryable by
  `intake_id`.
- **Validated by:** the user, live (Forensic intake → classify → route).
- **Validation Result:** _pending._
- **On pass (and only then):** record the dated Validation Result + flip 1.3 ✅.
- **On fail:** stays 🟡; next session re-focuses on 1.3.

### Live validation runbook (zero-guess — run in AWS CloudShell)

> **Two CloudShell tabs.** Submit runs in **Forensic (360999005254)**; verification
> reads the tracking table in **Hub (641628980935)**. **Run `aws sts
> get-caller-identity` before each block** — a banner comment does not change the
> account. Region `us-east-1`. **Type/paste ONE line at a time.** Ambient creds
> only (no `--profile`).

**Step 0 — Redeploy (additive; both stacks, Hub first then Forensic).** From the
repo `infra/` dir, deploy `ZtieHubTrackingStack` (Hub — adds the routing validator
path + bundled `routing.contract.v1.json`) then `ZtieIntakeStack` (Forensic — adds
`ROUTING_CONTRACT_VERSION` + the router emit in the preprocessor). Same two-account
deploy sequence as Story 1.2.

**Step 1 — Submit three artifacts from a FORENSIC-authed principal** (SigV4 via
`awscurl`, exactly as 1.2). Capture each returned `intake_id`:
- (a) a CloudFormation template uploaded as `stack.yaml` → expect
  `artifact_class=iac_template`, routed `lanes=[static_analysis, dynamic_detonation]`.
- (b) a bash script `deploy.sh` → expect `artifact_class=raw_script`, routed
  `lanes=[static_analysis, dynamic_detonation]`.
- (c) a plain text / unknown blob (e.g. `notes.txt` with prose, no IaC/script
  structure) → expect `artifact_class=other_unknown`, routed `lanes=[safe_reject]`,
  `routable=false`.

**Step 2 — Verify from a HUB-authed shell** — `aws dynamodb get-item` on the Hub
tracking table by each `intake_id`. Confirm on each record:
- `artifact_class` is as expected (classification already proven in 1.2);
- **`routing.lanes` / `routing_lanes`** equals the expected lane plan above;
- `routing.routable` and `routing.basis` (`class_route` for a/b,
  `safe_reject_fallback` for c);
- **NO** `verdict` / `forward` / `approved` field crossed, and `status` is still
  `RECEIVED` (routing never touches the verdict).

**DoD PASS** = each classified type shows the correct `routing.lanes` on its Hub
record (IaC → static+dynamic, raw script → static+dynamic, unknown → safe-reject),
queryable by `intake_id`, with no verdict/forward field. Then record the dated
Validation Result here + in RUNBOOK.md and flip 1.3 ✅ (paired status commit).
- **Advancement gate:** blocks all of Phase 2 (nothing to inspect until routing
  exists); pairs with 1.4.

### Risks & Watch-Items

- **Route on the class, not the raw artifact.** 1.3 consumes the derived label
  (1.2), which lives on the Hub tracking record. Decide early whether routing runs
  Forensic-side (off the same S3/label event, emitting a routing envelope through the
  same RD-013 Hub gate) or is a Hub-side projection of the label — keep the raw body
  in Forensic either way, and cross only derived data.
- **Fork targets are placeholders-with-contracts, not lanes.** 1.3 defines *where*
  each class goes; it must NOT start building the scanners/detonation (Phase 2). Make
  the fork targets addressable (a documented lane identifier + the routing contract)
  so 2.x plugs in.
- **`other_unknown` is a hand-off, not a rejection.** 1.3 routes the unroutable to
  1.4's entry; it must never crash on an unknown class and never silently drop it.
- **Zero-trust boundary (again).** A routing decision is a plan of controls, never a
  verdict and never a forward-to-PDE. No `safe`/`verdict`/`approved` field in the
  routing contract — same discipline as the 1.2 label.
- **Contract-first + pure-logic + stdlib-`unittest`** — proven twice now (1.R, 1.2);
  do it a third time.

### Lessons Learned / Carry-Forward *(carried from the Story 1.2 build session, 2026-08-25)*

- **From 1.2 — what to reuse (it worked cleanly):**
  - **Contract-first, a third time.** 1.2 wrote `classification.contract.v1.json`
    (draft-07, allow-list, `additionalProperties:false` everywhere, integrity-keyed
    by `intake_id`+`sha256`) via a `python` generator BEFORE the classifier, and the
    code fell out of the shape. Do the same for the **routing-decision** contract.
  - **`python json.dump` for the schema.** `fs_write` refuses a file with a remote
    `$schema` URL, so 1.2 generated the schema with
    `scripts/gen_classification_contract.py` and — importantly — wrote **both** the
    canonical `schemas/` copy AND the bundled `lambdas/hub_ingest/` copy from one
    source so they can't drift. Reuse that pattern (a `gen_*` script) if the routing
    contract is also enforced Hub-side.
  - **Pure logic + thin `awsio` seam = offline unit tests.** 1.2's
    `classifier.py` is pure (no boto3); `awsio.py` holds the boto3 calls;
    `handler.py` is the Lambda glue. Result: **32 stdlib-`unittest` tests pass
    offline** in the INTEGRATIONS_ONLY sandbox with no PyPI. A `test_contract_
    conformance.py` guarded by `try: import jsonschema` **skips offline / runs live**
    — a good way to prove the code satisfies the schema without needing PyPI here.
    Do the same for routing.
  - **Envelope-kind routing on the Hub gate.** 1.2 added a **second** envelope kind
    (the classification label) to the same RD-013 Hub ingest queue + validator; the
    validator now routes by kind (`'classification' in envelope`) and applies the
    label with an **integrity-bound conditional `update_item`** (record exists AND
    `sha256` matches) — never creating a record, never touching `status`/verdict.
    **If routing also crosses to the Hub, it is a THIRD envelope kind** — extend the
    same `_process_record` router + add a `routing.contract.v*.json`; keep the
    integrity binding (`intake_id`+`sha256`) and the fail-closed quarantine.
  - **Conditional-update disambiguation.** When the classification `update_item`
    condition fails, 1.2 does a single `GetItem` to tell **record-absent** (SQS
    ordering race → retry) from **sha256 mismatch** (integrity violation →
    quarantine). If routing depends on the label already being on the record, expect
    the same ordering race and reuse this retry-vs-quarantine pattern. (This is why
    the Hub validator now has `grantReadWriteData`, not just write.)
- **From 1.2 — environment truths (unchanged, do NOT relearn):**
  - Sandbox is **INTEGRATIONS_ONLY**: **PyPI + npm blocked**. You cannot run
    `pytest`/`moto`/`boto3`/`cdk`/`tsc` here. **Build + hand off; the USER validates
    live.** Never claim live tests/synth/deploy pass from the sandbox.
  - **Local proof that DOES work offline:** `python3 -m py_compile`,
    `~/.pyenv/versions/3.12.13/bin/ruff check`, and `prettier` via
    `npx --no-install` **after `unset NODE_OPTIONS`** (run from `infra/`). All three
    were green for 1.2.
  - **Ruff gotchas hit in 1.2 (fix them the same way):** default ruff flags
    `PIE810` (merge multiple `startswith` into one tuple call), `I001` (import
    order — `import awsio` sorts after `from classifier import ...`? no: plain
    `import` blocks sort before `from` only within their group — just let ruff tell
    you and reorder), `RUF012` (a mutable class attribute like a `set` literal needs
    `typing.ClassVar[set[str]]`), and `EXE001` (a file with a `#!` shebang must be
    `chmod +x`). Ruff's default set does **not** enable `E402`/`PLC0415`; don't add
    noqa for non-enabled rules (they show up as unused `RUF100`).
- **From 1.2 — the true state you inherit:**
  - **1.2 is 🟡 pending the user's live validation (PR #17, branch
    `feature/story-1.2`).** Local proof is green (32 offline unittest tests, ruff /
    prettier / py_compile clean). **1.3 cannot begin until 1.2 is ✅** — the
    advancement gate. FIRST action next session: check whether the user validated
    1.2 live; if yes, record it + flip 1.2 ✅ (paired status commit) THEN start 1.3;
    if not yet, the objective is to get 1.2 validated, not to start 1.3.
  - **1.2 live-validation runbook is in `story-1.2-brief.md`** ("Live validation
    runbook" section): redeploy Hub then Forensic (additive), submit a known IaC
    template, a known raw script, and a bash-script-as-`.yaml` mismatch via
    `awscurl`, then `aws dynamodb get-item` to confirm each `artifact_class` +
    `basis` + `signals_agree` landed on the tracking record. The mismatch proving
    `raw_script` by `basis=content` is the distrust-the-claim gate.
  - **Deployed/added P1 resources:** Hub `ZtieHubTrackingStack` (tracking DynamoDB
    + `artifact_class`/`classification` attributes now, ingest SQS + DLQ, validator
    Lambda — now `grantReadWriteData`, quarantine S3); Forensic `ZtieIntakeStack`
    (intake API + Lambda, artifact S3, **now also the preprocessor Lambda** triggered
    by S3 `ObjectCreated` on `intake/`, sending the label to the Hub queue). Outputs
    added: `PreprocessorFunctionName`, `PreprocessorRoleArn`. The preprocessor
    Lambda (or a sibling downstream of it) is the natural place routing hooks in —
    decide Forensic-side-event vs Hub-side-projection early.
  - **Contracts live in `schemas/`** (`intake-tracking.contract.v1.json`,
    `classification.contract.v1.json`) with byte-identical bundled copies in
    `lambdas/hub_ingest/`. `schemas/README.md` documents both. Add the routing
    contract there and keep the copies in sync (the G-2 checker will assert this
    later; until then, verify by `sha256sum`).
  - **`git` truth at handoff:** `main` clean; **PR #17 (1.2) OPEN** on branch
    `feature/story-1.2`. Re-run STEP 0 at session start (git pull, list open PRs) to
    reconfirm — and remember the early-merge lesson: if #17 merges before the live
    green run and the live run produced fixes, reconcile the base branch with a
    follow-up PR so `main` holds the validated code.
- **CloudShell operator lessons (still true):** run commands **one line at a time**
  (don't paste a whole block — a multi-line paste landing in `input()` was the 1.R
  "typed y but aborted" cause); **`/tmp` is wiped on session recycle** so regenerate
  any exported file before it is consumed; **state the account banner on every
  command block** and `aws sts get-caller-identity` before any operational command.
- **Must-know / must-avoid for the 1.3 session:**
  - Route on the **class label**, never the raw body; cross only derived data.
  - Contract-first + declarative table + pure-logic + stdlib-`unittest` (offline).
  - A routing decision is a plan of controls, **never** a verdict / forward-to-PDE.
  - Fork targets are addressable placeholders-with-contracts, **not** Phase-2 lanes.
  - The status flip 🟡 → ✅ rides a **separate paired status commit** after the
    user's confirmed live pass. Do NOT flip on inference.
- **User notes:** _(open for the user)_
