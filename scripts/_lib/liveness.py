# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Whether an agent can actually read the skills it has been given.

`verify` proves the installed bytes match the lockfile; it cannot see that an
agent skips a skill. Two ways that happened on a real machine: 18 of 20
user-level ~/.claude/skills links pointed at a registry layout that no longer
existed, and Claude Code silently loaded 2 of them. This module checks both
sides:

* user_skill_links: the agent's user-level skill directories, where a broken
  link is invisible to every lockfile check;
* loaded_skills: the skills the agent itself reports, from its own discovery
  (Claude Code's stream-json init event, Codex's rendered prompt input).

Which directories and which probe belong to which agent is data in
providers.json (`user_skills_dirs`, `live_probe`).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import NamedTuple

PROBE_TIMEOUT = 120


class Link(NamedTuple):
    directory: str
    name: str
    target: str
    loadable: bool


class ProbeError(RuntimeError):
    """The agent could not be asked: not installed, timed out, or said nothing."""


def _expand(directory: str, home: Path) -> Path:
    return home / directory[2:] if directory.startswith("~/") else Path(directory)


def user_skill_links(agent: dict, home: Path | None = None) -> list[Link]:
    """Every symlinked skill in the agent's user-level skill directories.

    A link is loadable when it resolves to a directory holding SKILL.md. Real
    directories are the user's own and are not judged; neither are dotfiles
    (Codex keeps its bundled skills in `.system`).
    """
    home = Path.home() if home is None else home
    links: list[Link] = []
    for directory in agent.get("user_skills_dirs", []):
        root = _expand(directory, home)
        if not root.is_dir():
            continue
        for entry in sorted(root.iterdir()):
            if entry.name.startswith(".") or not entry.is_symlink():
                continue
            links.append(Link(directory, entry.name, os.readlink(entry), (entry / "SKILL.md").is_file()))
    return links


def _claude_init(cwd: Path) -> set[str]:
    """Skills from Claude Code's init event.

    The event arrives before the model is called; the process is stopped as
    soon as it has been read, so at most one short request is started.
    """
    argv = ["claude", "-p", "Reply OK.", "--output-format", "stream-json", "--verbose", "--max-turns", "1"]
    with subprocess.Popen(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True) as proc:
        try:
            for line in proc.stdout:  # type: ignore[union-attr]  # stdout is PIPE
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if event.get("type") == "system" and event.get("subtype") == "init":
                    return {s if isinstance(s, str) else str(s.get("name")) for s in event.get("skills", [])}
        finally:
            proc.kill()
    raise ProbeError("claude printed no init event")


_CODEX_ENTRY = re.compile(r"^- (\S+?): .*\(file: r\d+/([^/]+)/SKILL\.md\)", re.MULTILINE)


def _texts(value: object):
    if isinstance(value, dict):
        for item in value.values():
            yield from _texts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _texts(item)
    elif isinstance(value, str):
        yield value


def codex_skill_names(prompt_input: object) -> set[str]:
    """Skill directory names Codex lists in its rendered prompt input.

    Names are taken from the listed SKILL.md path rather than the display
    name, which Codex prefixes with a plugin namespace (`agtmls:<skill>`).
    """
    names: set[str] = set()
    for text in _texts(prompt_input):
        if "<skills_instructions>" in text:
            names.update(directory for _, directory in _CODEX_ENTRY.findall(text))
    return names


def _codex_prompt(cwd: Path) -> set[str]:
    """Codex renders the prompt it would send without calling the model."""
    proc = subprocess.run(["codex", "debug", "prompt-input", "agtmls live check"], cwd=cwd,
                          capture_output=True, text=True, timeout=PROBE_TIMEOUT, check=False)
    if proc.returncode != 0:
        raise ProbeError(f"codex debug prompt-input exited {proc.returncode}")
    try:
        return codex_skill_names(json.loads(proc.stdout))
    except ValueError as exc:
        raise ProbeError("codex debug prompt-input printed no JSON") from exc


PROBES = {"claude-init": ("claude", _claude_init), "codex-prompt-input": ("codex", _codex_prompt)}


def loaded_skills(agent: dict, cwd: Path) -> set[str]:
    """The skills the agent itself reports it can use, run in `cwd`."""
    probe = agent.get("live_probe")
    if probe not in PROBES:
        raise ProbeError("no live check is known for this agent")
    binary, run = PROBES[probe]
    if shutil.which(binary) is None:
        raise ProbeError(f"{binary} is not installed")
    try:
        return run(cwd)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProbeError(f"{binary} could not be run: {exc}") from exc
