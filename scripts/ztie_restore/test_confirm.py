"""Unit tests for the confirm gate + restore abort path (Story 1.R).

Proves the two branches without a real terminal (the hard-won lesson: never try to
drive a real pty in tests):

- CONFIRMED-YES path: inject an ``input_fn`` that returns "y" and assert True.
- FAIL-SAFE-NO path: empty / negative / EOF / ``ZTIE_ASSUME_NO=1`` all return
  False, and the restore raises ``RestoreAborted`` making no changes.
"""

from __future__ import annotations

import contextlib
import io
import os
import unittest

from ztie_restore.confirm import confirm


class TestConfirm(unittest.TestCase):
    def test_affirmative_replies_confirm(self):
        for reply in ("y", "Y", "yes", "YES", " yes ", "y\r", "  y\r\n".strip("\n")):
            self.assertTrue(confirm("go?", input_fn=lambda _p, r=reply: r), reply)

    def test_negative_and_empty_fail_safe_no(self):
        for reply in ("", "n", "no", "nope", "maybe", "yy", "1", "   "):
            self.assertFalse(confirm("go?", input_fn=lambda _p, r=reply: r), reply)

    def test_eof_fails_safe_no(self):
        def raise_eof(_prompt):
            raise EOFError

        self.assertFalse(confirm("go?", input_fn=raise_eof))

    def test_assume_no_env_forces_no(self):
        os.environ["ZTIE_ASSUME_NO"] = "1"
        try:
            # Even an affirmative reply is overridden to NO.
            self.assertFalse(confirm("go?", input_fn=lambda _p: "yes"))
        finally:
            del os.environ["ZTIE_ASSUME_NO"]

    def test_assume_yes_confirms_without_prompt(self):
        # --yes proceeds without ever reading stdin. input_fn must NOT be called.
        def fail_if_called(_prompt):
            raise AssertionError("input_fn should not be called when assume_yes=True")

        self.assertTrue(confirm("go?", input_fn=fail_if_called, assume_yes=True))

    def test_assume_no_brake_beats_assume_yes(self):
        # The hard NO brake wins even over --yes.
        os.environ["ZTIE_ASSUME_NO"] = "1"
        try:
            self.assertFalse(confirm("go?", assume_yes=True))
        finally:
            del os.environ["ZTIE_ASSUME_NO"]


class TestRestoreAbort(unittest.TestCase):
    def test_declined_restore_makes_no_changes(self):
        from ztie_restore.restore import RestoreAborted, restore_account
        from ztie_restore.targets import HUB

        manifest = {
            "region": "us-east-1",
            "captured_at_utc": "2026-08-25T00:00:00Z",
            "governance_commit": {"sha": "deadbeef"},
            "resources": [],
        }

        # Stub caller_identity so no AWS call happens; force the confirm to NO.
        import ztie_restore.restore as restore_mod

        original = restore_mod.awsio.caller_identity
        restore_mod.awsio.caller_identity = lambda region: {
            "account": HUB.account_id,
            "arn": "arn:aws:iam::641628980935:user/test",
        }
        try:
            # The restore prints a plan banner to stdout; capture it so the test
            # output stays clean.
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(
                RestoreAborted
            ):
                restore_account(
                    manifest,
                    HUB,
                    confirm_fn=lambda _prompt, **_kw: False,
                    verify_after=False,
                )
        finally:
            restore_mod.awsio.caller_identity = original


if __name__ == "__main__":
    unittest.main()
