"""ZTIE Story 3.1 — unit tests for the PURE normalization logic (combine.py).

Stdlib-only; runs offline in the INTEGRATIONS_ONLY sandbox. Proves the load-bearing
behaviors: honest presence recording, evidence-never-verdict, relative-clock
carry-through, deterministic event cap, and integrity keying.
"""

from __future__ import annotations

import unittest

import combine

_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_SHA256 = "b" * 64


class TestPresenceHonesty(unittest.TestCase):
    def test_absent_inputs_recorded_not_fabricated(self):
        env = combine.combine(
            item={"intake_id": _INTAKE_ID, "sha256": _SHA256},
            combined_at="2026-09-11T00:00:00Z",
            contract_version="1.0",
        )
        ce = env["combined_event"]
        self.assertEqual(ce["inputs_present"], [])
        self.assertFalse(ce["complete"])
        for name in ("static", "dynamic", "sanitized"):
            self.assertEqual(ce["sources"][name]["presence"], "absent")
        # An absent signal is OMITTED, never fabricated.
        self.assertNotIn("static_highest_severity", ce["signals"])
        self.assertNotIn("dynamic_outcome", ce["signals"])
        self.assertEqual(ce["signals"]["behavioral_events"], [])
        self.assertEqual(ce["signals"]["behavioral_event_count"], 0)

    def test_partial_present_only_static(self):
        env = combine.combine(
            item={
                "intake_id": _INTAKE_ID,
                "sha256": _SHA256,
                "static_scan": {"highest_severity": "medium", "total_findings": 2},
            },
            combined_at="2026-09-11T00:00:00Z",
            contract_version="1.0",
        )
        ce = env["combined_event"]
        self.assertEqual(ce["inputs_present"], ["static"])
        self.assertFalse(ce["complete"])
        self.assertEqual(ce["sources"]["static"]["presence"], "present")
        self.assertEqual(ce["sources"]["static"]["highest_severity"], "medium")
        self.assertEqual(ce["sources"]["static"]["total_findings"], 2)
        self.assertEqual(ce["signals"]["static_highest_severity"], "medium")
        self.assertNotIn("dynamic_outcome", ce["signals"])

    def test_all_three_present_is_complete(self):
        env = combine.combine(
            item={
                "intake_id": _INTAKE_ID,
                "sha256": _SHA256,
                "static_scan": {"highest_severity": "none", "total_findings": 0},
                "dynamic_run": {"outcome": "completed"},
                "sanitized": {"pipeline": {"status": "sanitized", "truncated": False}},
            },
            combined_at="2026-09-11T00:00:00Z",
            contract_version="1.0",
        )
        ce = env["combined_event"]
        self.assertEqual(set(ce["inputs_present"]), {"static", "dynamic", "sanitized"})
        self.assertTrue(ce["complete"])


class TestIntegrityKeying(unittest.TestCase):
    def test_envelope_bound_to_item_identity(self):
        env = combine.combine(
            item={"intake_id": _INTAKE_ID, "sha256": _SHA256},
            combined_at="2026-09-11T00:00:00Z",
            contract_version="1.0",
        )
        self.assertEqual(env["intake_id"], _INTAKE_ID)
        self.assertEqual(env["sha256"], _SHA256)
        self.assertEqual(env["contract_version"], "1.0")
        self.assertEqual(env["combined_at"], "2026-09-11T00:00:00Z")


class TestBehavioralEventCarryThrough(unittest.TestCase):
    def _sanitized_with_events(self, events):
        return {
            "intake_id": _INTAKE_ID,
            "sha256": _SHA256,
            "sanitized": {
                "pipeline": {"status": "sanitized", "truncated": False},
                "events": events,
            },
        }

    def test_events_reshaped_and_relative_clock_preserved(self):
        env = combine.combine(
            item=self._sanitized_with_events(
                [
                    {
                        "offset_ms": 5,
                        "category": "file",
                        "syscall": "openat",
                        "summary": "openat(/etc/passwd)",
                        "redacted": False,
                    }
                ]
            ),
            combined_at="2026-09-11T00:00:00Z",
            contract_version="1.0",
        )
        ev = env["combined_event"]["signals"]["behavioral_events"][0]
        # Relative offset carried through unchanged (no wall clock).
        self.assertEqual(ev["offset_ms"], 5)
        self.assertEqual(ev["category"], "file")
        self.assertEqual(ev["syscall"], "openat")
        self.assertEqual(ev["summary"], "openat(/etc/passwd)")
        self.assertEqual(ev["redacted"], False)

    def test_malformed_events_dropped_not_fabricated(self):
        env = combine.combine(
            item=self._sanitized_with_events(
                [
                    {"category": "file", "syscall": "openat", "summary": "x"},  # no offset
                    {"offset_ms": 1, "category": "bogus", "syscall": "x", "summary": "y"},
                    {"offset_ms": 2, "category": "file", "syscall": "read", "summary": "read()"},
                ]
            ),
            combined_at="2026-09-11T00:00:00Z",
            contract_version="1.0",
        )
        events = env["combined_event"]["signals"]["behavioral_events"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["syscall"], "read")

    def test_events_capped_deterministically_in_trace_order(self):
        many = [
            {"offset_ms": i, "category": "other", "syscall": "s", "summary": "m"}
            for i in range(combine._MAX_EVENTS + 50)
        ]
        env = combine.combine(
            item=self._sanitized_with_events(many),
            combined_at="2026-09-11T00:00:00Z",
            contract_version="1.0",
        )
        events = env["combined_event"]["signals"]["behavioral_events"]
        self.assertEqual(len(events), combine._MAX_EVENTS)
        # trace order preserved (drop the tail, not a random subset)
        self.assertEqual(events[0]["offset_ms"], 0)
        self.assertEqual(events[-1]["offset_ms"], combine._MAX_EVENTS - 1)

    def test_oversized_strings_clipped(self):
        env = combine.combine(
            item=self._sanitized_with_events(
                [
                    {
                        "offset_ms": 1,
                        "category": "network",
                        "syscall": "c" * 500,
                        "summary": "s" * 900,
                    }
                ]
            ),
            combined_at="2026-09-11T00:00:00Z",
            contract_version="1.0",
        )
        ev = env["combined_event"]["signals"]["behavioral_events"][0]
        self.assertLessEqual(len(ev["syscall"]), combine._MAX_SYSCALL)
        self.assertLessEqual(len(ev["summary"]), combine._MAX_SUMMARY)


class TestEvidenceNeverVerdict(unittest.TestCase):
    def test_dynamic_outcome_is_evidence_not_verdict(self):
        env = combine.combine(
            item={
                "intake_id": _INTAKE_ID,
                "sha256": _SHA256,
                "dynamic_run": {"outcome": "execution_error"},
            },
            combined_at="2026-09-11T00:00:00Z",
            contract_version="1.0",
        )
        ce = env["combined_event"]
        # An error outcome is EVIDENCE; it does not become a verdict/complete flag.
        self.assertEqual(ce["signals"]["dynamic_outcome"], "execution_error")
        self.assertFalse(ce["complete"])  # only dynamic present

    def test_bad_enum_values_dropped_not_carried(self):
        env = combine.combine(
            item={
                "intake_id": _INTAKE_ID,
                "sha256": _SHA256,
                "static_scan": {"highest_severity": "catastrophic"},  # not in enum
                "dynamic_run": {"outcome": "exploded"},  # not in enum
            },
            combined_at="2026-09-11T00:00:00Z",
            contract_version="1.0",
        )
        ce = env["combined_event"]
        # Inputs are present, but out-of-enum values are NOT carried through.
        self.assertEqual(ce["sources"]["static"]["presence"], "present")
        self.assertNotIn("highest_severity", ce["sources"]["static"])
        self.assertNotIn("static_highest_severity", ce["signals"])
        self.assertNotIn("outcome", ce["sources"]["dynamic"])


class TestSanitizedRollup(unittest.TestCase):
    def test_pipeline_and_pointer_rolled_up(self):
        env = combine.combine(
            item={
                "intake_id": _INTAKE_ID,
                "sha256": _SHA256,
                "sanitized": {
                    "contract_version": "1.0",
                    "source": {
                        "trace_s3_bucket": "ztie-forensic-artifacts",
                        "trace_s3_key": f"traces/{_INTAKE_ID}/behavior-trace.txt",
                    },
                    "pipeline": {
                        "status": "no_trace",
                        "truncated": False,
                        "estimated_tokens": 0,
                    },
                },
            },
            combined_at="2026-09-11T00:00:00Z",
            contract_version="1.0",
        )
        src = env["combined_event"]["sources"]["sanitized"]
        self.assertEqual(src["presence"], "present")
        self.assertEqual(src["capture_status"], "no_trace")
        self.assertEqual(src["truncated"], False)
        self.assertEqual(src["estimated_tokens"], 0)
        self.assertEqual(src["trace_s3_bucket"], "ztie-forensic-artifacts")
        self.assertEqual(src["sanitized_contract_version"], "1.0")


if __name__ == "__main__":
    unittest.main()
