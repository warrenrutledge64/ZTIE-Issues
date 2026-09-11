#!/usr/bin/env python3
"""
ZTIE VPC cost auditor.

Run this in AWS CloudShell in EITHER account (Hub 641628980935 or
Forensic 360999005254). It enumerates every VPC in the region and, for each,
reports the resources that ACTUALLY COST MONEY:

  * NAT Gateways            (~$32/mo each + data processing)
  * Interface VPC endpoints (~$7.20/mo per endpoint per AZ + data)
  * Elastic IPs             (billed when allocated but not associated, or on NATs)
  * Running EC2 instances   (compute + EBS)

An empty VPC (subnets, route tables, gateway S3/DynamoDB endpoints, IGW alone)
is $0 — so those are listed only for context, not as cost.

Nothing here MUTATES anything. It is read-only. Deletion is a separate,
deliberate step you run after reviewing this output.

Usage (in CloudShell):
    aws sts get-caller-identity          # confirm which account you are in
    python3 vpc_cost_audit.py            # audits the default region
    python3 vpc_cost_audit.py --region us-east-1
"""
from __future__ import annotations

import argparse
import sys

import boto3

# Rough public on-demand list prices, us-east-1, for at-a-glance estimation only.
# Real bill depends on region + data processing. These are the IDLE hourly-run costs.
NAT_GW_MONTHLY = 32.40  # ~$0.045/hr * 720
INTERFACE_ENDPOINT_MONTHLY = 7.20  # ~$0.01/hr * 720, per AZ (ENI)
EIP_IDLE_MONTHLY = 3.60  # ~$0.005/hr * 720 for an unattached (or extra) EIP


def _tag(resource: dict, key: str = "Name") -> str:
    for t in resource.get("Tags", []):
        if t.get("Key") == key:
            return t.get("Value", "")
    return ""


def audit(region: str) -> None:
    ec2 = boto3.client("ec2", region_name=region)
    ident = boto3.client("sts").get_caller_identity()
    account = ident["Account"]

    print("=" * 78)
    print(f"ZTIE VPC COST AUDIT  |  account {account}  |  region {region}")
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
        print(f"\n--- VPC {vpc_id}  [{name}]  cidr={cidr}"
              f"{'  (DEFAULT VPC)' if is_default else ''} ---")

        vpc_cost = 0.0

        # NAT gateways ------------------------------------------------------
        nats = ec2.describe_nat_gateways(
            Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
        )["NatGateways"]
        live_nats = [n for n in nats if n.get("State") in ("available", "pending")]
        if live_nats:
            c = len(live_nats) * NAT_GW_MONTHLY
            vpc_cost += c
            print(f"  NAT GATEWAYS: {len(live_nats)}  ~${c:.2f}/mo  <-- BILLABLE")
            for n in live_nats:
                print(f"      {n['NatGatewayId']}  state={n['State']}  "
                      f"subnet={n.get('SubnetId')}")
        else:
            print("  NAT gateways: 0")

        # Interface endpoints ----------------------------------------------
        eps = ec2.describe_vpc_endpoints(
            Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]
        )["VpcEndpoints"]
        iface = [e for e in eps if e.get("VpcEndpointType") == "Interface"]
        gateway = [e for e in eps if e.get("VpcEndpointType") == "Gateway"]
        if iface:
            # cost scales with number of ENIs (endpoint x AZ)
            eni_count = sum(max(1, len(e.get("SubnetIds", []) or [1])) for e in iface)
            c = eni_count * INTERFACE_ENDPOINT_MONTHLY
            vpc_cost += c
            print(f"  INTERFACE ENDPOINTS: {len(iface)} endpoints / {eni_count} ENIs"
                  f"  ~${c:.2f}/mo  <-- BILLABLE")
            for e in iface:
                svc = e.get("ServiceName", "").split(".")[-1]
                azs = len(e.get("SubnetIds", []))
                print(f"      {e['VpcEndpointId']}  {svc}  azs={azs}  "
                      f"state={e.get('State')}")
        else:
            print("  Interface endpoints: 0")
        if gateway:
            print(f"  Gateway endpoints (FREE): {len(gateway)} "
                  f"({', '.join(e.get('ServiceName','').split('.')[-1] for e in gateway)})")

        # Elastic IPs -------------------------------------------------------
        addrs = ec2.describe_addresses()["Addresses"]
        # EIPs on NAT gws are counted via the NAT already; flag UNATTACHED ones.
        unattached = [a for a in addrs if not a.get("AssociationId")]
        if unattached:
            c = len(unattached) * EIP_IDLE_MONTHLY
            vpc_cost += c
            print(f"  UNATTACHED ELASTIC IPs (account-wide): {len(unattached)}"
                  f"  ~${c:.2f}/mo  <-- BILLABLE")
            for a in unattached:
                print(f"      {a.get('AllocationId')}  {a.get('PublicIp')}")

        # Running instances -------------------------------------------------
        insts = ec2.describe_instances(
            Filters=[
                {"Name": "vpc-id", "Values": [vpc_id]},
                {"Name": "instance-state-name", "Values": ["running", "pending"]},
            ]
        )["Reservations"]
        running = [i for r in insts for i in r["Instances"]]
        if running:
            print(f"  RUNNING EC2 INSTANCES: {len(running)}  <-- BILLABLE (compute+EBS)")
            for i in running:
                print(f"      {i['InstanceId']}  {i.get('InstanceType')}  "
                      f"launched={i.get('LaunchTime')}  name={_tag(i)}")
        else:
            print("  Running EC2 instances: 0")

        print(f"  >>> estimated idle VPC cost: ~${vpc_cost:.2f}/mo")
        grand_total += vpc_cost

    print("\n" + "=" * 78)
    print(f"ESTIMATED TOTAL IDLE COST (this account/region): ~${grand_total:.2f}/mo")
    print("(EIPs are account-wide, not per-VPC; estimates are list price, "
          "excl. data processing.)")
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
