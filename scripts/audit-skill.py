#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Static security, steganography, and prompt injection analyzer for AgtMLS skills."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from _lib import skill_roots  # noqa: E402  (scripts path first)

SKILLS_DIR = ROOT / "skills"

# The analyzer itself lives in _lib/analyzer.py, under the core coverage
# floor. Finding and audit_skill_target are what main() needs; the rest are
# re-exported because the unit tests load this script and call them.
from _lib import analyzer  # noqa: E402, F401  (the module, for tests that patch it)
from _lib.analyzer import (  # noqa: E402, F401  (needs the scripts path first; re-exported)
    MAX_AUDIT_BYTES,
    Finding,
    ForeignLayoutError,
    audit_file,
    audit_foreign,
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
GIT_TARGET = re.compile(r"^(?P<url>(?:https?|ssh|git)://\S+?|git@\S+?)@(?P<ref>[^@]+)$")
COMMIT_SHA = re.compile(r"^[0-9a-f]{40}$")


def fetch_foreign(target: str, workspace: Path) -> Path | str:
    """A local path as given, or a clone of `<git-url>@<sha>`; a str is the refusal.

    Network fetch is opt-in by giving a URL, and only by exact commit: a
    branch or tag can move between the audit and the install.
    """
    match = GIT_TARGET.match(target)
    if match is None:
        return Path(target).resolve()
    url, ref = match.group("url"), match.group("ref")
    if not COMMIT_SHA.match(ref):
        return f"refusing to fetch {url}@{ref}: give an exact 40-hex commit, not a branch or tag"
    clone = workspace / "foreign"
    for argv in (
        ["git", "clone", "--quiet", url, str(clone)],
        ["git", "-C", str(clone), "checkout", "--quiet", ref],
    ):
        proc = subprocess.run(argv, text=True, capture_output=True, check=False)
        if proc.returncode != 0:
            return f"{' '.join(argv[:2])} failed: {proc.stderr.strip() or proc.stdout.strip()}"
    return clone


def print_coverage(coverage: dict) -> None:
    """What the foreign audit read and what it did not: an unscanned file is
    not a clean one."""
    print("\nCoverage:")
    print(f"  {coverage['skills_audited']} distinct skill(s) audited from {coverage['skills_found']} location(s) "
          f"({coverage['duplicate_copies']} identical copies), {coverage['files_audited']} file(s) read")
    for name, paths in coverage["divergent_copies"].items():
        print(f"  DIVERGENT {name}: copies differ at {', '.join(paths)}")
    if coverage["files_not_audited"]:
        areas = ", ".join(f"{area} ({count})" for area, count in list(coverage["not_audited_by_area"].items())[:6])
        print(f"  NOT AUDITED: {coverage['files_not_audited']} auditable file(s) outside any skill: {areas}")
    for rel in coverage["agent_configs_not_audited"]:
        print(f"  NOT AUDITED agent config: {rel}")
    if coverage["skipped_directories"]:
        skipped = ", ".join(f"{name} ({count})" for name, count in coverage["skipped_directories"].items())
        print(f"  skipped directories: {skipped}")


def fails(findings: list[Finding], strict: bool) -> bool:
    """HIGH or CRITICAL always fails; MEDIUM or LOW only under --strict."""
    return any(f.severity in {"CRITICAL", "HIGH"} for f in findings) or (
        strict and any(f.severity in {"MEDIUM", "LOW"} for f in findings)
    )


def foreign_skill_json(report, root: Path, notes: list[str]) -> dict:
    return {
        "plugin": report.plugin,
        "path": report.path.relative_to(root).as_posix(),
        "digest": report.digest,
        "copies": [c.relative_to(root).as_posix() for c in report.copies],
        "policy": report.policy,
        "findings": [{
            "file": f.file_path.relative_to(root).as_posix(),
            "line": f.line, "severity": f.severity, "category": f.category,
            "rule": f.rule, "message": f.message,
        } for f in report.findings if f.suppressed is None],
        "portability": notes,
    }


def print_foreign_skill(report, root: Path, notes: list[str]) -> None:
    from _lib import portability

    policy = ", ".join(f"{k}={str(v).lower()}" for k, v in report.policy.items() if k != "provisional")
    kind = "provisional policy" if report.policy.get("provisional") else "declared policy"
    print(f"plugin {report.plugin}: {report.path.relative_to(root).as_posix()} ({kind}: {policy})")
    if report.copies:
        print(f"  identical copies: {', '.join(c.relative_to(root).as_posix() for c in report.copies)}")
    for f in report.findings:
        if f.suppressed is None:
            print(f"  [{f.severity}] {f.file_path.relative_to(root).as_posix()}:{f.line} ({f.rule} {f.category}): {f.message}")
    for note in portability.summarize(notes):
        print(f"  portability: {note}")


def foreign_reports(target: str, root: Path, pedantic: bool, fmt: str) -> int | list[Finding]:
    """Audit and print a fetched tree; the unsuppressed findings, or 2 when
    its layout cannot be read."""
    from _lib import portability
    from _lib.analyzer import foreign_coverage, foreign_layout

    try:
        reports = audit_foreign(root, pedantic)
    except ForeignLayoutError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    layout = foreign_layout(root)
    coverage = foreign_coverage(root, reports)
    every = [f for report in reports for f in report.findings if f.suppressed is None]
    # Notes, not findings: a skill that works in one agent only is not a
    # security risk, so portability never changes the exit code.
    notes = {r.path: portability.problems(r.path) for r in reports}
    if fmt == "json":
        print(json.dumps({
            "target": target, "layout": layout, "coverage": coverage,
            "skills": [foreign_skill_json(r, root, notes[r.path]) for r in reports],
        }, indent=2))
        return every
    print(f"Foreign audit of {target} ({layout or 'discovered skills'}): "
          f"{coverage['skills_audited']} distinct skill(s) in {coverage['skills_found']} location(s), "
          f"{len(every)} finding(s)\n")
    for r in reports:
        print_foreign_skill(r, root, notes[r.path])
    print_coverage(coverage)
    return every


def foreign_audit(target: str, fmt: str, strict: bool, pedantic: bool = False) -> int:
    with tempfile.TemporaryDirectory(prefix="agtmls-foreign-") as raw:
        root = fetch_foreign(target, Path(raw))
        if isinstance(root, str):
            print(f"error: {root}", file=sys.stderr)
            return 2
        every = foreign_reports(target, root, pedantic, fmt)
        if isinstance(every, int):
            return every
        return 1 if fails(every, strict) else 0


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


def parse_args() -> tuple[argparse.ArgumentParser, argparse.Namespace]:
    parser = argparse.ArgumentParser(
        description="Static security, steganography, and prompt injection analyzer for AgtMLS skills."
    )
    parser.add_argument("path", nargs="?", type=Path, help="Path to a skill directory or Markdown file")
    parser.add_argument("--all", action="store_true", help="Audit all skills in the registry")
    parser.add_argument("--foreign", metavar="PATH|GIT-URL@SHA", help="Audit every skill in a repository that is not this registry")
    parser.add_argument("--strict", action="store_true", help="Fail on warnings (MEDIUM/LOW) as well as HIGH/CRITICAL")
    parser.add_argument("--pedantic", action="store_true", help="Also report emoji-presentation selectors (AGT-STEG-002, LOW)")
    parser.add_argument("--format", choices=["text", "json", "sarif"], default="text", help="Output format")
    parser.add_argument("--baseline", type=Path, help="fingerprints of known findings; only new ones fail the audit")
    parser.add_argument("--write-baseline", type=Path, help="record the fingerprints of this audit's findings")
    return parser, parser.parse_args()


def audit_targets(args: argparse.Namespace) -> list[Path]:
    if not args.all:
        return [args.path.resolve()]  # a path is present: its absence returned earlier
    targets = list(skill_roots.skill_dirs(ROOT))
    agents_dir = ROOT / "agents"
    if agents_dir.exists():
        targets.extend(sorted(p for p in agents_dir.glob("*.md")))
    return targets


def finding_record(f: Finding, baseline: set[str] | None) -> dict:
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


def severity_counts(findings: list[Finding]) -> dict[str, int]:
    return {level.lower(): sum(1 for f in findings if f.severity == level)
            for level in ("CRITICAL", "HIGH", "MEDIUM", "LOW")}


def print_json_report(scanned: int, active: list[Finding], suppressed: list[Finding], baseline: set[str] | None) -> None:
    counts = severity_counts(active)
    print(json.dumps({
        "scanned_targets": scanned,
        "findings_count": len(active),
        **counts,
        "findings": [finding_record(f, baseline) for f in active],
        "suppressed": [{**finding_record(f, baseline), "justification": f.suppressed} for f in suppressed],
    }, indent=2))


def print_text_report(scanned: int, active: list[Finding], suppressed: list[Finding], known: list[Finding], new: list[Finding]) -> None:
    if not (active or suppressed):
        print(f"OK: Audited {scanned} target(s). Zero security or steganography findings detected.")
        return
    print(f"Audited {scanned} target(s): found {len(active)} issue(s).\n")
    for f in active:
        mark = " [baseline]" if f in known else ""
        print(f"[{f.severity}] {relative(f.file_path)}:{f.line} ({f.rule} {f.category}): {f.message}{mark}")
    for f in suppressed:
        print(f"[suppressed] {relative(f.file_path)}:{f.line} ({f.rule} {f.category}): {f.message} -- {f.suppressed}")
    counts = severity_counts(active)
    print(f"\nSummary: {counts['critical']} critical, {counts['high']} high, {counts['medium']} medium, {counts['low']} low.")
    if known:
        print(f"{len(known)} finding(s) in the baseline; {len(new)} new.")
    if suppressed:
        print(f"{len(suppressed)} finding(s) suppressed in source.")


def write_baseline(path: Path, active: list[Finding]) -> None:
    payload = {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "fingerprints": sorted({fingerprint(f) for f in active}),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def classify(every: list[Finding], baseline: set[str] | None) -> tuple[list, list, list, list]:
    """(suppressed, active, known, new) findings."""
    # Suppressed in source: shown, never counted. In the baseline: counted,
    # never failed. Only a new, unsuppressed finding decides the exit code.
    suppressed = [f for f in every if f.suppressed is not None]
    active = [f for f in every if f.suppressed is None]
    recorded = baseline or set()
    known = [f for f in active if fingerprint(f) in recorded]
    new = [f for f in active if fingerprint(f) not in recorded]
    return suppressed, active, known, new


def load_baseline(path: Path | None) -> tuple[set[str] | None, bool]:
    """(the baseline, whether it could be read); no path is no baseline."""
    if not path:
        return None, True
    baseline = read_baseline(path)
    if baseline is None:
        print(f"error: cannot read the baseline at {path}", file=sys.stderr)
    return baseline, baseline is not None


def report(fmt: str, scanned: int, found: tuple[list, list, list, list], baseline: set[str] | None) -> None:
    suppressed, active, known, new = found
    if fmt == "sarif":
        print(json.dumps(sarif_log(active, suppressed, baseline), indent=2))
    elif fmt == "json":
        print_json_report(scanned, active, suppressed, baseline)
    else:
        print_text_report(scanned, active, suppressed, known, new)


def main() -> int:
    parser, args = parse_args()
    if args.foreign:
        return foreign_audit(args.foreign, "json" if args.format == "json" else "text", args.strict, args.pedantic)
    if not args.path and not args.all:
        parser.print_help(sys.stderr)
        return 2
    baseline, readable = load_baseline(args.baseline)
    if not readable:
        return 2
    targets = audit_targets(args)
    found = classify([f for target in targets for f in audit_skill_target(target, args.pedantic)], baseline)
    if args.write_baseline:
        write_baseline(args.write_baseline, found[1])
    report(args.format, len(targets), found, baseline)
    return 1 if fails(found[3], args.strict) else 0


if __name__ == "__main__":
    sys.exit(main())
