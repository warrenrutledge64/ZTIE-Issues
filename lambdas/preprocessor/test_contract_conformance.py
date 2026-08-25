"""Contract-conformance test: the classifier's output, wrapped in the envelope,
must validate against ``classification.contract.v1.json``.

``jsonschema`` is not in the INTEGRATIONS_ONLY build sandbox (PyPI blocked), so
this test SKIPS offline and RUNS live (under pytest, where jsonschema is
installed). It closes the loop between the schema-first contract and the code:
whatever the pure classifier emits must satisfy the allow-list schema the Hub
validator enforces.
"""

from __future__ import annotations

import json
import os
import unittest

from classifier import classify

try:
    from jsonschema import Draft7Validator

    _HAVE_JSONSCHEMA = True
except ImportError:  # offline sandbox
    _HAVE_JSONSCHEMA = False

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "classification.contract.v1.json")

_VALID_INTAKE_ID = "62360e03-dfb1-4655-ac52-2a55345ab6f0"
_VALID_SHA256 = "a" * 64

_CFN_YAML = b"AWSTemplateFormatVersion: '2010-09-09'\nResources:\n  B:\n    Type: AWS::S3::Bucket\n"
_BASH = b"#!/usr/bin/env bash\necho hi\n"
_TEXT = b"just notes\n"


def _envelope(classification: dict) -> dict:
    return {
        "contract_version": "1.0",
        "intake_id": _VALID_INTAKE_ID,
        "sha256": _VALID_SHA256,
        "classified_at": "2026-08-25T12:00:00Z",
        "classification": classification,
    }


@unittest.skipUnless(_HAVE_JSONSCHEMA, "jsonschema not available offline")
class TestContractConformance(unittest.TestCase):
    def setUp(self):
        with open(_SCHEMA_PATH, encoding="utf-8") as fh:
            self.validator = Draft7Validator(json.load(fh))

    def _assert_conforms(self, filename, body):
        envelope = _envelope(classify(filename, body))
        errors = sorted(self.validator.iter_errors(envelope), key=str)
        self.assertEqual(errors, [], f"schema errors for {filename}: {errors}")

    def test_iac_envelope_conforms(self):
        self._assert_conforms("stack.yaml", _CFN_YAML)

    def test_script_envelope_conforms(self):
        self._assert_conforms("deploy.sh", _BASH)

    def test_mismatch_envelope_conforms(self):
        # script content under a .yaml name — the distrust-the-claim result must
        # still be a schema-valid envelope.
        self._assert_conforms("innocent.yaml", _BASH)

    def test_other_unknown_envelope_conforms(self):
        self._assert_conforms("readme", _TEXT)


if __name__ == "__main__":
    unittest.main()
