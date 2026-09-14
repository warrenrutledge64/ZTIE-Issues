# Story {{ID}} — LIVE validation runbook (stakeholder, two CloudShells)

> **This is the ONLY live part of Story {{ID}}, and only YOU can do it** (the executor has no AWS creds). You DEPLOY the resources, submit the test, and confirm the derived outcome. The executor **records your returned output verbatim** into RUNBOOK {{ID}} detail. **Nothing is recorded on inference** — paste back exactly what the commands print. On a pass, the executor flips {{ID}} ✅ (paired commit).

## Ground rules (these have bitten us every session)

- **TWO accounts → TWO CloudShell tabs.** Artifacts and compute are in **Forensic (360999005254)**; the durable tracking record is in the **Hub (641628980935)**. A banner comment does NOT change the account.
- **Run `aws sts get-caller-identity` BEFORE every block** and read `Account`. If it is not the account the block is for, switch tabs — do not proceed.
- **Feed commands ONE LINE AT A TIME.** Never paste a multi-line block.
- **`/tmp` is wiped when CloudShell recycles.** Re-clone/re-checkout if a session drops.
- **Region us-east-1**, ambient creds (no `--profile`).

## STEP 0 — Get the {{ID}} code

```bash
cd ~/ZTIE-Issues && git fetch origin -q && git checkout feature/story-{{ID}} && git reset --hard origin/feature/story-{{ID}}
