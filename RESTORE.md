# {{PROJECT_NAME}} — Backup & Restore-Point Procedure

> A **coordinated code + state** restore capability: when a slice goes badly,
> revert both the source (git) and the live state (whatever the code
> deploys/produces) back to a known-good restore point, as one unit. This is the
> defense against code-vs-deployed drift.

## What a "restore point" is

A restore point pairs two halves, captured together:

1. A **git tag** — `restore/phase-N-green` — marking the exact commit that passed
   a phase's end-of-phase validation.
2. A **state manifest** — a versioned file capturing the live state at that moment
   ({{what "state" means for this project — e.g. infrastructure resources, config,
   deployed versions, data schema}}), committed to the repo and reflected in
   [`BOM.md`](BOM.md).

Restoring one without the other is never necessary — they move as a unit.

## Tagging convention

| Purpose | Format | Example |
|---------|--------|---------|
| Phase end-of-phase restore point | `restore/phase-<N>-green` | `restore/phase-0-green` |

**Rules:**
1. **Pass-only** — created only after the phase's live validation passes and is
   confirmed. Never on inference.
2. **Immutable** — once pushed, never moved, re-pointed, or deleted. A superseding
   phase gets its own new tag; the old one stays.
3. **Annotated** (`git tag -a`) — carries a message, author, and date.
4. **Paired with a manifest** — recorded in [`BOM.md`](BOM.md).

The `restore/` prefix is reserved exclusively for restore points, so
`git tag -l 'restore/*'` lists exactly the restore points and nothing else.

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
history trustworthy. {{Note who enables this and how — often a repo-owner setting.}}

## Git-side revert procedure

**Never force-push `main`.** Reverting preserves history.

**Revert a merged change (preferred):**
```bash
git checkout -b revert/<desc>
git revert <bad-commit-sha>            # for a merge commit: git revert -m 1 <merge-sha>
git push origin revert/<desc>
# open a PR and merge it (main is PR-only)
```

**Roll `main` back to a restore point:**
```bash
git fetch --tags origin
git checkout -b restore/back-to-phase-<N>-green
git restore --source=restore/phase-<N>-green --staged --worktree -- .
git commit -m "Restore code to restore/phase-<N>-green"
git push origin restore/back-to-phase-<N>-green
# open a PR and merge it
```

> **Code is only half.** Reverting git returns the **source** to a known-good
> point. The **live state** is reverted using the manifest (see state-capture and
> coordinated-restore steps below). Always revert **both together**.

## State capture (fill in for this project)

{{A script/procedure that queries the live system and writes a timestamped,
versioned manifest of the current state, then updates BOM.md. Read-only —
capture must never mutate the live system. Handle the empty/clean case gracefully.}}

## Coordinated restore (fill in for this project)

{{A script/procedure that, given a restore-point tag: (1) checks out the tagged
commit, (2) re-applies the state pinned in that manifest, (3) verifies the
resulting live state matches the manifest.}}

## Restore validation (acceptance)

1. Capture a restore point on a known-good state (tag + manifest).
2. Make a deliberate trivial change to code and to one piece of live state.
3. Run the coordinated restore back to the captured point.
4. Confirm **both** the code and the live state return to known-good, and the
   inventory reflects reality.
