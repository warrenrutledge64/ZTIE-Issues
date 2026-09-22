# Story 2.4S (Fix B / RD-058) — live validation attempt 2: SEALED VERDICT **FAIL**

> Retained per RD-054. Independent validator: Gemini (blind, RD-055 — Kiro supplied PR number
> only). Code under test: **PR #192** (merge `5c5cd76f88e2a2fbb14e073a70d82ae7f007193e`). Kiro
> recorded this verbatim as a write-only scribe; it authored none of the rubric. This is the
> FIRST attempt in which the detonation host actually launched (OD-006 AMI blocker resolved),
> so the Fix-B path was genuinely exercised — and it failed.

## Verdict

```
VERDICT: FAIL (Host direct upload failed silently; fell back to SSM stdout)

DoD 1 (Positive IAM)       : PASS (iam-simulator output confirmed allowed)
DoD 2 (Negative IAM)       : PASS (iam-simulator output confirmed implicitDeny)
DoD 3 (Live Deposit)       : FAIL
  Evidence: aws s3api list-objects-v2 -> returned only `behavior-trace.txt`
            (the Lambda fallback payload written by awsio.put_trace)
  Evidence: `_UPLOAD_COMPLETE` sentinel and `behavior.strace.<pid>` files are MISSING
Human Sign-off (IAM Check) : PASS
DoD 4 (Timeout Survival)   : FAIL (evidence did not survive out-of-band)
Human Sign-off (Trace Data): FAIL (direct upload payload missing)
```

## What happened

The host launched and ran, but the **host-side direct S3 upload silently failed**, so the
handler's S3-first read found no per-PID objects and no sentinel and **fell back to the SSM
stdout slice** — the exact fragile transport Fix B was built to replace. The only object under
`traces/{intake_id}/` was `behavior-trace.txt`, which is the **Lambda's own** consolidated write
(`awsio.put_trace`), NOT the host's per-PID files (`behavior.strace.<pid>`) or the
`_UPLOAD_COMPLETE` sentinel.

## Root cause (localized against source — a real 2.4S code defect, fix-then-validate-once)

The host reaches S3 **only** through the isolated-VPC S3 **gateway endpoint**, which serves the
**regional** host `s3.us-east-1.amazonaws.com`; the **global** host `s3.amazonaws.com`
TCP-times-out (documented + verified-live in `awsio.py _s3()`, 2026-09-05). The Lambda pins its
boto3 client regional + SigV4 so the presigned FETCH url works — but the host-side upload commands
in `capturespec.build_trace_upload_commands` are bare:

```
aws s3 cp "$__t" s3://<bucket>/traces/<id>/ --only-show-errors || true
printf %s 'complete' | aws s3 cp - s3://<bucket>/traces/<id>/_UPLOAD_COMPLETE --only-show-errors || true
```

with **no `--region` and no `--endpoint-url`**. The host CLI therefore resolved the **global**
S3 endpoint, hung, and timed out; the `|| true` **swallowed the failure silently**; the wrapper
proceeded to emit the trace on stdout, which the Lambda sliced and saved as `behavior-trace.txt`.
The fetch works and the upload doesn't for exactly one reason: the fetch URL is regional, the
upload CLI target is global.

## Fix scope (tracked to `fix/story-2.4S-host-regional-s3`)

1. **Deterministically pin the host CLI to the regional endpoint** — inject the region from the
   CDK deploy context (NOT the host env; SSM `AWS-RunShellScript` runs in a stripped shell where
   `AWS_REGION` is flaky/absent) and add `--region <region> --endpoint-url https://s3.<region>.amazonaws.com`
   to every host `aws s3 cp`, mirroring what `awsio._s3()` already proved works.
2. **Eliminate the silent failure** — keep `|| true` (one failed copy must not crash the wrapper),
   but redirect each `aws s3 cp` stderr to a host log that ships back between markers, so a future
   upload failure is SELF-DIAGNOSING, never invisible (observability covenant).

## Consequence

- **2.4S STAYS 🟡; 2.4R STAYS 🟡; advancement gate ARMED.** A FAIL never earns ✅.
- **OD-006 (host-launch/AMI blocker) is RESOLVED** — the host launched this attempt, proving the
  AMI republish + `ZtieForensicInfraStack` redeploy worked. Closed in the Operational Debt Register.
- The fix goes out as a NEW PR; the independent validator re-validates the FIXED code **blind**
  from that new PR number (fresh sealed runbook from STEP 1). No re-use of this diagnosis in the
  re-validation.

## Provenance

- Code under test: PR #192, merge `5c5cd76f88e2a2fbb14e073a70d82ae7f007193e`.
- Accounts: Forensic `360999005254` (host + `traces/` bucket), Hub `641628980935`. Region `us-east-1`.
- Test intake prefix cited by the validator: `traces/24s-live-test/` (contained only `behavior-trace.txt`).
