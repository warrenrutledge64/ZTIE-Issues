# Session Brief — Story 2.5

> One brief per story (stored under `session-briefs/`), populated from
> [`RUNBOOK.md`](../../RUNBOOK.md). This is the stakeholder-facing spec and the
> change/audit record for the story.

---

## Story 2.5 — Telemetry sanitization pipeline (entropy scrub → noise suppress → ≤25K truncation)

| Field | Value |
|-------|-------|
| **Phase** | P2 — Parallel Inspection (the DYNAMIC lane, deepened) |
| **Date** | TBD (next session) |
| **Status** | ⬜ Not Started (build tier 8; next story by tier now that 2.4 is ✅) |
| **Depends on** | **2.4 ✅** (behavioral telemetry capture — the RAW telemetry 2.5 sanitizes; validated live 2026-09-10) |
| **Builds from restore point** | `restore/story-2.4-green` (to be tagged by the owner on the 2.4 validated merge commit). Branch the CODE off current `main` (contains merged 2.3 + 2.6 + 2.4). |
| **Session goal** | Take the RAW behavioral trace Story 2.4 captures and SANITIZE it for Phase-3 correlation: strip high-entropy blobs, suppress host/runtime noise, and truncate to a ≤25K-token budget — producing a clean, bounded, token-budgeted derived view without losing the artifact's salient behavior. |

---

### Background & Context

ZTIE is a four-phase AWS-native security pipeline; work is validation-gated (nothing
is ✅ until a recorded live pass — the covenant). Phase 2's dynamic lane RUNS the
artifact (2.3) and now CAPTURES its runtime behavior (2.4 ✅ 2026-09-10): the ephemeral
host records syscalls / network connection attempts / filesystem operations with
host-native `strace`, the FULL trace stays in Forensic S3 (`traces/`, RD-009), and a
bounded, verdict-free behavioral SUMMARY crosses to the Hub as the 8th RD-013 envelope
kind. **2.5 is the sanitization stage on top of that capture.** 2.4 deliberately
captures RAW behavior — which faithfully includes the SSM-agent + shell/coreutils host
noise, high-entropy strings, and can be large. 2.5 turns that raw material into the
clean, bounded, ≤25K-token view the Phase-3 Nova Pro correlation engine reasons over.

### What This Story Is (nature + gate role)

**Nature: NEW FEATURE story.** It may begin only if its Depends-on are ALL ✅ **and**
the Validation Debt Register is empty. Both are true as of 2026-09-10: **2.4 ✅** and the
register is EMPTY (2.4 cleared on its own recorded live pass). STEP 0 must still
RE-CONFIRM this on `main` (trust `main` + `check_docs` over this brief) before touching
anything.

### Objective & Value

- **Objective:** a sanitization pipeline that consumes the raw behavioral telemetry
  (the Forensic trace + / or the 2.4 summary) and applies, in order: (1) **entropy
  scrub** — redact/replace high-entropy blobs (keys, base64 payloads, random tokens)
  that carry no behavioral signal and inflate the token budget; (2) **noise suppress**
  — drop the deterministic host/runtime noise (SSM-agent boot, dynamic-linker library
  loads, locale-archive opens, shell/coreutils startup) that is NOT the artifact's own
  behavior, so the artifact's salient ops become legible; (3) **≤25K-token truncation**
  — bound the result to the Phase-3 token budget, deterministically and with a recorded
  truncation flag. Output a bounded, derived, verdict-free SANITIZED telemetry view.
- **Why it matters:** Phase-3 correlation (Nova Pro) needs a clean, bounded, honest view
  of what the artifact DID — not a raw multi-hundred-line trace dominated by host noise
  and high-entropy junk. 2.5 is what makes the behavioral evidence usable by the model.

### Scope, Dependencies & Position

- **In scope:** the entropy-scrub → noise-suppress → ≤25K-token-truncation pipeline as
  PURE, offline-testable logic (the proven 1.2→2.2→2.3→2.4 lane pattern: pure logic +
  thin seams); where the sanitized view lives + whether it crosses as its own envelope
  kind or refines 2.4's summary (a design decision to make CONTRACT-FIRST); the token
  budget + a deterministic truncation with a recorded truncated flag; tests; a new RD
  for the sanitization design + candidate control mappings.
- **Out of scope / do NOT touch:** behavioral CAPTURE (that is 2.4 — done); the Hub
  verdict; the static lane; the fork/orchestration internals (2.6) — but you MUST
  redeploy the lane stacks it orchestrates for validation (deploy-gap, below); Docker on
  the host.
- **Depends on:** **2.4 ✅** (no raw telemetry to sanitize without the capture). Plus an
  **empty Validation Debt Register**.
- **Unblocks:** 3.2 (Nova Pro correlation consumes the sanitized ≤25K-token view).
- **Roadmap position:** P2 dynamic lane, deepened — the sanitization stage on the
  captured telemetry. NOTE: 2.5 + 2.4 together complete the P2 dynamic-lane telemetry
  chain; confirm the P2 phase-gate wording on `main` at STEP 0.

### Approach & Constraints

- **Expected true-state (STEP 0 re-confirms; trust `main` + `check_docs`):** 2.4 ✅;
  Validation Debt Register EMPTY; advancement gate OPEN. Next free RD number: re-verify
  with `grep -oE "RD-0[0-9][0-9]" PROJECT_PLAN.md | sort -u | tail` and take the next
  free number (RD-030 is 2.4's; expect RD-031, but VERIFY).
- **Approach:** (1) STEP 0 + confirm the register is empty; (2) design the sanitized
  view CONTRACT-FIRST (bounded, verdict-free, token-budgeted; decide own-envelope-kind
  vs refine-2.4); (3) PURE pipeline logic (entropy scrub / noise suppress / truncate) +
  thin seams; (4) wire it into the telemetry path; (5) redeploy the lane stack(s), then
  the STAKEHOLDER validates live; (6) record + flip ✅ (paired commit); PROJECT_PLAN ↔
  RUNBOOK aligned; PR.
- **Roles:** the LIVE run is the **stakeholder's** action in Forensic (executor has NO
  live creds); the **executor RECORDS** the returned output verbatim. Do NOT simulate.
- **Hard constraints:** sanitize, don't re-capture; output is EVIDENCE, never a verdict;
  relative monotonic timestamps preserved; the full raw trace stays in Forensic (RD-009)
  — only the bounded sanitized view crosses; production code (no mock telemetry); docs
  first-class (RD-015), PR-reviewed.

### Validation Rationale & Compliance Mapping (REQUIRED — RD-014)

- **Rationale:** sanitization is what makes the raw behavioral evidence usable and
  bounded for automated correlation without leaking high-entropy secrets or drowning the
  signal in host noise.
- **Candidate control mappings** *(proposed; ratified on review):*

| Framework | Control ID | Control Name | Rationale | Status |
|-----------|-----------|--------------|-----------|--------|
| NIST 800-53 r5 | SI-4 | System Monitoring | Refines runtime-behavior monitoring into an analyzable form | Proposed |
| NIST 800-53 r5 | SC-28 | Protection of Information at Rest | Entropy scrub redacts secrets before they cross | Proposed |
| NIST 800-53 r5 | AU-6 | Audit Record Review/Analysis | Noise suppression makes the behavioral record reviewable | Proposed |
| NIST CSF | DE.AE-2 | Detected events are analyzed | Sanitized telemetry is the analyzable event stream | Proposed |
| ISO 27001:2022 | A.8.16 | Monitoring activities | Prepares monitored behavior for analysis | Proposed |
| ISO 27001:2022 | A.8.12 | Data leakage prevention | Entropy scrub prevents secret leakage into the crossed view | Proposed |

- **Audit evidence produced:** the dated Validation Result in RUNBOOK 2.5; the sanitized
  telemetry view (bounded, ≤25K tokens, truncated flag) on the Hub/derived record; the
  raw trace still in Forensic; a before/after showing host noise + high-entropy blobs
  removed and the artifact's salient ops preserved.

### Management-Artifact Obligations (REQUIRED — RD-015)

- [ ] Story's brief + runbook entry updated (status, Validation Result, dates).
- [ ] PROJECT_PLAN and RUNBOOK in exact alignment (2.5 identical in both).
- [ ] New RD (sanitization design) recorded; candidate control mappings (RD-014) recorded.
- [ ] All doc changes PR-reviewed (branch + PR, never straight to main).
- [ ] Governance kept restorable alongside the code.
- [ ] On validation pass: record Validation Result + flip ✅ (paired commit).
- [ ] Author the next-story handoff (3.1 telemetry aggregation, or as the graph leaves it) with real Lessons Learned.

### Change & Rollback

- **Change type:** normal (new sanitization logic + a bounded sanitized view; refines
  the 2.4 telemetry path).
- **Restore point this builds from:** `restore/story-2.4-green` (to be tagged by the
  owner on the 2.4 validated merge commit).
- **Backout plan:** if a check fails, 2.5 stays 🟡 (added to the Validation Debt Register
  in the same commit); fix + re-validate.

### Definition of Done / Validation Gate

> A pass/fail gate, not a description. The stakeholder validates live; the executor
> records; only a recorded pass flips status.

- **Done means (the stakeholder confirms live):**
  1. A real detonation's RAW behavioral trace is run through the pipeline and the
     SANITIZED output has host/runtime noise suppressed and high-entropy blobs scrubbed,
     while the artifact's salient behavior is preserved.
  2. The sanitized view is bounded to ≤25K tokens (deterministic truncation with a
     recorded truncated flag).
  3. The sanitized view is EVIDENCE (no verdict/safe/forward field); the FULL raw trace
     still stays in Forensic (RD-009); relative monotonic timestamps preserved.
  4. It crosses / attaches per the RD-013 gate (its own version pin if a new kind).
- **Validated by:** the stakeholder, live; the executor records verbatim.
- **Validation Result:** `pending`.
- **On pass (and only then):** record the dated Validation Result, flip 2.5 ✅ (paired
  commit), keep PLAN ↔ RUNBOOK aligned; capture a restore point (owner action).
- **On fail:** 2.5 stays 🟡; re-focus on fixing + re-validating; no advancement.

### Risks & Watch-Items

- **DEPLOY-GAP (highest-priority, learned live in 2.6 + re-confirmed in 2.4).** 2.5
  touches the detonation/telemetry path that 2.6's orchestration direct-invokes. If
  validation runs against OLD deployed lane code, the run misbehaves. **The 2.5
  LIVE-RUNBOOK must list "redeploy `ZtieDetonationStack` (and the Hub stack if the
  contract changed) BEFORE submitting a run" as an explicit pre-run step.** In 2.4 the
  detonation-stack redeploy was the step that made each code change actually take effect
  live.
- **Host noise is the target, not an accident.** 2.4's raw trace faithfully includes the
  SSM-agent boot, dynamic-linker library loads, locale-archive opens, and shell/coreutils
  startup. 2.5's noise-suppression is specifically about distinguishing that
  deterministic host noise from the artifact's own behavior. Design the suppressor around
  what 2.4 actually captured (look at a real `traces/<intake_id>/behavior-trace.txt`).
- **Entropy scrub must not destroy behavioral signal.** Redact high-entropy VALUES
  (blobs/keys) while keeping the structure (which syscall, which path shape) that carries
  behavioral meaning.
- **Deterministic, bounded truncation.** The ≤25K-token budget must be applied
  deterministically with a recorded `truncated` flag; never silently drop.
- **Relative clock only** (carried from 2.4): behavioral timings stay relative monotonic
  offsets from detonation start, never a wall clock.
- **AMI tooling:** the ubuntu-22.04 golden AMI ships `strace` (2.4 confirmed) but NOT
  `curl` (2.4's curl probe produced no execve). If a 2.5 test needs a network syscall,
  use a binary the AMI ships or add the tool to the golden AMI (Image-Builder-owned).
- **CloudShell `/tmp` + shell vars + pip installs are WIPED on session recycle.** Re-set
  variables + reinstall `awscurl` in the SAME block before use (bit us repeatedly in
  2.4's live run).
- **RD-number collisions happen.** Take the next free RD from CURRENT `main`.

### Lessons Learned / Carry-Forward

**From Story 2.4's build + LIVE VALIDATION (2026-09-10) — most relevant to 2.5:**
- **Capture-completeness bug found live, fixed before flip (fix-then-validate-once):**
  the first two live runs captured only SSM-agent/shell noise and ZERO artifact ops
  because `strace` traced a `sh -c 'if head -c2 FILE | grep -q "^#!"; then FILE; …'`
  WRAPPER (the shebang check ran as forked `head`/`grep` children that dominated the
  slice) and its single `-o` file was read partially-flushed. **Fix (commit 71c3387):**
  decide the shebang in the OUTER (untraced) shell so strace's traced argv[0] is the
  artifact/interpreter itself; `strace -ff` (one trace file PER PID, concatenated on
  emit) so a child's trace can't be lost to another process's buffering; `sync` before
  reading. **2.5 must not regress this when it post-processes the trace.**
- **The third run PASSED 4/4** (intake `16c2af41…`): a 40× file-op `raw_script` was
  captured host-native (`execve("/tmp/ztie/sample3.sh")` traced directly,
  `outcome=completed`), full 261-line trace in Forensic `traces/…`, and the crossed
  `behavior` summary carried the artifact's OWN `/tmp/ztie-evil-0..30.txt` paths
  (`filesystem.total_ops=34`, `capture_status=captured`), no-verdict grep empty, relative
  offsets. This is the raw-telemetry shape 2.5 will sanitize.
- **Host noise dominated the crossed top-50 sample** until the test artifact repeated an
  op 40× — direct motivation for 2.5's noise-suppression stage. Look at a real trace and
  build the suppressor around the actual SSM-agent/linker/locale noise seen.
- **`network.connect_attempts=0` was honest, not a bug:** `curl` is not on the golden AMI
  (no `curl` execve in the trace), so the artifact made no network syscall. AMI tooling
  gaps are Image-Builder-owned (outside this repo).
- **Deploy sequence that worked (both tabs, `aws sts get-caller-identity` before EVERY
  block):** redeploy `ZtieDetonationStack` in Forensic → redeploy `ZtieHubTrackingStack`
  in the Hub (ships the new contract bundle or the crossed record fail-closed
  quarantines) → submit via `awscurl` (JSON envelope `{filename, content_type, submitter,
  content_base64}`, URL last, `-d @file.json`; `pip install awscurl` first) → verify
  trace in Forensic (Tab A) + summary in the Hub tracking table (Tab B). The single most
  repeated operator mistake was running a block in the wrong account/tab — confirm
  identity first, every time. Placeholders like `<...>` in a pasted command are literal
  `<`/`>` shell redirections and error with `syntax error near unexpected token` — always
  substitute REAL values before running.
- **User notes:** *(open for the stakeholder to add anything before the 2.5 session.)*

> **Sequencing note:** 2.5 (sanitization) is the next story by build tier (tier 8) now
> that 2.4 closed ✅. It turns the raw behavioral capture into the clean, bounded,
> token-budgeted view Phase-3 Nova Pro correlation consumes; 3.2 depends on it.
