#!/usr/bin/env python3
"""Run lightweight unit tests for registry tool behavior."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "scripts" / "agtmls.py"


def load_script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class VersionPolicyTests(unittest.TestCase):
    def test_next_version_after_current_release(self) -> None:
        module = load_script("next-version.py")
        original = module.release_patches
        try:
            module.release_patches = lambda: [1]
            self.assertEqual(module.next_version(), "0.0.2")
            module.release_patches = lambda: []
            self.assertEqual(module.next_version(), "0.0.1")
        finally:
            module.release_patches = original

    def test_version_policy_rejects_patch_skip(self) -> None:
        module = load_script("validate-version-policy.py")
        errors = module.sequencing_errors("0.0.999", [(0, 0, 1)])
        self.assertTrue(any("skips patch releases" in error for error in errors))

    def test_version_policy_rejects_minor_before_999(self) -> None:
        module = load_script("validate-version-policy.py")
        errors = module.sequencing_errors("0.1.0", [(0, 0, 1)])
        self.assertTrue(any("0.0.x" in error for error in errors))

    def test_version_policy_allows_next_patch(self) -> None:
        module = load_script("validate-version-policy.py")
        self.assertEqual(module.sequencing_errors("0.0.2", [(0, 0, 1)]), [])


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
    suite = unittest.TestSuite()
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(VersionPolicyTests))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(CliJsonTests))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
