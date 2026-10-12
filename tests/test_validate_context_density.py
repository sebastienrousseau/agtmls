# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Tests for validate-context-density.py."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = ROOT / "scripts" / "validate-context-density.py"

spec = importlib.util.spec_from_file_location("validate_context_density", SCRIPT_PATH)
vcd = importlib.util.module_from_spec(spec)
sys.modules["validate_context_density"] = vcd
spec.loader.exec_module(vcd)


class TestValidateContextDensity(unittest.TestCase):
    def test_audit_file_clean(self) -> None:
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8") as f:
            f.write("# Rules\n- Item 1\n- Item 2\n")
            f.flush()
            issues = vcd.audit_file(Path(f.name))
            self.assertEqual(issues, [])

    def test_audit_file_missing(self) -> None:
        issues = vcd.audit_file(Path("/nonexistent/file.md"))
        self.assertEqual(issues, [])

    def test_audit_file_timestamp(self) -> None:
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8") as f:
            f.write("# Rules\nGenerated at 2026-10-12T22:00:00Z\n- Item 1\n")
            f.flush()
            issues = vcd.audit_file(Path(f.name))
            self.assertTrue(any("volatile timestamps" in i for i in issues))

    def test_audit_file_low_density(self) -> None:
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8") as f:
            f.write("A " * 300)
            f.flush()
            issues = vcd.audit_file(Path(f.name))
            self.assertTrue(any("density too low" in i for i in issues))

    def test_audit_file_exceeds_tokens(self) -> None:
        with tempfile.NamedTemporaryFile("w+", encoding="utf-8") as f:
            f.write("- " + "A " * 15000)
            f.flush()
            issues = vcd.audit_file(Path(f.name))
            self.assertTrue(any("exceeds max token budget" in i for i in issues))

    def test_main_success(self) -> None:
        with patch.object(sys, "argv", ["validate-context-density.py"]):
            self.assertEqual(vcd.main(), 0)

    def test_main_failure(self) -> None:
        with patch.object(sys, "argv", ["validate-context-density.py"]), \
             patch.object(vcd, "audit_file", return_value=["Mock failure"]):
            self.assertEqual(vcd.main(), 1)


if __name__ == "__main__":
    unittest.main()
