# Session Brief — Story G-3 (CLOSE)

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for **closing** Story G-3.
>
> **This is a CLOSE brief, not a build brief.** The original authoring brief
> ([`story-G-3-brief.md`](story-G-3-brief.md)) is kept verbatim as history (it
> predates the build). G-3 was BUILT long ago and has been actively enforcing the
> advancement gate ever since; this session only records its overdue **validation
> close** (flip 🟡 → ✅). Do not re-litigate or rebuild it.

---

## Story G-3 — Hard-pause enforcement (RD-023) — CLOSE

| Field | Value |
|-------|-------|
| **Phase** | Cross-cutting / Governance (`gov` track, build tier 0, not phase-bound) |
| **Track / gate role** | Governance. G-3 is EXEMPT from `check_docs` CHECK A/B/C register+gate logic (IDs starting `G-` are exempt), so it is NOT in the Validation Debt Register and closing it does not touch the register. |
| **Date** | TBD (this session) |
| **Status** | 🟡 In Progress — **built and in continuous use; never formally validation-closed.** This is the one story whose status is out of step with reality. |
| **Session goal** | Record G-3's validation and flip it 🟡 → ✅. Its Definition of Done is met offline: the three enforcement artifacts exist and `scripts/check_docs.py` + `scripts/test_check_docs.py` demonstrably enforce the rules. NO AWS / CloudShell needed. |

---

### Why this is the right next move

The advancement gate G-3 installs has correctly governed every feature story since
(it gated 3.1 and 3.2, armed/disarmed the Validation Debt Register on each, and was
extended with CHECK C in the build-order fix). Yet G-3 itself sits 🟡 — the machinery
that enforces the covenant has never been through the covenant's own close. That is
the single genuine status inconsistency on the board, and it is a **near-free green**:
G-3's validation is entirely offline (run the checker + its unittest suite), so there
is no live-validation round-trip. Closing it removes the inconsistency and makes the
gate itself validated.

### What "closing G-3" concretely requires (all already TRUE on `main` — verify, do not build)

G-3's Definition of Done (from its authoring brief + STORY_DETAIL) is four things.
Confirm each on current `main`; none should require new work:

1. **Validation Debt Register exists** in `RUNBOOK.md` (the machine-parsed table +
   status line). ✔ present.
2. **Advancement-gate clause** ("no new feature story while the register is
   non-empty") is in the RUNBOOK gate section + `METHODOLOGY.md` §4. ✔ present.
3. **Story-closure ≠ restore-point-work decoupling** stated in `METHODOLOGY.md`
   (§ "Story closure is decoupled from restore-point work"). ✔ present.
4. **`scripts/check_docs.py` enforces the checks:** FAILS on an injected
   un-registered 🟡 (CHECK A), FAILS on a new feature story started while debt is
   open (CHECK B), PASSES on a clean tree — and (added since) enforces build-tier
   order (CHECK C). ✔ implemented + unittest-covered.

The **recorded validation** is: `python3 scripts/check_docs.py` PASSES on the clean
tree (exit 0) AND `python3 -m unittest scripts.test_check_docs` reports the SUITE line
`OK` — the suite mutates copies to prove CHECK A/B/C each FIRE (those in-suite
`check_docs: FAIL …` prints are the checker exercising itself, not real failures).
That suite pass IS G-3's recorded pass: it demonstrates the gate fails-closed on the
exact defects the DoD names.

### Scope, Dependencies & Position

- **In scope:** verify the four DoD artifacts on `main`; run the checker + suite as
  the recorded validation; record a dated Validation Result in `RUNBOOK.md` master
  table (G-3 row 🟡 → ✅) + `docs/STORY_DETAIL.md` (G-3 section); confirm PROJECT_PLAN
  ↔ RUNBOOK alignment; author the next handoff.
- **Out of scope / do NOT do:** do NOT rebuild or "improve" the checker; do NOT touch
  pipeline/infra/lambda code; do NOT flip or alter any OTHER story's status; do NOT
  add G-3 to the Validation Debt Register (it is a `G-` governance story, exempt) and
  do NOT touch the `_NEW_WORK_STORY` fixture pin (that tracks the next ⬜ *pipe*
  story, unrelated to a governance close).
- **Depends on:** nothing hard-blocking. G-3 is tier 0. (It does not wait on the
  register being empty — governance stories are exempt from the gate.)
- **Unblocks:** nothing structurally (its enforcement is already live); closing it
  simply makes the board honest — the gate itself is now validated.

### Validation Rationale & Compliance Mapping (REQUIRED — RD-014)

- **Rationale:** recording G-3's close makes the assurance control (the advancement
  gate) itself validated and auditable — the enforcement mechanism is no longer an
  un-closed item.
- **Candidate control mappings** *(carried from the authoring brief; proposed):*
  NIST 800-53 r5 **CA-2** (Control Assessments), **CM-3** (Config Change Control),
  **CA-5** (POA&M — the Validation Debt Register is a live POA&M); NIST CSF
  **ID.GV-3 / PR.IP-3**; ISO 27001:2022 **A.5.36**, **A.8.32**. (All Proposed.)

### Management-Artifact Obligations (REQUIRED — RD-015)

- [ ] G-3 master-table row flipped 🟡 → ✅ with a `Completed` date.
- [ ] Dated Validation Result recorded in `docs/STORY_DETAIL.md` (G-3 section).
- [ ] PROJECT_PLAN ↔ RUNBOOK consistent (RD-023 already registered; no plan drift).
- [ ] `python3 scripts/check_docs.py` PASS + `python3 -m unittest
      scripts.test_check_docs` SUITE `OK` — run AFTER committing the status edit
      (CHECK B baseline is `git show HEAD:RUNBOOK.md`).
- [ ] All changes PR-reviewed (branch + PR, never straight to main).
- [ ] Author the next-story handoff (the next Ready item — C.3 or 3.2 per the
      RUNBOOK "Scheduling & readiness" buckets) with this session's lessons.

### Definition of Done / Validation Gate

- **Done means:** the four DoD artifacts are confirmed present on `main`; the checker
  PASSES clean and its suite reports `OK` (proving CHECK A/B/C fire on injected
  defects); G-3 is flipped ✅ with a dated Validation Result; PLAN ↔ RUNBOOK aligned.
- **Validation Result:** `pending`.
- **On pass (and only then):** flip G-3 ✅ (paired commit), record the dated result.
- **On fail:** if any DoD artifact is somehow missing/broken, G-3 stays 🟡 — fix the
  gap (that is real G-3 work), then re-validate. Do not close on inference.

### Risks & Watch-Items

- **Governance-story exemption (the key nuance):** G-3 is a `G-` story. `check_docs`
  CHECK A/B exempt `G-` IDs, so G-3 is legitimately NOT in the Validation Debt
  Register even while 🟡, and flipping it ✅ neither clears a register entry nor
  arms/disarms the gate. Closing it will not change `check_docs`'s output (it PASSES
  before and after). That is expected — do not go looking for a register row to clear.
- **Do not conflate with G-2.** The checker overlaps G-2's remit (RD-015) but G-2 is
  its own ⬜ story; closing G-3 does not close G-2. Leave G-2 ⬜.
- **check_docs timing:** run the checker only AFTER committing the status edit
  (CHECK B reads the committed HEAD as its baseline).
- **Do not touch `_NEW_WORK_STORY`.** It is pinned to the next ⬜ *pipe* story (3.2);
  a governance close does not move it.

### Lessons Learned / Carry-Forward *(from the sessions since G-3 was built)*

- G-3's checker has been extended twice since it was built: it now surfaces the
  **Operational Debt register** (OD-001/OD-002/OD-003, informational) and enforces
  **CHECK C** (build-tier monotonic order). All three checks + the OD surfacing are
  unittest-covered; the suite is currently **OK (7 tests)**.
- The gate has done its job for real: it stayed OPEN for 3.1 (register empty), ARMED
  while 3.1 sat 🟡 awaiting its live pass, and OPEN again once 3.1 flipped ✅. The
  close simply records what has been true in practice.
- Offline proof-bar note (INTEGRATIONS_ONLY sandbox): `ruff` at
  `~/.pyenv/versions/3.12.13/bin/ruff`. No AWS is involved in a G-3 close.

> **Sequencing note:** G-3-close is the highest-value Ready item — a near-free green
> that retires the one board inconsistency (the gate itself un-validated). After it,
> the next Ready work per the RUNBOOK "Scheduling & readiness" buckets is **C.3**
> (shared `awsio`/generator seam — pays down the 6×-copied tax) or **3.2** (next pipe
> feature).
