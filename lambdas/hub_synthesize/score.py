"""ZTIE Story 3.3 (RD-038) — PURE prompt-building + response-parsing logic for the
Hub-side three-score risk assessment.

This module is deliberately I/O-free and offline-unit-testable (the proven
1.2 -> 3.2 lane pattern: pure logic + a thin boto3 seam). It contains NO boto3, no
AWS calls, and no clock reads beyond what the caller passes in; it never invokes a
model. Its jobs are all PURE:

  1. BUILD the bounded, evidence-scoped VIEWS for the three Nova Pro calls from the
     ONE normalized combined-event record (3.1) already on the Hub tracking item:
       * STATIC view   — ONLY the static lane's derived evidence.
       * DYNAMIC view  — ONLY the dynamic lane's derived evidence (sanitized behavior
                         + run outcome).
       * COMBINED view — BOTH lanes' derived evidence together.
     Each view is built ONLY from the bounded, sanitized, derived combined event
     (no raw body / findings text / command log / raw trace — RD-009).

  2. BUILD the three scoped Nova Pro prompts. All three share ONE common 0-100 risk
     RUBRIC (so the scores are directly comparable) and a SYSTEM instruction that
     frames the model as a RISK-SCORING engine and FORBIDS a verdict — it asks for a
     0-100 risk score + a short rationale ONLY, never a safe/unsafe/pass/fail/forward
     decision.

  3. DEFENSIVELY PARSE each (non-deterministic, possibly malformed) model response
     into a bounded 0-100 integer + a bounded rationale. A response with no parseable
     score yields None (the caller records status 'unparseable'); a score is clamped
     into [0, 100]; a verdict-shaped key the model returns is simply not copied (the
     record has no slot for it).

Zero-trust invariants baked in here (mirror the contract):
  * EVIDENCE, never a verdict. Nothing this builds or parses is a verdict; the
    prompts ask for a risk SCORE only; the parse extracts a number + rationale.
  * SHARED RUBRIC. The same 0-100 anchoring is stated in all three prompts; only the
    evidence each sees differs, never the scale.
  * BOUNDED IN, BOUNDED OUT. Views are built from the bounded combined event
    (behavioral events further capped for the prompt); the parsed score is clamped
    0-100 and the rationale clipped.
  * HONEST. Absent lane evidence -> the caller skips that call
    ('skipped_no_evidence'); a malformed response -> 'unparseable'; neither
    fabricates a score.
"""

from __future__ import annotations

import json
from typing import Any

# --- Per-score statuses (mirror the contract enum) ----------------------------
STATUS_SCORED = "scored"
STATUS_MODEL_ERROR = "model_error"
STATUS_UNPARSEABLE = "unparseable"
STATUS_SKIPPED_NO_EVIDENCE = "skipped_no_evidence"

# The shared rubric version stamped on the result so all three scores are known to
# be on the same comparable scale. Bump when the rubric text below changes.
RUBRIC_VERSION = "1.0"

# --- Bounds (mirror the contract) ---------------------------------------------
_MAX_RATIONALE = 4000
_MAX_STATUS_DETAIL = 512
# For the prompt, cap the behavioral events embedded so the request stays bounded
# (the combined event already caps them at 2000; tighter here for a small prompt).
_PROMPT_MAX_EVENTS = 200


def _clip(text: Any, max_len: int) -> str | None:
    if text is None:
        return None
    return str(text)[:max_len]


# --- 1. EVIDENCE VIEWS (bounded, derived-only) --------------------------------


def static_evidence(combined_event: dict[str, Any]) -> dict[str, Any]:
    """The bounded STATIC-only evidence view. Pure. Derived data only (RD-009)."""
    signals = combined_event.get("signals") or {}
    sources = combined_event.get("sources") or {}
    static_src = sources.get("static") if isinstance(sources, dict) else None
    static_src = static_src if isinstance(static_src, dict) else {}
    return {
        "presence": str(static_src.get("presence", "absent")),
        "highest_severity": signals.get("static_highest_severity"),
        "total_findings": static_src.get("total_findings"),
    }


def dynamic_evidence(combined_event: dict[str, Any]) -> dict[str, Any]:
    """The bounded DYNAMIC-only evidence view (sanitized behavior + run outcome).
    Pure. Derived data only (RD-009) — the behavioral events are the ALREADY-sanitized
    2.5 events carried through by 3.1, further capped here for the prompt."""
    signals = combined_event.get("signals") or {}
    sources = combined_event.get("sources") or {}
    dyn_src = sources.get("dynamic") if isinstance(sources, dict) else None
    dyn_src = dyn_src if isinstance(dyn_src, dict) else {}
    san_src = sources.get("sanitized") if isinstance(sources, dict) else None
    san_src = san_src if isinstance(san_src, dict) else {}

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

    return {
        "presence": str(dyn_src.get("presence", "absent")),
        "outcome": signals.get("dynamic_outcome"),
        "capture_status": san_src.get("capture_status"),
        "behavioral_event_count": signals.get("behavioral_event_count"),
        "behavioral_events": events_out,
        "behavioral_events_prompt_capped": (
            isinstance(events_in, list) and len(events_in) > _PROMPT_MAX_EVENTS
        ),
    }


def combined_evidence(combined_event: dict[str, Any]) -> dict[str, Any]:
    """The bounded COMBINED evidence view — BOTH lanes' derived evidence together.
    Pure. It carries the SAME per-lane views (not the two scores — the combined score
    is Nova Pro's own assessment of the evidence, not a formula over the numbers) plus
    the completeness facts."""
    return {
        "inputs_present": combined_event.get("inputs_present", []),
        "complete": bool(combined_event.get("complete")),
        "static": static_evidence(combined_event),
        "dynamic": dynamic_evidence(combined_event),
    }


def has_static_evidence(combined_event: dict[str, Any]) -> bool:
    ev = static_evidence(combined_event)
    return ev.get("presence") == "present"


def has_dynamic_evidence(combined_event: dict[str, Any]) -> bool:
    ev = dynamic_evidence(combined_event)
    return ev.get("presence") == "present"


# --- 2. PROMPT BUILDING (shared rubric; verdict FORBIDDEN) --------------------

# The shared 0-100 risk rubric, stated IDENTICALLY in all three prompts so the three
# scores are directly comparable (a "40" means the same risk magnitude regardless of
# which call produced it). Only the EVIDENCE each call sees differs, never the scale.
_RUBRIC = (
    "Risk rubric (0-100, HIGHER = RISKIER), applied IDENTICALLY to every assessment "
    "so scores are comparable:\n"
    "  0-9   none/negligible   — no risk indicators in the evidence.\n"
    "  10-29 low               — minor/informational indicators.\n"
    "  30-49 medium            — notable indicators worth review.\n"
    "  50-74 high              — serious risk indicators.\n"
    "  75-100 critical         — severe risk indicators.\n"
    "Score ONLY what THIS evidence shows. Absent or inconclusive evidence is LOW "
    "risk (not high) unless the evidence itself indicates danger."
)

# The system instruction frames the model as a RISK-SCORING engine, NOT a decision
# engine. It explicitly forbids a verdict and pins the required JSON output shape.
SYSTEM_INSTRUCTION = (
    "You are a security RISK-SCORING engine for a zero-trust inspection pipeline. "
    "You are given bounded, derived evidence about ONE artifact and you assign a "
    "single risk SCORE on a fixed 0-100 rubric (higher = riskier). "
    "You MUST NOT render a verdict. Do NOT decide or state whether the artifact is "
    "safe, unsafe, malicious, benign, approved, rejected, should be forwarded, or "
    "should pass or fail. A human reviewer makes that decision downstream from your "
    "score. Your score is EVIDENCE (how risky the evidence looks), never a decision. "
    + _RUBRIC
    + " Respond with ONLY a single JSON object, no prose before or after, matching "
    'exactly: {"score": <integer 0-100>, "rationale": <string, under 2000 chars, '
    "explaining what in the evidence drove the score>}. Do not include any other "
    "field."
)

# A short label per score kind, embedded in the user turn so the model knows which
# evidence scope it is scoring (the scale + instructions are identical across all).
_KIND_INTRO = {
    "static": (
        "Assess the STATIC-ANALYSIS evidence ONLY (findings a static scanner flagged "
        "without running the artifact). Do not assume anything about runtime behavior."
    ),
    "dynamic": (
        "Assess the DYNAMIC-BEHAVIOR evidence ONLY (what the artifact actually did "
        "when detonated: sanitized syscalls / network / filesystem activity + the run "
        "outcome). Do not assume anything about static findings."
    ),
    "combined": (
        "Assess the artifact's OVERALL risk from BOTH the static-analysis evidence AND "
        "the dynamic-behavior evidence together. Form your OWN independent judgement of "
        "the whole picture (do not merely average the two lanes)."
    ),
}


def build_user_message(kind: str, evidence: dict[str, Any]) -> str:
    """Render a bounded evidence view into the user-turn text for the scoped call.
    Pure. The evidence is embedded as compact JSON (structured, bounded, never raw)."""
    intro = _KIND_INTRO.get(kind, "Assess the evidence.")
    return (
        f"{intro} Return ONLY the JSON object described in your instructions.\n\n"
        f"{kind.upper()}_EVIDENCE:\n"
        + json.dumps(evidence, sort_keys=True, separators=(",", ":"))
    )


def build_invoke_body(
    kind: str,
    evidence: dict[str, Any],
    *,
    max_tokens: int = 1000,
    temperature: float = 0.0,
) -> dict[str, Any]:
    """Build the Amazon Nova Invoke API request body (schemaVersion messages-v1) for
    one scoped score call. Pure — the awsio seam serializes + sends it. temperature 0
    for the most reproducible score possible from a non-deterministic model."""
    return {
        "schemaVersion": "messages-v1",
        "system": [{"text": SYSTEM_INSTRUCTION}],
        "messages": [
            {"role": "user", "content": [{"text": build_user_message(kind, evidence)}]}
        ],
        "inferenceConfig": {
            "maxTokens": max_tokens,
            "temperature": temperature,
            "topP": 1.0,
        },
    }


# --- 3. RESPONSE PARSING (defensive, bounded, verdict-free) -------------------


def extract_text(response_body: Any) -> str | None:
    """Pull the model's text out of a Nova Invoke response body (already parsed to a
    dict by the seam). Nova returns output.message.content[] where each part may carry
    a 'text'. Returns the concatenated text or None. Pure — tolerant of a malformed
    response (returns None, never raises)."""
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
    model that wraps the JSON in prose or a ``` fence. Returns the parsed object or
    None. Pure — never raises."""
    if not isinstance(text, str) or not text:
        return None
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        pass
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        newline = stripped.find("\n")
        if newline != -1:
            candidate = stripped[newline + 1 :]
            try:
                return json.loads(candidate)
            except (ValueError, TypeError):
                pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except (ValueError, TypeError):
            return None
    return None


def _coerce_score(value: Any) -> int | None:
    """Coerce a model-provided score into a bounded 0-100 int (clamped). Accepts an
    int or a numeric string / float. Returns None if not numeric. Pure — the parser
    NEVER fabricates a score, but a numeric out-of-range value is clamped rather than
    dropped (the model meant a number; keep it bounded)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        n = value
    elif isinstance(value, float):
        n = round(value)
    elif isinstance(value, str):
        try:
            n = round(float(value.strip()))
        except (ValueError, TypeError):
            return None
    else:
        return None
    return max(0, min(100, n))


def parse_score(text: str | None) -> tuple[int | None, str | None]:
    """Defensively parse the model's text into ``(score, rationale)``. ``score`` is a
    bounded 0-100 int or None if no numeric score could be parsed (caller records
    'unparseable'); ``rationale`` is the clipped explanation or None. NEVER raises,
    NEVER fabricates, NEVER emits a verdict field (only score + rationale are read).
    Pure."""
    parsed = _extract_json_object(text) if text is not None else None
    if not isinstance(parsed, dict):
        return None, None
    score = _coerce_score(parsed.get("score"))
    rationale = _clip(parsed.get("rationale"), _MAX_RATIONALE)
    if score is None:
        return None, rationale
    return score, rationale


# --- 4. RESULT ASSEMBLY (pure) ------------------------------------------------


def build_score_block(
    *,
    status: str,
    score: int | None = None,
    rationale: str | None = None,
    status_detail: str | None = None,
    model_id: str | None = None,
    attempts: int | None = None,
    latency_ms: int | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
) -> dict[str, Any]:
    """Assemble one bounded score block (static / dynamic / combined). Pure. Sets
    ``score``/``rationale`` ONLY when status is 'scored' (never fabricates a number
    for a failed/absent call)."""
    block: dict[str, Any] = {"status": status}
    if status == STATUS_SCORED and isinstance(score, int) and not isinstance(score, bool):
        block["score"] = max(0, min(100, score))
        if rationale:
            block["rationale"] = rationale
    detail = _clip(status_detail, _MAX_STATUS_DETAIL)
    if detail:
        block["status_detail"] = detail
    mid = _clip(model_id, 256)
    if mid:
        block["model_id"] = mid
    if isinstance(attempts, int) and not isinstance(attempts, bool):
        block["attempts"] = max(0, min(100, attempts))
    if isinstance(latency_ms, int) and not isinstance(latency_ms, bool):
        block["latency_ms"] = max(0, min(3600000, latency_ms))
    if isinstance(input_tokens, int) and not isinstance(input_tokens, bool):
        block["input_tokens"] = max(0, min(1000000, input_tokens))
    if isinstance(output_tokens, int) and not isinstance(output_tokens, bool):
        block["output_tokens"] = max(0, min(1000000, output_tokens))
    return block


def build_result(
    *,
    intake_id: str,
    sha256: str,
    scored_at: str,
    contract_version: str,
    static_block: dict[str, Any],
    dynamic_block: dict[str, Any],
    combined_block: dict[str, Any],
    rubric_version: str = RUBRIC_VERSION,
    combined_complete: bool | None = None,
) -> dict[str, Any]:
    """Assemble the full DERIVED scoring-result record (``scoring.contract.v1``).
    Integrity-keyed by intake_id + sha256. Pure. Always carries all three score
    blocks (each with its own honest status)."""
    result: dict[str, Any] = {
        "contract_version": contract_version,
        "intake_id": intake_id,
        "sha256": sha256,
        "scored_at": scored_at,
        "static": static_block,
        "dynamic": dynamic_block,
        "combined": combined_block,
    }
    rv = _clip(rubric_version, 16)
    if rv:
        result["rubric_version"] = rv
    if isinstance(combined_complete, bool):
        result["combined_complete"] = combined_complete
    return result
