"""ZTIE Story 2.3 — PURE run-outcome builders for the dynamic (detonation) lane.

This module is deliberately I/O-free and offline-unit-testable (the proven
1.2 -> 2.2 lane pattern: pure logic + a thin boto3 seam). It contains NO boto3, no
AWS calls, no clock reads beyond what the caller passes in — every value it needs is
handed in as an argument. Its only job is to assemble the bounded, DERIVED,
verdict-free run-outcome envelope that crosses the Forensic -> Hub RD-013 gate
(``dynamic-run.contract.v1``), and to enforce the contract's bounds (byte-capped
tails, allow-listed enums) in code so a malformed outcome can never be shaped here.

Zero-trust invariants baked in here (mirrors the contract):
  * EVIDENCE, never a verdict. There is NO verdict / safe / approved / forward field
    anywhere in what this builds. ``outcome`` describes how the ORCHESTRATION ended,
    never whether the artifact is safe.
  * CONTAINED + EPHEMERAL. The containment facts are asserted as constants
    (host-native, no Docker, isolated subnet, no public IP, IMDSv2) — this lane
    cannot emit an outcome that claims the run was uncontained.
  * DERIVED-ONLY + BOUNDED. The stdout/stderr tails that cross are hard byte-capped
    (``MAX_OUTPUT_TAIL``); the full log stays in Forensic behind a pointer.
"""

from __future__ import annotations

from typing import Any

# The lane id (must match the routing contract + the dynamic-run contract enum).
LANE = "dynamic_detonation"

# Contract-mirrored enums (kept in lockstep with gen_dynamic_run_contract.py).
OUTCOME_COMPLETED = "completed"
OUTCOME_EXECUTION_ERROR = "execution_error"
OUTCOME_LAUNCH_ERROR = "launch_error"
OUTCOME_TIMED_OUT = "timed_out"
OUTCOME_DELIVERY_ERROR = "delivery_error"
OUTCOMES = (
    OUTCOME_COMPLETED,
    OUTCOME_EXECUTION_ERROR,
    OUTCOME_LAUNCH_ERROR,
    OUTCOME_TIMED_OUT,
    OUTCOME_DELIVERY_ERROR,
)

# The SSM invocation statuses (AWS's own set) + our sentinel for "never executed".
SSM_STATUS_NOT_RUN = "not_run"
SSM_STATUSES = (
    "Success",
    "Failed",
    "Cancelled",
    "TimedOut",
    "Undelivered",
    "Terminated",
    "Pending",
    "InProgress",
    "Delayed",
    SSM_STATUS_NOT_RUN,
)

# Hard byte cap on the crossed stdout/stderr tails (matches the contract maxLength).
MAX_OUTPUT_TAIL = 4096

# SSM statuses that mean the host-native command reached a *successful* terminal
# state. Used only to map to the orchestration outcome; NOT a verdict.
_SSM_SUCCESS = "Success"
# SSM statuses that mean the command was accepted+ran but ended unsuccessfully
# (i.e. the artifact ran and errored). Still EVIDENCE, never a verdict.
_SSM_RAN_AND_FAILED = frozenset({"Failed", "Cancelled", "Terminated"})
_SSM_TIMED_OUT = frozenset({"TimedOut"})
# Undelivered means the command never reached the host to run.
_SSM_UNDELIVERED = frozenset({"Undelivered"})


def tail_bytes(text: str | bytes | None, max_bytes: int = MAX_OUTPUT_TAIL) -> tuple[str, bool]:
    """Return a UTF-8-safe TAIL of ``text`` capped to ``max_bytes``, + a truncated flag.

    Pure. Takes the LAST ``max_bytes`` of the (byte-encoded) text so the most recent
    output is preserved, decodes back to str replacing any partial multibyte char.
    Returns ('', False) for empty/None input. The caller stores the FULL log in
    Forensic; only this bounded tail crosses.
    """
    if not text:
        return "", False
    raw = text.encode("utf-8") if isinstance(text, str) else bytes(text)
    if len(raw) <= max_bytes:
        return raw.decode("utf-8", errors="replace"), False
    return raw[-max_bytes:].decode("utf-8", errors="replace"), True


def build_containment() -> dict[str, Any]:
    """The containment facts sub-object. Constants — this lane is ALWAYS host-native,
    no-Docker, isolated-subnet, no-public-ip, IMDSv2 (RD-001 / RD-008). It cannot
    emit an outcome asserting an uncontained run."""
    return {
        "host_native": True,
        "no_docker": True,
        "isolated_subnet": True,
        "public_ip": False,
        "imdsv2_required": True,
    }


def build_execution(
    *,
    ssm_status: str,
    ssm_command_id: str | None = None,
    exit_code: int | None = None,
    stdout: str | bytes | None = None,
    stderr: str | bytes | None = None,
    output_s3_bucket: str | None = None,
    output_s3_key: str | None = None,
) -> dict[str, Any]:
    """Assemble the bounded execution sub-object. Byte-caps the crossed tails; the
    full log stays in Forensic behind the pointer. Pure."""
    if ssm_status not in SSM_STATUSES:
        raise ValueError(f"unknown ssm_status {ssm_status!r}")
    execution: dict[str, Any] = {
        "mechanism": "ssm_send_command",
        "ssm_status": ssm_status,
    }
    if ssm_command_id:
        execution["ssm_command_id"] = ssm_command_id[:128]
    if exit_code is not None:
        # Clamp to the contract's -1..255 range (SSM uses -1 for "no code").
        execution["exit_code"] = max(-1, min(255, int(exit_code)))

    stdout_tail, out_trunc = tail_bytes(stdout)
    stderr_tail, err_trunc = tail_bytes(stderr)
    if stdout_tail:
        execution["stdout_tail"] = stdout_tail
    if stderr_tail:
        execution["stderr_tail"] = stderr_tail
    if out_trunc or err_trunc:
        execution["output_truncated"] = True
    if output_s3_bucket:
        execution["output_s3_bucket"] = output_s3_bucket[:256]
    if output_s3_key:
        execution["output_s3_key"] = output_s3_key[:1024]
    return execution


def build_teardown(
    *,
    hard_ttl_minutes: int,
    teardown_observed: bool,
    shutdown_behavior: str = "terminate",
    terminated_at: str | None = None,
    teardown_note: str | None = None,
) -> dict[str, Any]:
    """Assemble the TTL / teardown sub-object (RD-007). Pure."""
    if shutdown_behavior not in ("terminate", "stop"):
        raise ValueError(f"unknown shutdown_behavior {shutdown_behavior!r}")
    ttl = max(1, min(60, int(hard_ttl_minutes)))
    teardown: dict[str, Any] = {
        "hard_ttl_minutes": ttl,
        "shutdown_behavior": shutdown_behavior,
        "teardown_observed": bool(teardown_observed),
    }
    if terminated_at:
        teardown["terminated_at"] = terminated_at
    if teardown_note:
        teardown["teardown_note"] = teardown_note[:256]
    return teardown


def outcome_from_ssm_status(ssm_status: str) -> str:
    """Map a terminal SSM invocation status to the orchestration OUTCOME. Pure.

    NOT a verdict — it only says how the controlled run ended:
      Success                    -> completed
      Failed/Cancelled/Terminated-> execution_error (the artifact ran and errored)
      TimedOut                   -> timed_out
      Undelivered                -> delivery_error (never reached the host)
      anything non-terminal      -> timed_out (we stopped polling before terminal)
    """
    if ssm_status == _SSM_SUCCESS:
        return OUTCOME_COMPLETED
    if ssm_status in _SSM_RAN_AND_FAILED:
        return OUTCOME_EXECUTION_ERROR
    if ssm_status in _SSM_TIMED_OUT:
        return OUTCOME_TIMED_OUT
    if ssm_status in _SSM_UNDELIVERED:
        return OUTCOME_DELIVERY_ERROR
    # Pending / InProgress / Delayed / not_run reached here means we never saw a
    # terminal success/failure — treat as timed_out from the orchestrator's view.
    return OUTCOME_TIMED_OUT


def build_run(
    *,
    artifact_class: str,
    outcome: str,
    launch_template_id: str,
    launched_from_template: bool,
    execution: dict[str, Any],
    teardown: dict[str, Any],
    instance_id: str | None = None,
    launch_template_version: str | None = None,
    instance_type: str | None = None,
    started_at: str | None = None,
    duration_ms: int | None = None,
    error_reason: str | None = None,
) -> dict[str, Any]:
    """Assemble the ``run`` object. Pure. Enforces the allow-listed enums + bounds."""
    if outcome not in OUTCOMES:
        raise ValueError(f"unknown outcome {outcome!r}")
    run: dict[str, Any] = {
        "lane": LANE,
        "artifact_class": artifact_class,
        "outcome": outcome,
        "launched_from_template": bool(launched_from_template),
        "launch_template_id": launch_template_id[:64],
        "containment": build_containment(),
        "execution": execution,
        "teardown": teardown,
    }
    if instance_id:
        run["instance_id"] = instance_id[:64]
    if launch_template_version:
        run["launch_template_version"] = launch_template_version[:16]
    if instance_type:
        run["instance_type"] = instance_type[:32]
    if started_at:
        run["started_at"] = started_at
    if duration_ms is not None:
        run["duration_ms"] = max(0, min(86400000, int(duration_ms)))
    if error_reason:
        run["error_reason"] = error_reason[:512]
    return run


def build_run_envelope(
    *,
    intake_id: str,
    sha256: str,
    detonated_at: str,
    run: dict[str, Any],
    contract_version: str,
) -> dict[str, Any]:
    """Assemble the full DERIVED run-outcome envelope that crosses to the Hub.

    Integrity-keyed by intake_id + sha256 (bound to the exact artifact detonated).
    Pure — the caller (handler) supplies intake_id/sha256/detonated_at + the run.
    """
    return {
        "contract_version": contract_version,
        "intake_id": intake_id,
        "sha256": sha256,
        "detonated_at": detonated_at,
        "run": run,
    }


def build_launch_error_run(
    *,
    artifact_class: str,
    launch_template_id: str,
    hard_ttl_minutes: int,
    error_reason: str,
) -> dict[str, Any]:
    """Convenience: a fully-formed ``run`` for the case where the host could not be
    launched at all (RunInstances failed). No host, no execution, no teardown to
    observe — but still a bounded, verdict-free EVIDENCE record (the run was
    attempted and contained-by-design). Pure."""
    return build_run(
        artifact_class=artifact_class,
        outcome=OUTCOME_LAUNCH_ERROR,
        launch_template_id=launch_template_id,
        launched_from_template=False,
        instance_id=None,
        execution=build_execution(ssm_status=SSM_STATUS_NOT_RUN),
        teardown=build_teardown(
            hard_ttl_minutes=hard_ttl_minutes,
            teardown_observed=False,
            teardown_note="host never launched; nothing to tear down",
        ),
        error_reason=error_reason,
    )
