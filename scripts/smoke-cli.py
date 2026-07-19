#!/usr/bin/env python3
"""Smoke-test the agtmls CLI against index.json."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "scripts" / "agtmls.py"


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


def main() -> int:
    errors: list[str] = []
    index = json.loads((ROOT / "index.json").read_text(encoding="utf-8"))
    skill_count = index["skill_count"]

    list_skills = run(["list"])
    if list_skills.returncode != 0 or "general/cross-language-port" not in list_skills.stdout:
        errors.append(f"list skills failed:\n{list_skills.stdout}")

    list_commands = run(["list", "commands"])
    if list_commands.returncode != 0 or "command/agtmls" not in list_commands.stdout:
        errors.append(f"list commands failed:\n{list_commands.stdout}")

    search = run(["search", "yaml"])
    if search.returncode != 0 or "yaml-domain-reference" not in search.stdout:
        errors.append(f"search yaml failed:\n{search.stdout}")

    show = run(["show", "cross-language-port"])
    if show.returncode != 0 or "skill: cross-language-port" not in show.stdout:
        errors.append(f"show skill failed:\n{show.stdout}")

    show_json = run(["show", "agtmls", "--json"])
    try:
        payload = json.loads(show_json.stdout)
    except json.JSONDecodeError as exc:
        errors.append(f"show command JSON invalid: {exc}\n{show_json.stdout}")
    else:
        if payload.get("entry_type") != "command" or payload.get("name") != "agtmls":
            errors.append(f"show command JSON wrong payload: {payload}")

    stats = run(["stats"])
    if stats.returncode != 0 or f"skills: {skill_count}" not in stats.stdout or f"routing coverage: {skill_count}/{skill_count}" not in stats.stdout:
        errors.append(f"stats failed:\n{stats.stdout}")

    stats_json = run(["stats", "--json"])
    try:
        payload = json.loads(stats_json.stdout)
    except json.JSONDecodeError as exc:
        errors.append(f"stats JSON invalid: {exc}\n{stats_json.stdout}")
    else:
        if payload.get("skills") != skill_count or payload.get("coverage", {}).get("behavioral", {}).get("covered") != skill_count:
            errors.append(f"stats JSON wrong payload: {payload}")


    profiles = run(["profiles"])
    if profiles.returncode != 0 or "noyalib" not in profiles.stdout or "polyglot" not in profiles.stdout:
        errors.append(f"profiles failed:\n{profiles.stdout}")

    providers = run(["providers"])
    if providers.returncode != 0 or "native/codex" not in providers.stdout or "export/openai" not in providers.stdout:
        errors.append(f"providers failed:\n{providers.stdout}")

    diff = run(["diff", "--from", "index.json", "--to", "index.json", "--json"])
    try:
        payload = json.loads(diff.stdout)
    except json.JSONDecodeError as exc:
        errors.append(f"diff JSON invalid: {exc}\n{diff.stdout}")
    else:
        if payload != {"added": [], "changed": [], "removed": []}:
            errors.append(f"diff against self should be empty: {payload}")

    missing = run(["show", "does-not-exist"])
    if missing.returncode == 0:
        errors.append("show missing entry should fail")

    search_json = run(["search", "yaml", "--json"])
    try:
        payload = json.loads(search_json.stdout)
    except json.JSONDecodeError as exc:
        errors.append(f"search JSON invalid: {exc}\n{search_json.stdout}")
    else:
        if not any(item.get("name") == "yaml-domain-reference" for item in payload):
            errors.append(f"search JSON missing yaml-domain-reference: {payload}")

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        print()
        print(f"FAIL: {len(errors)} CLI smoke issue(s)")
        return 1
    print("OK: agtmls CLI smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
