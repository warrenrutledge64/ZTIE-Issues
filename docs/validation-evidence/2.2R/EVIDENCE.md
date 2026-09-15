# Story 2.2R — Retained Validation Evidence (RD-054)

> **Purpose (RD-054).** This folder holds the RAW, retained artifacts that make Story
> 2.2R's ✅ **auditable rather than testimony.** A skeptical third party can re-derive
> the pass from these artifacts without trusting Kiro, Gemini, or anyone's recollection.
> This does NOT claim the validation is bulletproof — a passing sample proves the
> presence of the tested behavior, not the absence of all defects.

## Provenance (marker ④)
- **Story:** 2.2R — remediation of 2.2G (Gitleaks positive-detection + raw-JSON redaction).
- **intake_id:** `669f5ce7-bef4-47bd-aa7f-a4fca1450005`
- **artifact sha256:** `88fe02344fec0aa65f55975ac5b67f6651228de4564838daa99952d5377493d0`
- **commit SHA under test:** `78c27ab` (branch `feature/story-2.2G`, PR #156, on `main`)
- **contract_version:** `1.2`
- **accounts:** Forensic `360999005254` (findings doc) / Hub `641628980935` (summary).
- **validated:** 2026-09-15, live, under the RD-053 split-brain protocol; independently
  adjudicated PASS by the validator (Gemini); the raw output below was read by the human.

## Positive-exercise (marker ①) — the boundary FIRED live
Raw Forensic findings document: `static-findings.json` (in this folder). The lane
reported a genuine gitleaks detection on a non-allowlisted planted secret:

```
tools: gitleaks -> status: ok, finding_count: 1   (bandit 0, checkov 2, signature-scan 0)
finding: tool=gitleaks  check_family=signature  severity=high  rule_id=generic-api-key
message: "Detected a Generic API Key ...: potential secret detected (wJal************ (redacted))"
```
`gitleaks finding_count = 1` (≥ 1 required). A `count: 0` result would have been
INCONCLUSIVE; this is a positive live exercise.

## Redaction / proof-of-absence (marker ②) — value excised, finding persists
The finding is present, but the secret VALUE is masked (`wJal************ (redacted)`),
and the raw value never enters the record. Re-runnable proof-of-absence, run on the
Forensic findings doc:

```
$ grep -c '<planted secret value>' static-findings.json     # -> 0   (value absent)
$ grep -c '"Secret"\|"Match"'      static-findings.json     # -> 0   (raw gitleaks fields never copied)
proof-of-absence: the planted secret returns 0 matches in the record
```
(The masked prefix `wJal…` is the well-known AWS documentation example key prefix; no
live credential is present in the record.)

## Human attestation (marker ③-human)
> Attested by: warren (stakeholder), 2026-09-15. I read the raw JSON findings record for
> intake `669f5ce7-bef4-47bd-aa7f-a4fca1450005` on the live Forensic system and confirmed
> the gitleaks finding is present (count 1, severity high) while the secret VALUE is
> redacted/excised; a grep of the planted value against the record returns 0 matches.

## Hub summary crossing (marker ③-crossing) — bounded summary crossed un-quarantined
Raw Hub tracking-item projection: `hub-static_scan-item.json` (in this folder). The
bounded, verdict-free summary attached to the Hub tracking record for intake
`669f5ce7…` under attribute `static_scan` (NOT quarantined), proving the RD-013 gate
accepted the v1.2 summary:

```
static_scan.total_findings = 3
static_scan.tools          = [bandit 0, checkov 2, gitleaks 1, signature-scan 0]   <- gitleaks present
static_scan.highest_severity = high
static_scan.counts_by_severity = {high: 1, medium: 2, low: 0, critical: 0, info: 0}
static_scan.compliance = NIST IA-5/SC-28 (x3), ISO A.5.17/A.8.24 (x3), 3 mapped / 0 unmapped
static_scan.findings_s3_key = findings/669f5ce7-.../static-findings.json   <- points back to the Forensic doc
```
The Hub carries only the bounded derived summary (RD-009/RD-013); the full findings
document stays in Forensic. The summary crossing un-quarantined confirms the Hub
ingest gate was on v1.2 and accepted the gitleaks-bearing summary.

## Verdict
All four RD-054 markers are satisfied with retained raw artifacts (this folder):
positive live detection (`gitleaks count 1`), raw-JSON redaction + proof-of-absence,
named human attestation, and provenance pins. Independently adjudicated PASS by the
validator (Gemini) under the RD-053 split-brain protocol; the human read the raw
record. This makes 2.2R's ✅ auditable — a third party can re-run the greps against
`static-findings.json` and re-derive the pass without trusting any party's word.
