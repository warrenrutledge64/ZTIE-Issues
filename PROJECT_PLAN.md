# {{PROJECT_NAME}} — Project Plan

> The **what and why**. This plan defines scope, phases, decisions, and acceptance
> criteria. The [`RUNBOOK.md`](RUNBOOK.md) tracks execution against it; the two
> must stay in sync. No phase is "done" until its live validation passes (see the
> runbook's Validation & Advancement Gate).

## 1. Project Identity

{{2–4 sentences: what this project is, the problem it solves, and the end state
that "done" looks like. Written so a newcomer has enough footing to follow.}}

## 2. Non-Negotiable Constraints

> The rules that hold across every phase. Any deliverable violating one is not
> done, regardless of other progress.

- {{constraint 1}}
- {{constraint 2}}
- **Production-quality:** no mocks/placeholders standing in for real services
  unless explicitly agreed.
- **Validation-gated:** nothing is "done" on inference — the user validates live
  and the result is recorded.
- **Restore-point discipline:** build from a known-good point; revert rather than
  forward-patch.

## 3. Phases & Milestones

> Ordered by dependency + reuse value. Pull genuine shared foundations forward and
> build them once. Each phase has a single, live end-of-phase validation gate.

### Phase {{PHASE_ID}} — {{PHASE_NAME}}
- **Goal:** {{what this phase delivers}}
- **Gate:** {{the live validation that closes it}}
- **Stories:** {{list — mirrored with detail in the runbook}}

_(repeat per phase)_

## 4. Dependency Map

**Hard dependencies (X cannot start until Y exists):**
- {{X ← Y, with the reason}}

**Shared foundations pulled forward (multi-phase reuse):**
- {{foundation — why it is built once, early}}

## 5. Registered Decisions

> Durable decisions with an ID so they can be referenced and ratified, not
> re-litigated each session.

| ID | Decision | Rationale | Date | Status |
|----|----------|-----------|------|--------|
| {{RD-001}} | {{decision}} | {{why}} | {{date}} | {{proposed / ratified}} |

## 6. Universal Acceptance Criteria

Every deliverable, in every phase, must satisfy (kept in sync with the runbook):
1. {{criterion 1}}
2. {{criterion 2}}
3. {{criterion 3}}
