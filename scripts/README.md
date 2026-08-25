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
