# Story 4.6 — LIVE ACCEPT-push (PDE handoff) validation runbook (stakeholder) — RD-047

> **This is the ONLY live part of 4.6, and only YOU can do it** (the executor has no AWS
> creds). This is the FIRST story that spans **THREE accounts** — Forensic (the pusher +
> the raw artifact), **Pipeline-Sandbox (586917955591)** (the landing bucket — the first
> ZTIE resource in this account; confirm you have creds), and the Hub (the human decision +
> the outcome). You deploy the Sandbox landing stack, then the Forensic pusher stack, record
> a human `accepted` on the Hub tracking item, then **INVOKE the pusher by `intake_id`** and
> confirm it **hash-verifies + pushes the artifact to the Sandbox landing bucket** and it
> LANDS — AND that a **no-accept / hash-mismatch invoke is REFUSED (nothing leaves
> Forensic)** — AND that only a **bounded, verdict-free outcome** crosses to the Hub. The
> executor records your returned output verbatim. **Nothing is recorded on inference.** On a
> pass the executor flips **4.6 → ✅** (paired commit), clears it from the Validation Debt
> Register, and 4.7 becomes the next first-OPEN pipe story.

## What 4.6 is (RD-047 — so the check is meaningful)

4.6 is the **Phase-4 ACCEPT ENFORCEMENT ACTION** — the push MECHANISM. On a **recorded
human ACCEPT** (`human_decision == "accepted"` on the Hub tracking item — **NEVER** the
advisory `recommended_verdict`, RD-040), the Forensic-side `pde_handoff` Lambda:
1. reads the Hub tracking item **cross-account** (`dynamodb:GetItem`) — the decision + the
   authoritative `sha256`,
2. recomputes the Forensic artifact's sha256 and **verifies it** against the record (SI-7),
3. evaluates the **fail-closed gate** — push **iff** `accepted` **AND** the hash verified,
4. **only if the gate says push**, `PutObject`s the artifact **cross-account** to the
   Pipeline-Sandbox landing bucket (586917955591) under the scoped prefix (SSE-S3), and
5. **ALWAYS** crosses a bounded, verdict-free `handoff.contract.v1` **outcome** to the Hub
   (`pushed` / `refused_not_accepted` / `refused_hash_mismatch`).

**FAIL-CLOSED:** absent a genuine accept, or on any hash mismatch, **NOTHING leaves
Forensic**. **The artifact goes Forensic → Sandbox DIRECTLY — it NEVER transits the Hub**
(only the bounded outcome crosses, RD-013). **ZTIE never re-executes the artifact.** The
push mechanism is decoupled from the human accept/reject UI + the auto decision-event
trigger (Story 4.4). **ServiceNow is OUT OF SCOPE.**

## Ground rules (these have bitten us every session)

- **THREE accounts, so up to THREE CloudShell tabs.** Forensic (360999005254) = the pusher
  Lambda + the raw artifact; **Pipeline-Sandbox (586917955591)** = the landing bucket (NEW
  — confirm you have creds for this account); Hub (641628980935) = the tracking table (the
  human decision + the outcome).
- **Run `aws sts get-caller-identity` BEFORE every block** and read `Account`. A banner
  comment does NOT change the account — a wrong-account error is the classic time-sink here.
- **Feed commands ONE LINE AT A TIME.** Never paste a multi-line block.
- **`/tmp` + shell vars are WIPED when CloudShell recycles.** Re-set every variable in the
  SAME block right before using it.
- **Region us-east-1**, ambient creds (**no `--profile`**).
- **Deploy-gap guard:** `cdk deploy` prints `✅ UPDATE_COMPLETE` even on the WRONG branch /
  wrong account. BEFORE deploying prove the checkout carries the RD-047 code; AFTER
  deploying inspect the LIVE resource (the pusher role's policy, the Sandbox bucket policy).
- **The `pde_handoff` Lambda uses a CUSTOM log group** (OD-003), so
  `aws logs tail /aws/lambda/<fn>` may fail `ResourceNotFoundException` — tail the real
  group from `LoggingConfig.LogGroup` if you need logs.
- **Reuse a fully-processed intake** whose raw artifact still exists in the Forensic artifact
  bucket (e.g. a 4.2/4.5 live-run intake such as `891cb78f-…`), so the record carries a real
  `sha256` and the artifact is present to hash + push.

---

## STEP 0 — confirm the three accounts + the intake to hand off

Open three tabs (Forensic / Pipeline-Sandbox / Hub) and in EACH:
```
aws sts get-caller-identity
```
Expect `360999005254` / `586917955591` / `641628980935` respectively. **If the
Pipeline-Sandbox tab fails (no creds), STOP** — this story cannot be validated without
Sandbox access; get creds for 586917955591 first.

Pick a fully-processed intake to hand off (Hub tab), and confirm its record + `sha256`:
```
TABLE=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='TrackingTableName'].OutputValue" --output text) ; IID=<paste-a-fully-processed-intake_id> ; aws dynamodb get-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --region us-east-1 --query "{sha256:Item.sha256.S, filename:Item.filename.S, human_decision:Item.human_decision.S}"
```
Expect a `sha256` + `filename`; `human_decision` will be `null` (not set yet — that is
correct; we set it in STEP 4). Note the `filename` — the artifact lives in the Forensic
artifact bucket at `intake/<intake_id>/<filename>`.

---

## STEP 1 — get the 4.6 code + prove the checkout carries it (each deploy tab)

In the tab you will deploy from (`cd ~/ZTIE-Issues`):
```
cd ~/ZTIE-Issues && git fetch origin -q && git checkout feature/story-4.6 && git reset --hard origin/feature/story-4.6
```
(If the 4.6 PR is already merged, use `git checkout main && git reset --hard origin/main`.)
```
git rev-parse --abbrev-ref HEAD && git log --oneline -1
```
```
ls lambdas/pde_handoff && grep -n "ZtieSandboxLandingStack\|ZtiePdeHandoffStack" infra/bin/ztie-infra.ts | head
```
Expect the `lambdas/pde_handoff/` files (`handler.py` / `handoff.py` / `awsio.py` /
`handoff.contract.v1.json`) + both new stacks wired in the bin. Confirm the pusher is PURE
(NO Bedrock) + push is fail-closed:
```
grep -n "human_decision\|evaluate_gate\|bedrock\|PutObject\|GetItem" infra/lib/ztie-pde-handoff-stack.ts | head
```
Expect `dynamodb:GetItem`, `s3:GetObject`, `s3:PutObject` and NO `bedrock`. If the stacks
are ABSENT, the checkout is stale — re-run the checkout.

---

## STEP 2 (Pipeline-Sandbox tab) — deploy the landing stack FIRST

> Deploy the Sandbox landing bucket + its cross-account bucket policy FIRST so its bucket
> name exists to pass to the Forensic pusher. (On the FIRST deploy the pusher role ARN does
> not exist yet, so the bucket policy falls back to the Forensic account root — still
> one-directional + one-prefix. In STEP 3b you re-deploy it with the exact pusher role ARN
> for tightest least-privilege.)

```
aws sts get-caller-identity
```
**Run in: Pipeline-Sandbox (586917955591).** Expect `586917955591`.
```
cd ~/ZTIE-Issues/infra && npm ci
```
```
cd ~/ZTIE-Issues/infra && npx cdk deploy ZtieSandboxLandingStack --require-approval never
```
Expect `✅ ZtieSandboxLandingStack` with outputs `SandboxLandingBucketName`,
`SandboxLandingPrefix` (= `accepted/`), `SandboxLandingAccountId` (= `586917955591`).
Capture the bucket name:
```
SBKT=$(aws cloudformation describe-stacks --stack-name ZtieSandboxLandingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='SandboxLandingBucketName'].OutputValue" --output text) ; echo "$SBKT"
```

---

## STEP 3 (Forensic tab) — deploy the pusher, then re-tighten the Sandbox grant

### 3a — deploy the Forensic pusher stack

Gather the coordinates it needs (Hub outputs — read them from a Hub tab, they are Hub
resources; then paste the values in the Forensic deploy). From the **Hub** tab:
```
aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='TrackingTableName'||OutputKey=='IngestQueueUrl'||OutputKey=='IngestQueueArn'].{K:OutputKey,V:OutputValue}" --output table
```
From the **Forensic** tab, get the artifact bucket:
```
aws cloudformation describe-stacks --stack-name ZtieIntakeStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='ArtifactBucketName'].OutputValue" --output text
```
Now deploy (Forensic tab), passing the artifact bucket, the Hub table name + ingest queue,
and the Sandbox bucket name from STEP 2 (`hubTrackingTableArn` is derived automatically from
the table name + the Hub account + region):
```
aws sts get-caller-identity
```
**Run in: Forensic (360999005254).** Expect `360999005254`.
```
cd ~/ZTIE-Issues/infra && npx cdk deploy ZtiePdeHandoffStack --require-approval never -c artifactBucketName=<ArtifactBucketName> -c hubTrackingTableName=<TrackingTableName> -c hubIngestQueueUrl=<IngestQueueUrl> -c hubIngestQueueArn=<IngestQueueArn> -c sandboxLandingBucket=<SandboxLandingBucketName>
```
Expect `✅ ZtiePdeHandoffStack` with outputs `PdeHandoffFunctionName`, `PdeHandoffRoleArn`.
Capture the pusher role ARN + function name:
```
PFN=$(aws cloudformation describe-stacks --stack-name ZtiePdeHandoffStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='PdeHandoffFunctionName'].OutputValue" --output text) ; PROLE=$(aws cloudformation describe-stacks --stack-name ZtiePdeHandoffStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='PdeHandoffRoleArn'].OutputValue" --output text) ; echo "$PFN" ; echo "$PROLE"
```

### 3b (Pipeline-Sandbox tab) — re-deploy the landing stack scoped to the exact pusher role

```
aws sts get-caller-identity
```
Expect `586917955591`.
```
cd ~/ZTIE-Issues/infra && npx cdk deploy ZtieSandboxLandingStack --require-approval never -c forensicPusherRoleArn=<PdeHandoffRoleArn>
```
Expect `✅`. Now the Sandbox bucket policy grants **exactly** the pusher role `s3:PutObject`
on the one prefix.

### 3c — post-deploy live verify (do NOT trust the green line)

Pusher role is PURE + least-privilege (Forensic tab):
```
ROLE=$(echo "$PROLE" | awk -F/ '{print $NF}') ; for P in $(aws iam list-role-policies --role-name "$ROLE" --query "PolicyNames" --output text); do aws iam get-role-policy --role-name "$ROLE" --policy-name "$P" --query "PolicyDocument.Statement[].{Sid:Sid,Action:Action,Resource:Resource}" --output json; done
```
Expect exactly: `dynamodb:GetItem` on the Hub table, `s3:GetObject` on the artifact bucket
`intake/*`, `s3:PutObject`+`s3:PutObjectTagging` on the Sandbox bucket `accepted/*`, and
`sqs:SendMessage` on the Hub ingest queue — **NO `bedrock:InvokeModel`, NO
`dynamodb:UpdateItem`/`PutItem`/`DeleteItem`, NO broader S3.**

Pusher env is PURE (Forensic tab):
```
aws lambda get-function-configuration --function-name "$PFN" --region us-east-1 --query "Environment.Variables"
```
Expect `TRACKING_TABLE`, `ARTIFACT_BUCKET`, `SANDBOX_LANDING_BUCKET`,
`SANDBOX_LANDING_PREFIX=accepted/`, `SANDBOX_ACCOUNT_ID=586917955591`,
`HUB_INGEST_QUEUE_URL`, `HANDOFF_CONTRACT_VERSION=1.0`, `LOG_LEVEL=INFO` — and **NO
`NOVA_MODEL_ID`**.

Sandbox bucket policy grants only the pusher role, one prefix, PutObject-only (Sandbox tab):
```
aws s3api get-bucket-policy --bucket "$SBKT" --region us-east-1 --query Policy --output text
```
Expect a single statement: `Effect: Allow`, principal = the pusher role ARN, action =
`s3:PutObject`(+`PutObjectTagging`), resource = `.../accepted/*`.

---

## STEP 4 — the FAIL-CLOSED proofs FIRST (nothing should leave Forensic yet)

> Prove the hard invariant BEFORE recording any accept: with `human_decision` still unset
> (`pending`), the pusher must REFUSE.

### 4a (Forensic tab) — invoke with NO accept → must refuse, nothing pushed

```
aws sts get-caller-identity
```
Expect `360999005254`.
```
IID=<the-intake_id> ; aws lambda invoke --function-name "$PFN" --payload "{\"intake_id\":\"$IID\"}" --cli-binary-format raw-in-base64-out --region us-east-1 /tmp/h1.json >/dev/null ; cat /tmp/h1.json
```
**Pass:** `"pushed": false`, `"outcome": "refused_not_accepted"`,
`"observed_decision": "pending"`.

Confirm NOTHING landed in the Sandbox (Pipeline-Sandbox tab):
```
aws sts get-caller-identity
```
Expect `586917955591`.
```
aws s3 ls "s3://$SBKT/accepted/$IID/" --region us-east-1 ; echo "exit=$?"
```
**Pass:** empty listing (no object) — nothing left Forensic on a non-accept.

### 4b — the outcome WAS recorded to the Hub (refusal) (Hub tab)

```
aws sts get-caller-identity
```
Expect `641628980935`.
```
TABLE=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='TrackingTableName'].OutputValue" --output text) ; IID=<the-intake_id> ; aws dynamodb get-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --region us-east-1 --query "Item.handoff_outcome.S"
```
**Pass:** `refused_not_accepted` (give the ingest gate a few seconds; reads are eventually
consistent). The refusal is recorded — the mechanism ran, it just refused.

---

## STEP 5 (Hub tab) — record the human ACCEPT, then push

> This is what Story 4.4's UI will do automatically later. For 4.6's validation you set it
> directly. **Set it ONLY on the intake you are handing off.**

```
aws sts get-caller-identity
```
Expect `641628980935`.
```
TABLE=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='TrackingTableName'].OutputValue" --output text) ; IID=<the-intake_id> ; aws dynamodb update-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --update-expression "SET human_decision = :d" --expression-attribute-values "{\":d\":{\"S\":\"accepted\"}}" --region us-east-1
```
Confirm it is set:
```
aws dynamodb get-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --region us-east-1 --query "Item.human_decision.S"
```
Expect `accepted`.

### 5a (Forensic tab) — invoke with the accept → PUSH

```
aws sts get-caller-identity
```
Expect `360999005254`.
```
IID=<the-intake_id> ; aws lambda invoke --function-name "$PFN" --payload "{\"intake_id\":\"$IID\"}" --cli-binary-format raw-in-base64-out --region us-east-1 /tmp/h2.json >/dev/null ; python3 -c "import json; d=json.load(open('/tmp/h2.json')); print('pushed:', d.get('pushed'), 'outcome:', d.get('outcome'), 'hash_verified:', d.get('hash_verified'), 'observed:', d.get('observed_decision')); print('dest:', d.get('handoff',{}).get('destination'))"
```
**Pass:** `pushed: True`, `outcome: pushed`, `hash_verified: True`,
`observed_decision: accepted`, and a `destination` block with
`account_id: 586917955591`, the Sandbox `bucket`, `prefix: accepted/`, and a `key` like
`accepted/<intake_id>/<filename>`.

### 5b (Pipeline-Sandbox tab) — confirm the artifact LANDED + the hash matches

```
aws sts get-caller-identity
```
Expect `586917955591`.
```
IID=<the-intake_id> ; aws s3 ls "s3://$SBKT/accepted/$IID/" --region us-east-1
```
**Pass:** the object is listed. Verify its recomputed sha256 matches the Hub record's
`sha256` (the exact inspected bytes crossed):
```
KEY=$(aws s3api list-objects-v2 --bucket "$SBKT" --prefix "accepted/$IID/" --region us-east-1 --query "Contents[0].Key" --output text) ; aws s3api get-object --bucket "$SBKT" --key "$KEY" --region us-east-1 /tmp/landed.bin >/dev/null ; python3 -c "import hashlib; print('landed sha256:', hashlib.sha256(open('/tmp/landed.bin','rb').read()).hexdigest())"
```
Compare that `landed sha256` to the Hub record's `sha256` from STEP 0 — **they must be
equal.** Also confirm the object metadata carried the hash:
```
aws s3api head-object --bucket "$SBKT" --key "$KEY" --region us-east-1 --query "Metadata"
```
Expect `intake-id` + `sha256` metadata.

### 5c (Hub tab) — the pushed outcome crossed (bounded, verdict-free)

```
aws sts get-caller-identity
```
Expect `641628980935`.
```
TABLE=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='TrackingTableName'].OutputValue" --output text) ; IID=<the-intake_id> ; aws dynamodb get-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --region us-east-1 --query "{outcome:Item.handoff_outcome.S, handoff:Item.handoff.M}"
```
**Pass:** `outcome` = `pushed`; the `handoff` map carries `observed_decision: accepted`,
`hash_verified: true`, and a `destination` pointer — and **NO** `verdict`/`safe`/`approved`/
`forward` key. (Give the ingest gate a few seconds.)

### 5d — no effective-verdict key crossed

```
IID=<the-intake_id> ; aws dynamodb get-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --region us-east-1 --query "Item.handoff" --output json > /tmp/ho.json ; python3 -c "import json; s=json.dumps(json.load(open('/tmp/ho.json'))); banned=['\"verdict\"','\"safe\"','\"approved\"','\"forward\"','\"malicious\"','\"pass_fail\"','\"clean\"']; print('FAIL: banned key present' if any(b in s for b in banned) else 'OK: no effective-verdict key in the crossed outcome')"
```
Expect `OK`.

---

## STEP 6 (optional) — hash-mismatch refusal (the SI-7 fail-closed proof)

> Optional but recommended: prove that even an ACCEPTED intake is refused if the bytes do not
> match. Easiest safe way: point at an intake whose artifact was re-written, OR temporarily
> corrupt the tracked `sha256` on a THROWAWAY test intake (NOT your real one) and confirm the
> pusher refuses. If you do not have a safe way to do this live, the offline `test_handler`
> `test_hash_mismatch_does_not_push_even_when_accepted` already proves the branch; note that
> in your paste-back.

---

## STEP 7 — paste back for the record

Paste back, VERBATIM:
- the `sts get-caller-identity` account for each tab used,
- the STEP 1 `git log --oneline -1` + the grep confirming the pusher is PURE,
- the STEP 3c pusher-role policy + env (PURE + least-privilege) + the Sandbox bucket policy,
- STEP 4a `/tmp/h1.json` (refused_not_accepted) + the empty Sandbox listing + STEP 4b
  `handoff_outcome` = `refused_not_accepted`,
- STEP 5a push summary, STEP 5b the landed object + the matching sha256 + the metadata,
  STEP 5c the `pushed` outcome map, STEP 5d the no-banned-key line,
- (optional) the STEP 6 mismatch-refusal result.

The executor records these verbatim into the RUNBOOK 4.6 detail, flips **4.6 → ✅** (paired
commit), clears 4.6 from the Validation Debt Register, and authors the 4.7 handoff. On a
FAIL, 4.6 stays 🟡 (already on the register); the executor fixes + re-validates once
(fix-then-validate-once), never marking done on inference.

## If something fails

- **Pipeline-Sandbox tab has no creds** — you cannot validate 4.6 without access to
  586917955591. Get creds for the Sandbox account first (this is the first ZTIE story to
  use it).
- **`AccessDenied` on the push** — the Sandbox bucket policy is not scoped to the pusher
  role yet (did you run STEP 3b with `-c forensicPusherRoleArn=`?), or the prefix does not
  match (`SANDBOX_LANDING_PREFIX` must equal the Sandbox stack's `landingPrefix`, both
  `accepted/`). Re-check STEP 3b + STEP 3c.
- **`outcome: refused_not_accepted` when you expected a push** — `human_decision` is not
  `accepted` on THIS intake (STEP 5 not applied / applied to a different id). Re-check STEP 5.
- **`outcome: refused_hash_mismatch`** — the Forensic artifact's bytes do not match the
  tracked `sha256` (the artifact was replaced, or you pointed at the wrong intake). This is
  the SI-7 guard working; confirm the artifact + record match.
- **`error.code: 404`** — no tracking record for that `intake_id` (wrong account / wrong
  id). Confirm the Hub + the correct id.
- **`error.code: 422`** — the tracking record is missing/malformed its `sha256` integrity
  key (an upstream data problem, not a 4.6 bug).
- **The object landed but its sha256 does not match** — a real 4.6 defect (the wrong bytes
  crossed). Capture it; the executor keeps 4.6 🟡 and fixes.
- **A bare effective-verdict key appears in the crossed outcome** — a real 4.6 defect (must
  be verdict-free). Capture it; keep 4.6 🟡 and fix.
- **Infra-shaped failure** (missing export / role) — check whether it is OD-001/OD-002
  cleanup fallout BEFORE assuming it is a 4.6 bug.
