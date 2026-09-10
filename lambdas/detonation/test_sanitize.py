"""ZTIE Story 2.5 — offline unit tests for the PURE sanitization pipeline.

Deliberately stdlib-only (the INTEGRATIONS_ONLY sandbox blocks PyPI). Proves the
three-stage pipeline (entropy scrub -> noise suppress -> <=25K-token truncation)
against a REALISTIC raw strace trace fixture that FAITHFULLY includes what a real
ubuntu-22.04 host-native ``strace -ff -tt -y`` run contains (2.4 confirmed):

  * SSM-agent boot + dynamic-linker library loads + locale-archive opens +
    shell/coreutils startup  -> the deterministic HOST NOISE the suppressor drops,
  * a high-entropy secret blob written by the artifact -> the value the entropy
    scrub redacts while keeping the write's structure,
  * the artifact's OWN salient file/network/process ops -> what MUST be preserved.

The fixture mirrors the shape 2.4's own test fixture uses (pid + HH:MM:SS.us stamp +
syscall + args + return), so it exercises the exact line format the live trace has.
"""

from __future__ import annotations

import unittest

import sanitize as sz

# A realistic raw strace slice: host noise (linker/locale/ssm/proc + mem syscalls),
# a high-entropy secret the artifact writes, and the artifact's own salient ops.
# Relative offsets are derived from the -tt stamps (first line = t0).
_RAW_TRACE = """
4001  14:03:22.100000 execve("/tmp/ztie/sample.sh", ["sample.sh"], 0x7ffe /* 21 vars */) = 0
4001  14:03:22.100500 brk(NULL) = 0x55c2a1b3f000
4001  14:03:22.101000 arch_prctl(0x3001 /* ARCH_??? */, 0x7ffe) = -1 EINVAL
4001  14:03:22.101500 openat(AT_FDCWD, "/etc/ld.so.cache", O_RDONLY|O_CLOEXEC) = 3</etc/ld.so.cache>
4001  14:03:22.102000 openat(AT_FDCWD, "/lib/x86_64-linux-gnu/libc.so.6", O_RDONLY|O_CLOEXEC) = 3
4001  14:03:22.102500 mmap(NULL, 8192, PROT_READ|PROT_WRITE, MAP_PRIVATE, -1, 0) = 0x7f2a
4001  14:03:22.103000 openat(AT_FDCWD, "/usr/lib/locale/locale-archive", O_RDONLY|O_CLOEXEC) = 3</usr/lib/locale/locale-archive>
4001  14:03:22.103500 openat(AT_FDCWD, "/var/lib/amazon/ssm/registration", O_RDONLY) = 4</var/lib/amazon/ssm/registration>
4001  14:03:22.104000 rt_sigprocmask(SIG_BLOCK, NULL, 0x7ffe, 8) = 0
4001  14:03:22.200000 openat(AT_FDCWD, "/tmp/ztie/loot.txt", O_WRONLY|O_CREAT, 0644) = 5</tmp/ztie/loot.txt>
4001  14:03:22.201000 write(5</tmp/ztie/loot.txt>, "AKIAIOSFODNN7EXAMPLEwJalrXUtnFEMIK7MDENGbPxRfiCYEXAMPLEKEY", 57) = 57
4001  14:03:22.202000 chmod("/tmp/ztie/loot.txt", 0777) = 0
4001  14:03:22.203000 rename("/tmp/ztie/loot.txt", "/tmp/ztie/exfil.dat") = 0
4001  14:03:22.240000 socket(AF_INET, SOCK_STREAM, IPPROTO_TCP) = 6
4001  14:03:22.250000 connect(6, {sa_family=AF_INET, sin_port=htons(443), sin_addr=inet_addr("93.184.216.34")}, 16) = -1 ENETUNREACH (Network is unreachable)
4001  14:03:22.260000 +++ exited with 0 +++
"""


class TestPipelineStages(unittest.TestCase):
    def setUp(self):
        self.result = sz.sanitize_trace(_RAW_TRACE, token_budget=25000)
        self.events = self.result["events"]
        self.pipeline = self.result["pipeline"]
        self.summaries = " ".join(e["summary"] for e in self.events)

    def test_status_and_stage_order(self):
        self.assertEqual(self.pipeline["status"], sz.STATUS_SANITIZED)
        # Stages recorded IN ORDER: entropy scrub -> noise suppress -> truncate.
        self.assertEqual(
            self.pipeline["stages"],
            ["entropy_scrub", "noise_suppress", "truncate"],
        )

    def test_host_noise_suppressed(self):
        # The linker/locale/ssm opens + mem/signal syscalls are DROPPED.
        self.assertGreater(self.pipeline["noise_suppressed"], 0)
        self.assertNotIn("ld.so.cache", self.summaries)
        self.assertNotIn("libc.so.6", self.summaries)
        self.assertNotIn("locale-archive", self.summaries)
        self.assertNotIn("amazon/ssm", self.summaries)
        # Pure runtime-scaffolding syscalls are gone too.
        for noise_sc in ("brk", "arch_prctl", "mmap", "rt_sigprocmask"):
            self.assertNotIn(
                noise_sc, [e["syscall"] for e in self.events],
                f"{noise_sc} should have been suppressed as host noise",
            )

    def test_artifact_behavior_preserved(self):
        syscalls = [e["syscall"] for e in self.events]
        # The artifact's OWN salient ops survive noise suppression.
        self.assertIn("execve", syscalls)
        self.assertIn("openat", syscalls)   # the loot.txt create
        self.assertIn("write", syscalls)
        self.assertIn("chmod", syscalls)
        self.assertIn("rename", syscalls)
        self.assertIn("connect", syscalls)
        # The artifact's own paths + destination are legible.
        self.assertIn("/tmp/ztie/loot.txt", self.summaries)
        self.assertIn("/tmp/ztie/exfil.dat", self.summaries)
        self.assertIn("93.184.216.34", self.summaries)

    def test_high_entropy_blob_redacted_but_structure_kept(self):
        # The secret VALUE is gone; the write's STRUCTURE (which fd/path, the syscall)
        # is kept.
        self.assertGreater(self.pipeline["entropy_redactions"], 0)
        self.assertNotIn("AKIAIOSFODNN7EXAMPLE", self.summaries)
        self.assertNotIn("wJalrXUtnFEMIK7MDENGbPxRfiCYEXAMPLEKEY", self.summaries)
        self.assertIn("[REDACTED:", self.summaries)
        # The write event is still present and still points at the loot path.
        write_events = [e for e in self.events if e["syscall"] == "write"]
        self.assertTrue(write_events)
        self.assertTrue(any(w.get("redacted") for w in write_events))
        self.assertTrue(any("/tmp/ztie/loot.txt" in w["summary"] for w in write_events))

    def test_categories_correct(self):
        by_syscall = {e["syscall"]: e["category"] for e in self.events}
        self.assertEqual(by_syscall["execve"], sz.CATEGORY_PROCESS)
        self.assertEqual(by_syscall["openat"], sz.CATEGORY_FILE)
        self.assertEqual(by_syscall["write"], sz.CATEGORY_FILE)
        self.assertEqual(by_syscall["connect"], sz.CATEGORY_NETWORK)

    def test_relative_monotonic_offsets(self):
        # First KEPT event is the execve at t0 => offset 0; offsets are non-negative,
        # monotonic non-decreasing, and never a wall clock.
        offsets = [e["offset_ms"] for e in self.events]
        self.assertEqual(offsets[0], 0)
        self.assertEqual(offsets, sorted(offsets))
        for o in offsets:
            self.assertGreaterEqual(o, 0)
            self.assertLessEqual(o, 86400000)
        # The connect ~150ms after execve is a small relative delta, not a huge stamp.
        connect = next(e for e in self.events if e["syscall"] == "connect")
        self.assertEqual(connect["offset_ms"], 150)

    def test_no_verdict_field_anywhere(self):
        banned = {"verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean"}
        for e in self.events:
            for k in e:
                self.assertNotIn(k, banned)
        for k in self.pipeline:
            self.assertNotIn(k, banned)

    def test_accounting_consistent(self):
        p = self.pipeline
        # raw_events = kept + suppressed (every parsed line is kept or dropped).
        self.assertEqual(p["raw_events"], p["kept_events"] + p["noise_suppressed"])
        # emitted <= kept (truncation only drops the tail).
        self.assertLessEqual(p["emitted_events"], p["kept_events"])
        self.assertEqual(p["emitted_events"], len(self.events))


class TestTruncation(unittest.TestCase):
    def test_deterministic_truncation_sets_flag(self):
        # A tiny budget forces truncation; the flag is recorded, order is preserved.
        result = sz.sanitize_trace(_RAW_TRACE, token_budget=10)
        self.assertTrue(result["pipeline"]["truncated"])
        self.assertLessEqual(
            result["pipeline"]["estimated_tokens"], result["pipeline"]["token_budget"]
        )
        # Events kept are a PREFIX (trace order), never a random subset.
        full = sz.sanitize_trace(_RAW_TRACE, token_budget=25000)["events"]
        trunc = result["events"]
        self.assertEqual(
            [e["syscall"] for e in trunc],
            [e["syscall"] for e in full[: len(trunc)]],
        )

    def test_generous_budget_not_truncated(self):
        result = sz.sanitize_trace(_RAW_TRACE, token_budget=25000)
        self.assertFalse(result["pipeline"]["truncated"])

    def test_deterministic_repeatable(self):
        a = sz.sanitize_trace(_RAW_TRACE, token_budget=25000)
        b = sz.sanitize_trace(_RAW_TRACE, token_budget=25000)
        self.assertEqual(a, b)

    def test_event_cap_enforced(self):
        # A pathological trace of many artifact ops is bounded by MAX_EVENTS.
        big = "\n".join(
            f'1  00:00:{i % 60:02d}.000000 openat(AT_FDCWD, "/tmp/ztie/f{i}.txt", O_WRONLY|O_CREAT, 0644) = 3'
            for i in range(sz.MAX_EVENTS + 500)
        )
        result = sz.sanitize_trace(big, token_budget=sz.MAX_TOKEN_BUDGET)
        self.assertLessEqual(len(result["events"]), sz.MAX_EVENTS)
        self.assertTrue(result["pipeline"]["truncated"])


class TestEmptyAndDegenerate(unittest.TestCase):
    def test_none_trace_is_no_trace(self):
        result = sz.sanitize_trace(None)
        self.assertEqual(result["pipeline"]["status"], sz.STATUS_NO_TRACE)
        self.assertEqual(result["events"], [])
        self.assertFalse(result["pipeline"]["truncated"])
        self.assertEqual(result["pipeline"]["raw_events"], 0)

    def test_empty_trace_is_no_trace(self):
        result = sz.sanitize_trace("   \n  \n")
        self.assertEqual(result["pipeline"]["status"], sz.STATUS_NO_TRACE)
        self.assertEqual(result["events"], [])

    def test_all_noise_yields_kept_zero(self):
        noise = """
1  00:00:00.100000 openat(AT_FDCWD, "/lib/x86_64-linux-gnu/libm.so.6", O_RDONLY) = 3
1  00:00:00.101000 brk(NULL) = 0x1
1  00:00:00.102000 mmap(NULL, 4096, PROT_READ, MAP_PRIVATE, -1, 0) = 0x2
"""
        result = sz.sanitize_trace(noise)
        self.assertEqual(result["pipeline"]["status"], sz.STATUS_SANITIZED)
        self.assertEqual(result["pipeline"]["kept_events"], 0)
        self.assertEqual(result["events"], [])

    def test_low_entropy_long_path_not_redacted(self):
        # A long but LOW-entropy path component (repeated chars) is kept intact —
        # the scrub targets secrets, not structure.
        trace = '1  00:00:00.1 openat(AT_FDCWD, "/tmp/ztie/aaaaaaaaaaaaaaaaaaaaaaaaaaaa.txt", O_RDONLY) = 3'
        result = sz.sanitize_trace(trace)
        self.assertEqual(result["pipeline"]["entropy_redactions"], 0)
        self.assertIn("aaaaaaaaaaaa", result["events"][0]["summary"])


class TestEntropyGate(unittest.TestCase):
    def test_shannon_entropy_high_for_random(self):
        self.assertGreater(sz._shannon_entropy("AKIAIOSFODNN7EXAMPLE9xQz"), sz._MIN_ENTROPY_BITS)

    def test_shannon_entropy_low_for_repeated(self):
        self.assertLess(sz._shannon_entropy("aaaaaaaaaaaaaaaaaaaaaaaa"), sz._MIN_ENTROPY_BITS)


if __name__ == "__main__":
    unittest.main()
