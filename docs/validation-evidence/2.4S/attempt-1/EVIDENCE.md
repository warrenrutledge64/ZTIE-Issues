# Story 2.4S (Fix B / RD-058) — live validation attempt 1: SEALED VERDICT **INCONCLUSIVE**

> Retained per RD-054 (a sealed verdict is necessary but not sufficient; the auditable
> artifact is the proof). Authored by the independent validator (Gemini) under the RD-052/053/055
> split-brain protocol; the code under test is **PR #192** (merge `5c5cd76f88e2a2fbb14e073a70d82ae7f007193e`,
> branch `feature/story-2.4S` → `main`). Kiro recorded this verbatim as a write-only scribe; it
> authored none of the rubric.

## Verdict

```
VERDICT: INCONCLUSIVE (Blocked by upstream Story 2.0 launch failure)

DoD 1 (Positive IAM)       : PASS (iam-simulator output confirmed allowed)
DoD 2 (Negative IAM)       : PASS (iam-simulator output confirmed implicitDeny)
DoD 3 (Live Deposit)       : BLOCKED
  Evidence: /tmp/24s-out.json -> "outcome": "launch_error"
  Evidence: /tmp/24s-out.json -> "error_reason": "RunInstances failed: An error occurred
            (MissingParameter) when calling the RunInstances operation:
            The request must contain the parameter ImageId"
DoD 4 (Timeout Survival)   : BLOCKED
  Evidence: /tmp/24s-out.json -> "ssm_status": "not_run" (Host never existed)
Human Sign-off (IAM)       : PASS
Human Sign-off (Trace)     : BLOCKED
```

## What this does and does NOT establish

- **Establishes:** the `DetonationInstanceRole` IAM grant for the Fix-B S3 upload is correct
  (DoD 1 positive / DoD 2 negative both PASS via `iam:simulate*`).
- **Does NOT establish:** anything about the Fix-B behavior itself. The ephemeral detonation
  host **never launched**, so the S3-direct upload path, the `_UPLOAD_COMPLETE` sentinel, the
  S3-first read, and the "SSM `TimedOut` BUT complete S3 trace = success" semantics were
  **never exercised**. `ssm_status: not_run` because there was no host.

## Root cause (validator RCA — drift / deploy-state, NOT a 2.0 code defect)

`awsio.run_instance_from_template` calls `ec2:RunInstances` with the `LaunchTemplateId` +
`Version: "$Latest"` and **omits `ImageId`** — the AMI is expected to come from the launch
template. EC2 rejected the call with `MissingParameter … The request must contain the
parameter ImageId`, which proves the **currently deployed `$Latest` version of launch
template `lt-045ddce7fdac386db` (Forensic 360999005254) carries no valid `ImageId`**.

The `ZtieForensicInfraStack` resolves the AMI via
`ec2.MachineImage.fromSsmParameter("/ztie/ami/ubuntu-22.04")` (verified in source:
`AMI_SSM_PREFIX = "/ztie/ami"`, default `amiFlavor = "ubuntu-22.04"`; the stack **CONSUMES**
the value, the Image Builder pipeline **PUBLISHES** it). So the SSM parameter
`/ztie/ami/ubuntu-22.04` was empty / stale / dummy at the last `cdk deploy`, baking an
AMI-less template version. This is an **environment / deploy-state** condition, not a
structural defect in the 2.0 CDK.

## Consequence

- **2.4S stays 🟡; the linked 2.4R entry stays 🟡; the advancement gate stays ARMED.**
  INCONCLUSIVE clears nothing.
- The blocker is tracked as **OD-006** in the RUNBOOK Operational Debt Register
  (`Blocks: 2.4S validation → 2.4R clearance`).
- **No code change** — the 2.4S code and the 2.0 CDK are unchanged. The remedy is operational
  (republish the AMI to SSM → redeploy `ZtieForensicInfraStack` → verify the live template
  version carries a real `ImageId` → re-run the SAME sealed runbook from STEP 3; no re-review,
  because the code did not change).

## Provenance

- Independent validator: Gemini (blind, RD-055 — Kiro supplied PR number only).
- Code under test: PR #192, merge `5c5cd76f88e2a2fbb14e073a70d82ae7f007193e`.
- Accounts: Forensic `360999005254` (detonation host + launch template `lt-045ddce7fdac386db`),
  Hub `641628980935`. Region `us-east-1`.
- Raw run output cited: `/tmp/24s-out.json` (operator's CloudShell). If that file was captured,
  attach it alongside this record; `/tmp` is wiped on CloudShell recycle, so re-capture on the
  next run if it has aged out.
