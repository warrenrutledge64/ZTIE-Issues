# Story 3.1 — LIVE combined-event normalization validation runbook (stakeholder)

> **This is the ONLY live part of 3.1, and only YOU can do it** (the executor has no
> AWS creds). You REDEPLOY the Hub tracking stack (which now ships the DynamoDB stream +
> the combined-event normalizer Lambda), submit ONE routable artifact so the lanes
> populate the per-input derived records, and confirm that ONE verdict-free
> `combined_event` was normalized onto the SAME Hub tracking record. The executor
> **records your returned output verbatim** into the RUNBOOK 3.1 detail. **Nothing is
> recorded on inference** — paste back exactly what the commands print. On a pass the
> executor flips 3.1 ✅ (paired commit) and clears 3.1 from the Validation Debt Register.

## What 3.1 is (so the check is meaningful)

3.1 is a HUB-SIDE normalize (RD-033). All three inputs it aggregates — the static-scan
summary (`static_scan`, 2.1/2.2), the dynamic-run outcome (`dynamic_run`, 2.3) and the
sanitized behavioral telemetry (`sanitized`, 2.5) — ALREADY live on the Hub durable
tracking item. A new Lambda (`lambdas/hub_normalize/`) is triggered by the tracking
table's **DynamoDB stream**: every time an input lands it re-reads the item and
re-derives ONE `combined_event` (`combined-event.contract.v1`) written back onto the
SAME item. It is EVIDENCE only — NO verdict field anywhere — and honest about which
inputs have landed (`inputs_present` / `complete`). Nothing new crosses Forensic→Hub.

## Ground rules (these have bitten us every session)

- **TWO accounts → TWO CloudShell tabs.** The artifact + the lanes + the ephemeral host
  are in **Forensic (360999005254)**; the tracking table + the stream + the normalizer +
  the `combined_event` you verify are all in the **Hub (641628980935)**. Deploy the Hub
  stack + verify the combined event from a **Hub-authed** shell; submit the artifact from
  a **Forensic-authed** shell.
- **Run `aws sts get-caller-identity` BEFORE every block** and read `Account`. If it is
  not the account the block is for, switch tabs — do not proceed. (Recurring trap: a
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

## STEP 0 (Hub tab) — get the 3.1 code + confirm Hub + prove the checkout carries 3.1

> **Deploy-gap guard (learned live in the 2.5 session, 2026-09-11):** a `cdk deploy`
> prints `✅ UPDATE_COMPLETE` even when the box is on the WRONG branch — it just
> re-synthesizes the STALE stack. So BEFORE deploying, prove the checkout actually
> carries the 3.1 change; AFTER deploying, inspect the LIVE Lambda. Never trust the green
> line alone.

```
aws sts get-caller-identity
```
**Run in: Hub (641628980935), us-east-1, no --profile.** Expect `"Account": "641628980935"`.

```
cd ~/ZTIE-Issues && git fetch origin -q && git checkout feature/story-3.1 && git reset --hard origin/feature/story-3.1
```
(If the 3.1 PR is already merged, use `git checkout main && git reset --hard origin/main`.)

```
git rev-parse --abbrev-ref HEAD && git log --oneline -1
```
Expect the story branch (or `main`) at the 3.1 tip.

```
grep -n "CombinedEventNormalizer" infra/lib/ztie-hub-tracking-stack.ts
```
Expect at least one hit (the normalizer construct). If it is ABSENT, the checkout is
stale — re-run the checkout above. This is the pre-deploy marker check.

---

## STEP 1 (Hub tab) — redeploy the Hub tracking stack (ships the stream + normalizer)

```
cd ~/ZTIE-Issues/infra && npm ci
```

```
cd ~/ZTIE-Issues/infra && npx cdk deploy ZtieHubTrackingStack --require-approval never
```
Expect `✅ ZtieHubTrackingStack` with outputs incl. the NEW
`CombinedEventNormalizerName`. Capture the tracking table name + normalizer name:

```
aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='TrackingTableName'||OutputKey=='CombinedEventNormalizerName'].[OutputKey,OutputValue]" --output text
```

### Post-deploy live verify (do NOT trust the green line alone)

```
NORMALIZER=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='CombinedEventNormalizerName'].OutputValue" --output text) ; aws lambda get-function-configuration --function-name "$NORMALIZER" --region us-east-1 --query "Environment.Variables"
```
Expect `COMBINED_EVENT_CONTRACT_VERSION` = `1.0` and `TRACKING_TABLE` set. Confirm the
stream is wired + enabled:

```
TABLE=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='TrackingTableName'].OutputValue" --output text) ; aws dynamodb describe-table --table-name "$TABLE" --region us-east-1 --query "Table.{Stream:StreamSpecification,Arn:LatestStreamArn}"
```
Expect `StreamEnabled: true`, `StreamViewType: NEW_AND_OLD_IMAGES`, and a stream ARN.

```
aws lambda list-event-source-mappings --function-name "$NORMALIZER" --region us-east-1 --query "EventSourceMappings[].{Src:EventSourceArn,State:State}" --output text
```
Expect one mapping in state `Enabled` whose source is the table's stream ARN.

---

## STEP 2 (Forensic tab) — submit ONE routable artifact so the lanes populate inputs

> This drives the existing pipeline end-to-end so the three per-lane derived records land
> on the tracking item. Use an artifact routing to BOTH lanes (e.g. a small CloudFormation
> template) so `static_scan` + `dynamic_run` + `sanitized` all populate and 3.1 can reach
> `complete: true`. (If a lane does not land, 3.1 still writes a combined event — it just
> records that input `absent`; that is the honest-partial behavior, also worth capturing.)

```
aws sts get-caller-identity
```
**Run in: Forensic (360999005254), us-east-1, no --profile.** Expect `360999005254`.

```
pip install awscurl >/dev/null 2>&1 ; python3 -c "import base64,json; b=base64.b64encode(open('/etc/hostname','rb').read()).decode(); open('/tmp/intake.json','w').write(json.dumps({'filename':'probe.yaml','content_type':'text/yaml','submitter':'story-3.1-live','content_base64':b}))"
```
(Substitute a real routable artifact for `/etc/hostname` if you want both lanes to run;
the intake API wants the JSON envelope, URL LAST, `-d @file`.)

```
ENDPOINT=$(aws cloudformation describe-stacks --stack-name ZtieIntakeStack --region us-east-1 --query "Stacks[0].Outputs[?contains(OutputKey,'IntakeApi')||contains(OutputKey,'Endpoint')].OutputValue" --output text) ; echo "$ENDPOINT"
```

```
awscurl --service execute-api --region us-east-1 -X POST -H 'Content-Type: application/json' -d @/tmp/intake.json "${ENDPOINT%/}/intake"
```
**Record the returned `intake_id`** (call it `IID`) — you verify the combined event by it.

---

## STEP 3 (Hub tab) — confirm ONE verdict-free `combined_event` was normalized

Give the lanes + the stream a minute, then read the tracking item (Hub tab):

```
aws sts get-caller-identity
```
Expect `641628980935`.

```
TABLE=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='TrackingTableName'].OutputValue" --output text) ; IID=<paste-the-intake_id> ; aws dynamodb get-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --region us-east-1 --query "Item.combined_event" --output json
```

**Pass criteria (all must hold):**
1. A `combined_event` object is present on the item (the normalizer fired off the stream).
2. `combined_event.sources` has `static` / `dynamic` / `sanitized`, each with `presence`
   `present` or `absent` HONESTLY matching which inputs landed; `inputs_present` lists
   exactly the present ones; `complete` is `true` iff all three are present.
3. `combined_event.signals.behavioral_events` (if the sanitized input landed) carry the
   ALREADY-sanitized 2.5 events with RELATIVE `offset_ms` (no wall clock).
4. **No verdict anywhere.** Confirm with a grep of the whole item:

```
aws dynamodb get-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --region us-east-1 --output json | grep -Ei "verdict|safe|approved|forward|malicious|pass_fail|\"clean\"" || echo "NO verdict-shaped key present (expected)"
```
Expect `NO verdict-shaped key present (expected)`.

5. **Idempotency / no stream loop** — read the normalizer's recent logs and confirm it
   is NOT re-writing an unchanged event in a loop:

```
NORMALIZER=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='CombinedEventNormalizerName'].OutputValue" --output text) ; aws logs tail "/aws/lambda/$NORMALIZER" --region us-east-1 --since 10m --format short | grep -Ei "combined event (written|unchanged)" | tail -20
```
Expect to see `combined event written` for the real input landings and then `combined
event unchanged; no write (idempotent)` — NOT an unbounded stream of writes.

---

## What to paste back to the executor

- STEP 0: branch + `git log -1` + the `grep CombinedEventNormalizer` hit.
- STEP 1: the deploy result line, the two outputs, the Lambda `Environment.Variables`,
  the `describe-table` stream block, and the event-source-mapping line.
- STEP 2: the `intake_id`.
- STEP 3: the `combined_event` JSON, the no-verdict grep result, and the idempotency log
  lines.

On a pass the executor records this verbatim into RUNBOOK 3.1 detail, flips 3.1 ✅
(paired commit), and clears 3.1 from the Validation Debt Register (which re-opens the
gate for 3.2). On any fail, 3.1 stays 🟡 — the executor fixes and you re-run.
