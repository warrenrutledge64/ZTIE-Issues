# Story 3.3 — LIVE accuracy + gap_analysis synthesis validation runbook (stakeholder)

> **This is the ONLY live part of 3.3, and only YOU can do it** (the executor has no
> AWS creds). You REDEPLOY the Hub tracking stack (which now ships the Story 3.3
> synthesizer Lambda + a THIRD DynamoDB-stream trigger), submit ONE routable artifact so
> a `correlation_result` (3.2) lands, and confirm that ONE **verdict-free**
> `synthesis_result` was recorded onto the SAME Hub tracking record — with a **static-only
> finding demonstrably reconciled against benign dynamic evidence** (a candidate false
> positive + a `static_uncorroborated` gap). The executor **records your returned output
> verbatim** into the RUNBOOK 3.3 detail. **Nothing is recorded on inference** — paste
> back exactly what the commands print. On a pass the executor flips 3.3 ✅ (paired
> commit) and clears 3.3 from the Validation Debt Register.

## What 3.3 is (so the check is meaningful)

3.3 is a HUB-SIDE derivation (RD-037), exactly like 3.1's (RD-033) and 3.2's (RD-035)
placement. Its input — the ONE verdict-free `correlation_result` that 3.2 wrote onto the
Hub tracking item — ALREADY lives Hub-side. A NEW Lambda (`lambdas/hub_synthesize/`) is
triggered by the tracking table's **DynamoDB stream** (the SAME stream 3.1/3.2 use): when
a `correlation_result` is present, it runs the `accuracy` + `gap_analysis` synthesis in
**PURE deterministic logic** and records a bounded, verdict-free `synthesis_result`
(`synthesis.contract.v1`) back onto the SAME item.

> **It is NOT a second Nova Pro call (RD-037).** The semantic static↔dynamic reasoning
> was already done by Nova Pro in 3.2 — the correlation carries discrete, categorized
> findings (each `kind` ∈ correlated/static_only/dynamic_only/contradiction). accuracy +
> gap_analysis are deterministic aggregations over that structure. So — unlike the 3.2
> correlator — **this Lambda has NO Bedrock client and NO Bedrock grant**, and there is
> **no Bedrock/model-access prerequisite** for this validation. It is EVIDENCE only —
> **NO verdict field anywhere**; an absent/non-correlated upstream is recorded honestly
> (a `status`), never fabricated. Nothing new crosses Forensic→Hub.

## Ground rules (these have bitten us every session)

- **TWO accounts → TWO CloudShell tabs.** The artifact + the lanes + the ephemeral host
  are in **Forensic (360999005254)**; the tracking table + the stream + the synthesizer +
  the `synthesis_result` you verify are all in the **Hub (641628980935)**. Deploy the Hub
  stack + verify the synthesis from a **Hub-authed** shell; submit the artifact from a
  **Forensic-authed** shell.
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

## STEP 1 (Hub tab) — get the 3.3 code + prove the checkout carries 3.3

> **Deploy-gap guard (learned live in the 2.5/2.6 sessions):** a `cdk deploy` prints
> `✅ UPDATE_COMPLETE` even when the box is on the WRONG branch — it just re-synthesizes
> STALE code. So BEFORE deploying, prove the checkout carries the 3.3 change; AFTER
> deploying, inspect the LIVE Lambda. Never trust the green line alone.

```
aws sts get-caller-identity
```
**Run in: Hub (641628980935), us-east-1, no --profile.** Expect `"Account": "641628980935"`.

```
cd ~/ZTIE-Issues && git fetch origin -q && git checkout feature/story-3.3 && git reset --hard origin/feature/story-3.3
```
(If the 3.3 PR is already merged, use `git checkout main && git reset --hard origin/main`.)

```
git rev-parse --abbrev-ref HEAD && git log --oneline -1
```
Expect the story branch (or `main`) at the 3.3 tip.

```
grep -n "SynthesisSynthesizer" infra/lib/ztie-hub-tracking-stack.ts
```
Expect at least one hit (the synthesizer construct + its output). If ABSENT, the checkout
is stale — re-run the checkout above. This is the pre-deploy marker check.

---

## STEP 2 (Hub tab) — redeploy the Hub tracking stack (ships the synthesizer)

```
cd ~/ZTIE-Issues/infra && npm ci
```

```
cd ~/ZTIE-Issues/infra && npx cdk deploy ZtieHubTrackingStack --require-approval never
```
Expect `✅ ZtieHubTrackingStack` with the NEW `SynthesisSynthesizerName` output.

### Post-deploy live verify (do NOT trust the green line alone)

```
SYN=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='SynthesisSynthesizerName'].OutputValue" --output text) ; aws lambda get-function-configuration --function-name "$SYN" --region us-east-1 --query "Environment.Variables"
```
Expect `SYNTHESIS_CONTRACT_VERSION` = `1.0`, `TRACKING_TABLE` set. (There is deliberately
NO `NOVA_MODEL_ID` / Bedrock env here — RD-037, pure post-processing.)

Confirm the synthesizer has its own stream mapping (a THIRD consumer beside the 3.1
normalizer + 3.2 correlator):

```
SYN=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='SynthesisSynthesizerName'].OutputValue" --output text) ; aws lambda list-event-source-mappings --function-name "$SYN" --region us-east-1 --query "EventSourceMappings[].{Src:EventSourceArn,State:State}" --output text
```
Expect one mapping in state `Enabled` whose source is the tracking table's stream ARN.

Confirm the synthesizer role has **NO Bedrock grant** (RD-037) — it should hold only the
DynamoDB read/write on the tracking table:

```
SYN=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='SynthesisSynthesizerName'].OutputValue" --output text) ; ROLE=$(aws lambda get-function-configuration --function-name "$SYN" --region us-east-1 --query Role --output text | awk -F/ '{print $NF}') ; for P in $(aws iam list-role-policies --role-name "$ROLE" --query "PolicyNames" --output text); do aws iam get-role-policy --role-name "$ROLE" --policy-name "$P" --query "PolicyDocument.Statement[].Action" --output json; done
```
Expect DynamoDB actions only (GetItem / UpdateItem / etc. on the tracking table). Expect
**NO `bedrock:*`** action anywhere.

---

## STEP 3 (Forensic tab) — submit ONE artifact that yields a STATIC-ONLY finding

> This is the DoD case: we need a `correlation_result` that carries at least one
> `static_only` finding (a static flag the dynamic behavior never exercised) so the
> synthesis can reconcile it as a **candidate false positive**. The 3.2 validation intake
> (`6145dc20-…`) already produced exactly this shape (`status:correlated`, one
> `kind:static_only` finding, because the detonation errored with no dynamic
> correlation). **If that item is still in the tracking table you may simply REUSE its
> `intake_id`** — the synthesizer fires off the stream when a `correlation_result` is
> present, and STEP 2's redeploy will have created the new stream mapping (which starts
> at `LATEST`, so submit/mutate AFTER the deploy — see STEP 3b). Otherwise submit a fresh
> routable artifact (a small CloudFormation template with a flagged-but-benign
> misconfiguration is ideal — static flags it, dynamic never exercises it).

```
aws sts get-caller-identity
```
**Run in: Forensic (360999005254), us-east-1, no --profile.** Expect `360999005254`.

```
pip install awscurl >/dev/null 2>&1 ; python3 -c "import base64,json; b=base64.b64encode(open('/etc/hostname','rb').read()).decode(); open('/tmp/intake.json','w').write(json.dumps({'filename':'probe.yaml','content_type':'text/yaml','submitter':'story-3.3-live','content_base64':b}))"
```
(Substitute a real both-lanes-routable artifact for `/etc/hostname` so a `correlation_result`
lands; the intake API wants the JSON envelope, URL LAST, `-d @file`.)

```
ENDPOINT=$(aws cloudformation describe-stacks --stack-name ZtieIntakeStack --region us-east-1 --query "Stacks[0].Outputs[?contains(OutputKey,'IntakeApi')||contains(OutputKey,'Endpoint')].OutputValue" --output text) ; echo "$ENDPOINT"
```

```
awscurl --service execute-api --region us-east-1 -X POST -H 'Content-Type: application/json' -d @/tmp/intake.json "${ENDPOINT%/}/intake"
```
**Record the returned `intake_id`** (call it `IID`).

### STEP 3b — REUSING an existing correlated item (Hub tab, optional)

The synthesizer's stream mapping starts at `LATEST`, so an OLD `correlation_result` that
was written before STEP 2's redeploy will NOT re-trigger on its own. To synthesize a
pre-existing correlated item, nudge it so a fresh stream event fires (a no-op touch that
does not change the correlation content — the fingerprint guard still fires once):

```
TABLE=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='TrackingTableName'].OutputValue" --output text) ; IID=<paste-a-correlated-intake_id> ; aws dynamodb update-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --update-expression "SET synthesis_touch = :t" --expression-attribute-values "{\":t\":{\"S\":\"story-3.3-live\"}}" --region us-east-1
```
(Fresh submits via STEP 3 do not need this — the 3.2 correlator's own write fires the
stream after the deploy.)

---

## STEP 4 (Hub tab) — confirm ONE verdict-free `synthesis_result` with the FP reconciled

Give the lanes + 3.1 + 3.2 + the stream a couple of minutes, then read the tracking item
(Hub tab):

```
aws sts get-caller-identity
```
Expect `641628980935`.

```
TABLE=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='TrackingTableName'].OutputValue" --output text) ; IID=<paste-the-intake_id> ; aws dynamodb get-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --region us-east-1 --query "Item.synthesis_result" --output json
```

**Pass criteria (all must hold):**
1. A `synthesis_result` object is present on the item (the synthesizer fired off the
   stream after the correlation was ready).
2. `status` is **`synthesized`** (the correlation carried at least one finding). A
   `synthesis` object is present with `summary`, `accuracy`, and `gaps`.
3. **The false positive is reconciled** — the DoD assertion. In `synthesis.accuracy`:
   `candidate_false_positive_count` ≥ 1, and `candidate_false_positives[]` contains the
   static-only finding (its `title`/`severity` carried from the correlation). The
   `accuracy_score` is a 0-100 reconciliation metric (e.g. a run with 0 confirmed
   correlations + 1 static-only scores 0 — every flagged item is uncorroborated). In
   `synthesis.gaps.items[]` the SAME finding appears as a `gap_type: static_uncorroborated`
   gap. This is a static flag reconciled against benign/absent dynamic evidence — a
   candidate false positive surfaced for the human gate, exactly what RD-003 promises.
4. `source_finding_count` matches the number of correlation findings; the
   `candidate_false_positives` + `gaps.items` arrays are each capped at 100.
5. **No verdict anywhere.** Confirm with a grep of the whole item:

```
aws dynamodb get-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --region us-east-1 --output json | grep -Ei "verdict|safe|approved|forward|malicious|pass_fail|\"clean\"" || echo "NO verdict-shaped key present (expected)"
```
Expect `NO verdict-shaped key present (expected)`.

6. **Synthesized once + no stream loop** — read the synthesizer's recent logs:

```
SYN=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='SynthesisSynthesizerName'].OutputValue" --output text) ; aws logs tail "/aws/lambda/$SYN" --region us-east-1 --since 15m --format short | grep -Ei "synthesis recorded|already synthesized|no correlation_result" | tail -30
```
Expect `synthesis recorded (status=synthesized, confirmed=…, candidate_false_positives=…,
gaps=…)` ONCE for the settled correlation, then `already synthesized for this correlation
fingerprint; no-op (guard)` on subsequent stream events — NOT an unbounded stream of
re-synthesis (proves the fingerprint call-storm/loop guard + the `Decimal`-canonicalized
fingerprint from the 3.1 loop lesson).

### If `status` is `no_correlation` or `skipped_no_findings` (honest, but not a pass)

- `no_correlation` → the upstream `correlation_result` was absent or its status was not
  `correlated` (e.g. the 3.2 correlation was `model_error`/`unparseable`). The synthesizer
  recorded that honestly (no synthesis fabricated). Get a `status:correlated` correlation
  first (re-run 3.2's step / re-submit), then re-check.
- `skipped_no_findings` → the correlation succeeded but carried ZERO findings (nothing to
  synthesize). Submit an artifact that produces at least one static finding so a
  `static_only` correlation finding results.
- In both cases the record is HONEST and NO verdict is asserted — that part of the design
  is already validated, but a **passing** 3.3 needs a `status: synthesized` run that
  reconciles a static-only finding as a candidate false positive.

---

## What to paste back to the executor

- STEP 1: branch + `git log -1` + the `grep SynthesisSynthesizer` hit.
- STEP 2: the deploy result line, the `SynthesisSynthesizerName` output, the Lambda
  `Environment.Variables` (to confirm the `SYNTHESIS_CONTRACT_VERSION` pin + NO Bedrock
  env), the event-source-mapping line, and the role's policy actions (to confirm NO
  `bedrock:*`).
- STEP 3: the `intake_id` (and whether it was a fresh submit or a reused correlated item).
- STEP 4: the `synthesis_result` JSON (showing `candidate_false_positives` + the
  `static_uncorroborated` gap — the reconciled false positive), the no-verdict grep
  result, and the synthesizer log lines (the `synthesis recorded …` line + the `already
  synthesized … no-op` line).

On a pass (a `status: synthesized` result with a static-only finding reconciled as a
candidate false positive + a `static_uncorroborated` gap, no verdict, synthesized once)
the executor records this verbatim into RUNBOOK 3.3 detail, flips 3.3 ✅ (paired commit),
and clears 3.3 from the Validation Debt Register (which re-opens the gate for 3.4). On any
fail, 3.3 stays 🟡 — the executor fixes and you re-run (fix-then-validate-once).
