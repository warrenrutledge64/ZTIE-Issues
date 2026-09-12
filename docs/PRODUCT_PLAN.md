# ZTIE Product Charter — Zero Trust Inspection Engine

> **The why and the for-whom — the charter-level view.** This is the highest-level
> ZTIE document: it states the product vision, the outcomes we are accountable for,
> the scope boundary, the stakeholders, the strategy, and the risks — in the language
> of a **project charter (PMP)** and a **product owner (Scrum)**. It is deliberately
> **charter-level**: it carries **no story IDs, no per-story detail, and no status**.
> Those live one layer down.
>
> **Where this sits in the document set (three intentional views of the same product):**
>
> | View | Document | Answers | Organized by |
> |------|----------|---------|--------------|
> | **Product / charter** | **`PRODUCT_PLAN.md`** (this doc) | *Why does ZTIE exist, for whom, what outcome, within what boundary?* | Value & strategy |
> | **Engineering / plan** | [`PROJECT_PLAN.md`](../PROJECT_PLAN.md) | *What are the phases, the design, the decisions, the acceptance criteria?* | Phase |
> | **Execution / ledger** | [`RUNBOOK.md`](../RUNBOOK.md) | *What is the status of each story, in what build order, validated how?* | Build order (dependency tiers) |
>
> The three always agree on the facts and deliberately differ in organization. **Story
> status has exactly one home — `RUNBOOK.md`.** This charter never restates a story's
> status; where you want "how far along are we," follow the link to the runbook. Not
> duplicating status is how these documents stay honest (RD-015).

---

## 1. Product Vision

**For** platform, security, and delivery teams **who** must let code and
infrastructure artifacts flow to production quickly **but** cannot afford to trust any
artifact by default, **ZTIE (the Zero Trust Inspection Engine)** is a security
inspection point **that** classifies, statically scans, and safely detonates every
artifact — then correlates the evidence with AI and gates promotion on a human
decision — **so that** only artifacts proven safe are ever handed downstream to the
**Platform Delivery Engine (PDE)**, and anything dangerous is contained and destroyed
before it can reach a production account.

**Vision statement.** *Every artifact earns its way to production. Nothing is trusted
because of where it came from; everything is cleared by what inspection proves about
it — and the dangerous artifact never leaves the blast zone.*

---

## 2. Problem & Opportunity

- **The problem.** Deployment pipelines routinely promote artifacts on implicit trust
  (it came from our build system, so it must be fine). Static scanning alone misses
  runtime behavior; running an unknown artifact to observe that behavior is exactly
  what you must never do near production. The result is a false choice between *fast*
  and *safe*.
- **The opportunity.** Resolve the false choice by making inspection a **first-class,
  zero-trust gate** that does BOTH — static analysis AND real dynamic detonation — in
  a hard-contained blast zone, then uses AI to reconcile the two into a single, honest
  verdict a human signs off on. Speed is preserved (inspection is parallel and
  automated); safety is structural (the unknown only ever executes inside an isolated,
  disposable account and cannot leave it without a human's approval).

---

## 3. Product Goal & Objectives

**Product goal.** Establish ZTIE as the mandatory, zero-trust inspection point that
every artifact passes through before the PDE — with no bypass path.

**Objectives (outcomes we hold ourselves to):**

1. **Inspect everything, trust nothing.** Every artifact is classified and inspected;
   there is no "skip inspection" route.
2. **See what static analysis cannot.** Capture real runtime behavior by detonating
   the artifact host-native on an ephemeral, isolated host — not a simulation.
3. **Correlate, don't guess.** Reconcile static findings against dynamic behavior with
   AI (Amazon Nova Pro) to cut false positives and produce one reasoned threat picture.
4. **Contain the blast radius absolutely.** The raw untrusted artifact lives, executes,
   and (on rejection) dies inside one disposable account, and cannot reach any
   production-bound account except by a human-approved, hash-verified handoff.
5. **Decide with a human in the loop.** Promotion is gated on an explicit human
   accept/reject of ZTIE's findings — the machine advises, a person decides.
6. **Make the evidence legible.** Deliver the verdict and its evidence in audience-tiered
   form (executive, security, developer) so each stakeholder can act on it.

---

## 4. Success Criteria & Outcome Measures

Charter-level outcomes (the *definition of a working product*, not sprint metrics):

- **Zero-bypass.** No artifact reaches the PDE without a recorded ZTIE clearance and a
  human ACCEPT. (Target: 100% of promotions traceable to a cleared, accepted intake.)
- **Dual-lane coverage.** Every inspected artifact has BOTH a static result AND a real
  detonation behavior record (or an honestly-recorded reason one is absent) before a
  verdict is offered.
- **Containment integrity.** No un-accepted artifact ever leaves the Forensic blast
  zone; a rejected artifact and its detonation chamber are destroyed there. (Target:
  zero escapes; every rejection leaves no residue.)
- **False-positive reduction.** Cases where static flags a risk but dynamic proves it
  benign (or vice-versa) are correctly reconciled by the AI correlation — demonstrated,
  not assumed.
- **Decision latency + legibility.** A reviewer can reach an accept/reject decision from
  the dashboard with the evidence tiered to their role, and can see live operational
  status (what is detonating now, which ports were exercised) and restore-point health.
- **Auditability.** Every intake, verdict, and enforcement action is recorded durably in
  the control plane, mapped to candidate compliance controls (NIST 800-53, NIST CSF,
  ISO 27001) for audit.

> *Concrete per-phase acceptance is defined as live validation gates — see §8 and, for
> the authoritative gate wording, [`PROJECT_PLAN.md`](../PROJECT_PLAN.md) §3.*

---

## 5. Scope

**In scope (the product ZTIE delivers):**

- Intake + classification/routing of incoming artifacts (IaC templates, raw scripts,
  unknown types) with a safe path for what cannot be routed.
- Parallel **static** analysis (linters/policy-as-code/SAST + compliance mapping +
  signature scans) and **dynamic** detonation (ephemeral host-native execution with
  syscall/network/filesystem telemetry).
- **AI correlation** of the two evidence streams into a unified threat picture.
- A **human accept/reject enforcement gate**, the hash-verified handoff to
  Pipeline-Sandbox on ACCEPT, and destruction of the artifact + chamber on REJECT.
- **Reporting**: a real-time dashboard (control plane) and per-execution, audience-tiered
  reports.
- The **governance operating system** that keeps the work honest (validation gate,
  restore points, decision log, management-artifact integrity).

**Out of scope (explicit non-goals):**

- **The Platform Delivery Engine (PDE) itself.** ZTIE performs *security clearance only*.
  Once an accepted, hash-verified artifact lands in Pipeline-Sandbox it is under **PDE**
  control and ZTIE's responsibility ends. ZTIE never re-executes a cleared artifact
  downstream, and Sandbox isolation is a PDE responsibility.
- **ServiceNow integration** — strictly out of scope for the ZTIE workflow and dashboard.
- **Functional/user-acceptance testing** of a cleared artifact (a PDE activity).
- **Writing back into the Dev origin.** The Dev → ZTIE crossing is input-only; ZTIE holds
  no permissions into Dev and never pushes results into it (developers *read* ZTIE's
  outputs).
- **Multi-tenant commercialization** (per-subscriber provisioning, cross-tenant
  isolation) — a deliberately deferred, strategy-contingent direction, not part of the
  core single-tenant product.

---

## 6. Stakeholders & Personas

| Persona / stakeholder | Cares about | Primary ZTIE touchpoint |
|-----------------------|-------------|--------------------------|
| **Product owner / sponsor** | The product does what it promises; scope + risk are managed | This charter; the accept/reject outcomes |
| **Security reviewer (the gatekeeper)** | Is this artifact safe? MITRE-mapped behavior, findings, the evidence to accept/reject | The Hub dashboard + the security-tier report + the human gate |
| **Executive / risk owner** | One-glance risk posture and verdict | The executive tier of the report + dashboard summary |
| **Developer (artifact author)** | Why did my artifact fail and how do I fix it | The developer-tier report (exact failure, file/line, remediation); reads ZTIE outputs |
| **Platform / delivery (PDE) team** | Only clean artifacts arrive, hash-verified, at the handoff | The Pipeline-Sandbox landing (downstream of ZTIE) |
| **Operator / SRE** | What's deployed where, what's running now, restore-point health | The dashboard live-status + inventory views |
| **Auditor / compliance** | Traceable decisions mapped to controls | The durable Hub record + compliance mappings |

**RACI (charter-level — decision rights, not task assignment):**

| Activity | Product Owner / Sponsor | Security Reviewer | Executor (AI dev) | PDE Team |
|----------|:----:|:----:|:----:|:----:|
| Product vision, scope, priority | **A/R** | C | C | I |
| Sequence / "what's next" decisions | **A** (decides) | C | **R** (recommends) | I |
| Accept / reject an inspected artifact | I | **A/R** | I | I |
| Build & validate the pipeline | C | C | **R** (A on validation: the stakeholder) | I |
| Downstream deployment of a cleared artifact | I | I | I | **A/R** |

*(R = Responsible, A = Accountable, C = Consulted, I = Informed.)*

---

## 7. Product Strategy & Roadmap (outcome-framed, phase-level)

ZTIE is built **foundation-first**: the hardened containment and the safe-crossing
boundary are proven before feature work lands on them, and value is delivered along the
artifact's own journey through the pipeline. The roadmap is expressed as **capability
milestones**, each an outcome — **not** a story list. *(For the story breakdown, build
order, and current status, follow [`RUNBOOK.md`](../RUNBOOK.md); this charter never
restates status.)*

1. **Intake & Routing** — *"every artifact is safely received and sent down the right
   path."* An artifact can be submitted, is classified, and is routed to the correct
   inspection lane; anything unroutable is safely refused, never crashed.
2. **Parallel Inspection** — *"we see both what the artifact IS and what it DOES."*
   Static analysis and real host-native detonation run concurrently in the blast zone,
   each producing structured evidence, with the ephemeral host guaranteed to tear down.
3. **AI Correlation & Assessment** — *"the two evidence streams become one honest
   verdict."* Static and dynamic findings are reconciled by Nova Pro into a unified
   threat score with prioritized findings and false-positives eliminated.
4. **Handoff & Reporting** — *"a human decides, and the decision is enforced and
   explained."* The verdict is surfaced on the dashboard and in tiered reports; a human
   accept/reject gates the hash-verified handoff to the PDE, rejection destroys the
   artifact and its chamber, and inconclusive holds for review.

**Cross-cutting (spans all milestones):** the governance operating system — the
validation covenant, restore-point discipline, the decision log, and
management-artifact integrity — is not a phase; it protects every milestone.

**Beyond the core product (deferred, strategy-contingent):** offering ZTIE as a
multi-tenant subscription (per-subscriber isolation) is a recognized future direction,
explicitly deferred until the single-tenant product is proven and a commercialization
decision is made.

---

## 8. Milestone Acceptance (how "done" is proven)

ZTIE's guiding principle: **nothing is "done" on inference — it is proven by a live
validation and the result is recorded** (the validation covenant). At the product level:

- Each capability milestone has a **single, live end-of-phase acceptance gate** — a real
  run through real AWS services that demonstrates the milestone's outcome (e.g. a
  known-bad artifact produces real static findings AND a real detonation behavior record
  in parallel; the AI reconciles a static/dynamic disagreement; an accepted artifact is
  pushed hash-verified while an un-accepted one never leaves Forensic).
- A milestone is not accepted on a passing local build or a green deploy alone; it is
  accepted on the recorded live result.
- **The authoritative gate wording lives in [`PROJECT_PLAN.md`](../PROJECT_PLAN.md) §3**
  and the binding mechanism in [`RUNBOOK.md`](../RUNBOOK.md); this charter states the
  principle, not the per-phase checklist.

---

## 9. Assumptions

- ZTIE runs entirely on **AWS** across separate accounts; the account boundary is the
  security wall.
- The **PDE exists and owns downstream deployment**; ZTIE integrates with it only at the
  Pipeline-Sandbox handoff.
- **Amazon Nova Pro** is the correlation/assessment engine (via Bedrock).
- Artifacts arrive from a **Dev origin** on an input-only crossing; ZTIE never writes back.
- The **golden detonation images** (pre-baked AMIs with the required tooling) are provided
  to the Forensic account; ZTIE consumes them rather than building them.
- A **human reviewer is available** to exercise the accept/reject gate (ZTIE advises; it
  does not auto-approve).

---

## 10. Constraints (charter summary)

These are the product-shaping rules; the **authoritative, exhaustive list is
[`PROJECT_PLAN.md`](../PROJECT_PLAN.md) §2** and the registered decisions. Summarized here
so the charter is self-standing:

- **Zero trust, no bypass.** Every artifact is inspected; there is no skip path.
- **Real execution, no mocks.** Detonation uses **ephemeral** EC2 with host-native SSM
  execution — never Docker, never a simulation. *(These instances are **ephemeral** —
  never "temporary.")* Production-quality throughout; no placeholder services.
- **Hard containment.** The raw artifact only ever executes in the Forensic blast zone and
  has **no path out except the human-approved, hash-verified contract gate**.
- **Human-gated enforcement.** The PASS / FAIL / INCONCLUSIVE verdict drives promotion, but
  a human makes the accept/reject call.
- **AWS-native automation.** CI/CD and infra automation are AWS-native; GitHub is for
  development only.
- **Python-first** development; validation-gated status; restore-point discipline (build
  from a known-good point, revert rather than forward-patch).

---

## 11. Dependencies

- **Amazon Bedrock / Nova Pro** — the correlation engine (external managed service).
- **The PDE** — the downstream consumer; ZTIE's job ends when a cleared artifact lands in
  Pipeline-Sandbox.
- **Golden AMIs / Image Builder** — the pre-baked detonation host images (provided to
  Forensic; consumed, not built, by ZTIE).
- **AWS Organizations / multi-account setup** — the three-account topology (Hub, Forensic,
  Pipeline-Sandbox) plus the Dev input spoke.
- **Inter-milestone dependency** — inspection precedes correlation precedes handoff; the
  containment foundation precedes anything that detonates. *(The precise dependency graph
  lives in [`docs/BUILD_ORDER.md`](BUILD_ORDER.md) / [`RUNBOOK.md`](../RUNBOOK.md).)*

---

## 12. Risks (product-level)

| Risk | Impact | Mitigation (product stance) |
|------|--------|------------------------------|
| **Blast-zone escape** — the unknown artifact reaches a production-bound account | Catastrophic | Single disposable Forensic account; only exit is the human-approved, hash-verified gate; reject destroys artifact + chamber |
| **Ephemeral host not torn down** | Cost + lingering exposure | Hard TTL self-termination as the guaranteed backstop, beyond best-effort terminate |
| **AI over-trust** — treating a model output as a verdict | Wrong promotion | The AI produces EVIDENCE only; the verdict is human-gated; no verdict is ever imported from crossed data |
| **False confidence from one lane** | Missed threat / needless block | Dual-lane inspection + AI correlation; a verdict requires both perspectives reconciled |
| **Secret/PII leakage into the control plane** | Compliance breach | Only derived/sanitized data crosses to the Hub; telemetry is entropy-scrubbed before it leaves the blast zone |
| **Governance drift** — plans/docs diverge from reality | Slow, quiet erosion of trust in the plan | One status home (RUNBOOK), machine-checked management-artifact integrity, restore points |
| **Scope creep into PDE / multi-tenant** | Diluted focus, over-build | Explicit out-of-scope boundary (§5); multi-tenant deferred to a commercialization decision |

---

## 13. Governance & Operating Cadence

- **Executor recommends, stakeholder decides.** The AI acts as the single developer and
  *recommends* the next piece of work with a reason; the **product owner decides** the
  order. Work is single-threaded — one story to a validated completion, then the next
  recommendation. Sequencing is justified by risk/hardening value, not speed.
- **The validation covenant.** A piece of work is not "done" until a recorded live pass of
  the final version. Being blocked or reworking is the covenant working, not failing.
- **Restore-point discipline.** Known-good states (code + deployed-state manifest) are
  captured together so the project can return to a good point rather than forward-patch a
  broken one.
- **Management artifacts are first-class.** This charter, the plan, the runbook, the
  decisions, and the templates are held to the same bar as code — versioned, reviewed, and
  kept consistent (RD-015), with status living in exactly one place (the runbook).

---

## 14. How to read the ZTIE documents

Start here (the *why*), then descend as you need more detail:

1. **`PRODUCT_PLAN.md`** (this doc) — vision, outcomes, scope, stakeholders, strategy,
   risk. Charter-level; no story detail or status.
2. **[`PROJECT_PLAN.md`](../PROJECT_PLAN.md)** — phases, architecture flow, the registered
   decisions, and the acceptance criteria. The engineering *what/why*.
3. **[`RUNBOOK.md`](../RUNBOOK.md)** — the execution ledger: every story with its status,
   dependencies, and validation result, in build order. **The single source of truth for
   status.**
4. Supporting: [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) (system narrative + flow),
   [`docs/BUILD_ORDER.md`](BUILD_ORDER.md) (dependency graph), [`docs/COMPLIANCE.md`](COMPLIANCE.md)
   (control mappings), [`METHODOLOGY.md`](../METHODOLOGY.md) (the operating system),
   [`BOM.md`](../BOM.md) / [`RESTORE.md`](../RESTORE.md) (inventory + restore procedure).

> **The one rule that keeps these consistent:** each fact has a single home. Status lives
> in the runbook; decisions live in the plan's decisions table; the *why* lives here. When
> a document needs another's fact, it **links** to it — it does not copy it.
