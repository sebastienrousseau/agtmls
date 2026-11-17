# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The parts of a repository that steer an agent without being a skill.

Hook wiring, harness settings, plugin and MCP manifests, instruction files,
and the install snippets and scripts a reader is told to run. A foreign
audit that reads only skills calls a repository clean while its
`.claude/settings.json` runs a command on every prompt; this module says
which files those are, runs the same detectors over them, and lists every
hook and MCP server they configure, so a reviewer sees what runs before
reading why.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import NamedTuple

from .analyzer import audit_file
from .findings import Finding, read_capped

# Directories whose every file configures an agent or a plugin.
CONFIG_DIRS = {
    ".claude", ".claude-plugin", ".codex", ".codex-plugin", ".cursor", ".cursor-plugin",
    ".gemini", ".opencode", "hooks",
}
# Files that configure an agent wherever they sit.
CONFIG_NAMES = {
    "hooks.json", "settings.json", "settings.local.json", "plugin.json", "marketplace.json",
    ".mcp.json", "mcp.json", "config.toml", "opencode.json", "opencode.jsonc",
    "AGENTS.md", "CLAUDE.md", "GEMINI.md", "copilot-instructions.md",
}
# A script under scripts/ whose name says it installs something.
INSTALL_WORDS = ("install", "setup", "bootstrap", "link")


def is_surface(rel: str) -> bool:
    """Whether a path (relative, POSIX) is part of the agent configuration.

    README files and docs/ are included for the install snippets in them:
    the command a reader pastes runs with their rights, as a hook does.
    """
    parts = rel.split("/")
    name = parts[-1]
    if name in CONFIG_NAMES or CONFIG_DIRS.intersection(parts[:-1]):
        return True
    if len(parts) == 1:
        return name.lower().startswith(("readme", "install"))
    if parts[0] == "docs":
        return True
    return parts[0] == "scripts" and any(word in name.lower() for word in INSTALL_WORDS)


def surfaces(outside: list[str]) -> list[str]:
    """The agent-configuration files among those outside every skill."""
    return sorted(rel for rel in outside if is_surface(rel))


# --- inventory ----------------------------------------------------------

# Events that fire on every prompt, every tool call or every session: a hook
# on one of them with no matcher runs each time.
EVERY_TURN = {"UserPromptSubmit", "PreToolUse", "PostToolUse", "SessionStart", "Stop", "SubagentStop", "Notification"}
URL_HOST = re.compile(r"\bhttps?://([A-Za-z0-9.-]+)")
NETWORK_TOOL = re.compile(r"\b(?:curl|wget|nc|ncat|Invoke-WebRequest|iwr)\b")
# A write (redirect, tee, copy, move, link, delete, mkdir) aimed at the home
# directory or an absolute path: a hook that changes things outside the repo.
WRITE_OUTSIDE = re.compile(
    r"(?:>>?|\btee\b(?:\s+-a)?|\b(?:cp|mv|ln|rm|mkdir|install)\b[^|;&]*?)\s+[\"']?"
    r"(?:~|\$HOME\b|\$\{HOME\}|/(?:etc|usr|opt|Users|home|Library|var|tmp)\b)"
)


def hosts(text: str) -> list[str]:
    """Hosts a command or URL names; "unknown" for a network tool with none."""
    found = sorted({h.lower() for h in URL_HOST.findall(text)})
    if not found and NETWORK_TOOL.search(text):
        return ["unknown"]
    return found


class Hook(NamedTuple):
    file: str
    event: str
    matcher: str | None
    command: str

    @property
    def gated(self) -> bool:
        """A matcher narrows when the hook runs; none, or "*", does not."""
        return self.matcher not in (None, "", "*")

    def record(self) -> dict:
        return {
            "file": self.file, "event": self.event, "matcher": self.matcher,
            "gated": self.gated, "every_turn": self.event in EVERY_TURN and not self.gated,
            "command": self.command, "hosts": hosts(self.command),
            "writes_outside_repo": bool(WRITE_OUTSIDE.search(self.command)),
        }


class Server(NamedTuple):
    file: str
    name: str
    transport: str  # "stdio" or "remote"
    target: str  # the command line, or the URL

    def record(self) -> dict:
        return {"file": self.file, "name": self.name, "transport": self.transport,
                "target": self.target, "hosts": hosts(self.target)}


def _json(path: Path) -> object:
    text = read_capped(path)
    try:
        return json.loads(text) if text is not None else None
    except ValueError:
        return None


def _dicts(value: object) -> list[dict]:
    return [v for v in value if isinstance(v, dict)] if isinstance(value, list) else []


def _hook_command(hook: dict) -> str | None:
    command = hook.get("command")
    return command if isinstance(command, str) else None


def hooks_in(rel: str, data: object) -> list[Hook]:
    """Every command hook a settings, hooks.json or plugin manifest wires."""
    table = data.get("hooks") if isinstance(data, dict) else None
    if not isinstance(table, dict):
        return []
    found: list[Hook] = []
    for event, groups in table.items():
        for group in _dicts(groups):
            matcher = group.get("matcher") if isinstance(group.get("matcher"), str) else None
            commands = [_hook_command(h) for h in _dicts(group.get("hooks"))]
            found.extend(Hook(rel, str(event), matcher, c) for c in commands if c is not None)
    return found


def _command_line(entry: dict) -> str:
    command = entry.get("command")
    parts = command if isinstance(command, list) else [command, *(entry.get("args") or [])]
    return " ".join(str(p) for p in parts if isinstance(p, (str, int, float)))


def _server(rel: str, name: str, entry: dict) -> Server:
    url = entry.get("url") or entry.get("serverUrl")
    if isinstance(url, str):
        return Server(rel, name, "remote", url)
    return Server(rel, name, "stdio", _command_line(entry))


def servers_in(rel: str, data: object) -> list[Server]:
    """MCP servers a .mcp.json, plugin manifest or opencode.json declares."""
    if not isinstance(data, dict):
        return []
    found: list[Server] = []
    for key in ("mcpServers", "mcp"):
        table = data.get(key)
        if isinstance(table, dict):
            found.extend(_server(rel, str(name), entry) for name, entry in table.items() if isinstance(entry, dict))
    return found


TOML_SERVER = re.compile(r"^\[mcp_servers\.\"?([\w.-]+?)\"?\]\s*$")
TOML_STRING = re.compile(r"^(command|url)\s*=\s*\"([^\"]*)\"")
TOML_ARGS = re.compile(r"^args\s*=\s*\[(.*)\]")


def _toml_entries(text: str) -> dict[str, dict]:
    """[mcp_servers.<name>] tables of a Codex config.toml, read line by line:
    tomllib is not in Python 3.10, and only three keys matter here."""
    entries: dict[str, dict] = {}
    current: dict | None = None
    for line in text.splitlines():
        line = line.strip()
        table = TOML_SERVER.match(line)
        if table or line.startswith("["):
            current = entries.setdefault(table.group(1), {}) if table else None
            continue
        if current is None:
            continue
        string, args = TOML_STRING.match(line), TOML_ARGS.match(line)
        if string:
            current[string.group(1)] = string.group(2)
        elif args:
            current["args"] = re.findall(r"\"([^\"]*)\"", args.group(1))
    return entries


def codex_servers(rel: str, text: str) -> list[Server]:
    return [_server(rel, name, entry) for name, entry in _toml_entries(text).items()]


def inventory(root: Path, files: list[str]) -> dict:
    """Every hook and MCP server the configuration files wire up."""
    hook_rows: list[Hook] = []
    server_rows: list[Server] = []
    for rel in files:
        path = root / rel
        if rel.endswith(".toml"):
            server_rows.extend(codex_servers(rel, read_capped(path) or ""))
        elif rel.endswith((".json", ".jsonc")):
            data = _json(path)
            hook_rows.extend(hooks_in(rel, data))
            server_rows.extend(servers_in(rel, data))
    return {"hooks": [h.record() for h in hook_rows], "mcp_servers": [s.record() for s in server_rows]}


class ConfigAudit(NamedTuple):
    files: list[str]
    findings: list[Finding]
    inventory: dict


def audit_config(root: Path, files: list[str], pedantic: bool = False) -> ConfigAudit:
    """The detectors over every configuration file, and its inventory."""
    findings: list[Finding] = []
    for rel in files:
        findings.extend(audit_file(root / rel, pedantic))
    return ConfigAudit(files, findings, inventory(root, files))


# --- what a branch changes -----------------------------------------------

# The paths an agent reads as configuration on its next run, after the
# list claude-code-action restores before it runs on a pull request, plus
# the other agents' equivalents. README and docs are not on it: a changed
# install snippet is reviewed as prose, a changed hook runs unread.
WATCH_DIRS = {".claude", ".codex", ".cursor", ".gemini", ".opencode", ".husky",
              ".claude-plugin", ".codex-plugin", ".cursor-plugin"}
WATCH_NAMES = {".mcp.json", ".claude.json", ".gitmodules", ".ripgreprc", "CLAUDE.md", "CLAUDE.local.md",
               "AGENTS.md", "GEMINI.md", "opencode.json", "opencode.jsonc", "copilot-instructions.md",
               "hooks.json", "plugin.json", "marketplace.json"}


def watched(rel: str) -> bool:
    """Whether a changed path is agent configuration an agent loads unread."""
    parts = rel.split("/")
    return parts[-1] in WATCH_NAMES or bool(WATCH_DIRS.intersection(parts[:-1]))


class ConfigChangeError(RuntimeError):
    """git could not compare the branch with its base."""


def changed_config(root: Path, base: str) -> list[tuple[str, str]]:
    """(status, path) for each watched path changed between `base` and HEAD.

    Compared from the merge base (`base...HEAD`), so a base that moved on
    does not show its own changes as the branch's. A rename is reported
    under its new path.
    """
    argv = ["git", "-C", str(root), "diff", "--name-status", "-M", "--no-color", f"{base}...HEAD", "--"]
    proc = subprocess.run(argv, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise ConfigChangeError(proc.stderr.strip() or f"git diff {base}...HEAD failed")
    changes: list[tuple[str, str]] = []
    for line in proc.stdout.splitlines():
        fields = line.split("\t")
        status, path = fields[0][:1], fields[-1]
        if watched(path):
            changes.append((status, path))
    return changes
