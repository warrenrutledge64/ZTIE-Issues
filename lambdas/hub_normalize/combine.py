"""ZTIE Story 3.1 — PURE aggregation/normalization logic for the Hub-side
combined-event normalizer (RD-033).

This module is deliberately I/O-free and offline-unit-testable (the proven
1.2 -> 2.6 lane pattern: pure logic + a thin boto3 seam). It contains NO boto3, no
AWS calls, no clock reads beyond what the caller passes in. Its only job is to
NORMALIZE the three per-lane derived outputs ALREADY on the Hub tracking record —
the static-scan summary (2.1/2.2), the dynamic-run outcome (2.3) and the sanitized
behavioral telemetry (2.5) — into ONE bounded, DERIVED, verdict-free COMBINED-EVENT
record (``combined-event.contract.v1``) the Phase-3 Nova Pro correlation engine
(3.2) reasons over, and to enforce the contract's bounds (allow-listed enums,
byte/length/array caps) in code so a malformed record can never be shaped here.

Zero-trust invariants baked in here (mirror the contract):
  * EVIDENCE, never a verdict. There is NO verdict / safe / approved / forward /
    pass_fail / malicious / clean field anywhere in what this builds.
    ``highest_severity`` / ``dynamic_outcome`` / ``capture_status`` describe
    EVIDENCE; ``complete`` is an AGGREGATION-completeness fact, NEVER a verdict.
  * NORMALIZE HONESTLY. An input's derived record may not have landed yet (SQS
    ordering) or a lane may be no_trace / errored. This RECORDS which inputs are
    present (``inputs_present`` + per-source ``presence``) and NEVER fabricates a
    missing one — an absent input is simply omitted from the signals.
  * DERIVED-ONLY (RD-009). It references the per-lane detail via bounded roll-ups +
    Forensic S3 pointers; it NEVER copies raw finding text, raw command output, or
    the raw behavioral trace. The behavioral events it carries through are the
    ALREADY-sanitized, already-bounded 2.5 events — 3.1 RE-SHAPES them, it does NOT
    re-capture or re-sanitize (2.4 / 2.5 own that).
  * RELATIVE CLOCK ONLY. Behavioral ``offset_ms`` values are carried through from
    the 2.5 events unchanged; only the envelope ``combined_at`` is wall-clock.

The single input is the Hub tracking item (a plain dict) as read from DynamoDB by
the thin ``awsio`` seam. The fields this reads were written by the Hub ingest
validator's per-kind apply paths:
  * ``static_scan``  — the crossed static-scan ``scan`` object (2.1/2.2).
  * ``dynamic_run``  — the crossed dynamic-run ``run`` object (2.3).
  * ``sanitized``    — the crossed sanitized-telemetry ``sanitized`` object (2.5).
None of these is re-fetched from Forensic; they are already Hub-side derived data.
"""

from __future__ import annotations

from typing import Any

# The three per-lane derived inputs this normalizes (input NAMES, not lanes).
INPUT_STATIC = "static"
INPUT_DYNAMIC = "dynamic"
INPUT_SANITIZED = "sanitized"
INPUTS = (INPUT_STATIC, INPUT_DYNAMIC, INPUT_SANITIZED)

# Per-input presence (kept in lockstep with gen_combined_event_contract.py).
PRESENT = "present"
ABSENT = "absent"

# Contract-mirrored roll-up enums (descriptive EVIDENCE, never a decision).
STATIC_SEVERITIES = ("none", "info", "low", "medium", "high", "critical")
DYNAMIC_OUTCOMES = (
    "completed",
    "execution_error",
    "launch_error",
    "timed_out",
    "delivery_error",
)
SANITIZE_STATUSES = ("sanitized", "no_trace", "sanitize_error")
EVENT_CATEGORIES = ("file", "network", "process", "signal", "other")

# Bounds mirrored from the contract (so the pure builder can never overrun them).
_MAX_EVENTS = 2000
_MAX_SUMMARY = 512
_MAX_SYSCALL = 256
_MAX_OFFSET_MS = 86400000
_MAX_FINDINGS = 1000000
_MAX_S3_BUCKET = 256
_MAX_S3_KEY = 1024
_MAX_CONTRACT_VERSION = 16
_MAX_COUNT = 100000000
_MAX_TOKENS = 1000000
_MAX_NORMALIZE_NOTE = 512


def _clip(text: Any, max_len: int) -> str | None:
    """Coerce ``text`` to a bounded str (or None). Pure; never raises on bad input."""
    if text is None:
        return None
    return str(text)[:max_len]


def _bounded_int(value: Any, lo: int, hi: int) -> int | None:
    """Coerce to a bounded int (or None). Rejects bools. Pure."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return max(lo, min(hi, value))


def _obj(value: Any) -> dict[str, Any]:
    """Return ``value`` if it is a dict, else an empty dict. Pure."""
    return value if isinstance(value, dict) else {}


def build_static_source(scan: Any) -> dict[str, Any]:
    """Normalize the static input from the tracking record's ``static_scan`` object.

    ``scan`` is the crossed static-scan ``scan`` object (or None/absent). Records
    presence honestly; when present, rolls up ONLY bounded, allow-listed fields by
    reference. Pure.
    """
    source: dict[str, Any] = {"input": INPUT_STATIC}
    scan_obj = _obj(scan)
    if not scan_obj:
        source["presence"] = ABSENT
        return source

    source["presence"] = PRESENT
    severity = scan_obj.get("highest_severity")
    if severity in STATIC_SEVERITIES:
        source["highest_severity"] = severity
    total = _bounded_int(scan_obj.get("total_findings"), 0, _MAX_FINDINGS)
    if total is not None:
        source["total_findings"] = total
    cv = _clip(scan_obj.get("contract_version"), _MAX_CONTRACT_VERSION)
    if cv:
        source["summary_contract_version"] = cv
    fb = _clip(scan_obj.get("findings_s3_bucket"), _MAX_S3_BUCKET)
    if fb:
        source["findings_s3_bucket"] = fb
    fk = _clip(scan_obj.get("findings_s3_key"), _MAX_S3_KEY)
    if fk:
        source["findings_s3_key"] = fk
    return source


def build_dynamic_source(run: Any) -> dict[str, Any]:
    """Normalize the dynamic input from the tracking record's ``dynamic_run`` object.

    ``run`` is the crossed dynamic-run ``run`` object (or None/absent). Records
    presence honestly; when present, rolls up ONLY bounded, allow-listed fields by
    reference. Pure.
    """
    source: dict[str, Any] = {"input": INPUT_DYNAMIC}
    run_obj = _obj(run)
    if not run_obj:
        source["presence"] = ABSENT
        return source

    source["presence"] = PRESENT
    outcome = run_obj.get("outcome")
    if outcome in DYNAMIC_OUTCOMES:
        source["outcome"] = outcome
    cv = _clip(run_obj.get("contract_version"), _MAX_CONTRACT_VERSION)
    if cv:
        source["run_contract_version"] = cv
    execution = _obj(run_obj.get("execution"))
    rb = _clip(execution.get("output_s3_bucket"), _MAX_S3_BUCKET)
    if rb:
        source["run_log_s3_bucket"] = rb
    rk = _clip(execution.get("output_s3_key"), _MAX_S3_KEY)
    if rk:
        source["run_log_s3_key"] = rk
    return source


def build_sanitized_source(sanitized: Any) -> dict[str, Any]:
    """Normalize the sanitized input from the tracking record's ``sanitized`` object.

    ``sanitized`` is the crossed sanitized-telemetry ``sanitized`` object (or
    None/absent). Records presence honestly; when present, rolls up ONLY bounded,
    allow-listed pipeline/pointer fields by reference (the events themselves are
    carried through into signals.behavioral_events). Pure.
    """
    source: dict[str, Any] = {"input": INPUT_SANITIZED}
    san_obj = _obj(sanitized)
    if not san_obj:
        source["presence"] = ABSENT
        return source

    source["presence"] = PRESENT
    pipeline = _obj(san_obj.get("pipeline"))
    status = pipeline.get("status")
    if status in SANITIZE_STATUSES:
        source["capture_status"] = status
    truncated = pipeline.get("truncated")
    if isinstance(truncated, bool):
        source["truncated"] = truncated
    est = _bounded_int(pipeline.get("estimated_tokens"), 0, _MAX_TOKENS)
    if est is not None:
        source["estimated_tokens"] = est
    cv = _clip(san_obj.get("contract_version"), _MAX_CONTRACT_VERSION)
    if cv:
        source["sanitized_contract_version"] = cv
    src = _obj(san_obj.get("source"))
    tb = _clip(src.get("trace_s3_bucket"), _MAX_S3_BUCKET)
    if tb:
        source["trace_s3_bucket"] = tb
    tk = _clip(src.get("trace_s3_key"), _MAX_S3_KEY)
    if tk:
        source["trace_s3_key"] = tk
    return source


def _normalize_event(event: Any) -> dict[str, Any] | None:
    """Re-shape ONE already-sanitized 2.5 event into the combined schema, enforcing
    the contract's bounds. Returns None for an unusable event. Pure — never
    re-sanitizes; the summary is carried through as the upstream 2.5 pipeline
    already redacted it.
    """
    ev = _obj(event)
    if not ev:
        return None
    offset = _bounded_int(ev.get("offset_ms"), 0, _MAX_OFFSET_MS)
    category = ev.get("category")
    syscall = _clip(ev.get("syscall"), _MAX_SYSCALL)
    summary = _clip(ev.get("summary"), _MAX_SUMMARY)
    # All four are required by the contract; drop an event missing any of them
    # rather than fabricate a value.
    if offset is None or category not in EVENT_CATEGORIES or not syscall or summary is None:
        return None
    out: dict[str, Any] = {
        "offset_ms": offset,
        "category": category,
        "syscall": syscall,
        "summary": summary,
    }
    redacted = ev.get("redacted")
    if isinstance(redacted, bool):
        out["redacted"] = redacted
    return out


def build_signals(
    *,
    static_source: dict[str, Any],
    dynamic_source: dict[str, Any],
    sanitized: Any,
) -> dict[str, Any]:
    """Build the normalized cross-lane signals block Nova Pro (3.2) correlates over.

    Surfaces the static severity + dynamic outcome (only when their input is
    present) and carries through the ALREADY-sanitized 2.5 behavioral events
    (re-shaped, capped at MAX_EVENTS in trace order — never a random subset). A
    signal whose input is absent is OMITTED, never fabricated. Pure.
    """
    signals: dict[str, Any] = {}

    if static_source.get("presence") == PRESENT and "highest_severity" in static_source:
        signals["static_highest_severity"] = static_source["highest_severity"]
    if dynamic_source.get("presence") == PRESENT and "outcome" in dynamic_source:
        signals["dynamic_outcome"] = dynamic_source["outcome"]

    events: list[dict[str, Any]] = []
    san_obj = _obj(sanitized)
    raw_events = san_obj.get("events")
    if isinstance(raw_events, list):
        for raw in raw_events:
            if len(events) >= _MAX_EVENTS:
                break  # deterministic cap, in trace order (drop the tail)
            normalized = _normalize_event(raw)
            if normalized is not None:
                events.append(normalized)

    signals["behavioral_events"] = events
    signals["behavioral_event_count"] = len(events)
    return signals


def build_combined_event(
    *,
    static_scan: Any = None,
    dynamic_run: Any = None,
    sanitized: Any = None,
    normalize_note: str | None = None,
) -> dict[str, Any]:
    """Assemble the bounded ``combined_event`` object: the three per-input source
    roll-ups + the normalized signals + the aggregation-completeness facts. Pure.
    Enforces the allow-listed enums + bounds.

    ``complete`` is True iff all three inputs are present — an AGGREGATION-
    completeness fact, NEVER a verdict. An absent input is RECORDED (presence
    'absent', omitted from inputs_present), never fabricated.
    """
    static_source = build_static_source(static_scan)
    dynamic_source = build_dynamic_source(dynamic_run)
    sanitized_source = build_sanitized_source(sanitized)

    inputs_present: list[str] = []
    if static_source["presence"] == PRESENT:
        inputs_present.append(INPUT_STATIC)
    if dynamic_source["presence"] == PRESENT:
        inputs_present.append(INPUT_DYNAMIC)
    if sanitized_source["presence"] == PRESENT:
        inputs_present.append(INPUT_SANITIZED)

    complete = len(inputs_present) == len(INPUTS)

    signals = build_signals(
        static_source=static_source,
        dynamic_source=dynamic_source,
        sanitized=sanitized,
    )

    combined: dict[str, Any] = {
        "inputs_present": inputs_present,
        "complete": complete,
        "sources": {
            "static": static_source,
            "dynamic": dynamic_source,
            "sanitized": sanitized_source,
        },
        "signals": signals,
    }
    note = _clip(normalize_note, _MAX_NORMALIZE_NOTE)
    if note:
        combined["normalize_note"] = note
    return combined


def build_combined_envelope(
    *,
    intake_id: str,
    sha256: str,
    combined_at: str,
    combined_event: dict[str, Any],
    contract_version: str,
) -> dict[str, Any]:
    """Assemble the full DERIVED combined-event record. Integrity-keyed by
    intake_id + sha256 (bound to the exact artifact all lanes inspected). Pure —
    the caller (handler) supplies intake_id/sha256/combined_at + the object.
    """
    return {
        "contract_version": contract_version,
        "intake_id": intake_id,
        "sha256": sha256,
        "combined_at": combined_at,
        "combined_event": combined_event,
    }


def combine(
    *,
    item: dict[str, Any],
    combined_at: str,
    contract_version: str,
    normalize_note: str | None = None,
) -> dict[str, Any]:
    """One-call PURE normalize: read the three derived inputs off the tracking
    ``item``, build the ``combined_event`` object AND wrap it in the envelope. This
    is the single entry point the handler drives. Pure — no I/O.

    ``item`` is the Hub tracking DynamoDB item (a plain dict). intake_id + sha256
    are taken from the item so the combined event is bound to the exact tracked
    artifact. Tolerates any input being absent (records it, never fabricates),
    never hangs, never drops, emits NO verdict.
    """
    return build_combined_envelope(
        intake_id=item["intake_id"],
        sha256=item["sha256"],
        combined_at=combined_at,
        combined_event=build_combined_event(
            static_scan=item.get("static_scan"),
            dynamic_run=item.get("dynamic_run"),
            sanitized=item.get("sanitized"),
            normalize_note=normalize_note,
        ),
        contract_version=contract_version,
    )
