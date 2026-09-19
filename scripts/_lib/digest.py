# SPDX-FileCopyrightText: 2026 Sebastien Rousseau
# SPDX-License-Identifier: Apache-2.0 OR MIT
"""Content-addressed identity for a skill.

Normative definition: agtmls-spec/spec/03-integrity.md. This is the reference
implementation; agtmls-core carries a second one in Rust, and the shared test
vectors in agtmls-spec/corpus/digest/cases.json are what keep them honest.

The digest is over a manifest of (relative path, file content hash) pairs
rather than over a tarball, so it is identical across a git clone, a `--copy`
install, an extracted wheel and a release tarball. That property is the whole
point: without it there is nothing to compare an installed skill against.

Rules that matter, and why:

  * Paths are sorted by their UTF-8 bytes, not by locale collation, so the
    digest does not change with LANG.
  * Mode bits are not hashed. The executable bit does not survive every
    transport (zip on Windows, some CI artifact paths), and a digest that
    changes based on how a file arrived is useless for verification. The
    lockfile records modes separately.
  * Symlinks are excluded and reported, never followed. Following them would
    make the digest depend on files outside the skill, and a skill that needs
    a symlink is not portable anyway.
  * Empty directories are not represented. A directory is its files.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

# Never part of a skill's identity: build caches, VCS internals, editor and
# OS debris. A skill whose digest moved because macOS wrote .DS_Store would
# report a false integrity failure.
EXCLUDED_NAMES = {".DS_Store", "Thumbs.db"}
EXCLUDED_DIRS = {"__pycache__", ".git", ".agtmls", "node_modules", ".venv"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".swp"}
ALGORITHM = "sha256"


def is_included(path: Path, root: Path) -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    relative = path.relative_to(root)
    if EXCLUDED_DIRS & set(relative.parts[:-1]):
        return False
    return path.name not in EXCLUDED_NAMES and path.suffix not in EXCLUDED_SUFFIXES


def manifest(root: Path) -> list[tuple[str, str]]:
    """The (path, content-hash) pairs the digest is taken over.

    Returned separately from digest() so a mismatch can be explained: knowing
    that two trees differ is much less useful than knowing which file did.
    """
    entries: list[tuple[str, str]] = []
    for path in root.rglob("*"):
        if not is_included(path, root):
            continue
        relative = path.relative_to(root).as_posix()
        entries.append((relative, hashlib.sha256(path.read_bytes()).hexdigest()))
    # Sort on the encoded path so ordering is byte-wise and locale-independent.
    entries.sort(key=lambda item: item[0].encode("utf-8"))
    return entries


def symlinks(root: Path) -> list[str]:
    """Symlinks skipped by the digest, so a caller can report them."""
    return sorted(
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_symlink()
    )


def digest_from_manifest(entries: list[tuple[str, str]]) -> str:
    accumulator = hashlib.sha256()
    for relative, content_hash in entries:
        accumulator.update(relative.encode("utf-8"))
        accumulator.update(b"\x00")
        accumulator.update(bytes.fromhex(content_hash))
        accumulator.update(b"\x00")
    return f"{ALGORITHM}:{accumulator.hexdigest()}"


def skill_digest(root: Path) -> str:
    """Stable content address for the skill directory at `root`."""
    return digest_from_manifest(manifest(root))
