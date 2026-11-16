# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The project's licence expression, read from its one source.

`pyproject.toml` states it (`license = "Apache-2.0 OR MIT"`). Everything
that writes a licence label (frontmatter, manifests, the index) takes it
from here, and the consistency check compares every label against it, so
the expression is written down by hand exactly once.

Read with a pattern, not `tomllib`: the floor is Python 3.10, where
`tomllib` does not exist, and the field is a single quoted line.
"""

from __future__ import annotations

import re
from pathlib import Path

LICENSE_LINE = re.compile(r'^license\s*=\s*"([^"]+)"\s*$', re.MULTILINE)


def expression(root: Path) -> str | None:
    """The SPDX expression `root/pyproject.toml` declares, or None."""
    try:
        text = (root / "pyproject.toml").read_text(encoding="utf-8")
    except OSError:
        return None
    match = LICENSE_LINE.search(text)
    return match.group(1) if match else None


def project_expression(root: Path) -> str:
    """The expression, for generators: a missing one is a broken checkout."""
    found = expression(root)
    if found is None:
        raise SystemExit(f"{root / 'pyproject.toml'}: no `license = \"...\"` expression")
    return found
