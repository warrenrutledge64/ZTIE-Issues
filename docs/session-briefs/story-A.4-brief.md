# Story A.4 (stakeholder brief) — institute deployed-state restore points; set the Phase-2 floor

> **What this session is.** With Story 2.0 validated live (A.2, 2026-09-02) and the
> Validation Debt Register now **empty**, the Phase-2 floor is *validated* but not yet
> *backed up*. This session institutes the **deployed-state restore points** that the
> Floor & Harvest Plan (§2 Phase A) requires before any archive/refactor work: run
> `capture` + `verify` for **both** accounts, commit the manifests, fill BOM's 11
> `pending` rows, and tag `restore/phase-2-floor-green`. It also folds in the quick
> confirmations that clear the runway: **A.1** (merge the capture-tooling extension)
> and **A.3** (confirm 2.1 into the floor).

## Where we are (true state at authoring, 2026-09-02)

- **Story 2.0 = ✅** — validated live in Forensic 360999005254 on 2026-09-02 (Story
  A.2, all 7 DoD checks passed). Flipped ✅ in RUNBOOK; `restore/story-2.0-green` is
  the paired-commit tag (tagged by the repo owner on the A.2 status commit).
- **Story 2.1 = ✅** — validated live 2026-09-01. A.3 is a *confirmation* only (no
  re-run).
- **Validation Debt Register = EMPTY.** The advancement gate is disarmed; new work
  may resume. `scripts/check_docs.py` passes clean.
- **`feature/restore-targets-phase2`** — built but **unmerged** (this is **A.1**: the
  capture-tooling extension for the post-2.1 targets). It must merge before A.4's
  capture can target the Phase-2 shape.
- **BOM.md** — **11 `pending` rows** still to fill with real deployed-state manifest
  references.
- **Deployed-state restore points** — **none captured yet** for Phase 2. Code tags
  exist (`restore/phase-1-green`, `restore/story-2.1-green`, `restore/story-2.0-green`)
  but no deployed-state manifest for Phase 2.

## What A.4 delivers (Definition of Done — Floor & Harvest Plan §2 Phase A gate)

1. **A.1 merged** — `feature/restore-targets-phase2` is on `main` (repo-owner merge),
   so the capture tool knows the post-2.1 targets.
2. **A.3 confirmed** — 2.1's ✅ is folded into the floor (a recorded confirmation; no
   re-validation).
3. **Deployed-state manifests captured + `verify`-clean for BOTH accounts** — Hub
   641628980935 and Forensic 360999005254. `verify` must compare only the
   **restore-relevant projection** (identity + desired-state fields), never raw
   captured objects, or volatile metadata (SSM param version, `last_modified`, CFN
   stack status, `stack_id`) will false-positive as drift. (Learned in Story 1.R.)
4. **BOM's 11 `pending` rows filled** — each with tag + SHA + manifest path.
5. **`restore/phase-2-floor-green` tagged** — the floor is set and backed up.
6. **Management artifacts first-class (RD-015)** — RUNBOOK ↔ PROJECT_PLAN aligned,
   BOM current, all via PR; check_docs stays green.

## What only YOU (the stakeholder) can do

- **A.1 merge:** merge `feature/restore-targets-phase2` → `main` (PR-based).
- **A.4 live runs:** run `capture` and `verify` in **BOTH** CloudShells — you have the
  live creds; the executor does not. Watch the account banner: **capture the Hub state
  from a Hub-authed shell and the Forensic state from a Forensic-authed shell.** Run
  `aws sts get-caller-identity` before each block (the operator has repeatedly run
  blocks in the wrong account).

## Scope guardrails

- **In scope:** A.1 confirm-merged; A.3 confirm 2.1; A.4 capture/verify/BOM/tag;
  RUNBOOK ↔ PROJECT_PLAN alignment; all via PR.
- **Out of scope:** the harvest inventory (B.1) and the archive build (Phase C); any
  new feature story (2.2+); any pipeline/infra/lambda code change; the "prove the
  negatives" 2.0 hardening (standing proposal, not this session).

## Lessons Learned / Carry-Forward (from Story A.2, the session that just closed)

- **A pre-validation defect was found and fixed before validating (fix-then-validate-once).**
  The first `cdk deploy` of `ZtieForensicInfraStack` failed: `UPDATE_FAILED` on
  `DetonationHostSg` with *"Invalid rule description."* Cause: a **security-group rule
  `description` contained `->`**, and `>` is **outside AWS's allowed SG-rule-description
  charset** (`a-zA-Z0-9. _-:/()#,@[]+=&;{}!$*`). Fix was a one-word change (`->` → `to`,
  commit `ab748be`); re-deploy was clean. **Watch-item for any CDK stack:** SG rule
  descriptions (and only those) are validated against that restricted charset — no
  `>`, `<`, `?`, backtick, or Unicode dash/arrow. Em dashes in *comments* and
  *CfnOutput descriptions* are harmless (they only render as `?` cosmetically).
- **Base-branch trap (avoided).** The `restore/story-2.1-green` tag was **behind**
  `main`; `main` carried the reshaped single-pane RUNBOOK, the G-3 register/gate,
  `check_docs.py`, and the Floor & Harvest Plan. Branch off **`origin/main`** (the
  brief permits "main at that commit"), not a stale restore tag, or you lose the
  register/gate you're operating on. **For A.4: base off the latest `main` that
  includes the A.2 flip + A.1 merge.**
- **Operator UX (recurs every session):** feed CloudShell commands **one line at a
  time**, never as a multi-line paste. In A.2, pasting the decoded UserData block
  caused the printed `shutdown -h +5` line to execute in CloudShell
  (*"System has not been booted with systemd… Host is down"*) — harmless (CloudShell
  isn't the detonation host) but it is **not** a check result. Two-account work needs
  two tabs; `aws sts get-caller-identity` before every block.
- **GitHub auth in CloudShell:** use the token-in-URL HTTPS form
  (`git remote set-url origin https://<TOKEN>@github.com/warrenrutledge64/ZTIE-Issues.git`);
  the account password is rejected. (The stakeholder pasted a PAT in the clear during
  A.2 — remind them to rotate it.)
- **Register clears by row removal.** `check_docs.py` reads the register table by
  story-ID; an `_(empty)_` placeholder row is ignored (no ID match), so the register
  parses as empty and the gate disarms. When the register is empty, CHECK B returns
  early (not armed) and CHECK A only requires 🟡/⛔ *feature* stories be registered
  (G-3 is governance-exempt). Keep that shape when editing.
- **Don't retro-edit history.** Session briefs, WORK_LOG, and the RD-023 rationale
  that reference "2.0 🟡 / the single open entry" were left as-is — they correctly
  describe the past. Only *current-status surfaces* (RUNBOOK master table + register,
  README focus table, BUILD_ORDER graph/recommendation) were flipped.
