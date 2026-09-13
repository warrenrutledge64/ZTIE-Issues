# Close-out package — G-1 ratification + OD-001 / OD-002 teardown

> **Purpose.** One reviewable place to close the three debt items you asked to finish:
> **G-1** (ratify the RD-014 compliance mappings), **OD-001** (Hub stale-stack cleanup),
> **OD-002** (Forensic stale-lineage teardown).
>
> **Division of labor (honest):**
> - **G-1 ratification** is an *accountable-reviewer decision* (RD-014). The executor
>   **must not self-ratify.** So: you approve the groups below (all, or group-by-group),
>   the executor then applies your approval as a dated + attributed `Proposed → Ratified`
>   flip. ZTIE claims control coverage **only** for ratified rows.
> - **OD-001 / OD-002** are **live AWS `delete-stack` operations.** The build sandbox has
>   **no AWS creds**, so the executor cannot run them. Run the blocks below in the RIGHT
>   account's CloudShell and paste the output back; the executor records the closure with
>   your evidence (**never on inference**).

---

## PART A — G-1 ratification checklist (your decision)

> **✅ DONE 2026-09-12** — the accountable party (repo owner `warrenrutledge64`) ratified
> ALL 8 groups (all 59 rows) in a single block. Every row in `../COMPLIANCE.md` is now
> `Ratified (warrenrutledge64, 2026-09-12)`; G-1 is closed ✅ (RUNBOOK + STORY_DETAIL). The
> checklist below is retained as the executed record.

The finished matrix is [`../COMPLIANCE.md`](../COMPLIANCE.md): **59 candidate (`Proposed`)
rows**, grouped below by artifact family. For each group, reply **RATIFY** (accept as
written), **RATIFY WITH EDITS** (say which rows/controls to change), or **HOLD** (defer).
Ratification just means: *"these candidate control mappings are a fair, non-overclaiming
representation of what the artifact implicates."* It does **not** assert ZTIE "is compliant."

**Attribution to record on flip:** who ratified (name/role) + date. If you approve all as a
block, the executor stamps every row `Ratified (<name>, 2026-09-12)`.

| # | Group (artifact family) | Rows | Your call |
|---|--------------------------|------|-----------|
| 1 | **Phase-1 intake/routing** — Story 1.1R data-contract boundary (RD-012/013/016), Story 1.2 classifier, Story 1.3 routing, Story 1.4 safe-reject | 14 | ☐ RATIFY / EDITS / HOLD |
| 2 | **Phase-2 static lane** — Story 2.1 non-executing scanners (RD-021), Story 2.2 compliance-map + signatures (RD-025) | 10 | ☐ RATIFY / EDITS / HOLD |
| 3 | **Phase-2 dynamic lane + orchestration** — RD-007/026 (2.3 detonation), RD-027 (2.0E endpoints), RD-029 (2.6 fork/join), RD-030 (2.4 telemetry), RD-031 (2.5 sanitize) | 6 | ☐ RATIFY / EDITS / HOLD |
| 4 | **Phase-3 correlation/synthesis** — RD-002 (parallel lanes), RD-003 (Nova Pro), RD-033 (3.1 combine), RD-035 (3.2 correlate), RD-037/038 (3.3 synthesize/three-score) | 6 | ☐ RATIFY / EDITS / HOLD |
| 5 | **Enforcement + reporting decisions** — RD-004 (static stack), RD-005 (verdict-drives-routing), RD-006 (dual-output reporting), RD-010/011 (handoff + clearance-only) | 5 | ☐ RATIFY / EDITS / HOLD |
| 6 | **Topology + containment** — RD-008 (three-account), RD-018 (hub-and-spoke), RD-019 (Dev input-only), RD-020 (Forensic containment) | 4 | ☐ RATIFY / EDITS / HOLD |
| 7 | **Governance / operating-model** — RD-015 (mgmt artifacts), RD-023 (advancement gate / G-3), RD-024 (operating model), RD-032 (legacy decommission), RD-034 (C.3 consolidation), RD-036 (G-4 charter) | 6 | ☐ RATIFY / EDITS / HOLD |
| 8 | **Non-functional constraints** — Zero-Trust posture, production-quality, AWS-native automation, Python-by-default, restore-point discipline, ServiceNow-out-of-scope | 6 | ☐ RATIFY / EDITS / HOLD |
|   | **Total** | **57** | (2 of the 59 rows — the two Story-2.1/2.2 already present pre-G-1 — fold into groups 2) |

> On your approval the executor: flips the approved rows to `Ratified (<attribution>,
> <date>)`, updates the COMPLIANCE.md header ("ZTIE claims coverage for the ratified rows
> below"), flips **G-1 → ✅** if **all** groups ratified (or leaves it 🟡 and records which
> groups ratified if partial — G-1 closes incrementally), aligns RUNBOOK + STORY_DETAIL,
> runs `check_docs` + `test_check_docs` green, and opens a PR.

---

## PART B — OD-001: Hub stale-stack cleanup (run in `[HUB]` 641628980935)

> **✅ DONE 2026-09-12** — 12 stale Hub stacks (13 incl. the nested IAM child) deleted +
> verified `GONE` in a live `[HUB]` CloudShell run; OD-001 closed in the RUNBOOK register
> (see COST_REMEDIATION_LEGACY_DECOMMISSION.md §8 for the full record incl. the three
> `DELETE_FAILED` unblocks). The blocks below are retained as the executed runbook.
>
> **Optional cost savings** (Lambda/WAF/Cognito/S3 on off-architecture prototypes). Nothing
> here blocks feature work. Run **one line at a time**; confirm the account first.

### B0. Confirm you are in the Hub
```bash
aws sts get-caller-identity --query Account --output text   # MUST print 641628980935
```

### B1. Run-recency check on the 4 pending pipeline stacks (decide keep vs delete)
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
**Decide:** recent run = active (**KEEP**); months-stale / `ROLLBACK` = dead prototype
(**DELETE candidate**). Paste this output back before deleting the four.

### B2. Delete the confirmed-stale Hub stacks (the strong candidates)
> **SAFETY — do NOT delete** `ztie-asymmetric-cmk` (live KMS attestation key) **or any**
> `PDE-*` / `pde-*` stack. Delete order: any consumer before its exporter. `delete-stack`
> is async — a stack still "deleting" is not stuck.
```bash
for S in \
  ztie-detonation-chamber-production \
  aws-sam-cli-managed-default \
  ztie-hub-frontend-stack \
  ztie-hub-backend-stack \
  ztie-hub-cognito-stack \
  ztie-dev-identity \
  ztie-dev-hosting \
  ztie-dev-waf-shield ; do
  echo "== deleting $S =="
  aws cloudformation delete-stack --region us-east-1 --stack-name "$S"
done
```
> If a delete fails on the nested `ztie-detonation-chamber-production` IAM stack or on
> interface-endpoint ENIs, see the endpoint-ENI fix in
> [`cost-cleanup-phase2-PROMPT.md`](cost-cleanup-phase2-PROMPT.md) (delete the endpoints
> directly, wait 2-3 min for ENIs to clear, retry the stack delete).

### B3. Verify each teardown
```bash
for S in ztie-detonation-chamber-production aws-sam-cli-managed-default \
  ztie-hub-frontend-stack ztie-hub-backend-stack ztie-hub-cognito-stack \
  ztie-dev-identity ztie-dev-hosting ztie-dev-waf-shield ; do
  printf "%-40s " "$S"
  aws cloudformation describe-stacks --region us-east-1 --stack-name "$S" \
    --query "Stacks[0].StackStatus" --output text 2>&1 | grep -q "does not exist" \
    && echo "GONE ✅" || aws cloudformation describe-stacks --region us-east-1 \
    --stack-name "$S" --query "Stacks[0].StackStatus" --output text
done
```
**Paste B1 + B3 output back** → executor records OD-001 closed with your evidence.

---

## PART C — OD-002: Forensic stale-lineage teardown (run in `[FORENSIC]` 360999005254)

> **✅ DONE 2026-09-12** — the stale Forensic lineage (8 stacks) + the RD-032 Phase-1 orphan
> `Forensic-Network-Perimeter` VPC were torn down + verified `GONE` in a live `[FORENSIC]`
> run; `DeployForensics-ZtieImageBuilder` was HELD (not confirmed dead); the
> `forensic-evidence-data-…` bucket was RETAINED (COMPLIANCE Object Lock, 365-day). OD-002
> closed in the RUNBOOK register (full record: COST_REMEDIATION_LEGACY_DECOMMISSION.md §10).
> The block below is retained as the executed runbook.
>
> **Must be a real Forensic shell.** A Hub run of the import check always says "exports
> nothing" and is meaningless — this has landed in the Hub by mistake repeatedly.

### C0. Confirm you are in Forensic
```bash
aws sts get-caller-identity --query Account --output text   # MUST print 360999005254
```

### C1. Import-safety check (is any export still imported by a live stack?)
```bash
for STACK in ztie-forensic-inspection DeployForensics-ZtieAnalyzer DeployForensics-ZtieCollector \
             DeployForensics-ZtieIngestion DeployForensics-ZtieProcessor Forensic-Unified-Baseline; do
  echo ""
  echo "########## $STACK ##########"
  EXPORTS=$(aws cloudformation list-exports --region us-east-1 \
    --query "Exports[?contains(ExportingStackId, '/$STACK/')].Name" --output text)
  if [ -z "$EXPORTS" ]; then echo "  (exports nothing)"; continue; fi
  for EXP in $EXPORTS; do
    printf "  export %-55s -> " "$EXP"
    IMPORTERS=$(aws cloudformation list-imports --region us-east-1 --export-name "$EXP" 2>&1)
    if echo "$IMPORTERS" | grep -q "is not imported"; then echo "NOT IMPORTED (safe)"; \
      else echo "IMPORTED BY:"; echo "$IMPORTERS" | sed 's/^/      /'; fi
  done
done
```
**Decision rule:** `NOT IMPORTED` on everything = the lineage is dead → tear it down.
**Any `IMPORTED BY`** = that piece is live glue (likely the ZTIE→PDE handoff) → **KEEP it**,
investigate the importer first, and tell the executor (do not delete it).

**Paste C1 output back before deleting anything.** The teardown block (C2) is only safe if
C1 shows everything NOT IMPORTED — the executor will confirm and hand you the exact
delete-stack order (consumers before exporters) based on your C1 result.

---

## What the executor does after your input

- **G-1:** apply your ratification calls (Part A) — dated + attributed flips — and close/step
  G-1 accordingly; PR.
- **OD-001:** on your B1+B3 evidence, mark OD-001 closed in the RUNBOOK Operational Debt
  register with the dated evidence note; extend the RD-032 governance doc; PR.
- **OD-002:** on your C1 evidence, confirm safety, hand you the exact delete order, then on
  your teardown+verify evidence mark OD-002 closed the same way; PR.
- Nothing is recorded on inference — closures ride on your pasted-back output.
