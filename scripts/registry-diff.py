#!/usr/bin/env python3
"""Diff two AgtMLS index files."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(spec: str) -> dict[str, object]:
    path = Path(spec)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if ":" in spec:
        proc = subprocess.run(["git", "show", spec], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if proc.returncode != 0:
            raise SystemExit(proc.stderr.strip() or f"cannot read {spec}")
        return json.loads(proc.stdout)
    raise SystemExit(f"index not found: {spec}")


def skill_map(index: dict[str, object]) -> dict[str, dict[str, object]]:
    return {str(skill["name"]): skill for skill in index.get("skills", [])}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="old", required=True)
    parser.add_argument("--to", dest="new", default="index.json")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    old = skill_map(load(args.old))
    new = skill_map(load(args.new))
    added = sorted(set(new) - set(old))
    removed = sorted(set(old) - set(new))
    changed = sorted(name for name in set(old) & set(new) if old[name] != new[name])
    payload = {"added": added, "removed": removed, "changed": changed}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"added: {len(added)}")
        for name in added:
            print(f"  + {name}")
        print(f"removed: {len(removed)}")
        for name in removed:
            print(f"  - {name}")
        print(f"changed: {len(changed)}")
        for name in changed:
            print(f"  * {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
