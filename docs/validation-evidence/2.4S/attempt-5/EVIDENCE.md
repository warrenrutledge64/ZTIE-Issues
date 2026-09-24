# Story 2.4S (Fix B / RD-058) — live validation attempt 5: SEALED PASS (2026-09-24)

> **Status: SEALED PASS.** The independent validator (Gemini, blind, RD-055) sealed a **PASS**
> for Story 2.4S on the clean final code (`main` `c1e323c`), with the ⛔ non-skippable
> deploy code-asset gate passing FIRST. On this PASS, **2.4S flips 🟡→✅ AND the linked 2.4R
> entry clears together** (one work item), the Validation Debt Register empties, and the
> advancement gate is DISARMED. This record is the write-only scribe's transcription of the
> validator's sealed verdict + the RETAINED raw evidence (RD-054); Kiro authored none of the
> rubric and did not adjudicate.
>
> - Code under test: **`main` `c1e323c`** — the final Story 2.4S / RD-058 code with all fixes
>   in (PRs #195 regional-endpoint / #198 absolute-CLI / #199 root-volume-30GB / #200 `set -u`
>   `__ZTIE_RC=0` init). No "attempt-5" code fix — the confirm-before-fix probe showed the code
>   was correct; the change since the attempt-4 FAIL was PROCESS (the deploy code-asset gate),
>   not code.
> - Independent validator: Gemini (blind, RD-055 — Kiro supplied the PR/commit + requirement
>   + operator gate only; see `docs/session-briefs/story-2.4S-revalidation-HANDOFF.md`).
> - Intake: `beb6f4b5-bdcc-4466-984c-fdaa3256bcdd` (hang-past-timeout probe — Fix B's timeout
>   path genuinely exercised: `exit_code=124`, `ssm_status` non-success).
> - Accounts: Forensic `360999005254` (detonation host + artifact bucket) / Hub `641628980935`.

## 1. Code-Asset Verification — the ⛔ blocking gate PASSED

The live Lambda deployment package was verified against `c1e323c` BEFORE the run
(`docs/session-briefs/story-2.4R-DEPLOY-VERIFY.md` STEP 4). All required fixes active, and the
diagnostic probe absent:

- `__ZTIE_RC=0` (PR #200 `set -u` init) — active, `capturespec.py` line 530.
- `--endpoint-url` (PR #195 regional endpoint) — active, `capturespec.py`.
- `HOST_AWS_CLI = "/usr/local/aws-cli/v2/current/bin/aws"` (PR #198 absolute CLI) — active.
- Fix B upload block (RD-058) — active (`TRACE_UPLOAD_COMPLETE_SENTINEL = "_UPLOAD_COMPLETE"`,
  `ZTIE-TRACE-UPLOAD-BEGIN`).
- S3-first read path (`awsio.read_uploaded_trace` / `handler.py` `trace_from_s3`) — active.
- Regression guard: `>>> OK: no probe code on the live asset` — proves the live Lambda is the
  clean `c1e323c` code, NOT the reverted diagnostic probe (the attempt-4 deploy-gap class is
  positively excluded).

This gate is the specific remediation for the attempt-4 FAIL (which ran stale pre-#200 code
under a green `UPDATE_COMPLETE`): the validation was NOT run over a stale/unverified asset.

## 2. Durable S3 Trace Offload + Completion Sentinel (Forensic `360999005254`)

`aws s3api list-objects-v2` on the Forensic artifact bucket
(`ztieintakestack-intakeartifactbucket2415ab50-vzfdr2jmnj5a`) under
`traces/beb6f4b5-bdcc-4466-984c-fdaa3256bcdd/` — the definitive raw evidence that the host's
DIRECT S3 offload + sentinel write succeeded (verbatim):

```
2026-09-24 01:04:48          8 traces/beb6f4b5-bdcc-4466-984c-fdaa3256bcdd/_UPLOAD_COMPLETE
2026-09-24 01:04:54      10947 traces/beb6f4b5-bdcc-4466-984c-fdaa3256bcdd/behavior-trace.txt
2026-09-24 01:04:46       3084 traces/beb6f4b5-bdcc-4466-984c-fdaa3256bcdd/behavior.strace.762
2026-09-24 01:04:47       7685 traces/beb6f4b5-bdcc-4466-984c-fdaa3256bcdd/behavior.strace.763
```

- `behavior.strace.762` / `.763` — the host's per-PID `strace -o` files, uploaded DIRECTLY to
  Forensic S3 by the ephemeral host (not the SSM stdout transport).
- `_UPLOAD_COMPLETE` (8 B) — the completeness sentinel, written LAST; its presence is the
  durable, out-of-band signal that every per-PID file was copied. Timestamps confirm ordering
  (per-PID files 01:04:46/47, then sentinel 01:04:48).
- `behavior-trace.txt` (10947 B) — the Lambda's own consolidated write of the recovered trace.

Corroborating (from the attempt-4 confirm-before-fix probe, same code, same intake, recorded
in `../attempt-4/PROBE-FINDING.md`): the Lambda logged
`using S3-uploaded behavioral trace for intake_id=beb6f4b5-… (objects=2 complete=True ssm_status=Failed)`
— i.e. it read the trace FROM S3 and treated the timed-out/failed SSM command with a complete
S3 trace as a SUCCESSFUL capture, exactly the RD-058 intent.

## 3. Sealed verdict block (validator, verbatim)

```
Sealed Validation Verdict: PASS (Story 2.4S / RD-058)

All blocking gates, pre-condition checks, and resilient S3-offload behaviors operated exactly
as specified in the architecture.

- Code-Asset Verification (blocking gate): PASS — all c1e323c fixes active; probe code absent.
- Durable S3 offload + completion sentinel:  PASS — per-PID strace files + _UPLOAD_COMPLETE
  present under traces/beb6f4b5-.../ in the Forensic artifact bucket.
```

## 4. Consequence

- **2.4S flips 🟡→✅** (validated live 2026-09-24). It is a `[sec-boundary]` story (new RD-013
  host→S3 exit surface + `DetonationInstanceRole` `s3:PutObject` on `traces/*`); the ✅ rests on
  the retained raw artifacts above (RD-054), not testimony.
- **The linked 2.4R entry clears together** (one work item — 2.4S is the RD-058 remediation
  that clears 2.4R; on this recorded PASS the auditable dynamic-lane evidence backfill 2.4R was
  chartered to provide now exists, so 2.4R closes ✅).
- **The Validation Debt Register empties; the advancement gate is DISARMED.** The next pipe
  story (**4.7**) unblocks.
- Evidence retained per RD-054: this record (the sealed verdict + the verbatim S3 listing + the
  code-asset gate result), alongside the full attempt history in `../attempt-1..4/` and the
  attempt-4 `PROBE-FINDING.md`.
