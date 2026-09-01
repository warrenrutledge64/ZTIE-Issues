# ZTIE Data Contracts

This directory holds the **enforced data contracts** that govern boundaries between
ZTIE components. A contract here is not documentation — it is the machine-checked
allow-list a validating gate enforces before any data is trusted.

## `intake-tracking.contract.v1.json` — the Forensic → Hub boundary (RD-013)

### Why this exists

The Forensic account (360999005254) is the blast zone: it is where the untrusted
artifact is received and (later) detonated. The Hub account (641628980935) is the
brains/control plane and must be kept **out of the blast zone** (RD-009). The single
most dangerous path in the whole system is the pipe *out* of Forensic *into* the Hub,
because everything leaving Forensic is attacker-influenced.

Per **RD-013**, we do **not** police what goes *into* Forensic (assumed dirty). All
rigor is on the **exit**. Nothing crosses to the Hub unless it satisfies this strict,
bounded, allow-list schema, enforced by a **Hub-owned validating ingestion gate**.
Forensic holds **no direct write** to Hub data.

### The contract's guarantees

- **Allow-list, not deny-list.** `additionalProperties: false` at every object level.
  A field the Hub didn't ask for is a rejection, not a silently-dropped extra.
- **No payload, no executable field.** There is deliberately no property for the raw
  artifact body, no base64 blob, no code. The schema *cannot* carry executable content
  because there is nowhere to put it. Only **derived** descriptive metadata crosses.
- **Everything typed + length-capped.** Every string has a `maxLength`; `size_bytes`
  is bounded to the intake ceiling; ids/hashes are `pattern`-locked (UUIDv4, 64-hex
  sha256, 12-digit account id). This bounds total record size and nesting.
- **Integrity-keyed.** `intake_id` (UUIDv4) + `sha256` bind the record to exactly one
  artifact. The Hub upserts **by `intake_id`** — no cross-record writes.
- **Verdict is Hub-owned.** `status` is an allow-list of Forensic-side lifecycle
  values (currently just `RECEIVED`). The human verdict (PASS/FAIL/INCONCLUSIVE) is
  **not** in this contract and is **never** imported or self-asserted from crossed
  data — it is decided Hub-side by the human gate (Phase 4).

### How it is enforced (fail-closed)

```
Forensic intake Lambda                    Hub (control plane)
----------------------                    -------------------
POST /intake
  ├─ store raw body -> Forensic S3 (octet-stream; stays in blast zone)
  └─ build DERIVED envelope (this contract)
        │  sqs:SendMessage  (one-directional, least-privilege:
        │                    Forensic role may ONLY SendMessage to this one queue)
        ▼
   Hub ingest SQS queue ──────────────▶ Hub validator Lambda
        │  (redrive on failure)              │  jsonschema validate against
        ▼                                     │  intake-tracking.contract.v1.json
   Hub ingest DLQ                             ├─ PASS → idempotent upsert-by-intake_id
                                              │         into Hub tracking DynamoDB
                                              └─ FAIL → write raw envelope to Hub
                                                        quarantine S3 (+ reason);
                                                        NEVER to the live table
```

- **Fail-closed:** a non-conforming record (malformed, oversized, unknown field,
  wrong version, bad pattern, injection-crafted) is **quarantined**, never written to
  the live tracking table.
- **One-directional, least-privilege:** the Forensic principal is granted exactly
  `sqs:SendMessage` on exactly the one ingest queue, via the queue's resource policy.
  It has **no** permission on the Hub tracking table, the quarantine bucket, or
  anything else in the Hub.
- **Idempotent:** SQS is at-least-once; the upsert-by-`intake_id` makes redelivery
  safe by construction.

### Escaping on render

This contract keeps *executable content* out of the Hub, but free-text fields
(`filename`, `submitter`) are still attacker-influenced. The dashboard (Phase 4) MUST
escape these on render (no stored XSS in the brains) — the contract carries them as
inert strings; it does not sanitize their *content*, only bounds their *shape*.

### Versioning

`contract_version` is pinned (`enum`). A future shape change ships as
`intake-tracking.contract.v2.json` with its own `contract_version`; the validator
rejects any envelope whose version it does not recognize (fail-closed), so an old
Forensic emitter can never silently write a new-shaped record or vice-versa.


## `classification.contract.v1.json` — the preprocessor label (Story 1.2, RD-013)

### Why this exists

Story 1.2's `preprocessor` classifies each intake artifact (IaC template / raw
script / other-unknown) by inspecting its **actual content**, not the untrusted
claimed type. That classification is a **second kind of envelope** that crosses the
same one-directional Forensic → Hub door as the intake-tracking envelope, so it needs
the same enforced allow-list contract.

### The contract's guarantees

- **Allow-list.** `additionalProperties: false` at every level; every field typed and
  `enum`/`maxLength`-bounded.
- **Integrity-keyed.** `intake_id` (UUIDv4) + `sha256` bind the label to exactly the
  artifact it was computed over. The Hub applies it with a conditional
  `update_item` that requires the tracked record to exist **and** its stored
  `sha256` to match; a mismatch is quarantined (a label for the wrong artifact never
  lands).
- **Derived-only.** No raw body / base64 / executable content field exists.
- **LABEL, not verdict.** There is deliberately **no** `verdict` / `safe` / `route`
  field — a classification is a label. The verdict is Hub-side / human-gated
  (Phase 4); routing is Story 1.3. The label crossing never touches the record's
  `status`.
- **Distrust-the-claim, auditable.** The result records BOTH the `extension_signal`
  and the `content_signal`, whether they `signals_agree`, and the `basis` the final
  class rests on — so a claim/content mismatch is visible evidence, and content wins.

### How it is enforced (fail-closed)

```
Forensic preprocessor Lambda                Hub (control plane)
----------------------------                -------------------
S3 ObjectCreated (intake/ prefix)
  ├─ read intake-id + sha256 (S3 metadata) + a bounded HEAD slice (stays in Forensic)
  ├─ classify(filename, content_bytes)  (pure; content wins over the claim)
  └─ build DERIVED label envelope (this contract)
        │  sqs:SendMessage  (same one-directional Hub ingest queue as intake)
        ▼
   Hub ingest SQS queue ──────────────▶ Hub validator Lambda (routes by envelope kind)
                                              │  jsonschema validate against
                                              │  classification.contract.v1.json
                                              ├─ PASS → conditional update_item onto
                                              │         the tracking record (exists AND
                                              │         sha256 matches); never creates,
                                              │         never touches status/verdict
                                              └─ FAIL → quarantine S3 (+ reason);
                                                        sha-mismatch also quarantines,
                                                        record-absent retries (ordering)
```

### Versioning

`contract_version` is pinned (`enum`), same discipline as the intake-tracking
contract.


## `routing.contract.v1.json` — the preprocessor routing decision (Story 1.3, RD-013)

### Why this exists

Story 1.3's `router` turns the derived class **label** (Story 1.2) into a **routing
decision** — a *plan of which controls to apply*: which downstream Phase-2 lane(s)
the artifact enters, or the safe-reject entry (Story 1.4) when it is unroutable. That
decision is a **third kind of envelope** that crosses the same one-directional
Forensic → Hub door as the intake-tracking and classification envelopes, so it needs
the same enforced allow-list contract.

### The contract's guarantees

- **Allow-list.** `additionalProperties: false` at every level; every field typed and
  `enum`/`maxLength`-bounded. The `lanes` array is a bounded (`minItems:1`,
  `maxItems:3`), `uniqueItems` list drawn from a closed lane `enum`
  (`static_analysis`, `dynamic_detonation`, `safe_reject`).
- **Integrity-keyed.** `intake_id` (UUIDv4) + `sha256` bind the decision to exactly
  the artifact it was computed over. The Hub applies it with a conditional
  `update_item` that requires the tracked record to exist **and** its stored `sha256`
  to match; a mismatch is quarantined (a decision for the wrong artifact never lands).
- **Derived-only.** No raw body / base64 / executable content field exists.
- **PLAN OF CONTROLS, not verdict.** There is deliberately **no** `verdict` / `safe` /
  `approved` / `forward` field — a routing decision only says *which controls apply*.
  The verdict is Hub-side / human-gated (Phase 4); forward-to-PDE is a Phase-4
  decision. The routing crossing never touches the record's `status`.
- **Declarative + fail-safe.** `basis` records whether the lanes came from a
  routing-table entry (`class_route`) or the safe-reject fallback
  (`safe_reject_fallback`). `other_unknown` — and any unrecognised class — routes to
  `[safe_reject]` (handed to Story 1.4), never into a scanner and never dropped.

### How it is enforced (fail-closed)

```
Forensic preprocessor Lambda                Hub (control plane)
----------------------------                -------------------
S3 ObjectCreated (intake/ prefix)
  ├─ classify(filename, content_bytes)  (Story 1.2 — pure)
  ├─ route(artifact_class)              (Story 1.3 — pure; class -> lane plan)
  └─ build DERIVED routing envelope (this contract)
        │  sqs:SendMessage  (same one-directional Hub ingest queue)
        ▼
   Hub ingest SQS queue ──────────────▶ Hub validator Lambda (routes by envelope kind)
                                              │  jsonschema validate against
                                              │  routing.contract.v1.json
                                              ├─ PASS → conditional update_item onto
                                              │         the tracking record (exists AND
                                              │         sha256 matches); sets routing +
                                              │         routing_lanes; never creates,
                                              │         never touches status/verdict
                                              └─ FAIL → quarantine S3 (+ reason);
                                                        sha-mismatch also quarantines,
                                                        record-absent retries (ordering)
```

### The two Phase-2 fork targets + the safe-reject entry

The lane `enum` is the set of **addressable fork targets** the whole of Phase 2 hangs
off (see `docs/ARCHITECTURE.md`):

- `static_analysis` — the non-executing static lane (cfn-lint, cfn-guard, checkov,
  bandit). **Story 2.1.**
- `dynamic_detonation` — the dynamic lane: ephemeral EC2 + host-native SSM detonation.
  **Story 2.3.**
- `safe_reject` — the safe-reject entry for unroutable/incompatible artifacts. Owned
  by **Story 1.4** (1.3 only hands off to it).

Both routable classes (`iac_template`, `raw_script`) fork into **both** `static_analysis`
and `dynamic_detonation` (the architecture forks the two lanes in parallel).

### Versioning

`contract_version` is pinned (`enum`), same discipline as the other two contracts.


## `reject.contract.v1.json` — the safe-reject outcome (Story 1.4, RD-013)

### Why this exists

Story 1.4's `rejector` is the pipeline's **fail-safe**. When the router (1.3) cannot
route an artifact to any Phase-2 inspection lane (`routable=false`), 1.4 refuses it
**cleanly and terminally** — recording the outcome on the Hub tracking record. That
rejection is a **fourth kind of envelope** that crosses the same one-directional
Forensic → Hub door.

### The contract's guarantees

- **Allow-list.** `additionalProperties: false` at every level; every field typed and
  `enum`/`maxLength`-bounded.
- **Integrity-keyed.** `intake_id` + `sha256` bind the rejection to exactly the
  artifact. The Hub applies it with a conditional `update_item` (exists AND sha match);
  a mismatch is quarantined.
- **Derived-only.** No raw body / base64 / executable content field exists.
- **TERMINAL PROCESSING OUTCOME, not verdict.** `pipeline_outcome` is always
  `SAFE_REJECTED` — this is the pipeline's terminal state for an unroutable artifact.
  It is **NOT** the human verdict (PASS/FAIL/INCONCLUSIVE), which stays Hub-side /
  human-gated (Phase 4). There is no `verdict`/`safe`/`approved`/`forward` field.
- **Never crash, never drop.** The whole point: any artifact reaching `safe_reject`
  is refused cleanly and recorded, not silently lost.

### How it is enforced (fail-closed)

```
Forensic preprocessor Lambda                Hub (control plane)
----------------------------                -------------------
classify → route → routable=false?
  └─ reject(routing_decision)       (Story 1.4 — pure)
  └─ build DERIVED reject envelope (this contract)
        │  sqs:SendMessage  (same one-directional Hub ingest queue)
        ▼
   Hub ingest SQS queue ──────────────▶ Hub validator Lambda (routes by envelope kind)
                                              │  jsonschema validate against
                                              │  reject.contract.v1.json
                                              ├─ PASS → conditional update_item onto
                                              │         the tracking record; sets
                                              │         pipeline_outcome=SAFE_REJECTED +
                                              │         rejection + rejected_at; never
                                              │         creates, never touches verdict
                                              └─ FAIL → quarantine S3 (+ reason);
                                                        sha-mismatch also quarantines,
                                                        record-absent retries (ordering)
```

### Versioning

`contract_version` is pinned (`enum`), same discipline as the other three contracts.


## `static-scan-summary.contract.v1.json` — the static-lane summary (Story 2.1, RD-013)

### Why this exists

Story 2.1's `static_scan` lane runs four non-executing scanners (cfn-lint, cfn-guard,
checkov, bandit) over an artifact routed to `static_analysis`, and normalizes their
output into ONE findings document. That document may echo artifact content, so per
**RD-009** it **stays in Forensic** (S3). Only a bounded, derived **summary** crosses
to the Hub — a **fifth kind of envelope** on the same one-directional Forensic → Hub
door. (The full normalized document has its own shape,
`static-findings.contract.v1.json`, documented in
[`static-findings.contract.README.md`](static-findings.contract.README.md); it is
**not** a crossing contract — the Hub never parses it.)

### The contract's guarantees

- **Allow-list.** `additionalProperties: false` at every level; every field typed and
  `enum`/`maxLength`/range-bounded. `counts_by_severity` is a **fixed-key** object
  (one non-negative int per severity), so it cannot smuggle arbitrary keys.
- **Integrity-keyed.** `intake_id` + `sha256` bind the summary to exactly the artifact.
  The Hub applies it with a conditional `update_item` (exists AND sha match); a
  mismatch is quarantined.
- **Derived-only, no finding text.** The summary carries counts, per-tool run status,
  the worst severity, and a **pointer** (`findings_s3_bucket`/`findings_s3_key`) back
  to the full document in Forensic. It has **no field** for finding messages, matched
  lines, or resource names — none can cross.
- **EVIDENCE, not verdict.** There is deliberately **no** `verdict`/`safe`/`approved`/
  `forward`/`pass_fail` field. `highest_severity` is a descriptive roll-up of
  evidence, not a decision. The verdict is Hub-side / human-gated (Phase 4). The
  summary crossing never touches the record's `status`.
- **NON-EXECUTING (RD-001).** Records `non_executing: true`; the static lane inspects
  the artifact and never runs it.
- **Resilient.** Per-tool `status` records `ok`/`error`; a scanner error is recorded
  (with `error_reason`) and the lane keeps running the other tools — it never crashes.

### How it is enforced (fail-closed)

```
Forensic static_scan Lambda                 Hub (control plane)
---------------------------                 -------------------
static-scan job (SQS) for static_analysis
  ├─ read raw artifact from Forensic S3 (stays in Forensic)
  ├─ run the class-appropriate scanners (NON-EXECUTING: parse only)
  ├─ normalize -> ONE findings document; write to Forensic S3 (findings/ prefix)
  └─ build DERIVED summary envelope (this contract; pointer to the findings doc)
        │  sqs:SendMessage  (same one-directional Hub ingest queue)
        ▼
   Hub ingest SQS queue ──────────────▶ Hub validator Lambda (routes by envelope kind)
                                              │  jsonschema validate against
                                              │  static-scan-summary.contract.v1.json
                                              ├─ PASS → conditional update_item onto
                                              │         the tracking record; sets
                                              │         static_scan + static_scan_summary
                                              │         + scanned_at; never creates,
                                              │         never touches status/verdict
                                              └─ FAIL → quarantine S3 (+ reason);
                                                        sha-mismatch also quarantines,
                                                        record-absent retries (ordering)
```

### Versioning

`contract_version` is pinned (`enum`), same discipline as the other four contracts.

## Canonical copy vs. the bundled runtime copy

`schemas/intake-tracking.contract.v1.json`, `schemas/classification.contract.v1.json`,
`schemas/routing.contract.v1.json` **and** `schemas/reject.contract.v1.json` are the
**canonical** repo copies. The Hub validator Lambda needs each schema at runtime, so
byte-identical copies are bundled into its asset
(`lambdas/hub_ingest/intake-tracking.contract.v1.json`,
`lambdas/hub_ingest/classification.contract.v1.json`,
`lambdas/hub_ingest/routing.contract.v1.json` and
`lambdas/hub_ingest/reject.contract.v1.json`). The pairs must stay byte-identical.
The classification contract is generated by
`python scripts/gen_classification_contract.py`, the routing contract by
`python scripts/gen_routing_contract.py`, the reject contract by
`python scripts/gen_reject_contract.py`, and the static-scan summary by
`python scripts/gen_static_scan_summary_contract.py` (bundled into
`lambdas/hub_ingest/static-scan-summary.contract.v1.json`), each of which writes
**both** locations from one source so they cannot drift; the intake-tracking pair
must be kept in sync by hand until the G-2 consistency checker asserts it in CI. The
**static-findings** document (`schemas/static-findings.contract.v1.json`, generated
by `python scripts/gen_static_findings_contract.py`) is bundled into the
**static-scan** Lambda (`lambdas/static_scan/static-findings.contract.v1.json`) — not
the Hub — because the Hub never parses it; that pair is also generated from one
source. If you edit a contract, update **both** copies and confirm they hash-match.
