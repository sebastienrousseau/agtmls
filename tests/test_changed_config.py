# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""`audit --changed-agent-config`: what a branch changes that an agent loads unread."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from .support import ROOT, load_script, run_main

sys.path.insert(0, str(ROOT / "scripts"))
from _lib import agent_config  # needs the scripts path first

changed = load_script("audit-changed-config.py")
HOOK = {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "./start.sh"}]}]}}


class WatchedTests(unittest.TestCase):
    def test_agent_configuration_is_watched_and_prose_and_code_are_not(self) -> None:
        for rel in (".claude/settings.json", ".mcp.json", ".claude.json", ".gitmodules", ".ripgreprc", "CLAUDE.md",
                    "CLAUDE.local.md", ".husky/pre-commit", "AGENTS.md", "pkg/AGENTS.md", ".codex/config.toml",
                    "opencode.json", "plugin/.claude-plugin/plugin.json"):
            with self.subTest(rel=rel):
                self.assertTrue(agent_config.watched(rel))
        for rel in ("README.md", "docs/setup.md", "src/app.py", "scripts/install.sh", "hooks.py"):
            with self.subTest(rel=rel):
                self.assertFalse(agent_config.watched(rel))


class BranchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(tempfile.mkdtemp(prefix="agtmls-changed-"))
        self.addCleanup(lambda: shutil.rmtree(self.repo, ignore_errors=True))
        subprocess.run(["git", "init", "-q", "-b", "main", str(self.repo)], check=True)
        self.write("AGENTS.md", "# rules\n")
        self.write("CLAUDE.md", "# old\n")
        self.write("old.mcp.json", "{}")
        self.commit("base")
        subprocess.run(self.git("checkout", "-q", "-b", "topic"), check=True)

    def git(self, *args: str) -> list[str]:
        return ["git", "-C", str(self.repo), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                "-c", "commit.gpgsign=false", *args]

    def write(self, rel: str, text: str) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def commit(self, message: str) -> None:
        subprocess.run(self.git("add", "-A"), check=True)
        subprocess.run(self.git("commit", "-q", "-m", message), check=True)

    def test_a_branch_that_adds_a_hook_names_it_audits_it_and_fails(self) -> None:
        """The case R35-3 names: a hook added to .claude/settings.json."""
        self.write(".claude/settings.json", json.dumps(HOOK))
        self.write("CLAUDE.md", "# new\n")
        self.write("src/app.py", "print(1)\n")
        (self.repo / "AGENTS.md").unlink()
        self.commit("change")
        self.assertEqual(agent_config.changed_config(self.repo, "main"),
                         [("A", ".claude/settings.json"), ("D", "AGENTS.md"), ("M", "CLAUDE.md")])
        code, output = run_main(changed, "main", "--root", str(self.repo))
        self.assertEqual(code, 1, output)
        self.assertIn("Agent configuration changed since main: 3 path(s)", output)
        self.assertIn("  added: .claude/settings.json", output)
        self.assertIn("  deleted: AGENTS.md", output)
        self.assertIn("  hook .claude/settings.json: SessionStart UNGATED: ./start.sh", output)
        self.assertIn("(AGT-HOOK-006)", output)
        self.assertNotIn("src/app.py", output)

    def test_json_carries_the_paths_findings_and_inventory(self) -> None:
        self.write(".mcp.json", json.dumps({"mcpServers": {"web": {"url": "http://m.example.com/mcp"}}}))
        self.commit("mcp")
        code, output = run_main(changed, "main", "--root", str(self.repo), "--format", "json")
        self.assertEqual(code, 1, output)
        data = json.loads(output)
        self.assertEqual(data["changed"], [{"status": "added", "path": ".mcp.json"}])
        self.assertEqual([f["rule"] for f in data["findings"]], ["AGT-MCP-003"])
        self.assertEqual(data["inventory"]["mcp_servers"][0]["name"], "web")

    def test_a_rename_is_reported_under_its_new_path(self) -> None:
        subprocess.run(self.git("mv", "old.mcp.json", ".mcp.json"), check=True)
        self.commit("rename")
        self.assertEqual(agent_config.changed_config(self.repo, "main"), [("R", ".mcp.json")])

    def test_no_configuration_change_passes(self) -> None:
        self.write("src/app.py", "print(1)\n")
        self.commit("code")
        code, output = run_main(changed, "main", "--root", str(self.repo))
        self.assertEqual(code, 0, output)
        self.assertIn("OK: no agent configuration changed since main", output)

    def test_a_base_git_cannot_find_is_exit_2(self) -> None:
        code, output = run_main(changed, "no-such-branch", "--root", str(self.repo))
        self.assertEqual(code, 2, output)
        self.assertIn("error:", output)
        with self.assertRaises(agent_config.ConfigChangeError):
            agent_config.changed_config(self.repo / "absent", "main")


if __name__ == "__main__":
    unittest.main()
