#!/usr/bin/env python3
"""Generate a static HTML registry catalog from index/profile/provider metadata."""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site" / "index.html"


def esc(value: object) -> str:
    return html.escape(str(value))


def render() -> str:
    index = json.loads((ROOT / "index.json").read_text(encoding="utf-8"))
    profiles = json.loads((ROOT / "profiles.json").read_text(encoding="utf-8"))["profiles"]
    providers = json.loads((ROOT / "providers.json").read_text(encoding="utf-8"))
    rows = []
    for skill in index["skills"]:
        policy = skill.get("safety_policy", {})
        rows.append(
            "<tr>"
            f"<td><code>{esc(skill['name'])}</code></td>"
            f"<td>{esc(skill.get('bundle') or 'general')}</td>"
            f"<td>{esc(skill.get('quality', {}).get('score', 0))}</td>"
            f"<td>{esc(policy.get('risk_level', 'unknown'))}</td>"
            f"<td>{esc(', '.join(skill.get('supported_agents', [])))}</td>"
            f"<td>{esc(', '.join(skill.get('tags', [])))}</td>"
            f"<td><code>{esc(skill['path'])}</code></td>"
            "</tr>"
        )
    profile_items = "".join(
        f"<li><code>{esc(name)}</code>: {esc(item['description'])}</li>"
        for name, item in sorted(profiles.items())
    )
    provider_items = "".join(
        f"<li><code>{esc(name)}</code>: {esc(item['description'])}</li>"
        for name, item in sorted(providers["export_targets"].items())
    )
    skills = "".join(rows)
    quality = index.get("quality", {}).get("average_score", 0)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AgtMLS Registry Catalog</title>
<style>
body {{ font-family: system-ui, -apple-system, Segoe UI, sans-serif; margin: 0; color: #172026; background: #f7f8fa; }}
header, main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
header {{ border-bottom: 1px solid #d9dee5; background: #ffffff; max-width: none; }}
header > div {{ max-width: 1180px; margin: 0 auto; }}
h1 {{ margin: 0 0 8px; font-size: 32px; }}
.summary {{ display: flex; flex-wrap: wrap; gap: 12px; margin-top: 16px; }}
.summary span {{ background: #e8eef5; border: 1px solid #ccd6e2; padding: 6px 10px; border-radius: 6px; }}
section {{ margin: 28px 0; }}
table {{ width: 100%; border-collapse: collapse; background: #ffffff; border: 1px solid #d9dee5; }}
th, td {{ text-align: left; padding: 10px 12px; border-bottom: 1px solid #e5e9ef; vertical-align: top; }}
th {{ background: #eef2f6; }}
code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.92em; }}
li {{ margin: 8px 0; }}
</style>
</head>
<body>
<header><div>
<h1>AgtMLS Registry Catalog</h1>
<p>Generated from <code>index.json</code>, <code>profiles.json</code>, and <code>providers.json</code>.</p>
<div class="summary">
<span>Version: <code>{esc(index['registry_version'])}</code></span>
<span>Skills: <code>{esc(index['skill_count'])}</code></span>
<span>Commands: <code>{esc(index['command_count'])}</code></span>
<span>Quality: <code>{esc(quality)}</code></span>
<span>Routing: <code>{esc(index['coverage']['routing']['covered'])}/{esc(index['coverage']['routing']['total'])}</code></span>
<span>Behavioral: <code>{esc(index['coverage']['behavioral']['covered'])}/{esc(index['coverage']['behavioral']['total'])}</code></span>
</div>
</div></header>
<main>
<section>
<h2>Skills</h2>
<table>
<thead><tr><th>Name</th><th>Bundle</th><th>Quality</th><th>Risk</th><th>Agents</th><th>Tags</th><th>Path</th></tr></thead>
<tbody>
{skills}
</tbody>
</table>
</section>
<section><h2>Profiles</h2><ul>{profile_items}</ul></section>
<section><h2>Export Targets</h2><ul>{provider_items}</ul></section>
</main>
</body>
</html>
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = render()
    if args.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(rendered, encoding="utf-8")
        print(f"wrote {OUT.relative_to(ROOT)}")
        return 0
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != rendered:
            print("FAIL: site/index.html is missing or stale; run python3 scripts/generate-docs-site.py --write")
            return 1
        print("OK: docs site is current")
        return 0
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
