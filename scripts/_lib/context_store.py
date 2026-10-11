# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Local SQLite context and full-text search (FTS5) store for skills.

Provides zero-dependency indexed storage and BM25 relevance ranking
for agent skills, instructions, and context metadata.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SAFE_FTS_CHARS = re.compile(r'[^a-zA-Z0-9\s]')


@dataclass(frozen=True)
class SearchResult:
    """A scored result from context search."""

    id: str
    name: str
    description: str
    tags: list[str]
    path: str
    score: float
    snippet: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize result to dictionary."""
        return asdict(self)


def sanitize_query(query: str) -> str:
    """Sanitize user search query for safe FTS5 MATCH execution."""
    cleaned = SAFE_FTS_CHARS.sub(" ", query).strip()
    tokens = [t for t in cleaned.split() if t.isalnum()]
    if not tokens:
        return '""'
    return " ".join(f'"{t}"*' for t in tokens)


class ContextStore:
    """SQLite-backed full-text search store with BM25 ranking."""

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self.db_path = str(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS skills (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    path TEXT NOT NULL,
                    digest TEXT NOT NULL,
                    content TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            self.conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS skills_fts USING fts5(
                    id UNINDEXED,
                    name,
                    description,
                    tags,
                    content,
                    tokenize='porter unicode61'
                )
            """)

    def index_skill(
        self,
        id: str,
        name: str,
        description: str,
        tags: list[str],
        path: str,
        content: str = "",
        digest: str = "",
    ) -> None:
        """Insert or update a skill in the context store and search index."""
        tags_str = " ".join(sorted(set(tags)))
        now = datetime.now(timezone.utc).isoformat()

        with self.conn:
            self.conn.execute(
                """
                INSERT INTO skills (id, name, description, tags, path, digest, content, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description,
                    tags = excluded.tags,
                    path = excluded.path,
                    digest = excluded.digest,
                    content = excluded.content,
                    updated_at = excluded.updated_at
                """,
                (id, name, description, tags_str, path, digest, content, now),
            )
            self.conn.execute("DELETE FROM skills_fts WHERE id = ?", (id,))
            self.conn.execute(
                """
                INSERT INTO skills_fts (id, name, description, tags, content)
                VALUES (?, ?, ?, ?, ?)
                """,
                (id, name, description, tags_str, content),
            )

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Perform BM25 full-text search against indexed skills."""
        match_expr = sanitize_query(query)
        if match_expr == '""':
            return []

        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT
                s.id, s.name, s.description, s.tags, s.path,
                bm25(skills_fts) as rank,
                snippet(skills_fts, 2, '<b>', '</b>', '...', 16) as snip
            FROM skills_fts f
            JOIN skills s ON s.id = f.id
            WHERE skills_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (match_expr, limit),
        )

        results: list[SearchResult] = []
        for row in cursor.fetchall():
            tags_list = row["tags"].split() if row["tags"] else []
            # In SQLite FTS5, lower bm25 score means more relevant, so we negate it for score
            score = round(-float(row["rank"]), 4)
            results.append(
                SearchResult(
                    id=row["id"],
                    name=row["name"],
                    description=row["description"],
                    tags=tags_list,
                    path=row["path"],
                    score=score,
                    snippet=row["snip"] or row["description"],
                )
            )
        return results

    def get_skill(self, id: str) -> dict[str, Any] | None:
        """Fetch a skill record by its unique identifier."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM skills WHERE id = ?", (id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    def count(self) -> int:
        """Return total count of indexed skills."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM skills")
        return int(cursor.fetchone()[0])

    def close(self) -> None:
        """Close SQLite connection."""
        self.conn.close()

    def __enter__(self) -> ContextStore:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
