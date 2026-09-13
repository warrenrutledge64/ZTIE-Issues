# Session Brief — Story 3.5 (verdict derivation)

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.
>
> **Story 3.5 CLOSES Phase 3.** It is the FIRST story that produces a VERDICT
> (PASS / FAIL / INCONCLUSIVE). Everything before it (2.x lanes, 3.1 combined event,
> 3.2 correlation, 3.3 three scores, 3.4 findings + remediations) was deliberately
> EVIDENCE-ONLY. 3.5 is where the accumulated evidence becomes a decision — but the
> decision stays HUMAN-GATED: the derived verdict INFORMS the human accept/reject gate
> on the dashboard, it does not replace it.

---

## Story 3.5 — Verdict derivation (PASS / FAIL / INCONCLUSIVE)

| Field | Value |
|-------|-------|
| **Phase** | P3 — Correlation & Synthesis (this story CLOSES it) |
| **Build tier** | 12 — **advances tier 11 → 12** (a new dependency layer opens: `3.4` at tier 11 goes ✅). A TIER move WITHIN Phase 3 (no phase transition). STEP 0 must re-confirm the tier-≤11 dependency set (`3.4` + its inputs `3.3` + `3.2`) is ✅. |
| **Date** | TBD (next session) |
| **Status** | ⬜ Not Started (build tier 12 — but see the ADVANCEMENT GATE below). |
| **Depends on** | **3.4 ✅** (the `remediation_result` — detailed findings + prioritized remediations) which itself sits over 3.3's `scoring_result` (three 0-100 risk scores) + the 3.2 `correlation_result`. 3.5 reads the SCORES + FINDINGS to derive the verdict. |
| **Builds from restore point** | Branch the CODE off current `main` (which must contain merged + LIVE-VALIDATED 3.4 by the time 3.5 begins). |
| **Session goal** | For one `intake_id`, derive an ENFORCEMENT VERDICT (PASS / FAIL / INCONCLUSIVE) from the three risk scores + the findings/gaps, recorded on the Hub tracking item as a bounded, DERIVED verdict record. This verdict INFORMS the human accept/reject gate (Phase 4); it is the FIRST intentional verdict in the pipeline. |

---

### ⚠️ ADVANCEMENT GATE (read FIRST at STEP 0)

**3.5 is a NEW FEATURE story. It may begin ONLY if its Depends-on are ALL ✅ AND the
Validation Debt Register is EMPTY.** As of this brief's authoring, **Story 3.4 (RD-039)
sits 🟡 on the register awaiting its recorded LIVE pass** (see
`story-3.4-LIVE-RUNBOOK.md`). So the gate is expected ARMED until 3.4 is validated live.
STEP 0 MUST re-confirm on `main`: `3.4` ✅ and the register EMPTY (trust `main` +
`check_docs`; if they disagree, `main` wins). **If 3.4 is still 🟡, 3.5 MAY NOT begin —
the only permitted work is validating/reworking 3.4.** `check_docs` CHECK B, machine-enforced.

---

### Background & Context

Phase 3 turns paired static + dynamic evidence into a decision-ready assessment. 3.1
(RD-033) normalized the per-lane outputs into ONE `combined_event`; 3.2 (RD-035)
correlated it with Nova Pro into a verdict-free `correlation_result`; 3.3 (RD-038)
produced three independent 0-100 Nova Pro risk scores (`scoring_result`); 3.4 (RD-039)
built the detailed findings + prioritized remediations (`remediation_result`).
**Everything so far is EVIDENCE — there is deliberately NO verdict anywhere.** Story 3.5
is the verdict-derivation step: it turns the three scores + the findings/gaps into a
single PASS / FAIL / INCONCLUSIVE verdict that the Phase-4 dashboard surfaces and the
human accept/reject gate acts on.

### What This Story Is (nature + gate role)

**Nature: NEW FEATURE story — AND a boundary-shifting one.** It is the FIRST place a
verdict field legitimately EXISTS. Every prior derived record was verdict-free by
contract (recursive no-verdict scans enforced it). 3.5's contract is the ONE that
introduces the verdict vocabulary — so its design must be especially careful about WHAT
the verdict means and WHERE the human stays in control.

### Objective & Value

- **Objective:** for one `intake_id`, a bounded, DERIVED verdict record on the Hub
  tracking item carrying a `verdict` ∈ {PASS, FAIL, INCONCLUSIVE} + the rationale/basis
  (which scores + findings drove it) + the completeness caveats. Contract-first, own
  version pin, Hub-side.
- **Why it matters:** the verdict is the pipeline's enforcement signal — PASS routes an
  artifact toward the PDE (on human ACCEPT), FAIL blocks + routes failure telemetry back,
  INCONCLUSIVE holds at the manual approval gate. But 3.5 DERIVES a recommendation; the
  HUMAN makes the call on the dashboard (RD-003 + the human-gate covenant).

### Scope, Dependencies & Position

- **In scope:** the verdict-derivation logic; a contract-first verdict record (bounded,
  allow-list, own version pin); the mapping from scores + findings/gaps → PASS/FAIL/
  INCONCLUSIVE (thresholds/rules the stakeholder must confirm); the honest handling of
  PARTIAL evidence (a partial `scoring_result` should tend toward INCONCLUSIVE, not a
  fabricated PASS/FAIL); tests; a new RD + candidate control mappings (RD-014).
- **DECIDE + JUSTIFY (contract-first, in the new RD):** whether the verdict is
  DETERMINISTIC (a rules/threshold mapping over the three scores + gap severities — likely
  PURE, mirroring 3.4) or a Nova Pro call. **Strongly prefer PURE + deterministic** — a
  verdict must be reproducible, explainable, and auditable, and the inputs are already
  structured; a model deciding the verdict would undercut the "model characterizes,
  human/rules decide" line. If PURE, no Bedrock grant (like 3.4).
- **Out of scope / do NOT touch:** re-scoring / re-correlating / re-normalizing / rebuilding
  the findings (those are 3.3/3.2/3.1/3.4). The human accept/reject ACTION + the Phase-4
  routing (4.6/4.7) are downstream. The dashboard rendering is Phase 4.
- **Depends on:** **3.4 ✅**. **Unblocks:** 4.1 (status-retrieval orchestrator) + the whole
  of Phase 4. **This story CLOSES Phase 3.**

### Approach & Constraints

- **Hard constraints:** derive the verdict, do not re-score/re-correlate; keep the
  RD-009/RD-013 boundary intact (reason only over the derived Hub-side scores + findings,
  no raw data, no Forensic durable store); PURE logic + thin seams (strongly preferred); if
  it calls Nova Pro (discouraged), a REAL call with exponential-backoff retry (RD-003) +
  scoped Bedrock grant; docs first-class (RD-015), PR-reviewed.
- **The verdict is a RECOMMENDATION, the human decides.** The derived verdict record must
  be clearly framed as ZTIE's recommended verdict that INFORMS the human accept/reject gate
  — never an auto-enforced decision. This is the ONE contract that carries a verdict field;
  design its meaning + framing with the stakeholder.
- **Partial/absent evidence → INCONCLUSIVE, honestly.** Never fabricate a PASS or FAIL when
  the evidence is incomplete (a partial `scoring_result`, a `coverage` gap, `no_scores`).
- **Thresholds are a STAKEHOLDER decision.** The exact score/severity thresholds that map to
  PASS/FAIL/INCONCLUSIVE must be confirmed with the stakeholder + recorded in the RD (do not
  invent enforcement thresholds unilaterally).
- **Roles:** if a LIVE step is needed it is the **stakeholder's**; the executor RECORDS.

### Validation Rationale & Compliance Mapping (REQUIRED — RD-014)

- **Rationale:** a reproducible, explainable verdict derived from the three risk scores +
  findings makes the enforcement recommendation auditable while keeping the final decision
  human-gated.
- **Candidate control mappings** *(proposed; ratified on review):*

| Framework | Control ID | Control Name | Rationale | Status |
|-----------|-----------|--------------|-----------|--------|
| NIST 800-53 r5 | RA-3 | Risk Assessment | Verdict derived from risk scores | Proposed |
| NIST 800-53 r5 | CA-6 | Authorization | Human-gated accept/reject decision | Proposed |
| NIST 800-53 r5 | SI-4 | System Monitoring | Verdict over monitored evidence | Proposed |
| NIST 800-53 r5 | AC-4 | Information Flow Enforcement | PASS/FAIL gates flow to the PDE | Proposed |
| NIST CSF | ID.RA-6 | Risk responses identified + prioritized | Verdict drives the response | Proposed |
| ISO 27001:2022 | A.8.16 | Monitoring activities | Verdict over monitored evidence | Proposed |

### Management-Artifact Obligations (REQUIRED — RD-015)

- [ ] Story's brief + runbook entry updated (status, Validation Result, dates).
- [ ] PROJECT_PLAN and RUNBOOK in exact alignment (3.5 identical in both).
- [ ] New RD (verdict-derivation design + the stakeholder-confirmed thresholds) recorded; candidate mappings recorded.
- [ ] All doc changes PR-reviewed (branch + PR, never straight to main).
- [ ] `check_docs` fixture `_NEW_WORK_STORY` repointed off 3.5 (→ the next still-⬜ feature story, e.g. 4.1) IN THE SAME PR.
- [ ] On validation pass: record Validation Result + flip ✅ (paired commit).
- [ ] Author the next-story handoff (4.1 status-retrieval orchestrator) with real Lessons Learned.
- [ ] ⚠️ **Verdict-field note:** 3.5 is the FIRST contract to carry a verdict field. The existing recursive no-verdict scans + the `check_docs` expectations are built around verdict-free Phase-3 records. Confirm nothing (a test, a doc check) assumes NO record ever carries a verdict — 3.5 legitimately breaks that, in its OWN new contract only. The 3.1–3.4 records stay verdict-free.

### Definition of Done / Validation Gate

- **Done means:** for one `intake_id` with a `remediation_result` (and the `scoring_result`
  it sits over), 3.5 derives a bounded verdict record (PASS/FAIL/INCONCLUSIVE + basis)
  validated against its schema and recorded on the tracking item; partial evidence yields
  INCONCLUSIVE honestly; the verdict is framed as a human-gated recommendation; RD-009/RD-013
  intact; validated live (if it touches the running pipeline) and recorded.
- **Validation Result:** `pending`.
- **On pass:** record dated result, flip 3.5 ✅ (paired commit), clear the register, keep
  PLAN ↔ RUNBOOK aligned. **Phase 3 closes.**
- **On fail:** 3.5 stays 🟡 (added to the register in the same commit); fix + re-validate.

### Risks & Watch-Items

- **ADVANCEMENT GATE:** 3.4 must be ✅ (live-validated) first.
- **The verdict is human-gated** — 3.5 DERIVES a recommendation; the human accept/reject on
  the dashboard is the enforcing decision. Frame it that way in the contract + docs.
- **Prefer PURE + deterministic** — a verdict must be reproducible + explainable; the inputs
  are structured. Justify in the RD; avoid a model deciding the verdict.
- **Thresholds are the stakeholder's call** — confirm + record them; do not invent them.
- **First verdict-bearing contract** — mind the existing no-verdict scans (they protect the
  3.1–3.4 records; 3.5's own contract intentionally carries the verdict).
- **Deploy-gap** — redeploy `ZtieHubTrackingStack` from the RIGHT branch; verify the LIVE
  resource after.

### Lessons Learned / Carry-Forward (from the 3.4 build, 2026-09-13)

- **The PURE-derived pattern held again (9th time + the 3.3 rework):** 3.4 was built as a
  NEW `lambdas/hub_remediate/` Lambda — contract-first (`scripts/gen_remediation_contract.py`
  registered in `gen_contracts.py`, byte-identical `schemas/` + lambda copies), PURE logic
  (`remediate.py`) + a thin DynamoDB-only `awsio` seam (NO Bedrock — the inputs were already
  structured, so no model call), a handler on the tracking-table stream with a
  `Decimal`-canonicalized fingerprint guard (over the `scoring_result` score blocks + the
  correlation findings) so it assesses once per settled evidence, and a two-layer conformance
  test + recursive no-verdict scan + schema-has-no-verdict-property check. **3.5 should reuse
  this exact skeleton** — but its contract is the FIRST to intentionally carry a verdict, so
  the no-verdict scan/expectations apply to its INPUTS' handling, not its own output.
- **`remediation_result` shape 3.5 consumes** (RD-039, `remediation.contract.v1`): top-level
  `contract_version`/`intake_id`/`sha256`/`assessed_at`/`status`
  (`assessed`/`no_scores`/`skipped_no_evidence`) + optional `rubric_version`/
  `combined_complete`/`correlation_status`/`truncated` + (when `assessed`) an `assessment`
  with `summary`, `scores` (the three 3.3 scores echoed + `highest_score`/
  `highest_score_kind`), `counts`, `detailed_findings[]`, `candidate_false_positives[]`,
  `gaps[]`, `prioritized_remediations[]`. **3.5 can read `scoring_result` directly for the
  raw scores OR the echoed `remediation_result.assessment.scores`** — decide which is the
  cleaner input (probably the `scoring_result` for the authoritative scores + the
  `remediation_result` gaps for coverage caveats).
- **Tolerate partial evidence honestly (the 3.4 lesson, sharpened for 3.5):** 3.4 ranks over
  whichever scores are present and marks `no_scores`/`skipped_no_evidence` honestly. 3.5 must
  turn incomplete evidence into **INCONCLUSIVE**, never a fabricated PASS/FAIL — a partial
  `scoring_result`, a `coverage` gap, or `remediation_result.status != assessed` are all
  INCONCLUSIVE signals.
- **RD-number + collision hygiene:** RD-039 is 3.4's. `grep -oE "RD-0[0-9][0-9]"
  PROJECT_PLAN.md | sort -u | tail` for the next FREE number (expect RD-040, but VERIFY —
  RD-036 was a real collision, RD-017 is a historical gap). **CHECK E is literal** — add the
  new RD's plan-table row BEFORE referencing the number in any living doc.
- **The offline bar (unchanged):** `~/.pyenv/versions/3.12.13/bin/python3 -m unittest`
  (pytest is NOT installed — use `unittest`); `~/.pyenv/versions/3.12.13/bin/ruff check`
  (DEFAULT rules); `env -u NODE_OPTIONS npx tsc --noEmit` shows ONLY the missing-`aws-cdk-lib`
  family — the `main` baseline is **106 errors** (TS2304=9, TS2307=49, TS2339=36, TS2353=6,
  TS2591=6); adding a stack Lambda adds ONE `__dirname` TS2304 (an existing type — fine).
  `env -u NODE_OPTIONS npx prettier --check` for the stack. `jsonschema` is NOT installed
  offline, so the LIVE conformance layer is `skipUnless`-skipped — it runs during the
  stakeholder's live validation.
- **check_docs fixture:** `scripts/test_check_docs.py` `_NEW_WORK_STORY` is now **3.5**.
  **When 3.5 leaves ⬜, repoint it to the next still-⬜ feature story (4.1) IN THE SAME PR**,
  then re-run `python3 -m unittest scripts.test_check_docs` (SUITE line OK).
- **check_docs CHECK I (links):** if you reference a not-yet-authored doc (e.g. the 4.1
  brief/prompt) in a LIVING doc like the on-deck README, CHECK I FAILS until that file
  exists. Author the next-story handoff files BEFORE pointing the on-deck README at them (or
  point at the LIVE-RUNBOOK, which you create this session).
- **check_docs timing (RD-015):** run `check_docs.py` only AFTER committing status/register
  edits (CHECK B baseline is `git show HEAD:RUNBOOK.md`). Set 3.5 🟡 AND add it to the
  register in the SAME commit.
- **User notes:** *(open for the stakeholder — especially the PASS/FAIL/INCONCLUSIVE
  thresholds, which are the stakeholder's decision to make.)*

> **Sequencing note:** 3.5 (verdict derivation) is next by tier after 3.4 — but ONLY after
> 3.4 clears its live pass (advancement gate). It consumes 3.4's findings + 3.3's scores and
> CLOSES Phase 3, unblocking all of Phase 4 (4.1 status-retrieval orchestrator next).
