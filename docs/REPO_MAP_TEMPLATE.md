# Repo Map — Reusable OS-Layer Template

> **Purpose.** A repeatable, drift-proof way to produce a structural map of any
> repository, so a map can be handed to a planning partner (e.g. Gemini) or a new
> team member as accurate ground truth — not a hand-drawn diagram that silently
> rots as directories get renamed.
>
> **This is the reusable OS layer.** It is deliberately free of ZTIE specifics.
> The project-instance layer for this repo is `docs/repo-map.annotations.json`
> (the phase/role labels) and the generated `docs/REPO_MAP.md` (the output).

---

## Why a generator instead of a hand-drawn tree

A hand-drawn tree is an *instance snapshot* that starts drifting the moment it is
written. The first ZTIE map did exactly this: it dropped the `hub_` prefix from six
directories (`correlate/` vs the real `hub_correlate/`, etc.) and asserted a per-file
layout for `intake/` that was not true. Those are precisely the errors a path-doing
executor trips over.

The fix is to treat **map generation as a repeatable process**, not an artifact:

- **REPO FACTS** are read from `git ls-tree` every run — names and counts are always
  correct for the committed ref.
- **INTERPRETATION** (phase/role framing) lives in a small JSON file and is *validated
  against the real tree*. A label pointing at a directory that no longer exists is
  reported as drift, never silently rendered.

## The two layers (hard separation)

| Layer | Source | Trust | Where it lives |
|---|---|---|---|
| **REPO FACTS** | `git ls-tree -r -t <ref>` | Authoritative | Generated on every run |
| **INTERPRETATION** | annotations JSON | Human framing, validated | `docs/repo-map.annotations.json` |

This mirrors the project's standing *reusable-OS-vs-instance* separation: the generator
+ this template are the OS layer (liftable to any repo); the annotations + output are the
instance layer.

## Procedure (repeatable, ~30 seconds)

```bash
# 1. Facts-only map of the current repo at HEAD (no interpretation):
python3 scripts/gen_repo_map.py

# 2. Full map with phase/role interpretation, written to the tracked file:
python3 scripts/gen_repo_map.py --ref main \
    --annotations docs/repo-map.annotations.json \
    -o docs/REPO_MAP.md

# 3. Drift gate — fails (exit 3) if any annotation targets a path that no longer exists:
python3 scripts/gen_repo_map.py --ref main \
    --annotations docs/repo-map.annotations.json --check
```

Re-run step 2 after any structural change (a new lambda, a renamed directory) and commit
the refreshed `docs/REPO_MAP.md`. Step 3 is suitable as a CI / pre-commit check.

## Authoring the annotations file

`docs/repo-map.annotations.json` is plain JSON with these keys (all optional):

| Key | Type | Meaning |
|---|---|---|
| `title` | string | Heading for the generated map |
| `intro` | string | One-paragraph orientation shown under the header |
| `roles` | object | `"<relative/path>": "<role text>"` — one line per directory or file |
| `groups` | array | Ordered conceptual groupings: `{ "label", "note", "paths": [...] }` |
| `footer` | string | Closing notes (topology, workflow, caveats) |

**Rule:** every path in `roles` and in every group's `paths` must exist in the tree at
the mapped ref. The generator validates this and, under `--check`, exits non-zero on any
mismatch. Keep interpretive labels (phase names, node nicknames) in the annotations file —
never bake them into the REPO FACTS output, so a reader can always tell fact from framing.

## Lifting this to another repo

1. Copy `scripts/gen_repo_map.py` into the target repo (stdlib only — no install).
2. Write a fresh `docs/repo-map.annotations.json` for that repo's directories (or run
   facts-only with no annotations to start).
3. Run the procedure above. Optionally wire step 3 into CI.

## Guarantees & limits

- **Deterministic:** output is sorted, so re-running on the same commit is byte-stable and
  diffs are meaningful.
- **Offline:** stdlib only; runs in a network-restricted sandbox.
- **Scope:** maps *structure* (directories, counts, immediate file layout). It does not
  parse code, infer dependencies, or read the RUNBOOK — those remain in the living docs.
- **Depth:** breaks down top-level directories and their immediate subdirectories, and
  lists the immediate files of leaf directories. Deeper nesting is summarized by count.
