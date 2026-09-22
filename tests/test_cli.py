# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The command surface: dispatch, JSON output, and the packaged shim."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from .support import CLI, ROOT, load_script, skill_text  # noqa: F401  (used by the cases below)


class CliJsonTests(unittest.TestCase):
    def run_cli(self, *args: str) -> str:
        proc = subprocess.run(
            [sys.executable, str(CLI), *args],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout)
        return proc.stdout

    def test_stats_json_has_full_coverage(self) -> None:
        payload = json.loads(self.run_cli("stats", "--json"))
        count = payload["skills"]
        self.assertEqual(payload["coverage"]["routing"], {"covered": count, "total": count})
        self.assertEqual(payload["coverage"]["behavioral"], {"covered": count, "total": count})

    def test_profiles_json_includes_required_profiles(self) -> None:
        payload = json.loads(self.run_cli("profiles", "--json"))
        self.assertTrue({"minimal", "polyglot", "noyalib", "security", "research"}.issubset(payload))

    def test_providers_json_includes_native_and_exports(self) -> None:
        payload = json.loads(self.run_cli("providers", "--json"))
        self.assertEqual(set(payload["native_agents"]), {"aider", "antigravity", "claude", "codex"})
        self.assertIn("generic", payload["export_targets"])
        self.assertIn("openai", payload["export_targets"])

    def test_show_resolves_a_general_skill(self) -> None:
        self.assertIn(
            "verification-before-completion", self.run_cli("show", "verification-before-completion")
        )

    def test_search_filters_to_matching_skills(self) -> None:
        self.assertIn("systematic-debugging", self.run_cli("search", "debugging"))


class NativeAgentParityTests(unittest.TestCase):
    """providers.json names the native agents; every other surface follows it.

    The installer accepted `antigravity`, the completions offered it, and the
    CLI rejected it: four hand-kept lists, three of them wrong.
    """

    def native(self) -> set[str]:
        data = json.loads((ROOT / "providers.json").read_text(encoding="utf-8"))
        return set(data["native_agents"])

    def test_every_agent_argument_offers_exactly_the_native_agents(self) -> None:
        import argparse

        parser = load_script("agtmls.py").build_parser()
        subparsers = next(
            action for action in parser._subparsers._group_actions  # noqa: SLF001  (argparse exposes no public accessor)
            if isinstance(action, argparse._SubParsersAction)  # noqa: SLF001  (the class is private too)
        )
        offered = {}
        for name, sub in subparsers.choices.items():
            for action in sub._actions:  # noqa: SLF001  (a subparser exposes no action list)
                if action.dest == "agent":
                    offered[name] = set(action.choices)
        self.assertTrue(offered, "no subcommand takes an agent")
        for name, choices in offered.items():
            self.assertEqual(choices, self.native(), f"`{name}` disagrees with providers.json")

    def test_the_installer_script_accepts_every_native_agent(self) -> None:
        text = (ROOT / "scripts" / "setup-workspace.sh").read_text(encoding="utf-8")
        labels = set()
        for line in text.splitlines():
            head = line.strip().split(")", 1)[0]
            if line.strip().endswith(";;") and ")" in line and "*" not in head:
                labels.update(head.split("|"))
        self.assertLessEqual(self.native(), labels)

    def test_agent_paths_come_from_providers_json(self) -> None:
        data = json.loads((ROOT / "providers.json").read_text(encoding="utf-8"))
        module = load_script("agtmls.py")
        for name, item in data["native_agents"].items():
            dot, prompt = module.agent_paths(name)
            self.assertEqual((dot, prompt), (str(Path(item["skills_dir"]).parent), item["prompt_file"]))

    def test_completions_offer_exactly_the_native_agents(self) -> None:
        text = (ROOT / "completions" / "agtmls.bash").read_text(encoding="utf-8")
        offered = set()
        for line in text.splitlines():
            if "claude" in line and "compgen -W" in line:
                offered.update(line.split('"')[1].split())
        self.assertEqual(offered, self.native())


class PackagedCliTests(unittest.TestCase):
    """src/agtmls/cli.py — the uvx entry point."""

    def setUp(self) -> None:
        sys.path.insert(0, str(ROOT / "src"))
        self.addCleanup(lambda: sys.path.remove(str(ROOT / "src")))

    def test_checkout_is_preferred_over_a_bundled_registry(self) -> None:
        from agtmls.cli import registry_root

        root, packaged = registry_root()
        self.assertFalse(packaged)
        self.assertTrue((root / "scripts" / "agtmls.py").exists())

    def test_agtmls_home_override_rejects_a_non_checkout(self) -> None:
        from agtmls.cli import registry_root

        with tempfile.TemporaryDirectory() as tmp:
            os.environ["AGTMLS_HOME"] = tmp
            try:
                with self.assertRaises(SystemExit):
                    registry_root()
            finally:
                del os.environ["AGTMLS_HOME"]

    def test_checkout_only_commands_exclude_consumer_commands(self) -> None:
        from agtmls.cli import _CHECKOUT_ONLY

        self.assertIn("check", _CHECKOUT_ONLY)
        self.assertIn("release-pack", _CHECKOUT_ONLY)
        self.assertNotIn("install", _CHECKOUT_ONLY)
        self.assertNotIn("list", _CHECKOUT_ONLY)

    def test_package_version_matches_the_registry(self) -> None:
        import agtmls

        plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(agtmls.__version__, plugin["version"])


class CliDispatchTests(unittest.TestCase):
    """Every declared subcommand must reach its handler without raising.

    Both dispatch bugs that shipped were invisible to the gate:
    `args.copy` raised AttributeError on doctor/status, and the
    `evidence --command` dest collision overwrote the subcommand name with a
    list so every comparison in main() missed and it fell through to
    `return 2`. validate-cli-surface.py could not see either, because it reads
    add_parser() calls out of the AST and greps the README -- it never calls
    main().

    This drives the real argparse namespace and the real dispatch chain with
    run() stubbed, so nothing is executed and the test stays fast. Falling
    through to `return 2`, or never reaching run(), is the failure.
    """

    # Every subcommand, with arguments sufficient to satisfy its parser.
    # A subcommand added without an entry here fails
    # test_every_declared_subcommand_is_covered, so coverage closes itself.
    INVOCATIONS: dict[str, list[str]] = {
        "agent-card": ["--check"],
        "audit": ["--all"],
        "bench": [],
        "bump-version": ["--check"],
        "check": [],
        "diff": ["--from", "index.json"],
        "docs-site": ["--check"],
        "doctor": [],
        "evidence": ["--skill", "probe", "--command", "make test"],
        "evolve": ["transcript.md", "--skill-name", "probe"],
        "export": ["--provider", "generic"],
        "import-skill": ["source.md"],
        "index": ["--check"],
        "install": ["rust", "claude"],
        "list": [],
        "mcp-resources": ["--check"],
        "next-version": [],
        "plugin-manifests": ["--check"],
        "profiles": [],
        "propose-skill": ["transcript.md", "--skill-name", "probe"],
        "providers": [],
        "provenance": ["--check"],
        "provider-install": ["--provider", "openai", "--target", "."],
        "release-check": [],
        "release-dry-run": [],
        "release-pack": [],
        "sbom": ["--check"],
        "scaffold-skill": ["probe"],
        "search": ["yaml"],
        "show": ["cross-language-port"],
        "stats": [],
        "status": [],
        "uninstall": ["claude"],
        "verify": ["claude"],
        "verify-release-assets": ["--tag", "v0.0.1"],
    }

    # Handlers that answer from index.json in-process instead of shelling out.
    LOCAL_HANDLERS = {
        "list", "search", "show", "stats", "profiles", "providers", "uninstall",
        "verify",
    }

    def setUp(self) -> None:
        self.module = load_script("agtmls.py")
        self.calls: list[list[str]] = []
        self.module.run = lambda argv, cwd=None: self.calls.append(list(argv)) or 0
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self._argv = sys.argv
        self.addCleanup(lambda: setattr(sys, "argv", self._argv))

    def dispatch(self, name: str, extra: list[str]) -> int:
        # --target is where a subcommand would write; keep it in a tmpdir.
        argv = ["agtmls", name, *extra]
        if name in {"install", "uninstall", "doctor", "status", "verify"}:
            argv += ["--target", self.tmp.name]
        sys.argv = argv
        self.calls.clear()
        return self.module.main()

    def optional_flags(self, name: str) -> list:
        """Every optional flag a subcommand declares, with a usable value.

        Derived from the parser so a new flag is exercised the day it is
        added. Each is dispatched on its own rather than all at once: some
        pairs are mutually exclusive, and one flag per dispatch reaches the
        same branches without having to know which.
        """
        import argparse

        parser = load_script("agtmls.py").build_parser()
        subparsers = next(
            action for action in parser._subparsers._group_actions  # noqa: SLF001  (argparse exposes no public accessor)
            if isinstance(action, argparse._SubParsersAction)  # noqa: SLF001  (the class is private too)
        )
        out = []
        for action in subparsers.choices[name]._actions:  # noqa: SLF001  (a subparser exposes no action list)
            if not action.option_strings or action.dest == "help":
                continue
            flag = action.option_strings[-1]
            if action.nargs == 0:
                out.append([flag])
            elif action.choices:
                out.append([flag, str(sorted(action.choices)[0])])
            elif "dir" in action.dest or "target" in action.dest:
                out.append([flag, self.tmp.name])
            else:
                out.append([flag, "probe"])
        return out

    def test_every_optional_flag_reaches_a_dispatch_branch(self) -> None:
        """The forwarding branches are `if args.x:` -- minimal args skip them all.

        Dispatching each subcommand with only its required arguments left
        roughly a third of this file unexecuted: every `--out-dir`,
        `--profile` and `--provider` forward was untested, so a dispatcher
        that silently dropped a flag would have looked fine.
        """
        exercised = 0
        for name, required in sorted(self.INVOCATIONS.items()):
            for flag in self.optional_flags(name):
                with self.subTest(subcommand=name, flag=flag[0]):
                    try:
                        code = self.dispatch(name, [*required, *flag])
                    except SystemExit:
                        continue  # mutually exclusive with a required argument
                    self.assertNotEqual(
                        code, 2, f"{name} {flag[0]} fell through every dispatch branch"
                    )
                    exercised += 1
        self.assertGreater(exercised, 30, f"only {exercised} flag dispatches ran")

    def test_a_forwarded_flag_actually_reaches_the_command_line(self) -> None:
        """A dispatcher that accepts a flag and drops it is worse than one that refuses it."""
        self.dispatch("export", ["--provider", "generic", "--out-dir", self.tmp.name])
        forwarded = " ".join(self.calls[0])
        self.assertIn("--out-dir", forwarded)
        self.assertIn(self.tmp.name, forwarded)

    def test_every_declared_subcommand_is_covered(self) -> None:
        declared = load_script("validate-cli-surface.py").subcommands()
        self.assertEqual(
            declared - set(self.INVOCATIONS),
            set(),
            "subcommand declared but never dispatched in a test",
        )
        self.assertEqual(
            set(self.INVOCATIONS) - declared,
            set(),
            "test dispatches a subcommand the CLI no longer declares",
        )

    def test_no_subcommand_raises_or_falls_through(self) -> None:
        for name, extra in sorted(self.INVOCATIONS.items()):
            with self.subTest(subcommand=name):
                try:
                    rc = self.dispatch(name, extra)
                except SystemExit as exc:  # argparse rejected our arguments
                    self.fail(f"{name}: parser rejected its own invocation: {exc}")
                self.assertNotEqual(rc, 2, f"{name} fell through every dispatch branch")
                if name not in self.LOCAL_HANDLERS:
                    self.assertTrue(self.calls, f"{name} never reached run()")

    @staticmethod
    def declared_flags(script: str) -> set[str]:
        """Option strings a script's argparse actually accepts."""
        tree = ast.parse((ROOT / "scripts" / script).read_text(encoding="utf-8"))
        flags: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "add_argument":
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and str(arg.value).startswith("-"):
                        flags.add(arg.value)
        return flags

    def test_forwarded_flags_are_accepted_by_the_target_script(self) -> None:
        """A dispatcher may only forward flags the receiving script declares.

        `doctor`/`status` forwarded --copy, which agtmls-doctor.py has never
        declared -- so even past the AttributeError it would have died in the
        child's argparse.
        """
        accepted = self.declared_flags("agtmls-doctor.py")
        for name in ("doctor", "status"):
            with self.subTest(subcommand=name):
                self.dispatch(name, [])
                forwarded = {a for a in self.calls[0] if a.startswith("--")}
                self.assertEqual(
                    forwarded - accepted,
                    set(),
                    f"{name} forwards flags agtmls-doctor.py does not accept",
                )

    def test_evidence_forwards_its_repeatable_command_flag(self) -> None:
        """The dest collision made --command unreachable; prove it arrives."""
        self.dispatch("evidence", ["--skill", "probe", "--command", "make test"])
        forwarded = self.calls[0]
        self.assertIn("--skill", forwarded)
        self.assertIn("make test", forwarded)


def main() -> int:
    # Discovery, not a hand-maintained tuple: a TestCase added without being
    # registered would otherwise never run, and a gate that silently skips
    # tests is the failure mode this whole suite exists to prevent.
    loader = unittest.defaultTestLoader
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        return 1
    print(f"OK: {result.testsRun} unit test(s) passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
