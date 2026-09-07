# Story 2.6 (stakeholder brief) — Parallel orchestration / fork of the two lanes

> **What this session is.** With the Phase-2 floor validated and backed up, both
> inspection lanes now exist and are ✅ end-to-end: the **static** lane (2.1 scanners +
> 2.2 compliance/signature enrichment) and the **dynamic** lane (2.3 detonation). Today
> the preprocessor fires **two independent enqueues** — one static-scan job, one
> detonation job — and nothing ties them together. Story **2.6** adds the missing
> **orchestration**: fork a routed artifact into **both lanes concurrently**, then
> **join** their two outputs into one collected result ready for Phase 3 aggregation.
> This is the story that **closes Phase 2**.

## Where we are (true state at authoring, 2026-09-07)

- **2.6 is the next buildable pipeline story.** Its dependencies — **2.1 ✅** (static
  lane) and **2.3 ✅** (dynamic lane) — are both met, and the Validation Debt Register
  is EMPTY, so the advancement gate is open for it (build tier 5).
- **2.4 is deliberately NOT next.** By the 2026-09-07 decision, 2.4 (behavioral
  telemetry) is gated behind A.5 + A.6 (the "clean the ground first" stories) and sits
  at tier 7. 2.6 does not pass through 2.4, so it is unaffected and is the correct next
  feature story. (2.6 needs the dynamic RUN to exist — 2.3 — not its telemetry capture.)
- **What already exists that 2.6 builds on:** the preprocessor
  (`lambdas/preprocessor/handler.py`) already enqueues a static-scan job when routing
  names `static_analysis` and a detonation job when it names `dynamic_detonation`
  (both intra-Forensic hand-offs, RD-009). The two lanes each already cross their own
  derived, verdict-free summary to the Hub (the fifth + sixth RD-013 envelope kinds).
  What is MISSING is the concurrent fork + the JOIN of the two lane outputs into one
  collected record for Phase 3.

## What 2.6 delivers (Definition of Done — a PASS/FAIL gate)

The stakeholder confirms live in **Forensic 360999005254** (+ Hub 641628980935 for the
crossed record):

1. **One routable artifact forks into BOTH lanes CONCURRENTLY** after routing — the
   static lane and the dynamic lane run in parallel (not one-then-the-other) for the
   same `intake_id`.
2. **Both lane outputs are COLLECTED / joined** — a single, bounded, derived record
   ties the static-scan summary and the dynamic-run outcome together for that
   `intake_id`, ready for Phase-3 aggregation.
3. **Evidence, never a verdict** — the joined record carries NO verdict/safe/approved/
   forward field (the verdict stays Hub-side / human-gated, Phase 4). Full detail stays
   in Forensic (RD-009); only bounded derived data crosses the RD-013 gate.
4. **Containment + boundaries intact** — the dynamic lane still runs host-native on the
   ephemeral EC2 (no Docker, RD-001), the isolated-VPC containment is unchanged, and
   the join does NOT re-introduce a durable store in Forensic (RD-012) or a raw-payload
   crossing.

## What only YOU (the stakeholder) can do

- **Run the live fork validation** in the Forensic CloudShell (submit one routable
  artifact via intake; confirm both lanes ran concurrently and both outputs were
  collected/joined). The executor has NO live creds and will RECORD your returned
  output verbatim — it will not simulate a run.
- **Verify the joined record on the Hub** in a Hub CloudShell tab (the tracking table
  is in the Hub). Two tabs, `aws sts get-caller-identity` before each block.
- **Merge** the PR (repo-owner action) and, on pass, place any restore tag.

## Scope guardrails

- **In scope:** the concurrent fork of the two lanes after routing; the JOIN /
  collection of both lane outputs into one bounded derived record for Phase 3; the
  orchestration mechanism (e.g. a Step Functions state machine or an equivalent
  join-on-both-complete pattern) in Forensic; contract-first for any new joined-record
  shape that crosses the RD-013 gate (its own version pin); pure logic + thin seams;
  tests; a new RD for the orchestration choice + candidate control mappings.
- **Out of scope / do NOT touch:** behavioral telemetry capture (2.4 — and it is gated
  behind A.5/A.6 anyway); telemetry sanitization (2.5); the Phase-3 Nova Pro
  correlation itself (3.x — 2.6 only COLLECTS the inputs, it does not correlate); the
  Hub verdict; Docker on the detonation host; re-litigating the 2.1/2.2/2.3 lane
  internals or their existing contracts.
- **Depends on (must be ✅):** 2.1 AND 2.3 (both are). Plus an EMPTY Validation Debt
  Register (it is).

## Lessons Learned / Carry-Forward (from the governance sessions that just closed)

- **The base-branch trap bit us for real this session — guard against it.** PR #65 was
  merged after only its FIRST commit was on the branch; the two later commits (A.5/A.6
  + the 2.4 re-tiering) were stranded and had to be reconciled onto `main` via a
  FOLLOW-UP PR (#66). For 2.6: after any live-validation fixes, `git log main..<branch>`
  and confirm every fix commit actually merged; if a PR merges early, open a follow-up
  PR — do not assume "merged" means the whole branch landed. The restore tag must point
  at the commit that carries the validated code.
- **Trust `main` + `check_docs` over any prompt.** STEP 0 re-establishes true state from
  `main`; if this brief and `main` disagree, `main` wins. Re-run
  `python3 scripts/check_docs.py` (expect PASS) and `python3 -m unittest
  scripts.test_check_docs` (expect OK) after ANY status/register/table edit — a doc
  edit that changes a story row can break a fixture; keep the fixtures state-independent.
- **Two accounts, two tabs, `aws sts get-caller-identity` before EVERY block.** The
  single most repeated live mistake in this project: querying the Hub tracking table
  from Forensic (→ `ResourceNotFoundException`) or submitting intake from a Hub
  principal (→ 403). The dynamic lane + fork orchestration live in Forensic; the joined
  record is verified in the Hub.
- **The artifact-fetch recipe (2.3) is settled — reuse, don't rediscover.** If 2.6's
  orchestration touches the launch/execute or any isolated-host S3 fetch: one S3
  gateway endpoint (no interface endpoint), host SG egress to the S3 managed prefix
  list (resolved via a real `ec2:DescribeManagedPrefixLists` call), a REGIONAL presigned
  host, and SigV4 — all four together. Do NOT pass an instance-profile ARN on
  `RunInstances` (the launch template already carries it). Bound every on-host fetch
  with `--connect-timeout`/`--max-time`.
- **Sandbox is INTEGRATIONS_ONLY** (no boto3/pytest/moto/jsonschema/aws-cdk-lib/npm
  installs). You BUILD + prove offline (stdlib `unittest` + a manual pure-Python
  conformance walk); the STAKEHOLDER validates live. `tsc --noEmit` shows only the
  environmental missing-`aws-cdk-lib` family — confirm no NEW defect.
- **Management artifacts are first-class (RD-015):** brief + RUNBOOK + PROJECT_PLAN in
  exact alignment; any new RD + candidate NIST/ISO mappings recorded; all via PR; keep
  unrelated governance edits off this feature branch. At session end, author the next
  story's brief + prompt with this session's real Lessons Learned.
