"""Verify live state against a manifest (Story 1.R).

Verify re-captures the CURRENT live projection for the account being checked and
diffs it against the manifest's stored projections, using
:func:`ztie_restore.projection.diff_projections`. Because both sides are
projections (identity + desired-state fields only), volatile metadata that
legitimately changes on any successful deploy/put — SSM version bumps, CFN
CREATE-vs-UPDATE status, ``last_updated_utc``, ``stack_id`` on recreate, Lambda
list ordering — never produces false-positive drift.

Verify is READ-ONLY. It answers one question: does live match the manifest?

Scoping: a manifest may span more than one account. Verify runs per-account (in
the matching CloudShell), so the manifest side is restricted to the resources this
account's target declares — computed from the target, not guessed. That way a
Hub-only verify does not report Forensic resources as "missing", while a resource
this account owns but that has been deleted still correctly reports as missing.
"""

from __future__ import annotations

from typing import Any

from . import awsio, projection
from .capture import AccountMismatch, capture_account
from .targets import AccountTarget


def scoped_identities(target: AccountTarget) -> set[tuple[str, str]]:
    """The set of projection identities this account target is responsible for.

    Built from the target declaration: each stack contributes a
    ``("cloudformation_stack", stack_name)`` identity, and each declared SSM
    parameter contributes an ``("ssm_parameter", name)`` identity. Per-resource
    identities (table/bucket/function) use CDK-generated physical names not known
    until run time, so those are matched by re-capturing live and keying on the
    live identities (a live resource that vanished shows up as ``missing`` via the
    stack projection changing, and the stack identity is always in scope).
    """
    idents: set[tuple[str, str]] = set()
    for stack in target.stacks:
        idents.add(("cloudformation_stack", stack.stack_name))
    for param in target.ssm_parameters:
        idents.add(("ssm_parameter", param))
    return idents


def verify_account(
    manifest: dict[str, Any],
    target: AccountTarget,
    *,
    include_secure_values: bool = False,
) -> dict[str, Any]:
    """Re-capture ``target`` live and diff against the manifest's projections."""
    region = manifest["region"]

    # Guard: refuse to verify against the wrong account.
    ident = awsio.caller_identity(region)
    if ident["account"] != target.account_id:
        raise AccountMismatch(
            f"expected account {target.account_id} ({target.label}) but ambient "
            f"credentials are account {ident['account']}."
        )

    _ident, live = capture_account(
        target, region, include_secure_values=include_secure_values
    )

    # Scope the manifest side to this account: the target's declared stack/SSM
    # identities plus any identity that appears live (per-resource physical ids).
    scope = scoped_identities(target)
    live_ids = {projection.projection_identity(p) for p in live}
    captured_scope = [
        p
        for p in manifest["resources"]
        if projection.projection_identity(p) in scope
        or projection.projection_identity(p) in live_ids
    ]

    return projection.diff_projections(
        captured_scope, live, include_secure_values=include_secure_values
    )
