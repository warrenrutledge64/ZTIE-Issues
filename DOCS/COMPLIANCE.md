# ZTIE — Compliance Control Traceability Matrix

> The single auditable home for mapping ZTIE **design artifacts** (registered
> decisions, stories, non-functional constraints) to security-control frameworks.
> Governed by **RD-014** ([`../PROJECT_PLAN.md`](../PROJECT_PLAN.md) §5).
>
> **This is a living document and is currently a stub.** The full back-mapping of
> existing artifacts is tracked as its own validated story (see the runbook) and is
> best executed once the core pipeline design stabilizes. New artifacts propose
> their mappings at authoring time (see the brief template).

## Framework scope (for audit)

- **NIST SP 800-53 Rev 5** — the **control catalog of record** (control IDs like
  `AC-3`, `SI-10`, `SC-7`, `AU-2`).
- **NIST CSF** — framework-level mapping (Functions/Categories) where useful.
- **NIST family, related** — RMF (SP 800-37) context as relevant.
- **ISO/IEC 27001:2022 Annex A** — control IDs (e.g. `A.5.x`, `A.8.x`).

## Convention (candidate vs. ratified)

- Every mapping has a **Status**: `Proposed` (candidate, authored but not reviewed)
  or `Ratified` (reviewed + accepted by an accountable party).
- **ZTIE claims control coverage only for `Ratified` mappings.** `Proposed` mappings
  are working candidates, not compliance assertions.
- Mapping is an interpretive exercise; the **authoritative** mapping for an audit is
  the responsibility of an accountable compliance reviewer, not the authoring agent.

## Traceability matrix

> One row per (artifact, control) candidate. Populated incrementally; the dedicated
> back-mapping story fills the existing artifacts. Kept in sync with
> `PROJECT_PLAN.md` (decisions/constraints) and `RUNBOOK.md` (stories).

| Artifact | NIST 800-53 (Rev 5) | NIST CSF | ISO/IEC 27001:2022 Annex A | Rationale | Status |
|----------|---------------------|----------|-----------------------------|-----------|--------|
| _(pending — populated by the back-mapping story and by new artifacts at authoring time)_ | | | | | |

## Maintenance

- **New artifact →** propose its candidate mappings when it is authored (the brief
  template carries a candidate-mappings table; registered decisions and
  non-functional constraints add their rows here).
- **Review →** an accountable party ratifies (`Proposed` → `Ratified`) or corrects.
- **Change →** if an artifact changes materially, re-review its mappings (a stale
  mapping is worse than none).
- This matrix and the artifacts it references must stay in sync; the matrix is the
  consolidated view, the artifacts are the source.
