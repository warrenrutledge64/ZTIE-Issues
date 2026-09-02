# How the Build Order Is Determined (the sequencing method)

> **Purpose.** This document explains the method used to order the stories in the
> [`RUNBOOK.md`](../../RUNBOOK.md) build-order table: what it is called, where it
> comes from, and the exact factors used to decide each story's position. It is a
> reference/explainer only. The [`RUNBOOK.md`](../../RUNBOOK.md) remains the source
> of truth for story status and dependencies; this document just describes the
> rule by which that table is arranged.
>
> Related: [`../../METHODOLOGY.md`](../../METHODOLOGY.md) section 1a names the wider
> development philosophy; this document is the detailed "how the ordering works"
> underneath it.

## 1. The short version

Stories are ordered by their **dependencies**, not by story number, phase, or
business priority. A story appears only after everything it depends on. This is
called **Dependency-Driven Sequencing**, and the algorithm that produces it is a
**topological sort**, presented as **build tiers**.

## 2. What the method is called, and where it comes from

There are two layers, with different histories:

**The ordering algorithm - Topological Sort.**
- **What it is:** the formal method for ordering the items of a dependency graph so
  that every item comes after the items it depends on. That is exactly what the
  build tiers are.
- **First published:** the commonly used form is **Kahn's algorithm, published by
  Arthur B. Kahn in 1962** ("Topological sorting of large networks",
  *Communications of the ACM*). A second well-known form is the depth-first-search
  based topological sort popularized by **Robert Tarjan in 1976**. Both rest on
  **directed acyclic graph (DAG)** theory.
- **The project-management equivalent:** the **Critical Path Method (CPM)**,
  developed by **DuPont and Remington Rand around 1957**. CPM is the same
  dependency-network idea applied to scheduling; the build tiers are, in PM terms,
  a CPM-style dependency network.

**The development philosophy that says "order by dependency, not by feature
priority" - Foundation-First / Component-Driven Development.**
- This is an industry practice (and appears in scaled frameworks as the
  "Architectural Runway"), not a single dated academic publication, so there is no
  one "first published" date for it. It is named and recorded in
  [`../../METHODOLOGY.md`](../../METHODOLOGY.md) section 1a. It is the *reason* we
  choose to order by dependency; the topological sort is *how* we do it.

## 3. The factors used to determine position (the exact steps)

Position in the table is determined by these steps, in order:

1. **Read the declared dependencies.** The input is each story's `Depends on`
   value in the [`RUNBOOK.md`](../../RUNBOOK.md) table. Dependencies are not
   inferred or guessed; only the stated `Depends on` is used (for example, 2.3
   depends on 2.0; A.2 depends on 2.0; B.1 depends on A.4).
2. **Build the dependency graph (a DAG).** Each story is a node; each "X depends on
   Y" is a directed edge from Y to X. The graph is checked to be **acyclic** (no
   story can transitively depend on itself). A cycle would make ordering
   impossible, and finding one is itself a finding to fix.
3. **Assign a build tier by longest-path depth.** A story's tier equals the length
   of the **longest** dependency chain leading to it. Tier 0 means no dependencies;
   a story sits one tier below its deepest dependency. This is the topological-sort
   / CPM step.
4. **Ties share a tier.** Stories at the same depth with no dependency between them
   (for example, 2.0 and 2.1) are **independent siblings**: they share a tier and
   there is no meaningful order between them. Left-to-right order within a tier is
   not significant.
5. **Dependency depth is the only ordering factor.** Story number, phase, business
   priority, and delivery speed (velocity) are **not** used to order the table.
   Phase and track (pipeline vs. the Floor & Harvest A/B/C transition work) are
   shown as labels only; they do not change a story's position.

## 4. The one secondary factor (and where it does NOT apply)

When choosing which story to **recommend working next** among the stories that are
currently unblocked (all dependencies done), a secondary heuristic is used:
prefer the **critical path** (the longest dependency chain, since any delay there
delays the whole project) and **foundation-hardening** value (protect the
load-bearing pieces before work lands on top of them).

This heuristic affects only the **"what to work next" recommendation**. It does
**not** affect how the table itself is ordered. The table is a pure topological
sort by dependency depth; the recommendation heuristic is a separate, human-facing
prioritization used inside a tier or among equally-eligible stories.

## 5. Summary statement (for reference)

> The build-order table is arranged by **Dependency-Driven Sequencing**, implemented
> as a **topological sort** with positions expressed as **build tiers** (tier =
> longest-dependency-path depth). The input is each story's declared `Depends on`;
> the graph is a DAG; ties share a tier as independent siblings; dependency depth is
> the sole ordering factor. Formally this is a topological ordering of a DAG (Kahn,
> 1962), whose project-management equivalent is the Critical Path Method (about
> 1957). The reason we order this way is the Foundation-First / Component-Driven
> philosophy recorded in [`../../METHODOLOGY.md`](../../METHODOLOGY.md) section 1a.
