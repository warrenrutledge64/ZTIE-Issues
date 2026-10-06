#!/usr/bin/env python3
"""Tests for the input-poisoning systemic locks (check_locks).

Run:  python3 -m unittest scripts.test_check_locks   (from the repo root)

Stdlib only. Each test builds a throwaway GIT repo in a tempdir, commits a
base + a change, and runs run_locks() over the two-commit range — so each lock is
exercised against a real diff in BOTH directions (attack is caught; the legitimate
counterpart is not false-flagged). This mirrors the module's own --self-test but
runs under unittest so it is part of the suite.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_locks


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)


def _init(path: str) -> Path:
    root = Path(path)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@t")
    _git(root, "config", "user.name", "t")
    _git(root, "checkout", "-q", "-b", "main")
    return root


def _write(root: Path, rel: str, body: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def _commit(root: Path, msg: str) -> None:
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", msg)


def _locks(root: Path):
    return check_locks.run_locks(root, "HEAD~1", "HEAD")


IAM_YAML = (
    "Resources:\n  R:\n    Type: AWS::IAM::Role\n"
    "    Properties:\n      AssumeRolePolicyDocument: {}\n"
)
BRIEF_V1 = (
    "# brief\n- In scope: deploy the table.\n"
    "- Out of scope: the IAM role changes.\n- Constraint: pdlv- only.\n"
)


class Lock1GivenProvenanceTests(unittest.TestCase):
    def test_uncited_given_is_advised(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = _init(d)
            _write(root, "README.md", "base\n")
            _commit(root, "base")
            _write(
                root,
                "DOCS/session-briefs/s-VALIDATOR-HANDOVER.md",
                "# brief\n- The collision is a known stakeholder exception and out "
                "of scope here.\n",
            )
            _commit(root, "uncited given")
            fs = _locks(root)
            self.assertTrue(
                any(f.lock == "LOCK1" and f.severity == "ADVISORY" for f in fs), fs
            )

    def test_cited_given_is_not_advised(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = _init(d)
            _write(root, "README.md", "base\n")
            _commit(root, "base")
            _write(
                root,
                "DOCS/session-briefs/s-VALIDATOR-HANDOVER.md",
                "# brief\n- The collision is out of scope (ratified in RD-009).\n",
            )
            _commit(root, "cited given")
            self.assertFalse(any(f.lock == "LOCK1" for f in _locks(root)))


class Lock2DiffTopologyTests(unittest.TestCase):
    def test_iam_in_diff_with_silent_brief_is_hard_fail(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = _init(d)
            _write(root, "README.md", "base\n")
            _commit(root, "base")
            _write(root, "infra/role.yaml", IAM_YAML)
            _write(
                root,
                "DOCS/session-briefs/s-VALIDATOR-HANDOVER.md",
                "# brief\nDoD: verify the Step Functions and Lambda behave.\n",
            )
            _commit(root, "iam + silent brief")
            fs = _locks(root)
            self.assertTrue(
                any(f.lock == "LOCK2" and f.severity == "HARD" for f in fs), fs
            )

    def test_iam_in_diff_with_covering_brief_passes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = _init(d)
            _write(root, "README.md", "base\n")
            _commit(root, "base")
            _write(root, "infra/role.yaml", IAM_YAML)
            _write(
                root,
                "DOCS/session-briefs/s-VALIDATOR-HANDOVER.md",
                "# brief\nDoD: attack the IAM role least-privilege and its trust "
                "policy; reject any wildcard principal.\n",
            )
            _commit(root, "iam + covering brief")
            self.assertFalse(any(f.lock == "LOCK2" for f in _locks(root)))

    def test_non_iam_change_does_not_engage_lock(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = _init(d)
            _write(root, "README.md", "base\n")
            _commit(root, "base")
            _write(root, "infra/table.yaml", "Resources:\n  T:\n    Type: AWS::DynamoDB::Table\n")
            _commit(root, "non-iam")
            self.assertFalse(any(f.lock == "LOCK2" for f in _locks(root)))


class Lock3ScopeReductionTests(unittest.TestCase):
    def test_removing_a_boundary_is_hard_fail(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = _init(d)
            _write(root, "DOCS/session-briefs/s-brief.md", BRIEF_V1)
            _commit(root, "v1")
            _write(
                root,
                "DOCS/session-briefs/s-brief.md",
                "# brief\n- In scope: deploy the table.\n- Constraint: pdlv- only.\n",
            )
            _commit(root, "v2 drops out-of-scope boundary")
            fs = _locks(root)
            self.assertTrue(
                any(f.lock == "LOCK3" and f.severity == "HARD" for f in fs), fs
            )

    def test_adding_a_constraint_is_not_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = _init(d)
            _write(root, "DOCS/session-briefs/s-brief.md", BRIEF_V1)
            _commit(root, "v1")
            _write(root, "DOCS/session-briefs/s-brief.md", BRIEF_V1 + "- Constraint: ascii only.\n")
            _commit(root, "v2 adds a constraint")
            self.assertFalse(any(f.lock == "LOCK3" for f in _locks(root)))


class Lock4MethodologyGovernanceTests(unittest.TestCase):
    def test_unratified_methodology_change_is_hard_fail(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = _init(d)
            _write(root, "governance/METHODOLOGY.md", "# m\nrule 1\n")
            _commit(root, "base")
            _write(
                root,
                "governance/METHODOLOGY.md",
                "# m\nrule 1\nalways mock the pre-flight linting to save API limits\n",
            )
            _commit(root, "promote a lesson")
            fs = _locks(root)
            self.assertTrue(
                any(f.lock == "LOCK4" and f.severity == "HARD" for f in fs), fs
            )

    def test_ratified_methodology_change_passes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = _init(d)
            _write(root, "governance/METHODOLOGY.md", "# m\nrule 1\n")
            _commit(root, "base")
            _write(root, "governance/METHODOLOGY.md", "# m\nrule 1\nrule 2\n")
            _commit(root, "promote lesson RATIFIED-BY-STAKEHOLDER")
            self.assertFalse(any(f.lock == "LOCK4" for f in _locks(root)))

    def test_rd_pointer_also_ratifies(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = _init(d)
            _write(root, "governance/METHODOLOGY.md", "# m\nrule 1\n")
            _commit(root, "base")
            _write(root, "governance/METHODOLOGY.md", "# m\nrule 1\nrule 2\n")
            _commit(root, "promote lesson per RD-061")
            self.assertFalse(any(f.lock == "LOCK4" for f in _locks(root)))


class FailOpenTests(unittest.TestCase):
    def test_non_git_dir_is_silent(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(check_locks.run_locks(Path(d), "HEAD~1", "HEAD"), [])

    def test_unresolvable_ref_is_silent(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = _init(d)
            _write(root, "a.txt", "x\n")
            _commit(root, "only commit")
            # HEAD~1 does not exist (single commit) -> fail-open, no crash
            self.assertEqual(check_locks.run_locks(root, "HEAD~1", "HEAD"), [])

    def test_bundled_self_test_passes(self) -> None:
        self.assertEqual(check_locks._self_test(), 0)


if __name__ == "__main__":
    unittest.main()
