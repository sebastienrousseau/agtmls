#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Static security, steganography, and prompt injection analyzer for AgtMLS skills."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"

# Hidden Unicode steganography and bidirectional control characters
INVISIBLE_UNICODE = {
    "\u200b": "Zero-width space (U+200B)",
    "\u200c": "Zero-width non-joiner (U+200C)",
    "\u200d": "Zero-width joiner (U+200D)",
    "\u2060": "Word joiner (U+2060)",
    "\ufeff": "Zero-width no-break space (U+FEFF)",
    "\u202a": "Left-to-right embedding (U+202A)",
    "\u202b": "Right-to-left embedding (U+202B)",
    "\u202c": "Pop directional formatting (U+202C)",
    "\u202d": "Left-to-right override (U+202D)",
    "\u202e": "Right-to-left override (U+202E)",
    "\u2066": "Left-to-right isolate (U+2066)",
    "\u2067": "Right-to-left isolate (U+2067)",
    "\u2068": "First strong isolate (U+2068)",
    "\u2069": "Pop directional isolate (U+2069)",
}

# Prompt injection and jailbreak patterns
PROMPT_INJECTION_PATTERNS = [
    (
        re.compile(r"\bignore\s+(?:all\s+)?(?:previous|prior)\s+(?:instructions|rules|prompts|directions)\b", re.IGNORECASE),
        "Instruction override pattern ('ignore previous instructions')",
    ),
    (
        re.compile(r"\bdisregard\s+(?:all\s+)?(?:previous|prior)\s+(?:instructions|rules|prompts|guidelines)\b", re.IGNORECASE),
        "Instruction override pattern ('disregard prior rules')",
    ),
    (
        re.compile(r"\byou\s+are\s+now\s+in\s+developer\s+mode\b", re.IGNORECASE),
        "Persona jailbreak ('developer mode')",
    ),
    (
        re.compile(r"\b(?:system\s+override|jailbreak\s+mode|dan\s+mode)\b", re.IGNORECASE),
        "System override / DAN jailbreak attempt",
    ),
    (
        re.compile(r"\bbypass\s+(?:all\s+)?(?:safety|security|guardrails|filters)\b", re.IGNORECASE),
        "Safety guardrail bypass attempt",
    ),
    (
        re.compile(r"\bdo\s+anything\s+now\b", re.IGNORECASE),
        "DAN exploit pattern ('do anything now')",
    ),
]

# Dangerous shell commands and unauthorized privilege escalation patterns
DANGEROUS_SHELL_PATTERNS = [
    (
        re.compile(r"(?:curl|wget)\s+[^|\n]+(?:\|\s*(?:ba|z)?sh|\|\s*python)", re.IGNORECASE),
        "Unsafe pipe-to-shell download execution (curl|bash)",
    ),
    (
        re.compile(r"\brm\s+-[a-z]*r[a-z]*f\s+/(?:\s|$|\*)", re.IGNORECASE),
        "Destructive recursive deletion of filesystem root (rm -rf /)",
    ),
    (
        re.compile(r"(?:cat|head|tail|cp|curl|scp)\s+.*(?:~/\.ssh|~/\.aws|~/\.gnupg|/etc/shadow|/etc/passwd)\b", re.IGNORECASE),
        "Attempt to read or exfiltrate private credentials (~/.ssh, ~/.aws, /etc/shadow)",
    ),
    (
        re.compile(r"(?:nc\s+-[a-z]*e\b|/dev/tcp/\d|/dev/udp/\d)", re.IGNORECASE),
        "Reverse shell or raw network socket manipulation",
    ),
]

# Data exfiltration patterns in markdown
DATA_EXFILTRATION_PATTERNS = [
    (
        re.compile(r"!\[.*?\]\((https?://[^)]*(?:\$|`|webhook|canarytokens|burpcollaborator|requestbin)[^)]*)\)", re.IGNORECASE),
        "Potential markdown image data exfiltration pingback",
    ),
]


class Finding(NamedTuple):
    file_path: Path
    line: int
    severity: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    category: str
    message: str


def check_steganography(path: Path, content: str) -> list[Finding]:
    findings: list[Finding] = []
    lines = content.splitlines()
    for line_idx, line in enumerate(lines, start=1):
        for char_idx, char in enumerate(line):
            if char in INVISIBLE_UNICODE:
                desc = INVISIBLE_UNICODE[char]
                findings.append(
                    Finding(
                        file_path=path,
                        line=line_idx,
                        severity="CRITICAL",
                        category="steganography",
                        message=f"Invisible unicode character detected: {desc} at column {char_idx + 1}",
                    )
                )
            code_pt = ord(char)
            # Unicode Tag characters (U+E0000 - U+E007F) used for covert channels
            if 0xE0000 <= code_pt <= 0xE007F:
                findings.append(
                    Finding(
                        file_path=path,
                        line=line_idx,
                        severity="CRITICAL",
                        category="steganography",
                        message=f"Covert tag character detected: U+{code_pt:04X} at column {char_idx + 1}",
                    )
                )
    return findings


def check_prompt_injection(path: Path, content: str) -> list[Finding]:
    findings: list[Finding] = []
    lines = content.splitlines()
    for line_idx, line in enumerate(lines, start=1):
        for pattern, desc in PROMPT_INJECTION_PATTERNS:
            if pattern.search(line):
                findings.append(
                    Finding(
                        file_path=path,
                        line=line_idx,
                        severity="HIGH",
                        category="prompt_injection",
                        message=desc,
                    )
                )
    return findings


def check_dangerous_shell(path: Path, content: str) -> list[Finding]:
    findings: list[Finding] = []
    lines = content.splitlines()
    for line_idx, line in enumerate(lines, start=1):
        for pattern, desc in DANGEROUS_SHELL_PATTERNS:
            if pattern.search(line):
                findings.append(
                    Finding(
                        file_path=path,
                        line=line_idx,
                        severity="HIGH",
                        category="unsafe_execution",
                        message=desc,
                    )
                )
    return findings


def check_data_exfiltration(path: Path, content: str) -> list[Finding]:
    findings: list[Finding] = []
    lines = content.splitlines()
    for line_idx, line in enumerate(lines, start=1):
        for pattern, desc in DATA_EXFILTRATION_PATTERNS:
            if pattern.search(line):
                findings.append(
                    Finding(
                        file_path=path,
                        line=line_idx,
                        severity="HIGH",
                        category="data_exfiltration",
                        message=desc,
                    )
                )
    return findings


def check_skill_honesty(skill_dir: Path) -> list[Finding]:
    findings: list[Finding] = []
    skill_md = skill_dir / "SKILL.md"
    metadata_json = skill_dir / "metadata.json"
    if not skill_md.exists() or not metadata_json.exists():
        return findings

    try:
        meta = json.loads(metadata_json.read_text(encoding="utf-8"))
    except Exception:
        return findings

    policy = meta.get("safety_policy", {})
    body = skill_md.read_text(encoding="utf-8", errors="replace")

    if not policy.get("executes_commands", True):
        # Look for explicit active instruction to run shell scripts
        if re.search(r"(?i)\brun\s+(?:the\s+following|this)\s+(?:script|command|bash)", body):
            findings.append(
                Finding(
                    file_path=skill_md,
                    line=1,
                    severity="MEDIUM",
                    category="policy_honesty",
                    message="Skill claims executes_commands=false but text instructs agent to run commands",
                )
            )

    if policy.get("network_access") == "none":
        # Check for instructions to download/fetch external network resources
        if re.search(r"(?i)\b(?:fetch|download|curl|wget)\s+https?://", body):
            findings.append(
                Finding(
                    file_path=skill_md,
                    line=1,
                    severity="MEDIUM",
                    category="policy_honesty",
                    message="Skill claims network_access=none but text contains instructions to fetch URLs",
                )
            )

    return findings


def audit_file(path: Path) -> list[Finding]:
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = path.read_text(encoding="utf-8", errors="replace")
    findings = []
    findings.extend(check_steganography(path, content))
    findings.extend(check_prompt_injection(path, content))
    findings.extend(check_dangerous_shell(path, content))
    findings.extend(check_data_exfiltration(path, content))
    return findings


def audit_skill_target(target: Path) -> list[Finding]:
    findings: list[Finding] = []
    if target.is_file():
        findings.extend(audit_file(target))
    elif target.is_dir():
        for p in sorted(target.rglob("*.md")):
            findings.extend(audit_file(p))
        findings.extend(check_skill_honesty(target))
    return findings


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
                print(f"[{f.severity}] {rel}:{f.line} ({f.category}): {f.message}")
            print(f"\nSummary: {critical_count} critical, {high_count} high, {medium_count} medium, {low_count} low.")
        else:
            print(f"OK: Audited {scanned_count} target(s). Zero security or steganography findings detected.")

    failed = (critical_count > 0 or high_count > 0) or (args.strict and (medium_count > 0 or low_count > 0))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
