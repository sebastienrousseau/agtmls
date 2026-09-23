# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""SHA256SUMS parsing, shared by the release rehearsal and the published audit.

Both scripts split every line into a digest and a name, so a blank line --
which any editor or a third-party tool may add -- raised ValueError and
turned a checksum audit into a traceback. The audit has to say what is wrong
with the file, not crash on reading it.
"""

from __future__ import annotations

import sys
import unittest

from .support import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
from _lib.checksums import parse_sums  # needs the scripts path first

DIGEST = "a" * 64


class ParseSumsTests(unittest.TestCase):
    def test_digest_and_name_are_read_from_each_line(self) -> None:
        sums, errors = parse_sums(f"{DIGEST}  one.tar.gz\n{'b' * 64}  two.whl\n")
        self.assertEqual(sums, {"one.tar.gz": DIGEST, "two.whl": "b" * 64})
        self.assertEqual(errors, [])

    def test_blank_lines_are_skipped(self) -> None:
        sums, errors = parse_sums(f"\n{DIGEST}  one.tar.gz\n\n   \n")
        self.assertEqual((sums, errors), ({"one.tar.gz": DIGEST}, []))

    def test_the_binary_mode_marker_is_not_part_of_the_name(self) -> None:
        """`sha256sum -b` writes `<digest> *<name>`."""
        sums, _ = parse_sums(f"{DIGEST} *one.tar.gz\n")
        self.assertEqual(sums, {"one.tar.gz": DIGEST})

    def test_a_line_that_is_not_digest_and_name_is_reported_by_number(self) -> None:
        sums, errors = parse_sums(f"{DIGEST}  one.tar.gz\njunk\nnot-a-digest  two.whl\n")
        self.assertEqual(sums, {"one.tar.gz": DIGEST})
        self.assertEqual(errors, [
            "SHA256SUMS line 2 is not '<sha256>  <file>': 'junk'",
            "SHA256SUMS line 3 is not '<sha256>  <file>': 'not-a-digest  two.whl'",
        ])


if __name__ == "__main__":
    unittest.main()
