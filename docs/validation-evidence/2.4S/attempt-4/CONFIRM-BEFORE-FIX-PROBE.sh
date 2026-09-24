#!/bin/sh
# Story 2.4S attempt-4 -> attempt-5 CONFIRM-BEFORE-FIX probe (covenant §4).
# Purpose: disambiguate WHY the direct S3 upload was INERT (empty ZTIE-UPLOAD-DIAG block,
# no per-PID objects, no _UPLOAD_COMPLETE sentinel) WITHOUT guessing an attempt-5 fix.
# It mirrors the PRODUCTION upload semantics in capturespec.build_trace_upload_commands
# (per-file `for` loop copy + a separate stdin sentinel copy), NOT a one-shot glob copy.
#
# HOW TO RUN IT FAITHFULLY (the timing matters):
#   The sharpest candidates (glob-empty-at-upload-time; setsid-timeout SIGKILL-group
#   teardown) are only reproduced IN CONTEXT. Prefer option (A); (B) is a weaker fallback.
#   (A) IN-WRAPPER (best): temporarily splice this block into
#       capturespec.build_trace_upload_commands right AFTER the TRACE_UPLOAD_BEGIN echo,
#       redeploy ZtieDetonationStack, and re-run the SAME hang-past-timeout payload
#       (validation_hang.sh / sleep 140). The probe output rides back in stdout between the
#       PROBE markers. This exercises the real teardown + real upload-time file visibility.
#   (B) STANDALONE (fallback only): run this on a FRESH ephemeral detonation host via an
#       SSM AWS-RunShellScript one-off, AFTER a detonation has produced /tmp/ztie files but
#       BEFORE TTL. This proves CLI/IAM/endpoint reachability but CANNOT reproduce a
#       timing/teardown-dependent inertness (so a clean result here does NOT clear cand. 1/2).
#
# Set these to the live values before running (bucket = Forensic ARTIFACT_BUCKET):
BUCKET="ztieintakestack-intakeartifactbucket2415ab50-vzfdr2jmnj5a"
INTAKE="6994199c-9255-4026-becd-cdf0dbb3c426"   # or the NEW intake if option (A)
REGION="us-east-1"
AWS="/usr/local/aws-cli/v2/current/bin/aws"     # HOST_AWS_CLI (PR #198 absolute path)
PREFIX="/tmp/ztie/behavior.strace"              # _TRACE_PREFIX
DEST="s3://${BUCKET}/traces/${INTAKE}/"
SENTINEL_DEST="s3://${BUCKET}/traces/${INTAKE}/_UPLOAD_COMPLETE"
ENDPOINT="https://s3.${REGION}.amazonaws.com"
S3FLAGS="--region ${REGION} --endpoint-url ${ENDPOINT}"   # NOTE: NO --only-show-errors here

echo "ZTIE-PROBE-BEGIN"

# --- Context: where am I, who am I, is the CLI even present/executable? -------------
echo "PROBE-CTX pwd=$(pwd) uid=$(id -u) shell=$0"
echo "PROBE-AWS: ls -l of the absolute CLI + a version call (stderr NOT suppressed):"
ls -l "$AWS" 2>&1 || echo "  (aws abs path missing)"
"$AWS" --version 2>&1 || echo "  (aws --version failed rc=$?)"

# --- Visibility: do the per-PID files exist AT THIS POINT, and what does the glob see? --
echo "PROBE-LS /tmp/ztie/:"
ls -la /tmp/ztie/ 2>&1
echo "PROBE-GLOB (ls \$PREFIX.*):"
ls -la "$PREFIX".* 2>&1
echo "PROBE-GLOB-COUNT: $(ls "$PREFIX".* 2>/dev/null | wc -l)"

# --- Reproduce the PRODUCTION per-PID loop EXACTLY, but with stderr VISIBLE + rc echoed ---
# (production redirects 2>>errlog and swallows with `|| true`; here we surface both.)
echo "PROBE-PER-PID-LOOP (mirrors the production for-loop; stderr shown, rc echoed):"
__n=0
for __t in $(ls "$PREFIX".* 2>/dev/null); do
  __n=$((__n+1))
  echo "  cp file: $__t"
  "$AWS" s3 cp "$__t" "$DEST" $S3FLAGS
  echo "  per_pid_cp_rc=$? file=$__t"
done
echo "PROBE-PER-PID-RAN=$__n (0 => the loop body NEVER executed = glob empty at this point)"

# --- Reproduce the PRODUCTION sentinel copy EXACTLY (the sharpest anomaly) --------------
echo "PROBE-SENTINEL (mirrors printf | aws s3 cp - ; stderr shown, rc echoed):"
printf %s 'complete' | "$AWS" s3 cp - "$SENTINEL_DEST" $S3FLAGS
echo "sentinel_cp_rc=$?"

# --- Confirm what actually landed in S3 for this intake ---------------------------------
echo "PROBE-S3-LIST (what is under traces/$INTAKE/ now):"
"$AWS" s3api list-objects-v2 --bucket "$BUCKET" --prefix "traces/${INTAKE}/" \
  --region "$REGION" --endpoint-url "$ENDPOINT" 2>&1 || echo "  (list failed rc=$?)"

echo "ZTIE-PROBE-END"
