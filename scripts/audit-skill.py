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
sys.path.insert(0, str(ROOT / "scripts"))
SKILLS_DIR = ROOT / "skills"

from _lib.rules import (  # noqa: E402  (needs the scripts path first)
    DANGEROUS_SHELL_PATTERNS,
    DATA_EXFILTRATION_PATTERNS,
    INVISIBLE_RE,
    INVISIBLE_UNICODE,
    PROMPT_INJECTION_PATTERNS,
    TOOL_CAPABILITIES,
)

# Everything an agent may read or a user may execute. Auditing only *.md was
# the gap that mattered: a skill ships harness scripts, examples and configs
# beside SKILL.md, and a malicious verify.sh passed `--all --strict` cleanly
# because the selector never handed it to the detectors.
AUDITABLE_SUFFIXES = {
    ".md", ".markdown", ".txt", ".rst",
    ".sh", ".bash", ".zsh", ".fish", ".ps1",
    ".py", ".js", ".mjs", ".cjs", ".ts", ".rb", ".pl", ".lua",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg",
}
SKIP_PARTS = {"__pycache__", ".git", "node_modules", "target", ".venv"}
# A hostile skill should not be able to exhaust memory during its own audit.
MAX_AUDIT_BYTES = 5 * 1024 * 1024

class Finding(NamedTuple):
    file_path: Path
    line: int
    severity: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    category: str
    message: str
    rule: str = "AGT-UNKNOWN"  # stable id, e.g. AGT-EXEC-001


def describe_invisible(char: str) -> str:
    """Name a hidden code point, falling back to its class."""
    if char in INVISIBLE_UNICODE:
        return INVISIBLE_UNICODE[char]
    code_pt = ord(char)
    if 0xE0000 <= code_pt <= 0xE007F:
        return f"Covert tag character (U+{code_pt:05X})"
    if 0xFE00 <= code_pt <= 0xFE0F:
        return f"Variation selector (U+{code_pt:04X})"
    return f"Invisible or format character (U+{code_pt:04X})"


def check_steganography(path: Path, content: str) -> list[Finding]:
    """Flag code points that render as nothing but survive into the prompt.

    One compiled character class replaces a per-character Python loop: the old
    form cost a dict lookup and an ord() per character of every file, and its
    14-entry table omitted the channels actually in use -- variation selectors
    above all, plus the soft hyphen and the invisible operators.
    """
    findings: list[Finding] = []
    for line_idx, line in enumerate(content.splitlines(), start=1):
        for match in INVISIBLE_RE.finditer(line):
            char = match.group(0)
            findings.append(
                Finding(
                    file_path=path,
                    line=line_idx,
                    severity="CRITICAL",
                    category="steganography",
                    message=(
                        f"Invisible unicode character detected: "
                        f"{describe_invisible(char)} at column {match.start() + 1}"
                    ),
                    rule="AGT-STEG-001",
                )
            )
    return findings


WHITESPACE_RUN = re.compile(r"\s+")


def flatten(content: str) -> str:
    """Collapse whitespace runs to a single space.

    Every detector used to match within a single line, so an attacker split a
    payload across a newline and walked past all of them. Matching the
    whitespace-normalised document closes that.
    """
    return WHITESPACE_RUN.sub(" ", content)


def line_map(content: str) -> list[int]:
    """Source line number for every character of flatten(content).

    Built only once a pattern has matched. Almost every file is clean, and
    walking each character in Python to produce a map nothing reads would
    repeat the mistake this module used to make in check_steganography.
    """
    lines: list[int] = []
    line_no = 1
    prev_space = False
    for char in content:
        if char.isspace():
            if not prev_space:
                lines.append(line_no)
                prev_space = True
        else:
            lines.append(line_no)
            prev_space = False
        if char == "\n":
            line_no += 1
    return lines


def scan(
    path: Path,
    content: str,
    patterns: list[tuple[re.Pattern[str], str, str]],
    severity: str,
    category: str,
) -> list[Finding]:
    flat = flatten(content)
    findings: list[Finding] = []
    seen: set[tuple[int, str]] = set()
    line_of: list[int] | None = None
    for pattern, rule, desc in patterns:
        for match in pattern.finditer(flat):
            if line_of is None:
                line_of = line_map(content)
            line = line_of[match.start()] if match.start() < len(line_of) else 1
            if (line, desc) in seen:
                continue
            seen.add((line, desc))
            findings.append(
                Finding(
                    file_path=path,
                    line=line,
                    severity=severity,
                    category=category,
                    message=desc,
                    rule=rule,
                )
            )
    return findings


def check_prompt_injection(path: Path, content: str) -> list[Finding]:
    return scan(path, content, PROMPT_INJECTION_PATTERNS, "HIGH", "prompt_injection")


def check_dangerous_shell(path: Path, content: str) -> list[Finding]:
    return scan(path, content, DANGEROUS_SHELL_PATTERNS, "HIGH", "unsafe_execution")


def check_data_exfiltration(path: Path, content: str) -> list[Finding]:
    return scan(path, content, DATA_EXFILTRATION_PATTERNS, "HIGH", "data_exfiltration")


def read_capped(path: Path) -> str | None:
    """Read a file, refusing anything large enough to be a resource attack."""
    try:
        if path.stat().st_size > MAX_AUDIT_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def frontmatter_tools(skill_md: Path) -> list[str]:
    """allowed-tools declared in SKILL.md frontmatter, if any."""
    text = read_capped(skill_md) or ""
    match = re.match(r"^---[ \t]*\n(.*?)\n---[ \t]*\n", text, re.DOTALL)
    if not match:
        return []
    field = re.search(r"^allowed-tools:[ \t]*(.*)$", match.group(1), re.MULTILINE)
    if not field:
        return []
    raw = field.group(1).strip().strip("[]")
    return [tool.strip().strip("'\"") for tool in raw.split(",") if tool.strip()]


def load_policy(skill_dir: Path) -> tuple[dict, list[Finding]]:
    """Return (safety_policy, findings).

    Fail closed. A missing or unparseable metadata.json used to return no
    findings at all, so the cheapest way to defeat every policy check was to
    delete the file that declared the policy.
    """
    skill_md = skill_dir / "SKILL.md"
    metadata_json = skill_dir / "metadata.json"

    if not metadata_json.exists():
        return {}, [
            Finding(
                file_path=skill_md if skill_md.exists() else skill_dir,
                line=1,
                severity="HIGH",
                category="policy_honesty",
                message=(
                    "Skill declares no metadata.json, so its safety policy cannot be "
                    "verified; an unattested skill is not a safe skill"
                ),
                rule="AGT-POLICY-001",
            )
        ]
    try:
        meta = json.loads(metadata_json.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {}, [
            Finding(
                file_path=metadata_json,
                line=1,
                severity="HIGH",
                category="policy_honesty",
                message=f"metadata.json is unparseable, so its safety policy cannot be verified: {exc}",
                rule="AGT-POLICY-002",
            )
        ]
    policy = meta.get("safety_policy", {})
    if not isinstance(policy, dict):
        return {}, [
            Finding(
                file_path=metadata_json,
                line=1,
                severity="HIGH",
                category="policy_honesty",
                message="metadata.json safety_policy is not an object",
                rule="AGT-POLICY-003",
            )
        ]
    return policy, []


def check_capability_escalation(skill_dir: Path, policy: dict) -> list[Finding]:
    """Frontmatter must not grant a capability the safety policy denies.

    This is the capability the runtime actually honours: a skill can swear in
    metadata.json that it never shells out while handing the agent Bash in its
    own frontmatter, and nothing checked the two against each other.
    """
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return []
    findings: list[Finding] = []
    for tool in frontmatter_tools(skill_md):
        capability = TOOL_CAPABILITIES.get(tool)
        if capability is None:
            continue
        if capability == "network_access":
            granted = policy.get("network_access") in {"optional", "required"}
        else:
            granted = bool(policy.get(capability))
        if not granted:
            findings.append(
                Finding(
                    file_path=skill_md,
                    line=1,
                    severity="HIGH",
                    category="capability_escalation",
                    message=(
                        f"Frontmatter grants '{tool}' but safety_policy denies "
                        f"{capability}; the runtime honours the frontmatter"
                    ),
                    rule="AGT-CAP-001",
                )
            )
    return findings


def check_skill_honesty(skill_dir: Path) -> list[Finding]:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return []

    policy, findings = load_policy(skill_dir)
    findings.extend(check_capability_escalation(skill_dir, policy))
    body = read_capped(skill_md) or ""

    if policy.get("executes_commands") is False:
        if re.search(r"(?i)\brun\s+(?:the\s+following|this)\s+(?:script|command|bash)", body):
            findings.append(
                Finding(
                    file_path=skill_md,
                    line=1,
                    severity="MEDIUM",
                    category="policy_honesty",
                    message="Skill claims executes_commands=false but text instructs agent to run commands",
                    rule="AGT-POLICY-004",
                )
            )

    if policy.get("network_access") == "none":
        if re.search(r"(?i)\b(?:fetch|download|curl|wget)\s+https?://", body):
            findings.append(
                Finding(
                    file_path=skill_md,
                    line=1,
                    severity="MEDIUM",
                    category="policy_honesty",
                    message="Skill claims network_access=none but text contains instructions to fetch URLs",
                    rule="AGT-POLICY-005",
                )
            )

    return findings


def auditable_files(root: Path):
    """Every file an agent could read or a user could execute.

    Restricting this to *.md was the single highest-impact gap: skills ship
    harness scripts, examples and configs, and none of them were ever handed
    to a detector. Symlinks are skipped rather than followed, so a link out of
    the skill tree cannot drag an unrelated file into the report.
    """
    if root.is_file():
        yield root
        return
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        if SKIP_PARTS & set(path.parts):
            continue
        if path.suffix.lower() in AUDITABLE_SUFFIXES:
            yield path
            continue
        try:  # anything executable, whatever its extension
            if path.stat().st_mode & 0o111:
                yield path
        except OSError:
            continue


def audit_file(path: Path) -> list[Finding]:
    content = read_capped(path)
    if content is None:
        return [
            Finding(
                file_path=path,
                line=1,
                severity="MEDIUM",
                category="unsafe_execution",
                message=f"File skipped: larger than the {MAX_AUDIT_BYTES} byte audit limit or unreadable",
                rule="AGT-SCAN-001",
            )
        ]
    findings = []
    findings.extend(check_steganography(path, content))
    findings.extend(check_prompt_injection(path, content))
    findings.extend(check_dangerous_shell(path, content))
    findings.extend(check_data_exfiltration(path, content))
    return findings


def audit_skill_target(target: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in auditable_files(target):
        findings.extend(audit_file(path))
    if target.is_dir():
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
