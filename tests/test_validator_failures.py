# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Every validator must be shown to fail.

The gate runs each validator once, against a repository that is correct, and
each one says OK. That proves they run. It does not prove any of them can
say anything else -- and a checker that always returns 0 is the exact failure
this suite exists to catch, in the checkers themselves.

So these drive the error branches: a manifest missing a field, a path that
escapes the repository, an eval case naming a skill that does not exist, a
positive list that is empty. Each asserts the specific complaint, not merely
that something went wrong, because a validator that fails for the wrong
reason is only accidentally right.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from .support import load_script


class PluginManifestFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = load_script("validate-plugin-manifest.py")

    def complaints(self, manifest: dict) -> list[str]:
        errors: list[str] = []
        original = self.mod.MANIFEST
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "plugin.json"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            self.mod.MANIFEST = path
            try:
                self.mod.check_plugin(errors)
            finally:
                self.mod.MANIFEST = original
        return errors

    def valid(self) -> dict:
        return {
            "name": "agtmls",
            "version": "0.0.1",
            "description": "x",
            "author": {"name": "Someone"},
            "license": "MIT",
            "homepage": "https://github.com/sebastienrousseau/agtmls",
            "skills": "./skills",
            "commands": "./commands",
            "agents": ["./agents/registry-auditor.md"],
        }

    def test_a_valid_manifest_produces_no_complaint_about_its_fields(self) -> None:
        for complaint in self.complaints(self.valid()):
            self.assertNotIn("missing", complaint)
            self.assertNotIn("must be", complaint)

    def test_a_missing_required_field_is_named(self) -> None:
        manifest = self.valid()
        del manifest["description"]
        self.assertIn("plugin manifest missing description", self.complaints(manifest))

    def test_the_wrong_name_is_refused(self) -> None:
        manifest = self.valid()
        manifest["name"] = "not-agtmls"
        self.assertIn("plugin manifest name must be agtmls", self.complaints(manifest))

    def test_a_non_semver_version_is_refused(self) -> None:
        manifest = self.valid()
        manifest["version"] = "v1"
        self.assertIn("plugin manifest version must be semver", self.complaints(manifest))

    def test_the_wrong_licence_is_refused(self) -> None:
        manifest = self.valid()
        manifest["license"] = "GPL-3.0"
        self.assertIn("plugin manifest license must be MIT", self.complaints(manifest))

    def test_an_author_without_a_name_is_refused(self) -> None:
        manifest = self.valid()
        manifest["author"] = {}
        self.assertIn("plugin manifest author.name is required", self.complaints(manifest))

    def test_a_homepage_that_is_not_github_https_is_refused(self) -> None:
        manifest = self.valid()
        manifest["homepage"] = "http://example.com/agtmls"
        self.assertTrue(
            any("homepage" in c for c in self.complaints(manifest)),
            "an insecure homepage was accepted",
        )

    def test_a_path_escaping_the_repository_is_refused(self) -> None:
        """`../` in a manifest path is a directory traversal with a nice name."""
        self.assertIsNone(self.mod.rel_path("../../etc"))
        self.assertIsNone(self.mod.rel_path("/absolute/path"))
        self.assertIsNone(self.mod.rel_path(None))
        self.assertIsNotNone(self.mod.rel_path("./skills"))

    def test_a_skills_path_that_is_not_a_directory_is_refused(self) -> None:
        errors: list[str] = []
        self.mod.check_skill_paths("label", "./does-not-exist", errors)
        self.assertTrue(errors, "a missing skills path was accepted")


class EvalCaseFailureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mod = load_script("validate-eval-cases.py")

    def routing(self, cases: dict[str, dict], names: set[str]) -> list[str]:
        original_dir, original_root = self.mod.ROUTING_DIR, self.mod.ROOT
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw) / "evals" / "cases"
            directory.mkdir(parents=True)
            for stem, payload in cases.items():
                (directory / f"{stem}.json").write_text(
                    payload if isinstance(payload, str) else json.dumps(payload),
                    encoding="utf-8",
                )
            self.mod.ROUTING_DIR, self.mod.ROOT = directory, Path(raw)
            try:
                return self.mod.validate_routing(names)
            finally:
                self.mod.ROUTING_DIR, self.mod.ROOT = original_dir, original_root

    def case(self, skill: str = "alpha") -> dict:
        return {"skill": skill, "positive": ["do a thing"], "negative": ["do another"]}

    def test_a_well_formed_case_passes(self) -> None:
        self.assertEqual(self.routing({"alpha": self.case()}, {"alpha"}), [])

    def test_a_case_for_a_skill_that_does_not_exist_is_caught(self) -> None:
        errors = self.routing({"ghost": self.case("ghost")}, {"alpha"})
        self.assertTrue(any("unknown skill" in e for e in errors), errors)

    def test_a_filename_that_disagrees_with_the_skill_is_caught(self) -> None:
        errors = self.routing({"beta": self.case("alpha")}, {"alpha"})
        self.assertTrue(any("filename must match" in e for e in errors), errors)

    def test_an_empty_positive_list_is_caught(self) -> None:
        case = self.case()
        case["positive"] = []
        errors = self.routing({"alpha": case}, {"alpha"})
        self.assertTrue(any("positive must be" in e for e in errors), errors)

    def test_a_missing_negative_list_is_caught(self) -> None:
        """Without negatives a case cannot show the skill repels anything."""
        case = self.case()
        del case["negative"]
        errors = self.routing({"alpha": case}, {"alpha"})
        self.assertTrue(any("negative must be" in e for e in errors), errors)

    def test_invalid_json_is_reported_rather_than_raised(self) -> None:
        errors = self.routing({"alpha": "{not json"}, {"alpha"})
        self.assertTrue(any("invalid JSON" in e for e in errors), errors)

    def test_a_skill_with_no_case_at_all_is_caught(self) -> None:
        errors = self.routing({"alpha": self.case()}, {"alpha", "orphan"})
        self.assertTrue(any("missing routing cases: orphan" in e for e in errors), errors)

    def test_string_list_rejects_what_is_not_one(self) -> None:
        self.assertTrue(self.mod.string_list(["a"]))
        self.assertFalse(self.mod.string_list([]))
        self.assertFalse(self.mod.string_list("a"))
        self.assertFalse(self.mod.string_list([1]))
        self.assertFalse(self.mod.string_list(None))
