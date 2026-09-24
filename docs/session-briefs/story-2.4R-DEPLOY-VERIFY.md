# Story 2.4R — Deploy & Verify the detonation-lane fix (repeatable checklist)

> **Why this file exists.** A live validation of the dynamic (detonation) lane must run
> the CORRECT code asset, not just the correct stack configuration. Attempts 4/5 exposed
> a critical audit flaw: **checking the Lambda's environment variables only proves the
> STACK config deployed — it does NOT prove the Lambda CODE PACKAGE (`capturespec.py`)
> was updated.** The two timeout env vars are read with in-code defaults
> (`os.environ.get("ARTIFACT_EXEC_TIMEOUT_S", "75")` / `..._KILL_GRACE_S", "5")`), so they
> read `75`/`5` (or absent-but-effectively-`75`/`5`) **whether or not** the deployed code
> asset actually contains the fix. Env-present and env-absent are behaviorally identical.
> Therefore the deploy gate below verifies the **live code asset**, not the env.
>
> **Boundary note (Split-Brain / Zero-Trust).** This is a **human-airgap action in the
> Forensic account (360999005254)**. The build side has no keys to Forensic and cannot
> run or verify it. Run every step below in a Forensic-authed AWS CloudShell.
>
> **State is unchanged by this doc.** Story 2.4R stays 🟡, OPEN on the Validation Debt
> Register, gate ARMED. It earns ✅ only on a fresh recorded live pass of the fixed code.

## Hard rules (deploy-gap guards, from attempts 2–5)
1. **Get on the pinned code FIRST** (a stale checkout is how a green `deploy` ships old
   code). Confirm the commit and grep the source marker before deploying.
2. **Confirm the account** with `aws sts get-caller-identity` — a banner comment does NOT
   change the account; running in Hub instead of Forensic is a common miss.
3. **Verify the LIVE CODE ASSET after deploy (STEP 4)** — NOT the env vars. The env vars
   are defaulted in code (75/5) and prove nothing about which `capturespec.py` shipped.
   Grep the live code for the fix marker and/or compare `CodeSha256` to the built asset.

> ## ⛔ NON-SKIPPABLE GATE (added 2026-09-24, from the 2.4S attempt-4 deploy-gap)
> **STEP 4 (live code-asset verification) is a BLOCKING PRECONDITION to running ANY 2.4R/2.4S
> validation — it is NOT optional and NOT satisfiable by an env-var read.** The 2.4S attempt-4
> FAIL was traced (via the confirm-before-fix probe, `docs/validation-evidence/2.4S/attempt-4/PROBE-FINDING.md`)
> to the live Lambda almost certainly running STALE pre-#200 code — the exact failure this
> gate exists to stop. The confirm-before-fix probe proved the CURRENT code's Fix-B upload
> path works end-to-end once the live asset was verified first (`grep -c` the marker = the
> expected count BEFORE running). Rule: **if STEP 4 does not print the code-asset PASS for the
> markers the story-under-test introduced, STOP — do not run the validation, do not seal a
> verdict.** A validation run over an unverified asset is INVALID (it can silently validate
> stale code), regardless of a green `UPDATE_COMPLETE`.
>
> **For a 2.4S (Fix B / RD-058) validation, the code-asset marker is the DIRECT-UPLOAD path**,
> not the 2.4R `setsid timeout` marker. Grep the live `capturespec.py` for BOTH:
> - `__ZTIE_RC=0` (the PR #200 `set -u` init — its ABSENCE is the attempt-4 crash cause), and
> - `TRACE-UPLOAD-BEGIN` / `_UPLOAD_COMPLETE` / the regional `--endpoint-url` (the Fix-B upload block).
> If any is absent from the LIVE zip, the deploy is stale — STOP and redeploy.

## STEP 0 — get on the pinned post-fix code
```bash
cd ~/ZTIE-Issues
git fetch origin --tags
git checkout <POST_FIX_MAIN_SHA>        # the pinned attempt-6 target (from validation_target.py)
git log --oneline -1                    # expect <POST_FIX_MAIN_SHA>
grep -n 'setsid timeout --kill-after' infra/lib/../lambdas/detonation/capturespec.py
#   expect the attempt-6 marker present in the SOURCE you are about to deploy
```

## STEP 1 — confirm you are in FORENSIC (not Hub)
```bash
aws sts get-caller-identity --query Account --output text            # expect 360999005254
```

## STEP 2 — pull the six REQUIRED context inputs from their source stacks
```bash
ARTIFACT_BUCKET=$(aws cloudformation describe-stacks --stack-name ZtieIntakeStack \
  --query "Stacks[0].Outputs[?OutputKey=='ArtifactBucketName'].OutputValue" --output text)
DET_QUEUE_URL=$(aws cloudformation describe-stacks --stack-name ZtieIntakeStack \
  --query "Stacks[0].Outputs[?OutputKey=='DetonationQueueUrl'].OutputValue" --output text)
DET_QUEUE_ARN=$(aws cloudformation describe-stacks --stack-name ZtieIntakeStack \
  --query "Stacks[0].Outputs[?OutputKey=='DetonationQueueArn'].OutputValue" --output text)
DET_ROLE_ARN=$(aws cloudformation describe-stacks --stack-name ZtieForensicInfraStack \
  --query "Stacks[0].Outputs[?OutputKey=='DetonationInstanceRoleArn'].OutputValue" --output text)
HUB_Q_URL=$(aws cloudformation describe-stacks --stack-name ZtieIntakeStack \
  --query "Stacks[0].Outputs[?OutputKey=='HubIngestQueueUrl'].OutputValue" --output text)
HUB_Q_ARN=$(aws cloudformation describe-stacks --stack-name ZtieIntakeStack \
  --query "Stacks[0].Outputs[?OutputKey=='HubIngestQueueArn'].OutputValue" --output text)
echo "$ARTIFACT_BUCKET | $DET_QUEUE_URL | $DET_QUEUE_ARN | $DET_ROLE_ARN | $HUB_Q_URL | $HUB_Q_ARN"
# NONE may be empty / "None". If any is, discover the real names:
#   aws cloudformation list-stacks --query "StackSummaries[?contains(StackName,'Ztie') && StackStatus!='DELETE_COMPLETE'].StackName"
#   aws cloudformation describe-stacks --stack-name <name> --query "Stacks[0].Outputs[].OutputKey"
```

## STEP 3 — deploy the detonation stack
```bash
cd infra
npx cdk deploy ZtieDetonationStack \
  -c artifactBucketName="$ARTIFACT_BUCKET" \
  -c detonationQueueUrl="$DET_QUEUE_URL" \
  -c detonationQueueArn="$DET_QUEUE_ARN" \
  -c hubIngestQueueUrl="$HUB_Q_URL" \
  -c hubIngestQueueArn="$HUB_Q_ARN" \
  -c detonationInstanceRoleArn="$DET_ROLE_ARN"
```

## STEP 4 — VERIFY THE LIVE CODE ASSET (the only proof that counts) — NOT the env vars
The fix lives in the Lambda **code package**, not the stack env. Prove the deployed
`capturespec.py` actually contains the attempt-6 construct.

> **Marker set depends on the story under test.** The fix markers below are for **Story 2.4S
> (Fix B / RD-058)** — the current code under test (`main` `c1e323c`). They are the PRECISE
> structural strings in the source (verified against `lambdas/detonation/`), NOT guesses:
> `__ZTIE_RC=0` (PR #200 `set -u` init — its absence is the attempt-4 crash cause),
> `--endpoint-url` (PR #195 regional pin), the absolute `HOST_AWS_CLI` (PR #198), the Fix-B
> upload block (`ZTIE-TRACE-UPLOAD-BEGIN` / `_UPLOAD_COMPLETE`), and the S3-first READ path
> (`read_uploaded_trace` / `trace_from_s3` in `handler.py`, `read_uploaded_trace` defined in
> `awsio.py`). NOTE: the S3 read uses `awsio.read_uploaded_trace` (boto3 resource `.Object().get()`),
> **NOT** a bare `s3.get_object` — grepping for `s3.get_object` yields a FALSE NEGATIVE.
> (The older 2.4R attempt-6 marker was `setsid timeout --kill-after=`; that construct is still
> present in the wrapper but is NOT the 2.4S gate.)

```bash
FN=$(aws cloudformation describe-stacks --stack-name ZtieDetonationStack \
  --query "Stacks[0].Outputs[?OutputKey=='DetonationFunctionName'].OutputValue" --output text)

# Download the LIVE code package and extract it.
URL=$(aws lambda get-function --function-name "$FN" --query 'Code.Location' --output text)
curl -s "$URL" -o /tmp/ztie-fn.zip
rm -rf /tmp/ztie-lambda && unzip -q /tmp/ztie-fn.zip -d /tmp/ztie-lambda

# (a) The five 2.4S fix markers must ALL be present on the live capturespec.py:
echo "== PR #200 (set -u init) ==";        grep -n '__ZTIE_RC=0' /tmp/ztie-lambda/capturespec.py
echo "== PR #195 (regional endpoint) ==";  grep -n 'endpoint-url' /tmp/ztie-lambda/capturespec.py
echo "== PR #198 (absolute CLI) ==";       grep -n 'HOST_AWS_CLI = "/usr/local/aws-cli/v2/current/bin/aws"' /tmp/ztie-lambda/capturespec.py
echo "== Fix B upload block (RD-058) =="; grep -n 'ZTIE-TRACE-UPLOAD-BEGIN\|_UPLOAD_COMPLETE' /tmp/ztie-lambda/capturespec.py
echo "== S3-first READ path ==";           grep -n 'read_uploaded_trace\|trace_from_s3' /tmp/ztie-lambda/handler.py
                                           grep -n 'def read_uploaded_trace' /tmp/ztie-lambda/awsio.py

# (b) Belt-and-suspenders: the live code hash equals the built asset hash.
aws lambda get-function-configuration --function-name "$FN" --query 'CodeSha256' --output text
#   compare to the CodeSha256 of the asset cdk synthesized for c1e323c (printed by `cdk deploy`).

# (c) REGRESSION GUARD: the diagnostic probe (diag/story-2.4S-upload-probe, PR #205, reverted)
#     must be ABSENT — its presence means the live Lambda is the probe deploy, NOT clean c1e323c:
grep -rn 'ZTIE-PROBE-BEGIN' /tmp/ztie-lambda/ \
  && echo "REGRESSION: probe code LIVE — redeploy ZtieDetonationStack from main c1e323c" \
  || echo "OK: no probe code on the live asset"
```
**PASS gate:** (a) EVERY marker prints a line (none empty) **AND** (c) prints
`OK: no probe code`. Only then is the live Lambda running the clean 2.4S code (`c1e323c`).
**Do NOT** run the 2.4S validation suite until the gate passes. **Never** substitute an
env-var read for this — env `75`/`5` is inert proof.

> **Why env-var verification is banned here (audit note, RD-015).** `capturespec.py`
> reads `os.environ.get("ARTIFACT_EXEC_TIMEOUT_S", "75")` and
> `os.environ.get("ARTIFACT_EXEC_KILL_GRACE_S", "5")`. A missing env var falls back to the
> identical `75`/`5`, so an env read cannot distinguish "fixed code deployed" from "stale
> code deployed" — both show `75`/`5`. This is a general rule for every ZTIE lane whose
> behavior lives in the code package: **verify the code asset (grep the live source or
> compare `CodeSha256`), never a defaulted env var.**

## After a PASS
The live Lambda now demonstrably runs the code under test (the clean 2.4S code, `c1e323c`).
Re-run the independent split-brain validation suite (runbook + DoD authored blind by the
Independent Validator, RD-055/056). A security-boundary ✅ still requires its RD-054 evidence
folder (for the current re-validation: `docs/validation-evidence/2.4S/attempt-<n>/`). This
checklist does NOT by itself flip 2.4S/2.4R — it only proves the RIGHT code is live so the
validation is not run over a stale asset (the attempt-4 deploy-gap).
