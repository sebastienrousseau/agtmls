# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Asking an agent which skills it can read, and checking its user-level links."""

from __future__ import annotations

import io
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from .support import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
from _lib import liveness  # needs the scripts path first

CODEX_PROMPT = [{"type": "message", "content": [{"type": "input_text", "text": (
    "<skills_instructions> ## Skills\n### Skill roots\n- `r0` = `/repo/.codex/skills`\n- `r1` = `/home/.codex/skills/.system`\n"
    "### Available skills\n- agtmls:using-agtmls: Meta-router. (file: r0/using-agtmls/SKILL.md)\n"
    "- imagegen: Images. (file: r1/imagegen/SKILL.md)\n</skills_instructions>")}]}]


class UserSkillLinkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.home = Path(tempfile.mkdtemp(prefix="agtmls-live-"))
        self.addCleanup(shutil.rmtree, self.home, True)

    def test_links_are_judged_and_real_directories_and_dotfiles_are_not(self) -> None:
        skills = self.home / ".claude" / "skills"
        (self.home / "real" / "one").mkdir(parents=True)
        (self.home / "real" / "one" / "SKILL.md").write_text("x", encoding="utf-8")
        skills.mkdir(parents=True)
        (skills / "one").symlink_to(self.home / "real" / "one")
        (skills / "two").symlink_to(self.home / "real" / "missing")
        (skills / "mine").mkdir()
        (skills / ".system").symlink_to(self.home / "real" / "missing")
        agent = {"user_skills_dirs": ["~/.claude/skills", "/no/such/dir"]}
        self.assertEqual(liveness.user_skill_links(agent, self.home), [
            liveness.Link("~/.claude/skills", "one", str(self.home / "real" / "one"), True),
            liveness.Link("~/.claude/skills", "two", str(self.home / "real" / "missing"), False),
        ])

    def test_default_home_and_no_dirs(self) -> None:
        with mock.patch.object(liveness.Path, "home", return_value=self.home):
            self.assertEqual(liveness.user_skill_links({"user_skills_dirs": ["~/.x/skills"]}), [])
        self.assertEqual(liveness.user_skill_links({}), [])


class ProbeTests(unittest.TestCase):
    def test_codex_names_come_from_the_skill_path_not_the_namespaced_name(self) -> None:
        self.assertEqual(liveness.codex_skill_names(CODEX_PROMPT), {"using-agtmls", "imagegen"})
        self.assertEqual(liveness.codex_skill_names({"a": ["no skills here", 3]}), set())

    def test_an_agent_without_a_probe_or_binary_cannot_be_asked(self) -> None:
        with self.assertRaisesRegex(liveness.ProbeError, "no live check"):
            liveness.loaded_skills({}, Path("."))
        with mock.patch.object(liveness.shutil, "which", return_value=None), \
                self.assertRaisesRegex(liveness.ProbeError, "claude is not installed"):
            liveness.loaded_skills({"live_probe": "claude-init"}, Path("."))

    def test_a_probe_that_cannot_run_is_an_error(self) -> None:
        with mock.patch.object(liveness.shutil, "which", return_value="/bin/codex"), \
                mock.patch.object(liveness.subprocess, "run", side_effect=subprocess.TimeoutExpired("codex", 1)), \
                self.assertRaisesRegex(liveness.ProbeError, "codex could not be run"):
            liveness.loaded_skills({"live_probe": "codex-prompt-input"}, Path("."))

    def test_codex_prompt_input_is_parsed_or_refused(self) -> None:
        def run(stdout: str, code: int = 0):
            return mock.patch.object(liveness.subprocess, "run",
                                     return_value=subprocess.CompletedProcess([], code, stdout, ""))
        with mock.patch.object(liveness.shutil, "which", return_value="/bin/codex"):
            with run(json.dumps(CODEX_PROMPT)):
                self.assertEqual(liveness.loaded_skills({"live_probe": "codex-prompt-input"}, Path(".")),
                                 {"using-agtmls", "imagegen"})
            with run("", 2), self.assertRaisesRegex(liveness.ProbeError, "exited 2"):
                liveness.loaded_skills({"live_probe": "codex-prompt-input"}, Path("."))
            with run("not json"), self.assertRaisesRegex(liveness.ProbeError, "no JSON"):
                liveness.loaded_skills({"live_probe": "codex-prompt-input"}, Path("."))

    def fake_claude(self, lines: list[str]):
        proc = mock.MagicMock()
        proc.__enter__.return_value = proc
        proc.stdout = io.StringIO("".join(line + "\n" for line in lines))
        return mock.patch.object(liveness.subprocess, "Popen", return_value=proc), proc

    def test_claude_skills_come_from_its_init_event_and_it_is_stopped_after(self) -> None:
        patch, proc = self.fake_claude(["not json", json.dumps({"type": "system", "subtype": "other"}),
                                        json.dumps({"type": "system", "subtype": "init",
                                                    "skills": ["using-agtmls", {"name": "debug"}]})])
        with mock.patch.object(liveness.shutil, "which", return_value="/bin/claude"), patch:
            self.assertEqual(liveness.loaded_skills({"live_probe": "claude-init"}, Path(".")), {"using-agtmls", "debug"})
        proc.kill.assert_called_once()

    def test_claude_without_an_init_event_is_an_error(self) -> None:
        patch, _ = self.fake_claude(["{}"])
        with mock.patch.object(liveness.shutil, "which", return_value="/bin/claude"), patch, \
                self.assertRaisesRegex(liveness.ProbeError, "no init event"):
            liveness.loaded_skills({"live_probe": "claude-init"}, Path("."))


if __name__ == "__main__":
    unittest.main()
