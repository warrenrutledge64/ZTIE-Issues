"""Read-only state capture (Story 1.R).

Given an account target, this:

1. Confirms the ambient credentials point at the EXPECTED account (fails loudly on
   a mismatch — you don't want to capture the wrong account into a manifest).
2. For each stack: captures the stack projection (template hash + parameters +
   tags), then resolves each declared logical id to its physical id via
   ``describe_stack_resources`` and captures that resource's projection.
3. Captures any declared SSM parameters.

Everything here is READ-ONLY. No AWS call in this module mutates anything.

The manifest can span multiple accounts (e.g. Hub + Forensic captured in two
CloudShell runs and merged, or captured one account at a time). Each capture run
records the STS identity it actually ran under, so a later restore can refuse to
run against the wrong account.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import awsio, manifest
from .targets import AccountTarget, StackTarget


class AccountMismatch(RuntimeError):
    """Raised when ambient credentials do not match the expected account."""


def _resolve_physical_id(stack_name: str, logical_id: str, region: str) -> str:
    """Resolve a CloudFormation logical id to its deployed physical id."""
    cfn = awsio._client("cloudformation", region)
    resources = cfn.describe_stack_resources(StackName=stack_name)["StackResources"]
    for r in resources:
        # CDK logical ids get a hash suffix; match by stable prefix.
        if r["LogicalResourceId"] == logical_id or r["LogicalResourceId"].startswith(
            logical_id
        ):
            return r["PhysicalResourceId"]
    raise KeyError(
        f"logical id '{logical_id}' not found in stack '{stack_name}'"
    )


def _capture_stack(stack: StackTarget, region: str, *, include_secure_values: bool) -> list[dict[str, Any]]:
    """Capture a stack projection + each of its declared resource projections."""
    out: list[dict[str, Any]] = [awsio.capture_cfn_stack(stack.stack_name, region)]
    for logical_id, kind in sorted(stack.resources.items()):
        physical_id = _resolve_physical_id(stack.stack_name, logical_id, region)
        if kind == "dynamodb":
            out.append(awsio.capture_dynamodb_table(physical_id, region))
        elif kind == "lambda":
            out.append(awsio.capture_lambda_function(physical_id, region))
        elif kind == "s3":
            out.append(awsio.capture_s3_bucket(physical_id, region))
        else:
            raise ValueError(f"unknown resource kind '{kind}' for {logical_id}")
    return out


def capture_account(
    target: AccountTarget,
    region: str,
    *,
    include_secure_values: bool = False,
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    """Capture one account. Returns (identity, resource-projections).

    Raises :class:`AccountMismatch` if the ambient credentials are not the
    account this target expects.
    """
    ident = awsio.caller_identity(region)
    if ident["account"] != target.account_id:
        raise AccountMismatch(
            f"expected account {target.account_id} ({target.label}) but ambient "
            f"credentials are account {ident['account']} ({ident['arn']}). "
            f"Run in the correct CloudShell / with the correct credentials."
        )

    resources: list[dict[str, Any]] = []
    for stack in target.stacks:
        resources.extend(
            _capture_stack(stack, region, include_secure_values=include_secure_values)
        )
    for param_name in target.ssm_parameters:
        resources.append(
            awsio.capture_ssm_parameter(
                param_name, region, include_secure_values=include_secure_values
            )
        )
    return ident, resources


def capture_to_manifest(
    target: AccountTarget,
    region: str,
    repo_root: Path,
    *,
    include_secure_values: bool = False,
) -> tuple[dict[str, Any], Path]:
    """Capture one account and write a fresh manifest. Returns (manifest, path)."""
    ident, resources = capture_account(
        target, region, include_secure_values=include_secure_values
    )
    m = manifest.build_manifest(
        region=region,
        accounts={
            target.label: {"account_id": ident["account"], "caller_arn": ident["arn"]}
        },
        resources=resources,
        repo_root=repo_root,
    )
    path = manifest.manifest_path(repo_root)
    manifest.write_manifest(m, path)
    return m, path
