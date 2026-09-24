# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Chapter 10 attestations: the spec's vectors, reproduced byte for byte."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from .support import ROOT, load_script, retarget, run_main

sys.path.insert(0, str(ROOT / "scripts"))
from _lib import attestations, rules  # needs the scripts path first

VECTORS = ROOT / "tests" / "fixtures" / "spec-attestations"


class SpecVectorTests(unittest.TestCase):
    """The spec's corpus/attestations, rebuilt from the same inputs."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="agtmls-attest-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.inputs = json.loads((VECTORS / "inputs.json").read_text(encoding="utf-8"))

    def materialise(self, name: str, files: dict[str, str]) -> Path:
        skill = self.tmp / name
        for rel, text in files.items():
            (skill / rel).parent.mkdir(parents=True, exist_ok=True)
            (skill / rel).write_text(text, encoding="utf-8")
        skill.mkdir(exist_ok=True)
        return skill

    def test_manifest_vectors(self) -> None:
        cases = {c["name"]: c for c in json.loads((VECTORS / "digest-cases.json").read_text(encoding="utf-8"))["cases"]}
        for item in self.inputs["manifests"]:
            with self.subTest(vector=item["vector"]):
                skill = self.materialise(item["digest_case"], cases[item["digest_case"]]["files"])
                rendered = attestations.render(attestations.manifest_statement(item["skill"], skill))
                self.assertEqual(rendered, (VECTORS / item["vector"]).read_text(encoding="utf-8"))

    def test_capabilities_vectors(self) -> None:
        """Their subject digests are placeholders, so the digest is passed in."""
        for item in self.inputs["capabilities"]:
            with self.subTest(vector=item["vector"]):
                skill = self.materialise(item["skill"], item["files"])
                statement = attestations.capabilities_statement(item["skill"], skill, digest=item["digest"])
                self.assertEqual(attestations.render(statement), (VECTORS / item["vector"]).read_text(encoding="utf-8"))


class CapabilityTableTests(unittest.TestCase):
    def test_the_table_comes_from_the_spec_snapshot(self) -> None:
        cap = next(r for r in rules.RULES if r["id"] == "AGT-CAP-001")
        self.assertEqual(rules.TOOL_CAPABILITIES, cap["tool_capabilities"])
        self.assertEqual(rules.TOOL_CAPABILITIES["Bash"], "executes_commands")

    def test_a_snapshot_without_the_table_is_refused(self) -> None:
        with self.assertRaises(SystemExit) as caught:
            rules.tool_capabilities([{"id": "AGT-CAP-001"}])
        self.assertIn("tool_capabilities", str(caught.exception))


class RenderTests(unittest.TestCase):
    def test_rendering_is_canonical(self) -> None:
        self.assertEqual(attestations.render({"b": 1, "a": "é"}), '{\n  "a": "é",\n  "b": 1\n}\n')

    def test_a_skill_without_metadata_declares_an_empty_policy(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            skill = Path(raw)
            (skill / "SKILL.md").write_text('---\nname: x\ndescription: Use when x.\nallowed-tools: "Bash"\n---\n', encoding="utf-8")
            predicate = attestations.capabilities_statement("x", skill)["predicate"]
        self.assertEqual(predicate["declared_policy"], {})
        self.assertEqual(predicate["escalations"], [{"capability": "executes_commands", "tool": "Bash"}])


class GeneratorTests(unittest.TestCase):
    """generate-skill-manifests.py over a copy of the registry."""

    @classmethod
    def setUpClass(cls) -> None:
        from .support import registry_fixture

        cls._workspace = Path(tempfile.mkdtemp(prefix="agtmls-attest-gen-"))
        cls.fixture = registry_fixture(cls._workspace / "tree")
        cls.module = load_script("generate-skill-manifests.py")
        retarget(cls.module, cls.fixture)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._workspace, ignore_errors=True)

    def test_write_then_check_is_clean_and_idempotent(self) -> None:
        self.assertEqual(run_main(self.module, "--write")[0], 0)
        first = {p: p.read_bytes() for p in sorted((self.fixture / "attestations").rglob("*.json"))}
        self.assertTrue(first)
        self.assertEqual(run_main(self.module, "--write")[0], 0)
        self.assertEqual(first, {p: p.read_bytes() for p in sorted((self.fixture / "attestations").rglob("*.json"))})
        code, output = run_main(self.module, "--check")
        self.assertEqual(code, 0, output)

    def test_an_edited_skill_makes_check_fail(self) -> None:
        run_main(self.module, "--write")
        skill = next(p for p in sorted((self.fixture / "skills").iterdir()) if (p / "SKILL.md").exists())
        original = (skill / "SKILL.md").read_text(encoding="utf-8")
        self.addCleanup((skill / "SKILL.md").write_text, original, encoding="utf-8")
        (skill / "SKILL.md").write_text(original + "\nedited\n", encoding="utf-8")
        code, output = run_main(self.module, "--check")
        self.assertEqual(code, 1)
        self.assertIn(f"attestations/{skill.name}/manifest.intoto.json", output)

    def test_a_stale_attestation_for_a_removed_skill_fails(self) -> None:
        run_main(self.module, "--write")
        stray = self.fixture / "attestations" / "no-such-skill" / "manifest.intoto.json"
        stray.parent.mkdir(parents=True, exist_ok=True)
        stray.write_text("{}\n", encoding="utf-8")
        self.addCleanup(shutil.rmtree, stray.parent, True)
        code, output = run_main(self.module, "--check")
        self.assertEqual(code, 1)
        self.assertIn("no-such-skill", output)

    def test_no_mode_prints_usage(self) -> None:
        self.assertEqual(run_main(self.module)[0], 2)


if __name__ == "__main__":
    unittest.main()
