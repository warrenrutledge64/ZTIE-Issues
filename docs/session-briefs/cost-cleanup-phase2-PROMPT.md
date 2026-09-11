# Carry-Forward Prompt — Cost Cleanup Phase 2 (remaining stale-stack decommission)

> **Purpose:** self-contained prompt for the NEXT session to finish the optional
> stale-stack cleanup that follows the VPC cost remediation (RD-032). This is a
> **bonus / opportunistic** track — treat it as its own sprint if the session has
> room, or defer it if the session is doing feature work. Nothing here is blocking
> the core pipeline.
>
> **Warm-start context (what already happened):** the ORIGINAL problem — unexpected
> VPC spend in the Hub (641628980935) and Forensic (360999005254) — is **SOLVED and
> confirmed.** Two stale off-architecture ZTIE lineages were decommissioned
> (RD-032, `docs/governance/COST_REMEDIATION_LEGACY_DECOMMISSION.md`, PR #82 merged;
> reusable auditor `scripts/vpc_cost_audit.py`, PR #81 merged):
> - Hub: `Ztie*-dev` lineage (`ZtieNetwork-dev` owned `ztie-detonation-vpc-dev`,
>   ~$115/mo) + dead `ztie-submit-api` — DELETED, VPC returns `InvalidVpcID.NotFound`.
> - Forensic: `Forensic-Network-Perimeter` orphan VPC (~$70/mo) + `Forensic-Linting-Runner`
>   — DELETED (first hit `DELETE_FAILED`; fixed by deleting the 6 interface endpoints
>   directly, waiting for ENIs to clear, then retrying the stack delete).
> - **Confirmed 2026-09-10:** Hub has ZERO non-default VPCs, ZERO interface endpoints,
>   ZERO NAT. ~$185/mo of VPC cost stopped in both accounts.

---

## Operator setup (do this first, every session)

The Hub/Forensic wrong-account mistake recurs constantly. A persisted CloudShell
prompt label is in `~/.bashrc` in each account showing `[HUB]` / `[FORENSIC]`.
If a shell doesn't show it, re-add:

```bash
cat >> ~/.bashrc <<'EOF'

if [ -z "$ZTIE_ACCT" ]; then
  ZTIE_ACCT=$(aws sts get-caller-identity --query Account --output text 2>/dev/null)
  case "$ZTIE_ACCT" in
    641628980935) ZTIE_LABEL="HUB" ;;
    360999005254) ZTIE_LABEL="FORENSIC" ;;
    586917955591) ZTIE_LABEL="SANDBOX" ;;
    *) ZTIE_LABEL="$ZTIE_ACCT" ;;
  esac
fi
export PS1="[\[\e[1;33m\]${ZTIE_LABEL}\[\e[0m\]] \w \$ "
EOF
source ~/.bashrc
```

Confirm the prompt reads the RIGHT account before EVERY block. Switching accounts =
open a CloudShell in the target account (SSO/console switcher), not just refreshing.
A brand-new Forensic CloudShell shows `[FORENSIC]` on its own.

---

## THE BONUS WORK (two remaining checks, then safe deletions)

### A. Hub — pipeline run-recency check (decide keep-vs-delete on 4 stacks)

Four Hub stacks are candidate-stale but export nothing (which for a pipeline proves
nothing — pipelines deploy, they aren't imported): `PipelineStack`,
`ZTIE-Pipeline-Stack`, `ZTIE-IAM-Deployment-Stack`, `ZTIE-CrossAccount-Pipeline`
(the last already `UPDATE_ROLLBACK_COMPLETE`). Decide by whether they've RUN recently.
Run in `[HUB]`:

```bash
echo "### CodePipelines + last state change ###"
for P in $(aws codepipeline list-pipelines --region us-east-1 --query 'pipelines[].name' --output text); do
  printf "%-45s " "$P"
  aws codepipeline get-pipeline-state --region us-east-1 --name "$P" \
    --query "max(stageStates[].latestExecution.lastStatusChange)" --output text 2>/dev/null || echo "(no state)"
done
echo ""
for S in PipelineStack ZTIE-Pipeline-Stack ZTIE-IAM-Deployment-Stack ZTIE-CrossAccount-Pipeline; do
  echo "-- $S --"
  aws cloudformation describe-stacks --region us-east-1 --stack-name "$S" \
    --query "Stacks[0].{Created:CreationTime,Updated:LastUpdatedTime,Desc:Description}" --output json 2>/dev/null
done
```
Recent run = active (KEEP). Months stale / rollback = dead prototype (DELETE candidate).

### B. Forensic — import-safety check (rest of the stale Forensic lineage)

Must run in a `[FORENSIC]` shell (has been run in the Hub by mistake 3x — the six
stacks live in Forensic, so a Hub run always says "exports nothing" and is meaningless).

```bash
for STACK in ztie-forensic-inspection DeployForensics-ZtieAnalyzer DeployForensics-ZtieCollector DeployForensics-ZtieIngestion DeployForensics-ZtieProcessor Forensic-Unified-Baseline; do
  echo ""
  echo "########## $STACK ##########"
  EXPORTS=$(aws cloudformation list-exports --region us-east-1 \
    --query "Exports[?contains(ExportingStackId, '/$STACK/')].Name" --output text)
  if [ -z "$EXPORTS" ]; then echo "  (exports nothing)"; continue; fi
  for EXP in $EXPORTS; do
    printf "  export %-55s -> " "$EXP"
    IMPORTERS=$(aws cloudformation list-imports --region us-east-1 --export-name "$EXP" 2>&1)
    if echo "$IMPORTERS" | grep -q "is not imported"; then echo "NOT IMPORTED (safe)"; else echo "IMPORTED BY:"; echo "$IMPORTERS" | sed 's/^/      /'; fi
  done
done
```
`NOT IMPORTED` on everything = the stale Forensic lineage is dead → tear it down
(delete-stack, consumers before any exporter). Any `IMPORTED BY` = that piece is live
glue (likely the ZTIE->PDE handoff) → keep it, investigate the importer first.

---

## Hub classification snapshot (from 2026-09-10 inventory)

**KEEP:**
- `ZtieHubTrackingStack`, `CDKToolkit` — current ZTIE.
- `ztie-asymmetric-cmk` — **LIVE KMS asymmetric attestation key** (exports
  `pde-ztie-signing-key-*-commercial-tenant-01-production`; this is the sign/verify
  key for the ZTIE->PDE attestation handoff). "Not imported" is IRRELEVANT for KMS
  (keys are referenced by ARN at runtime, not CFN imports). **DO NOT DELETE.**
- All `PDE-*` / `pde-*` — the PDE service the Hub ORCHESTRATES (active).

**STALE ZTIE — strong delete candidates (non-VPC; carry Lambda/WAF/Cognito/S3 cost):**
- `ztie-detonation-chamber-production` (+ nested `...-IAMRolesStack-...`) — detonation
  in the Hub violates RD-008 (control plane must stay out of the blast zone).
- `aws-sam-cli-managed-default` — SAM leftover, likely from the above.
- `ztie-hub-frontend-stack`, `ztie-hub-cognito-stack`, `ztie-hub-backend-stack` — old
  dashboard/website lineage, not in the current CDK repo.
- `ztie-dev-identity`, `ztie-dev-hosting`, `ztie-dev-waf-shield` — old `-dev` lineage;
  the WAF web ACL carries standing monthly cost.

**PENDING check A:** `PipelineStack`, `ZTIE-Pipeline-Stack`, `ZTIE-IAM-Deployment-Stack`,
`ZTIE-CrossAccount-Pipeline`.

**PDE cruft (flag to PDE owner, NOT ZTIE's to delete):** `pde-hub-foundation-fixed`
(DELETE_FAILED), `pde-hub-foundation-fixed2` / `pde-approval-api-stack`
(REVIEW_IN_PROGRESS — never executed change sets), `pde-hub-governance-rules`
(ROLLBACK_COMPLETE).

---

## Safety rules for any teardown (learned this remediation)

1. **Confirm the owning stack from the VPC/resource `aws:cloudformation:stack-name`
   tag before deleting — identity from tags, never inference.**
2. Prefer `aws cloudformation delete-stack` over hand-deleting resources; CFN enforces
   dependency/export safety and names the blocker in `describe-stack-events` on failure.
3. **Interface-endpoint VPCs:** a stack delete can fail on the subnet/endpoint-SG
   because endpoint ENIs are slow to detach. Fix: `delete-vpc-endpoints` directly,
   wait 2-3 min for ENIs to clear, then re-run `delete-stack`. (delete-stack is async;
   a resource still showing mid-delete is `deleting`, not stuck.)
4. Never delete a KMS key on inference (used by ARN, not CFN imports; scheduled
   deletion has a 7-30 day window by design).
5. Delete order: consumers/importers first, exporters last.
6. Verify each teardown: stack `DELETE_COMPLETE` (or absent) AND the resource returns
   `NotFound`.

---

## Governance obligations when this work is done (RD-015)

- Extend `docs/governance/COST_REMEDIATION_LEGACY_DECOMMISSION.md` with the Phase-2
  actions + evidence (or add a sibling reconciliation doc with the full two-account
  KEEP/PDE/STALE table).
- If Phase-2 changes the RD-032 scope materially, note it (amend RD-032 or add a new
  RD); keep PROJECT_PLAN <-> RUNBOOK aligned.
- Run `scripts/check_docs.py` (expect PASS) and `python3 -m unittest scripts.test_check_docs`
  (expect OK / 3 tests; the `check_docs: FAIL ...` lines for 2.5 fixtures are the
  checker testing ITSELF — not real failures).
- PR-review, never straight to main.

---

## THE CALL (decision points for the next session / stakeholder)

1. **Pause vs. continue?** The VPC bleed (the original ask) is DONE. Phase-2 is
   optional additional savings (WAF/Lambda/Cognito/S3 on the stale lineages). Only
   proceed if the session has room and the stakeholder says go.
2. **Confirm the two checks (A + B) before deleting anything** — especially the
   Forensic import check in a real `[FORENSIC]` shell.
3. **Do NOT touch** `ztie-asymmetric-cmk` or any `PDE-*`/`pde-*` stack.
4. Estimate/confirm the extra saving (Cost Explorer) so the effort is justified by
   value, not motion.
