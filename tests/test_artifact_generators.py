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
import json
import os
from unittest import mock

from .subset_support import SubsetCase, fake_git


class ProvenanceTests(SubsetCase):
    """provenance.json is what a consumer reads to learn what a release holds."""

    SCRIPT = "generate-provenance.py"
    SUBSET = (
        "index.json", "checks.json", "mcp-resources.json",
        "SBOM.spdx.json", "SBOM.cyclonedx.json", "provenance.json",
    )

    def setUp(self) -> None:
        # SOURCE_DATE_EPOCH, if the caller's shell set it, would bypass git.
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop("SOURCE_DATE_EPOCH", None)

    def module_with_git(self, stdout=""):
        module = self.script()
        module.subprocess = fake_git(stdout)
        return module

    def test_dates_and_ref_come_from_the_last_authored_commit(self) -> None:
        """The pathspec is the convergence property: no generated artifact in it.

        Deriving the date from SBOM.spdx.json meant committing a regenerated
        SBOM moved provenance's timestamp, so the pair never settled.
        """
        module = self.module_with_git(
            lambda argv: "2026-01-02T03:04:05Z\n" if "--format=%cd" in argv else "c0ffee\n"
        )
        statement = module.render()
        metadata = statement["predicate"]["runDetails"]["metadata"]
        self.assertEqual(metadata["startedOn"], "2026-01-02T03:04:05Z")
        self.assertEqual(metadata["finishedOn"], "2026-01-02T03:04:05Z")
        dependency = statement["predicate"]["buildDefinition"]["resolvedDependencies"][0]
        self.assertEqual(dependency["digest"], {"gitCommit": "c0ffee"})
        for argv in module.subprocess.calls:
            pathspec = argv[argv.index("--") + 1:]
            self.assertEqual(pathspec, [*module.SOURCE_DIRS, *module.SOURCE_FILES])
            for generated in ("SBOM.spdx.json", "SBOM.cyclonedx.json", "provenance.json"):
                self.assertNotIn(generated, pathspec)

    def test_source_date_epoch_overrides_git_for_the_timestamp(self) -> None:
        """Reproducible builds pin the clock; git must not be asked for it."""
        os.environ["SOURCE_DATE_EPOCH"] = "86400"
        module = self.module_with_git("c0ffee\n")
        self.assertEqual(module.built_at(), "1970-01-02T00:00:00Z")
        self.assertEqual(module.subprocess.calls, [])

    def test_outside_git_the_statement_says_so_instead_of_inventing(self) -> None:
        """An sdist has no history; the fallback is the epoch and `unknown`."""
        module = self.module_with_git("")
        self.assertEqual(module.built_at(), "1970-01-01T00:00:00Z")
        self.assertEqual(module.source_ref(), "unknown")

    def test_the_subject_digest_moves_with_any_material(self) -> None:
        module = self.module_with_git("")
        before = module.material_digest()
        self.preserve("checks.json")
        path = self.path("checks.json")
        path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
        self.assertNotEqual(module.material_digest(), before)

    def test_a_missing_material_is_refused_by_name(self) -> None:
        """A digest over fewer files than it claims would be a false statement."""
        self.preserve("mcp-resources.json")
        self.path("mcp-resources.json").unlink()
        module = self.module_with_git("")
        with self.assertRaises(SystemExit) as caught:
            module.material_digest()
        self.assertIn("mcp-resources.json", str(caught.exception.code))

    def test_the_statement_is_an_unsigned_in_toto_envelope(self) -> None:
        """It must not be mistaken for the signed provenance release.yml emits."""
        statement = self.module_with_git("").render()
        self.assertEqual(statement["_type"], "https://in-toto.io/Statement/v1")
        self.assertFalse(statement["agtmls"]["signed"])
        version = json.loads(self.path("index.json").read_text(encoding="utf-8"))["registry_version"]
        self.assertEqual(statement["subject"][0]["name"], f"agtmls-{version}")
        checks = json.loads(self.path("checks.json").read_text(encoding="utf-8"))["checks"]
        self.assertEqual(statement["agtmls"]["checks"], checks)

    def test_write_then_check_agree_and_tampering_is_caught(self) -> None:
        self.preserve("provenance.json")
        code, output = self.drive("--write", module=self.module_with_git("x\n"))
        self.assertEqual((code, output.strip()), (0, "wrote provenance.json"))
        code, output = self.drive("--check", module=self.module_with_git("x\n"))
        self.assertEqual(code, 0, output)
        self.assertIn("OK: provenance is current", output)
        # A different answer from git is a different statement: stale.
        code, output = self.drive("--check", module=self.module_with_git("y\n"))
        self.assertEqual(code, 1, output)
        self.assertIn("provenance.json is stale", output)

    def test_check_fails_when_the_statement_is_missing(self) -> None:
        self.preserve("provenance.json")
        self.path("provenance.json").unlink()
        code, output = self.drive("--check", module=self.module_with_git("x\n"))
        self.assertEqual(code, 1, output)

    def test_no_flag_prints_the_statement_and_writes_nothing(self) -> None:
        self.preserve("provenance.json")
        before = self.path("provenance.json").read_bytes()
        module = self.module_with_git("x\n")
        code, output = self.drive(module=module)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output), module.render())
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
