"""ZTIE Story 2.4 — pure unit tests for the behavioral-telemetry builders.

Offline, stdlib-only (behavior.py has NO boto3, no AWS, no clock reads). Exercises
the strace-trace parser (syscalls / network-as-INTENT / filesystem), the fd-path
extraction that must NEVER leak a write buffer as a path, and the bounded builders.
"""

from __future__ import annotations

import unittest

import behavior as bh

# A realistic strace -f -tt -y snippet covering exec, file ops (open/create/write/
# unlink/rename/chmod), and network connection ATTEMPTS (which fail in the isolated
# VPC — the attempt is the signal).
_SAMPLE = """
1234  14:03:22.100000 execve("/tmp/ztie/a.sh", ["a.sh"], 0x7ffe /* 20 vars */) = 0
1234  14:03:22.200000 openat(AT_FDCWD, "/etc/passwd", O_RDONLY) = 3</etc/passwd>
1234  14:03:22.210000 openat(AT_FDCWD, "/tmp/evil.txt", O_WRONLY|O_CREAT, 0644) = 4</tmp/evil.txt>
1234  14:03:22.220000 write(4</tmp/evil.txt>, "SECRETBUFFERDATA", 16) = 16
1234  14:03:22.225000 chmod("/tmp/evil.txt", 0777) = 0
1234  14:03:22.230000 rename("/tmp/evil.txt", "/tmp/evil2.txt") = 0
1234  14:03:22.235000 unlink("/tmp/evil2.txt") = 0
1234  14:03:22.240000 socket(AF_INET, SOCK_STREAM, IPPROTO_TCP) = 5
1234  14:03:22.250000 connect(5, {sa_family=AF_INET, sin_port=htons(443), sin_addr=inet_addr("93.184.216.34")}, 16) = -1 ENETUNREACH (Network is unreachable)
1234  14:03:22.255000 connect(5, {sa_family=AF_INET, sin_port=htons(443), sin_addr=inet_addr("93.184.216.34")}, 16) = -1 ENETUNREACH (Network is unreachable)
1234  14:03:22.260000 connect(6, {sa_family=AF_INET, sin_port=htons(53), sin_addr=inet_addr("8.8.8.8")}, 16) = -1 ENETUNREACH (Network is unreachable)
1234  14:03:22.270000 connect(7, {sa_family=AF_UNIX, sun_path="/var/run/nscd/socket"}, 110) = -1 ENOENT
+++ exited with 0 +++
"""


class TestSummarizeTrace(unittest.TestCase):
    def setUp(self):
        self.s = bh.summarize_trace(_SAMPLE)

    def test_syscalls_tally(self):
        sc = self.s["syscalls"]
        self.assertGreater(sc["total"], 0)
        self.assertGreater(sc["distinct"], 0)
        # connect appears 4 times (2 to :443, 1 to :53, 1 AF_UNIX) -> most frequent.
        top_names = {row["name"]: row["count"] for row in sc["top"]}
        self.assertEqual(top_names.get("connect"), 4)

    def test_network_is_intent_not_success(self):
        net = self.s["network"]
        # 4 connect attempts total (all failed in the isolated VPC).
        self.assertEqual(net["connect_attempts"], 4)
        # The AF_UNIX connect has no inet destination, so distinct inet dests = 2.
        self.assertEqual(net["distinct_destinations"], 2)
        self.assertEqual(net["dns_lookups"], 1)  # the :53 connect
        dests = {d["destination"]: d for d in net["destinations"]}
        self.assertIn("93.184.216.34:443", dests)
        self.assertEqual(dests["93.184.216.34:443"]["attempts"], 2)
        # NOTHING connected (no egress) — intent recorded, success false.
        self.assertFalse(dests["93.184.216.34:443"]["connected"])
        self.assertFalse(dests["8.8.8.8:53"]["connected"])

    def test_filesystem_ops_and_paths(self):
        fs = self.s["filesystem"]
        self.assertGreaterEqual(fs["total_ops"], 5)
        self.assertEqual(fs.get("creates"), 1)   # the O_CREAT open
        self.assertEqual(fs.get("opens"), 1)     # the /etc/passwd read
        self.assertEqual(fs.get("writes"), 1)
        self.assertEqual(fs.get("deletes"), 1)
        self.assertEqual(fs.get("renames"), 1)
        self.assertEqual(fs.get("permission_changes"), 1)
        pathops = {(p["path"], p["op"]) for p in fs["paths"]}
        self.assertIn(("/tmp/evil.txt", "create"), pathops)
        self.assertIn(("/etc/passwd", "open"), pathops)
        self.assertIn(("/tmp/evil2.txt", "delete"), pathops)

    def test_write_buffer_never_leaked_as_path(self):
        # The write(4</tmp/evil.txt>, "SECRETBUFFERDATA", 16) buffer must be read as
        # the fd-decoration path, NOT the quoted buffer content.
        fs = self.s["filesystem"]
        self.assertIn(("/tmp/evil.txt", "write"), {(p["path"], p["op"]) for p in fs["paths"]})
        for p in fs["paths"]:
            self.assertNotIn("SECRETBUFFERDATA", p["path"])

    def test_empty_trace_yields_zeroed_summaries(self):
        s = bh.summarize_trace("")
        self.assertEqual(s["syscalls"]["total"], 0)
        self.assertEqual(s["network"]["connect_attempts"], 0)
        self.assertEqual(s["filesystem"]["total_ops"], 0)
        # A captured-but-silent run is still valid EVIDENCE (no crash, no None).
        self.assertEqual(s["syscalls"].get("top", []), [])

    def test_none_trace_is_safe(self):
        s = bh.summarize_trace(None)
        self.assertEqual(s["syscalls"]["total"], 0)

    def test_per_pid_banner_lines_are_ignored(self):
        # Story 2.4R fix: the on-host emit now prints a per-PID banner
        # ``=== ZTIE trace file: <path> ===`` before each per-PID file's content so a
        # noisy sibling PID cannot truncate the artifact's own trace out. The parser
        # must treat those banners as non-syscall noise (not count them, not crash),
        # while still tallying the real syscall lines from every PID block.
        trace = (
            "=== ZTIE trace file: /tmp/ztie/behavior.strace.1234 ===\n"
            '1234  14:03:22.100000 execve("/tmp/ztie/a.sh", ["a.sh"], 0x7ffe) = 0\n'
            '1234  14:03:22.220000 write(4</tmp/evil.txt>, "SECRETBUFFERDATA", 16) = 16\n'
            "=== ZTIE trace file: /tmp/ztie/behavior.strace.1299 ===\n"
            '1299  14:03:22.300000 openat(AT_FDCWD, "/tmp/child.txt", O_WRONLY|O_CREAT, 0644) = 3</tmp/child.txt>\n'
        )
        s = bh.summarize_trace(trace)
        top = {row["name"]: row["count"] for row in s["syscalls"]["top"]}
        # Real syscalls from BOTH PID blocks tallied; the banner is not a syscall.
        self.assertEqual(top.get("write"), 1)
        self.assertEqual(top.get("execve"), 1)
        self.assertEqual(top.get("openat"), 1)
        self.assertNotIn("===", top)
        # The write of the planted buffer is present as a write op with the fd-path,
        # and the buffer content is never surfaced as a path.
        pathops = {(p["path"], p["op"]) for p in s["filesystem"]["paths"]}
        self.assertIn(("/tmp/evil.txt", "write"), pathops)
        for p in s["filesystem"]["paths"]:
            self.assertNotIn("SECRETBUFFERDATA", p["path"])

    def test_bounds_capped(self):
        # A trace with >MAX_SAMPLE_ITEMS distinct syscalls caps the top-N sample.
        lines = [
            f'1  00:00:00.0 syscall{i}(0) = 0' for i in range(bh.MAX_SAMPLE_ITEMS + 20)
        ]
        s = bh.summarize_trace("\n".join(lines))
        self.assertLessEqual(len(s["syscalls"].get("top", [])), bh.MAX_SAMPLE_ITEMS)

    def test_real_connect_from_bash_dev_tcp_is_network_intent(self):
        # Story 2.4R fix (network): the 2.4R FAIL used a `dash` `/dev/tcp` artifact,
        # which dash does NOT support, so it became a file openat (ENOENT) and 0
        # connect_attempts. A REAL network artifact (bash /dev/tcp, curl, nc) issues a
        # genuine connect() syscall. The parser must count that as a connect ATTEMPT
        # with the destination even though it fails (no egress in the isolated VPC).
        # This is exactly the line `bash -c 'exec 3<>/dev/tcp/93.184.216.34/443'`
        # produces under strace (a socket() then a connect() to the inet sockaddr).
        trace = (
            '4321  15:00:00.100000 socket(AF_INET, SOCK_STREAM, IPPROTO_IP) = 3<socket:[100]>\n'
            '4321  15:00:00.110000 connect(3<socket:[100]>, {sa_family=AF_INET, '
            'sin_port=htons(443), sin_addr=inet_addr("93.184.216.34")}, 16) '
            "= -1 ENETUNREACH (Network is unreachable)\n"
        )
        s = bh.summarize_trace(trace)
        net = s["network"]
        self.assertEqual(net["connect_attempts"], 1)
        self.assertEqual(net["distinct_destinations"], 1)
        d = {x["destination"]: x for x in net["destinations"]}
        self.assertIn("93.184.216.34:443", d)
        # INTENT recorded; the attempt failed (no egress) so connected is False.
        self.assertFalse(d["93.184.216.34:443"]["connected"])

    def test_successful_connect_marked_connected(self):
        # A hypothetical ret==0 connect (would be salient past containment) is
        # recorded connected=True.
        line = (
            '1 00:00:00.0 connect(3, {sa_family=AF_INET, sin_port=htons(80), '
            'sin_addr=inet_addr("10.0.0.1")}, 16) = 0'
        )
        s = bh.summarize_trace(line)
        d = {x["destination"]: x for x in s["network"]["destinations"]}
        self.assertTrue(d["10.0.0.1:80"]["connected"])


class TestBuilders(unittest.TestCase):
    def test_build_capture_enforces_enums(self):
        with self.assertRaises(ValueError):
            bh.build_capture(capture_tool="nope", capture_status="captured")
        with self.assertRaises(ValueError):
            bh.build_capture(capture_tool="strace", capture_status="nope")

    def test_build_capture_constants(self):
        cap = bh.build_capture(
            capture_tool="strace", capture_status="captured",
            capture_started_offset_ms=100, capture_stopped_offset_ms=63000,
        )
        self.assertTrue(cap["host_native"])
        self.assertTrue(cap["no_docker"])
        self.assertEqual(cap["capture_started_offset_ms"], 100)

    def test_offsets_are_clamped_nonnegative(self):
        cap = bh.build_capture(
            capture_tool="strace", capture_status="captured",
            capture_started_offset_ms=-5,
        )
        self.assertEqual(cap["capture_started_offset_ms"], 0)

    def test_build_behavior_omits_summaries_when_absent(self):
        cap = bh.build_capture(
            capture_tool="none", capture_status="tool_unavailable",
            error_reason="strace not present on host",
        )
        beh = bh.build_behavior(capture=cap)
        self.assertEqual(beh["lane"], "dynamic_detonation")
        self.assertNotIn("syscalls", beh)
        self.assertNotIn("network", beh)
        self.assertNotIn("filesystem", beh)

    def test_build_envelope_shape(self):
        cap = bh.build_capture(capture_tool="strace", capture_status="captured")
        env = bh.build_behavior_envelope(
            intake_id="62360e03-dfb1-4655-ac52-2a55345ab6f0",
            sha256="a" * 64,
            captured_at="2026-09-08T00:00:00Z",
            behavior=bh.build_behavior(capture=cap, summaries=bh.summarize_trace(_SAMPLE)),
            contract_version="1.0",
        )
        self.assertEqual(env["contract_version"], "1.0")
        self.assertEqual(env["behavior"]["capture"]["capture_status"], "captured")
        self.assertIn("syscalls", env["behavior"])


if __name__ == "__main__":
    unittest.main()
