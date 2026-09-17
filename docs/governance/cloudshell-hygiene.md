# AWS CloudShell hygiene (reusable, story-agnostic)

> A standing reference for operating the ZTIE accounts from AWS CloudShell during any
> live activity (validation, restore, teardown, investigation). It is **process guidance**,
> not a validation runbook: it does **not** author DoD or live-proof steps for any story
> (that is the Independent Validator's job under RD-055). Extracted from the retired
> `story-2.4R4-LIVE-RUNBOOK.md` so the hygiene notes live in ONE reusable place (RD-015)
> instead of being copied into each story's runbook.

## Account topology (three accounts)
- **Pipeline-Hub `641628980935`** — the control plane: DynamoDB tracking table, dashboard,
  reporting, the human accept/reject gate. Verify crossed/derived records here.
- **Forensic `360999005254`** — the blast zone: intake, scanners, the ephemeral EC2
  detonation host, the artifact bucket. Submit artifacts / run detonation here.
- **Pipeline-Sandbox `586917955591`** — the ZTIE→PDE handoff landing zone.

## Ground rules (these have bitten us every session)
- **One account per CloudShell tab.** A given block runs in exactly one account (e.g.
  submit in Forensic, verify in the Hub). A `# now in the Hub` banner comment does **NOT**
  change the account.
- **Run `aws sts get-caller-identity --query Account --output text` BEFORE every block**
  and read the account number. If it is not the account the block is for, switch tabs —
  do not proceed.
- **Feed commands ONE LINE AT A TIME.** Never paste a multi-line block into the prompt: a
  pasted blob can land in an interactive `read`/`input()` (with embedded `\r` between
  lines) and be misread, or run partial commands. One line, one Enter.
- **Region `us-east-1`, ambient creds** (no `--profile`).
- **`/tmp` is wiped when a CloudShell session recycles** (and `~` can be recycled on long
  idle). Any file you exported (e.g. `aws cloudformation get-template > /tmp/x.json`) must
  be regenerated in a fresh session. If the clone is gone, re-clone (below).

## Keeping your clone current
Your CloudShell clone falls behind whenever a PR merges to `main`.

- **Reading docs / want the latest project state → sync `main`:**
  ```bash
  cd ~/ZTIE-Issues
  git checkout main
  git fetch origin
  git pull --ff-only origin main   # --ff-only REFUSES a messy merge if local main drifted
  git log --oneline -1             # confirm you are at the latest merge
  ```
- **About to deploy + validate a story → check out the story's FEATURE branch:**
  ```bash
  cd ~/ZTIE-Issues
  git fetch origin
  git checkout feature/story-<id>
  git reset --hard origin/feature/story-<id>   # working tree == EXACTLY the code under test
  git log --oneline -1                         # pin/record this SHA
  ```
  `reset --hard origin/<branch>` discards local edits — safe on a **throwaway** CloudShell
  clone. Only ever run it on a clone you don't mind wiping.
- **If `git pull` complains about local changes** you didn't mean to make: `git status` to
  see them, `git stash` to park them, or `git checkout -- .` to discard tracked-file edits.
- **If the clone is gone** (CloudShell recycled it), re-clone:
  ```bash
  git clone https://github.com/warrenrutledge64/ZTIE-Issues.git
  ```

## Token safety
- **Never embed a token in the clone URL** (`git clone https://<TOKEN>@github.com/...`) for
  ongoing work — it leaks into shell scrollback / history. Use the credential prompt.
- **Rotate any token that appears in command output.** A GitHub PAT (`ghp_...`) echoed into
  CloudShell output is a leaked secret and must be rotated.

## Deploy-gap discipline (validating stale code)
A green `cdk deploy` can ship **stale** code two ways — guard against both:
- **Wrong checkout under a green deploy.** Before any `cdk deploy`, confirm the box is on the
  intended code (`git rev-parse --abbrev-ref HEAD && git log --oneline -1`) and grep the
  actual source for the change's marker. A `✅ UPDATE_COMPLETE` on the wrong checkout is a
  silent stale deploy.
- **Trusting the deploy line.** AFTER any deploy, verify the change actually took by
  inspecting the **live resource** (e.g. `aws lambda get-function-configuration ... --query
  Environment.Variables`) and confirming the new env/behavior is present — never trust the
  `✅ UPDATE_COMPLETE` line alone.
- **Downstream/new-consumer redeploys.** If a change adds a new envelope kind or a new code
  path that a *pre-existing* Lambda/stack must understand, redeploy **those** stacks too
  before validating — deploying only the new stack is insufficient.
