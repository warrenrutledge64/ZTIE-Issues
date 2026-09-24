#!/usr/bin/env python3
"""Single entrypoint that regenerates ALL ZTIE data contracts (Story C.3, RD-034).

Before C.3 each contract had its own ``gen_<name>_contract.py`` carrying an
IDENTICAL ``main()`` writer loop — the loop was copy-pasted 10 times. C.3 kept
each contract's ``SCHEMA`` (the genuine per-contract data) in its own module but
collapsed the duplicated *writer* into ``scripts/contract_writer.py`` and added
THIS single generator that drives every contract from one place.

Each per-contract module now exposes two data attributes and a thin ``main()``:
  * ``SCHEMA``    — the JSON Schema dict (unchanged from before C.3).
  * ``OUT_PATHS`` — repo-root-relative output path segment tuples (canonical
    ``schemas/`` copy + every bundled lambda copy that must stay byte-in-sync).
The individual ``gen_<name>_contract.py`` files remain runnable on their own
(their ``main()`` delegates to the shared writer), so nothing that referenced
them by name breaks; this file is the convenient "regenerate everything" driver.

Run:
    python3 scripts/gen_contracts.py            # regenerate every contract
    python3 scripts/gen_contracts.py --list     # list the registered contracts

Stdlib only (no PyPI) so it runs in the INTEGRATIONS_ONLY build sandbox.
"""

from __future__ import annotations

import argparse
import importlib

from contract_writer import resolve_out_paths, write_contract

# The registry of every contract this project generates, in a stable order.
# Each entry is the module name (under scripts/) that defines SCHEMA + OUT_PATHS.
# Adding a new contract = add its gen_<name>_contract module here (and give that
# module a SCHEMA + OUT_PATHS), rather than copy-pasting a whole new writer.
CONTRACT_MODULES = [
    "gen_classification_contract",
    "gen_routing_contract",
    "gen_reject_contract",
    "gen_static_scan_summary_contract",
    "gen_static_findings_contract",
    "gen_dynamic_run_contract",
    "gen_collected_contract",
    "gen_behavior_contract",
    "gen_sanitized_telemetry_contract",
    "gen_combined_event_contract",
    "gen_correlation_contract",
    "gen_scoring_contract",
    "gen_remediation_contract",
    "gen_verdict_contract",
    "gen_status_contract",
    "gen_dashboard_contract",
    "gen_report_contract",
    "gen_handoff_contract",
    "gen_disposition_contract",
    "gen_decision_token_contract",
]


def generate_all() -> None:
    """Regenerate every registered contract using the one shared writer."""

    for module_name in CONTRACT_MODULES:
        module = importlib.import_module(module_name)
        write_contract(module.SCHEMA, resolve_out_paths(module.OUT_PATHS))


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate ZTIE data contracts.")
    parser.add_argument(
        "--list",
        action="store_true",
        help="list the registered contract modules and exit (no files written)",
    )
    args = parser.parse_args()

    if args.list:
        for module_name in CONTRACT_MODULES:
            print(module_name)
        return

    generate_all()


if __name__ == "__main__":
    main()
