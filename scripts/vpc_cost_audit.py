#!/usr/bin/env python3
"""
ZTIE VPC cost auditor.

Run this in AWS CloudShell in EITHER account (Hub 641628980935 or
Forensic 360999005254). It enumerates every VPC in the region and, for each,
reports the resources that ACTUALLY COST MONEY:

  * NAT Gateways            (~$32/mo each + data processing)
  * Interface VPC endpoints (~$7.20/mo per endpoint per AZ + data)
  * Elastic IPs             (billed when allocated but not associated)
  * Running EC2 instances   (compute + EBS)

An empty VPC (subnets, route tables, gateway S3/DynamoDB endpoints, IGW alone)
is $0 -- so those are listed only for context, not as cost.

Nothing here MUTATES anything. It is read-only. Deletion is a separate,
deliberate step you run after reviewing this output.

NOTE ON FORMATTING: this script deliberately avoids f-strings that contain a
literal newline escape. When pasted into a shell heredoc, a terminal can expand
an embedded "\\n" inside an f-string into a real line break and split the string
literal, causing a SyntaxError. We use NL = chr(10) + plain concatenation / %
formatting so a heredoc paste is safe.

Usage (in CloudShell):
    aws sts get-caller-identity          # confirm which account you are in
    python3 vpc_cost_audit.py            # audits the default region
    python3 vpc_cost_audit.py --region us-east-1
"""
# ruff: noqa: UP031
# NOTE: UP031 (prefer str.format over %-formatting) is intentionally disabled for
# this file. %-formatting and plain concatenation are used on purpose so this
# script survives being pasted into a shell heredoc without any string literal
# being mangled by newline expansion.
from __future__ import annotations

import argparse
import sys

import boto3

NL = chr(10)

# Rough public on-demand list prices, us-east-1, for at-a-glance estimation only.
# Real bill depends on region + data processing. These are IDLE hourly-run costs.
NAT_GW_MONTHLY = 32.40  # ~$0.045/hr * 720
INTERFACE_ENDPOINT_MONTHLY = 7.20  # ~$0.01/hr * 720, per AZ (ENI)
EIP_IDLE_MONTHLY = 3.60  # ~$0.005/hr * 720 for an unattached EIP


def _tag(resource: dict, key: str = "Name") -> str:
    for t in resource.get("Tags", []):
        if t.get("Key") == key:
            return t.get("Value", "")
    return ""


def audit(region: str) -> None:
    ec2 = boto3.client("ec2", region_name=region)
    account = boto3.client("sts").get_caller_identity()["Account"]

    print("=" * 78)
    print("ZTIE VPC COST AUDIT  |  account " + account + "  |  region " + region)
    print("=" * 78)

    vpcs = ec2.describe_vpcs()["Vpcs"]
    if not vpcs:
        print("No VPCs in this region.")
        return

    grand_total = 0.0

    for vpc in vpcs:
        vpc_id = vpc["VpcId"]
        is_default = vpc.get("IsDefault", False)
        name = _tag(vpc) or "(no Name tag)"
        cidr = vpc.get("CidrBlock", "?")
        default_tag = "  (DEFAULT VPC)" if is_default else ""
        print(NL + "--- VPC " + vpc_id + "  [" + name + "]  cidr=" + cidr
              + default_tag + " ---")

        vpc_cost = 0.0

        # NAT gateways ------------------------------------------------------
        nats = ec2.describe_nat_gateways(
            Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
        )["NatGateways"]
        live_nats = [n for n in nats if n.get("State") in ("available", "pending")]
        if live_nats:
            c = len(live_nats) * NAT_GW_MONTHLY
            vpc_cost += c
            print("  NAT GATEWAYS: %d  ~$%.2f/mo  <-- BILLABLE" % (len(live_nats), c))
            for n in live_nats:
                print("      " + n["NatGatewayId"] + "  state=" + str(n.get("State"))
                      + "  subnet=" + str(n.get("SubnetId")))
        else:
            print("  NAT gateways: 0")

        # Interface endpoints ----------------------------------------------
        eps = ec2.describe_vpc_endpoints(
            Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
        )["VpcEndpoints"]
        iface = [e for e in eps if e.get("VpcEndpointType") == "Interface"]
        gateway = [e for e in eps if e.get("VpcEndpointType") == "Gateway"]
        if iface:
            eni_count = sum(max(1, len(e.get("SubnetIds", []) or [1])) for e in iface)
            c = eni_count * INTERFACE_ENDPOINT_MONTHLY
            vpc_cost += c
            print("  INTERFACE ENDPOINTS: %d endpoints / %d ENIs  ~$%.2f/mo  <-- BILLABLE"
                  % (len(iface), eni_count, c))
            for e in iface:
                svc = e.get("ServiceName", "").split(".")[-1]
                azs = len(e.get("SubnetIds", []))
                print("      " + e["VpcEndpointId"] + "  " + svc + "  azs=" + str(azs)
                      + "  state=" + str(e.get("State")))
        else:
            print("  Interface endpoints: 0")
        if gateway:
            names = ", ".join(e.get("ServiceName", "").split(".")[-1] for e in gateway)
            print("  Gateway endpoints (FREE): %d (%s)" % (len(gateway), names))

        # Elastic IPs (account-wide) ---------------------------------------
        addrs = ec2.describe_addresses()["Addresses"]
        unattached = [a for a in addrs if not a.get("AssociationId")]
        if unattached:
            c = len(unattached) * EIP_IDLE_MONTHLY
            vpc_cost += c
            print("  UNATTACHED ELASTIC IPs (account-wide): %d  ~$%.2f/mo  <-- BILLABLE"
                  % (len(unattached), c))
            for a in unattached:
                print("      " + str(a.get("AllocationId")) + "  " + str(a.get("PublicIp")))

        # Running instances -------------------------------------------------
        insts = ec2.describe_instances(
            Filters=[
                {"Name": "vpc-id", "Values": [vpc_id]},
                {"Name": "instance-state-name", "Values": ["running", "pending"]},
            ]
        )["Reservations"]
        running = [i for r in insts for i in r["Instances"]]
        if running:
            print("  RUNNING EC2 INSTANCES: %d  <-- BILLABLE (compute+EBS)" % len(running))
            for i in running:
                print("      " + i["InstanceId"] + "  " + str(i.get("InstanceType"))
                      + "  launched=" + str(i.get("LaunchTime")) + "  name=" + _tag(i))
        else:
            print("  Running EC2 instances: 0")

        print("  >>> estimated idle VPC cost: ~$%.2f/mo" % vpc_cost)
        grand_total += vpc_cost

    print(NL + "=" * 78)
    print("ESTIMATED TOTAL IDLE COST (this account/region): ~$%.2f/mo" % grand_total)
    print("(EIPs are account-wide; estimates are list price, excl. data processing.)")
    print("=" * 78)


def main() -> int:
    p = argparse.ArgumentParser(description="Audit billable VPC resources.")
    p.add_argument("--region", default=None,
                   help="AWS region (default: session/env default).")
    args = p.parse_args()
    region = args.region or boto3.session.Session().region_name or "us-east-1"
    audit(region)
    return 0


if __name__ == "__main__":
    sys.exit(main())
