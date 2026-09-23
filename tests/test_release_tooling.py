# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Scripts the gate never runs, and therefore never proved.

Completions are produced by `make completions`, release assets are verified
by a scheduled workflow, and publishing readiness is checked by hand. None of
them is a gate check, so each had zero coverage -- which is not a gap in a
number, it is the absence of any evidence that they work.

The completions list was the first thing this caught: hand-maintained, and one
command stale.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from .support import ROOT, load_script


class CompletionTests(unittest.TestCase):
    """Completions that disagree with the CLI teach the wrong surface."""

    def setUp(self) -> None:
        self.mod = load_script("generate-completions.py")
        self.surface = load_script("validate-cli-surface.py")

    def test_every_subcommand_the_parser_declares_is_offered(self) -> None:
        """`verify` was missing for as long as the list was written by hand."""
        self.assertEqual(sorted(self.mod.subcommands()), sorted(self.surface.subcommands()))

    def test_the_integrity_command_is_offered(self) -> None:
        # Named explicitly: this is the one that was absent, and the one whose
        # absence matters most.
        self.assertIn("verify", self.mod.subcommands())

    def test_each_shell_gets_every_subcommand(self) -> None:
        for render in (self.mod.render_bash, self.mod.render_zsh, self.mod.render_fish):
            text = render()
            for name in self.mod.subcommands():
                self.assertIn(name, text, f"{render.__name__} omits {name}")

    def test_the_generated_files_carry_a_licence(self) -> None:
        for render in (self.mod.render_bash, self.mod.render_zsh, self.mod.render_fish):
            self.assertIn("SPDX-License-Identifier", render())

    def test_what_is_on_disk_is_what_the_generator_produces(self) -> None:
        for name, render in (
            ("agtmls.bash", self.mod.render_bash),
            ("_agtmls", self.mod.render_zsh),
            ("agtmls.fish", self.mod.render_fish),
        ):
            path = ROOT / "completions" / name
            self.assertTrue(path.exists(), f"{name} is missing")
            self.assertEqual(
                path.read_text(encoding="utf-8"), render(),
                f"{name} is stale; run generate-completions.py --write",
            )

    def test_a_parser_with_no_subcommands_is_refused(self) -> None:
        """Silently emitting empty completions would look like success."""
        import argparse

        original = self.mod.build_parser
        try:
            self.mod.build_parser = lambda: argparse.ArgumentParser()
            with self.assertRaises(SystemExit):
                self.mod.subcommands()
        finally:
            self.mod.build_parser = original


class ReleaseAssetTests(unittest.TestCase):
    """Verifying a published release, without publishing one."""

    def setUp(self) -> None:
        self.mod = load_script("verify-release-assets.py")

    def test_sha256_matches_the_reference_implementation(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "asset.bin"
            payload = b"agtmls release asset\n" * 100
            path.write_bytes(payload)
            self.assertEqual(self.mod.sha256(path), hashlib.sha256(payload).hexdigest())

    def test_sha256_reads_a_large_file_in_chunks(self) -> None:
        """A release asset must not have to fit in memory to be checked."""
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "big.bin"
            payload = b"x" * (3 * 1024 * 1024)
            path.write_bytes(payload)
            self.assertEqual(self.mod.sha256(path), hashlib.sha256(payload).hexdigest())

    def test_provider_assets_come_from_the_provider_registry(self) -> None:
        assets = self.mod.provider_assets()
        self.assertTrue(assets, "no provider assets derived from providers.json")
        providers = json.loads((ROOT / "providers.json").read_text(encoding="utf-8"))
        for name in providers.get("export_targets", {}):
            self.assertTrue(
                any(name in asset for asset in assets),
                f"{name} is an export target with no release asset",
            )

    def test_the_base_assets_are_the_manifest_and_its_checksums(self) -> None:
        self.assertIn("release-manifest.json", self.mod.BASE_ASSETS)
        self.assertIn("SHA256SUMS", self.mod.BASE_ASSETS)


class PublishingReadinessTests(unittest.TestCase):
    """What stands between a built artifact and a registry nobody can install from."""

    def setUp(self) -> None:
        self.mod = load_script("check-publishing-readiness.py")

    def test_a_missing_repository_is_reported_not_raised(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            problems = self.mod.check("ghost", Path(raw) / "nowhere", "pypi", "release")
        self.assertTrue(problems, "a missing repository produced no problem")

    def test_a_repository_with_no_release_workflow_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            repo = Path(raw) / "repo"
            (repo / ".github" / "workflows").mkdir(parents=True)
            problems = self.mod.check("thing", repo, "pypi", "release")
        self.assertTrue(problems)

    def test_every_declared_package_names_a_registry_and_an_environment(self) -> None:
        self.assertTrue(self.mod.PACKAGES, "no packages declared")
        for entry in self.mod.PACKAGES:
            self.assertEqual(len(entry), 4, entry)
            name, _, registry, environment = entry
            self.assertTrue(name and registry and environment, entry)
