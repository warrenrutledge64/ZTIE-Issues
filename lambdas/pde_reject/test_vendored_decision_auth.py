"""ZTIE Story 4.7 — no-drift check for the vendored decision-auth library.

Each Lambda dir bundles as its OWN CDK asset, so the Forensic destroyer cannot import
``lib/decision_auth`` at runtime — it VENDORS byte-identical copies of ``canonical.py``,
``verify.py``, ``signature.py`` (the proven hub_report status_model / pde_handoff
vendoring discipline). This test asserts each vendored copy is sha256-identical to the
canonical ``lib/decision_auth`` source; if the library ever changes, re-copy it or this
fails.
"""

from __future__ import annotations

import hashlib
import os
import unittest

_HERE = os.path.dirname(__file__)
_CANONICAL_DIR = os.path.abspath(
    os.path.join(_HERE, "..", "..", "lib", "decision_auth")
)

_VENDORED = ["canonical.py", "verify.py", "signature.py", "decision.token.v1.json"]


def _sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


class TestVendoredDecisionAuthNoDrift(unittest.TestCase):
    def test_each_vendored_file_matches_canonical(self):
        for name in _VENDORED:
            vendored = os.path.join(_HERE, name)
            canonical = os.path.join(_CANONICAL_DIR, name)
            self.assertTrue(os.path.exists(vendored), f"missing vendored {name}")
            self.assertTrue(os.path.exists(canonical), f"missing canonical {name}")
            self.assertEqual(
                _sha256(vendored),
                _sha256(canonical),
                f"vendored {name} drifted from lib/decision_auth/{name}; re-copy it",
            )


if __name__ == "__main__":
    unittest.main()
