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
  2. The **master story table** -- the single build-order table shaped
     ``| Build tier | Story | Title | Depends on | Status | Phase | Completed |
     Restore tag |`` -- to get each story's ID and its status emoji (one of the
     legend markers ``⬜`` not started, ``🟡`` in progress, ``⛔`` blocked,
     ``✅`` done). The table is discovered by the PRESENCE of the Story, Title,
     Depends on, and Status columns in its header (in any position, so the
     leading ``Build tier`` column does not hide it), and both the Story ID and
     the Status are read from their columns located BY NAME rather than by a
     fixed position.

It also parses the **Operational Debt Register** (a SEPARATE ledger from the
Validation Debt Register, shaped ``| ID | Debt (what is riding) | Next action |
Owner | Opened |``) and PRINTS every open ``OD-nnn`` entry on every run. This is
informational only -- it does NOT affect the exit code or arm the advancement gate
-- but it guarantees that a new tier / session / story is never unaware of the
non-validation follow-through (cost cleanup, deferred teardowns, drift) that is riding.

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

CHECK C -- schedule-order invariant (single pane of glass = the true schedule)
    The master story table is ordered as the TRUE SCHEDULE (Option B): DONE
    history, then the OPEN execution queue in the order we intend to work it, then
    DEFERRED rows at the bottom. It is deliberately NOT sorted by a monotonic
    ``Build tier`` column -- we may schedule an independent tier-0 story before a
    tier-9 one. CHECK C keeps that schedule honest by enforcing the two invariants
    that a free reordering must never break:
      C1 -- DEPENDENCY PRECEDENCE: every story appears AFTER all stories in its
            ``Depends on`` cell. Build tier = 1 + the highest dependency tier
            (METHODOLOGY 1a), so reordering INDEPENDENT stories is fine, but a
            story may never sit above one of its own dependencies. This is the real
            invariant the old tier-monotonic rule proxied for.
      C2 -- DEFERRED ROWS LAST: no active (non-deferred) row may appear below a row
            whose title carries a ``DEFERRED`` marker.
    Covers EVERY track (pipe, governance G-n, Floor & Harvest A.n/B.n/C.n, tenancy
    T.n) via ``BUILD_ORDER_ID_RE`` (broader than ``STORY_ID_RE``). It reads the
    ``Depends on`` column but does not re-derive tiers.

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
# prose cells are not mistaken for IDs. NOTE: this deliberately matches only the
# pipe (N.N[suffix]) and governance (G-n) tracks -- the register / advancement-gate
# logic (CHECK A / CHECK B) is defined over those. The Floor-&-Harvest (A.n / B.n /
# C.n) and tenancy (T.n) tracks are intentionally OUTSIDE that scope and must not
# be pulled into the register/gate baseline by widening this pattern.
STORY_ID_RE = re.compile(r"^[0-9]+\.[0-9]+[A-Za-z]?$|^G-[0-9]+$")

# A BUILD-ORDER row ID: every track that appears in the master story table,
# including the letter tracks (Floor & Harvest A.n / B.n / C.n, tenancy T.n) that
# STORY_ID_RE deliberately excludes. Used ONLY by the build-order invariant
# (CHECK C), which must see EVERY row -- the out-of-order rows that motivated the
# check were letter-track rows. It is intentionally separate from STORY_ID_RE so
# the register / advancement-gate scope is unchanged.
BUILD_ORDER_ID_RE = re.compile(
    r"^[0-9]+\.[0-9]+[A-Za-z]?$|^G-[0-9]+$|^[A-Z]\.[0-9]+$"
)

# Columns that must all be PRESENT (in any position) for a header row to be the
# master story table. The master table leads with a "Build tier" column, so the
# signature is a presence check over this set rather than a leading-prefix match.
STORY_TABLE_COLUMNS = ("story", "title", "depends on", "status")
# Columns that must all be PRESENT for the Validation Debt Register table.
REGISTER_TABLE_COLUMNS = ("story", "why not done")
# Columns that must all be PRESENT for the Operational Debt Register table
# (a SEPARATE ledger from the Validation Debt Register: non-validation follow-through
# such as cost-cleanup remainders and deferred teardowns). Its open entries are
# PRINTED on every run so a new session cannot be unaware of the debt that is riding;
# it does NOT arm the advancement gate.
OP_DEBT_TABLE_COLUMNS = ("id", "debt (what is riding)", "next action")
# An operational-debt ID like OD-001.
OP_DEBT_ID_RE = re.compile(r"^OD-[0-9]+$")


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


def _header_has_columns(cells: list[str], required: tuple[str, ...]) -> bool:
    """True if every column in ``required`` is PRESENT (case-insensitive).

    A presence check (not a leading-prefix match), so a table whose header leads
    with an extra column such as ``Build tier`` is still recognised as long as it
    carries all of the required columns somewhere in its header.
    """
    lowered = {cell.lower() for cell in cells}
    return all(column in lowered for column in required)


def _column_index(cells: list[str], name: str) -> int:
    """Return the index of the header cell named ``name`` (case-insensitive)."""
    return [cell.lower() for cell in cells].index(name)


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
    story_index = 0
    for line in text.splitlines():
        if "|" not in line:
            if in_table:
                break
            continue
        cells = _split_row(line)
        if _header_has_columns(cells, REGISTER_TABLE_COLUMNS):
            in_table = True
            story_index = _column_index(cells, "story")
            continue
        if not in_table:
            continue
        if _is_separator_row(cells):
            continue
        if len(cells) <= story_index:
            continue
        story_id = _clean_id(cells[story_index])
        if STORY_ID_RE.match(story_id):
            registered.add(story_id)
    return registered


def parse_operational_debt(text: str) -> list[tuple[str, str]]:
    """Return open Operational Debt Register entries as (id, next_action) pairs.

    This is a SEPARATE ledger from the Validation Debt Register: it tracks
    non-validation follow-through (cost cleanup, deferred teardowns, drift). Open
    entries are printed on every run so a session cannot miss the debt that is
    riding, but they do NOT arm the advancement gate.
    """
    entries: list[tuple[str, str]] = []
    in_table = False
    id_index = 0
    action_index = 0
    for line in text.splitlines():
        # Skip blockquote prose (the section's ``>`` description text can itself
        # quote the table shape ``| ID | Debt ... |`` and would otherwise be
        # mistaken for the real header row).
        if line.lstrip().startswith(">"):
            continue
        if "|" not in line:
            if in_table:
                break
            continue
        cells = _split_row(line)
        if _header_has_columns(cells, OP_DEBT_TABLE_COLUMNS):
            in_table = True
            id_index = _column_index(cells, "id")
            action_index = _column_index(cells, "next action")
            continue
        if not in_table:
            continue
        if _is_separator_row(cells):
            continue
        if len(cells) <= max(id_index, action_index):
            continue
        debt_id = _clean_id(cells[id_index])
        if OP_DEBT_ID_RE.match(debt_id):
            entries.append((debt_id, cells[action_index].strip()))
    return entries


def parse_story_tier_order(text: str) -> list[tuple[str, int, list[str], bool]]:
    """Return the master table's rows, in physical order, as records for the
    schedule-order invariant (CHECK C).

    Each record is ``(story_id, build_tier, depends_on, is_deferred)`` where
    ``depends_on`` is the list of story IDs in the ``Depends on`` cell and
    ``is_deferred`` is True when the row's title carries an explicit ``DEFERRED``
    marker. The list preserves table order so CHECK C can assert (1) dependency
    PRECEDENCE — every story appears after all of its dependencies — and (2) that
    deferred rows are pulled to the bottom. This models the Option-B "true
    scheduled order" table: DONE history, then the OPEN execution queue, then
    DEFERRED — ordered by our chosen sequence constrained only by dependencies,
    NOT by a monotonic tier column.

    Only the master story table is read (same column-presence signature as
    ``parse_story_statuses``). Rows whose ``Build tier`` cell is not an integer are
    skipped (defensive).
    """
    order: list[tuple[str, int, list[str], bool]] = []
    in_table = False
    story_index = 0
    tier_index = 0
    deps_index = 0
    title_index = 0
    for line in text.splitlines():
        if "|" not in line:
            in_table = False
            continue
        cells = _split_row(line)
        if _header_has_columns(cells, STORY_TABLE_COLUMNS) and _header_has_columns(
            cells, ("build tier", "depends on", "title")
        ):
            in_table = True
            story_index = _column_index(cells, "story")
            tier_index = _column_index(cells, "build tier")
            deps_index = _column_index(cells, "depends on")
            title_index = _column_index(cells, "title")
            continue
        if not in_table:
            continue
        if _is_separator_row(cells):
            continue
        if len(cells) <= max(story_index, tier_index, deps_index, title_index):
            continue
        story_id = _clean_id(cells[story_index])
        if not BUILD_ORDER_ID_RE.match(story_id):
            continue
        try:
            tier = int(cells[tier_index].strip())
        except ValueError:
            continue
        # Dependencies: the cell lists comma-separated story IDs, or an em/en dash
        # (or "-") for "no dependency". Extract only well-formed IDs.
        deps = [
            _clean_id(part)
            for part in cells[deps_index].replace("\u2014", ",").replace("\u2013", ",").split(",")
            if BUILD_ORDER_ID_RE.match(_clean_id(part))
        ]
        is_deferred = "DEFERRED" in cells[title_index].upper()
        order.append((story_id, tier, deps, is_deferred))
    return order


def parse_story_statuses(text: str) -> dict[str, str]:
    """Return a mapping of story ID -> status marker from the master table.

    Only a table whose header CONTAINS the ``Story``, ``Title``, ``Depends on``,
    and ``Status`` columns is read, so the Progress Summary (phase rows), the
    story state-machine table, and the register itself are not mistaken for the
    story table. The Story ID and Status are both read from their columns located
    by name, so the leading ``Build tier`` column in the master table does not
    shift the ID out of view.
    """
    statuses: dict[str, str] = {}
    in_table = False
    story_index = 0
    status_index = 0
    for line in text.splitlines():
        if "|" not in line:
            in_table = False
            continue
        cells = _split_row(line)
        if _header_has_columns(cells, STORY_TABLE_COLUMNS):
            in_table = True
            story_index = _column_index(cells, "story")
            status_index = _column_index(cells, "status")
            continue
        if not in_table:
            continue
        if _is_separator_row(cells):
            continue
        if len(cells) <= max(story_index, status_index):
            continue
        story_id = _clean_id(cells[story_index])
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


def check_c_build_order(
    tier_order: list[tuple[str, int, list[str], bool]],
    runbook_name: str,
) -> list[Violation]:
    """CHECK C: the master table is in TRUE SCHEDULED ORDER (Option B).

    The master story table is the repo's "single pane of glass": DONE history,
    then the OPEN execution queue in the order we intend to work it, then DEFERRED
    rows at the bottom. Rows are ordered by our CHOSEN schedule, NOT by a monotonic
    ``Build tier`` column (build tier is retained per row as dependency metadata,
    but the table is no longer sorted by it). The two invariants that keep that
    schedule HONEST are enforced here:

      C1 -- DEPENDENCY PRECEDENCE (the hard rule): every story must appear AFTER
            all of the stories in its ``Depends on`` cell. Build tier = 1 + the
            highest tier of any dependency (METHODOLOGY 1a), so a schedule may
            reorder INDEPENDENT stories freely (e.g. do a tier-0 gate close before
            a tier-9 pipe story), but it may NEVER place a story above one of its
            own dependencies. This is the real invariant the old tier-monotonic
            rule was a proxy for; it still catches the drift that motivated CHECK C
            (a story scheduled before something it needs).

      C2 -- DEFERRED ROWS ARE LAST: once a row marked ``DEFERRED`` appears, every
            subsequent row must also be deferred. Deferred work is pulled to the
            bottom so the top of the table is the live schedule.

    Only rows for stories present in the table are precedence-checked (a dependency
    named but absent from the table is ignored -- out of scope for ordering).
    """
    violations: list[Violation] = []
    position = {story_id: idx for idx, (story_id, *_rest) in enumerate(tier_order)}

    # C1 -- dependency precedence.
    for idx, (story_id, _tier, deps, _deferred) in enumerate(tier_order):
        for dep in deps:
            dep_pos = position.get(dep)
            if dep_pos is not None and dep_pos > idx:
                violations.append(
                    Violation(
                        check="CHECK C",
                        file=runbook_name,
                        story_id=story_id,
                        detail=(
                            f"out of schedule order: appears before its dependency "
                            f"{dep!r} (which is listed later); every story must be "
                            "placed after all of its Depends-on entries so the "
                            "table stays a dependency-honest schedule"
                        ),
                    )
                )

    # C2 -- deferred rows must be last (no active row below a deferred one).
    seen_deferred = ""
    for story_id, _tier, _deps, deferred in tier_order:
        if deferred:
            seen_deferred = story_id
        elif seen_deferred:
            violations.append(
                Violation(
                    check="CHECK C",
                    file=runbook_name,
                    story_id=story_id,
                    detail=(
                        f"out of schedule order: an active (non-deferred) row "
                        f"appears below the deferred row {seen_deferred!r}; deferred "
                        "stories must be pulled to the bottom of the table"
                    ),
                )
            )
    return violations


def run_checks(repo_root: Path) -> list[Violation]:
    """Parse RUNBOOK.md under ``repo_root`` and run CHECK A, CHECK B, CHECK C."""
    runbook_path = repo_root / "RUNBOOK.md"
    text = runbook_path.read_text(encoding="utf-8")
    registered = parse_register(text)
    statuses = parse_story_statuses(text)
    tier_order = parse_story_tier_order(text)

    committed = committed_runbook_text(runbook_path)
    baseline = parse_story_statuses(committed) if committed is not None else statuses

    violations: list[Violation] = []
    violations.extend(
        check_a_register_completeness(statuses, registered, runbook_path.name)
    )
    violations.extend(
        check_b_advancement_gate(statuses, registered, baseline, runbook_path.name)
    )
    violations.extend(check_c_build_order(tier_order, runbook_path.name))
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

    # Surface OPERATIONAL debt on EVERY run (pass or fail) so a new tier / session /
    # story is never unaware of the non-validation follow-through that is riding.
    # This is informational (it does NOT affect the exit code or the advancement
    # gate); it just makes the debt impossible to miss at session start.
    runbook = repo_root / "RUNBOOK.md"
    if runbook.exists():
        op_debt = parse_operational_debt(runbook.read_text(encoding="utf-8"))
        if op_debt:
            print(f"check_docs: OPERATIONAL DEBT OPEN -- {len(op_debt)} item(s) riding "
                  "(informational; does not block feature work):")
            for debt_id, next_action in op_debt:
                print(f"  [{debt_id}] next: {next_action}")

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
