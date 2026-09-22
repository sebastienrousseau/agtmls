# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""What the benchmark measures.

The definitions, separated from the statistics that consume them, so
adding a workload does not mean reading the percentile code and vice
versa. Each entry is an argv run as its own process; the calibration is a
bare interpreter, which is what every other entry pays before doing any
work of its own.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS = ROOT / "scripts"

# Criterion 3.10, for the surfaces a person waits on.
COLD_START_BUDGET_MS = 100.0
INTERACTIVE = ("cli-list", "cli-search", "cli-show", "cli-stats")


# A bare interpreter: process spawn plus interpreter init, and nothing else.
# Every workload here pays that cost before it does any of its own work, so
# dividing by it isolates what AgtMLS costs from what the machine costs. A CPU
# loop was tried instead and made the ratios worse; see the module docstring.
CALIBRATION_CODE = "pass"

# Content-address every shipped skill: the hot path of `install --verify`
# and of `agtmls verify`.
DIGEST_CODE = (
    "import sys\n"
    f"sys.path.insert(0, {str(SCRIPTS)!r})\n"
    "from _lib.digest import skill_digest\n"
    "from pathlib import Path\n"
    f"root = Path({str(ROOT)!r}) / 'skills'\n"
    "for d in sorted(p for p in root.iterdir() if p.is_dir()):\n"
    "    skill_digest(d)\n"
)

# The router proxy's maths: build TF-IDF vectors for every skill description
# and score one prompt against all of them.
ROUTE_CODE = (
    "import importlib.util, sys\n"
    f"spec = importlib.util.spec_from_file_location('c', {str(SCRIPTS / 'check-skill-collisions.py')!r})\n"
    "m = importlib.util.module_from_spec(spec); sys.modules['c'] = m; spec.loader.exec_module(m)\n"
    "from pathlib import Path\n"
    f"root = Path({str(ROOT)!r}) / 'skills'\n"
    "descs = [m.frontmatter_description(p.read_text(encoding='utf-8'))\n"
    "         for p in sorted(root.glob('**/SKILL.md'))]\n"
    "vecs = m.tfidf([m.vector(d) for d in descs])\n"
    "query = m.tfidf([m.vector('hand this unfinished work over to someone else')])[0]\n"
    "ranked = sorted((m.cosine(query, v) for v in vecs), reverse=True)\n"
)


def workloads() -> dict[str, list[str]]:
    """Name -> argv. Every entry is run as its own process."""
    cli = str(SCRIPTS / "agtmls.py")
    return {
        "calibration": [sys.executable, "-c", CALIBRATION_CODE],
        "cli-list": [sys.executable, cli, "list"],
        "cli-search": [sys.executable, cli, "search", "review"],
        "cli-show": [sys.executable, cli, "show", "handoff"],
        "cli-stats": [sys.executable, cli, "stats"],
        "digest-registry": [sys.executable, "-c", DIGEST_CODE],
        "route-rank": [sys.executable, "-c", ROUTE_CODE],
        "audit-all": [sys.executable, str(SCRIPTS / "audit-skill.py"), "--all", "--strict"],
        "index-check": [sys.executable, str(SCRIPTS / "generate-skill-index.py"), "--check"],
    }
