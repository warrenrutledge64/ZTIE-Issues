# Story 2.4S attempt-4 — CONFIRM-BEFORE-FIX probe finding (2026-09-24)

> **This is EVIDENCE, not a status change.** 2.4S and 2.4R remain 🟡; the advancement gate
> stays ARMED. A story flips ✅ ONLY on the independent validator's sealed live pass of the
> clean final code (RD-055) — not on this executor-run diagnostic. This record corrects the
> attempt-4 root-cause attribution and states plainly what was proven.

## What was run

Per the covenant §4 confirm-before-fix gate, a TEMPORARY in-wrapper probe (branch
`diag/story-2.4S-upload-probe`, PR #205, **closed UNMERGED**) was spliced into
`capturespec.build_trace_upload_commands` right after the `TRACE-UPLOAD-BEGIN` echo and
BEFORE the untouched production loop/sentinel. It mirrored the production per-PID `aws s3 cp`
loop + the stdin `_UPLOAD_COMPLETE` sentinel EXACTLY, but with stderr surfaced + rc echoed
(no `2>>errlog`, no `|| true`), under its own `ZTIE-PROBE-BEGIN/END` markers.

Deploy discipline (the thing missing in attempt 4): the LIVE code asset was verified BEFORE
the run — `unzip -p <live-lambda>.zip capturespec.py | grep -c ZTIE-PROBE-BEGIN` = **2** — so
this run provably exercised the intended code, not a stale asset.

Run: intake `beb6f4b5-bdcc-4466-984c-fdaa3256bcdd` (payload `hang_probe.sh` = `#!/bin/sh` +
`sleep 140`, a genuine hang-past-timeout), Forensic `360999005254`.

## What it PROVED (raw evidence)

1. **Files present at upload time** — `PROBE-GLOB-COUNT: 2`
   (`/tmp/ztie/behavior.strace.762` 3084 B, `.763` 7685 B). Falsifies the
   "glob empty at upload time" candidate.
2. **The copies RAN and SUCCEEDED** — `per_pid_cp_rc=0` for both files (each logging
   `upload: … to s3://…/traces/beb6f4b5-…/behavior.strace.<pid>`), and `sentinel_cp_rc=0`.
   Falsifies the "IAM/endpoint/abs-path" and "SIGKILL-group teardown skips the block"
   candidates — the block ran to completion in the surviving wrapper.
3. **The objects LANDED** — `aws s3api list-objects-v2 --prefix traces/beb6f4b5-…/`:
   `behavior.strace.762` (3084), `behavior.strace.763` (7685), `_UPLOAD_COMPLETE` (8),
   plus the Lambda's own `behavior-trace.txt` (10947).
4. **The Lambda READ the S3 trace and treated Failed-SSM-but-complete-trace as SUCCESS** —
   the authoritative log line:
   `using S3-uploaded behavioral trace for intake_id=beb6f4b5-… (objects=2 complete=True ssm_status=Failed)`
   on a run where `ssm_status=Failed`, `exit_code=124` (GNU `timeout`), with
   `ZTIE-ARTIFACT-TIMED-OUT` in the wrapper stdout. This is exactly the RD-058 intent.

Note: the probe's own `PROBE-S3-LIST` step returned `AccessDenied` on `s3:ListBucket` — that
is CORRECT least-privilege (the `DetonationInstanceRole` has `s3:PutObject` on `traces/*`, NOT
`ListBucket`); it was a flaw in the probe's own list call, NOT an upload failure. The uploads
returned rc=0 and the objects are present (confirmed by an admin-authed list).

## Corrected root-cause attribution for attempt 4 (scoped honestly)

**Fix B (RD-058) — host→S3 direct upload + S3-first read + "Failed-SSM-but-complete-S3-trace
= successful capture" — WORKS end-to-end on current `main` (the code with PRs
#195/#198/#199/#200).** There is **no code defect** in the upload/read/record path.

The attempt-4 SEALED FAIL (empty `ZTIE-UPLOAD-DIAG` block, no S3 objects) is therefore **most
consistent with a DEPLOY-GAP, not a code defect**: the live Lambda most likely ran pre-#200
code, so the wrapper crashed on the `set -u` unbound `__ZTIE_RC` (exit 2 / SIGKILL) BEFORE
reaching the upload block — which produces exactly attempt-4's signature (no upload ran, so no
objects and no stderr → empty diag). This is the recurring "green `UPDATE_COMPLETE` over stale
code" class (cf. Story 2.5; attempt-5's H1/H2 honesty correction).

HONEST LIMIT (attempt-5 over-attribution lesson): the ephemeral attempt-4 host is gone
(RD-012), so H1 (code genuinely failed) vs H2 (stale/pre-#200 asset ran) for **that** run
cannot be retro-proven. What IS proven: the current code, verified-live, works. The attempt-4
register FAIL stands as the sealed record of that run; this addendum corrects the *why* and
records that the code is not defective.

Also note: the empty `ZTIE-UPLOAD-DIAG` block was mis-read at attempt-4 as a failure signal.
On a CLEAN upload the diag block is EMPTY BY DESIGN (the copies write no stderr on success) —
so "empty diag" alone is a success signal, not a failure one; the failure at attempt 4 was
the ABSENCE of the deposited objects, which the deploy-gap explains.

## What this does NOT establish

- It is **not** a validation pass: it ran the probe-contaminated wrapper (the probe did the
  uploads before the production block), and it was executor-run — the split-brain covenant
  requires the INDEPENDENT validator to adjudicate the CLEAN final code. Residual to close: the
  production block depositing on its own, with no probe ahead of it, on a clean run.
- 2.4S / 2.4R stay 🟡, gate ARMED.

## Consequence / next

- The probe is reverted (PR #205 closed unmerged; branch deleted). `main` carries the clean
  production `capturespec.py` (no probe).
- NO attempt-5 code fix is authored — there is no defect to fix. The real durable fix is
  PROCESS: the post-deploy LIVE CODE-ASSET check is made a HARD, non-skippable gate in the
  2.4S deploy-verify doc (so a future run cannot silently validate stale code the way attempt
  4 almost certainly did), reinforced by OD-007 (offline wrapper smoke-test harness) and
  OD-008 (SFN false-green — this run's fork branch reported success over `outcome=execution_error`).
- Next: a CLEAN split-brain re-validation of current `main` (final code, deploy-asset check
  enforced up front). On the validator's sealed PASS with retained evidence, 2.4S ✅ + 2.4R
  clears together + gate disarms + on-deck repoints to 4.7.
