"""Unit tests for the restore-relevant projection + diff (Story 1.R).

Pure-logic tests — no boto3, no AWS — so they run in the INTEGRATIONS_ONLY build
sandbox with plain ``unittest`` and also under ``pytest`` live. They pin the
central lesson: verify compares a PROJECTION, and volatile metadata must never
false-positive as drift.
"""

from __future__ import annotations

import unittest

from ztie_restore import projection as proj


class TestProjectionBuilders(unittest.TestCase):
    def test_cfn_projection_hashes_template_and_keeps_tags(self):
        p = proj.cfn_stack_projection(
            name="ZtieHubTrackingStack",
            template_body='{"Resources":{}}',
            parameters={"b": "2", "a": "1"},
            tags={"Project": "ZTIE", "Account": "Hub"},
        )
        self.assertEqual(p["type"], "cloudformation_stack")
        self.assertEqual(p["name"], "ZtieHubTrackingStack")
        self.assertEqual(len(p["template_sha256"]), 64)
        # parameters + tags are canonicalised (key-sorted).
        self.assertEqual(list(p["parameters"].keys()), ["a", "b"])
        self.assertEqual(list(p["tags"].keys()), ["Account", "Project"])

    def test_cfn_projection_hash_is_content_stable(self):
        a = proj.cfn_stack_projection(
            name="S", template_body="X", parameters=None, tags=None
        )
        b = proj.cfn_stack_projection(
            name="S", template_body="X", parameters={}, tags={}
        )
        self.assertEqual(a["template_sha256"], b["template_sha256"])

    def test_dynamodb_projection_sorts_attrs_and_gsis(self):
        p = proj.dynamodb_table_projection(
            name="t",
            billing_mode="PAY_PER_REQUEST",
            key_schema=[{"name": "intake_id", "key_type": "HASH"}],
            attribute_definitions=[
                {"name": "status", "type": "S"},
                {"name": "intake_id", "type": "S"},
            ],
            gsis=[
                {
                    "name": "status-received_at-index",
                    "key_schema": [{"name": "status", "key_type": "HASH"}],
                    "projection_type": "ALL",
                }
            ],
            sse="KMS",
            pitr=True,
        )
        # attribute_definitions sorted by name -> intake_id before status.
        self.assertEqual(
            [a["name"] for a in p["attribute_definitions"]], ["intake_id", "status"]
        )
        self.assertTrue(p["pitr"])

    def test_lambda_and_s3_projection_shapes(self):
        lam = proj.lambda_function_projection(
            name="fn", runtime="python3.12", handler="handler.handler", code_sha256="abc"
        )
        self.assertEqual(lam["runtime"], "python3.12")
        bucket = proj.s3_bucket_projection(
            name="b",
            versioning="Enabled",
            encryption="aws:kms",
            public_access_block={"BlockPublicAcls": True},
            bucket_key_enabled=True,
        )
        # all four PAB keys present, defaulting missing ones to False.
        self.assertEqual(
            set(bucket["public_access_block"]),
            {
                "BlockPublicAcls",
                "IgnorePublicAcls",
                "BlockPublicPolicy",
                "RestrictPublicBuckets",
            },
        )
        self.assertFalse(bucket["public_access_block"]["IgnorePublicAcls"])


class TestDiff(unittest.TestCase):
    def _stack(self, tags):
        return proj.cfn_stack_projection(
            name="ZtieHubTrackingStack",
            template_body="TEMPLATE",
            parameters={"p": "1"},
            tags=tags,
        )

    def test_identical_projections_match(self):
        cap = [self._stack({"Project": "ZTIE"})]
        live = [self._stack({"Project": "ZTIE"})]
        diff = proj.diff_projections(cap, live)
        self.assertTrue(diff["match"], diff)
        self.assertEqual(diff["changed"], [])

    def test_ordering_never_causes_drift(self):
        cap = [
            proj.lambda_function_projection(
                name="a", runtime="python3.12", handler="h", code_sha256="1"
            ),
            proj.lambda_function_projection(
                name="b", runtime="python3.12", handler="h", code_sha256="2"
            ),
        ]
        live = list(reversed(cap))  # same content, different order
        self.assertTrue(proj.diff_projections(cap, live)["match"])

    def test_dropped_tag_is_drift(self):
        # This is the exact CFN-tags lesson: losing a stack tag MUST be caught.
        cap = [self._stack({"Project": "ZTIE", "Story": "1.1R"})]
        live = [self._stack({"Project": "ZTIE"})]
        diff = proj.diff_projections(cap, live)
        self.assertFalse(diff["match"])
        changed_fields = {c["field"] for c in diff["changed"]}
        self.assertIn("tags", changed_fields)

    def test_missing_and_unexpected(self):
        cap = [self._stack({"Project": "ZTIE"})]
        live = [
            proj.lambda_function_projection(
                name="x", runtime="python3.12", handler="h", code_sha256="9"
            )
        ]
        diff = proj.diff_projections(cap, live)
        self.assertFalse(diff["match"])
        self.assertIn(["cloudformation_stack", "ZtieHubTrackingStack"], diff["missing"])
        self.assertIn(["lambda_function", "x"], diff["unexpected"])

    def test_uncaptured_secure_value_is_not_drift(self):
        cap = [
            proj.ssm_parameter_projection(
                name="/ztie/secret", type_="SecureString", value=None, secure=True
            )
        ]
        live = [
            proj.ssm_parameter_projection(
                name="/ztie/secret",
                type_="SecureString",
                value="live-secret",
                secure=True,
            )
        ]
        # Without opting in to secure values, the value field is dropped both sides.
        self.assertTrue(proj.diff_projections(cap, live)["match"])
        # With opt-in, the differing value IS drift.
        self.assertFalse(
            proj.diff_projections(cap, live, include_secure_values=True)["match"]
        )


if __name__ == "__main__":
    unittest.main()
