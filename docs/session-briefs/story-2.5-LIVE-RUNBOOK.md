# Story 2.5 — LIVE VALIDATION RUNBOOK (telemetry sanitization pipeline)

> **This is the ONLY live part of 2.5, and only YOU (the stakeholder) can do it** — the
> executor has no AWS creds. You **redeploy the detonation lane + Hub stacks** (deploy-gap),
> submit ONE artifact through intake, let it detonate host-native + get captured (2.4) and
> **SANITIZED (2.5)**, then confirm the single verdict-free `sanitized` record landed on the
> Hub tracking record with host noise + high-entropy blobs removed, the artifact's behavior
> preserved, bounded to ≤25K tokens with a `truncated` flag, and the FULL raw trace still in
> Forensic (RD-009). The executor **records your returned output verbatim** into RUNBOOK 2.5.
> **Nothing is recorded on inference** — paste back exactly what the commands print. On a 4/4
> pass the executor flips 2.5 ✅ (paired commit) and clears 2.5 from the Validation Debt
> Register.

## Ground rules (these have bitten us every session)

- **TWO accounts → TWO CloudShell tabs.** The detonation host, capture, sanitization
  (in the detonation Lambda) and the artifact are all in **Forensic (360999005254)**;
  the durable tracking record where the sanitized view is verified is in the **Hub
  (641628980935)**. Deploy the detonation stack + submit from a **Forensic-authed** shell;
  deploy the Hub stack + verify the record from a **Hub-authed** shell. A banner comment
  does NOT change the account.
- **Run `aws sts get-caller-identity` BEFORE every block** and read `Account`. If it is
  not the account the block is for, switch tabs — do not proceed. (Recurring trap: a
  `ResourceNotFoundException` on the tracking table means you queried it from Forensic;
  it lives in the Hub.)
- **Feed commands ONE LINE AT A TIME.** Never paste a multi-line block (a multi-line paste
  lands in a single prompt/read and mis-parses).
- **`/tmp` + shell vars + `pip install`s are WIPED when CloudShell recycles.** Every block
  re-sets every variable AND reinstalls `awscurl` in the SAME block, right before use. If a
  session drops, re-run the block from its `get-caller-identity` line.
- **Placeholders like `<...>` are literal `<`/`>` shell redirections** and will error with
  `syntax error near unexpected token` — always substitute the REAL value before running.
- **Region us-east-1**, ambient creds (**no `--profile`**).
- **GitHub auth in CloudShell:** token-in-URL HTTPS form
  `git remote set-url origin https://<TOKEN>@github.com/warrenrutledge64/ZTIE-Issues.git`.

---

## STEP 0 (Forensic tab) — get the 2.5 code + confirm Forensic

```
aws sts get-caller-identity
```
**Run in: Forensic (360999005254), us-east-1, no --profile.** Expect
`"Account": "360999005254"`. Then check out the code (re-set the branch var in the same
block):

```
BRANCH=feature/story-2.5 ; cd ~/ZTIE-Issues && git fetch origin -q && git checkout "$BRANCH" && git reset --hard "origin/$BRANCH"
```
(If the 2.5 PR is already merged, set `BRANCH=main` instead.)

> ⚠️ **DO NOT SKIP THIS — and PROVE it landed (live lesson, 2026-09-11).** A `cdk deploy`
> reports `✅ UPDATE_COMPLETE` even when the box is on the WRONG branch — it just deploys
> the STALE stack definition (a silent deploy-gap). During the 2.5 live run STEP 0's
> checkout was skipped, the box was still on `main`, and STEP 2a "succeeded" while
> shipping the pre-2.5 Lambda (the new env vars were still absent). **Confirm the box is
> on the 2.5 code BEFORE any deploy** (one line each):
> ```
> cd ~/ZTIE-Issues && git rev-parse --abbrev-ref HEAD && git log --oneline -1
> ```
> Expect `feature/story-2.5` and the branch tip commit. Then prove the stack SOURCE
> actually carries the 2.5 change:
> ```
> grep -n "SANITIZED_TELEMETRY_CONTRACT_VERSION" ~/ZTIE-Issues/infra/lib/ztie-detonation-stack.ts || echo "NOT PRESENT — box is on pre-2.5 code; re-run the checkout above"
> ```
> Expect a line number (the env var is present). If it prints `NOT PRESENT`, the checkout
> did not take — re-run it before deploying.

---

## STEP 1 (Forensic tab) — gather the deploy context values

```
aws sts get-caller-identity
```
**Run in: Forensic (360999005254), us-east-1, no --profile.** Expect `360999005254`.
Collect the deploy context from the already-deployed stacks' outputs (re-set `REGION` in
the same block):

```
REGION=us-east-1 ; aws cloudformation describe-stacks --region "$REGION" --stack-name ZtieDetonationStack --query "Stacks[0].Outputs" --output table
```
Note `ArtifactBucketName`, `DetonationQueueUrl`, `DetonationQueueArn`,
`DetonationInstanceRoleArn`, and (for the intake submit) the intake API endpoint from
`ZtieIntakeStack`:

```
REGION=us-east-1 ; aws cloudformation describe-stacks --region "$REGION" --stack-name ZtieIntakeStack --query "Stacks[0].Outputs" --output table
```
Note `IntakeApiEndpoint` (the `POST /intake` URL). And the Hub ingest queue coordinates
(published by the Hub stack; read them in the Hub tab at STEP 5, or from the detonation
stack's env if surfaced) — you will re-deploy the detonation stack WITH these, so also
grab them now from the Hub tab if needed.

---

## STEP 2 — REDEPLOY the changed stacks FIRST (the DEPLOY-GAP step — do NOT skip)

> **Why (the #1 recurring live lesson, 2.6 + 2.4):** the live detonation Lambda that the
> 2.6 orchestration direct-invokes will still be running its OLD deployed code until you
> `cdk deploy`. Story 2.5 ADDS `sanitize.py` + the sanitized-telemetry crossing to that
> Lambda, and ADDS the 9th contract kind to the Hub validator. If you validate against the
> old code, **no `sanitized` record will cross at all** (detonation) or it will
> **fail-closed QUARANTINE** (Hub, because the Hub has no `sanitized-telemetry.contract.v1`
> bundled / no `SANITIZED_TELEMETRY_CONTRACT_VERSION` pin). Redeploy BOTH before submitting.

**(2a) Forensic tab — redeploy the detonation lane** (ships `sanitize.py` + the
`SANITIZED_TELEMETRY_CONTRACT_VERSION` + `SANITIZE_TOKEN_BUDGET` env). Substitute the STEP 1
values:

```
cd ~/ZTIE-Issues/infra && env -u NODE_OPTIONS npx cdk deploy ZtieDetonationStack --require-approval never -c artifactBucketName="<ArtifactBucketName>" -c detonationQueueUrl="<DetonationQueueUrl>" -c detonationQueueArn="<DetonationQueueArn>" -c hubIngestQueueUrl="<HUB_INGEST_QUEUE_URL>" -c hubIngestQueueArn="<HUB_INGEST_QUEUE_ARN>" -c detonationInstanceRoleArn="<DetonationInstanceRoleArn>"
```

> ✅ **VERIFY the redeploy actually took — never trust the `✅ UPDATE_COMPLETE` line alone
> (live lesson, 2026-09-11).** A green deploy of the wrong checkout ships stale code
> silently. Inspect the LIVE Lambda's env and confirm the 2.5 vars are now present (they
> were `null`/absent pre-2.5):
> ```
> FN=$(aws cloudformation describe-stacks --region us-east-1 --stack-name ZtieDetonationStack --query "Stacks[0].Outputs[?OutputKey=='DetonationFunctionName'].OutputValue" --output text); aws lambda get-function-configuration --region us-east-1 --function-name "$FN" --query "Environment.Variables.{SANITIZED_TELEMETRY_CONTRACT_VERSION:SANITIZED_TELEMETRY_CONTRACT_VERSION,SANITIZE_TOKEN_BUDGET:SANITIZE_TOKEN_BUDGET}" --output json
> ```
> Expect `SANITIZED_TELEMETRY_CONTRACT_VERSION="1.0"` + `SANITIZE_TOKEN_BUDGET="25000"`.
> If either is `null`, the box was on the wrong branch (see STEP 0) — re-checkout + redeploy
> before continuing. Do NOT proceed to 2b/submit until this shows the 2.5 vars.

**(2b) Hub tab — redeploy the Hub tracking stack** (ships the bundled
`sanitized-telemetry.contract.v1.json` + the `SANITIZED_TELEMETRY_CONTRACT_VERSION` pin so
the crossed `sanitized` record VALIDATES instead of quarantining). Confirm the Hub tab
first:

```
aws sts get-caller-identity
```
**Run in: Hub (641628980935), us-east-1, no --profile.** Expect `641628980935`. Then:

```
cd ~/ZTIE-Issues/infra && env -u NODE_OPTIONS npx cdk deploy ZtieHubTrackingStack -c forensicCollectorRoleArn="<CollectorRoleArn>"
```
(Use the SAME `-c` context values you used for the last successful Hub deploy; this stack
takes no new context for 2.5 — the change is the bundled contract + the env pin, both
carried by the redeploy.)

---

## STEP 3 (Forensic tab) — submit ONE artifact that WRITES A SECRET + touches files

```
aws sts get-caller-identity
```
**Run in: Forensic (360999005254).** Expect `360999005254`. The intake API is SigV4 /
IAM-authed and lives in Forensic — you MUST submit from a Forensic-authed principal (a Hub
principal gets 403; that is the zero-trust gate working). Install `awscurl`, build a JSON
envelope whose artifact both **writes a high-entropy secret** (to exercise the entropy
scrub) and **touches several files** (to exercise noise-suppression vs. artifact ops), and
POST it (URL LAST, `-d @file.json`):

```
pip install awscurl -q ; INTAKE_ENDPOINT=<IntakeApiEndpoint> ; printf '#!/bin/sh\numask 077\necho "AKIAIOSFODNN7EXAMPLEwJalrXUtnFEMIK7MDENGbPxRfiCYEXAMPLEKEY" > /tmp/ztie/loot.txt\nchmod 777 /tmp/ztie/loot.txt\nmv /tmp/ztie/loot.txt /tmp/ztie/exfil.dat\nfor i in $(seq 1 8); do echo data > /tmp/ztie/f$i.txt; done\n' > sample.sh ; B64=$(base64 -w0 sample.sh) ; printf '{"filename":"sample.sh","content_type":"application/x-sh","submitter":"story-2.5-live","content_base64":"%s"}' "$B64" > intake.json ; awscurl --service execute-api --region us-east-1 -X POST -H 'Content-Type: application/json' -d @intake.json "$INTAKE_ENDPOINT"
```
Record the returned `intake_id` (a UUIDv4). Set it for the following blocks:
`INTAKE_ID=<the returned intake_id>`.

> If you get `Request body must be valid JSON`, you sent a raw file body — the intake API
> wants the JSON envelope above, not `--data-binary @sample.sh`.

---

## STEP 4 (Forensic tab) — confirm the FULL raw trace still stays in Forensic (DoD 3)

Give the run ~2–3 minutes (launch + SSM-online + host-native strace run + teardown), then
confirm the full raw behavioral trace is in Forensic S3 (RD-009 — it must NOT cross):

```
REGION=us-east-1 ; ARTIFACT_BUCKET=<ArtifactBucketName> ; INTAKE_ID=<INTAKE_ID> ; aws s3 ls "s3://$ARTIFACT_BUCKET/traces/$INTAKE_ID/" --region "$REGION"
```
Expect `behavior-trace.txt`. (Optional: peek at the RAW trace to see the host noise +
secret that 2.5 is about to remove — it will still contain SSM/linker/locale lines and the
`AKIA...` blob, proving the raw material is faithful:)

```
REGION=us-east-1 ; ARTIFACT_BUCKET=<ArtifactBucketName> ; INTAKE_ID=<INTAKE_ID> ; aws s3 cp "s3://$ARTIFACT_BUCKET/traces/$INTAKE_ID/behavior-trace.txt" - --region "$REGION" | head -40
```

---

## STEP 5 (Hub tab) — confirm the verdict-free SANITIZED record (DoD 1 + 2 + 4)

```
aws sts get-caller-identity
```
**Run in: Hub (641628980935), us-east-1, no --profile.** Expect `641628980935`. Read the
sanitized view + pipeline accounting off the tracking record (substitute REAL values):

```
TABLE=<TrackingTableName> ; INTAKE_ID=<INTAKE_ID> ; aws dynamodb get-item --region us-east-1 --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$INTAKE_ID\"}}" --query "Item.{sanitize_status:sanitize_status.S,truncated:sanitize_truncated.BOOL,pipeline:sanitized.M.pipeline.M,lane:sanitized.M.lane.S}" --output json
```
**Expect (DoD 1 + 2):** `sanitize_status = sanitized`; `pipeline.stages = [entropy_scrub,
noise_suppress, truncate]`; `pipeline.noise_suppressed > 0` (host noise dropped);
`pipeline.entropy_redactions >= 1` (the `AKIA...` secret redacted); `pipeline.kept_events`
and `pipeline.emitted_events` present; `pipeline.estimated_tokens <= pipeline.token_budget`
(≤ 25000); `truncated` recorded (true/false — either is valid as long as it is present and
consistent with the token math); `lane = dynamic_detonation`.

Then confirm the artifact behavior is PRESERVED while the secret is GONE (DoD 1):

```
TABLE=<TrackingTableName> ; INTAKE_ID=<INTAKE_ID> ; aws dynamodb get-item --region us-east-1 --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$INTAKE_ID\"}}" --output json | grep -Eo 'exfil.dat|loot.txt|execve|write|chmod|rename|REDACTED|AKIAIOSFODNN7EXAMPLE'
```
**Expect:** the artifact's own paths/ops appear (`loot.txt` / `exfil.dat` / `write` /
`chmod` / `rename` / `execve`) AND `REDACTED` appears, but the secret `AKIAIOSFODNN7EXAMPLE`
does **NOT** appear (it was scrubbed).

Finally, prove it is EVIDENCE, not a verdict (DoD 3):

```
TABLE=<TrackingTableName> ; INTAKE_ID=<INTAKE_ID> ; aws dynamodb get-item --region us-east-1 --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$INTAKE_ID\"}}" --output json | grep -Ei 'verdict|safe|approved|forward|malicious|pass_fail|"clean"'
```
**Expect: NO output** (empty). No verdict-shaped key crossed.

Also confirm the crossing did NOT quarantine (fail-closed would put it in the quarantine
bucket instead of the record):

```
TABLE=<TrackingTableName> ; INTAKE_ID=<INTAKE_ID> ; aws dynamodb get-item --region us-east-1 --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$INTAKE_ID\"}}" --query "Item.sanitized_at.S" --output text
```
**Expect:** a Z-suffixed UTC timestamp (the `sanitized` record applied cleanly).

---

## Definition of Done — the 4-point PASS/FAIL gate

The stakeholder confirms live:
1. **Sanitized (STEP 5):** a real detonation's RAW trace is run through the pipeline; the
   SANITIZED output has host/runtime noise suppressed (`noise_suppressed > 0`) + the
   high-entropy secret scrubbed (`entropy_redactions >= 1`, `REDACTED` present, `AKIA...`
   absent), while the artifact's salient ops are preserved (`loot.txt`/`exfil.dat`/`write`/
   `chmod`/`rename`/`execve`).
2. **Bounded (STEP 5):** `estimated_tokens <= token_budget` (≤ 25000), with a recorded
   `truncated` flag (deterministic truncation).
3. **Evidence, not a verdict (STEP 4 + 5):** the verdict/safe/forward grep is EMPTY; the
   FULL raw trace still stays in Forensic (`traces/<intake_id>/behavior-trace.txt`);
   relative monotonic `offset_ms` preserved (never a wall clock).
4. **Crosses per RD-013 (STEP 5):** the `sanitized` record (own version pin) applied to the
   Hub tracking record (a `sanitized_at` timestamp is present; nothing quarantined).

- **On a 4/4 pass:** paste the outputs back; the executor records the dated Validation
  Result in RUNBOOK 2.5, flips 2.5 ✅ (paired commit), clears 2.5 from the Validation Debt
  Register, and keeps PLAN ↔ RUNBOOK aligned. The owner tags the restore point on the merge.
- **On any fail:** 2.5 stays 🟡 on the register; paste the failing output; the executor
  fixes + you re-validate (fix-then-validate-once — validate the code you will actually
  keep).

---

## Watch-items (carried from 2.4 live)

- The **ubuntu-22.04 golden AMI ships `strace`** (2.4 confirmed) but **NOT `curl`**, so a
  network syscall may not appear (honest `network` intent, nothing to sanitize there). The
  sample above deliberately exercises FILE ops + a secret write, which the AMI fully
  supports — do NOT add a `curl` probe expecting a network event.
- If `sanitize_status = no_trace`, capture itself did not produce a trace (check the 2.4
  `behavior_capture_status` on the same record: `tool_unavailable` = strace missing on the
  host; `not_run` = detonation never executed). That is a 2.4/AMI condition, not a 2.5
  bug — 2.5 correctly records the gap rather than faking a view.
- If the record has a `behavior` object but NO `sanitized` object, the **detonation stack
  redeploy (STEP 2a) did not take** — the live Lambda is still pre-2.5. Redeploy and
  re-submit.
- If `sanitized` is missing AND the quarantine bucket has a new object, the **Hub redeploy
  (STEP 2b) did not take** — the Hub lacks the 9th contract/pin and fail-closed
  quarantined. Redeploy the Hub stack and re-submit.
