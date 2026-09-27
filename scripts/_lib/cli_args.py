# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Building the command lines scripts/agtmls.py forwards to its scripts.

A subcommand passes its flags on to the script that does the work; these
turn the parsed arguments into that script's argv, and resolve a path the
caller typed against the caller's directory, since the scripts run from the
registry.
"""

from __future__ import annotations

from pathlib import Path


def option(cmd: list[str], flag: str, value: object) -> None:
    """Forward `flag value` when a value was given."""
    if value:
        cmd.extend([flag, str(value)])


def repeated(cmd: list[str], flag: str, values: list) -> None:
    """Forward `flag value` once per value."""
    for value in values:
        cmd.extend([flag, str(value)])


def switch(cmd: list[str], flag: str, on: bool) -> None:
    """Forward a flag that takes no value."""
    if on:
        cmd.append(flag)


def callers_path(spec: str) -> str:
    """A path the caller typed, made absolute; anything else as given."""
    return str(Path(spec).resolve()) if Path(spec).exists() else spec


def foreign_target(target: str) -> str:
    """A path is the caller's; a URL@sha is passed through as given."""
    if "@" not in target or Path(target).exists():
        return str(Path(target).resolve())
    return target
