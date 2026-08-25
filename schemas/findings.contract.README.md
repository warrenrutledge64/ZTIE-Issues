# `findings.contract.v1` — the detonation capability profile (DESIGN-ONLY / RD-017)

> **Status: design sketch, NOT implemented.** This is the second data contract that
> crosses the Forensic → Hub boundary. It is built in **Phase 2** (detonation +
> telemetry), mapped in **Phase 3** (correlation), and rendered in **Phase 4**
> (dashboard + report). This file + `findings.contract.v1.draft.json` exist so those
> phases are built to the right target. It does not run yet.

## Why it's separate from the intake contract

`intake-tracking.contract.v1` (Story 1.1R) is the *thin* front-door record — an
artifact arrived, here's its hash. At intake **nothing has been inspected**, so it is
intentionally small.

`findings.contract.v1` is the *rich* record produced **after detonation**: the answer
to "**what can this program do**" and "**which doorknob did it jiggle**." It crosses
the **same RD-013 gate** (allow-list, typed, bounded, fail-closed, verdict Hub-owned
and never imported, no raw payload/executable field) and **enriches the same
`intake_id` record** in the Hub — one artifact, one authoritative record that grows.

## The two views (RD-017) — one evidence set, two lenses

Everything derives from **process-attributed causal telemetry**: every network / file
/ syscall event is bound to its owning process (`pid`, `ppid`, `argv`, start offset)
and linked into a process tree. That is what lets an open port resolve all the way
down to the exact process, command, and syscall that opened it.

- **View 1 — `capabilities[]` (MITRE ATT&CK inventory):** "what this program CAN DO."
  Each entry is a demonstrated technique (`Txxxx[.yyy]`), the evidence that earned it
  (`evidence_refs` back into `processes`/`ports`/`network`/`file_ops`/`syscalls`),
  and **which engine mapped it** (`mapped_by`).
- **View 2 — `ports[]` (port-indexed):** scan across a port range and, per port, see
  its properties — number/proto, state (listen/connect/probe/closed), owning pid,
  first-seen, allow/deny disposition, and the technique(s) it maps to. Baseline OS
  ports are flagged `baseline` when the scope is `all`.

## Selectable behavior (your calls, recorded per detonation)

- **MITRE mapping engine (`detonation.mapping_engine`): `rules` | `nova` | `both`.**
  `both` (default) runs deterministic rules first, then Nova Pro fills gaps / adds
  confidence. Every mapped technique records `mapped_by` (`rules` or `nova`) so you
  can trust and tune the source. You choose per run — one, the other, or both.
- **Port-view scope (`detonation.port_scope`): `all` | `artifact-only`.** `all` shows
  everything with baseline OS ports flagged; `artifact-only` shows just what the
  detonated program opened/touched.

## Open design points (resolve when Phase 2 starts)

- **Capture mechanism** on the ephemeral EC2 (host-native SSM, no Docker) that yields
  per-pid syscall/network/file attribution — e.g. eBPF or auditd. RD-017 fixes the
  *requirement* (causal + process-attributed); the Phase 2 story picks the tool.
- **Rules source** for the `rules` engine (Sigma-style behavior→technique set).
- Final bounds/limits on the arrays (current `maxItems` are placeholders to keep the
  crossed record bounded per RD-013).
