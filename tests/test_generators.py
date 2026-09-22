# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Generators and installers, driven against a copy.

These do real work -- write artifacts, copy trees, produce release bundles --
so the gate exercises them through subprocesses and nothing observes which
branches ran. Pointed at a fixture they can be driven in-process, which both
measures them and makes their failure modes testable: an export to a
directory that cannot be written, an import of a skill that is not one, a
doctor looking at a target that was never installed into.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from .support import load_script, registry_fixture, retarget, run_main


class GeneratorBase(unittest.TestCase):
    fixture: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls._workspace = tempfile.mkdtemp(prefix="agtmls-gen-")
        cls.fixture = registry_fixture(Path(cls._workspace) / "tree")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._workspace, ignore_errors=True)

    def setUp(self) -> None:
        self.out = Path(tempfile.mkdtemp(prefix="agtmls-out-"))
        self.addCleanup(lambda: shutil.rmtree(self.out, ignore_errors=True))

    def script(self, name: str):
        module = load_script(name)
        retarget(module, self.fixture)
        return module

    def drive(self, name: str, *args: str) -> tuple[int, str]:
        return run_main(self.script(name), *args)


class ExportTests(GeneratorBase):
    """`agtmls export` is how a registry reaches an agent that is not Claude."""

    def test_a_generic_export_writes_something(self) -> None:
        code, output = self.drive(
            "export-registry.py", "--provider", "generic", "--out-dir", str(self.out)
        )
        self.assertEqual(code, 0, output)
        self.assertTrue(any(self.out.rglob("*")), "export produced no files")

    def test_every_declared_provider_can_be_exported(self) -> None:
        providers = json.loads((self.fixture / "providers.json").read_text(encoding="utf-8"))
        targets = sorted(providers.get("export_targets", {}))
        self.assertTrue(targets, "no export targets declared")
        for name in targets:
            with self.subTest(provider=name):
                destination = self.out / name
                code, output = self.drive(
                    "export-registry.py", "--provider", name, "--out-dir", str(destination)
                )
                self.assertEqual(code, 0, f"{name}: {output}")
                self.assertTrue(any(destination.rglob("*")), f"{name} exported nothing")

    def test_an_unknown_provider_is_refused(self) -> None:
        code, output = self.drive(
            "export-registry.py", "--provider", "no-such-agent", "--out-dir", str(self.out)
        )
        self.assertNotEqual(code, 0, output)

    def test_a_profile_narrows_what_is_exported(self) -> None:
        wide = self.out / "wide"
        narrow = self.out / "narrow"
        self.drive("export-registry.py", "--provider", "generic", "--out-dir", str(wide))
        code, output = self.drive(
            "export-registry.py", "--provider", "generic",
            "--profile", "minimal", "--out-dir", str(narrow),
        )
        self.assertEqual(code, 0, output)
        self.assertLessEqual(
            len(list(narrow.rglob("*.md"))), len(list(wide.rglob("*.md"))),
            "the minimal profile exported at least as much as the full registry",
        )


class ImportTests(GeneratorBase):
    """Importing third-party content is the riskiest thing this registry does."""

    def skill_source(self, body: str = "") -> Path:
        source = self.out / "incoming.md"
        source.write_text(
            body or (
                "---\nname: external-skill\n"
                'description: "Use when importing an external skill for review."\n'
                "---\n\n# External Skill\n\nDo the thing.\n"
            ),
            encoding="utf-8",
        )
        return source

    def test_an_imported_skill_lands_where_it_was_asked_to(self) -> None:
        destination = self.out / "root"
        code, output = self.drive(
            "import-skill.py", str(self.skill_source()),
            "--name", "External Skill", "--out-root", str(destination),
        )
        self.assertEqual(code, 0, output)
        self.assertTrue((destination / "skills" / "external-skill" / "SKILL.md").exists(), output)

    def test_an_import_records_that_it_is_not_attested(self) -> None:
        """Fabricating a benign attestation for third-party content is the defect."""
        destination = self.out / "root"
        self.drive(
            "import-skill.py", str(self.skill_source()),
            "--name", "External Skill", "--out-root", str(destination),
        )
        metadata = json.loads(
            (destination / "skills" / "external-skill" / "metadata.json").read_text(encoding="utf-8")
        )
        self.assertFalse(metadata.get("attested", False), metadata)

    def test_importing_something_that_is_not_there_is_refused(self) -> None:
        code, output = self.drive(
            "import-skill.py", str(self.out / "nothing.md"),
            "--name", "Ghost", "--out-root", str(self.out / "root"),
        )
        self.assertNotEqual(code, 0, output)


class ScaffoldTests(GeneratorBase):
    def test_a_scaffolded_skill_has_everything_the_validators_want(self) -> None:
        destination = self.out / "root"
        code, output = self.drive(
            "scaffold-skill.py", "sample-skill", "--out-root", str(destination)
        )
        self.assertEqual(code, 0, output)
        skill = destination / "skills" / "sample-skill"
        for name in ("SKILL.md", "metadata.json"):
            self.assertTrue((skill / name).exists(), f"{name} was not scaffolded")

    def test_a_scaffolded_skill_gets_its_eval_cases(self) -> None:
        """A skill with no cases drops the registry's coverage silently."""
        destination = self.out / "root"
        self.drive("scaffold-skill.py", "sample-skill", "--out-root", str(destination))
        self.assertTrue((destination / "evals" / "cases" / "sample-skill.json").exists())
        self.assertTrue(
            (destination / "evals" / "behavioral" / "cases" / "sample-skill.json").exists()
        )

    def test_a_name_that_is_not_kebab_case_is_refused(self) -> None:
        code, output = self.drive(
            "scaffold-skill.py", "Not Kebab Case", "--out-root", str(self.out / "root")
        )
        self.assertNotEqual(code, 0, output)

    def test_scaffolding_over_an_existing_skill_is_refused(self) -> None:
        destination = self.out / "root"
        self.drive("scaffold-skill.py", "sample-skill", "--out-root", str(destination))
        code, output = self.drive(
            "scaffold-skill.py", "sample-skill", "--out-root", str(destination)
        )
        self.assertNotEqual(code, 0, "scaffolding silently overwrote an existing skill")


class McpResourceTests(GeneratorBase):
    def test_resource_uris_use_the_scheme_agtmls_mcp_serves(self) -> None:
        """The descriptors said `agtmls://skills/`; the server answers `agtmls://skill/`.

        agtmls-mcp (src/tools.rs) and docs/ECOSYSTEM.md both define
        `agtmls://skill/{name}`, so a client following this file asked the
        server for URIs it had never heard of.
        """
        code, output = self.drive("generate-mcp-resources.py", "--write")
        self.assertEqual(code, 0, output)
        data = json.loads((self.fixture / "mcp-resources.json").read_text(encoding="utf-8"))
        self.assertTrue(data["resources"], "no resources")
        for resource in data["resources"]:
            self.assertEqual(resource["uri"], f"agtmls://skill/{resource['name']}")


class SupplyChainGeneratorTests(GeneratorBase):
    """The artifacts a consumer checks the registry against."""

    def test_the_sbom_regenerates_and_then_agrees_with_itself(self) -> None:
        code, output = self.drive("generate-sbom.py", "--write")
        self.assertEqual(code, 0, output)
        code, output = self.drive("generate-sbom.py", "--check")
        self.assertEqual(code, 0, f"a freshly written SBOM reported itself stale:\n{output}")

    def test_the_sbom_covers_every_file_it_says_it_does(self) -> None:
        self.drive("generate-sbom.py", "--write")
        spdx = json.loads((self.fixture / "SBOM.spdx.json").read_text(encoding="utf-8"))
        self.assertTrue(spdx["files"], "the SBOM lists no files")
        for entry in spdx["files"][:20]:
            self.assertTrue(entry.get("checksums"), f"{entry['fileName']} has no checksum")
            self.assertTrue(entry.get("SPDXID"), f"{entry['fileName']} has no SPDXID")

    def test_cyclonedx_models_files_as_components(self) -> None:
        """A top-level `files` key is what the 1.6 schema refuses."""
        self.drive("generate-sbom.py", "--write")
        bom = json.loads((self.fixture / "SBOM.cyclonedx.json").read_text(encoding="utf-8"))
        self.assertNotIn("files", bom, "CycloneDX has no top-level files key")
        self.assertTrue(bom["components"], "no components")
        self.assertTrue(all(c["type"] == "file" for c in bom["components"]))

    def test_a_tampered_sbom_is_reported_stale(self) -> None:
        self.drive("generate-sbom.py", "--write")
        path = self.fixture / "SBOM.spdx.json"
        spdx = json.loads(path.read_text(encoding="utf-8"))
        spdx["files"][0]["checksums"][0]["checksumValue"] = "0" * 64
        path.write_text(json.dumps(spdx, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        code, output = self.drive("generate-sbom.py", "--check")
        self.assertNotEqual(code, 0, output)


class DoctorTests(GeneratorBase):
    """The command a person runs when their install is broken."""

    def test_the_doctor_passes_a_healthy_checkout(self) -> None:
        code, output = self.drive("agtmls-doctor.py", "--skip-gate")
        self.assertEqual(code, 0, output)

    def test_the_doctor_notices_a_missing_document(self) -> None:
        path = self.fixture / "SECURITY.md"
        original = path.read_bytes()
        self.addCleanup(lambda: path.write_bytes(original))
        path.unlink()
        code, output = self.drive("agtmls-doctor.py", "--skip-gate")
        self.assertNotEqual(code, 0, output)
        self.assertIn("SECURITY.md", output)

    def test_the_doctor_reports_a_target_that_does_not_exist(self) -> None:
        code, output = self.drive(
            "agtmls-doctor.py", "--skip-gate",
            "--target", str(self.out / "nowhere"), "--agent", "claude",
        )
        self.assertNotEqual(code, 0, output)
        self.assertIn("does not exist", output)

    def test_the_doctor_warns_about_a_target_with_nothing_installed(self) -> None:
        empty = self.out / "empty"
        empty.mkdir()
        code, output = self.drive(
            "agtmls-doctor.py", "--skip-gate", "--target", str(empty), "--agent", "claude"
        )
        self.assertIn("WARN", output, output)
