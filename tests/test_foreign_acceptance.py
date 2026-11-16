# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The acceptance runner fails on a missing rule or policy, and only then."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from .support import load_script, run_main

acceptance = load_script("run-foreign-acceptance.py")


def report(rules: list[str], policy: dict | None = None) -> dict:
    finding = [{"rule": r} for r in rules]
    return {"skills": [{"path": "skills/one", "policy": policy or {}, "findings": finding[:1], "suppressed": []}],
            "agent_config": {"findings": finding[1:], "suppressed": []}}


ENTRY = {"repo": "acme/tools", "commit": "c" * 40, "rules": ["AGT-HOOK-006", "AGT-MCP-003"],
         "policy": {"skills/one": {"executes_commands": True}}}


class CheckTests(unittest.TestCase):
    def test_every_rule_and_policy_value_present_passes(self) -> None:
        found = report(["AGT-HOOK-006", "AGT-MCP-003", "AGT-NEW-001"], {"executes_commands": True})
        self.assertEqual(acceptance.check(ENTRY, found), [])

    def test_a_missing_rule_or_a_wrong_policy_value_is_named(self) -> None:
        found = report(["AGT-HOOK-006"], {"executes_commands": "unknown"})
        self.assertEqual(acceptance.check(ENTRY, found), [
            "acme/tools: AGT-MCP-003 not reported",
            "acme/tools: skills/one executes_commands is 'unknown', expected True",
        ])

    def test_a_pinned_url_is_audited_when_no_clones_are_given(self) -> None:
        self.assertEqual(acceptance.target(ENTRY, None), f"https://github.com/acme/tools.git@{'c' * 40}")
        self.assertEqual(acceptance.target(ENTRY, Path("/x")), "/x/acme_tools")


class RunTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="agtmls-acceptance-"))
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))
        tree = self.tmp / "clones" / "acme_tools"
        (tree / ".claude").mkdir(parents=True)
        (tree / ".claude" / "settings.json").write_text(json.dumps({"hooks": {"UserPromptSubmit": [
            {"hooks": [{"type": "command", "command": "./recall.sh"}]}]}}), encoding="utf-8")
        git = ["git", "-C", str(tree), "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]
        subprocess.run(["git", "init", "-q", str(tree)], check=True)
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-q", "-m", "x"], check=True)
        self.commit = acceptance.head(str(tree))

    def run_with(self, rules: list[str], commit: str | None = None) -> tuple[int, str]:
        path = self.tmp / "acceptance.json"
        path.write_text(json.dumps({"repos": [{"repo": "acme/tools", "commit": commit or self.commit, "rules": rules}]}),
                        encoding="utf-8")
        return run_main(acceptance, "--clones", str(self.tmp / "clones"), "--acceptance", str(path))

    def test_a_checkout_that_reports_its_rules_passes(self) -> None:
        code, output = self.run_with(["AGT-HOOK-006"])
        self.assertEqual(code, 0, output)
        self.assertIn("OK: acme/tools @", output)
        self.assertIn("1/1 repositories as expected", output)

    def test_a_missing_rule_fails(self) -> None:
        code, output = self.run_with(["AGT-HOOK-006", "AGT-PERM-002"])
        self.assertEqual(code, 1, output)
        self.assertIn("  acme/tools: AGT-PERM-002 not reported", output)
        self.assertIn("0/1 repositories as expected", output)

    def test_a_checkout_at_another_commit_is_refused(self) -> None:
        code, output = self.run_with(["AGT-HOOK-006"], commit="0" * 40)
        self.assertEqual(code, 1, output)
        self.assertIn(f"is not a checkout of {'0' * 40}", output)
        self.assertIsNone(acceptance.head(str(self.tmp / "absent")))

    def test_an_audit_with_no_report_is_a_failure_not_a_crash(self) -> None:
        failed = subprocess.CompletedProcess([], 2, stdout="", stderr="error: clone failed")
        with mock.patch.object(acceptance.subprocess, "run", return_value=failed):
            self.assertEqual(acceptance.run_one({"repo": "acme/tools", "commit": "c" * 40, "rules": []}, None),
                             ["acme/tools: no report (exit 2): error: clone failed"])


if __name__ == "__main__":
    unittest.main()
