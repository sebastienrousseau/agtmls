# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Whether an agent asks before it runs a tool, from its own settings files.

Every capability check in a skill's safety_policy assumes the user is asked
before a tool runs. An agent configured to run unattended (Claude Code's
bypassPermissions or dontAsk, Codex's approval_policy = "never", Aider's
yes-always) makes that policy advisory. A mode where a safety classifier
approves each call instead of the user (Claude Code's auto) is neither: it
is reported on its own. Where each agent keeps the setting,
and which values mean "unattended", is data in providers.json
(`approval_settings`), so this module only reads files.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import NamedTuple

try:  # 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on 3.10 only
    tomllib = None  # type: ignore[assignment]  # 3.10 falls back to top-level key = value lines

MAX_BYTES = 1024 * 1024


class Setting(NamedTuple):
    path: str
    scope: str
    key: str
    value: object
    unattended: bool
    classified: bool = False


def _resolve(file: str, target: Path, home: Path) -> Path:
    return home / file[2:] if file.startswith("~/") else target / file


def _read(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


_FLAT = re.compile(r"^([A-Za-z0-9_.-]+)\s*[:=]\s*(.*?)\s*(?:#.*)?$")


def flat_top_level(text: str) -> dict[str, object]:
    """`key = value` (TOML) or `key: value` (YAML) lines before any table or
    nesting, which is all these settings need and all 3.10 can read."""
    values: dict[str, object] = {}
    for line in text.splitlines():
        if line.startswith("[") or not line.strip() or line[:1].isspace():
            if line.startswith("["):
                break
            continue
        match = _FLAT.match(line)
        if not match:
            continue
        raw = match.group(2).strip()
        if raw.lower() in {"true", "false"}:
            values[match.group(1)] = raw.lower() == "true"
        else:
            values[match.group(1)] = raw.strip("\"'")
    return values


def _value(text: str, fmt: str, key: str) -> object:
    if fmt == "json":
        try:
            data: object = json.loads(text)
        except ValueError:
            return None
        for part in key.split("."):
            data = data.get(part) if isinstance(data, dict) else None
        return data
    if fmt == "toml" and tomllib is not None:
        try:
            return tomllib.loads(text).get(key)
        except tomllib.TOMLDecodeError:
            return None
    return flat_top_level(text).get(key)


def settings(agent: dict, target: Path, home: Path | None = None) -> list[Setting]:
    """Every approval setting the agent's files declare, most specific first."""
    home = Path.home() if home is None else home
    found: list[Setting] = []
    for entry in agent.get("approval_settings", []):
        path = _resolve(entry["file"], target, home)
        text = _read(path)
        if text is None:
            continue
        value = _value(text, entry["format"], entry["key"])
        if value is None:
            continue
        found.append(Setting(entry["file"], entry["scope"], entry["key"], value, value in entry["unattended"],
                             value in entry.get("classified", [])))
    return found
