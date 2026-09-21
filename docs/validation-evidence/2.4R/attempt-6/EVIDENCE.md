# Story 2.4R — Retained Validation Evidence (RD-054) — attempt 6 — **SEALED VERDICT: FAIL**

> **Sixth failed 2.4R validation. Fix A (RD-057 — process-group kill via `setsid` +
> stdio detach) did NOT resolve the SSM stdout pipe-lock hang.** Per the covenant, **2.4R
> stays 🟡**, OPEN on the Validation Debt Register, gate **ARMED**; nothing is flipped ✅.
> This FAIL MEETS THE 2.4S (RD-058) TRIGGER CONDITION — the durability follow-on is
> activated (⬜ DEFERRED → 🟡 in progress).

## Provenance (RD-054 marker ④)
- **Story:** 2.4R — RD-054 evidence backfill of the DYNAMIC lane (strace behavioral telemetry).
- **Attempt:** 6 (attempts 1–5 in the sibling folders / RUNBOOK register).
- **code under test:** the immutable target commit `1e44cc4d6504004a5e67973f5acdc7ca5b4e81f3`
  (RD-057 / Fix A: `setsid timeout --kill-after=GRACE BUDGET …` + traced-program stdio
  detach). Deploy-gate: the CODE-ASSET check (grep the live `capturespec.py` for
  `setsid timeout --kill-after=`) per `docs/session-briefs/story-2.4R-DEPLOY-VERIFY.md` STEP 4
  — NOT the (inert) env-var check.
- **artifact:** the known-behavior probe (blocking `/dev/tcp` connect in the egress-less VPC).
- **evidence adjudicated by:** the independent validator (Gemini), split-brain (RD-053).
- **accounts:** Forensic `360999005254` (detonation) / Hub `641628980935`.

## The raw facts (`aws ssm get-command-invocation`)
```
Status                : TimedOut
StatusDetails         : ExecutionTimedOut
ExecutionElapsedTime  : PT2M0.003S      (hit the exact 120 s SSM executionTimeout ceiling)
ResponseCode          : 137             (128 + 9 = SIGKILL of the wrapper tree)
StandardOutputContent : "=== ZTIE detonation: begin (instrumented) ===\n"   (banner ONLY)
StandardErrorContent  : (none material)
trace                 : NO trace data, NO closing footer/markers
```

## What is NEW vs attempts 4/5 (the diagnostic difference)
Attempts 4/5 returned `len(stdout)=46` with **no markers at all**. Attempt 6 captured the
`=== ZTIE detonation: begin (instrumented) ===` banner, which is emitted **immediately
before** the `setsid timeout … strace …` line. So the wrapper DID reach and start the
traced run under the Fix A construct — then still hung to 120 s / 137. The hang is
downstream of where Fix A acts.

## Root cause — NOT fully disambiguated by this output (recorded honestly)
The sealed output is consistent with EITHER of two mechanisms, and this evidence alone does
NOT distinguish them (they both yield `TimedOut`/137):
1. **Pipe still held (validator's read):** a detached grandchild / lingering fd keeps the
   SSM stdout pipe open, so the agent never receives EOF and block-waits to the ceiling.
2. **`setsid` moved the kill target out of reach:** putting the traced program in a NEW
   session may have prevented GNU `timeout` from delivering SIGTERM/SIGKILL to the traced
   child (a new-session child is not in `timeout`'s process group), so strace/artifact ran
   unbounded to the SSM ceiling.
Both are plausible; neither is asserted as fact here. (This mirrors the attempt-5 lesson:
do not over-attribute a WHY the raw output cannot prove.) The decisive follow-up would be a
process-tree / `timeout` exit-code check on a live host — but see below: it does not gate
the fix.

## Why this does not block progress — the fix is RD-058 (2.4S / Fix B)
The SSM stdout transport is structurally fragile for this workload regardless of which
mechanism above holds: a deeply-nested, deliberately-misbehaving artifact (real malware
behavior) can hang the command channel, and the trace is lost with it. **2.4S abandons
stdout as the payload transport** — the host writes `strace -o` per-PID files and uploads
them to Forensic S3 (`traces/{intake_id}/`) BEFORE the wrapper exits, and the Lambda reads
the trace from S3, not `StandardOutputContent`. The evidence then SURVIVES the hang.

### CRITICAL design consequence for 2.4S (surfaced by this run)
Fix B does **not** stop the SSM command from timing out — if the pipe stays held, the SSM
status is STILL `TimedOut`/137. Therefore 2.4S's Lambda logic MUST treat **"SSM `TimedOut`
BUT a complete trace exists in S3"** as a SUCCESSFUL capture (read the S3 trace, summarize
it, cross the bounded `behavior.contract.v1` record), NOT a failure. Without this, we would
have durable evidence in S3 and STILL record a FAIL. This "S3-first, SSM-status-secondary"
handling is the piece that actually lets Fix B close 2.4R; it was not in the merged RD-058
design sketch and is added to the 2.4S scope.

## Retained raw artifacts (in this folder)
| File | What it is |
|------|-----------|
| `raw-facts-attempt-6.txt` | The adjudicated raw `get-command-invocation` facts (Status/StatusDetails/ElapsedTime/ResponseCode/StandardOutputContent). |

## Human attestation (RD-054 marker ③-human)
> Adjudicated FAIL (Attempt 6) by the independent validator (Gemini), split-brain (RD-053),
> against the immutable target `1e44cc4d…`. SSM `TimedOut` / `ExecutionTimedOut`,
> ExecutionElapsedTime PT2M0.003S, ResponseCode 137, stdout = the begin banner only, no
> trace. Fix A (setsid + timeout --kill-after) did not resolve the stdout pipe-lock hang.

## Outcome
**2.4R = FAIL (attempt 6) → stays 🟡, OPEN on the register, gate ARMED (NOT ✅).** Fix A is
insufficient. The trigger for **2.4S (RD-058 / Fix B — abandon stdout, host→S3 direct trace
upload, S3-first read)** is MET; 2.4S moves ⬜ DEFERRED → 🟡. Fix B earns ✅ only on a fresh
recorded live pass of its crossing, with its own RD-054 evidence folder.
