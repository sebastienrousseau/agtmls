# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""A fixture holding only what one generator reads.

`registry_fixture` copies the whole data tree, which costs over a second a
copy. The generators below each read a handful of files, and the unit suite
has a runtime budget, so each TestCase copies just those files and then drives
the real script against them through `retarget`, exactly as the full-copy
tests do. A generator that reads something the subset left out fails loudly
with FileNotFoundError; it cannot fall back to the real repository, because
retarget refuses to return while any module path still points there.
"""

from __future__ import annotations

import shutil
import tempfile
import types
import unittest
from pathlib import Path

from .support import ROOT, load_script, retarget, run_main


def subset_fixture(destination: Path, names: tuple[str, ...]) -> Path:
    """Copy `names` (paths relative to the repository root) into `destination`."""
    destination.mkdir(parents=True, exist_ok=True)
    # Resolved for the same reason registry_fixture resolves: macOS maps /var
    # onto /private/var, and generators print paths relative to their root.
    destination = destination.resolve()
    for name in names:
        source = ROOT / name
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(
                source, target, symlinks=True,
                ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"),
            )
        elif source.exists():
            shutil.copy2(source, target)
    return destination


def fake_git(stdout: str = "", *, raises: type[BaseException] | None = None):
    """A stand-in for the `subprocess` module that records what was asked.

    Provenance and the SBOM take their timestamps from `git log`. The fixture
    is not a repository, and the real answer moves with every commit, so a
    test that let git run would assert either nothing or something that stops
    being true tomorrow. `stdout` may be a callable of the argv.
    """
    calls: list[list[str]] = []

    def run(argv, **_kwargs):
        calls.append(list(argv))
        if raises is not None:
            raise raises("git is not installed")
        text = stdout(argv) if callable(stdout) else stdout
        return types.SimpleNamespace(stdout=text, returncode=0)

    module = types.SimpleNamespace(run=run, PIPE=-1, DEVNULL=-3, calls=calls)
    return module


class SubsetCase(unittest.TestCase):
    """One small fixture per class; files a test changes are put back after it."""

    SCRIPT = ""
    SUBSET: tuple[str, ...] = ()
    fixture: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls._workspace = tempfile.mkdtemp(prefix="agtmls-subset-")
        cls.fixture = subset_fixture(Path(cls._workspace) / "tree", cls.SUBSET)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls._workspace, ignore_errors=True)

    def script(self, name: str = ""):
        module = load_script(name or self.SCRIPT)
        retarget(module, self.fixture)
        return module

    def drive(self, *args: str, module=None) -> tuple[int, str]:
        return run_main(module or self.script(), *args)

    def path(self, relative: str) -> Path:
        return self.fixture / relative

    def preserve(self, *relatives: str) -> None:
        """Restore these fixture paths after the test, including their absence."""
        for relative in relatives:
            path = self.path(relative)
            if path.is_dir():
                backup = Path(tempfile.mkdtemp(prefix="agtmls-keep-")) / "copy"
                shutil.copytree(path, backup, symlinks=True)
                self.addCleanup(self._restore_dir, path, backup)
            else:
                data = path.read_bytes() if path.exists() else None
                self.addCleanup(self._restore_file, path, data)

    @staticmethod
    def _restore_file(path: Path, data: bytes | None) -> None:
        if data is None:
            path.unlink(missing_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

    @staticmethod
    def _restore_dir(path: Path, backup: Path) -> None:
        shutil.rmtree(path, ignore_errors=True)
        shutil.copytree(backup, path, symlinks=True)
        shutil.rmtree(backup.parent, ignore_errors=True)
