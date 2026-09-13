# Story 4.5 — LIVE per-execution-report validation runbook (stakeholder) — RD-045

> **This is the ONLY live part of 4.5, and only YOU can do it** (the executor has no AWS
> creds). You REDEPLOY the Hub tracking stack (which now ships the NEW Story 4.5
> `hub_report` / ReportOrchestrator Lambda), make sure a real intake carries a full
> Phase-3 record, then **INVOKE `hub_report` by `intake_id`** and confirm it RETURNS the
> assembled THREE-TIER report (`report.contract.v1`) — Executive / Security / Developer —
> AND a self-contained HTML render, assembled PURELY (no model call), READ-ONLY (nothing
> written), surfacing the 3.5 recommendation as **ADVISORY** (never acted upon) and marking
> MITRE / Sigma / file-line as `not_carried_on_hub`. The executor **records your returned
> output verbatim** into the RUNBOOK 4.5 detail. **Nothing is recorded on inference.** On a
> pass the executor flips 4.5 ✅ (paired commit), clears 4.5 from the Validation Debt
> Register, and the next Phase-4 pipe work (4.6 / 4.7) unblocks.

## What 4.5 is (RD-045 — so the check is meaningful)

4.5 is the **Phase-4 PER-EXECUTION REPORT** — the human-readable, audience-tiered
counterpart to the dashboard. Its `hub_report` Lambda assembles, on demand by `intake_id`,
a bounded per-intake report (`report.contract.v1`, own pin `REPORT_CONTRACT_VERSION`) in
three tiers + a self-contained inline-CSS HTML render (print-to-PDF for "PDF for humans"):

- **Executive** — the combined risk score + a one-paragraph ADVISORY verdict (built by
  REUSING the 4.1 `status_model.build_status`).
- **Security** — the correlated findings (behavioral chains) + severity roll-ups + gaps
  (from the 3.2 `correlation_result` + the 3.4 `remediation_result` assessment).
- **Developer** — the prioritized remediations (rank / priority / action / basis) +
  candidate false positives + static↔dynamic correlation (from the 3.4 assessment).

**CONTRACT-FIRST decision (RD-045, mirrors RD-041/RD-042): 4.5 is an ON-DEMAND
READ/transform** — NOT a durable stored record and NOT a stream consumer. So the
`hub_report` Lambda:
- makes **NO model call** (like 4.1/4.2 — **NO Bedrock client, NO Bedrock grant**),
- **WRITES nothing** (READ-only `dynamodb:GetItem`; there is no `put_*`/`update_*`/
  `delete_*` and no `Query`/`Scan` in its seam by design — the report is per-intake),
- has **NO DynamoDB-stream event source** — it is invoked **on demand**.

**HONEST BOUNDARY (RD-013):** MITRE ATT&CK technique IDs, Sigma rules, and exact file/line
are raw/Forensic detail NOT carried on the Hub; the report marks them `not_carried_on_hub`
(a placeholder, never fabricated). Widening the crossing to carry them is a SEPARATE
tracked story (4.9, RD-046), not this one. **CRUCIAL (RD-040): the 3.5 recommendation stays
ADVISORY** — the Executive tier surfaces it (`recommended_verdict` + `decision: pending` +
`advisory: true`); it is NEVER acted upon and there is NO bare effective-verdict key. The
HTML render HTML-escapes every derived value. **ServiceNow is OUT OF SCOPE.**

## Ground rules (these have bitten us every session)

- **This is a HUB story (641628980935).** The tracking table + the `hub_report` Lambda +
  the report you verify are all in the **Hub**. (The intake API + lanes are in Forensic —
  only needed to PRODUCE a real intake to report on.)
- **Run `aws sts get-caller-identity` BEFORE every block** and read `Account`. Deploy +
  invoke `hub_report` from a **Hub-authed** shell; submit an artifact (if you need a fresh
  one) from a **Forensic-authed** shell (a `403` on the intake submit means you ran it in
  the Hub).
- **Feed commands ONE LINE AT A TIME.** Never paste a multi-line block.
- **`/tmp` + shell vars are WIPED when CloudShell recycles.** Re-set every variable in the
  SAME block right before using it.
- **Region us-east-1**, ambient creds (**no `--profile`**).
- **The `hub_report` Lambda uses a CUSTOM log group** (OD-003 explicit LogGroup), so
  `aws logs tail /aws/lambda/<fn>` fails `ResourceNotFoundException`. Tail the real group
  from `LoggingConfig.LogGroup` if you need logs.
- **Reuse a fully-processed intake** (4.5 reads on demand) — e.g. the 4.2/4.3 live-run
  intake `891cb78f-…` — so all three tiers are populated. A fresh submit needs a few
  minutes for 3.2/3.3 (real Nova Pro calls) + 3.4 + 3.5 to land.

---

## STEP 0 (Hub tab) — no Bedrock prerequisite for 4.5 (but 3.2/3.3 need it upstream)

> 4.5 makes NO model call (RD-045), so it needs no Bedrock access itself. But its Security
> + Developer tiers are most meaningful over a COMPLETE Phase-3 record (which needs Nova
> Pro enabled upstream so 3.2/3.4 land). Reuse an intake that already reached `assessed`/
> `recommended`.

```
aws sts get-caller-identity
```
**Run in: Hub (641628980935), us-east-1, no --profile.** Expect `"Account": "641628980935"`.

---

## STEP 1 (Hub tab) — get the 4.5 code + prove the checkout carries it

> **Deploy-gap guard:** a `cdk deploy` prints `✅ UPDATE_COMPLETE` even on the WRONG branch.
> BEFORE deploying, prove the checkout carries the RD-045 code; AFTER deploying, inspect the
> LIVE Lambda. Never trust the green line.

```
cd ~/ZTIE-Issues && git fetch origin -q && git checkout feature/story-4.5 && git reset --hard origin/feature/story-4.5
```
(If the 4.5 PR is already merged, use `git checkout main && git reset --hard origin/main`.)

```
git rev-parse --abbrev-ref HEAD && git log --oneline -1
```

```
ls lambdas/hub_report && grep -n "ReportOrchestrator\|REPORT_CONTRACT_VERSION\|hub_report" infra/lib/ztie-hub-tracking-stack.ts | head
```
Expect the `lambdas/hub_report/` files (`handler.py` / `report.py` / `status_model.py` /
`awsio.py` / `report.contract.v1.json`) + the new `ReportOrchestrator` construct + the env
pin. Confirm it is PURE + READ-only + on-demand:

```
grep -n "reportFn\|grantReadData(reportFn)\|reportFn.addEventSource\|bedrock" infra/lib/ztie-hub-tracking-stack.ts | head
```
Expect `grantReadData(reportFn)` (READ-only) and NO `reportFn.addEventSource(...)` (not
stream-triggered) and NO bedrock grant tied to `reportFn`. If `ReportOrchestrator` is
ABSENT, the checkout is stale — re-run the checkout.

---

## STEP 2 (Hub tab) — redeploy the Hub tracking stack (ships the new 4.5 Lambda)

```
cd ~/ZTIE-Issues/infra && npm ci
```

```
cd ~/ZTIE-Issues/infra && npx cdk deploy ZtieHubTrackingStack --require-approval never
```
Expect `✅ ZtieHubTrackingStack` with the `ReportOrchestratorName` output.

### Post-deploy live verify (do NOT trust the green line alone)

```
RO=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='ReportOrchestratorName'].OutputValue" --output text) ; aws lambda get-function-configuration --function-name "$RO" --region us-east-1 --query "Environment.Variables"
```
Expect `REPORT_CONTRACT_VERSION` = `1.0`, `STATUS_CONTRACT_VERSION` = `1.0`,
`TRACKING_TABLE` set, `LOG_LEVEL` = `INFO`. (There is deliberately NO `NOVA_MODEL_ID` — 4.5
is PURE.)

Confirm the 4.5 Lambda has **NO Bedrock grant** (RD-045 PURE) and is **READ-only** on the
table — only `dynamodb:GetItem`/read-class actions, NO `UpdateItem`/`PutItem`/`DeleteItem`:

```
RO=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='ReportOrchestratorName'].OutputValue" --output text) ; ROLE=$(aws lambda get-function-configuration --function-name "$RO" --region us-east-1 --query Role --output text | awk -F/ '{print $NF}') ; for P in $(aws iam list-role-policies --role-name "$ROLE" --query "PolicyNames" --output text); do aws iam get-role-policy --role-name "$ROLE" --policy-name "$P" --query "PolicyDocument.Statement[].Action" --output json; done
```
Expect only READ `dynamodb:*` actions (GetItem / BatchGetItem / Query / etc.) — **NO
`dynamodb:UpdateItem`/`PutItem`/`DeleteItem`, NO `bedrock:InvokeModel`**.

---

## STEP 3 (optional, Forensic tab) — submit a routable artifact if you need a fresh intake

> Skip this if you will reuse a fully-processed intake (recommended). Otherwise submit one
> and give 3.2/3.3 (real Nova Pro) + 3.4 + 3.5 a few minutes to land.

```
aws sts get-caller-identity
```
**Run in: Forensic (360999005254), us-east-1, no --profile.** Expect `360999005254`.

```
pip install awscurl >/dev/null 2>&1 ; python3 -c "import base64,json; nl=chr(10); q=chr(39); tpl=('AWSTemplateFormatVersion: '+q+'2010-09-09'+q+nl+'Resources:'+nl+'  B:'+nl+'    Type: AWS::S3::Bucket'+nl).encode(); b=base64.b64encode(tpl).decode(); open('/tmp/intake.json','w').write(json.dumps({'filename':'probe.yaml','content_type':'text/yaml','submitter':'story-4.5-live','content_base64':b}))"
```

```
ENDPOINT=$(aws cloudformation describe-stacks --stack-name ZtieIntakeStack --region us-east-1 --query "Stacks[0].Outputs[?contains(OutputValue,'/intake')].OutputValue | [0]" --output text) ; echo "$ENDPOINT"
```

```
awscurl --service execute-api --region us-east-1 -X POST -H 'Content-Type: application/json' -d @/tmp/intake.json "$ENDPOINT"
```
**Record the returned `intake_id`.**

---

## STEP 4 (Hub tab) — INVOKE `hub_report` + confirm the three-tier report + HTML

Give the pipeline a few minutes if you submitted fresh, then invoke (Hub tab):

```
aws sts get-caller-identity
```
Expect `641628980935`.

### 4a — assemble the report (format=both -> payload + HTML)

```
RO=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='ReportOrchestratorName'].OutputValue" --output text) ; IID=<paste-the-intake_id> ; aws lambda invoke --function-name "$RO" --payload "{\"intake_id\":\"$IID\",\"format\":\"both\"}" --cli-binary-format raw-in-base64-out --region us-east-1 /tmp/report.json >/dev/null ; python3 -c "import json; d=json.load(open('/tmp/report.json')); r=d.get('report',{}); print('contract:', r.get('contract_version'), 'intake:', r.get('intake_id')); print('exec stage:', r.get('executive',{}).get('overall_stage'), 'combined_score:', r.get('executive',{}).get('combined_score')); print('exec rec:', r.get('executive',{}).get('recommendation')); print('security status:', r.get('security',{}).get('data_status'), 'findings:', r.get('security',{}).get('finding_count'), 'gaps:', r.get('security',{}).get('gap_count')); print('security mitre:', r.get('security',{}).get('mitre_attack'), 'sigma:', r.get('security',{}).get('sigma_rules')); print('developer status:', r.get('developer',{}).get('data_status'), 'remediations:', r.get('developer',{}).get('remediation_count'), 'file_line:', r.get('developer',{}).get('source_location')); print('html present:', 'html' in d, 'html len:', len(d.get('html','')))"
```

**Pass criteria (all must hold):**
1. The invoke returns `report` + `html` (NOT an `error` envelope): `report.contract_version` =
   `1.0`, matching `intake_id` + `sha256`.
2. **Executive** — `overall_stage` = `recommended` for a fully-processed intake, a
   `combined_score` (0-100), and a `recommendation` = the 3.5 advisory
   `recommended_verdict` (PASS/FAIL/INCONCLUSIVE) with **`decision` = `pending`** +
   **`advisory` = `true`** + a one-paragraph `summary`.
3. **Security** — `data_status` = `available`; `finding_count` / `gap_count` present; and
   **`mitre_attack.status` = `not_carried_on_hub`** + **`sigma_rules.status` =
   `not_carried_on_hub`** (the honest RD-013 placeholder, not an error).
4. **Developer** — `data_status` = `available`; `remediation_count` present; the
   remediations rank-ordered; and **`source_location.status` = `not_carried_on_hub`**
   (exact file/line not carried).
5. `html` is present and non-empty (the self-contained render).

### 4b — eyeball the HTML (optional but recommended)

```
python3 -c "import json; open('/tmp/report.html','w').write(json.load(open('/tmp/report.json')).get('html','')); print('wrote /tmp/report.html')"
```
Download `/tmp/report.html` from CloudShell (Actions -> Download file) and open it: confirm
the dark-on-light print layout with the **advisory banner**, the three tier sections
(Executive / Security / Developer), the graduated severity pills, and the "not available on
Hub" markers for MITRE / Sigma / file-line. Print-to-PDF gives the PDF.

### 4c — no effective-verdict key

```
python3 -c "import json; s=json.dumps(json.load(open('/tmp/report.json')).get('report',{})); banned=['\"verdict\"','\"safe\"','\"approved\"','\"forward\"','\"malicious\"','\"pass_fail\"','\"clean\"']; print('FAIL: banned key present' if any(b in s for b in banned) else 'OK: no effective-verdict key (only advisory recommended_verdict)')"
```
Expect `OK: no effective-verdict key`.

### 4d — READ-ONLY proof + error paths

7. **READ-ONLY — nothing written.** Confirm the invoke added NO field to the item:

```
TABLE=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='TrackingTableName'].OutputValue" --output text) ; IID=<paste-the-intake_id> ; aws dynamodb get-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --region us-east-1 --query "keys(Item)" --output json
```
Expect the SAME attribute set as before the invoke — NO new `report_*` attribute (4.5
returns the report, it does not persist it).

8. **Error paths clean:**

```
RO=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='ReportOrchestratorName'].OutputValue" --output text) ; aws lambda invoke --function-name "$RO" --payload "{\"intake_id\":\"00000000-0000-4000-8000-000000000000\"}" --cli-binary-format raw-in-base64-out --region us-east-1 /tmp/nf.json >/dev/null ; cat /tmp/nf.json
```
Expect `{"error": {"code": 404, ...}}`.

---

## STEP 5 — paste back for the record

Paste back, VERBATIM:
- the `sts get-caller-identity` account for each tab,
- the `git log --oneline -1` line + the STEP 1 greps,
- the STEP 2 post-deploy env + role-policy output (proving PURE + READ-only),
- the STEP 3 `intake_id` (or the reused one),
- the STEP 4a summary output, the STEP 4c no-banned-key line, the STEP 4d `keys(Item)` +
  404 envelope, and a one-line note of what the STEP 4b HTML looked like.

The executor records these verbatim into the RUNBOOK 4.5 detail, flips **4.5 → ✅** (paired
commit), clears 4.5 from the Validation Debt Register, and authors the next Phase-4 handoff.
On a FAIL, 4.5 stays 🟡 (already on the register); the executor fixes + re-validates once
(fix-then-validate-once), never marking done on inference.

## If something fails

- **Executive `overall_stage` is not `recommended`** — the pipeline has not finished for
  this intake (upstream latency, not a 4.5 bug). Reuse a fully-processed intake or wait.
- **Security/Developer `data_status` is `pending`** — the 3.2 correlation / 3.4 assessment
  has not landed. Expected before those stages complete; re-invoke once they do.
- **`error.code: 404`** on your real intake — the record is not there yet / wrong account /
  wrong id. Confirm Hub + the correct `intake_id`.
- **`error.code: 422`** — the tracking record is missing its `sha256` integrity key (a
  malformed item). Upstream data problem, not a 4.5 bug.
- **A new `report_*` attribute appears on the item** — that would be a real 4.5 defect (4.5
  must be READ-only). Capture it; the executor keeps 4.5 🟡 and fixes.
- **A bare effective-verdict key appears** — a real 4.5 defect (must be advisory only).
  Capture it; keep 4.5 🟡 and fix.
- **Infra-shaped failure** (missing role / export) — check whether it is OD-001/OD-002
  cleanup fallout BEFORE assuming it is a 4.5 bug.
