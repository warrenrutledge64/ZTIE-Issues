<!-- FILE: docs/session-briefs/story-2.4S-NEXT-SESSION-PROMPT.md -->
# Next-session warm-start prompt — Story 2.4S (Fix B / RD-058)

> Paste the block below to start the next Kiro session. It carries the exact live state,
> the open PR, the split-brain boundary, and the next action so the session starts with
> zero cold-start. Authoritative status always = `RUNBOOK.md`; this is the warm pointer.

```
We are resuming the ZTIE Detonation Chamber project (repo warrenrutledge64/ZTIE-Issues).
Clone it fresh and read RUNBOOK.md as the source of truth before acting — your persisted
learnings are STALE (they end around Story 4.6; the live work is the 2.4R/2.4S backfill).

CURRENT STATE (verify against the repo at STEP 0, do not trust this blindly):
- main tip at handoff: 1b916c9 (PR #199 merged).
- Validation Debt Register: 2 OPEN — 2.4R + its linked remediation 2.4S (one work item).
  Advancement gate is ARMED: no NEW feature story may begin until 2.4R/2.4S clears.
- 2.4S is 🟡 (built, NOT live-validated). 2.4R is 🟡. Neither has a recorded live PASS.
- Operational Debt: OD-004 + OD-005 open; OD-006 (AMI/host-launch blocker) CLOSED 2026-09-22.

WHAT 2.4S IS (Fix B / RD-058): the isolated Forensic detonation host uploads strace -o
per-PID trace files DIRECTLY to Forensic S3 (traces/{intake_id}/) with an _UPLOAD_COMPLETE
sentinel written last; the Lambda reads the trace from S3 and treats "SSM TimedOut/Failed
BUT a complete S3 trace exists" as a SUCCESSFUL capture. It replaces the fragile SSM-stdout
transport. It is a [sec-boundary] story (changes the RD-013 exit surface + DetonationInstanceRole IAM).

THE OPEN ITEM YOU MUST HANDLE FIRST:
- PR #200 (branch fix/story-2.4S-ztie-rc-init, head 5aa750a) is OPEN, not yet merged. It
  fixes a live set -u crash: __ZTIE_RC was assigned only inside the strace if/else branches
  but read by `exit $__ZTIE_RC` outside them, so an instant-completing payload tripped
  `__ZTIE_RC: parameter not set` (exit 2) and SIGKILLed the host before the trace uploaded.
  Fix = initialize __ZTIE_RC=0 once before the if. Includes an EXECUTION regression test
  (runs the emitted wrapper under sh -u). 180 detonation tests OK, ruff clean, check_docs 0.
- If #200 is still open at session start: it is the latest fix and must be merged + the code
  it produced is what gets validated. If it merged already, main carries it.

FOUR PRIOR LIVE FIXES ALREADY MERGED (all environment/shell-shape defects the offline bar
can't see) — do NOT re-introduce these:
  1. AMI-empty (OD-006, closed): /ztie/ami/ubuntu-22.04 was empty -> RunInstances MissingParameter ImageId.
  2. PR #195: host `aws s3 cp` must pin --region + --endpoint-url https://s3.<region>.amazonaws.com
     (VPC gateway serves the REGIONAL host only; global endpoint times out) + region injected
     deterministically from the Lambda AWS_REGION + upload stderr shipped between
     ZTIE-UPLOAD-DIAG-BEGIN/END markers (no more silent || true).
  3. PR #198: invoke the CLI by ABSOLUTE path /usr/local/aws-cli/v2/current/bin/aws
     (baked on AMI but NOT on the SSM shell PATH).
  4. PR #199: launch-template root volume 20->30GB to match the republished golden AMI snapshot.

NEXT ACTION = the 2.4S LIVE RE-VALIDATION (split-brain, RD-055):
- This is a live validation, NOT a build task. You (Kiro) author NO runbook, NO DoD, supply
  NO diff/snippet, and do NOT judge. The independent validator (Gemini, a FRESH context-free
  session) authors the DoD + runbook BLIND from the PR NUMBER ONLY, the stakeholder runs it
  live, and Gemini seals PASS/FAIL/INCONCLUSIVE. Kiro is a write-only scribe at close-out.
- Hand the validator the correct PR: if #200 is merged, hand the merge; the code under test
  is the current main with #200 in it. (Confirm the exact PR/SHA at STEP 0.)
- On a sealed PASS + RETAINED raw evidence (RD-054) — the aws s3api list-objects-v2 output
  showing _UPLOAD_COMPLETE + behavior.strace.<pid> files, AND the Lambda output showing
  capture_status: captured / trace_from_s3: true — Kiro appends
  docs/validation-evidence/2.4S/attempt-<n>/, flips 2.4S ✅, CLEARS the linked 2.4R entry
  (they close together), disarms the gate, repoints on-deck to Story 4.7, and PRs the close-out.
- On FAIL/INCONCLUSIVE: stays 🟡, fix-then-validate-once. NEVER flip on a summary/inference —
  a prior "Audit Sign-Off" was correctly REFUSED because it lacked raw evidence and cited the
  wrong lane's results.

DEPLOY-GAP DISCIPLINE for the live run: after `cdk deploy ZtieDetonationStack`, VERIFY the
live Lambda actually carries the new code (e.g. the __ZTIE_RC=0 init / the regional
--endpoint-url / absolute CLI path), not just a green UPDATE_COMPLETE. sts get-caller-identity
before every block; the detonation host is Forensic 360999005254, the tracking table is Hub
641628980935. Use a payload that HANGS past the SSM timeout (e.g. sleep 140) so Fix B's
timeout path is actually exercised.

TWO STANDING FLAGS to raise with the stakeholder (tracked-item candidates, not yet actioned):
  (a) SFN false-green: the fork branch reports SUCCEEDED even when RunInstances fails — a real
      observability gap that let false sign-offs look plausible.
  (b) Host-environment / wrapper smoke-test harness: 5 straight live defects were all
      shell/host-shape issues invisible offline. PR #200 added the first test that executes the
      emitted wrapper under sh -u; generalizing it (instant/hanging/no-shebang/strace-absent
      cases) would surface the rest offline in one pass instead of one live cycle each.

STEP 0 checklist: clone; read RUNBOOK.md (Validation Debt Register + Operational Debt Register)
+ docs/session-briefs/on-deck/README.md; confirm PR #200 state; confirm the gate is still ARMED
on 2.4R/2.4S; then proceed with the split-brain live re-validation. Offline tooling in this
sandbox: python via ~/.pyenv/versions/3.12.13/bin/python3 -m unittest (NOT pytest); ruff at
~/.pyenv/versions/3.12.13/bin/ruff; tsc/prettier need `env -u NODE_OPTIONS`; run check_docs
AFTER committing any status edit (CHECK B baseline = git show HEAD:RUNBOOK.md).
```
