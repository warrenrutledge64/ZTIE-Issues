"""Contract-conformance test: the router's output, wrapped in the envelope, must
validate against ``routing.contract.v1.json``.

``jsonschema`` is not in the INTEGRATIONS_ONLY build sandbox (PyPI blocked), so
this test SKIPS offline and RUNS live (under pytest, where jsonschema is
installed). It closes the loop between the schema-first routing contract and the
router code: whatever the pure router emits must satisfy the allow-list schema the
Hub validator enforces.
"""

from __future__ import annotations

import json
import os
import unittest

from router import IAC_TEMPLATE, OTHER_UNKNOWN, RAW_SCRIPT, route

try:
    from jsonschema import Draft7Validator

    _HAVE_JSONSCHEMA = True
except ImportError:  # offline sandbox
    _HAVE_JSONSCHEMA = False

# The router's canonical schema lives in schemas/; the bundled copy lives with the
# Hub validator. Point at the canonical repo copy for the conformance check.
_SCHEMA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "schemas", "routing.contract.v1.json"
)

_VALID_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_VALID_SHA256 = "a" * 64


def _envelope(routing: dict) -> dict:
    return {
        "contract_version": "1.0",
        "intake_id": _VALID_INTAKE_ID,
        "sha256": _VALID_SHA256,
        "routed_at": "2026-08-25T12:00:00Z",
        "routing": routing,
    }


@unittest.skipUnless(_HAVE_JSONSCHEMA, "jsonschema not available offline")
class TestRoutingContractConformance(unittest.TestCase):
    def setUp(self):
        with open(_SCHEMA_PATH, encoding="utf-8") as fh:
            self.validator = Draft7Validator(json.load(fh))

    def _assert_conforms(self, artifact_class):
        envelope = _envelope(route(artifact_class))
        errors = sorted(self.validator.iter_errors(envelope), key=str)
        self.assertEqual(errors, [], f"schema errors for {artifact_class}: {errors}")

    def test_iac_route_conforms(self):
        self._assert_conforms(IAC_TEMPLATE)

    def test_raw_script_route_conforms(self):
        self._assert_conforms(RAW_SCRIPT)

    def test_other_unknown_route_conforms(self):
        self._assert_conforms(OTHER_UNKNOWN)

    def test_unrecognised_class_route_conforms(self):
        # The fail-safe fallback (normalised to other_unknown) must still be a
        # schema-valid envelope.
        self._assert_conforms("something_totally_unexpected")


if __name__ == "__main__":
    unittest.main()
