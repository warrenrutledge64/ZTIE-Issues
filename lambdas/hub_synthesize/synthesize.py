"""ZTIE Story 3.3 — PURE accuracy + gap_analysis synthesis logic (RD-037).

This module is deliberately I/O-free and offline-unit-testable (the proven
1.2 -> 3.2 lane pattern: pure logic + a thin boto3 seam). It contains NO boto3, no
AWS calls, and — crucially — NO model call. The semantic static<->dynamic reasoning
was ALREADY done by Amazon Nova Pro in Story 3.2 (RD-035): the correlation result
carries DISCRETE, categorized findings, each with a ``kind`` in
{correlated, static_only, dynamic_only, contradiction} and a descriptive severity.
accuracy + gap_analysis are DETERMINISTIC aggregations over that already-structured
evidence, so 3.3 is PURE post-processing (RD-037) — no second Nova Pro call, fully
reproducible, no Bedrock grant, no verdict-injection surface.

Its two jobs are both PURE:

  1. accuracy — score how well the correlation ELIMINATES FALSE POSITIVES. A
     ``static_only`` finding is a static flag the dynamic behavior never exercised,
     i.e. a CANDIDATE false positive; ``correlated`` findings are confirmed
     cross-lane observations. The accuracy_score is a descriptive 0-100 EVIDENCE
     metric (the share of scored findings that are confirmed correlations), NOT a
     safety score and NOT a verdict.

  2. gap_analysis — surface where the two lanes DISAGREE or leave a GAP:
     ``static_only`` -> a static_uncorroborated gap, ``dynamic_only`` -> a
     dynamic_unexplained gap, ``contradiction`` -> a contradiction gap, and — when
     the correlation ran over an INCOMPLETE combined event — a structural
     ``coverage`` gap.

Zero-trust invariants baked in here (mirror the contract):
  * EVIDENCE, never a verdict. Nothing this builds contains a verdict / safe /
    approved / forward / pass_fail / malicious / clean field. The accuracy_score
    describes reconciliation, not safety; the severity roll-ups describe evidence.
  * BOUNDED IN, BOUNDED OUT. It reasons ONLY over the bounded 3.2 correlation result
    (already <= 100 findings, every string capped); the synthesis it produces is
    capped (lists <= MAX_ITEMS, every string clipped, every enum allow-listed).
  * HONEST. An absent / non-'correlated' upstream yields status 'no_correlation'; a
    'correlated' correlation with zero findings yields 'skipped_no_findings';
    neither fabricates a synthesis.
"""

from __future__ import annotations

from typing import Any

# --- Statuses (mirror the contract enum) --------------------------------------
STATUS_SYNTHESIZED = "synthesized"
STATUS_NO_CORRELATION = "no_correlation"
STATUS_SKIPPED_NO_FINDINGS = "skipped_no_findings"

# --- Allow-listed enums (mirror the contract) ---------------------------------
GAP_KINDS = (
    "static_uncorroborated",
    "dynamic_unexplained",
    "contradiction",
    "coverage",
)
GAP_SEVERITIES = (
    "unknown",
    "none",
    "info",
    "low",
    "medium",
    "high",
    "critical",
)
# Ordered worst-last so a max roll-up is a simple index comparison.
_SEVERITY_ORDER = {name: i for i, name in enumerate(GAP_SEVERITIES)}

# The correlation finding kinds 3.3 reads (from 3.2's correlation.contract.v1).
_CORRELATION_KINDS = ("correlated", "static_only", "dynamic_only", "contradiction")
# The upstream correlation status that means "there is a correlation to synthesize".
_UPSTREAM_CORRELATED = "correlated"

# --- Bounds (mirror the contract so the pure synthesizer never overruns them) -
_MAX_SUMMARY = 4000
_MAX_ITEMS = 100
_MAX_TITLE = 256
_MAX_DETAIL = 1024
_MAX_REF = 256
_MAX_REFS = 20
_MAX_STATUS_DETAIL = 512
_MAX_COUNT = 1000

# How a correlation finding kind maps onto a gap_analysis gap_type. 'correlated'
# findings are NOT gaps (the lanes agreed), so they are absent here.
_KIND_TO_GAP_TYPE = {
    "static_only": "static_uncorroborated",
    "dynamic_only": "dynamic_unexplained",
    "contradiction": "contradiction",
}


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
    if sev in GAP_SEVERITIES:
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


def extract_correlation(correlation_result: Any) -> tuple[dict[str, Any] | None, str | None]:
    """Pull the parseable, 'correlated' correlation object out of a 3.2
    correlation_result. Returns ``(correlation, upstream_status)`` where
    ``correlation`` is the bounded correlation object ONLY when the upstream status
    is 'correlated' AND a correlation object is present, else None; ``upstream_status``
    is the recorded correlation status (or None if absent) for traceability. Pure —
    tolerant of an absent / malformed correlation_result (returns (None, status)).
    """
    if not isinstance(correlation_result, dict):
        return None, None
    upstream_status = correlation_result.get("status")
    if not isinstance(upstream_status, str):
        upstream_status = None
    if upstream_status != _UPSTREAM_CORRELATED:
        return None, upstream_status
    correlation = correlation_result.get("correlation")
    if not isinstance(correlation, dict):
        return None, upstream_status
    return correlation, upstream_status


def _findings_of(correlation: dict[str, Any]) -> list[dict[str, Any]]:
    """The list of correlation findings (allow-listed kinds only). Pure."""
    raw = correlation.get("findings")
    if not isinstance(raw, list):
        return []
    return [f for f in raw if isinstance(f, dict) and _finding_kind(f) is not None]


def build_accuracy(findings: list[dict[str, Any]]) -> tuple[dict[str, Any], bool]:
    """Build the accuracy block from the correlation findings. Returns
    ``(accuracy, truncated)`` where ``truncated`` is True iff the candidate
    false-positive list was capped. PURE — the accuracy_score is a descriptive
    reconciliation metric, never a verdict.

    accuracy_score = round(100 * confirmed / (confirmed + candidate_false_positives))
    over the SCORED findings (confirmed correlations + candidate false positives);
    when there are no scored findings it is 0 (nothing was reconciled). It measures
    cross-lane reconciliation ONLY — a high score is not 'safe', a low score is not
    'unsafe'.
    """
    confirmed = 0
    static_only = 0
    dynamic_only = 0
    contradiction = 0
    candidates: list[dict[str, Any]] = []
    truncated = False

    for finding in findings:
        kind = _finding_kind(finding)
        if kind == "correlated":
            confirmed += 1
        elif kind == "static_only":
            static_only += 1
            # A static flag with no corresponding dynamic behavior is a CANDIDATE
            # false positive (the behavior never exercised it). Surface it.
            if len(candidates) >= _MAX_ITEMS:
                truncated = True
                continue
            candidate: dict[str, Any] = {
                "severity": _normalize_severity(finding.get("severity")),
                "title": _clip(finding.get("title"), _MAX_TITLE) or "untitled static finding",
            }
            detail = _clip(finding.get("detail"), _MAX_DETAIL)
            candidate["detail"] = (
                detail
                if detail
                else "static-only finding with no correlated dynamic behavior"
            )
            static_refs = _copy_refs(finding.get("static_refs"))
            if static_refs:
                candidate["static_refs"] = static_refs
            candidates.append(candidate)
        elif kind == "dynamic_only":
            dynamic_only += 1
        elif kind == "contradiction":
            contradiction += 1

    # The scored population for the reconciliation metric: confirmed correlations vs
    # candidate false positives (static-only). dynamic_only / contradiction are
    # coverage/conflict signals surfaced as GAPS, not part of the FP-reconciliation
    # ratio.
    scored = confirmed + static_only
    accuracy_score = round(100 * confirmed / scored) if scored > 0 else 0

    accuracy = {
        "accuracy_score": max(0, min(100, accuracy_score)),
        "confirmed_correlation_count": _bounded_count(confirmed),
        "candidate_false_positive_count": _bounded_count(len(candidates)),
        "static_only_count": _bounded_count(static_only),
        "dynamic_only_count": _bounded_count(dynamic_only),
        "contradiction_count": _bounded_count(contradiction),
        "candidate_false_positives": candidates,
    }
    return accuracy, truncated


def build_gaps(
    findings: list[dict[str, Any]], *, combined_complete: bool | None
) -> tuple[dict[str, Any], bool]:
    """Build the gaps block from the correlation findings. Returns
    ``(gaps, truncated)``. A static_only finding -> static_uncorroborated gap,
    dynamic_only -> dynamic_unexplained, contradiction -> contradiction; when the
    correlation ran over an INCOMPLETE combined event a structural 'coverage' gap is
    added. PURE; capped at MAX_ITEMS. EVIDENCE only, never a verdict.
    """
    items: list[dict[str, Any]] = []
    truncated = False

    # A coverage gap is surfaced first (structural) when the upstream correlation was
    # produced over incomplete inputs — a lane's evidence may be missing entirely.
    if combined_complete is False:
        items.append(
            {
                "gap_type": "coverage",
                "severity": "medium",
                "title": "Correlation produced over an incomplete combined event",
                "detail": (
                    "Not all lanes (static / dynamic / sanitized) had landed when the "
                    "correlation ran, so the two-lane comparison may be incomplete."
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

    gaps: dict[str, Any] = {"gap_count": len(items), "items": items}
    if items:
        worst = max(items, key=lambda g: _severity_rank(g["severity"]))
        gaps["highest_gap_severity"] = worst["severity"]
    return gaps, truncated


def build_summary(accuracy: dict[str, Any], gaps: dict[str, Any]) -> str:
    """A bounded, DETERMINISTIC narrative of the synthesis. PURE; no model, no
    verdict. Describes the reconciliation + notable gaps in evidence terms only."""
    confirmed = accuracy.get("confirmed_correlation_count", 0)
    candidates = accuracy.get("candidate_false_positive_count", 0)
    score = accuracy.get("accuracy_score", 0)
    gap_count = gaps.get("gap_count", 0)
    worst = gaps.get("highest_gap_severity")
    parts = [
        (
            f"Synthesis over the correlation evidence: {confirmed} confirmed "
            f"cross-lane correlation(s) and {candidates} candidate false "
            f"positive(s) (static-only findings not exercised by the observed "
            f"behavior); reconciliation score {score}/100 (evidence-only, not a "
            f"safety verdict)."
        ),
    ]
    if gap_count:
        worst_txt = f", highest severity {worst}" if worst else ""
        parts.append(f"{gap_count} gap(s) surfaced for review{worst_txt}.")
    else:
        parts.append("No static/dynamic gaps surfaced.")
    return " ".join(parts)[:_MAX_SUMMARY]


def synthesize(
    correlation_result: Any, *, combined_complete: bool | None = None
) -> dict[str, Any]:
    """The PURE synthesis core. Given a 3.2 correlation_result (as stored on the Hub
    tracking item), return the derived synthesis payload:

        {"status": <one of the statuses>,
         "status_detail": <optional str>,
         "correlation_status": <upstream status, if any>,
         "source_finding_count": <int, if a correlation was present>,
         "synthesis": {"summary", "accuracy", "gaps"}  # only when synthesized
         "truncated": <bool>}                          # only when a list was capped

    NEVER raises, NEVER fabricates, NEVER emits a verdict. The caller (the handler /
    build_result) stamps the identity + timestamp + contract version around this.
    Pure.
    """
    correlation, upstream_status = extract_correlation(correlation_result)

    if correlation is None:
        # Honest: nothing parseable to synthesize.
        detail = (
            f"upstream correlation status was {upstream_status!r}"
            if upstream_status is not None
            else "no correlation_result present on the tracking item"
        )
        return {
            "status": STATUS_NO_CORRELATION,
            "status_detail": _clip(detail, _MAX_STATUS_DETAIL),
            "correlation_status": upstream_status
            if isinstance(upstream_status, str)
            else None,
        }

    findings = _findings_of(correlation)
    if not findings:
        # Honest: a successful correlation that found nothing to correlate.
        return {
            "status": STATUS_SKIPPED_NO_FINDINGS,
            "status_detail": "correlation succeeded but carried zero findings",
            "correlation_status": upstream_status,
            "source_finding_count": 0,
        }

    accuracy, acc_trunc = build_accuracy(findings)
    gaps, gap_trunc = build_gaps(findings, combined_complete=combined_complete)
    summary = build_summary(accuracy, gaps)

    payload: dict[str, Any] = {
        "status": STATUS_SYNTHESIZED,
        "correlation_status": upstream_status,
        "source_finding_count": _bounded_count(len(findings)),
        "synthesis": {"summary": summary, "accuracy": accuracy, "gaps": gaps},
    }
    if acc_trunc or gap_trunc:
        payload["truncated"] = True
    return payload


def build_result(
    *,
    intake_id: str,
    sha256: str,
    synthesized_at: str,
    contract_version: str,
    payload: dict[str, Any],
    correlation_contract_version: str | None = None,
    combined_complete: bool | None = None,
) -> dict[str, Any]:
    """Assemble the full DERIVED synthesis-result record (``synthesis.contract.v1``)
    around the pure ``payload`` from ``synthesize``. Integrity-keyed by intake_id +
    sha256. PURE — the handler supplies the identity + timestamp. Only carries the
    ``synthesis`` object when the payload status is 'synthesized'.
    """
    result: dict[str, Any] = {
        "contract_version": contract_version,
        "intake_id": intake_id,
        "sha256": sha256,
        "synthesized_at": synthesized_at,
        "status": payload["status"],
    }
    detail = _clip(payload.get("status_detail"), _MAX_STATUS_DETAIL)
    if detail:
        result["status_detail"] = detail
    cstatus = payload.get("correlation_status")
    if isinstance(cstatus, str):
        result["correlation_status"] = cstatus
    ccv = _clip(correlation_contract_version, 16)
    if ccv:
        result["correlation_contract_version"] = ccv
    if isinstance(payload.get("source_finding_count"), int) and not isinstance(
        payload.get("source_finding_count"), bool
    ):
        result["source_finding_count"] = _bounded_count(payload["source_finding_count"])
    if isinstance(combined_complete, bool):
        result["combined_complete"] = combined_complete
    if payload.get("truncated") is True:
        result["truncated"] = True
    if payload["status"] == STATUS_SYNTHESIZED and isinstance(
        payload.get("synthesis"), dict
    ):
        result["synthesis"] = payload["synthesis"]
    return result
