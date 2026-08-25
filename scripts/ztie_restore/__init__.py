"""ZTIE state-capture + coordinated-restore tooling (Story 1.R).

A Python-first restore-point mechanism for the ZTIE pipeline. The public surface
is the CLI in :mod:`ztie_restore.cli`; the building blocks are:

- :mod:`ztie_restore.projection` — the restore-relevant projection model. Defines
  EXACTLY which identity + desired-state fields are captured per resource type.
  This is the contract everything else is written against (projection-first, the
  lesson carried from Story 1.1R).
- :mod:`ztie_restore.capture` — read-only capture of the live projection into a
  timestamped manifest.
- :mod:`ztie_restore.restore` — coordinated restore that re-applies a manifest,
  gated behind a deliberate ``input()`` confirm that fails safe to NO.
- :mod:`ztie_restore.verify` — compares the live projection against a manifest,
  ignoring volatile metadata that legitimately changes on any successful deploy.

Design invariants (Story 1.R / RD-012 / RD-013 / RD-015):

1. Capture is READ-ONLY. The only mutating action is restore, behind the confirm.
2. Verify compares a PROJECTION, never raw resource objects — volatile metadata
   (SSM version bumps, CFN CREATE-vs-UPDATE status, last_updated_utc, stack_id on
   recreate, Lambda list ordering) would otherwise false-positive as drift.
3. CloudFormation restore re-applies stack-level TAGS, not just template +
   parameters, or the restored stack loses its tags and correctly fails verify.
4. The manifest PINS the known-good governance-doc commit so code + state +
   governance restore as ONE unit (RD-015).
"""

from __future__ import annotations

__all__ = ["MANIFEST_SCHEMA_VERSION"]

# Bumped only when the manifest projection shape changes in a breaking way.
MANIFEST_SCHEMA_VERSION = "1.0"
