#!/usr/bin/env python3
"""
ZTIE read-only environment discovery (zero-trust split-brain, discovery mode).

Objective, READ-ONLY interrogation of the live AWS environment for one account:
  Layer 1 (enumerate)  : what infrastructure EXISTS.
  Layer 2 (verify)     : pull the config/state that proves each thing is LIVE
                         and correctly wired.

Scope this tool was built for: Forensic 360999005254 + Pipeline-Hub 641628980935,
region us-east-1. Run it once per account (in that account's credentialed shell).

HARD GUARANTEES
  * READ-ONLY BY CONSTRUCTION. Every boto3 call is a describe_/list_/get_/
    batch_get_/head_ call, plus a single DynamoDB scan(Select='COUNT') which
    returns only an item count (no attribute data). A allow-list of verb
    prefixes is enforced at call time; anything else raises before it runs.
  * NON-DESTRUCTIVE. It creates nothing, tags nothing, deletes nothing.
  * The account is verified up front (sts get-caller-identity). If it does not
    match --expect-account the tool refuses to run (wrong-tab guard).

OUTPUT
  * A structured JSON artifact:  discovery-<account>-<utc>.json
  * A human-readable summary to stdout.

Reusable (RD-015): parameterized by account + region, re-runnable by a third
party, and the JSON artifact is diffable across runs.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from collections.abc import Callable
from typing import Any

try:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError, EndpointConnectionError
except ImportError:  # pragma: no cover - boto3 is present in CloudShell
    print("boto3 is required (present by default in AWS CloudShell).", file=sys.stderr)
    raise

# ---------------------------------------------------------------------------
# Read-only enforcement
# ---------------------------------------------------------------------------

# Only operation names beginning with these verbs may ever be called.
_READ_ONLY_PREFIXES = (
    "describe_",
    "describe",  # sts get_caller_identity is get_; kept explicit below
    "list_",
    "get_",
    "batch_get_",
    "head_",
    "scan",  # only ever with Select='COUNT' (see _count_items)
    "lookup_",
)

# Known account -> friendly name (informational; not a trust boundary).
_KNOWN_ACCOUNTS = {
    "360999005254": "Forensic",
    "641628980935": "Pipeline-Hub",
    "586917955591": "Pipeline-Sandbox",
}


def _assert_read_only(op_name: str) -> None:
    """Fail closed if a non-read operation is ever attempted."""
    if not op_name.startswith(_READ_ONLY_PREFIXES):
        raise RuntimeError(
            f"BLOCKED: '{op_name}' is not a read-only operation. "
            "This tool is read-only by construction."
        )


class ReadOnlyClient:
    """Thin boto3 client wrapper that refuses any non-read operation."""

    def __init__(self, service: str, region: str):
        cfg = Config(
            region_name=region,
            retries={"max_attempts": 6, "mode": "adaptive"},
            read_timeout=30,
            connect_timeout=10,
        )
        self._c = boto3.client(service, config=cfg)
        self.service = service

    def call(self, op: str, **kwargs: Any) -> dict:
        _assert_read_only(op)
        fn: Callable[..., dict] = getattr(self._c, op)
        return fn(**kwargs)

    def paginate(self, op: str, key: str, **kwargs: Any) -> list:
        """Paginate a list_/describe_ op, collecting `key` from each page."""
        _assert_read_only(op)
        out: list = []
        if self._c.can_paginate(op):
            for page in self._c.get_paginator(op).paginate(**kwargs):
                out.extend(page.get(key, []) or [])
        else:
            resp = self.call(op, **kwargs)
            out.extend(resp.get(key, []) or [])
        return out


def _safe(label: str, fn: Callable[[], Any]) -> Any:
    """Run a discovery step, capturing AccessDenied / not-found as data, not crashes."""
    try:
        return fn()
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "ClientError")
        return {"_error": code, "_detail": str(e.response.get("Error", {}).get("Message", ""))[:300]}
    except EndpointConnectionError as e:
        return {"_error": "EndpointConnectionError", "_detail": str(e)[:200]}
    except Exception as e:  # noqa: BLE001 - discovery must be resilient
        return {"_error": type(e).__name__, "_detail": str(e)[:200]}


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

def whoami(region: str) -> dict:
    sts = boto3.client("sts", config=Config(region_name=region))
    ident = sts.get_caller_identity()  # get_ -> read-only
    acct = ident.get("Account", "")
    return {
        "account": acct,
        "account_name": _KNOWN_ACCOUNTS.get(acct, "UNKNOWN"),
        "arn": ident.get("Arn", ""),
        "user_id": ident.get("UserId", ""),
    }


# ---------------------------------------------------------------------------
# Layer 1 + Layer 2 per service
# ---------------------------------------------------------------------------

def discover_cloudformation(region: str) -> list:
    cf = ReadOnlyClient("cloudformation", region)
    stacks = cf.paginate("list_stacks", "StackSummaries")
    live = [
        s for s in stacks
        if s.get("StackStatus") != "DELETE_COMPLETE"
    ]
    out = []
    for s in live:
        out.append({
            "name": s.get("StackName"),
            "status": s.get("StackStatus"),                  # Layer 2: live?
            "created": _iso(s.get("CreationTime")),
            "updated": _iso(s.get("LastUpdatedTime")),
            "drift": s.get("DriftInformation", {}).get("StackDriftStatus"),
        })
    return sorted(out, key=lambda x: x["name"] or "")


def discover_lambda(region: str) -> list:
    lm = ReadOnlyClient("lambda", region)
    fns = lm.paginate("list_functions", "Functions")
    out = []
    for f in fns:
        out.append({
            "name": f.get("FunctionName"),
            "runtime": f.get("Runtime"),                     # Layer 2
            "last_modified": f.get("LastModified"),          # Layer 2: live/fresh?
            "code_sha256": f.get("CodeSha256"),
            "handler": f.get("Handler"),
            "memory_mb": f.get("MemorySize"),
            "timeout_s": f.get("Timeout"),
            "role": (f.get("Role") or "").split("/")[-1],
            "env_keys": sorted((f.get("Environment", {}).get("Variables", {}) or {}).keys()),
            "has_bedrock_env": any(
                "NOVA" in k or "BEDROCK" in k
                for k in (f.get("Environment", {}).get("Variables", {}) or {})
            ),
        })
    return sorted(out, key=lambda x: x["name"] or "")


def discover_stepfunctions(region: str) -> list:
    sf = ReadOnlyClient("stepfunctions", region)
    machines = sf.paginate("list_state_machines", "stateMachines")
    out = []
    for m in machines:
        arn = m.get("stateMachineArn")
        desc = _safe("sfn.describe", lambda a=arn: sf.call("describe_state_machine", stateMachineArn=a))
        # Layer 2: most-recent execution status proves it actually runs.
        execs = _safe(
            "sfn.list_exec",
            lambda a=arn: sf.call("list_executions", stateMachineArn=a, maxResults=1).get("executions", []),
        )
        last = execs[0] if isinstance(execs, list) and execs else None
        out.append({
            "name": m.get("name"),
            "arn": arn,
            "type": (desc.get("type") if isinstance(desc, dict) else None),
            "status": (desc.get("status") if isinstance(desc, dict) else None),
            "created": _iso(m.get("creationDate")),
            "last_execution": (
                {"status": last.get("status"), "start": _iso(last.get("startDate"))}
                if last else "no_executions"
            ),
        })
    return sorted(out, key=lambda x: x["name"] or "")


def discover_dynamodb(region: str) -> list:
    dy = ReadOnlyClient("dynamodb", region)
    names = dy.paginate("list_tables", "TableNames")
    out = []
    for n in names:
        d = _safe("ddb.describe", lambda t=n: dy.call("describe_table", TableName=t).get("Table", {}))
        # Layer 2: projected COUNT scan — returns ONLY a number, no item data.
        cnt = _safe("ddb.count", lambda t=n: dy.call("scan", TableName=t, Select="COUNT").get("Count"))
        out.append({
            "name": n,
            "status": d.get("TableStatus") if isinstance(d, dict) else d,   # Layer 2: ACTIVE?
            "item_count_metadata": d.get("ItemCount") if isinstance(d, dict) else None,
            "live_item_count": cnt,                          # Layer 2: actually holds data?
            "stream": (d.get("StreamSpecification", {}) or {}).get("StreamEnabled") if isinstance(d, dict) else None,
            "keys": [k.get("AttributeName") for k in (d.get("KeySchema", []) if isinstance(d, dict) else [])],
        })
    return sorted(out, key=lambda x: x["name"] or "")


def discover_s3(region: str) -> list:
    s3 = ReadOnlyClient("s3", region)
    buckets = _safe("s3.list", lambda: s3.call("list_buckets").get("Buckets", []))
    if isinstance(buckets, dict):  # error envelope
        return [buckets]
    out = []
    for b in buckets:
        name = b.get("Name")
        # Bucket region: only report buckets in the target region for this account sweep.
        loc = _safe("s3.loc", lambda nm=name: s3.call("get_bucket_location", Bucket=nm).get("LocationConstraint"))
        region_of = loc if loc else "us-east-1"  # null == us-east-1
        enc = _safe("s3.enc", lambda nm=name: s3.call("get_bucket_encryption", Bucket=nm))
        ver = _safe("s3.ver", lambda nm=name: s3.call("get_bucket_versioning", Bucket=nm).get("Status"))
        lock = _safe("s3.lock", lambda nm=name: s3.call("get_object_lock_configuration", Bucket=nm))
        out.append({
            "name": name,
            "created": _iso(b.get("CreationDate")),
            "region": region_of,
            "encryption": _summarize_enc(enc),                # Layer 2: SSE?
            "versioning": ver if not isinstance(ver, dict) else None,
            "object_lock": _object_lock_mode(lock),           # flags COMPLIANCE WORM
        })
    return sorted(out, key=lambda x: x["name"] or "")


def discover_apigateway(region: str) -> dict:
    v1 = ReadOnlyClient("apigateway", region)      # REST
    v2 = ReadOnlyClient("apigatewayv2", region)    # HTTP/WS
    rest = _safe("apigw.rest", lambda: v1.call("get_rest_apis", limit=500).get("items", []))
    rest_out = []
    if isinstance(rest, list):
        for a in rest:
            aid = a.get("id")
            # Layer 2: resources + methods prove wiring; get deployment stages.
            stages = _safe("apigw.stages", lambda i=aid: v1.call("get_stages", restApiId=i).get("item", []))
            rest_out.append({
                "id": aid,
                "name": a.get("name"),
                "created": _iso(a.get("createdDate")),
                "endpoint_types": (a.get("endpointConfiguration", {}) or {}).get("types"),
                "stages": [s.get("stageName") for s in stages] if isinstance(stages, list) else stages,
            })
    else:
        rest_out = [rest]
    http = _safe("apigw.http", lambda: v2.call("get_apis", MaxResults="500").get("Items", []))
    http_out = []
    if isinstance(http, list):
        for a in http:
            http_out.append({
                "id": a.get("ApiId"),
                "name": a.get("Name"),
                "protocol": a.get("ProtocolType"),
                "endpoint": a.get("ApiEndpoint"),
            })
    else:
        http_out = [http]
    return {"rest_v1": rest_out, "http_v2": http_out}


def discover_ec2(region: str) -> dict:
    ec2 = ReadOnlyClient("ec2", region)
    lts = _safe("ec2.lt", lambda: ec2.paginate("describe_launch_templates", "LaunchTemplates"))
    vpcs = _safe("ec2.vpc", lambda: ec2.paginate("describe_vpcs", "Vpcs"))
    eps = _safe("ec2.ep", lambda: ec2.paginate("describe_vpc_endpoints", "VpcEndpoints"))
    subnets = _safe("ec2.subnet", lambda: ec2.paginate("describe_subnets", "Subnets"))
    igws = _safe("ec2.igw", lambda: ec2.paginate("describe_internet_gateways", "InternetGateways"))
    nats = _safe("ec2.nat", lambda: ec2.paginate("describe_nat_gateways", "NatGateways"))
    running = _safe(
        "ec2.inst",
        lambda: ec2.paginate(
            "describe_instances", "Reservations",
            Filters=[{"Name": "instance-state-name", "Values": ["pending", "running", "shutting-down", "stopping"]}],
        ),
    )
    inst_count = 0
    if isinstance(running, list):
        for r in running:
            inst_count += len(r.get("Instances", []))
    return {
        "launch_templates": [
            {"name": t.get("LaunchTemplateName"), "id": t.get("LaunchTemplateId"),
             "default_version": t.get("DefaultVersionNumber"), "latest_version": t.get("LatestVersionNumber")}
            for t in (lts if isinstance(lts, list) else [])
        ] or (lts if isinstance(lts, dict) else []),
        "vpcs": [
            {"id": v.get("VpcId"), "cidr": v.get("CidrBlock"), "is_default": v.get("IsDefault"),
             "state": v.get("State")}
            for v in (vpcs if isinstance(vpcs, list) else [])
        ] or (vpcs if isinstance(vpcs, dict) else []),
        "vpc_endpoints": [
            {"id": e.get("VpcEndpointId"), "service": e.get("ServiceName"), "type": e.get("VpcEndpointType"),
             "state": e.get("State"), "vpc": e.get("VpcId")}
            for e in (eps if isinstance(eps, list) else [])
        ] or (eps if isinstance(eps, dict) else []),
        "subnet_count": len(subnets) if isinstance(subnets, list) else subnets,
        # Containment invariant checks (Layer 2): Forensic detonation VPC must have NO IGW/NAT.
        "internet_gateways": len(igws) if isinstance(igws, list) else igws,
        "nat_gateways": len([n for n in nats if n.get("State") != "deleted"]) if isinstance(nats, list) else nats,
        "active_instances": inst_count,   # ephemeral detonation hosts are transient; usually 0 at rest
    }


def discover_kms(region: str) -> list:
    kms = ReadOnlyClient("kms", region)
    keys = _safe("kms.list", lambda: kms.paginate("list_keys", "Keys"))
    if isinstance(keys, dict):
        return [keys]
    out = []
    for k in keys:
        kid = k.get("KeyId")
        meta = _safe("kms.meta", lambda i=kid: kms.call("describe_key", KeyId=i).get("KeyMetadata", {}))
        if not isinstance(meta, dict):
            out.append({"key_id": kid, "_error": meta})
            continue
        # Skip AWS-managed keys (noise); report customer-managed only.
        if meta.get("KeyManager") == "AWS":
            continue
        aliases = _safe("kms.alias", lambda i=kid: kms.call("list_aliases", KeyId=i).get("Aliases", []))
        out.append({
            "key_id": kid,
            "aliases": [a.get("AliasName") for a in aliases] if isinstance(aliases, list) else aliases,
            "state": meta.get("KeyState"),               # Layer 2: Enabled?
            "usage": meta.get("KeyUsage"),               # SIGN_VERIFY vs ENCRYPT_DECRYPT
            "spec": meta.get("KeySpec"),
            "created": _iso(meta.get("CreationDate")),
        })
    return out


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _iso(v: Any) -> Any:
    if isinstance(v, _dt.datetime):
        return v.astimezone(_dt.timezone.utc).isoformat()
    return v


def _summarize_enc(enc: Any) -> Any:
    if isinstance(enc, dict) and "_error" in enc:
        return "none" if enc["_error"] == "ServerSideEncryptionConfigurationNotFoundError" else enc
    try:
        rules = enc["ServerSideEncryptionConfiguration"]["Rules"]
        algs = [r["ApplyServerSideEncryptionByDefault"]["SSEAlgorithm"] for r in rules]
        return ",".join(sorted(set(algs)))
    except Exception:  # noqa: BLE001
        return "unknown"


def _object_lock_mode(lock: Any) -> Any:
    if isinstance(lock, dict) and "_error" in lock:
        return "none"
    try:
        cfg = lock["ObjectLockConfiguration"]
        rule = cfg.get("Rule", {}).get("DefaultRetention", {})
        return {"enabled": cfg.get("ObjectLockEnabled"), "mode": rule.get("Mode"),
                "days": rule.get("Days"), "years": rule.get("Years")}
    except Exception:  # noqa: BLE001
        return "none"


# ---------------------------------------------------------------------------
# orchestration
# ---------------------------------------------------------------------------

_STEPS = [
    ("cloudformation", discover_cloudformation),
    ("lambda", discover_lambda),
    ("stepfunctions", discover_stepfunctions),
    ("dynamodb", discover_dynamodb),
    ("s3", discover_s3),
    ("apigateway", discover_apigateway),
    ("ec2", discover_ec2),
    ("kms", discover_kms),
]


def run(region: str, expect_account: str | None) -> dict:
    ident = whoami(region)
    print(f"# caller: {ident['account']} ({ident['account_name']})  {ident['arn']}", file=sys.stderr)
    if expect_account and ident["account"] != expect_account:
        raise SystemExit(
            f"REFUSING: caller account {ident['account']} != --expect-account {expect_account}. "
            "Wrong CloudShell tab? (run `aws sts get-caller-identity` to confirm)"
        )
    result: dict[str, Any] = {
        "meta": {
            "tool": "discover_env.py",
            "generated_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "region": region,
            "identity": ident,
            "read_only": True,
        },
        "resources": {},
    }
    for name, fn in _STEPS:
        print(f"# discovering {name} ...", file=sys.stderr)
        result["resources"][name] = _safe(name, lambda f=fn: f(region))
    return result


def summarize(result: dict) -> str:
    r = result["resources"]
    ident = result["meta"]["identity"]
    lines = []
    a = f'{ident["account"]} ({ident["account_name"]})'
    lines.append(f"================ ZTIE DISCOVERY: {a}  region={result['meta']['region']} ================")
    lines.append(f"generated_utc: {result['meta']['generated_utc']}   (READ-ONLY)")

    def n(x):
        return len(x) if isinstance(x, list) else "ERR"

    cf = r.get("cloudformation", [])
    lines.append(f"\nCloudFormation stacks: {n(cf)}")
    if isinstance(cf, list):
        for s in cf:
            flag = "" if str(s.get("status", "")).endswith("_COMPLETE") else "  <-- NOT COMPLETE"
            lines.append(f"  - {s['name']:<45} {s.get('status')}{flag}")

    lm = r.get("lambda", [])
    lines.append(f"\nLambda functions: {n(lm)}")
    if isinstance(lm, list):
        for f in lm:
            bed = " [BEDROCK-env]" if f.get("has_bedrock_env") else ""
            lines.append(f"  - {f['name']:<45} {f.get('runtime')}  mod={f.get('last_modified')}{bed}")

    sf = r.get("stepfunctions", [])
    lines.append(f"\nStep Functions: {n(sf)}")
    if isinstance(sf, list):
        for m in sf:
            lines.append(f"  - {m['name']:<45} {m.get('type')}/{m.get('status')}  last={m.get('last_execution')}")

    dy = r.get("dynamodb", [])
    lines.append(f"\nDynamoDB tables: {n(dy)}")
    if isinstance(dy, list):
        for t in dy:
            lines.append(f"  - {t['name']:<45} {t.get('status')}  items(live_count)={t.get('live_item_count')}  stream={t.get('stream')}")

    s3 = r.get("s3", [])
    lines.append(f"\nS3 buckets: {n(s3)}")
    if isinstance(s3, list):
        for b in s3:
            lock = b.get("object_lock")
            lockflag = ""
            if isinstance(lock, dict) and lock.get("mode") == "COMPLIANCE":
                lockflag = "  <-- COMPLIANCE WORM"
            lines.append(f"  - {b['name']:<45} region={b.get('region')} enc={b.get('encryption')} ver={b.get('versioning')}{lockflag}")

    ag = r.get("apigateway", {})
    if isinstance(ag, dict):
        rest = ag.get("rest_v1", [])
        http = ag.get("http_v2", [])
        lines.append(f"\nAPI Gateway REST(v1): {n(rest)}   HTTP(v2): {n(http)}")
        if isinstance(rest, list):
            for a1 in rest:
                lines.append(f"  - REST {a1.get('id')} {a1.get('name')}  stages={a1.get('stages')}  types={a1.get('endpoint_types')}")
        if isinstance(http, list):
            for a2 in http:
                lines.append(f"  - HTTP {a2.get('id')} {a2.get('name')}  {a2.get('protocol')}")

    ec2 = r.get("ec2", {})
    if isinstance(ec2, dict):
        lines.append("\nEC2 / network:")
        lines.append(f"  launch_templates : {n(ec2.get('launch_templates', []))}")
        lines.append(f"  vpcs             : {n(ec2.get('vpcs', []))}")
        lines.append(f"  vpc_endpoints    : {n(ec2.get('vpc_endpoints', []))}")
        lines.append(f"  internet_gateways: {ec2.get('internet_gateways')}   nat_gateways: {ec2.get('nat_gateways')}")
        lines.append(f"  active_instances : {ec2.get('active_instances')}")
        igw = ec2.get("internet_gateways")
        if isinstance(igw, int) and igw > 0 and ident["account"] == "360999005254":
            lines.append("  <-- NOTE: Forensic detonation containment expects NO internet gateway; investigate.")

    kms = r.get("kms", [])
    lines.append(f"\nKMS customer-managed keys: {n(kms)}")
    if isinstance(kms, list):
        for k in kms:
            lines.append(f"  - {k.get('key_id')}  {k.get('usage')}/{k.get('state')}  aliases={k.get('aliases')}")

    lines.append("\n================ END ================")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="ZTIE read-only environment discovery.")
    p.add_argument("--region", default="us-east-1")
    p.add_argument("--expect-account", default=None,
                   help="Refuse to run unless the caller account matches (wrong-tab guard). "
                        "e.g. 360999005254 (Forensic) or 641628980935 (Hub).")
    p.add_argument("--out", default=None, help="JSON artifact path (default: discovery-<acct>-<utc>.json)")
    p.add_argument("--summary-only", action="store_true", help="Print summary only, still writes JSON.")
    args = p.parse_args(argv)

    result = run(args.region, args.expect_account)
    acct = result["meta"]["identity"]["account"]
    stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = args.out or f"discovery-{acct}-{stamp}.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2, default=str)
    print(summarize(result))
    print(f"\n[artifact] wrote {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
