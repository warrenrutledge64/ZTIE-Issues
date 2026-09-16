# Gemini Independent-Validation Package — Story 2.4R (RD-054 evidence backfill of the DYNAMIC lane / strace)

> **What this is.** The self-contained package YOU (the stakeholder) fill in and paste
> to the independent validator (Gemini) so Gemini authors the DoD + live steps and
> adjudicates the result. Built from `docs/GEMINI_VALIDATION_PACKAGE_TEMPLATE.md` per
> **RD-052 + RD-053 + RD-054**.
>
> **Kiro's role here is limited to the objective pointers below.** Kiro did NOT author
> the DoD, did NOT curate the diff, and does NOT interpret the result. YOU run the fetch
> commands in the Part 0 block and write the requirement in your OWN words (the
> `<<< WARREN >>>` slot in Part 0). If the diff or the requirement reaches Gemini via Kiro
> instead of via you, the pass is provisional.
>
> **Why 2.4R exists.** Story 2.4 (behavioral telemetry / strace) was validated live
> 2026-09-10 and genuinely worked (real filesystem ops captured), but that pass predates
> RD-053/054 and left NO retained raw evidence — and Forensic is ephemeral, so the
> original trace has aged out. The dynamic lane is a security boundary (behavioral
> detection), so under RD-054 it needs a retained, auditable evidence folder. 2.4R
> supplies it via a FRESH live strace run. (2.4 stays ✅ for what it validated; it is not
> retro-edited.)

---

## FLOW MAP — the self-driving baton (do these in order; each step names the NEXT)

> **Audience boundary:** **Part 0 is the ONLY thing Gemini ever sees** (you paste it into
> a fresh Gemini chat). Parts A / A2 / C / D / E are **YOUR operator reference** — Gemini
> does not see them and does not need to. Wherever you are (same chat or new), the "▶ NEXT"
> baton at the end of each step tells you exactly what to do next, so nothing stalls.

```
STEP 0  Paste Part 0 into a FRESH Gemini chat; fill the <<< requirement >>> in your words.
          Gemini replies: "run the fetch commands and paste the output."   ▶ go to STEP 1
STEP 1  Run Part A2 BLOCK 1 (the 2.4R rework PR diff) + BLOCK 2 (full lane source pinned
          to the POST-FIX main tip SHA). Paste ALL output back into the SAME Gemini chat.  ▶ STEP 2
STEP 2  Gemini returns: adversarial review + its OWN DoD + a numbered live runbook that
          CRITIQUES the supplied commands for efficacy and ADDS stronger/corroborating/
          negative collection commands. (Gemini's runbook is authoritative; the Part A2
          blocks are only a floor/backup reference.)                       ▶ STEP 3
STEP 3  Run the live runbook (Part A2 BLOCKS 3–6 are the same commands, account-labeled):
          redeploy (Forensic+Hub) → submit known-behavior artifact → read Hub behavior
          record → pull + read the Forensic raw trace.                     ▶ go to STEP 4
STEP 4  Paste the live raw output (BLOCK 5 + BLOCK 6) back to Gemini.
          Gemini returns a SEALED VERDICT (PASS / FAIL / INCONCLUSIVE).    ▶ go to STEP 5
STEP 5  On PASS: gather Part A2 BLOCK 7 evidence + your named attestation, and hand the
          sealed verdict + evidence to KIRO. Kiro commits docs/validation-evidence/2.4R/
          and flips 2.4R ✅.  On INCONCLUSIVE/FAIL: 2.4R stays 🟡; fix + re-run from STEP 3.
```

---

## Part 0 — The cold-start KICKOFF BLOCK (paste this whole block into a fresh Gemini chat)

> **Fill ONLY the `<<< WARREN: … >>>` requirement in your own words**, then paste everything
> between the fence into a new Gemini chat. This block is **self-contained through the fetch**:
> it carries the role, the requirement anchor, the objective pointers, the STEP 1 + STEP 1.5
> **fetch commands** (so you never have to hunt — command-completeness, METHODOLOGY §4a), and
> the ordered deliverables. It does NOT re-print the *drift-prone facts* — the builder's
> claims, the full facts sheet, and the fixed runbook-output structure — because those live in
> **exactly ONE place** each (facts sheet → Part A2's block comments + your answers; runbook
> structure → Part E) so an edit is made once and can't drift out of sync. The commands ARE in
> the block because STEP 1 needs them to function; Part A2 is the labeled superset for the
> later live-run blocks (3–7).

```
You are the INDEPENDENT VALIDATOR (RD-052/053/054) for the ZTIE project, Story 2.4R —
the auditable evidence backfill of the DYNAMIC LANE (strace behavioral telemetry, the
remediation of 2.4). The build agent (Kiro) wrote this code; you did NOT. Author your OWN
Definition of Done and a numbered, soup-to-nuts live runbook, and try to BREAK the change
— do not confirm the happy path. I (the stakeholder) run everything on live AWS and read
the raw output; you never touch the live system, only what I paste you. Kiro is a
write-only scribe at the end; it authored none of your rubric.

ZERO-TRUST ON THE COMMANDS THEMSELVES. Every command I give you below (and in the runbook
you author) was written by the BUILDER or me — do NOT trust that it collects ENOUGH.
Before you rely on any command set, ANALYZE IT FOR EFFICACY: does it actually surface the
evidence needed to prove/break the requirement, or could a real defect hide in what it
does not capture (a truncated trace, a grep that misses a syscall family, a query that
reads only one field, a head -N that clips the proof)? Then PROPOSE ADDITIONAL COMMANDS
for more robust data collection — wider/independent captures, corroborating reads, and
negative probes that would expose a fake or partial result. Treat the supplied commands as
a floor, never a ceiling. Call out any command whose output could be gamed or is
insufficient, and give me the stronger command to run instead or in addition.

STEP 1 — Tell me to run these, then WAIT for me to paste the output. Fetch the 2.4R REWORK
PR diff (the fix on top of the original 2.4 lane — replace <REWORK_PR> with its number,
which I supply):

    read -rs GH_TOKEN && export GH_TOKEN
    curl -sSL -H "Authorization: Bearer $GH_TOKEN" -H "Accept: application/vnd.github.v3.diff" \
      https://api.github.com/repos/warrenrutledge64/ZTIE-Issues/pulls/<REWORK_PR>
    # (Optional context — the ORIGINAL 2.4 lane the rework sits on: PRs #78 build / #79 fix.)

STEP 1.5 — FULL CONTEXT FETCH (mandatory — a diff is NOT enough). The original 2.4 defect
(strace tracing the WRAPPER, not the artifact) lived in the UNCHANGED surrounding code, and
the FAIL defects (missing %desc, whole-concat truncation) likewise live in the wrapper, so
do not sign off on the strace invocation, the trace parser, or the boundary crossing from
diff hunks alone. Fetch the FULL raw source pinned to the POST-FIX main tip (I paste you the
exact SHA once the rework PR merges — set it here):

    SHA=<POST_FIX_MAIN_SHA>        # the main tip AFTER the 2.4R rework PR merges (I give it to you)
    for f in \
      lambdas/detonation/capturespec.py \
      lambdas/detonation/behavior.py \
      lambdas/detonation/handler.py \
      lambdas/detonation/awsio.py \
      lambdas/detonation/behavior.contract.v1.json \
      lambdas/detonation/test_capturespec.py \
      lambdas/detonation/test_behavior.py \
      lambdas/hub_ingest/handler.py \
      infra/lib/ztie-detonation-stack.ts ; do
      echo "===== $f @ $SHA ====="
      curl -sSL -H "Authorization: Bearer $GH_TOKEN" -H "Accept: application/vnd.github.v3.raw" \
        "https://api.github.com/repos/warrenrutledge64/ZTIE-Issues/contents/$f?ref=$SHA"
      echo
    done
    unset GH_TOKEN

If, reviewing it, you need another file's full context (a helper the wrapper calls, the
SSM command construction, anything), NAME it and I will fetch it the same way before you
write the DoD. Review the ACTUAL code I paste, not my summary.

PLAIN REQUIREMENT (my own words — the one anchor neither AI authored):
<<< WARREN: WRITE 2-4 SENTENCES HERE IN YOUR OWN WORDS. e.g.: When an artifact is
detonated on the ephemeral EC2, the dynamic lane must actually capture THAT artifact's
own runtime behavior with strace — its syscalls, its file operations, and its outbound
network connection attempts. The full trace must stay in Forensic; only a bounded,
verdict-free summary may cross to the Hub. It must never fake a capture, never leak the
raw trace across the boundary, and never emit a verdict. >>>

OBJECTIVE POINTERS (facts, not a rubric):
- Code under test: the FIXED dynamic lane after the 2.4R rework PR (fix/story-2.4R) merges
  to main. Review it at the POST-FIX main tip (I will paste you that exact SHA at STEP 1 —
  it does not exist until the rework PR merges, so it is NOT hardcoded here). The original
  2.4 lane is PR #78 (build) + PR #79 (strace-wrapper fix), merge 566e274; the 2.4R rework
  PR is the delta on top. I will paste you BOTH the rework diff AND the full lane source at
  the post-fix SHA.
- THIS IS A RE-VALIDATION AFTER A SEALED FAIL (attempt 1, 2026-09-16, intake
  2b0af6a6-6552-461f-a18f-f6cca60ba0bc). The prior FAIL and what the rework changed (VERIFY
  these against the diff — do not trust them):
    * FAIL DoD 1 — the raw trace missed the artifact's planted write buffer: strace was
      invoked with `-e trace=%file,%network,%process,%signal`, but `write`/`writev`/
      `pwrite64` are FD-based (the `%desc` group), NOT `%file`, so no `write()` was ever
      captured. The rework adds `%desc`. CONFIRM a write of a planted buffer now appears in
      the raw trace AND is summarized as a filesystem write op (with the path from the
      strace `-y` fd decoration, never the buffer content).
    * FAIL DoD 3 — the negative verdict-field probe hit `recommended_verdict`/
      `verdict_result`/`verdict_at` on the tracking item, written by the CONCURRENT Phase-3
      hub_verdict (RD-040) stage — legitimate fields, but the whole-item probe does not
      tolerate them. The DoD-3 probe must be SCOPED to the `behavior` attribute (or the run
      must use a detonation-only path that does not trigger Phase-3). Decide the scoping in
      your DoD.
    * Truncation hardening — the on-host emit previously capped the WHOLE lexically-sorted
      per-PID concatenation with a single `head -c`, so a noisy sibling PID could truncate
      the artifact's own PID trace out. The rework caps EACH per-PID file independently and
      sorts numerically. CONFIRM the artifact's own PID trace survives.
    * Network artifact — the prior artifact used `dash` `/dev/tcp` (unsupported by dash), so
      the outbound intent surfaced as a file `openat`, not a `connect()`, and
      connect_attempts=0. The new known-behavior artifact must issue a REAL `connect()`
      (invoke `bash` explicitly, or use a socket-opening base binary the AMI ships) so
      network INTENT is genuinely exercised.
- Accounts: Forensic 360999005254 (detonation + full trace) / Hub 641628980935 (ingest +
  tracking). The crossed record is the Hub tracking item's "behavior" attribute; the full
  trace stays in Forensic S3. (I have the exact deploy order, strace flags, AMI/artifact
  notes, and submit/verify commands on hand and will supply any value you ask for.)

DELIVER, IN THIS ORDER:
1. Adversarial review of the code vs. the requirement — every way the capture could
   silently miss the artifact's own behavior (tracing the wrapper, buffering loss, partial
   -o flush), leak raw content across the boundary, or record a verdict; flag anything you
   cannot verify from what I pasted.
2. Your OWN Definition of Done (derived from the requirement, NOT copied from the builder).
   This is a SECURITY BOUNDARY (behavioral detection + the RD-013 crossing), so it MUST
   require: (a) a POSITIVE live capture — a known-behavior artifact yields
   capture_status=captured with real syscalls.total / filesystem.total_ops reflecting the
   artifact's OWN ops, and network.connect_attempts >= 1 INTENT; a not_run /
   tool_unavailable / empty capture is INCONCLUSIVE, never PASS; (b) a human reads the
   actual Forensic strace trace AND the derived summary and confirms they correspond and
   carry no verdict field; (c) RETAINED raw evidence in docs/validation-evidence/2.4R/ —
   your sealed PASS is necessary but NOT sufficient; the retained artifact is the proof.
3. Soup-to-nuts runbook — number every step, the exact command, and exactly what LITERAL
   output proves pass vs fail (aws sts get-caller-identity per block; the Forensic+Hub
   redeploy order + an env-pin check; the known-behavior artifact + how it's submitted;
   reading the Hub "behavior" record AND the Forensic raw trace; graceful degradation if
   strace is absent). For EACH data-collection step, first WEIGH the command's efficacy
   (what could hide in what it does not capture) and ADD any stronger/corroborating/negative
   command needed — do not just reuse the commands I hand you. Ask me for any exact
   command/value rather than guessing.
4. What only a HUMAN should sign off — the raw-trace read (artifact's own behavior present;
   no raw content leaked across RD-013); two LLMs agreeing is not sufficient.
5. A sealed verdict block after I paste the raw output: VERDICT: PASS | FAIL | INCONCLUSIVE,
   each DoD item marked with its literal evidence line, any human sign-off outstanding.
6. An evidence manifest — the exact RAW artifacts I must retain in
   docs/validation-evidence/2.4R/ so the pass is auditable, not testimony.
7. The STEP-3 runbook as a DOWNLOADABLE fixed-format file — ONE self-contained fenced
   block, first line `<!-- FILE: docs/session-briefs/story-2.4R-LIVE-RUNBOOK.md -->`, using
   the standard headers, given to me AFTER the sealed verdict. (I will tell you the exact
   fixed structure if you ask; it is the project's standard runbook shape.)

Ask me for any value you need rather than guessing. Begin with STEP 1.
```

**▶ NEXT (FLOW MAP STEP 1):** you pasted Part 0 (with the fetch commands in it) and Gemini
asked for the code → run the STEP 1 + STEP 1.5 commands above and paste the output back into
the SAME Gemini chat (Part A2 mirrors these as BLOCK 1 + BLOCK 2 if you want them labeled by
account). The full facts sheet lives in **Part A2's block comments** (and your answers to
Gemini); the deliverable-#7 fixed runbook structure lives in **Part E** — Gemini gets those
via what you paste / answer, not by re-printing them in the kickoff block.

---

## Part A2 — OPERATOR COMMAND SET (self-contained; every data item ships its command)

> Command-completeness (METHODOLOGY §4a): every artifact you'll paste to Gemini has its
> exact command here, labeled by account, with an `aws sts get-caller-identity` guard.
> Gemini's runbook will order these; this is the reference so you never have to hunt.
> `<intake_id>` is returned by the submit step (BLOCK 4). Two placeholders you fill from
> stack outputs are shown inline.
>
> **These commands are a FLOOR, not a ceiling (zero-trust).** They were written by the
> builder / operator, so do NOT assume they collect ENOUGH. Gemini is instructed to analyze
> each command set for efficacy and to PROPOSE ADDITIONAL commands for more robust data
> collection (wider/independent captures, corroborating reads, negative probes that would
> expose a fake or partial result) — expect its runbook to strengthen these, not just
> reuse them. If a block's output could be gamed or clipped (a `head -N` that truncates the
> proof, a grep that misses a syscall family, a query that reads one field), run the
> stronger command Gemini gives you in addition.

**BLOCK 1 — fetch the 2.4R REWORK PR diff (any shell with the GitHub token; feeds Gemini STEP 1):**
```
read -rs GH_TOKEN && export GH_TOKEN
# <REWORK_PR> = the 2.4R rework PR number (fix/story-2.4R). The original 2.4 lane it sits
# on is PRs #78 (build) + #79 (strace-wrapper fix) — fetch those too only if Gemini asks.
curl -sSL -H "Authorization: Bearer $GH_TOKEN" -H "Accept: application/vnd.github.v3.diff" \
  https://api.github.com/repos/warrenrutledge64/ZTIE-Issues/pulls/<REWORK_PR>
```

**BLOCK 2 — STEP 1.5 FULL CONTEXT FETCH: full lane source pinned to the POST-FIX main tip (a diff alone is NOT enough — feeds Gemini STEP 1.5):**
```
SHA=<POST_FIX_MAIN_SHA>   # the main tip AFTER the 2.4R rework PR merges (git rev-parse origin/main)
for f in lambdas/detonation/capturespec.py lambdas/detonation/behavior.py \
  lambdas/detonation/handler.py lambdas/detonation/awsio.py \
  lambdas/detonation/behavior.contract.v1.json \
  lambdas/detonation/test_capturespec.py lambdas/detonation/test_behavior.py \
  lambdas/hub_ingest/handler.py \
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
# 2.4R adversarial artifact — must POSITIVELY exercise all three capture classes so the
# rework can be proven live (this is the fix for the two prior-FAIL defects):
#  * WRITE a PLANTED, GREPPABLE buffer to a file  -> exercises the now-traced %desc write()
#    (the prior FAIL missed the buffer entirely because %desc was not traced).
#  * REAL connect() via BASH  -> bash supports /dev/tcp so it issues a genuine connect()
#    syscall (the prior FAIL used /bin/sh = dash, which has NO /dev/tcp, so the intent
#    surfaced as a file openat and connect_attempts was 0). Invoke bash explicitly.
#  * file create/delete ops for a fuller filesystem summary.
# The buffer is a fixed marker the human greps for in BOTH the raw trace (must be PRESENT,
# as the write's data arg) and the crossed Hub record (must be ABSENT — never leaks).
cat > /tmp/known_behavior.sh <<'EOF'
#!/bin/bash
# --- WRITE a planted buffer to a file (exercises %desc write capture) ---
printf 'ZTIE-EVIL-BUFFER-DATA-2p4R\n' > /tmp/ztie-write-probe.txt
# --- file create/delete ops ---
for i in 1 2 3 4 5; do echo x > /tmp/ztie-probe-$i.txt; rm -f /tmp/ztie-probe-$i.txt; done
# --- REAL connect() via bash /dev/tcp (fails in the egress-less VPC; the ATTEMPT is the signal) ---
exec 3<>/dev/tcp/93.184.216.34/443 || true
EOF
ENDPOINT=$(aws cloudformation describe-stacks --stack-name ZtieIntakeStack \
  --query "Stacks[0].Outputs[?OutputKey=='IntakeEndpoint'].OutputValue" --output text)
python3 - <<PY
import base64,json
open("/tmp/intake.json","w").write(json.dumps({
  "filename":"known_behavior.sh",
  "content_base64":base64.b64encode(open("/tmp/known_behavior.sh","rb").read()).decode(),
  "content_type":"text/x-shellscript","submitter":"ztie-2.4R-revalidation"}))
PY
pip install awscurl -q 2>/dev/null; awscurl --service execute-api --region us-east-1 \
  -X POST -H 'Content-Type: application/json' -d @/tmp/intake.json "$ENDPOINT"
# -> copy the returned intake_id
# NOTE: bash must be pre-baked on the ubuntu-22.04 golden AMI (it is, by default). If the
# host lacks bash the connect() path won't fire -> that's INCONCLUSIVE for the network DoD,
# not a pass. If you prefer not to rely on the shebang, a socket-opening base binary the AMI
# ships (e.g. `getent hosts` for DNS + a bash /dev/tcp) also exercises connect().
```

**BLOCK 5 — read the derived summary that crossed to the Hub (HUB 641628980935):**
```
aws sts get-caller-identity        # expect 641628980935
INTAKE=<intake_id from BLOCK 4>
TBL=$(aws cloudformation describe-stacks --stack-name ZtieHubTrackingStack \
  --query "Stacks[0].Outputs[?contains(OutputKey,'TrackingTable')].OutputValue" --output text)
aws dynamodb get-item --table-name "$TBL" \
  --key "{\"intake_id\":{\"S\":\"$INTAKE\"}}" --query "Item.behavior" --output json
# expect capture_status=captured, capture_tool=strace, real syscalls/filesystem counts
# INCLUDING filesystem.writes>=1 (the new %desc write capture), network.connect_attempts>=1
# (connected:false), NO verdict field. NOTE the "behavior" attribute is scoped to the
# dynamic-lane record — the DoD-3 verdict-field probe must target THIS attribute, not the
# whole item (the whole item legitimately carries the Phase-3 RD-040 advisory fields).
```

**BLOCK 6 — pull the FULL raw trace from Forensic + prove correspondence (FORENSIC 360999005254):**
```
aws sts get-caller-identity        # expect 360999005254
INTAKE=<intake_id from BLOCK 4>
BKT=$(aws cloudformation describe-stacks --stack-name ZtieIntakeStack \
  --query "Stacks[0].Outputs[?OutputKey=='ArtifactBucketName'].OutputValue" --output text)
aws s3 cp "s3://$BKT/traces/$INTAKE/behavior-trace.txt" /tmp/trace.txt && head -80 /tmp/trace.txt
# --- the 2.4R positive-exercise checks (the prior FAIL missed the first two) ---
grep -c "ZTIE-EVIL-BUFFER-DATA-2p4R" /tmp/trace.txt  # the WRITE BUFFER must be PRESENT (>=1) now that %desc is traced
grep -E "^.*\bwrite\(" /tmp/trace.txt | head          # the write() syscall(s) that carry the buffer
grep -Ec "connect\(" /tmp/trace.txt                   # a REAL connect() must be present (>=1) via bash /dev/tcp
grep -E "connect\(" /tmp/trace.txt | head             # the network-INTENT connect syscall(s)
grep -c "ztie-probe" /tmp/trace.txt                   # the artifact's OWN file create/delete ops present
grep -c "execve" /tmp/trace.txt                       # confirms strace traced the artifact directly
# CROSS-CHECK: the write buffer must be PRESENT in the raw trace but ABSENT from the Hub
# record (BLOCK 5) — proving capture happened AND the raw content never crossed the boundary.
```

**BLOCK 7 — gather the RD-054 retained evidence (save these for Kiro to commit to `docs/validation-evidence/2.4R/`):**
```
# from BLOCK 5: save the Hub behavior record
aws dynamodb get-item --table-name "$TBL" --key "{\"intake_id\":{\"S\":\"$INTAKE\"}}" \
  --query "Item.behavior" --output json > /tmp/2.4R-hub-behavior.json
# from BLOCK 6: keep /tmp/trace.txt (or a representative slice) as the raw trace artifact
head -200 /tmp/trace.txt > /tmp/2.4R-trace-slice.txt
# provenance: intake_id (above) + the POST-FIX main-tip SHA under test (git rev-parse
# origin/main after the 2.4R rework PR merges) ; plus your named+dated attestation that you
# READ /tmp/trace.txt, the write buffer is PRESENT there and ABSENT from the Hub record, and
# the record corresponds to the summary with no verdict field.
```
Paste BLOCK 5 + BLOCK 6 raw outputs back to Gemini for adjudication; hand BLOCK 7's files
+ your attestation + the intake_id/SHA to Kiro on a sealed PASS.

**▶ NEXT (FLOW MAP STEP 4→5):** paste BLOCK 5+6 to Gemini → get the sealed VERDICT → on
PASS, hand the verdict + BLOCK 7 evidence to Kiro (2.4R → ✅). That completes the loop.

> **Parts A, C, D, E below are REFERENCE ONLY** (the expanded fetch details, the roles, the
> limits, and the runbook-output format). They are not additional steps — the FLOW MAP above
> is the sequence, and the paste-to-Gemini prompt is Part 0. Gemini never sees these; only
> Part 0.

---

## Part A — Pull the raw code yourself (YOU run this; do NOT let Kiro curate it)

> **AWS CloudShell note:** the `gh` CLI is NOT available in CloudShell. Pull the raw
> diff with `curl` against the GitHub REST API using a token-authenticated request.
> Set the token WITHOUT echoing it (keeps it off screen + out of history); do NOT paste
> the token into Gemini or the chat:

```
read -rs GH_TOKEN && export GH_TOKEN     # paste the token at the silent prompt, press Enter

# The code under test is the 2.4R REWORK PR (fix/story-2.4R) on top of the original 2.4
# lane (PRs #78 build / #79 strace-wrapper fix). Pull the rework diff (set <REWORK_PR>):
curl -sSL -H "Authorization: Bearer $GH_TOKEN" -H "Accept: application/vnd.github.v3.diff" \
  https://api.github.com/repos/warrenrutledge64/ZTIE-Issues/pulls/<REWORK_PR> | tee /tmp/2.4R-rework.diff | head -c 200

unset GH_TOKEN
```

Copy the **full** diff that prints — that raw code is what Gemini reviews.

> Alternatively, once the rework PR merges, read the files directly in your cloned repo:
> `git -C <repo> show <POST_FIX_MAIN_SHA>` (or `git -C <repo> diff 566e274..<POST_FIX_MAIN_SHA>
> -- lambdas/detonation`), or open the code files below.
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

## Part C — How the loop runs (RD-053 4-stage)

1. **Handoff (Kiro → you):** Kiro gave the objective pointers above and stepped out.
2. **Design (you → Gemini):** you paste Part 0 (fetch commands + your requirement in the
   `<<< WARREN >>>` slot), run the fetch, paste the raw diff + full source back; Gemini
   authors the DoD + runbook.
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
- **Distrust the commands, not just the code (zero-trust on collection).** The commands the
  builder/operator supply are a floor. Gemini is tasked to judge whether each command set
  actually surfaces the evidence — or whether a defect could hide in what it does not
  capture — and to add stronger/corroborating/negative commands. A pass built on a command
  that under-collects (a truncated trace, a one-field query, a grep that misses a family) is
  a pass on incomplete evidence. Run the augmented commands, not just the given ones.


---

## Part E — Runbook output format (FIXED + downloadable)

> Deliverable #7 asks Gemini to emit the live runbook as ONE self-contained fenced block
> in the fixed shape below, so it's identical every time and is a droppable file you save
> and hand to Kiro / push to the Hub. (Gemini can't write files; "download" = copy the one
> block → save-as.)

**The block Gemini returns must look exactly like this (headers fixed):**
```
<!-- FILE: docs/session-briefs/story-2.4R-LIVE-RUNBOOK.md -->
# Story 2.4R — LIVE validation runbook (stakeholder, two CloudShells)

> The ONLY live part of 2.4R; only YOU can run it (executor has no AWS creds). The
> executor records your returned output VERBATIM; nothing on inference.

## Ground rules
- TWO tabs: Forensic 360999005254 (detonate + trace) / Hub 641628980935 (ingest + verify).
- `aws sts get-caller-identity` BEFORE every block; wrong account → switch tabs.
- One line at a time. /tmp wiped on recycle. Region us-east-1, ambient creds.

## STEP 0 — Get the code
   (checkout/reset to the POST-FIX main tip — the main commit after the 2.4R rework PR merges)

## STEP 1..N — numbered live steps
   Each step: ACCOUNT + exact command + literal pass/fail output. Start from Part A2
   BLOCKS 3–6 (redeploy Forensic+Hub, submit known-behavior artifact, read Hub `behavior`
   record, pull + read the Forensic raw trace) but STRENGTHEN them: for each collection
   step Gemini weighs the command's efficacy and adds wider/corroborating/negative commands
   so the evidence can't be truncated, clipped, or gamed — the supplied blocks are a floor.

## Definition of Done
   - positive strace capture (capture_status=captured, real syscalls/filesystem, network
     connect_attempts>=1 INTENT) — count:0/tool_unavailable = INCONCLUSIVE
   - human reads the RAW Forensic trace + it corresponds to the summary, no verdict field
   - retained evidence in docs/validation-evidence/2.4R/ (RD-054)

## Verdict recording
   On PASS: hand the sealed verdict + BLOCK 7 evidence to Kiro → 2.4R ✅.
   INCONCLUSIVE/FAIL → 2.4R stays 🟡; fix + re-run from STEP 3.
```

**Save + hand off (you, in CloudShell):**
1. Copy Gemini's single block.
2. `cat > docs/session-briefs/story-2.4R-LIVE-RUNBOOK.md` → paste → Ctrl-D (the
   `<!-- FILE: ... -->` marker names the path).
3. Upload that file to Kiro, or `git add` + commit it on the 2.4R docs branch and push to
   the Hub. Either way Kiro has the exact, standard-format runbook.
