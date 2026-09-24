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
    INVISIBLE_RE,
    INVISIBLE_UNICODE,
    RULES,
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
# Which runtimes grant a skill's allowed-tools and which only read them.
PROVIDERS = Path(__file__).resolve().parents[2] / "providers.json"
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


class EmojiContext(NamedTuple):
    """What makes a selector or a tag sequence an emoji rather than a channel.

    Read from AGT-STEG-001's `emoji_context` table (spec 4.10), so both
    implementations draw the line in the same place.
    """

    selectors: tuple[str, str]
    keycap: str
    base_points: frozenset[str]
    base_ranges: tuple[tuple[str, str], ...]
    flag_base: str
    tags: tuple[str, str]
    terminator: str

    def is_selector(self, char: str) -> bool:
        return self.selectors[0] <= char <= self.selectors[1]

    def is_base(self, char: str) -> bool:
        return char in self.base_points or any(low <= char <= high for low, high in self.base_ranges)

    def is_tag(self, char: str) -> bool:
        return self.tags[0] <= char <= self.tags[1]


def _cp(spelling: str) -> str:
    return chr(int(spelling.removeprefix("U+"), 16))


def emoji_context(table: dict) -> EmojiContext | None:
    """The context a rule declares, or None when it declares none.

    Without it every selector and tag character is a channel, which is what
    the rule meant before the table existed.
    """
    try:
        flag = table["subdivision_flag"]
        return EmojiContext(
            selectors=(_cp(table["selectors"]["from"]), _cp(table["selectors"]["to"])),
            keycap=_cp(table["keycap"]),
            base_points=frozenset(_cp(point) for point in table.get("base_points", [])),
            base_ranges=tuple((_cp(r["from"]), _cp(r["to"])) for r in table.get("base_ranges", [])),
            flag_base=_cp(flag["base"]),
            tags=(_cp(flag["tags_from"]), _cp(flag["tags_to"])),
            terminator=_cp(flag["terminator"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


_STEG_RULE = next((rule for rule in RULES if rule.get("id") == "AGT-STEG-001"), {})
EMOJI_CONTEXT = emoji_context(_STEG_RULE.get("emoji_context", {}))


def subdivision_flags(line: str, context: EmojiContext) -> dict[int, int]:
    """Column of each well-formed flag's first tag, mapped to its tag count.

    A flag is exactly the base, one or more tags, then the terminator. Every
    tag character inside one is accounted for by that one finding.
    """
    flags: dict[int, int] = {}
    i = 0
    while i < len(line):
        if line[i] == context.flag_base:
            j = i + 1
            while j < len(line) and context.is_tag(line[j]):
                j += 1
            if j > i + 1 and j < len(line) and line[j] == context.terminator:
                flags[i + 1] = j - i  # tags plus the terminator
                i = j
        i += 1
    return flags


def check_steganography(path: Path, content: str, pedantic: bool = False) -> list[Finding]:
    """Flag code points that render as nothing but survive into the prompt.

    One compiled character class replaces a per-character Python loop: the old
    form cost a dict lookup and an ord() per character of every file, and its
    14-entry table omitted the channels actually in use -- variation selectors
    above all, plus the soft hyphen and the invisible operators.

    With an emoji context (spec 4.10), a selector directly after an emoji
    base is an emoji as written: AGT-STEG-002 at LOW, and only when
    `pedantic`. A well-formed subdivision flag is AGT-STEG-002 at LOW,
    always, once per flag. Everything else stays AGT-STEG-001.
    """
    findings: list[Finding] = []
    context = EMOJI_CONTEXT
    for line_idx, line in enumerate(content.splitlines(), start=1):
        flags = subdivision_flags(line, context) if context else {}
        covered: set[int] = {start + k for start, count in flags.items() for k in range(count)}
        for match in INVISIBLE_RE.finditer(line):
            char = match.group(0)
            column = match.start()
            if context and context.is_selector(char):
                previous = line[column - 1] if column else ""
                following = line[column + 1] if column + 1 < len(line) else ""
                if previous and context.is_base(previous) and not (following and context.is_selector(following)):
                    if pedantic:
                        findings.append(Finding(
                            path, line_idx, "LOW", "steganography",
                            f"{describe_invisible(char)} after an emoji base at column {column + 1}: "
                            "emoji presentation, not a channel",
                            "AGT-STEG-002",
                        ))
                    continue
            if context and column in covered:
                if column in flags:
                    findings.append(Finding(
                        path, line_idx, "LOW", "steganography",
                        f"Tag sequence forming a subdivision flag at column {column + 1} "
                        f"({flags[column] - 1} tag character(s), terminated)",
                        "AGT-STEG-002",
                    ))
                continue
            findings.append(
                Finding(
                    file_path=path,
                    line=line_idx,
                    severity="CRITICAL",
                    category="steganography",
                    message=(
                        f"Invisible unicode character detected: "
                        f"{describe_invisible(char)} at column {column + 1}"
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


class PatternRule(NamedTuple):
    id: str
    category: str
    severity: str
    message: str
    scope: str  # "normalised", "line" or "raw"
    regex: re.Pattern[str]


def compile_rules(rules: list[dict]) -> list[PatternRule]:
    """Every pattern rule in a snapshot, with what it declares.

    Category, severity and scope come from the rule, not from the code that
    runs it, so a rule of a category this module never named still fires --
    which is what the Rust implementation already does, and what the
    differential conformance run compares.
    """
    compiled: list[PatternRule] = []
    for rule in rules:
        pattern = rule.get("pattern")
        if not isinstance(pattern, str):
            continue  # structural: implemented in code, declared in data
        compiled.append(PatternRule(
            id=rule["id"],
            category=rule["category"],
            severity=str(rule.get("severity", "high")).upper(),
            message=rule.get("description") or rule.get("title") or rule["id"],
            scope=rule.get("scope") or "normalised",
            regex=re.compile(pattern),
        ))
    return compiled


PATTERN_RULES = compile_rules(RULES)


def scan_rules(path: Path, content: str, rules: list[PatternRule]) -> list[Finding]:
    """Run pattern rules over one file, each in the scope it declares."""
    findings: list[Finding] = []
    seen: set[tuple[int, str]] = set()
    text = flat = None
    line_of: list[int] | None = None
    for rule in rules:
        if rule.scope == "normalised":
            if flat is None:
                text = normalize(content)
                flat = flatten(text)
            haystack = flat
        else:
            haystack = content
        for match in rule.regex.finditer(haystack):
            if rule.scope == "normalised":
                if line_of is None:
                    line_of = line_map(text or "")
                line = line_of[match.start()] if match.start() < len(line_of) else 1
            else:
                line = content.count("\n", 0, match.start()) + 1
            if (line, rule.message) in seen:
                continue
            seen.add((line, rule.message))
            findings.append(Finding(path, line, rule.severity, rule.category, rule.message, rule.id))
    return findings


def pattern_findings(path: Path, content: str, rules: list[PatternRule] | None = None) -> list[Finding]:
    """Every pattern rule's findings, with quoted injections softened."""
    findings = scan_rules(path, content, PATTERN_RULES if rules is None else rules)
    if not any(f.category == "prompt_injection" for f in findings):
        return findings
    quoted = quoted_lines(normalize(content))
    return [
        f._replace(severity="MEDIUM", message=f"{f.message} (quoted under a heading that marks it as an example)")
        if f.category == "prompt_injection" and f.line in quoted else f
        for f in findings
    ]


def _category(name: str) -> list[PatternRule]:
    return [rule for rule in PATTERN_RULES if rule.category == name]


def check_prompt_injection(path: Path, content: str) -> list[Finding]:
    return pattern_findings(path, content, _category("prompt_injection"))


def check_dangerous_shell(path: Path, content: str) -> list[Finding]:
    return pattern_findings(path, content, _category("unsafe_execution"))


def check_data_exfiltration(path: Path, content: str) -> list[Finding]:
    return pattern_findings(path, content, _category("data_exfiltration"))


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


def allowed_tools_semantics() -> dict[str, list[str]]:
    """Native agents grouped by what allowed-tools means to them.

    From providers.json: `grant` (the runtime pre-approves the tools, as
    Claude Code does), `declaration` (read, granting nothing, as the Agent
    Skills spec defines the field) or `ignored`. Without the table the
    caller falls back to the generic wording.
    """
    try:
        agents = json.loads(PROVIDERS.read_text(encoding="utf-8"))["native_agents"]
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    groups: dict[str, list[str]] = {}
    for name in sorted(agents):
        semantics = agents[name].get("allowed_tools_semantics") if isinstance(agents[name], dict) else None
        if isinstance(semantics, str):
            groups.setdefault(semantics, []).append(name)
    return groups


def escalation_rationale() -> str:
    """Who grants a denied capability, per target, so the finding is about
    effective escalation rather than a claim about every runtime."""
    groups = allowed_tools_semantics()
    if not groups:
        return "runtimes that pre-approve allowed-tools, such as Claude Code, will grant it"
    parts = []
    if groups.get("grant"):
        parts.append(f"runtimes that pre-approve allowed-tools grant it: {', '.join(groups['grant'])}")
    if groups.get("declaration"):
        parts.append(f"these read it as a declaration: {', '.join(groups['declaration'])}")
    if groups.get("ignored"):
        parts.append(f"these ignore it: {', '.join(groups['ignored'])}")
    return "; ".join(parts)


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
    rationale = escalation_rationale()
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
                    message=f"Frontmatter grants '{tool}' but safety_policy denies {capability}; {rationale}",
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


def audit_file_content(path: Path, content: str, pedantic: bool = False) -> list[Finding]:
    """Every detector over one file's text, with in-source suppressions applied."""
    findings: list[Finding] = []
    findings.extend(check_steganography(path, content, pedantic))
    findings.extend(pattern_findings(path, content))
    return apply_suppressions(findings, content)


def audit_file(path: Path, pedantic: bool = False) -> list[Finding]:
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
    return audit_file_content(path, content, pedantic)


class ForeignLayoutError(ValueError):
    """The tree is not something the foreign audit can read as skills."""


# Manifests whose `skills` field names the skill directories, in the order a
# repository is most likely to be one thing rather than another.
PLUGIN_MANIFESTS = (".claude-plugin/plugin.json", ".codex-plugin/plugin.json", ".cursor-plugin/plugin.json")
SKILL_LAYOUTS = (".agents/skills", ".claude/skills", "skills")


def _inside(root: Path, rel: str) -> Path | None:
    """`rel` joined under `root`, or None if it escapes.

    The escape check resolves; the returned path does not, so callers can
    relate it to the root they gave (macOS resolves /var to /private/var).
    """
    candidate = root / rel
    return candidate if candidate.resolve().is_relative_to(root.resolve()) else None


def _skills_under(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(p.parent for p in directory.glob("*/SKILL.md"))


def _manifest_skills(root: Path, manifest: Path, default_name: str) -> list[tuple[str, Path]]:
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    name = str(data.get("name") or default_name)
    declared = data.get("skills") or ["./skills"]
    found: list[tuple[str, Path]] = []
    for rel in declared if isinstance(declared, list) else [declared]:
        directory = _inside(root, str(rel)) if isinstance(rel, str) else None
        if directory is not None:
            found.extend((name, skill) for skill in _skills_under(directory))
    return found


def foreign_layout(root: Path) -> str | None:
    """Which layout a tree follows, or None."""
    if (root / ".claude-plugin" / "marketplace.json").is_file():
        return "claude-marketplace"
    for manifest in PLUGIN_MANIFESTS:
        if (root / manifest).is_file():
            return manifest.split("/")[0].strip(".").replace("-plugin", "-plugin")
    for layout in SKILL_LAYOUTS:
        if _skills_under(root / layout):
            return layout
    return None


def foreign_skills(root: Path) -> list[tuple[str, Path]]:
    """(plugin, skill directory) for every skill a foreign tree ships.

    Detects the layout: a Claude marketplace (each listed plugin's skills),
    a plugin manifest (its `skills` paths), or a skills directory
    (`.agents/skills`, `.claude/skills`, `skills`). A SKILL.md at the root
    is refused: one repository read as one skill audits everything in it as
    prose and calls a whole project a skill, which is what ruflo's root
    SKILL.md did.
    """
    marketplace = root / ".claude-plugin" / "marketplace.json"
    found: list[tuple[str, Path]] = []
    if marketplace.is_file():
        try:
            plugins = json.loads(marketplace.read_text(encoding="utf-8")).get("plugins", [])
        except (OSError, ValueError):
            plugins = []
        for entry in plugins if isinstance(plugins, list) else []:
            if not isinstance(entry, dict) or not isinstance(entry.get("source"), str):
                continue
            plugin_dir = _inside(root, entry["source"])
            if plugin_dir is None:
                continue
            name = str(entry.get("name") or plugin_dir.name)
            manifest = plugin_dir / ".claude-plugin" / "plugin.json"
            if manifest.is_file():
                found.extend(_manifest_skills(plugin_dir, manifest, name))
            else:
                found.extend((name, skill) for skill in _skills_under(plugin_dir / "skills"))
    if not found:
        for manifest in PLUGIN_MANIFESTS:
            if (root / manifest).is_file():
                found.extend(_manifest_skills(root, root / manifest, root.name))
                break
    if not found:
        for layout in SKILL_LAYOUTS:
            skills = _skills_under(root / layout)
            if skills:
                found.extend((layout, skill) for skill in skills)
                break
    if not found:
        if (root / "SKILL.md").is_file():
            raise ForeignLayoutError(
                f"a repository is not a skill: {root} has SKILL.md at its root and no skills directory; "
                "point at the skill directory itself to audit one skill"
            )
        raise ForeignLayoutError(f"no skills found under {root}: expected a marketplace, a plugin manifest, or a skills directory")
    return found


def provisional_policy(skill_dir: Path) -> dict:
    """A safety policy inferred from allowed-tools, for a skill that declares none.

    Any Bash grants executes_commands; Write or Edit grants writes_files;
    WebFetch or WebSearch makes network optional. Marked provisional, so a
    report never presents it as the author's own claim.
    """
    capabilities = {TOOL_CAPABILITIES.get(tool.split("(", 1)[0]) for tool in frontmatter_tools(skill_dir / "SKILL.md")}
    return {
        "executes_commands": "executes_commands" in capabilities,
        "writes_files": "writes_files" in capabilities,
        "network_access": "optional" if "network_access" in capabilities else "none",
        "handles_secrets": False,
        "provisional": True,
    }


class ForeignReport(NamedTuple):
    plugin: str
    path: Path
    policy: dict
    findings: list[Finding]


def audit_foreign(root: Path, pedantic: bool = False) -> list[ForeignReport]:
    """Every skill in a foreign tree, each against its own or a provisional policy."""
    reports: list[ForeignReport] = []
    for plugin, skill_dir in foreign_skills(root):
        findings: list[Finding] = []
        for path in auditable_files(skill_dir):
            findings.extend(audit_file(path, pedantic))
        if (skill_dir / "metadata.json").exists():
            policy, policy_findings = load_policy(skill_dir)
            findings.extend(policy_findings)
            findings.extend(check_skill_honesty(skill_dir))
        else:
            policy = provisional_policy(skill_dir)
            findings.extend(check_capability_escalation(skill_dir, policy))
        reports.append(ForeignReport(plugin, skill_dir, policy, findings))
    return reports


def audit_skill_target(target: Path, pedantic: bool = False) -> list[Finding]:
    findings: list[Finding] = []
    for path in auditable_files(target):
        findings.extend(audit_file(path, pedantic))
    if target.is_dir():
        findings.extend(check_skill_honesty(target))
    return findings
