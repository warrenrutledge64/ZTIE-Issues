# Session Brief — Story C.3

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.

---

## Story C.3 — Shared Python seam + one parameterized generator

| Field | Value |
|-------|-------|
| **Phase** | Cross-cutting / Floor & Harvest (`F&H` track, build tier 6 — not phase-bound) |
| **Build tier** | 6 (depends on `A.4` ✅, tier 5). **No tier advance for the pipe line** — this is an F&H refactor riding on the already-open floor; it does not gate a phase transition. STEP 0 re-confirms `A.4` ✅ and an empty register. |
| **Date** | TBD (next session) |
| **Status** | ⬜ Not Started |
| **Depends on** | **A.4 ✅** (the deployed-state restore floor — so any redeploy that proves the refactor has a captured baseline to compare against). No pipe-story dependency. |
| **Builds from restore point** | Branch the CODE off current `main` (which contains G-3 ✅ closed 2026-09-12 + all of Phase 2 + 3.1 ✅). |
| **Session goal** | Pay down the single most-compounded piece of duplication in the repo: extract the copy-pasted `awsio` boto3 seam **and** the Hub-gate envelope-kind pattern into ONE importable shared module, and collapse the 10 bespoke contract generators into ONE parameterized generator whose output is **byte-identical** (hash-matched) to what each bespoke generator produces today. Behaviour-preserving refactor — **zero functional change**, proven by identical contract hashes + green offline proof bar. |

---

### Why this is the right next move

With **G-3 now closed ✅ (2026-09-12)** the one board inconsistency is retired and the
advancement gate itself is validated. The next highest-value *Ready* item per the
RUNBOOK "Scheduling & readiness" buckets is **C.3** — the one backlog item whose cost
**rises with every pipe story**. On current `main` the `awsio.py` seam has been
hand-copied **6×** (`lambdas/preprocessor`, `lambdas/static_scan`, `lambdas/detonation`,
`lambdas/collector`, `lambdas/hub_normalize`, `scripts/ztie_restore`) and there are **10
bespoke contract generators** (`scripts/gen_*.py`) that share one shape. 3.1 added the
6th hand-copy of the pattern. This is a **pure refactor**: it changes no behaviour, adds
no feature, and touches no verdict/boundary logic — it just collapses the tax so the next
pipe story (3.2 →) stops paying it.

> **Note on the two `C.3` scopes.** C.3's authored scope in the Floor & Harvest plan is
> the **Python** seam + generator collapse (this brief). It is DISTINCT from the CDK L3
> construct-library chain (B.1 → C.1 → C.2 → C.4 → C.5, which stands up
> `infra-building-blocks`). C.3 does NOT depend on that chain (its dependency is A.4
> only) and can land independently. Do not conflate the two — this session is Python
> code-hygiene, not the CDK archive.

### What This Story Is (nature + gate role)

**Nature: FLOOR & HARVEST refactor (not a new feature).** F&H stories are not blocked by
the advancement gate the way *pipe* features are, but STEP 0 must still confirm the
register is empty and A.4 is ✅. It produces no new pipeline capability; it reduces
duplication so every subsequent story is cheaper and less drift-prone.

### Objective & Value

- **Objective (two parts, both behaviour-preserving):**
  1. **Shared `awsio` seam + Hub-gate pattern.** Extract the duplicated boto3 seam and
     the Hub-gate envelope-kind dispatch/apply pattern into ONE importable module the
     Lambdas (and `scripts/ztie_restore`) import instead of each carrying a private copy.
     The per-Lambda thin wrappers stay legible; the shared logic lives in one place.
  2. **One parameterized generator.** Collapse the 10 `scripts/gen_*_contract.py`
     generators into ONE generator driven by per-contract parameters (name, version-pin
     env var, discriminator, field set), producing output that is **byte-for-byte
     identical** to today's per-generator output (verified by comparing the regenerated
     JSON Schemas' hashes against the committed ones — zero drift).
- **Why it matters:** the awsio/gate pattern is copied 6× and the generators 10×; each
  new pipe story re-copies it (a real, recurring tax + a drift risk — a fix to one copy
  silently misses the others). One seam + one generator makes the pattern
  edit-once/verify-once and removes an entire class of copy-drift bug.

### Scope, Dependencies & Position

- **In scope:** create the shared module(s) (location TBD — likely a small importable
  package under `lambdas/` shared or a `lib/`-style path the Lambda bundlers can include;
  decide + justify in the RD, respecting how each Lambda is packaged/bundled today);
  repoint each of the 6 `awsio.py` copies + the Hub-gate dispatch to the shared code
  while keeping each Lambda's public seam surface unchanged; build the ONE parameterized
  contract generator + a per-contract parameter table; **prove identical output** (regen
  every contract, diff/hash against the committed schemas — must match); keep/extend the
  contract-conformance tests; a new RD (the shared-seam/one-generator decision) +
  candidate control mappings (RD-014); the `restore/shared-seam-green` restore point.
- **Out of scope / do NOT touch:** any behaviour change to a Lambda handler; any
  verdict/boundary/contract SCHEMA change (the schemas' bytes must not move — this is a
  refactor of the *generator*, not the *contracts*); the CDK L3 archive chain
  (B.1→C.1→C.2→C.4→C.5); any pipe feature; any other story's status; the Validation Debt
  Register; the `_NEW_WORK_STORY` fixture pin (it tracks the next ⬜ *pipe* story, 3.2 —
  a C.3 refactor does not move it).
- **Depends on:** **A.4 ✅** + an empty register. **Unblocks:** nothing structurally; it
  lowers the recurring cost of every subsequent pipe story and removes copy-drift risk.
- **Roadmap position:** the highest-value F&H cleanup, pulled forward because its cost
  compounds; recommended before returning to the pipe track (3.2).

### Approach & Constraints

- **Expected true-state (STEP 0 re-confirms; trust `main` + `check_docs`):** G-3 ✅
  (closed 2026-09-12); A.4 ✅; Validation Debt Register EMPTY; `check_docs` PASS + suite
  `OK`. Next free RD number: re-verify with
  `grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md | sort -u | tail` (highest is RD-033; expect
  **RD-034**, but VERIFY — collisions have happened, and RD-017 is a historical gap).
- **Hard constraints:** **behaviour-preserving** — the refactor must change NO runtime
  behaviour and NO contract bytes. Prove it: (1) regenerate every contract with the new
  single generator and confirm each output hash equals the committed schema's hash (zero
  drift); (2) keep the two-layer contract-conformance tests green; (3) each Lambda's
  handler behaviour + its public `awsio` surface unchanged. Production code (no mocks per
  the production-code-at-all-times rule); PURE logic + thin seams; docs first-class
  (RD-015), PR-reviewed.
- **Packaging reality (watch this):** each Lambda bundles its own directory today — the
  shared module must be **reachable by every Lambda's bundler** (zip include path /
  bundling command) AND importable by `scripts/ztie_restore`. Decide the shared location
  against how the CDK stacks actually bundle each Lambda; a shared module that isn't in
  the deploy bundle will pass offline tests but fail at runtime with `ModuleNotFoundError`
  (a deploy-gap sibling). If a live redeploy is used to prove no-op, verify the LIVE
  Lambda imports the shared code.
- **Roles:** if a LIVE proof step is used (e.g. a "(no changes)"/no-op redeploy of one
  Lambda to prove the bundle still works) it is the **stakeholder's** action; the
  **executor RECORDS** it verbatim. Do NOT simulate.

### Validation Rationale & Compliance Mapping (REQUIRED — RD-014)

- **Rationale:** removing 6×/10× duplication removes a whole class of copy-drift defect
  (a fix applied to one copy silently missing the others) and makes the security-relevant
  seam (the Hub-gate envelope-kind apply) edit-once/audit-once — a maintainability control
  that directly protects the integrity of the contract boundary.
- **Candidate control mappings** *(proposed; ratified on review):*

| Framework | Control ID | Control Name | Rationale | Status |
|-----------|-----------|--------------|-----------|--------|
| NIST 800-53 r5 | SA-15 | Development Process, Standards, and Tools | Consolidates duplicated code into a maintained shared module | Proposed |
| NIST 800-53 r5 | CM-2 | Baseline Configuration | Single generator = one authoritative contract baseline (hash-matched) | Proposed |
| NIST CSF | PR.IP-2 | A System Development Life Cycle is implemented | Reduces drift risk across the pipeline codebase | Proposed |
| ISO 27001:2022 | A.8.32 | Change management | One seam/one generator makes changes verifiable and non-drifting | Proposed |

### Management-Artifact Obligations (REQUIRED — RD-015)

- [ ] Story's brief + runbook entry updated (status, Validation Result, dates).
- [ ] PROJECT_PLAN and RUNBOOK in exact alignment (C.3 identical in both).
- [ ] New RD (shared-seam + one-generator design) recorded; candidate mappings recorded.
- [ ] All doc changes PR-reviewed (branch + PR, never straight to main).
- [ ] Do NOT touch `_NEW_WORK_STORY` (it pins the next ⬜ *pipe* story, 3.2 — unrelated
      to an F&H refactor).
- [ ] Governance kept restorable alongside the code (`restore/shared-seam-green`).
- [ ] On validation pass: record Validation Result + flip ✅ (paired commit).
- [ ] Author the next-story handoff (the next Ready item — **3.2 Nova Pro correlation**,
      or B.1 if the stakeholder prioritizes the archive chain) with real Lessons Learned.

### Definition of Done / Validation Gate

> A pass/fail gate, not a description.

- **Done means:** ONE shared `awsio`+Hub-gate module is imported by all 6 former copies
  (+ `scripts/ztie_restore`) with each Lambda's public seam + behaviour unchanged; ONE
  parameterized generator replaces the 10 bespoke ones and regenerates **byte-identical**
  (hash-matched) contract schemas (zero drift proven); the offline proof bar is green
  (contract-conformance tests + `ruff` + `prettier` + `tsc` adds no new error type); if a
  live no-op redeploy is used to prove the bundle, it is recorded. No contract SCHEMA
  bytes moved; no behaviour changed.
- **Validation Result:** `pending`.
- **On pass (and only then):** record the dated Validation Result, flip C.3 ✅ (paired
  commit), keep PLAN ↔ RUNBOOK aligned, place `restore/shared-seam-green`.
- **On fail:** C.3 stays 🟡 (added to the Validation Debt Register in the same commit);
  fix + re-validate.

### Risks & Watch-Items

- **Behaviour drift is the whole risk.** A refactor that changes ONE contract byte or ONE
  handler behaviour has failed. Prove no-drift with contract hashes + green conformance
  tests before flipping ✅.
- **Bundling / import path (deploy-gap sibling).** The shared module must be in every
  Lambda's deploy bundle and importable by `scripts/ztie_restore`; a module that passes
  offline but isn't bundled fails at runtime with `ModuleNotFoundError`. Verify the LIVE
  Lambda import if a redeploy is used.
- **Don't conflate C.3 with the CDK archive chain.** This C.3 is the Python seam +
  generator collapse (dep A.4 only); it is NOT B.1→C.1→C.2→C.4→C.5.
- **Governance-story / F&H nuance:** C.3 is `F&H`, not a *pipe* feature — closing it does
  not move `_NEW_WORK_STORY` (pinned to 3.2). Leave that fixture alone.
- **RD number:** verify the next free RD before registering (expect RD-034 but confirm).

### Lessons Learned / Carry-Forward (from the G-3-close session, 2026-09-12)

- **Governance closes are recorded, never inferred, and are docs-only.** G-3 was
  built-not-closed; its close was a pure status flip + a dated Validation Result once the
  four DoD artifacts were confirmed on `main` and the offline proof (`check_docs` exit 0
  + `test_check_docs` SUITE `OK`) was recorded. C.3 is the inverse — real code, so it
  needs a real behaviour-preserving proof (hashes + green tests), not just a status flip.
- **`check_docs` timing (unchanged rule):** run `python3 scripts/check_docs.py` only
  AFTER committing any status/register edit (CHECK B's baseline is
  `git show HEAD:RUNBOOK.md`; running before the commit gives a false positive).
- **`test_check_docs` reading:** the SUITE result line (`OK` vs `FAILED (failures=N)`) is
  what matters; the in-suite `check_docs: FAIL …` prints are the checker exercising itself
  against fixtures — NOT real failures. The suite is currently **OK (8 tests)** (it grew
  from 7 as CHECK C landed — expect the count to keep pace with the checker; assert on
  `OK`, not on a fixed count).
- **F&H stories are exempt from the advancement gate the way `G-` stories are**, but STEP
  0 still confirms A.4 ✅ + an empty register on `main` before starting. Trust `main` +
  `check_docs` over any doc text; if they disagree, `main` wins.
- **Offline proof bar (INTEGRATIONS_ONLY sandbox):** `ruff` at
  `~/.pyenv/versions/3.12.13/bin/ruff`; `prettier`/`npx tsc` need `env -u NODE_OPTIONS`;
  `tsc --noEmit` legitimately shows ONLY the missing-`aws-cdk-lib` family
  (TS2304/2307/2339/2353/2591) — confirm NO NEW error type. jsonschema/moto/boto3 not
  installable — prove contracts with a stdlib conformance walk + a jsonschema-`skipUnless`
  layer, and stub boto3 in `sys.modules` for handler tests. Default `python3` is 3.9 and
  is fine for the stdlib checker/tests; the shared module + tests must stay stdlib-only /
  stubbed to pass offline.
- **User notes:** *(open for the stakeholder to add anything before the C.3 session.)*

> **Sequencing note:** C.3 (shared Python seam + one generator) is the highest-value
> *Ready* F&H item now that G-3 is closed — the one backlog item whose cost compounds
> with every pipe story. After it, the default next work is the pipe track (**3.2 — Nova
> Pro correlation**), unless the stakeholder pulls the CDK archive chain (B.1 →) forward.
