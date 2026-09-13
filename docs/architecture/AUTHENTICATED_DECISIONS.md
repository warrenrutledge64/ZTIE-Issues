# ZTIE Authenticated Hub→Spoke Decisions

> **Design spike output (Story H.1).** This document specifies the mechanism by which
> the **Hub hands out authenticated decisions** that a **spoke verifies** — the concrete
> realization of the boundary set in [`RD-048`](../../PROJECT_PLAN.md) (the Hub is
> strictly the control plane; no spoke ever reads into it) and the crypto/format choices
> registered in [`RD-049`](../../PROJECT_PLAN.md). It is the shared primitive that
> Stories **4.6** (ACCEPT→push), **4.7** (REJECT→destroy), and **4.4** (the human UI +
> auto-delivery) all consume.
>
> **Nature:** doc-only design spike. No production code, no Lambda, no CDK, no schema
> file, no test, no live AWS. Validated by **stakeholder review**, not a live green-run.
> The BUILD + live validation of the sign/verify crossing is a **follow-on build story**
> (see §9). This document does not re-open RD-048/RD-049 — a genuine new sub-decision
> would need its own registered decision.
>
> **Companion docs:** [`../ARCHITECTURE.md`](../ARCHITECTURE.md) (system flow),
> [`MULTI_TENANCY.md`](MULTI_TENANCY.md) (the sibling design spike, Story T.1),
> [`../COMPLIANCE.md`](../COMPLIANCE.md) (control mappings), and
> [`../../RESTORE.md`](../../RESTORE.md).

---

## 1. Problem — why this exists

The Story 4.6 ACCEPT-push originally read the human decision **into** the Hub
(`dynamodb:GetItem` on the Hub tracking table, from the Forensic pusher). During 4.6's
live validation that read failed, and — more importantly — the stakeholder ruled that
**the Hub must be strictly the control plane: no spoke may read into it** (RD-048).

But the enforcement actions still need to *act on* a Hub-side human decision:

- **4.6** must push an artifact to the PDE **only** on a human **ACCEPT**.
- **4.7** must destroy an artifact **only** on a human **REJECT**.
- **4.4** is the human UI that records the decision and (later) triggers the action.

So we need a way for a spoke to **know a decision is genuinely a Hub-issued human
decision** — without reading the Hub, and without trusting whoever invoked the spoke
Lambda (a bare `{"decision": "accepted"}` in an invoke payload is forgeable and is
explicitly forbidden by RD-048). The answer is a **signed decision token**: the Hub
**signs**, the spoke **verifies**.

## 2. The boundary this must honor (RD-048, restated)

- Data flows **OUT of the Hub** (a signed token, handed to the spoke) — never a read
  **into** the Hub.
- The spoke needs **no Hub credentials, no Hub grant, and makes no call to the Hub**
  (not even to Hub-side KMS) to verify a decision.
- All spoke→Hub flow stays the existing one-directional, allow-listed, fail-closed
  RD-013 write-out (the bounded outcome the spoke reports after acting).

## 3. Mechanism — KMS asymmetric sign (Hub) + offline verify (spoke)

```
   HUB (control plane, 641628980935)                 SPOKE (e.g. Forensic 360999005254)
   ─────────────────────────────────                 ───────────────────────────────────
   human decision (4.4 / manual)
        │
        ▼
   build canonical decision.token.v1
   { intake_id, decision, sha256, issued_at, key_id }
        │
        ▼
   kms:Sign  (Hub-owned ASYMMETRIC key;                 embedded PUBLIC key (shipped at
   Hub is the ONLY principal with Sign)                 deploy time; NOT a secret)
        │                                                     │
        ├──── hand out: {token, signature} ───────────▶ verify signature OFFLINE
        │     (invoke payload now; Hub→Forensic               (no call to Hub / Hub-KMS)
        │      event later, Story 4.4)                        │
        │                                                     ▼
        │                                               VERIFY-THEN-ACT (fail-closed):
        │                                                 sig valid? decision expected?
        │                                                 token.sha256 == artifact sha256?
        │                                                 fresh (issued_at window)? key_id trusted?
        │                                                     │  all yes
        │                                                     ▼
        │                                               act (4.6 push / 4.7 destroy)
        │                                                     │
        ◀──── RD-013 one-directional write-out ──────────────┘
              (bounded, verdict-free outcome)
```

### 3.1 The signing key
- A **KMS asymmetric key** in the **Hub** account, key usage **SIGN_VERIFY**, spec
  **`ECC_NIST_P256`** with signing algorithm **`ECDSA_SHA_256`** (small signatures,
  widely supported; RSA is an acceptable alternative if a consumer needs it — decided at
  build time, not re-litigated here).
- **Only the Hub** (specifically the human-gate principal — Story 4.4's signer, or the
  stakeholder's manual sign for validation) holds **`kms:Sign`**. No spoke, and no other
  Hub component, can sign.
- The key's **public half** is exported once and **embedded into each spoke's config at
  deploy time** (a CDK context value / env var on the pusher + destroyer Lambdas). The
  public key is **not a secret**; shipping it to the spoke creates no exposure.
- `key_id` (the KMS key id / a short key fingerprint) travels in the token so the spoke
  can confirm it verified against the **trusted** key and to support key rotation (§7).

### 3.2 Why OFFLINE verify (not cross-account `kms:Verify`)
Verifying offline against the embedded public key means the spoke calls **nothing** to
check a decision — the purest form of RD-048 (the Hub is unreachable from the spoke). A
cross-account `kms:Verify` would work and still keep Hub *data* private, but it is a call
**to a Hub-owned KMS key** (needs a grant on the Hub key) — a crack in "the spoke never
touches the Hub." So offline verify is the chosen path; `kms:Verify` is explicitly
rejected as the primary mechanism.

## 4. The decision token — `decision.token.v1`

A small, **canonical, deterministic, bounded allow-list** object (the exact schema is
authored in the build story; this is its shape). No free-form fields — it is an
allow-listed contract like every other ZTIE crossing.

| Field | Type / bound | Meaning |
|-------|--------------|---------|
| `contract_version` | string enum `"1.0"` | Token schema version (own pin). |
| `intake_id` | UUIDv4 pattern | Which intake this decision is about. |
| `decision` | string enum `accepted` \| `rejected` | The human decision. (INCONCLUSIVE is a HOLD — **no token is issued**; absence of a valid `accepted`/`rejected` token = no action.) |
| `sha256` | 64-hex | The artifact's sha256 — **binds the decision to exact bytes**. |
| `issued_at` | RFC3339 UTC `Z`, `maxLength` bounded | When the Hub signed it (freshness/replay bound). |
| `key_id` | string, bounded | The signing key id/fingerprint the spoke must have trusted. |

- **Canonicalization:** the bytes that are signed are a **deterministic serialization**
  of the token (e.g. JSON with sorted keys + no insignificant whitespace, or a fixed
  field order) so the Hub and the spoke hash the exact same bytes. The build story pins
  the exact canonical form + a round-trip test.
- **Wire form:** `{ "token": <the canonical token>, "signature": <base64 detached sig> }`
  — compact enough for an invoke payload and a future Hub→Forensic event.
- **Verdict-free:** the token carries a *human decision*, never a machine "verdict"; the
  advisory `recommended_verdict` (RD-040) is NOT a decision and never produces a token.

## 5. Verify-then-act (the fail-closed gate the spoke runs)

The spoke acts **only if ALL** hold; any failure ⇒ **refuse, do nothing**:

1. **Signature valid** — `signature` verifies against the **trusted embedded public key**
   over the canonical token bytes.
2. **Expected decision** — `decision` is exactly the value this action requires
   (`accepted` for 4.6's push; `rejected` for 4.7's destroy). A token for the wrong
   decision does not authorize this action.
3. **Artifact binding** — `token.sha256` equals the spoke's **recomputed** sha256 of the
   artifact it is about. (This subsumes 4.6's existing SI-7 hash-verify: the same hash
   check now also proves the decision is about *these* bytes — a token for artifact A
   cannot authorize moving artifact B.)
4. **Freshness** — `issued_at` is within a bounded window (a configurable max age) — a
   replay bound so a captured token is not valid indefinitely.
5. **Key trust** — `key_id` matches the key the spoke was configured to trust.

Only after all five does the spoke perform its action (push / destroy) and then report
the bounded, verdict-free outcome back to the Hub over the existing RD-013 write-out.

> **This strengthens the prior fail-closed gate.** In the superseded RD-047 design the
> gate was "read `human_decision == accepted` + hash-verify". Now it is "verify a
> Hub-signed token whose decision is `accepted` AND whose `sha256` matches" — same
> fail-closed spirit, but the trust no longer depends on a cross-account read, and the
> decision is cryptographically bound to the artifact.

## 6. How each consumer uses it

| Story | Signs (Hub) | Verifies (spoke) | Acts on |
|-------|-------------|------------------|---------|
| **4.6** ACCEPT→push | Hub signs `decision=accepted` for the intake | Forensic pusher verifies offline | push artifact Forensic→Sandbox |
| **4.7** REJECT→destroy | Hub signs `decision=rejected` for the intake | Forensic destroyer verifies offline | destroy artifact + chamber in Forensic |
| **4.4** human UI + trigger | Hub-side signer produces the token on the human's click; delivers it Hub→Forensic (one-directional) | (delegates to 4.6/4.7 verify) | records the human decision + triggers the action |

INCONCLUSIVE (the hold) issues **no token** — so the spokes simply never receive an
authorization, which is the correct fail-closed "do nothing / hold" behavior.

## 7. Key management + rotation (noted; detailed at build time)
- The public key is embedded per spoke at deploy; `key_id` in the token lets a spoke
  trust a **set** of keys during a rotation window (accept old + new), then drop the old.
- Rotation is a Hub-side key action + a spoke redeploy with the new public key; because
  verification is offline, rotation never requires a spoke→Hub call.
- The signing key is `RETAIN` on stack removal (losing it invalidates the ability to
  issue decisions); its key policy grants `kms:Sign` to exactly the Hub signer principal.

## 8. What this deliberately does NOT do (scope guardrails)
- It does **not** re-introduce any spoke→Hub read (RD-048).
- It does **not** use a shared secret / HMAC (that would put signing material in the
  spoke, letting a compromised spoke mint decisions). Asymmetric only.
- It does **not** encrypt the artifact or change the RD-013 outcome crossing — it only
  authenticates the **decision**.
- It does **not** build 4.4's UI or auto-delivery — only the token + sign + verify
  primitive that 4.4 will drive.
- It is **not** the advisory verdict (RD-040) — the token is a *human* decision.

## 9. Follow-on build story (out of scope here; this is the design)
A build story implements + live-validates the crossing (its own RD is unnecessary — it
implements RD-048/RD-049; like other build stories it registers no new RD unless a real
new decision arises):
1. Author `decision.token.v1` schema (allow-list, own version pin) + its generator +
   conformance test (offline walk + jsonschema-skipUnless), mirroring the existing
   contract discipline.
2. A shared PURE verify library (canonicalize → verify signature → the five checks),
   fully offline-unit-testable (test vectors: valid, bad-sig, wrong-decision,
   sha-mismatch, stale, wrong-key).
3. Hub: the KMS asymmetric signing key + key policy (Hub signer only `kms:Sign`) + a
   `PublicKey` output; a small Hub-side signer (for 4.4 later; a documented manual
   `aws kms sign` recipe for validation now).
4. Spoke: embed the public key at deploy; wire the verify library into the pusher.
5. **Live validation of the crossing:** Hub signs a token for a real intake; the spoke
   verifies it offline and acts; prove every fail-closed branch (bad sig / wrong
   decision / sha-mismatch / stale / wrong key ⇒ refuse). No spoke→Hub read anywhere.

## 10. Rework impact on Story 4.6 (after this + the build story)
4.6's `pde_handoff` changes from "read `human_decision` from the Hub (cross-account) +
hash-verify" to "**verify a Hub-signed `accepted` token offline** (which includes the
sha256 binding) → push". The Sandbox landing stack + the one-directional least-privilege
push + the verdict-free outcome crossing are **unchanged**. The pusher's cross-account
`dynamodb:GetItem` grant is **removed** (no Hub read). 4.6 then gets its single live pass
on the reworked code, and stays 🟡 until then.
