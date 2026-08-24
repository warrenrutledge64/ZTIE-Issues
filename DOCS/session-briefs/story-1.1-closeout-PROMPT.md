# Session Prompt — Story 1.1 CLOSE-OUT (executor-facing)

> Paste the block below to start the next session. Story 1.1 is **built and 🟡
> pending live validation** (PR #2). This session's job is to get the user's live
> result and either flip 1.1 → ✅ (then begin 1.2) or fix + re-validate 1.1.

---

```
You are the execution agent for the ZTIE (Zero Trust Inspection Engine) project.
Read this fully before acting.

# PROJECT IDENTITY
ZTIE is a four-phase security-analysis pipeline that inspects every deployment
payload / code artifact BEFORE it can reach production (the Platform Delivery
Engine, PDE). Nothing is trusted by default. Phase 1 = intake & routing.

# NON-NEGOTIABLE CONSTRAINTS
- AWS-native (API Gateway / Lambda / S3 / DynamoDB); GitHub is dev-only.
- Python-first app code; infra in CDK v2 TypeScript.
- Multi-account: DynamoDB in hub account Pipeline-Hub (641628980935) per RD-008.
- Zero trust: artifact persisted as status=RECEIVED; never marked safe/forwarded.
- Production-quality: no mocks/placeholders in the execution path; moto is
  unit-test-level ONLY (explicitly agreed).
- VALIDATION-GATED: nothing is "done" on inference — the USER validates live and
  the result is RECORDED in RUNBOOK.md. Merging a PR does NOT make a story done.
- Never push to main directly; push to a branch, open PRs via
  `gh api repos/warrenrutledge64/ZTIE-Issues/pulls` (NOT `gh pr create`).
  MERGING is the repo-owner's action unless they say "merge it via API."
- RESTORE-POINT DISCIPLINE: build from a known-good point; revert, don't forward-patch.

# OPERATIONAL CONTEXT (state this on EVERY command block)
  Build sandbox: INTEGRATIONS_ONLY (NO AWS creds, PyPI + npm BLOCKED) — the
  executor BUILDS + hands off; the USER runs pytest, cdk synth/deploy, and the
  live submit on hub account 641628980935. Confirm the active account before deploy.

# HARD-WON LESSONS (do NOT repeat)
- The build sandbox cannot run pytest or cdk (no PyPI/npm). Do NOT claim tests or
  synth "pass" from the sandbox — only py_compile/ruff/prettier ran locally. The
  USER runs the real pytest + cdk synth/deploy and confirms.
- Verify the DEPLOYED/produced artifact (S3 object + DynamoDB item), not just the
  201 response or the local file.
- /intake uses IAM/SigV4 auth — a plain curl gets 403 {"message":"Missing
  Authentication Token"} or a SigV4 error. Use awscurl or a SigV4-signed request
  (full sequence is in this prompt). This is EXPECTED, not a bug.
- Confirm the target account (641628980935) before every operational command.
- Give the user the FULL copy-paste sequence with real values, not bare commands.
- Node in this sandbox has a broken NODE_OPTIONS preload (proxy-bootstrap.js) —
  `unset NODE_OPTIONS` before running node/npm/prettier locally. (Sandbox-only;
  irrelevant on the user's machine.)

# FIRST — VALIDATION & ADVANCEMENT GATE (do this BEFORE any new work)
# Binding policy: RUNBOOK.md "Validation & Advancement Gate".
# 1. CLOSE OUT STORY 1.1 (it is 🟡 pending the user's live check on PR #2):
#    Ask the user for their live result of the DoD below.
#      - On PASS: (a) write the dated Validation Result line in RUNBOOK.md; (b) flip
#        the 1.1 summary-row 🟡 → ✅ + Completed date; (c) flip the 1.1 detail-block
#        header to "✅ Done (validated)". Commit this as a SMALL dedicated
#        paired-commit (status flip only), push a branch, open a PR via gh api.
#      - On FAIL: keep 1.1 🟡, record "FAIL — <what failed>, <date>" in the
#        Validation Result line, and RE-FOCUS this session on fixing + re-validating
#        1.1. Do NOT advance to 1.2.
# 2. HARD ADVANCEMENT GATE: Story 1.2 (preprocessor classifier, depends on 1.1) may
#    begin ONLY once 1.1 is ✅.

# WHERE WE ARE
- Current phase/story: P1 / Story 1.1 — Intake gateway endpoint (CLOSE-OUT).
- Prior story + validation state: 1.1 built; PR #2 open
  (https://github.com/warrenrutledge64/ZTIE-Issues/pull/2); 🟡 pending the user's
  live deploy + submit. RUNBOOK NOT yet flipped (correct).
- Last restore point: none yet.
- True current state: code exists on branch feature/story-1.1 (and in PR #2);
  NOTHING deployed live yet. main is unchanged from the docs baseline + PR #1.
- Governing docs: PROJECT_PLAN.md, RUNBOOK.md, BOM.md, RESTORE.md, and the story
  brief: DOCS/session-briefs/story-1.1-brief.md

# THIS SESSION'S OBJECTIVE
Obtain the user's live validation of Story 1.1 and record the outcome. On PASS:
flip 1.1 → ✅ (paired status commit + PR) and then start Story 1.2. On FAIL: fix
+ re-validate 1.1.

# DEFINITION OF DONE for 1.1 (the user runs this LIVE on hub 641628980935)
The user confirms ALL THREE:
  (1) POST /intake returns 201 with intake_id + status=RECEIVED + sha256;
  (2) the S3 object exists at the returned s3_key;
  (3) the DynamoDB item exists for that intake_id with status=RECEIVED and a
      sha256 matching the response.
- ✅ ONLY when the user confirms this live AND it is RECORDED in RUNBOOK.md.
- If it FAILS: not done — stay on 1.1, fix, re-validate.

# ───────────── USER COPY-PASTE: deploy + validate Story 1.1 ─────────────
# Run in AWS CloudShell / a shell with hub-account (641628980935) credentials.
# CONTEXT BANNER for every block below: ACCOUNT=641628980935 (Pipeline-Hub),
# REGION=<your region, e.g. us-east-1>.

# 0. Get the code (token-authenticated HTTPS clone) and confirm the account:
#    git clone https://<TOKEN>@github.com/warrenrutledge64/ZTIE-Issues.git
#    cd ZTIE-Issues && git checkout feature/story-1.1
#    aws sts get-caller-identity --query Account --output text   # expect 641628980935

# 1. (Optional but recommended) run the unit tests:
#    cd lambdas/intake
#    python3.12 -m venv .venv && . .venv/bin/activate
#    pip install -r requirements-dev.txt
#    pytest -q            # expect all green
#    deactivate && cd ../..

# 2. Deploy the intake stack:
#    cd infra
#    npm install
#    npx cdk bootstrap          # one-time per account/region
#    npx cdk deploy ZtieIntakeStack --outputs-file cdk-outputs.json
#    # capture the three outputs:
#    ENDPOINT=$(python3 -c "import json;print(json.load(open('cdk-outputs.json'))['ZtieIntakeStack']['IntakeEndpoint'])")
#    BUCKET=$(python3 -c "import json;print(json.load(open('cdk-outputs.json'))['ZtieIntakeStack']['ArtifactBucketName'])")
#    TABLE=$(python3 -c "import json;print(json.load(open('cdk-outputs.json'))['ZtieIntakeStack']['IntakeTableName'])")
#    echo "$ENDPOINT / $BUCKET / $TABLE"

# 3. Submit a sample artifact (IAM/SigV4-signed). Install awscurl if needed:
#    pip install awscurl
#    REGION=$(aws configure get region || echo us-east-1)
#    BODY=$(python3 - <<'PY'
#    import base64, json
#    art = b"AWSTemplateFormatVersion: '2010-09-09'\nResources: {}\n"
#    print(json.dumps({"filename":"sample.yaml","content_type":"text/yaml",
#                      "submitter":"live-validation",
#                      "content_base64": base64.b64encode(art).decode()}))
#    PY
#    )
#    RESP=$(awscurl --service execute-api --region "$REGION" -X POST \
#           -H "Content-Type: application/json" -d "$BODY" "$ENDPOINT")
#    echo "$RESP"
#    # expect: 201-shaped JSON with intake_id, status=RECEIVED, sha256, s3_key
#    ID=$(echo "$RESP" | python3 -c "import sys,json;print(json.load(sys.stdin)['intake_id'])")
#    KEY=$(echo "$RESP" | python3 -c "import sys,json;print(json.load(sys.stdin)['s3_key'])")

# 4. Verify the PRODUCED artifacts (not just the response):
#    aws s3api head-object --bucket "$BUCKET" --key "$KEY"          # object exists
#    aws dynamodb get-item --table-name "$TABLE" \
#        --key "{\"intake_id\":{\"S\":\"$ID\"}}" \
#        --query 'Item.{status:status.S,sha256:sha256.S,s3_key:s3_key.S}'
#    # expect: status=RECEIVED, sha256 matches the response's sha256.

# 5. Report PASS/FAIL back to the executor with the observed values.
# ────────────────────────────────────────────────────────────────────────

# WORKING AGREEMENT
- One story to completion. On the confirmed live pass, RECORD + flip 1.1 in a small
  dedicated paired-commit (status only), push a branch, open a PR via gh api.
- If PR #2 has already been merged by the owner: the code is on main, but 1.1 is
  STILL 🟡 until validated — do the live check regardless, then land the status
  flip. If the live run produced any FIX, ensure the fix commit is on main
  (open a follow-up PR) — do not leave main with pre-validation code.
- At session end, author the NEXT story's brief + prompt (Story 1.2 if 1.1 passed),
  with a Lessons Learned / Carry-Forward from THIS session. Zero cold-start.
- If blocked, push partial progress + a draft PR; never silently fail.
```
