# Story 4.2 — LIVE dashboard-payload validation runbook (stakeholder) — RD-042

> **This is the ONLY live part of 4.2, and only YOU can do it** (the executor has no
> AWS creds). You REDEPLOY the Hub tracking stack (which now ships the NEW Story 4.2
> `hub_dashboard` / DashboardOrchestrator Lambda), submit ONE routable artifact so the full
> pipeline runs (intake → both lanes → 3.1 → 3.2 → 3.3 → 3.4 → 3.5), then **INVOKE the
> `hub_dashboard` orchestrator TWICE** — once for the PER-INTAKE view (`view=intake`) and once
> for the FLEET view (`view=fleet`) — and confirm it RETURNS the assembled DASHBOARD PAYLOAD
> (`dashboard.contract.v1`): the per-intake detail (the 4.1 status read-model reused verbatim +
> a `threat` color band + an `action` block), and the fleet list (recent-intake rows + a
> `metrics` roll-up), assembled PURELY (no model call), READ-ONLY (nothing written), surfacing
> the 3.5 recommendation as **ADVISORY** (never acted upon). The executor **records your returned
> output verbatim** into the RUNBOOK 4.2 detail. **Nothing is recorded on inference** — paste
> back exactly what the commands print. On a pass the executor flips 4.2 ✅ (paired commit),
> clears 4.2 from the Validation Debt Register, and **4.3 unblocks** (dashboard render).
>
> **This run DOUBLES as an end-to-end pipeline pass** (like 4.1). If the full
> intake→lanes→3.1→3.2→3.3→3.4→3.5 flow runs green AND `hub_dashboard` assembles both views, the
> pipeline is confirmed intact through the Phase-4 data layer. If an infra-shaped failure appears
> (missing role / bucket / VPC endpoint / export), check whether it is fallout from the earlier
> OD-001/OD-002 cleanup BEFORE assuming it is a 4.2 bug.

## What 4.2 is (RD-042 — so the check is meaningful)

4.2 is the **Phase-4 DATA LAYER**. 4.1 built the per-intake status read-model; 4.2's
`hub_dashboard` Lambda assembles the comprehensive DASHBOARD JSON PAYLOAD (`dashboard.contract.v1`,
own pin `DASHBOARD_CONTRACT_VERSION`) the real-time dashboard (4.3 render) consumes, in ONE of two
shapes discriminated by `view`:

- **`view=intake`** (per-intake detail) — `intake.status` = the 4.1 status read-model reused
  VERBATIM (4.2 delegates to `status_model.build_status`; it does NOT re-assemble it) + a
  `threat` block (the normalized DISPLAY color band `unknown/low/medium/high/critical` + the
  echoed evidence it was banded from: `combined_score` / `highest_gap_severity` /
  `contradiction_present`) + an `action` block (the intake identity the human APPROVE/REJECT
  control keys on + the ADVISORY `recommended_verdict` + `decision: pending` + `advisory: true`).
- **`view=fleet`** (recent-intakes list) — `fleet.intakes` = a bounded, newest-first list of
  compact rows (default 50, hard max 100) read from the tracking table's `status-received_at-index`
  GSI (NO full scan) + `fleet.returned_count` + `fleet.truncated` + `fleet.metrics` (tracking-native
  counts `by_stage` / `by_recommended_verdict` / `by_threat_tier` / `window_count`, and the
  STUBBED operational-health blocks `ami_build_health` / `sensor_status` / `cost` = `not_wired`).

**CONTRACT-FIRST decision (RD-042, mirrors RD-041): 4.2 is an ON-DEMAND READ/transform** — NOT a
durable stored record and NOT a stream consumer. So the `hub_dashboard` Lambda:
- makes **NO model call** (like 3.4/3.5/4.1 — **NO Bedrock client, NO Bedrock grant**),
- **WRITES nothing** (READ-only `dynamodb:GetItem` + a bounded `Query` on the GSI; NEVER a
  `Scan`; there is no `put_*`/`update_*`/`delete_*` in its seam by design),
- has **NO DynamoDB-stream event source** (unlike every Phase-3 Lambda) — it is invoked **on
  demand**.

**There is NO Bedrock/Nova Pro prerequisite for 4.2 itself** (Nova Pro is still needed UPSTREAM
so 3.2 + 3.3 land their inputs). The ONLY new derivation 4.2 makes is the DISPLAY `threat_tier`
(from the combined 3.3 score, raised by a high/critical 3.4 gap or a contradiction) — a color
band for the dark-theme render, **NEVER a verdict**. **CRUCIAL: the 3.5 recommendation stays
ADVISORY.** 4.2 surfaces it (`recommended_verdict` + `decision: pending` + `advisory: true`); it
NEVER routes / promotes / enforces and NEVER writes a verdict onto any record. The 3.1-3.4
records stay verdict-free. Nothing new crosses Forensic→Hub — the payload never leaves the Hub
except as this Lambda's response to a Hub-side caller. **ServiceNow is OUT OF SCOPE.**

## Ground rules (these have bitten us every session)

- **TWO accounts → TWO CloudShell tabs.** The artifact + lanes + ephemeral host are in
  **Forensic (360999005254)**; the tracking table + the `hub_dashboard` Lambda + the payload you
  verify are all in the **Hub (641628980935)**. Deploy the Hub stack + invoke `hub_dashboard`
  from a **Hub-authed** shell; submit the artifact from a **Forensic-authed** shell.
- **Run `aws sts get-caller-identity` BEFORE every block** and read `Account`. A
  `ResourceNotFoundException` on the tracking table means you queried it from Forensic; it lives
  in the Hub. A `403` on the intake submit means you ran it from the Hub; submit from Forensic.
- **Feed commands ONE LINE AT A TIME.** Never paste a multi-line block. A multi-line `python -c`
  with embedded newlines in a `b'...'` literal breaks ("unterminated string literal") — the
  intake-build one-liner below uses `chr()` concatenation to avoid that.
- **`/tmp` + shell vars are WIPED when CloudShell recycles.** Re-set every variable in the SAME
  block right before using it, and re-`pip install awscurl` before an intake submit.
- **Region us-east-1**, ambient creds (**no `--profile`**).
- **The `hub_dashboard` Lambda uses a CUSTOM log group** (OD-003 explicit LogGroup), so
  `aws logs tail /aws/lambda/<fn>` fails `ResourceNotFoundException`. Tail the real group from
  `LoggingConfig.LogGroup` if you need logs.
- **Use a ROUTABLE artifact** (a small CloudFormation template with an S3 bucket) so both lanes
  run and the full Phase-3 record lands — otherwise the per-intake `overall_stage` will not reach
  `recommended` and the `threat` tier will be `unknown`.
- **Endpoint query returns TWO outputs** joined by a tab, which breaks SigV4 — pin exactly one
  URL with the `[?contains(...)] | [0]` query (STEP 3).
- **Reads are eventually-consistent** right after a write — re-read after a moment.

---

## STEP 0 (Hub tab) — no Bedrock prerequisite for 4.2 (but 3.2/3.3 need it upstream)

> 4.2 makes NO model call (RD-042), so it needs no Bedrock access itself. But its per-intake
> view is most meaningful over a COMPLETE Phase-3 record, which needs Nova Pro enabled for the
> Hub account (as in the 3.2/3.3/3.5/4.1 live runs). If your artifact does not produce a
> `scoring_result` / `verdict_result`, confirm Nova Pro access exactly as the 3.3 LIVE-RUNBOOK
> STEP 0 describes.

```
aws sts get-caller-identity
```
**Run in: Hub (641628980935), us-east-1, no --profile.** Expect `"Account": "641628980935"`.

---

## STEP 1 (Hub tab) — get the 4.2 code + prove the checkout carries it

> **Deploy-gap guard:** a `cdk deploy` prints `✅ UPDATE_COMPLETE` even on the WRONG branch —
> it just re-synthesizes STALE code. BEFORE deploying, prove the checkout carries the RD-042
> code; AFTER deploying, inspect the LIVE Lambda. Never trust the green line.

```
cd ~/ZTIE-Issues && git fetch origin -q && git checkout feature/story-4.2 && git reset --hard origin/feature/story-4.2
```
(If the 4.2 PR is already merged, use `git checkout main && git reset --hard origin/main`.)

```
git rev-parse --abbrev-ref HEAD && git log --oneline -1
```

```
grep -n "DashboardOrchestrator\|DASHBOARD_CONTRACT_VERSION\|hub_dashboard" infra/lib/ztie-hub-tracking-stack.ts
```
Expect hits for the new `DashboardOrchestrator` Lambda + the env pin (`DASHBOARD_CONTRACT_VERSION`)
+ the `hub_dashboard` asset dir. Confirm there is **NO** new Bedrock grant and **NO** stream event
source tied to it (4.2 is PURE + on-demand):

```
grep -n "dashboardFn\|DashboardOrchestrator\|grantReadData(dashboardFn)\|dashboardFn.addEventSource" infra/lib/ztie-hub-tracking-stack.ts
```
Expect `grantReadData(dashboardFn)` (READ-only) and NO `dashboardFn.addEventSource(...)` (4.2 is
NOT stream-triggered). If `DashboardOrchestrator` is ABSENT, the checkout is stale — re-run the
checkout.

---

## STEP 2 (Hub tab) — redeploy the Hub tracking stack (ships the new 4.2 Lambda)

```
cd ~/ZTIE-Issues/infra && npm ci
```

```
cd ~/ZTIE-Issues/infra && npx cdk deploy ZtieHubTrackingStack --require-approval never
```
Expect `✅ ZtieHubTrackingStack` with the `DashboardOrchestratorName` output.

### Post-deploy live verify (do NOT trust the green line alone)

```
DO=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='DashboardOrchestratorName'].OutputValue" --output text) ; aws lambda get-function-configuration --function-name "$DO" --region us-east-1 --query "Environment.Variables"
```
Expect `DASHBOARD_CONTRACT_VERSION` = `1.0`, `STATUS_CONTRACT_VERSION` = `1.0`, `TRACKING_TABLE`
set, `LOG_LEVEL` = `INFO`. (There is deliberately NO `NOVA_MODEL_ID` here — 4.2 is PURE.)

Confirm the 4.2 Lambda has **NO Bedrock grant** (RD-042 PURE) and is **READ-only** on the table —
only `dynamodb:GetItem`/`Query`-class actions, NO `UpdateItem`/`PutItem`/`DeleteItem`:

```
DO=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='DashboardOrchestratorName'].OutputValue" --output text) ; ROLE=$(aws lambda get-function-configuration --function-name "$DO" --region us-east-1 --query Role --output text | awk -F/ '{print $NF}') ; for P in $(aws iam list-role-policies --role-name "$ROLE" --query "PolicyNames" --output text); do aws iam get-role-policy --role-name "$ROLE" --policy-name "$P" --query "PolicyDocument.Statement[].Action" --output json; done
```
Expect only READ `dynamodb:*` actions (GetItem / Query / BatchGetItem / etc.) — **NO
`dynamodb:UpdateItem`/`PutItem`/`DeleteItem`, NO `bedrock:InvokeModel`**.

---

## STEP 3 (Forensic tab) — submit ONE routable artifact so the full pipeline runs

> Use an artifact routing to BOTH lanes (a small CloudFormation template) so the full Phase-3
> record lands (3.1 → 3.5) — so the per-intake `overall_stage` reaches `recommended` and the
> `threat` tier is banded from a real combined score.

```
aws sts get-caller-identity
```
**Run in: Forensic (360999005254), us-east-1, no --profile.** Expect `360999005254`.

```
pip install awscurl >/dev/null 2>&1 ; python3 -c "import base64,json; nl=chr(10); q=chr(39); tpl=('AWSTemplateFormatVersion: '+q+'2010-09-09'+q+nl+'Resources:'+nl+'  B:'+nl+'    Type: AWS::S3::Bucket'+nl).encode(); b=base64.b64encode(tpl).decode(); open('/tmp/intake.json','w').write(json.dumps({'filename':'probe.yaml','content_type':'text/yaml','submitter':'story-4.2-live','content_base64':b}))"
```

```
ENDPOINT=$(aws cloudformation describe-stacks --stack-name ZtieIntakeStack --region us-east-1 --query "Stacks[0].Outputs[?contains(OutputValue,'/intake')].OutputValue | [0]" --output text) ; echo "$ENDPOINT"
```

```
awscurl --service execute-api --region us-east-1 -X POST -H 'Content-Type: application/json' -d @/tmp/intake.json "$ENDPOINT"
```
**Record the returned `intake_id`** (call it `IID`). (`$ENDPOINT` already ends in `/intake` — do
NOT append another.)

> **Reusing an existing intake is fine.** Because 4.2 is invoked ON DEMAND (not stream-triggered),
> you may skip the submit and invoke `hub_dashboard` for ANY `intake_id` that already carries a
> full Phase-3 record (e.g. a prior live-run intake). Give a fresh submit a few minutes for
> 3.2/3.3 (real Nova Pro calls) + 3.4 + 3.5 to land first.

---

## STEP 4 (Hub tab) — INVOKE `hub_dashboard` for BOTH views + confirm the payload

Give the lanes + 3.1 → 3.5 a few minutes, then invoke `hub_dashboard` (Hub tab):

```
aws sts get-caller-identity
```
Expect `641628980935`.

### 4a — PER-INTAKE view (`view=intake`)

```
DO=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='DashboardOrchestratorName'].OutputValue" --output text) ; IID=<paste-the-intake_id> ; aws lambda invoke --function-name "$DO" --payload "{\"view\":\"intake\",\"intake_id\":\"$IID\"}" --cli-binary-format raw-in-base64-out --region us-east-1 /tmp/dash_intake.json >/dev/null ; cat /tmp/dash_intake.json | python3 -m json.tool
```

**Pass criteria (per-intake — all must hold):**
1. The invoke returns the payload (NOT an `error` envelope): top-level `contract_version` = `1.0`,
   `view` = `intake`, an `assembled_at` Z-timestamp, and an `intake` object.
2. **`intake.status`** is the full 4.1 read-model (`contract_version 1.0`, matching `intake_id` +
   `sha256`, `overall_stage` = `recommended` for a fully-processed intake, `stages` all `present`,
   `scores` echoed static/dynamic/combined, `findings_summary`, `recommendation`). This is the 4.1
   read-model reused VERBATIM.
3. **`intake.threat`** carries a `tier` ∈ `unknown/low/medium/high/critical` — banded from the
   combined score (`combined_score` echoed) and raised by a high/critical `highest_gap_severity`
   or `contradiction_present`. A DISPLAY band, never a verdict.
4. **`intake.action`** carries `intake_id` + `sha256`, the ADVISORY `recommended_verdict`
   (∈ PASS/FAIL/INCONCLUSIVE, matching the item's `verdict_result`), **`decision` = `pending`**,
   and **`advisory` = `true`**. The recommendation is SURFACED, never acted upon.

### 4b — FLEET view (`view=fleet`)

```
DO=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='DashboardOrchestratorName'].OutputValue" --output text) ; aws lambda invoke --function-name "$DO" --payload "{\"view\":\"fleet\",\"limit\":10}" --cli-binary-format raw-in-base64-out --region us-east-1 /tmp/dash_fleet.json >/dev/null ; cat /tmp/dash_fleet.json | python3 -m json.tool
```

**Pass criteria (fleet — all must hold):**
5. Top-level `view` = `fleet`; `fleet.intakes` is a list of compact rows (each with `intake_id`,
   `overall_stage`, `threat_tier`, `decision: pending`, and `recommended_verdict` when one has
   landed); `fleet.returned_count` matches the list length (≤ 10, ≤ hard max 100);
   `fleet.truncated` is a boolean. YOUR intake from STEP 3 should appear as a row (it is recent).
6. **`fleet.metrics`** carries `window_count`, `by_stage`, `by_recommended_verdict`,
   `by_threat_tier` (tracking-native counts over the returned rows) — and the STUBBED health
   blocks **`ami_build_health` / `sensor_status` / `cost` each with `status: not_wired`** (their
   real data sources are deferred; the SHAPE is fixed).

### 4c — READ-ONLY proof + no effective-verdict key

7. **READ-ONLY — nothing written.** Re-read the tracking item and confirm the invokes added NO
   field and left the tracking `status` + the 3.1-3.5 records UNCHANGED:

```
TABLE=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='TrackingTableName'].OutputValue" --output text) ; IID=<paste-the-intake_id> ; aws dynamodb get-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --region us-east-1 --query "keys(Item)" --output json
```
Expect the SAME attribute set as before the invokes — and NO new 4.2-written attribute (no
`dashboard_*` / `threat_*` field on the item; 4.2 returns the payload, it does not persist it).

8. **No effective-verdict field in either payload.** Both payloads must carry the ADVISORY
   `recommended_verdict` but NEVER a bare effective verdict:

```
cat /tmp/dash_intake.json /tmp/dash_fleet.json | python3 -c "import sys; banned=['\"verdict\"','\"safe\"','\"approved\"','\"forward\"','\"malicious\"','\"pass_fail\"','\"clean\"']; s=sys.stdin.read(); print('FAIL: banned key present' if any(b in s for b in banned) else 'OK: no effective-verdict key (only advisory recommended_verdict)')"
```
Expect `OK: no effective-verdict key`.

9. **Error paths are clean (optional but recommended).** Invoke the intake view with a
   non-existent intake and a malformed id and confirm bounded error envelopes:

```
DO=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='DashboardOrchestratorName'].OutputValue" --output text) ; aws lambda invoke --function-name "$DO" --payload "{\"intake_id\":\"00000000-0000-4000-8000-000000000000\"}" --cli-binary-format raw-in-base64-out --region us-east-1 /tmp/nf.json >/dev/null ; cat /tmp/nf.json
```
Expect `{"error": {"code": 404, ...}}`.

```
DO=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='DashboardOrchestratorName'].OutputValue" --output text) ; aws lambda invoke --function-name "$DO" --payload "{\"intake_id\":\"not-a-uuid\"}" --cli-binary-format raw-in-base64-out --region us-east-1 /tmp/bad.json >/dev/null ; cat /tmp/bad.json
```
Expect `{"error": {"code": 400, ...}}`.

---

## STEP 5 — paste back for the record

Paste back, VERBATIM:
- the `sts get-caller-identity` account for each tab,
- the `git log --oneline -1` line + the STEP 1 greps,
- the STEP 2 post-deploy env + role-policy output (proving PURE + READ-only),
- the STEP 3 `intake_id` (or the reused one),
- the STEP 4a full `/tmp/dash_intake.json`, the STEP 4b full `/tmp/dash_fleet.json`, the
  `keys(Item)` before/after, the no-banned-key line, and the two error-path envelopes.

The executor records these verbatim into the RUNBOOK 4.2 detail, flips **4.2 → ✅** (paired
commit), clears 4.2 from the Validation Debt Register, and authors the **4.3** (dashboard render)
handoff. On a FAIL, 4.2 stays 🟡 (already on the register); the executor fixes + re-validates
once (fix-then-validate-once), never marking done on inference.

## If something fails

- **Per-intake `intake.status.overall_stage` is not `recommended`** — the pipeline has not
  finished for this intake. Wait a few minutes (3.2/3.3 are real Nova Pro calls) and re-invoke;
  check the item actually carries `scoring_result` + `verdict_result`. Upstream latency, not a
  4.2 bug.
- **`threat.tier` is `unknown`** — there is no combined score / elevating signal yet on the item.
  Expected before 3.3 lands; re-invoke once the pipeline finishes.
- **`error.code: 404`** on your real intake — the tracking record is not there yet (submit not
  landed / wrong account). Confirm you are in the Hub and the `intake_id` is correct.
- **`error.code: 422`** — the tracking record is missing its `sha256` integrity key (a malformed
  item). Upstream data problem, not a 4.2 bug (4.2 correctly refuses to assemble a view over a
  record it cannot integrity-key).
- **The fleet list is empty** — no tracking records match the known statuses yet. Submit an
  intake first (STEP 3) and re-invoke; reads are eventually-consistent.
- **A new 4.2-written attribute appears on the item** — that would be a real 4.2 defect (4.2 must
  be READ-only). Capture it; the executor keeps 4.2 🟡 and fixes.
- **Infra-shaped failure** (missing role / bucket / VPC endpoint / export) — check whether it is
  OD-001/OD-002 cleanup fallout BEFORE assuming it is a 4.2 bug.
