# Story 3.4 — LIVE findings + prioritized-remediations validation runbook (stakeholder) — RD-039

> **This is the ONLY live part of 3.4, and only YOU can do it** (the executor has no
> AWS creds). You REDEPLOY the Hub tracking stack (which now ships the NEW Story 3.4
> `hub_remediate` Lambda), submit ONE routable artifact so the full pipeline runs
> (intake → both lanes → 3.1 combined event → 3.2 correlation → 3.3 three scores), and
> confirm that ONE **verdict-free** `remediation_result` — carrying **detailed findings
> (incl. the migrated candidate-false-positive + gap lists) + a prioritized remediation
> list** — was recorded onto the SAME Hub tracking record, PURELY (no model call). The
> executor **records your returned output verbatim** into the RUNBOOK 3.4 detail.
> **Nothing is recorded on inference** — paste back exactly what the commands print. On a
> pass the executor flips 3.4 ✅ (paired commit) and clears 3.4 from the Validation Debt
> Register.
>
> **This run DOUBLES as the OD-001/OD-002 post-cleanup regression proof** (DoD #4): ~20
> stale stacks were deleted across both accounts on 2026-09-12; the live ZTIE pipeline
> stacks were kept + untouched. If the full intake→lanes→correlation→scoring→Hub-record
> flow runs green end-to-end, the cleanup was safe. If an infra-shaped failure appears
> (missing role / bucket / VPC endpoint / export), check whether a deleted stack was a
> hidden dependency BEFORE assuming it is a 3.4 bug.

## What 3.4 is (RD-039 — so the check is meaningful)

3.4 is the findings + remediations step of Phase 3. It reads the 3.3 `scoring_result`
(three 0-100 risk scores: static / dynamic / combined) AND the 3.2 `correlation_result`
(the categorized static↔dynamic findings) ALREADY on the Hub tracking item and produces a
bounded, verdict-free `remediation_result`:

- **detailed findings** — the 3.2 correlation findings surfaced for a human, PLUS the
  **migrated candidate-false-positive list** (from `static_only` findings) and the **gap
  list** (`static_uncorroborated` / `dynamic_unexplained` / `contradiction` / `coverage`).
- **a prioritized remediation list** — ranked highest-risk-first by the three risk scores +
  the finding/gap severities; each remediation an actionable, inert "fix X" string.

**CONTRACT-FIRST decision (RD-039): 3.4 is PURE Hub-side post-processing — it makes NO
model call** (its inputs are already structured). So — UNLIKE the 3.2 correlator + the 3.3
scorer — the `hub_remediate` Lambda has **NO Bedrock client and NO Bedrock grant**. That
means **there is NO Bedrock/Nova Pro prerequisite for 3.4 itself** (Nova Pro is still
needed UPSTREAM so 3.2 + 3.3 land their inputs). It is EVIDENCE + a to-do list, **never a
verdict** — the PASS/FAIL/INCONCLUSIVE decision is Story 3.5 + the human gate. Nothing new
crosses Forensic→Hub (it reads the derived scores + findings already on the item).

## Ground rules (these have bitten us every session)

- **TWO accounts → TWO CloudShell tabs.** The artifact + lanes + ephemeral host are in
  **Forensic (360999005254)**; the tracking table + stream + the `hub_remediate` Lambda +
  the `remediation_result` you verify are all in the **Hub (641628980935)**. Deploy the Hub
  stack + verify from a **Hub-authed** shell; submit the artifact from a **Forensic-authed**
  shell.
- **Run `aws sts get-caller-identity` BEFORE every block** and read `Account`. A
  `ResourceNotFoundException` on the tracking table means you queried it from Forensic; it
  lives in the Hub.
- **Feed commands ONE LINE AT A TIME.** Never paste a multi-line block.
- **`/tmp` + shell vars are WIPED when CloudShell recycles.** Re-set every variable in the
  SAME block right before using it, and re-`pip install awscurl` before an intake submit.
- **Region us-east-1**, ambient creds (**no `--profile`**).
- **The `hub_remediate` Lambda uses a CUSTOM log group** (OD-003 explicit LogGroup), so
  `aws logs tail /aws/lambda/<fn>` fails `ResourceNotFoundException`. Tail the real group
  from `LoggingConfig.LogGroup` (see STEP 4).
- **Use a ROUTABLE artifact** (a small CloudFormation template with an S3 bucket) so both
  lanes run, 3.1 reaches `complete`, and 3.2 + 3.3 land — otherwise 3.4 has nothing to
  assess. A trivial file (`/etc/hostname`) classifies `other_unknown` → `SAFE_REJECTED`.
- **Endpoint query returns TWO outputs** (`IntakeApi…` + `…Endpoint`) joined by a tab,
  which breaks SigV4 — pin exactly one URL (see STEP 3).
- **Reads are eventually-consistent** right after a write — re-read after a moment.

---

## STEP 0 (Hub tab) — no Bedrock prerequisite for 3.4 (but 3.2/3.3 need it upstream)

> 3.4 makes NO model call (RD-039 PURE), so it needs no Bedrock access itself. But it
> assesses over the 3.3 `scoring_result`, which needs Nova Pro enabled for the Hub account
> (as in the 3.2/3.3 live runs). If your artifact does not produce a `scoring_result`,
> confirm Nova Pro access exactly as the 3.3 LIVE-RUNBOOK STEP 0 describes.

```
aws sts get-caller-identity
```
**Run in: Hub (641628980935), us-east-1, no --profile.** Expect `"Account": "641628980935"`.

---

## STEP 1 (Hub tab) — get the 3.4 code + prove the checkout carries it

> **Deploy-gap guard:** a `cdk deploy` prints `✅ UPDATE_COMPLETE` even on the WRONG
> branch — it just re-synthesizes STALE code. BEFORE deploying, prove the checkout carries
> the RD-039 code; AFTER deploying, inspect the LIVE Lambda. Never trust the green line.

```
cd ~/ZTIE-Issues && git fetch origin -q && git checkout feature/story-3.4 && git reset --hard origin/feature/story-3.4
```
(If the 3.4 PR is already merged, use `git checkout main && git reset --hard origin/main`.)

```
git rev-parse --abbrev-ref HEAD && git log --oneline -1
```

```
grep -n "FindingsRemediation\|REMEDIATION_CONTRACT_VERSION" infra/lib/ztie-hub-tracking-stack.ts
```
Expect hits for the new `FindingsRemediation` Lambda + the env pin
(`REMEDIATION_CONTRACT_VERSION`). Confirm there is **NO** new Bedrock grant for it (3.4 is
PURE):

```
grep -n "InvokeNovaProForScoring\|InvokeNovaProOnly\|hub_remediate" infra/lib/ztie-hub-tracking-stack.ts
```
Expect the Bedrock-grant Sids only for the 3.2 correlator + 3.3 scorer (NOT tied to
`hub_remediate` / `FindingsRemediation`). If `FindingsRemediation` is ABSENT, the checkout
is stale — re-run the checkout.

---

## STEP 2 (Hub tab) — redeploy the Hub tracking stack (ships the new 3.4 Lambda)

```
cd ~/ZTIE-Issues/infra && npm ci
```

```
cd ~/ZTIE-Issues/infra && npx cdk deploy ZtieHubTrackingStack --require-approval never
```
Expect `✅ ZtieHubTrackingStack` with the `FindingsRemediationName` output.

### Post-deploy live verify (do NOT trust the green line alone)

```
REM=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='FindingsRemediationName'].OutputValue" --output text) ; aws lambda get-function-configuration --function-name "$REM" --region us-east-1 --query "Environment.Variables"
```
Expect `REMEDIATION_CONTRACT_VERSION` = `1.0`, `TRACKING_TABLE` set, `LOG_LEVEL` = `INFO`.
(There is deliberately NO `NOVA_MODEL_ID` here — 3.4 is PURE.)

Confirm the 3.4 Lambda has **NO Bedrock grant** (RD-039 PURE) — only DynamoDB:

```
REM=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='FindingsRemediationName'].OutputValue" --output text) ; ROLE=$(aws lambda get-function-configuration --function-name "$REM" --region us-east-1 --query Role --output text | awk -F/ '{print $NF}') ; for P in $(aws iam list-role-policies --role-name "$ROLE" --query "PolicyNames" --output text); do aws iam get-role-policy --role-name "$ROLE" --policy-name "$P" --query "PolicyDocument.Statement[].Action" --output json; done
```
Expect only `dynamodb:*` actions (GetItem / UpdateItem / etc.) — **NO `bedrock:InvokeModel`**.

---

## STEP 3 (Forensic tab) — submit ONE routable artifact so the full pipeline runs

> Use an artifact routing to BOTH lanes (a small CloudFormation template) so 3.1 reaches
> `complete`, 3.2 correlates, and 3.3 records a `scoring_result` — the input 3.4 assesses.
> This is also the OD-001/OD-002 regression proof (the whole pipeline must run green).

```
aws sts get-caller-identity
```
**Run in: Forensic (360999005254), us-east-1, no --profile.** Expect `360999005254`.

```
pip install awscurl >/dev/null 2>&1 ; python3 -c "import base64,json; tpl=b'AWSTemplateFormatVersion: \'2010-09-09\'\nResources:\n  B:\n    Type: AWS::S3::Bucket\n'; b=base64.b64encode(tpl).decode(); open('/tmp/intake.json','w').write(json.dumps({'filename':'probe.yaml','content_type':'text/yaml','submitter':'story-3.4-live','content_base64':b}))"
```
(A minimal CloudFormation template — an S3 bucket — gives the static lane findings and is
routable to both lanes. The intake API wants the JSON envelope, URL LAST, `-d @file`.)

```
ENDPOINT=$(aws cloudformation describe-stacks --stack-name ZtieIntakeStack --region us-east-1 --query "Stacks[0].Outputs[?contains(OutputValue,'/intake')].OutputValue | [0]" --output text) ; echo "$ENDPOINT"
```

```
awscurl --service execute-api --region us-east-1 -X POST -H 'Content-Type: application/json' -d @/tmp/intake.json "$ENDPOINT"
```
**Record the returned `intake_id`** (call it `IID`). (`$ENDPOINT` already ends in `/intake`
— do NOT append another.)

### STEP 3b — nudging a REUSED complete item (Hub tab, optional)

The 3.4 stream mapping starts at `LATEST`, so if you reuse an intake whose `scoring_result`
settled before the redeploy, nudge it (a no-op touch that does not change the evidence — the
fingerprint guard still fires once):

```
TABLE=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='TrackingTableName'].OutputValue" --output text) ; IID=<paste-a-scored-intake_id> ; aws dynamodb update-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --update-expression "SET remediation_touch = :t" --expression-attribute-values "{\":t\":{\"S\":\"story-3.4-live\"}}" --region us-east-1
```

---

## STEP 4 (Hub tab) — confirm ONE verdict-free `remediation_result`

Give the lanes + 3.1 + 3.2 + 3.3 + the stream a few minutes (3.2/3.3 make real Nova Pro
calls), then read the tracking item (Hub tab):

```
aws sts get-caller-identity
```
Expect `641628980935`.

```
TABLE=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='TrackingTableName'].OutputValue" --output text) ; IID=<paste-the-intake_id> ; aws dynamodb get-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --region us-east-1 --query "Item.remediation_result" --output json
```

**Pass criteria (all must hold):**
1. A `remediation_result` object is present on the item (the 3.4 Lambda fired off the
   stream after the `scoring_result` was ready), `status` = `assessed`, with
   `rubric_version` carried through and `contract_version` = `1.0`.
2. **`assessment` present** with:
   - `scores` echoing the three 3.3 scores (each with its honest `status`; `score` present
     when `scored`) + `highest_score` / `highest_score_kind`.
   - `detailed_findings[]` — the 3.2 correlation findings surfaced (may be empty if the
     correlation carried none — that is honest; then the migrated lists are also empty).
   - **`candidate_false_positives[]`** — present when the correlation had `static_only`
     findings (the migrated list).
   - **`gaps[]`** — present when there are `static_only` / `dynamic_only` / `contradiction`
     findings, or a `coverage` gap if `combined_complete` was false (the migrated list).
   - **`prioritized_remediations[]`** — ranked highest-risk-first, `rank` 1..N contiguous,
     each with a `priority` band + an actionable `action` string + a `basis` note. (An
     empty list is valid only when there were no findings AND no gaps.)
3. **Ranked by risk.** The highest-`priority` remediation should correspond to the
   highest-risk finding/gap (cross-check its `basis` cites the highest score / severity).
   A PARTIAL `scoring_result` (a lane `model_error` etc.) is tolerated — ranking falls back
   to severity honestly (the `basis` says "no risk score available" when no lane scored).
4. **No verdict anywhere.** Confirm with a grep of the whole item:

```
aws dynamodb get-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --region us-east-1 --output json | grep -Ei "verdict|safe|approved|forward|malicious|pass_fail|\"clean\"" || echo "NO verdict-shaped key present (expected)"
```
Expect `NO verdict-shaped key present (expected)`. (A stray hit inside a model-produced
`rationale` string carried through from 3.2/3.3 prose is acceptable — confirm there is no
verdict/safe/approved/forward FIELD; a remediation `action` never says reject/forward.)

5. **Assessed once + no stream loop** — read the 3.4 Lambda's logs (custom log group):

```
REM=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='FindingsRemediationName'].OutputValue" --output text) ; LG=$(aws lambda get-function-configuration --function-name "$REM" --region us-east-1 --query "LoggingConfig.LogGroup" --output text) ; aws logs tail "$LG" --region us-east-1 --since 20m --format short | grep -Ei "remediation recorded|already assessed|no scoring_result|not present" | tail -30
```
Expect ONE `remediation recorded (status=assessed, findings=…, gaps=…, remediations=…)`
line for the settled evidence, then `already assessed for this evidence fingerprint; no-op
(guard)` on subsequent stream events — NOT an unbounded re-assessment loop.

6. **Regression proof (DoD #4):** the fact that a `scoring_result` (and before it a
   `combined_event` + `correlation_result`) landed means the FULL pipeline
   (intake→static+dynamic lanes→3.1→3.2→3.3→3.4) ran green AFTER the OD-001/OD-002 cleanup.
   Confirm the earlier stages are present:

```
aws dynamodb get-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --region us-east-1 --query "keys(Item)" --output json
```
Expect the item to carry `combined_event`, `correlation_result`, `scoring_result`, AND
`remediation_result`. If any earlier stage is MISSING with an infra-shaped error in that
Lambda's logs (missing role / bucket / VPC endpoint / export), treat it as possible cleanup
fallout — check whether a deleted stack was a hidden dependency — before assuming a 3.4 bug.

### If `remediation_result.status` is `no_scores` / `skipped_no_evidence`

- `no_scores` → the `scoring_result` (3.3) had not landed when 3.4 read the item. Give
  3.2 + 3.3 more time (they make real Nova Pro calls), then nudge (STEP 3b) or re-submit.
- `skipped_no_evidence` → a `scoring_result` was present but no lane scored AND there were
  no correlation findings (e.g. all three 3.3 calls failed). Honest, but not a passing 3.4
  run — resolve the upstream scoring first, then re-run.

---

## What to paste back to the executor

- STEP 1: branch + `git log -1` + the `grep FindingsRemediation/REMEDIATION_CONTRACT_VERSION`
  hits + confirmation that `hub_remediate` has NO Bedrock grant.
- STEP 2: the deploy line, the Lambda `Environment.Variables` (no `NOVA_MODEL_ID`), and the
  role's action list (DynamoDB only, no `bedrock:InvokeModel`).
- STEP 3: the `intake_id` (and whether it was a fresh submit or a reused scored item).
- STEP 4: the `remediation_result` JSON (the `assessment` with detailed findings + candidate
  FPs + gaps + the prioritized remediations), the no-verdict grep result, the 3.4 log line
  (`remediation recorded …` + the `already assessed … no-op` line), and the `keys(Item)`
  output showing all four Phase-3 stages present (the regression proof).

On a pass (a verdict-free `remediation_result` with detailed findings + the migrated
candidate-FP/gap lists + a prioritized remediation list, ranked by risk, assessed once, no
verdict, AND the full pipeline green end-to-end) the executor records this verbatim into
RUNBOOK 3.4 detail, flips 3.4 ✅ (paired commit), and clears 3.4 from the Validation Debt
Register (re-opening the gate for 3.5). On any fail, 3.4 stays 🟡 — the executor fixes and
you re-run (fix-then-validate-once).
