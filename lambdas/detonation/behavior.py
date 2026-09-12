"""ZTIE Story 2.4 — PURE behavioral-telemetry builders for the dynamic lane.

Deliberately I/O-free and offline-unit-testable (the proven 1.2 -> 2.2 -> 2.3 lane
pattern: pure logic + a thin boto3 seam). It contains NO boto3, no AWS calls, and no
clock reads beyond what the caller passes in. Its jobs are:

  1. Parse a RAW host trace (RD-030: ``strace -f -tt -y`` output) into a BOUNDED,
     DERIVED behavioral summary — syscall tally, network connection ATTEMPTS
     (INTENT, since the isolated host has no egress), and filesystem operations.
  2. Assemble the bounded, verdict-free behavioral-telemetry envelope that crosses
     the Forensic -> Hub RD-013 gate (``behavior.contract.v1``), enforcing the
     contract's bounds (byte-capped names, maxItems-capped samples) in code so a
     malformed telemetry record can never be shaped here.

Zero-trust invariants baked in here (mirror the contract):
  * EVIDENCE, never a verdict. There is NO verdict / safe / approved / forward field
    anywhere in what this builds. Counts + samples describe what the artifact DID.
  * DERIVED-ONLY + BOUNDED. The full trace stays in Forensic behind a pointer; the
    crossed samples are hard maxItems/byte-capped. Sanitization (2.5) is NOT here.
  * HOST-NATIVE + NO-DOCKER (RD-001) — asserted as constants in the capture facts.
  * RELATIVE CLOCK ONLY — the capture offsets are monotonic ms from detonation
    start (supplied by the caller); never a wall clock.
  * NETWORK = INTENT — records connection ATTEMPTS, not only completed connections.
"""

from __future__ import annotations

import re
from typing import Any

import capturespec

# Contract-mirrored enums (kept in lockstep with gen_behavior_contract.py).
CAPTURE_TOOL_STRACE = capturespec.CAPTURE_TOOL_STRACE  # "strace"
CAPTURE_TOOL_NONE = capturespec.CAPTURE_TOOL_NONE      # "none"
CAPTURE_TOOLS = (CAPTURE_TOOL_STRACE, CAPTURE_TOOL_NONE)

CAPTURE_STATUS_CAPTURED = "captured"
CAPTURE_STATUS_TOOL_UNAVAILABLE = "tool_unavailable"
CAPTURE_STATUS_ERROR = "capture_error"
CAPTURE_STATUS_NOT_RUN = "not_run"
CAPTURE_STATUSES = (
    CAPTURE_STATUS_CAPTURED,
    CAPTURE_STATUS_TOOL_UNAVAILABLE,
    CAPTURE_STATUS_ERROR,
    CAPTURE_STATUS_NOT_RUN,
)

LANE = "dynamic_detonation"

# Contract bounds (mirror gen_behavior_contract.py).
MAX_SAMPLE_ITEMS = 50
MAX_NAME_LEN = 256
MAX_COUNT = 100000000

# --- strace line parsing ------------------------------------------------------
# strace -f -tt -y lines look like (pid optional with -f):
#   1234  14:03:22.123456 openat(AT_FDCWD, "/etc/passwd", O_RDONLY) = 3</etc/passwd>
#   1234  14:03:22.200000 connect(4, {sa_family=AF_INET, sin_port=htons(443),
#                                     sin_addr=inet_addr("93.184.216.34")}, 16) = -1 ...
# A resumed/unfinished pair may span two lines ("<unfinished ...>" / "<... resumed>").
# We extract the SYSCALL NAME robustly and, for a few syscalls, salient args.
_SYSCALL_RE = re.compile(
    r"^(?:\[?pid\s+\d+\]?\s+|\d+\s+)?"          # optional pid prefix (-f)
    r"(?:\d{2}:\d{2}:\d{2}\.\d+\s+)?"            # optional -tt timestamp
    r"(?P<name>[a-zA-Z_][a-zA-Z0-9_]*)\("        # the syscall name + "("
)

# Filesystem syscalls -> the operation class the contract records.
_FS_OP_BY_SYSCALL = {
    "open": "open",
    "openat": "open",
    "creat": "create",
    "mkdir": "create",
    "mkdirat": "create",
    "write": "write",
    "writev": "write",
    "pwrite64": "write",
    "unlink": "delete",
    "unlinkat": "delete",
    "rmdir": "delete",
    "rename": "rename",
    "renameat": "rename",
    "renameat2": "rename",
    "chmod": "permission_change",
    "fchmod": "permission_change",
    "fchmodat": "permission_change",
    "chown": "permission_change",
    "fchown": "permission_change",
    "fchownat": "permission_change",
    "lchown": "permission_change",
}
# Which fs ops are "creates" when the flags say so (O_CREAT on an open/openat).
_OPEN_SYSCALLS = frozenset({"open", "openat"})

# Network syscalls we tally as connection ATTEMPTS / lookups.
_NET_CONNECT_SYSCALLS = frozenset({"connect", "sendto", "sendmsg"})
_NET_SOCKET_SYSCALLS = frozenset({"socket", "socketcall"})

# Pull a quoted path out of a syscall's args (first quoted token).
_QUOTED_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')
# strace -y decorates a file descriptor with its resolved path: e.g. 4</tmp/x> or
# 3</etc/passwd>. Used to recover the path for fd-based ops (write/fchmod/...) whose
# quoted arg is a data BUFFER, not a path — so buffer content is never mistaken for
# a path (and never leaked as one).
_FD_PATH_RE = re.compile(r"\d+<([^>]+)>")
# Syscalls whose FIRST argument is a fd (path lives in the -y fd decoration), NOT a
# path string — so the quoted arg (a data buffer) must NOT be read as a path.
_FD_FIRST_ARG_SYSCALLS = frozenset(
    {"write", "writev", "pwrite64", "fchmod", "fchown"}
)
# Pull an IPv4 dotted quad out of an inet_addr("...") / a bare quad in args.
_IPV4_RE = re.compile(r'inet_addr\("(\d{1,3}(?:\.\d{1,3}){3})"\)')
_IPV6_RE = re.compile(r'inet_pton\([^,]+,\s*"([0-9a-fA-F:]+)"')
_PORT_RE = re.compile(r"htons\((\d+)\)")
# A getaddrinfo/gethostbyname-shaped DNS lookup often shows as a connect to :53 or
# an openat of /etc/resolv.conf; we count port-53 connects as dns_lookups too.


def _clip_name(s: str) -> str:
    return s[:MAX_NAME_LEN]


def parse_syscall_name(line: str) -> str | None:
    """Return the syscall name from one strace line, or None if it is not a
    syscall line (e.g. a blank line, a signal line, or an '+++ exited +++'). Pure."""
    m = _SYSCALL_RE.match(line)
    if not m:
        return None
    return m.group("name")


def _extract_destination(line: str) -> str | None:
    """Best-effort extract a 'ip:port' (or 'ip') destination from a connect/sendto
    line's sockaddr. Returns None when no inet address is present (e.g. an AF_UNIX
    connect). Pure — never resolves or dials anything."""
    ip = None
    m4 = _IPV4_RE.search(line)
    if m4:
        ip = m4.group(1)
    else:
        m6 = _IPV6_RE.search(line)
        if m6:
            ip = m6.group(1)
    if ip is None:
        return None
    mp = _PORT_RE.search(line)
    if mp:
        return f"{ip}:{mp.group(1)}"
    return ip


def _extract_fs_path(syscall: str, line: str) -> str:
    """Best-effort extract the filesystem PATH a syscall operated on. Pure.

    For fd-first-arg syscalls (write / fchmod / ...), the quoted arg is a DATA
    BUFFER, not a path — so we take the path ONLY from the strace ``-y`` fd
    decoration (e.g. ``4</tmp/x>``) and NEVER from the quoted buffer, so buffer
    content can never be mistaken for (or leaked as) a path. For path-arg syscalls
    (open / unlink / rename / chmod-by-path / ...), the path is the first quoted
    token, with the ``-y`` fd decoration as a fallback. Returns '' when no path is
    recoverable."""
    if syscall in _FD_FIRST_ARG_SYSCALLS:
        m = _FD_PATH_RE.search(line)
        return _clip_name(m.group(1)) if m else ""
    m = _QUOTED_RE.search(line)
    if m:
        return _clip_name(m.group(1))
    fd = _FD_PATH_RE.search(line)
    return _clip_name(fd.group(1)) if fd else ""


def _line_connected(line: str) -> bool:
    """True iff the syscall line shows a SUCCESSFUL connect (ret == 0). In the
    isolated VPC this is expected to be false (EINPROGRESS/ENETUNREACH/-1). Pure."""
    # strace shows the return after '=' at end of a finished line.
    tail = line.rsplit("=", 1)[-1].strip()
    return tail.startswith("0") and not tail.startswith("0x")


def summarize_trace(raw_trace: str | None) -> dict[str, Any]:
    """Parse a raw strace trace into the BOUNDED behavioral summary sub-objects.

    Returns {'syscalls': {...}, 'network': {...}, 'filesystem': {...}} shaped
    exactly as the contract requires (bounded counts + capped top-N samples). Pure,
    deterministic, and offline-testable. An empty/None trace yields zeroed summaries
    (a captured-but-silent run is still valid EVIDENCE).
    """
    syscall_counts: dict[str, int] = {}
    fs_path_ops: dict[tuple[str, str], int] = {}
    fs_op_counts: dict[str, int] = {
        "open": 0,
        "write": 0,
        "create": 0,
        "delete": 0,
        "rename": 0,
        "permission_change": 0,
    }
    net_dest_attempts: dict[str, int] = {}
    net_dest_connected: dict[str, bool] = {}
    connect_attempts = 0
    dns_lookups = 0

    for line in (raw_trace or "").splitlines():
        name = parse_syscall_name(line)
        if name is None:
            continue
        syscall_counts[name] = syscall_counts.get(name, 0) + 1

        # --- Filesystem ------------------------------------------------------
        op = _FS_OP_BY_SYSCALL.get(name)
        if op is not None:
            # An open/openat with O_CREAT is a create, not a plain open.
            if name in _OPEN_SYSCALLS and "O_CREAT" in line:
                op = "create"
            path = _extract_fs_path(name, line)
            if op in fs_op_counts:
                fs_op_counts[op] += 1
            if path:
                key = (path, op)
                fs_path_ops[key] = fs_path_ops.get(key, 0) + 1

        # --- Network (INTENT: attempts, not only successes) ------------------
        if name in _NET_CONNECT_SYSCALLS:
            connect_attempts += 1
            dest = _extract_destination(line)
            if dest is not None:
                net_dest_attempts[dest] = net_dest_attempts.get(dest, 0) + 1
                if _line_connected(line):
                    net_dest_connected[dest] = True
                elif dest not in net_dest_connected:
                    net_dest_connected[dest] = False
                # A connect to port 53 is a DNS-lookup-shaped op.
                if dest.endswith(":53"):
                    dns_lookups += 1

    # --- Assemble bounded syscalls summary ----------------------------------
    total_syscalls = sum(syscall_counts.values())
    top_syscalls = [
        {"name": _clip_name(n), "count": c}
        for n, c in sorted(
            syscall_counts.items(), key=lambda kv: (-kv[1], kv[0])
        )[:MAX_SAMPLE_ITEMS]
    ]
    syscalls = {
        "total": min(total_syscalls, MAX_COUNT),
        "distinct": min(len(syscall_counts), MAX_COUNT),
    }
    if top_syscalls:
        syscalls["top"] = top_syscalls

    # --- Assemble bounded network summary -----------------------------------
    destinations = [
        {
            "destination": _clip_name(dest),
            "attempts": min(attempts, MAX_COUNT),
            "connected": bool(net_dest_connected.get(dest, False)),
        }
        for dest, attempts in sorted(
            net_dest_attempts.items(), key=lambda kv: (-kv[1], kv[0])
        )[:MAX_SAMPLE_ITEMS]
    ]
    network = {
        "connect_attempts": min(connect_attempts, MAX_COUNT),
        "distinct_destinations": min(len(net_dest_attempts), MAX_COUNT),
        "dns_lookups": min(dns_lookups, MAX_COUNT),
    }
    if destinations:
        network["destinations"] = destinations

    # --- Assemble bounded filesystem summary --------------------------------
    total_fs_ops = sum(fs_op_counts.values())
    paths = [
        {"path": _clip_name(path), "op": op, "count": min(cnt, MAX_COUNT)}
        for (path, op), cnt in sorted(
            fs_path_ops.items(), key=lambda kv: (-kv[1], kv[0][0])
        )[:MAX_SAMPLE_ITEMS]
    ]
    filesystem: dict[str, Any] = {"total_ops": min(total_fs_ops, MAX_COUNT)}
    for k in ("opens", "writes", "creates", "deletes", "renames", "permission_changes"):
        # Map the plural contract field names to the internal op-count keys.
        internal = {
            "opens": "open",
            "writes": "write",
            "creates": "create",
            "deletes": "delete",
            "renames": "rename",
            "permission_changes": "permission_change",
        }[k]
        if fs_op_counts[internal]:
            filesystem[k] = min(fs_op_counts[internal], MAX_COUNT)
    if paths:
        filesystem["paths"] = paths

    return {"syscalls": syscalls, "network": network, "filesystem": filesystem}


def build_capture(
    *,
    capture_tool: str,
    capture_status: str,
    capture_started_offset_ms: int | None = None,
    capture_stopped_offset_ms: int | None = None,
    trace_truncated: bool | None = None,
    trace_s3_bucket: str | None = None,
    trace_s3_key: str | None = None,
    error_reason: str | None = None,
) -> dict[str, Any]:
    """Assemble the bounded capture-facts sub-object. host_native/no_docker are
    asserted constants (RD-001). Pure; enforces enums + bounds."""
    if capture_tool not in CAPTURE_TOOLS:
        raise ValueError(f"unknown capture_tool {capture_tool!r}")
    if capture_status not in CAPTURE_STATUSES:
        raise ValueError(f"unknown capture_status {capture_status!r}")
    capture: dict[str, Any] = {
        "capture_tool": capture_tool,
        "capture_status": capture_status,
        "host_native": True,
        "no_docker": True,
    }
    if capture_started_offset_ms is not None:
        capture["capture_started_offset_ms"] = max(
            0, min(86400000, int(capture_started_offset_ms))
        )
    if capture_stopped_offset_ms is not None:
        capture["capture_stopped_offset_ms"] = max(
            0, min(86400000, int(capture_stopped_offset_ms))
        )
    if trace_truncated is not None:
        capture["trace_truncated"] = bool(trace_truncated)
    if trace_s3_bucket:
        capture["trace_s3_bucket"] = trace_s3_bucket[:256]
    if trace_s3_key:
        capture["trace_s3_key"] = trace_s3_key[:1024]
    if error_reason:
        capture["error_reason"] = error_reason[:512]
    return capture


def build_behavior(
    *,
    capture: dict[str, Any],
    summaries: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the ``behavior`` object: capture facts + (when captured) the three
    bounded summaries. When capture did not happen (tool_unavailable / not_run /
    capture_error) the summaries are omitted — the gap is recorded in the capture
    facts, never faked. Pure."""
    behavior: dict[str, Any] = {"lane": LANE, "capture": capture}
    if summaries:
        for k in ("syscalls", "network", "filesystem"):
            if k in summaries:
                behavior[k] = summaries[k]
    return behavior


def build_behavior_envelope(
    *,
    intake_id: str,
    sha256: str,
    captured_at: str,
    behavior: dict[str, Any],
    contract_version: str,
) -> dict[str, Any]:
    """Assemble the full DERIVED behavioral-telemetry envelope that crosses to the
    Hub. Integrity-keyed by intake_id + sha256 (bound to the exact artifact
    detonated). ``captured_at`` is the ONLY wall-clock field; behavioral timings are
    relative offsets inside ``behavior.capture``. Pure."""
    return {
        "contract_version": contract_version,
        "intake_id": intake_id,
        "sha256": sha256,
        "captured_at": captured_at,
        "behavior": behavior,
    }
