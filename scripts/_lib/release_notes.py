# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""What a release's notes must say, judged the same way before and after.

release-preflight.py reads the prepared notes before the tag is pushed;
release-audit.py reads the published release body afterwards. Both need the
same answer to "is there a user-visible summary, and do the checksums equal
the artifacts?" -- AGENTS.md section 3 -- so it is answered once, here.
"""

from __future__ import annotations

import re

from .checksums import parse_sums


def section(text: str, heading: str) -> str | None:
    """The body of a `## heading` section, or None if there is none."""
    match = re.search(rf"^## {re.escape(heading)}[ \t]*\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    return match.group(1) if match else None


def notes_problems(name: str, text: str, sums: str | None, pending: bool = False) -> list[str]:
    """Everything missing from release notes `text`, called `name` in messages.

    `sums` is the SHA256SUMS text the Checksums section must equal. Without
    it, `pending` accepts a Checksums section that says so -- for a release
    whose artifacts are built only after its tag is pushed.
    """
    errors: list[str] = []
    summary = section(text, "Summary")
    if summary is None or not re.search(r"^- \S", summary, re.MULTILINE):
        errors.append(f"{name}: needs a `## Summary` section of user-visible changes, as bullets")
    checksums = section(text, "Checksums")
    if checksums is None:
        errors.append(f"{name}: needs a `## Checksums` section")
    elif sums is not None:
        expected, problems = parse_sums(sums)
        errors.extend(problems)
        listed, _ = parse_sums(checksums.replace("```", ""))
        if listed != expected:
            errors.append(f"{name}: Checksums section does not equal SHA256SUMS")
    elif not pending:
        errors.append(f"{name}: no SHA256SUMS to check the Checksums section against")
    elif "pending" not in checksums.lower():
        errors.append(f"{name}: pending checksums must be marked `pending` in the Checksums section")
    return errors
