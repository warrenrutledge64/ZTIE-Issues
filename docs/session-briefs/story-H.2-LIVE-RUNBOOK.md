# Story H.2 — LIVE sign/verify crossing validation (stakeholder) — RD-048 / RD-049

> **This is the ONLY live part of H.2, and only YOU can do it** (the executor has no AWS
> creds). You deploy the Hub decision-signing KMS key, **export its public key**, then
> prove the crossing: the **Hub SIGNS** a real `decision.token.v1` with `kms:Sign`, and the
> **spoke VERIFIES it OFFLINE** against the exported public key (no call to the Hub / Hub
> KMS) and would act — AND every **fail-closed** branch (bad signature / wrong decision /
> sha mismatch / stale / wrong key) **refuses**. The executor records your output verbatim.
> **Nothing is recorded on inference.** On a pass the executor flips **H.2 → ✅** and the
> 4.6 rework (verify a Hub-signed `accepted` token → push) is unblocked.

## What H.2 is (RD-048/RD-049 — so the check is meaningful)

H.2 builds the shared primitive 4.6/4.7/4.4 consume: the **Hub signs** an authenticated
decision, the **spoke verifies it OFFLINE**. No spoke ever reads into the Hub (RD-048); the
signature is what makes a handed-out decision trustworthy so a forged invoke can't fake it.

- **`decision.token.v1`** — a bounded allow-list token: `contract_version`, `intake_id`,
  `decision` (`accepted`|`rejected`), `sha256` (binds to exact bytes), `issued_at`
  (freshness), `key_id`. Canonical signed bytes = `json.dumps(token, sort_keys=True,
  separators=(",",":"))` over exactly those keys.
- **Verify-then-act (fail-closed):** the spoke acts ONLY if the signature verifies against
  the trusted public key AND the decision is the expected value AND `token.sha256` == the
  recomputed artifact sha256 AND the token is fresh AND `key_id` is trusted.
- **KMS asymmetric** ECC_NIST_P256 / ECDSA_SHA_256; only the Hub holds `kms:Sign`; the
  spoke verifies **offline** with the exported public key (no `kms:Verify`, no Hub call).

## Ground rules

- **This is primarily a HUB action (641628980935)** — the signing key + `kms:Sign` +
  `get-public-key` are all in the Hub. The "spoke verify" step can run **anywhere** (it is
  offline crypto against the public key) — for this validation you can even run it in the
  Hub CloudShell; it makes **no** AWS calls.
- **Run `aws sts get-caller-identity` before every block.**
- **Feed commands ONE LINE AT A TIME.** `/tmp` + shell vars are WIPED on a CloudShell
  recycle — re-set them in the same block.
- **Region us-east-1**, ambient creds (no `--profile`).
- **Deploy-gap guard:** after `cdk deploy`, inspect the LIVE key (`describe-key`) — confirm
  it is asymmetric SIGN_VERIFY, not just the green line.

---

## STEP 0 (Hub tab) — get the code + confirm the checkout carries H.2

```
aws sts get-caller-identity
```
Expect `641628980935`.
```
cd ~/ZTIE-Issues && git fetch origin -q && git checkout feature/story-H.2 && git reset --hard origin/feature/story-H.2 && git log --oneline -1
```
(If H.2's PR is merged, use `git checkout main && git reset --hard origin/main`.)
```
ls lib/decision_auth && grep -n "ZtieDecisionSigningStack" infra/bin/ztie-infra.ts | head
```
Expect `canonical.py` / `verify.py` / `signature.py` / `decision.token.v1.json` +
`requirements.txt`, and the stack wired in the bin.

---

## STEP 1 (Hub tab) — deploy the signing key + verify it live

Install deps (space-safe flags — CloudShell $HOME is small):
```
cd ~/ZTIE-Issues/infra && rm -rf ~/.npm && mkdir -p ~/.npm-cache ~/.npm-tmp && TMPDIR=~/.npm-tmp npm install --no-audit --no-fund --cache ~/.npm-cache
```
Deploy (scope `kms:Sign` to yourself — your SSO role ARN — for the manual sign; get it
from `aws sts get-caller-identity` `Arn`, use the role ARN form
`arn:aws:iam::641628980935:role/<name>` if you prefer, or omit `-c signerPrincipalArn` to
fall back to account-root):
```
cd ~/ZTIE-Issues/infra && TMPDIR=~/.npm-tmp npx cdk deploy ZtieDecisionSigningStack --require-approval never
```
Expect `✅ ZtieDecisionSigningStack` with outputs `DecisionSigningKeyArn` +
`DecisionSigningKeyId`. Capture:
```
KID=$(aws cloudformation describe-stacks --stack-name ZtieDecisionSigningStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='DecisionSigningKeyId'].OutputValue" --output text) ; KARN=$(aws cloudformation describe-stacks --stack-name ZtieDecisionSigningStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='DecisionSigningKeyArn'].OutputValue" --output text) ; echo "$KID" ; echo "$KARN"
```
Verify the LIVE key is asymmetric SIGN_VERIFY (not just the green line):
```
aws kms describe-key --key-id "$KID" --region us-east-1 --query "KeyMetadata.{Usage:KeyUsage,Spec:KeySpec,SigningAlgs:SigningAlgorithms}"
```
Expect `Usage: SIGN_VERIFY`, `Spec: ECC_NIST_P256`, `SigningAlgs: ["ECDSA_SHA_256"]`.

---

## STEP 2 (Hub tab) — export the public key (this is what the spoke embeds)

```
KID=<paste-DecisionSigningKeyId> ; aws kms get-public-key --key-id "$KID" --region us-east-1 --query PublicKey --output text | base64 -d > /tmp/ztie_pub.der ; openssl pkey -pubin -inform DER -in /tmp/ztie_pub.der -out /tmp/ztie_pub.pem 2>/dev/null || openssl ec -pubin -inform DER -in /tmp/ztie_pub.der -pubout -out /tmp/ztie_pub.pem ; echo "--- public key (PEM) ---" ; cat /tmp/ztie_pub.pem
```
This PEM is **not a secret** — it is the exact bytes a spoke embeds at deploy to verify
offline. Keep `/tmp/ztie_pub.pem` for STEP 4.

---

## STEP 3 (Hub tab) — the Hub SIGNS a real decision token

Build a canonical `decision.token.v1` for a real intake (reuse a fully-processed
`intake_id` + its `sha256` from the Hub tracking table — the same
`891cb78f-…` / `cd0429…` pair works), then `kms:Sign` its canonical bytes:
```
IID=891cb78f-fd35-4045-81d6-030d75d9c83e ; SHA=cd04299d8e29601f5425054e0470a71f255fb19a7d2fe3734bcb6213f27208f0 ; KARN=<paste-DecisionSigningKeyArn> ; ISSUED=$(python3 -c "import datetime;print(datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z'))")
```
Build the CANONICAL bytes exactly as the library does (sorted keys, no whitespace) and sign:
```
python3 -c "import json,sys; t={'contract_version':'1.0','intake_id':'$IID','decision':'accepted','sha256':'$SHA','issued_at':'$ISSUED','key_id':'$KARN'}; open('/tmp/token.json','w').write(json.dumps(t)); open('/tmp/canon.bin','wb').write(json.dumps(t,sort_keys=True,separators=(',',':')).encode()); print('canonical bytes written')"
```
```
aws kms sign --key-id "$KARN" --message fileb:///tmp/canon.bin --message-type RAW --signing-algorithm ECDSA_SHA_256 --region us-east-1 --query Signature --output text | base64 -d > /tmp/sig.der ; echo "signed -> /tmp/sig.der ($(wc -c < /tmp/sig.der) bytes)"
```

---

## STEP 4 (any tab — OFFLINE, no AWS) — the spoke VERIFIES + every fail-closed branch

> This is the spoke's job. It uses ONLY `/tmp/ztie_pub.pem` (the embedded public key),
> `/tmp/token.json`, and `/tmp/sig.der` — **no AWS calls**. `cryptography` must be available
> here; CloudShell's system Python usually has it (`python3 -c "import cryptography"`); if
> not, `pip install --user cryptography` in the CloudShell (this is the operator box, not
> the offline build sandbox).

Drive the real verify library against the real signature:
```
cd ~/ZTIE-Issues/lib/decision_auth && python3 -c "
import json,sys
import canonical, verify, signature
tok=json.load(open('/tmp/token.json'))
sig=open('/tmp/sig.der','rb').read()
pub=open('/tmp/ztie_pub.pem','rb').read()
def v(msg,s,p): return signature.verify_ecdsa_p256_sha256(msg,s,p)
r=verify.verify_decision(token=tok,signature=sig,public_key_pem=pub,verify_signature=v,expected_decision='accepted',artifact_sha256=tok['sha256'],trusted_key_ids=[tok['key_id']])
print('VALID token ->', r.ok, r.code, r.reason)
# fail-closed branches:
bad=dict(tok); bad['sha256']='b'*64
print('sha-mismatch ->', verify.verify_decision(token=tok,signature=sig,public_key_pem=pub,verify_signature=v,expected_decision='accepted',artifact_sha256='b'*64,trusted_key_ids=[tok['key_id']]).code)
print('wrong-decision ->', verify.verify_decision(token=tok,signature=sig,public_key_pem=pub,verify_signature=v,expected_decision='rejected',artifact_sha256=tok['sha256'],trusted_key_ids=[tok['key_id']]).code)
print('untrusted-key ->', verify.verify_decision(token=tok,signature=sig,public_key_pem=pub,verify_signature=v,expected_decision='accepted',artifact_sha256=tok['sha256'],trusted_key_ids=['rogue']).code)
tampered=sig[:-1]+bytes([sig[-1]^1])
print('bad-signature ->', verify.verify_decision(token=tok,signature=tampered,public_key_pem=pub,verify_signature=v,expected_decision='accepted',artifact_sha256=tok['sha256'],trusted_key_ids=[tok['key_id']]).code)
import datetime; old=dict(tok); old['issued_at']='2000-01-01T00:00:00Z'
# re-sign not needed for the stale check demo since signature won't match the mutated token;
# instead show freshness on the VALID token with a tiny max_age:
print('stale ->', verify.verify_decision(token=tok,signature=sig,public_key_pem=pub,verify_signature=v,expected_decision='accepted',artifact_sha256=tok['sha256'],trusted_key_ids=[tok['key_id']],max_age_seconds=0).code)
"
```

**Pass criteria (all must hold):**
1. `VALID token -> True ok all checks passed` — the real Hub signature verifies OFFLINE
   against the exported public key.
2. `sha-mismatch -> sha_mismatch` (a token for other bytes is refused).
3. `wrong-decision -> wrong_decision` (an `accepted` token can't authorize a `rejected`
   action).
4. `untrusted-key -> untrusted_key`.
5. `bad-signature -> bad_signature` (a one-bit-flipped signature is refused — proves the
   crypto is real, not stubbed).
6. `stale -> stale` (freshness bound fires).

> **No spoke→Hub call anywhere in STEP 4** — verification used only the local public key +
> token + signature. That is the RD-048 property proven live.

---

## STEP 5 — paste back for the record

Paste back, VERBATIM: the STEP 0 `git log -1` + `ls`/`grep`; the STEP 1 `describe-key`
output (SIGN_VERIFY / ECC_NIST_P256 / ECDSA_SHA_256) + the key ARN/id; a note that STEP 2
exported the PEM; the STEP 3 sign result (bytes); and the STEP 4 six-line output (VALID +
the five refusals). The executor records these into the RUNBOOK H.2 detail, flips
**H.2 → ✅**, and the 4.6 rework is unblocked. On a FAIL, H.2 stays 🟡; fix + re-validate
once.

## If something fails
- **`describe-key` not SIGN_VERIFY / ECC_NIST_P256** — wrong stack/key; re-check STEP 1.
- **`aws kms sign` AccessDenied** — your principal is not the `signerPrincipalArn` (or the
  account-root fallback isn't in effect); redeploy with `-c signerPrincipalArn=<your role ARN>`.
- **`VALID token -> False bad_signature`** — the canonical bytes signed (STEP 3) differ from
  what the library canonicalizes. Confirm STEP 3 used `sort_keys=True, separators=(',',':')`
  over exactly the six token keys (that IS the library's `canonical_bytes`). This is the
  thing to get exactly right — a real defect if it can't be made to verify.
- **`import cryptography` fails in STEP 4** — install it on the operator box
  (`pip install --user cryptography`); it is NOT the offline build sandbox.
- **A refusal branch returns `ok=True`** — a real H.2 defect (the gate must be fail-closed).
  Capture it; keep H.2 🟡 and fix.
