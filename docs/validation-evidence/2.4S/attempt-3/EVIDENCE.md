# Story 2.4S (Fix B / RD-058) — live validation attempt 3: PRE-RUN record

> **Status: sealed INCONCLUSIVE (awaiting live execution).** This is the independent
> validator's STEP-2 output — adversarial review + DoD + human sign-off requirements +
> the blind-authored live runbook — recorded **verbatim** by Kiro as a write-only scribe.
> Kiro authored NONE of this rubric or runbook (RD-052/053/055). The live run (STEP 3) has
> not happened yet; this file is completed with the raw outputs + the validator's SEALED
> verdict after the operator runs it.
>
> - Code under test: **PR #195** (`fix/story-2.4S-host-regional-s3`), head
>   `4c481e34f8fe36e4d290625e8eac20cb69c0019a`, merged to `main` as `08a638e`.
> - Independent validator: Gemini (blind, RD-055 — Kiro supplied the PR number + SHA only).
> - Runbook (verbatim): [`docs/session-briefs/story-2.4S-attempt-3-LIVE-RUNBOOK.md`](../../session-briefs/story-2.4S-attempt-3-LIVE-RUNBOOK.md).

## 1. Adversarial review (validator, verbatim) — diff vs. requirement

Requirement (validator's words): the ephemeral detonation host must directly upload trace
files to the `traces/*` prefix via the REGIONAL S3 endpoint without failing silently; it
must fall back to SSM stdout if the upload fails; any upload failure must be
self-diagnosing; the host must not possess read or prefix-hopping privileges.

- **Regional Asymmetry (PASS):** `capturespec.py` pins the `aws s3 cp` commands to the
  regional endpoint via `--region <region> --endpoint-url https://s3.<region>.amazonaws.com`.
- **Environment Resolution Hijacking (PASS):** region is injected deterministically from the
  Lambda's `AWS_REGION` (handler) and baked into the host command as a literal; the host's
  flaky/manipulable SSM env is bypassed entirely.
- **Silent Failure Masking (PASS):** `|| true` retained (one failed copy can't crash the
  wrapper) but each cp now appends `2>>/tmp/ztie/upload.stderr`, shipped back bracketed by
  `ZTIE-UPLOAD-DIAG-BEGIN`/`ZTIE-UPLOAD-DIAG-END` — a failed copy surfaces its cause.
- **Missing Region Graceful Degradation (PASS):** bucket+intake_id supplied without region =>
  direct upload skipped entirely, preventing regression to the silent global-endpoint behavior.

## 2. Definition of Done (validator, verbatim)

1. **Positive Boundary Proof:** live `DetonationInstanceRole` explicitly ALLOWS `s3:PutObject`
   to `…/traces/test.txt` (verified attempt 2).
2. **Negative Boundary Proof (adversarial):** live role returns implicit/explicit DENY for
   `s3:PutObject` to `…/findings/test.txt` and `s3:GetObject` on any path (verified attempt 2).
3. **Deployment Verification:** `ZtieDetonationStack` redeployed, proving the updated
   `capturespec.py` + `handler.py` are live.
4. **Positive Live Execution & Deposit:** a live artifact execution writes the
   `_UPLOAD_COMPLETE` sentinel + `behavior.strace.<pid>` files directly to
   `traces/{intake_id}/` via the regional endpoint.
5. **Timeout Survival (Fix B):** the Lambda evaluates `trace_from_s3=True` and reads the
   out-of-band trace without relying on the SSM stdout pipe.

## 3. Human sign-off requirements (validator, verbatim)

A human must: (a) verify the `aws s3api list-objects-v2` output specifically shows the
`_UPLOAD_COMPLETE` sentinel (missing sentinel => host died mid-upload, fix incomplete);
(b) review the Lambda output JSON to confirm `error_reason`/`teardown_note` reflects a
successful capture (no silent capture gap).

## 4. Sealed verdict block (validator, verbatim — PRE-RUN)

```
VERDICT: INCONCLUSIVE (Awaiting Attempt 3 live runbook execution)

DoD 1 (Positive IAM)       : PASS (Verified Attempt 2)
DoD 2 (Negative IAM)       : PASS (Verified Attempt 2)
DoD 3 (Deploy Verification): [PENDING LIVE EVIDENCE]
DoD 4 (Live Deposit)       : [PENDING LIVE EVIDENCE]
DoD 5 (Timeout Survival)   : [PENDING LIVE EVIDENCE]
Human Sign-off (IAM Check) : PASS (Verified Attempt 2)
Human Sign-off (Trace Data): [PENDING]
```

## 5. Evidence manifest (validator, verbatim) — RETAIN here on the live run

- `lambda-invoke-result.json` — proves the Lambda executed the new region-injection logic
  and surfaced the outcome.
- `live-trace-ls.txt` — proves the regional S3 deposit succeeded and the `_UPLOAD_COMPLETE`
  sentinel exists.

## 6. Post-run — SEALED VERDICT: FAIL (2026-09-22)

```
VERDICT: FAIL (Host direct upload failed: `aws` CLI not found in execution PATH)

DoD 1 (Positive IAM)       : PASS (Verified Attempt 2)
DoD 2 (Negative IAM)       : PASS (Verified Attempt 2)
DoD 3 (Deploy Verification): PASS (Lambda code updated successfully)
DoD 4 (Live Deposit)       : FAIL
  Evidence: S3 list-objects returned only `behavior-trace.txt` (SSM stdout fallback).
  Evidence: Diagnostic stderr log proved `aws: not found`.
DoD 5 (Timeout Survival)   : FAIL (Direct upload path did not execute)
Human Sign-off (IAM Check) : PASS
Human Sign-off (Trace Data): FAIL (Direct upload binary missing on host)
```

### What this run PROVED (net-positive despite the FAIL)
- **PR #195 is live and works as engineered.** The `ZTIE-UPLOAD-DIAG-BEGIN/END` self-diagnosing
  block fired and captured the exact cause on the FIRST failing run — no blind cycle. This is
  the observability covenant paying off, and it confirms DoD 3 (the fixed code deployed).
- The regional-endpoint pin was never reached because the uploads never ran at all.

### Root cause (from the diagnostic, recorded honestly)
`aws: not found` at the host shell (dash/`sh`), lines 15-16 = the per-PID `aws s3 cp` loop and
the sentinel `aws s3 cp -`. The **AWS CLI is not resolvable on the host's PATH in the
non-interactive SSM `AWS-RunShellScript` shell**. The earlier artifact FETCH worked because it
uses `curl` against a presigned URL, not the AWS CLI — so this run was the first to require the
CLI on the host, and the RD-030 assumption that `aws` is globally available there is wrong.

### The fix depends on a fact this output does NOT settle
Two candidate fixes, decided by whether the CLI is installed at all:
- **(a) Installed but off-PATH** → reference an ABSOLUTE path in `capturespec.py`
  (`/usr/local/bin/aws` or wherever it lives) — a small command-builder change.
- **(b) Not installed on the golden AMI** → the Image Builder / AMI recipe must install it —
  a Story **2.0-foundation** change, NOT a `capturespec.py` change.
A live probe on the host (`which aws || command -v aws || ls -la /usr/local/bin/aws /usr/bin/aws
/usr/local/aws-cli`) settles it. Fix-then-validate-once: do NOT guess an absolute path that may
not exist (that would repeat the attempt-2 assume-and-fail pattern).

### Consequence
- **2.4S STAYS 🟡, 2.4R STAYS 🟡, gate ARMED** (a FAIL never earns ✅).
- Evidence retained (RD-054): `lambda-invoke-result.json` (attach the STEP-3 `/tmp/24s-out-3.json`),
  `upload-stderr-diag.txt` (the `aws: not found` diagnostic — captured here), and this record.
- Fix + blind re-validation follow on a new PR once the install-vs-PATH question is answered.

