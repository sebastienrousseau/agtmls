# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Tests for agtmls-statusline.sh script."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "agtmls-statusline.sh"


class StatuslineScriptTests(unittest.TestCase):
    def test_statusline_plain_mode(self) -> None:
        result = subprocess.run(
            [str(SCRIPT), "--plain"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("AgtMLS:", result.stdout)
        self.assertIn("33 skills", result.stdout)

    def test_statusline_tmux_mode(self) -> None:
        result = subprocess.run(
            [str(SCRIPT), "--tmux"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("AgtMLS:", result.stdout)
        self.assertIn("33 skills", result.stdout)

    def test_statusline_json_mode(self) -> None:
        result = subprocess.run(
            [str(SCRIPT), "--json"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertEqual(data.get("skills"), 33)
        self.assertEqual(data.get("status"), "ok")

    def test_statusline_in_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [str(SCRIPT), "--plain"],
                cwd=tmpdir,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "AgtMLS: 0 skills")
