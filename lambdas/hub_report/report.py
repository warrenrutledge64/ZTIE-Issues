"""ZTIE Story 4.5 (RD-045) — PURE per-execution report assembly + HTML render.

This module is deliberately I/O-free and offline-unit-testable (the proven 1.2 -> 4.2
lane pattern: pure logic + a thin boto3 seam). It contains NO boto3, no AWS calls, and —
crucially (RD-045) — NO model call. Every Phase-3 assessment is already done and lives on
the Hub tracking item; Story 4.5 READS that accumulated record and TRANSFORMS it into ONE
bounded, DERIVED per-intake REPORT (``report.contract.v1``) in THREE AUDIENCE TIERS, and
renders it as a self-contained HTML document (print-to-PDF for "PDF for humans").

Tiers:
  * EXECUTIVE — the risk score + a one-paragraph ADVISORY verdict. Built by REUSING the
    4.1 ``status_model.build_status`` core (scores + the advisory recommendation + the
    findings summary).
  * SECURITY — the correlated findings (behavioral chains) + severity roll-ups + gaps,
    from the 3.2 ``correlation_result`` + the 3.4 ``remediation_result`` assessment. MITRE
    ATT&CK technique IDs + Sigma rules are NOT carried on the Hub (RD-013) — surfaced as an
    explicit ``not_carried_on_hub`` placeholder, never fabricated.
  * DEVELOPER — the prioritized remediations + candidate false positives + static<->dynamic
    correlation, from the 3.4 assessment. Exact file/line is NOT carried on the Hub
    (RD-013) — ``not_carried_on_hub``.

Zero-trust invariants baked in here (mirror the contract):
  * READ/TRANSFORM ONLY. NEVER re-normalizes / re-correlates / re-scores / rebuilds
    findings / re-derives the verdict. It only reads + echoes + bounds + re-groups.
  * NO MODEL CALL. Deterministic, reproducible; no Bedrock.
  * ADVISORY, NEVER ACTED UPON (RD-040). The 3.5 recommendation is surfaced as a
    recommendation the human gates; nothing here promotes/routes/enforces. The only
    decision-shaped field is ``decision`` = ``pending``. There is deliberately NO bare
    ``verdict`` / ``safe`` / ``approved`` / ``forward`` / ``pass_fail`` / ``malicious`` /
    ``clean`` key; the only verdict-shaped field is ``recommended_verdict`` (advisory).
  * HONEST. A missing source becomes a ``pending`` tier / an omitted optional field —
    never a fabricated value. Raw-only detail is an explicit ``not_carried_on_hub`` marker.
  * DERIVED-ONLY (RD-009). Reasons ONLY over the derived Hub-side fields; references
    nothing raw. The HTML render ESCAPES every derived value (no raw HTML injection).
"""

from __future__ import annotations

import html as _html
from typing import Any

import status_model

# --- Vocabularies (mirror the contract enums) ---------------------------------
DATA_AVAILABLE = "available"
DATA_PENDING = "pending"
DATA_NOT_CARRIED = "not_carried_on_hub"

SEVERITIES = ("unknown", "none", "info", "low", "medium", "high", "critical")
FINDING_KINDS = ("correlated", "static_only", "dynamic_only", "contradiction")
GAP_TYPES = ("static_uncorroborated", "dynamic_unexplained", "contradiction", "coverage")
REMEDIATION_PRIORITIES = ("low", "medium", "high", "critical")
REMEDIATION_SOURCE_KINDS = (
    "contradiction",
    "correlated",
    "coverage",
    "dynamic_only",
    "dynamic_unexplained",
    "static_only",
    "static_uncorroborated",
)
_RECOMMENDED_VERDICTS = ("PASS", "FAIL", "INCONCLUSIVE")

# --- Bounds (mirror the contract so the pure builder never overruns them) -----
_MAX_SUMMARY = 4000
_MAX_NOTE = 1024
_MAX_LABEL = 256
_MAX_DETAIL = 1024
_MAX_BASIS = 512
_MAX_REF = 256
_MAX_REFS = 20
_MAX_LIST = 100

_REPORT_NOTE = (
    "Derived read-only per-execution report assembled by Story 4.5 from the Hub tracking "
    "record. The recommended_verdict is ADVISORY and is NEVER acted upon automatically; "
    "the effective accept/reject decision is a human action at the Phase-4 gate (the human "
    "decision is pending). MITRE ATT&CK IDs, Sigma rules and exact file/line are raw "
    "Forensic detail not carried on the Hub (RD-013) and are marked accordingly."
)

_MITRE_NOTE = (
    "MITRE ATT&CK technique IDs are raw/Forensic detail not carried across the RD-013 gate; "
    "a future enrichment story may surface derived mappings."
)
_SIGMA_NOTE = (
    "Sigma rules are raw/Forensic detail not carried across the RD-013 gate; a future "
    "enrichment story may surface derived rules."
)
_FILELINE_NOTE = (
    "Exact file/line is raw/Forensic detail not carried across the RD-013 gate; a future "
    "enrichment story may surface derived locations."
)


# --- Small pure coercion helpers ----------------------------------------------


def _clip(text: Any, max_len: int) -> str | None:
    if text is None:
        return None
    return str(text)[:max_len]


def _enum(value: Any, allowed: tuple[str, ...]) -> str | None:
    return value if value in allowed else None


def _score(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        n = value
    elif isinstance(value, float):
        n = round(value)
    else:
        try:
            n = round(float(value))
        except (TypeError, ValueError):
            return None
    return max(0, min(100, n))


def _count(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return max(0, min(100000, n))


def _refs(value: Any) -> list[str]:
    """Bounded list of inert string refs (<= _MAX_REFS, each <= _MAX_REF). Pure."""
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for v in value[:_MAX_REFS]:
        if isinstance(v, (str, int, float)) and not isinstance(v, bool):
            out.append(str(v)[:_MAX_REF])
    return out


def _assessment(item: dict[str, Any]) -> dict[str, Any] | None:
    rr = item.get("remediation_result")
    if not isinstance(rr, dict):
        return None
    a = rr.get("assessment")
    return a if isinstance(a, dict) else {}


# --- EXECUTIVE tier -----------------------------------------------------------


def _executive_tier(status_view: dict[str, Any]) -> dict[str, Any]:
    """Build the executive tier from the 4.1 read-model (reused verbatim). Pure."""
    tier: dict[str, Any] = {"overall_stage": status_view.get("overall_stage", "received")}

    scores = status_view.get("scores")
    if isinstance(scores, dict):
        combined = scores.get("combined")
        if isinstance(combined, dict) and isinstance(combined.get("score"), int):
            tier["combined_score"] = combined["score"]

    fs = status_view.get("findings_summary")
    if isinstance(fs, dict):
        sev = _enum(fs.get("highest_gap_severity"), SEVERITIES)
        if sev is not None:
            tier["highest_gap_severity"] = sev
        if isinstance(fs.get("contradiction_present"), bool):
            tier["contradiction_present"] = fs["contradiction_present"]

    # The 4.1 recommendation block is already exactly the advisory shape we want.
    rec_src = status_view.get("recommendation")
    rec_src = rec_src if isinstance(rec_src, dict) else {}
    rec: dict[str, Any] = {
        "status": rec_src.get("status", "not_yet_recommended"),
        "decision": "pending",
        "advisory": True,
    }
    rv = _enum(rec_src.get("recommended_verdict"), _RECOMMENDED_VERDICTS)
    if rv is not None:
        rec["recommended_verdict"] = rv
    summary = _clip(rec_src.get("summary"), _MAX_SUMMARY)
    if summary:
        rec["summary"] = summary
    rubric = _clip(rec_src.get("rubric_version"), 16)
    if rubric:
        rec["rubric_version"] = rubric
    tier["recommendation"] = rec
    return tier


# --- SECURITY tier ------------------------------------------------------------


def _finding_view(f: Any) -> dict[str, Any] | None:
    if not isinstance(f, dict):
        return None
    kind = _enum(f.get("kind"), FINDING_KINDS)
    sev = _enum(f.get("severity"), SEVERITIES)
    title = _clip(f.get("title"), _MAX_LABEL)
    if kind is None or sev is None or not title:
        return None
    out: dict[str, Any] = {"kind": kind, "severity": sev, "title": title}
    detail = _clip(f.get("detail"), _MAX_DETAIL)
    if detail:
        out["detail"] = detail
    sr = _refs(f.get("static_refs"))
    if sr:
        out["static_refs"] = sr
    br = _refs(f.get("behavioral_refs"))
    if br:
        out["behavioral_refs"] = br
    return out


def _gap_view(g: Any) -> dict[str, Any] | None:
    if not isinstance(g, dict):
        return None
    gt = _enum(g.get("gap_type"), GAP_TYPES)
    sev = _enum(g.get("severity"), SEVERITIES)
    title = _clip(g.get("title"), _MAX_LABEL)
    if gt is None or sev is None or not title:
        return None
    out: dict[str, Any] = {"gap_type": gt, "severity": sev, "title": title}
    detail = _clip(g.get("detail"), _MAX_DETAIL)
    if detail:
        out["detail"] = detail
    sr = _refs(g.get("static_refs"))
    if sr:
        out["static_refs"] = sr
    br = _refs(g.get("behavioral_refs"))
    if br:
        out["behavioral_refs"] = br
    return out


def _security_tier(item: dict[str, Any]) -> dict[str, Any]:
    """Build the security tier from the 3.2 correlation + 3.4 assessment. Pure."""
    assessment = _assessment(item)
    correlation_result = item.get("correlation_result")
    correlation = (
        correlation_result.get("correlation")
        if isinstance(correlation_result, dict)
        else None
    )

    tier: dict[str, Any] = {
        # MITRE IDs + Sigma rules are raw/Forensic detail (RD-013) — honest placeholders.
        "mitre_attack": {"status": DATA_NOT_CARRIED, "note": _MITRE_NOTE[:_MAX_LABEL]},
        "sigma_rules": {"status": DATA_NOT_CARRIED, "note": _SIGMA_NOTE[:_MAX_LABEL]},
        "findings": [],
        "gaps": [],
    }

    if assessment is None:
        tier["data_status"] = DATA_PENDING
        tier["finding_count"] = 0
        tier["gap_count"] = 0
        return tier

    tier["data_status"] = DATA_AVAILABLE

    findings = [
        v
        for f in (assessment.get("detailed_findings") or [])[:_MAX_LIST]
        if (v := _finding_view(f)) is not None
    ]
    gaps = [
        v
        for g in (assessment.get("gaps") or [])[:_MAX_LIST]
        if (v := _gap_view(g)) is not None
    ]
    tier["findings"] = findings
    tier["gaps"] = gaps
    tier["finding_count"] = len(findings)
    tier["gap_count"] = len(gaps)

    sev = _enum(assessment.get("highest_finding_severity"), SEVERITIES)
    if sev is not None:
        tier["highest_finding_severity"] = sev

    if isinstance(correlation, dict):
        csev = _enum(correlation.get("highest_correlation_severity"), SEVERITIES)
        if csev is not None:
            tier["highest_correlation_severity"] = csev
        csummary = _clip(correlation.get("summary"), _MAX_SUMMARY)
        if csummary:
            tier["summary"] = csummary
    if "summary" not in tier:
        asummary = _clip(assessment.get("summary"), _MAX_SUMMARY)
        if asummary:
            tier["summary"] = asummary

    return tier


# --- DEVELOPER tier -----------------------------------------------------------


def _remediation_view(r: Any) -> dict[str, Any] | None:
    if not isinstance(r, dict):
        return None
    rank = r.get("rank")
    if isinstance(rank, bool) or not isinstance(rank, int) or not (1 <= rank <= _MAX_LIST):
        return None
    priority = _enum(r.get("priority"), REMEDIATION_PRIORITIES)
    title = _clip(r.get("title"), _MAX_LABEL)
    action = _clip(r.get("action"), _MAX_DETAIL)
    if priority is None or not title or not action:
        return None
    out: dict[str, Any] = {
        "rank": rank,
        "priority": priority,
        "title": title,
        "action": action,
    }
    basis = _clip(r.get("basis"), _MAX_BASIS)
    if basis:
        out["basis"] = basis
    sk = _enum(r.get("source_kind"), REMEDIATION_SOURCE_KINDS)
    if sk is not None:
        out["source_kind"] = sk
    sev = _enum(r.get("severity"), SEVERITIES)
    if sev is not None:
        out["severity"] = sev
    sr = _refs(r.get("static_refs"))
    if sr:
        out["static_refs"] = sr
    br = _refs(r.get("behavioral_refs"))
    if br:
        out["behavioral_refs"] = br
    return out


def _candidate_fp_view(c: Any) -> dict[str, Any] | None:
    if not isinstance(c, dict):
        return None
    sev = _enum(c.get("severity"), SEVERITIES)
    title = _clip(c.get("title"), _MAX_LABEL)
    if sev is None or not title:
        return None
    out: dict[str, Any] = {"severity": sev, "title": title}
    detail = _clip(c.get("detail"), _MAX_DETAIL)
    if detail:
        out["detail"] = detail
    sr = _refs(c.get("static_refs"))
    if sr:
        out["static_refs"] = sr
    return out


def _developer_tier(item: dict[str, Any]) -> dict[str, Any]:
    """Build the developer tier from the 3.4 assessment. Pure."""
    assessment = _assessment(item)
    tier: dict[str, Any] = {
        "prioritized_remediations": [],
        "candidate_false_positives": [],
        # Exact file/line is raw/Forensic detail (RD-013) — honest placeholder.
        "source_location": {"status": DATA_NOT_CARRIED, "note": _FILELINE_NOTE[:_MAX_LABEL]},
    }

    if assessment is None:
        tier["data_status"] = DATA_PENDING
        tier["remediation_count"] = 0
        tier["candidate_false_positive_count"] = 0
        return tier

    tier["data_status"] = DATA_AVAILABLE

    rems = [
        v
        for r in (assessment.get("prioritized_remediations") or [])[:_MAX_LIST]
        if (v := _remediation_view(r)) is not None
    ]
    fps = [
        v
        for c in (assessment.get("candidate_false_positives") or [])[:_MAX_LIST]
        if (v := _candidate_fp_view(c)) is not None
    ]
    tier["prioritized_remediations"] = rems
    tier["candidate_false_positives"] = fps
    tier["remediation_count"] = len(rems)
    tier["candidate_false_positive_count"] = len(fps)

    asummary = _clip(assessment.get("summary"), _MAX_SUMMARY)
    if asummary:
        tier["summary"] = asummary

    return tier


# --- Top-level report assembly ------------------------------------------------


def build_report(
    item: dict[str, Any],
    *,
    intake_id: str,
    sha256: str,
    assembled_at: str,
    contract_version: str,
    status_contract_version: str,
) -> dict[str, Any]:
    """Assemble the full DERIVED per-intake report (``report.contract.v1``) from a Hub
    tracking ``item``. Integrity-keyed by intake_id + sha256. PURE — the caller supplies
    identity + the assembly timestamp; this only reads + echoes + bounds + re-groups the
    already-derived fields into three tiers. NEVER raises on a partial item (a missing
    source becomes a ``pending`` tier); NEVER fabricates a value; NEVER emits an effective
    verdict or a made human decision. Reuses the 4.1 read-model for the executive core."""
    status_view = status_model.build_status(
        item,
        intake_id=intake_id,
        sha256=sha256,
        assembled_at=assembled_at,
        contract_version=status_contract_version,
    )

    report: dict[str, Any] = {
        "contract_version": contract_version,
        "intake_id": intake_id,
        "sha256": sha256,
        "assembled_at": assembled_at,
        "executive": _executive_tier(status_view),
        "security": _security_tier(item),
        "developer": _developer_tier(item),
        "report_note": _REPORT_NOTE[:_MAX_NOTE],
    }

    status = _clip(item.get("status"), _MAX_LABEL)
    if status:
        report["status"] = status
    received_at = _clip(item.get("received_at"), 40)
    if received_at:
        report["received_at"] = received_at

    return report


# --- Self-contained HTML render (print-to-PDF) --------------------------------
# Every derived value is escaped via html.escape before it reaches the document, so a
# derived string can never inject HTML (RD-009 / RD-013: the render escapes crossed data).


def _e(value: Any) -> str:
    return _html.escape("" if value is None else str(value), quote=True)


def _sev_pill(sev: str) -> str:
    return f'<span class="pill sev-{_e(sev)}">{_e(sev)}</span>'


def _refs_html(label: str, refs: list[str]) -> str:
    if not refs:
        return ""
    items = ", ".join(_e(r) for r in refs)
    return f'<div class="refs"><span class="refs-label">{_e(label)}:</span> {items}</div>'


def _not_carried_html(block: dict[str, Any]) -> str:
    note = block.get("note") or "Not carried on the Hub (stays in Forensic, RD-013)."
    return (
        '<p class="not-carried"><span class="badge-nc">not available on Hub</span> '
        f"{_e(note)}</p>"
    )


def render_html(report: dict[str, Any]) -> str:
    """Render the report payload as a self-contained (single-file, inline-CSS) HTML
    document suitable for print-to-PDF. PURE. Escapes every derived value."""
    ex = report.get("executive", {})
    sec = report.get("security", {})
    dev = report.get("developer", {})
    rec = ex.get("recommendation", {}) if isinstance(ex, dict) else {}

    rv = rec.get("recommended_verdict")
    rv_html = (
        f'<span class="verdict rec-{_e(rv)}">{_e(rv)}</span>'
        if rv
        else '<span class="muted">not yet recommended</span>'
    )
    combined = ex.get("combined_score")
    combined_html = _e(combined) if isinstance(combined, int) else "&mdash;"

    parts: list[str] = []
    parts.append("<!doctype html><html lang='en'><head><meta charset='utf-8'>")
    parts.append(
        f"<title>ZTIE report {_e(report.get('intake_id'))}</title>"
    )
    parts.append(f"<style>{_CSS}</style></head><body>")

    # Header
    parts.append("<header class='rpt-head'>")
    parts.append("<div class='brand'>ZTIE</div>")
    parts.append(
        "<div class='sub'>Per-execution report &mdash; Zero Trust Inspection Engine</div>"
    )
    parts.append(
        f"<div class='meta'>intake <code>{_e(report.get('intake_id'))}</code> "
        f"&middot; sha256 <code>{_e((report.get('sha256') or '')[:16])}&hellip;</code> "
        f"&middot; assembled {_e(report.get('assembled_at'))}</div>"
    )
    parts.append("</header>")

    # Advisory banner
    parts.append(
        "<div class='advisory'>Recommendations in this report are "
        "<strong>advisory only</strong> and are never acted upon automatically. The "
        "human accept / reject decision is made at the gate (decision: pending).</div>"
    )

    # EXECUTIVE
    parts.append("<section class='tier'><h2>Executive</h2>")
    parts.append("<div class='exec-grid'>")
    parts.append(
        f"<div class='kpi'><div class='kpi-label'>Combined risk score</div>"
        f"<div class='kpi-value'>{combined_html}<span class='kpi-unit'>/100</span></div></div>"
    )
    parts.append(
        f"<div class='kpi'><div class='kpi-label'>Recommended verdict (advisory)</div>"
        f"<div class='kpi-value'>{rv_html}</div></div>"
    )
    parts.append(
        f"<div class='kpi'><div class='kpi-label'>Human decision</div>"
        f"<div class='kpi-value'>{_e(rec.get('decision', 'pending'))}</div></div>"
    )
    parts.append("</div>")
    if rec.get("summary"):
        parts.append(f"<p class='summary'>{_e(rec.get('summary'))}</p>")
    parts.append(
        f"<p class='muted'>Stage reached: {_e(ex.get('overall_stage'))} &middot; "
        f"highest gap severity: {_e(ex.get('highest_gap_severity', 'n/a'))} &middot; "
        f"contradiction: {_e(bool(ex.get('contradiction_present')))}</p>"
    )
    parts.append("</section>")

    # SECURITY
    parts.append("<section class='tier'><h2>Security</h2>")
    if sec.get("data_status") != "available":
        parts.append(
            "<p class='pending'>Security findings are not yet available "
            "(the correlation / assessment has not landed for this intake).</p>"
        )
    else:
        if sec.get("summary"):
            parts.append(f"<p class='summary'>{_e(sec.get('summary'))}</p>")
        parts.append(
            f"<p class='muted'>{_e(sec.get('finding_count', 0))} finding(s) &middot; "
            f"{_e(sec.get('gap_count', 0))} gap(s) &middot; highest severity "
            f"{_e(sec.get('highest_finding_severity', 'unknown'))}</p>"
        )
        parts.append("<h3>Correlated findings (behavioral chains)</h3>")
        if sec.get("findings"):
            for f in sec["findings"]:
                parts.append("<div class='card'>")
                parts.append(
                    f"<div class='card-head'>{_sev_pill(f.get('severity', 'unknown'))} "
                    f"<span class='card-title'>{_e(f.get('title'))}</span> "
                    f"<span class='kind'>{_e(f.get('kind'))}</span></div>"
                )
                if f.get("detail"):
                    parts.append(f"<div class='card-detail'>{_e(f.get('detail'))}</div>")
                parts.append(_refs_html("static", f.get("static_refs", [])))
                parts.append(_refs_html("behavioral", f.get("behavioral_refs", [])))
                parts.append("</div>")
        else:
            parts.append("<p class='muted'>No correlated findings.</p>")
        parts.append("<h3>Gaps</h3>")
        if sec.get("gaps"):
            for g in sec["gaps"]:
                parts.append("<div class='card'>")
                parts.append(
                    f"<div class='card-head'>{_sev_pill(g.get('severity', 'unknown'))} "
                    f"<span class='card-title'>{_e(g.get('title'))}</span> "
                    f"<span class='kind'>{_e(g.get('gap_type'))}</span></div>"
                )
                if g.get("detail"):
                    parts.append(f"<div class='card-detail'>{_e(g.get('detail'))}</div>")
                parts.append("</div>")
        else:
            parts.append("<p class='muted'>No gaps.</p>")
    parts.append("<h3>MITRE ATT&amp;CK</h3>")
    parts.append(_not_carried_html(sec.get("mitre_attack", {})))
    parts.append("<h3>Sigma rules</h3>")
    parts.append(_not_carried_html(sec.get("sigma_rules", {})))
    parts.append("</section>")

    # DEVELOPER
    parts.append("<section class='tier'><h2>Developer</h2>")
    if dev.get("data_status") != "available":
        parts.append(
            "<p class='pending'>Developer remediations are not yet available "
            "(the assessment has not landed for this intake).</p>"
        )
    else:
        if dev.get("summary"):
            parts.append(f"<p class='summary'>{_e(dev.get('summary'))}</p>")
        parts.append("<h3>Prioritized remediations</h3>")
        if dev.get("prioritized_remediations"):
            parts.append("<ol class='remediations'>")
            for r in dev["prioritized_remediations"]:
                parts.append("<li class='card'>")
                parts.append(
                    f"<div class='card-head'>"
                    f"<span class='pill prio-{_e(r.get('priority'))}'>"
                    f"{_e(r.get('priority'))}</span> "
                    f"<span class='card-title'>{_e(r.get('title'))}</span></div>"
                )
                parts.append(f"<div class='card-detail'>{_e(r.get('action'))}</div>")
                if r.get("basis"):
                    parts.append(f"<div class='basis'>Basis: {_e(r.get('basis'))}</div>")
                parts.append(_refs_html("static", r.get("static_refs", [])))
                parts.append(_refs_html("behavioral", r.get("behavioral_refs", [])))
                parts.append("</li>")
            parts.append("</ol>")
        else:
            parts.append("<p class='muted'>No remediations.</p>")
        parts.append("<h3>Candidate false positives</h3>")
        if dev.get("candidate_false_positives"):
            for c in dev["candidate_false_positives"]:
                parts.append("<div class='card'>")
                parts.append(
                    f"<div class='card-head'>{_sev_pill(c.get('severity', 'unknown'))} "
                    f"<span class='card-title'>{_e(c.get('title'))}</span></div>"
                )
                if c.get("detail"):
                    parts.append(f"<div class='card-detail'>{_e(c.get('detail'))}</div>")
                parts.append("</div>")
        else:
            parts.append("<p class='muted'>No candidate false positives.</p>")
    parts.append("<h3>Exact file / line</h3>")
    parts.append(_not_carried_html(dev.get("source_location", {})))
    parts.append("</section>")

    # Footer
    if report.get("report_note"):
        parts.append(f"<footer class='rpt-foot'>{_e(report.get('report_note'))}</footer>")
    parts.append("</body></html>")
    return "".join(parts)


_CSS = (
    "body{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;"
    "color:#1a2230;margin:0;padding:0 24px 40px;font-size:14px;line-height:1.5}"
    ".rpt-head{padding:18px 0 10px;border-bottom:2px solid #263141}"
    ".brand{font-weight:800;letter-spacing:2px;color:#0b57d0;font-size:22px}"
    ".sub{color:#5a6472;font-size:13px}.meta{color:#5a6472;font-size:12px;margin-top:4px}"
    ".advisory{background:#f3e8ff;border:1px solid #b07cff;border-radius:6px;"
    "padding:8px 12px;margin:14px 0;font-size:13px}.advisory strong{color:#7a2fd0}"
    ".tier{margin:22px 0;padding-top:8px;border-top:1px solid #e2e8f0}"
    "h2{font-size:18px;margin:8px 0}h3{font-size:14px;margin:16px 0 6px;color:#0b57d0}"
    ".exec-grid{display:flex;gap:16px;flex-wrap:wrap;margin:10px 0}"
    ".kpi{border:1px solid #e2e8f0;border-radius:8px;padding:10px 14px;min-width:160px}"
    ".kpi-label{font-size:11px;text-transform:uppercase;color:#5a6472;letter-spacing:.5px}"
    ".kpi-value{font-size:22px;font-weight:700;margin-top:4px}.kpi-unit{font-size:13px;"
    "color:#5a6472;font-weight:400}.summary{margin:8px 0}.muted{color:#5a6472;font-size:13px}"
    ".pending{color:#5a6472;font-style:italic}"
    ".card{border:1px solid #e2e8f0;border-radius:8px;padding:10px 12px;margin:8px 0}"
    ".card-head{display:flex;gap:8px;align-items:center;flex-wrap:wrap}"
    ".card-title{font-weight:600}.kind{font-size:11px;color:#5a6472;text-transform:uppercase}"
    ".card-detail{margin-top:6px;font-size:13px}.basis{margin-top:4px;font-size:12px;color:#5a6472}"
    ".refs{margin-top:4px;font-size:11px;color:#5a6472}.refs-label{font-weight:600}"
    ".remediations{padding-left:18px}"
    ".pill{display:inline-block;padding:1px 8px;border-radius:5px;font-size:11px;"
    "font-weight:700;text-transform:uppercase;color:#fff}"
    ".sev-unknown,.sev-none,.sev-info,.prio-low{background:#5a6472}"
    ".sev-low{background:#2ea043}.sev-medium,.prio-medium{background:#d4a017;color:#1a2230}"
    ".sev-high,.prio-high{background:#e8590c}.sev-critical,.prio-critical{background:#e5484d}"
    ".verdict{font-weight:800}.rec-PASS{color:#2ea043}.rec-FAIL{color:#e5484d}"
    ".rec-INCONCLUSIVE{color:#d4a017}"
    ".not-carried{font-size:13px;color:#5a6472;margin:4px 0}"
    ".badge-nc{display:inline-block;background:#eef2f7;border:1px solid #cbd5e1;"
    "border-radius:5px;padding:1px 7px;font-size:11px;color:#5a6472;margin-right:6px}"
    ".rpt-foot{margin-top:28px;padding-top:12px;border-top:1px solid #e2e8f0;"
    "font-size:11px;color:#5a6472}"
    "code{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px}"
)
