# Validation-process UX findings (to be resolved in a dedicated story)

> **Purpose.** A running, durable log of usability / clarity problems the STAKEHOLDER
> hits while running the split-brain validation loop (RD-052/053/054) and its packages.
> These are NOT defects in the code under test and NOT things to fix mid-validation —
> they are friction points in the *validation tooling / instructions* themselves.
>
> **Scribe posture.** Kiro records these observations verbatim as they occur; it does
> NOT fix them during an active validation. They are triaged and resolved together in a
> separate, tracked governance story (a "validation-process UX / hardening" story to be
> scoped later). Each entry below is an input to that story's scope.
>
> **Status:** OPEN backlog — not yet scoped into a story. Do not close entries here; the
> future story references them.

---

## Findings

### VUX-001 — `read -rs GH_TOKEN` appears to "hang"; the silent-no-prompt behavior must be made plain

- **Where:** `docs/session-briefs/story-2.4R-VALIDATION-PACKAGE.md` (Part 0 kickoff block
  STEP 1 + STEP 1.5, and Part A), and `docs/GEMINI_VALIDATION_PACKAGE_TEMPLATE.md`
  wherever the token-fetch snippet appears. Also any other package generated from the
  template.
- **Observed (stakeholder, during Story 2.4R validation):** the very first command,
  `read -rs GH_TOKEN && export GH_TOKEN`, *appears to hang*. The stakeholder asked
  whether it needed to be `export GH_TOKEN="YOUR_TOKEN_HERE"` instead.
- **Actual cause (for the record — NOT a bug in the command):** `read -rs` is *correct*.
  It is silently waiting for the token to be pasted/typed. The `-s` (silent) flag means
  there is **no prompt text and no echo** — nothing appears on screen as you type, so it
  looks frozen. You paste the PAT at the blank line and press **Enter**; then
  `&& export GH_TOKEN` exports the already-set variable for `curl`.
- **Why the alternative is discouraged:** `export GH_TOKEN="..."` works and does not hang,
  but it **echoes the token on screen** and writes it to **shell history** — a leak risk
  (ties to the standing lesson that a PAT echoed into CloudShell output must be rotated).
  The silent `read -rs` form exists specifically to avoid that.
- **The finding (what to resolve in the future story):** this behavior is invisible to
  someone *familiar* with the command and baffling to someone who is not. The packages
  must **make it plain** at the point of use — e.g.:
  - use a visible prompt: `read -rsp "Paste GH token, then press Enter (nothing will show): " GH_TOKEN && export GH_TOKEN && echo`
  - add an inline note: "*This line looks like it hangs — it is silently waiting for you
    to paste the token. Nothing echoes (by design). Paste + Enter.*"
  - add a non-echoing length check to confirm it took: `echo "len=${#GH_TOKEN}"`.
  - keep the fail-safe: still `unset GH_TOKEN` at the end.
- **Do NOT** replace the silent form with an on-screen `export GH_TOKEN="..."` — that would
  trade a UX wrinkle for a real secret-leak regression. Fix is *clarity*, not *removal*.
- **Recorded:** during the Story 2.4R split-brain live validation (scribe: Kiro).
