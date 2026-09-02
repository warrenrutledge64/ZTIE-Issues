#!/usr/bin/env python3
"""Stdlib unittest suite for scripts/check_docs.py (Story G-3, RD-023).

Runs offline with no PyPI dependency. Each test copies the real RUNBOOK.md into a
tempfile.TemporaryDirectory, optionally mutates the copy (and, where the CHECK B
pre-gate baseline matters, seeds a git commit of the clean copy so HEAD is the
baseline), then invokes the checker against that fixture tree via ``--repo-root``.

Coverage:
  * clean tree PASSES (exit 0, zero violations);
  * an injected un-registered in-progress story fires CHECK A (non-zero exit);
  * an injected new feature story marked done while debt is open fires CHECK B
    (non-zero exit).
The two failure fixtures are designed so CHECK A and CHECK B each fire in
isolation, proving both rules independently.

Run:  python -m unittest scripts.test_check_docs
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_docs

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNBOOK = REPO_ROOT / "RUNBOOK.md"

# Status markers reused from the checker so the tests stay in lockstep with it.
IN_PROGRESS = check_docs.IN_PROGRESS
DONE = check_docs.DONE
NOT_STARTED = check_docs.NOT_STARTED


def _copy_clean_tree(dest: Path) -> Path:
    """Copy RUNBOOK.md into ``dest`` and return the copied file path."""
    dest.mkdir(parents=True, exist_ok=True)
    target = dest / "RUNBOOK.md"
    shutil.copyfile(RUNBOOK, target)
    return target


def _git_commit_baseline(repo_dir: Path) -> None:
    """Init a git repo in ``repo_dir`` and commit the current RUNBOOK.md.

    This makes HEAD the CHECK B pre-gate baseline so a subsequent working-tree
    mutation is seen as NEW work rather than folded into the baseline.
    """
    commands = (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "test"],
        ["git", "add", "RUNBOOK.md"],
        ["git", "commit", "-q", "-m", "baseline"],
    )
    for command in commands:
        subprocess.run(command, check=True, cwd=repo_dir, capture_output=True, text=True)


def _seed_open_debt(runbook_path: Path, story_id: str = "2.0") -> None:
    """Seed a non-empty Validation Debt Register in the copied RUNBOOK.

    On the real tree the register is EMPTY (Story 2.0's debt was cleared), and
    CHECK B early-returns when the register is empty, so the advancement gate is
    disarmed and cannot fire. This helper arms the gate for the CHECK B fixture by
    replacing the register's ``_(empty)_`` placeholder row with a plausible
    open-debt entry, without touching the master story table or any status cell.
    The seeded story (default 2.0) is deliberately an already-open baseline story
    so it does not itself trip CHECK B; it only makes the register non-empty.
    """
    text = runbook_path.read_text(encoding="utf-8")
    placeholder = "| _(empty)_ | — | — | — |"
    assert placeholder in text, "register placeholder row not found in fixture"
    seeded = f"| {story_id} | awaiting recorded live validation | run the live validation | executor |"
    runbook_path.write_text(text.replace(placeholder, seeded, 1), encoding="utf-8")


def _set_2_2_status(runbook_path: Path, new_marker: str) -> None:
    """Flip the master-table story 2.2 status cell to ``new_marker`` in place.

    In the reshaped master table every row leads with a ``Build tier`` column, so
    the 2.2 row now begins ``| 4 | [2.2](...) | ...``. The row is located by its
    Story cell (the second pipe-delimited cell, which carries the ``2.2`` ID even
    when it is wrapped in a markdown link) rather than by a fixed prefix.
    """
    text = runbook_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if not line.lstrip().startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        story_cell = cells[1]
        # Unwrap a markdown link like ``[2.2](...)`` down to the bare ID.
        link = re.match(r"^\[([^\]]+)\]", story_cell)
        story_id = link.group(1) if link else story_cell
        if story_id == "2.2":
            lines[index] = line.replace(NOT_STARTED, new_marker, 1)
            break
    else:  # pragma: no cover - guards against a fixture drifting from the doc
        raise AssertionError("could not locate the master-table story 2.2 row")
    runbook_path.write_text("".join(lines), encoding="utf-8")


class CheckDocsTests(unittest.TestCase):
    def test_clean_tree_passes(self) -> None:
        """The real, unmodified tree passes: exit 0, no violations."""
        violations = check_docs.run_checks(REPO_ROOT)
        self.assertEqual(violations, [], "clean tree should have no violations")
        self.assertEqual(check_docs.main(["--repo-root", str(REPO_ROOT)]), 0)

    def test_unregistered_in_progress_fires_check_a(self) -> None:
        """CHECK A fires when a 🟡 feature story is missing from the register.

        No git baseline is seeded, so the working tree is its own CHECK B
        baseline (2.2 is 🟡 in it) -- that keeps CHECK B quiet and isolates
        CHECK A on this fixture.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runbook = _copy_clean_tree(root)
            _set_2_2_status(runbook, IN_PROGRESS)  # 2.2 ⬜ -> 🟡, NOT registered

            violations = check_docs.run_checks(root)
            checks = {v.check for v in violations}
            self.assertIn("CHECK A", checks, "un-registered 🟡 must fire CHECK A")
            self.assertNotIn("CHECK B", checks, "CHECK B should stay isolated here")
            self.assertTrue(any(v.story_id == "2.2" for v in violations))
            self.assertEqual(check_docs.main(["--repo-root", str(root)]), 1)

    def test_new_feature_started_while_debt_open_fires_check_b(self) -> None:
        """CHECK B fires for a new feature story completed while debt is open.

        The real register is empty (2.0's debt was cleared), which disarms CHECK
        B, so the fixture first seeds a non-empty register (an open-debt 2.0 row)
        to arm the gate. A git baseline of that copy is committed next (2.2 is ⬜
        at HEAD, debt open), then 2.2 is flipped to ✅ in the working tree and
        left OUT of the register. Marking it ✅ keeps CHECK A quiet (CHECK A only
        inspects 🟡/⛔), and because 2.2 was ⬜ at baseline it is treated as NEW
        work while debt is still open, so CHECK B fires in isolation.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runbook = _copy_clean_tree(root)
            _seed_open_debt(runbook)  # arm the gate: register is non-empty
            _git_commit_baseline(root)  # HEAD baseline: 2.2 is ⬜, debt open
            _set_2_2_status(runbook, DONE)  # 2.2 ⬜ -> ✅ (new work)

            violations = check_docs.run_checks(root)
            checks = {v.check for v in violations}
            self.assertIn("CHECK B", checks, "new started feature must fire CHECK B")
            self.assertNotIn("CHECK A", checks, "CHECK A should stay isolated here")
            self.assertTrue(any(v.story_id == "2.2" for v in violations))
            self.assertEqual(check_docs.main(["--repo-root", str(root)]), 1)


if __name__ == "__main__":
    unittest.main()
