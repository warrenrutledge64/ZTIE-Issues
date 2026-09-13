"""Offline proof for the ZTIE Story 4.3 (RD-043) dashboard RENDER assets.

The render is a build-step-free vanilla HTML/CSS/JS SPA, so there is no npm test
runner in the offline build sandbox. These stdlib-only checks assert the render's
DESIGN INVARIANTS directly over the shipped static files, so they are enforceable on
the offline proof bar (``python3 -m unittest``) exactly like every Lambda's tests:

  * ADVISORY, NEVER ACTED UPON (RD-040): the render surfaces the 3.5
    ``recommended_verdict`` + an explicit advisory framing, and the APPROVE/REJECT
    control is a SURFACE only (the buttons are disabled — the action is Story 4.4). It
    NEVER renders a bare EFFECTIVE-verdict key.
  * NO STORED XSS (RD-013): the client inserts derived values via ``textContent`` /
    explicit escaping, NEVER via ``innerHTML`` of a raw payload value.
  * RENDER ONLY: the client makes NO write call (only GET) and consumes ONLY the 4.2
    ``dashboard.contract.v1`` payload.
  * TENANT-AWARE (RD-028): reads carry the configured ``subscriber_id``.
  * DARK THEME + GRADUATED THREAT SCALE: the CSS defines the dark base + the five-band
    (unknown/low/medium/high/critical) graduated color scale.

These are lints over the shipped source, not a DOM test; they guard the invariants that
matter and would otherwise only be caught in a browser.
"""

from __future__ import annotations

import os
import re
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))


def _read(name: str) -> str:
    with open(os.path.join(_HERE, name), encoding="utf-8") as fh:
        return fh.read()


class TestAdvisoryNeverActed(unittest.TestCase):
    """RD-040: the recommendation is advisory + human-gated; the control is a surface."""

    def setUp(self) -> None:
        self.app = _read("app.js")
        self.html = _read("index.html")

    def test_no_bare_effective_verdict_key_rendered(self) -> None:
        # The render must never surface a BARE effective-verdict key. `recommended_verdict`
        # is the allow-listed ADVISORY field (deliberately not a bare `verdict`). Assert no
        # bare banned key is read off the payload. We scan for property accesses / string
        # keys of the banned set, allowing `recommended_verdict` (which contains "verdict"
        # only as a suffix of the allowed name).
        banned = ["safe", "approved", "forward", "malicious", "pass_fail", "clean"]
        for key in banned:
            # A CODE property access `.<key>` (word-boundary) or a bracket string-key
            # `["<key>"]` off the payload. (Prose/labels are not property reads and are
            # intentionally allowed — the invariant is about what the render READS off the
            # payload, not English words in captions.)
            esc = re.escape(key)
            self.assertNotRegex(
                self.app,
                rf"\.{esc}\b",
                f"render reads a bare banned effective-verdict property .{key}",
            )
            self.assertNotRegex(
                self.app,
                rf"""\[\s*["']{esc}["']\s*\]""",
                f"render reads a bare banned effective-verdict key ['{key}']",
            )
        # A bare `.verdict` PROPERTY (not `.recommended_verdict`) must never be read; and
        # no bracket key `["verdict"]`. English words in captions ("never a verdict") are
        # fine — this checks property/key access only.
        self.assertNotRegex(
            self.app,
            r"(?<!recommended_)\.verdict\b",
            "render must read `recommended_verdict` (advisory), never a bare `.verdict`",
        )
        self.assertNotRegex(
            self.app,
            r"""\[\s*["']verdict["']\s*\]""",
            "render must not read a bare `['verdict']` key",
        )

    def test_advisory_framing_present(self) -> None:
        # The advisory banner + the per-intake note must state the recommendation is
        # advisory and never acted upon automatically.
        self.assertIn("advisory", self.html.lower())
        self.assertIn("advisory only", self.app.lower())
        self.assertRegex(self.app.lower(), r"never acted upon")

    def test_approve_reject_control_is_surface_only(self) -> None:
        # The APPROVE/REJECT buttons must be present (the control surface) but DISABLED
        # (the action is Story 4.4/4.7, not 4.3).
        self.assertIn("btn-approve", self.app)
        self.assertIn("btn-reject", self.app)
        self.assertRegex(
            self.app,
            r"approve\.setAttribute\(\s*[\"']disabled[\"']",
            "the approve control must be a disabled surface (the action is Story 4.4)",
        )
        self.assertRegex(
            self.app,
            r"reject\.setAttribute\(\s*[\"']disabled[\"']",
            "the reject control must be a disabled surface (the action is Story 4.7)",
        )

    def test_decision_rendered_as_pending(self) -> None:
        self.assertIn("pending", self.app)


class TestNoStoredXss(unittest.TestCase):
    """RD-013: the render escapes derived data — no innerHTML of raw values."""

    def test_no_innerhtml_assignment(self) -> None:
        app = _read("app.js")
        # `.innerHTML =` (or `.outerHTML =`) is banned: all text goes through textContent
        # / createTextNode / the safe `el()` helper.
        self.assertNotRegex(
            app,
            r"\.(inner|outer)HTML\s*=",
            "render must not assign innerHTML/outerHTML (use textContent — no stored XSS)",
        )

    def test_safe_dom_helpers_used(self) -> None:
        app = _read("app.js")
        self.assertIn("textContent", app)
        self.assertIn("createTextNode", app)


class TestRenderOnly(unittest.TestCase):
    """4.3 is RENDER ONLY: GET reads of the 4.2 payload, no writes, no model call."""

    def setUp(self) -> None:
        self.app = _read("app.js")

    def test_only_get_reads(self) -> None:
        # The only fetch method used is GET.
        methods = re.findall(r'method:\s*["\'](\w+)["\']', self.app)
        self.assertTrue(methods, "expected at least one fetch with an explicit method")
        for m in methods:
            self.assertEqual(m, "GET", f"render must only GET; found method {m}")
        # No write verbs anywhere in the client.
        for verb in ("POST", "PUT", "DELETE", "PATCH"):
            self.assertNotRegex(
                self.app,
                rf'method:\s*["\']{verb}["\']',
                f"render must not issue a {verb}",
            )

    def test_reads_both_views_of_the_42_payload(self) -> None:
        # GET /dashboard (fleet) + GET /status/{intake_id} (per-intake) — the two 4.2
        # views. Both are built via apiUrl(...) (line wrapping by the formatter tolerated).
        self.assertRegex(self.app, r'apiUrl\(\s*"dashboard')
        self.assertRegex(self.app, r'apiUrl\(\s*\n?\s*"status/')

    def test_not_wired_health_rendered_as_not_available(self) -> None:
        # The stubbed operational-health blocks arrive `not_wired`; render as
        # "not available yet", not as an error.
        self.assertIn("not_wired", self.app)
        self.assertIn("not available yet", self.app)


class TestTenantAware(unittest.TestCase):
    """RD-028: per-subscriber, org-shared — reads carry the subscriber id."""

    def test_subscriber_id_on_reads(self) -> None:
        app = _read("app.js")
        self.assertIn("subscriber_id=", app)
        self.assertIn("subscriberId", app)


class TestDarkThemeGraduatedScale(unittest.TestCase):
    """Dark background + a graduated threat/severity color scale (stakeholder req)."""

    def setUp(self) -> None:
        self.css = _read("styles.css")

    def test_dark_base(self) -> None:
        # A dark background base color variable.
        self.assertRegex(self.css, r"--bg:\s*#0", "dashboard must use a dark background")

    def test_graduated_tier_scale_all_five_bands(self) -> None:
        for band in ("unknown", "low", "medium", "high", "critical"):
            self.assertIn(
                f"--tier-{band}:",
                self.css,
                f"missing graduated color for threat tier '{band}'",
            )
            self.assertIn(
                f"tier-{band}",
                self.css,
                f"missing tier pill class for '{band}'",
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
