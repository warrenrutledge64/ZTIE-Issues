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

    curl is present on the golden AMI. --fail so a bad fetch is a non-zero exit the
    orchestrator sees as a delivery/execution error rather than a silent empty run.
    """
    return [
        "set -u",
        f"mkdir -p {shlex.quote(_STAGE_DIR)}",
        # -sS quiet but show errors; --fail non-2xx -> non-zero exit; -L follow.
        f"curl -sS --fail -L -o {shlex.quote(dest_path)} {shlex.quote(presigned_url)}",
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
