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

A story appears only after everything it depends on — **dependency precedence** is
the hard, non-negotiable rule (a story is never placed above one of its dependencies).
This is called **Dependency-Driven Sequencing**; the dependency graph is a DAG and
each story's **build tier = longest-dependency-path depth** (a topological sort).

Since 2026-09-12 the [`RUNBOOK.md`](../../RUNBOOK.md) master table is ordered as the
**true execution SCHEDULE**, not as a raw tier sort: DONE history → OPEN queue (in the
order we intend to work it) → DEFERRED at the bottom. Dependency precedence still holds
everywhere, but **within that constraint INDEPENDENT stories are ordered by priority**
(e.g. a tier-0 governance close or a tier-6 shared-seam may be scheduled before a
tier-9 pipe feature). So build tier is retained as **dependency metadata that
determines precedence**, but it is **not** the monotonic sort key of the table.

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
4. **Ties share a tier — and priority breaks the tie in the schedule.** Stories at
   the same depth with no dependency between them (for example, 2.0 and 2.1) are
   **independent siblings**. The tier math assigns them no order; the **schedule**
   then orders such independents (and, more broadly, any set of already-unblocked
   stories) by our chosen priority — provided precedence is never broken.
5. **Dependency precedence is the HARD constraint; priority orders the rest.**
   Story number, phase, and track (pipeline vs. governance `G` vs. Floor & Harvest
   `A`/`B`/`C` vs. tenancy `T`) never override precedence and are shown as labels.
   But among stories that precedence leaves free to move, the table reflects the
   order we actually intend to execute (see §4). The result is a
   **dependency-constrained schedule**, not a pure depth sort — enforced mechanically
   by [`../../scripts/check_docs.py`](../../scripts/check_docs.py) **CHECK C** (C1:
   every story after all its dependencies; C2: deferred rows last).

## 4. The one secondary factor (and where it does NOT apply)

When choosing which story to **recommend working next** among the stories that are
currently unblocked (all dependencies done), a secondary heuristic is used:
prefer the **critical path** (the longest dependency chain, since any delay there
delays the whole project) and **foundation-hardening** value (protect the
load-bearing pieces before work lands on top of them).

Since 2026-09-12 this prioritization is **reflected in the table's OPEN section
order itself** (the table is the schedule), not only in a separate recommendation:
the OPEN queue lists unblocked/soon-stories in the order we intend to do them, always
subject to the hard rule that a story never precedes one of its dependencies. The
critical-path / foundation-hardening heuristic is exactly how that priority is chosen.

## 4a. The mechanical guard (CHECK J) — and its blind spot

`scripts/check_docs.py` **CHECK J** is the *advisory* mechanical check that watches
sequence adherence. Know exactly what it does and does not do:

- **What it checks:** it compares the **on-deck starter** (the single "next session"
  pointer in [`../session-briefs/on-deck/README.md`](../session-briefs/on-deck/README.md))
  against the **first non-✅ row of the RUNBOOK "Ready now" (bucket A) table, read
  TOP-DOWN by ROW ORDER**. If they differ it prints a NON-BLOCKING advisory pointing here
  / to [`WORK_LOG.md`](WORK_LOG.md) to confirm an intended reorder. It never affects the
  exit code.
- **Blind spot 1 — it names only ONE row.** It reports only the *single* first-open
  bucket-A row (which, with the Floor-&-Harvest track open, is typically the lowest-tier
  `B.1`). It does not enumerate every out-of-tier Ready story.
- **Blind spot 2 — it reads ROW ORDER, not tier.** Bucket A is a hand-arranged table.
  CHECK J trusts that arrangement, so **an intra-phase / same-track tier inversion among
  independent Ready siblings is INVISIBLE to it** whenever the rows are ordered to match
  the executor's intent. Example that actually slipped through (2026-09-13): the Phase-4
  dashboard chain `4.3` (tier 15) was worked ahead of its Ready siblings `4.5/4.6/4.7`
  (tier 14); CHECK J only ever flagged the on-deck-vs-`B.1` mismatch, never the
  `4.3`-ahead-of-`4.5` inversion. See the retroactive reconciliation entry in
  [`WORK_LOG.md`](WORK_LOG.md) (2026-09-13).

**Consequence / the rule this makes explicit.** CHECK J is a helpful tripwire, **not** a
substitute for the sequencing discipline. Working a **higher-tier** Ready story ahead of a
**lower-tier independent Ready sibling** is permitted (§4: priority orders independents),
**but only as a priority decision recorded in [`WORK_LOG.md`](WORK_LOG.md) BEFORE starting**
— never as an executor "next" assertion, and never on the strength of CHECK J staying
silent. At each session's STEP 0, after reading the first-OPEN row, **also scan the OPEN
Ready set for any lower-tier sibling** you are about to skip; if you are, that skip needs a
recorded reorder. A dependency-precedence violation (a story above one of its own
dependencies) remains the HARD, blocking error (CHECK C); a tier inversion among
*independent* siblings is a *priority* choice that must be *recorded*, not silently taken.

## 5. Summary statement (for reference)

> The build-order table is arranged by **Dependency-Driven Sequencing**. Its
> foundation is a **topological sort** of the dependency DAG, with each story's
> **build tier = longest-dependency-path depth** (formally a topological ordering,
> Kahn 1962; project-management equivalent: the Critical Path Method, ~1957). The
> **hard invariant is dependency precedence** — a story never precedes one it depends
> on. On top of that, the table is presented as the **true execution schedule**
> (DONE history → OPEN queue → DEFERRED): independent/unblocked stories are ordered by
> priority (critical-path + foundation-hardening), so the `Build tier` column is
> dependency metadata, not the monotonic sort key. The schedule is enforced by
> `scripts/check_docs.py` CHECK C (precedence + deferred-last). The reason we order
> foundation-first is the Component-Driven philosophy in
> [`../../METHODOLOGY.md`](../../METHODOLOGY.md) section 1a.
