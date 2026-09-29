# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""What every detector reports, and how much of a file it will read.

Shared by analyzer.py (the per-file detectors) and policy.py (a skill's
declared safety policy against what it does), so neither imports the other.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

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
