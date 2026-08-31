"""ZTIE Story 2.1 — static-findings normalization (PURE logic).

This module turns each of the four static tools' NATIVE output into ONE normalized
findings shape (``schemas/static-findings.contract.v1.json``) so Phase 3 correlation
consumes a single format regardless of which tool fired. It also builds the derived
bounded SUMMARY that crosses to the Hub
(``schemas/static-scan-summary.contract.v1.json``).

Design (the 1.2 / 1.3 / 1.4 lesson — pure logic + a thin AWS seam):

  * PURE. No boto3, no S3, no subprocess, no I/O. Every function takes already-read
    tool output (a Python object / string / bytes) and returns plain dicts. This is
    why it is unit-testable with stdlib ``unittest`` over FIXTURE tool outputs in the
    INTEGRATIONS_ONLY sandbox with no PyPI. The scanner invocation + AWS calls live
    in ``scanners.py`` / ``awsio.py`` / ``handler.py``.
  * NON-EXECUTING. Normalization only reads tool output; it never runs the artifact.
  * EVIDENCE, NEVER A VERDICT. Nothing here decides PASS/FAIL/forward. Severity is a
    normalized descriptor; ``highest_severity`` is a roll-up of evidence.
  * NEVER RAISES ON TOOL OUTPUT. A tool that produced malformed / partial / empty
    output must not crash the lane. Each ``normalize_*`` tolerates missing keys and
    unexpected shapes and returns whatever findings it can parse (possibly none).
    The caller records a per-tool ``error`` when a tool *failed to run*; a tool that
    ran but emitted odd output still yields a best-effort (possibly empty) list.
  * BOUNDED. Strings are truncated to the contract caps; the findings array is
    capped and ``truncated`` is set when it overflows.
"""

from __future__ import annotations

import json
from typing import Any

# --- Tool + vocabulary constants (must match the contracts' enums) -----------

CFN_LINT = "cfn-lint"
CFN_GUARD = "cfn-guard"
CHECKOV = "checkov"
BANDIT = "bandit"

# check_family per tool.
FAMILY_IAC_LINT = "iac_lint"
FAMILY_POLICY_AS_CODE = "policy_as_code"
FAMILY_IAC_MISCONFIG = "iac_misconfig"
FAMILY_SAST = "sast"

# Normalized severity ladder, low -> high. Index = ordinal for the max roll-up.
SEVERITY_ORDER = ["info", "low", "medium", "high", "critical"]
_SEVERITY_RANK = {s: i for i, s in enumerate(SEVERITY_ORDER)}

# Contract caps (mirror static-findings.contract.v1.json).
_MSG_MAX = 2048
_RULE_ID_MAX = 256
_FILE_MAX = 1024
_RESOURCE_MAX = 512
_GUIDELINE_MAX = 1024
_FINDINGS_MAX = 5000
_ERROR_REASON_MAX = 512

CONTRACT_VERSION = "1.0"


def _s(value: Any, cap: int) -> str:
    """Coerce to a bounded string; never raise on odd input."""
    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    return text[:cap]


def _int_or_none(value: Any) -> int | None:
    """Best-effort non-negative int, else None. Never raises."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return n if n >= 0 else None


def _finding(
    *,
    tool: str,
    rule_id: Any,
    severity: str,
    check_family: str,
    message: Any,
    file: Any = None,
    start_line: Any = None,
    end_line: Any = None,
    resource: Any = None,
    guideline: Any = None,
) -> dict[str, Any]:
    """Assemble one normalized finding (bounded). ``severity`` must already be a
    member of SEVERITY_ORDER (callers map the tool's native severity first)."""
    finding: dict[str, Any] = {
        "tool": tool,
        "rule_id": _s(rule_id, _RULE_ID_MAX),
        "severity": severity if severity in _SEVERITY_RANK else "info",
        "check_family": check_family,
        "message": _s(message, _MSG_MAX),
    }
    location: dict[str, Any] = {}
    if file:
        location["file"] = _s(file, _FILE_MAX)
    sl = _int_or_none(start_line)
    if sl is not None:
        location["start_line"] = sl
    el = _int_or_none(end_line)
    if el is not None:
        location["end_line"] = el
    if resource:
        location["resource"] = _s(resource, _RESOURCE_MAX)
    if location:
        finding["location"] = location
    if guideline:
        finding["guideline"] = _s(guideline, _GUIDELINE_MAX)
    return finding


# --- Per-tool native-severity maps -------------------------------------------

# cfn-lint Level: Error / Warning / Informational.
_CFN_LINT_LEVEL = {
    "error": "high",
    "warning": "medium",
    "informational": "info",
    "info": "info",
}

# bandit issue_severity: LOW / MEDIUM / HIGH (+ we keep info for undefined).
_BANDIT_SEVERITY = {
    "undefined": "info",
    "low": "low",
    "medium": "medium",
    "high": "high",
}

# checkov severity (present when a severity source is configured): the standard
# ladder; default to medium for a failed check with no severity attached.
_CHECKOV_SEVERITY = {
    "info": "info",
    "informational": "info",
    "low": "low",
    "medium": "medium",
    "moderate": "medium",
    "high": "high",
    "critical": "critical",
}

# cfn-guard SARIF level: error / warning / note / none.
_SARIF_LEVEL = {
    "error": "high",
    "warning": "medium",
    "note": "low",
    "none": "info",
}


def _map(table: dict[str, str], value: Any, default: str) -> str:
    if not isinstance(value, str):
        return default
    return table.get(value.strip().lower(), default)


# --- Normalizers: native tool output -> list[normalized finding] -------------
# Each accepts the PARSED tool output (already json.loads'd by the caller) and is
# tolerant of missing/oddly-shaped keys. They never raise.


def normalize_cfn_lint(parsed: Any) -> list[dict[str, Any]]:
    """cfn-lint ``--format json`` emits a top-level ARRAY of match objects:
    ``{"Rule": {"Id", "Description", ...}, "Level", "Location": {"Start":
    {"LineNumber", "ColumnNumber"}, "End": {...}}, "Message", "Filename"}``."""
    out: list[dict[str, Any]] = []
    if not isinstance(parsed, list):
        return out
    for m in parsed:
        if not isinstance(m, dict):
            continue
        rule = m.get("Rule") if isinstance(m.get("Rule"), dict) else {}
        loc = m.get("Location") if isinstance(m.get("Location"), dict) else {}
        start = loc.get("Start") if isinstance(loc.get("Start"), dict) else {}
        end = loc.get("End") if isinstance(loc.get("End"), dict) else {}
        out.append(
            _finding(
                tool=CFN_LINT,
                rule_id=rule.get("Id"),
                severity=_map(_CFN_LINT_LEVEL, m.get("Level"), "medium"),
                check_family=FAMILY_IAC_LINT,
                message=m.get("Message") or rule.get("Description"),
                file=m.get("Filename"),
                start_line=start.get("LineNumber"),
                end_line=end.get("LineNumber"),
                guideline=rule.get("Source") or rule.get("DocumentationUrl"),
            )
        )
    return out


def normalize_bandit(parsed: Any) -> list[dict[str, Any]]:
    """bandit ``-f json`` emits ``{"results": [{"test_id", "test_name",
    "issue_severity", "issue_text", "filename", "line_number", "line_range",
    "more_info"}], "errors": [...], "metrics": {...}}``."""
    out: list[dict[str, Any]] = []
    if not isinstance(parsed, dict):
        return out
    results = parsed.get("results")
    if not isinstance(results, list):
        return out
    for r in results:
        if not isinstance(r, dict):
            continue
        line_range = r.get("line_range")
        end_line = None
        if isinstance(line_range, list) and line_range:
            end_line = line_range[-1]
        out.append(
            _finding(
                tool=BANDIT,
                rule_id=r.get("test_id"),
                severity=_map(_BANDIT_SEVERITY, r.get("issue_severity"), "medium"),
                check_family=FAMILY_SAST,
                message=r.get("issue_text") or r.get("test_name"),
                file=r.get("filename"),
                start_line=r.get("line_number"),
                end_line=end_line,
                guideline=r.get("more_info"),
            )
        )
    return out


def normalize_checkov(parsed: Any) -> list[dict[str, Any]]:
    """checkov ``-o json`` emits ``{"results": {"failed_checks": [{"check_id",
    "check_name", "severity", "file_path", "file_line_range": [s, e], "resource",
    "guideline"}], "passed_checks": [...]}, "summary": {...}}``. Checkov may also
    emit a LIST of such objects (one per framework) when multiple frameworks run —
    tolerate both. Only failed checks are findings."""
    out: list[dict[str, Any]] = []
    reports = parsed if isinstance(parsed, list) else [parsed]
    for report in reports:
        if not isinstance(report, dict):
            continue
        results = report.get("results")
        if not isinstance(results, dict):
            continue
        failed = results.get("failed_checks")
        if not isinstance(failed, list):
            continue
        for c in failed:
            if not isinstance(c, dict):
                continue
            line_range = c.get("file_line_range")
            start_line = end_line = None
            if isinstance(line_range, list) and line_range:
                start_line = line_range[0]
                end_line = line_range[-1]
            out.append(
                _finding(
                    tool=CHECKOV,
                    rule_id=c.get("check_id"),
                    # checkov severity is optional; a failed check with no severity
                    # is treated as medium evidence (not dropped, not inflated).
                    severity=_map(_CHECKOV_SEVERITY, c.get("severity"), "medium"),
                    check_family=FAMILY_IAC_MISCONFIG,
                    message=c.get("check_name"),
                    file=c.get("file_path"),
                    start_line=start_line,
                    end_line=end_line,
                    resource=c.get("resource"),
                    guideline=c.get("guideline"),
                )
            )
    return out


def normalize_cfn_guard_sarif(parsed: Any) -> list[dict[str, Any]]:
    """cfn-guard ``--output-format sarif`` emits standard SARIF 2.1.0:
    ``{"runs": [{"results": [{"ruleId", "level", "message": {"text"},
    "locations": [{"physicalLocation": {"artifactLocation": {"uri"}, "region":
    {"startLine", "endLine"}}}]}]}]}``. SARIF is used (over cfn-guard's own JSON)
    because it is a stable standard across cfn-guard versions."""
    out: list[dict[str, Any]] = []
    if not isinstance(parsed, dict):
        return out
    runs = parsed.get("runs")
    if not isinstance(runs, list):
        return out
    for run in runs:
        if not isinstance(run, dict):
            continue
        results = run.get("results")
        if not isinstance(results, list):
            continue
        for r in results:
            if not isinstance(r, dict):
                continue
            msg = r.get("message")
            text = msg.get("text") if isinstance(msg, dict) else msg
            file = start_line = end_line = None
            locs = r.get("locations")
            if isinstance(locs, list) and locs and isinstance(locs[0], dict):
                phys = locs[0].get("physicalLocation")
                if isinstance(phys, dict):
                    art = phys.get("artifactLocation")
                    if isinstance(art, dict):
                        file = art.get("uri")
                    region = phys.get("region")
                    if isinstance(region, dict):
                        start_line = region.get("startLine")
                        end_line = region.get("endLine")
            out.append(
                _finding(
                    tool=CFN_GUARD,
                    rule_id=r.get("ruleId"),
                    severity=_map(_SARIF_LEVEL, r.get("level"), "medium"),
                    check_family=FAMILY_POLICY_AS_CODE,
                    message=text,
                    file=file,
                    start_line=start_line,
                    end_line=end_line,
                )
            )
    return out


# Dispatch: how each tool's raw output is parsed + normalized. cfn-guard uses SARIF
# (a JSON dialect); the rest are plain JSON. The caller passes the raw stdout TEXT.
_NORMALIZERS = {
    CFN_LINT: normalize_cfn_lint,
    BANDIT: normalize_bandit,
    CHECKOV: normalize_checkov,
    CFN_GUARD: normalize_cfn_guard_sarif,
}


def normalize_tool_output(tool: str, raw_stdout: str | bytes | None) -> list[dict[str, Any]]:
    """Parse + normalize one tool's raw stdout into normalized findings.

    Tolerant + never-raises: empty / non-JSON / unexpectedly-shaped output yields
    an empty list (the caller decides whether that tool ran ``ok`` with zero
    findings or ``error`` based on the tool's exit code — not on this returning
    empty). Unknown tool -> empty list.
    """
    normalizer = _NORMALIZERS.get(tool)
    if normalizer is None:
        return []
    if raw_stdout is None:
        return []
    text = raw_stdout.decode("utf-8", "replace") if isinstance(raw_stdout, bytes) else raw_stdout
    text = text.strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return []
    try:
        return normalizer(parsed)
    except Exception:  # noqa: BLE001 - a normalizer must never crash the lane
        # Belt-and-suspenders: any unforeseen shape yields no findings rather than
        # an exception (production resilience over hostile tool output).
        return []


# --- Document + summary assembly ---------------------------------------------


def _highest_severity(findings: list[dict[str, Any]]) -> str:
    """The worst normalized severity across findings, or 'none' when empty."""
    worst = -1
    for f in findings:
        rank = _SEVERITY_RANK.get(f.get("severity", ""), -1)
        worst = max(worst, rank)
    return SEVERITY_ORDER[worst] if worst >= 0 else "none"


def _counts_by_severity(findings: list[dict[str, Any]]) -> dict[str, int]:
    """A fixed-key count object (one per severity), matching the summary contract."""
    counts = dict.fromkeys(SEVERITY_ORDER, 0)
    for f in findings:
        sev = f.get("severity")
        if sev in counts:
            counts[sev] += 1
    return counts


def build_tool_run(
    tool: str,
    *,
    status: str,
    finding_count: int,
    error_reason: str | None = None,
    duration_ms: int | None = None,
) -> dict[str, Any]:
    """A per-tool run record for the findings document's ``tools`` array.

    ``status`` is 'ok' when the tool ran to completion (possibly zero findings) or
    'error' when it failed — decided by the caller from the tool's exit code, NOT
    from whether findings were parsed. An 'error' is recorded, not fatal.
    """
    run: dict[str, Any] = {
        "tool": tool,
        "status": status if status in ("ok", "error") else "error",
        "finding_count": max(0, int(finding_count)),
    }
    if error_reason:
        run["error_reason"] = _s(error_reason, _ERROR_REASON_MAX)
    if duration_ms is not None:
        d = _int_or_none(duration_ms)
        if d is not None:
            run["duration_ms"] = d
    return run


def build_findings_document(
    *,
    intake_id: str,
    sha256: str,
    artifact_class: str,
    scanned_at: str,
    tool_runs: list[dict[str, Any]],
    findings: list[dict[str, Any]],
) -> dict[str, Any]:
    """Assemble the full normalized findings document (the Forensic-resident shape).

    The findings array is capped at the contract bound; ``truncated`` is set when it
    overflows. The per-tool ``finding_count`` in ``tool_runs`` remains the TRUE
    pre-truncation count (the caller sets it from the pre-cap per-tool lists).
    """
    truncated = len(findings) > _FINDINGS_MAX
    doc: dict[str, Any] = {
        "contract_version": CONTRACT_VERSION,
        "intake_id": intake_id,
        "sha256": sha256,
        "artifact_class": artifact_class,
        "scanned_at": scanned_at,
        "non_executing": True,
        "tools": tool_runs,
        "findings": findings[:_FINDINGS_MAX],
    }
    if truncated:
        doc["truncated"] = True
    return doc


def build_summary(
    *,
    intake_id: str,
    sha256: str,
    scanned_at: str,
    artifact_class: str,
    tool_runs: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    findings_s3_bucket: str,
    findings_s3_key: str,
    contract_version: str = CONTRACT_VERSION,
) -> dict[str, Any]:
    """Assemble the derived, bounded SUMMARY envelope-body that crosses to the Hub.

    Carries only counts + per-tool status + a pointer to the full document in
    Forensic. NO finding text, NO verdict. ``total_findings`` and the per-severity
    counts are the TRUE totals (computed over the full pre-truncation findings).
    """
    counts = _counts_by_severity(findings)
    total = sum(counts.values())
    summary_tools = [
        {
            k: v
            for k, v in run.items()
            # The summary's tool status carries tool/status/finding_count/
            # error_reason only (no duration_ms — that stays in the Forensic doc).
            if k in ("tool", "status", "finding_count", "error_reason")
        }
        for run in tool_runs
    ]
    scan: dict[str, Any] = {
        "artifact_class": artifact_class,
        "non_executing": True,
        "tools": summary_tools,
        "counts_by_severity": counts,
        "total_findings": total,
        "highest_severity": _highest_severity(findings),
        "findings_s3_bucket": _s(findings_s3_bucket, 256),
        "findings_s3_key": _s(findings_s3_key, _FILE_MAX),
    }
    if len(findings) > _FINDINGS_MAX:
        scan["findings_truncated"] = True
    return {
        "contract_version": contract_version,
        "intake_id": intake_id,
        "sha256": sha256,
        "scanned_at": scanned_at,
        "scan": scan,
    }
