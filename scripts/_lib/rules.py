# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Detection data for the skill analyzer.

Separated from audit-skill.py so the analyzer reads as logic and this reads
as a table. The normative definitions live in agtmls-spec/rules/*.toml, and
agtmls-core loads those directly. This module used to restate every pattern
by hand; it now builds its tables from rules.json, the snapshot that
sync-spec-rules.py takes of a pinned spec commit. Never edit rules.json by
hand -- change the spec, then re-sync.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

SNAPSHOT = Path(__file__).with_name("rules.json")
_RULES = json.loads(SNAPSHOT.read_text(encoding="utf-8"))["rules"]
# The whole table, for reporters that describe every rule (SARIF).
RULES = _RULES


def tool_capabilities(rules: list[dict]) -> dict[str, str]:
    """The capability each tool grants, from AGT-CAP-001's data (spec 10.5).

    This module used to carry its own copy, kept in step by hand with the
    Rust implementation's. The spec holds the one table now; a snapshot
    without it is refused rather than guessed at.
    """
    cap = next((rule for rule in rules if rule.get("id") == "AGT-CAP-001"), {})
    table = cap.get("tool_capabilities")
    if not isinstance(table, dict) or not table:
        raise SystemExit("FAIL: the rule snapshot's AGT-CAP-001 has no tool_capabilities table; re-sync from agtmls-spec")
    return dict(table)


TOOL_CAPABILITIES = tool_capabilities(_RULES)




def _by_category(category: str) -> list[tuple[re.Pattern[str], str, str]]:
    """(compiled pattern, rule id, message) for every pattern rule in a category.

    The spec writes case-insensitivity inline as `(?i)`, so the pattern text
    compiles unchanged and means the same thing in Rust and Python.
    """
    return [
        (re.compile(rule["pattern"]), rule["id"], rule["description"])
        for rule in _RULES
        if rule.get("category") == category and "pattern" in rule
    ]


def _code_point(spelling: str) -> str:
    return chr(int(spelling.removeprefix("U+"), 16))


_STEG = next(rule for rule in _RULES if rule["id"] == "AGT-STEG-001")

# Hidden Unicode steganography and bidirectional control characters
INVISIBLE_UNICODE = {
    _code_point(entry["cp"]): f"{entry['name']} ({entry['cp']})" for entry in _STEG["code_points"]
}

# Single pass over every hidden channel, including the ranges the table cannot
# enumerate: variation selectors (the dominant smuggling vector, one nibble per
# code point) and the Unicode tag block.
INVISIBLE_RE = re.compile(
    "["
    + "".join(sorted(INVISIBLE_UNICODE))
    + "".join(
        f"{_code_point(span['from'])}-{_code_point(span['to'])}" for span in _STEG["code_point_ranges"]
    )
    + "]"
)

# Prompt injection and jailbreak patterns
PROMPT_INJECTION_PATTERNS = _by_category("prompt_injection")

# Dangerous shell commands and unauthorized privilege escalation patterns
DANGEROUS_SHELL_PATTERNS = _by_category("unsafe_execution")

# Data exfiltration patterns in markdown
DATA_EXFILTRATION_PATTERNS = _by_category("data_exfiltration")
