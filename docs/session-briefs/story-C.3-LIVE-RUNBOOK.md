# Story C.3 — LIVE-RUNBOOK (optional owner no-op redeploy: prove the refactor still bundles/imports)

> C.3 is a **behaviour-preserving** refactor, validated OFFLINE (contract no-drift +
> Hub-gate apply/validate equivalence + green offline test bar + `ruff`/`py_compile`).
> It touches NO `.ts`/infra and changes NO AWS resource shape, so a live run is **not
> required** to close it. This runbook is an OPTIONAL belt-and-suspenders check the
> repo owner can run to confirm the one changed *deployed* file — `lambdas/hub_ingest/
> handler.py` — still bundles and imports cleanly in the live Lambda, since `hub_ingest`
> is the **Docker-bundled** Lambda and the refactor added a module-level `_KINDS`
> registry that runs at import time.
>
> Everything else C.3 changed (`scripts/*`) is dev tooling that never deploys.

## What changed that could conceivably affect runtime
- `lambdas/hub_ingest/handler.py` only. The 8 per-kind validate/apply/process trios are
  now thin delegates over a data-only `_KINDS` registry + generic helpers. `_KINDS` is
  built at MODULE IMPORT (a list of `_KindSpec`), so a typo there would surface as an
  **import error on cold start**, not a silent wrong-answer. The offline proof already
  confirmed byte-identical `update_item` calls + identical validation messages; this
  live check just confirms the module imports + a real message still flows.
- NO other Lambda changed. The `scripts/gen_*` + `contract_writer.py` + `gen_contracts.py`
  changes are build-time only and never ship in any asset bundle. The bundled contract
  JSON files are byte-identical (proven: `git diff -- schemas lambdas` empty), so no
  lambda's bundled schema copy moved.

## Preconditions
- `[HUB]` CloudShell (Pipeline-Hub `641628980935`), region `us-east-1`, ambient creds.
- `aws sts get-caller-identity` FIRST — confirm `Account` = `641628980935` (the tracking
  table + `hub_ingest` live in the Hub). If it shows Forensic, you are in the wrong tab.
- The box is on the C.3 code: `git fetch origin && git checkout feature/story-C.3 &&
  git reset --hard origin/feature/story-C.3` (or `main` after the PR merges), then
  `git rev-parse --abbrev-ref HEAD && git log --oneline -1`. Deploy-gap guard: a green
  `cdk deploy` from the WRONG checkout ships stale code — confirm the branch FIRST.
- Grep the marker so you KNOW the new code is what will synth:
  `grep -n "_KINDS_BY_NAME\|_KindSpec\|_process_kind" lambdas/hub_ingest/handler.py`
  (expect several hits — the registry + generic helpers).

## Deploy (Hub) + verify the LIVE resource actually took the new code
```bash
cd infra
npx cdk deploy ZtieHubTrackingStack   # the stack that bundles lambdas/hub_ingest (Docker)
```
- The bundling step runs `public.ecr.aws/lambda/python:3.12` and `pip install -r
  requirements.txt -t /asset-output` then `cp -r . /asset-output` — the whole
  `lambdas/hub_ingest` dir (handler + bundled schemas). A Python SYNTAX/IMPORT error in
  the refactored handler would NOT fail the bundle (it copies files, does not import
  them), so DO NOT trust `UPDATE_COMPLETE` alone — verify the live import next.
- AFTER deploy, confirm the live function imports the new module cleanly (cold-start a
  fresh container with an EMPTY records batch — a valid no-op the handler already
  supports, and requires only that the module imported):
```bash
FN=$(aws cloudformation describe-stack-resources \
  --stack-name ZtieHubTrackingStack \
  --query "StackResources[?ResourceType=='AWS::Lambda::Function' && contains(LogicalResourceId,'Ingest')].PhysicalResourceId" \
  --output text)
echo "hub_ingest function: $FN"
aws lambda invoke --function-name "$FN" \
  --payload '{"Records":[]}' --cli-binary-format raw-in-base64-out /tmp/c3_out.json
cat /tmp/c3_out.json     # expect: {"batchItemFailures": []}  (module imported, empty batch handled)
```
- A `{"batchItemFailures": []}` with **no** `Runtime.ImportModuleError` / `Unhandled` in
  the response proves the `_KINDS` registry built at import time and the handler is live.
  If you see an import error, the registry has a typo — do NOT merge; report it.

## Optional end-to-end reassurance (only if you want a full flow)
Re-submit any one intake through the normal Forensic intake API (see
`story-2.6-LIVE-RUNBOOK.md` for the awscurl submit recipe) and confirm the Hub tracking
record still gets each derived kind attached exactly as before (e.g. `classification`,
`static_scan`, `dynamic_run`, `sanitized`, `collected`), and that a `grep` for
`verdict|safe|approved|forward` on the record is still empty. This exercises the same
`_process_<kind>` → `_apply_kind` path the offline equivalence check already proved
byte-identical. Nothing about the on-the-wire envelope or the stored record changed.

## Restore point (owner action)
On merge, place the annotated restore tag **`restore/shared-seam-green`** on the merged
C.3 status commit (the paired commit that carries the ✅ flip), per
[`docs/SETTING_AND_REMOVING_RESTORE_POINTS.md`](../SETTING_AND_REMOVING_RESTORE_POINTS.md).
This is the RUNBOOK's declared restore tag for C.3.

## If anything fails
C.3 stays 🟡: add it to the Validation Debt Register (it is an F&H story, so it is not
auto-registered), fix the specific gap, re-run the offline proof bar + this check, then
re-flip. Do NOT close on inference.
