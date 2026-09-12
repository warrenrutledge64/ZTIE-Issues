# `scripts/` — ZTIE operational tooling

Python-first operational tooling for ZTIE. Run from the **repo root** in **AWS
CloudShell** with **ambient credentials** (no `--profile`).

## `ztie-restore` — state-capture + coordinated restore (Story 1.R)

The restore-point mechanism: capture a **restore-relevant projection** of ZTIE's
durable state to a timestamped manifest, and coordinate a restore back to it. The
manifest pins the known-good governance-doc commit so code + state + governance
restore as one unit (RD-015). Full procedures live in
[`../RESTORE.md`](../RESTORE.md).

```bash
# Read-only capture (Hub or Forensic — one account at a time, in that CloudShell):
python3 scripts/ztie-restore capture --account hub

# Read-only verify against a manifest (exit 0 = match, 3 = drift):
python3 scripts/ztie-restore verify --account hub --manifest restore-manifests/manifest-<UTC>.json

# Coordinated restore (MUTATING; input() confirm gate, fails safe to NO):
python3 scripts/ztie-restore restore --account hub \
  --manifest restore-manifests/manifest-<UTC>.json \
  --template ZtieHubTrackingStack=/tmp/ZtieHubTrackingStack.template.json
```

### Design invariants

- **Capture is read-only.** The only mutating path is `restore`, behind the
  `input()` confirm (fails safe to NO on empty/negative/EOF; `ZTIE_ASSUME_NO=1`
  forces NO for automatable proof — there is no assume-YES).
- **Verify compares a projection, not raw objects** — volatile metadata (SSM
  version, CFN status, `last_updated`, `stack_id`, list ordering) never
  false-positives as drift.
- **CFN restore re-applies stack-level tags**, not just template + parameters.
- **Account-guarded** — every command checks the live STS identity against the
  requested account label and refuses to act on the wrong account.

### Layout

| Module | Responsibility |
|--------|----------------|
| `ztie_restore/projection.py` | pure projection builders + the diff contract (no boto3) |
| `ztie_restore/awsio.py` | boto3 access layer (read-only capture + mutating restore helpers) |
| `ztie_restore/manifest.py` | manifest build/read/write + governance-commit pin |
| `ztie_restore/confirm.py` | the `input()` fail-safe-NO confirm gate |
| `ztie_restore/targets.py` | declarative per-account capture plan (Hub / Forensic) |
| `ztie_restore/capture.py` | orchestrates a read-only capture into a manifest |
| `ztie_restore/verify.py` | re-captures live and diffs against a manifest |
| `ztie_restore/restore.py` | confirm-gated coordinated restore |
| `ztie_restore/cli.py` + `ztie-restore` | CLI |

### Tests

Pure-logic unit tests use stdlib `unittest`, so they run without AWS/PyPI:

```bash
cd scripts && python3 -m unittest ztie_restore.test_projection ztie_restore.test_confirm
```

Live paths (capture/verify/restore against real AWS) are validated by the operator
in CloudShell — boto3 and `pytest` are not installable in the build sandbox.

## `check_docs.py` - governance-doc consistency checker (Story G-3, RD-023)

Machine-enforces the two hard-pause rules Story G-3 installs, by parsing
[`../RUNBOOK.md`](../RUNBOOK.md) (the source of truth for story status). It reads
the **Validation Debt Register** and every per-phase / cross-cutting **story
table**, then runs:

- **CHECK A (register completeness):** fails if any story whose status is
  `🟡 In Progress` or `⛔ Blocked` is missing from the Validation Debt Register.
  Cross-cutting / governance stories (IDs starting with `G-`) are exempt, since
  the register tracks built-but-unvalidated feature / floor work, not the
  governance story that installs the gate.
- **CHECK B (advancement gate):** fails if a NEW feature story is marked started
  (`🟡`) or done (`✅`) while the register is non-empty. Stories already in the
  register (reworking an open entry to clear it), `G-` governance stories, and
  the pre-gate baseline (the committed-tree set of started/done feature stories,
  read from `git show HEAD:RUNBOOK.md`) are exempt.

It exits `0` (with a PASS line) when there are no violations and `1` when any are
found, printing each violation with its file, story ID, and which check failed.

```bash
# Check the tree this script lives in:
python3 scripts/check_docs.py

# Check an alternate tree (used by the unittest fixtures):
python3 scripts/check_docs.py --repo-root /path/to/tree
```

It is **Python 3.12 stdlib only** (no PyPI) and **unittest-covered** by
[`test_check_docs.py`](test_check_docs.py): a clean tree passes, an injected
un-registered `🟡` fires CHECK A, and an injected new-feature-started-while-debt-open
fires CHECK B:

```bash
python3 -m unittest scripts.test_check_docs -v   # run from the repo root
```

Story G-2 (RD-015) owns a broader `check_docs.py` remit (plan/runbook divergence,
dangling RD references, stray placeholders, `✅`-without-a-validation-line); those
are out of scope here and G-2 extends this same checker later.


## Contract generators — `gen_contracts.py` + `contract_writer.py` (Story C.3, RD-034)

Every ZTIE data contract is a JSON Schema generated from a Python source of truth,
then written to the canonical `schemas/` copy AND every bundled lambda copy that
must stay byte-in-sync (each lambda ships its own copy because it bundles only its
own directory). Before C.3 each contract had its own `gen_<name>_contract.py` that
duplicated an identical writer loop 10 times — a copy-drift surface. C.3 collapsed
that duplication **without changing a single schema byte**:

- **`contract_writer.py`** — the one shared writer: `write_contract(schema, out_paths)`
  does `json.dump(schema, fh, indent=2)` + a trailing newline (no `sort_keys`, no
  custom separators — exactly what all 10 generators did), and `resolve_out_paths()`
  turns repo-root-relative segment tuples into absolute paths.
- **`gen_<name>_contract.py`** — now pure data + a thin shim: each keeps its
  docstring, constants, and `SCHEMA` dict unchanged, and declares an `OUT_PATHS`
  list (segment tuples). Its `main()` delegates to the shared writer, so each stays
  individually runnable (nothing that referenced a generator by name broke).
- **`gen_contracts.py`** — the single "regenerate everything" entrypoint; drives
  every registered contract through the one shared writer.

```bash
python3 scripts/gen_contracts.py            # regenerate every contract
python3 scripts/gen_contracts.py --list     # list the registered contracts
python3 scripts/gen_reject_contract.py      # regenerate just one (still works)
```

**No-drift discipline:** the regenerated files are byte-for-byte identical to the
committed schemas. After changing a contract, run `gen_contracts.py` and confirm
`git diff -- schemas lambdas` shows only the intended change; the two-layer
`test_*_contract_conformance.py` suites (offline stdlib walk + a jsonschema
`skipUnless` live layer) guard the shape.
