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

CHECK D..J -- management-artifact INTEGRITY + DOC-DRIFT (Story G-2, RD-015)
    Story G-2 finishes RD-015 by extending this same module (it does NOT rebuild
    CHECK A/B/C). The added rules, all stdlib-only / offline / Python-3.9-safe:
      CHECK D -- PLAN <-> RUNBOOK per-phase story-set divergence (compared only
                 for phases the plan enumerates as explicit IDs) + governance set.
      CHECK E -- a referenced ``RD-0NN`` absent from the plan's decisions table.
      CHECK F -- a stray ``{{placeholder}}`` outside the known template files
                 (inline-code references to the convention are ignored).
      CHECK G -- a ``✅`` story with no dated Completed / Validation Result record.
      CHECK H -- doc-drift (LIVING docs only): a generated ``phase-status`` region
                 disagreeing with the RUNBOOK roll-up, or an on-deck pointer at a
                 story already ✅.
      CHECK I -- a dangling repo-relative ``*.md`` link (target missing on disk).
      CHECK K -- (RD-054) a ✅ ``[sec-boundary]`` story lacking its retained
                 ``docs/validation-evidence/<id>/`` folder + the four evidence
                 markers (positive-exercise output, proof-of-absence, named human
                 attestation, provenance pins). Evidence, not testimony.
      CHECK L -- an OPEN story's ``story-<id>-VALIDATION-PACKAGE.md`` missing the
                 mandatory STEP 1.5 / FULL CONTEXT FETCH (full raw source via
                 ``application/vnd.github.v3.raw`` pinned to the SHA). A diff alone
                 hides wrapper-execution / contextual-leak flaws. Closed packages
                 are frozen/grandfathered.
      CHECK O -- (split-brain, RD-055) an OPEN story carries an executor-authored
                 ``story-<id>-LIVE-RUNBOOK.md``. Kiro's validation handoff is the PR
                 number ONLY; the independent validator authors the live runbook +
                 DoD, blind, each time. Closed stories' LIVE-RUNBOOKs are frozen,
                 grandfathered history. This machine-enforces the discipline that a
                 builder must not frame "how to prove it on live AWS."
      CHECK N -- (phase-gate) the hand-maintained Progress Summary phase row
                 disagrees with the machine-derived phase roll-up: either every
                 story in a phase is ✅ but the phase was never closed (the skipped
                 end-of-phase gate), or the phase row claims ✅ while a story in it
                 is still open. The end-of-phase validation is no longer left to
                 memory -- a story-complete-but-unclosed phase FAILS the gate.
      CHECK J -- (ADVISORY, non-blocking) the on-deck starter is not the first
                 OPEN item in the RUNBOOK "Ready now" schedule.
    LIVING vs FROZEN: CHECK H is scoped to living docs (README, BUILD_ORDER's
    delimited generated region, the on-deck pointer). Dated per-story briefs /
    PROMPTs / LIVE-RUNBOOKs and the WORK_LOG are frozen snapshots -- never edited
    to satisfy a checker.

Exit status: 0 when there are no violations, 1 when any (non-advisory) violation
is found. Advisory notes (CHECK J) are printed but never affect the exit code.

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


# ---------------------------------------------------------------------------
# G-2 EXTENSION (RD-015) -- management-artifact INTEGRITY + DOC-DRIFT checks.
#
# Everything above this banner is the Story G-3 machinery (CHECK A/B/C) and is
# left BEHAVIOUR-UNCHANGED. Story G-2 finishes RD-015 by adding the remaining
# integrity checks and the doc-drift guardrails agreed in the 2026-09-12 audit,
# all in this same stdlib-only, offline, Python-3.9-compatible module:
#
#   CHECK D -- PLAN <-> RUNBOOK story-set divergence (per phase, where the plan
#              enumerates explicit IDs) + governance-story-set divergence.
#   CHECK E -- a referenced ``RD-0NN`` that is absent from the decisions table.
#   CHECK F -- a stray ``{{placeholder}}`` outside the known template files.
#   CHECK G -- a ``✅`` story missing a dated ``Validation Result`` line.
#   CHECK H -- doc-drift: a LIVING doc's machine-checkable status glyph disagrees
#              with the RUNBOOK master table, OR the on-deck starter points at a
#              story already ✅ (a stale pointer).
#   CHECK I -- a dangling repo-relative ``*.md`` link (target does not exist).
#   CHECK J -- (ADVISORY) sequence adherence: the on-deck starter is not the
#              first OPEN item in the RUNBOOK "Ready now" schedule. Advisory
#              because a reorder is a legitimate stakeholder decision -- it warns
#              (printed) and does NOT fail the build.
#
# LIVING vs FROZEN: the glyph check (CHECK H) targets ONLY living docs (README,
# BUILD_ORDER's explicitly-delimited generated region, the on-deck pointer).
# Dated per-story briefs / PROMPTs / LIVE-RUNBOOKs and the WORK_LOG are frozen
# snapshots and are never "corrected" to satisfy a checker.
# ---------------------------------------------------------------------------

# The tracked doc set the drift / link checks read. Restricted to *.md tracked in
# the repo (walked from the repo root, skipping VCS / dependency dirs).
_SKIP_DIRS = {".git", "node_modules", "cdk.out", "__pycache__", ".pytest_cache"}

# Files whose live ``{{placeholder}}`` tokens are INTENTIONAL (they ARE templates):
# the two session templates and the session-START prompt are filled per-story.
# Paths are repo-relative, POSIX-style.
TEMPLATE_FILES = frozenset(
    {
        "docs/SESSION_BRIEF_TEMPLATE.md",
        "docs/SESSION_PROMPT_TEMPLATE.md",
        "docs/LIVE_RUNBOOK_TEMPLATE.md",
        "docs/GEMINI_VALIDATION_PACKAGE_TEMPLATE.md",
        "docs/KIRO_VALIDATION_KICKOFF_SKELETON.md",
        "docs/PHASE_GATE_VALIDATION_KICKOFF_SKELETON.md",
        "docs/PHASE_GATE_VALIDATION_PACKAGE_TEMPLATE.md",
        "docs/session-briefs/session-START-PROMPT.md",
    }
)

# A ``{{placeholder}}`` token (non-greedy, no nested braces).
PLACEHOLDER_RE = re.compile(r"\{\{[^{}]*\}\}")
# An inline code span ``like this`` -- placeholder references written as inline
# code are DOCUMENTATION about the convention, not stray placeholders.
INLINE_CODE_RE = re.compile(r"`[^`]*`")
# A story ID that also admits a LETTER-only minor part (e.g. ``1.R``) in addition
# to the digit-minor and letter-track forms in BUILD_ORDER_ID_RE. Used by the
# per-phase divergence + roll-up so ``1.R`` / ``2.0E`` are not silently dropped.
ANY_STORY_ID_RE = re.compile(
    r"^[0-9]+\.[0-9A-Za-z]+$|^G-[0-9]+$|^[A-Z]\.[0-9]+$"
)

# A registered-decision reference like ``RD-013`` (three-digit, zero-padded).
RD_REF_RE = re.compile(r"\bRD-0[0-9][0-9]\b")

# The LIVING core-governance docs. The doc-drift / dangling-ref / dangling-link
# checks (E, H, I) scope to these; dated per-story briefs / PROMPTs /
# LIVE-RUNBOOKs and the templates are FROZEN snapshots and are never inspected /
# "corrected" to satisfy a checker (the audit lesson: only living, duplicated
# surfaces drift). Paths are repo-relative POSIX.
LIVING_DOCS = frozenset(
    {
        "README.md",
        "RUNBOOK.md",
        "PROJECT_PLAN.md",
        "METHODOLOGY.md",
        "CONVENTIONS.md",
        "RESTORE.md",
        "BOM.md",
        "docs/BUILD_ORDER.md",
        "docs/COMPLIANCE.md",
        "docs/ARCHITECTURE.md",
        "docs/STORY_DETAIL.md",
        "docs/governance/OPERATING_MODEL.md",
        "docs/governance/WORK_LOG.md",
        "docs/governance/FLOOR_AND_HARVEST_PLAN.md",
        "docs/governance/SEQUENCING_METHOD.md",
        "docs/governance/COST_REMEDIATION_LEGACY_DECOMMISSION.md",
        "docs/governance/REUSABLE_OS_VS_INSTANCE.md",
        "docs/session-briefs/on-deck/README.md",
    }
)

# The docs that DEFINE registered decisions (PROJECT_PLAN's §5 table + §3 prose,
# and the Floor & Harvest plan which formally proposes RD-022 before C.5 copies it
# into the plan). An ``RD-0NN`` present in either is considered DEFINED by CHECK E.
DECISION_DEFINING_DOCS = ("PROJECT_PLAN.md", "docs/governance/FLOOR_AND_HARVEST_PLAN.md")
# A markdown link target: ``[text](target)``. We only inspect repo-relative
# targets (not http(s):, mailto:, or in-page ``#anchor`` links).
MD_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")

# The delimiters of the machine-checkable, generated phase-status region that
# CHECK H verifies against the RUNBOOK. Living docs (README, BUILD_ORDER) carry
# this block INSTEAD of a hand-kept status copy; b1 converts the old copies to it.
GEN_BEGIN = "<!-- BEGIN GENERATED: phase-status"
GEN_END = "<!-- END GENERATED: phase-status"


def _iter_markdown_files(repo_root: Path) -> list[Path]:
    """Return the tracked ``*.md`` files under ``repo_root`` (VCS/deps skipped)."""
    found: list[Path] = []
    for path in sorted(repo_root.rglob("*.md")):
        if any(part in _SKIP_DIRS for part in path.relative_to(repo_root).parts):
            continue
        found.append(path)
    return found


def _strip_inline_code(text: str) -> str:
    """Remove inline code spans so their contents are not scanned as prose."""
    return INLINE_CODE_RE.sub("", text)


def parse_plan_phase_story_sets(plan_text: str) -> dict[str, set[str]]:
    """Return PROJECT_PLAN's EXPLICIT per-phase story-ID sets.

    The plan is organised by phase. Only phases whose ``### Phase N`` section
    enumerates explicit **bold** story IDs are returned (Phase 1 today); phases
    that describe their stories in prose yield no set and are simply not compared
    (you cannot diff an ID set that was never written). The governance section's
    ``**G-n**`` IDs are returned under the key ``"gov"``. Each section is bounded
    to the next ``##``/``###`` heading so IDs from a later section do not bleed in.
    """
    sets: dict[str, set[str]] = {}
    # Split on level-3 headings, keeping the heading text as the record's start.
    sections = re.split(r"(?m)^### ", plan_text)
    # A bold story ID token, e.g. **1.1**, **1.1R**, **1.R**, **2.0E** (the pipe
    # track; the minor part may be letter-only as in ``1.R``). Governance **G-n**
    # is handled separately (its bold form is **G-n:**).
    bold_id = re.compile(r"\*\*([0-9]+\.[0-9A-Za-z]+)\*\*")
    for section in sections:
        if not section.strip():
            continue
        heading = section.splitlines()[0]
        # Bound this section: cut it at the next level-2 heading if present.
        body = re.split(r"(?m)^## ", section, maxsplit=1)[0]
        key: str | None = None
        stripped = heading.strip()
        match = re.match(r"Phase\s+([0-9]+)", stripped)
        if match:
            key = f"P{match.group(1)}"
        elif "Governance" in stripped:
            key = "gov"
        if key is None:
            continue
        if key == "gov":
            ids = set(re.findall(r"\*\*(G-[0-9]+)", body))
        else:
            ids = {m for m in bold_id.findall(body)}
        if ids:
            sets[key] = ids
    return sets


def parse_runbook_phase_story_sets(runbook_text: str) -> dict[str, set[str]]:
    """Return the RUNBOOK master table's story IDs grouped by phase label.

    Governance rows (Phase cell ``-`` and Track ``gov``) are grouped under the
    key ``"gov"`` so they line up with the plan's governance section. Pipeline
    rows use their ``P1``..``P4`` phase label.
    """
    sets: dict[str, set[str]] = {}
    in_table = False
    story_index = phase_index = track_index = 0
    for line in runbook_text.splitlines():
        if "|" not in line:
            in_table = False
            continue
        cells = _split_row(line)
        if _header_has_columns(cells, STORY_TABLE_COLUMNS) and _header_has_columns(
            cells, ("phase", "track")
        ):
            in_table = True
            story_index = _column_index(cells, "story")
            phase_index = _column_index(cells, "phase")
            track_index = _column_index(cells, "track")
            continue
        if not in_table or _is_separator_row(cells):
            continue
        if len(cells) <= max(story_index, phase_index, track_index):
            continue
        story_id = _clean_id(cells[story_index])
        if not ANY_STORY_ID_RE.match(story_id):
            continue
        track = cells[track_index].strip().lower()
        phase = cells[phase_index].strip()
        key = "gov" if track == "gov" else (phase if phase.startswith("P") else None)
        if key is None:
            continue
        sets.setdefault(key, set()).add(story_id)
    return sets


def check_d_plan_runbook_divergence(
    plan_text: str, runbook_text: str
) -> list[Violation]:
    """CHECK D: the PLAN and RUNBOOK must agree on the per-phase story set.

    Compared ONLY for phases whose plan section enumerates explicit IDs (so a
    prose-only phase is skipped, not falsely flagged). A divergence fires a
    violation naming the phase and the symmetric-difference IDs.
    """
    violations: list[Violation] = []
    plan_sets = parse_plan_phase_story_sets(plan_text)
    runbook_sets = parse_runbook_phase_story_sets(runbook_text)
    for phase, plan_ids in sorted(plan_sets.items()):
        runbook_ids = runbook_sets.get(phase, set())
        if plan_ids != runbook_ids:
            only_plan = sorted(plan_ids - runbook_ids)
            only_runbook = sorted(runbook_ids - plan_ids)
            violations.append(
                Violation(
                    check="CHECK D",
                    file="PROJECT_PLAN.md<->RUNBOOK.md",
                    story_id=phase,
                    detail=(
                        f"PLAN and RUNBOOK story-sets diverge for phase {phase}: "
                        f"only in PLAN={only_plan}, only in RUNBOOK={only_runbook}"
                    ),
                )
            )
    return violations


def check_e_dangling_rd_refs(repo_root: Path) -> list[Violation]:
    """CHECK E: every ``RD-0NN`` referenced anywhere is defined in the plan.

    The registered-decisions table lives in ``PROJECT_PLAN.md``; any ``RD-0NN``
    id that is REFERENCED (in any tracked doc) but never DEFINED there is a
    dangling reference. A decision is considered defined when its id appears in a
    plan table row's first cell OR as a bold/heading token in the decisions
    section. To stay robust, we treat any ``RD-0NN`` that appears in PROJECT_PLAN
    at the START of a table row (``| RD-0NN |``) or as ``**RD-0NN**`` as defined.
    """
    violations: list[Violation] = []
    # DEFINED = the RD appears anywhere in a decision-DEFINING doc. PROJECT_PLAN §5
    # carries most as table rows and §3 defines the topology decisions (RD-018/019/
    # 020) as bold prose; the Floor & Harvest plan formally proposes RD-022 before
    # C.5 copies it into the plan. Presence in either counts as defined.
    defined: set[str] = set()
    for rel in DECISION_DEFINING_DOCS:
        path = repo_root / rel
        if path.exists():
            defined.update(RD_REF_RE.findall(path.read_text(encoding="utf-8")))
    if not defined:
        return violations
    # REFERENCED = scanned across the LIVING core-governance docs only. Frozen
    # per-story briefs / PROMPTs and the schema READMEs are intentionally excluded
    # (e.g. RD-017, a known historical gap, is mentioned only in those frozen
    # artifacts as history — flagging it would "correct" a frozen snapshot).
    referenced: dict[str, str] = {}
    for rel in sorted(LIVING_DOCS):
        path = repo_root / rel
        if not path.exists():
            continue
        for ref in RD_REF_RE.findall(path.read_text(encoding="utf-8")):
            referenced.setdefault(ref, rel)
    for ref in sorted(referenced):
        if ref not in defined:
            violations.append(
                Violation(
                    check="CHECK E",
                    file=referenced[ref],
                    story_id=ref,
                    detail=(
                        f"references {ref} but it is not defined in the "
                        "PROJECT_PLAN registered-decisions table"
                    ),
                )
            )
    return violations


def check_f_stray_placeholders(repo_root: Path) -> list[Violation]:
    """CHECK F: no stray ``{{placeholder}}`` outside the known template files.

    Placeholder references written as INLINE CODE (``` `{{PROJECT_NAME}}` ```) are
    documentation about the convention and are ignored; a bare ``{{...}}`` in prose
    (outside the template files) is an unfilled placeholder and fires.
    """
    violations: list[Violation] = []
    for path in _iter_markdown_files(repo_root):
        rel = path.relative_to(repo_root).as_posix()
        if rel in TEMPLATE_FILES:
            continue
        prose = _strip_inline_code(path.read_text(encoding="utf-8"))
        hits = PLACEHOLDER_RE.findall(prose)
        if hits:
            violations.append(
                Violation(
                    check="CHECK F",
                    file=rel,
                    story_id=hits[0],
                    detail=(
                        f"stray unfilled placeholder(s) {sorted(set(hits))[:5]} "
                        "outside the known template files"
                    ),
                )
            )
    return violations


def check_g_done_without_validation(runbook_text: str) -> list[Violation]:
    """CHECK G: every ``✅`` story carries a dated Validation Result somewhere.

    A ``✅`` master-table story must have EITHER a filled ``Completed`` date in the
    master table OR a dated ``Validation Result`` line in STORY_DETAIL (the detail
    archive). To keep the check single-file and robust, we accept the master-table
    ``Completed`` date as the dated validation record: a ``✅`` row with an EMPTY
    Completed cell is the finding (an undated done story). Governance/F&H rows that
    legitimately carry ``-``/date are accepted; only a blank Completed on a ``✅``
    row fires.
    """
    violations: list[Violation] = []
    in_table = False
    story_index = status_index = completed_index = track_index = 0
    for line in runbook_text.splitlines():
        if "|" not in line:
            in_table = False
            continue
        cells = _split_row(line)
        if _header_has_columns(cells, STORY_TABLE_COLUMNS) and _header_has_columns(
            cells, ("completed", "track")
        ):
            in_table = True
            story_index = _column_index(cells, "story")
            status_index = _column_index(cells, "status")
            completed_index = _column_index(cells, "completed")
            track_index = _column_index(cells, "track")
            continue
        if not in_table or _is_separator_row(cells):
            continue
        if len(cells) <= max(story_index, status_index, completed_index, track_index):
            continue
        story_id = _clean_id(cells[story_index])
        if not ANY_STORY_ID_RE.match(story_id):
            continue
        if _status_marker(cells[status_index]) != DONE:
            continue
        # Scope to pipe + gov tracks: those carry the master-table Completed date as
        # their dated validation record (all such ✅ rows are dated today). F&H /
        # tenancy rows record their dated validation in the Floor & Harvest plan and
        # legitimately leave the Completed cell blank ("folds into floor"), so a
        # blank there is not a finding — do not back-date frozen F&H history.
        track = cells[track_index].strip().lower()
        if track not in {"pipe", "gov"}:
            continue
        completed = cells[completed_index].strip()
        # Accept an ISO-ish date or a non-empty dated note; a blank cell is the finding.
        if not completed or completed in {"-", "—"}:
            violations.append(
                Violation(
                    check="CHECK G",
                    file="RUNBOOK.md",
                    story_id=story_id,
                    detail=(
                        "story is ✅ Done but has no dated Completed / Validation "
                        "Result record (a done story must be dated)"
                    ),
                )
            )
    return violations


def parse_generated_phase_status(text: str) -> dict[str, str] | None:
    """Parse a doc's ``BEGIN/END GENERATED: phase-status`` block, if present.

    Returns ``{phase_label: status_marker}`` for the rows inside the delimited
    block, or ``None`` when the doc carries no such block. The block is a small
    pipe table ``| Phase | Status |`` whose values MUST be generated from (and are
    verified against) the RUNBOOK master table by CHECK H.
    """
    lines = text.splitlines()
    inside = False
    result: dict[str, str] = {}
    found = False
    for line in lines:
        if GEN_BEGIN in line:
            inside = True
            found = True
            continue
        if GEN_END in line:
            inside = False
            continue
        if not inside or "|" not in line:
            continue
        cells = _split_row(line)
        if _is_separator_row(cells) or len(cells) < 2:
            continue
        label = cells[0].strip()
        if label.lower() in {"phase", ""}:
            continue  # header row or blank
        # The status is whichever cell carries a legend marker (robust to the
        # region being a 2-column [Phase|Status] or 3-column [Phase|desc|Status]
        # table). Normalise the label to its ``Pn`` token so "P1 — Intake" and "P1"
        # both key as ``P1``.
        marker = next(
            (m for m in (_status_marker(cell) for cell in cells[1:]) if m), None
        )
        if marker is None:
            continue
        phase_key = re.match(r"P[0-9]+", label)
        result[phase_key.group(0) if phase_key else label] = marker
    return result if found else None


def parse_story_statuses_any(text: str) -> dict[str, str]:
    """Like ``parse_story_statuses`` but keyed by ``ANY_STORY_ID_RE`` so
    letter-minor IDs (``1.R``) and letter-track IDs (``A.4``/``T.1``) are included.

    Used by the phase roll-up (CHECK H), which must see every master-table story
    in a phase -- ``parse_story_statuses`` deliberately scopes to the pipe/gov
    register tracks and would drop ``1.R`` (leaving P1 falsely non-✅).
    """
    statuses: dict[str, str] = {}
    in_table = False
    story_index = status_index = 0
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
        if not in_table or _is_separator_row(cells):
            continue
        if len(cells) <= max(story_index, status_index):
            continue
        story_id = _clean_id(cells[story_index])
        if not ANY_STORY_ID_RE.match(story_id):
            continue
        marker = _status_marker(cells[status_index])
        if marker is not None:
            statuses[story_id] = marker
    return statuses


def _phase_rollup(runbook_text: str) -> dict[str, str]:
    """Derive each phase's rolled-up status from the RUNBOOK master table.

    A phase is ✅ only when every pipeline story in it is ✅; else 🟡 if any story
    is started/done (in progress); else ⬜. This is the authoritative status the
    generated living-doc region must mirror.
    """
    sets = parse_runbook_phase_story_sets(runbook_text)
    statuses = parse_story_statuses_any(runbook_text)
    rollup: dict[str, str] = {}
    for phase, ids in sets.items():
        if phase == "gov":
            continue
        markers = {statuses.get(sid, NOT_STARTED) for sid in ids}
        if markers == {DONE}:
            rollup[phase] = DONE
        elif markers & {DONE, IN_PROGRESS}:
            rollup[phase] = IN_PROGRESS
        else:
            rollup[phase] = NOT_STARTED
    return rollup


def _on_deck_target(repo_root: Path) -> str | None:
    """Return the story ID the on-deck starter points at, or None.

    The on-deck README's ``## Next session: Story <ID>`` heading is the single
    living pointer to the next starter; CHECK H/J read it.
    """
    on_deck = repo_root / "docs" / "session-briefs" / "on-deck" / "README.md"
    if not on_deck.exists():
        return None
    for line in on_deck.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^##\s+Next session:\s*Story\s+([0-9A-Za-z.\-]+)", line.strip())
        if m:
            return _clean_id(m.group(1))
    return None


def check_h_doc_drift(repo_root: Path, runbook_text: str) -> list[Violation]:
    """CHECK H: living-doc status must not drift from the RUNBOOK.

    Two drift classes, LIVING DOCS ONLY:
      (1) a doc's generated ``phase-status`` region disagrees with the RUNBOOK
          phase roll-up (README, BUILD_ORDER carry this delimited block);
      (2) the on-deck starter points at a story that is already ✅ in the RUNBOOK
          (a stale pointer).
    Frozen dated artifacts are never inspected.
    """
    violations: list[Violation] = []
    rollup = _phase_rollup(runbook_text)
    for rel in ("README.md", "docs/BUILD_ORDER.md"):
        path = repo_root / rel
        if not path.exists():
            continue
        generated = parse_generated_phase_status(path.read_text(encoding="utf-8"))
        if generated is None:
            continue
        for phase, marker in sorted(generated.items()):
            expected = rollup.get(phase)
            if expected is not None and marker != expected:
                violations.append(
                    Violation(
                        check="CHECK H",
                        file=rel,
                        story_id=phase,
                        detail=(
                            f"generated phase-status glyph {marker!r} disagrees "
                            f"with the RUNBOOK roll-up {expected!r}; regenerate the "
                            "block from the RUNBOOK master table (do not hand-edit)"
                        ),
                    )
                )
    statuses = parse_story_statuses(runbook_text)
    target = _on_deck_target(repo_root)
    if target is not None and statuses.get(target) == DONE:
        violations.append(
            Violation(
                check="CHECK H",
                file="docs/session-briefs/on-deck/README.md",
                story_id=target,
                detail=(
                    "on-deck starter points at a story that is already ✅ in the "
                    "RUNBOOK; repoint it at the next OPEN story"
                ),
            )
        )
    return violations


def check_i_dangling_links(repo_root: Path) -> list[Violation]:
    """CHECK I: every repo-relative ``*.md`` link target exists on disk.

    Only repo-relative links are checked; external (``http(s):``, ``mailto:``) and
    pure in-page ``#anchor`` links are skipped. A link with a ``#anchor`` suffix is
    checked for its FILE part only (anchor existence is not verified).
    """
    violations: list[Violation] = []
    # LIVING docs only: a broken link in a maintained doc is a defect to fix, but a
    # dated frozen brief/PROMPT is a snapshot we do not rewrite (its relative paths
    # were correct for where it was authored). Templates carry links relative to
    # where the FILLED file lands, not their own location, so they are excluded too.
    for rel in sorted(LIVING_DOCS):
        path = repo_root / rel
        if not path.exists():
            continue
        text = _strip_inline_code(path.read_text(encoding="utf-8"))
        for target in MD_LINK_RE.findall(text):
            target = target.strip()
            if not target or target.startswith("#"):
                continue
            if re.match(r"^[a-z][a-z0-9+.\-]*:", target):  # scheme -> external
                continue
            file_part = target.split("#", 1)[0].split("?", 1)[0]
            if not file_part:
                continue
            resolved = (path.parent / file_part).resolve()
            if not resolved.exists():
                violations.append(
                    Violation(
                        check="CHECK I",
                        file=rel,
                        story_id=file_part,
                        detail=f"links to {file_part!r} which does not exist",
                    )
                )
    return violations


# The literal tag a master-table row carries to declare itself a SECURITY-BOUNDARY
# story (RD-053 rule (a) / RD-054). Explicit + auditable: no heuristic guessing.
SEC_BOUNDARY_TAG = "[sec-boundary]"


def check_k_evidence_capture(repo_root: Path, runbook_text: str) -> list[Violation]:
    """CHECK K (RD-054): a ✅ SECURITY-BOUNDARY story must carry retained raw evidence.

    A master-table row tagged ``[sec-boundary]`` that is ``✅`` must have a durable
    evidence folder ``docs/validation-evidence/<story-id>/`` committed alongside the
    flip, and that folder must carry the four RD-054 markers so the pass is auditable
    (not testimony): a positive-exercise artifact, a proof-of-absence, a named+dated
    human attestation, and provenance pins (intake_id + commit SHA). To stay
    single-file + robust we assert the folder exists and its combined text contains
    the required marker tokens; the human supplies the actual raw artifacts.

    Non-security stories (untagged rows) are unaffected. Stories closed before RD-054
    are grandfathered by NOT carrying the tag; adding the tag opts a story in.
    """
    violations: list[Violation] = []
    # Required marker tokens (case-insensitive) that must appear across the folder's
    # files, mapping each RD-054 requirement to a searchable anchor.
    required = {
        "positive-exercise output": ("count", "finding"),
        "proof-of-absence": ("proof-of-absence", "zero match", "0 match", "returns 0", "no match"),
        "human attestation": ("attested by", "attestation", "verified by"),
        "provenance (intake_id)": ("intake_id", "intake id", "intake:"),
        "provenance (commit SHA)": ("commit", "sha"),
    }
    in_table = False
    story_index = status_index = 0
    for line in runbook_text.splitlines():
        if "|" not in line:
            in_table = False
            continue
        cells = _split_row(line)
        if _header_has_columns(cells, STORY_TABLE_COLUMNS):
            in_table = True
            story_index = _column_index(cells, "story")
            status_index = _column_index(cells, "status")
            continue
        if not in_table or _is_separator_row(cells):
            continue
        if len(cells) <= max(story_index, status_index):
            continue
        # The tag may appear anywhere in the row's cells (typically the Title cell).
        if SEC_BOUNDARY_TAG not in line:
            continue
        story_id = _clean_id(cells[story_index])
        if not ANY_STORY_ID_RE.match(story_id):
            continue
        if _status_marker(cells[status_index]) != DONE:
            continue  # only a ✅ sec-boundary story must carry evidence
        folder = repo_root / "docs" / "validation-evidence" / story_id
        if not folder.is_dir():
            violations.append(
                Violation(
                    check="CHECK K",
                    file="RUNBOOK.md",
                    story_id=story_id,
                    detail=(
                        f"is a ✅ security-boundary story but has no evidence folder "
                        f"docs/validation-evidence/{story_id}/ (RD-054: a security "
                        f"boundary ✅ rests on retained raw artifacts, not testimony)"
                    ),
                )
            )
            continue
        blob = ""
        for p in sorted(folder.rglob("*")):
            if p.is_file():
                try:
                    blob += p.read_text(encoding="utf-8", errors="replace").lower()
                except OSError:
                    pass
        missing = [
            label
            for label, tokens in required.items()
            if not any(tok in blob for tok in tokens)
        ]
        if missing:
            violations.append(
                Violation(
                    check="CHECK K",
                    file=f"docs/validation-evidence/{story_id}/",
                    story_id=story_id,
                    detail=(
                        "evidence folder is missing required RD-054 marker(s): "
                        + ", ".join(missing)
                    ),
                )
            )
    return violations


# A validation package's filename encodes its story id: story-<ID>-VALIDATION-PACKAGE.md
_VALIDATION_PACKAGE_RE = re.compile(r"story-(?P<id>.+)-VALIDATION-PACKAGE\.md$")
# The markers a package MUST contain to prove the mandatory full-context step is present.
_STEP15_MARKERS = ("STEP 1.5", "FULL CONTEXT FETCH")
# The raw-source accept header the full-context fetch relies on (must appear too, so the
# section is real instructions and not just a heading).
_RAW_ACCEPT_MARKER = "application/vnd.github.v3.raw"


def check_l_validation_package_full_context(
    repo_root: Path, runbook_text: str
) -> list[Violation]:
    """CHECK L: an OPEN story's validation package must carry the STEP 1.5 full-context fetch.

    Every ``docs/session-briefs/story-<ID>-VALIDATION-PACKAGE.md`` for a story that is
    still OPEN (``🟡``/``⛔``) must include the mandatory **STEP 1.5 — FULL CONTEXT
    FETCH** section: the full raw source (``application/vnd.github.v3.raw``) of the
    modified scripts/parsers/templates, pinned to the commit SHA — because a diff hides
    contextual leaks and wrapper-execution flaws (the Story 2.4 strace defect). This
    makes "we always include STEP 1.5" machine-enforced rather than a convention.

    Scope: OPEN stories only. A package for a CLOSED (``✅``) story is frozen history and
    is grandfathered (do not back-date a package authored before STEP 1.5 existed) — the
    same frozen-artifact discipline CHECK I uses.
    """
    violations: list[Violation] = []
    briefs = repo_root / "docs" / "session-briefs"
    if not briefs.is_dir():
        return violations
    statuses = parse_story_statuses_any(runbook_text)
    for path in sorted(briefs.glob("story-*-VALIDATION-PACKAGE.md")):
        m = _VALIDATION_PACKAGE_RE.search(path.name)
        if not m:
            continue
        story_id = m.group("id")
        # Only enforce on stories that are still OPEN; closed packages are frozen.
        if statuses.get(story_id) not in {IN_PROGRESS, BLOCKED}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        missing = [tok for tok in _STEP15_MARKERS if tok not in text]
        if _RAW_ACCEPT_MARKER not in text:
            missing.append(_RAW_ACCEPT_MARKER)
        if missing:
            violations.append(
                Violation(
                    check="CHECK L",
                    file=f"docs/session-briefs/{path.name}",
                    story_id=story_id,
                    detail=(
                        "OPEN story's validation package is missing the mandatory "
                        "STEP 1.5 / FULL CONTEXT FETCH (full raw source via "
                        "application/vnd.github.v3.raw, pinned to the commit SHA); "
                        "a diff alone hides wrapper-execution / contextual-leak flaws. "
                        "Missing marker(s): " + ", ".join(missing)
                    ),
                )
            )
    return violations


# A LIVE-RUNBOOK artifact's filename encodes its story id: story-<ID>-LIVE-RUNBOOK.md
# (also OD-<n>-LIVE-RUNBOOK.md). Under RD-055 the EXECUTOR (Kiro) is FORBIDDEN from
# authoring live-proof steps — the independent validator authors the live runbook each
# time, blind, from the PR number. A LIVE-RUNBOOK committed for an OPEN story is the
# concrete artifact-form of the split-brain breach the discipline exists to prevent.
_LIVE_RUNBOOK_RE = re.compile(r"^story-(?P<id>.+)-LIVE-RUNBOOK\.md$")


def check_o_no_executor_live_runbook(
    repo_root: Path, runbook_text: str
) -> list[Violation]:
    """CHECK O (split-brain, RD-055): no EXECUTOR-authored LIVE-RUNBOOK for an OPEN story.

    RD-055 pins that the executor's entire validation handoff is the **PR number
    only**: Kiro does NOT author a ``story-<id>-LIVE-RUNBOOK.md``, a test script, or
    any "how to prove it on live AWS" steps — the independent validator (Gemini)
    authors the live runbook + DoD from scratch, blind, each time. This check
    machine-enforces that for FORWARD work: a ``story-<ID>-LIVE-RUNBOOK.md`` present
    for a story that is still OPEN (``🟡``/``⛔``) fails, because it means live-proof
    framing was authored on the builder's side before/instead of the validator's.

    Scope + frozen-history discipline (mirrors CHECK L): only OPEN stories fire.
    LIVE-RUNBOOKs for CLOSED (``✅``) stories are frozen artifacts of the pre-RD-055
    era and are **grandfathered** — they are history, never rewritten to satisfy a
    checker. ``OD-<n>-LIVE-RUNBOOK.md`` files (operational-debt capture runbooks, a
    stakeholder read-only activity, not a story validation handoff) are not matched.
    """
    violations: list[Violation] = []
    briefs = repo_root / "docs" / "session-briefs"
    if not briefs.is_dir():
        return violations
    statuses = parse_story_statuses_any(runbook_text)
    for path in sorted(briefs.glob("story-*-LIVE-RUNBOOK.md")):
        m = _LIVE_RUNBOOK_RE.match(path.name)
        if not m:
            continue
        story_id = m.group("id")
        if statuses.get(story_id) not in {IN_PROGRESS, BLOCKED}:
            continue  # closed/absent stories are frozen history — grandfathered
        violations.append(
            Violation(
                check="CHECK O",
                file=f"docs/session-briefs/{path.name}",
                story_id=story_id,
                detail=(
                    "an OPEN story has an executor-authored LIVE-RUNBOOK, which "
                    "RD-055 forbids: Kiro's validation handoff is the PR number "
                    "ONLY — the independent validator authors the live runbook + "
                    "DoD from scratch, blind. Remove the LIVE-RUNBOOK; do not "
                    "author live-proof steps on the builder side."
                ),
            )
        )
    return violations


# The heading under which the hand-maintained phase roll-up table lives. The
# Progress Summary is a LIVING surface (a ``| Phase | Scope | Gate | Status |``
# table) that a human edits at phase-close; CHECK N verifies it against the
# machine-derived roll-up so a skipped phase-gate (every story ✅ but the phase row
# never advanced) cannot pass silently.
PROGRESS_SUMMARY_HEADING = "## Progress Summary"


def parse_progress_summary_status(runbook_text: str) -> dict[str, str]:
    """Return the Progress Summary table's hand-kept ``{Pn: status_marker}`` map.

    The Progress Summary is the human-facing phase roll-up table under the
    ``## Progress Summary`` heading, shaped ``| Phase | Scope | Gate | Status |``
    with each row leading with a ``**Pn — …**`` phase label. Unlike the generated
    ``phase-status`` block (CHECK H), this table is hand-maintained — it is where a
    phase is marked ✅ at phase-close — so it can drift from the real story roll-up
    if the end-of-phase gate is skipped. This parser reads it so CHECK N can
    compare the two. The phase label is normalised to its ``Pn`` token.
    """
    result: dict[str, str] = {}
    in_section = False
    in_table = False
    phase_index = status_index = 0
    for line in runbook_text.splitlines():
        if line.startswith("## "):
            # Enter the section at its heading; leave at the NEXT level-2 heading.
            in_section = line.strip() == PROGRESS_SUMMARY_HEADING
            in_table = False
            continue
        if not in_section or "|" not in line:
            continue
        cells = _split_row(line)
        if _header_has_columns(cells, ("phase", "status")):
            in_table = True
            phase_index = _column_index(cells, "phase")
            status_index = _column_index(cells, "status")
            continue
        if not in_table or _is_separator_row(cells):
            continue
        if len(cells) <= max(phase_index, status_index):
            continue
        label = cells[phase_index]
        phase_key = re.search(r"P[0-9]+", label)
        if phase_key is None:
            continue
        marker = _status_marker(cells[status_index])
        if marker is not None:
            result[phase_key.group(0)] = marker
    return result


def check_n_phase_gate(repo_root: Path, runbook_text: str) -> list[Violation]:
    """CHECK N (phase-gate, HARD): the Progress Summary may never claim a phase is
    MORE complete than its stories.

    ``_phase_rollup`` derives each phase's TRUE status from the master story table
    (✅ only when every story in the phase is ✅); ``parse_progress_summary_status``
    reads the hand-maintained Progress Summary row. CHECK N hard-fails on the
    **contradiction** direction only: the Progress Summary row is ✅ but the roll-up
    is not (a story in the phase is still ⬜/🟡/⛔, or regressed). A phase cannot be
    marked done while a story it contains is not — that is a lie in the ledger, the
    same management-artifact-integrity class (RD-015) CHECK H guards for the
    generated block, so it blocks.

    The OPPOSITE direction — every story ✅ but the phase row not yet ✅ (the
    **skipped end-of-phase gate**, exactly the Phase 1 drift) — is handled by the
    ADVISORY ``phase_gate_advisories`` below, NOT here: closing a phase is a
    stakeholder-confirmed event (run the gate + capture the restore point), not
    something a checker should auto-trip or wedge the main line red over. It is
    surfaced loudly on every run instead (impossible to miss, non-blocking),
    mirroring the Operational Debt register and CHECK J.

    Phases the Progress Summary does not enumerate are not compared.
    """
    violations: list[Violation] = []
    rollup = _phase_rollup(runbook_text)
    summary = parse_progress_summary_status(runbook_text)
    for phase, shown in sorted(summary.items()):
        true_marker = rollup.get(phase)
        if true_marker is None or shown != DONE or true_marker == DONE:
            continue
        violations.append(
            Violation(
                check="CHECK N",
                file="RUNBOOK.md",
                story_id=phase,
                detail=(
                    f"the Progress Summary marks phase {phase} ✅ but its story "
                    f"roll-up is {true_marker!r}: a phase may not be ✅ while a story "
                    "it contains is not. Reconcile the phase row to the roll-up (a "
                    "phase closes only after every story in it is ✅)."
                ),
            )
        )
    return violations


def phase_gate_advisories(repo_root: Path, runbook_text: str) -> list[Violation]:
    """ADVISORY: name every phase that is STORY-COMPLETE but not yet CLOSED.

    This is the un-missable, non-blocking backstop for the **end-of-phase
    validation** that was previously left to human memory (the Phase 1 miss). When
    every story in a phase is ✅ (roll-up ``✅``) but the Progress Summary row is not
    yet ✅, the phase's end-of-phase gate has not been run + recorded and its
    restore point / BOM row may be owed. We do NOT auto-close it (that is a
    stakeholder-confirmed act, §Phase gate) and we do NOT hard-fail the build over
    it (a red main for an un-run gate wedges unrelated work). Instead we print it as
    an advisory on EVERY run — the same treatment as the Operational Debt register —
    so the owed phase-gate can never silently slip the way Phase 1 did.
    """
    advisories: list[Violation] = []
    rollup = _phase_rollup(runbook_text)
    summary = parse_progress_summary_status(runbook_text)
    for phase, true_marker in sorted(rollup.items()):
        if true_marker != DONE:
            continue
        if summary.get(phase) == DONE:
            continue  # already closed
        advisories.append(
            Violation(
                check="CHECK N (advisory)",
                file="RUNBOOK.md",
                story_id=phase,
                detail=(
                    f"phase {phase} is STORY-COMPLETE (every story ✅) but its "
                    "end-of-phase gate has not been recorded and the phase row is "
                    "not ✅. PHASE-GATE CLOSE OWED: run the phase's end-of-phase "
                    "gate, capture/confirm its restore point (RESTORE.md + BOM.md), "
                    "record the gate pass, then flip the Progress Summary row to ✅. "
                    "A story-complete phase is NOT a closed phase."
                ),
            )
        )
    return advisories


def check_j_sequence_adherence(
    repo_root: Path, runbook_text: str
) -> list[Violation]:
    """CHECK J (ADVISORY): the on-deck starter should be the first OPEN item.

    The RUNBOOK "Ready now" schedule (bucket A) lists the schedulable stories
    top-down; the FIRST open (non-✅) row is the scheduled next story. If the
    on-deck starter points elsewhere it MAY be a legitimate stakeholder reorder,
    so this is ADVISORY: it returns a violation tagged ``CHECK J (advisory)`` that
    ``main`` prints as a WARNING and does NOT count toward the exit code. It fires
    only when a clean mechanical signal exists (a parseable Ready-now bucket and an
    on-deck target); otherwise it stays silent.
    """
    violations: list[Violation] = []
    target = _on_deck_target(repo_root)
    if target is None:
        return violations
    first_open = _first_open_ready_story(runbook_text)
    if first_open is None:
        return violations
    if target != first_open:
        violations.append(
            Violation(
                check="CHECK J (advisory)",
                file="docs/session-briefs/on-deck/README.md",
                story_id=target,
                detail=(
                    f"on-deck starter is {target!r} but the first OPEN item in the "
                    f"RUNBOOK 'Ready now' schedule is {first_open!r}; if this is an "
                    "intended reorder, record it in WORK_LOG (advisory only)"
                ),
            )
        )
    return violations


def _first_open_ready_story(runbook_text: str) -> str | None:
    """Return the first non-✅ story ID in the RUNBOOK 'Ready now' (bucket A) table.

    Bucket A is the table under the ``**A. Ready now`` heading. Rows whose story
    cell is struck through (``~~G-3~~``, meaning closed) are skipped; the first row
    whose story is NOT ✅ in the master table is the scheduled next story. Returns
    None when the bucket cannot be parsed (no clean signal -> CHECK J stays silent).
    """
    lines = runbook_text.splitlines()
    statuses = parse_story_statuses(runbook_text)
    in_bucket = False
    story_index = 0
    for line in lines:
        if line.lstrip().startswith("**A. Ready now"):
            in_bucket = True
            continue
        if in_bucket and line.lstrip().startswith(("**B.", "**C.", "## ", "### ")):
            break
        if not in_bucket or "|" not in line:
            continue
        cells = _split_row(line)
        if _header_has_columns(cells, ("story",)):
            story_index = _column_index(cells, "story")
            continue
        if _is_separator_row(cells) or len(cells) <= story_index:
            continue
        raw = cells[story_index].strip()
        if raw.startswith("~~"):  # struck-through = closed, skip
            continue
        story_id = _clean_id(raw)
        if not BUILD_ORDER_ID_RE.match(story_id):
            continue
        if statuses.get(story_id) != DONE:
            return story_id
    return None


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

    # --- G-2 integrity + doc-drift checks (CHECK D..I) -------------------------
    plan_path = repo_root / "PROJECT_PLAN.md"
    plan_text = plan_path.read_text(encoding="utf-8") if plan_path.exists() else ""
    if plan_text:
        violations.extend(check_d_plan_runbook_divergence(plan_text, text))
    violations.extend(check_e_dangling_rd_refs(repo_root))
    violations.extend(check_f_stray_placeholders(repo_root))
    violations.extend(check_g_done_without_validation(text))
    violations.extend(check_h_doc_drift(repo_root, text))
    violations.extend(check_i_dangling_links(repo_root))
    violations.extend(check_k_evidence_capture(repo_root, text))
    violations.extend(check_l_validation_package_full_context(repo_root, text))
    violations.extend(check_o_no_executor_live_runbook(repo_root, text))
    violations.extend(check_n_phase_gate(repo_root, text))
    return violations


def run_advisories(repo_root: Path) -> list[Violation]:
    """Run the ADVISORY checks (CHECK J). These are surfaced as warnings and do
    NOT affect the exit code -- a reorder is a legitimate stakeholder decision."""
    runbook_path = repo_root / "RUNBOOK.md"
    if not runbook_path.exists():
        return []
    text = runbook_path.read_text(encoding="utf-8")
    advisories = phase_gate_advisories(repo_root, text)
    advisories.extend(check_j_sequence_adherence(repo_root, text))
    return advisories


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

    # ADVISORY checks (CHECK J -- sequence adherence). Printed as a warning; they
    # NEVER affect the exit code, because a reorder is a legitimate stakeholder
    # decision (RD-024). Surfaced here so a stale/out-of-order on-deck is visible.
    advisories = run_advisories(repo_root)
    if advisories:
        print(f"check_docs: ADVISORY -- {len(advisories)} note(s) "
              "(informational; does not block):")
        for advisory in advisories:
            print(f"  {advisory.render()}")

    violations = run_checks(repo_root)
    if violations:
        print(f"check_docs: FAIL -- {len(violations)} violation(s):")
        for violation in violations:
            print(f"  {violation.render()}")
        return 1
    print(
        "check_docs: PASS -- register + advancement gate + schedule order + "
        "management-artifact integrity (plan/runbook, RD refs, placeholders, "
        "validation dates, doc-drift, links, phase-gate) all satisfied"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
