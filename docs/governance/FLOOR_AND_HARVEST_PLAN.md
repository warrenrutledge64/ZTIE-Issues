# ZTIE — Floor & Harvest Plan (get to a backed-up floor, then build the reusable way, in position for the next tier-5 story)

> **The authoritative transition plan.** Self-contained, phased, gate-driven — same
> discipline as [`PROJECT_PLAN.md`](../../PROJECT_PLAN.md) / [`RUNBOOK.md`](../../RUNBOOK.md)
> / [`METHODOLOGY.md`](../../METHODOLOGY.md): dependency-gated, **nothing is "done" on
> inference** (a recorded live/again-provable validation drives status and gates
> advancement), and **every completed step earns a restore point**.
>
> **Supersedes** the earlier `docs/TRANSITION_PLAN.md` draft — this version reflects
> the final agreed ordering (finish the two stories first) and the added
> **Harvest Inventory** step. If both exist, this one is the source of truth.

## 0. Purpose & the drift signal

A 2026-09-01 repo audit found ZTIE is **still building in the fashion that caused the
previous burn-down**: AWS primitives (`s3.Bucket`, `sqs.Queue`, `lambda.Function`,
`RestApi`, `Table`) instantiated **raw and inline in every stack**; the `awsio` seam
**duplicated** across Lambdas; **5 bespoke contract generators** (~160–300 lines
each) re-implementing the same "SCHEMA-dict → json.dump to two paths"; the Hub gate a
**703-line monolith** with 13 repeated per-envelope-kind helpers; **no shared,
parameterized construct library**; and restore practice **half-done** (code tags
exist, but zero deployed-state manifests captured, 11 `pending` rows in BOM).

The stakeholder called a **FULL STOP on new feature work** at the audit, until we are,
in practice, building **micro / decoupled / parameterized components from an archive,
with restore points**. This plan is that stop, made concrete.

> **Honest history (recorded 2026-09-07, Story A.5).** The full-stop was **declared**
> at the audit but did **not** hold as a hard freeze: **Story 2.2 (validated ✅
> 2026-09-03) and Story 2.3 (validated ✅ 2026-09-05) both shipped the OLD, hand-written
> way after the audit.** They were not blocked because the structural gate
> (`scripts/check_docs.py` CHECK B) only blocks new feature work while the Validation
> Debt Register is non-empty, and that register was/became empty. Those stories remain
> ✅ — a recorded live pass never auto-reverts (METHODOLOGY §4); they are candidates for
> *forward* migration onto the archive (Phase C, C.4), not retroactive downgrade. The
> discipline this plan installs therefore applies **going forward from the current
> empty-register state**: the next un-built pipeline work is built the new way once the
> archive exists (Phase C), not by re-opening completed stories.

**Utility over convenience.** The goal is durable, reusable building blocks — not the
fastest path to the next feature.

## 1. Non-negotiable constraints

- **Finish the floor before converting.** Validate 2.0, confirm 2.1, and institute
  real (deployed-state) restore points **before** any archive/refactor work. We do
  not convert on top of un-validated or un-backed-up state.
- **Additive, never a burn-down.** The live system on `main` is not rewritten. The
  archive is *new code*; ZTIE adopts it *incrementally*, and each adoption is **proven
  drift-free by `cdk synth` diff** before any deploy. A stack that can't be proven
  equivalent is stopped and reassessed — never forced.
- **Restore point per step.** Every completed step tags `restore/<id>-green` and,
  where deployed state changed, captures a manifest. Code + state + governance restore
  as one unit.
- **Story closure is decoupled from restore-point work.** A story's closure is driven
  **only by that story's own recorded live validation** and is **decoupled from
  restore-point / capture work** (a separately-tracked activity, e.g. A.4). No single
  story's ✅ is ever contingent on downstream capture or archive work. This reconciles
  with the "finish the floor" framing above (validate 2.0, confirm 2.1, then institute
  deployed-state restore points) without making any one story's ✅ hostage to that
  capture work.
- **Parameterization principles** (define once, vary by prop):
  1. **Secure/opinionated defaults are baked in, not parameters** (a caller can't turn
     off KMS / block-public / SSL / fail-closed). Secure by construction.
  2. **Only real, observed variation becomes a prop** — no speculative knobs. Add a
     prop when a *second real use* needs it; interfaces firm up over first uses
     (start at `0.x`).
- **Harvest before build.** We inventory *what to extract and its parameters* from the
  real repo (evidence-based) **before** writing the archive — so the archive is built
  to a spec, not a guess.
- **The practice is the deliverable.** By the exit, "build a component" = "instantiate
  a parameterized construct from the archive," recorded as **RD-022**.

## 2. Phases

### Phase A — Finish & back up the Phase-2 floor
*2.0 ✅ (live), 2.1 ✅ (confirmed), both backed by deployed-state restore points, and
the capture tooling correct for the post-2.1 shape. The known-good floor we convert
from — and the fallback if conversion goes wrong.*

**Gate:** 2.0 validated live + flipped ✅; 2.1 confirmed ✅ on `main`; deployed-state
manifest captured + `verify`-clean for **both** accounts; BOM's 11 `pending` rows
filled; `restore/story-2.0-green` + `restore/phase-2-floor-green` pushed.

### Phase B — Harvest inventory (survey → decide what to parameterize/archive)
*A deliberate catalog of every repeated/duplicated pattern in the repo, each with a
proposed component boundary, its baked-in defaults vs. its parameters, the number of
current call-sites it replaces, and a harvest priority. This inventory IS the
archive's build spec.*

**Gate:** `docs/governance/HARVEST_INVENTORY.md` reviewed and accepted; each candidate
has a decided parameter surface (or is explicitly deferred).

### Phase C — Build the archive & convert to the practice
*A separate, versioned, parameterized construct archive exists; the shared Python seam
+ one generator replace the duplication; at least one ZTIE stack is migrated onto the
archive, drift-proven; building-the-new-way is the default and is recorded.*

**Gate:** archive repo builds + tests green + is consumable; ZTIE imports it; the first
migrated stack synthesizes to an identical (or explainably identical) template and
re-deploys "(no changes)"; RD-022 recorded in `PROJECT_PLAN.md`, METHODOLOGY note +
templates updated.

### Exit — Ready to build the next pipeline story the new way
*The next un-built pipeline story is NOT part of this plan. This plan ends when that
next story can be started by instantiating archive constructs rather than hand-writing
a stack. By the dependency graph that next story is a **tier-5 story — 2.4 or 2.6**
(they are independent siblings; the graph does not order them, so neither is "the"
target over the other). (Corrected 2026-09-07, Story A.5: the earlier text named
"Story 2.2" as the exit target, but 2.2 shipped the old way on 2026-09-03 and can no
longer be the next-built-the-new-way story.)*

## 3. Registered decision introduced here

| ID | Decision | Rationale |
|----|----------|-----------|
| **RD-022** | Components are built as **parameterized, decoupled, reusable micro-constructs** drawn from a shared, versioned archive (`infra-building-blocks`), with **secure defaults baked in and only real variation exposed as props**. ZTIE adopts the archive **additively** and migrates existing stacks only when **proven drift-free by `cdk synth` diff** — never by rewrite. Every transition step earns a restore point. | The previous effort burned down from accreting hand-written, duplicated stacks. Reuse-by-construction (not copy-paste) + drift-proven migration + restore points prevents recurrence. Utility over build convenience. |

> RD-022 is proposed here; copied into `PROJECT_PLAN.md` §5 when Phase C's gate passes.

## 4. Stories

> Status: `⬜ Not Started` · `🟡 In Progress` · `⛔ Blocked` · `✅ Done (validated)`.
> ✅ only on a recorded, confirmed pass (the RUNBOOK gate).

> **Status now lives in the RUNBOOK.** [`RUNBOOK.md`](../../RUNBOOK.md) is the single
> source of truth for the status of these A/B/C stories. They are **no longer a
> separate block**: each A/B/C story is now interleaved into the RUNBOOK's one master
> table in its true dependency build-tier (per [`METHODOLOGY.md`](../../METHODOLOGY.md)
> §1a), carrying a `Track = F&H` label — find them by that label. The table below is
> retained for narrative and dependency reference only and is no longer authoritative
> for status. If this table and the RUNBOOK ever disagree on a status, the RUNBOOK
> wins; update it there, not here.

| Story | Title | Depends on | Status | Restore tag |
|-------|-------|-----------|--------|-------------|
| **A.1** | Merge the capture-tooling extension (post-2.1 targets) to `main` — the stale `feature/restore-targets-phase2` branch was NOT merged (it predates the docs consolidation, single-pane RUNBOOK, G-3 gate, and this plan; merging it would revert that governance state — the base-branch trap). Its **substance** (the `targets.py` Phase-2 target extension) was re-applied onto latest `main` in the A.4 PR. | — | ✅ | (folded into A.4 PR) |
| **A.2** | **Validate Story 2.0 live** (7 DoD checks, §6) → record + flip ✅ | 2.0 built | ✅ | `restore/story-2.0-green` |
| **A.3** | Confirm Story 2.1 ✅ on `main` (validated 2026-09-01) — no re-run; fold into the floor. **Confirmed (A.4 session, 2026-09-02):** 2.1 is ✅ on `main`, its dated live Validation Result is recorded in `docs/STORY_DETAIL.md#story-2-1`, and its deployed shape is a capture target for the floor manifest — no re-validation performed. | 2.1 ✅ | ✅ | (folds into floor) |
| **A.4** | Institute deployed-state restore points: `capture` + `verify` both accounts, commit manifests, fill BOM's 11 `pending` rows. **Validated (2026-09-02):** both accounts captured + `verify`-clean (Hub `manifest-20260902T201610Z.json`, Forensic `manifest-20260902T201931Z.json` — each `VERIFY: MATCH`, exit 0, empty changed/missing/unexpected); BOM's 11 rows filled + §4 floor row added. Tag `restore/phase-2-floor-green` placed by the repo owner on the merged A.4 status commit. | A.1, A.2 | ✅ | `restore/phase-2-floor-green` |
| **B.1** | **Harvest inventory** — survey the repo; catalog candidates + parameter surfaces + priority in `docs/governance/HARVEST_INVENTORY.md` | A.4 | ⬜ | (docs) |
| **C.1** | Stand up the archive repo `infra-building-blocks` (CDK L3 lib; peer-dep `aws-cdk-lib`; jest Template tests; SemVer `0.x`; checkpoint tags) | B.1 | ⬜ | archive `v0.1.0`+ |
| **C.2** | Build the parameterized constructs the inventory selected (e.g. `SecureBucket`, `ContractIngestQueue`, `OneWaySenderGrant`, `SecureRestApi`, `ContractGateLambda`, `AccountGuardedStack`) | C.1 | ⬜ | archive tag per construct |
| **C.3** | Shared Python seam + one generator: extract duplicated `awsio` + the hub-gate envelope-kind pattern into an importable module; collapse the 5 bespoke generators into ONE parameterized generator (identical output, hash-matched) | A.4 | ⬜ | `restore/shared-seam-green` |
| **C.4** | Migrate ONE ZTIE stack onto the archive as proof: rewrite to constructs, prove `cdk synth` = same CloudFormation (or explainable diff), one live "(no changes)" deploy | C.2 | ⬜ | `restore/migrate-<stack>-green` |
| **C.5** | Record the practice: RD-022 into `PROJECT_PLAN.md`; METHODOLOGY "build-from-archive" note; update BRIEF/PROMPT templates + `CONVENTIONS.md`; relocate remaining root governance docs into `docs/governance/` (the deferred move) | C.4 | ⬜ | (docs) |
| **A.5** | Correct this plan's drift (2026-09-07): exit target 2.2 → next tier-5 story (2.4/2.6); rewrite the §0 full-stop paragraph to the honest history (2.2/2.3 shipped the old way after the audit). Docs-only; changes no story's status. | A.4 | ⬜ | (docs) |
| **A.6** | Push the outstanding deployed-state restore tags `restore/phase-2-floor-green` (A.4 floor) + `restore/story-2.3-green` (Story 2.3) — owner action; both referenced across the docs but not yet present on `origin`. | A.4, 2.3 | ⬜ | (tags) |

## 5. Definition of Done (this plan) — exit gate

1. **2.0 ✅** (recorded live) and **2.1 ✅** confirmed on `main`.
2. **Deployed-state restore instituted:** manifests captured + `verify`-clean (Hub +
   Forensic); BOM has zero `pending`; `restore/phase-2-floor-green` pushed.
3. **Harvest inventory accepted** (`docs/governance/HARVEST_INVENTORY.md`).
4. **Archive exists and is real:** `infra-building-blocks` builds, tests pass,
   version-tagged, ZTIE can `import` it.
5. **Parameterized-by-construction proven:** ≥1 ZTIE stack migrated, identical/explained
   synth diff, "(no changes)" deploy.
6. **Duplication reduced:** shared seam + single generator replace the copies.
7. **Practice recorded** (RD-022 + METHODOLOGY + templates + CONVENTIONS).

On all seven: **the full stop lifts**; the next un-built pipeline story (tier-5:
2.4 / 2.6) begins — built the new way.

## 6. Story A.2 — Story 2.0 live validation runbook (Forensic 360999005254)

All in the **Forensic** CloudShell. `ZtieForensicInfraStack` is standalone (no
cross-account context). The **7 DoD checks**:

**STEP 0 — code + account**
```
cd ~/ZTIE-Issues && git fetch origin -q && git checkout main && git reset --hard origin/main
cd infra && npm install
aws sts get-caller-identity --query Account --output text     # 360999005254
```

**STEP 1 — deploy (check 1: stack deploys)**
```
npx cdk deploy ZtieForensicInfraStack --require-approval never
aws cloudformation describe-stacks --stack-name ZtieForensicInfraStack --query "Stacks[0].Outputs" --output table
```
Save `VpcId`, `DetonationLaunchTemplateId`, `DetonationInstanceRoleArn`, `AmiParameterName`.

**Checks 2 & 7 — isolated VPC, no IGW/NAT, no `0.0.0.0/0` route**
```
VPC=<VpcId>
aws ec2 describe-internet-gateways --filters "Name=attachment.vpc-id,Values=$VPC" --query 'InternetGateways[].InternetGatewayId' --output text   # want empty
aws ec2 describe-nat-gateways --filter "Name=vpc-id,Values=$VPC" --query 'NatGateways[].NatGatewayId' --output text                                 # want empty
aws ec2 describe-route-tables --filters "Name=vpc-id,Values=$VPC" --query "RouteTables[].Routes[?DestinationCidrBlock=='0.0.0.0/0']" --output json  # want [] everywhere
```

**Check 3 — VPC endpoints (S3 gateway + SSM/SSMMessages/EC2Messages/Logs/SQS/Bedrock interfaces)**
```
aws ec2 describe-vpc-endpoints --filters "Name=vpc-id,Values=$VPC" --query "VpcEndpoints[].[ServiceName,VpcEndpointType,State]" --output table
```

**Check 4 — launch template resolves a valid AMI via SSM**
```
LT=<DetonationLaunchTemplateId>
aws ec2 describe-launch-template-versions --launch-template-id "$LT" --versions '$Latest' --query "LaunchTemplateVersions[0].LaunchTemplateData.{ImageId:ImageId,Instance:InstanceType,Imdsv2:MetadataOptions.HttpTokens}" --output table
aws ssm get-parameter --name /ztie/ami/ubuntu-22.04 --query 'Parameter.Value' --output text    # want an ami-... id
```
*(Known: the Ubuntu AMI was set manually earlier; the AL2023 build failed. 2.0 defaults to ubuntu-22.04, so this should resolve. If the param is empty, that is the finding — fix or note it.)*

**Check 6 — UserData has `shutdown -h +5`**
```
aws ec2 describe-launch-template-versions --launch-template-id "$LT" --versions '$Latest' --query "LaunchTemplateVersions[0].LaunchTemplateData.UserData" --output text | base64 -d    # want: shutdown -h +5
```

**Check 5 — instance role has `AmazonSSMManagedInstanceCore`**
```
ROLE=$(echo "<DetonationInstanceRoleArn>" | sed 's#.*/##')
aws iam list-attached-role-policies --role-name "$ROLE" --query "AttachedPolicies[].PolicyName" --output text
```

**On all 7 pass:** record the dated Validation Result in RUNBOOK 2.0, flip ✅ (paired
commit), tag `restore/story-2.0-green`. **On any fail:** stay on 2.0, fix, re-validate.

## 7. Sequence

```
A.1 merge capture tooling ─► A.2 VALIDATE 2.0 (live) ─► A.3 confirm 2.1
                                     │
                                     ▼
              A.4 capture+verify+BOM ─► tag restore/phase-2-floor-green
                                     │   [FLOOR SET — backed up]
                                     ▼
              B.1 HARVEST INVENTORY (survey repo → what to parameterize/archive)
                                     │
        ┌────────────────────────────┼───────────────────────────┐
        ▼                            ▼                            ▼
 C.1 archive repo ─► C.2 constructs   C.3 shared seam + one generator
        └─────────────┬──────────────┘
                      ▼
             C.4 migrate ONE stack (drift-proven) ─► C.5 record practice + doc relocation
                      ▼
          ── EXIT: in position to build the next tier-5 story (2.4/2.6) from the archive ──
```

## 8. What only the stakeholder can do (out-of-band)

- **A.2 / A.4:** run the live AWS commands in CloudShell (validation + `capture`/
  `verify`) — the executor has no live creds.
- **C.1:** create the empty `infra-building-blocks` GitHub repo (executor builds the
  contents; cannot create repos under the account).
- **All merges** remain the repo-owner's action (PR-based, never direct to `main`).
