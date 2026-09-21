# Story 2.4R — Retained Validation Evidence (RD-054) — attempt 5 — **SEALED VERDICT: FAIL**

> **Fifth failed 2.4R validation. The 2.4R4 on-host `timeout` fix did NOT protect the
> wrapper — Attempt 5 reproduced Attempt 4 byte-for-byte.** Per the covenant, **2.4R
> stays 🟡**, OPEN on the Validation Debt Register, gate **ARMED**; nothing is flipped ✅.
> The `timeout -k 5 75 strace …` construct failed to return control to the wrapper
> script; the run still hung until the 120 s SSM `executionTimeout` SIGKILLed the whole
> wrapper before the emit block ran, and the trace was lost entirely.

## Provenance (RD-054 marker ④)
- **Story:** 2.4R — RD-054 evidence backfill of the DYNAMIC lane (strace behavioral telemetry).
- **Attempt:** 5 (attempt 1 = top-level folder; 2 = `../attempt-2/`; 3 = `../attempt-3/`; 4 = `../attempt-4/`).
- **code under test:** commit `9cd4102` (2.4R4 on-host-timeout fix), pinned as the immutable
  validation target (`main` tip `03602939…`); the fix WAS deployed and its live env WAS
  confirmed present before this run (`ARTIFACT_EXEC_TIMEOUT_S=75`, `ARTIFACT_EXEC_KILL_GRACE_S=5`).
- **artifact:** the known-behavior probe whose last op is `exec 3<>/dev/tcp/93.184.216.34/443 || true`.
- **evidence adjudicated by:** the independent validator (Gemini), split-brain (RD-053).
- **accounts:** Forensic `360999005254` (detonation + artifact bucket) / Hub `641628980935`.

## The raw facts (identical to attempt 4 — the fix changed nothing observable)
```
ssm_status      : TimedOut   exit_code: 137   (137 = 128 + 9 = SIGKILL)
len(stdout)     : 46
len(stderr)     : 0
BEGIN marker    : absent
END   marker    : absent
ZTIE-ARTIFACT-TIMED-OUT marker : absent
trace file (S3) : 404 Not Found
```

## Conclusion (validator-sealed)
The 75 s GNU `timeout` failed to return control to the wrapper script. Execution still
hung until the 120 s SSM `executionTimeout` triggered and SIGKILLed everything, so the
emit block never ran and the trace was lost entirely. **The attempt-4 fix (bound the
artifact run with `timeout -k GRACE BUDGET` so the wrapper survives) is FALSIFIED as
deployed** — `timeout` did not deliver a timely, effective kill that returned control.

## Root-cause investigation (why `timeout -k 5 75 strace …` did not release the wrapper)
Directed lines of inquiry for the attempt-6 fix (NOT sealed conclusions — the raw run
shows the SYMPTOM, len(stdout)=46 with no markers; the mechanism below is the analysis to
confirm against a fresh instrumented run):

1. **`timeout` bounds `strace`, not the hung grandchild — and the artifact's real work is
   a re-exec subtree.** In `_instrumented_exec_commands` the construct is
   `timeout -k 5 75 strace -ff … /bin/sh <artifact>`. `timeout` runs `strace` as its
   child and, at BUDGET, sends the signal **to `strace` only** (a single PID, not the
   process group by default). The artifact's blocking `connect()` lives in a
   **grandchild** (`strace` → `/bin/sh` → the artifact's `exec`). If `strace` does not
   propagate the signal to the traced subtree, killing `strace` can leave the grandchild
   blocked, holding the SSM stdout pipe open — so the wrapper never regains control and
   SSM SIGKILLs the whole tree at 120 s. **Fix direction:** `timeout --signal=KILL` is
   insufficient across a subtree; use a process-group kill — run the artifact in its own
   group and `timeout -k` a `setsid`/`kill -- -<pgid>` teardown, OR `strace -f` with a
   tracer that forwards fatal signals, OR bound with `setsid timeout …` so the whole
   session is signaled.

2. **A process blocked in `connect()` on a held fd may not die on SIGTERM, and the KILL
   grace targets the wrong PID.** `timeout -k 5 75` sends SIGTERM at 75 s then SIGKILL at
   80 s **to `strace`**. If `strace` is killed but the traced `connect()` grandchild is
   not in `strace`'s delivered signal set, the grandchild survives the KILL. **Fix
   direction:** ensure the KILL reaches the artifact PID/PGID, not just the tracer.

3. **Lingering file descriptor keeps the SSM stdout pipe open (the 46-byte tell).**
   `len(stdout)=46` with NO `begin`/`end`/timeout markers means the wrapper printed only
   its first banner-ish bytes and then **blocked before the emit block** — consistent with
   a surviving grandchild inheriting and holding the stdout pipe fd, so SSM's reader never
   sees EOF and the command sits until `executionTimeout`. **Fix direction:** run the
   artifact with stdout/stderr redirected to on-host files (not the inherited SSM pipe) so
   a surviving child cannot hold the command pipe open; the wrapper reads the files and
   emits, and control returns even if a child lingers.

4. **Deliver the trace out-of-band so trace survival does not depend on the wrapper
   finishing.** Regardless of the signal mechanics, the current design loses EVERYTHING if
   the wrapper is killed. **Fix direction (architectural, attempt 6):** `strace -o` already
   writes per-PID files on the host; have the host **upload those files to Forensic S3
   directly** (SSM `--output-s3-bucket-name`, or a host `aws s3 cp` in a trap) the moment
   strace exits, so a later wrapper kill cannot erase the trace. This decouples trace
   survival from the fragile in-wrapper emit block that has now failed five times.

## Retained raw artifacts (in this folder)
| File | What it is |
|------|-----------|
| `raw-facts-attempt-5.txt` | The adjudicated raw facts (ssm_status/exit_code/len/marker/S3-404 probe) for attempt 5. |

## Human attestation (RD-054 marker ③-human)
> Adjudicated FAIL (Attempt 5) by the independent validator (Gemini), split-brain (RD-053).
> Code under test = deployed `9cd4102` with live env confirmed (`ARTIFACT_EXEC_TIMEOUT_S=75`
> / `ARTIFACT_EXEC_KILL_GRACE_S=5`). Result identical to Attempt 4: `TimedOut` / exit 137 /
> len(stdout)=46 / no markers / trace 404. The on-host `timeout` did not return control to
> the wrapper before the 120 s SSM executionTimeout SIGKILLed it.

## Outcome
**2.4R = FAIL (attempt 5) → stays 🟡, OPEN on the register, gate ARMED (NOT ✅).** The
attempt-4 on-host-`timeout` fix is falsified as deployed. A PASS requires a fresh live run
of a NEW fix (attempt 6) whose design ensures control returns to the wrapper (process-group
kill / detached stdio) AND, preferably, delivers the trace out-of-band so trace survival no
longer depends on the wrapper surviving.
