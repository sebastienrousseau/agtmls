# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The analyzer's rules come from agtmls-spec, not from a hand-kept copy.

rules.py used to restate every pattern in agtmls-spec/rules/*.toml by hand,
and the only thing that noticed drift was a differential run in *other*
repositories' CI. The spec is now snapshotted into scripts/_lib/rules.json by
sync-spec-rules.py, rules.py builds its tables from that snapshot, and the
gate checks the snapshot -- here, on every Python this repo supports.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from .support import ROOT, load_script, run_main

SNAPSHOT = ROOT / "scripts" / "_lib" / "rules.json"
SPEC = ROOT.parent / "agtmls-spec"


class RulesComeFromTheSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        sys.path.insert(0, str(ROOT / "scripts"))
        self.addCleanup(lambda: sys.path.remove(str(ROOT / "scripts")))
        from _lib import rules

        self.rules = rules
        self.snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    def test_every_pattern_rule_in_the_snapshot_is_loaded(self) -> None:
        loaded = {
            rule_id: (regex.pattern, message)
            for table in (
                self.rules.PROMPT_INJECTION_PATTERNS,
                self.rules.DANGEROUS_SHELL_PATTERNS,
                self.rules.DATA_EXFILTRATION_PATTERNS,
            )
            for regex, rule_id, message in table
        }
        expected = {
            rule["id"]: (rule["pattern"], rule["description"])
            for rule in self.snapshot["rules"]
            if "pattern" in rule
        }
        self.assertEqual(loaded, expected)

    def test_the_invisible_code_point_table_is_the_spec_list(self) -> None:
        steg = next(r for r in self.snapshot["rules"] if r["id"] == "AGT-STEG-001")
        expected = {chr(int(c["cp"][2:], 16)): f"{c['name']} ({c['cp']})" for c in steg["code_points"]}
        self.assertEqual(self.rules.INVISIBLE_UNICODE, expected)

    def test_the_snapshot_records_where_it_came_from(self) -> None:
        source = self.snapshot["source"]
        self.assertEqual(source["repository"], "sebastienrousseau/agtmls-spec")
        self.assertRegex(source["commit"], r"^[0-9a-f]{40}$")
        self.assertTrue(source["files"])


class SyncCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="agtmls-rules-"))
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))
        self.module = load_script("sync-spec-rules.py")

    def snapshot_copy(self, mutate) -> Path:
        data = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        mutate(data)
        path = self.tmp / "rules.json"
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.module.SNAPSHOT = path
        return path

    def test_the_committed_snapshot_is_self_consistent(self) -> None:
        code, output = run_main(self.module, "--check")
        self.assertEqual(code, 0, output)

    def test_a_pattern_that_misses_its_own_true_positive_is_caught(self) -> None:
        def mutate(data: dict) -> None:
            rule = next(r for r in data["rules"] if r["id"] == "AGT-INJ-001")
            rule["pattern"] = "(?i)this will never match"

        self.snapshot_copy(mutate)
        code, output = run_main(self.module, "--check")
        self.assertNotEqual(code, 0, output)
        self.assertIn("AGT-INJ-001", output)

    def test_a_pattern_that_matches_its_own_false_positive_is_caught(self) -> None:
        def mutate(data: dict) -> None:
            rule = next(r for r in data["rules"] if r["id"] == "AGT-EXEC-001")
            rule["pattern"] = "(?i)curl"

        self.snapshot_copy(mutate)
        code, output = run_main(self.module, "--check")
        self.assertIn("AGT-EXEC-001", output)
        self.assertNotEqual(code, 0, output)

    @unittest.skipUnless(sys.version_info >= (3, 11), "tomllib is 3.11+")
    @unittest.skipUnless((SPEC / "rules").is_dir(), "no agtmls-spec checkout beside this repo")
    def test_a_snapshot_that_drifted_from_the_spec_is_caught(self) -> None:
        spec = self.tmp / "spec"
        shutil.copytree(SPEC / "rules", spec / "rules")
        target = spec / "rules" / "AGT-INJ-006.toml"
        target.write_text(
            target.read_text(encoding="utf-8").replace("do\\s+anything", "do\\s+everything"),
            encoding="utf-8",
        )
        code, output = run_main(self.module, "--check", "--from", str(spec), "--commit", "0" * 40)
        self.assertNotEqual(code, 0, output)
        self.assertIn("AGT-INJ-006", output)


if __name__ == "__main__":
    unittest.main()
