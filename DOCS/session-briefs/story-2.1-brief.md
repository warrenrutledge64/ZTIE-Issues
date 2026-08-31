# Session Brief — Story 2.1

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.

---

## Story 2.1 — Static scanning stack (cfn-lint, cfn-guard, checkov, bandit)

| Field | Value |
|-------|-------|
| **Phase** | P2 — Parallel Inspection |
| **Date** | TBD (next session) |
| **Status** | ⬜ Not Started |
| **Builds from restore point** | none yet (Phase-1 close deferred to a governance session) |
| **Session goal** | Build the **static-analysis lane**: a non-executing scanning stack that runs **cfn-lint, cfn-guard, checkov, and bandit** over an artifact routed to `static_analysis`, and emits **structured JSON findings** — the first Phase-2 lane and a Phase-3 correlation input. Non-executing only: it reads/parses the artifact, it never runs it. |

---

### Background & Context

Phase 1 is complete. Phase 2 forks into a **static** lane (this story) and a
**dynamic** detonation lane (2.3, which needs the 2.0 infra foundation). Story 1.3's
router names the `static_analysis` lane for `iac_template` and `raw_script` classes;
2.1 is the concrete destination for that lane. It runs in the **Forensic account
(360999005254)** because it touches the raw artifact (RD-008), but — unlike the
dynamic lane — it **never executes** the artifact; it statically inspects it.

**2.1 depends on 1.3 ✅ only** (it consumes the routing decision that names the
static lane). It does **not** depend on 2.0 — static scanning needs no VPC/EC2/launch
template. So 2.1 can proceed independently of whether 2.0 has been validated yet.

### Objective & Value

- **Objective:** a static-scan runner that, for an artifact routed to
  `static_analysis`, invokes the four scanners appropriate to its class —
  **cfn-lint / cfn-guard / checkov** for IaC templates, **bandit** (Python SAST) +
  **checkov** for scripts — normalizes their outputs into one **structured JSON
  findings** document (a derived artifact), and records that a static scan
  completed on the **Hub** tracking record via the same RD-013 data-contract gate.
  Emits JSON results for Phase-3 correlation. (RD-004.)
- **Why it matters:** this is one of the two evidence streams Nova Pro correlates in
  Phase 3. Without structured static findings there is nothing to cross-reference
  against dynamic behavior, and no false-positive elimination.

### Scope, Dependencies & Position

- **In scope:** the scanner-invocation + output-normalization logic (pure where
  possible; the four tools behind a thin seam); a **findings JSON contract**
  (contract-first, like every prior story); the Forensic-side wiring that reads the
  artifact (bounded), runs the scanners, writes the findings JSON (Forensic S3), and
  crosses a derived "static scan complete + summary counts" envelope to the Hub via
  the RD-013 gate; production code; offline-provable tests over fixture scanner
  outputs.
- **Out of scope / do NOT touch:** compliance-framework mapping + signature scans
  (that is **2.2**, which depends on 2.1); the detonation/dynamic lane (2.3/2.4/2.5);
  the parallel fork/orchestration (2.6 — 2.1 just needs to be an addressable lane
  entry); the Hub verdict (a scan finding is **evidence**, never a verdict). Don't
  edit intentional `{{...}}` placeholders.
- **Depends on:** **1.3 ✅**. Feeds **2.2** and the fork (**2.6**); its JSON is a
  **Phase-3** input.

### Key design questions to settle early (contract-first)

1. **What crosses to the Hub vs. what stays in Forensic?** Per RD-009/RD-012 the raw
   findings (which may echo artifact content) stay in Forensic (S3); only a
   **derived, bounded summary** (scan-complete flag, per-tool finding counts,
   highest severity, a pointer/id) crosses the gate. Design the findings-summary
   contract as a **fifth envelope kind** on the existing Hub gate, integrity-keyed by
   `intake_id` + `sha256`, allow-list, no verdict field.
2. **How are the scanners packaged/invoked?** cfn-lint/checkov/bandit are Python
   (pip); cfn-guard is a Rust binary. Decide the runtime (Lambda with a bundled
   layer, or a container-image Lambda, or run them on a small Forensic compute) —
   **static scanning is non-executing, so a container image here is a packaging
   choice, NOT the forbidden detonation-Docker** (the no-Docker rule is specifically
   about the *dynamic detonation* host per RD-001). Confirm the packaging approach
   against the AWS-native + production-code constraints before building.
3. **Normalization schema:** one shared findings shape across all four tools
   (tool, rule id, severity, resource/location, message) so Phase 3 consumes one
   format. This is a candidate for the shared event/telemetry schema package the
   plan calls for.

### Definition of Done (this session) — a PASS/FAIL gate

The user, live in Forensic, confirms: a **known-bad** IaC template and a
**known-bad** script are each statically scanned by the appropriate tools; a
**structured JSON findings** document is produced (inspectable) with real findings;
the derived scan-complete summary lands on the Hub tracking record (queryable by
`intake_id`); no artifact is executed; the pipeline does not crash on a scanner
error. Goes ✅ ONLY when confirmed live AND recorded in `RUNBOOK.md`.

---

### Lessons Learned / Carry-Forward (from the Story 2.0 build session)

Actual lessons from building 2.0 — read these before starting 2.1:

- **The `unset NODE_OPTIONS` gotcha (TS work).** In the build sandbox a broken
  `NODE_OPTIONS` preload makes `tsc`/`prettier`/`npm` crash with `MODULE_NOT_FOUND`
  on `internal/preload`. **`unset NODE_OPTIONS` first** and they work. (For 2.1's
  Python code this bites less, but any TS infra edits need it.)
- **Offline proof bar for CDK/TS.** The sandbox is INTEGRATIONS_ONLY: `npm install`
  hits the registry and gets **403** (no `aws-cdk-lib`, no `node_modules`), so you
  **cannot `cdk synth`/`deploy`** and `tsc --noEmit` **will** report
  `Cannot find module 'aws-cdk-lib'` + cascading `env`/`region` "not on type"
  errors. That error family is **environmental, not a defect** — it appears
  identically on the already-live-validated stacks. Proof = **`prettier --check`
  clean** + **`tsc` shows only that missing-dep family** (filter it out to confirm
  no genuine errors). For Python, the real proof is stdlib-`unittest` (no pip):
  boto3/pytest/moto are **not installable offline** — mark AWS-touching tests
  live-only/skipped and prove the **pure** logic offline (the 1.2/1.3/1.4 pattern).
- **`gh`/bash cannot see agent-written `/tmp` files.** When opening a PR with a body
  file, write the body via a **bash heredoc** into a bash-visible path first, THEN
  `gh api ... -F body=@file`. `gh pr create` is still broken — use
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls -f title=... -F body=@file
  -f head=feature/story-2.1 -f base=main --jq .html_url`.
- **Contract-first keeps paying off.** Every P1 story and 2.0's outputs went smoother
  by fixing the derived shape first. For 2.1, settle the **findings-summary Hub
  envelope** (fifth kind) and the **normalized findings JSON** shape before writing
  scanner glue. Reuse the existing Hub-gate envelope-kind routing +
  integrity-bound conditional `update_item` pattern (`lambdas/hub_ingest/handler.py`)
  — do not invent a new crossing mechanism.
- **Two-account validation reality (recurs every session).** The intake API + all
  artifact-touching compute is in **Forensic**; the durable tracking record is in the
  **Hub**. The operator needs **two CloudShell tabs** and must run
  `aws sts get-caller-identity` before each block. Submit from a **Forensic** SigV4
  principal (a Hub SSO principal gets 403 — that is the zero-trust gate working);
  query the tracking table from a **Hub** shell (querying it in Forensic gives
  `ResourceNotFoundException`).
- **2.0 handoff state:** `ZtieForensicInfraStack` gives 2.3 (not 2.1) its VPC + launch
  template. If 2.0 is still 🟡 when 2.1 runs, that is fine — **2.1 does not depend on
  2.0.** But before starting 2.1, run STEP 0 and, if 2.0's validation completed, make
  sure its status was flipped and reconciled on `main` (the "early-merge fix drift"
  watch-item).
- **CDK string-literal charset (real 2.0 defect, live-only):** if you touch a CDK
  stack, any string that reaches AWS — **security-group rule/group descriptions
  especially** — must be plain-ASCII from EC2's set `a-zA-Z0-9. _-:/()#,@[]+=&;{}!$*`.
  A `>` (in `->`) made 2.0's SG `CREATE_FAILED`; `cdk synth`/`tsc` did NOT catch it.
  Avoid `->` and `—` in those literals.
- **Image Builder AMI status (corrected live 2026-08-31, matters for 2.3 not 2.1):**
  the SSM param `/ztie/ami/ubuntu-22.04` did **NOT** exist in Forensic and the old
  `ami-088e04fb4c75334c4` is **gone** from this account/region. For 2.0 we put a
  **stock Ubuntu 22.04 AMI** (`ami-040dc3b259ece28c6`) into the param as a
  placeholder (the launch template is parametric, so this needs no code change).
  **Story 2.3 must build/wire the real golden AMI into `/ztie/ami/<flavor>` and fix
  the failed AL2023 Image-Builder build + the broken EventBridge→Lambda SSM-update
  automation.** 2.1 (static scanning) needs no AMI.
- **A first-create CFN failure leaves the stack `ROLLBACK_COMPLETE`** — you must
  `delete-stack` + `wait stack-delete-complete` before re-deploying.

### Management-artifact obligations (RD-015)

- [ ] Fill this brief's As-built once the story is built.
- [ ] RUNBOOK 2.1 detail block + summary row; keep PROJECT_PLAN ↔ RUNBOOK aligned.
- [ ] Any new registered decision (e.g. scanner packaging choice) recorded + candidate control mapping proposed.
- [ ] On validation pass: record Validation Result + flip ✅ (paired commit).
- [ ] Author the next-story handoff (2.2 or 2.3 per readiness) with Lessons Learned.
