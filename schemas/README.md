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


## Canonical copy vs. the bundled runtime copy

`schemas/intake-tracking.contract.v1.json` is the **canonical** repo copy. The Hub
validator Lambda needs the schema at runtime, so an identical copy is bundled into
its asset at `lambdas/hub_ingest/intake-tracking.contract.v1.json`. The two must stay
byte-identical. A future story (G-2, the management-artifact consistency checker) will
assert this in CI; until then, if you edit the contract, update **both** copies (or
re-copy canonical → lambda dir) and confirm they hash-match.
