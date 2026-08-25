# ZTIE — Compliance Control Traceability Matrix

> The single auditable home for mapping ZTIE **design artifacts** (registered
> decisions, stories, non-functional constraints) to security-control frameworks.
> Governed by **RD-014** ([`../PROJECT_PLAN.md`](../PROJECT_PLAN.md) §5).
>
> **This is a living document and is currently a stub.** The full back-mapping of
> existing artifacts is tracked as its own validated story (see the runbook) and is
> best executed once the core pipeline design stabilizes. New artifacts propose
> their mappings at authoring time (see the brief template).

## Framework scope (for audit)

- **NIST SP 800-53 Rev 5** — the **control catalog of record** (control IDs like
  `AC-3`, `SI-10`, `SC-7`, `AU-2`).
- **NIST CSF** — framework-level mapping (Functions/Categories) where useful.
- **NIST family, related** — RMF (SP 800-37) context as relevant.
- **ISO/IEC 27001:2022 Annex A** — control IDs (e.g. `A.5.x`, `A.8.x`).

## Convention (candidate vs. ratified)

- Every mapping has a **Status**: `Proposed` (candidate, authored but not reviewed)
  or `Ratified` (reviewed + accepted by an accountable party).
- **ZTIE claims control coverage only for `Ratified` mappings.** `Proposed` mappings
  are working candidates, not compliance assertions.
- Mapping is an interpretive exercise; the **authoritative** mapping for an audit is
  the responsibility of an accountable compliance reviewer, not the authoring agent.

## Traceability matrix

> One row per (artifact, control) candidate. Populated incrementally; the dedicated
> back-mapping story fills the existing artifacts. Kept in sync with
> `PROJECT_PLAN.md` (decisions/constraints) and `RUNBOOK.md` (stories).

| Artifact | NIST 800-53 (Rev 5) | NIST CSF | ISO/IEC 27001:2022 Annex A | Rationale | Status |
|----------|---------------------|----------|-----------------------------|-----------|--------|
| RD-013 / Story 1.1R — enforced data contract on the Forensic→Hub boundary | `SI-10` (information input validation), `SC-7` (boundary protection) | `PR.DS-2` (data-in-transit protected), `PR.PT-4` | `A.8.26` (application security requirements), `A.8.22` (segregation of networks) | The Hub-owned validating gate enforces an allow-list schema on all data crossing the trust boundary from the blast zone; fail-closed input validation at a controlled boundary | Proposed |
| RD-016 / Story 1.1R — least-privilege one-directional SQS door | `AC-3` (access enforcement), `AC-6` (least privilege), `SC-7(3)` (access points) | `PR.AC-4` (access permissions, least privilege) | `A.5.15` (access control), `A.8.3` (information access restriction) | The Forensic principal holds exactly `sqs:SendMessage` on exactly one queue and no access to any Hub data store; single controlled access point into the control plane | Proposed |
| RD-012 / Story 1.1R — durable audit record in the Hub (out of the blast zone) | `AU-2` (event logging), `AU-9` (protection of audit information), `CP-2` (contingency) | `PR.IP-4`, `DE.AE-3` | `A.8.15` (logging), `A.5.28` (collection of evidence) | The authoritative tracking record lives in the durable control plane so it survives blast-zone teardown and serves as the audit trail | Proposed |
| Story 1.1R — fail-closed quarantine of non-conforming records | `SI-10`, `AU-2`, `SI-4` (system monitoring) | `DE.AE-2` (analyze detected events) | `A.8.16` (monitoring activities) | Rejected envelopes are retained (quarantine S3 + DLQ) for triage without polluting the authoritative record; supports detection/analysis of malformed or hostile crossings | Proposed |
| RD-013 / Story 1.1R — verdict decided Hub-side, never imported from crossed data | `AC-3`, `CM-5` (access restrictions for change) | `PR.AC-4` | `A.8.2` (privileged access rights) | The security verdict is a Hub-owned, human-gated decision; crossed data cannot self-assert a verdict (status enum excludes verdicts; validator re-asserts) | Proposed |
| Story 1.2 — preprocessor classifies by CONTENT, not the claimed type | `SI-10` (information input validation), `SI-3` (malicious code protection) | `DE.CM-4`, `PR.DS-6` (integrity checking) | `A.8.26` (application security requirements) | The classifier inspects actual bytes (magic-bytes / structural sniffing) and distrusts the untrusted extension; where they disagree the content signal is authoritative and both are recorded — input validation that resists a mislabeled/disguised artifact | Proposed |
| Story 1.2 — classification recorded as tracked component metadata | `CM-8` (system component inventory), `AU-2` (event logging) | `ID.AM-2` (software platforms inventoried) | `A.5.9` (inventory of information/assets) | The derived artifact class is upserted onto the durable Hub tracking record keyed by `intake_id`, inventorying what each artifact is for downstream routing/audit | Proposed |
| Story 1.2 — classification label is integrity-bound + carries no verdict/route | `SI-7` (software/information integrity), `AC-4` (information flow enforcement) | `PR.DS-6`, `PR.AC-5` | `A.8.26`, `A.5.14` (information transfer) | A label can attach only to the exact artifact it was computed over (`intake_id`+`sha256` conditional update; sha mismatch → quarantine), and the classification carries no verdict/route/safety field — it is a LABEL only; the verdict stays Hub-side/human-gated | Proposed |

## Maintenance

- **New artifact →** propose its candidate mappings when it is authored (the brief
  template carries a candidate-mappings table; registered decisions and
  non-functional constraints add their rows here).
- **Review →** an accountable party ratifies (`Proposed` → `Ratified`) or corrects.
- **Change →** if an artifact changes materially, re-review its mappings (a stale
  mapping is worse than none).
- This matrix and the artifacts it references must stay in sync; the matrix is the
  consolidated view, the artifacts are the source.
