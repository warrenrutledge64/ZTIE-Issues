Owner action — tag `restore/story-2.3-green` on the ZTIE-Issues repo.

# CONTEXT
Story 2.3 (the dynamic detonation lane — ephemeral EC2 + host-native SSM execution)
was validated live 2026-09-05: all 4 Definition-of-Done checks passed in Forensic
360999005254 (see `docs/STORY_DETAIL.md#story-2-3` for the verbatim evidence), and
the paired status commit (PR #60, "flip 🟡 -> ✅") is merged to `main`. `RUNBOOK.md`'s
master story table and `PROJECT_PLAN.md` already reference the restore tag
`restore/story-2.3-green` as if it exists — but it does NOT: `git tag -l` currently
shows only `restore/phase-1-green`, `restore/story-2.0-green`, and
`restore/story-2.1-green`. This is the one real remaining item to close Story 2.3
out completely, and it is an OWNER action (requires real git push rights the
executor does not have in this sandbox).

# WHAT TO DO

```
git fetch origin
git log --oneline -5 origin/main
```
Confirm the PR #60 merge commit ("Merge pull request #60 ... flip 🟡 -> ✅") is an
ancestor of the current `origin/main` tip. Commits after it are fine and expected
(docs-only PRs #61/#62/#63 may have landed on top — none of them touch Story 2.3's
code or its validation result, so they do not invalidate the tag target).

```
git tag -a restore/story-2.3-green origin/main \
  -m "Story 2.3 validated live 2026-09-05: dynamic detonation lane (ephemeral EC2 + host-native SSM), 4/4 DoD pass"
git push origin restore/story-2.3-green
```

Then verify:
```
git tag -l
```
Expect it to now list `restore/phase-1-green`, `restore/story-2.0-green`,
`restore/story-2.1-green`, and `restore/story-2.3-green`.

# CONSTRAINTS
- Tag `origin/main`'s CURRENT tip (do not tag an older commit and do not tag anything
  BEFORE the PR #60 merge — that would point the restore at pre-validation code).
- This is a plain annotated git tag pushed directly to `origin` — it is NOT a story,
  NOT a PR, and does NOT touch RUNBOOK.md/PROJECT_PLAN.md (they already correctly
  reference this tag name; no doc edit is needed here).
- Nothing else is in scope for this session. Do not start Story 2.4 or any other
  work here — this prompt is scoped to exactly one action.

# WHEN DONE
Report back the tag's target commit SHA and the `git tag -l` output confirming all
four restore tags are present. Story 2.3 is then fully closed out (code + governance
+ restore point all consistent), and Story 2.4 (behavioral telemetry capture) is
ready to start in its own session per `docs/session-briefs/story-2.4-PROMPT.md`.
