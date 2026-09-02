#!/usr/bin/env python3
"""Governance-doc consistency checker for ZTIE (Story G-3, RD-023).

This checker machine-enforces the two hard-pause rules Story G-3 installs, by
parsing ``RUNBOOK.md`` (the repo's source of truth for story status). It is
Python 3.12 stdlib only (argparse, re, sys, pathlib) so it runs offline with no
PyPI dependency, and it is covered by ``scripts/test_check_docs.py`` (unittest).

It parses two things out of RUNBOOK.md:

  1. The **Validation Debt Register** -- the set of story IDs recorded as open
     validation debt (built but not live-validated). The register is the pipe
     table under the "Validation Debt Register" heading, shaped
     ``| Story | Why not done | Single action to clear | Owner |``.
  2. Every **story table** -- the per-phase and cross-cutting tables shaped
     ``| Story | Title | Depends on | Status | Completed | Restore tag |`` -- to
     get each story's ID and its status emoji (one of the legend markers
     ``⬜`` not started, ``🟡`` in progress, ``⛔`` blocked, ``✅`` done).

Status-cell text may carry an em dash or other formatting; the emoji is detected
by scanning the cell for a legend marker, so cells that also contain the em dash
convention used elsewhere in the repo do not break parsing.

CHECK A -- register completeness
    FAIL if any story whose RUNBOOK status is ``🟡`` or ``⛔`` (``⛔`` is treated
    the same as ``🟡`` for the register) is ABSENT from the Validation Debt
    Register. Cross-cutting / governance stories (IDs starting with ``G-``) are
    EXEMPT: the register tracks built-but-unvalidated FEATURE / floor work, not
    the governance/tooling story that installs the gate itself, so G-3 (which is
    ``🟡`` while it builds this very checker) does not have to register itself.
    The checker reads the committed tree as-is; a feature story that is
    legitimately mid-build inside an uncommitted session is tolerated because the
    checker runs on the committed tree, not on scratch edits.

CHECK B -- advancement gate (no new feature work while debt is open)
    FAIL if a NEW feature story is marked started (``🟡``) or done (``✅``) while
    the register is NON-EMPTY, EXCEPT:
      (i)   stories already IN the register (reworking or validating an open
            ``🟡`` / ``⛔`` entry to clear it is how debt is cleared, so it is
            explicitly allowed);
      (ii)  cross-cutting / governance stories (IDs starting with ``G-``); and
      (iii) the established completed baseline -- the set of feature story IDs
            that were already ``🟡`` / ``✅`` in the committed tree before the
            gate was installed.

    The gate is about NEW work: every current non-register ``🟡`` / ``✅``
    feature story (the 1.x set and 2.1) was validated / completed BEFORE G-3
    installed the gate, so the checker must not retroactively flag them. The
    practical, testable proxy: treat the baseline (the committed-tree set of
    ``🟡`` / ``✅`` feature story IDs) as pre-gate, and FAIL only when a feature
    story that is NOT in that baseline and NOT in the register appears as started
    ``🟡`` / done ``✅`` while the register is non-empty. On the clean tree that
    set is empty, so CHECK B passes; an injected new started feature story that
    was ``⬜`` in the baseline trips it.

    The baseline is read from the committed tree (``git show HEAD:RUNBOOK.md``)
    relative to the working-tree RUNBOOK; when the committed file cannot be read
    (e.g. a fresh fixture tree with no git history) the working tree is used as
    its own baseline, which keeps a clean checkout passing.

NOTE (G-2 overlap): Story G-2 (RD-015) owns a broader ``check_docs.py`` remit
(plan/runbook divergence, dangling RD refs, stray placeholders, ``✅`` without a
validation line). Those are deliberately OUT of scope here -- this file
implements only the two G-3 rules and G-2 extends it later.

Exit status: 0 when there are no violations, 1 when any violation is found.

Usage:
    check_docs.py [--repo-root PATH]

``--repo-root`` points the checker at an alternate tree (used by the unittest
fixtures); without it the repo root is located relative to this file.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Status legend markers used repo-wide in RUNBOOK.md.
NOT_STARTED = "\u2b1c"  # white large square
IN_PROGRESS = "\U0001f7e1"  # yellow circle
BLOCKED = "\u26d4"  # no-entry
DONE = "\u2705"  # check mark
STATUS_MARKERS = (NOT_STARTED, IN_PROGRESS, BLOCKED, DONE)

# Statuses that count as open validation debt (must appear in the register).
OPEN_DEBT_STATUSES = (IN_PROGRESS, BLOCKED)
# Statuses that count as "started or done" for the advancement gate.
STARTED_OR_DONE_STATUSES = (IN_PROGRESS, DONE)

# A story ID like 1.1, 1.1R, 2.0, G-3. Anchored so table separator rows and
# prose cells are not mistaken for IDs.
STORY_ID_RE = re.compile(r"^[0-9]+\.[0-9]+[A-Za-z]?$|^G-[0-9]+$")

# Header cells that identify a per-phase / cross-cutting story table. The story
# tables all start with these four columns.
STORY_TABLE_HEADER = ("story", "title", "depends on", "status")
# Header cells that identify the Validation Debt Register table.
REGISTER_TABLE_HEADER = ("story", "why not done")


@dataclass(frozen=True)
class Violation:
    """One machine-detected governance-doc inconsistency."""

    check: str
    file: str
    story_id: str
    detail: str

    def render(self) -> str:
        return f"[{self.check}] {self.file}: story {self.story_id}: {self.detail}"


def _split_row(line: str) -> list[str]:
    """Split a markdown pipe-table row into stripped cell strings.

    Tolerates leading / trailing pipes and cells that contain the em dash
    convention used elsewhere in the repo (the em dash is left inside the cell,
    never used as a delimiter).
    """
    stripped = line.strip()
    stripped = stripped.removeprefix("|")
    stripped = stripped.removesuffix("|")
    return [cell.strip() for cell in stripped.split("|")]


def _is_separator_row(cells: list[str]) -> bool:
    """True for a markdown header separator row like ``|---|---|``."""
    return all(cell and set(cell) <= {"-", ":"} for cell in cells)


def _header_matches(cells: list[str], expected: tuple[str, ...]) -> bool:
    """True if the leading header cells match ``expected`` (case-insensitive)."""
    lowered = [cell.lower() for cell in cells]
    return len(lowered) >= len(expected) and lowered[: len(expected)] == list(expected)


def _clean_id(cell: str) -> str:
    """Strip markdown emphasis / links from a first-column story-ID cell."""
    text = cell.strip()
    text = text.replace("*", "").replace("`", "")
    link = re.match(r"^\[([^\]]+)\]", text)
    if link:
        text = link.group(1)
    return text.strip()


def _status_marker(cell: str) -> str | None:
    """Return the legend marker found in a status cell, or None."""
    for marker in STATUS_MARKERS:
        if marker in cell:
            return marker
    return None


def parse_register(text: str) -> set[str]:
    """Return the set of story IDs recorded in the Validation Debt Register."""
    registered: set[str] = set()
    in_table = False
    for line in text.splitlines():
        if "|" not in line:
            if in_table:
                break
            continue
        cells = _split_row(line)
        if _header_matches(cells, REGISTER_TABLE_HEADER):
            in_table = True
            continue
        if not in_table:
            continue
        if _is_separator_row(cells):
            continue
        story_id = _clean_id(cells[0])
        if STORY_ID_RE.match(story_id):
            registered.add(story_id)
    return registered


def parse_story_statuses(text: str) -> dict[str, str]:
    """Return a mapping of story ID -> status marker from all story tables.

    Only tables whose header starts with ``Story | Title | Depends on | Status``
    are read, so the Progress Summary (phase rows), the story state-machine
    table, and the register itself are not mistaken for story tables.
    """
    statuses: dict[str, str] = {}
    in_table = False
    status_index = 0
    for line in text.splitlines():
        if "|" not in line:
            in_table = False
            continue
        cells = _split_row(line)
        if _header_matches(cells, STORY_TABLE_HEADER):
            in_table = True
            status_index = [cell.lower() for cell in cells].index("status")
            continue
        if not in_table:
            continue
        if _is_separator_row(cells):
            continue
        if len(cells) <= status_index:
            continue
        story_id = _clean_id(cells[0])
        if not STORY_ID_RE.match(story_id):
            continue
        marker = _status_marker(cells[status_index])
        if marker is not None:
            statuses[story_id] = marker
    return statuses


def _is_governance(story_id: str) -> bool:
    """True for a cross-cutting / governance story (exempt from both checks)."""
    return story_id.startswith("G-")


def committed_runbook_text(runbook_path: Path) -> str | None:
    """Return the committed (HEAD) RUNBOOK.md text, or None if unavailable.

    Used to derive the pre-gate baseline for CHECK B. Runs ``git show`` scoped to
    the file's repository; any failure (no git, no history, detached fixture
    tree) returns None so the caller falls back to the working tree.
    """
    repo_dir = runbook_path.resolve().parent
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_dir), "show", f"HEAD:{runbook_path.name}"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, ValueError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def check_a_register_completeness(
    statuses: dict[str, str],
    registered: set[str],
    runbook_name: str,
) -> list[Violation]:
    """CHECK A: every open-debt feature story must be in the register."""
    violations: list[Violation] = []
    for story_id, marker in sorted(statuses.items()):
        if marker not in OPEN_DEBT_STATUSES:
            continue
        if _is_governance(story_id):
            continue  # governance/tooling story installing the gate is exempt
        if story_id not in registered:
            violations.append(
                Violation(
                    check="CHECK A",
                    file=runbook_name,
                    story_id=story_id,
                    detail=(
                        "open-debt story (status is in-progress/blocked) is "
                        "missing from the Validation Debt Register"
                    ),
                )
            )
    return violations


def check_b_advancement_gate(
    statuses: dict[str, str],
    registered: set[str],
    baseline: dict[str, str],
    runbook_name: str,
) -> list[Violation]:
    """CHECK B: no NEW feature story may start/complete while debt is open."""
    violations: list[Violation] = []
    if not registered:
        return violations  # register empty -> the advancement gate is not armed
    # The pre-gate baseline: feature story IDs already started/done at HEAD.
    baseline_started = {
        story_id
        for story_id, marker in baseline.items()
        if marker in STARTED_OR_DONE_STATUSES and not _is_governance(story_id)
    }
    for story_id, marker in sorted(statuses.items()):
        if marker not in STARTED_OR_DONE_STATUSES:
            continue
        if _is_governance(story_id):
            continue  # governance stories are not gated
        if story_id in registered:
            continue  # reworking/validating an open entry is how debt clears
        if story_id in baseline_started:
            continue  # already started/done before the gate existed
        violations.append(
            Violation(
                check="CHECK B",
                file=runbook_name,
                story_id=story_id,
                detail=(
                    "new feature story marked started/done while the Validation "
                    "Debt Register is non-empty"
                ),
            )
        )
    return violations


def run_checks(repo_root: Path) -> list[Violation]:
    """Parse RUNBOOK.md under ``repo_root`` and run CHECK A and CHECK B."""
    runbook_path = repo_root / "RUNBOOK.md"
    text = runbook_path.read_text(encoding="utf-8")
    registered = parse_register(text)
    statuses = parse_story_statuses(text)

    committed = committed_runbook_text(runbook_path)
    baseline = parse_story_statuses(committed) if committed is not None else statuses

    violations: list[Violation] = []
    violations.extend(
        check_a_register_completeness(statuses, registered, runbook_path.name)
    )
    violations.extend(
        check_b_advancement_gate(statuses, registered, baseline, runbook_path.name)
    )
    return violations


def default_repo_root() -> Path:
    """Locate the repo root relative to this file (scripts/ is under root)."""
    return Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Enforce the Story G-3 hard-pause rules against RUNBOOK.md: every "
            "open-debt story is registered (CHECK A) and no new feature story "
            "starts while debt is open (CHECK B)."
        )
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="repo root to check (defaults to the tree this script lives in)",
    )
    args = parser.parse_args(argv)
    repo_root = args.repo_root if args.repo_root is not None else default_repo_root()

    violations = run_checks(repo_root)
    if violations:
        print(f"check_docs: FAIL -- {len(violations)} violation(s):")
        for violation in violations:
            print(f"  {violation.render()}")
        return 1
    print("check_docs: PASS -- register complete and advancement gate satisfied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
