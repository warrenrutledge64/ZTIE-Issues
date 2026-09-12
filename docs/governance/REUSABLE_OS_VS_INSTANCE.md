# Reusable OS layer vs. ZTIE project-instance layer (RD-015(d))

> **Why this doc exists.** RD-015 holds the management artifacts to the same bar as
> code — *reusable, durable, repeatable* — and clause **(d)** requires them to be
> **separable into a reusable operating-system (OS) layer vs. a project-instance
> layer, so that reusability is PROVABLE, not merely asserted.** This document is that
> proof: it draws the boundary explicitly, classifies every management artifact on one
> side or the other, and gives the concrete procedure to lift the OS layer into a
> brand-new project. Story **G-2** owns this doc; [`../../METHODOLOGY.md`](../../METHODOLOGY.md)
> §8–§9 and [`../../PROJECT_PLAN.md`](../../PROJECT_PLAN.md) RD-015 are its parents.

---

## 1. The boundary in one sentence

The **OS layer** is everything that would be true of *any* project run this way — the
method, the templates, the enforcement gate, the restore discipline, and the checker
that polices them. The **instance layer** is everything that is true only of *ZTIE* —
its registered decisions, its AWS account IDs, its pipeline stories, its schemas and
Lambdas. **If you deleted the instance layer you would still have a working project
operating-system; if you deleted the OS layer you would have ZTIE's facts with no
machinery to run or protect them.**

---

## 2. Classification of every management artifact

Legend: **OS** = generic/reusable (ships in the template, project-agnostic);
**INSTANCE** = ZTIE-specific (filled in per project); **SPLIT** = one file that
carries both a reusable skeleton AND instance content (the skeleton is OS; the filled
body is instance).

| Artifact | Layer | What is reusable (OS) vs. ZTIE-specific (instance) |
|----------|-------|-----------------------------------------------------|
| `METHODOLOGY.md` | **OS** | The covenant, the story ritual, the two-role split, dependency-driven sequencing, restore-point discipline, the document set. Contains only generic method + `{{PROJECT_NAME}}` placeholders. |
| `docs/SESSION_BRIEF_TEMPLATE.md` | **OS** | Blank, placeholder-driven story-spec skeleton. |
| `docs/SESSION_PROMPT_TEMPLATE.md` | **OS** | Blank, placeholder-driven executor-prompt skeleton. |
| `docs/session-briefs/session-START-PROMPT.md` | **OS** | Generic session-open ritual prompt (placeholder-driven). |
| `scripts/check_docs.py` | **OS** | The enforcement gate. CHECK A/B/C (register + advancement gate + schedule order) and CHECK D–J (plan↔runbook divergence, dangling RD refs, stray placeholders, undated ✅, doc-drift, dangling links, sequence advisory) are all **generic** — they parse the *shape* of the ledger, not ZTIE facts. The only instance-shaped inputs are data constants (`LIVING_DOCS`, `TEMPLATE_FILES`, `DECISION_DEFINING_DOCS`), which are the reconfiguration surface (see §4). |
| `scripts/test_check_docs.py` | **OS** | Generic self-tests of the gate (mutate a copy → assert the check fires). |
| `RESTORE.md` | **SPLIT** | The tagging convention + capture/verify/restore *procedure* is OS; the ZTIE account IDs / stack names / manifest contents are instance. |
| `BOM.md` | **SPLIT** | The "if it's deployed, it's in the inventory; if it's in the inventory, it maps to a restore point" *discipline* is OS; the actual inventory rows + restore-tag index are instance. |
| `scripts/ztie_restore/` | **SPLIT** | The capture/verify/restore + `governance_commit` pin *mechanism* is OS-shaped (reusable pattern); the `targets.py` resource selectors are ZTIE-specific. |
| `README.md` | **SPLIT** | The "single pane of glass that POINTS to source docs" *structure* is OS; the ZTIE architecture, accounts, and links are instance. |
| `PROJECT_PLAN.md` | **INSTANCE** | ZTIE scope, phases, constraints, and the registered-decisions table (RD-001…). Only the Universal Acceptance Criteria are OS-reusable. |
| `RUNBOOK.md` | **INSTANCE** | The Validation & Advancement Gate *section text* is OS (copy it verbatim into a new project); every story row, register entry, phase, and schedule is instance. |
| `docs/BUILD_ORDER.md` | **INSTANCE** | ZTIE's dependency graph. (The "derived view, RUNBOOK is source of truth" convention is OS.) |
| `docs/ARCHITECTURE.md`, `docs/COMPLIANCE.md` | **INSTANCE** | ZTIE system narrative + ZTIE control mappings. |
| `docs/governance/OPERATING_MODEL.md` | **SPLIT** | The recommend/decide loop is OS; the ZTIE examples are instance. |
| `docs/governance/FLOOR_AND_HARVEST_PLAN.md`, `WORK_LOG.md`, `SEQUENCING_METHOD.md`, `COST_REMEDIATION_LEGACY_DECOMMISSION.md` | **INSTANCE** | ZTIE-specific tracks / logs / cost work. |
| `docs/session-briefs/*` (filled briefs + prompts) | **INSTANCE** | Per-ZTIE-story artifacts (frozen snapshots). |
| `CONVENTIONS.md` | **SPLIT** | Generic repo conventions are OS; ZTIE-specific paths/names are instance. |
| `lambdas/`, `infra/`, `schemas/`, contract generators | **INSTANCE** | ZTIE application/infrastructure/data-contract code. |

**Net:** the OS layer is a small, well-bounded set — the method (`METHODOLOGY.md`), the
three templates, the gate (`check_docs.py` + its tests), the *sections* of RUNBOOK that
are the engine (the Validation & Advancement Gate + Close-Out Procedure), and the
restore *discipline*. Everything else is instance.

---

## 3. What makes the separation PROVABLE (not asserted)

1. **The gate is generic by construction.** `check_docs.py` never hard-codes a ZTIE
   story ID, phase, RD number, or account. It parses the *structure* of the ledger
   (tables, columns, status glyphs, delimited generated regions). Its only
   project-specific inputs are the three data constants named in §2 — the intended
   reconfiguration surface.
2. **The instance layer names itself.** Every ZTIE-specific decision is a numbered
   `RD-0NN`; every ZTIE fact lives in `PROJECT_PLAN.md` / `RUNBOOK.md` / the schemas.
   The OS layer contains **zero** `RD-0NN` definitions and **zero** account IDs.
3. **The extraction test (§4) is repeatable.** You can lift the OS layer into an empty
   repo and it still runs (the templates fill, the gate passes on a seeded blank
   ledger) with no ZTIE content present — that is the operational proof of reusability.

---

## 4. How to lift the OS layer into a new project (the repeatable procedure)

This mirrors `METHODOLOGY.md` §9 and makes the reuse concrete:

1. **Copy the OS files** into the new repo: `METHODOLOGY.md`, the three templates,
   `scripts/check_docs.py` + `scripts/test_check_docs.py`, and the *Validation &
   Advancement Gate* + *Story Close-Out Procedure* sections of `RUNBOOK.md`.
2. **Reconfigure the gate's data constants** for the new project (only these change):
   - `LIVING_DOCS` — the new project's living, duplication-prone docs.
   - `TEMPLATE_FILES` — where live `{{placeholders}}` are intentional.
   - `DECISION_DEFINING_DOCS` — where the new project defines its registered decisions.
3. **Replace `{{PROJECT_NAME}}`** and the other placeholders throughout.
4. **Seed a blank `RUNBOOK.md`** (one ⬜ row per story, empty Validation Debt Register)
   and a `PROJECT_PLAN.md` (scope, phases, the new project's `RD-0NN` table).
5. **Run `python3 scripts/check_docs.py`** — it should PASS on the seeded blank ledger,
   proving the OS layer works before any instance content exists.

The instance layer (the new project's plan rows, decisions, schemas, and code) is then
authored per the story ritual — it is never copied from ZTIE.

---

## 5. Maintenance

- When a NEW management artifact is added, classify it here (OS / INSTANCE / SPLIT) as
  part of the story that adds it — same bar as code (RD-015(e)).
- If a generic capability is discovered inside an instance file (e.g. a reusable check
  buried in a ZTIE doc), migrate it to the OS layer and record the move, so the OS
  layer stays genuinely project-agnostic and the boundary stays honest.
