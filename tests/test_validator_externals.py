# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Validators that answer to something outside the registry's data.

The CLI surface is checked against the parser's source; spec conformance
against the agentskills reference implementation; the SBOM against the wheel
it describes and, when installed, spdx-tools. Each was left out of the
tree-only sweep for that reason, and each was therefore never seen to fail.

The external tools are replaced here with recorders. Whether skills-ref or
spdx-tools is right is their project's problem; whether this repository
listens when they object is this one's, and a validator that ignored their
exit code would print OK forever.
"""

from __future__ import annotations

import subprocess
import sys
from unittest import mock

from .support import run_main
from .test_validator_slices import SliceFixture


class CliSurfaceValidatorTests(SliceFixture):
    """A subcommand nobody documented is one nobody finds.

    The check reads the parser's source rather than importing it, so the
    fixture needs only that file and the three documents it is compared with.
    """

    SCRIPT = "validate-cli-surface.py"
    PATHS = ("scripts/_lib/cli_parser.py", "README.md", "docs/cli.md", "commands/agtmls.md")
    PARSER = "scripts/_lib/cli_parser.py"

    def test_the_shipped_surface_passes(self) -> None:
        self.assertIn("OK: CLI surface valid with 34 subcommand(s)", self.assert_clean())

    def test_a_subcommand_the_parser_no_longer_declares_is_caught(self) -> None:
        """Dropping `check` from the parser would break every script calling it."""
        self.replace(self.PARSER, 'sub.add_parser("check")', 'sub.add_parser("chekc")')
        output = self.assert_catches("CLI subcommands mismatch", count=1)
        self.assertIn("'chekc'", output)

    def test_only_literal_add_parser_names_are_read(self) -> None:
        """A computed name cannot be checked, so it must not be guessed at."""
        module = self.module()
        self.overwrite(
            self.PARSER,
            "sub.add_parser('literal')\n"
            "sub.add_parser(name)\n"
            "sub.add_parser()\n"
            "sub.add_argument('not-a-parser')\n"
            "add_parser('bare-call')\n",
        )
        self.assertEqual(module.subcommands(), {"literal"})

    def test_a_missing_command_reference_is_caught(self) -> None:
        self.remove("docs/cli.md")
        self.assert_catches("docs/cli.md is missing; the CLI surface must stay documented")

    def test_an_undocumented_subcommand_is_caught(self) -> None:
        for document in ("README.md", "docs/cli.md"):
            text = (self.fixture / document).read_text(encoding="utf-8")
            self.overwrite(document, text.replace("agtmls.py bench", "agtmls.py b-e-n-c-h"))
        self.assert_catches("README/docs/cli.md missing agtmls.py bench example or mention", count=1)

    def test_a_slash_command_that_does_not_run_status_is_caught(self) -> None:
        """`/agtmls` in Claude Code is this file; without status it does nothing useful."""
        text = (self.fixture / "commands/agtmls.md").read_text(encoding="utf-8")
        self.overwrite("commands/agtmls.md", text.replace("agtmls.py status", "agtmls.py"))
        self.assert_catches("commands/agtmls.md must invoke agtmls.py status", count=1)

    def test_a_missing_list_commands_example_is_caught(self) -> None:
        for document in ("README.md", "docs/cli.md"):
            text = (self.fixture / document).read_text(encoding="utf-8")
            self.overwrite(document, text.replace("agtmls.py list commands", "agtmls.py list skills"))
        self.assert_catches("README missing agtmls.py list commands example", count=1)


class SpecConformanceRunnerTests(SliceFixture):
    """skills-ref decides; this script must ask it about every skill and listen.

    Two stand-in skills are enough: the reference validator is replaced, so
    their content is never read, only their directories enumerated.
    """

    SCRIPT = "validate-spec-conformance.py"
    CMD = ("/opt/bin/agentskills",)

    @classmethod
    def populate(cls) -> None:
        for name in ("alpha", "beta"):
            skill = cls.fixture / "skills" / name
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(f"---\nname: {name}\n---\n", encoding="utf-8")
        # A directory without SKILL.md is not a skill and must not be sent.
        (cls.fixture / "skills" / "not-a-skill").mkdir()

    def drive(self, rejected: dict[str, str] | None = None) -> tuple[int, str, list]:
        rejected = rejected or {}
        calls: list = []

        def fake_reference(argv, **kwargs):
            calls.append((argv, kwargs))
            name = argv[-1].rsplit("/", 1)[-1]
            if name in rejected:
                return subprocess.CompletedProcess(argv, 1, stdout=rejected[name], stderr="warning: x\n")
            return subprocess.CompletedProcess(argv, 0, stdout="Valid skill\n", stderr="")

        module = self.module()
        with mock.patch.object(module, "runner", return_value=self.CMD), \
                mock.patch.object(module.subprocess, "run", side_effect=fake_reference):
            code, output = run_main(module)
        return code, output, calls

    def test_every_skill_is_submitted_and_a_clean_run_passes(self) -> None:
        code, output, calls = self.drive()
        self.assertEqual(code, 0, output)
        self.assertIn("OK: 2 skill(s) valid per skills-ref", output)
        self.assertEqual(
            [argv for argv, _ in calls],
            [[*self.CMD, "validate", str(self.fixture / "skills" / name)] for name in ("alpha", "beta")],
        )
        self.assertEqual(calls[0][1]["cwd"], self.fixture)

    def test_a_skill_the_reference_rejects_fails_with_its_reasons(self) -> None:
        """The reference's own words are the diagnosis; dropping them hides it."""
        code, output, _ = self.drive({"beta": "name: must be lowercase\n"})
        self.assertEqual(code, 1, output)
        self.assertIn("FAIL: skills/beta\n    name: must be lowercase\n    warning: x", output)
        self.assertNotIn("FAIL: skills/alpha", output)
        self.assertIn("FAIL: 1 skill(s) rejected by the reference implementation", output)

    def test_an_empty_registry_is_a_failure_not_a_pass(self) -> None:
        """Zero skills validated is not zero skills invalid."""
        module = self.module()
        module.SKILLS_DIR = self.fixture / "nowhere"
        with mock.patch.object(module, "runner", return_value=self.CMD):
            code, output = run_main(module)
        self.assertEqual(code, 1, output)
        self.assertIn("FAIL: no skills found under", output)

    def test_the_installed_cli_is_preferred(self) -> None:
        module = self.module()
        with mock.patch.object(module.shutil, "which", return_value="/opt/bin/agentskills"), \
                mock.patch.object(module.subprocess, "run") as probe:
            self.assertEqual(module.runner(), ["/opt/bin/agentskills"])
        probe.assert_not_called()

    def test_an_importable_module_is_used_when_there_is_no_cli(self) -> None:
        """pip may install the package without putting its script on PATH."""
        module = self.module()
        with mock.patch.object(module.shutil, "which", return_value=None), \
                mock.patch.object(module.subprocess, "run",
                                  return_value=subprocess.CompletedProcess([], 0)) as probe:
            self.assertEqual(module.runner(), [sys.executable, "-m", "skills_ref.cli"])
        self.assertEqual(probe.call_args.args[0], [sys.executable, "-c", "import skills_ref"])

    def test_neither_means_not_available(self) -> None:
        module = self.module()
        with mock.patch.object(module.shutil, "which", return_value=None), \
                mock.patch.object(module.subprocess, "run",
                                  return_value=subprocess.CompletedProcess([], 1)):
            self.assertIsNone(module.runner())


class SbomValidatorTests(SliceFixture):
    """A bill of materials that no tool accepts, or that describes a different
    artifact from the one shipped, is paperwork rather than provenance.

    spdx-tools is replaced in every case, reporting itself absent unless a
    test says otherwise, so the structural checks run the same everywhere.
    """

    SCRIPT = "validate-sbom-conformance.py"
    PATHS = ("SBOM.spdx.json", "SBOM.cyclonedx.json", "pyproject.toml")
    SPDX = "SBOM.spdx.json"
    ABSENT = subprocess.CompletedProcess([], 1, stdout="No module named spdx_tools\n")

    def run_validator(self, *args: str, spdx_tools=ABSENT) -> tuple[int, str]:
        module = self.module()
        kwargs = {"side_effect": spdx_tools} if isinstance(spdx_tools, BaseException) \
            else {"return_value": spdx_tools}
        with mock.patch.object(module.subprocess, "run", **kwargs) as tool:
            result = run_main(module, *args)
        self.tool = tool
        return result

    def spdx(self, mutate) -> None:
        self.edit_json(self.SPDX, mutate)

    def test_the_shipped_sbom_conforms(self) -> None:
        output = self.assert_clean()
        self.assertIn("skipped (spdx-tools not installed)", output)

    def test_spdx_tools_is_asked_about_the_document(self) -> None:
        self.run_validator()
        argv = self.tool.call_args.args[0]
        self.assertEqual(argv[-2:], ["-i", str(self.fixture / self.SPDX)])
        self.assertIn("spdx_tools.spdx.clitools.pyspdxtools", argv)

    def test_an_accepting_upstream_validator_is_reported(self) -> None:
        code, output = self.run_validator(
            spdx_tools=subprocess.CompletedProcess([], 0, stdout="The document is valid.\n")
        )
        self.assertEqual(code, 0, output)
        self.assertIn("spdx-tools: valid", output)

    def test_an_upstream_rejection_fails(self) -> None:
        code, output = self.run_validator(
            spdx_tools=subprocess.CompletedProcess([], 1, stdout="SPDXID is malformed\n")
        )
        self.assertEqual(code, 1, output)
        self.assertIn("spdx-tools rejected the document:\nSPDXID is malformed", output)

    def test_an_upstream_complaint_fails_even_with_exit_zero(self) -> None:
        """pyspdxtools reports some violations on stdout and still exits 0."""
        code, output = self.run_validator(
            spdx_tools=subprocess.CompletedProcess([], 0, stdout="creators must be a list\n")
        )
        self.assertEqual(code, 1, output)
        self.assertIn("spdx-tools rejected the document", output)

    def test_an_interpreter_that_cannot_start_skips_the_upstream_check(self) -> None:
        code, output = self.run_validator(spdx_tools=OSError("exec format error"))
        self.assertEqual(code, 0, output)
        self.assertIn("skipped (spdx-tools not installed)", output)

    def test_a_missing_document_is_caught(self) -> None:
        self.remove(self.SPDX)
        code, output = self.run_validator()
        self.assertEqual(code, 1, output)
        self.assertIn("FAIL: SBOM.spdx.json is missing", output)

    def test_each_mandatory_field_is_required(self) -> None:
        for field in ("spdxVersion", "SPDXID", "creationInfo", "name", "documentNamespace", "dataLicense"):
            with self.subTest(field=field):
                self.spdx(lambda data, field=field: data.pop(field))
                self.assert_catches(f"SBOM.spdx.json: missing mandatory field {field!r}")
                self.doCleanups()

    def test_a_document_without_a_creation_date_is_caught(self) -> None:
        self.spdx(lambda data: data["creationInfo"].pop("created"))
        self.assert_catches("creationInfo.created is required", count=1)

    def test_the_epoch_placeholder_date_is_caught(self) -> None:
        """A reproducible build's zero timestamp is not the date it was made."""
        self.spdx(lambda data: data["creationInfo"].__setitem__("created", "1970-01-01T00:00:00Z"))
        self.assert_catches("creationInfo.created is the epoch placeholder", count=1)

    def test_a_document_without_creators_is_caught(self) -> None:
        self.spdx(lambda data: data["creationInfo"].__setitem__("creators", []))
        self.assert_catches("creationInfo.creators is required", count=1)

    def test_a_placeholder_namespace_is_caught(self) -> None:
        self.spdx(lambda data: data.__setitem__("documentNamespace", "https://example.invalid/agtmls"))
        self.assert_catches("documentNamespace is still a placeholder", count=1)

    def test_a_document_describing_no_package_is_caught(self) -> None:
        self.spdx(lambda data: data.__setitem__("packages", []))
        self.assert_catches("no packages section, so it describes no artifact", count=1)

    def test_a_document_with_no_relationships_is_caught(self) -> None:
        self.spdx(lambda data: data.pop("relationships"))
        self.assert_catches("no relationships, so nothing is DESCRIBES-linked", count=1)

    def test_a_file_without_an_identifier_is_reported_once(self) -> None:
        """One complaint, not one per file: a systematic fault is one fault."""
        def strip(data) -> None:
            for entry in data["files"][:3]:
                entry.pop("SPDXID")
            self.first = data["files"][0]["fileName"]
        self.spdx(strip)
        self.assert_catches(f"file {self.first} has no SPDXID", count=1)

    def test_a_file_without_a_sha1_checksum_is_caught(self) -> None:
        """SPDX 2.3 makes SHA1 mandatory for files; SHA256 alone is invalid."""
        def strip(data) -> None:
            entry = data["files"][0]
            entry["checksums"] = [c for c in entry["checksums"] if c["algorithm"] != "SHA1"]
            self.first = entry["fileName"]
        self.spdx(strip)
        self.assert_catches(f"file {self.first} lacks the mandatory SHA1 checksum", count=1)

    def test_a_shipped_directory_the_sbom_omits_is_named(self) -> None:
        self.spdx(lambda data: data.__setitem__(
            "files", [f for f in data["files"] if not f["fileName"].startswith("./skills/")]
        ))
        self.assert_catches("SBOM.spdx.json omits shipped wheel paths: skills", count=1)

    def test_a_missing_cyclonedx_document_is_caught(self) -> None:
        self.remove("SBOM.cyclonedx.json")
        self.assert_catches("SBOM.cyclonedx.json is missing", count=1)

    def test_a_cyclonedx_file_in_another_format_is_caught(self) -> None:
        self.edit_json("SBOM.cyclonedx.json", lambda data: data.__setitem__("bomFormat", "SPDX"))
        self.assert_catches("SBOM.cyclonedx.json is not a CycloneDX document", count=1)

    def test_a_cyclonedx_file_without_a_spec_version_is_caught(self) -> None:
        self.edit_json("SBOM.cyclonedx.json", lambda data: data.pop("specVersion"))
        self.assert_catches("SBOM.cyclonedx.json is not a CycloneDX document", count=1)


class WheelPathTests(SliceFixture):
    """What counts as shipped is read from pyproject, so its parsing must be right."""

    SCRIPT = "validate-sbom-conformance.py"

    def paths(self, pyproject: str) -> set[str]:
        self.overwrite("pyproject.toml", pyproject)
        return self.module().wheel_paths()

    def test_a_pyproject_without_the_table_ships_nothing(self) -> None:
        self.assertEqual(self.paths("[project]\nname = \"agtmls\"\n"), set())

    def test_the_table_is_read_to_its_end_when_it_is_the_last_section(self) -> None:
        """Comments, blanks and dot-paths are skipped; nested paths collapse to their root."""
        table = (
            "[tool.hatch.build.targets.wheel.force-include]\n"
            "# the registry\n"
            "\n"
            '"skills/nested" = "agtmls/_registry/skills/nested"\n'
            '".claude-plugin/plugin.json" = "agtmls/_registry/.claude-plugin/plugin.json"\n'
            '"index.json" = "agtmls/_registry/index.json"\n'
        )
        self.assertEqual(self.paths(table), {"skills", "index.json"})

    def test_the_next_section_ends_the_table(self) -> None:
        table = (
            "[tool.hatch.build.targets.wheel.force-include]\n"
            '"skills" = "agtmls/_registry/skills"\n'
            "[tool.hatch.build.targets.sdist]\n"
            '"scripts" = "elsewhere"\n'
        )
        self.assertEqual(self.paths(table), {"skills"})

