# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""No tracked file names a path inside someone's home directory.

`GEMINI.md` ships in the Gemini CLI extension and `AGENTS.md` is read by
every agent working in a clone; until v0.0.31 both pointed into the
maintainer's home directory, which exists on one laptop and nowhere else. A
reader elsewhere gets a dead reference, and the maintainer's home layout
is published with every release.
"""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Built from parts so this file does not match itself.
HOME_PATH = re.compile("/" + "(?:Users|home)" + r"/[A-Za-z][A-Za-z0-9._-]*/")


def tracked() -> list[str]:
    proc = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        raise unittest.SkipTest("not a git checkout")
    return [name for name in proc.stdout.split("\0") if name]


class PersonalPathTests(unittest.TestCase):
    def test_no_tracked_file_names_a_home_directory(self) -> None:
        hits = []
        for name in tracked():
            path = ROOT / name
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue  # binary: a GIF or a wheel fixture holds no prose
            hits += [
                f"{name}:{text.count(chr(10), 0, m.start()) + 1}: {m.group(0)}"
                for m in HOME_PATH.finditer(text)
            ]
        self.assertEqual(hits, [], "home-directory paths in tracked files:\n" + "\n".join(hits))


if __name__ == "__main__":
    unittest.main()
