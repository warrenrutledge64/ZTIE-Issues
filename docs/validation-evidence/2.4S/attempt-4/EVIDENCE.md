# Story 2.4S (Fix B / RD-058) — live validation attempt 4: SEALED FAIL (2026-09-23)

> **Status: SEALED FAIL.** Fix A (`__ZTIE_RC=0`, PR #200) is PROVEN — the wrapper survived a
> hanging artifact and extracted the strace evidence — but **Fix B (the direct host→S3 trace
> upload that IS Story 2.4S / RD-058) still failed SILENTLY and the run fell back to the SSM
> stdout transport.** The DoD is only partially met; a partial/FAIL never earns ✅.
>
> This record is the write-only scribe's transcription of the independent validator's sealed
> adjudication (RD-052/053/055) plus the RETAINED raw evidence (RD-054). Kiro authored none of
> the verdict; the root-cause analysis in §Root cause is engineering triage for the NEXT fix,
> explicitly scoped to what the raw evidence settles vs. does not.
>
> - Code under test: **current `main` `99ffdd4`** — all five live fixes in
>   (PRs #195 regional-endpoint / #198 absolute-CLI-path / #199 root-volume 30GB /
>   #200 `__ZTIE_RC=0` set-u fix; OD-006 AMI-empty resolved). Handed to the validator as the
>   latest merged fix (PR #200 / current main), RD-055.
> - Independent validator: Gemini (blind, RD-055 — Kiro supplied the PR number / main SHA only).
> - Intake: `6994199c-9255-4026-becd-cdf0dbb3c426` (payload
>   `intake/6994199c-.../validation_hang.sh`, 49 bytes — a hang-past-timeout probe, so Fix B's
>   timeout-survival path was genuinely exercised).
> - Accounts: Forensic `360999005254` (detonation host + artifact bucket) / Hub `641628980935`.

## 1. What this run PROVED (the net-positive — Fix A works)

- **Fix A (`__ZTIE_RC=0`) resolved the `set -u` crash.** The wrapper no longer dies with
  `__ZTIE_RC: parameter not set` (exit 2) on the way to the emit/upload block.
- **The hanging-artifact timeout fired and the wrapper SURVIVED.** The artifact was killed at
  the on-host budget: **`exit_code: 124`** (GNU `timeout` TERM/KILL) and the
  **`ZTIE-ARTIFACT-TIMED-OUT`** marker printed — the RD-057 `setsid timeout --kill-after` +
  stdio-detach path did its job (no 120 s SSM SIGKILL / 137 this time).
- **The strace evidence was extracted.** The run produced a full 11,851-byte
  `runs/6994199c-.../detonation-output.json` with the trace carried inline — i.e. the strace
  `-o` per-PID files DID exist (the later stdout emit block, using the same
  `ls /tmp/ztie/behavior.strace.*` glob, found and emitted them).

## 2. What this run FAILED (Fix B — the actual point of 2.4S)

- **DoD 4 (live deposit) FAIL** — S3 has **no `traces/6994199c-.../` prefix at all**: no
  `behavior.strace.<pid>` per-PID objects and **no `_UPLOAD_COMPLETE` sentinel** (retained
  listing: `s3-listing.txt`). No object landed anywhere else in the bucket for this intake.
- **DoD 5 (timeout survival) FAIL** — the durable out-of-band S3 trace does not exist, so the
  Lambda's S3-first read found nothing (`trace_from_s3` was NOT `True`) and it fell back to
  the SSM stdout slice — the exact fragile transport Fix B was built to replace.
- **The self-diagnosing diag block is EMPTY.** The wrapper printed `ZTIE-TRACE-UPLOAD-BEGIN`
  and `ZTIE-TRACE-UPLOADED`, then `ZTIE-UPLOAD-DIAG-BEGIN` / `ZTIE-UPLOAD-DIAG-END` with
  **nothing between them** (`upload-stderr-diag.txt`). Because every `aws s3 cp` appends
  `2>>/tmp/ztie/upload.stderr` and the diag ships `head -c <cap> /tmp/ztie/upload.stderr`, an
  empty block means the copies wrote **no stderr** — they neither ran-and-failed (that logs a
  cause) nor ran-and-succeeded (that deposits objects). This is a NEW, distinct failure mode.

## 3. Sealed verdict block (validator, verbatim)

```
VERDICT: FAIL (Fix A proven; Fix B direct S3 upload still fails silently -> stdout fallback)

DoD 1 (Positive IAM)       : PASS (Verified Attempt 2 — DetonationInstanceRole ALLOWS
                                    s3:PutObject on traces/*)
DoD 2 (Negative IAM)       : PASS (Verified Attempt 2 — DENY on findings/* + all GetObject)
DoD 3 (Deploy Verification): PASS (the fixed code is live — the wrapper survived the hang,
                                    exit_code 124 + ZTIE-ARTIFACT-TIMED-OUT fired, and the
                                    upload block's markers printed)
DoD 4 (Live Deposit)       : FAIL
  Evidence: no traces/6994199c-.../ prefix in S3 — no behavior.strace.<pid> objects,
            no _UPLOAD_COMPLETE sentinel (s3-listing.txt).
  Evidence: the run fell back to the SSM stdout transport (11,851-byte detonation-output.json).
DoD 5 (Timeout Survival)   : FAIL
  Evidence: trace_from_s3 was not True; the durable out-of-band S3 trace does not exist.
  Diagnostic: ZTIE-UPLOAD-DIAG block EMPTY -> the aws s3 cp copies produced no stderr
              (neither ran-and-failed nor ran-and-succeeded).
Human Sign-off (IAM Check) : PASS
Human Sign-off (Trace Data): FAIL (direct upload deposited nothing; stdout fallback only)
```

## 4. Root cause — CANDIDATES, scoped honestly (engineering triage for attempt 5)

> Per the attempt-5 lesson (do NOT over-attribute a WHY the raw output cannot prove), this
> section separates what the evidence SETTLES from the candidate mechanisms a targeted host
> probe must disambiguate BEFORE any attempt-5 code change (confirm-then-fix, covenant §4).

**Settled by the evidence:**
- The attempt-2 cause (bare/global endpoint) and the attempt-3 cause (`aws: not found` on the
  SSM PATH) are FIXED and are NOT the cause here: PR #195 pins
  `--region <r> --endpoint-url https://s3.<r>.amazonaws.com` and PR #198 invokes the absolute
  `HOST_AWS_CLI = /usr/local/aws-cli/v2/current/bin/aws`. Either of those recurring would have
  written to the errlog (a non-empty diag) — it is empty, so they did not recur.
- The strace per-PID files EXISTED (the stdout emit block found + emitted them). So this is
  NOT a "no trace was produced" case.
- The `aws s3 cp` invocations produced NO stderr into `/tmp/ztie/upload.stderr`.

**NOT settled by this output — candidate mechanisms (need a live host probe to pick one):**
1. **Glob-empty-at-upload-time (ordering/visibility).** The upload block is spliced by
   `build_capture_run_commands` AFTER `_instrumented_exec_commands` — which ends with `sync`
   — and BEFORE the stdout emit block. So on paper the per-PID files are synced before the
   upload globs them. But the upload `for __t in $(ls /tmp/ztie/behavior.strace.* 2>/dev/null)`
   runs inside the `if command -v strace` branch's command list; if, under the SIGKILL-group
   teardown, the files are not yet visible to THAT `ls` (but are by the later emit `ls`), the
   loop body (the only `aws s3 cp` with an errlog) never runs -> no stderr, no deposit,
   consistent with the empty diag. The sentinel `printf | aws s3 cp -` would still run,
   though — see candidate 3.
2. **SIGKILL-group interaction.** `setsid timeout --kill-after=GRACE BUDGET strace …` puts the
   traced run in its own session/group and SIGKILLs the whole group on timeout. If the upload
   sub-block (or the shell state around it) is perturbed by that teardown, the copies may be
   skipped. Needs confirmation that the upload block executes in the wrapper shell, not a
   killed descendant.
3. **Sentinel copy silently no-op'd.** Even if the per-PID loop is empty, the sentinel
   `printf %s 'complete' | <aws> s3 cp - s3://…/_UPLOAD_COMPLETE …  2>>errlog || true` should
   ALWAYS run and would either deposit `_UPLOAD_COMPLETE` (it did not) or log stderr (empty
   diag). Its writing NEITHER is the sharpest anomaly and the strongest tell that the upload
   sub-block did not execute as written (candidate 1/2), OR that stderr is not reaching the
   errlog under the SSM shell (a redirection/visibility issue).

## 5. CONFIRM-BEFORE-FIX probe (attempt 5 gate — do NOT skip, do NOT guess)

A short live host probe settles candidates 1–3 without shipping a theorized fix (avoids the
attempt-2 assume-and-fail). Add ONE diagnostic to the upload block (or run as an SSM one-off on
a fresh detonation) that, right where the upload loop runs, prints:
- `echo "UPLOAD-CTX pwd=$(pwd) whoami=$(id -u)"`
- `echo "UPLOAD-LS:"; ls -la /tmp/ztie/ 2>&1; echo "GLOB:"; ls -la /tmp/ztie/behavior.strace.* 2>&1`
- a single explicit test copy with stderr NOT suppressed:
  `/usr/local/aws-cli/v2/current/bin/aws s3 cp /tmp/ztie/behavior.strace.* s3://<bucket>/traces/<id>/ --region <r> --endpoint-url https://s3.<r>.amazonaws.com ; echo "cp_rc=$?"`
shipped OUTSIDE the `|| true` so its rc + stderr are visible. This proves whether the files are
visible at upload time (candidate 1), whether the block runs at all in the surviving wrapper
(candidate 2), and whether the CLI+endpoint actually works for a copy here (candidate 3 / any
residual IAM/endpoint issue). ONLY after that is the attempt-5 fix authored, on its own branch,
for its own blind re-validation.

## 6. Consequence

- **2.4S STAYS 🟡, 2.4R STAYS 🟡, the advancement gate stays ARMED** (a partial/FAIL never
  earns ✅; the linked 2.4R clears only on 2.4S's own recorded live PASS).
- Evidence retained per RD-054: this record, `upload-stderr-diag.txt` (the EMPTY diag block),
  and `s3-listing.txt` (the adjudicating S3 slice: no `traces/6994199c-.../`, no sentinel).
- Fix-then-validate-once: run the §5 confirm-before-fix probe FIRST, then author the targeted
  attempt-5 fix on a new branch and re-validate blind from its own PR number.

## 7. Standing flags surfaced this cycle (tracked-item candidates — stakeholder to action)

- **(a) SFN false-green.** The fork/parallel branch reports `SUCCEEDED` even when the launch
  path fails — a real observability gap that has let partial runs look plausible. Candidate for
  the Operational Debt Register.
- **(b) Host-environment / wrapper smoke-test harness.** FIVE straight live defects (attempts
  2→attempt-4 + the set-u crash) were all shell/host-shape issues invisible to the offline bar
  (which asserts only the command STRING). PR #200 added the FIRST test that EXECUTES the
  emitted wrapper under `sh -u`; generalizing it (instant / hanging / no-shebang /
  strace-absent / **upload-block-with-a-stubbed-`aws`** cases) would surface this whole class
  offline in one pass instead of one live cycle each. Candidate for a dedicated hardening story.
