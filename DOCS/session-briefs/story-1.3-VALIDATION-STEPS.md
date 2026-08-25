# Story 1.3 — Step-by-Step Live Validation (copy/paste)

> **What you are proving:** each classified artifact gets the correct **routing
> decision** on its Hub tracking record — IaC template and raw script each route to
> `[static_analysis, dynamic_detonation]`; an unknown blob routes to `[safe_reject]`
> (`routable=false`) — queryable by `intake_id`, with **no** verdict/forward field
> and `status` still `RECEIVED`.

## Ground rules (read once)

- **TWO CloudShell tabs.** **Tab F = Forensic (360999005254)** to submit; **Tab H =
  Hub (641628980935)** to verify. The intake API is IAM/SigV4 in Forensic; the
  tracking table is in the Hub.
- **Region us-east-1. Ambient creds only — never `--profile`.**
- **Run `aws sts get-caller-identity` at the top of each tab** and confirm the
  `Account` before running anything. A banner comment does NOT change the account.
- **Run ONE line at a time.** Do not paste a whole block at once.

---

## STEP 0 — Deploy (both tabs, in order: Hub first, then Forensic)

### 0a. Tab H (Hub) — confirm account, then deploy the Hub stack

```
aws sts get-caller-identity --query Account --output text     # must print 641628980935
```
```
cd ~/ZTIE-Issues/infra && git fetch origin && git checkout feature/story-1.3 && git pull --ff-only
```
```
npm ci
```
```
npx cdk deploy ZtieHubTrackingStack --require-approval never
```

Capture the Hub outputs (you need these next):

```
aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack \
  --query "Stacks[0].Outputs[?OutputKey=='IngestQueueUrl'||OutputKey=='IngestQueueArn'||OutputKey=='TrackingTableName'].[OutputKey,OutputValue]" \
  --output text
```

Note the three values — call them `QURL`, `QARN`, `TABLE`.

### 0b. Tab F (Forensic) — confirm account, then deploy the Forensic stack

```
aws sts get-caller-identity --query Account --output text     # must print 360999005254
```
```
cd ~/ZTIE-Issues/infra && git fetch origin && git checkout feature/story-1.3 && git pull --ff-only
```
```
npm ci
```

Deploy, passing the Hub queue coordinates from 0a (paste the real `QURL`/`QARN`):

```
npx cdk deploy ZtieIntakeStack --require-approval never \
  -c hubIngestQueueUrl="<PASTE QURL>" \
  -c hubIngestQueueArn="<PASTE QARN>"
```

Capture the intake endpoint:

```
aws cloudformation describe-stacks --stack-name ZtieIntakeStack \
  --query "Stacks[0].Outputs[?OutputKey=='IntakeEndpoint'].OutputValue" --output text
```

Note it — call it `ENDPOINT`.

> If `awscurl` is not installed in Tab F: `pip install --user awscurl` (one line).

---

## STEP 1 — Submit three artifacts (Tab F, Forensic)

Re-confirm the account first:
```
aws sts get-caller-identity --query Account --output text     # 360999005254
```

Set the endpoint (paste the real value from 0b):
```
ENDPOINT="<PASTE ENDPOINT>"
```

### 1a. IaC template (expect artifact_class=iac_template → lanes [static_analysis, dynamic_detonation])

Build the request JSON (the API takes base64 of the artifact body in `content_base64`):
```
printf 'AWSTemplateFormatVersion: "2010-09-09"\nResources:\n  B:\n    Type: AWS::S3::Bucket\n' > stack.yaml
```
```
python3 -c "import base64,json;print(json.dumps({'filename':'stack.yaml','content_type':'text/yaml','content_base64':base64.b64encode(open('stack.yaml','rb').read()).decode()}))" > req_iac.json
```
```
awscurl --service execute-api --region us-east-1 -X POST -H 'Content-Type: application/json' -d @req_iac.json "$ENDPOINT"
```
Copy the `intake_id` from the 201 response → call it `ID_IAC`.

### 1b. Raw script (expect artifact_class=raw_script → lanes [static_analysis, dynamic_detonation])

```
printf '#!/usr/bin/env bash\nset -e\necho "deploying"\n' > deploy.sh
```
```
python3 -c "import base64,json;print(json.dumps({'filename':'deploy.sh','content_type':'text/x-shellscript','content_base64':base64.b64encode(open('deploy.sh','rb').read()).decode()}))" > req_script.json
```
```
awscurl --service execute-api --region us-east-1 -X POST -H 'Content-Type: application/json' -d @req_script.json "$ENDPOINT"
```
Copy the `intake_id` → `ID_SCRIPT`.

### 1c. Unknown blob (expect artifact_class=other_unknown → lanes [safe_reject], routable=false)

```
printf 'These are just some meeting notes. No code here at all.\n' > notes.txt
```
```
python3 -c "import base64,json;print(json.dumps({'filename':'notes.txt','content_type':'text/plain','content_base64':base64.b64encode(open('notes.txt','rb').read()).decode()}))" > req_unknown.json
```
```
awscurl --service execute-api --region us-east-1 -X POST -H 'Content-Type: application/json' -d @req_unknown.json "$ENDPOINT"
```
Copy the `intake_id` → `ID_UNKNOWN`.

> Each POST should return **201** with an `intake_id`, `status":"RECEIVED"`, and a
> `sha256`. A **403** here means you are in the wrong account (submit from Forensic).

---

## STEP 2 — Verify the routing decision (Tab H, Hub)

Re-confirm the account and set the table name (from 0a):
```
aws sts get-caller-identity --query Account --output text     # 641628980935
```
```
TABLE="<PASTE TABLE>"
```

Give the pipeline a few seconds (S3 event → preprocessor classify+route → SQS → Hub
gate). Then read each record (paste the real intake_id for each):

### 2a. IaC record
```
aws dynamodb get-item --table-name "$TABLE" --key '{"intake_id":{"S":"<ID_IAC>"}}' \
  --query "Item.{class:artifact_class.S, lanes:routing_lanes.L[*].S, routable:routing.M.routable.BOOL, basis:routing.M.basis.S, status:status.S}" --output json
```
Expect: `class=iac_template`, `lanes=["static_analysis","dynamic_detonation"]`,
`routable=true`, `basis=class_route`, `status=RECEIVED`.

### 2b. Raw-script record
```
aws dynamodb get-item --table-name "$TABLE" --key '{"intake_id":{"S":"<ID_SCRIPT>"}}' \
  --query "Item.{class:artifact_class.S, lanes:routing_lanes.L[*].S, routable:routing.M.routable.BOOL, basis:routing.M.basis.S, status:status.S}" --output json
```
Expect: `class=raw_script`, `lanes=["static_analysis","dynamic_detonation"]`,
`routable=true`, `basis=class_route`, `status=RECEIVED`.

### 2c. Unknown record
```
aws dynamodb get-item --table-name "$TABLE" --key '{"intake_id":{"S":"<ID_UNKNOWN>"}}' \
  --query "Item.{class:artifact_class.S, lanes:routing_lanes.L[*].S, routable:routing.M.routable.BOOL, basis:routing.M.basis.S, status:status.S}" --output json
```
Expect: `class=other_unknown`, `lanes=["safe_reject"]`, `routable=false`,
`basis=safe_reject_fallback`, `status=RECEIVED`.

### 2d. Confirm NO verdict/forward field crossed (all three)
```
aws dynamodb get-item --table-name "$TABLE" --key '{"intake_id":{"S":"<ID_UNKNOWN>"}}' \
  --query "Item.{verdict:verdict, forward:forward, approved:approved}" --output json
```
Expect all three to be `null` (routing never writes a verdict/forward/approved).

---

## PASS / FAIL

- **PASS** = 2a/2b/2c all match the expected `lanes` + `routable` + `basis`, `status`
  is `RECEIVED` on all three, and 2d shows no verdict/forward/approved. Tell me and I
  record the dated Validation Result in `RUNBOOK.md` and flip **1.3 ✅** (paired
  status commit).
- **FAIL** = anything off. Paste the exact `get-item` output here; 1.3 stays 🟡 and I
  fix + re-validate.

### If a record has no `routing` yet
The routing update is applied only after the intake record exists (integrity-bound).
Wait ~10–20s and re-run the `get-item`. If it never appears, check the preprocessor
Lambda logs (Tab F) and the Hub validator Lambda logs / the quarantine bucket +
ingest DLQ (Tab H) — paste what you find.
