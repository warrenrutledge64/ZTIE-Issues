"""ZTIE Story 2.6 — offline conformance for the collected-record (join) contract.

Pure-stdlib (no jsonschema / moto / boto3), so the loop between the schema-first
contract and the code is closed OFFLINE in the INTEGRATIONS_ONLY sandbox where
PyPI is blocked. It asserts the load-bearing RD-013 / RD-016 / RD-014 invariants
of schemas/collected.contract.v1.json directly:

  * additionalProperties:false at EVERY object level (recursive walk),
  * NO verdict-family property (verdict/safe/approved/forward/pass_fail/malicious/
    clean) anywhere in the schema (recursive scan),
  * the canonical schema file byte-matches the two bundled copies (hash-match),
  * the top-level allow-list + own version pin + unique 'collected' discriminator.

Model: lambdas/detonation/test_contract_conformance.py and
lambdas/preprocessor/test_contract_conformance.py (the existing conformance style).
"""

from __future__ import annotations

import json
import os
import unittest

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SCHEMA_PATH = os.path.join(_REPO, "schemas", "collected.contract.v1.json")
_BUNDLED_PATHS = [
    os.path.join(_REPO, "lambdas", "hub_ingest", "collected.contract.v1.json"),
    os.path.join(_REPO, "lambdas", "collector", "collected.contract.v1.json"),
]

# Properties that must NEVER appear anywhere in the collected schema — it is
# EVIDENCE, never a verdict (RD-014). Checked recursively.
_BANNED_VERDICT_KEYS = frozenset(
    {"verdict", "safe", "approved", "forward", "malicious", "pass_fail", "clean"}
)


def _load_schema() -> dict:
    with open(_SCHEMA_PATH, encoding="utf-8") as fh:
        return json.load(fh)


class TestCollectedContractConformance(unittest.TestCase):
    """Pure-Python manual conformance — runs even without jsonschema."""

    def setUp(self):
        self.schema = _load_schema()

    # --- allow-list: additionalProperties:false at every object level --------
    def _assert_closed(self, node, path="<root>"):
        if isinstance(node, dict):
            # Any node that declares object-shape (type object and/or properties)
            # must be a closed allow-list.
            declares_object = node.get("type") == "object" or "properties" in node
            if declares_object:
                self.assertEqual(
                    node.get("additionalProperties"),
                    False,
                    f"object node at {path} must set additionalProperties:false",
                )
            props = node.get("properties")
            if isinstance(props, dict):
                for pk, pv in props.items():
                    self._assert_closed(pv, f"{path}.properties.{pk}")
            items = node.get("items")
            if isinstance(items, dict):
                self._assert_closed(items, f"{path}.items")
            elif isinstance(items, list):
                for i, iv in enumerate(items):
                    self._assert_closed(iv, f"{path}.items[{i}]")

    def test_additional_properties_false_everywhere(self):
        self._assert_closed(self.schema)

    # --- no verdict-family property anywhere ---------------------------------
    def _assert_no_banned_property(self, node, path="<root>"):
        if isinstance(node, dict):
            props = node.get("properties")
            if isinstance(props, dict):
                for pk in props:
                    self.assertNotIn(
                        pk,
                        _BANNED_VERDICT_KEYS,
                        f"schema defines a verdict property {pk!r} at {path}",
                    )
            for k, v in node.items():
                self._assert_no_banned_property(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                self._assert_no_banned_property(v, f"{path}[{i}]")

    def test_no_verdict_property_anywhere(self):
        self._assert_no_banned_property(self.schema)

    # --- top-level allow-list + own version pin + unique discriminator -------
    def test_top_level_shape(self):
        self.assertEqual(self.schema.get("$schema"), "http://json-schema.org/draft-07/schema#")
        self.assertEqual(
            self.schema.get("$id"),
            "https://ztie.internal/schemas/collected.contract.v1.json",
        )
        self.assertEqual(self.schema.get("type"), "object")
        self.assertEqual(self.schema.get("additionalProperties"), False)
        self.assertEqual(
            self.schema.get("required"),
            ["contract_version", "intake_id", "sha256", "joined_at", "collected"],
        )
        props = self.schema["properties"]
        # Own version pin — enum ['1.0'], NOT a shared version.
        self.assertEqual(props["contract_version"]["enum"], ["1.0"])
        # Integrity keys are bounded patterns.
        self.assertIn("pattern", props["intake_id"])
        self.assertEqual(props["sha256"]["pattern"], "^[0-9a-f]{64}$")
        self.assertEqual(props["joined_at"]["maxLength"], 40)
        # Unique 'collected' discriminator; it must NOT collide with the other
        # envelope kinds' discriminator keys.
        self.assertIn("collected", props)
        for colliding in ("run", "scan", "rejection", "routing", "classification", "status"):
            self.assertNotIn(
                colliding,
                props,
                f"top-level key {colliding!r} collides with another envelope kind",
            )

    # --- join facts: per-lane status records completed/errored/not_applicable
    def test_records_per_lane_status_and_join_facts(self):
        collected = self.schema["properties"]["collected"]
        self.assertEqual(collected.get("additionalProperties"), False)
        self.assertEqual(
            collected["required"],
            ["lanes_expected", "lanes_collected", "both_complete", "static", "dynamic"],
        )
        cprops = collected["properties"]
        self.assertEqual(cprops["both_complete"]["type"], "boolean")
        for lane_key, lane_const in (
            ("static", "static_analysis"),
            ("dynamic", "dynamic_detonation"),
        ):
            lane = cprops[lane_key]
            self.assertEqual(lane["properties"]["lane"]["const"], lane_const)
            self.assertEqual(
                lane["properties"]["lane_status"]["enum"],
                ["completed", "errored", "not_applicable"],
            )
        # References (does not duplicate) the per-lane evidence via bounded pointers.
        self.assertIn("findings_s3_key", cprops["static"]["properties"])
        self.assertIn("highest_severity", cprops["static"]["properties"])
        self.assertIn("run_log_s3_key", cprops["dynamic"]["properties"])
        self.assertIn("outcome", cprops["dynamic"]["properties"])

    # --- hash-match: canonical file byte-matches the bundled copies ----------
    def test_bundled_copies_byte_match(self):
        with open(_SCHEMA_PATH, "rb") as fh:
            canonical = fh.read()
        for bundled in _BUNDLED_PATHS:
            with open(bundled, "rb") as fh:
                self.assertEqual(
                    fh.read(),
                    canonical,
                    f"bundled copy {bundled} must byte-match the canonical schema",
                )


if __name__ == "__main__":
    unittest.main()
