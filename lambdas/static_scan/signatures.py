"""ZTIE Story 2.2 / 2.2G — signature-based scanning (PURE logic).

Beyond the four config/SAST tools (2.1), this engine runs SIGNATURE-BASED detection
for known-bad patterns that lint / policy / SAST miss: dangerous code constructs and
known-bad indicators (IoC-style markers). It emits NORMALIZED findings in the SAME
shape as the other tools, tagged with the ``signature`` check_family and the
``signature-scan`` tool, so Phase-3 correlation consumes one format.

Story 2.2G — SECRET detection is now owned SOLELY by the compiled ``gitleaks`` tool
(``scanners.run_gitleaks`` + ``normalize.normalize_gitleaks``). The embedded SECRET
regex rules this engine shipped in Story 2.2 were REMOVED (superseded) so there is
one deterministic source of truth for secrets and no duplicate secret findings. The
DANGEROUS and MALWARE families REMAIN here — gitleaks does not cover reverse shells,
EICAR, crypto-miners, ``curl|sh``, ``eval``/``exec``, insecure-TLS, world-writable
bits, etc. — so this engine still complements gitleaks + the class-specific tools.

Design (the 2.1 lesson — pure logic + a thin seam; this is the pure engine):
  * PURE. No boto3, no subprocess, no network, no I/O — it takes the artifact BYTES
    (already read by the ``awsio`` seam) and returns normalized findings. Offline-
    testable with stdlib ``unittest`` (no PyPI). The file read stays in ``handler``.
  * NON-EXECUTING (RD-001). It scans the artifact as DATA with compiled regexes over
    the decoded text; it NEVER runs the artifact. This is the whole reason a
    signature engine belongs in the static lane, not the detonation lane.
  * EVIDENCE, NEVER A VERDICT. A signature hit is evidence with a normalized
    severity; nothing here decides PASS/FAIL/forward/safe.
  * NEVER RAISES / NEVER CRASHES THE LANE (DoD). ``scan_bytes`` catches everything
    and returns whatever it found; the caller records a per-tool ``error`` only if
    the engine itself failed to run. A single bad rule cannot take the lane down.
  * BOUNDED. Matched text is NEVER echoed verbatim (a secret must not leak into the
    findings document); only a bounded, redacted message + location is emitted. The
    number of findings is capped so a pathological artifact cannot produce an
    unbounded result.
  * REAL, NON-MOCK RULESET. The rules below are a real, curated detection set
    (secret patterns modelled on the well-known detect-secrets / gitleaks families,
    dangerous-construct patterns, and IoC markers), embedded as data and versioned
    with the code (RD-025). It is not a placeholder.

Rule id convention: ``ZTIE-SIG-<FAMILY>-<nnn>`` where FAMILY is one of SECRET /
DANGEROUS / MALWARE (compliance.py maps the FAMILY token to controls). This keeps
signature findings traceable to the exact rule and to a control family.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# The tool + family names (must match the contract enums + compliance.py).
SIGNATURE_TOOL = "signature-scan"
FAMILY_SIGNATURE = "signature"

# Signature ruleset version. Bump when the rules change materially so a stored
# finding is traceable to the exact ruleset that produced it (RD-025).
RULESET_VERSION = "2026-09-03"

# Bounds.
_MAX_FINDINGS = 2000
_MAX_SCAN_BYTES = 5 * 1024 * 1024  # scan at most 5 MiB of decoded text
_MESSAGE_MAX = 2048
_RULE_ID_MAX = 256

# Normalized severities (must match normalize.SEVERITY_ORDER).
_INFO, _LOW, _MEDIUM, _HIGH, _CRITICAL = "info", "low", "medium", "high", "critical"


@dataclass(frozen=True)
class SignatureRule:
    """One signature rule. ``pattern`` is a compiled regex matched against the
    decoded artifact text (NON-EXECUTING — pure pattern match over data)."""

    rule_id: str
    title: str
    severity: str
    pattern: re.Pattern[str]
    # Redact the match in the message (secrets) vs. quote a bounded snippet
    # (dangerous constructs are not sensitive). Secrets are ALWAYS redacted.
    redact: bool = True


def _c(pat: str, flags: int = 0) -> re.Pattern[str]:
    return re.compile(pat, flags)


# --- The ruleset -------------------------------------------------------------
# Real, curated detection rules. Secret families are modelled on the well-known
# detect-secrets / gitleaks provider-token shapes; dangerous constructs cover
# language-agnostic high-risk calls; MALWARE covers IoC-style markers. Rules are
# deliberately high-signal so a planted secret / known-bad pattern is detected.

_RULES: tuple[SignatureRule, ...] = (
    # --- SECRET family — SUPERSEDED by gitleaks (Story 2.2G) ----------------
    # The embedded SECRET regex rules (ZTIE-SIG-SECRET-001..008) that Story 2.2
    # shipped were REMOVED in Story 2.2G: the compiled, deterministic ``gitleaks``
    # tool is now the SOLE source of truth for secret detection (Decision C — no
    # fragile custom secret regexes, no duplicate secret findings from two engines).
    # gitleaks runs in the same lane via toolplan + scanners.run_gitleaks and its
    # findings normalize into the SAME `signature` check_family. The DANGEROUS and
    # MALWARE families below are RETAINED — gitleaks does not cover reverse shells,
    # EICAR, crypto-miners, curl|sh, eval/exec, etc., so removing them would be an
    # un-replaced capability regression.
    # --- DANGEROUS family (bounded snippet, not sensitive) -----------------
    SignatureRule(
        "ZTIE-SIG-DANGEROUS-001",
        "Shell pipe to interpreter (curl|wget ... | sh)",
        _HIGH,
        _c(r"(?i)\b(?:curl|wget)\b[^\n|]{0,200}\|\s*(?:sudo\s+)?(?:ba|z|)sh\b"),
        redact=False,
    ),
    SignatureRule(
        "ZTIE-SIG-DANGEROUS-002",
        "Dynamic code evaluation (eval/exec/Function)",
        _MEDIUM,
        _c(r"\b(?:eval|exec|system|popen|Function)\s*\(", re.IGNORECASE),
        redact=False,
    ),
    SignatureRule(
        "ZTIE-SIG-DANGEROUS-003",
        "Base64-decode piped to shell/eval",
        _HIGH,
        _c(r"(?i)base64\s+(?:-d|--decode)[^\n|]{0,120}\|\s*(?:ba|z|)sh\b"),
        redact=False,
    ),
    SignatureRule(
        "ZTIE-SIG-DANGEROUS-004",
        "Insecure TLS verification disabled",
        _MEDIUM,
        _c(r"(?i)(?:verify\s*=\s*False|InsecureSkipVerify\s*[:=]\s*true|--no-check-certificate)"),
        redact=False,
    ),
    SignatureRule(
        "ZTIE-SIG-DANGEROUS-005",
        "World-writable permission bits (chmod 777)",
        _LOW,
        _c(r"\bchmod\s+(?:-R\s+)?0?777\b"),
        redact=False,
    ),
    # --- MALWARE / IoC family (bounded snippet) -----------------------------
    SignatureRule(
        "ZTIE-SIG-MALWARE-001",
        "Reverse shell pattern",
        _CRITICAL,
        _c(
            r"(?i)(?:/dev/tcp/\d|nc\s+-e\b|ncat\s+-e\b|"
            r"socket\.socket\([^)]*\)[^\n]{0,120}connect\()",
        ),
        redact=False,
    ),
    SignatureRule(
        "ZTIE-SIG-MALWARE-002",
        "EICAR anti-malware test signature",
        _CRITICAL,
        _c(r"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"),
        redact=False,
    ),
    SignatureRule(
        "ZTIE-SIG-MALWARE-003",
        "Suspicious crypto-miner reference",
        _HIGH,
        _c(r"(?i)\b(?:xmrig|stratum\+tcp://|minerd|cryptonight)\b"),
        redact=False,
    ),
)


@dataclass
class SignatureScanResult:
    """Outcome of the signature engine over one artifact. ``findings`` are already
    normalized into the ZTIE findings shape. Mirrors scanners.ScanResult so the
    handler treats the signature engine like any other tool."""

    tool: str = SIGNATURE_TOOL
    status: str = "ok"  # "ok" | "error"
    findings: list[dict[str, Any]] = field(default_factory=list)
    error_reason: str | None = None
    duration_ms: int = 0


def _decode(data: bytes | str) -> str:
    if isinstance(data, str):
        return data[:_MAX_SCAN_BYTES]
    return data[:_MAX_SCAN_BYTES].decode("utf-8", "replace")


def _line_of(text: str, index: int) -> int:
    """1-based line number of a match offset. Never raises."""
    if index <= 0:
        return 1
    return text.count("\n", 0, index) + 1


def _redacted(match_text: str) -> str:
    """Redact a matched secret: keep a short non-sensitive prefix, mask the rest.
    A secret must NEVER be echoed verbatim into the findings document (RD-009 keeps
    the doc in Forensic, but we still never persist a live credential)."""
    m = match_text.strip()
    if len(m) <= 4:
        return "****"
    return f"{m[:4]}{'*' * min(len(m) - 4, 12)} (redacted)"


def _snippet(match_text: str, cap: int = 120) -> str:
    """A bounded, single-line snippet of a non-sensitive dangerous-construct match."""
    s = " ".join(match_text.split())
    return s[:cap]


def _finding_from_match(rule: SignatureRule, match: re.Match[str], filename: str, text: str) -> dict[str, Any]:
    """Build ONE normalized finding for a signature match. Same shape the other
    tools produce (tool, rule_id, severity, check_family, message, location)."""
    if rule.redact:
        detail = _redacted(match.group(0))
        message = f"{rule.title}: potential secret detected ({detail})"
    else:
        message = f"{rule.title}: matched '{_snippet(match.group(0))}'"
    finding: dict[str, Any] = {
        "tool": SIGNATURE_TOOL,
        "rule_id": rule.rule_id[:_RULE_ID_MAX],
        "severity": rule.severity,
        "check_family": FAMILY_SIGNATURE,
        "message": message[:_MESSAGE_MAX],
    }
    location: dict[str, Any] = {"start_line": _line_of(text, match.start())}
    if filename:
        location["file"] = filename[:1024]
    finding["location"] = location
    return finding


def scan_bytes(data: bytes | str, filename: str = "") -> SignatureScanResult:
    """Run every signature rule over the artifact text (NON-EXECUTING). Returns a
    SignatureScanResult; NEVER raises. Findings are bounded + secrets redacted.

    A rule that raises (a pathological regex/input) is skipped and does not abort
    the scan — the whole engine reports ``status=ok`` with whatever it found, or
    ``status=error`` only if decoding/setup itself failed.
    """
    try:
        text = _decode(data)
    except Exception as exc:  # noqa: BLE001 - a decode failure must not crash the lane
        return SignatureScanResult(status="error", error_reason=f"decode failed: {exc}"[:512])

    findings: list[dict[str, Any]] = []
    for rule in _RULES:
        if len(findings) >= _MAX_FINDINGS:
            break
        try:
            for match in rule.pattern.finditer(text):
                findings.append(_finding_from_match(rule, match, filename, text))
                if len(findings) >= _MAX_FINDINGS:
                    break
        except Exception:  # noqa: BLE001, S112 - one bad rule never crashes the pure engine (no logger by design)
            # Skip this rule; keep scanning with the rest (production resilience).
            continue
    return SignatureScanResult(status="ok", findings=findings)


def ruleset_size() -> int:
    """Number of active signature rules (for logging / diagnostics)."""
    return len(_RULES)
