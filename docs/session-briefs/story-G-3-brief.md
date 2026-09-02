# Session Brief — Story G-3

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.

---

## Story G-3 — Hard-pause enforcement: make un-validated work impossible to lose track of

| Field | Value |
|-------|-------|
| **Phase** | Cross-cutting / Governance |
| **Date** | TBD (next session) |
| **Status** | ⬜ Not Started |
| **Builds from restore point** | `restore/story-2.1-green` |
| **Session goal** | Turn the "hard pause" from a verbal, in-the-moment agreement into a **structural, machine-checkable mechanism**: a Validation Debt register, an advancement gate that blocks new feature work while debt is open, and an explicit decoupling of *story closure* from *restore-point work* — so an un-validated story (e.g. 2.0) can never silently slip through the cracks. |

---

### Background & Context

ZTIE tracks work as validation-gated stories: nothing is ✅ until a recorded live
pass (the covenant). Phase 1 is ✅; Phase 2 is mid-flight — **2.1 is ✅ (validated
live 2026-09-01)**, **2.0 is 🟡 (built, deployed once, never live-validated)**. The
stakeholder identified a recurring failure mode from prior efforts: a story left in
🟡 "to validate later" quietly becomes permanent debt and the effort rots around it.
The stakeholder and the executor agreed a division of labor: **the executor OWNS
calling hard pauses** (surfacing when we must stop to validate/back up/consolidate);
the **stakeholder retains final say** to accept, defer, or override. A hard pause is
only real if it survives across sessions and cannot be bypassed by forgetting — so it
must be **encoded**, not merely spoken. This story encodes it.

### Objective & Value

- **Objective:** add three enforcement artifacts to the governance layer — (1) a
  **Validation Debt register** in the RUNBOOK listing every built-but-not-live-
  validated story and the single action to clear it; (2) a **hard advancement gate**
  rule: no new *feature* story starts while the register is non-empty; (3) an explicit
  statement that **story closure depends only on that story's own validation** and is
  **decoupled** from restore-point/capture work — and wire these into the automated
  consistency checker (G-2's `scripts/check_docs.py`) so they are machine-enforced.
- **Why it matters:** it converts "we agreed to pause" into "the ledger will not let
  us advance past un-validated work." It directly kills the stakeholder's stated
  fear (validation slipping through the cracks) and makes the covenant self-policing.

### Scope, Dependencies & Position

- **In scope:** a **Validation Debt register** section at the top of `RUNBOOK.md`
  (seeded with its one current entry: **2.0 → run the 7 DoD checks**); a **hard
  advancement-gate** clause added to the RUNBOOK's Validation & Advancement Gate and
  METHODOLOGY (§4); a short **"story closure ≠ restore-point work"** statement in
  METHODOLOGY + the Floor & Harvest Plan; and extending the (planned) G-2
  `scripts/check_docs.py` remit — or, if G-2 is not yet built, specifying the exact
  checks G-3 requires so G-2 implements them: **fail if any 🟡 story is absent from
  the Validation Debt register**, and **fail if a new feature story is marked started
  while the register is non-empty**.
- **Out of scope:** validating 2.0 itself (that is its own story/action — G-3 only
  makes 2.0's open state impossible to ignore); building the parameterized archive;
  any Phase-2 feature work. G-3 changes governance + a checker, not pipeline code.
- **Depends on:** none hard-blocking (docs/tooling). Coordinates with **G-2**
  (the consistency checker) — if G-2 exists, extend it; if not, G-3 specifies the
  checks and G-2 implements them. Should build from `restore/story-2.1-green`.
- **Unblocks:** trustworthy advancement for the whole rest of the plan — every future
  phase inherits the debt register + gate.
- **Roadmap position:** cross-cutting governance; slots alongside G-1/G-2. Best done
  now, while the hard-pause need is concrete and there is exactly one debt item to
  seed the register with.

### Approach & Constraints

- **Approach:** (1) add the Validation Debt register to `RUNBOOK.md` (table:
  story · why-not-done · single action to clear · owner); seed it with **2.0**.
  (2) Add the advancement-gate clause (no new feature story while debt non-empty) to
  the RUNBOOK gate + METHODOLOGY §4. (3) Add the story-closure-vs-restore-points
  decoupling statement. (4) Specify/implement the two automated checks in
  `scripts/check_docs.py`. (5) Keep PROJECT_PLAN ↔ RUNBOOK aligned.
- **Hard constraints:** Python-first for any tooling (project standard). Docs are
  first-class (RD-015): PR-reviewed, never straight to main. **Do not** flip 2.0 or
  any story status — G-3 only records/enforces state, it never validates on inference.
  The executor owns *proposing* the pause; the stakeholder owns the *decision*.
- **Checker path taken (recorded per the prompt):** the minimal checker was
  **IMPLEMENTED HERE in `scripts/check_docs.py`** (Python 3.12, stdlib only,
  `unittest`-tested) rather than deferred to G-2. It therefore **partially fulfills
  and overlaps G-2's `check_docs.py` remit** (RD-015 management-artifact integrity):
  G-2, when picked up, extends this same checker instead of starting fresh.

### Validation Rationale & Compliance Mapping (REQUIRED — RD-014)

- **Rationale:** G-3 strengthens the project's assurance posture by making
  incomplete-validation *visible and blocking* rather than silent — a process control
  against shipping/advancing on unverified work.
- **Candidate control mappings** *(proposed; ratified on review):*

| Framework | Control ID | Control Name | Rationale | Status |
|-----------|-----------|--------------|-----------|--------|
| NIST 800-53 r5 | CA-2 | Control Assessments | Enforces that a component is not treated as complete until its validation is recorded | Proposed |
| NIST 800-53 r5 | CM-3 | Configuration Change Control | Advancement gate blocks new change while validation debt is open | Proposed |
| NIST 800-53 r5 | CA-5 | Plan of Action & Milestones | The Validation Debt register is a live POA&M of un-validated items + the action to clear each | Proposed |
| NIST CSF | ID.GV-3 / PR.IP-3 | Governance / change-control process | Codifies the pause + gate as a repeatable governance process | Proposed |
| ISO 27001:2022 | A.5.36 | Compliance with policies/standards for information security | Machine check enforces adherence to the validation covenant | Proposed |
| ISO 27001:2022 | A.8.32 | Change management | New work is gated behind cleared validation debt | Proposed |

- **Audit evidence produced:** the Validation Debt register (a standing POA&M), the
  gate clause in RUNBOOK/METHODOLOGY, and a `check_docs.py` run that fails on
  un-registered 🟡 or on advancement-with-open-debt.

### Management-Artifact Obligations (REQUIRED — RD-015)

- [ ] Story's **brief + runbook entry** updated (G-3 row added; register seeded).
- [ ] **PROJECT_PLAN and RUNBOOK in exact alignment** (G-3 appears in both; gate
      clause consistent).
- [ ] Any **new/changed registered decisions** recorded — G-3 introduces the
      hard-pause/advancement-gate discipline; record it (candidate RD, e.g. RD-023)
      and add candidate control mappings (RD-014).
- [ ] All doc changes **PR-reviewed** (branch + PR, never straight to main).
- [ ] Governance kept **restorable** alongside the code (register + gate are part of
      the pinned governance-doc commit).

### Change & Rollback

- **Change type:** standard (docs + a checker rule; no runtime/infra change).
- **Restore point this builds from:** `restore/story-2.1-green`.
- **Backout plan:** revert the docs/tooling PR; no deployed state involved.

### Definition of Done / Validation Gate

- **Done means:** (1) the **Validation Debt register** exists in `RUNBOOK.md`, seeded
  with the current debt (**2.0 → run its 7 DoD checks**); (2) the **advancement-gate
  clause** (no new feature story while the register is non-empty) is in the RUNBOOK
  gate + METHODOLOGY; (3) the **story-closure ≠ restore-point-work** decoupling is
  stated in METHODOLOGY + the Floor & Harvest Plan; (4) `scripts/check_docs.py`
  **fails** on an injected un-registered 🟡 story AND on an injected "new feature
  story started while debt open," and **passes** on the clean tree; PROJECT_PLAN ↔
  RUNBOOK aligned.
- **Validated by:** the user (runs `check_docs.py` on a clean tree → pass, then on
  each injected defect → fail), or reviews the docs if the checker is deferred to G-2.
- **Validation Result:** `pending`.
- **On pass (and only then):** record the Validation Result + set the RUNBOOK row ✅.
- **On fail:** stays 🟡; re-focus on fixing G-3 before advancing.
- **Advancement gate:** none blocks G-3 from starting; once ✅, the gate it installs
  governs all subsequent feature stories.

### Risks & Watch-Items

- **Do not let G-3 become a way to "resolve" 2.0 on paper.** G-3 records and blocks;
  it must never flip 2.0 to ✅. The register entry is cleared only by 2.0's real
  validation. (This is the exact drift the covenant forbids.)
- **Checker false-positives:** the "🟡 must be in the register" rule must tolerate a
  story that is legitimately mid-build in the current session; scope the check to
  committed state, and treat ⛔ the same as 🟡 for register purposes.
- **G-2 ordering:** if G-2 (`check_docs.py`) is not yet built, G-3 must not silently
  assume it — either implement the minimal checker here or clearly hand the two checks
  to G-2 as a spec, and record which was done.

### Lessons Learned / Carry-Forward *(from the session that authored this)*

- **What prompted this:** during the post-2.1 governance/reorg work the stakeholder
  flagged that un-validated stories (2.0) risk slipping through the cracks — a
  failure mode seen in prior efforts. Agreement reached: the **executor owns calling
  hard pauses; the stakeholder owns the decision**. A verbal pause is not enough — it
  must be encoded. Hence G-3.
- **Current true state (2026-09-01):** on `main` — 2.1 ✅ (validated live), **2.0 🟡
  (never live-validated — the one open floor item)**, restore tags
  `restore/phase-1-green` + `restore/story-2.1-green` exist, deployed-state restore
  capture NOT yet done (BOM has 11 `pending` rows; `feature/restore-targets-phase2`
  built but unmerged). Plan of record: `docs/governance/FLOOR_AND_HARVEST_PLAN.md`.
- **Must-know / must-avoid:** G-3 is governance/tooling only — it does not validate
  2.0, build the archive, or touch pipeline code. It makes the *pause* real; it does
  not *clear* the debt. Keep docs PR-reviewed (RD-015). Python-first for the checker.
- **User notes:** the stakeholder will follow the executor's lead on *when* to call a
  hard pause and on *whether* to invoke this gate at a given moment; G-3 provides the
  mechanism, not the schedule.
