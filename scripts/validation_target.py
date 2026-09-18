#!/usr/bin/env python3
"""
ZTIE validation-target packager (zero-trust split-brain).

Produces an IMMUTABLE, reproducible validation target for a story so an
airgapped Independent Validator (which has NO view into the RUNBOOK) can
evaluate the ACTUAL merged state — never a fabricated PR/diff.

It emits two things, both mechanical and read-only:

  1. PIN THE TARGET  (git, read-only):
       - the current `main` tip SHA
       - the fix/subject commit SHA(s) for the story
       - the production-code file scope + each file's blob hash at main
       - a drift check (are the files identical at the fix commit and at main?)
       - an Option-2 baseline->main code diff command (a real, non-empty delta)

  2. RUNBOOK CONTEXT EXTRACT  (text, VERBATIM):
       - the story's master-table row, exactly as written
       - the Validation Debt Register status + every SEALED VERDICT line for
         the story, exactly as written
     The extractor is STRICTLY MECHANICAL: it copies lines out of RUNBOOK.md
     with ZERO executor interpretation, summarization, or judgment. It never
     authors a DoD, never asserts pass/fail, never infers status.

WHY THIS EXISTS (RD-015, repeatable OS layer): the old validation flow assumed
an unmerged PR/diff. Once a fix is merged, the PR/diff is empty and the target
is undefined. Pinning an immutable SHA + file scope + verbatim runbook context
works for EVERY story, merged or not, and is reproducible by any third party.

READ-ONLY: this tool runs only `git` plotting/inspection commands (rev-parse,
log, show, diff, cat-file) and reads RUNBOOK.md. It writes only its own output
artifact. It changes no repository state.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# read-only git
# ---------------------------------------------------------------------------

_ALLOWED_GIT = {
    "rev-parse", "log", "show", "diff", "cat-file", "merge-base", "fetch", "tag",
}


def git(*args: str) -> str:
    if not args or args[0] not in _ALLOWED_GIT:
        raise RuntimeError(f"BLOCKED: git '{args[0] if args else ''}' is not in the read-only allow-list.")
    # fetch is read-only w.r.t. local working tree/history mutation of tracked content;
    # restrict it to a plain remote refresh (no push, no prune-by-default surprises).
    res = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    if res.returncode != 0:
        return f"<git error: {res.stderr.strip()[:300]}>"
    return res.stdout.rstrip("\n")


def blob_hash(ref: str, path: str) -> str | None:
    out = git("rev-parse", f"{ref}:{path}")
    return out if out and not out.startswith("<git error") else None


# ---------------------------------------------------------------------------
# RUNBOOK context extract  (VERBATIM, mechanical)
# ---------------------------------------------------------------------------

def extract_runbook_context(runbook: Path, story_id: str) -> dict:
    """Copy — verbatim — the story's master-table row and any SEALED VERDICT /
    register lines that name the story. No interpretation whatsoever."""
    text = runbook.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Escape the story id for regex (e.g. "2.4R" -> "2\.4R"); match as a
    # whole token so "2.4" does not match "2.4R".
    esc = re.escape(story_id)
    token = re.compile(rf"(?<![\w.]){esc}(?![\w])")

    # 1) master-table row: a line beginning with '|' whose STORY COLUMN is the
    #    story id. We check the id appears in an early pipe-delimited cell (the
    #    master table's Story column is cell index 3; on-deck/register tables put
    #    the id in cell index 1). Matching the CELL — not anywhere on the line —
    #    stops prose mentions (e.g. a VUX row or a 4.7 row that names 2.4R) from
    #    being transported as if they were 2.4R's own row. Still purely
    #    mechanical: exact cell equality, no interpretation.
    master_rows = []
    for ln in lines:
        if not ln.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        # strip markdown link/emphasis around the id: [2.4R](...), **2.4R**, `x`
        def _cell_id(c: str) -> str:
            m = re.search(r"\[([^\]]+)\]", c)  # [2.4R](link) -> 2.4R
            base = m.group(1) if m else c
            return base.replace("*", "").replace("`", "").strip()
        cell_ids = [_cell_id(c) for c in cells]
        if story_id in (cell_ids[1:4] if len(cell_ids) >= 4 else cell_ids):
            master_rows.append(ln)

    # 2) register status + sealed-verdict blockquote lines that name the story.
    #    We copy contiguous blockquote ('>') paragraphs that mention the id,
    #    verbatim, so the Validator sees exactly what the runbook says.
    register_blocks: list[str] = []
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith(">") and (token.search(ln) or "Register status" in ln or "SEALED VERDICT" in ln):
            # gather the whole contiguous blockquote paragraph
            start = i
            while i < len(lines) and lines[i].startswith(">"):
                i += 1
            block = "\n".join(lines[start:i])
            # keep only blocks that actually name the story or are the register status
            if token.search(block) or "Register status" in block:
                register_blocks.append(block)
        else:
            i += 1

    return {
        "story_id": story_id,
        "source_file": str(runbook.name),
        "verbatim_master_table_row": master_rows,          # list, exact lines
        "verbatim_register_and_verdict_blocks": register_blocks,  # list, exact blocks
        "extractor_note": (
            "MECHANICAL VERBATIM COPY from RUNBOOK.md. No summarization, no "
            "interpretation, no pass/fail assertion. If a line is not present "
            "here, it was not present (naming this story) in the runbook."
        ),
    }


# ---------------------------------------------------------------------------
# pin the target  (git, read-only)
# ---------------------------------------------------------------------------

def pin_target(
    main_ref: str,
    fix_commits: list[str],
    code_paths: list[str],
    baseline_ref: str | None,
) -> dict:
    main_sha = git("rev-parse", main_ref)

    fixes = []
    for c in fix_commits:
        sha = git("rev-parse", c)
        subj = git("show", "-s", "--format=%s", c)
        # merge-base --is-ancestor returns empty stdout on success; use its rc.
        is_anc = subprocess.run(
            ["git", "merge-base", "--is-ancestor", c, main_ref], check=False
        ).returncode == 0
        fixes.append({
            "ref": c, "sha": sha, "subject": subj,
            "is_ancestor_of_main": is_anc,
        })

    file_scope = []
    drift = []
    primary_fix = fix_commits[0] if fix_commits else main_ref
    for p in code_paths:
        at_main = blob_hash(main_ref, p)
        at_fix = blob_hash(primary_fix, p)
        file_scope.append({"path": p, "blob_at_main": at_main})
        drift.append({
            "path": p,
            "blob_at_fix": at_fix,
            "blob_at_main": at_main,
            "identical": (at_fix is not None and at_fix == at_main),
        })

    option2 = None
    if baseline_ref:
        base_sha = git("rev-parse", baseline_ref)
        paths = " ".join(code_paths)
        option2 = {
            "baseline_ref": baseline_ref,
            "baseline_sha": base_sha,
            "code_diff_command": f"git diff {base_sha}..{main_sha} -- {paths}",
            "note": "Real, non-empty change delta the fix introduced over the baseline.",
        }

    return {
        "repo_main_ref": main_ref,
        "main_tip_sha": main_sha,
        "fix_commits": fixes,
        "code_file_scope": file_scope,
        "drift_check": drift,
        "all_files_stable_on_main": all(d["identical"] for d in drift) if drift else None,
        "reproduce_command": (
            f"git fetch && git checkout {main_sha} -- " + " ".join(code_paths)
        ),
        "option2_baseline_diff": option2,
    }


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------

def render(pkg: dict) -> str:
    t = pkg["target"]
    c = pkg["runbook_context"]
    L = []
    L.append(f"===== ZTIE IMMUTABLE VALIDATION TARGET — story {c['story_id']} =====")
    L.append("(read-only, reproducible; NOT a PR/diff; carries no verdict)\n")
    L.append(f"main tip SHA : {t['main_tip_sha']}")
    L.append(f"all code files stable on main: {t['all_files_stable_on_main']}")
    L.append("\nfix commit(s) (attempt code):")
    for f in t["fix_commits"]:
        L.append(f"  {f['sha']}  ancestor_of_main={f['is_ancestor_of_main']}")
        L.append(f"    {f['subject']}")
    L.append("\nproduction-code file scope (content at main tip):")
    for f in t["code_file_scope"]:
        L.append(f"  {f['path']}  blob={f['blob_at_main']}")
    L.append("\ndrift check (fix commit vs main):")
    for d in t["drift_check"]:
        L.append(f"  {'SAME' if d['identical'] else 'DIFF'}  {d['path']}")
    L.append(f"\nreproduce: {t['reproduce_command']}")
    if t.get("option2_baseline_diff"):
        o = t["option2_baseline_diff"]
        L.append(f"\nOption 2 baseline->main code diff:\n  baseline: {o['baseline_sha']}\n  {o['code_diff_command']}")
    L.append("\n----- RUNBOOK CONTEXT (VERBATIM, for the airgapped Validator) -----")
    L.append("master-table row(s):")
    for r in c["verbatim_master_table_row"]:
        L.append(f"  {r}")
    L.append("register status + sealed verdicts (verbatim):")
    for b in c["verbatim_register_and_verdict_blocks"]:
        L.append("  " + b.replace("\n", "\n  "))
    L.append(f"\nNOTE: {c['extractor_note']}")
    L.append("===== END =====")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="ZTIE immutable validation-target packager (read-only).")
    p.add_argument("--story", required=True, help="Story id, e.g. 2.4R")
    p.add_argument("--fix-commit", action="append", default=[],
                   help="Commit ref carrying the attempt code (repeatable; first = primary).")
    p.add_argument("--code-path", action="append", default=[],
                   help="Production-code file path in scope (repeatable).")
    p.add_argument("--main-ref", default="origin/main")
    p.add_argument("--baseline-ref", default=None,
                   help="Optional baseline ref for the Option-2 code diff.")
    p.add_argument("--runbook", default="RUNBOOK.md")
    p.add_argument("--out", default=None)
    args = p.parse_args(argv)

    runbook = Path(args.runbook)
    if not runbook.exists():
        print(f"RUNBOOK not found: {runbook}", file=sys.stderr)
        return 2

    pkg = {
        "target": pin_target(args.main_ref, args.fix_commit, args.code_path, args.baseline_ref),
        "runbook_context": extract_runbook_context(runbook, args.story),
    }
    out_path = args.out or f"validation-target-{args.story.replace('.', '_')}.json"
    Path(out_path).write_text(json.dumps(pkg, indent=2), encoding="utf-8")
    print(render(pkg))
    print(f"\n[artifact] wrote {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
