# Session Brief — Story 2.2

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.

---

## Story 2.2 — Compliance-framework mapping (NIST SP 800-53 / ISO 27001) + signature scans

| Field | Value |
|-------|-------|
| **Phase** | P2 — Parallel Inspection |
| **Date** | TBD (next session) |
| **Status** | ⬜ Not Started |
| **Builds from restore point** | none yet (Phase-1 close deferred to a governance session) |
| **Session goal** | Extend the static lane so a static finding is **mapped to the compliance control(s) it implicates** (NIST SP 800-53 Rev 5 + ISO/IEC 27001:2022 Annex A) and so **signature-based scans** for known-bad patterns / known vulnerabilities run alongside the four tools — enriching the same normalized findings shape and the same derived Hub summary. Non-executing, like 2.1. |

---

### Background & Context

Story 2.1 built the static lane: it runs cfn-lint / cfn-guard / checkov / bandit
(non-executing) over an artifact routed to `static_analysis`, normalizes their
output into **one findings shape** (`schemas/static-findings.contract.v1.json`,
Forensic S3), and crosses a bounded, derived **summary** to the Hub as the fifth
RD-013 envelope kind (`schemas/static-scan-summary.contract.v1.json`) — carrying no
verdict (a finding is EVIDENCE). 2.2 **builds on 2.1** (depends on 2.1 ✅): it adds
two enrichments to that same evidence stream:

1. **Compliance-framework mapping.** RD-004 requires the static evidence to be
   evaluated against mandated frameworks — **NIST SP 800-53 Rev 5** (catalog of
   record) and **ISO/IEC 27001:2022 Annex A** (and NIST CSF where relevant, per
   RD-014). 2.2 maps each finding's tool + native `rule_id` to the control(s) it
   implicates, so a violation is traceable to a framework control. Note the
   distinction from **RD-014 / Story G-1**: G-1 maps ZTIE's *own design artifacts*
   to controls (project self-audit); 2.2 maps *the scanned artifact's findings* to
   controls (the product ZTIE produces about a customer artifact). Reuse the
   candidate-vs-ratified discipline conceptually, but 2.2's mapping is a runtime
   finding enrichment, not the governance matrix.
2. **Signature scans.** Beyond the four config/SAST tools, run signature-based
   detection for known-bad patterns / known vulnerabilities (e.g. secret patterns,
   known-malicious snippets/IoCs). Emit as normalized findings with an appropriate
   `check_family` (a new `signature` family is likely warranted).

### Objective & Value

- **Objective:** enrich the 2.1 findings with (a) a `compliance` mapping per finding
  (or a mapping table the summary references) tying it to NIST 800-53 / ISO 27001
  controls, and (b) signature-scan findings, all in the **same** normalized shape and
  the **same** derived Hub summary. Non-executing throughout.
- **Why it matters:** the operator/report tiers (RD-006) need "which control did this
  violate"; Phase 3 correlation + the Phase 4 Security-tier report consume the
  control mappings. Signature scans catch the known-bad that lint/policy/SAST miss.

### Scope, Dependencies & Position

- **In scope:** a control-mapping mechanism (finding → NIST/ISO control ids) — decide
  contract-first whether it lives ON each finding (a `compliance` sub-object) or as a
  separate mapping artifact keyed by tool+rule_id; the signature-scan tool(s) +
  their normalization into the one findings shape (likely a `signature` check_family
  + possibly a new tool enum value — a contract version bump if so); the summary may
  gain bounded compliance roll-up fields (still no verdict); tests over fixtures;
  production code.
- **Out of scope / do NOT touch:** the dynamic lane (2.3/2.4/2.5); the parallel fork
  (2.6); the Hub verdict (a mapped finding is still EVIDENCE, never a verdict, never a
  forward-to-PDE decision); G-1's governance self-audit matrix (`docs/COMPLIANCE.md`)
  — that is ZTIE's own design mapping, a different thing. Don't edit intentional
  `{{...}}` placeholders.
- **Depends on:** **2.1 ✅**. Feeds Phase 3 correlation + the Phase 4 tiered report.

### Key design questions to settle early (contract-first)

1. **Where does the control mapping live?** On each finding (`compliance: {nist:
   [...], iso: [...]}`) vs. a separate rule→control table the findings reference. A
   contract change either way → bump `static-findings.contract.v1` to v1.1/v2 and the
   summary if it carries a compliance roll-up. Keep it an allow-list, bounded, no
   verdict.
2. **Signature source.** What provides the signatures (secret-pattern set, a known-CVE
   / IoC list, a Sigma-style ruleset)? It must be a real, non-mock source (production
   code). Decide packaging — it likely rides in the same container image (RD-021).
3. **Candidate-vs-ratified for runtime mappings.** A finding's control mapping is a
   claim; decide whether/how it is labeled (proposed) vs. asserted, mirroring RD-014's
   discipline so ZTIE doesn't overclaim "this violates control X" without basis.

### Definition of Done (this session) — a PASS/FAIL gate

The user, live in Forensic, confirms: a known-bad IaC template / script is scanned
and (a) a finding is **mapped to the correct framework control** (NIST 800-53 and/or
ISO 27001) in the findings document + reflected in the Hub summary, and (b) a
**known signature** (e.g. a planted secret or known-bad pattern) is **detected** as a
normalized finding. No artifact is executed; the pipeline does not crash on a scanner
error. Goes ✅ ONLY when confirmed live AND recorded in `RUNBOOK.md`.

---

### Lessons Learned / Carry-Forward (from the Story 2.1 build session)

Actual lessons from building 2.1 — read these before starting 2.2:

- **The static lane is contract-first with TWO homes (RD-009).** The full normalized
  findings document (`static-findings.contract.v1`) lives in **Forensic S3**
  (`findings/<intake_id>/static-findings.json`) because it may echo artifact content;
  only a bounded, verdict-free **summary** (`static-scan-summary.contract.v1`, the
  fifth Hub envelope kind, `scan` discriminator) crosses the RD-013 gate. 2.2's
  compliance/signature enrichments follow the SAME split: rich detail stays in
  Forensic, only bounded derived roll-ups cross. Do NOT put finding text or control
  rationale prose into the crossed summary — keep it a bounded roll-up.
- **The generator pattern (schemas can't be fs_write'd with a remote `$schema`).**
  Contracts are generated by `python scripts/gen_*_contract.py` via `json.dump` into
  BOTH `schemas/` and the bundled Lambda copy from one SCHEMA dict (fs_write refuses
  the remote `$schema` URL). For 2.2, if you bump the findings contract, edit the
  generator and re-run it; verify the two copies hash-match. `chmod +x` new
  generators (ruff EXE001).
- **Pure logic + thin seam is the offline-proof bar.** `normalize.py` / `toolplan.py`
  are pure and proven with **stdlib `unittest`** over FIXTURE tool outputs (16 tests);
  boto3/pytest/moto/jsonschema/aws-cdk-lib are **NOT installable** in the
  INTEGRATIONS_ONLY sandbox. Put 2.2's compliance-mapping + signature-normalization
  logic in the pure layer (a `compliance.py` mapping table + a `signatures`
  normalizer) and prove it offline; mark AWS/real-tool tests live-only/skipped. A
  **manual pure-Python conformance check** (recursive over required/
  additionalProperties/enum/const) is a good pre-live proof that built docs satisfy
  the schema when jsonschema isn't available.
- **Scanners never crash the lane.** `scanners.py` records a per-tool
  `status=error`+`error_reason` and keeps going (DoD). Add any signature tool the same
  way — a signature-engine failure must be recorded, not fatal.
- **Packaging is a container image (RD-021).** The static-scan Lambda is a
  `lambda.DockerImageFunction` (`lambdas/static_scan/Dockerfile`) because cfn-guard is
  a Rust binary. A signature tool / ruleset rides in the same image. RD-001's
  no-Docker rule is detonation-host-only — an image is fine for the non-executing
  static lane.
- **The Hub gate reuse pattern (do NOT invent a new crossing).** Add any new crossing
  field via the existing envelope-kind routing + integrity-bound conditional
  `update_item` (`attribute_exists(intake_id) AND sha256=…`; never create; never
  touch `status`/verdict) in `lambdas/hub_ingest/handler.py`. If 2.2 changes the
  summary shape, bump `static-scan-summary.contract` + its bundled copy + the pinned
  `SUMMARY_CONTRACT_VERSION`, and add gate tests (moto, live-only).
- **TS/CDK offline gotchas.** `unset NODE_OPTIONS` before tsc/prettier/npm. `npm
  install` 403s offline → cannot `cdk synth`; proof = `prettier --check` clean + `tsc
  --noEmit` showing ONLY the environmental missing-`aws-cdk-lib`/`constructs`/
  `path`/`__dirname`/`env-not-on-Props` family (identical on the live stacks).
- **Two-account live-validation reality (recurs every session).** Intake + all
  artifact-touching compute (incl. the static-scan Lambda) is in **Forensic
  (360999005254)**; the durable tracking record is in the **Hub (641628980935)**. The
  operator needs **two CloudShell tabs**; run `aws sts get-caller-identity` before
  each block. Submit `POST /intake` from a **Forensic** SigV4 principal (a Hub
  principal gets 403 — the zero-trust gate working). Query the tracking table from a
  **Hub** shell (in Forensic it's `ResourceNotFoundException`).
- **2.1 deploy shape (what 2.2 inherits).** Three stacks touched: Hub validator
  (fifth envelope kind), the intake stack (adds the Forensic static-scan work queue +
  wires the preprocessor to enqueue), and the new **`ZtieStaticScanStack`**
  (container-image Lambda). The static-scan work queue is created in the **intake
  stack**; the static-scan stack imports the artifact bucket + work queue + Hub queue
  by context. Deploy order: Hub → intake → static-scan. 2.2 most likely edits the
  static-scan Lambda + its contracts + possibly the Hub gate, redeploying those.
- **2.1 validation status watch-item.** 2.1 is 🟡 (built, PR open) at the time this
  brief is authored. Per the covenant, **2.2 cannot BEGIN until 2.1 is ✅** (recorded
  live pass). Run STEP 0: confirm 2.1's live validation was recorded + flipped ✅ on
  `main`; if 2.1 is still 🟡, the focus is finishing 2.1's validation, not starting
  2.2. Also confirm no early-merge drift (the fix-commits-after-merge watch-item).
- **2.0 still 🟡 (unrelated to 2.2).** 2.0 (infra foundation) was 🟡 through the 2.1
  session; it blocks 2.3 (detonation), not 2.2.

Additional hard-won lessons from the 2.1 **live validation** (not pre-run guesses):

- **cfn-guard 3.x SARIF needs BOTH `--structured` AND `--show-summary none`.** The
  first live IaC scan errored `the structured flag must be set when output is set to
  sarif`; adding `--structured` alone then errored `Cannot provide a summary-type
  other than none when the structured flag is present`. The working invocation is
  `cfn-guard validate --data <f> --rules <r> --output-format sarif --structured
  --show-summary none` (verified in-container producing clean SARIF, exit 19 =
  violations found = our `ok`). If 2.2 adds/changes any cfn-guard invocation, keep
  that flag trio. Fixes landed as branch commits `5e9391d` + `730034a`.
- **The Hub ingest-queue sender grant is REPLACE, not append.** `ZtieHubTrackingStack`
  rewrites the queue resource policy from exactly the `forensic*RoleArn` context
  values you pass on THAT deploy. Deploying it with only one role ARN (e.g. just
  `forensicStaticScanRoleArn`) **drops** the intake + preprocessor senders and their
  `SendMessage` starts failing (`AccessDenied ... no resource-based policy allows
  sqs:SendMessage`). ALWAYS pass **all three** on any Hub deploy:
  `-c forensicIntakeRoleArn=… -c forensicPreprocessorRoleArn=… -c
  forensicStaticScanRoleArn=…`. (Story 2.2 will likely reuse the static-scan role, so
  no new sender — but any Hub redeploy must still pass all three.)
- **Container-image Lambda deploy needs Docker → a build box, not CloudShell.** 2.1's
  `ZtieStaticScanStack` (and any 2.2 image change) must be `cdk deploy`'d from a
  Docker-capable host with Forensic creds. We used a disposable `t3.large` AL2023 EC2
  in Forensic (instance profile `ztie-build-box` = Admin + SSM, connect via
  `aws ssm start-session`, UserData installs docker+node20+cdk). It is NOT
  architectural — terminate it when done (or keep it for 2.2 and kill later). A
  future AWS-native improvement is CodeBuild for the image build (no EC2).
- **CDK asset "(no changes)" trap.** If `cdk deploy` says `(no changes)` but you know
  the Lambda code changed, the working tree is almost certainly a STALE clone/branch
  (we hit an old `feature/story-1.4` + `feature/story-2.0` clone, plus an accidental
  nested clone under `infra/`). Always `git reset --hard origin/feature/story-2.2`
  and verify a known file's size/marker before deploying; `rm -rf cdk.out`.
- **Two-tab / wrong-account recurs.** A `ResourceNotFoundException` on the tracking
  table means you queried it from Forensic — the table is in the Hub. Intake API 4xx
  `Request body must be valid JSON` means you posted raw YAML — the intake contract is
  a JSON body with the artifact in `content_base64` (base64), plus `filename`; build
  it with a small python `base64.b64encode` step, submit with `awscurl -d @file.json`.
- **When a `$VAR` submission check reads stale data,** it's usually an unset variable
  (pasting the literal `<placeholder>`) causing the S3 read to hit an old/empty path —
  set the id explicitly and check `scanned_at` in the doc to confirm you're reading
  the run you just triggered.

### Management-artifact obligations (RD-015)

- [ ] Fill this brief's As-built once the story is built.
- [ ] RUNBOOK 2.2 detail block + summary row; keep PROJECT_PLAN ↔ RUNBOOK aligned.
- [ ] Any contract version bump (findings/summary) recorded; any new registered decision + candidate control mapping proposed.
- [ ] On validation pass: record Validation Result + flip ✅ (paired commit).
- [ ] Author the next-story handoff (2.3 detonation — needs 2.0 ✅ — or 2.6 fork per readiness) with Lessons Learned.
