# Setting and Removing Restore Points

**A ZTIE-Issues operational user guide.**

> **Who this is for.** Anyone on the ZTIE team who needs to create, trust, or retire a
> restore point — from a junior developer running their first `git tag`, to the ITIL /
> PMP / Scrum / Product roles who own change enablement, baselines, and delivered value.
> The concepts are kept rigorous; the hands-on steps are spelled out fully with real,
> copy-paste-ready commands. No prior git/AWS fluency is assumed.

> **Scope note.** This is an operational how-to. It describes ZTIE's own restore
> mechanism and discipline. It does **not** claim ZTIE "is compliant" with any framework;
> the discipline-specific vocabulary is used to make the practice legible to those roles,
> not to assert certification.

---

## 1. What a restore point *is* in ZTIE

A **restore point** is a **configuration baseline** for the ZTIE pipeline: a captured,
known-good state you can deliberately return to. In the language of the roles who own it:

| Role | Reads a restore point as… |
|------|---------------------------|
| **ITIL 4 MP** | A **configuration baseline** established under **change enablement**; the set of Configuration Items (CIs) is recorded in service **configuration management** with `BOM.md` as the **CMDB**. |
| **PMP** | A **baseline** under **configuration management / change control**; the sanctioned point a **rollback** returns to. |
| **Scrum Master** | The repeatable, drift-preventing safety net that protects the team from **rework**. |
| **Product Owner** | The mechanism that protects **delivered value** — a stakeholder-visible guarantee that we can get back to a working, accepted state. |
| **Junior Developer** | A named git tag plus a saved snapshot of what's actually deployed in AWS. |

### 1.1 A ZTIE restore point is deliberately TWO coordinated things

It is **not** just a git tag. It is a pair that must be kept in sync:

1. **CODE restore point** — an **annotated git tag** named `restore/<milestone>-green`,
   pushed to GitHub (`origin`). It pins the exact known-good commit of code **and**
   governance docs.
   - Examples that exist today: `restore/phase-1-green`, `restore/story-2.0-green`,
     `restore/story-2.1-green`.

2. **DEPLOYED-STATE restore point** — a **JSON manifest** in the `restore-manifests/`
   folder, produced by the `scripts/ztie_restore/` tooling (`capture` / `verify` /
   `restore`). It captures the **live AWS resource state** as a *restore-relevant
   projection*: identity + desired-state only (CloudFormation template hash + parameters
   + tags, DynamoDB config, Lambda code hash, S3 config, SSM params) — **not** raw data.
   - Examples captured today (the Phase-2 floor):
     - `restore-manifests/manifest-20260902T201610Z.json` — **Hub**, 4 projections
     - `restore-manifests/manifest-20260902T201931Z.json` — **Forensic**, 11 projections

> **The rule that makes it "real":** a restore point exists only when **BOTH** parts
> exist **and agree** — the tag pins the commit, the manifest pins the deployed state, and
> **`BOM.md` indexes them together**. `BOM.md` is the CMDB / configuration-item inventory;
> if a resource is deployed, it is in `BOM.md`, and it maps to a restore point. A tag with
> no manifest, or a manifest with no tag, or either one not recorded in `BOM.md`, is **not
> a restore point** — it is a loose end.

### 1.2 The three-account nuance (restore behaves differently per account)

ZTIE spans three AWS accounts, and "restore" does **not** mean the same thing in each:

- **Pipeline-Hub (`641628980935`)** — the **brains / control plane**. Holds the **durable
  record** (the DynamoDB tracking table + the data-contract ingestion gate). This account
  **MUST be truly restorable**; **its manifest matters most**. When in doubt, protect the
  Hub.

- **Forensic (`360999005254`)** — the disposable **blast zone** (isolated VPC, ephemeral
  EC2 detonation, raw artifacts). It holds only **ephemeral** state by design, so the
  model is **"REBUILD, don't restore":** re-stand-up the infrastructure from code + its
  manifest. Raw payloads are **disposable and NOT restored**.

- **Pipeline-Sandbox (`586917955591`)** — the ZTIE→PDE handoff landing zone. Once an
  artifact lands there it is **under PDE control**, so it is largely **OUT of ZTIE's
  restore scope**.

See the [per-account cheatsheet](#4-per-account-cheatsheet) in §4 for the short version.

### 1.3 Ground rules you must respect (every time)

- **Annotated tags only.** Always `git tag -a` (annotated), **never** lightweight. Always
  `git push` the tag to `origin`.
- **Nothing is "backed up" on inference.** After a `capture`, run `verify` and confirm it
  reports **MATCH (clean)** before you trust the baseline. "It probably worked" is not a
  baseline.
- **Live AWS commands are the OWNER's action, in AWS CloudShell.** There are no shared
  credentials. Before **every** AWS block, run `aws sts get-caller-identity` to confirm
  which account you are in. **Hub and Forensic need SEPARATE CloudShell tabs.**
- **Run AWS/CloudShell commands ONE LINE AT A TIME** (do not paste a whole block at once).
- **`/tmp` is wiped when CloudShell recycles** — anything you exported there (e.g. a
  template body) must be regenerated in a fresh session before you use it.
- **Restoring code is destructive.** `git reset --hard <tag>` throws away uncommitted work
  and moves your branch. Always **look first** with `git checkout <tag>` (§3.4).
- **Removing a restore point is a change-control action** — it deletes a safety net. It
  requires a deliberate confirmation and reconciling `BOM.md` / `RUNBOOK.md` (§5).

---

## 2. Before you start (one-time orientation)

Everything code-side runs from the **repo root**. Clone it and step in:

```bash
git clone https://github.com/warrenrutledge64/ZTIE-Issues.git
cd ZTIE-Issues
```

The tooling entrypoint is a Python script run from the repo root:

```bash
python3 scripts/ztie-restore --help
```

It has exactly three subcommands: `capture` (read-only), `verify` (read-only), and
`restore` (mutating, confirm-gated). You will use `capture` and `verify` for *setting* a
restore point.

> **How to tell you're in the right place:** `ls BOM.md RESTORE.md scripts/ztie-restore`
> should list all three without error. If it errors, you are not in the repo root.

---

## 3. SETTING a restore point (establishing a controlled baseline)

This is a **change-enablement** activity: you are proposing and then ratifying a new
configuration baseline. The order matters — **capture and verify the deployed state
first**, then tag the code that produced it, then index both in the CMDB.

**The three steps:**
- **3.1** Capture deployed state **per account** and **verify MATCH**.
- **3.2** Create + push the annotated code tag on the validated commit.
- **3.3** Record it in `BOM.md` (the CMDB) so code and state are indexed together.

### 3.1 Capture deployed state per account, then VERIFY

> **Where:** AWS CloudShell, in the **owner's** account session. Hub and Forensic are
> **separate tabs**. One account at a time.

#### 3.1.a — Hub (the account that matters most)

**Step 1 — Open the Hub CloudShell tab and confirm the account.** Run this first, on its
own:

```bash
aws sts get-caller-identity
```

Look at the `"Account"` field in the output. It **must** be `641628980935` (Hub). If it
says anything else, you are in the wrong tab — stop and switch.

**Step 2 — Capture the Hub's live projection to a fresh manifest:**

```bash
python3 scripts/ztie-restore capture --account hub
```

- **What it does:** reads (read-only, mutates nothing) the Hub stack + tracking DynamoDB +
  validator Lambda + quarantine S3, and writes a new timestamped file under
  `restore-manifests/`.
- **How to tell it worked:** it prints something like
  `Captured 4 projection(s) for account 'hub'.` and
  `Manifest written: restore-manifests/manifest-<UTC>.json`. **Copy that exact manifest
  path** — you need it in the next step and in `BOM.md`.
- If a stack is not deployed, capture **refuses** and tells you which stack was not found
  rather than writing a half-empty manifest. Deploy first, then capture.

**Step 3 — VERIFY the manifest reports MATCH (this is the trust step):**

```bash
python3 scripts/ztie-restore verify --account hub --manifest restore-manifests/manifest-20260902T201610Z.json
```

(Substitute the manifest path printed in Step 2.)

- **What "good" looks like:** the last line reads
  `VERIFY: MATCH — live projection equals the manifest (no drift).` and the command exits
  `0`.
- **If it says `VERIFY: DRIFT`** (exit `3`): the live state changed after capture, or
  something is off. **Do not tag.** Re-capture from clean state and verify again.

> **Why verify right after capture?** It proves the manifest is a faithful projection of
> live state *now* — that's the "no baseline on inference" rule. Verify compares only the
> restore-relevant projection, so a genuine re-deploy (which bumps CloudFormation status,
> SSM version, timestamps) still reports **MATCH**, not false drift.

#### 3.1.b — Forensic (rebuild-not-restore, but still captured)

**Step 1 — Open a SEPARATE CloudShell tab for Forensic and confirm the account:**

```bash
aws sts get-caller-identity
```

The `"Account"` field **must** be `360999005254` (Forensic). Different account = different
tab. Do not run Forensic commands in the Hub tab.

**Step 2 — Capture Forensic's config projection:**

```bash
python3 scripts/ztie-restore capture --account forensic
```

- This captures the intake stack + intake Lambda + artifact S3 **config only**. The raw
  payloads are **ephemeral and NOT captured** — that is by design (Forensic is the blast
  zone).
- Note the printed manifest path (today's example: `manifest-20260902T201931Z.json`, 11
  projections).

**Step 3 — VERIFY Forensic reports MATCH:**

```bash
python3 scripts/ztie-restore verify --account forensic --manifest restore-manifests/manifest-20260902T201931Z.json
```

(Substitute the path from Step 2.) Confirm `VERIFY: MATCH` / exit `0`.

**Step 4 — Bring the manifests back into the repo.** The manifests live in the git repo
under `restore-manifests/`. Commit the two you intend to keep (from a machine with the
repo checked out):

```bash
git add restore-manifests/manifest-20260902T201610Z.json restore-manifests/manifest-20260902T201931Z.json
git commit -m "restore: capture Phase-2 floor deployed-state manifests (Hub + Forensic), verify MATCH"
```

> **Easy mistake:** capturing in CloudShell and never getting the manifest file into the
> repo. The manifest is a Configuration Item — it must be committed, or the "deployed-state
> half" of the restore point does not actually exist in version control.

### 3.2 Create and push the annotated code tag

Now pin the **exact commit** whose code produced the state you just verified. Do this on a
machine with the repo checked out (not CloudShell).

**Step 1 — Make sure you're on the validated commit.** Confirm what you're about to tag:

```bash
git log -1 --oneline
```

The commit shown here is what the tag will point at. It should be the commit that includes
the validated code **and** the committed manifests from §3.1. If it isn't, check out the
right commit first.

**Step 2 — Create the ANNOTATED tag** (note `-a` and `-m` — never a bare `git tag <name>`):

```bash
git tag -a restore/phase-2-floor-green -m "Phase-2 floor: 2.0 + 2.1 validated; Hub+Forensic manifests captured and verify-clean 2026-09-02"
```

- **Naming:** always `restore/<id>-green`. Use the milestone/story id (`phase-1`,
  `story-2.0`, `story-2.1`, `phase-2-floor`). The `-green` suffix means "validated / known
  good."

**Step 3 — Confirm it's annotated** (this is how you catch a lightweight tag):

```bash
git cat-file -t restore/phase-2-floor-green
```

This must print `tag` (an annotated tag object). If it prints `commit`, you made a
lightweight tag by mistake — delete it (`git tag -d restore/phase-2-floor-green`) and redo
Step 2 **with `-a`**.

**Step 4 — Push the tag to origin** (a tag that only lives on your laptop is not a restore
point):

```bash
git push origin restore/phase-2-floor-green
```

**Step 5 — Confirm origin actually has it:**

```bash
git ls-remote --tags origin | grep restore/phase-2-floor-green
```

If this returns a line, the tag is on GitHub. If it returns nothing, the push didn't take —
repeat Step 4.

> **Recurring gap (see §6):** a tag named in `BOM.md`/`RUNBOOK.md` that was **never
> pushed** — the docs reference `restore/phase-2-floor-green` but `git ls-remote` finds
> nothing. That is a phantom baseline. Step 5 is how you prevent it.

### 3.3 Record it in `BOM.md` (the CMDB) — index code + state together

The restore point is not "real" until the CMDB indexes both halves. Update `BOM.md` so
each affected resource row points at the **tag**, the **commit**, and the **manifest
path(s)**. Follow the existing format in `BOM.md`.

- Update the header block:
  - **`Last updated:`** date + what closed.
  - **`Current restore point:`** the new tag, with a one-line description and the manifest
    paths, e.g. `restore-manifests/manifest-20260902T201610Z.json` (Hub, 4 projections)
    and `restore-manifests/manifest-20260902T201931Z.json` (Forensic, 11 projections).
- In the **Deployed / Produced Artifacts** table, set each row's **Restore point** column
  to the tag `@ <commit>` plus the manifest path that covers it (the existing rows show the
  exact style, e.g. `` restore/phase-2-floor-green @ 33fa6b0; …manifest-20260902T201931Z.json ``).
- Update the **`RUNBOOK.md` "Restore tag" column** for the story/phase this baseline closes.

Then commit the documentation as part of the same baseline:

```bash
git add BOM.md RUNBOOK.md
git commit -m "docs(cmdb): index restore/phase-2-floor-green (tag + commit + Hub/Forensic manifests) in BOM + RUNBOOK"
git push origin HEAD
```

> **Change-enablement checkpoint:** at this point the baseline is *ratified* — the CIs
> (`BOM.md`), the code pin (annotated pushed tag), and the deployed-state pin (verified,
> committed manifests) all agree. That agreement is the deliverable.

### 3.4 (Reference) Restoring code safely — LOOK FIRST

You don't restore when *setting* a baseline, but here's the safe form for when you do,
because it's dangerous:

```bash
# SAFE — look at the tagged code without moving your branch (detached HEAD, non-destructive):
git checkout restore/phase-2-floor-green
```

```bash
# DESTRUCTIVE — only after you've looked and are sure; this discards uncommitted work
# and moves the branch. Make a branch/backup first.
git checkout main
git reset --hard restore/phase-2-floor-green
```

Restoring **deployed state** is the `restore` subcommand (confirm-gated, prompts `[y/N]`,
fails safe to NO). Full deployed-state restore procedure is in
[`RESTORE.md`](../RESTORE.md); Hub is the primary durable target, Forensic is
rebuild-from-code.

---

## 4. Per-account cheatsheet

| Account | What to capture | Restore vs. Rebuild | What NOT to bother with |
|---------|-----------------|---------------------|-------------------------|
| **Pipeline-Hub** `641628980935` | Full config projection: CFN template hash + params + **tags**, DynamoDB config, validator Lambda code hash, quarantine S3 config, SSM params. **Verify MATCH.** | **RESTORE — truly.** This is the durable control plane; its manifest matters most. Re-apply template+params+tags, then `verify`. | DynamoDB **items** / S3 **objects** (that's data, not config — not in scope of restore). |
| **Forensic** `360999005254` | Config projection of the intake stack + intake Lambda + artifact S3 (**config only**). **Verify MATCH.** | **REBUILD, don't restore.** Re-stand-up infra from code + manifest. It's the disposable blast zone. | **Raw payloads / detonation scratch / ephemeral EC2** — disposable by design, never restored. |
| **Pipeline-Sandbox** `586917955591` | — (nothing, for ZTIE purposes) | Neither. Out of ZTIE's restore scope. | The whole account — once an artifact lands here it's **under PDE control**. Don't capture, tag, or restore it as part of ZTIE. |

---

## 5. REMOVING a restore point (a change-controlled action)

Removing a restore point **removes a safety net**. Treat it as a change-control action:
have a reason, get a deliberate confirmation, and **reconcile the CMDB** so nothing ever
references a tag that no longer exists.

### 5.1 Decide and confirm (the change-control gate)

Before deleting anything, answer out loud (or in the PR / change record):
- **Why** is this baseline being retired? (Superseded by a newer green? Created in error?)
- **What replaces it?** There should almost always be a newer `restore/<id>-green` that is
  still valid, so the team is never left with **zero** restore points.
- **Deliberate confirmation:** get the explicit go-ahead from whoever owns the baseline
  (Product Owner / change authority). This is not a routine cleanup — it reduces
  recoverability.

### 5.2 Delete the tag locally AND on origin

A tag lives in two places. You must remove **both**, or it "comes back" on the next fetch.

**Step 1 — Delete the local tag:**

```bash
git tag -d restore/phase-2-floor-green
```

Expected output: `Deleted tag 'restore/phase-2-floor-green' (was <sha>)`.

**Step 2 — Delete the tag on origin** (note the `:refs/tags/` form — this is a *delete*):

```bash
git push origin :refs/tags/restore/phase-2-floor-green
```

**Step 3 — Confirm it's gone from origin:**

```bash
git ls-remote --tags origin | grep restore/phase-2-floor-green
```

This should return **nothing**. If it still shows the tag, Step 2 didn't take — repeat it.

> **Easy mistake:** deleting the local tag only. `git tag -d` alone leaves the tag on
> GitHub, and the next `git fetch --tags` re-creates it locally. Always do both steps.

### 5.3 Retire the manifest (only if appropriate)

The deployed-state half is a manifest file under `restore-manifests/`. Retire it **only**
if this baseline is genuinely being decommissioned and nothing else references those
manifests:

```bash
git rm restore-manifests/manifest-20260902T201610Z.json restore-manifests/manifest-20260902T201931Z.json
```

> **Caution:** manifests are cheap and are historical evidence of a known-good state. If
> unsure, **keep the manifest** and only remove the tag + reconcile the CMDB. Deleting a
> manifest that another baseline still points at will break that baseline.

### 5.4 Reconcile `BOM.md` and `RUNBOOK.md` (mandatory)

This is the part that keeps the CMDB honest. After removing a tag, **no document may
reference it.**

**Step 1 — Find every reference to the tag across the repo:**

```bash
grep -rn "restore/phase-2-floor-green" .
```

**Step 2 — Fix each hit:** in `BOM.md` update the `Current restore point:` header and any
Restore-point column cells to the tag that now applies; in `RUNBOOK.md` update the
**"Restore tag"** column for the affected stories. Do not leave a row pointing at a deleted
tag.

**Step 3 — Re-run the grep to prove zero references remain:**

```bash
grep -rn "restore/phase-2-floor-green" .
```

This must return **nothing** (except, arguably, this guide's examples). A hit here means
the CMDB still references a tag that no longer exists — the exact drift removal is supposed
to prevent.

**Step 4 — Commit the reconciliation as one change:**

```bash
git add BOM.md RUNBOOK.md restore-manifests/
git commit -m "chore(restore): retire restore/phase-2-floor-green; reconcile BOM + RUNBOOK (no dangling references)"
git push origin HEAD
```

---

## 6. Common mistakes / anti-patterns

- **Tagging a commit whose live state has since drifted.** You captured, then something
  changed in AWS, then you tagged the old commit. The tag and manifest now disagree. **Fix:
  always `verify` MATCH immediately before tagging** (§3.1) and tag the commit that
  includes the verified manifests.
- **A tag referenced in docs but never pushed (the recurring gap).** `BOM.md`/`RUNBOOK.md`
  name a `restore/<id>-green` that `git ls-remote --tags origin` can't find. It's a phantom
  baseline — there is nothing to roll back to. **Fix: always do §3.2 Step 5 (confirm on
  origin) before recording the tag in the CMDB.** *(This has actually happened in this repo:
  `restore/phase-2-floor-green` is referenced in the docs but is not yet a pushed tag.)*
- **Running a block in the wrong account.** Capturing "Hub" while your CloudShell is
  actually in Forensic (or vice-versa) produces a manifest that lies. **Fix: run
  `aws sts get-caller-identity` and read the `Account` field before every block; keep Hub
  and Forensic in separate tabs.**
- **Pasting `<placeholders>` literally.** Copying `--manifest restore-manifests/manifest-<UTC>.json`
  verbatim will fail — `<UTC>` is not a real filename. **Fix: substitute the actual path
  the `capture` step printed.**
- **Using a lightweight tag.** `git tag <name>` (no `-a`) creates a lightweight tag with no
  message, author, or date — not an auditable baseline. **Fix: always `git tag -a … -m …`
  and confirm with `git cat-file -t <tag>` prints `tag`.**
- **Trusting a capture without verifying.** "Capture succeeded, so we're backed up." No —
  capture only writes a file. **Fix: `verify` must report `MATCH` (exit 0) before you trust
  it.**
- **Trying to restore Forensic's raw payloads.** They're ephemeral and disposable by
  design. **Fix: rebuild Forensic infra from code + manifest; don't chase the payloads.**
- **Treating Sandbox as ZTIE's to restore.** Once an artifact lands in Pipeline-Sandbox
  it's PDE's. **Fix: leave it out of ZTIE restore points entirely.**
- **`/tmp` amnesia in CloudShell.** You exported a template to `/tmp`, the session
  recycled, and now the file's gone mid-restore. **Fix: regenerate `/tmp` artifacts in the
  current session before you use them.**
- **Deleting a tag locally only.** It reappears on the next fetch. **Fix: delete both
  local (`git tag -d`) and origin (`git push origin :refs/tags/<tag>`), then confirm with
  `git ls-remote`.**

---

## 7. Related documents

- [`RESTORE.md`](../RESTORE.md) — the full deployed-state capture/verify/restore procedures
  and the Story 1.R restore-validation (acceptance) gate.
- [`BOM.md`](../BOM.md) — the CMDB / configuration-item inventory; maps each resource to its
  restore tag + manifest.
- [`RUNBOOK.md`](../RUNBOOK.md) — story/phase status with the **"Restore tag"** column.
- `scripts/ztie_restore/` — the `capture` / `verify` / `restore` tooling
  (`python3 scripts/ztie-restore --help`).
