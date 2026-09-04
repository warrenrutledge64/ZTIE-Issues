"""ZTIE Story 2.3 — PURE run-spec derivation for the dynamic (detonation) lane.

I/O-free and offline-unit-testable. Given the artifact's filename + class, derive
the host-native shell commands the ephemeral EC2 will run over SSM to (1) pull the
artifact from Forensic S3 via a presigned URL over the S3 VPC endpoint, and (2)
EXECUTE it directly on the host (NO Docker — RD-001). It makes NO AWS calls and
reaches NO verdict; it only shapes the command list.

The presigned URL is injected by the caller at run time (it is a short-lived
Forensic-internal credential, never logged into the crossed outcome).
"""

from __future__ import annotations

import shlex

# The class labels the router can hand to this lane (from Story 1.2 / 1.3).
IAC_TEMPLATE = "iac_template"
RAW_SCRIPT = "raw_script"

# Where the artifact is staged on the ephemeral host (host-local scratch, wiped on
# the hard-TTL teardown).
_STAGE_DIR = "/tmp/ztie"


def _download_commands(presigned_url: str, dest_path: str) -> list[str]:
    """Commands to fetch the artifact onto the host over the S3 VPC endpoint.

    curl is present on the golden AMI. Hard-bounded so a fetch that cannot reach S3
    (e.g. a routing/DNS problem in the isolated VPC) FAILS FAST with a diagnosable
    exit code, instead of hanging until the 5-minute hard TTL SIGKILLs the command
    (which surfaced as ``TimedOut`` / rc137 / empty output — indistinguishable from a
    real long-running artifact). Flags:
      --connect-timeout 10 : give up if S3 is not reachable within 10s
      --max-time 60        : cap the whole transfer at 60s
      --retry 2            : ride out a transient blip
      --fail               : non-2xx -> non-zero exit (a delivery failure is visible)
      -v to a log file     : capture curl's own diagnostics on the host for triage
    """
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


def build_run_commands(
    *, filename: str, artifact_class: str, presigned_url: str
) -> list[str]:
    """Build the ordered host-native shell command list for one detonation.

    - Stages the artifact from the presigned Forensic URL.
    - EXECUTES it host-native (no container): a raw_script is made executable and
      run (interpreter inferred from shebang, else /bin/sh); anything else is run
      through /bin/sh as a best-effort. This is the first place ZTIE actually RUNS
      the artifact — inside the isolated, ephemeral, self-terminating host.

    Pure: returns the command list; the caller sends it via SSM. The hard TTL
    (`shutdown -h +5` from the 2.0 UserData) bounds the run no matter what these do.
    """
    dest = f"{_STAGE_DIR}/artifact"
    if filename:
        # Keep the original name so shebang/extension-based execution behaves.
        safe = filename.rsplit("/", 1)[-1]
        dest = f"{_STAGE_DIR}/{safe}"

    commands = _download_commands(presigned_url, dest)
    q = shlex.quote(dest)

    # Detonate. We echo clear markers so the captured log is easy to bound/triage.
    commands += [
        "echo '=== ZTIE detonation: begin ==='",
        f"chmod +x {q} 2>/dev/null || true",
        # If it has a shebang, execute directly; otherwise run through /bin/sh.
        (
            f"if head -c2 {q} | grep -q '^#!'; then {q}; "
            f"else /bin/sh {q}; fi"
        ),
        "__ZTIE_RC=$?",
        "echo \"=== ZTIE detonation: end rc=$__ZTIE_RC ===\"",
        "exit $__ZTIE_RC",
    ]
    return commands
