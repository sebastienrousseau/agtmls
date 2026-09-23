# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""A broken-tree harness for the per-branch validator tests.

`test_validator_gate.py` proves each data validator can fail at all. The
modules that use this harness go one step further: every distinct complaint a
validator knows how to make is provoked on its own and asserted by its exact
`FAIL:` text. A validator whose individual checks are never seen to fire can
lose one of them and still pass the gate.

One fixture serves every module that imports this. Copying the tree costs
about a second, and the tests between them break it several hundred times;
paying that once, rather than once per class, is what keeps them fast. Every
break is undone by a cleanup the moment its test ends, so sharing the copy is
safe as long as no test edits it without going through these helpers.

Not named `test_*`, so discovery imports it only through the modules that use
it and never runs it as a suite of its own.
"""

from __future__ import annotations

import atexit
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from .support import load_script, registry_fixture, retarget, run_main

_FIXTURE: Path | None = None


def shared_fixture() -> Path:
    """The one registry copy, made on first use and removed at exit."""
    global _FIXTURE
    if _FIXTURE is None:
        workspace = tempfile.mkdtemp(prefix="agtmls-branches-")
        atexit.register(shutil.rmtree, workspace, ignore_errors=True)
        _FIXTURE = registry_fixture(Path(workspace))
    return _FIXTURE


class BrokenTreeCase(unittest.TestCase):
    """Break one thing in the shared copy, run one validator, put it back."""

    fixture: Path

    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = shared_fixture()

    # -- breaking the tree -------------------------------------------------

    def restore_later(self, relative: str) -> Path:
        path = self.fixture / relative
        original = path.read_bytes() if path.is_file() else None

        def restore() -> None:
            if original is None:
                if path.is_file():
                    path.unlink()
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(original)

        self.addCleanup(restore)
        return path

    def overwrite(self, relative: str, text: str) -> Path:
        path = self.restore_later(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def create_dir(self, relative: str) -> Path:
        """A directory that must not outlive the test, created with its parents.

        Registered before anything is written into it, so its files -- each
        registered by `overwrite` after this -- are removed first, and the
        cleanup here only has to take away what is left.
        """
        path = self.fixture / relative
        self.assertFalse(path.exists(), f"{relative} already exists in the fixture")
        self.addCleanup(shutil.rmtree, path, ignore_errors=True)
        path.mkdir(parents=True)
        return path

    def edit_json(self, relative: str, mutate) -> Path:
        path = self.restore_later(relative)
        data = json.loads(path.read_text(encoding="utf-8"))
        mutate(data)
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return path

    def remove(self, relative: str) -> None:
        self.restore_later(relative).unlink()

    def move_aside(self, relative: str) -> None:
        """Take a directory out of the tree and put it back afterwards."""
        path = self.fixture / relative
        parked = path.with_name(path.name + ".parked")
        path.rename(parked)
        self.addCleanup(parked.rename, path)

    # -- running a validator -----------------------------------------------

    def run_validator(self, script: str, *args: str) -> tuple[int, str]:
        module = load_script(script)
        retarget(module, self.fixture)
        return run_main(module, *args)

    def assert_clean(self, script: str, *args: str) -> str:
        code, output = self.run_validator(script, *args)
        self.assertEqual(code, 0, f"{script} failed on a pristine fixture:\n{output}")
        return output

    def assert_fails(self, script: str, *expected: str) -> str:
        """Nonzero exit, and every expected complaint said in so many words."""
        code, output = self.run_validator(script)
        self.assertNotEqual(code, 0, f"{script} accepted a broken tree:\n{output}")
        for text in expected:
            self.assertIn(text, output)
        return output
