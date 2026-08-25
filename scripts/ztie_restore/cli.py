"""ZTIE restore CLI (Story 1.R).

Three subcommands:

  capture  --account {hub|forensic} [--region us-east-1] [--include-secure-values]
      Read-only. Captures the account's restore-relevant projection to a fresh
      timestamped manifest under ``restore-manifests/`` and prints its path.

  verify   --account {hub|forensic} --manifest <path> [--include-secure-values]
      Read-only. Re-captures live and diffs against the manifest. Exit 0 iff the
      restore-relevant projection matches (no drift); exit 3 on drift.

  restore  --account {hub|forensic} --manifest <path>
           [--template STACK=PATH ...] [--no-verify]
      MUTATING, behind the ``input()`` confirm gate (fails safe to NO). Re-applies
      the pinned CFN template + parameters + tags and any SSM values, then verifies.

Ambient credentials (CloudShell). Region defaults to us-east-1. The account label
is checked against the ambient STS identity — the tool refuses to act on the wrong
account.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import capture as capture_mod
from . import manifest as manifest_mod
from . import restore as restore_mod
from . import verify as verify_mod
from .capture import AccountMismatch
from .restore import RestoreAborted
from .targets import resolve_account

# Repo root = two levels up from this file (scripts/ztie_restore/cli.py).
REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_REGION = "us-east-1"


def _print_diff(diff: dict[str, object]) -> None:
    print(json.dumps(diff, indent=2, sort_keys=True))


def cmd_capture(args: argparse.Namespace) -> int:
    target = resolve_account(args.account)
    try:
        m, path = capture_mod.capture_to_manifest(
            target,
            args.region,
            REPO_ROOT,
            include_secure_values=args.include_secure_values,
        )
    except AccountMismatch as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    rel = path.relative_to(REPO_ROOT)
    print(f"Captured {len(m['resources'])} projection(s) for account '{target.label}'.")
    print(f"Manifest written: {rel}")
    print(f"Governance commit pinned: {m['governance_commit'].get('sha')}")
    if m["governance_commit"].get("dirty"):
        print("  WARNING: working tree is dirty — commit before relying on this pin.")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    target = resolve_account(args.account)
    m = manifest_mod.read_manifest(Path(args.manifest))
    try:
        diff = verify_mod.verify_account(
            m, target, include_secure_values=args.include_secure_values
        )
    except AccountMismatch as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    _print_diff(diff)
    if diff["match"]:
        print("VERIFY: MATCH — live projection equals the manifest (no drift).")
        return 0
    print("VERIFY: DRIFT — live projection differs from the manifest (see report).")
    return 3


def cmd_restore(args: argparse.Namespace) -> int:
    target = resolve_account(args.account)
    m = manifest_mod.read_manifest(Path(args.manifest))
    template_bodies = restore_mod.load_template_bodies(args.template or [])
    try:
        result = restore_mod.restore_account(
            m,
            target,
            template_bodies=template_bodies,
            verify_after=not args.no_verify,
        )
    except RestoreAborted as e:
        print(f"RESTORE ABORTED: {e}")
        return 4
    for line in result["applied"]:
        print(f"  applied: {line}")
    for line in result["skipped"]:
        print(f"  SKIPPED: {line}")
    if result["verify"] is not None:
        _print_diff(result["verify"])
        if not result["verify"]["match"]:
            print("RESTORE: applied, but post-restore verify shows DRIFT.")
            return 3
        print("RESTORE: applied and post-restore verify MATCHES the manifest.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ztie-restore",
        description="ZTIE state-capture + coordinated-restore (Story 1.R).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    def add_common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument(
            "--account",
            required=True,
            help="account label to act on (hub | forensic)",
        )
        sp.add_argument(
            "--region", default=DEFAULT_REGION, help=f"AWS region (default {DEFAULT_REGION})"
        )
        sp.add_argument(
            "--include-secure-values",
            action="store_true",
            help="capture/compare SecureString SSM values (default: off)",
        )

    sp_cap = sub.add_parser("capture", help="read-only capture -> timestamped manifest")
    add_common(sp_cap)
    sp_cap.set_defaults(func=cmd_capture)

    sp_ver = sub.add_parser("verify", help="read-only diff of live vs a manifest")
    add_common(sp_ver)
    sp_ver.add_argument("--manifest", required=True, help="path to a manifest JSON")
    sp_ver.set_defaults(func=cmd_verify)

    sp_res = sub.add_parser("restore", help="coordinated restore (confirm-gated)")
    sp_res.add_argument("--account", required=True, help="account label (hub | forensic)")
    sp_res.add_argument("--region", default=DEFAULT_REGION)
    sp_res.add_argument("--manifest", required=True, help="path to a manifest JSON")
    sp_res.add_argument(
        "--template",
        action="append",
        metavar="STACK=PATH",
        help="template body to re-deploy for a stack (repeatable)",
    )
    sp_res.add_argument(
        "--no-verify",
        action="store_true",
        help="skip the post-restore verify (not recommended)",
    )
    sp_res.set_defaults(func=cmd_restore)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
