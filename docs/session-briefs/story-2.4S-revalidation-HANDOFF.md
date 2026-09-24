<!-- FILE: docs/session-briefs/story-2.4S-revalidation-HANDOFF.md -->
# Handoff — Story 2.4S live re-validation (split-brain, RD-055)

> **Scope of this file (RD-055).** This handoff carries ONLY the PR/commit under test, the
> requirement in plain terms, and the operator gate. It deliberately contains **no Definition
> of Done, no numbered runbook, no acceptance criteria/thresholds, no deploy command, and no
> fetch/diff/grep snippets** — those are authored by the INDEPENDENT validator (Gemini),
> blind, from scratch. Kiro (the build/executor side) authored none of the validation rubric
> and is a write-only scribe at close-out.

## Code under test
- Repo `warrenrutledge64/ZTIE-Issues`, current `main` — commit **`c1e323c`** (the merge tip).
- It carries the final Story 2.4S / RD-058 code with all fixes in (PRs **#195**, **#198**,
  **#199**, **#200**).
- **There is NO new "attempt-5" fix.** A confirm-before-fix probe showed the code is correct;
  the change since the last sealed attempt is **process, not code** (see the operator gate).

## What Story 2.4S is (requirement, plain terms)
The isolated Forensic detonation host must get the behavioral (strace) trace of a detonated
artifact **out of the blast zone durably** — even when the artifact hangs and the SSM command
times out — by uploading the trace directly to Forensic S3 and having the Lambda read it from
there, treating a timed-out/failed SSM command that nonetheless has a **complete** S3 trace as
a **successful capture**. It is a `[sec-boundary]` story: it changes the RD-013 exit surface (a
new host→S3 write path out of the blast zone) and the `DetonationInstanceRole` IAM
(`s3:PutObject` on `traces/*`).

## Blocking operator precondition (must pass BEFORE the validation run)
After deploying, verify the **live Lambda CODE ASSET** actually carries the code under test.
This is a ⛔ **non-skippable gate** documented in
[`story-2.4R-DEPLOY-VERIFY.md`](story-2.4R-DEPLOY-VERIFY.md). The prior sealed FAIL (attempt 4)
was traced to a **deploy-gap**: the live Lambda ran stale code and a green `UPDATE_COMPLETE`
hid it. **A validation run over an unverified/stale asset is INVALID — do not run it, and do
not seal a verdict, until the live code-asset check passes.** (The validator authors the actual
verification steps; this note only makes the gate known.)

## Protocol (RD-052 / RD-053 / RD-055)
- The **stakeholder** fetches the diff for `c1e323c` **independently**, directly from the
  repository, and states the requirement in their own words.
- The **independent validator (Gemini, fresh / blind)** authors the Definition of Done + the
  numbered live runbook from scratch, the stakeholder runs it live, and Gemini seals
  **PASS / FAIL / INCONCLUSIVE**.
- **Kiro authored none of this** and is write-only scribe at close-out. A `not_run` /
  empty-with-no-honest-health capture is INCONCLUSIVE, not PASS.

## Accounts / operator hygiene
- Detonation host + artifact bucket: **Forensic `360999005254`**.
- Tracking table: **Hub `641628980935`**.
- Two CloudShell tabs; run `aws sts get-caller-identity` before each block (a banner comment
  does not change the account). Reusable discipline:
  [`../governance/cloudshell-hygiene.md`](../governance/cloudshell-hygiene.md).

## Close-out (what happens after the seal)
- **Sealed PASS** (with RD-054 raw evidence retained): Kiro appends the evidence folder, flips
  2.4S ✅, clears the linked **2.4R** entry (they close together, one work item), disarms the
  advancement gate, and repoints on-deck to **Story 4.7**.
- **FAIL / INCONCLUSIVE:** stays 🟡; Kiro records the sealed verdict verbatim — never a flip on
  inference.

## Current status + context (for the scribe, not the blind validator)
- 2.4S + 2.4R are **🟡**; the advancement gate is **ARMED**.
- Full history: the RUNBOOK Validation Debt Register, and
  [`../validation-evidence/2.4S/attempt-4/`](../validation-evidence/2.4S/attempt-4/EVIDENCE.md)
  — the sealed attempt-4 FAIL record (`EVIDENCE.md`) and the confirm-before-fix addendum
  (`PROBE-FINDING.md`).

> **Blind-ness note.** If your process treats the attempt-4 `PROBE-FINDING.md` (which explains
> WHY attempt 4 failed and that the current code works) as context that could bias the blind
> DoD, WITHHOLD that link from the validator and hand them only the PR/commit + the requirement
> above. Whether to share it is the stakeholder's call; it is part of the honest audit trail,
> but enforcing blind-ness is the stakeholder's to decide.
