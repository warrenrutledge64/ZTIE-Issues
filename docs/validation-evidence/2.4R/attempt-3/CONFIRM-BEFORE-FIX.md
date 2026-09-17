# Story 2.4R — CONFIRM the root cause BEFORE building a 4th fix

> **Discipline note (carried forward from the attempt-3 handoff):** three fixes have
> shipped on strace-flag theories against a live-only symptom. **The next change must be
> confirm-then-fix, not guess-and-ship.** This file is the confirming-evidence request. It
> introduces **no code change**; 2.4R stays 🟡, OPEN on the Validation Debt Register, gate
> ARMED.

## What the code actually does (static analysis, this session)

The generic `capture_error` seen on attempts 2 and 3 —
`error_reason: "no behavioral trace emitted between capture markers"` — is emitted by
`handler.py` **only** when BOTH of these hold (see `_build_telemetry_envelopes`):

1. `capturespec.slice_trace(stdout)` returns an **empty / None** trace, AND
2. `capturespec.no_trace_diagnostic(trace)` returns `None` (the self-diagnostic did not fire).

`slice_trace` (in `capturespec.py`) behaves as:

| stdout condition | returns | handler path |
|---|---|---|
| BEGIN marker **absent** | `None` | generic `capture_error` ✅ (matches symptom) |
| BEGIN present, END **absent** (cut mid-trace) | `text[start:]` = a **non-empty tail** | `capture_status = captured` (`trace_truncated`), **NOT** the observed symptom |
| BEGIN + END present, nothing between | `""` (empty) | generic `capture_error` ✅ (matches symptom) |
| BEGIN + END present, diagnostic marker between | the stderr text | `capture_error` **with a strace reason** (self-diagnostic fired) |

### Why this refines (and partially challenges) the attempt-3 "SSM 24 KB truncation" theory

The attempt-3 theory was: verbose pre-trace output pushes the trace **and its markers** past
AWS's 24,000-char `StandardOutputContent` cap, so `slice_trace` sees nothing.

But the rendered host command list shows almost **nothing** reaches the SSM **stdout** channel
before the `=== ZTIE behavior trace: begin ===` marker:

- `curl ... -v ... 2> /tmp/ztie/curl.log` — curl's verbose output goes to a **file**, not stdout.
- `strace ... -o /tmp/ztie/behavior.strace ... 2> /tmp/ztie/behavior-strace-stderr.log` — the
  trace goes to per-PID **files** and strace's stderr to a **file**, not stdout.
- The 2.4R probe (`adversarial-2.4R-v3.sh`) is **quiet** (a `printf` to a file, `touch`/`rm`,
  one `/dev/tcp` connect) — it emits essentially nothing to stdout.

So before the BEGIN marker, stdout holds only two short banners. **The BEGIN marker lands
very early — well within 24 KB.** If SSM truncation happened, it would cut the **END** marker
(or mid-trace), giving BEGIN-without-END → a **non-empty best-effort tail** → recorded as
`captured` (`trace_truncated=true`), **not** the empty generic `capture_error` we observed.

**Conclusion:** pure SSM-truncation-of-the-markers does **not** cleanly explain the observed
*empty* `capture_error` for this quiet probe. The most code-consistent hypothesis is:

> **Both markers are present, with nothing (usable) between them, AND the self-diagnostic
> `else` branch did not emit its `ZTIE-CAPTURE-NO-TRACE-FILES` marker.**

That points at the **`emit_or_diag` shell block** or the **strace run producing no per-PID
files in a way the `ls` guard still saw as present** — i.e. a host/shell-behavior question,
not an SSM-transport question. Only the raw bytes decide it. **Do not build a fix on either
theory until the evidence below is in hand.**

## The confirming artifact

`handler.py` writes the FULL command log to Forensic S3 with `"stdout": stdout`, where
`stdout` is **exactly** the (possibly-truncated) `StandardOutputContent` that `slice_trace`
consumed. So this file IS the Lambda's own input — it discriminates every hypothesis above.

- **Account:** Forensic `360999005254`
- **Bucket:** the ZTIE Forensic artifact bucket (the one Story 2.3/2.4 write `runs/` under —
  the same bucket in the detonation stack's `ARTIFACT_BUCKET` / output env).
- **Key:** `runs/0ad74eb4-7290-4958-8837-58edb7c6e9a7/detonation-output.json`
  (NOT `run.log` — that key never existed.)

## Exact commands (run from a Forensic-authed CloudShell — split-brain Part B)

```bash
# 0. Confirm you are in the FORENSIC account (360999005254), NOT the Hub.
aws sts get-caller-identity --query Account --output text   # expect 360999005254

# 1. Resolve the Forensic artifact bucket name from the detonation Lambda's env
#    (avoids guessing the bucket name). Adjust the function name if different.
FN=$(aws lambda list-functions \
  --query "Functions[?contains(FunctionName,'Detonation')].FunctionName | [0]" \
  --output text)
echo "detonation fn: $FN"
BUCKET=$(aws lambda get-function-configuration --function-name "$FN" \
  --query "Environment.Variables.ARTIFACT_BUCKET" --output text)
echo "artifact bucket: $BUCKET"

# 2. Pull the exact file the Lambda's slice_trace consumed.
KEY="runs/0ad74eb4-7290-4958-8837-58edb7c6e9a7/detonation-output.json"
aws s3api get-object --bucket "$BUCKET" --key "$KEY" /tmp/deto.json
```

Then analyze it **with Python** (per the standing "Python by default" preference) so the
answer is unambiguous and copy-pasteable back into the repo:

```bash
python3 - <<'PY'
import json
d = json.load(open("/tmp/deto.json"))
out = d.get("stdout") or ""
err = d.get("stderr") or ""
B = "=== ZTIE behavior trace: begin ==="
E = "=== ZTIE behavior trace: end ==="
DIAG = "ZTIE-CAPTURE-NO-TRACE-FILES; strace stderr follows:"
bi, ei = out.find(B), out.find(E)
print("ssm_status      :", d.get("ssm_status"), "exit_code:", d.get("exit_code"))
print("len(stdout)     :", len(out), " (SSM inline cap is ~24000 chars)")
print("len(stderr)     :", len(err))
print("BEGIN marker at :", bi)
print("END   marker at :", ei)
print("DIAG  marker in :", DIAG in out)
print("TOOL_UNAVAILABLE:", "ZTIE-CAPTURE-TOOL-UNAVAILABLE" in out)
print("trace-file hdrs :", out.count("=== ZTIE trace file: "))
if bi != -1:
    seg = out[bi+len(B): ei if ei != -1 else None]
    print("chars between markers:", len(seg))
    print("---- first 600 chars between markers ----")
    print(seg[:600])
print("---- last 400 chars of stdout ----")
print(out[-400:])
print("==== stderr (StandardErrorContent — what strace/host reported) ====")
print(err[:2000])
PY
```

## How each result maps to a root cause (decision table)

| Observation | Root cause | The fix |
|---|---|---|
| `len(stdout)` ≈ 24000 **and** END marker missing (`ei == -1`) **and** BEGIN present | **SSM 24 KB truncation** (attempt-3 theory) — confirmed | **Architectural:** stop shipping the trace through SSM inline stdout. Have the host write the trace to Forensic S3 directly (presigned PUT, mirroring the artifact GET), and the Lambda reads it from S3. Trace size stops being a correctness gate. Keeps RD-009 (full trace stays in Forensic). |
| BEGIN **and** END present, **0 chars between**, DIAG marker **absent**, `len(stdout)` well under 24000 | **Host/shell logic** — strace produced no per-PID files AND the `emit_or_diag` else-branch did not fire (e.g. the `ls …strace.*` glob guard evaluated unexpectedly, or `set -u`/`errexit` aborted the block) | Fix the shell branch, not the transport. `stderr` + strace-stderr content tell us why strace wrote nothing. |
| BEGIN present, END missing, but a **non-empty** tail between | Would have recorded `captured(truncated)`, so this contradicts the sealed FAIL — re-check the crossed record | Re-examine; do not fix blind. |
| DIAG marker **present** in stdout | strace ran but wrote no per-PID file; `stderr`/the diag text names the reason (rejected `-e`, permission, etc.) | Fix per the named strace reason. |

**Whatever the evidence shows, the 4th change is built to match it — and then validated by a
fresh live run with its own retained evidence (the covenant: a story is not ✅ until a
recorded live pass of the FINAL code).**

---
*Authored this session as the confirm-then-fix gate for attempt 4. No code changed; 2.4R
remains 🟡 / OPEN / gate ARMED.*
