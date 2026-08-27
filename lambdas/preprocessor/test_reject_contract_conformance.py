"""Contract-conformance test: the rejector's output, wrapped in the envelope, must
validate against ``reject.contract.v1.json``.

``jsonschema`` is not in the INTEGRATIONS_ONLY build sandbox (PyPI blocked), so
this test SKIPS offline and RUNS live (under pytest, where jsonschema is installed).
"""

from __future__ import annotations

import json
import os
import unittest

from rejector import reject

try:
    from jsonschema import Draft7Validator

    _HAVE_JSONSCHEMA = True
except ImportError:
    _HAVE_JSONSCHEMA = False

_SCHEMA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "schemas", "reject.contract.v1.json"
)

_VALID_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_VALID_SHA256 = "a" * 64


def _envelope(rejection: dict) -> dict:
    return {
        "contract_version": "1.0",
        "intake_id": _VALID_INTAKE_ID,
        "sha256": _VALID_SHA256,
        "rejected_at": "2026-08-27T12:00:00Z",
        "rejection": rejection,
    }


def _unroutable(notes: str | None = None) -> dict:
    d: dict = {
        "artifact_class": "other_unknown",
        "lanes": ["safe_reject"],
        "routable": False,
        "basis": "safe_reject_fallback",
    }
    if notes:
        d["notes"] = notes
    return d


@unittest.skipUnless(_HAVE_JSONSCHEMA, "jsonschema not available offline")
class TestRejectContractConformance(unittest.TestCase):
    def setUp(self):
        with open(_SCHEMA_PATH, encoding="utf-8") as fh:
            self.validator = Draft7Validator(json.load(fh))

    def _assert_conforms(self, routing_decision):
        rejection = reject(routing_decision)
        self.assertIsNotNone(rejection)
        envelope = _envelope(rejection)
        errors = sorted(self.validator.iter_errors(envelope), key=str)
        self.assertEqual(errors, [], f"schema errors: {errors}")

    def test_other_unknown_conforms(self):
        self._assert_conforms(_unroutable())

    def test_with_notes_conforms(self):
        self._assert_conforms(_unroutable(notes="unrecognised class"))

    def test_missing_class_fallback_conforms(self):
        self._assert_conforms({"routable": False})


if __name__ == "__main__":
    unittest.main()
