# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The validators the tree-only sweep had to leave out.

`test_validator_gate.py` drives every validator it can against a full copy of
the registry, and lists the ones it cannot in NEEDS_MORE_THAN_A_TREE: they
read the real packaging manifest, shell out, or compare against the real
scripts. Excluded from the sweep, they were excluded from any proof that they
can fail, and the gate runs each one on every commit.

None of them needs the whole tree, though. Each reads a handful of files, so
each class here copies exactly those -- the real ones, so "passes on a correct
tree" means the tree that ships -- and breaks them one at a time. Copying a
slice instead of the registry keeps the whole module well under a second.
Wherever a validator shells out, the tool is replaced with a stand-in that
records how it was called; the decision about what its answer means is the
code under test, and the tool's own behaviour is not.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from .support import ROOT, load_script, retarget, run_main

try:
    import tomllib  # noqa: F401
    NO_TOMLLIB = False
except ModuleNotFoundError:  # pragma: no cover - 3.10 only
    NO_TOMLLIB = True
# On 3.10 validate-packaging.py reads only the force-include table and the
# version, so the checks that need a real TOML parser do not run there.


class SliceFixture(unittest.TestCase):
    """A few real files copied out of the repository, and one validator.

    SCRIPT names the validator; PATHS lists what it reads, relative to the
    repository root. Tests restore whatever they break, so order does not
    matter and one copy per class is enough.
    """

    SCRIPT = ""
    PATHS: tuple[str, ...] = ()
    fixture: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls._workspace = tempfile.mkdtemp(prefix="agtmls-slice-")
        # Resolved for the same reason registry_fixture resolves: macOS maps
        # /var onto /private/var, and relative_to() needs one spelling.
        cls.fixture = Path(cls._workspace).resolve()
        for relative in cls.PATHS:
            source = ROOT / relative
            target = cls.fixture / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))
            else:
                shutil.copy2(source, target)
        cls.populate()

    @classmethod
    def populate(cls) -> None:
        """Hook for a class whose validator needs more than copies."""

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._workspace, ignore_errors=True)

    def restore_later(self, relative: str) -> Path:
        path = self.fixture / relative
        original = path.read_bytes() if path.is_file() else None
        mode = path.stat().st_mode if path.is_file() else None

        def restore() -> None:
            if original is None:
                if path.is_file():
                    path.unlink()
                return
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(original)
            os.chmod(path, mode)

        self.addCleanup(restore)
        return path

    def overwrite(self, relative: str, text: str) -> Path:
        path = self.restore_later(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def replace(self, relative: str, old: str, new: str) -> Path:
        """Swap one string, and refuse if it is not there to swap.

        A replacement that silently matches nothing leaves the tree correct,
        and the test would then be asserting a failure it never caused.
        """
        path = self.fixture / relative
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text, f"{relative} no longer contains {old!r}; the test is stale")
        return self.overwrite(relative, text.replace(old, new))

    def edit_json(self, relative: str, mutate) -> Path:
        path = self.restore_later(relative)
        data = json.loads(path.read_text(encoding="utf-8"))
        mutate(data)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return path

    def remove(self, relative: str) -> None:
        self.restore_later(relative).unlink()

    def module(self):
        module = load_script(self.SCRIPT)
        retarget(module, self.fixture)
        return module

    def run_validator(self, *args: str) -> tuple[int, str]:
        return run_main(self.module(), *args)

    def assert_clean(self) -> str:
        code, output = self.run_validator()
        self.assertEqual(code, 0, f"{self.SCRIPT} failed on a correct tree:\n{output}")
        self.assertIn("OK:", output)
        self.assertNotIn("FAIL", output)
        return output

    def assert_catches(self, *complaints: str, count: int | None = None) -> str:
        """Fail, and say each of `complaints`; with `count`, say nothing else."""
        code, output = self.run_validator()
        self.assertEqual(code, 1, f"{self.SCRIPT} accepted a broken tree:\n{output}")
        for complaint in complaints:
            self.assertIn(complaint, output)
        if count is not None:
            self.assertIn(f"FAIL: {count} ", output)
        return output


class PackagingValidatorTests(SliceFixture):
    """A wheel that installs and then cannot find its own skills.

    That failure is silent at build time, so this validator is the only thing
    between a layout mistake and every `uvx agtmls` user. The fixture holds
    the real pyproject, plugin manifest and package version, plus a stand-in
    for each force-included path: only their existence is checked.
    """

    SCRIPT = "validate-packaging.py"
    PATHS = ("pyproject.toml", ".claude-plugin/plugin.json", "src/agtmls/__init__.py")

    @classmethod
    def populate(cls) -> None:
        # Read with the validator's own fallback parser, which a sibling test
        # proves equal to tomllib: the suite also runs on 3.10, which has none.
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        include = load_script(cls.SCRIPT).parse_force_include(text)
        for source in include:
            stand_in = cls.fixture / source
            if (ROOT / source).is_dir():
                stand_in.mkdir(parents=True, exist_ok=True)
            elif not stand_in.exists():
                stand_in.parent.mkdir(parents=True, exist_ok=True)
                stand_in.write_text("stand-in\n", encoding="utf-8")
        cls.version = re.search(r'^version = "([^"]+)"', text, re.MULTILINE).group(1)
        cls.bundled = len(include)

    def test_the_shipped_layout_passes(self) -> None:
        output = self.assert_clean()
        self.assertIn(f"{self.bundled} path(s) bundled into agtmls/_registry/", output)

    def test_a_missing_pyproject_is_the_first_complaint(self) -> None:
        self.remove("pyproject.toml")
        self.assert_catches("FAIL: pyproject.toml missing")

    def test_the_wrong_distribution_name_is_caught(self) -> None:
        self.replace("pyproject.toml", 'name = "agtmls"', 'name = "agtmls-fork"')
        self.assert_catches("pyproject project.name must be agtmls", count=1)

    def test_a_console_script_aimed_elsewhere_is_caught(self) -> None:
        """`uvx agtmls` runs whatever this names; the wrong target is a dead CLI."""
        self.replace("pyproject.toml", 'agtmls = "agtmls.cli:main"', 'agtmls = "agtmls.cli:run"')
        self.assert_catches("console script agtmls must be agtmls.cli:main", count=1)

    def test_a_runtime_dependency_is_caught(self) -> None:
        """One dependency turns an instant uvx launch into a resolver run."""
        self.replace("pyproject.toml", "dependencies = []", 'dependencies = ["requests"]')
        self.assert_catches("dependencies must stay empty", count=1)

    def test_a_runtime_path_left_out_of_the_wheel_is_caught(self) -> None:
        self.replace(
            "pyproject.toml", '"profiles.json" = "agtmls/_registry/profiles.json"\n', ""
        )
        self.assert_catches("force-include missing runtime path: profiles.json", count=1)

    def test_a_runtime_path_mapped_to_the_wrong_name_is_caught(self) -> None:
        """Scripts resolve the registry by name; a renamed directory is invisible."""
        self.replace(
            "pyproject.toml",
            '"skills" = "agtmls/_registry/skills"',
            '"skills" = "agtmls/_registry/skillz"',
        )
        self.assert_catches(
            "force-include skills maps to agtmls/_registry/skillz, expected agtmls/_registry/skills",
            count=1,
        )

    def test_a_force_included_path_that_does_not_exist_is_caught(self) -> None:
        self.remove("CATALOG.md")
        self.assert_catches("force-include source does not exist: CATALOG.md", count=1)

    def test_a_path_bundled_outside_the_registry_is_caught(self) -> None:
        self.replace(
            "pyproject.toml", '"agtmls/_registry/CATALOG.md"', '"elsewhere/CATALOG.md"'
        )
        self.assert_catches(
            "force-include target must live under agtmls/_registry/: elsewhere/CATALOG.md",
            count=1,
        )

    def test_a_plugin_manifest_on_another_version_is_caught(self) -> None:
        """Two version numbers that disagree mean one release shipped as two."""
        self.edit_json(".claude-plugin/plugin.json", lambda data: data.__setitem__("version", "9.9.9"))
        self.assert_catches(
            f"pyproject version {self.version} must match plugin.json 9.9.9",
            f"__version__ {self.version} must match plugin.json 9.9.9",
            count=2,
        )

    def test_a_package_that_does_not_declare_its_version_is_caught(self) -> None:
        self.overwrite("src/agtmls/__init__.py", '"""No version here."""\n')
        self.assert_catches("src/agtmls/__init__.py must define __version__", count=1)

    def test_a_package_version_that_drifted_is_caught(self) -> None:
        self.replace("src/agtmls/__init__.py", f'__version__ = "{self.version}"', '__version__ = "0.0.0"')
        self.assert_catches(f"__version__ 0.0.0 must match plugin.json {self.version}", count=1)

    def test_a_missing_package_is_caught(self) -> None:
        self.remove("src/agtmls/__init__.py")
        self.assert_catches("src/agtmls/__init__.py missing", count=1)

    def test_the_fallback_parser_reads_nothing_without_the_table(self) -> None:
        """On 3.10 a pyproject without the table must look empty, not crash."""
        module = self.module()
        self.assertEqual(module.parse_force_include("[project]\nname = \"agtmls\"\n"), {})

    def test_the_fallback_parser_ignores_comments_inside_the_table(self) -> None:
        module = self.module()
        text = (
            "[tool.hatch.build.targets.wheel.force-include]\n"
            "# a note\n"
            '"skills" = "agtmls/_registry/skills"  # trailing\n'
        )
        self.assertEqual(module.parse_force_include(text), {"skills": "agtmls/_registry/skills"})



class PackagingWithoutTomllibTests(PackagingValidatorTests):
    """Every packaging verdict again, on the path Python 3.10 takes.

    3.10 has no tomllib, and the validator used to skip the distribution
    name, console script and no-dependencies checks there without a word --
    so one leg of the CI matrix ran a weaker gate while reporting OK.
    """

    def module(self):
        module = super().module()
        module.tomllib = None
        return module


@unittest.skipIf(NO_TOMLLIB, "comparing against tomllib needs 3.11+")
class ProjectFallbackParserTests(unittest.TestCase):
    def test_the_fallback_reads_the_shipped_pyproject_as_tomllib_does(self) -> None:
        import tomllib

        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        project = tomllib.loads(text)["project"]
        expected = {
            "name": project["name"],
            "version": project["version"],
            "scripts": project.get("scripts", {}),
            "dependencies": project.get("dependencies", []),
        }
        self.assertEqual(load_script("validate-packaging.py").parse_project(text), expected)

    def test_a_multi_line_dependency_list_is_read_whole(self) -> None:
        text = '[project]\nname = "x"\ndependencies = [\n  "a>=1",\n  "b",\n]\n[project.scripts]\nx = "m:f"\n'
        parsed = load_script("validate-packaging.py").parse_project(text)
        self.assertEqual(parsed["dependencies"], ["a>=1", "b"])
        self.assertEqual(parsed["scripts"], {"x": "m:f"})

class PythonScriptValidatorTests(SliceFixture):
    """Every script is run as `./scripts/x.py` by someone; each must be runnable.

    A handful of real scripts stands in for the directory, since the check is
    per file and parsing all of them would only cost time.
    """

    SCRIPT = "validate-python-scripts.py"
    PATHS = (
        "scripts/validate-docs-site.py",
        "scripts/validate-gitignore.py",
        "scripts/validate-packaging.py",
    )
    TARGET = "scripts/validate-docs-site.py"

    def test_real_scripts_pass(self) -> None:
        self.assertIn("OK: 3 Python script(s) valid", self.assert_clean())

    def test_a_script_without_the_python3_shebang_is_caught(self) -> None:
        text = (self.fixture / self.TARGET).read_text(encoding="utf-8")
        self.overwrite(self.TARGET, text.replace("#!/usr/bin/env python3\n", "#!/usr/bin/python\n", 1))
        self.assert_catches(f"{self.TARGET}: missing python3 shebang", count=1)

    def test_a_script_that_does_not_parse_is_caught(self) -> None:
        text = (self.fixture / self.TARGET).read_text(encoding="utf-8")
        self.overwrite(self.TARGET, text + "\ndef broken(:\n")
        self.assert_catches(f"{self.TARGET}: syntax error:", count=1)

    def test_a_script_that_is_not_executable_is_caught(self) -> None:
        """Without the bit, the documented `./scripts/x.py` fails with EACCES."""
        path = self.restore_later(self.TARGET)
        path.chmod(0o644)
        self.assert_catches(f"{self.TARGET}: not executable", count=1)


class ShellSyntaxValidatorTests(SliceFixture):
    """A shell script with a syntax error fails only on the path that runs it.

    `bash -n` is the tool; what is under test is which files it is pointed
    at, and what a non-zero answer turns into. Most cases replace bash with a
    recorder. One runs the real thing, because a stand-in cannot show that
    the flag used really detects a syntax error.
    """

    SCRIPT = "validate-shell-syntax.py"
    PATHS = (
        "scripts/setup-workspace.sh",
        "skills/cross-language-port/harness/golden-diff.sh",
    )
    SHIPPED = ("scripts/setup-workspace.sh", "skills/cross-language-port/harness/golden-diff.sh")

    @classmethod
    def populate(cls) -> None:
        # Copies that live where no shipped script does: VCS internals and
        # bytecode caches. Checking them would report files nobody wrote.
        for skipped in (".git/hooks/pre-commit.sh", "scripts/__pycache__/stale.sh"):
            path = cls.fixture / skipped
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("if then fi\n", encoding="utf-8")

    def drive(self, broken: dict[str, str] | None = None) -> tuple[int, str, list]:
        broken = broken or {}
        calls: list = []

        def fake_bash(argv, **kwargs):
            calls.append((argv, kwargs))
            relative = str(Path(argv[-1]).relative_to(self.fixture))
            if relative in broken:
                return subprocess.CompletedProcess(argv, 2, stdout=broken[relative] + "\n")
            return subprocess.CompletedProcess(argv, 0, stdout="")

        module = self.module()
        with mock.patch.object(module.subprocess, "run", side_effect=fake_bash):
            code, output = run_main(module)
        return code, output, calls

    def test_every_shipped_script_is_checked_and_nothing_else(self) -> None:
        code, output, calls = self.drive()
        self.assertEqual(code, 0, output)
        self.assertIn("OK: 2 shell script(s) syntax-valid", output)
        checked = [str(Path(argv[-1]).relative_to(self.fixture)) for argv, _ in calls]
        self.assertEqual(checked, list(self.SHIPPED))

    def test_each_script_is_parsed_not_executed(self) -> None:
        """`-n` is the whole safety of this check: without it bash runs the file."""
        _, _, calls = self.drive()
        for argv, kwargs in calls:
            self.assertEqual(argv[:2], ["bash", "-n"])
            self.assertEqual(kwargs["cwd"], self.fixture)
            self.assertFalse(kwargs["check"])

    def test_a_rejected_script_is_named_with_the_reason(self) -> None:
        target = self.SHIPPED[1]
        code, output, _ = self.drive({target: "line 3: syntax error near `fi'"})
        self.assertEqual(code, 1, output)
        self.assertIn(f"FAIL: {target}:\nline 3: syntax error near `fi'", output)
        self.assertIn("FAIL: 1 shell syntax issue(s)", output)

    @unittest.skipUnless(shutil.which("bash"), "bash is not installed")
    def test_real_bash_rejects_a_real_syntax_error(self) -> None:
        self.overwrite("scripts/broken.sh", "#!/usr/bin/env bash\nif true; then\n  echo x\n")
        code, output = self.run_validator()
        self.assertEqual(code, 1, output)
        self.assertIn("FAIL: scripts/broken.sh:", output)
        self.assertIn("FAIL: 1 shell syntax issue(s)", output)


class DocsSiteValidatorTests(SliceFixture):
    """The published catalog page: complete, and free of script.

    The page is served as a static file; an inline script in it would be
    code running on the project's domain that no review looked for.
    """

    SCRIPT = "validate-docs-site.py"
    PATHS = ("site/index.html",)
    PAGE = "site/index.html"

    def test_the_generated_page_passes(self) -> None:
        self.assertIn("OK: docs site valid", self.assert_clean())

    def test_a_missing_page_is_caught(self) -> None:
        self.remove(self.PAGE)
        self.assert_catches("site/index.html missing", count=1)

    def test_each_required_section_is_checked(self) -> None:
        for needle in ("AgtMLS Registry Catalog", "Quality", "Export Targets",
                       "cross-language-port", "providers.json"):
            with self.subTest(needle=needle):
                self.replace(self.PAGE, needle, "")
                self.assert_catches(f"site/index.html missing {needle!r}", count=1)
                self.doCleanups()

    def test_an_inline_script_is_caught_whatever_its_case(self) -> None:
        self.replace(self.PAGE, "</body>", "<SCRIPT>alert(1)</SCRIPT></body>")
        self.assert_catches("must remain static without inline scripts", count=1)


class IgnorePolicyValidatorTests(SliceFixture):
    """Editor droppings and caches must never reach a commit or a wheel."""

    SCRIPT = "validate-gitignore.py"
    PATHS = (".gitignore",)
    POLICY = ".gitignore"

    def test_the_shipped_policy_passes(self) -> None:
        self.assertIn("OK: .gitignore policy valid with 7 required pattern(s)", self.assert_clean())

    def test_a_required_pattern_that_is_removed_is_caught(self) -> None:
        self.replace(self.POLICY, ".agtmls/\n", "")
        self.assert_catches("missing required .gitignore pattern: .agtmls/", count=1)

    def test_a_commented_out_pattern_does_not_count(self) -> None:
        """`# .DS_Store` reads like a rule and ignores nothing."""
        self.replace(self.POLICY, ".DS_Store\n", "# .DS_Store\n")
        self.assert_catches("missing required .gitignore pattern: .DS_Store", count=1)

    def test_a_repeated_comment_is_not_a_duplicate_pattern(self) -> None:
        """Section headers repeat; only rules can conflict."""
        text = (self.fixture / self.POLICY).read_text(encoding="utf-8")
        self.overwrite(self.POLICY, "# local artifacts\n" + text + "  # local artifacts\n")
        self.assert_clean()

    def test_a_pattern_padded_with_whitespace_still_counts(self) -> None:
        self.replace(self.POLICY, "*.swp\n", "  *.swp  \n")
        self.assert_clean()

    def test_a_duplicated_pattern_is_caught(self) -> None:
        """Duplicates are how two edits to one policy drift apart unnoticed."""
        text = (self.fixture / self.POLICY).read_text(encoding="utf-8")
        self.overwrite(self.POLICY, text + "dist/\n")
        self.assert_catches("duplicate .gitignore pattern: dist/", count=1)
