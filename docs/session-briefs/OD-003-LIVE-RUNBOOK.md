# OD-003 — LIVE deploy + verify runbook (stakeholder)

> **This is the ONLY live part of OD-003, and only YOU can do it** (the executor has no
> AWS creds). OD-003 is **build-toolchain hygiene** — a version bump plus a swap of two
> deprecated CDK settings to their current form. **No behaviour changes.** You redeploy
> the CDK stacks on a **Node 22** box, confirm the only real change is the log-group
> rename described below, and confirm the new log groups receive logs. On a clean deploy
> the executor closes OD-003 in the RUNBOOK Operational Debt register with a dated
> evidence note. **Nothing is recorded on inference** — paste back exactly what the
> commands print.

---

## What OD-003 is (so the check is meaningful)

OD-003 was raised during the Story 3.1 live validation (2026-09-11/12). `cdk deploy` in
CloudShell was printing forward-looking warnings — it is **not** a break; deploys work
today. Three things were flagged:

1. **Toolchain aging out.** The AWS SDK for JS v3 will require **Node >= 22** after early
   Jan 2027 (CloudShell was on Node v20), and a newer CDK release is available vs the
   repo's old pins.
2. **Deprecated DynamoDB setting.** `pointInTimeRecovery: true` → the structured
   `pointInTimeRecoverySpecification: { pointInTimeRecoveryEnabled: true }`. **Same
   behaviour — point-in-time recovery (continuous backup) stays ON.**
3. **Deprecated Lambda setting.** `logRetention` (a shortcut that provisions a hidden
   custom resource) → an explicit `logs.LogGroup` passed as `logGroup`. **Same behaviour
   — logs still kept ONE MONTH.**

### What the code change actually is (PR #105)

- **`infra/package.json`** version bumps: `aws-cdk` `^2.140.0` → `^2.1141.0`,
  `aws-cdk-lib` `^2.140.0` → `^2.265.0`, `@types/node` `^20` → `^22`.
- **DynamoDB (Hub tracking table):** `pointInTimeRecovery: true` → `pointInTimeRecoverySpecification`.
- **Lambda log retention → explicit LogGroup**, for **every** function across all six
  stacks: `ztie-intake-stack` (intake handler + preprocessor), `ztie-hub-tracking-stack`
  (ingest validator, combined-event normalizer, **Story 3.2 Nova correlator**, **Story
  3.3 synthesizer**), `ztie-detonation-stack`, `ztie-orchestration-stack`,
  `ztie-static-scan-stack`.

> **The one non-obvious effect — read this before you deploy.** The old `logRetention`
> shortcut let AWS name each log group `/aws/lambda/<function-name>`. The explicit
> `logGroup` gets a CDK-generated name instead. So a `cdk deploy` will **create new log
> groups and retire the old retention custom resource** — this is **expected** and is
> **NOT a zero-change deploy**. Any change BEYOND the log-group swap (Lambda code, env
> vars, the DynamoDB table itself, IAM) would be unexpected — pause and report it.
> Reference: <https://github.com/aws/aws-cdk/issues/28809> (content rephrased for
> licensing compliance).

---

## Ground rules (these have bitten us every session)

- **TWO accounts.** Most stacks are in **Forensic (360999005254)**; the Hub tracking
  stack is in **Hub (641628980935)**. Deploy each stack from a shell authed to the
  account that stack lives in.
- **The Hub tracking stack needs Docker** (the ingest validator bundles `jsonschema` in
  the Lambda Python 3.12 image), so that stack must be deployed from a **Docker-capable,
  Forensic/Hub-authed build box**, not a plain CloudShell. The other stacks deploy fine
  from CloudShell.
- **Run `aws sts get-caller-identity` BEFORE every block** and read `Account`. If it is
  not the account the block is for, switch tabs.
- **Feed commands ONE LINE AT A TIME.** Never paste a multi-line block.
- **Region us-east-1**, ambient creds (**no `--profile`**).
- **GitHub auth in CloudShell:** token-in-URL HTTPS form
  `git remote set-url origin https://<TOKEN>@github.com/warrenrutledge64/ZTIE-Issues.git`.

---

## STEP 0 — merge PR #105 first

Review and merge **PR #105** (`chore/od-003-migration` → `main`):
<https://github.com/warrenrutledge64/ZTIE-Issues/pull/105>

Then every deploy below is done from `main`.

---

## STEP 1 — get on Node 22 and prove the checkout carries OD-003

```
node --version
```
If it is not `v22.x`, switch: CloudShell ships `nvm`, so —
```
nvm install 22 && nvm use 22
```
```
node --version
```
Expect `v22.x`.

```
cd ~/ZTIE-Issues && git fetch origin -q && git checkout main && git reset --hard origin/main
```
```
git log --oneline -1
```
Expect the PR #105 merge commit at the tip.

Prove the deprecated settings are actually gone from the checkout (should print NOTHING):
```
grep -rn "logRetention:" infra/lib/*.ts ; grep -rn "pointInTimeRecovery:" infra/lib/*.ts
```
Prove the new pins are present:
```
grep -E "aws-cdk\"|aws-cdk-lib|@types/node" infra/package.json
```

---

## STEP 2 — install and look at the diff BEFORE deploying

```
cd ~/ZTIE-Issues/infra && npm install
```
```
npx cdk diff --all
```
**Read the diff.** For EACH stack you expect to see, essentially, only:
- new `AWS::Logs::LogGroup` resources being **added**, and
- the old log-retention **custom resource being removed**,
- (Hub tracking stack only) the DynamoDB table showing the PITR property re-expressed —
  it must still be **enabled**, not disabled.

If you see the Lambda **code**, **environment variables**, the DynamoDB **table
key/stream**, or **IAM** changing, STOP and report the diff — that is not expected for
OD-003.

---

## STEP 3 — deploy per stack

Deploy from the correct account per stack. Forensic stacks (CloudShell is fine for all
but the Hub stack):
```
npx cdk deploy ZtieIntakeStack
npx cdk deploy ZtieStaticScanStack
npx cdk deploy ZtieDetonationStack
npx cdk deploy ZtieOrchestrationStack
```
> `ZtieStaticScanStack` and `ZtieDetonationStack` build container images and need a
> **Docker-capable** Forensic box (the same disposable build-box pattern used in Story
> 2.1/2.3), not a plain CloudShell.

Hub stack, from a **Docker-capable Hub-authed** box (it bundles `jsonschema`):
```
npx cdk deploy ZtieHubTrackingStack
```

Each should end `✅ UPDATE_COMPLETE`. **Do not trust the green line alone** — verify in
STEP 4.

> Pass any per-stack context these stacks already require (e.g. the detonation stack's
> `-c detonationInstanceRoleArn=<ZtieForensicInfraStack DetonationInstanceRoleArn>`) —
> OD-003 does not change those requirements.

---

## STEP 4 — verify the change actually took (never trust the green line)

**a) New log groups exist and are set to one-month (30-day) retention.** Example for the
intake handler (repeat per function / stack as you like):
```
aws logs describe-log-groups --query "logGroups[?contains(logGroupName, 'IntakeHandlerLogGroup')].[logGroupName,retentionInDays]" --output table
```
Expect a group to be listed with `retentionInDays = 30`.

**b) PITR still ON on the Hub tracking table** (run in the **Hub** tab):
```
aws dynamodb describe-continuous-backups --table-name <TrackingTableName from the Hub stack output> --query "ContinuousBackupsDescription.PointInTimeRecoveryDescription.PointInTimeRecoveryStatus" --output text
```
Expect `ENABLED`.

**c) Logs actually flow.** Submit one ordinary intake (the usual awscurl SigV4 submit
from a Forensic tab) and confirm the new log groups receive log events for that run.

---

## STEP 5 — close OD-003

If STEP 4 is clean (new log groups at 30-day retention, PITR still `ENABLED`, logs
flowing, and no unexpected diff), OD-003 is done. Have the executor:

1. In `RUNBOOK.md`, move OD-003 out of the **open** Operational Debt register (or mark it
   resolved) with a **dated evidence note** — paste back the STEP 4 outputs verbatim so
   the close is on evidence, not inference.
2. Update the register status line (`3 open` → `2 open`, OD-001/OD-002 remaining).
3. Run `python3 scripts/check_docs.py` (expect PASS) and
   `python3 -m unittest scripts.test_check_docs` (expect OK) after committing the status
   change.

---

## Work-effort record (what this session produced)

- **Branch:** `chore/od-003-migration` (a fresh branch — the earlier
  `chore/od-003-node-cdk-upgrade` had its registration-only PR #89 already merged).
- **PR:** #105 into `main`.
- **Commits:** `f09416c` (version bump + both deprecated-API migrations across the six
  stacks) and `109102b` (migrate the Story 3.2 correlator + 3.3 synthesizer, which landed
  on `main` after the branch was cut and were picked up via a `git merge origin/main` to
  avoid the stale-branch trap).
- **Files:** `infra/package.json`, the five stack files that define Lambdas /
  the tracking table, and this RUNBOOK note. (`ztie-forensic-infra-stack.ts` was untouched
  — it defines no Lambda log retention or table PITR.)
- **Offline proof-bar (sandbox is INTEGRATIONS_ONLY, npm registry blocked so no full
  `synth`):** `tsc --noEmit` shows only the documented missing-`aws-cdk-lib` error family
  and **no new error type** from these edits; `prettier --check` clean; both new prop
  names verified against current CDK docs; `check_docs.py` PASS and `test_check_docs` OK.
- **Remaining:** the live per-stack `cdk deploy` verification above — the reason OD-003
  stays **open** until you run it (covenant: no close on inference).
