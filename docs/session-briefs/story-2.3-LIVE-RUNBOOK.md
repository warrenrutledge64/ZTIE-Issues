# Story 2.3 — LIVE detonation validation runbook (stakeholder, two CloudShells)

> **This is the ONLY live part of 2.3, and only YOU can do it** (the executor has no
> AWS creds). You DEPLOY the detonation lane, submit a routed artifact, watch a real
> ephemeral EC2 run it host-native, confirm the 5-min hard TTL tears it down, and
> confirm the derived run OUTCOME crossed to the Hub. The executor **records your
> returned output verbatim** into RUNBOOK 2.3 detail. **Nothing is recorded on
> inference** — paste back exactly what the commands print. On a 4/4 pass the executor
> flips 2.3 ✅ (paired commit) and tags `restore/story-2.3-green`.

## Ground rules (these have bitten us every session)

- **TWO accounts → TWO CloudShell tabs.** The detonation lane + host + artifact are in
  **Forensic (360999005254)**; the durable tracking record is in the **Hub
  (641628980935)**. Deploy + detonate from a **Forensic-authed** shell; verify the
  crossed outcome from a **Hub-authed** shell. A banner comment does NOT change the
  account.
- **Run `aws sts get-caller-identity` BEFORE every block** and read `Account`. If it is
  not the account the block is for, switch tabs — do not proceed. (Recurring trap: a
  `ResourceNotFoundException` on the tracking table means you queried it from Forensic;
  it lives in the Hub.)
- **Feed commands ONE LINE AT A TIME.** Never paste a multi-line block.
- **`/tmp` is wiped when CloudShell recycles.** Re-clone/re-checkout if a session drops.
- **Region us-east-1**, ambient creds (no `--profile`).
- **GitHub auth in CloudShell:** token-in-URL HTTPS form
  `git remote set-url origin https://<TOKEN>@github.com/warrenrutledge64/ZTIE-Issues.git`.

## STEP 0 (Forensic tab) — get the 2.3 code

```
cd ~/ZTIE-Issues && git fetch origin -q && git checkout feature/story-2.3 && git reset --hard origin/feature/story-2.3
```
(If the 2.3 PR is already merged, use `main` instead.)

Confirm you are in Forensic:
```
aws sts get-caller-identity
```
Expect `"Account": "360999005254"`.

## STEP 1 (Forensic tab) — gather the deploy context values

The detonation stack imports coordinates from the Hub + intake + 2.0 stacks. Collect
them (these come from the already-deployed stacks' outputs):

```
aws cloudformation describe-stacks --stack-name ZtieIntakeStack --query "Stacks[0].Outputs" --output table
```
Note `ArtifactBucketName`, `DetonationQueueUrl`, `DetonationQueueArn`. (If the intake
stack pre-dates this PR, it must be re-deployed first so the new DetonationQueue exists
— see STEP 2.)

```
aws cloudformation describe-stacks --stack-name ZtieForensicInfraStack --query "Stacks[0].Outputs" --output table
```
Note `DetonationInstanceRoleArn`.

Hub ingest queue (from the Hub stack — you captured these when deploying the Hub):
`hubIngestQueueUrl`, `hubIngestQueueArn` (Hub output `IngestQueueUrl` / `IngestQueueArn`).

## STEP 2 (Forensic tab) — deploy the intake stack update + the detonation stack

The intake stack changed (it now creates the DetonationQueue + wires the preprocessor),
so deploy it first, then the new detonation stack.

```
cd ~/ZTIE-Issues/infra && npm ci
```
```
npx cdk deploy ZtieIntakeStack \
  -c hubIngestQueueUrl=<HUB_INGEST_QUEUE_URL> \
  -c hubIngestQueueArn=<HUB_INGEST_QUEUE_ARN>
```
Re-read `DetonationQueueUrl` / `DetonationQueueArn` from the updated outputs, then:
```
npx cdk deploy ZtieDetonationStack \
  -c artifactBucketName=<ARTIFACT_BUCKET_NAME> \
  -c detonationQueueUrl=<DETONATION_QUEUE_URL> \
  -c detonationQueueArn=<DETONATION_QUEUE_ARN> \
  -c hubIngestQueueUrl=<HUB_INGEST_QUEUE_URL> \
  -c hubIngestQueueArn=<HUB_INGEST_QUEUE_ARN> \
  -c detonationInstanceRoleArn=<DETONATION_INSTANCE_ROLE_ARN>
```
Record the `DetonationFunctionName` output. **PASTE the deploy tail back to the executor.**

> Also (also-good) re-deploy the Hub stack so the Hub validator Lambda ships the new
> `dynamic-run.contract.v1.json` bundle + the `DYNAMIC_RUN_CONTRACT_VERSION` pin:
> `npx cdk deploy ZtieHubTrackingStack` (Hub tab / Hub creds). Without this the crossed
> outcome will quarantine (fail-closed) rather than attach — which is itself a valid
> observation, but check 4 needs the Hub to accept it.

## STEP 3 (Forensic tab) — submit a routed artifact

Submit a small script artifact via the intake API (SigV4-signed, Forensic principal —
the same POST /intake you used to validate 1.x/2.1). A `raw_script` routes to BOTH
`static_analysis` and `dynamic_detonation`, so the detonation job will be enqueued.

Use a benign, obviously-behaving sample so the captured run is easy to read, e.g. a
one-line shell script that echoes and touches a file:
```
printf '#!/bin/sh\necho ZTIE-DETONATION-OK\ntouch /tmp/ztie-marker\n' > sample.sh
awscurl --service execute-api --region us-east-1 -X POST \
  -H 'Content-Type: application/octet-stream' --data-binary @sample.sh \
  "<INTAKE_ENDPOINT>"
```
Record the returned `intake_id`. **PASTE it back.**

## STEP 4 (Forensic tab) — watch the ephemeral EC2 run + tear down (checks 1–3)

Tail the detonation Lambda logs to see the launch + host-native SSM run + teardown:
```
aws logs tail /aws/lambda/<DetonationFunctionName> --since 10m --follow
```
Look for (paste these lines back): `launched ephemeral detonation host instance_id=i-...`,
`sent host-native SSM command command_id=...`, `detonation complete ... outcome=completed
ssm_status=Success teardown_observed=...`.

**Check 1 (launch from template):** confirm the instance was launched from the 2.0
template:
```
aws ec2 describe-instances --instance-ids <INSTANCE_ID> \
  --query "Reservations[0].Instances[0].{State:State.Name,LT:Tags[?Key=='aws:ec2launchtemplate:id']|[0].Value,Subnet:SubnetId,PubIp:PublicIpAddress}"
```
Expect a launch-template id, an isolated subnet, and `PubIp: null`.

**Check 2 (host-native SSM, no Docker):** confirm the command ran via SSM
`AWS-RunShellScript`:
```
aws ssm get-command-invocation --command-id <SSM_COMMAND_ID> --instance-id <INSTANCE_ID> \
  --query "{Status:Status,Doc:DocumentName,Rc:ResponseCode}"
```
Expect `Doc: "AWS-RunShellScript"`, a terminal `Status`, and the stdout should contain
`ZTIE-DETONATION-OK` (host-native execution — no container involved).

**Check 3 (5-min hard TTL teardown):** re-run the describe-instances state a few minutes
after launch:
```
aws ec2 describe-instances --instance-ids <INSTANCE_ID> --query "Reservations[0].Instances[0].State.Name"
```
Expect `shutting-down` or `terminated` within ~5 minutes of boot. **KNOWN CAVEAT — if it
is still `running` past the TTL, that is the finding: record it, do NOT pass check 3.**

## STEP 5 (Hub tab) — confirm the derived run outcome crossed (check 4)

Switch to the **Hub** tab and confirm identity FIRST:
```
aws sts get-caller-identity
```
Expect `"Account": "641628980935"`. Then read the tracking record:
```
aws dynamodb get-item --table-name <TRACKING_TABLE_NAME> \
  --key '{"intake_id":{"S":"<INTAKE_ID>"}}' \
  --query "Item.{outcome:dynamic_run_outcome.S,detonated_at:detonated_at.S,run:dynamic_run.M.outcome.S}"
```
Expect `dynamic_run_outcome` (e.g. `completed`) + `detonated_at` present, and inspect
`Item.dynamic_run` — it must carry `containment` (host_native/no_docker/isolated_subnet
true), `execution` (ssm_status, byte-capped tails + a Forensic `runs/` pointer), and
`teardown` — and **NO** verdict/safe/forward field. The full command log stays in
Forensic under `runs/<intake_id>/detonation-output.json` (do NOT expect it in the Hub).

## RECORD (executor)

Paste back, per check, the exact command output. The executor records a dated
Validation Result in RUNBOOK 2.3 + STORY_DETAIL 2.3:
- **PASS (4/4):** flip 2.3 ✅ (paired commit), keep PLAN ↔ RUNBOOK aligned, clear 2.3
  from the Validation Debt Register, capture/tag `restore/story-2.3-green`, then author
  the 2.4 session start.
- **FAIL (any check):** 2.3 stays 🟡; the executor fixes + you re-validate. A host still
  running past its TTL is a SEV finding, recorded, never passed.
