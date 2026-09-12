"""ZTIE Story 3.2 — PURE prompt-building + response-parsing logic for the Hub-side
Nova Pro correlation engine (RD-035).

This module is deliberately I/O-free and offline-unit-testable (the proven
1.2 -> 3.1 lane pattern: pure logic + a thin boto3 seam). It contains NO boto3, no
AWS calls, no clock reads beyond what the caller passes in, and it never invokes a
model. Its two jobs are both PURE:

  1. BUILD A BOUNDED PROMPT from the ONE normalized combined-event record (3.1,
     RD-033) already on the Hub tracking item. The prompt asks Nova Pro (RD-003) to
     CORRELATE the static misconfigurations against the dynamic behavioral
     indicators — it NEVER asks the model for a verdict / safe / forward decision.
     It is built ONLY from the bounded combined event (no raw body / findings text /
     command log / raw trace — RD-009); the behavioral events it embeds are the
     ALREADY-sanitized, already-bounded 2.5 events carried through by 3.1, further
     capped here so the prompt itself stays bounded.

  2. DEFENSIVELY PARSE the model's (non-deterministic, possibly malformed) text
     response into the bounded ``correlation.contract.v1`` result, enforcing the
     contract's allow-listed enums + length/array caps in code so a malformed model
     response can NEVER shape an out-of-bounds or verdict-bearing record. If the
     response cannot be parsed, this returns a STATUS ('unparseable') and NO
     fabricated correlation — the same honesty discipline as 3.1's absent inputs.

Zero-trust invariants baked in here (mirror the contract):
  * EVIDENCE, never a verdict. Nothing this builds or parses contains a verdict /
    safe / approved / forward / pass_fail / malicious / clean field; the prompt does
    not ask for one, and any verdict-shaped key the model returns is DROPPED by the
    allow-list parse (the record schema has no slot for it).
  * BOUNDED IN, BOUNDED OUT. The prompt is capped; the parsed result is capped
    (findings <= MAX_FINDINGS, every string clipped, every enum allow-listed).
  * HONEST. An empty / no-signals combined event yields a 'skipped_no_signals'
    decision (the caller does not even invoke the model); a malformed response
    yields 'unparseable'; neither fabricates a correlation.
"""

from __future__ import annotations

import json
from typing import Any

# --- Statuses (mirror the contract enum) --------------------------------------
STATUS_CORRELATED = "correlated"
STATUS_MODEL_ERROR = "model_error"
STATUS_UNPARSEABLE = "unparseable"
STATUS_SKIPPED_NO_SIGNALS = "skipped_no_signals"

# --- Allow-listed enums (mirror the contract) ---------------------------------
CORRELATION_KINDS = ("correlated", "static_only", "dynamic_only", "contradiction")
CORRELATION_SEVERITIES = (
    "unknown",
    "none",
    "info",
    "low",
    "medium",
    "high",
    "critical",
)
# Ordered worst-last so a max roll-up is a simple index comparison.
_SEVERITY_ORDER = {name: i for i, name in enumerate(CORRELATION_SEVERITIES)}

# --- Bounds (mirror the contract so the pure parser can never overrun them) ---
_MAX_SUMMARY = 4000
_MAX_FINDINGS = 100
_MAX_TITLE = 256
_MAX_DETAIL = 1024
_MAX_REF = 256
_MAX_REFS = 20
_MAX_STATUS_DETAIL = 512

# --- Prompt bounds (keep the request to Nova Pro bounded) ---------------------
# The combined event already caps behavioral_events at 2000; for the PROMPT we cap
# tighter so the request stays small + cheap and the token budget is predictable.
_PROMPT_MAX_EVENTS = 200


def _clip(text: Any, max_len: int) -> str | None:
    """Coerce ``text`` to a bounded str (or None). Pure; never raises."""
    if text is None:
        return None
    return str(text)[:max_len]


def _severity_rank(sev: str) -> int:
    return _SEVERITY_ORDER.get(sev, 0)


# --- 1. PROMPT BUILDING -------------------------------------------------------


def has_correlatable_signals(combined_event: Any) -> bool:
    """True iff the combined event carries anything worth correlating: at least one
    input present AND at least one signal (a static severity, a dynamic outcome, or
    a behavioral event). An empty / no-input combined event is honestly skipped
    (the caller records 'skipped_no_signals' and does not invoke the model). Pure.
    """
    if not isinstance(combined_event, dict):
        return False
    inputs_present = combined_event.get("inputs_present")
    if not isinstance(inputs_present, list) or not inputs_present:
        return False
    signals = combined_event.get("signals")
    if not isinstance(signals, dict):
        return False
    if signals.get("static_highest_severity") or signals.get("dynamic_outcome"):
        return True
    events = signals.get("behavioral_events")
    return isinstance(events, list) and len(events) > 0


def build_prompt_payload(combined_event: dict[str, Any]) -> dict[str, Any]:
    """Build the BOUNDED, evidence-only view of the combined event that goes into
    the Nova Pro prompt. It carries ONLY the derived signals + presence facts + the
    (further-capped) already-sanitized behavioral events — never anything raw
    (RD-009). Pure — the caller renders it into the prompt template.
    """
    signals = combined_event.get("signals") or {}
    sources = combined_event.get("sources") or {}

    events_in = signals.get("behavioral_events")
    events_out: list[dict[str, Any]] = []
    if isinstance(events_in, list):
        for ev in events_in:
            if len(events_out) >= _PROMPT_MAX_EVENTS:
                break
            if not isinstance(ev, dict):
                continue
            events_out.append(
                {
                    "offset_ms": ev.get("offset_ms"),
                    "category": ev.get("category"),
                    "syscall": _clip(ev.get("syscall"), 256),
                    "summary": _clip(ev.get("summary"), 512),
                }
            )

    def _presence(name: str) -> str:
        src = sources.get(name) if isinstance(sources, dict) else None
        if isinstance(src, dict):
            return str(src.get("presence", "absent"))
        return "absent"

    return {
        "inputs_present": combined_event.get("inputs_present", []),
        "complete": bool(combined_event.get("complete")),
        "static": {
            "presence": _presence("static"),
            "highest_severity": signals.get("static_highest_severity"),
            "total_findings": (sources.get("static") or {}).get("total_findings")
            if isinstance(sources.get("static"), dict)
            else None,
        },
        "dynamic": {
            "presence": _presence("dynamic"),
            "outcome": signals.get("dynamic_outcome"),
        },
        "behavioral_events": events_out,
        "behavioral_event_count": signals.get("behavioral_event_count"),
        "behavioral_events_prompt_capped": (
            isinstance(events_in, list) and len(events_in) > _PROMPT_MAX_EVENTS
        ),
    }


# The system instruction that FRAMES the model as a correlation engine, NOT a
# decision engine. It explicitly forbids a verdict and pins the required output
# shape. Kept here (not just in the prompts/ template) so the pure builder is
# self-contained + offline-testable and the template + code cannot drift.
SYSTEM_INSTRUCTION = (
    "You are a security EVIDENCE CORRELATION engine for a zero-trust inspection "
    "pipeline. You are given a single normalized combined-event record for one "
    "artifact: static-analysis findings (misconfigurations) alongside dynamic "
    "behavioral indicators observed while the artifact ran in an isolated "
    "detonation chamber. Your ONLY job is to CORRELATE this evidence: explain where "
    "the static findings are supported, explained, or contradicted by the observed "
    "behavior, and surface behavior that has no static explanation. "
    "You MUST NOT render a verdict. Do NOT decide or state whether the artifact is "
    "safe, unsafe, malicious, benign, approved, rejected, should be forwarded, or "
    "should pass or fail. There is no verdict field and you must not invent one. A "
    "human reviewer makes that decision downstream from your correlation. "
    "Describe severity only as how NOTABLE a correlated observation is (evidence), "
    "never as a decision. "
    "Respond with ONLY a single JSON object, no prose before or after, matching "
    "exactly this shape: "
    '{"summary": <string>, "findings": [{"kind": one of '
    '["correlated","static_only","dynamic_only","contradiction"], "severity": one '
    'of ["unknown","none","info","low","medium","high","critical"], "title": '
    '<string>, "detail": <string, optional>, "static_refs": [<string>, ...], '
    '"behavioral_refs": [<string>, ...]}]}. '
    "If there is insufficient evidence to correlate, return an empty findings list "
    "and say so in the summary. Keep the summary under 3000 characters."
)


def build_user_message(combined_event: dict[str, Any]) -> str:
    """Render the bounded evidence view into the user-turn text for the model.
    Pure. The evidence is embedded as compact JSON so the model receives structured,
    bounded input (never raw content)."""
    payload = build_prompt_payload(combined_event)
    return (
        "Correlate the static findings against the dynamic behavior in this "
        "normalized combined-event record. Return ONLY the JSON object described in "
        "your instructions.\n\nCOMBINED_EVENT_EVIDENCE:\n"
        + json.dumps(payload, sort_keys=True, separators=(",", ":"))
    )


def build_invoke_body(
    combined_event: dict[str, Any],
    *,
    max_tokens: int = 2000,
    temperature: float = 0.0,
) -> dict[str, Any]:
    """Build the Amazon Nova Invoke API request body (schemaVersion messages-v1).
    Pure — the awsio seam serializes + sends it. temperature 0 for the most
    reproducible correlation possible from a non-deterministic model."""
    return {
        "schemaVersion": "messages-v1",
        "system": [{"text": SYSTEM_INSTRUCTION}],
        "messages": [
            {"role": "user", "content": [{"text": build_user_message(combined_event)}]}
        ],
        "inferenceConfig": {
            "maxTokens": max_tokens,
            "temperature": temperature,
            "topP": 1.0,
        },
    }


# --- 2. RESPONSE PARSING (defensive, bounded, verdict-free) -------------------


def extract_text(response_body: Any) -> str | None:
    """Pull the model's text out of a Nova Invoke response body (already parsed to a
    dict by the seam). Nova returns output.message.content[] where each part may
    carry a 'text'. Returns the concatenated text or None if the shape is
    unexpected. Pure — tolerant of a malformed response (returns None, never
    raises)."""
    if not isinstance(response_body, dict):
        return None
    output = response_body.get("output")
    if not isinstance(output, dict):
        return None
    message = output.get("message")
    if not isinstance(message, dict):
        return None
    content = message.get("content")
    if not isinstance(content, list):
        return None
    parts: list[str] = []
    for part in content:
        if isinstance(part, dict) and isinstance(part.get("text"), str):
            parts.append(part["text"])
    text = "".join(parts).strip()
    return text or None


def _extract_json_object(text: str) -> Any:
    """Best-effort: parse the first top-level JSON object out of ``text``. Handles a
    model that wraps the JSON in prose or a ```json fence. Returns the parsed object
    or None. Pure — never raises."""
    if not isinstance(text, str) or not text:
        return None
    # Fast path: the whole thing is JSON.
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        pass
    # Strip a common ``` fence.
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        # drop a leading language tag like 'json\n'
        newline = stripped.find("\n")
        if newline != -1:
            candidate = stripped[newline + 1 :]
            try:
                return json.loads(candidate)
            except (ValueError, TypeError):
                pass
    # Slice from the first { to the matching last } and try that.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except (ValueError, TypeError):
            return None
    return None


def _parse_finding(raw: Any) -> dict[str, Any] | None:
    """Coerce one raw model finding into a bounded, allow-listed correlation
    finding. Drops (returns None) a finding missing its required fields or with an
    out-of-enum kind/severity, rather than fabricating a value. Pure. Any
    verdict-shaped key the model included is simply not copied (allow-list)."""
    if not isinstance(raw, dict):
        return None
    kind = raw.get("kind")
    if kind not in CORRELATION_KINDS:
        return None
    severity = raw.get("severity")
    if severity not in CORRELATION_SEVERITIES:
        severity = "unknown"
    title = _clip(raw.get("title"), _MAX_TITLE)
    if not title:
        return None
    out: dict[str, Any] = {"kind": kind, "severity": severity, "title": title}
    detail = _clip(raw.get("detail"), _MAX_DETAIL)
    if detail:
        out["detail"] = detail
    for key in ("static_refs", "behavioral_refs"):
        refs_in = raw.get(key)
        if isinstance(refs_in, list):
            refs_out: list[str] = []
            for r in refs_in:
                if len(refs_out) >= _MAX_REFS:
                    break
                clipped = _clip(r, _MAX_REF)
                if clipped:
                    refs_out.append(clipped)
            if refs_out:
                out[key] = refs_out
    return out


def parse_correlation(text: str | None) -> tuple[dict[str, Any] | None, bool]:
    """Defensively parse the model's text into a bounded ``correlation`` object.

    Returns ``(correlation, truncated)`` where ``correlation`` is the bounded object
    (or None if the text could not be parsed at all) and ``truncated`` is True iff
    the findings list was capped to MAX_FINDINGS. NEVER raises, NEVER fabricates,
    NEVER emits a verdict field (the allow-list simply does not copy one). Pure.
    """
    parsed = _extract_json_object(text) if text is not None else None
    if not isinstance(parsed, dict):
        return None, False

    summary = _clip(parsed.get("summary"), _MAX_SUMMARY)
    if summary is None:
        # A correlation with no summary is not a usable correlation; treat as
        # unparseable rather than inventing one.
        return None, False

    raw_findings = parsed.get("findings")
    findings: list[dict[str, Any]] = []
    truncated = False
    if isinstance(raw_findings, list):
        for raw in raw_findings:
            if len(findings) >= _MAX_FINDINGS:
                truncated = True
                break
            finding = _parse_finding(raw)
            if finding is not None:
                findings.append(finding)

    correlation: dict[str, Any] = {"summary": summary, "findings": findings}
    correlation["finding_count"] = len(findings)
    if findings:
        worst = max(findings, key=lambda f: _severity_rank(f["severity"]))
        correlation["highest_correlation_severity"] = worst["severity"]
    return correlation, truncated


def build_result(
    *,
    intake_id: str,
    sha256: str,
    correlated_at: str,
    contract_version: str,
    status: str,
    model_id: str | None = None,
    attempts: int | None = None,
    latency_ms: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    truncated: bool | None = None,
    combined_complete: bool | None = None,
    combined_event_contract_version: str | None = None,
    status_detail: str | None = None,
    correlation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the full DERIVED correlation-result record (``correlation.contract
    .v1``). Integrity-keyed by intake_id + sha256. Pure — the handler supplies the
    invocation facts + the parsed correlation. Only sets ``correlation`` when the
    status is 'correlated' AND a correlation object was produced (never fabricated).
    """
    result: dict[str, Any] = {
        "contract_version": contract_version,
        "intake_id": intake_id,
        "sha256": sha256,
        "correlated_at": correlated_at,
        "status": status,
    }
    detail = _clip(status_detail, _MAX_STATUS_DETAIL)
    if detail:
        result["status_detail"] = detail
    mid = _clip(model_id, 256)
    if mid:
        result["model_id"] = mid
    if isinstance(attempts, int) and not isinstance(attempts, bool):
        result["attempts"] = max(0, min(100, attempts))
    if isinstance(latency_ms, int) and not isinstance(latency_ms, bool):
        result["latency_ms"] = max(0, min(3600000, latency_ms))
    if isinstance(input_tokens, int) and not isinstance(input_tokens, bool):
        result["input_tokens"] = max(0, min(1000000, input_tokens))
    if isinstance(output_tokens, int) and not isinstance(output_tokens, bool):
        result["output_tokens"] = max(0, min(1000000, output_tokens))
    if isinstance(truncated, bool):
        result["truncated"] = truncated
    if isinstance(combined_complete, bool):
        result["combined_complete"] = combined_complete
    cev = _clip(combined_event_contract_version, 16)
    if cev:
        result["combined_event_contract_version"] = cev
    if status == STATUS_CORRELATED and isinstance(correlation, dict):
        result["correlation"] = correlation
    return result
