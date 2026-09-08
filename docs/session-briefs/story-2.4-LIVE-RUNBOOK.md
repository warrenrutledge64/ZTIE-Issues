# Story 2.4 — LIVE behavioral-telemetry validation runbook (stakeholder, two CloudShells)

> **This is the ONLY live part of 2.4, and only YOU can do it** (the executor has no
> AWS creds). You REDEPLOY the changed detonation lane + the Hub gate, submit ONE
> routable artifact, watch the ephemeral host CAPTURE its own behavior host-native, and
> confirm a bounded, verdict-free behavioral-telemetry summary landed on the Hub
> tracking record while the FULL trace stayed in Forensic. The executor **records your
> returned output verbatim** into RUNBOOK 2.4 detail. **Nothing is recorded on
> inference** — paste back exactly what the commands print. On a 4/4 pass the executor
> flips 2.4 ✅ (paired commit) and clears 2.4 from the Validation Debt Register.

## Ground rules (these have bitten us every session)

- **TWO accounts → TWO CloudShell tabs.** The detonation lane, the ephemeral host, the
  capture, the artifact, and the full trace are all in **Forensic (360999005254)**; the
  durable tracking record where the crossed summary is verified is in the **Hub
  (641628980935)**. Deploy + submit + watch capture from a **Forensic-authed** shell;
  verify the crossed summary from a **Hub-authed** shell. A banner comment does NOT
  change the account.
- **Run `aws sts get-caller-identity` BEFORE every block** and read `Account`. If it is
  not the account the block is for, switch tabs — do not proceed. (Recurring trap: a
  `ResourceNotFoundException` on the tracking table means you queried it from Forensic;
  it lives in the Hub.)
- **Feed commands ONE LINE AT A TIME.** Never paste a multi-line block.
- **`/tmp` + shell vars are WIPED when CloudShell recycles.** Every block below re-sets
  every variable it uses, in the SAME block, right before using it. If a session drops,
  re-run the block from its `get-caller-identity` line.
- **Region us-east-1**, ambient creds (**no `--profile`**).
- **GitHub auth in CloudShell:** token-in-URL HTTPS form
  `git remote set-url origin https://<TOKEN>@github.com/warrenrutledge64/ZTIE-Issues.git`.

---

## STEP 0 (Forensic tab) — get the 2.4 code + confirm Forensic

```
aws sts get-caller-identity
```
**Run in: Forensic (360999005254), us-east-1, no --profile.** Expect
`"Account": "360999005254"`. Then check out the code (re-set the branch var in the same
block):

```
BRANCH=feature/story-2.4 ; cd ~/ZTIE-Issues && git fetch origin -q && git checkout "$BRANCH" && git reset --hard "origin/$BRANCH"
```
(If the 2.4 PR is already merged, set `BRANCH=main` instead.)

---

## STEP 1 (Forensic tab) — gather the deploy context values

```
aws sts get-caller-identity
```
**Run in: Forensic (360999005254), us-east-1, no --profile.** Expect `360999005254`.
The detonation stack imports the artifact bucket, the detonation work queue, the Hub
ingest queue coordinates, and the detonation instance-role ARN. Collect them from the
already-deployed stacks' outputs (re-set `REGION` in the same block):

```
REGION=us-east-1 ; aws cloudformation describe-stacks --region "$REGION" --stack-name ZtieDetonationStack --query "Stacks[0].Outputs" --output table
```
Note `DetonationFunctionName`.

```
REGION=us-east-1 ; aws cloudformation describe-stacks --region "$REGION" --stack-name ZtieIntakeStack --query "Stacks[0].Outputs" --output table
```
Note `ArtifactBucketName`, `DetonationQueueUrl`, `DetonationQueueArn`, and the intake API
endpoint you used for 1.x/2.1/2.3/2.6.

```
REGION=us-east-1 ; aws cloudformation describe-stacks --region "$REGION" --stack-name ZtieForensicInfraStack --query "Stacks[0].Outputs[?OutputKey=='DetonationInstanceRoleArn'].OutputValue" --output text
```
Note `DetonationInstanceRoleArn`.

Hub ingest queue (from the Hub stack `ZtieHubTrackingStack` outputs `IngestQueueUrl` /
`IngestQueueArn` — the SAME values the intake + lane stacks already use):
`hubIngestQueueUrl`, `hubIngestQueueArn`.

---

## STEP 2 (Forensic tab) — REDEPLOY the detonation lane (the deploy-gap step)

```
aws sts get-caller-identity
```
**Run in: Forensic (360999005254), us-east-1, no --profile.** Expect `360999005254`.
Install infra deps (re-set the dir in the same block):

```
cd ~/ZTIE-Issues/infra && env -u NODE_OPTIONS npm install
```
> **Use `npm install`, NOT `npm ci`** — this repo has no committed `package-lock.json`,
> so `npm ci` fails (2.0E live lesson).

> **CRITICAL (deploy-gap, the top 2.4 watch-item — learned live in 2.6, 2026-09-08).**
> Story 2.4 CHANGES the detonation lane handler (`lambdas/detonation/handler.py` now
> runs the artifact under `strace` and crosses a new `behavior` envelope). Story 2.6's
> orchestration DIRECT-INVOKES that same handler. If you submit a run BEFORE redeploying
> the detonation stack, the LIVE lane is still on its pre-2.4 code — no capture happens
> and no `behavior` record crosses, even though your new code is "done". So you MUST
> redeploy `ZtieDetonationStack` (ships the new handler + `capturespec.py` +
> `behavior.py` + the bundled `behavior.contract.v1.json` + the `BEHAVIOR_CONTRACT_VERSION`
> / `TRACES_PREFIX` env + the `traces/*` grant) BEFORE submitting. Re-set every context
> var in the SAME block, one line at a time:

```
ARTIFACT_BUCKET=<ArtifactBucketName> ; DETON_Q_URL=<DetonationQueueUrl> ; DETON_Q_ARN=<DetonationQueueArn> ; HUB_Q_URL=<HUB_INGEST_QUEUE_URL> ; HUB_Q_ARN=<HUB_INGEST_QUEUE_ARN> ; DETON_ROLE_ARN=<DetonationInstanceRoleArn> ; cd ~/ZTIE-Issues/infra && env -u NODE_OPTIONS npx cdk deploy ZtieDetonationStack -c artifactBucketName="$ARTIFACT_BUCKET" -c detonationQueueUrl="$DETON_Q_URL" -c detonationQueueArn="$DETON_Q_ARN" -c hubIngestQueueUrl="$HUB_Q_URL" -c hubIngestQueueArn="$HUB_Q_ARN" -c detonationInstanceRoleArn="$DETON_ROLE_ARN"
```
**PASTE the deploy tail back to the executor.**

> **Also REDEPLOY the Hub stack** so the Hub validator Lambda ships the new
> `behavior.contract.v1.json` bundle + the `BEHAVIOR_CONTRACT_VERSION` pin. Without this
> the crossed `behavior` record QUARANTINES fail-closed (unknown-version / unknown
> contract) rather than attaching — which is itself a valid observation, but DoD item 3
> needs the Hub to accept the summary. Do this in the **Hub tab** with **Hub creds** —
> see STEP 5's identity check first, then:
> `cd ~/ZTIE-Issues/infra && env -u NODE_OPTIONS npx cdk deploy ZtieHubTrackingStack`
> (pass the same context args that stack already expects; the only 2.4 change is the
> bundled contract + the `BEHAVIOR_CONTRACT_VERSION` env).

> **AMI note (expected, not a failure):** `strace` must be pre-baked on the ubuntu-22.04
> golden AMI. This repo does NOT build the AMI (Image-Builder-owned). If `strace` is not
> yet on the AMI, the run will capture `capture_status=tool_unavailable` and run the
> artifact uninstrumented — the graceful-degradation path working AS DESIGNED (a recorded
> gap, not a crash). For a FULL 4/4 pass with real captured behavior, `strace` must be on
> the AMI first; if it is not, record the `tool_unavailable` result honestly and treat
> "bake strace into the golden AMI" as the blocking pre-req (Image-Builder work). You can
> confirm whether the AMI ships strace by checking a prior run's host, or by adding
> `strace` to the Image Builder component and rebuilding `/ztie/ami/ubuntu-22.04`.

---

## STEP 3 (Forensic tab) — submit ONE routable artifact that DOES something observable

```
aws sts get-caller-identity
```
**Run in: Forensic (360999005254), us-east-1, no --profile.** Expect `360999005254`.
Submit a small `raw_script` that makes clearly-observable syscalls: touches a file
(filesystem), and ATTEMPTS an outbound connection (network INTENT — it will FAIL in the
isolated VPC, which is exactly the signal we capture). The intake API wants a JSON
envelope via `awscurl` (SigV4, Forensic principal), NOT a raw body. Re-set the endpoint
var in the same block, one line at a time:

```
INTAKE_ENDPOINT=<INTAKE_ENDPOINT_FROM_STEP_1>
```
```
printf '#!/bin/sh\necho ZTIE-BEHAVIOR-OK\ntouch /tmp/ztie-evil.txt\n(exec 3<>/dev/tcp/93.184.216.34/443) 2>/dev/null || true\nrm -f /tmp/ztie-evil.txt\n' > sample.sh
```
```
python3 -c "import base64,json;b=open('sample.sh','rb').read();print(json.dumps({'filename':'sample.sh','content_type':'application/x-sh','submitter':'ztie-2.4-live','content_base64':base64.b64encode(b).decode()}))" > intake.json
```
```
pip install awscurl >/dev/null 2>&1 ; awscurl --service execute-api --region us-east-1 -X POST -H 'Content-Type: application/json' -d @intake.json "$INTAKE_ENDPOINT"
```
Record the returned `intake_id`. **PASTE it back.**

---

## STEP 4 (Forensic tab) — confirm capture ran host-native + the FULL trace stayed in Forensic (DoD 1 + 2)

```
aws sts get-caller-identity
```
**Run in: Forensic (360999005254), us-east-1, no --profile.** Expect `360999005254`.
Tail the detonation Lambda for this `intake_id` — it should log the launched instance,
the SSM command (with capture), the detonation completing, and the behavioral summary
crossing. Re-set both vars in the same block:

```
DETON_FN=<DetonationFunctionName> ; INTAKE_ID=<INTAKE_ID> ; aws logs filter-log-events --region us-east-1 --log-group-name "/aws/lambda/$DETON_FN" --filter-pattern "\"$INTAKE_ID\"" --query "events[].message" --output text
```
**PASTE it back.** Expect lines showing the host launched, the host-native SSM command
sent (with capture), the detonation completing, and (if `strace` was on the AMI) the
behavioral telemetry crossing.

**DoD 2 — the FULL trace stays in Forensic (RD-009).** Confirm the full behavioral trace
was written to Forensic S3 under `traces/<intake_id>/` (re-set both vars in the same
block):
```
ARTIFACT_BUCKET=<ArtifactBucketName> ; INTAKE_ID=<INTAKE_ID> ; aws s3 ls "s3://$ARTIFACT_BUCKET/traces/$INTAKE_ID/"
```
**PASTE it back.** A PASS shows `behavior-trace.txt` present (when `strace` captured). You
can spot-check it is a real strace trace (stays in Forensic — do NOT copy it to the Hub):
```
ARTIFACT_BUCKET=<ArtifactBucketName> ; INTAKE_ID=<INTAKE_ID> ; aws s3 cp "s3://$ARTIFACT_BUCKET/traces/$INTAKE_ID/behavior-trace.txt" - | head -30
```
Expect strace-shaped lines (e.g. `openat(... "/tmp/ztie-evil.txt" ...)`, a `connect(...`
to `93.184.216.34:443` that returns an error — the failed attempt is the captured
INTENT). If instead the run recorded `tool_unavailable` (no `traces/` object), see the
AMI note in STEP 2 — that is the graceful-degradation path, not a code failure.

---

## STEP 5 (Hub tab) — confirm the bounded, verdict-free behavioral SUMMARY crossed (DoD 3 + 4)

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

Read the behavioral telemetry for your `intake_id` (re-set both vars in the same block):
```
TABLE=<TrackingTableName> ; INTAKE_ID=<INTAKE_ID> ; aws dynamodb get-item --region us-east-1 --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$INTAKE_ID\"}}" --query "Item.{capture_status:behavior_capture_status.S,captured_at:captured_at.S,behavior:behavior.M}" --output json
```
**PASTE this back.** A PASS shows a SINGLE `behavior` object for the one `intake_id`:
- `behavior.capture` with `capture_tool` = `strace`, `capture_status` = `captured`,
  `host_native` = true, `no_docker` = true, and RELATIVE `capture_started_offset_ms` /
  `capture_stopped_offset_ms` (integers, NOT wall-clock timestamps);
- `behavior.syscalls` (total + top), `behavior.network` (connect_attempts >= 1, a
  destination `93.184.216.34:443` with `connected: false` — INTENT captured), and
  `behavior.filesystem` (a `/tmp/ztie-evil.txt` path with a create/delete op);
- a `behavior.capture.trace_s3_bucket` / `trace_s3_key` POINTER back to the Forensic
  trace (the full trace stays in Forensic — only this pointer + the bounded summary
  crossed).

**DoD item 3 — NO verdict/safe/approved/forward field anywhere.** Dump the whole item and
grep the raw JSON for any decision field (re-set both vars in the same block):
```
TABLE=<TrackingTableName> ; INTAKE_ID=<INTAKE_ID> ; aws dynamodb get-item --region us-east-1 --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$INTAKE_ID\"}}" --output json | grep -Ei 'verdict|safe|approved|forward|malicious|pass_fail'
```
A PASS returns **NO matching lines** (empty output). Any hit is a containment failure —
do NOT pass DoD item 3; record the finding.

**DoD item 4 — relative clock only.** Confirm the behavioral timings are relative
monotonic offsets, never a wall clock (re-set both vars in the same block):
```
TABLE=<TrackingTableName> ; INTAKE_ID=<INTAKE_ID> ; aws dynamodb get-item --region us-east-1 --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$INTAKE_ID\"}}" --query "Item.behavior.M.capture.M.{started:capture_started_offset_ms.N,stopped:capture_stopped_offset_ms.N}" --output json
```
A PASS shows integer millisecond offsets (e.g. `"started":"1200","stopped":"63000"`), NOT
an ISO timestamp. (The only wall-clock field is the envelope `captured_at`, for audit
correlation.)

---

## What a PASS looks like (the 4 DoD gate the stakeholder confirms live)

1. **Behavior captured host-native (NO Docker).** During a real detonation the ephemeral
   host captured the artifact's syscalls + network connection attempts + filesystem ops
   with `strace`, host-native over SSM — STEP 4's Lambda log + the `traces/` object.
2. **Full trace stays in Forensic (RD-009).** STEP 4 shows `behavior-trace.txt` in
   Forensic S3 under `traces/<intake_id>/`; it never crossed to the Hub.
3. **Bounded, verdict-free summary crossed to the Hub.** STEP 5 shows ONE `behavior`
   record (own version pin) with the three bounded summaries + a Forensic pointer, and
   the grep for `verdict|safe|approved|forward` returns NO lines.
4. **Relative clock only.** The behavioral timings are relative monotonic offsets, never
   a wall clock.

**Goes ✅ ONLY when you confirm a live 4/4 pass AND the executor RECORDS it in
RUNBOOK.md.** No recorded pass → 2.4 stays 🟡 (it remains the open Validation Debt
Register entry, keeping the advancement gate armed).

> **If `strace` is not on the AMI:** STEP 4/5 will show `capture_status=tool_unavailable`
> with NO `traces/` object and NO summaries — the graceful-degradation path working (the
> lane did not crash, the 2.3 run outcome is unaffected). This is NOT a 4/4 pass for the
> capture DoD; record it honestly and treat "bake `strace` into the ubuntu-22.04 golden
> AMI" (Image-Builder work, tracked outside this repo/story) as the blocking pre-req,
> then re-run this runbook.

---

## RECORD (executor)

Paste back, per DoD item, the exact command output. The executor records a dated
Validation Result in RUNBOOK 2.4 + STORY_DETAIL 2.4:
- **PASS (4/4):** flip 2.4 ✅ (paired commit), keep PLAN ↔ RUNBOOK ↔ STORY_DETAIL
  aligned, clear 2.4 from the Validation Debt Register, and capture a restore point
  (owner action). The executor **records your returned output verbatim — it does not
  simulate a run.**
- **FAIL (any DoD item):** 2.4 stays 🟡; the executor fixes + you re-validate.

---

## NEXT STORY (pointer — do NOT flip any status now)

After 2.4's recorded live pass, the next work by RUNBOOK build tier is **2.5** (telemetry
sanitization pipeline: entropy scrub → noise suppress → ≤25K truncation), which depends
on 2.4's raw telemetry. Seed 2.5's brief with THIS session's Lessons Learned:
- The deploy-gap redeploy of `ZtieDetonationStack` (and the Hub stack for the new
  contract bundle) is a MANDATORY pre-run step whenever a story changes a lane handler
  the 2.6 orchestration direct-invokes.
- `strace` must be pre-baked on the golden AMI (Image-Builder-owned, outside this repo) —
  the isolated host has no internet to install at boot; the lane degrades gracefully to
  `tool_unavailable` if it is absent.
- Network capture in the isolated VPC is about INTENT: connection attempts fail (no
  egress) but the attempt is the captured signal (`connected: false`).
- Behavioral timings cross as RELATIVE monotonic offsets from detonation start, never a
  wall clock.
