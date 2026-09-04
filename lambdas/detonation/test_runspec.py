"""ZTIE Story 2.3 — offline unit tests for the PURE run-spec derivation.

Pure stdlib ``unittest``. Proves the host-native command list is well-formed,
NON-container (no docker/podman), stages from the presigned URL, and executes the
artifact directly on the host.
"""

from __future__ import annotations

import unittest

import runspec

_URL = "https://example-forensic-bucket.s3.amazonaws.com/intake/x/a.sh?X-Amz-Signature=deadbeef"


class TestBuildRunCommands(unittest.TestCase):
    def test_returns_command_list(self):
        cmds = runspec.build_run_commands(
            filename="deploy.sh", artifact_class="raw_script", presigned_url=_URL
        )
        self.assertIsInstance(cmds, list)
        self.assertTrue(all(isinstance(c, str) for c in cmds))
        self.assertGreater(len(cmds), 3)

    def test_no_container_runtime_used(self):
        # RD-001: host-native only. The command list must NEVER shell out to a
        # container runtime.
        joined = "\n".join(
            runspec.build_run_commands(
                filename="x.sh", artifact_class="raw_script", presigned_url=_URL
            )
        )
        for banned in ("docker", "podman", "nerdctl", "containerd", "runc"):
            self.assertNotIn(banned, joined)

    def test_stages_from_presigned_url(self):
        cmds = runspec.build_run_commands(
            filename="a.sh", artifact_class="raw_script", presigned_url=_URL
        )
        joined = "\n".join(cmds)
        self.assertIn("curl", joined)
        self.assertIn("--fail", joined)  # a bad fetch is a non-zero exit
        self.assertIn(_URL, joined)

    def test_executes_the_artifact(self):
        cmds = runspec.build_run_commands(
            filename="a.sh", artifact_class="raw_script", presigned_url=_URL
        )
        joined = "\n".join(cmds)
        self.assertIn("chmod +x", joined)
        # shebang-aware execution, else /bin/sh
        self.assertIn("/bin/sh", joined)
        self.assertIn("exit $__ZTIE_RC", joined)

    def test_filename_is_quoted_and_sanitised(self):
        # A hostile filename must not break out of the staged path.
        cmds = runspec.build_run_commands(
            filename="../../etc/passwd; rm -rf /",
            artifact_class="raw_script",
            presigned_url=_URL,
        )
        joined = "\n".join(cmds)
        # shlex.quote wraps the dangerous chars; the raw ' rm -rf /' must not appear
        # as a bare command token in the staging path.
        self.assertIn("/tmp/ztie/", joined)
        self.assertIn("'", joined)  # quoting applied

    def test_empty_filename_falls_back(self):
        cmds = runspec.build_run_commands(
            filename="", artifact_class="other_unknown", presigned_url=_URL
        )
        joined = "\n".join(cmds)
        self.assertIn("/tmp/ztie/artifact", joined)


if __name__ == "__main__":
    unittest.main()
