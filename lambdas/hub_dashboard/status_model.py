"""ZTIE Story 4.1 (RD-041) — PURE per-intake status read-model assembly.

This module is deliberately I/O-free and offline-unit-testable (the proven
1.2 -> 3.5 lane pattern: pure logic + a thin boto3 seam). It contains NO boto3, no
AWS calls, and — crucially (RD-041) — NO model call. Every Phase-3 assessment is
already done and lives on the Hub tracking item; Story 4.1 is the Phase-4 opener that
READS that accumulated record and TRANSFORMS it into ONE bounded, DERIVED per-intake
STATUS READ-MODEL (``status.contract.v1``) the dashboard (4.2) + report (4.5) consume.

What it produces (RD-041), all by ECHOING already-derived Hub-side fields — never by
re-deriving anything:
  * intake identity (intake_id + sha256) + the assembly timestamp,
  * the FURTHEST pipeline stage reached (received / classified / collected / correlated
    / scored / assessed / recommended), reported HONESTLY from which fields are present,
  * per-stage presence for 3.1-3.5 (which derived fields have landed),
  * the three 3.3 lane scores echoed as CONTEXT (never re-blended),
  * a bounded 3.4 findings/remediation SUMMARY (status + counts + highest gap severity +
    contradiction flag — NOT the full findings text),
  * the 3.5 ADVISORY ``recommended_verdict`` surfaced ALONGSIDE the human ``decision``
    (always ``pending``), with an explicit ``advisory: true`` flag.

Zero-trust invariants baked in here (mirror the contract):
  * READ/TRANSFORM ONLY. NEVER re-normalizes / re-correlates / re-scores / rebuilds
    findings / re-derives the verdict. It only reads + echoes + bounds.
  * NO MODEL CALL. Deterministic, reproducible; no Bedrock.
  * ADVISORY, NEVER ACTED UPON (RD-040). The 3.5 recommendation is surfaced as a
    recommendation the human gates; nothing here promotes/routes/enforces. The only
    decision-shaped field is ``decision``, whose single legal value is ``pending``.
    There is deliberately NO bare ``verdict`` / ``safe`` / ``approved`` / ``forward`` /
    ``pass_fail`` / ``malicious`` / ``clean`` key; the only verdict-shaped field is
    ``recommendation.recommended_verdict`` (advisory).
  * BOUNDED IN, BOUNDED OUT; allow-list; HONEST. A missing field becomes an ``absent``
    stage / an omitted optional block — never a fabricated value.
  * DERIVED-ONLY (RD-009). Reasons ONLY over the derived Hub-side fields; references
    nothing raw.
"""

from __future__ import annotations

from typing import Any

# --- Overall stage vocabulary (mirror the contract enum) ----------------------
STAGE_RECEIVED = "received"
STAGE_CLASSIFIED = "classified"
STAGE_COLLECTED = "collected"
STAGE_CORRELATED = "correlated"
STAGE_SCORED = "scored"
STAGE_ASSESSED = "assessed"
STAGE_RECOMMENDED = "recommended"

# --- Stage presence vocabulary (mirror the contract enum) ---------------------
PRESENT = "present"
ABSENT = "absent"

# --- Recommendation status vocabulary (mirror the contract enum) --------------
REC_STATUS_NOT_YET = "not_yet_recommended"
_REC_STATUSES = ("recommended", "no_scores", "incomplete", REC_STATUS_NOT_YET)

# --- The single legal human-decision value 4.1 can report ---------------------
DECISION_PENDING = "pending"

# --- The three score lanes ----------------------------------------------------
SCORE_KINDS = ("static", "dynamic", "combined")
SCORE_STATUS_SCORED = "scored"
_SCORE_STATUSES = ("scored", "model_error", "unparseable", "skipped_no_evidence")

# --- Allow-listed severity vocabulary (mirror 3.4 / verdict) ------------------
SEVERITIES = ("unknown", "none", "info", "low", "medium", "high", "critical")
_RECOMMENDED_VERDICTS = ("PASS", "FAIL", "INCONCLUSIVE")

# --- Bounds (mirror the contract so the pure builder never overruns them) -----
_MAX_SUMMARY = 4000
_MAX_NOTE = 1024
_MAX_LABEL = 256
_MAX_STATUS_DETAIL = 512
_MAX_RUBRIC_VERSION = 16
_MAX_COUNT = 100000

_READ_MODEL_NOTE = (
    "Derived read-only status view assembled by Story 4.1 from the Hub tracking record. "
    "The recommended_verdict is ADVISORY and is NEVER acted upon automatically; the "
    "effective accept/reject decision is a human action at the Phase-4 dashboard gate "
    "(the human decision is pending)."
)


def _clip(text: Any, max_len: int) -> str | None:
    if text is None:
        return None
    return str(text)[:max_len]


def _coerce_score(value: Any) -> int | None:
    """Coerce a stored score into a bounded 0-100 int, or None if not a plain number.
    Pure — NEVER fabricates; a bool is not a number; a numeric value is clamped."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        n = value
    elif isinstance(value, float):
        n = round(value)
    else:
        # A Decimal (DynamoDB) or numeric string: coerce via int(float(...)) defensively.
        try:
            n = round(float(value))
        except (TypeError, ValueError):
            return None
    return max(0, min(100, n))


def _coerce_count(value: Any) -> int | None:
    """Coerce a stored count into a bounded 0.._MAX_COUNT int, or None. Pure."""
    if isinstance(value, bool):
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return max(0, min(_MAX_COUNT, n))


def _normalize_severity(sev: Any) -> str | None:
    return sev if sev in SEVERITIES else None


def _present(item: dict[str, Any], field: str) -> str:
    return PRESENT if isinstance(item.get(field), dict) else ABSENT


def _classification_present(item: dict[str, Any]) -> str:
    """The Story 1.2 classification label is a flattened field on the item (not a dict
    sub-record), so probe a couple of shapes defensively. Pure."""
    for key in ("classification", "classification_result", "classification_label"):
        val = item.get(key)
        if val is not None and val != "":
            return PRESENT
    return ABSENT


def _overall_stage(stages: dict[str, str], classification: str) -> str:
    """The FURTHEST stage reached, from which derived fields are present. Pure,
    honest — reports how far the pipeline got, never a verdict."""
    if stages.get("verdict_recommendation") == PRESENT:
        return STAGE_RECOMMENDED
    if stages.get("remediation") == PRESENT:
        return STAGE_ASSESSED
    if stages.get("scoring") == PRESENT:
        return STAGE_SCORED
    if stages.get("correlation") == PRESENT:
        return STAGE_CORRELATED
    if stages.get("combined_event") == PRESENT:
        return STAGE_COLLECTED
    if classification == PRESENT:
        return STAGE_CLASSIFIED
    return STAGE_RECEIVED


# --- Echoed sub-views (all pure; each returns None when its source is absent) --


def _score_echo_block(block: Any) -> dict[str, Any]:
    """One lane's echo: {status, score?}. Pure. CONTEXT only, never re-scored."""
    status = block.get("status") if isinstance(block, dict) else None
    if status not in _SCORE_STATUSES:
        return {"status": "skipped_no_evidence"}
    out: dict[str, Any] = {"status": status}
    if status == SCORE_STATUS_SCORED:
        val = _coerce_score(block.get("score"))
        if val is not None:
            out["score"] = val
        else:
            # A 'scored' block with no usable number is reported honestly as non-scored.
            out["status"] = "unparseable"
    return out


def _scores_view(scoring_result: Any) -> dict[str, Any] | None:
    """Echo the three 3.3 lane scores (context). None when no scoring_result. Pure."""
    if not isinstance(scoring_result, dict):
        return None
    view: dict[str, Any] = {
        "static": _score_echo_block(scoring_result.get("static")),
        "dynamic": _score_echo_block(scoring_result.get("dynamic")),
        "combined": _score_echo_block(scoring_result.get("combined")),
    }
    rv = _clip(scoring_result.get("rubric_version"), _MAX_RUBRIC_VERSION)
    if rv:
        view["rubric_version"] = rv
    return view


def _findings_summary_view(remediation_result: Any) -> dict[str, Any] | None:
    """Bounded SUMMARY of the 3.4 remediation_result (status + counts + severity +
    contradiction flag). None when no remediation_result. NOT the full findings text.
    Pure."""
    if not isinstance(remediation_result, dict):
        return None
    status = _clip(remediation_result.get("status"), _MAX_LABEL)
    view: dict[str, Any] = {"status": status if status else "unknown"}

    assessment = remediation_result.get("assessment")
    counts = assessment.get("counts") if isinstance(assessment, dict) else None
    counts = counts if isinstance(counts, dict) else {}

    for src_key, out_key in (
        ("detailed_finding_count", "finding_count"),
        ("candidate_false_positive_count", "candidate_false_positive_count"),
        ("gap_count", "gap_count"),
        ("remediation_count", "remediation_count"),
    ):
        n = _coerce_count(counts.get(src_key))
        if n is not None:
            view[out_key] = n

    if isinstance(assessment, dict):
        sev = _normalize_severity(assessment.get("highest_gap_severity"))
        if sev is not None:
            view["highest_gap_severity"] = sev

    contradiction = counts.get("contradiction")
    contradiction_n = _coerce_count(contradiction)
    if contradiction_n is not None:
        view["contradiction_present"] = contradiction_n > 0

    return view


def _recommendation_view(verdict_result: Any) -> dict[str, Any]:
    """Surface the 3.5 ADVISORY recommendation ALONGSIDE the human decision (always
    pending). ALWAYS returns a block: when no verdict_result has landed, status is
    ``not_yet_recommended`` and no recommended_verdict is reported. Pure, HONEST — the
    recommended_verdict is echoed exactly as 3.5 recorded it; 4.1 never derives it."""
    view: dict[str, Any] = {
        "decision": DECISION_PENDING,
        "advisory": True,
    }
    if not isinstance(verdict_result, dict):
        view["status"] = REC_STATUS_NOT_YET
        return view

    status = verdict_result.get("status")
    view["status"] = status if status in _REC_STATUSES else REC_STATUS_NOT_YET

    rv = verdict_result.get("recommended_verdict")
    if rv in _RECOMMENDED_VERDICTS:
        view["recommended_verdict"] = rv

    rubric = _clip(verdict_result.get("rubric_version"), _MAX_RUBRIC_VERSION)
    if rubric:
        view["rubric_version"] = rubric

    detail = _clip(verdict_result.get("status_detail"), _MAX_STATUS_DETAIL)
    if detail:
        view["status_detail"] = detail

    basis = verdict_result.get("recommendation_basis")
    if isinstance(basis, dict):
        summary = _clip(basis.get("summary"), _MAX_SUMMARY)
        if summary:
            view["summary"] = summary

    return view


def build_status(
    item: dict[str, Any],
    *,
    intake_id: str,
    sha256: str,
    assembled_at: str,
    contract_version: str,
) -> dict[str, Any]:
    """Assemble the full DERIVED per-intake status read-model (``status.contract.v1``)
    from a Hub tracking ``item``. Integrity-keyed by intake_id + sha256. PURE — the
    caller supplies identity + the assembly timestamp; this only reads + echoes + bounds
    the already-derived fields. NEVER raises on a partial item (missing stages become
    ``absent`` / omitted optional blocks); NEVER fabricates a value; NEVER emits an
    effective verdict or a made human decision."""
    stages = {
        "combined_event": _present(item, "combined_event"),
        "correlation": _present(item, "correlation_result"),
        "scoring": _present(item, "scoring_result"),
        "remediation": _present(item, "remediation_result"),
        "verdict_recommendation": _present(item, "verdict_result"),
    }
    classification = _classification_present(item)
    if classification == PRESENT:
        stages["classification"] = PRESENT

    result: dict[str, Any] = {
        "contract_version": contract_version,
        "intake_id": intake_id,
        "sha256": sha256,
        "assembled_at": assembled_at,
        "overall_stage": _overall_stage(stages, classification),
        "stages": stages,
        "recommendation": _recommendation_view(item.get("verdict_result")),
        "read_model_note": _READ_MODEL_NOTE[:_MAX_NOTE],
    }

    status = _clip(item.get("status"), _MAX_LABEL)
    if status:
        result["status"] = status
    received_at = _clip(item.get("received_at"), 40)
    if received_at:
        result["received_at"] = received_at

    scores = _scores_view(item.get("scoring_result"))
    if scores is not None:
        result["scores"] = scores

    findings = _findings_summary_view(item.get("remediation_result"))
    if findings is not None:
        result["findings_summary"] = findings

    return result
