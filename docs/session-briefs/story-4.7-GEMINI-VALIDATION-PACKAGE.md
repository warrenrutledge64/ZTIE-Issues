# Gemini Independent-Validation Package — Story 4.7 (PR #211)

> **Filled from [`../GEMINI_VALIDATION_PACKAGE_TEMPLATE.md`](../GEMINI_VALIDATION_PACKAGE_TEMPLATE.md) for the 4.7 live validation.**
> Story 4.7 = REJECT → destroy the untrusted artifact + its detonation chamber in Forensic;
> INCONCLUSIVE → hold. Built + offline-proven on **PR #211** (branch `feature/story-4.7`),
> status **🟡** — awaiting this single recorded live pass.
>
> **⛔ RD-055 (Zero-Trust Validation Supply Chain).** Kiro's entire handoff is the **PR
> number + objective pointers below** — Kiro supplies NO diff, no diff-fetch you didn't run
> yourself, no code snippets, and does NOT author the requirement or the runbook. **YOU
> (stakeholder) fetch the diff + full source directly from the GitHub API; GEMINI authors
> the DoD + runbook blind.** If the diff or the requirement reached Gemini via Kiro, the
> pass is VOID.
>
> **How to use:** fill the `<<< REQUIREMENT >>>` slot in Part 0 in YOUR OWN WORDS, then paste
> the whole Part-0 fenced block into a FRESH Gemini chat. Part A2 is your account-labeled
> operator command set (Gemini never sees it). This is a `[sec-boundary]` story — a PASS
> must rest on RETAINED raw evidence (RD-054), not testimony.

---

## FLOW MAP — the self-driving baton (do these in order; each names the NEXT)

> **Audience boundary:** **Part 0 is the ONLY thing Gemini sees.** Parts A2 / notes are the
> operator's reference.

```
STEP 0  Paste Part 0 into a FRESH Gemini chat; fill the <<< requirement >>> in your words.
          Gemini replies: "run the fetch commands and paste the output."        ▶ STEP 1
STEP 1  Run Part A2 BLOCK 1 (diff) + BLOCK 2 (full source @ SHA). Paste output to Gemini.  ▶ STEP 2
STEP 2  Gemini returns: adversarial review + its OWN DoD + a numbered live runbook.  ▶ STEP 3
STEP 3  Run the live runbook (Part A2 has the account-labeled commands): deploy (+ Hub
          ingest redeploy) → ⛔ code-asset gate → sign a rejected token → destroy → prove
          the fail-safe branches → read the crossed outcome.                    ▶ STEP 4
STEP 4  Paste the live raw output to Gemini → SEALED VERDICT (PASS/FAIL/INCONCLUSIVE).  ▶ STEP 5
STEP 5  On PASS: gather retained evidence + your named attestation, hand the sealed verdict +
          evidence to KIRO → Kiro records + flips 4.7 ✅ + authors docs/validation-evidence/4.7/.
          On INCONCLUSIVE/FAIL: 4.7 stays 🟡; fix + re-run from STEP 3.
```

---

## Part 0 — The cold-start KICKOFF BLOCK (paste this whole block into a fresh Gemini chat)

> Fill only the `<<< REQUIREMENT (your own words) >>>` block. Everything else is an objective
> pointer or a fetch command Kiro is allowed to supply. Do NOT let Kiro fill the requirement.

```
You are the INDEPENDENT VALIDATOR (RD-052/053/054/055) for the ZTIE project — subject:
Story 4.7 (REJECT -> destroy the untrusted artifact + its detonation chamber in the Forensic
account; INCONCLUSIVE -> hold). The build agent (Kiro) wrote this code; you did NOT. Author
your OWN Definition of Done and a numbered, soup-to-nuts live runbook, and try to BREAK the
change — do not confirm the happy path. I (the stakeholder) run everything on live AWS and
read the raw output; you never touch the live system, only what I paste you. Kiro is a
write-only scribe at the end; it authored none of your rubric.

ZERO-TRUST ON THE COMMANDS THEMSELVES. Every command I give you (and every command in the
runbook you author) was written by the BUILDER or me — do NOT trust that it collects ENOUGH.
Before you rely on any command set, ANALYZE IT FOR EFFICACY: does it actually surface the
evidence needed to prove/break the requirement, or could a real defect hide in what it does
NOT capture (a delete that tombstones instead of removing all versions, a describe that
misses a still-running instance, a query that reads one field, a head -N that clips the
proof)? Then PROPOSE ADDITIONAL COMMANDS for more robust collection — wider/independent
captures, corroborating reads, and negative probes that would expose a fake or partial
result. Treat the supplied commands as a floor, never a ceiling.

STEP 1 — Tell me to fetch the raw code, then WAIT for me to paste it. The command I run in
AWS CloudShell (gh is not available there) is (the first line LOOKS like it hangs — it is a
SILENT prompt: nothing echoes as I paste the token; I paste it + press Enter):

    read -rsp "Paste GH token, then press Enter (nothing will show): " GH_TOKEN && export GH_TOKEN && echo
    echo "token length: ${#GH_TOKEN}"      # confirms it took — prints only a number, not the token
    curl -sSL -H "Authorization: Bearer $GH_TOKEN" -H "Accept: application/vnd.github.v3.diff" \
      https://api.github.com/repos/warrenrutledge64/ZTIE-Issues/pulls/211
    unset GH_TOKEN

STEP 1.5 — FULL CONTEXT FETCH (mandatory — a diff is NOT enough). A diff hides contextual
leaks and execution flaws in the UNCHANGED surrounding code. You may NOT sign off on this
boundary-crossing / destructive logic from the diff alone. Have me fetch the FULL raw source
of every script the PR touched, pinned to the exact commit SHA (again the first line is a
SILENT token prompt — nothing echoes; paste + Enter):

    read -rsp "Paste GH token, then press Enter (nothing will show): " GH_TOKEN && export GH_TOKEN && echo
    echo "token length: ${#GH_TOKEN}"
    SHA=3e73f4b593e666d3a2fcc31249f398769a97a70d     # PR #211 branch tip (feature/story-4.7); pin every fetch to this
    for f in \
      lambdas/pde_reject/handler.py \
      lambdas/pde_reject/reject.py \
      lambdas/pde_reject/awsio.py \
      lambdas/pde_reject/verify.py \
      lambdas/pde_reject/canonical.py \
      lambdas/pde_reject/signature.py \
      lambdas/pde_reject/disposition.contract.v1.json \
      lambdas/hub_ingest/handler.py \
      infra/lib/ztie-forensic-reject-stack.ts \
      infra/bin/ztie-infra.ts ; do
      echo "===== $f @ $SHA ====="
      curl -sSL -H "Authorization: Bearer $GH_TOKEN" -H "Accept: application/vnd.github.v3.raw" \
        "https://api.github.com/repos/warrenrutledge64/ZTIE-Issues/contents/$f?ref=$SHA"
      echo
    done
    unset GH_TOKEN

If you find a file whose FULL context you need that I did not list, NAME it and have me fetch
it the same way before you write the DoD. Do not verdict on any file you have only seen as a
diff. (Review the ACTUAL diff AND the full raw files I paste — not my summary.)

PLAIN REQUIREMENT (my own words — the one anchor neither AI authored):
<<< REQUIREMENT (your own words): what 4.7 must actually DO on a human REJECT vs INCONCLUSIVE,
what "destroyed" must mean for a versioned artifact + its detonation chamber + its derived
Forensic outputs, the trust boundary it must never cross (the Forensic side must NOT read the
Hub; it must act only on a Hub-SIGNED reject decision verified OFFLINE — never on any advisory
recommendation), and the fail-safe failure modes it must survive (no token / bad signature /
an ACCEPTED token / hash mismatch / stale / untrusted key -> nothing destroyed; INCONCLUSIVE
holds). Replace this whole line. >>>

FACTS SHEET (objective — lookups, not a rubric):
- Accounts / IDs: Hub 641628980935 (signs the decision) ; Forensic 360999005254 (runs the
  destroyer + holds the artifact + chamber) ; region us-east-1. The bounded outcome crosses
  back to the Hub.
- Hub decision-signing key (H.2, already live): ARN
  arn:aws:kms:us-east-1:641628980935:key/3321e5b7-2ca3-42e3-b99c-9b9d83a45243
  (SIGN_VERIFY / ECC_NIST_P256 / ECDSA_SHA_256). The Forensic destroyer embeds this key's
  PUBLIC half and verifies OFFLINE.
- New this story: stack ZtieForensicRejectStack (Forensic) -> Lambda pde_reject ; a NEW
  RD-013 crossing kind "disposition" added to the Hub ingest validator (lambdas/hub_ingest).
- Deploy order (deploy-gap — MUST): (1) deploy ZtieForensicRejectStack in Forensic, passing
  the Hub public key as SINGLE-LINE base64 (a raw multi-line PEM truncates to a 27-byte
  header and the happy path fail-closes bad_signature); (2) REDEPLOY ZtieHubTrackingStack in
  the Hub so the ingest validator knows the new "disposition" kind (else the crossed outcome
  is quarantined). Verify BOTH by dumping the live resource, never a green UPDATE_COMPLETE.
- CODE-ASSET gate (the #1 2.4R/2.4S lesson — REQUIRE it before any verdict): download the
  DEPLOYED pde_reject zip (aws lambda get-function -> Code.Location -> curl -> unzip) and grep
  the SOURCE for this story's structural markers, NOT env vars: verify_decision /
  expected_decision="rejected" / HUB_PUBLIC_KEY_PEM (token-verify) ; destroy_intake_prefixes /
  DeleteMarkers / list_object_versions (versioned-delete) ; find_running_chamber /
  terminate_chamber (chamber) ; PLUS a regression guard that NO probe/diagnostic marker rode
  along (grep clean for ZTIE-PROBE / DIAG-BEGIN). A validation over an asset missing these is
  INVALID.
- How to submit a test input + where to read the result: submit a FRESH THROWAWAY intake to
  the Forensic intake API (this story DESTROYS — never reject an intake you want to keep),
  let it process so it has an artifact under intake/<id>/ + derived findings/ runs/ traces/
  (and optionally a live ephemeral EC2 for the intake, tagged IntakeId + Ephemeral=true, to
  exercise the terminate path within its 5-min TTL). Sign a "rejected" decision.token.v1 in
  the Hub (aws kms sign --message-type RAW --signing-algorithm ECDSA_SHA_256 over
  json.dumps(token, sort_keys=True, separators=(",",":")) of exactly the six keys
  contract_version/intake_id/decision/sha256/issued_at/key_id), then invoke pde_reject in
  Forensic with {intake_id, decision_token, signature, artifact_s3_key}. Read the result from
  the invoke response AND from Forensic S3 (the four prefixes should be gone — 0 versions +
  0 delete-markers) AND from EC2 (chamber terminated/none). The bounded "disposition" outcome
  crosses to the Hub tracking item (disposition_outcome / disposition map); confirm no
  verdict/safe/approved/forward/malicious/pass_fail/clean key, and that the Hub's derived
  report record SURVIVES.
- Code under test: PR #211 (branch feature/story-4.7). Ask me for the exact head SHA and pin
  every fetch to it.

DELIVER, IN THIS ORDER:
1. Adversarial review of the diff + full source vs. the requirement — every way to destroy
   WITHOUT a genuine signed reject, every way a refusal could still delete something, every
   spoke->Hub read, every version/marker a delete could leave behind, any chamber it could
   miss or wrongly terminate; flag anything you cannot verify from the diff alone.
2. Your OWN Definition of Done (derived from the requirement, NOT copied from the builder),
   including the adversarial cases. This is a SECURITY BOUNDARY + a DESTRUCTIVE action, so the
   DoD MUST require: (a) a POSITIVE live exercise — a genuine signed "rejected" token actually
   DESTROYS (all object versions + delete-markers gone across the four prefixes; a live
   chamber terminated or provably none) ; (b) the FAIL-SAFE branches proven from every angle,
   each against a FRESH intake whose files remain UNCHANGED after the refusal (no token=hold /
   bad sig / accepted / sha-mismatch / stale / untrusted -> NOTHING destroyed) ; (c) the live
   destroyer role has NO dynamodb + env has NO TRACKING_TABLE (no spoke->Hub read) ; (d) a
   human reads the RAW crossed outcome + the RAW S3/EC2 state ; (e) RETAINED raw evidence in
   docs/validation-evidence/4.7/. A "the Lambda didn't error" result is INCONCLUSIVE, never a
   PASS; offline tests support but never substitute.
3. Soup-to-nuts runbook — number every step, the exact command, and exactly what LITERAL
   output proves pass vs fail (aws sts get-caller-identity per block; the two-part deploy +
   the CODE-ASSET gate + the env/role checks; sign; invoke; read S3 + EC2 + the Hub outcome).
   For EACH data-collection step, first WEIGH the supplied command's efficacy (what could hide
   in what it does not capture) and ADD any stronger/corroborating/negative command needed.
4. What only a HUMAN should sign off (this destroys an artifact + crosses the RD-013 boundary)
   — two LLMs agreeing is not sufficient.
5. A sealed verdict block after I paste the raw output: VERDICT: PASS | FAIL | INCONCLUSIVE,
   each DoD item marked with its literal evidence line, any human sign-off outstanding.
6. An evidence manifest — the exact RAW artifacts I must RETAIN so the pass is auditable
   (the destroy counts + the emptied prefixes listing + the chamber state + the crossed
   disposition map + intake_id/commit-SHA provenance + a named human attestation).
7. THE RUNBOOK AS A DOWNLOADABLE FILE (fixed format). Output your STEP-3 runbook as ONE
   self-contained fenced code block I can copy straight into a file — no prose around it.
   First line inside the block MUST be
   `<!-- FILE: docs/session-briefs/story-4.7-LIVE-RUNBOOK.md -->` and the body MUST follow the
   fixed structure (Ground rules / STEP 0 Get the code / STEP 1..N numbered live steps /
   Definition of Done / Verdict recording).

Ask me for any value you need rather than guessing. Begin with STEP 1.
```

---

## Part A2 — Operator command set (account-labeled; Gemini never sees this — it's YOUR reference)

> Your backup for the live-run blocks. Gemini's authored runbook is authoritative; use these to
> execute it. `aws sts get-caller-identity` before EVERY block; region `us-east-1`; feed one
> line at a time; `/tmp` + shell vars wiped on a CloudShell recycle.

### BLOCK 1 — fetch the diff (any tab) — for STEP 1
```
read -rsp "Paste GH token, then press Enter (nothing will show): " GH_TOKEN && export GH_TOKEN && echo
echo "token length: ${#GH_TOKEN}"
curl -sSL -H "Authorization: Bearer $GH_TOKEN" -H "Accept: application/vnd.github.v3.diff" \
  https://api.github.com/repos/warrenrutledge64/ZTIE-Issues/pulls/211 | tee /tmp/4.7.diff
# head SHA (pin STEP 1.5 to this):
curl -sSL -H "Authorization: Bearer $GH_TOKEN" -H "Accept: application/vnd.github+json" \
  https://api.github.com/repos/warrenrutledge64/ZTIE-Issues/pulls/211 | grep -m1 '"sha"'
unset GH_TOKEN
```

### BLOCK 2 — full source @ SHA (any tab) — for STEP 1.5
Use the `for f in … ; do … done` loop in Part 0 STEP 1.5 (paths already listed), `SHA=3e73f4b593e666d3a2fcc31249f398769a97a70d`.

### BLOCK 3 — Forensic deploy (Forensic tab `360999005254`) — for the runbook's deploy step
```
aws sts get-caller-identity   # expect 360999005254
cd ~/ZTIE-Issues && git fetch origin -q && git checkout feature/story-4.7 && git reset --hard origin/feature/story-4.7 && git log --oneline -1
# Hub public key -> /tmp/ztie_pub.pem must already exist from the Hub tab (see BLOCK 5).
ARTB=$(aws cloudformation describe-stacks --stack-name ZtieIntakeStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='ArtifactBucketName'].OutputValue" --output text)
KARN=arn:aws:kms:us-east-1:641628980935:key/3321e5b7-2ca3-42e3-b99c-9b9d83a45243
# IQURL/IQARN come from the Hub tab (ZtieHubTrackingStack outputs IngestQueueUrl/IngestQueueArn).
cd ~/ZTIE-Issues/infra && rm -rf ~/.npm && mkdir -p ~/.npm-cache ~/.npm-tmp && TMPDIR=~/.npm-tmp npm install --no-audit --no-fund --cache ~/.npm-cache
TMPDIR=~/.npm-tmp npx cdk deploy ZtieForensicRejectStack --require-approval never \
  -c artifactBucketName=$ARTB -c hubIngestQueueUrl=<IQURL> -c hubIngestQueueArn=<IQARN> \
  -c hubPublicKeyPemBase64=$(base64 -w0 /tmp/ztie_pub.pem) -c trustedKeyIds=$KARN
RFN=$(aws cloudformation describe-stacks --stack-name ZtieForensicRejectStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='PdeRejectFunctionName'].OutputValue" --output text)
RROLE=$(aws cloudformation describe-stacks --stack-name ZtieForensicRejectStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='PdeRejectRoleArn'].OutputValue" --output text)
echo "$RFN" ; echo "$RROLE"
```

### BLOCK 4 — ⛔ CODE-ASSET gate + role/env verify (Forensic tab) — REQUIRED before any verdict
```
LOC=$(aws lambda get-function --function-name "$RFN" --region us-east-1 --query Code.Location --output text) ; curl -s "$LOC" -o /tmp/reject.zip ; mkdir -p /tmp/reject && (cd /tmp/reject && unzip -oq /tmp/reject.zip)
grep -n 'expected_decision="rejected"\|verify_decision\|HUB_PUBLIC_KEY_PEM' /tmp/reject/handler.py /tmp/reject/reject.py | head
grep -n 'destroy_intake_prefixes\|_delete_all_versions_under_prefix\|DeleteMarkers\|list_object_versions' /tmp/reject/awsio.py | head
grep -n 'find_running_chamber\|terminate_chamber\|Ephemeral' /tmp/reject/awsio.py | head
grep -rn 'ZTIE-PROBE\|DIAG-BEGIN\|TODO-REMOVE' /tmp/reject/ || echo "clean (no probe markers)"
ROLE=$(echo "$RROLE" | awk -F/ '{print $NF}') ; for P in $(aws iam list-role-policies --role-name "$ROLE" --query "PolicyNames" --output text); do aws iam get-role-policy --role-name "$ROLE" --policy-name "$P" --query "PolicyDocument.Statement[].{Sid:Sid,Action:Action}" --output json; done
aws lambda get-function-configuration --function-name "$RFN" --region us-east-1 --query "Environment.Variables" | grep -E "HUB_PUBLIC_KEY_PEM|TRUSTED_KEY_IDS|TRACKING_TABLE|NOVA_MODEL_ID"
aws lambda get-function-configuration --function-name "$RFN" --region us-east-1 --query "Environment.Variables.HUB_PUBLIC_KEY_PEM" --output text | wc -c   # expect ~178+, NOT 27
```
Expect: all three marker classes present; probe grep clean; role actions ONLY s3
get/delete/list + ec2 describe/terminate + sqs send (NO dynamodb); env has HUB_PUBLIC_KEY_PEM +
TRUSTED_KEY_IDS, NO TRACKING_TABLE / NO NOVA_MODEL_ID; PEM full length.

### BLOCK 5 — Hub: export the public key + redeploy the ingest for the new kind (Hub tab `641628980935`)
```
aws sts get-caller-identity   # expect 641628980935
KID=$(aws cloudformation describe-stacks --stack-name ZtieDecisionSigningStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='DecisionSigningKeyId'].OutputValue" --output text)
aws kms get-public-key --key-id "$KID" --region us-east-1 --query PublicKey --output text | base64 -d > /tmp/ztie_pub.der ; openssl pkey -pubin -inform DER -in /tmp/ztie_pub.der -out /tmp/ztie_pub.pem 2>/dev/null || openssl ec -pubin -inform DER -in /tmp/ztie_pub.der -pubout -out /tmp/ztie_pub.pem ; cat /tmp/ztie_pub.pem
# (copy /tmp/ztie_pub.pem to the Forensic tab for BLOCK 3)
IQURL=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='IngestQueueUrl'].OutputValue" --output text)
IQARN=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='IngestQueueArn'].OutputValue" --output text)
echo "$IQURL" ; echo "$IQARN"
cd ~/ZTIE-Issues && git fetch origin -q && git checkout feature/story-4.7 && git reset --hard origin/feature/story-4.7
cd ~/ZTIE-Issues/infra && rm -rf ~/.npm && mkdir -p ~/.npm-cache ~/.npm-tmp && TMPDIR=~/.npm-tmp npm install --no-audit --no-fund --cache ~/.npm-cache
TMPDIR=~/.npm-tmp npx cdk deploy ZtieHubTrackingStack --require-approval never
# confirm the live ingest knows the new kind:
IFN=$(aws cloudformation describe-stack-resources --stack-name ZtieHubTrackingStack --region us-east-1 --query "StackResources[?ResourceType=='AWS::Lambda::Function' && contains(LogicalResourceId,'IngestValidator')].PhysicalResourceId" --output text)
ILOC=$(aws lambda get-function --function-name "$IFN" --region us-east-1 --query Code.Location --output text) ; curl -s "$ILOC" -o /tmp/ingest.zip ; mkdir -p /tmp/ingest && (cd /tmp/ingest && unzip -oq /tmp/ingest.zip) ; grep -n '"disposition"\|name="disposition"' /tmp/ingest/handler.py | head ; ls /tmp/ingest/disposition.contract.v1.json
```

### BLOCK 6 — Hub: sign a `rejected` token (Hub tab) — set IID + SHA to the fresh intake's values
```
KARN=arn:aws:kms:us-east-1:641628980935:key/3321e5b7-2ca3-42e3-b99c-9b9d83a45243
IID=<fresh-intake-uuid> ; SHA=<that artifact's sha256> ; AKEY=intake/$IID/<filename>
ISSUED=$(python3 -c "import datetime;print(datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00','Z'))")
python3 -c "import json; t={'contract_version':'1.0','intake_id':'$IID','decision':'rejected','sha256':'$SHA','issued_at':'$ISSUED','key_id':'$KARN'}; open('/tmp/token.json','w').write(json.dumps(t)); open('/tmp/canon.bin','wb').write(json.dumps(t,sort_keys=True,separators=(',',':')).encode()); print('written')"
SIG_B64=$(aws kms sign --key-id "$KARN" --message fileb:///tmp/canon.bin --message-type RAW --signing-algorithm ECDSA_SHA_256 --region us-east-1 --query Signature --output text) ; echo "$SIG_B64" > /tmp/sig.b64
python3 -c "import json; tok=json.load(open('/tmp/token.json')); sig=open('/tmp/sig.b64').read().strip(); open('/tmp/invoke.json','w').write(json.dumps({'intake_id':tok['intake_id'],'decision_token':tok,'signature':sig,'artifact_s3_key':'$AKEY'})); print('invoke written')"
# copy /tmp/invoke.json to the Forensic tab
```

### BLOCK 7 — Forensic: snapshot BEFORE, destroy, verify AFTER (Forensic tab)
```
ARTB=$(aws cloudformation describe-stacks --stack-name ZtieIntakeStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='ArtifactBucketName'].OutputValue" --output text) ; IID=<fresh-intake-uuid>
for P in intake findings runs traces ; do echo "== $P/$IID/ ==" ; aws s3api list-object-versions --bucket "$ARTB" --prefix "$P/$IID/" --region us-east-1 --query "{versions: length(Versions || \`[]\`), markers: length(DeleteMarkers || \`[]\`)}" ; done
RFN=$(aws cloudformation describe-stacks --stack-name ZtieForensicRejectStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='PdeRejectFunctionName'].OutputValue" --output text)
aws lambda invoke --function-name "$RFN" --payload fileb:///tmp/invoke.json --cli-binary-format raw-in-base64-out --region us-east-1 /tmp/out.json >/dev/null ; python3 -c "import json;d=json.load(open('/tmp/out.json'));print('destroyed:',d.get('destroyed'),'outcome:',d.get('outcome'),'chamber:',d.get('chamber_state'));print('destroyed_block:',json.dumps(d.get('disposition',{}).get('destroyed'),default=str))"
for P in intake findings runs traces ; do echo "== $P/$IID/ (expect 0/0) ==" ; aws s3api list-object-versions --bucket "$ARTB" --prefix "$P/$IID/" --region us-east-1 --query "{versions: length(Versions || \`[]\`), markers: length(DeleteMarkers || \`[]\`)}" ; done
aws ec2 describe-instances --filters "Name=tag:IntakeId,Values=$IID" "Name=tag:Ephemeral,Values=true" --region us-east-1 --query "Reservations[].Instances[].{id:InstanceId,state:State.Name}"
```

### BLOCK 8 — FAIL-SAFE negatives (Forensic tab) — each against a FRESH intake `$IID2`
Repeat BLOCK 6 with the broken input, invoke, and confirm `destroyed: False` + `$IID2`'s prefixes UNCHANGED:
- no token: invoke `{"intake_id":"<iid2>","artifact_s3_key":"intake/<iid2>/<f>"}` → `held`.
- tampered sig (flip one base64 char) → `refused_not_rejected`.
- `accepted` token (sign with `decision:"accepted"`) → `refused_not_rejected`.
- sha-mismatch (`sha256` = `b`*64) → `refused_hash_mismatch`.
- stale (`issued_at`=`2000-01-01T00:00:00Z`) → `refused_not_rejected`.
- untrusted key (rogue `key_id`) → `refused_not_rejected`.

### BLOCK 9 — Hub: the crossed outcome + the surviving report (Hub tab)
```
TABLE=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack --region us-east-1 --query "Stacks[0].Outputs[?OutputKey=='TrackingTableName'].OutputValue" --output text) ; IID=<fresh-intake-uuid>
aws dynamodb get-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --region us-east-1 --query "{outcome:Item.disposition_outcome.S, disposition:Item.disposition.M}"
aws dynamodb get-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --region us-east-1 --query "Item.disposition" --output json > /tmp/do.json ; python3 -c "import json;s=json.dumps(json.load(open('/tmp/do.json')));banned=['\"verdict\"','\"safe\"','\"approved\"','\"forward\"','\"malicious\"','\"pass_fail\"','\"clean\"'];print('FAIL' if any(b in s for b in banned) else 'OK: no effective-verdict key')"
aws dynamodb get-item --table-name "$TABLE" --key "{\"intake_id\":{\"S\":\"$IID\"}}" --region us-east-1 --query "keys(Item)" --output json   # the report record survives
```

---

## Notes / limits (Part D condensed)

- The `<<< REQUIREMENT >>>` anchor is YOURS — reword it, do not paste Kiro's framing.
- The FAIL-SAFE branches are the point of a destroy story — prove each against a FRESH intake
  whose files remain intact after the refusal, not just the happy destroy.
- This is `[sec-boundary]` (RD-054): the PASS rests on RETAINED raw artifacts committed to
  `docs/validation-evidence/4.7/attempt-<n>/` (the destroy counts + emptied-prefix listings +
  chamber state + the crossed disposition map + a NAMED human attestation + intake_id/SHA
  provenance), because Forensic is ephemeral.
- Two LLMs agreeing is not a pass — your reading of the raw S3/EC2/Hub output is.

## Close-out (Part C stage 4)
On an explicit sealed **PASS**, hand the sealed verdict + retained evidence to **Kiro**; Kiro
records it verbatim, flips **4.7 → ✅** (paired commit), clears the Validation Debt Register,
authors `docs/validation-evidence/4.7/attempt-<n>/EVIDENCE.md`, and repoints on-deck to **4.4**
(which closes Phase 4). On **INCONCLUSIVE/FAIL**, 4.7 stays **🟡**; fix + re-validate once.
