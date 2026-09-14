# Session Prompt — Story 4.6 (REWORKED) LIVE validation — executor handoff

You are the ZTIE execution agent picking up mid-flight. This session's ONE job: **get the
reworked Story 4.6 through its recorded LIVE validation and flip it ✅** (or fix-then-
validate-once if it fails). Read this fully before acting; re-establish true state (STEP 0)
before touching anything. Trust `main` + `check_docs` over anything written here if they
disagree.

## WHERE WE ARE (as of 2026-09-14, previous session)

- **ZTIE** = 4-phase AWS-native zero-trust inspection pipeline. Three accounts: **Hub
  (641628980935)** = control plane; **Forensic (360999005254)** = blast zone (artifact +
  lanes + the pusher); **Pipeline-Sandbox (586917955591)** = the ZTIE→PDE landing zone.
- **Story 4.6** = the ACCEPT enforcement action (push a hash-verified, human-accepted
  artifact Forensic→Pipeline-Sandbox). It is **🟡** — the sole open Validation-Debt entry.
- **A redesign already happened and is DONE** (not a rewind): 4.6's original live run
  surfaced a cross-account read INTO the Hub; the stakeholder ruled the **Hub is strictly
  the control plane** (**RD-048**, ratified) with a **KMS-asymmetric Hub-sign / spoke-verify-
  OFFLINE** mechanism (**RD-049**, ratified). The primitive was built + **validated live as
  Story H.2 ✅** (`lib/decision_auth` + `ZtieDecisionSigningStack`, a KMS ECC_NIST_P256
  SIGN_VERIFY key). Restore tags `restore/phase-3-green` + `restore/story-4.5-green` were
  pushed (code half; manifests tracked as **OD-004**, non-blocking).
- **4.6 was then REWORKED** onto that primitive (PR #150, merged): the Forensic `pde_handoff`
  now VERIFIES a Hub-signed `decision.token.v1` OFFLINE instead of reading the Hub; the
  `dynamodb:GetItem` grant + `TRACKING_TABLE` are removed; the Sandbox landing stack + the
  one-directional push + the verdict-free `handoff` outcome crossing are unchanged. 42
  offline tests pass.
- **A live-deploy bug was found + fixed:** the reworked `ZtiePdeHandoffStack` had a
  `StackDescriptionTooLong` (>1024-byte CloudFormation stack description), so `cdk deploy`
  errored BEFORE deploying (the OLD pre-rework stack stayed live — that's why a verify then
  showed `dynamodb:GetItem` + `TRACKING_TABLE`). The fix (shorten the description) is **PR
  #151 — STILL OPEN as of this writing.**

## STEP 0 — RE-ESTABLISH TRUE STATE (before anything)

1. `git fetch origin && git checkout main && git reset --hard origin/main && git log --oneline -1`.
2. **CONFIRM PR #151 IS MERGED** (the deploy-blocking fix):
   `gh api repos/warrenrutledge64/ZTIE-Issues/pulls/151 --jq '.merged'` → must be `true`.
   Also confirm `main` carries the short description:
   `grep -c "Forensic ACCEPT-push: pde_handoff VERIFIES" infra/bin/ztie-infra.ts` → must be `1`.
   **If #151 is NOT merged, STOP and merge it first** (or the live deploy will fail again with
   `StackDescriptionTooLong`).
3. `python3 scripts/check_docs.py` → PASS (expect only OD-004 operational-debt + a CHECK J
   advisory; both informational). `~/.pyenv/versions/3.12.13/bin/python3 -m unittest
   scripts.test_check_docs` → OK (19).
4. Confirm **4.6 is 🟡** in the RUNBOOK master table (now near the TOP of the runbook) and
   is the sole Validation-Debt entry. Confirm **H.2 ✅**.
5. Re-read `docs/session-briefs/story-4.6-LIVE-RUNBOOK.md` (the FRESH one — the pre-rework
   content is superseded) and `docs/architecture/AUTHENTICATED_DECISIONS.md`.

## THE LIVE VALIDATION (the whole job) — follow `story-4.6-LIVE-RUNBOOK.md`

This is the STAKEHOLDER's action in **three CloudShell tabs** (Hub / Forensic / Pipeline-
Sandbox); the executor gives exact copy-paste commands, records the returned output VERBATIM,
and never marks done on inference. `aws sts get-caller-identity` before EVERY block. Region
us-east-1, no `--profile`.

**Known live values (verified last session — re-confirm at STEP 0):**
- Hub decision-signing key ARN (= the token `key_id`, and the `trustedKeyIds`):
  `arn:aws:kms:us-east-1:641628980935:key/3321e5b7-2ca3-42e3-b99c-9b9d83a45243`
- Hub public key PEM (exported via `aws kms get-public-key`; NOT a secret):
  ```
  -----BEGIN PUBLIC KEY-----
  MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEGM954tKO/02mMuexReRXDns6yMSM
  qcp3EL37+OgCUNoEBUdJDYqo7+THKwhVL6cy55cCKI6/gDF1RbSkqlIWVA==
  -----END PUBLIC KEY-----
  ```
- Hub ingest queue URL: `https://sqs.us-east-1.amazonaws.com/641628980935/ZtieHubTrackingStack-IngestQueue2280FF4E-1iWf9MMmxAjq`
- Hub ingest queue ARN: `arn:aws:sqs:us-east-1:641628980935:ZtieHubTrackingStack-IngestQueue2280FF4E-1iWf9MMmxAjq`
- Hub tracking table: `ZtieHubTrackingStack-TrackingTable170A6688-133E30JVEWB1Z`
- Forensic artifact bucket: `ztieintakestack-intakeartifactbucket2415ab50-vzfdr2jmnj5a`
- Sandbox landing bucket: `ztiesandboxlandingstack-pdelandingbucketcf8a86dc-gllin1kwtr21`
- Reuse a fully-processed intake: `891cb78f-fd35-4045-81d6-030d75d9c83e`, filename
  `probe.yaml`, sha256 `cd04299d8e29601f5425054e0470a71f255fb19a7d2fe3734bcb6213f27208f0`.

**The sequence (details + exact commands in the LIVE-RUNBOOK):**
1. **Forensic tab — REDEPLOY `ZtiePdeHandoffStack`** on the fixed `main` (the deploy that
   failed last time). Deploy cmd: `cd ~/ZTIE-Issues/infra && TMPDIR=~/.npm-tmp npx cdk deploy
   ZtiePdeHandoffStack --require-approval never -c
   artifactBucketName=ztieintakestack-intakeartifactbucket2415ab50-vzfdr2jmnj5a -c
   hubIngestQueueUrl=<IngestQueueUrl> -c hubIngestQueueArn=<IngestQueueArn> -c
   sandboxLandingBucket=ztiesandboxlandingstack-pdelandingbucketcf8a86dc-gllin1kwtr21 -c
   hubPublicKeyPem="$(cat /tmp/ztie_pub.pem)" -c
   trustedKeyIds=arn:aws:kms:us-east-1:641628980935:key/3321e5b7-2ca3-42e3-b99c-9b9d83a45243`
   (write the PEM above to `/tmp/ztie_pub.pem` first via a `cat > … <<'PEM'` heredoc; run
   `rm -rf ~/.npm && mkdir -p ~/.npm-cache ~/.npm-tmp && TMPDIR=~/.npm-tmp npm install
   --no-audit --no-fund --cache ~/.npm-cache` if deps aren't installed).
2. **POST-DEPLOY VERIFY (the rework's whole point):** the live pusher role has **NO
   `dynamodb`** action (only `s3:GetObject` / `s3:PutObject`(+tagging) / `sqs:SendMessage`),
   and its env has `HUB_PUBLIC_KEY_PEM` + `TRUSTED_KEY_IDS` and **NO `TRACKING_TABLE` / NO
   `NOVA_MODEL_ID`**. (Last session this still showed the OLD stack because the deploy had
   errored — so DON'T trust it until you've re-run the deploy on fixed `main` and the deploy
   prints `✅ ZtiePdeHandoffStack`.) If the pusher role ARN changed, re-tighten the Sandbox
   grant: Sandbox tab `npx cdk deploy ZtieSandboxLandingStack --require-approval never -c
   forensicPusherRoleArn=<PdeHandoffRoleArn>`.
3. **Hub tab — sign an `accepted` token:** build the CANONICAL bytes
   `json.dumps(token, sort_keys=True, separators=(",",":"))` over the six token keys
   (contract_version/intake_id/decision/sha256/issued_at/key_id), `aws kms sign
   --signing-algorithm ECDSA_SHA_256 --message-type RAW`, base64 the signature, assemble the
   invoke payload `{intake_id, decision_token, signature, artifact_s3_key:
   intake/<id>/probe.yaml}`.
4. **Forensic tab — invoke the pusher** with that payload → expect `pushed: True`,
   `outcome: pushed`; **Sandbox tab** — the object LANDED under `accepted/<id>/` and its
   recomputed sha256 == the tracked sha256.
5. **FAIL-CLOSED proofs** (each must refuse, nothing lands): no token (400), tampered
   signature (`refused_not_accepted`), rejected token (`refused_not_accepted`), sha-mismatch
   (`refused_hash_mismatch`), stale token (`refused_not_accepted`).
6. **Hub tab** — the bounded, verdict-free `handoff` outcome crossed (`handoff_outcome:
   pushed`, no `verdict`/`safe`/`approved`/`forward` key); NO spoke→Hub read happened.

## ON A PASS
Record the verbatim results into `docs/STORY_DETAIL.md` (4.6 Validation Result) + the RUNBOOK,
flip **4.6 🟡→✅** (paired commit on a `docs/story-4.6-validate` branch), clear 4.6 from the
Validation Debt Register, add a WORK_LOG close entry, and repoint the on-deck README to the
next work (**4.7** — REJECT→destroy, which VERIFIES a Hub-signed `rejected` token the same
way; then **4.4** — the human UI + one-directional Hub→Forensic delivery — which CLOSES Phase
4). Author the 4.7 handoff (brief+prompt) — note the existing `story-4.7-*` handoff predates
RD-048 and must be refreshed to the verify-a-signed-token shape. Run `check_docs` AFTER
committing the status edit. Open the close-out PR via `gh api` (not `gh pr create`).

## ON A FAIL
4.6 stays 🟡. Fix on a branch, redeploy, re-validate once (fix-then-validate-once) — never
mark done on inference.

## HARD-WON LESSONS (carry forward)
- **A green `cdk deploy` line is the only proof it deployed** — last session a
  `StackDescriptionTooLong` errored BEFORE deploy and a subsequent role/env check showed the
  STALE old stack (still had `dynamodb` + `TRACKING_TABLE`), which looked like a rework
  failure but wasn't. Always confirm `✅ <StackName>` printed, THEN verify the live resource.
  Keep any new CloudFormation stack `description` < 1024 bytes.
- **The rework's invariant to prove live:** the pusher NEVER reads the Hub — role has no
  `dynamodb`, env has no `TRACKING_TABLE`; the decision is a Hub-signed token verified
  OFFLINE (RD-048/RD-049). That is the thing this validation exists to demonstrate.
- **Canonical bytes must match** what `lib/decision_auth/canonical.py` produces
  (`sort_keys=True, separators=(",",":")` over exactly the six keys) or the signature won't
  verify — a `refused_not_accepted`/"bad_signature" on the happy path usually means the signed
  bytes differed from what the verifier canonicalizes.
- **Three accounts, three tabs; `sts get-caller-identity` before every block.** Feed commands
  ONE LINE AT A TIME; `/tmp` + shell vars are WIPED on a CloudShell recycle (re-set in-block).
- **Git auth on CloudShell:** the boxes cached an old (now-rotated) token; if `git fetch`
  fails auth, clear the helper (`git config --global --unset-all credential.helper; rm -f
  ~/.git-credentials`) and let git PROMPT for username + the current token (do NOT put the
  token in the URL — it echoes into logs/chat; rotate any token that leaks).
- **Offline proof bar** (executor sandbox, INTEGRATIONS_ONLY): `~/.pyenv/versions/3.12.13/bin/
  python3 -m unittest` (pytest NOT installed); `~/.pyenv/versions/3.12.13/bin/ruff check`;
  `env -u NODE_OPTIONS npx tsc --noEmit` (confirm NO NEW error TYPE — the missing-`aws-cdk-lib`
  family is the baseline); `env -u NODE_OPTIONS npx prettier --write`. `gh pr create` is
  BROKEN — open PRs via `gh api repos/warrenrutledge64/ZTIE-Issues/pulls`.
- **Covenant:** 4.6 is not ✅ until a recorded live pass of the FINAL (fixed) code. Reworking/
  fixing a 🟡 story is normal; never flip on inference.

## OPEN ITEMS (non-blocking)
- **OD-004:** the paired restore-point state manifests for `restore/phase-3-green` +
  `restore/story-4.5-green` are not captured yet (live `scripts/ztie-restore` in Hub +
  Forensic + Pipeline-Sandbox). Operational debt; does not block 4.6.
- A GitHub PAT leaked into chat twice (rotate it).
