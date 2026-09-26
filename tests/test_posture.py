# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Reading an agent's approval settings from its own files."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from .support import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
from _lib import posture  # needs the scripts path first

AGENT = {"approval_settings": [
    {"file": "project.json", "scope": "project", "format": "json", "key": "permissions.defaultMode",
     "unattended": ["bypassPermissions"], "classified": ["auto"]},
    {"file": "~/user.toml", "scope": "user", "format": "toml", "key": "approval_policy", "unattended": ["never"]},
    {"file": "conf.yml", "scope": "project", "format": "yaml", "key": "yes-always", "unattended": [True]},
]}


class PostureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.target = Path(tempfile.mkdtemp(prefix="agtmls-posture-"))
        self.home = Path(tempfile.mkdtemp(prefix="agtmls-posture-home-"))
        for path in (self.target, self.home):
            self.addCleanup(shutil.rmtree, path, True)

    def read(self) -> list[posture.Setting]:
        return posture.settings(AGENT, self.target, self.home)

    def test_nothing_on_disk_reports_nothing(self) -> None:
        self.assertEqual(self.read(), [])

    def test_each_format_and_scope_is_read(self) -> None:
        (self.target / "project.json").write_text(json.dumps({"permissions": {"defaultMode": "auto"}}), encoding="utf-8")
        (self.home / "user.toml").write_text('approval_policy = "never"\n', encoding="utf-8")
        (self.target / "conf.yml").write_text("yes-always: true  # careful\n", encoding="utf-8")
        self.assertEqual(self.read(), [
            posture.Setting("project.json", "project", "permissions.defaultMode", "auto", False, True),
            posture.Setting("~/user.toml", "user", "approval_policy", "never", True, False),
            posture.Setting("conf.yml", "project", "yes-always", True, True, False),
        ])

    def test_unreadable_malformed_or_absent_keys_report_nothing(self) -> None:
        (self.target / "project.json").write_text("{ not json", encoding="utf-8")
        (self.home / "user.toml").write_text("approval_policy = [unclosed\n", encoding="utf-8")
        (self.target / "conf.yml").write_text("model: sonnet\n", encoding="utf-8")
        self.assertEqual(self.read(), [])
        (self.target / "project.json").write_text(json.dumps({"permissions": "x"}), encoding="utf-8")
        self.assertEqual(self.read(), [])

    def test_an_oversized_file_is_not_read(self) -> None:
        (self.target / "project.json").write_text(json.dumps({"permissions": {"defaultMode": "bypassPermissions"}}), encoding="utf-8")
        with mock.patch.object(posture, "MAX_BYTES", 10):
            self.assertEqual(self.read(), [])

    def test_without_tomllib_top_level_keys_are_still_read(self) -> None:
        """Python 3.10 has no tomllib; the settings these agents use are top-level."""
        (self.home / "user.toml").write_text(
            '# comment\n\napproval_policy = "never" # inline\n  indented = "ignored"\n[table]\napproval_policy = "later"\n',
            encoding="utf-8",
        )
        with mock.patch.object(posture, "tomllib", None):
            self.assertEqual([s.value for s in self.read()], ["never"])
        self.assertEqual(posture.flat_top_level("flag = false\nname: 'x'\nnot a pair\nlist = [1, 2]\nmap = {a = 1}\n"),
                         {"flag": False, "name": "x"})
        # What 3.10 reads must not differ from tomllib on a malformed value.
        (self.home / "user.toml").write_text("approval_policy = [unclosed\n", encoding="utf-8")
        with mock.patch.object(posture, "tomllib", None):
            self.assertEqual(self.read(), [])

    def test_default_home_is_the_users(self) -> None:
        with mock.patch.object(posture.Path, "home", return_value=self.home):
            (self.home / "user.toml").write_text('approval_policy = "never"\n', encoding="utf-8")
            self.assertEqual([s.key for s in posture.settings(AGENT, self.target)], ["approval_policy"])


if __name__ == "__main__":
    unittest.main()
