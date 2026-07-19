#!/usr/bin/env python3
"""Scaffold a new AgtMLS skill from templates."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "templates"
SKILLS = ROOT / "skills"
EVALS = ROOT / "evals"
KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def write_new(path: Path, text: str) -> None:
    if path.exists():
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def render(template: Path, name: str, title: str) -> str:
    return (
        template.read_text(encoding="utf-8")
        .replace("example-skill", name)
        .replace("Example Skill", title)
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("name", help="kebab-case skill name")
    parser.add_argument("--bundle", help="optional project bundle under skills/")
    parser.add_argument("--title", help="human title for the skill heading")
    parser.add_argument("--out-root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if not KEBAB.match(args.name):
        print("FAIL: skill name must be kebab-case", file=sys.stderr)
        return 1
    if args.bundle and not KEBAB.match(args.bundle):
        print("FAIL: bundle must be kebab-case", file=sys.stderr)
        return 1

    out_root = args.out_root.resolve()
    skills_root = out_root / "skills"
    evals_root = out_root / "evals"
    title = args.title or args.name.replace("-", " ").title()
    skill_dir = skills_root / args.bundle / args.name if args.bundle else skills_root / args.name
    if skill_dir.exists():
        print(f"FAIL: skill directory already exists: {skill_dir}", file=sys.stderr)
        return 1

    try:
        write_new(skill_dir / "SKILL.md", render(TEMPLATES / "skill" / "SKILL.md", args.name, title))
        write_new(skill_dir / "reference.md", render(TEMPLATES / "skill" / "reference.md", args.name, title))
        if not args.bundle:
            write_new(skill_dir / "metadata.json", render(TEMPLATES / "skill" / "metadata.json", args.name, title))
        write_new(
            evals_root / "cases" / f"{args.name}.json",
            render(TEMPLATES / "evals" / "routing.json", args.name, title),
        )
        write_new(
            evals_root / "behavioral" / "cases" / f"{args.name}.json",
            render(TEMPLATES / "evals" / "behavioral.json", args.name, title),
        )
    except FileExistsError as exc:
        print(f"FAIL: refusing to overwrite existing file: {Path(exc.filename)}", file=sys.stderr)
        return 1

    print(f"created {skill_dir}")
    print("next: edit the scaffolded descriptions and run python3 scripts/agtmls.py check")
    return 0


if __name__ == "__main__":
    sys.exit(main())
