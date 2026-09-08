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
_TRACE_FILE = f"{_STAGE_DIR}/behavior.strace"


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

# The strace syscall groups we trace: file (open/write/unlink/rename/chmod...),
# network (socket/connect/sendto/recvfrom...), and process (execve/clone/fork...).
# ``-f`` follows children (an artifact that forks), ``-tt`` gives relative-ish
# microsecond timestamps for ordering, ``-y`` decodes fds to paths where possible.
_STRACE_TRACE_GROUPS = "trace=%file,%network,%process,%signal"


def _instrumented_exec_commands(artifact_path: str) -> list[str]:
    """The strace-wrapped host-native execution of the artifact (when strace exists).

    strace runs the SAME execution runspec would (shebang -> direct, else /bin/sh),
    writing the trace to a file, following forks. The artifact's own rc is preserved
    so the run outcome (2.3) is unchanged by instrumentation.
    """
    q = shlex.quote(artifact_path)
    trace = shlex.quote(_TRACE_FILE)
    strace_cmd = (
        f"strace -f -tt -y -s 256 -o {trace} -e {_STRACE_TRACE_GROUPS} "
        f"/bin/sh -c 'if head -c2 {q} | grep -q \"^#!\"; then {q}; "
        f"else /bin/sh {q}; fi'"
    )
    return [
        "echo '=== ZTIE detonation: begin (instrumented) ==='",
        f"chmod +x {q} 2>/dev/null || true",
        # Run the artifact under strace. Preserve the artifact's exit code in
        # __ZTIE_RC so the 2.3 outcome mapping is unaffected by capture.
        f"{strace_cmd}",
        "__ZTIE_RC=$?",
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
    trace = shlex.quote(_TRACE_FILE)
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
    # bounded. The FULL trace file remains on the host (wiped at TTL) and the Lambda
    # persists what it receives to Forensic S3.
    commands += [
        f"  echo {begin}",
        f"  head -c {ON_HOST_TRACE_CAP_BYTES} {trace} 2>/dev/null || true",
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
