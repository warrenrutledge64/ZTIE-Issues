# Story 2.4R — Deploy & Verify the detonation-lane fix (repeatable checklist)

> **Why this file exists.** The independent entry-boundary validation found the LIVE
> `ZtieDetonationStack-DetonationOrchestrator` Lambda in the Forensic account
> **missing** `ARTIFACT_EXEC_TIMEOUT_S` / `ARTIFACT_EXEC_KILL_GRACE_S`. Those two env
> vars ARE present in the pinned code (`9cd4102`, on `main` tip `03602939`) — so this
> is a **deploy-gap**, not a code defect: the correct code was never deployed onto the
> live Lambda. No code change is needed; the stack just needs a redeploy + a live check.
>
> **Boundary note (Split-Brain / Zero-Trust).** This is a **human-airgap action in the
> Forensic account (360999005254)**. The build side has no keys to Forensic and cannot
> run or verify it. Run every step below in a Forensic-authed AWS CloudShell.
>
> **State is unchanged by this doc.** Story 2.4R stays 🟡, OPEN on the Validation Debt
> Register, gate ARMED. It clears only on a fresh recorded live pass of the fixed code.

## Hard rules (deploy-gap guards, from prior live lessons)
1. **Get on the pinned code FIRST** (a stale checkout is exactly how a green `deploy`
   ships old code). Confirm the commit and grep the source marker before deploying.
2. **Confirm the account** with `aws sts get-caller-identity` — a banner comment does
   NOT change the account; running in Hub instead of Forensic is a common miss.
3. **Verify the LIVE resource after deploy** (STEP 4). Never trust the
   `✅ UPDATE_COMPLETE` line alone — a "successful" deploy of the wrong checkout still
   ships stale code. The live `get-function-configuration` env is the only proof.

## STEP 0 — get on the exact pinned code
```bash
cd ~/ZTIE-Issues
git fetch origin --tags
git checkout 03602939acdb2140f7154611b8156e5e5c469383
git log --oneline -1                                                 # expect 03602939...
grep -n ARTIFACT_EXEC_TIMEOUT_S infra/lib/ztie-detonation-stack.ts   # expect lines ~173/174
```

## STEP 1 — confirm you are in FORENSIC (not Hub)
```bash
aws sts get-caller-identity --query Account --output text            # expect 360999005254
```

## STEP 2 — pull the six REQUIRED context inputs from their source stacks
`ZtieDetonationStack` only synthesizes when all six are supplied. Each comes from
another stack's CloudFormation output (read live — nothing hard-coded).

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
# NONE of these may be empty or "None".
```

**If any value is empty:** the stack name or output key differs in your account.
Discover the real ones and re-map:
```bash
aws cloudformation list-stacks \
  --query "StackSummaries[?contains(StackName,'Ztie') && StackStatus!='DELETE_COMPLETE'].StackName"
aws cloudformation describe-stacks --stack-name <name> --query "Stacks[0].Outputs[].OutputKey"
```
The six inputs map to these source outputs (per `infra/bin/ztie-infra.ts`):
| Context input | Source stack | Source output |
|---|---|---|
| `artifactBucketName` | intake stack | `ArtifactBucketName` |
| `detonationQueueUrl` | intake stack | `DetonationQueueUrl` |
| `detonationQueueArn` | intake stack | `DetonationQueueArn` |
| `hubIngestQueueUrl` | intake stack | `HubIngestQueueUrl` (Hub `IngestQueueUrl`) |
| `hubIngestQueueArn` | intake stack | `HubIngestQueueArn` (Hub `IngestQueueArn`) |
| `detonationInstanceRoleArn` | forensic-infra (2.0) stack | `DetonationInstanceRoleArn` |

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

## STEP 4 — VERIFY THE LIVE LAMBDA (the only proof that counts)
```bash
FN=$(aws cloudformation describe-stacks --stack-name ZtieDetonationStack \
  --query "Stacks[0].Outputs[?OutputKey=='DetonationFunctionName'].OutputValue" --output text)
aws lambda get-function-configuration --function-name "$FN" \
  --query "Environment.Variables.{ARTIFACT_EXEC_TIMEOUT_S:ARTIFACT_EXEC_TIMEOUT_S,ARTIFACT_EXEC_KILL_GRACE_S:ARTIFACT_EXEC_KILL_GRACE_S}"
```
**PASS:** `{"ARTIFACT_EXEC_TIMEOUT_S":"75","ARTIFACT_EXEC_KILL_GRACE_S":"5"}`
**FAIL:** either value is `null`/absent → the deploy shipped stale code again; re-check
STEP 0 (right commit?) and STEP 1 (right account?) and redeploy. Do NOT re-run the
2.4R validation suite until STEP 4 shows 75/5.

## After a PASS
The live infrastructure now matches the pinned `9cd4102` contract. Re-run the
independent entry-boundary + behavioral validation suite. (This does not by itself flip
2.4R to ✅ — the full split-brain live pass adjudicated by the Independent Validator is
what clears the register.)
