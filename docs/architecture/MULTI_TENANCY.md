# ZTIE Multi-Tenancy Architecture

> **Design spike output (Story T.1).** This document captures the multi-tenancy
> decisions that were **already settled** in [`RD-028`](../../PROJECT_PLAN.md) on
> 2026-09-07. It writes them up with rationale, rejected alternatives, the
> subscriber-identifier model, Hub data partitioning, the Phase-4 dashboard view, and
> the migration path from today's single shared Forensic account. It **does not
> re-open or re-litigate RD-028** — a genuine new sub-decision would need its own new
> registered decision. Ratification of RD-028 is the accountable party's call (RD-014);
> the executor drafts + proposes, the stakeholder ratifies.
>
> **Nature:** doc-only design spike. No production code, no Lambda, no CDK, no schema,
> no test, no live AWS. Validated by **stakeholder review**, not a live green-run.
>
> **Companion docs:** [`../ARCHITECTURE.md`](../ARCHITECTURE.md) for the single-tenant
> system flow; [`../COMPLIANCE.md`](../COMPLIANCE.md) for the ratified control mappings
> (the RD-028 / Story T.1 row).

---

## 1. Summary — two boundaries, decided deliberately

ZTIE's target commercial shape is a **subscription service**: many paying
**subscribers** (e.g. Acme, Globex), each with one or more **users** (e.g. Alice & Bob
at Acme). Offering ZTIE this way creates **two distinct isolation questions**, and
RD-028 answers each with a different, deliberate boundary:

| Boundary | Between whom | Isolation posture | Mechanism |
|----------|--------------|-------------------|-----------|
| **Tenant boundary** | Between subscribers (Acme vs. Globex) | **HARD isolation** — one subscriber's detonation must be incapable of affecting or observing another's | A **per-subscriber Forensic AWS account**, vended via **AWS Organizations** |
| **Intra-tenant boundary** | Between users inside one subscriber (Alice & Bob at Acme) | **SHARED-TRUST** — colleagues share the subscriber's environment and both see the subscriber's dashboard/results (a feature, not a leak) | None by design — isolation granularity is **per-subscriber, not per-user** |

Two separate jobs, both covered, by two different mechanisms:

- The **account barrier** does **tenant-level** blast-radius + data separation between
  paying customers.
- The **ephemeral host** (throwaway EC2 + wiped EBS volume, destroyed after every run)
  does **residue containment** — this is true regardless of *who* triggered the run, so
  it already protects users, runs, and subscribers from execution residue.

The Hub (Pipeline-Hub, `641628980935`) remains the **single shared control plane**
across all subscribers; only the Forensic blast zone is vended per subscriber.

---

## 2. Between subscribers = HARD isolation via a per-subscriber Forensic account

### 2.1 The chosen boundary

For ZTIE offered as a subscription service, **each subscriber gets its own disposable
Forensic AWS account**, vended via **AWS Organizations**. This is the strongest
available isolation boundary and is a natural fit for ZTIE's existing three-account
topology (Hub / Forensic / Pipeline-Sandbox):

- The **Hub stays the shared control plane** — it tracks all subscribers, holds the
  durable records, runs the dashboard, and hosts the human accept/reject gate. It is
  deliberately kept out of every blast zone (RD-008, RD-012).
- Each **subscriber gets its own Forensic blast-zone account** — the isolated VPC, the
  static scanners, and the ephemeral EC2 detonation host all live in *that subscriber's*
  Forensic account. A subscriber's untrusted artifact only ever executes inside its own
  account.
- The **Pipeline-Sandbox** handoff landing zone (RD-008) follows the same tenancy model
  as the pipeline commercializes; the ZTIE→PDE handoff remains one-directional and
  least-privilege per subscriber. (Detailed Sandbox tenancy is a T.2/T.3-era decision;
  T.1 fixes only that the hard tenant boundary is the account, and the Hub stays shared.)

The AWS account boundary is the containment wall between one subscriber's untrusted
artifact and every other subscriber: a breach, resource-exhaustion, or hostile
detonation in Acme's Forensic account cannot reach Globex's Forensic account, because
they are separate AWS accounts with no trust relationship between them.

### 2.2 Alternatives considered and rejected as primary

| Alternative | What it is | Why rejected as the primary tenant boundary |
|-------------|-----------|---------------------------------------------|
| **Per-tenant VPC in a shared account** | All subscribers share one AWS account; each gets its own VPC | Shared-account blast radius: a compromise or misconfiguration escaping a VPC (or abusing account-level IAM, service quotas, or the account root) reaches every tenant. IAM, service limits, and the account trust boundary are shared — too weak a wall for mutually-untrusting paying customers detonating unknown code. |
| **Per-tenant full-stack cell** | Every subscriber gets a complete, independent ZTIE deployment (its own Hub + Forensic + Sandbox) | Over-built: it needlessly duplicates the **control plane** (Hub, dashboard, tracking store, human gate), which does not need per-tenant isolation and is more valuable **shared** (one operational surface, one place to manage subscribers, one audit trail). The thing that must be hard-isolated is the **blast zone**, not the brains. A per-tenant Hub multiplies operational + cost overhead for no isolation gain. |

The per-subscriber **Forensic** account is the sweet spot: it hard-isolates exactly the
component that runs untrusted code (the blast zone), while keeping the control plane
shared (where sharing is a feature, and where RD-012/RD-013 already keep raw untrusted
data out).

### 2.3 Why the account is the boundary — not the VPC endpoints

Residue / cross-contamination between runs is **not** handled by the account boundary or
by network endpoints — it is handled by the **ephemeral host** (see §4). A per-run
interface endpoint (RD-027) is a *single-tenant idle-cost* optimization and would not
isolate users or tenants anyway, because the tenant boundary is the **environment**
(the account), not any per-run network component. Naming this explicitly keeps the
design from being over-built: we do not need per-tenant endpoints or per-run network
partitioning to achieve tenant isolation — the account does that.

---

## 3. Within a subscriber = SHARED-TRUST (per-subscriber, not per-user)

### 3.1 The decision

**Users inside one subscriber are shared-trust.** Alice and Bob at Acme share Acme's
ZTIE environment, and **both** see Acme's dashboard, intake records, verdicts, and
reports. This is **intended** — an org-shared view is a feature, not a leak.

Isolation granularity is therefore **per-subscriber, NOT per-user**:

- **No** per-user AWS accounts.
- **No** per-user data partitioning in the Hub.
- **No** per-user IAM scoping of the dashboard or records.

A subscriber's users collaborate over one shared view of that subscriber's data. The
only partition that exists in the data model is **the subscriber**.

### 3.2 Why within-org shared-trust is safe

The concern people intuitively raise about sharing an environment — *"could one user's
detonation contaminate another user's results?"* — is handled the **same way regardless
of who triggered the run**: every detonation runs on its **own throwaway EC2 host + a
wiped EBS volume**, destroyed after the run (RD-007 TTL teardown; RD-026 host-native
execution). No execution residue crosses between runs, and therefore none crosses
between users of the same subscriber. Sharing the *view* of results does not share any
*execution state*. So intra-tenant sharing carries no residue risk, and the collaborative
dashboard is pure upside.

### 3.3 Future opt-in (explicitly out of scope now)

If a future enterprise customer needs **team-vs-team isolation inside their own org**
(e.g. Acme's security team must not see Acme's contractor team's results), that is an
**opt-in add-on** decided at that time — it is **explicitly NOT built now** and must not
be pre-engineered. Building per-user partitioning today would add cost and complexity for
a requirement no one has. If it is ever needed, it is a new registered decision on the
tenancy track, not a silent expansion of RD-028.

---

## 4. Residue containment = the ephemeral host + wiped volume (not accounts/endpoints)

This is called out explicitly so the tenancy design is **not over-built**:

- **Tenant-level blast-radius + data separation between paying customers** = the
  **per-subscriber account** (§2).
- **Execution-residue containment between runs (and thus between users of one
  subscriber)** = the **ephemeral EC2 host + wiped EBS volume**, destroyed after each
  detonation (RD-007 hard-TTL `shutdown`; RD-026 host-native SSM execution, no Docker).

These are **two different jobs done by two different mechanisms**. Neither the account
boundary nor a VPC endpoint does residue containment; the ephemeral host does. Conversely,
the ephemeral host does not do tenant separation between paying customers; the account
does. Keeping this distinction clear prevents both under-building (assuming the host
isolates tenants) and over-building (adding per-tenant/per-user endpoints or partitions to
achieve residue containment that the host already provides).

---

## 5. The subscriber-identifier model

A **subscriber** is the unit of tenancy. To make the model concrete:

- **`subscriber_id`** is the stable, opaque identifier for a subscriber (e.g. a UUID or a
  short slug minted at subscriber onboarding). It is the single partition key of the
  tenant model. Users do **not** get their own identifier in the isolation model — a
  user is only ever *"a user acting on behalf of `subscriber_id`."*
- **End-to-end propagation.** `subscriber_id` is established at the point a subscriber's
  environment is vended (T.2) and travels with every artifact and every derived record:
  it is stamped on the intake at submission time, carried through the Forensic pipeline
  as pipeline metadata (never as executable content, per RD-013), and written onto the
  **durable Hub tracking record** as a first-class field.
- **Binding, not self-assertion.** As with the existing integrity model (RD-016
  `intake_id`+`sha256`), the `subscriber_id` on a crossed record is bound at the trusted
  boundary — the crossing is scoped by the vended-account identity that produced it, so a
  record cannot claim to belong to a subscriber other than the one whose Forensic account
  emitted it. (The concrete enforcement mechanism is a T.3 implementation detail; T.1
  fixes only that `subscriber_id` is the partition key and is boundary-bound, not
  self-asserted.)

> **Note (design intent, not a new decision).** The exact `subscriber_id` scheme (UUID
> vs. slug vs. AWS Organizations account-id-derived) and the precise binding mechanism
> are **implementation choices for T.2/T.3**, called out here as design intent so the
> Phase-4 Hub is built expecting a subscriber partition key. They do not change RD-028.

---

## 6. How the Hub partitions many subscribers' data (shared control plane)

The Hub is **shared** across all subscribers by design (§2.1), so subscriber data must be
**partitioned within the Hub**. The model:

- **The durable Hub tracking record is keyed/attributed by `subscriber_id`.** Every
  intake record, classification, per-lane summary, correlation, score, remediation, and
  advisory verdict already lives on the Hub tracking item (RD-012). Under multi-tenancy,
  each such item carries its `subscriber_id`, and every read is **scoped by
  `subscriber_id`** — a query for one subscriber's data can never return another
  subscriber's rows.
- **Dashboard queries are subscriber-scoped.** Every dashboard/status read is filtered to
  the requesting subscriber's `subscriber_id`; there is no query path that returns
  cross-subscriber data.
- **The RD-013 data-contract boundary is unchanged.** Only derived, bounded, verdict-free
  data crosses Forensic→Hub (no raw payload / no executable content); adding
  `subscriber_id` to that contract is a metadata field, not a relaxation of the
  allow-list. Each subscriber's Forensic account writes through the same fail-closed,
  integrity-keyed Hub-owned gate.
- **Noisy-neighbor / quota controls** (per-subscriber concurrency caps, per-subscriber
  queues/quotas so one subscriber's detonation volume cannot starve another) are named
  here as a **Hub-side requirement** but are **implemented in T.3**, not T.1.

> The Hub partitioning **implementation** (index design, query enforcement, per-subscriber
> quotas) is **T.3**. T.1 fixes the architectural requirement: the Hub is shared, and it
> partitions per subscriber (never per user).

---

## 7. The Phase-4 dashboard is a per-subscriber, org-shared view

The reason T.1 is scheduled **before Phase 4**: Phase 4 builds the Hub dashboard + the
handoff/reporting plane, and it must be built **tenant-aware from the start** or it will
be a costly retrofit.

- **Per-subscriber:** a dashboard session is scoped to exactly one subscriber's data. A
  user at Acme sees Acme's intakes, verdicts, and reports — **never** Globex's. This is
  enforced by the §6 `subscriber_id`-scoped queries.
- **Org-shared:** **all** users at a subscriber see **the same** dashboard for that
  subscriber (§3). There is no per-user view, no per-user filtering, and no per-user
  partition. Alice and Bob at Acme see identical Acme data.
- **The human accept/reject gate is per-subscriber, shared within the org.** The
  dashboard's human-in-the-loop accept/reject control (which gates whether an analyzed
  artifact may pass downstream to the PDE) operates on the subscriber's data and is
  usable by that subscriber's users — the advisory `recommended_verdict` (RD-040) stays
  advisory, and a human at the subscriber actively selects PASS/FAIL. The verdict remains
  human-gated; multi-tenancy does not change that, it only scopes *whose* data the human
  is acting on.

**Consequence for Phase 4 design:** the dashboard's data-access layer must take
`subscriber_id` as a first-class scope on every query from day one, and the read-model
(Story 4.1 status-retrieval) must carry `subscriber_id` through. Designing this now avoids
a single-tenant dashboard that later has to be re-plumbed for tenancy.

---

## 8. Migration path — from one shared Forensic account to per-subscriber accounts

Today ZTIE runs **single-tenant**: one shared Forensic account (`360999005254`), one Hub
(`641628980935`), one Pipeline-Sandbox (`586917955591`). The multi-tenant target must be
reachable **without a rebuild**. The migration maps forward as follows:

1. **The Hub does not move.** The Hub is already the shared control plane. Making it
   tenant-aware is an **additive** change: add a `subscriber_id` field to the tracking
   record + scope reads by it (§6). Existing single-tenant records are treated as a single
   implicit "tenant zero" — they are backfilled with a reserved `subscriber_id` (e.g. the
   founding/internal subscriber) so no record is orphaned and no schema break occurs.
2. **Today's shared Forensic account becomes "tenant zero's" Forensic account.** The
   current Forensic account (`360999005254`) is not decommissioned — it is re-cast as the
   Forensic account of the first (internal/founding) subscriber. Its stacks
   (`ZtieForensicInfraStack`, detonation, static-scan) are already the exact per-subscriber
   blast-zone baseline that T.2 will vend into *new* subscriber accounts.
3. **New subscribers are vended, not migrated.** Onboarding a new subscriber (T.2) means
   AWS-Organizations-vending a **fresh** Forensic account and deploying the same
   blast-zone baseline (stack-set) into it, tagged with that subscriber's `subscriber_id`.
   No existing data moves; each new subscriber starts clean.
4. **The Forensic stacks are already the template.** Because the current Forensic
   deployment is a parameterized CDK stack set, the per-subscriber vend is "deploy this
   same stack set into a newly-vended account with `subscriber_id` as a parameter/tag" —
   not a redesign. This is precisely why the account (not a VPC) is the boundary: the unit
   we already deploy (a Forensic account's stacks) is the unit we vend.
5. **The RD-013 contract stays constant.** The Forensic→Hub crossing contract is unchanged
   except for the additive `subscriber_id` metadata field; the same fail-closed,
   integrity-keyed Hub gate serves every subscriber's account. No boundary re-architecture.

Net: the current single-tenant deployment is a **special case** (tenant zero) of the
multi-tenant model, not a throwaway. Multi-tenancy is reached by **adding** a subscriber
partition to the (unchanged) shared Hub and **vending more copies** of the (unchanged)
Forensic blast-zone baseline — never by rebuilding what exists.

---

## 9. Forward scope — T.2 and T.3 (out of scope for T.1)

T.1 is architecture only. The build work it enables is deferred to the commercialization
phase (after the core single-tenant pipeline is complete — RD-028), and is scoped **from
this document**:

- **T.2 — Per-subscriber environment provisioning / deprovisioning.** Automate stand-up +
  teardown of an isolated per-**subscriber** ZTIE environment per §2/§8: AWS-Organizations
  account-vending + a baseline stack-set deploy of the Forensic blast zone, subscriber-
  tagged + cost-attributable, with nuke-on-offboard (mirroring ZTIE's nuke-on-reject
  discipline). Granularity is per-subscriber (not per-user, §3). **Depends on T.1.**
  *(Out of T.1 scope: any provisioning/deprovisioning code.)*
- **T.3 — Hub-side per-subscriber data isolation + noisy-neighbor / quota controls.**
  Implement the §6 partitioning: per-subscriber scoping of the Hub tracking/reporting/
  dashboard plane (a subscriber cannot read another's records/verdicts/reports/dashboard)
  + per-subscriber limits (concurrency caps, per-subscriber queues/quotas) so one
  subscriber's detonation volume cannot starve another, consistent with the RD-013
  boundary. Partitioning is per-subscriber only; within a subscriber the dashboard is
  org-shared (§3, §7). **Depends on T.2.**
  *(Out of T.1 scope: the Hub-side partitioning implementation.)*

---

## 10. Compliance mapping (RD-014) — cite, do not duplicate

The candidate control mappings for this architecture are **already ratified** in
[`../COMPLIANCE.md`](../COMPLIANCE.md) under the **`RD-028 / Story T.1`** row (ratified by
the accountable party `warrenrutledge64`, 2026-09-12). This document does **not** add a
duplicate row — it reconciles with and cites the existing ratified mapping:

| Framework | Control | Why it applies |
|-----------|---------|----------------|
| NIST 800-53 r5 | `SC-7` (Boundary Protection) | Per-subscriber account is the hard tenant boundary |
| NIST 800-53 r5 | `SC-2` (Separation of System & User Functionality) | Between-subscriber separation |
| NIST 800-53 r5 | `SC-4` (Information in Shared Resources) | No cross-subscriber residue (ephemeral host) |
| NIST 800-53 r5 | `SC-32` (System Partitioning) | Per-subscriber Forensic account partition |
| NIST 800-53 r5 | `AC-4` (Information Flow Enforcement) | Hub partitions per-subscriber data |
| NIST 800-53 r5 | `AC-3` (Access Enforcement) | Within-subscriber shared dashboard access |
| NIST CSF | `PR.AC-5` (network integrity / segregation) | Account-level segregation between subscribers |
| NIST CSF | `PR.AC-4` (access permissions) | Per-subscriber (not per-user) access model |
| ISO 27001:2022 | `A.8.22` (Segregation of networks) | Per-subscriber account boundary |
| ISO 27001:2022 | `A.5.23` (cloud services security) | AWS-Organizations-vended per-subscriber environments |
| ISO 27001:2022 | `A.8.3` (information access restriction) | Subscriber-scoped Hub data access |

Per RD-014, ZTIE claims control coverage only for **ratified** mappings. These are ratified
in `COMPLIANCE.md`; this section restates them for locality and must stay consistent with
that authoritative matrix (no duplicate row is added there).

---

## 11. Decision status

- **RD-028** is proposed for **ratification** as part of Story T.1 (Proposed → Ratified),
  pending accountable-party sign-off (RD-014). This document is the write-up that RD-028's
  ratification refers to.
- **This document does not create a new decision.** It documents the settled RD-028
  decisions. Any genuine new sub-decision surfaced later requires its own new registered
  decision (the next free number after RD-040), with its PROJECT_PLAN decisions-table row
  added before the number is referenced in any living doc.
