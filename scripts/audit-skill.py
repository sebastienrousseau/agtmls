#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Static security, steganography, and prompt injection analyzer for AgtMLS skills."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
SKILLS_DIR = ROOT / "skills"

# The analyzer itself lives in _lib/analyzer.py, under the core coverage
# floor. Finding and audit_skill_target are what main() needs; the rest are
# re-exported because the unit tests load this script and call them.
from _lib.analyzer import (  # noqa: E402, F401  (needs the scripts path first; re-exported)
    MAX_AUDIT_BYTES,
    Finding,
    audit_file,
    audit_skill_target,
    check_dangerous_shell,
    check_prompt_injection,
    check_steganography,
    flatten,
    line_map,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Static security, steganography, and prompt injection analyzer for AgtMLS skills."
    )
    parser.add_argument("path", nargs="?", type=Path, help="Path to a skill directory or Markdown file")
    parser.add_argument("--all", action="store_true", help="Audit all skills in the registry")
    parser.add_argument("--strict", action="store_true", help="Fail on warnings (MEDIUM/LOW) as well as HIGH/CRITICAL")
    parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    args = parser.parse_args()

    if not args.path and not args.all:
        parser.print_help(sys.stderr)
        return 2

    targets: list[Path] = []
    if args.all:
        if SKILLS_DIR.exists():
            targets.extend(sorted(d for d in SKILLS_DIR.iterdir() if d.is_dir()))
        agents_dir = ROOT / "agents"
        if agents_dir.exists():
            targets.extend(sorted(p for p in agents_dir.glob("*.md")))
    elif args.path:
        targets.append(args.path.resolve())

    all_findings: list[Finding] = []
    scanned_count = 0
    for target in targets:
        scanned_count += 1
        all_findings.extend(audit_skill_target(target))

    critical_count = sum(1 for f in all_findings if f.severity == "CRITICAL")
    high_count = sum(1 for f in all_findings if f.severity == "HIGH")
    medium_count = sum(1 for f in all_findings if f.severity == "MEDIUM")
    low_count = sum(1 for f in all_findings if f.severity == "LOW")

    if args.format == "json":
        data = {
            "scanned_targets": scanned_count,
            "findings_count": len(all_findings),
            "critical": critical_count,
            "high": high_count,
            "medium": medium_count,
            "low": low_count,
            "findings": [
                {
                    "file": str(f.file_path.relative_to(ROOT) if f.file_path.is_relative_to(ROOT) else f.file_path),
                    "line": f.line,
                    "severity": f.severity,
                    "category": f.category,
                    "rule": f.rule,
                    "message": f.message,
                }
                for f in all_findings
            ],
        }
        print(json.dumps(data, indent=2))
    else:
        if all_findings:
            print(f"Audited {scanned_count} target(s): found {len(all_findings)} issue(s).\n")
            for f in all_findings:
                rel = f.file_path.relative_to(ROOT) if f.file_path.is_relative_to(ROOT) else f.file_path
                print(f"[{f.severity}] {rel}:{f.line} ({f.rule} {f.category}): {f.message}")
            print(f"\nSummary: {critical_count} critical, {high_count} high, {medium_count} medium, {low_count} low.")
        else:
            print(f"OK: Audited {scanned_count} target(s). Zero security or steganography findings detected.")

    failed = (critical_count > 0 or high_count > 0) or (args.strict and (medium_count > 0 or low_count > 0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
