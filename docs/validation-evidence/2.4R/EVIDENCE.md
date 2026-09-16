# Story 2.4R — Retained Validation Evidence (RD-054) — **SEALED VERDICT: FAIL**

> **This folder is the audit trail of a FAILED validation, not a pass.** Story 2.4R was
> live-validated under the RD-053 split-brain protocol on 2026-09-16 and the independent
> validator (Gemini) returned a **SEALED VERDICT: FAIL**. Per the covenant, **Story 2.4R
> stays 🟡 (In Progress)** and remains on the Validation Debt Register; nothing is flipped
> ✅. These artifacts are retained (RD-054) so the failure is auditable rather than
> testimony — a third party can re-derive the FAIL from the raw files here.

## Provenance (RD-054 marker ④)
- **Story:** 2.4R — RD-054 evidence backfill of the DYNAMIC lane (strace behavioral telemetry; remediation of 2.4).
- **intake_id:** `2b0af6a6-6552-461f-a18f-f6cca60ba0bc`
- **artifact sha256:** `bbf851a1805eb25197afce1d3166be6b325001807fd9a97de7abb728d0464941`
- **commit SHA under test:** `566e274` (the 2.4 dynamic-lane merge — PRs #78 build + #79 strace-wrapper fix).
- **artifact filename / class:** `adversarial.sh` / `raw_script`; **submitter:** `ztie-2.4R-live`.
- **accounts:** Forensic `360999005254` (detonation + full trace) / Hub `641628980935` (tracking record).
- **run window:** 2026-09-16 ~20:00–20:02Z (per the item timestamps).
- **adjudicated:** 2026-09-16, live, under the RD-053 split-brain protocol; **SEALED VERDICT
  FAIL** returned by the independent validator (Gemini); the raw output below was read by the human.

## Retained raw artifacts (in this folder)
| File | What it is |
|------|-----------|
| `adversarial.sh` | The known-behavior adversarial payload submitted (write-buffer + a backgrounded `/dev/tcp` network-intent to test `strace -ff` child following). |
| `behavior-trace-2.4R.txt` | The raw Forensic strace trace as returned by the live run (the artifact's own execution). |
| `dynamodb-summary-2.4R.json` | The Hub tracking-item **key-fields projection** for this intake. NOTE: this is the material-fields projection of the live item (the long repeated locale `newfstatat` lines, per-call `input_tokens`/`latency_ms`, and the full sanitized `events[]` list were condensed for size); the full-fidelity raw strace is `behavior-trace-2.4R.txt` and the item's own `dynamic_run.execution.stdout_tail`. |

## Sealed verdict (transcribed VERBATIM from the validator; not re-judged by the executor)

```
SEALED VERDICT: [ FAIL ]

[FAIL] DoD 1: Positive Adversarial Capture
   (Raw trace in Forensic S3 completely missed the write buffer, proving execution
    truncation/child-drop vulnerabilities).
[PASS] DoD 2: Boundary Integrity (No Leakage)
   (No buffer data leaked into the Hub DynamoDB).
[FAIL] DoD 3: Human Verification
   (Verdict fields like `recommended_verdict` were present in the DynamoDB item,
    violating the strict evidence-only requirement for this test).
[PENDING] DoD 4: Retained Raw Evidence
   (Awaiting stakeholder commit of the run artifacts — satisfied by THIS folder).
```

## DoD-by-DoD, corroborated by the raw artifacts

### [FAIL] DoD 1 — Positive adversarial capture (the write buffer was NOT captured)
The payload's first action is `echo "ZTIE-EVIL-BUFFER-DATA" > /tmp/ztie-leak-test.txt`. The
raw trace shows the file was **created** but the buffer **content was never captured**:

```
$ grep -c 'ZTIE-EVIL-BUFFER-DATA' behavior-trace-2.4R.txt     # -> 0  (buffer string absent from the trace)
$ grep -c '^.*\bwrite(' behavior-trace-2.4R.txt               # -> 0  (NO write() syscall captured at all)
# the file is only ever seen as an open, never a write:
20:02:16.951628 openat(... "/tmp/ztie-leak-test.txt", O_WRONLY|O_CREAT|O_TRUNC, 0666) = 3</tmp/ztie-leak-test.txt>
```
And the crossed Hub summary records it as an `op: create` with **no write op-class**
(`dynamodb-summary-2.4R.json` → `behavior.filesystem.paths[] path=/tmp/ztie-leak-test.txt op=create`).
A capture that misses the artifact's own `write()` of a planted buffer is **incomplete** —
this is INCONCLUSIVE/FAIL for a positive-exercise security boundary, never PASS.

**Root causes to fix (fix-forward, next rework):**
1. **strace does not trace `write` (and likely the wider `%file`/`write` group).** No `write(`
   appears anywhere in the trace, so the strace `-e trace=...` set omits `write`. The capture
   must trace the write-class syscalls (`write`, `pwrite64`, `writev`) so a planted buffer is
   observable.
2. **Child-process / truncation exposure.** The validator flagged the `cat $(ls … | sort)`
   alphabetical-sort concatenation pushing the artifact's PID trace out of the 512KB
   truncation window (or the wrapper failing to follow child processes). The trace here is
   short (single artifact), so truncation did not bite this run — but the concatenation/ordering
   defect remains and must be fixed so a real (larger) multi-PID trace cannot drop the
   artifact's own PID.

### [PASS] DoD 2 — Boundary integrity (no leakage) — but hollow
The planted buffer string did **not** cross into the Hub tracking item:

```
$ grep -c 'ZTIE-EVIL-BUFFER-DATA' dynamodb-summary-2.4R.json   # -> 0  (no buffer leakage into the Hub)
```
This PASSES the leakage check — but it is a **hollow pass**: the buffer was never captured
in the first place (DoD 1), so "it didn't leak" proves nothing about redaction of a value
that was actually observed.

### [FAIL] DoD 3 — Human verification / evidence-only (verdict fields present)
The negative probe for verdict fields on the tracking record returned multiple hits:

```
$ grep -oE '"(verdict_at|verdict_result|recommended_verdict)"' dynamodb-summary-2.4R.json | sort -u
"recommended_verdict"
"verdict_at"
"verdict_result"
```
Per the runbook's strict rule, any hit on these fields during this check is a DoD-3 FAIL.
**Observed cause (for the fix, not an excuse):** these were written by the **Phase-3
`hub_verdict` Lambda (RD-040)** running concurrently on the same tracking item —
`verdict_result.recommended_verdict = "FAIL"` (advisory, `human_decision: pending`,
driven by combined score 75). They are legitimate Phase-3 advisory fields, but the 2.4R
DoD-3 probe (which asserts an evidence-only dynamic-lane record) does not tolerate them.

**Fix-forward options for the next rework (stakeholder to choose):** either (a) scope the
DoD-3 negative probe to the `behavior` attribute only (not the whole item, which
legitimately carries Phase-3 advisory fields), or (b) run the 2.4R validation against a
detonation-only path that does not trigger the Phase-3 verdict stage. This is a
**validation-probe scoping** decision, distinct from the DoD-1 capture defect.

### Network-intent observation (feeds the DoD-1 fix)
The payload's `exec 3<>/dev/tcp/93.184.216.34/443` surfaced as a **file `openat`, not a
`connect()`**, and `network.connect_attempts = 0`:
```
20:02:18.964376 openat(... "/dev/tcp/93.184.216.34/443", O_RDWR|O_CREAT, 0666) = -1 ENOENT (No such file or directory)
```
Cause: Ubuntu's `/bin/sh` is `dash`, which has **no `/dev/tcp` pseudo-device** (that is a
`bash` feature), so it literally tried to `open()` a file. The next rework's known-behavior
artifact must use a binary/interpreter that issues a real `connect()` (e.g. invoke `bash`
explicitly, or use a base binary that opens a socket) so the network-INTENT path is
genuinely exercised.

## [PENDING → satisfied] DoD 4 — Retained raw evidence (RD-054)
The three raw artifacts above are committed alongside this record; this folder satisfies the
"retain the run artifacts as a permanent audit trail of the failure" requirement.

## Human attestation (RD-054 marker ③-human)
> Attested by: warren (stakeholder), 2026-09-16. I ran the 2.4R adversarial validation live
> (intake `2b0af6a6-6552-461f-a18f-f6cca60ba0bc`, code under test commit `566e274`), read the
> raw Forensic strace trace and the Hub tracking record, and confirm: the planted write buffer
> `ZTIE-EVIL-BUFFER-DATA` is **absent** from the raw trace (DoD 1 FAIL — capture incomplete);
> the buffer did **not** leak into the Hub item (DoD 2 PASS); and verdict fields
> (`recommended_verdict`/`verdict_result`/`verdict_at`) **are present** in the item (DoD 3 FAIL
> per the strict evidence-only probe). The independent validator (Gemini) adjudicated a
> **SEALED VERDICT: FAIL** on this evidence.

## Outcome
**2.4R = FAIL → stays 🟡 (In Progress), remains OPEN on the Validation Debt Register, the
advancement gate stays ARMED.** Story 2.4 remains ✅ for what it validated live 2026-09-10;
2.4R is its RD-054 evidence backfill and must be **fixed then re-validated once** (fix-forward,
covenant §4). The next rework must address: (1) strace must capture write-class syscalls; (2)
the `cat | sort` concatenation / child-follow / 512KB-truncation ordering defect; (3) the
network artifact must exercise a real `connect()`; and (4) the DoD-3 verdict-field probe must
be scoped to the `behavior` attribute (or the run must avoid triggering the Phase-3 verdict
stage). A future PASS requires a fresh live run of the FIXED code with its own retained evidence.
