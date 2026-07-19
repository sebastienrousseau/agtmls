#!/usr/bin/env python3
"""Import an external Markdown skill into the AgtMLS draft area."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "imported-skill"


def source_skill_md(source: Path) -> Path:
    if source.is_dir():
        candidate = source / "SKILL.md"
        if candidate.exists():
            return candidate
        markdown = sorted(source.glob("*.md"))
        if markdown:
            return markdown[0]
    if source.is_file():
        return source
    raise SystemExit(f"no Markdown skill found in {source}")


def title_from(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--name")
    parser.add_argument("--bundle", default="imported")
    parser.add_argument("--out-root", type=Path, default=ROOT)
    args = parser.parse_args()
    skill_md = source_skill_md(args.source)
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    name = slugify(args.name or title_from(text, skill_md.stem))
    out_root = args.out_root.resolve()
    target = out_root / "skills" / args.bundle / name
    if target.exists():
        raise SystemExit(f"target skill already exists: {target}")
    target.mkdir(parents=True)
    if args.source.is_dir():
        for item in args.source.iterdir():
            if item.name == "metadata.json":
                continue
            dst = target / ("SKILL.md" if item == skill_md else item.name)
            if item.is_dir():
                shutil.copytree(item, dst)
            elif item.is_file():
                shutil.copy2(item, dst)
    else:
        shutil.copy2(skill_md, target / "SKILL.md")
    if not (target / "reference.md").exists():
        (target / "reference.md").write_text(f"# {name} Reference\n\nImported draft. Review and expand before publication.\n", encoding="utf-8")
    meta = {
        "version": "0.0.1",
        "owner": "unassigned",
        "maturity": "draft",
        "supported_agents": ["claude", "codex", "aider"],
        "required_tools": [],
        "safety_policy": {
            "network_access": "none",
            "writes_files": False,
            "executes_commands": False,
            "handles_secrets": False,
            "requires_human_review": True,
            "risk_level": "low"
        }
    }
    (target / "metadata.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(target.relative_to(out_root).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
