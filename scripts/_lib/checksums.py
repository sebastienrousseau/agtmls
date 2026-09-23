# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Read a SHA256SUMS file.

Shared by release-dry-run.py and verify-release-assets.py, which each split
every line in two and so raised ValueError on a blank line -- turning a
checksum audit into a traceback instead of a finding.
"""

from __future__ import annotations

import re

# `sha256sum` writes `<digest>  <name>`, or `<digest> *<name>` in binary mode.
LINE = re.compile(r"^(?P<digest>[0-9a-fA-F]{64}) [ *](?P<name>.+)$")


def parse_sums(text: str) -> tuple[dict[str, str], list[str]]:
    """(name -> digest, problems). Blank lines are skipped, not errors."""
    sums: dict[str, str] = {}
    errors: list[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        match = LINE.match(line)
        if match is None:
            errors.append(f"SHA256SUMS line {number} is not '<sha256>  <file>': {line!r}")
            continue
        sums[match.group("name").strip()] = match.group("digest").lower()
    return sums, errors
