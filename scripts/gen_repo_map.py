#!/usr/bin/env python3
"""Generate an accurate structural map of a git repository.

This is a REUSABLE OS-layer tool (see docs/REPO_MAP_TEMPLATE.md). It produces a
Markdown structural map straight from the git tree, so the map can never drift
from the real directory names the way a hand-drawn diagram does.

Two layers, kept strictly separate in the output:

  * REPO FACTS  -- derived only from `git ls-tree`: real directory names, file
    counts, and the observed per-directory file layout. Never editorialized.
  * INTERPRETATION -- optional phase/role annotations supplied via a JSON config
    (--annotations). Every annotation is validated against a real directory; any
    annotation whose target does not exist is reported as a WARNING and never
    silently rendered, so a stale label surfaces immediately.

Design constraints (per this project's standing preferences):
  * Python, stdlib only -- runs in the offline INTEGRATIONS_ONLY sandbox.
  * Deterministic output (sorted), so re-running on the same commit is byte-stable
    and diffs are meaningful.
  * Repeatable: point it at any repo + optional annotations and re-run.

Usage:
    python3 scripts/gen_repo_map.py                      # map the current repo, facts only
    python3 scripts/gen_repo_map.py --annotations docs/repo-map.annotations.json
    python3 scripts/gen_repo_map.py --repo /path/to/repo --ref main -o MAP.md
    python3 scripts/gen_repo_map.py --check              # exit 3 if annotations are stale

Exit codes:
    0  success
    2  usage / git error
    3  --check requested and one or more annotations are stale (drift detected)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

# --------------------------------------------------------------------------- #
# git tree extraction (REPO FACTS)
# --------------------------------------------------------------------------- #


@dataclass
class Entry:
    """One object in the git tree."""

    kind: str  # "blob" or "tree"
    path: str


def _run_git(repo: Path, args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        sys.exit("error: git executable not found on PATH")
    except subprocess.CalledProcessError as exc:
        sys.exit(f"error: git {' '.join(args)} failed: {exc.stderr.strip()}")
    return result.stdout


def resolve_ref(repo: Path, ref: str) -> tuple[str, str]:
    """Return (short_sha, subject) for the given ref."""
    out = _run_git(repo, ["log", "-1", "--format=%h%x00%s", ref]).strip()
    short, _, subject = out.partition("\x00")
    return short, subject


def read_tree(repo: Path, ref: str) -> list[Entry]:
    """Return every tracked object under `ref` (recursive)."""
    raw = _run_git(repo, ["ls-tree", "-r", "-t", "--format=%(objecttype)%x09%(path)", ref])
    entries: list[Entry] = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        kind, _, path = line.partition("\t")
        if kind in ("blob", "tree"):
            entries.append(Entry(kind=kind, path=path))
    return entries


# --------------------------------------------------------------------------- #
# structural analysis (REPO FACTS)
# --------------------------------------------------------------------------- #


@dataclass
class DirNode:
    name: str
    file_count: int = 0
    subdir_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class RepoStructure:
    root_files: list[str]
    top_dirs: list[DirNode]
    total_entries: int


def analyze(entries: list[Entry]) -> RepoStructure:
    root_files: list[str] = []
    top_level_dirs: set[str] = set()
    # file count per top-level dir
    dir_file_count: dict[str, int] = defaultdict(int)
    # file count per (top-level dir, immediate subdir)
    subdir_file_count: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for e in entries:
        parts = e.path.split("/")
        if e.kind == "tree":
            if len(parts) == 1:
                top_level_dirs.add(parts[0])
            continue
        # blob
        if len(parts) == 1:
            root_files.append(parts[0])
            continue
        top = parts[0]
        dir_file_count[top] += 1
        if len(parts) >= 3:
            subdir_file_count[top][parts[1]] += 1

    nodes: list[DirNode] = []
    for name in sorted(top_level_dirs):
        nodes.append(
            DirNode(
                name=name,
                file_count=dir_file_count.get(name, 0),
                subdir_counts=dict(sorted(subdir_file_count.get(name, {}).items())),
            )
        )

    return RepoStructure(
        root_files=sorted(root_files),
        top_dirs=nodes,
        total_entries=len(entries),
    )


def dir_file_layout(entries: list[Entry], dir_path: str) -> list[str]:
    """Return the immediate files (basenames) directly inside `dir_path`."""
    prefix = dir_path.rstrip("/") + "/"
    files: list[str] = []
    for e in entries:
        if e.kind != "blob":
            continue
        if not e.path.startswith(prefix):
            continue
        rest = e.path[len(prefix) :]
        if "/" not in rest:
            files.append(rest)
    return sorted(files)


# --------------------------------------------------------------------------- #
# annotations (INTERPRETATION) -- validated, never trusted blindly
# --------------------------------------------------------------------------- #


@dataclass
class Annotations:
    title: str = ""
    intro: str = ""
    # path (relative, e.g. "lambdas/hub_ingest") -> role string
    roles: dict[str, str] = field(default_factory=dict)
    # optional grouping: group label -> ordered list of paths
    groups: list[dict] = field(default_factory=list)
    footer: str = ""


def load_annotations(path: Path) -> Annotations:
    data = json.loads(path.read_text(encoding="utf-8"))
    return Annotations(
        title=data.get("title", ""),
        intro=data.get("intro", ""),
        roles=data.get("roles", {}),
        groups=data.get("groups", []),
        footer=data.get("footer", ""),
    )


def validate_annotations(ann: Annotations, entries: list[Entry]) -> list[str]:
    """Return a list of warning strings for annotations that target no real dir/file."""
    real_paths = {e.path for e in entries}
    warnings: list[str] = []
    for p in ann.roles:
        if p not in real_paths:
            warnings.append(f"role annotation targets non-existent path: {p!r}")
    for g in ann.groups:
        for p in g.get("paths", []):
            if p not in real_paths:
                warnings.append(
                    f"group {g.get('label', '?')!r} references non-existent path: {p!r}"
                )
    return warnings


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #


def render(
    repo_name: str,
    ref: str,
    short_sha: str,
    subject: str,
    struct: RepoStructure,
    entries: list[Entry],
    ann: Annotations | None,
    warnings: list[str],
) -> str:
    lines: list[str] = []
    title = (ann.title if ann and ann.title else f"{repo_name} — Repository Structure Map")
    lines.append(f"# {title}")
    lines.append("")
    lines.append(
        "> **Generated by** `scripts/gen_repo_map.py` — re-run to refresh; do not hand-edit."
    )
    lines.append(
        f"> **Repo:** `{repo_name}` · **Ref:** `{ref}` @ `{short_sha}` · "
        f"**Entries:** {struct.total_entries}"
    )
    lines.append(f"> **Tip commit:** {subject}")
    lines.append("")
    lines.append(
        "> This map has two layers. **REPO FACTS** are derived only from the git tree "
        "(directory names, counts, file layouts) and are always accurate for the ref "
        "above. **INTERPRETATION** (phase/role labels) comes from an annotations file "
        "and reflects human framing, not repo structure."
    )
    lines.append("")

    if warnings:
        lines.append("> ⚠️ **Annotation drift detected** (labels not rendered):")
        for w in warnings:
            lines.append(f"> - {w}")
        lines.append("")

    if ann and ann.intro:
        lines.append(ann.intro)
        lines.append("")

    # ---- REPO FACTS: top-level layout ---------------------------------- #
    lines.append("## REPO FACTS — top-level layout")
    lines.append("")
    lines.append("```")
    lines.append(f"{repo_name}/")
    for f in struct.root_files:
        lines.append(f"├── {f}")
    for node in struct.top_dirs:
        plural = "file" if node.file_count == 1 else "files"
        lines.append(f"├── {node.name}/    ({node.file_count} {plural})")
    lines.append("```")
    lines.append("")

    # ---- REPO FACTS: per-directory breakdown --------------------------- #
    lines.append("## REPO FACTS — directory breakdown")
    lines.append("")
    for node in struct.top_dirs:
        plural = "file" if node.file_count == 1 else "files"
        lines.append(f"### `{node.name}/` — {node.file_count} {plural}")
        lines.append("")
        if node.subdir_counts:
            lines.append("| Subdirectory | Files | Role (interpretation) |")
            lines.append("|---|---|---|")
            for sub, count in node.subdir_counts.items():
                full = f"{node.name}/{sub}"
                role = ann.roles.get(full, "") if ann else ""
                lines.append(f"| `{sub}/` | {count} | {role} |")
            lines.append("")
        else:
            # leaf dir: show its immediate files
            files = dir_file_layout(entries, node.name)
            if files:
                lines.append("Files: " + ", ".join(f"`{f}`" for f in files))
                lines.append("")

    # ---- INTERPRETATION: grouped view ---------------------------------- #
    if ann and ann.groups:
        lines.append("## INTERPRETATION — grouped view")
        lines.append("")
        lines.append(
            "*The groupings and labels below are human framing, not directory "
            "structure. Every path is validated against the real tree above.*"
        )
        lines.append("")
        for g in ann.groups:
            lines.append(f"### {g.get('label', 'Group')}")
            if g.get("note"):
                lines.append("")
                lines.append(g["note"])
            lines.append("")
            for p in g.get("paths", []):
                role = ann.roles.get(p, "")
                suffix = f" — {role}" if role else ""
                lines.append(f"- `{p}`{suffix}")
            lines.append("")

    if ann and ann.footer:
        lines.append("---")
        lines.append("")
        lines.append(ann.footer)
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


# --------------------------------------------------------------------------- #
# cli
# --------------------------------------------------------------------------- #


def _repo_name(repo: Path) -> str:
    # `git config --get` exits non-zero when the key is unset (no origin remote),
    # which is normal for a fresh clone-less repo or a test fixture. Tolerate it
    # and fall back to the directory name rather than aborting.
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return repo.resolve().name
    url = result.stdout.strip() if result.returncode == 0 else ""
    if url:
        name = url.rstrip("/").rsplit("/", 1)[-1]
        return name.removesuffix(".git")
    return repo.resolve().name


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo", default=".", help="path to the git repo (default: cwd)")
    parser.add_argument("--ref", default="HEAD", help="git ref to read the tree from (default: HEAD)")
    parser.add_argument(
        "--ref-label",
        default=None,
        help="ref name shown in the map header (default: the --ref value). Use "
        "--ref HEAD --ref-label main to map the current tree but label it 'main'.",
    )
    parser.add_argument(
        "--annotations",
        default=None,
        help="path to a JSON annotations file (INTERPRETATION layer)",
    )
    parser.add_argument("-o", "--output", default=None, help="write map to this file (default: stdout)")
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit 3 if any annotation is stale (for CI/pre-commit drift detection)",
    )
    args = parser.parse_args(argv)

    repo = Path(args.repo)
    if not (repo / ".git").exists() and not repo.joinpath(".git").is_file():
        # allow worktrees / bare-adjacent; git itself will error clearly otherwise
        pass

    short_sha, subject = resolve_ref(repo, args.ref)
    entries = read_tree(repo, args.ref)
    struct = analyze(entries)
    repo_name = _repo_name(repo)

    ann: Annotations | None = None
    warnings: list[str] = []
    if args.annotations:
        ann = load_annotations(Path(args.annotations))
        warnings = validate_annotations(ann, entries)

    if args.check and warnings:
        for w in warnings:
            print(f"drift: {w}", file=sys.stderr)
        return 3

    ref_label = args.ref_label if args.ref_label else args.ref
    output = render(repo_name, ref_label, short_sha, subject, struct, entries, ann, warnings)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"wrote {args.output} ({struct.total_entries} entries, ref {args.ref}@{short_sha})")
        if warnings:
            print(f"  ⚠️ {len(warnings)} stale annotation(s) — see the map header", file=sys.stderr)
    else:
        sys.stdout.write(output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
