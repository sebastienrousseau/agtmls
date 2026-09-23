# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Plugin manifests and the SBOM: what other tools read about this registry.

A runtime installs AgtMLS by reading one of eight generated manifests, and a
scanner inventories it by reading the SBOM. Both are derived, so the defects
worth testing are the ones where the derivation silently stops tracking its
source: a version bump one runtime never sees, a new agent file missing from
a manifest, a covered directory that vanished without anyone noticing, a
timestamp that claims history an unpacked sdist does not have.
"""

from __future__ import annotations

import json
import os
from unittest import mock

from .subset_support import SubsetCase, fake_git

MANIFESTS = (
    ".agents/plugins/marketplace.json", ".codex-plugin/plugin.json",
    ".cursor-plugin/plugin.json", ".kimi-plugin/plugin.json",
    ".opencode/INSTALL.md", "gemini-extension.json", "GEMINI.md", "plugin.json",
)


class PluginManifestTests(SubsetCase):
    SCRIPT = "generate-plugin-manifests.py"
    SUBSET = (
        ".claude-plugin", "providers.json", "skills/using-agtmls/SKILL.md", "agents",
        ".agents", ".codex-plugin", ".cursor-plugin", ".kimi-plugin", ".opencode",
        "gemini-extension.json", "GEMINI.md", "plugin.json",
    )

    def setUp(self) -> None:
        self.preserve(*MANIFESTS)

    def test_the_committed_manifests_are_current(self) -> None:
        code, output = self.drive("--check")
        self.assertEqual(code, 0, output)
        self.assertIn("OK: 8 plugin manifest(s) current across 6 target(s)", output)

    def test_a_hand_edited_manifest_is_named_and_write_restores_it(self) -> None:
        path = self.path(".cursor-plugin/plugin.json")
        original = path.read_text(encoding="utf-8")
        path.write_text(original.replace('"AgtMLS"', '"Hand Edited"'), encoding="utf-8")
        code, output = self.drive("--check")
        self.assertEqual(code, 1, output)
        self.assertIn("FAIL: .cursor-plugin/plugin.json is stale", output)
        self.assertIn("FAIL: 1 stale manifest(s)", output)
        code, output = self.drive("--write")
        self.assertEqual((code, output.strip()), (0, "OK: 1 of 8 plugin manifest(s) regenerated"))
        self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_a_version_bump_reaches_every_manifest_that_carries_one(self) -> None:
        """The reason these are generated: one runtime left on the old version."""
        self.preserve(".claude-plugin/plugin.json")
        path = self.path(".claude-plugin/plugin.json")
        plugin = json.loads(path.read_text(encoding="utf-8"))
        plugin["version"] = "9.8.7"
        path.write_text(json.dumps(plugin), encoding="utf-8")
        code, output = self.drive("--check")
        self.assertEqual(code, 1, output)
        for rel in (".codex-plugin/plugin.json", ".cursor-plugin/plugin.json",
                    ".kimi-plugin/plugin.json", "gemini-extension.json"):
            self.assertIn(f"FAIL: {rel} is stale", output)
        self.assertEqual(self.drive("--write")[0], 0)
        for rel in (".codex-plugin/plugin.json", "gemini-extension.json"):
            self.assertEqual(json.loads(self.path(rel).read_text(encoding="utf-8"))["version"], "9.8.7")

    def test_a_new_agent_file_is_listed_by_path(self) -> None:
        """`agents` takes file paths; a directory string fails `claude plugin validate`."""
        self.preserve("agents")
        self.path("agents/zz-new.md").write_text("# New agent\n", encoding="utf-8")
        self.assertEqual(self.drive("--check")[0], 1)
        self.assertEqual(self.drive("--write")[0], 0)
        codex = json.loads(self.path(".codex-plugin/plugin.json").read_text(encoding="utf-8"))
        self.assertIn("./agents/zz-new.md", codex["agents"])
        self.assertEqual(codex["agents"], sorted(codex["agents"]))

    def test_providers_json_must_declare_exactly_the_generated_files(self) -> None:
        self.preserve("providers.json")
        path = self.path("providers.json")
        providers = json.loads(path.read_text(encoding="utf-8"))
        providers["plugin_targets"]["kimi"]["manifest_files"] = [".kimi-plugin/other.json"]
        path.write_text(json.dumps(providers), encoding="utf-8")
        code, output = self.drive("--write")
        self.assertEqual(code, 1, output)
        self.assertIn("manifest_files do not match generated set", output)
        self.assertIn("- .kimi-plugin/other.json", output)
        self.assertIn("- .kimi-plugin/plugin.json", output)

    def test_a_missing_router_skill_is_refused(self) -> None:
        """GEMINI.md @-includes it; a dangling include loads nothing, silently."""
        self.preserve("skills/using-agtmls/SKILL.md")
        self.path("skills/using-agtmls/SKILL.md").unlink()
        code, output = self.drive("--check")
        self.assertEqual(code, 1, output)
        self.assertIn("router skill missing: skills/using-agtmls/SKILL.md", output)

    def test_write_recreates_a_deleted_manifest_directory(self) -> None:
        self.preserve(".kimi-plugin")
        (self.path(".kimi-plugin/plugin.json")).unlink()
        self.path(".kimi-plugin").rmdir()
        code, output = self.drive("--write")
        self.assertEqual((code, output.strip()), (0, "OK: 1 of 8 plugin manifest(s) regenerated"))
        self.assertTrue(self.path(".kimi-plugin/plugin.json").exists())

    def test_one_of_check_or_write_is_required(self) -> None:
        self.assertEqual(self.drive()[0], 2)


class SbomCoverageTests(SubsetCase):
    """What the SBOM lists, and the date it claims, on a partial tree."""

    SCRIPT = "generate-sbom.py"
    SUBSET = (".claude-plugin", "templates", "LICENSE-MIT")

    def setUp(self) -> None:
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("SOURCE_DATE_EPOCH", None)

    def test_absent_paths_are_skipped_and_debris_is_excluded(self) -> None:
        """An sdist may lack a covered path; OS and interpreter debris is not content."""
        self.preserve("templates")
        (self.path("templates/.DS_Store")).write_bytes(b"\0")
        (self.path("templates/__pycache__")).mkdir()
        (self.path("templates/__pycache__/x.pyc")).write_bytes(b"\0")
        (self.path("templates/link.md")).symlink_to(self.path("templates/README.md"))
        module = self.script()
        listed = [p.relative_to(self.fixture).as_posix() for p in module.covered_paths()]
        self.assertEqual(listed, sorted(listed))
        self.assertIn("LICENSE-MIT", listed)
        self.assertIn("templates/skill/SKILL.md", listed)
        for excluded in ("templates/.DS_Store", "templates/__pycache__/x.pyc", "templates/link.md"):
            self.assertNotIn(excluded, listed)
        self.assertFalse(any(p.startswith(("skills/", "src/", "index.json")) for p in listed), listed)

    def test_the_date_is_asked_of_git_for_the_covered_top_level_paths(self) -> None:
        module = self.script()
        module.subprocess = fake_git("2026-05-06T07:08:09Z\n")
        paths = module.covered_paths()
        self.assertEqual(module.created_at(paths), "2026-05-06T07:08:09Z")
        (argv,) = module.subprocess.calls
        self.assertEqual(argv[argv.index("--") + 1:], ["LICENSE-MIT", "templates"])

    def test_without_history_the_date_is_the_epoch_not_an_invention(self) -> None:
        for label, git in (("no output", fake_git("")), ("no git", fake_git(raises=OSError))):
            with self.subTest(git=label):
                module = self.script()
                module.subprocess = git
                self.assertEqual(module.created_at(module.covered_paths()), "1970-01-01T00:00:00Z")

    def test_source_date_epoch_pins_the_date_without_asking_git(self) -> None:
        os.environ["SOURCE_DATE_EPOCH"] = "0"
        module = self.script()
        module.subprocess = fake_git("2026-05-06T07:08:09Z\n")
        self.assertEqual(module.created_at([]), "1970-01-01T00:00:00Z")
        self.assertEqual(module.subprocess.calls, [])

    def test_no_flag_prints_the_chosen_format(self) -> None:
        version = json.loads(self.path(".claude-plugin/plugin.json").read_text(encoding="utf-8"))["version"]
        module = self.script()
        module.subprocess = fake_git("")
        code, output = self.drive(module=module)
        self.assertEqual(code, 0, output)
        spdx = json.loads(output)
        self.assertEqual((spdx["spdxVersion"], spdx["name"]), ("SPDX-2.3", f"agtmls-{version}"))
        self.assertIn("./LICENSE-MIT", [f["fileName"] for f in spdx["files"]])
        code, output = self.drive("--format", "cyclonedx", module=module)
        self.assertEqual(code, 0, output)
        bom = json.loads(output)
        self.assertEqual((bom["bomFormat"], bom["specVersion"]), ("CycloneDX", "1.6"))
        self.assertFalse(self.path("SBOM.spdx.json").exists(), "printing must not write")
