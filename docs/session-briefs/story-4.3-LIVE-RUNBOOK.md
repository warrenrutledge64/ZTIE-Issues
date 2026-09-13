# Story 4.3 — LIVE dashboard-render validation runbook (stakeholder) — RD-043

> **This is the ONLY live part of 4.3, and only YOU can do it** (the executor has no
> AWS creds). You DEPLOY the NEW `ZtieDashboardStack` in the **Hub** account (a static
> dark-theme SPA on private S3 + CloudFront, plus an IAM-auth API Gateway front that
> PROXIES to the UNCHANGED Story 4.2 `hub_dashboard` Lambda), make sure a real intake has
> run the full pipeline (so a per-intake record exists), then **exercise the two GET
> endpoints** — `GET /dashboard` (fleet) and `GET /status/{intake_id}` (per-intake) — via
> `awscurl` (SigV4), and **load the CloudFront URL in a browser** to eyeball the render
> (dark theme + graduated threat coloring + the advisory recommendation + the disabled
> APPROVE/REJECT control). The executor **records your returned output verbatim** into the
> RUNBOOK 4.3 detail. **Nothing is recorded on inference** — paste back exactly what the
> commands print / what you see. On a pass the executor flips 4.3 ✅ (paired commit), clears
> 4.3 from the Validation Debt Register, and the next Phase-4 pipe work unblocks.
>
> **4.3 renders 4.2's payload — it re-derives NOTHING.** The API endpoints proxy to the
> UNCHANGED 4.2 `hub_dashboard` Lambda, so the JSON they return is exactly
> `dashboard.contract.v1` (already validated live in 4.2). This run proves: (1) the
> AWS-native hosting stands up (S3+CloudFront serve the SPA; the IAM-auth API proxies to
> 4.2), and (2) the render is correct + safe (dark theme, graduated coloring, advisory
> framing, disabled control surface, `not_wired`→"not available yet").

## What 4.3 is (RD-043 — so the check is meaningful)

4.3 is the **Phase-4 PRESENTATION layer** — RENDER ONLY over 4.2's
`dashboard.contract.v1`. `ZtieDashboardStack` (Hub account) deploys:

- a **private, encrypted, block-public S3 bucket** holding the static SPA assets
  (`dashboard/index.html` + `styles.css` + `app.js` + a deploy-time `config.js`), served
  over **HTTPS via CloudFront using Origin Access Control** (the S3 origin is reachable
  ONLY through CloudFront); and
- a **REST API Gateway (IAM/SigV4 auth)** exposing `GET /dashboard` (fleet view) and
  `GET /status/{intake_id}` (per-intake view), each a `LambdaIntegration` **proxy to the
  EXISTING Story 4.2 `hub_dashboard` Lambda, referenced by ARN and UNCHANGED** (this stands
  up the GET front 4.2 deferred — the 4.2 handler already accepts the API-Gateway
  `pathParameters`/`queryStringParameters` shape).

The client (`app.js`) is **RENDER ONLY**: GET-only reads of the two 4.2 views, consuming
only `dashboard.contract.v1`; it re-derives nothing, calls no model, writes nothing. It
renders the fleet/list colored by the display `threat_tier` (dark theme, graduated
low/medium/high/critical), the per-intake detail drill-in (the 4.1 read-model + the
`threat` band + risk-score context bars + findings summary), the operator headline cards
(live activity + restore-point health as a first-class card; a port ⇄ MITRE placeholder
pending its deferred data source), and the human APPROVE/REJECT control SURFACE.

**CRUCIAL (RD-040): the 3.5 recommendation stays ADVISORY.** The render surfaces
`recommended_verdict` with an explicit advisory banner + a per-intake note + `decision:
pending`; the APPROVE/REJECT buttons are present but **DISABLED** (the ACTION + routing is
4.4/4.6/4.7). It renders NO bare effective-verdict value off the payload. **No stored XSS
(RD-013):** every derived value is inserted via `textContent`/`createTextNode`, never
`innerHTML`. The stubbed `not_wired` health blocks render as **"not available yet"** (correct
state, not an error). **Tenant-aware (RD-028):** a `subscriber_id` (default
`ztie-tenant-zero`) is carried on every read. **AWS-native** hosting/serving; **ServiceNow
OUT OF SCOPE.**

**Auth note:** the read API is **IAM/SigV4** (same zero-trust posture as the intake API). A
browser Cognito login is a DEFERRED follow-on — so a plain browser load of the CloudFront
URL will render the SPA shell + a clear "could not load data" notice for the API calls
(because an unsigned browser fetch is not authorized). That is EXPECTED and is not a 4.3
bug; the DATA path is proven here via `awscurl` (SigV4), and the RENDER is proven by
eyeballing the SPA + (optionally) pasting a signed payload into the page. This mirrors how
the intake API is validated.

## Ground rules (these have bitten us every session)

- **This stack is in the HUB (641628980935).** The 4.2 Lambda it proxies to, the tracking
  table, and everything you deploy/verify here are all in the Hub. (The intake API + lanes
  are in Forensic — only needed to PRODUCE a real intake to look at.)
- **Run `aws sts get-caller-identity` BEFORE every block** and read `Account`. Deploy +
  verify 4.3 from a **Hub-authed** shell. If you need to submit a fresh artifact, do that
  from a **Forensic-authed** shell (a `403` on the intake submit means you ran it in the Hub).
- **Feed commands ONE LINE AT A TIME.** Never paste a multi-line block.
- **`/tmp` + shell vars are WIPED when CloudShell recycles.** Re-set every variable in the
  SAME block right before using it, and re-`pip install awscurl` before a SigV4 call.
- **Region us-east-1**, ambient creds (**no `--profile`**).
- **Use a ROUTABLE artifact** (a small CloudFormation template with an S3 bucket) so the
  full Phase-3 record lands and the per-intake `overall_stage` reaches `recommended` and the
  `threat_tier` is banded from a real combined score. **You may REUSE any prior live-run
  intake** that already carries a full Phase-3 record (4.3 reads on demand) — e.g. the 4.2
  live-run intake `891cb78f-…` — instead of submitting a fresh one.
- **The 4.2 endpoint query can return more than one output** joined by a tab, which breaks
  SigV4 — pin exactly one URL with the `[?contains(...)] | [0]` query.
- **Reads are eventually-consistent** right after a write — re-read after a moment.

---

## STEP 0 (Hub tab) — prerequisite: Story 4.2 is deployed + a real intake exists

> 4.3 makes NO model call and adds NO new pipeline behavior — it only renders 4.2's payload.
> Its prerequisite is simply that the Story 4.2 `hub_dashboard` Lambda is DEPLOYED in the
> Hub (it is — 4.2 was validated live 2026-09-13) and that at least one intake carries a
> full Phase-3 record to render.

```
aws sts get-caller-identity
```
**Run in: Hub (641628980935), us-east-1, no --profile.** Expect `"Account": "641628980935"`.

Confirm the 4.2 Lambda exists and capture its ARN (you pass it to the 4.3 stack):

```
DASH_FN=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='DashboardOrchestratorName'].OutputValue" --output text) ; echo "$DASH_FN"
```

```
DASH_ARN=$(aws lambda get-function --function-name "$DASH_FN" --region us-east-1 --query "Configuration.FunctionArn" --output text) ; echo "$DASH_ARN"
```
**Record `$DASH_ARN`** — you pass it as `-c dashboardFunctionArn=$DASH_ARN` in STEP 2.

---

## STEP 1 (Hub tab) — get the 4.3 code + prove the checkout carries it

> **Deploy-gap guard:** a `cdk deploy` prints `✅` even on the WRONG branch — it just
> re-synthesizes STALE code. BEFORE deploying, prove the checkout carries the RD-043 stack;
> AFTER deploying, inspect the LIVE resources. Never trust the green line.

```
cd ~/ZTIE-Issues && git fetch origin -q && git checkout feature/story-4.3 && git reset --hard origin/feature/story-4.3
```
(If the 4.3 PR is already merged, use `git checkout main && git reset --hard origin/main`.)

```
git rev-parse --abbrev-ref HEAD && git log --oneline -1
```

```
ls dashboard && grep -n "ZtieDashboardStack\|DashboardApi\|withOriginAccessControl\|dashboardFunctionArn" infra/lib/ztie-dashboard-stack.ts | head
```
Expect the `dashboard/` assets (`index.html` / `styles.css` / `app.js` / `test_dashboard_render.py`)
and the stack's key constructs. Confirm the stack REFERENCES (does NOT recreate) the 4.2 Lambda:

```
grep -n "fromFunctionArn\|GET\|status/{intake_id}\|AuthorizationType.IAM" infra/lib/ztie-dashboard-stack.ts | head
```
Expect `Function.fromFunctionArn(...)` (imported, not created), the two `GET` methods, the
`{intake_id}` path resource, and `AuthorizationType.IAM`. If `ZtieDashboardStack` is ABSENT, the
checkout is stale — re-run the checkout.

---

## STEP 2 (Hub tab) — deploy the NEW dashboard stack

```
cd ~/ZTIE-Issues/infra && npm ci
```

```
cd ~/ZTIE-Issues/infra && DASH_ARN=$(aws lambda get-function --function-name "$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='DashboardOrchestratorName'].OutputValue" --output text)" --region us-east-1 --query "Configuration.FunctionArn" --output text) ; npx cdk deploy ZtieDashboardStack -c dashboardFunctionArn="$DASH_ARN" --require-approval never
```
Expect `✅ ZtieDashboardStack` with outputs `DashboardUrl` (CloudFront), `DashboardApiUrl`,
`DashboardSiteBucketName`, `DashboardSubscriberId`. (CloudFront can take several minutes to fully
deploy the first time.)

### Post-deploy live verify (do NOT trust the green line alone)

Capture the two URLs:

```
API=$(aws cloudformation describe-stacks --stack-name ZtieDashboardStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='DashboardApiUrl'].OutputValue" --output text) ; URL=$(aws cloudformation describe-stacks --stack-name ZtieDashboardStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='DashboardUrl'].OutputValue" --output text) ; echo "API=$API" ; echo "URL=$URL"
```

Confirm the 4.3 stack created NO Lambda of its own (it proxies to the 4.2 Lambda) and the API is
IAM-authed:

```
aws cloudformation describe-stack-resources --stack-name ZtieDashboardStack --region us-east-1 --query "StackResources[?ResourceType=='AWS::Lambda::Function'].LogicalResourceId" --output json
```
Expect `[]` (an empty list) — 4.3 adds no Lambda; it references the 4.2 one.

---

## STEP 3 (optional, Forensic tab) — submit a routable artifact if you need a fresh intake

> Skip this if you will reuse an existing intake that already carries a full Phase-3 record
> (recommended — e.g. the 4.2 live-run intake). Otherwise submit one and give 3.2/3.3 (real
> Nova Pro calls) + 3.4 + 3.5 a few minutes to land.

```
aws sts get-caller-identity
```
**Run in: Forensic (360999005254), us-east-1, no --profile.** Expect `360999005254`.

```
pip install awscurl >/dev/null 2>&1 ; python3 -c "import base64,json; nl=chr(10); q=chr(39); tpl=('AWSTemplateFormatVersion: '+q+'2010-09-09'+q+nl+'Resources:'+nl+'  B:'+nl+'    Type: AWS::S3::Bucket'+nl).encode(); b=base64.b64encode(tpl).decode(); open('/tmp/intake.json','w').write(json.dumps({'filename':'probe.yaml','content_type':'text/yaml','submitter':'story-4.3-live','content_base64':b}))"
```

```
ENDPOINT=$(aws cloudformation describe-stacks --stack-name ZtieIntakeStack --region us-east-1 --query "Stacks[0].Outputs[?contains(OutputValue,'/intake')].OutputValue | [0]" --output text) ; echo "$ENDPOINT"
```

```
awscurl --service execute-api --region us-east-1 -X POST -H 'Content-Type: application/json' -d @/tmp/intake.json "$ENDPOINT"
```
**Record the returned `intake_id`** (call it `IID`).

---

## STEP 4 (Hub tab) — exercise the two GET endpoints via SigV4 (the DATA path)

```
aws sts get-caller-identity
```
Expect `641628980935`. Install the SigV4 client if needed:

```
pip install awscurl >/dev/null 2>&1
```

### 4a — GET /status/{intake_id} (per-intake view)

```
API=$(aws cloudformation describe-stacks --stack-name ZtieDashboardStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='DashboardApiUrl'].OutputValue" --output text) ; IID=<paste-the-intake_id> ; awscurl --service execute-api --region us-east-1 -X GET "${API}status/${IID}?subscriber_id=ztie-tenant-zero" | python3 -m json.tool
```

**Pass criteria (per-intake — all must hold):**
1. The call returns the payload (NOT an `error` envelope): `contract_version` = `1.0`, `view` =
   `intake`, an `assembled_at` Z-timestamp, and an `intake` object.
2. **`intake.status`** is the full 4.1 read-model (`overall_stage` = `recommended` for a
   fully-processed intake, `stages` all `present`, `scores` echoed static/dynamic/combined,
   `findings_summary`, `recommendation`).
3. **`intake.threat.tier`** ∈ `unknown/low/medium/high/critical` (a DISPLAY band; `combined_score`
   echoed).
4. **`intake.action`** carries `intake_id` + `sha256`, the ADVISORY `recommended_verdict`,
   **`decision` = `pending`**, and **`advisory` = `true`**.

### 4b — GET /dashboard (fleet view)

```
API=$(aws cloudformation describe-stacks --stack-name ZtieDashboardStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='DashboardApiUrl'].OutputValue" --output text) ; awscurl --service execute-api --region us-east-1 -X GET "${API}dashboard?subscriber_id=ztie-tenant-zero&limit=10" | python3 -m json.tool
```

**Pass criteria (fleet — all must hold):**
5. `view` = `fleet`; `fleet.intakes` is a list of compact rows (each with `intake_id`,
   `overall_stage`, `threat_tier`, `decision: pending`, and `recommended_verdict` when landed);
   `fleet.returned_count` matches the list length (≤ 10); `fleet.truncated` is a boolean.
6. **`fleet.metrics`** carries `window_count`, `by_stage`, `by_recommended_verdict`,
   `by_threat_tier`, and the STUBBED **`ami_build_health` / `sensor_status` / `cost` each with
   `status: not_wired`**.

### 4c — no effective-verdict key in either payload

7. Both payloads carry the ADVISORY `recommended_verdict` but NEVER a bare effective verdict:

```
API=$(aws cloudformation describe-stacks --stack-name ZtieDashboardStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='DashboardApiUrl'].OutputValue" --output text) ; { awscurl --service execute-api --region us-east-1 -X GET "${API}dashboard?limit=10"; awscurl --service execute-api --region us-east-1 -X GET "${API}status/<paste-the-intake_id>"; } | python3 -c "import sys; banned=['\"verdict\"','\"safe\"','\"approved\"','\"forward\"','\"malicious\"','\"pass_fail\"','\"clean\"']; s=sys.stdin.read(); print('FAIL: banned key present' if any(b in s for b in banned) else 'OK: no effective-verdict key (only advisory recommended_verdict)')"
```
Expect `OK: no effective-verdict key`.

### 4d — error paths are clean (optional but recommended)

```
API=$(aws cloudformation describe-stacks --stack-name ZtieDashboardStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='DashboardApiUrl'].OutputValue" --output text) ; awscurl --service execute-api --region us-east-1 -X GET "${API}status/00000000-0000-4000-8000-000000000000"
```
Expect a `{"error": {"code": 404, ...}}` envelope (the 4.2 Lambda's not-found path, surfaced
through the proxy).

---

## STEP 5 (browser) — load the CloudFront URL + eyeball the RENDER

Open `$URL` (the `DashboardUrl` output) in a browser. Confirm, VISUALLY:
- **Dark background theme.** The page is dark; the top bar shows the ZTIE brand + the subscriber
  badge (`ztie-tenant-zero`).
- **Advisory banner** is visible at the top: recommendations are advisory only / never acted upon
  automatically.
- The **fleet table** renders with **graduated `threat_tier` color pills** (unknown/low/medium/
  high/critical each a distinct color, distinguishable at a glance) and a metrics roll-up; the
  operator headline cards show **live activity** + **restore-point health** (first-class card) +
  a **port ⇄ MITRE placeholder** ("not available yet"); the AMI/sensor/cost health shows **"not
  available yet"** (NOT an error).
- Clicking a row opens the **per-intake drill-in**: the stages, the risk-score context bars, the
  findings summary, the `threat` band, and the **human decision gate** card with the ADVISORY
  recommendation + `human decision: pending` + the **DISABLED** Approve / Reject buttons (hover
  shows "the action is Story 4.4 / 4.7").

> **Expected (not a bug):** because the read API is IAM/SigV4 and the browser is not signed in
> (Cognito is a deferred follow-on), the fleet/detail data area may show a bounded "could not load
> data (HTTP 403)" notice with the read-path explanation. The SPA shell, dark theme, and the
> advisory framing still render — and the DATA path is proven in STEP 4 via `awscurl`. If you want
> the browser to show live data, that requires the deferred Cognito front (a later story). The
> pass bar for 4.3 is: STEP 4 returns the correct payloads via SigV4 AND STEP 5 shows the dark-
> theme render with graduated coloring + the advisory, disabled control surface.

---

## STEP 6 — paste back for the record

Paste back, VERBATIM:
- the `sts get-caller-identity` account for each tab,
- the `git log --oneline -1` line + the STEP 1 greps,
- the STEP 2 outputs (`DashboardUrl`, `DashboardApiUrl`) + the empty-Lambda-list check,
- the STEP 3 `intake_id` (or the reused one),
- the STEP 4a full per-intake JSON, the STEP 4b full fleet JSON, the no-banned-key line, and the
  STEP 4d 404 envelope,
- a one-line description (or screenshot) of what STEP 5 rendered (dark theme, graduated coloring,
  advisory banner, disabled Approve/Reject).

The executor records these verbatim into the RUNBOOK 4.3 detail, flips **4.3 → ✅** (paired
commit), clears 4.3 from the Validation Debt Register, and authors the next Phase-4 handoff. On a
FAIL, 4.3 stays 🟡 (already on the register); the executor fixes + re-validates once
(fix-then-validate-once), never marking done on inference.

## If something fails

- **`ZtieDashboardStack` deploy fails on `dashboardFunctionArn`** — you did not pass `-c
  dashboardFunctionArn=<the 4.2 Lambda ARN>` (STEP 2). The stack only instantiates when the ARN
  is supplied. Re-run with the ARN from STEP 0.
- **CloudFront URL 403/AccessDenied for the SPA itself** — the distribution may still be
  deploying (first deploy takes several minutes) or the `BucketDeployment` has not finished.
  Wait and retry; confirm the `DashboardSiteBucketName` bucket has `index.html`.
- **`awscurl` GET returns 403 `not authorized`** — your Hub principal lacks `execute-api:Invoke`
  on the API, OR you are in the wrong account. Confirm `sts get-caller-identity` = Hub and that
  your role can invoke the API.
- **Per-intake `overall_stage` is not `recommended`** — the pipeline has not finished for this
  intake (upstream latency, not a 4.3 bug). Wait and re-GET, or reuse a fully-processed intake.
- **`threat.tier` is `unknown`** — no combined score yet on the item. Expected before 3.3 lands.
- **`error.code: 404`** on your real intake — the record is not there yet / wrong account /
  wrong id. Confirm Hub + the correct `intake_id`.
- **The JSON shows a bare effective-verdict key, or the buttons are enabled/wired** — that would
  be a real 4.3 defect (4.3 must be advisory + a disabled surface). Capture it; the executor
  keeps 4.3 🟡 and fixes.
- **A new attribute appears on the tracking item after a GET** — 4.3 (via the 4.2 Lambda) must be
  READ-only. Capture it; keep 4.3 🟡 and fix.
- **Infra-shaped failure** (missing role / export) — check whether it is OD-001/OD-002 cleanup
  fallout BEFORE assuming it is a 4.3 bug.
