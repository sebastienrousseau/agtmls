# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""index.json and BENCHMARKS.md: the two documents other generators read.

index.json feeds the catalog, the docs site, the MCP resource list and every
export, so a parsing slip in generate-skill-index.py propagates to all of
them. BENCHMARKS.md states measured numbers, and its generator is the only
thing standing between a re-measurement and prose that no longer matches it.
"""

from __future__ import annotations

import json
import shutil

from .subset_support import SubsetCase


class SkillIndexTests(SubsetCase):
    SCRIPT = "generate-skill-index.py"
    # Two skills, not thirty-one: collect() digests every skill tree, and the
    # behaviour under test does not depend on how many there are.
    SUBSET = (
        "skills/using-agtmls", "skills/incident-response",
        "commands", ".claude-plugin", "index.json",
    )

    def add_skill(self, name: str, text: str, metadata: dict | None = None):
        directory = self.path(f"skills/{name}")
        directory.mkdir()
        self.addCleanup(shutil.rmtree, directory, True)
        (directory / "SKILL.md").write_text(text, encoding="utf-8")
        if metadata is not None:
            (directory / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        return next(s for s in self.script().collect()["skills"] if s["path"] == f"skills/{name}")

    def test_write_then_check_agree_and_print_writes_nothing(self) -> None:
        self.preserve("index.json")
        # The committed index lists every skill; this fixture holds two.
        code, output = self.drive("--check")
        self.assertEqual(code, 1, output)
        self.assertIn("index.json is missing or stale", output)
        code, output = self.drive("--write")
        self.assertEqual((code, output.strip()), (0, "wrote index.json"))
        written = self.path("index.json").read_text(encoding="utf-8")
        code, output = self.drive()
        self.assertEqual((code, output), (0, written))

    def test_a_skill_without_metadata_is_indexed_with_honest_defaults(self) -> None:
        """No sidecar means no metadata_path, and the quality score must say so."""
        skill = self.add_skill(
            "zz-bare", '---\nname: zz-bare\ndescription: "Use when testing."\n---\n\n# Bare\n'
        )
        self.assertIsNone(skill["metadata_path"])
        self.assertFalse(skill["quality"]["checks"]["metadata"])
        self.assertEqual((skill["kind"], skill["bundle"]), ("general", None))
        self.assertEqual(skill["maturity"], "hardened")
        self.assertEqual(skill["description"], "Use when testing.")

    def test_a_skill_without_frontmatter_is_named_after_its_directory(self) -> None:
        skill = self.add_skill("zz-plain", "# No frontmatter at all\n", {"bundle": "noyalib"})
        self.assertEqual(skill["name"], "zz-plain")
        self.assertEqual(skill["description"], "")
        self.assertEqual((skill["kind"], skill["bundle"]), ("project", "noyalib"))
        self.assertIn("noyalib", skill["tags"])

    def test_frontmatter_parsing_follows_the_yaml_shapes_skills_use(self) -> None:
        parse = self.script().parse_frontmatter
        self.assertEqual(parse("no frontmatter\n"), {})
        # An indented line before any key belongs to nothing and is dropped.
        self.assertEqual(parse("---\n  stray\nname: x\n---\n"), {"name": "x"})
        # A block with only continuation lines has no keys at all.
        self.assertEqual(parse("---\n  stray\n---\n"), {})
        folded = parse("---\ndescription: >\n  first line\n  second line\n---\n")
        self.assertEqual(folded, {"description": "first line second line"})
        # The final key is unquoted like every other: for a command file,
        # `description` is the last key.
        self.assertEqual(parse('---\nname: a\ndescription: "b"\n---\n'), {"name": "a", "description": "b"})

    def test_quoted_scalars_lose_their_quotes_and_keep_their_escapes(self) -> None:
        unquote = self.script().unquote
        self.assertEqual(unquote('"say \\"hi\\""'), 'say "hi"')
        self.assertEqual(unquote("'it''s'"), "it's")
        self.assertEqual(unquote("\"mismatched'"), "\"mismatched'")
        self.assertEqual(unquote('"'), '"')

    def test_an_unchanged_skill_keeps_the_release_it_last_changed_in(self) -> None:
        """Stamping every skill with the current release made all of them look new."""
        self.preserve("index.json")
        self.path("index.json").write_text(json.dumps({"skills": [
            {"name": "kept", "integrity": "sha256-a", "last_changed_version": "0.0.2"},
            {"name": "moved", "integrity": "sha256-old", "last_changed_version": "0.0.2"},
            "not a skill entry",
        ]}), encoding="utf-8")
        skills = [
            {"name": "kept", "integrity": "sha256-a"},
            {"name": "moved", "integrity": "sha256-new"},
            {"name": "added", "integrity": "sha256-b"},
        ]
        self.script().apply_change_tracking(skills, "0.0.9")
        self.assertEqual(
            [s["last_changed_version"] for s in skills], ["0.0.2", "0.0.9", "0.0.9"]
        )

    def test_with_no_readable_index_every_skill_changed_in_this_release(self) -> None:
        self.preserve("index.json")
        for state in ("missing", "corrupt"):
            with self.subTest(index=state):
                if state == "missing":
                    self.path("index.json").unlink()
                else:
                    self.path("index.json").write_text("{not json", encoding="utf-8")
                skills = [{"name": "using-agtmls", "integrity": "sha256-x"}]
                self.script().apply_change_tracking(skills, "0.0.9")
                self.assertEqual(skills[0]["last_changed_version"], "0.0.9")


class BenchmarkDocEdgeTests(SubsetCase):
    """The refusals test_benchmark_doc.py does not reach."""

    SCRIPT = "generate-benchmarks-doc.py"
    SUBSET = ("BENCHMARKS.md", "benchmarks", "bench-baseline.json")

    def test_an_unknown_block_is_reported_rather_than_left_alone(self) -> None:
        """A misspelt marker would otherwise hold hand-typed numbers forever."""
        self.preserve("BENCHMARKS.md")
        doc = self.path("BENCHMARKS.md")
        doc.write_text(
            doc.read_text(encoding="utf-8")
            + '\n<!-- generated:latencies sources="" -->\n1.00ms\n<!-- /generated:latencies -->\n',
            encoding="utf-8",
        )
        code, output = self.drive("--check")
        self.assertEqual(code, 1, output)
        self.assertIn("latencies: unknown generated block", output)

    def test_write_refuses_a_document_missing_a_block_and_leaves_it_alone(self) -> None:
        self.preserve("BENCHMARKS.md")
        module = self.script()
        doc = self.path("BENCHMARKS.md")
        text = module.BLOCK.sub(
            lambda m: "" if m.group("name") == "scaling" else m.group(0),
            doc.read_text(encoding="utf-8"),
        )
        doc.write_text(text, encoding="utf-8")
        code, output = self.drive("--write", module=module)
        self.assertEqual(code, 1, output)
        self.assertIn("scaling: no generated block in BENCHMARKS.md; add its markers first", output)
        self.assertEqual(doc.read_text(encoding="utf-8"), text)

    def test_no_flag_is_a_usage_error(self) -> None:
        code, output = self.drive()
        self.assertEqual(code, 2)
        self.assertIn("--write", output)
