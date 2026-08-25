"""ZTIE Story 1.2 — preprocessor classifier (PURE logic).

Given (filename, content bytes) for one intake artifact, classify it as one of a
small closed set: ``iac_template`` (CloudFormation / Terraform / other IaC),
``raw_script`` (shell / python / javascript / ... source), or ``other_unknown``.

Design (from the 1.R / 1.1R lessons):

  * PURE FUNCTION. No boto3, no S3, no I/O. It takes bytes + a filename and
    returns a plain dict shaped by ``schemas/classification.contract.v1.json``
    (minus the envelope keys, which the wiring layer stamps: intake_id, sha256,
    classified_at, contract_version). This is why it is unit-testable with stdlib
    ``unittest`` in the INTEGRATIONS_ONLY sandbox with no PyPI.
  * DISTRUST-THE-CLAIM. The filename extension is UNTRUSTED (the intake body is
    stored octet-stream with the claimed type kept only as metadata, per 1.1). We
    compute an *extension signal* and a *content signal* INDEPENDENTLY, record
    BOTH, and when they disagree the CONTENT signal is authoritative.
  * ZERO-TRUST BOUNDARY. This produces a LABEL only. It never marks an artifact
    safe, never decides a verdict, and never decides a route. Verdict is Hub-side /
    human-gated (Phase 4); routing is Story 1.3.
  * PRODUCTION CODE. Real structural sniffing (magic bytes / anchored structural
    cues), real handling of binary / empty / undecodable input, bounded work
    (only a head slice is inspected).
"""

from __future__ import annotations

import re
from typing import Any

# --- Class + signal vocabulary (must match the contract enums) ---------------

IAC_TEMPLATE = "iac_template"
RAW_SCRIPT = "raw_script"
OTHER_UNKNOWN = "other_unknown"
# A per-signal detector may also decline to guess.
SIGNAL_NONE = "none"

# Only this many bytes of the head are structurally inspected. Classification is
# a cheap triage step; it does not need (and must not attempt) to read a whole
# multi-megabyte artifact. Structural cues for IaC/scripts appear early.
_HEAD_BYTES = 65536

# --- Extension signal --------------------------------------------------------
# The extension is a HINT ONLY (untrusted). These maps are intentionally small
# and explicit; an unrecognised extension yields SIGNAL_NONE, never a guess.

_IAC_EXTENSIONS = {
    "tf": "terraform",
    "tfvars": "terraform",
    "hcl": "hcl",
    # CloudFormation is commonly .yaml/.yml/.json/.template — but those extensions
    # are ambiguous (a .json/.yaml can be anything), so we do NOT map them to IaC
    # by extension alone. Content inspection carries CloudFormation. Only the
    # unambiguous IaC extensions are mapped here.
    "template": "cfn-ext",
}

_SCRIPT_EXTENSIONS = {
    "sh": "shell",
    "bash": "shell",
    "zsh": "shell",
    "ksh": "shell",
    "py": "python",
    "rb": "ruby",
    "pl": "perl",
    "php": "php",
    "js": "javascript",
    "mjs": "javascript",
    "cjs": "javascript",
    "ts": "typescript",
    "ps1": "powershell",
    "bat": "batch",
    "cmd": "batch",
}

# Ambiguous data extensions: recognised, but NOT decisive on their own. They mean
# "content must decide" — an extension signal of NONE with the extension recorded.
_AMBIGUOUS_EXTENSIONS = {"json", "yaml", "yml"}


def _split_extension(filename: str | None) -> str | None:
    """Lowercased extension (without dot), or None if the name has none."""
    if not filename:
        return None
    base = filename.rsplit("/", 1)[-1]
    if "." not in base:
        return None
    ext = base.rsplit(".", 1)[-1].strip().lower()
    if not ext or len(ext) > 32 or not re.fullmatch(r"[a-z0-9]+", ext):
        return None
    return ext


def extension_signal(filename: str | None) -> dict[str, Any]:
    """Classify by the (untrusted) filename extension alone.

    Returns {"artifact_class": <SIGNAL_*>, ["extension": <ext>]}.
    """
    ext = _split_extension(filename)
    signal: dict[str, Any] = {"artifact_class": SIGNAL_NONE}
    if ext is None:
        return signal
    signal["extension"] = ext
    if ext in _IAC_EXTENSIONS:
        signal["artifact_class"] = IAC_TEMPLATE
    elif ext in _SCRIPT_EXTENSIONS:
        signal["artifact_class"] = RAW_SCRIPT
    # Ambiguous (json/yaml/yml) or unrecognised: record the ext, decline to guess.
    return signal


# --- Content signal ----------------------------------------------------------

# A leading UTF-8/UTF-16 BOM is tolerated before decoding.
_BOMS = (b"\xef\xbb\xbf", b"\xff\xfe", b"\xfe\xff")

# Bytes that strongly indicate a NON-text binary (so: other_unknown, never a
# script/template). Checked on the raw head slice before any text decode.
_BINARY_MAGICS: tuple[tuple[bytes, str], ...] = (
    (b"\x7fELF", "elf-binary"),
    (b"MZ", "pe-binary"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpeg"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
    (b"%PDF-", "pdf"),
    (b"PK\x03\x04", "zip-archive"),  # also docx/jar/zip
    (b"\x1f\x8b", "gzip"),
    (b"BZh", "bzip2"),
    (b"\xfd7zXZ\x00", "xz"),
    (b"\x00\x00\x01\x00", "ico"),
)

# Interpreter names recognised in a shebang -> raw_script.
_SHEBANG_INTERPRETERS = (
    "sh",
    "bash",
    "zsh",
    "ksh",
    "dash",
    "python",
    "python2",
    "python3",
    "perl",
    "ruby",
    "node",
    "php",
    "pwsh",
    "env",
)

# Anchored structural cues for a raw script body (checked against decoded text).
# Each is (compiled regex, short non-executable indicator label).
_SCRIPT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^\s*def\s+\w+\s*\(", re.MULTILINE), "python:def"),
    (re.compile(r"^\s*import\s+\w", re.MULTILINE), "python:import"),
    (re.compile(r"^\s*from\s+[\w.]+\s+import\s", re.MULTILINE), "python:from-import"),
    (re.compile(r"^\s*function\s+\w+\s*\(", re.MULTILINE), "js:function"),
    (re.compile(r"\bconst\s+\w+\s*=|\blet\s+\w+\s*=|\bvar\s+\w+\s*=", re.MULTILINE), "js:declaration"),
    (re.compile(r"\brequire\s*\(\s*['\"]", re.MULTILINE), "js:require"),
    (re.compile(r"^\s*(?:export\s+)?(?:async\s+)?function\b", re.MULTILINE), "js:export-function"),
    (re.compile(r"^\s*(?:if|for|while)\b.*;\s*then\b|^\s*fi\s*$|^\s*done\s*$", re.MULTILINE), "shell:control"),
    (re.compile(r"^\s*echo\s+", re.MULTILINE), "shell:echo"),
)


def _decode_head(head: bytes) -> str | None:
    """Best-effort UTF-8 decode of the head slice (after stripping a BOM).

    Returns None if the bytes are clearly not text (undecodable, or contains NUL).
    """
    for bom in _BOMS:
        if head.startswith(bom):
            head = head[len(bom) :]
            break
    # A NUL byte in the head is a strong non-text signal.
    if b"\x00" in head:
        return None
    try:
        return head.decode("utf-8")
    except UnicodeDecodeError:
        # Try a lenient latin-1 pass only to sniff structure; if it still looks
        # non-textual (high ratio of control chars) treat as binary.
        text = head.decode("latin-1", errors="replace")
        control = sum(1 for c in text if ord(c) < 9 or (13 < ord(c) < 32))
        if text and control / len(text) > 0.05:
            return None
        return text


def _looks_like_json_object(text: str) -> bool:
    stripped = text.lstrip()
    return stripped.startswith(("{", "["))


def _cfn_content_signal(text: str) -> str | None:
    """Return a CloudFormation indicator label if the text is a CFN template."""
    # The strongest CFN cue, JSON or YAML.
    if re.search(r"AWSTemplateFormatVersion", text):
        return "cfn:AWSTemplateFormatVersion"
    if re.search(r"^Transform:\s*(?:.*SAM|AWS::Serverless)", text, re.MULTILINE):
        return "cfn:Transform-SAM"
    # A Resources: map whose entries carry AWS::<Service>::<Type> Type values is a
    # very strong CFN structural cue (YAML or JSON).
    has_resources = re.search(r"(^|[\s,{\"])Resources[\"']?\s*:", text)
    has_aws_type = re.search(r"AWS::[A-Za-z0-9]+::[A-Za-z0-9]+", text)
    if has_resources and has_aws_type:
        return "cfn:Resources+AWS::Type"
    return None


def _terraform_content_signal(text: str) -> str | None:
    """Return a Terraform/HCL indicator label if the text is Terraform."""
    # HCL blocks: resource "aws_s3_bucket" "b" { ... } / provider "aws" { ... } /
    # terraform { required_providers ... }.
    if re.search(r'^\s*resource\s+"[a-z0-9_]+"\s+"[A-Za-z0-9_-]+"\s*\{', text, re.MULTILINE):
        return "terraform:resource-block"
    if re.search(r'^\s*provider\s+"[a-z0-9_]+"\s*\{', text, re.MULTILINE):
        return "terraform:provider-block"
    if re.search(r"^\s*terraform\s*\{", text, re.MULTILINE) and re.search(
        r"required_providers|required_version", text
    ):
        return "terraform:settings-block"
    if re.search(r'^\s*(?:variable|module|output)\s+"[A-Za-z0-9_-]+"\s*\{', text, re.MULTILINE):
        return "terraform:named-block"
    return None


def _shebang_signal(text: str) -> str | None:
    """Return a shebang interpreter label if the text begins with a recognised one."""
    first_line = text.splitlines()[0] if text.splitlines() else ""
    m = re.match(r"^#!\s*(\S+)(?:\s+(\S+))?", first_line)
    if not m:
        return None
    interp_path = m.group(1)
    interp = interp_path.rsplit("/", 1)[-1]
    # `#!/usr/bin/env python3` -> the real interpreter is the arg.
    if interp == "env" and m.group(2):
        interp = m.group(2).rsplit("/", 1)[-1]
    interp = re.sub(r"[0-9.]+$", "", interp) or interp
    base = interp.rstrip("0123456789.")
    for known in _SHEBANG_INTERPRETERS:
        if base == known.rstrip("0123456789.") or interp.startswith(known):
            return f"shebang:{base or interp}"
    return None


def content_signal(content: bytes) -> dict[str, Any]:
    """Classify by inspecting the ACTUAL bytes (authoritative on disagreement).

    Returns {"artifact_class": <SIGNAL_*>, ["matched_indicator": <label>]}.
    """
    signal: dict[str, Any] = {"artifact_class": SIGNAL_NONE}
    if not content:
        return signal

    head = content[:_HEAD_BYTES]

    # 1. Hard binary magics -> definitively not text; other_unknown.
    for magic, label in _BINARY_MAGICS:
        if head.startswith(magic):
            signal["artifact_class"] = OTHER_UNKNOWN
            signal["matched_indicator"] = f"binary:{label}"
            return signal

    text = _decode_head(head)
    if text is None:
        signal["artifact_class"] = OTHER_UNKNOWN
        signal["matched_indicator"] = "binary:non-text-bytes"
        return signal

    # 2. IaC structural cues take precedence over generic script cues, because a
    #    CFN/Terraform file can contain script-like fragments (UserData, etc.) but
    #    the outer structure is unambiguous.
    cfn = _cfn_content_signal(text)
    if cfn:
        signal["artifact_class"] = IAC_TEMPLATE
        signal["matched_indicator"] = cfn
        return signal
    tf = _terraform_content_signal(text)
    if tf:
        signal["artifact_class"] = IAC_TEMPLATE
        signal["matched_indicator"] = tf
        return signal

    # 3. A shebang is the strongest raw-script cue.
    sb = _shebang_signal(text)
    if sb:
        signal["artifact_class"] = RAW_SCRIPT
        signal["matched_indicator"] = sb
        return signal

    # 4. Anchored source-structure cues -> raw_script.
    for pattern, label in _SCRIPT_PATTERNS:
        if pattern.search(text):
            signal["artifact_class"] = RAW_SCRIPT
            signal["matched_indicator"] = label
            return signal

    # 5. Structured data with no IaC markers (a plain JSON/YAML doc) is not, by
    #    itself, an IaC template nor a script -> other_unknown (routing/1.4 owns
    #    the decision on what to do with it).
    if _looks_like_json_object(text):
        signal["artifact_class"] = OTHER_UNKNOWN
        signal["matched_indicator"] = "structured-data:no-iac-markers"
        return signal

    return signal


# --- Fusion: combine the two independent signals -----------------------------


def _fuse(
    ext_sig: dict[str, Any], content_sig: dict[str, Any]
) -> tuple[str, str, str, bool]:
    """Combine the extension + content signals into (class, basis, confidence,
    signals_agree), applying distrust-the-claim.

    Rules:
      * If content is decisive (not 'none'):
          - if extension agrees -> class=content, basis='agreement', high/medium.
          - if extension disagrees OR is 'none' -> class=CONTENT (distrust the
            claim), basis='content'. High confidence when a strong structural cue
            matched; the two signals are recorded so the mismatch is auditable.
      * If content is 'none' but extension is decisive -> class=extension,
          basis='extension', medium (weaker: we only had the untrusted name).
      * If both are 'none' -> other_unknown, basis='none', low.
    """
    ext_class = ext_sig["artifact_class"]
    content_class = content_sig["artifact_class"]

    content_decisive = content_class != SIGNAL_NONE
    ext_decisive = ext_class != SIGNAL_NONE

    if content_decisive:
        agree = ext_decisive and ext_class == content_class
        if content_class == OTHER_UNKNOWN:
            # Content proved it is not a routable type. Extension can't override.
            return OTHER_UNKNOWN, ("agreement" if agree else "content"), "medium", agree
        if agree:
            return content_class, "agreement", "high", True
        # Disagreement (or extension had no opinion): CONTENT WINS.
        return content_class, "content", "high", False

    if ext_decisive:
        # Only the untrusted extension had an opinion; content was inconclusive.
        return ext_class, "extension", "medium", False

    return OTHER_UNKNOWN, "none", "low", False


def classify(filename: str | None, content: bytes) -> dict[str, Any]:
    """Classify one artifact from its (untrusted) filename + its actual bytes.

    Returns the ``classification`` object of the classification contract:
    ``artifact_class``, ``basis``, ``confidence``, ``signals_agree``,
    ``extension_signal``, ``content_signal``, and an optional ``notes`` string.

    This is a LABEL only — never a verdict, never a route, never a safety claim.
    """
    ext_sig = extension_signal(filename)
    content_sig = content_signal(content)
    artifact_class, basis, confidence, agree = _fuse(ext_sig, content_sig)

    result: dict[str, Any] = {
        "artifact_class": artifact_class,
        "basis": basis,
        "confidence": confidence,
        "signals_agree": agree,
        "extension_signal": ext_sig,
        "content_signal": content_sig,
    }

    # A short, bounded, non-executable diagnostic note for the mismatch / unknown
    # cases (useful for the developer-tier report later; never raw content).
    if basis == "content" and ext_sig["artifact_class"] != SIGNAL_NONE:
        result["notes"] = (
            f"claimed extension suggested {ext_sig['artifact_class']} but content "
            f"classified as {artifact_class} (content is authoritative)"
        )
    elif artifact_class == OTHER_UNKNOWN:
        result["notes"] = "no IaC or script structure recognised"

    return result
