# ZTIE — Transition Plan: "Close Phase-2 floor, then build the reusable way"

> **The what and why (for this transition only).** This is a **self-contained,
> time-boxed plan** that carries ZTIE from *where it is today* (mid-Phase-2, still
> building infra as hand-written, per-story stacks) to *where it needs to be* (2.0
> and 2.1 locked ✅ and backed up by real restore points, and every component
> hereafter built as a **parameterized, decoupled, reusable micro-component drawn
> from a shared archive**). It ends at the doorstep of **Story 2.2** — which will be
> the first story built the new way.
>
> Same discipline as [`PROJECT_PLAN.md`](../PROJECT_PLAN.md) / [`RUNBOOK.md`](../RUNBOOK.md)
> and [`METHODOLOGY.md`](../METHODOLOGY.md): phased, dependency-gated, **nothing is
> "done" on inference** — a live/again-provable validation drives status and gates
> advancement, and every completed step earns a **restore point**.

## 0. Why this plan exists (the drift signal)

A repo audit (2026-09-01) found ZTIE is **still building in the fashion that caused
the previous burn-down**: AWS primitives (`s3.Bucket`, `sqs.Queue`,
`lambda.Function`, `RestApi`, `Table`) are instantiated **raw and inline in every
stack**; the `awsio` seam is **duplicated** across Lambdas; there are **5 bespoke
contract generators** (~160–300 lines each) re-implementing the same
"SCHEMA-dict → json.dump to two paths" logic; the Hub gate is a **703-line
monolith** with 13 repeated per-envelope-kind helpers; and **no shared, reusable,
parameterized construct library exists**. Restore-point practice is **half-done**:
code-level tags exist, but no deployed-state manifest has been captured and BOM has
11 `pending` rows.

The stakeholder has called a **FULL STOP on new feature work** until we are, in
practice, building **micro / decoupled / parameterized components from an archive,
with restore points**. This plan is that stop, made concrete.

**Utility over convenience:** the goal is durable, reusable building blocks — not
the fastest path to the next feature. We accept more up-front work to stop the
duplication accretion that kills the effort at scale.

## 1. Non-negotiable constraints (for this transition)

- **Additive, never a burn-down.** The live, validated system on `main` is not
  rewritten. The archive is *new code*; ZTIE adopts it *incrementally* and each
  adoption is **proven drift-free by `cdk synth` diff** before any deploy. Any stack
  that cannot be proven equivalent is stopped and reassessed — never forced.
- **Floor first.** We do **not** convert on top of un-validated or un-backed-up
  state. 2.0 must be validated and both 2.0/2.1 restore-pointed **before** conversion.
- **Restore point per step.** Every completed step tags a `restore/<id>-green` and,
  where deployed state changes, captures a manifest. Code + state + governance
  restore as one unit.
- **Parameterization principles (define once, vary by prop):**
  1. **Secure/opinionated defaults are baked in, not parameters** — a caller cannot
     turn off KMS / block-public / SSL / fail-closed. Secure by construction.
  2. **Only real, observed variation becomes a prop** — no speculative knobs. A prop
     is added when a *second real use* needs it (interfaces firm up over first uses;
     start at `0.x`).
- **The methodology itself is the deliverable.** By the end, "build a component" =
  "instantiate a parameterized construct from the archive," not "hand-write another
  stack." This is registered as a decision (RD-022, below) so it is not re-litigated.

## 2. Phases

Two gate-phases (**T0** close the floor, **T1** build the archive + convert), then
the exit. Each row is a story tracked in §4.

### Phase T0 — Close & back up the Phase-2 floor
*Goal: 2.0 ✅, 2.1 ✅-confirmed, both backed by real (deployed-state) restore points,
capture tooling correct for the post-2.1 shape. This is the known-good floor we
convert from — and the fallback if conversion goes wrong.*

- **Gate:** 2.0 validated live and flipped ✅; 2.1 confirmed ✅ on `main`; a
  deployed-state manifest captured + `verify`-clean for **both** accounts; BOM's 11
  `pending` rows filled; `restore/story-2.0-green` + `restore/phase-2-floor-green`
  tags pushed.

### Phase T1 — Stand up the archive & convert to the practice
*Goal: a separate, versioned, parameterized construct archive exists; the shared
Python seam + one generator replace the duplication; ZTIE's existing stacks are
migrated onto the archive, each proven drift-free; building-the-new-way is the
default.*

- **Gate:** the archive repo builds + tests green and is consumable; ZTIE imports it;
  at least the first migrated stack synthesizes to an identical (or explainably
  identical) template and re-deploys "(no changes)"; the practice is documented in
  METHODOLOGY + RD-022.

### Exit — Ready for Story 2.2 (the new way)
*Story 2.2 is NOT part of this plan. This plan ends when 2.2 can be started by
instantiating archive constructs rather than hand-writing a stack. 2.2 then proceeds
under the normal RUNBOOK.*

## 3. Registered decision introduced here

| ID | Decision | Rationale |
|----|----------|-----------|
| **RD-022** | **Components are built as parameterized, decoupled, reusable micro-constructs drawn from a shared, versioned archive (`infra-building-blocks`), with secure defaults baked in and only real variation exposed as props. ZTIE adopts the archive ADDITIVELY and migrates existing stacks only when proven drift-free by `cdk synth` diff — never by rewrite. Every transition step earns a restore point.** | The previous effort burned down from accreting hand-written, duplicated stacks. Reuse-by-construction (not copy-paste) + drift-proven migration + restore points is the practice that prevents recurrence. Utility over build convenience. |

> RD-022 is proposed here and will be copied into `PROJECT_PLAN.md` §5 (decisions
> table) when this plan's T1 gate passes, so the main plan carries it going forward.

## 4. Stories (tracked like the RUNBOOK)

> Status legend: `⬜ Not Started` · `🟡 In Progress` · `⛔ Blocked` · `✅ Done (validated)`.
> Same gate as the RUNBOOK: a story is ✅ only on a recorded, confirmed pass.

| Story | Title | Depends on | Status | Restore tag |
|-------|-------|-----------|--------|-------------|
| **T0.1** | Merge the capture-tooling extension (post-2.1 targets) to `main` | — | 🟡 | — |
| **T0.2** | Validate Story 2.0 live (isolated VPC, launch template, SSM, no-egress) → flip ✅ | 2.0 built | ⬜ | `restore/story-2.0-green` |
| **T0.3** | Confirm Story 2.1 ✅ on `main` (already validated 2026-09-01) — no re-run, just confirm + carry into the floor tag | 2.1 ✅ | ⬜ | (folds into floor) |
| **T0.4** | Institute deployed-state restore points: `capture` + `verify` both accounts, commit manifests, fill BOM's 11 `pending` rows | T0.1, T0.2 | ⬜ | `restore/phase-2-floor-green` |
| **T1.1** | Stand up the archive repo `infra-building-blocks` (CDK L3 construct library; peer-dep `aws-cdk-lib`; jest Template tests; SemVer `0.x`; checkpoint tags) | T0.4 | ⬜ | archive `v0.1.0`+ |
| **T1.2** | Build the first parameterized constructs, seeded from ZTIE's proven patterns: `SecureBucket`, `ContractIngestQueue`, `OneWaySenderGrant`, `SecureRestApi`, `ContractGateLambda`, `AccountGuardedStack` | T1.1 | ⬜ | archive tag per construct |
| **T1.3** | Shared Python seam + one generator: extract the duplicated `awsio` + the hub-gate envelope-kind pattern into an importable module; collapse the 5 bespoke generators into ONE parameterized generator (identical output, hash-matched) | T0.4 | ⬜ | `restore/shared-seam-green` |
| **T1.4** | Migrate ONE ZTIE stack onto the archive as the proof: rewrite to use constructs, prove `cdk synth` = same CloudFormation (or explainable diff), one live "(no changes)" deploy | T1.2 | ⬜ | `restore/migrate-<stack>-green` |
| **T1.5** | Record the practice: RD-022 into `PROJECT_PLAN.md`; a METHODOLOGY §"build-from-archive" note; update the story BRIEF/PROMPT templates so future stories default to archive constructs | T1.4 | ⬜ | (docs) |

## 5. Definition of Done (this plan) — the exit gate

All true:
1. **2.0 ✅** (recorded live validation) and **2.1 ✅** confirmed on `main`.
2. **Deployed-state restore instituted**: manifests captured + `verify`-clean for Hub
   and Forensic; BOM has zero `pending`; `restore/phase-2-floor-green` tag pushed.
3. **Archive exists and is real**: `infra-building-blocks` repo builds, tests pass,
   is version-tagged, and ZTIE can `import` it.
4. **Parameterized-by-construction proven**: at least one ZTIE stack migrated onto the
   archive with an identical/explained synth diff and a "(no changes)" deploy.
5. **Duplication reduced**: the shared seam + single generator replace the copies.
6. **Practice recorded** (RD-022 + METHODOLOGY + templates) so 2.2 onward defaults to
   building from the archive.

On all six: **the full stop lifts** and Story 2.2 begins — built the new way.

## 6. Sequence (execution order)

```
T0.1  merge capture-tooling extension  ──►  T0.2  validate 2.0 (live)  ──►  T0.3 confirm 2.1
                                                        │
                                                        ▼
                                   T0.4  capture + verify + BOM  ──►  tag restore/phase-2-floor-green
                                                        │
                                                    [FLOOR SET — safe to convert]
                                                        │
        ┌───────────────────────────────────────────────┼───────────────────────────────┐
        ▼                                                 ▼                               ▼
 T1.1 archive repo  ──►  T1.2 constructs        T1.3 shared seam + one generator     (parallel-safe)
        └───────────────────┬───────────────────────────┘
                            ▼
                   T1.4 migrate ONE stack (drift-proven)  ──►  T1.5 record the practice
                            ▼
                   ── EXIT: ready to build Story 2.2 from the archive ──
```

## 7. What only the stakeholder can do (out-of-band)

- **T0.2 / T0.4:** run the live AWS commands in CloudShell (validation + `capture`/
  `verify`) — the executor prepares and records but has no live creds.
- **T1.1:** create the empty `infra-building-blocks` GitHub repo (executor builds the
  contents; cannot create repos under the account).
- **All merges** remain the repo-owner's action (PR-based, never direct to `main`).
