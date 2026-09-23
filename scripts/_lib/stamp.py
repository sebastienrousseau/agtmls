# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The one timestamp a committed supply-chain artifact carries.

It was the date of the newest commit touching the described paths, and
provenance also named that commit. Both are properties of history, not of
content, and a squash merge rewrites history: main receives one new commit,
with a new date and a new hash, on the same tree. Every SBOM regenerated on a
branch was therefore stale the moment it merged, and main's CI failed after
each squash merge (d229411, c4eba07) while the pull request checks passed.

The stamp now records when the described content last changed, and the
artifact itself is the record: `--write` keeps the stamp an artifact already
holds while everything else renders identically, and takes a new one only
when the content moves. `--check` renders with the stamp the file holds, so
the same tree gets the same verdict in any history, or none (an sdist). Git is
not consulted at all.
"""

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

FORMAT = "%Y-%m-%dT%H:%M:%SZ"
PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")

Render = Callable[[str], dict]
Locate = Callable[[dict], object]


def clock() -> float:
    return time.time()


def now() -> str:
    """A new stamp: SOURCE_DATE_EPOCH when a reproducible build pins it."""
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    seconds = int(epoch) if epoch else clock()
    return datetime.fromtimestamp(seconds, tz=timezone.utc).strftime(FORMAT)


def dump(document: dict) -> str:
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def recorded(path: Path, locate: Locate) -> str | None:
    """The stamp `path` already holds, or None when it has no valid one."""
    try:
        value = locate(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        return None
    return value if isinstance(value, str) and PATTERN.fullmatch(value) else None


def current(path: Path, render: Render, locate: Locate) -> bool:
    """Whether `path` is exactly what renders from today's content and its own stamp."""
    stamp = recorded(path, locate)
    return stamp is not None and path.read_text(encoding="utf-8") == dump(render(stamp))


def settle(path: Path, render: Render, locate: Locate) -> str:
    """The text to write: the file's own stamp if nothing else moved, else a new one."""
    if current(path, render, locate):
        return path.read_text(encoding="utf-8")
    return dump(render(now()))
