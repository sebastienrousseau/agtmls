# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The rules a release must satisfy before anything is packed.

Which version comes next, what a bump rewrites, which metadata must agree,
whether the publishing workflows can mint a token, and what changed between
two indexes. `test_release_mechanics.py` drives the happy paths of the bump
and the policy gate; these are the refusals, which are the part a release
depends on and the part nothing exercised.

One registry copy serves the whole module. A case that breaks a file restores
it on cleanup, so each case sees the tree the one before it started with --
and a case that forgot would show up as a neighbour failing, not a silent pass.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from .support import load_script, registry_fixture, retarget, run_main

_BASE: Path
FIXTURE: Path


def setUpModule() -> None:
    global _BASE, FIXTURE
    _BASE = Path(tempfile.mkdtemp(prefix="agtmls-policy-")).resolve()
    FIXTURE = registry_fixture(_BASE / "tree")


def tearDownModule() -> None:
    shutil.rmtree(_BASE, ignore_errors=True)


_LOADED: dict[str, object] = {}


class FixtureCase(unittest.TestCase):
    def script(self, name: str):
        """Each script is loaded once per module; cases patch, never assign."""
        if name not in _LOADED:
            module = load_script(name)
            retarget(module, FIXTURE)
            _LOADED[name] = module
        return _LOADED[name]

    def patch(self, module, attribute: str, value) -> None:
        patcher = mock.patch.object(module, attribute, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def preserve(self, *relative: str) -> None:
        """Restore these files -- or remove them, if new -- when the case ends."""
        for rel in relative:
            path = FIXTURE / rel
            original = path.read_bytes() if path.exists() else None

            def restore(path: Path = path, original: bytes | None = original) -> None:
                if original is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(original)

            self.addCleanup(restore)

    def edit_json(self, rel: str, change) -> None:
        self.preserve(rel)
        path = FIXTURE / rel
        data = json.loads(path.read_text(encoding="utf-8"))
        change(data)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def edit_text(self, rel: str, old: str, new: str) -> None:
        self.preserve(rel)
        path = FIXTURE / rel
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text, f"{rel} no longer contains what this case breaks")
        path.write_text(text.replace(old, new), encoding="utf-8")

    def version(self) -> str:
        return json.loads(
            (FIXTURE / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )["version"]


def tags(stdout: str):
    """A `git tag --list` that answers with `stdout`."""
    return mock.patch.object(
        subprocess, "run", return_value=subprocess.CompletedProcess([], 0, stdout, "")
    )


class NextVersionTests(FixtureCase):
    """The only source of the next version; every release script asks it."""

    def test_only_patch_line_tags_count_and_duplicates_collapse(self) -> None:
        module = self.script("next-version.py")
        with tags("v0.0.3\nv0.0.1\n v0.0.3 \nv0.1.0\nv0.0.x\nrelease-1\n") as run:
            self.assertEqual(module.release_patches(), [1, 3])
        self.assertEqual(run.call_args.args[0], ["git", "tag", "--list", "v0.0.*"])
        self.assertEqual(run.call_args.kwargs["cwd"], FIXTURE)

    def test_the_patch_line_runway_ends_at_999(self) -> None:
        module = self.script("next-version.py")
        self.patch(module, "release_patches", lambda: [998, 999])
        with self.assertRaises(SystemExit) as caught:
            module.next_version()
        self.assertIn("0.1.0 requires an explicit policy change", str(caught.exception))
        module.release_patches = lambda: [997, 998]  # still under patch
        self.assertEqual(module.next_version(), "0.0.999")

    def test_each_output_format_names_the_same_version(self) -> None:
        module = self.script("next-version.py")
        self.patch(module, "release_patches", lambda: [1, 2])
        self.assertEqual(run_main(module), (0, "0.0.3\n"))
        self.assertEqual(run_main(module, "--tag"), (0, "v0.0.3\n"))
        code, output = run_main(module, "--json")
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output), {
            "version": "0.0.3", "tag": "v0.0.3",
            "policy": "0.0.x increments by exactly 0.0.1",
        })


class BumpRefusalTests(FixtureCase):
    """What a bump does when the tree, or its helpers, are not as expected."""

    def bumper(self, target: str = "9.9.9", failing: str | None = None):
        """A bumper whose subprocesses are recorded instead of spawned."""
        module = self.script("bump-version.py")
        self.ran: list[str] = []

        def run(cmd):
            name = Path(cmd[1]).name
            self.ran.append(name)
            if name == "next-version.py":
                return subprocess.CompletedProcess(cmd, 0, target + "\n")
            return subprocess.CompletedProcess(cmd, 1 if name == failing else 0, f"ran {name}\n")

        self.patch(module, "run", run)
        self.preserve(".claude-plugin/plugin.json", "pyproject.toml", "src/agtmls/__init__.py",
                      ".claude-plugin/marketplace.json", "CHANGELOG.md")
        return module

    def test_next_version_comes_from_the_next_version_script(self) -> None:
        module = self.script("bump-version.py")
        done = subprocess.CompletedProcess([], 0, "0.0.4\n")
        with mock.patch.object(module.subprocess, "run", return_value=done) as run:
            self.assertEqual(module.next_version(), "0.0.4")
        self.assertEqual(Path(run.call_args.args[0][1]).name, "next-version.py")
        self.assertEqual(run.call_args.kwargs["cwd"], FIXTURE)

    def test_a_failing_next_version_aborts_with_its_message(self) -> None:
        module = self.script("bump-version.py")
        failed = subprocess.CompletedProcess([], 1, "v0.0.999 already exists")
        with mock.patch.object(module.subprocess, "run", return_value=failed), \
                self.assertRaises(SystemExit) as caught:
            module.next_version()
        self.assertEqual(str(caught.exception), "v0.0.999 already exists")

    def test_a_full_bump_moves_every_carrier_and_runs_every_generator(self) -> None:
        old = self.version()
        module = self.bumper()
        code, output = run_main(module)  # no --version: the next allowed one
        self.assertEqual(code, 0, output)
        self.assertIn(f"OK: bumped AgtMLS from {old} to 9.9.9", output)
        self.assertEqual(self.version(), "9.9.9")
        for rel in ("pyproject.toml", "src/agtmls/__init__.py", ".claude-plugin/marketplace.json"):
            text = (FIXTURE / rel).read_text(encoding="utf-8")
            self.assertIn('"9.9.9"', text, f"{rel} did not move")
            self.assertNotIn(f'"{old}"', text, f"{rel} kept the old version")
        generators = [item[0] for item in module.GENERATORS]
        self.assertEqual(self.ran, ["next-version.py", "next-version.py", *generators])
        self.assertIn("ran generate-provenance.py", output)

    def test_a_failing_generator_stops_the_bump_with_its_exit_code(self) -> None:
        module = self.bumper(failing="generate-catalog.py")
        code, output = run_main(module)
        self.assertEqual(code, 1)
        self.assertEqual(self.ran[-1], "generate-catalog.py", "generators ran past a failure")
        self.assertNotIn("OK:", output)

    def test_a_rerun_does_not_open_a_second_section(self) -> None:
        """A bump interrupted after the changelog must be safe to repeat."""
        self.preserve("CHANGELOG.md")
        module = self.script("bump-version.py")
        module.update_changelog("9.9.9", "2099-01-01")
        once = (FIXTURE / "CHANGELOG.md").read_text(encoding="utf-8")
        module.update_changelog("9.9.9", "2099-01-02")
        self.assertEqual((FIXTURE / "CHANGELOG.md").read_text(encoding="utf-8"), once)
        self.assertEqual(once.count("## 9.9.9 - "), 1)

    def test_a_changelog_without_unreleased_is_refused(self) -> None:
        self.edit_text("CHANGELOG.md", "## Unreleased\n", "## Pending\n")
        module = self.script("bump-version.py")
        with self.assertRaises(SystemExit) as caught:
            module.update_changelog("9.9.9", "2099-01-01")
        self.assertIn("missing ## Unreleased", str(caught.exception))

    def test_an_empty_unreleased_section_gets_a_placeholder_entry(self) -> None:
        """Otherwise the new heading would sit over the previous release's notes."""
        self.preserve("CHANGELOG.md")
        path = FIXTURE / "CHANGELOG.md"
        path.write_text("# Changelog\n\n## Unreleased\n\n## 0.0.1 - 2026-01-01\n\n- First.\n",
                        encoding="utf-8")
        self.script("bump-version.py").update_changelog("0.0.2", "2099-01-01")
        # Blank-line runs are collapsed before comparing: the bump currently
        # leaves two blank lines above the next heading (visible in the real
        # CHANGELOG under three past releases). That is cosmetic and
        # reported separately; this case is about which entry lands where.
        text = path.read_text(encoding="utf-8")
        while "\n\n\n" in text:
            text = text.replace("\n\n\n", "\n\n")
        self.assertEqual(text, (
            "# Changelog\n\n## Unreleased\n\n## 0.0.2 - 2099-01-01\n\n### Changed\n\n"
            "- Bumped release metadata through the guarded patch-line release flow.\n\n"
            "## 0.0.1 - 2026-01-01\n\n- First.\n"
        ))

    def test_a_first_release_with_no_earlier_section_keeps_its_notes(self) -> None:
        self.preserve("CHANGELOG.md")
        path = FIXTURE / "CHANGELOG.md"
        path.write_text("# Changelog\n\n## Unreleased\n\n- Initial skills.\n", encoding="utf-8")
        self.script("bump-version.py").update_changelog("0.0.1", "2099-01-01")
        self.assertEqual(
            path.read_text(encoding="utf-8"),
            "# Changelog\n\n## Unreleased\n\n## 0.0.1 - 2099-01-01\n\n- Initial skills.\n\n",
        )


class ReleaseMetadataTests(FixtureCase):
    """validate-release.py: the metadata a release announces must agree."""

    def check(self) -> tuple[int, str]:
        return run_main(self.script("validate-release.py"))

    def assertRefused(self, message: str) -> None:
        code, output = self.check()
        self.assertEqual(code, 1, output)
        self.assertIn(f"FAIL: {message}", output)
        self.assertIn("FAIL: 1 release metadata issue(s)", output)

    def test_the_shipped_metadata_is_consistent(self) -> None:
        code, output = self.check()
        self.assertEqual(code, 0, output)
        self.assertIn(f"OK: release metadata valid for agtmls {self.version()}", output)

    def test_a_non_semver_plugin_version_is_refused(self) -> None:
        self.edit_json(".claude-plugin/plugin.json", lambda d: d.update(version="0.0"))
        self.edit_json("index.json", lambda d: d.update(registry_version="0.0"))
        self.assertRefused("plugin version must be semver X.Y.Z")

    def test_an_index_behind_the_plugin_is_refused(self) -> None:
        self.edit_json("index.json", lambda d: d.update(registry_version="0.0.0"))
        self.assertRefused("index registry_version must match plugin version")

    def test_an_index_for_another_registry_is_refused(self) -> None:
        self.edit_json("index.json", lambda d: d.update(name="other"))
        self.assertRefused("index name must match plugin name")

    def test_a_changelog_with_no_unreleased_section_is_refused(self) -> None:
        self.edit_text("CHANGELOG.md", "## Unreleased", "## Upcoming")
        self.assertRefused("CHANGELOG.md must contain ## Unreleased")

    def test_a_release_procedure_that_skips_the_gate_is_refused(self) -> None:
        self.edit_text("RELEASE.md", "python3 scripts/agtmls.py check", "make check")
        self.assertRefused("RELEASE.md must require python3 scripts/agtmls.py check")

    def test_a_release_procedure_that_skips_the_index_is_refused(self) -> None:
        self.edit_text("RELEASE.md", "python3 scripts/agtmls.py index --write", "make index")
        self.assertRefused("RELEASE.md must require index regeneration")


class SequencingRuleTests(unittest.TestCase):
    """The 0.0.x runway, as a pure function of the version and the tags."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.rule = staticmethod(load_script("validate-version-policy.py").sequencing_errors)

    def test_a_version_that_is_not_semver_is_the_only_error(self) -> None:
        """The rest of the rule cannot be evaluated against a malformed version."""
        self.assertEqual(self.rule("0.0.3-rc1", [(0, 0, 2)]), ["plugin version must be semver X.Y.Z"])

    def test_patch_zero_and_patch_1000_are_off_the_runway(self) -> None:
        for version in ("0.0.0", "0.0.1000"):
            self.assertIn("0.0.x patch must be between 1 and 999", self.rule(version, []))

    def test_a_minor_tag_is_forbidden_until_999_is_tagged(self) -> None:
        errors = self.rule("0.0.3", [(0, 0, 2), (0, 1, 0)])
        self.assertIn("minor/major release tags are forbidden until v0.0.999 exists", errors)
        self.assertEqual(self.rule("0.0.999", [(0, 0, 998), (0, 0, 999), (0, 1, 0)]), [])

    def test_only_non_patch_line_tags_leave_the_patch_rules_unapplied(self) -> None:
        errors = self.rule("0.0.5", [(1, 0, 0)])
        self.assertEqual(errors, ["minor/major release tags are forbidden until v0.0.999 exists"])

    def test_a_version_behind_the_latest_tag_is_refused(self) -> None:
        self.assertEqual(self.rule("0.0.4", [(0, 0, 3), (0, 0, 5)]),
                         ["current version 0.0.4 is behind latest tag v0.0.5"])

    def test_the_latest_tagged_version_itself_is_allowed(self) -> None:
        """Between a tag and the next bump, the tree sits at the tagged version."""
        self.assertEqual(self.rule("0.0.5", [(0, 0, 5)]), [])


class VersionPolicyRefusalTests(FixtureCase):
    """validate-version-policy.py end to end: each way the tree can drift."""

    def check(self, tag_list: str = "") -> tuple[int, str]:
        module = self.script("validate-version-policy.py")
        with tags(tag_list):
            return run_main(module)

    def assertRefused(self, message: str, **kwargs) -> str:
        code, output = self.check(**kwargs)
        self.assertEqual(code, 1, output)
        self.assertIn(f"FAIL: {message}", output)
        return output

    def test_tags_are_read_from_git_and_filtered(self) -> None:
        module = self.script("validate-version-policy.py")
        with tags("v0.0.2\nv0.0.1\nv1.2\nnightly\nv0.1.0\n") as run:
            self.assertEqual(module.release_tags(), [(0, 0, 1), (0, 0, 2), (0, 1, 0)])
        self.assertEqual(run.call_args.args[0], ["git", "tag", "--list", "v*"])
        self.assertEqual(run.call_args.kwargs["cwd"], FIXTURE)

    def test_the_tree_passes_against_its_own_release_tags(self) -> None:
        patch = int(self.version().rsplit(".", 1)[1])
        code, output = self.check("".join(f"v0.0.{n}\n" for n in range(1, patch)))
        self.assertEqual(code, 0, output)
        self.assertIn(f"OK: version policy valid for {self.version()}", output)

    def test_a_tree_behind_the_latest_tag_is_refused(self) -> None:
        ahead = int(self.version().rsplit(".", 1)[1]) + 10
        self.assertRefused(f"current version {self.version()} is behind latest tag v0.0.{ahead}",
                           tag_list=f"v0.0.{ahead}\n")

    def test_a_malformed_version_is_reported_once_not_twice(self) -> None:
        """The rule runs before and after reading tags; errors must not double."""
        self.edit_json(".claude-plugin/plugin.json", lambda d: d.update(version="0.0"))
        output = self.assertRefused("plugin version must be semver X.Y.Z")
        self.assertEqual(output.count("plugin version must be semver"), 1, output)

    def test_every_metadata_file_must_carry_the_plugin_version(self) -> None:
        module = self.script("validate-version-policy.py")
        self.preserve("extra-manifest.json")
        (FIXTURE / "extra-manifest.json").write_text('{"version": "0.0.1"}', encoding="utf-8")
        self.patch(module, "METADATA_FILES", [*module.METADATA_FILES, FIXTURE / "extra-manifest.json"])
        with tags(""):
            code, output = run_main(module)
        self.assertEqual(code, 1)
        self.assertIn(f"FAIL: extra-manifest.json version 0.0.1 must match {self.version()}", output)

    def test_a_version_free_file_that_does_not_exist_is_not_an_error(self) -> None:
        """A skill removed between import and check has no version to carry."""
        module = self.script("validate-version-policy.py")
        self.patch(module, "VERSION_FREE",
                   [*module.VERSION_FREE, FIXTURE / "skills" / "gone" / "metadata.json"])
        with tags(""):
            code, output = run_main(module)
        self.assertEqual(code, 0, output)

    def test_provenance_without_a_subject_list_is_refused(self) -> None:
        self.edit_json("provenance.json", lambda d: d.update(subject={"name": "x"}))
        self.assertRefused("provenance.json must carry an in-toto subject list")

    def test_provenance_naming_another_release_is_refused(self) -> None:
        self.edit_json("provenance.json", lambda d: d["subject"][0].update(name="agtmls-0.0.1"))
        self.assertRefused(f"provenance.json subject name must be 'agtmls-{self.version()}', "
                           "got 'agtmls-0.0.1'")

    def test_provenance_declaring_another_version_is_refused(self) -> None:
        def change(data: dict) -> None:
            data["predicate"]["buildDefinition"]["externalParameters"]["registryVersion"] = "0.0.1"

        self.edit_json("provenance.json", change)
        self.assertRefused("provenance.json registryVersion must match plugin version")

    def test_a_release_with_no_dated_changelog_entry_is_refused(self) -> None:
        version = self.version()
        self.edit_text("CHANGELOG.md", f"## {version} - ", f"## {version} (draft) ")
        self.assertRefused(f"CHANGELOG.md must contain a dated ## {version} release entry")

    def test_a_missing_versioning_policy_is_refused_on_both_clauses(self) -> None:
        self.preserve("VERSIONING.md")
        (FIXTURE / "VERSIONING.md").unlink()
        output = self.assertRefused("VERSIONING.md must document: Versions increment by exactly `0.0.1`")
        self.assertIn("VERSIONING.md must document: `v0.1.0` is forbidden until `v0.0.999`", output)
        self.assertIn("FAIL: 2 version policy issue(s)", output)
