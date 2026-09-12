# Story 3.2 — LIVE Nova Pro correlation validation runbook (stakeholder)

> **This is the ONLY live part of 3.2, and only YOU can do it** (the executor has no
> AWS creds). You REDEPLOY the Hub tracking stack (which now ships the Story 3.2
> correlator Lambda + its `bedrock:InvokeModel` grant + a second DynamoDB-stream
> trigger), make sure Nova Pro is enabled in Bedrock for the Hub account, submit ONE
> routable artifact so a `combined_event` (3.1) lands, and confirm that ONE
> **verdict-free** `correlation_result` — produced by a REAL Amazon Nova Pro call — was
> recorded onto the SAME Hub tracking record. The executor **records your returned
> output verbatim** into the RUNBOOK 3.2 detail. **Nothing is recorded on inference** —
> paste back exactly what the commands print. On a pass the executor flips 3.2 ✅
> (paired commit) and clears 3.2 from the Validation Debt Register.

## What 3.2 is (so the check is meaningful)

3.2 is a HUB-SIDE derivation (RD-035), exactly like 3.1's placement (RD-033). Its input
— the ONE normalized `combined_event` that 3.1 wrote onto the Hub tracking item —
ALREADY lives Hub-side. A NEW Lambda (`lambdas/hub_correlate/`) is triggered by the
tracking table's **DynamoDB stream** (the same stream 3.1 uses): when a `combined_event`
is ready, it hands the bounded, evidence-only view to **Amazon Nova Pro** (RD-003) via
`bedrock-runtime`, correlates the static misconfigurations against the dynamic behavioral
indicators, and records a bounded, verdict-free `correlation_result`
(`correlation.contract.v1`) back onto the SAME item — with real exponential-backoff
retry on Bedrock throttling. It is EVIDENCE only — **NO verdict field anywhere**; the
prompt never asks the model for a verdict, and a malformed/absent/throttled response is
recorded honestly (a `status`), never fabricated. Nothing new crosses Forensic→Hub.

## Ground rules (these have bitten us every session)

- **TWO accounts → TWO CloudShell tabs.** The artifact + the lanes + the ephemeral host
  are in **Forensic (360999005254)**; the tracking table + the stream + the correlator +
  the `correlation_result` you verify + **Bedrock/Nova Pro** are all in the
  **Hub (641628980935)**. Deploy the Hub stack + verify the correlation from a
  **Hub-authed** shell; submit the artifact from a **Forensic-authed** shell.
- **Run `aws sts get-caller-identity` BEFORE every block** and read `Account`. If it is
  not the account the block is for, switch tabs. (Recurring trap: a
  `ResourceNotFoundException` on the tracking table means you queried it from Forensic;
  it lives in the Hub.)
- **Feed commands ONE LINE AT A TIME.** Never paste a multi-line block.
- **`/tmp` + shell vars are WIPED when CloudShell recycles.** Re-set every variable in
  the SAME block right before using it, and re-`pip install awscurl` before an intake
  submit.
- **Region us-east-1**, ambient creds (**no `--profile`**).
- **GitHub auth in CloudShell:** token-in-URL HTTPS form
  `git remote set-url origin https://<TOKEN>@github.com/warrenrutledge64/ZTIE-Issues.git`.

---

## STEP 0 (Hub tab) — Bedrock/Nova Pro access prerequisite

> Nova Pro must be ENABLED for the Hub account (model access is per-account, per-region)
> or the very first live call fails `AccessDeniedException` — which 3.2 will honestly
> record as `status: model_error`, but that is NOT a passing correlation. Confirm access
> once, up front.

```
aws sts get-caller-identity
```
**Run in: Hub (641628980935), us-east-1, no --profile.** Expect `"Account": "641628980935"`.

```
aws bedrock list-foundation-models --region us-east-1 --query "modelSummaries[?contains(modelId,'nova-pro')].[modelId,modelLifecycle.status]" --output text
```
Expect a `amazon.nova-pro-v1:0` (ACTIVE) row. If Bedrock model access for Nova Pro is not
yet granted, enable it in the Bedrock console (Model access) for us-east-1 before
proceeding. Nova Pro on-demand is invoked through the region-prefixed inference profile
`us.amazon.nova-pro-v1:0` (the correlator's default `NOVA_MODEL_ID`).

---

## STEP 1 (Hub tab) — get the 3.2 code + prove the checkout carries 3.2

> **Deploy-gap guard (learned live in the 2.5 session, 2026-09-11):** a `cdk deploy`
> prints `✅ UPDATE_COMPLETE` even when the box is on the WRONG branch — it just
> re-synthesizes STALE code. So BEFORE deploying, prove the checkout carries the 3.2
> change; AFTER deploying, inspect the LIVE Lambda. Never trust the green line alone.

```
cd ~/ZTIE-Issues && git fetch origin -q && git checkout feature/story-3.2 && git reset --hard origin/feature/story-3.2
```
(If the 3.2 PR is already merged, use `git checkout main && git reset --hard origin/main`.)

```
git rev-parse --abbrev-ref HEAD && git log --oneline -1
```
Expect the story branch (or `main`) at the 3.2 tip.

```
grep -n "NovaCorrelator" infra/lib/ztie-hub-tracking-stack.ts
```
Expect at least one hit (the correlator construct + its output). If ABSENT, the checkout
is stale — re-run the checkout above. This is the pre-deploy marker check.

---

## STEP 2 (Hub tab) — redeploy the Hub tracking stack (ships the correlator)

```
cd ~/ZTIE-Issues/infra && npm ci
```

```
cd ~/ZTIE-Issues/infra && npx cdk deploy ZtieHubTrackingStack --require-approval never
```
Expect `✅ ZtieHubTrackingStack` with outputs incl. the NEW `NovaCorrelatorName` +
`NovaModelId`.

### Post-deploy live verify (do NOT trust the green line alone)

```
CORR=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='NovaCorrelatorName'].OutputValue" --output text) ; aws lambda get-function-configuration --function-name "$CORR" --region us-east-1 --query "Environment.Variables"
```
Expect `CORRELATION_CONTRACT_VERSION` = `1.0`, `NOVA_MODEL_ID` = `us.amazon.nova-pro-v1:0`,
`NOVA_MAX_ATTEMPTS` = `5`, `CORRELATE_ONLY_WHEN_COMPLETE` = `1`, `TRACKING_TABLE` set.

Confirm the correlator has its own stream mapping (a SECOND consumer beside the 3.1
normalizer):

```
CORR=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='NovaCorrelatorName'].OutputValue" --output text) ; aws lambda list-event-source-mappings --function-name "$CORR" --region us-east-1 --query "EventSourceMappings[].{Src:EventSourceArn,State:State}" --output text
```
Expect one mapping in state `Enabled` whose source is the tracking table's stream ARN.

Confirm the Bedrock grant is scoped (NOT `*`):

```
CORR=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='NovaCorrelatorName'].OutputValue" --output text) ; ROLE=$(aws lambda get-function-configuration --function-name "$CORR" --region us-east-1 --query Role --output text | awk -F/ '{print $NF}') ; aws iam list-role-policies --role-name "$ROLE" --query "PolicyNames" --output text
```
Then inspect the inline policy for the `InvokeNovaProOnly` statement — its `Resource`
should list the Nova Pro inference-profile + foundation-model ARNs, never `*`:

```
aws iam get-role-policy --role-name "$ROLE" --policy-name <the-policy-name-from-above> --query "PolicyDocument.Statement[?Sid=='InvokeNovaProOnly']" --output json
```

---

## STEP 3 (Forensic tab) — submit ONE routable artifact so a combined event lands

> This drives the pipeline so the per-lane inputs land and 3.1 normalizes a
> `combined_event` — which triggers 3.2. Use an artifact routing to BOTH lanes (e.g. a
> small CloudFormation template) so the combined event reaches `complete: true` (the
> default gate `CORRELATE_ONLY_WHEN_COMPLETE=1` waits for all three inputs). If you have
> a recent intake from the 3.1 validation whose `combined_event` is `complete`, you may
> REUSE its `intake_id` instead of submitting a new one — the correlator fires off the
> stream when the combined event is ready.

```
aws sts get-caller-identity
```
**Run in: Forensic (360999005254), us-east-1, no --profile.** Expect `360999005254`.

```
pip install awscurl >/dev/null 2>&1 ; python3 -c "import base64,json; b=base64.b64encode(open('/etc/hostname','rb').read()).decode(); open('/tmp/intake.json','w').write(json.dumps({'filename':'probe.yaml','content_type':'text/yaml','submitter':'story-3.2-live','content_base64':b}))"
```
(Substitute a real both-lanes-routable artifact for `/etc/hostname` so the combined event
reaches `complete: true`; the intake API wants the JSON envelope, URL LAST, `-d @file`.)

```
ENDPOINT=$(aws cloudformation describe-stacks --stack-name ZtieIntakeStack --region us-east-1 --query "Stacks[0].Outputs[?contains(OutputKey,'IntakeApi')||contains(OutputKey,'Endpoint')].OutputValue" --output text) ; echo "$ENDPOINT"
```

```
awscurl --service execute-api --region us-east-1 -X POST -H 'Content-Type: application/json' -d @/tmp/intake.json "${ENDPOINT%/}/intake"
```
**Record the returned `intake_id`** (call it `IID`).

---

## STEP 4 (Hub tab) — confirm ONE verdict-free `correlation_result` from a REAL Nova Pro call

Give the lanes + 3.1 + the stream + the model call a couple of minutes, then read the
tracking item (Hub tab):

```
aws sts get-caller-identity
```
Expect `641628980935`.

```
TABLE=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='TrackingTableName'].OutputValue" --output text) ; IID=<paste-the-intake_id> ; aws dynamodb get-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --region us-east-1 --query "Item.correlation_result" --output json
```

**Pass criteria (all must hold):**
1. A `correlation_result` object is present on the item (the correlator fired off the
   stream after the combined event was ready).
2. `status` is **`correlated`** (a real Nova Pro response was parsed). `model_id` is the
   Nova Pro id; `attempts` is present (1 on a clean first try; >1 means the
   exponential-backoff retry engaged — either is fine, both prove the retry path exists).
3. A bounded `correlation` object is present with a `summary` and a `findings` array
   (each finding `kind` ∈ correlated/static_only/dynamic_only/contradiction, a descriptive
   `severity`, a bounded `title`). `finding_count` matches the array length; the array is
   capped at 100.
4. `combined_complete` reflects the combined event (`true` for a both-lanes artifact).
5. **No verdict anywhere.** Confirm with a grep of the whole item:

```
aws dynamodb get-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --region us-east-1 --output json | grep -Ei "verdict|safe|approved|forward|malicious|pass_fail|\"clean\"" || echo "NO verdict-shaped key present (expected)"
```
Expect `NO verdict-shaped key present (expected)`.

6. **Retry is inspectable + no call storm** — read the correlator's recent logs:

```
CORR=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='NovaCorrelatorName'].OutputValue" --output text) ; aws logs tail "/aws/lambda/$CORR" --region us-east-1 --since 15m --format short | grep -Ei "correlation recorded|already correlated|backing off|not complete yet|no correlatable" | tail -30
```
Expect to see `correlation recorded (status=correlated, attempts=N, findings=…)` ONCE for
the settled combined event, then `already correlated for this combined-event fingerprint;
no-op (guard)` on subsequent stream events — NOT an unbounded stream of model calls. Any
`backing off …` lines (if throttled) are the exponential-backoff retry working.

### If `status` is `model_error` or `unparseable` (honest, but not a pass)

- `model_error` with `AccessDeniedException` in `status_detail` → Nova Pro model access
  is not enabled for the Hub account (STEP 0); enable it and re-submit.
- `model_error` with `ThrottlingException after N attempts` → the retry budget was
  exhausted under heavy throttling; re-submit (the retry path is proven; this is a
  capacity condition, not a code defect).
- `unparseable` → the model returned an off-format response; the correlator recorded it
  honestly (never fabricated). Re-submit; if it persists, the executor tunes the prompt
  and you re-run (fix-then-validate-once).
- In all cases the record is HONEST and NO verdict is asserted — that part of the design
  is already validated, but a **passing** 3.2 needs a `status: correlated` run.

---

## What to paste back to the executor

- STEP 0: the `list-foundation-models` Nova Pro row.
- STEP 1: branch + `git log -1` + the `grep NovaCorrelator` hit.
- STEP 2: the deploy result line, the `NovaCorrelatorName`/`NovaModelId` outputs, the
  Lambda `Environment.Variables`, the event-source-mapping line, and the
  `InvokeNovaProOnly` policy statement (to confirm it is scoped, not `*`).
- STEP 3: the `intake_id`.
- STEP 4: the `correlation_result` JSON, the no-verdict grep result, and the correlator
  log lines (the `correlation recorded …` line + the `already correlated … no-op` line).

On a pass (a `status: correlated` result with the retry inspectable and no verdict) the
executor records this verbatim into RUNBOOK 3.2 detail, flips 3.2 ✅ (paired commit), and
clears 3.2 from the Validation Debt Register (which re-opens the gate for 3.3). On any
fail, 3.2 stays 🟡 — the executor fixes and you re-run.
