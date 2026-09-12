# Story 3.3 — LIVE three-score risk validation runbook (stakeholder) — RD-038

> **This is the ONLY live part of 3.3, and only YOU can do it** (the executor has no
> AWS creds). You REDEPLOY the Hub tracking stack (which now ships the reworked Story
> 3.3 scorer Lambda + its re-added scoped `bedrock:InvokeModel` grant), make sure Nova
> Pro is enabled in Bedrock for the Hub account, submit ONE routable artifact so a
> `combined_event` (3.1) lands, and confirm that ONE **verdict-free** `scoring_result`
> — carrying **three 0-100 risk scores (static / dynamic / combined)** from **three
> REAL Amazon Nova Pro calls** — was recorded onto the SAME Hub tracking record. The
> executor **records your returned output verbatim** into the RUNBOOK 3.3 detail.
> **Nothing is recorded on inference** — paste back exactly what the commands print. On
> a pass the executor flips 3.3 ✅ (paired commit) and clears 3.3 from the Validation
> Debt Register.

## What 3.3 is now (RD-038 — so the check is meaningful)

3.3 was RE-SCOPED by RD-038 (stakeholder course-correction): it no longer produces the
RD-037 `accuracy`/`gap_analysis` `synthesis_result`. It now produces **three independent
0-100 risk scores** (higher = riskier), each by a SEPARATE Amazon Nova Pro call over the
derived Hub-side evidence, on a SHARED rubric:

- **static** — Nova Pro over ONLY the static lane's derived evidence.
- **dynamic** — Nova Pro over ONLY the dynamic lane's derived evidence (a peer of static).
- **combined** — Nova Pro over BOTH lanes' derived evidence together (its own assessment,
  NOT a formula over the two).

Each score is EVIDENCE, **never a verdict** — the prompts ask for a risk score + rationale
only; a failed/absent call is recorded honestly via that score's `status`
(scored / model_error / unparseable / skipped_no_evidence), never fabricated. The verdict
stays Hub-side / human-gated (Story 3.5). Nothing new crosses Forensic→Hub (Nova Pro reads
the derived evidence already on the tracking item — never the raw payload / trace).

## Ground rules (these have bitten us every session)

- **TWO accounts → TWO CloudShell tabs.** The artifact + lanes + ephemeral host are in
  **Forensic (360999005254)**; the tracking table + stream + the scorer + the
  `scoring_result` you verify + **Bedrock/Nova Pro** are all in the **Hub (641628980935)**.
  Deploy the Hub stack + verify from a **Hub-authed** shell; submit the artifact from a
  **Forensic-authed** shell.
- **Run `aws sts get-caller-identity` BEFORE every block** and read `Account`. A
  `ResourceNotFoundException` on the tracking table means you queried it from Forensic; it
  lives in the Hub.
- **Feed commands ONE LINE AT A TIME.** Never paste a multi-line block.
- **`/tmp` + shell vars are WIPED when CloudShell recycles.** Re-set every variable in the
  SAME block right before using it, and re-`pip install awscurl` before an intake submit.
- **Region us-east-1**, ambient creds (**no `--profile`**).
- **GitHub auth in CloudShell:** token-in-URL HTTPS form
  `git remote set-url origin https://<TOKEN>@github.com/warrenrutledge64/ZTIE-Issues.git`.

> **✅ VALIDATED LIVE 2026-09-12** (intake `217b909b-…`: static/dynamic/combined = 55/30/55,
> shared rubric, verdict-free, scored once). Live lessons captured so a re-run / the next
> story is friction-free:
> - **Endpoint query returns TWO outputs.** `ZtieIntakeStack` exposes both an `IntakeApi…`
>   and an `…Endpoint` output, so a `contains(OutputKey,...)` query returns BOTH joined by a
>   tab — SigV4 then signs a mangled path (the tab appears as `%2509` in the canonical
>   string) and you get "signature does not match". Pin exactly one URL:
>   `--query "Stacks[0].Outputs[?contains(OutputValue,'/intake')].OutputValue | [0]"` and
>   submit to `"$ENDPOINT"` directly (it already ends in `/intake` — do NOT append another).
> - **The scorer uses a CUSTOM log group** (OD-003 explicit LogGroup), so
>   `aws logs tail /aws/lambda/<fn>` fails `ResourceNotFoundException`. Tail the real group:
>   `LG=$(... get-function-configuration ... --query LoggingConfig.LogGroup --output text)`
>   then `aws logs tail "$LG" ...`.
> - **Use a ROUTABLE artifact.** A trivial file (e.g. `/etc/hostname`) classifies
>   `other_unknown` → `SAFE_REJECTED` (unroutable), so neither lane runs and nothing is
>   scored. Submit a real CloudFormation template (an S3 bucket is enough to give the static
>   lane findings).
> - **Reads are eventually-consistent.** Right after the scorer writes, an immediate
>   `Item.scoring_result` query can return `null`; re-read after a moment (or query
>   `keys(Item)` to confirm `scoring_result`/`scored_at` are present).

---

## STEP 0 (Hub tab) — Bedrock/Nova Pro access prerequisite

> RD-038 RE-ADDED the Nova Pro call to this Lambda (the RD-037 build had none). Nova Pro
> must be ENABLED for the Hub account (per-account, per-region) or the calls fail
> `AccessDeniedException` — which 3.3 will honestly record as `status: model_error` on
> each score, but that is NOT a passing run. Confirm access once, up front.

```
aws sts get-caller-identity
```
**Run in: Hub (641628980935), us-east-1, no --profile.** Expect `"Account": "641628980935"`.

```
aws bedrock list-foundation-models --region us-east-1 --query "modelSummaries[?contains(modelId,'nova-pro')].[modelId,modelLifecycle.status]" --output text
```
Expect an `amazon.nova-pro-v1:0` (ACTIVE) row. Nova Pro on-demand is invoked through the
region-prefixed inference profile `us.amazon.nova-pro-v1:0` (the scorer's default
`NOVA_MODEL_ID`).

---

## STEP 1 (Hub tab) — get the reworked 3.3 code + prove the checkout carries it

> **Deploy-gap guard:** a `cdk deploy` prints `✅ UPDATE_COMPLETE` even on the WRONG
> branch — it just re-synthesizes STALE code. BEFORE deploying, prove the checkout carries
> the RD-038 rework; AFTER deploying, inspect the LIVE Lambda. Never trust the green line.

```
cd ~/ZTIE-Issues && git fetch origin -q && git checkout feature/story-3.3 && git reset --hard origin/feature/story-3.3
```
(If the 3.3 PR is already merged, use `git checkout main && git reset --hard origin/main`.)

```
git rev-parse --abbrev-ref HEAD && git log --oneline -1
```

```
grep -n "InvokeNovaProForScoring\|SCORING_CONTRACT_VERSION" infra/lib/ztie-hub-tracking-stack.ts
```
Expect hits for BOTH the scoped Bedrock grant (`InvokeNovaProForScoring`) and the env pin
(`SCORING_CONTRACT_VERSION`). If ABSENT, the checkout is stale — re-run the checkout. This
is the pre-deploy marker check (proves the RD-038 rework, not the RD-037 build).

---

## STEP 2 (Hub tab) — redeploy the Hub tracking stack (ships the reworked scorer)

```
cd ~/ZTIE-Issues/infra && npm ci
```

```
cd ~/ZTIE-Issues/infra && npx cdk deploy ZtieHubTrackingStack --require-approval never
```
Expect `✅ ZtieHubTrackingStack` with the `SynthesisSynthesizerName` output.

### Post-deploy live verify (do NOT trust the green line alone)

```
SYN=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='SynthesisSynthesizerName'].OutputValue" --output text) ; aws lambda get-function-configuration --function-name "$SYN" --region us-east-1 --query "Environment.Variables"
```
Expect `SCORING_CONTRACT_VERSION` = `1.0`, `NOVA_MODEL_ID` = `us.amazon.nova-pro-v1:0`,
`NOVA_MAX_ATTEMPTS` = `5`, `SCORE_ONLY_WHEN_COMPLETE` = `1`, `TRACKING_TABLE` set. (This is
the RD-038 marker — the RD-037 build had `SYNTHESIS_CONTRACT_VERSION` + NO Nova env.)

Confirm the scoped Bedrock grant is present (NOT `*`):

```
SYN=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='SynthesisSynthesizerName'].OutputValue" --output text) ; ROLE=$(aws lambda get-function-configuration --function-name "$SYN" --region us-east-1 --query Role --output text | awk -F/ '{print $NF}') ; for P in $(aws iam list-role-policies --role-name "$ROLE" --query "PolicyNames" --output text); do aws iam get-role-policy --role-name "$ROLE" --policy-name "$P" --query "PolicyDocument.Statement[?Sid=='InvokeNovaProForScoring']" --output json; done
```
Expect an `InvokeNovaProForScoring` statement whose `Resource` lists the Nova Pro
inference-profile + foundation-model ARNs, never `*`.

---

## STEP 3 (Forensic tab) — submit ONE routable artifact so a combined event lands

> Use an artifact routing to BOTH lanes (e.g. a small CloudFormation template) so the
> combined event reaches `complete: true` (default gate `SCORE_ONLY_WHEN_COMPLETE=1`). If
> a recent intake from the 3.1/3.2 validation still has a `complete` combined event on the
> tracking item, you may REUSE its `intake_id` — but the scorer's stream mapping starts at
> `LATEST`, so nudge it (see STEP 3b) after the redeploy.

```
aws sts get-caller-identity
```
**Run in: Forensic (360999005254), us-east-1, no --profile.** Expect `360999005254`.

```
pip install awscurl >/dev/null 2>&1 ; python3 -c "import base64,json; b=base64.b64encode(open('/etc/hostname','rb').read()).decode(); open('/tmp/intake.json','w').write(json.dumps({'filename':'probe.yaml','content_type':'text/yaml','submitter':'story-3.3-live','content_base64':b}))"
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

### STEP 3b — REUSING an existing complete item (Hub tab, optional)

The scorer's stream mapping starts at `LATEST`, so a combined event that settled before the
redeploy will not re-trigger on its own. Nudge it (a no-op touch that does not change the
evidence — the fingerprint guard still fires once):

```
TABLE=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='TrackingTableName'].OutputValue" --output text) ; IID=<paste-a-complete-intake_id> ; aws dynamodb update-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --update-expression "SET scoring_touch = :t" --expression-attribute-values "{\":t\":{\"S\":\"story-3.3-live\"}}" --region us-east-1
```

---

## STEP 4 (Hub tab) — confirm ONE verdict-free `scoring_result` with THREE real scores

Give the lanes + 3.1 + the stream + three model calls a couple of minutes, then read the
tracking item (Hub tab):

```
aws sts get-caller-identity
```
Expect `641628980935`.

```
TABLE=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='TrackingTableName'].OutputValue" --output text) ; IID=<paste-the-intake_id> ; aws dynamodb get-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --region us-east-1 --query "Item.scoring_result" --output json
```

**Pass criteria (all must hold):**
1. A `scoring_result` object is present on the item (the scorer fired off the stream after
   the combined event was ready), with `rubric_version` set.
2. **Three score blocks** — `static`, `dynamic`, `combined` — each with a `status`. On a
   passing run each is `status: scored` with a bounded **0-100 `score`** (higher = riskier)
   + a `rationale` + `model_id` = the Nova Pro id + `attempts` (1 on a clean first try; >1
   means the exponential-backoff retry engaged — either proves the retry path). The three
   scores are on the SAME rubric so they are comparable.
3. **The combined score is its own assessment**, not an average — the `combined.rationale`
   should reference BOTH lanes' evidence. (It is fine if `combined` differs from any simple
   mean of `static`/`dynamic`.)
4. **No verdict anywhere.** Confirm with a grep of the whole item:

```
aws dynamodb get-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --region us-east-1 --output json | grep -Ei "verdict|safe|approved|forward|malicious|pass_fail|\"clean\"" || echo "NO verdict-shaped key present (expected)"
```
Expect `NO verdict-shaped key present (expected)`.

5. **Scored once + no call storm** — read the scorer's recent logs:

```
SYN=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='SynthesisSynthesizerName'].OutputValue" --output text) ; aws logs tail "/aws/lambda/$SYN" --region us-east-1 --since 15m --format short | grep -Ei "scoring recorded|already scored|not complete yet|no lane evidence" | tail -30
```
Expect ONE `scoring recorded (static=…/…, dynamic=…/…, combined=…/…)` line for the settled
combined event, then `already scored for this evidence fingerprint; no-op (guard)` on
subsequent stream events — NOT an unbounded stream of model calls (that would be 3× paid
calls per mutation).

### If any score is `model_error` / `unparseable` / `skipped_no_evidence` (honest, but read it)

- `model_error` + `AccessDeniedException` in `status_detail` → Nova Pro access not enabled
  for the Hub (STEP 0); enable + re-submit.
- `model_error` + `ThrottlingException` → retry budget exhausted under throttling;
  re-submit (the retry path is proven; a capacity condition, not a code defect).
- `unparseable` → the model returned an off-format response; recorded honestly, never
  fabricated. Re-submit; if it persists, the executor tunes the prompt (fix-then-validate).
- `skipped_no_evidence` on a lane → that lane's evidence wasn't present when scored (submit
  a both-lanes artifact so all three score).
- A PARTIAL result (one score failed, two scored) is HONEST and is a valid recorded outcome
  — but a **passing** 3.3 wants all three `scored` for the paired artifact. Re-submit if a
  score failed for a transient reason.

---

## What to paste back to the executor

- STEP 0: the `list-foundation-models` Nova Pro row.
- STEP 1: branch + `git log -1` + the `grep InvokeNovaProForScoring/SCORING_CONTRACT_VERSION` hits.
- STEP 2: the deploy line, the Lambda `Environment.Variables` (the RD-038 env markers), and
  the `InvokeNovaProForScoring` policy statement (to confirm it is scoped, not `*`).
- STEP 3: the `intake_id` (and whether it was a fresh submit or a reused complete item).
- STEP 4: the `scoring_result` JSON (the three score blocks), the no-verdict grep result,
  and the scorer log line (`scoring recorded …` + the `already scored … no-op` line).

On a pass (three `status: scored` 0-100 scores on the shared rubric, retry inspectable, no
verdict, scored once) the executor records this verbatim into RUNBOOK 3.3 detail, flips 3.3
✅ (paired commit), and clears 3.3 from the Validation Debt Register (re-opening the gate
for 3.4). On any fail, 3.3 stays 🟡 — the executor fixes and you re-run (fix-then-validate-once).
