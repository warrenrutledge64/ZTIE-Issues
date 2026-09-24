# Story 2.4R — CLOSED ✅ 2026-09-24 (cleared by its RD-058 remediation Story 2.4S)

> 2.4R is the RD-054 auditable-evidence backfill of the DYNAMIC (strace) lane. Six live
> attempts (1–6, sealed FAILs retained in this folder + the RUNBOOK register) proved the
> in-wrapper strace→SSM-stdout transport was structurally fragile for a hanging artifact, so
> the clearing path became Story **2.4S** (Fix B / RD-058: host uploads the `strace -o` per-PID
> files DIRECTLY to Forensic S3; the Lambda treats a timed-out SSM command with a complete S3
> trace as a successful capture). On 2.4S's SEALED PASS the durable, human-verified dynamic-lane
> evidence 2.4R was chartered to provide now exists, so this linked entry cleared with it (one
> work item).

## RD-054 markers for the 2.4R closure

- **Positive-exercise output:** captured via 2.4S — the Forensic artifact bucket held the host's
  per-PID strace files (`behavior.strace.762` 3084 B, `.763` 7685 B; real syscall/finding content
  of the known-behavior artifact) under `traces/beb6f4b5-bdcc-4466-984c-fdaa3256bcdd/`.
- **Proof-of-absence:** the crossed record carried NO effective-verdict field
  (`verdict|safe|approved|forward|malicious|pass_fail|clean` — **returns 0** on the 2.4S crossing);
  a hanging/behaving artifact is EVIDENCE, never a verdict, and no raw payload body crossed.
- **Human attestation:** **attested by warren (stakeholder), 2026-09-24**; independently adjudicated
  PASS by Gemini (split-brain, blind).
- **Provenance pins:** `intake_id: beb6f4b5-bdcc-4466-984c-fdaa3256bcdd`; code under test
  `commit c1e323c`.

## Authoritative record

The sealed PASS evidence lives at
[`../2.4S/attempt-5/EVIDENCE.md`](../2.4S/attempt-5/EVIDENCE.md). The 2.4R attempt-1..6 sealed-FAIL
records in this folder are retained as the RD-054 audit trail (do not retro-edit).
