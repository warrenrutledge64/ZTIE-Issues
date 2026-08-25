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

## Canonical copy vs. the bundled runtime copy

`schemas/intake-tracking.contract.v1.json` **and**
`schemas/classification.contract.v1.json` are the **canonical** repo copies. The Hub
validator Lambda needs each schema at runtime, so byte-identical copies are bundled
into its asset (`lambdas/hub_ingest/intake-tracking.contract.v1.json` and
`lambdas/hub_ingest/classification.contract.v1.json`). The pairs must stay
byte-identical. The classification contract is generated by
`python scripts/gen_classification_contract.py`, which writes **both** locations from
one source so they cannot drift; the intake-tracking pair must be kept in sync by
hand until the G-2 consistency checker asserts it in CI. If you edit a contract,
update **both** copies and confirm they hash-match.
