# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The CLI's in-process handlers: install, verify, uninstall and the queries.

CliDispatchTests proves every subcommand reaches a handler. It cannot prove
the handlers that answer in-process do the right thing, because it stubs the
one call that matters and never looks at what landed. These drive the real
code against a cut-down registry and inspect the target afterwards: the
lockfile an install writes, the exit code a tampered tree earns, and which
links an uninstall is and is not allowed to remove.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from .mini_registry import GENERAL, SKILLS, mini_registry, replace_file
from .support import load_script, retarget, run_main

EXIT_INTEGRITY_FAILURE = 3


_WORKSPACE: str = ""
FIXTURE = Path()


def setUpModule() -> None:
    # One registry for the module: every test that edits it restores it.
    global _WORKSPACE, FIXTURE
    _WORKSPACE = tempfile.mkdtemp(prefix="agtmls-cli-")
    FIXTURE = mini_registry(Path(_WORKSPACE) / "tree")


def tearDownModule() -> None:
    shutil.rmtree(_WORKSPACE, ignore_errors=True)


def capture(function, *args) -> tuple[int, str]:
    """Call one handler directly, the way main() would, and keep what it said."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        code = function(*args)
    return code, buffer.getvalue()


class CliFixture(unittest.TestCase):
    """Loads agtmls.py once per class; main() is only driven where it holds logic.

    Building the argparse tree costs ~17 ms, so handlers whose dispatch line
    CliDispatchTests already covers are called directly.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = FIXTURE
        cls.cli = load_script("agtmls.py")
        retarget(cls.cli, cls.fixture)
        # In a dict: a function stored as a class attribute would come back
        # bound to the test case.
        cls.originals = {"run": cls.cli.run, "load_index": cls.cli.load_index}

    def setUp(self) -> None:
        # Undo whatever the previous test stubbed.
        for name, function in self.originals.items():
            setattr(self.cli, name, function)
        self.target = Path(tempfile.mkdtemp(prefix="agtmls-target-")).resolve()
        self.addCleanup(lambda: shutil.rmtree(self.target, ignore_errors=True))
        self.calls: list[list[str]] = []

    def index(self) -> dict:
        return json.loads((self.fixture / "index.json").read_text(encoding="utf-8"))


class InstallLifecycleTests(CliFixture):
    """install -> verify -> uninstall, with the shell installer stood in for.

    setup-workspace.sh costs a second per run and is driven end to end by the
    smoke scripts. What it does not cover is the Python around it: the
    integrity check that must refuse *before* anything is copied, and the
    lockfile written *after*, which is the only thing `verify` can check
    against. The stand-in materialises the general skills (plus any requested
    bundle) the way the real installer does, so everything downstream of
    run() is the shipped code.
    """

    def fake_installer(self, argv: list[str], cwd: Path | None = None) -> int:
        self.calls.append(list(argv))
        agent = argv[2]
        bundles = {argv[i + 1] for i, arg in enumerate(argv) if arg == "--bundle"}
        skills = Path(cwd) / f".{agent}" / "skills"
        skills.mkdir(parents=True, exist_ok=True)
        for skill in self.index()["skills"]:
            if skill["bundle"] is None or skill["bundle"] in bundles:
                source = self.fixture / skill["path"]
                if "--copy" in argv:
                    shutil.copytree(source, skills / skill["name"])
                else:
                    (skills / skill["name"]).symlink_to(source)
        return 0

    def install(self, *extra: str) -> tuple[int, str]:
        self.cli.run = self.fake_installer
        return run_main(self.cli, "install", "rust", "claude", "--target", str(self.target), *extra)

    def lock(self) -> dict:
        return json.loads((self.target / ".agtmls" / "manifest.json").read_text(encoding="utf-8"))

    def test_an_install_records_what_landed_with_the_published_digests(self) -> None:
        """A lockfile that disagreed with index.json would make verify meaningless."""
        code, output = self.install("--copy")
        self.assertEqual(code, 0, output)
        self.assertIn(f"recorded {len(GENERAL)} skill(s) in .agtmls/manifest.json", output)
        lock = self.lock()
        self.assertEqual(lock["mode"], "copy")
        self.assertEqual(lock["source"]["registry_version"], self.index()["registry_version"])
        published = {s["name"]: s["integrity"] for s in self.index()["skills"]}
        self.assertEqual(sorted(e["name"] for e in lock["skills"]), sorted(GENERAL))
        for entry in lock["skills"]:
            self.assertEqual(entry["integrity"], published[entry["name"]], entry["name"])

    def test_a_symlink_install_is_recorded_as_one(self) -> None:
        code, output = self.install()
        self.assertEqual(code, 0, output)
        self.assertEqual(self.lock()["mode"], "symlink")

    def test_a_profile_forwards_its_bundles_once_each(self) -> None:
        """--bundle noyalib plus --profile noyalib must not install noyalib twice."""
        code, output = self.install("--profile", "noyalib", "--bundle", "noyalib", "--copy")
        self.assertEqual(code, 0, output)
        self.assertEqual(self.calls[0].count("noyalib"), 1, self.calls[0])
        self.assertIn("noyalib-config-and-flags", [e["name"] for e in self.lock()["skills"]])

    def test_an_unknown_profile_is_refused_before_anything_runs(self) -> None:
        code, output = self.install("--profile", "no-such-profile")
        self.assertEqual(code, 1)
        self.assertIn("unknown profile: no-such-profile", output)
        self.assertEqual(self.calls, [])

    def test_every_install_flag_reaches_the_installer(self) -> None:
        self.install("--skills-only", "--copy", "--force")
        for flag in ("--skills-only", "--copy", "--force"):
            self.assertIn(flag, self.calls[0])

    def test_a_tampered_registry_is_refused_with_the_integrity_exit_code(self) -> None:
        """Copying a modified skill into a consumer and reporting it later is not a control."""
        skill = self.fixture / "skills" / "using-agtmls" / "SKILL.md"
        replace_file(self, skill, skill.read_text(encoding="utf-8") + "\ninjected\n")
        code, output = self.install("--copy")
        self.assertEqual(code, EXIT_INTEGRITY_FAILURE, output)
        self.assertIn("refusing to install: 1 skill(s) do not match index.json", output)
        self.assertIn("using-agtmls", output)
        self.assertIn("on disk  sha256:", output)
        self.assertEqual(self.calls, [], "the installer ran despite the drift")
        self.assertFalse((self.target / ".claude").exists())

    def test_a_skill_missing_from_disk_is_drift_too(self) -> None:
        source = self.fixture / "skills" / "systematic-debugging"
        parked = self.fixture / "parked-systematic-debugging"
        source.rename(parked)
        self.addCleanup(parked.rename, source)
        code, output = self.install()
        self.assertEqual(code, EXIT_INTEGRITY_FAILURE, output)
        self.assertIn("on disk  <missing>", output)

    def test_no_verify_and_dry_run_skip_the_integrity_check(self) -> None:
        skill = self.fixture / "skills" / "using-agtmls" / "SKILL.md"
        replace_file(self, skill, skill.read_text(encoding="utf-8") + "\nlocal edit\n")
        code, output = self.install("--no-verify")
        self.assertEqual(code, 0, output)
        self.assertEqual(len(self.calls), 1)

        self.calls.clear()
        shutil.rmtree(self.target / ".claude")
        (self.target / ".agtmls" / "manifest.json").unlink()
        code, output = self.install("--dry-run")
        self.assertEqual(code, 0, output)
        self.assertIn("--dry-run", self.calls[0])
        self.assertFalse((self.target / ".agtmls" / "manifest.json").exists(),
                         "a dry run wrote a lockfile")

    def test_an_index_entry_without_a_digest_is_refused(self) -> None:
        """An entry with no `integrity` used to be skipped, so stripping a
        skill's digest from index.json let any content through the check.
        A skill with nothing to verify against is unverified, not clean."""
        index = self.index()
        for skill in index["skills"]:
            if skill["name"] == "using-agtmls":
                del skill["integrity"]
        replace_file(self, self.fixture / "index.json", json.dumps(index))
        skill_md = self.fixture / "skills" / "using-agtmls" / "SKILL.md"
        replace_file(self, skill_md, skill_md.read_text(encoding="utf-8") + "\nedit\n")
        self.assertEqual(self.cli.verify_registry()[0][:2], ("using-agtmls", "<no digest>"))

    def test_a_failed_installer_writes_no_lockfile(self) -> None:
        self.cli.run = lambda argv, cwd=None: 5
        code, _ = run_main(self.cli, "install", "rust", "claude", "--target", str(self.target))
        self.assertEqual(code, 5)
        self.assertFalse((self.target / ".agtmls").exists())

    def test_an_installer_that_installed_nothing_records_nothing(self) -> None:
        self.cli.run = lambda argv, cwd=None: 0
        code, output = run_main(self.cli, "install", "rust", "claude", "--target", str(self.target))
        self.assertEqual(code, 0, output)
        self.assertEqual(self.lock()["skills"], [])

    def verify(self, json_output: bool = False) -> tuple[int, str]:
        return capture(self.cli.verify_install, self.target, "claude", json_output)

    def test_verify_accepts_an_untouched_install(self) -> None:
        self.install("--copy")
        code, output = self.verify()
        self.assertEqual(code, 0, output)
        self.assertIn(f"OK: {len(GENERAL)} skill(s) match the lockfile", output)

    def test_verify_fails_a_modified_install_with_exit_3(self) -> None:
        self.install("--copy")
        installed = self.target / ".claude" / "skills" / "using-agtmls" / "SKILL.md"
        installed.write_text("tampered\n", encoding="utf-8")
        code, output = self.verify()
        self.assertEqual(code, EXIT_INTEGRITY_FAILURE, output)
        self.assertIn("MODIFIED", output)
        self.assertIn("using-agtmls", output)
        self.assertIn("FAIL: 1 integrity problem(s)", output)

    def test_verify_json_names_each_problem(self) -> None:
        self.install("--copy")
        shutil.rmtree(self.target / ".claude" / "skills" / "systematic-debugging")
        code, output = self.verify(json_output=True)
        self.assertEqual(code, EXIT_INTEGRITY_FAILURE, output)
        payload = json.loads(output)
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["target"], str(self.target))
        self.assertEqual(
            payload["problems"],
            [{"skill": "systematic-debugging", "status": "missing",
              "detail": "recorded in the lockfile but not installed"}],
        )

    def test_an_unmanaged_skill_is_reported_but_is_not_a_failure(self) -> None:
        """A hand-added skill is the user's business; it is not tampering."""
        self.install("--copy")
        (self.target / ".claude" / "skills" / "my-own-skill").mkdir()
        code, output = self.verify()
        self.assertEqual(code, 0, output)
        self.assertIn("UNMANAGED", output)
        self.assertIn("my-own-skill", output)

    def test_verify_without_a_lockfile_is_an_integrity_failure(self) -> None:
        code, output = self.verify()
        self.assertEqual(code, EXIT_INTEGRITY_FAILURE, output)
        self.assertIn("NO-LOCKFILE", output)


class UninstallTests(CliFixture):
    """uninstall may only remove what this registry put there."""

    def setUp(self) -> None:
        super().setUp()
        self.skills = self.target / ".claude" / "skills"
        self.skills.mkdir(parents=True)
        (self.target / ".claude" / "commands").mkdir()

    def uninstall(self, remove_prompt: bool = False) -> tuple[int, str]:
        return capture(self.cli.uninstall, self.target, "claude", remove_prompt)

    def record(self, names, mode: str) -> Path:
        payload = self.cli.lockfile.build(self.target, self.fixture, list(names), mode, "0.0.0")
        return self.cli.lockfile.write(self.target, payload)

    def test_copied_skills_recorded_in_the_lockfile_are_removed(self) -> None:
        """`uvx agtmls install` copies (the wheel's cache is ephemeral), and
        v0.0.7's uninstall, which knew only symlinks, then removed 0 items."""
        for name in GENERAL:
            shutil.copytree(self.fixture / "skills" / name, self.skills / name)
        hand = self.skills / "hand-written"
        hand.mkdir()
        (hand / "SKILL.md").write_text("mine\n", encoding="utf-8")
        commands = self.target / ".claude" / "commands"
        ours = commands / "agtmls-audit.md"
        shutil.copy2(self.fixture / "commands" / "agtmls-audit.md", ours)
        theirs = commands / "mine.md"
        theirs.write_text("# mine\n", encoding="utf-8")
        lock = self.record(GENERAL, "copy")

        code, output = self.uninstall()
        self.assertEqual(code, 0, output)
        for name in GENERAL:
            self.assertFalse((self.skills / name).exists(), f"{name} survived")
        self.assertFalse(ours.exists(), "a copied registry command survived")
        self.assertTrue(hand.is_dir(), "a hand-written skill was removed")
        self.assertTrue(theirs.exists(), "the user's own command was removed")
        self.assertFalse(lock.exists(), "the lockfile outlived everything it recorded")
        self.assertIn(f"removed {len(GENERAL) + 2} AgtMLS-managed item(s) from {self.target}", output)

    def test_a_copied_skill_edited_since_install_is_left_in_place(self) -> None:
        """verify reports a local edit rather than repairing it; uninstall must
        not delete it either. The lockfile stays, since it still describes a
        skill that is there."""
        name = GENERAL[0]
        shutil.copytree(self.fixture / "skills" / name, self.skills / name)
        (self.skills / name / "SKILL.md").write_text("edited\n", encoding="utf-8")
        lock = self.record([name], "copy")
        code, output = self.uninstall()
        self.assertEqual(code, 0, output)
        self.assertTrue((self.skills / name).is_dir(), "an edited skill was deleted")
        self.assertIn(f"{name}: modified since install; left in place", output)
        self.assertIn("removed 0 AgtMLS-managed item(s)", output)
        self.assertTrue(lock.exists())

    def test_a_recorded_copy_already_gone_is_skipped_and_the_lockfile_dir_is_shared(self) -> None:
        """Nothing to remove for a skill the user deleted by hand; and .agtmls
        may hold files that are not ours, so only the lockfile goes."""
        lock = self.record([GENERAL[0]], "copy")
        theirs = lock.parent / "notes.txt"
        theirs.write_text("keep\n", encoding="utf-8")
        code, output = self.uninstall()
        self.assertEqual(code, 0, output)
        self.assertFalse(lock.exists())
        self.assertTrue(theirs.exists(), "a file beside the lockfile was removed")
        self.assertIn("removed 1 AgtMLS-managed item(s)", output)

    def test_verify_of_a_target_whose_skills_dir_is_gone_reports_them_missing(self) -> None:
        self.record([GENERAL[0]], "copy")
        problems = self.cli.lockfile.verify(self.target, self.target / ".claude" / "gone")
        self.assertEqual([(name, status) for name, status, _ in problems], [(GENERAL[0], "missing")])

    def test_a_symlink_uninstall_drops_the_lockfile_it_leaves_stale(self) -> None:
        name = GENERAL[0]
        (self.skills / name).symlink_to(self.fixture / "skills" / name)
        lock = self.record([name], "symlink")
        code, output = self.uninstall()
        self.assertEqual(code, 0, output)
        self.assertFalse((self.skills / name).is_symlink())
        self.assertFalse(lock.exists(), "a lockfile with nothing left to describe was kept")
        self.assertFalse(lock.parent.exists(), "an empty .agtmls directory was left behind")
        self.assertIn("removed 2 AgtMLS-managed item(s)", output)

    def test_only_links_into_the_registry_are_removed(self) -> None:
        ours = self.skills / "using-agtmls"
        ours.symlink_to(self.fixture / "skills" / "using-agtmls")
        command = self.target / ".claude" / "commands" / "agtmls-audit.md"
        command.symlink_to(self.fixture / "commands" / "agtmls-audit.md")
        elsewhere = Path(tempfile.mkdtemp(prefix="agtmls-elsewhere-"))
        self.addCleanup(lambda: shutil.rmtree(elsewhere, ignore_errors=True))
        foreign = self.skills / "foreign"
        foreign.symlink_to(elsewhere)
        dangling = self.skills / "dangling"
        dangling.symlink_to(self.fixture / "skills" / "no-such-skill")
        real = self.skills / "hand-written"
        real.mkdir()

        code, output = self.uninstall()
        self.assertEqual(code, 0, output)
        self.assertIn(f"removed 2 AgtMLS-managed item(s) from {self.target}", output)
        self.assertFalse(ours.is_symlink())
        self.assertFalse(command.is_symlink())
        for kept in (foreign, dangling, real):
            self.assertTrue(kept.is_symlink() or kept.is_dir(), f"{kept.name} was removed")

    def test_a_sibling_checkout_sharing_our_prefix_is_not_ours(self) -> None:
        """`/x/agtmls-experiments` starts with `/x/agtmls`; that is not containment."""
        sibling = Path(str(self.fixture) + "-experiments")
        (sibling / "skills" / "probe").mkdir(parents=True)
        self.addCleanup(lambda: shutil.rmtree(sibling, ignore_errors=True))
        link = self.skills / "probe"
        link.symlink_to(sibling / "skills" / "probe")
        code, output = self.uninstall()
        self.assertEqual(code, 0, output)
        self.assertTrue(link.is_symlink(), "a link into a sibling checkout was removed")

    def test_a_generated_prompt_is_removed_only_when_asked(self) -> None:
        prompt = self.target / "CLAUDE.md"
        prompt.write_text("<!-- Generated by AgtMLS -->\n# Prompt\n", encoding="utf-8")
        self.uninstall()
        self.assertTrue(prompt.exists(), "the prompt went without --remove-prompt")
        code, output = self.uninstall(remove_prompt=True)
        self.assertEqual(code, 0, output)
        self.assertFalse(prompt.exists())
        self.assertIn("removed 1 AgtMLS-managed item(s)", output)

    def test_a_hand_written_prompt_survives_remove_prompt(self) -> None:
        """The user's own CLAUDE.md is not ours to delete, flag or no flag."""
        prompt = self.target / "CLAUDE.md"
        prompt.write_text("# My own rules\n", encoding="utf-8")
        self.uninstall(remove_prompt=True)
        self.assertEqual(prompt.read_text(encoding="utf-8"), "# My own rules\n")
        empty = self.target / "CLAUDE.md"
        empty.write_text("", encoding="utf-8")
        self.uninstall(remove_prompt=True)
        self.assertTrue(empty.exists(), "an empty prompt file was treated as generated")

    def test_a_target_with_nothing_installed_is_a_no_op(self) -> None:
        shutil.rmtree(self.target / ".claude")
        code, output = self.uninstall()
        self.assertEqual(code, 0, output)
        self.assertIn("removed 0 AgtMLS-managed item(s)", output)


class QueryTests(CliFixture):
    """list, search, show and stats answer from index.json without a subprocess."""

    def query(self, *args: str) -> tuple[int, str]:
        """Parse like the CLI would, then call the handler main() dispatches to."""
        name, rest = args[0], list(args[1:])
        json_output = "--json" in rest
        rest = [arg for arg in rest if arg != "--json"]
        if name == "list":
            bundle = rest[rest.index("--bundle") + 1] if "--bundle" in rest else None
            kind = rest[0] if rest and rest[0] != "--bundle" else "skills"
            return capture(self.cli.list_entries, kind, bundle, json_output)
        handler = {"search": self.cli.search_entries, "show": self.cli.show_entry}.get(name)
        if handler:
            return capture(handler, rest[0], json_output)
        return capture(getattr(self.cli, name), json_output)

    def test_list_filters_by_bundle(self) -> None:
        code, output = self.query("list", "--bundle", "_general")
        self.assertEqual(code, 0, output)
        listed = sorted(line.split()[0] for line in output.splitlines())
        self.assertEqual(listed, sorted(f"general/{name}" for name in GENERAL))
        code, output = self.query("list", "--bundle", "noyalib", "--json")
        self.assertEqual([s["name"] for s in json.loads(output)], ["noyalib-config-and-flags"])

    def test_list_all_skills_names_their_bundle(self) -> None:
        code, output = self.query("list")
        self.assertEqual(code, 0, output)
        self.assertEqual(len(output.splitlines()), len(SKILLS))
        self.assertIn("noyalib/noyalib-config-and-flags  ", output)

    def test_list_commands_in_both_formats(self) -> None:
        commands = self.index()["commands"]
        code, output = self.query("list", "commands")
        self.assertEqual(code, 0, output)
        self.assertEqual(
            output.splitlines(),
            [f"command/{c['name']}  {c['description']}" for c in commands],
        )
        code, output = self.query("list", "commands", "--json")
        self.assertEqual(json.loads(output), commands)

    def test_search_matches_commands_and_requires_every_term(self) -> None:
        code, output = self.query("search", "agtmls-audit")
        self.assertEqual(code, 0, output)
        self.assertTrue(output.startswith("command/agtmls-audit  "), output)
        code, output = self.query("search", "debugging systematic")
        self.assertEqual([line.split()[0] for line in output.splitlines()],
                         ["general/systematic-debugging"])
        code, output = self.query("search", "systematic zzz-no-such-term", "--json")
        self.assertEqual(json.loads(output), [])

    def test_show_a_command_omits_the_fields_it_does_not_have(self) -> None:
        code, output = self.query("show", "agtmls-audit")
        self.assertEqual(code, 0, output)
        self.assertTrue(output.startswith("command: agtmls-audit\npath: commands/agtmls-audit.md\n"))
        self.assertNotIn("bundle:", output)
        self.assertNotIn("tags:", output)

    def test_show_resolves_a_bundle_qualified_name(self) -> None:
        code, output = self.query("show", "noyalib/noyalib-config-and-flags")
        self.assertEqual(code, 0, output)
        self.assertIn("bundle: noyalib", output)
        self.assertIn("tags: config, noyalib", output)
        code, output = self.query("show", "using-agtmls", "--json")
        entry = json.loads(output)
        self.assertEqual((entry["name"], entry["entry_type"]), ("using-agtmls", "skill"))

    def test_show_skips_a_missing_description_rather_than_printing_a_blank(self) -> None:
        index = self.index()
        index["commands"] = [{"name": "bare", "path": "commands/bare.md", "tags": ["x"]}]
        self.cli.load_index = lambda: index
        code, output = self.query("show", "bare")
        self.assertEqual(code, 0, output)
        self.assertEqual(output, "command: bare\npath: commands/bare.md\ntags: x\n")

    def test_show_an_unknown_name_fails(self) -> None:
        code, output = self.query("show", "no-such-skill")
        self.assertEqual(code, 1)
        self.assertIn("no registry entry named 'no-such-skill'", output)

    def test_stats_reports_what_the_index_says(self) -> None:
        code, output = self.query("stats")
        self.assertEqual(code, 0, output)
        self.assertIn(f"skills: {len(SKILLS)}\n", output)
        self.assertIn(f"bundle/general: {len(GENERAL)}\n", output)
        self.assertIn("bundle/noyalib: 1\n", output)
        self.assertIn("quality: 100\n", output)
        routing = self.index()["coverage"]["routing"]
        self.assertIn(f"routing coverage: {routing['covered']}/{routing['total']}\n", output)

    def test_stats_without_quality_data_omits_the_line(self) -> None:
        index = self.index()
        del index["quality"]
        self.cli.load_index = lambda: index
        code, output = self.query("stats")
        self.assertEqual(code, 0, output)
        self.assertNotIn("quality:", output)

    def test_profiles_and_providers_in_text(self) -> None:
        code, output = self.query("profiles")
        self.assertEqual(code, 0, output)
        self.assertIn("minimal  bundles=general  ", output)
        self.assertIn("noyalib  bundles=noyalib  ", output)
        code, output = self.query("providers")
        self.assertIn("native/claude\n", output)
        self.assertIn("export/openai\n", output)


class DispatchEdgeTests(CliFixture):
    """Forwarding branches CliDispatchTests' one-flag-at-a-time sweep never takes."""

    def forwarded(self, *args: str) -> list[str]:
        self.cli.run = lambda argv, cwd=None: self.calls.append(list(argv)) or 0
        code, output = run_main(self.cli, *args)
        self.assertEqual(code, 0, output)
        return self.calls[-1]

    def test_doctor_without_a_target_forwards_no_target(self) -> None:
        argv = self.forwarded("doctor", "--agent", "claude")
        self.assertNotIn("--target", argv)
        self.assertEqual(argv[-2:], ["--agent", "claude"])

    def test_audit_forwards_a_path_without_all(self) -> None:
        argv = self.forwarded("audit", "skills/using-agtmls")
        self.assertEqual(argv[-1], "skills/using-agtmls")
        self.assertNotIn("--all", argv)

    def test_bump_version_without_check_does_not_add_it(self) -> None:
        """--check turns a bump into a dry comparison; adding it unasked would no-op the bump."""
        argv = self.forwarded("bump-version", "--version", "0.0.7", "--date", "2026-09-22")
        self.assertEqual(argv[-4:], ["--version", "0.0.7", "--date", "2026-09-22"])
        self.assertNotIn("--check", argv)

    def test_run_returns_the_child_exit_code_from_the_given_directory(self) -> None:
        """run() is the one line every dispatch trusts; stubbing it everywhere hid it."""
        code = self.cli.run(
            [sys.executable, "-c",
             "import os, sys; open('cwd.txt', 'w').write(os.getcwd()); sys.exit(7)"],
            cwd=self.target,
        )
        self.assertEqual(code, 7)
        self.assertEqual(
            os.path.realpath((self.target / "cwd.txt").read_text(encoding="utf-8")),
            os.path.realpath(self.target),
        )

    def test_an_agent_providers_json_does_not_name_is_an_error(self) -> None:
        with self.assertRaises(ValueError):
            self.cli.agent_paths("no-such-agent")


if __name__ == "__main__":
    unittest.main()


class DispatchFallthroughTests(unittest.TestCase):
    def test_a_subcommand_with_no_handler_exits_2_rather_than_0(self) -> None:
        """argparse only accepts declared subcommands, so reaching the end of
        main() means one was declared without a handler. Falling off the end
        would return None -- exit 0, success -- for a command that did nothing."""
        import argparse
        from unittest import mock

        cli = load_script("agtmls.py")
        parser = mock.Mock()
        parser.parse_args.return_value = argparse.Namespace(subcommand="declared-but-unhandled")
        with mock.patch.object(cli, "build_parser", return_value=parser):
            self.assertEqual(cli.main(), 2)

