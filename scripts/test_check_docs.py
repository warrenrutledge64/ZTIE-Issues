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
    (non-zero exit);
  * CHECK C (schedule order, Option B): the clean tree is dependency-honest
    (every story after its deps, deferred rows last); a story hoisted above its
    own dependency fires C1; a row marked DEFERRED above active rows fires C2.
The failure fixtures are designed so CHECK A, CHECK B, and CHECK C each fire in
isolation, proving the rules independently.

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


# A master-table story that is ⬜ Not Started in the real RUNBOOK and carries no
# register entry, used by the CHECK A / CHECK B fixtures as "new feature work".
# It MUST be repointed whenever this pinned story advances off ⬜ (2.2 then 2.5
# then 3.1 then 3.2 each served this role and then moved to ✅/🟡; when 3.2 went 🟡
# in its build session, this was repointed to 3.3 — the next untouched downstream ⬜
# pipeline story, keeping the fixtures independent of the current pipeline state).
# RECURRING MAINTENANCE: when 3.3 later leaves ⬜, repoint this to the next
# still-⬜ master-table feature story (e.g. 3.4).
_NEW_WORK_STORY = "3.3"


def _seed_open_debt(runbook_path: Path, story_id: str = "2.0") -> None:
    """Seed a non-empty Validation Debt Register in the copied RUNBOOK.

    CHECK B early-returns when the register is empty, so the advancement gate is
    disarmed and cannot fire. This helper arms the gate for the CHECK B fixture by
    inserting a plausible open-debt row immediately after the register's header
    separator, without touching the master story table or any status cell. It is
    robust to the register already holding entries (it does not depend on an
    ``_(empty)_`` placeholder). The seeded story (default 2.0) is deliberately an
    already-open/complete baseline story so it does not itself trip CHECK B; it
    only guarantees the register is non-empty.
    """
    text = runbook_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    seeded = (
        f"| {story_id} | awaiting recorded live validation | "
        f"run the live validation | executor |\n"
    )
    in_register = False
    for index, line in enumerate(lines):
        cells = [cell.strip().lower() for cell in line.strip().strip("|").split("|")]
        if {"story", "why not done"} <= set(cells):
            in_register = True
            continue
        if in_register and set(line.strip().strip("|").replace("|", "")) <= {"-", ":", " "} and "-" in line:
            # The header separator row -> insert the seeded open-debt row after it.
            lines.insert(index + 1, seeded)
            runbook_path.write_text("".join(lines), encoding="utf-8")
            return
    raise AssertionError("Validation Debt Register table not found in fixture")


def _set_story_status(
    runbook_path: Path, story_id: str, new_marker: str, from_marker: str = NOT_STARTED
) -> None:
    """Flip the master-table row for ``story_id`` from ``from_marker`` to
    ``new_marker`` in place.

    The master table carries extra leading columns (``Build tier``, ``Track``), so
    the Story column is NOT at a fixed index. This helper locates the ``Story``
    column BY HEADER NAME (mirroring how the production checker parses the table)
    and reads the ID from that column, unwrapping a markdown link like ``[2.5](...)``
    down to the bare ID. That keeps the fixture robust when columns are added.
    """
    text = runbook_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    story_col: int | None = None
    for index, line in enumerate(lines):
        if not line.lstrip().startswith("|"):
            story_col = None
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        # Discover the Story column from a header row, then use it for data rows.
        if story_col is None:
            if "Story" in cells and "Status" in cells:
                story_col = cells.index("Story")
            continue
        if len(cells) <= story_col:
            continue
        story_cell = cells[story_col]
        # Unwrap a markdown link like ``[2.5](...)`` down to the bare ID.
        link = re.match(r"^\[([^\]]+)\]", story_cell)
        parsed = link.group(1) if link else story_cell
        if parsed == story_id:
            lines[index] = line.replace(from_marker, new_marker, 1)
            break
    else:  # pragma: no cover - guards against a fixture drifting from the doc
        raise AssertionError(f"could not locate the master-table story {story_id} row")
    runbook_path.write_text("".join(lines), encoding="utf-8")


def _move_last_master_row_to_top(runbook_path: Path) -> tuple[str, list[str]]:
    """Move the LAST data row of the master table to the TOP of the data section,
    creating a DEPENDENCY-PRECEDENCE violation for the CHECK C fixture (Option B
    model: the table is a schedule, so CHECK C enforces precedence + deferred-last,
    not tier-monotonic).

    The last table row is the highest-tier story (4.4), which depends on 4.3 + 4.7.
    Hoisting it to the top places it ABOVE its own dependencies -> CHECK C's
    dependency-precedence rule (C1) must fire. Returns the moved row's
    ``(story_id, deps)`` for the assertion. Pure row relocation; no cell changed.
    """
    lines = runbook_path.read_text(encoding="utf-8").splitlines(keepends=True)
    sep_idx = None
    deps_col = story_col = None
    for index, line in enumerate(lines):
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip().lower() for c in line.strip().strip("|").split("|")]
        if {"story", "title", "depends on", "status", "build tier"} <= set(cells):
            sep_idx = index + 1
            deps_col = cells.index("depends on")
            story_col = cells.index("story")
            break
    assert sep_idx is not None
    first_data = sep_idx + 1
    last_data = first_data
    while last_data < len(lines) and lines[last_data].lstrip().startswith("|"):
        last_data += 1
    last_data -= 1
    moved = lines.pop(last_data)
    lines.insert(first_data, moved)  # now the deepest story sits above its deps
    runbook_path.write_text("".join(lines), encoding="utf-8")
    cells = [c.strip() for c in moved.strip().strip("|").split("|")]
    story = re.sub(r"^\[|\].*$", "", cells[story_col])
    deps = [d.strip() for d in cells[deps_col].replace("\u2014", ",").split(",") if d.strip()]
    return story, deps


def _defer_first_open_row(runbook_path: Path) -> str:
    """Mark the FIRST non-deferred, not-done master-table row as ``[DEFERRED]`` in
    its title WITHOUT moving it, creating a C2 (deferred-not-last) violation: a
    deferred row now sits above many active rows. Returns the story id. Only edits
    the title cell text (adds a DEFERRED marker); changes no status or order.
    """
    lines = runbook_path.read_text(encoding="utf-8").splitlines(keepends=True)
    story_col = title_col = status_col = None
    in_table = False
    for index, line in enumerate(lines):
        if not line.lstrip().startswith("|"):
            in_table = False
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        lowered = [c.lower() for c in cells]
        if {"story", "title", "depends on", "status", "build tier"} <= set(lowered):
            in_table = True
            story_col = lowered.index("story")
            title_col = lowered.index("title")
            status_col = lowered.index("status")
            continue
        if not in_table or len(cells) <= max(story_col, title_col, status_col):
            continue
        if set(line.strip().strip("|").replace("|", "")) <= {"-", ":", " "}:
            continue
        # first row that is neither done (✅) nor already deferred
        if check_docs.DONE in cells[status_col] or "DEFERRED" in cells[title_col].upper():
            continue
        story = re.sub(r"^\[|\].*$", "", cells[story_col])
        new_cells = cells[:]
        new_cells[title_col] = cells[title_col] + " [DEFERRED: fixture]"
        lines[index] = "| " + " | ".join(new_cells) + " |\n"
        runbook_path.write_text("".join(lines), encoding="utf-8")
        return story
    raise AssertionError("no active master-table row found to defer")


class CheckDocsTests(unittest.TestCase):
    def test_clean_tree_passes(self) -> None:
        """The real, unmodified tree passes: exit 0, no violations."""
        violations = check_docs.run_checks(REPO_ROOT)
        self.assertEqual(violations, [], "clean tree should have no violations")
        self.assertEqual(check_docs.main(["--repo-root", str(REPO_ROOT)]), 0)

    def test_unregistered_in_progress_fires_check_a(self) -> None:
        """CHECK A fires when a 🟡 feature story is missing from the register.

        No git baseline is seeded, so the working tree is its own CHECK B
        baseline (the pinned story is 🟡 in it, matching HEAD) -- that keeps
        CHECK B quiet and isolates CHECK A on this fixture.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runbook = _copy_clean_tree(root)
            # A ⬜ story -> 🟡, left OUT of the register.
            _set_story_status(runbook, _NEW_WORK_STORY, IN_PROGRESS)

            violations = check_docs.run_checks(root)
            checks = {v.check for v in violations}
            self.assertIn("CHECK A", checks, "un-registered 🟡 must fire CHECK A")
            self.assertNotIn("CHECK B", checks, "CHECK B should stay isolated here")
            self.assertTrue(any(v.story_id == _NEW_WORK_STORY for v in violations))
            self.assertEqual(check_docs.main(["--repo-root", str(root)]), 1)

    def test_new_feature_started_while_debt_open_fires_check_b(self) -> None:
        """CHECK B fires for a new feature story completed while debt is open.

        The fixture seeds a non-empty register (an open-debt 2.0 row) to arm the
        gate regardless of the real register's contents. A git baseline of that
        copy is committed next (the pinned story is ⬜ at HEAD, debt open), then
        the pinned story is flipped to ✅ in the working tree and left OUT of the
        register. Marking it ✅ keeps CHECK A quiet (CHECK A only inspects 🟡/⛔),
        and because the pinned story was ⬜ at baseline it is treated as NEW work
        while debt is still open, so CHECK B fires in isolation.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runbook = _copy_clean_tree(root)
            _seed_open_debt(runbook)  # arm the gate: register is non-empty
            _git_commit_baseline(root)  # HEAD baseline: pinned story ⬜, debt open
            _set_story_status(runbook, _NEW_WORK_STORY, DONE)  # ⬜ -> ✅ (new work)

            violations = check_docs.run_checks(root)
            checks = {v.check for v in violations}
            self.assertIn("CHECK B", checks, "new started feature must fire CHECK B")
            self.assertNotIn("CHECK A", checks, "CHECK A should stay isolated here")
            self.assertTrue(any(v.story_id == _NEW_WORK_STORY for v in violations))
            self.assertEqual(check_docs.main(["--repo-root", str(root)]), 1)

    def test_clean_tree_is_dependency_ordered(self) -> None:
        """CHECK C: the real master table is a dependency-honest schedule.

        Option B: the table is ordered as the true schedule (DONE history -> OPEN
        queue -> DEFERRED), not by a monotonic tier column. The invariants are
        C1 dependency precedence (every story after its deps) and C2 deferred-last.
        """
        text = (REPO_ROOT / "RUNBOOK.md").read_text(encoding="utf-8")
        order = check_docs.parse_story_tier_order(text)
        # Sanity: the parser sees the letter tracks + captures deps and deferral.
        ids = {sid for sid, *_ in order}
        self.assertTrue({"A.4", "T.1", "C.3"} <= ids, "letter tracks must be parsed")
        # No CHECK C violation on the real, scheduled tree.
        self.assertEqual(
            check_docs.check_c_build_order(order, "RUNBOOK.md"),
            [],
            "clean scheduled tree must have no CHECK C violation",
        )
        # Independent verification of C1: every dependency present in the table
        # appears strictly before the story that depends on it.
        position = {sid: idx for idx, (sid, *_rest) in enumerate(order)}
        for idx, (sid, _tier, deps, _deferred) in enumerate(order):
            for dep in deps:
                if dep in position:
                    self.assertLess(
                        position[dep], idx, f"{sid} must appear after its dep {dep}"
                    )
        # C2: deferred rows (T.2/T.3) are at the very bottom.
        deferred_flags = [deferred for _sid, _t, _d, deferred in order]
        first_deferred = deferred_flags.index(True) if True in deferred_flags else len(order)
        self.assertTrue(
            all(deferred_flags[first_deferred:]),
            "all deferred rows must be contiguous at the bottom",
        )

    def test_dependency_precedence_violation_fires_check_c(self) -> None:
        """CHECK C (C1) fires when a story is scheduled ABOVE its own dependency.

        Only reorders rows, so CHECK A and CHECK B stay quiet and CHECK C is
        isolated. Hoisting the deepest story (4.4, deps 4.3+4.7) to the top places
        it above its dependencies -> a precedence violation.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runbook = _copy_clean_tree(root)
            moved_id, deps = _move_last_master_row_to_top(runbook)

            violations = check_docs.run_checks(root)
            checks = {v.check for v in violations}
            self.assertIn("CHECK C", checks, "story above its dependency must fire CHECK C")
            self.assertNotIn("CHECK A", checks, "CHECK A should stay isolated here")
            self.assertNotIn("CHECK B", checks, "CHECK B should stay isolated here")
            self.assertTrue(
                any(v.check == "CHECK C" and v.story_id == moved_id for v in violations),
                f"expected a CHECK C precedence violation for {moved_id} (deps {deps})",
            )
            self.assertEqual(check_docs.main(["--repo-root", str(root)]), 1)

    def test_deferred_not_last_fires_check_c(self) -> None:
        """CHECK C (C2) fires when a deferred row sits above active rows.

        Marking the first open row ``[DEFERRED]`` in place (without moving it) puts
        a deferred row above many active rows -> a deferred-not-last violation.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runbook = _copy_clean_tree(root)
            deferred_id = _defer_first_open_row(runbook)

            violations = check_docs.run_checks(root)
            checks = {v.check for v in violations}
            self.assertIn("CHECK C", checks, "deferred-above-active must fire CHECK C")
            self.assertTrue(
                any(v.check == "CHECK C" for v in violations),
                f"expected a CHECK C deferred-last violation after deferring {deferred_id}",
            )
            self.assertEqual(check_docs.main(["--repo-root", str(root)]), 1)

    def test_operational_debt_register_parses_open_entries(self) -> None:
        """The real tree's Operational Debt Register parses its open OD-nnn rows.

        This is a SEPARATE ledger from the Validation Debt Register; open entries
        are surfaced (printed) but do NOT arm the advancement gate, so the clean
        tree still passes with exit 0 even while operational debt is open.
        """
        text = (REPO_ROOT / "RUNBOOK.md").read_text(encoding="utf-8")
        entries = check_docs.parse_operational_debt(text)
        ids = {debt_id for debt_id, _action in entries}
        # OD-001 / OD-002 are the seeded cost-cleanup carry-forward items.
        self.assertIn("OD-001", ids, "operational debt OD-001 must be parsed")
        self.assertIn("OD-002", ids, "operational debt OD-002 must be parsed")
        for _debt_id, action in entries:
            self.assertTrue(action, "each open entry must carry a next action")
        # Operational debt does NOT block: the clean tree still passes.
        self.assertEqual(check_docs.run_checks(REPO_ROOT), [])

    def test_operational_debt_ignores_blockquote_prose(self) -> None:
        """A ``>`` blockquote that quotes the table shape is not a real header.

        The section's description prose quotes ``| ID | Debt ... |`` to document
        the expected shape; the parser must skip blockquote lines so that prose
        is not mistaken for the header row (which would yield zero parsed rows).
        """
        synthetic = (
            "## Operational Debt Register\n"
            "> keep the table shape | ID | Debt (what is riding) | Next action |"
            " Owner | Opened |\n"
            "\n"
            "| ID | Debt (what is riding) | Next action | Owner | Opened |\n"
            "|----|-----------------------|-------------|-------|--------|\n"
            "| OD-042 | something riding | do the thing | me | 2026-09-11 |\n"
            "\n"
            "## Next Section\n"
        )
        entries = check_docs.parse_operational_debt(synthetic)
        self.assertEqual(entries, [("OD-042", "do the thing")])


if __name__ == "__main__":
    unittest.main()
