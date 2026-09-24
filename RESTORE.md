# ZTIE — Backup & Restore-Point Procedure

> A **coordinated code + state** restore capability: when a slice goes badly,
> revert both the source (git) and the live state (whatever the code
> deploys/produces) back to a known-good restore point, as one unit. This is the
> defense against code-vs-deployed drift.
>
> **Story 1.R** builds the state half of this: a **Python** tool
> (`scripts/ztie-restore`) that captures a **restore-relevant projection** of
> ZTIE's durable state to a timestamped manifest and performs a **coordinated
> restore** back to a manifest. The manifest also **pins the known-good
> governance-doc commit** (RD-015), so code + state + governance move as one unit.

## What a "restore point" is

A restore point pairs two halves, captured together:

1. A **git tag** — `restore/phase-N-green` — marking the exact commit that passed
   a phase's end-of-phase validation.
2. A **state manifest** — a versioned file (`restore-manifests/manifest-<UTC>.json`)
   capturing the live state at that moment. For ZTIE "state" means the
   **restore-relevant projection** of the durable AWS resources (see the schema
   `schemas/restore-manifest.v1.json`): CloudFormation stacks (template hash +
   parameters + **stack-level tags**), the Hub durable DynamoDB tracking table's
   configuration, the Lambda functions (runtime + handler + `code_sha256`), the S3
   bucket *configurations*, and any SSM parameters. The manifest is committed to
   the repo and reflected in [`BOM.md`](BOM.md).

> **Projection, not raw objects — and configuration, not data.** The manifest
> captures desired-state/config only. It does **not** capture DynamoDB items, S3
> object contents, or any data-plane content — a restore point is a configuration
> baseline, not a data backup. And it deliberately excludes volatile metadata
> (SSM `Version`, CFN `StackStatus`/`LastUpdatedTime`/`StackId`, Lambda list
> ordering, ARNs, timestamps) so a legitimate re-deploy never reads as drift.

Restoring one half without the other is never necessary — they move as a unit.

## Tagging convention

ZTIE uses **two** deliberately distinct kinds of green tag. They differ in
granularity, in what they pin, and in when they are created. Keeping them separate
is what keeps the word "restore point" meaningful — a restore point is a *coordinated
code + state* baseline, not merely "a commit that worked."

| Purpose | Granularity | Format | Pins | Example |
|---------|-------------|--------|------|---------|
| **Restore point** — end-of-phase coordinated baseline | **Per phase** | `restore/phase-<N>-green` | **Code + state** (annotated tag **paired with a verified state manifest**) | `restore/phase-1-green` |
| **Checkpoint** — end-of-story rollback marker | **Per story** | `checkpoint/story-<id>-green` | **Code only** (annotated tag; no manifest required) | `checkpoint/story-4.7-green` |

### Restore point (`restore/…`) — the heavyweight, per-phase, code+state baseline

**Rules:**
1. **Pass-only** — created only after the phase's live validation passes and is
   confirmed. Never on inference.
2. **Immutable** — once pushed, never moved, re-pointed, or deleted. A superseding
   phase gets its own new tag; the old one stays.
3. **Annotated** (`git tag -a`) — carries a message, author, and date.
4. **Paired with a manifest** — recorded in [`BOM.md`](BOM.md), and the manifest's
   pinned `governance_commit.sha` must equal the tagged commit.

The `restore/` prefix is reserved exclusively for restore points, so
`git tag -l 'restore/*'` lists exactly the restore points and nothing else.

### Checkpoint (`checkpoint/…`) — the lightweight, per-story, code-half rollback marker

A **checkpoint** is a cheap, frequent, **code-only** rollback marker created at the
close of **each validated story** — the fine-grained safety net *between* the
heavyweight phase restore points. It exists because a phase can span many stories, and
losing a story's worth of validated code to drift or a bad merge should never require
rolling all the way back to the last phase-green. In the roles' vocabulary it is a
**working baseline** / **sprint-increment marker**, distinct from the sanctioned
end-of-phase **configuration baseline**.

**Rules:**
1. **Pass-only** — created only after the story's own live validation passes and is
   recorded in the RUNBOOK (status flipped ✅). Never on inference, never on a still-🟡
   story.
2. **Immutable** — once pushed, never moved, re-pointed, or deleted (same discipline as
   `restore/`).
3. **Annotated** (`git tag -a`) — carries a message, author, and date.
4. **Code-half only, and it says so** — a checkpoint pins the validated commit; it does
   **not** require a paired state manifest, and it must **not** be recorded as a
   `Current restore point` in `BOM.md`. A coordinated code+state restore is only ever to
   a `restore/phase-<N>-green` point. (If you later want the deployed state pinned at a
   checkpoint too, capture a manifest — but that does not make it a restore point; the
   phase-green tag remains the coordinated baseline.)

The `checkpoint/` prefix is reserved exclusively for these per-story markers, so
`git tag -l 'checkpoint/*'` lists exactly the story checkpoints and
`git tag -l 'restore/*'` still lists exactly the coordinated restore points — neither
pollutes the other.

> **Why two prefixes, not one.** Overloading `restore/` for every story close would
> flood the coordinated-baseline namespace, demand a 3-account live manifest capture at
> every story (heavy, and often impossible mid-phase before the phase state settles),
> and dilute the "known-good, fully-restorable" signal. The split gives frequent,
> cheap rollback granularity (checkpoints) **without** weakening the meaning of a
> restore point (phase-green + verified manifest). This is standard baseline vs.
> working-increment discipline (ITIL configuration baseline / PMP change control):
> `restore/` = sanctioned baseline; `checkpoint/` = per-increment rollback marker.

```bash
# Create a per-story checkpoint (only on a confirmed pass, at the story's ✅ commit):
git checkout main && git pull --ff-only origin main
git tag -a checkpoint/story-<id>-green -m "Story <id> pass: <what was validated>, <date>, confirmed by <who>"
git push origin checkpoint/story-<id>-green

# List / inspect story checkpoints (kept separate from restore points):
git tag -l 'checkpoint/*'
git show checkpoint/story-<id>-green --no-patch

# Roll code back to a story checkpoint (code half only — same safe form as restore/):
git fetch --tags origin
git checkout -b restore/back-to-story-<id>-green
git restore --source=checkpoint/story-<id>-green --staged --worktree -- .
git commit -m "Restore code to checkpoint/story-<id>-green"
git push origin restore/back-to-story-<id>-green   # open a PR and merge it (main is PR-only)
```

```bash
# Create (only on a confirmed pass, at the phase's green commit):
git checkout main && git pull --ff-only origin main
git tag -a restore/phase-<N>-green -m "Phase <N> pass: <what was validated>, <date>, confirmed by <who>"
git push origin restore/phase-<N>-green

# List / inspect:
git tag -l 'restore/*'
git show restore/phase-<N>-green --no-patch

# Check out (inspect a known-good state; detached HEAD is expected):
git fetch --tags origin
git checkout restore/phase-<N>-green
git checkout main
```

## Protected main line

`main` must be **change-by-review only**: require a pull request, block direct
pushes, block force-pushes, block deletion. This is what makes restore-point
history trustworthy.

> **ZTIE note (enforcement reality):** the repo is a **private repo on a free
> personal account**, where GitHub does **not** enforce branch protection or
> rulesets (the settings can be created but are not enforced until GitHub Team/
> Enterprise, or the repo is made public). Until then, PR-only is **self-enforced
> by convention** — the repo owner enables protection when the plan/visibility
> changes, and re-runs the direct-push-rejection check afterwards.

## Git-side revert procedure

**Never force-push `main`.** Reverting preserves history.

**Revert a merged change (preferred):**
```bash
git checkout -b revert/<desc>
git revert <bad-commit-sha>            # for a merge commit: git revert -m 1 <merge-sha>
git push origin revert/<desc>
# open a PR and merge it (main is PR-only)
```

**Roll `main` back to a restore point (code half):**
```bash
git fetch --tags origin
git checkout -b restore/back-to-phase-<N>-green
git restore --source=restore/phase-<N>-green --staged --worktree -- .
git commit -m "Restore code to restore/phase-<N>-green"
git push origin restore/back-to-phase-<N>-green
# open a PR and merge it
```

> **Code is only half.** Reverting git returns the **source** to a known-good
> point. The **live state** is reverted using the manifest (below). Always revert
> **both together** — and the manifest's pinned `governance_commit.sha` tells you
> exactly which commit to revert the code to.

---

## The `ztie-restore` tool

A Python 3.12 CLI under `scripts/`. **Python-first** and interactive-safe: the
only mutating action (`restore`) is gated behind a deliberate `input()` confirm
that **fails safe to NO** on empty/negative/EOF input (no shell `/dev/tty`
fiddliness — this is *why* the tool is Python).

Run it from the repo root in **AWS CloudShell** with **ambient credentials**
(no `--profile`). Region defaults to `us-east-1`. The account label is checked
against the live STS identity, so the tool **refuses to act on the wrong account**.

| Subcommand | Mutates? | What it does | Exit codes |
|------------|----------|--------------|------------|
| `capture`  | no (read-only) | writes a fresh `restore-manifests/manifest-<UTC>.json` of the account's projection + pins the governance commit | `0` ok · `2` account mismatch |
| `verify`   | no (read-only) | re-captures live and diffs against a manifest (projection-only) | `0` match · `3` drift · `2` account mismatch |
| `restore`  | **yes** (confirm-gated) | re-applies CFN template+params+**tags** and SSM values, then verifies | `0` ok · `3` post-restore drift · `4` aborted (fail-safe NO) |

Accounts (`--account`): `hub` (Pipeline-Hub 641628980935, `ZtieHubTrackingStack`)
and `forensic` (Forensic 360999005254, `ZtieIntakeStack`). Capture/verify/restore
run **one account at a time**, in that account's CloudShell.

## State capture (read-only)

Captures a timestamped manifest for one account. Never mutates anything.

```bash
# In the HUB CloudShell (account 641628980935):
python3 scripts/ztie-restore capture --account hub
# -> restore-manifests/manifest-<UTC>.json  (Hub stack + tracking DynamoDB + validator Lambda + quarantine S3)

# In the FORENSIC CloudShell (account 360999005254):
python3 scripts/ztie-restore capture --account forensic
# -> a separate manifest for the Forensic intake stack + intake Lambda + artifact S3 (config only; the raw payloads are ephemeral and NOT captured)
```

The manifest records: `schema_version`, `captured_at_utc`, `region`, the pinned
`governance_commit` (repo `HEAD` sha + branch + a `dirty` flag), the `accounts`
actually captured (id + caller ARN), and the `resources` projections. Commit the
manifest you intend to keep as a restore point, then reflect it in `BOM.md`.

> **Empty/clean case:** if a target stack is not deployed, `describe_stacks`
> raises and capture reports which stack was not found rather than writing a
> half-empty manifest. Deploy the stacks first (Hub, then Forensic — see the
> 1.1R brief), then capture.

## Coordinated restore (mutating — confirm-gated)

Re-applies the pinned state for one account **after** the confirm gate. It
re-applies the CloudFormation **template + parameters + stack-level tags** and any
captured SSM values, then runs `verify`.

Because the manifest stores a template *hash* (a projection, not the artifact),
supply the known-good template body to re-deploy. Synthesise it from the tagged
commit's CDK, or export the live stack's template:

```bash
# Option A — export the current live template (before you change anything):
aws cloudformation get-template --stack-name ZtieHubTrackingStack \
  --query TemplateBody --output json > /tmp/ZtieHubTrackingStack.template.json

# Option B — synthesise from the governance-pinned commit:
git checkout <governance_commit.sha>
cd infra && npm ci && npx cdk synth ZtieHubTrackingStack \
  > /tmp/ZtieHubTrackingStack.template.json && cd ..
```

Then run the coordinated restore (it will prompt; anything but an explicit `y`/`yes`
aborts with no changes):

```bash
python3 scripts/ztie-restore restore --account hub \
  --manifest restore-manifests/manifest-<UTC>.json \
  --template ZtieHubTrackingStack=/tmp/ZtieHubTrackingStack.template.json
# Proceed with the coordinated restore? [y/N]:
```

Restore does **not**: restore DynamoDB items / S3 objects (data, not config); touch
Forensic's ephemeral raw payloads / scratch (disposable — rebuilt, not restored);
or re-run CDK for you (it applies the supplied template body directly via
CloudFormation, so it is independent of the toolchain state).

**Code + state together (RD-015):** before/after the state restore, revert the
code to the manifest's pinned commit using the git procedure above
(`restore/back-to-phase-<N>-green`). The manifest's `governance_commit.sha` is the
authoritative pointer for the code half.

## Verify (read-only)

```bash
python3 scripts/ztie-restore verify --account hub \
  --manifest restore-manifests/manifest-<UTC>.json
# prints the projection diff; exit 0 = MATCH (no drift), exit 3 = DRIFT
```

Verify compares **only** the restore-relevant projection, so a real re-deploy
(which bumps CFN status to `UPDATE_COMPLETE`, moves `LastUpdatedTime`, may change
`StackId` on recreate, and bumps SSM `Version`) reports **MATCH**, not false drift.

## Restore validation (acceptance) — the Story 1.R gate

Run live, one account (Hub is the primary durable target):

1. **Capture** a restore point on the known-good state:
   `python3 scripts/ztie-restore capture --account hub` → note the manifest path.
2. **Make a deliberate trivial change** to live state — e.g. add or change a
   stack-level tag on `ZtieHubTrackingStack`, or add a throwaway SSM parameter and
   add it to the target — and confirm `verify` now reports **DRIFT** (exit 3).
3. **Coordinated restore** back to the manifest:
   `python3 scripts/ztie-restore restore --account hub --manifest <path> --template ZtieHubTrackingStack=<template>`
   — answer `y` at the prompt.
4. **Confirm** the post-restore `verify` reports **MATCH** (no false drift), and
   that `BOM.md` reflects reality.
5. **Confirm the gate fails safe:** re-run `restore` and press Enter (empty) or
   type `n` — it must abort with **no changes** (exit 4). (Automatable proof:
   `ZTIE_ASSUME_NO=1 python3 scripts/ztie-restore restore --account hub --manifest <path>`
   aborts without prompting.)

On a confirmed pass, record the dated Validation Result in
[`RUNBOOK.md`](RUNBOOK.md) and flip Story 1.R ✅. The Phase-1 close (capturing
`restore/phase-1-green`) proceeds separately, after 1.2/1.3/1.4 route correctly.
