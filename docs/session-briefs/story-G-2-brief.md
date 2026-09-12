# Session Brief — Story G-2

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.

---

## Story G-2 — Management-artifact integrity (RD-015): finish + extend the checker, kill doc-drift

| Field | Value |
|-------|-------|
| **Phase** | Cross-cutting / Governance (`gov` track, build tier 0, not phase-bound) |
| **Track / gate role** | Governance. G-2 is EXEMPT from `check_docs` CHECK A/B/C register+gate logic (IDs starting `G-` are exempt); closing it does not touch the Validation Debt Register or the `_NEW_WORK_STORY` fixture pin. |
| **Date** | TBD (scheduled after C.3 in the OPEN queue) |
| **Status** | ⬜ Not Started |
| **Session goal** | Make RD-015 (management artifacts held to the same bar as code) machine-enforceable end-to-end: EXTEND the existing `scripts/check_docs.py` with the remaining integrity checks AND the doc-drift guardrails agreed from the 2026-09-12 audit, convert the duplicated status surfaces to pointers, and document the reusable-OS/instance boundary. |

---

### ⚠️ Scope is RE-BASED (read first)

When G-2 was first written, `scripts/check_docs.py` did not exist. **It exists now**
(built by G-3) and already enforces **CHECK A** (register completeness), **CHECK B**
(advancement gate), and **CHECK C** (schedule order: dependency precedence + deferred
rows last). So G-2 is **finish + extend, NOT build-from-scratch — do not rebuild the
checker.** The remaining scope folds in the doc-alignment guardrails from the
2026-09-12 repo-wide documentation audit.

**Why the audit matters to G-2:** the audit found that *every* stale doc was a
**duplicated status claim** (README's status tables, BUILD_ORDER's ✅/⬜ glyphs, the
on-deck pointer), while dated per-story artifacts never drifted. The lesson — and G-2's
mandate — is structural: **if a fact is not duplicated, it cannot go stale**, and what
must be duplicated should be machine-checked against the one source of truth (RUNBOOK).

### Objective & Value

- **Objective:** turn RD-015 from aspiration into enforcement — a clean tree passes
  `check_docs.py`, and it demonstrably FAILS on each injected integrity/drift defect,
  so management-artifact drift is caught mechanically rather than by eyeballing.
- **Why it matters:** the project's plan, runbook, and living docs are first-class
  deliverables (RD-015). This audit proved they drift in exactly one predictable way;
  G-2 installs the guardrail that stops it recurring for every future story.

### Scope, Dependencies & Position

- **In scope (extend `check_docs.py`; do NOT rebuild it):**
  - **(a) Integrity checks** (original G-2 scope): fail if PROJECT_PLAN↔RUNBOOK
    story-sets diverge per phase; a referenced `RD-0NN` is absent from the decisions
    table; stray `{{placeholders}}` remain outside the known template files; a ✅ story
    lacks a dated Validation Result line.
  - **(b1) De-duplicate status:** rework README "Status at a glance" / "Current focus"
    and `docs/BUILD_ORDER.md` per-story ✅/⬜ glyphs so they POINT to (or are generated
    from) the RUNBOOK master table rather than being a hand-kept copy.
  - **(b2) Doc-drift check:** fail when a living doc's embedded story-status glyph
    disagrees with the RUNBOOK master table, AND when the on-deck starter points at a
    story already ✅.
  - **(b3) Dangling-link check:** fail if any tracked `*.md` links to a repo-relative
    path that does not exist.
  - **(c) Reusable-OS / project-instance separation** documented so reusability is
    provable, not asserted.
  - **(d) Governance-doc commit pin** in the restore manifest (coordinate with 1.R).
  - **Close-out habit:** add one line to `docs/SESSION_PROMPT_TEMPLATE.md` — "if this
    story changed status, update RUNBOOK ONLY; confirm README/on-deck/BUILD_ORDER
    POINT (don't copy); `check_docs` will verify."
- **Out of scope / do NOT do:** rebuild CHECK A/B/C; change any story's status; touch
  the `_NEW_WORK_STORY` fixture pin; add G-2 to the Validation Debt Register (it is a
  `G-` story, exempt); pipeline/infra/lambda code.
- **Depends on:** nothing hard-blocking (tier 0). Scheduled after **C.3** in the OPEN
  queue (its cheap half — the extra checks + drift guardrails — pairs with the
  shared-seam cleanup). Overlaps **G-3** (which built the checker G-2 extends) and
  **1.R** (governance-doc commit pin).
- **Unblocks:** durable plan/doc alignment for the whole remaining runbook.

### Validation Rationale & Compliance Mapping (REQUIRED — RD-014)

- **Rationale:** machine-enforced management-artifact integrity is a process control
  against drift/misstatement in the plan of record.
- **Candidate control mappings** *(proposed):* NIST 800-53 r5 **CM-3** (Config Change
  Control), **SA-10** (Developer Configuration Management), **CA-7** (Continuous
  Monitoring — of the governance docs); NIST CSF **ID.GV-3 / PR.IP-3**; ISO 27001:2022
  **A.5.36**, **A.8.32**. (All Proposed.)

### Management-Artifact Obligations (REQUIRED — RD-015)

- [ ] G-2 brief + runbook/STORY_DETAIL entry updated (status, Validation Result, dates).
- [ ] PROJECT_PLAN ↔ RUNBOOK aligned.
- [ ] New/changed RDs recorded if the de-dup design warrants one; candidate mappings recorded.
- [ ] All changes PR-reviewed (branch + PR, never straight to main).
- [ ] `check_docs.py` PASS + `test_check_docs` SUITE `OK` after committing (new checks covered by self-tests that prove each FIRES on an injected defect).
- [ ] Author the next-story handoff with this session's lessons.

### Definition of Done / Validation Gate

- **Done means:** `check_docs.py` passes clean and FAILS on each injected defect
  (plan/runbook divergence; dangling RD ref; stray placeholder; ✅-without-validation
  line; a README/BUILD_ORDER glyph disagreeing with RUNBOOK; an on-deck pointer at a ✅
  story; a dangling `*.md` link); the status-duplication surfaces are converted to
  pointers; the reusable-OS/instance boundary doc is reviewed as accurate; PLAN ↔
  RUNBOOK aligned. Each new check has a self-test proving it fires.
- **Validation Result:** `pending`.
- **On pass:** record the dated Validation Result + flip G-2 ✅.
- **On fail:** stays ⬜/🟡; fix + re-validate.

### Risks & Watch-Items

- **Don't rebuild the checker.** Extend CHECK A/B/C's module; keep the stdlib-only,
  offline, Python-3.9-compatible constraints (the suite runs under the repo's default
  `python3`). Add self-tests in the same pattern (mutate a copy → assert the new check
  fires; read the SUITE result line, not the in-suite fixture-print lines).
- **De-dup carefully.** When converting README/BUILD_ORDER status to pointers, don't
  lose useful narrative — replace the *duplicated status table* with a link + optional
  generated snippet, not the whole section.
- **Governance-story exemption.** Flipping G-2 ✅ does not clear a register row or
  change CHECK A/B output (expected).

### Lessons Learned / Carry-Forward *(from the 2026-09-12 documentation audit)*

- The audit corrected README (status regions + restore table), the on-deck pointer
  (was pointing at completed 2.5), BUILD_ORDER glyphs + "right now" note, and the
  METHODOLOGY/SEQUENCING_METHOD "pure topological sort" framing (obsoleted by the
  PR #93 schedule model). All were **duplicated-status** drift — exactly what b1/b2
  prevent.
- It also had to **hand-verify no dangling links** before deleting spent one-shots
  (`story-2.2-completion-START-PROMPT.md`, `story-2.3-VALIDATION-STEPS.md`) — b3
  automates that.
- Frozen per-story briefs/PROMPTs/LIVE-RUNBOOKs and WORK_LOG are dated snapshots and
  must NOT be "corrected"; b2's glyph check must scope to LIVING docs (README,
  BUILD_ORDER, on-deck), not the frozen artifacts.
- `check_docs.py` CHECK C is now dependency-precedence + deferred-last (NOT
  tier-monotonic) — any new check must not reintroduce a tier-monotonic assumption.

> **Sequencing note:** G-2 sits in the OPEN queue after C.3. Its cheap, high-value half
> (the extra integrity checks + the b1/b2/b3 drift guardrails) is the part worth doing
> promptly — it protects every subsequent story's docs; the reusable-OS/instance doc
> (c) is lower-urgency and can trail.
