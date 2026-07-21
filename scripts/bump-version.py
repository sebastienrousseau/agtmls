#!/usr/bin/env python3
"""Bump AgtMLS metadata to the next allowed patch-line version."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILES = [
    ROOT / ".claude-plugin" / "plugin.json",
    ROOT / "skills" / "cross-language-port" / "metadata.json",
    ROOT / "skills" / "engineering" / "metadata.json",
    ROOT / "skills" / "loops" / "metadata.json",
    ROOT / "skills" / "noyalib" / "metadata.json",
    ROOT / "skills" / "security" / "metadata.json",
    ROOT / "skills" / "using-agtmls" / "metadata.json",
    ROOT / "skills" / "web-reach" / "metadata.json",
    ROOT / "templates" / "skill" / "metadata.json",
]
TEXT_DEFAULT_FILES = [
    ROOT / "scripts" / "import-skill.py",
    ROOT / "scripts" / "generate-skill-index.py",
]
GENERATORS = [
    ["generate-skill-index.py", "--write"],
    ["generate-catalog.py", "--write"],
    ["generate-docs-site.py", "--write"],
    ["generate-agent-card.py", "--write"],
    ["generate-mcp-resources.py", "--write"],
    ["generate-sbom.py", "--write"],
    ["generate-provenance.py", "--write"],
]


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)


def current_version() -> str:
    return json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))["version"]


def next_version() -> str:
    proc = run([sys.executable, str(ROOT / "scripts" / "next-version.py")])
    if proc.returncode != 0:
        raise SystemExit(proc.stdout)
    return proc.stdout.strip()


def replace_json_version(path: Path, version: str) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = version
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def replace_text_default(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    text = text.replace(f'"{old}"', f'"{new}"')
    path.write_text(text, encoding="utf-8")


def update_changelog(version: str, today: str) -> None:
    path = ROOT / "CHANGELOG.md"
    text = path.read_text(encoding="utf-8")
    heading = f"## {version} - "
    if heading in text:
        return
    marker = "## Unreleased\n"
    if marker not in text:
        raise SystemExit("CHANGELOG.md missing ## Unreleased")
    entry = (
        f"## Unreleased\n\n"
        f"## {version} - {today}\n\n"
        "### Changed\n\n"
        "- Bumped release metadata through the guarded patch-line release flow.\n\n"
    )
    text = text.replace(marker, entry, 1)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", help="target version; defaults to scripts/next-version.py")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--check", action="store_true", help="only validate that the requested version is the next allowed version")
    args = parser.parse_args()

    target = args.version or next_version()
    allowed = next_version()
    if target != allowed:
        print(f"FAIL: requested {target}; next allowed version is {allowed}")
        return 1
    if args.check:
        print(f"OK: bump target {target} is valid")
        return 0

    old = current_version()
    for path in VERSION_FILES:
        replace_json_version(path, target)
    for path in TEXT_DEFAULT_FILES:
        replace_text_default(path, old, target)
    update_changelog(target, args.date)
    for item in GENERATORS:
        proc = run([sys.executable, str(ROOT / "scripts" / item[0]), *item[1:]])
        print(proc.stdout, end="")
        if proc.returncode != 0:
            return proc.returncode
    print(f"OK: bumped AgtMLS from {old} to {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
