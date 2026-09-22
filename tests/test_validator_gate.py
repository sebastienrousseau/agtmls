# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Drive every data validator against a broken registry.

The gate runs each validator once, against a repository that is correct, and
each one says OK. That proves they run. It proves nothing about whether any of
them can say anything else, and a checker that always returns 0 is the precise
failure this repository was built to prevent -- in its own checkers.

Each case below breaks one thing and requires the validator responsible to
notice. Both directions are asserted: the same validator must pass on the
pristine fixture, or "it failed" would mean nothing.

The fixture is a copy of the whole tree, made once per class because copying
it costs about two seconds. Tests restore whatever they broke, so order does
not matter.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from .support import ROOT, load_script, registry_fixture, retarget, run_main

ROOT_MANIFEST = ROOT / "checks.json"


class ValidatorFailureBase(unittest.TestCase):
    """One broken tree, many validators."""

    fixture: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls._workspace = tempfile.mkdtemp(prefix="agtmls-fixture-")
        cls.fixture = registry_fixture(Path(cls._workspace))

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._workspace, ignore_errors=True)

    def restore_later(self, relative: str) -> Path:
        path = self.fixture / relative
        original = path.read_bytes() if path.is_file() else None

        def restore() -> None:
            if original is None:
                if path.is_file():
                    path.unlink()
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(original)

        self.addCleanup(restore)
        return path

    def overwrite(self, relative: str, text: str) -> Path:
        path = self.restore_later(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def edit_json(self, relative: str, mutate) -> Path:
        path = self.restore_later(relative)
        data = json.loads(path.read_text(encoding="utf-8"))
        mutate(data)
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return path

    def remove(self, relative: str) -> None:
        self.restore_later(relative).unlink()

    def run_validator(self, script: str, *args: str) -> tuple[int, str]:
        module = load_script(script)
        retarget(module, self.fixture)
        return run_main(module, *args)

    def assert_clean(self, script: str, *args: str) -> None:
        code, output = self.run_validator(script, *args)
        self.assertEqual(code, 0, f"{script} failed on a pristine fixture:\n{output}")

    def assert_catches(self, script: str, *args: str) -> str:
        code, output = self.run_validator(script, *args)
        self.assertNotEqual(code, 0, f"{script} accepted a broken tree:\n{output}")
        return output

    def some_skill(self) -> Path:
        return sorted((self.fixture / "skills").glob("*/SKILL.md"))[0]


class SkillValidatorTests(ValidatorFailureBase):
    def test_skills_pass_when_intact(self) -> None:
        self.assert_clean("validate-skills.py")

    def test_a_skill_without_frontmatter_is_caught(self) -> None:
        self.overwrite(
            str(self.some_skill().relative_to(self.fixture)), "# No frontmatter\n"
        )
        self.assertIn("frontmatter", self.assert_catches("validate-skills.py"))

    def test_a_description_with_no_trigger_cue_is_caught(self) -> None:
        skill = self.some_skill()
        name = skill.parent.name
        self.overwrite(
            str(skill.relative_to(self.fixture)),
            f'---\nname: {name}\ndescription: "A thing that exists."\n---\n\n# Title\n\nbody\n',
        )
        self.assert_catches("validate-skills.py")

    def test_metadata_passes_when_intact(self) -> None:
        self.assert_clean("validate-skill-metadata.py")

    def test_a_skill_that_reintroduces_a_version_is_caught(self) -> None:
        """The field whose removal made the digest stable."""
        metadata = sorted((self.fixture / "skills").glob("*/metadata.json"))[0]
        self.edit_json(
            str(metadata.relative_to(self.fixture)),
            lambda data: data.__setitem__("version", "0.0.6"),
        )
        self.assertIn("version", self.assert_catches("validate-skill-metadata.py"))

    def test_metadata_with_an_unknown_risk_level_is_caught(self) -> None:
        metadata = sorted((self.fixture / "skills").glob("*/metadata.json"))[0]
        self.edit_json(
            str(metadata.relative_to(self.fixture)),
            lambda data: data["safety_policy"].__setitem__("risk_level", "catastrophic"),
        )
        self.assert_catches("validate-skill-metadata.py")

    def test_collisions_pass_when_descriptions_differ(self) -> None:
        self.assert_clean("check-skill-collisions.py")

    def test_two_identical_descriptions_are_caught(self) -> None:
        """Two skills the router cannot choose between is a routing defect."""
        skills = sorted((self.fixture / "skills").glob("*/SKILL.md"))[:2]
        shared = (
            "Use when doing the one identical thing that both of these skills "
            "claim, so no router could ever tell them apart at all."
        )
        for skill in skills:
            self.overwrite(
                str(skill.relative_to(self.fixture)),
                f'---\nname: {skill.parent.name}\ndescription: "{shared}"\n---\n\n# T\n\nbody\n',
            )
        self.assert_catches("check-skill-collisions.py")


class ManifestValidatorTests(ValidatorFailureBase):
    def test_plugin_manifest_passes_when_intact(self) -> None:
        self.assert_clean("validate-plugin-manifest.py")

    def test_a_manifest_missing_a_field_is_caught(self) -> None:
        self.edit_json(".claude-plugin/plugin.json", lambda data: data.pop("description"))
        self.assertIn("description", self.assert_catches("validate-plugin-manifest.py"))

    def test_a_manifest_pointing_outside_the_repository_is_caught(self) -> None:
        self.edit_json(
            ".claude-plugin/plugin.json",
            lambda data: data.__setitem__("skills", "../../etc"),
        )
        self.assert_catches("validate-plugin-manifest.py")

    def test_providers_pass_when_intact(self) -> None:
        self.assert_clean("validate-providers.py")

    def test_a_provider_with_no_export_target_is_caught(self) -> None:
        self.edit_json("providers.json", lambda data: data.__setitem__("export_targets", {}))
        self.assert_catches("validate-providers.py")

    def test_profiles_pass_when_intact(self) -> None:
        self.assert_clean("validate-profiles.py")

    def test_a_profile_naming_a_bundle_that_does_not_exist_is_caught(self) -> None:
        def mutate(data: dict) -> None:
            first = sorted(data["profiles"])[0]
            data["profiles"][first]["bundles"] = ["no-such-bundle"]

        self.edit_json("profiles.json", mutate)
        self.assert_catches("validate-profiles.py")

    def test_two_profiles_that_install_the_same_skills_are_caught(self) -> None:
        """`security` and `research` were copies of `noyalib` under other names."""

        def mutate(data: dict) -> None:
            data["profiles"]["security"] = dict(data["profiles"]["noyalib"])

        self.edit_json("profiles.json", mutate)
        self.assertIn("security", self.assert_catches("validate-profiles.py"))

    def test_a_profile_that_omits_its_own_bundle_is_caught(self) -> None:
        def mutate(data: dict) -> None:
            data["profiles"]["security"]["bundles"] = []

        self.edit_json("profiles.json", mutate)
        self.assertIn("security", self.assert_catches("validate-profiles.py"))

    def test_a_general_profile_that_pulls_in_a_project_bundle_is_caught(self) -> None:
        def mutate(data: dict) -> None:
            data["profiles"]["polyglot"]["bundles"] = ["noyalib"]

        self.edit_json("profiles.json", mutate)
        self.assertIn("noyalib", self.assert_catches("validate-profiles.py"))

    def test_lifecycle_passes_when_intact(self) -> None:
        self.assert_clean("validate-lifecycle.py")

    def test_a_lifecycle_missing_its_no_manual_edit_rule_is_caught(self) -> None:
        self.overwrite("lifecycle.json", json.dumps({"stages": []}) + "\n")
        self.assert_catches("validate-lifecycle.py")


class RepositoryValidatorTests(ValidatorFailureBase):
    def test_json_files_pass_when_intact(self) -> None:
        self.assert_clean("validate-json-files.py")

    def test_malformed_json_anywhere_is_caught(self) -> None:
        self.overwrite("evals/cases/handoff.json", "{ not json")
        self.assertIn("handoff", self.assert_catches("validate-json-files.py"))

    def test_licence_headers_pass_when_intact(self) -> None:
        self.assert_clean("validate-licence-headers.py")

    def test_a_document_with_no_licence_is_caught(self) -> None:
        self.overwrite("docs/checks.md", "# Checks\n\nNo licence header here.\n")
        self.assertIn("checks.md", self.assert_catches("validate-licence-headers.py"))

    def test_a_script_with_no_licence_is_caught(self) -> None:
        """Code was counted but never read, so a bare script passed."""
        self.overwrite("scripts/unlicensed.py", '"""No header."""\n')
        self.assertIn("unlicensed.py", self.assert_catches("validate-licence-headers.py"))

    def test_a_shell_script_with_no_licence_is_caught(self) -> None:
        self.overwrite("scripts/unlicensed.sh", "#!/usr/bin/env bash\nset -euo pipefail\n")
        self.assertIn("unlicensed.sh", self.assert_catches("validate-licence-headers.py"))

    def test_a_licence_buried_below_the_header_is_caught(self) -> None:
        """A header is the first lines of the file, not a mention anywhere."""
        body = "\n".join(["#!/usr/bin/env python3"] + ["pass"] * 10)
        self.overwrite("scripts/buried.py", body + "\n# SPDX-License-Identifier: MIT\n")
        self.assertIn("buried.py", self.assert_catches("validate-licence-headers.py"))

    def test_a_licence_this_repository_does_not_offer_is_caught(self) -> None:
        self.overwrite(
            "scripts/gpl.py", "# SPDX-License-Identifier: GPL-3.0-only\n\"\"\"Wrong.\"\"\"\n"
        )
        self.assertIn("GPL-3.0-only", self.assert_catches("validate-licence-headers.py"))

    def test_a_skill_that_drops_its_licence_field_is_caught(self) -> None:
        """SKILL.md cannot carry a comment header, so it declares `license:`."""
        skill = self.some_skill()
        self.overwrite(
            str(skill.relative_to(self.fixture)),
            f'---\nname: {skill.parent.name}\ndescription: "Use when needed."\n---\n\n# T\n\nbody\n',
        )
        self.assert_catches("validate-licence-headers.py")

    def test_doc_links_pass_when_intact(self) -> None:
        self.assert_clean("validate-doc-links.py")

    def test_a_link_to_a_file_that_is_not_there_is_caught(self) -> None:
        self.overwrite(
            "docs/checks.md",
            "<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->\n\n"
            "# Checks\n\nSee [the missing guide](does-not-exist.md).\n",
        )
        self.assert_catches("validate-doc-links.py")

    def test_secrets_pass_when_there_are_none(self) -> None:
        self.assert_clean("validate-secrets.py")

    def test_a_committed_private_key_is_caught(self) -> None:
        # Assembled rather than written out: the scanner reads this file too,
        # and a test fixture that trips the check it is testing is a secret
        # scanner working correctly on the wrong target. It caught exactly
        # that when this was first written as a literal.
        marker = "-----BEGIN " + "RSA" + " PRIVATE" + " KEY-----"
        self.overwrite(
            "docs/checks.md",
            "<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->\n\n"
            f"# Checks\n\n{marker}\nMIIEow==\n",
        )
        self.assert_catches("validate-secrets.py")

    def test_a_committed_api_token_is_caught(self) -> None:
        token = "ghp" + "_" + "A" * 24
        self.overwrite(
            "docs/checks.md",
            "<!-- SPDX-License-Identifier: Apache-2.0 OR MIT -->\n\n"
            f"# Checks\n\nexport TOKEN={token}\n",
        )
        self.assert_catches("validate-secrets.py")

    def test_governance_passes_when_intact(self) -> None:
        self.assert_clean("validate-governance.py")

    def test_a_missing_supply_chain_artifact_is_caught(self) -> None:
        """Despite the name, this check is about the SBOM and provenance.

        Named for the category it sits in rather than what it inspects, which
        is worth knowing before trusting it to cover GOVERNANCE.md -- it does
        not.
        """
        self.remove("SBOM.spdx.json")
        self.assertIn("SBOM", self.assert_catches("validate-governance.py"))

    def test_a_missing_provenance_statement_is_caught(self) -> None:
        self.remove("provenance.json")
        self.assert_catches("validate-governance.py")

    def test_system_prompts_pass_when_intact(self) -> None:
        self.assert_clean("validate-system-prompts.py")

    def test_a_system_prompt_stripped_of_its_content_is_caught(self) -> None:
        self.overwrite("system-prompts/rust.md", "<!-- SPDX-License-Identifier: MIT -->\n")
        self.assert_catches("validate-system-prompts.py")

    def test_templates_pass_when_intact(self) -> None:
        self.assert_clean("validate-templates.py")

    def test_a_missing_template_is_caught(self) -> None:
        self.remove("templates/skill/SKILL.md")
        self.assert_catches("validate-templates.py")


class GeneratedArtifactTests(ValidatorFailureBase):
    """A generator's --check mode is the only thing keeping its output honest."""

    def test_the_index_is_current(self) -> None:
        self.assert_clean("generate-skill-index.py", "--check")

    def test_a_stale_index_is_caught(self) -> None:
        self.edit_json("index.json", lambda data: data.__setitem__("skill_count", 999))
        self.assertIn("stale", self.assert_catches("generate-skill-index.py", "--check"))

    def test_the_catalog_is_current(self) -> None:
        self.assert_clean("generate-catalog.py", "--check")

    def test_a_stale_catalog_is_caught(self) -> None:
        self.overwrite("CATALOG.md", "# Catalog\n\nnothing here\n")
        self.assert_catches("generate-catalog.py", "--check")

    def test_mcp_resources_are_current(self) -> None:
        self.assert_clean("generate-mcp-resources.py", "--check")

    def test_stale_mcp_resources_are_caught(self) -> None:
        self.edit_json("mcp-resources.json", lambda data: data.__setitem__("resources", []))
        self.assert_catches("generate-mcp-resources.py", "--check")

    def test_generated_artifact_markers_are_present(self) -> None:
        self.assert_clean("validate-generated-artifacts.py")

    def test_an_index_that_forgets_what_generated_it_is_caught(self) -> None:
        self.edit_json("index.json", lambda data: data.__setitem__("generated_by", "a person"))
        self.assert_catches("validate-generated-artifacts.py")

    def test_the_skill_index_metadata_is_valid(self) -> None:
        self.assert_clean("validate-skill-index.py")

    def test_an_index_entry_with_no_description_is_caught(self) -> None:
        def mutate(data: dict) -> None:
            data["skills"][0]["description"] = ""

        self.edit_json("index.json", mutate)
        self.assert_catches("validate-skill-index.py")


class EveryValidatorTests(ValidatorFailureBase):
    """Run the whole data gate in-process, against a copy.

    The gate runs these as subprocesses, which is right for a gate and useless
    for measurement: nothing observes which branches ran. Driving them
    in-process against a fixture exercises the same code and shows it.

    Scoped to the checks that only read the tree. The smoke tests spawn
    installers, shell out to make and reach for git, which is what makes them
    smoke tests rather than unit tests.
    """

    #: Checks that need a git history, a network, or a subprocess of their own.
    NEEDS_MORE_THAN_A_TREE = {
        "validate-python-scripts.py",   # reads scripts/, which the fixture copies but does not own
        "validate-shell-syntax.py",     # shells out to sh -n
        "validate-spec-conformance.py", # optional external reference implementation
        "validate-version-policy.py",   # reads git tags
        "validate-packaging.py",        # asserts the real wheel layout
        "validate-check-manifest.py",   # reads the real workflow
        "validate-docs-site.py",        # compares against the real generator output
        "validate-cli-surface.py",      # parses the real parser source
        "validate-sbom-conformance.py", # diffs against the real pyproject
        "generate-sbom.py",             # hashes the real tree
        "generate-provenance.py",       # reads git
        "generate-docs-site.py",        # embeds the real version
        "generate-plugin-manifests.py", # writes outside the fixture
        "sync-skill-frontmatter.py",    # rewrites skills in place
        "agtmls-doctor.py",             # runs the gate
        "bench.py",                     # measures
        "run-security-evals.py",        # materialises its own corpus
        "run-trigger-evals.py",         # scores the real registry
        "run-behavioral-evals.py",      # scores the real registry
        "run-unit-tests.py",            # this
        "audit-skill.py",               # covered by SkillAuditTests
        "validate-eval-cases.py",       # covered by EvalCaseFailureTests
        "validate-licence-headers.py",  # covered above
        "validate-doc-links.py",        # covered above
        "validate-secrets.py",          # covered above
        "validate-json-files.py",       # covered above
        "validate-gitignore.py",        # reads the real .gitignore policy
        "validate-release.py",          # reads RELEASE.md against git state
        "release-check.py",             # runs other checks as subprocesses
    }

    def tree_only_checks(self) -> list[list[str]]:
        import shlex

        manifest = json.loads((ROOT_MANIFEST).read_text(encoding="utf-8"))["checks"]
        out = []
        for entry in manifest:
            parts = shlex.split(entry)
            if parts[0] in self.NEEDS_MORE_THAN_A_TREE or parts[0].startswith("smoke-"):
                continue
            out.append(parts)
        return out

    def test_every_tree_only_check_passes_on_a_correct_copy(self) -> None:
        """If one of these cannot pass a correct tree, it cannot mean anything."""
        checked = []
        for parts in self.tree_only_checks():
            code, output = self.run_validator(parts[0], *parts[1:])
            self.assertEqual(code, 0, f"{parts[0]} failed on a pristine fixture:\n{output}")
            checked.append(parts[0])
        self.assertGreaterEqual(len(checked), 8, f"only drove {checked}")


class SpecConformanceTests(unittest.TestCase):
    """validate-spec-conformance.py printed SKIP and passed whenever skills-ref
    was missing, and CI installed it with `|| true` -- so a failed install
    silently turned the spec check off on every leg.
    """

    def drive(self, env: dict[str, str], version: tuple[int, int]) -> tuple[int, str]:
        import os
        from unittest import mock

        module = load_script("validate-spec-conformance.py")
        with mock.patch.object(module, "runner", return_value=None), \
                mock.patch.dict(os.environ, env, clear=False), \
                mock.patch.object(module, "PYTHON", version):
            if "CI" not in env:
                os.environ.pop("CI", None)
            return run_main(module)

    def test_a_missing_reference_validator_fails_in_ci(self) -> None:
        code, output = self.drive({"CI": "true"}, (3, 12))
        self.assertEqual(code, 1, output)
        self.assertIn("FAIL", output)

    def test_ci_on_a_python_the_reference_does_not_support_skips(self) -> None:
        """skills-ref needs 3.11+; the 3.10 leg cannot run it at all."""
        code, output = self.drive({"CI": "true"}, (3, 10))
        self.assertEqual(code, 0, output)
        self.assertIn("SKIP", output)

    def test_a_local_run_without_it_still_skips(self) -> None:
        """The offline gate stays runnable on a machine with no network."""
        code, output = self.drive({}, (3, 12))
        self.assertEqual(code, 0, output)
        self.assertIn("SKIP", output)


class SecurityClaimTests(ValidatorFailureBase):
    """A static analyzer is triage, and the docs must say so.

    Packing evades every static skill scanner tested at over 90% (arXiv
    2607.02357), yet the README promised "proactive defense" and listed
    "Attack Vectors Defended". A security product that overclaims is
    discredited by the first bypass.
    """

    def test_the_shipped_documents_make_no_absolute_claims(self) -> None:
        self.assert_clean("validate-security-claims.py")

    def test_defense_language_in_the_readme_is_caught(self) -> None:
        path = self.fixture / "README.md"
        self.overwrite("README.md", path.read_text(encoding="utf-8") + "\nAgtMLS provides proactive defense against malicious skills.\n")
        self.assertIn("README.md", self.assert_catches("validate-security-claims.py"))

    def test_a_guarantee_in_the_docs_is_caught(self) -> None:
        self.overwrite("docs/claims.md", "<!-- SPDX-License-Identifier: MIT -->\n\nThe analyzer guarantees that no malicious skill is installed.\n")
        self.assertIn("claims.md", self.assert_catches("validate-security-claims.py"))

    def test_security_md_must_separate_boundaries_from_heuristics(self) -> None:
        path = self.fixture / "SECURITY.md"
        text = path.read_text(encoding="utf-8")
        self.overwrite("SECURITY.md", text.replace("## Boundaries and heuristics", "## Something else"))
        self.assertIn("SECURITY.md", self.assert_catches("validate-security-claims.py"))
