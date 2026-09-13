# Story 4.1 — LIVE status-retrieval orchestrator validation runbook (stakeholder) — RD-041

> **This is the ONLY live part of 4.1, and only YOU can do it** (the executor has no
> AWS creds). You REDEPLOY the Hub tracking stack (which now ships the NEW Story 4.1
> `hub_status` / StatusRetrieval Lambda), submit ONE routable artifact so the full pipeline
> runs (intake → both lanes → 3.1 combined event → 3.2 correlation → 3.3 three scores → 3.4
> findings/remediations → 3.5 advisory verdict), then **INVOKE the `hub_status` orchestrator
> for that `intake_id`** and confirm it RETURNS the assembled per-intake **status read-model**
> (`status.contract.v1`) — identity + `overall_stage` + per-stage presence + the three 3.3
> scores + a bounded `findings_summary` + a `recommendation` block surfacing the 3.5
> `recommended_verdict` as **ADVISORY** (`decision: pending`, `advisory: true`) — assembled
> PURELY (no model call), READ-ONLY (nothing written), and surfacing the recommendation
> **without acting on it**. The executor **records your returned output verbatim** into the
> RUNBOOK 4.1 detail. **Nothing is recorded on inference** — paste back exactly what the
> commands print. On a pass the executor flips 4.1 ✅ (paired commit), clears 4.1 from the
> Validation Debt Register, and **4.2 unblocks** (then B.1 per the reorder).
>
> **This run DOUBLES as an end-to-end pipeline pass** (like 3.4/3.5). If the full
> intake→lanes→3.1→3.2→3.3→3.4→3.5 flow runs green AND `hub_status` assembles the view, the
> pipeline is confirmed intact through the Phase-4 opener. If an infra-shaped failure appears
> (missing role / bucket / VPC endpoint / export), check whether it is fallout from the earlier
> OD-001/OD-002 cleanup BEFORE assuming it is a 4.1 bug.

## What 4.1 is (RD-041 — so the check is meaningful)

4.1 OPENS Phase 4. It is the **status-retrieval orchestrator**: for one `intake_id` with the
full Phase-3 record on the Hub tracking item, the `hub_status` Lambda READS the item and
assembles a bounded, DERIVED per-intake **status read-model** (`status.contract.v1`, own pin
`STATUS_CONTRACT_VERSION`) it RETURNS as its response:

- **`overall_stage`** — the furthest pipeline stage reached (received / classified / collected
  / correlated / scored / assessed / **recommended**), reported honestly from which derived
  fields are present.
- **`stages`** — per-stage presence (`present`/`absent`) for 3.1 `combined_event` / 3.2
  `correlation` / 3.3 `scoring` / 3.4 `remediation` / 3.5 `verdict_recommendation` (named so it
  is never mistaken for an effective-verdict field).
- **`scores`** — the three 3.3 lane scores (static / dynamic / combined) echoed as CONTEXT,
  never re-blended.
- **`findings_summary`** — the 3.4 `status` + by-category counts + `highest_gap_severity` +
  `contradiction_present`. NOT the full findings text.
- **`recommendation`** — the 3.5 `recommended_verdict` echoed **ADVISORY** + `decision: pending`
  + an explicit `advisory: true` flag (+ the 3.5 `summary` / `rubric_version` when present).

**CONTRACT-FIRST decision (RD-041): 4.1 is an ON-DEMAND READ/transform** — NOT a durable stored
record and NOT a stream consumer. So the `hub_status` Lambda:
- makes **NO model call** (like 3.4/3.5 — **NO Bedrock client, NO Bedrock grant**),
- **WRITES nothing** (READ-only `dynamodb:GetItem`; there is no `put_*` in its seam by design),
- has **NO DynamoDB-stream event source** (unlike every Phase-3 Lambda) — it is invoked **on
  demand, per intake**.

**There is NO Bedrock/Nova Pro prerequisite for 4.1 itself** (Nova Pro is still needed UPSTREAM
so 3.2 + 3.3 land their inputs). **CRUCIAL: the 3.5 recommendation stays ADVISORY.** 4.1
surfaces it; it NEVER routes / promotes / enforces, NEVER writes a verdict onto any record, and
reports `decision: pending`. The 3.1-3.4 records stay verdict-free. Nothing new crosses
Forensic→Hub — the view never leaves the Hub except as this Lambda's response to a Hub-side
caller.

## Ground rules (these have bitten us every session)

- **TWO accounts → TWO CloudShell tabs.** The artifact + lanes + ephemeral host are in
  **Forensic (360999005254)**; the tracking table + the `hub_status` Lambda + the read-model you
  verify are all in the **Hub (641628980935)**. Deploy the Hub stack + invoke `hub_status` from a
  **Hub-authed** shell; submit the artifact from a **Forensic-authed** shell.
- **Run `aws sts get-caller-identity` BEFORE every block** and read `Account`. A
  `ResourceNotFoundException` on the tracking table means you queried it from Forensic; it lives
  in the Hub. A `403` on the intake submit means you ran it from the Hub; submit from Forensic.
- **Feed commands ONE LINE AT A TIME.** Never paste a multi-line block. A multi-line `python -c`
  with embedded newlines in a `b'...'` literal breaks ("unterminated string literal") — the
  intake-build one-liner below uses `chr()` concatenation to avoid that.
- **`/tmp` + shell vars are WIPED when CloudShell recycles.** Re-set every variable in the SAME
  block right before using it, and re-`pip install awscurl` before an intake submit.
- **Region us-east-1**, ambient creds (**no `--profile`**).
- **The `hub_status` Lambda uses a CUSTOM log group** (OD-003 explicit LogGroup), so
  `aws logs tail /aws/lambda/<fn>` fails `ResourceNotFoundException`. Tail the real group from
  `LoggingConfig.LogGroup` if you need logs.
- **Use a ROUTABLE artifact** (a small CloudFormation template with an S3 bucket) so both lanes
  run, 3.1 reaches `complete`, and 3.2 + 3.3 + 3.4 + 3.5 land — otherwise the read-model's
  `overall_stage` will not reach `recommended`. A trivial file (`/etc/hostname`) classifies
  `other_unknown` → `SAFE_REJECTED`.
- **Endpoint query returns TWO outputs** (`IntakeApi…` + `…Endpoint`) joined by a tab, which
  breaks SigV4 — pin exactly one URL with the `[?contains(...)] | [0]` query (STEP 3).
- **Reads are eventually-consistent** right after a write — re-read after a moment.

---

## STEP 0 (Hub tab) — no Bedrock prerequisite for 4.1 (but 3.2/3.3 need it upstream)

> 4.1 makes NO model call (RD-041), so it needs no Bedrock access itself. But its read-model is
> most meaningful over a COMPLETE Phase-3 record, which needs Nova Pro enabled for the Hub
> account (as in the 3.2/3.3/3.5 live runs). If your artifact does not produce a
> `scoring_result` / `verdict_result`, confirm Nova Pro access exactly as the 3.3 LIVE-RUNBOOK
> STEP 0 describes.

```
aws sts get-caller-identity
```
**Run in: Hub (641628980935), us-east-1, no --profile.** Expect `"Account": "641628980935"`.

---

## STEP 1 (Hub tab) — get the 4.1 code + prove the checkout carries it

> **Deploy-gap guard:** a `cdk deploy` prints `✅ UPDATE_COMPLETE` even on the WRONG branch —
> it just re-synthesizes STALE code. BEFORE deploying, prove the checkout carries the RD-041
> code; AFTER deploying, inspect the LIVE Lambda. Never trust the green line.

```
cd ~/ZTIE-Issues && git fetch origin -q && git checkout feature/story-4.1 && git reset --hard origin/feature/story-4.1
```
(If the 4.1 PR is already merged, use `git checkout main && git reset --hard origin/main`.)

```
git rev-parse --abbrev-ref HEAD && git log --oneline -1
```

```
grep -n "StatusRetrieval\|STATUS_CONTRACT_VERSION\|hub_status" infra/lib/ztie-hub-tracking-stack.ts
```
Expect hits for the new `StatusRetrieval` Lambda + the env pin (`STATUS_CONTRACT_VERSION`) + the
`hub_status` asset dir. Confirm there is **NO** new Bedrock grant and **NO** stream event source
tied to it (4.1 is PURE + on-demand):

```
grep -n "statusFn\|StatusRetrieval\|grantReadData(statusFn)\|addEventSource" infra/lib/ztie-hub-tracking-stack.ts
```
Expect `grantReadData(statusFn)` (READ-only) and NO `statusFn.addEventSource(...)` (4.1 is NOT
stream-triggered). If `StatusRetrieval` is ABSENT, the checkout is stale — re-run the checkout.

---

## STEP 2 (Hub tab) — redeploy the Hub tracking stack (ships the new 4.1 Lambda)

```
cd ~/ZTIE-Issues/infra && npm ci
```

```
cd ~/ZTIE-Issues/infra && npx cdk deploy ZtieHubTrackingStack --require-approval never
```
Expect `✅ ZtieHubTrackingStack` with the `StatusRetrievalName` output.

### Post-deploy live verify (do NOT trust the green line alone)

```
SR=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='StatusRetrievalName'].OutputValue" --output text) ; aws lambda get-function-configuration --function-name "$SR" --region us-east-1 --query "Environment.Variables"
```
Expect `STATUS_CONTRACT_VERSION` = `1.0`, `TRACKING_TABLE` set, `LOG_LEVEL` = `INFO`.
(There is deliberately NO `NOVA_MODEL_ID` here — 4.1 is PURE.)

Confirm the 4.1 Lambda has **NO Bedrock grant** (RD-041 PURE) and is **READ-only** on the table —
only `dynamodb:GetItem`-class actions, NO `UpdateItem`/`PutItem`:

```
SR=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='StatusRetrievalName'].OutputValue" --output text) ; ROLE=$(aws lambda get-function-configuration --function-name "$SR" --region us-east-1 --query Role --output text | awk -F/ '{print $NF}') ; for P in $(aws iam list-role-policies --role-name "$ROLE" --query "PolicyNames" --output text); do aws iam get-role-policy --role-name "$ROLE" --policy-name "$P" --query "PolicyDocument.Statement[].Action" --output json; done
```
Expect only READ `dynamodb:*` actions (GetItem / Query / BatchGetItem / etc.) — **NO
`dynamodb:UpdateItem`/`PutItem`/`DeleteItem`, NO `bedrock:InvokeModel`**.

---

## STEP 3 (Forensic tab) — submit ONE routable artifact so the full pipeline runs

> Use an artifact routing to BOTH lanes (a small CloudFormation template) so 3.1 reaches
> `complete`, 3.2 correlates, 3.3 records a `scoring_result`, 3.4 records a `remediation_result`,
> and 3.5 records a `verdict_result` — so the read-model's `overall_stage` reaches `recommended`.

```
aws sts get-caller-identity
```
**Run in: Forensic (360999005254), us-east-1, no --profile.** Expect `360999005254`.

```
pip install awscurl >/dev/null 2>&1 ; python3 -c "import base64,json; nl=chr(10); q=chr(39); tpl=('AWSTemplateFormatVersion: '+q+'2010-09-09'+q+nl+'Resources:'+nl+'  B:'+nl+'    Type: AWS::S3::Bucket'+nl).encode(); b=base64.b64encode(tpl).decode(); open('/tmp/intake.json','w').write(json.dumps({'filename':'probe.yaml','content_type':'text/yaml','submitter':'story-4.1-live','content_base64':b}))"
```
(A minimal CloudFormation template — an S3 bucket — gives the static lane findings and is
routable to both lanes. The intake API wants the JSON envelope, URL LAST, `-d @file`.)

```
ENDPOINT=$(aws cloudformation describe-stacks --stack-name ZtieIntakeStack --region us-east-1 --query "Stacks[0].Outputs[?contains(OutputValue,'/intake')].OutputValue | [0]" --output text) ; echo "$ENDPOINT"
```

```
awscurl --service execute-api --region us-east-1 -X POST -H 'Content-Type: application/json' -d @/tmp/intake.json "$ENDPOINT"
```
**Record the returned `intake_id`** (call it `IID`). (`$ENDPOINT` already ends in `/intake` — do
NOT append another.)

> **Reusing an existing intake is fine.** Because 4.1 is invoked ON DEMAND (not stream-triggered),
> you may skip the submit and just invoke `hub_status` for ANY `intake_id` that already carries a
> full Phase-3 record (e.g. the 3.5 live-run intake `0c74042e-6976-4fdf-a39c-7599f9733921`). Give
> a fresh submit a few minutes for 3.2/3.3 (real Nova Pro calls) + 3.4 + 3.5 to land first.

---

## STEP 4 (Hub tab) — INVOKE the `hub_status` orchestrator + confirm the read-model

Give the lanes + 3.1 + 3.2 + 3.3 + 3.4 + 3.5 a few minutes, then invoke `hub_status` for the
intake (Hub tab):

```
aws sts get-caller-identity
```
Expect `641628980935`.

```
SR=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='StatusRetrievalName'].OutputValue" --output text) ; IID=<paste-the-intake_id> ; aws lambda invoke --function-name "$SR" --payload "{\"intake_id\":\"$IID\"}" --cli-binary-format raw-in-base64-out --region us-east-1 /tmp/status.json >/dev/null ; cat /tmp/status.json | python3 -m json.tool
```

**Pass criteria (all must hold):**
1. The invoke returns the **status read-model** (NOT an `error` envelope): top-level
   `contract_version` = `1.0`, `intake_id` = `IID`, a 64-hex `sha256`, an `assembled_at`
   Z-timestamp, plus `overall_stage`, `stages`, and `recommendation`.
2. **`overall_stage` = `recommended`** for a fully-processed intake (all five Phase-3 fields
   present), and **`stages`** shows `present` for `combined_event` / `correlation` / `scoring` /
   `remediation` / `verdict_recommendation`. (If you invoked before 3.5 landed, `overall_stage`
   will honestly be an earlier stage — re-invoke once the pipeline finishes.)
3. **`scores`** echoes the three 3.3 lane scores (static / dynamic / combined) matching the
   item's `scoring_result` (context echo, NOT re-blended); **`findings_summary`** echoes the 3.4
   `status` + counts + `highest_gap_severity` + `contradiction_present`.
4. **`recommendation`** carries the 3.5 `recommended_verdict` (∈ PASS/FAIL/INCONCLUSIVE) matching
   the item's `verdict_result.recommended_verdict`, with **`decision` = `pending`** and
   **`advisory` = `true`**. The recommendation is SURFACED, never acted upon.
5. **READ-ONLY — nothing written.** Re-read the tracking item and confirm 4.1 added NO field
   (there is NO `status_result` / `status_read_model` / `assembled_at` ON THE ITEM — 4.1 returns
   the view, it does not persist it), and the tracking `status` + the 3.1-3.5 records are
   UNCHANGED by the invoke:

```
TABLE=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='TrackingTableName'].OutputValue" --output text) ; IID=<paste-the-intake_id> ; aws dynamodb get-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --region us-east-1 --query "keys(Item)" --output json
```
Expect the SAME attribute set as before the invoke (e.g. `intake_id`, `sha256`, `status`,
`received_at`, `combined_event`, `correlation_result`, `scoring_result`, `remediation_result`,
`verdict_result`, `verdict_at`, …) — and NO new 4.1-written attribute.

6. **No effective-verdict field in the view.** The read-model must carry the ADVISORY
   `recommended_verdict` but NEVER a bare effective verdict:

```
cat /tmp/status.json | python3 -c "import sys,json; d=json.load(sys.stdin); banned={'verdict','safe','approved','forward','malicious','pass_fail','clean'}; import json as j; s=j.dumps(d); print('FAIL: banned key present' if any(('\"'+k+'\"') in s for k in banned) else 'OK: no effective-verdict key (only advisory recommended_verdict)')"
```
Expect `OK: no effective-verdict key`.

7. **Error paths are clean (optional but recommended).** Invoke with a non-existent intake and a
   malformed id and confirm bounded error envelopes (not a crash):

```
SR=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='StatusRetrievalName'].OutputValue" --output text) ; aws lambda invoke --function-name "$SR" --payload "{\"intake_id\":\"00000000-0000-4000-8000-000000000000\"}" --cli-binary-format raw-in-base64-out --region us-east-1 /tmp/nf.json >/dev/null ; cat /tmp/nf.json
```
Expect `{"error": {"code": 404, ...}}`.

```
SR=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='StatusRetrievalName'].OutputValue" --output text) ; aws lambda invoke --function-name "$SR" --payload "{\"intake_id\":\"not-a-uuid\"}" --cli-binary-format raw-in-base64-out --region us-east-1 /tmp/bad.json >/dev/null ; cat /tmp/bad.json
```
Expect `{"error": {"code": 400, ...}}`.

---

## STEP 5 — paste back for the record

Paste back, VERBATIM:
- the `sts get-caller-identity` account for each tab,
- the `git log --oneline -1` line + the STEP 1 greps,
- the STEP 2 post-deploy env + role-policy output (proving PURE + READ-only),
- the STEP 3 `intake_id` (or the reused one),
- the STEP 4 full `/tmp/status.json` read-model, the `keys(Item)` before/after, the
  no-banned-key line, and the two error-path envelopes.

The executor records these verbatim into the RUNBOOK 4.1 detail, flips **4.1 → ✅** (paired
commit), clears 4.1 from the Validation Debt Register, and authors the **4.2** (dashboard JSON
payload) handoff. On a FAIL, 4.1 stays 🟡 (already on the register); the executor fixes +
re-validates once (fix-then-validate-once), never marking done on inference.

## If something fails

- **`overall_stage` is not `recommended`** — the pipeline has not finished for this intake. Wait
  a few minutes (3.2/3.3 are real Nova Pro calls) and re-invoke; check the item actually carries
  `scoring_result` + `verdict_result`. This is upstream latency, not a 4.1 bug.
- **`error.code: 404`** on your real intake — the tracking record is not there yet (submit not
  landed / wrong account). Confirm you are in the Hub and the `intake_id` is correct.
- **`error.code: 422`** — the tracking record is missing its `sha256` integrity key (a malformed
  item). Note it; this is an upstream data problem, not a 4.1 bug (4.1 correctly refuses to
  assemble a view over a record it cannot integrity-key).
- **A new 4.1-written attribute appears on the item** — that would be a real 4.1 defect (4.1 must
  be READ-only). Capture it; the executor keeps 4.1 🟡 and fixes.
- **Infra-shaped failure** (missing role / bucket / VPC endpoint / export) — check whether it is
  OD-001/OD-002 cleanup fallout BEFORE assuming it is a 4.1 bug; the earlier stories' LIVE-RUNBOOKs
  list the affected resources.
