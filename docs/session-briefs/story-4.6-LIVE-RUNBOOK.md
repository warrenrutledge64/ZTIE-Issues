# Story 4.6 — LIVE ACCEPT-push validation runbook (stakeholder) — RD-047, reworked per RD-048/RD-049

> **SUPERSEDES the pre-rework runbook.** The original 4.6 read the human decision from the
> Hub cross-account; that path is FORBIDDEN by RD-048 (the Hub is strictly the control
> plane). This reworked 4.6 VERIFIES a **Hub-signed `decision.token.v1` OFFLINE** (the H.2
> primitive, validated live) and never reads the Hub. This runbook proves the reworked
> crossing end-to-end.
>
> **Only YOU can do this** (the executor has no AWS creds). It spans **THREE accounts** —
> **Hub (641628980935)** signs the decision token; **Forensic (360999005254)** runs the
> pusher + holds the artifact; **Pipeline-Sandbox (586917955591)** is the landing bucket.
> On a pass the executor flips **4.6 → ✅** and Phase-4's ACCEPT half is done.

## What reworked 4.6 is (so the check is meaningful)

The Phase-4 **ACCEPT enforcement action**, now on the authenticated-decision primitive. The
Forensic `pde_handoff` Lambda is invoked with `{intake_id, decision_token, signature,
artifact_s3_key}` and:
1. VERIFIES the Hub-signed `decision.token.v1` **OFFLINE** against the embedded Hub public
   key (`lib/decision_auth`, `cryptography` bundled) — **no call into the Hub / Hub KMS**;
2. recomputes the Forensic artifact's sha256;
3. **fail-closed gate:** push **iff** the signature verifies AND `decision == "accepted"`
   AND `token.sha256` == the recomputed sha256 AND the token is fresh AND `key_id` is
   trusted;
4. only then pushes the artifact one-directionally to the Sandbox landing bucket;
5. ALWAYS crosses a bounded, verdict-free `handoff` outcome to the Hub (RD-013).

**No spoke→Hub read anywhere (RD-048).** The signed token is the authorization; a
forged/unsigned invoke can't push. The artifact goes Forensic→Sandbox directly; never
through the Hub. ZTIE never re-executes it.

## Prerequisites (already live from earlier stories)
- **H.2 `ZtieDecisionSigningStack`** is deployed in the Hub — signing key
  `arn:aws:kms:us-east-1:641628980935:key/3321e5b7-2ca3-42e3-b99c-9b9d83a45243`
  (`aws kms describe-key` = SIGN_VERIFY / ECC_NIST_P256 / ECDSA_SHA_256). If not, deploy it
  per `story-H.2-LIVE-RUNBOOK.md` STEP 1 first.
- **`ZtieSandboxLandingStack`** is deployed in Pipeline-Sandbox (from the earlier 4.6 build).
- A fully-processed intake whose raw artifact still exists in the Forensic artifact bucket
  (e.g. `891cb78f-…` / `probe.yaml`, `sha256 cd0429…`).

## Ground rules
- Three CloudShell tabs (Hub / Forensic / Pipeline-Sandbox). `aws sts get-caller-identity`
  before EVERY block; a banner does not change the account.
- Feed commands ONE LINE AT A TIME. `/tmp` + shell vars wiped on recycle — re-set in-block.
- Region us-east-1, ambient creds (no `--profile`).
- Deploy-gap guard: after `cdk deploy`, inspect the LIVE resource (the pusher role must have
  **NO `dynamodb`** action + **NO `TRACKING_TABLE`** env — that is the whole point of the
  rework).

---

## STEP 0 (all tabs) — accounts + the H.2 signing key + the public key

Confirm each tab's account with `aws sts get-caller-identity` (Hub `641628980935`, Forensic
`360999005254`, Pipeline-Sandbox `586917955591`).

**Hub tab** — capture the signing key ARN + export the public key (the pusher embeds this):
```
KARN=$(aws cloudformation describe-stacks --stack-name ZtieDecisionSigningStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='DecisionSigningKeyArn'].OutputValue" --output text) ; KID=$(aws cloudformation describe-stacks --stack-name ZtieDecisionSigningStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='DecisionSigningKeyId'].OutputValue" --output text) ; echo "KARN=$KARN"
```
```
aws kms get-public-key --key-id "$KID" --region us-east-1 --query PublicKey --output text | base64 -d > /tmp/ztie_pub.der ; openssl pkey -pubin -inform DER -in /tmp/ztie_pub.der -out /tmp/ztie_pub.pem 2>/dev/null || openssl ec -pubin -inform DER -in /tmp/ztie_pub.der -pubout -out /tmp/ztie_pub.pem ; cat /tmp/ztie_pub.pem
```
Keep `/tmp/ztie_pub.pem` + `$KARN` — you'll pass them to the Forensic deploy.

---

## STEP 1 (Forensic tab) — get the reworked code + REDEPLOY the pusher

```
cd ~/ZTIE-Issues && git fetch origin -q && git checkout main && git reset --hard origin/main && git log --oneline -1
```
(If the rework PR is not yet merged, `git checkout feature/story-4.6-rework && git reset --hard origin/feature/story-4.6-rework`.)
```
grep -n "HUB_PUBLIC_KEY_PEM\|dynamodb" infra/lib/ztie-pde-handoff-stack.ts | head
```
Expect `HUB_PUBLIC_KEY_PEM` present and **NO `dynamodb`** line (the Hub read is gone).
```
cd ~/ZTIE-Issues/infra && rm -rf ~/.npm && mkdir -p ~/.npm-cache ~/.npm-tmp && TMPDIR=~/.npm-tmp npm install --no-audit --no-fund --cache ~/.npm-cache
```
Gather the coordinates (Forensic artifact bucket + Hub ingest queue + Sandbox bucket):
```
ARTB=$(aws cloudformation describe-stacks --stack-name ZtieIntakeStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='ArtifactBucketName'].OutputValue" --output text) ; echo "ARTB=$ARTB"
```
(From the **Hub** tab: `IngestQueueUrl` + `IngestQueueArn` from `ZtieHubTrackingStack`. From the **Sandbox** tab: `SandboxLandingBucketName` from `ZtieSandboxLandingStack`.) Then deploy — note `-c hubPublicKeyPem="$(cat /tmp/ztie_pub.pem)"` and `-c trustedKeyIds=$KARN`:
```
cd ~/ZTIE-Issues/infra && TMPDIR=~/.npm-tmp npx cdk deploy ZtiePdeHandoffStack --require-approval never -c artifactBucketName=$ARTB -c hubIngestQueueUrl=<IngestQueueUrl> -c hubIngestQueueArn=<IngestQueueArn> -c sandboxLandingBucket=<SandboxLandingBucketName> -c hubPublicKeyPem="$(cat /tmp/ztie_pub.pem)" -c trustedKeyIds=$KARN
```
Expect `✅ ZtiePdeHandoffStack` + outputs `PdeHandoffFunctionName` + `PdeHandoffRoleArn`. Capture:
```
PFN=$(aws cloudformation describe-stacks --stack-name ZtiePdeHandoffStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='PdeHandoffFunctionName'].OutputValue" --output text) ; PROLE=$(aws cloudformation describe-stacks --stack-name ZtiePdeHandoffStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='PdeHandoffRoleArn'].OutputValue" --output text) ; echo "$PFN" ; echo "$PROLE"
```

### Post-deploy live verify (the rework's whole point — no Hub read)
```
ROLE=$(echo "$PROLE" | awk -F/ '{print $NF}') ; for P in $(aws iam list-role-policies --role-name "$ROLE" --query "PolicyNames" --output text); do aws iam get-role-policy --role-name "$ROLE" --policy-name "$P" --query "PolicyDocument.Statement[].{Sid:Sid,Action:Action}" --output json; done
```
Expect ONLY `s3:GetObject`, `s3:PutObject`(+tagging), `sqs:SendMessage` — **NO `dynamodb:*`, NO `bedrock`.**
```
aws lambda get-function-configuration --function-name "$PFN" --region us-east-1 --query "Environment.Variables" | grep -E "HUB_PUBLIC_KEY_PEM|TRUSTED_KEY_IDS|TRACKING_TABLE|NOVA_MODEL_ID" ; echo "(expect HUB_PUBLIC_KEY_PEM + TRUSTED_KEY_IDS present; NO TRACKING_TABLE, NO NOVA_MODEL_ID)"
```

### (If the pusher role ARN changed) re-tighten the Sandbox grant (Pipeline-Sandbox tab)
```
cd ~/ZTIE-Issues/infra && TMPDIR=~/.npm-tmp npx cdk deploy ZtieSandboxLandingStack --require-approval never -c forensicPusherRoleArn=$PROLE
```

---

## STEP 2 (Hub tab) — sign an `accepted` decision token for the intake

```
IID=891cb78f-fd35-4045-81d6-030d75d9c83e ; SHA=cd04299d8e29601f5425054e0470a71f255fb19a7d2fe3734bcb6213f27208f0 ; ISSUED=$(python3 -c "import datetime;print(datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z'))")
```
Build the CANONICAL bytes exactly as the library does + `kms:Sign` + base64 the signature:
```
python3 -c "import json; t={'contract_version':'1.0','intake_id':'$IID','decision':'accepted','sha256':'$SHA','issued_at':'$ISSUED','key_id':'$KARN'}; open('/tmp/token.json','w').write(json.dumps(t)); open('/tmp/canon.bin','wb').write(json.dumps(t,sort_keys=True,separators=(',',':')).encode()); print('token + canonical written')"
```
```
SIG_B64=$(aws kms sign --key-id "$KARN" --message fileb:///tmp/canon.bin --message-type RAW --signing-algorithm ECDSA_SHA_256 --region us-east-1 --query Signature --output text) ; echo "$SIG_B64" > /tmp/sig.b64 ; echo "signed (base64 sig $(wc -c < /tmp/sig.b64) chars)"
```
Build the invoke payload (token + base64 signature + the Forensic artifact key):
```
python3 -c "import json; tok=json.load(open('/tmp/token.json')); sig=open('/tmp/sig.b64').read().strip(); iid=tok['intake_id']; open('/tmp/invoke.json','w').write(json.dumps({'intake_id':iid,'decision_token':tok,'signature':sig,'artifact_s3_key':'intake/'+iid+'/probe.yaml'})); print('invoke payload written')"
```
Copy `/tmp/invoke.json`'s content to the Forensic tab (it's small JSON — paste it, or re-create it there; it contains no secret).

---

## STEP 3 (Forensic tab) — the ACCEPT push (verify offline → push)

Put the STEP-2 payload at `/tmp/invoke.json` on the Forensic box, then:
```
PFN=$(aws cloudformation describe-stacks --stack-name ZtiePdeHandoffStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='PdeHandoffFunctionName'].OutputValue" --output text) ; aws lambda invoke --function-name "$PFN" --payload fileb:///tmp/invoke.json --cli-binary-format raw-in-base64-out --region us-east-1 /tmp/out.json >/dev/null ; python3 -c "import json;d=json.load(open('/tmp/out.json'));print('pushed:',d.get('pushed'),'outcome:',d.get('outcome'),'observed:',d.get('observed_decision'));print('dest:',d.get('handoff',{}).get('destination'))"
```
**Pass:** `pushed: True`, `outcome: pushed`, `observed: accepted`, a `destination` with `account_id 586917955591` + the Sandbox bucket + `key accepted/<intake_id>/probe.yaml`.

### (Pipeline-Sandbox tab) confirm the artifact LANDED + hash matches
```
SBKT=<SandboxLandingBucketName> ; IID=891cb78f-fd35-4045-81d6-030d75d9c83e ; aws s3 ls "s3://$SBKT/accepted/$IID/" --region us-east-1
```
```
KEY=$(aws s3api list-objects-v2 --bucket "$SBKT" --prefix "accepted/$IID/" --region us-east-1 --query "Contents[0].Key" --output text) ; aws s3api get-object --bucket "$SBKT" --key "$KEY" --region us-east-1 /tmp/landed.bin >/dev/null ; python3 -c "import hashlib;print('landed sha256:',hashlib.sha256(open('/tmp/landed.bin','rb').read()).hexdigest())"
```
**Pass:** the object is listed and `landed sha256` == `cd0429…` (the exact inspected bytes crossed).

---

## STEP 4 (Forensic tab) — FAIL-CLOSED proofs (nothing pushes without a valid signed accept)

Re-invoke with a broken payload each time; expect `pushed: False` and NOTHING new in the
Sandbox. (Use a DIFFERENT intake or check the Sandbox listing is unchanged.)

- **No token:** invoke `{"intake_id":"<iid>","artifact_s3_key":"intake/<iid>/probe.yaml"}` → `{"error":{"code":400}}` (missing decision_token) — no push.
- **Tampered signature:** flip one char in the base64 `signature` → `pushed: False`, `outcome: refused_not_accepted` (signature does not verify).
- **Rejected token:** sign a token with `decision:"rejected"` (repeat STEP 2 with rejected) → `pushed: False`, `outcome: refused_not_accepted`.
- **sha-mismatch:** sign a token whose `sha256` is `b*64` (wrong bytes) → `pushed: False`, `outcome: refused_hash_mismatch`.
- **Stale:** sign a token with an old `issued_at` (e.g. `2000-01-01T00:00:00Z`) → `pushed: False`, `outcome: refused_not_accepted`.

Confirm the Sandbox `accepted/<iid>/` listing did NOT gain an object from any refusal.

---

## STEP 5 (Hub tab) — the outcome crossed (bounded, verdict-free); no Hub read happened

```
TABLE=<TrackingTableName> ; IID=891cb78f-fd35-4045-81d6-030d75d9c83e ; aws dynamodb get-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --region us-east-1 --query "{outcome:Item.handoff_outcome.S, handoff:Item.handoff.M}"
```
**Pass:** `outcome: pushed`; the `handoff` map carries `observed_decision: accepted`, `hash_verified: true`, a `destination` — and NO `verdict`/`safe`/`approved`/`forward` key.
```
aws dynamodb get-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --region us-east-1 --query "Item.handoff" --output json > /tmp/ho.json ; python3 -c "import json;s=json.dumps(json.load(open('/tmp/ho.json')));banned=['\"verdict\"','\"safe\"','\"approved\"','\"forward\"','\"malicious\"','\"pass_fail\"','\"clean\"'];print('FAIL' if any(b in s for b in banned) else 'OK: no effective-verdict key')"
```

---

## STEP 6 — paste back for the record
Paste back, VERBATIM: STEP 1 the pusher role policy (no dynamodb) + env (no TRACKING_TABLE);
STEP 3 the push output + the landed object + matching sha256; STEP 4 the five refusal
results + the unchanged Sandbox listing; STEP 5 the `pushed` outcome map + the no-banned-key
line. The executor records these + flips **4.6 → ✅** (paired commit), clears 4.6 from the
Validation Debt Register. On a FAIL, 4.6 stays 🟡; fix + re-validate once.

## If something fails
- **`VALID` push refuses with `refused_not_accepted` + "bad_signature"** — the canonical
  bytes signed in STEP 2 differ from what the library canonicalizes. Confirm STEP 2 used
  `sort_keys=True, separators=(',',':')` over exactly the six token keys (that IS the
  library's `canonical_bytes`) and that `HUB_PUBLIC_KEY_PEM` on the deployed Lambda is the
  key you signed with (same `key_id`/ARN as `trustedKeyIds`).
- **Pusher role still shows `dynamodb`** — the reworked code did not deploy (stale checkout /
  wrong branch). Re-checkout + redeploy; the whole point of the rework is no Hub read.
- **`AccessDenied` on the push** — the Sandbox bucket policy is not scoped to the (new)
  pusher role ARN; re-run the STEP 1 Sandbox re-tighten with the current `$PROLE`.
- **404/malformed on the intake** — wrong intake id / the artifact was cleaned up; pick a
  fresh fully-processed intake with its artifact still present.
