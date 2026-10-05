#!/usr/bin/env python3
"""Systemic locks against INPUT-poisoning of the split-brain validation (generic).

The split-brain covenant stops the builder from authoring the JUDGMENT (the DoD /
rubric). It does NOT, by itself, stop the builder from poisoning the INPUTS the
validator reasons from — the "givens", the topology map, the standing lessons.
These four locks turn that remaining procedural trust into enforced invariants.

Attack vectors (from an adversarial review) and the lock that closes each:

  LOCK 1  Semantic smuggling -- the builder rigs the validator brief's "given" /
          scope-boundary section with a FALSE given ("X is a known stakeholder
          exception, out of scope") so the blind validator authors a weak DoD.
          LOCK: a scope-boundary / "given" that asserts something is out of scope
          or a ratified exception, with NO record pointer (RD-### / decision
          record), is an UNVERIFIED builder assertion -> ADVISORY flag (paired
          with the template directive telling the validator to ATTACK un-cited
          givens). Advisory, not hard: a legitimately-cited given is the norm, and
          over-blocking here would push givens out of the brief entirely.

  LOCK 2  Lie by omission -- the builder omits IAM from the brief's topology map,
          so the blind validator never authors a privilege-escalation check even
          though the backdoor is right there in the diff.
          LOCK: scan the raw DIFF (objective repo truth, not the curated brief) for
          an added IAM/trust/privilege change (AWS::IAM::*, a trust/assume-role
          policy, or a `Resource: "*"` / `Action: "*"` wildcard). If the diff adds
          one but the validator brief's DoD does NOT target IAM/privilege/trust ->
          HARD FAIL. Binds the validator to the diff, not the brief.

  LOCK 3  Advisory bypass -- the builder buries a subtle SCOPE REDUCTION in
          conversational noise, betting a tired human ignores the volume advisory.
          LOCK: the dangerous payload is the scope reduction itself, which is
          unambiguous -> compare a handoff against its PREVIOUS committed version;
          if a scope / boundary / deliverable / constraint bullet was REMOVED ->
          HARD FAIL. (Volume stays advisory in check_docs; shrinkage is hard.)

  LOCK 4  Poisoning the standing OS -- the builder promotes a shield-lowering
          "general lesson" into METHODOLOGY.md, rewriting the OS for every spawn.
          LOCK: any diff that touches METHODOLOGY.md is a PRIVILEGED change ->
          HARD FAIL unless the commit range carries an explicit ratification
          marker (RATIFIED-BY-STAKEHOLDER, or an RD-### pointer). Promotion becomes
          a stakeholder ratification act, not a silent builder commit.

Design notes:
  * GIT-SOURCED but ISOLATED. Locks 2/3/4 need a diff + commit messages; this
    module takes an explicit base..head ref range so it is deterministic and
    unit-testable, and FAIL-OPEN when git / the range / the artifacts are absent
    (so a partially-adopted repo or a non-git checkout is never spuriously blocked).
  * check_docs.py stays the pure-filesystem gate; it calls run_locks() only when a
    git repo + a resolvable range exist.

Usage:
    python3 scripts/check_locks.py --base origin/main --head HEAD
    python3 scripts/check_locks.py --self-test

Exit codes:
    0  PASS (no HARD violations; advisories may print)
    1  FAIL (one or more HARD lock violations)
    2  usage / environment error
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# ---- shapes we recognize --------------------------------------------------

# A validator brief (the artifact Lock 1 + Lock 2 reason about). Instances name this
# differently -- the kit/pde use "-validator-handover.md"; ZTIE uses
# "-validation-package.md" (+ "-validator-handover.md" for phase gates). Recognize both
# so the lock is instance-agnostic.
VALIDATOR_BRIEF_SUFFIXES = ("-validator-handover.md", "-validation-package.md")
# Handoff artifacts Lock 3 (scope-reduction) guards.
HANDOFF_SUFFIXES = (
    "-prompt.md",
    "-validator-handover.md",
    "-validation-package.md",
    "-brief.md",
)

# Lock 1: a line that asserts a scope boundary / "given".
_GIVEN_RE = re.compile(
    r"\b(out of scope|out-of-scope|known (?:stakeholder )?exception|"
    r"treat as a given|is a given|already (?:ratified|approved|accepted)|"
    r"not in scope|exempt(?:ed)? from|waived)\b",
    re.IGNORECASE,
)
# A citation that legitimizes a given / decision.
_RECORD_REF_RE = re.compile(r"\b(RD-\d{2,}|decision record|RATIFIED-BY-STAKEHOLDER)\b", re.IGNORECASE)

# Lock 2: IAM / privilege / trust surface in a diff's ADDED lines.
_IAM_RESOURCE_RE = re.compile(r"AWS::IAM::", re.IGNORECASE)
_TRUST_RE = re.compile(r"AssumeRolePolicyDocument|sts:AssumeRole|Principal\s*:", re.IGNORECASE)
_WILDCARD_RE = re.compile(r"""(Resource|Action)\s*:\s*['"]?\*['"]?""", re.IGNORECASE)
# A validator brief that DOES target IAM/privilege in its DoD.
_DOD_IAM_RE = re.compile(
    r"\b(IAM|least[- ]privilege|privilege|trust polic|assume[- ]?role|"
    r"permission(?:s)? boundary|wildcard|principal)\b",
    re.IGNORECASE,
)

# Lock 3: a bullet that states a scope boundary / deliverable / constraint.
_SCOPE_BULLET_RE = re.compile(
    r"^\s*[-*]\s*\**\s*(in scope|out of scope|out-of-scope|deliverable|"
    r"constraint|hard constraint|must not|do not touch|boundary|depends on)\b",
    re.IGNORECASE,
)

# Lock 4: ratification marker in a commit message range.
_RATIFY_MARKER_RE = re.compile(r"\b(RATIFIED-BY-STAKEHOLDER|RD-\d{2,})\b")


@dataclass
class Finding:
    lock: str
    severity: str  # "HARD" | "ADVISORY"
    where: str
    detail: str

    def render(self) -> str:
        return f"[{self.lock}/{self.severity}] {self.where}: {self.detail}"


# ---- git helpers (all fail-open) ------------------------------------------


def _git(root: Path, *args: str) -> tuple[int, str]:
    try:
        p = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        return p.returncode, p.stdout
    except FileNotFoundError:
        return 127, ""


def _is_git_repo(root: Path) -> bool:
    rc, _ = _git(root, "rev-parse", "--is-inside-work-tree")
    return rc == 0


def _rev_ok(root: Path, ref: str) -> bool:
    rc, _ = _git(root, "rev-parse", "--verify", "--quiet", ref)
    return rc == 0


def _changed_files(root: Path, base: str, head: str) -> list[str]:
    rc, out = _git(root, "diff", "--name-only", f"{base}..{head}")
    return [ln for ln in out.splitlines() if ln.strip()] if rc == 0 else []


def _added_lines(root: Path, base: str, head: str, path: str) -> list[str]:
    """ADDED lines (leading '+', excluding the +++ header) for one file in a diff."""
    rc, out = _git(root, "diff", f"{base}..{head}", "--", path)
    if rc != 0:
        return []
    added: list[str] = []
    for ln in out.splitlines():
        if ln.startswith("+") and not ln.startswith("+++"):
            added.append(ln[1:])
    return added


def _file_at(root: Path, ref: str, path: str) -> str | None:
    rc, out = _git(root, "show", f"{ref}:{path}")
    return out if rc == 0 else None


def _commit_messages(root: Path, base: str, head: str) -> str:
    rc, out = _git(root, "log", "--format=%B", f"{base}..{head}")
    return out if rc == 0 else ""


# ---- LOCK 1 : provenance of "givens" (advisory) ---------------------------


def lock1_given_provenance(root: Path, base: str, head: str) -> list[Finding]:
    out: list[Finding] = []
    for path in _changed_files(root, base, head):
        if not path.lower().endswith(VALIDATOR_BRIEF_SUFFIXES):
            continue
        text = _file_at(root, head, path)
        if text is None:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if _GIVEN_RE.search(line) and not _RECORD_REF_RE.search(line):
                out.append(
                    Finding(
                        "LOCK1",
                        "ADVISORY",
                        f"{Path(path).name}:{i}",
                        "a scope-boundary / 'given' asserts an exception or "
                        "out-of-scope with NO record pointer (RD-### / decision "
                        "record) -- treat as an UNVERIFIED builder assertion; the "
                        "validator must ATTACK it, not accept it. Cite the "
                        "ratified decision or remove the claim",
                    )
                )
    return out


# ---- LOCK 2 : diff-derived topology (hard) --------------------------------


def _diff_adds_iam(root: Path, base: str, head: str) -> list[str]:
    """Files whose ADDED diff lines introduce an IAM/trust/privilege surface."""
    hits: list[str] = []
    for path in _changed_files(root, base, head):
        # only inspect infra-ish text; skip the briefs themselves + binaries
        if path.lower().endswith(HANDOFF_SUFFIXES):
            continue
        added = _added_lines(root, base, head, path)
        blob = "\n".join(added)
        if (
            _IAM_RESOURCE_RE.search(blob)
            or _TRUST_RE.search(blob)
            or _WILDCARD_RE.search(blob)
        ):
            hits.append(path)
    return hits


def lock2_diff_derived_topology(root: Path, base: str, head: str) -> list[Finding]:
    iam_files = _diff_adds_iam(root, base, head)
    if not iam_files:
        return []  # no privilege surface added -> lock not engaged
    # Does ANY validator brief changed in this range target IAM/privilege?
    briefs = [
        p for p in _changed_files(root, base, head)
        if p.lower().endswith(VALIDATOR_BRIEF_SUFFIXES)
    ]
    if not briefs:
        return [
            Finding(
                "LOCK2",
                "HARD",
                ", ".join(Path(f).name for f in iam_files),
                "the diff adds an IAM / trust-policy / wildcard-privilege change "
                "but NO validator brief in this change targets it. The validator "
                "is bound to the DIFF, not the builder's brief -- author a brief "
                "whose DoD attacks this privilege change (lie-by-omission lock)",
            )
        ]
    covered = False
    for b in briefs:
        text = _file_at(root, head, b) or ""
        if _DOD_IAM_RE.search(text):
            covered = True
            break
    if covered:
        return []
    return [
        Finding(
            "LOCK2",
            "HARD",
            ", ".join(Path(f).name for f in iam_files),
            "the diff adds an IAM / trust-policy / wildcard-privilege change but "
            "the validator brief does NOT target IAM/privilege/trust in its DoD "
            "(lie-by-omission). Add an adversarial privilege-escalation check tied "
            "to this diff before the brief is used",
        )
    ]


# ---- LOCK 3 : scope-reduction (hard) --------------------------------------


def _scope_bullets(text: str) -> set[str]:
    out: set[str] = set()
    for line in text.splitlines():
        if _SCOPE_BULLET_RE.match(line):
            out.add(" ".join(line.split()).lower())
    return out


def lock3_scope_reduction(root: Path, base: str, head: str) -> list[Finding]:
    out: list[Finding] = []
    for path in _changed_files(root, base, head):
        if not path.lower().endswith(HANDOFF_SUFFIXES):
            continue
        before = _file_at(root, base, path)
        after = _file_at(root, head, path)
        if before is None or after is None:
            continue  # newly-added or deleted handoff -> no prior scope to shrink
        removed = _scope_bullets(before) - _scope_bullets(after)
        if removed:
            sample = next(iter(sorted(removed)))[:80]
            out.append(
                Finding(
                    "LOCK3",
                    "HARD",
                    Path(path).name,
                    f"{len(removed)} scope/boundary/deliverable/constraint bullet(s) "
                    f"REMOVED vs the prior committed version (e.g. '{sample}…'). A "
                    "silent scope reduction is the advisory-bypass payload -- restore "
                    "it, or record an explicit stakeholder-ratified scope change",
                )
            )
    return out


# ---- LOCK 4 : METHODOLOGY governance (hard) -------------------------------


def lock4_methodology_governance(root: Path, base: str, head: str) -> list[Finding]:
    touched = [
        p for p in _changed_files(root, base, head)
        if Path(p).name == "METHODOLOGY.md"
    ]
    if not touched:
        return []
    msgs = _commit_messages(root, base, head)
    if _RATIFY_MARKER_RE.search(msgs):
        return []
    return [
        Finding(
            "LOCK4",
            "HARD",
            ", ".join(touched),
            "METHODOLOGY.md (the standing OS) was changed with NO ratification "
            "marker in the commit range. Promotion into the standing layer is a "
            "STAKEHOLDER act, not a silent builder commit -- the commit must carry "
            "'RATIFIED-BY-STAKEHOLDER' or an RD-### pointer (OS-poisoning lock)",
        )
    ]


# ---- driver ---------------------------------------------------------------


def run_locks(root: Path, base: str, head: str) -> list[Finding]:
    """All four locks. Fail-open: returns [] if not a git repo or refs unresolved."""
    if not _is_git_repo(root) or not _rev_ok(root, base) or not _rev_ok(root, head):
        return []
    out: list[Finding] = []
    out += lock1_given_provenance(root, base, head)
    out += lock2_diff_derived_topology(root, base, head)
    out += lock3_scope_reduction(root, base, head)
    out += lock4_methodology_governance(root, base, head)
    return out


def _print(findings: list[Finding]) -> int:
    hard = [f for f in findings if f.severity == "HARD"]
    adv = [f for f in findings if f.severity == "ADVISORY"]
    for f in adv:
        print(f"  {f.render()}")
    for f in hard:
        print(f"  {f.render()}")
    if hard:
        print(f"check_locks: FAIL -- {len(hard)} hard lock violation(s)"
              + (f" (+{len(adv)} advisory)" if adv else ""))
        return 1
    if adv:
        print(f"check_locks: PASS -- {len(adv)} advisory(ies), 0 hard violations")
    else:
        print("check_locks: PASS -- no lock violations")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--base", default="origin/main", help="base ref of the change range")
    ap.add_argument("--head", default="HEAD", help="head ref of the change range")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        return _self_test()
    return _print(run_locks(Path(args.repo_root), args.base, args.head))


# ---- adversarial self-test (builds throwaway git repos) -------------------


def _self_test() -> int:  # noqa: C901 - a flat sequence of sabotage cases
    import tempfile

    failures: list[str] = []

    def _repo(path: str) -> Path:
        root = Path(path)
        _git(root, "init", "-q")
        _git(root, "config", "user.email", "t@t")
        _git(root, "config", "user.name", "t")
        _git(root, "checkout", "-q", "-b", "main")
        return root

    def _commit(root: Path, msg: str) -> None:
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", msg)

    def _write(root: Path, rel: str, body: str) -> None:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")

    def _check(name: str, cond: bool) -> None:
        if not cond:
            failures.append(name)

    # ---- LOCK 1: un-cited given flags; cited given does not ----
    with tempfile.TemporaryDirectory() as d:
        root = _repo(d)
        _write(root, "README.md", "base\n")
        _commit(root, "base")
        sb = "DOCS/session-briefs/story-x-VALIDATOR-HANDOVER.md"
        _write(root, sb, "# brief\n- The PDE-Orchestrator collision is a known "
                         "stakeholder exception and out of scope for this deploy.\n")
        _commit(root, "add brief (uncited given)")
        f = run_locks(root, "HEAD~1", "HEAD")
        _check("L1 uncited-given flagged",
               any(x.lock == "LOCK1" and x.severity == "ADVISORY" for x in f))

    with tempfile.TemporaryDirectory() as d:
        root = _repo(d)
        _write(root, "README.md", "base\n")
        _commit(root, "base")
        sb = "DOCS/session-briefs/story-x-VALIDATOR-HANDOVER.md"
        _write(root, sb, "# brief\n- The collision is out of scope (ratified in "
                         "RD-009).\n")
        _commit(root, "add brief (cited given)")
        f = run_locks(root, "HEAD~1", "HEAD")
        _check("L1 cited-given NOT flagged",
               not any(x.lock == "LOCK1" for x in f))

    # ---- LOCK 1 (alt naming): ZTIE-style *-VALIDATION-PACKAGE.md also recognized ----
    with tempfile.TemporaryDirectory() as d:
        root = _repo(d)
        _write(root, "README.md", "base\n")
        _commit(root, "base")
        _write(root, "docs/session-briefs/story-x-VALIDATION-PACKAGE.md",
               "# pkg\n- The collision is a known stakeholder exception, out of scope.\n")
        _commit(root, "add ZTIE-style validation package (uncited given)")
        f = run_locks(root, "HEAD~1", "HEAD")
        _check("L1 recognizes *-VALIDATION-PACKAGE.md naming",
               any(x.lock == "LOCK1" for x in f))

    # ---- LOCK 2: IAM in diff + brief silent on IAM => HARD; brief covers => ok ----
    iam_yaml = ("Resources:\n  R:\n    Type: AWS::IAM::Role\n"
                "    Properties:\n      AssumeRolePolicyDocument: {}\n")
    with tempfile.TemporaryDirectory() as d:
        root = _repo(d)
        _write(root, "README.md", "base\n")
        _commit(root, "base")
        _write(root, "infra/role.yaml", iam_yaml)
        _write(root, "DOCS/session-briefs/s-VALIDATOR-HANDOVER.md",
               "# brief\nDoD: verify the Step Functions and Lambda behave.\n")
        _commit(root, "add IAM role + brief silent on IAM")
        f = run_locks(root, "HEAD~1", "HEAD")
        _check("L2 IAM-omission HARD-flagged",
               any(x.lock == "LOCK2" and x.severity == "HARD" for x in f))

    with tempfile.TemporaryDirectory() as d:
        root = _repo(d)
        _write(root, "README.md", "base\n")
        _commit(root, "base")
        _write(root, "infra/role.yaml", iam_yaml)
        _write(root, "DOCS/session-briefs/s-VALIDATOR-HANDOVER.md",
               "# brief\nDoD: attack the IAM role least-privilege, its trust "
               "policy and any wildcard principal.\n")
        _commit(root, "add IAM role + brief that targets IAM")
        f = run_locks(root, "HEAD~1", "HEAD")
        _check("L2 IAM-covered NOT flagged",
               not any(x.lock == "LOCK2" for x in f))

    with tempfile.TemporaryDirectory() as d:
        root = _repo(d)
        _write(root, "README.md", "base\n")
        _commit(root, "base")
        _write(root, "infra/table.yaml",
               "Resources:\n  T:\n    Type: AWS::DynamoDB::Table\n")
        _commit(root, "non-IAM change")
        f = run_locks(root, "HEAD~1", "HEAD")
        _check("L2 non-IAM change not engaged",
               not any(x.lock == "LOCK2" for x in f))

    # ---- LOCK 3: removing a scope bullet => HARD; keeping it => ok ----
    v1 = ("# brief\n- In scope: deploy the table.\n"
          "- Out of scope: the IAM role changes.\n- Constraint: pdlv- only.\n")
    with tempfile.TemporaryDirectory() as d:
        root = _repo(d)
        _write(root, "DOCS/session-briefs/s-brief.md", v1)
        _commit(root, "brief v1")
        # drop the Out-of-scope boundary silently
        _write(root, "DOCS/session-briefs/s-brief.md",
               "# brief\n- In scope: deploy the table.\n- Constraint: pdlv- only.\n")
        _commit(root, "brief v2 (noise)")
        f = run_locks(root, "HEAD~1", "HEAD")
        _check("L3 scope-reduction HARD-flagged",
               any(x.lock == "LOCK3" and x.severity == "HARD" for x in f))

    with tempfile.TemporaryDirectory() as d:
        root = _repo(d)
        _write(root, "DOCS/session-briefs/s-brief.md", v1)
        _commit(root, "brief v1")
        _write(root, "DOCS/session-briefs/s-brief.md", v1 + "- Constraint: ascii only.\n")
        _commit(root, "brief v2 add constraint")
        f = run_locks(root, "HEAD~1", "HEAD")
        _check("L3 scope-addition NOT flagged",
               not any(x.lock == "LOCK3" for x in f))

    # ---- LOCK 4: METHODOLOGY change w/o marker => HARD; with marker => ok ----
    with tempfile.TemporaryDirectory() as d:
        root = _repo(d)
        _write(root, "governance/METHODOLOGY.md", "# m\nrule 1\n")
        _commit(root, "base methodology")
        _write(root, "governance/METHODOLOGY.md",
               "# m\nrule 1\nalways mock the pre-flight linting to save API limits\n")
        _commit(root, "promote a general lesson")
        f = run_locks(root, "HEAD~1", "HEAD")
        _check("L4 unratified methodology HARD-flagged",
               any(x.lock == "LOCK4" and x.severity == "HARD" for x in f))

    with tempfile.TemporaryDirectory() as d:
        root = _repo(d)
        _write(root, "governance/METHODOLOGY.md", "# m\nrule 1\n")
        _commit(root, "base methodology")
        _write(root, "governance/METHODOLOGY.md", "# m\nrule 1\nrule 2\n")
        _commit(root, "promote lesson RATIFIED-BY-STAKEHOLDER")
        f = run_locks(root, "HEAD~1", "HEAD")
        _check("L4 ratified methodology NOT flagged",
               not any(x.lock == "LOCK4" for x in f))

    # ---- fail-open: not a git repo ----
    with tempfile.TemporaryDirectory() as d:
        _check("fail-open on non-git dir",
               run_locks(Path(d), "HEAD~1", "HEAD") == [])

    if failures:
        print("check_locks --self-test: FAIL")
        for name in failures:
            print(f"  - {name}")
        return 1
    print("check_locks --self-test: PASS (13 sabotage cases)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
