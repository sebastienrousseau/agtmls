# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Static security, steganography and prompt-injection analysis of skills.

The detection logic, separated from audit-skill.py's command line so it sits
in the library the 100% coverage floor measures: this is the code the
registry's security claims rest on, and it was the one part of them outside
the floor. The rule data it applies lives in rules.py.
"""

from __future__ import annotations

import json
import re
import stat
import unicodedata
from pathlib import Path
from typing import NamedTuple

from .rules import (
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
    suppressed: str | None = None  # the justification of an in-source suppression


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


def normalize(content: str) -> str:
    """The text as an agent reads it, for every rule but steganography.

    Pipeline: raw -> record invisibles (check_steganography, on the raw text)
    -> strip them -> NFKC -> flatten() -> rules. A keyword split by a
    zero-width space or a tag character, or spelt in fullwidth letters,
    matched no rule while reading as the keyword to a model; the hidden
    bytes were reported as steganography and the instruction went unnamed.
    Newlines survive both steps, so line numbers computed on the result
    still point into the source.
    """
    return unicodedata.normalize("NFKC", INVISIBLE_RE.sub("", content))


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
    text = normalize(content)
    flat = flatten(text)
    findings: list[Finding] = []
    seen: set[tuple[int, str]] = set()
    line_of: list[int] | None = None
    for pattern, rule, desc in patterns:
        for match in pattern.finditer(flat):
            if line_of is None:
                line_of = line_map(text)
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


# A heading under which quoting an attack is teaching, not attacking.
QUOTING_HEADING = re.compile(r"(?i)\b(?:examples?|attacks?|do\s+not|don't)\b")
FENCE = re.compile(r"^\s{0,3}(?:```|~~~)")


def quoted_lines(text: str) -> set[int]:
    """Line numbers inside a fenced block or blockquote under a quoting heading.

    An injection there is the skill showing what it defends against. It is
    still reported, and still fails --strict; it is no longer HIGH.
    """
    quoted: set[int] = set()
    heading_quotes = False
    in_fence = False
    for number, line in enumerate(text.splitlines(), start=1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if not in_fence and line.startswith("#"):
            heading_quotes = bool(QUOTING_HEADING.search(line))
            continue
        if heading_quotes and (in_fence or line.lstrip().startswith(">")):
            quoted.add(number)
    return quoted


def check_prompt_injection(path: Path, content: str) -> list[Finding]:
    findings = scan(path, content, PROMPT_INJECTION_PATTERNS, "HIGH", "prompt_injection")
    if not findings:
        return findings
    quoted = quoted_lines(normalize(content))
    return [
        f._replace(severity="MEDIUM", message=f"{f.message} (quoted under a heading that marks it as an example)")
        if f.line in quoted else f
        for f in findings
    ]


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


# One tool: a name, optionally with a parenthesised specifier that may itself
# contain spaces -- `Bash(git log:*)`.
TOOL_TOKEN = re.compile(r"[^\s,()'\"\[\]]+(?:\([^)]*\))?")


def frontmatter_tools(skill_md: Path) -> list[str]:
    """allowed-tools declared in SKILL.md frontmatter, if any.

    The Agent Skills spec writes the field space-separated, and every skill
    here does: `allowed-tools: "Read Glob Bash"`. This split on commas only,
    so that string came back as a single tool named "Read Glob Bash" that
    granted nothing, and AGT-CAP-001 could not fire on a real skill. Commas
    and YAML list brackets are still accepted.
    """
    text = read_capped(skill_md) or ""
    match = re.match(r"^---[ \t]*\n(.*?)\n---[ \t]*\n", text, re.DOTALL)
    if not match:
        return []
    field = re.search(r"^allowed-tools:[ \t]*(.*)$", match.group(1), re.MULTILINE)
    if not field:
        return []
    return TOOL_TOKEN.findall(field.group(1))


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
        # `Bash(git log:*)` narrows Bash; it still grants executes_commands.
        capability = TOOL_CAPABILITIES.get(tool.split("(", 1)[0])
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
                        f"{capability}; runtimes that pre-approve allowed-tools, "
                        "such as Claude Code, will grant it"
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

    if policy.get("executes_commands") is False and re.search(
        r"(?i)\brun\s+(?:the\s+following|this)\s+(?:script|command|bash)", body
    ):
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

    if policy.get("network_access") == "none" and re.search(
        r"(?i)\b(?:fetch|download|curl|wget)\s+https?://", body
    ):
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
        if SKIP_PARTS & set(path.parts):
            continue
        # One lstat answers "regular file, not a symlink" and "executable"
        # together; a file that vanished since rglob listed it is skipped.
        try:
            mode = path.lstat().st_mode
        except OSError:
            continue
        if not stat.S_ISREG(mode):
            continue
        if path.suffix.lower() in AUDITABLE_SUFFIXES or mode & 0o111:
            yield path


SUPPRESSION = re.compile(r"<!--\s*agtmls-ignore\s+(AGT-[A-Z]+-\d{3})\s*:\s*(\S[^>]*?)\s*-->")
# Hidden bytes and packed payloads are never a matter of judgement.
UNSUPPRESSABLE = ("AGT-STEG-", "AGT-PACK-")


def suppressions(content: str) -> dict[int, dict[str, str]]:
    """Justified suppressions, keyed by the one line each one covers.

    `<!-- agtmls-ignore AGT-INJ-001: quotes the attack for training -->`
    covers the next line only. The reason is required: a comment without
    one is not a suppression, so the finding it meant to hide still fires.
    """
    found: dict[int, dict[str, str]] = {}
    for number, line in enumerate(content.splitlines(), start=1):
        for rule, reason in SUPPRESSION.findall(line):
            found.setdefault(number + 1, {})[rule] = reason
    return found


def apply_suppressions(findings: list[Finding], content: str) -> list[Finding]:
    covered = suppressions(content)
    if not covered:
        return findings
    return [
        f._replace(suppressed=covered[f.line][f.rule])
        if f.rule in covered.get(f.line, {}) and not f.rule.startswith(UNSUPPRESSABLE) else f
        for f in findings
    ]


def audit_file_content(path: Path, content: str) -> list[Finding]:
    """Every detector over one file's text, with in-source suppressions applied."""
    findings: list[Finding] = []
    findings.extend(check_steganography(path, content))
    findings.extend(check_prompt_injection(path, content))
    findings.extend(check_dangerous_shell(path, content))
    findings.extend(check_data_exfiltration(path, content))
    return apply_suppressions(findings, content)


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
    return audit_file_content(path, content)


def audit_skill_target(target: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in auditable_files(target):
        findings.extend(audit_file(path))
    if target.is_dir():
        findings.extend(check_skill_honesty(target))
    return findings
