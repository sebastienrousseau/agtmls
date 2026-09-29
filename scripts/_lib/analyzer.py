# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Static security, steganography and prompt-injection analysis of skills.

The detection logic, separated from audit-skill.py's command line so it sits
in the library the 100% coverage floor measures: this is the code the
registry's security claims rest on, and it was the one part of them outside
the floor. The rule data it applies lives in rules.py.
"""

from __future__ import annotations

import re
import stat
import unicodedata
from pathlib import Path
from typing import NamedTuple

from .findings import MAX_AUDIT_BYTES, Finding, read_capped
from .policy import check_skill_honesty
from .rules import (
    INVISIBLE_RE,
    INVISIBLE_UNICODE,
    RULES,
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


def _flag_length(line: str, start: int, context: EmojiContext) -> int:
    """Tags plus terminator of a well-formed flag whose base is at `start`, or 0."""
    if line[start] != context.flag_base:
        return 0
    end = start + 1
    while end < len(line) and context.is_tag(line[end]):
        end += 1
    well_formed = end > start + 1 and end < len(line) and line[end] == context.terminator
    return end - start if well_formed else 0


def subdivision_flags(line: str, context: EmojiContext) -> dict[int, int]:
    """Column of each well-formed flag's first tag, mapped to its tag count.

    A flag is exactly the base, one or more tags, then the terminator. Every
    tag character inside one is accounted for by that one finding.
    """
    flags: dict[int, int] = {}
    i = 0
    while i < len(line):
        length = _flag_length(line, i, context)
        if length:
            flags[i + 1] = length  # tags plus the terminator
            i += length
        i += 1
    return flags


def _emoji_presentation(context, line: str, column: int) -> bool:
    """A variation selector directly after an emoji base, and not itself
    followed by another selector: an emoji as written."""
    previous = line[column - 1] if column else ""
    following = line[column + 1] if column + 1 < len(line) else ""
    return bool(previous) and context.is_base(previous) and not (following and context.is_selector(following))


def _steg(path: Path, line_idx: int, severity: str, message: str, rule: str) -> Finding:
    return Finding(path, line_idx, severity, "steganography", message, rule)


def _match_finding(path: Path, line_idx: int, line: str, match: re.Match, context, flags: dict[int, int],
                   covered: set[int], pedantic: bool) -> Finding | None:
    """One invisible code point's finding, or None where it is part of an emoji as written."""
    char, column = match.group(0), match.start()
    if context and context.is_selector(char) and _emoji_presentation(context, line, column):
        return _steg(path, line_idx, "LOW", f"{describe_invisible(char)} after an emoji base at column "
                     f"{column + 1}: emoji presentation, not a channel", "AGT-STEG-002") if pedantic else None
    if context and column in covered:
        return _steg(path, line_idx, "LOW", f"Tag sequence forming a subdivision flag at column {column + 1} "
                     f"({flags[column] - 1} tag character(s), terminated)", "AGT-STEG-002") if column in flags else None
    return _steg(path, line_idx, "CRITICAL", "Invisible unicode character detected: "
                 f"{describe_invisible(char)} at column {column + 1}", "AGT-STEG-001")


def _line_steganography(path: Path, line_idx: int, line: str, context, pedantic: bool) -> list[Finding]:
    """One line's invisible code points, judged against the emoji context."""
    flags = subdivision_flags(line, context) if context else {}
    covered: set[int] = {start + k for start, count in flags.items() for k in range(count)}
    found = (_match_finding(path, line_idx, line, m, context, flags, covered, pedantic) for m in INVISIBLE_RE.finditer(line))
    return [finding for finding in found if finding is not None]


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
        findings += _line_steganography(path, line_idx, line, context, pedantic)
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


JSON_ESCAPE = re.compile(r'\\(?:u([0-9a-fA-F]{4})|(["\\/bfnrt]))')
_SIMPLE = {'"': '"', "\\": "\\", "/": "/", "b": " ", "f": " ", "n": " ", "r": " ", "t": " "}


class _EscapeDecoder:
    """Decoded text, holding a high surrogate until its low half arrives."""

    def __init__(self) -> None:
        self.out: list[str] = []
        self.pending_high: int | None = None

    def flush(self) -> None:
        """A high surrogate with no low half becomes U+FFFD."""
        if self.pending_high is not None:
            self.out.append("\ufffd")
            self.pending_high = None

    def code_point(self, code: int) -> None:
        if 0xD800 <= code <= 0xDBFF:
            self.flush()
            self.pending_high = code
        elif 0xDC00 <= code <= 0xDFFF:
            if self.pending_high is None:
                self.out.append("\ufffd")
            else:
                self.out.append(chr(0x10000 + ((self.pending_high - 0xD800) << 10) + (code - 0xDC00)))
                self.pending_high = None
        else:
            self.flush()
            char = chr(code)
            self.out.append(" " if char in "\n\r\u2028\u2029\x85\x0b\x0c" else char)


def decode_json_escapes(content: str) -> str:
    """JSON string escapes decoded, never creating a line (spec 4.3).

    A model reads a tool description decoded, so `Ignore previous\n
    instructions` in a JSON file is the phrase. Escaped whitespace and any
    decoded line terminator become a space, so line numbers still point into
    the source; a surrogate pair is one code point, a lone one U+FFFD.
    """
    decoder = _EscapeDecoder()
    last = 0
    for match in JSON_ESCAPE.finditer(content):
        if match.start() != last:
            decoder.flush()
        decoder.out.append(content[last:match.start()])
        last = match.end()
        if match.group(2) is not None:
            decoder.flush()
            decoder.out.append(_SIMPLE[match.group(2)])
        else:
            decoder.code_point(int(match.group(1), 16))
    decoder.flush()
    decoder.out.append(content[last:])
    return "".join(decoder.out)


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
    applies_to: tuple[str, ...] = ("*",)


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
            applies_to=tuple(rule.get("applies_to") or ("*",)),
        ))
    return compiled


def selector_matches(selector: str, path: Path, content: str) -> bool:
    """One `applies_to` selector against one file (spec 4.11).

    `*`, `*.<ext>` compared case-insensitively, or `executable`: a file whose
    content begins with `#!`. Content, not a mode bit, so in-memory analysis
    decides the same way as a filesystem walk. Any other form matches nothing.
    """
    if selector == "*":
        return True
    if selector == "executable":
        return content.startswith("#!")
    if selector.startswith("*.") and "*" not in selector[1:]:
        return path.name.lower().endswith(selector[1:].lower())
    return False


def applies(rule: PatternRule, path: Path, content: str) -> bool:
    return any(selector_matches(selector, path, content) for selector in rule.applies_to)


PATTERN_RULES = compile_rules(RULES)


class _ScanViews:
    """The file as a rule reads it: raw, or decoded, normalised and
    flattened, each built once and only when a rule needs it."""

    def __init__(self, path: Path, content: str) -> None:
        self.path, self.content = path, content
        self.text: str | None = None
        self.flat: str | None = None
        self.line_of: list[int] | None = None

    def haystack(self, scope: str) -> str:
        if scope != "normalised":
            return self.content
        if self.flat is None:
            source = decode_json_escapes(self.content) if self.path.name.lower().endswith(".json") else self.content
            self.text = normalize(source)
            self.flat = flatten(self.text)
        return self.flat

    def line(self, scope: str, offset: int) -> int:
        """The 1-based source line of an offset into the rule's haystack."""
        if scope != "normalised":
            return self.content.count("\n", 0, offset) + 1
        if self.line_of is None:
            self.line_of = line_map(self.text or "")
        return self.line_of[offset] if offset < len(self.line_of) else 1


def scan_rules(path: Path, content: str, rules: list[PatternRule]) -> list[Finding]:
    """Run pattern rules over one file, each in the scope it declares."""
    findings: list[Finding] = []
    seen: set[tuple[int, str]] = set()
    views = _ScanViews(path, content)
    for rule in rules:
        if not applies(rule, path, content):
            continue
        for match in rule.regex.finditer(views.haystack(rule.scope)):
            line = views.line(rule.scope, match.start())
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
    quoted = quoted_lines(normalize(content))  # escapes do not move lines
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


def has_shebang(path: Path) -> bool:
    """A script with no extension and no execute bit is still a script (spec 4.11)."""
    try:
        with path.open("rb") as handle:
            return handle.read(2) == b"#!"
    except OSError:
        return False


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
        if path.suffix.lower() in AUDITABLE_SUFFIXES or mode & 0o111 or has_shebang(path):
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


def audit_skill_target(target: Path, pedantic: bool = False) -> list[Finding]:
    findings: list[Finding] = []
    for path in auditable_files(target):
        findings.extend(audit_file(path, pedantic))
    if target.is_dir():
        findings.extend(check_skill_honesty(target))
    return findings
