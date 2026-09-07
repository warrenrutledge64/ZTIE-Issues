"""ZTIE Story 2.0E (RD-027) — offline unit tests for the ephemeral interface
VPC-endpoint seam in ``awsio.py``.

Pure stdlib ``unittest`` — runs in the INTEGRATIONS_ONLY sandbox (no boto3 / moto /
pytest needed). We inject a tiny fake EC2 client into the module-level client cache
so the seam's *logic* (tag-scoping, availability polling, fail-safe-never-raise
teardown, orphan sweep) is exercised without any real AWS call. The real EC2 path is
covered live by the stakeholder's validation run.
"""

from __future__ import annotations

import sys
import types
import unittest

# The INTEGRATIONS_ONLY sandbox has no boto3 (see repo Lessons Learned). awsio.py
# imports boto3 + botocore at module top for its client factories, but these tests
# never touch the real client — they inject a fake into awsio._ec2_client. So stub
# just enough of boto3/botocore to import awsio offline. (Live tests use real boto3.)
if "boto3" not in sys.modules:
    _boto3 = types.ModuleType("boto3")
    _boto3.client = lambda *a, **k: None  # never called in these tests
    sys.modules["boto3"] = _boto3
if "botocore" not in sys.modules:
    _botocore = types.ModuleType("botocore")
    _config = types.ModuleType("botocore.config")
    _config.Config = lambda *a, **k: None
    _botocore.config = _config
    sys.modules["botocore"] = _botocore
    sys.modules["botocore.config"] = _config

import awsio


class _FakeEc2:
    """Minimal fake EC2 client capturing calls and returning scripted responses."""

    def __init__(self):
        self.created: list[dict] = []
        self.deleted: list[list[str]] = []
        self.describe_responses: list[dict] = []
        self.describe_calls: list[dict] = []
        self._create_seq = 0
        self.raise_on_delete = False
        self.raise_on_describe = False

    def create_vpc_endpoint(self, **kwargs):
        self.created.append(kwargs)
        self._create_seq += 1
        return {"VpcEndpoint": {"VpcEndpointId": f"vpce-{self._create_seq:04d}"}}

    def describe_vpc_endpoints(self, **kwargs):
        self.describe_calls.append(kwargs)
        if self.raise_on_describe:
            raise RuntimeError("boom")
        return self.describe_responses.pop(0) if self.describe_responses else {"VpcEndpoints": []}

    def delete_vpc_endpoints(self, **kwargs):
        if self.raise_on_delete:
            raise RuntimeError("boom")
        self.deleted.append(kwargs["VpcEndpointIds"])
        return {}


class _Base(unittest.TestCase):
    def setUp(self):
        self.fake = _FakeEc2()
        awsio._ec2_client = self.fake  # inject

    def tearDown(self):
        awsio._ec2_client = None  # reset the module cache


class TestCreate(_Base):
    def test_creates_one_per_service_and_tags_them(self):
        ids = awsio.create_interface_endpoints(
            vpc_id="vpc-1",
            subnet_id="subnet-1",
            security_group_id="sg-1",
            service_names=["com.amazonaws.us-east-1.ssm", "com.amazonaws.us-east-1.sqs"],
            intake_id="intake-xyz",
        )
        self.assertEqual(len(ids), 2)
        self.assertEqual(len(self.fake.created), 2)
        first = self.fake.created[0]
        self.assertEqual(first["VpcEndpointType"], "Interface")
        self.assertTrue(first["PrivateDnsEnabled"])
        self.assertEqual(first["SubnetIds"], ["subnet-1"])
        self.assertEqual(first["SecurityGroupIds"], ["sg-1"])
        # Tagged so teardown + sweep can find exactly these.
        tags = {t["Key"]: t["Value"] for t in first["TagSpecifications"][0]["Tags"]}
        self.assertEqual(tags[awsio._EPHEMERAL_TAG_KEY], awsio._EPHEMERAL_TAG_VALUE)
        self.assertEqual(tags["IntakeId"], "intake-xyz")


class TestWaitAvailable(_Base):
    def test_empty_is_trivially_true(self):
        self.assertTrue(awsio.wait_for_endpoints_available([], timeout_s=1))

    def test_all_available_returns_true(self):
        self.fake.describe_responses = [
            {"VpcEndpoints": [{"State": "available"}, {"State": "available"}]}
        ]
        # dns_settle_s=0 so the state-logic assertion does not incur a real sleep.
        self.assertTrue(
            awsio.wait_for_endpoints_available(
                ["vpce-1", "vpce-2"], timeout_s=5, poll_s=0, dns_settle_s=0
            )
        )

    def test_failed_state_bails_early_false(self):
        self.fake.describe_responses = [
            {"VpcEndpoints": [{"State": "available"}, {"State": "failed"}]}
        ]
        self.assertFalse(
            awsio.wait_for_endpoints_available(
                ["vpce-1", "vpce-2"], timeout_s=5, poll_s=0, dns_settle_s=0
            )
        )

    def test_dns_settle_delay_applied_only_after_available(self):
        # RD-027 SSM-online race fix: once all endpoints are 'available', the
        # function sleeps dns_settle_s to let private DNS propagate before the
        # caller launches the host. Stub time.sleep to capture the settle without
        # actually sleeping, and assert it was applied with the right duration.
        slept: list[float] = []
        orig_sleep = awsio.time.sleep
        awsio.time.sleep = lambda s: slept.append(s)
        try:
            self.fake.describe_responses = [
                {"VpcEndpoints": [{"State": "available"}]}
            ]
            ok = awsio.wait_for_endpoints_available(
                ["vpce-1"], timeout_s=5, poll_s=0, dns_settle_s=45
            )
        finally:
            awsio.time.sleep = orig_sleep
        self.assertTrue(ok)
        # The 45s settle sleep must have been applied (exactly once, since the
        # endpoint was already available on the first poll -> no poll sleeps).
        self.assertIn(45, slept)

    def test_dns_settle_not_applied_when_never_available(self):
        # If endpoints never reach 'available' (timeout), the settle delay must NOT
        # be applied -- there is nothing to settle and the caller will error out.
        slept: list[float] = []
        orig_sleep = awsio.time.sleep
        awsio.time.sleep = lambda s: slept.append(s)
        try:
            self.fake.describe_responses = [
                {"VpcEndpoints": [{"State": "pending"}]}
            ]
            ok = awsio.wait_for_endpoints_available(
                ["vpce-1"], timeout_s=0, poll_s=0, dns_settle_s=45
            )
        finally:
            awsio.time.sleep = orig_sleep
        self.assertFalse(ok)
        self.assertNotIn(45, slept)


class TestDelete(_Base):
    def test_deletes_ids(self):
        awsio.delete_interface_endpoints(["vpce-1", "vpce-2"])
        self.assertEqual(self.fake.deleted, [["vpce-1", "vpce-2"]])

    def test_empty_is_noop(self):
        awsio.delete_interface_endpoints([])
        self.assertEqual(self.fake.deleted, [])

    def test_never_raises_on_error(self):
        # Fail-safe: a delete failure is a COST risk, never fatal (the sweep is the
        # backstop). Must NOT propagate.
        self.fake.raise_on_delete = True
        try:
            awsio.delete_interface_endpoints(["vpce-1"])
        except Exception:  # noqa: BLE001
            self.fail("delete_interface_endpoints must never raise")


class TestSweep(_Base):
    def test_sweep_is_scoped_by_vpc_and_ztie_tag(self):
        self.fake.describe_responses = [
            {"VpcEndpoints": [
                {"VpcEndpointId": "vpce-a", "State": "available"},
                {"VpcEndpointId": "vpce-b", "State": "pending"},
                {"VpcEndpointId": "vpce-c", "State": "deleting"},  # skipped
            ]}
        ]
        # Second describe (the post-delete drain wait) sees them gone.
        self.fake.describe_responses.append({"VpcEndpoints": []})
        deleted = awsio.sweep_orphaned_endpoints("vpc-1", drain_timeout_s=5)
        # Deleting-state endpoint is skipped; the other two are swept.
        self.assertEqual(sorted(deleted), ["vpce-a", "vpce-b"])
        self.assertEqual(self.fake.deleted, [["vpce-a", "vpce-b"]])
        # The describe was scoped by vpc-id AND the ZTIE ephemeral tag.
        filters = {f["Name"]: f["Values"] for f in self.fake.describe_calls[0]["Filters"]}
        self.assertEqual(filters["vpc-id"], ["vpc-1"])
        self.assertEqual(
            filters[f"tag:{awsio._EPHEMERAL_TAG_KEY}"], [awsio._EPHEMERAL_TAG_VALUE]
        )

    def test_sweep_waits_for_deletion_to_drain_before_returning(self):
        # RD-027 live fix: after deleting the orphan, the sweep must wait for it to
        # be GONE before returning, so the caller does not create a same-service
        # endpoint while the old one is still 'deleting' (DNS race). First describe
        # finds the orphan; the drain describes see it still deleting, then gone.
        self.fake.describe_responses = [
            {"VpcEndpoints": [{"VpcEndpointId": "vpce-a", "State": "available"}]},
            {"VpcEndpoints": [{"VpcEndpointId": "vpce-a", "State": "deleting"}]},
            {"VpcEndpoints": []},  # gone
        ]
        orig_sleep = awsio.time.sleep
        awsio.time.sleep = lambda s: None  # do not actually sleep during the drain
        try:
            deleted = awsio.sweep_orphaned_endpoints("vpc-1", drain_timeout_s=5)
        finally:
            awsio.time.sleep = orig_sleep
        self.assertEqual(deleted, ["vpce-a"])
        # It kept polling past the 'deleting' state until the endpoint was gone
        # (>= 3 describe calls: initial scan + at least one deleting + gone).
        self.assertGreaterEqual(len(self.fake.describe_calls), 3)


class TestWaitGone(_Base):
    def test_empty_is_trivially_true(self):
        self.assertTrue(awsio.wait_for_endpoints_gone([], timeout_s=1))

    def test_notfound_means_gone(self):
        self.fake.raise_on_describe = True  # NotFound-style error => gone
        self.assertTrue(
            awsio.wait_for_endpoints_gone(["vpce-1"], timeout_s=5, poll_s=0)
        )

    def test_gone_when_no_endpoints_returned(self):
        self.fake.describe_responses = [{"VpcEndpoints": []}]
        self.assertTrue(
            awsio.wait_for_endpoints_gone(["vpce-1"], timeout_s=5, poll_s=0)
        )

    def test_sweep_empty_returns_empty_and_no_delete(self):
        self.fake.describe_responses = [{"VpcEndpoints": []}]
        self.assertEqual(awsio.sweep_orphaned_endpoints("vpc-1"), [])
        self.assertEqual(self.fake.deleted, [])

    def test_sweep_never_raises(self):
        self.fake.raise_on_describe = True
        try:
            self.assertEqual(awsio.sweep_orphaned_endpoints("vpc-1"), [])
        except Exception:  # noqa: BLE001
            self.fail("sweep_orphaned_endpoints must never raise")


if __name__ == "__main__":
    unittest.main()
