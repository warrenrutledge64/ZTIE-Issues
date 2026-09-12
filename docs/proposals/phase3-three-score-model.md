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
scale where HIGHER = RISKIER**:

| # | Score | Computed WHERE | Computed HOW | Nature |
|---|-------|----------------|--------------|--------|
| 1 | **Static risk score** | in the **static lane** (Forensic — the 2.1/2.2 scanners) | deterministic, from the static findings + their severities | EVIDENCE |
| 2 | **Dynamic risk score** | in the **dynamic lane** (Forensic — 2.3 detonation / 2.4 capture / 2.5 sanitize) | deterministic, from the observed behavior | EVIDENCE |
| 3 | **Combined risk score** | **centrally in Phase 3** (Hub) | **Amazon Nova Pro** forms its OWN independent assessment of the evidence already on the Hub tracking item | EVIDENCE |

Load-bearing points of the stakeholder's decision:

- **Both lanes carry their own weight.** Static and dynamic are PEERS. Dynamic is NOT a
  mere check on static (the old "does the behavior corroborate the static flag?" frame),
  and static is NOT the default point of view. Each lane stands on its own findings and
  its own score.
- **The combined score is its OWN independent assessment** — NOT a mechanical
  average/formula of the two lane scores. Nova Pro looks at the whole evidence picture and
  produces its own 0–100 risk number (option (a), chosen explicitly over a deterministic
  central formula).
- **A SCORE IS EVIDENCE, NEVER A VERDICT.** The combined score is a 0–100 risk number and
  **nothing more** — there is deliberately **NO PASS / FAIL / INCONCLUSIVE / safe /
  approved / forward / block field**. The enforcement VERDICT stays exactly where it is
  today: **Story 3.5 + the human accept/reject gate on the dashboard.** A high score
  INFORMS that human; it never makes the call. (RD-003 + the human-gate covenant intact.)

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
carry equal weight in any headline number until 3.4 — and even 3.4 was under-defined as to
whether the lanes are peers.

**This proposal supersedes that under-defined framing.** It does NOT retro-edit the ✅
stories (2.1/2.2/2.3/2.4/2.5 stay ✅ for what they validated; 3.1/3.2 stay ✅ for what they
validated). It **remediates forward** (per the covenant): the ✅ lanes get *additive*
scoring extensions as NEW stories, and the 🟡/⬜ Phase-3 stories are re-scoped.

---

## 3. Draft RD-038 (to be registered in `PROJECT_PLAN.md` on approval)

> **RD-038 — Phase-3 risk assessment is THREE INDEPENDENT 0–100 risk scores (static +
> dynamic scored in-lane as peers; combined scored centrally by Nova Pro as its own
> assessment); a score is EVIDENCE, the verdict stays human-gated.** The Phase-3 output is
> three risk scores on a 0–100 scale (higher = riskier), not one static-centric metric.
> **(a) Static risk score** is computed IN the static lane (2.1/2.2, Forensic) from the
> static findings + severities and crosses the RD-013 gate as bounded, verdict-free
> derived evidence (extends the static-scan summary; own version pin). **(b) Dynamic risk
> score** is computed IN the dynamic lane (2.3/2.4/2.5, Forensic) from the observed
> behavior and crosses as bounded, verdict-free derived evidence (extends the dynamic-run
> / behavioral summary; own version pin). The two lanes are PEERS — dynamic is not a check
> on static and neither is the default point of view. **(c) Combined risk score** is
> computed CENTRALLY in Phase 3 (Hub) by Amazon Nova Pro (RD-003) as its OWN independent
> 0–100 risk assessment of the evidence already Hub-side (the combined event + the two lane
> scores + the correlation), NOT a mechanical average of the two lane scores. **(d)
> Evidence, never a verdict:** every one of the three scores is EVIDENCE — there is NO
> verdict/safe/approved/forward/pass_fail/malicious/clean field anywhere, the Nova Pro
> prompt asks for a RISK SCORE ONLY (never a decision), and the response is parsed
> defensively into a bounded 0–100 integer (a malformed/absent response is recorded
> honestly via a status, never fabricated). The enforcement verdict (PASS/FAIL/
> INCONCLUSIVE) remains Story 3.5 + the human accept/reject gate on the dashboard,
> untouched. **(e)** This RD CORRECTS the earlier under-defined, static-centric framing of
> the Phase-3 assessment (which produced 3.3's `accuracy_score` from static's POV); it
> remediates FORWARD — the ✅ lanes get additive scoring extensions as new stories, and the
> 🟡/⬜ Phase-3 stories are re-scoped (§5), rather than retro-editing any validated story.
> Candidate control mappings (RD-014): NIST 800-53 r5 **RA-3** (Risk Assessment — three
> independent risk scores), **RA-5** (Vulnerability Monitoring/Scanning — static risk),
> **SI-4** (System Monitoring — dynamic risk), **CA-7** (Continuous Monitoring); NIST CSF
> **ID.RA-5** (threats/vulnerabilities/likelihood used to determine risk), **DE.AE-2**
> (events analyzed); ISO 27001:2022 **A.8.8** (Management of technical vulnerabilities),
> **A.8.16** (Monitoring activities) — all Proposed. | **Rationale:** the stakeholder's
> model treats static and dynamic as independent, equally-weighted views and adds a
> genuinely combined assessment on top — a more faithful risk picture than a single
> static-scoped metric. Scoring each lane in its own lane keeps each score next to the
> evidence that produces it (and keeps the Hub out of the raw blast zone, RD-008/009);
> scoring the combined number centrally with Nova Pro (its own assessment, not a formula)
> is what makes it "combined" rather than arithmetic. Keeping all three as EVIDENCE (never
> a verdict) preserves RD-003 + the human gate: the model may CHARACTERIZE risk but never
> DECIDE. | <date> | proposed |

---

## 4. The one boundary that needs the most care (Nova Pro produces a *score*)

Today Nova Pro produces a correlation but **no number**. Under this proposal it also
produces a **combined risk score**. That is a genuine expansion of what the model is
trusted to output, so the guardrails must be explicit:

- The prompt asks for **a 0–100 risk score + supporting rationale ONLY**. It MUST NOT ask
  the model whether the artifact is safe/unsafe, should pass/fail, or should be
  forwarded/blocked. (Same "evidence correlation engine, not a decision engine" framing
  the 3.2 prompt already uses — extended to "risk-scoring engine.")
- The response is parsed **defensively** into a bounded integer `0 ≤ score ≤ 100`. Anything
  out of range or unparseable is clamped/recorded via a `status`, never fabricated.
- The scoring-result schema is allow-list, verdict-free (no verdict-shaped key anywhere),
  integrity-keyed by `intake_id + sha256`, own version pin — the proven contract-first
  pattern.
- **A score ≠ a verdict.** The record carries a number and a rationale. It carries no
  decision. 3.5 (+ the human) turns scores into PASS/FAIL/INCONCLUSIVE.

---

## 5. Story impact (remediate forward — nothing ✅ is retro-edited)

> This is a Phase-3 (and lane) re-architecture, so it re-scopes stories. Exact story IDs +
> tiers are the **planning partner's (Gemini's) call** to sequence; the shape below is the
> proposal for that planning.

**A. New scoring extensions to the ✅ lanes (additive; do not retro-edit the ✅ stories):**

- **Static-score extension** (extends 2.1/2.2): compute a static risk score (0–100) in the
  static lane from the findings + severities; cross it as bounded, verdict-free evidence
  (extend the static-scan summary contract, own pin). New story — e.g. `2.7` (or `2.2S`).
- **Dynamic-score extension** (extends 2.3/2.4/2.5): compute a dynamic risk score (0–100)
  in the dynamic lane from the observed behavior; cross it as bounded, verdict-free
  evidence. New story — e.g. `2.8` (or `2.5D`).

**B. Re-scope the Phase-3 stories:**

- **3.3 (🟡 → reworked):** it stays 🟡 (never validated on the old shape). Options for the
  planning partner: (i) **repurpose** 3.3 as the **combined-score (Nova Pro) assessment**
  step, or (ii) **keep** 3.3 as the accuracy/gap synthesis but explicitly demote its
  `accuracy_score` to a named "static false-positive reconciliation" sub-metric (NOT a
  headline score) that feeds the combined step. Recommendation: since the combined score is
  the natural home of the Nova Pro assessment and 3.4 already owned "the unified score,"
  fold the accuracy/gap synthesis and the combined-score assessment together and make the
  3.3/3.4 boundary: **3.3 = combined Nova Pro risk-score assessment (consumes both lane
  scores + the correlation)**, **3.4 = detailed findings + prioritized remediations built
  around the three scores.** (Final split is Gemini's call.)
- **3.4 (⬜):** re-scoped to "detailed findings + prioritized remediations over the three
  scores" (the remediation list ranks by the combined + lane scores + gap severities).
- **3.5 (⬜):** UNCHANGED in intent — verdict derivation (PASS/FAIL/INCONCLUSIVE) from the
  scores + the human gate. It now consumes three scores instead of one.

**C. Dependency effect:** the combined-score step (3.3-reworked) now depends on the two
lane scores existing, so the static-score + dynamic-score extensions must land (and be
live-validated) before the combined step can be validated. The planning partner re-derives
the build tiers accordingly.

---

## 6. What does NOT change

- The three-account topology, RD-008/009 (Hub out of the blast zone; only derived data
  crosses), RD-012/013 (no durable Forensic store; the data-contract gate). Lane scores are
  derived, bounded, verdict-free — they cross the existing gate like every other summary.
- The human accept/reject gate and the PASS/FAIL/INCONCLUSIVE verdict (Story 3.5). Scores
  inform it; they do not replace it.
- The validation covenant. 3.3 stays 🟡; the new lane-score stories and the reworked
  Phase-3 stories each earn ✅ only on their own recorded live pass.
- Everything already ✅ (2.1–2.5, 3.1, 3.2) stays ✅ for what it validated. This is
  additive/forward remediation, not a rewrite of validated work.

---

## 7. Open questions for the stakeholder / planning partner

1. **Score semantics detail:** are the two lane scores intended to be roughly comparable
   0–100 scales (so a human reading "static 40 / dynamic 85 / combined 80" interprets them
   consistently), or is each lane free to define its own 0–100 however fits its evidence?
2. **Combined-score inputs:** should Nova Pro see the two lane scores as inputs to its
   combined assessment, or ONLY the underlying evidence (so the combined number is not
   anchored to the lane numbers)? The stakeholder said "its own independent assessment" —
   this question decides whether "independent" means "not a formula over them" (they're
   still visible as input) vs. "does not even see them."
3. **3.3 vs 3.4 split:** adopt the §5.B recommendation (3.3 = combined Nova Pro score;
   3.4 = findings + remediations), or a different split?
4. **Story IDs / tiers:** Gemini to assign IDs + re-derive build tiers for the two new
   lane-score stories and the reworked Phase-3 stories.

---

## 8. Recommended next step

On approval of this proposal: register **RD-038** in `PROJECT_PLAN.md`, hand §5 + §7 to
Gemini to sequence the new + reworked stories into `RUNBOOK.md`, and re-issue the Story 3.3
brief/prompt against the corrected definition. Until then, **3.3 remains 🟡 and no pipeline
code changes** — the register stays as-is (3.3 open), so the advancement gate correctly
still blocks new downstream feature work.
