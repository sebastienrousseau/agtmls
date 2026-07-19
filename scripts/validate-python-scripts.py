#!/usr/bin/env python3
"""Validate Python maintenance scripts."""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"


def main() -> int:
    errors: list[str] = []
    scripts = sorted(SCRIPTS.glob("*.py"))
    for path in scripts:
        text = path.read_text(encoding="utf-8")
        if not text.startswith("#!/usr/bin/env python3\n"):
            errors.append(f"{path.relative_to(ROOT)}: missing python3 shebang")
        try:
            ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            errors.append(f"{path.relative_to(ROOT)}: syntax error: {exc}")
        if not os.access(path, os.X_OK):
            errors.append(f"{path.relative_to(ROOT)}: not executable")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} Python script issue(s)")
        return 1
    print(f"OK: {len(scripts)} Python script(s) valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
