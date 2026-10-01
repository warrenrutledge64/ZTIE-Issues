# The Project Operating System — Methodology

> A repeatable, disciplined way to run a build project with an AI execution
> partner. This document is the **why and how**; the other files in this repo
> (`PROJECT_PLAN.md`, `RUNBOOK.md`, `BOM.md`, `RESTORE.md`, and the `docs/`
> templates) are the **ready-to-fill what**. Start a new project by creating a repo
> from this template ("Use this template"), then fill in the `{{placeholders}}`.

This is not a coding style guide. It is a **way of working** — how work is
planned, executed, validated, and carried from one working session to the next so
that progress is real, provable, and never built on unproven ground.

---

## 1. The core idea

Big builds fail in predictable ways: work drifts from the plan, "done" is claimed
on things that were never actually verified, and each new working session starts
cold and re-learns (or forgets) what the last one knew. This operating system
exists to prevent exactly those failures. It rests on a few principles:

1. **One story at a time, to completion.** Work is broken into small, ordered
   *stories*. A session takes exactly one story and finishes it. No half-done
   stories left drifting.
2. **Nothing is "done" on inference.** A story is only complete when its result is
   **validated live** and that result is **recorded**. A command exiting without
   error is not proof. "It should work" is never a status.
3. **Validation drives status; status gates advancement.** The recorded validation
   result is what flips a story to done — and you cannot start a story until the
   stories it depends on are done. (See §4, the Validation & Advancement Gate.)
4. **Build from a known-good point; revert, don't forward-patch.** Every validated
   milestone becomes a labeled, returnable restore point. When a slice goes bad,
   you return to the last good point rather than piling fixes onto a broken base.
5. **Warm handoffs.** Each session ends by writing the *next* session's briefing
   while the context is fresh — so the next session starts knowing everything the
   last one learned, including what went wrong.
6. **Two brains, clear roles.** A **planner** decides *what* and *why* and keeps
   the long memory; an **executor** does *how* — builds, tests, and hands back a
   result. They are bridged by a written prompt (see §2).
7. **Management artifacts are first-class.** The plan, runbook, this methodology,
   the restore/inventory docs, the templates, the registered decisions, and the
   per-story briefs/prompts are held to the **same bar as the code** — *reusable,
   durable, repeatable*. They are versioned and change-by-review, kept internally
   consistent (plan↔runbook always align), covered by the restore-point system
   (governance restores with code + state, as one unit), and separable into a
   reusable operating-system layer vs. a project-instance layer. A story is not
   done until its management artifacts are updated and aligned — not just its code.
   These documents *are* the project's durable memory and its reusable OS; they
   earn the same rigor as anything shipped.

Everything below is the machinery that makes these principles automatic instead of
aspirational.

---

## 1a. Development philosophy (what kind of development this is)

These are the project's decided, named terms for *how* it builds. They are fixed
vocabulary, not options to pick from.

**Foundation-First, Component-Driven Development (CDD).** This is the umbrella
name. Hardened, reusable components are built and proven first, then assembled into
features. It prioritizes long-term stability, reusability, and hardness over
feature velocity.

**Dependency-Driven Sequencing.** A story is built only after everything it depends
on — dependency precedence is the hard rule, regardless of story-number. **Build tier
= 1 + the highest tier of anything it depends on**, and it is retained per story as
dependency metadata (it determines precedence and is announced at handoff, below).
The [`RUNBOOK.md`](RUNBOOK.md) master table is the single source of truth for order,
but it is ordered as the **true execution SCHEDULE** — DONE history → OPEN queue (in
the order we intend to work it) → DEFERRED — NOT as a monotonic sort of the `Build
tier` column. Within the hard dependency-precedence constraint we are free to
prioritize INDEPENDENT stories across tiers (e.g. close a tier-0 governance story or
do a tier-6 shared-seam before a tier-9 pipe feature). Consequently the `Build tier`
column is intentionally non-monotonic down the table; the schedule is kept honest
mechanically by [`scripts/check_docs.py`](scripts/check_docs.py) **CHECK C** (C1:
every story appears after all its dependencies; C2: deferred rows stay at the bottom).
The dependency-graph picture (with tiers) lives in
[`docs/BUILD_ORDER.md`](docs/BUILD_ORDER.md).

**Announce tier transitions explicitly at handoff.** Each story's brief and prompt
must state the story's build tier and whether the session **advances to a new tier**
(a new dependency layer opening) or stays within the current tier. This is a
standing requirement, not a nicety: a tier advance is precisely the moment the agent
must re-confirm that the *entire* new dependency set is ✅ and the Validation Debt
Register is empty (the advancement gate, §4) — not merely glance at the
immediately-prior story. A tier transition often coincides with a phase change but is
distinct from it; when both happen, name both. This obligation is encoded in
[`docs/SESSION_BRIEF_TEMPLATE.md`](docs/SESSION_BRIEF_TEMPLATE.md) (the `Build tier`
field + "Where This Story Sits") and
[`docs/SESSION_PROMPT_TEMPLATE.md`](docs/SESSION_PROMPT_TEMPLATE.md) ("WHERE THIS
STORY SITS" + the STEP 0 tier-transition truth).

**Enablers and the Architectural Runway.** The foundational technical work items
are *Enablers*, and together they form the *Architectural Runway*: the
infrastructure, security boundaries, and guardrails that feature work lands on.
They are not user-facing on their own; features land on them.

| Enablers (Architectural Runway) | Features (land on the runway) |
|---|---|
| Story 2.0 isolated-VPC / containment infra; the Forensic to Hub data-contract gate; the detonation containment | The user-facing analysis and dashboard work that runs safely on top of them |

**This philosophy is already encoded in the project's decisions.** It is the "why"
behind **RD-022** (reusable, parameterized components drawn from a shared archive;
proposed in [`docs/governance/FLOOR_AND_HARVEST_PLAN.md`](docs/governance/FLOOR_AND_HARVEST_PLAN.md)
§3, copied into [`PROJECT_PLAN.md`](PROJECT_PLAN.md) §5 when Phase C closes), and it
is enforced by **RD-023** (the Validation Debt Register plus advancement gate in
[`PROJECT_PLAN.md`](PROJECT_PLAN.md) §5: features wait until the foundation they
depend on is validated).

**The tradeoff, stated honestly.** Foundation-First costs more visible effort
upfront and delays user-facing value, in exchange for less rework, less
duplication, and less technical debt later. This is a deliberate, accepted
tradeoff.

Every work recommendation the AI makes is measured against this philosophy
(hardness and reuse), not against speed.

---

## 2. The two roles (split-brain)

| Role | Owns | Analogy |
|------|------|---------|
| **Planner** (strategic) | Architecture, risk, story sequencing, cross-session memory, course-correction. Decides *what* to build next and *why*. | The navigator |
| **Executor** (tactical) | Implements exactly one story: builds, tests, pushes, opens the change for review, reports results. Decides *how*. | The driver |

The two are deliberately separate so neither drifts into the other's job. The
planner does not write the code; the executor does not silently re-plan the
roadmap. They communicate through **one artifact per story: a written prompt**
(the executor's kickoff) generated from a **brief** (the human-readable story
spec). The brief is the source of truth; the prompt is generated from it.

**"Does not silently re-plan the roadmap" — the concrete failure mode.** Choosing
*which* story is worked next is a **Planner/stakeholder decision** (RD-024:
executor recommends, stakeholder decides). Two things the executor must therefore
NOT do: (1) **start a story other than the one at the front of the RUNBOOK's OPEN
schedule** without the stakeholder's explicit go — even when that other story is
"Ready" (all dependencies ✅). Dependency-precedence being satisfied means a story
*may* be built, not that it is *scheduled next*; the schedule order among
independent Ready stories is the stakeholder's call. (2) **Edit the RUNBOOK's
recommendation** (the "Default next action" / schedule order) and then work off
that self-made edit — that is re-planning disguised as executing. If the executor
believes a different Ready story is the better next move, it **surfaces that as a
recommendation and waits for the decision** (logging it in
[`docs/governance/WORK_LOG.md`](docs/governance/WORK_LOG.md) as a recommendation,
not a status change); it does not self-select. This is operationalized as the first
step of the session-open ritual (§5.A.0).

> You can play the planner yourself, or use a second AI/collaborator for it. What
> matters is that the *planning* thinking and the *executing* thinking are kept
> distinct and handed off explicitly in writing.

**The split-brain also carries into validation (RD-052, see §4a).** Beyond
plan-vs-execute, the party that **validates** a story is deliberately not the party
that **built** it: the executor builds and records the result, but the *validation
runbook + its Definition of Done are authored by the independent Planner brain*
from the raw diff + the stakeholder's own requirement — so the builder never grades
its own paper. Details + limits in §4a.

---

## 3. The unit of work: a Story

A **story** is the smallest independently-valuable, independently-validatable slice
of work. Stories are grouped into **phases** (larger milestones). Each story has:

- an **ID** (e.g. `1.2`) and a **title**;
- a list of stories it **depends on**;
- concrete **do-it steps**;
- a **Definition of Done that is a pass/fail validation gate**, not a description;
- a **status** and a recorded **validation result**.

Stories are ordered by **dependency and reuse value** — do the things that unblock
or get reused by the most downstream work first. Genuine shared foundations are
pulled forward and built once, early.

---

## 4. The Validation & Advancement Gate (the heart of the system)

This is the rule that makes "done" mean something. It is **binding**: it drives
status changes and dictates whether work advances.

**Roles.** The **validator** (usually the human, on the live system) runs the
check and confirms the outcome. The **executor records** the result and only then
changes the status. **The executor never self-certifies a story as done.**

**Status legend**

`⬜ Not Started` · `🟡 In Progress` · `⛔ Blocked` · `✅ Done (validated)`

**Story state machine** — a story moves only on a recorded validation result:

| From | Event | To |
|------|-------|----|
| ⬜ | work begins | 🟡 |
| 🟡 | validation **passes** (recorded, confirmed) | ✅ |
| 🟡 | validation **fails / incomplete** | stays 🟡 (or ⛔ if externally blocked) |
| ✅ | (never auto-reverts; a regression opens a new remediation story) | — |

**Two hard rules that follow from it:**

1. **No result → no ✅.** Without a recorded, confirmed pass, a story stays 🟡.
   There is no "probably done."
2. **Fail → no advancement.** If a story fails or is only partially validated, you
   **stay on that story** until it passes. The next session's job becomes *fix and
   re-validate this story* — not the next one.
3. **The covenant is not to be circumvented.** The question *"how do we get around
   validation?"* is itself a **drift signal** — the exact impulse this system exists
   to stop. You do not route around the gate; you **satisfy** it. A story stays 🟡
   through **any** amount of in-progress work and rework — including fixing a defect
   found *after* the code was built (even an architectural one). Reworking a 🟡 story
   is normal, expected activity; it is **not** a reason to bypass validation or to
   flip the status on inference. **Only a recorded live pass of the *final* code
   earns ✅.** When a defect is found before validation, the move is
   **fix-then-validate-once** (validate the code you will actually keep) — never
   validate-the-wrong-thing, and never mark done to "unblock" progress.

   > *Case that taught this (Story 1.1, ZTIE-Issues):* the intake gateway was built,
   > but before validation a topology defect was found — it targeted the Hub account
   > instead of Forensic, which would have placed raw untrusted artifacts in the
   > brains/control-plane account. The correct response was **not** "get around the
   > covenant" — it was: keep the story 🟡, fix the account placement, then do the
   > single live run that validates the corrected code. Being blocked or reworking is
   > the covenant working, not failing.

**Hard advancement gate.** A story **cannot begin** until **every** story it
depends on is ✅. If a dependency isn't ✅, the executor stops and surfaces it
rather than starting.

**Validation-debt gate (no new feature work on open debt).** Beyond the dependency
check, **no NEW feature story may begin while the Validation Debt Register is
non-empty.** That register (at the top of `RUNBOOK.md`) lists every built-but-not-
live-validated story (`🟡` or `⛔`) and the single action to clear each. Reworking or
validating an already-open `🟡`/`⛔` entry is explicitly allowed and is NOT gated
(that is how debt is cleared); only genuinely new feature work is blocked. An entry
is cleared solely by that story's own recorded live validation, never on paper. The
executor owns calling the pause; the stakeholder retains final say. This is machine-
enforced by `scripts/check_docs.py` (`⛔` counts the same as `🟡`).

**Story closure is decoupled from restore-point work.** A story's closure depends
**solely on that story's own recorded live validation** and is **independent of**
restore-point, capture, or archive work. No story is ever held hostage to downstream
restore or capture activity: those are separately-tracked activities (see §6), not a
precondition for an individual story's ✅. (Phase-close, below, is where a restore
point is captured; a single story's ✅ never waits on it.)

**Phase gate.** A phase closes **only** when its end-of-phase check passes and is
recorded. On phase-close — and not before — you capture a **restore point**
(§6), record it in the inventory, and mark the phase done. **The end-of-phase gate
is not left to memory.** When every story in a phase reaches ✅, the phase is
*story-complete* but **not closed**: it still owes its end-of-phase validation + a
captured restore point + the Progress-Summary flip. [`scripts/check_docs.py`](scripts/check_docs.py)
**CHECK N** makes this mechanical — it derives each phase's true roll-up from the
master story table and compares it to the hand-kept Progress Summary:
- a phase marked ✅ while a story in it is still open is a **hard failure** (the
  ledger may never claim a phase is more done than its stories);
- a phase that is story-complete but whose row is not yet ✅ is surfaced as a loud,
  un-missable **advisory on every run** ("PHASE-GATE CLOSE OWED") — the same
  treatment as the Operational Debt register — so a skipped phase-gate can never
  slip the way one did before this check existed.
Closing the phase (running the gate, confirming the restore point, flipping the
row) remains a **stakeholder-confirmed act**, never an auto-flip; CHECK N guarantees
the owed close is always visible until it is done.

**The phase gate has its own split-brain handoff — just like a story.** A phase
validation is a validation, so it carries the same matched handoff pair as a story,
only phase-shaped (anchored to the frozen `restore/phase-N-green` tag instead of a
diff): the *Gemini → Kiro* [`docs/PHASE_GATE_VALIDATION_KICKOFF_SKELETON.md`](docs/PHASE_GATE_VALIDATION_KICKOFF_SKELETON.md)
(drives Kiro to pin a read-only phase target + verbatim RUNBOOK context — the gate
statement, the phase's story set, each story's recorded Validation Result — then
stop) and the *stakeholder → Gemini* [`docs/PHASE_GATE_VALIDATION_PACKAGE_TEMPLATE.md`](docs/PHASE_GATE_VALIDATION_PACKAGE_TEMPLATE.md)
(the validator authors the end-of-phase DoD + live integration runbook blind). Kiro
authors no DoD, no runbook, and no verdict for a phase any more than for a story
(the CHECK O lane). These are the phase-level siblings of the per-story
[`docs/KIRO_VALIDATION_KICKOFF_SKELETON.md`](docs/KIRO_VALIDATION_KICKOFF_SKELETON.md)
+ [`docs/GEMINI_VALIDATION_PACKAGE_TEMPLATE.md`](docs/GEMINI_VALIDATION_PACKAGE_TEMPLATE.md).

**Recording a result.** Every story carries a one-line, dated **Validation
Result**: `pass — <what was checked>, <date>, confirmed by <who>` or
`FAIL — <what failed>, <date>`. That line is the auditable driver behind the
status marker. The marker without a recorded result is not a valid ✅.

### 4a. Split-brain independent validation (RD-052)

**One protocol; only the DEGREE varies.** Every check under this system is a
**validation** — there is no separate class of "real validations" vs. "lesser
checks." A light doc-consistency confirmation and a live security-boundary
detonation are the *same procedure* (this split-brain 4-stage loop, §4b), run
through the *same* package ([`docs/GEMINI_VALIDATION_PACKAGE_TEMPLATE.md`](docs/GEMINI_VALIDATION_PACKAGE_TEMPLATE.md)).
What changes is the **degree** — how deep the Definition of Done and the retained
evidence must go — and that is set by *what the story governs*: a security boundary
demands a positive live exercise + a human raw-record read + retained evidence
(§4c, RD-054); a lighter story demands a lighter DoD. Same protocol, calibrated
depth, always a validation. The package's **cold-start kickoff block** (the
self-contained prompt the stakeholder pastes into a fresh validator chat) is a
**required, standard artifact of every validation** — generated from the template,
never reconstructed ad hoc.

The covenant says *who confirms* a result (the validator, on the live system) and
*who records* it (the executor). This section adds **who authors the check** — and
the answer is deliberately **not the party that built the code**.

**The failure mode it closes: "grading your own paper."** When the build agent
also (a) writes the pass/fail rubric, (b) curates what evidence the check looks at,
and (c) interprets the results, a green validation proves only *internal
consistency with the builder's own understanding* — not correctness. The builder
can unknowingly test its own misreading of the spec and confirm it.

**The split.** The build and the validation-framing are held by different brains:

| Party | Owns | Must NOT |
|-------|------|----------|
| **Executor (builder — e.g. Kiro)** | Builds the code; on a recorded pass, RECORDS the result + flips status. | Author the pass/fail rubric it is judged by; curate what the validator sees; interpret the live results. |
| **Validator (independent — e.g. the Planner brain / Gemini)** | Authors the live-validation runbook **and its own Definition of Done**, tasked to try to **break** the change, not confirm it. | Have written the implementation code under test; inherit the executor's rubric. |
| **Stakeholder (human)** | Carries the **raw diff/PR** to the validator (pulled directly from the repo, not a package curated by the builder); states the requirement in their **own** plain words (the one anchor neither AI authored); runs the runbook on the real system; **reads the raw output** and decides. | Rubber-stamp a "builder-built-it, validator-approved-it" handshake without reading the literal output. |
| **The live system (real AWS)** | Is the **actual grader.** | — |

**Why the inputs must not come from the builder.** Independence lives with
*whoever frames what gets tested*. If the executor hands the validator a curated
package (which diff to show, which invariants to list, which DoD to use), the
validator merely confirms the picture the builder painted — self-grading laundered
through a second name. So the two judgment inputs — **the diff** and **the
requirement the DoD is derived from** — come from the **stakeholder/repo**, never
curated by the builder. The reusable handoff the stakeholder fills and pastes to
the validator is [`docs/GEMINI_VALIDATION_PACKAGE_TEMPLATE.md`](docs/GEMINI_VALIDATION_PACKAGE_TEMPLATE.md).

**A diff is never enough — full context is mandatory (STEP 1.5).** The validator must
**never** be limited to git diffs or PR summaries. A diff shows only changed lines, but
**contextual leaks and wrapper-execution flaws hide in the unchanged surrounding code**
— the Story 2.4 strace defect (tracing the wrapper, not the artifact) lived exactly
there. So every kickoff block carries a mandatory **STEP 1.5 — FULL CONTEXT FETCH**: the
stakeholder pulls the **FULL raw source** (`Accept: application/vnd.github.v3.raw`) of
every **script, parser, or CloudFormation template** the PR modified, **pinned to the
exact commit SHA** (`?ref=<SHA>`), and pastes it to the validator alongside the diff. The
validator may not sign off on boundary-crossing logic or execution telemetry from a diff
hunk alone, and must name any additional file it needs in full before writing the DoD.

**Command-completeness — every "paste X" ships the command that PRODUCES X.** A
validation/handoff block must be **self-contained and copy-paste runnable by the
operator with zero hunting.** Every piece of data the block (or the validator's DoD)
asks the operator to paste — the diff, the full source, a deploy + env-pin check, the
test-input submission, the live result record, the raw trace slice, the retained
evidence — must be accompanied by the **exact command that generates it**, with real
values substituted (intake_id, table/bucket names, SHA) and **each command labeled with
the account it runs in** (e.g. Forensic 360999005254 vs Hub 641628980935) plus an
`aws sts get-caller-identity` guard. Bare command *names*, "run the appropriate query,"
or "the validator's runbook will tell you" are **not acceptable** — the operator should
never have to reverse-engineer how to obtain a required artifact. (When the validator
authors the live runbook it inherits this bar; when Kiro authors the package's objective
command scaffolding, it supplies the runnable commands for every data item the block
names.)

**Keep the kickoff block TIGHT — but self-contained through the fetch (anti-drift,
balanced with command-completeness).** Two failure modes pull in opposite directions, and
the rule holds both. On one side, a long, everything-inlined kickoff block is a concrete
drift hazard: a fact written in the prompt AND an operator section means a later edit — a
renamed file, a new SHA, a reworded DoD item — has to be caught in every copy or they
silently disagree, and the copy the validator actually reads (Part 0) diverges from the
reference. On the other side, stripping the block so far that it asks the operator to
*produce data without the command that produces it* violates command-completeness and
leaves the operator hunting. Resolve it by KIND of content, not by length:
- **IN the kickoff block (Part 0), because the steps need them to run:** the role, the
  stakeholder's `<<<requirement>>>` anchor, the objective pointers (PR #, merge SHA,
  accounts), the **STEP 1 + STEP 1.5 fetch commands** (so Part 0 is self-contained through
  the fetch), and the ordered deliverables. The per-story operator command set (Part A2) is
  the labeled *superset* for the later live-run blocks and may restate STEP 1/1.5 by account
  label — low-drift, because the SHA/PR is a single variable.
- **NOT in the block — referenced instead, because they are the drift-prone facts:** the
  full facts sheet beyond the pointers, the builder's-claims-to-verify, and the fixed
  runbook-output structure. The validator receives these through what the stakeholder
  *pastes and answers* (the diff + full source at STEP 1/1.5, and any value it asks for),
  not by copying paragraphs into the prompt body.

Rule of thumb: **a command that STEP N runs belongs where STEP N is; a fact that can be
edited later and drift belongs in exactly one section and is referenced.** This is a
first-class management-artifact-integrity requirement (RD-015): a poorly structured prompt
is itself a defect — an over-stuffed one manufactures drift, a starved one manufactures
hunting-and-guessing. Enforced by convention + review (the template header states it and
`docs/GEMINI_VALIDATION_PACKAGE_TEMPLATE.md`'s Part 0 is the reference shape).

**Zero trust on the commands, not just the code — a supplied command set is a FLOOR.**
Command-completeness makes the package runnable; this makes it *sufficient*. Every command
in a validation package was written by the builder or the operator, so trusting it to
collect ENOUGH is the same "grading your own paper" failure the split-brain exists to close
— one layer down, at the evidence layer. Therefore every kickoff block MUST instruct the
validator to **analyze each supplied command set for efficacy** — does it actually surface
the evidence needed to prove or break the requirement, or could a real defect hide in what
it does not capture (a truncated trace, a `head -N` that clips the proof, a grep that misses
a syscall/finding family, a query that reads a single field)? — **and to propose additional
commands for more robust data collection**: wider/independent captures, corroborating reads,
and negative probes that would expose a fake or partial result. The validator treats the
supplied commands as a starting floor it is expected to strengthen, never a trusted ceiling,
and its authored runbook (§4b) carries the strengthened commands. A pass built on a command
that under-collects is a pass on incomplete evidence — which for a security boundary is
INCONCLUSIVE, never PASS (§4c, RD-053/054). This language is required in the kickoff block
(Part 0) and echoed in the operator command set and the runbook-output format.

**The loop.**
1. Executor builds the story to completion and opens the change (PR).
2. Stakeholder pulls the **raw diff** from the repo and, with their own plain
   statement of the requirement, pastes both into the validator (via the template).
3. Validator returns an **adversarial review + its own DoD + a numbered,
   soup-to-nuts live runbook** whose pass/fail is visible in the **literal command
   output**.
4. Stakeholder runs it on the live system and **reads the raw output** — the verdict
   is theirs, not narrated by either AI.
5. Stakeholder reports the result; the executor **records it verbatim** and flips
   status per §4 (or fixes-then-revalidates on a fail).

**What this does NOT claim (the honest limits — state them, don't hide them).**
This reduces builder-framing bias; it does **not** make the process objective.
Both brains are LLMs and can share a blind spot. The requirement anchor is only as
good as the stakeholder's own wording. The **live run + the stakeholder's own
reading of the raw output remain the true gate** — an LLM-authored runbook is a
rubric, not the grader. And for the **security-critical boundaries** (the RD-013
Forensic→Hub crossing, secret redaction), a **human reviewer is still required** —
two LLMs agreeing is not the assurance an auditor wants.

**Relation to the rest of the system.** This layers ON TOP OF the covenant (§4 —
the executor still never self-certifies; only a recorded live pass earns ✅) and
the Step-0 true-state gate (RD-051). It changes *who writes the check*, not *what a
pass means*.

### 4b. The hardened 4-stage loop + detection-first (RD-053)

RD-052 removed the builder from *authoring* the rubric. RD-053 pins the mechanics so
the builder cannot re-enter the loop and a security control cannot pass without
being positively exercised. It supersedes the earlier "stakeholder reports the
result to the executor, which records it" wording: **validation lives wholly on the
validator/stakeholder side; the executor (Kiro) is a write-only scribe.**

**The four stages.**

1. **Handoff (Kiro → stakeholder) — PR NUMBER ONLY (RD-055).** Kiro provides the
   **Pull Request number and nothing else**, then **exits the validation loop
   entirely.** Kiro is **forbidden** from providing the raw diff, any diff-fetch
   command, code snippets, or any framing of what changed. (Kiro may still record
   objective pointers such as the commit SHA and stack/resource names in the PR
   description / evidence folder for the ledger, but its **handoff to the stakeholder
   for validation is the PR number alone.**)
2. **Design (stakeholder → Gemini).** The **stakeholder** fetches the **raw diff
   independently, directly from the repository API** (their own choice of tool /
   command — Kiro supplies no command), and states the requirement in their **own
   words**, and pastes both into Gemini. **Gemini authors the command-verifiable DoD
   + the numbered live runbook FROM SCRATCH, blind to Kiro's assumptions** — Kiro
   authors none of it (no runbook, no test script, no live-proof steps; RD-055).
3. **Execute & Judge (stakeholder + Gemini).** The stakeholder runs the steps on
   live AWS and pastes the **raw literal output back to Gemini**, which adjudicates
   a verdict of **PASS / FAIL / INCONCLUSIVE** against its own DoD.
4. **Close-out (stakeholder → Kiro).** **Only** on Gemini's explicit **PASS** does
   the stakeholder bring the sealed verdict + raw evidence to Kiro, whose role is
   **purely administrative** — transcribe the verdict verbatim, flip status, clear
   the register, open the next gate. **Kiro never re-judges, upgrades an
   INCONCLUSIVE, or infers a pass;** if what it is handed is not an explicit PASS, it
   stays 🟡.

**Two hard rules.**

- **(a) Security-boundary positive-exercise.** For any story governing a security
  control (secret detection/redaction, the RD-013 Forensic→Hub crossing, RD-048/049
  auth/signing, artifact destroy/handoff), the live run **must positively trip the
  boundary**. A negative / allowlisted / empty result — e.g. a scanner reporting
  `count: 0` on a planted payload — is **strictly INCONCLUSIVE, never PASS**; it
  proves only that the container did not crash, not that the control works. Offline
  tests may **support** but never **substitute** for the live positive exercise.
- **(b) Redaction standard.** Redaction is proven **only** by a human reading the
  **raw JSON record** to confirm the sensitive value was excised while the finding
  metadata persists — **never** by a summary tag such as `REDACTED-OK` (which is
  circular when `count: 0`, since the sanitizer was never forced to scrub an active
  finding).

**Transport constraint (load-bearing) — HARDENED by RD-055 (zero-trust supply chain).**
Gemini **cannot reach the repo or AWS**, so the raw diff and the raw live output travel
to it **through the stakeholder** (pulled and pasted by them). **RD-055 removes the
earlier "Kiro may help obtain the diff" allowance:** to keep the validation supply chain
unadulterated, Kiro is **forbidden** from providing the raw diff, any diff-fetch command,
or any code snippet — Kiro's entire handoff is the **PR number only** (stage 1). The
stakeholder fetches the diff **independently, directly from the repository API**, so
nothing the validator sees was shaped, selected, or supplied by the builder. If the diff
or the requirement ever reached Gemini via Kiro, the pass is **void**, not merely
provisional — it must be re-sourced by the stakeholder from scratch.

**Guardrail.** The human remains the **final reader** on the security boundary
(Gemini adjudicates against its rubric; it does not self-confirm), and the live run +
the human's own reading of the raw output remain the true gate. Reusable artifact:
[`docs/GEMINI_VALIDATION_PACKAGE_TEMPLATE.md`](docs/GEMINI_VALIDATION_PACKAGE_TEMPLATE.md).

**The RD-055 handoff is no longer left to discipline alone — it is machine-backed +
reminded.** Two memory-independent backstops now enforce "the executor's handoff is
the PR number only":
- **[`scripts/check_docs.py`](scripts/check_docs.py) CHECK O** hard-fails if an OPEN
  story carries an executor-authored ``story-<id>-LIVE-RUNBOOK.md`` — the concrete
  artifact-form of the breach (the builder framing "how to prove it on live AWS").
  LIVE-RUNBOOKs for closed stories are frozen pre-RD-055 history and are
  grandfathered.
- **A `SessionStart` hook** ([`.kiro/hooks/split-brain-validation-contract.json`](.kiro/hooks/split-brain-validation-contract.json))
  re-injects this output contract at the start of every session, so the rule does
  not depend on the executor remembering it mid-conversation. The failure mode this
  closes is subtle: the executor drifting into "being helpful" by offering a
  validation command, awscurl invocation, test input, or acceptance criterion in
  ordinary chat — upstream of the per-story prompt. If you catch yourself about to
  type a validation command or DoD, that is the drift signal; stop and hand off the
  PR number.

### 4c. Evidence-capture: trust the artifact, not the word (RD-054)

RD-053 made the validation independent and detection-first. RD-054 closes the last
leak: **the ledger must not depend on anyone's testimony — not Kiro's, not the
human's recollection, and not Gemini's adjudication.** Independence removes builder
bias; it does not make the validator an oracle. Gemini is an LLM, can share a blind
spot, and only ever sees what the stakeholder pastes it — it has no first-hand view
of the live system. The one thing in the loop that is not somebody's word is the
**raw artifact the live system produced.** (This mirrors the project's own thesis:
ZTIE trusts no incoming artifact — it would be incoherent to validate a zero-trust
system on trust.)

**The rule.** A story that governs a **security boundary** (RD-053 rule (a): secret
detection/redaction, the RD-013 crossing, RD-048/049 auth/signing, artifact
destroy/handoff) may **not** be flipped ✅ unless a durable evidence folder
`docs/validation-evidence/<story-id>/` is committed **alongside the status flip**,
containing:

1. **Raw positive-exercise output** — the literal live output proving the boundary
   fired (e.g. the normalized findings JSON with `gitleaks count ≥ 1`, finding
   present). Literal, not paraphrased.
2. **Proof-of-absence for redaction** — the literal command + output showing the
   planted sensitive value returns **zero** matches in the record (and raw
   `Secret`/`Match` fields are absent). Re-runnable by an auditor.
3. **A named, dated human attestation** — who read the raw record, and when. A bare
   "human verified" / `REDACTED-OK` is not acceptable.
4. **Provenance pins** — the `intake_id` and the commit SHA under test.

The stakeholder captures this **at validation time** — Forensic is ephemeral (RD-012),
so the record can age out; "the evidence is gone" is itself a finding, not a pass.

**What this does and does not claim.** It raises assurance from *testimony* to
*auditable* (a skeptical third party can re-derive the pass from retained artifacts).
It does **not** claim the validation is bulletproof — a passing sample proves the
presence of the tested behavior, never the absence of all defects. Enforced by
[`scripts/check_docs.py`](scripts/check_docs.py): a security-boundary story marked ✅
without its evidence folder + required markers fails. Non-security stories are
unaffected; stories closed before RD-054 are grandfathered but should backfill.

---

## 5. The session ritual

Every working session — no exceptions — follows this shape:

**A. Open — Validation & Advancement Gate first (before any new work):**
0. **Confirm you are working the SCHEDULED next story (sequence check).** The story
   to start is the **first OPEN item in the RUNBOOK schedule order** (the "Ready now"
   bucket, top-down). If the session intends to work a *different* Ready story, that
   is a **re-prioritization of the roadmap — a Planner/stakeholder decision, not the
   executor's** (§2, RD-024): surface it as a recommendation and get the explicit go
   BEFORE starting; do **not** self-select, and do **not** edit the RUNBOOK's "Default
   next action" / schedule order to match your choice and then work off that edit.
   Record any approved reorder in [`docs/governance/WORK_LOG.md`](docs/governance/WORK_LOG.md)
   (a recommendation/decision note, not a status change) so the schedule stays the
   agreed plan of record. Dependency-precedence being satisfied means a story *may*
   be built (step 2), never that it is what we build *next*.
1. **Close out the prior story.** Read the ledger. If the prior story is 🟡 pending
   validation, get the validator's result. On pass → record it + flip to ✅. On
   fail → keep it 🟡 and re-focus this session on fixing it.
2. **Check the advancement gate.** Confirm this story's dependencies are all ✅. If
   not, stop and surface the blocker.

**B. Middle — one story to completion:**
- Design → build → the validator runs the live check → record the result → flip
  status. Push work to a branch and open it for review; never push straight to the
  protected main line.

**C. Close — warm handoff (mandatory, do not skip):**
- Author the **next** story's brief and prompt while context is fresh, including a
  **Lessons Learned / Carry-Forward** section with what *actually* happened this
  session: bugs hit and their fixes, decisions that mattered, the corrected true
  state of the system, operator/UX lessons, and watch-items. Favor lessons from
  the live run over pre-run guesses. A handoff with an empty lessons section is
  incomplete.

---

## 6. Restore-point discipline

A **restore point** is a labeled, returnable known-good state, captured at each
phase gate (and any other point worth being able to return to). It has two halves
that are always captured together:

1. **Code** — an immutable tag on the exact validated commit (e.g. a
   `restore/phase-N-green` convention). Immutable, annotated, created only on a
   confirmed pass.
2. **State** — a manifest of whatever the code deploys/produces (infrastructure,
   config, versions), captured so the deployed reality is recorded, not inferred.

Because the two are paired, you never restore one without the other. When a slice
goes bad, you **return to the last restore point** rather than forward-patching a
broken base. The rule that prevents drift: *if it's deployed, it's in the
inventory; if it's in the inventory, it maps to a restore point.*

---

## 7. Universal disciplines (apply to everything)

- **Verify the real artifact, not the intention.** After a change, confirm the
  *actually-deployed/produced* thing contains the change — the local file passing
  is not proof.
- **State your context on every operational command.** If commands run against
  specific environments/accounts, prefix every command block with a banner naming
  where it runs. Confirm the target before destructive actions.
- **Production-quality by default.** No mock data or placeholder services standing
  in for real ones unless explicitly agreed; real connections, error handling,
  and tests from the start.
- **Interactive prompts read from the terminal, not piped input** — or piped data
  silently auto-answers them. Fail safe (default to "no") when there is no
  terminal.
- **Give the operator the full copy-paste sequence** — every step, in order, with
  real values substituted — not bare command names that assume context.

---

## 8. The document set

These ship in this template (blank, with `{{placeholders}}`) and are filled in per
project. Together they *are* the persistent memory of the project — the system has
no memory outside these files.

| Document | Role |
|----------|------|
| `PROJECT_PLAN.md` | The *what/why*: scope, phases, decisions, acceptance criteria. |
| `RUNBOOK.md` | The *do-it-and-track-it* ledger: every story with status, dependencies, do-it steps, validation result. **Contains the binding Validation & Advancement Gate.** This is the source of truth for status. |
| `BOM.md` (inventory / bill of materials) | The authoritative list of everything the project produces/deploys, each entry tied to a restore point. Defense against drift. |
| `RESTORE.md` | The restore-point procedure: tagging convention, state capture, and coordinated revert. |
| `SESSION_BRIEF_TEMPLATE.md` | Human-facing story spec (for all stakeholders); doubles as change record + audit artifact. |
| `SESSION_PROMPT_TEMPLATE.md` | Executor-facing kickoff prompt, generated from the brief; primes a fresh session with zero cold-start. |
| `session-briefs/` | The filled-in briefs + prompts, one per story, as the project runs. |

---

## 9. How to start a new project with this kit

1. **Create a new repo from this template** ("Use this template" on GitHub), then
   replace every `{{PROJECT_NAME}}` placeholder with your project's name.
2. **Fill `PROJECT_PLAN.md`** — scope, phases, the ordered story list, acceptance
   criteria. Keep the Universal Acceptance Criteria that apply to every story.
3. **Seed `RUNBOOK.md`** from the plan — one row per story, dependencies set, all
   ⬜. Keep the Validation & Advancement Gate section verbatim; it is the engine.
4. **Adjust `RESTORE.md` and `BOM.md`** to your project's technology (what a
   "state manifest" means for you).
5. **Protect your main line** so it is change-by-review only (no direct pushes,
   no force-push). This is what makes the restore-point history trustworthy.
6. **Run story 1** using the session ritual (§5): fill its brief + prompt from the
   templates, execute to a validated pass, then write the next story's handoff.

That's the whole system. It is intentionally lightweight — a handful of documents
and one binding rule — because the discipline, not the tooling, is what makes
progress real.
