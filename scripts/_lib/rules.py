# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Detection data for the skill analyzer.

Separated from audit-skill.py so the analyzer reads as logic and this reads
as a table. The normative definitions live in agtmls-spec/rules/*.toml, and
agtmls-core loads those directly; these are the Python implementation's copy
of the same rule set, kept honest by the differential conformance run.
"""

from __future__ import annotations

import re


# Tools that grant a capability the safety policy may be denying. Kept in step
# with derive_allowed_tools() in sync-skill-frontmatter.py, which is what the
# published frontmatter is generated from.
TOOL_CAPABILITIES = {
    "Bash": "executes_commands",
    "BashOutput": "executes_commands",
    "KillShell": "executes_commands",
    "Write": "writes_files",
    "Edit": "writes_files",
    "NotebookEdit": "writes_files",
    "WebFetch": "network_access",
    "WebSearch": "network_access",
}

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
    "\u00ad": "Soft hyphen (U+00AD)",
    "\u034f": "Combining grapheme joiner (U+034F)",
    "\u061c": "Arabic letter mark (U+061C)",
    "\u115f": "Hangul choseong filler (U+115F)",
    "\u1160": "Hangul jungseong filler (U+1160)",
    "\u17b4": "Khmer vowel inherent AQ (U+17B4)",
    "\u17b5": "Khmer vowel inherent AA (U+17B5)",
    "\u180e": "Mongolian vowel separator (U+180E)",
    "\u200e": "Left-to-right mark (U+200E)",
    "\u200f": "Right-to-left mark (U+200F)",
    "\u2061": "Function application (U+2061)",
    "\u2062": "Invisible times (U+2062)",
    "\u2063": "Invisible separator (U+2063)",
    "\u2064": "Invisible plus (U+2064)",
    "\u3164": "Hangul filler (U+3164)",
    "\uffa0": "Halfwidth hangul filler (U+FFA0)",
}

# Single pass over every hidden channel, including the ranges the table cannot
# enumerate: variation selectors (the dominant smuggling vector, one nibble per
# code point) and the Unicode tag block.
INVISIBLE_RE = re.compile(
    "[" + "".join(sorted(INVISIBLE_UNICODE)) + "]"
    r"|[\ufe00-\ufe0f]"
    r"|[\U000e0000-\U000e007f]"
)

# Prompt injection and jailbreak patterns
PROMPT_INJECTION_PATTERNS = [
    (
        re.compile(r"\bignore\s+(?:all\s+)?(?:previous|prior)\s+(?:instructions|rules|prompts|directions)\b", re.IGNORECASE),
        "AGT-INJ-001",
        "Instruction override pattern ('ignore previous instructions')",
    ),
    (
        re.compile(r"\bdisregard\s+(?:all\s+)?(?:previous|prior)\s+(?:instructions|rules|prompts|guidelines)\b", re.IGNORECASE),
        "AGT-INJ-002",
        "Instruction override pattern ('disregard prior rules')",
    ),
    (
        re.compile(r"\byou\s+are\s+now\s+in\s+developer\s+mode\b", re.IGNORECASE),
        "AGT-INJ-003",
        "Persona jailbreak ('developer mode')",
    ),
    (
        re.compile(r"\b(?:system\s+override|jailbreak\s+mode|dan\s+mode)\b", re.IGNORECASE),
        "AGT-INJ-004",
        "System override / DAN jailbreak attempt",
    ),
    (
        re.compile(r"\bbypass\s+(?:all\s+)?(?:safety|security|guardrails|filters)\b", re.IGNORECASE),
        "AGT-INJ-005",
        "Safety guardrail bypass attempt",
    ),
    (
        re.compile(r"\bdo\s+anything\s+now\b", re.IGNORECASE),
        "AGT-INJ-006",
        "DAN exploit pattern ('do anything now')",
    ),
]

# Dangerous shell commands and unauthorized privilege escalation patterns
DANGEROUS_SHELL_PATTERNS = [
    (
        # Requires an actual fetch target -- a URL or a variable holding one.
        # Matching any `curl ... | bash` flagged prose *warning against* the
        # pattern, which is how a security tool earns a blanket suppression.
        re.compile(r"(?:curl|wget)\s+[^|\n]*(?:https?://|\$\{?[A-Za-z_])[^|\n]*\|\s*(?:(?:ba|z)?sh|python\d?)\b", re.IGNORECASE),
        "AGT-EXEC-001",
        "Unsafe pipe-to-shell download execution (curl|bash)",
    ),
    (
        re.compile(r"\brm\s+-[a-z]*r[a-z]*f\s+/(?:\s|$|\*)", re.IGNORECASE),
        "AGT-EXEC-002",
        "Destructive recursive deletion of filesystem root (rm -rf /)",
    ),
    (
        re.compile(r"(?:cat|head|tail|cp|curl|scp)\s+.*(?:~/\.ssh|~/\.aws|~/\.gnupg|/etc/shadow|/etc/passwd)\b", re.IGNORECASE),
        "AGT-EXEC-003",
        "Attempt to read or exfiltrate private credentials (~/.ssh, ~/.aws, /etc/shadow)",
    ),
    (
        re.compile(r"(?:nc\s+-[a-z]*e\b|/dev/tcp/\d|/dev/udp/\d)", re.IGNORECASE),
        "AGT-EXEC-004",
        "Reverse shell or raw network socket manipulation",
    ),
]

# Data exfiltration patterns in markdown
DATA_EXFILTRATION_PATTERNS = [
    (
        re.compile(r"!\[.*?\]\((https?://[^)]*(?:\$|`|webhook|canarytokens|burpcollaborator|requestbin)[^)]*)\)", re.IGNORECASE),
        "AGT-EXFIL-001",
        "Potential markdown image data exfiltration pingback",
    ),
]
