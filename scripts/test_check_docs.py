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


def _copy_clean_repo(dest: Path) -> Path:
    """Copy the WHOLE repo doc tree into ``dest`` and return the repo root.

    The Story G-2 checks (CHECK D..J) read multiple docs (PROJECT_PLAN, README,
    BUILD_ORDER, the on-deck pointer, the Floor & Harvest plan, every ``*.md``),
    so their fixtures need the full tree — not just RUNBOOK.md. We copy the repo
    (excluding VCS / build / cache dirs) so each fixture starts from a clean,
    passing tree and mutates exactly ONE surface, proving the target check fires
    in isolation. ``.git`` is excluded so ``committed_runbook_text`` falls back to
    the working tree (keeping CHECK B quiet on these fixtures).
    """
    ignore = shutil.ignore_patterns(
        ".git", "node_modules", "cdk.out", "__pycache__", ".pytest_cache", "*.pyc"
    )
    shutil.copytree(REPO_ROOT, dest, ignore=ignore, dirs_exist_ok=True)
    return dest


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
# then 3.1 then 3.2 then 3.3 each served this role and then moved to ✅/🟡; when 3.3
# went 🟡 in its build session, this was repointed to 3.4 — the next untouched
# downstream ⬜ pipeline story, keeping the fixtures independent of the current
# pipeline state).
# RECURRING MAINTENANCE: when 4.3 later leaves ⬜, repoint this to the next
# still-⬜ master-table feature story (e.g. 4.4).
_NEW_WORK_STORY = "4.4"


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
        # OD-001, OD-002, OD-003 were all closed 2026-09-12 (Hub sweep, Forensic sweep,
        # CDK toolchain bump). They live only as CLOSED blockquote notes, which the
        # parser must NOT surface as open rows; the placeholder "(none open)" row is not
        # a real OD-nnn entry either.
        self.assertNotIn("OD-001", ids, "closed OD-001 must NOT parse as an open row")
        self.assertNotIn("OD-002", ids, "closed OD-002 must NOT parse as an open row")
        self.assertNotIn("OD-003", ids, "closed OD-003 must NOT parse as an open row")
        # OD-004 (opened 2026-09-13): the deferred restore-point state-manifest capture
        # for the phase-3-green + story-4.5-green tags. It IS an open row, so the parser
        # must surface exactly it.
        self.assertIn("OD-004", ids, "open OD-004 must parse as an open row")
        self.assertEqual(
            ids, {"OD-004"}, "OD-004 is the only currently-open operational-debt row"
        )
        # Operational debt does NOT block: the tree still passes (exit 0) even with an
        # open OD entry — an open OD row is surfaced, never gate-arming.
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


class G2IntegrityAndDriftTests(unittest.TestCase):
    """Self-tests for the Story G-2 checks (CHECK D..J).

    Each test copies the WHOLE clean tree, mutates ONE surface, and asserts the
    target check FIRES (read the SUITE ``OK`` / ``FAILED`` line, not the in-suite
    ``check_docs: FAIL`` fixture prints). A companion assertion confirms the clean
    tree does NOT fire that check, so each rule is proven both ways.
    """

    def test_clean_tree_has_no_g2_violations(self) -> None:
        """The real tree passes every G-2 check (D..I); only advisory J may note."""
        violations = check_docs.run_checks(REPO_ROOT)
        g2 = {v.check for v in violations} & {
            "CHECK D", "CHECK E", "CHECK F", "CHECK G", "CHECK H", "CHECK I"
        }
        self.assertEqual(g2, set(), f"clean tree must have no G-2 violations: {violations}")

    def test_plan_runbook_divergence_fires_check_d(self) -> None:
        """CHECK D fires when a phase's PLAN story-set diverges from the RUNBOOK.

        Delete a Phase-1 story ID from the PLAN's explicit list (drop **1.4** ->
        `1.4`) so the plan set no longer equals the RUNBOOK P1 set.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_clean_repo(Path(tmp))
            plan = root / "PROJECT_PLAN.md"
            text = plan.read_text(encoding="utf-8")
            self.assertIn("**1.4**", text)
            plan.write_text(text.replace("**1.4**", "1.4", 1), encoding="utf-8")

            checks = {v.check for v in check_docs.run_checks(root)}
            self.assertIn("CHECK D", checks, "plan/runbook divergence must fire CHECK D")

    def test_dangling_rd_ref_fires_check_e(self) -> None:
        """CHECK E fires when a living doc references an undefined RD.

        Inject ``RD-099`` (never defined) into a living doc (the README).
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_clean_repo(Path(tmp))
            readme = root / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8") + "\n\nSee RD-099 for details.\n",
                encoding="utf-8",
            )
            violations = check_docs.run_checks(root)
            self.assertTrue(
                any(v.check == "CHECK E" and v.story_id == "RD-099" for v in violations),
                "an undefined RD reference in a living doc must fire CHECK E",
            )

    def test_stray_placeholder_fires_check_f(self) -> None:
        """CHECK F fires for a bare ``{{placeholder}}`` outside the template files."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_clean_repo(Path(tmp))
            readme = root / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8") + "\n\nTODO {{UNFILLED}} here.\n",
                encoding="utf-8",
            )
            checks = {v.check for v in check_docs.run_checks(root)}
            self.assertIn("CHECK F", checks, "a stray placeholder must fire CHECK F")

    def test_placeholder_in_inline_code_does_not_fire_check_f(self) -> None:
        """A ``{{placeholder}}`` written as INLINE CODE is documentation, not stray."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_clean_repo(Path(tmp))
            readme = root / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8")
                + "\n\nFill the `{{PROJECT_NAME}}` placeholder.\n",
                encoding="utf-8",
            )
            checks = {v.check for v in check_docs.run_checks(root)}
            self.assertNotIn(
                "CHECK F", checks, "an inline-code placeholder reference must NOT fire"
            )

    def test_done_without_date_fires_check_g(self) -> None:
        """CHECK G fires for a ✅ pipe/gov story with a blank Completed cell.

        Blank the Completed date of an already-✅ pipe story (1.1) in the master
        table without touching its status glyph.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_clean_repo(Path(tmp))
            runbook = root / "RUNBOOK.md"
            lines = runbook.read_text(encoding="utf-8").splitlines(keepends=True)
            for i, line in enumerate(lines):
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                # master row for 1.1: | 0 | pipe | [1.1](...) | ... | ✅ | P1 | 2026-08-24 |
                if len(cells) >= 8 and cells[2].startswith("[1.1]") and "✅" in line:
                    lines[i] = line.replace("2026-08-24", "")
                    break
            else:
                self.fail("could not find the 1.1 master row to blank")
            runbook.write_text("".join(lines), encoding="utf-8")
            violations = check_docs.run_checks(root)
            self.assertTrue(
                any(v.check == "CHECK G" and v.story_id == "1.1" for v in violations),
                "a ✅ pipe story with no Completed date must fire CHECK G",
            )

    def test_glyph_drift_fires_check_h(self) -> None:
        """CHECK H fires when a living doc's generated glyph disagrees with RUNBOOK.

        Corrupt README's generated phase-status block by flipping one phase glyph to a
        value the RUNBOOK roll-up does NOT have, and assert CHECK H fires. The fixture
        must not assume any particular phase is still open (as phases close, the block's
        glyphs change), so it mutates whichever known glyph is present: prefer flipping
        an open phase (⬜/🟡) to ✅, else flip a ✅ to ⬜ — either way it disagrees with
        the true RUNBOOK roll-up.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_clean_repo(Path(tmp))
            readme = root / "README.md"
            text = readme.read_text(encoding="utf-8")
            begin = text.index(check_docs.GEN_BEGIN)
            end = text.index(check_docs.GEN_END)
            block = text[begin:end]
            if "⬜" in block:
                mutated = block.replace("⬜", "✅", 1)
            elif "🟡" in block:
                mutated = block.replace("🟡", "✅", 1)
            else:  # every phase is ✅ — flip one to an open glyph to force disagreement
                mutated = block.replace("✅", "⬜", 1)
            self.assertNotEqual(mutated, block, "fixture found no glyph to mutate")
            readme.write_text(text[:begin] + mutated + text[end:], encoding="utf-8")
            checks = {v.check for v in check_docs.run_checks(root)}
            self.assertIn("CHECK H", checks, "a drifted generated glyph must fire CHECK H")

    def test_on_deck_points_at_done_fires_check_h(self) -> None:
        """CHECK H fires when the on-deck starter points at an already-✅ story.

        Repoint the on-deck ``## Next session`` heading at a done story (1.1).
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_clean_repo(Path(tmp))
            on_deck = root / "docs" / "session-briefs" / "on-deck" / "README.md"
            lines = on_deck.read_text(encoding="utf-8").splitlines(keepends=True)
            for i, line in enumerate(lines):
                if line.startswith("## Next session:"):
                    lines[i] = "## Next session: Story 1.1 — (a done story)\n"
                    break
            else:
                self.fail("could not find the on-deck Next session heading")
            on_deck.write_text("".join(lines), encoding="utf-8")
            violations = check_docs.run_checks(root)
            self.assertTrue(
                any(v.check == "CHECK H" and v.story_id == "1.1" for v in violations),
                "an on-deck pointer at a ✅ story must fire CHECK H",
            )

    def test_dangling_link_fires_check_i(self) -> None:
        """CHECK I fires for a repo-relative link whose target is missing."""
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_clean_repo(Path(tmp))
            readme = root / "README.md"
            readme.write_text(
                readme.read_text(encoding="utf-8")
                + "\n\nSee [the missing doc](docs/DOES_NOT_EXIST.md).\n",
                encoding="utf-8",
            )
            violations = check_docs.run_checks(root)
            self.assertTrue(
                any(
                    v.check == "CHECK I" and "DOES_NOT_EXIST" in v.story_id
                    for v in violations
                ),
                "a dangling repo-relative link must fire CHECK I",
            )

    def test_dangling_link_in_frozen_artifact_does_not_fire_check_i(self) -> None:
        """A broken link in a FROZEN artifact (not a living doc) must NOT fire.

        CHECK I is scoped to LIVING docs; a dated frozen brief is a snapshot we do
        not rewrite. Injecting a broken link into a frozen brief stays silent.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_clean_repo(Path(tmp))
            frozen = root / "docs" / "session-briefs" / "story-1.1-brief.md"
            frozen.write_text(
                frozen.read_text(encoding="utf-8")
                + "\n\nSee [gone](docs/GONE.md).\n",
                encoding="utf-8",
            )
            violations = check_docs.run_checks(root)
            self.assertFalse(
                any(v.check == "CHECK I" and "GONE" in v.story_id for v in violations),
                "a broken link in a frozen artifact must NOT fire CHECK I",
            )

    def test_sequence_adherence_is_advisory_only(self) -> None:
        """CHECK J is ADVISORY: it never affects the exit code.

        Repoint the on-deck starter at an OPEN story that is not the first Ready
        item; CHECK J appears in ``run_advisories`` but NOT in ``run_checks`` (so a
        clean-but-reordered tree still exits 0).
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = _copy_clean_repo(Path(tmp))
            # Derive an out-of-order target instead of hard-coding a story ID: point
            # on-deck at an OPEN story that is NOT the first Ready-now item. (Hard-coding
            # a specific ID goes stale as stories close and the first-open item shifts —
            # e.g. after G-1 closed 2026-09-12, T.1 became the first-open item, so the
            # old hard-coded "T.1" no longer produced a mismatch.)
            runbook_text = (root / "RUNBOOK.md").read_text(encoding="utf-8")
            first_open = check_docs._first_open_ready_story(runbook_text)
            self.assertIsNotNone(first_open, "clean repo must have a first-open Ready story")
            statuses = check_docs.parse_story_statuses(runbook_text)
            out_of_order = next(
                (sid for sid, st in statuses.items()
                 if st != check_docs.DONE and sid != first_open),
                None,
            )
            self.assertIsNotNone(
                out_of_order, "need a second open story to simulate a reorder"
            )
            on_deck = root / "docs" / "session-briefs" / "on-deck" / "README.md"
            lines = on_deck.read_text(encoding="utf-8").splitlines(keepends=True)
            for i, line in enumerate(lines):
                if line.startswith("## Next session:"):
                    lines[i] = f"## Next session: Story {out_of_order} — (an open but out-of-order story)\n"
                    break
            on_deck.write_text("".join(lines), encoding="utf-8")
            advisories = {v.check for v in check_docs.run_advisories(root)}
            hard = {v.check for v in check_docs.run_checks(root)}
            self.assertIn("CHECK J (advisory)", advisories, "reorder must raise advisory J")
            self.assertNotIn(
                "CHECK J (advisory)", hard, "advisory J must never be a hard violation"
            )


if __name__ == "__main__":
    unittest.main()
