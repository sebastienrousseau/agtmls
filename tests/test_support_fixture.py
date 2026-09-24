# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""registry_fixture: the copy of the tree every validator test breaks."""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from . import support


class RegistryFixtureTests(unittest.TestCase):
    def test_a_file_that_vanishes_mid_copy_does_not_take_the_fixture_down(self) -> None:
        """The coverage gate writes and deletes `.coverage.*` files beside the
        tree while tests run; one vanished between iterdir() and copy2()."""
        real = shutil.copy2
        vanished: list[str] = []

        def flaky(src, dst, *args, **kwargs):
            if src.name == "README.md" and not vanished:
                vanished.append(src.name)
                raise FileNotFoundError(src)
            return real(src, dst, *args, **kwargs)

        with tempfile.TemporaryDirectory() as raw, mock.patch.object(support.shutil, "copy2", flaky):
            fixture = support.registry_fixture(Path(raw) / "tree")
            self.assertTrue((fixture / "providers.json").exists())
            self.assertFalse((fixture / "README.md").exists())
        self.assertEqual(vanished, ["README.md"])

    def test_a_release_signature_in_the_tree_is_never_copied(self) -> None:
        """The release job runs the gate with index.json.sig present."""
        sig = support.ROOT / "index.json.sig"
        created = not sig.exists()
        if created:
            sig.write_text("signature\n", encoding="utf-8")
            self.addCleanup(lambda: sig.unlink(missing_ok=True))
        with tempfile.TemporaryDirectory() as raw:
            fixture = support.registry_fixture(Path(raw) / "tree")
            self.assertFalse((fixture / "index.json.sig").exists())
            self.assertTrue((fixture / "index.json").exists())

    def test_coverage_data_files_are_never_copied(self) -> None:
        stray = support.ROOT / ".coverage.test-host.pid1.abc"
        stray.write_text("", encoding="utf-8")
        self.addCleanup(lambda: stray.unlink(missing_ok=True))
        with tempfile.TemporaryDirectory() as raw:
            fixture = support.registry_fixture(Path(raw) / "tree")
            self.assertFalse((fixture / stray.name).exists())
