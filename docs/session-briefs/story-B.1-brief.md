# Story B.1 (stakeholder brief) — the Harvest Inventory (survey the repo → what to parameterize/archive)

> **What this session is.** The Phase-2 floor is now set **and backed up** (Story A.4,
> 2026-09-02: 2.0 ✅ + 2.1 ✅, deployed-state manifests captured + `verify`-clean for
> both accounts, BOM filled, `restore/phase-2-floor-green` tagged). Per the Floor &
> Harvest Plan (§2 Phase B, §4/§7), the next step is the **Harvest Inventory**: a
> deliberate catalog of every repeated / duplicated pattern in the repo, each with a
> proposed component boundary, its baked-in defaults vs. its parameters, the number of
> current call-sites it replaces, and a harvest priority. **This inventory IS the
> archive's build spec** — we survey before we build so the archive is evidence-based,
> not a guess.

## Where we are (true state at authoring, 2026-09-02)

- **Phase-2 floor = set + backed up.** 2.0 ✅ (A.2), 2.1 ✅ (2026-09-01),
  Validation Debt Register EMPTY, deployed-state restore point
  `restore/phase-2-floor-green` exists (Hub + Forensic manifests, both `verify`-clean).
- **The drift signal that started Phase B is real and unchanged** (Floor & Harvest Plan
  §0): AWS primitives instantiated raw and inline in every stack; the `awsio` seam
  duplicated across Lambdas; ~5 bespoke contract generators re-implementing the same
  "SCHEMA-dict → json.dump to two paths"; a ~703-line hub-gate monolith with repeated
  per-envelope-kind helpers; no shared parameterized construct library.
- **B.1 is a repo survey — no live AWS, no infra change.** It reads the code and
  produces a reviewed catalog (`docs/governance/HARVEST_INVENTORY.md`).

## What B.1 delivers (Definition of Done — Floor & Harvest Plan §2 Phase B gate)

1. **`docs/governance/HARVEST_INVENTORY.md`** exists and catalogs every candidate:
   for each repeated/duplicated pattern — a **proposed component boundary**, its
   **baked-in (secure/opinionated) defaults vs. its parameters** (only real, observed
   variation becomes a prop — no speculative knobs), the **number of current
   call-sites** it would replace (evidence), and a **harvest priority**.
2. **Every candidate has a decided parameter surface** (or is explicitly deferred),
   reviewed and accepted by the stakeholder (the Phase B gate).
3. **Management artifacts first-class (RD-015):** the inventory is PR-reviewed;
   RUNBOOK ↔ PROJECT_PLAN facts stay aligned; `check_docs.py` stays green.

## What only YOU (the stakeholder) can do

- **Review + accept** the inventory (the Phase B gate): confirm each candidate's
  decided parameter surface, or explicitly defer it. There is **no live AWS action**
  in B.1 — it is a survey, so this is a review decision, not a CloudShell run.

## Scope guardrails

- **In scope:** the repo survey + the catalog + its parameter-surface decisions; all
  via PR.
- **Out of scope:** building the archive repo or any construct (that is Phase C —
  C.1/C.2/C.3); migrating any stack; any new feature story (2.2+); any
  pipeline/infra/lambda code change; the "prove the negatives" 2.0 hardening (standing
  proposal). B.1 catalogs; it does not extract or refactor.

## Lessons Learned / Carry-Forward (from Story A.4, the session that just closed)

- **The "merge the stale branch" trap is real — and A.4 hit it head-on.** A.1 was
  written as "merge `feature/restore-targets-phase2` → main," but that branch was cut
  **before** the `docs/` consolidation, the single-pane RUNBOOK, the G-3 register/gate,
  `check_docs.py`, and the Floor & Harvest Plan. Merging it verbatim would have
  **reverted all that governance state** (its diff was ~48 files: it re-renamed `docs/`
  → `DOCS/`, deleted `check_docs.py`, deleted the governance folder). The correct move
  was to re-apply **only its substance** (the `scripts/ztie_restore/targets.py` Phase-2
  target extension) onto latest `main`, never merging the branch. **For B.1 and beyond:
  before merging/adopting any older branch, diff it against current `main` — if it
  touches governance/layout files it did not intend to, cherry-pick the substance
  instead.** (This is the same base-branch trap the A.2 lessons flagged, in a new guise.)
- **Placeholder-in-command bites in CloudShell.** The operator pasted the literal
  `verify --manifest <the path capture printed>` twice — bash threw
  `syntax error near unexpected token 'newline'`, and the `verify` never ran. **Give
  the operator the fully-substituted command with the real manifest path filled in**,
  not a `<placeholder>`; and have them `echo "…_EXIT=$?"` so the exit code is captured.
- **Run commands from the repo dir.** A `verify` was first run from `~` (home) and
  failed `can't open file '.../scripts/ztie-restore'` (bash exit 2, not the tool's
  account-mismatch exit 2). Always `cd ~/ZTIE-Issues` first; the prompt `~ $` vs
  `ZTIE-Issues $` tells you which dir you're in.
- **`capture` warns "working tree is dirty" — that's expected here.** The untracked
  manifest file is present in the tree at capture time, so the governance pin is
  flagged dirty. It is harmless for A.4 (the floor tag rides the merged status commit).
  If a perfectly-clean pin is ever needed, capture to a temp dir outside the repo, then
  move the file in — but that was not required for A.4.
- **Re-runs leave stray manifests.** A first Forensic `capture` (`…200944Z`) was made,
  then STEP 0 was re-run and a second Forensic `capture` (`…201931Z`) was the one
  actually `verify`-clean. Both got committed; the executor removed the unverified
  stray so the floor points at exactly one manifest per account. **Watch for
  more-than-two manifests on the branch and keep only the verified pair.**
- **GitHub auth in CloudShell:** the account password / bare PAT-as-password is
  rejected (`Password authentication is not supported`). Use the token-in-URL HTTPS
  remote: `git remote set-url origin https://<TOKEN>@github.com/warrenrutledge64/ZTIE-Issues.git`.
  A PAT was pasted in the clear again this session — **rotate it.**
- **Two accounts, two tabs, `sts get-caller-identity` before every block** — still the
  standing rule (it held this session; both captures landed in the right account).
