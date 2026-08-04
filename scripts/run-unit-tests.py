#!/usr/bin/env python3
"""Unit tests for the registry tooling itself.

The 55-check gate validates repository *data*. These tests validate the
*validators* — the failure mode the gate cannot see is a checker that always
returns 0. Every test here is written to fail if the logic it covers is
weakened, not merely if it raises.

Run directly, or via `python3 scripts/agtmls.py check`.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "scripts" / "agtmls.py"


def load_script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(
        name.replace("-", "_").replace(".py", ""), path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def skill_text(frontmatter: str, body: str = "# Heading\n\ncontent\n") -> str:
    return f"---\n{frontmatter.strip()}\n---\n\n{body}"


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

    def test_metadata_file_list_is_derived_not_hardcoded(self) -> None:
        # A newly added skill must not be able to escape the version gate.
        module = load_script("validate-version-policy.py")
        covered = set(module.METADATA_FILES)
        for meta in (ROOT / "skills").glob("*/metadata.json"):
            self.assertIn(meta, covered, f"{meta.name} is outside the version gate")


class SkillContractTests(unittest.TestCase):
    """validate-skills.py — the agentskills.io spec gate."""

    VALID = 'name: demo-skill\ndescription: "Do a thing. Use when the thing is needed."'

    def setUp(self) -> None:
        self.mod = load_script("validate-skills.py")

    def check(self, frontmatter, body="# Heading\n\ncontent\n", name="demo-skill"):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / name
            skill_dir.mkdir()
            md = skill_dir / "SKILL.md"
            md.write_text(skill_text(frontmatter, body), encoding="utf-8")
            return self.mod.check(md)

    def test_valid_skill_has_no_errors(self) -> None:
        self.assertEqual(self.check(self.VALID), [])

    def test_rejects_key_outside_the_spec(self) -> None:
        errors = self.check(self.VALID + "\ndate: 2026-01-01")
        self.assertTrue(any("outside the Agent Skills spec" in e for e in errors), errors)

    def test_accepts_every_spec_key(self) -> None:
        frontmatter = (
            "name: demo-skill\n"
            'description: "Do a thing. Use when the thing is needed."\n'
            "license: MIT\n"
            'compatibility: "Requires git"\n'
            'allowed-tools: "Read Grep"\n'
            "metadata:\n"
            '  x-author: "someone"\n'
        )
        self.assertEqual(self.check(frontmatter), [])

    def test_rejects_name_directory_mismatch(self) -> None:
        errors = self.check(self.VALID, name="other-dir")
        self.assertTrue(any("!= directory name" in e for e in errors), errors)

    def test_rejects_consecutive_hyphens(self) -> None:
        errors = self.check('name: bad--name\ndescription: "Use when needed."', name="bad--name")
        self.assertTrue(any("kebab-case" in e for e in errors), errors)

    def test_rejects_overlong_name(self) -> None:
        long_name = "a" * (self.mod.MAX_NAME + 1)
        errors = self.check(
            f'name: {long_name}\ndescription: "Use when needed."', name=long_name
        )
        self.assertTrue(any("too long" in e for e in errors), errors)

    def test_rejects_overlong_description(self) -> None:
        desc = "Use when " + ("x" * self.mod.MAX_DESC)
        errors = self.check(f'name: demo-skill\ndescription: "{desc}"')
        self.assertTrue(any("`description` too long" in e for e in errors), errors)

    def test_rejects_description_without_trigger_cue(self) -> None:
        errors = self.check('name: demo-skill\ndescription: "A thing that exists."')
        self.assertTrue(any("trigger cue" in e for e in errors), errors)

    def test_rejects_overlong_compatibility(self) -> None:
        compat = "x" * (self.mod.MAX_COMPAT + 1)
        errors = self.check(self.VALID + f'\ncompatibility: "{compat}"')
        self.assertTrue(any("`compatibility` too long" in e for e in errors), errors)

    def test_rejects_nested_metadata(self) -> None:
        errors = self.check(self.VALID + "\nmetadata:\n  nested:\n    deep: 1")
        self.assertTrue(any("flat string key/value" in e for e in errors), errors)

    def test_rejects_body_over_budget(self) -> None:
        body = "# Heading\n\n" + ("filler\n" * (self.mod.MAX_BODY_LINES + 10))
        errors = self.check(self.VALID, body=body)
        self.assertTrue(any("lines" in e for e in errors), errors)

    def test_rejects_missing_top_level_heading(self) -> None:
        errors = self.check(self.VALID, body="## Only a subheading\n")
        self.assertTrue(any("top-level" in e for e in errors), errors)

    def test_rejects_missing_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "demo-skill"
            skill_dir.mkdir()
            md = skill_dir / "SKILL.md"
            md.write_text("# No frontmatter\n", encoding="utf-8")
            self.assertTrue(any("frontmatter" in e for e in self.mod.check(md)))


class CollisionMathTests(unittest.TestCase):
    """check-skill-collisions.py — the router's safety net."""

    def setUp(self) -> None:
        self.mod = load_script("check-skill-collisions.py")

    def score(self, a: str, b: str) -> float:
        vecs = self.mod.tfidf([self.mod.vector(a), self.mod.vector(b)])
        return self.mod.cosine(vecs[0], vecs[1])

    def test_identical_descriptions_are_maximally_similar(self) -> None:
        text = "port rust python golden harness equivalence"
        self.assertAlmostEqual(self.score(text, text), 1.0, places=6)

    def test_disjoint_descriptions_are_orthogonal(self) -> None:
        self.assertAlmostEqual(
            self.score("parser scanner tokenizer", "marketing launch positioning"), 0.0, places=6
        )

    def test_partial_overlap_falls_between(self) -> None:
        score = self.score("coverage llvm regions threshold", "coverage llvm campaign target")
        self.assertGreater(score, 0.0)
        self.assertLess(score, 1.0)

    def test_thresholds_are_ordered(self) -> None:
        self.assertLess(self.mod.WARN_AT, self.mod.FAIL_AT)

    def test_stopwords_are_dropped_from_vectors(self) -> None:
        self.assertNotIn("the", self.mod.vector("the parser and the scanner"))

    def test_frontmatter_description_stops_at_next_key(self) -> None:
        text = skill_text('name: d\ndescription: "the description"\nlicense: MIT')
        self.assertNotIn("MIT", self.mod.frontmatter_description(text))


class FrontmatterSyncTests(unittest.TestCase):
    """sync-skill-frontmatter.py — metadata.json to portable spec fields."""

    def setUp(self) -> None:
        self.mod = load_script("sync-skill-frontmatter.py")

    def test_allowed_tools_reflect_the_safety_policy(self) -> None:
        tools = self.mod.derive_allowed_tools(
            {"writes_files": True, "executes_commands": True, "network_access": "optional"}
        )
        for expected in ("Read", "Write", "Edit", "Bash", "WebFetch", "WebSearch"):
            self.assertIn(expected, tools)

    def test_read_only_policy_grants_no_mutating_tools(self) -> None:
        tools = self.mod.derive_allowed_tools(
            {"writes_files": False, "executes_commands": False, "network_access": "none"}
        )
        for forbidden in ("Write", "Edit", "Bash", "WebFetch", "WebSearch"):
            self.assertNotIn(forbidden, tools)

    def test_network_none_withholds_network_tools(self) -> None:
        tools = self.mod.derive_allowed_tools(
            {"executes_commands": True, "network_access": "none"}
        )
        self.assertIn("Bash", tools)
        self.assertNotIn("WebFetch", tools)

    def test_required_tools_become_compatibility(self) -> None:
        self.assertIn("Requires cargo, git", self.mod.derive_compatibility({"required_tools": ["cargo", "git"]}))

    def test_compatibility_is_truncated_to_the_spec_cap(self) -> None:
        compat = self.mod.derive_compatibility({"required_tools": ["x" * 900]})
        self.assertLessEqual(len(compat), self.mod.MAX_COMPAT)

    def test_metadata_values_are_all_strings(self) -> None:
        pairs = self.mod.derive_metadata(
            {
                "version": "0.0.3",
                "owner": "o",
                "maturity": "hardened",
                "bundle": "b",
                "safety_policy": {"risk_level": "low", "network_access": "none"},
            }
        )
        self.assertTrue(pairs)
        for key, value in pairs:
            self.assertIsInstance(key, str)
            self.assertIsInstance(value, str)

    def test_preserved_blocks_drop_generated_keys_only(self) -> None:
        kept = self.mod.preserved_blocks(
            ["name: demo", 'description: "text"', "license: MIT", "metadata:", '  agtmls-version: "0.0.3"']
        )
        self.assertIn("name: demo", kept)
        self.assertIn('description: "text"', kept)
        self.assertNotIn("license: MIT", kept)
        self.assertFalse(any(line.strip().startswith("agtmls-") for line in kept))

    def test_render_is_idempotent_on_a_real_skill(self) -> None:
        skill = ROOT / "skills" / "using-agtmls" / "SKILL.md"
        rendered = self.mod.render(skill)
        self.assertIsNotNone(rendered)
        self.assertEqual(rendered, skill.read_text(encoding="utf-8"))


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


class MetadataContractTests(unittest.TestCase):
    """Bundle membership and safety policy are now load-bearing fields."""

    def test_every_skill_declares_a_bundle(self) -> None:
        for meta in sorted((ROOT / "skills").glob("*/metadata.json")):
            data = json.loads(meta.read_text(encoding="utf-8"))
            self.assertIn("bundle", data, f"{meta} must declare bundle (null for general)")

    def test_high_risk_skills_require_human_review(self) -> None:
        for meta in sorted((ROOT / "skills").glob("*/metadata.json")):
            policy = json.loads(meta.read_text(encoding="utf-8"))["safety_policy"]
            if policy.get("risk_level") == "high":
                self.assertTrue(policy.get("requires_human_review"), meta)

    def test_published_allowed_tools_match_each_safety_policy(self) -> None:
        sync = load_script("sync-skill-frontmatter.py")
        index = json.loads((ROOT / "index.json").read_text(encoding="utf-8"))
        for skill in index["skills"]:
            meta = json.loads((ROOT / skill["path"] / "metadata.json").read_text(encoding="utf-8"))
            expected = sync.derive_allowed_tools(meta.get("safety_policy", {}))
            self.assertEqual(skill["allowed_tools"], expected, skill["name"])


class CheckManifestTests(unittest.TestCase):
    """The gate must be identical in the manifest, the runner, and CI."""

    def test_manifest_runner_and_ci_agree(self) -> None:
        module = load_script("validate-check-manifest.py")
        manifest = json.loads((ROOT / "checks.json").read_text(encoding="utf-8"))["checks"]
        self.assertEqual(manifest, module.runner_checks())
        workflow = (ROOT / ".github" / "workflows" / "validate.yml").read_text(encoding="utf-8")
        for check in manifest:
            self.assertIn(f"scripts/{check.split()[0]}", workflow, f"{check} is not run by CI")


class CliJsonTests(unittest.TestCase):
    def run_cli(self, *args: str) -> str:
        proc = subprocess.run(
            [sys.executable, str(CLI), *args],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout)
        return proc.stdout

    def test_stats_json_has_full_coverage(self) -> None:
        payload = json.loads(self.run_cli("stats", "--json"))
        count = payload["skills"]
        self.assertEqual(payload["coverage"]["routing"], {"covered": count, "total": count})
        self.assertEqual(payload["coverage"]["behavioral"], {"covered": count, "total": count})

    def test_profiles_json_includes_required_profiles(self) -> None:
        payload = json.loads(self.run_cli("profiles", "--json"))
        self.assertTrue({"minimal", "polyglot", "noyalib", "security", "research"}.issubset(payload))

    def test_providers_json_includes_native_and_exports(self) -> None:
        payload = json.loads(self.run_cli("providers", "--json"))
        self.assertEqual(set(payload["native_agents"]), {"claude", "codex", "aider"})
        self.assertIn("generic", payload["export_targets"])
        self.assertIn("openai", payload["export_targets"])

    def test_show_resolves_a_general_skill(self) -> None:
        self.assertIn(
            "verification-before-completion", self.run_cli("show", "verification-before-completion")
        )

    def test_search_filters_to_matching_skills(self) -> None:
        self.assertIn("systematic-debugging", self.run_cli("search", "debugging"))


class PackagedCliTests(unittest.TestCase):
    """src/agtmls/cli.py — the uvx entry point."""

    def setUp(self) -> None:
        sys.path.insert(0, str(ROOT / "src"))
        self.addCleanup(lambda: sys.path.remove(str(ROOT / "src")))

    def test_checkout_is_preferred_over_a_bundled_registry(self) -> None:
        from agtmls.cli import registry_root

        root, packaged = registry_root()
        self.assertFalse(packaged)
        self.assertTrue((root / "scripts" / "agtmls.py").exists())

    def test_agtmls_home_override_rejects_a_non_checkout(self) -> None:
        from agtmls.cli import registry_root

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["AGTMLS_HOME"] = tmp
            try:
                with self.assertRaises(SystemExit):
                    registry_root()
            finally:
                del os.environ["AGTMLS_HOME"]

    def test_checkout_only_commands_exclude_consumer_commands(self) -> None:
        from agtmls.cli import _CHECKOUT_ONLY

        self.assertIn("check", _CHECKOUT_ONLY)
        self.assertIn("release-pack", _CHECKOUT_ONLY)
        self.assertNotIn("install", _CHECKOUT_ONLY)
        self.assertNotIn("list", _CHECKOUT_ONLY)

    def test_package_version_matches_the_registry(self) -> None:
        import agtmls

        plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(agtmls.__version__, plugin["version"])


CASES = (
    VersionPolicyTests,
    SkillContractTests,
    CollisionMathTests,
    FrontmatterSyncTests,
    PackagingTests,
    PluginManifestTests,
    IndexGenerationTests,
    RouterParsingTests,
    MetadataContractTests,
    CheckManifestTests,
    CliJsonTests,
    PackagedCliTests,
)


def main() -> int:
    loader = unittest.defaultTestLoader
    suite = unittest.TestSuite(loader.loadTestsFromTestCase(case) for case in CASES)
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        return 1
    print(f"OK: {result.testsRun} unit test(s) passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
