#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Run the unit suite.

The 65-check gate validates repository *data*. These tests validate the
*validators*, and they live in `tests/` as a discovered package rather than in
this file: it had reached 1,248 lines, which the maintainability ceiling
exists to catch.

Discovery, not a hand-maintained registry. A TestCase added to a module here
runs without being named anywhere, and a gate that silently skips tests is the
failure this suite exists to prevent.

    python3 scripts/run-unit-tests.py
    python3 -m unittest discover -s tests -t .
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    sys.path.insert(0, str(ROOT))
    suite = unittest.defaultTestLoader.discover(
        start_dir=str(ROOT / "tests"), top_level_dir=str(ROOT)
    )
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if not result.wasSuccessful():
        return 1
    if result.testsRun == 0:
        print("FAIL: discovery found no tests; run `python3 -m unittest discover "
              "-s tests -t .` to see why")
        return 1
    print(f"OK: {result.testsRun} unit test(s) passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
