"""Manifest read/write + governance-commit pinning (Story 1.R).

A *manifest* is a single timestamped JSON file that captures, as one restorable
unit (RD-015):

- ``schema_version`` — the manifest projection shape version.
- ``captured_at_utc`` — ISO-8601 UTC timestamp of capture.
- ``region`` — the AWS region captured.
- ``governance_commit`` — the pinned known-good governance-doc git commit, so a
  restore returns **code + state + governance together**. Captured from the repo
  HEAD at capture time (with dirty-tree flagged).
- ``accounts`` — a map of ``account_label -> {account_id, caller_arn}`` recording
  which real AWS accounts were captured (so restore can refuse the wrong account).
- ``resources`` — the list of restore-relevant projections (see
  :mod:`ztie_restore.projection`).

The manifest is written under ``restore-manifests/`` with a name of the form
``manifest-<UTC-ISO>.json`` so multiple captures never collide and history is
auditable. A JSON Schema for the manifest itself lives alongside the tooling and
is emitted via ``json.dump`` (never string-written) because it carries a remote
``$schema`` URL, which the file-write path refuses.
"""

from __future__ import annotations

import datetime as _dt
import json
import subprocess
from pathlib import Path
from typing import Any

from . import MANIFEST_SCHEMA_VERSION

MANIFEST_DIR = "restore-manifests"


def utc_now_iso() -> str:
    """Return the current UTC time as a compact ISO-8601 string."""
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _filename_stamp() -> str:
    """A filesystem-safe UTC stamp for manifest filenames."""
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def governance_commit(repo_root: Path) -> dict[str, Any]:
    """Return the pinned governance-doc commit info from the repo (RD-015).

    Pins the current ``HEAD`` sha and flags whether the working tree is dirty, so
    a manifest captured from an uncommitted tree is honestly recorded as such.
    Failures (not a git repo) degrade gracefully to ``{"sha": None, ...}`` rather
    than aborting a capture.
    """
    def _git(*args: str) -> str | None:
        try:
            out = subprocess.run(
                ["git", *args],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=True,
            )
            return out.stdout.strip()
        except Exception:  # noqa: BLE001 — git absent / not a repo
            return None

    sha = _git("rev-parse", "HEAD")
    status = _git("status", "--porcelain")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    return {
        "sha": sha,
        "branch": branch,
        "dirty": bool(status),  # True if uncommitted changes exist
    }


def build_manifest(
    *,
    region: str,
    accounts: dict[str, dict[str, str]],
    resources: list[dict[str, Any]],
    repo_root: Path,
) -> dict[str, Any]:
    """Assemble a manifest dict from captured pieces."""
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "captured_at_utc": utc_now_iso(),
        "region": region,
        "governance_commit": governance_commit(repo_root),
        "accounts": accounts,
        "resources": resources,
    }


def manifest_path(repo_root: Path) -> Path:
    """Return the path a fresh manifest should be written to."""
    return repo_root / MANIFEST_DIR / f"manifest-{_filename_stamp()}.json"


def write_manifest(manifest: dict[str, Any], path: Path) -> Path:
    """Write a manifest to ``path`` as pretty JSON (creating parent dirs)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=False)
        fh.write("\n")
    return path


def read_manifest(path: Path) -> dict[str, Any]:
    """Read + minimally validate a manifest file."""
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    if "resources" not in data or "schema_version" not in data:
        raise ValueError(f"{path} is not a valid ZTIE restore manifest")
    return data
