# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The library core: digests, lockfiles, and the packaged entry point.

These are the pieces `agtmls verify` is built from, and the ones a consumer's
trust actually rests on. Everything else in this repository validates data;
this decides whether an installed skill is the skill that was published.

The gate exercises most of it through subprocesses, which proves it works and
measures nothing. These are the direct tests, so the error paths -- a missing
lockfile, a tampered skill, a symlink that must not be followed -- are
exercised rather than assumed.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from .support import ROOT

sys.path.insert(0, str(ROOT / "scripts"))

from _lib import covered, digest, lockfile  # noqa: E402  (needs the scripts path first)


class DigestTests(unittest.TestCase):
    """agtmls-spec/spec/03-integrity.md, exercised rather than described."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="agtmls-digest-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))

    def write(self, relative: str, text: str = "x") -> Path:
        path = self.tmp / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_build_debris_is_not_part_of_a_skill(self) -> None:
        """A digest that moved because macOS wrote .DS_Store is a false alarm."""
        self.write("SKILL.md", "# skill\n")
        before = digest.skill_digest(self.tmp)
        self.write(".DS_Store", "junk")
        self.write("__pycache__/mod.cpython-312.pyc", "bytecode")
        self.write("notes.pyc", "bytecode")
        self.write(".agtmls/manifest.json", "{}")
        self.assertEqual(digest.skill_digest(self.tmp), before)

    def test_a_nested_excluded_directory_is_skipped(self) -> None:
        self.write("SKILL.md", "# skill\n")
        before = digest.skill_digest(self.tmp)
        self.write("deep/__pycache__/x.txt", "junk")
        self.assertEqual(digest.skill_digest(self.tmp), before)

    def test_content_changes_move_the_digest(self) -> None:
        self.write("SKILL.md", "# skill\n")
        before = digest.skill_digest(self.tmp)
        self.write("SKILL.md", "# skill, edited\n")
        self.assertNotEqual(digest.skill_digest(self.tmp), before)

    def test_symlinks_are_excluded_and_reported(self) -> None:
        """Following one would make the digest depend on files outside the skill."""
        self.write("SKILL.md", "# skill\n")
        outside = self.tmp.parent / "outside.txt"
        outside.write_text("secret", encoding="utf-8")
        self.addCleanup(outside.unlink)
        link = self.tmp / "link.md"
        link.symlink_to(outside)

        self.assertEqual(digest.symlinks(self.tmp), ["link.md"])
        self.assertNotIn("link.md", [name for name, _ in digest.manifest(self.tmp)])

    def test_the_manifest_sorts_by_bytes_not_locale(self) -> None:
        for name in ("b.md", "A.md", "a.md", "Z.md"):
            self.write(name, name)
        names = [name for name, _ in digest.manifest(self.tmp)]
        self.assertEqual(names, sorted(names, key=lambda n: n.encode("utf-8")))

    def test_the_digest_names_its_algorithm(self) -> None:
        self.write("SKILL.md", "# skill\n")
        value = digest.skill_digest(self.tmp)
        self.assertTrue(value.startswith("sha256:"), value)
        self.assertEqual(len(value.split(":", 1)[1]), 64)

    def test_an_empty_directory_is_not_represented(self) -> None:
        """A directory is its files."""
        self.write("SKILL.md", "# skill\n")
        before = digest.skill_digest(self.tmp)
        (self.tmp / "empty").mkdir()
        self.assertEqual(digest.skill_digest(self.tmp), before)


class LockfileTests(unittest.TestCase):
    """What turns a digest from a number in a file into a control."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="agtmls-lock-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.registry = self.tmp / "registry"
        (self.registry / "skills" / "alpha").mkdir(parents=True)
        (self.registry / "skills" / "alpha" / "SKILL.md").write_text("# alpha\n", encoding="utf-8")
        self.target = self.tmp / "consumer"
        self.skills_dir = self.target / ".claude" / "skills"
        self.skills_dir.mkdir(parents=True)

    def install(self, name: str = "alpha") -> Path:
        source = self.registry / "skills" / name
        destination = self.skills_dir / name
        destination.mkdir(parents=True, exist_ok=True)
        for path in source.rglob("*"):
            if path.is_file():
                (destination / path.relative_to(source)).write_text(
                    path.read_text(encoding="utf-8"), encoding="utf-8"
                )
        return destination

    def lock(self, skills: list[str] | None = None) -> dict:
        payload = lockfile.build(
            self.target, self.registry, skills if skills is not None else ["alpha"],
            "copy", "0.0.1",
        )
        lockfile.write(self.target, payload)
        return payload

    def test_executable_files_are_recorded_separately(self) -> None:
        """The bit does not survive every transport, so it is not in the digest."""
        script = self.registry / "skills" / "alpha" / "run.sh"
        script.write_text("#!/bin/sh\n", encoding="utf-8")
        script.chmod(0o755)
        self.assertEqual(lockfile.executable_files(self.registry / "skills" / "alpha"), ["run.sh"])
        plain = self.registry / "skills" / "alpha" / "SKILL.md"
        self.assertNotIn(plain.name, lockfile.executable_files(plain.parent))

    def test_build_skips_a_skill_that_is_not_there(self) -> None:
        payload = lockfile.build(self.target, self.registry, ["alpha", "ghost"], "copy", "0.0.1")
        self.assertEqual([entry["name"] for entry in payload["skills"]], ["alpha"])
        self.assertEqual(payload["mode"], "copy")
        self.assertEqual(payload["source"]["registry_version"], "0.0.1")
        self.assertEqual(payload["schema_version"], lockfile.SCHEMA_VERSION)

    def test_write_then_read_round_trips(self) -> None:
        payload = self.lock()
        self.assertEqual(lockfile.read(self.target), payload)
        self.assertTrue(lockfile.lockfile_path(self.target).exists())

    def test_reading_where_there_is_none_returns_none(self) -> None:
        self.assertIsNone(lockfile.read(self.target))

    def test_verify_without_a_lockfile_says_so(self) -> None:
        problems = lockfile.verify(self.target, self.skills_dir)
        self.assertEqual([status for _, status, _ in problems], ["no-lockfile"])

    def test_verify_accepts_an_untouched_install(self) -> None:
        self.install()
        self.lock()
        self.assertEqual(lockfile.verify(self.target, self.skills_dir), [])

    def test_verify_reports_a_modified_skill(self) -> None:
        installed = self.install()
        self.lock()
        (installed / "SKILL.md").write_text("# alpha, tampered\n", encoding="utf-8")
        problems = lockfile.verify(self.target, self.skills_dir)
        self.assertEqual([(name, status) for name, status, _ in problems], [("alpha", "modified")])
        self.assertIn("expected sha256:", problems[0][2])

    def test_verify_reports_a_deleted_skill(self) -> None:
        installed = self.install()
        self.lock()
        (installed / "SKILL.md").unlink()
        installed.rmdir()
        problems = lockfile.verify(self.target, self.skills_dir)
        self.assertEqual([(name, status) for name, status, _ in problems], [("alpha", "missing")])

    def test_verify_reports_but_never_removes_an_unmanaged_skill(self) -> None:
        """Deleting something we have no record of installing is not ours to do."""
        self.install()
        self.lock()
        stranger = self.skills_dir / "not-ours"
        stranger.mkdir()
        (stranger / "SKILL.md").write_text("# mine\n", encoding="utf-8")
        problems = lockfile.verify(self.target, self.skills_dir)
        self.assertEqual([(n, s) for n, s, _ in problems], [("not-ours", "unmanaged")])
        self.assertTrue(stranger.exists(), "verify deleted a skill it did not install")

    def test_the_lockfile_is_outside_the_digest_it_records(self) -> None:
        """An install must not change the identity of what it installed."""
        installed = self.install()
        before = digest.skill_digest(installed)
        self.lock()
        self.assertEqual(digest.skill_digest(installed), before)

    def test_exit_codes_are_distinct(self) -> None:
        """0/1/2 conflates worked, broke, and you typed it wrong."""
        codes = [lockfile.EXIT_OK, lockfile.EXIT_ERROR,
                 lockfile.EXIT_USAGE, lockfile.EXIT_INTEGRITY_FAILURE]
        self.assertEqual(len(set(codes)), len(codes))
        self.assertEqual(lockfile.EXIT_INTEGRITY_FAILURE, 3)


class CoveredPathTests(unittest.TestCase):
    """One definition of what the supply-chain artifacts describe."""

    def test_no_generated_artifact_is_in_the_timestamp_basis(self) -> None:
        """Provenance timestamped from its own materials never settles."""
        basis = set(covered.SOURCE_DIRS) | set(covered.SOURCE_FILES)
        for artifact in covered.GENERATED:
            self.assertNotIn(artifact, basis, f"{artifact} is generated and in the basis")

    def test_the_sbom_lists_the_generated_files_the_wheel_ships(self) -> None:
        """Splitting the basis from the SBOM list must not drop shipped files."""
        self.assertLessEqual({"index.json", "CATALOG.md"}, set(covered.SBOM_FILES))
        self.assertLessEqual(set(covered.SOURCE_FILES), set(covered.SBOM_FILES))

    def test_every_source_path_exists(self) -> None:
        for name in covered.SOURCE_DIRS:
            self.assertTrue((ROOT / name).is_dir(), f"{name} is covered but missing")
        for name in covered.SOURCE_FILES:
            self.assertTrue((ROOT / name).is_file(), f"{name} is covered but missing")

    def test_the_wheel_contents_are_covered(self) -> None:
        """A shipped path missing from the basis is a path with no provenance."""
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        section = pyproject.split("[tool.hatch.build.targets.wheel.force-include]")[1]
        section = section.split("\n[", 1)[0]
        shipped = {
            line.split("=", 1)[0].strip().strip('"')
            for line in section.splitlines()
            if "=" in line and not line.strip().startswith("#")
        }
        # A shipped generated file (index.json) is described by the SBOM, and
        # its date follows the skills/ it is generated from.
        basis = set(covered.SOURCE_DIRS) | set(covered.SBOM_FILES)
        for path in shipped:
            if path.startswith((".", "LICENSE")):
                continue
            self.assertIn(path, basis, f"{path} ships in the wheel but has no provenance")


class PackagedEntryPointTests(unittest.TestCase):
    """`uvx agtmls` must behave like a checkout, or the wheel is a different tool."""

    def run_module(self, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
        environment = dict(os.environ)
        environment["PYTHONPATH"] = os.pathsep.join(
            [str(ROOT / "src")] + ([environment["PYTHONPATH"]] if environment.get("PYTHONPATH") else [])
        )
        environment.update(env or {})
        return subprocess.run(
            [sys.executable, "-m", "agtmls", *args],
            cwd=ROOT, env=environment, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
        )

    def test_python_m_agtmls_dispatches(self) -> None:
        proc = self.run_module("stats", "--json")
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(
            json.loads(proc.stdout)["registry_version"],
            json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"],
        )

    def test_a_failing_subcommand_propagates_its_exit_code(self) -> None:
        proc = self.run_module("show", "no-such-skill-anywhere")
        self.assertEqual(proc.returncode, 1, proc.stdout)

    def test_agtmls_home_pointing_at_rubbish_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            proc = self.run_module("list", env={"AGTMLS_HOME": raw})
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("not an AgtMLS checkout", proc.stdout)

    def test_agtmls_home_pointing_at_a_checkout_is_used(self) -> None:
        proc = self.run_module("stats", env={"AGTMLS_HOME": str(ROOT)})
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_usage_errors_exit_two(self) -> None:
        proc = self.run_module("definitely-not-a-subcommand")
        self.assertEqual(proc.returncode, 2, proc.stdout)


class PackagedWheelLayoutTests(unittest.TestCase):
    """The branches that only exist once the registry is inside the wheel.

    A checkout never takes them, because `registry_root()` finds the checkout
    first -- so they were the last uncovered lines in the entry point, and
    they are the ones deciding whether `uvx agtmls` works at all.

    Exercised in-process against the real module, with `__file__` and
    `_PACKAGED` pointed at a fixture that has the layout pyproject's
    force-include produces. An earlier attempt copied cli.py into the fixture
    and ran it as a subprocess; that tested a *different file*, so the real
    one stayed uncovered while the tests passed.
    """

    def setUp(self) -> None:
        sys.path.insert(0, str(ROOT / "src"))
        import agtmls.cli as module

        self.module = module
        self.original = (module.__file__, module._PACKAGED)
        self.addCleanup(self.restore)

    def restore(self) -> None:
        self.module.__file__, self.module._PACKAGED = self.original

    def fixture(self, with_registry: bool) -> Path:
        """A package tree with `_registry/` beside `cli.py`."""
        root = Path(tempfile.mkdtemp(prefix="agtmls-wheel-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(root, ignore_errors=True))
        package = root / "site" / "agtmls"
        package.mkdir(parents=True)
        registry = package / "_registry"
        if with_registry:
            scripts = registry / "scripts"
            scripts.mkdir(parents=True)
            # Enough to prove which argv the shim forwarded, without carrying
            # the whole registry.
            (scripts / "agtmls.py").write_text(
                "import json, sys\nprint(json.dumps(sys.argv[1:]))\n", encoding="utf-8"
            )
        self.module.__file__ = str(package / "cli.py")
        self.module._PACKAGED = registry
        return registry

    def call(self, *args: str) -> tuple[int, str]:
        import contextlib
        import io

        buffer = io.StringIO()
        code = 0
        with contextlib.redirect_stdout(buffer):
            try:
                code = self.module.main(list(args))
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else 1
                if isinstance(exc.code, str):
                    buffer.write(exc.code)
        return code, buffer.getvalue()

    def test_the_bundled_registry_is_found(self) -> None:
        registry = self.fixture(True)
        root, packaged = self.module.registry_root()
        self.assertTrue(packaged)
        self.assertEqual(root, registry)

    def test_install_from_a_wheel_defaults_to_copy(self) -> None:
        """Symlinking into a uvx cache about to be collected leaves dangling links."""
        self.fixture(True)
        code, out = self.call("install", "rust", "claude")
        self.assertEqual(code, 0, out)
        self.assertIn("--copy", json.loads(out))

    def test_an_explicit_copy_flag_is_not_duplicated(self) -> None:
        self.fixture(True)
        _, out = self.call("install", "rust", "claude", "--copy")
        self.assertEqual(json.loads(out).count("--copy"), 1, out)

    def test_a_checkout_command_is_not_given_the_copy_flag(self) -> None:
        self.fixture(True)
        _, out = self.call("list")
        self.assertEqual(json.loads(out), ["list"])

    def test_checkout_only_commands_are_refused_with_a_remedy(self) -> None:
        self.fixture(True)
        code, out = self.call("check")
        self.assertNotEqual(code, 0)
        self.assertIn("needs a repository checkout", out)
        self.assertIn("AGTMLS_HOME", out)

    def test_a_package_with_no_registry_says_so(self) -> None:
        self.fixture(False)
        code, out = self.call("list")
        self.assertNotEqual(code, 0)
        self.assertIn("registry not found", out)
