# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Every complaint the skill-facing validators can make, provoked.

A skill is read by a router that sees only its frontmatter, by installers
that trust its metadata.json, and by consumers of index.json who never open
the skill at all. The validators here guard those three views plus the
system prompts and the scaffold templates new skills are born from.

Each test breaks one rule and asserts the `FAIL:` line (or, for
validate-skills, the per-skill bullet) that names it. A nonzero exit alone
would pass as long as any one rule still fired.
"""

from __future__ import annotations

import json
import unittest

from .validator_harness import BrokenTreeCase


class SkillContractBranchTests(BrokenTreeCase):
    """validate-skills.py enforces the Agent Skills spec plus the router contract."""

    SCRIPT = "validate-skills.py"
    GOOD_DESCRIPTION = "Use when the fixture needs a valid description."

    def setUp(self) -> None:
        self.skill = min((self.fixture / "skills").glob("*/SKILL.md"))
        self.name = self.skill.parent.name

    def write_skill(self, frontmatter: str, body: str = "# Title\n\nbody\n") -> None:
        self.overwrite(
            str(self.skill.relative_to(self.fixture)), f"---\n{frontmatter}\n---\n\n{body}"
        )

    def assert_skill_fails(self, *expected: str) -> str:
        return self.assert_fails(self.SCRIPT, *(f"    - {text}" for text in expected))

    def valid(self, extra: str = "") -> str:
        return f"name: {self.name}\ndescription: {self.GOOD_DESCRIPTION}\n{extra}".rstrip("\n")

    def test_an_unterminated_frontmatter_block_is_refused(self) -> None:
        self.overwrite(
            str(self.skill.relative_to(self.fixture)), f"---\nname: {self.name}\n\n# Title\n"
        )
        self.assert_skill_fails("unterminated frontmatter block")

    def test_a_frontmatter_block_with_no_fields_names_both_missing_ones(self) -> None:
        """Stray text before any key belongs to no field and is ignored."""
        self.write_skill("stray text before any key")
        self.assert_skill_fails("missing `name`", "missing `description`")

    def test_a_key_outside_the_spec_is_refused_by_name(self) -> None:
        """`skills-ref validate` rejects unknown keys, so other runtimes would too."""
        self.write_skill(self.valid("version: 1.0.0\ntags: a"))
        self.assert_skill_fails("frontmatter key(s) outside the Agent Skills spec: `tags`, `version`")

    def test_a_name_that_breaks_every_name_rule_is_refused_for_each(self) -> None:
        """Too long, not kebab-case and not the directory: three separate rules."""
        name = "Bad_" + "x" * 61
        self.write_skill(f"name: {name}\ndescription: {self.GOOD_DESCRIPTION}")
        self.assert_skill_fails(
            f"`name` ({name!r}) != directory name ({self.name!r})",
            f"`name` is not kebab-case: {name!r}",
            "`name` too long: 65 > 64 chars",
        )

    def test_an_empty_compatibility_field_is_refused(self) -> None:
        self.write_skill(self.valid("compatibility:"))
        self.assert_skill_fails("`compatibility` present but empty")

    def test_an_overlong_compatibility_field_is_refused(self) -> None:
        """The spec caps it; other runtimes reject the skill beyond that."""
        self.write_skill(self.valid("compatibility: " + "x" * 501))
        self.assert_skill_fails("`compatibility` too long: 501 > 500 chars")

    def test_an_empty_metadata_block_is_refused(self) -> None:
        self.write_skill(self.valid("metadata:"))
        self.assert_skill_fails("`metadata` present but empty")

    def test_nested_metadata_is_refused(self) -> None:
        """The spec allows string values only; a nested map is not one."""
        self.write_skill(self.valid("metadata:\n  nested:\n    deep: value"))
        self.assert_skill_fails("`metadata` must be flat string key/value pairs: 'nested:'")

    def test_an_overlong_description_is_refused(self) -> None:
        """Claude Code truncates silently past the cap, so the tail never routes."""
        description = "Use when " + "x" * 1016
        self.write_skill(f"name: {self.name}\ndescription: {description}")
        self.assert_skill_fails("`description` too long: 1025 > 1024 chars")

    def test_a_body_without_a_heading_is_refused(self) -> None:
        self.write_skill(self.valid(), body="Just prose, no heading.\n")
        self.assert_skill_fails("body has no top-level `# ` heading")

    def test_an_overlong_skill_is_refused(self) -> None:
        """Past the budget, activation loads more than progressive disclosure allows."""
        self.write_skill(self.valid(), body="# Title\n" + "line\n" * 500)
        self.assert_skill_fails("SKILL.md too long:")

    def test_an_empty_skill_tree_is_refused(self) -> None:
        """No skills is a broken checkout, not a vacuous pass."""
        self.move_aside("skills")
        self.assert_fails(self.SCRIPT, "no SKILL.md files found under")


class SkillMetadataBranchTests(BrokenTreeCase):
    """metadata.json declares what a skill may do; installers act on it."""

    SCRIPT = "validate-skill-metadata.py"

    def setUp(self) -> None:
        self.path = min((self.fixture / "skills").glob("*/metadata.json"))
        self.relative = str(self.path.relative_to(self.fixture))

    def edit(self, mutate) -> None:
        self.edit_json(self.relative, mutate)

    def policy(self, key: str, value) -> None:
        self.edit(lambda data: data["safety_policy"].__setitem__(key, value))

    def fails_with(self, message: str) -> None:
        self.assert_fails(self.SCRIPT, f"FAIL: {self.relative}: {message}")

    @unittest.expectedFailure
    def test_malformed_metadata_is_reported_rather_than_raised(self) -> None:
        """Known defect: the first pass reports it, the second pass crashes.

        main() catches the JSONDecodeError and records "invalid JSON", then
        its coverage loop calls metadata_for(), which parses the same file
        again without a handler and raises. Marked as an expected failure so
        the suite stays green while the defect stands, and turns red -- as an
        unexpected success -- the day it is fixed and this marker must go.
        """
        self.overwrite(self.relative, "{ not json")
        self.fails_with("invalid JSON")

    def test_metadata_without_an_owner_is_refused(self) -> None:
        self.edit(lambda data: data.pop("owner"))
        self.fails_with("missing owner")

    def test_metadata_without_a_bundle_field_is_refused(self) -> None:
        """General skills say so with null; silence is not the same answer."""
        self.edit(lambda data: data.pop("bundle"))
        self.fails_with("missing bundle (use null for general skills)")

    def test_a_bundle_that_is_not_kebab_case_is_refused(self) -> None:
        self.edit(lambda data: data.__setitem__("bundle", "Not Kebab"))
        self.fails_with("bundle must be null or kebab-case")

    def test_an_unknown_maturity_is_refused(self) -> None:
        self.edit(lambda data: data.__setitem__("maturity", "alpha"))
        self.fails_with("maturity must be one of")

    def test_an_unsupported_agent_is_refused(self) -> None:
        self.edit(lambda data: data.__setitem__("supported_agents", ["gpt"]))
        self.fails_with("supported_agents must be subset of")

    def test_required_tools_that_are_not_strings_are_refused(self) -> None:
        self.edit(lambda data: data.__setitem__("required_tools", [1]))
        self.fails_with("required_tools must be a string list")

    def test_a_missing_safety_policy_is_refused(self) -> None:
        self.edit(lambda data: data.pop("safety_policy"))
        self.fails_with("safety_policy must be an object")

    def test_an_unknown_network_access_level_is_refused(self) -> None:
        self.policy("network_access", "sometimes")
        self.fails_with("safety_policy.network_access must be one of")

    def test_a_safety_flag_that_is_not_boolean_is_refused(self) -> None:
        """A string "no" is truthy, so it would read as the opposite of itself."""
        self.policy("writes_files", "no")
        self.fails_with("safety_policy.writes_files must be boolean")

    def test_a_high_risk_skill_without_human_review_is_refused(self) -> None:
        def mutate(data: dict) -> None:
            data["safety_policy"]["risk_level"] = "high"
            data["safety_policy"]["requires_human_review"] = False

        self.edit(mutate)
        self.fails_with("high-risk skills must require human review")

    def test_a_skill_with_no_metadata_file_is_refused(self) -> None:
        self.remove(self.relative)
        skill_dir = str(self.path.parent.relative_to(self.fixture))
        self.assert_fails(self.SCRIPT, f"FAIL: {skill_dir}: no metadata.json")


class SkillIndexBranchTests(BrokenTreeCase):
    """index.json is what consumers read instead of the skills themselves."""

    SCRIPT = "validate-skill-index.py"
    FILE = "index.json"

    def first_skill(self, mutate):
        return lambda data: mutate(data["skills"][0])

    def first_command(self, mutate):
        return lambda data: mutate(data["commands"][0])

    def skill_name(self) -> str:
        return json.loads((self.fixture / self.FILE).read_text(encoding="utf-8"))["skills"][0]["name"]

    def test_a_missing_index_is_refused(self) -> None:
        self.remove(self.FILE)
        self.assert_fails(self.SCRIPT, "FAIL: index.json missing")

    def test_counts_that_disagree_with_their_lists_are_refused(self) -> None:
        def mutate(data: dict) -> None:
            data["skill_count"] += 1
            data["command_count"] += 1

        self.edit_json(self.FILE, mutate)
        self.assert_fails(
            self.SCRIPT,
            "FAIL: skill_count does not match skills length",
            "FAIL: command_count does not match commands length",
        )

    def test_duplicate_names_are_refused(self) -> None:
        """Two entries under one name make lookup by name ambiguous."""

        def mutate(data: dict) -> None:
            data["skills"].append(dict(data["skills"][0]))
            data["commands"].append(dict(data["commands"][0]))

        self.edit_json(self.FILE, mutate)
        self.assert_fails(
            self.SCRIPT,
            "FAIL: duplicate skill names in index",
            "FAIL: duplicate command names in index",
        )

    def test_a_skill_without_a_path_is_refused(self) -> None:
        name = self.skill_name()
        self.edit_json(self.FILE, self.first_skill(lambda skill: skill.pop("path")))
        self.assert_fails(self.SCRIPT, f"FAIL: {name}: missing path")

    def test_a_skill_path_that_does_not_exist_is_refused(self) -> None:
        name = self.skill_name()
        self.edit_json(
            self.FILE, self.first_skill(lambda skill: skill.__setitem__("path", "skills/gone"))
        )
        self.assert_fails(self.SCRIPT, f"FAIL: {name}: indexed SKILL.md path does not exist")

    def test_a_skill_missing_tags_and_evals_is_refused_for_each(self) -> None:
        """Tags feed search; the evals are what earned it a place in the index."""
        name = self.skill_name()

        def mutate(skill: dict) -> None:
            skill["tags"] = []
            skill["evals"] = {"routing": False, "behavioral": False}

        self.edit_json(self.FILE, self.first_skill(mutate))
        self.assert_fails(
            self.SCRIPT,
            f"FAIL: {name}: missing tags",
            f"FAIL: {name}: missing routing eval",
            f"FAIL: {name}: missing behavioral eval",
        )

    def test_a_quality_score_that_is_not_an_integer_is_refused(self) -> None:
        name = self.skill_name()
        self.edit_json(
            self.FILE, self.first_skill(lambda skill: skill.__setitem__("quality", {"score": "A"}))
        )
        self.assert_fails(self.SCRIPT, f"FAIL: {name}: missing integer quality score")

    def test_a_quality_score_below_the_threshold_is_refused(self) -> None:
        name = self.skill_name()
        self.edit_json(
            self.FILE, self.first_skill(lambda skill: skill["quality"].__setitem__("score", 74))
        )
        self.assert_fails(self.SCRIPT, f"FAIL: {name}: quality score below publication threshold")

    def test_incomplete_coverage_summary_is_refused(self) -> None:
        self.edit_json(
            self.FILE, lambda data: data["coverage"]["routing"].__setitem__("covered", 0)
        )
        self.assert_fails(self.SCRIPT, "FAIL: routing coverage summary is not complete")

    def test_a_missing_aggregate_quality_score_is_refused(self) -> None:
        self.edit_json(self.FILE, lambda data: data.pop("quality"))
        self.assert_fails(self.SCRIPT, "FAIL: missing aggregate quality score")

    def test_bundle_counts_that_do_not_add_up_are_refused(self) -> None:
        self.edit_json(self.FILE, lambda data: data["bundles"].__setitem__("_general", 0))
        self.assert_fails(self.SCRIPT, "FAIL: bundle counts do not sum to skill_count")

    def test_a_command_without_a_description_or_file_is_refused(self) -> None:
        def mutate(command: dict) -> None:
            command["description"] = ""
            command["path"] = "commands/gone.md"

        name = json.loads((self.fixture / self.FILE).read_text(encoding="utf-8"))["commands"][0]["name"]
        self.edit_json(self.FILE, self.first_command(mutate))
        self.assert_fails(
            self.SCRIPT,
            f"FAIL: command {name}: missing description",
            f"FAIL: command {name}: indexed path does not exist",
        )


class SystemPromptBranchTests(BrokenTreeCase):
    """One prompt per supported language plus a base; nothing more, nothing less."""

    SCRIPT = "validate-system-prompts.py"

    def test_a_missing_base_prompt_is_refused(self) -> None:
        self.remove("system-prompts/_base.md")
        self.assert_fails(self.SCRIPT, "FAIL: system-prompts/_base.md missing")

    def test_a_base_prompt_without_a_heading_is_refused(self) -> None:
        self.overwrite("system-prompts/_base.md", "Standards, but no heading.\n")
        self.assert_fails(self.SCRIPT, "FAIL: system-prompts/_base.md missing top-level heading")

    def test_a_missing_language_prompt_is_refused(self) -> None:
        self.remove("system-prompts/python.md")
        self.assert_fails(self.SCRIPT, "FAIL: system-prompts/python.md missing")

    def test_an_empty_language_prompt_is_refused(self) -> None:
        self.overwrite("system-prompts/python.md", "\n")
        self.assert_fails(
            self.SCRIPT,
            "FAIL: system-prompts/python.md is empty",
            "FAIL: system-prompts/python.md missing top-level heading",
        )

    def test_an_unexpected_prompt_is_refused(self) -> None:
        """A prompt for a language the CLI does not know is never offered."""
        self.overwrite("system-prompts/cobol.md", "# COBOL\n")
        self.assert_fails(self.SCRIPT, "FAIL: unexpected system prompt profile(s): cobol.md")


class TemplateBranchTests(BrokenTreeCase):
    """`scaffold` copies these; a broken template breaks every skill made from it."""

    SCRIPT = "validate-templates.py"

    def test_a_missing_json_template_is_refused(self) -> None:
        """Reported once as missing, and not parsed as though it were there."""
        self.remove("templates/skill/metadata.json")
        output = self.assert_fails(
            self.SCRIPT, "FAIL: missing template: templates/skill/metadata.json"
        )
        self.assertNotIn("metadata.json invalid JSON", output)

    def test_a_malformed_json_template_is_refused(self) -> None:
        self.overwrite("templates/evals/routing.json", "{ not json")
        self.assert_fails(self.SCRIPT, "FAIL: templates/evals/routing.json invalid JSON")

    def test_a_skill_template_without_frontmatter_or_placeholder_is_refused(self) -> None:
        self.overwrite("templates/skill/SKILL.md", "# A skill\n")
        self.assert_fails(
            self.SCRIPT,
            "FAIL: skill template must start with frontmatter",
            "FAIL: skill template must contain example-skill placeholder",
        )
