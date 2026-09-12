# Proposal — Phase 3 three-independent-score model (draft RD-038)

> **Status: PROPOSAL for review (not adopted).** This document is a decision record
> DRAFT for the stakeholder (and the Gemini planning partner) to react to. Nothing in
> the pipeline changes until it is approved. On approval, the RD below is registered in
> `PROJECT_PLAN.md` and the story re-scoping in §5 is sequenced into `RUNBOOK.md`.
>
> **Origin: a stakeholder course-correction.** The stakeholder identified — while Story
> 3.3 was still 🟡 (built, not yet live-validated) — that this aspect of the Phase-3
> assessment **was not properly defined** when Phase 3 was originally scoped. The earlier
> framing scored the assessment from the STATIC lane's point of view (3.3 as
> "false-positive reconciliation" over a single AI correlation). This proposal records the
> corrected definition. Catching it now, before 3.3 is validated + merged into the
> pipeline shape, is the cheap moment to correct it — the validation covenant working as
> intended, not a failure.

---

## 1. The decision (what the stakeholder specified)

The Phase-3 assessment produces **THREE INDEPENDENT risk scores**, each on a **0–100
scale where HIGHER = RISKIER**, and **all three are produced by Amazon Nova Pro** (RD-003)
via **three separate, evidence-scoped calls**, centrally in Phase 3 (Hub):

| # | Score | Nova Pro call sees | Nature |
|---|-------|--------------------|--------|
| 1 | **Static risk score** | **ONLY** the static lane's derived evidence (the static-scan findings + severities already on the Hub tracking item) | EVIDENCE |
| 2 | **Dynamic risk score** | **ONLY** the dynamic lane's derived evidence (the sanitized behavioral telemetry + run outcome already on the Hub tracking item) | EVIDENCE |
| 3 | **Combined risk score** | the static lane's evidence **AND** the dynamic lane's evidence, **together** — the raw (derived) evidence from BOTH lanes, **NOT** the two scores above | EVIDENCE |

Load-bearing points of the stakeholder's decision:

- **All three scores are computed by Nova Pro** — not in the lanes, not by deterministic
  central logic. There is **no in-lane scoring** and **no scoring formula**; the model
  performs every assessment.
- **THREE SEPARATE CALLS, each scoped to its evidence** (chosen deliberately over one call
  returning all three, for steadiness/resilience — see §4). The static call cannot see
  dynamic evidence and vice-versa, so the two lane scores are genuinely INDEPENDENT (one
  lane's evidence cannot contaminate the other's score). A fault in one call (throttle /
  error / unparseable) does not sink the other two — each score records its OWN honest
  status.
- **Both lanes carry their own weight.** Static and dynamic are PEERS. Dynamic is NOT a
  check on static, and static is NOT the default point of view.
- **The combined score reasons over the RAW EVIDENCE FROM BOTH LANES, not over the two
  lane scores.** It is a genuinely independent assessment of the whole evidence picture —
  NOT an aggregation/average of `static_score` + `dynamic_score`. The combined Nova Pro
  call is given the static evidence + the dynamic evidence together and forms its own
  0–100 number.
- **"Raw evidence" = the already-derived, sanitized, bounded evidence on the Hub** (the
  static-scan findings summary + the sanitized behavioral telemetry / run outcome). It is
  **NEVER** the raw untrusted payload or the raw trace — those never leave Forensic
  (RD-008/009). "Raw" here means "the primary evidence itself, not a pre-digested
  correlation," in its sanitized/bounded Hub-side form.
- **A SCORE IS EVIDENCE, NEVER A VERDICT.** Each of the three is a 0–100 risk number (+ a
  short rationale) and **nothing more** — there is deliberately **NO PASS / FAIL /
  INCONCLUSIVE / safe / approved / forward / block field**. The enforcement VERDICT stays
  exactly where it is today: **Story 3.5 + the human accept/reject gate on the
  dashboard.** A high score INFORMS that human; it never makes the call. (RD-003 + the
  human-gate covenant intact.)

---

## 2. Why this is a real change (and what it supersedes)

What is built today (Phase 3 so far):

- **3.1 (✅)** aggregates the per-lane derived outputs into ONE `combined_event`.
- **3.2 (✅)** asks Nova Pro to CORRELATE that combined event into ONE verdict-free
  `correlation_result` — a list of findings tagged `correlated` / `static_only` /
  `dynamic_only` / `contradiction`. It produces **no score**.
- **3.3 (🟡, RD-037)** synthesizes that correlation into `accuracy` (a false-positive
  reconciliation metric) + `gaps`. Its `accuracy_score` is, by its own definition, a
  **static-scoped** metric: `confirmed / (confirmed + static_only)` — it measures "how
  noisy was the static scanner," and it **does not weigh `dynamic_only` at all**.
- **3.4 (⬜)** was scoped as "the unified threat score + prioritized remediations."

The gap the stakeholder identified: **there is no independent static score, no
independent dynamic score, and the only score that exists (3.3's `accuracy_score`) reads
the assessment from static's point of view.** Dynamic evidence is captured but does not
carry equal weight in any headline number.

**This proposal supersedes that under-defined framing.** It does NOT retro-edit the ✅
stories (2.1/2.2/2.3/2.4/2.5 stay ✅ for what they validated; 3.1/3.2 stay ✅ for what they
validated). It **remediates forward** (per the covenant): the 🟡/⬜ Phase-3 stories are
re-scoped. Note (a genuine simplification vs. an earlier draft of this proposal): because
ALL scoring is done by Nova Pro in Phase 3 over evidence that **already crosses to the
Hub**, **the ✅ static and dynamic lanes need NO change at all** — they keep crossing the
same derived evidence they cross today. There are no new lane-scoring stories.

---

## 3. Draft RD-038 (to be registered in `PROJECT_PLAN.md` on approval)

> **RD-038 — Phase-3 risk assessment is THREE INDEPENDENT 0–100 risk scores (static,
> dynamic, combined), ALL produced by Nova Pro via three separate evidence-scoped calls
> over the derived Hub-side evidence; a score is EVIDENCE, the verdict stays
> human-gated.** The Phase-3 output is three risk scores on a 0–100 scale (higher =
> riskier), not one static-centric metric, and **all three are produced by Amazon Nova Pro
> (RD-003), centrally in Phase 3 (Hub), via THREE SEPARATE evidence-scoped calls** — there
> is no in-lane scoring and no scoring formula. **(a) Static risk score:** a Nova Pro call
> that sees ONLY the static lane's derived evidence (the static-scan findings + severities
> on the Hub tracking item) and returns a 0–100 risk score + rationale. **(b) Dynamic risk
> score:** a Nova Pro call that sees ONLY the dynamic lane's derived evidence (the
> sanitized behavioral telemetry + run outcome on the Hub tracking item) and returns a
> 0–100 risk score + rationale. **(c) Combined risk score:** a Nova Pro call that sees the
> static lane's evidence AND the dynamic lane's evidence TOGETHER (the raw derived evidence
> from BOTH lanes — NOT the two lane scores) and forms its OWN independent 0–100 risk
> assessment of the whole picture. The two lanes are PEERS (dynamic is not a check on
> static; neither is the default POV), and separate scoped calls make the two lane scores
> genuinely independent (neither lane's evidence can contaminate the other's score) and
> fault-isolated (one call failing does not sink the other two; each score records its own
> honest status). **"Raw evidence" is the already-derived, sanitized, bounded evidence on
> the Hub** — NEVER the raw untrusted payload or raw trace, which never leave Forensic
> (RD-008/009 intact). **(d) Evidence, never a verdict:** every one of the three scores is
> EVIDENCE — there is NO verdict/safe/approved/forward/pass_fail/malicious/clean field
> anywhere, each Nova Pro prompt asks for a RISK SCORE ONLY (never a decision), and each
> response is parsed defensively into a bounded 0–100 integer (a malformed/absent/throttled
> response is recorded honestly via a per-score status, never fabricated). The enforcement
> verdict (PASS/FAIL/INCONCLUSIVE) remains Story 3.5 + the human accept/reject gate on the
> dashboard, untouched. **(e)** This RD CORRECTS the earlier under-defined, static-centric
> framing of the Phase-3 assessment (which produced 3.3's `accuracy_score` from static's
> POV); it remediates FORWARD by re-scoping the 🟡/⬜ Phase-3 stories (§5), and — because
> all scoring is Hub-side over already-crossed evidence — requires NO change to the ✅
> static/dynamic lanes and adds no new lane stories. Candidate control mappings (RD-014):
> NIST 800-53 r5 **RA-3** (Risk Assessment — three independent risk scores), **RA-5**
> (Vulnerability Monitoring/Scanning — static evidence risk), **SI-4** (System Monitoring —
> dynamic behavior risk), **CA-7** (Continuous Monitoring); NIST CSF **ID.RA-5**
> (threats/vulnerabilities/likelihood used to determine risk), **DE.AE-2** (events
> analyzed); ISO 27001:2022 **A.8.8** (Management of technical vulnerabilities), **A.8.16**
> (Monitoring activities) — all Proposed. | **Rationale:** the stakeholder's model treats
> static and dynamic as independent, equally-weighted views and adds a genuinely combined
> assessment on top — a more faithful risk picture than a single static-scoped metric.
> Having Nova Pro perform all three assessments (rather than deterministic scoring) keeps
> the risk judgement with the model that already reasons over the evidence; three separate
> scoped calls make the lane scores truly independent + fault-isolated (steadier/more
> resilient than one call, at the cost of 3× the Bedrock calls — an accepted trade); the
> combined call reasoning over both lanes' raw evidence (not the two numbers) is what makes
> it a genuine combined assessment rather than arithmetic. Keeping all three as EVIDENCE
> (never a verdict) preserves RD-003 + the human gate: the model may CHARACTERIZE risk but
> never DECIDE. | <date> | proposed |

---

## 4. The boundary that needs the most care (Nova Pro produces *scores*)

Today Nova Pro produces a correlation but **no number**. Under this proposal it produces
**three risk scores** (via three calls). That is a genuine expansion of what the model is
trusted to output, so the guardrails must be explicit:

- **Three scoped prompts, three calls.** The static call is given ONLY static evidence;
  the dynamic call ONLY dynamic evidence; the combined call BOTH lanes' evidence together.
  This is deliberate (chosen over one all-in-one call): true independence + fault
  isolation. **Accepted trade:** ~3× the Bedrock cost/latency and three retry loops
  instead of one (each the proven 3.2 exponential-backoff pattern).
- **Each prompt asks for a 0–100 risk score + supporting rationale ONLY.** It MUST NOT ask
  the model whether the artifact is safe/unsafe, should pass/fail, or should be
  forwarded/blocked. (The 3.2 "evidence engine, not a decision engine" framing, extended
  to "risk-scoring engine.")
- **Each response is parsed defensively** into a bounded integer `0 ≤ score ≤ 100`.
  Out-of-range/unparseable is clamped or recorded via that score's `status`, never
  fabricated.
- **Per-score honest status + partial results.** Because the calls are independent, one can
  fail while the others succeed (e.g. `static_score: 40`, `dynamic_score: status=model_error`,
  `combined_score: 70`). The scoring-result schema represents each score with its own
  `status` so a partial result is recorded honestly — never faked, never hidden. If the
  combined call runs while a lane call failed, that is recorded too (the combined call
  still had the underlying evidence; the lane SCORE failing does not starve it).
- **The scoring-result schema is allow-list, verdict-free** (no verdict-shaped key
  anywhere), integrity-keyed by `intake_id + sha256`, own version pin — the proven
  contract-first pattern.
- **A score ≠ a verdict.** The record carries three numbers + rationales + statuses. It
  carries no decision. 3.5 (+ the human) turns scores into PASS/FAIL/INCONCLUSIVE.

---

## 5. Story impact (remediate forward — nothing ✅ is retro-edited)

> This re-scopes the Phase-3 stories. Exact story IDs + tiers are the **planning partner's
> (Gemini's) call** to sequence; the shape below is the proposal for that planning.

**A. The ✅ static + dynamic lanes: NO CHANGE.** All scoring is Hub-side, over evidence
that already crosses today, so 2.1/2.2 (static) and 2.3/2.4/2.5 (dynamic) are untouched —
no new lane-scoring stories. (This is a simplification vs. an earlier draft of this
proposal, which had proposed in-lane scoring; the stakeholder's "Nova Pro does all three"
decision removes that work.)

**B. Re-scope the Phase-3 stories:**

- **3.3 (🟡 → reworked):** it stays 🟡 (never validated on the old shape). Re-scoped to the
  **three-score Nova Pro assessment**: three evidence-scoped calls (static / dynamic /
  combined) producing a bounded, verdict-free scoring result on the Hub tracking item. This
  absorbs the "unified score" that 3.4 previously owned. The old accuracy/gap synthesis
  either folds in as supporting detail or is dropped in favor of the three scores +
  rationales (planning partner's call).
- **3.4 (⬜):** re-scoped to "**detailed findings + prioritized remediations** over the
  three scores" (the remediation list ranks by the combined + lane scores + finding
  severities). It consumes 3.3's scores; it does not itself score.
- **3.5 (⬜):** UNCHANGED in intent — verdict derivation (PASS/FAIL/INCONCLUSIVE) from the
  scores + the human gate. It now consumes three scores instead of one.

**C. Dependency effect:** all three scores are produced in one Phase-3 step over
already-Hub evidence, so no new upstream dependency is introduced (3.3-reworked still
depends on the evidence 3.1/3.2 already put on the item). The planning partner re-derives
build tiers if the 3.3/3.4 split changes.

---

## 6. What does NOT change

- The three-account topology, RD-008/009 (Hub out of the blast zone; only derived,
  sanitized data crosses; the raw payload + raw trace never leave Forensic), RD-012/013
  (no durable Forensic store; the data-contract gate). Nova Pro scores the DERIVED evidence
  already on the Hub — it never touches raw payload.
- The ✅ static + dynamic lanes (no in-lane scoring; they cross the same evidence they do
  today).
- The human accept/reject gate and the PASS/FAIL/INCONCLUSIVE verdict (Story 3.5). Scores
  inform it; they do not replace it.
- The validation covenant. 3.3 stays 🟡; the reworked Phase-3 stories each earn ✅ only on
  their own recorded live pass.
- Everything already ✅ (2.1–2.5, 3.1, 3.2) stays ✅ for what it validated.

---

## 7. Open questions for the stakeholder / planning partner

1. **Score-scale comparability:** should the three 0–100 scores be defined on a *comparable*
   scale (so a human reading "static 40 / dynamic 85 / combined 80" interprets them
   consistently), or is each call free to define its own 0–100 as fits its evidence? (A
   shared rubric in the three prompts would make them comparable.)
2. **3.3 vs 3.4 split:** adopt §5.B (3.3 = the three Nova Pro scores; 3.4 = findings +
   remediations), or a different split? And does the old accuracy/gap synthesis survive as
   supporting detail under 3.3, or is it dropped in favor of the three scores + rationales?
3. **Story IDs / tiers:** Gemini to confirm the reworked 3.3/3.4 scope + re-derive build
   tiers.

---

## 8. Recommended next step

On approval of this proposal: register **RD-038** in `PROJECT_PLAN.md`, hand §5 + §7 to
Gemini to sequence the reworked Phase-3 stories into `RUNBOOK.md`, and re-issue the Story
3.3 brief/prompt against the corrected definition. Until then, **3.3 remains 🟡 and no
pipeline code changes** — the register stays as-is (3.3 open), so the advancement gate
correctly still blocks new downstream feature work.
