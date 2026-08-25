"""Thin AWS access layer for ZTIE restore (Story 1.R).

All boto3 calls live here so the projection/diff logic stays pure and unit-
testable. Every function in this module is READ-ONLY except the ones in the
explicitly-named ``restore`` section, which are only ever reached from
:mod:`ztie_restore.restore` after the confirm gate.

Credentials are AMBIENT — this is designed to run in AWS CloudShell with the
account's own credentials (no ``--profile``, no assumed role). The operator
selects the account by running in the right CloudShell; the tool records which
account it actually captured (via STS ``GetCallerIdentity``) into the manifest so
a restore can refuse to run against the wrong account.

boto3 is not importable in the INTEGRATIONS_ONLY build sandbox (PyPI is blocked),
so it is imported lazily inside functions. The pure modules never import this one,
and this module never imports boto3 at module scope — importing
``ztie_restore.awsio`` must not fail where boto3 is absent.
"""

from __future__ import annotations

from typing import Any

from . import projection as proj


def _client(service: str, region: str):
    """Return a boto3 client (lazy import; ambient credentials)."""
    import boto3  # lazy import so the module loads without boto3 present

    return boto3.client(service, region_name=region)


def caller_identity(region: str) -> dict[str, str]:
    """Return {account, arn} for the ambient credentials (identity check)."""
    ident = _client("sts", region).get_caller_identity()
    return {"account": ident["Account"], "arn": ident["Arn"]}


# --------------------------------------------------------------------------- #
# READ-ONLY capture helpers — build projections from live resources.
# --------------------------------------------------------------------------- #
def capture_cfn_stack(name: str, region: str) -> dict[str, Any]:
    """Read a CloudFormation stack -> projection (template hash + params + tags)."""
    cfn = _client("cloudformation", region)
    desc = cfn.describe_stacks(StackName=name)["Stacks"][0]
    template_body = cfn.get_template(StackName=name, TemplateStage="Original")[
        "TemplateBody"
    ]
    # get_template may return a dict (parsed) or a raw string; canonicalise to text.
    if not isinstance(template_body, str):
        import json

        template_body = json.dumps(template_body, sort_keys=True, separators=(",", ":"))
    parameters = {
        p["ParameterKey"]: p.get("ParameterValue", "")
        for p in desc.get("Parameters", [])
    }
    tags = {t["Key"]: t["Value"] for t in desc.get("Tags", [])}
    return proj.cfn_stack_projection(
        name=name, template_body=template_body, parameters=parameters, tags=tags
    )


def capture_dynamodb_table(name: str, region: str) -> dict[str, Any]:
    """Read a DynamoDB table -> configuration projection."""
    ddb = _client("dynamodb", region)
    t = ddb.describe_table(TableName=name)["Table"]

    billing = t.get("BillingModeSummary", {}).get("BillingMode")
    if not billing:
        # A provisioned table without a summary; infer from throughput presence.
        billing = "PROVISIONED" if t.get("ProvisionedThroughput", {}).get(
            "ReadCapacityUnits"
        ) else "PAY_PER_REQUEST"

    sse = t.get("SSEDescription", {}).get("SSEType") or "AWS_MANAGED_DEFAULT"

    pitr = False
    try:
        cont = ddb.describe_continuous_backups(TableName=name)
        pitr = (
            cont["ContinuousBackupsDescription"]["PointInTimeRecoveryDescription"][
                "PointInTimeRecoveryStatus"
            ]
            == "ENABLED"
        )
    except Exception:  # noqa: BLE001 — PITR describe is best-effort
        pitr = False

    gsis = [
        {
            "name": g["IndexName"],
            "key_schema": [
                {"name": k["AttributeName"], "key_type": k["KeyType"]}
                for k in g["KeySchema"]
            ],
            "projection_type": g.get("Projection", {}).get("ProjectionType", ""),
        }
        for g in t.get("GlobalSecondaryIndexes", [])
    ]

    return proj.dynamodb_table_projection(
        name=name,
        billing_mode=billing,
        key_schema=[
            {"name": k["AttributeName"], "key_type": k["KeyType"]}
            for k in t["KeySchema"]
        ],
        attribute_definitions=[
            {"name": a["AttributeName"], "type": a["AttributeType"]}
            for a in t["AttributeDefinitions"]
        ],
        gsis=gsis,
        sse=sse,
        pitr=pitr,
    )


def capture_lambda_function(name: str, region: str) -> dict[str, Any]:
    """Read a Lambda function -> projection (runtime + handler + code hash)."""
    lam = _client("lambda", region)
    cfg = lam.get_function_configuration(FunctionName=name)
    return proj.lambda_function_projection(
        name=cfg["FunctionName"],
        runtime=cfg.get("Runtime", ""),
        handler=cfg.get("Handler", ""),
        code_sha256=cfg.get("CodeSha256", ""),
    )


def capture_s3_bucket(name: str, region: str) -> dict[str, Any]:
    """Read an S3 bucket's configuration -> projection (not its objects)."""
    s3 = _client("s3", region)

    versioning = s3.get_bucket_versioning(Bucket=name).get("Status", "Disabled")

    enc_algo = "NONE"
    bucket_key = False
    try:
        rules = s3.get_bucket_encryption(Bucket=name)[
            "ServerSideEncryptionConfiguration"
        ]["Rules"]
        if rules:
            default = rules[0].get("ApplyServerSideEncryptionByDefault", {})
            enc_algo = default.get("SSEAlgorithm", "NONE")
            bucket_key = bool(rules[0].get("BucketKeyEnabled", False))
    except Exception:  # noqa: BLE001 — no encryption configured
        enc_algo = "NONE"

    pab: dict[str, bool] = {}
    try:
        pab = s3.get_public_access_block(Bucket=name)["PublicAccessBlockConfiguration"]
    except Exception:  # noqa: BLE001 — no PAB set
        pab = {}

    return proj.s3_bucket_projection(
        name=name,
        versioning=versioning,
        encryption=enc_algo,
        public_access_block=pab,
        bucket_key_enabled=bucket_key,
    )


def capture_ssm_parameter(
    name: str, region: str, *, include_secure_values: bool
) -> dict[str, Any]:
    """Read an SSM parameter -> projection. SecureString value only if opted-in."""
    ssm = _client("ssm", region)
    # describe gives type without decrypting; get_parameter gives the value.
    meta = ssm.describe_parameters(
        ParameterFilters=[{"Key": "Name", "Values": [name]}]
    )["Parameters"]
    param_type = meta[0]["Type"] if meta else "String"
    secure = param_type == "SecureString"

    value: str | None = None
    if not secure or include_secure_values:
        got = ssm.get_parameter(Name=name, WithDecryption=include_secure_values)
        value = got["Parameter"]["Value"]

    return proj.ssm_parameter_projection(
        name=name, type_=param_type, value=value, secure=secure
    )


# --------------------------------------------------------------------------- #
# RESTORE (MUTATING) helpers — only reached after the confirm gate.
# --------------------------------------------------------------------------- #
def restore_cfn_stack(
    name: str,
    template_body: str,
    parameters: dict[str, str],
    tags: dict[str, str],
    region: str,
) -> None:
    """Re-apply a CloudFormation stack: template + parameters + **tags**.

    Tags are re-applied explicitly (the equivalent of ``aws cloudformation deploy
    --tags``) — a restore that only re-applies template + parameters would strip
    the stack's tags and correctly fail the projected verify.
    """
    cfn = _client("cloudformation", region)
    param_list = [
        {"ParameterKey": k, "ParameterValue": v} for k, v in sorted(parameters.items())
    ]
    tag_list = [{"Key": k, "Value": v} for k, v in sorted(tags.items())]
    cfn.update_stack(
        StackName=name,
        TemplateBody=template_body,
        Parameters=param_list,
        Tags=tag_list,
        Capabilities=["CAPABILITY_NAMED_IAM", "CAPABILITY_AUTO_EXPAND"],
    )
    cfn.get_waiter("stack_update_complete").wait(StackName=name)


def restore_ssm_parameter(
    name: str, type_: str, value: str, region: str
) -> None:
    """Re-put an SSM parameter to its captured desired value (overwrite)."""
    ssm = _client("ssm", region)
    ssm.put_parameter(Name=name, Type=type_, Value=value, Overwrite=True)
