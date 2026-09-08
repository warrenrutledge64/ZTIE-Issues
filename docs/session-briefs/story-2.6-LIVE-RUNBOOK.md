# Story 2.6 — LIVE parallel-orchestration validation runbook (stakeholder, two CloudShells)

> **This is the ONLY live part of 2.6, and only YOU can do it** (the executor has no
> AWS creds). You DEPLOY the inspection-orchestration state machine, submit ONE routable
> artifact, watch the Step Functions execution fan out to BOTH lanes CONCURRENTLY for
> that `intake_id`, and confirm the single verdict-free `collected` join record landed
> on the Hub tracking record. The executor **records your returned output verbatim** into
> RUNBOOK 2.6 detail. **Nothing is recorded on inference** — paste back exactly what the
> commands print. On a 4/4 pass the executor flips 2.6 ✅ (paired commit), clears 2.6
> from the Validation Debt Register, and updates the Phase 2 phase-gate record (2.6
> closes Phase 2).

## Ground rules (these have bitten us every session)

- **TWO accounts → TWO CloudShell tabs.** The orchestration state machine, both lanes,
  the ephemeral host, and the artifact are all in **Forensic (360999005254)**; the
  durable tracking record where the joined record is verified is in the **Hub
  (641628980935)**. Deploy + submit + watch the fork from a **Forensic-authed** shell;
  verify the joined record from a **Hub-authed** shell. A banner comment does NOT change
  the account.
- **Run `aws sts get-caller-identity` BEFORE every block** and read `Account`. If it is
  not the account the block is for, switch tabs — do not proceed. (Recurring trap: a
  `ResourceNotFoundException` on the tracking table means you queried it from Forensic;
  it lives in the Hub.)
- **Feed commands ONE LINE AT A TIME.** Never paste a multi-line block.
- **`/tmp` + shell vars are WIPED when CloudShell recycles.** Every block below re-sets
  every variable it uses, in the SAME block, right before using it. If a session drops,
  just re-run the block from its `get-caller-identity` line.
- **Region us-east-1**, ambient creds (**no `--profile`**).
- **GitHub auth in CloudShell:** token-in-URL HTTPS form
  `git remote set-url origin https://<TOKEN>@github.com/warrenrutledge64/ZTIE-Issues.git`.

---

## STEP 0 (Forensic tab) — get the 2.6 code + confirm Forensic

```
aws sts get-caller-identity
```
**Run in: Forensic (360999005254), us-east-1, no --profile.** Expect
`"Account": "360999005254"`. Then check out the code (re-set the branch var in the same
block):

```
BRANCH=feature/story-2.6 ; cd ~/ZTIE-Issues && git fetch origin -q && git checkout "$BRANCH" && git reset --hard "origin/$BRANCH"
```
(If the 2.6 PR is already merged, set `BRANCH=main` instead.)

---

## STEP 1 (Forensic tab) — gather the deploy context values

```
aws sts get-caller-identity
```
**Run in: Forensic (360999005254), us-east-1, no --profile.** Expect `360999005254`.
The orchestration stack imports the two lane Lambda ARNs, the artifact bucket, and the
Hub ingest queue coordinates. Collect them from the already-deployed stacks' outputs
(re-set `REGION` in the same block):

```
REGION=us-east-1 ; aws cloudformation describe-stacks --region "$REGION" --stack-name ZtieStaticScanStack --query "Stacks[0].Outputs" --output table
```
Note `StaticScanFunctionName` (its ARN is `arn:aws:lambda:us-east-1:360999005254:function:<StaticScanFunctionName>`).

```
REGION=us-east-1 ; aws cloudformation describe-stacks --region "$REGION" --stack-name ZtieDetonationStack --query "Stacks[0].Outputs" --output table
```
Note `DetonationFunctionName` (its ARN is `arn:aws:lambda:us-east-1:360999005254:function:<DetonationFunctionName>`).

```
REGION=us-east-1 ; aws cloudformation describe-stacks --region "$REGION" --stack-name ZtieIntakeStack --query "Stacks[0].Outputs" --output table
```
Note `ArtifactBucketName` and the intake API endpoint you used for 1.x/2.1/2.3.

Hub ingest queue (from the Hub stack `ZtieHubTrackingStack` outputs `IngestQueueUrl` /
`IngestQueueArn` — the SAME values the intake + lane stacks already use):
`hubIngestQueueUrl`, `hubIngestQueueArn`.

---

## STEP 2 (Forensic tab) — deploy the orchestration stack + re-deploy the changed stacks

```
aws sts get-caller-identity
```
**Run in: Forensic (360999005254), us-east-1, no --profile.** Expect `360999005254`.
Install infra deps (re-set the dir in the same block):

```
cd ~/ZTIE-Issues/infra && env -u NODE_OPTIONS npm install
```
> **Use `npm install`, NOT `npm ci`** — this repo has no committed `package-lock.json`,
> so `npm ci` fails (2.0E live lesson, 2026-09-08).

> **CRITICAL (found live 2026-09-08): REDEPLOY BOTH LANE STACKS FIRST.** Story 2.6 adds
> a `_is_direct_invoke` path to BOTH lane handlers (`lambdas/static_scan/handler.py` +
> `lambdas/detonation/handler.py`) so a Step Functions Parallel branch can invoke them
> with a bare job dict and get the real summary/run back. The live lanes were deployed
> for 2.1/2.3 (BEFORE that code existed), so until you redeploy them they take the SQS
> path, loop over zero `Records`, and return `{"batchItemFailures": []}` — which the
> collector correctly records as `errored` (`both_complete:false`). SYMPTOM: a ~1s
> execution and both lanes `errored` with "produced no recognizable scan summary / run
> outcome." FIX: redeploy the two lane stacks so they carry the 2.6 handler code:
> ```
> cd ~/ZTIE-Issues/infra && env -u NODE_OPTIONS npx cdk deploy ZtieStaticScanStack -c artifactBucketName="<ArtifactBucketName>" -c staticScanQueueUrl="<StaticScanQueueUrl>" -c staticScanQueueArn="<StaticScanQueueArn>" -c hubIngestQueueUrl="<HUB_INGEST_QUEUE_URL>" -c hubIngestQueueArn="<HUB_INGEST_QUEUE_ARN>"
> ```
> ```
> cd ~/ZTIE-Issues/infra && env -u NODE_OPTIONS npx cdk deploy ZtieDetonationStack -c artifactBucketName="<ArtifactBucketName>" -c detonationQueueUrl="<DetonationQueueUrl>" -c detonationQueueArn="<DetonationQueueArn>" -c hubIngestQueueUrl="<HUB_INGEST_QUEUE_URL>" -c hubIngestQueueArn="<HUB_INGEST_QUEUE_ARN>" -c detonationInstanceRoleArn="<DetonationInstanceRoleArn>"
> ```
> (All the `<...>` values come from the STEP 1 stack-output lookups.) Only AFTER both
> lane stacks are redeployed does the fork actually run the lanes.

Deploy the NEW orchestration stack. The stack (`ZtieOrchestrationStack`,
`infra/lib/ztie-orchestration-stack.ts`, wired in `infra/bin/ztie-infra.ts`) is a
Step Functions STANDARD state machine — a Parallel state with a `static` branch and a
`dynamic` branch (each with a per-branch Catch) and a terminal collector-invoking join
task. Re-set every context var in the SAME block, one line at a time:

```
STATIC_FN_ARN=arn:aws:lambda:us-east-1:360999005254:function:<StaticScanFunctionName> ; DETON_FN_ARN=arn:aws:lambda:us-east-1:360999005254:function:<DetonationFunctionName> ; ARTIFACT_BUCKET=<ArtifactBucketName> ; HUB_Q_URL=<HUB_INGEST_QUEUE_URL> ; HUB_Q_ARN=<HUB_INGEST_QUEUE_ARN> ; cd ~/ZTIE-Issues/infra && env -u NODE_OPTIONS npx cdk deploy ZtieOrchestrationStack -c staticScanFunctionArn="$STATIC_FN_ARN" -c detonationFunctionArn="$DETON_FN_ARN" -c artifactBucketName="$ARTIFACT_BUCKET" -c hubIngestQueueUrl="$HUB_Q_URL" -c hubIngestQueueArn="$HUB_Q_ARN"
```
Record the `InspectionStateMachineArn`, `CollectorFunctionName`, and `CollectorRoleArn`
outputs. **PASTE the deploy tail back to the executor.**

Now RE-DEPLOY the intake stack passing the state-machine ARN so the preprocessor
switches from the two independent enqueues to starting ONE concurrent fork execution
(`ORCHESTRATION_STATE_MACHINE_ARN` + a scoped `states:StartExecution`). Re-set vars in
the same block:

```
HUB_Q_URL=<HUB_INGEST_QUEUE_URL> ; HUB_Q_ARN=<HUB_INGEST_QUEUE_ARN> ; SM_ARN=<InspectionStateMachineArn> ; cd ~/ZTIE-Issues/infra && env -u NODE_OPTIONS npx cdk deploy ZtieIntakeStack -c hubIngestQueueUrl="$HUB_Q_URL" -c hubIngestQueueArn="$HUB_Q_ARN" -c orchestrationStateMachineArn="$SM_ARN"
```

> Also re-deploy the Hub stack so the Hub validator Lambda ships the new
> `collected.contract.v1.json` bundle + the `COLLECTED_CONTRACT_VERSION` pin (and, for
> tightest least-privilege, add the collector as a send-only principal on the ingest
> queue). Do this in the **Hub tab** with **Hub creds** — see STEP 5's identity check:
> `env -u NODE_OPTIONS npx cdk deploy ZtieHubTrackingStack -c forensicCollectorRoleArn=<CollectorRoleArn>`. Without this the crossed `collected` record will
> quarantine (fail-closed) rather than attach — which is itself a valid observation, but
> DoD item 2 needs the Hub to accept the join.

---

## STEP 3 (Forensic tab) — submit ONE routable artifact via intake

```
aws sts get-caller-identity
```
**Run in: Forensic (360999005254), us-east-1, no --profile.** Expect `360999005254`.
Submit a small script artifact via the intake API (SigV4-signed, Forensic principal —
the same `POST /intake` you used for 1.x/2.1/2.3). A `raw_script` routes to BOTH
`static_analysis` and `dynamic_detonation`, so the preprocessor starts ONE fork
execution that fans out to both lanes. Re-set the endpoint var in the same block:

```
INTAKE_ENDPOINT=<INTAKE_ENDPOINT_FROM_STEP_1> ; printf '#!/bin/sh\necho ZTIE-FORK-OK\ntouch /tmp/ztie-marker\n' > sample.sh && awscurl --service execute-api --region us-east-1 -X POST -H 'Content-Type: application/octet-stream' --data-binary @sample.sh "$INTAKE_ENDPOINT"
```
Record the returned `intake_id`. **PASTE it back.**

---

## STEP 4 (Forensic tab) — observe BOTH branches run CONCURRENTLY (DoD 1)

```
aws sts get-caller-identity
```
**Run in: Forensic (360999005254), us-east-1, no --profile.** Expect `360999005254`.
Find the execution the preprocessor started for this `intake_id`, then read its history.
Re-set the state-machine ARN + region in the same block:

```
SM_ARN=<InspectionStateMachineArn> ; REGION=us-east-1 ; aws stepfunctions list-executions --region "$REGION" --state-machine-arn "$SM_ARN" --max-results 5 --query "executions[].{name:name,status:status,started:startDate}" --output table
```
Identify the execution for your `intake_id` (the preprocessor names/tags executions by
`intake_id`; if the name is opaque, pick the most recent `startDate` matching your
submit) and capture its ARN:

```
SM_ARN=<InspectionStateMachineArn> ; REGION=us-east-1 ; aws stepfunctions list-executions --region "$REGION" --state-machine-arn "$SM_ARN" --max-results 5 --query "executions[0].executionArn" --output text
```

Now prove BOTH branches were in flight AT THE SAME TIME (parallel, not sequential). Dump
the execution history and look at the `TaskStateEntered` / task-scheduled events for the
two lane tasks — the dynamic-lane task ENTERS while the static-lane task is still running
(their running intervals OVERLAP), which is only possible under the Parallel state:

```
EXEC_ARN=<EXECUTION_ARN_FROM_ABOVE> ; REGION=us-east-1 ; aws stepfunctions get-execution-history --region "$REGION" --execution-arn "$EXEC_ARN" --max-results 200 --query "events[?contains(type, 'Task') || contains(type, 'Parallel')].{id:id,ts:timestamp,type:type,name:stateEnteredEventDetails.name}" --output table
```
**PASTE this table back.** A PASS shows a `ParallelStateEntered`, then BOTH the static
and the dynamic lane tasks ENTERED (scheduled/started) before EITHER lane's task
`Succeeded` — the two lanes' running windows overlap in time. If instead the dynamic
task only enters AFTER the static task succeeded (no overlap), that is SEQUENTIAL — do
NOT pass DoD item 1; record the finding.

Optionally cross-check the two lane Lambdas both logged this `intake_id` with overlapping
timestamps (re-set the function names in the same block):
```
STATIC_FN=<StaticScanFunctionName> ; INTAKE_ID=<INTAKE_ID> ; aws logs filter-log-events --region us-east-1 --log-group-name "/aws/lambda/$STATIC_FN" --filter-pattern "\"$INTAKE_ID\"" --query "events[].{ts:timestamp,msg:message}" --output text
```
```
DETON_FN=<DetonationFunctionName> ; INTAKE_ID=<INTAKE_ID> ; aws logs filter-log-events --region us-east-1 --log-group-name "/aws/lambda/$DETON_FN" --filter-pattern "\"$INTAKE_ID\"" --query "events[].{ts:timestamp,msg:message}" --output text
```

You can also confirm the terminal join fired by tailing the collector:
```
COLLECTOR_FN=<CollectorFunctionName> ; INTAKE_ID=<INTAKE_ID> ; aws logs filter-log-events --region us-east-1 --log-group-name "/aws/lambda/$COLLECTOR_FN" --filter-pattern "\"$INTAKE_ID\"" --query "events[].message" --output text
```
Expect a line showing `lanes_expected` = both lanes, `lanes_collected` = both,
`both_complete=true`, per-lane status. **PASTE it back.**

---

## STEP 4b (Forensic tab) — confirm the SYNCHRONOUS detonation timeout budget (review v1, issue 4)

Under the fork the dynamic branch invokes the detonation Lambda SYNCHRONOUSLY: the
`LambdaInvoke` blocks until the Lambda returns, and the Lambda blocks on the full
ephemeral-EC2 launch + host-native SSM run. The timeout budgets MUST nest so a slow
(but healthy) run returns a real `run` outcome rather than the Lambda container timing
out — a container timeout would trip the branch `Catch` and record a SPURIOUS `errored`
while the host keeps running to its hard TTL. The expected, code-pinned nesting is:

| Budget | Where set | Expected value | Must be |
| --- | --- | --- | --- |
| Host hard TTL (`shutdown -h`) | 2.0 launch-template UserData (`HARD_TTL_MINUTES`) | **5 min (300 s)** | the innermost guaranteed backstop |
| Detonation internal orchestration | `handler.py` (`SSM_ONLINE_TIMEOUT_S` 120 + `EXEC_TIMEOUT_S` 120 + `EXEC_POLL_TIMEOUT_S` 150 + `TEARDOWN_OBSERVE_TIMEOUT_S` 60 ≈ **≤ 450 s** worst case) | must **cover** the 300 s host run |
| Detonation **Lambda** timeout | `ztie-detonation-stack.ts` `Duration.seconds(840)` = **14 min** | must **span** the whole synchronous run (> internal budget, > host TTL) |
| Detonation queue visibility (SQS path only) | detonation stack, **900 s** | > Lambda timeout (unchanged, SQS path) |
| State-machine timeout | `ztie-orchestration-stack.ts` `Duration.minutes(20)` = **1200 s** | must **exceed** the Lambda timeout so SFN does not kill the branch first |
| `LambdaInvoke` task timeout (both branches) | orchestration stack | **unset** (no per-task timeout) | must NOT be shorter than the Lambda timeout |

So the ordering the code ships is: `host TTL 300 s  <  internal ≤ 450 s  <  Lambda 840 s  <  state machine 1200 s`, and NO per-branch `LambdaInvoke` task timeout truncates it. That ordering is correct on paper; it can only be TRULY confirmed with a real ~5-min detonation. Confirm it live here:

```
aws sts get-caller-identity
```
**Run in: Forensic (360999005254), us-east-1, no --profile.** Expect `360999005254`.
Confirm the detonation Lambda's configured timeout is 840 s (re-set the function name in
the same block):
```
DETON_FN=<DetonationFunctionName> ; aws lambda get-function-configuration --region us-east-1 --function-name "$DETON_FN" --query "Timeout" --output text
```
Expect **`840`**. Then, for THIS run's execution, confirm the dynamic branch task
returned via a real Lambda return (a `TaskSucceeded`/`TaskStateExited` for the dynamic
lane) and did NOT hit `States.Timeout` / a Lambda `Task timed out` error that routed into
the `DynamicLaneErrored` Pass:
```
EXEC_ARN=<EXECUTION_ARN_FROM_STEP_4> ; REGION=us-east-1 ; aws stepfunctions get-execution-history --region "$REGION" --execution-arn "$EXEC_ARN" --max-results 500 --query "events[?contains(type,'TaskFailed') || contains(type,'ExecutionTimedOut') || contains(type,'TaskTimedOut')].{id:id,ts:timestamp,type:type,cause:taskFailedEventDetails.cause}" --output table
```
**PASTE this back.** A PASS shows **no `TaskTimedOut` / `Task timed out` cause for the
dynamic lane** (an empty table, or only NON-timeout entries). If the dynamic lane shows a
`Task timed out` / `States.Timeout` cause while the host log shows the run still executing
to its TTL, the Lambda timeout is too short for a real synchronous run — record the
finding and raise the detonation Lambda timeout (still under the 900 s SQS visibility and
the 1200 s state-machine ceiling) before re-validating.

---

## STEP 5 (Hub tab) — confirm the single verdict-free JOINED record (DoD 2 + 3)

Switch to the **Hub** tab and confirm identity FIRST:
```
aws sts get-caller-identity
```
**Run in: Hub (641628980935), us-east-1, no --profile.** Expect `"Account": "641628980935"`.
(A `ResourceNotFoundException` here means you are still in the Forensic tab — switch.)

Get the tracking table name (re-set region in the same block):
```
REGION=us-east-1 ; aws cloudformation describe-stacks --region "$REGION" --stack-name ZtieHubTrackingStack --query "Stacks[0].Outputs[?OutputKey=='TrackingTableName'].OutputValue" --output text
```

Read the joined record for your `intake_id` (re-set both vars in the same block):
```
TABLE=<TrackingTableName> ; INTAKE_ID=<INTAKE_ID> ; aws dynamodb get-item --region us-east-1 --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$INTAKE_ID\"}}" --query "Item.{lanes:collected_lanes,joined_at:joined_at.S,collected:collected.M}" --output json
```
**PASTE this back.** A PASS shows a SINGLE `collected` object tying `static_scan` and
`dynamic_run` together for the one `intake_id` — `collected_lanes` lists BOTH lanes, the
`collected.M` object carries `lanes_expected` / `lanes_collected` (both), per-lane status
+ Forensic pointers (findings/ and runs/), and `joined_at` is set.

**DoD item 3 — NO verdict/safe/approved/forward field anywhere.** Dump the whole item
and grep the raw JSON for any decision field (re-set both vars in the same block):
```
TABLE=<TrackingTableName> ; INTAKE_ID=<INTAKE_ID> ; aws dynamodb get-item --region us-east-1 --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$INTAKE_ID\"}}" --output json | grep -Ei 'verdict|safe|approved|forward'
```
A PASS returns **NO matching lines** (empty output). Any hit is a containment failure —
do NOT pass DoD item 3; record the finding. (The full per-lane logs stay in Forensic
under `findings/<intake_id>/…` and `runs/<intake_id>/…`; do NOT expect them in the Hub.)

---

## DoD 4 — containment / boundaries intact (carried from 2.1 + 2.3)

The orchestration stack only ORCHESTRATES the existing lanes — it does not re-implement
either lane, launch a host, or move raw payload. So DoD item 4 is confirmed by
inspection of the joined record + the lane facts already validated:
- **Dynamic lane host-native, no Docker (RD-001):** the `collected` record's dynamic-lane
  entry carries the 2.3 containment flags (`host_native`/`no_docker`/`isolated_subnet`);
  the ephemeral host still self-terminates on the 5-min hard TTL (re-verify per the
  [Story 2.3 LIVE runbook](story-2.3-LIVE-RUNBOOK.md) if a fresh host launched).
- **Isolated VPC unchanged:** no orchestration change to the 2.0 network foundation.
- **No durable Forensic store (RD-012):** the only durable record is the Hub tracking
  record; Forensic keeps only the `findings/` + `runs/` artifacts it already kept.
- **No raw-payload crossing:** the `collected` envelope is bounded evidence (per-lane
  status + pointers), never the artifact body — confirm there is no base64/raw body in
  the item you dumped in STEP 5.

---

## What a PASS looks like (the 4 DoD gate the stakeholder confirms live)

1. **Concurrent fork.** STEP 4's execution history shows a `ParallelStateEntered` and
   BOTH lane tasks ENTERED before EITHER `Succeeded` (overlapping running windows) for
   the one `intake_id` — parallel, not sequential.
2. **Both lanes collected / joined.** STEP 5 shows ONE `collected` record with
   `collected_lanes` = both lanes and `both_complete`/`lanes_collected` = both, tying
   `static_scan` + `dynamic_run` together for that `intake_id`, ready for Phase 3.
3. **Evidence, not a decision.** STEP 5's grep for `verdict|safe|approved|forward`
   returns NO lines anywhere in the item.
4. **Containment intact.** Dynamic lane host-native (no Docker, RD-001); isolated VPC
   unchanged; only-durable-store is the Hub record (RD-012); no raw-payload crossing.

**Goes ✅ ONLY when you confirm a live 4/4 pass AND the executor RECORDS it in
RUNBOOK.md.** No recorded pass → 2.6 stays 🟡 (it remains the open Validation Debt
Register entry, keeping the advancement gate armed).

---

## RECORD (executor)

Paste back, per DoD item, the exact command output. The executor records a dated
Validation Result in RUNBOOK 2.6 + STORY_DETAIL 2.6:
- **PASS (4/4):** flip 2.6 ✅ (paired commit), keep PLAN ↔ RUNBOOK ↔ STORY_DETAIL
  aligned, clear 2.6 from the Validation Debt Register, and update the **Phase 2
  phase-gate record (2.6 closes Phase 2)**. The executor **records your returned output
  verbatim — it does not simulate a run.**
- **FAIL (any DoD item):** 2.6 stays 🟡; the executor fixes + you re-validate.

---

## NEXT STORY (pointer — do NOT flip any status now)

After 2.6's recorded live pass closes Phase 2, the next work by RUNBOOK build tier is the
Floor & Harvest clean-ground pair **A.5** (correct the Floor & Harvest plan drift) +
**A.6** (push the outstanding deployed-state restore tags), which together GATE **2.4**
(behavioral telemetry capture), followed by **3.1** (telemetry aggregation) once the fork
feeds Phase 3. Seed that story's brief with THIS session's Lessons Learned:
- The preprocessor fork switch is a RE-DEPLOY of the intake stack with
  `orchestrationStateMachineArn` — a two-phase deploy (orchestration stack first, then
  intake re-deploy) because the state-machine ARN is an output of the first.
- The `collected` join is the 7th RD-013 envelope kind on the SAME Hub ingest queue,
  pinned by its OWN `COLLECTED_CONTRACT_VERSION` (never the shared `CONTRACT_VERSION`) —
  the Hub stack MUST be re-deployed to ship the new contract bundle or the join
  quarantines fail-closed.
- Proving "parallel, not sequential" is done from the Step Functions execution HISTORY
  (overlapping task-entered/succeeded windows under the Parallel state), not from log
  wall-clock alone.
