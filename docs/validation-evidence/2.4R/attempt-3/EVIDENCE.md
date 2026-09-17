# Story 2.4R — Retained Validation Evidence (RD-054) — attempt 3 — **SEALED VERDICT: FAIL**

> **Third failed 2.4R validation, run against the v3 fix (PR #176, merged main `8cd0e2b`).**
> Same symptom as attempt 2 — `capture_status: capture_error`, `error_reason: "no
> behavioral trace emitted between capture markers"` — **even though the v3 fix dropped
> `%desc` (the attempt-2 prime suspect) and added a self-diagnosing no-trace path.** Two
> new facts from this run change the diagnosis. Per the covenant, **2.4R stays 🟡**, OPEN on
> the Validation Debt Register, gate **ARMED**; nothing is flipped ✅.

## Provenance (RD-054 marker ④)
- **Story:** 2.4R — RD-054 evidence backfill of the DYNAMIC lane (strace behavioral telemetry).
- **Attempt:** 3 (attempt 1 = top-level folder; attempt 2 = `../attempt-2/`).
- **intake_id:** `0ad74eb4-7290-4958-8837-58edb7c6e9a7` (from the terminal attestation).
- **code under test:** the v3 fix, PR #176 merged to main **`8cd0e2b`** (explicit
  `write`/`writev`/`pwrite64` syscalls, NO `%desc`; self-diagnosing no-trace path).
- **accounts:** Forensic `360999005254` (detonation) / Hub `641628980935` (tracking).
- **validated:** 2026-09-16, live, RD-053 split-brain; adjudicated **FAIL**. Attested by:
  warren (stakeholder), 2026-09-16.

## Retained raw artifacts (in this folder)
| File | What it is |
|------|-----------|
| `adversarial-2.4R-v3.sh` | The v3 known-behavior artifact (planted write buffer `ZTIE-EVIL-BUFFER-DATA-V3` + file ops + a real `bash` `/dev/tcp` connect intent). |
| `hub-behavior-2.4R-v3.json` | The Hub tracking item's `behavior` attribute projection (the crossed capture facts). |
| `terminal-attestation-2.4R-v3.txt` | The Forensic terminal (S3 `run.log` 404) + the stakeholder's attestation. |

## The two NEW facts (and why they matter)
1. **`capture_error` PERSISTED with `%desc` removed.** The v3 code traces with
   `-e trace=%file,%network,%process,%signal,write,writev,pwrite64` (no `%desc`). If `%desc`
   were the cause, v3 would have captured a trace. It did not → **the attempt-2 `%desc`
   root-cause theory is FALSIFIED.** (Recorded honestly: the executor's attempt-2 diagnosis
   was wrong, or at best incomplete.)
2. **The self-diagnostic marker DID NOT fire.** v3 added a no-trace fallback that, if strace
   wrote no per-PID file, emits a `ZTIE-CAPTURE-NO-TRACE-FILES; strace stderr follows:`
   marker + strace's stderr BETWEEN the trace markers. The crossed record shows neither that
   marker nor a strace reason — just the GENERIC `error_reason: "no behavioral trace emitted
   between capture markers"`. That generic reason is what the handler records when
   `slice_trace` finds **no usable trace between the markers at all** (empty or missing).

## Reassessed prime suspect — SSM inline-stdout 24 KB truncation (NOT strace, NOT %desc)
The behavioral trace is delivered back to the Lambda **inline in the SSM command's stdout**
and sliced out between markers:
- `lambdas/detonation/awsio.py::poll_command` returns `inv.get("StandardOutputContent", "")`.
- `send_command` uses `AWS-RunShellScript` with **no** `--output-s3-bucket-name` / `OutputS3*`.
- `handler.py` does `stdout = result.get("stdout")` then `capturespec.slice_trace(stdout)`.

**AWS truncates `GetCommandInvocation.StandardOutputContent` to 24,000 characters** (the
documented remedy is to send command output to S3 via `--output-s3-bucket-name`). The
capture command emits a LOT of stdout BEFORE the trace even begins — the `curl -v` artifact
fetch is verbose, plus the detonation begin/end banners — and then the trace itself. Once
the cumulative stdout crosses 24 KB, everything after is dropped. If the `=== ZTIE behavior
trace: begin ===` marker (and the emit that follows, INCLUDING the self-diagnostic) lands
past the 24 KB cut, then `slice_trace` sees no usable trace → generic `capture_error`, and
the self-diagnostic "does not fire" from the record's point of view **because it was
truncated away on-host, not because it didn't run.**

This explains EVERY symptom across attempts 2 and 3 that the strace theories did not:
- Why the generic reason (not the self-diagnostic) appears — both are past the 24 KB cut.
- Why the write-syscall / `%desc` changes made no difference — they change trace CONTENT,
  not the transport that is dropping it; adding syscalls only makes the trace BIGGER, more
  likely to be truncated.
- Why attempt-1 produced a (13 KB) trace but a bufferless one — a smaller artifact + fewer
  syscall classes fit closer to (but the write lines fell outside) the window.

**This is an INFRASTRUCTURE/TRANSPORT defect, not a strace-invocation defect.** The fix is
architectural: deliver the trace to Forensic S3 directly (SSM `--output-s3-bucket-name`, or
have the host write the trace to S3 and the Lambda read it from there) instead of shipping
it through the 24 KB-capped SSM inline stdout — so trace SIZE stops being a correctness gate.

## Confirming evidence still to fetch (before the 4th fix is built)
The full host output IS retained in Forensic S3 at
`runs/0ad74eb4-7290-4958-8837-58edb7c6e9a7/detonation-output.json` (NOT `run.log` — that key
never existed; that was a wrong-key fetch). Its `stdout` field is the exact
(24 KB-truncated) SSM output. **If the truncation theory is correct, that `stdout` will be
~24,000 chars and will NOT contain the `=== ZTIE behavior trace: begin/end ===` markers (or
will contain BEGIN but be cut before END).** The executor has requested this artifact to
CONFIRM the theory before building the fix — no more theory-driven fixes.

## Human attestation (RD-054 marker ③-human)
> Attested by: warren (stakeholder), 2026-09-16. I ran the 2.4R live validation against the
> v3 code (PR #176, main `8cd0e2b`), intake `0ad74eb4-7290-4958-8837-58edb7c6e9a7`. The Hub
> crossing succeeded but the capture FAILED (`capture_status: capture_error`), the
> self-diagnostic marker did NOT fire, and the S3 run log was not written (`run.log` 404).

## Outcome
**2.4R = FAIL (attempt 3) → stays 🟡, OPEN on the register, gate ARMED (NOT ✅).** The
`%desc` theory is falsified; the reassessed prime suspect is the 24 KB SSM inline-stdout
truncation of the trace transport. Next: (1) CONFIRM via `detonation-output.json` (stdout
length + marker presence); (2) if confirmed, the 4th fix is ARCHITECTURAL — move the trace
off the 24 KB SSM inline channel onto S3 — not another strace-flag tweak. A future PASS
requires a fresh live run of that fixed code with its own retained evidence.
