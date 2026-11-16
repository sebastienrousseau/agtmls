# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""A provisional policy is inferred or unknown, never defaulted to false."""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from .support import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
from _lib import inferred_policy  # needs the scripts path first

HEAD = "---\nname: s\ndescription: Use when testing.\n---\n\n# S\n\n"


class InferredPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="agtmls-inferred-"))
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))

    def policy(self, body: str, **extra: str) -> dict:
        (self.tmp / "SKILL.md").write_text(HEAD + body, encoding="utf-8")
        for rel, text in extra.items():
            (self.tmp / rel).write_text(text, encoding="utf-8")
        return inferred_policy.provisional_policy(self.tmp)

    def test_nothing_said_is_unknown_not_false(self) -> None:
        self.assertEqual(self.policy("Explain the diff in plain words.\n"), {
            "executes_commands": "unknown", "writes_files": "unknown", "network_access": "unknown",
            "handles_secrets": "unknown", "provisional": True, "basis": {},
        })

    def test_a_command_the_skill_tells_the_agent_to_run_is_execution(self) -> None:
        """The case R34-4 names: `make test` was reported as executes_commands=false."""
        policy = self.policy("Before you answer, run `make test` and read its output.\n")
        self.assertIs(policy["executes_commands"], True)
        self.assertEqual(policy["basis"], {"executes_commands": "SKILL.md:8"})

    def test_a_shell_block_or_a_shipped_script_is_execution(self) -> None:
        self.assertEqual(self.policy("Steps:\n\n```bash\nnpm ci\n```\n")["basis"], {"executes_commands": "SKILL.md:10"})
        (self.tmp / "SKILL.md").unlink()
        self.assertEqual(self.policy("Use the helper.\n", **{"verify.sh": "#!/bin/sh\n"})["basis"],
                         {"executes_commands": "ships verify.sh"})

    def test_network_writes_and_secrets_are_inferred_from_the_body(self) -> None:
        policy = self.policy("Fetch https://api.example.com/spec, then write the output file.\n"
                             "Read the API key from .env.\n")
        self.assertEqual((policy["network_access"], policy["writes_files"], policy["handles_secrets"]),
                         ("optional", True, True))
        self.assertEqual(policy["basis"], {"handles_secrets": "SKILL.md:9", "network_access": "SKILL.md:8",
                                           "writes_files": "SKILL.md:8"})

    def test_allowed_tools_take_precedence_as_the_basis(self) -> None:
        (self.tmp / "SKILL.md").write_text(
            "---\nname: s\ndescription: Use when testing.\nallowed-tools: \"Bash(git log:*) Read\"\n---\n\nRun `git log`.\n",
            encoding="utf-8")
        policy = inferred_policy.provisional_policy(self.tmp)
        self.assertEqual(policy["basis"], {"executes_commands": "allowed-tools: Bash(git log:*)"})


if __name__ == "__main__":
    unittest.main()
