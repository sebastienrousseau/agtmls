#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Static security, steganography, and prompt injection analyzer for AgtMLS skills."""

from __future__ import annotations

import argparse
import hashlib
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
from _lib.cli_parser import registry_version  # noqa: E402  (same path insertion)
from _lib.rules import RULES  # noqa: E402  (same path insertion)

SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
SARIF_LEVEL = {"CRITICAL": "error", "HIGH": "error", "MEDIUM": "warning", "LOW": "note"}
BASELINE_SCHEMA_VERSION = 1


def relative(path: Path) -> str:
    return (path.relative_to(ROOT) if path.is_relative_to(ROOT) else path).as_posix()


def fingerprint(finding: Finding) -> str:
    """Stable across edits elsewhere in the file: no line number in it."""
    key = f"{finding.rule}|{relative(finding.file_path)}|{finding.message}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


def read_baseline(path: Path) -> set[str] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return set(data["fingerprints"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def sarif_log(active: list[Finding], suppressed: list[Finding], baseline: set[str] | None) -> dict:
    """SARIF 2.1.0: one run, every rule described, one result per finding."""
    results = []
    for finding in [*active, *suppressed]:
        location = finding.file_path
        uri = relative(location) if location.is_relative_to(ROOT) else location.resolve().as_uri()
        result: dict = {
            "ruleId": finding.rule,
            "level": SARIF_LEVEL[finding.severity],
            "message": {"text": finding.message},
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {"uri": uri},
                    "region": {"startLine": finding.line},
                }
            }],
            "partialFingerprints": {"agtmls/v1": fingerprint(finding)},
        }
        if finding.suppressed is not None:
            result["suppressions"] = [{"kind": "inSource", "justification": finding.suppressed}]
        if baseline is not None:
            result["baselineState"] = "unchanged" if fingerprint(finding) in baseline else "new"
        results.append(result)
    return {
        "$schema": SARIF_SCHEMA,
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {
                "name": "agtmls",
                "version": registry_version(),
                "informationUri": "https://github.com/sebastienrousseau/agtmls",
                "rules": [{
                    "id": rule["id"],
                    "name": rule.get("title", rule["id"]),
                    "shortDescription": {"text": rule.get("title", rule["id"])},
                    "fullDescription": {"text": rule.get("description", "")},
                    "defaultConfiguration": {"level": SARIF_LEVEL.get(str(rule.get("severity", "")).upper(), "warning")},
                } for rule in RULES],
            }},
            "results": results,
        }],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Static security, steganography, and prompt injection analyzer for AgtMLS skills."
    )
    parser.add_argument("path", nargs="?", type=Path, help="Path to a skill directory or Markdown file")
    parser.add_argument("--all", action="store_true", help="Audit all skills in the registry")
    parser.add_argument("--strict", action="store_true", help="Fail on warnings (MEDIUM/LOW) as well as HIGH/CRITICAL")
    parser.add_argument("--format", choices=["text", "json", "sarif"], default="text", help="Output format")
    parser.add_argument("--baseline", type=Path, help="fingerprints of known findings; only new ones fail the audit")
    parser.add_argument("--write-baseline", type=Path, help="record the fingerprints of this audit's findings")
    args = parser.parse_args()

    if not args.path and not args.all:
        parser.print_help(sys.stderr)
        return 2
    baseline: set[str] | None = None
    if args.baseline:
        baseline = read_baseline(args.baseline)
        if baseline is None:
            print(f"error: cannot read the baseline at {args.baseline}", file=sys.stderr)
            return 2

    targets: list[Path] = []
    if args.all:
        if SKILLS_DIR.exists():
            targets.extend(sorted(d for d in SKILLS_DIR.iterdir() if d.is_dir()))
        agents_dir = ROOT / "agents"
        if agents_dir.exists():
            targets.extend(sorted(p for p in agents_dir.glob("*.md")))
    else:  # a path is present: its absence returned above
        targets.append(args.path.resolve())

    every: list[Finding] = []
    scanned_count = 0
    for target in targets:
        scanned_count += 1
        every.extend(audit_skill_target(target))
    # Suppressed in source: shown, never counted. In the baseline: counted,
    # never failed. Only a new, unsuppressed finding decides the exit code.
    suppressed = [f for f in every if f.suppressed is not None]
    all_findings = [f for f in every if f.suppressed is None]
    known = [f for f in all_findings if baseline is not None and fingerprint(f) in baseline]
    new = [f for f in all_findings if baseline is None or fingerprint(f) not in baseline]
    if args.write_baseline:
        payload = {
            "schema_version": BASELINE_SCHEMA_VERSION,
            "fingerprints": sorted({fingerprint(f) for f in all_findings}),
        }
        args.write_baseline.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    critical_count = sum(1 for f in all_findings if f.severity == "CRITICAL")
    high_count = sum(1 for f in all_findings if f.severity == "HIGH")
    medium_count = sum(1 for f in all_findings if f.severity == "MEDIUM")
    low_count = sum(1 for f in all_findings if f.severity == "LOW")

    def record(f: Finding) -> dict:
        return {
            "file": relative(f.file_path),
            "line": f.line,
            "severity": f.severity,
            "category": f.category,
            "rule": f.rule,
            "message": f.message,
            "fingerprint": fingerprint(f),
            "baseline": baseline is not None and fingerprint(f) in baseline,
        }

    if args.format == "sarif":
        print(json.dumps(sarif_log(all_findings, suppressed, baseline), indent=2))
    elif args.format == "json":
        data = {
            "scanned_targets": scanned_count,
            "findings_count": len(all_findings),
            "critical": critical_count,
            "high": high_count,
            "medium": medium_count,
            "low": low_count,
            "findings": [record(f) for f in all_findings],
            "suppressed": [{**record(f), "justification": f.suppressed} for f in suppressed],
        }
        print(json.dumps(data, indent=2))
    elif all_findings or suppressed:
        print(f"Audited {scanned_count} target(s): found {len(all_findings)} issue(s).\n")
        for f in all_findings:
            mark = " [baseline]" if f in known else ""
            print(f"[{f.severity}] {relative(f.file_path)}:{f.line} ({f.rule} {f.category}): {f.message}{mark}")
        for f in suppressed:
            print(f"[suppressed] {relative(f.file_path)}:{f.line} ({f.rule} {f.category}): {f.message} -- {f.suppressed}")
        print(f"\nSummary: {critical_count} critical, {high_count} high, {medium_count} medium, {low_count} low.")
        if known:
            print(f"{len(known)} finding(s) in the baseline; {len(new)} new.")
        if suppressed:
            print(f"{len(suppressed)} finding(s) suppressed in source.")
    else:
        print(f"OK: Audited {scanned_count} target(s). Zero security or steganography findings detected.")
    failed = any(f.severity in {"CRITICAL", "HIGH"} for f in new) or (
        args.strict and any(f.severity in {"MEDIUM", "LOW"} for f in new)
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
