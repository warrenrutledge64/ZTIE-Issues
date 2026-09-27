# Git hooks (opt-in)

Repo-tracked hooks that enforce the governance gate locally, so drift is caught
at commit time instead of in review.

## Install (once per clone)

```bash
git config core.hooksPath .githooks
```

That points git at this directory. Nothing is installed globally and no file
outside the repo is touched.

## What runs

- **`pre-commit`** — runs [`scripts/check_docs.py`](../scripts/check_docs.py)
  before every commit and blocks the commit if it fails. This includes:
  - **CHECK M** — fails if `docs/REPO_MAP.md` has drifted from the tree, or if an
    annotation in `docs/repo-map.annotations.json` targets a path that no longer
    exists. Fix by regenerating:
    ```bash
    python3 scripts/gen_repo_map.py --ref main \
        --annotations docs/repo-map.annotations.json -o docs/REPO_MAP.md
    ```
    then re-stage `docs/REPO_MAP.md`.
  - all the existing CHECK A–L governance-doc integrity rules.

## Bypass

`git commit --no-verify` skips the hook. Use it sparingly and only when you
understand why the gate is complaining.

## Note on CI

This is a **local developer** convenience. Authoritative enforcement for this
project is AWS-native (CodeBuild/CodePipeline) per the operating model; wire
`python3 scripts/check_docs.py` into that pipeline as the buildspec step for the
same guarantee on the server side.
