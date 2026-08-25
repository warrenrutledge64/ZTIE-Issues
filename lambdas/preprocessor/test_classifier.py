"""Unit tests for the ZTIE Story 1.2 PURE classifier.

Pure-logic tests — no boto3, no AWS, no PyPI — so they run in the INTEGRATIONS_ONLY
build sandbox with plain ``unittest`` and also under ``pytest`` live. They pin the
Definition of Done: a known IaC template and a known raw script each classify
CORRECTLY, and an artifact whose claimed extension DISAGREES with its content is
classified by CONTENT (distrust-the-claim).

Run offline:  python3 -m unittest lambdas/preprocessor/test_classifier.py
"""

from __future__ import annotations

import unittest
from typing import ClassVar

from classifier import (
    IAC_TEMPLATE,
    OTHER_UNKNOWN,
    RAW_SCRIPT,
    SIGNAL_NONE,
    classify,
    content_signal,
    extension_signal,
)

# --- Representative fixtures (the kinds of artifact the user will feed live) --

CFN_YAML = b"""AWSTemplateFormatVersion: '2010-09-09'
Description: A minimal S3 bucket
Resources:
  MyBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: my-example-bucket
"""

CFN_JSON = b"""{
  "AWSTemplateFormatVersion": "2010-09-09",
  "Resources": {
    "MyBucket": { "Type": "AWS::S3::Bucket" }
  }
}
"""

TERRAFORM = b"""terraform {
  required_providers {
    aws = { source = "hashicorp/aws" }
  }
}

resource "aws_s3_bucket" "b" {
  bucket = "my-tf-bucket"
}
"""

BASH_SCRIPT = b"""#!/usr/bin/env bash
set -euo pipefail
echo "deploying"
for f in *.txt; do
  echo "$f"
done
"""

PYTHON_SCRIPT = b"""#!/usr/bin/env python3
import os


def main():
    print(os.getcwd())


if __name__ == "__main__":
    main()
"""

PYTHON_NO_SHEBANG = b"""import sys
from collections import defaultdict


def tally(items):
    counts = defaultdict(int)
    for i in items:
        counts[i] += 1
    return counts
"""

JS_SCRIPT = b"""const http = require('http');

function handler(req, res) {
  res.end('ok');
}

http.createServer(handler).listen(8080);
"""

PLAIN_JSON_DATA = b'{"name": "widget", "count": 42, "tags": ["a", "b"]}'

PLAIN_TEXT = b"just some notes about the project, nothing structured here at all.\n"

ELF_BINARY = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 64
PNG_IMAGE = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
EMPTY = b""


class TestExtensionSignal(unittest.TestCase):
    def test_terraform_extension_is_iac(self):
        sig = extension_signal("main.tf")
        self.assertEqual(sig["artifact_class"], IAC_TEMPLATE)
        self.assertEqual(sig["extension"], "tf")

    def test_script_extensions(self):
        self.assertEqual(extension_signal("deploy.sh")["artifact_class"], RAW_SCRIPT)
        self.assertEqual(extension_signal("app.py")["artifact_class"], RAW_SCRIPT)
        self.assertEqual(extension_signal("index.js")["artifact_class"], RAW_SCRIPT)

    def test_ambiguous_extensions_decline(self):
        # json/yaml/yml are recorded but NOT decisive by extension alone.
        for name in ("stack.yaml", "config.yml", "data.json"):
            sig = extension_signal(name)
            self.assertEqual(sig["artifact_class"], SIGNAL_NONE)
            self.assertIn("extension", sig)

    def test_no_extension(self):
        sig = extension_signal("Dockerfile")
        self.assertEqual(sig["artifact_class"], SIGNAL_NONE)
        self.assertNotIn("extension", sig)

    def test_none_filename(self):
        self.assertEqual(extension_signal(None)["artifact_class"], SIGNAL_NONE)


class TestContentSignal(unittest.TestCase):
    def test_cfn_yaml_content(self):
        sig = content_signal(CFN_YAML)
        self.assertEqual(sig["artifact_class"], IAC_TEMPLATE)
        self.assertIn("cfn", sig["matched_indicator"])

    def test_cfn_json_content(self):
        self.assertEqual(content_signal(CFN_JSON)["artifact_class"], IAC_TEMPLATE)

    def test_terraform_content(self):
        sig = content_signal(TERRAFORM)
        self.assertEqual(sig["artifact_class"], IAC_TEMPLATE)
        self.assertIn("terraform", sig["matched_indicator"])

    def test_bash_shebang_content(self):
        sig = content_signal(BASH_SCRIPT)
        self.assertEqual(sig["artifact_class"], RAW_SCRIPT)
        self.assertTrue(sig["matched_indicator"].startswith("shebang"))

    def test_python_shebang_content(self):
        self.assertEqual(content_signal(PYTHON_SCRIPT)["artifact_class"], RAW_SCRIPT)

    def test_python_without_shebang_by_structure(self):
        sig = content_signal(PYTHON_NO_SHEBANG)
        self.assertEqual(sig["artifact_class"], RAW_SCRIPT)
        self.assertTrue(sig["matched_indicator"].startswith("python"))

    def test_js_by_structure(self):
        self.assertEqual(content_signal(JS_SCRIPT)["artifact_class"], RAW_SCRIPT)

    def test_plain_json_data_is_other(self):
        sig = content_signal(PLAIN_JSON_DATA)
        self.assertEqual(sig["artifact_class"], OTHER_UNKNOWN)

    def test_plain_text_is_none(self):
        self.assertEqual(content_signal(PLAIN_TEXT)["artifact_class"], SIGNAL_NONE)

    def test_elf_binary_is_other(self):
        sig = content_signal(ELF_BINARY)
        self.assertEqual(sig["artifact_class"], OTHER_UNKNOWN)
        self.assertIn("binary", sig["matched_indicator"])

    def test_png_is_other(self):
        self.assertEqual(content_signal(PNG_IMAGE)["artifact_class"], OTHER_UNKNOWN)

    def test_empty_is_none(self):
        self.assertEqual(content_signal(EMPTY)["artifact_class"], SIGNAL_NONE)


class TestClassifyHappyPath(unittest.TestCase):
    """DoD part 1: a known IaC template and a known raw script classify correctly."""

    def test_known_iac_template_yaml(self):
        r = classify("s3-bucket.yaml", CFN_YAML)
        self.assertEqual(r["artifact_class"], IAC_TEMPLATE)
        # ambiguous ext + decisive content -> content basis, high confidence.
        self.assertEqual(r["basis"], "content")
        self.assertEqual(r["confidence"], "high")

    def test_known_iac_terraform_agreement(self):
        r = classify("main.tf", TERRAFORM)
        self.assertEqual(r["artifact_class"], IAC_TEMPLATE)
        # extension (.tf) AND content agree -> agreement, high.
        self.assertEqual(r["basis"], "agreement")
        self.assertTrue(r["signals_agree"])
        self.assertEqual(r["confidence"], "high")

    def test_known_raw_script_bash_agreement(self):
        r = classify("deploy.sh", BASH_SCRIPT)
        self.assertEqual(r["artifact_class"], RAW_SCRIPT)
        self.assertEqual(r["basis"], "agreement")
        self.assertTrue(r["signals_agree"])

    def test_known_raw_script_python(self):
        r = classify("app.py", PYTHON_SCRIPT)
        self.assertEqual(r["artifact_class"], RAW_SCRIPT)
        self.assertTrue(r["signals_agree"])


class TestClassifyDistrustTheClaim(unittest.TestCase):
    """DoD part 2: claimed extension disagrees with content -> content WINS."""

    def test_script_disguised_as_yaml_template(self):
        # A raw bash script uploaded with a .yaml name (claims IaC-ish). Content
        # must win: raw_script, basis=content, signals disagree, both recorded.
        r = classify("innocent.yaml", BASH_SCRIPT)
        self.assertEqual(r["artifact_class"], RAW_SCRIPT)
        self.assertEqual(r["basis"], "content")
        self.assertFalse(r["signals_agree"])
        self.assertEqual(r["content_signal"]["artifact_class"], RAW_SCRIPT)
        # the extension was ambiguous (yaml) so it recorded 'none' + the ext.
        self.assertEqual(r["extension_signal"]["extension"], "yaml")

    def test_cfn_template_disguised_as_shell_script(self):
        # A real CloudFormation template uploaded as deploy.sh (claims script).
        # Content must win: iac_template, content basis, signals disagree.
        r = classify("deploy.sh", CFN_YAML)
        self.assertEqual(r["artifact_class"], IAC_TEMPLATE)
        self.assertEqual(r["basis"], "content")
        self.assertFalse(r["signals_agree"])
        self.assertEqual(r["extension_signal"]["artifact_class"], RAW_SCRIPT)
        self.assertEqual(r["content_signal"]["artifact_class"], IAC_TEMPLATE)
        self.assertIn("notes", r)

    def test_binary_disguised_as_python(self):
        # An ELF binary named .py claims to be a script. Content wins: other_unknown.
        r = classify("totally_python.py", ELF_BINARY)
        self.assertEqual(r["artifact_class"], OTHER_UNKNOWN)
        self.assertEqual(r["content_signal"]["artifact_class"], OTHER_UNKNOWN)
        self.assertFalse(r["signals_agree"])

    def test_terraform_disguised_as_txt(self):
        r = classify("notes.txt", TERRAFORM)
        self.assertEqual(r["artifact_class"], IAC_TEMPLATE)
        self.assertEqual(r["basis"], "content")


class TestClassifyOtherUnknown(unittest.TestCase):
    """DoD supports 1.4: unroutable artifacts become other_unknown, no crash."""

    def test_plain_text_unknown(self):
        r = classify("readme", PLAIN_TEXT)
        self.assertEqual(r["artifact_class"], OTHER_UNKNOWN)
        self.assertEqual(r["basis"], "none")
        self.assertEqual(r["confidence"], "low")
        self.assertIn("notes", r)

    def test_plain_json_data_unknown(self):
        r = classify("config.json", PLAIN_JSON_DATA)
        self.assertEqual(r["artifact_class"], OTHER_UNKNOWN)

    def test_empty_artifact_unknown(self):
        r = classify("empty.sh", EMPTY)
        # No content to go on; only the untrusted extension had an opinion.
        self.assertEqual(r["extension_signal"]["artifact_class"], RAW_SCRIPT)
        self.assertEqual(r["content_signal"]["artifact_class"], SIGNAL_NONE)
        # extension-only -> class follows the (weak) extension, basis=extension.
        self.assertEqual(r["artifact_class"], RAW_SCRIPT)
        self.assertEqual(r["basis"], "extension")
        self.assertEqual(r["confidence"], "medium")

    def test_image_unknown(self):
        r = classify("logo.png", PNG_IMAGE)
        self.assertEqual(r["artifact_class"], OTHER_UNKNOWN)


class TestResultShape(unittest.TestCase):
    """Every result must carry both signals + the required contract fields, and
    must NEVER contain a verdict/route/safety field (zero-trust boundary)."""

    FORBIDDEN: ClassVar[set[str]] = {
        "verdict",
        "safe",
        "route",
        "decision",
        "forward",
        "status",
    }

    def test_required_fields_present(self):
        for fn, body in (
            ("main.tf", TERRAFORM),
            ("app.py", PYTHON_SCRIPT),
            ("x", PLAIN_TEXT),
            ("evil.yaml", BASH_SCRIPT),
        ):
            r = classify(fn, body)
            for field in (
                "artifact_class",
                "basis",
                "confidence",
                "signals_agree",
                "extension_signal",
                "content_signal",
            ):
                self.assertIn(field, r, f"{field} missing for {fn}")

    def test_no_verdict_or_route_field_ever(self):
        for fn, body in (("main.tf", TERRAFORM), ("app.py", PYTHON_SCRIPT)):
            r = classify(fn, body)
            self.assertEqual(self.FORBIDDEN & set(r.keys()), set())

    def test_classes_are_from_the_closed_set(self):
        allowed = {IAC_TEMPLATE, RAW_SCRIPT, OTHER_UNKNOWN}
        for fn, body in (
            ("main.tf", TERRAFORM),
            ("app.py", PYTHON_SCRIPT),
            ("x", PLAIN_TEXT),
            ("logo.png", PNG_IMAGE),
        ):
            self.assertIn(classify(fn, body)["artifact_class"], allowed)


if __name__ == "__main__":
    unittest.main()
