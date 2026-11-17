#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Name and audit the agent configuration a branch changes.

    agtmls audit --changed-agent-config origin/main

Settings, hooks, MCP manifests and instruction files run or steer the
agent on its next session, before anyone has read them; a pull request
that adds a hook to .claude/settings.json changes what every later agent
run does. This lists each such path the branch changes against its base,
audits the ones that still exist with the usual rules and hook and MCP
inventory, and exits 1 whenever there is one, so a CI job can hold the
change for a person to read. Exit 0 when none changed, 2 when git cannot
compare.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _lib.agent_config import ConfigChangeError, audit_config, changed_config  # noqa: E402  (scripts path first)

STATUS = {"A": "added", "M": "modified", "D": "deleted", "R": "renamed", "C": "copied", "T": "type changed"}


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("base", help="the branch or commit to compare HEAD with, e.g. origin/main")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="the repository (default: the current directory)")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    return parser.parse_args(argv)


def relative(root: Path, path) -> str:
    return Path(path).relative_to(root).as_posix()


def json_report(args: argparse.Namespace, changes: list[tuple[str, str]], audit, findings: list) -> None:
    print(json.dumps({
        "base": args.base,
        "changed": [{"status": STATUS.get(s, s), "path": p} for s, p in changes],
        "findings": [{"rule": f.rule, "severity": f.severity, "file": relative(args.root, f.file_path),
                      "line": f.line, "message": f.message} for f in findings],
        "inventory": audit.inventory,
    }, indent=2))


def inventory_lines(inventory: dict) -> list[str]:
    hooks = [f"  hook {h['file']}: {h['event']} "
             f"{'matcher=' + repr(h['matcher']) if h['gated'] else 'UNGATED'}: {h['command']}" for h in inventory["hooks"]]
    servers = [f"  mcp {s['file']}: {s['name']} ({s['transport']}): {s['target']}" for s in inventory["mcp_servers"]]
    return hooks + servers


def text_report(args: argparse.Namespace, changes: list[tuple[str, str]], audit, findings: list) -> None:
    if not changes:
        print(f"OK: no agent configuration changed since {args.base}")
        return
    print(f"Agent configuration changed since {args.base}: {len(changes)} path(s); read each before an agent runs here.")
    lines = [f"  {STATUS.get(status, status)}: {path}" for status, path in changes]
    lines += inventory_lines(audit.inventory)
    lines += [f"  [{f.severity}] {relative(args.root, f.file_path)}:{f.line} ({f.rule}): {f.message}" for f in findings]
    print("\n".join(lines))


def report(args: argparse.Namespace, changes: list[tuple[str, str]]) -> None:
    audit = audit_config(args.root, [path for status, path in changes if status != "D"])
    findings = [f for f in audit.findings if f.suppressed is None]
    (json_report if args.format == "json" else text_report)(args, changes, audit, findings)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    args.root = args.root.resolve()
    try:
        changes = changed_config(args.root, args.base)
    except ConfigChangeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    report(args, changes)
    return 1 if changes else 0


if __name__ == "__main__":
    sys.exit(main())
