# How We Work Together - The ZTIE Operating Model (a test-drive runbook)

> **This is a "try it out and learn" document.** It is written for a
> non-technical reader. Its job is to make the way we run this project simple to
> follow, so you can watch the loop work, feel comfortable steering it, and refine
> it as we go. Nothing here changes any status or any record. It explains the
> loop; it does not run it.
>
> Related reading (all links are relative to this file):
> [`../../METHODOLOGY.md`](../../METHODOLOGY.md) (the full method),
> [`../../RUNBOOK.md`](../../RUNBOOK.md) (the live status ledger and source of
> truth), [`../../PROJECT_PLAN.md`](../../PROJECT_PLAN.md) (scope and decisions),
> [`FLOOR_AND_HARVEST_PLAN.md`](FLOOR_AND_HARVEST_PLAN.md) (the current transition
> plan), [`../BUILD_ORDER.md`](../BUILD_ORDER.md) (the picture of what can be built
> when), and [`WORK_LOG.md`](WORK_LOG.md) (the running list of recommendations).

## 1. The one-sentence version

The AI acts as the senior (and only) developer and hands you **one** recommended
next piece of work at a time with a short reason; **you** decide whether to do it,
and we finish that one piece completely and prove it works before anything else
begins.

## 2. Who does what (the two roles)

This project runs on a deliberate split that already lives in
[`../../METHODOLOGY.md`](../../METHODOLOGY.md) §2 (the "executor proposes,
stakeholder decides" split) and is now enforced structurally by the hard-pause
gate that story G-3 installed (recorded as **RD-023** in
[`../../PROJECT_PLAN.md`](../../PROJECT_PLAN.md) §5).

**The AI owns sequencing.** The AI is the senior developer here, and the only one.
It reads the dependency graph (the map of what depends on what, see
[`../BUILD_ORDER.md`](../BUILD_ORDER.md)), notices which pieces are **load-bearing**
(a lot of later work sits on top of them) and which pieces **harden the
foundation**, and from all of that it picks the single best next thing to do. It
then hands you that one recommendation with a one-line reason, in the shape:

> **Next up: X, because Y.**

You are never handed a menu of ten things to juggle. You get one clear proposal at
a time.

**You own the decision.** For each recommendation you have three simple answers:

- **Go**: yes, do this next.
- **Not yet**: hold off (maybe you want to wait, or gather something first).
- **Do Z instead**: you would rather we pick a different piece.

The AI does not silently re-plan around your decision, and you are never asked to
organize the build order yourself. The AI organizes; the dependency graph is the
**AI's tool**, not something you have to operate. Your job is the go / not-yet /
do-Z call, using the plain-language reason the AI gives you.

## 3. The single-threaded rule (one thing at a time, always)

We work on **exactly one** piece of work at a time, start to finish. There is
never a second effort running alongside it. This is the first principle in
[`../../METHODOLOGY.md`](../../METHODOLOGY.md) §1: one story at a time, to
completion, with no half-done work left drifting.

Why this matters for you: you will never be asked to track two things at once, and
you will never be told something is "kind of done." A piece of work is either the
one thing in progress, or it is finished and proven, or it has not started.

## 4. "Parallel" means freedom to choose, not doing two things at once

You will sometimes hear that two pieces of work are "parallel." In this project
that word has a narrow, specific meaning, and it is worth being clear about because
it is easy to misread.

**"Parallel in the dependency graph" only means the two pieces have no dependency
between them, so the AI is free to choose which to do first.** It does **not** mean
we run them at the same time. With a single developer we never run two efforts at
the same wall-clock moment. Two "parallel" pieces simply collapse into a chosen
order: the AI picks one to do first, we finish it, then we do the other. You are
never asked to run two efforts at once.

A concrete example from this project: stories 2.0 and 2.1 both depend only on story
1.3, and neither depends on the other, so they are **independent siblings**. That
made them "parallel" in the graph. In practice we did 2.1 first (it is now
finished), and 2.0 is still waiting. Same order, one at a time. See
[`../BUILD_ORDER.md`](../BUILD_ORDER.md) for the full picture.

## 5. How one cycle runs, start to finish

Every cycle has the same simple shape:

1. **The AI recommends one piece of work, with a reason.** "Next up: X, because Y."
2. **You decide:** go / not yet / do Z instead.
3. **On "go," the AI builds it.** One piece, to completion. The code goes onto a
   branch and is opened for review; merging the code does **not** make it done.
4. **We validate it live.** The real thing is checked on the real system. In this
   project the live checks are **your** action (you have the live access; the AI
   does not), and the AI records exactly what you confirm. Nothing is ever marked
   done on a guess. This is the covenant in
   [`../../METHODOLOGY.md`](../../METHODOLOGY.md) §4: nothing is "done" on
   inference.
5. **We record the result and update the status** using the **existing Story
   Close-Out Procedure** in [`../../RUNBOOK.md`](../../RUNBOOK.md). That procedure
   uses two separate commits on purpose:
   - **Commit A, the work.** The piece is built; its status stays **🟡 In
     Progress**. Building it is not the same as proving it.
   - **Commit B, the status flip.** Only after you confirm a live pass does a
     small, dedicated commit flip the status to **✅ Done (validated)** and record
     the dated result.
6. **The AI brings the next recommendation**, and the cycle repeats.

If the live check **fails**, nothing flips to done. The piece stays 🟡 and the next
cycle re-focuses on fixing and re-validating that same piece. We do not move on.

## 6. The safety rails that keep this honest

Two structural rails, both already built into the project, keep the loop from
drifting:

- **The Validation Debt Register** (at the top of
  [`../../RUNBOOK.md`](../../RUNBOOK.md)) lists every piece that has been built but
  never proven live. Today it holds exactly one entry: **story 2.0**.
- **The Advancement Gate** (RUNBOOK's "Validation & Advancement Gate," and
  [`../../METHODOLOGY.md`](../../METHODOLOGY.md) §4) says: **no new feature work may
  begin while that register has any entry in it.** Reworking or validating the
  open entry is allowed and encouraged, because that is exactly how the register
  gets cleared. This is checked automatically by
  [`../../scripts/check_docs.py`](../../scripts/check_docs.py), so it cannot be
  skipped by accident.

Put simply: while something built-but-unproven is sitting there, the AI will keep
steering you back to proving it before piling anything new on top. That is the
system working as designed, not a delay.

## 7. Quality and hardness over speed

The AI justifies its recommendations by **risk and hardening value**, not by how
fast we could tick boxes. The goal is to protect the load-bearing foundation before
anything dangerous lands on top of it. When the AI says "next up: X," the reason
"Y" will be about **why doing X now reduces risk or strengthens the foundation**,
not about which option is quickest. A slower, sturdier order beats a fast, fragile
one every time.

## 8. A tiny worked example (our real first cycle)

Here is one full cycle, using the actual first recommendation:

1. **AI recommends:** "Next up: validate and harden **story 2.0** (the containment
   wall), because it is the single built-but-unproven piece and everything
   dangerous in Phase 2 (the detonation work) will sit directly on top of it."
2. **You decide:** go / not yet / do Z instead. (This is a proposal awaiting your
   call; see [`WORK_LOG.md`](WORK_LOG.md).)
3. **On "go," we validate 2.0 live.** You run its checks on the real Forensic
   account, following the 7 checks already written in
   [`FLOOR_AND_HARVEST_PLAN.md`](FLOOR_AND_HARVEST_PLAN.md) §6. The AI records what
   you confirm.
4. **We record and flip status** via the Story Close-Out Procedure: the result is
   written into story 2.0's record, its status flips 🟡 → ✅, and the 2.0 entry
   leaves the Validation Debt Register.
5. **The AI brings the next recommendation**, and the register being empty re-opens
   new feature work under the gate.

The full reasoning for this first recommendation lives in
[`WORK_LOG.md`](WORK_LOG.md), and it lines up with the earlier hand-off note in
[`../session-briefs/story-A.2-brief.md`](../session-briefs/story-A.2-brief.md)
(story A.2 is "validate 2.0 live").

## 9. How we will know it is working (what to watch for)

Signs the model is working:

- You are only ever holding **one** decision at a time, and each comes with a plain
  reason.
- Nothing is marked done until you have confirmed it live; the status ledger in
  [`../../RUNBOOK.md`](../../RUNBOOK.md) never claims something you have not seen
  work.
- The Validation Debt Register trends toward empty, and new work does not start
  while it has an entry.
- [`../../scripts/check_docs.py`](../../scripts/check_docs.py) keeps passing, which
  means the register and the gate are internally consistent.

Things to watch for (gentle warning signs):

- A recommendation whose reason is "because it is faster" rather than "because it
  reduces risk": push back and ask for the risk reasoning.
- Any suggestion to mark something done before you have confirmed it live: that is
  exactly the drift this system exists to prevent.
- More than one thing "in progress" at once: there should only ever be one.

## 10. A note on registering this as a decision

Because this operating model is durable and referenceable (the same reason the
hard-pause gate was recorded as **RD-023**), it is recorded as a candidate
registered decision, **RD-024** (status: proposed), in
[`../../PROJECT_PLAN.md`](../../PROJECT_PLAN.md) §5. That entry captures the
single-threaded, AI-recommends / stakeholder-decides loop described here so it can
be referenced and ratified rather than re-litigated each session. Recording RD-024
in the plan does **not** change any story status and does not clear any validation
debt; it simply writes down the way we have agreed to work.
