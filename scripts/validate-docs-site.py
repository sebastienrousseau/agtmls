#!/usr/bin/env python3
"""Validate generated static docs site."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site" / "index.html"


def main() -> int:
    errors: list[str] = []
    if not SITE.exists():
        errors.append("site/index.html missing")
    else:
        text = SITE.read_text(encoding="utf-8")
        for needle in ["AgtMLS Registry Catalog", "Quality", "Export Targets", "cross-language-port", "providers.json"]:
            if needle not in text:
                errors.append(f"site/index.html missing {needle!r}")
        if "<script" in text.lower():
            errors.append("site/index.html must remain static without inline scripts")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} docs site issue(s)")
        return 1
    print("OK: docs site valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
