# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Generated artifacts: provenance, the docs site, the manpage, completions.

Each of these is a file the gate compares against a fresh render, so each
generator has the same three duties: `--write` produces exactly what
`--check` then accepts, `--check` refuses a file that is stale or missing,
and whatever the artifact states is derived rather than typed. The gate runs
them only in the passing direction; these tests make them fail on purpose.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from unittest import mock

from .subset_support import SubsetCase


class ProvenanceTests(SubsetCase):
    """provenance.json is what a consumer reads to learn what a release holds."""

    SCRIPT = "generate-provenance.py"
    SUBSET = (
        "index.json", "checks.json", "mcp-resources.json",
        "SBOM.spdx.json", "SBOM.cyclonedx.json", "provenance.json",
    )

    def setUp(self) -> None:
        # SOURCE_DATE_EPOCH pins the stamp a fresh statement takes.
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ["SOURCE_DATE_EPOCH"] = "86400"

    def test_the_source_is_pinned_by_content_not_by_a_commit(self) -> None:
        """A squash merge gives the same tree a new commit; a digest survives it."""
        module = self.script()
        self.assertFalse(hasattr(module, "subprocess"), "provenance must not consult git")
        statement = module.render("2026-01-02T03:04:05Z")
        metadata = statement["predicate"]["runDetails"]["metadata"]
        self.assertEqual(metadata["startedOn"], "2026-01-02T03:04:05Z")
        self.assertEqual(metadata["finishedOn"], "2026-01-02T03:04:05Z")
        (dependency,) = statement["predicate"]["buildDefinition"]["resolvedDependencies"]
        sbom = hashlib.sha256(self.path("SBOM.spdx.json").read_bytes()).hexdigest()
        self.assertEqual(dependency["digest"], {"sha256": sbom})
        self.assertNotIn("gitCommit", json.dumps(statement))

    def test_the_subject_digest_moves_with_any_material(self) -> None:
        module = self.script()
        before = module.material_digest()
        self.preserve("checks.json")
        path = self.path("checks.json")
        path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
        self.assertNotEqual(module.material_digest(), before)

    def test_a_missing_material_is_refused_by_name(self) -> None:
        """A digest over fewer files than it claims would be a false statement."""
        self.preserve("mcp-resources.json")
        self.path("mcp-resources.json").unlink()
        module = self.script()
        with self.assertRaises(SystemExit) as caught:
            module.material_digest()
        self.assertIn("mcp-resources.json", str(caught.exception.code))

    def test_the_statement_is_an_unsigned_in_toto_envelope(self) -> None:
        """It must not be mistaken for the signed provenance release.yml emits."""
        statement = self.script().render("2026-01-02T03:04:05Z")
        self.assertEqual(statement["_type"], "https://in-toto.io/Statement/v1")
        self.assertFalse(statement["agtmls"]["signed"])
        version = json.loads(self.path("index.json").read_text(encoding="utf-8"))["registry_version"]
        self.assertEqual(statement["subject"][0]["name"], f"agtmls-{version}")
        checks = json.loads(self.path("checks.json").read_text(encoding="utf-8"))["checks"]
        self.assertEqual(statement["agtmls"]["checks"], checks)

    def test_write_then_check_agree_and_tampering_is_caught(self) -> None:
        self.preserve("provenance.json")
        code, output = self.drive("--write", module=self.script())
        self.assertEqual((code, output.strip()), (0, "wrote provenance.json"))
        code, output = self.drive("--check", module=self.script())
        self.assertEqual(code, 0, output)
        self.assertIn("OK: provenance is current", output)
        # A changed material is a different statement: stale.
        self.preserve("checks.json")
        checks = self.path("checks.json")
        checks.write_text(checks.read_text(encoding="utf-8") + " ", encoding="utf-8")
        code, output = self.drive("--check")
        self.assertEqual(code, 1, output)
        self.assertIn("provenance.json is stale", output)

    def test_check_fails_when_the_statement_is_missing(self) -> None:
        self.preserve("provenance.json")
        self.path("provenance.json").unlink()
        code, output = self.drive("--check", module=self.script())
        self.assertEqual(code, 1, output)

    def test_no_flag_prints_the_statement_and_writes_nothing(self) -> None:
        self.preserve("provenance.json")
        before = self.path("provenance.json").read_bytes()
        module = self.script()
        code, output = self.drive(module=module)
        self.assertEqual(code, 0)
        # Exactly what --write would store, stamp included.
        self.assertEqual(output, module.stamp.settle(module.OUT, module.render, module.built_on))
        self.assertEqual(self.path("provenance.json").read_bytes(), before)


class DocsSiteTests(SubsetCase):
    """site/index.html is the catalog a person browses; it renders registry data."""

    SCRIPT = "generate-docs-site.py"
    SUBSET = ("index.json", "profiles.json", "providers.json", "site")

    def test_write_then_check_agree(self) -> None:
        self.preserve("site/index.html")
        code, output = self.drive("--write")
        self.assertEqual((code, output.strip()), (0, "wrote site/index.html"))
        code, output = self.drive("--check")
        self.assertEqual(code, 0, output)
        self.assertIn("OK: docs site is current", output)

    def test_a_hand_edited_page_is_stale(self) -> None:
        self.preserve("site/index.html")
        self.drive("--write")
        page = self.path("site/index.html")
        page.write_text(page.read_text(encoding="utf-8").replace("Skills", "Skils", 1), encoding="utf-8")
        code, output = self.drive("--check")
        self.assertEqual(code, 1, output)
        self.assertIn("missing or stale", output)

    def test_a_missing_page_is_reported_and_write_recreates_its_directory(self) -> None:
        self.preserve("site")
        (self.path("site/index.html")).unlink()
        self.path("site").rmdir()
        self.assertEqual(self.drive("--check")[0], 1)
        self.assertEqual(self.drive("--write")[0], 0)
        self.assertTrue(self.path("site/index.html").exists())

    def test_skill_data_is_escaped_not_injected(self) -> None:
        """Every cell is registry data; unescaped, a skill name is markup."""
        self.preserve("index.json")
        index = json.loads(self.path("index.json").read_text(encoding="utf-8"))
        index["skills"] = [{"name": "<script>alert(1)</script>", "path": "skills/x"}]
        self.path("index.json").write_text(json.dumps(index), encoding="utf-8")
        page = self.script().render()
        self.assertNotIn("<script>", page)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)
        # Fields a skill may omit render as explicit defaults, not as errors.
        row = page.split("<tbody>")[1].split("</tbody>")[0]
        self.assertIn("<td>general</td><td>0</td><td>unknown</td>", row)

    def test_no_flag_prints_the_page(self) -> None:
        module = self.script()
        code, output = self.drive(module=module)
        self.assertEqual((code, output), (0, module.render()))


class ManpageTests(SubsetCase):
    """agtmls.1 carries the version, which used to be patched in by hand."""

    SCRIPT = "generate-manpage.py"
    SUBSET = (".claude-plugin", "share")

    def bump(self, version: str) -> None:
        self.preserve(".claude-plugin/plugin.json")
        path = self.path(".claude-plugin/plugin.json")
        plugin = json.loads(path.read_text(encoding="utf-8"))
        plugin["version"] = version
        path.write_text(json.dumps(plugin), encoding="utf-8")

    def test_the_version_is_read_from_plugin_json(self) -> None:
        self.bump("9.8.7")
        self.preserve("share/man/man1/agtmls.1")
        code, output = self.drive("--write")
        self.assertEqual((code, output.strip()), (0, "wrote share/man/man1/agtmls.1"))
        page = self.path("share/man/man1/agtmls.1").read_text(encoding="utf-8")
        self.assertIn('"agtmls 9.8.7"', page)
        code, output = self.drive("--check")
        self.assertEqual(code, 0, output)
        self.assertIn("OK: manpage is current", output)

    def test_a_version_bump_makes_the_committed_page_stale(self) -> None:
        self.assertEqual(self.drive("--check")[0], 0, "the committed manpage should be current")
        self.bump("9.8.7")
        code, output = self.drive("--check")
        self.assertEqual(code, 1, output)
        self.assertIn("stale manpage at share/man/man1/agtmls.1", output)

    def test_a_missing_page_is_stale(self) -> None:
        self.preserve("share/man/man1/agtmls.1")
        self.path("share/man/man1/agtmls.1").unlink()
        self.assertEqual(self.drive("--check")[0], 1)

    def test_no_flag_is_a_usage_error(self) -> None:
        code, output = self.drive()
        self.assertEqual(code, 2)
        self.assertIn("--check", output)


class CompletionTests(SubsetCase):
    """Completions that disagree with the CLI teach the wrong surface."""

    SCRIPT = "generate-completions.py"
    SUBSET = ("completions",)
    FILES = ("agtmls.bash", "_agtmls", "agtmls.fish")

    def test_write_then_check_agree(self) -> None:
        self.preserve("completions")
        code, output = self.drive("--write")
        self.assertEqual(code, 0, output)
        for name in self.FILES:
            self.assertIn(f"wrote completions/{name}", output)
        code, output = self.drive("--check")
        self.assertEqual(code, 0, output)
        self.assertIn("(3 files)", output)

    def test_every_shell_offers_every_subcommand(self) -> None:
        module = self.script()
        self.assertIn("verify", module.SUBCOMMANDS, "the command that went missing once")
        for shell, text in (
            ("bash", module.render_bash()),
            ("zsh", module.render_zsh()),
            ("fish", module.render_fish()),
        ):
            for sub in module.SUBCOMMANDS:
                with self.subTest(shell=shell, sub=sub):
                    self.assertIn(sub, text)
        for agent in module.native_agents():
            self.assertIn(agent, module.render_bash())

    def test_a_stale_file_is_named(self) -> None:
        self.preserve("completions")
        self.path("completions/agtmls.fish").write_text("# hand edit\n", encoding="utf-8")
        code, output = self.drive("--check")
        self.assertEqual(code, 1, output)
        self.assertIn("stale shell completions: agtmls.fish", output)

    def test_a_missing_file_is_stale(self) -> None:
        self.preserve("completions")
        self.path("completions/_agtmls").unlink()
        code, output = self.drive("--check")
        self.assertEqual(code, 1, output)
        self.assertIn("_agtmls", output)

    def test_no_flag_is_a_usage_error(self) -> None:
        self.assertEqual(self.drive()[0], 2)

    def test_subcommands_are_found_past_other_positionals(self) -> None:
        """argparse keeps subcommands in the positionals group, after any positional."""
        module = self.script()
        parser = argparse.ArgumentParser()
        parser.add_argument("target")
        sub = parser.add_subparsers()
        sub.add_parser("zeta")
        sub.add_parser("alpha")
        module.build_parser = lambda: parser
        self.assertEqual(module.subcommands(), ["alpha", "zeta"])

    def test_a_parser_without_subcommands_is_refused(self) -> None:
        """Empty completions would install silently; the refusal names the cause."""
        module = self.script()
        module.build_parser = argparse.ArgumentParser
        with self.assertRaises(SystemExit) as caught:
            module.subcommands()
        self.assertIn("declares no subcommands", str(caught.exception.code))


class CatalogAndResourceTests(SubsetCase):
    """CATALOG.md and mcp-resources.json are both views of index.json."""

    SUBSET = ("index.json", "CATALOG.md", "mcp-resources.json")

    def test_the_catalog_writes_what_check_accepts(self) -> None:
        self.preserve("CATALOG.md")
        self.path("CATALOG.md").write_text("stale\n", encoding="utf-8")
        self.assertEqual(self.drive("--check", module=self.script("generate-catalog.py"))[0], 1)
        code, output = self.drive("--write", module=self.script("generate-catalog.py"))
        self.assertEqual((code, output.strip()), (0, "wrote CATALOG.md"))
        code, output = self.drive("--check", module=self.script("generate-catalog.py"))
        self.assertEqual(code, 0, output)

    def test_the_catalog_prints_without_writing(self) -> None:
        module = self.script("generate-catalog.py")
        code, output = self.drive(module=module)
        self.assertEqual((code, output), (0, module.render()))
        index = json.loads(self.path("index.json").read_text(encoding="utf-8"))
        self.assertIn(f"Skills: `{index['skill_count']}`", output)

    def test_the_resource_list_prints_and_detects_staleness(self) -> None:
        module = self.script("generate-mcp-resources.py")
        code, output = self.drive(module=module)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output), module.render())
        self.preserve("mcp-resources.json")
        self.path("mcp-resources.json").write_text("{}\n", encoding="utf-8")
        code, output = self.drive("--check", module=self.script("generate-mcp-resources.py"))
        self.assertEqual(code, 1, output)
        self.assertIn("mcp-resources.json is stale", output)
