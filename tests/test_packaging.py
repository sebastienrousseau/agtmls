# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The wheel, the plugin manifests, and the index they are built from."""

from __future__ import annotations

import json
import tempfile
import textwrap
import unittest
from pathlib import Path

from .support import (  # noqa: F401  (used by the cases below)
    CLI,
    ROOT,
    load_script,
    skill_text,
)


class PackagingTests(unittest.TestCase):
    """validate-packaging.py — the wheel must carry a usable registry."""

    def setUp(self) -> None:
        self.mod = load_script("validate-packaging.py")
        self.text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    def test_fallback_toml_parser_matches_the_real_one(self) -> None:
        # This path only executes on Python 3.10; exercise it everywhere so it
        # cannot rot unnoticed.
        parsed = self.mod.parse_force_include(self.text)
        self.assertEqual(parsed["skills"], "agtmls/_registry/skills")
        try:
            import tomllib
        except ModuleNotFoundError:  # pragma: no cover - 3.10 only
            return
        real = tomllib.loads(self.text)["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]
        self.assertEqual(parsed, real)

    def test_fallback_parser_ignores_other_sections(self) -> None:
        text = textwrap.dedent(
            """
            [tool.hatch.build.targets.wheel.force-include]
            "skills" = "agtmls/_registry/skills"

            [tool.other]
            "skills" = "somewhere/else"
            """
        )
        self.assertEqual(self.mod.parse_force_include(text), {"skills": "agtmls/_registry/skills"})

    def test_every_runtime_path_is_bundled(self) -> None:
        parsed = self.mod.parse_force_include(self.text)
        for required in self.mod.REQUIRED:
            self.assertIn(required, parsed, f"{required} would be missing from the wheel")

    def test_registry_layout_makes_script_roots_resolve(self) -> None:
        # scripts/*.py compute ROOT as parent.parent, so scripts must land one
        # level under the registry root inside the wheel.
        parsed = self.mod.parse_force_include(self.text)
        self.assertEqual(parsed["scripts"], f"{self.mod.PREFIX}/scripts")


class PluginManifestTests(unittest.TestCase):
    """Manifest generation and the flat-tree invariant it depends on."""

    def setUp(self) -> None:
        self.gen = load_script("generate-plugin-manifests.py")
        self.val = load_script("validate-plugin-manifest.py")
        self.plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))

    def test_flat_tree_needs_only_the_skills_root(self) -> None:
        self.assertEqual(self.gen.skill_paths(), ["./skills"])
        self.assertEqual(self.val.required_skill_paths(), {"./skills"})

    def test_no_skill_is_nested(self) -> None:
        nested = list((ROOT / "skills").glob("*/*/SKILL.md"))
        self.assertEqual(nested, [], f"nested skills are invisible to runtimes: {nested}")

    def test_every_declared_manifest_is_generated(self) -> None:
        providers = json.loads((ROOT / "providers.json").read_text(encoding="utf-8"))
        declared = {p for spec in providers["plugin_targets"].values() for p in spec["manifest_files"]}
        self.assertEqual(declared, set(self.gen.render(self.plugin)))

    def test_generated_manifests_carry_the_plugin_version(self) -> None:
        rendered = self.gen.render(self.plugin)
        self.assertEqual(json.loads(rendered[".codex-plugin/plugin.json"])["version"], self.plugin["version"])

    def test_antigravity_manifest_uses_its_own_schema(self) -> None:
        rendered = json.loads(self.gen.render(self.plugin)["plugin.json"])
        self.assertIn("antigravity.google", rendered["$schema"])

    def test_reserved_marketplace_names_are_known(self) -> None:
        self.assertIn("claude-plugins-official", self.val.RESERVED_MARKETPLACES)

    def test_skill_path_check_rejects_a_missing_root(self) -> None:
        errors: list[str] = []
        self.val.check_skill_paths("test skills", "./commands", errors)
        self.assertTrue(any("omits bundle path" in e for e in errors), errors)


class IndexGenerationTests(unittest.TestCase):
    """generate-skill-index.py — what every export inherits."""

    def setUp(self) -> None:
        self.mod = load_script("generate-skill-index.py")

    def test_unquote_strips_double_quotes(self) -> None:
        self.assertEqual(self.mod.unquote('"hello"'), "hello")

    def test_unquote_handles_escaped_inner_quotes(self) -> None:
        self.assertEqual(self.mod.unquote('"say \\"hi\\""'), 'say "hi"')

    def test_unquote_leaves_bare_scalars_alone(self) -> None:
        self.assertEqual(self.mod.unquote("hello"), "hello")
        self.assertEqual(self.mod.unquote("it's fine"), "it's fine")

    def test_parse_frontmatter_unquotes_descriptions(self) -> None:
        fields = self.mod.parse_frontmatter(skill_text('name: d\ndescription: "quoted"'))
        self.assertEqual(fields["description"], "quoted")

    def test_skill_kind_derives_from_metadata_not_path(self) -> None:
        self.assertEqual(self.mod.skill_kind({"bundle": None}), ("general", None))
        self.assertEqual(self.mod.skill_kind({"bundle": "noyalib"}), ("project", "noyalib"))
        self.assertEqual(self.mod.skill_kind({}), ("general", None))

    def test_index_descriptions_carry_no_yaml_quotes(self) -> None:
        index = json.loads((ROOT / "index.json").read_text(encoding="utf-8"))
        for skill in index["skills"]:
            self.assertFalse(
                skill["description"].startswith('"'),
                f"{skill['name']} description leaked its YAML quotes",
            )


class RouterParsingTests(unittest.TestCase):
    """run-trigger-evals.py — the description extractor the evals depend on."""

    def setUp(self) -> None:
        self.mod = load_script("run-trigger-evals.py")

    def test_description_stops_at_the_next_key(self) -> None:
        text = skill_text('name: d\ndescription: "the description"\nlicense: MIT\nallowed-tools: "Bash"')
        with tempfile.TemporaryDirectory() as tmp:
            md = Path(tmp) / "SKILL.md"
            md.write_text(text, encoding="utf-8")
            got = self.mod.description_of(md)
        self.assertIn("the description", got)
        self.assertNotIn("MIT", got)
        self.assertNotIn("Bash", got)

    def test_tokenizer_keeps_content_words(self) -> None:
        self.assertIn("harness", self.mod.toks("port rust golden harness"))

    def test_tokenizer_drops_stopwords(self) -> None:
        self.assertNotIn("the", self.mod.toks("the harness"))
