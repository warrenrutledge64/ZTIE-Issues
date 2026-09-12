# ZTIE Nova Pro correlation prompt (Story 3.2, RD-035)

> This is the human-readable, reviewable master of the Nova Pro correlation prompt
> for the Phase-3 static ↔ dynamic correlation engine. The **authoritative** prompt
> text actually sent to the model lives in code as
> `lambdas/hub_correlate/correlate.py::SYSTEM_INSTRUCTION` +
> `build_user_message()`, so the prompt cannot drift from the code and stays
> offline-testable. This document mirrors that text and explains the design; if the
> two ever differ, **the code is authoritative** and this file must be re-synced.

## Role framing (system turn)

Nova Pro is framed as a **security EVIDENCE CORRELATION engine**, never a decision
engine. It receives ONE normalized combined-event record (Story 3.1, RD-033) for a
single artifact — the static-analysis findings (misconfigurations) alongside the
dynamic behavioral indicators observed while the artifact ran in the isolated
detonation chamber — and its ONLY job is to **correlate** that evidence:

- where the static findings are **supported / explained** by the observed behavior,
- where behavior has **no static explanation** (`dynamic_only`),
- where a static finding has **no corresponding behavior** (`static_only`),
- where static and dynamic evidence **contradict** (`contradiction`).

## Hard rule: NO VERDICT (evidence, never a decision)

The prompt **explicitly forbids a verdict**. The model must not decide or state
whether the artifact is safe, unsafe, malicious, benign, approved, rejected, should
be forwarded, or should pass/fail. There is no verdict field and the model must not
invent one. A human reviewer makes that decision downstream (Phase 4). "Severity" is
described only as **how notable** a correlated observation is (evidence), never as a
decision.

This mirrors the zero-trust invariant enforced everywhere in ZTIE (RD-014): the
correlation is EVIDENCE; the verdict stays Hub-side / human-gated. Even if the model
returned a verdict-shaped key, the code's allow-list parse (`parse_correlation`)
drops it — the `correlation.contract.v1` schema has no slot for it.

## Bounded input (RD-009)

The user turn embeds ONLY the bounded, derived evidence view built by
`build_prompt_payload()`:

- `inputs_present`, `complete` (aggregation-completeness facts, not a verdict);
- `static`: presence, `highest_severity`, `total_findings` (roll-up, by reference);
- `dynamic`: presence, `outcome`;
- `behavioral_events`: the ALREADY-sanitized 2.5 events carried through by 3.1,
  further capped for the prompt (`offset_ms`, `category`, `syscall`, `summary`);
- `behavioral_event_count`, and a flag if the events were prompt-capped.

It never contains the raw artifact body, raw findings text, the raw command log, or
the raw behavioral trace — those stay in Forensic (RD-009). All behavioral timings
are relative offsets carried through from 2.5.

## Required output shape (bounded, parsed defensively)

The model is instructed to return **only** a single JSON object:

```json
{
  "summary": "<narrative correlation, < 3000 chars>",
  "findings": [
    {
      "kind": "correlated | static_only | dynamic_only | contradiction",
      "severity": "unknown | none | info | low | medium | high | critical",
      "title": "<short title>",
      "detail": "<optional longer explanation>",
      "static_refs": ["<optional short refs>"],
      "behavioral_refs": ["<optional short refs>"]
    }
  ]
}
```

The response is parsed **defensively** (`parse_correlation`): the code tolerates
prose or a ```` ```json ```` fence around the JSON, allow-lists every `kind` /
`severity`, clips every string to the contract bounds, caps `findings` at
`MAX_FINDINGS = 100` (recording `truncated: true` if it had to drop the tail), and
drops any field the contract does not define. If the response cannot be parsed into
the contract, the correlator records `status: "unparseable"` and **no fabricated
correlation** — the same honesty discipline as 3.1's absent inputs.

## Non-determinism + throttling

`temperature` is `0.0` for the most reproducible correlation possible from a
non-deterministic model. Bedrock throttling / 5xx are retried with **real
exponential backoff + jitter** (RD-003) in `awsio.invoke_nova`; the number of
attempts is recorded on the result (`attempts`) so the retry is inspectable. If the
retry budget is exhausted (or the error is non-retryable), the correlator records
`status: "model_error"` with a bounded `status_detail` and never fabricates a
correlation.
