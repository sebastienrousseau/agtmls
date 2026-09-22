# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Version policy, and the content addresses it must not disturb."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from .support import CLI, ROOT, load_script, skill_text  # noqa: F401  (used by the cases below)


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

    def test_no_skill_can_escape_the_version_free_gate(self) -> None:
        """The inverse of the rule this test used to enforce.

        Skills were once required to carry the registry version, and this
        asserted none could escape that. They must now carry none, so what a
        newly added skill must not escape is the check that forbids it -- and
        that list has to stay derived from the tree, not hardcoded.
        """
        module = load_script("validate-version-policy.py")
        guarded = set(module.VERSION_FREE)
        for meta in (ROOT / "skills").glob("*/metadata.json"):
            self.assertIn(meta, guarded, f"{meta.name} is outside the version-free gate")
        self.assertEqual(
            set(module.METADATA_FILES), {ROOT / ".claude-plugin" / "plugin.json"},
            "the registry version must be authored in exactly one file",
        )


class DigestStabilityTests(unittest.TestCase):
    """A content address must change when, and only when, the content does.

    Every skill used to carry `agtmls-version` in its frontmatter and a
    matching `version` in metadata.json, both stamped with the registry's
    version on every release. Both are inside the digest, so a release moved
    all 31 digests whether or not a single skill had changed. That made
    `agtmls verify` unable to tell a maintainer's bump from tampering, which
    is the one question it exists to answer.
    """

    def copy_skill(self, destination: Path) -> Path:
        source = ROOT / "skills" / "handoff"
        target = destination / "handoff"
        shutil.copytree(source, target)
        return target

    def test_digest_survives_a_version_bump(self) -> None:
        sys.path.insert(0, str(ROOT / "scripts"))
        from _lib.digest import skill_digest

        current = json.loads(
            (ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )["version"]
        bumped = "9.9.9"
        with tempfile.TemporaryDirectory() as raw:
            skill = self.copy_skill(Path(raw))
            before = skill_digest(skill)
            for path in sorted(skill.rglob("*")):
                if path.is_file():
                    text = path.read_text(encoding="utf-8", errors="replace")
                    if current in text:
                        path.write_text(text.replace(current, bumped), encoding="utf-8")
            after = skill_digest(skill)
        self.assertEqual(
            before, after,
            "a release moved this skill's content address without its content changing",
        )

    def test_no_skill_carries_the_registry_version(self) -> None:
        offenders = []
        for metadata in sorted((ROOT / "skills").glob("*/metadata.json")):
            if "version" in json.loads(metadata.read_text(encoding="utf-8")):
                offenders.append(str(metadata.relative_to(ROOT)))
        for skill_md in sorted((ROOT / "skills").glob("*/SKILL.md")):
            if "agtmls-version" in skill_md.read_text(encoding="utf-8"):
                offenders.append(str(skill_md.relative_to(ROOT)))
        self.assertEqual(
            offenders[:5], [],
            "a version stamped into a skill puts the release into its digest",
        )

    def test_the_version_lives_in_few_enough_places_to_track(self) -> None:
        """Scorecard 7.2. Generated artifacts legitimately restate it."""
        current = json.loads(
            (ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )["version"]
        generated = (
            "sbom", "provenance", "index.json", "mcp-resources",
            "catalog", "lock", "changelog", "site", "bench-baseline",
        )
        # The per-provider manifests restate the version by construction. The
        # generator is asked which files it owns, rather than this test
        # carrying a second copy of that list to drift from.
        manifests = load_script("generate-plugin-manifests.py")
        owned = set(manifests.render(
            json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        )) if hasattr(manifests, "render") else set()
        carriers = []
        for path in sorted(ROOT.rglob("*")):
            if not path.is_file() or path.is_symlink():
                continue
            relative = path.relative_to(ROOT)
            if {".git", "__pycache__", ".agtmls", "benchmarks", "share", "completions"} & set(relative.parts):
                continue
            # Registry *content* is not registry *packaging*. The noyalib
            # skills discuss noyalib's own v0.0.6, which has nothing to do
            # with this registry's version and must not be counted as a
            # place it can drift.
            if {"skills", "references", "system-prompts", "agents", "commands",
                "evals", "templates"} & set(relative.parts):
                continue
            if any(marker in path.name.lower() for marker in generated):
                continue
            if str(relative) in owned:
                continue
            if path.suffix.lower() not in {".json", ".toml", ".py", ".md", ".yml", ".yaml"}:
                continue
            if current in path.read_text(encoding="utf-8", errors="replace"):
                carriers.append(str(relative))
        self.assertLessEqual(
            len(carriers), 8,
            f"{current} is authored in {len(carriers)} files: {carriers[:10]}",
        )
