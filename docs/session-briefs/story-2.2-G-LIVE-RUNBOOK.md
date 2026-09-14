# Story 2.2G — LIVE gitleaks-integration validation runbook (stakeholder, two CloudShells)

> **This is the ONLY live part of 2.2G, and only YOU can do it** (the executor has no
> AWS creds). You REBUILD the static-scan container image (now embedding the compiled
> `gitleaks` binary), REDEPLOY the Hub ingest gate FIRST then the static lane, submit
> ONE artifact carrying a PLANTED secret, and confirm a `gitleaks` finding is normalized
> into `static-findings.contract.v1` and reflected in the bounded Hub summary. The
> executor **records your returned output verbatim** into RUNBOOK 2.2G detail. **Nothing
> is recorded on inference** — paste back exactly what the commands print. On a pass the
> executor flips 2.2G ✅ (paired commit) and clears it from the Validation Debt Register.

## Ground rules (these have bitten us every session)

- **TWO accounts → TWO CloudShell tabs.** The static-scan lane, the artifact, and the
  full findings document are all in **Forensic (360999005254)**; the durable tracking
  record + the Hub ingest gate that validates the crossed summary are in the **Hub
  (641628980935)**. Rebuild + submit from a **Forensic-authed** shell; redeploy the Hub
  ingest gate + verify the summary from a **Hub-authed** shell. A banner comment does
  NOT change the account.
- **Run `aws sts get-caller-identity` BEFORE every block** and read `Account`. If it is
  not the account the block is for, switch tabs — do not proceed. (Recurring trap: a
  `ResourceNotFoundException` on the tracking table means you queried it from Forensic;
  it lives in the Hub.)
- **Feed commands ONE LINE AT A TIME.** Never paste a multi-line block.
- **`/tmp` + shell vars are WIPED when CloudShell recycles.** Every block re-sets every
  variable it uses, in the SAME block, right before using it. If a session drops, re-run
  the block from its `get-caller-identity` line.
- **Region us-east-1**, ambient creds (**no `--profile`**).
- **GitHub auth in CloudShell:** token-in-URL HTTPS form
  `git remote set-url origin https://<TOKEN>@github.com/warrenrutledge64/ZTIE-Issues.git`.

> ### ⚠️ THE ONE ORDER THAT MATTERS THIS STORY (Decision B — deploy-gap class)
> Story 2.2G bumps the static-scan **summary contract to v1.2** (the `gitleaks` tool
> added to the per-tool status enum). The Hub ingest gate pins `SUMMARY_CONTRACT_VERSION`
> and rejects any other version **fail-closed (quarantines)**. So you MUST:
>
> **REDEPLOY `ZtieHubTrackingStack` (Hub) FIRST → THEN rebuild/redeploy `ZtieStaticScanStack` (Forensic).**
>
> If you redeploy the static lane first, the very first gitleaks-bearing summary crosses
> as v1.2 while the live Hub gate still expects v1.1 → the summary QUARANTINES and never
> attaches. (This is the exact sibling of the 2.6 collected-kind + the 4.6 handoff-kind
> deploy-gaps.) After the Hub redeploy, VERIFY the live env carries `SUMMARY_CONTRACT_VERSION=1.2` before touching the lane.

---

## STEP 0 (Forensic tab) — get the 2.2G code + confirm Forensic

```
aws sts get-caller-identity
```
**Run in: Forensic (360999005254), us-east-1, no --profile.** Expect
`"Account": "360999005254"`. Then check out the code (re-set the branch var in the same
block):

```
BRANCH=feature/story-2.2G ; cd ~/ZTIE-Issues && git fetch origin -q && git checkout "$BRANCH" && git reset --hard "origin/$BRANCH"
```
(If the 2.2G PR is already merged, set `BRANCH=main` instead.) Confirm you are on the
2.2G code and the gitleaks marker is present in the source you are about to deploy
(deploy-gap guard — never trust a green deploy of a stale checkout):

```
cd ~/ZTIE-Issues && git log --oneline -1 && grep -n "run_gitleaks" lambdas/static_scan/scanners.py && grep -n "GITLEAKS_VERSION" lambdas/static_scan/Dockerfile
```
**PASTE the branch tip SHA + the two grep hits back.**

---

## STEP 1 (Forensic tab) — gather the deploy context values

```
aws sts get-caller-identity
```
**Run in: Forensic (360999005254), us-east-1, no --profile.** Expect `360999005254`.
Collect the context values the static-scan stack needs from the already-deployed stacks'
outputs (re-set `REGION` in the same block, one line at a time):

```
REGION=us-east-1 ; aws cloudformation describe-stacks --region "$REGION" --stack-name ZtieStaticScanStack --query "Stacks[0].Outputs" --output table
```
Note `StaticScanFunctionName`.

```
REGION=us-east-1 ; aws cloudformation describe-stacks --region "$REGION" --stack-name ZtieIntakeStack --query "Stacks[0].Outputs" --output table
```
Note `ArtifactBucketName`, `StaticScanQueueUrl`, `StaticScanQueueArn`, and the intake API
endpoint (pin it robustly):

```
REGION=us-east-1 ; aws cloudformation describe-stacks --region "$REGION" --stack-name ZtieIntakeStack --query "Stacks[0].Outputs[?contains(OutputValue,'/intake')].OutputValue | [0]" --output text
```

Hub ingest queue coordinates (from `ZtieHubTrackingStack` outputs `IngestQueueUrl` /
`IngestQueueArn` — the SAME values the lane stacks already use): `hubIngestQueueUrl`,
`hubIngestQueueArn`.

---

## STEP 2 (Hub tab) — REDEPLOY THE HUB INGEST GATE FIRST (accept summary v1.2)

> **DO THIS BEFORE THE STATIC LANE.** See the boxed order rule above.

```
aws sts get-caller-identity
```
**Run in: Hub (641628980935), us-east-1, no --profile.** Expect `"Account": "641628980935"`.
Install infra deps (re-set the dir in the same block):

```
cd ~/ZTIE-Issues/infra && env -u NODE_OPTIONS npm install
```
> **Use `npm install`, NOT `npm ci`** — this repo has no committed `package-lock.json`
> (2.0E live lesson).

Redeploy the Hub tracking/ingest stack. It ships the bundled **v1.2**
`static-scan-summary.contract.v1.json` (now listing the `gitleaks` tool) AND the
`SUMMARY_CONTRACT_VERSION="1.2"` env pin the handler enforces:

```
cd ~/ZTIE-Issues/infra && env -u NODE_OPTIONS npx cdk deploy ZtieHubTrackingStack
```
**PASTE the deploy tail back.** Then VERIFY the live ingest Lambda actually carries the
v1.2 pin (deploy-gap guard — never trust the green `UPDATE_COMPLETE` line). Find the
ingest validator function and dump its env:

```
REGION=us-east-1 ; aws lambda list-functions --region "$REGION" --query "Functions[?contains(FunctionName,'IngestValidator')].FunctionName" --output text
```
```
INGEST_FN=<IngestValidator function name from above> ; aws lambda get-function-configuration --region us-east-1 --function-name "$INGEST_FN" --query "Environment.Variables.SUMMARY_CONTRACT_VERSION" --output text
```
**PASTE this back.** Expect **`1.2`**. If it prints `1.1` or `None`, the redeploy did not
take (wrong checkout / wrong stack) — STOP and fix before touching the lane, or the
summary will quarantine.

---

## STEP 3 (Forensic tab) — REBUILD + REDEPLOY THE STATIC LANE (embeds gitleaks)

```
aws sts get-caller-identity
```
**Run in: Forensic (360999005254), us-east-1, no --profile.** Expect `360999005254`.
The static lane is a **container-image** Lambda; the redeploy REBUILDS the image, which
downloads + installs the pinned `gitleaks` binary (`ARG GITLEAKS_VERSION=8.30.1`) and
runs the in-Dockerfile sanity `gitleaks version`. Re-set every context var in the SAME
block, one line at a time:

```
cd ~/ZTIE-Issues/infra && env -u NODE_OPTIONS npm install
```
```
ARTIFACT_BUCKET=<ArtifactBucketName> ; SS_Q_URL=<StaticScanQueueUrl> ; SS_Q_ARN=<StaticScanQueueArn> ; HUB_Q_URL=<hubIngestQueueUrl> ; HUB_Q_ARN=<hubIngestQueueArn> ; cd ~/ZTIE-Issues/infra && env -u NODE_OPTIONS npx cdk deploy ZtieStaticScanStack -c artifactBucketName="$ARTIFACT_BUCKET" -c staticScanQueueUrl="$SS_Q_URL" -c staticScanQueueArn="$SS_Q_ARN" -c hubIngestQueueUrl="$HUB_Q_URL" -c hubIngestQueueArn="$HUB_Q_ARN"
```
**PASTE the deploy tail back.** A PASS here already proves **DoD item 1** (the gitleaks
binary downloaded + is executable in the image): the Docker build step
`RUN cfn-lint --version && checkov --version && bandit --version && gitleaks version`
FAILS the build if gitleaks is not installed/executable, so a successful image build =
gitleaks present. Then confirm the live lane function carries the v1.2 emit pin:

```
STATIC_FN=<StaticScanFunctionName> ; aws lambda get-function-configuration --region us-east-1 --function-name "$STATIC_FN" --query "Environment.Variables.SUMMARY_CONTRACT_VERSION" --output text
```
**PASTE this back.** Expect **`1.2`**.

---

## STEP 4 (Forensic tab) — submit ONE artifact carrying a PLANTED secret (DoD 2)

```
aws sts get-caller-identity
```
**Run in: Forensic (360999005254), us-east-1, no --profile.** Expect `360999005254`.
The intake API wants a JSON body `{filename, content_base64, content_type, submitter}`
(NOT a raw file body — a raw body gives "Request body must be valid JSON"; 2.6 lesson).
Build a small `raw_script` artifact that plants a well-known **test** AWS key (the
canonical AWS-docs EXAMPLE key — not a live credential) so gitleaks fires deterministically.
Re-set the endpoint var in the same block, one line at a time:

```
printf 'AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE\nAWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY\n' > planted.sh
```
```
B64=$(base64 -w0 planted.sh) ; printf '{"filename":"planted.sh","content_base64":"%s","content_type":"text/x-shellscript","submitter":"stakeholder-2.2G"}' "$B64" > intake.json
```
```
INTAKE_ENDPOINT=<INTAKE_ENDPOINT_FROM_STEP_1> ; awscurl --service execute-api --region us-east-1 -X POST -H 'Content-Type: application/json' -d @intake.json "$INTAKE_ENDPOINT"
```
Record the returned `intake_id`. **PASTE it back.**

> (If `awscurl` is missing: `pip install awscurl`. Pass the URL AFTER the flags with
> `-d @intake.json`.)

---

## STEP 5 (Forensic tab) — confirm gitleaks ran + the full findings doc (DoD 2 + 3)

```
aws sts get-caller-identity
```
**Run in: Forensic (360999005254), us-east-1, no --profile.** Expect `360999005254`.
Tail the static-scan Lambda for this `intake_id` and confirm a `tool=gitleaks` line with
`status=ok` and `findings>=1` (re-set both vars in the same block):

```
STATIC_FN=<StaticScanFunctionName> ; INTAKE_ID=<INTAKE_ID> ; aws logs filter-log-events --region us-east-1 --log-group-name "/aws/lambda/$STATIC_FN" --filter-pattern "\"$INTAKE_ID\"" --query "events[].message" --output text
```
**PASTE the `tool=gitleaks ...` line back.** Expect `tool=gitleaks status=ok findings=1`
(the planted key) among the per-tool lines.

Now read the FULL findings document that STAYS IN FORENSIC (RD-009) and confirm the
gitleaks finding is normalized into the contract shape AND the raw secret was REDACTED
(never persisted). Re-set the bucket + intake vars in the same block:

```
ARTIFACT_BUCKET=<ArtifactBucketName> ; INTAKE_ID=<INTAKE_ID> ; aws s3 cp "s3://$ARTIFACT_BUCKET/findings/$INTAKE_ID/static-findings.json" - | python3 -c "import sys,json;d=json.load(sys.stdin);print('contract_version',d['contract_version']);print('tools',[t['tool'] for t in d['tools']]);print([f for f in d['findings'] if f['tool']=='gitleaks'])"
```
**PASTE this back.** A PASS shows: `contract_version 1.2`; `gitleaks` in the `tools`
list; at least one finding with `tool=gitleaks`, `check_family=signature`,
`severity=high`, a `location`, and a `message` that says "potential secret detected
(...redacted)" — and **the raw key `wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY` MUST NOT
appear anywhere** in the output (secret redaction, RD-009 defense-in-depth):

```
ARTIFACT_BUCKET=<ArtifactBucketName> ; INTAKE_ID=<INTAKE_ID> ; aws s3 cp "s3://$ARTIFACT_BUCKET/findings/$INTAKE_ID/static-findings.json" - | grep -F "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" && echo "LEAK-FAIL" || echo "REDACTED-OK"
```
**PASTE this back.** Expect **`REDACTED-OK`** (grep finds nothing).

---

## STEP 6 (Hub tab) — confirm the gitleaks finding reflected in the bounded summary (DoD 3)

Switch to the **Hub** tab and confirm identity FIRST:
```
aws sts get-caller-identity
```
**Run in: Hub (641628980935), us-east-1, no --profile.** Expect `"Account": "641628980935"`.
Get the tracking table name (re-set region in the same block):
```
REGION=us-east-1 ; aws cloudformation describe-stacks --region "$REGION" --stack-name ZtieHubTrackingStack --query "Stacks[0].Outputs[?OutputKey=='TrackingTableName'].OutputValue" --output text
```

Read the crossed summary for your `intake_id` (re-set both vars in the same block):
```
TABLE=<TrackingTableName> ; INTAKE_ID=<INTAKE_ID> ; aws dynamodb get-item --region us-east-1 --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$INTAKE_ID\"}}" --query "Item.{tools:static_scan.M.tools,highest:static_scan_highest_severity,compliance:static_scan_compliance,scanned_at:static_scanned_at}" --output json
```
**PASTE this back.** A PASS shows the `static_scan` summary attached (NOT quarantined),
with a per-tool status entry `tool=gitleaks status=ok`, `highest_severity=high`, and a
bounded `compliance` roll-up whose `nist_800_53` map includes `IA-5` / `SC-28` (the
secret-control mapping for the gitleaks finding). If `static_scan` is ABSENT, the summary
quarantined — almost always the Hub-gate order rule (STEP 2) was skipped or the ingest
env still shows `1.1`; re-check STEP 2, then re-submit.

**DoD item 3 (evidence, never a verdict) — NO verdict/safe/approved/forward field.**
```
TABLE=<TrackingTableName> ; INTAKE_ID=<INTAKE_ID> ; aws dynamodb get-item --region us-east-1 --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$INTAKE_ID\"}}" --output json | grep -Ei 'verdict|"safe"|approved|forward|pass_fail' && echo "VERDICT-FAIL" || echo "NO-VERDICT-OK"
```
**PASTE this back.** Expect **`NO-VERDICT-OK`**. (The full finding text + mapping
rationale stay in Forensic; only bounded counts + per-tool status + the control-count
roll-up cross.)

---

## OPTIONAL — DoD item 4 (caveat enforcement: a gitleaks tool ERROR is recorded, not fatal)

This is proven offline (the shared `_result_from_output` records a `>1` exit / timeout /
spawn-failure as `status=error` with a bounded `error_reason`, and the lane loop
continues) and does not require its own live submit. If you want a live demonstration,
submit any artifact and confirm that even if `gitleaks` had errored, the OTHER tools'
findings + the summary still crossed (the lane's per-tool `tool=gitleaks status=...` line
appears regardless, and a `status=error` never produces a `batchItemFailures` for the
job). No action needed for a normal pass.

---

## What a PASS looks like (the DoD gate the stakeholder confirms live)

1. **gitleaks installed + executable in the image.** STEP 3's `ZtieStaticScanStack` image
   build SUCCEEDS — the Dockerfile sanity line runs `gitleaks version`, so a green build =
   gitleaks present and runnable.
2. **A planted secret triggers a gitleaks finding.** STEP 5 shows a `tool=gitleaks
   status=ok findings>=1` log line and a normalized `tool=gitleaks` finding in the
   Forensic findings document (v1.2), with the raw secret REDACTED (`REDACTED-OK`).
3. **Normalized into the contract + reflected in the bounded Hub summary.** STEP 6 shows
   the `static_scan` summary ATTACHED (not quarantined) with a `gitleaks` per-tool entry
   + the `IA-5`/`SC-28` compliance roll-up, and the no-verdict grep returns
   `NO-VERDICT-OK`.
4. **Caveat enforced.** A gitleaks error (exit `>1` / timeout) is recorded as a per-tool
   `error` and never crashes the lane (offline-proven; optionally demonstrated above).

**Goes ✅ ONLY when you confirm a live pass AND the executor RECORDS it in RUNBOOK.md.**
No recorded pass → 2.2G stays 🟡 (it remains the open Validation Debt Register entry,
keeping the advancement gate armed).

---

## RECORD (executor)

Paste back, per DoD item, the exact command output. The executor records a dated
Validation Result in RUNBOOK 2.2G + STORY_DETAIL 2.2G:
- **PASS:** flip 2.2G ✅ (paired commit), keep PLAN ↔ RUNBOOK ↔ STORY_DETAIL aligned,
  clear 2.2G from the Validation Debt Register. The executor **records your returned
  output verbatim — it does not simulate a run.**
- **FAIL (any DoD item):** 2.2G stays 🟡; the executor fixes + you re-validate.

---

## Carry-forward watch-items for THIS run (live-relevant)

- **Hub-gate-before-lane order is mandatory** (Decision B): the summary contract went to
  v1.2, so redeploy `ZtieHubTrackingStack` and confirm the live ingest env
  `SUMMARY_CONTRACT_VERSION=1.2` BEFORE the static lane emits v1.2, or the summary
  quarantines fail-closed.
- **gitleaks command shape** (if you ever invoke by hand): `gitleaks dir <path>
  --report-format json --report-path /dev/stdout --no-banner --exit-code 1`. `detect` is
  DEPRECATED in gitleaks v8.19+ — the lane uses `dir`. Exit `0`=no leaks, `1`=leaks
  found (JSON on stdout — still a successful scan), `>1`=tool error.
- **gitleaks assigns no severity** — the lane normalizes every gitleaks finding to
  `high` and reuses the `signature` check_family (Decision A).
- **Secrets are redacted** in the normalized finding (the raw `Secret`/`Match` is never
  persisted) — the `REDACTED-OK` grep is a hard gate.
- **The 2.2 embedded SECRET regex rules were REMOVED** (superseded by gitleaks); the
  signature engine now only fires DANGEROUS + MALWARE (reverse-shell/EICAR/miner/
  curl|sh/eval). A planted secret no longer produces a `ZTIE-SIG-SECRET-*` finding —
  gitleaks is the sole secret source of truth.
