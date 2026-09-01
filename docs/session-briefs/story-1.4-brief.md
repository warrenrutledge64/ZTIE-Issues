# Session Brief — Story 1.4

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.

---

## Story 1.4 — Safe-reject path for unknown/incompatible types

| Field | Value |
|-------|-------|
| **Phase** | P1 — Intake & Routing |
| **Date** | 2026-08-27 |
| **Status** | ✅ Done — validated live 2026-08-27 |
| **Builds from restore point** | none yet (Phase-1 close captures the first tag, after 1.2/1.3/1.4 + validated 1.R) |
| **Session goal** | Implement the **safe-reject** path that Story 1.3 hands the `safe_reject` lane off to: an `other_unknown` / unroutable / incompatible artifact is rejected **cleanly and terminally** — recorded as safe-rejected on the Hub tracking record, never entered into a scanner/detonation lane, and never crashing the pipeline. |

---

### Background & Context

Phase 1 is Intake & Routing. 1.1 ✅ (intake gateway), 1.1R ✅ (durable record → Hub
behind the RD-013 gate), 1.R ✅ (restore mechanism), 1.2 ✅ (classifier → derived
class label), **1.3 🟡→✅** (routing table → a routing DECISION that names the
`safe_reject` lane for `other_unknown`/unroutable classes). **1.4 owns what happens
at that `safe_reject` lane:** it is the resilience criterion of the whole phase — an
incompatible/unknown artifact must be refused *safely* so an incompatible scan never
runs and never crashes the pipeline. (1.3 must be ✅ live before 1.4 begins — the
advancement gate; 1.4 pairs with 1.3.)

### Objective & Value

- **Objective:** a **safe-reject handler** — the concrete destination for the
  `safe_reject` lane the 1.3 router emits. It marks the artifact safe-rejected on the
  **Hub** tracking record (a derived, contract-shaped status update crossing the same
  RD-013 gate), does NOT forward it to any Phase-2 lane, and terminates the artifact's
  ZTIE flow cleanly. Per RD-010, an artifact that never reaches the human accept/reject
  gate but is refused up front should have its Forensic raw body handled per the
  ephemeral-cleanup discipline (decide: destroy-now vs. leave to the S3 lifecycle/TTL —
  align with RD-010/RD-012).
- **Why it matters:** this is the pipeline's **fail-safe**. Without it, an unroutable
  artifact would either dead-end silently or be forced into a scanner that cannot
  handle it (a crash). 1.4 makes "we don't know what this is" a **clean, recorded,
  terminal outcome**, not an error.

### Scope, Dependencies & Position

- **In scope:** the safe-reject handler (contract-first, like 1.2/1.3); the
  safe-reject as a derived, recorded terminal status on the Hub record (no verdict
  self-assertion — a safe-reject is a *processing outcome*, distinct from the
  human PASS/FAIL/INCONCLUSIVE verdict; confirm this framing early against RD-010);
  clean handling of the Forensic ephemeral body; production code; pure decision logic
  + thin AWS seam; offline-provable stdlib `unittest` tests.
- **Out of scope / do NOT touch:** the router (1.3 — 1.4 only *consumes* the
  `safe_reject` lane), the classifier (1.2), the Hub contract gate internals beyond
  adding the safe-reject status path, any Phase-2 scanning/detonation. Don't edit
  intentional `{{...}}` template placeholders.
- **Depends on:** **1.3 ✅** (the router must name the `safe_reject` lane). Pairs with
  1.3.
- **Unblocks:** the **Phase-1 close** (1.4 is the phase's resilience criterion; with
  1.2/1.3/1.4 routing correctly AND 1.R ✅, capture `restore/phase-1-green`).
- **Roadmap position:** the last Phase-1 story; the fail-safe branch of the fork.

### Approach & Constraints

- **Approach:** contract-first — decide the SHAPE of the safe-reject outcome BEFORE
  the code (a fourth crossing kind on the RD-013 gate, OR an extension of a status
  update — decide early whether it is its own envelope or a status transition on the
  existing record; prefer the smallest contract that records *terminal safe-rejected*
  + *why* without carrying a verdict). Keep the decision a **pure function**; put any
  boto3 behind the thin `awsio` seam. **Zero-trust:** a safe-reject is a terminal
  processing outcome, NOT a human verdict and NOT a forward decision — it must be
  clearly distinguishable from PASS/FAIL/INCONCLUSIVE (which stay Hub-side/human-gated,
  Phase 4).
- **Hard constraints:** **Python 3.12** (project standard). **Production code** — real
  terminal handling, real cleanup of the ephemeral body, never crash on any input.
  AWS-native. **Validation-gated**: the user validates live and the result is recorded
  in `RUNBOOK.md`.

### Validation Rationale & Compliance Mapping (REQUIRED — RD-014)

- **Rationale:** safe-reject is a **resilience / graceful-degradation** control — the
  system refuses an input it cannot safely process instead of failing open or crashing.
- **Candidate control mappings** *(candidate-until-ratified; also add ratified rows to
  [`../COMPLIANCE.md`](../COMPLIANCE.md)):*

| Framework | Control ID | Control Name | Rationale | Status |
|-----------|-----------|--------------|-----------|--------|
| NIST 800-53 r5 | SI-10 | Information Input Validation | Unroutable/incompatible input is refused cleanly rather than processed | Proposed |
| NIST 800-53 r5 | SC-5 | Denial-of-Service Protection | An incompatible scan can never crash the pipeline (resilience) | Proposed |
| NIST 800-53 r5 | CM-7 | Least Functionality | Refused artifacts never enter a scanner/detonation lane | Proposed |
| NIST 800-53 r5 | SI-11 | Error Handling | Failure is handled as a clean, recorded, terminal outcome (no unsafe crash) | Proposed |
| ISO 27001:2022 | A.8.26 | Application security requirements | Class-appropriate, fail-safe handling of validated input | Proposed |

- **Audit evidence produced:** the safe-reject records + the live validation run.

### Management-Artifact Obligations (REQUIRED — RD-015)

- [ ] Story's **brief + runbook entry** updated (status, validation result, dates).
- [ ] **PROJECT_PLAN and RUNBOOK in exact alignment**.
- [ ] Candidate control mappings recorded (RD-014).
- [ ] All doc changes **PR-reviewed** (branch + PR, never straight to main).
- [ ] Phase-1 close: once 1.4 is ✅ (and 1.2/1.3 ✅, 1.R ✅), reflect final state in
      `BOM.md` and capture `restore/phase-1-green` (tag + manifest) via `ztie-restore`.

### Change & Rollback

- **Change type:** normal (adds the safe-reject handler + its contract/status path).
- **Restore point this builds from:** none (Phase-1 close is captured *after* 1.4).
- **Backout plan:** revert the merged PR; safe-reject is additive on the routing
  decision and does not mutate the router/classifier/intake path.

### Definition of Done / Validation Gate

- **Done means:** the user, live, submits an unknown/unsupported artifact (an
  `other_unknown` that 1.3 routes to `safe_reject`) and confirms it is **rejected
  cleanly** — recorded as safe-rejected on the Hub record (queryable by `intake_id`),
  **not** forwarded to any scanner/detonation lane, and the pipeline does **not**
  crash. Confirm a routable artifact (IaC/script) is *not* safe-rejected (the branch
  is selective).
- **Validated by:** the user, live (Forensic intake → classify → route → safe-reject).
- **Validation Result:** _pending._
- **On pass (and only then):** record the dated Validation Result + flip 1.4 ✅, then
  proceed to the **Phase-1 close** (capture `restore/phase-1-green`).
- **On fail:** stays 🟡; next session re-focuses on 1.4.
- **Advancement gate:** required for the P1 gate (resilience criterion) + the P1 close.

### Risks & Watch-Items

- **Safe-reject ≠ verdict.** A safe-reject is a *terminal processing outcome* (we
  could not route this), NOT the human PASS/FAIL/INCONCLUSIVE verdict. Keep it clearly
  distinct on the record and out of the verdict slot — the verdict stays
  Hub-side/human-gated (Phase 4). Do not let a safe-reject masquerade as a FAIL.
- **Never crash, never drop.** The whole point: any input reaching the safe-reject
  lane is refused *cleanly* and *recorded*. No unhandled exception, no silent dead-end.
- **Ephemeral-body handling.** Decide (against RD-010/RD-012) whether the Forensic raw
  body is destroyed immediately on safe-reject or left to the S3 lifecycle/TTL. Either
  way it stays in Forensic; the Hub only records the derived outcome.
- **Contract-first + pure-logic + stdlib-`unittest`** — proven four times now (1.R,
  1.2, 1.3); do it again. If safe-reject crosses to the Hub it is a FOURTH envelope
  kind (or a status transition) on the same RD-013 gate — extend `hub_ingest`'s
  `_process_record` router the same way, integrity-bind by `intake_id`+`sha256`,
  fail-closed quarantine, and expect the label/routing/reject ordering races.

### Lessons Learned / Carry-Forward *(carried from the Story 1.3 build session, 2026-08-25)*

- **From 1.3 — what to reuse (it worked cleanly a FOURTH time):**
  - **Contract-first via `python json.dump`.** `scripts/gen_routing_contract.py` wrote
    `routing.contract.v1.json` (draft-07, allow-list, `additionalProperties:false`
    everywhere, integrity-keyed by `intake_id`+`sha256`) into **both** `schemas/` and
    the bundled `lambdas/hub_ingest/` copy from one source (`fs_write` refuses a remote
    `$schema` URL). Both were **byte-identical** (verified with `sha256sum`). Do the
    same for any safe-reject contract — add a `scripts/gen_*_contract.py`.
  - **Declarative table + pure logic + thin `awsio` seam.** `router.py` was a pure
    `route(artifact_class)` over an immutable `_ROUTING_TABLE` dict (use a
    `tuple[str, ...]` value so ruff's RUF012 does not fire and the table can't be
    mutated) → **12 stdlib-`unittest` tests pass offline**. The boto3 lives only in
    `awsio.py`; `handler.py` is the glue. Keep the safe-reject *decision* pure and put
    the record-update / body-cleanup behind `awsio`.
  - **Third/fourth envelope kind on the same Hub gate.** `hub_ingest/handler.py`
    dispatches by envelope KIND in `_process_record` (`routing` in envelope → routing;
    `classification` in envelope → classification; else intake). Each kind:
    fail-closed validate → **integrity-bound conditional `update_item`**
    (`attribute_exists(intake_id) AND sha256 = <sha>`) that **never creates a record,
    never touches `status`/verdict**. The classification and routing paths now share
    `_resolve_conditional_apply_failure(...)` (returns `True` = retryable ordering
    race → re-raise so SQS redelivers; `False` = sha mismatch → already quarantined).
    A safe-reject that crosses to the Hub should reuse this exact shape — add
    `_is_reject_envelope` + `_process_reject` + reuse the shared helper.
  - **Conformance test that skips offline / runs live.** `test_*_conformance.py`
    guarded by `try: import jsonschema` (skips in the INTEGRATIONS_ONLY sandbox, runs
    under pytest live). Plus a **manual stdlib schema-constraint check** (load the
    schema JSON, assert the pure output's keys ⊆ properties, enums, bounds) gives
    offline confidence without PyPI. Do both.
  - **The router emits the routing envelope from the SAME preprocessor handler**, as a
    second `SendMessage` after the classification envelope (`awsio.send_routing_
    envelope`). If safe-reject is emitted Forensic-side too, follow this pattern; if it
    is a Hub-side reaction to the routing decision, decide that early (the 1.3 brief's
    "Forensic-event vs Hub-projection" question applies again).
- **From 1.3 — environment truths (unchanged, do NOT relearn):**
  - Sandbox is **INTEGRATIONS_ONLY**: **PyPI + npm blocked**. You cannot run
    `pytest`/`moto`/`boto3`/`cdk`/`tsc` here. **Build + hand off; the USER validates
    live.** Never claim live tests/synth/deploy pass from the sandbox.
  - **Local proof that DOES work offline (all green for 1.3):** `python3 -m py_compile`,
    `~/.pyenv/versions/3.12.13/bin/ruff check`, `python3 -m unittest`, and `prettier`
    via `npx --no-install --check` **after `unset NODE_OPTIONS`** run **from `infra/`**
    (prettier is scoped to the TS/infra code — **Markdown files are NOT
    prettier-clean in this repo**, `README.md`/`METHODOLOGY.md` also warn, so do NOT
    try to prettier-format the docs).
  - **Ruff default set:** clean on the first try for 1.3 by using an **immutable
    `tuple` for the table** (avoids RUF012) and letting imports sort naturally (I001).
    Watch: `EXE001` — a `#!`-shebang file must be `chmod +x` (I `chmod +x`'d
    `gen_routing_contract.py`). Do NOT add `# noqa` for non-enabled rules (unused
    RUF100). If you factor an `except`-handler branch into a helper, avoid a **bare
    `raise` inside the helper** — return a bool and let the caller re-raise (I did this
    with `_resolve_conditional_apply_failure`), which is clean and unambiguous.
  - **`gh pr create` is broken here** — open PRs with
    `gh api repos/warrenrutledge64/ZTIE-Issues/pulls -f title=... -F body=@file
    -f head=... -f base=main --jq .html_url`. Push to `feature/story-1.4`.
- **From 1.3 — the true state you inherit:**
  - **1.3 is 🟡 pending the user's live validation (PR #19, branch
    `feature/story-1.3`).** Local proof green (12 offline router unittest tests + 8
    live hub-gate routing tests authored; ruff/prettier/py_compile clean; schemas
    byte-identical). **FIRST action next session:** check whether the user validated
    1.3 live. **On pass:** record the dated Validation Result + flip 1.3 ✅ (paired
    status commit) THEN start 1.4. **On fail / not yet:** 1.3 stays 🟡 and the session
    objective becomes fix + re-validate 1.3 — do NOT start 1.4. (Advancement gate:
    1.4 depends on 1.3 ✅.)
  - **1.3 live-validation runbook is in `story-1.3-brief.md`** ("Live validation
    runbook"): redeploy Hub then Forensic (additive), submit an IaC template
    (`stack.yaml`), a bash script (`deploy.sh`), and a plain-text unknown; then
    `aws dynamodb get-item` from the HUB shell to confirm each record's
    `routing.lanes`/`routing_lanes` (`[static_analysis, dynamic_detonation]` for the
    first two, `[safe_reject]` for the unknown), `routing.routable`, `routing.basis`,
    and that **no verdict/forward field crossed** and `status` is still `RECEIVED`.
  - **What 1.3 added:** `schemas/routing.contract.v1.json` (+ bundled
    `lambdas/hub_ingest/` copy) + `scripts/gen_routing_contract.py`;
    `lambdas/preprocessor/router.py` (pure declarative table) + `router` import,
    `_build_routing_envelope`, and the routing emit in `handler.py`;
    `awsio.send_routing_envelope`; the routing envelope kind + `_validate_routing_
    contract` + `_apply_routing` (SET `routing`/`routing_lanes`/`routed_at`) + the
    shared `_resolve_conditional_apply_failure` in `hub_ingest/handler.py`;
    `ROUTING_CONTRACT_VERSION=1.0` on the preprocessor Lambda in
    `ztie-intake-stack.ts`. The routing decision lands on the Hub record as
    `routing` (+ flat `routing_lanes`) + `routed_at`, keyed by `intake_id`.
  - **Lane vocabulary (the addressable fork targets):** `static_analysis` (Story 2.1
    static lane), `dynamic_detonation` (Story 2.3 dynamic lane), `safe_reject`
    (**this story, 1.4**). Both routable classes fork into both Phase-2 lanes;
    `other_unknown`/unroutable → `[safe_reject]`. **1.4 implements the `safe_reject`
    destination.**
  - **Contracts live in `schemas/`** (`intake-tracking`, `classification`, `routing`)
    with byte-identical bundled copies in `lambdas/hub_ingest/`; `schemas/README.md`
    documents all three. Add any safe-reject contract there and keep the copies in
    sync (verify by `sha256sum`; the G-2 checker is not built yet).
  - **`git` truth at handoff:** `main` clean; **PR #19 (1.3) OPEN** on branch
    `feature/story-1.3`. Re-run STEP 0 at session start (git pull, list open PRs). If
    #19 merges before the live green run and the live run produced fixes, reconcile
    the base branch with a follow-up PR so `main` holds the validated code (the early-
    merge lesson).
- **CloudShell operator lessons (still true):** run commands **one line at a time**
  (a multi-line paste landing in `input()` was the 1.R "typed y but aborted"); **`/tmp`
  is wiped on session recycle** (regenerate any exported file before it is consumed);
  the intake API is **IAM/SigV4 in FORENSIC** (submit from a Forensic principal — a Hub
  SSO principal gets 403) and the tracking table is in the **HUB** (verify from a Hub
  shell — Forensic gives ResourceNotFoundException), so **two CloudShell tabs** and
  `aws sts get-caller-identity` before every operational block.
- **Must-know / must-avoid for the 1.4 session:**
  - A safe-reject is a **terminal processing outcome**, NOT a verdict and NOT a
    forward — keep it distinct from PASS/FAIL/INCONCLUSIVE (Hub-side/human-gated).
  - Contract-first + pure-logic + declarative + stdlib-`unittest` (offline).
  - **Never crash, never drop** — the whole point of the story.
  - Decide Forensic-body cleanup against RD-010/RD-012; the raw body stays in
    Forensic, the Hub records only the derived outcome.
  - The status flip 🟡 → ✅ rides a **separate paired status commit** after the user's
    confirmed live pass. Do NOT flip on inference.
  - After 1.4 ✅ (with 1.2/1.3 ✅ and 1.R ✅), do the **Phase-1 close**: `BOM.md` +
    `restore/phase-1-green` capture via `ztie-restore`.
- **User notes:** _(open for the user)_
