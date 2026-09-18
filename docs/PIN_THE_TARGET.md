# Pin-the-Target: immutable validation targets for zero-trust split-brain

> **Status:** PROPOSAL (executor-drafted, mechanical only). Ratification is the
> planning brain's (Gemini) act. This document defines a **repeatable, reusable**
> way to hand the Independent Validator an immutable target for **any** story —
> merged or not — replacing the fragile "give the Validator a PR number" step.
> RD-015 (management artifacts are first-class, reusable, durable, repeatable).

## Why the PR/diff step breaks

The original split-brain flow asked for a **PR number** and had the Validator
review its diff. That assumes an **unmerged** PR exists. Once a fix is merged
(the normal end-state of a build/fix session), `git diff <merge-base>...<pr>` is
**empty** — the PR's content is already in `main`. The Validator then has
**nothing to evaluate**, and the temptation is to *fabricate* a fresh PR just to
produce a diff. **Fabricating a PR to satisfy a template is a violation of the
immutable-artifact principle** and a validation drift signal.

## The rule

**Validate the actual state, pinned to an immutable commit — never a manufactured
delta.** The target is defined by:

1. an immutable **commit SHA** (the `main` tip, plus the fix commit(s)),
2. a precise **production-code file scope** with per-file **blob hashes**,
3. a **drift check** proving the files are identical at the fix commit and at
   `main` (nothing altered them after the fix landed), and
4. optionally, a **real baseline→main code diff** (Option 2) — a *non-empty,
   non-fabricated* delta showing what the fix introduced.

Any third party reproduces the exact target from the SHA. No PR required.

## The reusable recipe (read-only)

Run in a current clone. All commands are read-only (`fetch`, `rev-parse`,
`log`, `show`, `diff`, `merge-base`, `cat-file`).

```
# 0. refresh
git fetch origin --tags

# 1. main tip (immutable pin)
git rev-parse origin/main

# 2. find the fix commit(s) for the story
git log --no-merges --oneline <baseline>..origin/main --grep="<story-id>" -i

# 3. confirm each fix commit is actually on main
git merge-base --is-ancestor <fix-sha> origin/main && echo ON-MAIN

# 4. production-code file scope only (exclude docs/evidence churn)
git show --stat --format="" <fix-sha> -- lambdas/ infra/ schemas/ lib/ scripts/

# 5. drift check — files identical at fix commit and at main?
git rev-parse <fix-sha>:<path>      # blob hash at the fix
git rev-parse origin/main:<path>    # blob hash at main  (must be equal)

# 6. (Option 2) the real change delta over the pre-story baseline
git diff <baseline-sha>..origin/main -- <code paths>
```

Or run the tool that does all of this and also extracts the runbook context:

```
python3 scripts/validation_target.py \
  --story 2.4R \
  --fix-commit <fix-sha> \
  --code-path lambdas/detonation/capturespec.py \
  --code-path lambdas/detonation/handler.py \
  --code-path lambdas/detonation/test_capturespec.py \
  --code-path infra/lib/ztie-detonation-stack.ts \
  --baseline-ref <pre-story-baseline-sha>
```

It writes `validation-target-<story>.json` and prints a human block. The output
is safe to paste to the airgapped Validator.

## The RUNBOOK-context extract (the Validator can't see the runbook)

The Independent Validator runs in an isolated chat with **no view into
`RUNBOOK.md`**. It therefore cannot know a story's row, dependencies, DoD, or
prior sealed verdicts unless the package **transports** them. `validation_target.py`
copies — **verbatim, mechanically, with zero interpretation** — the story's:

- master-table row (exact line), and
- Validation Debt Register status + every `SEALED VERDICT` block that names the
  story (exact blocks).

The extractor **never** authors a DoD, **never** asserts pass/fail, **never**
infers status. It transports facts across the airgap; the planning brain owns
the DoD and the verdict.

## Choosing the baseline for Option 2

- Prefer the **parent of the commit that opened the story** (`<open-commit>^`) —
  the tightest honest "before the story" baseline.
- A `restore/<story>-green` tag is a valid baseline **only if** it predates the
  story's own work; if the tag predates a later evidence/regime change, the
  parent-of-open baseline is more honest. State which you used.

## Separation of duties (unchanged)

- **Planning brain (Gemini / Validator):** authors the DoD + live steps, and
  **adjudicates** the sealed verdict.
- **Executor (Kiro):** produces this **read-only, judgment-free** immutable
  target + verbatim context. Executes live steps the package specifies without
  interpreting a verdict.
- **Human airgap (stakeholder):** carries the target + context to the Validator;
  runs the live steps; retains evidence.

"Merged" ≠ "validated." A story stays 🟡 until its own recorded live pass of the
**final** code (the code pinned here).
