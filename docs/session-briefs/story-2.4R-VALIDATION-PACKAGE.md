# Gemini Independent-Validation Package — Story 2.4R (RD-054 evidence backfill of the DYNAMIC lane / strace)

> **What this is.** The self-contained package YOU (the stakeholder) fill in and paste
> to the independent validator (Gemini) so Gemini authors the DoD + live steps and
> adjudicates the result. Built from `docs/GEMINI_VALIDATION_PACKAGE_TEMPLATE.md` per
> **RD-052 + RD-053 + RD-054**.
>
> **Kiro's role here is limited to the objective pointers below.** Kiro did NOT author
> the DoD, did NOT curate the diff, and does NOT interpret the result. YOU pull the raw
> diff (Part A) and write the requirement in your OWN words (Part B). If the diff or the
> requirement reaches Gemini via Kiro instead of via you, the pass is provisional.
>
> **Why 2.4R exists.** Story 2.4 (behavioral telemetry / strace) was validated live
> 2026-09-10 and genuinely worked (real filesystem ops captured), but that pass predates
> RD-053/054 and left NO retained raw evidence — and Forensic is ephemeral, so the
> original trace has aged out. The dynamic lane is a security boundary (behavioral
> detection), so under RD-054 it needs a retained, auditable evidence folder. 2.4R
> supplies it via a FRESH live strace run. (2.4 stays ✅ for what it validated; it is not
> retro-edited.)

---

## Part 0 — The cold-start KICKOFF BLOCK (paste this whole block into a fresh Gemini chat)

> Fill ONLY the `<<< WARREN: … >>>` requirement in your own words, then paste everything
> between the fence into a new Gemini chat. It embeds the diff-fetch command (PR #78 build
> + PR #79 strace fix), the role, the facts, and the deliverables — Gemini drives from zero.

```
You are the INDEPENDENT VALIDATOR (RD-052/053/054) for the ZTIE project, Story 2.4R —
the auditable evidence backfill of the DYNAMIC LANE (strace behavioral telemetry, the
remediation of 2.4). The build agent (Kiro) wrote this code; you did NOT. Author your OWN
Definition of Done and a numbered, soup-to-nuts live runbook, and try to BREAK the change
— do not confirm the happy path. I (the stakeholder) run everything on live AWS and read
the raw output; you never touch the live system, only what I paste you. Kiro is a
write-only scribe at the end; it authored none of your rubric.

STEP 1 — Tell me to fetch the raw code, then WAIT for me to paste it. The commands I run
in AWS CloudShell (gh is not available there) are:

    read -rs GH_TOKEN && export GH_TOKEN
    curl -sSL -H "Authorization: Bearer $GH_TOKEN" -H "Accept: application/vnd.github.v3.diff" \
      https://api.github.com/repos/warrenrutledge64/ZTIE-Issues/pulls/78
    curl -sSL -H "Authorization: Bearer $GH_TOKEN" -H "Accept: application/vnd.github.v3.diff" \
      https://api.github.com/repos/warrenrutledge64/ZTIE-Issues/pulls/79
    unset GH_TOKEN

STEP 1.5 — FULL CONTEXT FETCH (mandatory — a diff is NOT enough). The Story 2.4 defect
(strace tracing the WRAPPER, not the artifact) lived in the surrounding execution code,
not the changed lines — so you may NOT sign off on the strace invocation, the trace
parser, or the boundary crossing from diff hunks alone. Have me fetch the FULL raw source
of every script/parser/template in this lane, pinned to the reviewed commit SHA:

    read -rs GH_TOKEN && export GH_TOKEN
    SHA=566e274        # the 2.4 merge commit under test — pin every fetch to this
    for f in \
      lambdas/detonation/capturespec.py \
      lambdas/detonation/behavior.py \
      lambdas/detonation/handler.py \
      lambdas/detonation/awsio.py \
      lambdas/detonation/behavior.contract.v1.json \
      lambdas/hub_ingest/handler.py \
      infra/lib/ztie-detonation-stack.ts ; do
      echo "===== $f @ $SHA ====="
      curl -sSL -H "Authorization: Bearer $GH_TOKEN" -H "Accept: application/vnd.github.v3.raw" \
        "https://api.github.com/repos/warrenrutledge64/ZTIE-Issues/contents/$f?ref=$SHA"
      echo
    done
    unset GH_TOKEN

If reviewing the diff you find another file whose full context you need (e.g. the SSM
command construction or any helper the wrapper calls), NAME it and have me fetch it the
same way before you write the DoD.

(PR #78 = the 2.4 build; PR #79 = the strace-wrapper fix; merge commit 566e274. I will
paste both raw diffs AND the full raw files above. Review the ACTUAL code, not my summary.)

PLAIN REQUIREMENT (my own words — the one anchor neither AI authored):
<<< WARREN: WRITE 2-4 SENTENCES HERE IN YOUR OWN WORDS. e.g.: When an artifact is
detonated on the ephemeral EC2, the dynamic lane must actually capture THAT artifact's
own runtime behavior with strace — its syscalls, its file operations, and its outbound
network connection attempts. The full trace must stay in Forensic; only a bounded,
verdict-free summary may cross to the Hub. It must never fake a capture, never leak the
raw trace across the boundary, and never emit a verdict. >>>

BUILDER'S CLAIMS TO VERIFY, NOT TRUST:
- artifact runs host-native (NO Docker) UNDER strace; strace traces the artifact/
  interpreter DIRECTLY, not just SSM-agent/shell noise (the original 2.4 defect, fixed in
  PR #79).
- the FULL trace stays in Forensic S3 (RD-009); only a bounded, derived, verdict-free
  behavior.contract.v1 summary crosses to the Hub (8th RD-013 envelope kind).
- summary carries real capture facts: capture_status=captured, capture_tool=strace,
  syscall tally, filesystem op-classes, network as INTENT (a failed connect in the
  egress-less VPC -> connected:false).
- NO verdict/safe/approved/forward/pass_fail/malicious field anywhere.
- graceful degradation: if strace is absent, records capture_status=tool_unavailable and
  does NOT crash / does NOT fake a summary.

FACTS SHEET (objective):
- Accounts: Forensic 360999005254 (detonation + full trace) / Hub 641628980935 (ingest +
  tracking).
- Deploy order (deploy-gap): redeploy ZtieDetonationStack (Forensic) AND ZtieHubTrackingStack
  (Hub) on current main BEFORE submitting; verify BEHAVIOR_CONTRACT_VERSION=1.0 took.
- strace as built: strace -ff -tt -y -s 256 -o <prefix> -e <file,network,process,signal>.
- AMI: strace must be pre-baked on the ubuntu-22.04 golden AMI. The known-behavior test
  artifact must use a network binary the AMI ships so the network-INTENT path fires (the
  original run had curl absent -> 0 connect attempts).
- Submit: SigV4 POST /intake from a Forensic principal, routed to the dynamic lane. Verify
  on the Hub tracking record by intake_id, attribute "behavior". Full trace in Forensic S3
  under traces/<intake_id>/behavior-trace.txt.

DELIVER, IN THIS ORDER:
1. Adversarial review of the diff vs. the requirement — every way the capture could
   silently miss the artifact's own behavior (tracing the wrapper, buffering loss, partial
   -o flush), leak raw content across the boundary, or record a verdict.
2. Your OWN Definition of Done (derived from the requirement, not copied from the builder),
   which MUST require: (a) a positive live capture — a known-behavior artifact yields
   capture_status=captured with real syscalls.total / filesystem.total_ops reflecting the
   artifact's OWN ops, and network.connect_attempts >= 1 INTENT; a not_run/tool_unavailable/
   empty capture is INCONCLUSIVE, never PASS; (b) a human reads the actual Forensic strace
   trace AND the derived summary and confirms they correspond and carry no verdict field;
   (c) retained raw evidence (raw summary + a trace slice + the Hub crossed record +
   provenance intake_id + commit SHA) in docs/validation-evidence/2.4R/ — a sealed PASS from
   you is necessary but NOT sufficient; the retained artifact is the proof.
3. Soup-to-nuts runbook — number every step, the exact command, and exactly what literal
   output proves pass vs fail (aws sts get-caller-identity per block; the Forensic+Hub
   redeploy order + env-pin check; the known-behavior artifact + how it's submitted;
   reading the Hub "behavior" record AND the Forensic raw trace; graceful degradation if
   strace is absent).
4. What only a HUMAN should sign off — the raw-trace read (artifact's own behavior present;
   no raw content leaked across RD-013); two LLMs agreeing is not sufficient.
5. A sealed verdict block after I paste the raw output: VERDICT: PASS | FAIL | INCONCLUSIVE,
   each DoD item marked with its literal evidence line, any human sign-off outstanding.
6. An evidence manifest — the exact RAW artifacts I must retain in
   docs/validation-evidence/2.4R/ so the pass is auditable, not testimony.

Ask me for any value you need rather than guessing. Begin with STEP 1.
```

---

## Part A2 — OPERATOR COMMAND SET (self-contained; every data item ships its command)

> Command-completeness (METHODOLOGY §4a): every artifact you'll paste to Gemini has its
> exact command here, labeled by account, with an `aws sts get-caller-identity` guard.
> Gemini's runbook will order these; this is the reference so you never have to hunt.
> `<intake_id>` is returned by the submit step (BLOCK 4). Two placeholders you fill from
> stack outputs are shown inline.

**BLOCK 1 — fetch the diffs (any shell with the GitHub token; feeds Gemini STEP 1):**
```
read -rs GH_TOKEN && export GH_TOKEN
curl -sSL -H "Authorization: Bearer $GH_TOKEN" -H "Accept: application/vnd.github.v3.diff" \
  https://api.github.com/repos/warrenrutledge64/ZTIE-Issues/pulls/78
curl -sSL -H "Authorization: Bearer $GH_TOKEN" -H "Accept: application/vnd.github.v3.diff" \
  https://api.github.com/repos/warrenrutledge64/ZTIE-Issues/pulls/79
```

**BLOCK 2 — full source pinned to the SHA (feeds Gemini STEP 1.5):**
```
SHA=566e274
for f in lambdas/detonation/capturespec.py lambdas/detonation/behavior.py \
  lambdas/detonation/handler.py lambdas/detonation/awsio.py \
  lambdas/detonation/behavior.contract.v1.json lambdas/hub_ingest/handler.py \
  infra/lib/ztie-detonation-stack.ts ; do
  echo "===== $f @ $SHA ====="
  curl -sSL -H "Authorization: Bearer $GH_TOKEN" -H "Accept: application/vnd.github.v3.raw" \
    "https://api.github.com/repos/warrenrutledge64/ZTIE-Issues/contents/$f?ref=$SHA"
  echo
done
unset GH_TOKEN
```

**BLOCK 3 — redeploy the lane + verify the env pin (FORENSIC 360999005254):**
```
aws sts get-caller-identity        # expect 360999005254
cd ~/ZTIE-Issues && git fetch origin && git checkout main && git reset --hard origin/main
npx cdk deploy ZtieDetonationStack --require-approval never
DFN=$(aws cloudformation describe-stacks --stack-name ZtieDetonationStack \
  --query "Stacks[0].Outputs[?OutputKey=='DetonationFunctionName'].OutputValue" --output text)
aws lambda get-function-configuration --function-name "$DFN" \
  --query "Environment.Variables.BEHAVIOR_CONTRACT_VERSION"     # expect "1.0"
```

**BLOCK 3b — redeploy the Hub ingest (HUB 641628980935):**
```
aws sts get-caller-identity        # expect 641628980935
cd ~/ZTIE-Issues && git checkout main && git reset --hard origin/main
npx cdk deploy ZtieHubTrackingStack --require-approval never
```

**BLOCK 4 — build + submit the known-behavior artifact (FORENSIC 360999005254):**
```
aws sts get-caller-identity        # expect 360999005254
# file ops + an outbound INTENT using an AMI-shipped binary (egress-less VPC -> attempt fails, capture succeeds):
cat > /tmp/known_behavior.sh <<'EOF'
#!/bin/sh
for i in 1 2 3 4 5; do echo x > /tmp/ztie-probe-$i.txt; rm -f /tmp/ztie-probe-$i.txt; done
getent hosts example.com || true          # DNS/network-intent via a base binary
exec 3<>/dev/tcp/169.254.169.254/80 || true
EOF
ENDPOINT=$(aws cloudformation describe-stacks --stack-name ZtieIntakeStack \
  --query "Stacks[0].Outputs[?OutputKey=='IntakeEndpoint'].OutputValue" --output text)
python3 - <<PY
import base64,json
open("/tmp/intake.json","w").write(json.dumps({
  "filename":"known_behavior.sh",
  "content_base64":base64.b64encode(open("/tmp/known_behavior.sh","rb").read()).decode(),
  "content_type":"text/x-shellscript","submitter":"2.4R-validation"}))
PY
pip install awscurl -q 2>/dev/null; awscurl --service execute-api --region us-east-1 \
  -X POST -H 'Content-Type: application/json' -d @/tmp/intake.json "$ENDPOINT"
# -> copy the returned intake_id
```

**BLOCK 5 — read the derived summary that crossed to the Hub (HUB 641628980935):**
```
aws sts get-caller-identity        # expect 641628980935
INTAKE=<intake_id from BLOCK 4>
TBL=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack \
  --query "Stacks[0].Outputs[?contains(OutputKey,'TrackingTable')].OutputValue" --output text)
aws dynamodb get-item --table-name "$TBL" \
  --key "{\"intake_id\":{\"S\":\"$INTAKE\"}}" --query "Item.behavior" --output json
# expect capture_status=captured, capture_tool=strace, real syscalls/filesystem counts,
# network.connect_attempts>=1 (connected:false), NO verdict field
```

**BLOCK 6 — pull the FULL raw trace from Forensic + prove correspondence (FORENSIC 360999005254):**
```
aws sts get-caller-identity        # expect 360999005254
INTAKE=<intake_id from BLOCK 4>
BKT=$(aws cloudformation describe-stacks --stack-name ZtieIntakeStack \
  --query "Stacks[0].Outputs[?OutputKey=='ArtifactBucketName'].OutputValue" --output text)
aws s3 cp "s3://$BKT/traces/$INTAKE/behavior-trace.txt" /tmp/trace.txt && head -80 /tmp/trace.txt
grep -c "ztie-probe" /tmp/trace.txt                 # the artifact's OWN file ops present
grep -E "connect\(|socket\(|getaddrinfo" /tmp/trace.txt | head   # the network-INTENT syscalls
grep -c "execve" /tmp/trace.txt                     # confirms strace traced the artifact directly
```

**BLOCK 7 — gather the RD-054 retained evidence (save these for Kiro to commit to `docs/validation-evidence/2.4R/`):**
```
# from BLOCK 5: save the Hub behavior record
aws dynamodb get-item --table-name "$TBL" --key "{\"intake_id\":{\"S\":\"$INTAKE\"}}" \
  --query "Item.behavior" --output json > /tmp/2.4R-hub-behavior.json
# from BLOCK 6: keep /tmp/trace.txt (or a representative slice) as the raw trace artifact
head -200 /tmp/trace.txt > /tmp/2.4R-trace-slice.txt
# provenance: intake_id (above) + commit 566e274 ; plus your named+dated attestation that
# you READ /tmp/trace.txt and it corresponds to the summary with no verdict field.
```
Paste BLOCK 5 + BLOCK 6 raw outputs back to Gemini for adjudication; hand BLOCK 7's files
+ your attestation + the intake_id/SHA to Kiro on a sealed PASS.

---

## Part A — Pull the raw code yourself (YOU run this; do NOT let Kiro curate it)

> **AWS CloudShell note:** the `gh` CLI is NOT available in CloudShell. Pull the raw
> diff with `curl` against the GitHub REST API using a token-authenticated request.
> Set the token WITHOUT echoing it (keeps it off screen + out of history); do NOT paste
> the token into Gemini or the chat:

```
read -rs GH_TOKEN && export GH_TOKEN     # paste the token at the silent prompt, press Enter

# The 2.4 dynamic-lane code landed in PR #78 (build) + PR #79 (fix/reconcile — the
# strace-wrapper fix). Pull BOTH raw diffs:
curl -sSL -H "Authorization: Bearer $GH_TOKEN" -H "Accept: application/vnd.github.v3.diff" \
  https://api.github.com/repos/warrenrutledge64/ZTIE-Issues/pulls/78 | tee /tmp/2.4-build.diff | head -c 200
curl -sSL -H "Authorization: Bearer $GH_TOKEN" -H "Accept: application/vnd.github.v3.diff" \
  https://api.github.com/repos/warrenrutledge64/ZTIE-Issues/pulls/79 | tee /tmp/2.4-fix.diff | head -c 200

unset GH_TOKEN
```

Copy the **full** diffs that print — that raw code is what Gemini reviews.

> Alternatively, since the 2.4 code is merged to `main`, read the files directly in your
> cloned repo: `git -C <repo> show 566e274` (PR #78 merge), or open the code files below.
>
> The dynamic-lane code that governs strace behavior: `lambdas/detonation/capturespec.py`
> (the `strace -ff -tt -y -s 256 -o PREFIX -e <trace groups>` command + trace
> concatenation), `lambdas/detonation/behavior.py` (raw-trace → bounded
> `behavior.contract.v1` summary: syscall tally, network INTENT, filesystem op-classes),
> `lambdas/detonation/handler.py` (`BEHAVIOR_CONTRACT_VERSION`, emit), `awsio.py`
> (`put_trace` + `send_behavior_envelope`), `behavior.contract.v1.json`; the Hub side
> `lambdas/hub_ingest/handler.py` (the `behavior` envelope kind) + its bundled contract;
> and `infra/lib/ztie-detonation-stack.ts`. Paste the whole diff; let Gemini decide what
> matters.

---

## Part B — Paste to Gemini (with the diff from Part A)

> **Role:** You are the INDEPENDENT validator for ZTIE Story 2.4R (the RD-054 evidence
> backfill of the dynamic lane — strace behavioral telemetry — the remediation of 2.4).
> The build agent (Kiro) wrote this code; you did not. Author your OWN Definition of Done
> and a numbered, soup-to-nuts live runbook, and try to **break** the change — do not
> confirm the happy path. Derive your criteria from the plain requirement below; do not
> trust the builder's wording.
>
> **Plain requirement (the anchor — YOU write this in YOUR OWN words before pasting to
> Gemini; it is the one input neither AI authored). Replace this whole quoted block with
> your wording.** Suggested substance to cover, in your own voice: when an artifact is
> detonated host-native on the ephemeral EC2, the lane must ACTUALLY capture that
> artifact's own runtime behavior with strace (its syscalls, its filesystem operations,
> its outbound network ATTEMPTS), derive a bounded verdict-free summary, keep the full
> trace in Forensic, and cross only the bounded summary to the Hub. Describe what
> "correct" and "must-never" look like to you.
>
> **Builder's claims to VERIFY, not trust:**
> - the artifact runs host-native (NO Docker, RD-001) UNDER strace, and strace traces the
>   artifact/interpreter DIRECTLY (not just the SSM-agent/shell noise — this was the
>   original 2.4 defect, fixed in PR #79).
> - the FULL trace stays in Forensic S3 (RD-009); only a bounded, DERIVED, verdict-free
>   `behavior.contract.v1` summary crosses to the Hub (8th RD-013 envelope kind).
> - the summary carries real capture facts: `capture_status=captured`,
>   `capture_tool=strace`, syscall tally, filesystem op-classes, network as INTENT
>   (a failed `connect` in the egress-less VPC → `connected:false`).
> - NO verdict/safe/approved/forward/pass_fail/malicious field anywhere (behavior is
>   EVIDENCE; the verdict is Hub-side/human-gated).
> - graceful degradation: if strace is absent the lane records
>   `capture_status=tool_unavailable` and does NOT crash / does NOT fake a summary.
>
> **Facts sheet (objective — accounts, deploy order, tooling):**
> - Accounts: Forensic `360999005254` (detonation + full trace) / Hub `641628980935`
>   (ingest + tracking).
> - Deploy order (deploy-gap, 2.6 lesson): redeploy `ZtieDetonationStack` (Forensic) AND
>   the Hub stack (ships the bundled `behavior.contract.v1`, `BEHAVIOR_CONTRACT_VERSION`)
>   BEFORE submitting a run.
> - strace command (as built): `strace -ff -tt -y -s 256 -o <prefix> -e <file,network,process,signal groups>`.
> - AMI: strace must be pre-baked on the ubuntu-22.04 golden AMI (isolated host, no
>   boot-time internet). Pick a known-behavior artifact that uses binaries the AMI ships
>   so the network-INTENT path can fire (the original 2.4 run had `curl` absent → 0
>   connect attempts).
> - Submit path: SigV4 `POST /intake` from a Forensic-authed principal, routed to the
>   dynamic lane; verify on the Hub tracking record (`intake_id`), attribute `behavior`;
>   the full trace is in Forensic S3 under `traces/<intake_id>/`.
> - Code under test: PR #78 (build) + PR #79 (strace-wrapper fix), merge `566e274`.
>
> **The code (raw diff from YOUR Part A — NOT a builder-curated summary):**
> ```
> [PASTE THE FULL RAW DIFFS FROM PART A HERE — replace this line]
> ```
>
> **Deliver, in this order:**
> 1. **Adversarial review** of the diff vs. the requirement — every way the capture could
>    silently miss the artifact's own behavior (tracing the wrapper not the artifact,
>    buffering loss, partial `-o` flush), leak raw content across the boundary, or record
>    a verdict; anything you cannot verify from the diff alone.
> 2. **Your own Definition of Done** (derived from the requirement, NOT copied from the
>    builder). It MUST require, per RD-053 + RD-054:
>    - a **positive live capture**: a known-behavior artifact yields
>      `capture_status=captured` with real `syscalls.total` / `filesystem.total_ops`
>      reflecting the artifact's OWN operations (and, if a network-capable binary is used,
>      `network.connect_attempts ≥ 1` INTENT). A `not_run` / `tool_unavailable` / empty
>      capture is **INCONCLUSIVE, never PASS**.
>    - a **raw-trace read**: a human reads the actual Forensic strace trace AND the derived
>      summary and confirms they correspond (the artifact's own syscalls are present) and
>      carry NO verdict field.
>    - **retained evidence** committed to `docs/validation-evidence/2.4R/`: the raw
>      `behavior.contract.v1` summary, a slice of the raw Forensic trace, the Hub crossed
>      record, and provenance (intake_id + commit SHA). A sealed PASS from you is necessary
>      but NOT sufficient — the retained artifact is the proof.
> 3. **Soup-to-nuts runbook** — number every step, the exact command, and exactly what
>    literal output proves pass vs. fail. Include: account/tab (`aws sts get-caller-identity`
>    each block), the Forensic+Hub redeploy order + a check the live env pins took, the
>    known-behavior artifact + how it is submitted, reading the Hub `behavior` record AND
>    the Forensic raw trace, and the graceful-degradation behavior if strace is absent.
> 4. **What only a human should sign off** — the raw-trace read (the artifact's own
>    behavior is present; no raw content leaked across RD-013) is human-verified; two LLMs
>    agreeing is not sufficient.
> 5. **A sealed verdict block** — `VERDICT: PASS | FAIL | INCONCLUSIVE`, each DoD item
>    marked with its literal evidence line, and any human sign-off still outstanding.
> 6. **An evidence manifest (RD-054)** — the exact RAW artifacts I must RETAIN in
>    `docs/validation-evidence/2.4R/` so the pass is auditable, not testimony.
>
> Ask me for any value you need rather than guessing.

---

## Part C — How the loop runs (RD-053 4-stage)

1. **Handoff (Kiro → you):** Kiro gave the objective pointers above and stepped out.
2. **Design (you → Gemini):** you pull the diff (Part A) + write the requirement (Part B),
   paste both to Gemini; Gemini authors the DoD + runbook.
3. **Execute & judge (you + Gemini):** you run it on live AWS, paste the RAW output +
   the raw trace slice back to Gemini, which adjudicates PASS / FAIL / INCONCLUSIVE and
   returns the sealed verdict. You read the raw trace yourself (security boundary).
4. **Close-out (you → Kiro):** ONLY on an explicit PASS, bring the sealed verdict + raw
   evidence to Kiro, which transcribes it verbatim, commits `docs/validation-evidence/2.4R/`,
   flips 2.4R → ✅, clears the register, and opens the gate (next pipe work = Story 4.7).

---

## Part D — Straight talk (the limits — do not skip)

- **The requirement anchor is yours.** If you paste a requirement Kiro wrote, its framing
  sneaks back in. Reword it in your own voice.
- **Real system + your eyes are the grader.** Gemini can't run the live system or read the
  raw trace; it only writes the gate and adjudicates the output you paste.
- **An empty/`not_run` capture is not a pass.** For this security boundary, strace must
  actually capture the artifact's OWN behavior; a degraded/tool-unavailable run proves only
  that the lane didn't crash.
- **Retention is the proof.** A sealed PASS from Gemini is necessary but not sufficient —
  the pass rests on the raw artifacts retained in `docs/validation-evidence/2.4R/`, captured
  at validation time because Forensic is ephemeral. This makes the pass auditable, not
  bulletproof.
- **Avoid the two-AI handshake.** "Builder built it, validator approved it" is not a pass —
  your reading of the raw output is.
