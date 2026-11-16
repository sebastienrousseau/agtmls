# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""The repository is offered under one licence expression, everywhere.

`pyproject.toml` states it. Every other place a licence is written down
has to agree: SPDX headers, skill frontmatter, plugin manifests, the
index, CITATION.cff and the SBOMs. A label that says `MIT` alone tells a
reader they may not rely on the Apache-2.0 grant, so a single drift is a
failure, not a warning.
"""

from __future__ import annotations

import re

from .validator_harness import BrokenTreeCase

EXPRESSION = "Apache-2.0 OR MIT"
SCRIPT = "validate-licence-consistency.py"


class ConsistencyTests(BrokenTreeCase):
    """Structured licence labels agree with pyproject.toml."""

    def test_the_registry_as_committed_is_consistent(self) -> None:
        self.assert_clean(SCRIPT)

    def test_a_plugin_manifest_that_says_mit_is_refused(self) -> None:
        self.edit_json(".claude-plugin/plugin.json", lambda d: d.update(license="MIT"))
        self.assert_fails(
            SCRIPT,
            f"FAIL: .claude-plugin/plugin.json: license is 'MIT', not '{EXPRESSION}'",
        )

    def test_an_index_entry_that_says_mit_is_refused(self) -> None:
        def mutate(data: dict) -> None:
            data["skills"][0]["license"] = "MIT"

        self.edit_json("index.json", mutate)
        self.assert_fails(SCRIPT, "FAIL: index.json: skills[0].license is 'MIT'")

    def test_an_sbom_package_that_says_apache_only_is_refused(self) -> None:
        path = self.restore_later("SBOM.spdx.json")
        text = path.read_text(encoding="utf-8")
        path.write_text(
            text.replace(f'"licenseDeclared": "{EXPRESSION}"', '"licenseDeclared": "Apache-2.0"', 1),
            encoding="utf-8",
        )
        self.assert_fails(SCRIPT, "FAIL: SBOM.spdx.json:", "licenseDeclared is 'Apache-2.0'")

    def test_the_spdx_document_data_licence_is_not_a_project_label(self) -> None:
        """SPDX requires CC0-1.0 for the document's own data; it says nothing about ours."""
        output = self.assert_clean(SCRIPT)
        self.assertNotIn("CC0-1.0", output)

    def test_citation_that_says_mit_is_refused(self) -> None:
        path = self.restore_later("CITATION.cff")
        text = path.read_text(encoding="utf-8")
        path.write_text(re.sub(r"(?m)^license:.*$", "license: MIT", text), encoding="utf-8")
        self.assert_fails(SCRIPT, "FAIL: CITATION.cff: license is 'MIT'")

    def test_recorded_evidence_is_left_as_recorded(self) -> None:
        """Agent transcripts quote what a fixture said at the time; they are records, not labels."""
        self.overwrite("docs/evidence/old-run.json", '{"license": "MIT"}\n')
        self.assert_clean(SCRIPT)

    def test_a_pyproject_without_a_licence_is_refused(self) -> None:
        path = self.restore_later("pyproject.toml")
        text = path.read_text(encoding="utf-8")
        path.write_text(re.sub(r'(?m)^license = ".*"$', "", text), encoding="utf-8")
        self.assert_fails(SCRIPT, "FAIL: pyproject.toml: no `license = \"...\"` expression")


class HeaderExpressionTests(BrokenTreeCase):
    """SPDX headers and frontmatter declare the project's expression, nothing narrower."""

    HEADERS = "validate-licence-headers.py"

    def test_an_mit_only_header_is_refused(self) -> None:
        self.overwrite("scripts/mit_only.py", "# SPDX-License-Identifier: MIT\nx = 1\n")
        self.assert_fails(
            self.HEADERS,
            f"FAIL: scripts/mit_only.py: declares MIT, not the project's {EXPRESSION}",
        )

    def test_the_reversed_order_is_refused(self) -> None:
        """One spelling everywhere, so a grep for the expression finds every file."""
        self.overwrite("docs/reversed.md", "<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->\n\n# R\n")
        self.assert_fails(self.HEADERS, "FAIL: docs/reversed.md: declares MIT OR Apache-2.0")

    def test_skill_frontmatter_that_says_mit_is_refused(self) -> None:
        path = self.restore_later("skills/handoff/SKILL.md")
        text = path.read_text(encoding="utf-8")
        path.write_text(re.sub(r"(?m)^license:.*$", "license: MIT", text, count=1), encoding="utf-8")
        self.assert_fails(
            self.HEADERS,
            f"FAIL: skills/handoff/SKILL.md: frontmatter declares MIT, not the project's {EXPRESSION}",
        )

    def test_a_workflow_header_is_checked(self) -> None:
        self.overwrite(".github/workflows/mit.yml", "# SPDX-License-Identifier: MIT\nname: x\n")
        self.assert_fails(self.HEADERS, "FAIL: .github/workflows/mit.yml: declares MIT")
