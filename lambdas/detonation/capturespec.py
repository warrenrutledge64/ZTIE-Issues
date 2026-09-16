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

import shlex

# Where the artifact + its trace are staged on the ephemeral host (host-local
# scratch, wiped on the hard-TTL teardown). Mirrors runspec._STAGE_DIR.
_STAGE_DIR = "/tmp/ztie"
# strace -ff writes ONE file per traced PID named ``<prefix>.<pid>``. We concatenate
# ``<prefix>.*`` when emitting, so a forked/exec'd child's trace is never lost to
# another process's output buffering (the single-file form truncated live).
_TRACE_PREFIX = f"{_STAGE_DIR}/behavior.strace"


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

# The strace syscall groups we trace:
#   %file    — path-taking syscalls (open/openat/unlink/rename/chmod-by-path...).
#   %desc    — file-DESCRIPTOR syscalls (write/writev/pwrite64/read/fchmod...). This
#              group is REQUIRED to capture a write of a data buffer: ``write`` et al.
#              take an fd, NOT a filename, so they are NOT in %file. Without %desc the
#              artifact's own ``write()`` of a planted buffer is never recorded (the
#              Story 2.4R live FAIL, 2026-09-16: the buffer syscall was missing from
#              the trace entirely). The behavior.py parser reads the PATH for these
#              fd-based ops from the ``-y`` fd decoration, never from the data buffer.
#   %network — socket/connect/sendto/recvfrom... (network capture = INTENT).
#   %process — execve/clone/fork/exit... (the process tree).
#   %signal  — signal delivery/handling.
# ``-ff`` follows children into per-PID files (an artifact that forks), ``-tt`` gives
# microsecond timestamps for ordering, ``-y`` decodes fds to paths where possible.
_STRACE_TRACE_GROUPS = "trace=%file,%desc,%network,%process,%signal"


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
    # Trace the artifact directly: if it has a shebang, strace runs it as the program;
    # otherwise strace runs `/bin/sh <artifact>` as the program. Either way strace's
    # traced argv[0] is the real interpreter, so -ff follows the true work subtree.
    strace_direct = (
        f"strace -ff -tt -y -s 256 -o {prefix} -e {_STRACE_TRACE_GROUPS} {q}"
    )
    strace_via_sh = (
        f"strace -ff -tt -y -s 256 -o {prefix} -e {_STRACE_TRACE_GROUPS} /bin/sh {q}"
    )
    return [
        "echo '=== ZTIE detonation: begin (instrumented) ==='",
        f"chmod +x {q} 2>/dev/null || true",
        # Shebang decision in the OUTER (untraced) shell so the traced program is the
        # artifact/interpreter itself, not a wrapper. Preserve the artifact's exit
        # code in __ZTIE_RC so the 2.3 outcome mapping is unaffected by capture.
        f"if head -c2 {q} | grep -q '^#!'; then {strace_direct}; else {strace_via_sh}; fi",
        "__ZTIE_RC=$?",
        # Flush every per-PID trace file to disk before the caller reads them.
        "sync",
        "echo \"=== ZTIE detonation: end rc=$__ZTIE_RC ===\"",
    ]


def _uninstrumented_exec_commands(artifact_path: str) -> list[str]:
    """The plain host-native execution (strace absent) — identical to runspec's
    execution so the detonation still runs and the 2.3 outcome is still produced;
    only the behavioral capture is skipped (recorded as tool_unavailable)."""
    q = shlex.quote(artifact_path)
    return [
        f"echo {shlex.quote(TOOL_UNAVAILABLE_MARKER)}",
        "echo '=== ZTIE detonation: begin (uninstrumented; no capture tool) ==='",
        f"chmod +x {q} 2>/dev/null || true",
        f"if head -c2 {q} | grep -q '^#!'; then {q}; else /bin/sh {q}; fi",
        "__ZTIE_RC=$?",
        "echo \"=== ZTIE detonation: end rc=$__ZTIE_RC ===\"",
    ]


def build_capture_run_commands(*, artifact_path: str) -> list[str]:
    """Build the ordered host-native command list that runs the artifact UNDER
    capture and emits the trace between markers.

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
    # ``_TRACE_PREFIX`` is ``/tmp/ztie/behavior.strace`` (4 dot-separated fields), so
    # the PID is field 5 — ``sort -t. -k5,5n`` orders by the numeric PID suffix.
    pid_field = _TRACE_PREFIX.count(".") + 2
    per_pid_emit = (
        f"for __f in $(ls {shlex.quote(prefix)}.* 2>/dev/null "
        f"| sort -t. -k{pid_field},{pid_field}n); do "
        f'echo "=== ZTIE trace file: $__f ==="; '
        f'head -c {ON_HOST_TRACE_PER_PID_CAP_BYTES} "$__f"; '
        f"done 2>/dev/null"
    )
    commands += [
        f"  echo {begin}",
        f"  {{ {per_pid_emit} | head -c {ON_HOST_TRACE_CAP_BYTES} ; }} || true",
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
