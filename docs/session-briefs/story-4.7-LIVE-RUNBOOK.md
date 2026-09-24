# Story 4.7 — LIVE REJECT/destroy validation runbook (stakeholder) — RD-047, per RD-048/RD-049

> **The REJECT/hold half of the human gate — the sibling of the ✅ 4.6 ACCEPT-push, on the
> SAME authenticated-decision trust model (RD-048/RD-049).** 4.7 VERIFIES a **Hub-signed
> `rejected` `decision.token.v1` OFFLINE** and, ONLY on a verified reject bound to the
> artifact bytes, DESTROYS the artifact (all versions) + its derived Forensic outputs +
> terminates any live detonation chamber. INCONCLUSIVE (no token) HOLDS. It never reads the
> Hub.
>
> **Only YOU can do this** (the executor has no AWS creds). It spans **THREE accounts** —
> **Hub (641628980935)** signs the decision token; **Forensic (360999005254)** runs the
> destroyer + holds the artifact + chamber; the bounded outcome crosses back to the **Hub**.
> On a pass the executor flips **4.7 → ✅**; together with 4.3 (✅) this unblocks **4.4**
> (which closes Phase 4). 4.7 is a `[sec-boundary]` story — on ✅ the executor also authors +
> retains `docs/validation-evidence/4.7/` (RD-054).

## The one invariant this run must prove (RD-040)
**4.7 destroys ONLY on a verified Hub-signed `rejected` token — NEVER on the advisory
`recommended_verdict`.** INCONCLUSIVE is a HOLD (no token → nothing destroyed). Absent a
genuine signed REJECT, NOTHING is destroyed. The FAIL-SAFE branches (STEP 5) are the most
important part of this validation.

## What 4.7 is (so the check is meaningful)
The Phase-4 **REJECT enforcement action** on the authenticated-decision primitive. The
Forensic `pde_reject` Lambda is invoked with `{intake_id, decision_token, signature,
artifact_s3_key?}` and:
1. VERIFIES the Hub-signed `decision.token.v1` **OFFLINE** against the embedded Hub public
   key (`lib/decision_auth`, `cryptography` bundled), `expected_decision="rejected"` — **no
   call into the Hub / Hub KMS**. A MISSING token = the INCONCLUSIVE HOLD (fail-safe default);
2. recomputes the Forensic artifact's sha256;
3. **fail-safe gate:** destroy **iff** the signature verifies AND `decision == "rejected"`
   AND `token.sha256` == the recomputed sha256 AND the token is fresh AND `key_id` is
   trusted;
4. only then deletes ALL object versions + delete-markers under the intake's Forensic
   prefixes (`intake/<id>/` + derived `findings/<id>/` `runs/<id>/` `traces/<id>/`) AND
   terminates any live detonation chamber (the ephemeral EC2 for the intake);
5. ALWAYS crosses a bounded, verdict-free `disposition` outcome to the Hub (RD-013, the
   **11th** envelope kind).

**No spoke→Hub read anywhere (RD-048).** The signed token is the authorization; a
forged/unsigned invoke can't destroy. The destroy happens IN Forensic; only the bounded
outcome crosses. ZTIE never re-executes the artifact. The derived report survives in the Hub.

## Prerequisites (already live from earlier stories)
- **H.2 `ZtieDecisionSigningStack`** deployed in the Hub — signing key
  `arn:aws:kms:us-east-1:641628980935:key/3321e5b7-2ca3-42e3-b99c-9b9d83a45243`
  (`aws kms describe-key` = SIGN_VERIFY / ECC_NIST_P256 / ECDSA_SHA_256). Same key 4.6 used.
- A fully-processed intake whose raw artifact still exists in the Forensic artifact bucket,
  AND whose derived outputs (`findings/` / `runs/` / `traces/`) exist so the destroy has
  something to sweep. **Submit a FRESH throwaway intake for this test** (4.7 is destructive —
  do NOT reject an intake you want to keep). A `probe.yaml`-style artifact routed through both
  lanes is ideal (it leaves `findings/` + `runs/` + possibly `traces/`).
- **Optional (to exercise the chamber-terminate path):** kick off a detonation so an
  ephemeral EC2 is briefly live for the intake, then run the reject while it is still running
  (within the 5-min TTL). If no chamber is live, the run records `chamber: none_running` —
  still a valid pass (the common case; the TTL already reaped it).

## Ground rules
- Three CloudShell tabs (Hub / Forensic — the Hub also receives the outcome). `aws sts
  get-caller-identity` before EVERY block; a banner does not change the account.
- Feed commands ONE LINE AT A TIME. `/tmp` + shell vars wiped on recycle — re-set in-block.
- Region us-east-1, ambient creds (no `--profile`).
- Deploy-gap guard: after `cdk deploy`, do BOTH the ⛔ CODE-ASSET gate (STEP 1a) AND inspect
  the LIVE resource (the destroyer role must have **NO `dynamodb`** action + **NO
  `TRACKING_TABLE`** env — the whole point of RD-048).

---

## STEP 0 (all tabs) — accounts + the H.2 signing key + the public key

Confirm each tab's account with `aws sts get-caller-identity` (Hub `641628980935`, Forensic
`360999005254`).

**Hub tab** — capture the signing key ARN + export the public key (the destroyer embeds this):
```
KARN=$(aws cloudformation describe-stacks --stack-name ZtieDecisionSigningStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='DecisionSigningKeyArn'].OutputValue" --output text) ; KID=$(aws cloudformation describe-stacks --stack-name ZtieDecisionSigningStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='DecisionSigningKeyId'].OutputValue" --output text) ; echo "KARN=$KARN"
```
```
aws kms get-public-key --key-id "$KID" --region us-east-1 --query PublicKey --output text | base64 -d > /tmp/ztie_pub.der ; openssl pkey -pubin -inform DER -in /tmp/ztie_pub.der -out /tmp/ztie_pub.pem 2>/dev/null || openssl ec -pubin -inform DER -in /tmp/ztie_pub.der -pubout -out /tmp/ztie_pub.pem ; cat /tmp/ztie_pub.pem
```
Keep `/tmp/ztie_pub.pem` + `$KARN`. Also grab the Hub ingest queue coordinates + the tracking
table name (for STEP 6):
```
IQURL=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='IngestQueueUrl'].OutputValue" --output text) ; IQARN=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='IngestQueueArn'].OutputValue" --output text) ; echo "$IQURL" ; echo "$IQARN"
```

---

## STEP 1 (Forensic tab) — get the 4.7 code + deploy the destroyer + (deploy-gap) redeploy the Hub ingest

```
cd ~/ZTIE-Issues && git fetch origin -q && git checkout feature/story-4.7 && git reset --hard origin/feature/story-4.7 && git log --oneline -1
```
(Or `main` once the PR is merged.)
```
grep -n "HUB_PUBLIC_KEY_PEM\|dynamodb\|TerminateInstances" infra/lib/ztie-forensic-reject-stack.ts | head
```
Expect `HUB_PUBLIC_KEY_PEM` present, `TerminateInstances` present (tag-conditioned), and **NO
`dynamodb`** line (no Hub read).
```
cd ~/ZTIE-Issues/infra && rm -rf ~/.npm && mkdir -p ~/.npm-cache ~/.npm-tmp && TMPDIR=~/.npm-tmp npm install --no-audit --no-fund --cache ~/.npm-cache
```
Gather the Forensic artifact bucket coordinate:
```
ARTB=$(aws cloudformation describe-stacks --stack-name ZtieIntakeStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='ArtifactBucketName'].OutputValue" --output text) ; echo "ARTB=$ARTB"
```
Deploy the destroyer — pass the Hub public key as **SINGLE-LINE base64** (`hubPublicKeyPemBase64`;
a raw multi-line PEM truncates through `-c` — the 4.6 live defect), + the Hub ingest queue from
STEP 0:
```
cd ~/ZTIE-Issues/infra && TMPDIR=~/.npm-tmp npx cdk deploy ZtieForensicRejectStack --require-approval never -c artifactBucketName=$ARTB -c hubIngestQueueUrl=$IQURL -c hubIngestQueueArn=$IQARN -c hubPublicKeyPemBase64=$(base64 -w0 /tmp/ztie_pub.pem) -c trustedKeyIds=$KARN
```
Expect `✅ ZtieForensicRejectStack` + outputs `PdeRejectFunctionName` + `PdeRejectRoleArn`. Capture:
```
RFN=$(aws cloudformation describe-stacks --stack-name ZtieForensicRejectStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='PdeRejectFunctionName'].OutputValue" --output text) ; RROLE=$(aws cloudformation describe-stacks --stack-name ZtieForensicRejectStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='PdeRejectRoleArn'].OutputValue" --output text) ; echo "$RFN" ; echo "$RROLE"
```

**DEPLOY-GAP (Hub tab) — the new `disposition` RD-013 kind needs a Hub ingest redeploy.** 4.7
adds the 11th envelope kind; the LIVE `hub_ingest` validator will QUARANTINE a `disposition`
outcome until `ZtieHubTrackingStack` is redeployed with the new kind (the 4.6 `handoff`
lesson). Redeploy it BEFORE the live run:
```
cd ~/ZTIE-Issues/infra && TMPDIR=~/.npm-tmp npx cdk deploy ZtieHubTrackingStack --require-approval never
```
Then confirm the live ingest Lambda knows the kind (download the deployed zip + grep):
```
IFN=$(aws cloudformation describe-stack-resources --stack-name ZtieHubTrackingStack --region us-east-1 --query "StackResources[?ResourceType=='AWS::Lambda::Function' && contains(LogicalResourceId,'IngestValidator')].PhysicalResourceId" --output text) ; LOC=$(aws lambda get-function --function-name "$IFN" --region us-east-1 --query Code.Location --output text) ; curl -s "$LOC" -o /tmp/ingest.zip ; mkdir -p /tmp/ingest && (cd /tmp/ingest && unzip -oq /tmp/ingest.zip) ; grep -n 'name="disposition"\|"disposition"' /tmp/ingest/handler.py | head ; ls /tmp/ingest/disposition.contract.v1.json
```
Expect the `disposition` `_KindSpec` present + the bundled `disposition.contract.v1.json`.

### ⛔ STEP 1a — NON-SKIPPABLE post-deploy CODE-ASSET gate (the #1 2.4R/2.4S lesson)
Before ANY validation result is trusted, PROVE the live `pde_reject` Lambda runs THIS story's
code (never an env-var read; never trust the green `UPDATE_COMPLETE`). Download the deployed
zip + grep the source for 4.7's STRUCTURAL markers + a regression guard that no probe/diagnostic
marker rode along:
```
LOC=$(aws lambda get-function --function-name "$RFN" --region us-east-1 --query Code.Location --output text) ; curl -s "$LOC" -o /tmp/reject.zip ; mkdir -p /tmp/reject && (cd /tmp/reject && unzip -oq /tmp/reject.zip)
```
```
echo "== token-verify path ==" ; grep -n 'expected_decision="rejected"\|verify_decision\|HUB_PUBLIC_KEY_PEM' /tmp/reject/handler.py /tmp/reject/reject.py | head ; echo "== versioned-delete path ==" ; grep -n 'destroy_intake_prefixes\|_delete_all_versions_under_prefix\|DeleteMarkers\|list_object_versions' /tmp/reject/awsio.py | head ; echo "== chamber path ==" ; grep -n 'find_running_chamber\|terminate_chamber\|Ephemeral' /tmp/reject/awsio.py | head ; echo "== regression guard: NO probe/diagnostic marker ==" ; grep -rn 'ZTIE-PROBE\|DIAG-BEGIN\|TODO-REMOVE' /tmp/reject/ || echo "clean (no probe markers)"
```
Expect all three marker classes PRESENT and the probe grep `clean`. **A validation over an
asset missing these markers is INVALID — stop and redeploy the right code.**

### Post-deploy live verify (RD-048 — no Hub read)
```
ROLE=$(echo "$RROLE" | awk -F/ '{print $NF}') ; for P in $(aws iam list-role-policies --role-name "$ROLE" --query "PolicyNames" --output text); do aws iam get-role-policy --role-name "$ROLE" --policy-name "$P" --query "PolicyDocument.Statement[].{Sid:Sid,Action:Action}" --output json; done
```
Expect ONLY `s3:GetObject` / `s3:DeleteObject` / `s3:DeleteObjectVersion` / `s3:GetObjectVersion`
/ `s3:ListBucket` / `s3:ListBucketVersions` / `ec2:DescribeInstances` / `ec2:TerminateInstances`
(tag-conditioned) / `sqs:SendMessage` — **NO `dynamodb:*`, NO `bedrock`.**
```
aws lambda get-function-configuration --function-name "$RFN" --region us-east-1 --query "Environment.Variables" | grep -E "HUB_PUBLIC_KEY_PEM|TRUSTED_KEY_IDS|TRACKING_TABLE|NOVA_MODEL_ID" ; echo "(expect HUB_PUBLIC_KEY_PEM + TRUSTED_KEY_IDS present; NO TRACKING_TABLE, NO NOVA_MODEL_ID)"
```
Confirm the embedded PEM is the FULL key (the 4.6 truncation trap), not 27 bytes:
```
aws lambda get-function-configuration --function-name "$RFN" --region us-east-1 --query "Environment.Variables.HUB_PUBLIC_KEY_PEM" --output text | wc -c ; echo "(expect ~178+; a 27-char value = truncated PEM, redeploy with base64)"
```

---

## STEP 2 (Forensic tab) — snapshot the target intake BEFORE the reject

Pick the FRESH throwaway intake to reject (`$IID`) and its artifact key. Record what exists so
the destroy is provable:
```
IID=<the-fresh-intake-uuid> ; ARTB=$(aws cloudformation describe-stacks --stack-name ZtieIntakeStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='ArtifactBucketName'].OutputValue" --output text)
```
```
for P in intake findings runs traces ; do echo "== $P/$IID/ (versions) ==" ; aws s3api list-object-versions --bucket "$ARTB" --prefix "$P/$IID/" --region us-east-1 --query "{versions: length(Versions || \`[]\`), markers: length(DeleteMarkers || \`[]\`)}" ; done
```
Note the `intake/<id>/<filename>` key + its sha256 (the tracked hash — from the Hub item or
recompute here):
```
AKEY=$(aws s3api list-objects-v2 --bucket "$ARTB" --prefix "intake/$IID/" --region us-east-1 --query "Contents[0].Key" --output text) ; aws s3api get-object --bucket "$ARTB" --key "$AKEY" --region us-east-1 /tmp/art.bin >/dev/null ; SHA=$(python3 -c "import hashlib;print(hashlib.sha256(open('/tmp/art.bin','rb').read()).hexdigest())") ; echo "AKEY=$AKEY SHA=$SHA"
```
(Optional chamber path: confirm whether a live chamber exists for the intake.)
```
aws ec2 describe-instances --filters "Name=tag:IntakeId,Values=$IID" "Name=tag:Ephemeral,Values=true" "Name=instance-state-name,Values=pending,running,stopping,stopped" --region us-east-1 --query "Reservations[].Instances[].{id:InstanceId,state:State.Name}"
```

---

## STEP 3 (Hub tab) — sign a `rejected` decision token for the intake

```
ISSUED=$(python3 -c "import datetime;print(datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z'))")
```
Build the CANONICAL bytes exactly as the library does (`sort_keys=True, separators=(',',':')`
over the six token keys) + `kms:Sign` + base64 the signature. **Set `IID` + `SHA` to STEP-2's
values.**
```
python3 -c "import json; t={'contract_version':'1.0','intake_id':'$IID','decision':'rejected','sha256':'$SHA','issued_at':'$ISSUED','key_id':'$KARN'}; open('/tmp/token.json','w').write(json.dumps(t)); open('/tmp/canon.bin','wb').write(json.dumps(t,sort_keys=True,separators=(',',':')).encode()); print('token + canonical written')"
```
```
SIG_B64=$(aws kms sign --key-id "$KARN" --message fileb:///tmp/canon.bin --message-type RAW --signing-algorithm ECDSA_SHA_256 --region us-east-1 --query Signature --output text) ; echo "$SIG_B64" > /tmp/sig.b64 ; echo "signed (base64 sig $(wc -c < /tmp/sig.b64) chars)"
```
```
python3 -c "import json; tok=json.load(open('/tmp/token.json')); sig=open('/tmp/sig.b64').read().strip(); iid=tok['intake_id']; open('/tmp/invoke.json','w').write(json.dumps({'intake_id':iid,'decision_token':tok,'signature':sig,'artifact_s3_key':'$AKEY'})); print('invoke payload written')"
```
Copy `/tmp/invoke.json`'s content to the Forensic tab (small JSON, no secret).

---

## STEP 4 (Forensic tab) — the REJECT destroy (verify offline → destroy)

Put the STEP-3 payload at `/tmp/invoke.json` on the Forensic box, then:
```
RFN=$(aws cloudformation describe-stacks --stack-name ZtieForensicRejectStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='PdeRejectFunctionName'].OutputValue" --output text) ; aws lambda invoke --function-name "$RFN" --payload fileb:///tmp/invoke.json --cli-binary-format raw-in-base64-out --region us-east-1 /tmp/out.json >/dev/null ; python3 -c "import json;d=json.load(open('/tmp/out.json'));print('destroyed:',d.get('destroyed'),'outcome:',d.get('outcome'),'observed:',d.get('observed_decision'),'chamber:',d.get('chamber_state'));print('disposition:',json.dumps(d.get('disposition',{}).get('destroyed'),default=str))"
```
**Pass:** `destroyed: True`, `outcome: destroyed`, `observed: rejected`, `chamber:` either
`terminated` (a live host was found + killed) or `none_running`, and a `destroyed` block with
`artifact_versions_deleted` > 0 + `prefixes_cleared` listing the four prefixes.

### Confirm the artifact + derived outputs are GONE (all versions)
```
for P in intake findings runs traces ; do echo "== $P/$IID/ (should be 0/0) ==" ; aws s3api list-object-versions --bucket "$ARTB" --prefix "$P/$IID/" --region us-east-1 --query "{versions: length(Versions || \`[]\`), markers: length(DeleteMarkers || \`[]\`)}" ; done
```
**Pass:** every prefix now `versions: 0, markers: 0` (all versions + delete-markers gone — not a
tombstone).

### Confirm the chamber is gone (if one was live)
```
aws ec2 describe-instances --filters "Name=tag:IntakeId,Values=$IID" "Name=tag:Ephemeral,Values=true" --region us-east-1 --query "Reservations[].Instances[].{id:InstanceId,state:State.Name}"
```
**Pass:** no instance, or state `shutting-down`/`terminated`.

---

## STEP 5 (Forensic tab) — FAIL-SAFE proofs (nothing is destroyed without a valid signed reject)

**Use a DIFFERENT fresh throwaway intake `$IID2`** for each destructive-negative check (so a
refusal that correctly destroys NOTHING can be confirmed against an intake whose files still
exist). Snapshot its prefixes first (as STEP 2), invoke with a broken payload, then re-check the
prefixes are UNCHANGED and `destroyed: False`.

- **No token (INCONCLUSIVE HOLD):** invoke `{"intake_id":"<iid2>","artifact_s3_key":"intake/<iid2>/<f>"}` → `destroyed: False`, `outcome: held` — prefixes UNCHANGED.
- **Tampered signature:** flip one char in the base64 `signature` → `destroyed: False`, `outcome: refused_not_rejected` — prefixes UNCHANGED.
- **`accepted` token (wrong decision):** sign a token with `decision:"accepted"` → `destroyed: False`, `outcome: refused_not_rejected` (an accept does not authorize a destroy) — prefixes UNCHANGED.
- **sha-mismatch:** sign a `rejected` token whose `sha256` is `b*64` → `destroyed: False`, `outcome: refused_hash_mismatch` — prefixes UNCHANGED.
- **Stale:** sign a `rejected` token with `issued_at` `2000-01-01T00:00:00Z` → `destroyed: False`, `outcome: refused_not_rejected` — prefixes UNCHANGED.
- **Untrusted key:** (optional) sign with a different key / set `key_id` to a rogue value → `destroyed: False`, `outcome: refused_not_rejected` — prefixes UNCHANGED.

After the negatives, confirm `$IID2`'s prefixes STILL have their versions (nothing was destroyed
by any refusal/hold).

---

## STEP 6 (Hub tab) — the outcome crossed (bounded, verdict-free); no Hub read happened

```
TABLE=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='TrackingTableName'].OutputValue" --output text) ; aws dynamodb get-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --region us-east-1 --query "{outcome:Item.disposition_outcome.S, disposition:Item.disposition.M}"
```
**Pass:** `outcome: destroyed`; the `disposition` map carries `observed_decision: rejected`,
`hash_verified: true`, `report_survives: true`, `chamber_state`, a `destroyed` block — and NO
`verdict`/`safe`/`approved`/`forward` key.
```
aws dynamodb get-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --region us-east-1 --query "Item.disposition" --output json > /tmp/do.json ; python3 -c "import json;s=json.dumps(json.load(open('/tmp/do.json')));banned=['\"verdict\"','\"safe\"','\"approved\"','\"forward\"','\"malicious\"','\"pass_fail\"','\"clean\"'];print('FAIL' if any(b in s for b in banned) else 'OK: no effective-verdict key')"
```
**The report survives:** confirm the Hub item still carries its Phase-1→4 derived record
(`combined_event`/`correlation_result`/`scoring_result`/`remediation_result`/`verdict_result`,
etc.) — 4.7 destroyed ONLY the Forensic blast-zone artifact + chamber, never the Hub record.
```
aws dynamodb get-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --region us-east-1 --query "keys(Item)" --output json
```

---

## STEP 7 — paste back for the record + the RD-054 evidence folder
Paste back, VERBATIM: STEP 1a the CODE-ASSET grep (all three marker classes + probe-clean) +
the role policy (no dynamodb) + env (no TRACKING_TABLE, full PEM length); STEP 4 the destroy
output + the four prefixes now 0/0 + the chamber gone; STEP 5 the six FAIL-SAFE results + the
UNCHANGED `$IID2` prefixes; STEP 6 the `destroyed` outcome map + the no-banned-key line + the
surviving Hub record keys. The executor records these + flips **4.7 → ✅** (paired commit),
clears 4.7 from the Validation Debt Register, and — because 4.7 is `[sec-boundary]` — authors +
retains `docs/validation-evidence/4.7/attempt-<n>/EVIDENCE.md` with the four RD-054 marker
classes (positive-exercise: `artifact_versions_deleted` count / `destroyed`; proof-of-absence:
prefixes `0/0` + refusals destroyed nothing; human attestation: "attested by …"; provenance:
`intake_id` + the validated commit SHA). On a FAIL, 4.7 stays 🟡; fix + re-validate once.

## If something fails
- **`rejected` destroy refuses with `refused_not_rejected` + "bad_signature"** — the canonical
  bytes signed in STEP 3 differ from what the library canonicalizes, OR the embedded
  `HUB_PUBLIC_KEY_PEM` is truncated. Confirm STEP 3 used `sort_keys=True, separators=(',',':')`
  over exactly the six token keys, and STEP 1's PEM-length check showed the FULL key (redeploy
  with `hubPublicKeyPemBase64` if 27 bytes). `aws kms verify` of `/tmp/canon.bin` isolates
  signing-half vs verify-half.
- **Destroyer role still shows `dynamodb`** — the 4.7 code did not deploy (stale checkout /
  wrong branch). Re-checkout + redeploy; the whole point is no Hub read.
- **`disposition` outcome quarantined / Hub item field null** — the Hub ingest stack was not
  redeployed for the new `disposition` kind (the deploy-gap). Redeploy `ZtieHubTrackingStack`
  (STEP 1), re-invoke, re-check.
- **`AccessDenied` on the S3 delete / `TerminateInstances`** — the destroyer role condition did
  not match; confirm the intake's objects are under the four granted prefixes and the chamber
  carries `Ephemeral=true`+`Project=ZTIE` tags.
- **404 / artifact already gone** — 4.7 returns `outcome: held` (idempotent, nothing to
  destroy) rather than erroring; pick a fresh intake whose artifact still exists to prove the
  destroy path.
