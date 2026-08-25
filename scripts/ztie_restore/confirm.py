"""The mutation confirm gate (Story 1.R).

Python ``input()``, FAIL-SAFE to NO. This is deliberately Python and not a shell
``read``/``/dev/tty`` prompt: the earlier Bash restore attempt failed on exactly
that (CR/whitespace handling, ``set -e`` interaction, a terminal that wasn't
attached). ``input()`` avoids all of it.

Contract:

- Only an explicit, affirmative reply proceeds. Accepted (case-insensitive, after
  trimming surrounding whitespace incl. a stray trailing CR): ``y``, ``yes``.
- Anything else — empty input, ``n``, ``no``, gibberish, or EOF/no-TTY
  (``EOFError``) — returns NO. There is no default-yes path.
- An environment escape hatch for automated FAIL-SAFE-NO proof:
  ``ZTIE_ASSUME_NO=1`` forces NO without prompting (used to demonstrate the
  gate rejects without a live terminal). There is intentionally NO assume-YES
  env var — the only way to get YES is a human typing it.
"""

from __future__ import annotations

import os

_AFFIRMATIVE = {"y", "yes"}


def _normalise(reply: str) -> str:
    """Trim a trailing CR + surrounding whitespace, lowercase."""
    return reply.strip().strip("\r").strip().lower()


def confirm(prompt: str, *, input_fn=input) -> bool:
    """Return True only on an explicit affirmative reply. Fails safe to NO.

    ``input_fn`` is injectable so the confirmed-YES path can be exercised in tests
    without a real terminal (the hard-won lesson: don't try to drive a real pty).
    """
    if os.environ.get("ZTIE_ASSUME_NO") == "1":
        return False
    try:
        reply = input_fn(f"{prompt} [y/N]: ")
    except EOFError:
        # No terminal / piped-closed stdin -> fail safe to NO.
        return False
    return _normalise(reply) in _AFFIRMATIVE
