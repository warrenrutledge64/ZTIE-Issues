"""ZTIE Story 2.1 — scanner invocation seam (subprocess lives HERE).

The four static tools are invoked here, behind a thin seam, so the normalization
logic (``normalize.py``) stays pure and offline-testable. Every invocation is
NON-EXECUTING: the tool PARSES / INSPECTS the artifact file on disk; the artifact
itself is NEVER run. There is no ``shell=True``, no interpreter invoked on the
artifact, no ``eval`` — the artifact path is only ever passed as a data argument to
a scanner.

Resilience (DoD: "does not crash on a scanner error"): each ``run_*`` returns a
``ScanResult`` and NEVER raises. A crash, non-JSON output, timeout, or missing
binary is captured as ``status="error"`` with a bounded reason; the caller records
it and runs the other tools regardless.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

from normalize import (
    BANDIT,
    CFN_GUARD,
    CFN_LINT,
    CHECKOV,
    normalize_tool_output,
)

# Per-tool wall-clock budget. A tool that hangs is killed and recorded as an error
# rather than blocking the lane.
_DEFAULT_TIMEOUT_S = 120


@dataclass
class ScanResult:
    """Outcome of one tool invocation. ``findings`` is already normalized."""

    tool: str
    status: str  # "ok" | "error"
    findings: list[dict[str, Any]] = field(default_factory=list)
    error_reason: str | None = None
    duration_ms: int = 0


def _run(
    tool: str,
    argv: list[str],
    *,
    # cfn-guard/cfn-lint/checkov/bandit exit NON-ZERO when they FIND issues; a
    # non-zero exit is therefore NOT an error for these tools. Only a signal /
    # crash / unparsable output is an error. ``ok_exit_is_findings`` documents that.
    timeout_s: int = _DEFAULT_TIMEOUT_S,
) -> tuple[str, str, int | None]:
    """Invoke a tool, capturing stdout/stderr/returncode. Never raises.

    Returns (stdout, stderr, returncode); returncode is None on timeout / spawn
    failure. NON-EXECUTING: ``argv`` is a fixed program + flags + the artifact PATH
    as data; the artifact is never executed and ``shell`` is never used.
    """
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        return proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired:
        return "", f"timeout after {timeout_s}s", None
    except FileNotFoundError:
        return "", f"{tool} binary not found", None
    except Exception as exc:  # noqa: BLE001 - never let a spawn failure crash the lane
        return "", f"spawn failed: {exc}", None


def _result_from_output(
    tool: str,
    stdout: str,
    stderr: str,
    returncode: int | None,
    duration_ms: int,
) -> ScanResult:
    """Turn a raw invocation into a normalized ScanResult.

    A None returncode (timeout / spawn failure) is an error. Otherwise the output
    is normalized; if the tool exited non-zero AND produced no parseable findings
    AND wrote to stderr, that is treated as an error (the tool failed rather than
    'found issues'). A tool that ran and produced parseable JSON is ``ok`` even on a
    non-zero exit (these tools exit non-zero when they find issues).
    """
    if returncode is None:
        return ScanResult(
            tool=tool,
            status="error",
            error_reason=(stderr or "invocation failed")[:512],
            duration_ms=duration_ms,
        )
    findings = normalize_tool_output(tool, stdout)
    if not findings and returncode != 0 and not stdout.strip():
        # No output at all + non-zero exit -> the tool errored (e.g. bad args,
        # crash) rather than cleanly finding nothing.
        return ScanResult(
            tool=tool,
            status="error",
            error_reason=(stderr.strip() or f"exit {returncode}, no output")[:512],
            duration_ms=duration_ms,
        )
    return ScanResult(
        tool=tool,
        status="ok",
        findings=findings,
        duration_ms=duration_ms,
    )


def _timed(tool: str, argv: list[str], timeout_s: int) -> ScanResult:
    start = time.monotonic()
    stdout, stderr, rc = _run(tool, argv, timeout_s=timeout_s)
    duration_ms = int((time.monotonic() - start) * 1000)
    return _result_from_output(tool, stdout, stderr, rc, duration_ms)


# --- Per-tool invocations (NON-EXECUTING: artifact path passed as data) -------


def run_cfn_lint(artifact_path: str, timeout_s: int = _DEFAULT_TIMEOUT_S) -> ScanResult:
    """cfn-lint over the template file. `--format json` -> array of matches."""
    return _timed(CFN_LINT, ["cfn-lint", "--format", "json", artifact_path], timeout_s)


def run_bandit(artifact_path: str, timeout_s: int = _DEFAULT_TIMEOUT_S) -> ScanResult:
    """bandit Python SAST over the script file. `-f json`. bandit exits 1 when it
    finds issues; that is 'ok' (findings), not an error."""
    return _timed(BANDIT, ["bandit", "-f", "json", "-q", artifact_path], timeout_s)


def run_checkov(artifact_path: str, timeout_s: int = _DEFAULT_TIMEOUT_S) -> ScanResult:
    """checkov over a single file. `-o json --compact`; `-f` scans one file
    (non-executing static config/IaC scan)."""
    return _timed(
        CHECKOV,
        ["checkov", "-f", artifact_path, "-o", "json", "--compact"],
        timeout_s,
    )


def run_cfn_guard(
    artifact_path: str,
    rules_path: str,
    timeout_s: int = _DEFAULT_TIMEOUT_S,
) -> ScanResult:
    """cfn-guard policy-as-code over the template. SARIF output (stable across
    versions). Requires a rules file (`--rules`).

    cfn-guard 3.x requires the ``--structured`` flag whenever the output format is
    a machine format (sarif/json); without it the tool errors
    ("the structured flag must be set when output is set to sarif"). ``--structured``
    ALSO requires the summary to be explicitly disabled — with ``--structured`` set,
    cfn-guard rejects any ``--show-summary`` value other than ``none`` ("Cannot
    provide a summary-type other than `none` when the `structured` flag is
    present"), and its default summary is not ``none``. So we must pass BOTH
    ``--structured`` and ``--show-summary none`` to get pure SARIF on stdout."""
    return _timed(
        CFN_GUARD,
        [
            "cfn-guard",
            "validate",
            "--data",
            artifact_path,
            "--rules",
            rules_path,
            "--output-format",
            "sarif",
            "--structured",
            "--show-summary",
            "none",
        ],
        timeout_s,
    )
