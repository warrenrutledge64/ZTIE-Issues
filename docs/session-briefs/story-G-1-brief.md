# Session Brief — Story G-1

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.

---

## Story G-1 — Compliance back-mapping (RD-014): finish + ratify the control-traceability matrix

| Field | Value |
|-------|-------|
| **Phase** | Cross-cutting / Governance (`gov` track, build tier 0, not phase-bound) |
| **Track / gate role** | Governance. G-1 is EXEMPT from `check_docs` CHECK A/B/C register+gate logic (IDs starting `G-` are exempt); closing it does not touch the Validation Debt Register or the `_NEW_WORK_STORY` fixture pin. |
| **Date** | TBD (first OPEN "Ready now" item after G-2 closed 2026-09-12; low-urgency) |
| **Status** | ⬜ Not Started |
| **Session goal** | COMPLETE the compliance control-traceability matrix in `docs/COMPLIANCE.md` for the artifacts not yet mapped, and drive candidate mappings toward ratification — so ZTIE's audit story (NIST 800-53 r5 / CSF / RMF + ISO 27001:2022 Annex A) is provable, not asserted. |

---

### ⚠️ Scope is FINISH + RATIFY — do NOT rebuild

`docs/COMPLIANCE.md` **already exists** with the framework scope, the
candidate-vs-ratified convention, and seeded mappings (as of 2026-09-12: ~28 `Proposed`
+ 3 `Ratified` rows; mappings seeded for RD-001/009/012/013/014/016/021/025). Every RD
since RD-014 already proposes candidate mappings at authoring time. So G-1 is **finish +
ratify, NOT build-from-scratch.**

### Objective & Value

- **Objective:** extend the traceability matrix to cover the remaining design artifacts
  (the registered decisions not yet mapped — e.g. RD-002…RD-013 gaps, RD-015…RD-034 —
  the non-functional constraints, and each story), each row carrying a rationale and a
  `Proposed`/`Ratified` status; then have an accountable reviewer ratify (or correct)
  the candidates so ZTIE claims coverage ONLY for ratified mappings.
- **Why it matters:** RD-014 makes compliance mapping a standing auditability practice.
  A complete, honestly-labeled matrix is what an auditor reads; decorative or stale
  mappings (or overclaiming "ZTIE is compliant") are worse than none.

### Scope, Dependencies & Position

- **In scope:**
  - Back-map the remaining registered decisions, non-functional constraints, and stories
    to NIST SP 800-53 Rev 5 (catalog of record), NIST CSF, related NIST (RMF), and
    ISO/IEC 27001:2022 Annex A, in the existing `docs/COMPLIANCE.md` matrix shape.
  - Each row: the artifact, the candidate control(s), a one-line rationale, and
    Status=`Proposed` (or `Ratified` once an accountable party confirms). Use
    `unmapped` honestly where no real control matches — never fabricate coverage.
  - Drive ratification: the accountable reviewer flips `Proposed → Ratified` per
    reviewed artifact (may be done incrementally per artifact group).
- **Out of scope / do NOT do:** rebuild `docs/COMPLIANCE.md`; assert ZTIE "is
  compliant" (only ratified mappings may be claimed); change any story's status; touch
  the register or the `_NEW_WORK_STORY` pin; pipeline/infra/lambda code.
- **Depends on:** nothing hard-blocking (tier 0). Best executed once the Phase-3 design
  stabilizes (avoid mapping a moving target); its own RUNBOOK note says so.
- **Unblocks:** nothing structurally — it is a standing auditability practice.

### Validation Rationale & Compliance Mapping (REQUIRED — RD-014)

- **Rationale:** a complete, honestly-labeled control matrix is the audit artifact of
  record; ratification is the control that keeps it from overclaiming.
- **Candidate control mappings** *(proposed):* NIST 800-53 r5 **CA-2** (Control
  Assessments), **PM-9** (Risk Management Strategy), **PL-2** (System Security &
  Privacy Plans); NIST CSF **ID.GV** / **ID.RA**; ISO 27001:2022 **A.5.36**,
  **A.5.35**. (All Proposed — G-1 itself ratifies.)

### Management-Artifact Obligations (REQUIRED — RD-015)

- [ ] G-1 brief + runbook/STORY_DETAIL entry updated (status, Validation Result, dates).
- [ ] PROJECT_PLAN ↔ RUNBOOK aligned.
- [ ] Candidate mappings labeled `Proposed`; ratified ones dated + attributed.
- [ ] All changes PR-reviewed (branch + PR, never straight to main).
- [ ] `check_docs.py` PASS + `test_check_docs` SUITE `OK` after committing (G-1 adds
      no new checks, but the doc-integrity checks must stay green — no dangling RD refs,
      no broken links, no drifted glyphs).
- [ ] Author the next-story handoff with this session's lessons.

### Definition of Done / Validation Gate

- **Done means:** the traceability matrix covers the remaining artifacts with honest,
  rationale-bearing candidate mappings; an accountable reviewer has ratified (or
  corrected) them per artifact group; `check_docs.py` PASSES clean and the suite is
  `OK`; PLAN ↔ RUNBOOK aligned.
- **Validation Result:** `pending`.
- **On pass:** record the dated Validation Result + flip G-1 ✅ (may be validated
  incrementally per artifact group).
- **On fail:** stays ⬜/🟡; fix + re-validate.

### Risks & Watch-Items

- **Don't overclaim.** Candidate-until-ratified; ZTIE claims coverage only for ratified
  mappings. `unmapped` is a valid, honest outcome.
- **Governance-story exemption.** Flipping G-1 ✅ does not clear a register row or
  change CHECK A/B output (expected).
- **Keep the docs green.** The G-2 checker (CHECK A–J) now runs on every status change.
  Update the RUNBOOK master table ONLY for status; README / on-deck / BUILD_ORDER POINT
  to it (do not hand-copy status). Do not introduce a dangling `RD-0NN` reference in a
  living doc (CHECK E) or a broken link (CHECK I); if you cite a not-yet-defined RD,
  don't hard-code its bare id in a living doc.

### Lessons Learned / Carry-Forward *(from the G-2 session, 2026-09-12)*

- **`check_docs.py` is now the enforcement backstop for exactly this kind of work.** It
  extends CHECK A/B/C with CHECK D (plan↔runbook divergence), E (dangling `RD-0NN` refs
  in living docs), F (stray `{{placeholders}}`), G (undated ✅ pipe/gov story), H
  (living-doc glyph drift + on-deck-at-✅), I (dangling `*.md` links), and J (ADVISORY,
  non-blocking, sequence-adherence). Run `python3 scripts/check_docs.py` (expect PASS,
  exit 0) and `python3 -m unittest scripts.test_check_docs` (expect SUITE `OK`) AFTER
  committing any status edit — the in-suite `check_docs: FAIL …` prints are the checker
  exercising itself against fixtures, NOT real failures; read the SUITE `OK`/`FAILED`
  line.
- **CHECK E scopes "defined" to PROJECT_PLAN + the Floor & Harvest plan and scans refs
  over LIVING docs only.** If G-1 references an RD that is not yet in those docs, either
  define it there or don't name its bare id in a living doc.
- **Status de-dup is now enforced:** README's "Status at a glance" and BUILD_ORDER's
  "what this view says" carry a `<!-- BEGIN/END GENERATED: phase-status -->` region that
  CHECK H verifies against the RUNBOOK roll-up. If G-1 changes any phase's rollup (it
  won't — G-1 is `gov`), regenerate those blocks; otherwise leave them.
- **The offline proof-bar in this sandbox:** default `python3` is 3.9 and the checker +
  suite run under it (stdlib-only); `ruff` is at `~/.pyenv/versions/3.12.13/bin/ruff`
  (not on PATH). No AWS is needed for G-1 (pure docs).
- **Sequence discipline:** G-1 is the first OPEN "Ready now" item, but it is low-urgency;
  3.2 (pipe) is the higher-value default next action and is in a separate session. If the
  stakeholder prefers to reorder (e.g. T.1 before Phase 4, or straight to the pipe
  track), that is their call — record it in WORK_LOG before starting; CHECK J will note
  the on-deck/schedule mismatch as a non-blocking advisory.
