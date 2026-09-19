# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The authored paths the supply-chain artifacts describe.

One definition, used by both generate-sbom.py and generate-provenance.py.

Both derive their timestamp from the commit that last changed one of these,
which is deterministic and true. The subtlety that matters: this list contains
only **authored** paths. It must never contain a generated artifact.

Provenance originally timestamped itself from its own materials, which include
SBOM.spdx.json. Committing a regenerated SBOM therefore moved provenance's
timestamp, so the pair never settled -- regenerating one invalidated the other.
Timestamping both from authored content instead means one regeneration
converges: committing the generated files cannot move a date derived from
files they are not.
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
    "index.json", "profiles.json", "providers.json",
    "lifecycle.json", "checks.json", "CATALOG.md",
    "LICENSE-APACHE", "LICENSE-MIT",
]

# Generated, therefore excluded from the timestamp basis. Listed so the
# exclusion is explicit rather than implied by absence.
GENERATED = [
    "SBOM.spdx.json", "SBOM.cyclonedx.json", "provenance.json",
    "agent-card.json", "mcp-resources.json", "CATALOG.md",
]
