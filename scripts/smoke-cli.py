#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
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


def text_check(label: str, args: list[str], *needles: str):
    """Exit 0, with every needle in the output."""
    def check() -> list[str]:
        out = run(args)
        if out.returncode == 0 and all(needle in out.stdout for needle in needles):
            return []
        return [f"{label} failed:\n{out.stdout}"]
    return check


def json_check(label: str, args: list[str], accept, wrong: str):
    """Output that parses as JSON and that `accept` takes; `wrong` names
    what was expected, with the payload in place of `{payload}`."""
    def check() -> list[str]:
        out = run(args)
        try:
            payload = json.loads(out.stdout)
        except json.JSONDecodeError as exc:
            return [f"{label} invalid: {exc}\n{out.stdout}"]
        return [] if accept(payload) else [wrong.format(payload=payload)]
    return check


def must_fail(label: str, args: list[str]):
    def check() -> list[str]:
        return [label] if run(args).returncode == 0 else []
    return check


def checks(skill_count: int) -> list:
    """Every smoke check, in the order it runs and reports."""
    n = skill_count
    return [
        text_check("list skills", ["list"], "general/cross-language-port"),
        text_check("list commands", ["list", "commands"], "command/agtmls"),
        text_check("search yaml", ["search", "yaml"], "yaml-domain-reference"),
        text_check("show skill", ["show", "cross-language-port"], "skill: cross-language-port"),
        json_check("show command JSON", ["show", "agtmls", "--json"],
                   lambda p: p.get("entry_type") == "command" and p.get("name") == "agtmls",
                   "show command JSON wrong payload: {payload}"),
        text_check("stats", ["stats"], f"skills: {n}", f"routing coverage: {n}/{n}"),
        json_check("stats JSON", ["stats", "--json"],
                   lambda p: p.get("skills") == n and p.get("coverage", {}).get("behavioral", {}).get("covered") == n,
                   "stats JSON wrong payload: {payload}"),
        text_check("profiles", ["profiles"], "noyalib", "polyglot"),
        text_check("providers", ["providers"], "native/codex", "export/openai"),
        text_check("audit", ["audit", "--all", "--strict"], "Zero security or steganography findings detected"),
        json_check("diff JSON", ["diff", "--from", "index.json", "--to", "index.json", "--json"],
                   lambda p: p == {"added": [], "changed": [], "removed": []},
                   "diff against self should be empty: {payload}"),
        must_fail("show missing entry should fail", ["show", "does-not-exist"]),
        json_check("search JSON", ["search", "yaml", "--json"],
                   lambda p: any(item.get("name") == "yaml-domain-reference" for item in p),
                   "search JSON missing yaml-domain-reference: {payload}"),
    ]


def main() -> int:
    index = json.loads((ROOT / "index.json").read_text(encoding="utf-8"))
    errors = [error for check in checks(index["skill_count"]) for error in check()]
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
