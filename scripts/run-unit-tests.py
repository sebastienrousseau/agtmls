#!/usr/bin/env python3
"""Run lightweight unit tests for registry tool behavior."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "scripts" / "agtmls.py"


class CliJsonTests(unittest.TestCase):
    def run_cli(self, *args: str) -> str:
        proc = subprocess.run([sys.executable, str(CLI), *args], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        return proc.stdout

    def test_stats_json_has_full_coverage(self) -> None:
        import json
        payload = json.loads(self.run_cli("stats", "--json"))
        skill_count = payload["skills"]
        self.assertEqual(payload["coverage"]["routing"], {"covered": skill_count, "total": skill_count})
        self.assertEqual(payload["coverage"]["behavioral"], {"covered": skill_count, "total": skill_count})

    def test_profiles_json_includes_required_profiles(self) -> None:
        import json
        payload = json.loads(self.run_cli("profiles", "--json"))
        self.assertTrue({"minimal", "polyglot", "noyalib", "security", "research"}.issubset(payload))

    def test_providers_json_includes_native_and_exports(self) -> None:
        import json
        payload = json.loads(self.run_cli("providers", "--json"))
        self.assertEqual(set(payload["native_agents"]), {"claude", "codex", "aider"})
        self.assertIn("generic", payload["export_targets"])
        self.assertIn("openai", payload["export_targets"])


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CliJsonTests)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
