# Story A.6 — OWNER ACTION: push the two outstanding annotated restore tags

> **What this is.** Copy-paste-ready commands for the **repo owner** to push the two
> annotated restore tags that Story A.6 closes. The executor sandbox has **no push
> rights for tags**, so this is your (owner) direct action against `origin`. After you
> push, the executor verifies on `origin` and — on your confirmation — records the dated
> Validation Result and flips A.6 ✅.
>
> **No live AWS is needed.** A.6 is a pure git-tag action. The deployed-state manifests
> these tags pin were already captured + `verify`-clean in Story A.4 (both accounts,
> `VERIFY: MATCH`, exit 0, 2026-09-02).

## Targets (locked by the executor, verified against `origin/main` on 2026-09-08)

| Tag | Target commit | Why this commit |
|-----|---------------|-----------------|
| `restore/phase-2-floor-green` | `642fc7f87b8cd11802b53d6cf127b4cd26e3983b` (PR #41 merge — the merged Story A.4 status commit) | Carries **both** floor manifests (`restore-manifests/manifest-20260902T201610Z.json` Hub, 4 proj · `restore-manifests/manifest-20260902T201931Z.json` Forensic, 11 proj); is an ancestor of `main`; matches the dominant "tag the story's PR-merge commit" convention. **NOT** the newer 2.0E Forensic manifest commit (`cb6b5c5`), **NOT** pre-validation code. |
| `restore/story-2.3-green` | `630887ca032a0bbf554d4993310354bd6daa8360` (`origin/main` current tip) | At/after the PR #60 merge (`cb60d03`) that flipped Story 2.3 ✅; the commits on top are docs-only and do not touch 2.3's code or its validation result. This is exactly what `docs/session-briefs/story-2.3-restore-tag-PROMPT.md` prescribes ("tag `origin/main`'s current tip"). |

> **Before you run:** these SHAs were resolved against `origin/main` at tip
> `630887c` (Merge PR #74, A.5 reconcile). If `main` has advanced since, re-resolve
> `restore/story-2.3-green` to the **current** `origin/main` tip (the floor tag stays
> pinned at `642fc7f` regardless — it is a fixed historical commit).

## Step 0 — sync and confirm the gap (run first)

```bash
git clone https://github.com/warrenrutledge64/ZTIE-Issues.git   # skip if already cloned
cd ZTIE-Issues
git fetch origin --tags
git checkout main
git reset --hard origin/main
git ls-remote --tags origin
```

Expect the remote to list exactly four `restore/*` tags and NOT the two below:
`restore/phase-1-green`, `restore/story-2.0-green`, `restore/story-2.0E-green`,
`restore/story-2.1-green`. If either `restore/phase-2-floor-green` or
`restore/story-2.3-green` already exists, **STOP** and tell the executor — do not re-tag
or overwrite.

## Step 1 — create + push `restore/phase-2-floor-green`

```bash
git tag -a restore/phase-2-floor-green 642fc7f87b8cd11802b53d6cf127b4cd26e3983b \
  -m "Phase-2 floor: 2.0 + 2.1 validated; Hub+Forensic deployed-state manifests captured and verify-clean 2026-09-02 (Story A.4)"
git cat-file -t restore/phase-2-floor-green      # MUST print: tag  (annotated, not "commit")
git push origin restore/phase-2-floor-green
```

## Step 2 — create + push `restore/story-2.3-green`

```bash
# Re-resolve the tip if main has advanced; otherwise this pins 630887c.
git tag -a restore/story-2.3-green origin/main \
  -m "Story 2.3 validated live 2026-09-05: dynamic detonation lane (ephemeral EC2 + host-native SSM), 4/4 DoD pass"
git cat-file -t restore/story-2.3-green          # MUST print: tag
git push origin restore/story-2.3-green
```

## Step 3 — confirm all six tags are on `origin`

```bash
git ls-remote --tags origin | grep -E 'restore/(phase-1-green|story-2\.0-green|story-2\.0E-green|story-2\.1-green|phase-2-floor-green|story-2\.3-green)'
```

You should see **all six**:
`restore/phase-1-green`, `restore/story-2.0-green`, `restore/story-2.0E-green`,
`restore/story-2.1-green`, `restore/phase-2-floor-green`, `restore/story-2.3-green`
(each also appears with a `^{}` dereferenced line — that is the normal annotated-tag
form and is expected).

## Step 4 — tell the executor

Report back the two tag target SHAs and the `git ls-remote --tags origin` output showing
all six. The executor will then verify independently on `origin`, record the dated
Validation Result in `RUNBOOK.md` + `docs/STORY_DETAIL.md`, and flip A.6 ✅ (the covenant:
no recorded confirmation → A.6 stays open).

## Ground rules (from `docs/SETTING_AND_REMOVING_RESTORE_POINTS.md`)

- **Annotated only** (`git tag -a … -m …`); `git cat-file -t <tag>` must print `tag`.
- **Push to `origin`** and **confirm on `origin`** (`git ls-remote`) — a tag only on your
  laptop is a phantom baseline.
- **Do not tag pre-validation code**; the targets above are at/after each story's recorded
  validation.
