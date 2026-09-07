"""ZTIE Story 2.6 — PURE join/collection logic for the collector (join) Lambda.

This module is deliberately I/O-free and offline-unit-testable (the proven
1.2 -> 2.3 lane pattern: pure logic + a thin boto3 seam). It contains NO boto3, no
AWS calls, no clock reads beyond what the caller passes in — every value it needs is
handed in as an argument. Its only job is to JOIN the two per-lane branch results of
the Story 2.6 concurrent fork into ONE bounded, DERIVED, verdict-free COLLECTED
record that crosses the Forensic -> Hub RD-013 gate (``collected.contract.v1``), and
to enforce the contract's bounds (allow-listed enums, byte/length caps) in code so a
malformed record can never be shaped here.

Zero-trust invariants baked in here (mirror the contract):
  * EVIDENCE, never a verdict. There is NO verdict / safe / approved / forward /
    pass_fail / malicious field anywhere in what this builds. ``lane_status`` /
    ``outcome`` / ``highest_severity`` describe EVIDENCE about the two runs;
    ``both_complete`` is a JOIN-completeness fact, NEVER a safety verdict.
  * BOTH-COMPLETE JOIN, TOLERANT OF FAILURE. A lane that errored (or was never
    reported) is RECORDED (``errored`` / ``not_applicable``) — the join never hangs
    forever and never silently drops the other lane's output. A one-lane failure
    still yields a VALID collected record carrying the other lane's roll-up.
  * DERIVED-ONLY (RD-009). Only bounded roll-ups + Forensic S3 pointers cross; the
    full findings document and the full command log stay in Forensic. This module
    NEVER copies raw finding text or raw command output.

The two branch results are the outputs of the Step Functions Parallel state's two
branches. Each branch result is either:
  * a per-lane summary payload (the static-scan-summary / dynamic-run roll-up the
    lane already produced), OR
  * a recorded error/absent marker (a branch Catch fired, or the lane was not
    named by routing) — captured here as ``errored`` / ``not_applicable``.
"""

from __future__ import annotations

from typing import Any

# The two inspection lanes this record joins (matches the routing contract's lane
# enum and the collected contract's lane enums).
LANE_STATIC = "static_analysis"
LANE_DYNAMIC = "dynamic_detonation"

# Per-lane join statuses (kept in lockstep with gen_collected_contract.py).
LANE_COMPLETED = "completed"
LANE_ERRORED = "errored"
LANE_NOT_APPLICABLE = "not_applicable"
LANE_STATUSES = (LANE_COMPLETED, LANE_ERRORED, LANE_NOT_APPLICABLE)

# Contract-mirrored roll-up enums (by reference to the two crossed per-lane
# summaries). Descriptive EVIDENCE, never a decision.
STATIC_SEVERITIES = ("none", "info", "low", "medium", "high", "critical")
DYNAMIC_OUTCOMES = (
    "completed",
    "execution_error",
    "launch_error",
    "timed_out",
    "delivery_error",
)

# Bounds mirrored from the contract (so the pure builder can never overrun them).
_MAX_ERROR_REASON = 512
_MAX_CONTRACT_VERSION = 16
_MAX_S3_BUCKET = 256
_MAX_S3_KEY = 1024
_MAX_JOIN_NOTE = 512
_MAX_FINDINGS = 1000000


def _clip(text: Any, max_len: int) -> str | None:
    """Coerce ``text`` to a bounded str (or None). Pure; never raises on bad input."""
    if text is None:
        return None
    s = str(text)
    return s[:max_len]


def _branch_status(branch_result: Any) -> str:
    """Classify one branch result into a lane_status. Pure.

    A branch result is:
      * a dict WITHOUT an ``error`` marker      -> the lane reported -> completed
      * a dict WITH a truthy ``error`` marker   -> the lane errored  -> errored
      * anything else (None / non-dict / empty) -> the lane errored  -> errored
    ``not_applicable`` is decided by the CALLER from routing (a lane routing never
    named has nothing to collect), not from the branch result itself.
    """
    if isinstance(branch_result, dict) and not branch_result.get("error"):
        return LANE_COMPLETED
    return LANE_ERRORED


def _error_reason(branch_result: Any, default: str) -> str:
    """Extract a short, bounded, non-executable error reason. Pure."""
    if isinstance(branch_result, dict):
        for key in ("error", "error_reason", "Cause", "cause"):
            val = branch_result.get(key)
            if val:
                return _clip(val, _MAX_ERROR_REASON) or default
    return default


def build_static_status(
    *, expected: bool, branch_result: Any
) -> dict[str, Any]:
    """Build the bounded STATIC-lane status sub-object (references the 2.1/2.2
    summary by roll-up + Forensic pointer). Pure. Tolerates an errored/absent lane.

    ``expected`` is whether routing named the static lane. When it did not, the lane
    is ``not_applicable`` (nothing to collect). When it did, the branch result is
    rolled up (completed) or recorded as errored.
    """
    status: dict[str, Any] = {"lane": LANE_STATIC}
    if not expected:
        status["lane_status"] = LANE_NOT_APPLICABLE
        return status

    lane_status = _branch_status(branch_result)
    status["lane_status"] = lane_status
    if lane_status == LANE_ERRORED:
        status["error_reason"] = _error_reason(
            branch_result, "static lane errored; no summary collected"
        )
        return status

    # completed — roll up ONLY bounded, allow-listed fields by reference. The
    # branch_result is the static-scan-summary envelope (or its ``scan`` object).
    scan = branch_result.get("scan") if isinstance(branch_result, dict) else None
    if not isinstance(scan, dict):
        scan = branch_result if isinstance(branch_result, dict) else {}

    severity = scan.get("highest_severity")
    if severity in STATIC_SEVERITIES:
        status["highest_severity"] = severity
    total = scan.get("total_findings")
    if isinstance(total, bool):
        total = None
    if isinstance(total, int):
        status["total_findings"] = max(0, min(_MAX_FINDINGS, total))
    cv = branch_result.get("contract_version") if isinstance(branch_result, dict) else None
    if cv is not None:
        status["summary_contract_version"] = _clip(cv, _MAX_CONTRACT_VERSION)
    fb = scan.get("findings_s3_bucket")
    if fb:
        status["findings_s3_bucket"] = _clip(fb, _MAX_S3_BUCKET)
    fk = scan.get("findings_s3_key")
    if fk:
        status["findings_s3_key"] = _clip(fk, _MAX_S3_KEY)
    return status


def build_dynamic_status(
    *, expected: bool, branch_result: Any
) -> dict[str, Any]:
    """Build the bounded DYNAMIC-lane status sub-object (references the 2.3 run
    outcome by roll-up + Forensic pointer). Pure. Tolerates an errored/absent lane.
    """
    status: dict[str, Any] = {"lane": LANE_DYNAMIC}
    if not expected:
        status["lane_status"] = LANE_NOT_APPLICABLE
        return status

    lane_status = _branch_status(branch_result)
    status["lane_status"] = lane_status
    if lane_status == LANE_ERRORED:
        status["error_reason"] = _error_reason(
            branch_result, "dynamic lane errored; no run outcome collected"
        )
        return status

    # completed — roll up ONLY bounded, allow-listed fields by reference. The
    # branch_result is the dynamic-run envelope (or its ``run`` object).
    run = branch_result.get("run") if isinstance(branch_result, dict) else None
    if not isinstance(run, dict):
        run = branch_result if isinstance(branch_result, dict) else {}

    outcome = run.get("outcome")
    if outcome in DYNAMIC_OUTCOMES:
        status["outcome"] = outcome
    cv = branch_result.get("contract_version") if isinstance(branch_result, dict) else None
    if cv is not None:
        status["run_contract_version"] = _clip(cv, _MAX_CONTRACT_VERSION)
    execution = run.get("execution") if isinstance(run, dict) else None
    if isinstance(execution, dict):
        rb = execution.get("output_s3_bucket")
        if rb:
            status["run_log_s3_bucket"] = _clip(rb, _MAX_S3_BUCKET)
        rk = execution.get("output_s3_key")
        if rk:
            status["run_log_s3_key"] = _clip(rk, _MAX_S3_KEY)
    return status


def build_collected(
    *,
    lanes_expected: list[str],
    static_result: Any = None,
    dynamic_result: Any = None,
    join_note: str | None = None,
) -> dict[str, Any]:
    """Assemble the bounded ``collected`` object: the two per-lane status roll-ups +
    the join facts. Pure. Enforces the allow-listed enums + bounds.

    ``lanes_expected`` is the set of lanes routing (Story 1.3) named for this
    artifact. A lane routing expected but whose branch errored/never reported is
    recorded (``errored``), not dropped; a lane routing never named is
    ``not_applicable``. ``both_complete`` is True iff EVERY expected lane completed
    — a JOIN-completeness fact, NEVER a verdict.
    """
    static_expected = LANE_STATIC in lanes_expected
    dynamic_expected = LANE_DYNAMIC in lanes_expected

    static_status = build_static_status(
        expected=static_expected, branch_result=static_result
    )
    dynamic_status = build_dynamic_status(
        expected=dynamic_expected, branch_result=dynamic_result
    )

    # A lane is "collected" iff its per-lane summary was actually gathered
    # (completed OR errored) — an expected lane that reported nothing at all is a
    # recorded gap. not_applicable lanes are never collected.
    lanes_collected: list[str] = []
    if static_status["lane_status"] in (LANE_COMPLETED, LANE_ERRORED):
        lanes_collected.append(LANE_STATIC)
    if dynamic_status["lane_status"] in (LANE_COMPLETED, LANE_ERRORED):
        lanes_collected.append(LANE_DYNAMIC)

    # both_complete: every lane routing EXPECTED reached 'completed'. With zero
    # expected lanes there is nothing to complete, so it is vacuously False (the
    # join is only meaningful when routing named at least one lane).
    expected_statuses = []
    if static_expected:
        expected_statuses.append(static_status["lane_status"])
    if dynamic_expected:
        expected_statuses.append(dynamic_status["lane_status"])
    both_complete = bool(expected_statuses) and all(
        s == LANE_COMPLETED for s in expected_statuses
    )

    # Normalize + de-dupe lanes_expected to the allow-listed enum (defensive: the
    # caller may pass extras/dupes; the contract caps at 2 unique lanes).
    normalized_expected: list[str] = []
    for lane in (LANE_STATIC, LANE_DYNAMIC):
        if lane in lanes_expected and lane not in normalized_expected:
            normalized_expected.append(lane)

    collected: dict[str, Any] = {
        "lanes_expected": normalized_expected,
        "lanes_collected": lanes_collected,
        "both_complete": both_complete,
        "static": static_status,
        "dynamic": dynamic_status,
    }
    note = _clip(join_note, _MAX_JOIN_NOTE)
    if note:
        collected["join_note"] = note
    return collected


def build_collected_envelope(
    *,
    intake_id: str,
    sha256: str,
    joined_at: str,
    collected: dict[str, Any],
    contract_version: str,
) -> dict[str, Any]:
    """Assemble the full DERIVED collected-record envelope that crosses to the Hub.

    Integrity-keyed by intake_id + sha256 (bound to the exact artifact both lanes
    inspected). Pure — the caller (handler) supplies intake_id/sha256/joined_at +
    the collected object.
    """
    return {
        "contract_version": contract_version,
        "intake_id": intake_id,
        "sha256": sha256,
        "joined_at": joined_at,
        "collected": collected,
    }


def join(
    *,
    intake_id: str,
    sha256: str,
    joined_at: str,
    lanes_expected: list[str],
    static_result: Any = None,
    dynamic_result: Any = None,
    contract_version: str,
    join_note: str | None = None,
) -> dict[str, Any]:
    """One-call PURE join: build the ``collected`` object AND wrap it in the crossing
    envelope. This is the single entry point the handler drives. Pure — no I/O.

    Tolerates one lane erroring/absent (records it, keeps the other lane's roll-up),
    never hangs, never drops, and emits NO verdict.
    """
    collected = build_collected(
        lanes_expected=lanes_expected,
        static_result=static_result,
        dynamic_result=dynamic_result,
        join_note=join_note,
    )
    return build_collected_envelope(
        intake_id=intake_id,
        sha256=sha256,
        joined_at=joined_at,
        collected=collected,
        contract_version=contract_version,
    )
