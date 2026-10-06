# Portfolio Dashboard - concept capture (idea parking, not built yet)

> **Why this file exists.** To capture the idea in GitHub so it is not forgotten.
> This is a concept note only. Nothing here is built, scheduled, or started. It
> lives on the `Dashboard` branch as a placeholder for a future, separate project.

## The idea in one line

A single portfolio dashboard the owner uses to run many projects: switch tabs to
see one project (e.g. ZTIE) one moment and another (e.g. PDE) the next, each tab
showing that project's backlog, expandable down into its stories.

## What it is

- A personal project-management / portfolio tool for the owner (a PMP).
- Spans multiple projects (ZTIE, PDE, and more over time), one tab per project.
- Expand a project to see the stories in its backlog.
- Presents the SAME backlog two ways for two audiences:
  - **Manager view** - organized by phase (the what/why; matches `PROJECT_PLAN.md`).
  - **Developer view** - organized by build/dependency order plus the critical
    path and no-block schedule (the Foundation-First / Component-Driven method
    named in `METHODOLOGY.md` section 1a).
- Same stories, one backlog, two presentations. It never becomes a second source
  of truth: per-project status/facts still come from that project's runbook.

## What it is NOT (scope guard)

- NOT the ZTIE product's operator dashboard (that is ZTIE Story 4.3, a Phase-4
  feature inside the pipeline). This portfolio tool sits ABOVE individual projects.
- NOT started, and deliberately not built now: standing up a real tabbed app is its
  own software project and, per our own method, should be planned foundation-first
  in its own repo rather than rushed onto a side branch. Also, ZTIE's own
  foundation work (story 2.0) is still unvalidated, so new build work is on hold.

## Rough data model (for whenever it is built)

```
Portfolio
  -> Project (ZTIE, PDE, ...)        # one tab each
       -> Backlog
            -> Story                 # id, title, phase, build-tier, depends-on, status
```

## Suggested next steps (when the owner chooses to pick this up)

1. Give it its own repo (e.g. `portfolio-dashboard`) - it is cross-project, so it
   should not live inside any single project's repo.
2. Plan it foundation-first as its own project with its own stories.
3. Reuse the two views already designed here: phase (manager) and build order
   (developer), and the "expand project into stories" backlog model above.

_Status: idea captured. No work scheduled._
