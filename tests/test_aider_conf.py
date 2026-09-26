# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""aider_conf: one file in or out of .aider.conf.yml's top-level `read:` list.

The installer appended `read:\\n  - CONVENTIONS.md` whatever the file held, so
a config with its own `read:` gained a second key. Each case is a form a
hand-written config takes, and each edit must leave every other line as it
was; a shape the module cannot edit safely is left alone and reported.
"""

from __future__ import annotations

import contextlib
import io
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from .support import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
from _lib import aider_conf  # needs the scripts path first

NAME = "CONVENTIONS.md"


def capture(function, *args) -> tuple[int, str]:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        code = function(*args)
    return code, buffer.getvalue()


class RegisterTests(unittest.TestCase):
    def register(self, text: str) -> str | None:
        return aider_conf.register(text, NAME)[0]

    def test_a_missing_or_keyless_config_gains_a_read_block(self) -> None:
        self.assertEqual(self.register(""), f"read:\n  - {NAME}\n")
        self.assertEqual(self.register("model: sonnet"), f"model: sonnet\nread:\n  - {NAME}\n")

    def test_an_existing_block_list_gains_one_item_in_its_own_indent(self) -> None:
        cases = {
            "read:\n  - NOTES.md\nmodel: sonnet\n": f"read:\n  - NOTES.md\n  - {NAME}\nmodel: sonnet\n",
            "read:\n- NOTES.md\n- 'A.md'  # mine\n": f"read:\n- NOTES.md\n- 'A.md'  # mine\n- {NAME}\n",
            "read:\n    - NOTES.md\n\n# end\n": f"read:\n    - NOTES.md\n    - {NAME}\n\n# end\n",
            "read:\nmodel: sonnet\n": f"read:\n  - {NAME}\nmodel: sonnet\n",
        }
        for before, after in cases.items():
            with self.subTest(before=before):
                self.assertEqual(self.register(before), after)

    def test_flow_and_scalar_values_are_extended(self) -> None:
        self.assertEqual(self.register("read: [NOTES.md, \"B.md\"]\n"), f"read: [NOTES.md, B.md, {NAME}]\n")
        self.assertEqual(self.register("read: []\n"), f"read: [{NAME}]\n")
        self.assertEqual(self.register("read: NOTES.md # mine\n"), f"read:\n  - NOTES.md\n  - {NAME}\n")

    def test_an_entry_already_there_in_any_form_changes_nothing(self) -> None:
        for text in (f"read:\n  - {NAME}\n", f"read: ['{NAME}']\n", f"read: \"{NAME}\"\n"):
            with self.subTest(text=text):
                new, message = aider_conf.register(text, NAME)
                self.assertIsNone(new)
                self.assertEqual(message, f"{NAME} is already in read:")

    def test_a_shape_it_cannot_edit_safely_is_left_and_named(self) -> None:
        cases = {
            "read:\n  - A.md\nread:\n  - B.md\n": "it has more than one top-level `read:` key",
            "read: [A.md,\n  B.md]\n": "its `read:` flow list spans lines",
            "read:\n  nested: true\n": "its `read:` list holds something other than `- <file>` items",
        }
        for text, reason in cases.items():
            with self.subTest(text=text):
                new, message = aider_conf.register(text, NAME)
                self.assertIsNone(new)
                self.assertEqual(message, f"not changed: {reason}; add {NAME} to read: yourself")


class UnregisterTests(unittest.TestCase):
    def test_register_then_unregister_restores_the_original(self) -> None:
        for original in (
            "model: sonnet\n",
            "read:\n  - NOTES.md\nmodel: sonnet\n",
            "read: [NOTES.md]\n",
        ):
            with self.subTest(original=original):
                registered = aider_conf.register(original, NAME)[0]
                self.assertEqual(aider_conf.unregister(registered, NAME), (original, True))

    def test_a_config_holding_only_the_entry_is_to_be_deleted(self) -> None:
        for text in (f"read:\n  - {NAME}\n", f"read: [{NAME}]\n", f"read: {NAME}\n"):
            with self.subTest(text=text):
                self.assertEqual(aider_conf.unregister(text, NAME), (None, True))

    def test_a_config_without_the_entry_is_unchanged(self) -> None:
        text = "read:\n  - NOTES.md\n"
        self.assertEqual(aider_conf.unregister(text, NAME), (text, False))


class CommandLineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="agtmls-aider-"))
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))
        self.conf = self.tmp / ".aider.conf.yml"

    def main(self, *args: str) -> tuple[int, str]:
        return capture(aider_conf.main, ["aider_conf.py", *args])

    def test_register_writes_and_unregister_removes_the_file_it_emptied(self) -> None:
        self.assertEqual(self.main("register", str(self.conf), NAME), (0, f"added read: {NAME}\n"))
        self.assertEqual(self.conf.read_text(encoding="utf-8"), f"read:\n  - {NAME}\n")
        self.assertEqual(self.main("register", str(self.conf), NAME), (0, f"{NAME} is already in read:\n"))
        self.assertEqual(self.main("unregister", str(self.conf), NAME), (0, f"removed {NAME} from read:\n"))
        self.assertFalse(self.conf.exists())
        self.assertEqual(self.main("unregister", str(self.conf), NAME), (0, f"{NAME} was not in read:\n"))

    def test_unregister_keeps_the_rest_of_the_file(self) -> None:
        self.conf.write_text(f"model: sonnet\nread:\n  - {NAME}\n", encoding="utf-8")
        self.main("unregister", str(self.conf), NAME)
        self.assertEqual(self.conf.read_text(encoding="utf-8"), "model: sonnet\n")

    def test_a_bad_invocation_prints_usage(self) -> None:
        code, _ = capture(aider_conf.main, ["aider_conf.py", "bogus"])
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
