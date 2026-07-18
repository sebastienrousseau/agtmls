#!/usr/bin/env python3
"""Validate the AgtMLS plugin manifest."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / ".claude-plugin" / "plugin.json"
REQUIRED = ["name", "version", "description", "author", "license", "homepage", "skills", "commands"]
SEMVER = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def rel_path(value: object) -> Path | None:
    if not isinstance(value, str) or not value.startswith("./") or ".." in Path(value).parts:
        return None
    return ROOT / value


def main() -> int:
    errors: list[str] = []
    if not MANIFEST.exists():
        print("FAIL: .claude-plugin/plugin.json missing")
        return 1
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"FAIL: .claude-plugin/plugin.json invalid JSON: {exc}")
        return 1

    for field in REQUIRED:
        if field not in manifest:
            errors.append(f"plugin manifest missing {field}")
    if manifest.get("name") != "agtmls":
        errors.append("plugin manifest name must be agtmls")
    version = manifest.get("version")
    if not isinstance(version, str) or not SEMVER.match(version):
        errors.append("plugin manifest version must be semver")
    if manifest.get("license") != "MIT":
        errors.append("plugin manifest license must be MIT")
    author = manifest.get("author")
    if not isinstance(author, dict) or not author.get("name"):
        errors.append("plugin manifest author.name is required")
    homepage = manifest.get("homepage")
    if not isinstance(homepage, str) or not homepage.startswith("https://github.com/"):
        errors.append("plugin manifest homepage must be a GitHub HTTPS URL")

    for field in ["skills", "commands"]:
        target = rel_path(manifest.get(field))
        if target is None:
            errors.append(f"plugin manifest {field} must be a safe ./ relative path")
        elif not target.exists():
            errors.append(f"plugin manifest {field} path does not exist: {manifest.get(field)}")
        elif not target.is_dir():
            errors.append(f"plugin manifest {field} path must be a directory: {manifest.get(field)}")

    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8", errors="replace") if (ROOT / "LICENSE").exists() else ""
    if manifest.get("license") == "MIT" and "MIT License" not in license_text:
        errors.append("LICENSE file must contain MIT License text")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} plugin manifest issue(s)")
        return 1
    print("OK: plugin manifest valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
