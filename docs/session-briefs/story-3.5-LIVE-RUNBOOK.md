# Story 3.5 — LIVE advisory recommended-verdict validation runbook (stakeholder) — RD-040

> **This is the ONLY live part of 3.5, and only YOU can do it** (the executor has no
> AWS creds). You REDEPLOY the Hub tracking stack (which now ships the NEW Story 3.5
> `hub_verdict` Lambda), submit ONE routable artifact so the full pipeline runs
> (intake → both lanes → 3.1 combined event → 3.2 correlation → 3.3 three scores → 3.4
> findings/remediations), and confirm that ONE **advisory** `verdict_result` — carrying a
> `recommended_verdict` (PASS / FAIL / INCONCLUSIVE) + a `recommendation_basis` + an
> explicit `human_decision: pending` — was recorded onto the SAME Hub tracking record,
> PURELY (no model call), and is **NEVER acted upon**. The executor **records your
> returned output verbatim** into the RUNBOOK 3.5 detail. **Nothing is recorded on
> inference** — paste back exactly what the commands print. On a pass the executor flips
> 3.5 ✅ (paired commit), clears 3.5 from the Validation Debt Register, and **Phase 3
> CLOSES** (4.1 unblocks).
>
> **This run DOUBLES as an end-to-end pipeline pass** (like 3.4's). If the full
> intake→lanes→3.1→3.2→3.3→3.4→3.5 flow runs green, the pipeline is confirmed intact. If
> an infra-shaped failure appears (missing role / bucket / VPC endpoint / export), check
> whether it is fallout from the earlier OD-001/OD-002 cleanup BEFORE assuming it is a 3.5
> bug.

## What 3.5 is (RD-040 — so the check is meaningful)

3.5 is the verdict step of Phase 3 — the FIRST record that legitimately carries a
verdict-shaped field. It reads the 3.3 `scoring_result` (three 0-100 risk scores: static /
dynamic / combined) AND the 3.4 `remediation_result` (findings + gaps) ALREADY on the Hub
tracking item and DETERMINISTICALLY maps them to an **advisory** `verdict_result`:

- **`recommended_verdict`** ∈ {PASS, FAIL, INCONCLUSIVE}, driven by the **`combined`**
  score (NOT a re-aggregation of the three lane scores): `combined ≤ 29` → PASS,
  `30-74` → INCONCLUSIVE, `≥ 75` → FAIL.
- **Forced INCONCLUSIVE** regardless of the score on a `contradiction` finding OR any
  incompleteness (a `coverage` gap / `combined_complete=false` / a partial `scoring_result`
  — any lane not `scored` / `combined` itself not `scored` / `remediation_result.status !=
  assessed`). A high-severity gap → INCONCLUSIVE (a human look), NEVER an auto-FAIL.
- **`recommendation_basis`** — the combined score + the driver + the static/dynamic scores
  as CONTEXT + a plain-language `summary`.
- **`human_decision: pending`** — ALWAYS. 3.5 NEVER writes the human's actual selection.

**CONTRACT-FIRST decision (RD-040): 3.5 is PURE Hub-side post-processing — it makes NO
model call** (its inputs are already structured + the mapping is deterministic). So — like
3.4 and UNLIKE the 3.2 correlator + the 3.3 scorer — the `hub_verdict` Lambda has **NO
Bedrock client and NO Bedrock grant**. **There is NO Bedrock/Nova Pro prerequisite for 3.5
itself** (Nova Pro is still needed UPSTREAM so 3.2 + 3.3 land their inputs).

**CRUCIAL: the `recommended_verdict` is ADVISORY and is NEVER acted upon.** Nothing in ZTIE
routes / promotes / destroys / moves an artifact based on it. The Phase-4 routing is driven
SOLELY by a HUMAN actively selecting PASS or FAIL on the dashboard. The advisory field is
named `recommended_verdict` (not a bare `verdict`) so nothing mistakes it for the effective
decision, and 3.5 writes it to its OWN new fields (`verdict_result` / `verdict_at`) — it
NEVER touches `status` or the 3.1-3.4 records (which stay verdict-free). Nothing new crosses
Forensic→Hub.

## Ground rules (these have bitten us every session)

- **TWO accounts → TWO CloudShell tabs.** The artifact + lanes + ephemeral host are in
  **Forensic (360999005254)**; the tracking table + stream + the `hub_verdict` Lambda +
  the `verdict_result` you verify are all in the **Hub (641628980935)**. Deploy the Hub
  stack + verify from a **Hub-authed** shell; submit the artifact from a **Forensic-authed**
  shell.
- **Run `aws sts get-caller-identity` BEFORE every block** and read `Account`. A
  `ResourceNotFoundException` on the tracking table means you queried it from Forensic; it
  lives in the Hub.
- **Feed commands ONE LINE AT A TIME.** Never paste a multi-line block.
- **`/tmp` + shell vars are WIPED when CloudShell recycles.** Re-set every variable in the
  SAME block right before using it, and re-`pip install awscurl` before an intake submit.
- **Region us-east-1**, ambient creds (**no `--profile`**).
- **The `hub_verdict` Lambda uses a CUSTOM log group** (OD-003 explicit LogGroup), so
  `aws logs tail /aws/lambda/<fn>` fails `ResourceNotFoundException`. Tail the real group
  from `LoggingConfig.LogGroup` (see STEP 4).
- **Use a ROUTABLE artifact** (a small CloudFormation template with an S3 bucket) so both
  lanes run, 3.1 reaches `complete`, and 3.2 + 3.3 + 3.4 land — otherwise 3.5 has nothing to
  recommend over. A trivial file (`/etc/hostname`) classifies `other_unknown` →
  `SAFE_REJECTED`.
- **Endpoint query returns TWO outputs** (`IntakeApi…` + `…Endpoint`) joined by a tab,
  which breaks SigV4 — pin exactly one URL (see STEP 3).
- **Reads are eventually-consistent** right after a write — re-read after a moment.

---

## STEP 0 (Hub tab) — no Bedrock prerequisite for 3.5 (but 3.2/3.3 need it upstream)

> 3.5 makes NO model call (RD-040 PURE), so it needs no Bedrock access itself. But it
> recommends over the 3.3 `scoring_result`, which needs Nova Pro enabled for the Hub account
> (as in the 3.2/3.3 live runs). If your artifact does not produce a `scoring_result`,
> confirm Nova Pro access exactly as the 3.3 LIVE-RUNBOOK STEP 0 describes.

```
aws sts get-caller-identity
```
**Run in: Hub (641628980935), us-east-1, no --profile.** Expect `"Account": "641628980935"`.

---

## STEP 1 (Hub tab) — get the 3.5 code + prove the checkout carries it

> **Deploy-gap guard:** a `cdk deploy` prints `✅ UPDATE_COMPLETE` even on the WRONG
> branch — it just re-synthesizes STALE code. BEFORE deploying, prove the checkout carries
> the RD-040 code; AFTER deploying, inspect the LIVE Lambda. Never trust the green line.

```
cd ~/ZTIE-Issues && git fetch origin -q && git checkout feature/story-3.5 && git reset --hard origin/feature/story-3.5
```
(If the 3.5 PR is already merged, use `git checkout main && git reset --hard origin/main`.)

```
git rev-parse --abbrev-ref HEAD && git log --oneline -1
```

```
grep -n "VerdictRecommendation\|VERDICT_CONTRACT_VERSION" infra/lib/ztie-hub-tracking-stack.ts
```
Expect hits for the new `VerdictRecommendation` Lambda + the env pin
(`VERDICT_CONTRACT_VERSION`). Confirm there is **NO** new Bedrock grant for it (3.5 is
PURE):

```
grep -n "InvokeNovaPro\|hub_verdict\|VerdictRecommendation" infra/lib/ztie-hub-tracking-stack.ts
```
Expect the Bedrock-grant Sids only for the 3.2 correlator + 3.3 scorer (NOT tied to
`hub_verdict` / `VerdictRecommendation`). If `VerdictRecommendation` is ABSENT, the checkout
is stale — re-run the checkout.

---

## STEP 2 (Hub tab) — redeploy the Hub tracking stack (ships the new 3.5 Lambda)

```
cd ~/ZTIE-Issues/infra && npm ci
```

```
cd ~/ZTIE-Issues/infra && npx cdk deploy ZtieHubTrackingStack --require-approval never
```
Expect `✅ ZtieHubTrackingStack` with the `VerdictRecommendationName` output.

### Post-deploy live verify (do NOT trust the green line alone)

```
VER=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='VerdictRecommendationName'].OutputValue" --output text) ; aws lambda get-function-configuration --function-name "$VER" --region us-east-1 --query "Environment.Variables"
```
Expect `VERDICT_CONTRACT_VERSION` = `1.0`, `TRACKING_TABLE` set, `LOG_LEVEL` = `INFO`.
(There is deliberately NO `NOVA_MODEL_ID` here — 3.5 is PURE.)

Confirm the 3.5 Lambda has **NO Bedrock grant** (RD-040 PURE) — only DynamoDB:

```
VER=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='VerdictRecommendationName'].OutputValue" --output text) ; ROLE=$(aws lambda get-function-configuration --function-name "$VER" --region us-east-1 --query Role --output text | awk -F/ '{print $NF}') ; for P in $(aws iam list-role-policies --role-name "$ROLE" --query "PolicyNames" --output text); do aws iam get-role-policy --role-name "$ROLE" --policy-name "$P" --query "PolicyDocument.Statement[].Action" --output json; done
```
Expect only `dynamodb:*` actions (GetItem / UpdateItem / etc.) — **NO `bedrock:InvokeModel`**.

---

## STEP 3 (Forensic tab) — submit ONE routable artifact so the full pipeline runs

> Use an artifact routing to BOTH lanes (a small CloudFormation template) so 3.1 reaches
> `complete`, 3.2 correlates, 3.3 records a `scoring_result`, and 3.4 records a
> `remediation_result` — the inputs 3.5 recommends over.

```
aws sts get-caller-identity
```
**Run in: Forensic (360999005254), us-east-1, no --profile.** Expect `360999005254`.

```
pip install awscurl >/dev/null 2>&1 ; python3 -c "import base64,json; tpl=b'AWSTemplateFormatVersion: \'2010-09-09\'\nResources:\n  B:\n    Type: AWS::S3::Bucket\n'; b=base64.b64encode(tpl).decode(); open('/tmp/intake.json','w').write(json.dumps({'filename':'probe.yaml','content_type':'text/yaml','submitter':'story-3.5-live','content_base64':b}))"
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

### STEP 3b — nudging a REUSED item that already has scoring + remediation (Hub tab, optional)

The 3.5 stream mapping starts at `LATEST`, so if you reuse an intake whose `scoring_result`
+ `remediation_result` settled before the redeploy, nudge it (a no-op touch that does not
change the evidence — the fingerprint guard still fires once):

```
TABLE=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='TrackingTableName'].OutputValue" --output text) ; IID=<paste-a-scored+assessed-intake_id> ; aws dynamodb update-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --update-expression "SET verdict_touch = :t" --expression-attribute-values "{\":t\":{\"S\":\"story-3.5-live\"}}" --region us-east-1
```

---

## STEP 4 (Hub tab) — confirm ONE advisory `verdict_result`

Give the lanes + 3.1 + 3.2 + 3.3 + 3.4 + the stream a few minutes (3.2/3.3 make real Nova
Pro calls), then read the tracking item (Hub tab):

```
aws sts get-caller-identity
```
Expect `641628980935`.

```
TABLE=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='TrackingTableName'].OutputValue" --output text) ; IID=<paste-the-intake_id> ; aws dynamodb get-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --region us-east-1 --query "Item.verdict_result" --output json
```

**Pass criteria (all must hold):**
1. A `verdict_result` object is present on the item (the 3.5 Lambda fired off the stream
   after the `scoring_result` was ready), `status` ∈ {`recommended`, `incomplete`,
   `no_scores`}, with `contract_version` = `1.0` and `rubric_version` carried through.
2. **`recommended_verdict`** is present and ∈ {PASS, FAIL, INCONCLUSIVE}, matching the
   RD-040 mapping over the actual `combined` score:
   - `combined ≤ 29` → PASS; `30-74` → INCONCLUSIVE; `≥ 75` → FAIL;
   - OR forced **INCONCLUSIVE** if a `contradiction` finding is present or the evidence is
     incomplete (partial scoring / coverage gap / combined not scored / remediation not
     assessed). Cross-check `recommendation_basis.driver` (`combined_score` /
     `contradiction_present` / `incomplete_evidence` / `no_score_available`) +
     `recommendation_basis.combined_score` + `override_reasons` explains the result.
3. **`human_decision` = `pending`** (ALWAYS). 3.5 must NOT have written any human
   selection.
4. **Advisory, never acted upon.** The tracking `status` is UNCHANGED by 3.5 (it did not
   route / promote / destroy anything), and the recommendation lives ONLY in
   `verdict_result` / `verdict_at`. Confirm the item's tracking `status` is whatever the
   upstream pipeline set (e.g. `RECEIVED` / a lane status) — NOT a verdict.
5. **Representative-mapping check (DoD).** Ideally confirm BOTH ends of the mapping across
   one or two intakes:
   - a **low-`combined`** intake (or one the scorer rated low) → `recommended_verdict` =
     **PASS**;
   - a **contradiction / incomplete** intake → `recommended_verdict` = **INCONCLUSIVE**.
   (If your single test intake yields only one of these, note the `combined` score + basis;
   a FAIL requires a genuinely high combined score, which a benign probe template usually
   will not produce — that is expected, not a failure of 3.5.)
6. **The 3.1-3.4 records stay verdict-free.** Confirm the OTHER Phase-3 records did NOT gain
   a verdict field (only 3.5's OWN record carries `recommended_verdict`):

```
aws dynamodb get-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --region us-east-1 --query "Item.scoring_result" --output json | grep -Ei "\"verdict\"|recommended_verdict|\"safe\"|approved|pass_fail" || echo "scoring_result has NO verdict field (expected)"
```
```
aws dynamodb get-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --region us-east-1 --query "Item.remediation_result" --output json | grep -Ei "\"verdict\"|recommended_verdict|\"safe\"|approved|pass_fail" || echo "remediation_result has NO verdict field (expected)"
```
Expect both to print the "NO verdict field (expected)" line.

7. **No bare effective-verdict key on 3.5's record either.** 3.5's record carries
   `recommended_verdict` (allowed) but NEVER a bare effective `verdict` / `safe` /
   `approved` / `forward` / `malicious` / `pass_fail` / `clean` key:

```
aws dynamodb get-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --region us-east-1 --query "Item.verdict_result" --output json | grep -Ei "\"verdict\"|\"safe\"|\"approved\"|\"forward\"|\"malicious\"|\"pass_fail\"|\"clean\"" || echo "NO bare effective-verdict key (expected; only recommended_verdict + human_decision:pending)"
```
Expect `NO bare effective-verdict key (expected...)`. (A stray hit inside the model prose
carried through into the basis `summary` is acceptable — confirm there is no effective
verdict FIELD; `recommended_verdict` + `human_decision: pending` are the only verdict-shaped
keys.)

8. **Recommended once + no stream loop** — read the 3.5 Lambda's logs (custom log group):

```
VER=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='VerdictRecommendationName'].OutputValue" --output text) ; LG=$(aws lambda get-function-configuration --function-name "$VER" --region us-east-1 --query "LoggingConfig.LogGroup" --output text) ; aws logs tail "$LG" --region us-east-1 --since 20m --format short | grep -Ei "verdict recorded|already recommended|no scoring_result|not present" | tail -30
```
Expect ONE `verdict recorded (status=…, recommended_verdict=…, human_decision=pending)`
line for the settled evidence, then `already recommended for this evidence fingerprint;
no-op (guard)` on subsequent stream events — NOT an unbounded re-recommendation loop.

9. **End-to-end pipeline green** — confirm the earlier stages are all present:

```
aws dynamodb get-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --region us-east-1 --query "keys(Item)" --output json
```
Expect the item to carry `combined_event`, `correlation_result`, `scoring_result`,
`remediation_result`, AND `verdict_result`. If any earlier stage is MISSING with an
infra-shaped error in that Lambda's logs (missing role / bucket / VPC endpoint / export),
treat it as possible earlier-cleanup fallout before assuming a 3.5 bug.

### If `verdict_result.status` is `no_scores` / the recommendation is unexpectedly INCONCLUSIVE

- `no_scores` → the `scoring_result` (3.3) had not landed when 3.5 read the item. Give
  3.2 + 3.3 more time (they make real Nova Pro calls), then nudge (STEP 3b) or re-submit.
- `incomplete` + INCONCLUSIVE → the evidence was incomplete (read `override_reasons`); this
  is HONEST and a valid 3.5 outcome, not a bug. To see a score-driven PASS/FAIL you need all
  lanes `scored` + `remediation_result.status = assessed` + no contradiction/coverage gap.

---

## What to paste back to the executor

- STEP 1: branch + `git log -1` + the `grep VerdictRecommendation/VERDICT_CONTRACT_VERSION`
  hits + confirmation that `hub_verdict` has NO Bedrock grant.
- STEP 2: the deploy line, the Lambda `Environment.Variables` (no `NOVA_MODEL_ID`), and the
  role's action list (DynamoDB only, no `bedrock:InvokeModel`).
- STEP 3: the `intake_id` (and whether it was a fresh submit or a reused scored+assessed
  item).
- STEP 4: the `verdict_result` JSON (the `recommended_verdict`, the `recommendation_basis`
  incl. `driver` + `combined_score` + `override_reasons`, and `human_decision: pending`),
  the two "3.1-3.4 stay verdict-free" grep results, the "no bare effective-verdict key"
  grep result, the 3.5 log line (`verdict recorded …` + the `already recommended … no-op`
  line), and the `keys(Item)` output showing all five Phase-3 stages present.

On a pass (an advisory `verdict_result` with a `recommended_verdict` per the RD-040 mapping
+ `human_decision: pending`, advisory-only / never acted upon, the 3.1-3.4 records still
verdict-free, recommended once, no stream loop, AND the full pipeline green end-to-end) the
executor records this verbatim into RUNBOOK 3.5 detail, flips 3.5 ✅ (paired commit), clears
3.5 from the Validation Debt Register, and **Phase 3 CLOSES** (4.1 unblocks). On any fail,
3.5 stays 🟡 — the executor fixes and you re-run (fix-then-validate-once).
