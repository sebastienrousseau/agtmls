# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Every complaint the manifest and metadata validators can make, provoked.

These files are what other runtimes read: the Claude plugin manifest and its
marketplace entry, the provider table, the install profiles, the command
files and the skill lifecycle. Each validator below checks a dozen separate
rules, and the gate only ever sees them all pass together. A rule that stops
firing looks exactly like a rule that is satisfied.

So each test breaks one rule and asserts the exact `FAIL:` line that names
it. Asserting only a nonzero exit would let one rule's message cover for
another's silence.
"""

from __future__ import annotations

import json

from .validator_harness import BrokenTreeCase

PLUGIN = ".claude-plugin/plugin.json"
MARKETPLACE = ".claude-plugin/marketplace.json"


class PluginManifestBranchTests(BrokenTreeCase):
    """plugin.json and marketplace.json gate distribution through Claude Code."""

    SCRIPT = "validate-plugin-manifest.py"

    def entry(self, data: dict) -> dict:
        return data["plugins"][0]

    def test_a_missing_manifest_names_the_generator_that_restores_it(self) -> None:
        """The fix for a missing generated file is to run its generator."""
        self.remove(PLUGIN)
        self.assert_fails(
            self.SCRIPT,
            "FAIL: .claude-plugin/plugin.json missing; run generate-plugin-manifests.py --write",
        )

    def test_a_missing_marketplace_is_reported_on_its_own(self) -> None:
        self.remove(MARKETPLACE)
        self.assert_fails(self.SCRIPT, "FAIL: .claude-plugin/marketplace.json missing")

    def test_malformed_json_is_reported_rather_than_raised(self) -> None:
        """A traceback would hide which of the two files is broken."""
        self.overwrite(MARKETPLACE, "{ not json")
        self.assert_fails(self.SCRIPT, "FAIL: .claude-plugin/marketplace.json invalid JSON")

    def test_agents_given_as_a_directory_string_are_refused(self) -> None:
        """`claude plugin validate` rejects a directory where it wants files."""
        self.edit_json(PLUGIN, lambda data: data.__setitem__("agents", "./agents"))
        self.assert_fails(
            self.SCRIPT,
            "FAIL: plugin manifest agents must be an array of agent file paths, not str",
        )

    def test_a_commands_path_that_escapes_is_refused(self) -> None:
        self.edit_json(PLUGIN, lambda data: data.__setitem__("commands", "../commands"))
        self.assert_fails(
            self.SCRIPT, "FAIL: plugin manifest commands must be a safe ./ relative path"
        )

    def test_a_commands_path_naming_a_file_is_refused(self) -> None:
        """A runtime scans the commands path; a file there yields no commands."""
        self.edit_json(PLUGIN, lambda data: data.__setitem__("commands", "./README.md"))
        self.assert_fails(
            self.SCRIPT, "FAIL: plugin manifest commands path must be a directory: ./README.md"
        )

    def test_an_mit_claim_without_mit_text_is_refused(self) -> None:
        """The manifest's licence field is a promise the licence file must keep."""
        self.overwrite("LICENSE-MIT", "All rights reserved.\n")
        self.assert_fails(self.SCRIPT, "FAIL: LICENSE file must contain MIT License text")

    def test_a_marketplace_name_that_is_not_kebab_case_is_refused(self) -> None:
        self.edit_json(MARKETPLACE, lambda data: data.__setitem__("name", "Agt MLS"))
        self.assert_fails(self.SCRIPT, "FAIL: marketplace name must be kebab-case")

    def test_a_reserved_marketplace_name_is_refused(self) -> None:
        """A catalog under a reserved name stops loading entirely."""
        self.edit_json(
            MARKETPLACE, lambda data: data.__setitem__("name", "claude-plugins-official")
        )
        self.assert_fails(
            self.SCRIPT,
            "FAIL: marketplace name 'claude-plugins-official' is reserved for official Anthropic use",
        )

    def test_a_marketplace_without_an_owner_is_refused(self) -> None:
        self.edit_json(MARKETPLACE, lambda data: data.pop("owner"))
        self.assert_fails(self.SCRIPT, "FAIL: marketplace owner.name is required")

    def test_an_empty_marketplace_is_refused(self) -> None:
        self.edit_json(MARKETPLACE, lambda data: data.__setitem__("plugins", []))
        self.assert_fails(self.SCRIPT, "FAIL: marketplace plugins must be a non-empty array")

    def test_a_marketplace_that_does_not_list_this_plugin_is_refused(self) -> None:
        """A catalog that lists something else installs something else."""
        self.edit_json(MARKETPLACE, lambda data: self.entry(data).__setitem__("name", "other"))
        self.assert_fails(self.SCRIPT, "FAIL: marketplace does not list the plugin 'agtmls'")

    def test_a_marketplace_entry_that_is_not_an_object_is_refused(self) -> None:
        self.edit_json(MARKETPLACE, lambda data: data["plugins"].append("agtmls"))
        self.assert_fails(self.SCRIPT, "FAIL: marketplace plugin entry must be an object")

    def test_a_second_entry_is_checked_on_its_own_terms(self) -> None:
        """An unrelated entry is held to the name rule, not to plugin.json.

        It carries no skills or agents and names another plugin, so the
        version-pinning comparison must not apply to it -- only the kebab-case
        rule it breaks.
        """
        self.edit_json(
            MARKETPLACE,
            lambda data: data["plugins"].append(
                {"name": "Other Plugin", "source": {"source": "github", "repo": "a/b"}}
            ),
        )
        output = self.assert_fails(
            self.SCRIPT, "FAIL: marketplace plugin 'Other Plugin' name must be kebab-case"
        )
        self.assertNotIn("'Other Plugin' version", output)

    def test_an_entry_source_that_escapes_is_refused(self) -> None:
        self.edit_json(
            MARKETPLACE, lambda data: self.entry(data).__setitem__("source", "../elsewhere")
        )
        self.assert_fails(
            self.SCRIPT,
            "FAIL: marketplace plugin 'agtmls' source must be a safe ./ relative path "
            "or a source object",
        )

    def test_an_entry_without_a_source_is_refused(self) -> None:
        self.edit_json(MARKETPLACE, lambda data: self.entry(data).pop("source"))
        self.assert_fails(self.SCRIPT, "FAIL: marketplace plugin 'agtmls' source is required")

    def test_an_entry_whose_version_drifts_from_plugin_json_is_refused(self) -> None:
        """Installed users update on the catalog's version, not the manifest's."""
        version = json.loads((self.fixture / PLUGIN).read_text(encoding="utf-8"))["version"]
        self.edit_json(
            MARKETPLACE, lambda data: self.entry(data).__setitem__("version", "0.0.0-stale")
        )
        self.assert_fails(
            self.SCRIPT,
            f"FAIL: marketplace plugin 'agtmls' version ('0.0.0-stale') != plugin.json ('{version}')",
        )


class ProviderBranchTests(BrokenTreeCase):
    """providers.json decides which runtimes an install or export can target."""

    SCRIPT = "validate-providers.py"
    FILE = "providers.json"

    def test_providers_pass_when_intact(self) -> None:
        self.assertIn("OK: provider metadata valid", self.assert_clean(self.SCRIPT))

    def test_a_missing_table_is_reported_rather_than_raised(self) -> None:
        self.remove(self.FILE)
        self.assert_fails(self.SCRIPT, "FAIL: providers.json invalid or missing")

    def test_malformed_json_is_reported_rather_than_raised(self) -> None:
        self.overwrite(self.FILE, "{ not json")
        self.assert_fails(self.SCRIPT, "FAIL: providers.json invalid or missing")

    def test_an_unknown_schema_version_is_refused(self) -> None:
        self.edit_json(self.FILE, lambda data: data.__setitem__("schema_version", 2))
        self.assert_fails(self.SCRIPT, "FAIL: providers.json schema_version must be 1")

    def test_a_dropped_native_agent_is_refused(self) -> None:
        self.edit_json(self.FILE, lambda data: data["native_agents"].pop("aider"))
        self.assert_fails(self.SCRIPT, "FAIL: native_agents must be exactly")

    def test_a_native_agent_that_is_not_an_object_is_refused(self) -> None:
        self.edit_json(
            self.FILE, lambda data: data["native_agents"].__setitem__("claude", "symlink")
        )
        self.assert_fails(self.SCRIPT, "FAIL: native agent claude must be an object")

    def test_a_native_agent_missing_a_path_is_refused(self) -> None:
        """Without a prompt_file the installer has nothing to link."""
        self.edit_json(self.FILE, lambda data: data["native_agents"]["claude"].pop("prompt_file"))
        self.assert_fails(self.SCRIPT, "FAIL: native agent claude missing prompt_file")

    def test_a_native_agent_that_copies_is_refused(self) -> None:
        """A copied install silently stops receiving registry updates."""
        self.edit_json(
            self.FILE,
            lambda data: data["native_agents"]["claude"].__setitem__("install_mode", "copy"),
        )
        self.assert_fails(self.SCRIPT, "FAIL: native agent claude install_mode must be symlink")

    def test_a_native_agent_must_say_what_allowed_tools_means_to_it(self) -> None:
        """Claude Code pre-approves the field; the Agent Skills spec makes it a
        declaration. AGT-CAP-001 reports escalation per target from this."""
        self.edit_json(self.FILE, lambda data: data["native_agents"]["claude"].pop("allowed_tools_semantics"))
        self.assert_fails(self.SCRIPT, "FAIL: native agent claude missing allowed_tools_semantics")
        self.edit_json(
            self.FILE,
            lambda data: data["native_agents"]["claude"].__setitem__("allowed_tools_semantics", "maybe"),
        )
        self.assert_fails(
            self.SCRIPT,
            "FAIL: native agent claude allowed_tools_semantics must be grant, declaration or ignored",
        )

    def test_approval_settings_are_checked_for_shape(self) -> None:
        """doctor reads these to say when a skill's safety_policy is advisory."""
        self.edit_json(self.FILE, lambda data: data["native_agents"]["claude"].__setitem__("approval_settings", "x"))
        self.assert_fails(self.SCRIPT, "FAIL: native agent claude approval_settings must be a list")
        self.edit_json(self.FILE, lambda data: data["native_agents"]["claude"].__setitem__("approval_settings", [
            7, {"file": "", "scope": "user", "key": "k", "format": "ini", "unattended": [], "classified": "auto"},
        ]))
        self.assert_fails(self.SCRIPT, "FAIL: native agent claude approval_settings[0] must be an object")
        self.assert_fails(self.SCRIPT, "FAIL: native agent claude approval_settings[1] missing file")
        self.assert_fails(self.SCRIPT, "FAIL: native agent claude approval_settings[1] format must be json, toml or yaml")
        self.assert_fails(self.SCRIPT, "FAIL: native agent claude approval_settings[1] needs the unattended values it recognises")
        self.assert_fails(self.SCRIPT, "FAIL: native agent claude approval_settings[1] classified must be a list")

    def test_plugin_targets_that_are_not_an_object_are_refused(self) -> None:
        """Treated as empty afterwards, so every required target is then missing."""
        self.edit_json(self.FILE, lambda data: data.__setitem__("plugin_targets", []))
        self.assert_fails(
            self.SCRIPT,
            "FAIL: plugin_targets must be an object",
            "FAIL: missing plugin target: kimi",
        )

    def test_a_dropped_plugin_target_is_refused(self) -> None:
        self.edit_json(self.FILE, lambda data: data["plugin_targets"].pop("kimi"))
        self.assert_fails(self.SCRIPT, "FAIL: missing plugin target: kimi")

    def test_a_plugin_target_that_is_not_an_object_is_refused(self) -> None:
        self.edit_json(self.FILE, lambda data: data["plugin_targets"].__setitem__("kimi", "yes"))
        self.assert_fails(self.SCRIPT, "FAIL: plugin target kimi must be an object")

    def test_a_plugin_target_with_a_blank_description_is_refused(self) -> None:
        self.edit_json(
            self.FILE,
            lambda data: data["plugin_targets"]["kimi"].__setitem__("description", "  "),
        )
        self.assert_fails(self.SCRIPT, "FAIL: plugin target kimi must have description")

    def test_a_plugin_target_with_no_manifest_files_is_refused(self) -> None:
        self.edit_json(
            self.FILE,
            lambda data: data["plugin_targets"]["kimi"].__setitem__("manifest_files", []),
        )
        self.assert_fails(self.SCRIPT, "FAIL: plugin target kimi must have manifest_files")

    def test_a_manifest_path_that_escapes_is_refused(self) -> None:
        """Absolute and parent-relative paths would read outside the checkout."""
        for bad in ("../plugin.json", "/etc/plugin.json"):
            with self.subTest(path=bad):
                self.edit_json(
                    self.FILE,
                    lambda data, bad=bad: data["plugin_targets"]["kimi"].__setitem__(
                        "manifest_files", [bad]
                    ),
                )
                self.assert_fails(
                    self.SCRIPT,
                    "FAIL: plugin target kimi manifest_files must be safe relative paths",
                )

    def test_a_manifest_that_is_not_in_the_repository_is_refused(self) -> None:
        self.edit_json(
            self.FILE,
            lambda data: data["plugin_targets"]["kimi"].__setitem__(
                "manifest_files", ["absent/plugin.json"]
            ),
        )
        self.assert_fails(self.SCRIPT, "FAIL: plugin target kimi manifest missing: absent/plugin.json")

    def test_an_export_target_without_a_description_is_refused(self) -> None:
        self.edit_json(self.FILE, lambda data: data["export_targets"]["generic"].pop("description"))
        self.assert_fails(self.SCRIPT, "FAIL: export target generic must have description")

    def test_an_export_target_without_adapters_is_refused(self) -> None:
        self.edit_json(
            self.FILE,
            lambda data: data["export_targets"]["generic"].__setitem__("adapter_files", []),
        )
        self.assert_fails(self.SCRIPT, "FAIL: export target generic must have adapter_files")

    def test_an_adapter_path_that_escapes_is_refused(self) -> None:
        self.edit_json(
            self.FILE,
            lambda data: data["export_targets"]["generic"].__setitem__(
                "adapter_files", ["../ADAPTERS.md"]
            ),
        )
        self.assert_fails(
            self.SCRIPT, "FAIL: export target generic adapter_files must be safe relative paths"
        )

    def test_export_targets_that_are_not_an_object_are_refused(self) -> None:
        self.edit_json(self.FILE, lambda data: data.__setitem__("export_targets", ["generic"]))
        self.assert_fails(
            self.SCRIPT,
            "FAIL: export_targets must be an object",
            "FAIL: missing export target: generic",
        )


class ProfileBranchTests(BrokenTreeCase):
    """A profile is what `install --profile` resolves; a bad one installs wrongly."""

    SCRIPT = "validate-profiles.py"
    FILE = "profiles.json"

    def minimal(self, mutate):
        return lambda data: mutate(data["profiles"]["minimal"])

    def test_an_unknown_schema_version_is_refused(self) -> None:
        self.edit_json(self.FILE, lambda data: data.__setitem__("schema_version", 2))
        self.assert_fails(self.SCRIPT, "FAIL: profiles.json schema_version must be 1")

    def test_profiles_that_are_not_an_object_are_refused(self) -> None:
        self.edit_json(self.FILE, lambda data: data.__setitem__("profiles", []))
        self.assert_fails(
            self.SCRIPT,
            "FAIL: profiles must be an object",
            "FAIL: missing required profile: minimal",
        )

    def test_a_dropped_required_profile_is_refused(self) -> None:
        """The documented profiles are part of the CLI's promise."""
        self.edit_json(self.FILE, lambda data: data["profiles"].pop("research"))
        self.assert_fails(self.SCRIPT, "FAIL: missing required profile: research")

    def test_a_profile_that_is_not_an_object_is_refused(self) -> None:
        self.edit_json(self.FILE, lambda data: data["profiles"].__setitem__("minimal", []))
        self.assert_fails(self.SCRIPT, "FAIL: profile minimal must be an object")

    def test_a_profile_without_a_description_is_refused(self) -> None:
        self.edit_json(self.FILE, self.minimal(lambda p: p.__setitem__("description", " ")))
        self.assert_fails(self.SCRIPT, "FAIL: profile minimal missing description")

    def test_skills_that_are_not_a_string_list_are_refused(self) -> None:
        self.edit_json(self.FILE, self.minimal(lambda p: p.__setitem__("skills", "using-agtmls")))
        self.assert_fails(self.SCRIPT, "FAIL: profile minimal skills must be a string list")

    def test_bundles_that_are_not_a_string_list_are_refused(self) -> None:
        self.edit_json(self.FILE, self.minimal(lambda p: p.__setitem__("bundles", [1])))
        self.assert_fails(self.SCRIPT, "FAIL: profile minimal bundles must be a string list")

    def test_a_profile_naming_a_skill_that_does_not_exist_is_refused(self) -> None:
        self.edit_json(self.FILE, self.minimal(lambda p: p["skills"].append("no-such-skill")))
        self.assert_fails(
            self.SCRIPT, "FAIL: profile minimal references unknown skill: no-such-skill"
        )


class CommandBranchTests(BrokenTreeCase):
    """commands/*.md become slash commands; each must parse and do something."""

    SCRIPT = "validate-commands.py"
    VALID = '---\ndescription: "Do the thing."\n---\n\nRun `python3 scripts/agtmls.py list`.\n'

    def test_commands_pass_when_intact(self) -> None:
        self.assertIn("command file(s) valid", self.assert_clean(self.SCRIPT))

    def test_a_missing_commands_directory_is_refused_three_ways(self) -> None:
        """The directory, the manifest's pointer to it, and its contents."""
        self.move_aside("commands")
        self.assert_fails(
            self.SCRIPT,
            "FAIL: commands/ missing",
            "FAIL: plugin manifest commands path does not exist",
            "FAIL: commands/ has no command markdown files",
        )

    def test_a_missing_plugin_manifest_is_refused(self) -> None:
        self.remove(PLUGIN)
        self.assert_fails(self.SCRIPT, "FAIL: .claude-plugin/plugin.json missing")

    def test_a_manifest_pointing_elsewhere_is_refused(self) -> None:
        self.edit_json(PLUGIN, lambda data: data.__setitem__("commands", "./cmds"))
        self.assert_fails(self.SCRIPT, "FAIL: plugin manifest commands path must be ./commands")

    def test_a_command_without_frontmatter_is_refused(self) -> None:
        self.overwrite("commands/agtmls-audit.md", "Run `python3 scripts/agtmls.py audit`.\n")
        self.assert_fails(self.SCRIPT, "FAIL: commands/agtmls-audit.md: missing YAML frontmatter")

    def test_a_command_without_a_description_is_refused(self) -> None:
        """A continuation line is not a field, so it cannot stand in for one."""
        self.overwrite(
            "commands/agtmls-audit.md",
            "---\n  description: indented, so not a key\n---\n\n"
            "Run `python3 scripts/agtmls.py audit`.\n",
        )
        self.assert_fails(self.SCRIPT, "FAIL: commands/agtmls-audit.md: missing description")

    def test_a_command_filename_that_is_not_kebab_case_is_refused(self) -> None:
        """The filename is the slash command's name."""
        self.overwrite("commands/Bad_Name.md", self.VALID)
        self.assert_fails(
            self.SCRIPT, "FAIL: commands/Bad_Name.md: filename must be kebab-case .md"
        )

    def test_a_command_that_does_not_invoke_the_cli_is_refused(self) -> None:
        self.overwrite("commands/agtmls-audit.md", '---\ndescription: "Audit."\n---\n\nThink.\n')
        self.assert_fails(
            self.SCRIPT, "FAIL: commands/agtmls-audit.md: should invoke scripts/agtmls.py"
        )


class LifecycleBranchTests(BrokenTreeCase):
    """lifecycle.json carries the rules skill evolution may never relax."""

    SCRIPT = "validate-lifecycle.py"
    FILE = "lifecycle.json"

    def test_a_missing_lifecycle_is_refused(self) -> None:
        self.remove(self.FILE)
        self.assert_fails(self.SCRIPT, "FAIL: lifecycle.json missing")

    def test_an_unknown_schema_version_is_refused(self) -> None:
        self.edit_json(self.FILE, lambda data: data.__setitem__("schema_version", 2))
        self.assert_fails(self.SCRIPT, "FAIL: schema_version must be 1")

    def test_stages_out_of_order_are_refused(self) -> None:
        """Publishing before hardening is the order the lifecycle exists to stop."""
        self.edit_json(self.FILE, lambda data: data["stages"].reverse())
        self.assert_fails(self.SCRIPT, "FAIL: stages must be ordered as")

    def test_a_stage_without_artifacts_or_exit_criteria_is_refused(self) -> None:
        def mutate(data: dict) -> None:
            data["stages"][0].pop("required_artifacts")
            data["stages"][0]["exit_criteria"] = []

        self.edit_json(self.FILE, mutate)
        self.assert_fails(
            self.SCRIPT,
            "FAIL: proposal: missing required_artifacts",
            "FAIL: proposal: missing exit_criteria",
        )

    def test_a_dropped_non_negotiable_is_named(self) -> None:
        self.edit_json(
            self.FILE,
            lambda data: data["non_negotiables"].remove("no background transcript capture"),
        )
        self.assert_fails(
            self.SCRIPT, "FAIL: missing non-negotiable: no background transcript capture"
        )
