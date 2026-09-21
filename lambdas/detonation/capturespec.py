"""ZTIE Story 2.4 — PURE capture-spec derivation for the dynamic (detonation) lane.

I/O-free and offline-unit-testable (the proven 1.2 -> 2.2 -> 2.3 lane pattern: pure
logic + a thin boto3 seam). This module builds the ordered host-native shell command
list that INSTRUMENTS the Story 2.3 detonation: it wraps the artifact execution in a
host-native capture tool (RD-030: ``strace``) so that, while the artifact runs
directly on the ephemeral EC2 (NO Docker, RD-001), the host records its own syscalls,
network connection attempts and filesystem operations to a trace file, then emits that
trace back to the orchestrator between clear markers.

It makes NO AWS calls and reaches NO verdict; it only shapes the command list. The
FULL trace is delivered back to the Lambda in the SSM command output (between markers)
and the Lambda writes it to Forensic S3 (RD-009) — the same delivery mechanism the
2.3 run log already uses, so no on-host S3 PUT / presign is introduced here.

Design notes:
  * Capture is HOST-NATIVE, driven over SSM, NEVER in a container (RD-001).
  * ``strace`` is PRE-BAKED on the golden AMI (RD-030). The isolated host has no
    internet to install it at boot, so the command PROBES for it first and DEGRADES
    GRACEFULLY: if ``strace`` is absent it emits a diagnosable marker and still runs
    the artifact (uninstrumented) so the detonation itself is never blocked by a
    missing capture tool. The orchestrator records that as ``tool_unavailable``.
  * Network capture is about INTENT, not success: in the isolated VPC every outbound
    connection attempt fails, but ``strace`` records the ATTEMPT (the signal).
  * The trace is bounded on the host too (``head -c``) so a pathological artifact
    cannot make the trace unbounded; the Lambda bounds it again when summarizing.
"""

from __future__ import annotations

import os
import shlex

# Where the artifact + its trace are staged on the ephemeral host (host-local
# scratch, wiped on the hard-TTL teardown). Mirrors runspec._STAGE_DIR.
_STAGE_DIR = "/tmp/ztie"
# strace -ff writes ONE file per traced PID named ``<prefix>.<pid>``. We concatenate
# ``<prefix>.*`` when emitting, so a forked/exec'd child's trace is never lost to
# another process's output buffering (the single-file form truncated live).
_TRACE_PREFIX = f"{_STAGE_DIR}/behavior.strace"
# Story 2.4S / Fix B (RD-058): the S3 key prefix (relative to the Forensic artifact bucket)
# under which the host uploads the per-PID trace files: ``traces/{intake_id}/``. MUST match
# the handler's TRACES_PREFIX env default so the Lambda reads from the same place the host
# wrote. Kept here as a pure module constant (capturespec makes no AWS calls; it only shapes
# the host command that does the upload).
TRACES_PREFIX_REL = "traces/"
# strace's OWN stderr (startup diagnostics: a rejected -e expression, a permission
# error, etc.) is redirected here so that if strace fails to produce ANY per-PID trace
# file we can surface WHY instead of returning a silent empty capture (Story 2.4R live
# FAIL #2, 2026-09-16: %desc was rejected and the capture came back empty with no
# on-host reason visible in the crossed record).
# IMPORTANT: this filename MUST NOT match the ``<_TRACE_PREFIX>.*`` glob the emitter
# concatenates (else strace's stderr would be mixed into the trace as a bogus per-PID
# file). It deliberately uses a different stem (``behavior-strace-stderr.log``), not
# ``behavior.strace.<something>``.
_STRACE_STDERR_FILE = f"{_STAGE_DIR}/behavior-strace-stderr.log"


def artifact_host_path(filename: str) -> str:
    """The host-local path the artifact is staged at (host scratch, wiped at TTL).

    Keeps the original basename so shebang/extension-based execution behaves,
    mirroring runspec. Pure."""
    if filename:
        safe = filename.rsplit("/", 1)[-1]
        if safe:
            return f"{_STAGE_DIR}/{safe}"
    return f"{_STAGE_DIR}/artifact"


def build_fetch_commands(*, presigned_url: str, dest_path: str) -> list[str]:
    """Fetch the artifact onto the host over the S3 VPC gateway endpoint.

    Reuses the EXACT proven-live bounded-curl recipe from Story 2.3's runspec (a
    fetch that cannot reach S3 FAILS FAST with a diagnosable exit code instead of
    hanging until the 5-min hard TTL SIGKILLs it): --connect-timeout / --max-time /
    --retry / --fail, with curl's own diagnostics captured to a host log and a
    ZTIE-FETCH-FAILED marker emitted on failure. Pure."""
    log = f"{_STAGE_DIR}/curl.log"
    return [
        "set -u",
        f"mkdir -p {shlex.quote(_STAGE_DIR)}",
        (
            f"curl -sS --fail -L --connect-timeout 10 --max-time 60 --retry 2 "
            f"-o {shlex.quote(dest_path)} -v {shlex.quote(presigned_url)} "
            f"2> {shlex.quote(log)} || {{ echo \"ZTIE-FETCH-FAILED rc=$?\"; "
            f"tail -c 800 {shlex.quote(log)}; exit 90; }}"
        ),
    ]

# Clear markers the orchestrator greps for to slice the trace out of the combined
# SSM command output. Kept ASCII + distinctive so they cannot appear by accident in
# ordinary artifact output.
TRACE_BEGIN_MARKER = "=== ZTIE behavior trace: begin ==="
TRACE_END_MARKER = "=== ZTIE behavior trace: end ==="
# Emitted (instead of the trace) when strace is not present on the host — the
# orchestrator maps this to capture_status=tool_unavailable (a recorded gap).
TOOL_UNAVAILABLE_MARKER = "ZTIE-CAPTURE-TOOL-UNAVAILABLE"

# Emitted BETWEEN the trace markers when strace ran (tool present) but produced NO
# per-PID trace file — a diagnostic prefix followed by strace's own stderr, so a
# no-trace capture is self-explaining instead of a silent empty (Story 2.4R FAIL #2).
# ``slice_trace`` returns this text as the "trace", so the orchestrator still records
# capture_error (there are no real syscalls to summarize) but the human/Hub sees WHY.
STRACE_NO_TRACE_DIAG_MARKER = "ZTIE-CAPTURE-NO-TRACE-FILES; strace stderr follows:"

# Emitted when the artifact run hit the INNER ``timeout`` (Story 2.4R SEALED FAIL attempt
# 4): the artifact hung/blocked (e.g. a ``/dev/tcp`` connect with no egress) and was
# terminated so the wrapper could survive to emit whatever was captured. The orchestrator
# maps this to a recorded, honest capture-health fact (a time-bounded run), NEVER a
# verdict — a hanging artifact is EVIDENCE (a real malware behavior), not a pass/fail.
ARTIFACT_TIMED_OUT_MARKER = "ZTIE-ARTIFACT-TIMED-OUT"

# Story 2.4S / Fix B (RD-058): trace SURVIVAL is decoupled from the SSM stdout transport.
# Attempts 1-6 proved the in-wrapper strace->SSM-stdout path is structurally fragile for a
# hanging artifact: the wrapper hangs to the 120 s SSM executionTimeout (137) and the trace
# is lost with the ephemeral host at TTL. Fix B has the HOST upload the ``strace -o`` per-PID
# files DIRECTLY to Forensic S3 (``traces/{intake_id}/``) the moment strace exits, BEFORE the
# fragile stdout emit block — so the evidence is durable even if the wrapper is later killed.
# The upload uses the pre-baked AWS CLI (RD-030) over the S3 VPC gateway endpoint (the same
# in-region S3 path the artifact fetch already uses; NO public egress). A completeness
# SENTINEL object is written LAST, so the Lambda can distinguish a COMPLETE upload from a
# partial one purely by the sentinel's presence in S3 (it never has to trust stdout).
#
# The sentinel object key (relative to ``traces/{intake_id}/``). Written last; its presence
# in S3 == "the host finished copying every per-PID trace file it had". The Lambda reads
# this from S3, NOT from stdout, so a hung/killed wrapper cannot make a complete upload look
# partial. Kept a distinct name that does NOT match the per-PID trace glob the reader lists.
TRACE_UPLOAD_COMPLETE_SENTINEL = "_UPLOAD_COMPLETE"
# Best-effort stdout markers (visibility only — survival does NOT depend on these crossing).
TRACE_UPLOAD_BEGIN_MARKER = "ZTIE-TRACE-UPLOAD-BEGIN"
TRACE_UPLOADED_MARKER = "ZTIE-TRACE-UPLOADED"

# The capture tool (RD-030). Kept here so the handler/behavior modules import ONE
# source of truth for the tool name that crosses in the contract.
CAPTURE_TOOL_STRACE = "strace"
CAPTURE_TOOL_NONE = "none"

# Hard on-host cap on the emitted trace (bytes). The full trace still stays in
# Forensic; this only bounds how much is shipped back through the SSM output so a
# pathological artifact cannot make the returned trace unbounded. The Lambda applies
# its own summary bounds on top. 512 KiB is generous for a 5-min host-native run.
ON_HOST_TRACE_CAP_BYTES = 512 * 1024

# PER-PID on-host cap on the emitted trace (bytes). strace -ff writes ONE file per
# traced PID (``PREFIX.<pid>``); we cap EACH per-PID file independently so EVERY PID
# is represented in the emitted slice. This fixes the Story 2.4R live FAIL
# (2026-09-16): the earlier form capped the WHOLE lexically-sorted concatenation with
# a single ``head -c``, so a noisy low-sorting PID (e.g. a linker/locale child) could
# consume the entire 512 KiB budget and truncate the ARTIFACT's own PID trace out
# entirely. A per-PID cap guarantees the artifact's own syscalls survive the cap
# regardless of how noisy any sibling PID is; the overall cap remains a hard backstop.
# 128 KiB per PID is ample for a single process's 5-min host-native syscall stream.
ON_HOST_TRACE_PER_PID_CAP_BYTES = 128 * 1024

# INNER artifact-execution timeout (seconds) + SIGKILL grace (seconds). Story 2.4R
# SEALED FAIL (attempt 4, 2026-09-16/17): a KNOWN-BEHAVIOR probe whose last op was
# ``exec 3<>/dev/tcp/<ip>/443`` HUNG the traced process — in the isolated Forensic VPC
# there is NO egress, so the bash ``/dev/tcp`` connect blocks waiting for a SYN-ACK that
# never comes. strace, following the artifact, blocked with it. After the SSM command's
# ``executionTimeout`` (handler EXEC_TIMEOUT_S, default 120s) elapsed, the SSM agent
# SIGKILLed the ENTIRE wrapper script (exit 137). Because the whole wrapper died mid-run,
# execution NEVER reached the trace-emit block below — the BEGIN/END markers and the
# per-PID concat loop never ran — so the crossed record was an empty capture_error and
# the ON-HOST evidence (the strace -o per-PID files) was lost with the host at TTL.
# The observed detonation-output.json: ssm_status=TimedOut, exit_code=137, len(stdout)=46,
# no BEGIN/END/DIAG markers, zero trace-file headers. (This falsified the earlier
# truncation / %desc / shell-branch theories: nothing was truncated — only 46 bytes ever
# came back — and strace never got to write, so its stderr was empty too.)
#
# THE FIX: bound the artifact run with ``timeout -k GRACE BUDGET`` so a hanging/sleeping
# artifact (a real malware behavior — a C2 connect, a daemon, a sleep) is terminated but
# the WRAPPER SCRIPT SURVIVES to run the emit block and ship whatever per-PID trace files
# strace already wrote to disk. ``timeout`` sends SIGTERM at BUDGET, then SIGKILL at
# BUDGET+GRACE if the process ignores TERM (a process blocked in connect() with a held fd
# often needs the KILL). BUDGET+GRACE MUST stay comfortably below the SSM
# ``executionTimeout`` so SSM never kills the wrapper: with the default 120s SSM ceiling,
# a 75s budget + 5s grace = 80s worst case leaves ~40s headroom for the fetch (curl
# --max-time 60), strace startup, ``sync``, and the emit loop. Overridable via env so
# infra can tune it against EXEC_TIMEOUT_S without a code change (kept a pure module
# constant here; the handler passes no value — this is host-side shell shaping).
ARTIFACT_EXEC_TIMEOUT_S = int(os.environ.get("ARTIFACT_EXEC_TIMEOUT_S", "75"))
ARTIFACT_EXEC_KILL_GRACE_S = int(os.environ.get("ARTIFACT_EXEC_KILL_GRACE_S", "5"))
# ``timeout`` exit code when it had to kill the artifact (124 = terminated on TERM at
# BUDGET; 128+SIGNAL if it needed the KILL). Recorded honestly in __ZTIE_RC so the run
# outcome + the capture note can say "the artifact was time-bounded" rather than pretend
# it exited cleanly. GNU coreutils ``timeout`` is on the golden AMI (RD-030 pre-bake).
ARTIFACT_TIMEOUT_RC = 124

# Story 2.4R SEALED FAIL attempt 5 (2026-09-20): the attempt-4 ``timeout -k G B strace …``
# fix was FALSIFIED live — result byte-for-byte identical to attempt 4 (ssm_status
# TimedOut, exit 137, len(stdout)=46, no markers, trace 404) on the DEPLOYED fixed code
# (live env 75/5 CONFIRMED, so NOT a deploy-gap). ROOT CAUSE: GNU ``timeout`` signals its
# DIRECT child (``strace``) only, NOT the process group. The blocking ``connect()`` lives
# in a re-exec GRANDCHILD (strace -> /bin/sh -> artifact); killing ``strace`` left the
# grandchild alive, and the grandchild had INHERITED the SSM command's stdout pipe fd — so
# the SSM agent never saw EOF, the wrapper never regained control, and SSM SIGKILLed the
# ENTIRE session at the 120 s executionTimeout before the emit block ran.
#
# THE ATTEMPT-6 FIX (Fix A — process-group kill + stdio detach; RD-057):
#   (1) Run the traced program under ``setsid`` so ``strace`` + the artifact's whole
#       re-exec subtree form their OWN process group / session, distinct from the wrapper.
#   (2) Use ``timeout --kill-after=GRACE --signal=TERM`` combined with a session-wide kill:
#       GNU coreutils ``timeout`` in a NEW session propagates the terminating signal to the
#       WHOLE foreground process group of the timed command when it is a session leader, so
#       SIGTERM-then-SIGKILL reaches the grandchild too (belt-and-suspenders: we also
#       ``setsid`` so the timed command is a session/group leader).
#   (3) Redirect the traced program's OWN stdout+stderr to on-host files (NOT the inherited
#       SSM pipe). The artifact's file descriptors are then host-local; when strace/artifact
#       are killed, NOTHING the artifact spawned still holds the SSM command's stdout pipe
#       open, so the pipe gets EOF and the WRAPPER regains control immediately to run the
#       emit block. (strace's -o per-PID trace files are unaffected; its own diagnostic
#       stderr still goes to _STRACE_STDERR_FILE.)
# Together (1)+(2) guarantee the KILL reaches the hanging grandchild, and (3) guarantees the
# SSM pipe is released even if some child somehow lingers. BUDGET+GRACE still stays well
# under the SSM EXEC_TIMEOUT_S ceiling so the wrapper — never the artifact subtree — owns
# the teardown. GNU coreutils ``timeout`` + ``setsid`` are pre-baked on the golden AMI
# (RD-030). This is the on-host counterpart of the artifact stdio the wrapper detaches.
# The artifact's own stdout/stderr are staged on-host (host scratch, wiped at TTL) and are
# NOT part of the behavioral evidence (the trace is strace's -o files); they exist only so
# a hung child cannot hold the command pipe open.
_ARTIFACT_STDOUT_FILE = f"{_STAGE_DIR}/artifact-stdout.log"
_ARTIFACT_STDERR_FILE = f"{_STAGE_DIR}/artifact-stderr.log"

# The strace syscall set we trace. We combine the four %-CLASSES proven-accepted by the
# golden AMI's strace build with three EXPLICIT write-class syscall NAMES:
#   %file    — path-taking syscalls (open/openat/unlink/rename/chmod-by-path...).
#   %network — socket/connect/sendto/recvfrom... (network capture = INTENT).
#   %process — execve/clone/fork/exit... (the process tree).
#   %signal  — signal delivery/handling.
#   write,writev,pwrite64 — the fd-based WRITE syscalls, so a write of a data buffer is
#              captured. These take an fd, NOT a filename, so they are NOT in %file.
# WHY EXPLICIT NAMES, NOT the %desc CLASS (Story 2.4R live FAIL #2, 2026-09-16): the
# rework's first attempt added the ``%desc`` class to get write capture, but the AMI's
# strace build REJECTED ``%desc`` and exited before writing ANY ``-ff`` per-PID file, so
# the WHOLE capture came back empty (capture_error / no trace). The four classes above
# were already proven-accepted (attempt-1 produced a rich trace with them), so the safe,
# minimal fix is to add ONLY the three write syscalls we actually need BY NAME. Explicit
# syscall names are the oldest, most universally-supported strace ``-e trace=`` form and
# avoid pulling in the rest of the %desc class (read/recv noise) as a bonus. The
# behavior.py parser reads the PATH for these fd-based ops from the ``-y`` fd decoration,
# never from the data buffer, so the buffer content is never mistaken for / leaked as a path.
# ``-ff`` follows children into per-PID files (an artifact that forks), ``-tt`` gives
# microsecond timestamps for ordering, ``-y`` decodes fds to paths where possible.
_STRACE_TRACE_GROUPS = "trace=%file,%network,%process,%signal,write,writev,pwrite64"


def _instrumented_exec_commands(artifact_path: str) -> list[str]:
    """The strace-wrapped host-native execution of the artifact (when strace exists).

    IMPORTANT (live-hardened 2026-09-10): strace traces the artifact DIRECTLY as its
    immediate child, NOT a shebang-testing ``sh -c 'if head|grep ...'`` wrapper. The
    earlier wrapper form caused two live capture MISSES: (a) the traced top-level
    process was the wrapper shell, and the artifact's re-exec subtree (a ``#!/bin/sh``
    artifact execs into another sh that does the real work) was unreliably followed;
    (b) the ``head -c2 | grep`` pipeline ran as forked children that dominated the
    (truncated) slice. Fixes:
      * Decide the interpreter OUTSIDE the traced process (a plain ``sh -c`` around the
        whole thing is fine; the shebang test is done in the OUTER shell so strace's
        argv[0] is the artifact/interpreter itself).
      * ``strace -ff -o PREFIX`` writes ONE trace file PER PID (``PREFIX.<pid>``), so a
        forked/exec'd child's trace is on its own file and cannot be lost to another
        process's buffering; the caller concatenates ``PREFIX.*``.
      * ``sync`` after strace exits so every per-PID file is flushed to disk before the
        caller reads it (the earlier single-file form sliced a partially-flushed file).
    The artifact's own rc is preserved in ``__ZTIE_RC`` so the 2.3 outcome mapping is
    unaffected by instrumentation.
    """
    q = shlex.quote(artifact_path)
    prefix = shlex.quote(_TRACE_PREFIX)
    errf = shlex.quote(_STRACE_STDERR_FILE)
    # ``timeout -k GRACE BUDGET`` BOUNDS the traced run (Story 2.4R SEALED FAIL, attempt
    # 4): a hanging/blocking artifact (e.g. a bash ``/dev/tcp`` connect in the egress-less
    # VPC) must NOT be allowed to run until the SSM executionTimeout SIGKILLs the whole
    # wrapper — that loses the trace + never runs the emit block. ``timeout`` wraps STRACE
    # (the tracer's own process), so terminating it terminates the traced child too and
    # strace flushes its ``-o`` per-PID files on exit; the WRAPPER then survives to emit
    # them. SIGTERM at BUDGET, SIGKILL at BUDGET+GRACE if it ignores TERM (a process
    # blocked in connect() with a held fd usually needs the KILL). Budget+grace stays well
    # under EXEC_TIMEOUT_S so SSM never kills the wrapper.
    # Story 2.4R attempt-6 (RD-057): ``setsid timeout --kill-after=GRACE BUDGET strace …``.
    # ``setsid`` makes the timed command a NEW session/process-group leader, so when GNU
    # ``timeout`` fires it terminates the WHOLE group — strace AND the artifact's re-exec
    # grandchild (the one that blocks in connect()) — not just strace. Attempt 5 proved a
    # plain ``timeout -k`` signals only its direct child (strace), leaving the grandchild
    # alive to hold the SSM stdout pipe open. ``--kill-after`` is the explicit long form of
    # ``-k`` (SIGKILL GRACE seconds after the initial SIGTERM if the group ignores TERM).
    to = f"setsid timeout --kill-after={ARTIFACT_EXEC_KILL_GRACE_S} {ARTIFACT_EXEC_TIMEOUT_S}"
    # STDIO DETACH: redirect the traced program's OWN stdout+stderr to host-local files so
    # NO artifact child inherits (and can hold open) the SSM command's stdout pipe. Once
    # the group is killed, the SSM pipe has no remaining writer -> the agent gets EOF and
    # the WRAPPER regains control to run the emit block. Without this, a lingering child
    # kept the pipe open and the wrapper hung to the 120 s SSM ceiling (attempt 5).
    aout = shlex.quote(_ARTIFACT_STDOUT_FILE)
    aerr = shlex.quote(_ARTIFACT_STDERR_FILE)
    # Trace the artifact directly: if it has a shebang, strace runs it as the program;
    # otherwise strace runs `/bin/sh <artifact>` as the program. Either way strace's
    # traced argv[0] is the real interpreter, so -ff follows the true work subtree.
    # strace's OWN stderr (startup diagnostics like a rejected -e expression) is
    # redirected to a host file (``errf``) so a no-trace failure can be explained, not
    # silent (Story 2.4R FAIL #2). With ``-o PREFIX`` the trace goes to per-PID files, so
    # the redirections here only touch strace's own fd 2 (diagnostics) and the ARTIFACT's
    # inherited stdout/stderr — never the trace itself. The artifact's stdout is sent to a
    # host file (``1> aout``); strace's diagnostics + the artifact's stderr go to host
    # files too — none touch the SSM command pipe.
    strace_direct = (
        f"{to} strace -ff -tt -y -s 256 -o {prefix} -e {_STRACE_TRACE_GROUPS} {q} "
        f"1> {aout} 2> {errf}"
    )
    strace_via_sh = (
        f"{to} strace -ff -tt -y -s 256 -o {prefix} -e {_STRACE_TRACE_GROUPS} "
        f"/bin/sh {q} 1> {aout} 2> {errf}"
    )
    # NOTE: the artifact's own stderr is folded into strace's traced program stderr file
    # (_STRACE_STDERR_FILE) only for the direct/`via_sh` program; strace writes its trace
    # to -o per-PID files regardless. _ARTIFACT_STDERR_FILE is reserved for the
    # uninstrumented path below (kept symmetric + host-local).
    _ = aerr
    return [
        "echo '=== ZTIE detonation: begin (instrumented) ==='",
        f"chmod +x {q} 2>/dev/null || true",
        # Shebang decision in the OUTER (untraced) shell so the traced program is the
        # artifact/interpreter itself, not a wrapper. Preserve the (possibly
        # timeout-forced) exit code in __ZTIE_RC so the 2.3 outcome mapping + the capture
        # note reflect a time-bounded run honestly (timeout exits 124 on TERM at BUDGET).
        f"if head -c2 {q} | grep -q '^#!'; then {strace_direct}; else {strace_via_sh}; fi",
        "__ZTIE_RC=$?",
        # Emit a distinctive marker when the artifact was time-bounded so the orchestrator
        # can record capture health honestly (the trace, if any, is still on disk below).
        f'if [ "$__ZTIE_RC" = "{ARTIFACT_TIMEOUT_RC}" ]; then echo {shlex.quote(ARTIFACT_TIMED_OUT_MARKER)}; fi',
        # Flush every per-PID trace file to disk before the caller reads them.
        "sync",
        "echo \"=== ZTIE detonation: end rc=$__ZTIE_RC ===\"",
    ]


def _uninstrumented_exec_commands(artifact_path: str) -> list[str]:
    """The plain host-native execution (strace absent) — identical to runspec's
    execution so the detonation still runs and the 2.3 outcome is still produced;
    only the behavioral capture is skipped (recorded as tool_unavailable)."""
    q = shlex.quote(artifact_path)
    # Same session-wide bound + stdio detach as the instrumented path (Story 2.4R attempt-6,
    # RD-057): ``setsid timeout --kill-after=GRACE BUDGET`` so a hanging artifact's whole
    # process group is killed (not just the direct child), and the artifact's stdout/stderr
    # go to host-local files so no lingering child holds the SSM command pipe open. There is
    # no trace to preserve here, but the wrapper must still survive to emit the end banner +
    # the artifact's rc — the same failure (attempt 5) applies if a missing-strace host runs
    # a hanging artifact.
    to = f"setsid timeout --kill-after={ARTIFACT_EXEC_KILL_GRACE_S} {ARTIFACT_EXEC_TIMEOUT_S}"
    aout = shlex.quote(_ARTIFACT_STDOUT_FILE)
    aerr = shlex.quote(_ARTIFACT_STDERR_FILE)
    io = f"1> {aout} 2> {aerr}"
    return [
        f"echo {shlex.quote(TOOL_UNAVAILABLE_MARKER)}",
        "echo '=== ZTIE detonation: begin (uninstrumented; no capture tool) ==='",
        f"chmod +x {q} 2>/dev/null || true",
        f"if head -c2 {q} | grep -q '^#!'; then {to} {q} {io}; else {to} /bin/sh {q} {io}; fi",
        "__ZTIE_RC=$?",
        f'if [ "$__ZTIE_RC" = "{ARTIFACT_TIMEOUT_RC}" ]; then echo {shlex.quote(ARTIFACT_TIMED_OUT_MARKER)}; fi',
        "echo \"=== ZTIE detonation: end rc=$__ZTIE_RC ===\"",
    ]


def build_trace_upload_commands(*, bucket: str, intake_id: str) -> list[str]:
    """Story 2.4S / Fix B (RD-058): upload the ``strace -o`` per-PID trace files DIRECTLY
    to Forensic S3 (``s3://<bucket>/traces/{intake_id}/``) from the HOST, the moment strace
    exits and BEFORE the fragile stdout emit block — so trace SURVIVAL does not depend on
    the wrapper surviving or on the SSM stdout pipe reaching EOF (attempts 1-6 hung there).

    Ordered semantics (the completeness contract the Lambda relies on):
      1. echo the BEGIN marker (best-effort stdout visibility only).
      2. ``aws s3 cp`` EACH per-PID file ``PREFIX.<pid>`` to ``traces/{intake_id}/`` (over
         the S3 VPC gateway endpoint; NO public egress). Guarded so an empty capture (no
         per-PID files) is a clean no-op, never a failure.
      3. Write the completeness SENTINEL object (``traces/{intake_id}/_UPLOAD_COMPLETE``)
         LAST. Its presence in S3 is the durable, out-of-band signal that every per-PID
         file the host had was copied — the Lambda checks S3 for this, never stdout.
      4. echo the UPLOADED marker (best-effort visibility only).

    Pure: returns the command list (no AWS calls here — the HOST runs these over SSM). The
    upload is a `` || true`` best-effort per file so a single slow/failed copy cannot hang
    or fail the wrapper; the sentinel is only written if the copies ran, so a partial upload
    is distinguishable (per-PID objects present, sentinel ABSENT) from a complete one.
    """
    prefix = shlex.quote(_TRACE_PREFIX)
    # s3:// destination for this intake's traces. intake_id is a validated UUID upstream;
    # shlex.quote it anyway (defence in depth — it becomes part of a shell command).
    dest = shlex.quote(f"s3://{bucket}/{TRACES_PREFIX_REL}{intake_id}/")
    sentinel_dest = shlex.quote(
        f"s3://{bucket}/{TRACES_PREFIX_REL}{intake_id}/{TRACE_UPLOAD_COMPLETE_SENTINEL}"
    )
    return [
        f"echo {shlex.quote(TRACE_UPLOAD_BEGIN_MARKER)}",
        # Copy every per-PID trace file to S3. `aws s3 cp <dir-or-glob>` needs a loop for a
        # glob; iterate so each file lands under traces/{intake_id}/<basename>. The `ls`
        # is guarded so no per-PID file is a clean skip (empty capture). Per-file `|| true`
        # so one failed copy never aborts the wrapper (best-effort durability).
        (
            f"for __t in $(ls {prefix}.* 2>/dev/null); do "
            f'aws s3 cp "$__t" {dest} --only-show-errors || true; '
            f"done"
        ),
        # Write the completeness sentinel LAST (out-of-band signal the Lambda reads from S3).
        # `printf | aws s3 cp -` writes a tiny object without needing a temp file.
        f"printf %s 'complete' | aws s3 cp - {sentinel_dest} --only-show-errors || true",
        f"echo {shlex.quote(TRACE_UPLOADED_MARKER)}",
    ]


def build_capture_run_commands(
    *, artifact_path: str, bucket: str | None = None, intake_id: str | None = None
) -> list[str]:
    """Build the ordered host-native command list that runs the artifact UNDER
    capture and emits the trace between markers.

    Story 2.4S / Fix B (RD-058): when ``bucket`` + ``intake_id`` are supplied, the strace
    per-PID files are ALSO uploaded directly to Forensic S3 (``traces/{intake_id}/``) the
    moment strace exits and BEFORE the stdout emit block, so the trace survives even if the
    wrapper is later killed / the SSM stdout pipe never reaches EOF (attempts 1-6). The
    stdout emit block is retained as a best-effort fallback for hosts/runs where S3 upload
    is unavailable. When ``bucket``/``intake_id`` are omitted, behavior is unchanged
    (stdout-only), keeping the function backward-compatible for callers/tests.

    Structure (all host-native over SSM, NO Docker):
      1. Probe for ``strace`` on the host (PATH lookup).
      2. If present -> run the artifact under strace (file/network/process groups),
         then emit the (on-host-capped) trace between BEGIN/END markers.
      3. If absent  -> emit TOOL_UNAVAILABLE_MARKER, run the artifact uninstrumented
         (so the detonation still happens), and emit NO trace.
      4. Always ``exit $__ZTIE_RC`` so the artifact's own exit code is what SSM sees
         (the 2.3 outcome mapping is unchanged by instrumentation).

    Pure: returns the command list; the caller (awsio.send_command) ships it via SSM
    and slices the trace out of the returned output with the markers. The 5-min hard
    TTL bounds the run regardless of what the artifact does.
    """
    prefix = _TRACE_PREFIX
    begin = shlex.quote(TRACE_BEGIN_MARKER)
    end = shlex.quote(TRACE_END_MARKER)

    commands = [
        "set -u",
        f"mkdir -p {shlex.quote(_STAGE_DIR)}",
        # Probe for strace; branch on availability so a missing capture tool never
        # blocks the detonation itself.
        "if command -v strace >/dev/null 2>&1; then",
    ]
    commands += [f"  {c}" for c in _instrumented_exec_commands(artifact_path)]
    # Story 2.4S / Fix B (RD-058): upload the per-PID trace files DIRECTLY to Forensic S3
    # RIGHT HERE — after strace exited + ``sync`` flushed the files, and BEFORE the fragile
    # stdout emit block below. This is the whole point of Fix B: the trace is durable in S3
    # the moment strace finishes, so even if the emit block / SSM stdout pipe hangs (attempts
    # 1-6) and the wrapper is later SIGKILLed, the evidence already crossed to S3 and the
    # Lambda reads it from there. Only spliced when the caller supplied bucket + intake_id;
    # otherwise the stdout path is the sole transport (backward-compatible).
    if bucket and intake_id:
        commands += [
            f"  {c}"
            for c in build_trace_upload_commands(bucket=bucket, intake_id=intake_id)
        ]
    # Emit the trace between markers, capped on-host so the returned output is
    # bounded. strace -ff writes ONE file per traced PID (``PREFIX.<pid>``). We cap
    # EACH per-PID file INDEPENDENTLY (``head -c PER_PID``) as we concatenate, so
    # every PID — including the artifact's own — is represented in the emitted slice.
    # This is the Story 2.4R fix: the earlier single ``head -c`` over the whole
    # lexically-sorted concatenation let a noisy low-sorting sibling PID consume the
    # entire budget and truncate the artifact's own trace out. A trailing overall
    # ``head -c`` remains as a HARD BACKSTOP so the returned output is still bounded
    # even with many PIDs. Files are sorted NUMERICALLY by PID (``sort -t. -k<n>n``)
    # for stable, human-readable ordering (lexical sort would put PREFIX.1000 before
    # PREFIX.999). The FULL per-PID files remain on the host (wiped at TTL); the
    # Lambda persists what it receives to Forensic S3. The glob is guarded by
    # ``2>/dev/null`` + a trailing ``|| true`` so an empty capture never fails.
    #
    # ``_TRACE_PREFIX`` is ``/tmp/ztie/behavior.strace`` — split on ``.`` that is
    # ``/tmp/ztie/behavior`` | ``strace`` | ``<pid>``, so the PID is field 3.
    # ``sort -t. -k3,3n`` orders numerically by the PID suffix (so PREFIX.999 sorts
    # before PREFIX.1000, unlike a lexical sort). Kept general via ``count('.')+2``.
    pid_field = _TRACE_PREFIX.count(".") + 2
    errf = shlex.quote(_STRACE_STDERR_FILE)
    diag = shlex.quote(STRACE_NO_TRACE_DIAG_MARKER)
    per_pid_emit = (
        f"for __f in $(ls {shlex.quote(prefix)}.* 2>/dev/null "
        f"| sort -t. -k{pid_field},{pid_field}n); do "
        f'echo "=== ZTIE trace file: $__f ==="; '
        f'head -c {ON_HOST_TRACE_PER_PID_CAP_BYTES} "$__f"; '
        f"done 2>/dev/null"
    )
    # SELF-DIAGNOSING no-trace path (Story 2.4R FAIL #2): if strace produced NO per-PID
    # file, the emit above is empty and the record would be a silent capture_error. So
    # if the glob matches nothing, emit a diagnostic marker + strace's own stderr
    # (capped) between the markers instead, so the crossed record shows WHY (e.g. a
    # rejected -e expression). ``ls`` deciding presence is the same glob the emit uses.
    emit_or_diag = (
        f"if ls {shlex.quote(prefix)}.* >/dev/null 2>&1; then "
        f"{{ {per_pid_emit} | head -c {ON_HOST_TRACE_CAP_BYTES} ; }} || true; "
        f"else "
        f"echo {diag}; "
        f"head -c {ON_HOST_TRACE_PER_PID_CAP_BYTES} {errf} 2>/dev/null || true; "
        f"fi"
    )
    commands += [
        f"  echo {begin}",
        f"  {emit_or_diag}",
        f"  echo {end}",
        "else",
    ]
    commands += [f"  {c}" for c in _uninstrumented_exec_commands(artifact_path)]
    commands += [
        "fi",
        "exit $__ZTIE_RC",
    ]
    return commands


def slice_trace(stdout: str | None) -> tuple[str | None, bool]:
    """Slice the behavioral trace out of the combined SSM command stdout.

    Returns (trace, tool_unavailable):
      * trace is the text BETWEEN the BEGIN/END markers (the raw host trace), or
        None when no trace was emitted (tool unavailable, or capture produced none).
      * tool_unavailable is True iff the host reported the capture tool was missing
        (the TOOL_UNAVAILABLE_MARKER was emitted) — the orchestrator maps that to
        capture_status=tool_unavailable (a recorded gap, never a silent one).

    Pure and offline-testable. Tolerates the markers being absent (returns
    (None, ...)) so a malformed/empty output can never crash the parse.
    """
    text = stdout or ""
    tool_unavailable = TOOL_UNAVAILABLE_MARKER in text
    begin = text.find(TRACE_BEGIN_MARKER)
    if begin == -1:
        return None, tool_unavailable
    start = begin + len(TRACE_BEGIN_MARKER)
    end = text.find(TRACE_END_MARKER, start)
    if end == -1:
        # BEGIN seen but END missing (output truncated mid-trace) — take the tail
        # after BEGIN as a best-effort trace; caller records trace_truncated.
        return text[start:].strip("\n"), tool_unavailable
    return text[start:end].strip("\n"), tool_unavailable


def no_trace_diagnostic(trace: str | None) -> str | None:
    """If the sliced trace is the SELF-DIAGNOSING no-trace payload (strace ran but
    produced no per-PID file, so the emitter shipped the diagnostic marker + strace's
    own stderr instead), return the stderr text (bounded) for the caller to record as
    the ``capture_error`` reason. Otherwise return None (it is a real trace, or empty).

    Pure and offline-testable. This is how a no-trace capture becomes SELF-EXPLAINING
    on the crossed record instead of a silent ``capture_error`` (Story 2.4R FAIL #2)."""
    if not trace:
        return None
    stripped = trace.lstrip("\n")
    if not stripped.startswith(STRACE_NO_TRACE_DIAG_MARKER):
        return None
    detail = stripped[len(STRACE_NO_TRACE_DIAG_MARKER):].strip()
    # Bound what we record as the reason (the contract error_reason is length-capped
    # by build_capture; keep this tidy). Collapse to a single line for the record.
    detail = " ".join(detail.split())
    return detail[:400] if detail else "strace produced no trace files (no stderr captured)"


def artifact_timed_out(stdout: str | None) -> bool:
    """True iff the host emitted the ARTIFACT_TIMED_OUT_MARKER — the artifact run hit the
    inner ``timeout`` (it hung/blocked, e.g. a ``/dev/tcp`` connect with no egress) and
    was terminated so the wrapper could survive to emit the trace (Story 2.4R attempt-4
    fix). The orchestrator records this as an honest capture-health fact; it is EVIDENCE
    of a hanging artifact, NEVER a verdict. Pure and offline-testable."""
    return ARTIFACT_TIMED_OUT_MARKER in (stdout or "")
