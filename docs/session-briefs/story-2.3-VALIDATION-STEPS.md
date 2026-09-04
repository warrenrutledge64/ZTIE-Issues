# Story 2.3 — step-by-step live validation (copy-paste, CloudShell)

> **Who runs this:** YOU, in the AWS Console → CloudShell. The executor has no AWS
> creds and only RECORDS what you paste back. Nothing here runs itself — you paste
> commands **one at a time** and read the output.
>
> **What you are proving (4 checks):** (1) one ephemeral EC2 launches FROM the 2.0
> launch template, (2) the artifact runs host-native via SSM with NO Docker, (3) the
> instance is torn down by the 5-minute hard TTL, (4) a bounded, verdict-free run
> outcome crosses to the Hub.
>
> **You need TWO CloudShell tabs:**
> - **Tab F = Forensic** account (360999005254) — deploy, submit, watch, checks 1–3.
> - **Tab H = Hub** account (641628980935) — check 4.
>
> **Golden rule:** run `aws sts get-caller-identity` at the top of every tab and read
> `Account`. If it is the wrong account, switch tabs. Region is **us-east-1**.

---

## TAB F (Forensic) — Step 0: confirm account + get the code

```bash
aws sts get-caller-identity --query Account --output text
```
➡️ Must print **360999005254**. If not, you are in the wrong account — fix the tab.

```bash
cd ~/ZTIE-Issues && git fetch origin -q && git checkout main && git reset --hard origin/main
```
(If you do not have the repo yet:
`git clone https://<YOUR_TOKEN>@github.com/warrenrutledge64/ZTIE-Issues.git ~/ZTIE-Issues` first.)

---

## TAB F — Step 1: load the existing stack outputs into variables

These read the already-deployed stacks and stash the values the deploy needs. Paste
the whole block (it only READS):

```bash
REGION=us-east-1
# Hub ingest queue (created by the Hub stack) — the Forensic->Hub door:
HUB_INGEST_URL=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region $REGION --query "Stacks[0].Outputs[?OutputKey=='IngestQueueUrl'].OutputValue" --output text)
HUB_INGEST_ARN=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region $REGION --query "Stacks[0].Outputs[?OutputKey=='IngestQueueArn'].OutputValue" --output text)
# 2.0 detonation instance role (created by the forensic-infra stack):
DET_ROLE_ARN=$(aws cloudformation describe-stacks --stack-name ZtieForensicInfraStack --region $REGION --query "Stacks[0].Outputs[?OutputKey=='DetonationInstanceRoleArn'].OutputValue" --output text)
echo "HUB_INGEST_URL=$HUB_INGEST_URL"
echo "HUB_INGEST_ARN=$HUB_INGEST_ARN"
echo "DET_ROLE_ARN=$DET_ROLE_ARN"
```
➡️ All three must print non-empty values. If any is blank, that stack is not deployed
under the expected name — stop and tell the executor what `describe-stacks` shows.

---

## TAB F — Step 2: deploy the updated intake stack (adds the detonation queue)

```bash
cd ~/ZTIE-Issues/infra && npm ci
```
```bash
npx cdk deploy ZtieIntakeStack --require-approval never \
  -c hubIngestQueueUrl="$HUB_INGEST_URL" \
  -c hubIngestQueueArn="$HUB_INGEST_ARN"
```
➡️ Wait for `✅  ZtieIntakeStack`. Then capture the new detonation-queue + bucket +
endpoint outputs:

```bash
ARTIFACT_BUCKET=$(aws cloudformation describe-stacks --stack-name ZtieIntakeStack --region $REGION --query "Stacks[0].Outputs[?OutputKey=='ArtifactBucketName'].OutputValue" --output text)
DET_QUEUE_URL=$(aws cloudformation describe-stacks --stack-name ZtieIntakeStack --region $REGION --query "Stacks[0].Outputs[?OutputKey=='DetonationQueueUrl'].OutputValue" --output text)
DET_QUEUE_ARN=$(aws cloudformation describe-stacks --stack-name ZtieIntakeStack --region $REGION --query "Stacks[0].Outputs[?OutputKey=='DetonationQueueArn'].OutputValue" --output text)
INTAKE_ENDPOINT=$(aws cloudformation describe-stacks --stack-name ZtieIntakeStack --region $REGION --query "Stacks[0].Outputs[?OutputKey=='IntakeEndpoint'].OutputValue" --output text)
echo "ARTIFACT_BUCKET=$ARTIFACT_BUCKET"; echo "DET_QUEUE_URL=$DET_QUEUE_URL"; echo "DET_QUEUE_ARN=$DET_QUEUE_ARN"; echo "INTAKE_ENDPOINT=$INTAKE_ENDPOINT"
```

---

## TAB F — Step 3: deploy the NEW detonation stack

```bash
npx cdk deploy ZtieDetonationStack --require-approval never \
  -c artifactBucketName="$ARTIFACT_BUCKET" \
  -c detonationQueueUrl="$DET_QUEUE_URL" \
  -c detonationQueueArn="$DET_QUEUE_ARN" \
  -c hubIngestQueueUrl="$HUB_INGEST_URL" \
  -c hubIngestQueueArn="$HUB_INGEST_ARN" \
  -c detonationInstanceRoleArn="$DET_ROLE_ARN"
```
➡️ Wait for `✅  ZtieDetonationStack`. Capture the function name:

```bash
DET_FN=$(aws cloudformation describe-stacks --stack-name ZtieDetonationStack --region $REGION --query "Stacks[0].Outputs[?OutputKey=='DetonationFunctionName'].OutputValue" --output text)
echo "DET_FN=$DET_FN"
```
**📋 PASTE BACK:** the last ~15 lines of each deploy + the `DET_FN` value.

---

## TAB H (Hub) — Step 4: re-deploy the Hub stack so it accepts the new envelope

Switch to **Tab H** and confirm the account FIRST:
```bash
aws sts get-caller-identity --query Account --output text
```
➡️ Must print **641628980935**.

```bash
cd ~/ZTIE-Issues && git fetch origin -q && git checkout main && git reset --hard origin/main
cd infra && npm ci
npx cdk deploy ZtieHubTrackingStack --require-approval never
```
➡️ This ships the Hub validator's new `dynamic-run.contract.v1` bundle + version pin.
Without it, the crossed outcome would be quarantined (fail-closed) instead of attached.
Capture the tracking table name (you need it for check 4):
```bash
TRACKING_TABLE=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='TrackingTableName'].OutputValue" --output text)
echo "TRACKING_TABLE=$TRACKING_TABLE"
```
**📋 PASTE BACK:** the deploy tail + `TRACKING_TABLE`.

---

## TAB F (Forensic) — Step 5: submit a routed artifact

Back in **Tab F**. Confirm account (`aws sts get-caller-identity --query Account --output text` → 360999005254). Install the SigV4 submit tool + create a benign sample:
```bash
pip install --quiet awscurl
printf '#!/bin/sh\necho ZTIE-DETONATION-OK\ntouch /tmp/ztie-marker\nid\n' > /tmp/sample.sh
cat /tmp/sample.sh
```
Submit it (a `raw_script` forks into BOTH the static and dynamic lanes):
```bash
awscurl --service execute-api --region us-east-1 -X POST \
  -H 'Content-Type: application/octet-stream' --data-binary @/tmp/sample.sh \
  "$INTAKE_ENDPOINT"
```
➡️ The JSON response contains an `intake_id`. Save it:
```bash
INTAKE_ID=<paste-the-intake_id-from-the-response>
echo "INTAKE_ID=$INTAKE_ID"
```
**📋 PASTE BACK:** the full submit response + your `INTAKE_ID`.

---

## TAB F — Step 6: watch the detonation (find the instance + SSM command ids)

Give it ~30–60s after submit, then look at the detonation Lambda log for the run:
```bash
aws logs tail "/aws/lambda/$DET_FN" --since 15m --format short | grep -Ei "launched|SSM command|detonation complete|instance_id|outcome"
```
➡️ You are looking for lines like:
`launched ephemeral detonation host instance_id=i-0... from template=lt-...`,
`sent host-native SSM command command_id=...`,
`detonation complete intake_id=... outcome=completed ssm_status=Success teardown_observed=...`.

Pull the two ids into variables (copy them from the log lines):
```bash
INSTANCE_ID=<paste i-... from the log>
SSM_CMD_ID=<paste the command_id from the log>
echo "INSTANCE_ID=$INSTANCE_ID  SSM_CMD_ID=$SSM_CMD_ID"
```
**📋 PASTE BACK:** the matched log lines.

---

## TAB F — Check 1: launched from the 2.0 template, isolated, no public IP

```bash
aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --region us-east-1 \
  --query "Reservations[0].Instances[0].{State:State.Name,Subnet:SubnetId,PublicIp:PublicIpAddress,LaunchTemplate:Tags[?Key=='aws:ec2launchtemplate:id']|[0].Value}"
```
➡️ **PASS check 1** if: a launch-template id is present, `Subnet` is set, `PublicIp` is
`null`. **📋 PASTE BACK** the full output.

## TAB F — Check 2: host-native SSM execution, NO Docker

```bash
aws ssm get-command-invocation --command-id "$SSM_CMD_ID" --instance-id "$INSTANCE_ID" --region us-east-1 \
  --query "{Doc:DocumentName,Status:Status,Rc:ResponseCode,Stdout:StandardOutputContent}"
```
➡️ **PASS check 2** if: `Doc` = `AWS-RunShellScript`, `Status` is terminal (e.g.
`Success`), and `Stdout` contains `ZTIE-DETONATION-OK` (the artifact ran directly on the
host — no container). **📋 PASTE BACK** the full output.

## TAB F — Check 3: 5-minute hard TTL teardown

Wait until ~5–6 minutes after the instance launched, then:
```bash
aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --region us-east-1 \
  --query "Reservations[0].Instances[0].State.Name" --output text
```
➡️ **PASS check 3** if this prints `shutting-down` or `terminated`.
⚠️ **If it still prints `running` well past 5 minutes, that is the FINDING — do NOT pass
check 3.** Paste it back either way. **📋 PASTE BACK** the state (and re-run once more a
minute later if it was still `running`).

---

## TAB H (Hub) — Check 4: the bounded, verdict-free outcome crossed

Switch to **Tab H**, confirm account = 641628980935, then:
```bash
aws dynamodb get-item --region us-east-1 --table-name "$TRACKING_TABLE" \
  --key "{\"intake_id\":{\"S\":\"$INTAKE_ID\"}}" \
  --query "Item.{outcome:dynamic_run_outcome.S,detonated_at:detonated_at.S}"
```
➡️ Expect `outcome` (e.g. `completed`) + `detonated_at` present. Then see the full run
object (confirm containment + NO verdict field):
```bash
aws dynamodb get-item --region us-east-1 --table-name "$TRACKING_TABLE" \
  --key "{\"intake_id\":{\"S\":\"$INTAKE_ID\"}}" \
  --query "Item.dynamic_run.M.{lane:lane.S,outcome:outcome.S,containment:containment.M,teardown:teardown.M.teardown_observed.BOOL,ssm:execution.M.ssm_status.S}"
```
➡️ **PASS check 4** if: `lane` = `dynamic_detonation`, `containment` shows
host_native/no_docker/isolated_subnet true + public_ip false, and there is **no**
`verdict`/`safe`/`forward` field anywhere. **📋 PASTE BACK** both outputs.
(If the item has no `dynamic_run` at all, also paste
`aws logs tail /aws/lambda/<HUB-VALIDATOR-FN> --since 15m` — the outcome may have been
quarantined, which is itself useful signal.)

---

## What to send back

Paste, labelled by step, the outputs from: Step 3 (`DET_FN`), Step 4 (`TRACKING_TABLE`),
Step 5 (submit response + `INTAKE_ID`), Step 6 (log lines), and **Checks 1, 2, 3, 4**.

Then the executor will:
- **All 4 pass** → record the dated Validation Result, flip 2.3 → ✅ (paired PR),
  clear it from the Validation Debt Register, tag `restore/story-2.3-green`.
- **Any check fails / errors** → that is real signal; the executor fixes it and, because
  2.3 already merged to `main`, lands the fix as a FOLLOW-UP PR, and you re-run.
```
