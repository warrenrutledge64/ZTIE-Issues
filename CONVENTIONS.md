# Repository Conventions (reusable across projects)

> A small, durable standard for how any project in this operating model is laid out
> and named. New projects adopt this from day one; existing projects conform at a
> natural editing break (never via a risky big-bang move). The goal is a repo whose
> **root explains itself at a glance** and whose names are predictable everywhere.

## 1. Root layout

The repository root holds **only**:

```
README.md      ← the dashboard / landing page (always at root)
LICENSE        ← conventional at root
.gitignore     ← and other dotfiles
docs/          ← ALL documentation lives here (see §2)
<code dirs>    ← language/tool-standard code directories (see §3)
```

**Rule:** no loose governance/spec `.md` files at the root. If it is prose, it lives
under `docs/`. The only markdown at root is `README.md`.

## 2. The `docs/` tree

One documentation home, lowercase, sub-foldered **by purpose**:

```
docs/
  governance/       PROJECT_PLAN, RUNBOOK, METHODOLOGY, RESTORE, BOM, TRANSITION_PLAN, CONVENTIONS
  architecture/     ARCHITECTURE, COMPLIANCE, and design notes
  session-briefs/   per-story briefs + prompts + the brief/prompt templates
```

- **`governance/`** — the operating-system docs: the plan, the live status ledger,
  the methodology, restore procedure, bill of materials, and any transition plans.
  These are first-class deliverables (held to the same bar as code).
- **`architecture/`** — how the system is built and how it maps to controls.
- **`session-briefs/`** — the warm handoff for each unit of work.

## 3. Code directories

Standard, purpose-named, **lowercase** — unchanged by this convention:

```
infra/     IaC (CDK/Terraform/…)
services/  or lambdas/ — application/runtime code
schemas/   data contracts
scripts/   CLI tools + generators
```

Use the ecosystem-standard name for the stack in play; do not invent casing
variants (`infra`, not `Infra`).

## 4. Naming rules

| Thing | Rule | Example |
|-------|------|---------|
| Folders | lowercase, purpose-named | `governance/`, not `Docs/` / `docs/` |
| Root markdown | only `README.md` | — |
| Restore tags | `restore/<milestone>-green` | `restore/phase-2-floor-green` |
| Feature branches | `feature/<story-id>` | `feature/story-2.2` |
| Docs branches | `docs/<topic>` | `docs/conventions` |
| Fix branches | `fix/<topic>` | `fix/hub-lambda-bundling` |
| Branch lifecycle | delete after merge (kept only if deliberately retained for reference) | — |
| Reusable construct archive (infra) | its own versioned repo | `infra-building-blocks` |

## 5. Adoption

- **New project:** start with this layout — `README.md` + `LICENSE` at root, a
  `docs/{governance,architecture,session-briefs}/` tree, standard code dirs.
- **Existing project (e.g. ZTIE):** conform **incrementally** at a natural break, not
  via a high-churn move. ZTIE consolidates casing now (`docs/` → `docs/`) and
  relocates its remaining root governance docs into `docs/governance/` as part of a
  step that is already editing those docs (planned for TRANSITION_PLAN step **T1.5**),
  so the link-rewrite churn piggybacks on edits already in flight and the restore
  lineage is not perturbed mid-transition.

> This file itself will move to `docs/governance/CONVENTIONS.md` when ZTIE performs
> its T1.5 consolidation. Until then it lives at root as the visible standard.
