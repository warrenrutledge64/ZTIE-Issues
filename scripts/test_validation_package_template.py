"""ZTIE OD-005 — secret-safe guard for the validation-package template.

WHY THIS EXISTS. OD-005 tracked validation-tooling UX friction (the VUX sub-lane in the
RUNBOOK Operational Debt Register). Its one settled finding, VUX-001, was that the
GitHub-token fetch step in ``docs/GEMINI_VALIDATION_PACKAGE_TEMPLATE.md`` used a silent
``read -rs`` that *looks like it hangs*, and the tempting "fix" — typing
``export GH_TOKEN=ghp_…`` on the command line — is a SECRET-LEAK regression (the token
echoes to the screen + into shell history; ties to the standing "a PAT echoed into
CloudShell output must be rotated" lesson). VUX-001 was fixed in the template on
2026-09-16 (a silent-prompt ``read -rsp`` + a ``token length`` confirm + ``unset``).

This test is the DURABLE, REPEATABLE guard (RD-015) that closes OD-005: it fails if the
template ever REINTRODUCES a secret-leaking token form or drops the safe handling — so the
whole class the VUX collection was created to catch can never silently come back. It is
offline + stdlib-only (no live component), like the OD-007 harness.

Scope note: the template legitimately MENTIONS the leaky form in a NEGATIVE example / prose
warning ("do NOT type ``export GH_TOKEN=ghp_…``"). The leaky-form assertion below targets a
real *command-line assignment* of the token to an env var, NOT a fenced/backticked teaching
reference, so the guard does not flag the very line that warns against it.
"""

from __future__ import annotations

import pathlib
import re
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = REPO_ROOT / "docs" / "GEMINI_VALIDATION_PACKAGE_TEMPLATE.md"

# The secret-safe token read: a SILENT prompt (-s), non-echoing, that shows a visible
# instruction and does not print the token. This is the VUX-001 fix form.
_SAFE_READ_RE = re.compile(r"read -rsp \"Paste GH token[^\"]*\" GH_TOKEN")

# A leaky COMMAND-LINE assignment of the token to GH_TOKEN with a literal/paste value
# (echoes the secret to the screen + shell history). We match an ``export GH_TOKEN=``
# (or a bare ``GH_TOKEN=``) assignment whose right-hand side is a literal token / paste
# placeholder — NOT a ``read``-populated variable, and NOT a backticked prose reference.
# Deliberately EXCLUDES the safe ``export GH_TOKEN`` with NO ``=`` (the ``read … && export
# GH_TOKEN`` form) and the ``${#GH_TOKEN}`` length print.
_LEAKY_ASSIGN_RE = re.compile(
    r"(?m)^\s*(?:export\s+)?GH_TOKEN=\s*[\"']?(?:ghp_|<|\$\{?PAT|pat\b|[A-Za-z0-9]{8})"
)


def _strip_inline_code(text: str) -> str:
    """Remove backtick-fenced inline spans so a leaky form quoted as a NEGATIVE example
    in prose (``do NOT type `export GH_TOKEN=ghp_…```) is not mistaken for a real command."""
    return re.sub(r"`[^`]*`", "", text)


class TestValidationPackageTemplateTokenSafety(unittest.TestCase):
    def setUp(self):
        self.assertTrue(TEMPLATE.is_file(), f"template missing: {TEMPLATE}")
        self.text = TEMPLATE.read_text(encoding="utf-8")

    def test_uses_the_silent_prompt_read_form(self):
        # The VUX-001 fix: the token is read via a silent, non-echoing prompt. There must
        # be at least one such form (the template has several token-fetch spots).
        self.assertRegex(
            self.text,
            _SAFE_READ_RE,
            "the GH token fetch must use the silent-prompt `read -rsp \"Paste GH token…\" "
            "GH_TOKEN` form (VUX-001 fix); a plain `export GH_TOKEN=…` leaks the secret",
        )

    def test_no_leaky_command_line_token_assignment(self):
        # The regression guard: no ACTUAL command-line assignment of a literal/paste token
        # to GH_TOKEN. Prose negative-examples inside backticks are stripped first so the
        # "do NOT type `export GH_TOKEN=ghp_…`" teaching line is not flagged.
        code_only = _strip_inline_code(self.text)
        m = _LEAKY_ASSIGN_RE.search(code_only)
        self.assertIsNone(
            m,
            "a leaky command-line `GH_TOKEN=<value>` assignment reappeared in the template "
            f"(secret-leak regression, VUX-001): {m.group(0)!r}" if m else "",
        )

    def test_every_token_read_is_paired_with_unset(self):
        # Hygiene: the token is cleared after use. There must be at least as many `unset
        # GH_TOKEN` as silent-prompt reads, so no fetch block leaves the token in the env.
        reads = len(_SAFE_READ_RE.findall(self.text))
        unsets = self.text.count("unset GH_TOKEN")
        self.assertGreaterEqual(
            unsets,
            reads,
            f"each token read must be paired with an `unset GH_TOKEN` (reads={reads}, "
            f"unsets={unsets})",
        )

    def test_has_the_looks_like_it_hangs_clarity_note(self):
        # VUX-001's other half: the silent prompt LOOKS like it hangs, so the template must
        # tell the operator it is silently waiting (clarity at the point of use).
        low = self.text.lower()
        self.assertTrue(
            ("looks like it hangs" in low)
            or ("silently waiting" in low)
            or ("nothing will show" in low),
            "the template must carry the 'this looks like it hangs — it is silently "
            "waiting' clarity note next to the silent token prompt (VUX-001)",
        )

    def test_guard_would_catch_a_reintroduced_leak(self):
        # Prove the guard has TEETH: inject the leaky form into a COPY and confirm the
        # leaky-assignment regex fires (so a real regression cannot pass silently).
        injected = self.text + "\n\nexport GH_TOKEN=ghp_examplepastedsecrettoken\n"
        self.assertRegex(_strip_inline_code(injected), _LEAKY_ASSIGN_RE)


if __name__ == "__main__":
    unittest.main()
