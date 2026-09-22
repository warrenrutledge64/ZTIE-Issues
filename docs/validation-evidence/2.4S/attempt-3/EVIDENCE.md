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

## 6. Post-run (to be completed after STEP 3)

> Paste the raw STEP-3/STEP-4 outputs, attach the two manifest artifacts, and record the
> validator's FINAL sealed verdict here. Until then this stays a PRE-RUN record and 2.4S
> stays 🟡 (2.4R stays 🟡, gate ARMED).
