# Story 2.4R4 — LIVE-RUNBOOK (fresh live validation of the FIXED code)

> The 2.4R4 fix (on-host `timeout` so a hanging artifact no longer SIGKILLs the wrapper) is
> BUILT + offline/behaviorally proven, but the covenant requires a **recorded live pass of
> the FINAL code** before 2.4R can flip ✅. This runbook is split-brain Part B (RD-053): the
> operator runs it in the real accounts; the independent validator (Gemini) adjudicates.
> **2.4R stays 🟡 until that recorded pass.**

## Accounts / tabs
- **Forensic `360999005254`** — detonation lane, artifact bucket, deploy target for
  `ZtieDetonationStack`. (Submit intake here.)
- **Hub `641628980935`** — the DynamoDB tracking table (verify the crossed `behavior` record here).
- Two CloudShell tabs; run `aws sts get-caller-identity --query Account --output text` before
  EVERY block (a banner does not change the account).

## STEP 0 — put the box on the FIXED code (deploy-gap discipline)
A green `cdk deploy` of the WRONG checkout ships stale code. Before deploying:
```bash
cd ~/ZTIE-Issues
git fetch origin
git checkout feature/story-2.4R4         # or the merged main once 2.4R4 PR is merged
git reset --hard origin/feature/story-2.4R4
git log --oneline -1                       # paste this SHA into the evidence
# Confirm the fix is actually present in the source that will synth:
grep -n "ARTIFACT_EXEC_TIMEOUT_S\|ARTIFACT_TIMED_OUT_MARKER\|timeout -k" lambdas/detonation/capturespec.py
grep -n "ARTIFACT_EXEC_TIMEOUT_S" infra/lib/ztie-detonation-stack.ts
```

## STEP 1 — deploy the detonation lane (Forensic)
```bash
aws sts get-caller-identity --query Account --output text   # expect 360999005254
cd ~/ZTIE-Issues/infra
# deploy with the same context the lane normally takes (artifactBucketName, hub ingest, etc.)
npx cdk deploy ZtieDetonationStack --require-approval never
```
AFTER deploy, VERIFY the live Lambda actually carries the fix (never trust the ✅ line):
```bash
FN=$(aws lambda list-functions \
  --query "Functions[?contains(FunctionName,'Detonation')].FunctionName | [0]" --output text)
aws lambda get-function-configuration --function-name "$FN" \
  --query "Environment.Variables.{budget:ARTIFACT_EXEC_TIMEOUT_S,grace:ARTIFACT_EXEC_KILL_GRACE_S}"
# expect budget=75 grace=5  (NOT null)
```

## STEP 2 — submit the HANGING probe (the regression that FAILed attempt 4)
Submit the SAME known-behavior artifact whose `/dev/tcp` connect hangs
(`docs/validation-evidence/2.4R/attempt-4/adversarial-2.4R-v3.sh`), via the intake API (SigV4, Forensic). Record the
new `intake_id`. This proves the fix on the exact failure that produced TimedOut/137.

## STEP 3 — (recommended) submit a NON-hanging known-behavior artifact
A quiet probe that does file ops + a `printf` write buffer but NO blocking connect, so we
also prove a NORMAL run still yields a FULL trace (the fix must not regress the happy path).

## STEP 4 — verify on the Hub tracking item (Hub tab)
```bash
aws sts get-caller-identity --query Account --output text   # expect 641628980935
# GetItem the tracking record for each intake_id; inspect the `behavior` attribute.
```
**PASS criteria — the HANGING probe (STEP 2):**
- The run NO LONGER times out the wrapper: the crossed `behavior.capture` is present (not a
  silent gap), `capture_status` is `captured` (partial) with `trace_truncated: true`, OR
  `capture_error` with an `error_reason` naming the inner timeout — **either is a PASS for the
  fix**, because the wrapper SURVIVED and recorded honest health instead of vanishing.
- The raw Forensic trace (`traces/<intake>/behavior-trace.txt`) exists and, if `captured`,
  contains the artifact's syscalls UP TO the timeout, including the `connect()` INTENT to
  `93.184.216.34:443` (network capture = intent; the isolated VPC blocks it).
- `runs/<intake>/detonation-output.json` shows the `ZTIE-ARTIFACT-TIMED-OUT` marker and the
  BEGIN/END trace markers ARE present (the emit block ran) — contrast attempt 4 where all
  were absent.
- No verdict/effective-decision field written by this lane (evidence-only; scope the probe to
  the `behavior` attribute so the concurrent Phase-3 `hub_verdict` stage does not false-trip
  the negative probe — the attempt-1 DoD-3 lesson).

**PASS criteria — the NORMAL probe (STEP 3):** `capture_status: captured`, the planted write
buffer's `write`/`writev`/`pwrite64` syscalls present in the raw trace, file ops present, no
timeout marker.

## STEP 5 — retain + adjudicate
Retain in `docs/validation-evidence/2.4R/attempt-5/` (next attempt folder): both
`detonation-output.json`s, the raw `behavior-trace.txt`(s), the Hub `behavior` projection,
the deploy SHA from STEP 0, and a terminal attestation. The independent validator adjudicates
PASS/FAIL. On a recorded PASS: 2.4R flips 🟡→✅, the Validation Debt Register entry clears,
and the advancement gate OPENS (the next pipe story, **4.7**, unblocks).

## Notes / watch-items
- GNU `timeout` is pre-baked on the golden AMI (RD-030). If a future AMI lacks it, the
  wrapper would fall through — add an AMI-bake assertion if that ever surfaces.
- A hanging artifact is EVIDENCE, never a verdict: the lane records capture health and the
  connect INTENT; the PASS/FAIL/INCONCLUSIVE decision stays Hub-side / human-gated (Phase 4).
- Budget is tunable via `ARTIFACT_EXEC_TIMEOUT_S`/`ARTIFACT_EXEC_KILL_GRACE_S` env without a
  code change; keep BUDGET+GRACE comfortably under the SSM `EXEC_TIMEOUT_S` (120 s) ceiling.
