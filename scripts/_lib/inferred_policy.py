# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""A provisional safety policy for a skill that declares none.

A foreign skill without metadata.json was given `executes_commands: false`
whenever its frontmatter granted no Bash, though its body told the agent to
run `make test`. A report that says "false" there states something nobody
checked. Each capability is now granted by allowed-tools, inferred from
what the skill tells the agent to do, or left "unknown"; never defaulted to
false. The basis of each value is kept, so a reviewer can check it.
"""

from __future__ import annotations

import re
from pathlib import Path

from .findings import read_capped
from .policy import frontmatter_tools
from .rules import TOOL_CAPABILITIES

UNKNOWN = "unknown"
SHELL_FENCE = re.compile(r"^\s*(?:```|~~~)\s*(?:sh|bash|zsh|shell|console|powershell|pwsh|ps1)\b", re.IGNORECASE)
# "run `make test`", "execute `./verify.sh`", "invoke `npm ci`"
RUN_COMMAND = re.compile(r"\b(?:run|execute|invoke)\s+`[^`\n]+`", re.IGNORECASE)
FETCH = re.compile(r"\b(?:curl|wget|git\s+clone|WebFetch|WebSearch|(?:fetch|download)\s+https?://)", re.IGNORECASE)
WRITE = re.compile(r"\b(?:write|create|edit|modify|save|overwrite)\s+(?:the\s+|a\s+|an\s+|each\s+|every\s+)?"
                   r"(?:[\w.-]+\s+)?files?\b", re.IGNORECASE)
SECRET = re.compile(r"\b(?:api[_ -]?keys?|access tokens?|secrets?|credentials?|passwords?)\b|\.env\b", re.IGNORECASE)
SCRIPT_SUFFIXES = {".sh", ".bash", ".zsh", ".ps1", ".py", ".js", ".mjs", ".cjs", ".ts", ".rb", ".pl"}

EVIDENCE = {
    "executes_commands": (SHELL_FENCE, RUN_COMMAND),
    "network_access": (FETCH,),
    "writes_files": (WRITE,),
    "handles_secrets": (SECRET,),
}


def _first_line(text: str, patterns: tuple[re.Pattern[str], ...]) -> int | None:
    for number, line in enumerate(text.splitlines(), start=1):
        if any(p.search(line) for p in patterns):
            return number
    return None


def _shipped_script(skill_dir: Path) -> str | None:
    """A script the skill ships beside SKILL.md: something meant to be run."""
    scripts = sorted(p for p in skill_dir.rglob("*") if p.is_file() and p.suffix.lower() in SCRIPT_SUFFIXES)
    return scripts[0].relative_to(skill_dir).as_posix() if scripts else None


def _granted(skill_md: Path) -> dict[str, str]:
    """Capabilities allowed-tools grants, each with the tool that grants it."""
    granted: dict[str, str] = {}
    for tool in frontmatter_tools(skill_md):
        capability = TOOL_CAPABILITIES.get(tool.split("(", 1)[0])
        if capability is not None:
            granted.setdefault(capability, f"allowed-tools: {tool}")
    return granted


def _bases(skill_dir: Path) -> dict[str, str]:
    """Why each capability is held, for those that are."""
    skill_md = skill_dir / "SKILL.md"
    bases = _granted(skill_md)
    text = read_capped(skill_md) or ""
    for capability, patterns in EVIDENCE.items():
        line = _first_line(text, patterns)
        if line is not None:
            bases.setdefault(capability, f"SKILL.md:{line}")
    script = _shipped_script(skill_dir)
    if script is not None:
        bases.setdefault("executes_commands", f"ships {script}")
    return bases


def provisional_policy(skill_dir: Path) -> dict:
    """True, with its basis, where the skill grants or asks for a capability;
    "unknown" where nothing says either way. Marked provisional, so a report
    never presents it as the author's own claim."""
    bases = _bases(skill_dir)
    network = "optional" if "network_access" in bases else UNKNOWN
    return {
        "executes_commands": "executes_commands" in bases or UNKNOWN,
        "writes_files": "writes_files" in bases or UNKNOWN,
        "network_access": network,
        "handles_secrets": "handles_secrets" in bases or UNKNOWN,
        "provisional": True,
        "basis": dict(sorted(bases.items())),
    }
