# Story A.4 — LIVE capture + verify runbook (stakeholder, two CloudShells)

> **This is the ONLY live-run part of A.4, and only YOU can do it** (the executor has
> no AWS creds). You run `capture` then `verify` in **both** accounts; the executor
> **records the returned output verbatim** into RUNBOOK 2.0/2.1 detail, BOM §4, and the
> Floor & Harvest Plan. **Nothing is recorded on inference** — paste back exactly what
> the commands print.

## Ground rules (these have bitten us every session)

- **TWO accounts → TWO CloudShell tabs.** Capture the **Hub** state (641628980935) from a
  **Hub-authed** shell and the **Forensic** state (360999005254) from a **Forensic-authed**
  shell. A banner comment does **not** change the account.
- **Run `aws sts get-caller-identity` BEFORE every block** and read the `Account`. If it
  is not the account the block is for, switch tabs — do not proceed.
- **Feed commands ONE LINE AT A TIME.** Never paste a multi-line block; a stray line can
  execute in the shell.
- **`/tmp` is wiped when CloudShell recycles.** If a session drops, re-clone / re-checkout
  before re-running. Manifests are written under `restore-manifests/` in the repo, not
  `/tmp`, so a committed/pushed manifest survives.
- **GitHub auth in CloudShell:** token-in-URL HTTPS form —
  `git remote set-url origin https://<TOKEN>@github.com/warrenrutledge64/ZTIE-Issues.git`.
  (Rotate any PAT you pasted in the clear.)

## STEP 0 (BOTH tabs) — get the A.4 code that targets the Phase-2 shape

The capture must run with the **A.1 target extension** (this PR's branch), or it will
back up only the frozen Phase-1 shape and MISS all of Story 2.0/2.1. Use whichever is
true when you run:

- **If this PR is already merged:** use `main`.

  ```
  cd ~/ZTIE-Issues && git fetch origin -q && git checkout main && git reset --hard origin/main
  ```

- **If not yet merged:** use the story branch.

  ```
  cd ~/ZTIE-Issues && git fetch origin -q && git checkout docs/story-a4-floor-restore && git reset --hard origin/docs/story-a4-floor-restore
  ```

Confirm the extension is present (should print the three Forensic stacks):

```
python3 -c "import sys; sys.path.insert(0,'scripts'); from ztie_restore.targets import resolve_account; print([s.stack_name for s in resolve_account('forensic').stacks])"
```
Expect: `['ZtieIntakeStack', 'ZtieStaticScanStack', 'ZtieForensicInfraStack']`

> **Note on the pinned governance commit.** The manifest pins `governance_commit.sha`
> = the repo HEAD you capture from. Capturing from the branch pins the branch commit and
> flags nothing dirty (as long as you did the `reset --hard`). That is fine for A.4 —
> the executor records the manifest as-captured; the final `restore/phase-2-floor-green`
> tag is placed on the merged status commit.

---

## TAB 1 — HUB (641628980935)

**H-0. Confirm account**
```
aws sts get-caller-identity --query Account --output text
```
Expect: `641628980935`. If not, switch to your Hub tab.

**H-1. Capture the Hub projection**
```
python3 scripts/ztie-restore capture --account hub
```
Record: the full printed output — the `Manifest written: restore-manifests/manifest-<UTC>.json`
path and the `Governance commit pinned:` line. Save that manifest path as `$HUB_MANIFEST`.

**H-2. Verify (read-only) the Hub projection is clean (no drift)**
```
python3 scripts/ztie-restore verify --account hub --manifest <paste the H-1 manifest path>
```
Record: the final line. **Want:** `VERIFY: MATCH — live projection equals the manifest (no drift).`
(exit 0). If it prints `VERIFY: DRIFT` (exit 3), paste the full JSON diff — we stay on A.4
and reconcile; we do **not** tag the floor.

**H-3. Commit + push the Hub manifest** (so it survives a CloudShell recycle and lands in the PR)
```
git add restore-manifests/
git commit -m "restore(A.4): capture Hub deployed-state manifest (verify-clean)"
git push origin HEAD
```
Record: the committed manifest filename.

---

## TAB 2 — FORENSIC (360999005254)

**F-0. Confirm account**
```
aws sts get-caller-identity --query Account --output text
```
Expect: `360999005254`. If not, switch to your Forensic tab.

**F-1. Capture the Forensic projection**
```
python3 scripts/ztie-restore capture --account forensic
```
Record: the full printed output — the `Manifest written:` path and `Governance commit pinned:`.
Save that path as `$FORENSIC_MANIFEST`.

> This capture resolves `ZtieIntakeStack` (IntakeArtifactBucket, IntakeHandler,
> PreprocessorHandler), `ZtieStaticScanStack` (StaticScanFunction), and
> `ZtieForensicInfraStack` (stack projection) plus the four `/ztie/detonation/*` SSM
> parameters. If a logical id is not found (e.g. a stack/resource name drifted), the tool
> raises a clear `KeyError` — paste it; that is a finding to reconcile, not a pass.

**F-2. Verify (read-only) the Forensic projection is clean**
```
python3 scripts/ztie-restore verify --account forensic --manifest <paste the F-1 manifest path>
```
Record: the final line. **Want:** `VERIFY: MATCH …` (exit 0). On `DRIFT` (exit 3), paste
the JSON diff — stay on A.4.

**F-3. Commit + push the Forensic manifest**
```
git add restore-manifests/
git commit -m "restore(A.4): capture Forensic deployed-state manifest (verify-clean)"
git push origin HEAD
```
Record: the committed manifest filename.

---

## What to paste back to the executor (verbatim)

1. Hub `capture` output (manifest path + governance commit) and Hub `verify` final line + exit.
2. Forensic `capture` output (manifest path + governance commit) and Forensic `verify` final line + exit.
3. The two committed manifest filenames under `restore-manifests/`.

The executor then fills BOM's 11 `pending` rows (tag + SHA + manifest path), records the
A.3 confirmation + A.4 verify-clean results, aligns RUNBOOK ↔ PROJECT_PLAN, and the repo
owner tags `restore/phase-2-floor-green` on the paired status commit.

## Fail / drift handling (covenant)

- Any `verify` that is **not** MATCH, or any `capture` error → **A.4 stays open**; fix or
  reconcile the drift, re-capture, re-verify. **Do not** tag `restore/phase-2-floor-green`
  and **do not** advance to B.1 until both accounts are recorded verify-clean.
