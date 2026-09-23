# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""BENCHMARKS.md states only what benchmarks/results/ recorded.

The scaling table said digest grew x9.5 and pairwise scoring x73.4 for ten
times the registry. scaling.json, re-measured since, said x7.02 and x110.62.
Nothing compared the two, which is exactly how laya-mlx's README came to
advertise latencies its own committed data did not support.

Every measured number in BENCHMARKS.md now sits inside a generated block that
records the sha256 of the results file it was rendered from, and the gate
fails if the block or the file moves without the other.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from .support import load_script, registry_fixture, retarget, run_main


class BenchmarkDocTests(unittest.TestCase):
    fixture: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls._workspace = tempfile.mkdtemp(prefix="agtmls-benchdoc-")
        cls.fixture = registry_fixture(Path(cls._workspace) / "tree")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._workspace, ignore_errors=True)

    def setUp(self) -> None:
        self.saved = {
            name: (self.fixture / name).read_bytes()
            for name in (
                "BENCHMARKS.md", "README.md",
                "benchmarks/results/scaling.json", "benchmarks/results/latency.json",
            )
        }
        self.addCleanup(self.restore)

    def restore(self) -> None:
        for name, data in self.saved.items():
            (self.fixture / name).write_bytes(data)

    def drive(self, *args: str) -> tuple[int, str]:
        module = load_script("generate-benchmarks-doc.py")
        retarget(module, self.fixture)
        return run_main(module, *args)

    def test_the_committed_document_matches_its_results(self) -> None:
        code, output = self.drive("--check")
        self.assertEqual(code, 0, output)

    def test_results_that_moved_without_the_document_are_caught(self) -> None:
        path = self.fixture / "benchmarks/results/scaling.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["growth"]["pairwise"] = 999.0
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        code, output = self.drive("--check")
        self.assertNotEqual(code, 0, output)
        self.assertIn("scaling", output)

    def test_a_hand_edited_number_is_caught(self) -> None:
        path = self.fixture / "BENCHMARKS.md"
        text = path.read_text(encoding="utf-8")
        latency = json.loads((self.fixture / "benchmarks/results/latency.json").read_text(encoding="utf-8"))
        p50 = f"{latency['workloads']['cli-list']['p50_ms']:.2f}"
        self.assertIn(p50, text)
        path.write_text(text.replace(p50, "1.00", 1), encoding="utf-8")
        code, output = self.drive("--check")
        self.assertNotEqual(code, 0, output)
        self.assertIn("latency", output)

    def test_write_repairs_what_check_rejects(self) -> None:
        path = self.fixture / "benchmarks/results/scaling.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["growth"]["pairwise"] = 999.0
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.assertEqual(self.drive("--write")[0], 0)
        code, output = self.drive("--check")
        self.assertEqual(code, 0, output)
        self.assertIn("999.00", (self.fixture / "BENCHMARKS.md").read_text(encoding="utf-8"))

    def test_a_hand_edited_readme_number_is_caught(self) -> None:
        """The front page is where a stale number does the most damage."""
        path = self.fixture / "README.md"
        text = path.read_text(encoding="utf-8")
        latency = json.loads((self.fixture / "benchmarks/results/latency.json").read_text(encoding="utf-8"))
        p50 = f"| {latency['workloads']['cli-list']['p50_ms']:.0f} ms P50 |"
        self.assertIn(p50, text)
        path.write_text(text.replace(p50, "| 1 ms P50 |", 1), encoding="utf-8")
        code, output = self.drive("--check")
        self.assertEqual(code, 1, output)
        self.assertIn("README.md block headline", output)
        self.assertEqual(self.drive("--write")[0], 0)
        self.assertIn(p50, path.read_text(encoding="utf-8"))

    def test_a_readme_without_its_block_cannot_be_written(self) -> None:
        path = self.fixture / "README.md"
        path.write_text("# AgtMLS\n", encoding="utf-8")
        code, output = self.drive("--write")
        self.assertEqual(code, 1, output)
        self.assertIn("headline: no generated block in README.md; add its markers first", output)
        self.assertEqual(path.read_text(encoding="utf-8"), "# AgtMLS\n")

    def test_a_block_in_the_wrong_document_is_unknown(self) -> None:
        path = self.fixture / "BENCHMARKS.md"
        path.write_text(path.read_text(encoding="utf-8") + '\n<!-- generated:headline sources="" -->\n<!-- /generated:headline -->\n', encoding="utf-8")
        code, output = self.drive("--check")
        self.assertEqual(code, 1, output)
        self.assertIn("BENCHMARKS.md block headline: unknown generated block", output)

    def test_a_document_with_no_generated_blocks_is_refused(self) -> None:
        (self.fixture / "BENCHMARKS.md").write_text("# Benchmarks\n\nhand-written\n", encoding="utf-8")
        code, output = self.drive("--check")
        self.assertNotEqual(code, 0, output)


if __name__ == "__main__":
    unittest.main()
