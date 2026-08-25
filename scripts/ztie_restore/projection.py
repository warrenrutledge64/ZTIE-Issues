"""Restore-relevant projection model (Story 1.R).

This module defines the ONLY thing ZTIE restore reasons about: a *projection* of
each durable resource down to its **identity + desired-state fields**. It never
carries raw resource objects.

Why a projection and not the raw AWS describe output? Because a lot of what AWS
returns legitimately changes on any successful deploy/put and would false-positive
as "drift" in a naive diff:

- SSM ``Parameter.Version`` bumps on every ``put-parameter``; ``LastModifiedDate``
  moves every write.
- CloudFormation ``StackStatus`` is ``CREATE_COMPLETE`` the first time and
  ``UPDATE_COMPLETE`` after a restore; ``LastUpdatedTime`` moves; ``StackId``
  changes if a stack is deleted and recreated.
- Lambda / list APIs return items in an unstable order.
- DynamoDB / S3 return ARNs, creation dates, item/size counts, etc. that are not
  part of the desired state.

So for each resource type we capture a small, explicit set of fields and compare
ONLY those. The captured fields are the ones a restore actually re-establishes.

Field sets (the contract):

- **CloudFormation stack**: ``name`` (stack name — identity), ``template_sha256``
  (sha256 of the deployed template body), ``parameters`` (name->value map), and
  ``tags`` (name->value map). The template hash + parameters + tags are exactly
  what a coordinated ``aws cloudformation deploy --tags`` re-applies. Status,
  stack_id, timestamps are deliberately excluded.
- **DynamoDB table**: ``name`` (identity), ``billing_mode``,
  ``key_schema`` (ordered list of {name, key_type}), ``attribute_definitions``
  (sorted list of {name, type}), ``gsis`` (sorted list of {name, key_schema,
  projection_type}), ``sse`` (server-side-encryption type), ``pitr`` (bool). ARN,
  creation date, item count, table size, and status are excluded.
- **Lambda function**: ``name`` (identity), ``runtime``, ``handler``,
  ``code_sha256``. Last-modified, version, code size, ARN are excluded. The list
  of functions is sorted by name so ordering never causes drift.
- **S3 bucket (config)**: ``name`` (identity), ``versioning`` (Enabled/
  Suspended/Disabled), ``encryption`` (algorithm), ``public_access_block`` (the
  four booleans), ``bucket_key_enabled``. Creation date and object contents are
  excluded (this captures *configuration*, not data).
- **SSM parameter**: ``name`` (identity), ``type`` (String/StringList/
  SecureString), ``value`` (the desired value; a SecureString value is captured
  only if the operator explicitly opts in), ``secure`` (bool). Version and
  last-modified are excluded.

Everything here is pure data + comparison logic (no boto3), so it is unit-testable
without AWS and is the single source of truth both capture and verify agree on.
"""

from __future__ import annotations

import hashlib
from typing import Any


def sha256_hex(data: bytes) -> str:
    """Return the lowercase hex sha256 of ``data`` (used for template bodies)."""
    return hashlib.sha256(data).hexdigest()


# --------------------------------------------------------------------------- #
# Normalisation helpers — make a projection canonical + order-insensitive.
# --------------------------------------------------------------------------- #
def _canonical_map(m: dict[str, Any] | None) -> dict[str, Any]:
    """Return a key-sorted plain dict (None -> {})."""
    if not m:
        return {}
    return {k: m[k] for k in sorted(m)}


def _sorted_by(items: list[dict[str, Any]] | None, key: str) -> list[dict[str, Any]]:
    """Return ``items`` sorted by ``item[key]`` (None -> [])."""
    if not items:
        return []
    return sorted(items, key=lambda d: str(d.get(key, "")))


# --------------------------------------------------------------------------- #
# Per-resource projection builders. Each takes already-fetched, plain-dict input
# (so it stays boto3-free and testable) and returns the canonical projection.
# --------------------------------------------------------------------------- #
def cfn_stack_projection(
    *,
    name: str,
    template_body: str | bytes,
    parameters: dict[str, str] | None,
    tags: dict[str, str] | None,
) -> dict[str, Any]:
    """Projection of a CloudFormation stack: name + template hash + params + tags.

    The template body is hashed (not stored verbatim) so the manifest stays small
    and the comparison is exact. Tags are first-class here because a restore MUST
    re-apply stack-level tags (``aws cloudformation deploy --tags``) or the
    restored stack loses them and correctly fails verify.
    """
    body = template_body.encode("utf-8") if isinstance(template_body, str) else template_body
    return {
        "type": "cloudformation_stack",
        "name": name,
        "template_sha256": sha256_hex(body),
        "parameters": _canonical_map(parameters),
        "tags": _canonical_map(tags),
    }


def dynamodb_table_projection(
    *,
    name: str,
    billing_mode: str,
    key_schema: list[dict[str, str]],
    attribute_definitions: list[dict[str, str]],
    gsis: list[dict[str, Any]] | None,
    sse: str,
    pitr: bool,
) -> dict[str, Any]:
    """Projection of a DynamoDB table's desired configuration (not its items)."""
    return {
        "type": "dynamodb_table",
        "name": name,
        "billing_mode": billing_mode,
        # key_schema order is meaningful (HASH before RANGE) -> keep as-is.
        "key_schema": [
            {"name": k["name"], "key_type": k["key_type"]} for k in key_schema
        ],
        "attribute_definitions": _sorted_by(
            [{"name": a["name"], "type": a["type"]} for a in attribute_definitions],
            "name",
        ),
        "gsis": _sorted_by(
            [
                {
                    "name": g["name"],
                    "key_schema": [
                        {"name": k["name"], "key_type": k["key_type"]}
                        for k in g.get("key_schema", [])
                    ],
                    "projection_type": g.get("projection_type", ""),
                }
                for g in (gsis or [])
            ],
            "name",
        ),
        "sse": sse,
        "pitr": bool(pitr),
    }


def lambda_function_projection(
    *,
    name: str,
    runtime: str,
    handler: str,
    code_sha256: str,
) -> dict[str, Any]:
    """Projection of a Lambda function: name + runtime + handler + code hash."""
    return {
        "type": "lambda_function",
        "name": name,
        "runtime": runtime,
        "handler": handler,
        "code_sha256": code_sha256,
    }


def s3_bucket_projection(
    *,
    name: str,
    versioning: str,
    encryption: str,
    public_access_block: dict[str, bool],
    bucket_key_enabled: bool,
) -> dict[str, Any]:
    """Projection of an S3 bucket's configuration (not its objects)."""
    pab_keys = (
        "BlockPublicAcls",
        "IgnorePublicAcls",
        "BlockPublicPolicy",
        "RestrictPublicBuckets",
    )
    return {
        "type": "s3_bucket",
        "name": name,
        "versioning": versioning,
        "encryption": encryption,
        "public_access_block": {k: bool(public_access_block.get(k, False)) for k in pab_keys},
        "bucket_key_enabled": bool(bucket_key_enabled),
    }


def ssm_parameter_projection(
    *,
    name: str,
    type_: str,
    value: str | None,
    secure: bool,
) -> dict[str, Any]:
    """Projection of an SSM parameter: name + type + value + secure flag.

    ``value`` is the desired value the restore would put back. For a SecureString
    the value is only present if the operator explicitly opted in to capturing
    secure values; otherwise it is ``None`` and verify compares name/type/secure
    only (never silently treating a missing secret as drift).
    """
    return {
        "type": "ssm_parameter",
        "name": name,
        "param_type": type_,
        "value": value,
        "secure": bool(secure),
    }


# --------------------------------------------------------------------------- #
# Comparison — the verify contract.
# --------------------------------------------------------------------------- #
# The identity of a projection (what makes two projections "the same resource"):
_IDENTITY = ("type", "name")


def projection_identity(p: dict[str, Any]) -> tuple[str, str]:
    """Return the (type, name) identity of a projection entry."""
    return (str(p.get("type", "")), str(p.get("name", "")))


def _fields_to_compare(p: dict[str, Any], *, include_secure_values: bool) -> dict[str, Any]:
    """Return the comparable field subset of a projection.

    Volatile fields are already excluded at capture time (we only ever store the
    projection). The one runtime nuance: a SecureString SSM value that was not
    captured (``value is None``) is dropped from BOTH sides of the comparison so a
    deliberately-uncaptured secret never reads as drift.
    """
    fields = {k: v for k, v in p.items() if k not in _IDENTITY}
    if p.get("type") == "ssm_parameter" and p.get("secure") and not include_secure_values:
        fields.pop("value", None)
    return fields


def diff_projections(
    captured: list[dict[str, Any]],
    live: list[dict[str, Any]],
    *,
    include_secure_values: bool = False,
) -> dict[str, Any]:
    """Diff two lists of projections by identity, comparing only projected fields.

    Returns a structured report::

        {
          "match": bool,
          "missing":   [identity, ...],   # in captured, absent live (deleted)
          "unexpected":[identity, ...],   # in live, absent captured (added)
          "changed":   [{"identity", "field", "captured", "live"}, ...],
        }

    ``match`` is True iff there are no missing, unexpected, or changed entries.
    Ordering never matters — everything is keyed by identity, and list-valued
    fields inside a projection were already canonicalised at build time.
    """
    cap_by_id = {projection_identity(p): p for p in captured}
    live_by_id = {projection_identity(p): p for p in live}

    missing = sorted(set(cap_by_id) - set(live_by_id))
    unexpected = sorted(set(live_by_id) - set(cap_by_id))

    changed: list[dict[str, Any]] = []
    for ident in sorted(set(cap_by_id) & set(live_by_id)):
        cap_fields = _fields_to_compare(
            cap_by_id[ident], include_secure_values=include_secure_values
        )
        live_fields = _fields_to_compare(
            live_by_id[ident], include_secure_values=include_secure_values
        )
        for field in sorted(set(cap_fields) | set(live_fields)):
            if cap_fields.get(field) != live_fields.get(field):
                changed.append(
                    {
                        "identity": list(ident),
                        "field": field,
                        "captured": cap_fields.get(field),
                        "live": live_fields.get(field),
                    }
                )

    return {
        "match": not missing and not unexpected and not changed,
        "missing": [list(i) for i in missing],
        "unexpected": [list(i) for i in unexpected],
        "changed": changed,
    }
