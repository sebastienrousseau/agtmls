#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Generate MCP-style resource descriptors for AgtMLS skills."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "mcp-resources.json"
# The scheme agtmls-mcp serves (src/tools.rs) and docs/ECOSYSTEM.md defines.
# This file said `agtmls://skills/`, so a client that followed it asked the
# server for URIs it did not know.
URI_PREFIX = "agtmls://skill/"


def render() -> dict:
    index = json.loads((ROOT / "index.json").read_text(encoding="utf-8"))
    return {
        "schema_version": 1,
        "resources": [
            {
                "uri": f"{URI_PREFIX}{skill['name']}",
                "name": skill["name"],
                "description": skill["description"],
                "mimeType": "text/markdown",
                "path": skill["path"] + "/SKILL.md",
            }
            for skill in index["skills"]
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    text = json.dumps(render(), indent=2, sort_keys=True) + "\n"
    if args.write:
        OUT.write_text(text, encoding="utf-8")
        print(f"wrote {OUT.relative_to(ROOT)}")
        return 0
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != text:
            print("FAIL: mcp-resources.json is stale; run generate-mcp-resources.py --write")
            return 1
        print("OK: MCP resources are current")
        return 0
    print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
