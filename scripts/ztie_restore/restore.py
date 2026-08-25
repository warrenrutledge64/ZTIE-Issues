"""Coordinated restore (Story 1.R).

Given a manifest, restore re-applies the pinned state, but ONLY after a deliberate
confirm that fails safe to NO (see :mod:`ztie_restore.confirm`). This is the ONLY
mutating path in the tool.

What restore re-applies (state half of the coordinated restore):

- **CloudFormation stacks** — re-deploys the pinned template + parameters +
  **stack-level tags**. Re-applying tags is not optional: a restore that only
  re-applied template + parameters would strip the stack's tags and then correctly
  fail the projected verify (tags are part of the CFN projection).
- **SSM parameters** — re-puts the captured desired value.

What restore does NOT do:

- It does not restore DynamoDB *items*, S3 *objects*, or any data content — it
  restores *configuration/desired-state*. Data-plane content is out of scope for a
  restore point (the manifest is a configuration baseline, not a data backup).
- It does not touch Forensic's ephemeral raw-payload/scratch — that is disposable
  and rebuilt, never restored.
- It does not re-run CDK. Restore re-applies the *captured template body* directly
  via CloudFormation so it is independent of the toolchain state.

The **code half** of the coordinated restore (git) is driven by the documented
procedure in ``RESTORE.md`` using the manifest's pinned ``governance_commit`` — the
two halves move as one unit (RD-015). Restore prints the pinned commit so the
operator reconciles code + state together.

Because the deployed ZTIE stacks are CDK-synthesised, the raw template body needed
to re-deploy is NOT in the manifest (the manifest stores only a hash, by design —
a projection, not the artifact). Restore therefore reads the template body from
the SAME source the capture pinned: the live stack's last-known-good template, or
an explicitly-supplied template file. This keeps the manifest a small projection
while still enabling a real re-apply. If neither is available, restore reports
exactly what the operator must supply rather than guessing.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import awsio
from .confirm import confirm
from .targets import AccountTarget
from .verify import verify_account


class RestoreAborted(RuntimeError):
    """Raised when the operator does not confirm the mutating restore."""


def _plan_summary(manifest: dict[str, Any], target: AccountTarget) -> list[str]:
    """Human-readable list of what the restore WOULD change for this account."""
    lines: list[str] = []
    stack_names = {s.stack_name for s in target.stacks}
    for p in manifest["resources"]:
        if p["type"] == "cloudformation_stack" and p["name"] in stack_names:
            lines.append(
                f"  - re-deploy CFN stack '{p['name']}' "
                f"(template sha256 {p['template_sha256'][:12]}…, "
                f"{len(p['parameters'])} params, {len(p['tags'])} tags)"
            )
        elif p["type"] == "ssm_parameter" and p["name"] in target.ssm_parameters:
            lines.append(f"  - put SSM parameter '{p['name']}' ({p['param_type']})")
    return lines


def restore_account(
    manifest: dict[str, Any],
    target: AccountTarget,
    *,
    template_bodies: dict[str, str] | None = None,
    confirm_fn=confirm,
    verify_after: bool = True,
) -> dict[str, Any]:
    """Coordinated restore for one account, behind the confirm gate.

    ``template_bodies`` maps stack_name -> raw template body (JSON/YAML text) for
    the CFN re-apply. If a stack's body is not supplied, restore records it as a
    manual step in the result rather than silently skipping.

    Returns a result dict: ``{"confirmed", "applied", "skipped", "verify"}``.
    Raises :class:`RestoreAborted` if the operator declines.
    """
    region = manifest["region"]

    # Guard: refuse to restore against the wrong account.
    ident = awsio.caller_identity(region)
    if ident["account"] != target.account_id:
        raise RuntimeError(
            f"refusing to restore: expected account {target.account_id} "
            f"({target.label}) but ambient credentials are account {ident['account']}."
        )

    plan = _plan_summary(manifest, target)
    banner = (
        f"\nZTIE COORDINATED RESTORE — account '{target.label}' ({target.account_id}), "
        f"region {region}\n"
        f"Manifest captured {manifest['captured_at_utc']} "
        f"(governance commit {manifest['governance_commit'].get('sha')}).\n"
        f"This WILL MUTATE live state. Planned changes:\n"
        + ("\n".join(plan) if plan else "  (nothing in scope for this account)")
    )
    print(banner)

    if not confirm_fn("Proceed with the coordinated restore?"):
        raise RestoreAborted("operator did not confirm — no changes made (fail-safe NO)")

    template_bodies = template_bodies or {}
    applied: list[str] = []
    skipped: list[str] = []
    stack_names = {s.stack_name for s in target.stacks}

    for p in manifest["resources"]:
        if p["type"] == "cloudformation_stack" and p["name"] in stack_names:
            body = template_bodies.get(p["name"])
            if body is None:
                skipped.append(
                    f"CFN stack '{p['name']}': no template body supplied "
                    f"(pass --template {p['name']}=<path> to re-deploy)"
                )
                continue
            awsio.restore_cfn_stack(
                name=p["name"],
                template_body=body,
                parameters=p["parameters"],
                tags=p["tags"],
                region=region,
            )
            applied.append(f"CFN stack '{p['name']}' (template + params + tags)")
        elif p["type"] == "ssm_parameter" and p["name"] in target.ssm_parameters:
            if p.get("secure") and p.get("value") is None:
                skipped.append(
                    f"SSM '{p['name']}': SecureString value was not captured; "
                    f"re-put manually"
                )
                continue
            awsio.restore_ssm_parameter(
                name=p["name"], type_=p["param_type"], value=p["value"], region=region
            )
            applied.append(f"SSM parameter '{p['name']}'")

    result: dict[str, Any] = {
        "confirmed": True,
        "applied": applied,
        "skipped": skipped,
        "verify": None,
    }
    if verify_after:
        result["verify"] = verify_account(manifest, target)
    return result


def load_template_bodies(pairs: list[str]) -> dict[str, str]:
    """Parse ``--template STACK=PATH`` pairs into {stack_name: body-text}."""
    out: dict[str, str] = {}
    for pair in pairs:
        if "=" not in pair:
            raise ValueError(f"--template expects STACK=PATH, got '{pair}'")
        stack, path = pair.split("=", 1)
        out[stack] = Path(path).read_text(encoding="utf-8")
    return out
