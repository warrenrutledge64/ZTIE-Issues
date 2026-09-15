# Gemini Independent-Validation Package — Story 2.2R (remediation of 2.2G, RD-053)

> **What this is.** The self-contained package YOU (the stakeholder) fill in and paste
> to the independent validator (Gemini) so Gemini authors the DoD + live steps and
> adjudicates the result. Built from `docs/GEMINI_VALIDATION_PACKAGE_TEMPLATE.md` per
> **RD-052 + RD-053**.
>
> **Kiro's role here is limited to the objective pointers below.** Kiro did NOT author
> the DoD, did NOT curate the diff, and does NOT interpret the result. YOU pull the raw
> diff (Part A) and write the requirement in your OWN words (Part B). If the diff or the
> requirement reaches Gemini via Kiro instead of via you, the pass is provisional.
>
> **Why 2.2R exists.** 2.2G's live run registered gitleaks `count: 0` (a doc-placeholder
> the tool allowlists) and rested redaction on a `REDACTED-OK` summary tag. Under RD-053
> that is INCONCLUSIVE for the security control — the boundary was never positively
> exercised. 2.2R supplies the missing LIVE positive-detection + raw-JSON redaction proof.
> (2.2G stays ✅ for the wiring/supersession it validated; it is not retro-edited.)

---

## Part A — Pull the raw code yourself (YOU run this; do NOT let Kiro curate it)

> **AWS CloudShell note:** the `gh` CLI is NOT available in CloudShell. Pull the raw
> diff with `curl` against the GitHub REST API using a token-authenticated request.
> Export a PAT once (do NOT paste the token into Gemini or the chat), then run the curl:

```
export GH_TOKEN=<your_personal_access_token>

curl -sSL \
  -H "Authorization: Bearer $GH_TOKEN" \
  -H "Accept: application/vnd.github.v3.diff" \
  https://api.github.com/repos/warrenrutledge64/ZTIE-Issues/pulls/156
```

Copy the **full** diff that prints — that raw diff is the code Gemini reviews. (You can
append `| tee /tmp/2.2G.diff` to also save it to a file for easy copying.)

> Alternatively, since the 2.2G code is already merged to `main`, you can read the raw
> files directly in your cloned repo at the merge commit:
> `git -C <repo> show 78c27ab` (full merge diff), or open the individual files below.
>
> The 2.2G code is PR #156, merge commit `78c27ab`, branch `feature/story-2.2G`
> (already on `main`). The diff includes governance/markdown files too; the
> code that governs the gitleaks behavior is: `lambdas/static_scan/scanners.py`,
> `normalize.py`, `signatures.py`, `compliance.py`, `toolplan.py`, `handler.py`,
> `Dockerfile`, `static-findings.contract.v1.json`; `lambdas/hub_ingest/handler.py` +
> its `static-scan-summary.contract.v1.json`; and the CDK stacks
> `infra/lib/ztie-static-scan-stack.ts` + `ztie-hub-tracking-stack.ts`. Paste the whole
> diff; let Gemini decide what matters.

---

## Part B — Paste to Gemini (with the diff from Part A)

> **Role:** You are the INDEPENDENT validator for ZTIE Story 2.2R (the remediation of
> 2.2G under RD-053). The build agent (Kiro) wrote this code; you did not. Author your
> OWN Definition of Done and a numbered, soup-to-nuts live runbook, and try to **break**
> the change — do not confirm the happy path. Derive your criteria from the plain
> requirement below; do not trust the builder's wording.
>
> **Plain requirement (the anchor — YOU write this in YOUR OWN words before pasting to
> Gemini; it is the one input neither AI authored). Replace this whole quoted block with
> your wording.** Suggested substance to cover, in your own voice: the static-analysis
> lane must actually DETECT a real secret using the compiled gitleaks binary in the
> deployed container, normalize that finding into the derived contract, and the sensitive
> value must be REDACTED in the record that is stored / crosses to the Hub — while the
> finding itself is still recorded. Describe what "correct" and "must-never" look like to
> you.
>
> **Builder's claims to VERIFY, not trust:**
> - gitleaks is the SOLE secret scanner; the old Story-2.2 regex SECRET rules were removed
>   (no duplicate/second secret engine).
> - a detected secret's raw value is REDACTED and never persisted (RD-009), while the
>   finding metadata remains.
> - findings normalize into `static-findings.contract.v1` **v1.2** (tool `gitleaks`,
>   `check_family=signature`, `severity=high`); the bounded summary attaches to the Hub
>   tracking table without quarantine (Hub ingest pinned to summary **v1.2**).
> - a gitleaks tool error is recorded (`status=error`) and does NOT crash the lane (fail-open).
>
> **Facts sheet (objective — accounts, stacks, deploy order):**
> - Accounts: Forensic `360999005254` (static lane), Hub `641628980935` (ingest + tracking).
> - Deploy order (deploy-gap): redeploy `ZtieHubTrackingStack` (Hub) FIRST so the ingest
>   gate accepts summary contract **v1.2**, THEN rebuild/redeploy `ZtieStaticScanStack`
>   (Forensic) which embeds compiled `gitleaks v8.30.1`.
> - Submit path: SigV4 `POST /intake` from a Forensic-authed principal; verify on the Hub
>   tracking DynamoDB record (`intake_id`).
> - Code under test: PR #156 / commit `78c27ab`.
>
> **The code (raw diff from YOUR Part A — NOT a builder-curated summary):**
> ```
> [PASTE THE FULL RAW DIFF OUTPUT FROM PART A HERE — replace this line]
> ```
>
> **Deliver, in this order:**
> 1. **Adversarial review** of the diff vs. the requirement — every way detection could
>    silently fail (allowlists, wrong invocation, container path), every way a secret
>    could leak un-redacted, anything you cannot verify from the diff alone.
> 2. **Your own Definition of Done** (derived from the requirement, NOT copied from the
>    builder). It MUST require, per RD-053:
>    - a **positive live detection**: a planted, **non-allowlisted** secret (a synthetic
>      real-format token, e.g. an `AKIA…`-shaped or high-entropy value — NOT `EXAMPLE`/a
>      doc placeholder) yields **`gitleaks count ≥ 1`** in the live output. A `count: 0`
>      result is **INCONCLUSIVE, never PASS**.
>    - a **raw-JSON redaction check**: a human reads the actual record (Forensic findings
>      doc + the bounded Hub summary) and confirms the secret VALUE is excised while the
>      finding persists. A `REDACTED-OK` summary tag is NOT acceptable evidence.
> 3. **Soup-to-nuts runbook** — number every step, the exact command, and exactly what
>    literal output proves pass vs. fail. Include: account/tab (`aws sts get-caller-identity`
>    each block), the Hub-first deploy order + a check that the live env pins took, planting
>    the non-allowlisted secret, submitting it, reading the raw finding + the redacted value,
>    and the fail-open behavior on a tool error.
> 4. **What only a human should sign off** — the secret-redaction boundary (RD-009) is
>    human-read from the raw JSON; two LLMs agreeing is not sufficient.
> 5. **A sealed verdict block** — after I paste you the raw output, return
>    `VERDICT: PASS | FAIL | INCONCLUSIVE`, each DoD item marked with its literal evidence
>    line, and any human sign-off still outstanding. This is what I carry back to Kiro.
>
> Ask me for any value you need rather than guessing.

---

## Part C — How the loop runs (RD-053 4-stage)

1. **Handoff (Kiro → you):** Kiro gave the objective pointers above and stepped out.
2. **Design (you → Gemini):** you pull the diff (Part A) + write the requirement (Part B),
   paste both to Gemini; Gemini authors the DoD + runbook.
3. **Execute & judge (you + Gemini):** you run it on live AWS, paste the RAW output back to
   Gemini, which adjudicates PASS / FAIL / INCONCLUSIVE and returns the sealed verdict.
   You read the raw redaction record yourself (security boundary).
4. **Close-out (you → Kiro):** ONLY on an explicit PASS, bring the sealed verdict + raw
   evidence to Kiro, which transcribes it verbatim, flips 2.2R → ✅, clears the register,
   and opens the gate (next pipe work = Story 4.7).

---

## Part D — Straight talk (the limits — do not skip)

- **The requirement anchor is yours.** If you paste a requirement Kiro wrote, its framing
  sneaks back in. Reword it in your own voice.
- **Real system + your eyes are the grader.** Gemini can't run the live system or read the
  raw record; it only writes the gate and adjudicates the output you paste.
- **`count: 0` is not a pass.** For this security boundary, the tool must actually fire on a
  planted secret; a benign/allowlisted input proves only that the container didn't crash.
- **Redaction is read raw, by a human.** `REDACTED-OK` is a conclusion, not evidence.
- **Avoid the two-AI handshake.** "Kiro built it, Gemini approved it" is not a pass — your
  reading of the raw output is.
