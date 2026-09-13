"""ZTIE Story 3.4 (RD-039) — PURE detailed-findings + prioritized-remediations logic.

This module is deliberately I/O-free and offline-unit-testable (the proven
1.2 -> 3.3 lane pattern: pure logic + a thin boto3 seam). It contains NO boto3, no
AWS calls, and — crucially (RD-039) — NO model call. The semantic risk assessment was
ALREADY done upstream: Amazon Nova Pro produced the three 0-100 risk scores in Story
3.3 (RD-038) and the categorized static<->dynamic findings in Story 3.2 (RD-035). Over
that already-structured evidence, building a findings view + ranking remediations is
DETERMINISTIC, so 3.4 is PURE post-processing — no second model call, fully
reproducible, no Bedrock grant, no verdict-injection surface.

Its jobs are all PURE:

  1. DETAILED FINDINGS — surface the 3.2 correlation findings (bounded + allow-listed)
     for the human gate + the report.

  2. The MIGRATED lists (moved here from the old RD-037 3.3 synthesis):
       * candidate false positives — `static_only` findings (a static flag the observed
         behavior never exercised).
       * gaps — `static_only` -> `static_uncorroborated`, `dynamic_only` ->
         `dynamic_unexplained`, `contradiction` -> `contradiction`, plus a structural
         `coverage` gap when the assessment ran over an INCOMPLETE combined event.

  3. PRIORITIZED REMEDIATIONS — an actionable to-do per finding + gap, RANKED
     highest-risk-first by (a) the three 0-100 risk scores from 3.3 and (b) the
     finding/gap descriptive severity. It TOLERATES A PARTIAL scoring result: it ranks
     honestly over WHICHEVER scores are present (a missing/failed score is never
     fabricated).

Zero-trust invariants baked in here (mirror the contract):
  * EVIDENCE + a to-do, never a verdict. Nothing this builds contains a verdict / safe
    / approved / forward / pass_fail / malicious / clean field. A remediation is
    'fix X' (an action), NEVER 'reject the artifact' (a decision). The verdict is
    Story 3.5 + the human gate.
  * BOUNDED IN, BOUNDED OUT. It reasons ONLY over the bounded 3.3 scoring result +
    3.2 correlation result (already capped, every string bounded); the lists it
    produces are capped (<= MAX_ITEMS, every string clipped, every enum allow-listed).
  * HONEST. No `scoring_result` -> status 'no_scores'; a scoring result with no scored
    lane AND no findings -> 'skipped_no_evidence'; otherwise 'assessed'. It never
    fabricates a score or a finding.
"""

from __future__ import annotations

from typing import Any

# --- Overall status (mirror the contract enum) --------------------------------
STATUS_ASSESSED = "assessed"
STATUS_NO_SCORES = "no_scores"
STATUS_SKIPPED_NO_EVIDENCE = "skipped_no_evidence"

# --- Per-lane score statuses (from the 3.3 scoring.contract.v1) ---------------
SCORE_STATUS_SCORED = "scored"
_SCORE_STATUSES = ("scored", "model_error", "unparseable", "skipped_no_evidence")

# --- The three score lanes ----------------------------------------------------
SCORE_KINDS = ("static", "dynamic", "combined")

# --- Allow-listed severity vocabulary (mirror the contract / 3.2) -------------
SEVERITIES = ("unknown", "none", "info", "low", "medium", "high", "critical")
# Ordered worst-last so a max roll-up is a simple index comparison.
_SEVERITY_ORDER = {name: i for i, name in enumerate(SEVERITIES)}

# --- Correlation finding kinds 3.4 reads (from 3.2 correlation.contract.v1) ---
_CORRELATION_KINDS = ("correlated", "static_only", "dynamic_only", "contradiction")
# The upstream correlation status that means "there are findings to surface".
_UPSTREAM_CORRELATED = "correlated"

# --- Gap types (migrated from the old RD-037 3.3 synthesis) -------------------
GAP_TYPES = (
    "static_uncorroborated",
    "dynamic_unexplained",
    "contradiction",
    "coverage",
)
# How a correlation finding kind maps onto a gap type. 'correlated' findings are NOT
# gaps (the lanes agreed), so they are absent here.
_KIND_TO_GAP_TYPE = {
    "static_only": "static_uncorroborated",
    "dynamic_only": "dynamic_unexplained",
    "contradiction": "contradiction",
}

# --- Remediation priority bands (mirror the contract enum) --------------------
REMEDIATION_PRIORITIES = ("low", "medium", "high", "critical")

# --- Bounds (mirror the contract so the pure builder never overruns them) -----
_MAX_SUMMARY = 4000
_MAX_ITEMS = 100
_MAX_TITLE = 256
_MAX_DETAIL = 1024
_MAX_ACTION = 1024
_MAX_BASIS = 512
_MAX_REF = 256
_MAX_REFS = 20
_MAX_STATUS_DETAIL = 512
_MAX_COUNT = 1000


def _clip(text: Any, max_len: int) -> str | None:
    """Coerce ``text`` to a bounded str (or None). Pure; never raises."""
    if text is None:
        return None
    return str(text)[:max_len]


def _severity_rank(sev: str) -> int:
    return _SEVERITY_ORDER.get(sev, 0)


def _bounded_count(n: int) -> int:
    return max(0, min(_MAX_COUNT, n))


def _normalize_severity(sev: Any) -> str:
    """Coerce a finding's severity into the allow-listed vocabulary. Pure."""
    if sev in SEVERITIES:
        return sev
    return "unknown"


def _copy_refs(raw: Any) -> list[str]:
    """Copy a bounded list of short string refs. Pure; drops non-strings + caps."""
    out: list[str] = []
    if isinstance(raw, list):
        for r in raw:
            if len(out) >= _MAX_REFS:
                break
            clipped = _clip(r, _MAX_REF)
            if clipped:
                out.append(clipped)
    return out


def _finding_kind(finding: Any) -> str | None:
    """The allow-listed ``kind`` of a correlation finding, or None if invalid.
    Pure — an out-of-enum kind is dropped (never fabricated)."""
    if not isinstance(finding, dict):
        return None
    kind = finding.get("kind")
    return kind if kind in _CORRELATION_KINDS else None


# --- 1. INPUTS: scores + findings (defensive extraction) ----------------------


def extract_scores(scoring_result: Any) -> dict[str, dict[str, Any]] | None:
    """Pull the three per-lane score blocks out of a 3.3 scoring_result. Returns a
    dict ``{"static": block, "dynamic": block, "combined": block}`` (each a bounded
    block with at least a valid ``status``), or None when no scoring_result is present.
    Pure — tolerant of a malformed scoring_result (a missing/invalid lane block becomes
    a synthetic ``skipped_no_evidence`` block so downstream ranking is honest)."""
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
        scores[kind] = out
    return scores


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


def scored_value(scores: dict[str, dict[str, Any]], kind: str) -> int | None:
    """The 0-100 score for a lane if it is 'scored', else None (honest partial). Pure."""
    block = scores.get(kind) or {}
    if block.get("status") == SCORE_STATUS_SCORED:
        return _coerce_score(block.get("score"))
    return None


def highest_score(scores: dict[str, dict[str, Any]]) -> tuple[int | None, str | None]:
    """The maximum present score across the three lanes + which lane carried it. Ties
    resolve in the order static < dynamic < combined (combined wins a tie, as the
    whole-picture assessment). Returns (None, None) when no lane scored. Pure."""
    best_kind: str | None = None
    best_val: int | None = None
    for kind in SCORE_KINDS:  # static, dynamic, combined — combined last wins ties
        val = scored_value(scores, kind)
        if val is None:
            continue
        if best_val is None or val >= best_val:
            best_val, best_kind = val, kind
    return best_val, best_kind


def extract_findings(
    correlation_result: Any,
) -> tuple[list[dict[str, Any]], str | None]:
    """Pull the allow-listed correlation findings out of a 3.2 correlation_result.
    Returns ``(findings, upstream_status)``. ``findings`` is the bounded list of
    valid-kind findings (empty when the correlation is absent / not 'correlated' /
    carried none); ``upstream_status`` is the recorded correlation status (or None).
    Pure — tolerant of an absent / malformed correlation_result."""
    if not isinstance(correlation_result, dict):
        return [], None
    upstream_status = correlation_result.get("status")
    if not isinstance(upstream_status, str):
        upstream_status = None
    if upstream_status != _UPSTREAM_CORRELATED:
        return [], upstream_status
    correlation = correlation_result.get("correlation")
    if not isinstance(correlation, dict):
        return [], upstream_status
    raw = correlation.get("findings")
    if not isinstance(raw, list):
        return [], upstream_status
    findings = [f for f in raw if isinstance(f, dict) and _finding_kind(f) is not None]
    return findings, upstream_status


# --- 2. DETAILED FINDINGS + MIGRATED LISTS ------------------------------------


def build_detailed_findings(
    findings: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    """Surface the correlation findings for the human gate + report, bounded +
    allow-listed. Returns ``(detailed_findings, truncated)``. Pure. EVIDENCE only."""
    out: list[dict[str, Any]] = []
    truncated = False
    for finding in findings:
        if len(out) >= _MAX_ITEMS:
            truncated = True
            break
        kind = _finding_kind(finding)
        item: dict[str, Any] = {
            "kind": kind,
            "severity": _normalize_severity(finding.get("severity")),
            "title": _clip(finding.get("title"), _MAX_TITLE) or "untitled finding",
        }
        detail = _clip(finding.get("detail"), _MAX_DETAIL)
        if detail:
            item["detail"] = detail
        static_refs = _copy_refs(finding.get("static_refs"))
        if static_refs:
            item["static_refs"] = static_refs
        behavioral_refs = _copy_refs(finding.get("behavioral_refs"))
        if behavioral_refs:
            item["behavioral_refs"] = behavioral_refs
        out.append(item)
    return out, truncated


def build_candidate_false_positives(
    findings: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    """Build the candidate-false-positive list from the `static_only` findings (a
    static flag the observed behavior never exercised). Migrated from the old 3.3
    synthesis. Returns ``(candidates, truncated)``. Pure. EVIDENCE only."""
    out: list[dict[str, Any]] = []
    truncated = False
    for finding in findings:
        if _finding_kind(finding) != "static_only":
            continue
        if len(out) >= _MAX_ITEMS:
            truncated = True
            break
        candidate: dict[str, Any] = {
            "severity": _normalize_severity(finding.get("severity")),
            "title": _clip(finding.get("title"), _MAX_TITLE)
            or "untitled static finding",
        }
        detail = _clip(finding.get("detail"), _MAX_DETAIL)
        candidate["detail"] = (
            detail if detail else "static-only finding with no correlated dynamic behavior"
        )
        static_refs = _copy_refs(finding.get("static_refs"))
        if static_refs:
            candidate["static_refs"] = static_refs
        out.append(candidate)
    return out, truncated


def build_gaps(
    findings: list[dict[str, Any]], *, combined_complete: bool | None
) -> tuple[list[dict[str, Any]], bool]:
    """Build the gap list from the correlation findings. Migrated from the old 3.3
    synthesis. A static_only finding -> static_uncorroborated, dynamic_only ->
    dynamic_unexplained, contradiction -> contradiction; when the assessment ran over
    an INCOMPLETE combined event a structural 'coverage' gap is added FIRST. Returns
    ``(gaps, truncated)``. Pure; capped at MAX_ITEMS. EVIDENCE only, never a verdict."""
    items: list[dict[str, Any]] = []
    truncated = False

    if combined_complete is False:
        items.append(
            {
                "gap_type": "coverage",
                "severity": "medium",
                "title": "Assessment produced over an incomplete combined event",
                "detail": (
                    "Not all lanes (static / dynamic / sanitized) had landed when the "
                    "assessment ran, so the two-lane comparison may be incomplete."
                ),
            }
        )

    for finding in findings:
        kind = _finding_kind(finding)
        gap_type = _KIND_TO_GAP_TYPE.get(kind or "")
        if gap_type is None:
            # 'correlated' findings are agreements, not gaps.
            continue
        if len(items) >= _MAX_ITEMS:
            truncated = True
            break
        gap: dict[str, Any] = {
            "gap_type": gap_type,
            "severity": _normalize_severity(finding.get("severity")),
            "title": _clip(finding.get("title"), _MAX_TITLE) or f"{gap_type} gap",
        }
        detail = _clip(finding.get("detail"), _MAX_DETAIL)
        if detail:
            gap["detail"] = detail
        static_refs = _copy_refs(finding.get("static_refs"))
        if static_refs:
            gap["static_refs"] = static_refs
        behavioral_refs = _copy_refs(finding.get("behavioral_refs"))
        if behavioral_refs:
            gap["behavioral_refs"] = behavioral_refs
        items.append(gap)

    return items, truncated


# --- 3. PRIORITIZED REMEDIATIONS ----------------------------------------------

# The remediation guidance template per finding kind / gap type. Each is an INERT,
# actionable "fix X" (never a decision to reject/forward the artifact).
_REMEDIATION_ACTION = {
    "correlated": (
        "A static finding was confirmed by observed runtime behavior. Investigate the "
        "root cause and remediate the underlying issue, then re-inspect."
    ),
    "static_only": (
        "A static finding was NOT exercised by the observed behavior (a candidate false "
        "positive). Confirm whether it is a true issue or scanner noise; if genuine, "
        "remediate, else record the suppression rationale."
    ),
    "dynamic_only": (
        "Runtime behavior was observed with no corresponding static finding. Investigate "
        "the behavior, add/adjust static coverage so it is caught earlier, and remediate "
        "if it is a genuine issue."
    ),
    "contradiction": (
        "The static and dynamic evidence disagree. Reconcile the two lanes: determine "
        "which is correct, then remediate the underlying issue or the detection gap."
    ),
    "static_uncorroborated": (
        "A static flag has no corroborating dynamic behavior. Review whether it is a true "
        "issue; if so remediate, otherwise document why it is uncorroborated."
    ),
    "dynamic_unexplained": (
        "Observed behavior is unexplained by any static finding. Investigate its origin "
        "and extend static analysis to explain it."
    ),
    "coverage": (
        "The assessment ran over incomplete evidence (a lane had not landed). Ensure "
        "both lanes complete and re-run the assessment before relying on the scores."
    ),
}

_REMEDIATION_TITLE_PREFIX = {
    "correlated": "Remediate confirmed cross-lane finding",
    "static_only": "Triage candidate false positive",
    "dynamic_only": "Investigate unexplained runtime behavior",
    "contradiction": "Reconcile static/dynamic contradiction",
    "static_uncorroborated": "Review uncorroborated static flag",
    "dynamic_unexplained": "Explain unexplained dynamic behavior",
    "coverage": "Complete both lanes and re-assess",
}


def _priority_band(risk: int) -> str:
    """Map a 0-100 risk magnitude onto a descriptive priority band, using the SAME
    thresholds as the shared 0-100 rubric (low<30, medium<50, high<75, critical). A
    descriptive band, NEVER a verdict. Pure."""
    if risk >= 75:
        return "critical"
    if risk >= 50:
        return "high"
    if risk >= 30:
        return "medium"
    return "low"


def _remediation_risk(
    severity: str, scores: dict[str, dict[str, Any]]
) -> tuple[int, int]:
    """Compute the ranking key for one remediation over a source severity + the three
    scores. Returns ``(risk_magnitude, severity_rank)`` where risk_magnitude is the
    max of (the highest present score) and (the severity mapped onto 0-100), so a
    high-severity finding still ranks even when scoring is partial/absent. Pure —
    ranks honestly over whichever scores are present (no fabricated score)."""
    best_score, _ = highest_score(scores)
    # Map the descriptive severity onto the same 0-100 band midpoints so a finding with
    # no score still gets an honest ranking weight from its severity alone.
    sev_to_risk = {
        "critical": 90,
        "high": 60,
        "medium": 40,
        "low": 20,
        "info": 10,
        "none": 0,
        "unknown": 15,
    }
    sev_risk = sev_to_risk.get(severity, 15)
    magnitude = max(sev_risk, best_score if best_score is not None else 0)
    return magnitude, _severity_rank(severity)


def _basis_note(
    magnitude: int, scores: dict[str, dict[str, Any]], severity: str
) -> str:
    best_score, best_kind = highest_score(scores)
    if best_score is not None:
        score_txt = f"highest risk score {best_score} ({best_kind})"
    else:
        score_txt = "no risk score available (partial/absent scoring)"
    return _clip(
        f"priority from {score_txt}; source severity {severity}; "
        f"ranking magnitude {magnitude}",
        _MAX_BASIS,
    )


def build_prioritized_remediations(
    findings: list[dict[str, Any]],
    gaps: list[dict[str, Any]],
    scores: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], bool]:
    """Build the prioritized remediation list, ranked highest-risk-first by the three
    risk scores + the finding/gap severities. One remediation per correlation finding
    and per gap (coverage gaps included). Returns ``(remediations, truncated)``. Pure.
    EVIDENCE + a to-do, never a verdict."""
    # Gather (source_kind, severity, title, static_refs, behavioral_refs) candidates
    # from BOTH the findings and the gaps.
    raw: list[dict[str, Any]] = []
    for finding in findings:
        kind = _finding_kind(finding)
        if kind is None:
            continue
        raw.append(
            {
                "source_kind": kind,
                "severity": _normalize_severity(finding.get("severity")),
                "title": _clip(finding.get("title"), _MAX_TITLE),
                "static_refs": _copy_refs(finding.get("static_refs")),
                "behavioral_refs": _copy_refs(finding.get("behavioral_refs")),
            }
        )
    for gap in gaps:
        raw.append(
            {
                "source_kind": gap.get("gap_type"),
                "severity": _normalize_severity(gap.get("severity")),
                "title": _clip(gap.get("title"), _MAX_TITLE),
                "static_refs": _copy_refs(gap.get("static_refs")),
                "behavioral_refs": _copy_refs(gap.get("behavioral_refs")),
            }
        )

    # Score each candidate, then sort highest-risk-first (stable so equal-risk items
    # keep their input order: findings before gaps).
    scored_candidates: list[tuple[tuple[int, int], int, dict[str, Any]]] = []
    for idx, cand in enumerate(raw):
        magnitude, sev_rank = _remediation_risk(cand["severity"], scores)
        scored_candidates.append(((magnitude, sev_rank), idx, cand))
    scored_candidates.sort(key=lambda t: (-t[0][0], -t[0][1], t[1]))

    out: list[dict[str, Any]] = []
    truncated = False
    for (magnitude, _sev_rank), _idx, cand in scored_candidates:
        if len(out) >= _MAX_ITEMS:
            truncated = True
            break
        source_kind = cand["source_kind"]
        severity = cand["severity"]
        rank = len(out) + 1
        rem: dict[str, Any] = {
            "rank": rank,
            "priority": _priority_band(magnitude),
            "title": cand["title"] or _REMEDIATION_TITLE_PREFIX.get(source_kind, "Remediate finding"),
            "action": _clip(
                _REMEDIATION_ACTION.get(
                    source_kind, "Investigate and remediate the underlying issue."
                ),
                _MAX_ACTION,
            ),
            "basis": _basis_note(magnitude, scores, severity),
        }
        if source_kind in _REMEDIATION_ACTION:
            rem["source_kind"] = source_kind
        rem["severity"] = severity
        if cand["static_refs"]:
            rem["static_refs"] = cand["static_refs"]
        if cand["behavioral_refs"]:
            rem["behavioral_refs"] = cand["behavioral_refs"]
        out.append(rem)
    return out, truncated


# --- 4. SUMMARY + ASSEMBLY ----------------------------------------------------


def build_summary(
    scores: dict[str, dict[str, Any]],
    counts: dict[str, int],
    remediation_count: int,
) -> str:
    """A bounded, DETERMINISTIC narrative of the findings + prioritization. PURE; no
    model, no verdict. Describes the evidence + how remediations were ranked."""
    best_score, best_kind = highest_score(scores)
    if best_score is not None:
        score_txt = (
            f"highest risk score {best_score}/100 ({best_kind} lane) on the shared "
            f"rubric (evidence-only, not a safety verdict)"
        )
    else:
        score_txt = "no risk score available (partial or absent scoring)"
    findings_total = counts.get("detailed_finding_count", 0)
    parts = [
        (
            f"Findings + remediations over the correlation evidence and the three risk "
            f"scores: {score_txt}. {findings_total} detailed finding(s) "
            f"({counts.get('correlated', 0)} correlated, "
            f"{counts.get('static_only', 0)} static-only, "
            f"{counts.get('dynamic_only', 0)} dynamic-only, "
            f"{counts.get('contradiction', 0)} contradiction); "
            f"{counts.get('candidate_false_positive_count', 0)} candidate false "
            f"positive(s); {counts.get('gap_count', 0)} gap(s)."
        ),
    ]
    if remediation_count:
        parts.append(
            f"{remediation_count} remediation(s) prioritized highest-risk-first (a "
            f"to-do list, never a verdict)."
        )
    else:
        parts.append("No remediations required (no findings or gaps).")
    return " ".join(parts)[:_MAX_SUMMARY]


def _by_kind_counts(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"correlated": 0, "static_only": 0, "dynamic_only": 0, "contradiction": 0}
    for finding in findings:
        kind = _finding_kind(finding)
        if kind in counts:
            counts[kind] += 1
    return counts


def _highest_severity(items: list[dict[str, Any]]) -> str | None:
    if not items:
        return None
    worst = max(items, key=lambda x: _severity_rank(x.get("severity", "unknown")))
    return worst.get("severity", "unknown")


def assess(
    scoring_result: Any,
    correlation_result: Any,
    *,
    combined_complete: bool | None = None,
) -> dict[str, Any]:
    """The PURE assessment core. Given the 3.3 scoring_result + the 3.2
    correlation_result (as stored on the Hub tracking item), return the derived
    remediation payload:

        {"status": <one of the statuses>,
         "status_detail": <optional str>,
         "correlation_status": <upstream 3.2 status, if any>,
         "assessment": {...}}  # only when status is 'assessed'

    NEVER raises, NEVER fabricates, NEVER emits a verdict. The caller (the handler /
    build_result) stamps the identity + timestamp + contract version around this.
    Pure.
    """
    scores = extract_scores(scoring_result)
    findings, upstream_status = extract_findings(correlation_result)

    if scores is None:
        return {
            "status": STATUS_NO_SCORES,
            "status_detail": "no scoring_result present on the tracking item (3.3 not landed)",
            "correlation_status": upstream_status,
        }

    any_scored = any(
        (scores.get(k) or {}).get("status") == SCORE_STATUS_SCORED for k in SCORE_KINDS
    )
    if not any_scored and not findings:
        return {
            "status": STATUS_SKIPPED_NO_EVIDENCE,
            "status_detail": (
                "scoring_result present but no lane scored and no correlation findings; "
                "nothing to assess"
            ),
            "correlation_status": upstream_status,
        }

    detailed_findings, df_trunc = build_detailed_findings(findings)
    candidate_fps, cfp_trunc = build_candidate_false_positives(findings)
    gaps, gap_trunc = build_gaps(findings, combined_complete=combined_complete)
    remediations, rem_trunc = build_prioritized_remediations(findings, gaps, scores)

    by_kind = _by_kind_counts(findings)
    counts = {
        **by_kind,
        "detailed_finding_count": _bounded_count(len(detailed_findings)),
        "candidate_false_positive_count": _bounded_count(len(candidate_fps)),
        "gap_count": _bounded_count(len(gaps)),
        "remediation_count": _bounded_count(len(remediations)),
    }

    best_score, best_kind = highest_score(scores)
    scores_block: dict[str, Any] = {
        "static": scores["static"],
        "dynamic": scores["dynamic"],
        "combined": scores["combined"],
    }
    if best_score is not None:
        scores_block["highest_score"] = best_score
        scores_block["highest_score_kind"] = best_kind

    assessment: dict[str, Any] = {
        "summary": build_summary(scores, counts, len(remediations)),
        "scores": scores_block,
        "counts": counts,
        "prioritized_remediations": remediations,
    }
    if detailed_findings:
        assessment["detailed_findings"] = detailed_findings
        hs = _highest_severity(detailed_findings)
        if hs:
            assessment["highest_finding_severity"] = hs
    if candidate_fps:
        assessment["candidate_false_positives"] = candidate_fps
    if gaps:
        assessment["gaps"] = gaps
        hg = _highest_severity(gaps)
        if hg:
            assessment["highest_gap_severity"] = hg

    payload: dict[str, Any] = {
        "status": STATUS_ASSESSED,
        "correlation_status": upstream_status,
        "assessment": assessment,
    }
    if df_trunc or cfp_trunc or gap_trunc or rem_trunc:
        payload["truncated"] = True
    return payload


def build_result(
    *,
    intake_id: str,
    sha256: str,
    assessed_at: str,
    contract_version: str,
    payload: dict[str, Any],
    rubric_version: str | None = None,
    combined_complete: bool | None = None,
) -> dict[str, Any]:
    """Assemble the full DERIVED remediation-result record (``remediation.contract.v1``)
    around the pure ``payload`` from ``assess``. Integrity-keyed by intake_id + sha256.
    PURE — the handler supplies the identity + timestamp. Only carries the
    ``assessment`` object when the payload status is 'assessed'."""
    result: dict[str, Any] = {
        "contract_version": contract_version,
        "intake_id": intake_id,
        "sha256": sha256,
        "assessed_at": assessed_at,
        "status": payload["status"],
    }
    detail = _clip(payload.get("status_detail"), _MAX_STATUS_DETAIL)
    if detail:
        result["status_detail"] = detail
    correlation_status = payload.get("correlation_status")
    if isinstance(correlation_status, str) and correlation_status in (
        "correlated",
        "model_error",
        "unparseable",
        "skipped_no_signals",
    ):
        result["correlation_status"] = correlation_status
    rv = _clip(rubric_version, 16)
    if rv:
        result["rubric_version"] = rv
    if isinstance(combined_complete, bool):
        result["combined_complete"] = combined_complete
    if payload.get("truncated") is True:
        result["truncated"] = True
    if payload["status"] == STATUS_ASSESSED and isinstance(
        payload.get("assessment"), dict
    ):
        result["assessment"] = payload["assessment"]
    return result
