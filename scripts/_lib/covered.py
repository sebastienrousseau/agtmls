# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The authored paths the supply-chain artifacts describe.

One definition, used by generate-sbom.py. Provenance pins these through the
SBOM's digest.

These lists once also chose which commits dated the artifacts, which is why
authored and generated paths are kept apart. Nothing is dated from git any
more (see `_lib/stamp.py`); the split remains because SBOM_FILES is exactly
the authored files plus the generated ones the wheel ships.
"""

from __future__ import annotations

# Every path force-included into the wheel by pyproject.toml, plus the
# authored JSON at the repository root. Keep in step with
# validate-packaging.py and validate-sbom-conformance.py.
SOURCE_DIRS = [
    "agents", "commands", "evals", "references", "scripts",
    "skills", "src", "system-prompts", "templates",
]
SOURCE_FILES = [
    "profiles.json", "providers.json", "lifecycle.json", "checks.json",
    "LICENSE-APACHE", "LICENSE-MIT",
]

# What the SBOM lists: everything shipped, generated or not. The wheel ships
# index.json, so an SBOM without it describes the wrong artifact.
SBOM_FILES = [*SOURCE_FILES, "index.json", "CATALOG.md"]
