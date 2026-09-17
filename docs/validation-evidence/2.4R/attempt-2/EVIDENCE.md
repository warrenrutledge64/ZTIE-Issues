# Story 2.4R — Retained Validation Evidence (RD-054) — attempt 2 — **SEALED VERDICT: FAIL**

> **This folder is the audit trail of the SECOND failed 2.4R validation, run against the
> FIXED code from PR #175 (merged to main `bdc7a68`).** The rework fixed the attempt-1
> defects (missing `%desc` write capture, whole-concat truncation) but the live run of the
> fixed code produced a NEW, TOTAL failure mode: `capture_status: capture_error` /
> `error_reason: "no behavioral trace emitted between capture markers"` — strace produced
> NO trace at all. Per the covenant, **Story 2.4R stays 🟡 (In Progress)**, remains on the
> Validation Debt Register, gate stays **ARMED**; nothing is flipped ✅.

## Provenance (RD-054 marker ④)
- **Story:** 2.4R — RD-054 evidence backfill of the DYNAMIC lane (strace behavioral telemetry).
- **Attempt:** 2 (attempt 1 = the top-level `docs/validation-evidence/2.4R/` folder, a
  different FAIL — the write buffer was missed because `%desc` was not traced).
- **intake_id:** `528c0ad1-8285-46fa-8327-48f424d3ca4d` (from the terminal attestation).
- **code under test:** the FIXED dynamic lane, PR #175 merged to main **`bdc7a68`**
  (the `%desc` write-capture + per-PID cap rework).
- **accounts:** Forensic `360999005254` (detonation) / Hub `641628980935` (tracking).
- **validated:** 2026-09-16, live, under the RD-053 split-brain protocol; independently
  adjudicated **FAIL**. Attested by: warren (stakeholder), 2026-09-16.

## Retained raw artifacts (in this folder)
| File | What it is |
|------|-----------|
| `adversarial.sh` | The known-behavior artifact submitted (planted write buffer + file ops + a real `bash` `/dev/tcp` connect intent). |
| `hub-behavior-2.4R.json` | The Hub tracking item's `behavior` attribute projection for this intake (the crossed capture facts). |
| `terminal-attestation-2.4R.txt` | The Forensic terminal showing the S3 `runs/<intake>/run.log` is a 404 (never written) + the stakeholder's attestation. |

## Sealed verdict — FAIL (transcribed; not re-judged by the executor)
The live run of the fixed code FAILED: `capture_status: capture_error`. The dynamic lane is
a security boundary and a `capture_error` / no-trace result is NOT a pass (it is strictly
worse than INCONCLUSIVE — the capture did not fire at all). 2.4R remains 🟡.

## What the raw evidence shows

### The capture produced NO trace (the crossed `behavior.capture`)
```
lane                        = dynamic_detonation
capture_tool                = strace            <- strace WAS present (not tool_unavailable)
capture_status              = capture_error
capture_started_offset_ms   = 65551
capture_stopped_offset_ms   = 191500            <- ~126 s capture window: the run DID execute
error_reason                = "no behavioral trace emitted between capture markers"
```
There are NO `syscalls` / `network` / `filesystem` summary sub-objects — because there was
no trace to summarize. The handler's `capture_error` branch fired: `capturespec.slice_trace`
found the BEGIN/END markers but **nothing (or only whitespace) between them**, and
`strace` was detected (so it is NOT `tool_unavailable`).

### The S3 run log was never written
```
$ aws s3 cp "s3://$BKT/runs/528c0ad1-8285-46fa-8327-48f424d3ca4d/run.log" /tmp/run.log
fatal error: (404) ... Key "runs/528c0ad1-.../run.log" does not exist
```
So there is no host-side command output retained to inspect WHY strace emitted nothing —
which is itself a finding (the `capture_error` path is currently BLIND to the strace stderr).

## Interpreting the failure mode (empty-between-markers)
`slice_trace` returns an empty trace when the on-host emit between the BEGIN/END markers
produced no bytes. That emit is `for __f in $(ls /tmp/ztie/behavior.strace.* …); do … done`.
An empty result means **`ls` matched no per-PID trace files** — i.e. `strace -ff -o
/tmp/ztie/behavior.strace …` wrote NO per-PID files. strace writes no `-ff` files when it
fails to start/attach (e.g. it rejects an option/argument and exits before tracing). The
run still took ~126 s (the artifact itself ran), consistent with strace erroring out while
the `if…then…fi` and the artifact still executed.

**Prime suspect (a defect introduced by the PR #175 rework):** the added `%desc` trace
group in `-e trace=%file,%desc,%network,%process,%signal` is rejected by the golden AMI's
strace build (or the combined `-e trace=` list is malformed for that version), so strace
exits without writing any per-PID file. This is the "offline can't catch it" class: the
offline tests only assert the command STRING contains `%desc`; only a real strace on the
AMI proves the option is accepted. **Compounding defect:** the `capture_error` path discards
strace's stderr and no `run.log` was written, so the run is blind to the exact strace error.

## Human attestation (RD-054 marker ③-human)
> Attested by: warren (stakeholder), 2026-09-16. I ran the 2.4R live validation against the
> fixed code (PR #175, main `bdc7a68`), intake `528c0ad1-8285-46fa-8327-48f424d3ca4d`. The
> Hub crossing succeeded but the capture FAILED (`capture_status: capture_error`,
> `error_reason: "no behavioral trace emitted between capture markers"`), and the S3 run log
> was not written (404). No behavioral trace was produced.

## Outcome
**2.4R = FAIL (attempt 2) → stays 🟡, remains OPEN on the Validation Debt Register, gate
ARMED (NOT ✅).** The rework must be REWORKED again (fix-then-validate-once): (1) make the
strace trace-group set robust so a rejected group cannot silently zero the whole capture —
prefer an explicit, widely-supported syscall list (or a fallback if a group is rejected);
(2) make the `capture_error` path SELF-DIAGNOSING — surface the strace stderr / a diagnostic
into the emitted output (and ensure the run log is written) so a no-trace run is never blind
to WHY; (3) re-validate live, confirming the planted write buffer now appears in the raw
trace. A future PASS requires a fresh live run of the re-fixed code with its own retained
evidence.
