# ZTIE Execution-Order Runbook (derived view)

> **Derived, dependency-ordered view of [`../RUNBOOK.md`](../RUNBOOK.md).** This
> file re-presents the SAME stories as the runbook, but sequenced in strict
> execution (topological) order instead of grouped by phase. It is a read-only
> mirror. [`../RUNBOOK.md`](../RUNBOOK.md) remains the **source of truth** for
> story status, dependencies, validation results, and completion dates. **Nothing
> here changes status** — status is only ever flipped in `../RUNBOOK.md`, by hand,
> per the Story Close-Out Procedure. If any story's dependencies or status change
> in the runbook, **this view must be regenerated** so it does not drift.

## How this view is ordered

Stories are **topologically sorted by their `Depends on` column**: a story appears
only after every story it depends on has already appeared. Ties (stories that
become eligible at the same point) are broken by story ID. Each row carries the
same fields as the source runbook, copied verbatim: Story ID, Title, Depends on,
Status, Completed date (if any), and Restore tag (if any).

Cross-cutting / governance stories (G-1, G-2, G-3) have **no pipeline dependency**;
they are sequenced by readiness rather than by the pipeline DAG, so they are listed
in their own section at the end rather than woven into the numbered order.

Status legend (same as the runbook): `⬜ Not Started` · `🟡 In Progress` ·
`⛔ Blocked` · `✅ Done (validated)`.

## Execution order (dependency-sorted)

| # | Story | Title | Depends on | Status | Completed | Restore tag |
|---|-------|-------|-----------|--------|-----------|-------------|
| 1 | 1.1 | Intake gateway endpoint (payload/artifact entry) | — | ✅ | 2026-08-24 | |
| 2 | 1.1R | Remediation: move durable tracking record Forensic → Hub behind the data-contract gate (RD-012/013/016) | 1.1 | ✅ | 2026-08-25 | |
| 3 | 1.2 | Preprocessor classifier (extension + metadata inspection) | 1.1 | ✅ | 2026-08-25 | |
| 4 | 1.R | Restore-point mechanism: state-capture + coordinated restore; fill RESTORE.md + BOM.md (prerequisite for the P1 close) | 1.1R | ✅ | 2026-08-25 | |
| 5 | 1.3 | Routing table → static & dynamic lanes | 1.2 | ✅ | 2026-08-27 | |
| 6 | 1.4 | Safe-reject path for unknown/incompatible types | 1.2 | ✅ | 2026-08-27 | |
| 7 | 2.0 | AWS infra foundation (CDK v2: VPC/isolated subnets, IAM, launch template, SSM, Nova Pro access) | 1.3 | 🟡 | | |
| 8 | 2.1 | Static scanning stack (cfn-lint, cfn-guard, checkov, bandit) | 1.3 | ✅ | 2026-09-01 | |
| 9 | 2.2 | Compliance-framework mapping (NIST SP 800-53 / ISO 27001) + signature scans | 2.1 | ⬜ | | |
| 10 | 2.3 | Detonation chamber — ephemeral EC2 + host-native SSM execution | 2.0 | ⬜ | | |
| 11 | 2.4 | Behavioral telemetry capture (syscalls / network / filesystem) | 2.3 | ⬜ | | |
| 12 | 2.5 | Telemetry sanitization pipeline (entropy scrub → noise suppress → ≤25K truncation) | 2.4 | ⬜ | | |
| 13 | 2.6 | Parallel orchestration / fork of the two lanes | 2.1, 2.3 | ⬜ | | |
| 14 | 3.1 | Telemetry aggregation / normalization (shared schema) | 2.6 | ⬜ | | |
| 15 | 3.2 | Nova Pro correlation engine (exponential-backoff retry) | 3.1, 2.5 | ⬜ | | |
| 16 | 3.3 | accuracy + gap_analysis synthesis | 3.2 | ⬜ | | |
| 17 | 3.4 | Unified threat scoring + prioritized remediations | 3.3 | ⬜ | | |
| 18 | 3.5 | Verdict derivation (PASS / FAIL / INCONCLUSIVE) | 3.4 | ⬜ | | |
| 19 | 4.1 | Status-retrieval orchestrator | 3.5 | ⬜ | | |
| 20 | 4.2 | Dashboard JSON payload | 4.1 | ⬜ | | |
| 21 | 4.3 | Real-time dashboard (dark theme, graduated severity/threat color coding) | 4.2 | ⬜ | | |
| 22 | 4.5 | Per-execution PDF report (tiered: Executive / Security / Developer) | 4.1 | ⬜ | | |
| 23 | 4.6 | ACCEPT → ZTIE pushes hash-verified artifact Forensic → Pipeline-Sandbox (PDE handoff) | 4.1 | ⬜ | | |
| 24 | 4.7 | REJECT → destroy artifact + detonation chamber in Forensic; INCONCLUSIVE → hold at approval gate | 4.1 | ⬜ | | |
| 25 | 4.4 | Interactive accept/reject control (Hub) gating the Forensic→Pipeline-Sandbox push | 4.3, 4.7 | ⬜ | | |

> Note on step 25: **4.4 appears after 4.7** because it depends on **both 4.3 and
> 4.7**. A story may not precede any of its dependencies, so 4.4 is placed only
> once both are already in the order.

> Open validation debt: **2.0 (step 7)** is `🟡` — built but not yet live-validated.
> See the Validation Debt Register in [`../RUNBOOK.md`](../RUNBOOK.md); a new feature
> story may not begin while that register is non-empty.

## Cross-cutting / Governance (no pipeline dependency; sequenced by readiness)

These stories are not part of the pipeline DAG. They have no `Depends on` and are
started when ready, so they sit outside the numbered execution order above.

| Story | Title | Depends on | Status | Completed | Restore tag |
|-------|-------|-----------|--------|-----------|-------------|
| G-1 | Back-map design artifacts to candidate NIST family + ISO 27001 controls (RD-014) | — | ⬜ | | |
| G-2 | Management-artifact integrity: automated consistency check + reusable-OS/instance separation (RD-015) | — | ⬜ | | |
| G-3 | Hard-pause enforcement: Validation Debt register + advancement gate + story-closure/restore-point decoupling; wire into check_docs.py (RD-023) | — | 🟡 | | |

## Relationship to the phase groupings

The phase groupings (P1–P4) still live in [`../RUNBOOK.md`](../RUNBOOK.md) with the
per-phase story tables, detail blocks, and validation gates. This execution-order
view is **complementary, not a replacement**: use the runbook for the authoritative
per-story detail and status, and use this file to read the same work in the order it
can actually be executed.
