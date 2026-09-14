"""ZTIE Story 2.2 — finding -> compliance-control mapping (PURE logic).

This module maps a normalized static finding (its ``tool`` + native ``rule_id``) to
the security-framework control(s) it IMPLICATES — NIST SP 800-53 Rev 5 (the control
catalog of record) and ISO/IEC 27001:2022 Annex A (RD-004 / RD-014 framework scope).
The result is attached to each finding as a bounded ``compliance`` sub-object so a
violation is traceable to a framework control for the Phase-3 correlation and the
Phase-4 Security-tier report (RD-006).

Distinction from RD-014 / Story G-1 (do NOT conflate):
  * G-1 maps ZTIE's OWN design artifacts to controls (project self-audit,
    ``docs/COMPLIANCE.md``). This module does NOT touch that matrix.
  * Story 2.2 maps the SCANNED ARTIFACT'S findings to controls — the product ZTIE
    emits ABOUT a customer artifact. This is a runtime finding enrichment.

Design (the 2.1 lesson — pure logic + a thin seam; this is pure):
  * PURE. No boto3, no I/O, no subprocess. Offline-testable with stdlib ``unittest``.
  * EVIDENCE, NEVER A VERDICT. A control mapping says "this finding implicates
    control X"; it NEVER says "this artifact fails / is unsafe". No verdict / safe /
    approved / forward field. The verdict is Hub-side / human-gated (Phase 4).
  * CANDIDATE-vs-RATIFIED (mirrors RD-014). Every emitted mapping carries a
    ``basis`` that is ``ratified`` when it came from an accountable-reviewer-ratified
    entry in the mapping table, or ``proposed`` when it is a candidate (authored,
    not yet reviewed). ZTIE does not overclaim: an unmatched finding gets an EMPTY
    control list with ``basis: unmapped`` rather than a fabricated control.
  * REAL, NON-MOCK SOURCE. The mapping table is a curated correspondence between the
    scanners' own rule catalogues (cfn-lint / cfn-guard / checkov / bandit rule ids
    and the ZTIE signature families) and the two frameworks. It is data, not a guess
    per-run; it is versioned with the code and reviewed via PR.
  * BOUNDED. Control-id strings are short and length-capped; the per-finding control
    lists are capped so a finding cannot carry an unbounded mapping.
"""

from __future__ import annotations

from typing import Any

# Mapping-source version. Bumped when the correspondence table changes materially,
# so a stored finding's mapping is traceable to the exact table that produced it.
MAPPING_VERSION = "2026-09-03"

# The frameworks in scope (RD-014). These are the only mapping keys emitted.
FRAMEWORK_NIST = "nist_800_53"
FRAMEWORK_ISO = "iso_27001"

# candidate-vs-ratified discipline (RD-014). Until an accountable compliance
# reviewer ratifies the table, every mapping ZTIE emits is a candidate.
BASIS_RATIFIED = "ratified"
BASIS_PROPOSED = "proposed"
BASIS_UNMAPPED = "unmapped"

# Bounds (mirror the findings contract's compliance sub-object caps).
_CONTROL_ID_MAX = 32
_CONTROLS_PER_FRAMEWORK_MAX = 8
_RATIONALE_MAX = 512


# --- The correspondence table ------------------------------------------------
# Keyed by (tool, key) where key is either an exact native rule_id or a PREFIX
# (checkov's CKV_* families, bandit's Bnnn families, cfn-lint's E/W ladders) so a
# whole rule family maps without enumerating every id. Values are the controls the
# rule IMPLICATES + a short rationale. All entries are candidate (proposed) until
# an accountable reviewer ratifies them; the table is the single source and is
# reviewed via PR (RD-015). ISO ids are Annex A 2022; NIST ids are SP 800-53 Rev 5.
#
# A finding is matched by: (a) exact (tool, rule_id); else (b) the longest matching
# (tool, prefix); else it is UNMAPPED (empty controls, basis=unmapped) — ZTIE never
# fabricates a control it cannot justify.

# Each entry: {"nist": [...], "iso": [...], "rationale": str, "ratified": bool}
_TABLE: dict[str, dict[str, dict[str, Any]]] = {
    # --- checkov (iac_misconfig) — CKV_* families keyed by prefix. ----------
    "checkov": {
        # Encryption at rest (S3/EBS/RDS/etc.). SC-28 protection of info at rest.
        "CKV_AWS_ENCRYPTION": {
            "nist": ["SC-28", "SC-13"],
            "iso": ["A.8.24", "A.5.33"],
            "rationale": "Encryption-at-rest misconfiguration implicates protection of information at rest and use of cryptography.",
            "ratified": False,
        },
        # Public access / open to the world. AC-3 access enforcement, SC-7 boundary.
        "CKV_AWS_PUBLIC": {
            "nist": ["AC-3", "SC-7", "AC-6"],
            "iso": ["A.8.3", "A.5.15"],
            "rationale": "Public-exposure misconfiguration implicates access enforcement and boundary protection.",
            "ratified": False,
        },
        # Logging / audit not enabled. AU-2 event logging.
        "CKV_AWS_LOGGING": {
            "nist": ["AU-2", "AU-12"],
            "iso": ["A.8.15", "A.8.16"],
            "rationale": "Disabled logging/audit implicates event logging and audit record generation.",
            "ratified": False,
        },
        # Generic checkov AWS misconfiguration — configuration management baseline.
        "CKV_AWS": {
            "nist": ["CM-6", "CM-2"],
            "iso": ["A.8.9"],
            "rationale": "IaC misconfiguration implicates secure configuration settings and a configuration baseline.",
            "ratified": False,
        },
        # Secret detected by checkov's secrets framework. IA-5 authenticator mgmt.
        "CKV_SECRET": {
            "nist": ["IA-5", "SC-28"],
            "iso": ["A.5.17", "A.8.24"],
            "rationale": "A hardcoded secret implicates authenticator management and protection of stored credentials.",
            "ratified": False,
        },
        # Any other checkov family (CKV2_*, CKV_GIT_*, etc.).
        "CKV": {
            "nist": ["CM-6"],
            "iso": ["A.8.9"],
            "rationale": "Policy/config finding implicates secure configuration settings.",
            "ratified": False,
        },
    },
    # --- cfn-guard (policy_as_code) — ZTIE baseline.guard rule names. -------
    # These are the exact rule ids in guard-rules/baseline.guard.
    "cfn-guard": {
        "S3_BUCKET_PUBLIC_ACCESS_BLOCK": {
            "nist": ["AC-3", "SC-7", "AC-6"],
            "iso": ["A.8.3", "A.5.15"],
            "rationale": "Missing S3 public-access-block implicates access enforcement and boundary protection.",
            "ratified": False,
        },
        "S3_BUCKET_NO_PUBLIC_ACL": {
            "nist": ["AC-3", "AC-6"],
            "iso": ["A.8.3"],
            "rationale": "Public/authenticated-read ACL implicates access enforcement and least privilege.",
            "ratified": False,
        },
        "S3_BUCKET_ENCRYPTION": {
            "nist": ["SC-28", "SC-13"],
            "iso": ["A.8.24", "A.5.33"],
            "rationale": "Missing bucket encryption implicates protection of information at rest.",
            "ratified": False,
        },
        "EBS_VOLUME_ENCRYPTED": {
            "nist": ["SC-28", "SC-13"],
            "iso": ["A.8.24"],
            "rationale": "Unencrypted EBS volume implicates protection of information at rest.",
            "ratified": False,
        },
        "SG_NO_UNRESTRICTED_INGRESS": {
            "nist": ["SC-7", "AC-4", "CM-7"],
            "iso": ["A.8.20", "A.8.22"],
            "rationale": "0.0.0.0/0 ingress implicates boundary protection, flow enforcement and least functionality.",
            "ratified": False,
        },
        "IAM_NO_WILDCARD_ADMIN": {
            "nist": ["AC-6", "AC-3"],
            "iso": ["A.5.15", "A.8.2"],
            "rationale": "Action:* on Resource:* implicates least privilege and access enforcement.",
            "ratified": False,
        },
    },
    # --- cfn-lint (iac_lint) — E (error) and W (warning) ladders by prefix. -
    "cfn-lint": {
        # Security-relevant lint families (E1/E2/E3 property + IAM/security checks).
        "E": {
            "nist": ["CM-6", "SA-11"],
            "iso": ["A.8.9", "A.8.28"],
            "rationale": "Template error implicates secure configuration and developer testing/evaluation.",
            "ratified": False,
        },
        "W": {
            "nist": ["CM-6"],
            "iso": ["A.8.9"],
            "rationale": "Template warning implicates secure configuration settings.",
            "ratified": False,
        },
    },
    # --- bandit (sast) — Bnnn test ids by family prefix. --------------------
    "bandit": {
        # B1xx misc (assert, exec, hardcoded bindings). B105-107 hardcoded pw.
        "B105": {
            "nist": ["IA-5"],
            "iso": ["A.5.17"],
            "rationale": "Hardcoded password implicates authenticator management.",
            "ratified": False,
        },
        "B106": {
            "nist": ["IA-5"],
            "iso": ["A.5.17"],
            "rationale": "Hardcoded password argument implicates authenticator management.",
            "ratified": False,
        },
        "B107": {
            "nist": ["IA-5"],
            "iso": ["A.5.17"],
            "rationale": "Hardcoded password default implicates authenticator management.",
            "ratified": False,
        },
        # B3xx blocklist calls (eval, pickle, subprocess, etc.).
        "B602": {
            "nist": ["SI-10", "CM-7"],
            "iso": ["A.8.28"],
            "rationale": "subprocess with shell=True implicates input validation and secure coding.",
            "ratified": False,
        },
        "B605": {
            "nist": ["SI-10", "CM-7"],
            "iso": ["A.8.28"],
            "rationale": "os.system / shell execution implicates input validation and secure coding.",
            "ratified": False,
        },
        "B303": {
            "nist": ["SC-13"],
            "iso": ["A.8.24"],
            "rationale": "Weak/insecure hash implicates use of cryptography.",
            "ratified": False,
        },
        "B501": {
            "nist": ["SC-8", "SC-13"],
            "iso": ["A.8.24"],
            "rationale": "Disabled certificate validation implicates transmission confidentiality/integrity.",
            "ratified": False,
        },
        # Any other bandit test — generic SAST -> secure coding + dev testing.
        "B": {
            "nist": ["SA-11", "SI-10"],
            "iso": ["A.8.28"],
            "rationale": "SAST finding implicates developer security testing and secure coding.",
            "ratified": False,
        },
    },
    # --- gitleaks (signature) — Story 2.2G secret scanner. ------------------
    # EVERY gitleaks finding is a detected secret/credential (that is all gitleaks
    # reports), so the whole tool maps to the same SECRET controls the superseded
    # ZTIE signature SECRET family used. gitleaks' native rule ids vary
    # (aws-access-token, generic-api-key, github-pat, private-key, ...); they all
    # implicate authenticator management + protection of stored credentials, so a
    # single tool-level entry is honest and avoids enumerating gitleaks' ruleset.
    # ``map_finding`` resolves gitleaks via this GITLEAKS_SECRET key (below).
    "gitleaks": {
        "GITLEAKS_SECRET": {
            "nist": ["IA-5", "SC-28"],
            "iso": ["A.5.17", "A.8.24"],
            "rationale": "A detected secret/credential implicates authenticator management and protection of stored credentials.",
            "ratified": False,
        },
    },
    # --- signature-scan (signature) — ZTIE signature families. --------------
    # Keyed by the signature rule_id families emitted by signatures.py.
    "signature-scan": {
        "SECRET": {
            "nist": ["IA-5", "SC-28"],
            "iso": ["A.5.17", "A.8.24"],
            "rationale": "A detected secret/credential implicates authenticator management and protection of stored credentials.",
            "ratified": False,
        },
        "MALWARE": {
            "nist": ["SI-3"],
            "iso": ["A.8.7"],
            "rationale": "A known-bad / malware pattern implicates malicious-code protection.",
            "ratified": False,
        },
        "DANGEROUS": {
            "nist": ["SI-10", "CM-7"],
            "iso": ["A.8.28"],
            "rationale": "A dangerous code pattern implicates input validation and secure coding.",
            "ratified": False,
        },
        # Any other signature family.
        "SIG": {
            "nist": ["SI-3"],
            "iso": ["A.8.7"],
            "rationale": "A signature match implicates malicious-code protection.",
            "ratified": False,
        },
    },
}


def _bounded_controls(ids: Any) -> list[str]:
    """Coerce to a bounded, de-duplicated list of short control-id strings."""
    out: list[str] = []
    if not isinstance(ids, (list, tuple)):
        return out
    for cid in ids:
        if not isinstance(cid, str):
            continue
        c = cid.strip()[:_CONTROL_ID_MAX]
        if c and c not in out:
            out.append(c)
        if len(out) >= _CONTROLS_PER_FRAMEWORK_MAX:
            break
    return out


def _lookup(tool: str, rule_id: str) -> dict[str, Any] | None:
    """Find the best table entry for (tool, rule_id): exact id, else the longest
    matching prefix, else None. Never raises."""
    table = _TABLE.get(tool)
    if not isinstance(table, dict):
        return None
    if not isinstance(rule_id, str):
        return None
    rid = rule_id.strip()
    if rid in table:
        return table[rid]
    # Longest-prefix match so a specific family (e.g. CKV_AWS_ENCRYPTION) wins over
    # a general one (CKV_AWS, then CKV). Prefixes here are matched
    # case-sensitively against the rule id text; for checkov the synthetic family
    # keys (CKV_AWS_ENCRYPTION/PUBLIC/LOGGING/SECRET) are resolved by the caller in
    # ``map_finding`` via keyword hints, so here we only do straight prefixing.
    best_key = None
    for key in table:
        if rid.startswith(key) and (best_key is None or len(key) > len(best_key)):
            best_key = key
    return table[best_key] if best_key is not None else None


# checkov rule ids do not encode their topic (CKV_AWS_20 could be anything), so we
# additionally classify a checkov/signature finding into a synthetic family using
# keyword hints from its message. This keeps the table small and honest (a mapping
# is only asserted when the topic is recognizable), and anything unrecognized falls
# through to the generic family or UNMAPPED.
_CHECKOV_TOPIC_HINTS = (
    ("CKV_SECRET", ("secret", "credential", "hardcoded", "access key", "private key")),
    ("CKV_AWS_ENCRYPTION", ("encrypt", "kms", "sse", "at rest")),
    ("CKV_AWS_PUBLIC", ("public", "0.0.0.0", "publicly", "internet")),
    ("CKV_AWS_LOGGING", ("logging", "log ", "audit", "cloudtrail", "access log")),
)


def _checkov_family(rule_id: str, message: str) -> str:
    """Pick a checkov synthetic family from message keywords, else fall to the
    generic CKV_AWS / CKV family by rule-id prefix."""
    text = (message or "").lower()
    for family, hints in _CHECKOV_TOPIC_HINTS:
        if any(h in text for h in hints):
            return family
    if isinstance(rule_id, str) and rule_id.startswith("CKV_AWS"):
        return "CKV_AWS"
    return "CKV"


def _signature_family(rule_id: str) -> str:
    """Signature rule ids are ``ZTIE-SIG-<FAMILY>-nnn``; the FAMILY token selects
    the mapping. Fall back to the generic SIG family."""
    if isinstance(rule_id, str):
        parts = rule_id.split("-")
        if len(parts) >= 3 and parts[0] == "ZTIE" and parts[1] == "SIG":
            fam = parts[2].upper()
            if fam in _TABLE["signature-scan"]:
                return fam
    return "SIG"


def map_finding(tool: str, rule_id: str, message: str = "") -> dict[str, Any]:
    """Return the bounded ``compliance`` sub-object for one finding.

    Shape (matches the findings contract v1.1 ``compliance`` sub-object):
        {
          "nist_800_53": ["SC-28", ...],   # bounded, may be empty
          "iso_27001":   ["A.8.24", ...],  # bounded, may be empty
          "basis": "ratified" | "proposed" | "unmapped",
          "mapping_version": "<date>",
          "rationale": "<bounded inert text>"  # present only when mapped
        }

    EVIDENCE, NEVER A VERDICT: this never asserts the artifact fails — only which
    control(s) the finding implicates. UNMAPPED (empty lists, basis=unmapped) when
    no honest mapping exists — ZTIE does not fabricate a control.
    """
    entry: dict[str, Any] | None
    if tool == "checkov":
        entry = _TABLE["checkov"].get(_checkov_family(rule_id, message))
    elif tool == "signature-scan":
        entry = _TABLE["signature-scan"].get(_signature_family(rule_id))
    elif tool == "gitleaks":
        # Story 2.2G — every gitleaks finding is a secret; map the whole tool to the
        # SECRET controls regardless of gitleaks' native rule id.
        entry = _TABLE["gitleaks"]["GITLEAKS_SECRET"]
    else:
        entry = _lookup(tool, rule_id)

    if entry is None:
        return {
            FRAMEWORK_NIST: [],
            FRAMEWORK_ISO: [],
            "basis": BASIS_UNMAPPED,
            "mapping_version": MAPPING_VERSION,
        }

    nist = _bounded_controls(entry.get("nist"))
    iso = _bounded_controls(entry.get("iso"))
    if not nist and not iso:
        return {
            FRAMEWORK_NIST: [],
            FRAMEWORK_ISO: [],
            "basis": BASIS_UNMAPPED,
            "mapping_version": MAPPING_VERSION,
        }
    basis = BASIS_RATIFIED if entry.get("ratified") else BASIS_PROPOSED
    compliance: dict[str, Any] = {
        FRAMEWORK_NIST: nist,
        FRAMEWORK_ISO: iso,
        "basis": basis,
        "mapping_version": MAPPING_VERSION,
    }
    rationale = entry.get("rationale")
    if isinstance(rationale, str) and rationale:
        compliance["rationale"] = rationale[:_RATIONALE_MAX]
    return compliance


def enrich_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach a ``compliance`` sub-object to every finding IN PLACE and return the
    list. A finding already carries tool + rule_id + message from normalization.
    Never raises on an odd finding (missing keys map to UNMAPPED)."""
    for f in findings:
        if not isinstance(f, dict):
            continue
        f["compliance"] = map_finding(
            f.get("tool", ""), f.get("rule_id", ""), f.get("message", "")
        )
    return findings


# --- Summary roll-up ---------------------------------------------------------

# The summary (crossed to the Hub) carries a BOUNDED compliance roll-up: how many
# findings implicated each distinct control, per framework, plus how many were
# unmapped. No finding text / rationale crosses — only counts keyed by control id.
_ROLLUP_CONTROLS_MAX = 200


def build_compliance_rollup(findings: list[dict[str, Any]]) -> dict[str, Any]:
    """Derive the bounded compliance roll-up for the crossed summary.

    Shape (matches the summary contract v1.1 ``compliance`` object):
        {
          "nist_800_53": {"SC-28": 3, "AC-3": 1, ...},  # control id -> count
          "iso_27001":   {"A.8.24": 3, ...},
          "mapped_findings": <int>,
          "unmapped_findings": <int>,
          "mapping_version": "<date>"
        }

    Counts are bounded (control maps capped); no finding text crosses. This is
    EVIDENCE roll-up, never a verdict.
    """
    nist_counts: dict[str, int] = {}
    iso_counts: dict[str, int] = {}
    mapped = 0
    unmapped = 0
    for f in findings:
        if not isinstance(f, dict):
            continue
        comp = f.get("compliance")
        if not isinstance(comp, dict) or comp.get("basis") == BASIS_UNMAPPED:
            unmapped += 1
            continue
        mapped += 1
        for cid in comp.get(FRAMEWORK_NIST, []) or []:
            if isinstance(cid, str) and len(nist_counts) < _ROLLUP_CONTROLS_MAX:
                nist_counts[cid] = nist_counts.get(cid, 0) + 1
            elif isinstance(cid, str) and cid in nist_counts:
                nist_counts[cid] += 1
        for cid in comp.get(FRAMEWORK_ISO, []) or []:
            if isinstance(cid, str) and len(iso_counts) < _ROLLUP_CONTROLS_MAX:
                iso_counts[cid] = iso_counts.get(cid, 0) + 1
            elif isinstance(cid, str) and cid in iso_counts:
                iso_counts[cid] += 1
    return {
        FRAMEWORK_NIST: nist_counts,
        FRAMEWORK_ISO: iso_counts,
        "mapped_findings": mapped,
        "unmapped_findings": unmapped,
        "mapping_version": MAPPING_VERSION,
    }
