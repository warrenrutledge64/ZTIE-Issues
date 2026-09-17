# Story {{ID}} — LIVE validation runbook (VALIDATOR-authored; stakeholder-run)

> **⛔ RD-055 (Zero-Trust Validation Supply Chain) — WHO AUTHORS THIS FILE.** Under
> RD-055 the live-validation runbook is authored by the **Independent Validator (Gemini),
> from scratch, blind to the builder's assumptions**, using only the stakeholder's
> plain-English requirement + the PR diff the stakeholder fetched **independently from the
> repository API**. **The build agent (Kiro) does NOT author, fill, or supply this runbook**,
> nor any test script or "how to prove it on live AWS" step, nor the raw diff / a diff-fetch
> command / code snippets — Kiro's entire validation handoff is the **PR number only**. This
> file is a **reference skeleton for the VALIDATOR**, not a Kiro deliverable. If any part of
> the runbook, DoD, or diff reached Gemini via Kiro, the pass is **VOID** and must be
> re-sourced by the stakeholder. (See METHODOLOGY §4b + PROJECT_PLAN RD-055.)

> **This is the ONLY live part of Story {{ID}}, and only YOU (the stakeholder) can do it** (neither AI has AWS creds). You DEPLOY the resources, submit the test, and confirm the derived outcome; the **Validator adjudicates** PASS/FAIL/INCONCLUSIVE against its own DoD. On an explicit PASS, the executor is handed the sealed verdict and is a **write-only scribe** — it **records the verdict verbatim** into RUNBOOK {{ID}} detail and flips {{ID}} ✅ (paired commit). **Nothing is recorded on inference.**

## Ground rules (these have bitten us every session)

- **TWO accounts → TWO CloudShell tabs.** Artifacts and compute are in **Forensic (360999005254)**; the durable tracking record is in the **Hub (641628980935)**. A banner comment does NOT change the account.
- **Run `aws sts get-caller-identity` BEFORE every block** and read `Account`. If it is not the account the block is for, switch tabs — do not proceed.
- **Feed commands ONE LINE AT A TIME.** Never paste a multi-line block.
- **`/tmp` is wiped when CloudShell recycles.** Re-clone/re-checkout if a session drops.
- **Region us-east-1**, ambient creds (no `--profile`).

## STEP 0 — Get the {{ID}} code

```bash
cd ~/ZTIE-Issues && git fetch origin -q && git checkout feature/story-{{ID}} && git reset --hard origin/feature/story-{{ID}}
