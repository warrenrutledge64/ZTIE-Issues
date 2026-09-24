# OD-004 — restore-tag STATE-MANIFEST capture (turn-key stakeholder runbook)

> **What this closes.** OD-004 (RUNBOOK Operational Debt Register). Two restore TAGS were
> pushed **code-half only** on 2026-09-13:
> - `restore/phase-3-green` → commit **`e2b325d`**
> - `restore/story-4.5-green` → commit **`537d61c`**
>
> A by-the-book restore point pairs the tag with a **live state manifest** (RESTORE.md rule 4)
> whose pinned `governance_commit.sha` equals the tag's target commit. Those manifests were
> never captured, so the STATE half is missing and a coordinated code+state restore to these
> points is not yet possible. This runbook captures them.
>
> **Who runs this:** the STAKEHOLDER, in AWS CloudShell with ambient creds (no `--profile`).
> It CANNOT be run from the offline build sandbox (no live AWS). It is **read-only** (the
> `capture` + `verify` subcommands never mutate AWS — see `scripts/ztie_restore/`).

---

## SCOPE — hub + forensic ONLY (why NOT sandbox)

The OD-004 register text said "Hub + Forensic + Pipeline-Sandbox manifests," but the correct,
honest scope is **hub + forensic**, for two independent reasons:

1. **The tool supports only `hub` and `forensic`.** `scripts/ztie_restore/targets.py` defines
   exactly two `AccountTarget`s (`HUB` = 641628980935, `FORENSIC` = 360999005254);
   `resolve_account` rejects anything else. There is no `sandbox` capture plan.
2. **The Sandbox account holds no ZTIE durable state to capture.** Pipeline-Sandbox
   (586917955591) is the **PDE-owned** ZTIE→PDE landing zone (BOM.md §1). ZTIE's responsibility
   ends when the artifact lands there; its only resource is the PDE landing bucket, which is
   PDE's to own/restore, not ZTIE's. Capturing it would contradict the topology (and RD-012,
   which scopes ZTIE's durable state to the Hub).

So a complete, correct restore point for these two tags = a **Hub manifest + a Forensic
manifest** each, pinned to the tag's commit. (If the stakeholder later decides ZTIE should also
snapshot the Sandbox landing bucket config, that is a separate change: add a `sandbox`
`AccountTarget` first — it is not part of OD-004.)

---

## PRE-FLIGHT (once, in CloudShell)

```
# 1) Clone / cd to the repo, then check out the FIRST tag's commit so the manifest's
#    governance_commit.sha will pin to it. (Capture reads AWS live state, but it also records
#    the CURRENT git commit as governance_commit — so check out the tag before capturing.)
cd ~/ZTIE-Issues || git clone https://<TOKEN>@github.com/warrenrutledge64/ZTIE-Issues.git ~/ZTIE-Issues && cd ~/ZTIE-Issues
git fetch origin --tags

# 2) Confirm the two tag targets (should print the commits below):
git rev-parse restore/phase-3-green^{}    # expect e2b325d727291b479261fbf4aa4e4540faf2f7b9
git rev-parse restore/story-4.5-green^{}  # expect 537d61c8491e600038aa2f023d9e6ae5773b44c9
```

> **NOTE on the git commit the manifest pins.** `capture` records `governance_commit.sha` from
> the repo's CURRENT `HEAD`. To pin a manifest to a tag, **check out that tag's commit before
> capturing** (a detached HEAD is fine — capture is read-only and writes only the manifest file):
> `git checkout e2b325d` (for phase-3) / `git checkout 537d61c` (for 4.5). The manifests you
> commit at the end go on a normal branch (see CLOSE-OUT), but each manifest's *pinned* sha must
> equal its tag's target. If checking out the old commit is inconvenient, capture on `main` and
> we will reconcile the pin in the close-out PR (the executor will confirm
> `git merge-base --is-ancestor <tag-commit> <manifest-pin>` and record the exact relationship).

---

## CAPTURE — run BOTH accounts for BOTH tags (4 manifests total)

You need a manifest per (account × tag). Do the two accounts for one tag, then repeat for the
other. **Run `aws sts get-caller-identity` before each block** and confirm the `Account` matches
the intended account (the #1 recurring live mistake is running a block in the wrong account).

### Tag 1 — `restore/phase-3-green` (commit `e2b325d`)

```
git checkout e2b325d          # detached HEAD; pins governance_commit.sha = e2b325d

# --- HUB (641628980935) tab ---
aws sts get-caller-identity   # confirm "Account": "641628980935"
python3 scripts/ztie-restore capture --account hub
# -> prints: "Captured N projection(s) for account 'hub'." + the manifest path
#            "Governance commit pinned: e2b325d…"  (CONFIRM it says e2b325d)

# --- FORENSIC (360999005254) tab ---
aws sts get-caller-identity   # confirm "Account": "360999005254"
python3 scripts/ztie-restore capture --account forensic
# -> prints the Forensic manifest path + "Governance commit pinned: e2b325d…"
```

### Tag 2 — `restore/story-4.5-green` (commit `537d61c`)

```
git checkout 537d61c          # detached HEAD; pins governance_commit.sha = 537d61c

# --- HUB tab ---
aws sts get-caller-identity   # confirm 641628980935
python3 scripts/ztie-restore capture --account hub

# --- FORENSIC tab ---
aws sts get-caller-identity   # confirm 360999005254
python3 scripts/ztie-restore capture --account forensic
```

You will now have **4 new files** under `restore-manifests/manifest-<UTC>.json`.

---

## VERIFY (read-only — proves the manifest matches live state)

For EACH of the 4 manifests, run `verify` against the SAME account it was captured in and
confirm it reports **MATCH / no drift** (verify compares a restore-relevant PROJECTION —
identity + desired-state fields — so volatile metadata like SSM version bumps / CFN
CREATE-vs-UPDATE status do NOT count as drift):

```
# example — do this for all 4 (hub+forensic × both tags), in the matching account tab:
python3 scripts/ztie-restore verify  --account hub      --manifest restore-manifests/manifest-<UTC>.json
python3 scripts/ztie-restore verify  --account forensic --manifest restore-manifests/manifest-<UTC>.json
```

---

## PASTE BACK (to the executor)

Paste back, verbatim:
1. The **4 manifest file paths** + for each, the printed **"Governance commit pinned: …"** line.
2. The **`verify` output** for each (expect MATCH / no drift).
3. `git rev-parse restore/phase-3-green^{}` and `restore/story-4.5-green^{}` (re-confirm targets).

The executor then, on a `docs/od-004-manifest-capture` branch:
- **commits the 4 manifest files** under `restore-manifests/` (they are the deliverable);
- **adds the BOM.md §4 rows** pairing each tag with its Hub + Forensic manifest paths + each
  manifest's pinned `governance_commit.sha` (confirming it equals the tag's target commit, per
  RESTORE.md rule 4);
- updates `BOM.md`'s "Current restore point" note if appropriate;
- **closes OD-004** in the RUNBOOK Operational Debt Register (remove the row + a dated CLOSED
  note) — an OD closes only when the follow-through is actually done, with dated evidence;
- runs `python3 scripts/check_docs.py` (PASS) + `python3 -m unittest scripts.test_check_docs`
  (OK, after removing OD-004 from the open-OD fixture) and opens the close-out PR.

---

## GOTCHAS (from prior live captures — RESTORE.md + the tag-drift lesson)

- **`/tmp` is wiped when CloudShell recycles** — if you export a template or intermediate file,
  regenerate it in the new session before consuming it.
- **Manifests must pin the tag's commit, not `main`'s tip.** Capture on the tag's checked-out
  commit (above), or the executor reconciles the pin in the close-out.
- **Tag targets don't drift here** — both tags are annotated and already pushed (fixed-historical
  commits `e2b325d` / `537d61c`), so unlike an owner-gated push there is no re-verify-at-push
  step. Still, re-print the two `rev-parse` lines so we record them.
- **Read-only:** `capture` and `verify` never call a mutating AWS API. Only `restore` mutates,
  and this runbook never runs `restore`.
