Story 2.2 (executor-facing)
You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting. Do NOT change anything until you have (a) READ the
plan + runbook, (b) re-established true state (STEP 0), and (c) confirmed the
advancement gate.

# PROJECT IDENTITY
ZTIE is a four-phase AWS-native security pipeline that inspects every untrusted
artifact BEFORE it reaches the PDE. Three accounts: Pipeline-Hub (641628980935) =
brains/control plane + durable record; Forensic (360999005254) = self-contained
blast zone (ephemeral only); Pipeline-Sandbox (586917955591) = ZTIE→PDE handoff.
Story 2.2 EXTENDS the Phase-2 STATIC lane (built in 2.1): it adds (1) COMPLIANCE-
FRAMEWORK MAPPING — mapping each static finding to the NIST SP 800-53 Rev 5 and
ISO/IEC 27001:2022 Annex A control(s) it implicates (RD-004/RD-014) — and (2)
SIGNATURE-BASED SCANS for known-bad patterns / known vulnerabilities, both
enriching the SAME normalized findings shape and the SAME derived Hub summary that
2.1 established. NON-EXECUTING, like 2.1: it inspects/parses the artifact, never
runs it.

# NON-NEGOTIABLE CONSTRAINTS
- PYTHON-FIRST. Python 3.12. Bash only for trivial glue.
- NON-EXECUTING. 2.2 inspects; it must NEVER execute the artifact (execution is the
  dynamic lane, 2.3, on the isolated EC2 host).
- FORENSIC ACCOUNT (360999005254) — it touches the raw artifact + the full findings
  document, so it runs in the blast zone (RD-008). Only DERIVED, bounded data
  crosses to the Hub (RD-009/012/013).
- CONTRACT-FIRST. Decide the SHAPES first. 2.2 will likely (a) extend the normalized
  findings contract with a per-finding `compliance` mapping (and a `signature`
  check_family / possibly a new tool enum) and (b) extend the Hub summary with a
  bounded compliance roll-up — a VERSION BUMP of `static-findings.contract` and/or
  `static-scan-summary.contract` (v1.1/v2). Emit every schema via a `python
  json.dump` generator (fs_write refuses a remote `$schema` URL); write BOTH the
  canonical schemas/ copy and any bundled lambda copy from one source so they can't
  drift; verify hash-match. Bump the pinned CONTRACT_VERSION if the crossed shape
  changes, and keep the Hub validator's version pin in sync.
- EVIDENCE, NEVER A VERDICT. A mapped finding / a signature hit is EVIDENCE. NO
  verdict / safe / approved / forward / pass_fail field — anywhere. The verdict is
  Hub-side / human-gated (Phase 4). A control mapping says "this finding implicates
  control X," never "this artifact fails."
- SELF-AUDIT vs PRODUCT MAPPING — do not conflate. RD-014 / Story G-1 maps ZTIE's
  OWN design artifacts to controls in `docs/COMPLIANCE.md` (project governance). 2.2
  maps the SCANNED ARTIFACT'S findings to controls (the product ZTIE emits about a
  customer artifact). 2.2 does NOT edit the G-1 governance matrix.
- PURE LOGIC + THIN SEAM. Put the compliance-mapping table + signature normalization
  in the PURE layer (offline-testable); keep tool/engine invocation behind the thin
  subprocess/awsio seams. A tool/engine error must NOT crash the lane (record it
  per-tool, keep going — the 2.1 pattern).
- PRODUCTION CODE. No mock mappings, no fake signatures. Real control-mapping source,
  a real signature source/ruleset, real findings. VALIDATION-GATED: nothing is
  "done" on inference — the USER validates live and the result is RECORDED in
  RUNBOOK.md.

# OPERATIONAL CONTEXT (state this on EVERY command block)
  Build sandbox is INTEGRATIONS_ONLY (NO AWS creds; PyPI + npm BLOCKED —
  boto3/pytest/moto/jsonschema/aws-cdk-lib NOT installable). You BUILD + hand off;
  the USER runs the live validation in CloudShell (ambient creds, no --profile).
  Region us-east-1. Confirm the active account with `aws sts get-caller-identity`
  before every operational block. The intake API + static-scan lane are in FORENSIC
  (360999005254); the tracking table is in the HUB (641628980935) — the operator
  needs TWO CloudShell tabs. Submit POST /intake from a FORENSIC SigV4 principal (a
  Hub principal gets 403 — the zero-trust gate); query the tracking table from a HUB
  shell (querying it in Forensic gives ResourceNotFoundException).

# HARD-WON LESSONS (do NOT repeat) — carried from the 2.1 build session
- Offline proof bar: prove PURE logic (mapping table, signature normalizer,
  document/summary assembly) with stdlib `unittest` over FIXTURE tool outputs; mark
  AWS-touching + real-tool tests live-only/skipped. A manual pure-Python conformance
  check (recursive over required/additionalProperties/enum/const) proves built docs
  satisfy the schema when jsonschema isn't installable. ruff for lint (fix BLE001 on
  intentional swallows with `# noqa: BLE001`; `chmod +x` new generator scripts for
  EXE001).
- Two homes (RD-009): the full findings document stays in FORENSIC S3
  (`findings/<intake_id>/static-findings.json`); only a bounded, verdict-free SUMMARY
  crosses to the Hub (fifth envelope kind, `scan` discriminator). Keep 2.2's rich
  compliance rationale / signature detail in the Forensic document; cross only
  bounded roll-ups. Do NOT invent a new crossing — reuse the Hub-gate envelope-kind
  routing + integrity-bound conditional update_item pattern in
  lambdas/hub_ingest/handler.py.
- Container-image packaging (RD-021) is already in place for the static-scan Lambda
  (lambdas/static_scan/Dockerfile, lambda.DockerImageFunction). A signature engine /
  ruleset rides in that same image. RD-001's no-Docker rule is detonation-host-only.
- TS/CDK: `unset NODE_OPTIONS` first; `npm install` 403s offline so you CANNOT `cdk
  synth`/`deploy` — proof is `prettier --check` clean + `tsc --noEmit` showing ONLY
  the environmental missing-`aws-cdk-lib`/`constructs`/`path`/`__dirname`/
  `env-not-on-Props` family (identical on the live stacks).
- Opening the PR: `gh pr create` is BROKEN. Write the PR body via a bash heredoc into
  a bash-visible path (agent-written /tmp files are NOT visible to gh/bash), then:
  gh api repos/warrenrutledge64/ZTIE-Issues/pulls -f title=... -F body=@file
  -f head=feature/story-2.2 -f base=main --jq .html_url

# FIRST — VALIDATION & ADVANCEMENT GATE (do this BEFORE any new work)
# Binding policy: RUNBOOK.md "Validation & Advancement Gate".
# 1. Close out Story 2.1: it was 🟡 (built, PR open) at the end of its build session.
#      If the user validated it, confirm the recorded pass + ✅ flip is on main (and
#      no early-merge drift — fixes discovered during the live run must be merged to
#      base). If it FAILED, 2.1 is the focus, not 2.2. If still unvalidated, 2.2
#      CANNOT begin — 2.2 DEPENDS ON 2.1 ✅.
# 2. ADVANCEMENT GATE: 2.2 depends on 2.1 ✅ (hard gate — no override). Also note the
#      static-scan lane's live deploy shape (three stacks: Hub validator, intake
#      stack w/ the static-scan work queue, ZtieStaticScanStack container-image
#      Lambda; deploy order Hub → intake → static-scan).

# WHERE WE ARE (reconfirm via STEP 0 — git pull, list open PRs, no main/PR drift)
- Phase 1 COMPLETE: 1.1 / 1.1R / 1.R / 1.2 / 1.3 / 1.4 all ✅.
- Phase 2: 2.0 (infra foundation) 🟡 (built, PR #23 merged, awaiting live validation
  — blocks 2.3, NOT 2.2). 2.1 (static lane) 🟡 or ✅ depending on validation (check
  main). 2.2 is this story. 2.3 (detonation) needs 2.0.
- Deployed/added by 2.1: `schemas/static-findings.contract.v1.json` (Forensic-
  resident findings doc) + `schemas/static-scan-summary.contract.v1.json` (fifth Hub
  envelope kind); `lambdas/static_scan/` (normalize.py pure, toolplan.py pure,
  scanners.py subprocess seam, awsio.py boto3 seam, handler.py, Dockerfile,
  guard-rules/baseline.guard); Hub gate extended for the `scan` envelope kind;
  preprocessor enqueues a static-scan job to the Forensic static-scan work queue;
  `infra/lib/ztie-static-scan-stack.ts` (+ intake/hub stack edits).
- Governing docs: PROJECT_PLAN.md, RUNBOOK.md (source of truth for status),
  RESTORE.md, BOM.md, docs/COMPLIANCE.md, docs/ARCHITECTURE.md, and this story's
  brief: session-briefs/story-2.2-brief.md

# THIS SESSION'S OBJECTIVE
Extend the static lane so (1) a static finding is mapped to the NIST 800-53 / ISO
27001 control(s) it implicates, and (2) signature-based scans for known-bad
patterns/known vulns run alongside the four tools — both enriching the same
normalized findings shape (Forensic S3) and the same derived Hub summary (fifth
envelope kind). Get the user to validate live that a known-bad IaC/script yields a
finding mapped to the correct framework control AND a planted known signature is
detected — without executing the artifact and without crashing on a scanner error.

# SCOPE & GUARDRAILS
- In scope: the finding→control mapping (contract-first: on-finding `compliance`
  sub-object vs. a referenced table — bump the findings contract accordingly);
  signature scan tool(s)/ruleset + their normalization into the one findings shape
  (likely a `signature` check_family, possibly a new tool enum → contract bump);
  optional bounded compliance roll-up on the summary (still NO verdict); reuse the
  Hub-gate pattern; tests; record any RD (e.g. the signature-source choice).
- Out of scope / do NOT touch: the dynamic lane (2.3/2.4/2.5); the fork (2.6); the
  Hub verdict; G-1's governance self-audit matrix in docs/COMPLIANCE.md (different
  thing — that maps ZTIE's own design, not the scanned artifact).
- Depends on (must be ✅): 2.1.

# DEFINITION OF DONE (this session) — a PASS/FAIL GATE
The user, live in Forensic, confirms: a known-bad IaC template / script is scanned
and (a) a finding is mapped to the correct framework control (NIST 800-53 and/or ISO
27001) in the findings document + reflected in the Hub summary, and (b) a known
signature (e.g. a planted secret / known-bad pattern) is detected as a normalized
finding; no artifact is executed; the pipeline does not crash on a scanner error.
- Goes ✅ ONLY when the user confirms live AND it is RECORDED in RUNBOOK.md.
- If validation FAILS: not done — stay on 2.2, fix, re-validate.

# ENVIRONMENT
- Repo cloned; push to feature/story-2.2 (never main). Open/manage PRs via
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls` (NOT `gh pr create`).
- Merging is the repo-owner's action unless told "merge it via API."

# WORKING AGREEMENT
- MANAGEMENT ARTIFACTS ARE FIRST-CLASS (RD-015): keep PROJECT_PLAN ↔ RUNBOOK in
  EXACT alignment; update the 2.2 brief; PR-review all docs. Not done until docs are
  updated + aligned, not just code.
- One story to completion: design → build → USER validates live → RECORD + flip
  status → commit (paired status commit). Push to a branch; open a PR.
- At session end, author the NEXT story's brief + prompt (MANDATORY) with a Lessons
  Learned / Carry-Forward of THIS session's actual lessons. (Next after 2.2 per the
  runbook ordering is Story 2.3 detonation — which needs 2.0 ✅ — or the 2.6 fork;
  check the runbook + dependency gates.)
- If blocked, push partial progress + a draft PR; never silently fail.
