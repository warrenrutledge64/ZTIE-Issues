"""ZTIE Story 3.5 (RD-040) — PURE advisory recommended-verdict logic.

This module is deliberately I/O-free and offline-unit-testable (the proven
1.2 -> 3.4 lane pattern: pure logic + a thin boto3 seam). It contains NO boto3, no
AWS calls, and — crucially (RD-040) — NO model call. Every prior Phase-3 assessment
is already done: Amazon Nova Pro produced the three 0-100 risk scores in Story 3.3
(RD-038) and the categorized findings in Story 3.2 (RD-035); Story 3.4 (RD-039)
surfaced the findings + gaps. Over that already-structured evidence, deriving a
recommended verdict is DETERMINISTIC, so 3.5 is PURE post-processing — no model call,
fully reproducible, no Bedrock grant, no verdict-injection surface.

What it produces (RD-040):
  * a DETERMINISTIC, ADVISORY ``recommended_verdict`` in {PASS, FAIL, INCONCLUSIVE},
  * a bounded ``recommendation_basis`` (which combined score + which override drove it,
    with static/dynamic echoed as CONTEXT only),
  * and an explicit ``human_decision`` marker that is ALWAYS ``pending``.

The mapping (stakeholder-ratified thresholds, RD-040), DRIVEN BY THE ``combined`` score
— NEVER a re-aggregation of the three lane scores (the ``combined`` score is RD-038's
own whole-picture number; re-blending would reintroduce the arithmetic-over-scores
anti-pattern one layer down). On the shared 0-100 rubric (higher = riskier):

    combined <= 29  -> PASS
    combined 30-74  -> INCONCLUSIVE
    combined >= 75  -> FAIL

FORCE INCONCLUSIVE regardless of the score if ANY of:
  * a ``contradiction`` finding is present (the lanes disagree), OR
  * the evidence is incomplete: a ``coverage`` gap / ``combined_complete`` is false / a
    partial ``scoring_result`` (any lane ``model_error`` / ``unparseable`` /
    ``skipped_no_evidence``) / ``combined`` itself not ``scored`` /
    ``remediation_result.status`` != ``assessed``.
A high-severity gap pushes toward INCONCLUSIVE (a human look), NEVER an auto-FAIL —
FAIL is reserved for a genuinely high ``combined`` score.

Zero-trust invariants baked in here (mirror the contract):
  * ADVISORY, NEVER ACTED UPON. The recommended_verdict is a recommendation the human
    gates; nothing routes/promotes/destroys an artifact on it. This record carries ONLY
    the recommendation + ``human_decision: pending``; it NEVER writes the human's actual
    selection (a separate, human-owned Phase-4 field). The advisory field is named
    ``recommended_verdict`` (not a bare ``verdict``) so nothing downstream mistakes it
    for the effective decision.
  * NO RE-AGGREGATION. The ``combined`` score is the sole numeric driver; static/dynamic
    are echoed as context and NEVER re-blended into a new number.
  * BOUNDED IN, BOUNDED OUT; allow-list; HONEST. No ``scoring_result`` -> status
    ``no_scores`` + recommended_verdict INCONCLUSIVE; incomplete evidence -> status
    ``incomplete`` + INCONCLUSIVE; otherwise status ``recommended`` with the
    score-driven verdict. It NEVER fabricates a PASS/FAIL over incomplete evidence.
"""

from __future__ import annotations

from typing import Any

# --- Recommended-verdict vocabulary (mirror the contract enum) ----------------
VERDICT_PASS = "PASS"
VERDICT_FAIL = "FAIL"
VERDICT_INCONCLUSIVE = "INCONCLUSIVE"

# --- Overall status (mirror the contract enum) --------------------------------
STATUS_RECOMMENDED = "recommended"
STATUS_NO_SCORES = "no_scores"
STATUS_INCOMPLETE = "incomplete"

# --- Basis driver (mirror the contract enum) ----------------------------------
DRIVER_COMBINED_SCORE = "combined_score"
DRIVER_CONTRADICTION = "contradiction_present"
DRIVER_INCOMPLETE = "incomplete_evidence"
DRIVER_NO_SCORE = "no_score_available"

# --- The single legal human-decision marker on THIS record --------------------
HUMAN_DECISION_PENDING = "pending"

# --- Per-lane score statuses (from the 3.3 scoring.contract.v1) ---------------
SCORE_STATUS_SCORED = "scored"
_SCORE_STATUSES = ("scored", "model_error", "unparseable", "skipped_no_evidence")

# --- The three score lanes ----------------------------------------------------
SCORE_KINDS = ("static", "dynamic", "combined")

# --- The RD-040 cut lines (stakeholder-ratified thresholds) -------------------
# combined <= PASS_MAX -> PASS ; PASS_MAX < combined < FAIL_MIN -> INCONCLUSIVE ;
# combined >= FAIL_MIN -> FAIL. (29 / 75 per RD-040.)
CUT_PASS_MAX = 29
CUT_FAIL_MIN = 75

# --- Allow-listed severity vocabulary (mirror the 3.4 gap severities) ---------
SEVERITIES = ("unknown", "none", "info", "low", "medium", "high", "critical")
_SEVERITY_ORDER = {name: i for i, name in enumerate(SEVERITIES)}
# A gap at or above this severity is "high" (context that biases toward INCONCLUSIVE,
# NEVER an auto-FAIL).
_HIGH_GAP_SEVERITIES = frozenset({"high", "critical"})

# --- Bounds (mirror the contract so the pure builder never overruns them) -----
_MAX_SUMMARY = 4000
_MAX_NOTE = 1024
_MAX_REASON = 256
_MAX_REASONS = 20
_MAX_STATUS_DETAIL = 512
_MAX_RUBRIC_VERSION = 16

# The remediation status that means the findings/gaps are trustworthy input.
_REMEDIATION_ASSESSED = "assessed"

_CUT_LINES_NOTE = (
    f"RD-040 cut lines on the shared 0-100 combined score: <= {CUT_PASS_MAX} -> PASS; "
    f"{CUT_PASS_MAX + 1}-{CUT_FAIL_MIN - 1} -> INCONCLUSIVE; >= {CUT_FAIL_MIN} -> FAIL. "
    "Forced INCONCLUSIVE on a contradiction finding or any incomplete evidence."
)


def _clip(text: Any, max_len: int) -> str | None:
    if text is None:
        return None
    return str(text)[:max_len]


def _severity_rank(sev: str) -> int:
    return _SEVERITY_ORDER.get(sev, 0)


def _normalize_severity(sev: Any) -> str:
    return sev if sev in SEVERITIES else "unknown"


# --- Score extraction (defensive; from the 3.3 scoring_result) ----------------


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
        return None
    return max(0, min(100, n))


def extract_scores(scoring_result: Any) -> dict[str, dict[str, Any]] | None:
    """Pull the three per-lane score blocks out of a 3.3 scoring_result. Returns
    ``{"static": block, "dynamic": block, "combined": block}`` (each with a valid
    ``status`` and, when scored, a bounded ``score``), or None when no scoring_result
    is present. Pure — a missing/invalid lane block becomes a synthetic
    ``skipped_no_evidence`` block so the incompleteness logic is honest."""
    if not isinstance(scoring_result, dict):
        return None
    scores: dict[str, dict[str, Any]] = {}
    for kind in SCORE_KINDS:
        block = scoring_result.get(kind)
        status = block.get("status") if isinstance(block, dict) else None
        if status not in _SCORE_STATUSES:
            scores[kind] = {"status": "skipped_no_evidence"}
            continue
        out: dict[str, Any] = {"status": status}
        if status == SCORE_STATUS_SCORED:
            score = _coerce_score(block.get("score"))
            if score is not None:
                out["score"] = score
            else:
                # A "scored" block with no usable number is treated as non-scored
                # honestly (never fabricate a number).
                out["status"] = "unparseable"
        scores[kind] = out
    return scores


def _lane_scored_value(scores: dict[str, dict[str, Any]], kind: str) -> int | None:
    block = scores.get(kind) or {}
    if block.get("status") == SCORE_STATUS_SCORED:
        return _coerce_score(block.get("score"))
    return None


def _score_echo(scores: dict[str, dict[str, Any]], kind: str) -> dict[str, Any]:
    """One lane's echo for the basis: {status, score?}. Pure. CONTEXT only."""
    block = scores.get(kind) or {"status": "skipped_no_evidence"}
    status = block.get("status")
    if status not in _SCORE_STATUSES:
        status = "skipped_no_evidence"
    out: dict[str, Any] = {"status": status}
    if status == SCORE_STATUS_SCORED:
        val = _coerce_score(block.get("score"))
        if val is not None:
            out["score"] = val
    return out


# --- Incompleteness / contradiction detection (from 3.4 / combined event) ------


def _combined_complete(
    scoring_result: Any, remediation_result: Any
) -> bool | None:
    """The combined-event aggregation-completeness fact. Prefer the 3.3 scoring_result
    (it stamps combined_complete top-level), fall back to the 3.4 remediation_result.
    Pure."""
    for src in (scoring_result, remediation_result):
        if isinstance(src, dict):
            cc = src.get("combined_complete")
            if isinstance(cc, bool):
                return cc
    return None


def _gaps(remediation_result: Any) -> list[dict[str, Any]]:
    """The 3.4 gap list, or []. Pure."""
    if not isinstance(remediation_result, dict):
        return []
    assessment = remediation_result.get("assessment")
    if not isinstance(assessment, dict):
        return []
    gaps = assessment.get("gaps")
    return [g for g in gaps if isinstance(g, dict)] if isinstance(gaps, list) else []


def _has_contradiction(remediation_result: Any) -> bool:
    """True iff a contradiction finding is present (the lanes disagree). Reads the 3.4
    remediation_result's by-kind counts + the gap list (a contradiction becomes a
    contradiction gap). Pure."""
    if not isinstance(remediation_result, dict):
        return False
    assessment = remediation_result.get("assessment")
    if isinstance(assessment, dict):
        counts = assessment.get("counts")
        if isinstance(counts, dict):
            c = counts.get("contradiction")
            if isinstance(c, int) and not isinstance(c, bool) and c > 0:
                return True
    for gap in _gaps(remediation_result):
        if gap.get("gap_type") == "contradiction":
            return True
    return False


def _has_coverage_gap(remediation_result: Any) -> bool:
    for gap in _gaps(remediation_result):
        if gap.get("gap_type") == "coverage":
            return True
    return False


def _highest_gap_severity(remediation_result: Any) -> str | None:
    gaps = _gaps(remediation_result)
    if not gaps:
        return None
    worst = max(gaps, key=lambda g: _severity_rank(_normalize_severity(g.get("severity"))))
    return _normalize_severity(worst.get("severity"))


def _remediation_status(remediation_result: Any) -> str | None:
    if isinstance(remediation_result, dict):
        s = remediation_result.get("status")
        if isinstance(s, str):
            return s
    return None


def _incompleteness_reasons(
    scores: dict[str, dict[str, Any]],
    scoring_result: Any,
    remediation_result: Any,
) -> list[str]:
    """The bounded, ordered list of specific reasons the evidence is incomplete (each
    forces INCONCLUSIVE). Empty means the evidence is complete enough for a score-driven
    PASS/FAIL. Pure; deterministic order."""
    reasons: list[str] = []

    # combined itself must be scored (it is the driver).
    if _lane_scored_value(scores, "combined") is None:
        reasons.append("combined_not_scored")
    # any lane not scored -> partial scoring_result.
    for kind in ("static", "dynamic"):
        if (scores.get(kind) or {}).get("status") != SCORE_STATUS_SCORED:
            reasons.append(f"{kind}_not_scored")

    # combined event aggregation not complete.
    if _combined_complete(scoring_result, remediation_result) is False:
        reasons.append("combined_incomplete")

    # a structural coverage gap.
    if _has_coverage_gap(remediation_result):
        reasons.append("coverage_gap")

    # the 3.4 remediation step did not fully assess (its findings/gaps are the
    # incompleteness signal source, so a non-assessed status is itself incomplete).
    rem_status = _remediation_status(remediation_result)
    if rem_status is not None and rem_status != _REMEDIATION_ASSESSED:
        reasons.append("remediation_not_assessed")

    # de-dupe preserving order (combined_not_scored may also be implied above).
    seen: set[str] = set()
    ordered: list[str] = []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            ordered.append(r)
    return ordered[:_MAX_REASONS]


# --- The verdict mapping ------------------------------------------------------


def _score_to_verdict(combined_score: int) -> str:
    """The RD-040 score-driven mapping over the combined score ONLY. Pure."""
    if combined_score <= CUT_PASS_MAX:
        return VERDICT_PASS
    if combined_score >= CUT_FAIL_MIN:
        return VERDICT_FAIL
    return VERDICT_INCONCLUSIVE


def derive(
    scoring_result: Any,
    remediation_result: Any,
) -> dict[str, Any]:
    """The PURE verdict-derivation core. Given the 3.3 scoring_result + the 3.4
    remediation_result (as stored on the Hub tracking item), return the derived verdict
    payload:

        {"status": <one of the statuses>,
         "recommended_verdict": <PASS|FAIL|INCONCLUSIVE>,
         "status_detail": <optional str>,
         "basis": {...}}   # present when status is 'recommended' or 'incomplete'

    NEVER raises, NEVER fabricates a PASS/FAIL over incomplete evidence, NEVER emits an
    effective/acted-upon verdict or the human's selection. The caller (the handler /
    build_result) stamps identity + timestamp + contract version + human_decision:pending
    around this. Pure.
    """
    scores = extract_scores(scoring_result)

    if scores is None:
        # 3.3 has not landed. Honest: nothing to recommend over -> INCONCLUSIVE.
        return {
            "status": STATUS_NO_SCORES,
            "recommended_verdict": VERDICT_INCONCLUSIVE,
            "status_detail": (
                "no scoring_result present on the tracking item (3.3 not landed); "
                "recommendation is INCONCLUSIVE pending scores"
            ),
        }

    contradiction = _has_contradiction(remediation_result)
    reasons = _incompleteness_reasons(scores, scoring_result, remediation_result)
    combined_val = _lane_scored_value(scores, "combined")
    highest_gap = _highest_gap_severity(remediation_result)

    # Build the shared basis skeleton (echoes + context). NO re-blending: static/dynamic
    # are echoed as context; combined is the driver.
    basis: dict[str, Any] = {
        "scores": {
            "static": _score_echo(scores, "static"),
            "dynamic": _score_echo(scores, "dynamic"),
            "combined": _score_echo(scores, "combined"),
        },
        "combined_status": (scores.get("combined") or {}).get(
            "status", "skipped_no_evidence"
        ),
        "contradiction_present": contradiction,
        "evidence_complete": (not reasons) and combined_val is not None,
        "cut_lines_note": _CUT_LINES_NOTE,
    }
    if combined_val is not None:
        basis["combined_score"] = combined_val
    if highest_gap is not None:
        basis["highest_gap_severity"] = highest_gap
    if reasons:
        basis["override_reasons"] = reasons

    # --- Decide the recommended verdict (overrides first, then the score) ----
    # A contradiction OR any incompleteness FORCES INCONCLUSIVE. Otherwise the combined
    # score drives it. A high-severity gap is captured as context (highest_gap_severity)
    # but is NOT an auto-FAIL — FAIL comes only from a genuinely high combined score.
    if combined_val is None:
        driver = DRIVER_NO_SCORE
        verdict = VERDICT_INCONCLUSIVE
        status = STATUS_INCOMPLETE
        detail = "no combined risk score available; recommendation is INCONCLUSIVE"
    elif contradiction:
        driver = DRIVER_CONTRADICTION
        verdict = VERDICT_INCONCLUSIVE
        status = STATUS_INCOMPLETE
        detail = (
            "a contradiction finding is present (the lanes disagree); forced "
            "INCONCLUSIVE for a human look"
        )
    elif reasons:
        driver = DRIVER_INCOMPLETE
        verdict = VERDICT_INCONCLUSIVE
        status = STATUS_INCOMPLETE
        detail = "evidence incomplete (" + ", ".join(reasons) + "); forced INCONCLUSIVE"
    else:
        driver = DRIVER_COMBINED_SCORE
        verdict = _score_to_verdict(combined_val)
        status = STATUS_RECOMMENDED
        detail = None

    basis["driver"] = driver
    basis["summary"] = _build_summary(
        verdict, driver, combined_val, basis["scores"], contradiction, reasons, highest_gap
    )

    payload: dict[str, Any] = {
        "status": status,
        "recommended_verdict": verdict,
        "basis": basis,
    }
    clipped_detail = _clip(detail, _MAX_STATUS_DETAIL)
    if clipped_detail:
        payload["status_detail"] = clipped_detail
    return payload


def _build_summary(
    verdict: str,
    driver: str,
    combined_val: int | None,
    score_echoes: dict[str, Any],
    contradiction: bool,
    reasons: list[str],
    highest_gap: str | None,
) -> str:
    """A bounded, DETERMINISTIC narrative of WHY this recommendation. PURE; explicitly
    frames the result as an ADVISORY recommendation the human gates, never a verdict."""
    static_echo = score_echoes.get("static", {})
    dynamic_echo = score_echoes.get("dynamic", {})

    def _ctx(name: str, echo: dict[str, Any]) -> str:
        if echo.get("status") == SCORE_STATUS_SCORED and "score" in echo:
            return f"{name} {echo['score']}"
        return f"{name} {echo.get('status', 'unknown')}"

    context = f"context: {_ctx('static', static_echo)}, {_ctx('dynamic', dynamic_echo)}"

    if driver == DRIVER_COMBINED_SCORE and combined_val is not None:
        head = (
            f"ADVISORY recommendation {verdict}: driven by the combined risk score "
            f"{combined_val}/100 on the shared rubric (RD-040 cut lines "
            f"<= {CUT_PASS_MAX} PASS / {CUT_PASS_MAX + 1}-{CUT_FAIL_MIN - 1} "
            f"INCONCLUSIVE / >= {CUT_FAIL_MIN} FAIL). {context}."
        )
    elif driver == DRIVER_CONTRADICTION:
        combined_txt = (
            f"combined {combined_val}" if combined_val is not None else "combined unscored"
        )
        head = (
            f"ADVISORY recommendation {verdict}: FORCED INCONCLUSIVE because a "
            f"contradiction finding is present (the static and dynamic lanes disagree), "
            f"regardless of the combined score ({combined_txt}). {context}."
        )
    elif driver == DRIVER_INCOMPLETE:
        combined_txt = (
            f"combined {combined_val}" if combined_val is not None else "combined unscored"
        )
        head = (
            f"ADVISORY recommendation {verdict}: FORCED INCONCLUSIVE because the evidence "
            f"is incomplete ({', '.join(reasons)}), regardless of the score "
            f"({combined_txt}). {context}."
        )
    else:  # DRIVER_NO_SCORE
        head = (
            f"ADVISORY recommendation {verdict}: no combined risk score is available, so "
            f"there is nothing to recommend a PASS/FAIL over. {context}."
        )

    tail = (
        " This recommendation is ADVISORY ONLY and is NEVER acted upon automatically; a "
        "human must actively select PASS or FAIL at the dashboard gate (the human "
        "decision is pending)."
    )
    if highest_gap in _HIGH_GAP_SEVERITIES and verdict != VERDICT_FAIL:
        tail = (
            f" A {highest_gap}-severity gap was noted (a reason for a human look, never "
            f"an auto-FAIL)." + tail
        )
    return (head + tail)[:_MAX_SUMMARY]


def build_result(
    *,
    intake_id: str,
    sha256: str,
    recommended_at: str,
    contract_version: str,
    payload: dict[str, Any],
    rubric_version: str | None = None,
) -> dict[str, Any]:
    """Assemble the full DERIVED verdict-result record (``verdict.contract.v1``) around
    the pure ``payload`` from ``derive``. Integrity-keyed by intake_id + sha256. PURE —
    the handler supplies the identity + timestamp. ALWAYS stamps
    ``human_decision: pending`` (3.5 NEVER writes the human's actual selection)."""
    result: dict[str, Any] = {
        "contract_version": contract_version,
        "intake_id": intake_id,
        "sha256": sha256,
        "recommended_at": recommended_at,
        "status": payload["status"],
        "recommended_verdict": payload["recommended_verdict"],
        "human_decision": HUMAN_DECISION_PENDING,
    }
    detail = _clip(payload.get("status_detail"), _MAX_STATUS_DETAIL)
    if detail:
        result["status_detail"] = detail
    rv = _clip(rubric_version, _MAX_RUBRIC_VERSION)
    if rv:
        result["rubric_version"] = rv
    basis = payload.get("basis")
    if isinstance(basis, dict):
        result["recommendation_basis"] = basis
    return result
