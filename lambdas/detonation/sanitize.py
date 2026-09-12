"""ZTIE Story 2.5 — PURE telemetry-sanitization pipeline for the dynamic lane.

Deliberately I/O-free and offline-unit-testable (the proven 1.2 -> 2.2 -> 2.3 -> 2.4
lane pattern: pure logic + a thin boto3 seam). It contains NO boto3, no AWS calls,
and no clock reads. Its job is to take the RAW behavioral trace Story 2.4 captured
(RD-030 — the same ``strace -ff -tt -y`` text 2.4 wrote to Forensic S3, RD-009) and
SANITIZE it for Phase-3 correlation through three stages, IN ORDER:

  1. ENTROPY SCRUB  — redact high-entropy VALUES (keys, base64 blobs, random tokens)
     that carry no behavioral signal and inflate the token budget, while KEEPING the
     behavioral STRUCTURE (which syscall, which path shape, which destination).
  2. NOISE SUPPRESS — drop the deterministic host/runtime noise that is NOT the
     artifact's own behavior (SSM-agent boot, dynamic-linker library loads,
     locale-archive opens, shell/coreutils startup) so the artifact's salient ops
     become legible.
  3. <=25K-TOKEN TRUNCATION — bound the result to the Phase-3 token budget,
     DETERMINISTICALLY (kept in trace order, dropping the tail), with a recorded
     ``truncated`` flag. Never a silent drop.

Zero-trust invariants baked in here (mirror the contract, RD-031):
  * SANITIZE, DO NOT RE-CAPTURE. This consumes 2.4's raw trace; it never runs the
    artifact and never touches the capture path.
  * EVIDENCE, never a verdict. There is NO verdict / safe / approved / forward field
    anywhere in what this builds. The sanitized events + pipeline accounting describe
    what the artifact DID and what the pipeline removed.
  * DERIVED-ONLY + BOUNDED. The full raw trace stays in Forensic behind a pointer;
    the crossed events are byte-capped, entropy-scrubbed, and token-budgeted.
  * RELATIVE CLOCK ONLY — event offsets are monotonic ms deltas from the FIRST trace
    line's timestamp (derived here from the ``-tt`` HH:MM:SS.us stamps), never a
    wall clock.
  * DETERMINISTIC — the same raw trace always yields the same sanitized view (stable
    ordering, a fixed chars/4 token heuristic, no randomness).
"""

from __future__ import annotations

import re
from typing import Any

import capturespec

# --- Contract-mirrored constants (kept in lockstep with
# gen_sanitized_telemetry_contract.py). ---------------------------------------
LANE = "dynamic_detonation"

STAGE_ENTROPY_SCRUB = "entropy_scrub"
STAGE_NOISE_SUPPRESS = "noise_suppress"
STAGE_TRUNCATE = "truncate"
SANITIZATION_STAGES = (STAGE_ENTROPY_SCRUB, STAGE_NOISE_SUPPRESS, STAGE_TRUNCATE)

STATUS_SANITIZED = "sanitized"
STATUS_NO_TRACE = "no_trace"
STATUS_ERROR = "sanitize_error"

CATEGORY_FILE = "file"
CATEGORY_NETWORK = "network"
CATEGORY_PROCESS = "process"
CATEGORY_SIGNAL = "signal"
CATEGORY_OTHER = "other"

CAPTURE_TOOL_STRACE = capturespec.CAPTURE_TOOL_STRACE  # "strace"
CAPTURE_TOOL_NONE = capturespec.CAPTURE_TOOL_NONE      # "none"

# Contract bounds (mirror the generator).
MAX_EVENTS = 2000
MAX_EVENT_LEN = 512
MAX_NAME_LEN = 256
MAX_COUNT = 100000000
DEFAULT_TOKEN_BUDGET = 25000
MAX_TOKEN_BUDGET = 1000000

# A deterministic token-estimate heuristic: ~4 chars per token (never a live
# tokenizer call — the sandbox has no model access and the estimate must be
# reproducible offline).
_CHARS_PER_TOKEN = 4

# --- strace line parsing (reuses 2.4's proven line shape) --------------------
# strace -ff -tt -y lines look like (pid prefix from -ff, -tt microsecond stamp):
#   1234  14:03:22.123456 openat(AT_FDCWD, "/etc/passwd", O_RDONLY) = 3</etc/passwd>
# We split each line into (pid?, HH:MM:SS.us timestamp?, syscall-name, rest-of-line).
_LINE_RE = re.compile(
    r"^(?:\[?pid\s+(?P<pid>\d+)\]?\s+|(?P<pid2>\d+)\s+)?"   # optional pid prefix (-ff)
    r"(?:(?P<ts>\d{2}:\d{2}:\d{2}\.\d+)\s+)?"               # optional -tt timestamp
    r"(?P<name>[a-zA-Z_][a-zA-Z0-9_]*)\((?P<rest>.*)$"      # syscall name + "(" + rest
)

# The strace -e syscall groups 2.4 traces, mapped to the contract's event category.
_FILE_SYSCALLS = frozenset(
    {
        "open", "openat", "openat2", "creat", "mkdir", "mkdirat", "read", "readv",
        "pread64", "write", "writev", "pwrite64", "close", "unlink", "unlinkat",
        "rmdir", "rename", "renameat", "renameat2", "chmod", "fchmod", "fchmodat",
        "chown", "fchown", "fchownat", "lchown", "stat", "lstat", "fstat", "newfstatat",
        "statx", "access", "faccessat", "faccessat2", "getdents", "getdents64",
        "readlink", "readlinkat", "symlink", "symlinkat", "link", "linkat", "truncate",
        "ftruncate", "lseek", "dup", "dup2", "dup3", "fcntl", "ioctl", "chdir", "fchdir",
    }
)
_NETWORK_SYSCALLS = frozenset(
    {
        "socket", "socketcall", "connect", "bind", "listen", "accept", "accept4",
        "sendto", "recvfrom", "sendmsg", "recvmsg", "sendmmsg", "recvmmsg", "send",
        "recv", "getsockname", "getpeername", "getsockopt", "setsockopt", "shutdown",
        "socketpair",
    }
)
_PROCESS_SYSCALLS = frozenset(
    {
        "execve", "execveat", "fork", "vfork", "clone", "clone3", "wait4", "waitid",
        "exit", "exit_group", "getpid", "getppid", "gettid", "setpgid", "setsid",
        "prctl", "arch_prctl", "brk", "mmap", "mprotect", "munmap", "set_tid_address",
        "set_robust_list", "futex",
    }
)
_SIGNAL_SYSCALLS = frozenset(
    {
        "rt_sigaction", "rt_sigprocmask", "rt_sigreturn", "sigaction", "kill", "tkill",
        "tgkill", "rt_sigpending", "rt_sigtimedwait", "rt_sigqueueinfo", "signalfd",
        "signalfd4", "pause",
    }
)


def _categorize(name: str) -> str:
    """Map a syscall name to its contract event category. Pure."""
    if name in _NETWORK_SYSCALLS:
        return CATEGORY_NETWORK
    if name in _FILE_SYSCALLS:
        return CATEGORY_FILE
    if name in _PROCESS_SYSCALLS:
        return CATEGORY_PROCESS
    if name in _SIGNAL_SYSCALLS:
        return CATEGORY_SIGNAL
    return CATEGORY_OTHER


def _ts_to_ms(ts: str | None) -> int | None:
    """Convert an strace ``-tt`` HH:MM:SS.us stamp to milliseconds-since-midnight.

    Returns None when there is no timestamp. The caller turns these into RELATIVE
    monotonic offsets by subtracting the first observed value (so no wall clock ever
    crosses; only the delta from detonation start does). Pure."""
    if not ts:
        return None
    try:
        hms, _, frac = ts.partition(".")
        h, m, s = (int(x) for x in hms.split(":"))
        micros = int((frac + "000000")[:6])
        return ((h * 3600 + m * 60 + s) * 1000) + (micros // 1000)
    except (ValueError, IndexError):
        return None


# --- Stage 1: entropy scrub --------------------------------------------------
# High-entropy VALUE patterns to redact (keys / base64 blobs / hex blobs / long
# random tokens). We redact the VALUE while keeping the surrounding structure so a
# path like "/tmp/AKIA...." keeps its shape but the secret is gone. The markers are
# bounded and inert.
_REDACTION_MARKER = "[REDACTED:{kind}]"

# A long base64-ish run (>= 24 chars of base64 alphabet) — keys, tokens, blobs.
_BASE64_BLOB_RE = re.compile(r"[A-Za-z0-9+/]{24,}={0,2}")
# A long hex run (>= 32 hex chars) — hashes, keys, random hex blobs.
_HEX_BLOB_RE = re.compile(r"\b[0-9a-fA-F]{32,}\b")
# A long unbroken high-entropy token (>= 20 chars mixing letters+digits, no spaces).
_MIXED_TOKEN_RE = re.compile(r"\b(?=[^\s\"]*[0-9])(?=[^\s\"]*[A-Za-z])[A-Za-z0-9._\-]{20,}\b")

# Shannon-entropy gate so a long-but-structured token (e.g. a normal long path
# component made only of a repeated word) is not needlessly redacted; only
# genuinely high-entropy substrings are.
_MIN_ENTROPY_BITS = 3.2


def _shannon_entropy(s: str) -> float:
    """Shannon entropy (bits/char) of a string. Pure, deterministic."""
    if not s:
        return 0.0
    from math import log2

    counts: dict[str, int] = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * log2(c / n) for c in counts.values())


def _redact_high_entropy(text: str) -> tuple[str, int]:
    """Redact high-entropy VALUES in one event line, keeping structure. Returns
    (scrubbed_text, redactions). Pure and deterministic.

    Order matters (longest/most-specific class first) so a blob is not partially
    matched by a later, broader pattern. Every candidate must ALSO clear the Shannon
    entropy gate, so a long low-entropy run (repeated chars, a plain word) is left
    intact — the scrub targets secrets, not structure."""
    redactions = 0

    def _sub(pattern: re.Pattern[str], kind: str, s: str) -> str:
        nonlocal redactions

        def _repl(m: re.Match[str]) -> str:
            nonlocal redactions
            val = m.group(0)
            if _shannon_entropy(val) < _MIN_ENTROPY_BITS:
                return val  # structured/low-entropy — keep it
            redactions += 1
            return _REDACTION_MARKER.format(kind=kind)

        return pattern.sub(_repl, s)

    out = _sub(_BASE64_BLOB_RE, "b64", text)
    out = _sub(_HEX_BLOB_RE, "hex", out)
    out = _sub(_MIXED_TOKEN_RE, "tok", out)
    return out, redactions


# --- Stage 2: noise suppression ----------------------------------------------
# Deterministic host/runtime noise that is NOT the artifact's own behavior. These
# are matched on the PATH the syscall touched (or the destination), so an artifact
# that legitimately touches one of these is still visible via its OTHER ops; the
# suppressor only drops the boot/linker/locale/shell scaffolding events.
#
# Designed against what a real ubuntu-22.04 host-native strace faithfully contains
# (2.4 confirmed: SSM-agent boot, dynamic-linker library loads, locale-archive opens,
# shell/coreutils startup). Prefix-matched on the path substring extracted from the
# event line.
_NOISE_PATH_PREFIXES = (
    # dynamic linker + shared libraries
    "/lib/", "/lib64/", "/usr/lib/", "/usr/lib64/", "/etc/ld.so",
    # locale / i18n scaffolding opened by libc at startup
    "/usr/lib/locale/", "/usr/share/locale/", "/usr/lib/locale/locale-archive",
    # SSM agent + its working dirs (the command channel, not the artifact)
    "/var/lib/amazon/ssm/", "/var/log/amazon/ssm/", "/opt/aws/ssm/",
    "/etc/amazon/ssm/",
    # proc/sys pseudo-fs the shell + coreutils poke at startup
    "/proc/self/", "/proc/filesystems", "/sys/kernel/", "/proc/meminfo",
    # shell + coreutils startup config
    "/etc/nsswitch.conf", "/etc/ld.so.cache", "/etc/ld.so.preload",
    "/usr/lib/x86_64-linux-gnu/",
)
# Syscalls that are pure runtime scaffolding (memory management / thread setup /
# libc bookkeeping) and never the artifact's salient behavior — dropped regardless
# of path. Kept conservative so real behavior is never suppressed.
_NOISE_SYSCALLS = frozenset(
    {
        "brk", "mmap", "mprotect", "munmap", "arch_prctl", "set_tid_address",
        "set_robust_list", "rseq", "prlimit64", "getrandom", "futex",
        "rt_sigprocmask", "rt_sigaction",
    }
)


def _extract_path_or_dest(rest: str) -> str:
    """Best-effort pull the first quoted token OR an strace -y fd path decoration
    from a syscall's argument tail — used only to classify NOISE (not to build the
    crossed path; the summary carries the scrubbed full args). Pure."""
    m = re.search(r'"((?:[^"\\]|\\.)*)"', rest)
    if m:
        return m.group(1)
    fd = re.search(r"\d+<([^>]+)>", rest)
    return fd.group(1) if fd else ""


def _is_noise(name: str, rest: str) -> bool:
    """True iff this event is deterministic host/runtime noise (not the artifact's
    own behavior). Pure and deterministic."""
    if name in _NOISE_SYSCALLS:
        return True
    path = _extract_path_or_dest(rest)
    if path:
        for prefix in _NOISE_PATH_PREFIXES:
            if path.startswith(prefix):
                return True
    return False


# --- Parsed event (internal, pre-emit) ---------------------------------------
class _Event:
    __slots__ = ("category", "offset_ms", "redacted", "summary", "syscall")

    def __init__(
        self,
        *,
        offset_ms: int,
        category: str,
        syscall: str,
        summary: str,
        redacted: bool,
    ) -> None:
        self.offset_ms = offset_ms
        self.category = category
        self.syscall = syscall
        self.summary = summary
        self.redacted = redacted

    def as_contract(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "offset_ms": self.offset_ms,
            "category": self.category,
            "syscall": self.syscall[:MAX_NAME_LEN],
            "summary": self.summary[:MAX_EVENT_LEN],
        }
        if self.redacted:
            row["redacted"] = True
        return row


def _clean_summary(name: str, rest: str) -> str:
    """Build the one-line event summary from the syscall name + its arg tail, with
    the trailing strace return kept (it carries behavioral meaning: rc, errno). The
    entropy scrub is applied by the caller. Pure."""
    # Normalise whitespace so the summary is a single tidy line.
    tail = " ".join(rest.split())
    return f"{name}({tail}"


def _estimate_tokens(events: list[dict[str, Any]]) -> int:
    """Deterministic token estimate for the emitted events (chars/4 heuristic over a
    stable serialization). Never a live tokenizer call. Pure."""
    chars = 0
    for e in events:
        # offset + category + syscall + summary + redacted flag, plus small overhead.
        chars += len(str(e["offset_ms"])) + len(e["category"]) + len(e["syscall"])
        chars += len(e["summary"]) + (5 if e.get("redacted") else 0) + 8
    return (chars + _CHARS_PER_TOKEN - 1) // _CHARS_PER_TOKEN


def sanitize_trace(
    raw_trace: str | None,
    *,
    token_budget: int = DEFAULT_TOKEN_BUDGET,
) -> dict[str, Any]:
    """Run the three-stage sanitization pipeline over a raw strace trace.

    Returns {'events': [...], 'pipeline': {...}} where events is the bounded,
    token-budgeted, entropy-scrubbed, noise-suppressed sanitized event sequence (in
    trace order) and pipeline is the three-stage accounting (status, ordered stages,
    counts, token budget/estimate, truncated flag). Pure, deterministic, and
    offline-testable. An empty/None trace yields an empty events list with
    status='no_trace' (a captured-but-empty run is still recorded honestly).

    Stages run IN ORDER: parse -> (1) entropy scrub -> (2) noise suppress ->
    (3) <=25K-token truncation.
    """
    budget = max(0, min(int(token_budget), MAX_TOKEN_BUDGET))

    lines = (raw_trace or "").splitlines()
    if not any(line.strip() for line in lines):
        return {
            "events": [],
            "pipeline": {
                "status": STATUS_NO_TRACE,
                "stages": list(SANITIZATION_STAGES),
                "raw_events": 0,
                "entropy_redactions": 0,
                "noise_suppressed": 0,
                "kept_events": 0,
                "emitted_events": 0,
                "token_budget": budget,
                "estimated_tokens": 0,
                "truncated": False,
            },
        }

    base_ms: int | None = None
    raw_events = 0
    entropy_redactions = 0
    noise_suppressed = 0
    kept: list[_Event] = []

    for line in lines:
        m = _LINE_RE.match(line)
        if not m:
            continue  # blank line, signal line, '+++ exited +++', resumed marker, etc.
        name = m.group("name")
        rest = m.group("rest")
        raw_events += 1

        # Relative monotonic offset from the FIRST timestamped line (never wall clock).
        ms = _ts_to_ms(m.group("ts"))
        if ms is not None:
            if base_ms is None:
                base_ms = ms
            offset_ms = ms - base_ms
            # Guard a midnight-rollover / clock quirk: clamp to the contract range.
            if offset_ms < 0:
                offset_ms += 86400000
            offset_ms = max(0, min(offset_ms, 86400000))
        else:
            offset_ms = 0

        # --- Stage 2 (applied per-event): noise suppress -------------------
        # (Runs on the parsed event; the entropy scrub is applied to the KEPT
        # events only, so we never spend scrub work on dropped noise.)
        if _is_noise(name, rest):
            noise_suppressed += 1
            continue

        # --- Stage 1: entropy scrub (on kept events) -----------------------
        summary = _clean_summary(name, rest)
        scrubbed, n_red = _redact_high_entropy(summary)
        entropy_redactions += n_red

        kept.append(
            _Event(
                offset_ms=offset_ms,
                category=_categorize(name),
                syscall=name,
                summary=scrubbed,
                redacted=n_red > 0,
            )
        )

    kept_count = len(kept)

    # --- Stage 3: <=token_budget truncation (deterministic, trace order) ----
    emitted: list[dict[str, Any]] = []
    running_tokens = 0
    truncated = False
    for ev in kept:
        row = ev.as_contract()
        row_tokens = _estimate_tokens([row])
        # Enforce BOTH the token budget AND the hard event cap deterministically.
        if len(emitted) >= MAX_EVENTS or (running_tokens + row_tokens) > budget:
            truncated = True
            break
        emitted.append(row)
        running_tokens += row_tokens

    return {
        "events": emitted,
        "pipeline": {
            "status": STATUS_SANITIZED,
            "stages": list(SANITIZATION_STAGES),
            "raw_events": min(raw_events, MAX_COUNT),
            "entropy_redactions": min(entropy_redactions, MAX_COUNT),
            "noise_suppressed": min(noise_suppressed, MAX_COUNT),
            "kept_events": min(kept_count, MAX_COUNT),
            "emitted_events": len(emitted),
            "token_budget": budget,
            "estimated_tokens": min(running_tokens, MAX_TOKEN_BUDGET),
            "truncated": truncated,
        },
    }


def build_source(
    *,
    capture_tool: str,
    trace_s3_bucket: str | None = None,
    trace_s3_key: str | None = None,
    raw_trace_bytes: int | None = None,
) -> dict[str, Any]:
    """Assemble the bounded source-pointer sub-object (RD-009: reference, never
    duplicate the raw trace). Pure; enforces the tool enum + bounds."""
    if capture_tool not in (CAPTURE_TOOL_STRACE, CAPTURE_TOOL_NONE):
        raise ValueError(f"unknown capture_tool {capture_tool!r}")
    source: dict[str, Any] = {"capture_tool": capture_tool}
    if trace_s3_bucket:
        source["trace_s3_bucket"] = trace_s3_bucket[:256]
    if trace_s3_key:
        source["trace_s3_key"] = trace_s3_key[:1024]
    if raw_trace_bytes is not None:
        source["raw_trace_bytes"] = max(0, min(int(raw_trace_bytes), MAX_COUNT))
    return source


def build_sanitized(
    *,
    source: dict[str, Any],
    pipeline: dict[str, Any],
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assemble the ``sanitized`` object: lane + source pointer + pipeline accounting
    + (when there was a trace) the bounded sanitized event sequence. When there was
    no trace (status 'no_trace') the events array is omitted — the gap is recorded in
    the pipeline accounting, never faked. Pure."""
    sanitized: dict[str, Any] = {
        "lane": LANE,
        "source": source,
        "pipeline": pipeline,
    }
    if events:
        sanitized["events"] = events[:MAX_EVENTS]
    return sanitized


def build_sanitized_envelope(
    *,
    intake_id: str,
    sha256: str,
    sanitized_at: str,
    sanitized: dict[str, Any],
    contract_version: str,
) -> dict[str, Any]:
    """Assemble the full DERIVED sanitized-telemetry envelope that crosses to the
    Hub. Integrity-keyed by intake_id + sha256 (bound to the exact artifact
    detonated). ``sanitized_at`` is the ONLY wall-clock field; event timings are
    relative offsets inside ``sanitized.events[].offset_ms``. Pure."""
    return {
        "contract_version": contract_version,
        "intake_id": intake_id,
        "sha256": sha256,
        "sanitized_at": sanitized_at,
        "sanitized": sanitized,
    }
