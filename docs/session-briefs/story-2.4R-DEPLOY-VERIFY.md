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

```bash
FN=$(aws cloudformation describe-stacks --stack-name ZtieDetonationStack \
  --query "Stacks[0].Outputs[?OutputKey=='DetonationFunctionName'].OutputValue" --output text)

# (a) Download the LIVE code package and grep the actual source for the fix marker:
URL=$(aws lambda get-function --function-name "$FN" --query 'Code.Location' --output text)
curl -s "$URL" -o /tmp/ztie-fn.zip
unzip -p /tmp/ztie-fn.zip capturespec.py | grep -nE "setsid timeout --kill-after=" \
  && echo "CODE-ASSET OK: attempt-6 wrapper present on the live Lambda" \
  || echo "CODE-ASSET FAIL: live Lambda does NOT contain the attempt-6 fix — STALE DEPLOY"

# (b) Belt-and-suspenders: the live code hash equals the built asset hash.
aws lambda get-function-configuration --function-name "$FN" --query 'CodeSha256' --output text
#   compare to the CodeSha256 of the asset cdk synthesized for <POST_FIX_MAIN_SHA>.

# (c) The plain-timeout marker must be GONE (regression guard: no attempt-5 code lingering):
unzip -p /tmp/ztie-fn.zip capturespec.py | grep -E "timeout -k [0-9]" \
  && echo "REGRESSION: bare 'timeout -k' still on the live Lambda (stale/mixed asset)" \
  || echo "OK: no bare 'timeout -k' on the live Lambda"
```
**PASS gate:** (a) prints `CODE-ASSET OK` **and** (c) prints `OK`. Only then is the live
Lambda running the attempt-6 code. **Do NOT** run the 2.4R validation suite until (a)+(c)
pass. **Never** substitute an env-var read for this — env `75`/`5` is inert proof.

> **Why env-var verification is banned here (audit note, RD-015).** `capturespec.py`
> reads `os.environ.get("ARTIFACT_EXEC_TIMEOUT_S", "75")` and
> `os.environ.get("ARTIFACT_EXEC_KILL_GRACE_S", "5")`. A missing env var falls back to the
> identical `75`/`5`, so an env read cannot distinguish "fixed code deployed" from "stale
> code deployed" — both show `75`/`5`. This is a general rule for every ZTIE lane whose
> behavior lives in the code package: **verify the code asset (grep the live source or
> compare `CodeSha256`), never a defaulted env var.**

## After a PASS
The live Lambda now demonstrably runs the attempt-6 code. Re-run the independent
split-brain validation suite (runbook + DoD authored blind by the Independent Validator,
RD-055/056). A security-boundary ✅ still requires its RD-054 evidence folder
(`docs/validation-evidence/2.4R/attempt-6/`). This checklist does NOT by itself flip 2.4R.
