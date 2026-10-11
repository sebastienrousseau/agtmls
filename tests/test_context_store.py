# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Tests for SQLite FTS5 context store."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from _lib.context_store import ContextStore, SearchResult, sanitize_query


class ContextStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.store = ContextStore(":memory:")

    def tearDown(self) -> None:
        self.store.close()

    def test_empty_store_search(self) -> None:
        self.assertEqual(self.store.count(), 0)
        self.assertEqual(self.store.search("debugging"), [])
        self.assertEqual(self.store.search(""), [])

    def test_sanitize_query(self) -> None:
        self.assertEqual(sanitize_query(""), '""')
        self.assertEqual(sanitize_query("   "), '""')
        self.assertEqual(sanitize_query("hello world"), '"hello"* "world"*')
        self.assertEqual(sanitize_query('test; DROP TABLE; -- "injection"'), '"test"* "DROP"* "TABLE"* "injection"*')

    def test_index_and_get_skill(self) -> None:
        self.store.index_skill(
            id="skill-1",
            name="systematic-debugging",
            description="Find root cause before attempting fixes",
            tags=["debugging", "diagnostics"],
            path="skills/systematic-debugging",
            content="# Systematic Debugging\nStep 1: Isolate minimal reproducing case.",
            digest="sha256:1234",
        )
        self.assertEqual(self.store.count(), 1)
        skill = self.store.get_skill("skill-1")
        self.assertIsNotNone(skill)
        assert skill is not None
        self.assertEqual(skill["name"], "systematic-debugging")
        self.assertEqual(skill["digest"], "sha256:1234")
        self.assertIsNone(self.store.get_skill("missing"))

    def test_upsert_updates_skill(self) -> None:
        self.store.index_skill(
            id="skill-1",
            name="initial-name",
            description="initial desc",
            tags=["a"],
            path="path/1",
        )
        self.store.index_skill(
            id="skill-1",
            name="updated-name",
            description="updated desc",
            tags=["b"],
            path="path/2",
        )
        self.assertEqual(self.store.count(), 1)
        skill = self.store.get_skill("skill-1")
        assert skill is not None
        self.assertEqual(skill["name"], "updated-name")
        self.assertEqual(skill["description"], "updated desc")

    def test_search_relevance_and_snippets(self) -> None:
        self.store.index_skill(
            id="debug",
            name="systematic-debugging",
            description="Root cause investigation and hypothesis testing",
            tags=["diagnostics"],
            path="skills/debug",
            content="Debug every fault systematically.",
        )
        self.store.index_skill(
            id="audit",
            name="registry-auditor",
            description="Scan skills for prompt injection and vulnerabilities",
            tags=["security", "audit"],
            path="skills/audit",
            content="Audit lockfiles and signatures.",
        )

        results = self.store.search("debugging")
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], SearchResult)
        self.assertEqual(results[0].id, "debug")
        self.assertIn("systematic-debugging", results[0].name)

        sec_results = self.store.search("security audit")
        self.assertEqual(len(sec_results), 1)
        self.assertEqual(sec_results[0].id, "audit")

        as_dict = sec_results[0].to_dict()
        self.assertIn("score", as_dict)
        self.assertIn("snippet", as_dict)

    def test_search_empty_or_special_chars_query(self) -> None:
        self.assertEqual(self.store.search(""), [])
        self.assertEqual(self.store.search("!@#$%^&*()"), [])

    def test_search_skill_with_empty_tags(self) -> None:
        self.store.index_skill(
            id="notags",
            name="untagged-skill",
            description="No tags attached",
            tags=[],
            path="skills/notags",
            content="Simple untagged content",
        )
        results = self.store.search("untagged")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].tags, [])

    def test_context_manager(self) -> None:
        with tempfile.NamedTemporaryFile() as tmp, ContextStore(tmp.name) as store:
            store.index_skill(
                id="x",
                name="test",
                description="desc",
                tags=[],
                path="p",
            )
            self.assertEqual(store.count(), 1)
