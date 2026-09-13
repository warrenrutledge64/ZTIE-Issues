Owner action — push two annotated restore tags (`restore/phase-3-green` + `restore/story-4.5-green`) on the ZTIE-Issues repo.

# CONTEXT
The restore-tag baseline had drifted behind the validated work: the newest tag was
`restore/story-2.5-green`, but every validated ✅ story since (2.6, 3.1–3.5 which
CLOSED Phase 3, and 4.1/4.2/4.3/4.5) was untagged. This closes that gap with the two
sensible restore points — the Phase-3 boundary and the last-validated Phase-4 floor
BEFORE the in-progress Story 4.6 rework — so we have a clean known-good code baseline
to fall back to if the 4.6 rework goes badly.

This is a **tags-only** close (an explicit, stakeholder-approved partial): a
by-the-book restore point pairs the git tag with a live state MANIFEST (RESTORE.md
rule 4). The paired manifest capture for both tags is deferred to a scheduled
follow-up (recorded in the RUNBOOK Operational Debt Register as OD-004). Until the
manifests are captured, these two tags are the CODE half of the restore point; the
STATE half follows.

This is an OWNER action — it requires real `git push` rights the executor does not
have in this sandbox.

# THE EXACT TARGET COMMITS (pin these SHAs — do NOT tag `origin/main`'s tip)
> **Why explicit SHAs, not `origin/main`:** a restore tag pinned to "current main
> tip" can DRIFT if any PR merges between this prep and your push (this bit us on the
> 2.3 tag). Pin the exact validated-close commits below. They are already on `main`
> and immutable.

- `restore/phase-3-green`  -> **`e2b325d`**  (Merge PR #122 `docs/story-3.5-validate`
  — the commit that flipped Story 3.5 ✅ and marked **Phase 3 CLOSED**; RD-040).
- `restore/story-4.5-green` -> **`537d61c`** (Merge PR #138 `docs/story-4.5-validate`
  — the 4.5 ✅ flip; RD-045. It is a DESCENDANT of the 4.5 build merge #136
  `bf2f11f` AND the live Decimal-fix merge #137 `5d7fa96`, so it pins the
  FULLY-VALIDATED 4.5 code, not the pre-fix build — the fix-after-merge guard).

# PRE-PUSH RE-VERIFY (run these first; all must pass)
```
git fetch origin
```
Confirm both targets are still on `origin/main` and 4.5's live fix is included:
```
git merge-base --is-ancestor e2b325d origin/main && echo "phase-3 target on main OK"
git merge-base --is-ancestor 537d61c origin/main && echo "4.5 target on main OK"
git merge-base --is-ancestor 5d7fa96 537d61c && echo "4.5 target includes the live fix OK"
```
Confirm the tags do not already exist:
```
git tag -l 'restore/*'
```
Expect the seven existing tags (phase-1, phase-2-floor, story-2.0, 2.0E, 2.1, 2.3,
2.5) and NEITHER `restore/phase-3-green` NOR `restore/story-4.5-green` yet.

# PUSH THE TWO ANNOTATED TAGS (pinned to the explicit SHAs)
```
git tag -a restore/phase-3-green e2b325d -m "Phase 3 CLOSED (validated live 2026-09-13, RD-040): combined-event normalize + Nova Pro correlation + three-score risk + findings/remediations + advisory recommended_verdict; all verdict-free, human-gated. Code half; state manifest deferred (OD-004)."
git push origin restore/phase-3-green
```
```
git tag -a restore/story-4.5-green 537d61c -m "Story 4.5 validated live 2026-09-13 (RD-045): per-execution tiered report (Executive/Security/Developer) incl. the live Decimal rank fix (PR #137). Last-validated Phase-4 floor before the 4.6 rework. Code half; state manifest deferred (OD-004)."
git push origin restore/story-4.5-green
```

# VERIFY
```
git tag -l 'restore/*'
git cat-file -t restore/phase-3-green    # expect: tag  (annotated)
git cat-file -t restore/story-4.5-green  # expect: tag  (annotated)
git rev-list -n 1 restore/phase-3-green    # expect deref -> e2b325d
git rev-list -n 1 restore/story-4.5-green  # expect deref -> 537d61c
```

# CONSTRAINTS
- Pin the EXPLICIT SHAs above — do NOT tag `origin/main`'s current tip (drift guard),
  and do NOT tag anything BEFORE those merges (that would point the restore at
  pre-validation code).
- **Annotated** (`git tag -a`) only. **Immutable** — once pushed, never move/re-point/
  delete (RESTORE.md rule 2).
- These are plain annotated git tags pushed directly to `origin`. RUNBOOK.md /
  PROJECT_PLAN.md are updated in the SAME PR that adds this prompt (the tag names are
  referenced there); no separate doc edit is needed at push time.
- Do NOT capture the state manifests here — that is the OD-004 follow-up (needs a live
  AWS session in the Hub + Forensic + Pipeline-Sandbox accounts).

# WHEN DONE
Report back: the two `git rev-list -n 1` deref SHAs (expect `e2b325d` / `537d61c`),
the `git cat-file -t` type (expect `tag` for both), and the full `git tag -l
'restore/*'` list (expect NINE tags). Paste it back so the executor confirms the
restore-point baseline is closed (code half) and OD-004 tracks the manifest capture.
