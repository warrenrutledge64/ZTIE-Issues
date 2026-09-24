# Story 4.7 — RD-054 Retained Validation Evidence (attempt-1)

> **Story 4.7 — REJECT → destroy artifact + detonation chamber in Forensic; INCONCLUSIVE → hold.**
> `[sec-boundary]` story (RD-047 + RD-048/RD-049). VALIDATED LIVE + SEALED **PASS** 2026-09-24 by
> the independent validator (Gemini, blind, RD-055) under the split-brain protocol, adjudicated
> on the raw artifacts retained below. This folder is the durable proof the ✅ rests on (RD-054:
> "trust the artifact, not the word — including the validator's"), captured at validation time
> because the Forensic blast zone is ephemeral.

## Provenance

| Field | Value |
|-------|-------|
| **Story** | 4.7 (RD-047, per RD-048/RD-049) |
| **Code under test** | branch `feature/story-4.7`, commit `3e73f4b593e666d3a2fcc31249f398769a97a70d` (PR #211); the live Hub ingest was redeployed from this branch to carry the new `disposition` RD-013 kind |
| **Destroy intake (leg a/d/e)** | `0c74042e-6976-4fdf-a39c-7599f9733921` (artifact `intake/0c74042e-…/probe.yaml`) |
| **Fail-safe HOLD intake (leg b)** | `08dd5caa-b2a6-425a-be3a-03509df860ed` (artifact `intake/08dd5caa-…/sample.sh`) |
| **Accounts** | Hub 641628980935 (signs the decision + holds the tracking ledger) · Forensic 360999005254 (destroyer + artifact + chamber) |
| **Human attester** | **Warren Rutledge** (stakeholder; ran every live block, read the raw output) |
| **Validator** | Gemini (independent, blind, RD-055) — sealed PASS on the raw artifacts below |
| **Date** | 2026-09-24 |

## Sealed verdict

**VERDICT: PASS** — all five DoD legs proven live with retained raw artifacts; the deploy-gap
that quarantined the first crossing attempt was closed and the crossing re-proven cleanly.

| DoD leg | Status | Evidence (below) |
|---------|--------|------------------|
| (a) Positive destroy on a verified `rejected` token | ✅ | §2 |
| (b) Fail-safe HOLD (no token → destroy nothing) | ✅ | §1 |
| (c) Least privilege / no spoke→Hub read (role has NO dynamodb; env NO TRACKING_TABLE) | ✅ | §4 |
| (d) Raw S3 `0/0` across all four intake prefixes after destroy | ✅ | §2 |
| (e) Bounded verdict-free `disposition` outcome crosses to the Hub; report survives | ✅ | §3 |

---

## §1 — POSITIVE-EXERCISE + PROOF-OF-ABSENCE (b): fail-safe HOLD destroys nothing

Intake `08dd5caa-b2a6-425a-be3a-03509df860ed`. The destroyer invoked with **no decision token**
(the INCONCLUSIVE path) held and destroyed nothing; the S3 prefixes were unchanged before/after.

```
# no-token invoke -> HOLD
destroyed: False   outcome: held   reason: no rejected decision token presented (hold at approval gate)

# S3 state AFTER the hold (UNCHANGED — nothing destroyed on a refusal)
== intake/08dd5caa-b2a6-425a-be3a-03509df860ed/ ==    { "versions": 1, "markers": 0 }
== findings/08dd5caa-b2a6-425a-be3a-03509df860ed/ ==  { "versions": 1, "markers": 0 }
== runs/08dd5caa-b2a6-425a-be3a-03509df860ed/ ==      { "versions": 1, "markers": 0 }
== traces/08dd5caa-b2a6-425a-be3a-03509df860ed/ ==    { "versions": 0, "markers": 0 }
```

**Fail-safe invariant proven:** absent a valid Hub-signed `rejected` token, NOTHING is destroyed.
(The sealed-run adversarial matrix additionally covered bad-signature / `accepted` / sha-mismatch /
stale / untrusted-key → all refuse; the offline test suites `test_reject.py` + `test_handler.py`
assert every branch, and the live no-token HOLD above is the recorded runtime proof-of-absence.)

## §2 — POSITIVE-EXERCISE (a, d): verified `rejected` token → real destroy → S3 purged

Intake `0c74042e-6976-4fdf-a39c-7599f9733921`, artifact sha256
`26e89a93db3c89960d36edee0a61a9d4488d22e9cd965c3541e615e97e0e764e` (computed live; the Hub-signed
`decision.token.v1` was `kms:Sign` ECDSA_SHA_256 over exactly that sha).

```
# verified rejected-token invoke -> DESTROY
destroyed: True   outcome: destroyed   observed: rejected   chamber: none_running

# S3 state AFTER the destroy (all four prefixes purged — versions AND delete-markers)
== intake/0c74042e-6976-4fdf-a39c-7599f9733921/ ==    { "versions": 0, "markers": 0 }
== findings/0c74042e-6976-4fdf-a39c-7599f9733921/ ==  { "versions": 0, "markers": 0 }
== runs/0c74042e-6976-4fdf-a39c-7599f9733921/ ==      { "versions": 0, "markers": 0 }
== traces/0c74042e-6976-4fdf-a39c-7599f9733921/ ==    { "versions": 0, "markers": 0 }
```

**Destroy invariant proven:** on a verified `rejected` token bound to the artifact sha256, the raw
artifact + all derived Forensic outputs are destroyed to `0/0` (no zombie versions/tombstones).
`chamber: none_running` — no live ephemeral EC2 for this intake (the 5-min hard TTL had already
reaped it; the terminate path is tag-scoped `Ephemeral=true`+`Project=ZTIE` per the stack policy).

## §3 — POSITIVE-EXERCISE + PROOF-OF-ABSENCE (e): the bounded, verdict-free crossing landed; report survives

The Hub tracking-ledger read for `0c74042e-…` AFTER the destroy — the bounded `disposition`
outcome crossed Forensic→Hub via the RD-013 ingest gate and applied integrity-bound:

```json
{
  "outcome": "destroyed",
  "disposition": {
    "artifact_s3_key": { "S": "intake/0c74042e-6976-4fdf-a39c-7599f9733921/probe.yaml" },
    "outcome": { "S": "destroyed" },
    "report_survives": { "BOOL": true },
    "chamber_state": { "S": "none_running" },
    "observed_decision": { "S": "rejected" },
    "reason": { "S": "verified Hub-signed rejected token + matching artifact sha256" },
    "hash_verified": { "BOOL": true },
    "destroyed": {
      "M": {
        "chamber": { "S": "none_running" },
        "destroyed_at": { "S": "2026-09-24T20:32:20.308159Z" },
        "prefixes_cleared": {
          "L": [
            { "S": "intake/0c74042e-6976-4fdf-a39c-7599f9733921/" },
            { "S": "findings/0c74042e-6976-4fdf-a39c-7599f9733921/" },
            { "S": "runs/0c74042e-6976-4fdf-a39c-7599f9733921/" },
            { "S": "traces/0c74042e-6976-4fdf-a39c-7599f9733921/" }
          ]
        },
        "artifact_versions_deleted": { "N": "4" }
      }
    }
  }
}
```

```
# No-banned-effective-verdict-key scan over the crossed disposition map (proof-of-absence):
OK: no effective-verdict key
```

**Crossing invariants proven:** `outcome: destroyed`, `observed_decision: rejected`,
`hash_verified: true`, `report_survives: true` (the derived Hub report record is NEVER touched by
4.7 — only the Forensic blast-zone artifact + chamber are destroyed), `artifact_versions_deleted: 4`,
and the scan confirms NO effective-verdict key (`verdict`/`safe`/`approved`/`forward`/`malicious`/
`pass_fail`/`clean`) crossed — the outcome is bounded EVIDENCE, never a verdict (RD-013/RD-040).

## §4 — PROOF-OF-ABSENCE (c): no spoke→Hub read (RD-048)

The Forensic destroyer role (`ZtieForensicRejectStack` `PdeReject` role) was verified to hold ONLY
`s3` (get/delete/list on the intake prefixes) + `ec2` (describe + tag-scoped terminate) +
`sqs:SendMessage` on the one Hub ingest queue — **NO `dynamodb`** action of any kind — and its Lambda
env carries `HUB_PUBLIC_KEY_PEM` + `TRUSTED_KEY_IDS` with **NO `TRACKING_TABLE`** and **NO
`NOVA_MODEL_ID`**. The decision is a Hub-signed `decision.token.v1` verified OFFLINE against the
embedded public key; the destroyer never calls the Hub. (Verified in the sealed run's IAM/env
inspection.)

---

## Deploy-gap encountered + closed (recorded for the audit trail)

The FIRST crossing attempt returned `disposition: null` on the Hub. Root cause (confirmed, not a
4.7 code defect): `ZtieHubTrackingStack` had NOT been redeployed after 4.7 added the new
`disposition` RD-013 envelope kind, so the live `hub_ingest` validator did not recognize the kind
and the crossed outcome was fail-closed **quarantined** — the exact 4.6 `handoff` deploy-gap class,
flagged pre-run. Remediation: redeployed `ZtieHubTrackingStack`; the live ingest asset then showed
`grep -c '"disposition"' handler.py = 9` + the bundled `disposition.contract.v1.json` present. A
second contributing factor on an interim attempt was a hand-seeded anchor record lacking a `sha256`
attribute, which the integrity-bound apply (`attribute_exists(intake_id) AND sha256 = :sha`)
correctly conditional-failed — the zero-trust gate working as designed. After redeploy + a properly
sha-anchored intake, the crossing landed cleanly (§3). This is the split-brain + raw-evidence
discipline working: the sealed verdict's "disposition recorded" claim was re-proven against the
actual ledger rather than accepted on testimony.

## RD-054 marker checklist (CHECK K)

- **positive-exercise:** §2 `destroyed: True` + `artifact_versions_deleted: 4`; §1 live HOLD.
- **proof-of-absence:** §2 all four prefixes `versions: 0, markers: 0`; §1 prefixes unchanged on
  refusal; §3 `OK: no effective-verdict key`; §4 role has NO `dynamodb`.
- **human attestation:** attested by **Warren Rutledge** (stakeholder), 2026-09-24 — ran every
  live block and read the raw output; independent validator Gemini sealed PASS (RD-055).
- **provenance:** intake `0c74042e-6976-4fdf-a39c-7599f9733921` (destroy) + intake
  `08dd5caa-b2a6-425a-be3a-03509df860ed` (hold) + commit
  `3e73f4b593e666d3a2fcc31249f398769a97a70d`.
