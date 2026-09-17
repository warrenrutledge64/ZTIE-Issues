# Story 2.4R — Retained Validation Evidence (RD-054) — attempt 4 — **SEALED VERDICT: FAIL**

> **Fourth failed 2.4R validation. The confirm-then-fix gate finally produced the raw
> facts, and they FALSIFIED the attempt-3 SSM-truncation theory too.** The real root cause
> is a **hanging artifact that timed out the SSM wrapper (SIGKILL/137) before the trace-emit
> block ran** — an architectural blind spot, not a strace-flag or transport-size issue. Per
> the covenant, **2.4R stays 🟡**, OPEN on the Validation Debt Register, gate **ARMED**;
> nothing is flipped ✅. This session BUILT the 2.4R4 fix (fix-then-validate-once); it is
> unvalidated until a fresh live run of the FINAL code with its own retained evidence.

## Provenance (RD-054 marker ④)
- **Story:** 2.4R — RD-054 evidence backfill of the DYNAMIC lane (strace behavioral telemetry).
- **Attempt:** 4 (attempt 1 = top-level folder; 2 = `../attempt-2/`; 3 = `../attempt-3/`).
- **intake_id:** `0ad74eb4-7290-4958-8837-58edb7c6e9a7` (the same run adjudicated in attempt 3;
  the retained `detonation-output.json` was fetched and re-read to CONFIRM the cause).
- **evidence adjudicated by:** the independent validator (Gemini), split-brain (RD-053).
- **accounts:** Forensic `360999005254` (detonation + artifact bucket) / Hub `641628980935`.
- **confirm gate:** PR #178 — `../attempt-3/CONFIRM-BEFORE-FIX.md` (the fetch + decision table).

## The raw facts (from `runs/0ad74eb4-…/detonation-output.json`)
```
ssm_status      : TimedOut   exit_code: 137   (137 = 128 + 9 = SIGKILL)
len(stdout)     : 46         (SSM inline cap is ~24000 — nowhere near it)
len(stderr)     : 0
BEGIN marker at : -1
END   marker at : -1
DIAG  marker in : False
trace-file hdrs : 0
planted buffer in stdout : 0 (clean)
```

## Confirmed root cause — a hanging artifact SIGKILLed the whole wrapper
The known-behavior probe's last operation is:
```sh
exec 3<>/dev/tcp/93.184.216.34/443 || true
```
In the isolated Forensic VPC there is **no egress**, so the bash `/dev/tcp` connect BLOCKS
waiting for a SYN-ACK that never arrives. `strace`, following the artifact, blocked with it.
After the SSM command's `executionTimeout` (handler `EXEC_TIMEOUT_S`, default **120 s** —
`lambdas/detonation/handler.py`) elapsed, the SSM agent **SIGKILLed the entire wrapper
script** (exit 137). Because the whole wrapper died mid-run, execution NEVER reached the
trace-emit block at the bottom of `build_capture_run_commands`: the
`=== ZTIE behavior trace: begin/end ===` markers and the per-PID concat loop never ran, the
on-host `strace -o` per-PID files were lost with the host at its hard TTL, and the Hub's
`capture_error` / "no behavioral trace emitted between capture markers" was the **correct
downstream report of an upstream hang**.

### Why this falsifies every earlier theory
- **Not truncation (attempt 3):** `len(stdout)=46`. Nothing was cut — there were only 46
  bytes. The `begin` marker was never printed at all (offset −1), not "printed then dropped."
- **Not `%desc` (attempt 2) / not the shell branch:** strace never reached the point of
  writing (or failing to write) a trace file; `len(stderr)=0` — it wasn't a strace error, it
  was strace being killed mid-trace along with everything else.

## Architectural finding
The capture wrapper was **brittle to a hanging/blocking/sleeping artifact** — which is a
*real malware behavior* (a C2 connect, a daemon that never exits, a deliberate `sleep`). Any
such artifact would run until the SSM `executionTimeout` SIGKILLed the wrapper, losing the
entire trace and leaving no on-host record. The dynamic lane must bound the *artifact* run
itself so the *wrapper* always survives to harvest whatever was captured.

## Fix built this session — 2.4R4 (fix-then-validate-once)
Bound the artifact run on-host with GNU `timeout -k GRACE BUDGET` (pre-baked on the golden
AMI, RD-030) around the strace/artifact invocation:

- `capturespec.py`:
  - New constants `ARTIFACT_EXEC_TIMEOUT_S` (default **75 s**), `ARTIFACT_EXEC_KILL_GRACE_S`
    (default **5 s**), `ARTIFACT_TIMEOUT_RC = 124`, marker `ARTIFACT_TIMED_OUT_MARKER =
    "ZTIE-ARTIFACT-TIMED-OUT"`.
  - BOTH strace invocations (shebang + via-`/bin/sh`) **and** both uninstrumented
    invocations are now wrapped: `timeout -k 5 75 strace … <artifact>`. `timeout` sends
    SIGTERM at BUDGET, SIGKILL at BUDGET+GRACE if the process ignores TERM (a process blocked
    in `connect()` with a held fd usually needs the KILL). Killing `timeout`'s child
    terminates the traced artifact, and strace flushes its `-o` per-PID files on exit.
  - The wrapper emits `ZTIE-ARTIFACT-TIMED-OUT` (OUTSIDE the trace markers, gated on
    `__ZTIE_RC == 124`) so the orchestrator can record capture health honestly; `__ZTIE_RC`
    is still captured and `exit $__ZTIE_RC` preserved (the 2.3 outcome mapping is unchanged).
  - New pure helper `artifact_timed_out(stdout)`.
- `handler.py` (`_build_telemetry_envelopes`): after `slice_trace`, compute
  `timed_out = capturespec.artifact_timed_out(stdout)`. A time-bounded run with a partial
  trace crosses as `capture_status: captured` + `trace_truncated: true` + a timeout note; a
  time-bounded run with no trace at all crosses as `capture_status: capture_error` with a
  timeout-specific `error_reason`. **Never a verdict** — a hanging artifact is EVIDENCE.
- `infra/lib/ztie-detonation-stack.ts`: `ARTIFACT_EXEC_TIMEOUT_S`/`ARTIFACT_EXEC_KILL_GRACE_S`
  env (75/5) with a doc comment coupling them to the 120 s SSM ceiling (tunable, RD-015).

**No contract change:** the `behavior.contract.v1` `capture_status` enum
(`captured/tool_unavailable/capture_error/not_run`) is unchanged; the honest states above use
existing fields (`trace_truncated`, `error_reason`).

### Budget hierarchy (why the wrapper now survives)
`ARTIFACT_EXEC_TIMEOUT_S (75) + ARTIFACT_EXEC_KILL_GRACE_S (5) = 80 s` ≪ `EXEC_TIMEOUT_S (120 s)`
SSM ceiling, leaving ~40 s for the fetch (`curl --max-time 60`), strace startup, `sync`, and
the emit loop. So `timeout` fires FIRST and the SSM agent never SIGKILLs the wrapper.

## Offline proof (INTEGRATIONS_ONLY build sandbox)
- `test_capturespec` **32 OK** — includes a new `TestArtifactExecutionTimeout` class (7 tests):
  both strace invocations wrapped; uninstrumented path bounded; budget+grace < 120; marker
  gated on rc 124 and emitted before the trace-begin marker; emit block after the bounded run;
  `artifact_timed_out` detection; `__ZTIE_RC` preserved.
- Full detonation suite **157 OK** (18 jsonschema-live skips — jsonschema not installable offline).
- `py_compile` OK; `ruff` clean; `tsc --noEmit` = existing missing-aws-cdk-lib family only
  (TS2304/2307/2339/2353/2591), **no new error type**; `prettier` clean; `gen_contracts.py`
  no drift.
- **Behavioral proof (the end-to-end proof prior attempts lacked):** a stand-in `fake_strace`
  that writes a per-PID trace file (incl. a `connect(…443…) <unfinished …>` line) then
  `sleep 600` was run through the exact wrapper structure with a 3 s budget. Result: the
  child was killed at 3 s (not 600), `ZTIE-ARTIFACT-TIMED-OUT` fired, and the **wrapper
  SURVIVED** to print the BEGIN/END markers and ship the captured per-PID file. This proves
  the core claim: a hanging artifact now yields **partial evidence + an honest health note**,
  not an empty `capture_error` and not a lost run.

## Retained raw artifacts (in this folder)
| File | What it is |
|------|-----------|
| `detonation-output-probe.txt` | The adjudicated raw facts from `runs/0ad74eb4-…/detonation-output.json` (the ssm_status/exit_code/len/marker probe). |
| `adversarial-2.4R-v3.sh` | The known-behavior artifact whose blocking `/dev/tcp` connect exposed the hang (carried from attempt 3 for provenance). |
| `../attempt-3/CONFIRM-BEFORE-FIX.md` | The confirm-then-fix gate that produced this evidence (PR #178). |

## Human attestation (RD-054 marker ③-human)
> Adjudicated FAIL by the independent validator (Gemini), split-brain (RD-053), 2026-09-17,
> from the retained `detonation-output.json` (ssm_status=TimedOut, exit_code=137,
> len(stdout)=46, no trace markers). Root cause: the artifact's `/dev/tcp` connect hung the
> traced run until the 120 s SSM executionTimeout SIGKILLed the whole wrapper before the emit
> block ran.

## Outcome
**2.4R = FAIL (attempt 4) → stays 🟡, OPEN on the register, gate ARMED (NOT ✅).** All three
prior theories are falsified; the confirmed cause is a hanging-artifact timeout that killed
the wrapper. The 2.4R4 fix (on-host `timeout` so the wrapper survives) is BUILT and
offline+behaviorally proven, but a PASS requires a **fresh live run of the FIXED code** with
its own retained evidence — see `LIVE-RUNBOOK.md` in this folder.
