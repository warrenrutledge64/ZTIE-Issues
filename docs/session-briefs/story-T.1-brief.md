# Session Brief — Story T.1 (multi-tenant isolation: design spike + architecture doc)

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.
>
> **T.1 is a DESIGN SPIKE — doc-only, NO production code.** Its output is a ratified
> architecture doc (`docs/architecture/MULTI_TENANCY.md`) that writes up the ALREADY-SETTLED
> RD-028 multi-tenancy decisions + the migration path, and moves RD-028 from Proposed toward
> ratified. It does NOT re-open or re-litigate RD-028; it documents it. There is NO live AWS
> gate — T.1 is validated by stakeholder review.

---

## Story T.1 — Multi-tenant isolation: design spike + architecture doc

| Field | Value |
|-------|-------|
| **Track** | tenancy (Worry 2 — tenant isolation) |
| **Build tier** | 5 (per the RUNBOOK master table). T.1 is a doc-only spike that may proceed early; its only dependency (2.3) is ✅, so it has been schedulable for a while. It is NOT part of the pipe tier ladder. |
| **Date** | TBD (next session) |
| **Status** | ⬜ Not Started (doc-only; may proceed early). |
| **Depends on** | **2.3 ✅** (best authored once the P2 pipeline floor is stable so tenancy is not designed against a moving target — that floor is now well past, with Phase 3 closed). |
| **Registered direction** | **RD-028** (decisions settled 2026-09-07; PROPOSED). T.1 documents + ratifies them. |
| **Session goal** | Write `docs/architecture/MULTI_TENANCY.md` capturing the RD-028 decisions (both boundaries + rationale + rejected alternatives), the subscriber-identifier model, how the Hub partitions many subscribers' data, the Phase-4 dashboard as a per-subscriber org-shared view, and the migration path from today's single shared Forensic account to per-subscriber accounts; then move RD-028 from Proposed toward ratified (accountable-party sign-off) + add candidate control mappings. NO code. |

---

### ⚠️ WHY T.1 IS NEXT (sequencing — read this)

Story 3.5 closed **Phase 3** (2026-09-13). Per the RUNBOOK "Ready now" schedule + the
sequencing rule (METHODOLOGY §5.A.0), the story to START is the **first OPEN item in tier
order** — which is **T.1 (tier 5)**, NOT the next pipe story 4.1 (tier 13). The stakeholder
recorded this explicitly on 2026-09-13 in `docs/governance/WORK_LOG.md`: T.1 should land
**before Phase 4** because it protects the Phase-4 dashboard/Hub design (which must be built
tenant-aware, not retrofitted). T.1 is doc-only + cheap, and unblocks T.2. This brief does
NOT re-decide that ordering — STEP 0 confirms T.1 is the first OPEN Ready-now item.

*(The advancement gate is not relevant in the usual sense here — the Validation Debt Register
is EMPTY after 3.5 closed, and T.1 has no unmet dependency. STEP 0 confirms both.)*

### What This Story Is (nature + gate role)

**Nature: a DESIGN SPIKE (doc-only).** No production code, no new Lambda, no CDK, no live
AWS. The deliverable is a written, PR-reviewed architecture doc that captures decisions the
stakeholder already made (RD-028) so the Phase-4 build is tenant-aware. Its "validation" is
**stakeholder review + RD-028 ratification** — there is no live green-run gate. It is the
cheap, correct moment to pin the tenant model in writing before Phase 4 designs the dashboard
+ Hub partitioning.

### Objective & Value

- **Objective:** author `docs/architecture/MULTI_TENANCY.md` and ratify RD-028.
- **Why it matters:** Phase 4 builds the Hub dashboard + handoff. If the tenant model is not
  written down first, the dashboard/Hub get built single-tenant and later retrofitted (costly
  + risky). Naming both isolation boundaries now keeps Phase 4 + the Hub built tenant-aware.

### Scope, Dependencies & Position

- **In scope (the doc must capture — from RD-028, write up, do NOT re-litigate):**
  - **BETWEEN subscribers = HARD isolation via a per-subscriber Forensic AWS account**
    (vended via AWS Organizations; the Hub stays the shared control plane tracking all
    subscribers, each subscriber gets its own disposable Forensic blast-zone account).
    Record the alternatives considered + **rejected as primary** and WHY: per-tenant VPC in a
    shared account (shared-account blast radius / IAM / limits), per-tenant full-stack cell.
  - **WITHIN a subscriber = SHARED-TRUST:** colleagues share the subscriber's environment and
    both see the subscriber's org-shared dashboard + results (a feature, not a leak).
    Isolation granularity is **per-subscriber, NOT per-user** — no per-user accounts, no
    per-user data partitioning, no per-user IAM scoping. Team-vs-team isolation inside an org
    is a possible **future opt-in, explicitly out of scope now**.
  - **Residue containment is the ephemeral host + wiped EBS volume**, NOT accounts or
    endpoints — document this so the design is not over-built (ties to RD-027's residue note).
  - **The subscriber-identifier model** — how a subscriber is identified end-to-end, and how
    the Hub **partitions many subscribers' data** on the shared control plane (the tracking
    record + dashboard queries scoped by subscriber).
  - **The Phase-4 dashboard is a per-subscriber, org-shared view** (all users at a subscriber
    see that subscriber's data; never another subscriber's).
  - **The migration path** from today's **single shared Forensic account** (360999005254) to
    per-subscriber vended accounts — how the current single-tenant deployment maps forward
    without a rebuild.
- **Also in scope:** move RD-028 Proposed → ratified (accountable-party sign-off, dated +
  attributed) + candidate control mappings (RD-014) recorded in the doc (note: `docs/COMPLIANCE.md`
  already carries a **Ratified** RD-028 / Story T.1 row — reconcile with it, don't duplicate).
- **Out of scope (do NOT build):** any provisioning / deprovisioning automation (that is
  **T.2** — deferred to the commercialization phase); Hub-side data-partitioning
  implementation (that is **T.3**); any per-user isolation; any code at all.
- **Depends on:** 2.3 ✅. **Unblocks:** T.2 (per-subscriber environment vending) + T.3
  (Hub-side data partitioning), both scoped FROM this doc.

### Approach & Constraints

- **Doc-only.** The only file created is `docs/architecture/MULTI_TENANCY.md` (plus the
  RD-028 ratification edit + any COMPLIANCE reconciliation). No Lambda, no CDK, no schema, no
  test, no live AWS.
- **Document, don't re-decide.** RD-028's decisions are settled — write them up with rationale
  + rejected alternatives + migration path. If drafting surfaces a genuine NEW sub-decision,
  raise it explicitly (register the next free RD after RD-040 — VERIFY — and add its
  plan-table row BEFORE referencing the number; CHECK E is literal); do not silently change
  RD-028.
- **AWS-native framing.** The vended-account model is AWS Organizations (consistent with the
  Hub/Forensic/Sandbox multi-account topology + the AWS-native-operations learning).
- **Docs first-class (RD-015):** PR-reviewed; PROJECT_PLAN ↔ RUNBOOK aligned; the new doc is
  a durable management artifact.
- **Roles:** ratification (Proposed → Ratified) is the **accountable party's** call
  (repo owner), not the executor's — the executor drafts + proposes; the stakeholder ratifies.

### Validation Rationale & Compliance Mapping (REQUIRED — RD-014)

- **Rationale:** a written, ratified tenant model lets Phase 4 (dashboard + Hub partitioning)
  and later T.2/T.3 be built tenant-aware from the start rather than retrofitted, and records
  WHY the hard boundary is a per-subscriber account (auditable design intent).
- **Candidate control mappings** *(the RD-028 / Story T.1 row is already **Ratified** in
  `docs/COMPLIANCE.md` — cite/reconcile it; do not create a duplicate):*

| Framework | Control ID | Control Name | Rationale | Status |
|-----------|-----------|--------------|-----------|--------|
| NIST 800-53 r5 | SC-7 | Boundary Protection | Per-subscriber account is the hard boundary | Ratified (per COMPLIANCE.md) |
| NIST 800-53 r5 | SC-2 | Separation of System & User Functionality | Between-subscriber separation | Ratified |
| NIST 800-53 r5 | SC-4 | Information in Shared Resources | No cross-subscriber residue | Ratified |
| NIST 800-53 r5 | SC-32 | System Partitioning | Per-subscriber Forensic account partition | Ratified |
| NIST 800-53 r5 | AC-4 | Information Flow Enforcement | Hub partitions per-subscriber data | Ratified |
| NIST CSF | PR.AC-5 | Network integrity / segregation | Account-level segregation | Ratified |
| ISO 27001:2022 | A.8.22 | Segregation of networks | Per-subscriber account boundary | Ratified |

### Management-Artifact Obligations (REQUIRED — RD-015)

- [ ] `docs/architecture/MULTI_TENANCY.md` authored (both boundaries + rationale + rejected alternatives + subscriber-id model + Hub partitioning + Phase-4 dashboard view + migration path).
- [ ] RD-028 moved Proposed → Ratified (accountable party, dated + attributed) in PROJECT_PLAN.md.
- [ ] `docs/COMPLIANCE.md` RD-028 / T.1 row reconciled (already Ratified — ensure consistency, no duplicate row).
- [ ] Story's brief + runbook entry updated (status, Validation Result, dates); PROJECT_PLAN ↔ RUNBOOK aligned (T.1 identical in both).
- [ ] All doc changes PR-reviewed (branch + PR, never straight to main).
- [ ] `check_docs` fixture `_NEW_WORK_STORY` — T.1 is a `tenancy`/design story, NOT a pipe feature story; confirm whether the fixture needs repointing (it currently tracks the next PIPE feature story, 4.1 — T.1 closing likely does NOT change it, but verify + run `python3 -m unittest scripts.test_check_docs` → SUITE OK).
- [ ] On stakeholder-review pass: record Validation Result + flip T.1 ✅ (paired commit); update the on-deck pointer to the next Ready-now item (likely B.1, tier 6, then the pipe story 4.1 — read it off the RUNBOOK schedule, do not assert).
- [ ] Author the next story's handoff with real Lessons Learned (per the sequencing rule — the first OPEN Ready-now item after T.1).

### Definition of Done / Validation Gate

- **Done means:** `docs/architecture/MULTI_TENANCY.md` exists + PR-reviewed; BOTH boundaries
  documented with rationale + rejected alternatives + the migration path from the single
  shared Forensic account; RD-028 ratified by the accountable party; T.2/T.3 scoped from it.
- **Validated by:** **stakeholder review** (design story — NO live AWS gate).
- **Validation Result:** `pending`.
- **On pass:** record dated result, flip T.1 ✅ (paired commit), keep PLAN ↔ RUNBOOK aligned,
  repoint the on-deck pointer to the next first-OPEN Ready-now item.
- **On fail (review asks for changes):** T.1 stays ⬜/🟡; revise the doc + re-review.

### Risks & Watch-Items

- **Do NOT build anything.** The strongest failure mode for a design spike is scope creep into
  T.2 (provisioning code). Keep it a doc.
- **Do NOT re-open RD-028.** Write up the settled decisions; a new sub-decision needs its own
  new RD (do not mutate RD-028's meaning).
- **Sequencing:** T.1 is next per the WORK_LOG reorder; after T.1, the next item is read off
  the RUNBOOK Ready-now schedule (likely B.1 tier 6, then 4.1) — do NOT assert 4.1 as next.
- **No live gate** — this story is not validated by a green run; it is validated by review.
  Do not fabricate a "live pass"; record the stakeholder's review acceptance instead.

### Lessons Learned / Carry-Forward (from the 3.5 build + validation, 2026-09-13)

- **Sequencing discipline (the reason T.1 is next):** deps-✅ makes a story *eligible*, not
  *next* — the story to START is the first OPEN item in the RUNBOOK "Ready now" schedule in
  tier order (§5.A.0). After 3.5 closed Phase 3, that is T.1 (tier 5), not the higher-tier
  pipe story 4.1. `check_docs` CHECK J flags an on-deck-vs-schedule mismatch as a non-blocking
  advisory; a stakeholder reorder is recorded in `docs/governance/WORK_LOG.md`. (This session
  is the reorder being honored.)
- **check_docs timing (RD-015):** run `check_docs.py` only AFTER committing status/register
  edits (CHECK B baseline is `git show HEAD:RUNBOOK.md`). Update the **RUNBOOK master table
  ONLY** for status; README / on-deck / BUILD_ORDER POINT to it (CHECK H verifies). `pytest`
  is NOT installed offline — run `~/.pyenv/versions/3.12.13/bin/python3 -m unittest`.
- **CHECK I (broken-link):** if a LIVING doc links a not-yet-authored file, CHECK I fails.
  When the on-deck README points at T.1's brief/prompt, those files must exist (they do — this
  brief + `story-T.1-PROMPT.md`). When you later point it at the next story, author that
  handoff first.
- **CHECK E is literal:** if T.1 authoring registers a NEW RD, add its PROJECT_PLAN row BEFORE
  referencing the number in any living doc (RD-028 already exists — ratifying it needs no new
  number).
- **Stale-branch trap:** cut T.1's branch from the LATEST `main` (after the 3.5-closure +
  T.1-reorder docs merge). If you branch early, `git merge origin/main` + commit BEFORE
  running check_docs.
- **User notes:** *(open for the stakeholder — e.g. the subscriber-identifier scheme, and any
  constraint on the migration path from the current single Forensic account.)*

> **Sequencing note:** T.1 is the first OPEN "Ready now" item (tier 5) after Phase 3 closed,
> per the 2026-09-13 WORK_LOG reorder. It is doc-only and unblocks T.2/T.3. The next PIPE
> story (4.1, tier 13) is staged and follows once the Ready-now schedule reaches it.
