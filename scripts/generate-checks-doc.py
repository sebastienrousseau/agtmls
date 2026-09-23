#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Render the check list in docs/checks.md from checks.json.

docs/checks.md was a hand-kept copy of the gate, and nothing compared it with
the manifest. By v0.0.7 it listed 47 of the 66 checks, in a different order,  check-count:historical
and named one invocation (`agtmls-doctor.py` without `--skip-gate`) the gate
does not run. The list now lives between markers:

    <!-- generated:checks source="checks.json" -->
    ...
    <!-- /generated:checks -->

`--write` re-renders it; `--check` fails if it differs from the manifest. The
prose around the markers is authored and left alone.

    python3 scripts/generate-checks-doc.py --write
    python3 scripts/generate-checks-doc.py --check
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "checks.md"
MANIFEST = ROOT / "checks.json"

OPEN = '<!-- generated:checks source="checks.json" -->'
CLOSE = "<!-- /generated:checks -->"
BLOCK = re.compile(re.escape(OPEN) + r"\n.*?" + re.escape(CLOSE), re.DOTALL)


def render(checks: list[str]) -> str:
    lines = "\n".join(f"python3 scripts/{check}" for check in checks)
    return f"{OPEN}\n```bash\n{lines}\n```\n{CLOSE}"


def rendered_doc(text: str) -> str | None:
    """`text` with the block re-rendered, or None when it has no block."""
    if not BLOCK.search(text):
        return None
    checks = json.loads(MANIFEST.read_text(encoding="utf-8"))["checks"]
    return BLOCK.sub(lambda _: render(checks), text, count=1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()

    current = DOC.read_text(encoding="utf-8")
    fresh = rendered_doc(current)
    if fresh is None:
        print(f"FAIL: {DOC.relative_to(ROOT)} has no {OPEN} block")
        return 1
    if args.write:
        DOC.write_text(fresh, encoding="utf-8")
        print(f"wrote {DOC.relative_to(ROOT)}")
        return 0
    if current != fresh:
        print(f"FAIL: {DOC.relative_to(ROOT)} does not list checks.json; run generate-checks-doc.py --write")
        return 1
    print(f"OK: {DOC.relative_to(ROOT)} lists every check in checks.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
