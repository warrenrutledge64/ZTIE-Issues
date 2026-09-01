# ZTIE-Issues

> **You just created a new effort from the `project-os-starter` template.**
> This repo comes pre-wired with a disciplined way of working: one story at a
> time, nothing "done" on inference, validation results that drive status and gate
> advancement, restore-point discipline, and warm session-to-session handoffs.
> The full rationale is in [`METHODOLOGY.md`](METHODOLOGY.md) — **read that first.**

## Day 0 — bootstrap this effort (do these 6 steps)

1. **Rename.** Replace every `{{PROJECT_NAME}}` placeholder (this file,
   `PROJECT_PLAN.md`, `RUNBOOK.md`, `BOM.md`, `RESTORE.md`) with your effort's name.
2. **Fill [`PROJECT_PLAN.md`](PROJECT_PLAN.md)** — project identity, non-negotiable
   constraints, phases, the ordered story list, registered decisions, and the
   Universal Acceptance Criteria.
3. **Seed [`RUNBOOK.md`](RUNBOOK.md)** from the plan — one row per story,
   dependencies set, all ⬜. **Keep the Validation & Advancement Gate and the Story
   Close-Out Procedure sections verbatim** — they are the engine.
4. **Adjust [`RESTORE.md`](RESTORE.md) + [`BOM.md`](BOM.md)** to your technology —
   define what a "state manifest" means for this effort and what goes in the
   inventory.
5. **Protect `main`** — change-by-review only (PR required, no direct/force push).
   This is what makes the restore-point history trustworthy. *(On a free private
   repo GitHub will not enforce this; then PR-only is self-enforced by convention.)*
6. **Run Story 1** using the session ritual (see `METHODOLOGY.md` §5): fill its
   brief + prompt from [`docs/`](docs/), execute to a validated pass, then author
   the next story's handoff before wrapping.

## What's in this repo

| Path | Role |
|------|------|
| [`METHODOLOGY.md`](METHODOLOGY.md) | The **why & how** — principles, roles, the binding gate, the session ritual, restore-point discipline. Read first. |
| [`PROJECT_PLAN.md`](PROJECT_PLAN.md) | The *what/why*: scope, phases, decisions, acceptance criteria. |
| [`RUNBOOK.md`](RUNBOOK.md) | The *do-it-and-track-it* ledger — **source of truth for status** — with the **Validation & Advancement Gate** and the **Story Close-Out Procedure** baked in. |
| [`BOM.md`](BOM.md) | Inventory (Bill of Materials): everything produced/deployed, each tied to a restore point. |
| [`RESTORE.md`](RESTORE.md) | Restore-point procedure: tagging convention, state capture, coordinated revert. |
| [`docs/SESSION_BRIEF_TEMPLATE.md`](docs/SESSION_BRIEF_TEMPLATE.md) | Human-facing per-story spec (doubles as the change record). |
| [`docs/SESSION_PROMPT_TEMPLATE.md`](docs/SESSION_PROMPT_TEMPLATE.md) | Executor-facing per-story kickoff prompt, generated from the brief. |
| [`docs/session-briefs/`](docs/session-briefs/) | The filled-in briefs + prompts, one per story, as the effort runs. |

## The one rule to internalize

**"Done" means validated, not merged.** A story moves to ✅ only when a live check
passes and that result is recorded in `RUNBOOK.md` (see the Story Close-Out
Procedure). Merging code does not make a story done. That single discipline is what
keeps status honest and the restore-point history trustworthy.
